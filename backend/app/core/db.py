from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings
from app.models import Base

engine = create_engine(
    settings.DATABASE_URL,
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
