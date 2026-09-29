import tempfile
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from app.models.business_data import Base
from app.services.data_ingestion import ingest_csv_to_db
from scripts.generate_data import generate_synthetic_data


@pytest.fixture(scope="module")
def test_db_session():
    """
    Shared pytest fixture creating an in-memory SQLite database populated with synthetic dataset.
    Used across test_db.py and test_sql_tool.py.
    """
    engine = create_engine("sqlite:///:memory:", echo=False)

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()

    with tempfile.TemporaryDirectory() as tmp_dir:
        generate_synthetic_data(seed=42, output_dir=tmp_dir)
        ingest_csv_to_db(tmp_dir, session)

    yield session
    session.close()
