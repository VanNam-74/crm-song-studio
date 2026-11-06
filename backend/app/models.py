"""
Create Song server - database models (SQLAlchemy 2.x, PostgreSQL).

Simplified scope: the tool generates lyrics + music and uploads files to R2.
Admins copy lyrics / file links into HIS CRM by hand and mark the job done.
There is no automatic delivery back to WordPress and no customer email.

Tables:
  admin_users, provider_configs, sites
  prompt_templates, prompt_versions
  song_orders, song_jobs
  lyric_generations, music_generations, music_clips
  job_events, webhook_logs
"""
from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON, BigInteger, Boolean, DateTime, Enum, ForeignKey, Index, Integer,
    Numeric, String, Text, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# JSONB on PostgreSQL, plain JSON elsewhere (SQLite in tests).
JSONType = JSON().with_variant(JSONB(), "postgresql")
# BIGINT on PostgreSQL; SQLite only auto-increments INTEGER primary keys.
BigIntPK = BigInteger().with_variant(Integer(), "sqlite")


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


def pg_enum(e: type[enum.Enum], name: str) -> Enum:
    return Enum(e, name=name, values_callable=lambda x: [m.value for m in x])


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class UserRole(str, enum.Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


class MusicProviderType(str, enum.Enum):
    SUNO_COOKIE = "suno_cookie"
    SUNO_OFFICIAL = "suno_official"
    MANUAL = "manual"


class DeliveryOption(str, enum.Enum):
    ONE_DAY = "1_day"
    THREE_DAY = "3_day"


class OrderStatus(str, enum.Enum):
    ACTIVE = "active"
    DONE = "done"
    CANCELLED = "cancelled"


class JobStatus(str, enum.Enum):
    QUEUED = "queued"
    GENERATING_LYRICS = "generating_lyrics"
    LYRICS_READY = "lyrics_ready"          # waiting for admin review
    LYRICS_APPROVED = "lyrics_approved"
    GENERATING_MUSIC = "generating_music"
    UPLOADING = "uploading"                # downloading takes, uploading to R2
    MUSIC_READY = "music_ready"            # waiting for admin to pick a take
    READY = "ready"                        # final take chosen, copy to HIS CRM
    DONE = "done"                          # admin copied lyrics + file to HIS CRM
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobType(str, enum.Enum):
    INITIAL = "initial"
    REVISION_LYRICS = "revision_lyrics"
    REVISION_MUSIC = "revision_music"


class LyricsStatus(str, enum.Enum):
    DRAFT = "draft"
    EDITED = "edited"
    APPROVED = "approved"


class GenerationStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETE = "complete"
    FAILED = "failed"


class EventLevel(str, enum.Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


# ---------------------------------------------------------------------------
# Admin & configuration
# ---------------------------------------------------------------------------

class AdminUser(TimestampMixin, Base):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    full_name: Mapped[str | None] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(pg_enum(UserRole, "user_role"), default=UserRole.OPERATOR)
    totp_secret_enc: Mapped[str | None] = mapped_column(Text)        # encrypted; null = 2FA off
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AdminSession(Base):
    """Server-side login session. The cookie holds a random token; only its SHA-256 is stored."""
    __tablename__ = "admin_sessions"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("admin_users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(255))


class ProviderConfig(TimestampMixin, Base):
    __tablename__ = "provider_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    type: Mapped[MusicProviderType] = mapped_column(pg_enum(MusicProviderType, "music_provider_type"))
    config_enc: Mapped[str | None] = mapped_column(Text)        # encrypted JSON: base_url, api_key...
    max_concurrent: Mapped[int] = mapped_column(Integer, default=1)
    max_per_hour: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_health_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_health_status: Mapped[str | None] = mapped_column(String(50))
    credits_remaining: Mapped[int | None] = mapped_column(Integer)


class Site(TimestampMixin, Base):
    __tablename__ = "sites"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    slug: Mapped[str] = mapped_column(String(50), unique=True)          # /webhooks/{slug}
    base_url: Mapped[str] = mapped_column(String(255))
    webhook_secret_enc: Mapped[str] = mapped_column(Text)              # WordPress -> tool (HMAC)
    r2_prefix: Mapped[str | None] = mapped_column(String(255))         # e.g. "songs/" in the site's bucket

    default_prompt_template_id: Mapped[int | None] = mapped_column(
        ForeignKey("prompt_templates.id", ondelete="SET NULL", use_alter=True)
    )
    revision_prompt_template_id: Mapped[int | None] = mapped_column(
        ForeignKey("prompt_templates.id", ondelete="SET NULL", use_alter=True)
    )
    provider_config_id: Mapped[int | None] = mapped_column(ForeignKey("provider_configs.id", ondelete="SET NULL"))

    require_lyric_approval: Mapped[bool] = mapped_column(Boolean, default=True)
    require_clip_selection: Mapped[bool] = mapped_column(Boolean, default=True)
    revision_due_hours: Mapped[int] = mapped_column(Integer, default=24)
    due_warning_hours: Mapped[int] = mapped_column(Integer, default=6)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


# ---------------------------------------------------------------------------
# Prompts (versions are immutable once used; edit = new version)
# ---------------------------------------------------------------------------

class PromptTemplate(TimestampMixin, Base):
    __tablename__ = "prompt_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int | None] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"))  # null = shared
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    active_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("prompt_versions.id", ondelete="SET NULL", use_alter=True)
    )
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)


class PromptVersion(Base):
    __tablename__ = "prompt_versions"
    __table_args__ = (UniqueConstraint("template_id", "version"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("prompt_templates.id", ondelete="CASCADE"))
    version: Mapped[int] = mapped_column(Integer)
    system_prompt: Mapped[str] = mapped_column(Text)
    user_template: Mapped[str] = mapped_column(Text)                  # Jinja2
    model: Mapped[str] = mapped_column(String(100))
    model_params: Mapped[dict | None] = mapped_column(JSONType)
    output_schema: Mapped[dict | None] = mapped_column(JSONType)
    change_note: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---------------------------------------------------------------------------
# Orders & jobs
# ---------------------------------------------------------------------------

class SongOrder(TimestampMixin, Base):
    __tablename__ = "song_orders"
    __table_args__ = (UniqueConstraint("site_id", "wp_order_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="RESTRICT"))
    wp_order_id: Mapped[int] = mapped_column(BigInteger)
    order_number: Mapped[str] = mapped_column(String(50))
    customer_name: Mapped[str | None] = mapped_column(String(255))
    customer_email: Mapped[str | None] = mapped_column(String(255))
    package_name: Mapped[str | None] = mapped_column(String(255))
    delivery_option: Mapped[DeliveryOption] = mapped_column(pg_enum(DeliveryOption, "delivery_option"))
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[OrderStatus] = mapped_column(pg_enum(OrderStatus, "order_status"), default=OrderStatus.ACTIVE)
    current_job_id: Mapped[int | None] = mapped_column(
        ForeignKey("song_jobs.id", ondelete="SET NULL", use_alter=True)
    )


class SongJob(TimestampMixin, Base):
    __tablename__ = "song_jobs"
    __table_args__ = (
        UniqueConstraint("order_id", "revision_no"),
        Index("ix_song_jobs_status_due", "status", "due_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("song_orders.id", ondelete="CASCADE"))
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"))
    revision_no: Mapped[int] = mapped_column(Integer, default=0)
    job_type: Mapped[JobType] = mapped_column(pg_enum(JobType, "job_type"), default=JobType.INITIAL)
    parent_job_id: Mapped[int | None] = mapped_column(ForeignKey("song_jobs.id", ondelete="SET NULL"))
    customer_feedback: Mapped[str | None] = mapped_column(Text)

    status: Mapped[JobStatus] = mapped_column(pg_enum(JobStatus, "job_status"), default=JobStatus.QUEUED, index=True)
    priority: Mapped[int] = mapped_column(Integer, default=5)           # higher = sooner (1-day orders)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    error_step: Mapped[str | None] = mapped_column(String(50))
    error_message: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)

    input_snapshot: Mapped[dict | None] = mapped_column(JSONType)     # order data at creation time

    final_title: Mapped[str | None] = mapped_column(String(255))
    final_style: Mapped[str | None] = mapped_column(Text)
    final_lyrics: Mapped[str | None] = mapped_column(Text)
    lyrics_status: Mapped[LyricsStatus | None] = mapped_column(pg_enum(LyricsStatus, "lyrics_status"))
    lyrics_approved_by_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id", ondelete="SET NULL"))
    lyrics_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    selected_clip_id: Mapped[int | None] = mapped_column(
        ForeignKey("music_clips.id", ondelete="SET NULL", use_alter=True)
    )

    # Admin copied lyrics + file to HIS CRM
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    done_by_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id", ondelete="SET NULL"))

    cost_openai: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=0)
    cost_music: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=0)


# ---------------------------------------------------------------------------
# Results (one row per OpenAI / Suno call)
# ---------------------------------------------------------------------------

class LyricGeneration(Base):
    __tablename__ = "lyric_generations"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("song_jobs.id", ondelete="CASCADE"), index=True)
    prompt_version_id: Mapped[int | None] = mapped_column(ForeignKey("prompt_versions.id", ondelete="SET NULL"))
    model: Mapped[str] = mapped_column(String(100))
    rendered_prompt: Mapped[str] = mapped_column(Text)
    status: Mapped[GenerationStatus] = mapped_column(pg_enum(GenerationStatus, "generation_status"))
    title: Mapped[str | None] = mapped_column(String(255))
    style: Mapped[str | None] = mapped_column(Text)
    lyrics: Mapped[str | None] = mapped_column(Text)
    raw_response: Mapped[dict | None] = mapped_column(JSONType)
    openai_response_id: Mapped[str | None] = mapped_column(String(100))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    cost: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MusicGeneration(Base):
    __tablename__ = "music_generations"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("song_jobs.id", ondelete="CASCADE"), index=True)
    provider_config_id: Mapped[int | None] = mapped_column(ForeignKey("provider_configs.id", ondelete="SET NULL"))
    provider_type: Mapped[MusicProviderType] = mapped_column(pg_enum(MusicProviderType, "music_provider_type"))
    request_payload: Mapped[dict] = mapped_column(JSONType)
    status: Mapped[GenerationStatus] = mapped_column(pg_enum(GenerationStatus, "generation_status"))
    poll_count: Mapped[int] = mapped_column(Integer, default=0)
    cost: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    error_message: Mapped[str | None] = mapped_column(Text)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MusicClip(Base):
    __tablename__ = "music_clips"

    id: Mapped[int] = mapped_column(primary_key=True)
    generation_id: Mapped[int] = mapped_column(ForeignKey("music_generations.id", ondelete="CASCADE"), index=True)
    provider_clip_id: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[GenerationStatus] = mapped_column(pg_enum(GenerationStatus, "generation_status"))
    duration_sec: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    source_audio_url: Mapped[str | None] = mapped_column(Text)
    r2_bucket: Mapped[str | None] = mapped_column(String(100))
    r2_key: Mapped[str | None] = mapped_column(String(500))
    file_size: Mapped[int | None] = mapped_column(BigInteger)
    mime_type: Mapped[str | None] = mapped_column(String(50))
    provider_meta: Mapped[dict | None] = mapped_column(JSONType)
    admin_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---------------------------------------------------------------------------
# Logs
# ---------------------------------------------------------------------------

class JobEvent(Base):
    __tablename__ = "job_events"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("song_jobs.id", ondelete="CASCADE"), index=True)
    level: Mapped[EventLevel] = mapped_column(pg_enum(EventLevel, "event_level"), default=EventLevel.INFO)
    step: Mapped[str] = mapped_column(String(50))
    message: Mapped[str] = mapped_column(Text)
    data: Mapped[dict | None] = mapped_column(JSONType)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WebhookLog(Base):
    """Every webhook received. (site_id, delivery_id) blocks duplicate processing."""
    __tablename__ = "webhook_logs"
    __table_args__ = (UniqueConstraint("site_id", "delivery_id"),)

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    site_id: Mapped[int | None] = mapped_column(ForeignKey("sites.id", ondelete="SET NULL"))
    delivery_id: Mapped[str | None] = mapped_column(String(100))   # set only when the signature is valid
    event_type: Mapped[str] = mapped_column(String(50))
    payload: Mapped[dict | None] = mapped_column(JSONType)
    signature_valid: Mapped[bool] = mapped_column(Boolean, default=False)
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("song_jobs.id", ondelete="SET NULL"))
    error_message: Mapped[str | None] = mapped_column(Text)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
