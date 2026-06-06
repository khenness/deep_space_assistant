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
