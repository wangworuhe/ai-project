#!/usr/bin/env python3
"""Deterministically validate one imported grammar Unit and its answer links."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_DATABASE = PROJECT_ROOT / "storage" / "database" / "database.db"
DEFAULT_PACKAGES = PROJECT_ROOT / "storage" / "grammar" / "import-packages"
DEFAULT_CACHE_ROOT = PROJECT_ROOT / "storage" / "grammar" / "source-cache"


class ValidationFailure(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--unit", type=int, required=True)
    parser.add_argument("--package", type=Path)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument(
        "--require-status", choices=("importing", "reviewed", "published")
    )
    return parser.parse_args()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationFailure(message)


def load_package(path: Path, unit_number: int) -> dict[str, Any]:
    require(path.is_file(), f"Unit package is missing: {path}")
    package = json.loads(path.read_text(encoding="utf-8"))
    require(
        package.get("unit", {}).get("number") == unit_number,
        f"Package Unit number does not match --unit {unit_number}",
    )
    command = [
        str(PROJECT_ROOT / ".venv" / "bin" / "python"),
        str(PROJECT_ROOT / "scripts" / "import-grammar-unit.py"),
        "--package",
        str(path),
        "--validate-only",
    ]
    result = subprocess.run(command, cwd=PROJECT_ROOT, text=True, capture_output=True)
    require(
        result.returncode == 0,
        "Package validation failed:\n" + (result.stdout + result.stderr).strip(),
    )
    return package


def completed_cache() -> Path:
    candidates: list[tuple[float, Path]] = []
    for manifest_path in DEFAULT_CACHE_ROOT.glob("*/manifest.json"):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("status") == "complete":
            candidates.append((manifest_path.stat().st_mtime, manifest_path.parent))
    require(bool(candidates), "No completed grammar source cache was found")
    return max(candidates)[1]


def validate_cache(package: dict[str, Any]) -> None:
    cache = completed_cache()
    pages = {package["unit"]["body_page"], package["unit"]["exercise_page"]}
    pages.update(item["page"] for item in package["media"].values())
    for page in pages:
        require(
            (cache / "pages" / f"page-{page:03d}.json").is_file(),
            f"Cached text is missing for PDF page {page}",
        )
        render = cache / "renders" / f"page-{page:03d}.jpg"
        require(render.is_file() and render.stat().st_size > 0, f"Render is missing for PDF page {page}")


def rows_by_key(rows: list[sqlite3.Row], *columns: str) -> dict[tuple[Any, ...], sqlite3.Row]:
    return {tuple(row[column] for column in columns): row for row in rows}


def validate_database(
    connection: sqlite3.Connection,
    package: dict[str, Any],
    required_status: str | None,
) -> dict[str, int | str]:
    unit_data = package["unit"]
    book_data = package["book"]
    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    require(integrity == "ok", f"SQLite integrity_check failed: {integrity}")
    require(not connection.execute("PRAGMA foreign_key_check").fetchall(), "SQLite foreign_key_check failed")

    unit_rows = connection.execute(
        """
        SELECT u.*, b.slug, b.edition
        FROM grammar_units u
        JOIN grammar_books b ON b.id = u.book_id
        WHERE b.slug = ? AND b.edition = ? AND u.unit_number = ?
        """,
        (book_data["slug"], book_data["edition"], unit_data["number"]),
    ).fetchall()
    require(len(unit_rows) == 1, f"Expected one database Unit, found {len(unit_rows)}")
    unit = unit_rows[0]
    require(unit["title"] == unit_data["title"], "Database Unit title differs from package")
    require(unit["body_source_page"] == unit_data["body_page"], "Body source page differs")
    require(unit["exercise_source_page"] == unit_data["exercise_page"], "Exercise source page differs")
    if required_status:
        require(unit["status"] == required_status, f"Unit status is {unit['status']}, expected {required_status}")

    blocks = connection.execute(
        "SELECT * FROM grammar_content_blocks WHERE unit_id = ? ORDER BY sort_order", (unit["id"],)
    ).fetchall()
    require(len(blocks) == len(package["body"]["sections"]) + 1, "Content-block count differs from package")

    exercise_rows = connection.execute(
        "SELECT * FROM grammar_exercises WHERE unit_id = ? ORDER BY sort_order", (unit["id"],)
    ).fetchall()
    exercises = rows_by_key(exercise_rows, "exercise_number")
    expected_exercises = {item["number"]: item for item in package["exercises"]}
    require(set(exercises) == {(key,) for key in expected_exercises}, "Exercise numbers differ from package")

    question_rows = connection.execute(
        """
        SELECT q.*, e.exercise_number
        FROM grammar_questions q
        JOIN grammar_exercises e ON e.id = q.exercise_id
        WHERE e.unit_id = ?
        ORDER BY e.sort_order, q.sort_order
        """,
        (unit["id"],),
    ).fetchall()
    questions = rows_by_key(question_rows, "exercise_number", "question_number")
    expected_questions = {
        (exercise["number"], question["number"]): question
        for exercise in package["exercises"]
        for question in exercise["questions"]
    }
    require(set(questions) == set(expected_questions), "Question keys differ from package")

    expected_slot_count = 0
    non_example_count = 0
    linked_answer_count = 0
    for key, expected in expected_questions.items():
        question = questions[key]
        require(question["question_type"] == expected["type"], f"Question type differs: {key}")
        require(bool(question["is_example"]) == expected["example"], f"Example flag differs: {key}")
        require(question["source_page"] == expected["source_page"], f"Question source page differs: {key}")
        require(json.loads(question["content_json"]) == expected["content"], f"Question content differs: {key}")

        slot_rows = connection.execute(
            "SELECT * FROM grammar_answer_slots WHERE question_id = ? ORDER BY slot_order",
            (question["id"],),
        ).fetchall()
        expected_slots = expected["slots"]
        expected_slot_count += len(expected_slots)
        require(len(slot_rows) == len(expected_slots), f"Answer-slot count differs: {key}")
        for actual, wanted in zip(slot_rows, sorted(expected_slots, key=lambda item: item["order"])):
            require(actual["slot_key"] == wanted["key"], f"Answer-slot key differs: {key}")
            require(actual["slot_order"] == wanted["order"], f"Answer-slot order differs: {key}")

        solution_rows = connection.execute(
            """
            SELECT s.*, k.book_id AS key_book_id, k.unit_number AS key_unit_number,
                   k.exercise_number AS key_exercise_number, k.item_number AS key_item_number,
                   k.answer_text AS key_answer_text
            FROM grammar_solutions s
            LEFT JOIN grammar_answer_key_entries k ON k.id = s.answer_key_entry_id
            WHERE s.question_id = ?
            """,
            (question["id"],),
        ).fetchall()
        require(len(solution_rows) == 1, f"Expected one solution: {key}")
        solution = solution_rows[0]
        if not expected["example"]:
            non_example_count += 1
            require(solution["answer_key_entry_id"] is not None, f"Missing answer-key link: {key}")
            require(solution["key_book_id"] == unit["book_id"], f"Answer key belongs to another book: {key}")
            require(solution["key_unit_number"] == unit_data["number"], f"Answer key Unit differs: {key}")
            require(solution["key_exercise_number"] == key[0], f"Answer key exercise differs: {key}")
            require(solution["key_item_number"] == key[1], f"Answer key item differs: {key}")
            require(bool(solution["key_answer_text"].strip()), f"Answer key is empty: {key}")
            linked_answer_count += 1

    media_rows = connection.execute(
        "SELECT * FROM grammar_media WHERE unit_id = ?", (unit["id"],)
    ).fetchall()
    require(len(media_rows) == len(package["media"]), "Media count differs from package")
    for media in media_rows:
        require(bool(media["content_blob"]), f"Media {media['id']} has an empty blob")
        require(
            hashlib.sha256(media["content_blob"]).hexdigest() == media["sha256"],
            f"Media {media['id']} SHA256 differs",
        )

    return {
        "status": unit["status"],
        "content_blocks": len(blocks),
        "media": len(media_rows),
        "exercises": len(exercise_rows),
        "questions": len(question_rows),
        "answer_slots": expected_slot_count,
        "non_example_questions": non_example_count,
        "linked_answers": linked_answer_count,
    }


def main() -> int:
    args = parse_args()
    package_path = (args.package or DEFAULT_PACKAGES / f"unit-{args.unit:03d}.json").resolve()
    database_path = args.database.expanduser().resolve()
    try:
        package = load_package(package_path, args.unit)
        validate_cache(package)
        require(database_path.is_file(), f"Database is missing: {database_path}")
        connection = sqlite3.connect(database_path)
        connection.row_factory = sqlite3.Row
        try:
            counts = validate_database(connection, package, args.require_status)
        finally:
            connection.close()
    except (ValidationFailure, json.JSONDecodeError, sqlite3.Error) as exc:
        print(json.dumps({"result": "FAIL", "unit": args.unit, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1

    print(json.dumps({"result": "PASS", "unit": args.unit, **counts}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
