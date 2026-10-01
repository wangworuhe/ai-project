#!/usr/bin/env python3
"""Create a consistent timestamped SQLite backup and prune old deploy backups."""

from __future__ import annotations

import sqlite3
import sys
from datetime import datetime
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: backup_sqlite.py SOURCE_DB BACKUP_DIR", file=sys.stderr)
        return 2

    source = Path(sys.argv[1])
    backup_dir = Path(sys.argv[2])
    if not source.exists():
        print(f"No database at {source}; skipping first-deploy backup.")
        return 0

    backup_dir.mkdir(parents=True, exist_ok=True)
    destination = backup_dir / f"database-{datetime.now().strftime('%Y%m%d-%H%M%S')}.db"
    with sqlite3.connect(source) as source_db, sqlite3.connect(destination) as backup_db:
        source_db.backup(backup_db)
    destination.chmod(0o600)

    backups = sorted(backup_dir.glob("database-*.db"), reverse=True)
    for old_backup in backups[14:]:
        old_backup.unlink()
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

