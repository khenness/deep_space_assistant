# Developer Diary — Deep Space Assistant

---

## Friday 5th June 2026 — Starting Out

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
