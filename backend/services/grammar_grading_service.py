"""Immutable grammar submissions and conservative deterministic grading."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone
from decimal import Decimal

from flask import current_app

from backend.extensions import db
from backend.models.grammar import (
    GrammarAnswerSlot,
    GrammarAttemptAnswer,
    GrammarAttemptSession,
    GrammarExercise,
    GrammarQuestion,
    GrammarUnit,
)
from backend.services.grammar_mistake_service import apply_attempt_answer


GRADING_VERSION = "deterministic-v1"
MAX_ANSWER_LENGTH = 2000
MAX_ANSWERS_PER_REQUEST = 500
SUPPORTED_GRADING_MODES = {"exact", "normalized"}
SUPPORTED_NORMALIZATION_RULES = {"choice-code", "english-text"}

_APOSTROPHE_TRANSLATION = str.maketrans({
    "’": "'",
    "‘": "'",
    "ʼ": "'",
    "＇": "'",
    "`": "'",
})
_ZERO_WIDTH = dict.fromkeys(map(ord, "\u200b\u200c\u200d\ufeff"), None)


class SubmissionValidationError(ValueError):
    """A client-visible formal-submission validation failure."""


def _json_sha256(value):
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def question_submission_version(question, slots=None):
    """Fingerprint the visible question and answer-slot contract."""
    if slots is None:
        slots = sorted(
            (item for item in question.answer_slots if item.is_active),
            key=lambda item: item.slot_order,
        )
    return _json_sha256({
        "question_id": question.id,
        "content": question.content_json,
        "slots": [{
            "id": slot.id,
            "key": slot.slot_key,
            "order": slot.slot_order,
            "type": slot.answer_type,
            "normalization_rule": slot.normalization_rule,
            "points": str(slot.points),
        } for slot in slots],
    })


def _base_normalize(value):
    value = unicodedata.normalize("NFKC", value)
    value = value.translate(_APOSTROPHE_TRANSLATION).translate(_ZERO_WIDTH)
    return " ".join(value.split()).strip()


def normalize_answer(value, normalization_rule, grading_mode):
    """Normalize only presentation variants that cannot change English meaning."""
    if normalization_rule not in SUPPORTED_NORMALIZATION_RULES:
        raise ValueError(f"Unsupported normalization rule: {normalization_rule}")
    if grading_mode not in SUPPORTED_GRADING_MODES:
        raise ValueError(f"Unsupported grading mode: {grading_mode}")

    normalized = _base_normalize(value)
    if normalization_rule == "choice-code":
        return normalized.casefold()
    if grading_mode == "exact":
        return normalized

    # Ignore case, typography, and whitespace before punctuation. Terminal
    # punctuation is handled directionally during comparison: an expected mark
    # may be omitted, but a different or additional mark is not accepted.
    normalized = re.sub(r"\s+([,.;:!?])", r"\1", normalized)
    return normalized.casefold()


def _normalized_values_match(user_value, expected_value, normalization_rule, grading_mode):
    if user_value == expected_value:
        return True
    if normalization_rule != "english-text" or grading_mode != "normalized":
        return False
    return bool(
        expected_value
        and expected_value[-1] in ".!?"
        and user_value == expected_value[:-1].rstrip()
    )


def grade_answer_values(slot_specs, user_values, variants, grading_mode):
    """Grade one complete question against explicit, whole-answer variants."""
    slot_keys = [slot["key"] for slot in slot_specs]
    raw_values = {key: user_values.get(key, "") for key in slot_keys}
    filled = {key: bool(value.strip()) for key, value in raw_values.items()}
    if not any(filled.values()):
        return {
            "outcome": "unanswered",
            "normalized": {key: "" for key in slot_keys},
            "matched_variant_order": None,
        }
    if not all(filled.values()):
        return {
            "outcome": "incomplete",
            "normalized": {key: _base_normalize(raw_values[key]) for key in slot_keys},
            "matched_variant_order": None,
        }
    if grading_mode not in SUPPORTED_GRADING_MODES or any(
        slot["normalization_rule"] not in SUPPORTED_NORMALIZATION_RULES
        for slot in slot_specs
    ):
        return {
            "outcome": "needs_review",
            "normalized": {key: _base_normalize(raw_values[key]) for key in slot_keys},
            "matched_variant_order": None,
        }

    normalized_user = {
        slot["key"]: normalize_answer(
            raw_values[slot["key"]], slot["normalization_rule"], grading_mode
        )
        for slot in slot_specs
    }
    usable_variants = []
    for variant in variants:
        values = variant.get("values")
        if not isinstance(values, dict) or set(values) != set(slot_keys):
            continue
        if not all(isinstance(values[key], str) for key in slot_keys):
            continue
        usable_variants.append(variant)

    if not usable_variants:
        return {
            "outcome": "needs_review",
            "normalized": normalized_user,
            "matched_variant_order": None,
        }

    for variant in usable_variants:
        normalized_variant = {
            slot["key"]: normalize_answer(
                variant["values"][slot["key"]],
                slot["normalization_rule"],
                grading_mode,
            )
            for slot in slot_specs
        }
        if all(
            _normalized_values_match(
                normalized_user[slot["key"]],
                normalized_variant[slot["key"]],
                slot["normalization_rule"],
                grading_mode,
            )
            for slot in slot_specs
        ):
            return {
                "outcome": "correct",
                "normalized": normalized_user,
                "matched_variant_order": variant["order"],
            }
    return {
        "outcome": "incorrect",
        "normalized": normalized_user,
        "matched_variant_order": None,
    }


def _published_unit(unit_number):
    return GrammarUnit.query.filter_by(
        unit_number=unit_number, status="published"
    ).first()


def _profile_key():
    return current_app.config["GRAMMAR_DRAFT_PROFILE"]


def _parse_submission(payload):
    if not isinstance(payload, dict):
        raise SubmissionValidationError("请求内容格式不正确")
    if not isinstance(payload.get("answers"), list):
        raise SubmissionValidationError("请求必须包含 answers 数组")
    if not isinstance(payload.get("question_versions"), list):
        raise SubmissionValidationError("请求必须包含 question_versions 数组")
    submitted = payload["answers"]
    if len(submitted) > MAX_ANSWERS_PER_REQUEST:
        raise SubmissionValidationError("一次提交的答案数量过多")

    values = {}
    for index, item in enumerate(submitted, start=1):
        if not isinstance(item, dict):
            raise SubmissionValidationError(f"第 {index} 个答案格式不正确")
        slot_id = item.get("slot_id")
        value = item.get("value")
        if isinstance(slot_id, bool) or not isinstance(slot_id, int):
            raise SubmissionValidationError(f"第 {index} 个答案缺少有效的 slot_id")
        if slot_id in values:
            raise SubmissionValidationError(f"答案槽 {slot_id} 重复出现")
        if not isinstance(value, str):
            raise SubmissionValidationError(f"答案槽 {slot_id} 的内容必须是文本")
        if len(value) > MAX_ANSWER_LENGTH:
            raise SubmissionValidationError(
                f"答案槽 {slot_id} 超过 {MAX_ANSWER_LENGTH} 个字符"
            )
        values[slot_id] = value
    question_versions = {}
    for index, item in enumerate(payload["question_versions"], start=1):
        if not isinstance(item, dict):
            raise SubmissionValidationError(f"第 {index} 个题目版本格式不正确")
        question_id = item.get("question_id")
        version = item.get("version")
        if isinstance(question_id, bool) or not isinstance(question_id, int):
            raise SubmissionValidationError(f"第 {index} 个题目版本缺少有效的 question_id")
        if question_id in question_versions:
            raise SubmissionValidationError(f"题目 {question_id} 的版本重复出现")
        if not isinstance(version, str) or not re.fullmatch(r"[0-9a-f]{64}", version):
            raise SubmissionValidationError(f"题目 {question_id} 的版本格式不正确")
        question_versions[question_id] = version
    return values, question_versions


def _active_questions(unit):
    return [
        (exercise, question)
        for exercise in sorted(
            (item for item in unit.exercises if item.is_active),
            key=lambda item: item.sort_order,
        )
        for question in sorted(
            (
                item
                for item in exercise.questions
                if item.is_active and not item.is_example
            ),
            key=lambda item: item.sort_order,
        )
    ]


def _slot_specs(question):
    slots = sorted(
        (item for item in question.answer_slots if item.is_active),
        key=lambda item: item.slot_order,
    )
    return slots, [
        {
            "id": slot.id,
            "key": slot.slot_key,
            "normalization_rule": slot.normalization_rule,
            "points": str(slot.points),
        }
        for slot in slots
    ]


def _solution_snapshot(solution, slot_specs):
    if solution is None:
        return None
    return {
        "id": solution.id,
        "answer_kind": solution.answer_kind,
        "display_answer": solution.display_answer,
        "grading_mode": solution.grading_mode,
        "verification_status": solution.verification_status,
        "source_page": solution.source_page,
        "source_label": solution.source_label,
        "slots": slot_specs,
        "variants": [
            {
                "order": variant.variant_order,
                "values": variant.values_json,
                "primary": variant.is_primary,
                "source_text": variant.source_text,
            }
            for variant in sorted(solution.variants, key=lambda item: item.variant_order)
        ],
    }


def submit_unit_attempt(unit_number, payload):
    unit = _published_unit(unit_number)
    if unit is None:
        return None
    submitted_values, submitted_versions = _parse_submission(payload)
    questions = _active_questions(unit)
    active_slot_ids = {
        slot.id
        for _, question in questions
        for slot in question.answer_slots
        if slot.is_active
    }
    if set(submitted_values) - active_slot_ids:
        raise SubmissionValidationError(
            "答案对应的题目已更新或不可作答，请刷新页面后重试"
        )
    current_versions = {
        question.id: question_submission_version(question)
        for _, question in questions
    }
    if submitted_versions != current_versions:
        raise SubmissionValidationError(
            "题目内容已更新，请刷新页面后重新提交"
        )

    submitted_at = datetime.now(timezone.utc).replace(tzinfo=None)
    session = GrammarAttemptSession(
        profile_key=_profile_key(),
        unit=unit,
        status="grading",
        grading_version=GRADING_VERSION,
        total_questions=len(questions),
        correct_count=0,
        incorrect_count=0,
        incomplete_count=0,
        unanswered_count=0,
        needs_review_count=0,
        points_awarded=Decimal("0"),
        points_possible=Decimal("0"),
        submitted_at=submitted_at,
    )
    db.session.add(session)

    results = []
    counts = {
        "correct": 0,
        "incorrect": 0,
        "incomplete": 0,
        "unanswered": 0,
        "needs_review": 0,
    }
    total_awarded = Decimal("0")
    total_possible = Decimal("0")

    for exercise, question in questions:
        slots, slot_specs = _slot_specs(question)
        possible = sum((slot.points for slot in slots), Decimal("0"))
        total_possible += possible
        user_values = {
            slot.slot_key: submitted_values.get(slot.id, "") for slot in slots
        }
        solution = question.solution
        solution_snapshot = _solution_snapshot(solution, slot_specs)
        variants = solution_snapshot["variants"] if solution_snapshot else []
        grading_mode = solution.grading_mode if solution else None

        if solution is None or solution.verification_status != "verified":
            base_result = grade_answer_values(
                slot_specs, user_values, [], grading_mode or "unsupported"
            )
            if base_result["outcome"] not in {"unanswered", "incomplete"}:
                base_result["outcome"] = "needs_review"
        else:
            base_result = grade_answer_values(
                slot_specs, user_values, variants, grading_mode
            )

        outcome = base_result["outcome"]
        counts[outcome] += 1
        awarded = possible if outcome == "correct" else Decimal("0")
        total_awarded += awarded
        question_hash = _json_sha256(question.content_json)
        solution_hash = (
            _json_sha256(solution_snapshot) if solution_snapshot is not None else None
        )
        record = GrammarAttemptAnswer(
            session=session,
            question=question,
            solution=solution,
            exercise_number=exercise.exercise_number,
            question_number=question.question_number,
            question_content_json=question.content_json,
            question_content_sha256=question_hash,
            solution_snapshot_json=solution_snapshot,
            solution_sha256=solution_hash,
            user_answers_json=user_values,
            normalized_answers_json=base_result["normalized"],
            outcome=outcome,
            grading_mode=grading_mode,
            matched_variant_order=base_result["matched_variant_order"],
            points_awarded=awarded,
            points_possible=possible,
        )
        db.session.add(record)
        db.session.flush()
        apply_attempt_answer(record, session.profile_key, practiced_at=submitted_at)
        results.append({
            "question_id": question.id,
            "exercise_number": exercise.exercise_number,
            "question_number": question.question_number,
            "outcome": outcome,
            "user_answers": user_values,
            "accepted_variants": [variant["values"] for variant in variants],
            "matched_variant_order": base_result["matched_variant_order"],
            "points_awarded": float(awarded),
            "points_possible": float(possible),
        })

    session.status = "needs_review" if counts["needs_review"] else "graded"
    session.correct_count = counts["correct"]
    session.incorrect_count = counts["incorrect"]
    session.incomplete_count = counts["incomplete"]
    session.unanswered_count = counts["unanswered"]
    session.needs_review_count = counts["needs_review"]
    session.points_awarded = total_awarded
    session.points_possible = total_possible
    db.session.commit()

    return _serialize_session(session, results=results)


def _serialize_session(session, results=None):
    if results is None:
        results = [{
            "question_id": answer.question_id,
            "exercise_number": answer.exercise_number,
            "question_number": answer.question_number,
            "outcome": answer.outcome,
            "user_answers": answer.user_answers_json,
            "accepted_variants": (
                [variant["values"] for variant in answer.solution_snapshot_json["variants"]]
                if answer.solution_snapshot_json else []
            ),
            "matched_variant_order": answer.matched_variant_order,
            "points_awarded": float(answer.points_awarded),
            "points_possible": float(answer.points_possible),
        } for answer in session.answers]
    return {
        "id": session.id,
        "unit_number": session.unit.unit_number,
        "status": session.status,
        "grading_version": session.grading_version,
        "submitted_at": session.submitted_at.isoformat(),
        "summary": {
            "total_questions": session.total_questions,
            "correct": session.correct_count,
            "incorrect": session.incorrect_count,
            "incomplete": session.incomplete_count,
            "unanswered": session.unanswered_count,
            "needs_review": session.needs_review_count,
            "points_awarded": float(session.points_awarded),
            "points_possible": float(session.points_possible),
        },
        "results": results,
    }


def get_attempt_session(session_id):
    session = GrammarAttemptSession.query.filter_by(
        id=session_id, profile_key=_profile_key()
    ).first()
    return _serialize_session(session) if session else None
