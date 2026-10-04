"""Pydantic request/response schemas."""

import re
from typing import Optional, Literal
from regions import SUPPORTED_STATES
from pydantic import BaseModel, EmailStr, Field, field_validator


def validate_password_strength(pw: str) -> str:
    """Same rules the signup form checks client-side (see js/common.js)."""
    if len(pw) < 8:
        raise ValueError("Password must be at least 8 characters")
    if len(pw.encode("utf-8")) > 72:
        raise ValueError("Password is too long (72 bytes max)")
    if not re.search(r"[A-Za-z]", pw) or not re.search(r"\d", pw):
        raise ValueError("Password must include at least one letter and one number")
    return pw
class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)

class ChatResponse(BaseModel):
    response: str

class SignupRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email")
    @classmethod
    def lowercase_email(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("password")
    @classmethod
    def check_password(cls, v: str) -> str:
        return validate_password_strength(v)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)

    @field_validator("email")
    @classmethod
    def lowercase_email(cls, v: str) -> str:
        return v.strip().lower()


class AuthResponse(BaseModel):
    token: str
    profile_complete: bool


class ProfileUpdate(BaseModel):
    description: Optional[str] = None
    target_audience: Optional[str] = None
    products: Optional[str] = None
    business_name: Optional[str] = None
    industry: Optional[str] = None
    tone: Optional[str] = None
    states: Optional[list[str]] = None
    past_taglines: Optional[list[str]] = None


    @field_validator("states")
    @classmethod
    def check_states(cls, value):
        return validate_states(value)


class ProfileResponse(BaseModel):
    description: Optional[str] = None
    target_audience: Optional[str] = None
    products: Optional[str] = None
    email: str
    business_name: Optional[str] = None
    industry: Optional[str] = None
    tone: Optional[str] = None
    states: list[str] = []
    past_taglines: list[str] = []
    profile_complete: bool = False


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)
    content_type: Literal["caption", "notification", "meme", "email", "newsletter"] = "caption"
    states: Optional[list[str]] = None  # defaults to profile states if omitted


    @field_validator("states")
    @classmethod
    def check_states(cls, value):
        return validate_states(value)


class TaglineCandidate(BaseModel):
    state: str
    text: str
    grounding_context: dict


class GenerateResponse(BaseModel):
    results: list[TaglineCandidate]
    note: str


class FeedbackRequest(BaseModel):
    state: str
    tagline_text: str
    thumbs: str  # "up" | "down"


class EmailDraftRequest(BaseModel):
    selected_taglines: dict[str, str]  # {state: tagline_text}


class EmailDraftResponse(BaseModel):
    subject: str
    body: str
    note: str


class EmailSendRequest(BaseModel):
    subject: str
    body: str
    approved: bool


def validate_states(value):
    if value is not None:
        if any(state not in SUPPORTED_STATES for state in value):
            raise ValueError("Unsupported state selected")
        return list(dict.fromkeys(value))
    return value
