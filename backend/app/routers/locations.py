import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.location import CampusLocation
from app.models.category import Category
from app.models.user import UserRole
from app.schemas.location import CampusLocationOut, CampusLocationCreate, CategoryOut, CategoryCreate
from app.services.auth import require_roles

router = APIRouter(prefix="", tags=["Campuses & Categories"])


@router.get("/locations", response_model=List[CampusLocationOut])
def get_campus_locations(db: Session = Depends(get_db)):
    return db.query(CampusLocation).all()


@router.get("/locations/{location_id}", response_model=CampusLocationOut)
def get_campus_location_by_id(location_id: str, db: Session = Depends(get_db)):
    location = db.query(CampusLocation).filter(CampusLocation.id == location_id).first()
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")
    return location


@router.post("/locations", response_model=CampusLocationOut, status_code=status.HTTP_201_CREATED)
def create_campus_location(
    loc_in: CampusLocationCreate,
    db: Session = Depends(get_db),
    _ = Depends(require_roles(UserRole.ADMIN, UserRole.SECURITY_OFFICER))
):
    campus_name = (loc_in.campus_name or "").strip()
    block_or_facility = (loc_in.block_or_facility or "").strip()

    existing = db.query(CampusLocation).filter(
        CampusLocation.campus_name == campus_name,
        CampusLocation.block_or_facility == block_or_facility,
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A campus location with the same campus and facility already exists",
        )

    new_loc = CampusLocation(
        id=f"loc-{uuid.uuid4().hex[:8]}",
        campus_name=campus_name,
        block_or_facility=block_or_facility,
        floor_or_room=loc_in.floor_or_room,
        latitude=loc_in.latitude,
        longitude=loc_in.longitude,
    )
    db.add(new_loc)
    db.commit()
    db.refresh(new_loc)
    return new_loc


@router.patch("/locations/{location_id}", response_model=CampusLocationOut)
def update_campus_location(
    location_id: str,
    loc_in: CampusLocationCreate,
    db: Session = Depends(get_db),
    _ = Depends(require_roles(UserRole.ADMIN, UserRole.SECURITY_OFFICER)),
):
    location = db.query(CampusLocation).filter(CampusLocation.id == location_id).first()
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")

    location.campus_name = (loc_in.campus_name or "").strip()
    location.block_or_facility = (loc_in.block_or_facility or "").strip()
    location.floor_or_room = loc_in.floor_or_room
    location.latitude = loc_in.latitude
    location.longitude = loc_in.longitude
    db.commit()
    db.refresh(location)
    return location


@router.get("/categories", response_model=List[CategoryOut])
def get_categories(db: Session = Depends(get_db)):
    return db.query(Category).all()


@router.get("/categories/{category_id}", response_model=CategoryOut)
def get_category_by_id(category_id: str, db: Session = Depends(get_db)):
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    return category


@router.post("/categories", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
def create_category(
    cat_in: CategoryCreate,
    db: Session = Depends(get_db),
    _ = Depends(require_roles(UserRole.ADMIN))
):
    name = (cat_in.name or "").strip()
    existing = db.query(Category).filter(Category.name == name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Category '{name}' already exists",
        )

    new_cat = Category(
        id=f"cat-{uuid.uuid4().hex[:8]}",
        name=name,
        description=cat_in.description,
        parent_id=cat_in.parent_id,
        verification_attributes=cat_in.verification_attributes or "[]",
    )
    db.add(new_cat)
    db.commit()
    db.refresh(new_cat)
    return new_cat


@router.patch("/categories/{category_id}", response_model=CategoryOut)
def update_category(
    category_id: str,
    cat_in: CategoryCreate,
    db: Session = Depends(get_db),
    _ = Depends(require_roles(UserRole.ADMIN)),
):
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")

    new_name = (cat_in.name or "").strip()
    if new_name and new_name != category.name:
        duplicate = db.query(Category).filter(Category.name == new_name).first()
        if duplicate and duplicate.id != category.id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Category '{new_name}' already exists")

    category.name = new_name
    category.description = cat_in.description
    category.parent_id = cat_in.parent_id
    category.verification_attributes = cat_in.verification_attributes or "[]"
    db.commit()
    db.refresh(category)
    return category
