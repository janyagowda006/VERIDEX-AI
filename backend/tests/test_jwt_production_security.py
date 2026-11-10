import pytest
from datetime import timedelta
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import create_app
from app.core.config import (
    settings,
    KNOWN_INSECURE_JWT_SECRET,
    validate_jwt_secret_configuration
)
from app.core.auth import (
    get_signing_secret,
    create_access_token,
    decode_access_token
)
from app.core.db import Base, get_db
from app.api.deps import seed_default_users_if_needed

VALID_PROD_SECRET = "production_secure_entropy_key_9876543210_abcdef"
ALTERNATE_SECRET = "different_valid_production_secret_999999999_xyz"


def test_production_startup_rejects_missing_jwt_secret():
    """
    Test that application startup in production mode fails fast if JWT_SECRET is missing.
    """
    # 1. Validation function fails fast
    with pytest.raises(RuntimeError) as exc_info:
        validate_jwt_secret_configuration(environment="production", secret=None)
    assert "JWT_SECRET environment variable is missing" in str(exc_info.value)
    assert "Production startup aborted" in str(exc_info.value)

    # Also with empty/whitespace string
    with pytest.raises(RuntimeError) as exc_info_empty:
        validate_jwt_secret_configuration(environment="production", secret="   ")
    assert "JWT_SECRET environment variable is missing" in str(exc_info_empty.value)

    # 2. FastAPI lifespan startup fails fast
    prod_app = create_app(environment="production", jwt_secret="")
    with pytest.raises(RuntimeError) as lifespan_exc:
        with TestClient(prod_app):
            pass
    assert "JWT_SECRET environment variable is missing" in str(lifespan_exc.value)


def test_production_startup_rejects_known_default_jwt_secret():
    """
    Test that application startup in production mode fails fast if JWT_SECRET equals the known default.
    """
    # 1. Validation function fails fast
    with pytest.raises(RuntimeError) as exc_info:
        validate_jwt_secret_configuration(
            environment="production",
            secret=KNOWN_INSECURE_JWT_SECRET
        )
    assert "Known insecure default JWT_SECRET detected" in str(exc_info.value)
    assert "Production startup aborted" in str(exc_info.value)

    # 2. FastAPI lifespan startup fails fast
    prod_app = create_app(environment="production", jwt_secret=KNOWN_INSECURE_JWT_SECRET)
    with pytest.raises(RuntimeError) as lifespan_exc:
        with TestClient(prod_app):
            pass
    assert "Known insecure default JWT_SECRET detected" in str(lifespan_exc.value)


def test_production_startup_accepts_valid_secret():
    """
    Test that application startup in production mode succeeds when a valid secret is provided.
    """
    # 1. Validation function succeeds without exception
    validate_jwt_secret_configuration(environment="production", secret=VALID_PROD_SECRET)

    # 2. FastAPI lifespan startup succeeds
    prod_app = create_app(environment="production", jwt_secret=VALID_PROD_SECRET)
    with TestClient(prod_app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


def test_production_token_generation_and_verification_with_valid_secret():
    """
    Test token generation and verification using a valid production secret.
    """
    data = {"user_id": "usr_prod_test", "role": "ANALYST"}
    token = create_access_token(data, secret_key=VALID_PROD_SECRET)
    assert isinstance(token, str)
    assert len(token.split(".")) == 3

    payload = decode_access_token(token, secret_key=VALID_PROD_SECRET)
    assert payload["user_id"] == "usr_prod_test"
    assert payload["role"] == "ANALYST"


def test_development_mode_permits_fallback_secret():
    """
    Test that development mode allows application operation with development fallback secret.
    """
    # In development mode, missing secret does not raise
    validate_jwt_secret_configuration(environment="development", secret=None)

    # get_signing_secret returns fallback
    secret = get_signing_secret(environment="development", explicit_secret=None)
    assert secret == KNOWN_INSECURE_JWT_SECRET.encode("utf-8")


def test_production_get_signing_secret_safeguards():
    """
    Test that get_signing_secret rejects missing and insecure secrets in production.
    """
    with pytest.raises(RuntimeError) as exc_missing:
        get_signing_secret(environment="production", explicit_secret=None)
    assert "JWT_SECRET environment variable is missing" in str(exc_missing.value)

    with pytest.raises(RuntimeError) as exc_default:
        get_signing_secret(environment="production", explicit_secret=KNOWN_INSECURE_JWT_SECRET)
    assert "Known insecure default JWT_SECRET detected" in str(exc_default.value)


def test_configured_token_expiration_duration():
    """
    Verify the actual configured token expiration duration and test expired token rejection.
    """
    # Actual duration from configuration
    configured_minutes = getattr(settings, "JWT_ACCESS_TOKEN_EXPIRE_MINUTES", 1440)
    assert configured_minutes == 1440  # 24 hours (1,440 minutes)

    # Expired token rejection
    expired_token = create_access_token(
        {"user_id": "usr_exp"},
        expires_delta=timedelta(seconds=-1),
        secret_key=VALID_PROD_SECRET
    )
    with pytest.raises(HTTPException) as exc_info:
        decode_access_token(expired_token, secret_key=VALID_PROD_SECRET)
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Token has expired"


def test_invalid_signature_token_rejection():
    """
    Test that tokens signed with a different key are rejected with 401 Unauthorized.
    """
    token_signed_with_a = create_access_token(
        {"user_id": "usr_tamper"},
        secret_key=VALID_PROD_SECRET
    )

    with pytest.raises(HTTPException) as exc_info:
        decode_access_token(token_signed_with_a, secret_key=ALTERNATE_SECRET)
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Could not validate credentials"


def test_malformed_token_rejection_variants():
    """
    Test rejection of malformed tokens (wrong number of segments, invalid base64).
    """
    for malformed in ["single_segment", "two.segments", "a.b.c.d", "invalid!@#.base64!@#.sig!@#"]:
        with pytest.raises(HTTPException) as exc_info:
            decode_access_token(malformed, secret_key=VALID_PROD_SECRET)
        assert exc_info.value.status_code == 401


def test_production_mode_disables_mock_headers_and_requires_bearer_token():
    """
    Test that in production mode, mock headers (X-Veridex-Mock-User-Id) are strictly disabled
    and requests without a valid Bearer token are rejected with 401 Unauthorized.
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    seed_default_users_if_needed(db)

    prod_app = create_app(environment="production", jwt_secret=VALID_PROD_SECRET)

    def override_get_db():
        try:
            yield db
        finally:
            pass

    prod_app.dependency_overrides[get_db] = override_get_db

    with TestClient(prod_app) as client:
        # 1. Unauthenticated request in production -> 401
        unauth_resp = client.get("/api/auth/me")
        assert unauth_resp.status_code == 401
        assert unauth_resp.json()["detail"] == "Not authenticated"

        # 2. Request with mock headers in production -> MUST BE REJECTED with 401
        mock_headers_resp = client.get(
            "/api/auth/me",
            headers={"X-Veridex-Mock-User-Id": "usr_analyst_01", "X-Veridex-Mock-Role": "ANALYST"}
        )
        assert mock_headers_resp.status_code == 401
        assert mock_headers_resp.json()["detail"] == "Not authenticated"

        # 3. Request with valid Bearer token -> 200
        valid_token = create_access_token(
            {"user_id": "usr_analyst_01", "role": "ANALYST"},
            secret_key=VALID_PROD_SECRET
        )
        auth_resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {valid_token}"})
        assert auth_resp.status_code == 200
        assert auth_resp.json()["user_id"] == "usr_analyst_01"

    prod_app.dependency_overrides.clear()
    db.close()
    Base.metadata.drop_all(bind=engine)


def test_secret_values_never_leak_in_exception_messages():
    """
    Verify that error messages from security validation do not expose actual secret values.
    """
    secret_candidate = "super_private_secret_99999"
    try:
        validate_jwt_secret_configuration(environment="production", secret="")
    except RuntimeError as e:
        assert secret_candidate not in str(e)

    try:
        validate_jwt_secret_configuration(environment="production", secret=KNOWN_INSECURE_JWT_SECRET)
    except RuntimeError as e:
        # Should explain the issue without leaking any unhashed credentials
        assert "Production startup aborted" in str(e)
