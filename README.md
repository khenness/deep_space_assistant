# Deep Space Assistant

A community tool for the space exploration game [Elite Dangerous](https://www.elitedangerous.com/).

Given an undiscovered system name, finds nearby known systems from the [EDSM](https://www.edsm.net/) database using Elite Dangerous procedural naming structure. Useful when you're deep in unexplored space and need a known reference point.

## How it works

Elite Dangerous system names like `Eol Prou KR-W d100` encode spatial information — sector, boxel, and mass code. Systems sharing the same sector+boxel+masscode are within ~50 ly of each other. The tool uses this to find known neighbours and returns a confidence tier based on how closely the names match.

## Setup

**1. Create a virtualenv and install dependencies**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**2. Download the EDSM bulk data dump**

Download `systemsWithCoordinates.json` from [EDSM nightly dumps](https://www.edsm.net/en/nightly-dumps) and place it in `data/`. The file is ~3.3 GB compressed, ~14 GB uncompressed.

**3. Import the data into SQLite**

```bash
python scripts/import_edsm_dump/import_edsm_dump.py
```

This takes 60–90 minutes and produces `data/edsm.db` (~7 GB). You can test the import is working with `--limit 100` before running the full import.

## Running the web app

```bash
.venv/bin/uvicorn api.main:app --port 8000
```

Then open [http://localhost:8000](http://localhost:8000) in your browser.

The API is also available directly — interactive docs at [http://localhost:8000/docs](http://localhost:8000/docs).

## Running the CLI

```bash
python scripts/find_nearby_systems/find_nearby_systems.py \
  --system "Eol Prou KR-W d100" \
  --local \
  --results 5
```

Use `--gather` to record in-game distances to `data/distance_data.csv` for analysis.

## Running tests

```bash
.venv/bin/pytest tests/ -v
```

Tests use an in-memory SQLite database — no data files required.
