# Runtime path bootstrap must run before the legacy-compatible absolute
# ``app`` imports below; suppress only the resulting import-order lint rule.
# ruff: noqa: E402
import logging.config
from pathlib import Path
import sys

# Keep the Runtime import root stable for both the container's `/app` layout
# and direct repository-root imports such as `services.runtime.main:app`.
RUNTIME_ROOT = Path(__file__).resolve().parent
if str(RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNTIME_ROOT))

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api.api_v1.api import api_router
from app.api.admin_v1.api import admin_api_router
from app.lib import LOG_CONFIG, get_logging_message
from app.core.config import settings
from app.core.redis_manager import RedisManager
from contextlib import asynccontextmanager

logging.config.dictConfig(LOG_CONFIG)
logger = logging.getLogger('ms-image-service')

# 全局Redis管理器
redis_manager = RedisManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时初始化Redis
    app.state.redis_manager = redis_manager
    await redis_manager.init_redis_pool(app)
    yield
    # 关闭时清理Redis连接
    await redis_manager.close_redis_pool()


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
        # as a safe production contract.  XRay auth uses explicit JWT headers.
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


_SAFE_HTTP_DETAILS = {
    "Missing bearer token",
    "Invalid bearer token",
    "Tenant scope is required",
    "Insufficient tenant scope",
    "Insufficient admin scope",
    "JWT verification is not configured",
    "Admin JWT algorithm is not configured",
    "JWT algorithm is not configured",
}


def _safe_http_detail(status_code: int, detail: object) -> str:
    """Keep arbitrary exception details out of shared logs/responses."""
    if isinstance(detail, str) and detail in _SAFE_HTTP_DETAILS:
        return detail
    return {
        400: "请求无效",
        401: "未认证",
        403: "无权限",
        404: "资源不存在",
        409: "请求冲突",
        422: "请求参数无效",
        503: "服务暂不可用",
    }.get(status_code, "请求失败")


@app.exception_handler(RequestValidationError)
@admin_app.exception_handler(RequestValidationError)
def validation_exception_handler(request, exc) -> JSONResponse:
    # Pydantic parser messages can contain attacker-controlled fragments.
    # Keep both logs and responses on a stable, non-echoing contract.
    err_message = "请求参数无效"
    logger.warning(get_logging_message(request, "request_validation_error"))
    return JSONResponse({
        'data': None,
        'message': err_message,
        'success': False,
    }, status_code=422)


@app.exception_handler(StarletteHTTPException)
@admin_app.exception_handler(StarletteHTTPException)
def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    err_message = _safe_http_detail(exc.status_code, exc.detail)
    logger.warning(get_logging_message(request, err_message))
    return JSONResponse({
        'data': None,
        'message': err_message,
        'success': False,
    }, status_code=exc.status_code)


@app.exception_handler(Exception)
@admin_app.exception_handler(Exception)
def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        get_logging_message(request, f"Unhandled exception type={type(exc).__name__}"),
        exc_info=False,
    )
    return JSONResponse({
        'data': None,
        'message': "Internal Server Error",
        'success': False,
    }, status_code=500)


@app.exception_handler(SQLAlchemyError)
@admin_app.exception_handler(SQLAlchemyError)
def database_exception_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    """Map commit/teardown database failures to a stable technical 503."""
    logger.error(
        get_logging_message(request, f"database_exception type={type(exc).__name__}"),
        exc_info=False,
    )
    return JSONResponse(
        {
            "data": None,
            "message": "服务依赖未就绪",
            "success": False,
            "error_code": 5031,
        },
        status_code=503,
    )


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

    uvicorn.run(app='main:app', host="0.0.0.0", port=settings.APPLICATION_PORT,
                reload=False if settings.ENV == 'production' else True)
