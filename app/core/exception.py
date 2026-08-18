# -*- coding: utf-8 -*-
# @version        : 1.0
# @Create Time    : 2021/10/19 15:47
# @File           : exception.py
# @IDE            : PyCharm
# @desc           : 全局异常处理

from fastapi.responses import JSONResponse
# from sqlalchemy.testing.plugin.plugin_base import logging
import logging
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.exceptions import RequestValidationError
from starlette import status
from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi import FastAPI

# from app.core.logger import logger
# Legacy handlers remain available to the scaffold, but they must not print
# request payloads, query strings, or exception details that may contain
# credentials or image addresses.
DEBUG = False
logger = logging.getLogger(__name__)
from typing import Optional


class CustomException(Exception):

    def __init__(
            self,
            msg: str,
            code: int = status.HTTP_400_BAD_REQUEST,
            status_code: int = status.HTTP_200_OK,
            desc: str = None
    ):
        self.msg = msg
        self.code = code
        self.status_code = status_code
        self.desc = desc


class PushServiceException(Exception):
    """推送服务异常

    Attributes:
        message: 错误信息
        code: 错误代码（可选）
    """

    def __init__(self, message: str, code: Optional[str] = None):
        self.message = message
        self.code = code
        super().__init__(self.message)


def _request_path(request: Request) -> str:
    """Return only the path component for safe diagnostic logging."""
    return request.url.path


def _safe_public_message(status_code: int, detail: object) -> str:
    """Do not reflect arbitrary HTTP/validation details from legacy handlers."""
    if isinstance(detail, str) and detail in {
        "Missing bearer token",
        "Invalid bearer token",
        "Tenant scope is required",
        "Insufficient tenant scope",
        "Insufficient admin scope",
    }:
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


def register_exception(app: FastAPI):
    """
    异常捕捉
    """

    @app.exception_handler(CustomException)
    async def custom_exception_handler(request: Request, exc: CustomException):
        """
        自定义异常
        """
        logger.warning("custom_exception status=%s path=%s", exc.status_code, _request_path(request))
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "message": _safe_public_message(exc.status_code, exc.msg),
                "code": exc.code,
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def unicorn_exception_handler(request: Request, exc: StarletteHTTPException):
        """
        重写HTTPException异常处理器
        """
        logger.warning("http_exception status=%s path=%s", exc.status_code, _request_path(request))
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.status_code,
                "message": _safe_public_message(exc.status_code, exc.detail),
            }
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """
        重写请求验证异常处理器
        """
        logger.warning("request_validation_error path=%s", _request_path(request))
        # Keep a stable message instead of reflecting malformed values or
        # nested request keys from the validation payload.
        msg = "请求参数无效"
        return JSONResponse(
            status_code=200,
            content=jsonable_encoder(
                {
                    "message": msg,
                    # Validation bodies can contain signed URLs or image
                    # addresses; never echo them from a shared error handler.
                    "body": None,
                    "code": status.HTTP_400_BAD_REQUEST
                }
            ),
        )

    @app.exception_handler(ValueError)
    async def value_exception_handler(request: Request, exc: ValueError):
        """
        捕获值异常
        """
        logger.warning("value_exception path=%s", _request_path(request))
        return JSONResponse(
            status_code=200,
            content=jsonable_encoder(
                {
                    "message": "请求参数无效",
                    "code": status.HTTP_400_BAD_REQUEST
                }
            ),
        )

    @app.exception_handler(Exception)
    async def all_exception_handler(request: Request, exc: Exception):
        """
        捕获全部异常
        """
        logger.error(
            "unhandled_exception type=%s path=%s",
            type(exc).__name__,
            _request_path(request),
            exc_info=False,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=jsonable_encoder(
                {
                    "message": "接口异常！",
                    "code": status.HTTP_500_INTERNAL_SERVER_ERROR
                }
            ),
        )
