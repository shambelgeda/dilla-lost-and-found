from typing import Optional

from pydantic import BaseModel, ConfigDict


class CampusLocationBase(BaseModel):
    campus_name: str
    block_or_facility: str
    floor_or_room: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class CampusLocationCreate(CampusLocationBase):
    pass

class CampusLocationOut(CampusLocationBase):
    id: str

    model_config = ConfigDict(from_attributes=True)

class CategoryBase(BaseModel):
    name: str
    description: Optional[str] = None
    parent_id: Optional[str] = None
    verification_attributes: Optional[str] = "[]"

class CategoryCreate(CategoryBase):
    pass

class CategoryOut(CategoryBase):
    id: str

    model_config = ConfigDict(from_attributes=True)
