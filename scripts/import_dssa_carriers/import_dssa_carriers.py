#!/usr/bin/env python3
"""
Downloads the DSSA carrier roster from the community spreadsheet and imports
it into the local SQLite database, enriching each carrier with 3D coordinates
looked up from the systems table.

The spreadsheet is the authoritative DSSA source, maintained by the community:
https://docs.google.com/spreadsheets/d/e/2PACX-1vTevQUcLThqo4emXE4nowJeasI07gFio4fETwevAXKIA18NhlDzbnZzRMVUOAT26OROfHG7fCXvTLgY/pubhtml

Re-run this script periodically to pick up carrier movements or status changes.

Usage:
    python import_dssa_carriers.py
    python import_dssa_carriers.py --db data/edsm_test.db
"""

import argparse
import csv
import io
import sqlite3
import sys
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = REPO_ROOT / "data" / "edsm.db"

SPREADSHEET_CSV_URL = (
    "https://docs.google.com/spreadsheets/d/e/"
    "2PACX-1vTevQUcLThqo4emXE4nowJeasI07gFio4fETwevAXKIA18NhlDzbnZzRMVUOAT26OROfHG7fCXvTLgY"
    "/pub?gid=0&single=true&output=csv"
)


def create_table(conn: sqlite3.Connection) -> None:
    conn.execute("DROP TABLE IF EXISTS dssa_carriers")
    conn.execute("""
        CREATE TABLE dssa_carriers (
            callsign        TEXT NOT NULL,
            vessel          TEXT NOT NULL,
            operation       TEXT,
            region          TEXT,
            system_name     TEXT NOT NULL,
            x               REAL,
            y               REAL,
            z               REAL,
            services        TEXT,
            status          TEXT,
            owner           TEXT
        )
    """)
    conn.execute("CREATE INDEX idx_dssa_xyz ON dssa_carriers (x, y, z)")
    conn.commit()


def fetch_csv() -> list[dict]:
    print("Downloading DSSA carrier roster...")
    resp = requests.get(SPREADSHEET_CSV_URL, timeout=30)
    resp.raise_for_status()
    reader = csv.DictReader(io.StringIO(resp.text))
    return list(reader)


def lookup_coordinates(system_name: str, conn: sqlite3.Connection) -> tuple[float, float, float] | None:
    row = conn.execute(
        "SELECT x, y, z FROM systems WHERE LOWER(name) = LOWER(?)",
        (system_name.strip(),),
    ).fetchone()
    return row if row else None


def run_import(db_path: Path) -> None:
    if not db_path.exists():
        print(f"Error: database not found: {db_path}")
        print("Run scripts/import_edsm_dump/import_edsm_dump.py first.")
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    rows = fetch_csv()

    operational = [
        r for r in rows
        if r.get("DEPLOYMENT OPERATION STATUS", "").strip() == "Carrier Operational"
    ]
    print(f"Found {len(operational)} operational carriers in roster.")

    create_table(conn)

    inserted = 0
    no_coords = []

    for row in operational:
        system = row.get("CURRENT LOCATION", "").strip()
        if not system:
            continue

        coords = lookup_coordinates(system, conn)

        conn.execute(
            "INSERT INTO dssa_carriers VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                row.get("CALLSIGN", "").strip(),
                row.get("VESSEL", "").strip(),
                row.get("DEPLOYMENT OPERATION NAME", "").strip(),
                row.get("REGION", "").strip(),
                system,
                coords[0] if coords else None,
                coords[1] if coords else None,
                coords[2] if coords else None,
                row.get("AVAILABLE SERVICES", "").strip(),
                row.get("DEPLOYMENT OPERATION STATUS", "").strip(),
                row.get("OWNER", "").strip(),
            ),
        )
        inserted += 1
        if not coords:
            no_coords.append(system)

    conn.commit()
    conn.close()

    print(f"\nDone.")
    print(f"  Carriers imported : {inserted}")
    print(f"  With coordinates  : {inserted - len(no_coords)}")
    print(f"  Without coords    : {len(no_coords)} (system not in EDSM DB — distance calc unavailable)")
    if no_coords:
        for s in no_coords:
            print(f"    - {s}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import DSSA carrier roster into local SQLite database."
    )
    parser.add_argument(
        "--db", type=Path, default=DEFAULT_DB,
        help=f"Path to SQLite database (default: {DEFAULT_DB})",
    )
    args = parser.parse_args()
    run_import(args.db)


if __name__ == "__main__":
    main()
