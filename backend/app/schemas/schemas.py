from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, EmailStr


class UserRegister(BaseModel):
    name:     str
    email:    EmailStr
    phone:    Optional[str] = None
    password: str


class UserLogin(BaseModel):
    email:    EmailStr
    password: str


class OfficerLogin(BaseModel):
    email:    EmailStr
    password: str


class OfficerRegister(BaseModel):
    name:     str
    email:    EmailStr
    phone:    Optional[str] = None
    password: str
    zone:     Optional[str] = None


class OfficerUpdate(BaseModel):
    name:     Optional[str] = None
    phone:    Optional[str] = None
    zone:     Optional[str] = None
    password: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    name:         Optional[str] = None


class StatusUpdate(BaseModel):
    status:        str
    officer_notes: Optional[str] = None


class FundUpdate(BaseModel):
    amount: float
    note:   Optional[str] = None


class ReassignUpdate(BaseModel):
    officer_id: int


class MessageSend(BaseModel):
    message: str


class OfficerDirectoryOut(BaseModel):
    id:    int
    name:  str
    zone:  Optional[str] = None

    class Config:
        from_attributes = True