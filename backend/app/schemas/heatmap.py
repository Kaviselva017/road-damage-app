from pydantic import BaseModel


class ClusterPoint(BaseModel):
    lat: float
    lng: float
    count: int
    weight: float
    dominant_damage_type: str
    max_severity: str


class Hotspot(ClusterPoint):
    estimated_repair_cost: float
    complaint_ids: list[str]
