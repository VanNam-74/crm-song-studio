from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://song:song@localhost:5432/create_song"
    redis_url: str = "redis://localhost:6379/0"

    # Fernet key used to encrypt site secrets in the database.
    # Generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    fernet_key: str

    # Public URL of this server, used only to print webhook URLs in scripts.
    public_base_url: str = "http://localhost:8000"

    # Reject webhooks whose timestamp is older/newer than this (replay protection).
    webhook_tolerance_seconds: int = 300

    # Due date = paid_at + hours for each package.
    one_day_hours: int = 24
    three_day_hours: int = 72
    default_delivery_option: str = "3_day"

    # Set to false in tests or when Celery/Redis is not running yet.
    enqueue_tasks: bool = True

    # Internal admin login
    session_cookie_name: str = "ss_session"
    session_ttl_hours: int = 12
    cookie_secure: bool = True            # set false only for plain-http local dev
    login_max_attempts: int = 5
    login_lock_minutes: int = 15
    totp_issuer: str = "Song Studio"
    r2_public_base_url: str | None = None

@lru_cache
def get_settings() -> Settings:
    return Settings()
