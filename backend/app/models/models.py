from sqlalchemy import Column, Integer, String, Float, DateTime, Enum, ForeignKey, Text, Boolean, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
from datetime import datetime
import enum

class SeverityLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class ComplaintStatus(str, enum.Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    REJECTED = "rejected"

class DamageType(str, enum.Enum):
    POTHOLE = "pothole"
    CRACK = "crack"
    SURFACE_DAMAGE = "surface_damage"
    MULTIPLE = "multiple"

class AreaType(str, enum.Enum):
    HOSPITAL = "hospital"
    SCHOOL = "school"
    MARKET = "market"
    HIGHWAY = "highway"
    RESIDENTIAL = "residential"
    RURAL = "rural"
    UNKNOWN = "unknown"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, index=True, nullable=False)
    phone = Column(String(20))
    hashed_password = Column(String(255), nullable=False)
    points = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    complaints = relationship("Complaint", back_populates="user")

class FieldOfficer(Base):
    __tablename__ = "field_officers"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, index=True, nullable=False)
    phone = Column(String(20))
    hashed_password = Column(String(255), nullable=False)
    zone = Column(String(100))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    complaints = relationship("Complaint", back_populates="officer")

class Complaint(Base):
    __tablename__ = "complaints"
    id = Column(Integer, primary_key=True, index=True)
    complaint_id = Column(String(20), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    officer_id = Column(Integer, ForeignKey("field_officers.id"), nullable=True)

    # Location
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    address = Column(String(500))
    area_type = Column(String(50), default="unknown")  # hospital, school, market, highway etc
    nearby_places = Column(Text)  # JSON string of nearby POIs

    # AI Detection
    damage_type = Column(Enum(DamageType), nullable=False)
    severity = Column(Enum(SeverityLevel), nullable=False)
    ai_confidence = Column(Float)
    description = Column(Text)

    # Media
    image_url = Column(String(500), nullable=False)
    image_thumbnail_url = Column(String(500))
    image_hash = Column(String(64))  # For duplicate image detection

    # Status
    status = Column(Enum(ComplaintStatus), default=ComplaintStatus.PENDING)
    officer_notes = Column(Text)

    # Priority Algorithm
    priority_score = Column(Float, default=0.0)
    damage_size_score = Column(Float, default=0.0)   # from AI
    traffic_density_score = Column(Float, default=0.0)
    accident_risk_score = Column(Float, default=0.0)
    area_criticality_score = Column(Float, default=0.0)  # hospital=10, school=8
    rainfall_score = Column(Float, default=0.0)
    
    # Environmental
    rainfall_mm = Column(Float, nullable=True)
    traffic_volume = Column(String(50), nullable=True)
    road_age_years = Column(Integer, nullable=True)
    weather_condition = Column(String(100), nullable=True)

    # Fund
    allocated_fund = Column(Float, default=0.0)
    fund_note = Column(Text)
    fund_allocated_at = Column(DateTime, nullable=True)

    # Duplicate detection
    is_duplicate = Column(Boolean, default=False)
    duplicate_of = Column(String(20), nullable=True)
    report_count = Column(Integer, default=1)  # How many users reported same spot

    # Verification
    is_verified = Column(Boolean, default=False)
    fake_report_score = Column(Float, default=0.0)  # 0=genuine, 1=likely fake

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    resolved_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="complaints")
    officer = relationship("FieldOfficer", back_populates="complaints")
    messages = relationship("Message", back_populates="complaint")

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    complaint_id = Column(String(20), ForeignKey("complaints.complaint_id"))
    sender_role = Column(String(20))
    sender_name = Column(String(100))
    message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    complaint = relationship("Complaint", back_populates="messages")

class LoginLog(Base):
    __tablename__ = "login_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True)
    email = Column(String(150))
    role = Column(String(20))
    name = Column(String(100), nullable=True)
    ip_address = Column(String(50))
    logged_in_at = Column(DateTime, default=datetime.utcnow)
    logout_at = Column(DateTime, nullable=True)
    session_duration_mins = Column(Integer, nullable=True)
    status = Column(String(20), default="success")

class ComplaintOfficer(Base):
    __tablename__ = "complaint_officers"
    id = Column(Integer, primary_key=True, index=True)
    complaint_id = Column(String(20), ForeignKey("complaints.complaint_id"))
    officer_id = Column(Integer, ForeignKey("field_officers.id"))
    assigned_at = Column(DateTime, default=datetime.utcnow)
    role = Column(String(50), default="field")

class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    complaint_id = Column(String(20), nullable=True)
    type = Column(String(50))  # submitted, verified, scheduled, completed
    title = Column(String(200))
    message = Column(Text)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
