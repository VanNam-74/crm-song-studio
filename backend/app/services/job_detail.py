import asyncio
import logging
from datetime import datetime, timezone
from string import ascii_uppercase

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.config import get_settings
from app.models import (
    AdminUser, EventLevel, GenerationStatus, JobEvent, JobStatus, LyricGeneration, LyricsStatus,
    MusicClip, MusicGeneration, OrderStatus, Site, SongJob, SongOrder,
)
from app.schemas.job_detail import (
    ClipOut, EventOut, JobAction, JobDetailOut, LyricDraftOut, LyricsUpdate, MusicGenerationOut,
    OrderDetail, SiteBrief,
)

logger = logging.getLogger(__name__)

CLOSED = (JobStatus.DONE, JobStatus.CANCELLED)
LYRIC_STEPS = {"generate_lyrics", "enqueue", "webhook"}

ACTIONS: dict[JobStatus, list[JobAction]] = {
    JobStatus.QUEUED: ["cancel"],
    JobStatus.GENERATING_LYRICS: ["cancel"],
    JobStatus.LYRICS_READY: ["save_lyrics", "approve_lyrics", "regenerate_lyrics", "cancel"],
    JobStatus.LYRICS_APPROVED: ["cancel"],
    JobStatus.GENERATING_MUSIC: ["cancel"],
    JobStatus.UPLOADING: ["cancel"],
    JobStatus.MUSIC_READY: ["select_clip", "confirm_take", "regenerate_music", "cancel"],
    JobStatus.READY: ["select_clip", "mark_done", "regenerate_music", "cancel"],
    JobStatus.DONE: ["reopen"],
    JobStatus.FAILED: ["retry", "regenerate_lyrics", "cancel"],
    JobStatus.CANCELLED: [],
}


class JobNotFound(Exception):
    pass


class JobActionError(Exception):
    pass


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _audio_url(key: str | None) -> str | None:
    base = get_settings().r2_public_base_url
    if not key or not base:
        return None
    return f"{base.rstrip('/')}/{key.lstrip('/')}"


def _wp_admin_url(site: Site, wp_order_id: int) -> str:
    return f"{site.base_url.rstrip('/')}/wp-admin/admin.php?page=wc-orders&action=edit&id={wp_order_id}"


async def _load(session: AsyncSession, job_id: int, lock: bool = False) -> SongJob:
    stmt = select(SongJob).where(SongJob.id == job_id)
    if lock:
        stmt = stmt.with_for_update()
    job = await session.scalar(stmt)
    if job is None:
        raise JobNotFound
    return job


def _require(job: SongJob, action: JobAction) -> None:
    if action not in ACTIONS.get(job.status, []):
        raise JobActionError(f"Cannot {action.replace('_', ' ')} while job is {job.status.value}")


def _event(session: AsyncSession, job: SongJob, step: str, message: str, actor: AdminUser | None,
           level: EventLevel = EventLevel.INFO, data: dict | None = None) -> None:
    session.add(JobEvent(job_id=job.id, step=step, message=message, level=level, data=data,
                         actor_id=actor.id if actor else None))


async def _enqueue(session: AsyncSession, job: SongJob, task_name: str, kwargs: dict) -> None:
    """Commit first, then push to Celery so the worker never reads stale rows."""
    await session.commit()
    if not get_settings().enqueue_tasks:
        return
    from app import tasks

    task = getattr(tasks, task_name)
    try:
        await asyncio.to_thread(task.apply_async, kwargs={"job_id": job.id, **kwargs},
                                priority=job.priority, retry=False)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Could not enqueue %s for job %s", task_name, job.id)
        _event(session, job, "enqueue", f"Could not queue {task_name}: {exc}", None, EventLevel.ERROR)
        await session.commit()


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

async def get_job_detail(session: AsyncSession, job_id: int) -> JobDetailOut:
    job = await _load(session, job_id)
    order = await session.get(SongOrder, job.order_id)
    site = await session.get(Site, job.site_id)

    users = {
        u.id: (u.full_name or u.email)
        for u in await session.scalars(
            select(AdminUser).where(AdminUser.id.in_(
                [i for i in (job.lyrics_approved_by_id, job.done_by_id) if i]
            ))
        )
    }

    drafts = [
        LyricDraftOut(
            id=g.id, no=i + 1, status=g.status, model=g.model, title=g.title, style=g.style,
            lyrics=g.lyrics, note=(g.raw_response or {}).get("admin_note"),
            input_tokens=g.input_tokens, output_tokens=g.output_tokens,
            error_message=g.error_message, created_at=g.created_at,
        )
        for i, g in enumerate(await session.scalars(
            select(LyricGeneration).where(LyricGeneration.job_id == job.id).order_by(LyricGeneration.id)
        ))
    ]

    gens = list(await session.scalars(
        select(MusicGeneration).where(MusicGeneration.job_id == job.id).order_by(MusicGeneration.id)
    ))
    clips_by_gen: dict[int, list[MusicClip]] = {}
    if gens:
        for c in await session.scalars(
            select(MusicClip).where(MusicClip.generation_id.in_([g.id for g in gens])).order_by(MusicClip.id)
        ):
            clips_by_gen.setdefault(c.generation_id, []).append(c)
    music = [
        MusicGenerationOut(
            id=g.id, no=i + 1, provider_type=g.provider_type, status=g.status, poll_count=g.poll_count,
            error_message=g.error_message, submitted_at=g.submitted_at, completed_at=g.completed_at,
            clips=[
                ClipOut(
                    id=c.id, label=ascii_uppercase[n % 26], status=c.status, duration_sec=c.duration_sec,
                    audio_url=_audio_url(c.r2_key), r2_key=c.r2_key, file_size=c.file_size,
                    mime_type=c.mime_type, admin_note=c.admin_note, is_selected=c.id == job.selected_clip_id,
                )
                for n, c in enumerate(clips_by_gen.get(g.id, []))
            ],
        )
        for i, g in enumerate(gens)
    ]

    actor = aliased(AdminUser)
    events = [
        EventOut(id=e.id, level=e.level, step=e.step, message=e.message, actor_name=name, created_at=e.created_at)
        for e, name in (await session.execute(
            select(JobEvent, func.coalesce(actor.full_name, actor.email))
            .outerjoin(actor, actor.id == JobEvent.actor_id)
            .where(JobEvent.job_id == job.id)
            .order_by(JobEvent.id.desc())
            .limit(100)
        )).all()
    ]

    due = _aware(job.due_at)
    return JobDetailOut(
        id=job.id, revision_no=job.revision_no, job_type=job.job_type, parent_job_id=job.parent_job_id,
        customer_feedback=job.customer_feedback, status=job.status, priority=job.priority, due_at=due,
        is_overdue=due < datetime.now(timezone.utc) and job.status not in CLOSED,
        error_step=job.error_step, error_message=job.error_message, retry_count=job.retry_count,
        final_title=job.final_title, final_style=job.final_style, final_lyrics=job.final_lyrics,
        lyrics_status=job.lyrics_status, lyrics_approved_by=users.get(job.lyrics_approved_by_id),
        lyrics_approved_at=job.lyrics_approved_at, selected_clip_id=job.selected_clip_id,
        done_at=job.done_at, done_by=users.get(job.done_by_id),
        created_at=job.created_at, updated_at=job.updated_at,
        site=SiteBrief(
            id=site.id, slug=site.slug, name=site.name, base_url=site.base_url,
            require_lyric_approval=site.require_lyric_approval, require_clip_selection=site.require_clip_selection,
        ),
        order=OrderDetail(
            id=order.id, wp_order_id=order.wp_order_id, order_number=order.order_number,
            customer_name=order.customer_name, customer_email=order.customer_email,
            package_name=order.package_name, delivery_option=order.delivery_option, paid_at=order.paid_at,
            status=order.status, wp_admin_url=_wp_admin_url(site, order.wp_order_id),
            story=(job.input_snapshot or {}).get("story") or {},
        ),
        drafts=drafts, music=music, events=events, actions=ACTIONS.get(job.status, []),
    )


# ---------------------------------------------------------------------------
# Actions (each returns nothing; the router re-reads the detail)
# ---------------------------------------------------------------------------

def _apply_lyrics(job: SongJob, data: LyricsUpdate) -> bool:
    changed = (data.title, data.style, data.lyrics) != (job.final_title, job.final_style, job.final_lyrics)
    job.final_title = data.title.strip()
    job.final_style = data.style.strip() if data.style else None
    job.final_lyrics = data.lyrics.strip()
    return changed


async def save_lyrics(session: AsyncSession, job_id: int, data: LyricsUpdate, actor: AdminUser) -> None:
    job = await _load(session, job_id, lock=True)
    _require(job, "save_lyrics")
    if _apply_lyrics(job, data):
        job.lyrics_status = LyricsStatus.EDITED
        _event(session, job, "lyrics", "Lyrics edited", actor)
    await session.commit()


async def approve_lyrics(session: AsyncSession, job_id: int, data: LyricsUpdate | None, actor: AdminUser) -> None:
    job = await _load(session, job_id, lock=True)
    _require(job, "approve_lyrics")
    if data is not None and _apply_lyrics(job, data):
        _event(session, job, "lyrics", "Lyrics edited", actor)
    if not (job.final_title and job.final_lyrics):
        raise JobActionError("Title and lyrics are required before approval")
    job.lyrics_status = LyricsStatus.APPROVED
    job.lyrics_approved_by_id = actor.id
    job.lyrics_approved_at = datetime.now(timezone.utc)
    job.status = JobStatus.LYRICS_APPROVED
    job.selected_clip_id = None
    _event(session, job, "lyrics", "Lyrics approved, queued for music", actor)
    await _enqueue(session, job, "generate_music", {})


async def regenerate_lyrics(session: AsyncSession, job_id: int, note: str | None, actor: AdminUser) -> None:
    job = await _load(session, job_id, lock=True)
    _require(job, "regenerate_lyrics")
    note = (note or "").strip() or None
    job.status = JobStatus.QUEUED
    job.lyrics_status = None
    job.error_step = job.error_message = None
    _event(session, job, "lyrics", f'Rewrite requested{": " + note if note else ""}', actor, data={"note": note})
    await _enqueue(session, job, "generate_lyrics", {"note": note})


async def select_clip(session: AsyncSession, job_id: int, clip_id: int, actor: AdminUser) -> None:
    job = await _load(session, job_id, lock=True)
    _require(job, "select_clip")
    clip = await session.scalar(
        select(MusicClip)
        .join(MusicGeneration, MusicGeneration.id == MusicClip.generation_id)
        .where(MusicClip.id == clip_id, MusicGeneration.job_id == job.id)
    )
    if clip is None:
        raise JobActionError("Clip does not belong to this job")
    if clip.status is not GenerationStatus.COMPLETE or not clip.r2_key:
        raise JobActionError("Clip is not uploaded yet")
    if job.selected_clip_id != clip.id:
        job.selected_clip_id = clip.id
        _event(session, job, "clip", f"Selected clip #{clip.id}", actor, data={"clip_id": clip.id})
    await session.commit()


async def confirm_take(session: AsyncSession, job_id: int, actor: AdminUser) -> None:
    job = await _load(session, job_id, lock=True)
    _require(job, "confirm_take")
    if job.selected_clip_id is None:
        raise JobActionError("Select a clip first")
    job.status = JobStatus.READY
    _event(session, job, "clip", "Take confirmed, ready to copy to CRM", actor)
    await session.commit()


async def regenerate_music(session: AsyncSession, job_id: int, actor: AdminUser) -> None:
    job = await _load(session, job_id, lock=True)
    _require(job, "regenerate_music")
    if job.lyrics_status is not LyricsStatus.APPROVED:
        raise JobActionError("Lyrics must be approved first")
    job.status = JobStatus.LYRICS_APPROVED
    job.selected_clip_id = None
    _event(session, job, "music", "New music generation requested", actor)
    await _enqueue(session, job, "generate_music", {})


async def mark_done(session: AsyncSession, job_id: int, actor: AdminUser) -> None:
    job = await _load(session, job_id, lock=True)
    _require(job, "mark_done")
    job.status = JobStatus.DONE
    job.done_at = datetime.now(timezone.utc)
    job.done_by_id = actor.id
    order = await session.get(SongOrder, job.order_id)
    if order.current_job_id == job.id:
        order.status = OrderStatus.DONE
    _event(session, job, "done", "Copied to CRM, job done", actor)
    await session.commit()


async def reopen(session: AsyncSession, job_id: int, actor: AdminUser) -> None:
    job = await _load(session, job_id, lock=True)
    _require(job, "reopen")
    job.status = JobStatus.READY
    job.done_at = job.done_by_id = None
    order = await session.get(SongOrder, job.order_id)
    if order.current_job_id == job.id:
        order.status = OrderStatus.ACTIVE
    _event(session, job, "done", "Job reopened", actor)
    await session.commit()


async def retry(session: AsyncSession, job_id: int, actor: AdminUser) -> None:
    job = await _load(session, job_id, lock=True)
    _require(job, "retry")
    step = job.error_step or ""
    music_step = job.lyrics_status is LyricsStatus.APPROVED and step not in LYRIC_STEPS
    job.retry_count += 1
    job.error_step = job.error_message = None
    if music_step:
        job.status = JobStatus.LYRICS_APPROVED
        task = "generate_music"
    else:
        job.status = JobStatus.QUEUED
        task = "generate_lyrics"
    _event(session, job, "retry", f"Retry from {step or 'start'} ({task})", actor)
    await _enqueue(session, job, task, {})


async def cancel(session: AsyncSession, job_id: int, actor: AdminUser) -> None:
    job = await _load(session, job_id, lock=True)
    _require(job, "cancel")
    job.status = JobStatus.CANCELLED
    _event(session, job, "cancel", "Job cancelled", actor, EventLevel.WARNING)
    await session.commit()