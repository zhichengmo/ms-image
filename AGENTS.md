# AGENTS

本文件定义 Codex 在基于 `ms-scaffold` 创建和维护项目时应优先遵守的项目级规则。

目标：
- 保持 `FastAPI + Service + CRUD + Schema` 分层稳定
- 避免把业务逻辑写散到 endpoint
- 让后续生成的新项目保持统一目录结构和书写风格

## Architecture

默认分层链路：

```text
API -> Service -> CRUD -> Model/DB
Schema 作为接口边界与数据结构约束层
```

强制规则：
- 业务接口必须遵循 `API -> Service -> CRUD`
- `API` 层不直接承载复杂数据库访问逻辑
- `CRUD` 层不承载 HTTP 语义
- `Schema` 层不承载数据库访问逻辑
- 健康检查、版本信息这类简单只读接口可以例外，允许 API 直接返回

## Layer Rules

### API Layer

目录：
- `app/api/api_v1/endpoints/`
- `app/api/admin_v1/endpoints/`

职责：
- 定义路由
- 接收请求参数
- 处理依赖注入
- 处理鉴权依赖
- 调用 Service
- 返回 `GenericResponse` / `PagedResponse`

约束：
- 使用 `response_model`
- 不在 endpoint 中写复杂业务判断
- 不在 endpoint 中直接拼装复杂 SQLAlchemy 查询
- 不在 endpoint 中直接编排多个 DAL 完成业务流程

推荐模式：

```python
@router.post("/users", response_model=GenericResponse[UserResponse])
async def create_user(
    payload: UserCreate,
    service: UserService = Depends(get_user_service),
):
    data = await service.create_user(payload)
    return GenericResponse(success=True, message="创建成功", data=data)
```

### Service Layer

目录：
- `app/service/`

职责：
- 承载业务逻辑
- 编排多个 CRUD 调用
- 做业务校验、状态判断、幂等控制、聚合查询

约束：
- Service 构造函数接收 `AsyncSession`
- Service 内部初始化所需 DAL
- 不依赖 `APIRouter`、`Request`、`Depends`
- 不在 Service 中直接返回 HTTP 风格响应对象作为主设计

推荐模式：

```python
class UserService:
    def __init__(self, db: AsyncSession):
        self.user_dal = UserDal(db)

    async def create_user(self, payload: UserCreate) -> UserResponse:
        exists = await self.user_dal.get_user_by_email(payload.email)
        if exists:
            raise ValueError("邮箱已存在")
        return await self.user_dal.create_user(payload)
```

### CRUD Layer

目录：
- `app/crud/`

职责：
- 基于 `DalBase` 封装数据访问
- 提供实体级别、可复用的查询方法

约束：
- 每个核心实体一个 `XxxDal`
- `XxxDal.__init__` 必须调用 `super().__init__(db=db, model=YourModel)`
- 默认只处理数据访问，不处理接口语义
- 不在 CRUD 中直接拼装 `GenericResponse`

推荐模式：

```python
class UserDal(DalBase):
    def __init__(self, db: AsyncSession):
        super().__init__(db=db, model=User)

    async def get_user_by_email(self, email: str):
        return await self.get_data(email=email)
```

### Schema Layer

目录：
- `app/schemas/`

职责：
- 定义请求体
- 定义响应体
- 定义分页结构

约束：
- `Create`、`Update`、`Response` 分离
- `Update` 字段默认可选，供部分更新使用
- `Response` 应启用 `from_attributes = True`
- 不在 schema 中写数据库逻辑

推荐命名：
- `UserCreate`
- `UserUpdate`
- `UserResponse`
- `UserQuery`

### Model Layer

目录：
- `app/models/`

职责：
- 定义 ORM 模型
- 定义字段类型、索引、约束、表名

约束：
- 不承载接口语义
- 不承载复杂业务流程

## Dependency Injection

推荐通过依赖注入暴露 Service，而不是在 API 中手动创建 DAL。

示例：

```python
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.async_db import get_async_session
from app.service.user_service import UserService


async def get_user_service(
    db: AsyncSession = Depends(get_async_session),
) -> UserService:
    return UserService(db)
```

规则：
- API 层优先依赖 `get_xxx_service`
- Service 内部再初始化 `XxxDal`
- 除简单接口外，不推荐 API 直接使用 `XxxDal`

## Response Rules

统一响应格式：
- 单对象使用 `GenericResponse[T]`
- 分页列表使用 `PagedResponse[T]`

规则：
- API 层负责包装统一响应
- Service 层返回业务对象或 schema 数据
- CRUD 层返回 ORM 对象或序列化结果

## Naming

统一命名：
- Model: `User`
- DAL: `UserDal`
- Service: `UserService`
- Schema: `UserCreate` / `UserUpdate` / `UserResponse`
- endpoint 文件：`user.py`

避免：
- `crud_user.py`
- `user_service_impl.py`
- `schema_user.py`
- 含糊的方法名如 `handle_user`、`do_user_thing`

## Module Checklist

新增业务实体时，默认按以下顺序补齐：

1. `app/models/xxx.py`
2. `app/schemas/xxx.py`
3. `app/crud/xxx.py`
4. `app/service/xxx_service.py`
5. `app/api/api_v1/endpoints/xxx.py`
6. 在对应 `api.py` 注册路由
7. 补 Alembic 迁移

## Exceptions

允许不经过 Service 的场景：
- 健康检查
- 版本信息
- 简单静态信息返回

必须经过 Service 的场景：
- 数据新增
- 数据更新
- 数据删除
- 权限相关业务判断
- 多表协作
- 状态流转
- 审核流

## Generation Defaults

后续基于该脚手架生成新项目时，Codex 默认执行以下规则：

- 保持现有目录结构，不随意重构根结构
- 新增业务模块优先补全 `api/service/crud/schema/model`
- 示例代码优先展示完整调用链
- 优先复用 `DalBase`、`GenericResponse`、`PagedResponse`
- 除健康检查外，不生成 “API 直连 CRUD” 的示例实现

## Reference Notes

参考仓库现状时，需要注意：
- 当前仓库已有 `CLAUDE.md`，可作为架构说明参考
- 实际代码中 `health` 与 `admin` 示例接口较轻，可视为简单接口例外
- 当前 `app/service/` 目录存在，但业务示例尚未完全走通完整分层；后续新增模块应按本文件补齐
