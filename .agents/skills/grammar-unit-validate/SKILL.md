---
name: grammar-unit-validate
description: Validate exactly one imported English Grammar in Use Unit against the source PDF, structured package, SQLite records, answer-key links, API response, and rendered reader. Use after creating, rebuilding, or publishing a grammar Unit.
---

# Grammar Unit Validate

Validate one Unit per invocation. This skill is the mandatory gate used by `$grammar-unit-import`; it does not authorize importing another Unit or changing unrelated application code.

## Read first

- `docs/grammar-content-architecture.md`
- `docs/grammar-unit-import-lessons.md`
- `storage/grammar/import-packages/unit-NNN.json`
- `schemas/grammar-unit.schema.json`

## Validation gate

All phases must pass for the same Unit number.

### 1. Source fidelity

Inspect the complete body and exercise pages from the configured PDF as rendered images. Also use cached text and coordinates for searching, but do not treat extraction order as layout truth.

Compare the package and page line by line:

- Unit title, grammar point, every labeled body section, and each section's lead sentence.
- Every exercise number, instruction, example, question number, complete prompt, parenthesized cue, word bank, option, and answer slot.
- Every meaningful illustration and its crop. Check that media is attached to the correct section or exercise and does not omit labels or explanatory text.
- Reconstruct inline questions in segment order. The visible sequence must match the printed prompt; no `cue` or text may disappear behind an input slot.

### 2. Deterministic package and database checks

Run from the project root:

```bash
.venv/bin/python .agents/skills/grammar-unit-validate/scripts/validate_unit.py --unit N
```

For a published Unit, add `--require-status published`. The command must report `PASS`. It checks schema validation, source-cache assets, package/database counts, exact question content and slots, media hashes, solutions, answer-key foreign keys, SQLite integrity, and foreign keys.

Then run:

```bash
.venv/bin/python scripts/import-grammar-answer-key.py --audit-only
```

The global answer audit must retain zero empty answers, duplicate keys, and hash mismatches.

### 3. Reader and API checks

- Confirm `/api/grammar/library/units/N` returns 200 locally. If Tailnet access is part of the active deployment, confirm it there too.
- Confirm the public payload contains only stable draft keys and printed examples, not standard solution text.
- Open `/grammar?unit=N&section=reading` and `/grammar?unit=N&section=exercise` in a browser.
- Visually compare both views with the source pages. Test directory selection, both tabs, images, every supported question renderer, keyboard focus, and a refresh with a draft answer.
- Run frontend lint/build only when shared frontend code or renderers changed; data-only imports do not require rebuilding identical code for every Unit.

## Result

Return `PASS` only if every required phase passes. Report the source pages, package and database counts, answer-link count, API status, browser review, and any checks not performed.

On failure, return `FAIL`, identify the exact Unit/exercise/question or body section, and do not permit the next Unit to start. Fix reusable logic rather than adding Unit-specific UI. Once the cause is understood and resolved, append it to `docs/grammar-unit-import-lessons.md` with a prevention check.
