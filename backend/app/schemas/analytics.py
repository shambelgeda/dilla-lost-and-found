from pydantic import BaseModel
from typing import List

class HotspotStat(BaseModel):
    campus_name: str
    block_or_facility: str
    lost_count: int
    found_count: int

class CategoryStat(BaseModel):
    category_name: str
    count: int

class TrendStat(BaseModel):
    month: str
    lost_reports: int
    found_reports: int
    approved_claims: int

class OverviewStats(BaseModel):
    total_lost_reported: int
    total_found_reported: int
    total_matches_found: int
    total_claims_approved: int
    recovery_rate_percentage: float
    hotspots: List[HotspotStat]
    category_distribution: List[CategoryStat]
