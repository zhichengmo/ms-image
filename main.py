import logging.config
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles

from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse, FileResponse

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
    openapi_url="/admin/openapi.json",
    docs_url="/admin/docs",
    redoc_url="/admin/redoc",
    root_path='/ms-image/admin'
)

if settings.ENV == 'dev':
    from fastapi.middleware.cors import CORSMiddleware

    # 开发环境允许所有源访问，支持内网IP访问
    origins = ["*"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    admin_app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.exception_handler(RequestValidationError)
@admin_app.exception_handler(RequestValidationError)
def validation_exception_handler(request, exc) -> JSONResponse:
    err_message = exc.errors()[0]['msg']
    logger.warning(get_logging_message(request, err_message))
    return JSONResponse({
        'data': None,
        'message': exc.errors()[0]['msg'],
        'success': False,
    }, status_code=422)


@app.exception_handler(StarletteHTTPException)
@admin_app.exception_handler(StarletteHTTPException)
def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    err_message = exc.detail
    logger.warning(get_logging_message(request, err_message))
    return JSONResponse({
        'data': None,
        'message': exc.detail,
        'success': False,
    }, status_code=exc.status_code)


@app.exception_handler(Exception)
@admin_app.exception_handler(Exception)
def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(get_logging_message(request, f"Unhandled exception: {exc}"))
    return JSONResponse({
        'data': None,
        'message': "Internal Server Error",
        'success': False,
    }, status_code=500)


app.include_router(api_router, prefix=settings.API_V1_STR)
admin_app.include_router(admin_api_router, prefix="/api/v1")


# 添加根路径重定向
@app.get("/")
async def root():
    return {"message": "Ms Image Service is running", "docs": "/docs"}


@admin_app.get("/")
async def admin_root():
    return {"message": "MS Scaffold Admin API is running", "docs": "/admin/docs"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app='main:app', host="0.0.0.0", port=settings.APPLICATION_PORT,
                reload=False if settings.ENV == 'production' else True)