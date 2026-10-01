#!/usr/bin/env python3
"""Run one synthetic, schema-checked grammar explanation through Mecha."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import uuid
from pathlib import Path

import requests
from jsonschema import Draft202012Validator


ROOT = Path(os.environ.get("AI_PROJECT_ROOT", Path(__file__).resolve().parents[1]))
OUTPUT_SCHEMA = json.loads((ROOT / "schemas/grammar-explanation-output.schema.json").read_text())
PROMPT = (ROOT / "prompts/grammar-mistake-explainer-v1.txt").read_text().strip()


def task_request(request_id: str) -> dict:
    question = {"text": "They ___ a new hospital. (build)"}
    payload = {
        "schema_version": "grammar-explanation-input/v1",
        "request_id": request_id,
        "attempt_session_id": 999999,
        "language": "zh-CN",
        "lesson_context": {
            "unit_number": 1,
            "title": "Present continuous (I am doing)",
            "grammar_point": "present continuous",
            "content_blocks": [],
        },
        "items": [{
            "attempt_answer_id": 999999,
            "question_id": 999999,
            "exercise_number": "1",
            "question_number": "1",
            "question_type": "fill_blank",
            "question_content": question,
            "user_answers": {"answer-1": "They are build"},
            "accepted_variants": [{"answer-1": "They are building"}],
            "deterministic_outcome": "incorrect",
            "question_content_sha256": hashlib.sha256(json.dumps(question, sort_keys=True).encode()).hexdigest(),
            "solution_sha256": None,
        }],
    }
    return {
        "worker": "grammar-mistake-explainer",
        "prompt": PROMPT,
        "context": {"input": payload, "output_schema": OUTPUT_SCHEMA},
        "dedup_key": f"migration-smoke:{request_id}",
        "max_retries": 1,
    }


def get_json(session: requests.Session, method: str, url: str, **kwargs) -> dict:
    response = session.request(method, url, timeout=20, **kwargs)
    response.raise_for_status()
    result = response.json()
    if not isinstance(result, dict):
        raise ValueError("Mecha response is not an object")
    return result


def main() -> int:
    base_url = os.environ["MECHA_BASE_URL"].rstrip("/")
    api_key = os.environ["MECHA_API_KEY"]
    request_id = f"migration-smoke-{uuid.uuid4().hex[:12]}"
    request = task_request(request_id)
    session = requests.Session()
    session.headers["Authorization"] = f"Bearer {api_key}"

    first = get_json(session, "POST", f"{base_url}/task", json=request)
    duplicate = get_json(session, "POST", f"{base_url}/task", json=request)
    task_id = str(first.get("id") or first.get("task_id") or "")
    if not task_id or task_id != str(duplicate.get("id") or duplicate.get("task_id") or ""):
        raise ValueError("dedup_key did not return the same task ID")

    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        task = get_json(session, "GET", f"{base_url}/task/{task_id}")
        state = str(task.get("status") or task.get("state") or "").lower()
        if state in {"completed", "succeeded", "success"}:
            break
        if state in {"failed", "error", "cancelled", "canceled"}:
            raise ValueError(f"Mecha task ended in {state}: {str(task.get('error'))[:300]}")
        time.sleep(5)
    else:
        raise TimeoutError(f"Mecha task {task_id} did not complete in five minutes")

    from backend.services.grammar_ai_review_service import _result_payload

    output, _ = _result_payload(task.get("result"), 1_048_576)
    Draft202012Validator(OUTPUT_SCHEMA).validate(output)
    items = output["items"]
    if output["request_id"] != request_id or len(items) != 1:
        raise ValueError("Output request ID or item count does not match")
    item = items[0]
    if item["attempt_answer_id"] != 999999 or item["review_decision"] != "not_applicable":
        raise ValueError("Output changed the deterministic grading boundary")
    if item["corrected_answers"] != [{"slot_key": "answer-1", "value": "They are building"}]:
        raise ValueError("Output did not preserve the accepted answer and slot")

    evidence_dir = Path("/app/storage/logs")
    evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence_path = evidence_dir / f"mecha-{request_id}.json"
    fd = os.open(evidence_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as file:
        json.dump({"request": request, "task": task}, file, ensure_ascii=False, indent=2)
    print(f"task_id={task_id} status={state} schema=valid dedup=valid evidence={evidence_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, ValueError, TimeoutError, requests.RequestException) as error:
        print(f"Mecha smoke failed: {error}", file=sys.stderr)
        raise SystemExit(1)
