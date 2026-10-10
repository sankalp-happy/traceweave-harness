"use strict";

const view = document.getElementById("view");
const state = { report: null, tasks: { group: "all", repo: "all", outcome: "any", q: "", sort: "group", dir: 1 } };

// ---------- helpers ----------
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = (n) => Number(n).toLocaleString("en-GB");
const pval = (p) => (p >= 0.9995 ? "1" : p < 0.001 ? "<0.001" : String(Number(p.toPrecision(2))));
const day = (ts) => new Date(ts).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
const clock = (ts, utc = true) => new Date(ts).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", ...(utc && { timeZone: "UTC" }) });
const taskHref = (id) => `#/task/${encodeURIComponent(id)}`;
const ran = (a) => a && (a.rc === 0 || a.rc === 1);

async function api(path, opts) {
  const res = await fetch(path, opts);
  const body = await res.json().catch(() => ({ error: `HTTP ${res.status}` }));
  if (!res.ok) throw new Error(body.error || `HTTP ${res.status}`);
  return body;
}

function verdict(a) {
  if (!a) return `<span class="muted">not run</span>`;
  return a.pass ? `<span class="v-pass">pass</span>` : `<span class="v-fail">fail</span>`;
}

function suiteLine(a) {
  if (!ran(a)) return `the suite did not run <span class="muted">(pytest exit ${a.rc})</span>`;
  return `<b>${fmt(a.passed)}</b> passed · <b>${fmt(a.failed)}</b> failed${a.errors ? ` · <b>${fmt(a.errors)}</b> errors` : ""}`;
}

const REASONS = {
  "name shared with another function (override family)": "override families",
  "dunder method": "dunder methods",
  "name appears in the test suite": "named in the test suite",
  "not a function or method (lambda)": "lambdas",
  "name under four characters": "names under four characters",
  "overload stub or numbered redefinition": "overload stubs",
  "no in-package caller ran under the suite": "never executed",
  "new name already in use": "new name taken",
};

// ---------- report ----------
function consort(r) {
  const a = r.attrition;
  const excluded = Object.entries(a).filter(([k]) => k !== "eligible" && k !== "dropped by validation").sort((x, y) => y[1] - x[1]);
  const exclTotal = excluded.reduce((s, [, n]) => s + n, 0);
  const eligible = a.eligible || 0;
  const dropped = a["dropped by validation"] || 0;
  const t = r.table.find((x) => x.repo === "pooled" && x.group === "treatment");
  if (!t) return `<p class="muted">No treatment results recorded yet.</p>`;
  const how = "#/method?focus=exclusions";
  return `
  <figure class="fig">
  <figcaption>Figure 1. Allocation of rename targets <span class="muted">(oracle editor: a ceiling; no LLM run yet)</span></figcaption>
  <div class="flow">
    <a class="box" href="${how}">Functions with a caller seen only at runtime<b>${fmt(eligible + exclTotal)}</b><span class="hint">how tasks were chosen</span></a>
    <div class="v"></div>
    <div class="row">
      <a class="box" href="${how}">Eligible rename tasks<b>${fmt(eligible)}</b></a>
      <div class="h" aria-hidden="true"></div>
      <a class="excl" href="${how}"><b>Excluded ${fmt(exclTotal)}</b><ul>${excluded.map(([k, n]) => `<li><span>${esc(REASONS[k] || k)}</span><span>${fmt(n)}</span></li>`).join("")}</ul><span class="hint">see each reason</span></a>
    </div>
    <div class="v"></div>
    <div class="row">
      <a class="box" href="#/tasks?group=treatment">Gradeable by the test suite<b>${fmt(t.tasks)}</b><span class="hint">open all ${t.tasks}</span></a>
      <div class="h" aria-hidden="true"></div>
      <a class="excl" href="${how}"><b>Dropped ${fmt(dropped)}</b><ul><li><span>suite could not tell a right rename from a wrong one</span></li></ul><span class="hint">see how tasks are validated</span></a>
    </div>
    <div class="v" aria-hidden="true"></div>
    <div class="split" aria-hidden="true"></div>
    <div class="arms">
      <a class="arm" href="#/tasks?group=treatment&outcome=static-pass"><span class="sc static-c">Static arm</span><b>${t.static}</b><span class="of">of ${t.tasks} pass</span><span class="hint">open these</span></a>
      <a class="arm" href="#/tasks?group=treatment&outcome=fused-pass"><span class="sc fused-c">Fused arm</span><b>${t.fused}</b><span class="of">of ${t.tasks} pass</span><span class="hint">open these</span></a>
    </div>
    <p class="paired">Paired: every task runs under both arms, edited by the oracle</p>
  </div>
  </figure>`;
}

function outcomesTable(r) {
  const order = ["treatment", "placebo"];
  const rows = [...r.table].sort((x, y) => order.indexOf(x.group) - order.indexOf(y.group)
    || (x.repo === "pooled") - (y.repo === "pooled") || x.repo.localeCompare(y.repo));
  const label = (x) => `${x.group === "treatment" ? "Treatment" : "Placebo"}, ${x.repo}`;
  return `<table>
    <caption>Table 1. Oracle outcomes by arm <span class="muted">(tasks passed)</span></caption>
    <thead><tr><th scope="col">Group</th><th scope="col">Tasks</th><th scope="col">Static arm</th><th scope="col">Fused arm</th><th scope="col">Fused only<sup>a</sup></th><th scope="col">Static only<sup>a</sup></th><th scope="col">Exact p<sup>b</sup></th></tr></thead>
    <tbody>${rows.map((x) => { const href = `#/tasks?group=${x.group}&repo=${x.repo === "pooled" ? "all" : encodeURIComponent(x.repo)}`;
      return `<tr class="go ${x.repo === "pooled" ? "pooled" : ""}" data-href="${href}"><td><a href="${href}">${label(x)}</a></td><td>${x.tasks}</td><td>${x.static}</td><td>${x.fused}</td><td>${x.fused_only}</td><td>${x.static_only}</td><td>${pval(x.p)}</td></tr>`; }).join("")}</tbody>
  </table>`;
}

function rosterRows(tasks) {
  return tasks.map((t) => `<tr class="go" data-href="${taskHref(t.id)}">
      <td class="t"><a href="${taskHref(t.id)}">${esc(t.qualname)}</a></td>
      <td class="l">${esc(t.repo)}</td>
      <td>${t.runtime_only}</td>
      <td class="seen">${t.static ? `${t.static.refs_shown} · <b>${t.fused.refs_shown}</b> / ${t.refs_total}` : "—"}</td>
      <td>${verdict(t.static)}</td><td>${verdict(t.fused)}</td></tr>`).join("");
}

function renderReport(r) {
  const treat = r.tasks.filter((t) => t.group === "treatment");
  const fusedFails = treat.filter((t) => t.fused && !t.fused.pass);
  const oneLine = fusedFails.filter((t) => t.refs_total - t.fused.refs_shown === 1).length;
  const placebo = r.table.find((x) => x.repo === "pooled" && x.group === "placebo");
  const p = r.provenance;
  view.innerHTML = `
  <div class="report">
    <section>
      <h1>Runtime call-graph context in repo-wide renames: a paired, placebo-controlled study</h1>
      <p class="lede">The same editor, prompt and token budget in both arms. The only difference is whether callers seen only while the test suite ran are in the context. The outcome is the project's own test suite.</p>
      ${consort(r)}
    </section>
    <section>
      <div class="scroll">${outcomesTable(r)}</div>
      <ol class="footnotes">
        <li><sup>a</sup> Tasks that pass in that arm only: the discordant pairs.</li>
        <li><sup>b</sup> Exact two-sided McNemar test on the discordant pairs.</li>
      </ol>
      <p class="table-note">These are ceilings: the oracle renames every line its context shows, so a failure means the context lacked a line, not that the editor erred. Placebo prompts are byte-identical across arms, so the arms must agree, and they do${placebo ? ` (${placebo.static} and ${placebo.fused} of ${placebo.tasks})` : ""}. ${fusedFails.length ? `Of the ${fusedFails.length} treatment tasks the fused arm still fails, ${oneLine === fusedFails.length ? "every one" : oneLine} misses exactly one line naming the function, where it is passed or stored as a value rather than called.` : ""}</p>
      <p class="witness">Source: <code>${esc(p.command)}</code> · ${fmt(p.rows)} recorded rows · ${p.first ? `${day(p.first)}, ${clock(p.first)}–${clock(p.last)} UTC` : "no runs recorded"}</p>
    </section>
  </div>
  <div class="below">
    <section>
      <div class="scroll"><table>
        <caption>Table 2. Treatment tasks <span class="muted">(lines naming the function seen: static · fused / total)</span></caption>
        <thead><tr><th scope="col">Task</th><th scope="col" class="l">Repo</th><th scope="col">Runtime-only callers</th><th scope="col">Lines seen</th><th scope="col">Static arm</th><th scope="col">Fused arm</th></tr></thead>
        <tbody>${rosterRows(sortTasks(treat, "fused-first"))}</tbody>
      </table></div>
    </section>
    <section>
      <h2>Placebo tasks</h2>
      <p class="muted">${placebo ? `${placebo.tasks} tasks whose callers are all visible to static analysis. Both arms receive the same prompt; ${placebo.tasks - placebo.static} fail in both, because a line naming the function is outside every call graph.` : "None recorded."} <a href="#/tasks?group=placebo">Open the placebo roster</a>.</p>
    </section>
  </div>`;
}

function sortTasks(tasks, key, dir = 1) {
  const score = (t) => (t.fused?.pass ? 2 : 0) + (t.static?.pass ? 1 : 0);
  const keys = {
    "fused-first": (t) => [-(t.fused?.pass && !t.static?.pass), -score(t), t.qualname],
    task: (t) => [t.qualname], repo: (t) => [t.repo, t.qualname], group: (t) => [t.group === "placebo", t.qualname],
    runtime: (t) => [t.runtime_only, t.qualname], seen: (t) => [t.fused ? t.fused.refs_shown / t.refs_total : -1, t.qualname],
    static: (t) => [!!t.static?.pass, t.qualname], fused: (t) => [!!t.fused?.pass, t.qualname],
  };
  const k = keys[key];
  return [...tasks].sort((a, b) => {
    const x = k(a), y = k(b);
    for (let i = 0; i < x.length; i++) {
      if (x[i] < y[i]) return -dir;
      if (x[i] > y[i]) return dir;
    }
    return 0;
  });
}

// ---------- tasks ----------
const SORT_ICON = `<svg viewBox="0 0 10 10" aria-hidden="true"><path d="M1 3.5 5 7.5 9 3.5" fill="none" stroke="currentColor" stroke-width="1.6"/></svg>`;

function renderTasks(r, params) {
  const s = state.tasks;
  if ([...params.keys()].length) {
    Object.assign(s, { group: "all", repo: "all", outcome: "any", q: "" });
    for (const k of ["group", "repo", "outcome"]) if (params.get(k)) s[k] = params.get(k);
  }
  const repos = r.repos.map((x) => x.name);
  view.innerHTML = `
  <h1>Tasks</h1>
  <div class="filters">
    <div class="field"><span id="g-label">Group</span><div class="seg" role="group" aria-labelledby="g-label">
      ${["all", "treatment", "placebo"].map((g) => `<button type="button" data-group="${g}" aria-pressed="${s.group === g}">${g[0].toUpperCase() + g.slice(1)}</button>`).join("")}
    </div></div>
    <label class="field">Repo<select id="f-repo"><option value="all">All repos</option>${repos.map((x) => `<option ${s.repo === x ? "selected" : ""}>${esc(x)}</option>`).join("")}</select></label>
    <label class="field">Outcome<select id="f-outcome">
      ${[["any", "Any outcome"], ["differ", "Arms disagree"], ["static-pass", "Static arm passes"], ["fused-pass", "Fused arm passes"], ["both-pass", "Both arms pass"], ["both-fail", "Both arms fail"]].map(([v, l]) => `<option value="${v}" ${s.outcome === v ? "selected" : ""}>${l}</option>`).join("")}
    </select></label>
    <label class="field">Find a function<input type="search" id="f-q" value="${esc(s.q)}" placeholder="e.g. flag_activation_value" autocomplete="off"></label>
  </div>
  <p class="count" id="count" aria-live="polite"></p>
  <div class="scroll"><table>
    <thead><tr>
      ${[["task", "Task", "l"], ["repo", "Repo", "l"], ["group", "Group", "l"], ["runtime", "Runtime-only callers", ""], ["seen", "Lines seen", ""], ["static", "Static arm", ""], ["fused", "Fused arm", ""]]
        .map(([k, l, c]) => `<th scope="col" class="${c}" ${s.sort === k ? `aria-sort="${s.dir > 0 ? "ascending" : "descending"}"` : ""}><button class="sort" data-sort="${k}">${l}${SORT_ICON}</button></th>`).join("")}
    </tr></thead>
    <tbody id="rows"></tbody>
  </table></div>`;

  const paint = () => {
    const q = s.q.trim().toLowerCase();
    const list = r.tasks.filter((t) => (s.group === "all" || t.group === s.group)
      && (s.repo === "all" || t.repo === s.repo)
      && (!q || t.qualname.toLowerCase().includes(q))
      && (s.outcome === "any"
        || (s.outcome === "differ" && t.static && t.static.pass !== t.fused.pass)
        || (s.outcome === "static-pass" && t.static?.pass)
        || (s.outcome === "fused-pass" && t.fused?.pass)
        || (s.outcome === "both-pass" && t.static?.pass && t.fused?.pass)
        || (s.outcome === "both-fail" && t.static && !t.static.pass && !t.fused.pass)));
    document.getElementById("count").textContent = `${list.length} of ${r.tasks.length} tasks`;
    document.getElementById("rows").innerHTML = list.length
      ? sortTasks(list, s.sort, s.dir).map((t) => `<tr class="go" data-href="${taskHref(t.id)}">
          <td class="t"><a href="${taskHref(t.id)}">${esc(t.qualname)}</a></td><td class="l">${esc(t.repo)}</td>
          <td class="l"><span class="group-tag ${t.group}">${t.group}</span></td><td>${t.runtime_only}</td>
          <td class="seen">${t.static ? `${t.static.refs_shown} · <b>${t.fused.refs_shown}</b> / ${t.refs_total}` : "—"}</td>
          <td>${verdict(t.static)}</td><td>${verdict(t.fused)}</td></tr>`).join("")
      : `<tr><td colspan="7" class="empty">No task matches these filters. <a href="#/tasks" id="clear">Clear filters</a></td></tr>`;
  };
  paint();

  view.querySelectorAll("[data-group]").forEach((b) => b.addEventListener("click", () => {
    s.group = b.dataset.group;
    view.querySelectorAll("[data-group]").forEach((x) => x.setAttribute("aria-pressed", x === b));
    paint();
  }));
  document.getElementById("f-repo").addEventListener("change", (e) => { s.repo = e.target.value; paint(); });
  document.getElementById("f-outcome").addEventListener("change", (e) => { s.outcome = e.target.value; paint(); });
  document.getElementById("f-q").addEventListener("input", (e) => { s.q = e.target.value; paint(); });
  view.querySelectorAll("button.sort").forEach((b) => b.addEventListener("click", () => {
    s.dir = s.sort === b.dataset.sort ? -s.dir : 1;
    s.sort = b.dataset.sort;
    view.querySelectorAll("thead th").forEach((th) => th.removeAttribute("aria-sort"));
    b.parentElement.setAttribute("aria-sort", s.dir > 0 ? "ascending" : "descending");
    paint();
  }));
  view.addEventListener("click", (e) => {
    if (e.target.id === "clear") Object.assign(s, { group: "all", repo: "all", outcome: "any", q: "" });
  });
}

// ---------- method ----------
function renderMethod(r) {
  const a = r.attrition;
  const rows = Object.entries(a).filter(([k]) => k !== "eligible" && k !== "dropped by validation").sort((x, y) => y[1] - x[1]);
  view.innerHTML = `
  <h1>Method</h1>
  <div class="method" style="margin-top:24px">
    <section>
      <h2>Design</h2>
      <table class="design"><tbody>
        <tr><td>Task</td><td>Rename one function or method across the repository. One right answer, and a free oracle.</td></tr>
        <tr><td class="static-c">Static arm</td><td>The definition plus every caller reported by PyCG ∪ Pyright: the strongest static graph available.</td></tr>
        <tr><td class="fused-c">Fused arm</td><td>The same, plus callers observed while the repository's own test suite ran under <code>sys.setprofile</code>.</td></tr>
        <tr><td>Held equal</td><td>Prompt template, slicer, excerpt window, token budget, model and effort. A check on every task confirms the two prompts differ only in the caller list and its excerpts.</td></tr>
        <tr><td>Slicer</td><td>The retrieval unit is a caller function. For each, the model sees two lines either side of every line in that function's own body that names the target, plus the line the tracer saw make a runtime-only call.</td></tr>
        <tr><td>Oracle</td><td>Apply the edits and run the full suite. A task passes only if as many tests pass as on the untouched checkout and no new test fails.</td></tr>
        <tr><td>Editors</td><td>The <em>oracle</em> renames the symbol on every line its context shows, and nothing else: a ceiling. LLM runs use the same harness and are not yet recorded.</td></tr>
      </tbody></table>
      <h2 style="margin-top:16px">Pre-registered predictions</h2>
      <p class="muted">Written 10 Oct 2026, before any LLM run. The oracle ran first and is reported as a ceiling, not as a test of these.</p>
      <ol>
        <li>Treatment: the fused arm passes more tasks than the static arm. Exact two-sided McNemar on discordant pairs.</li>
        <li>Placebo: no difference between arms beyond the editor's own noise. Its prompts are identical by construction.</li>
      </ol>
    </section>
    <section id="exclusions">
      <h2>Which functions became tasks</h2>
      <p class="muted">Every function with at least one caller seen only at runtime, and why each excluded one was excluded. None of these filters looks at which arm sees what.</p>
      <table>
        <thead><tr><th scope="col">Reason</th><th scope="col">Functions</th></tr></thead>
        <tbody>${rows.map(([k, n]) => `<tr><td>${esc(k)}</td><td>${n}</td></tr>`).join("")}
          <tr class="pooled"><td>Eligible</td><td>${a.eligible || 0}</td></tr>
          <tr><td>Dropped: suite could not tell right from wrong</td><td>${a["dropped by validation"] || 0}</td></tr></tbody>
      </table>
      <h2 style="margin-top:16px">Limits</h2>
      <ul>
        <li><b>Small n.</b> A pilot on two repositories, reported with its exact p-value.</li>
        <li><b>A unique name makes text search sufficient.</b> The experiment measures call-graph-retrieved context, the kind code-graph retrieval supplies, not whether renaming is hard.</li>
        <li><b>Runtime coverage is the test suite's coverage.</b> A caller no test executes is invisible to both arms.</li>
        <li><b>Calls are not references.</b> A function stored or passed as a value is named on a line no call graph contains.</li>
        <li><b>Provenance.</b> These static graphs were extracted on the development host; regenerate on the execution host before publication.</li>
      </ul>
    </section>
  </div>`;
}

// ---------- task ----------
function markName(text, name) {
  const re = new RegExp(`(?<![\\w])${name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}(?![\\w])`, "g");
  return esc(text).replace(re, (m) => `<mark>${m}</mark>`);
}

function codeBlock(file, name) {
  let prev = null, out = "";
  for (const l of file.lines) {
    if (prev !== null && l.n !== prev + 1) out += `<div class="gap">lines ${prev + 1}–${l.n - 1} not shown</div>`;
    const cls = l.added ? " added" : "";
    out += `<div class="ln${cls}${l.edit !== null ? " edit" : ""}">${l.n}</div><div class="tx${cls}">${markName(l.text, name) || " "}</div>`;
    if (l.edit !== null) out += `<div class="ln edit" aria-label="edited to">→</div><div class="tx edit">${esc(l.edit)}</div>`;
    prev = l.n;
  }
  return `<div class="code-file"><div class="fname">${esc(file.path)}</div><div class="code">${out}</div></div>`;
}

function entry(kind, a, rec) {
  const match = rec && kind !== "Recorded"
    ? (a.pass === rec.pass && a.passed === rec.passed && a.failed === rec.failed
      ? `<span class="match pass">matches the record</span>` : `<span class="match fail">differs from the record</span>`)
    : "";
  return `<div class="entry${kind === "Recorded" ? "" : " live-entry"}">
    <span class="kind">${kind}</span>
    <span class="verdict ${a.pass ? "pass" : "fail"}">${a.pass ? "Pass" : "Fail"}</span>
    <span class="nums">${suiteLine(a)} ${match}</span>
  </div>`;
}

function armColumn(d, c) {
  const a = d.arms[c];
  const rec = a.recorded;
  const label = c === "static" ? `<span class="sc static-c">Static arm</span>` : `<span class="sc fused-c">Fused arm</span>`;
  const cap = c === "static" ? "callers from PyCG ∪ Pyright" : "plus callers seen at runtime";
  const failing = rec && rec.bad_count
    ? `<details class="prompt"><summary>Failing tests (${fmt(rec.bad_count)}, counting any that fail on the untouched checkout)</summary>
        <pre>${rec.bad.map(esc).join("\n")}${rec.bad_count > rec.bad.length ? `\nand ${fmt(rec.bad_count - rec.bad.length)} more` : ""}</pre></details>`
    : `<p class="none">${rec ? "No failing tests." : ""}</p>`;
  return `<section class="arm-col" aria-label="${c} arm">
    <header>${label}<span class="cap">${cap} · ${a.callers.length} in context</span></header>
    <div class="outcome" id="out-${c}">
      ${rec ? entry("Recorded", rec) : `<p class="none">No recorded run for this arm.</p>`}
      ${rec && !ran(rec) && rec.note ? `<p class="none">pytest said: <code>${esc(rec.note)}</code></p>` : ""}
    </div>
    <div>
      <div class="block-title">Lines naming the function it could not see <span>${a.unseen.length} of ${d.refs_total}</span></div>
      ${a.unseen.length ? `<ul class="unseen">${a.unseen.map((u) => `<li><span class="at">${esc(u.path)}:${u.n}</span><span class="src">${markName(u.text, d.name)}</span></li>`).join("")}</ul>` : `<p class="none">None: every line naming it was in the context.</p>`}
    </div>
    <div>
      <div class="block-title">Excerpts this arm was shown <span>${rec ? `${rec.edits} edit${rec.edits === 1 ? "" : "s"} made` : ""}${a.truncated ? " · truncated at the token budget" : ""}</span></div>
      ${a.excerpts.map((f) => codeBlock(f, d.name)).join("")}
    </div>
    ${failing}
    <details class="prompt"><summary>Callers in this arm's context (${a.callers.length})</summary>
      <pre>${a.callers.map((k) => `${esc(k.qualname)}  ${esc(k.path)}${k.runtime_only ? "   runtime only" : ""}`).join("\n") || "none"}</pre></details>
    <details class="prompt"><summary>Exact prompt ${rec ? `<code>sha256 ${rec.prompt_sha256.slice(0, 12)}</code>` : ""}</summary><pre>${esc(a.prompt)}</pre></details>
  </section>`;
}

function renderTask(d) {
  const head = `
    <p class="crumb"><a href="#/tasks">Tasks</a> / ${esc(d.repo)}</p>
    <div class="task-head">
      <h1>${esc(d.qualname)} <span class="to">renamed to</span> ${esc(d.new_name)}</h1>
      <p class="muted"><span class="group-tag ${d.group}">${d.group}</span> · ${esc(d.repo)} · <code>${esc(d.path)}:${d.line}</code></p>
    </div>
    <p class="summary">Static analysis found <b>${d.static_callers}</b> caller${d.static_callers === 1 ? "" : "s"}. Running the test suite found <b>${d.runtime_callers}</b>${d.fetched ? `, of which static analysis missed <b class="fused-c">${d.runtime_only.length}</b>` : ""}. The function is named on <b>${d.refs_total}</b> lines in the package${d.baseline ? `, and the untouched suite passes <b>${fmt(d.baseline.passed)}</b> tests` : ""}.</p>`;
  if (!d.fetched) {
    view.innerHTML = `${head}<p class="notice" style="margin-top:24px">The source for ${esc(d.repo)} is not on this machine, so its excerpts cannot be shown. Run <code>${esc(d.fetch_command)}</code>, then reload.</p>`;
    return;
  }
  view.innerHTML = `${head}
    ${d.runtime_only.length ? `<div class="scroll callers-table"><table>
      <caption>Callers only the runtime trace saw</caption>
      <thead><tr><th scope="col">Caller</th><th scope="col" class="l">Call site</th><th scope="col" class="l">Line that made the call</th></tr></thead>
      <tbody>${d.runtime_only.map((c) => `<tr><td class="t">${esc(c.qualname)}</td><td class="where">${esc(c.path)}${c.line ? `:${c.line}` : ""}</td><td class="src">${esc(c.text || "")}</td></tr>`).join("")}</tbody>
    </table></div>` : `<p class="table-note" style="margin-top:24px">A placebo task: no caller is visible only at runtime, so both arms receive the same prompt.</p>`}
    <div class="live">
      <button class="run" id="run" type="button">Re-run both arms now</button>
      <p id="run-note">Applies the oracle's edits and runs ${esc(d.repo)}'s test suite once per arm, about ${Math.max(2, Math.round(((d.arms.static.recorded?.seconds || 3) + (d.arms.fused.recorded?.seconds || 3)) + 1))} seconds.</p>
    </div>
    <div class="legend" style="margin-bottom:16px"><span><i class="k-added"></i>shown only to the fused arm</span><span><i class="k-name"></i>the function's name</span><span><i class="k-unseen"></i>a line naming it that the arm never saw</span></div>
    <div class="arms-grid">${armColumn(d, "static")}${armColumn(d, "fused")}</div>`;

  const btn = document.getElementById("run");
  const note = document.getElementById("run-note");
  btn.addEventListener("click", async () => {
    btn.disabled = true;
    const t0 = performance.now();
    const tick = setInterval(() => { note.textContent = `Running the suite for both arms… ${((performance.now() - t0) / 1000).toFixed(0)} s`; }, 250);
    try {
      const live = await api(`/api/run?id=${encodeURIComponent(d.id)}`, { method: "POST" });
      for (const c of ["static", "fused"]) {
        document.getElementById(`out-${c}`).insertAdjacentHTML("beforeend", entry(`Live, ${clock(Date.now(), false)}`, live[c], d.arms[c].recorded));
      }
      note.textContent = `Finished in ${((performance.now() - t0) / 1000).toFixed(1)} s. Live results sit under the recorded ones; nothing was overwritten.`;
    } catch (err) {
      note.innerHTML = `<span class="err">The run did not complete: ${esc(err.message)}</span>`;
    } finally {
      clearInterval(tick);
      btn.disabled = false;
    }
  });
}

// ---------- routing ----------
async function route() {
  const [path, query] = location.hash.slice(1).split("?");
  const params = new URLSearchParams(query || "");
  const section = path.split("/")[1] || "report";
  document.querySelectorAll("[data-nav]").forEach((a) => a.toggleAttribute("aria-current", false));
  const nav = document.querySelector(`[data-nav="${section === "task" ? "tasks" : section}"]`);
  if (nav) nav.setAttribute("aria-current", "page");
  try {
    state.report ??= await api("/api/report");
    const r = state.report;
    document.getElementById("status").textContent = r.provenance.last
      ? `Oracle ceiling · recorded ${day(r.provenance.last)} · no LLM runs yet` : "No runs recorded";
    if (section === "report") renderReport(r);
    else if (section === "tasks") renderTasks(r, params);
    else if (section === "method") renderMethod(r);
    else if (section === "task") {
      view.innerHTML = `<p class="loading">Loading the task and both arms' excerpts…</p>`;
      renderTask(await api(`/api/task?id=${encodeURIComponent(decodeURIComponent(path.split("/").slice(2).join("/")))}`));
    } else view.innerHTML = `<p class="notice">There is no page at this address. <a href="#/report">Go to the report</a>.</p>`;
    document.title = { report: "Report", tasks: "Tasks", method: "Method", task: "Task" }[section]
      ? `${{ report: "Report", tasks: "Tasks", method: "Method", task: "Task" }[section]} · TraceWeave harness` : "TraceWeave harness";
  } catch (err) {
    view.innerHTML = `<p class="notice">Could not load this page: ${esc(err.message)}. Is <code>python3 tw.py ui</code> still running?</p>`;
  }
  const focus = params.get("focus") && document.getElementById(params.get("focus"));
  if (focus) focus.scrollIntoView({ block: "start" });
  else window.scrollTo(0, 0);
}

view.addEventListener("click", (e) => {
  const row = e.target.closest("tr.go");
  if (row && !e.target.closest("a")) location.hash = row.dataset.href;
});
window.addEventListener("hashchange", route);
route();
