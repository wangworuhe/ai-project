---
name: grammar-unit-import
description: Import one or more English Grammar in Use Units into this project's structured SQLite reader. Use when the user asks to add, parse, rebuild, or publish grammar Unit content; process requested Units sequentially and validate each Unit before continuing.
---

# Grammar Unit Import

Import source-faithful Unit content through the project's shared schema and importer. Never create a Unit-specific page, renderer branch, HTML fragment, or CSS payload.

## Required context

Before editing or importing, read:

- `docs/grammar-content-architecture.md`
- `docs/grammar-unit-import-lessons.md`
- `.agents/skills/grammar-unit-validate/SKILL.md`
- `schemas/grammar-unit.schema.json`

Use the completed cache under `storage/grammar/source-cache/` and the configured source PDF. Treat the PDF page image as the layout authority, extracted text as a searchable aid, and `grammar_answer_key_entries` as the answer authority.

## Unit transaction

Work on exactly one Unit at a time, in ascending requested order:

1. Identify its body page, exercise page, title, sections, exercises, examples, cues, answer slots, and images from the source. Inspect both full-page renders visually.
2. Create or update `storage/grammar/import-packages/unit-NNN.json`. Preserve the complete printed wording and order. Store semantic content and limited layout hints, never arbitrary HTML or CSS.
3. Match every non-example question to the answer key by edition, Unit number, exercise number, and item number. Do not invent missing answers. Complex multi-slot answers require reviewed slot mappings when automatic splitting is unsafe.
4. Run `.venv/bin/python scripts/import-grammar-unit.py --unit N --validate-only`. Fix every failure before writing the database.
5. Back up `storage/database/database.db`, then import the Unit. Use `--replace` only when rebuilding an existing Unit. Preserve the intended status; normally validate as `reviewed` before publishing.
6. Invoke `$grammar-unit-validate` for this Unit. Do not start another requested Unit unless it returns a complete pass.
7. If validation exposes a new failure pattern, fix the reusable parser, schema, importer, renderer, or validator rather than adding a Unit-specific exception. Append the symptom, cause, fix, and prevention rule to `docs/grammar-unit-import-lessons.md`.

For multiple Units, repeat the complete transaction for Unit N before starting Unit N+1. On any unresolved failure, stop the batch, leave later Units untouched, and report the last passed Unit and the current blocker.

## Completion report

For each Unit, report source pages, section/exercise/question/slot/media counts, answer-link results, package path, database status, and validation outcome. Distinguish automated checks from manual visual review.
