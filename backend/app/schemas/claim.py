from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.claim import ClaimStatus
from app.schemas.item import ItemOut
from app.schemas.user import UserOut

class ClaimCreate(BaseModel):
    found_item_id: str
    lost_item_id: Optional[str] = None
    proof_description: str
    proof_file_path: Optional[str] = None

class ClaimVerify(BaseModel):
    status: ClaimStatus # APPROVED or REJECTED
    officer_notes: Optional[str] = None

class ClaimOut(BaseModel):
    id: str
    found_item_id: str
    claimant_id: str
    lost_item_id: Optional[str] = None
    proof_description: str
    proof_file_path: Optional[str] = None
    status: ClaimStatus
    verified_by: Optional[str] = None
    officer_notes: Optional[str] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None
    found_item: Optional[ItemOut] = None
    lost_item: Optional[ItemOut] = None
    claimant: Optional[UserOut] = None
    verifier: Optional[UserOut] = None

    model_config = ConfigDict(from_attributes=True)
