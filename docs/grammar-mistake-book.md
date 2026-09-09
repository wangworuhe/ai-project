# Grammar mistake book

The mistake book is a projection of immutable rows in
`grammar_attempt_answers`. It never edits or replaces formal grading evidence.

## Inclusion and mastery rules

- Only deterministic `incorrect` outcomes create or increment a mistake.
- `unanswered`, `incomplete`, and `needs_review` do not count as wrong answers.
- A later correct answer changes `reviewing` to `improving`.
- Two consecutive correct answers after the latest mistake change the status to
  `mastered`.
- Any later incorrect answer increments `wrong_count`, resets the correct streak,
  and returns the item to `reviewing`.
- The latest incorrect submission snapshot supplies the displayed question,
  user answer, and accepted variants, so a later content import cannot rewrite
  historical evidence.

## Storage

`grammar_mistake_entries` has one row per profile and stable integer
`question_id`. It points to both the latest definitive attempt answer and the
latest incorrect attempt answer. All practice history remains available through
the attempt tables.

The pre-existing `grammar_mistakes` and `grammar_attempts` tables are legacy
prototype data. They are preserved for safety but are not read or written by the
structured reader.

At application startup, formal attempt answers are replayed idempotently. This
backfills submissions made before the mistake-book table existed without
duplicating `wrong_count`.

## API

`GET /api/grammar/library/mistakes?status=active`

Supported status filters are `active`, `all`, `reviewing`, `improving`, and
`mastered`. An optional positive integer `unit` parameter narrows the returned
items to one Unit.
