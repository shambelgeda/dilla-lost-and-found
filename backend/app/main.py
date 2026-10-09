import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from app.config import settings
from app.database import Base, engine, SessionLocal, sync_database_schema
from app.routers import (
    analytics_router,
    auth_router,
    claims_router,
    items_router,
    locations_router,
    matches_router,
    notifications_router,
)
from app.seed_data import seed_database
from app.services.ai_engine import refresh_stale_embeddings_and_matches

# Create tables in database and sync schema additions
Base.metadata.create_all(bind=engine)
sync_database_schema(engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = SessionLocal()
    try:
        seed_database(db)
        refresh_stale_embeddings_and_matches(db)
        yield
    finally:
        db.close()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Multimodal AI-Based Lost-and-Found Matching System using Image & Text Similarity for Dilla University",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS middleware for modern frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static file serving for uploaded item photos
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

frontend_dist = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "frontend",
    "dist",
)
if os.path.isdir(frontend_dist):
    app.mount("/app", StaticFiles(directory=frontend_dist, html=True), name="frontend")

# Include Routers
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(locations_router, prefix=settings.API_V1_STR)
app.include_router(items_router, prefix=settings.API_V1_STR)
app.include_router(matches_router, prefix=settings.API_V1_STR)
app.include_router(claims_router, prefix=settings.API_V1_STR)
app.include_router(analytics_router, prefix=settings.API_V1_STR)
app.include_router(notifications_router, prefix=settings.API_V1_STR)

@app.get("/")
def root():
    return {
        "system": settings.PROJECT_NAME,
        "institution": "Dilla University",
        "status": "operational",
        "version": settings.VERSION,
        "docs": "/docs",
        "portal": "/app/",
    }

@app.get("/api/v1/health")
def health_check():
    return {
        "status": "healthy",
        "service": "dilla-lost-and-found-backend",
        "ai_engine": "multimodal-sim-v1",
        "weights": {
            "image": settings.WEIGHT_IMAGE,
            "text": settings.WEIGHT_TEXT,
            "metadata": settings.WEIGHT_METADATA
        }
    }
