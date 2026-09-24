from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=150)
    password: str = Field(min_length=1)


class RegisterRequest(BaseModel):
    username: str = Field(min_length=1, max_length=150)
    email: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1)
    biography: str = ""


class RefreshRequest(BaseModel):
    refresh: str = Field(min_length=1)


class UserBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str


class TokenPairResponse(BaseModel):
    access: str
    refresh: str
    user: UserBrief
