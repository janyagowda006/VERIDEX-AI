from fastapi.testclient import TestClient
from app.main import app
from app.core.db import get_db, Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import pytest

client = TestClient(app)

# In-memory test DB for schema and readiness
engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield db
    db.close()
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


def test_health_check():
    """
    Test GET /health endpoint returns HTTP 200 and status ok.
    """
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_probe():
    """
    Test GET /ready and /health/ready return readiness status.
    """
    resp = client.get("/ready")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ready"
    assert resp.json()["database"] == "connected"

    resp_alias = client.get("/health/ready")
    assert resp_alias.status_code == 200
    assert resp_alias.json()["status"] == "ready"


def test_cors_preflight():
    """
    Test CORS OPTIONS preflight returns appropriate headers.
    """
    response = client.options(
        "/api/ask",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Authorization,Content-Type"
        }
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_schema_endpoint_aliases():
    """
    Test /api/tools/sql-schema and /api/tools/schema return identical schema.
    """
    resp1 = client.get("/api/tools/sql-schema")
    assert resp1.status_code == 200
    data1 = resp1.json()

    resp2 = client.get("/api/tools/schema")
    assert resp2.status_code == 200
    data2 = resp2.json()

    assert data1 == data2
    assert "tables" in data1


def test_root_endpoint():
    """
    Test GET / root endpoint returns expected service payload.
    """
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "project" in data
    assert data["project"] == "VERIDEX-AI"
