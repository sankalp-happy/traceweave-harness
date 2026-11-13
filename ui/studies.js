"use strict";
// The two AI studies and the pages around them: Overview (the precision-recall
// plane), Study 1 (who can find the calls), Study 2 (can an AI agent make the
// change), Method (how the truth is recorded). Every number comes from
// /api/truth, /api/study1, /api/study2; live runs stream from /api/live.

const AI = { model: "groq:openai/gpt-oss-120b", editors: [], cache: {}, busy: false };
const AI_NAME = { "groq:openai/gpt-oss-20b": "gpt-oss-20b", "groq:openai/gpt-oss-120b": "gpt-oss-120b", "groq:qwen/qwen3.8-27b": "qwen3.8-27b" };
const KIND = { "name match": "baseline", PyCG: "static", Pyright: "static", "PyCG ∪ Pyright": "static",
  "gpt-oss-20b": "ai", "gpt-oss-120b": "ai", "qwen3.8-27b": "ai", "majority of the 3 LLMs": "ai", "learned combiner": "combiner" };
const KIND_NAME = { static: "Static analysers", ai: "AI models", combiner: "Learned combiner", baseline: "Baseline" };
const RESOLVER_NAME = { "name match": "Name match (grep)", "PyCG ∪ Pyright": "PyCG + Pyright", "majority of the 3 LLMs": "Majority of the 3 AI models", "learned combiner": "Learned combiner" };
const rname = (r) => RESOLVER_NAME[r] || r;
const pct = (x) => `${Math.round(100 * x)}%`;
const dec = (x) => x.toFixed(2);
const shortName = (q) => q.split(".").pop();
const rowId = (r) => `r-${r.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "")}`;

async function cached(path) {
  AI.cache[path] ??= await api(path);
  return AI.cache[path];
}

function sse(params, onEvent) {
  return new Promise((resolve, reject) => {
    const es = new EventSource(`/api/live?${new URLSearchParams(params)}`);
    let failure = null;
    es.onmessage = (m) => {
      const e = JSON.parse(m.data);
      if (e.type === "error") failure = e.message; else onEvent(e);
    };
    es.addEventListener("end", () => { es.close(); failure ? reject(new Error(failure)) : resolve(); });
    es.onerror = () => { es.close(); reject(new Error(failure || "The connection to tw.py ui dropped. Check that it is still running.")); };
  });
}

async function loadEditors() {
  if (!AI.editors.length) AI.editors = await api("/api/editors");
  return AI.editors;
}
const aiReady = () => AI.editors.find((e) => e.id === AI.model)?.ready;
const aiWhy = () => AI.editors.find((e) => e.id === AI.model)?.why || "";

function aiSwitch() {
  const el = document.getElementById("status");
  const eds = AI.editors.filter((e) => e.id !== "oracle");
  if (!eds.length) { el.textContent = ""; return; }
  el.innerHTML = `<span id="ed-label">AI model</span><span class="seg" role="group" aria-labelledby="ed-label">${eds.map((e) =>
    `<button type="button" data-ai="${esc(e.id)}" aria-pressed="${e.id === AI.model}" ${e.ready ? "" : "disabled"}>${esc(e.name)}</button>`).join("")}</span>${
    eds.every((e) => !e.ready) ? `<span class="ed-off">AI is off: ${esc(eds[0].why || "")}</span>` : ""}`;
}

document.getElementById("status").addEventListener("click", (e) => {
  const b = e.target.closest("[data-ai]");
  if (!b || AI.busy || b.dataset.ai === AI.model) return;
  AI.model = b.dataset.ai;
  aiSwitch();
  document.dispatchEvent(new CustomEvent("ai-model"));
});

// ---------------------------------------------------------------- the plane
function planePoints(s1) {
  return s1.resolvers.filter((r) => r !== "majority of the 3 LLMs").map((r) => ({ id: r, name: rname(r), kind: KIND[r], ...s1.leaderboard[r] }));
}

// Label offsets keep names off each other; tuned to these resolvers, they fall back to the right.
const LABEL_AT = { PyCG: [10, -10, "start"], Pyright: [-10, -12, "end"], "PyCG ∪ Pyright": [-12, 18, "end"],
  "gpt-oss-120b": [-4, 24, "end"], "gpt-oss-20b": [0, -14, "middle"], "qwen3.8-27b": [-12, 4, "end"],
  "learned combiner": [12, -14, "start"], "name match": [-12, -12, "end"] };

function planeSVG(points, { width = 800, height = 520, xs = [0.4, 1], ys = [0.2, 1], small = false } = {}) {
  const m = { l: 58, r: 26, t: 18, b: 50 };
  const X = (r) => m.l + ((r - xs[0]) / (xs[1] - xs[0])) * (width - m.l - m.r);
  const Y = (p) => height - m.b - ((p - ys[0]) / (ys[1] - ys[0])) * (height - m.t - m.b);
  const ticks = (a, b) => { const out = []; for (let v = a; v <= b + 1e-9; v += 0.2) out.push(+v.toFixed(1)); return out; };
  const grid = ticks(xs[0], xs[1]).map((v) => `<line x1="${X(v)}" y1="${m.t}" x2="${X(v)}" y2="${height - m.b}" class="grid"/><text x="${X(v)}" y="${height - m.b + 18}" class="tick" text-anchor="middle">${v.toFixed(1)}</text>`).join("")
    + ticks(ys[0], ys[1]).map((v) => `<line x1="${m.l}" y1="${Y(v)}" x2="${width - m.r}" y2="${Y(v)}" class="grid"/><text x="${m.l - 8}" y="${Y(v) + 4}" class="tick" text-anchor="end">${v.toFixed(1)}</text>`).join("");
  // F1 contours: every point on one has the same F1 = 2pr/(p+r).
  const contours = [0.7, 0.8, 0.9].map((f) => {
    const pts = [];
    for (let r = xs[0]; r <= 1.0001; r += 0.005) {
      const p = (f * r) / (2 * r - f);
      if (2 * r > f && p >= ys[0] && p <= 1) pts.push(`${X(r).toFixed(1)},${Y(p).toFixed(1)}`);
    }
    const last = pts[pts.length - 1]?.split(",");
    return pts.length > 1 ? `<polyline points="${pts.join(" ")}" class="contour"/>${last ? `<text x="${+last[0] - 4}" y="${+last[1] - 6}" class="contour-label" text-anchor="end">F1 ${f}</text>` : ""}` : "";
  }).join("");
  const mark = (pt) => {
    const x = X(pt.recall), y = Y(pt.precision);
    const shape = pt.kind === "static" ? `<rect x="${x - 6}" y="${y - 6}" width="12" height="12" class="mk static"/>`
      : pt.kind === "combiner" ? `<path d="M${x} ${y - 10} L${x + 10} ${y} L${x} ${y + 10} L${x - 10} ${y} Z" class="mk combiner"/>`
        : pt.kind === "baseline" ? `<path d="M${x} ${y - 7} L${x + 7} ${y + 6} L${x - 7} ${y + 6} Z" class="mk baseline"/>`
          : `<circle cx="${x}" cy="${y}" r="6.5" class="mk ai"/>`;
    const [dx, dy, anchor] = LABEL_AT[pt.id] || [10, 4, "start"];
    return `<a href="#/study1?focus=${rowId(pt.id)}" class="pt" data-pt="${esc(pt.id)}" aria-label="${esc(pt.name)}: precision ${dec(pt.precision)}, recall ${dec(pt.recall)}, F1 ${dec(pt.f1)}">
      <circle cx="${x}" cy="${y}" r="16" class="hit"/>${shape}
      ${small ? "" : `<text x="${x + dx}" y="${y + dy}" text-anchor="${anchor}" class="pt-label ${pt.kind}">${esc(pt.name)}</text>`}</a>`;
  };
  const notes = small ? "" : `<text x="${X(0.64)}" y="${Y(0.985)}" class="plane-note" text-anchor="middle">precise, but blind</text>
    <text x="${X(0.86)}" y="${Y(0.615)}" class="plane-note" text-anchor="middle">sees more, and guesses</text>`;
  return `<svg viewBox="0 0 ${width} ${height}" class="plane-svg" role="img" aria-label="Precision against recall for each resolver">
    ${grid}${contours}${notes}
    <line x1="${m.l}" y1="${height - m.b}" x2="${width - m.r}" y2="${height - m.b}" class="axis"/><line x1="${m.l}" y1="${m.t}" x2="${m.l}" y2="${height - m.b}" class="axis"/>
    <text x="${(m.l + width - m.r) / 2}" y="${height - 8}" text-anchor="middle" class="axis-title">Recall: share of the real calls it found →</text>
    <text x="16" y="${(m.t + height - m.b) / 2}" text-anchor="middle" class="axis-title" transform="rotate(-90 16 ${(m.t + height - m.b) / 2})">Precision: share of its claims that were real →</text>
    ${points.map(mark).join("")}
  </svg>`;
}

function planeLegend() {
  return `<div class="legend plane-legend">
    <span><svg width="14" height="14" aria-hidden="true"><rect x="1" y="1" width="12" height="12" class="mk static"/></svg>${KIND_NAME.static}</span>
    <span><svg width="14" height="14" aria-hidden="true"><circle cx="7" cy="7" r="6" class="mk ai"/></svg>${KIND_NAME.ai}</span>
    <span><svg width="18" height="18" aria-hidden="true"><path d="M9 1 L17 9 L9 17 L1 9 Z" class="mk combiner"/></svg>${KIND_NAME.combiner}</span>
    <span><svg width="14" height="14" aria-hidden="true"><path d="M7 1 L13 12 L1 12 Z" class="mk baseline"/></svg>Baseline: every named function (grep)</span>
  </div>`;
}

function wireTooltips(root, points) {
  const tip = root.querySelector(".tip");
  const show = (el) => {
    const pt = points.find((p) => p.id === el.dataset.pt);
    if (!pt || !tip) return;
    tip.innerHTML = `<b>${esc(pt.name)}</b><span>precision <b>${dec(pt.precision)}</b> · recall <b>${dec(pt.recall)}</b> · F1 <b>${dec(pt.f1)}</b></span><span>${fmt(pt.tp)} real calls found, ${fmt(pt.fp)} claimed that never happened, ${fmt(pt.fn)} missed</span>`;
    const box = root.getBoundingClientRect(), r = el.querySelector(".hit").getBoundingClientRect();
    tip.style.left = `${Math.min(box.width - 260, Math.max(0, r.left - box.left + r.width / 2 - 130))}px`;
    tip.style.top = `${r.top - box.top - 8}px`;
    tip.hidden = false;
  };
  root.querySelectorAll(".pt").forEach((el) => {
    el.addEventListener("mouseenter", () => show(el));
    el.addEventListener("focus", () => show(el));
    el.addEventListener("mouseleave", () => { tip.hidden = true; });
    el.addEventListener("blur", () => { tip.hidden = true; });
  });
}

// ---------------------------------------------------------------- overview
function agentMatrix(s2, { compact = false } = {}) {
  const cell = (editor, cond) => s2.cells.find((c) => c.editor === editor && c.condition === cond);
  const n = s2.tasks.length;
  const show = (c) => (!c ? `<span class="pending">running</span>`
    : c.runs < n ? `<span class="frac partial"><b>${c.passed}</b> passed <small>· ${n - c.runs} running</small></span>`
      : `<span class="frac ${c.passed === n ? "all" : c.passed === 0 ? "none" : ""}"><b>${c.passed}</b> of ${n}</span>`);
  const llms = Object.values(AI_NAME);
  return `<table class="matrix${compact ? " compact" : ""}">
    <thead><tr><th scope="col">Editor</th><th scope="col">every line with the name <small>(grep)</small></th><th scope="col">static analysis</th><th scope="col">the test run</th></tr></thead>
    <tbody>
      <tr class="bound"><th scope="row">Regex rename</th><td colspan="3">${show(cell("regex", "-"))} <small>renames every occurrence</small></td></tr>
      ${llms.map((m) => `<tr><th scope="row">${esc(m)}</th>${s2.conditions.map((c) => `<td>${show(cell(m, c))}</td>`).join("")}</tr>`).join("")}
      <tr class="bound"><th scope="row">Exact rename</th><td colspan="3">${show(cell("exact rename", "-"))} <small>the lines the test run saw</small></td></tr>
    </tbody></table>`;
}

async function renderOverview() {
  const [truth, s1, s2] = await Promise.all([cached("/api/truth"), cached("/api/study1"), cached("/api/study2")]);
  const click = truth.find((t) => t.repo === "click") || truth[0];
  const lb = s1.leaderboard, ai = ["gpt-oss-20b", "gpt-oss-120b", "qwen3.8-27b"];
  const best = ai.reduce((a, b) => (lb[b].recall > lb[a].recall ? b : a));
  const bestF1 = ai.reduce((a, b) => (lb[b].f1 > lb[a].f1 ? b : a));
  const st = lb["PyCG ∪ Pyright"], comb = lb["learned combiner"];
  const held = click.static["PyCG ∪ Pyright"] / click.pairs;
  const tz = s1.by_repo.toolz;
  const points = planePoints(s1);
  const f = s1.featured;
  view.innerHTML = `
  <div class="ov">
    <section class="ov-main">
      <h1>Static analysis is precise but blind. AI sees more, and guesses.</h1>
      <p class="lede">Each point is one way to answer “does this line of code call that function?” for ${fmt(s1.sample.items)} places in two real Python projects, scored against every call their test suites actually made.</p>
      <div class="ov-act">
        <button class="run" type="button" data-try>Try one function live</button>
        <p class="fine">Asks ${esc(AI_NAME[AI.model])} which functions <code>${esc(f ? shortName(f.caller.split("::").pop()) : "")}</code> in click calls, then checks its answer against the recorded calls.</p>
      </div>
      <figure class="plane">
        ${planeLegend()}
        <div class="plane-scroll"><div class="plane-wrap">${planeSVG(points, { height: 470 })}<div class="tip" role="status" hidden></div></div></div>
        <figcaption>Figure 1. Precision and recall of each resolver on the same ${fmt(s1.sample.items)} items from ${s1.sample.functions} functions. Curves join points with equal F1. <span class="phone-only">Scroll the chart sideways to see every point. </span><a href="#/study1">The items, the table and every answer</a></figcaption>
      </figure>
    </section>
    <aside class="ov-side">
      <h2>Findings</h2>
      <ol class="findings">
        <li>While click's ${fmt(click.tests)} tests ran, its functions called each other along <b>${fmt(click.pairs)}</b> distinct paths. PyCG and Pyright together hold <b>${pct(held)}</b> of those ${fmt(click.pairs)} paths: static analysis misses about ${held > 0.6 && held < 0.75 ? "a third" : pct(1 - held)} of what really runs.</li>
        <li>AI models find more. ${esc(best)} finds <b>${pct(lb[best].recall)}</b> of the real calls among the ${fmt(s1.sample.items)} places in the chart (static analysis: ${pct(st.recall)}), but <b>${pct(1 - lb[best].precision)}</b> of the calls it claims never happen${tz ? `, and in toolz, where static analysis is already nearly perfect, ${pct(1 - tz.scores[best].precision)} of its claims are wrong` : ""}.</li>
        <li>A learned combiner of both, trained on the recorded calls and scored on functions it never saw, reaches <b>F1 ${dec(comb.f1)}</b>: above static analysis (${dec(st.f1)}) and the best single AI model (${dec(lb[bestF1].f1)}).</li>
      </ol>
      <h2>Can an AI agent rename the right function?</h2>
      <p class="fine side-lede">${s2.tasks.length} renames of a function that shares its name with another, so a regex breaks the project. The agent sees one of three kinds of context; the project's tests judge.</p>
      ${agentMatrix(s2, { compact: true })}
      <p class="more"><a href="#/study2">Study 2: every task and every run</a></p>
    </aside>
  </div>`;
  wireTooltips(view.querySelector(".plane-wrap"), points);
  view.querySelector("[data-try]").addEventListener("click", () => {
    if (f) location.hash = `#/study1/fn/${encodeURIComponent(f.repo)}/${encodeURIComponent(f.caller)}?ask=1`;
  });
}

// ---------------------------------------------------------------- study 1
function bar(x, cls = "") { return `<span class="hbar ${cls}"><i style="width:${Math.max(0, Math.min(1, x)) * 100}%"></i></span>`; }

async function renderStudy1(params) {
  const s1 = await cached("/api/study1");
  const lb = s1.leaderboard, rows = s1.resolvers;
  const points = planePoints(s1);
  const cats = Object.entries(s1.categories);
  const show = ["PyCG ∪ Pyright", "gpt-oss-120b", "learned combiner"];
  const weights = Object.entries(s1.weights).filter(([k]) => k !== "bias");
  const wmax = Math.max(...weights.map(([, v]) => Math.abs(v)), 1);
  const filter = params.get("only") || "missed";
  const fns = s1.functions.filter((f) => filter === "all" || (filter === "missed" ? f.static_missed : f.shared));
  view.innerHTML = `
  <div class="study">
    <header class="study-head">
      <p class="crumb"><a href="#/">Overview</a></p>
      <h1>Study 1 · Who can find the calls?</h1>
      <p class="lede">An item is one place where a project function is named in code that ran: “does this function call that one?” The answer comes from the test run, which recorded every call. Static analysers answer from the code alone; each AI model reads the function and the candidates and answers; the learned combiner weighs all of them.</p>
    </header>
    <section class="s1-top">
      <div class="s1-left">
      <figure class="plane small">
        ${planeLegend()}
        <div class="plane-scroll"><div class="plane-wrap">${planeSVG(points, { width: 640, height: 430 })}<div class="tip" role="status" hidden></div></div></div>
        <figcaption>Figure 1. The same plane as the overview.</figcaption>
      </figure>
      <table class="board-t by-repo">
          <caption>Table 1b. The same, project by project <span class="muted">(precision / recall)</span></caption>
          <thead><tr><th scope="col">Resolver</th>${Object.keys(s1.by_repo).map((r) => `<th scope="col">${esc(r)} <small>${fmt(s1.by_repo[r].items)} items</small></th>`).join("")}</tr></thead>
          <tbody>${["PyCG ∪ Pyright", "gpt-oss-120b", "learned combiner"].map((r) => `<tr class="${KIND[r]}"><th scope="row"><span class="kind-dot ${KIND[r]}" aria-hidden="true"></span>${esc(rname(r))}</th>${Object.values(s1.by_repo).map((v) => `<td>${dec(v.scores[r].precision)} / ${dec(v.scores[r].recall)}</td>`).join("")}</tr>`).join("")}</tbody>
        </table>
      </div>

      <div>
        <table class="board-t" id="leaderboard">
          <caption>Table 1. Every resolver on the same ${fmt(s1.sample.items)} items <span class="muted">(${s1.sample.functions} functions, ${s1.sample.real} real calls)</span></caption>
          <thead><tr><th scope="col">Resolver</th><th scope="col">Precision</th><th scope="col">Recall</th><th scope="col">F1</th></tr></thead>
          <tbody>${rows.map((r) => `<tr id="${rowId(r)}" class="${KIND[r]}${r === "learned combiner" ? " best" : ""}${params.get("focus") === rowId(r) ? " target" : ""}"><th scope="row"><span class="kind-dot ${KIND[r]}" aria-hidden="true"></span>${esc(rname(r))}</th>
            <td>${dec(lb[r].precision)}</td><td>${dec(lb[r].recall)}</td><td>${bar(lb[r].f1, KIND[r])}<b>${dec(lb[r].f1)}</b></td></tr>`).join("")}</tbody>
        </table>
        <p class="table-note">The AI models answer a fixed random sample of the functions with at least one hard item (a shared name, a bare reference, or a pair static analysis gets wrong), because Groq's free tier allows about 200,000 tokens a day per model. On all ${fmt(s1.all.items)} items, static analysis scores precision ${dec(s1.static_on_all["PyCG ∪ Pyright"].precision)} and recall ${dec(s1.static_on_all["PyCG ∪ Pyright"].recall)}. A further ${fmt(s1.all.unnamed)} real calls never name their target (a callback invoked under another name), so no resolver here can find them.</p>
      </div>
    </section>
    <section class="s1-mid">
      <figure class="cats">
        <figcaption>Figure 2. Recall by how the function is written, for three resolvers</figcaption>
        <div class="legend">${show.map((r) => `<span><i class="sw ${KIND[r]}"></i>${esc(rname(r))}</span>`).join("")}</div>
        ${cats.map(([c, v]) => `<div class="cat-row"><div class="cat-name"><b>${esc({ "unique name": "Unique name", "shared name": "Name shared with other functions", call: "Written as a call: f(…)", reference: "Written without a call: obj.f", constructor: "A class name: Thing(…)" }[c])}</b><span>${fmt(v.real)} real calls in ${fmt(v.items)} items</span></div>
          <div class="cat-bars">${show.map((r) => `<div class="cb" title="${esc(rname(r))}: recall ${dec(v.scores[r].recall)}">${bar(v.scores[r].recall, KIND[r])}<span>${v.real ? dec(v.scores[r].recall) : "–"}</span></div>`).join("")}</div></div>`).join("")}
      </figure>
      <figure class="weights">
        <figcaption>Figure 3. What the learned combiner trusts <span class="muted">(logistic regression weights; ${s1.folds || 5}-fold cross-validation by function)</span></figcaption>
        ${weights.map(([k, v]) => `<div class="w-row"><span class="w-name">${esc(/^(gpt|qwen)/.test(k) ? k : k[0].toUpperCase() + k.slice(1))}</span><span class="w-bar"><span class="w-neg">${v < 0 ? `<i style="width:${(100 * -v) / wmax}%"></i>` : ""}</span><span class="w-pos">${v > 0 ? `<i style="width:${(100 * v) / wmax}%"></i>` : ""}</span></span><span class="w-val">${v > 0 ? "+" : ""}${v.toFixed(2)}</span></div>`).join("")}
        <p class="fine">Right of the centre line: makes a call more likely. It leans on gpt-oss-120b and Pyright, and doubts a name written without a call.</p>
      </figure>
    </section>
    <section class="s1-fns" id="functions">
      <div class="fns-head"><h2>Every function in the sample</h2>
        <div class="seg" role="group" aria-label="Which functions">${[["missed", "Static analysis misses a call"], ["shared", "A name is shared"], ["all", "All"]].map(([k, l]) => `<button type="button" data-only="${k}" aria-pressed="${filter === k}">${l}</button>`).join("")}</div></div>
      <p class="count">${fns.length} functions. Open one to see its code, every candidate and every answer, and to ask an AI model live.</p>
      <div class="scroll"><table class="fn-t">
        <thead><tr><th scope="col">Function</th><th scope="col">Candidates</th><th scope="col">Real calls</th><th scope="col">Static misses</th><th scope="col">Right: static</th><th scope="col">Right: ${esc(AI_NAME[AI.model])}</th><th scope="col">Right: combiner</th></tr></thead>
        <tbody>${fns.map((f) => { const href = `#/study1/fn/${encodeURIComponent(f.repo)}/${encodeURIComponent(f.caller)}`;
          const right = (r) => `<span class="${f.right[r] === f.items ? "allright" : ""}">${f.right[r]} of ${f.items}</span>`;
          return `<tr class="go" data-href="${href}"><td class="t"><a href="${href}">${esc(f.qualname)}</a> <span class="repo">${esc(f.repo)}</span></td><td>${f.items}</td><td>${f.real}</td><td>${f.static_missed || ""}</td><td>${right("PyCG ∪ Pyright")}</td><td>${right(AI_NAME[AI.model])}</td><td>${right("learned combiner")}</td></tr>`; }).join("")}</tbody>
      </table></div>
    </section>
  </div>`;
  wireTooltips(view.querySelector(".plane-wrap"), points);
  view.querySelectorAll("[data-only]").forEach((b) => b.addEventListener("click", () => { location.hash = `#/study1?only=${b.dataset.only}&focus=functions`; }));
}

async function renderFunction(repo, caller, params) {
  const d = await api(`/api/study1/fn?${new URLSearchParams({ repo, caller })}`);
  const llms = Object.values(AI_NAME);
  const live = { state: null, answer: null, seconds: null, error: null, reasoning: null };
  const names = new Set(d.candidates.map((c) => c.name));
  const lines = new Map();
  d.candidates.forEach((c) => c.lines.forEach((n) => lines.set(n, true)));
  const mark = (text) => esc(text).replace(/\b[A-Za-z_][A-Za-z0-9_]*\b/g, (w) => (names.has(w) ? `<mark>${w}</mark>` : w));
  const real = d.candidates.filter((c) => c.real).length;
  const cell = (says, isReal) => (says === null || says === undefined ? `<td class="na">–</td>`
    : `<td class="${says === isReal ? "ok" : "bad"}">${says ? "calls" : "no"}</td>`);
  const paint = () => {
    const ans = live.answer && new Map(live.answer.map((a) => [a.callee, a.says]));
    view.querySelector("#cands").innerHTML = d.candidates.map((c) => `<tr>
        <th scope="row"><code>${esc(c.qualname)}</code><small>${esc({ call: "written as a call", reference: "written without a call", constructor: "a class name" }[c.style])}${c.shared > 1 ? ` · ${c.shared} functions share the name` : ""}</small></th>
        <td class="truth ${c.real ? "yes" : "no"}">${c.real ? "calls" : "no"}</td>
        ${cell(c.pycg, c.real)}${cell(c.pyright, c.real)}${llms.map((m) => cell(c.llm[m], c.real)).join("")}
        ${cell(c.learned === null ? null : c.learned >= 0.5, c.real)}
        ${ans ? cell(ans.get(c.callee), c.real) : `<td class="na">${live.state === "asking" ? "…" : ""}</td>`}</tr>`).join("");
    const btn = view.querySelector("#ask");
    btn.disabled = AI.busy || !aiReady();
    btn.textContent = live.state === "asking" ? `Asking ${AI_NAME[AI.model]}…` : `Ask ${AI_NAME[AI.model]} now`;
    const right = ans ? d.candidates.filter((c) => ans.get(c.callee) === c.real).length : 0;
    view.querySelector("#ask-out").innerHTML = live.error ? `<p class="run-err">${esc(live.error)}</p>`
      : ans ? `<p class="say-sm"><b>${esc(AI_NAME[AI.model])}</b> answered in ${live.seconds} s and got <b>${right} of ${d.candidates.length}</b> right against the recorded calls.</p>${live.reasoning ? `<details class="prompt"><summary>What it wrote before answering</summary><pre>${esc(live.reasoning)}</pre></details>` : ""}`
        : !aiReady() ? `<p class="fine">${esc(aiWhy())}</p>` : `<p class="fine">Sends the same prompt the benchmark used, now, and scores the answer against the recorded calls.</p>`;
  };
  view.innerHTML = `
  <div class="study">
    <p class="crumb"><a href="#/study1">Study 1</a> / ${esc(d.repo)}</p>
    <h1 class="fn-title"><code>${esc(d.qualname)}</code></h1>
    <p class="lede">In ${esc(d.path)}. It names <b>${d.candidates.length}</b> project function${d.candidates.length === 1 ? "" : "s"} in code that ran; the test run shows it really calls <b>${real}</b> of them.</p>
    <div class="fn-grid">
      <section>
        <div class="code-file"><div class="fname">${esc(d.path)}</div><div class="code">${d.code.map((l) => `<div class="ln${lines.has(l.n) ? " hit" : ""}">${l.n}</div><div class="tx${lines.has(l.n) ? " hit" : ""}">${mark(l.text) || " "}</div>`).join("")}</div></div>
      </section>
      <section>
        <p class="fine cand-note">Blue: the resolver is right. Red: it is wrong. <span class="phone-only">Scroll the table sideways for every model.</span></p>
        <table class="cand-t">
          <caption>Each candidate, and what each resolver says</caption>
          <thead><tr><th scope="col">Candidate</th><th scope="col">Test run</th><th scope="col">PyCG</th><th scope="col">Pyright</th>${llms.map((m) => `<th scope="col">${esc(m)}</th>`).join("")}<th scope="col">Combiner</th><th scope="col">Live</th></tr></thead>
          <tbody id="cands"></tbody>
        </table>
        <div class="ask"><button class="run" id="ask" type="button"></button><div id="ask-out"></div></div>
        <details class="prompt"><summary>The exact prompt every AI model received</summary><pre>${esc(d.prompt)}</pre></details>
      </section>
    </div>
  </div>`;
  paint();
  const ask = async () => {
    if (AI.busy || !aiReady()) return;
    AI.busy = true;
    Object.assign(live, { state: "asking", answer: null, error: null });
    paint();
    try {
      await sse({ stage: "resolve", repo: d.repo, caller: d.caller, editor: AI.model }, (e) => {
        if (e.type === "answer") Object.assign(live, { answer: e.answers, seconds: e.seconds, reasoning: e.reasoning, error: e.error });
      });
    } catch (err) {
      live.error = err.message;
    } finally {
      AI.busy = false;
      live.state = null;
      paint();
    }
  };
  view.querySelector("#ask").addEventListener("click", ask);
  document.addEventListener("ai-model", paint, { once: true });
  if (params.get("ask") === "1") ask();
}

// ---------------------------------------------------------------- study 2
async function renderStudy2() {
  const s2 = await cached("/api/study2");
  view.innerHTML = `
  <div class="study">
    <header class="study-head">
      <p class="crumb"><a href="#/">Overview</a></p>
      <h1>Study 2 · Can an AI agent rename the right function?</h1>
      <p class="lede">Each task renames one function whose name another function also has: <code>Context.fail</code> but not <code>ParamType.fail</code>. Every call that reaches it must change and no other. A regex cannot do this. The AI agent gets the same instructions and one of three kinds of context; the project's own tests judge.</p>
    </header>
    <section class="s2-top">
      <div>
        <table class="matrix" id="matrix"><caption>Table 2. Renames that passed the test suite, out of ${s2.tasks.length}</caption></table>
      </div>
      <dl class="conds">
        <dt>Every line with the name (grep)</dt><dd>What an agent's search tool returns. The agent must work out which lines are calls to this function.</dd>
        <dt>Static analysis</dt><dd>The definition, plus the lines in callers PyCG or Pyright report.</dd>
        <dt>The test run</dt><dd>The definition, plus the lines the test run saw call it.</dd>
      </dl>
    </section>
    <section>
      <h2>The ${s2.tasks.length} tasks</h2>
      <p class="fine">Kept only if the right rename passes, a regex rename fails, and renaming the definition alone fails, each checked by running the tests. ${Object.values(s2.attrition).reduce((a, b) => a + b, 0)} other candidates were left out: ${Object.entries(s2.attrition).map(([k, v]) => `${v} because ${k}`).join(", ")}.</p>
      <div class="scroll"><table class="fn-t">
        <thead><tr><th scope="col">Rename</th><th scope="col">Lines with the name</th><th scope="col">Lines that call it</th><th scope="col" class="l">Other functions with the name</th></tr></thead>
        <tbody>${s2.tasks.map((t) => { const href = `#/study2/task/${encodeURIComponent(t.id)}`;
          return `<tr class="go" data-href="${href}"><td class="t"><a href="${href}">${esc(t.qualname)}</a></td><td>${t.named}</td><td>${t.right}</td><td class="l">${t.namesakes.map(esc).join(", ")}</td></tr>`; }).join("")}</tbody>
      </table></div>
    </section>
  </div>`;
  view.querySelector("#matrix").insertAdjacentHTML("beforeend", agentMatrix(s2).replace(/^<table class="matrix">|<\/table>$/g, ""));
}

async function renderAgentTask(id) {
  const d = await api(`/api/study2/task?${new URLSearchParams({ id })}`);
  const conds = [["grep", "Every line with the name"], ["static", "Static analysis"], ["runtime", "The test run"]];
  const live = { edits: {}, tests: {}, asking: null, error: null, running: null };
  const shownFor = { grep: () => true, static: (l) => l.static || l.right && l.path === d.path && l.n === d.line, runtime: (l) => l.right };
  const recorded = (c) => d.runs.find((r) => r.editor === AI_NAME[AI.model] && r.condition === c);
  const paint = () => {
    const lanes = conds.map(([c, label]) => {
      const lv = live.edits[c], rec = recorded(c), lt = live.tests[c];
      const edited = lv ? new Set(lv.lines.map((l) => `${l.path}:${l.line}`)) : rec ? new Set(rec.edits.map(([p, n]) => `${p}:${n}`)) : null;
      const squares = d.named.map((l) => {
        const key = `${l.path}:${l.n}`, shown = shownFor[c](l);
        const st = edited ? (edited.has(key) ? (l.right ? "done" : "wrongedit") : l.right ? "missed" : shown ? "kept" : "unshown")
          : shown ? (l.right ? "shown-right" : "shown") : "unshown";
        const label = `${l.path.split("/").pop()}:${l.n}, in ${l.in}: ${l.text}. ${{ done: "Renamed, rightly", wrongedit: "Renamed, wrongly: another function's line", missed: "Missed: still calls the old name", kept: "Another function's line, left alone", unshown: "Not shown to the agent", shown: "Another function's line, shown", "shown-right": "Calls this function, shown" }[st]}.`;
        return `<span class="sq ${st}" tabindex="0" role="img" aria-label="${esc(label)}" data-tip="${esc(label)}"></span>`;
      }).join("");
      const verdict = lt?.done ? lt : rec && !lv ? { pass: rec.pass, passed: rec.passed, failed: rec.failed, done: true, recorded: true } : null;
      const nRight = edited ? d.named.filter((l) => l.right && edited.has(`${l.path}:${l.n}`)).length : 0;
      const nWrong = edited ? d.named.filter((l) => !l.right && edited.has(`${l.path}:${l.n}`)).length : 0;
      return `<div class="lane2">
        <h3>${label}</h3>
        <div class="sqs">${squares}</div>
        <p class="lane-cap">${live.asking === c ? `Asking ${esc(AI_NAME[AI.model])}…`
          : edited ? `Renamed <b>${nRight}</b> of ${d.right} right lines${nWrong ? ` and <b class="fail">${nWrong}</b> line${nWrong === 1 ? "" : "s"} of another function` : ""}`
            : `Shown <b>${d.named.filter((l) => shownFor[c](l)).length}</b> of ${d.named.length} lines`}</p>
        ${lt && !lt.done ? `<div class="track"><i style="width:${Math.min(100, (100 * (lt.passed || 0)) / (lt.baseline || d.baseline))}%"></i></div><p class="lane-cap">${fmt(lt.passed || 0)} tests passed so far</p>` : ""}
        ${verdict ? `<p class="v2"><span class="verdict ${verdict.pass ? "pass" : "fail"}">${verdict.pass ? "Pass" : "Fail"}</span><span class="lane-cap">${fmt(verdict.passed)} of ${fmt(d.baseline)} tests pass${verdict.recorded ? " · recorded run" : " · just now"}</span></p>` : ""}
      </div>`;
    }).join("");
    view.querySelector("#lanes").innerHTML = lanes;
    const btn = view.querySelector("#run-agent");
    btn.disabled = AI.busy || !aiReady();
    btn.textContent = live.running ? (live.running === "edit" ? "Asking the agent…" : "Running the tests…") : `Run ${AI_NAME[AI.model]} now, with all three contexts`;
    view.querySelector("#agent-note").innerHTML = live.error ? `<p class="run-err">${esc(live.error)}</p>` : !aiReady() ? `<p class="fine">${esc(aiWhy())}</p>`
      : `<p class="fine">Three requests to ${esc(AI_NAME[AI.model])}, then three runs of click's tests, one per context: about 30 seconds.</p>`;
  };
  view.innerHTML = `
  <div class="study">
    <p class="crumb"><a href="#/study2">Study 2</a> / ${esc(d.repo)}</p>
    <h1>Rename <code>${esc(d.qualname)}</code> to <code>${esc(d.new_name)}</code></h1>
    <p class="lede"><b>${d.named.length}</b> lines in ${esc(d.repo)} contain <code>${esc(d.name)}</code>. The test run saw only <b>${d.right}</b> of them call <code>${esc(d.qualname)}</code>; the rest belong to ${d.namesakes.map((n) => `<code>${esc(n)}</code>`).join(", ")}. Each square below is one of those lines.</p>
    <div class="legend sq-key"><span><i class="sq shown-right"></i>calls this function</span><span><i class="sq shown"></i>another function's line, shown</span><span><i class="sq unshown"></i>not shown</span><span><i class="sq done"></i>renamed, rightly</span><span><i class="sq wrongedit"></i>renamed, wrongly</span><span><i class="sq missed"></i>missed</span></div>
    <div class="lanes-wrap"><div class="lanes2" id="lanes"></div><div class="tip sq-tip" role="status" hidden></div></div>
    <div class="ask"><button class="run" id="run-agent" type="button"></button><div id="agent-note"></div></div>
    <details class="code-reveal"><summary>Show the code</summary>
      <ul class="named">${d.named.map((l) => `<li class="${l.right ? "right" : ""}"><span class="at">${esc(l.path.split("/").pop())}:${l.n}</span><span class="in">${esc(l.in)}</span><code>${markName(l.text, d.name)}</code></li>`).join("")}</ul>
    </details>
  </div>`;
  paint();
  const wrap = view.querySelector(".lanes-wrap"), tip = wrap.querySelector(".sq-tip");
  const showTip = (e) => {
    const sq = e.target.closest?.(".sq[data-tip]");
    if (!sq) return;
    const box = wrap.getBoundingClientRect(), r = sq.getBoundingClientRect();
    tip.textContent = sq.dataset.tip;
    tip.style.left = `${Math.min(box.width - 260, Math.max(0, r.left - box.left - 120))}px`;
    tip.style.top = `${r.top - box.top - 6}px`;
    tip.hidden = false;
  };
  const hideTip = (e) => { if (e.target.closest?.(".sq")) tip.hidden = true; };
  wrap.addEventListener("mouseover", showTip);
  wrap.addEventListener("focusin", showTip);
  wrap.addEventListener("mouseout", hideTip);
  wrap.addEventListener("focusout", hideTip);
  view.querySelector("#run-agent").addEventListener("click", async () => {
    if (AI.busy || !aiReady()) return;
    AI.busy = true;
    Object.assign(live, { edits: {}, tests: {}, error: null, running: "edit" });
    paint();
    try {
      await sse({ stage: "agent", id: d.id, editor: AI.model }, (e) => {
        if (e.type === "asking") live.asking = e.arm;
        if (e.type === "edits") { live.edits[e.arm] = e; live.asking = null; }
        paint();
      });
      live.running = "test";
      paint();
      let last = 0;
      await sse({ stage: "test", id: d.id }, (e) => {
        const t = (live.tests[e.arm] ||= { passed: 0, baseline: d.baseline });
        if (e.type === "progress") Object.assign(t, { passed: e.passed });
        if (e.type === "verdict") Object.assign(t, e, { done: true });
        const now = performance.now();
        if (e.type !== "progress" || now - last > 150) { last = now; paint(); }
      });
    } catch (err) {
      live.error = err.message;
      live.asking = null;
    } finally {
      AI.busy = false;
      live.running = null;
      paint();
    }
  });
  document.addEventListener("ai-model", paint, { once: true });
}

// ---------------------------------------------------------------- method
async function renderMethod2() {
  const truth = await cached("/api/truth");
  const s1 = await cached("/api/study1");
  const click = truth.find((t) => t.repo === "click") || truth[0];
  const live = { state: null, tests: 0, total: 0, calls: 0, sites: 0, done: null, error: null };
  const paint = () => {
    const el = view.querySelector("#truth-live");
    el.innerHTML = live.error ? `<p class="run-err">${esc(live.error)}</p>`
      : live.state ? `<div class="counts"><span><b>${fmt(live.tests)}</b> of ${fmt(live.total || click.tests)} tests run</span><span><b>${fmt(live.calls)}</b> calls into click</span><span><b>${fmt(live.sites)}</b> distinct calling lines, tests included</span></div>
         <div class="track"><i style="width:${live.total ? (100 * live.tests) / live.total : 0}%"></i></div>
         ${live.done ? `<p class="say-sm">Recorded <b>${fmt(live.done.pairs)}</b> caller-to-callee paths in ${live.done.seconds} s; <b>${fmt(live.done.same_as_saved)}</b> of the ${fmt(live.done.saved)} saved ones again. PyCG and Pyright hold ${fmt(live.done.static["PyCG ∪ Pyright"])} of them.</p>` : ""}`
        : "";
    view.querySelector("#truth-run").disabled = AI.busy;
  };
  view.innerHTML = `
  <div class="study method2">
    <header class="study-head">
      <h1>Method</h1>
      <p class="lede">Nothing in this demo is labelled by hand or by a model. The ground truth is what the program did while its own tests ran.</p>
    </header>
    <figure class="pipe">
      <figcaption>Figure 4. From a test run to two studies</figcaption>
      <div class="pipe-flow">
        <div class="pbox"><small>click's own test suite</small><b>${fmt(click.tests)}</b><small>tests pass</small></div>
        <div class="parrow" aria-hidden="true"></div>
        <div class="pbox"><small>a tracer on every call (Python 3.12 sys.monitoring)</small><b>${fmt(click.calls)}</b><small>calls, from ${fmt(click.sites)} call sites</small></div>
        <div class="parrow" aria-hidden="true"></div>
        <div class="pbox truth"><small>ground truth</small><b>${fmt(click.pairs)}</b><small>caller-to-callee paths; ${fmt(click.lines)} lines ran</small></div>
        <div class="parrow split2" aria-hidden="true"></div>
        <div class="pstack"><a class="pbox" href="#/study1"><small>Study 1</small><b>${fmt(s1.all.items)}</b><small>items: who can find the calls</small></a><a class="pbox" href="#/study2"><small>Study 2</small><b>9</b><small>renames a regex breaks</small></a></div>
      </div>
      <div class="ask"><button class="run" id="truth-run" type="button">Record the truth again, now</button><p class="fine">Runs click's whole suite with the tracer on this laptop: about 6 seconds.</p></div>
      <div id="truth-live" aria-live="polite"></div>
    </figure>
    <div class="method-cols">
      <section>
        <h2>Study 1: the items</h2>
        <p>An item is a function and a project function named in a line of it that ran: as a call, as a name without a call (a property read or a value handed on), or as a class name (a constructor runs that class's <code>__init__</code>). The label is whether the test run recorded that call. The function's own signature and docstring do not count. ${fmt(s1.all.unnamed)} real calls name no target at all and are reported apart.</p>
        <h2>The AI models</h2>
        <p>gpt-oss-20b, gpt-oss-120b and qwen3.8-27b on Groq, temperature 0, low reasoning effort. Each sees the function's lines, numbered; each candidate's definition with its decorators; and the classes involved. It must answer with candidate ids, which the response schema enforces.</p>
        <h2>The learned combiner</h2>
        <p>A logistic regression on ten features: what PyCG, Pyright and each AI model say; how the name is written; whether it is shared; whether the candidate is a method of the caller's class. Trained and scored with 5-fold cross-validation grouped by function, so no function is scored by a model that saw it.</p>
      </section>
      <section>
        <h2>Study 2: the tasks</h2>
        <p>Every function whose name another function shares, that package code really calls and the tests do not call directly. A task is kept only if renaming exactly the lines the test run saw passes the tests, a regex rename fails, and renaming the definition alone fails.</p>
        <h2>Limits</h2>
        <ul>
          <li><b>Two projects.</b> click and toolz, pinned to one commit each.</li>
          <li><b>A sample for the AI models.</b> Free-tier limits; the sampling rule and seed are fixed and saved with the results.</li>
          <li><b>The tests decide what counts.</b> A call no test makes is not in the truth, for any resolver.</li>
          <li><b>Built on this laptop.</b> The static graphs are rebuilt on the Linux machine before anything is published.</li>
        </ul>
        <h2>Earlier pilot</h2>
        <p>A first study renamed functions with unique names, where a regex would also work. <a href="#/pilot">Its live walkthrough</a>, <a href="#/pilot-results">results</a> and <a href="#/pilot-method">method</a> are kept as they were.</p>
      </section>
    </div>
  </div>`;
  view.querySelector("#truth-run").addEventListener("click", async () => {
    if (AI.busy) return;
    AI.busy = true;
    Object.assign(live, { state: "running", tests: 0, total: 0, calls: 0, sites: 0, done: null, error: null });
    paint();
    let last = 0;
    try {
      await sse({ stage: "truth", repo: "click" }, (e) => {
        if (e.type === "collected") live.total = e.total;
        if (e.type === "progress") Object.assign(live, { tests: e.passed + e.failed + e.errors + e.skipped, calls: e.calls, sites: e.sites });
        if (e.type === "done") live.done = e;
        const now = performance.now();
        if (e.type !== "progress" || now - last > 100) { last = now; paint(); }
      });
    } catch (err) {
      live.error = err.message;
    } finally {
      AI.busy = false;
      paint();
    }
  });
}
