import logging

from fastapi import APIRouter, FastAPI

from app.internal import auth, jobs 

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(
    title="Create Song – internal",
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)

api = APIRouter(prefix="/api")
api.include_router(auth.router)
api.include_router(jobs.router)
# later: sites, prompts, providers...


@api.get("/health", include_in_schema=False)
async def health() -> dict:
    return {"status": "ok"}


app.include_router(api)
