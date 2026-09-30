import hashlib
import hmac
import base64
import json
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from fastapi import HTTPException, status
from app.core.config import settings

# PBKDF2 Password Hashing
SALT_BYTES = 16
ITERATIONS = 100000

def get_password_hash(password: str) -> str:
    """
    Generates a secure PBKDF2-HMAC-SHA256 hash formatted as salt_hex:hash_hex.
    """
    import os
    salt = os.urandom(SALT_BYTES)
    derived = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, ITERATIONS)
    return f"{salt.hex()}:{derived.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plain password against a stored PBKDF2 salt_hex:hash_hex password string.
    """
    try:
        if ":" not in hashed_password:
            return False
        salt_hex, hash_hex = hashed_password.split(":", 1)
        salt = bytes.fromhex(salt_hex)
        expected_hash = bytes.fromhex(hash_hex)
        derived = hashlib.pbkdf2_hmac('sha256', plain_password.encode('utf-8'), salt, ITERATIONS)
        return hmac.compare_digest(derived, expected_hash)
    except Exception:
        return False


def _b64encode_url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('utf-8')


def _b64decode_url(data_str: str) -> bytes:
    padding = '=' * (4 - (len(data_str) % 4))
    if len(padding) == 4:
        padding = ''
    return base64.urlsafe_b64decode(data_str + padding)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Creates a base64url HMAC-SHA256 (HS256) JWT access token.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=getattr(settings, 'JWT_ACCESS_TOKEN_EXPIRE_MINUTES', 1440))
    
    to_encode.update({"exp": int(expire.timestamp())})

    header = {"alg": "HS256", "typ": "JWT"}

    header_bytes = json.dumps(header, separators=(',', ':')).encode('utf-8')
    payload_bytes = json.dumps(to_encode, separators=(',', ':')).encode('utf-8')

    encoded_header = _b64encode_url(header_bytes)
    encoded_payload = _b64encode_url(payload_bytes)

    signature_input = f"{encoded_header}.{encoded_payload}".encode('utf-8')
    secret = (getattr(settings, 'JWT_SECRET', None) or "veridex_secret_key_phase_95h_jwt_auth_key").encode('utf-8')
    signature = hmac.new(secret, signature_input, hashlib.sha256).digest()
    encoded_signature = _b64encode_url(signature)

    return f"{encoded_header}.{encoded_payload}.{encoded_signature}"


def decode_access_token(token: str) -> dict:
    """
    Decodes and verifies a JWT token string.
    Raises HTTPException(401) on invalid/malformed/expired token.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    parts = token.split(".")
    if len(parts) != 3:
        raise credentials_exception

    encoded_header, encoded_payload, encoded_signature = parts

    # Verify signature
    signature_input = f"{encoded_header}.{encoded_payload}".encode('utf-8')
    secret = (getattr(settings, 'JWT_SECRET', None) or "veridex_secret_key_phase_95h_jwt_auth_key").encode('utf-8')
    expected_signature = hmac.new(secret, signature_input, hashlib.sha256).digest()
    
    try:
        actual_signature = _b64decode_url(encoded_signature)
        if not hmac.compare_digest(expected_signature, actual_signature):
            raise credentials_exception
    except Exception:
        raise credentials_exception

    # Decode payload
    try:
        payload_bytes = _b64decode_url(encoded_payload)
        payload = json.loads(payload_bytes.decode('utf-8'))
    except Exception:
        raise credentials_exception

    # Verify expiration
    exp = payload.get("exp")
    if not exp or time.time() > exp:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload
