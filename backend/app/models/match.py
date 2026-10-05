import enum
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Enum, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base

class MatchStatus(str, enum.Enum):
    SUGGESTED = "SUGGESTED"            # High confidence auto-match shown to student
    OFFICER_REVIEW = "OFFICER_REVIEW"  # Ambiguous match (0.52 - 0.80) in officer queue
    CONFIRMED = "CONFIRMED"            # Officer or user accepted the match
    DISMISSED = "DISMISSED"            # Officer or user rejected the match

class Match(Base):
    __tablename__ = "matches"

    id = Column(String, primary_key=True, index=True)
    lost_item_id = Column(String, ForeignKey("items.id"), nullable=False)
    found_item_id = Column(String, ForeignKey("items.id"), nullable=False)
    image_score = Column(Float, default=0.0)
    text_score = Column(Float, default=0.0)
    meta_score = Column(Float, default=0.0)
    final_score = Column(Float, nullable=False, index=True)
    status = Column(Enum(MatchStatus), default=MatchStatus.SUGGESTED, nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint('lost_item_id', 'found_item_id', name='uq_lost_found_pair'),
    )

    lost_item = relationship("Item", foreign_keys=[lost_item_id])
    found_item = relationship("Item", foreign_keys=[found_item_id])
