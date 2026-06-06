import sqlite3

from fastapi import Depends, FastAPI, HTTPException

from .database import get_db
from .models import NearbyResponse, NearbySystem
from .search import find_nearby

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


@app.get("/health")
def health():
    return {"status": "ok"}
