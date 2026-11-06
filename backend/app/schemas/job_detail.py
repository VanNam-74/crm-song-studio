from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.models import (
    DeliveryOption, EventLevel, GenerationStatus, JobStatus, JobType, LyricsStatus,
    MusicProviderType, OrderStatus,
)

JobAction = Literal[
    "save_lyrics",
    "approve_lyrics",
    "regenerate_lyrics",
    "select_clip",
    "confirm_take",
    "regenerate_music",
    "mark_done",
    "reopen",
    "retry",
    "cancel",
]


class SiteBrief(BaseModel):
    id: int
    slug: str
    name: str
    base_url: str
    require_lyric_approval: bool
    require_clip_selection: bool


class OrderDetail(BaseModel):
    id: int
    wp_order_id: int
    order_number: str
    customer_name: str | None
    customer_email: str | None
    package_name: str | None
    delivery_option: DeliveryOption
    paid_at: datetime
    status: OrderStatus
    wp_admin_url: str
    story: dict[str, Any]


class LyricDraftOut(BaseModel):
    id: int
    no: int
    status: GenerationStatus
    model: str
    title: str | None
    style: str | None
    lyrics: str | None
    note: str | None
    input_tokens: int | None
    output_tokens: int | None
    error_message: str | None
    created_at: datetime


class ClipOut(BaseModel):
    id: int
    label: str
    status: GenerationStatus
    duration_sec: Decimal | None
    audio_url: str | None
    r2_key: str | None
    file_size: int | None
    mime_type: str | None
    admin_note: str | None
    is_selected: bool


class MusicGenerationOut(BaseModel):
    id: int
    no: int
    provider_type: MusicProviderType
    status: GenerationStatus
    poll_count: int
    error_message: str | None
    submitted_at: datetime
    completed_at: datetime | None
    clips: list[ClipOut]


class EventOut(BaseModel):
    id: int
    level: EventLevel
    step: str
    message: str
    actor_name: str | None
    created_at: datetime


class JobDetailOut(BaseModel):
    id: int
    revision_no: int
    job_type: JobType
    parent_job_id: int | None
    customer_feedback: str | None
    status: JobStatus
    priority: int
    due_at: datetime
    is_overdue: bool
    error_step: str | None
    error_message: str | None
    retry_count: int

    final_title: str | None
    final_style: str | None
    final_lyrics: str | None
    lyrics_status: LyricsStatus | None
    lyrics_approved_by: str | None
    lyrics_approved_at: datetime | None

    selected_clip_id: int | None
    done_at: datetime | None
    done_by: str | None
    created_at: datetime
    updated_at: datetime

    site: SiteBrief
    order: OrderDetail
    drafts: list[LyricDraftOut]
    music: list[MusicGenerationOut]
    events: list[EventOut]
    actions: list[JobAction]


class LyricsUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    style: str | None = Field(default=None, max_length=1000)
    lyrics: str = Field(min_length=1, max_length=20000)


class RegenerateLyricsIn(BaseModel):
    note: str | None = Field(default=None, max_length=2000)


class SelectClipIn(BaseModel):
    clip_id: int