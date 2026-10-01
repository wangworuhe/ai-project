"""Mistake-book projections built from immutable deterministic grading evidence."""

from __future__ import annotations

from datetime import datetime

from flask import current_app

from backend.extensions import db
from backend.models.grammar import (
    GrammarAIReviewItem,
    GrammarAIReviewJob,
    GrammarAttemptAnswer,
    GrammarAttemptSession,
    GrammarExercise,
    GrammarMistakeEntry,
    GrammarQuestion,
    GrammarUnit,
)


MASTERY_CORRECT_STREAK = 2
VISIBLE_SCOPES = {"active", "all", "reviewing", "improving", "mastered"}


class MistakeQueryError(ValueError):
    """A client-visible mistake-book query validation failure."""


def _apply_to_entry(answer, profile_key, entry, practiced_at=None):
    if answer.outcome not in {"correct", "incorrect"}:
        return None
    if entry is not None and entry.latest_attempt_answer_id >= answer.id:
        return entry

    occurred_at = practiced_at or answer.session.submitted_at or datetime.utcnow()
    if answer.outcome == "incorrect":
        if entry is None:
            entry = GrammarMistakeEntry(
                profile_key=profile_key,
                question_id=answer.question_id,
                latest_attempt_answer_id=answer.id,
                latest_incorrect_attempt_answer_id=answer.id,
                status="reviewing",
                wrong_count=1,
                correct_streak=0,
                first_wrong_at=occurred_at,
                last_wrong_at=occurred_at,
                last_practiced_at=occurred_at,
            )
            db.session.add(entry)
        else:
            entry.latest_attempt_answer_id = answer.id
            entry.latest_incorrect_attempt_answer_id = answer.id
            entry.status = "reviewing"
            entry.wrong_count += 1
            entry.correct_streak = 0
            entry.last_wrong_at = occurred_at
            entry.last_practiced_at = occurred_at
            entry.mastered_at = None
        return entry

    if entry is None:
        return None
    entry.latest_attempt_answer_id = answer.id
    entry.correct_streak += 1
    entry.last_practiced_at = occurred_at
    if entry.correct_streak >= MASTERY_CORRECT_STREAK:
        entry.status = "mastered"
        entry.mastered_at = occurred_at
    else:
        entry.status = "improving"
        entry.mastered_at = None
    return entry


def apply_attempt_answer(answer, profile_key, practiced_at=None):
    """Apply one definitive answer outcome to the current mistake-book state."""
    if answer.outcome not in {"correct", "incorrect"}:
        return None
    if answer.id is None:
        db.session.flush()
    entry = GrammarMistakeEntry.query.filter_by(
        profile_key=profile_key, question_id=answer.question_id
    ).first()
    return _apply_to_entry(answer, profile_key, entry, practiced_at)


def sync_existing_attempts():
    """Backfill or catch up the projection without changing attempt evidence."""
    entries = {
        (entry.profile_key, entry.question_id): entry
        for entry in GrammarMistakeEntry.query.all()
    }
    answers = (
        GrammarAttemptAnswer.query
        .join(GrammarAttemptSession)
        .filter(GrammarAttemptAnswer.outcome.in_(("correct", "incorrect")))
        .order_by(GrammarAttemptSession.submitted_at, GrammarAttemptAnswer.id)
        .all()
    )
    for answer in answers:
        key = (answer.session.profile_key, answer.question_id)
        entry = _apply_to_entry(
            answer,
            answer.session.profile_key,
            entries.get(key),
            practiced_at=answer.session.submitted_at,
        )
        if entry is not None:
            entries[key] = entry
    db.session.commit()


def _accepted_variants(answer):
    snapshot = answer.solution_snapshot_json or {}
    return [
        variant.get("values", {})
        for variant in snapshot.get("variants", [])
        if isinstance(variant, dict) and isinstance(variant.get("values"), dict)
    ]


def _serialize_entry(entry):
    latest = db.session.get(GrammarAttemptAnswer, entry.latest_attempt_answer_id)
    latest_wrong = db.session.get(
        GrammarAttemptAnswer, entry.latest_incorrect_attempt_answer_id
    )
    question = entry.question
    exercise = question.exercise
    unit = exercise.unit
    review_item = (
        GrammarAIReviewItem.query
        .filter_by(attempt_answer_id=latest_wrong.id)
        .join(GrammarAIReviewJob)
        .filter(GrammarAIReviewJob.status == "completed")
        .order_by(GrammarAIReviewItem.id.desc())
        .first()
    )
    review_job = next((job for job in
        GrammarAIReviewJob.query.filter_by(attempt_session_id=latest_wrong.session_id)
        .order_by(GrammarAIReviewJob.id.desc()).all()
        if latest_wrong.id in {
            item.get("attempt_answer_id")
            for item in (job.payload_json or {}).get("items", [])
            if isinstance(item, dict)
        }
    ), None)
    ai_review = None
    if review_item:
        ai_review = {
            "status": "completed",
            "explanation_status": review_item.explanation_status,
            "error_type": review_item.error_type,
            "summary": review_item.summary_zh,
            "explanation": review_item.explanation_zh,
            "corrected_answers": review_item.corrected_answers_json,
            "grammar_rule": review_item.grammar_rule,
            "contrast_examples": review_item.contrast_examples_json,
            "review_tip": review_item.review_tip_zh,
            "confidence": float(review_item.confidence),
            "review_decision": review_item.review_decision,
        }
    elif review_job:
        ai_review = {
            "status": review_job.status,
            "message": "讲解服务暂时不可用" if review_job.status in {"failed", "invalid_result"} else None,
        }
    return {
        "id": entry.id,
        "status": entry.status,
        "wrong_count": entry.wrong_count,
        "correct_streak": entry.correct_streak,
        "mastery_target": MASTERY_CORRECT_STREAK,
        "first_wrong_at": entry.first_wrong_at.isoformat(),
        "last_wrong_at": entry.last_wrong_at.isoformat(),
        "last_practiced_at": entry.last_practiced_at.isoformat(),
        "mastered_at": entry.mastered_at.isoformat() if entry.mastered_at else None,
        "question_id": entry.question_id,
        "unit_number": unit.unit_number,
        "unit_title": unit.title,
        "grammar_point": unit.grammar_point,
        "exercise_number": latest_wrong.exercise_number,
        "question_number": latest_wrong.question_number,
        "question_content": latest_wrong.question_content_json,
        "latest_outcome": latest.outcome,
        "latest_wrong": {
            "attempt_answer_id": latest_wrong.id,
            "submission_id": latest_wrong.session_id,
            "user_answers": latest_wrong.user_answers_json,
            "accepted_variants": _accepted_variants(latest_wrong),
            "submitted_at": latest_wrong.session.submitted_at.isoformat(),
        },
        "ai_review": ai_review,
    }


def list_mistakes(scope="active", unit_number=None):
    if scope not in VISIBLE_SCOPES:
        raise MistakeQueryError("status 必须是 active、all、reviewing、improving 或 mastered")
    if unit_number is not None and (isinstance(unit_number, bool) or unit_number < 1):
        raise MistakeQueryError("unit 必须是正整数")

    profile_key = current_app.config["GRAMMAR_DRAFT_PROFILE"]
    base = GrammarMistakeEntry.query.filter_by(profile_key=profile_key)
    if unit_number is not None:
        base = (
            base.join(GrammarMistakeEntry.question)
            .join(GrammarQuestion.exercise)
            .join(GrammarExercise.unit)
            .filter(GrammarUnit.unit_number == unit_number)
        )
    all_entries = base.all()
    query = base
    if scope == "active":
        query = query.filter(GrammarMistakeEntry.status.in_(("reviewing", "improving")))
    elif scope != "all":
        query = query.filter(GrammarMistakeEntry.status == scope)
    entries = [_serialize_entry(item) for item in query.order_by(
        GrammarMistakeEntry.last_practiced_at.desc(), GrammarMistakeEntry.id.desc()
    ).all()]
    summary = {
        "total": len(all_entries),
        "active": sum(item.status in {"reviewing", "improving"} for item in all_entries),
        "reviewing": sum(item.status == "reviewing" for item in all_entries),
        "improving": sum(item.status == "improving" for item in all_entries),
        "mastered": sum(item.status == "mastered" for item in all_entries),
    }
    return {"scope": scope, "summary": summary, "items": entries}
