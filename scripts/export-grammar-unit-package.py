#!/usr/bin/env python3
"""Export one reviewed database unit as a reusable import package."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend import create_app
from backend.models import GrammarUnit


DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "storage" / "grammar" / "import-packages"


def json_number(value):
    number = float(value)
    return int(number) if number.is_integer() else number


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--unit", type=int, required=True)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def stable_media_keys(unit: GrammarUnit) -> tuple[dict[int, str], dict[str, dict]]:
    keys: dict[int, str] = {}
    definitions: dict[str, dict] = {}

    def register(media_id: int, prefix: str) -> str:
        if media_id in keys:
            return keys[media_id]
        media = next(item for item in unit.media if item.id == media_id)
        key = prefix
        suffix = 2
        while key in definitions:
            key = f"{prefix}-{suffix}"
            suffix += 1
        bbox = media.source_bbox or {}
        keys[media_id] = key
        definitions[key] = {
            "page": media.source_page,
            "crop": {name: int(bbox[name]) for name in ("x", "y", "width", "height")},
            "alt": media.alt_text or key,
        }
        return key

    for block in sorted(unit.content_blocks, key=lambda item: item.sort_order):
        if block.block_type != "section":
            continue
        label = block.content_json.get("label", block.section).lower()
        for index, media_id in enumerate(block.content_json.get("media_ids", []), start=1):
            register(media_id, f"body-{label}-{index}")
    for exercise in sorted(unit.exercises, key=lambda item: item.sort_order):
        metadata = exercise.word_bank_json or {}
        for index, media_id in enumerate(metadata.get("media_ids", []), start=1):
            register(media_id, f"exercise-{exercise.exercise_number}-{index}")
    return keys, definitions


def export_unit(unit: GrammarUnit) -> dict:
    media_keys, media = stable_media_keys(unit)
    heading = next(
        block for block in unit.content_blocks if block.block_type == "heading"
    )
    sections = []
    for block in sorted(unit.content_blocks, key=lambda item: item.sort_order):
        if block.block_type != "section":
            continue
        sections.append({
            "label": block.content_json["label"],
            "range": [block.source_bbox[1], block.source_bbox[3]],
            "heading_range": block.content_json["heading_range"],
            "heading": block.content_json["heading"],
            "media": [media_keys[item] for item in block.content_json.get("media_ids", [])],
        })

    exercises = []
    for exercise in sorted(unit.exercises, key=lambda item: item.sort_order):
        metadata = exercise.word_bank_json or {}
        questions = []
        for question in sorted(exercise.questions, key=lambda item: item.sort_order):
            content = dict(question.content_json)
            content.pop("media_id", None)
            solution = question.solution
            questions.append({
                "number": question.question_number,
                "type": question.question_type,
                "example": question.is_example,
                "source_page": question.source_page,
                "content": content,
                "slots": [{
                    "key": slot.slot_key,
                    "order": slot.slot_order,
                    "type": slot.answer_type,
                    "normalization": slot.normalization_rule,
                    "points": json_number(slot.points),
                } for slot in sorted(question.answer_slots, key=lambda item: item.slot_order)],
                "solution": {
                    "kind": solution.answer_kind,
                    "display_answer": solution.display_answer,
                    "grading_mode": solution.grading_mode,
                    "note": solution.note,
                    "source_page": solution.source_page,
                    "source_label": solution.source_label,
                    "verification_status": solution.verification_status,
                    "variants": [{
                        "values": variant.values_json,
                        "primary": variant.is_primary,
                        "source_text": variant.source_text,
                    } for variant in sorted(solution.variants, key=lambda item: item.variant_order)],
                },
            })
        exercises.append({
            "number": exercise.exercise_number,
            "instruction": exercise.instruction,
            "type": exercise.exercise_type,
            "source_page": exercise.source_page,
            "word_bank": metadata.get("words", []),
            "options": metadata.get("options", []),
            "media": [media_keys[item] for item in metadata.get("media_ids", [])],
            "questions": questions,
        })

    return {
        "schema_version": 1,
        "book": {
            "slug": unit.book.slug,
            "title": unit.book.title,
            "edition": unit.book.edition,
            "author": unit.book.author,
        },
        "unit": {
            "number": unit.unit_number,
            "title": unit.title,
            "grammar_point": unit.grammar_point,
            "body_page": unit.body_source_page,
            "exercise_page": unit.exercise_source_page,
            "sort_order": unit.sort_order,
            "status": unit.status,
        },
        "media": media,
        "body": {
            "page": unit.body_source_page,
            "heading_range": [heading.source_bbox[1], heading.source_bbox[3]],
            "sections": sections,
        },
        "exercises": exercises,
    }


def main() -> int:
    args = parse_args()
    output = args.output or DEFAULT_OUTPUT_DIR / f"unit-{args.unit:03d}.json"
    app = create_app()
    with app.app_context():
        unit = GrammarUnit.query.filter_by(unit_number=args.unit).first()
        if unit is None:
            raise SystemExit(f"Unit {args.unit} is not in the database")
        package = export_unit(unit)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
