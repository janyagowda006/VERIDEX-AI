import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from app.main import app
from app.core.db import get_db, Base
from app.models.user import User
from app.models.audit_log import AuditLogEntry
from app.services.audit_logger import AuditLogger
from app.core.auth import create_access_token, get_password_hash
from app.services.investigation_service import InvestigationService
from app.api.deps import seed_default_users_if_needed


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

    # Add custom test users
    users = [
        ("usr_analyst_t", "analyst_t@veridex.ai", "password123", "Alice Analyst", "ANALYST"),
        ("usr_reviewer_t", "reviewer_t@veridex.ai", "password123", "Bob Reviewer", "REVIEWER"),
        ("usr_auditor_t", "auditor_t@veridex.ai", "password123", "Carol Auditor", "AUDITOR"),
        ("usr_admin_t", "admin_t@veridex.ai", "password123", "Dave Admin", "ADMIN")
    ]

    for u_id, email, password, name, role in users:
        existing = db.query(User).filter(User.user_id == u_id).first()
        if not existing:
            user = User(
                user_id=u_id,
                email=email,
                hashed_password=get_password_hash(password),
                full_name=name,
                role=role,
                is_active=True
            )
            db.add(user)
    db.commit()

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


def get_auth_header(user_id: str, role: str, email: str = "user@veridex.ai"):
    token = create_access_token({"user_id": user_id, "role": role, "email": email})
    return {"Authorization": f"Bearer {token}", "X-Veridex-No-Auth-Fallback": "1"}


def create_sample_investigation(db: Session, owner_id: str) -> str:
    inv = InvestigationService.create_investigation(
        db=db,
        question="Which vendor has highest risk?",
        owner_id=owner_id
    )
    inv.status = "COMPLETED"
    db.commit()
    return inv.investigation_id



# ============================================================================
# AUTH AUDIT LOG TESTS (1-3, 18)
# ============================================================================

def test_login_success_creates_audit_event(setup_db_and_overrides):
    """1. Successful login creates LOGIN_SUCCESS audit log entry."""
    db = setup_db_and_overrides
    response = client.post("/api/auth/login", json={
        "email": "analyst_t@veridex.ai",
        "password": "password123"
    })
    assert response.status_code == 200

    logs = AuditLogger.list_audit_logs(db, user_id="usr_analyst_t", action_type="LOGIN_SUCCESS")
    assert len(logs) >= 1
    latest = logs[0]
    assert latest.status == "SUCCESS"
    assert latest.user_role == "ANALYST"
    assert latest.resource_id == "usr_analyst_t"


def test_login_failure_creates_audit_event(setup_db_and_overrides):
    """2. Failed login creates LOGIN_FAILURE audit log entry."""
    db = setup_db_and_overrides
    response = client.post("/api/auth/login", json={
        "email": "analyst_t@veridex.ai",
        "password": "wrongpassword"
    })
    assert response.status_code == 401

    logs = AuditLogger.list_audit_logs(db, action_type="LOGIN_FAILURE")
    assert len(logs) >= 1
    latest = logs[0]
    assert latest.status == "FAILURE"
    assert latest.resource_id == "analyst_t@veridex.ai"


def test_passwords_and_tokens_never_logged(setup_db_and_overrides):
    """3. Verify passwords or tokens are never stored in audit logs."""
    db = setup_db_and_overrides
    client.post("/api/auth/login", json={
        "email": "analyst_t@veridex.ai",
        "password": "supersecretpassword"
    })

    logs = db.query(AuditLogEntry).all()
    for log in logs:
        log_str = f"{log.details} {log.resource_id} {log.action_type} {log.status}"
        assert "supersecretpassword" not in log_str
        assert "Bearer" not in log_str


# ============================================================================
# RBAC ACCESS TESTS (4-7)
# ============================================================================

def test_auditor_can_query_audit_logs():
    """4. AUDITOR role can query audit log entries."""
    headers = get_auth_header("usr_auditor_t", "AUDITOR")
    response = client.get("/api/v1/audit/logs", headers=headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_admin_can_query_audit_logs():
    """5. ADMIN role can query audit log entries."""
    headers = get_auth_header("usr_admin_t", "ADMIN")
    response = client.get("/api/v1/audit/logs", headers=headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_analyst_cannot_query_audit_logs():
    """6. ANALYST receives 403 when querying audit log entries."""
    headers = get_auth_header("usr_analyst_t", "ANALYST")
    response = client.get("/api/v1/audit/logs", headers=headers)
    assert response.status_code == 403


def test_reviewer_cannot_query_audit_logs():
    """7. REVIEWER receives 403 when querying audit log entries."""
    headers = get_auth_header("usr_reviewer_t", "REVIEWER")
    response = client.get("/api/v1/audit/logs", headers=headers)
    assert response.status_code == 403


# ============================================================================
# REVIEW AUDIT LOG TESTS (8-11)
# ============================================================================

def test_approved_review_creates_audit_event(setup_db_and_overrides):
    """8. APPROVED review creates REVIEW_APPROVE audit log entry."""
    db = setup_db_and_overrides
    inv_id = create_sample_investigation(db, owner_id="usr_analyst_t")

    headers = get_auth_header("usr_reviewer_t", "REVIEWER")
    response = client.post(
        f"/api/investigations/{inv_id}/review",
        json={"review_status": "APPROVED", "review_notes": "Looks robust"},
        headers=headers
    )
    assert response.status_code == 200

    logs = AuditLogger.list_audit_logs(db, resource_id=inv_id, action_type="REVIEW_APPROVE")
    assert len(logs) >= 1
    assert logs[0].user_id == "usr_reviewer_t"
    assert logs[0].user_role == "REVIEWER"
    assert logs[0].status == "SUCCESS"


def test_rejected_review_creates_audit_event(setup_db_and_overrides):
    """9. REJECTED review creates REVIEW_REJECT audit log entry."""
    db = setup_db_and_overrides
    inv_id = create_sample_investigation(db, owner_id="usr_analyst_t")

    headers = get_auth_header("usr_reviewer_t", "REVIEWER")
    response = client.post(
        f"/api/investigations/{inv_id}/review",
        json={"review_status": "REJECTED", "review_notes": "Insufficient data"},
        headers=headers
    )
    assert response.status_code == 200

    logs = AuditLogger.list_audit_logs(db, resource_id=inv_id, action_type="REVIEW_REJECT")
    assert len(logs) >= 1
    assert logs[0].user_id == "usr_reviewer_t"


def test_self_review_remains_blocked(setup_db_and_overrides):
    """10. Self-review remains blocked (403)."""
    db = setup_db_and_overrides
    inv_id = create_sample_investigation(db, owner_id="usr_reviewer_t")

    headers = get_auth_header("usr_reviewer_t", "REVIEWER")
    response = client.post(
        f"/api/investigations/{inv_id}/review",
        json={"review_status": "APPROVED", "review_notes": "Self review attempt"},
        headers=headers
    )
    assert response.status_code == 403


def test_unauthorized_user_cannot_create_review(setup_db_and_overrides):
    """11. ANALYST user cannot create reviews (403)."""
    db = setup_db_and_overrides
    inv_id = create_sample_investigation(db, owner_id="usr_admin_t")

    headers = get_auth_header("usr_analyst_t", "ANALYST")
    response = client.post(
        f"/api/investigations/{inv_id}/review",
        json={"review_status": "APPROVED", "review_notes": "Analyst attempt"},
        headers=headers
    )
    assert response.status_code == 403


# ============================================================================
# EXPORT AUDIT LOG TESTS (12-14)
# ============================================================================

def test_authorized_export_creates_audit_event(setup_db_and_overrides):
    """12. Authorized report export creates EXPORT_REPORT audit log entry."""
    db = setup_db_and_overrides
    inv_id = create_sample_investigation(db, owner_id="usr_analyst_t")

    headers = get_auth_header("usr_auditor_t", "AUDITOR")
    response = client.get(f"/api/investigations/{inv_id}/export?format=json", headers=headers)
    assert response.status_code == 200

    logs = AuditLogger.list_audit_logs(db, resource_id=inv_id, action_type="EXPORT_REPORT")
    assert len(logs) >= 1
    assert logs[0].user_id == "usr_auditor_t"
    assert logs[0].user_role == "AUDITOR"
    assert "json" in logs[0].details.lower()


def test_unauthorized_analyst_export_blocked(setup_db_and_overrides):
    """13. Analyst export attempt is blocked with 403."""
    db = setup_db_and_overrides
    inv_id = create_sample_investigation(db, owner_id="usr_analyst_t")

    headers = get_auth_header("usr_analyst_t", "ANALYST")
    response = client.get(f"/api/investigations/{inv_id}/export?format=json", headers=headers)
    assert response.status_code == 403


def test_audit_entry_contains_user_and_resource_id(setup_db_and_overrides):
    """14. Audit log entry correctly attributes user ID and resource ID."""
    db = setup_db_and_overrides
    inv_id = create_sample_investigation(db, owner_id="usr_analyst_t")

    headers = get_auth_header("usr_admin_t", "ADMIN")
    client.get(f"/api/investigations/{inv_id}/export?format=markdown", headers=headers)

    logs = AuditLogger.list_audit_logs(db, resource_id=inv_id, action_type="EXPORT_REPORT")
    assert len(logs) >= 1
    assert logs[0].user_id == "usr_admin_t"
    assert logs[0].resource_id == inv_id


# ============================================================================
# OWNERSHIP & IMMUTABILITY TESTS (15-18)
# ============================================================================

def test_investigation_ownership_isolation_remains_intact(setup_db_and_overrides):
    """15. Ownership isolation remains strictly intact."""
    db = setup_db_and_overrides
    inv_id = create_sample_investigation(db, owner_id="usr_admin_t")

    headers = get_auth_header("usr_analyst_t", "ANALYST")
    response = client.get(f"/api/investigations/{inv_id}", headers=headers)
    assert response.status_code == 403


def test_no_audit_log_modification_routes_exist():
    """16. No API routes permit modification (PUT/PATCH) of audit records."""
    headers = get_auth_header("usr_admin_t", "ADMIN")
    put_resp = client.put("/api/v1/audit/logs/some_id", json={"status": "MUTATED"}, headers=headers)
    patch_resp = client.patch("/api/v1/audit/logs/some_id", json={"status": "MUTATED"}, headers=headers)
    assert put_resp.status_code in (404, 405)
    assert patch_resp.status_code in (404, 405)


def test_no_audit_log_deletion_routes_exist():
    """17. No API routes permit deletion (DELETE) of audit records."""
    headers = get_auth_header("usr_admin_t", "ADMIN")
    del_resp = client.delete("/api/v1/audit/logs/some_id", headers=headers)
    assert del_resp.status_code in (404, 405)


def test_audit_records_capture_request_ip(setup_db_and_overrides):
    """18. Audit records capture request client IP."""
    db = setup_db_and_overrides
    response = client.post("/api/auth/login", json={
        "email": "analyst_t@veridex.ai",
        "password": "password123"
    })
    assert response.status_code == 200

    logs = AuditLogger.list_audit_logs(db, user_id="usr_analyst_t", action_type="LOGIN_SUCCESS")
    assert len(logs) >= 1
    assert logs[0].ip_address is not None or logs[0].ip_address == "testclient"
