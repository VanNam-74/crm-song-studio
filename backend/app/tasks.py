import logging

from app.celery_app import celery_app

logger = logging.getLogger(__name__)

@celery_app.task(name="app.tasks.generate_lyrics", bind=True, max_retries=5)
def generate_lyrics(self, job_id: int, note: str | None = None) -> None:
    """Step 2 - placeholder until the OpenAI step is built. `note` = admin rewrite note."""
    logger.info("generate_lyrics received job %s note=%r (not implemented yet)", job_id, note)


@celery_app.task(name="app.tasks.generate_music", bind=True, max_retries=3)
def generate_music(self, job_id: int) -> None:
    """Step 4-5 - placeholder until the Suno provider is built."""
    logger.info("generate_music received job %s (not implemented yet)", job_id)