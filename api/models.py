from pydantic import BaseModel


class NearbySystem(BaseModel):
    name: str
    match_level: str
    search_prefix: str
    confidence: str
    typical_range_ly: str


class NearbyResponse(BaseModel):
    input_system: str
    results: list[NearbySystem]
