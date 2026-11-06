"""Password hashing (Argon2id) and TOTP 2FA helpers."""
import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()

# Used when the email does not exist, so a wrong email takes as long as a wrong password.
_DUMMY_HASH = _hasher.hash("not-a-real-password")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def new_totp_secret() -> str:
    return pyotp.random_base32()


def totp_uri(secret: str, email: str, issuer: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=issuer)


def verify_totp(secret: str, code: str | None) -> bool:
    if not code or not code.isdigit() or len(code) != 6:
        return False
    return pyotp.TOTP(secret).verify(code, valid_window=1)
