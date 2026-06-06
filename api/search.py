import math
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


def _sector_density(parsed: ParsedName, db: sqlite3.Connection) -> int | None:
    if not parsed.is_procedural:
        return None
    row = db.execute(
        "SELECT COUNT(*) FROM systems WHERE name LIKE ? AND sector IS NOT NULL",
        (f"{parsed.sector} {parsed.boxel} %",),
    ).fetchone()
    return row[0] if row else 0


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


def _find_nearby_named(
    system_name: str,
    db: sqlite3.Connection,
    num_results: int,
) -> list[dict]:
    """Coordinate-based radius search for hand-named systems (Sol, Colonia, etc.)."""
    coords = _get_system_coords(system_name, db)
    if not coords:
        return []

    sx, sy, sz = coords
    radius = 200.0

    # Bounding box narrows via idx_xyz. No LIMIT here — we need all candidates
    # in the box before sorting by distance, otherwise close named systems
    # (e.g. Alpha Centauri) may be excluded in favour of arbitrary distant ones.
    candidates = db.execute(
        "SELECT name, x, y, z FROM systems "
        "WHERE x BETWEEN ? AND ? AND y BETWEEN ? AND ? AND z BETWEEN ? AND ? "
        "AND name != ? COLLATE NOCASE",
        (sx - radius, sx + radius, sy - radius, sy + radius, sz - radius, sz + radius,
         system_name),
    ).fetchall()

    results = []
    for name, cx, cy, cz in candidates:
        dist = math.sqrt((sx - cx) ** 2 + (sy - cy) ** 2 + (sz - cz) ** 2)
        if dist <= radius:
            results.append({
                "name": name,
                "match_level": "coordinate-radius",
                "search_prefix": f"{system_name} ±{radius:.0f}ly",
                "confidence": "exact",
                "typical_range_ly": f"< {dist:.1f} ly",
                "sector_density": None,
                "distance_ly": dist,
            })

    results.sort(key=lambda r: r["distance_ly"])
    for r in results:
        del r["distance_ly"]
    return results[:num_results]


def find_nearby(
    system_name: str,
    db: sqlite3.Connection,
    num_results: int = 5,
) -> list[dict]:
    parsed = parse_system_name(system_name)

    if not parsed.is_procedural:
        return _find_nearby_named(system_name, db, num_results)

    density = _sector_density(parsed, db)
    seen: dict[str, dict] = {}

    for level in _search_levels(parsed):
        if len(seen) >= num_results:
            break

        prefix = level["prefix"]
        rows = db.execute(
            "SELECT name FROM systems WHERE name LIKE ? AND sector IS NOT NULL LIMIT ?",
            (prefix + "%", num_results * 10),
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
                    "sector_density": density,
                }

    return list(seen.values())[:num_results]


def _get_system_coords(system_name: str, db: sqlite3.Connection) -> tuple[float, float, float] | None:
    row = db.execute(
        "SELECT x, y, z FROM systems WHERE name = ? COLLATE NOCASE",
        (system_name.strip(),),
    ).fetchone()
    return row if row else None


def find_nearest_dssa(
    system_name: str,
    db: sqlite3.Connection,
    num_results: int = 5,
) -> dict:
    """
    Find the nearest DSSA carriers to a given system.

    For undiscovered systems (not in our DB), we first find a nearby reference
    system using prefix matching, then compute distances from that reference.
    For known systems, we compute distances directly.

    Returns a dict with reference_system used and sorted carrier results.
    """
    carriers = db.execute(
        "SELECT callsign, vessel, operation, region, system_name, x, y, z, services, owner "
        "FROM dssa_carriers WHERE x IS NOT NULL"
    ).fetchall()

    if not carriers:
        return {"reference_system": None, "results": []}

    # Try to get coords for the input system directly
    coords = _get_system_coords(system_name, db)
    reference_system = system_name

    # If not found (undiscovered system), find a nearby known reference
    reference_confidence = "exact"
    reference_error_ly = None
    reference_density = None
    if not coords:
        nearby = find_nearby(system_name, db, num_results=1)
        if not nearby:
            return {"reference_system": None, "reference_confidence": None, "reference_error_ly": None, "reference_density": None, "results": []}
        best = nearby[0]
        reference_system = best["name"]
        reference_confidence = best["confidence"]
        reference_error_ly = "± " + best["typical_range_ly"]
        reference_density = best["sector_density"]
        coords = _get_system_coords(reference_system, db)

    if not coords:
        return {"reference_system": None, "reference_confidence": None, "reference_error_ly": None, "reference_density": None, "results": []}

    rx, ry, rz = coords

    results = []
    for callsign, vessel, operation, region, system_name_c, cx, cy, cz, services, owner in carriers:
        dist = math.sqrt((rx - cx) ** 2 + (ry - cy) ** 2 + (rz - cz) ** 2)
        results.append({
            "callsign": callsign,
            "vessel": vessel,
            "operation": operation or "",
            "region": region or "",
            "system_name": system_name_c,
            "distance_ly": round(dist, 1),
            "services": [s.strip() for s in services.split(",")] if services else [],
            "owner": owner or "",
        })

    results.sort(key=lambda r: r["distance_ly"])
    is_approximate = reference_system != system_name
    return {
        "reference_system": reference_system if is_approximate else None,
        "reference_confidence": reference_confidence if is_approximate else None,
        "reference_error_ly": reference_error_ly if is_approximate else None,
        "reference_density": reference_density if is_approximate else None,
        "results": results[:num_results],
    }
