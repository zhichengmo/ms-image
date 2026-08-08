from typing import Generic, TypeVar, List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime

T = TypeVar('T')


class GenericResponse(BaseModel, Generic[T]):
    """通用响应模型"""
    success: bool = Field(True, description="请求是否成功")
    message: str = Field("操作成功", description="响应消息")
    data: Optional[T] = Field(None, description="响应数据")
    error_code: int = Field(0, description="错误代码，0表示无错误")


class PageInfo(BaseModel):
    """分页信息"""
    total: int = Field(..., description="总记录数")
    page: int = Field(..., description="当前页码")
    limit: int = Field(..., description="每页记录数")
    total_pages: int = Field(..., description="总页数")


class PagedResponse(BaseModel, Generic[T]):
    """分页响应模型"""
    success: bool = Field(True, description="请求是否成功")
    message: str = Field("操作成功", description="响应消息")
    data: List[T] = Field([], description="数据列表")
    page_info: PageInfo = Field(..., description="分页信息")
    error_code: int = Field(0, description="错误代码，0表示无错误")


class BaseTimeModel(BaseModel):
    """基础时间模型"""
    id: Optional[int] = Field(None, description="主键ID")
    created_at: Optional[datetime] = Field(None, description="创建时间")
    updated_at: Optional[datetime] = Field(None, description="更新时间")

    class Config:
        from_attributes = True