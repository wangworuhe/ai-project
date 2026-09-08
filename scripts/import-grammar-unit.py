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
    parser.add_argument("--replace", action="store_true", help="replace an already imported Unit")
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
) -> dict[str, int]:
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
    existing = GrammarUnit.query.filter_by(book_id=book.id, unit_number=number).first()
    if existing and not replace:
        raise ValueError(f"Unit {number} already exists; use --replace to rebuild it")
    if existing:
        for item in list(existing.media):
            db.session.delete(item)
        db.session.delete(existing)
        db.session.flush()

    unit = GrammarUnit(
        book=book,
        unit_number=number,
        title=unit_data["title"],
        grammar_point=unit_data["grammar_point"],
        body_source_page=unit_data["body_page"],
        exercise_source_page=unit_data["exercise_page"],
        sort_order=unit_data["sort_order"],
        status=status_override or unit_data["status"],
    )
    db.session.add(unit)

    media_by_key: dict[str, GrammarMedia] = {}
    for key, definition in package["media"].items():
        data = crop_jpeg(
            cache / "renders" / f"page-{definition['page']:03d}.jpg",
            definition["crop"],
        )
        item = GrammarMedia(
            book=book,
            unit=unit,
            mime_type="image/jpeg",
            content_blob=data,
            width=definition["crop"]["width"],
            height=definition["crop"]["height"],
            sha256=hashlib.sha256(data).hexdigest(),
            alt_text=definition["alt"],
            source_page=definition["page"],
            source_bbox={"coordinate_space": "render-96dpi", **definition["crop"]},
        )
        db.session.add(item)
        media_by_key[key] = item
    db.session.flush()

    body = package["body"]
    heading_start, heading_end = body["heading_range"]
    page, heading_blocks = source_blocks(cache, body["page"], heading_start, heading_end)
    unit.content_blocks.append(GrammarContentBlock(
        section="body",
        block_type="heading",
        content_json={"text": unit.title, "source_blocks": heading_blocks},
        source_page=body["page"],
        source_bbox=[0, heading_start, page["width"], heading_end],
        sort_order=0,
    ))
    for order, section in enumerate(body["sections"], start=1):
        start, end = section["range"]
        page, blocks = source_blocks(cache, body["page"], start, end)
        imported_text = " ".join(block.get("text", "") for block in blocks)
        if _heading_key(section["heading"]) not in _heading_key(imported_text):
            raise ValueError(
                f"Unit {number} section {section['label']} is missing its reviewed heading"
            )
        unit.content_blocks.append(GrammarContentBlock(
            section="body",
            block_type="section",
            content_json={
                "label": section["label"],
                "heading": section["heading"],
                "heading_range": section["heading_range"],
                "source_blocks": blocks,
                "media_ids": [media_by_key[key].id for key in section["media"]],
            },
            source_page=body["page"],
            source_bbox=[0, start, page["width"], end],
            sort_order=order,
        ))

    verified_at = datetime.now(timezone.utc).replace(tzinfo=None)
    answer_key_by_item = {
        (entry.exercise_number, entry.item_number): entry
        for entry in GrammarAnswerKeyEntry.query.filter_by(
            book_id=book.id,
            unit_number=number,
        ).all()
    }
    for exercise_order, exercise_data in enumerate(package["exercises"], start=1):
        exercise = GrammarExercise(
            unit=unit,
            exercise_number=exercise_data["number"],
            instruction=exercise_data["instruction"],
            exercise_type=exercise_data["type"],
            word_bank_json={
                "words": exercise_data["word_bank"],
                "options": exercise_data["options"],
                "media_ids": [media_by_key[key].id for key in exercise_data["media"]],
            },
            source_page=exercise_data["source_page"],
            sort_order=exercise_order,
        )
        db.session.add(exercise)
        for question_order, question_data in enumerate(exercise_data["questions"], start=1):
            answer_key = answer_key_by_item.get((
                exercise_data["number"], question_data["number"]
            ))
            if not question_data["example"] and answer_key is None:
                raise ValueError(
                    f"No answer-key entry for UNIT {number} / "
                    f"{exercise_data['number']} / {question_data['number']}"
                )
            question = GrammarQuestion(
                exercise=exercise,
                question_number=question_data["number"],
                question_type=question_data["type"],
                content_json=question_data["content"],
                sort_order=question_order,
                is_example=question_data["example"],
                source_page=question_data["source_page"],
            )
            db.session.add(question)
            for slot_data in question_data["slots"]:
                question.answer_slots.append(GrammarAnswerSlot(
                    slot_key=slot_data["key"],
                    slot_order=slot_data["order"],
                    answer_type=slot_data["type"],
                    normalization_rule=slot_data["normalization"],
                    points=slot_data["points"],
                ))
            solution_data = question_data.get("solution")
            if solution_data is None:
                solution_data = solution_from_answer_key(question_data, answer_key)
            solution = GrammarSolution(
                question=question,
                answer_key_entry=answer_key,
                answer_kind=solution_data["kind"],
                display_answer=solution_data["display_answer"],
                grading_mode=solution_data["grading_mode"],
                is_example=question_data["example"],
                note=solution_data.get("note"),
                source_page=solution_data["source_page"],
                source_label=solution_data["source_label"],
                verification_status=solution_data["verification_status"],
                verified_at=(
                    verified_at if solution_data["verification_status"] == "verified" else None
                ),
            )
            db.session.add(solution)
            for variant_order, variant_data in enumerate(solution_data["variants"], start=1):
                solution.variants.append(GrammarAnswerVariant(
                    variant_order=variant_order,
                    values_json=variant_data["values"],
                    is_primary=variant_data["primary"],
                    source_text=variant_data["source_text"],
                ))

    db.session.commit()
    questions = [question for exercise in unit.exercises for question in exercise.questions]
    return {
        "books": 1,
        "units": 1,
        "content_blocks": len(unit.content_blocks),
        "media": len(unit.media),
        "exercises": len(unit.exercises),
        "questions": len(questions),
        "answer_slots": sum(len(question.answer_slots) for question in questions),
        "answerable_slots": sum(
            len(question.answer_slots) for question in questions if not question.is_example
        ),
        "solutions": sum(question.solution is not None for question in questions),
        "answer_variants": sum(len(question.solution.variants) for question in questions),
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
