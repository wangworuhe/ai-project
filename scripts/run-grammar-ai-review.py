#!/usr/bin/env python3
"""Continuously advance durable grammar explanation jobs."""

import argparse
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend import create_app
from backend.services.grammar_ai_review_service import process_review_jobs_once


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval", type=float, default=5)
    args = parser.parse_args()
    app = create_app()
    while True:
        with app.app_context():
            result = process_review_jobs_once()
            if args.once:
                print(result)
                return
        time.sleep(max(1, args.interval))


if __name__ == "__main__":
    main()
