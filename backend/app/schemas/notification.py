from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class NotificationOut(BaseModel):
    id: str
    user_id: str
    title: str
    message: str
    notification_type: str
    related_entity: Optional[str] = None
    related_id: Optional[str] = None
    is_read: bool = False
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationCountOut(BaseModel):
    unread_count: int


class NotificationReadAllOut(BaseModel):
    updated_count: int
    unread_count: int
