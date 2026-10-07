import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.claim import Claim, ClaimStatus
from app.models.item import Item, ItemStatus, ItemType
from app.models.match import Match, MatchStatus
from app.models.user import User, UserRole
from app.models.audit import AuditLog
from app.schemas.claim import ClaimCreate, ClaimVerify, ClaimHandover, ClaimOut
from app.services.auth import get_current_user, require_roles
from app.services.notification import send_claim_update_notification, create_notification
from app.services.privacy import sanitize_claim_out

router = APIRouter(prefix="/claims", tags=["Ownership Claims & Verification"])

@router.post("", response_model=ClaimOut, status_code=status.HTTP_201_CREATED)
def submit_claim(
    claim_in: ClaimCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Verify found item exists
    found_item = db.query(Item).filter(Item.id == claim_in.found_item_id).first()
    if not found_item:
        raise HTTPException(status_code=404, detail="Found item not found")
    if found_item.report_type != ItemType.FOUND:
        raise HTTPException(status_code=400, detail="Claims can only be submitted against found items")
    if found_item.status == ItemStatus.RESOLVED:
        raise HTTPException(status_code=400, detail="This item has already been claimed and returned")

    if claim_in.lost_item_id:
        linked_lost_item = db.query(Item).filter(Item.id == claim_in.lost_item_id).first()
        if not linked_lost_item:
            raise HTTPException(status_code=400, detail="Lost item not found")
        if linked_lost_item.id == found_item.id:
            raise HTTPException(status_code=400, detail="Found item and lost item cannot be the same item")
        if linked_lost_item.report_type != ItemType.LOST:
            raise HTTPException(status_code=400, detail="Linked lost item must be a lost report")

    # Prevent duplicate pending claims from same user
    existing_claim = db.query(Claim).filter(
        Claim.found_item_id == claim_in.found_item_id,
        Claim.claimant_id == current_user.id,
        Claim.status.in_([ClaimStatus.SUBMITTED, ClaimStatus.UNDER_REVIEW])
    ).first()
    if existing_claim:
        raise HTTPException(status_code=400, detail="You already have an active pending claim for this item")

    claim_id = f"clm-{uuid.uuid4().hex[:10]}"
    claim = Claim(
        id=claim_id,
        found_item_id=claim_in.found_item_id,
        claimant_id=current_user.id,
        lost_item_id=claim_in.lost_item_id,
        proof_description=claim_in.proof_description,
        proof_file_path=claim_in.proof_file_path,
        status=ClaimStatus.SUBMITTED,
        created_at=datetime.now(timezone.utc)
    )
    db.add(claim)

    # Mark found item as CLAIM_PENDING
    found_item.status = ItemStatus.CLAIM_PENDING
    
    # Audit log
    audit = AuditLog(
        id=f"aud-{uuid.uuid4().hex[:8]}",
        actor_id=current_user.id,
        action="SUBMIT_CLAIM",
        target_entity="claims",
        target_id=claim_id,
        details=f"Claim submitted for item {found_item.title}"
    )
    db.add(audit)
    db.commit()
    db.refresh(claim)
    return sanitize_claim_out(claim, current_user)

@router.get("", response_model=List[ClaimOut])
def list_claims(
    status_filter: Optional[ClaimStatus] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Claim)
    if status_filter:
        query = query.filter(Claim.status == status_filter)
    # If caller is student/staff, only see their own claims
    if current_user.role in [UserRole.STUDENT, UserRole.STAFF]:
        query = query.filter(Claim.claimant_id == current_user.id)

    claims = query.order_by(Claim.created_at.desc()).all()
    return [sanitize_claim_out(c, current_user) for c in claims]

@router.get("/{claim_id}", response_model=ClaimOut)
def get_claim(
    claim_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    is_claimant = claim.claimant_id == current_user.id
    is_officer = current_user.role in [UserRole.SECURITY_OFFICER, UserRole.ADMIN]
    if not (is_claimant or is_officer):
        raise HTTPException(status_code=403, detail="Unauthorized to view this claim")

    return sanitize_claim_out(claim, current_user)

@router.patch("/{claim_id}/verify", response_model=ClaimOut)
def verify_claim(
    claim_id: str,
    verify_data: ClaimVerify,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SECURITY_OFFICER, UserRole.ADMIN))
):
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    claim.status = verify_data.status
    claim.verified_by = current_user.id
    claim.officer_notes = verify_data.officer_notes
    claim.resolved_at = datetime.now(timezone.utc)

    found_item = claim.found_item
    if verify_data.status == ClaimStatus.APPROVED:
        # Generate 6-character secure pickup verification code
        claim.handover_code = f"DU-{uuid.uuid4().hex[:6].upper()}"

        # Mark found item as RESOLVED
        found_item.status = ItemStatus.RESOLVED

        # If there was a linked lost item, mark it RESOLVED too
        if claim.lost_item_id:
            lost_item = db.query(Item).filter(Item.id == claim.lost_item_id).first()
            if lost_item:
                lost_item.status = ItemStatus.RESOLVED

            # Also update match status to CONFIRMED
            match_rec = db.query(Match).filter(
                Match.lost_item_id == claim.lost_item_id,
                Match.found_item_id == found_item.id
            ).first()
            if match_rec:
                match_rec.status = MatchStatus.CONFIRMED

        # Reconcile any other pending claims for this found item
        competing_claims = db.query(Claim).filter(
            Claim.found_item_id == found_item.id,
            Claim.id != claim.id,
            Claim.status.in_([ClaimStatus.SUBMITTED, ClaimStatus.UNDER_REVIEW])
        ).all()
        for c in competing_claims:
            c.status = ClaimStatus.REJECTED
            c.officer_notes = "Another ownership claim was approved for this item."
            c.resolved_at = datetime.now(timezone.utc)
            c.verified_by = current_user.id
            if c.claimant:
                send_claim_update_notification(
                    claim_status="REJECTED",
                    claimant=c.claimant,
                    item_title=found_item.title,
                    remarks=c.officer_notes,
                    db=db,
                )
    else:
        # Revert found item: check if there are other pending claims
        remaining_pending = db.query(Claim).filter(
            Claim.found_item_id == found_item.id,
            Claim.id != claim.id,
            Claim.status.in_([ClaimStatus.SUBMITTED, ClaimStatus.UNDER_REVIEW])
        ).count()
        found_item.status = ItemStatus.CLAIM_PENDING if remaining_pending > 0 else ItemStatus.OPEN

    # Audit log
    audit = AuditLog(
        id=f"aud-{uuid.uuid4().hex[:8]}",
        actor_id=current_user.id,
        action=f"VERIFY_CLAIM_{verify_data.status.value}",
        target_entity="claims",
        target_id=claim_id,
        details=f"Officer remarks: {verify_data.officer_notes or 'None'}"
    )
    db.add(audit)
    db.commit()
    db.refresh(claim)

    # Send Notification to claimant with pickup code instructions if approved
    if claim.claimant:
        remarks = verify_data.officer_notes or "Proof verified by officer."
        if verify_data.status == ClaimStatus.APPROVED and claim.handover_code:
            remarks += f"\nYour Physical Pickup Verification Code is: {claim.handover_code}. Please present this code and your Student ID at the Security Office."

        send_claim_update_notification(
            claim_status=verify_data.status.value,
            claimant=claim.claimant,
            item_title=found_item.title,
            remarks=remarks,
            db=db,
        )

    return sanitize_claim_out(claim, current_user)

@router.post("/{claim_id}/handover", response_model=ClaimOut)
def confirm_physical_handover(
    claim_id: str,
    handover_data: ClaimHandover,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SECURITY_OFFICER, UserRole.ADMIN))
):
    """
    Physical handover verification: Officer verifies student's university ID and checks the 6-character
    verification pickup code before transferring custody of the found item.
    """
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    if claim.status != ClaimStatus.APPROVED:
        raise HTTPException(
            status_code=400,
            detail=f"Only approved claims can be physically handed over. Current status: {claim.status.value}"
        )

    submitted_code = handover_data.verification_code.strip().upper()
    if not claim.handover_code or submitted_code != claim.handover_code.upper():
        raise HTTPException(
            status_code=400,
            detail="Invalid physical handover verification code. Please confirm code on student's portal."
        )

    claim.status = ClaimStatus.HANDED_OVER
    claim.handed_over_at = datetime.now(timezone.utc)
    claim.handover_officer_id = current_user.id
    claim.handover_notes = handover_data.handover_notes

    found_item = claim.found_item
    found_item.status = ItemStatus.RESOLVED

    audit = AuditLog(
        id=f"aud-{uuid.uuid4().hex[:8]}",
        actor_id=current_user.id,
        action="PHYSICAL_HANDOVER_COMPLETED",
        target_entity="claims",
        target_id=claim_id,
        details=f"Item '{found_item.title}' handed over to claimant {claim.claimant.full_name} ({claim.claimant.university_id})"
    )
    db.add(audit)
    db.commit()
    db.refresh(claim)

    if claim.claimant:
        create_notification(
            db=db,
            user=claim.claimant,
            title="Physical Handover Completed",
            message=(
                f"✅ Physical handover complete! Your item '{found_item.title}' has been successfully handed over "
                f"to you at the Campus Security Office by Officer {current_user.full_name}. Thank you for using "
                f"the Dilla University Lost & Found system."
            ),
            notification_type="HANDOVER",
            related_entity="claims",
            related_id=claim.id
        )

    return sanitize_claim_out(claim, current_user)
