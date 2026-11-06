from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery("create_song", broker=settings.redis_url, include=["app.tasks"])
celery_app.conf.update(
    timezone="UTC",
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_queue="default",
    task_routes={
        "app.tasks.generate_lyrics": {"queue": "lyrics"},
        "app.tasks.generate_music": {"queue": "music"},
    },
    # Do not hang the webhook request if Redis is down - fail fast instead.
    broker_transport_options={"max_retries": 1, "interval_start": 0, "interval_step": 0.2},
)
