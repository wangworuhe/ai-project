"""Read-only serializers for reviewed, database-backed grammar units."""

from __future__ import annotations

from backend.extensions import db
from backend.models.grammar import GrammarMedia, GrammarUnit


def _merge_segments(segments):
    merged = []
    for segment in segments:
        text = segment.get("text", "")
        if not text:
            continue
        style = {
            "bold": bool(segment.get("bold")),
            "italic": bool(segment.get("italic")),
        }
        if merged and all(merged[-1].get(key) == value for key, value in style.items()):
            merged[-1]["text"] += text
        else:
            merged.append({"text": text, **style})
    return merged


def _source_lines(source_blocks, section_label, heading_range):
    """Convert positioned PDF spans into reflowable lines without exposing coordinates."""
    blocks = [
        block for block in source_blocks
        if not (
            (
                block.get("text", "").strip() == section_label
                and block.get("bbox", [999])[0] < 115
            )
            or heading_range[0] <= block.get("bbox", [0, -1])[1] < heading_range[1]
        )
    ]
    blocks.sort(key=lambda block: (block["bbox"][1], block["bbox"][0]))
    grouped = []
    for block in blocks:
        if not grouped or abs(block["bbox"][1] - grouped[-1]["top"]) > 4:
            grouped.append({"top": block["bbox"][1], "blocks": [block]})
        else:
            grouped[-1]["blocks"].append(block)

    lines = []
    previous_top = None
    for group in grouped:
        group["blocks"].sort(key=lambda block: block["bbox"][0])
        segments = []
        previous_right = None
        for block in group["blocks"]:
            if previous_right is not None and block["bbox"][0] - previous_right > 3:
                segments.append({"text": " ", "bold": False, "italic": False})
            segments.extend(block.get("segments") or [{"text": block.get("text", "")}])
            previous_right = block["bbox"][2]
        lines.append({
            "segments": _merge_segments(segments),
            "paragraph_start": previous_top is None or group["top"] - previous_top > 24,
        })
        previous_top = group["top"]
    return lines


def _media_url(media):
    """Version media URLs so replacing a Unit cannot reuse a stale browser image."""
    return f"/api/grammar/library/media/{media.id}?v={media.sha256[:16]}"


def list_published_units():
    units = GrammarUnit.query.filter_by(status="published").order_by(
        GrammarUnit.sort_order, GrammarUnit.unit_number
    ).all()
    book = units[0].book if units else None
    return {
        "book": ({
            "slug": book.slug,
            "title": book.title,
            "edition": book.edition,
            "author": book.author,
        } if book else None),
        "units": [{
            "number": unit.unit_number,
            "title": unit.title,
            "grammar_point": unit.grammar_point,
            "body_page": unit.body_source_page,
            "exercise_page": unit.exercise_source_page,
        } for unit in units],
    }


def get_published_unit(unit_number):
    unit = GrammarUnit.query.filter_by(
        unit_number=unit_number, status="published"
    ).first()
    if unit is None:
        return None

    media_by_id = {
        media.id: media
        for media in GrammarMedia.query.filter_by(unit_id=unit.id).all()
    }
    body = []
    for block in sorted(unit.content_blocks, key=lambda item: item.sort_order):
        if block.block_type != "section":
            continue
        content = block.content_json
        media_ids = [
            media_id for media_id in content.get("media_ids", [])
            if media_id in media_by_id
        ]
        body.append({
            "label": content.get("label", ""),
            "heading": content.get("heading", ""),
            "lines": _source_lines(
                content.get("source_blocks", []),
                content.get("label", ""),
                content.get("heading_range", [0, 0]),
            ),
            "media": [{
                "id": media_id,
                "url": _media_url(media_by_id[media_id]),
                "alt": media_by_id[media_id].alt_text,
                "width": media_by_id[media_id].width,
                "height": media_by_id[media_id].height,
            } for media_id in media_ids],
        })

    exercises = []
    for exercise in sorted(unit.exercises, key=lambda item: item.sort_order):
        metadata = exercise.word_bank_json or {}
        exercise_media = [
            media_id for media_id in metadata.get("media_ids", [])
            if media_id in media_by_id
        ]
        questions = []
        for question in sorted(exercise.questions, key=lambda item: item.sort_order):
            slots = []
            for slot in sorted(question.answer_slots, key=lambda item: item.slot_order):
                slots.append({
                    "key": slot.slot_key,
                    "answer_key": (
                        f"u{unit.unit_number}-{exercise.exercise_number}-"
                        f"{question.question_number}"
                        + (f"-{slot.slot_key}" if slot.slot_key != "answer-1" else "")
                    ),
                    "type": slot.answer_type,
                })
            serialized = {
                "id": question.id,
                "number": question.question_number,
                "type": question.question_type,
                "is_example": question.is_example,
                "content": question.content_json,
                "slots": slots,
            }
            # Printed examples are part of the question page and are safe to show.
            if question.is_example and question.solution:
                serialized["example_answer"] = question.solution.display_answer
            questions.append(serialized)
        exercises.append({
            "id": exercise.id,
            "number": exercise.exercise_number,
            "instruction": exercise.instruction,
            "type": exercise.exercise_type,
            "word_bank": metadata.get("words", []),
            "options": metadata.get("options", []),
            "media": [{
                "id": media_id,
                "url": _media_url(media_by_id[media_id]),
                "alt": media_by_id[media_id].alt_text,
                "width": media_by_id[media_id].width,
                "height": media_by_id[media_id].height,
            } for media_id in exercise_media],
            "questions": questions,
        })

    return {
        "edition": unit.book.edition,
        "number": unit.unit_number,
        "title": unit.title,
        "grammar_point": unit.grammar_point,
        "body_page": unit.body_source_page,
        "exercise_page": unit.exercise_source_page,
        "body": body,
        "exercises": exercises,
    }


def get_published_media(media_id):
    media = db.session.get(GrammarMedia, media_id)
    if media is None or media.unit is None or media.unit.status != "published":
        return None
    return media
