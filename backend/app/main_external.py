"""PUBLIC app - the only thing exposed to the internet (Cloudflare Tunnel).

Serves WordPress webhooks only. No docs, no admin API.

    uvicorn app.main_external:app --host 127.0.0.1 --port 8001 --proxy-headers
"""
import logging

from fastapi import FastAPI

from app.external import webhooks

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title="Create Song – external", docs_url=None, redoc_url=None, openapi_url=None)
app.include_router(webhooks.router)


@app.get("/health", include_in_schema=False)
async def health() -> dict:
    return {"status": "ok"}
