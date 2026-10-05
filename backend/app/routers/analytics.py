from datetime import datetime, timezone
from typing import List, Sequence
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models.item import Item, ItemType, ItemStatus
from app.models.match import Match
from app.models.claim import Claim, ClaimStatus
from app.models.location import CampusLocation
from app.models.category import Category
from app.models.audit import AuditLog
from app.models.user import UserRole
from app.schemas.analytics import OverviewStats, HotspotStat, CategoryStat, TrendStat
from app.services.auth import require_roles

router = APIRouter(prefix="/analytics", tags=["Analytics & Hotspots"])


def shift_calendar_month(dt: datetime, months: int) -> datetime:
    month_index = dt.year * 12 + (dt.month - 1) + months
    year, month0 = divmod(month_index, 12)
    return dt.replace(year=year, month=month0 + 1)


def build_monthly_trend_summary(raw_rows: Sequence[tuple]) -> List[dict]:
    """Convert raw month buckets into dashboard-friendly summaries ordered newest first."""
    ordered = sorted(raw_rows, key=lambda row: row[0])
    return [
        {
            "month": month,
            "lost_reports": lost,
            "found_reports": found,
            "approved_claims": approved,
        }
        for month, lost, found, approved in ordered
    ][::-1]

@router.get("/overview", response_model=OverviewStats)
def get_overview_analytics(
    db: Session = Depends(get_db),
    _ = Depends(require_roles(UserRole.ADMIN, UserRole.SECURITY_OFFICER))
):
    total_lost = db.query(Item).filter(Item.report_type == ItemType.LOST).count()
    total_found = db.query(Item).filter(Item.report_type == ItemType.FOUND).count()
    total_matches = db.query(Match).count()
    total_approved_claims = db.query(Claim).filter(Claim.status == ClaimStatus.APPROVED).count()
    
    recovery_rate = (total_approved_claims / max(1, total_lost)) * 100.0

    # Hotspot calculation by location
    hotspot_results = db.query(
        CampusLocation.campus_name,
        CampusLocation.block_or_facility,
        func.count(Item.id).label("total_items")
    ).join(Item, CampusLocation.id == Item.location_id, isouter=True)\
     .group_by(CampusLocation.id)\
     .order_by(func.count(Item.id).desc())\
     .limit(10).all()

    hotspots = []
    for h in hotspot_results:
        lost_c = db.query(Item).join(CampusLocation).filter(
            CampusLocation.block_or_facility == h.block_or_facility,
            Item.report_type == ItemType.LOST
        ).count()
        found_c = db.query(Item).join(CampusLocation).filter(
            CampusLocation.block_or_facility == h.block_or_facility,
            Item.report_type == ItemType.FOUND
        ).count()
        hotspots.append(HotspotStat(
            campus_name=h.campus_name,
            block_or_facility=h.block_or_facility,
            lost_count=lost_c,
            found_count=found_c
        ))

    # Category distribution
    cat_results = db.query(
        Category.name,
        func.count(Item.id)
    ).join(Item, Category.id == Item.category_id, isouter=True)\
     .group_by(Category.id).all()

    categories = [CategoryStat(category_name=c[0], count=c[1]) for c in cat_results]

    return OverviewStats(
        total_lost_reported=total_lost,
        total_found_reported=total_found,
        total_matches_found=total_matches,
        total_claims_approved=total_approved_claims,
        recovery_rate_percentage=round(recovery_rate, 2),
        hotspots=hotspots,
        category_distribution=categories
    )


@router.get("/trends", response_model=List[TrendStat])
def get_monthly_trends(
    db: Session = Depends(get_db),
    _ = Depends(require_roles(UserRole.ADMIN, UserRole.SECURITY_OFFICER))
):
    """Return the previous six months of item and claim activity for the dashboard."""
    today = datetime.now(timezone.utc)
    month_start = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    months = [shift_calendar_month(month_start, -offset).strftime("%Y-%m") for offset in range(5, -1, -1)]
    lower_bound = shift_calendar_month(month_start, -5)

    lost_counts = {
        row[0]: row[1]
        for row in db.query(
            func.strftime("%Y-%m", Item.created_at).label("month"),
            func.count(Item.id).label("count")
        ).filter(
            Item.report_type == ItemType.LOST,
            Item.created_at >= lower_bound
        ).group_by("month").all()
    }
    found_counts = {
        row[0]: row[1]
        for row in db.query(
            func.strftime("%Y-%m", Item.created_at).label("month"),
            func.count(Item.id).label("count")
        ).filter(
            Item.report_type == ItemType.FOUND,
            Item.created_at >= lower_bound
        ).group_by("month").all()
    }
    approved_counts = {
        row[0]: row[1]
        for row in db.query(
            func.strftime("%Y-%m", Claim.created_at).label("month"),
            func.count(Claim.id).label("count")
        ).filter(
            Claim.status == ClaimStatus.APPROVED,
            Claim.created_at >= lower_bound
        ).group_by("month").all()
    }

    raw_rows = [
        (month, lost_counts.get(month, 0), found_counts.get(month, 0), approved_counts.get(month, 0))
        for month in months
    ]

    return [TrendStat(**entry) for entry in build_monthly_trend_summary(raw_rows)]


@router.get("/audit-logs")
def get_audit_logs(
    db: Session = Depends(get_db),
    _ = Depends(require_roles(UserRole.ADMIN))
):
    return db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(100).all()
