---
name: TraceWeave harness
description: Two studies of who can find a function's calls and whether an AI agent can rename it, reported the way a clinical trial is reported.
colors:
  ink: "#1b1b1b"
  ink-2: "#4a5057"
  ink-3: "#6b7279"
  hair: "#d3d9df"
  journal-blue: "#0b4f8a"
  journal-blue-deep: "#083c6a"
  blue-tint: "#dce8f4"
  slate: "#56616b"
  analyser-slate: "#7d8790"
  failure-red: "#b23a2e"
  red-tint: "#f7e5e2"
  red-line: "#e7c7c2"
  mist: "#e9eef3"
  wash: "#f7f9fb"
  control-line: "#9aa3ab"
  wait-line: "#b9c2cb"
  track: "#dfe5ea"
  faint-rule: "#eef1f4"
  contour: "#c7d2dc"
  page: "#ffffff"
typography:
  display:
    fontFamily: "Source Serif 4, Georgia, serif"
    fontSize: "44px"
    fontWeight: 600
    lineHeight: 1.05
  headline:
    fontFamily: "Source Serif 4, Georgia, serif"
    fontSize: "30px"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "-0.01em"
  title:
    fontFamily: "Source Serif 4, Georgia, serif"
    fontSize: "21px"
    fontWeight: 600
    lineHeight: 1.3
  caption:
    fontFamily: "Source Serif 4, Georgia, serif"
    fontSize: "17px"
    fontWeight: 600
    lineHeight: 1.35
  narration:
    fontFamily: "Source Sans 3, -apple-system, Segoe UI, sans-serif"
    fontSize: "18px"
    fontWeight: 400
    lineHeight: 1.5
  body:
    fontFamily: "Source Sans 3, -apple-system, Segoe UI, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.5
    fontFeature: "\"tnum\""
  label:
    fontFamily: "Source Sans 3, -apple-system, Segoe UI, sans-serif"
    fontSize: "14.5px"
    fontWeight: 700
    letterSpacing: "0.04em"
    fontFeature: "\"smcp\""
  note:
    fontFamily: "Source Sans 3, -apple-system, Segoe UI, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.45
  mono:
    fontFamily: "ui-monospace, SF Mono, Menlo, Consolas, monospace"
    fontSize: "12.5px"
    fontWeight: 400
    lineHeight: 1.6
rounded:
  none: "0px"
spacing:
  s1: "4px"
  s2: "8px"
  s3: "12px"
  s4: "16px"
  s5: "24px"
  s6: "32px"
  s7: "48px"
  s8: "64px"
  gutter: "clamp(16px, 3.3vw, 48px)"
components:
  button-run:
    backgroundColor: "{colors.journal-blue}"
    textColor: "{colors.page}"
    rounded: "{rounded.none}"
    padding: "11px 18px"
  button-run-hover:
    backgroundColor: "{colors.journal-blue-deep}"
  button-run-disabled:
    backgroundColor: "{colors.mist}"
    textColor: "{colors.ink-2}"
  button-ghost:
    backgroundColor: "{colors.page}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "11px 16px"
  button-ghost-hover:
    backgroundColor: "{colors.mist}"
  button-ghost-disabled:
    backgroundColor: "{colors.page}"
    textColor: "{colors.ink-3}"
  segmented-option:
    backgroundColor: "{colors.page}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "6px 14px"
  segmented-option-pressed:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.page}"
  input-field:
    backgroundColor: "{colors.page}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "6px 10px"
  consort-box:
    backgroundColor: "{colors.page}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "10px 16px"
    width: "300px"
  consort-arm:
    backgroundColor: "{colors.page}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "{spacing.s3}"
    width: "140px"
  table-row-pooled:
    backgroundColor: "{colors.mist}"
    textColor: "{colors.ink}"
  story-column:
    backgroundColor: "{colors.page}"
    textColor: "{colors.ink}"
    width: "1120px"
  score-dot:
    backgroundColor: "{colors.page}"
    rounded: "{rounded.none}"
    size: "22px"
  score-dot-pass:
    backgroundColor: "{colors.journal-blue}"
  score-dot-fail:
    backgroundColor: "{colors.red-tint}"
  step-marker:
    backgroundColor: "{colors.page}"
    textColor: "{colors.ink-3}"
    rounded: "{rounded.none}"
    size: "24px"
  step-marker-done:
    backgroundColor: "{colors.ink-2}"
    textColor: "{colors.page}"
  step-marker-now:
    backgroundColor: "{colors.journal-blue}"
    textColor: "{colors.page}"
  place:
    backgroundColor: "{colors.page}"
    rounded: "{rounded.none}"
    width: "36px"
    height: "26px"
  place-shown-static:
    backgroundColor: "{colors.mist}"
  place-shown-fused:
    backgroundColor: "{colors.blue-tint}"
  place-done-static:
    backgroundColor: "{colors.slate}"
  place-done-fused:
    backgroundColor: "{colors.journal-blue}"
  place-missed:
    backgroundColor: "{colors.red-tint}"
  progress-track:
    backgroundColor: "{colors.track}"
    height: "8px"
  diff-del:
    backgroundColor: "{colors.wash}"
    textColor: "{colors.ink-3}"
    padding: "1px 6px"
  diff-ins:
    backgroundColor: "{colors.page}"
    textColor: "{colors.ink}"
    padding: "1px 6px"
  unseen-list:
    backgroundColor: "{colors.red-tint}"
    textColor: "{colors.ink}"
    typography: "{typography.mono}"
    padding: "6px 10px"
  masthead:
    backgroundColor: "{colors.page}"
    textColor: "{colors.ink-2}"
    height: "60px"
  overview-column:
    backgroundColor: "{colors.page}"
    textColor: "{colors.ink}"
    width: "1440px"
  study-column:
    backgroundColor: "{colors.page}"
    textColor: "{colors.ink}"
    width: "1320px"
  plane-mark-static:
    backgroundColor: "{colors.analyser-slate}"
    rounded: "{rounded.none}"
    size: "12px"
  plane-mark-ai:
    backgroundColor: "{colors.journal-blue}"
    size: "13px"
  plane-mark-combiner:
    backgroundColor: "{colors.journal-blue}"
    size: "20px"
  plane-mark-baseline:
    backgroundColor: "{colors.page}"
    size: "14px"
  tooltip:
    backgroundColor: "{colors.page}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "8px 10px"
    width: "260px"
  f1-bar:
    backgroundColor: "{colors.faint-rule}"
    rounded: "{rounded.none}"
    width: "90px"
    height: "8px"
  f1-bar-ai:
    backgroundColor: "{colors.journal-blue}"
  f1-bar-static:
    backgroundColor: "{colors.analyser-slate}"
  f1-bar-combiner:
    backgroundColor: "{colors.journal-blue-deep}"
  f1-bar-baseline:
    backgroundColor: "{colors.wait-line}"
  leaderboard-row-best:
    backgroundColor: "{colors.blue-tint}"
    textColor: "{colors.ink}"
  weight-bar-negative:
    backgroundColor: "{colors.analyser-slate}"
    height: "10px"
  weight-bar-positive:
    backgroundColor: "{colors.journal-blue}"
    height: "10px"
  candidate-cell-right:
    backgroundColor: "{colors.page}"
    textColor: "{colors.journal-blue}"
    padding: "6px 4px"
  candidate-cell-wrong:
    backgroundColor: "{colors.red-tint}"
    textColor: "{colors.failure-red}"
    padding: "6px 4px"
  candidate-cell-truth:
    backgroundColor: "{colors.mist}"
    textColor: "{colors.ink}"
    padding: "6px 4px"
  matrix-row-bound:
    backgroundColor: "{colors.wash}"
    textColor: "{colors.ink}"
  line-square:
    backgroundColor: "{colors.page}"
    rounded: "{rounded.none}"
    size: "18px"
  line-square-shown:
    backgroundColor: "{colors.mist}"
  line-square-shown-right:
    backgroundColor: "{colors.blue-tint}"
  line-square-done:
    backgroundColor: "{colors.journal-blue}"
  line-square-wrong-edit:
    backgroundColor: "{colors.failure-red}"
  line-square-missed:
    backgroundColor: "{colors.red-tint}"
  pipeline-box:
    backgroundColor: "{colors.page}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "12px 14px"
---

# Design System: TraceWeave harness

## Overview

**Creative North Star: "The Clinical Trial Report"**

The surface is set like a results section in a medical journal: a white page, near-black ink, one journal blue, and figures whose every number links to the rows behind it. The default route is the Overview, built on one figure: a precision–recall plane on which every resolver is a point, beside three numbered findings in plain sentences and a compact results matrix. Study 1 and Study 2 follow as journal sections (numbered figures, three-rule tables, a table of every item), and Method draws the pipeline as flow boxes. The register is a printed report someone can audit, not a product dashboard. The chart is the hero; nothing above it competes.

The earlier pilot stays reachable and keeps its own forms: the pilot walkthrough (#/pilot, one task told as a story with a scoreboard, stepper, call graph and place squares), pilot results (#/pilot-results, a CONSORT flow and outcome tables), pilot tasks (#/tasks and #/task/<id>) and pilot method (#/pilot-method). They are linked from Method's "Earlier pilot" paragraph and highlight the Method tab.

Density is that of a journal page read on a 13 to 15 inch laptop: 15px sans body with tabular figures, 13px notes, serif reserved for titles, captions, counts and verdict words. Colour carries meaning and nothing else. On the study pages, blue is AI models, the learned combiner and the right answer; a lighter slate is the static analysers; red is a wrong answer or a failed run. In the pilot, blue is the fused arm and slate the static arm. Depth is flat. Structure comes from rules: a 3px blue rule under the masthead, 2px ink rules opening tables, side columns and lanes, 1.5px ink strokes on figure boxes, hairlines between rows. Chrome corners are square throughout; only chart marks take circle, diamond and triangle shapes, as a second encoding. Motion appears only when it reports a real process.

**Key Characteristics:**
- White page, ink type, one blue accent with a fixed meaning.
- The chart is the hero: the Overview opens on the precision–recall plane, not on numbers in tiles.
- Serif for titles, captions, counts and verdict words; sans for UI and prose; system mono only for names and code.
- Three-rule tables, numbered figures, CONSORT and pipeline boxes; squares for lines and runs.
- Small-caps labels for arms, groups, verdicts and column heads.
- Square corners, no drop shadows, no fills beyond tints with assigned meanings.
- Live results are told by state and by sentences: a square's fill says what happened, a line under the button says how it went.

## Colors

A restrained journal palette: ink on white, with exactly one saturated accent and one alarm colour, each bound to a meaning, plus two slates and a few chart greys.

### Primary
- **Journal Blue** (journal-blue): on the study pages, AI models (filled circles on the plane, bars in Figure 2), the learned combiner's diamond on the plane, positive combiner weights, a right answer in the candidate table, a full pass in the matrix, a renamed right line; in the pilot, the fused arm ("Static analysis + test run"). Everywhere: links, pass verdicts, progress fills, the masthead rule, focus rings, the active tab and the "Show the code" summary. It means "the intervention", "right" or "go here".
- **Journal Blue Deep** (journal-blue-deep): the learned combiner's bars (Table 1's F1 bar, Figure 2's recall bars) and its Figure 2 legend key, so it reads apart from the AI models' blue bars; run-button hover.
- **Blue Tint** (blue-tint): the learned combiner's best row in Table 1; a line that calls the function, shown to the agent; the right lines in the Study 2 code list; in the pilot, a place shown to the fused run and lines shown only to the fused arm; text selection.

### Secondary
- **Analyser Slate** (analyser-slate): the static analysers on every study chart: square marks on the plane, their F1 and recall bars, negative combiner weights, the legend swatch and the kind dot in tables. It is a lighter step of slate chosen for colour-vision safety: slate against journal blue failed the check (normal-vision ΔE 11.5, under 15), analyser slate against journal blue passes (colour-vision ΔE 19.7, normal ΔE 21.9). Its square shape carries the distinction a second time.
- **Slate** (slate): the pilot's static arm, "Static analysis only": its run name, its renamed places, its call-graph edges, and the placebo group tag. Pilot only; study charts use analyser slate.

### Tertiary
- **Failure Red** (failure-red): Fail verdicts, run errors, a wrong answer in the candidate table, a line renamed that belongs to another function (filled square), a missed line's dashed border, the count of wrong edits, a matrix cell where no run passed. In the pilot: the failed share of a test track, the "still the old name" count, failed score dots, places never shown or not renamed, unseen locations, and the outline on a score dot whose live run differs. Nowhere else.
- **Red Tint** (red-tint): the fill of a wrong cell in the candidate table, a missed line square, a failed score dot, a place left with the old name, and the unseen-lines list.
- **Red Line** (red-line): the unseen-lines list border and its legend key.

### Neutral
- **Ink** (ink): all headings, body text, figure-box strokes, table and lane rules, the combiner diamond's ring, the tooltip border, pipeline arrows and the zero line of the weights figure.
- **Ink 2** (ink-2): secondary text, ledes, axis lines and titles, finding numerals, static point labels, nav at rest.
- **Ink 3** (ink-3): the plane's two italic notes and F1 contour labels, axis ticks, the hollow grep-baseline triangle and its label, "running" placeholders, not-applicable cells, steps still to do, line numbers.
- **Hair** (hair): default borders of line squares, score dots and places, code-file borders, reveal rules.
- **Mist** (mist): the test-run truth cell in the candidate table, another function's line shown to the agent, pooled table rows, hover on figure boxes and ghost buttons, the disabled run button.
- **Wash** (wash): the lines of a Study 1 function's code that name a candidate, the bound rows of the results matrix (regex rename, exact rename), file-name bars, gap rows in code excerpts, notices, the old lines of a diff.
- **Faint Rule** (faint-rule): the plane's grid, the unfilled ground of F1 and recall bars, row separators in tables and Figure 2.
- **Contour** (contour): the F1 contour curves on the plane.
- **Control Line** (control-line): borders of form controls; the border of a shown, unrenamed line square.
- **Wait Line** (wait-line): the grep baseline's bar fill; in the pilot, the dashed border of a score dot with no run yet.
- **Track** (track): the unfilled ground of progress and test tracks.
- **Page** (page): the ground, and the 2px halo around plane marks.

### Named Rules
**The Assigned Meaning Rule.** On the study pages blue is AI and right, analyser slate is static analysis, red is wrong or failed; in the pilot blue is the fused arm and slate the static arm. Mist and blue tint mean "shown, not yet renamed". No colour is used decoratively, and no new hue enters without a meaning.

**The Shape Twice Rule.** Every resolver kind is encoded by colour and by shape: static analysers are analyser-slate squares, AI models journal-blue circles, the learned combiner a journal-blue diamond with a 2px ink ring, the grep baseline a hollow ink-3 triangle. Plane marks, legend keys and table kind dots repeat the shape; on bars, where shape cannot show, the combiner turns journal-blue-deep.

**The Red Is Evidence Rule.** Red marks only a failed verdict, an error, a wrong answer, a wrong or missed edit, or (in the pilot) a place never shown or left with the old name. It is never used for emphasis or warning chrome.

**The Diff Is Not a Verdict Rule.** Diffs carry no red and no green: old lines are wash with ink-3 strikethrough, new lines are ink 600 on white with a hairline at the left. Red stays reserved for what the tests and the unseen list prove.

## Typography

**Display Font:** Source Serif 4 (with Georgia, serif), self-hosted, OFL
**Body Font:** Source Sans 3 (with -apple-system, Segoe UI, sans-serif), self-hosted, OFL
**Label/Mono Font:** system monospace stack (ui-monospace, SF Mono, Menlo, Consolas)

**Character:** A journal pairing: a sturdy text serif for the parts a reader cites (titles, findings' numerals, captions, counts, verdict words) and a neutral humanist sans for everything operated and narrated. All figures are tabular.

### Hierarchy
- **Display** (600, 44px, 1.05): the pass counts inside the pilot's CONSORT arm boxes. Smaller figure steps: counts in pipeline boxes (600, 30px, 1.1), pilot verdict words (600, 30px, 1), Study 2 verdict words (600, 28px, 1), pilot score counts (600, 26px, 1), live counters on Method (600, 24px), matrix pass counts (600, 18px).
- **Headline** (600, 30px, 1.2, -0.01em; 24px at 720px and below): page titles. The Overview's claim is 32px, capped at 34ch. A Study 1 function title is the qualified name in mono 600 26px; a Study 2 task title reads "Rename X to Y" with the names in mono at 0.86em.
- **Title** (600, 21px, 1.3): the masthead name and pilot section headings; study section headings at 20px; the Overview side column's headings at 19px.
- **Caption** (600, 17px, 1.35): table and figure captions, numbered ("Table 1.", "Figure 2."), with a 13 to 14px sans qualifier in ink-2.
- **Narration** (400, 18px, 1.5; 16px at 720px): the pilot's one sentence per step. On the study pages a live result line is 16px.
- **Body** (400, 15px, 1.5): prose and table cells. Study ledes at 16.5px ink-2, capped at 78ch; findings at 15.5px; matrix at 14px (13.5px compact); candidate cells at 12.5px 600. Measure capped at 62 to 96ch.
- **Label** (700, small caps, 0.03 to 0.05em): run names, arm names, group tags, verdicts, column heads. Study 2 lane names are 700 15px sans.
- **Note** (400, 12.5 to 13.5px): fine print, hints, figure captions under the plane, footnotes, legends, the tooltips, "running" (italic 13px ink-3). The plane's two notes are the one italic serif use (400, 14px, ink-3).
- **Mono** (12 to 13.5px, 1.6 in excerpts): function names, code, file names, commands and diffs.

### Named Rules
**The Serif Is Cited Rule.** Serif sets only what a reader would quote: titles, findings' numerals, captions, counts and verdict words. Controls, nav, narration and prose are sans.

**The Small Capitals Rule.** Categorical labels (run, arm, group, verdict, column head) are small caps in weight 700, never uppercase with tracking.

**The Plain Words First Rule.** Every identifier follows a sentence that explains it: resolvers and conditions are named in words ("Name match (grep)", "Every line with the name"), and a function's code appears only after a lede says what it is.

## Layout

A single centred column capped at 1600px with a fluid gutter (16 to 48px). The Overview is a two-column grid capped at 1440px: the plane column at 1.75fr beside a side column at 1fr (at least 320px), 48px apart. The side column opens with a 2px ink rule and holds the findings, the Study 2 question and the compact matrix. Study and Method pages sit in a 1320px centred column: Study 1 opens with a two-equal-column grid: Figure 1 with Table 1b under it on the left, Table 1 with its note on the right; then Figure 2 at 1.2fr beside Figure 3 at 1fr; a function page sets code at 1fr beside the candidate table at 1.25fr; Study 2 sets the matrix at 1.4fr beside the conditions list at 1fr, and a task's three lanes in equal columns 24px apart; Method's prose runs in two equal columns. Column gaps are 48px, 32px on the function page.

The pilot keeps its layouts: a 1120px story column with the call graph (at most 440px) beside the two runs, stacking at 1000px; the pilot results page as a 600px figure column beside a flexible table column; pilot task pages with the two arms in a shared subgrid.

Spacing runs on a 4px-based scale (4, 8, 12, 16, 24, 32, 48, 64). Sections below the fold are separated by 64px, sections within them by 32 to 48px.

Breakpoints collapse in order:
- **1180px:** the Overview, every study grid, the function page and Method's columns stack to one column; the pipeline turns vertical with its arrows pointing down. The pilot results and pilot method grids stack.
- **1100px:** masthead gaps tighten to 16px and the switch label hides.
- **1000px:** the pilot task page's two arms and the pilot stage stack.
- **720px:** the masthead wraps (name on its own line, nav wrapping) and stops being sticky; titles step to 24px; Study 2 lanes and Figure 2 rows stack; Figure 3's name column narrows to 130px; F1 bars shrink to 48px; study tables scroll sideways; the plane scrolls sideways inside its figure at a 640px minimum, with a phone-only hint in the caption (and one above the candidate table); in the pilot the CONSORT spine recentres, scoreboard rows stack and the code columns stack.

Wide tables scroll horizontally inside their own container rather than squeezing.

## Elevation & Depth

Flat. There are no drop shadows and no layered surfaces; the masthead is sticky but separated only by its 3px blue rule, and the plane's tooltip floats on a 1px ink border, not a shadow. Depth and grouping come from rules and tints with assigned meanings. The only box-shadow in the system is an inset 1.5px underline on highlighted marks in code (ink-3 under the function's name, red under an unseen name), also used for candidate names in a Study 1 function's code; it is a text-marking device, not elevation.

### Named Rules
**The Rules Not Shadows Rule.** Group with a rule or a hairline border; never lift with a shadow.

## Shapes

Square corners on all chrome (0px), including buttons, inputs, tooltips, line squares, score dots, step markers, place squares and figure boxes. The one exception is the 2px radius on the focus outline. Chart marks are the only non-square forms, and their shape is data: square for static analysers, circle for AI models, diamond for the learned combiner, triangle for the grep baseline; each mark on the plane wears a 2px white halo. Stroke weight encodes role: 3px for the masthead, active tab and pilot call-graph edges; 2.5px for the ground-truth box in the pipeline; 2px for table top/bottom, side columns, lanes and the combiner's ring; 1.5px for figure boxes, pipeline arrows and the borders of squares, dots and places; 1px for controls, hairlines, tooltips and the plane's axes. Dashed borders mean "not shown" or "not yet known": a line not shown to the agent, a missed line (dashed red), and in the pilot an unrun score dot, a place hidden from a run, a CONSORT exclusion box.

## Components

### Buttons
Solid, square and few.
- **Shape:** square (0px).
- **Run (primary):** journal blue fill, white 600 15px sans, 11px 18px padding; hover deepens to journal-blue-deep over 0.15s; disabled is a mist fill with a control-line border, ink-2 text and a progress cursor while a run is in flight. It is the one live action per page: "Try one function live" (Overview), "Ask gpt-oss-120b now", "Run gpt-oss-120b now, with all three contexts", "Record the truth again, now"; in the pilot, the step action. While running its label says what is happening ("Asking gpt-oss-120b…", "Running the tests…"). A 13px ink-2 fine line beside or under it says what the button will do and how long it takes, or why the AI is off.
- **Ghost (secondary):** white with a 1px control-line border, ink 600 14px sans, 11px 16px padding; hover fills mist over 0.15s; disabled drops to ink-3 text. Pilot only: Run all, Play all steps, Stop after this task, Next task.
- **Busy:** while any live run is in flight every live button and the AI model switch lock.
- **Focus:** 2px journal blue outline at 2px offset (global).
- **Sort (in pilot table heads):** the small-caps column-head label with a drawn 9px chevron SVG at 35% opacity, full opacity when sorted, rotated for descending.

### Segmented control
- **Style:** options joined in one 1px control-line frame, separated by 1px dividers; white ground, 14px ink text, 6px 14px padding; 13px with 4px 12px in the masthead.
- **State:** the pressed option inverts to ink fill with white text. Disabled options turn ink-3.
- **Uses:** the masthead AI model switch; Study 1's function filter ("Static analysis misses a call", "A name is shared", "All"); pilot filters.

### Inputs / Fields
- **Style:** 1px control-line border, square, white ground, 14px text, 6px 10px padding; select at least 180px, search at least 260px; full-width at 720px. Pilot pages only.
- **Focus:** the global 2px blue outline.

### Navigation
- **Masthead:** 60px sticky bar, white, closed by a 3px journal blue rule. "TraceWeave" in 21px serif left; tabs in 15px ink-2 sans: Overview, "Study 1: finding calls", "Study 2: the AI agent", Method. The current tab is blue, weight 700, with a 3px blue underline that sits on the masthead rule; pilot routes mark Method current. The status slot right holds the "AI model" label and a segmented switch of gpt-oss-20b / gpt-oss-120b / qwen3.8-27b on the Overview, study and Method routes (an unavailable model disables; when none is ready a 12px ink-2 note of at most 22ch gives the reason). Pilot routes show the pilot's editor switch instead.
- **Crumb:** 14px ink-2 link above a study, function or task title ("Overview", "Study 1 / click").

### Precision–recall plane (signature)
Figure 1, the Overview's hero and Study 1's opening figure. Recall on x (0.4 to 1), precision on y (0.2 to 1), ticks every 0.2 in 12px ink-3 on a faint-rule grid, 1px ink-2 axes, axis titles in 600 13px ink-2 that say what each axis means in words. Three F1 contours (0.7, 0.8, 0.9) in 1px contour strokes, each labelled "F1 0.8" in 11.5px ink-3 at its upper end. On the large plane only, two italic serif notes (14px, ink-3) name the regions: "precise, but blind" near the static analysers and "sees more, and guesses" near the AI models. Contours, their labels and these notes are the only annotations. Marks follow the Shape Twice Rule (static 12px square, AI 6.5px-radius circle, combiner 20px diamond with 2px ink ring, baseline 14px hollow triangle in 1.5px ink-3), each named beside it in 600 13.5px (static in ink-2, the combiner 15px blue, the baseline 400 ink-3). A legend of the four shapes sits above the plot; a 13px ink-2 figcaption under it gives the item count, explains the curves and links to Study 1. Each mark is a link to its own row in Table 1 (#/study1?focus=r-<id>), with a 16px hit circle that tints blue at 8% on hover and takes a 2px blue ring on keyboard focus. On Study 1 the plane is capped at 640px. On phones it scrolls sideways at a 640px minimum width.

### Tooltip
Used by the plane and by Study 2's line squares. A 260px white box with a 1px ink border, square, 8px 10px padding, 12.5px/1.4 text: the resolver in ink bold, then precision, recall and F1 with ink bold figures, then a sentence of real calls found, claimed and missed in ink-2. On a line square it gives the file, line, enclosing function and source. It sits above the hovered or focused mark, clamped inside its figure, appears and hides instantly (no transition), ignores the pointer and is announced as status.

### Findings
A numbered list in the Overview's side column under a 19px serif "Findings": three plain sentences at 15.5px/1.5, 12px apart, numerals in serif 600 15px ink-2, the figure that carries each finding in bold. No tiles, no icons.

### Results matrix (signature)
Table 2: editors down, contexts across ("every line with the name (grep)", "static analysis", "the test run"). Each cell is "N of M" with N in 18px serif 600: blue when every task passed, red when none did, ink otherwise; "N of M" appears only when a cell is complete; a cell with runs still out reads "N passed · K still running", N in 18px serif ink-2 and the remainder in 12px ink-3; a cell with no runs yet reads "running" in italic 13px ink-3. The regex rename and exact rename rows are bound rows on wash spanning the three contexts with a small note. Compact (13.5px) in the Overview's side column.

### Leaderboard with F1 bars
Table 1 and Table 1b in three-rule form. Each resolver row starts with a 10px kind dot in its mark shape and colour; the F1 cell holds a 90px by 8px bar on faint-rule (blue for AI, journal-blue-deep for the combiner, analyser slate for static, wait-line for the baseline) before the bold figure. The combiner's row takes blue tint; the row a plane point links to is outlined in 2px blue, inset 2px. Table 1b sets precision / recall per project, item counts under the heads in 400 ink-3.

### Recall by category (Figure 2)
Rows separated by faint-rule hairlines: a 230px name column (600 14.5px name, 12.5px ink-2 count) beside three thin bars (7px, at most 260px), one per resolver in its kind colour, each followed by its figure in 12.5px ink-2. A legend of 12px keys sits above in each kind's shape: an analyser-slate square, a blue circle, and a journal-blue-deep rotated square for the combiner.

### Combiner weights (Figure 3)
Diverging bars from a 1px ink centre line, 10px tall: negative weights extend left in analyser slate, positive right in blue, scaled to the largest weight. A 210px feature-name column at left, the signed value right-aligned in 12.5px ink-2. A fine line under it says how to read the direction.

### Function explorer
Study 1's "Every function in the sample", filtered by a segmented control, then a count sentence. A three-rule table of clickable rows: the qualified name as a link with the project in 12px ink-3 sans, counts, and "N of M" right for static, the chosen AI model and the combiner; a fully right count turns blue 700.

### Candidate table
On a Study 1 function page, beside the code. One row per candidate (mono 600 12.5px name over an 11.5px ink-3 note of how it is written and whether the name is shared), then compact centred cells: the test-run truth on mist in ink 700, then each resolver's "calls" or "no", blue when right, red on red tint when wrong, an ink-3 dash when it gave no answer, and a Live column filled by the "Ask" button. The caption states the key ("blue: right, red: wrong"), and a fine line above the table repeats it in words, with a phone-only hint to scroll sideways. The result line under the button is 16px: "gpt-oss-120b answered in N s and got K of M right against the recorded calls", with the model's reasoning in a collapsible.

### Code with marked names
The function page's code uses the code excerpt: a file bar over numbered lines; lines that name a candidate get an ink 700 line number and a wash ground, and each candidate name is marked in mist with an ink-3 underline. The exact prompt every model received sits behind a collapsible.

### Conditions list
A definition list opened by a 2px ink rule: each context's name in 700 14.5px, its definition in 14px ink-2.

### Line squares (signature)
Study 2's lanes: one 18px square per line that contains the name, 4px apart, 1.5px border, square, in three equal lanes (one per context) each opened by a 2px ink rule and a 700 15px name. States:
- **shown-right** (a line that calls the function, shown): blue tint fill with a 2px blue border.
- **shown** (another function's line, shown) and **kept** (shown and rightly left): mist fill, control-line border.
- **unshown** (not shown to the agent): dashed light grey border on white.
- **done** (renamed, rightly): solid journal blue.
- **wrongedit** (renamed, but belongs to another function): solid failure red.
- **missed** (a right line left unrenamed): red tint with a 1.5px dashed red border.
Each square is focusable (an image with a label naming its line) and shows the shared tooltip on hover or focus; keyboard focus is a 2px blue outline at 2px offset. A key of the six states sits above the lanes. Under each lane a 14.5px ink-2 caption ("Shown 3 of 14 lines", "Renamed 3 of 3 right lines and 1 line of another function"), a progress track while tests run, then the verdict word in 28px serif (blue Pass, red Fail) with "N of M tests pass · recorded run" or "· just now". Squares change colour over 0.4s.

### Pipeline figure (signature)
Figure 4 on Method: flow boxes joined by arrows, left to right. Each box is 1.5px ink, 12px 14px padding, a 12.5px ink-2 line above and below a 30px serif count; the ground-truth box takes a 2.5px border. Arrows are 1.5px ink lines with a drawn 8px head, 36px long; the last stage is a stack of two boxes that link to Study 1 and Study 2 and fill mist on hover. Under it the run button "Record the truth again, now" and, while it runs, live counters: "N of M tests run", "N calls into click", "N distinct calling lines", each figure in 24px serif inside its phrase, over a progress track, then a 16px result sentence.

### Show the code (disclosure)
Under a hairline, a blue 600 "Show the code" summary. On a Study 2 task page it holds the list of every line with the name: location in 12px mono ink-3, enclosing function in ink-2, the source with the name marked, right lines on blue tint. In the pilot it holds the diffs, the unseen list and the model's reasoning.

### Three-rule table (signature)
Journal table form: caption above in serif 17px; 2px ink rule over the head, 1px ink rule under it, 2px ink rule closing the body; faint-rule row separators. Column heads are small caps 700, right-aligned for numbers, first column left. Pooled rows take a mist ground and bold weight. Clickable rows tint faintly on hover and turn their link blue. Table notes follow in 13.5px ink-2.

### Pilot components
The pilot routes keep these, unchanged:
- **CONSORT flow:** a single spine of 1.5px ink connectors through 300px boxes with a serif count; exclusions branch right into 252px dashed boxes; two 140px arm boxes carry the small-caps arm name in its colour, a 44px serif count and "of N pass". Every box is a link: hover fills mist, a 12px blue underlined hint names where it goes.
- **Arm column and outcome entry:** a 2px ink rule and small-caps arm name; entries of kind, a 30px serif verdict word and counts; a live re-run arrives with a 0.7s rise-and-fade from mist.
- **Story head and task line:** the question as a 30px serif H1 with a 17px ink-2 lede; "Rename X to X_v2" at 24px with an inline task picker.
- **Scoreboard:** two rows, one per run: a small-caps run name, 17 square 22px dot buttons 6px apart, and a 26px serif count with "of 17 renames worked". Dots: blue worked, red tint with red border failed, dashed wait-line not run, 1.5px ink outline at 2px offset ran live, 2px red outline differs from the recording, scaled to 1.25 when selected.
- **Stepper:** four 24px numbered square markers (todo ink-3 outline, done filled ink-2, now filled blue) with Play all (ghost) and the step action.
- **Narration:** one 18px sentence, at most 80ch, at least three lines tall, announced politely.
- **Call graph:** callers routed at 0 and 45 degrees into a 1.5px ink target box; 3px edges in slate (found by static analysis) or blue (found only by the test run), drawing in over 0.8s; short names in mono 600 12.5px; at most six callers.
- **Place squares:** one 36px by 26px square per line naming the function: unknown dashed hair, hidden dashed red, shown 2px in the lane colour over mist or blue tint, done solid slate or blue, missed red tint dashed red, skipped red tint solid red; fading over 0.45s.
- **Test row, diff, code excerpt and unseen-lines list:** 8px tracks blue then red; diffs in wash strikethrough and ink 600; numbered excerpts with fused-only lines in blue tint; unseen lines on red tint in a red-line border.

### Progress tracks
Square 8px tracks on the track ground, blue for passed then red for failed; widths move linearly over 0.2s.

### Motion
Motion reports a process and nothing else. Line squares and score dots change colour over 0.4s, pilot place squares over 0.45s, all on the system ease (cubic-bezier(.16, 1, .3, 1)); tracks widen linearly over 0.2s; button hovers fill over 0.15s. Tooltips appear and hide instantly. The global reduced-motion rule removes every animation and transition.

## Do's and Don'ts

### Do:
- **Do** make the chart the hero: a page about results opens on its figure (the precision–recall plane on the Overview), with findings beside it, not above it.
- **Do** bind every colour to its meaning: on the study pages analyser slate for static analysers, journal blue for AI models, the combiner and right answers, failure red for wrong answers and failed runs; in the pilot slate for the static arm and blue for the fused arm.
- **Do** encode each resolver kind twice, by colour and shape: slate square, blue circle, blue diamond with an ink ring, hollow ink-3 triangle.
- **Do** keep chart annotation to the faint F1 contours, their labels and the plane's two italic notes; grids stay faint-rule and axes 1px ink-2.
- **Do** write findings as numbered plain sentences, with the figure that carries each one in bold.
- **Do** show results that are not in yet as "running", or "N passed · K still running" for a partial cell; "N of M" only when a cell is complete; never fill a cell with an estimate.
- **Do** set tables as three-rule tables: 2px ink top, 1px ink under the head, 2px ink closing the body; number every table and figure in its caption.
- **Do** set run, arm, group, verdict and column-head labels in small caps at weight 700.
- **Do** keep serif for titles, findings' numerals, captions, counts and verdict words, and use tabular figures everywhere.
- **Do** give each live button a fine line saying what it will do and how long it takes, and report the outcome as one sentence under it.
- **Do** animate only what reports a real process: squares and dots changing colour (0.4 to 0.45s), tracks filling (0.2s), and in the pilot edges drawing (0.8s); the global reduced-motion rule stops all of it.

### Don't:
- **Don't** add hero-metric strips, KPI tiles or stat cards; a count is a serif figure inside a sentence ("3 of 9", "9 of 17 renames worked"). Counters appear only while a live run is reporting, each inside its phrase.
- **Don't** let code lead: on Study 2 and the pilot, code, diffs and the line list sit behind "Show the code", and every prompt sits behind a collapsible; the Study 1 function page shows its code only after a lede sentence says what it is.
- **Don't** invent results: a cell without runs reads "running", never a placeholder number, and a partial cell never shows a denominator.
- **Don't** introduce rounded corners or drop shadows on chrome; the only non-square forms are chart marks whose shape is data.
- **Don't** use red for emphasis, warnings or decoration, and never on diffs; red is only for fails, wrong answers and missed or unseen lines.
- **Don't** set labels in tracked uppercase; use small caps.
- **Don't** use glyph or emoji icons; marks, arrows and the sort chevron are drawn in SVG or CSS.
- **Don't** add hues outside the palette; a new state needs an assigned meaning first.
