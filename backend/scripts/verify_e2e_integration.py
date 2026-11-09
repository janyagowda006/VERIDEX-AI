"""
VERIDEX AI — End-to-End Programmatic Integration Verification Script
Executes and verifies the complete 9-phase lifecycle against the live FastAPI application:
1. Synthetic business data & user seeding
2. Authentication & JWT access token generation
3. Bearer token profile validation and production unauthorized enforcement
4. Multipart business dataset file upload
5. Relational schema introspection & dynamic table discovery
6. Investigation question submission & persistent record creation
7. Multi-scenario robustness re-assessment
8. Human-in-the-loop review & separation of duties enforcement
9. Executive audit report export (Markdown & JSON)

Usage:
    python backend/scripts/verify_e2e_integration.py
"""

import os
import sys
import tempfile
from io import BytesIO
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure backend root is on sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

os.environ["TESTING"] = "1"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from app.main import app
from app.core.db import Base, get_db
from app.models.user import User
from app.models.business_data import Order
from app.models.investigation import Investigation, InvestigationReview
from app.services.data_ingestion import ingest_csv_to_db
from app.services.report_exporter import ReportExporter
from app.api.deps import seed_default_users_if_needed
from scripts.generate_data import generate_synthetic_data


def run_e2e_verification():
    print("=" * 60)
    print("VERIDEX AI — Live 9-Phase End-to-End Integration Verification")
    print("=" * 60)

    # In-memory SQLite engine with StaticPool
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Force production mode for strict auth enforcement
    app.state.ENVIRONMENT = "production"
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    seed_default_users_if_needed(db)

    with tempfile.TemporaryDirectory() as tmp_dir:
        generate_synthetic_data(seed=42, output_dir=tmp_dir)
        ingest_csv_to_db(tmp_dir, db)

    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    # --- Phase 1: Database Seeding & Record Count Verification ---
    print("\n[Phase 1] Database Seeding & Record Counts:")
    order_count = db.query(Order).count()
    user_count = db.query(User).count()
    print(f"  ✓ Seeded orders in DB: {order_count}")
    print(f"  ✓ Seeded users in DB: {user_count}")
    assert order_count > 0, "Orders table must contain seeded records"
    assert user_count >= 4, "Users table must contain default users"

    # --- Phase 2: Authentication & JWT Login ---
    print("\n[Phase 2] Authentication & JWT Login:")
    login_resp = client.post(
        "/api/auth/login",
        json={"email": "analyst@veridex.ai", "password": "password123"}
    )
    assert login_resp.status_code == 200, f"Expected 200, got {login_resp.status_code}"
    login_data = login_resp.json()
    token = login_data["access_token"]
    print(f"  ✓ Login status: {login_resp.status_code} OK")
    print(f"  ✓ Access token type: {login_data['token_type']}")
    print(f"  ✓ Authenticated user: {login_data['user']['email']} ({login_data['user']['role']})")
    assert login_data["user"]["role"] == "ANALYST"

    # Invalid credentials
    bad_login = client.post(
        "/api/auth/login",
        json={"email": "analyst@veridex.ai", "password": "wrongpassword"}
    )
    print(f"  ✓ Invalid credentials rejection: {bad_login.status_code} ({bad_login.json()['detail']})")
    assert bad_login.status_code == 401

    # --- Phase 3: Bearer Token Auth & Unauthorized Rejection ---
    print("\n[Phase 3] Bearer Token Auth & Production Unauthorized Rejection:")
    headers = {"Authorization": f"Bearer {token}"}
    me_resp = client.get("/api/auth/me", headers=headers)
    print(f"  ✓ Authenticated /api/auth/me status: {me_resp.status_code} ({me_resp.json()['user_id']})")
    assert me_resp.status_code == 200
    assert me_resp.json()["user_id"] == "usr_analyst_01"

    unauth_resp = client.get("/api/auth/me")
    print(f"  ✓ Unauthenticated /api/auth/me in production: {unauth_resp.status_code} ({unauth_resp.json()['detail']})")
    assert unauth_resp.status_code == 401

    # --- Phase 4: Multipart Dataset Upload & Dynamic Table Creation ---
    print("\n[Phase 4] Dynamic Dataset File Upload & DB Ingestion:")
    csv_bytes = b"order_id,region,product_line,revenue,profit,quarter,returned\nORD-UP-1,North,Gadgets,5000.0,1500.0,Q3,0\nORD-UP-2,South,Gadgets,3000.0,600.0,Q3,0\n"
    files = {"file": ("uploaded_orders.csv", BytesIO(csv_bytes), "text/csv")}
    upload_resp = client.post("/api/data-sources/upload", files=files, headers=headers)
    assert upload_resp.status_code == 201
    upload_data = upload_resp.json()
    uploaded_table = upload_data["table_name"]
    print(f"  ✓ Upload status: {upload_resp.status_code} CREATED")
    print(f"  ✓ Ingested table name: {uploaded_table} ({upload_data['row_count']} rows)")

    # Direct DB verification
    db_rows = db.execute(text(f"SELECT COUNT(*) FROM {uploaded_table}")).scalar()
    print(f"  ✓ Direct DB query verification: {db_rows} rows persisted in '{uploaded_table}'")
    assert db_rows == 2

    # --- Phase 5: Schema Introspection ---
    print("\n[Phase 5] Relational Schema Introspection:")
    schema_resp = client.get("/api/tools/sql-schema", headers=headers)
    assert schema_resp.status_code == 200
    tables = schema_resp.json()["tables"]
    table_names = [t["name"] for t in tables] if isinstance(tables, list) else list(tables.keys())
    print(f"  ✓ Schema introspection tables ({len(table_names)}): {table_names}")
    assert uploaded_table in table_names

    # --- Phase 6: Ask Question (Investigation Workflow) ---
    print("\n[Phase 6] Ask Question & Investigation Persistence:")
    ask_resp = client.post(
        "/api/ask",
        json={"question": "What region should we prioritize for Q4?", "max_turns": 2},
        headers=headers
    )
    assert ask_resp.status_code == 200
    ask_data = ask_resp.json()
    inv_id = ask_data["investigation_id"]
    print(f"  ✓ Ask status: {ask_resp.status_code} OK")
    print(f"  ✓ Created investigation ID: {inv_id}")

    # Direct DB record verification
    inv_record = db.query(Investigation).filter(Investigation.investigation_id == inv_id).first()
    assert inv_record is not None
    print(f"  ✓ Direct DB query verification: Investigation '{inv_id}' persisted with status '{inv_record.status}'")

    # --- Phase 7: Robustness Re-assessment ---
    print("\n[Phase 7] Robustness Re-assessment:")
    reassess_resp = client.post(
        f"/api/investigations/{inv_id}/reassess",
        json={"scenario_shift_pct": 15.0},
        headers=headers
    )
    assert reassess_resp.status_code == 200
    print(f"  ✓ Reassessment status: {reassess_resp.status_code} OK")

    # --- Phase 8: Human Review & Separation of Duties ---
    print("\n[Phase 8] Human-in-the-Loop Review & Separation of Duties:")
    # Analyst self-review must fail
    self_review = client.post(
        f"/api/investigations/{inv_id}/review",
        json={"review_status": "APPROVED", "reviewer_id": "usr_analyst_01", "review_notes": "Self review"},
        headers=headers
    )
    print(f"  ✓ Analyst self-review blocked: {self_review.status_code} ({self_review.json()['detail']})")
    assert self_review.status_code == 403

    # Reviewer Login
    rev_login = client.post(
        "/api/auth/login",
        json={"email": "reviewer@veridex.ai", "password": "password123"}
    )
    rev_token = rev_login.json()["access_token"]
    rev_headers = {"Authorization": f"Bearer {rev_token}"}

    # Reviewer submits review
    review_resp = client.post(
        f"/api/investigations/{inv_id}/review",
        json={"review_status": "APPROVED", "reviewer_id": "usr_reviewer_01", "review_notes": "Evidence audited."},
        headers=rev_headers
    )
    assert review_resp.status_code == 200
    print(f"  ✓ Reviewer approval status: {review_resp.status_code} OK (Decision: {review_resp.json()['review_status']})")
    assert review_resp.json()["review_status"] == "APPROVED"

    # Direct DB verification of review
    rev_record = db.query(InvestigationReview).filter(InvestigationReview.investigation_id == inv_id).first()
    assert rev_record is not None
    print(f"  ✓ Direct DB query verification: Review record persisted by '{rev_record.reviewer_id}'")

    # --- Phase 9: Report Export (RBAC Enforced) ---
    print("\n[Phase 9] Report Export & RBAC Enforcement:")
    # Analyst export attempt must fail
    analyst_export = client.get(f"/api/investigations/{inv_id}/export?format=markdown", headers=headers)
    print(f"  ✓ Analyst export blocked: {analyst_export.status_code} ({analyst_export.json()['detail']})")
    assert analyst_export.status_code == 403

    # Reviewer exports Markdown
    export_md = client.get(f"/api/investigations/{inv_id}/export?format=markdown", headers=rev_headers)
    assert export_md.status_code == 200
    print(f"  ✓ Reviewer Markdown export: {export_md.status_code} OK (length: {len(export_md.text)} chars)")
    assert "VERIDEX Executive Audit Report" in export_md.text

    # Reviewer exports JSON
    export_json = client.get(f"/api/investigations/{inv_id}/export?format=json", headers=rev_headers)
    assert export_json.status_code == 200
    assert export_json.json()["investigation"]["investigation_id"] == inv_id
    print(f"  ✓ Reviewer JSON export: {export_json.status_code} OK (ID: {export_json.json()['investigation']['investigation_id']})")

    # Verify ReportExporter reads directly from database
    direct_export = ReportExporter.export_as_json(db, inv_id)
    assert direct_export["investigation"]["investigation_id"] == inv_id
    print(f"  ✓ Direct DB query verification: ReportExporter read DB record directly")

    app.dependency_overrides.clear()
    db.close()

    print("\n" + "=" * 60)
    print("ALL 9 END-TO-END PHASES VERIFIED WITH DIRECT DB PERSISTENCE!")
    print("=" * 60)


if __name__ == "__main__":
    run_e2e_verification()
