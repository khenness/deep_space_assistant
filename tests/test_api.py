"""
Integration tests for the HTTP layer. Uses FastAPI's TestClient to make real
HTTP requests against the app without running a server. The DB dependency is
overridden with an in-memory SQLite DB so tests are self-contained.
"""

import sqlite3

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.database import get_db


def make_test_db():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.execute("""
        CREATE TABLE systems (
            name TEXT NOT NULL,
            x REAL, y REAL, z REAL,
            sector TEXT, boxel TEXT, mass_code TEXT
        )
    """)
    conn.executemany("INSERT INTO systems VALUES (?, ?, ?, ?, ?, ?, ?)", [
        ("Zunou GS-B d7562", 1.0, 2.0, 3.0, "Zunou", "GS-B", "d"),
        ("Zunou GS-B d7600", 4.0, 5.0, 6.0, "Zunou", "GS-B", "d"),
        ("Zunou GS-B c100",  10.0, 20.0, 30.0, "Zunou", "GS-B", "c"),
        ("Zunou AA-A d1",    100.0, 200.0, 300.0, "Zunou", "AA-A", "d"),
        ("Sol",              0.0,  0.0,  0.0,  None, None, None),
    ])
    conn.execute("""
        CREATE TABLE named_neighbours (
            system_name  TEXT NOT NULL,
            neighbour    TEXT NOT NULL,
            distance_ly  REAL NOT NULL
        )
    """)
    conn.execute(
        "CREATE INDEX idx_named_neighbours_system ON named_neighbours (system_name COLLATE NOCASE)"
    )
    conn.execute("CREATE INDEX idx_xyz ON systems (x, y, z)")
    conn.commit()
    return conn


@pytest.fixture
def client():
    test_conn = make_test_db()

    def override_get_db():
        yield test_conn

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()
    test_conn.close()


class TestHealthEndpoint:
    def test_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestNearbyEndpoint:
    def test_returns_results(self, client):
        resp = client.get("/nearby", params={"system": "Zunou GS-B d7561"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["input_system"] == "Zunou GS-B d7561"
        assert len(body["results"]) > 0

    def test_result_shape(self, client):
        resp = client.get("/nearby", params={"system": "Zunou GS-B d7561"})
        result = resp.json()["results"][0]
        assert "name" in result
        assert "match_level" in result
        assert "confidence" in result
        assert "typical_range_ly" in result

    def test_respects_results_param(self, client):
        resp = client.get("/nearby", params={"system": "Zunou GS-B d7561", "results": 1})
        assert len(resp.json()["results"]) <= 1

    def test_empty_system_returns_422(self, client):
        resp = client.get("/nearby", params={"system": ""})
        assert resp.status_code == 422

    def test_missing_system_returns_422(self, client):
        resp = client.get("/nearby")
        assert resp.status_code == 422

    def test_non_procedural_returns_200(self, client):
        resp = client.get("/nearby", params={"system": "Sol"})
        assert resp.status_code == 200
