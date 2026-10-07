import os
from typing import Optional

from app.models.claim import Claim
from app.models.item import Item
from app.models.match import Match
from app.models.user import User, UserRole
from app.schemas.claim import ClaimOut
from app.schemas.item import ItemOut
from app.schemas.match import MatchOut


def sanitize_item_out(item: Item, current_user: Optional[User]) -> ItemOut:
    """
    Mask confidential identifiers (serial numbers, password hints, hidden marks)
    unless the requesting user is the item reporter or a campus security officer / admin.
    Also normalizes uploaded image URLs for client access.
    """
    out = ItemOut.model_validate(item)
    is_owner = current_user and current_user.id == item.user_id
    is_staff_or_admin = current_user and current_user.role in [UserRole.SECURITY_OFFICER, UserRole.ADMIN]

    if not (is_owner or is_staff_or_admin):
        out.confidential_identifiers = None

    for image in out.images:
        image.file_path = f"/uploads/{os.path.basename(image.file_path)}"

    return out


def sanitize_match_out(match: Match, current_user: Optional[User]) -> MatchOut:
    """
    Sanitize both lost and found items in a Match record so confidential identifiers
    are never leaked to students before an ownership claim is verified.
    """
    out = MatchOut.model_validate(match)
    if match.lost_item:
        out.lost_item = sanitize_item_out(match.lost_item, current_user)
    if match.found_item:
        out.found_item = sanitize_item_out(match.found_item, current_user)
    return out


def sanitize_claim_out(claim: Claim, current_user: Optional[User]) -> ClaimOut:
    """
    Sanitize items linked to a claim and protect the physical handover verification code.
    Only the claimant and security officers / admins may view the handover code.
    """
    out = ClaimOut.model_validate(claim)
    if claim.found_item:
        out.found_item = sanitize_item_out(claim.found_item, current_user)
    if claim.lost_item:
        out.lost_item = sanitize_item_out(claim.lost_item, current_user)

    is_claimant = current_user and current_user.id == claim.claimant_id
    is_staff_or_admin = current_user and current_user.role in [UserRole.SECURITY_OFFICER, UserRole.ADMIN]

    if not (is_claimant or is_staff_or_admin):
        out.handover_code = None
        out.proof_description = "[Protected Proof]"
        out.proof_file_path = None

    return out
