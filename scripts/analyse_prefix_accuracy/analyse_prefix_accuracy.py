#!/usr/bin/env python3
"""
Validates the prefix-matching hypothesis against the full EDSM dataset.

Two modes:

1. Random sampling (default) — loads every Nth system and checks whether same-sector+boxel
   neighbours are spatially close. Fast but sparse: with 96.4M records, even 1-in-1000
   sampling leaves most sector+boxels with only one entry, so neighbour-finding fails.
   Use --sample-every 50 for denser (but slower) sampling.

2. Targeted sector analysis (--sector) — loads ALL systems from one or more sector+boxel
   combinations and computes pairwise distances. Much more reliable for validation.
   Use --find-dense first to discover which sector+boxels have the most records.

Usage:
    # Find the most data-rich sector+boxels to analyse
    python analyse_prefix_accuracy.py --find-dense --lines 5000000

    # Targeted analysis of a known dense sector
    python analyse_prefix_accuracy.py --sector "Zunou GS-B" --sector "Eol Prou KR-W"

    # Random sampling (default, sparse)
    python analyse_prefix_accuracy.py --sample-every 1000 --probe 200
"""

import argparse
import json
import math
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_FILE = REPO_ROOT / "data" / "systemsWithCoordinates.json"


def distance(a: dict, b: dict) -> float:
    return math.sqrt(
        (a["x"] - b["x"]) ** 2 +
        (a["y"] - b["y"]) ** 2 +
        (a["z"] - b["z"]) ** 2
    )


def parse_sector_boxel(name: str) -> tuple[str, str] | None:
    """Extract sector and boxel from a procedural name. Returns None if not procedural."""
    m = re.match(r"^(.+?)\s+([A-Z]{2}-[A-Z])\s+[a-h]", name.strip(), re.IGNORECASE)
    if m:
        return m.group(1).strip(), m.group(2).upper()
    return None


def parse_sector_boxel_masscode(name: str) -> tuple[str, str, str] | None:
    """Extract sector, boxel, and mass code from a procedural name."""
    m = re.match(r"^(.+?)\s+([A-Z]{2}-[A-Z])\s+([a-h])", name.strip(), re.IGNORECASE)
    if m:
        return m.group(1).strip(), m.group(2).upper(), m.group(3).lower()
    return None


def find_dense_sectors(data_file: Path, max_lines: int) -> None:
    """Scan the first N lines of the file and report the most-populated sector+boxels."""
    counts: dict[str, int] = defaultdict(int)
    total = 0
    print(f"Scanning first {max_lines:,} lines of {data_file.name}...")

    with open(data_file) as f:
        for i, line in enumerate(f):
            if i >= max_lines:
                break
            if i % 1_000_000 == 0 and i > 0:
                print(f"  {i:,} lines scanned...")
            line = line.strip().rstrip(",")
            if not line or line in ("[", "]"):
                continue
            try:
                obj = json.loads(line)
                parsed = parse_sector_boxel(obj.get("name", ""))
                if parsed:
                    counts[f"{parsed[0]} {parsed[1]}"] += 1
                    total += 1
            except json.JSONDecodeError:
                continue

    top = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:20]
    print(f"\nProcessed {total:,} procedural systems across {len(counts):,} sector+boxels.")
    print(f"\nTop 20 most-populated sector+boxels in first {max_lines:,} lines:")
    for key, count in top:
        print(f"  {key}: {count:,} systems")


def load_targeted_sectors(data_file: Path, target_sectors: list[str]) -> dict[tuple, list]:
    """Load all systems from specific sector+boxel combinations."""
    # Parse targets: "Zunou GS-B" -> ("Zunou", "GS-B"), "Eol Prou KR-W" -> ("Eol Prou", "KR-W")
    target_keys: set[tuple[str, str]] = set()
    for t in target_sectors:
        parts = t.strip().rsplit(" ", 1)
        if len(parts) == 2:
            target_keys.add((parts[0].strip(), parts[1].strip().upper()))
        else:
            print(f"  Warning: could not parse sector '{t}' — expected 'Sector BOXEL' e.g. 'Zunou GS-B'")

    if not target_keys:
        return {}

    buckets: dict[tuple, list] = defaultdict(list)
    print(f"Loading systems for {len(target_keys)} sector+boxel target(s)...")

    with open(data_file) as f:
        for i, line in enumerate(f):
            if i % 5_000_000 == 0 and i > 0:
                print(f"  {i:,} lines read, {sum(len(v) for v in buckets.values()):,} systems loaded...")
            line = line.strip().rstrip(",")
            if not line or line in ("[", "]"):
                continue
            try:
                obj = json.loads(line)
                coords = obj.get("coords")
                if not coords:
                    continue
                parsed = parse_sector_boxel(obj["name"])
                if parsed and parsed in target_keys:
                    buckets[parsed].append({
                        "name": obj["name"],
                        "x": coords["x"],
                        "y": coords["y"],
                        "z": coords["z"],
                    })
            except (json.JSONDecodeError, KeyError):
                continue

    total = sum(len(v) for v in buckets.items())
    print(f"\nLoaded {sum(len(v) for v in buckets.values()):,} systems across {len(buckets)} sector+boxel(s).")
    for key, systems in sorted(buckets.items(), key=lambda x: -len(x[1])):
        print(f"  {key[0]} {key[1]}: {len(systems):,} systems")

    return dict(buckets)


def load_systems_sampled(data_file: Path, sample_every: int) -> list[dict]:
    """Stream the JSON file and load every Nth system."""
    systems = []
    print(f"Loading every {sample_every}th system from {data_file.name}...")

    with open(data_file) as f:
        for i, line in enumerate(f):
            if i % 5_000_000 == 0 and i > 0:
                print(f"  {i:,} lines read, {len(systems):,} systems sampled...")
            if i % sample_every != 0:
                continue
            line = line.strip().rstrip(",")
            if not line or line in ("[", "]"):
                continue
            try:
                obj = json.loads(line)
                if "coords" in obj and "name" in obj:
                    systems.append({
                        "name": obj["name"],
                        "x": obj["coords"]["x"],
                        "y": obj["coords"]["y"],
                        "z": obj["coords"]["z"],
                    })
            except json.JSONDecodeError:
                continue

    print(f"\nLoaded {len(systems):,} systems.")
    return systems


def analyse_sector_boxel(systems: list[dict], label: str, num_probe: int) -> None:
    """Compute nearest-neighbour distances within a sector+boxel and report statistics."""
    probes = random.sample(systems, min(num_probe, len(systems)))
    min_dists = []

    for probe in probes:
        others = [s for s in systems if s["name"] != probe["name"]]
        if not others:
            continue
        min_dists.append(min(distance(probe, s) for s in others))

    if not min_dists:
        print(f"\n{label}: insufficient data")
        return

    min_dists.sort()
    median = min_dists[len(min_dists) // 2]
    mean = sum(min_dists) / len(min_dists)

    print(f"\n{label} ({len(systems):,} systems, {len(probes)} probes):")
    print(f"  Nearest neighbour — mean: {mean:.1f} ly  median: {median:.1f} ly  "
          f"min: {min_dists[0]:.1f} ly  max: {min_dists[-1]:.1f} ly")
    print(f"  % under  50 ly: {100*sum(1 for d in min_dists if d <  50)/len(min_dists):.0f}%")
    print(f"  % under 100 ly: {100*sum(1 for d in min_dists if d < 100)/len(min_dists):.0f}%")
    print(f"  % under 200 ly: {100*sum(1 for d in min_dists if d < 200)/len(min_dists):.0f}%")
    print(f"  % under 500 ly: {100*sum(1 for d in min_dists if d < 500)/len(min_dists):.0f}%")


def analyse_random_sample(systems: list[dict], index: dict, num_probe: int) -> None:
    """Random-sample analysis: for each probe find same-sector+boxel neighbours."""
    procedural = [s for s in systems if parse_sector_boxel(s["name"])]
    probes = random.sample(procedural, min(num_probe, len(procedural)))

    results = []
    no_neighbours = 0

    for probe in probes:
        key = parse_sector_boxel(probe["name"])
        neighbours = [s for s in index[key] if s["name"] != probe["name"]]
        if not neighbours:
            no_neighbours += 1
            continue
        distances = sorted([distance(probe, n) for n in neighbours])
        results.append({
            "name": probe["name"],
            "neighbour_count": len(neighbours),
            "min_distance": distances[0],
            "median_distance": distances[len(distances) // 2],
            "max_distance": distances[-1],
        })

    if not results:
        print("\nNo results — sample is too sparse. "
              "Try --sample-every 50, or use --sector for targeted analysis.")
        return

    min_dists = [r["min_distance"] for r in results]
    median_dists = [r["median_distance"] for r in results]

    print(f"\n{'='*60}")
    print(f"RESULTS: {len(results)} probe systems with sector+boxel neighbours")
    print(f"  ({no_neighbours} probes had no neighbours in sample)")
    print(f"{'='*60}")
    print(f"\nDistance to NEAREST same-sector+boxel neighbour:")
    print(f"  Mean:   {sum(min_dists)/len(min_dists):.1f} ly")
    print(f"  Median: {sorted(min_dists)[len(min_dists)//2]:.1f} ly")
    print(f"  Min:    {min(min_dists):.1f} ly")
    print(f"  Max:    {max(min_dists):.1f} ly")
    print(f"  % under 100 ly: {100*sum(1 for d in min_dists if d < 100)/len(min_dists):.1f}%")
    print(f"  % under 200 ly: {100*sum(1 for d in min_dists if d < 200)/len(min_dists):.1f}%")
    print(f"  % under 500 ly: {100*sum(1 for d in min_dists if d < 500)/len(min_dists):.1f}%")

    print(f"\nDistance to MEDIAN same-sector+boxel neighbour:")
    print(f"  Mean:   {sum(median_dists)/len(median_dists):.1f} ly")
    print(f"  Median: {sorted(median_dists)[len(median_dists)//2]:.1f} ly")

    print(f"\nSample results (5 random probes):")
    for r in random.sample(results, min(5, len(results))):
        print(f"  {r['name']}")
        print(f"    neighbours={r['neighbour_count']}  "
              f"min={r['min_distance']:.1f} ly  "
              f"median={r['median_distance']:.1f} ly  "
              f"max={r['max_distance']:.1f} ly")


def main():
    parser = argparse.ArgumentParser(
        description="Validate prefix-matching accuracy against EDSM bulk data."
    )
    parser.add_argument(
        "--sector", action="append", dest="sectors", metavar="SECTOR_BOXEL",
        help='Target sector+boxel for analysis e.g. "Zunou GS-B". Repeat for multiple.',
    )
    parser.add_argument(
        "--find-dense", action="store_true",
        help="Scan the file and report the most-populated sector+boxels.",
    )
    parser.add_argument(
        "--lines", type=int, default=5_000_000,
        help="Lines to scan when using --find-dense (default: 5,000,000)",
    )
    parser.add_argument(
        "--sample-every", type=int, default=1000,
        help="For random sampling: load every Nth system (default: 1000, ~96k systems)",
    )
    parser.add_argument(
        "--probe", type=int, default=200,
        help="Number of probe systems for distance analysis (default: 200)",
    )
    args = parser.parse_args()

    if not DATA_FILE.exists():
        print(f"Error: {DATA_FILE} not found.")
        print("Download from https://www.edsm.net/en/nightly-dumps and place in data/")
        sys.exit(1)

    if args.find_dense:
        find_dense_sectors(DATA_FILE, args.lines)
        return

    if args.sectors:
        buckets = load_targeted_sectors(DATA_FILE, args.sectors)
        if not buckets:
            print("No matching systems found.")
            sys.exit(1)
        print(f"\n{'='*60}")
        print("DISTANCE ANALYSIS: nearest neighbour within same sector+boxel")
        print(f"{'='*60}")
        for key, systems in sorted(buckets.items(), key=lambda x: -len(x[1])):
            analyse_sector_boxel(systems, f"{key[0]} {key[1]}", args.probe)
        return

    # Default: random sampling
    systems = load_systems_sampled(DATA_FILE, args.sample_every)
    print("Building sector+boxel index...")
    index: dict = defaultdict(list)
    for s in systems:
        parsed = parse_sector_boxel(s["name"])
        if parsed:
            index[parsed].append(s)
    print(f"Index contains {len(index):,} unique sector+boxel combinations.")
    analyse_random_sample(systems, index, args.probe)


if __name__ == "__main__":
    main()
