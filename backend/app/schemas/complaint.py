from pydantic import BaseModel


class ComplaintStatusOut(BaseModel):
    id: int
    status: str
    damage_type: str | None = None
    confidence: float | None = None
