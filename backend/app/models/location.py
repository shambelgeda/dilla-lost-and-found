from sqlalchemy import Column, String, Float
from app.database import Base

class CampusLocation(Base):
    __tablename__ = "campus_locations"

    id = Column(String, primary_key=True, index=True) # UUID
    campus_name = Column(String, nullable=False) # e.g. "Main Campus", "Odayaa Campus (Tech)", "Health Science"
    block_or_facility = Column(String, nullable=False) # e.g. "Central Library", "Block 42 IoT", "Student Cafeteria"
    floor_or_room = Column(String, nullable=True) # e.g. "Ground Floor Lab 2", "Reading Hall 1"
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
