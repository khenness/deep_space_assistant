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
import time
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = REPO_ROOT / "data" / "edsm.db"

RADIUS = 50.0
MAX_NEIGHBOURS = 50
BATCH_SIZE = 1000


def build(db_path: Path, second_pass_only: bool = False) -> None:
    start = time.monotonic()
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    conn = sqlite3.connect(db_path)
    total_rows = 0

    _BLOCKLIST = {"AssetViewerSystem"}

    if not second_pass_only:
        print("Loading named systems...")
        rows = [
            (name, x, y, z)
            for name, x, y, z in conn.execute(
                "SELECT name, x, y, z FROM systems WHERE sector IS NULL AND x IS NOT NULL"
            ).fetchall()
            if name not in _BLOCKLIST
        ]
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

    # Second pass: named systems with no named neighbours within 50ly (e.g. Sagittarius A*
    # at the galactic core). Single set-difference query — much faster than per-row checks.
    print("Finding named systems with no named neighbours (core/isolated systems)...")
    isolated = conn.execute(
        "SELECT name, x, y, z FROM systems "
        "WHERE sector IS NULL AND x IS NOT NULL "
        "AND name NOT IN (SELECT DISTINCT system_name FROM named_neighbours) "
        "AND name NOT IN ('AssetViewerSystem')"
    ).fetchall()
    print(f"  {len(isolated):,} isolated named systems found")

    if isolated:
        print(f"  Computing all-systems neighbours for isolated systems (radius={RADIUS}ly)...")
        batch = []
        for name, sx, sy, sz in isolated:
            db_rows = conn.execute(
                "SELECT name, ((x-?)*(x-?) + (y-?)*(y-?) + (z-?)*(z-?)) AS dist_sq "
                "FROM systems "
                "WHERE x BETWEEN ? AND ? AND y BETWEEN ? AND ? AND z BETWEEN ? AND ? "
                "AND name != ? COLLATE NOCASE "
                "AND name NOT IN ('AssetViewerSystem') "
                "ORDER BY dist_sq LIMIT ?",
                (sx, sx, sy, sy, sz, sz,
                 sx - RADIUS, sx + RADIUS, sy - RADIUS, sy + RADIUS, sz - RADIUS, sz + RADIUS,
                 name, MAX_NEIGHBOURS),
            ).fetchall()
            for neighbour, dist_sq in db_rows:
                dist = math.sqrt(dist_sq)
                if dist <= RADIUS:
                    batch.append((name, neighbour, round(dist, 4)))

        conn.executemany("INSERT INTO named_neighbours VALUES (?, ?, ?)", batch)
        total_rows += len(batch)
        conn.commit()
        print(f"  {len(batch):,} rows added for isolated systems")

    conn.close()
    elapsed = time.monotonic() - start
    print(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (took {elapsed:.0f}s)")
    print(f"Done. {total_rows:,} rows written to named_neighbours.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--fill-isolated", action="store_true",
                        help="Skip the named-only pass; only fill in systems with no neighbours yet (e.g. Sgr A* at the galactic core)")
    args = parser.parse_args()
    build(args.db, second_pass_only=args.fill_isolated)
