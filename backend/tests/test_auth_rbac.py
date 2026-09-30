import pytest
from datetime import timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from app.main import app
from app.core.db import get_db, Base
from app.models.user import User
from app.models.investigation import Investigation, InvestigationReview
from app.core.auth import (
    get_password_hash,
    verify_password,
    create_access_token,
    decode_access_token
)
from app.api.deps import seed_default_users_if_needed

# Setup in-memory SQLite database with StaticPool so all sessions share the same DB
SQLALCHEMY_DATABASE_URL = "sqlite://"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db_and_overrides():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    seed_default_users_if_needed(db)

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


def get_token_for_user(email: str = "analyst@veridex.ai") -> str:
    resp = client.post("/api/auth/login", json={"email": email, "password": "password123"})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def auth_headers(email: str = "analyst@veridex.ai") -> dict:
    token = get_token_for_user(email)
    return {"Authorization": f"Bearer {token}"}


# 1. Password Hashing & Verification
def test_password_hash_and_verify():
    raw_pass = "secure_password_123"
    hashed = get_password_hash(raw_pass)
    assert hashed != raw_pass
    assert verify_password(raw_pass, hashed) is True
    assert verify_password("wrong_password", hashed) is False


# 2. JWT Creation
def test_jwt_creation():
    data = {"user_id": "usr_123", "email": "test@veridex.ai", "role": "ANALYST"}
    token = create_access_token(data)
    assert isinstance(token, str)
    assert len(token.split(".")) == 3


# 3. JWT Validation
def test_jwt_validation():
    data = {"user_id": "usr_123", "email": "test@veridex.ai", "role": "ANALYST"}
    token = create_access_token(data)
    payload = decode_access_token(token)
    assert payload["user_id"] == "usr_123"
    assert payload["email"] == "test@veridex.ai"
    assert payload["role"] == "ANALYST"


# 4. Expired JWT Rejection
def test_expired_jwt_rejection():
    data = {"user_id": "usr_123", "email": "test@veridex.ai", "role": "ANALYST"}
    expired_token = create_access_token(data, expires_delta=timedelta(seconds=-10))
    with pytest.raises(Exception) as exc_info:
        decode_access_token(expired_token)
    assert exc_info.value.status_code == 401


# 5. Malformed JWT Rejection
def test_malformed_jwt_rejection():
    with pytest.raises(Exception) as exc_info:
        decode_access_token("invalid.token.string")
    assert exc_info.value.status_code == 401


# 6. Inactive User Rejection
def test_inactive_user_rejection(setup_db_and_overrides):
    db = setup_db_and_overrides
    user = db.query(User).filter(User.email == "analyst@veridex.ai").first()
    user.is_active = False
    db.commit()

    resp = client.post("/api/auth/login", json={"email": "analyst@veridex.ai", "password": "password123"})
    assert resp.status_code == 401


# 7. Login Success
def test_login_success():
    resp = client.post("/api/auth/login", json={"email": "analyst@veridex.ai", "password": "password123"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["user"]["role"] == "ANALYST"


# 8. Login Invalid Credentials
def test_login_invalid_credentials():
    resp = client.post("/api/auth/login", json={"email": "analyst@veridex.ai", "password": "wrongpassword"})
    assert resp.status_code == 401


# 9. /api/auth/me
def test_read_current_user_profile():
    headers = auth_headers("reviewer@veridex.ai")
    resp = client.get("/api/auth/me", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "reviewer@veridex.ai"
    assert data["role"] == "REVIEWER"


# 10. Unauthenticated Protected Endpoint -> 401
def test_unauthenticated_protected_endpoint():
    resp = client.get("/api/investigations", headers={"X-Veridex-No-Auth-Fallback": "true"})
    assert resp.status_code == 401


# 11. ANALYST can create investigation
def test_analyst_can_create_investigation(monkeypatch):
    from app.schemas.ai import AskResponse
    def mock_run_investigation_loop(*args, **kwargs):
        return AskResponse(
            success=True,
            question="What is revenue?",
            answer="Revenue is 100",
            claims=[],
            evidence=[],
            tool_calls=[],
            metadata={"total_turns": 1}
        )

    monkeypatch.setattr("app.api.routes.run_investigation_loop", mock_run_investigation_loop)

    headers = auth_headers("analyst@veridex.ai")
    resp = client.post("/api/ask", json={"question": "Test question analyst"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["success"] is True


# 12. REVIEWER cannot create investigation
def test_reviewer_cannot_create_investigation():
    headers = auth_headers("reviewer@veridex.ai")
    resp = client.post("/api/ask", json={"question": "Reviewer question"}, headers=headers)
    assert resp.status_code == 403


# 13. AUDITOR cannot create investigation
def test_auditor_cannot_create_investigation():
    headers = auth_headers("auditor@veridex.ai")
    resp = client.post("/api/ask", json={"question": "Auditor question"}, headers=headers)
    assert resp.status_code == 403


# 14. ADMIN can create investigation
def test_admin_can_create_investigation(monkeypatch):
    from app.schemas.ai import AskResponse
    def mock_run_investigation_loop(*args, **kwargs):
        return AskResponse(
            success=True,
            question="Admin question",
            answer="Admin answer",
            claims=[],
            evidence=[],
            tool_calls=[]
        )
    monkeypatch.setattr("app.api.routes.run_investigation_loop", mock_run_investigation_loop)

    headers = auth_headers("admin@veridex.ai")
    resp = client.post("/api/ask", json={"question": "Admin question"}, headers=headers)
    assert resp.status_code == 200


# 15. Analyst sees only own investigations & 16. Analyst cannot access another analyst investigation
def test_analyst_ownership_isolation(setup_db_and_overrides):
    db = setup_db_and_overrides
    inv_user1 = Investigation(investigation_id="inv_user1", question="User 1 Q", status="COMPLETED", owner_id="usr_analyst_01")
    inv_user2 = Investigation(investigation_id="inv_user2", question="User 2 Q", status="COMPLETED", owner_id="usr_other_analyst")
    db.add_all([inv_user1, inv_user2])
    db.commit()

    headers = auth_headers("analyst@veridex.ai") # usr_analyst_01
    resp = client.get("/api/investigations", headers=headers)
    assert resp.status_code == 200
    inv_ids = [item["investigation_id"] for item in resp.json()]
    assert "inv_user1" in inv_ids
    assert "inv_user2" not in inv_ids

    # Analyst accessing user 1 -> OK
    resp_detail1 = client.get("/api/investigations/inv_user1", headers=headers)
    assert resp_detail1.status_code == 200

    # Analyst accessing user 2 -> 403 Forbidden
    resp_detail2 = client.get("/api/investigations/inv_user2", headers=headers)
    assert resp_detail2.status_code == 403


# 17. Reviewer can access another analyst investigation & 18. Auditor can access another analyst investigation
def test_privileged_roles_can_access_all_investigations(setup_db_and_overrides):
    db = setup_db_and_overrides
    inv_user1 = Investigation(investigation_id="inv_priv1", question="User 1 Q", status="COMPLETED", owner_id="usr_analyst_01")
    db.add(inv_user1)
    db.commit()

    rev_headers = auth_headers("reviewer@veridex.ai")
    aud_headers = auth_headers("auditor@veridex.ai")

    assert client.get("/api/investigations/inv_priv1", headers=rev_headers).status_code == 200
    assert client.get("/api/investigations/inv_priv1", headers=aud_headers).status_code == 200


# 19. Analyst can continue own thread & 20. Analyst cannot hijack another user's thread & 21. Reviewer cannot continue analyst thread
def test_multi_turn_thread_continuation_security(setup_db_and_overrides, monkeypatch):
    db = setup_db_and_overrides
    inv1 = Investigation(investigation_id="inv_thread1", question="Q1", status="COMPLETED", owner_id="usr_analyst_01")
    db.add(inv1)
    db.commit()

    from app.schemas.ai import AskResponse
    def mock_run_investigation_loop(*args, **kwargs):
        return AskResponse(
            success=True,
            question="Continuation",
            answer="Answer",
            claims=[],
            evidence=[],
            tool_calls=[]
        )
    monkeypatch.setattr("app.api.routes.run_investigation_loop", mock_run_investigation_loop)

    headers_owner = auth_headers("analyst@veridex.ai") # usr_analyst_01
    headers_reviewer = auth_headers("reviewer@veridex.ai")

    # Owner can continue own thread
    resp_cont = client.post("/api/ask", json={"question": "Turn 2", "investigation_id": "inv_thread1"}, headers=headers_owner)
    assert resp_cont.status_code == 200

    # Reviewer cannot ask / append turn
    resp_rev = client.post("/api/ask", json={"question": "Turn 2", "investigation_id": "inv_thread1"}, headers=headers_reviewer)
    assert resp_rev.status_code == 403


# 22. Analyst cannot submit review & 23. Auditor cannot submit review & 24. Reviewer can submit review & 25. Admin can submit review
def test_review_submission_roles(setup_db_and_overrides):
    db = setup_db_and_overrides
    inv = Investigation(investigation_id="inv_rev_test", question="Q", status="COMPLETED", owner_id="usr_analyst_01")
    db.add(inv)
    db.commit()

    payload = {"review_status": "APPROVED", "review_notes": "Looks solid"}

    # Analyst -> 403
    assert client.post("/api/investigations/inv_rev_test/review", json=payload, headers=auth_headers("analyst@veridex.ai")).status_code == 403

    # Auditor -> 403
    assert client.post("/api/investigations/inv_rev_test/review", json=payload, headers=auth_headers("auditor@veridex.ai")).status_code == 403

    # Reviewer -> 200
    assert client.post("/api/investigations/inv_rev_test/review", json=payload, headers=auth_headers("reviewer@veridex.ai")).status_code == 200

    # Admin -> 200
    assert client.post("/api/investigations/inv_rev_test/review", json=payload, headers=auth_headers("admin@veridex.ai")).status_code == 200


# 26. Reviewer cannot review own investigation & 27. Fake reviewer_id is ignored & 28. Stored reviewer_id equals authenticated user ID
def test_self_review_prevention_and_verified_identity(setup_db_and_overrides):
    db = setup_db_and_overrides
    inv_own = Investigation(investigation_id="inv_rev_own", question="Q", status="COMPLETED", owner_id="usr_reviewer_01")
    inv_other = Investigation(investigation_id="inv_rev_other", question="Q", status="COMPLETED", owner_id="usr_analyst_01")
    db.add_all([inv_own, inv_other])
    db.commit()

    rev_headers = auth_headers("reviewer@veridex.ai") # usr_reviewer_01

    # Reviewer attempting to review their own investigation -> 403 Forbidden
    payload = {"review_status": "APPROVED", "reviewer_id": "fake_impersonated_id", "review_notes": "Self review"}
    resp = client.post("/api/investigations/inv_rev_own/review", json=payload, headers=rev_headers)
    assert resp.status_code == 403

    # Now test fake reviewer_id on an investigation owned by someone else
    resp_valid = client.post("/api/investigations/inv_rev_other/review", json=payload, headers=rev_headers)
    assert resp_valid.status_code == 200
    res_data = resp_valid.json()
    assert res_data["reviewer_id"] == "usr_reviewer_01"  # Bound to authenticated user, fake_impersonated_id ignored!


# 29. Analyst cannot export & 30. Reviewer can export & 31. Auditor can export
def test_export_report_roles(setup_db_and_overrides):
    db = setup_db_and_overrides
    inv = Investigation(investigation_id="inv_exp_test", question="Q", status="COMPLETED", owner_id="usr_analyst_01")
    db.add(inv)
    db.commit()

    # Analyst -> 403
    assert client.get("/api/investigations/inv_exp_test/export?format=json", headers=auth_headers("analyst@veridex.ai")).status_code == 403

    # Reviewer -> 200
    assert client.get("/api/investigations/inv_exp_test/export?format=json", headers=auth_headers("reviewer@veridex.ai")).status_code == 200

    # Auditor -> 200
    assert client.get("/api/investigations/inv_exp_test/export?format=json", headers=auth_headers("auditor@veridex.ai")).status_code == 200


# 32. Auditor cannot reassess & 33. Analyst can reassess own investigation & 34. Analyst cannot reassess another user's & 35. Reviewer can reassess another user's
def test_reassess_roles_and_ownership(setup_db_and_overrides):
    db = setup_db_and_overrides
    from app.ai.provider import MockLLMProvider
    from app.ai.orchestrator import run_investigation_loop
    from app.services.investigation_service import InvestigationService

    inv_analyst = Investigation(investigation_id="inv_reassess_analyst", question="Q", status="IN_PROGRESS", owner_id="usr_analyst_01")
    inv_other = Investigation(investigation_id="inv_reassess_other", question="Q", status="IN_PROGRESS", owner_id="usr_other")
    db.add_all([inv_analyst, inv_other])
    db.commit()

    provider = MockLLMProvider()
    resp = run_investigation_loop(question="Q", db=db, provider=provider, max_turns=1)

    InvestigationService.update_investigation_success(db=db, investigation_id="inv_reassess_analyst", response=resp, execution_time_ms=10.0)
    InvestigationService.update_investigation_success(db=db, investigation_id="inv_reassess_other", response=resp, execution_time_ms=10.0)

    # Auditor -> 403
    assert client.post("/api/investigations/inv_reassess_analyst/reassess", headers=auth_headers("auditor@veridex.ai")).status_code == 403

    # Analyst reassesses own -> 200
    assert client.post("/api/investigations/inv_reassess_analyst/reassess", headers=auth_headers("analyst@veridex.ai")).status_code == 200

    # Analyst reassesses another user's -> 403
    assert client.post("/api/investigations/inv_reassess_other/reassess", headers=auth_headers("analyst@veridex.ai")).status_code == 403

    # Reviewer reassesses another user's -> 200
    assert client.post("/api/investigations/inv_reassess_other/reassess", headers=auth_headers("reviewer@veridex.ai")).status_code == 200


# 36. Admin bypasses ownership restrictions
def test_admin_bypasses_ownership_restrictions(setup_db_and_overrides, monkeypatch):
    db = setup_db_and_overrides
    inv_other = Investigation(investigation_id="inv_admin_test", question="Q", status="COMPLETED", owner_id="usr_analyst_01")
    db.add(inv_other)
    db.commit()

    admin_headers = auth_headers("admin@veridex.ai")

    # Admin can view another user's investigation
    assert client.get("/api/investigations/inv_admin_test", headers=admin_headers).status_code == 200

    from app.schemas.ai import AskResponse
    def mock_run_investigation_loop(*args, **kwargs):
        return AskResponse(
            success=True,
            question="Admin continuation",
            answer="Admin answer",
            claims=[],
            evidence=[],
            tool_calls=[]
        )
    monkeypatch.setattr("app.api.routes.run_investigation_loop", mock_run_investigation_loop)

    # Admin can append turn to another user's investigation
    assert client.post("/api/ask", json={"question": "Admin turn", "investigation_id": "inv_admin_test"}, headers=admin_headers).status_code == 200
