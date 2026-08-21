"""Shared HTTP exception contract for MS-Image application entrypoints."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from apps.backend.lib import get_logging_message


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
    """Keep arbitrary exception details out of shared logs and responses."""
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


def install_api_exception_handlers(app: FastAPI, logger: logging.Logger) -> None:
    """Install the stable, non-echoing API error contract on one ASGI app."""

    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        del exc
        logger.warning(get_logging_message(request, "request_validation_error"))
        return JSONResponse(
            {"data": None, "message": "请求参数无效", "success": False},
            status_code=422,
        )

    async def http_exception_handler(
        request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        err_message = _safe_http_detail(exc.status_code, exc.detail)
        logger.warning(get_logging_message(request, err_message))
        return JSONResponse(
            {"data": None, "message": err_message, "success": False},
            status_code=exc.status_code,
        )

    async def database_exception_handler(
        request: Request,
        exc: SQLAlchemyError,
    ) -> JSONResponse:
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

    async def global_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        logger.error(
            get_logging_message(request, f"Unhandled exception type={type(exc).__name__}"),
            exc_info=False,
        )
        return JSONResponse(
            {"data": None, "message": "Internal Server Error", "success": False},
            status_code=500,
        )

    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(SQLAlchemyError, database_exception_handler)
    app.add_exception_handler(Exception, global_exception_handler)


__all__ = ["install_api_exception_handlers"]
