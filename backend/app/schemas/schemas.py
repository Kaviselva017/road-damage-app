from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
from app.models.models import SeverityLevel, ComplaintStatus, DamageType

# --- Auth ---
class UserCreate(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str]
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserOut(BaseModel):
    id: int
    name: str
    email: str
    phone: Optional[str]
    points: int
    created_at: datetime
    class Config:
        from_attributes = True

# --- Complaints ---
class ComplaintCreate(BaseModel):
    latitude: float
    longitude: float
    address: Optional[str]

class AIDetectionResult(BaseModel):
    damage_type: DamageType
    severity: SeverityLevel
    confidence: float
    description: str

class ComplaintOut(BaseModel):
    id: int
    complaint_id: str
    latitude: float
    longitude: float
    address: Optional[str]
    damage_type: DamageType
    severity: SeverityLevel
    ai_confidence: Optional[float]
    description: Optional[str]
    image_url: str
    status: ComplaintStatus
    officer_notes: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    resolved_at: Optional[datetime]
    class Config:
        from_attributes = True

class ComplaintStatusUpdate(BaseModel):
    status: ComplaintStatus
    officer_notes: Optional[str]

class ComplaintAssign(BaseModel):
    officer_id: int

# --- Officer ---
class OfficerCreate(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str]
    password: str
    zone: Optional[str]

class OfficerOut(BaseModel):
    id: int
    name: str
    email: str
    phone: Optional[str]
    zone: Optional[str]
    is_active: int
    class Config:
        from_attributes = True

class MessageCreate(BaseModel):
    message: str

class MessageOut(BaseModel):
    id: int
    complaint_id: str
    sender_role: str
    sender_name: str
    message: str
    created_at: datetime

    class Config:
        from_attributes = True