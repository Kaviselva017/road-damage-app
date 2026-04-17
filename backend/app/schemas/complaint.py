from pydantic import BaseModel
from typing import Optional

class ComplaintStatusOut(BaseModel):
    id: int
    status: str
    damage_type: Optional[str] = None
    confidence: Optional[float] = None
