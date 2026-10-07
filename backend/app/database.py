from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import settings

# SQLite connection with thread checking disabled for FastAPI async handlers
engine = create_engine(
    settings.DATABASE_URL, 
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)


@event.listens_for(engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
    if "sqlite" in settings.DATABASE_URL:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def sync_database_schema(db_engine):
    """Ensure missing columns on existing tables are added automatically."""
    from sqlalchemy import inspect, text
    inspector = inspect(db_engine)
    if "claims" in inspector.get_table_names():
        claim_cols = {c["name"] for c in inspector.get_columns("claims")}
        with db_engine.connect() as conn:
            if "handover_code" not in claim_cols:
                conn.execute(text("ALTER TABLE claims ADD COLUMN handover_code VARCHAR(50)"))
            if "handed_over_at" not in claim_cols:
                conn.execute(text("ALTER TABLE claims ADD COLUMN handed_over_at DATETIME"))
            if "handover_officer_id" not in claim_cols:
                conn.execute(text("ALTER TABLE claims ADD COLUMN handover_officer_id VARCHAR"))
            if "handover_notes" not in claim_cols:
                conn.execute(text("ALTER TABLE claims ADD COLUMN handover_notes TEXT"))
            conn.commit()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
