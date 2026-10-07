import os
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, status, UploadFile
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db
from app.models.item import Item, ItemType, ItemStatus, ItemImage
from app.models.user import User, UserRole
from app.models.location import CampusLocation
from app.models.category import Category
from app.models.audit import AuditLog
from app.models.match import Match
from app.models.claim import Claim
from app.models.notification import Notification
from app.schemas.item import ItemOut, ItemFilter, ItemUpdate
from app.services.auth import get_current_user, get_current_user_optional, require_roles
from app.services.ai_engine import run_matching_engine_for_item, process_and_store_embedding
from app.services.notification import send_match_notification
from app.services.privacy import sanitize_item_out

router = APIRouter(prefix="/items", tags=["Lost & Found Items"])

@router.post("", response_model=ItemOut, status_code=status.HTTP_201_CREATED)
async def report_item(
    report_type: ItemType = Form(...),
    title: str = Form(...),
    description: str = Form(...),
    category_id: str = Form(...),
    location_id: str = Form(...),
    incident_date: str = Form(...),
    confidential_identifiers: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=400, detail="Category not found")
    location = db.query(CampusLocation).filter(CampusLocation.id == location_id).first()
    if not location:
        raise HTTPException(status_code=400, detail="Location not found")

    try:
        inc_date = datetime.fromisoformat(incident_date.replace("Z", "+00:00"))
    except Exception:
        inc_date = datetime.now(timezone.utc)

    item_id = f"itm-{uuid.uuid4().hex[:10]}"
    new_item = Item(
        id=item_id,
        user_id=current_user.id,
        report_type=report_type,
        title=title,
        description=description,
        category_id=category_id,
        location_id=location_id,
        incident_date=inc_date,
        status=ItemStatus.OPEN,
        confidential_identifiers=confidential_identifiers,
        created_at=datetime.now(timezone.utc)
    )
    db.add(new_item)
    db.commit()

    # Handle image upload if provided
    if image and image.filename:
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        file_ext = os.path.splitext(image.filename)[1] or ".jpg"
        img_filename = f"{item_id}_{uuid.uuid4().hex[:6]}{file_ext}"
        saved_img_path = os.path.join(settings.UPLOAD_DIR, img_filename)
        
        contents = await image.read()
        with open(saved_img_path, "wb") as f:
            f.write(contents)

        item_image = ItemImage(
            id=f"img-{uuid.uuid4().hex[:8]}",
            item_id=item_id,
            file_path=saved_img_path,
            is_primary=True,
            uploaded_at=datetime.now(timezone.utc)
        )
        db.add(item_image)
        db.commit()

    db.refresh(new_item)

    # 1. Generate & persist embeddings
    process_and_store_embedding(new_item, db)

    # 2. Run AI matching engine against the opposite item pool
    matches = run_matching_engine_for_item(new_item, db)
    
    # 3. If direct high-confidence match found, trigger alerts
    for m in matches:
        if m.status.value == "SUGGESTED":
            lost_item = m.lost_item
            found_item = m.found_item
            if lost_item and lost_item.user:
                send_match_notification(m, lost_item, found_item, lost_item.user, db=db)

    # Audit log
    audit = AuditLog(
        id=f"aud-{uuid.uuid4().hex[:8]}",
        actor_id=current_user.id,
        action=f"CREATE_{report_type.value}_REPORT",
        target_entity="items",
        target_id=item_id,
        details=f"Title: {title}, Category: {category_id}"
    )
    db.add(audit)
    db.commit()

    db.refresh(new_item)
    return sanitize_item_out(new_item, current_user)

@router.get("", response_model=List[ItemOut])
def list_items(
    report_type: Optional[ItemType] = None,
    category_id: Optional[str] = None,
    campus_name: Optional[str] = None,
    status_filter: Optional[ItemStatus] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    query = db.query(Item)
    if report_type:
        query = query.filter(Item.report_type == report_type)
    if category_id:
        query = query.filter(Item.category_id == category_id)
    if status_filter:
        query = query.filter(Item.status == status_filter)
    if campus_name:
        query = query.join(CampusLocation).filter(CampusLocation.campus_name == campus_name)
    if search:
        search_fmt = f"%{search.strip()}%"
        query = query.filter((Item.title.ilike(search_fmt)) | (Item.description.ilike(search_fmt)))

    items = query.order_by(Item.created_at.desc()).all()
    return [sanitize_item_out(item, current_user) for item in items]

@router.get("/my-reports", response_model=List[ItemOut])
def get_my_reported_items(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    items = db.query(Item).filter(Item.user_id == current_user.id).order_by(Item.created_at.desc()).all()
    return [sanitize_item_out(item, current_user) for item in items]

@router.get("/{item_id}", response_model=ItemOut)
def get_item_by_id(
    item_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return sanitize_item_out(item, current_user)

@router.patch("/{item_id}", response_model=ItemOut)
def update_item(
    item_id: str,
    item_update: ItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    is_owner = item.user_id == current_user.id
    is_staff_or_admin = current_user.role in [UserRole.SECURITY_OFFICER, UserRole.ADMIN]
    if not (is_owner or is_staff_or_admin):
        raise HTTPException(status_code=403, detail="Not allowed to update this item")

    update_fields = item_update.model_dump(exclude_unset=True)
    if "category_id" in update_fields and update_fields["category_id"] is not None:
        category = db.query(Category).filter(Category.id == update_fields["category_id"]).first()
        if not category:
            raise HTTPException(status_code=400, detail="Category not found")
    if "location_id" in update_fields and update_fields["location_id"] is not None:
        location = db.query(CampusLocation).filter(CampusLocation.id == update_fields["location_id"]).first()
        if not location:
            raise HTTPException(status_code=400, detail="Location not found")

    for field, value in update_fields.items():
        setattr(item, field, value)
    item.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)

    if any(field in update_fields for field in ("title", "description", "category_id", "location_id")):
        process_and_store_embedding(item, db)
        run_matching_engine_for_item(item, db)

    audit = AuditLog(
        id=f"aud-{uuid.uuid4().hex[:8]}",
        actor_id=current_user.id,
        action="UPDATE_ITEM",
        target_entity="items",
        target_id=item.id,
        details=f"Updated item fields: {', '.join(sorted(update_fields.keys()))}"
    )
    db.add(audit)
    db.commit()

    return sanitize_item_out(item, current_user)

@router.delete("/{item_id}")
def delete_item(
    item_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    is_owner = item.user_id == current_user.id
    is_staff_or_admin = current_user.role in [UserRole.SECURITY_OFFICER, UserRole.ADMIN]
    if not (is_owner or is_staff_or_admin):
        raise HTTPException(status_code=403, detail="Not allowed to delete this item")

    # 1. Clean up associated Match records
    db.query(Match).filter(
        (Match.lost_item_id == item_id) | (Match.found_item_id == item_id)
    ).delete(synchronize_session=False)

    # 2. Clean up associated Claim records
    db.query(Claim).filter(Claim.lost_item_id == item_id).update(
        {Claim.lost_item_id: None}, synchronize_session=False
    )
    db.query(Claim).filter(Claim.found_item_id == item_id).delete(synchronize_session=False)

    # 3. Clean up associated notifications
    db.query(Notification).filter(Notification.related_id == item_id).delete(synchronize_session=False)

    # 4. Remove physical upload files if present
    for img in item.images:
        if img.file_path and os.path.exists(img.file_path):
            try:
                os.remove(img.file_path)
            except OSError:
                pass

    db.delete(item)
    db.commit()

    audit = AuditLog(
        id=f"aud-{uuid.uuid4().hex[:8]}",
        actor_id=current_user.id,
        action="DELETE_ITEM",
        target_entity="items",
        target_id=item_id,
        details=f"Deleted item '{item.title}'"
    )
    db.add(audit)
    db.commit()

    return {"item_id": item_id, "detail": "Item deleted successfully"}

@router.patch("/{item_id}/status", response_model=ItemOut)
def update_item_status(
    item_id: str,
    new_status: ItemStatus,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SECURITY_OFFICER, UserRole.ADMIN))
):
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    item.status = new_status
    item.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)
    return sanitize_item_out(item, current_user)
