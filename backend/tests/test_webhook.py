import asyncio
import json
import time
import uuid
from datetime import datetime, timedelta, timezone

from tests.conftest import DB_FILE  # noqa: E402  (env is set in conftest)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import func, select  # noqa: E402

from app.core.db import SessionLocal, engine  # noqa: E402
from app.main_external import app  # noqa: E402
from app.models import Base, JobEvent, Site, SongJob, SongOrder, WebhookLog  # noqa: E402
from app.core.security import compute_signature, encrypt  # noqa: E402

SECRET = "test-secret-123"
URL = "/webhooks/heartintosong"

async def _setup() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as s:
        s.add(Site(name="Heart Into Song", slug="heartintosong", base_url="https://heartintosong.com",
                   webhook_secret_enc=encrypt(SECRET)))
        s.add(Site(name="Old site", slug="oldsite", base_url="https://old.example.com",
                   webhook_secret_enc=encrypt(SECRET), is_active=False))
        await s.commit()

async def _scalar(stmt):
    async with SessionLocal() as s:
        return await s.scalar(stmt)

def q(stmt):
    return asyncio.run(_scalar(stmt))

@pytest.fixture(autouse=True)
def fresh_db():
    asyncio.run(_setup())
    yield
    DB_FILE.unlink(missing_ok=True)

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

def order(order_id=10482, delivery_option="1_day", paid_at=None):
    return {
        "id": order_id, "number": str(order_id), "status": "processing",
        "paid_at": paid_at or "2026-10-31T04:00:00+00:00",
        "customer": {"name": "Daniel W.", "email": "d@example.com"},
        "package": "Custom Song", "delivery_option": delivery_option,
        "items": [{"product_id": 1, "name": "Custom Song", "quantity": 1, "meta": {"Delivery": "1 Day"}}],
        "story": {"tnm_recipient_name": "Margaret", "tnm_story": "Lake Tahoe, 1985"},
    }

def send(client, payload, secret=SECRET, ts=None, url=URL, raw=None):
    body = raw if raw is not None else json.dumps(payload).encode()
    ts = str(ts if ts is not None else int(time.time()))
    headers = {"Content-Type": "application/json", "X-TNM-Event": payload.get("event", "x"),
               "X-TNM-Timestamp": ts, "X-TNM-Signature": compute_signature(secret, ts, body)}
    return client.post(url, content=body, headers=headers)

def paid(order_payload, delivery_id=None):
    return {"event": "order.paid", "delivery_id": delivery_id or str(uuid.uuid4()), "order": order_payload}

def test_ping(client):
    r = send(client, {"event": "ping", "delivery_id": str(uuid.uuid4())})
    assert r.status_code == 200
    assert r.json()["status"] == "pong"

def test_order_paid_creates_job_with_due_date(client):
    r = send(client, paid(order(delivery_option="1_day")))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "created"

    job = q(select(SongJob).where(SongJob.id == body["job_id"]))
    assert job.status.value == "queued"
    assert job.priority == 9
    assert job.input_snapshot["story"]["tnm_recipient_name"] == "Margaret"
    paid_at = datetime(2026, 10, 31, 4, tzinfo=timezone.utc)
    due = job.due_at if job.due_at.tzinfo else job.due_at.replace(tzinfo=timezone.utc)
    assert due == paid_at + timedelta(hours=24)

    o = q(select(SongOrder).where(SongOrder.id == job.order_id))
    assert o.current_job_id == job.id and o.delivery_option.value == "1_day"
    assert q(select(func.count()).select_from(JobEvent).where(JobEvent.job_id == job.id)) == 1

def test_three_day_and_missing_package_default(client):
    r1 = send(client, paid(order(order_id=1, delivery_option="3_day")))
    r2 = send(client, paid(order(order_id=2, delivery_option=None)))
    j1 = q(select(SongJob).where(SongJob.id == r1.json()["job_id"]))
    j2 = q(select(SongJob).where(SongJob.id == r2.json()["job_id"]))
    assert j1.priority == 5
    due1 = j1.due_at if j1.due_at.tzinfo else j1.due_at.replace(tzinfo=timezone.utc)
    assert due1 == datetime(2026, 10, 31, 4, tzinfo=timezone.utc) + timedelta(hours=72)
    # package not detected -> default 3_day + a warning event
    assert q(select(func.count()).select_from(JobEvent)
             .where(JobEvent.job_id == j2.id, JobEvent.level == "warning")) == 1

def test_same_delivery_is_duplicate(client):
    p = paid(order(), delivery_id="11111111-aaaa")
    assert send(client, p).json()["status"] == "created"
    r = send(client, p)
    assert r.status_code == 200 and r.json()["status"] == "duplicate"
    assert q(select(func.count()).select_from(SongJob)) == 1

def test_resend_same_order_returns_existing_job(client):
    first = send(client, paid(order())).json()
    second = send(client, paid(order())).json()  # new delivery_id, same WP order
    assert second["status"] == "exists" and second["job_id"] == first["job_id"]
    assert q(select(func.count()).select_from(SongJob)) == 1

def test_bad_signature_rejected_and_logged(client):
    r = send(client, paid(order()), secret="wrong")
    assert r.status_code == 401
    assert q(select(func.count()).select_from(SongJob)) == 0
    log = q(select(WebhookLog))
    assert log.signature_valid is False and log.delivery_id is None

def test_tampered_body_rejected(client):
    p = paid(order())
    body = json.dumps(p).encode()
    ts = str(int(time.time()))
    sig = compute_signature(SECRET, ts, body)
    tampered = body.replace(b"Margaret", b"Mallory")
    r = client.post(URL, content=tampered, headers={"X-TNM-Timestamp": ts, "X-TNM-Signature": sig})
    assert r.status_code == 401

def test_old_timestamp_rejected(client):
    r = send(client, paid(order()), ts=int(time.time()) - 3600)
    assert r.status_code == 401

def test_missing_order_is_422(client):
    r = send(client, {"event": "order.paid", "delivery_id": str(uuid.uuid4())})
    assert r.status_code == 422

def test_unknown_or_inactive_site_404(client):
    assert send(client, {"event": "ping", "delivery_id": str(uuid.uuid4())}, url="/webhooks/nope").status_code == 404
    assert send(client, {"event": "ping", "delivery_id": str(uuid.uuid4())}, url="/webhooks/oldsite").status_code == 404
