from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.match import Match, MatchStatus
from app.models.item import Item
from app.models.user import User, UserRole
from app.schemas.match import MatchOut, MatchStatusUpdate
from app.services.auth import get_current_user, require_roles
from app.services.ai_engine import run_matching_engine_for_item
from app.services.privacy import sanitize_match_out

router = APIRouter(prefix="/matches", tags=["AI Matches"])

@router.get("/my-matches", response_model=List[MatchOut])
def get_my_item_matches(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Fetch potential matches for the currently authenticated user's lost items."""
    user_item_ids = [i.id for i in db.query(Item.id).filter(Item.user_id == current_user.id).all()]
    matches = db.query(Match).filter(
        (Match.lost_item_id.in_(user_item_ids)) | (Match.found_item_id.in_(user_item_ids)),
        Match.status.in_([MatchStatus.SUGGESTED, MatchStatus.CONFIRMED, MatchStatus.OFFICER_REVIEW])
    ).order_by(Match.final_score.desc()).all()
    return [sanitize_match_out(m, current_user) for m in matches]

@router.get("/review-queue", response_model=List[MatchOut])
def get_officer_review_queue(
    status_filter: Optional[MatchStatus] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SECURITY_OFFICER, UserRole.ADMIN))
):
    """Retrieve items requiring manual review or all active AI suggestions for officers."""
    query = db.query(Match)
    if status_filter:
        query = query.filter(Match.status == status_filter)
    else:
        query = query.filter(Match.status.in_([MatchStatus.OFFICER_REVIEW, MatchStatus.SUGGESTED]))
    
    matches = query.order_by(Match.final_score.desc()).all()
    return [sanitize_match_out(m, current_user) for m in matches]

@router.get("/{match_id}", response_model=MatchOut)
def get_match_detail(
    match_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match record not found")

    is_lost_owner = match.lost_item and match.lost_item.user_id == current_user.id
    is_found_owner = match.found_item and match.found_item.user_id == current_user.id
    is_officer = current_user.role in [UserRole.SECURITY_OFFICER, UserRole.ADMIN]
    if not (is_lost_owner or is_found_owner or is_officer):
        raise HTTPException(status_code=403, detail="Unauthorized to view this match")

    return sanitize_match_out(match, current_user)

@router.patch("/{match_id}/status", response_model=MatchOut)
def update_match_status(
    match_id: str,
    status_update: MatchStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    
    # Verify authorization
    is_lost_owner = match.lost_item and match.lost_item.user_id == current_user.id
    is_found_owner = match.found_item and match.found_item.user_id == current_user.id
    is_officer = current_user.role in [UserRole.SECURITY_OFFICER, UserRole.ADMIN]
    if not (is_lost_owner or is_found_owner or is_officer):
        raise HTTPException(status_code=403, detail="Unauthorized to change match status")

    match.status = status_update.status
    db.commit()
    db.refresh(match)
    return sanitize_match_out(match, current_user)

@router.post("/trigger/{item_id}", response_model=List[MatchOut])
def trigger_ai_matching(
    item_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Manually re-run the multimodal AI similarity pipeline for a specific item."""
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    is_owner = item.user_id == current_user.id
    is_officer = current_user.role in [UserRole.SECURITY_OFFICER, UserRole.ADMIN]
    if not (is_owner or is_officer):
        raise HTTPException(status_code=403, detail="Unauthorized to trigger matching for this item")

    matches = run_matching_engine_for_item(item, db)
    return [sanitize_match_out(m, current_user) for m in matches]
