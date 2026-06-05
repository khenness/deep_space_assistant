#!/usr/bin/env python3
"""
Finds known EDSM systems near an unknown/unexplored system using Elite Dangerous
procedural naming structure (sector, boxel, mass code) as search levels.

Usage:
    python find_nearby_systems.py --system "Stuemeae FG-Y d7561" --results 5
    python find_nearby_systems.py --system "Stuemeae FG-Y d7561" --results 5 --gather

Procedural name structure (community-researched, not official):
    Stuemeae   FG-Y   d   7561
    [sector]  [boxel] [mass code] [sequence]

Mass code approximate boxel sizes:
    a=10ly  b=20ly  c=40ly  d=80ly  e=160ly  f=320ly  g=640ly  h=1280ly
"""

import argparse
import csv
import math
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import requests

EDSM_SYSTEMS_URL = "https://www.edsm.net/api-v1/systems"
OUTPUT_FILE = "data/distance_data.csv"
REQUEST_DELAY = 0.5  # seconds between EDSM requests

# Approximate boxel diameter in ly per mass code (community research, unverified)
MASS_CODE_SIZE_LY = {
    "a": 10, "b": 20, "c": 40, "d": 80,
    "e": 160, "f": 320, "g": 640, "h": 1280,
}



@dataclass
class ParsedName:
    sector: str
    boxel: str
    mass_code: str
    sequence: str
    raw: str

    @property
    def is_procedural(self) -> bool:
        return bool(self.sector and self.boxel and self.mass_code)


def parse_system_name(name: str) -> ParsedName:
    """
    Attempt to parse an ED procedural system name into components.

    Expected format: "Sector XX-X x#### [extra]"
    Examples:
        "Stuemeae FG-Y d7561"     -> sector=Stuemeae, boxel=FG-Y, mass_code=d, sequence=7561
        "Dryau Ausms KG-Y e4912"  -> sector=Dryau Ausms, boxel=KG-Y, mass_code=e, sequence=4912

    Returns a ParsedName with empty strings for components if parsing fails.
    """
    # Pattern: one or more words (sector), then XX-X boxel, then letter+digits
    pattern = r"^(.+?)\s+([A-Z]{2}-[A-Z])\s+([a-h])(\d+)(.*)$"
    m = re.match(pattern, name.strip(), re.IGNORECASE)
    if m:
        return ParsedName(
            sector=m.group(1).strip(),
            boxel=m.group(2).upper(),
            mass_code=m.group(3).lower(),
            sequence=m.group(4),
            raw=name,
        )
    return ParsedName(sector="", boxel="", mass_code="", sequence="", raw=name)


def build_search_levels(parsed: ParsedName) -> list[dict]:
    """
    Build ordered search levels for a parsed procedural name.

    Strategy: strip sequence digits one at a time first (staying within the same
    sector+boxel+masscode), then widen to sector+boxel, then sector-only.

    This means we search d756%, d75%, d7%, d%, then FG-Y %, then Stuemeae %.
    Sequence-stripped searches return the spatially tightest cluster first.
    """
    levels = []

    # Level 1: strip sequence digits one at a time (same sector+boxel+masscode)
    seq = parsed.sequence
    while seq:
        seq = seq[:-1]
        prefix = f"{parsed.sector} {parsed.boxel} {parsed.mass_code}{seq}"
        levels.append({
            "label": f"sector+boxel+masscode (seq prefix '{parsed.mass_code}{seq}')",
            "match_level": "sector+boxel+masscode",
            "prefix": prefix,
        })

    # Level 2: same sector+boxel, any mass code
    levels.append({
        "label": "sector+boxel",
        "match_level": "sector+boxel",
        "prefix": f"{parsed.sector} {parsed.boxel} ",
    })

    # Level 3: same sector only
    levels.append({
        "label": "sector",
        "match_level": "sector",
        "prefix": f"{parsed.sector} ",
    })

    return levels


def edsm_prefix_search(prefix: str) -> list[dict]:
    """Search EDSM for all known systems matching a prefix."""
    try:
        resp = requests.get(
            EDSM_SYSTEMS_URL,
            params={"systemName": f"{prefix}%", "showCoordinates": 1},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        print(f"  [warn] EDSM request failed for prefix '{prefix}': {e}", file=sys.stderr)
        return []


def find_nearby_systems(system_name: str, num_results: int) -> list[dict]:
    """
    Search EDSM at each structural level (sector+boxel+masscode, sector+boxel, sector)
    until we have enough results. Returns up to num_results matches sorted by
    match level (most specific first).
    """
    parsed = parse_system_name(system_name)

    print(f"\nSearching for systems near: {system_name}")

    if parsed.is_procedural:
        size_hint = MASS_CODE_SIZE_LY.get(parsed.mass_code, "?")
        print(f"  Parsed: sector='{parsed.sector}' boxel='{parsed.boxel}' "
              f"mass_code='{parsed.mass_code}' (~{size_hint} ly boxel) sequence='{parsed.sequence}'")
    else:
        print("  Warning: could not parse as a procedural name — falling back to character prefix stripping")

    seen = {}  # system name -> result dict

    if parsed.is_procedural:
        levels_to_try = build_search_levels(parsed)
    else:
        levels_to_try = _character_prefix_levels(system_name)

    for level_index, level in enumerate(levels_to_try):
        if len(seen) >= num_results:
            break

        prefix = level["prefix"]
        print(f"  [{level['label']}] Searching '{prefix}%' ...", end=" ", flush=True)
        time.sleep(REQUEST_DELAY)
        results = edsm_prefix_search(prefix)
        new_count = 0

        for r in results:
            name = r.get("name", "")
            if name and name.lower() != system_name.lower() and name not in seen:
                coords = r.get("coords")
                if coords:
                    seen[name] = {
                        "name": name,
                        "coords": coords,
                        "match_level": level.get("match_level", level["label"]),
                        "search_prefix": prefix,
                        "level_index": level_index,
                    }
                    new_count += 1

        print(f"found {len(results)} systems ({new_count} new with coords)")

    if not seen:
        print("\nNo known systems found.")
        return []

    # Within each match level, sort by sequence number proximity to the input system.
    # Hypothesis: nearby sequence numbers = nearby spatial position within a boxel.
    # This is unverified — tonight's data gathering will test it.
    input_seq = int(parsed.sequence) if parsed.sequence.isdigit() else None

    # Results are already keyed by the level index they were found at (insertion order).
    # Sort by (level_index, sequence_distance) — closest structural match first.
    def sort_key(result):
        seq_distance = 0
        if input_seq is not None:
            m = re.search(r"(\d+)\s*$", result["name"])
            if m:
                seq_distance = abs(int(m.group(1)) - input_seq)
        return (result["level_index"], seq_distance)

    sorted_results = sorted(seen.values(), key=sort_key)

    # Attach sequence distance to each result for the CSV
    for result in sorted_results:
        if input_seq is not None:
            m = re.search(r"(\d+)\s*$", result["name"])
            result["sequence_distance"] = abs(int(m.group(1)) - input_seq) if m else None
        else:
            result["sequence_distance"] = None

    return sorted_results[:num_results]


def _character_prefix_levels(system_name: str) -> list[dict]:
    """Fallback for non-procedural names: generate character-stripped prefix levels."""
    levels = []
    name = system_name.rstrip()
    while len(name) >= 4:
        name = name[:-1]
        levels.append({"label": f"prefix-{len(name)}", "prefix": name})
    return levels


def gather_mode(system_name: str, matches: list[dict]) -> None:
    """Prompt user for in-game distances and append results to CSV."""
    print("\n--- Data Gathering Mode ---")
    print("Enter the in-game distance (ly) to each system (press Enter to skip).\n")

    rows = []
    timestamp = datetime.utcnow().isoformat()
    parsed = parse_system_name(system_name)

    for match in matches:
        name = match["name"]
        while True:
            raw = input(f"  Distance to '{name}' (ly)? ").strip()
            if raw == "":
                print(f"  Skipping '{name}'")
                break
            try:
                distance_ly = float(raw)
                rows.append({
                    "timestamp": timestamp,
                    "input_system": system_name,
                    "input_sector": parsed.sector,
                    "input_boxel": parsed.boxel,
                    "input_mass_code": parsed.mass_code,
                    "input_sequence": parsed.sequence,
                    "matched_system": name,
                    "match_level": match["match_level"],
                    "search_prefix": match["search_prefix"],
                    "sequence_distance": match.get("sequence_distance"),
                    "measured_distance_ly": distance_ly,
                })
                break
            except ValueError:
                print("  Please enter a number.")

    if not rows:
        print("\nNo data entered, nothing saved.")
        return

    output_path = Path(OUTPUT_FILE)
    file_exists = output_path.exists() and output_path.stat().st_size > 0

    with open(output_path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows)

    print(f"\nAppended {len(rows)} row(s) to {output_path.resolve()}")


def main():
    parser = argparse.ArgumentParser(
        description="Find known EDSM systems near an unknown/unexplored system."
    )
    parser.add_argument(
        "--system", "-s",
        required=True,
        help='Name of the unknown system, e.g. "Stuemeae FG-Y d7561"',
    )
    parser.add_argument(
        "--results", "-n",
        type=int,
        default=5,
        help="Number of results to return (default: 5)",
    )
    parser.add_argument(
        "--gather",
        action="store_true",
        help="Enable data gathering mode: prompts for in-game distances and saves to CSV",
    )
    args = parser.parse_args()

    matches = find_nearby_systems(args.system, args.results)

    if not matches:
        sys.exit(1)

    print(f"\nTop {len(matches)} nearby known systems:")
    for i, m in enumerate(matches, 1):
        print(f"  {i}. {m['name']}  [{m['match_level']}]")

    if args.gather:
        gather_mode(args.system, matches)
    else:
        print("\nTip: re-run with --gather to record in-game distances for analysis.")


if __name__ == "__main__":
    main()
