from __future__ import annotations

from pydantic import BaseModel, EmailStr


class UserRegister(BaseModel):
    name: str
    email: EmailStr
    phone: str | None = None
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class OfficerLogin(BaseModel):
    email: EmailStr
    password: str


class OfficerRegister(BaseModel):
    name: str
    email: EmailStr
    phone: str | None = None
    password: str
    zone: str | None = None


class OfficerUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    zone: str | None = None
    password: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    name: str | None = None


class StatusUpdate(BaseModel):
    status: str
    officer_notes: str | None = None


class FundUpdate(BaseModel):
    amount: float
    note: str | None = None


class ReassignUpdate(BaseModel):
    officer_id: int


class MessageSend(BaseModel):
    message: str


class OfficerDirectoryOut(BaseModel):
    id: int
    name: str
    zone: str | None = None

    class Config:
        from_attributes = True
