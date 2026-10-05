from sqlalchemy import Column, String, ForeignKey, Text
from app.database import Base

class Category(Base):
    __tablename__ = "categories"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True) # e.g. "Laptops & Computers", "Mobile Phones", "Student IDs & Documents"
    parent_id = Column(String, ForeignKey("categories.id"), nullable=True)
    description = Column(String, nullable=True)
    verification_attributes = Column(Text, default="[]") # JSON list of questions for blind proof e.g. ["brand", "color", "wallpaper/serial"]
