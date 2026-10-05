import enum
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime, Enum
from app.database import Base

class UserRole(str, enum.Enum):
    STUDENT = "STUDENT"
    STAFF = "STAFF"
    SECURITY_OFFICER = "SECURITY_OFFICER"
    ADMIN = "ADMIN"

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True) # UUID string
    university_id = Column(String, unique=True, index=True, nullable=False) # e.g. "DU/R/1042/14"
    full_name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    phone = Column(String, nullable=True)
    role = Column(Enum(UserRole), default=UserRole.STUDENT, nullable=False)
    telegram_chat_id = Column(String, nullable=True)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
