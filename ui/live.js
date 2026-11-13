"use strict";
// The live demo, told as one story: a function is used in N places; each run
// shows the editor some of them; the editor renames what it sees; the tests
// judge. Every number comes from a real process the server runs (/api/live,
// server-sent events). Code stays behind "Show the code".

const LIVE = {
  editor: "oracle", editors: [], report: null,
  results: {},   // editor -> task id -> { static: verdict, fused: verdict }
  b: null,       // the task on stage and its steps
  busy: false, all: false, stop: false,
};
const LANE = { static: "Static analysis only", fused: "Static analysis + test run" };
const STEPS = ["Read the code", "Run the tests", "Rename", "Check with the tests"];

// Session storage: a reload keeps this tab's runs; a new tab on demo day starts clean.
try { LIVE.results = JSON.parse(sessionStorage.getItem("tw-live") || "{}"); } catch { LIVE.results = {}; }
const save = () => { try { sessionStorage.setItem("tw-live", JSON.stringify(LIVE.results)); } catch { /* private mode */ } };
const liveOf = (id) => (LIVE.results[LIVE.editor] || {})[id];
const short = (q) => q.split(".").pop();
const isLLM = () => LIVE.editor !== "oracle";
const edName = () => (LIVE.editors.find((e) => e.id === LIVE.editor) || { name: "Rename script" }).name;
const fetchedRepo = (name) => LIVE.report.repos.find((r) => r.name === name)?.fetched !== false;
const places = (n) => `${n} place${n === 1 ? "" : "s"}`;
const code = (s) => `<code>${esc(s)}</code>`;

const chance = (p) => (p < 0.01 ? "under 1 in 100" : p < 0.5 ? `about 1 in ${Math.round(1 / p)}` : "high: the two runs agree");

function signTest(b, c) {
  const n = b + c;
  if (!n) return 1;
  let comb = 1, tail = 1;
  for (let k = 1; k <= Math.min(b, c); k++) { comb = comb * (n - k + 1) / k; tail += comb; }
  return Math.min(1, 2 * tail / 2 ** n);
}

function stream(stage, id, onEvent) {
  return new Promise((resolve, reject) => {
    const q = new URLSearchParams({ stage, id });
    if (stage === "edit") q.set("editor", LIVE.editor);
    const es = new EventSource(`/api/live?${q}`);
    let failure = null;
    es.onmessage = (m) => {
      const e = JSON.parse(m.data);
      if (e.type === "error") failure = e.message; else onEvent(e);
    };
    es.addEventListener("end", () => { es.close(); failure ? reject(new Error(failure)) : resolve(); });
    es.onerror = () => { es.close(); reject(new Error(failure || "The connection to tw.py ui dropped. Check that it is still running.")); };
  });
}

// The tasks where running the tests finds callers that reading the code misses.
function tasks() {
  return LIVE.report.tasks.filter((t) => t.group === "treatment" && fetchedRepo(t.repo))
    .sort((a, b) => (b.fused?.pass && !b.static?.pass) - (a.fused?.pass && !a.static?.pass) || a.qualname.localeCompare(b.qualname));
}

// ---------- page ----------
async function renderLive(r) {
  LIVE.report = r;
  if (!LIVE.editors.length) {
    LIVE.editors = await api("/api/editors");
    editorSwitch(r, "live");
  }
  view.innerHTML = `
  <div class="story">
    <header class="story-head">
      <h1>Does watching a program run help an editor change it safely?</h1>
      <p class="lede">We ask an editor to rename one function everywhere in a real project. It can only change the code we show it. We find that code in two ways: by reading the code without running it (static analysis), and by also watching the project's tests run. Then those tests decide whether the rename worked.</p>
    </header>
    <section class="score" aria-label="Results for every task">
      <div class="score-rows" id="score"></div>
      <div class="score-foot">
        <p class="fine" id="score-note"></p>
        <button class="ghost" id="stop" type="button" hidden>Stop after this task</button>
        <button class="ghost" id="run-all" type="button"></button>
      </div>
    </section>
    <section class="task" id="task" aria-label="One task, step by step"></section>
  </div>`;
  document.getElementById("run-all").addEventListener("click", runAll);
  document.getElementById("stop").addEventListener("click", () => { LIVE.stop = true; paintScore(); });
  document.getElementById("score").addEventListener("click", (e) => {
    const dot = e.target.closest("[data-task]");
    if (dot && !LIVE.busy) select(dot.dataset.task);
  });
  document.getElementById("task").addEventListener("click", taskClick);
  document.getElementById("task").addEventListener("change", (e) => {
    if (e.target.id === "chooser" && !LIVE.busy) select(e.target.value);
  });
  paintScore();
  const first = LIVE.b && tasks().some((t) => t.id === LIVE.b.id) ? LIVE.b.id
    : (tasks().find((t) => t.id === "click:Context.command_path") || tasks()[0])?.id;
  if (first) select(first, { keep: LIVE.b?.id === first });
}

function setLiveEditor(id) {
  if (LIVE.busy || id === LIVE.editor) return;
  LIVE.editor = id;
  const b = LIVE.b;
  if (b && b.step > 2) Object.assign(b, { step: 2, edit: { static: null, fused: null }, test: { static: null, fused: null } });
  paintAll();
}

// ---------- the scoreboard: one square per task, per run ----------
function paintScore() {
  const el = document.getElementById("score");
  if (!el) return;
  const list = tasks(), n = list.length;
  const result = (t, arm) => liveOf(t.id)?.[arm] || (isLLM() ? null : t[arm]);
  el.innerHTML = ["static", "fused"].map((arm) => {
    const pass = list.filter((t) => result(t, arm)?.pass).length;
    const dots = list.map((t, i) => {
      const r = result(t, arm), live = liveOf(t.id)?.[arm];
      const differs = live && !isLLM() && t[arm] && t[arm].pass !== live.pass;
      return `<button type="button" class="dot ${r ? (r.pass ? "p" : "x") : "none"}${live ? " ran" : ""}${differs ? " differs" : ""}${LIVE.b?.id === t.id ? " on" : ""}" data-task="${esc(t.id)}" ${LIVE.busy ? "disabled" : ""}
        aria-label="Task ${i + 1}, ${esc(short(t.qualname))}: ${r ? (r.pass ? "worked" : "failed") : "not run yet"}${live ? ", run live" : ""}" title="${i + 1}. ${esc(short(t.qualname))}"></button>`;
    }).join("");
    return `<div class="score-row"><span class="lane-name ${arm}">${LANE[arm]}</span><div class="dots">${dots}</div>
      <span class="score-n"><b class="${arm}-c">${pass}</b> of ${n} renames worked</span></div>`;
  }).join("");

  const liveCount = list.filter((t) => liveOf(t.id)).length;
  const differ = list.filter((t) => !isLLM() && ["static", "fused"].some((a) => liveOf(t.id)?.[a] && t[a] && t[a].pass !== liveOf(t.id)[a].pass)).length;
  const b = list.filter((t) => t.fused?.pass && !t.static?.pass).length, c = list.filter((t) => t.static?.pass && !t.fused?.pass).length;
  document.getElementById("score-note").innerHTML = isLLM()
    ? `Each square is one task. ${esc(edName())} has no recorded run, so squares fill as you run tasks live${liveCount ? `: ${liveCount} of ${n} so far` : ""}.`
    : `Each square is one task, filled from our recorded run. The chance of a gap this large by luck alone is ${chance(signTest(b, c))}. ${liveCount ? `A ring marks the ${liveCount} run live today${differ ? `; ${differ} came out differently` : ", all matching"}.` : "Click a square to run that task live."}`;
  const btn = document.getElementById("run-all");
  btn.textContent = LIVE.all ? `Running task ${list.findIndex((t) => t.id === LIVE.b?.id) + 1} of ${n}…` : `Run all ${n} live${isLLM() ? " with the AI model" : ""}`;
  btn.disabled = LIVE.busy;
  const stop = document.getElementById("stop");
  stop.hidden = !LIVE.all;
  stop.disabled = LIVE.stop;
  stop.textContent = LIVE.stop ? "Stopping after this task" : "Stop after this task";
}

// ---------- one task, step by step ----------
async function select(id, { keep = false } = {}) {
  if (!id) return;
  if (!keep || !LIVE.b || LIVE.b.id !== id) {
    LIVE.b = { id, d: null, step: 0, running: null, error: null, fresh: new Set(),
      trace: null, edit: { static: null, fused: null }, test: { static: null, fused: null } };
  }
  paintScore();
  const el = document.getElementById("task");
  if (!LIVE.b.d) {
    el.dataset.task = "";
    el.innerHTML = `<p class="loading">Loading the task…</p>`;
    try {
      LIVE.b.d = await api(withModel(`/api/task?id=${encodeURIComponent(id)}`));
    } catch (err) {
      el.innerHTML = `<p class="notice">This task could not load (${esc(err.message)}).</p>`;
      return;
    }
  }
  if (LIVE.b.id === id) paintTask();
}

function taskClick(e) {
  const go = e.target.closest("[data-go]");
  if (go) {
    LIVE.b.driving = true;
    return go.dataset.go === "all" ? playAll() : advance();
  }
  const next = e.target.closest("[data-next-task]");
  if (next && !LIVE.busy) select(next.dataset.nextTask);
}

async function advance() {
  const b = LIVE.b;
  if (!b || LIVE.busy) return false;
  if (b.step === 0) {
    b.step = 1;
    b.fresh = new Set(b.d.graph.static.map((c) => c.key));
    paintTask();
    // From here on the task is the subject: bring its steps and both runs into one screen.
    document.getElementById("task").scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });
    return true;
  }
  const stage = { 1: "trace", 2: "edit", 3: "test" }[b.step];
  if (!stage) return false;
  const step = b.step;
  b.error = null;
  try {
    await runStage(b, stage);
    if (LIVE.b !== b) return false;
    b.step = step + 1;
    return true;
  } catch (err) {
    b.error = err.message;
    return false;
  } finally {
    paintAll();
  }
}

async function playAll() {
  while (LIVE.b && LIVE.b.step < 4 && await advance()) { /* each step waits for the one before */ }
}

function paintAll() { paintScore(); if (LIVE.b?.d) paintTask(); }

async function runStage(b, stage) {
  LIVE.busy = true;
  b.running = stage;
  if (stage === "trace") b.trace = { total: 0, done: 0, found: [], latest: null, summary: null };
  if (stage === "edit") b.edit = { static: null, fused: null };
  if (stage === "test") b.test = { static: null, fused: null };
  let last = 0;
  const tick = (force) => {   // progress arrives every 50 ms; repaint at most every 120 ms
    const now = performance.now();
    if (force || now - last > 120) { last = now; paintTask(); }
  };
  try {
    paintAll();
    if (stage === "trace") {
      await stream("trace", b.id, (e) => {
        const tr = b.trace;
        if (e.type === "collected") tr.total = e.total;
        else if (e.type === "progress") tr.done = e.passed + e.failed + e.errors + e.skipped;
        else if (e.type === "caller") { tr.found.push(e); tr.latest = e; b.fresh.add(e.key); return tick(true); }
        else if (e.type === "done") tr.summary = e;
        tick();
      });
    } else if (stage === "edit") {
      await stream("edit", b.id, (e) => {
        if (e.type === "asking") b.edit[e.arm] = { asking: true, t0: performance.now(), ...e };
        else if (e.type === "edits") b.edit[e.arm] = { ...b.edit[e.arm], ...e, asking: false };
        tick(true);
      });
    } else {
      await stream("test", b.id, (e) => {
        if (e.type === "start") b.test[e.arm] = { total: 0, passed: 0, failed: 0, errors: 0, skipped: 0, baseline: e.baseline };
        else if (e.type === "collected") b.test[e.arm].total = e.total;
        else if (e.type === "progress") Object.assign(b.test[e.arm], { passed: e.passed, failed: e.failed, errors: e.errors, skipped: e.skipped });
        else if (e.type === "verdict") { b.test[e.arm] = { ...b.test[e.arm], ...e, done: true }; return tick(true); }
        tick();
      });
      (LIVE.results[LIVE.editor] ||= {})[b.id] = { static: keepVerdict(b.test.static), fused: keepVerdict(b.test.fused) };
      save();
    }
  } finally {
    b.running = null;
    LIVE.busy = LIVE.all;
  }
}
const keepVerdict = (v) => ({ pass: v.pass, passed: v.passed, failed: v.failed, at: Date.now() });

async function runAll() {
  if (LIVE.busy) return;
  LIVE.all = LIVE.busy = true;
  LIVE.stop = false;
  paintAll();
  try {
    for (const t of tasks()) {
      if (LIVE.stop) break;
      await select(t.id);
      const b = LIVE.b;
      Object.assign(b, { step: 2, skippedTrace: true, fresh: new Set(b.d.graph.static.map((c) => c.key)) });
      await runStage(b, "edit");
      b.step = 3;
      await runStage(b, "test");
      b.step = 4;
      paintAll();
    }
  } catch (err) {
    if (LIVE.b) LIVE.b.error = err.message;
  } finally {
    LIVE.all = LIVE.busy = LIVE.stop = false;
    paintAll();
  }
}

// ---------- the task, drawn ----------
function paintTask() {
  const b = LIVE.b, d = b?.d, el = document.getElementById("task");
  if (!el || !d) return;
  if (el.dataset.task !== b.id) {
    el.dataset.task = b.id;
    el.innerHTML = ["head", "steps", "say", "err", "stage", "code"].map((p) => `<div class="part-${p}" data-part="${p}"></div>`).join("");
  }
  part(el, "head", taskHead(d));
  part(el, "err", b.error ? `<p class="run-err">The run stopped. ${esc(b.error)}</p>` : "");
  if (!d.fetched) {
    part(el, "say", `<p class="notice">The code for ${esc(d.repo)} is not on this computer. Run <code>${esc(d.fetch_command)}</code>, then reload.</p>`);
    return;
  }
  const steps = part(el, "steps", stepper(b));
  // Whoever drives the steps keeps their place: the rebuilt Next button takes focus back.
  if (b.driving && !steps.contains(document.activeElement)) steps.querySelector('[data-go="next"]:not(:disabled), [data-next-task]')?.focus({ preventScroll: true });
  part(el, "say", `<p class="say" aria-live="polite" aria-busy="${!!b.running}">${narrate(b)}</p>`);
  const stage = part(el, "stage", `<div class="who">${graphSVG(b)}</div><div class="lanes"><p class="fine">Each square is one line where ${code(d.name)} is written; the first is the function's own definition.</p>${lane(b, "static")}${lane(b, "fused")}</div>`);
  for (const k of b.fresh) stage.querySelector(`[data-key="${CSS.escape(k)}"]`)?.classList.add("fresh");
  b.fresh.clear();
  part(el, "code", codeReveal(b));
}

function part(el, name, html) {
  const x = el.querySelector(`[data-part="${name}"]`);
  if (x._html !== html) {
    const open = x.querySelector("details")?.open;   // keep "Show the code" open across repaints
    x.innerHTML = html;
    x._html = html;
    if (open && x.querySelector("details")) x.querySelector("details").open = true;
  }
  return x;
}

function taskHead(d) {
  const list = tasks();
  return `<div class="task-line">
      <h2>Rename ${code(d.name)} to ${code(d.new_name)}</h2>
      <label class="chooser">Task <select id="chooser" ${LIVE.busy ? "disabled" : ""}>${list.map((t, i) => `<option value="${esc(t.id)}" ${t.id === d.id ? "selected" : ""}>${i + 1}. ${esc(short(t.qualname))}, in the ${esc(t.repo)} project</option>`).join("")}</select></label>
    </div>
    <p class="task-sub">In the ${esc(d.repo)} project, ${esc(d.about || "a Python project")}${d.baseline ? `, checked by its ${fmt(d.baseline.passed)} tests` : ""}. The name ${code(d.name)} appears in <b>${places(d.refs_total)}</b> in the code, and every one has to change.</p>`;
}

function stepper(b) {
  const label = ["Start", "Next: run the tests", `Next: ${isLLM() ? "ask the AI model to rename" : "rename"}`, "Next: check with the tests"][b.step];
  const busy = LIVE.busy ? "disabled" : "";
  const action = b.step >= 4 ? nextTaskButton(b)
    : `<button class="ghost" type="button" data-go="all" ${busy}>Play all steps</button><button class="run" type="button" data-go="next" ${busy}>${b.running ? "Running…" : label}</button>`;
  return `<div class="stepper"><ol>${STEPS.map((s, i) => {
    const n = i + 1, state = b.running && b.step === i ? "now" : b.step >= n ? "done" : "todo";
    const skipped = n === 2 && b.skippedTrace;
    const current = b.running ? b.step === i : b.step === n;
    return `<li class="${state}"${current ? ` aria-current="step"` : ""}><span class="n">${n}</span>${s}${skipped ? " <small>(recorded)</small>" : ""}</li>`;
  }).join("")}</ol><div class="actions">${action}</div></div>`;
}

function nextTaskButton(b) {
  if (LIVE.all) return "";
  const list = tasks(), nxt = list[list.findIndex((t) => t.id === b.id) + 1];
  return nxt ? `<button class="ghost" type="button" data-next-task="${esc(nxt.id)}">Next task: ${esc(short(nxt.qualname))}</button>` : "";
}

// One sentence for the step on screen: what is happening, in plain words.
function narrate(b) {
  const d = b.d, name = code(d.name), N = d.refs_total;
  const S = d.graph.static.length, sStatic = d.arms.static.refs_shown, sFused = d.arms.fused.refs_shown;
  if (b.step === 0) return `Press Start to see how one task runs, one step at a time.`;
  if (b.step === 1 && !b.running) {
    return `Static analysis reads the code without running it. ${S
      ? `It found ${S} function${S === 1 ? "" : "s"} that use${S === 1 ? "s" : ""} ${name}, so the editor sees the definition and those uses: <b>${sStatic} of the ${N}</b> places.`
      : `It found nothing that uses ${name}, so the editor sees only the function's own definition: <b>${sStatic} of the ${N}</b> places.`}`;
  }
  if (b.running === "trace") {
    const tr = b.trace;
    const now = tr.latest ? ` Just found: <b>${esc(short(tr.latest.qualname))}</b> uses it.` : "";
    return tr.total ? `Running all ${fmt(tr.total)} of ${esc(d.repo)}'s tests and noting every function that calls ${name}: ${fmt(tr.done)} run so far.${now}`
      : `Starting ${esc(d.repo)}'s tests…`;
  }
  if (b.step === 2 && !b.running) {
    const extra = b.skippedTrace ? d.graph.hidden.length : (b.trace?.found || []).filter((c) => c.kind !== "static").length;
    return `${b.skippedTrace ? "The recorded test run" : "The tests"} found ${extra} more function${extra === 1 ? "" : "s"} using ${name} that static analysis missed. With them, the editor is shown <b>${sFused} of the ${N}</b> places.`;
  }
  if (b.running === "edit") {
    return isLLM() ? `Asking ${esc(edName())}, an AI model, to do the rename twice: once with each set of places.`
      : `The rename script changes ${name} in every place it is shown. It never gets a shown place wrong, so anything it misses was never shown.`;
  }
  if (b.step === 3 && !b.running) {
    const [s, f] = ["static", "fused"].map((a) => renamed(b, a));
    return `${LANE.static}: ${s} of ${N} renamed. ${LANE.fused}: ${f} of ${N} renamed.${s < N || f < N ? ` Wherever the old name is left behind, the code still calls a function that no longer exists.` : ""}`;
  }
  if (b.running === "test") return `Running all of ${esc(d.repo)}'s tests on each edited copy, one after the other.`;
  if (b.step >= 4) {
    const s = b.test.static, f = b.test.fused;
    if (!s?.done || !f?.done) return "";
    const why = (t) => (t.pass ? "every test still passes" : `${fmt(t.failed + t.errors)} tests fail`);
    return `${LANE.static}: ${why(s)}. ${LANE.fused}: ${why(f)}.${!s.pass && f.pass ? ` Watching the tests run found the places that reading the code missed.` : ""}`;
  }
  return "";
}

// The function's own definition first, then every other line that names it.
const refsInOrder = (d) => [...d.refs].sort((a, b) => (b.path === d.path && b.n === d.line) - (a.path === d.path && a.n === d.line));

function renamed(b, arm) {
  const lines = b.edit[arm]?.lines || [];
  return b.d.refs.filter((r) => lines.some((l) => l.path === r.path && l.line === r.n && l.after.includes(b.d.new_name))).length;
}

function lane(b, arm) {
  const d = b.d, N = d.refs_total;
  const known = arm === "static" ? b.step >= 1 : b.step >= 2;
  const unseen = new Set(d.arms[arm].unseen.map((u) => `${u.path}:${u.n}`));
  const e = b.edit[arm], edited = e && !e.asking;
  const lines = e?.lines || [];
  const boxes = refsInOrder(d).map((r) => {
    const shown = !unseen.has(`${r.path}:${r.n}`);
    const done = edited && lines.some((l) => l.path === r.path && l.line === r.n && l.after.includes(d.new_name));
    const state = !known ? "unknown" : edited ? (done ? "done" : shown ? "skipped" : "missed") : shown ? "shown" : "hidden";
    const tip = !known ? "" : edited ? (done ? "renamed" : shown ? "shown, but not renamed" : "never shown, so still the old name") : shown ? "shown to the editor" : "not shown to the editor";
    return `<span class="place ${state}" title="${esc(`${r.path.split("/").pop()}:${r.n}  ${r.text}`)}${tip ? ` (${tip})` : ""}"></span>`;
  }).join("");
  const shownN = N - unseen.size, doneN = edited ? renamed(b, arm) : 0;
  const caption = !known ? (arm === "fused" ? "Waiting for the test run" : "")
    : e?.asking ? (isLLM() ? `${esc(edName())} is thinking… ${((performance.now() - e.t0) / 1000).toFixed(0)} s` : "Renaming…")
      : edited ? (doneN === N ? `All ${N} renamed` : `<b>${doneN}</b> renamed · <b class="fail">${N - doneN}</b> still the old name`)
        : `<b>${shownN}</b> of ${N} places shown to the editor`;
  return `<div class="lane ${arm}">
    <h3 class="lane-name ${arm}">${LANE[arm]}</h3>
    <div class="places" role="img" aria-label="${esc(caption.replace(/<[^>]+>/g, ""))}">${boxes}</div>
    <p class="lane-cap">${caption}</p>
    ${testRow(b, arm)}
  </div>`;
}

function testRow(b, arm) {
  const t = b.test[arm];
  if (!t) return b.running === "test" ? `<p class="lane-cap">Waits for the other run; both use the same copy of the code.</p>` : "";
  const total = t.baseline || t.total || 1;
  const pw = Math.min(100, (100 * t.passed) / total), fw = Math.min(100 - pw, (100 * (t.failed + t.errors)) / total);
  const broke = t.syntax_error || (t.done && t.rc !== 0 && t.rc !== 1);
  return `<div class="test-row">
    <div class="track" role="progressbar" aria-valuemin="0" aria-valuemax="${total}" aria-valuenow="${t.passed}" aria-label="Tests passing"><i style="width:${pw}%"></i><i class="bad" style="width:${fw}%"></i></div>
    <p class="lane-cap"><b>${fmt(t.passed)}</b> of ${fmt(t.baseline)} tests pass${t.done ? "" : "…"}</p>
    ${t.done ? `<span class="verdict ${t.pass ? "pass" : "fail"}">${t.pass ? "Pass" : "Fail"}</span>` : ""}
    ${broke ? `<p class="run-err">The edit broke the file, so the tests could not start.</p>` : ""}
  </div>`;
}

function graphSVG(b) {
  const g = b.d.graph, W = 440;
  const found = new Map((b.trace?.found || []).map((c) => [c.key, c]));
  const showHidden = b.skippedTrace && b.step >= 2;
  const slots = [
    ...g.static.map((c) => ({ ...c, kind: "static", on: b.step >= 1 })),
    ...g.hidden.map((c) => ({ ...c, kind: "hidden", on: found.has(c.key) || showHidden })),
    ...[...found.values()].filter((c) => c.kind === "new").map((c) => ({ ...c, kind: "new", on: true })),
  ];
  const shown = slots.slice(0, 6), more = slots.length - shown.length;
  const n = Math.max(shown.length, 1), gap = 34, H = Math.max(120, n * gap + 20);
  const name = b.d.name, boxW = Math.max(110, name.length * 7.8 + 24);
  const xt = W - boxW - 2, yc = H / 2, x0 = 196;
  const lines = shown.map((c, i) => {
    if (!c.on) return "";
    const y = 10 + gap / 2 + i * gap + (H - 20 - n * gap) / 2;
    const ye = yc + (n > 1 ? (i - (n - 1) / 2) * Math.min(7, 26 / (n - 1)) : 0);
    const dy = Math.abs(ye - y), bend = xt - 18;
    return `<g class="edge ${c.kind === "static" ? "static" : "hidden"}" data-key="${esc(c.key)}">
      <path d="M${x0} ${y} H${bend - dy} L${bend} ${ye} H${xt}" pathLength="1"/>
      <circle cx="${x0}" cy="${y}" r="5.5"/>
      <text x="${x0 - 11}" y="${y + 4}" text-anchor="end" class="who-name">${esc(c.key === b.d.graph.target ? `${short(c.qualname)} (itself)` : short(c.qualname))}</text></g>`;
  }).join("");
  const note = b.step === 0 ? "who uses it appears here"
    : !slots.some((s) => s.on) ? (b.running === "trace" ? "watching the tests…" : "reading the code found none") : "";
  const tr = b.trace, pct = tr?.total ? Math.min(100, (100 * tr.done) / tr.total) : 0;
  return `<p class="who-title">Functions that use ${code(name)}</p>
  <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Functions that use ${esc(name)}: ${slots.filter((s) => s.on).map((s) => short(s.qualname)).join(", ") || "none shown yet"}">
    ${lines}${note ? `<text x="${x0 - 11}" y="${yc + 4}" text-anchor="end" class="none-found">${note}</text>` : ""}
    <rect x="${xt}" y="${yc - 18}" width="${boxW}" height="36" class="target"/>
    <text x="${xt + boxW / 2}" y="${yc + 5}" text-anchor="middle" class="target-name">${esc(name)}</text>
    ${more > 0 ? `<text x="${x0 - 11}" y="${H - 2}" text-anchor="end" class="none-found">and ${more} more</text>` : ""}
  </svg>
  ${b.running === "trace" ? `<div class="track" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${Math.round(pct)}" aria-label="Tests run"><i style="width:${pct}%"></i></div>` : ""}
  <p class="graph-key"><span><i class="k-static"></i>found by static analysis</span><span><i class="k-hidden"></i>found only by the test run</span></p>`;
}

function codeReveal(b) {
  const d = b.d;
  const col = (arm) => {
    const e = b.edit[arm];
    const unseen = d.arms[arm].unseen;
    const diff = (e?.lines || []).map((l) => `<li><span class="at">${esc(l.path.split("/").pop())}:${l.line}</span><del>${esc(l.before.trim())}</del><ins>${esc(l.after.trim())}</ins></li>`).join("");
    return `<div class="code-col"><h4 class="lane-name ${arm}">${LANE[arm]}</h4>
      ${diff ? `<p class="fine">What the editor changed</p><ul class="diff">${diff}</ul>` : `<p class="fine">${b.step >= 3 ? "The editor changed nothing." : "The edits appear here after step 3."}</p>`}
      ${unseen.length ? `<p class="unseen-title">Never shown to the editor</p><ul class="unseen">${unseen.map((u) => `<li><span class="at">${esc(u.path.split("/").pop())}:${u.n}</span><span class="src">${markName(u.text, d.name)}</span></li>`).join("")}</ul>` : ""}
      ${e?.reasoning ? `<details class="prompt"><summary>What ${esc(edName())} wrote before answering</summary><pre>${esc(e.reasoning)}</pre></details>` : ""}
    </div>`;
  };
  return `<details class="code-reveal"><summary>Show the code</summary>
    <p class="fine">The function is <code>${esc(d.qualname)}</code> in <code>${esc(d.path)}:${d.line}</code>. The static callers come from PyCG and Pyright, run beforehand on the same commit. <a href="${taskHref(d.id)}">Full evidence for this task</a>.</p>
    <div class="code-cols">${col("static")}${col("fused")}</div>
    ${b.step >= 4 ? `<p class="witness">The same run from a terminal: <code>python3 tw.py show ${esc(d.id)} --live ${esc(LIVE.editor)}</code></p>` : ""}
  </details>`;
}

// The LLM's thinking time ticks between server events.
setInterval(() => {
  if (LIVE.b?.running === "edit" && isLLM()) paintTask();
}, 500);
