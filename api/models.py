from pydantic import BaseModel


class NearbySystem(BaseModel):
    name: str
    match_level: str
    search_prefix: str
    confidence: str
    typical_range_ly: str
    sector_density: int | None  # known systems in input's sector+boxel; None for named systems


class NearbyResponse(BaseModel):
    input_system: str
    results: list[NearbySystem]


class DSSACarrier(BaseModel):
    callsign: str
    vessel: str
    operation: str
    region: str
    system_name: str
    distance_ly: float | None
    services: list[str]
    owner: str


class DSSAResponse(BaseModel):
    input_system: str
    reference_system: str | None
    reference_confidence: str | None  # "exact", "high", "medium", "low"
    reference_error_ly: str | None    # human-readable margin e.g. "± 50 ly"
    reference_density: int | None     # known systems in reference's sector+boxel
    results: list[DSSACarrier]
