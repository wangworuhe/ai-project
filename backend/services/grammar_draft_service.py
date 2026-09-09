"""Server-side persistence for the current grammar workbook draft."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from flask import current_app

from backend.extensions import db
from backend.models.grammar import (
    GrammarAnswerSlot,
    GrammarDraft,
    GrammarDraftAnswer,
    GrammarExercise,
    GrammarQuestion,
    GrammarUnit,
)


MAX_ANSWER_LENGTH = 2000
MAX_ANSWERS_PER_REQUEST = 500


class DraftValidationError(ValueError):
    """A client-visible draft validation failure."""


def _published_unit(unit_number):
    return GrammarUnit.query.filter_by(
        unit_number=unit_number, status="published"
    ).first()


def _profile_key():
    return current_app.config["GRAMMAR_DRAFT_PROFILE"]


def _content_sha256(question):
    serialized = json.dumps(
        question.content_json, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _active_slots(unit_id):
    rows = (
        db.session.query(GrammarAnswerSlot, GrammarQuestion)
        .join(GrammarQuestion, GrammarQuestion.id == GrammarAnswerSlot.question_id)
        .join(GrammarExercise, GrammarExercise.id == GrammarQuestion.exercise_id)
        .filter(
            GrammarExercise.unit_id == unit_id,
            GrammarExercise.is_active.is_(True),
            GrammarQuestion.is_active.is_(True),
            GrammarQuestion.is_example.is_(False),
            GrammarAnswerSlot.is_active.is_(True),
        )
        .all()
    )
    return {slot.id: (slot, question) for slot, question in rows}


def get_unit_draft(unit_number):
    unit = _published_unit(unit_number)
    if unit is None:
        return None
    draft = GrammarDraft.query.filter_by(
        profile_key=_profile_key(), unit_id=unit.id
    ).first()
    if draft is None:
        return {"answers": [], "updated_at": None}

    active_slot_ids = set(_active_slots(unit.id))
    answers = [
        {"slot_id": answer.answer_slot_id, "value": answer.answer_text}
        for answer in sorted(draft.answers, key=lambda item: item.answer_slot_id)
        if answer.answer_slot_id in active_slot_ids
    ]
    return {
        "answers": answers,
        "updated_at": draft.updated_at.isoformat() if draft.updated_at else None,
    }


def save_unit_draft(unit_number, payload):
    unit = _published_unit(unit_number)
    if unit is None:
        return None
    if not isinstance(payload, dict) or not isinstance(payload.get("answers"), list):
        raise DraftValidationError("请求必须包含 answers 数组")
    submitted = payload["answers"]
    if len(submitted) > MAX_ANSWERS_PER_REQUEST:
        raise DraftValidationError("一次保存的答案数量过多")

    values = {}
    for index, item in enumerate(submitted, start=1):
        if not isinstance(item, dict):
            raise DraftValidationError(f"第 {index} 个答案格式不正确")
        slot_id = item.get("slot_id")
        value = item.get("value")
        if isinstance(slot_id, bool) or not isinstance(slot_id, int):
            raise DraftValidationError(f"第 {index} 个答案缺少有效的 slot_id")
        if slot_id in values:
            raise DraftValidationError(f"答案槽 {slot_id} 重复出现")
        if not isinstance(value, str):
            raise DraftValidationError(f"答案槽 {slot_id} 的内容必须是文本")
        if len(value) > MAX_ANSWER_LENGTH:
            raise DraftValidationError(
                f"答案槽 {slot_id} 超过 {MAX_ANSWER_LENGTH} 个字符"
            )
        values[slot_id] = value

    active_slots = _active_slots(unit.id)
    unknown = sorted(set(values) - set(active_slots))
    if unknown:
        raise DraftValidationError(
            "答案对应的题目已更新或不可作答，请刷新页面后重试"
        )

    draft = GrammarDraft.query.filter_by(
        profile_key=_profile_key(), unit_id=unit.id
    ).first()
    if draft is None:
        draft = GrammarDraft(profile_key=_profile_key(), unit=unit)
        db.session.add(draft)
        db.session.flush()

    existing = {answer.answer_slot_id: answer for answer in draft.answers}
    retained_slot_ids = set()
    for slot_id, value in values.items():
        if not value.strip():
            continue
        retained_slot_ids.add(slot_id)
        answer = existing.get(slot_id)
        if answer is None:
            answer = GrammarDraftAnswer(draft=draft, answer_slot_id=slot_id)
            db.session.add(answer)
        answer.answer_text = value
        answer.question_content_sha256 = _content_sha256(active_slots[slot_id][1])

    for slot_id, answer in existing.items():
        if slot_id not in retained_slot_ids:
            db.session.delete(answer)

    saved_at = datetime.now(timezone.utc).replace(tzinfo=None)
    if retained_slot_ids:
        draft.updated_at = saved_at
    else:
        db.session.delete(draft)
    db.session.commit()
    return {
        "saved_answers": len(retained_slot_ids),
        "updated_at": saved_at.isoformat(),
    }
