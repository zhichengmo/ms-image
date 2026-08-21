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
- 数据库访问必须统一经由现有 `apps.runtime.core.crud.DalBase`；不得新建第二套 `CRUDBase`、Repository 或数据库服务。
- “不另外添加服务”指不平行创建新的 service/repository 包、通用数据库服务或重复的微服务边界；需要业务编排时，只在现有 `apps/runtime/service/` 中增加对应的 `XxxService`，并复用同一条调用链。
- `API` 层不直接承载复杂数据库访问逻辑
- `CRUD` 层不承载 HTTP 语义
- `Schema` 层不承载数据库访问逻辑
- 健康检查、版本信息这类简单只读接口可以例外，允许 API 直接返回

## Layer Rules

### API Layer

目录：
- `apps/runtime/api/api_v1/endpoints/`
- `apps/runtime/admin_api/endpoints/`

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
- `apps/runtime/service/`

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
- `apps/runtime/crud/`

职责：
- 基于 `DalBase` 封装数据访问
- 提供实体级别、可复用的查询方法

约束：
- 每个核心实体一个 `XxxDal`
- `XxxDal.__init__` 必须调用 `super().__init__(db=db, model=YourModel)`
- `XxxDal` 必须继承 `apps.runtime.core.crud.DalBase`，构造函数接收 `AsyncSession`；所有查询、新增、更新、删除均使用其异步方法（如 `get_data`、`get_datas`、`get_count`、`create_data`、`create_datas`、`put_data`、`delete_datas`）。
- 不得直接在 Service、API、Worker 或脚本中拼装 SQLAlchemy 数据库调用；确需实体特有查询时，封装为 `XxxDal` 方法并继续调用 `DalBase`。
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
- `apps/runtime/schemas/`

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
- `apps/runtime/models/`

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

from apps.runtime.core.async_db import get_async_session
from apps.runtime.service.user_service import UserService


async def get_user_service(
    db: AsyncSession = Depends(get_async_session),
) -> UserService:
    return UserService(db)
```

规则：
- API 层优先依赖 `get_xxx_service`
- Service 内部再初始化 `XxxDal`
- 除简单接口外，不推荐 API 直接使用 `XxxDal`

## Database and Service Reuse

数据库访问合同以 `apps/runtime/core/crud.py` 中的 `DalBase` 实现为准：

```python
class DalBase:
    # 倒序排序字段
    ORDER_FIELD = ["desc", "descending"]

    def __init__(self, db: AsyncSession = None, model: Any = None, schema: Any = None):
        self.db = db
        self.model = model
        self.schema = schema

    async def get_data(
        self,
        data_id: int = None,
        v_start_sql: SelectType = None,
        v_select_from: list[Any] = None,
        v_join: list[Any] = None,
        v_outer_join: list[Any] = None,
        v_options: list[Any] = None,
        v_where: list[Any] = None,
        v_order: str = None,
        v_order_field: str = None,
        v_return_none: bool = False,
        v_schema: Any = None,
        v_expire_all: bool = False,
        **kwargs,
    ) -> Any:
        ...
```

`DalBase` 的 `get_data`、`get_datas`、`get_count`、`create_data`、`create_datas`、`put_data`、`delete_datas` 等方法都是异步方法，调用必须使用 `await`。`XxxDal` 不得绕过基类直接操作 session；不得把遗留 MongoEngine 的 `apps/runtime/crud/base.py:CRUDBase` 当作本项目的数据库访问实现。

实体 DAL 只在 `apps/runtime/crud/xxx.py` 中定义一次，例如 `class UserDal(DalBase)`；Service 使用 `from apps.runtime.crud.user import UserDal`，构造 `UserDal(db)` 后调用它的方法。Service、API、Worker 和脚本都不得重新写 SQL、`select`/`update`/`delete` 语句或另造一个数据库访问类。

本项目已经有 `apps/runtime/service/` 业务层和 `apps/runtime/core/crud.py` 数据访问基类。新增功能应复用它们：API 通过 `get_xxx_service` 注入现有 Service，Service 接收 `AsyncSession` 并初始化 `XxxDal`。除健康检查、版本信息和静态状态接口外，不要在 endpoint 中直接创建 DAL，也不要再增加平行的 Repository/DatabaseService/微服务。

数据库模型约束：每张物理 MySQL 表必须定义独立、非空的 `id` 作为单列主键，默认使用服务端生成的 opaque `VARCHAR(64)`；业务 ID、请求 ID、事件键、版本号、哈希和联合唯一约束不得替代 `id` 主键，也不得使用联合主键。目标新表不设计 `tenant_id` 或其他租户分区字段，资源 ID 必须全局唯一；读取历史兼容数据时不得把旧租户字段带回目标模型。新表不声明 foreign key；状态、类型等可演进字段优先使用 string/json/timestamp，不使用数据库 enum；每个字段的 SQLAlchemy `comment` 同时写候选类型和中文含义。资源 ID 只能放在 query 参数或 request body，禁止设计 `/{id}` 路由。

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

1. `apps/runtime/models/xxx.py`
2. `apps/runtime/schemas/xxx.py`
3. `apps/runtime/crud/xxx.py`
4. `apps/runtime/service/xxx_service.py`
5. `apps/runtime/api/api_v1/endpoints/xxx.py`
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
- 不重复创建数据库访问基类、Repository、DatabaseService 或新的平行 service 包；先复用现有 `DalBase` 与 `apps/runtime/service/`，只有明确的业务用例才新增实体级 `XxxService`。

## Reference Notes

参考仓库现状时，需要注意：
- 当前仓库已有 `CLAUDE.md`，可作为架构说明参考
- 实际代码中 `health` 与 `admin` 示例接口较轻，可视为简单接口例外
- 当前 `apps/runtime/service/` 目录存在，但业务示例尚未完全走通完整分层；后续新增模块应按本文件补齐

<!-- AGENT_HANDOFF_PROTOCOL:START -->
# Codex Agent Handoff Protocol

Layout: multi-document

## Required Startup Routine

Before making a plan or editing files, read:

1. `AGENT_HANDOFF.md`
2. `.agent-handoff/snapshot.md`
3. `.agent-handoff/risks.md`
4. `.agent-handoff/backlog.md`
5. Additional `.agent-handoff/` files only when needed by the current task, following the Recovery Reading Order in `AGENT_HANDOFF.md`
6. The source files directly relevant to the user's current request

Use the handoff files as continuity memory, but verify implementation details from source files before changing behavior.

## Default Implementation Standard

For non-trivial development work, target production/commercial-grade quality by default rather than minimum viable implementation. Prefer robust, maintainable solutions with appropriate validation, runtime and edge-case consideration, and clear reporting of what was and was not tested. Keep scope aligned with the user's request; do not add unrelated features or speculative abstractions.

## Stable File Reading Protocol

To avoid Read tool line-number or offset drift:

1. Prefer dedicated search/read tools for ordinary file lookup, content search, and file reads.
2. Confirm file size before reading large or volatile files, using line counts or targeted searches when needed.
3. Search for exact targets first, then read small exact ranges around those targets.
4. Keep Read ranges no larger than 240 lines unless the file is known to be small.
5. If Read returns unexpected empty output, offset warnings, stale snippets, inconsistent line numbers, `file is shorter than the provided offset`, or an API termination after a Read attempt, stop paging with Read for that file immediately.
6. Treat Read `offset` as a line number, not a character offset. Never retry the same out-of-range offset, and never guess by adding zeros or using large approximate offsets. If the tool reports the file has N lines, all follow-up Read offsets for that file must be within `0..N`.
7. Recover from Read offset failure by re-anchoring with a targeted `Grep` for the section/title/symbol, or by reading a small known-valid range such as offset `0`; only then read a small range around the confirmed line number.
8. When Read becomes unreliable, use shell verification commands such as `wc -l`, `rg -n`, and `sed -n '<start>,<end>p'` with quoted paths; keep ranges small and record that fallback in validation notes when relevant.
9. Treat read-only shell inspection commands (`wc`, `rg`, `grep`, `sed -n`, `ls`, `pwd`, and non-mutating `git status`/`git diff`/`git log`/`git ls-files`) as safe query operations. They should be pre-approved in project settings where possible so source verification does not require repeated manual approval.
10. Do not propose or edit code based on uncertain offsets; re-anchor with search results first.

## Continuation Recovery Guard

If the user says `continue`, `继续`, `Continue from where you left off.`, or any equivalent continuation request, treat it as an explicit instruction to resume the task. Do not answer `No response requested.` and do not stop silently. First state the last known objective and next concrete action, then continue. If context is insufficient, recover from the handoff files and task-relevant source files before acting.

## Durable Handoff Memory

The repository uses multi-document durable handoff memory:

- `AGENT_HANDOFF.md`: index and recovery route
- `.agent-handoff/snapshot.md`: current objective, status, next actions, active files, blockers, and open questions
- `.agent-handoff/workspace.md`: repository map, entry points, commands, and stable context
- `.agent-handoff/decisions.md`: durable decisions with reasons and evidence
- `.agent-handoff/work-log.md`: recent operational work
- `.agent-handoff/validation.md`: validation commands/checks and results
- `.agent-handoff/backlog.md`: pending work
- `.agent-handoff/risks.md`: risks, blockers, unknowns, and confirmations
- `.agent-handoff/archive.md`: compressed old history

Maintain the smallest relevant file. Do not put all state into `AGENT_HANDOFF.md`; it is an index.

## Handoff Size Discipline

- Keep `AGENT_HANDOFF.md` short; it is an index.
- Treat `.agent-handoff/snapshot.md` as replace-in-place current state, never an append-only history.
- Snapshot soft limit: 16 KiB or 240 lines. Hard limit: 32 KiB or 400 lines.
- Rotate `.agent-handoff/work-log.md` above 64 KiB or 30 dated sections.
- Rotate `.agent-handoff/validation.md` above 64 KiB or 200 table rows.
- Keep `.agent-handoff/backlog.md` and `.agent-handoff/risks.md` at or below 32 KiB. Only completed backlog items may be archived mechanically; risks need semantic review.
- Keep generated archive chunks at or below 128 KiB and keep archive history outside normal recovery.
- After updating handoff state, run the installed `agent-handoff/scripts/maintain_handoff.py --repo <repo> --compact-if-needed` when available. Archive before replacement and never rewrite unparseable state.
- In an ongoing uninterrupted chat, reread only relevant handoff files after compaction, resume, uncertainty, or task changes.

## Mandatory Closeout Protocol

Before any final response for a non-trivial task, update the relevant handoff files without waiting for the user to ask.

Minimum required updates:

- Refresh `.agent-handoff/snapshot.md` with current objective, status, next actions, active files, blockers, and open questions.
- Add or update `.agent-handoff/work-log.md` when files or task status changed.
- Add `.agent-handoff/validation.md` entries for commands/checks run or intentionally not run.
- Record durable decisions in `.agent-handoff/decisions.md`.
- Update `.agent-handoff/backlog.md` and `.agent-handoff/risks.md` when follow-ups, blockers, risks, or unknowns changed.
- Remove or rewrite stale state that would mislead the next agent.
- Run the bundled handoff maintenance script when available and resolve any hard-limit or unsafe-cleanup findings.

If the task was purely conversational and no project state changed, no file update is required.

## Work Discipline

- Do not assume which subproject is active. Infer it from the user request, handoff files, and repository evidence.
- Prefer existing project conventions over new abstractions.
- Read files before editing them.
- Keep edits scoped to the task.
- Do not modify generated dependency folders unless explicitly asked.
- Never revert unrelated user or agent changes.
- Record validation honestly. If tests or checks were not run, say so in handoff files and in the final response.

## Session Closeout Checklist

Before final response, update the relevant `.agent-handoff/` files with final task status, files changed, commands/checks run and outcomes, and remaining risks, blockers, open questions, or next steps.
<!-- AGENT_HANDOFF_PROTOCOL:END -->
