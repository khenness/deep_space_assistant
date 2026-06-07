#!/usr/bin/env python3
"""
Downloads the EDASTRO Galactic Exploration Catalog (GEC) combined dataset and
imports it into the local SQLite database as a poi table.

The combined endpoint includes both GEC entries (~609) and GMP entries (~2,123)
for a total of ~2,732 points of interest, all with galactic XYZ coordinates.

Licensed under CC BY-NC-SA 3.0 — https://edastro.com/gec/APIinfo

Usage:
    python scripts/import_gec/import_gec.py
    python scripts/import_gec/import_gec.py --db data/edsm.db
"""

import argparse
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = REPO_ROOT / "data" / "edsm.db"

GEC_URL = "https://edastro.com/gec/json/combined"


def create_table(conn: sqlite3.Connection) -> None:
    conn.execute("DROP TABLE IF EXISTS poi")
    conn.execute("""
        CREATE TABLE poi (
            id           INTEGER NOT NULL,
            source       TEXT NOT NULL,
            name         TEXT NOT NULL,
            system_name  TEXT NOT NULL,
            x            REAL,
            y            REAL,
            z            REAL,
            category     TEXT,
            category2    TEXT,
            region       TEXT,
            sol_distance REAL,
            summary      TEXT,
            description  TEXT,
            avg_stars    REAL,
            votes        INTEGER,
            rare         INTEGER,
            poi_url      TEXT,
            main_image   TEXT,
            id64         INTEGER
        )
    """)
    conn.execute("CREATE INDEX idx_poi_xyz ON poi (x, y, z)")
    conn.execute("CREATE INDEX idx_poi_category ON poi (category)")
    conn.commit()


def fetch_pois() -> list[dict]:
    print(f"Fetching {GEC_URL} ...")
    resp = requests.get(GEC_URL, timeout=60, headers={"User-Agent": "DeepSpaceAssistant/1.0"})
    resp.raise_for_status()
    data = resp.json()
    print(f"  {len(data):,} entries received")
    return data


def run_import(db_path: Path) -> None:
    start = time.monotonic()
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if not db_path.exists():
        print(f"Error: database not found: {db_path}")
        print("Run scripts/import_edsm_dump/import_edsm_dump.py first.")
        sys.exit(1)

    pois = fetch_pois()
    conn = sqlite3.connect(db_path)
    create_table(conn)

    inserted = 0
    no_coords = 0

    for entry in pois:
        coords = entry.get("coordinates")
        if not coords or len(coords) < 3:
            no_coords += 1
            x = y = z = None
        else:
            x, y, z = coords[0], coords[1], coords[2]

        # GMP entries have a leaner schema — many fields will be absent
        conn.execute(
            "INSERT INTO poi VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                entry.get("id"),
                entry.get("source", "GEC"),
                entry.get("name", ""),
                entry.get("galMapSearch") or entry.get("name", ""),
                x, y, z,
                entry.get("type"),
                entry.get("type2") or None,
                entry.get("region") or None,
                entry.get("solDistance"),
                entry.get("summary") or None,
                entry.get("descriptionMardown") or None,  # note: typo is in the API
                entry.get("avgStars"),
                entry.get("votes"),
                1 if entry.get("rare") else 0,
                entry.get("poiUrl") or None,
                entry.get("mainImage") or None,
                entry.get("id64"),
            ),
        )
        inserted += 1

    conn.commit()
    conn.close()

    elapsed = time.monotonic() - start
    print(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (took {elapsed:.0f}s)")
    print(f"  POIs imported    : {inserted:,}")
    print(f"  Without coords   : {no_coords}")
    print(f"  Database         : {db_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import EDASTRO GEC combined POI dataset into local SQLite database."
    )
    parser.add_argument(
        "--db", type=Path, default=DEFAULT_DB,
        help=f"Path to SQLite database (default: {DEFAULT_DB})",
    )
    args = parser.parse_args()
    run_import(args.db)


if __name__ == "__main__":
    main()
