import sys
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from app.core.config import settings
from app.models.business_data import Base

db_url = settings.DATABASE_URL

# Only default to in-memory SQLite for tests if DATABASE_URL is NOT set to PostgreSQL and USE_POSTGRES is NOT 1
is_testing = "pytest" in sys.modules or os.getenv("TESTING") == "1"
is_postgres_forced = os.getenv("USE_POSTGRES") == "1" or "postgresql" in db_url.lower()

if is_testing and not is_postgres_forced:
    db_url = "sqlite://"
    engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
else:
    engine = create_engine(
        db_url,
        pool_pre_ping=True
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """
    Creates database tables if they do not exist.
    """
    Base.metadata.create_all(bind=engine)


def get_db():
    """
    FastAPI dependency yielding a database session.
    """
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
