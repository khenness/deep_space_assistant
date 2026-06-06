import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "edsm.db"


def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
    try:
        yield conn
    finally:
        conn.close()
