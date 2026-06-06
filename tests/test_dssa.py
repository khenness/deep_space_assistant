"""
Tests for DSSA carrier search. Uses in-memory SQLite with seeded systems
and carriers so no data files are required.
"""

import math
import sqlite3

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.database import get_db
from api.search import find_nearest_dssa


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.execute("""
        CREATE TABLE systems (
            name TEXT NOT NULL, x REAL, y REAL, z REAL,
            sector TEXT, boxel TEXT, mass_code TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE dssa_carriers (
            callsign TEXT, vessel TEXT, operation TEXT, region TEXT,
            system_name TEXT, x REAL, y REAL, z REAL,
            services TEXT, status TEXT, owner TEXT
        )
    """)
    conn.executemany("INSERT INTO systems VALUES (?, ?, ?, ?, ?, ?, ?)", [
        ("Colonia",         -9530.5, -910.28, 19808.125, None, None, None),
        ("Zunou GS-B d100",  0.0,     0.0,    0.0,       "Zunou", "GS-B", "d"),
        ("Zunou GS-B d200",  5.0,     5.0,    5.0,       "Zunou", "GS-B", "d"),
    ])
    conn.executemany(
        "INSERT INTO dssa_carriers VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("ABC-123", "DSSA Near One",   "Op Near",   "Core",    "Colonia",         -9530.5, -910.28, 19808.125, "Repair, Refuel", "Carrier Operational", "Pilot1"),
            ("DEF-456", "DSSA Far One",    "Op Far",    "Rim",     "Zunou GS-B d100",  0.0,     0.0,    0.0,       "Repair",         "Carrier Operational", "Pilot2"),
            ("GHI-789", "DSSA No Coords",  "Op None",   "Unknown", "Unknown System",   None,    None,   None,      "Repair",         "Carrier Operational", "Pilot3"),
        ]
    )
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def client(db):
    def override_get_db():
        yield db
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestFindNearestDSSA:
    def test_known_system_returns_sorted_by_distance(self, db):
        results = find_nearest_dssa("Colonia", db)
        assert results["results"][0]["callsign"] == "ABC-123"

    def test_excludes_carriers_without_coordinates(self, db):
        results = find_nearest_dssa("Colonia", db)
        names = [r["vessel"] for r in results["results"]]
        assert "DSSA No Coords" not in names

    def test_distance_is_correct(self, db):
        results = find_nearest_dssa("Zunou GS-B d100", db)
        near = next(r for r in results["results"] if r["callsign"] == "DEF-456")
        assert near["distance_ly"] == 0.0

    def test_services_returned_as_list(self, db):
        results = find_nearest_dssa("Colonia", db)
        assert isinstance(results["results"][0]["services"], list)

    def test_undiscovered_system_uses_reference(self, db):
        results = find_nearest_dssa("Zunou GS-B d999", db)
        assert results["reference_system"] is not None
        assert results["reference_confidence"] in ("high", "medium", "low")
        assert results["reference_error_ly"] is not None

    def test_known_system_has_no_reference(self, db):
        results = find_nearest_dssa("Colonia", db)
        assert results["reference_system"] is None
        assert results["reference_confidence"] is None
        assert results["reference_error_ly"] is None

    def test_unknown_system_no_nearby_returns_empty(self, db):
        results = find_nearest_dssa("Completely Unknown Sector AA-B c1-0", db)
        assert results["results"] == []

    def test_respects_num_results(self, db):
        results = find_nearest_dssa("Colonia", db, num_results=1)
        assert len(results["results"]) <= 1


class TestDSSAEndpoint:
    def test_returns_200(self, client):
        resp = client.get("/dssa/nearest", params={"system": "Colonia"})
        assert resp.status_code == 200

    def test_response_shape(self, client):
        resp = client.get("/dssa/nearest", params={"system": "Colonia"})
        body = resp.json()
        assert "input_system" in body
        assert "results" in body
        result = body["results"][0]
        assert "callsign" in result
        assert "vessel" in result
        assert "distance_ly" in result
        assert "services" in result

    def test_empty_system_returns_422(self, client):
        resp = client.get("/dssa/nearest", params={"system": ""})
        assert resp.status_code == 422
