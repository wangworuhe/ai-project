#!/usr/bin/env python3
"""Render the source PDF pages required by grammar Unit data packages."""

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = Path(
    "/Users/yala/Documents/04-Resources/MacShare/"
    "English Grammar in Use (fifth edition - Teachercoms Library) "
    "(Raymond Murphy) (Z-Library).pdf"
)
SOURCE_PDF = Path(os.environ.get("GRAMMAR_BOOK_SOURCE_PDF", DEFAULT_SOURCE)).expanduser()
OUTPUT_DIR = PROJECT_ROOT / "storage" / "grammar" / "book-pages"
PACKAGE_DIR = PROJECT_ROOT / "storage" / "grammar" / "import-packages"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Render only the PDF pages referenced by grammar Unit data packages."
    )
    parser.add_argument(
        "--unit",
        type=int,
        action="append",
        help="Render one Unit package. Repeat this option to render several Units.",
    )
    parser.add_argument(
        "--package-dir",
        type=Path,
        default=PACKAGE_DIR,
        help="Directory containing unit-NNN.json packages.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help="Directory for page-NNN.png assets.",
    )
    parser.add_argument("--dpi", type=int, default=130, help="Output resolution.")
    return parser.parse_args()


def package_paths(package_dir, units):
    if units:
        paths = [package_dir / f"unit-{unit:03d}.json" for unit in units]
    else:
        paths = sorted(package_dir.glob("unit-*.json"))
    missing = [path for path in paths if not path.is_file()]
    if missing:
        raise SystemExit(f"Unit package was not found: {missing[0]}")
    if not paths:
        raise SystemExit(f"No Unit packages were found in: {package_dir}")
    return paths


def referenced_pages(paths):
    pages = set()
    for path in paths:
        with path.open(encoding="utf-8") as package_file:
            package = json.load(package_file)
        pages.add(int(package["unit"]["body_page"]))
        pages.add(int(package["unit"]["exercise_page"]))
        pages.add(int(package["body"]["page"]))
        pages.update(int(item["page"]) for item in package.get("media", {}).values())
        pages.update(int(item["source_page"]) for item in package.get("exercises", []))
    return sorted(pages)


def main():
    args = parse_args()
    if not SOURCE_PDF.is_file():
        raise SystemExit(f"Source PDF was not found: {SOURCE_PDF}")
    if not shutil.which("pdftoppm"):
        raise SystemExit("pdftoppm is required. Install Poppler before generating book pages.")
    if args.dpi < 72:
        raise SystemExit("--dpi must be at least 72")

    paths = package_paths(args.package_dir, args.unit)
    pages = referenced_pages(paths)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    for page_number in pages:
        output_prefix = args.output_dir / f"page-{page_number:03d}"
        subprocess.run(
            [
                "pdftoppm",
                "-f",
                str(page_number),
                "-l",
                str(page_number),
                "-r",
                str(args.dpi),
                "-singlefile",
                "-png",
                str(SOURCE_PDF),
                str(output_prefix),
            ],
            check=True,
        )
        rendered = output_prefix.with_suffix(".png")
        if not rendered.is_file():
            raise SystemExit(f"Missing rendered page: {rendered}")

    units = ", ".join(path.stem.removeprefix("unit-") for path in paths)
    print(
        f"Rendered {len(pages)} source pages for Unit packages {units} "
        f"to {args.output_dir}"
    )


if __name__ == "__main__":
    main()
