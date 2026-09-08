#!/usr/bin/env python3
"""Parse and incrementally import the complete Key to Exercises into SQLite."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend import create_app
from backend.extensions import db
from backend.models import GrammarAnswerKeyEntry, GrammarBook, GrammarSolution
from config.config import Config


CACHE_ROOT = PROJECT_ROOT / "storage" / "grammar" / "source-cache"
BOOK_SLUG = "english-grammar-in-use"
BOOK_EDITION = "fifth-edition"
FIRST_SOURCE_PAGE = 348
LAST_SOURCE_PAGE = 379
PRINTED_PAGE_OFFSET = 12
PARSER_VERSION = "key-to-exercises-v1"
EXPECTED_UNIT_COUNT = 145
EXPECTED_EXERCISE_COUNT = 566
EXPECTED_ENTRY_COUNT = 3941
Y_LINE_TOLERANCE = 1.3
COLUMNS = ((0, 320), (320, 550), (550, float("inf")))


@dataclass
class ParsedEntry:
    unit_number: int
    exercise_number: str
    item_number: str
    answer_text: str
    source_page: int
    source_blocks: list[dict[str, Any]] = field(default_factory=list)
    is_example_answer: bool = False
    parse_warnings: list[str] = field(default_factory=list)

    @property
    def source_label(self) -> str:
        return (
            f"UNIT {self.unit_number} / {self.exercise_number} / "
            f"{self.item_number}"
        )

    @property
    def content_sha256(self) -> str:
        payload = json.dumps(
            {
                "answer_text": self.answer_text,
                "source_blocks": self.source_blocks,
                "is_example_answer": self.is_example_answer,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--unit-start", type=int, default=1)
    parser.add_argument("--unit-end", type=int, default=EXPECTED_UNIT_COUNT)
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--replace", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--audit-only", action="store_true")
    return parser.parse_args()


def find_cache(explicit: Path | None) -> tuple[Path, dict[str, Any]]:
    candidates = [explicit.expanduser().resolve()] if explicit else [
        path.parent for path in CACHE_ROOT.glob("*/manifest.json")
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


def clean_text(text: str) -> str:
    text = " ".join(text.split())
    text = re.sub(r"\s+([,.;:?!\)])", r"\1", text)
    text = re.sub(r"([\(])\s+", r"\1", text)
    return text.strip()


def join_blocks(blocks: list[dict[str, Any]]) -> str:
    text = ""
    previous_right = None
    for block in sorted(blocks, key=lambda item: item["bbox"][0]):
        value = block.get("text", "").replace("\n", " ")
        if not value.strip():
            continue
        left, _, right, _ = block["bbox"]
        if (
            text
            and previous_right is not None
            and left - previous_right > 2
            and not text[-1].isspace()
            and not value[0].isspace()
        ):
            text += " "
        text += value
        previous_right = right
    return clean_text(text)


def is_item_start(text: str) -> bool:
    return bool(re.match(r"^\d+\s", text) or re.fullmatch(r"\d+", text))


def page_lines(cache: Path, page_number: int) -> list[dict[str, Any]]:
    page_path = cache / "pages" / f"page-{page_number:03d}.json"
    if not page_path.is_file():
        raise ValueError(f"Missing cached page: {page_path}")
    page = json.loads(page_path.read_text(encoding="utf-8"))
    result = []
    for column_index, (left_bound, right_bound) in enumerate(COLUMNS):
        blocks = []
        for block in page["text_blocks"]:
            left, top, _, _ = block["bbox"]
            text = clean_text(block.get("text", ""))
            if not (left_bound <= left < right_bound and 65 <= top <= 1080):
                continue
            if not text or text == "Key to Exercises":
                continue
            if "facebook.com/" in text or "vk.com/" in text:
                continue
            blocks.append(block)
        blocks.sort(key=lambda item: (item["bbox"][1], item["bbox"][0]))

        baselines: list[list[dict[str, Any]]] = []
        for block in blocks:
            if (
                not baselines
                or abs(block["bbox"][1] - baselines[-1][0]["bbox"][1])
                > Y_LINE_TOLERANCE
            ):
                baselines.append([block])
            else:
                baselines[-1].append(block)

        for baseline in baselines:
            baseline.sort(key=lambda item: item["bbox"][0])
            starts = [
                index
                for index, block in enumerate(baseline)
                if is_item_start(clean_text(block.get("text", "")))
            ]
            groups = []
            if len(starts) > 1:
                if starts[0] > 0:
                    groups.append(baseline[:starts[0]])
                boundaries = starts + [len(baseline)]
                groups.extend(
                    baseline[start:end]
                    for start, end in zip(boundaries, boundaries[1:])
                )
            else:
                groups = [baseline]
            for group in groups:
                if not group:
                    continue
                result.append({
                    "page": page_number,
                    "printed_page": page_number - PRINTED_PAGE_OFFSET,
                    "column": column_index + 1,
                    "top": min(block["bbox"][1] for block in group),
                    "text": join_blocks(group),
                    "blocks": [{
                        "page": page_number,
                        "bbox": [round(value, 4) for value in block["bbox"]],
                        "text": clean_text(block.get("text", "")),
                    } for block in group],
                })
    return result


def parse_answer_key(cache: Path) -> list[ParsedEntry]:
    unit_number = None
    exercise_number = None
    current: ParsedEntry | None = None
    example_mode = False
    entries: list[ParsedEntry] = []
    entries_by_key: dict[tuple[int, str, str], ParsedEntry] = {}
    exercises = set()
    units = set()

    for page_number in range(FIRST_SOURCE_PAGE, LAST_SOURCE_PAGE + 1):
        for line in page_lines(cache, page_number):
            text = line["text"]
            unit_match = re.fullmatch(r"UNIT\s+(\d+)", text, re.IGNORECASE)
            if unit_match:
                unit_number = int(unit_match.group(1))
                units.add(unit_number)
                exercise_number = None
                current = None
                example_mode = False
                continue

            exercise_match = re.fullmatch(r"(\d{1,3})\.(\d+)", text)
            if exercise_match:
                exercise_number = text
                exercises.add((unit_number, exercise_number))
                current = None
                example_mode = False
                continue

            if text.lower().startswith("example answer") and not re.match(r"^\d+", text):
                example_mode = True
                current = None
                continue

            item_match = re.match(r"^(\d+)\s*(.*)$", text)
            if item_match and unit_number is not None and exercise_number is not None:
                item_number = item_match.group(1)
                answer_text = item_match.group(2).strip()
                key = (unit_number, exercise_number, item_number)
                if key in entries_by_key:
                    if current is None:
                        raise ValueError(f"Detached numeric continuation: {key}")
                    continuation = (
                        answer_text
                        if (
                            current.unit_number,
                            current.exercise_number,
                            current.item_number,
                        ) == key
                        else text
                    )
                    current.answer_text = clean_text(
                        f"{current.answer_text} {continuation}"
                    )
                    current.source_blocks.extend(line["blocks"])
                    current.parse_warnings.append("numeric-continuation")
                    continue
                current = ParsedEntry(
                    unit_number=unit_number,
                    exercise_number=exercise_number,
                    item_number=item_number,
                    answer_text=answer_text,
                    source_page=page_number,
                    source_blocks=list(line["blocks"]),
                    is_example_answer=(
                        example_mode or "example answer" in answer_text.lower()
                    ),
                )
                entries.append(current)
                entries_by_key[key] = current
                continue

            if current is not None:
                current.answer_text = clean_text(f"{current.answer_text} {text}")
                current.source_blocks.extend(line["blocks"])

    validate_parsed(entries, units, exercises)
    return entries


def validate_parsed(entries, units, exercises) -> None:
    expected_units = set(range(1, EXPECTED_UNIT_COUNT + 1))
    if units != expected_units:
        raise ValueError(f"Unit coverage mismatch: {sorted(expected_units - units)} missing")
    if len(exercises) != EXPECTED_EXERCISE_COUNT:
        raise ValueError(
            f"Expected {EXPECTED_EXERCISE_COUNT} exercises, parsed {len(exercises)}"
        )
    if len(entries) != EXPECTED_ENTRY_COUNT:
        raise ValueError(
            f"Expected {EXPECTED_ENTRY_COUNT} answer entries, parsed {len(entries)}"
        )
    keys = [
        (entry.unit_number, entry.exercise_number, entry.item_number)
        for entry in entries
    ]
    if len(keys) != len(set(keys)):
        raise ValueError("Parsed answer keys are not unique")
    if any(not entry.answer_text for entry in entries):
        raise ValueError("One or more parsed answers are empty")
    if any(
        not entry.exercise_number.startswith(f"{entry.unit_number}.")
        for entry in entries
    ):
        raise ValueError("An exercise was associated with the wrong Unit")

    anchors = {
        (1, "1.1", "2"): "He’s tying / He is tying",
        (2, "2.2", "8"): "takes … does it take",
        (32, "32.4", "4"): "3 am",
        (121, "121.1", "20"): "5 o’clock",
        (145, "145.4", "6"): "called back / called me back",
    }
    by_key = {
        (entry.unit_number, entry.exercise_number, entry.item_number): entry
        for entry in entries
    }
    for key, expected_text in anchors.items():
        if expected_text not in by_key[key].answer_text:
            raise ValueError(f"Anchor validation failed for {key}: {expected_text}")


def answer_json(entry: ParsedEntry) -> dict[str, Any]:
    return {
        "raw": entry.answer_text,
        "has_alternatives": " / " in entry.answer_text or " or " in entry.answer_text,
        "has_multiple_parts": "…" in entry.answer_text,
        "parse_warnings": entry.parse_warnings,
    }


def import_entries(
    entries: list[ParsedEntry],
    manifest: dict[str, Any],
    unit_start: int,
    unit_end: int,
    replace: bool,
) -> dict[str, int]:
    book = GrammarBook.query.filter_by(slug=BOOK_SLUG, edition=BOOK_EDITION).first()
    if book is None:
        raise ValueError("Import the grammar book record before importing its answer key")
    source = manifest["source"]
    if book.source_sha256 != source["sha256"]:
        raise ValueError("Answer cache does not match the database book source")

    selected = [
        entry for entry in entries
        if unit_start <= entry.unit_number <= unit_end
    ]
    existing_rows = GrammarAnswerKeyEntry.query.filter(
        GrammarAnswerKeyEntry.book_id == book.id,
        GrammarAnswerKeyEntry.unit_number >= unit_start,
        GrammarAnswerKeyEntry.unit_number <= unit_end,
    ).all()
    existing_by_key = {
        (row.unit_number, row.exercise_number, row.item_number): row
        for row in existing_rows
    }
    parsed_keys = set()
    inserted = updated = unchanged = removed = 0
    verified_at = datetime.now(timezone.utc).replace(tzinfo=None)

    for entry in selected:
        key = (entry.unit_number, entry.exercise_number, entry.item_number)
        parsed_keys.add(key)
        row = existing_by_key.get(key)
        if row is None:
            row = GrammarAnswerKeyEntry(book=book)
            db.session.add(row)
            inserted += 1
        elif row.content_sha256 == entry.content_sha256:
            unchanged += 1
            continue
        elif not replace:
            raise ValueError(
                f"Answer {entry.source_label} changed; rerun this range with --replace"
            )
        else:
            updated += 1

        row.unit_number = entry.unit_number
        row.exercise_number = entry.exercise_number
        row.item_number = entry.item_number
        row.answer_text = entry.answer_text
        row.answer_json = answer_json(entry)
        row.is_example_answer = entry.is_example_answer
        row.source_page = entry.source_page
        row.source_printed_page = entry.source_page - PRINTED_PAGE_OFFSET
        row.source_label = entry.source_label
        row.source_blocks_json = entry.source_blocks
        row.parser_version = PARSER_VERSION
        row.content_sha256 = entry.content_sha256
        row.verification_status = "parsed"
        row.updated_at = verified_at

    stale_rows = [
        row for key, row in existing_by_key.items()
        if key not in parsed_keys
    ]
    if stale_rows and not replace:
        raise ValueError(
            f"{len(stale_rows)} stale rows exist in this range; rerun with --replace"
        )
    for row in stale_rows:
        if row.solution is not None:
            row.solution.answer_key_entry = None
        db.session.delete(row)
        removed += 1

    db.session.flush()
    key_rows = GrammarAnswerKeyEntry.query.filter_by(book_id=book.id).all()
    key_by_business_key = {
        (row.unit_number, row.exercise_number, row.item_number): row
        for row in key_rows
    }
    linked = 0
    solutions = GrammarSolution.query.join(GrammarSolution.question).all()
    for solution in solutions:
        question = solution.question
        exercise = question.exercise
        unit = exercise.unit
        if question.is_example:
            continue
        key_row = key_by_business_key.get((
            unit.unit_number,
            exercise.exercise_number,
            question.question_number,
        ))
        if key_row is not None:
            solution.answer_key_entry = key_row
            linked += 1
    db.session.commit()
    return {
        "selected": len(selected),
        "inserted": inserted,
        "updated": updated,
        "unchanged": unchanged,
        "removed": removed,
        "linked_solutions": linked,
    }


def audit_database() -> dict[str, Any]:
    book = GrammarBook.query.filter_by(slug=BOOK_SLUG, edition=BOOK_EDITION).first()
    if book is None:
        raise ValueError("Grammar book record is missing")
    rows = GrammarAnswerKeyEntry.query.filter_by(book_id=book.id).all()
    keys = [(row.unit_number, row.exercise_number, row.item_number) for row in rows]
    if len(rows) != EXPECTED_ENTRY_COUNT:
        raise ValueError(f"Database contains {len(rows)} answers, expected {EXPECTED_ENTRY_COUNT}")
    if len(keys) != len(set(keys)):
        raise ValueError("Database contains duplicate answer business keys")
    if {row.unit_number for row in rows} != set(range(1, EXPECTED_UNIT_COUNT + 1)):
        raise ValueError("Database Unit coverage is incomplete")
    exercises = {(row.unit_number, row.exercise_number) for row in rows}
    if len(exercises) != EXPECTED_EXERCISE_COUNT:
        raise ValueError("Database exercise coverage is incomplete")
    if any(not row.answer_text.strip() for row in rows):
        raise ValueError("Database contains an empty answer")
    if any(
        row.content_sha256 != hashlib.sha256(json.dumps(
            {
                "answer_text": row.answer_text,
                "source_blocks": row.source_blocks_json,
                "is_example_answer": row.is_example_answer,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")).hexdigest()
        for row in rows
    ):
        raise ValueError("One or more answer content hashes do not match")
    linked = GrammarSolution.query.filter(
        GrammarSolution.answer_key_entry_id.isnot(None)
    ).count()
    return {
        "answers": len(rows),
        "units": len({row.unit_number for row in rows}),
        "exercises": len(exercises),
        "source_pages": [
            min(row.source_page for row in rows),
            max(row.source_page for row in rows),
        ],
        "printed_pages": [
            min(row.source_printed_page for row in rows),
            max(row.source_printed_page for row in rows),
        ],
        "linked_solutions": linked,
        "empty_answers": 0,
        "duplicate_keys": 0,
        "hash_mismatches": 0,
    }


def main() -> int:
    args = parse_args()
    if not 1 <= args.unit_start <= args.unit_end <= EXPECTED_UNIT_COUNT:
        raise SystemExit("Unit range must satisfy 1 <= start <= end <= 145")
    cache, manifest = find_cache(args.cache)
    entries = parse_answer_key(cache)
    print(json.dumps({
        "parser": PARSER_VERSION,
        "answers": len(entries),
        "units": len({entry.unit_number for entry in entries}),
        "exercises": len({
            (entry.unit_number, entry.exercise_number) for entry in entries
        }),
        "source_pages": [FIRST_SOURCE_PAGE, LAST_SOURCE_PAGE],
    }, ensure_ascii=False, indent=2))
    if args.validate_only:
        return 0

    app = create_app()
    with app.app_context():
        if args.audit_only:
            result = audit_database()
        else:
            result = import_entries(
                entries,
                manifest,
                args.unit_start,
                args.unit_end,
                args.replace,
            )
    print(f"Database: {Config.DATABASE_PATH}")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
