# Grammar AI review integration

Deterministic grading remains the only authority for `correct` and `incorrect` outcomes. AI review is an asynchronous, optional explanation layer: submission writes immutable attempt evidence and one or more `grammar_ai_review_jobs` in the same SQLite transaction, while a separate runner sends jobs to Mecha and validates results before exposing them in the mistake book.

## Contract and lifecycle

- Input: `schemas/grammar-explanation-input.schema.json`
- Output: `schemas/grammar-explanation-output.schema.json`
- Worker: `grammar-mistake-explainer` by default
- Prompt: `grammar-mistake-explainer/v1`, stored in `prompts/grammar-mistake-explainer-v1.txt`
- Batch size: at most 20 answers
- States: `queued` → `dispatched` → `completed`, `failed`, or `invalid_result`
- Idempotency: every batch has a stable `dedup_key`; startup backfill can run repeatedly.
- Retry: a failed batch is preserved and a new queued job receives a new request ID and deduplication key.

Only `incorrect` and `needs_review` answers are sent. The result must contain every requested immutable `attempt_answer_id` exactly once, preserve the submitted slot set, satisfy JSON Schema, and echo the request ID. For deterministic `incorrect` answers, `review_decision` must be `not_applicable`; an AI response cannot change the grade.

## Configuration

Set these in the project `.env` after Mecha is ready:

```dotenv
MECHA_BASE_URL=http://127.0.0.1:21212
MECHA_API_KEY=replace-with-the-Mecha-bearer-token
GRAMMAR_AI_REVIEW_WORKER=grammar-mistake-explainer
GRAMMAR_AI_REVIEW_BATCH_SIZE=20
```

With no `MECHA_BASE_URL`, the runner deliberately stays idle and queued jobs remain durable. Run one cycle manually with:

```sh
.venv/bin/python scripts/run-grammar-ai-review.py --once
```

`scripts/install-local-services.sh` installs the continuous runner as `com.yala.ai-project.grammar-ai-review`. Transport failures use a bounded exponential delay; Mecha remains responsible for retries after accepting a task.

The browser only calls ai-project:

- `GET /api/grammar/library/submissions/<id>/ai-review`
- `POST /api/grammar/library/submissions/<id>/ai-review/retry`

It never receives the Mecha API key or connects to Mecha directly.
