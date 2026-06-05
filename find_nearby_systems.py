#!/usr/bin/env python3
"""
Finds known EDSM systems near an unknown/unexplored system by progressively
shortening the system name prefix and searching for matches.

Usage:
    python find_nearby_systems.py --system "Stuemeae FG-Y d7561" --results 5
    python find_nearby_systems.py --system "Stuemeae FG-Y d7561" --results 5 --gather
"""

import argparse
import csv
import json
import math
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

EDSM_SYSTEMS_URL = "https://www.edsm.net/api-v1/systems"
OUTPUT_FILE = "distance_data.csv"
REQUEST_DELAY = 0.5  # seconds between EDSM requests, be polite


def edsm_prefix_search(prefix: str) -> list[dict]:
    """Search EDSM for all known systems matching a prefix."""
    try:
        resp = requests.get(
            EDSM_SYSTEMS_URL,
            params={
                "systemName": f"{prefix}%",
                "showCoordinates": 1,
            },
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        print(f"  [warn] EDSM request failed for prefix '{prefix}': {e}", file=sys.stderr)
        return []


def euclidean_distance(a: dict, b: dict) -> float:
    return math.sqrt(
        (a["x"] - b["x"]) ** 2
        + (a["y"] - b["y"]) ** 2
        + (a["z"] - b["z"]) ** 2
    )


def generate_prefixes(system_name: str) -> list[str]:
    """
    Yield progressively shorter prefixes of system_name.
    Stops when prefix is too short to be useful (< 4 chars).
    Example: "Stuemeae FG-Y d7561" -> ["Stuemeae FG-Y d756", "Stuemeae FG-Y d75", ...]
    """
    prefixes = []
    name = system_name.rstrip()
    while len(name) >= 4:
        name = name[:-1]
        prefixes.append(name)
    return prefixes


def find_nearby_systems(system_name: str, num_results: int) -> list[dict]:
    """
    Search EDSM using progressively shorter prefixes until we have enough results.
    Returns the `num_results` matches with the most specific (longest) prefix match,
    sorted by prefix length descending (best matches first).
    """
    seen = {}  # system name -> result dict, deduplicated

    print(f"\nSearching for systems near: {system_name}")

    for prefix in generate_prefixes(system_name):
        if len(seen) >= num_results * 3:
            # We have a reasonable pool — stop burning API calls
            break

        print(f"  Trying prefix: '{prefix}' ...", end=" ", flush=True)
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
                        "prefix_length": len(prefix),
                    }
                    new_count += 1

        print(f"found {len(results)} systems ({new_count} new with coords)")

        if len(seen) >= num_results:
            break

    if not seen:
        print("\nNo known systems found. The system name prefix may be too unique.")
        return []

    # Sort by prefix length (longer prefix = more specific match = likely closer)
    sorted_results = sorted(seen.values(), key=lambda x: x["prefix_length"], reverse=True)
    return sorted_results[:num_results]


def gather_mode(system_name: str, matches: list[dict]) -> None:
    """Prompt user for in-game distances and append results to CSV."""
    print("\n--- Data Gathering Mode ---")
    print("Enter the in-game distance (ly) from your current system to each result.")
    print("Press Enter without a value to skip a system.\n")

    rows = []
    timestamp = datetime.utcnow().isoformat()

    for match in matches:
        name = match["name"]
        prefix_len = match["prefix_length"]
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
                    "matched_system": name,
                    "prefix_length": prefix_len,
                    "shared_prefix": system_name[:prefix_len],
                    "measured_distance_ly": distance_ly,
                })
                break
            except ValueError:
                print("  Please enter a number.")

    if not rows:
        print("\nNo data entered, nothing saved.")
        return

    output_path = Path(OUTPUT_FILE)
    file_exists = output_path.exists()

    with open(output_path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows)

    print(f"\nAppended {len(rows)} row(s) to {output_path.resolve()}")
    print("Thank you — this data helps validate whether prefix length predicts distance.")


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
        prefix = args.system[:m["prefix_length"]]
        print(f"  {i}. {m['name']}  (shared prefix: '{prefix}', length {m['prefix_length']})")

    if args.gather:
        gather_mode(args.system, matches)
    else:
        print("\nTip: re-run with --gather to record in-game distances for analysis.")


if __name__ == "__main__":
    main()
