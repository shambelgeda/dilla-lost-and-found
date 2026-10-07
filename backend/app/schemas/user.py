from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr

from app.models.user import UserRole

class UserBase(BaseModel):
    university_id: str
    full_name: str
    email: EmailStr
    phone: Optional[str] = None
    role: UserRole = UserRole.STUDENT
    telegram_chat_id: Optional[str] = None

class UserCreate(UserBase):
    password: str

class UserLogin(BaseModel):
    university_id_or_email: str
    password: str

class UserRoleUpdate(BaseModel):
    role: UserRole

class UserOut(UserBase):
    id: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut

class TokenPayload(BaseModel):
    sub: str
    role: str
