"""
Build the named_neighbours table.

For each named system (sector IS NULL), finds its nearest neighbours
among other named systems within 50ly, storing up to 50 per system.
Run this after the EDSM import and whenever the systems table is refreshed.

Usage:
    python scripts/build_named_neighbours/build_named_neighbours.py
    python scripts/build_named_neighbours/build_named_neighbours.py --db path/to/edsm.db
"""

import argparse
import math
import sqlite3
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = REPO_ROOT / "data" / "edsm.db"

RADIUS = 50.0
MAX_NEIGHBOURS = 50
BATCH_SIZE = 1000


def build(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)

    print("Loading named systems...")
    rows = conn.execute(
        "SELECT name, x, y, z FROM systems WHERE sector IS NULL AND x IS NOT NULL"
    ).fetchall()
    print(f"  {len(rows):,} named systems loaded")

    print("Dropping and recreating named_neighbours table...")
    conn.execute("DROP TABLE IF EXISTS named_neighbours")
    conn.execute("""
        CREATE TABLE named_neighbours (
            system_name  TEXT NOT NULL,
            neighbour    TEXT NOT NULL,
            distance_ly  REAL NOT NULL
        )
    """)
    conn.execute("""
        CREATE INDEX idx_named_neighbours_system
        ON named_neighbours (system_name COLLATE NOCASE)
    """)

    print(f"Computing neighbours (radius={RADIUS}ly, max={MAX_NEIGHBOURS} per system)...")
    batch = []
    total_rows = 0

    for i, (name, sx, sy, sz) in enumerate(rows):
        if i % 10000 == 0:
            print(f"  {i:,}/{len(rows):,}...", flush=True)

        neighbours = []
        for (other_name, cx, cy, cz) in rows:
            if other_name == name:
                continue
            # Bounding box fast-reject
            if abs(cx - sx) > RADIUS or abs(cy - sy) > RADIUS or abs(cz - sz) > RADIUS:
                continue
            dist = math.sqrt((sx - cx) ** 2 + (sy - cy) ** 2 + (sz - cz) ** 2)
            if dist <= RADIUS:
                neighbours.append((dist, other_name))

        neighbours.sort()
        for dist, neighbour in neighbours[:MAX_NEIGHBOURS]:
            batch.append((name, neighbour, round(dist, 4)))

        if len(batch) >= BATCH_SIZE:
            conn.executemany(
                "INSERT INTO named_neighbours VALUES (?, ?, ?)", batch
            )
            total_rows += len(batch)
            batch = []

    if batch:
        conn.executemany("INSERT INTO named_neighbours VALUES (?, ?, ?)", batch)
        total_rows += len(batch)

    conn.commit()
    conn.close()
    print(f"Done. {total_rows:,} rows written to named_neighbours.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()
    build(args.db)
