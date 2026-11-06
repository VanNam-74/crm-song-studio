from typing import Annotated

from fastapi import APIRouter, Query

from app.internal.deps import CurrentUser, DbSession
from app.schemas.jobs import JobSort, JobsOut, StatusGroup
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