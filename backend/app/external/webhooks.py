import json
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session
from app.models import Site, WebhookLog
from app.schemas.webhook import WebhookPayload, WebhookResponse
from app.core.security import SignatureError, decrypt, verify_signature
from backend.app.services.job_list import create_job_from_order, enqueue_generate_lyrics

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _safe_json(body: bytes) -> dict | None:
    try:
        data = json.loads(body)
        return data if isinstance(data, dict) else None
    except ValueError:
        return None


@router.post("/{slug}", response_model=WebhookResponse)
async def receive_webhook(
    slug: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    x_tnm_event: str | None = Header(default=None),
    x_tnm_timestamp: str | None = Header(default=None),
    x_tnm_signature: str | None = Header(default=None),
) -> WebhookResponse:
    body = await request.body()

    site = await session.scalar(select(Site).where(Site.slug == slug))
    if site is None or not site.is_active:
        raise HTTPException(status_code=404, detail="Unknown site")

    # 1. Signature (on the raw body, before any parsing)
    try:
        verify_signature(
            decrypt(site.webhook_secret_enc),
            x_tnm_timestamp,
            x_tnm_signature,
            body,
            get_settings().webhook_tolerance_seconds,
        )
    except SignatureError as exc:
        session.add(WebhookLog(
            site_id=site.id, event_type=(x_tnm_event or "unknown")[:50],
            signature_valid=False, error_message=str(exc),
        ))
        await session.commit()
        logger.warning("Rejected webhook for %s: %s", slug, exc)
        raise HTTPException(status_code=401, detail="Invalid signature")

    # 2. Payload
    try:
        payload = WebhookPayload.model_validate_json(body)
    except ValidationError as exc:
        session.add(WebhookLog(
            site_id=site.id, event_type=(x_tnm_event or "unknown")[:50], payload=_safe_json(body),
            signature_valid=True, error_message=str(exc)[:2000],
        ))
        await session.commit()
        raise HTTPException(status_code=422, detail="Invalid payload")

    # 3. Duplicate delivery (WordPress retried the same send)
    log = WebhookLog(
        site_id=site.id, delivery_id=payload.delivery_id, event_type=payload.event,
        payload=_safe_json(body), signature_valid=True,
    )
    session.add(log)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        return WebhookResponse(status="duplicate", message="Delivery already processed")

    if payload.event == "ping":
        log.processed = True
        await session.commit()
        return WebhookResponse(status="pong", message=f"Connected to {site.name}")

    # 4. order.paid -> order + job
    job, created = await create_job_from_order(session, site, payload.order)
    log.processed = True
    log.job_id = job.id
    await session.commit()

    if created:
        await enqueue_generate_lyrics(session, job)
        return WebhookResponse(status="created", job_id=job.id)
    return WebhookResponse(status="exists", job_id=job.id, message="Order already has a job")
