import enum
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Boolean, Enum
from sqlalchemy.orm import relationship
from app.database import Base

class ItemType(str, enum.Enum):
    LOST = "LOST"
    FOUND = "FOUND"

class ItemStatus(str, enum.Enum):
    OPEN = "OPEN"
    CLAIM_PENDING = "CLAIM_PENDING"
    RESOLVED = "RESOLVED"
    DISCARDED = "DISCARDED"

class Item(Base):
    __tablename__ = "items"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    report_type = Column(Enum(ItemType), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    category_id = Column(String, ForeignKey("categories.id"), nullable=False)
    location_id = Column(String, ForeignKey("campus_locations.id"), nullable=False)
    incident_date = Column(DateTime, nullable=False)
    status = Column(Enum(ItemStatus), default=ItemStatus.OPEN, nullable=False, index=True)
    confidential_identifiers = Column(Text, nullable=True) # Serial number, distinctive scratch, wallpaper, password hint
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    category = relationship("Category", foreign_keys=[category_id])
    location = relationship("CampusLocation", foreign_keys=[location_id])
    images = relationship("ItemImage", back_populates="item", cascade="all, delete-orphan")
    embedding = relationship("ItemEmbedding", back_populates="item", uselist=False, cascade="all, delete-orphan")

class ItemImage(Base):
    __tablename__ = "item_images"

    id = Column(String, primary_key=True, index=True)
    item_id = Column(String, ForeignKey("items.id"), nullable=False)
    file_path = Column(String(500), nullable=False)
    is_primary = Column(Boolean, default=False)
    uploaded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    item = relationship("Item", back_populates="images")

class ItemEmbedding(Base):
    __tablename__ = "item_embeddings"

    id = Column(String, primary_key=True, index=True)
    item_id = Column(String, ForeignKey("items.id"), unique=True, nullable=False)
    image_vector_json = Column(Text, nullable=True) # JSON float array of 512 dimensions
    text_vector_json = Column(Text, nullable=False)  # JSON float array of 512 dimensions
    model_version = Column(String(100), default="multilingual-sim-v1")
    generated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    item = relationship("Item", back_populates="embedding")
