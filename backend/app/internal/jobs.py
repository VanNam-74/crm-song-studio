from collections.abc import Awaitable
from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, Query, status

from app.internal.deps import CanOperate, CurrentUser, DbSession
from app.schemas.job_detail import JobDetailOut, LyricsUpdate, RegenerateLyricsIn, SelectClipIn
from app.schemas.jobs import JobSort, JobsOut, StatusGroup
from app.services import job_detail as svc
from app.services.job_list import JobFilters, list_jobs

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=JobsOut)
async def get_jobs(
    session: DbSession,
    user: CurrentUser,
    status: StatusGroup = "all",
    site: str | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    sort: JobSort = "due",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> JobsOut:
    return await list_jobs(
        session,
        JobFilters(group=status, site=site, q=q, sort=sort, page=page, page_size=page_size),
    )


async def _detail(session, job_id: int) -> JobDetailOut:
    try:
        return await svc.get_job_detail(session, job_id)
    except svc.JobNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")


async def _run(session, job_id: int, action: Awaitable[None]) -> JobDetailOut:
    try:
        await action
    except svc.JobNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    except svc.JobActionError as exc:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))
    session.expire_all()
    return await _detail(session, job_id)


@router.get("/{job_id}", response_model=JobDetailOut)
async def get_job(job_id: int, session: DbSession, user: CurrentUser) -> JobDetailOut:
    return await _detail(session, job_id)


@router.patch("/{job_id}/lyrics", response_model=JobDetailOut)
async def save_lyrics(job_id: int, body: LyricsUpdate, session: DbSession, user: CanOperate) -> JobDetailOut:
    return await _run(session, job_id, svc.save_lyrics(session, job_id, body, user))


@router.post("/{job_id}/approve-lyrics", response_model=JobDetailOut)
async def approve_lyrics(
    job_id: int, session: DbSession, user: CanOperate, body: Annotated[LyricsUpdate | None, Body()] = None
) -> JobDetailOut:
    return await _run(session, job_id, svc.approve_lyrics(session, job_id, body, user))


@router.post("/{job_id}/regenerate-lyrics", response_model=JobDetailOut)
async def regenerate_lyrics(
    job_id: int, session: DbSession, user: CanOperate, body: Annotated[RegenerateLyricsIn | None, Body()] = None
) -> JobDetailOut:
    note = body.note if body else None
    return await _run(session, job_id, svc.regenerate_lyrics(session, job_id, note, user))


@router.post("/{job_id}/select-clip", response_model=JobDetailOut)
async def select_clip(job_id: int, body: SelectClipIn, session: DbSession, user: CanOperate) -> JobDetailOut:
    return await _run(session, job_id, svc.select_clip(session, job_id, body.clip_id, user))


@router.post("/{job_id}/confirm-take", response_model=JobDetailOut)
async def confirm_take(job_id: int, session: DbSession, user: CanOperate) -> JobDetailOut:
    return await _run(session, job_id, svc.confirm_take(session, job_id, user))


@router.post("/{job_id}/regenerate-music", response_model=JobDetailOut)
async def regenerate_music(job_id: int, session: DbSession, user: CanOperate) -> JobDetailOut:
    return await _run(session, job_id, svc.regenerate_music(session, job_id, user))


@router.post("/{job_id}/mark-done", response_model=JobDetailOut)
async def mark_done(job_id: int, session: DbSession, user: CanOperate) -> JobDetailOut:
    return await _run(session, job_id, svc.mark_done(session, job_id, user))


@router.post("/{job_id}/reopen", response_model=JobDetailOut)
async def reopen(job_id: int, session: DbSession, user: CanOperate) -> JobDetailOut:
    return await _run(session, job_id, svc.reopen(session, job_id, user))


@router.post("/{job_id}/retry", response_model=JobDetailOut)
async def retry(job_id: int, session: DbSession, user: CanOperate) -> JobDetailOut:
    return await _run(session, job_id, svc.retry(session, job_id, user))


@router.post("/{job_id}/cancel", response_model=JobDetailOut)
async def cancel(job_id: int, session: DbSession, user: CanOperate) -> JobDetailOut:
    return await _run(session, job_id, svc.cancel(session, job_id, user))