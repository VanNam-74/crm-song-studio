import logging

from app.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.generate_lyrics", bind=True, max_retries=5)
def generate_lyrics(self, job_id: int) -> None:
    """Step 2 - placeholder until the OpenAI step is built."""
    logger.info("generate_lyrics received job %s (not implemented yet)", job_id)
