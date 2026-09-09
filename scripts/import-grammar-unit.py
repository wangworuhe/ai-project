#!/usr/bin/env python3
"""Validate and import a versioned grammar Unit package into SQLite."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend import create_app
from backend.extensions import db
from backend.models import (
    GrammarAnswerKeyEntry,
    GrammarAnswerSlot,
    GrammarAnswerVariant,
    GrammarBook,
    GrammarContentBlock,
    GrammarExercise,
    GrammarMedia,
    GrammarQuestion,
    GrammarSolution,
    GrammarUnit,
)
from config.config import Config


DEFAULT_CACHE_ROOT = PROJECT_ROOT / "storage" / "grammar" / "source-cache"
DEFAULT_PACKAGE_ROOT = PROJECT_ROOT / "storage" / "grammar" / "import-packages"
SCHEMA_PATH = PROJECT_ROOT / "schemas" / "grammar-unit.schema.json"
SUPPORTED_EXERCISE_TYPES = frozenset({"fill", "matching", "picture-fill", "rewrite"})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--unit", type=int, help="load unit-NNN.json from the package directory")
    source.add_argument("--package", type=Path, help="explicit Unit package path")
    parser.add_argument("--cache", type=Path, help="specific completed source-cache directory")
    parser.add_argument(
        "--replace",
        action="store_true",
        help="update an already imported Unit in place while preserving stable record IDs",
    )
    parser.add_argument("--validate-only", action="store_true", help="validate without changing SQLite")
    parser.add_argument(
        "--status", choices=("importing", "reviewed", "published"),
        help="override the package publication status",
    )
    return parser.parse_args()


def package_path(args: argparse.Namespace) -> Path:
    path = args.package if args.package else DEFAULT_PACKAGE_ROOT / f"unit-{args.unit:03d}.json"
    path = path.expanduser().resolve()
    if not path.is_file():
        raise SystemExit(f"Unit package was not found: {path}")
    return path


def _normalized(text: str) -> str:
    return " ".join(text.split())


def _without_whitespace(text: str) -> str:
    return re.sub(r"\s+", "", text)


def _heading_key(text: str) -> str:
    """Compare headings despite PDF font runs that split a printed word."""
    return "".join(character.lower() for character in text if character.isalnum())


def validate_package(package: dict[str, Any]) -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(schema).iter_errors(package), key=lambda item: list(item.path))
    if errors:
        details = "\n".join(
            f"- {'/'.join(map(str, error.path)) or '<root>'}: {error.message}"
            for error in errors
        )
        raise ValueError(f"Unit package does not match schema v1:\n{details}")

    unit = package["unit"]
    if package["body"]["page"] != unit["body_page"]:
        raise ValueError("body.page must match unit.body_page")

    media_keys = set(package["media"])
    referenced_media = {
        key
        for section in package["body"]["sections"]
        for key in section["media"]
    } | {
        key
        for exercise in package["exercises"]
        for key in exercise["media"]
    }
    missing_media = referenced_media - media_keys
    if missing_media:
        raise ValueError(f"Unknown media keys: {', '.join(sorted(missing_media))}")

    section_labels = [section["label"] for section in package["body"]["sections"]]
    if len(section_labels) != len(set(section_labels)):
        raise ValueError("Body section labels must be unique")

    exercise_numbers = [exercise["number"] for exercise in package["exercises"]]
    if len(exercise_numbers) != len(set(exercise_numbers)):
        raise ValueError("Exercise numbers must be unique within a Unit")

    for exercise in package["exercises"]:
        if exercise["type"] not in SUPPORTED_EXERCISE_TYPES:
            raise ValueError(
                f"Exercise {exercise['number']} uses unsupported renderer type "
                f"{exercise['type']!r}"
            )
        question_numbers = [question["number"] for question in exercise["questions"]]
        if len(question_numbers) != len(set(question_numbers)):
            raise ValueError(f"Exercise {exercise['number']} has duplicate question numbers")

        for question in exercise["questions"]:
            slot_keys = [slot["key"] for slot in question["slots"]]
            slot_orders = [slot["order"] for slot in question["slots"]]
            if len(slot_keys) != len(set(slot_keys)) or len(slot_orders) != len(set(slot_orders)):
                raise ValueError(
                    f"Exercise {exercise['number']} question {question['number']} "
                    "has duplicate answer slots"
                )
            segments = question["content"].get("segments", [])
            unknown_segments = {
                segment.get("type")
                for segment in segments
                if segment.get("type") not in {"text", "input", "cue"}
            }
            if unknown_segments:
                raise ValueError(
                    f"Exercise {exercise['number']} question {question['number']} "
                    f"has unsupported content segments: {sorted(unknown_segments, key=str)}"
                )

            input_key_list = [
                segment["slot_key"]
                for segment in segments
                if segment.get("type") == "input"
            ]
            input_keys = set(input_key_list)
            if input_keys - set(slot_keys):
                raise ValueError(
                    f"Exercise {exercise['number']} question {question['number']} "
                    "references an undefined answer slot"
                )
            if segments and (
                input_keys != set(slot_keys)
                or len(input_key_list) != len(input_keys)
            ):
                raise ValueError(
                    f"Exercise {exercise['number']} question {question['number']} "
                    "must reference every answer slot exactly once"
                )

            if question["type"] == "fill" and segments:
                rebuilt_prompt = "".join(
                    "___"
                    if segment["type"] == "input"
                    else f"({segment['text']})"
                    if segment["type"] == "cue"
                    else segment["text"]
                    for segment in segments
                )
                if _without_whitespace(rebuilt_prompt) != _without_whitespace(
                    question["content"].get("prompt", "")
                ):
                    raise ValueError(
                        f"Exercise {exercise['number']} question {question['number']} "
                        "content segments do not reconstruct the complete printed prompt"
                    )
            solution = question.get("solution")
            if question["example"] and solution is None:
                raise ValueError(
                    f"Exercise {exercise['number']} question {question['number']} "
                    "is a printed example and must include its displayed solution"
                )
            if solution is not None:
                for variant in solution["variants"]:
                    if set(variant["values"]) != set(slot_keys):
                        raise ValueError(
                            f"Exercise {exercise['number']} question {question['number']} "
                            "solution variant does not cover every answer slot"
                        )


def load_package(path: Path) -> dict[str, Any]:
    package = json.loads(path.read_text(encoding="utf-8"))
    validate_package(package)
    return package


def find_cache(explicit: Path | None) -> tuple[Path, dict[str, Any]]:
    candidates = [explicit.expanduser().resolve()] if explicit else [
        path.parent for path in DEFAULT_CACHE_ROOT.glob("*/manifest.json")
    ]
    completed = []
    for candidate in candidates:
        manifest_path = candidate / "manifest.json"
        if not manifest_path.is_file():
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("status") == "complete" and manifest.get("page_count"):
            completed.append((manifest_path.stat().st_mtime, candidate, manifest))
    if not completed:
        raise SystemExit("No completed grammar source cache was found")
    _, cache, manifest = max(completed, key=lambda item: item[0])
    return cache, manifest


def crop_jpeg(render: Path, crop: dict[str, int]) -> bytes:
    if not shutil.which("sips"):
        raise SystemExit("sips is required to crop media from cached page renders")
    if not render.is_file():
        raise ValueError(f"Cached page render is missing: {render}")
    with tempfile.TemporaryDirectory(prefix="grammar-unit-media-") as directory:
        output = Path(directory) / "crop.jpg"
        subprocess.run(
            [
                "sips", "--cropToHeightWidth", str(crop["height"]), str(crop["width"]),
                "--cropOffset", str(crop["y"]), str(crop["x"]), render, "--out", output,
            ],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        return output.read_bytes()


def source_blocks(cache: Path, page_number: int, start: float, end: float) -> tuple[dict, list]:
    page_path = cache / "pages" / f"page-{page_number:03d}.json"
    if not page_path.is_file():
        raise ValueError(f"Cached page JSON is missing: {page_path}")
    page = json.loads(page_path.read_text(encoding="utf-8"))
    blocks = [
        block for block in page["text_blocks"]
        if start <= block["bbox"][1] < end
    ]
    return page, blocks


def solution_from_answer_key(question_data: dict[str, Any], answer_key) -> dict[str, Any]:
    """Build a conservative reference solution from a pre-imported answer-key row."""
    slots = sorted(question_data["slots"], key=lambda item: item["order"])
    raw_answer = answer_key.answer_text
    if len(slots) == 1:
        parts = [raw_answer]
    else:
        parts = [part.strip() for part in re.split(r"\s*…+\s*", raw_answer)]
        if len(parts) != len(slots) or any(not part for part in parts):
            raise ValueError(
                f"{answer_key.source_label} has {len(slots)} answer slots but its "
                "answer-key text cannot be split safely; provide a reviewed solution "
                "in the Unit package"
            )
    values = {
        slot["key"]: part
        for slot, part in zip(slots, parts)
    }
    return {
        "kind": question_data["type"],
        "display_answer": raw_answer,
        "grading_mode": "reference",
        "note": None,
        "source_page": answer_key.source_page,
        "source_label": answer_key.source_label,
        "verification_status": "pending",
        "variants": [{
            "values": values,
            "primary": True,
            "source_text": raw_answer,
        }],
    }


def import_package(
    package: dict[str, Any],
    cache: Path,
    manifest: dict[str, Any],
    *,
    replace: bool,
    status_override: str | None,
) -> dict[str, int | str]:
    book_data = package["book"]
    unit_data = package["unit"]
    source = manifest["source"]
    book = GrammarBook.query.filter_by(
        slug=book_data["slug"], edition=book_data["edition"]
    ).first()
    if book is None:
        book = GrammarBook(
            slug=book_data["slug"],
            title=book_data["title"],
            edition=book_data["edition"],
            author=book_data["author"],
            source_filename=source["filename"],
            source_sha256=source["sha256"],
            total_pages=manifest["page_count"],
        )
        db.session.add(book)
        db.session.flush()
    else:
        book.title = book_data["title"]
        book.author = book_data["author"]
        book.source_filename = source["filename"]
        book.source_sha256 = source["sha256"]
        book.total_pages = manifest["page_count"]

    number = unit_data["number"]
    unit = GrammarUnit.query.filter_by(book_id=book.id, unit_number=number).first()
    if unit and not replace:
        raise ValueError(f"Unit {number} already exists; use --replace to update it")
    operation = "updated" if unit else "created"
    if unit is None:
        unit = GrammarUnit(book=book, unit_number=number)
        db.session.add(unit)
    unit.title = unit_data["title"]
    unit.grammar_point = unit_data["grammar_point"]
    unit.body_source_page = unit_data["body_page"]
    unit.exercise_source_page = unit_data["exercise_page"]
    unit.sort_order = unit_data["sort_order"]
    unit.status = status_override or unit_data["status"]
    db.session.flush()

    media_by_key: dict[str, GrammarMedia] = {}
    existing_media = {item.asset_key: item for item in unit.media if item.asset_key}
    legacy_media = [item for item in unit.media if not item.asset_key]
    for key, definition in package["media"].items():
        data = crop_jpeg(
            cache / "renders" / f"page-{definition['page']:03d}.jpg",
            definition["crop"],
        )
        digest = hashlib.sha256(data).hexdigest()
        source_bbox = {"coordinate_space": "render-96dpi", **definition["crop"]}
        item = existing_media.pop(key, None)
        if item is None:
            item = next(
                (
                    candidate for candidate in legacy_media
                    if candidate.source_page == definition["page"]
                    and candidate.source_bbox == source_bbox
                ),
                None,
            )
            if item is not None:
                legacy_media.remove(item)
        if item is None:
            previous_key = next(
                (
                    previous_key
                    for previous_key, candidate in existing_media.items()
                    if candidate.sha256 == digest
                ),
                None,
            )
            if previous_key is not None:
                item = existing_media.pop(previous_key)
        if item is None:
            item = GrammarMedia(book=book, unit=unit)
            db.session.add(item)
        item.asset_key = key
        item.mime_type = "image/jpeg"
        item.content_blob = data
        item.width = definition["crop"]["width"]
        item.height = definition["crop"]["height"]
        item.sha256 = digest
        item.alt_text = definition["alt"]
        item.source_page = definition["page"]
        item.source_bbox = source_bbox
        media_by_key[key] = item
    db.session.flush()

    body = package["body"]
    heading_start, heading_end = body["heading_range"]
    page, heading_blocks = source_blocks(cache, body["page"], heading_start, heading_end)
    existing_blocks: dict[str, GrammarContentBlock] = {}
    for block in unit.content_blocks:
        key = "heading" if block.block_type == "heading" else (
            f"section:{(block.content_json or {}).get('label')}"
        )
        existing_blocks[key] = block
        # Free the unique (unit, section, sort_order) values before reordering.
        block.sort_order = -(block.id or 0) - 1
    db.session.flush()

    heading = existing_blocks.pop("heading", None)
    if heading is None:
        heading = GrammarContentBlock(unit=unit)
        db.session.add(heading)
    heading.section = "body"
    heading.block_type = "heading"
    heading.content_json = {"text": unit.title, "source_blocks": heading_blocks}
    heading.source_page = body["page"]
    heading.source_bbox = [0, heading_start, page["width"], heading_end]
    heading.sort_order = 0
    for order, section in enumerate(body["sections"], start=1):
        start, end = section["range"]
        page, blocks = source_blocks(cache, body["page"], start, end)
        imported_text = " ".join(block.get("text", "") for block in blocks)
        if _heading_key(section["heading"]) not in _heading_key(imported_text):
            raise ValueError(
                f"Unit {number} section {section['label']} is missing its reviewed heading"
            )
        block_key = f"section:{section['label']}"
        block = existing_blocks.pop(block_key, None)
        if block is None:
            block = GrammarContentBlock(unit=unit)
            db.session.add(block)
        block.section = "body"
        block.block_type = "section"
        block.content_json = {
            "label": section["label"],
            "heading": section["heading"],
            "heading_range": section["heading_range"],
            "source_blocks": blocks,
            "media_ids": [media_by_key[key].id for key in section["media"]],
        }
        block.source_page = body["page"]
        block.source_bbox = [0, start, page["width"], end]
        block.sort_order = order
    for stale_block in existing_blocks.values():
        db.session.delete(stale_block)

    verified_at = datetime.now(timezone.utc).replace(tzinfo=None)
    answer_key_by_item = {
        (entry.exercise_number, entry.item_number): entry
        for entry in GrammarAnswerKeyEntry.query.filter_by(
            book_id=book.id,
            unit_number=number,
        ).all()
    }
    existing_exercises = {item.exercise_number: item for item in unit.exercises}
    retired_exercises = 0
    retired_questions = 0
    retired_slots = 0
    for exercise_order, exercise_data in enumerate(package["exercises"], start=1):
        exercise = existing_exercises.pop(exercise_data["number"], None)
        if exercise is None:
            exercise = GrammarExercise(unit=unit, exercise_number=exercise_data["number"])
            db.session.add(exercise)
        exercise.instruction = exercise_data["instruction"]
        exercise.exercise_type = exercise_data["type"]
        exercise.word_bank_json = {
            "words": exercise_data["word_bank"],
            "options": exercise_data["options"],
            "media_ids": [media_by_key[key].id for key in exercise_data["media"]],
        }
        exercise.source_page = exercise_data["source_page"]
        exercise.sort_order = exercise_order
        exercise.is_active = True
        db.session.flush()

        existing_questions = {item.question_number: item for item in exercise.questions}
        for question_order, question_data in enumerate(exercise_data["questions"], start=1):
            answer_key = answer_key_by_item.get((
                exercise_data["number"], question_data["number"]
            ))
            if not question_data["example"] and answer_key is None:
                raise ValueError(
                    f"No answer-key entry for UNIT {number} / "
                    f"{exercise_data['number']} / {question_data['number']}"
                )
            question = existing_questions.pop(question_data["number"], None)
            if question is None:
                question = GrammarQuestion(
                    exercise=exercise, question_number=question_data["number"]
                )
                db.session.add(question)
            question.question_type = question_data["type"]
            question.content_json = question_data["content"]
            question.sort_order = question_order
            question.is_example = question_data["example"]
            question.source_page = question_data["source_page"]
            question.source_bbox = None
            question.is_active = True
            db.session.flush()

            existing_slots = {item.slot_key: item for item in question.answer_slots}
            for slot in existing_slots.values():
                # Free the unique slot-order values before a possible reorder.
                slot.slot_order = -(slot.id or 0) - 1
            db.session.flush()
            for slot_data in question_data["slots"]:
                slot = existing_slots.pop(slot_data["key"], None)
                if slot is None:
                    slot = GrammarAnswerSlot(question=question, slot_key=slot_data["key"])
                    db.session.add(slot)
                slot.slot_order = slot_data["order"]
                slot.answer_type = slot_data["type"]
                slot.normalization_rule = slot_data["normalization"]
                slot.points = slot_data["points"]
                slot.is_active = True
            for stale_slot in existing_slots.values():
                stale_slot.is_active = False
                retired_slots += 1

            solution_data = question_data.get("solution")
            if solution_data is None:
                solution_data = solution_from_answer_key(question_data, answer_key)
            solution = question.solution
            if solution is None:
                solution = GrammarSolution(question=question)
                db.session.add(solution)
            solution.answer_key_entry = answer_key
            solution.answer_kind = solution_data["kind"]
            solution.display_answer = solution_data["display_answer"]
            solution.grading_mode = solution_data["grading_mode"]
            solution.is_example = question_data["example"]
            solution.note = solution_data.get("note")
            solution.source_page = solution_data["source_page"]
            solution.source_label = solution_data["source_label"]
            solution.verification_status = solution_data["verification_status"]
            if solution_data["verification_status"] == "verified":
                solution.verified_at = solution.verified_at or verified_at
            else:
                solution.verified_at = None
            db.session.flush()

            existing_variants = {item.variant_order: item for item in solution.variants}
            for variant_order, variant_data in enumerate(solution_data["variants"], start=1):
                variant = existing_variants.pop(variant_order, None)
                if variant is None:
                    variant = GrammarAnswerVariant(
                        solution=solution, variant_order=variant_order
                    )
                    db.session.add(variant)
                variant.values_json = variant_data["values"]
                variant.is_primary = variant_data["primary"]
                variant.source_text = variant_data["source_text"]
            for stale_variant in existing_variants.values():
                db.session.delete(stale_variant)

        for stale_question in existing_questions.values():
            if stale_question.is_active:
                retired_questions += 1
            stale_question.is_active = False
            for slot in stale_question.answer_slots:
                if slot.is_active:
                    retired_slots += 1
                slot.is_active = False

    for stale_exercise in existing_exercises.values():
        if stale_exercise.is_active:
            retired_exercises += 1
        stale_exercise.is_active = False
        for question in stale_exercise.questions:
            if question.is_active:
                retired_questions += 1
            question.is_active = False
            for slot in question.answer_slots:
                if slot.is_active:
                    retired_slots += 1
                slot.is_active = False

    # Media and content blocks are source assets, not user-owned records. Remove
    # assets no longer referenced by the current package after all references
    # have been updated to their stable media IDs.
    for stale_media in [*existing_media.values(), *legacy_media]:
        db.session.delete(stale_media)

    db.session.commit()
    exercises = [exercise for exercise in unit.exercises if exercise.is_active]
    questions = [
        question
        for exercise in exercises
        for question in exercise.questions
        if question.is_active
    ]
    return {
        "operation": operation,
        "books": 1,
        "units": 1,
        "content_blocks": len(unit.content_blocks),
        "media": len(unit.media),
        "exercises": len(exercises),
        "questions": len(questions),
        "answer_slots": sum(
            sum(slot.is_active for slot in question.answer_slots) for question in questions
        ),
        "answerable_slots": sum(
            sum(slot.is_active for slot in question.answer_slots)
            for question in questions if not question.is_example
        ),
        "solutions": sum(question.solution is not None for question in questions),
        "answer_variants": sum(len(question.solution.variants) for question in questions),
        "retired_exercises": retired_exercises,
        "retired_questions": retired_questions,
        "retired_slots": retired_slots,
    }


def main() -> int:
    args = parse_args()
    path = package_path(args)
    package = load_package(path)
    print(f"Validated schema v{package['schema_version']}: {path}")
    if args.validate_only:
        return 0

    cache, manifest = find_cache(args.cache)
    app = create_app()
    with app.app_context():
        try:
            result = import_package(
                package,
                cache,
                manifest,
                replace=args.replace,
                status_override=args.status,
            )
        except Exception:
            db.session.rollback()
            raise
    print(f"Imported Unit {package['unit']['number']} into {Config.DATABASE_PATH}")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
