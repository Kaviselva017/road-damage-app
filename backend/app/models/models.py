"""
RoadWatch Models — uses plain String for status/severity/damage_type
so SQLite works without enum migration issues.
"""
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from app.database import Base
from app.utils.datetime_utils import utc_now


class User(Base):
    __tablename__ = "users"
    id              = Column(Integer, primary_key=True, index=True)
    name            = Column(String, nullable=False)
    email           = Column(String, unique=True, index=True, nullable=False)
    phone           = Column(String, nullable=True)
    hashed_password = Column(String, nullable=False)
    is_active       = Column(Boolean, default=True)
    reward_points   = Column(Integer, default=0)
    created_at      = Column(DateTime, default=utc_now)

    complaints    = relationship("Complaint", back_populates="user")
    notifications = relationship("Notification", back_populates="user")


class FieldOfficer(Base):
    __tablename__ = "field_officers"
    id              = Column(Integer, primary_key=True, index=True)
    name            = Column(String, nullable=False)
    email           = Column(String, unique=True, index=True, nullable=False)
    phone           = Column(String, nullable=True)
    hashed_password = Column(String, nullable=False)
    zone            = Column(String, nullable=True)
    is_admin        = Column(Boolean, default=False)
    is_active       = Column(Boolean, default=True)
    last_login      = Column(DateTime, nullable=True)
    created_at      = Column(DateTime, default=utc_now)

    complaints        = relationship("Complaint", back_populates="officer")
    complaint_officers = relationship("ComplaintOfficer", back_populates="officer")


class Complaint(Base):
    __tablename__ = "complaints"
    id           = Column(Integer, primary_key=True, index=True)
    complaint_id = Column(String, unique=True, index=True, nullable=False)
    user_id      = Column(Integer, ForeignKey("users.id"), nullable=True)
    officer_id   = Column(Integer, ForeignKey("field_officers.id"), nullable=True)

    latitude  = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    address   = Column(Text, nullable=True)
    area_type = Column(String, default="residential")

    damage_type   = Column(String, default="pothole")   # pothole|crack|surface_damage|multiple
    severity      = Column(String, default="medium")    # high|medium|low
    ai_confidence = Column(Float, default=0.0)
    description   = Column(Text, nullable=True)
    image_url     = Column(String, nullable=True)
    after_image_url = Column(String, nullable=True)

    status        = Column(String, default="pending")   # pending|assigned|in_progress|completed|rejected
    officer_notes = Column(Text, nullable=True)

    priority_score    = Column(Float, default=0.0)
    allocated_fund    = Column(Float, default=0.0)
    fund_note         = Column(Text, nullable=True)
    fund_allocated_at = Column(DateTime, nullable=True)

    image_hash  = Column(String, nullable=True)
    is_duplicate = Column(Boolean, default=False)
    duplicate_of = Column(String, nullable=True)
    report_count = Column(Integer, default=1)

    created_at  = Column(DateTime, default=utc_now)
    resolved_at = Column(DateTime, nullable=True)

    user    = relationship("User", back_populates="complaints")
    officer = relationship("FieldOfficer", back_populates="complaints")
    notifications    = relationship("Notification", back_populates="complaint_ref")
    messages         = relationship("Message", back_populates="complaint_ref")
    complaint_officers = relationship("ComplaintOfficer", back_populates="complaint")


class ComplaintOfficer(Base):
    __tablename__ = "complaint_officers"
    id           = Column(Integer, primary_key=True, index=True)
    complaint_id = Column(String, ForeignKey("complaints.complaint_id"))
    officer_id   = Column(Integer, ForeignKey("field_officers.id"))
    assigned_at  = Column(DateTime, default=utc_now)

    complaint = relationship("Complaint", back_populates="complaint_officers")
    officer   = relationship("FieldOfficer", back_populates="complaint_officers")


class Notification(Base):
    __tablename__ = "notifications"
    id           = Column(Integer, primary_key=True, index=True)
    user_id      = Column(Integer, ForeignKey("users.id"), nullable=False)
    complaint_id = Column(String, ForeignKey("complaints.complaint_id"), nullable=True)
    message      = Column(Text, nullable=False)
    type         = Column(String, default="info")
    is_read      = Column(Boolean, default=False)
    created_at   = Column(DateTime, default=utc_now)

    user          = relationship("User", back_populates="notifications")
    complaint_ref = relationship("Complaint", back_populates="notifications")


class Message(Base):
    __tablename__ = "messages"
    id           = Column(Integer, primary_key=True, index=True)
    complaint_id = Column(String, ForeignKey("complaints.complaint_id"), nullable=False)
    sender_id    = Column(Integer, nullable=False)
    sender_role  = Column(String, nullable=False)
    message      = Column(Text, nullable=False)
    created_at   = Column(DateTime, default=utc_now)

    complaint_ref = relationship("Complaint", back_populates="messages")


class LoginLog(Base):
    __tablename__ = "login_logs"
    id             = Column(Integer, primary_key=True, index=True)
    email          = Column(String, nullable=False)
    role           = Column(String, nullable=False)
    ip_address     = Column(String, nullable=True)
    logged_in_at   = Column(DateTime, default=utc_now)
    logged_out_at  = Column(DateTime, nullable=True)
    session_minutes = Column(Integer, nullable=True)