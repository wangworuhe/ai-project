"""Mistake-book projections built from immutable deterministic grading evidence."""

from __future__ import annotations

from datetime import datetime

from flask import current_app

from backend.extensions import db
from backend.models.grammar import (
    GrammarAttemptAnswer,
    GrammarAttemptSession,
    GrammarMistakeEntry,
)


MASTERY_CORRECT_STREAK = 2
VISIBLE_SCOPES = {"active", "all", "reviewing", "improving", "mastered"}


class MistakeQueryError(ValueError):
    """A client-visible mistake-book query validation failure."""


def apply_attempt_answer(answer, profile_key, practiced_at=None):
    """Apply one definitive answer outcome to the current mistake-book state."""
    if answer.outcome not in {"correct", "incorrect"}:
        return None
    if answer.id is None:
        db.session.flush()

    entry = GrammarMistakeEntry.query.filter_by(
        profile_key=profile_key, question_id=answer.question_id
    ).first()
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


def sync_existing_attempts():
    """Backfill or catch up the projection without changing attempt evidence."""
    answers = (
        GrammarAttemptAnswer.query
        .join(GrammarAttemptSession)
        .filter(GrammarAttemptAnswer.outcome.in_(("correct", "incorrect")))
        .order_by(GrammarAttemptSession.submitted_at, GrammarAttemptAnswer.id)
        .all()
    )
    for answer in answers:
        apply_attempt_answer(
            answer,
            answer.session.profile_key,
            practiced_at=answer.session.submitted_at,
        )
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
    }


def list_mistakes(scope="active", unit_number=None):
    if scope not in VISIBLE_SCOPES:
        raise MistakeQueryError("status 必须是 active、all、reviewing、improving 或 mastered")
    if unit_number is not None and (isinstance(unit_number, bool) or unit_number < 1):
        raise MistakeQueryError("unit 必须是正整数")

    profile_key = current_app.config["GRAMMAR_DRAFT_PROFILE"]
    base = GrammarMistakeEntry.query.filter_by(profile_key=profile_key)
    all_entries = base.all()
    query = base
    if scope == "active":
        query = query.filter(GrammarMistakeEntry.status.in_(("reviewing", "improving")))
    elif scope != "all":
        query = query.filter_by(status=scope)
    # Unit filtering is applied after serialization to avoid joining the same
    # attempt table through both latest-answer foreign keys.
    entries = [_serialize_entry(item) for item in query.order_by(
        GrammarMistakeEntry.last_practiced_at.desc(), GrammarMistakeEntry.id.desc()
    ).all()]
    if unit_number is not None:
        entries = [item for item in entries if item["unit_number"] == unit_number]
    summary = {
        "total": len(all_entries),
        "active": sum(item.status in {"reviewing", "improving"} for item in all_entries),
        "reviewing": sum(item.status == "reviewing" for item in all_entries),
        "improving": sum(item.status == "improving" for item in all_entries),
        "mastered": sum(item.status == "mastered" for item in all_entries),
    }
    return {"scope": scope, "summary": summary, "items": entries}
