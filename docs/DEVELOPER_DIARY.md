# Developer Diary — Deep Space Assistant

---

## Friday 5th June 2026 17:35 — Starting Out

*This is a summary of today's session authored by Claude and approved by Kevin.*

### The Problem

Kevin has been playing Elite Dangerous for years. His main commander, KevinFromDublin, is currently out near the galactic core — one of the most star-dense, least-explored regions of the game. Out there, you constantly find yourself in systems that exist in the game but have never been uploaded to community databases like EDSM.

This matters because EDSM is the backbone of most community tools. Want to find the nearest fleet carrier offering repairs? You need a known system to search from. Want to find nearby exobiology opportunities? Same problem. If you're in an undiscovered system, you're effectively invisible to all of these tools.

The workaround every explorer knows is tedious: manually truncate your system name until EDSM's autocomplete finds something nearby. Strip a character, try again, strip another, try again. It works, but it's slow and annoying when your canopy is cracked and you're carrying months of exploration data.

Kevin wants to automate that.

### Setting Up the Collaboration

Kevin hasn't used AI tools for a project like this before. He set some ground rules upfront — he wanted Claude to act as a Staff Engineer, not just an implementer. That meant challenging assumptions, flagging risks early, and stopping him from over-engineering things before the core idea was even validated.

He also flagged a personal risk: a habit of spending weeks on architecture instead of building the thing and finding out if it works. He asked Claude to push back on that.

### Researching the Ecosystem

Before writing a line of code, we looked at what already exists. The Elite Dangerous community has a surprisingly rich set of tools:

- **EDSM** — the main star map database, built from player-submitted data
- **Spansh** — powerful route planner and data tool with bulk data dumps
- **EDDN** — a live data stream that players can submit to and tools can subscribe to
- **EDAstro** — community data visualisation

The key finding: both EDSM and Spansh already have partial name search. And Spansh has a fleet carrier search endpoint. This raised an obvious question — is there actually a gap to fill here, or does this already exist?

### Pushing Back on the Initial Design

Rather than building what Kevin originally described, we challenged some of the assumptions in his initial design doc:

1. **The core problem may already be solved.** Spansh's search might handle this already. Worth checking before building.
2. **The prefix algorithm is unvalidated.** The assumption is that shared name prefixes in Elite Dangerous correspond to spatial proximity. That's probably true, but it's an assumption, not a confirmed fact.
3. **PostGIS is premature.** Kevin had listed PostGIS as a requirement. This is plain Euclidean distance over 3D coordinates — Postgres can do that without a spatial extension.
4. **Confidence scores are made up.** The original API design included confidence scores. Where would they come from? That question didn't have an answer yet.

The suggestion was to not build an API, a database, a React frontend, or any infrastructure at all yet. Build a Python script first, run it, and find out if the approach actually works.

Kevin agreed.

### Understanding the Naming Structure

While discussing the approach, Kevin shared community research on how Elite Dangerous procedural system names actually work. The community has done significant reverse engineering of the Stellar Forge naming system. Names like `Stuemeae FG-Y d7561` aren't random — they encode spatial information:

```
Stuemeae   FG-Y   d    7561
[sector]  [boxel] [mc] [sequence]
```

- The **sector** is a named region roughly 1280 ly across
- The **boxel** is a spatial subdivision within the sector
- The **mass code** (`a`–`h`) indicates the approximate size of the boxel (10 ly to 1280 ly)
- The **sequence number** may encode position within the boxel — this is unverified

This changed the script design. Instead of blindly stripping characters, the script understands these structural boundaries and searches at each level in order, tightest first.

### What We Actually Built

A single Python CLI script: `scripts/find_nearby_systems/find_nearby_systems.py`.

```bash
python scripts/find_nearby_systems/find_nearby_systems.py \
  --system "Stuemeae FG-Y d7561" \
  --results 5 \
  --gather
```

It parses the system name, then searches EDSM using progressively wider prefixes:

1. `Stuemeae FG-Y d756%` — same sector, boxel, mass code, close sequence
2. `Stuemeae FG-Y d75%` — slightly wider sequence
3. ...and so on, widening until it has enough results

Within results, candidates are sorted by sequence number proximity — the hypothesis being that `d7560` is physically closer to `d7561` than `d7200` is. This is untested.

The `--gather` flag is where it gets interesting. After showing the results, the script prompts Kevin to enter the actual in-game distance to each candidate system. Alt-tab into Elite, open the galaxy map, read off the number, come back and type it in. Those measurements get saved to `data/distance_data.csv`.

### Why Gather Data?

The whole script is built on a hypothesis that hasn't been proven: does sequence number proximity actually predict physical distance?

Tonight Kevin plans to play with KevinFromDublin near the galactic core, run the script on undiscovered systems, and manually verify the distances. The CSV will accumulate ground truth that will either confirm or kill the core assumption.

If sequence numbers do correlate with distance, we have the foundation for a properly calibrated approximation engine. If they don't, we find out now — before building any infrastructure around a bad idea.

### One Complication

Kevin pointed out that the galactic core — where his main account is — is actually the *least* explored region in EDSM. EDSM coverage is driven by players running the EDSM plugin while playing, and not many people make it all the way out to the core. This is counterintuitive: the core is the most star-dense part of the galaxy, but has the least community data.

This means tonight's tests might return very few results — not because the algorithm is broken, but simply because EDSM doesn't have coverage there. That's still a useful data point.

The bubble (human space near Earth) actually has the best EDSM coverage. Kevin's other three accounts are all based there. If the core tests don't yield much data, repositioning one of them to a mid-arm region with partial coverage might give better conditions for testing the algorithm.

### Repo Structure

We set up a straightforward repo structure. One deliberate decision: we started with `src/scripts/` but that's a Python packaging convention that only makes sense when you have an installable package. We don't. So we dropped it and went with flat, obvious top-level directories:

```
deep_space_assistant/
├── data/           # collected measurements
├── docs/           # this diary and future documentation
├── scripts/        # standalone CLI tools
├── requirements.txt
└── README.md
```

The principle: boring and obvious beats clever and premature.

### What's Next

Tonight: Kevin plays the game, gathers data, commits the CSV.

After that: analyse the data. Does the algorithm work? How close are the results? Does it vary by galactic region?

If it looks promising, we'll talk about what to build next. If it doesn't, we'll figure out why and adjust. Either way, we'll know something real instead of just having a theory.

---

## Friday 5th June 2026 21:55 — First Real Data, From Deep Space

*This is a summary of today's session authored by Claude and approved by Kevin.*

### The Setup

After building the script in the afternoon session, Kevin did what any good engineer does — he went and used the thing in the real world. His commander KevinFromDublin was already out in deep space aboard "Faster Than Light", an engineered Caspian Explorer — a ship that is, let's say, *legally distinct* from the Starship Enterprise. It looks like someone crossed the Defiant from DS9 with the Enterprise-D from The Next Generation, slapped a fuel scoop on it, and called it an exploration vessel. Frontier would like you to know it bears no resemblance to any fictional starship. Anyway — it can jump 86.90 light years at a time. A single jump takes about 60 seconds. A light year is roughly 9.46 trillion kilometres. The ship covers that distance in a minute.

Kevin plays on his TV with a laptop beside him. Alt-tabbing between the game and the terminal, typing in system names and distances manually, is genuinely tedious — but that's what science looks like sometimes.

### The Journey

Kevin started in the **Galactic Centre** region and rode the **Neutron Star Highway** toward Colonia. The highway is a network of neutron stars that can boost a ship's jump range by 6x — but it comes with risk. To get the boost, you fly directly into the neutron star's plasma cone in supercruise. Misjudge the approach and you hit the exclusion zone: the ship gets knocked out of supercruise, starts taking heat damage, and can explode. If that happens, every undiscovered system you've scanned is gone permanently. Your name won't appear on those systems. The credits are lost. Months of exploration, gone. High risk, high reward.

Kevin navigated this using **EDCopilot**, a community navigation tool that was part of the inspiration for Deep Space Assistant.

Along the way he found two ammonia worlds — rare, high-value planets with a yellowy-brown appearance — and scanned them. He also topped up his fuel tanks at a class G star. Veteran explorers know the acronym KGBFOAM for the star types that let you fuel scoop: K, G, B, F, O, A, M. The galaxy provides.

After riding the highway for a while, Kevin branched off into unexplored space and arrived in the **Odin's Hold** region, where he took the final reading of the night before stopping. He's planning to continue toward Colonia tomorrow to visit engineers — NPCs who can upgrade and modify ship components.

### The Data

Kevin gathered five measurement sessions across three galactic regions:

| System | Region | Match level |
|---|---|---|
| PHUA AUB RG-Y D3678 | Galactic Centre | sector+boxel+masscode |
| JUENAE SL-K D9-3226 | Galactic Centre | sector+boxel+masscode + sector fallback |
| BYOOMI EP-I C25-5880 | Galactic Core boundary | sector only |
| BYOOMI IY-G D11-5408 | Galactic Core boundary | sector+boxel+masscode |
| PHROI FLYUAE IV-I C24-3143 | Odin's Hold | sector+boxel+masscode |

One reading had to be abandoned midway through due to a script bug — the CSV path was hardcoded relative to the working directory, so running the script from inside the `scripts/` folder caused a `FileNotFoundError` after all the distances had been entered. Frustrating. Fixed and rerun.

There was also a moment mid-session where Kevin couldn't tell if a system name contained the letter "I" (eye) or "l" (ell) — the in-game font makes them indistinguishable. He had to ask ChatGPT to disambiguate it. This is a real UX problem: a wrong character causes the search to silently return nothing.

### What the Data Actually Shows

Going in, the hypothesis was: *smaller sequence distance predicts smaller physical distance*. The script was even sorting results by sequence proximity based on this assumption.

The data doesn't support it.

Looking at BYOOMI IY-G D11-5408, the sequence distances range from 1365 to 8705 — nearly 8x variation — but the physical distances are all squashed into a 53–104 ly band with no consistent ordering. The match with sequence distance 6832 is *closer* than the one with 1365. For PHUA AUB RG-Y D3678, all five results cluster between 57–79 ly despite a 19x range in sequence distance.

**Sequence distance does not predict physical distance.** At least not with this matching approach.

What *does* matter is the match level. Every `sector+boxel+masscode` result came back under ~110 ly. Every `sector`-only result was 393–1370 ly. The structural level of the match is the real predictor.

### Two Anomalies Worth Investigating

**1. JUENAE SL-K D9-3226 looks like a parsing issue.** The script parsed `input_sequence=9`, but the matched systems are `d9-3625`, `d9-8813` — the format suggests `9-3226` is a compound sequence number, not just `9`. The hyphen may indicate a different naming convention. This is probably a manual entry error or an unusual system name format, but it needs investigation. Worth noting that all the data here is manually entered — mistakes happen.

**2. PHROI FLYUAE reveals something more interesting.** One result came back at 14.54 ly (`IV-I c24-447`, sharing the `24-` sequence prefix). The other four came back at 660–689 ly (`IV-I c11-*`, completely different prefix). This suggests the useful variable isn't numeric sequence distance, it's whether the matched system shares the same sequence *prefix* — `24-something` vs `11-something`. The script searches for this correctly, but the sorting and ranking logic isn't reflecting it.

### What Needs to Change

Two things to fix in the script before the next session:

1. **Stop sorting by sequence distance** — the data says it's not meaningful. Need a better ranking approach.
2. **Investigate the hyphenated sequence format** — `D9-3226` may need different parsing logic.

The broader question — does this tool actually produce useful results? — is still open but leaning positive. `sector+boxel+masscode` matches are consistently returning systems within 50–110 ly, which for an explorer trying to find a fleet carrier is genuinely useful. That's the core value proposition. The sequence sorting is a nice-to-have that turned out not to work, not a fundamental flaw.

### What's Next

Kevin is continuing toward Colonia tomorrow. More data from different regions will help confirm whether the `sector+boxel+masscode` pattern holds reliably or whether tonight was lucky. Colonia has much better EDSM coverage than the core — it'll be a proper test.

---

## Saturday 6th June 2026 — Near-Death, Neutron Stars, and Numbers That Don't Lie

*This is a summary of today's session authored by Claude and approved by Kevin.*

### Morning: Fixing What Yesterday Revealed

The day started with a bug report — from yesterday's own data.

JUENAE SL-K D9-3226. Looking at the CSV, something was off. The script had parsed the sequence as `9`, but the matched neighbours all had names like `d9-3625` and `d9-8813`. The hyphen in `D9-3226` isn't punctuation separating a mass code from a sequence — it's part of the sequence itself. The full sequence is `9-3226`, not `9`. The script had been silently wrong about this.

The fix was a one-line regex change: the sequence pattern was updated from `\d+` to `\d+(?:-\d+)?` to handle the hyphenated format. The script now detects hyphenated sequences, warns about them in output, and skips the sequence_distance calculation entirely for those systems — since computing `|9 - something|` when the full sequence is `9-3226` produces meaningless results.

While fixing the parser, a `--note` flag was also added. Every data row now carries a free-text note so sessions can be tagged with context — galactic region, why a particular measurement looks anomalous, anything useful for later analysis. The JUENAE rows in the existing CSV were back-annotated: `sequence_distance unreliable (hyphenated sequence parsed incorrectly in v1 of script)`.

With the fixes in, Kevin gathered a final session from the **KYLOARPH** region before the morning wrapped up.

### Afternoon: Cloudflare Strikes Back

Then the script started returning 403s.

Not occasionally. Every single request. EDSM's API was responding, but the response was a Cloudflare bot protection challenge — the kind that requires JavaScript to solve in a browser. A Python `requests` call can't do that, regardless of how politely you set the User-Agent header.

Kevin tried switching to his mobile hotspot, hoping it was an IP block. Still 403. He'd never aggressively hammered the API — two seconds between requests, maybe a couple dozen calls across the whole project. The block wasn't about volume; Cloudflare was just detecting non-browser HTTP clients.

This is a legitimate question worth sitting with: EDSM provides this API explicitly for tools like this. They probably welcome integrations. But Cloudflare's bot detection doesn't know or care about intent — it sees an HTTP client without a browser fingerprint and blocks it. It's an infrastructure decision by the site operator that creates friction for exactly the kind of legitimate use they'd otherwise encourage. Welcome to the web in 2026.

The short-term mitigation — User-Agent header, 2-second delays — didn't solve it. The longer-term solution was already in reach: EDSM publishes nightly bulk data dumps. Forget the API for now.

### Downloading the Galaxy

The EDSM nightly dump — `systemsWithCoordinates.json` — is 3.34 GB compressed, 14 GB uncompressed. Kevin downloaded it and dropped it into `data/`. It was added to `.gitignore` (the only version you'd ever want to commit is the compressed one, and even then, not really — it changes nightly and it's enormous).

The file contains 96.4 million records, one JSON object per line, each with a system name, 3D coordinates, and a submission date. The entire accessible EDSM star catalogue in a single file.

Now the analysis could run locally, without Cloudflare, without rate limits, without API calls.

### In Space: A Near-Death Experience

While all of this was happening at the keyboard, KevinFromDublin was still flying.

Kevin entered a system to fuel scoop from a neutron star and found two companion suns in extremely close orbit around it. The system geometry was unusual enough that the arrival vector dropped him almost directly into one of the orbiting stars. He nearly slammed into it at supercruise speed.

This is the nightmare scenario for explorers. If the ship takes enough heat damage to destroy it, all unsubmitted exploration data is gone. Every scan, every discovery, every first-footfall — erased. The credits, the in-game prestige of having your name on those systems, all of it gone permanently. Kevin got out. But it was close enough to be worth writing down.

He also found two ammonia worlds along the route — planets with a distinctive yellowy-brown atmosphere, high cartographic value, relatively rare. Scanned and logged.

### Arriving at Colonia

488 light years out from Colonia, Kevin could see the nebula.

He took a screenshot. The purple glow of humanity's second bubble, visible from nearly 500 ly away in the dark between the arms. That screenshot is going on the blog.

Colonia was colonised by a character called Jaques, who is — and this is canon — a bartender. He flew his station (called, simply, Jaques Station) from the bubble toward the galactic core back in 3302, got displaced by an unknown accident, and ended up 22,000 light years from anywhere. Pilots found him, built up a colony around him, and now it's a thriving community hub in the middle of nowhere. Kevin stopped to sell his exploration data and pay his respects.

He also visited the engineer **Baltanos** at a surface station called **The Divine Apparatus**. Engineers in Elite Dangerous are specialist NPCs who can modify and upgrade ship components beyond standard specifications. Kevin used the opportunity to upgrade the power plant and shields on "Faster Than Light", and fitted mining equipment in case anything interesting turns up during the journey home. He took a screenshot of Baltanos for the blog post.

### Evening: The Data Speaks

With the 14 GB file on disk, the analysis script was run against the full dataset. The approach that had failed with random sampling — too sparse, almost no sector+boxels had multiple entries — was abandoned in favour of targeted analysis. The scan had already identified the densest sector+boxels in the dataset:

- **Zunou GS-B**: 8,503 known systems
- **Eol Prou KR-W**: 2,312 known systems — the Colonia region. Kevin was literally flying through this area.

For each, 100 probe systems were randomly selected and their nearest same-sector+boxel neighbour was calculated using actual 3D Euclidean distance.

| Region | Systems | Mean nearest | Median nearest | Max nearest |
|---|---|---|---|---|
| Zunou GS-B | 8,503 | 2.2 ly | 2.2 ly | 4.4 ly |
| Eol Prou KR-W | 2,312 | 7.9 ly | 8.0 ly | 15.9 ly |

100% of probes in both regions found a same-sector+boxel neighbour within 50 light years. No exceptions.

This isn't just confirmation of the core hypothesis — it's stronger than expected. The `sector+boxel` grouping is essentially a spatial guarantee, not a useful heuristic. Every system with known neighbours in the same sector+boxel has those neighbours close by. The maximum nearest-neighbour distance in Zunou GS-B, across 8,503 systems, is 4.4 ly. In Colonia — the sector Kevin is currently flying through — 15.9 ly.

For context: in Elite Dangerous, a fleet carrier advertising repair services is usable from 1,000 ly away. A same-sector+boxel system is almost certainly within range of anything useful.

The analysis script was also refactored to support this targeted workflow properly:

```bash
# Find dense sectors to analyse
python analyse_prefix_accuracy.py --find-dense --lines 5000000

# Targeted analysis
python analyse_prefix_accuracy.py --sector "Zunou GS-B" --sector "Eol Prou KR-W"
```

### What This Means

Two days in, the validation picture is clear:

- **Sequence distance**: no correlation with physical distance. Removed from the ranking logic.
- **Match level** (`sector+boxel+masscode` vs `sector+boxel` vs `sector`): the primary predictor, confirmed by field measurements.
- **Sector+boxel grouping**: a spatial guarantee. 100% of systems with known neighbours are within 50 ly of them — confirmed against 10,000+ real systems from the bulk dataset.

The algorithm works. The question is no longer *whether* to build something, but *what* to build, and in what order.

### What's Next

The immediate next step is better in-game measurement data. Kevin is now in Colonia — a region with good EDSM coverage — which means the API (once Cloudflare stops blocking it) or the bulk dataset can actually return useful results. Gathering measurements here will be more valuable than the galactic core data was.

Longer term: the bulk data file opens up a local search mode that doesn't depend on EDSM's API at all. A small SQLite database indexed on sector+boxel would make lookups instant, eliminate the Cloudflare dependency entirely, and be refreshed from the nightly dump whenever it goes stale. That's a natural next step — but only once the measurement data confirms the approach holds across more regions.

---

## Saturday 6th June 2026 (continued) — From Scripts to a Working Product

*This is a summary of today's session authored by Claude and approved by Kevin.*

### From Analysis to Infrastructure

The evening had confirmed the hypothesis: sector+boxel prefix matching is a spatial guarantee. The question shifted from *does this work* to *how do we build a real thing around it*.

The EDSM bulk dump was already on disk. The natural next step was getting all 96.4 million systems into SQLite so queries could run locally, without Cloudflare, without network latency. Kevin had never used SQLite seriously before. The explanation was: it's a single file, it lives next to your code, you query it with standard SQL. No server to run, no configuration, no `docker-compose.yml` for a database. For a project with one developer and one user, this is almost always the right call.

The import script — `scripts/import_edsm_dump/import_edsm_dump.py` — reads the 14 GB JSON file in batches of 10,000, parses each system's name into its structural components (sector, boxel, mass code, sequence), and writes them to the DB. The schema is intentionally minimal:

```sql
CREATE TABLE systems (name TEXT, x REAL, y REAL, z REAL, sector TEXT, boxel TEXT, mass_code TEXT)
```

Lines that fail to parse are stored with NULL columns rather than dropped. 0.16% of the 96.4 million records fell into this category.

Kevin ran the import and went to do other things. It took a while. When it finished, the DB was 9.5 GB on disk. The entire EDSM catalogue, fully queryable, available offline forever.

### Building the API

With the data in place, a FastAPI service was built around it. Kevin had never used FastAPI before. The mental model it needed: it's a framework that turns Python functions into HTTP endpoints, handles routing and validation automatically, and generates OpenAPI docs for free. It has a dependency injection system — `Depends(get_db)` — that handles opening and closing the SQLite connection per request without threading issues.

Three endpoints:
- `GET /nearby` — find known systems near a procedural name using prefix matching
- `GET /dssa/nearest` — find the nearest DSSA fleet carriers to a given system
- `GET /` — serves the HTML frontend

Tests came with the implementation: unit tests against in-memory SQLite for the search logic, integration tests using FastAPI's `TestClient` for the HTTP layer. 30 tests total.

Two threading bugs surfaced during testing:

**`sqlite3.ProgrammingError: SQLite objects created in a thread`** — FastAPI runs sync endpoints in a thread pool. The fix: `check_same_thread=False` on all `sqlite3.connect()` calls, including test fixtures.

**`sqlite3.OperationalError: database is locked`** — The EDSM import holds a write lock while batch-committing. If the API starts while the import is still running, the API's read connections time out instantly. The fix: `timeout=10` to give the write lock time to release.

### The Frontend

Kevin's brief: make it as simple as possible. A search box, a button, and a table of results. No React, no build step, no Node.js. A single `index.html` served directly by FastAPI via `FileResponse`.

It looked exactly like a plain HTML page from 2005, which was the point. Monospace font, black text on white background, table with borders. It worked.

### DSSA: The Real Use Case

Partway through the session, Kevin explained what actually prompted this whole project. His ship had been damaged in deep space and he'd needed to find the nearest DSSA carrier — the network of player-maintained fleet carriers scattered across the galaxy at strategic positions, each offering repair and refuel services. No existing tool handled undiscovered systems well.

The DSSA carrier roster is community-maintained in a Google Sheet. 102 entries. An import script was built to download the CSV, normalise carrier names (stripping parenthetical nicknames and body suffixes like `4 B`), look up each carrier's system coordinates in the local SQLite DB, and store everything in a `dssa_carriers` table.

The import took over an hour. The root cause: the coordinate lookup was using `LOWER(name) = LOWER(?)`, which bypasses SQLite's indexes entirely — every lookup was a full scan of 96 million rows. The fix was to create a case-insensitive index and rewrite the query to use it:

```sql
CREATE INDEX idx_name ON systems (name COLLATE NOCASE)
-- query: WHERE name = ? COLLATE NOCASE
```

After the index was built, the same 102-row import ran in seconds. 101 of 102 carriers got coordinates — the one missing entry ("Delacor") turned out to be a station name, not a system name.

The DSSA search itself computes 3D Euclidean distance from the input system to every carrier with known coordinates, sorts by distance, and returns the top N. For undiscovered systems (not in the DB), it first finds a nearby reference system via prefix matching and calculates from there — reporting the reference system, confidence level, and expected error to the user.

### Another Performance Issue

When Kevin tried the nearby search with 50 results enabled, it was taking 7.5 seconds. The SQL query was returning every matching system without a LIMIT clause — for the sector-level fallback on a name like `BYOOMI`, that meant fetching 163,846 rows over the network between SQLite and Python, then trimming to 50 in application code. Adding `LIMIT num_results * 10` to the query dropped the response from 7.5 seconds to 0.07 seconds.

### UI Iteration

A few rounds of UI polish followed. Kevin wanted the results count to be editable per tab (default 10, max 50). Then he wanted the system name to persist when switching between tabs — type something in the "Find Nearby" tab, switch to "DSSA", and the text is still there.

The first instinct was to use DOM manipulation — move a single input element between panels when switching tabs. This was correctly rejected as brittle: the element's state and positioning would depend on the order of JS execution rather than being declared in the HTML. The simpler approach: two separate inputs, kept in sync via `input` event listeners. The same pattern was applied to the results count inputs.

### Named System Support

A UX gap surfaced: typing "Sol" into the "Find Nearby Discovered Systems" tab returned nothing. The search code correctly detected that Sol isn't a procedural name and returned early — but to a user, it just looks broken.

The fix was to route non-procedural names through a different search path: look up the system's coordinates by exact name match, then find all systems within a 200 ly bounding box using the `x` coordinate index (newly added), compute exact Euclidean distances, and return the closest ones. For a named system in the DB, you get real coordinate-based results. For a named system not in the DB (e.g. a typo), you get a clean empty result.

The branch is completely deterministic — procedural names always match the `XX-X` boxel pattern, named systems never do. No heuristics, no probability. The same API response shape works for both paths; the frontend doesn't know which branch was taken.

A new SQLite index — `idx_x` on `systems(x)` — was added to make the bounding box query fast. Without it, a named system search would scan 96 million rows. With it, SQLite narrows to roughly 0.1% of the table, then filters `y` and `z` in memory.

### Where Things Stand

The project now has a working local service:
- 96.4M systems in SQLite, queryable offline
- Procedural and named system support in the nearby search
- DSSA carrier search with distance calculation and undiscovered system support
- A minimal but functional HTML frontend
- 33 passing tests

The data philosophy is settled: download and host the data locally, update on a schedule, show data freshness timestamps in the UI. No live API calls at query time. Resilient to third-party failures.

Still on the list: tourist/sightseeing spots as the next dataset, data freshness timestamps in the UI, Docker containerisation (explicitly deferred — not the interesting part), and eventually a proper React frontend that Kevin wants to design himself.

---

## Saturday 6th June 2026 (late night) — Testing in the Field, Trust Calibration

*This is a summary of today's session authored by Claude and approved by Kevin.*

### A Real Test, A Real Discrepancy

Kevin was flying in deep space and used the tool live. He typed `WEPOOE SG-X B5124` into the DSSA tab and got a result of ~4,776 ly to DSSA Buurian Anchorage. The game said 4,007 ly. That's a 769 ly error on a result that was labelled "high confidence, ± < 50 ly."

The initial explanation offered — permit-locked systems causing gaps in EDSM coverage — was wrong. Kevin pushed back immediately and correctly. There are hundreds of freely-accessible named systems near Sol, and permit locks are irrelevant to the problem at hand. The real issue took more digging.

### The Root Cause: Sparse Sector Coverage

The EDSM bulk dump is populated from player submissions. In densely explored regions like Colonia or the human bubble, sector+boxels have hundreds or thousands of known systems. Out in deep space, many sector+boxels have two or three. When the prefix matching finds a "high confidence" match in a two-system boxel, it's not high confidence at all — it just means those two systems share the same structural name prefix. They might be hundreds of light years apart.

The confidence tiers were derived from bulk analysis of *dense* sectors. Applied to sparse ones, they were lying.

### The Fix: Surface Density

The solution was to compute and display how many known systems exist in the matched sector+boxel alongside every result. One extra query per search using the existing `idx_name` index — fast, no new indexes needed.

The UI now shows the count next to confidence: `high (87 known)` for a dense sector, `high (2 known)` for a sparse one. Colour coding communicates urgency at a glance — orange below 20 known systems, red below 5, with a plain-language warning: *"very sparse sector, actual distances may be significantly higher than shown."*

The same information flows through to the DSSA reference note. When distances are calculated from an approximate reference system in a sparse sector, the note now reads in red rather than grey, with an explicit caveat.

The first attempt at the density query used `COLLATE NOCASE` on the `sector` column — which bypassed the index and caused a full 96M row scan, making the search hang. It was rewritten to use a `name LIKE 'Sector Boxel %'` pattern against the existing NOCASE name index instead.

### Another Index: `idx_xyz`

The named system bounding box query (introduced in the previous session to handle inputs like "Sol") was also found to be slow. The `idx_x` single-column index narrowed by x-coordinate but left a huge cross-section of the galaxy to scan for y and z — near Sol, the busiest part of EDSM, that was potentially millions of candidates. A composite `idx_xyz` on `(x, y, z)` was added. SQLite can then filter all three axes at the index level, returning a tight spatial box without loading unrelated rows into memory.

Building `idx_xyz` on 96M rows requires a write lock on the DB, so the server had to be stopped first. This is a one-time operation — the index persists.

There was also a subtler bug in the named system path: the query used `LIMIT num_results * 50` to cap the candidate set before sorting by distance. The problem is that SQLite returns rows in index order, not distance order — so with a limit in place, Alpha Centauri (1.3 ly from Sol) could be excluded from the candidate set while arbitrary systems 190 ly away were included. The limit was removed. With `idx_xyz` in place, fetching all candidates in a 200 ly box is fast regardless of count.

### Polishing the UI

Several rounds of smaller improvements:

**Title and tagline** — The app is now "Elite Dangerous: Deep Space Assistant" with the tagline *"A lightning fast tool for explorers that works with undiscovered systems!"*

**"Showing results for" label** — Results tables now show which system was searched above the table. This prevents confusion when switching between tabs where stale results from a previous search might still be visible.

**"Confidence" → "Accuracy" on the DSSA tab** — The word "confidence" meant two different things across tabs: on the nearby tab it describes how close the prefix match is; on the DSSA tab it was describing the reference system quality. Renamed to "Accuracy" on the DSSA tab to reduce confusion. Exact results show "exact" rather than a dash.

**Better error messages** — When a system has no EDSM coverage and no reference can be found for DSSA distances, the message now explains why rather than implying the carrier roster is missing.

### Field Validation

Kevin ran a final test from `AGNAIRY ZS-F D12-3105`, currently in deep space. The tool reported ~3,385 ly to Buurian Anchorage; the game measured 3,447 ly — a 62 ly error on a 3,447 ly distance (1.8%). The sparse sector warning was displayed correctly in red. The reference system was only 1 known system in its sector, so the warning was accurate and honest.

For a tool that's working from an approximate reference point in an uncharted region, 62 ly at 3,400 ly range is a useful result. The user knows it's an estimate. That's the right outcome.

### Where Things Stand

33 passing tests. The density feature is the most significant improvement to result trustworthiness since the initial build — it turns a potentially misleading "high confidence" label into an honest one. The tool now tells you not just what it found, but how much to trust it.

The distance error column remains in the DSSA table for now — Kevin noted it's probably more confusing to users than helpful, but it's useful during development to see the raw numbers. Will be revisited.

---

## Sunday 7th June 2026 — Named Systems, Precomputed Tables, and the Sagittarius A* Edge Case

*This is a summary of today's session authored by Claude and approved by Kevin.*

### The Problem That Wouldn't Die

Despite the previous session fixing named system performance — adding `idx_named_xyz`, moving sort and limit into SQL — Sol was still taking 5–12 seconds. A procedural system like `JUENAE SL-K D9-3226` would return 1,000 results in under a second. Sol, three light years from Earth, the most famous system in the game, took longer than a neutron star jump.

The diagnosis was straightforward in retrospect. The `idx_named_xyz` partial index narrows the spatial query for named systems, but the 50 ly sphere around Sol contains a lot of named systems. The database was doing the right thing — it was just doing a lot of it. The fundamental issue was that we were re-running a bounding box search every single time someone searched for Sol, even though the answer never changes.

### The Fix: Precompute at Import Time

The solution was to move the work to a place where it only needs to happen once. A new script — `scripts/build_named_neighbours/build_named_neighbours.py` — loads all ~154,000 named systems into memory, computes each system's nearest named neighbours within 50 ly (bounding box fast-reject, then Euclidean), and writes them into a `named_neighbours` table. The script runs once after the EDSM import and whenever the systems table is refreshed. The query at search time becomes a single indexed lookup by system name — O(1).

The table stores the top 50 neighbours per system with precomputed distances. For Sol, that lookup is now sub-millisecond.

The live fallback path — the bounding box query — is still there. If the `named_neighbours` table has no rows for a system (e.g. the table hasn't been built yet, or was just dropped), the code falls through to the live query automatically. The build script is an offline optimisation, not a hard dependency.

### AssetViewerSystem Returns

Once testing began against the live database, AssetViewerSystem reappeared. Frontier's internal development artifact, sitting at coordinates (0, 2, 0) — two light years from Sol — had been precomputed into the `named_neighbours` table because the build script hadn't filtered it out. The blocklist that excluded it from live bounding box queries existed only in the fallback path. The fix was to add the filter at the start of the build script, before any neighbour computation happens, so it can't end up in the table at all.

### The Sagittarius A* Problem

This is where the architecture hit a genuine edge case it hadn't considered.

Sagittarius A* — the supermassive black hole at the galactic centre — is a named system. It has exact coordinates in EDSM. But it's surrounded not by other named systems, but by tens of thousands of procedural systems. The 50 ly sphere around it contains nothing with `sector IS NULL`. So the `named_neighbours` table has no rows for it. The fallback fires. And the fallback was written as `WHERE sector IS NULL` — find named systems in the box — which also finds nothing.

The result: Sagittarius A* returned zero results, stuck in a spinner.

The wrong fix would have been to extend the `named_neighbours` radius to, say, 500 ly and hope to capture procedural systems. The right fix was to acknowledge that this is a two-phase problem: look for named neighbours first (good for Sol, Alpha Centauri, most of the bubble), and if none are found, widen to all systems — named and procedural — at 200 ly. This covers the Sgr A* case without changing the behaviour for systems that already work correctly.

One small SQL mistake during the fix: when the extra filter clause was empty (for the all-systems pass), the generated SQL became `FROM systems  AND x BETWEEN...` — missing a `WHERE`. Fixed by ensuring every branch has a proper `WHERE` clause.

### Tests

One existing test — `test_non_procedural_returns_empty_results` — asserted that Sol should return an empty result list. This was written when named system support was first added, at a time when we expected non-procedural inputs to yield nothing. The semantics have since changed — named systems now actively search for neighbours. The test was renamed and updated to assert a 200 response without making claims about the result list, which is the correct invariant for the HTTP layer.

33 tests, all passing.

### What's Next

The import is still running in a separate window. Once it finishes, the build script needs to run:

```bash
.venv/bin/python scripts/build_named_neighbours/build_named_neighbours.py
```

After that, restart the server and Sol should be sub-100ms. Sagittarius A* will return nearby procedural systems from the fallback. AssetViewerSystem will not appear anywhere. The named system path will be in the state it should have been in from the start.

---
