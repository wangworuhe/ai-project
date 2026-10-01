"""Durable bridge between deterministic grading and Mecha AI explanations."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path

import requests
from flask import current_app
from jsonschema import Draft202012Validator

from backend.extensions import db
from backend.models.grammar import (
    GrammarAIReviewItem,
    GrammarAIReviewJob,
    GrammarAttemptSession,
)

INPUT_VERSION = "grammar-explanation-input/v1"
PROMPT_VERSION = "grammar-mistake-explainer/v1"
ELIGIBLE_OUTCOMES = {"incorrect", "needs_review"}
ACTIVE_STATES = {"queued", "dispatched"}
_SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schemas"
_PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "grammar-mistake-explainer-v1.txt"


class ReviewResultError(ValueError):
    """The worker completed, but its result cannot safely be persisted."""


def _canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(value):
    return hashlib.sha256(_canonical_json(value).encode()).hexdigest()


def _schema(name):
    with (_SCHEMA_DIR / name).open(encoding="utf-8") as handle:
        return json.load(handle)


def _prompt(version):
    if version != PROMPT_VERSION:
        raise ValueError(f"Unsupported grammar review prompt version: {version}")
    return _PROMPT_PATH.read_text(encoding="utf-8").strip()


def _accepted_variants(answer):
    snapshot = answer.solution_snapshot_json or {}
    return [
        item["values"] for item in snapshot.get("variants", [])
        if isinstance(item, dict) and isinstance(item.get("values"), dict)
    ]


def _build_payload(session, answers, request_id):
    unit = session.unit
    return {
        "schema_version": INPUT_VERSION,
        "request_id": request_id,
        "attempt_session_id": session.id,
        "language": "zh-CN",
        "lesson_context": {
            "unit_number": unit.unit_number,
            "title": unit.title,
            "grammar_point": unit.grammar_point,
            "content_blocks": [block.content_json for block in sorted(unit.content_blocks, key=lambda value: value.sort_order)],
        },
        "items": [{
            "attempt_answer_id": answer.id,
            "question_id": answer.question_id,
            "exercise_number": answer.exercise_number,
            "question_number": answer.question_number,
            "question_type": answer.question.question_type,
            "question_content": answer.question_content_json,
            "user_answers": answer.user_answers_json,
            "accepted_variants": _accepted_variants(answer),
            "deterministic_outcome": answer.outcome,
            "question_content_sha256": answer.question_content_sha256,
            "solution_sha256": answer.solution_sha256,
        } for answer in answers],
    }


def create_review_jobs_for_session(session, answers=None):
    """Create idempotent batches in the grading transaction; never call Mecha."""
    if session.id is None:
        db.session.flush()
    answers = list(answers if answers is not None else session.answers)
    eligible = [answer for answer in answers if answer.outcome in ELIGIBLE_OUTCOMES]
    if not eligible:
        return []
    size = max(1, min(20, current_app.config.get("GRAMMAR_AI_REVIEW_BATCH_SIZE", 20)))
    chunks = [eligible[index:index + size] for index in range(0, len(eligible), size)]
    jobs = []
    for index, chunk in enumerate(chunks, start=1):
        request_id = f"grammar-{session.id}-{index}-v1"
        dedup_key = f"grammar-explanation:v1:prompt-v1:{session.id}:{index}:{_sha256([item.id for item in chunk])[:16]}"
        existing = GrammarAIReviewJob.query.filter_by(request_id=request_id).first()
        if existing:
            jobs.append(existing)
            continue
        payload = _build_payload(session, chunk, request_id)
        Draft202012Validator(_schema("grammar-explanation-input.schema.json")).validate(payload)
        job = GrammarAIReviewJob(
            profile_key=session.profile_key, attempt_session_id=session.id,
            batch_index=index, batch_count=len(chunks),
            worker_name=current_app.config.get("GRAMMAR_AI_REVIEW_WORKER", "grammar-mistake-explainer"),
            schema_version=INPUT_VERSION, prompt_version=PROMPT_VERSION,
            request_id=request_id, dedup_key=dedup_key,
            payload_json=payload, payload_sha256=_sha256(payload), status="queued",
        )
        db.session.add(job)
        jobs.append(job)
    return jobs


def sync_existing_review_jobs():
    """Idempotently backfill eligible historical submissions without networking."""
    sessions = (GrammarAttemptSession.query
                .filter((GrammarAttemptSession.incorrect_count > 0) | (GrammarAttemptSession.needs_review_count > 0))
                .order_by(GrammarAttemptSession.id).all())
    for session in sessions:
        create_review_jobs_for_session(session)
    db.session.commit()


class MechaClient:
    def __init__(self, base_url, api_key="", timeout=15):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        if api_key:
            self.session.headers["Authorization"] = f"Bearer {api_key}"

    def create_task(self, job):
        response = self.session.post(f"{self.base_url}/task", json={
            "worker": job.worker_name,
            "prompt": _prompt(job.prompt_version),
            "context": {"input": job.payload_json, "output_schema": _schema("grammar-explanation-output.schema.json")},
            "dedup_key": job.dedup_key,
            "max_retries": 3,
        }, timeout=self.timeout)
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, dict):
            raise ReviewResultError("Mecha create response is not an object")
        task_id = body.get("id") or body.get("task_id")
        if not isinstance(task_id, (str, int)):
            raise ReviewResultError("Mecha create response has no task id")
        return str(task_id)

    def get_task(self, task_id):
        response = self.session.get(f"{self.base_url}/task/{task_id}", timeout=self.timeout)
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, dict):
            raise ReviewResultError("Mecha task response is not an object")
        return body


def _result_payload(raw_result, max_bytes):
    raw_text = raw_result if isinstance(raw_result, str) else _canonical_json(raw_result)
    if len(raw_text.encode()) > max_bytes:
        raise ReviewResultError("Mecha result exceeds configured size limit")
    value = raw_result
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as error:
            raise ReviewResultError("Mecha result is not JSON") from error
    if isinstance(value, dict) and "output" in value:
        value = value["output"]
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError as error:
                raise ReviewResultError("Mecha output is not JSON") from error
    if not isinstance(value, dict):
        raise ReviewResultError("Mecha output is not an object")
    return value, raw_text


def validate_and_store_result(job, raw_result):
    result, raw_text = _result_payload(raw_result, current_app.config.get("GRAMMAR_AI_REVIEW_RESULT_MAX_BYTES", 1048576))
    errors = sorted(Draft202012Validator(_schema("grammar-explanation-output.schema.json")).iter_errors(result), key=lambda item: list(item.path))
    if errors:
        raise ReviewResultError(f"Output schema violation: {errors[0].message}")
    if result["request_id"] != job.request_id:
        raise ReviewResultError("Output request_id does not match job")
    inputs = {item["attempt_answer_id"]: item for item in job.payload_json["items"]}
    outputs = result["items"]
    output_ids = [item["attempt_answer_id"] for item in outputs]
    if len(output_ids) != len(set(output_ids)) or set(output_ids) != set(inputs):
        raise ReviewResultError("Output must contain every requested answer exactly once")
    for item in outputs:
        original = inputs[item["attempt_answer_id"]]
        corrected = item["corrected_answers"]
        corrected_keys = [answer["slot_key"] for answer in corrected]
        if len(corrected_keys) != len(set(corrected_keys)) or set(corrected_keys) != set(original["user_answers"]):
            raise ReviewResultError("Corrected-answer slots do not match submitted slots")
        corrected_values = {answer["slot_key"]: answer["value"] for answer in corrected}
        accepted_variants = original.get("accepted_variants") or []
        if accepted_variants and corrected_values not in accepted_variants:
            raise ReviewResultError("Corrected answers must match one authoritative accepted variant")
        if original["deterministic_outcome"] == "incorrect" and item["review_decision"] != "not_applicable":
            raise ReviewResultError("AI cannot revise a deterministic incorrect grade")
        if original["deterministic_outcome"] == "needs_review" and item["review_decision"] == "not_applicable":
            raise ReviewResultError("A needs-review answer requires an explicit review decision")
    result_hash = _sha256(result)
    for item in outputs:
        db.session.add(GrammarAIReviewItem(
            job=job, attempt_answer_id=item["attempt_answer_id"],
            explanation_status=item["explanation_status"], error_type=item["error_type"],
            summary_zh=item["summary_zh"], explanation_zh=item["explanation_zh"],
            corrected_answers_json={answer["slot_key"]: answer["value"] for answer in item["corrected_answers"]},
            grammar_rule=item["grammar_rule"],
            contrast_examples_json=item["contrast_examples"], review_tip_zh=item["review_tip_zh"],
            confidence=item["confidence"], review_decision=item["review_decision"],
            result_sha256=result_hash,
        ))
    job.raw_result_text = raw_text
    job.status = "completed"
    job.completed_at = datetime.utcnow()
    job.error_message = None


def _retry_later(job, error):
    attempts = max(job.dispatch_attempts, job.poll_attempts)
    job.error_message = str(error)[:2000]
    job.next_attempt_at = datetime.utcnow() + timedelta(seconds=min(300, 2 ** min(attempts, 8)))


def process_review_jobs_once(client=None):
    """Advance due jobs once. Safe to call repeatedly and after restarts."""
    base_url = current_app.config.get("MECHA_BASE_URL", "")
    if not base_url and client is None:
        return {"configured": False, "processed": 0}
    client = client or MechaClient(base_url, current_app.config.get("MECHA_API_KEY", ""), current_app.config.get("GRAMMAR_AI_REVIEW_HTTP_TIMEOUT", 15))
    now = datetime.utcnow()
    jobs = (GrammarAIReviewJob.query.filter(GrammarAIReviewJob.status.in_(ACTIVE_STATES))
            .filter((GrammarAIReviewJob.next_attempt_at.is_(None)) | (GrammarAIReviewJob.next_attempt_at <= now))
            .order_by(GrammarAIReviewJob.id).limit(20).all())
    for job in jobs:
        task = None
        try:
            if job.status == "queued":
                job.dispatch_attempts += 1
                job.mecha_task_id = client.create_task(job)
                job.status = "dispatched"
                job.dispatched_at = now
                job.next_attempt_at = now
            else:
                job.poll_attempts += 1
                task = client.get_task(job.mecha_task_id)
                state = str(task.get("status") or task.get("state") or "").lower()
                if state in {"completed", "succeeded", "success"}:
                    validate_and_store_result(job, task.get("result"))
                elif state in {"failed", "error", "cancelled", "canceled"}:
                    job.status = "failed"
                    job.error_message = str(task.get("error") or "Mecha task failed")[:2000]
                    job.completed_at = now
                else:
                    job.next_attempt_at = now + timedelta(seconds=5)
        except ReviewResultError as error:
            job.status = "invalid_result"
            job.error_message = str(error)[:2000]
            job.completed_at = now
            if isinstance(task, dict):
                job.raw_result_text = _canonical_json(task.get("result"))[:current_app.config.get("GRAMMAR_AI_REVIEW_RESULT_MAX_BYTES", 1048576)]
        except (requests.RequestException, ValueError) as error:
            _retry_later(job, error)
        db.session.commit()
    return {"configured": True, "processed": len(jobs)}


def get_session_review(session_id):
    session = GrammarAttemptSession.query.filter_by(
        id=session_id, profile_key=current_app.config["GRAMMAR_DRAFT_PROFILE"]
    ).first()
    if session is None:
        return None
    jobs = GrammarAIReviewJob.query.filter_by(attempt_session_id=session.id).order_by(GrammarAIReviewJob.batch_index).all()
    return {
        "submission_id": session.id,
        "jobs": [{
            "id": job.id, "batch_index": job.batch_index,
            "batch_count": job.batch_count, "status": job.status,
            "items": [{
                "attempt_answer_id": item.attempt_answer_id,
                "explanation_status": item.explanation_status,
                "error_type": item.error_type, "summary": item.summary_zh,
                "explanation": item.explanation_zh,
                "corrected_answers": item.corrected_answers_json,
                "grammar_rule": item.grammar_rule,
                "contrast_examples": item.contrast_examples_json,
                "review_tip": item.review_tip_zh,
                "confidence": float(item.confidence),
                "review_decision": item.review_decision,
            } for item in job.items],
        } for job in jobs],
    }


def retry_session_review(session_id):
    """Create a new durable attempt for each latest failed batch."""
    session = GrammarAttemptSession.query.filter_by(
        id=session_id, profile_key=current_app.config["GRAMMAR_DRAFT_PROFILE"]
    ).first()
    if session is None:
        return None

    jobs = (GrammarAIReviewJob.query.filter_by(attempt_session_id=session.id)
            .order_by(GrammarAIReviewJob.batch_index, GrammarAIReviewJob.id.desc()).all())
    latest_by_batch = {}
    batch_counts = {}
    for job in jobs:
        latest_by_batch.setdefault(job.batch_index, job)
        batch_counts[job.batch_index] = batch_counts.get(job.batch_index, 0) + 1

    for batch_index, prior in latest_by_batch.items():
        if prior.status not in {"failed", "invalid_result"}:
            continue
        retry_number = batch_counts[batch_index]
        request_id = f"grammar-{session.id}-{batch_index}-v1-r{retry_number}"
        payload = deepcopy(prior.payload_json)
        payload["request_id"] = request_id
        job = GrammarAIReviewJob(
            profile_key=session.profile_key,
            attempt_session_id=session.id,
            batch_index=batch_index,
            batch_count=prior.batch_count,
            worker_name=prior.worker_name,
            schema_version=prior.schema_version,
            prompt_version=prior.prompt_version,
            request_id=request_id,
            dedup_key=f"{prior.dedup_key.split(':retry:', 1)[0]}:retry:{retry_number}",
            payload_json=payload,
            payload_sha256=_sha256(payload),
            status="queued",
        )
        db.session.add(job)
    db.session.commit()
    return get_session_review(session_id)
