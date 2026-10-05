import enum
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from app.database import Base

class ClaimStatus(str, enum.Enum):
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

class Claim(Base):
    __tablename__ = "claims"

    id = Column(String, primary_key=True, index=True)
    found_item_id = Column(String, ForeignKey("items.id"), nullable=False)
    claimant_id = Column(String, ForeignKey("users.id"), nullable=False)
    lost_item_id = Column(String, ForeignKey("items.id"), nullable=True)
    proof_description = Column(Text, nullable=False)
    proof_file_path = Column(String(500), nullable=True)
    status = Column(Enum(ClaimStatus), default=ClaimStatus.SUBMITTED, nullable=False, index=True)
    verified_by = Column(String, ForeignKey("users.id"), nullable=True)
    officer_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime, nullable=True)

    found_item = relationship("Item", foreign_keys=[found_item_id])
    lost_item = relationship("Item", foreign_keys=[lost_item_id])
    claimant = relationship("User", foreign_keys=[claimant_id])
    verifier = relationship("User", foreign_keys=[verified_by])
