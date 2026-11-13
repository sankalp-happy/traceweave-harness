# Pilot: gpt-oss-20b with whole-line edits (2026-10-11)

78 of 280 rows, run before the edit format changed. The model had to retype
each edited line in full, indentation included. 33 of the 50 failures were
files Python could not parse (wrong indentation, or the excerpt's `  695| `
line prefix copied into the edit), which has nothing to do with the context
under test. Control tasks also favoured the run sent first (8 to 1 on
identical prompts), and the static run was always sent first.

Because of that, the prompt now asks for `{path, line, old, new}` edits. These
rows are kept as they were recorded and are left out of every report and page:
`tw.py ui` and `tw.py report results/*.jsonl` read only `results/*.jsonl`.
