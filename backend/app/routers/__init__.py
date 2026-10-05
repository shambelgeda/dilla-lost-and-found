from app.routers.auth import router as auth_router
from app.routers.locations import router as locations_router
from app.routers.items import router as items_router
from app.routers.matches import router as matches_router
from app.routers.claims import router as claims_router
from app.routers.analytics import router as analytics_router
from app.routers.notifications import router as notifications_router

__all__ = [
    "auth_router",
    "locations_router",
    "items_router",
    "matches_router",
    "claims_router",
    "analytics_router",
    "notifications_router",
]
