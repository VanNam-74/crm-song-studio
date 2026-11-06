from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.models import DeliveryOption, JobStatus, JobType

StatusGroup = Literal["all", "review", "pick", "progress", "ready", "done", "failed", "overdue"]
JobSort = Literal["due", "updated", "created"]


class JobOut(BaseModel):
    id: int
    order_id: int
    order_number: str
    wp_order_id: int
    site_slug: str
    site_name: str
    customer_name: str | None
    customer_email: str | None
    package_name: str | None
    delivery_option: DeliveryOption
    job_type: JobType
    revision_no: int
    status: JobStatus
    status_group: StatusGroup
    title: str | None
    priority: int
    due_at: datetime
    is_overdue: bool
    error_step: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class JobsOut(BaseModel):
    items: list[JobOut]
    total: int
    page: int
    page_size: int
    counts: dict[StatusGroup, int]