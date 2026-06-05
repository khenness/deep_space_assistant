# find_nearby_systems

A CLI script that finds known EDSM systems near an unknown or undiscovered Elite Dangerous system, using the procedural naming structure to guide the search.

## Background

Elite Dangerous procedural system names encode spatial information:

```
Stuemeae   FG-Y   d    7561
[sector]  [boxel] [mc] [sequence]
```

- **Sector** — a named galactic region, roughly 1280 ly across
- **Boxel** — a spatial subdivision within the sector
- **Mass code** — a single letter (`a`–`h`) indicating approximate boxel size:

| Code | Approx. size |
|------|-------------|
| a    | 10 ly       |
| b    | 20 ly       |
| c    | 40 ly       |
| d    | 80 ly       |
| e    | 160 ly      |
| f    | 320 ly      |
| g    | 640 ly      |
| h    | 1280 ly     |

- **Sequence** — a number identifying a system within the boxel. Hypothesised (unverified) to encode spatial position.

> These naming conventions are community-researched and not officially documented by Frontier Developments.

## Usage

```bash
# Activate the virtualenv from the repo root
source .venv/bin/activate

# Find nearby systems (display only)
python src/scripts/find_nearby_systems/find_nearby_systems.py --system "Stuemeae FG-Y d7561" --results 5

# Find nearby systems and record in-game distances
python src/scripts/find_nearby_systems/find_nearby_systems.py --system "Stuemeae FG-Y d7561" --results 5 --gather
```

### Arguments

| Argument | Short | Default | Description |
|----------|-------|---------|-------------|
| `--system` | `-s` | required | Your current system name |
| `--results` | `-n` | 5 | Number of candidate systems to return |
| `--gather` | | off | Enable data gathering mode |

## How the search works

The script searches EDSM at progressively wider levels, stopping as soon as it has enough results:

1. `Stuemeae FG-Y d756%` — same sector, boxel, mass code, sequence prefix (tightest)
2. `Stuemeae FG-Y d75%` — wider sequence prefix
3. `Stuemeae FG-Y d7%` — wider still
4. `Stuemeae FG-Y d%` — all systems with same sector+boxel+masscode
5. `Stuemeae FG-Y %` — same sector+boxel, any mass code
6. `Stuemeae %` — same sector only (widest)

Within results, candidates are sorted by sequence number proximity to your input system (e.g. `d7560` ranks above `d7566` when searching for `d7561`). This proximity sorting is an unvalidated hypothesis — see data gathering below.

## Data gathering mode

In `--gather` mode, after displaying results the script prompts you for the in-game distance to each candidate system. Alt-tab into the game, open the galaxy map, search for the system, read off the distance, and type it in. Press Enter with no value to skip.

Distances are appended to `data/distance_data.csv` in the repo root.

## CSV data structure

`distance_data.csv` schema:

| Column | Description |
|--------|-------------|
| `timestamp` | UTC timestamp of the run. Rows sharing a timestamp are from the same session. |
| `input_system` | The full system name you entered. |
| `input_sector` | Parsed sector component (e.g. `Stuemeae`). Proxy for galactic region. |
| `input_boxel` | Parsed boxel identifier (e.g. `FG-Y`). |
| `input_mass_code` | Parsed mass code letter (e.g. `d`). Indicates approximate boxel size. |
| `input_sequence` | Parsed sequence number (e.g. `7561`). |
| `matched_system` | The known EDSM system returned as a candidate. |
| `match_level` | How specific the search was: `sector+boxel+masscode`, `sector+boxel`, or `sector`. Narrower is better. |
| `search_prefix` | The exact prefix string sent to EDSM (e.g. `Stuemeae FG-Y d756`). |
| `sequence_distance` | Absolute difference between `input_sequence` and the matched system's sequence number. |
| `measured_distance_ly` | The actual in-game distance in light years, as read from the galaxy map. This is the ground truth. |

### Key experimental question

Does smaller `sequence_distance` predict smaller `measured_distance_ly`?

If yes: sequence numbers encode spatial position within a boxel, and we can use them to rank candidates by likely proximity.

If no: sequence numbers are not spatially ordered and a different ranking approach is needed.
