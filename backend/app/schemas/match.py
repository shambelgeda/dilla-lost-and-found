from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.match import MatchStatus
from app.schemas.item import ItemOut

class MatchOut(BaseModel):
    id: str
    lost_item_id: str
    found_item_id: str
    image_score: float
    text_score: float
    meta_score: float
    final_score: float
    status: MatchStatus
    created_at: datetime
    lost_item: Optional[ItemOut] = None
    found_item: Optional[ItemOut] = None

    model_config = ConfigDict(from_attributes=True)

class MatchStatusUpdate(BaseModel):
    status: MatchStatus
