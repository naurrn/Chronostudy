from pydantic import BaseModel, EmailStr, Field
from typing import Optional


class RegisterRequest(BaseModel):
    nama: str = Field(..., min_length=2)
    email: EmailStr
    password: str = Field(..., min_length=6)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class MEQAnswer(BaseModel):
    kode: str
    jawaban_index: int


class MEQSubmit(BaseModel):
    jawaban: list[MEQAnswer]


class MataKuliah(BaseModel):
    nama: str
    bloom: int = Field(..., ge=1, le=6)
    sesi: int = Field(..., ge=1, le=5)


class JadwalRequest(BaseModel):
    hari: list[str]
    jam_ranges: list[str]
    matkul: list[MataKuliah]


class ChatMessage(BaseModel):
    message: str


class AdminLogin(BaseModel):
    password: str
