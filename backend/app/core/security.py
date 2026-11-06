"""Webhook signature verification and encryption of stored secrets."""
import hashlib
import hmac
import secrets
import time

from cryptography.fernet import Fernet

from app.core.config import get_settings


class SignatureError(Exception):
    pass


def _fernet() -> Fernet:
    return Fernet(get_settings().fernet_key.encode())


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    return _fernet().decrypt(value.encode()).decode()


def new_secret() -> str:
    return secrets.token_urlsafe(32)


def compute_signature(secret: str, timestamp: str, body: bytes) -> str:
    """sha256=HMAC(secret, "<timestamp>.<raw body>") - must match the WordPress plugin."""
    message = timestamp.encode() + b"." + body
    return "sha256=" + hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def verify_signature(
    secret: str,
    timestamp: str | None,
    signature: str | None,
    body: bytes,
    tolerance: int,
    now: int | None = None,
) -> None:
    if not timestamp or not signature:
        raise SignatureError("Missing signature headers")
    try:
        ts = int(timestamp)
    except ValueError as exc:
        raise SignatureError("Invalid timestamp") from exc
    now = int(time.time()) if now is None else now
    if abs(now - ts) > tolerance:
        raise SignatureError("Timestamp outside tolerance")
    expected = compute_signature(secret, timestamp, body)
    if not hmac.compare_digest(expected, signature):
        raise SignatureError("Signature mismatch")
