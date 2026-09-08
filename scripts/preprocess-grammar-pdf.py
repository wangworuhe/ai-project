#!/usr/bin/env python3
"""Build a reusable, indexed extraction cache for the grammar source PDF.

The cache is deliberately separate from the published grammar tables.  It keeps
source-faithful text, positions, font metadata, images, page renders, and search
indexes so later import/review passes do not need to parse the PDF again.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = Path(
    "/Users/yala/Documents/04-Resources/MacShare/"
    "English Grammar in Use (fifth edition - Teachercoms Library) "
    "(Raymond Murphy) (Z-Library).pdf"
)
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "storage" / "grammar" / "source-cache"
EXTRACTOR_VERSION = "1.0.0"
UNIT_COUNT = 145


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=Path(os.environ.get("GRAMMAR_BOOK_SOURCE_PDF", DEFAULT_SOURCE)),
        help="source PDF (defaults to GRAMMAR_BOOK_SOURCE_PDF or the configured book)",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help="parent directory for hash-versioned extraction caches",
    )
    parser.add_argument(
        "--render-dpi", type=int, default=96, help="DPI for visual-review JPEG pages"
    )
    parser.add_argument(
        "--skip-renders", action="store_true", help="do not create visual-review JPEG pages"
    )
    parser.add_argument(
        "--force", action="store_true", help="replace an existing complete cache"
    )
    return parser.parse_args()


def run(command: list[str], *, stdout_path: Path | None = None) -> None:
    printable = " ".join(command[:2])
    print(f"Running {printable} ...", flush=True)
    if stdout_path:
        with stdout_path.open("wb") as output:
            subprocess.run(command, check=True, stdout=output)
    else:
        subprocess.run(command, check=True)


def require_commands(*names: str) -> None:
    missing = [name for name in names if not shutil.which(name)]
    if missing:
        raise SystemExit(f"Missing required command(s): {', '.join(missing)}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def parse_pdfinfo(source: Path) -> dict[str, str]:
    result = subprocess.run(
        ["pdfinfo", str(source)], check=True, text=True, capture_output=True
    )
    info: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        info[key.strip().lower().replace(" ", "_")] = value.strip()
    return info


def styled_segments(element: ElementTree.Element) -> list[dict[str, object]]:
    segments: list[dict[str, object]] = []

    def append(text: str | None, bold: bool, italic: bool) -> None:
        if text:
            segments.append({"text": text, "bold": bold, "italic": italic})

    def visit(node: ElementTree.Element, bold: bool = False, italic: bool = False) -> None:
        tag = node.tag.lower().rsplit("}", 1)[-1]
        bold = bold or tag == "b"
        italic = italic or tag == "i"
        append(node.text, bold, italic)
        for child in node:
            visit(child, bold, italic)
            append(child.tail, bold, italic)

    visit(element)
    return segments


def number(value: str | None, default: float = 0) -> float:
    try:
        return float(value) if value is not None else default
    except ValueError:
        return default


def normalize_bbox(left: float, top: float, width: float, height: float) -> list[float]:
    right = left + width
    bottom = top + height
    return [round(min(left, right), 4), round(min(top, bottom), 4),
            round(max(left, right), 4), round(max(top, bottom), 4)]


def parse_xml(xml_path: Path) -> tuple[dict[int, dict[str, object]], dict[str, dict[str, object]]]:
    pages: dict[int, dict[str, object]] = {}
    image_sources: dict[str, dict[str, object]] = {}
    global_fonts: dict[str, dict[str, object]] = {}

    for event, element in ElementTree.iterparse(xml_path, events=("end",)):
        if element.tag != "page":
            continue
        page_number = int(element.attrib["number"])
        blocks: list[dict[str, object]] = []
        images: list[dict[str, object]] = []
        used_font_ids: set[str] = set()

        for child in element:
            if child.tag == "fontspec":
                global_fonts[child.attrib["id"]] = {
                    "size": number(child.attrib.get("size")),
                    "family": child.attrib.get("family", ""),
                    "color": child.attrib.get("color", ""),
                }
            elif child.tag == "text":
                left = number(child.attrib.get("left"))
                top = number(child.attrib.get("top"))
                width = number(child.attrib.get("width"))
                height = number(child.attrib.get("height"))
                segments = styled_segments(child)
                text = "".join(str(segment["text"]) for segment in segments)
                if not text:
                    continue
                block = {
                    "text": text,
                    "bbox": normalize_bbox(left, top, width, height),
                    "font_id": child.attrib.get("font"),
                    "segments": segments,
                }
                font_id = child.attrib.get("font", "")
                used_font_ids.add(font_id)
                font = global_fonts.get(font_id)
                if font:
                    block["font"] = font
                blocks.append(block)
            elif child.tag == "image":
                source_name = Path(child.attrib.get("src", "")).name
                left = number(child.attrib.get("left"))
                top = number(child.attrib.get("top"))
                width = number(child.attrib.get("width"))
                height = number(child.attrib.get("height"))
                image = {
                    "source_name": source_name,
                    "bbox": normalize_bbox(left, top, width, height),
                }
                images.append(image)
                image_sources[source_name] = {"page": page_number, **image}

        pages[page_number] = {
            "page": page_number,
            "width": number(element.attrib.get("width")),
            "height": number(element.attrib.get("height")),
            "fonts": {
                font_id: global_fonts[font_id]
                for font_id in sorted(used_font_ids)
                if font_id in global_fonts
            },
            "text_blocks": blocks,
            "images": images,
        }
        element.clear()

    return pages, image_sources


def store_images(
    raw_dir: Path,
    destination: Path,
    image_sources: dict[str, dict[str, object]],
) -> dict[str, dict[str, object]]:
    destination.mkdir(parents=True, exist_ok=True)
    index: dict[str, dict[str, object]] = {}
    for source_name, metadata in sorted(image_sources.items()):
        raw_path = raw_dir / source_name
        if not raw_path.is_file():
            index[source_name] = {**metadata, "status": "missing"}
            continue
        digest = sha256_file(raw_path)
        suffix = raw_path.suffix.lower() or ".bin"
        asset_name = f"{digest}{suffix}"
        asset_path = destination / asset_name
        if not asset_path.exists():
            shutil.copyfile(raw_path, asset_path)
        index[source_name] = {
            **metadata,
            "status": "ok",
            "sha256": digest,
            "asset": f"images/{asset_name}",
            "bytes": raw_path.stat().st_size,
        }
    return index


def split_page_text(all_text: str, page_count: int) -> dict[int, str]:
    chunks = all_text.split("\f")
    if chunks and not chunks[-1].strip():
        chunks.pop()
    if len(chunks) != page_count:
        raise RuntimeError(f"Expected {page_count} text pages, extracted {len(chunks)}")
    return {number: chunks[number - 1].rstrip() + "\n" for number in range(1, page_count + 1)}


def extract_unit_title(page: dict[str, object]) -> str:
    candidates = []
    for block in page["text_blocks"]:
        font = block.get("font") or {}
        bbox = block["bbox"]
        if bbox[1] <= 135 and bbox[0] >= 95 and number(str(font.get("size", 0))) >= 20:
            text = str(block["text"]).strip()
            # The unit badge is left of x=95, so a numeric fragment in this
            # region belongs to titles such as "should 1" or "the 2".
            if text and not re.fullmatch(r"Unit", text, flags=re.IGNORECASE):
                candidates.append(block)
    candidates.sort(key=lambda item: (item["bbox"][1], item["bbox"][0]))
    lines: list[list[dict[str, object]]] = []
    for candidate in candidates:
        if not lines or abs(candidate["bbox"][1] - lines[-1][0]["bbox"][1]) > 8:
            lines.append([candidate])
        else:
            lines[-1].append(candidate)

    rendered_lines = []
    for line in lines:
        line.sort(key=lambda item: item["bbox"][0])
        value = ""
        previous_right = None
        for item in line:
            text = str(item["text"])
            if (
                value
                and previous_right is not None
                and item["bbox"][0] - previous_right > 2
                and not value.endswith((" ", "("))
                and not text.startswith((" ", ")", ",", ".", ":", ";"))
            ):
                value += " "
            value += text
            previous_right = item["bbox"][2]
        rendered_lines.append(value.strip())
    title = " ".join(rendered_lines)
    return re.sub(r"\s+", " ", title).strip()


def exercise_numbers(text: str, unit_number: int) -> list[str]:
    pattern = re.compile(rf"(?m)^\s*({unit_number}\.\d+)\s+")
    return list(dict.fromkeys(pattern.findall(text)))


def build_answer_index(page_text: dict[int, str]) -> dict[str, object]:
    key_pages = [
        page for page, text in page_text.items()
        if "Key to Exercises" in text[:600]
    ]
    if not key_pages:
        raise RuntimeError("Could not locate Key to Exercises")

    unit_starts: dict[int, int] = {}
    headings_by_page: dict[int, list[int]] = {}
    for page in key_pages:
        # The three-column key often places several UNIT headings on one
        # extracted text line, so anchoring to line boundaries would miss the
        # headings in the middle and right columns.
        units = [
            int(value)
            for value in re.findall(r"\bUNIT\s+(\d+)\b", page_text[page])
        ]
        headings_by_page[page] = units
        for unit in units:
            unit_starts.setdefault(unit, page)

    units_index: dict[str, dict[str, object]] = {}
    for unit in range(1, UNIT_COUNT + 1):
        start_page = unit_starts.get(unit)
        next_page = unit_starts.get(unit + 1)
        if start_page is None:
            units_index[str(unit)] = {"status": "heading-not-found", "pages": []}
            continue
        end_page = next_page if next_page is not None else key_pages[-1]
        units_index[str(unit)] = {
            "status": "indexed",
            "start_page": start_page,
            "end_page": end_page,
            "pages": list(range(start_page, end_page + 1)),
        }

    return {
        "title": "Key to Exercises",
        "start_page": key_pages[0],
        "end_page": key_pages[-1],
        "pages": key_pages,
        "headings_by_page": {str(key): value for key, value in headings_by_page.items()},
        "units": units_index,
    }


def build_indexes(
    target: Path,
    pages: dict[int, dict[str, object]],
    page_text: dict[int, str],
    image_index: dict[str, dict[str, object]],
    renders_enabled: bool,
) -> dict[str, object]:
    indexes_dir = target / "indexes"
    indexes_dir.mkdir(parents=True, exist_ok=True)
    answer_index = build_answer_index(page_text)
    units: dict[str, dict[str, object]] = {}
    exercises: dict[str, dict[str, object]] = {}

    for unit in range(1, UNIT_COUNT + 1):
        body_page = 12 + unit * 2
        exercise_page = body_page + 1
        numbers = exercise_numbers(page_text[exercise_page], unit)
        answer_pages = answer_index["units"].get(str(unit), {}).get("pages", [])
        units[str(unit)] = {
            "unit_number": unit,
            "title": extract_unit_title(pages[body_page]),
            "body_page": body_page,
            "exercise_page": exercise_page,
            "exercise_numbers": numbers,
            "answer_pages": answer_pages,
        }
        for order, exercise_number in enumerate(numbers, start=1):
            exercises[exercise_number] = {
                "unit_number": unit,
                "sort_order": order,
                "question_page": exercise_page,
                "answer_pages": answer_pages,
            }

    pages_index = []
    for page_number, page in sorted(pages.items()):
        pages_index.append({
            "page": page_number,
            "json": f"pages/page-{page_number:03d}.json",
            "text": f"text/page-{page_number:03d}.txt",
            "render": f"renders/page-{page_number:03d}.jpg" if renders_enabled else None,
            "text_block_count": len(page["text_blocks"]),
            "image_count": len(page["images"]),
        })

    write_json(indexes_dir / "pages.json", pages_index)
    write_json(indexes_dir / "units.json", units)
    write_json(indexes_dir / "exercises.json", exercises)
    write_json(indexes_dir / "answer-key.json", answer_index)
    write_json(indexes_dir / "images.json", image_index)

    search_path = indexes_dir / "search.db"
    connection = sqlite3.connect(search_path)
    try:
        connection.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        connection.execute(
            "CREATE TABLE pages (page INTEGER PRIMARY KEY, section TEXT NOT NULL, "
            "text TEXT NOT NULL, json_path TEXT NOT NULL)"
        )
        connection.execute(
            "CREATE VIRTUAL TABLE pages_fts USING fts5(page UNINDEXED, section, text)"
        )
        connection.executemany(
            "INSERT INTO metadata(key, value) VALUES (?, ?)",
            (("extractor_version", EXTRACTOR_VERSION), ("page_count", str(len(pages)))),
        )
        for page_number, text in page_text.items():
            if page_number in (12 + n * 2 for n in range(1, UNIT_COUNT + 1)):
                section = "unit-body"
            elif page_number in (13 + n * 2 for n in range(1, UNIT_COUNT + 1)):
                section = "unit-exercises"
            elif page_number in answer_index["pages"]:
                section = "answer-key"
            else:
                section = "other"
            json_path = f"pages/page-{page_number:03d}.json"
            connection.execute(
                "INSERT INTO pages(page, section, text, json_path) VALUES (?, ?, ?, ?)",
                (page_number, section, text, json_path),
            )
            connection.execute(
                "INSERT INTO pages_fts(page, section, text) VALUES (?, ?, ?)",
                (page_number, section, text),
            )
        connection.commit()
    finally:
        connection.close()

    return {
        "unit_count": len(units),
        "exercise_count": len(exercises),
        "answer_key_start_page": answer_index["start_page"],
        "answer_key_end_page": answer_index["end_page"],
        "answer_units_indexed": sum(
            value.get("status") == "indexed" for value in answer_index["units"].values()
        ),
    }


def main() -> int:
    args = parse_args()
    source = args.source.expanduser().resolve()
    output_root = args.output_root.expanduser().resolve()
    if not source.is_file():
        raise SystemExit(f"Source PDF was not found: {source}")
    if args.render_dpi < 48 or args.render_dpi > 300:
        raise SystemExit("--render-dpi must be between 48 and 300")
    require_commands("pdfinfo", "pdftohtml", "pdftotext", "pdftoppm")

    source_hash = sha256_file(source)
    target = output_root / source_hash
    manifest_path = target / "manifest.json"
    if manifest_path.is_file() and not args.force:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("status") == "complete" and manifest.get("extractor_version") == EXTRACTOR_VERSION:
            print(f"Complete cache already exists: {target}")
            return 0
        raise SystemExit(f"Incomplete or older cache exists; inspect it or rerun with --force: {target}")

    output_root.mkdir(parents=True, exist_ok=True)
    temporary = output_root / f".{source_hash}.tmp-{os.getpid()}"
    if temporary.exists():
        shutil.rmtree(temporary)
    for name in ("raw", "pages", "text", "images", "renders", "indexes"):
        (temporary / name).mkdir(parents=True, exist_ok=True)

    started_at = datetime.now(timezone.utc)
    info = parse_pdfinfo(source)
    page_count = int(info.get("pages", "0"))
    if not page_count:
        raise RuntimeError("pdfinfo did not return a valid page count")

    raw_dir = temporary / "raw"
    xml_path = raw_dir / "book.xml"
    run([
        "pdftohtml", "-q", "-xml", "-hidden", "-noroundcoord", "-fontfullname",
        "-fmt", "png", str(source), str(xml_path),
    ])
    all_text_path = raw_dir / "book.txt"
    run(["pdftotext", "-layout", str(source), str(all_text_path)])

    pages, image_sources = parse_xml(xml_path)
    if len(pages) != page_count:
        raise RuntimeError(f"Expected {page_count} XML pages, extracted {len(pages)}")
    page_text = split_page_text(all_text_path.read_text(encoding="utf-8"), page_count)
    image_index = store_images(raw_dir, temporary / "images", image_sources)

    for page_number, page in sorted(pages.items()):
        for image in page["images"]:
            image.update(image_index.get(image["source_name"], {}))
        write_json(temporary / "pages" / f"page-{page_number:03d}.json", page)
        (temporary / "text" / f"page-{page_number:03d}.txt").write_text(
            page_text[page_number], encoding="utf-8"
        )

    renders_enabled = not args.skip_renders
    if renders_enabled:
        run([
            "pdftoppm", "-jpeg", "-jpegopt", "quality=78,progressive=y,optimize=y",
            "-r", str(args.render_dpi), str(source), str(temporary / "renders" / "page"),
        ])
        rendered = list((temporary / "renders").glob("page-*.jpg"))
        if len(rendered) != page_count:
            raise RuntimeError(f"Expected {page_count} renders, created {len(rendered)}")

    index_summary = build_indexes(
        temporary, pages, page_text, image_index, renders_enabled
    )
    unique_assets = {item.get("asset") for item in image_index.values() if item.get("asset")}
    missing_images = sum(item.get("status") != "ok" for item in image_index.values())
    completed_at = datetime.now(timezone.utc)
    manifest = {
        "status": "complete",
        "extractor_version": EXTRACTOR_VERSION,
        "source": {
            "path": str(source),
            "filename": source.name,
            "sha256": source_hash,
            "bytes": source.stat().st_size,
        },
        "pdfinfo": info,
        "page_count": page_count,
        "render_dpi": args.render_dpi if renders_enabled else None,
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "statistics": {
            "text_blocks": sum(len(page["text_blocks"]) for page in pages.values()),
            "image_placements": len(image_sources),
            "unique_image_assets": len(unique_assets),
            "missing_image_assets": missing_images,
            **index_summary,
        },
    }
    write_json(temporary / "manifest.json", manifest)

    # Raw extracted image fragments are represented by the hash-named assets and
    # images.json. Keeping a second copy would only inflate the rebuildable cache.
    for raw_image in raw_dir.glob("book-*.png"):
        raw_image.unlink()

    if target.exists():
        if not args.force:
            raise RuntimeError(f"Target appeared while preprocessing: {target}")
        shutil.rmtree(target)
    temporary.replace(target)
    print(f"Preprocessing complete: {target}")
    print(json.dumps(manifest["statistics"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as error:
        print(f"Command failed with exit code {error.returncode}: {error.cmd}", file=sys.stderr)
        raise
