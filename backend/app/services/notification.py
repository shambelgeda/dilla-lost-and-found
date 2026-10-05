import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.item import Item
from app.models.match import Match
from app.models.notification import Notification
from app.models.user import User

logger = logging.getLogger("notification_service")


def create_notification(
    db: Session,
    user: User,
    title: str,
    message: str,
    notification_type: str = "SYSTEM",
    related_entity: Optional[str] = None,
    related_id: Optional[str] = None,
) -> Notification:
    notification = Notification(
        id=f"ntf-{uuid.uuid4().hex[:8]}",
        user_id=user.id,
        title=title,
        message=message,
        notification_type=notification_type,
        related_entity=related_entity,
        related_id=related_id,
        is_read=False,
        created_at=datetime.now(timezone.utc),
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


def send_match_notification(
    match: Match,
    lost_item: Item,
    found_item: Item,
    recipient: User,
    db: Optional[Session] = None,
):
    """
    Dispatch automated notification (Telegram / Email / In-App) to student when an AI match is found.
    """
    message = (
        f"🎯 [Dilla University Lost & Found] Potential Match Found!\n"
        f"Your lost item '{lost_item.title}' matches a found item '{found_item.title}' "
        f"with a similarity score of {int(match.final_score * 100)}%.\n"
        f"Found Location: {found_item.location.block_or_facility if found_item.location else 'Campus'}\n"
        f"Please check your portal to view the details and file a claim."
    )

    if db is not None:
        create_notification(
            db,
            recipient,
            "Potential Match Found",
            message,
            notification_type="MATCH",
            related_entity="matches",
            related_id=match.id,
        )

    if recipient.telegram_chat_id:
        logger.info(f"[TELEGRAM ALERT] To Chat {recipient.telegram_chat_id}: {message}")

    logger.info(f"[EMAIL NOTIFICATION] To {recipient.email}: Subject: Match Alert - {lost_item.title}")


def send_claim_update_notification(
    claim_status: str,
    claimant: User,
    item_title: str,
    remarks: Optional[str] = None,
    db: Optional[Session] = None,
):
    """Notify student when an officer reviews their ownership claim."""
    status_text = "APPROVED ✅" if claim_status == "APPROVED" else "REJECTED ❌"
    msg = (
        f"📢 [Dilla University Lost & Found] Claim Update:\n"
        f"Your claim for '{item_title}' has been {status_text}.\n"
        f"Notes: {remarks or 'No additional notes.'}\n"
    )
    if claim_status == "APPROVED":
        msg += "Please visit the Campus Security / Lost-and-Found Office with your student ID for physical handover."

    if db is not None:
        create_notification(
            db,
            claimant,
            "Claim Status Update",
            msg,
            notification_type="CLAIM",
            related_entity="claims",
        )

    logger.info(f"[CLAIM NOTIF] To {claimant.email}: {msg}")
