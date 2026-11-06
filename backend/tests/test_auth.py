import asyncio
from datetime import datetime, timedelta, timezone

import pyotp
import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from tests.conftest import DB_FILE
from app.core.config import get_settings
from app.core.db import SessionLocal, engine
from app.core.passwords import hash_password
from app.core.security import encrypt
from app.internal.deps import AdminOnly
from app.main_external import app as external_app
from app.main_internal import app
from app.models import AdminSession, AdminUser, Base, UserRole

PW = "correct horse battery"
TOTP_SECRET = pyotp.random_base32()

probe = APIRouter(prefix="/api/test")


@probe.get("/admin-only")
async def admin_only(user: AdminOnly):
    return {"ok": user.email}


app.include_router(probe)


async def _setup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as s:
        s.add_all([
            AdminUser(email="admin@studio.test", full_name="Admin", role=UserRole.ADMIN, password_hash=hash_password(PW)),
            AdminUser(email="op@studio.test", role=UserRole.OPERATOR, password_hash=hash_password(PW)),
            AdminUser(email="2fa@studio.test", role=UserRole.ADMIN, password_hash=hash_password(PW),
                      totp_secret_enc=encrypt(TOTP_SECRET)),
            AdminUser(email="off@studio.test", role=UserRole.ADMIN, password_hash=hash_password(PW), is_active=False),
        ])
        await s.commit()


def q(stmt):
    async def run():
        async with SessionLocal() as s:
            return await s.scalar(stmt)
    return asyncio.run(run())


@pytest.fixture(autouse=True)
def fresh_db():
    asyncio.run(_setup())
    yield
    DB_FILE.unlink(missing_ok=True)


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def login(client, email="admin@studio.test", password=PW, otp=None):
    return client.post("/api/auth/login", json={"email": email, "password": password, "otp": otp})


def test_me_requires_login(client):
    assert client.get("/api/auth/me").status_code == 401


def test_login_sets_httponly_cookie_and_me_works(client):
    r = login(client, email="  ADMIN@studio.test ")
    assert r.status_code == 200, r.text
    assert r.json() == {"id": 1, "email": "admin@studio.test", "full_name": "Admin", "role": "admin"}
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie and "path=/api" in cookie
    assert client.get("/api/auth/me").json()["email"] == "admin@studio.test"
    token = client.cookies.get(get_settings().session_cookie_name)
    stored = q(select(AdminSession.token_hash))
    assert token and stored and stored != token  # only the hash is stored


def test_wrong_password_and_unknown_email_look_the_same(client):
    a = login(client, password="nope")
    b = login(client, email="ghost@studio.test")
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json()


def test_inactive_user_cannot_login(client):
    assert login(client, email="off@studio.test").status_code == 401


def test_lockout_after_max_attempts(client):
    for _ in range(get_settings().login_max_attempts):
        assert login(client, password="bad").status_code == 401
    assert login(client).status_code == 429  # even the right password is refused while locked
    locked = q(select(AdminUser.locked_until).where(AdminUser.email == "admin@studio.test"))
    assert locked is not None


def test_totp_required_when_enabled(client):
    assert login(client, email="2fa@studio.test").status_code == 401
    assert login(client, email="2fa@studio.test", otp="000000").status_code in (401,)
    code = pyotp.TOTP(TOTP_SECRET).now()
    assert login(client, email="2fa@studio.test", otp=code).status_code == 200


def test_logout_invalidates_session(client):
    login(client)
    token = client.cookies.get(get_settings().session_cookie_name)
    assert client.post("/api/auth/logout").status_code == 204
    assert q(select(func.count()).select_from(AdminSession)) == 0
    client.cookies.set(get_settings().session_cookie_name, token, path="/api")
    assert client.get("/api/auth/me").status_code == 401  # stolen old cookie is useless


def test_expired_session_rejected(client):
    login(client)

    async def expire():
        async with SessionLocal() as s:
            sess = await s.scalar(select(AdminSession))
            sess.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
            await s.commit()
    asyncio.run(expire())
    assert client.get("/api/auth/me").status_code == 401


def test_role_guard(client):
    login(client, email="op@studio.test")
    assert client.get("/api/test/admin-only").status_code == 403
    client.post("/api/auth/logout")
    login(client)
    assert client.get("/api/test/admin-only").json() == {"ok": "admin@studio.test"}


def test_external_app_has_no_admin_api_or_docs():
    with TestClient(external_app) as c:
        assert c.post("/api/auth/login", json={}).status_code == 404
        assert c.get("/docs").status_code == 404
        assert c.get("/openapi.json").status_code == 404
