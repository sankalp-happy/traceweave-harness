"""A learned combiner: static analysis + three LLMs' answers + the code's shape -> is this call real?

Static analysers are precise and miss calls; LLMs find more calls and claim
some that never happen (bench.py, resolve.py). This model learns how far to
trust each of them, and when, from the ground truth itself.

Logistic regression, written out here: a dozen features and about a thousand
items need no ML library. It is trained and scored with 5-fold cross-validation
grouped by caller function, so no function's items are ever scored by a model
that saw them in training; every number it reports is out-of-fold. It uses only
items whose caller every LLM answered.

  python3 tw.py learn click toolz
"""
from __future__ import annotations

import math
import random

import bench
import resolve
from graph import Bundle

SEED = 20261016
LLMS = ("groq:openai/gpt-oss-20b", "groq:openai/gpt-oss-120b", "groq:qwen/qwen3.8-27b")
FEATURES = ("PyCG says yes", "Pyright says yes", "gpt-oss-20b says yes", "gpt-oss-120b says yes",
            "qwen3.8-27b says yes", "written as a call", "written as a reference", "written as a class name",
            "name shared with other functions", "method of the caller's own class")


def featurize(bundle: Bundle, i: dict, votes: list[bool]) -> list[float]:
    owner = lambda k: bundle.nodes[k]["qualname"].rsplit(".", 1)[0] if bundle.nodes[k]["kind"] == "method" else None
    return [float(i["pycg"]), float(i["pyright"]), *map(float, votes),
            float(i["style"] == "call"), float(i["style"] == "reference"), float(i["style"] == "constructor"),
            float(i["shared"] > 1), float(owner(i["callee"]) is not None and owner(i["callee"]) == owner(i["caller"]))]


def rows(names: list[str]) -> list[dict]:
    out = []
    for name in names:
        b = Bundle(name)
        llm = resolve.answers(b)
        for i in bench.items(b):
            if all(i["caller"] in llm.get(m, {}) for m in LLMS):
                votes = [i["callee"] in llm[m][i["caller"]] for m in LLMS]
                out.append({"group": f"{name}:{i['caller']}", "x": featurize(b, i, votes), "y": float(i["label"]),
                            "item": i, "votes": votes, "repo": name})
    return out


def fit(data: list[dict], l2: float = 0.5, epochs: int = 3000, lr: float = 0.3) -> list[float]:
    """Weights (bias first) by full-batch gradient descent on the L2-regularised log loss."""
    w = [0.0] * (len(data[0]["x"]) + 1)
    n = len(data)
    for _ in range(epochs):
        grad = [0.0] * len(w)
        for r in data:
            p = predict(w, r["x"])
            err = p - r["y"]
            grad[0] += err
            for j, xj in enumerate(r["x"], 1):
                grad[j] += err * xj
        for j in range(len(w)):
            w[j] -= lr * (grad[j] / n + (l2 * w[j] / n if j else 0.0))
    return w


def predict(w: list[float], x: list[float]) -> float:
    z = w[0] + sum(wj * xj for wj, xj in zip(w[1:], x))
    return 1 / (1 + math.exp(-max(-30, min(30, z))))


def cross_val(data: list[dict], k: int = 5) -> list[float]:
    """Out-of-fold probabilities, folds grouped by caller function."""
    groups = sorted({r["group"] for r in data})
    random.Random(SEED).shuffle(groups)
    fold = {g: n % k for n, g in enumerate(groups)}
    probs = [0.0] * len(data)
    for f in range(k):
        w = fit([r for r in data if fold[r["group"]] != f])
        for n, r in enumerate(data):
            if fold[r["group"]] == f:
                probs[n] = predict(w, r["x"])
    return probs


def report(names: list[str]) -> dict:
    data = rows(names)
    probs = cross_val(data)
    items = [dict(r["item"], _p=p, _votes=r["votes"]) for r, p in zip(data, probs)]
    resolvers = {
        "PyCG ∪ Pyright": lambda i: i["pycg"] or i["pyright"],
        **{m.split("/")[-1]: (lambda i, n=n: i["_votes"][n]) for n, m in enumerate(LLMS)},
        "majority of the 3 LLMs": lambda i: sum(i["_votes"]) >= 2,
        "static ∪ any LLM": lambda i: i["pycg"] or i["pyright"] or any(i["_votes"]),
        "learned combiner": lambda i: i["_p"] >= 0.5,
    }
    w = fit(data)
    return {"items": len(items), "callers": len({r["group"] for r in data}), "real": int(sum(r["y"] for r in data)),
            "folds": 5, "seed": SEED, "llms": list(LLMS),
            "predictions": [{"repo": r["repo"], "caller": r["item"]["caller"], "callee": r["item"]["callee"],
                             "p": round(p, 4)} for r, p in zip(data, probs)],
            "scores": {k: bench.score(items, f) for k, f in resolvers.items()},
            "shared": {k: bench.score([i for i in items if i["shared"] > 1], f) for k, f in resolvers.items()},
            "weights": dict(zip(("bias",) + FEATURES, (round(x, 2) for x in w)))}
