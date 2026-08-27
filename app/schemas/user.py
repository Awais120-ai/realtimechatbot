from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, ConfigDict



class UserBase(BaseModel):
    email: EmailStr
    username: str


class UserCreate(UserBase):
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserUpdate(BaseModel):
    email: EmailStr | None = None
    username: str | None = None
    avatar_url: str | None = None
    profile_picture: str | None = None


class UserChangePassword(BaseModel):
    current_password: str
    new_password: str

class UserRead(UserBase):
    id: int
    avatar_url: str | None = None
    profile_picture: str | None = None
    is_active: bool
    is_online: bool
    last_seen: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

