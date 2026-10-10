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

const GROUP = { treatment: "hidden caller", placebo: "control" };
const RUN = { static: "Static only", fused: "Static + runtime" };

function verdict(a) {
  if (!a) return `<span class="muted">not run</span>`;
  return a.pass ? `<span class="v-pass">pass</span>` : `<span class="v-fail">fail</span>`;
}

function suiteLine(a) {
  if (!ran(a)) return `The tests could not start <span class="muted">(pytest exit code ${a.rc})</span>`;
  return `<b>${fmt(a.passed)}</b> tests passed, <b>${fmt(a.failed)}</b> failed${a.errors ? `, <b>${fmt(a.errors)}</b> errors` : ""}`;
}

const REASONS = {
  "name shared with another function (override family)": "Another function has the same name",
  "dunder method": "Special method, such as __init__",
  "name appears in the test suite": "The tests mention it by name",
  "not a function or method (lambda)": "Lambda, so it has no name to change",
  "name under four characters": "Name shorter than four letters",
  "overload stub or numbered redefinition": "Overload stub",
  "no in-package caller ran under the suite": "No test runs it",
  "new name already in use": "The new name is already taken",
};
const reason = (k) => REASONS[k] || k;

// ---------- report ----------
function consort(r) {
  const a = r.attrition;
  const excluded = Object.entries(a).filter(([k]) => k !== "eligible" && k !== "dropped by validation").sort((x, y) => y[1] - x[1]);
  const exclTotal = excluded.reduce((s, [, n]) => s + n, 0);
  const eligible = a.eligible || 0;
  const dropped = a["dropped by validation"] || 0;
  const t = r.table.find((x) => x.repo === "pooled" && x.group === "treatment");
  if (!t) return `<p class="muted">No results for hidden-caller tasks yet.</p>`;
  const how = "#/method?focus=exclusions";
  return `
  <figure class="fig">
  <figcaption>Figure 1. How the ${t.tasks} tasks were chosen, and how many passed <span class="muted">(results from the rename script, not an LLM)</span></figcaption>
  <div class="flow">
    <a class="box" href="${how}">Functions with a hidden caller<b>${fmt(eligible + exclTotal)}</b><span class="hint">see how tasks were chosen</span></a>
    <div class="v"></div>
    <div class="row">
      <a class="box" href="${how}">Usable as rename tasks<b>${fmt(eligible)}</b></a>
      <div class="h" aria-hidden="true"></div>
      <a class="excl" href="${how}"><b>Left out, ${fmt(exclTotal)}</b><ul>${excluded.map(([k, n]) => `<li><span>${esc(reason(k))}</span><span>${fmt(n)}</span></li>`).join("")}</ul><span class="hint">see each reason</span></a>
    </div>
    <div class="v"></div>
    <div class="row">
      <a class="box" href="#/tasks?group=treatment">The tests can check the rename<b>${fmt(t.tasks)}</b><span class="hint">see all ${t.tasks}</span></a>
      <div class="h" aria-hidden="true"></div>
      <a class="excl" href="${how}"><b>Left out, ${fmt(dropped)}</b><ul><li><span>The tests could not tell a right rename from a wrong one</span></li></ul><span class="hint">see how this was checked</span></a>
    </div>
    <div class="v" aria-hidden="true"></div>
    <div class="split" aria-hidden="true"></div>
    <div class="arms">
      <a class="arm" href="#/tasks?group=treatment&outcome=static-pass"><span class="sc static-c">${RUN.static}</span><b>${t.static}</b><span class="of">of ${t.tasks} pass</span><span class="hint">see these</span></a>
      <a class="arm" href="#/tasks?group=treatment&outcome=fused-pass"><span class="sc fused-c">${RUN.fused}</span><b>${t.fused}</b><span class="of">of ${t.tasks} pass</span><span class="hint">see these</span></a>
    </div>
    <p class="paired">Each task runs twice, once with each set of callers.</p>
  </div>
  </figure>`;
}

function outcomesTable(r) {
  const order = ["treatment", "placebo"];
  const rows = [...r.table].sort((x, y) => order.indexOf(x.group) - order.indexOf(y.group)
    || (x.repo === "pooled") - (y.repo === "pooled") || x.repo.localeCompare(y.repo));
  const label = (x) => `${x.group === "treatment" ? "Hidden caller" : "Control"}, ${x.repo === "pooled" ? "both repos" : x.repo}`;
  return `<table>
    <caption>Table 1. Tasks passed with each set of callers</caption>
    <thead><tr><th scope="col">Tasks</th><th scope="col">Count</th><th scope="col">${RUN.static}</th><th scope="col">${RUN.fused}</th><th scope="col">Pass only with runtime<sup>a</sup></th><th scope="col">Pass only without<sup>a</sup></th><th scope="col">p-value<sup>b</sup></th></tr></thead>
    <tbody>${rows.map((x) => { const href = `#/tasks?group=${x.group}&repo=${x.repo === "pooled" ? "all" : encodeURIComponent(x.repo)}`;
      return `<tr class="go ${x.repo === "pooled" ? "pooled" : ""}" data-href="${href}"><td class="nw"><a href="${href}">${label(x)}</a></td><td>${x.tasks}</td><td>${x.static}</td><td>${x.fused}</td><td>${x.fused_only}</td><td>${x.static_only}</td><td>${pval(x.p)}</td></tr>`; }).join("")}</tbody>
  </table>`;
}

function rosterRows(tasks) {
  return tasks.map((t) => `<tr class="go" data-href="${taskHref(t.id)}">
      <td class="t"><a href="${taskHref(t.id)}">${esc(t.qualname)}</a></td>
      <td class="l">${esc(t.repo)}</td>
      <td>${t.runtime_only}</td>
      ${shownCells(t)}
      <td>${verdict(t.static)}</td><td>${verdict(t.fused)}</td></tr>`).join("");
}

function shownCells(t) {
  if (!t.static) return `<td class="seen">not run</td><td class="seen">not run</td>`;
  return `<td class="seen">${t.static.refs_shown} of ${t.refs_total}</td><td class="seen"><b>${t.fused.refs_shown}</b> of ${t.refs_total}</td>`;
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
      <h1>Does knowing the calls that happen at runtime help rename code correctly?</h1>
      <p class="lede">The editor renames one function across a whole project, but it only sees the code that calls the function. Each task runs twice. The first time, static analysis finds the callers. The second time, we also add callers recorded while the project's tests ran. The project's own tests then decide whether the rename worked.</p>
      ${consort(r)}
    </section>
    <section>
      <div class="scroll">${outcomesTable(r)}</div>
      <ol class="footnotes">
        <li><sup>a</sup> Tasks where the two runs disagree.</li>
        <li><sup>b</sup> Exact two-sided McNemar test on the tasks where the two runs disagree.</li>
      </ol>
      <p class="table-note">The rename script changes the function's name on every line it is shown, so it fails only when a line is missing. Its score is the best any editor could reach with the same code in view. Control tasks get the same prompt both times, so their two runs should match, and they do${placebo ? ` (${placebo.static} and ${placebo.fused} of ${placebo.tasks})` : ""}. ${fusedFails.length ? `With runtime callers added, ${fusedFails.length} hidden-caller tasks still fail. ${oneLine === fusedFails.length ? "Each" : `${oneLine} of them`} misses one line that stores or passes the function instead of calling it, and no call graph records that line.` : ""}</p>
      <p class="witness">These numbers come from <code>${esc(p.command)}</code>, which reads ${fmt(p.rows)} saved runs from ${p.first ? `${day(p.first)}, ${clock(p.first)} to ${clock(p.last)} UTC` : "no runs yet"}.</p>
    </section>
  </div>
  <div class="below">
    <section>
      <div class="scroll"><table>
        <caption>Table 2. Hidden-caller tasks <span class="muted">(how many lines that mention the function each run was shown)</span></caption>
        <thead><tr><th scope="col">Function</th><th scope="col" class="l">Repo</th><th scope="col">Hidden callers</th><th scope="col">Lines shown, ${RUN.static.toLowerCase()}</th><th scope="col">Lines shown, ${RUN.fused.toLowerCase()}</th><th scope="col">${RUN.static}</th><th scope="col">${RUN.fused}</th></tr></thead>
        <tbody>${rosterRows(sortTasks(treat, "fused-first"))}</tbody>
      </table></div>
    </section>
    <section>
      <h2>Control tasks</h2>
      <p class="muted">${placebo ? `In ${placebo.tasks} tasks, static analysis already finds every caller, so both runs get the same prompt. ${placebo.tasks - placebo.static} fail both times, because a line that mentions the function sits outside every call graph.` : "No results yet."} <a href="#/tasks?group=placebo">See the control tasks</a>.</p>
    </section>
  </div>`;
}

function sortTasks(tasks, key, dir = 1) {
  const score = (t) => (t.fused?.pass ? 2 : 0) + (t.static?.pass ? 1 : 0);
  const keys = {
    "fused-first": (t) => [-(t.fused?.pass && !t.static?.pass), -score(t), t.qualname],
    task: (t) => [t.qualname], repo: (t) => [t.repo, t.qualname], group: (t) => [t.group === "placebo", t.qualname],
    runtime: (t) => [t.runtime_only, t.qualname], seen: (t) => [t.fused ? t.fused.refs_shown / t.refs_total : -1, t.qualname],
    "seen-static": (t) => [t.static ? t.static.refs_shown / t.refs_total : -1, t.qualname],
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
    <div class="field"><span id="g-label">Task type</span><div class="seg" role="group" aria-labelledby="g-label">
      ${[["all", "All"], ["treatment", "Hidden caller"], ["placebo", "Control"]].map(([g, l]) => `<button type="button" data-group="${g}" aria-pressed="${s.group === g}">${l}</button>`).join("")}
    </div></div>
    <label class="field">Repo<select id="f-repo"><option value="all">All repos</option>${repos.map((x) => `<option ${s.repo === x ? "selected" : ""}>${esc(x)}</option>`).join("")}</select></label>
    <label class="field">Result<select id="f-outcome">
      ${[["any", "Any result"], ["differ", "The two runs disagree"], ["static-pass", `${RUN.static} passes`], ["fused-pass", `${RUN.fused} passes`], ["both-pass", "Both runs pass"], ["both-fail", "Both runs fail"]].map(([v, l]) => `<option value="${v}" ${s.outcome === v ? "selected" : ""}>${l}</option>`).join("")}
    </select></label>
    <label class="field">Find a function<input type="search" id="f-q" value="${esc(s.q)}" placeholder="flag_activation_value" autocomplete="off"></label>
  </div>
  <p class="count" id="count" aria-live="polite"></p>
  <div class="scroll"><table>
    <thead><tr>
      ${[["task", "Function", "l"], ["repo", "Repo", "l"], ["group", "Task type", "l"], ["runtime", "Hidden callers", ""], ["seen-static", `Lines shown, ${RUN.static.toLowerCase()}`, ""], ["seen", `Lines shown, ${RUN.fused.toLowerCase()}`, ""], ["static", RUN.static, ""], ["fused", RUN.fused, ""]]
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
          <td class="l"><span class="group-tag ${t.group}">${GROUP[t.group]}</span></td><td>${t.runtime_only}</td>
          ${shownCells(t)}
          <td>${verdict(t.static)}</td><td>${verdict(t.fused)}</td></tr>`).join("")
      : `<tr><td colspan="8" class="empty">No task matches these filters. <a href="#/tasks" id="clear">Clear filters</a></td></tr>`;
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
  <h1>How it works</h1>
  <div class="method" style="margin-top:24px">
    <section>
      <h2>The experiment</h2>
      <table class="design"><tbody>
        <tr><td>Task</td><td>Rename one function everywhere in a project. There is one right answer, and the project's tests can check it.</td></tr>
        <tr><td class="static-c">${RUN.static}</td><td>The editor sees the function and every caller that two static analysers, PyCG and Pyright, find together.</td></tr>
        <tr><td class="fused-c">${RUN.fused}</td><td>The editor also sees callers recorded while the project's own tests ran.</td></tr>
        <tr><td>Kept the same</td><td>The prompt, the amount of code shown, and the editor. An automatic check on every task confirms that the two prompts differ only in the list of callers and their code.</td></tr>
        <tr><td>Code shown</td><td>For each caller, the editor sees every line in that caller that mentions the function, with two lines either side. For a hidden caller, it also sees the line where the test run recorded the call.</td></tr>
        <tr><td>Pass or fail</td><td>We apply the edits and run all the project's tests. A rename passes only if as many tests pass as before and no new test fails.</td></tr>
        <tr><td>Editor</td><td>The rename script changes the name on every line it is shown and nothing else, so its score is the best possible with that code. An LLM will use the same steps. No LLM has run yet.</td></tr>
      </tbody></table>
      <h2 style="margin-top:16px">Predictions written before any LLM run</h2>
      <p class="muted">Written on 10 Oct 2026. The rename script ran before this, and its scores show the best possible result, so they do not test these predictions.</p>
      <ol>
        <li>On hidden-caller tasks, more renames pass with runtime callers added. An exact two-sided McNemar test checks this.</li>
        <li>On control tasks, both runs score the same apart from the editor's own randomness, because their prompts are identical.</li>
      </ol>
    </section>
    <section id="exclusions">
      <h2>Which functions became tasks</h2>
      <p class="muted">This table lists every function with a hidden caller and why some were left out. None of these rules looks at which run a task goes to.</p>
      <table>
        <thead><tr><th scope="col">Reason</th><th scope="col">Functions</th></tr></thead>
        <tbody>${rows.map(([k, n]) => `<tr><td>${esc(reason(k))}</td><td>${n}</td></tr>`).join("")}
          <tr class="pooled"><td>Usable as rename tasks</td><td>${a.eligible || 0}</td></tr>
          <tr><td>Left out because the tests could not tell a right rename from a wrong one</td><td>${a["dropped by validation"] || 0}</td></tr></tbody>
      </table>
      <p class="muted">To check each task, we rename every line that mentions the function, and the tests must pass. Then we rename only the definition, and the tests must fail.</p>
      <h2 style="margin-top:16px">Limits</h2>
      <ul>
        <li><b>Few tasks.</b> This pilot covers two projects and 17 hidden-caller tasks, so the p-value is shown in full.</li>
        <li><b>Search would also work here.</b> Each function has a unique name, so a text search finds every line. The experiment tests code found through call graphs, the way code-search tools for AI find it. It does not test whether renaming is hard.</li>
        <li><b>The test run only sees what the tests run.</b> If no test runs a caller, neither run of the editor sees it.</li>
        <li><b>A call graph records calls, not every mention.</b> When code stores or passes a function as a value, that line is not a call, and no call graph records it.</li>
        <li><b>Where the graphs came from.</b> We built these static call graphs on the development Mac. Before publishing, we will rebuild them on the Linux machine that runs the experiments.</li>
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
    if (prev !== null && l.n !== prev + 1) out += `<div class="gap">lines ${prev + 1} to ${l.n - 1} not shown</div>`;
    const cls = l.added ? " added" : "";
    out += `<div class="ln${cls}${l.edit !== null ? " edit" : ""}">${l.n}</div><div class="tx${cls}">${markName(l.text, name) || " "}</div>`;
    if (l.edit !== null) out += `<div class="ln edit">new</div><div class="tx edit">${esc(l.edit)}</div>`;
    prev = l.n;
  }
  return `<div class="code-file"><div class="fname">${esc(file.path)}</div><div class="code">${out}</div></div>`;
}

function entry(kind, a, rec) {
  const match = rec && kind !== "Saved run"
    ? (a.pass === rec.pass && a.passed === rec.passed && a.failed === rec.failed
      ? `<span class="match pass">Same as the saved run.</span>` : `<span class="match fail">Different from the saved run.</span>`)
    : "";
  return `<div class="entry${kind === "Saved run" ? "" : " live-entry"}">
    <span class="kind">${kind}</span>
    <span class="verdict ${a.pass ? "pass" : "fail"}">${a.pass ? "Pass" : "Fail"}</span>
    <span class="nums">${suiteLine(a)} ${match}</span>
  </div>`;
}

function armColumn(d, c) {
  const a = d.arms[c];
  const rec = a.recorded;
  const label = `<span class="sc ${c}-c">${RUN[c]}</span>`;
  const n = a.callers.length;
  const cap = c === "static" ? `${n} caller${n === 1 ? "" : "s"} found by static analysis` : `${n} caller${n === 1 ? "" : "s"}, including hidden ones`;
  const failing = rec && rec.bad_count
    ? `<details class="prompt"><summary>${fmt(rec.bad_count)} failing test${rec.bad_count === 1 ? "" : "s"}, including any that also fail before the edit</summary>
        <pre>${rec.bad.map(esc).join("\n")}${rec.bad_count > rec.bad.length ? `\nand ${fmt(rec.bad_count - rec.bad.length)} more` : ""}</pre></details>`
    : `<p class="none">${rec ? "No test failed." : ""}</p>`;
  return `<section class="arm-col" aria-label="${RUN[c]}">
    <header>${label}<span class="cap">${cap}</span></header>
    <div class="outcome" id="out-${c}">
      ${rec ? entry("Saved run", rec) : `<p class="none">This run has no saved result.</p>`}
      ${rec && !ran(rec) && rec.note ? `<p class="none">pytest printed <code>${esc(rec.note)}</code></p>` : ""}
    </div>
    <div>
      <div class="block-title">Lines that mention the function but were not shown <span>${a.unseen.length} of ${d.refs_total}</span></div>
      ${a.unseen.length ? `<ul class="unseen">${a.unseen.map((u) => `<li><span class="at">${esc(u.path)}:${u.n}</span><span class="src">${markName(u.text, d.name)}</span></li>`).join("")}</ul>` : `<p class="none">None. Every line that mentions the function was shown.</p>`}
    </div>
    <div>
      <div class="block-title">Code the editor was shown <span>${rec ? `${rec.edits} line${rec.edits === 1 ? "" : "s"} changed` : ""}${a.truncated ? ". Cut short at the size limit." : ""}</span></div>
      ${a.excerpts.map((f) => codeBlock(f, d.name)).join("")}
    </div>
    ${failing}
    <details class="prompt"><summary>The ${n} caller${n === 1 ? "" : "s"} in this run</summary>
      <pre>${a.callers.map((k) => `${esc(k.qualname)}  ${esc(k.path)}${k.runtime_only ? "   (hidden caller)" : ""}`).join("\n") || "none"}</pre></details>
    <details class="prompt"><summary>The exact prompt the editor received ${rec ? `<code>sha256 ${rec.prompt_sha256.slice(0, 12)}</code>` : ""}</summary><pre>${esc(a.prompt)}</pre></details>
  </section>`;
}

function renderTask(d) {
  const head = `
    <p class="crumb"><a href="#/tasks">Tasks</a> / ${esc(d.repo)}</p>
    <div class="task-head">
      <h1><span class="to">Rename</span> ${esc(d.qualname)} <span class="to">to</span> ${esc(d.new_name)}</h1>
      <p class="muted"><span class="group-tag ${d.group}">${GROUP[d.group]} task</span>, in ${esc(d.repo)} at <code>${esc(d.path)}:${d.line}</code></p>
    </div>
    <p class="summary">Static analysis found <b>${d.static_callers}</b> caller${d.static_callers === 1 ? "" : "s"}. The test run found <b>${d.runtime_callers}</b>${d.fetched ? (d.runtime_only.length === d.runtime_callers ? `, and ${d.runtime_callers === 1 ? "it is" : `all <b class="fused-c">${d.runtime_callers}</b> are`} hidden from static analysis`
        : d.runtime_only.length ? `, and <b class="fused-c">${d.runtime_only.length}</b> of them ${d.runtime_only.length === 1 ? "is" : "are"} hidden from static analysis` : ", and static analysis found all of them") : ""}. The function is mentioned on <b>${d.refs_total}</b> lines in the project${d.baseline ? `, and before any edit <b>${fmt(d.baseline.passed)}</b> tests pass` : ""}.</p>`;
  if (!d.fetched) {
    view.innerHTML = `${head}<p class="notice" style="margin-top:24px">The code for ${esc(d.repo)} is not on this computer, so this page cannot show it. Run <code>${esc(d.fetch_command)}</code>, then reload the page.</p>`;
    return;
  }
  view.innerHTML = `${head}
    ${d.runtime_only.length ? `<div class="scroll callers-table"><table>
      <caption>Hidden callers <span class="muted">(found by the test run, missed by static analysis)</span></caption>
      <thead><tr><th scope="col">Caller</th><th scope="col" class="l">File and line</th><th scope="col" class="l">The line that calls the function</th></tr></thead>
      <tbody>${d.runtime_only.map((c) => `<tr><td class="t">${esc(c.qualname)}</td><td class="where">${esc(c.path)}${c.line ? `:${c.line}` : ""}</td><td class="src">${esc(c.text || "")}</td></tr>`).join("")}</tbody>
    </table></div>` : `<p class="table-note" style="margin-top:24px">This is a control task. Static analysis already finds every caller, so both runs get the same prompt.</p>`}
    <div class="live">
      <button class="run" id="run" type="button">Run both again now</button>
      <p id="run-note">This runs the rename script with each set of callers, then runs ${esc(d.repo)}'s tests after each. It takes about ${Math.max(2, Math.round(((d.arms.static.recorded?.seconds || 3) + (d.arms.fused.recorded?.seconds || 3)) + 1))} seconds.</p>
    </div>
    <div class="legend" style="margin-bottom:16px"><span><i class="k-added"></i>shown only when runtime callers are added</span><span><i class="k-name"></i>the function's name</span><span><i class="k-unseen"></i>mentions the function but was not shown</span></div>
    <div class="arms-grid">${armColumn(d, "static")}${armColumn(d, "fused")}</div>`;

  const btn = document.getElementById("run");
  const note = document.getElementById("run-note");
  btn.addEventListener("click", async () => {
    btn.disabled = true;
    const t0 = performance.now();
    const tick = setInterval(() => { note.textContent = `Running the tests for both runs, ${((performance.now() - t0) / 1000).toFixed(0)} s so far.`; }, 250);
    try {
      const live = await api(`/api/run?id=${encodeURIComponent(d.id)}`, { method: "POST" });
      for (const c of ["static", "fused"]) {
        document.getElementById(`out-${c}`).insertAdjacentHTML("beforeend", entry(`Run at ${clock(Date.now(), false)}`, live[c], d.arms[c].recorded));
      }
      note.textContent = `Finished in ${((performance.now() - t0) / 1000).toFixed(1)} s. The new results are listed under the saved ones, which stay unchanged.`;
    } catch (err) {
      note.innerHTML = `<span class="err">The run stopped. ${esc(err.message)}</span>`;
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
      ? `Rename script results from ${day(r.provenance.last)}. No LLM run yet.` : "No saved runs yet.";
    if (section === "report") renderReport(r);
    else if (section === "tasks") renderTasks(r, params);
    else if (section === "method") renderMethod(r);
    else if (section === "task") {
      view.innerHTML = `<p class="loading">Loading the task…</p>`;
      renderTask(await api(`/api/task?id=${encodeURIComponent(decodeURIComponent(path.split("/").slice(2).join("/")))}`));
    } else view.innerHTML = `<p class="notice">This page does not exist. <a href="#/report">Go to the results</a>.</p>`;
    const titles = { report: "Results", tasks: "Tasks", method: "How it works", task: "Task" };
    document.title = titles[section] ? `${titles[section]} | TraceWeave harness` : "TraceWeave harness";
  } catch (err) {
    view.innerHTML = `<p class="notice">This page could not load (${esc(err.message)}). Check that <code>python3 tw.py ui</code> is still running.</p>`;
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
