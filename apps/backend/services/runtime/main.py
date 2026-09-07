# Runtime path bootstrap keeps direct script execution compatible with the
# repository-root namespace; suppress only the resulting import-order lint
# rule.
# ruff: noqa: E402
import logging.config
from pathlib import Path
import sys

# Keep the repository root stable for direct execution and fully-qualified
# imports such as `apps.backend.services.runtime.main:app`.
REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fastapi import FastAPI

from apps.backend.services.runtime.api.api_v1.api import api_router
from apps.backend.services.runtime.admin_api.api import admin_api_router
from apps.backend.core.http import install_api_exception_handlers
from apps.backend.lib import LOG_CONFIG
from apps.backend.services.runtime.config import settings
from apps.backend.services.runtime.lifespan import lifespan

logging.config.dictConfig(LOG_CONFIG)
logger = logging.getLogger('ms-image-service')

# 用户端API
app = FastAPI(
    title=settings.APPLICATION_NAME,
    openapi_url="/openapi.json",
    lifespan=lifespan,
    root_path='/ms-image'
)

# 管理员API
admin_app = FastAPI(
    title=f"{settings.APPLICATION_NAME} - 管理员后台",
    # The deployment prefix is carried by root_path.  Keeping the ASGI
    # routes relative prevents the external URL from becoming
    # /ms-image/admin/admin/docs.
    openapi_url="/openapi.json" if settings.ENV == "dev" else None,
    docs_url="/docs" if settings.ENV == "dev" else None,
    redoc_url="/redoc" if settings.ENV == "dev" else None,
    lifespan=lifespan,
    root_path='/ms-image/admin'
)

if settings.ENV == 'dev':
    from fastapi.middleware.cors import CORSMiddleware

    # 开发环境允许所有源访问，支持内网IP访问
    origins = ["*"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        # Wildcard origins and credentialed browser requests are incompatible
        # as a safe production contract. XRay auth uses explicit Authorization
        # headers (configured Basic Auth or Bearer JWT).
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    admin_app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )


install_api_exception_handlers(app, logger)
install_api_exception_handlers(admin_app, logger)


app.include_router(api_router, prefix=settings.API_V1_STR)
admin_app.include_router(admin_api_router, prefix="/api/v1")


# 添加根路径重定向
@app.get("/")
async def root():
    return {"message": "Ms Image Service is running", "docs": "/docs"}


@admin_app.get("/")
async def admin_root():
    return {"message": "MS-Image Admin API is running", "docs": "/docs"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app='apps.backend.services.runtime.main:app', host="0.0.0.0", port=settings.APPLICATION_PORT,
                reload=False if settings.ENV == 'production' else True)
