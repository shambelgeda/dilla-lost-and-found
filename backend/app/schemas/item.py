from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from app.models.item import ItemStatus, ItemType
from app.schemas.location import CampusLocationOut, CategoryOut
from app.schemas.user import UserOut

class ItemImageOut(BaseModel):
    id: str
    file_path: str
    is_primary: bool

    model_config = ConfigDict(from_attributes=True)

class ItemCreate(BaseModel):
    report_type: ItemType
    title: str
    description: str
    category_id: str
    location_id: str
    incident_date: datetime
    confidential_identifiers: Optional[str] = None # Secret verification info

class ItemUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category_id: Optional[str] = None
    location_id: Optional[str] = None
    status: Optional[ItemStatus] = None
    confidential_identifiers: Optional[str] = None

class ItemOut(BaseModel):
    id: str
    user_id: str
    report_type: ItemType
    title: str
    description: str
    category_id: str
    location_id: str
    incident_date: datetime
    status: ItemStatus
    confidential_identifiers: Optional[str] = None  # Strip if caller is unauthorized student
    created_at: datetime
    updated_at: datetime
    category: Optional[CategoryOut] = None
    location: Optional[CampusLocationOut] = None
    user: Optional[UserOut] = None
    images: List[ItemImageOut] = []

    model_config = ConfigDict(from_attributes=True)

class ItemFilter(BaseModel):
    report_type: Optional[ItemType] = None
    category_id: Optional[str] = None
    campus_name: Optional[str] = None
    status: Optional[ItemStatus] = None
    search_query: Optional[str] = None
