import re
import sqlite3
from dataclasses import dataclass

PROCEDURAL_RE = re.compile(
    r"^(.+?)\s+([A-Z]{2}-[A-Z])\s+([a-h])(\d+(?:-\d+)?)(.*)$",
    re.IGNORECASE,
)

# Confidence tier definitions derived from bulk analysis of EDSM dataset.
# sector+boxel+masscode: 100% of systems within 50 ly (mean ~2-8 ly)
# sector+boxel: same spatial bucket, wider mass code — typically under 200 ly
# sector: coarse fallback — 400-1400 ly range observed in field measurements
CONFIDENCE_TIERS = {
    "sector+boxel+masscode": ("high",   "< 50 ly"),
    "sector+boxel":          ("medium", "< 200 ly"),
    "sector":                ("low",    "400 – 1400 ly"),
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
    m = PROCEDURAL_RE.match(name.strip())
    if m:
        return ParsedName(
            sector=m.group(1).strip(),
            boxel=m.group(2).upper(),
            mass_code=m.group(3).lower(),
            sequence=m.group(4),
            raw=name,
        )
    return ParsedName(sector="", boxel="", mass_code="", sequence="", raw=name)


def _search_levels(parsed: ParsedName) -> list[dict]:
    levels = []
    seq = parsed.sequence
    while seq:
        seq = seq[:-1]
        levels.append({
            "match_level": "sector+boxel+masscode",
            "prefix": f"{parsed.sector} {parsed.boxel} {parsed.mass_code}{seq}",
        })
    levels.append({
        "match_level": "sector+boxel",
        "prefix": f"{parsed.sector} {parsed.boxel} ",
    })
    levels.append({
        "match_level": "sector",
        "prefix": f"{parsed.sector} ",
    })
    return levels


def find_nearby(
    system_name: str,
    db: sqlite3.Connection,
    num_results: int = 5,
) -> list[dict]:
    parsed = parse_system_name(system_name)
    if not parsed.is_procedural:
        return []

    seen: dict[str, dict] = {}

    for level in _search_levels(parsed):
        if len(seen) >= num_results:
            break

        prefix = level["prefix"]
        rows = db.execute(
            "SELECT name FROM systems WHERE name LIKE ? AND sector IS NOT NULL",
            (prefix + "%",),
        ).fetchall()

        for (name,) in rows:
            if name.lower() == system_name.lower():
                continue
            if name not in seen:
                confidence, typical_range = CONFIDENCE_TIERS.get(
                    level["match_level"], ("unknown", "unknown")
                )
                seen[name] = {
                    "name": name,
                    "match_level": level["match_level"],
                    "search_prefix": prefix,
                    "confidence": confidence,
                    "typical_range_ly": typical_range,
                }

    return list(seen.values())[:num_results]
