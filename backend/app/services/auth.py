import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.passwords import hash_password, needs_rehash, verify_password, verify_totp
from app.core.security import decrypt
from app.models import AdminSession, AdminUser


class AuthError(Exception):
    """Wrong email, password or 2FA code (never says which)."""


class LockedError(AuthError):
    """Too many failed attempts for this account."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def normalize_email(email: str) -> str:
    return email.strip().lower()


async def authenticate(session: AsyncSession, email: str, password: str, otp: str | None) -> AdminUser:
    settings = get_settings()
    now = _now()
    user = await session.scalar(
        select(AdminUser).where(func.lower(AdminUser.email) == normalize_email(email))
    )

    if user is not None and user.locked_until is not None and _aware(user.locked_until) > now:
        raise LockedError()

    ok = verify_password(password, user.password_hash if user else None)
    if ok and user is not None and user.totp_secret_enc:
        ok = verify_totp(decrypt(user.totp_secret_enc), (otp or "").strip())

    if not ok or user is None or not user.is_active:
        if user is not None:
            user.failed_login_count = (user.failed_login_count or 0) + 1
            if user.failed_login_count >= settings.login_max_attempts:
                user.locked_until = now + timedelta(minutes=settings.login_lock_minutes)
                user.failed_login_count = 0
            await session.commit()
        raise AuthError()

    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    return user


async def create_session(
    session: AsyncSession, user: AdminUser, ip: str | None, user_agent: str | None
) -> str:
    now = _now()
    token = secrets.token_urlsafe(32)
    await session.execute(
        delete(AdminSession).where(AdminSession.user_id == user.id, AdminSession.expires_at < now)
    )
    session.add(AdminSession(
        user_id=user.id,
        token_hash=hash_token(token),
        expires_at=now + timedelta(hours=get_settings().session_ttl_hours),
        last_seen_at=now,
        ip_address=(ip or "")[:64] or None,
        user_agent=(user_agent or "")[:255] or None,
    ))
    await session.commit()
    return token


async def get_session_user(session: AsyncSession, token: str) -> AdminUser | None:
    row = await session.execute(
        select(AdminSession, AdminUser)
        .join(AdminUser, AdminUser.id == AdminSession.user_id)
        .where(AdminSession.token_hash == hash_token(token))
    )
    found = row.first()
    if found is None:
        return None
    admin_session, user = found
    now = _now()
    if _aware(admin_session.expires_at) <= now or not user.is_active:
        await session.delete(admin_session)
        await session.commit()
        return None
    if admin_session.last_seen_at is None or now - _aware(admin_session.last_seen_at) > timedelta(minutes=5):
        admin_session.last_seen_at = now
        await session.commit()
    return user


async def delete_session(session: AsyncSession, token: str) -> None:
    await session.execute(delete(AdminSession).where(AdminSession.token_hash == hash_token(token)))
    await session.commit()


async def delete_all_sessions(session: AsyncSession, user_id: int) -> None:
    await session.execute(delete(AdminSession).where(AdminSession.user_id == user_id))
    await session.commit()
