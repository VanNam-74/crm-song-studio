from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import JobStatus, LyricGeneration, Site, SongJob, SongOrder
from app.schemas.jobs import JobOut, JobSort, JobsOut, StatusGroup

GROUP_STATUSES: dict[str, tuple[JobStatus, ...]] = {
    "review": (JobStatus.LYRICS_READY,),
    "pick": (JobStatus.MUSIC_READY,),
    "progress": (
        JobStatus.QUEUED,
        JobStatus.GENERATING_LYRICS,
        JobStatus.LYRICS_APPROVED,
        JobStatus.GENERATING_MUSIC,
        JobStatus.UPLOADING,
    ),
    "ready": (JobStatus.READY,),
    "done": (JobStatus.DONE,),
    "failed": (JobStatus.FAILED,),
}

CLOSED = (JobStatus.DONE, JobStatus.CANCELLED)

STATUS_TO_GROUP = {s: g for g, statuses in GROUP_STATUSES.items() for s in statuses}


@dataclass
class JobFilters:
    group: StatusGroup = "all"
    site: str | None = None
    q: str | None = None
    sort: JobSort = "due"
    page: int = 1
    page_size: int = 25


def _latest_title():
    return (
        select(LyricGeneration.title)
        .where(LyricGeneration.job_id == SongJob.id, LyricGeneration.title.is_not(None))
        .order_by(LyricGeneration.id.desc())
        .limit(1)
        .correlate(SongJob)
        .scalar_subquery()
    )


def _overdue(now: datetime):
    return and_(SongJob.due_at < now, SongJob.status.not_in(CLOSED))


async def list_jobs(session: AsyncSession, f: JobFilters) -> JobsOut:
    now = datetime.now(timezone.utc)
    title = func.coalesce(SongJob.final_title, _latest_title())

    base = []
    if f.site:
        base.append(Site.slug == f.site)
    if f.q and f.q.strip():
        like = f"%{f.q.strip()}%"
        base.append(
            or_(
                SongOrder.order_number.ilike(like),
                SongOrder.customer_name.ilike(like),
                SongOrder.customer_email.ilike(like),
                title.ilike(like),
            )
        )

    def joined(stmt):
        return stmt.join(SongOrder, SongOrder.id == SongJob.order_id).join(Site, Site.id == SongJob.site_id)

    count_rows = await session.execute(
        joined(select(SongJob.status, func.count()).select_from(SongJob)).where(*base).group_by(SongJob.status)
    )
    counts: dict[str, int] = {g: 0 for g in ("all", *GROUP_STATUSES, "overdue")}
    for status, n in count_rows.all():
        counts["all"] += n
        group = STATUS_TO_GROUP.get(status)
        if group:
            counts[group] += n
    counts["overdue"] = await session.scalar(
        joined(select(func.count()).select_from(SongJob)).where(*base, _overdue(now))
    ) or 0

    where = list(base)
    if f.group == "overdue":
        where.append(_overdue(now))
    elif f.group != "all":
        where.append(SongJob.status.in_(GROUP_STATUSES[f.group]))

    if f.sort == "updated":
        order_by = (SongJob.updated_at.desc(), SongJob.id.desc())
    elif f.sort == "created":
        order_by = (SongJob.created_at.desc(), SongJob.id.desc())
    else:
        closed_last = case((SongJob.status.in_(CLOSED), 1), else_=0)
        order_by = (closed_last, SongJob.due_at.asc(), SongJob.priority.desc(), SongJob.id)

    total = counts[f.group]
    rows = await session.execute(
        joined(select(SongJob, SongOrder, Site, title.label("title")).select_from(SongJob))
        .where(*where)
        .order_by(*order_by)
        .offset((f.page - 1) * f.page_size)
        .limit(f.page_size)
    )

    items = []
    for job, order, site, job_title in rows.all():
        due = job.due_at if job.due_at.tzinfo else job.due_at.replace(tzinfo=timezone.utc)
        items.append(
            JobOut(
                id=job.id,
                order_id=order.id,
                order_number=order.order_number,
                wp_order_id=order.wp_order_id,
                site_slug=site.slug,
                site_name=site.name,
                customer_name=order.customer_name,
                customer_email=order.customer_email,
                package_name=order.package_name,
                delivery_option=order.delivery_option,
                job_type=job.job_type,
                revision_no=job.revision_no,
                status=job.status,
                status_group=STATUS_TO_GROUP.get(job.status, "all"),
                title=job_title,
                priority=job.priority,
                due_at=due,
                is_overdue=due < now and job.status not in CLOSED,
                error_step=job.error_step,
                error_message=job.error_message,
                created_at=job.created_at,
                updated_at=job.updated_at,
            )
        )

    return JobsOut(items=items, total=total, page=f.page, page_size=f.page_size, counts=counts)