#!/usr/bin/env python3
"""
Imports the EDSM nightly dump (systemsWithCoordinates.json) into a local SQLite database.

The database is used by find_nearby_systems.py in --local mode, avoiding the EDSM API
and its Cloudflare bot protection entirely.

Schema:
    systems(name TEXT, x REAL, y REAL, z REAL, sector TEXT, boxel TEXT, mass_code TEXT)
    Index on (sector, boxel) for fast prefix lookups.

Parsed columns (sector, boxel, mass_code) are nullable — systems whose names don't match
the procedural naming pattern are stored with NULLs and excluded from prefix search results.

Usage:
    # Test with first 100 records before importing the full 14GB file
    python import_edsm_dump.py --limit 100

    # Full import (takes a while)
    python import_edsm_dump.py

    # Use a different output path
    python import_edsm_dump.py --db data/custom.db
"""

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = REPO_ROOT / "data" / "systemsWithCoordinates.json"
DEFAULT_DB = REPO_ROOT / "data" / "edsm.db"

PROCEDURAL_RE = re.compile(
    r"^(.+?)\s+([A-Z]{2}-[A-Z])\s+([a-h])",
    re.IGNORECASE,
)

BATCH_SIZE = 10_000


def parse_procedural(name: str) -> tuple[str, str, str] | tuple[None, None, None]:
    m = PROCEDURAL_RE.match(name.strip())
    if m:
        return m.group(1).strip(), m.group(2).upper(), m.group(3).lower()
    return None, None, None


def create_schema(conn: sqlite3.Connection) -> None:
    conn.execute("DROP TABLE IF EXISTS systems")
    conn.execute("""
        CREATE TABLE systems (
            name      TEXT NOT NULL,
            x         REAL NOT NULL,
            y         REAL NOT NULL,
            z         REAL NOT NULL,
            sector    TEXT,
            boxel     TEXT,
            mass_code TEXT
        )
    """)
    conn.execute("CREATE INDEX idx_sector_boxel ON systems (sector, boxel)")
    conn.commit()


def run_import(source: Path, db_path: Path, limit: int | None) -> None:
    print(f"Source : {source}")
    print(f"Output : {db_path}")
    if limit:
        print(f"Limit  : first {limit:,} records")
    print()

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    create_schema(conn)

    total = 0
    parse_failures = 0
    batch = []

    with open(source) as f:
        for line in f:
            line = line.strip().rstrip(",")
            if not line or line in ("[", "]"):
                continue

            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            coords = obj.get("coords")
            name = obj.get("name", "")
            if not coords or not name:
                continue

            sector, boxel, mass_code = parse_procedural(name)
            if sector is None:
                parse_failures += 1

            batch.append((name, coords["x"], coords["y"], coords["z"], sector, boxel, mass_code))
            total += 1

            if len(batch) >= BATCH_SIZE:
                conn.executemany(
                    "INSERT INTO systems VALUES (?, ?, ?, ?, ?, ?, ?)", batch
                )
                conn.commit()
                batch.clear()

            if total % 1_000_000 == 0:
                print(f"  {total:,} records imported...")

            if limit and total >= limit:
                break

    if batch:
        conn.executemany("INSERT INTO systems VALUES (?, ?, ?, ?, ?, ?, ?)", batch)
        conn.commit()

    conn.close()

    parse_rate = 100 * parse_failures / total if total else 0
    print(f"\nDone.")
    print(f"  Records imported : {total:,}")
    print(f"  Parse failures   : {parse_failures:,} ({parse_rate:.2f}%) — stored with NULL sector/boxel/mass_code")
    print(f"  Database         : {db_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import EDSM nightly dump into a local SQLite database."
    )
    parser.add_argument(
        "--source", type=Path, default=DEFAULT_SOURCE,
        help=f"Path to systemsWithCoordinates.json (default: {DEFAULT_SOURCE})",
    )
    parser.add_argument(
        "--db", type=Path, default=DEFAULT_DB,
        help=f"Output SQLite database path (default: {DEFAULT_DB})",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Import only the first N records (for testing)",
    )
    args = parser.parse_args()

    if not args.source.exists():
        print(f"Error: source file not found: {args.source}")
        print("Download from https://www.edsm.net/en/nightly-dumps and place in data/")
        sys.exit(1)

    run_import(args.source, args.db, args.limit)


if __name__ == "__main__":
    main()
