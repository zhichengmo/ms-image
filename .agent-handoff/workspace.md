# 工作区地图

## 仓库结构

- `main.py`：FastAPI（Web 接口框架）应用入口。
- `app/api/`：用户与管理 API（应用程序接口）。
- `app/service/`：业务服务；当前主要为 `xray_accuracy`（X 光准确率）验证骨架。
- `app/crud/`：数据访问层；目标实现统一继承 `app.core.crud.DalBase`。
- `app/models/`：SQLAlchemy ORM（对象关系映射）模型；当前仍含旧 AI 和 XRay 专项表。
- `app/schemas/`：请求/响应和阶段结构合同。
- `app/core/`：数据库、AI、OSS（对象存储）和消息基础设施。
- `workers/`：异步 Worker（工作进程）和 Outbox Relay（事务发件箱中继）。
- `docs/`：设计、重构导航、工程证据和历史资料。
- `AGENT_HANDOFF.md`、`.agent-handoff/`：跨会话恢复入口和状态。

## 主要入口

- `main.py`：应用创建和路由挂载。
- `app/api/api_v1/api.py`：用户 API 路由。
- `app/api/admin_v1/api.py`：管理 API 路由。
- `workers/xray_accuracy_worker/celery_app.py`：当前 XRay 异步入口。

## 文档与设计

- `docs/README.md`：文档中心。
- `docs/refactor/README.md`：重构、团队介绍和新会话导航。
- `docs/refactor/10-xray-detailed-flow.md`：XRay（X 光）端到端、事务、状态和恢复开发流程图。
- `AGENT_SESSION_PROMPTS.md`：新会话启动、继续、关闭和交接审查的可复用提示词。
- `docs/ms-image-final-architecture-and-database-design.md`：精确设计母文。
- `docs/history/README.md`：历史演进与冲突索引。
- `docs/artifacts/README.md`：工程证据索引。
- `docs/术语中英对照.md`：英文标识中文解释。

## 长期项目事实

- 目标业务链遵循 `API -> Service -> CRUD(DalBase) -> Model/DB`。
- 目标 MySQL 表不使用 Foreign Key（外键）、数据库 Enum（枚举）或 `tenant_id`（租户标识）。
- 每张物理表使用服务端生成的 `id VARCHAR(64)` 单列主键。
- API 资源 ID 放 query/body，不使用 `/{id}`。
- OSS 保存 bytes；不建设公共 `file_asset`（文件资产）表。
- 医学结论只能来自模型或医生；Python 只做校验、路由、持久化和审计。
- 未经用户特别授权不生成迁移脚本或测试脚本，不操作真实数据库。

## 开发规则

- 修改前读取确切代码，保护用户未提交改动。
- Worker/API/Service 不直接拼 SQLAlchemy 查询。
- OSS/Broker/Provider（对象存储/消息代理/AI 服务）调用不在数据库事务内。
- 目标设计和当前实现必须明确区分为 `PROPOSED` 与 `CONFIRMED`。
- 非文档任务结束前更新最小必要 handoff（交接）文件并记录验证。
