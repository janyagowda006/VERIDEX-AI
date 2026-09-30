from typing import Optional, List, Callable
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.core.auth import decode_access_token, get_password_hash
from app.models.business_data import Base
from app.models.user import User
from app.models.investigation import Investigation, InvestigationReview, InvestigationTurn

security_scheme = HTTPBearer(auto_error=False)

DEFAULT_USERS = [
    {
        "user_id": "usr_analyst_01",
        "email": "analyst@veridex.ai",
        "password": "password123",
        "full_name": "Alice Analyst",
        "role": "ANALYST"
    },
    {
        "user_id": "usr_reviewer_01",
        "email": "reviewer@veridex.ai",
        "password": "password123",
        "full_name": "Bob Reviewer",
        "role": "REVIEWER"
    },
    {
        "user_id": "usr_auditor_01",
        "email": "auditor@veridex.ai",
        "password": "password123",
        "full_name": "Carol Auditor",
        "role": "AUDITOR"
    },
    {
        "user_id": "usr_admin_01",
        "email": "admin@veridex.ai",
        "password": "password123",
        "full_name": "Dave Admin",
        "role": "ADMIN"
    }
]


def seed_default_users_if_needed(db: Session):
    """
    Ensures baseline default users exist in DB for manual/dev/testing ease.
    Dynamically creates tables on the session bind if not present.
    """
    try:
        bind = db.get_bind()
        Base.metadata.create_all(bind=bind)

        existing = db.query(User.user_id).filter(User.email == "analyst@veridex.ai").first()
        if not existing:
            sp = db.begin_nested()
            try:
                for u_data in DEFAULT_USERS:
                    if not db.query(User.user_id).filter(User.email == u_data["email"]).first():
                        new_user = User(
                            user_id=u_data["user_id"],
                            email=u_data["email"],
                            hashed_password=get_password_hash(u_data["password"]),
                            full_name=u_data["full_name"],
                            role=u_data["role"],
                            is_active=True
                        )
                        db.add(new_user)
                sp.commit()
                db.commit()
            except Exception:
                sp.rollback()
    except Exception:
        pass


def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    Extracts and verifies JWT token from Bearer header or Dev Mock Headers.
    """
    seed_default_users_if_needed(db)

    token = None
    if credentials and credentials.credentials:
        token = credentials.credentials
    else:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()

    # DEV MOCK AUTH & TEST FALLBACK
    mock_user_id = request.headers.get("X-Veridex-Mock-User-Id")
    mock_role = request.headers.get("X-Veridex-Mock-Role")
    no_auth_fallback = request.headers.get("X-Veridex-No-Auth-Fallback")

    env = getattr(request.app.state, "ENVIRONMENT", "development")

    if not token and env == "development" and not no_auth_fallback:
        if mock_user_id or mock_role:
            if mock_user_id:
                user = db.query(User).filter(User.user_id == mock_user_id).first()
            else:
                role_to_use = mock_role if mock_role in ["ANALYST", "REVIEWER", "AUDITOR", "ADMIN"] else "ANALYST"
                user = db.query(User).filter(User.role == role_to_use).first()
            if user and user.is_active:
                return user
        else:
            default_user = db.query(User).filter(User.role == "ADMIN").first()
            if default_user and default_user.is_active:
                return default_user

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(token)
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def require_roles(*allowed_roles: str):
    """
    Dependency generator for RBAC role checking.
    ADMIN role is automatically permitted on all endpoints unless explicitly restricted.
    """
    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role == "ADMIN" or current_user.role in allowed_roles:
            return current_user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User with role '{current_user.role}' is not authorized to access this resource."
        )
    return dependency
