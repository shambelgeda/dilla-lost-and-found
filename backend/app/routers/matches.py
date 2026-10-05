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
    return matches

@router.get("/review-queue", response_model=List[MatchOut])
def get_officer_review_queue(
    status_filter: Optional[MatchStatus] = None,
    db: Session = Depends(get_db),
    _ = Depends(require_roles(UserRole.SECURITY_OFFICER, UserRole.ADMIN))
):
    """Retrieve items requiring manual review or all active AI suggestions for officers."""
    query = db.query(Match)
    if status_filter:
        query = query.filter(Match.status == status_filter)
    else:
        query = query.filter(Match.status.in_([MatchStatus.OFFICER_REVIEW, MatchStatus.SUGGESTED]))
    
    return query.order_by(Match.final_score.desc()).all()

@router.get("/{match_id}", response_model=MatchOut)
def get_match_detail(
    match_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match record not found")
    return match

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
    is_owner = match.lost_item.user_id == current_user.id
    is_officer = current_user.role in [UserRole.SECURITY_OFFICER, UserRole.ADMIN]
    if not (is_owner or is_officer):
        raise HTTPException(status_code=403, detail="Unauthorized to change match status")

    match.status = status_update.status
    db.commit()
    db.refresh(match)
    return match

@router.post("/trigger/{item_id}", response_model=List[MatchOut])
def trigger_ai_matching(
    item_id: str,
    db: Session = Depends(get_db),
    _ = Depends(get_current_user)
):
    """Manually re-run the multimodal AI similarity pipeline for a specific item."""
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    matches = run_matching_engine_for_item(item, db)
    return matches
