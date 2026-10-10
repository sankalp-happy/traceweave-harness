---
name: TraceWeave harness
description: A paired, placebo-controlled experiment reported the way a clinical trial is reported.
colors:
  ink: "#1b1b1b"
  ink-2: "#4a5057"
  ink-3: "#6b7279"
  hair: "#d3d9df"
  journal-blue: "#0b4f8a"
  journal-blue-deep: "#083c6a"
  blue-tint: "#dce8f4"
  slate: "#56616b"
  failure-red: "#b23a2e"
  red-tint: "#f7e5e2"
  red-line: "#e7c7c2"
  mist: "#e9eef3"
  wash: "#f7f9fb"
  control-line: "#9aa3ab"
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
  body:
    fontFamily: "Source Sans 3, -apple-system, Segoe UI, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.5
    fontFeature: "\"tnum\""
  label:
    fontFamily: "Source Sans 3, -apple-system, Segoe UI, sans-serif"
    fontSize: "14px"
    fontWeight: 700
    letterSpacing: "0.04em"
    fontFeature: "\"smcp\""
  note:
    fontFamily: "Source Sans 3, -apple-system, Segoe UI, sans-serif"
    fontSize: "12.5px"
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
  unseen-list:
    backgroundColor: "{colors.red-tint}"
    textColor: "{colors.ink}"
    typography: "{typography.mono}"
    padding: "6px 10px"
  masthead:
    backgroundColor: "{colors.page}"
    textColor: "{colors.ink-2}"
    height: "60px"
---

# Design System: TraceWeave harness

## Overview

**Creative North Star: "The Clinical Trial Report"**

The surface is set like a results section in a medical journal: a white page, near-black ink, one journal blue, and figures whose every number links to the rows behind it. Allocation is drawn as a CONSORT flow in 1.5px ink boxes; outcomes sit in three-rule tables; arms are named in small capitals. The register is a printed report someone can audit, not a product dashboard.

Density is that of a journal page read on a 13 to 15 inch laptop: 15px sans body with tabular figures, 12.5px notes, serif reserved for titles, captions and the headline figures. Colour carries meaning and nothing else. Blue is the fused (intervention) arm and the link; slate is the static arm; red appears only where something failed or an arm could not see a line. Everything held equal between arms recedes into ink and hairlines.

Depth is flat. Structure comes from rules: a 3px blue rule under the masthead, 2px ink rules opening and closing tables, 1.5px ink strokes on figure boxes, hairlines between rows. Corners are square throughout.

**Key Characteristics:**
- White page, ink type, one blue accent with a fixed meaning.
- Serif for titles, captions and figures; sans for UI and prose; system mono only for code.
- Three-rule tables and CONSORT boxes as the primary structures.
- Small-caps labels for arms, groups, verdicts and column heads.
- Square corners, no drop shadows, no fills beyond tints with assigned meanings.

## Colors

A restrained journal palette: ink on white, with exactly one saturated accent and one alarm colour, each bound to a meaning.

### Primary
- **Journal Blue** (journal-blue): the fused arm, links, pass verdicts, the masthead rule, focus rings, the active tab and the run button. It means "the intervention" or "go here".
- **Journal Blue Deep** (journal-blue-deep): run-button hover only.
- **Blue Tint** (blue-tint): lines shown only to the fused arm in code excerpts, and text selection.

### Secondary
- **Slate** (slate): the static arm label and the placebo group tag; the comparison arm, deliberately quieter than blue.

### Tertiary
- **Failure Red** (failure-red): fail verdicts, run errors, and the location of lines an arm could not see. Nowhere else.
- **Red Tint** (red-tint) with **Red Line** (red-line): the background and border of the unseen-lines list and its legend key.

### Neutral
- **Ink** (ink): all headings, body text, CONSORT strokes and table rules.
- **Ink 2** (ink-2): secondary text, captions' qualifiers, nav at rest, counts.
- **Ink 3** (ink-3): line numbers, placeholders, the source witness line, the underline under the function's name.
- **Hair** (hair): hairline borders on code files, the live-run band, the witness rule.
- **Mist** (mist): pooled table rows, hover on CONSORT figures, and the highlight on the function's name in code.
- **Wash** (wash): file-name bars, gap rows in code excerpts, and notices.
- **Control Line** (control-line): borders of form controls (segmented buttons, select, search).
- **Page** (page): the ground.

### Named Rules
**The Assigned Meaning Rule.** Blue is the fused arm and navigation; slate is the static arm; red is failure or an unseen line. No colour is used decoratively, and no new hue enters without a meaning.

**The Red Is Evidence Rule.** Red marks only a failed verdict, an error, or a line the arm never saw. It is never used for emphasis or warning chrome.

## Typography

**Display Font:** Source Serif 4 (with Georgia, serif), self-hosted, OFL
**Body Font:** Source Sans 3 (with -apple-system, Segoe UI, sans-serif), self-hosted, OFL
**Label/Mono Font:** system monospace stack (ui-monospace, SF Mono, Menlo, Consolas)

**Character:** A journal pairing: a sturdy text serif for the parts a reader cites (titles, captions, the figures) and a neutral humanist sans for everything operated. All figures are tabular.

### Hierarchy
- **Display** (600, 44px, 1.05): the pass counts inside the two CONSORT arm boxes. Smaller figure steps: verdict words in task arms (600, 30px, 1) and counts in CONSORT boxes (600, 24px, 1.2).
- **Headline** (600, 30px, 1.2, -0.01em; 24px at 720px and below): page titles. On a task page the title is the qualified name in mono (600, 26px; 20px at 720px) with "renamed to" in serif 400.
- **Title** (600, 21px, 1.3): section headings and the masthead product name.
- **Caption** (600, 17px, 1.35): table captions and figure captions, with a 14px sans qualifier in ink-2.
- **Body** (400, 15px, 1.5): prose and table cells. Lede at 16px, task summary at 17px/1.55. Measure capped at 62 to 72ch.
- **Label** (700, small caps, 0.03 to 0.05em): arm names, group tags, pass/fail verdicts, table column heads.
- **Note** (400, 12.5 to 13.5px): CONSORT exclusions, hints, footnotes, table notes, legends.
- **Mono** (12.5 to 13.5px, 1.6 in excerpts): code, file names, task identifiers, commands.

### Named Rules
**The Serif Is Cited Rule.** Serif sets only what a reader would quote: titles, captions, and headline figures. Controls, nav and prose are sans.

**The Small Capitals Rule.** Categorical labels (arm, group, verdict, column head) are small caps in weight 700, never uppercase with tracking.

## Layout

A single centred column capped at 1600px with a fluid gutter (16 to 48px). The report page is a two-column grid: a 600px figure column (title, lede, CONSORT flow) beside a flexible table column, with 24px row gap and 48px column gap. The method page is two equal columns. A task page sets the two arms side by side in a shared subgrid so each block (outcome, unseen lines, excerpts) aligns straight across.

Spacing runs on a 4px-based scale (4, 8, 12, 16, 24, 32, 48, 64). Sections below the fold are separated by 64px, sections within them by 48px.

Breakpoints collapse in order:
- **1180px:** report and method grids drop to one column.
- **1000px:** the task page's two arms stack.
- **720px:** the masthead wraps (name on its own line, status hidden), titles step down, the CONSORT spine recentres at 50% with connectors turned vertical and boxes full-width, filters and inputs go full-width.

Wide tables scroll horizontally inside their own container rather than squeezing.

## Elevation & Depth

Flat. There are no drop shadows and no layered surfaces; the masthead is sticky but separated only by its 3px blue rule. Depth and grouping come from rules and tints with assigned meanings. The only box-shadow in the system is an inset 1.5px underline on highlighted marks in code (ink-3 under the function's name, red under an unseen name), which is a text-marking device, not elevation.

### Named Rules
**The Rules Not Shadows Rule.** Group with a rule or a hairline border; never lift with a shadow.

## Shapes

Square corners everywhere (0px), including buttons, inputs and the segmented control. The one exception is the 2px radius on the focus outline. Stroke weight encodes role: 3px for the masthead and active tab, 2px for table top/bottom and arm-column heads, 1.5px for CONSORT boxes and connectors, 1px for controls and hairlines, 1px dashed for CONSORT exclusion boxes.

## Components

### Buttons
Solid, square and few.
- **Shape:** square (0px).
- **Run (primary):** journal blue fill, white 600 15px sans, 11px 18px padding; hover deepens to journal-blue-deep over 0.15s; disabled is a pale blue-grey with a progress cursor while a run is in flight.
- **Focus:** 2px journal blue outline at 2px offset (global).
- **Sort (in table heads):** inherits the small-caps column-head label, with a drawn 9px chevron SVG at 35% opacity, full opacity when sorted, rotated for descending.

### Segmented control
- **Style:** options joined in one 1px control-line frame, separated by 1px dividers; white ground, 14px ink text, 6px 14px padding.
- **State:** the pressed option inverts to ink fill with white text.

### Inputs / Fields
- **Style:** 1px control-line border, square, white ground, 14px text, 6px 10px padding; select at least 180px, search at least 260px; full-width at 720px.
- **Labels:** 13px ink-2 above the control, 4px gap.
- **Focus:** the global 2px blue outline.

### Navigation
- **Masthead:** 60px sticky bar, white, closed by a 3px journal blue rule. Serif product name left; tabs in 15px ink-2 sans; the current tab is blue, weight 700, with a 3px blue underline that sits on the masthead rule. Run status right in 13px ink-2, hidden at 720px.
- **Crumb:** 14px ink-2 link above a task title.

### Three-rule table (signature)
Journal table form: caption above in serif 17px; 2px ink rule over the head, 1px ink rule under it, 2px ink rule closing the body; faint row separators. Column heads are small caps 700, right-aligned for numbers, first column left. Pooled rows take a mist ground and bold weight. Clickable rows tint faintly on hover and turn their link blue. Footnotes and a table note follow in 13 to 13.5px ink-2; a source witness line (command, row count, run window) closes under a hairline.

### CONSORT flow (signature)
Allocation drawn as figures that are also navigation. A single vertical spine of 1.5px ink connectors runs through 300px boxes outlined in 1.5px ink, with a serif count; exclusions branch right into 252px dashed boxes with itemised reasons. The flow splits into two 140px arm boxes carrying the small-caps arm name in its arm colour, a 44px serif count, and "of N pass". Every box is a link: hover fills with mist, and a 12 to 12.5px blue underlined hint names where it goes.

### Arm column and outcome entry
Each arm column opens with a 2px ink rule and a small-caps arm name. An outcome entry is a three-column row: kind (12.5px ink-2), verdict word in 30px serif (blue pass, red fail), and counts. A live re-run appends an entry that arrives with a 0.7s rise-and-fade from mist (cubic-bezier(.16, 1, .3, 1)); reduced motion removes it.

### Code excerpt
A file bar (mono 12.5px ink-2 on wash) over a two-column grid of right-aligned ink-3 line numbers behind a hairline, and unwrapped code at 12.5px/1.6. Lines shown only to the fused arm take blue-tint with bold blue line numbers; the function's name is marked in mist with an ink-3 underline; elided ranges are wash rows. A legend of 12px swatches explains each mark.

### Unseen-lines list
A mono list on red-tint inside a red-line border, each row the location in failure red and the source line in ink, with the name marked by a red underline. It is the only red surface in the system.

## Do's and Don'ts

### Do:
- **Do** bind every colour to its meaning: journal blue for the fused arm and links, slate for the static arm, failure red only for failure and unseen lines.
- **Do** set tables as three-rule tables: 2px ink top, 1px ink under the head, 2px ink closing the body.
- **Do** draw allocation and flow as CONSORT boxes in 1.5px ink with square corners, and make each figure a link to its rows.
- **Do** set arm, group, verdict and column-head labels in small caps at weight 700.
- **Do** keep serif for titles, captions and headline figures, and use tabular figures everywhere.
- **Do** close evidence with a source line naming the command and rows that produce it.

### Don't:
- **Don't** introduce rounded corners or drop shadows, and don't summarise results as KPI tiles or stat cards; report them as figures and tables.
- **Don't** use red for emphasis, warnings or decoration.
- **Don't** set labels in tracked uppercase; use small caps.
- **Don't** use glyph or emoji icons; the only icon is a drawn inline SVG chevron for sort direction.
- **Don't** add hues outside the palette; a new state needs an assigned meaning first.
