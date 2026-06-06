"""
Unit tests for the search logic. No HTTP involved — calls search.py directly
against a small in-memory SQLite DB seeded with known data.
"""

import sqlite3

import pytest

from api.search import find_nearby, parse_system_name


@pytest.fixture
def db():
    """In-memory SQLite DB with a handful of systems for testing."""
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE systems (
            name TEXT NOT NULL,
            x REAL, y REAL, z REAL,
            sector TEXT, boxel TEXT, mass_code TEXT
        )
    """)
    conn.executemany("INSERT INTO systems VALUES (?, ?, ?, ?, ?, ?, ?)", [
        # Same sector+boxel+masscode as query target
        ("Zunou GS-B d7562", 1.0, 2.0, 3.0, "Zunou", "GS-B", "d"),
        ("Zunou GS-B d7600", 4.0, 5.0, 6.0, "Zunou", "GS-B", "d"),
        # Same sector+boxel, different mass code
        ("Zunou GS-B c100",  10.0, 20.0, 30.0, "Zunou", "GS-B", "c"),
        # Same sector only
        ("Zunou AA-A d1",    100.0, 200.0, 300.0, "Zunou", "AA-A", "d"),
        # Different sector entirely — should never appear in results
        ("Colonia AA-A d1",  999.0, 999.0, 999.0, "Colonia", "AA-A", "d"),
        # Unparsed named system — should never appear in results
        ("Sol",              0.0, 0.0, 0.0, None, None, None),
    ])
    conn.commit()
    yield conn
    conn.close()


class TestParseSystemName:
    def test_standard_procedural(self):
        p = parse_system_name("Zunou GS-B d7561")
        assert p.sector == "Zunou"
        assert p.boxel == "GS-B"
        assert p.mass_code == "d"
        assert p.sequence == "7561"
        assert p.is_procedural

    def test_hyphenated_sequence(self):
        p = parse_system_name("Juenae SL-K d9-3226")
        assert p.sequence == "9-3226"
        assert p.is_procedural

    def test_multi_word_sector(self):
        p = parse_system_name("Eol Prou KR-W d100")
        assert p.sector == "Eol Prou"
        assert p.boxel == "KR-W"
        assert p.is_procedural

    def test_named_system(self):
        p = parse_system_name("Sol")
        assert not p.is_procedural

    def test_case_insensitive(self):
        p = parse_system_name("zunou gs-b D7561")
        assert p.is_procedural
        assert p.boxel == "GS-B"
        assert p.mass_code == "d"


class TestFindNearby:
    def test_returns_same_sector_boxel_masscode_first(self, db):
        results = find_nearby("Zunou GS-B d7561", db, num_results=5)
        assert results[0]["match_level"] == "sector+boxel+masscode"

    def test_excludes_query_system_itself(self, db):
        results = find_nearby("Zunou GS-B d7562", db, num_results=5)
        assert all(r["name"] != "Zunou GS-B d7562" for r in results)

    def test_excludes_different_sector(self, db):
        results = find_nearby("Zunou GS-B d7561", db, num_results=5)
        assert all("Colonia" not in r["name"] for r in results)

    def test_procedural_excludes_named_systems(self, db):
        results = find_nearby("Zunou GS-B d7561", db, num_results=5)
        assert all(r["name"] != "Sol" for r in results)

    def test_respects_num_results(self, db):
        results = find_nearby("Zunou GS-B d7561", db, num_results=2)
        assert len(results) <= 2

    def test_named_system_returns_coordinate_results(self, db):
        results = find_nearby("Sol", db, num_results=5)
        assert len(results) > 0
        assert all(r["match_level"] == "coordinate-radius" for r in results)
        assert all(r["confidence"] == "exact" for r in results)

    def test_named_system_excludes_self(self, db):
        results = find_nearby("Sol", db, num_results=5)
        assert all(r["name"] != "Sol" for r in results)

    def test_named_system_not_in_db_returns_empty(self, db):
        results = find_nearby("Sagittarius A*", db)
        assert results == []

    def test_named_system_only_returns_within_radius(self, db):
        # Sol is at 0,0,0. Colonia AA-A d1 is at 999,999,999 — way outside 200ly
        results = find_nearby("Sol", db, num_results=10)
        assert all(r["name"] != "Colonia AA-A d1" for r in results)

    def test_confidence_tiers_present(self, db):
        results = find_nearby("Zunou GS-B d7561", db, num_results=5)
        for r in results:
            assert r["confidence"] in ("high", "medium", "low")
            assert r["typical_range_ly"]
