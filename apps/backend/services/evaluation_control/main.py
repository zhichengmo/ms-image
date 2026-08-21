# ruff: noqa: E402
"""ASGI entrypoint for offline Evaluation governance."""

import logging
import logging.config
from pathlib import Path
import sys

from fastapi import FastAPI


REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from apps.backend.services.evaluation_control.api.api_v1.api import api_router
from apps.backend.services.evaluation_control.config import settings
from apps.backend.services.evaluation_control.lifespan import lifespan
from apps.backend.core.http import install_api_exception_handlers
from apps.backend.lib import LOG_CONFIG


logging.config.dictConfig(LOG_CONFIG)
logger = logging.getLogger("ms-image-evaluation-control")

app = FastAPI(
    title=f"{settings.APPLICATION_NAME} - Evaluation Control",
    openapi_url="/openapi.json",
    lifespan=lifespan,
    root_path="/ms-image/evaluation-control",
)
install_api_exception_handlers(app, logger)
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "MS-Image Evaluation Control API is running", "docs": "/docs"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app="apps.backend.services.evaluation_control.main:app",
        host="0.0.0.0",
        port=8003,
        reload=False if settings.ENV == "production" else True,
    )
