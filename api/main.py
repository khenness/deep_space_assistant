import sqlite3
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .database import get_db
from .models import DSSACarrier, DSSAResponse, NearbyResponse, NearbySystem
from .search import find_nearby, find_nearest_dssa

FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"

app = FastAPI(
    title="Deep Space Assistant",
    description="Find known EDSM systems near an undiscovered Elite Dangerous system.",
    version="0.1.0",
)


@app.get("/nearby", response_model=NearbyResponse)
def get_nearby(
    system: str,
    results: int = 5,
    db: sqlite3.Connection = Depends(get_db),
) -> NearbyResponse:
    if not system.strip():
        raise HTTPException(status_code=422, detail="system name cannot be empty")

    matches = find_nearby(system, db, num_results=results)

    return NearbyResponse(
        input_system=system,
        results=[NearbySystem(**m) for m in matches],
    )


@app.get("/dssa/nearest", response_model=DSSAResponse)
def get_nearest_dssa(
    system: str,
    results: int = 5,
    db: sqlite3.Connection = Depends(get_db),
) -> DSSAResponse:
    if not system.strip():
        raise HTTPException(status_code=422, detail="system name cannot be empty")

    data = find_nearest_dssa(system, db, num_results=results)

    if not data["results"]:
        return DSSAResponse(
            input_system=system,
            reference_system=None,
            results=[],
        )

    return DSSAResponse(
        input_system=system,
        reference_system=data["reference_system"],
        results=[DSSACarrier(**r) for r in data["results"]],
    )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def index():
    return FileResponse(FRONTEND_DIR / "index.html")
