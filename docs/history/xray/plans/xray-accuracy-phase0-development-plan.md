# XRay（X 光）V2 Phase 0（第 0 阶段）工程基线开发计划与进度

> 中文阅读说明：`Phase 0` 是“第 0 阶段”，`development plan` 是“开发计划”；其余英文术语请参阅[英文术语中英对照](../../../术语中英对照.md)。

> `ARCHIVED / 历史资料`：本文保留 2026-08-11 时点的 Phase 0 记录，不再是当前唯一进度依据。

状态：`ARCHIVED`（已归档）

当前依据：[MS-Image 最终架构、数据库与完整链路设计](../../../ms-image-final-architecture-and-database-design.md)

历史语境：本文后文的“当前”“本轮”“下一步”“必须”和状态标记均冻结在 2026-08-11 记录时点，不表示现在的代码、环境、任务进度或发布授权。

版本：v0.14
最后更新时间：2026-08-11（Asia/Shanghai）
目标仓库：`/Users/mozhicheng/workspace/code/cy-code/ms-image`
关联历史设计基线：[xray-accuracy-detailed-development-document.md](../design/xray-accuracy-detailed-development-document.md)

> 在 2026-08-11 记录时点，本文件曾作为 Phase 0 进度记录。`DONE` 只表示当时有可复核 artifact 且通过对应阶段门禁；源码中“已经存在”的脚手架能力只能标记为 `CONFIRMED_BASELINE` 或 `PARTIAL`。该历史阶段不实现医学诊断链、不调用真实 Provider、不创建迁移文件或测试脚本。

本轮实现只推进工程前置链，不改变医学状态：Session/Study/Image 已接入现有 Run/Trace/Outbox 事实源，Provider 仍保持 fail-closed；即使 endpoint、model 和 API Key 已配置，在启用开关、TLS/认证、receipt signing 和逐图 receipt 全部验证前也不得标记 qualification 通过。

## 1. 历史时点状态摘要

- Phase 0 工程实施状态：`PARTIAL`
- G0 验收状态：`NOT_STARTED / NO-GO`
- 当前版本：`v0.13`
- 医学状态：`UNKNOWN / PAUSED`
- 生产状态：`NO-GO`
- 当前完成范围：Phase 0 已完成部分进程、readiness、Redis、租户依赖和本地 runtime artifact。仓库还预制了 validation-only 的 Phase 1 零模型 Run/Trace/Checkpoint/Outbox、Prompt/AI stub、TechnicalExecutor（技术执行器）与 DB-backed qualification worker；该预制链已通过临时 MySQL 本地落库验收，但发生在 G0 前，只作为技术证据，不计入 P0 `DONE`，也不得部署或扩展为医学链。
- 当前阻断项：代理外部路径未验证；DB/Redis readiness 未在部署环境验证；零模型 Model 尚无 migration；正式 Broker 生产审批/部署恢复演练尚未完成；本地资格环境已设置 `XRAY_PROVIDER_ENABLED=true`，真实认证、actual model 和两图 transport probe 已通过，但 Gemini OpenAI-compatible 响应不提供逐图 receipt、nonce echo 或 receipt signature；此外 approved fixture manifest、receipt signing key 与 qualification artifact signing key 尚未配置，正式 qualification 当前 fail-closed 为 `blocked/qualification_artifact_signing_key_missing`；Docker 容器 Python 3.11 与本机 artifact Python 3.12 的干净环境复现未完成。
- 下一步：配置获批的测试影像、HTTPS endpoint、model 和 secret 后重新执行真实多影像 qualification；在 Provider 未通过前保持 `XRAY_PROVIDER_QUALIFIED=false`，不得进入医学链或准确率评估。当前已修复 Prompt 语言静默回退、ModelCall token usage、Trace 敏感字段、Worker 默认 OSS resolver wiring，并收紧了请求 MIME allowlist、四集合 hash/逐图 receipt 对账和 qualification CLI 脱敏输出；这些只提高工程完整性，不改变真实 Provider 阻断状态。

本轮已完成的工程子项（不等价于对应 P0 任务 `DONE`）：

- `CONFIRMED_BASELINE`：双 ASGI 入口、用户/管理 liveness、受保护 admin readiness、DB/Redis/Broker fail-closed 探针、JWT tenant 依赖、DalBase CAS、零模型 API/Service/DAL/Model 草案；Checkpoint lease 条件已静态核验。
- `CONFIRMED_BASELINE`：取消重试幂等、唯一约束异常精确分类、禁止字段错误不回显、replay 阶段/发布指纹绑定、late trace 不推进 Run 版本。
- `PARTIAL`（artifact-only）：Outbox event/aggregate/hash/whitelist/attempt/error/relay lease 字段、确定性 replay artifact；已加入 Checkpoint/Outbox lease/CAS/orphan/final-writer 语义，但均未部署到 live schema 或真实 Broker。

阶段边界说明：设计基线将 G0 设为 Phase 1 前置门禁。当前 Phase 1 skeleton 是未获 G0 接受的预制代码，只能用于本地 validation-only qualification；不得据此把 Phase 0、G0 或生产状态标为完成。

## 2. 任务状态表

| ID | 任务 | 状态 | 负责人角色 | 前置 | 当前证据 | 更新时间 | 备注 |
|---|---|---|---|---|---|---|---|
| P0-A | 项目与运行时基线 | `PARTIAL` | 平台/运行时负责人 | 工作树快照 | [`p0-git-snapshot.txt`](../../../artifacts/p0-git-snapshot.txt)、[`p0-runtime-manifest.json`](../../../artifacts/p0-runtime-manifest.json)、[`p0-import-main.txt`](../../../artifacts/p0-import-main.txt)；当前源码 `compileall`/Compose config/本地双端 smoke 已通过 | 2026-08-09 | artifact 已重新绑定当前 HEAD/diff hash；尚未在干净环境安装依赖并完成部署环境启动 |
| P0-B | 双端进程、路由前缀与健康检查 | `PARTIAL` | 平台/SRE/网关负责人 | P0-A | [`p0-process-boundary.md`](../../../artifacts/p0-process-boundary.md)、[`p0-readiness.json`](../../../artifacts/p0-readiness.json)；health 200/readiness 503；admin readiness 需管理员 scope | 2026-08-09 | admin 已有独立容器，管理 docs 路径、launcher 生命周期已收口；代理路径仍 UNKNOWN |
| P0-C | 鉴权、租户与控制面边界 | `PARTIAL` | 安全/平台/权限负责人 | P0-B | [`p0-auth-tenant-contract.md`](../../../artifacts/p0-auth-tenant-contract.md)、`app/api/deps.py`、`app/core/config.py`、`app/lib/__init__.py`、`app/core/exception.py`、零模型 XRay（X 光） routes | 2026-08-09 | 用户/管理员 XRay（X 光） 查询已挂 tenant scope；已拒绝 JWT 占位密钥并修正 API（应用程序接口） key 未来时间；真实 DB 跨租户回归、单用途 replay 和完整控制面写 scope仍未验收 |
| P0-D | MySQL、AsyncSession、DalBase 与 Redis 语义 | `PARTIAL` | 后端/数据/DBA/安全负责人 | P0-B | [`p0-dal-boundary.md`](../../../artifacts/p0-dal-boundary.md)、[`p1-mysql-qualification.json`](../../../artifacts/p1-mysql-qualification.json)、`app/core/async_db.py`、`app/core/crud.py`、`app/core/redis_manager.py`、`app/core/readiness.py`、零模型 XRay（X 光） Model/DAL（数据访问层） | 2026-08-10 | Redis fail-closed、无 FK/string/comment 草案和临时 MySQL qualification 已通过；无部署 schema/migration，不能标 DONE |
| P0-E | Broker（消息代理）、Celery、Worker（异步工作进程） 边界与 Outbox（事务发件箱） ADR | `PARTIAL` | 异步基础设施/SRE/后端负责人 | P0-A、P0-D | [`p0-broker-adr.md`](../../../artifacts/p0-broker-adr.md)、`app/core/messaging/`、`workers/xray_accuracy_worker/`、[`p1-mysql-qualification.json`](../../../artifacts/p1-mysql-qualification.json) | 2026-08-10 | 公共 relay/consumer/reconcile 代码和 replay/DB-backed 证据已存在，但当前无 Docker/RabbitMQ/Celery live 消费证据；生产审批、部署恢复演练和 migration 仍未完成，不能标 DONE |
| P0-F | Phase 0 Gate 与状态记录 | `PARTIAL` | 项目负责人/QA/SRE | P0-A～P0-E | 本文件、[`p0-unknowns.md`](../../../artifacts/p0-unknowns.md)、[`p0-g0-approval.md`](../../../artifacts/p0-g0-approval.md) | 2026-08-09 | 记录文件和 artifact 索引已创建；G0 尚未验收 |
| G0 | Phase 0 总门禁 | `NOT_STARTED` | 平台+安全+QA/SRE | P0-A～P0-F | 无 | — | 任一 P0 任务未通过都不得接受、部署或扩展 Phase 1 skeleton |

状态定义：

- `CONFIRMED_BASELINE`：源码或配置已确认存在，但不代表本阶段完成。
- `PARTIAL`：已经有部分实现，但完成定义或验收证据不足。
- `NOT_STARTED`：尚未实现。
- `BLOCKED`：被明确的外部依赖、安全决策或授权阻断。
- `DONE`：完成定义、验收记录和 artifact 均已满足。

## 3. P0-A 项目与运行时基线

### 3.1 已确认基础

- 用户端入口：`main:app`，默认端口 8000。
- 管理端入口：`main:admin_app`，现有启动脚本使用端口 8001。
- Python/依赖定义：`requirements.txt`。
- 镜像入口：`Dockerfile`。
- 本地基础设施：`docker-compose.yml`。
- 当前工作树存在用户未提交修改，实施中不得 reset、checkout、clean 或覆盖。

### 3.2 本轮已开发

- Compose 改为使用 `.env.example` 作为可复现默认配置，并允许外部 `.env` 覆盖。
- Compose 增加独立 `admin` 服务，启动 `main:admin_app`，暴露 8001。
- Dockerfile 暴露 8000/8001。
- Compose 增加 MySQL、Redis、RabbitMQ healthcheck 和条件依赖。
- Compose 增加 RabbitMQ 基础设施，但 `BROKER_ENABLED=false`，未启动 Worker 或真实消费。

### 3.2.1 启动方式差异

| 方式 | 用户端 | 管理端 | 依赖与风险 |
|---|---|---|---|
| 本地 uvicorn | `uvicorn main:app --port 8000` | `uvicorn main:admin_app --port 8001` | 依赖需由本机单独提供；可复现命令已冻结 |
| Dockerfile 直接运行 | 默认 `main:app` | 不启动 | 这是当前 P0-B blocker，不可误认为双端部署 |
| Docker Compose | `app` service | `admin` service（host 端口默认仅绑定 `127.0.0.1`） | 用户/管理 liveness 使用公开进程探针；管理 readiness 需 scope；同时声明 MySQL/Redis/RabbitMQ healthcheck；网关转发尚未验证 |
| 生产部署 | 待部署 ADR | 待部署 ADR | secret、代理、进程编排和 readiness 证据均待外部确认 |

### 3.3 未完成与验收证据

| 项目 | 状态 | 验收证据 |
|---|---|---|
| `import main` | `PARTIAL` | [`p0-import-main.txt`](../../../artifacts/p0-import-main.txt)；仅证明 import-time 构造，不证明依赖可用 |
| 用户/管理独立启动 | `PARTIAL` | [`p0-process-boundary.md`](../../../artifacts/p0-process-boundary.md)；本地两个独立 uvicorn 进程 smoke 已归档，生产进程/代理仍未验证 |
| Compose 配置可解析 | `PARTIAL` | [`p0-runtime-manifest.json`](../../../artifacts/p0-runtime-manifest.json)；`docker compose config` 已通过 |
| 干净依赖复现 | `NOT_STARTED` | manifest 已建立，但尚无干净环境安装锁定记录 |
| 工作树快照 | `CONFIRMED_BASELINE` | `git status --short`；后续变更不得覆盖 |

### 3.4 完成定义

P0-A 只有在 import、Compose config、双端启动命令、runtime manifest 和工作树快照全部有 artifact 后才能标记 `DONE`。

### 3.5 任务记录补充

| 字段 | 记录 |
|---|---|
| 待开发/目标文件 | `Dockerfile`、`docker-compose.yml`、`.env.example`、`docs/artifacts/p0-runtime-manifest.json`、`docs/artifacts/p0-git-snapshot.txt` |
| 前置条件 | 保留当前工作树；平台确认本地 Python 与依赖来源 |
| 阻断条件 | 无干净环境安装记录、生产 secret 注入和双端部署证据 |
| 验收证据 | `p0-import-main.txt`、`p0-runtime-manifest.json`、`p0-process-boundary.md` |
| Owner/完成日期 | 平台/运行时负责人；未完成，日期 TBD |
| 回滚方式 | 保留快照后回退本轮新增启动编排；不得覆盖既有未提交修改 |

## 4. P0-B 双端进程、路由前缀与健康检查

### 4.1 本轮已开发

- `admin_app` 复用 lifespan，确保独立 admin 进程也初始化并关闭 Redis manager。
- 用户端新增 `/api/v1/readiness`。
- 管理端新增 `/api/v1/readiness`。
- readiness 与现有 `/health` 分离：health 仅表示进程存活，readiness 检查依赖并在失败时返回 503。
- Compose 使用 app/admin healthcheck。

### 4.2 readiness（就绪性）规则

当前 `app/core/readiness.py` 检查：

- MySQL：执行 `SELECT 1`。
- Redis：主动 `ping()`，失败返回未就绪。
- Broker：`BROKER_ENABLED=false` 时返回 `required=false/state=disabled/ready=null`，不宣称 RabbitMQ 可用；启用后在 Broker qualification 完成前返回 `state=unqualified/ready=false`。

readiness 不能把 liveness、配置存在、依赖 Python 包安装或 HTTP 200 误认为 Broker/DB/Redis 已可用。

### 4.3 记录时点未完成

- 真实反向代理外部路径尚未验证。
- `root_path` 仍只是 OpenAPI/ASGI 部署元数据，不等于真实 URL 前缀。
- admin 控制根路径是否需要网络限制或额外鉴权尚未形成 ADR。
- Broker 仍未 qualification，因此完整 readiness 不能标记为通过。

### 4.4 任务记录补充

| 字段 | 记录 |
|---|---|
| 待开发/目标文件 | `main.py`、`app/api/api_v1/endpoints/health.py`、`app/api/admin_v1/endpoints/admin.py`、`docker-compose.yml`、网关配置（外部） |
| 前置条件 | P0-A 入口与端口冻结；网关提供 `/ms-image` 和 `/ms-image/admin` 证据 |
| 阻断条件 | 代理路径未验证；admin readiness 的控制面网络边界未确认 |
| 验收证据 | `p0-process-boundary.md`、`p0-readiness.json`、边缘 HTTP smoke |
| Owner/完成日期 | 平台/SRE/网关负责人；未完成，日期 TBD |
| 回滚方式 | 保留 `/health` liveness，停用未验证的外部 readiness 暴露；记录变更原因 |

## 5. P0-C 鉴权、租户与控制面

### 5.1 本轮已开发

- 配置新增 `TENANT_CLAIM=tenant_id`。
- 配置新增独立 `ADMIN_REQUIRED_WRITE_SCOPE=xray:admin:write`。
- `app/api/deps.py` 新增严格 tenant claim 提取：缺失、空值或非字符串返回 403。
- 新增 `get_tenant_context` 和 `require_tenant_scope`，后续 XRay endpoint 必须使用，不能信任 query/body 的 tenant 字段。
- 保留现有 JWT 解码和管理员 scope 依赖，避免破坏现有未提交改动。

### 5.2 记录时点未完成

- 零模型 XRay endpoint 已使用 tenant dependency 保护 Run 查询/取消/Trace 和 admin control read；
  Review/Trace/Release 写操作尚未存在，真实 DB 跨租户回归仍待部署环境。
- 尚未定义普通诊断 scope 与控制面写 scope 的完整矩阵。
- 尚未完成跨租户访问拒绝的验收 artifact。
- 图像凭证 allowlist/TTL/单用途合同尚未实现。

### 5.3 任务记录补充

| 字段 | 记录 |
|---|---|
| 待开发/目标文件 | `app/api/deps.py`、`app/core/config.py`、XRay（X 光） endpoints、外部身份/凭证 ADR |
| 前置条件 | JWT issuer/audience/tenant claim 和 admin scope 由身份平台确认 |
| 阻断条件 | live DB 跨租户回归、控制面写 scope 矩阵、图像凭证服务合同未知 |
| 验收证据 | `p0-auth-tenant-contract.md`、401/403/跨租户拒绝 artifact、敏感日志审计 |
| Owner/完成日期 | 安全/平台/权限负责人；未完成，日期 TBD |
| 回滚方式 | 只保留已审计只读 validation-only 路由；禁止开放 truth/release/Holdout 写权限 |

## 6. P0-D 数据库、`DalBase`（数据访问基类）与 Redis（内存数据存储）

### 6.1 本轮已开发

- 新链仍限定 SQLAlchemy 2.x + `AsyncSession` + `app.core.crud.DalBase`。
- RedisManager 新增 `ready`、`last_error` 状态。
- Redis ping 失败时关闭并清空 client，不再保留“看似存在但不可用”的 client。
- RedisManager 新增 `check_readiness()`。
- readiness 显式报告 database、redis、broker 三个组件。

### 6.2 记录时点确认但未完成

- `async_db.py` 的引擎和 session 已存在，零模型 XRay model/DAL/service 草案已增加。
- `DalBase` 已存在，Run/Snapshot/Checkpoint/Trace/Outbox 实体 DAL 已增加；医学实体仍未开始。
- Alembic metadata 尚未导入 XRay models。
- 没有 migration revision；本阶段按计划不创建 migration。
- MongoEngine legacy CRUD 仍存在，只能保持为 legacy，不得由新 XRay 引入。
- Alembic URL/secret 管理仍需 ADR 和后续授权。

### 6.3 任务记录补充

| 字段 | 记录 |
|---|---|
| 待开发/目标文件 | `app/models/xray_accuracy/`、`app/crud/xray_accuracy/`、`app/service/xray_accuracy/`、`app/core/async_db.py`、`app/core/readiness.py`、Alembic ADR |
| 前置条件 | DBA 确认 MySQL 版本、连接 URL 来源和迁移授权 |
| 阻断条件 | 无 live schema/migration；Alembic URL 含开发占位凭证；Redis/Broker（消息代理） 真实可用性未知 |
| 验收证据 | `p0-dal-boundary.md`、模型 DDL/comment/FK 扫描、DB/Redis readiness artifact |
| Owner/完成日期 | 后端/数据/DBA/安全负责人；未完成，日期 TBD |
| 回滚方式 | 不生成 migration；若模型草案阻断 import，移除 XRay（X 光） 注册并保留 legacy CRUD 隔离 |

## 7. P0-E Broker（消息代理）、Worker（异步工作进程）与 Outbox（事务发件箱）

### 7.1 本轮已开发

- Compose 增加 RabbitMQ 3.13 management 基础设施、持久化卷和健康检查。
- `RABBITMQ_HOST` 默认改为 Compose service name `rabbitmq`。
- `BROKER_ENABLED=false` 明确表示当前未启用 Worker/真实消费。
- 消息白名单、Outbox 事务边界和 MySQL 事实源已写入完整设计文档。
- `workers/xray_accuracy_worker/technical_worker.py` 已提供 DB-backed qualification entrypoint；
  它不连接 RabbitMQ，正式 consumer 仍未启用。

### 7.2 Broker（消息代理）ADR（架构决策记录）草案

ADR 实例已记录于 [`p0-broker-adr.md`](../../../artifacts/p0-broker-adr.md)。当前只冻结候选
拓扑、消息白名单、Outbox 事务边界和恢复规则，不代表 Broker 已接通。`BROKER_ENABLED`
必须保持 `false`，直到异步基础设施负责人、SRE、后端负责人完成审批并有 stub/replay
恢复 artifact。

### 7.3 记录时点未完成

- 已有公共 Celery app/task、RabbitMQ consumer、正式 relay 和全局 reconcile；当前只完成本地
  Broker/临时 schema qualification，生产部署与恢复演练仍未完成。
- 已有 validation-only Outbox model 和发布确认实现，但没有已部署 migration/schema artifact。
- Broker ADR 仍需异步基础设施、SRE、后端负责人审批。
- 已有 deterministic replay、独立测试 MySQL 以及 DB-backed Worker 的重复投递、取消、late
  result 和 lease artifact；当前没有 RabbitMQ/Celery live 消费证据，生产 DLQ/lease/orphan
  恢复证据仍缺失。
- `.env.example` 的 `BROKER_ENABLED` 在生产 qualification/恢复演练前保持 `false`；仅允许
  本地 Compose qualification 显式覆盖为 `true`。

### 7.4 任务记录补充

| 字段 | 记录 |
|---|---|
| 待开发/目标文件 | `docs/artifacts/p0-broker-adr.md`、生产部署 schema、Broker（消息代理） 恢复演练 artifact |
| 前置条件 | 异步基础设施/SRE/后端审批 RabbitMQ+Celery 候选及消息白名单 |
| 阻断条件 | ADR/生产部署未审批；生产 DLQ、lease、orphan 恢复演练未完成；默认 Broker（消息代理） 仍 disabled |
| 验收证据 | `p0-broker-adr.md`、`p1-zero-model-replay.json`、持久化恢复演练 artifact |
| Owner/完成日期 | 异步基础设施/SRE/后端负责人；未完成，日期 TBD |
| 回滚方式 | `BROKER_ENABLED=false`，仅保留内存 replay；不得将 Redis/Celery result backend 当事实源 |

## 8. P0-F Gate（门禁）与记录维护

### 8.1 G0 必须收集的 artifact（证据产物）

| Artifact（不可变产物） | 内容 | 当前状态 |
|---|---|---|
| `p0-git-snapshot.txt` | 完整工作树清单、HEAD 和 dirty fingerprint | `PASS-LOCAL（artifact）` |
| `p0-runtime-manifest.json` | Python、依赖、启动命令、环境摘要 | `PASS-LOCAL（artifact）` |
| `p0-import-main.txt` | 当前源码 `import main`/compileall 结果 | `PASS-LOCAL（artifact）` |
| `p0-process-boundary.md` | app/admin 启动和外部 URL | `PARTIAL` |
| `p0-readiness.json` | DB/Redis/Broker（消息代理） readiness 结果 | `PARTIAL（本地 fail-closed smoke）` |
| `p0-auth-tenant-contract.md` | JWT、scope、tenant、控制面边界 | `PARTIAL` |
| `p0-dal-boundary.md` | AsyncSession、DalBase、MongoEngine 隔离和 schema 规则 | `PARTIAL` |
| `p0-broker-adr.md` | RabbitMQ/Celery/Outbox（事务发件箱） 决策 | `PARTIAL（草案未审批）` |
| `p1-zero-model-chain-contract.md` | 零模型 Run/Trace（技术追踪）/Outbox（事务发件箱） API（应用程序接口）→Service（业务服务层）→DAL（数据访问层）→Model 与 replay | `PARTIAL` |
| `p1-zero-model-replay.json` | 重复投递/CAS/取消/迟到/DLQ/lease/orphan/final-writer/Outbox（事务发件箱） relay deterministic replay | `PARTIAL`（artifact-only） |
| `p1-prompt-ai-request-replay.json` | Prompt（提示词） manifest/render hash、AI stub request、receipt、ModelCall fingerprint、Checkpoint/Trace（技术追踪）/Run 状态推进 | `PARTIAL`（artifact-only） |
| `p1-mysql-qualification.json` | 临时 MySQL 中的 Run/ModelCall/Checkpoint/Trace（技术追踪）/Outbox（事务发件箱）、重复、取消和 late 落库 | `PASS-LOCAL（预制 Phase 1；非 G0/部署证据）` |
| `p0-unknowns.md` | 未解决 UNKNOWN、owner、解阻动作 | `CONFIRMED_BASELINE` |
| `p0-g0-approval.md` | 平台、安全、QA/SRE 审批 | `NOT_STARTED` |

### 8.2 G0 完成定义

以下条件全部满足才可将 Phase 0 标记 `DONE`：

1. P0-A 至 P0-F 都有完成证据。
2. 用户端、管理端和代理路径可复现。
3. readiness 能真实区分 DB/Redis/Broker 状态。
4. tenant context 已挂到实际 XRay endpoint，跨租户访问被拒绝。
5. DalBase/AsyncSession/无 FK/string 状态/字段 comment 合同已冻结。
6. Broker ADR、消息白名单、Outbox 事务边界和恢复规则已审批。
7. Worker stub/replay 通过重复投递、CAS、取消、迟到、DLQ、孤儿恢复验收。
8. 未调用真实 Provider、未修改 truth/标签/scorer/原始影像。

### 8.3 任务记录补充

| 字段 | 记录 |
|---|---|
| 待开发/目标文件 | 本状态文档、`docs/artifacts/p0-g0-approval.md`、G0 汇总 artifact |
| 前置条件 | P0-A 至 P0-E 完成证据、平台/安全/QA-SRE 审批 |
| 阻断条件 | 任一 P0 任务非 `DONE`、UNKNOWN 未关闭、外部部署/DB/Broker（消息代理） 证据缺失 |
| 验收证据 | G0 artifact 索引、签名审批、未解决 UNKNOWN 清单 |
| Owner/完成日期 | 项目负责人/QA/SRE；未完成，日期 TBD |
| 回滚方式 | Phase 0 保持 `PARTIAL`、G0 保持 `NOT_STARTED/NO-GO`；不接受或部署预制 Phase 1 skeleton，不删除已有 artifact |

## 9. 第一阶段不开发的内容

以下内容必须保持 `NOT_STARTED`、`BLOCKED` 或 `N/A`：

- JointPrimaryReader、FamilyRouter、SparseTargetedReview、BlindRecallSentinel、FinalMedicalReader。
- 真实 Provider、医学 Prompt 调优、Embedding、小模型医学裁决。
- trusted gold、paired A/B、Holdout、Shadow、Gray、Active。
- 生产报告替换、医学准确率声明。
- 数据库迁移、测试脚本。
- Python 医学结论覆盖逻辑。
- 将 ABN/NOR、疾病码、历史输出、弱标签或 failure-bank 标签送入 Prompt。

## 10. 验收记录

| 验收 ID | 场景 | 结果 | Artifact（不可变产物） | 执行时间 | 执行者 |
|---|---|---|---|---|---|
| A0-01 | `import main` | `PASS-LOCAL（当前源码 artifact）` | [`p0-import-main.txt`](../../../artifacts/p0-import-main.txt) | 2026-08-09 20:59 | 平台负责人 |
| A0-02 | Compose 配置解析 | `PASS-LOCAL（当前源码 artifact）` | [`p0-runtime-manifest.json`](../../../artifacts/p0-runtime-manifest.json) | 2026-08-09 20:59 | SRE |
| A0-03 | 用户端 liveness | `PASS（本地 smoke）` | [`p0-readiness.json`](../../../artifacts/p0-readiness.json) | 2026-08-09 21:03 | 平台负责人 |
| A0-04 | 管理端 liveness/readiness | `PARTIAL（liveness 与带 scope readiness）` | [`p0-process-boundary.md`](../../../artifacts/p0-process-boundary.md) | 2026-08-09 20:40 | 平台负责人 |
| A0-05 | DB（数据库）/Redis/Broker（消息代理）readiness（就绪性） | `PARTIAL（DB/Redis fail-closed；Broker disabled 明确为 API-only，worker_ready=false）` | [`p0-readiness.json`](../../../artifacts/p0-readiness.json) | 2026-08-09 21:03 | SRE（站点可靠性工程） |
| A0-06 | JWT/tenant/scope | `PARTIAL（零模型路由负向 smoke；admin readiness 已纳入 scope）` | [`p0-auth-tenant-contract.md`](../../../artifacts/p0-auth-tenant-contract.md)、[`p1-zero-model-chain-contract.md`](../../../artifacts/p1-zero-model-chain-contract.md) | 2026-08-09 20:40 | 安全负责人 |
| A0-07 | DalBase/无 MongoEngine 越界 | `PARTIAL` | [`p0-dal-boundary.md`](../../../artifacts/p0-dal-boundary.md) | 2026-08-09 19:39 | 架构负责人 |
| A0-08 | Broker（消息代理） ADR/Outbox（事务发件箱） 恢复 | `PARTIAL（ADR 草案 + DalBase lease/CAS + relay/orphan/final/CAS replay；无持久化恢复）` | [`p0-broker-adr.md`](../../../artifacts/p0-broker-adr.md)、[`p0-dal-boundary.md`](../../../artifacts/p0-dal-boundary.md)、[`p1-zero-model-replay.json`](../../../artifacts/p1-zero-model-replay.json) | 2026-08-09 21:29 | 异步基础设施负责人 |
| A0-09 | G0 审批 | `PENDING` | `p0-g0-approval.md` | — | 平台+安全+QA/SRE |
| A0-10 | cancel Worker（取消工作进程）终态、重复投递、late-only（仅记录迟到结果）与 Outbox ack（事务发件箱确认） | `PASS-LOCAL（fake DAL + deterministic replay；无 live MySQL/Broker）` | [`p1-zero-model-replay.json`](../../../artifacts/p1-zero-model-replay.json)、[`p1-prompt-ai-request-replay.json`](../../../artifacts/p1-prompt-ai-request-replay.json) | 2026-08-10 00:18 | 后端/异步基础设施负责人 |
| A0-11 | Prompt pin（提示词固定）/歧义、AI error trace/fallback（AI 错误追踪/降级）、schema（结构合同）校验、physical attempt nonce（物理尝试随机数）、Trace（技术追踪）幂等 | `PASS-LOCAL（stub/replay + fake DAL；无 live MySQL/Broker）` | [`p1-prompt-ai-request-replay.json`](../../../artifacts/p1-prompt-ai-request-replay.json)、[`p1-zero-model-chain-contract.md`](../../../artifacts/p1-zero-model-chain-contract.md) | 2026-08-10 01:06 | 后端/AI 基础设施负责人 |
| A0-12 | 临时 MySQL（关系型数据库）Run（运行）→Worker（工作进程）→ModelCall（模型调用）→Checkpoint（检查点）→Trace（技术追踪）→Outbox（事务发件箱）、重复、取消与 late（迟到） | `PASS-LOCAL（临时 schema 已删除；无 migration/Broker/真实 Provider）` | [`p1-mysql-qualification.json`](../../../artifacts/p1-mysql-qualification.json) | 2026-08-10 01:22 | 后端/异步基础设施负责人 |
| A1-01 | 公共 AI contracts（AI 合同）、唯一 ConnectionPool（连接池）、Stub（桩实现）多影像 receipt/hash（回执/摘要）合同 | `PASS-LOCAL（不代表真实 Provider）` | `app/core/ai/contracts.py`、`app/core/ai/connection_pool.py`、内联合同 smoke | 2026-08-10 15:48 | 后端/AI 基础设施负责人 |
| A1-02 | `import main`、全量 compileall、无凭证真实 qualification fail-closed | `PASS-LOCAL / BLOCKED（provider_disabled）` | [`ai-provider-qualification.v1.json`](../../../artifacts/ai-provider-qualification.v1.json) | 2026-08-10 15:48 | 平台/Provider（AI 服务提供方） 负责人 |
| A1-03 | qualification artifact 敏感字段投影与 Provider（AI 服务提供方） actual_model/逐图 count 门禁 | `PASS-LOCAL（未执行真实 Provider）` | `app/core/ai/qualification.py`、`app/core/ai/openai_compatible.py`、`app/service/xray_accuracy/providers.py` | 2026-08-10 15:48 | 安全/Provider（AI 服务提供方） 负责人 |

## 11. 阻断项

| Blocker ID | 描述 | 影响 | Owner | 解阻动作 | 状态 |
|---|---|---|---|---|---|
| B-P0-01 | 代理真实外部路径未验证 | P0-B/G0 | 网关负责人 | 提供代理配置和 smoke artifact | `OPEN` |
| B-P0-02 | XRay（X 光） endpoint 已有零模型 skeleton，但真实 DB-backed 跨租户验收尚未完成 | P0-C/G0 | 后端/安全负责人 | 启动带 schema 的 DB 环境，验证同租户可读、跨租户不泄露 | `OPEN` |
| B-P0-03 | 零模型 XRay（X 光） model 已有草案但无 migration | P0-D 持久化验收 | DBA/数据负责人 | 获得 migration 授权后生成并验证 revision | `BLOCKED_BY_SCOPE` |
| B-P0-04 | 正式 RabbitMQ/Celery relay、consumer、DLQ/reconcile 尚未启用，ADR 尚未审批；当前仅有 DB-backed qualification worker 与内存 replay | P0-E/G0 | 异步基础设施负责人 | 完成 ADR 审批，再接通持久化 relay/consumer 并执行恢复演练 | `OPEN` |
| B-P0-05 | 无真实环境 readiness artifact | P0-A/B/D | SRE | 启动 MySQL/Redis/RabbitMQ 并保存结果 | `OPEN` |
| B-P0-06 | Compose 与 `.env.example` 仍含开发用默认凭证，生产 secret 注入方式未冻结；基础设施 host 端口仅允许本机开发绑定 | P0-A/C/D/G0 | 安全/SRE | 完成 secret manager/部署 ADR；确认非开发环境不暴露 MySQL/Redis/RabbitMQ 管理端口 | `OPEN` |
| B-P0-07 | Dockerfile 默认 CMD 仅启动用户端，直接 `docker run` 不会提供 admin | P0-B/G0 | 平台/SRE | 冻结 Compose 为唯一双端部署入口，或提供受控双进程启动方案 | `OPEN` |
| B-P0-08 | admin readiness 返回依赖状态，现已要求管理员 scope；外部网关与控制面网络边界仍未验证 | P0-B/P0-C/G0 | 安全/平台/网关 | 使用带管理员 JWT 的 readiness artifact 完成部署边缘回归，并确认只内网暴露 | `OPEN` |
| B-P0-09 | Outbox（事务发件箱） 新增 event/aggregate/hash/relay 对账字段已通过临时 MySQL transaction qualification，但尚无部署 schema、migration 或真实 relay | P0-D/P0-E/G0 | DBA/异步基础设施 | 取得迁移授权后生成 schema/revision，并完成真实 relay 对账验收 | `BLOCKED_BY_SCOPE` |
| B-P0-10 | G0 是 Phase 1 前置门禁，但仓库已经存在未获 G0 接受的 validation-only Phase 1 skeleton | 阶段治理/G0 | 项目负责人/架构负责人 | 冻结该 skeleton 为不可部署的预制代码；G0 前不得继续扩展或接真实 Provider（AI 服务提供方） | `OPEN` |
| B-P0-11 | cancel worker 只收束 Run 和 cancel trace；若原 request_gate 消息永不投递，checkpoint 不会由取消消息主动转为 `late` | P0-E/G0 恢复语义 | 异步基础设施/后端负责人 | 在正式 consumer/reconcile ADR 中定义取消 sweep 或 orphan recovery 的 checkpoint 收束规则 | `OPEN` |

## 12. 变更日志

| 日期 | 变更 | 原因 | 证据 |
|---|---|---|---|
| 2026-08-09 | 创建 Phase 0 状态记录文档 | 建立开发任务、完成状态和 G0 记录入口 | 本文件 |
| 2026-08-09 | 增加 admin Compose 服务、RabbitMQ 基础设施和健康检查 | 收口双端进程与依赖启动边界 | `docker-compose.yml`、`Dockerfile` |
| 2026-08-09 | 增加 readiness、Redis fail-closed 状态和 tenant context | 建立 P0-B/P0-C/P0-D 工程合同 | `app/core/readiness.py`、`app/core/redis_manager.py`、`app/api/deps.py`、`main.py` |
| 2026-08-09 | 使用 `/opt/homebrew/anaconda3/envs/ms-async-12/bin/python3.12` 完成 import、py_compile、Compose config 和 FastAPI smoke | 验证基线改动不会阻断启动，且依赖未启动时 readiness fail-closed | 会话命令输出；尚未生成独立 artifact |
| 2026-08-09 | 归档 Git/runtime/import/process/readiness/auth/unknown/G0 artifact，并补充 Broker（消息代理） ADR 草案 | 让 Phase 0 状态可追溯，明确草案不等于审批完成 | `docs/artifacts/` |
| 2026-08-09 | 修正 admin docs/OpenAPI 与 `root_path` 重复前缀；readiness 错误改为稳定脱敏码 | 消除外部路由歧义和依赖错误信息泄露风险 | `main.py`、`app/core/readiness.py`、`app/core/redis_manager.py` |
| 2026-08-09 | 限制日志只记录 URL path，API（应用程序接口） key 错误不回显凭证 | 满足敏感日志防护基线 | `app/lib/__init__.py`、`app/api/deps.py` |
| 2026-08-09 | RS256 优先使用显式环境变量 PEM，缺失时才读取 `RSA_PUBLIC_KEY_PATH` | 避免密钥注入方式被文件回退逻辑覆盖 | `app/core/config.py` |
| 2026-08-09 | 增加设计基线链路审查表 | 将 final/review、full_sent、Stage4、Phase/实验臂、schema comment、API（应用程序接口） 错误合同歧义显式列为后续门禁 | 本文件 §15 |
| 2026-08-09 | readiness 增加单项超时、Redis 断线后可重新连接、admin host 端口默认限制为 localhost | 避免探针无限等待、瞬态故障永久不可恢复和控制面意外公网暴露 | `app/core/readiness.py`、`app/core/redis_manager.py`、`docker-compose.yml` |
| 2026-08-09 | 双进程 launcher 在任一子进程退出时联动停止，legacy 异常处理不再打印请求 body/query/detail | 避免用户端或管理端半失效运行，以及敏感输入进入日志/响应 | `run_servers.py`、`app/core/exception.py` |
| 2026-08-09 | 增加 validation-only 零模型 Run/Trace（技术追踪）/Outbox（事务发件箱） skeleton、tenant-scoped admin read、CAS/idempotency/replay contract | 先闭合技术链路，再进入 Study（影像检查）/Provider（AI 服务提供方）/准确率阶段 | `docs/artifacts/p1-zero-model-chain-contract.md` |
| 2026-08-09 | 完成模型 comment/FK/DDL 静态审计、API（应用程序接口） 负向 smoke、replay lifecycle smoke 和分层扫描 | 验证链路边界而不声称 DB/Provider（AI 服务提供方）/医学完成 | `p1-zero-model-replay.json`、会话验证输出 |
| 2026-08-09 | 修复 cancel_requested 重试重复推进、精确区分幂等唯一冲突、禁止字段响应不回显路径；admin readiness 纳入管理员 scope；补齐 Outbox（事务发件箱） 对账字段 | 根据链路审计关闭确定性状态/泄漏问题，同时保持无 migration/无真实 Broker（消息代理） | `application_service.py`、`run.py`、`xray_runs.py`、`admin.py`、`outbox.py`、`p1-zero-model-chain-contract.md` |
| 2026-08-09 | legacy HTTP/validation handler 改为稳定脱敏消息 | 避免未注册的旧异常路径再次回显请求内容或内部 detail | `app/core/exception.py` |
| 2026-08-09 | 加强 replay lease/heartbeat/orphan/final-writer/CAS 语义；Outbox（事务发件箱） DAL（数据访问层） 校验 hash/白名单并拆分 event/task；Compose 基础设施端口改为 localhost 绑定 | 关闭可在本地验证的异步状态与开发暴露缺口，同时保持无真实 Broker（消息代理）/migration | `workers/xray_accuracy_worker/replay.py`、`app/crud/xray_accuracy/outbox.py`、`app/models/xray_accuracy/outbox.py`、`docker-compose.yml` |
| 2026-08-09 | 重新生成当前源码 import/runtime/git/readiness/replay artifact，并修正 Broker（消息代理） disabled 的 `api_only/worker_ready=false` 语义 | 让验收证据绑定当前工作树，避免把历史 artifact 误读为当前部署或 Worker（异步工作进程） 可用性 | `docs/artifacts/p0-*.{txt,json,md}`、`docs/artifacts/p1-zero-model-replay.json`、`app/core/readiness.py` |
| 2026-08-09 | 增加纯内存 ReplayOutboxRelay 的 enqueue/retry/published/dead-letter 演练 | 在不连接 RabbitMQ、不创建 migration 的前提下验证 Outbox（事务发件箱） 发布生命周期合同 | `workers/xray_accuracy_worker/replay.py`、`docs/artifacts/p1-zero-model-replay.json` |
| 2026-08-09 | relay stub 增加 release/stage/version/trace/whitelist/event-type 对齐校验 | 防止 Outbox（事务发件箱） 行与实际消息体在发布前发生字段漂移 | `workers/xray_accuracy_worker/replay.py` |
| 2026-08-09 | 增加 StageCheckpoint owner/lease 完成窗口保护、retry 元数据清理，以及 Outbox（事务发件箱） DalBase claim/heartbeat/published/retry/dead-letter/recovery 状态转换 | 防止 lease 过期 worker 覆盖新状态，并将 relay 状态推进收口到统一 DAL（数据访问层） | `app/crud/xray_accuracy/stage_checkpoint.py`、`app/crud/xray_accuracy/outbox.py`、`app/core/crud.py` |
| 2026-08-09 | 更新 deterministic replay artifact 与 Git/runtime 快照指纹 | 让证据覆盖 relay lease/orphan recovery，并绑定当前工作树 | `docs/artifacts/p1-zero-model-replay.json`、`docs/artifacts/p0-git-snapshot.txt`、`docs/artifacts/p0-runtime-manifest.json` |
| 2026-08-09 | 修复 Checkpoint heartbeat 未定义变量、fail lease 条件缺失、迟到旧版本先 CAS、取消重试版本合同；增加 Outbox（事务发件箱）/Checkpoint 唯一约束、占位 JWT 拒绝、API（应用程序接口） key 未来时间拒绝和非生产 admin docs/CORS 收口 | 关闭本地可复现的链路错误与默认配置风险，仍不宣称生产安全或准确率 | `app/crud/xray_accuracy/stage_checkpoint.py`、`workers/xray_accuracy_worker/replay.py`、`app/service/xray_accuracy/application_service.py`、`app/api/deps.py`、`main.py`、`app/models/xray_accuracy/` |
| 2026-08-09 | 增加 request_gate Prompt（提示词） manifest/render hash、stub AI request、ModelCall DAL（数据访问层）/receipt 和 TechnicalExecutor，并让 replay 同步 StageCheckpoint 与 ModelCall 技术状态 | 按用户最新要求把 Prompt（提示词） 与 AI 请求纳入完整链路，但保持 validation-only、无真实 Provider（AI 服务提供方）、无医学 verdict | `prompts/xray_accuracy/request_gate.v1.txt`、`app/service/xray_accuracy/`、`app/crud/xray_accuracy/model_call.py`、`workers/xray_accuracy_worker/replay.py` |
| 2026-08-09 | 补齐 Prompt（提示词） published/active/version/language/checksum/cache 合同与 AI pool timeout/retry/Retry-After/cooldown/fallback/trace；修复 XRay（X 光） API（应用程序接口） 错误响应前未 rollback、Executor 失败状态无法提交、用户 scope/sub 合同不严格 | 闭合 validation-only Prompt（提示词） → Pool → ModelCall → Checkpoint → Run → Trace（技术追踪） 的成功和失败路径，不接真实 Provider（AI 服务提供方） | `app/service/xray_accuracy/`、`app/api/api_v1/endpoints/xray_runs.py`、`app/api/deps.py`、`app/core/config.py`、`workers/xray_accuracy_worker/replay.py`、`docs/artifacts/p1-prompt-ai-request-replay.json` |
| 2026-08-09 | 增加 DB-backed `XRayTechnicalWorker`（XRay（X 光） 技术执行工作进程）的 `execute_message`/`execute_outbox_event`，把 Outbox（事务发件箱） lease、Executor、成功/重试/dead-letter ack 收入同一事务；增加终态/取消 late-only 守卫 | 让请求真正进入可调用的 Worker（异步工作进程）/Executor 入口，并防止取消或完成 Run 被后续技术结果覆盖 | `workers/xray_accuracy_worker/technical_worker.py`、`app/service/xray_accuracy/technical_executor.py`、`app/crud/xray_accuracy/stage_checkpoint.py` |
| 2026-08-09 | 增加 module_key/variables JSON Prompt（提示词） 查询合同、Provider（AI 服务提供方） client cache、连接成功率/失败率/最近错误统计和 Retry-After 文本解析 | 覆盖目标文件中 Prompt（提示词） governance 与 AI pool 的剩余工程语义，不接真实 Provider（AI 服务提供方） | `app/service/xray_accuracy/{prompt_service,ai_request_service}.py`、`docs/artifacts/p1-prompt-ai-request-replay.json` |
| 2026-08-09 | 以 fake DAL（数据访问层） 完成合法 Run 创建 smoke，并验证 queued Run 同时生成 Snapshot/Checkpoint/Trace（技术追踪）/Outbox（事务发件箱）；更新 worker/Outbox（事务发件箱） qualification artifact | 在无 live schema 前证明 API（应用程序接口）→Service（业务服务层） 的入口合同已连接到可执行 Outbox（事务发件箱） 消息 | `app/service/xray_accuracy/application_service.py`、`docs/artifacts/p1-zero-model-replay.json`、`docs/artifacts/p1-zero-model-chain-contract.md` |
| 2026-08-10 | 修复 cancel Worker（异步工作进程） 只返回 `cancel_acknowledged` 而不推进 `cancel_requested → cancelled` 的链路错误；增加 release/trace/expected_version 校验、CAS 终态写入、唯一 `run_cancelled` Trace（技术追踪）、重复消息幂等和 Outbox（事务发件箱） published 记录；同步 replay/Phase 1 artifacts | 审计发现 Run 模型声明 `cancelled` 终态，但数据库 Worker（异步工作进程） 没有任何写入路径，取消会永久停在 `cancel_requested` | `workers/xray_accuracy_worker/technical_worker.py`、`workers/xray_accuracy_worker/replay.py`、`docs/artifacts/p1-zero-model-replay.json`、`docs/artifacts/p1-prompt-ai-request-replay.json`、`docs/artifacts/p1-zero-model-chain-contract.md` |
| 2026-08-10 | 修复 error trace 的 `RenderedPrompt` 属性错误；pin 唯一 Prompt（提示词） checksum、拒绝同版本歧义 revision；增加渲染后泄漏检查、schema 驱动响应校验、retry physical attempt nonce、provider_key trace、Trace（技术追踪） append-or-read、running checkpoint late 迁移、非 retryable Worker（异步工作进程） 异常进入 DLQ 和 admin 404/rollback | 本地 stub/fallback 复核发现错误路径无法生成 trace，重试重放可能复用 ModelCall attempt，重复 late delivery 可能撞 Trace（技术追踪） 主键，非 retryable Worker（异步工作进程） 异常可能被错误标记 published，控制面错误路径事务语义不一致 | `app/service/xray_accuracy/{prompt_service,ai_request_service,technical_executor}.py`、`app/crud/xray_accuracy/{trace_event,stage_checkpoint}.py`、`app/api/admin_v1/endpoints/xray_control.py`、`app/models/xray_accuracy/{stage_checkpoint,trace_event}.py`、`workers/xray_accuracy_worker/technical_worker.py`、相关 Phase 1 artifacts |
| 2026-08-10 | 取消终态 API（应用程序接口） 对 `cancelled` 当前/前一版本重试保持幂等；同步 StageCheckpoint attempt 语义为逻辑 task + ModelCall physical attempt | 消除终态取消客户端重试误报 CAS 冲突，并使当前实现与 schema comment/Phase 1 合同一致 | `app/service/xray_accuracy/application_service.py`、`app/models/xray_accuracy/stage_checkpoint.py`、`docs/artifacts/p1-zero-model-chain-contract.md` |
| 2026-08-10 | 重新采集当前 import/process/readiness/runtime/Git 与 Phase 1 验收证据并同步工作树指纹 | 让记录文档与当前源码、当前本地 smoke 和未提交工作树保持可追溯 | `docs/artifacts/p0-{import-main,process-boundary,readiness,runtime-manifest,git-snapshot}.*`、`docs/artifacts/p1-*.json` |
| 2026-08-10 | 临时 MySQL qualification 发现并修复 savepoint 后访问过期 Outbox（事务发件箱） ORM 导致的 `MissingGreenlet`；随后真实落库验证成功、重复、取消和 late 链通过，临时 schema 已删除 | 让 DB-backed qualification worker 在 AsyncSession + nested transaction 下可执行，并提供非内存的持久化证据 | `workers/xray_accuracy_worker/technical_worker.py`、`docs/artifacts/p1-mysql-qualification.json` |
| 2026-08-10 | 将 Broker（消息代理）/Celery/Provider（AI 服务提供方） 公共能力从 XRay（X 光） 适配层抽出；增加公共 topology、Celery app factory、TransactionalOutboxRelay、OpenAI-compatible client、Provider（AI 服务提供方） qualification 命令和 fail-closed provider readiness；当前仅有代码与 replay/DB-backed 证据，真实外部 Provider（AI 服务提供方） 当前返回 `provider_auth` | 支持未来 CT/MRI/超声复用同一异步与 Provider（AI 服务提供方） 基础设施；Docker daemon 不可用，未证明 RabbitMQ+Celery live 自动消费；`app/service/xray_accuracy/execution_service.py:61-104` 及 admin 控制接口仍保留手动 qualification/control 入口，不能宣称已移除手动路径；不把凭证未通过的真实 Provider（AI 服务提供方） 标记为 qualified | `app/core/messaging/`、`app/core/ai/`、`workers/xray_accuracy_worker/{celery_app,outbox_relay,provider_qualification}.py`、`app/api/admin_v1/endpoints/xray_control.py`、`docs/artifacts/release-readiness-summary.md` |
| 2026-08-10 | 冻结“公共内核 + 影像适配器”的多影像封装边界，明确 Provider（AI 服务提供方）/Pool、Broker（消息代理）/Outbox（事务发件箱）、Run/Trace（技术追踪）/readiness 只实现一次，XRay（X 光）/CT/MRI/超声仅注册各自 Prompt（提示词）、Schema、图像编排和阶段 handler；当前仅形成设计合同，未标记实现完成 | 避免未来按影像复制整套服务导致目录、查询、状态和恢复语义漂移，也避免把影像专属医学规则放进公共层 | `docs/history/xray/plans/xray-accuracy-development-plan.md` §4.1、`app/core/messaging/`、`app/core/ai/`、`app/service/xray_accuracy/` |
| 2026-08-10 | 审计并冻结去冗余数据库设计；补充 Alembic metadata 导入全部 XRay（X 光） 模型，并让 Alembic URL 来自 Settings 而非硬编码密码；未生成 revision、未删除数据库、未执行 migration | 为后续受控重建准备 schema 边界，同时保护当前用户数据和未提交工作树 | `docs/history/xray/design/xray-accuracy-database-redesign.md`、`alembic_migrations/env.py` |
| 2026-08-10 | 在本机 MySQL 9.3 创建独立测试库 `ms_image_imaging_test`；`ms_image` 不存在，未读取或修改其他业务库；按去冗余 ORM metadata 创建 6 张 `xray_accuracy_*` 表，保留 schema/data 变更前备份 | 在保留原有数据库的前提下验证新 schema 可创建、无 foreign key、无空 comment；不代表应用 TCP 连接、生产 schema 或 G0 已通过 | `docs/artifacts/p0-db-rebuild-preflight.txt`、`docs/artifacts/ms_image_imaging_test-schema-backup.sql`、`docs/artifacts/ms_image_imaging_test-before-schema-change.sql`、本机 INFORMATION_SCHEMA 查询 |
| 2026-08-10 | 去除 Run `validation_only`/`cancel_requested` 物理冗余列，改由 `execution_mode`/`execution_status` 单一事实表达；去除 Trace（技术追踪） `late_flag`，迟到由 `event_type` 表达；保留旧 `xray_accuracy_*` 表名 | 在独立测试库内完成非破坏性 ALTER，并通过 ORM/数据库列对照；原有数据库未修改 | `app/models/xray_accuracy/{run,trace_event}.py`、`docs/artifacts/p0-imaging-test-db-qualification.json` |
| 2026-08-10 | 在隔离测试库保留并核对一条 validation-only `XRayRunService`（XRay（X 光） 运行服务） → `DalBase`（数据访问基类）/MySQL → `Outbox`（事务发件箱） → `XRayTechnicalWorker`（XRay（X 光） 技术执行工作进程） → `StubAIProvider`（桩 AI 提供方）持久化闭环；未调用真实 Provider（AI 服务提供方） | 验证去冗余模型仍兼容现有 Service（业务服务层）/Worker（异步工作进程） 链路；仅为本机 socket PASS-LOCAL，不代表 TCP 部署、RabbitMQ/Celery、生产 readiness 或医学完成 | `docs/artifacts/p0-imaging-test-db-qualification.json` |
| 2026-08-10 | 在去冗余 schema 上重新执行独立测试库闭环；Run/Checkpoint/ModelCall/Trace（技术追踪）/Outbox（事务发件箱） 再次落库并完成，Provider（AI 服务提供方） 仍为 stub/replay | 核对 `execution_mode` 替代冗余布尔字段后 Service（业务服务层）/Worker（异步工作进程） 仍可运行；仅为本机 socket PASS-LOCAL | `docs/artifacts/p0-imaging-test-db-qualification-rerun.json` |
| 2026-08-10 | 将 XRay（X 光） Service（业务服务层） 内部 ConnectionPool 收敛为 `app/core/ai/connection_pool.py` 唯一公共实现；补齐 ProviderRequest response_schema、真实请求 deadline、同 lane retry、actual_model 和 image_count_received 门禁；qualification artifact 对 request ID/usage 做哈希与白名单投影 | 消除重复池实现和 Stub 初始化不兼容，确保真实多影像 qualification 不能以 HTTP 200、伪造 full_sent 或缺失 actual model/逐图 receipt 放行；当前默认配置仍 fail-closed | `app/service/xray_accuracy/ai_request_service.py`、`app/core/ai/{contracts,connection_pool,openai_compatible,qualification}.py`、`app/service/xray_accuracy/providers.py`、`workers/xray_accuracy_worker/provider_qualification.py` |
| 2026-08-10 | 加强 qualification artifact 完整性门禁：HTTPS、actual_model、receipt capability、ordered hash、逐图 confirmed/index/hash 与 manifest 对账；未知异常统一映射稳定错误类；`XRAY_PROVIDER_QUALIFIED=true` 仍必须匹配当前 artifact | 防止手工/过期 artifact、HTTP endpoint、模型漂移或异常文本绕过真实 Provider（AI 服务提供方） 资格门禁；当前仍为 `blocked/provider_disabled` | `app/core/ai/qualification.py`、`app/core/readiness.py`、`app/core/ai/contracts.py`、`workers/xray_accuracy_worker/provider_qualification.py`、`app/service/xray_accuracy/ai_request_service.py` |
| 2026-08-10 | 修复 Prompt Registry（提示词注册表）的中文→英文静默回退，统一当前已发布 Prompt（提示词）为显式英文；缺失语言现在 fail-closed | 防止语言变化污染 paired A/B 和请求 fingerprint；模型实际执行语言必须可追溯 | `app/service/xray_accuracy/prompt_service.py`、`app/service/xray_accuracy/ai_request_service.py` |
| 2026-08-10 | ModelCall 写入 provider usage token，Trace（技术追踪） Event 增加递归敏感字段拒绝；Provider（AI 服务提供方） HTTP 408 归类为可重试 timeout；qualification 图像检查补齐 WebP/GIF/BMP | 修复审计字段丢失、敏感 Trace（技术追踪） 落库、408 被误判 schema_invalid 和声明/实现格式不一致 | `app/service/xray_accuracy/ai_request_service.py`、`app/crud/xray_accuracy/trace_event.py`、`app/core/ai/openai_compatible.py`、`app/core/ai/qualification.py` |
| 2026-08-10 | Worker（异步工作进程） 在真实 Provider（AI 服务提供方） 模式下自动装配 OSS（对象存储）-backed XRay（X 光） image resolver；凭证缺失仍 fail-closed | 之前真实 Provider（AI 服务提供方） 路径默认使用 FailClosedImageResolver，冻结 Study（影像检查） 无法进入实际多影像请求 | `workers/xray_accuracy_worker/technical_worker.py`、`app/core/imaging/oss_resolver.py` |
| 2026-08-10 | ModelCall receipt 增加 expected/resolved/requested/sent image refs、SHA 和 coverage_status | 让 full_sent 具备四集合可审计证据，不新增第二套事实表 | `app/service/xray_accuracy/ai_request_service.py`、`app/service/xray_accuracy/technical_executor.py` |
| 2026-08-11 | 收紧源影像 MIME 请求边界；qualification evidence 对四集合逐组校验 hash 数量/格式/ordered SHA，并将逐图 receipt 的 index/status/hash 与 ModelCall 对账；qualification CLI stdout 改为仅输出状态摘要 | 防止 refs 相同但 hash lineage 不一致、未支持媒体类型进入 Worker（异步工作进程），以及命令日志泄露过多资格元数据 | `app/schemas/xray_accuracy/{image_contract,lifecycle,run}.py`、`app/service/xray_accuracy/execution_service.py`、`workers/xray_accuracy_worker/provider_qualification.py` |
| 2026-08-11 | 开启本地 Provider（AI 服务提供方） 资格环境；增加 MySQL Unix socket 支持和 secret-free Key fingerprint 优先选择；真实验证 preferred lane 的认证、actual model、usage、request ID 及两图 transport；将 Provider（AI 服务提供方） 完全不声明 receipt capability 的情况稳定分类为 `provider_receipt_unsupported` | 旧 Key 池前七个 credential 已失效，第八个去重 Key 可真实调用；Gemini 标准响应不含私有逐图签名 receipt，必须与 `provider_receipt_missing` 区分且不得冒充 `full_sent=confirmed` | `.env`（ignored，无明文 Key）、`app/core/{config,async_db,reference_env}.py`、`app/core/ai/{contracts,connection_pool}.py`、`app/service/xray_accuracy/providers.py`、`workers/xray_accuracy_worker/{provider_qualification,technical_worker}.py` |

## 13. 回滚规则

- 本阶段变更只允许回滚新增的 Phase 0 工程边界，不得覆盖用户原有修改。
- 如果 admin Compose 服务或 readiness 影响现有 liveness，可停用新 readiness 路由并保留 `/health`；必须在变更日志记录原因。
- `.env.example` 的 `BROKER_ENABLED` 在生产审批、DLQ/恢复演练通过前保持 `false`；仅允许
  Compose 本地 qualification 服务显式覆盖为 `true`。
- Redis/DB/Broker 依赖异常时只能返回 readiness 失败或技术失败，不得转换为医学 normal/abnormal。
- 未通过 G0 前不得接受、部署或继续扩展预制 Phase 1 skeleton，也不得接入真实 Provider。

## 14. 链路审查与已识别问题

以下是本轮对“请求 → 双端进程 → 鉴权 → readiness → 异步边界”链路的工程审查结论，
不是医学准确率结论：

1. `root_path` 只影响 ASGI 生成的 URL 元数据，不能证明网关真的提供
   `/ms-image` 或 `/ms-image/admin`；必须以网关配置和边缘 smoke 为准。该项仍是
   `B-P0-01`。
2. 管理端曾将 `openapi_url/docs_url/redoc_url` 再次写成 `/admin/*`，与
   `root_path='/ms-image/admin'` 叠加后会形成 `/ms-image/admin/admin/*` 的外部歧义，
   已改为 root_path 相对路径并保留路由 artifact。
3. readiness 不能把“进程可导入”或“Redis client 对象存在”当成依赖可用；当前已使用
   MySQL `SELECT 1`、Redis `PING` 和 Broker 显式 qualification 状态，并在失败时返回
   503。底层异常已脱敏为稳定错误码，避免通过探针泄露连接信息。
4. `tenant_id` 依赖已经挂到零模型 Run/Trace 和管理员控制面读取路由，但真实 DB-backed
   跨租户拒绝仍未验收；必须在有 schema 的部署环境补充证据。
5. `app/core/crud.py` 的 `DalBase` 现在承载零模型 XRay Model/DAL/Service；MongoEngine
   legacy CRUD 仍存在但不得进入新链。模型草案虽已满足无 FK/string/comment 规则，
   没有 migration authority 前不能把 P0-D 标成完成。
6. Compose 已提供 RabbitMQ，并新增公共 Celery app factory、XRay relay/consumer 与全局
   lease reconcile；当前 Compose 默认 `BROKER_ENABLED=false`，代码和 replay/DB-backed
   qualification 已有，但由于 Docker daemon 不可用，尚无 RabbitMQ+Celery live 自动消费
   证据。生产 Broker 审批、部署恢复演练和真实 Provider qualification 仍是 P0-E/G0 门禁。
7. 统一异常处理会记录异常消息，因此所有新增 endpoint 必须避免把 signed URL、原图地址、
   token 或医学输入拼进异常 detail；当前通用日志已去掉 query string，API key 依赖也已改为
   固定错误消息，main/legacy handler 的 HTTP detail、异常 body 和 traceback 也已收口，
   但 XRay 领域日志合同仍待 Phase 1 实例化。
8. Compose 中的 `password`、示例 JWT key 只可作为本地开发占位；若没有外部 secret 注入合同，
   不能把当前配置当成生产安全基线。
9. `Dockerfile` 的默认 `CMD` 仍然只启动 `main:app`；只有 Compose 的独立 `admin` service
   才启动 `main:admin_app`。因此“直接 `docker run` 同时提供双端”尚未成立，部署合同必须明确
   Compose/编排层是双端启动入口，或后续提供受控的双进程方案。
10. 取消链路曾存在确定性错误：API 已将 Run 置为 `cancel_requested` 并发出 cancel Outbox，
   但 Worker 只读取并 ack，未执行 CAS 到 `cancelled`，也未写终态 Trace；现已修复并通过
   fake-DAL 与临时 MySQL 的终态、重复投递和 Outbox published smoke。真实 Broker 与部署 schema 仍待验收。
11. Prompt 资产原先未 pin checksum，错误路径的 trace 还访问了 `PromptManifest` 上不存在的
    `rendered_sha256`；现已固定当前 revision checksum，并修复错误 trace 路径，Prompt 歧义和
    渲染后泄漏均 fail-closed。
12. retry/re-delivery 原先可能复用相同的 Provider physical attempt id，导致 ModelCall 唯一键
    冲突；现由每次 AI Service invocation 生成 request nonce，physical attempt id 可审计且不复用。
13. 迟到重复消息原先可能重复插入固定 Trace 主键，且 running checkpoint 无法转 late；现已
    增加 append-or-read Trace 与 running→late 条件，并通过临时 MySQL 串行资格验证；真实并发和 Broker 回归仍未完成。
14. 临时 MySQL qualification 暴露了 savepoint 释放后 Outbox ORM 属性过期、同步访问触发
    `MissingGreenlet` 的异步会话错误；Worker 现已在进入 savepoint 前提取消息身份纯值并通过复验。
15. 管理控制面 Run 不存在原先返回 200 且 SQLAlchemy 异常未显式 rollback；现与用户面统一
    为 404/503 并回滚，真实 DB session teardown 仍需部署环境验证。
16. cancel worker 当前不主动扫描同一 Run 的 queued/running checkpoint；只有迟到的
    request_gate delivery 才会触发 `mark_late`。若消息永久丢失，需由正式 reconcile/sweep
    收束 orphan checkpoint，不能把当前临时 qualification 误读为已解决。

这些问题都已映射到任务状态和 blocker 表；在 G0 审批前不得推进医学 Phase 1、真实 Provider 或准确率实验。

> 注：零模型 skeleton 是为先闭合技术链路而增加的 validation-only 草案，不等于 G0 通过，
> 也不改变 Phase 0 对真实 Provider、医学节点、迁移和测试脚本的禁止范围。

## 15. 设计基线文档中的待修订链路问题

这些问题来自对关联完整架构文档的只读审查，当前不在 Phase 0 代码实现范围内，必须在
进入相应阶段前修订 ADR/状态合同：

| 问题 | 证据位置 | 影响 | 处理门禁 |
|---|---|---|---|
| `FinalMedicalReader` 是唯一 AI final owner，但 `review_required` 的 AI final 持久化位置、人工 review 与交付状态关系未闭合 | `xray-accuracy-detailed-development-document.md` §2、§7 | 可能由 Review（人工复核）/DecisionPolicy 覆盖医学 final，分母不可复现 | Phase 1 状态机 ADR |
| `full_sent` 一处要求逐图 receipt，另一处允许 qualification 替代证据，但没有不可变批准 artifact/证据等级 | §5、§11 | 同一数据集可能被不同实现计为 eligible | B0/A1 实验门禁 |
| Phase 4 提及未定义的 `Stage4`，与 A3a/A2/A3b 和具体 stage_key 无唯一映射 | §12 | 失败恢复和重试无法机械验收 | Phase 4 实施前修订 |
| Phase 编号、实验臂编号（Control/B0/A1/A3a…）和 pipeline stage_key 交织，没有统一导航表 | §11–§13 | 开发、QA、医学读者可能误把实验臂当实现阶段 | 文档发布门禁 |
| 多个表以压缩字段列表描述，未逐字段给出 SQL 候选类型、nullable、索引和中文 comment | §7 | 实现者无法稳定生成 schema artifact | P0-D schema 合同 |
| API（应用程序接口） 错误合同没有完整映射 HTTP 状态、409/CAS、幂等冲突、可重试语义 | §6 | 客户端重试和故障归因不一致 | Phase 1 API（应用程序接口） ADR |

上述条目是设计风险，不应被当前 `PARTIAL` 工程基线误读为已解决。

## 16. 链路改动进度（准确率前置）

该表记录为先完成技术链路而增加的零模型骨架；这些任务不改变医学状态，也不代表 G0
或任何准确率门禁已通过。

| ID | 改动 | 状态 | 代码/证据 | 未完成边界 |
|---|---|---|---|---|
| CHAIN-01 | 用户 Run/取消/Trace（技术追踪） API（应用程序接口），资源 ID 使用 query/body | `PARTIAL` | `app/api/api_v1/endpoints/xray_runs.py` | DB schema/migration 和部署环境未验收 |
| CHAIN-02 | Admin tenant-scoped control read | `PARTIAL` | `app/api/admin_v1/endpoints/xray_control.py`、`app/api/deps.py` | release/truth/Holdout 写权限尚未开放 |
| CHAIN-03 | Run/Snapshot/Checkpoint/ModelCall/Trace（技术追踪）/Outbox（事务发件箱） SQLAlchemy model 草案 | `PARTIAL` | `app/models/xray_accuracy/`、`p0-dal-boundary.md` | 已补不可变 `study_revision`、Outbox（事务发件箱） relay 对账字段、ModelCall fingerprint/receipt 字段和唯一约束；无 migration；Finding/Review（人工复核）/ReleaseEvent 未开始 |
| CHAIN-04 | `API → Service → DAL(DalBase) → Model`（应用程序接口 → 业务服务层 → 数据访问层 → 模型）调用链、tenant filter（租户过滤）、幂等唯一键 | `PARTIAL` | `app/service/xray_accuracy/`、`app/crud/xray_accuracy/` | live MySQL（在线数据库）、并发竞态和 CAS DB（数据库比较并交换）证据待补 |
| CHAIN-05 | Outbox（事务发件箱） 白名单、technical worker entrypoint 与 deterministic replay（重复/CAS/取消终态/迟到/DLQ/lease/orphan/final writer/relay） | `PARTIAL` | [`p1-zero-model-replay.json`](../../../artifacts/p1-zero-model-replay.json)、`app/core/messaging/`、`app/crud/xray_accuracy/outbox.py`、`workers/xray_accuracy_worker/` | 公共 relay/consumer/reconcile 代码与 replay/DB-backed 证据已存在，但无 RabbitMQ/Celery live 消费证据；生产 Broker（消息代理）、部署 schema 和恢复演练仍未完成 |
| CHAIN-07 | published/active Prompt（提示词） Registry（注册表）、公共 AI contracts/ConnectionPool、OpenAI-compatible 多影像 adapter、ModelCall fingerprint/receipt、TechnicalExecutor 成功/失败状态 | `PARTIAL` | `prompts/xray_accuracy/request_gate.v1.txt`、`app/core/ai/{contracts,connection_pool,openai_compatible,qualification}.py`、`app/service/xray_accuracy/{prompt_service,ai_request_service,technical_executor,providers}.py`、`workers/xray_accuracy_worker/provider_qualification.py`、[`ai-provider-qualification.v1.json`](../../../artifacts/ai-provider-qualification.v1.json) | 真实认证、actual model 和两图 transport probe 已通过；Gemini 不提供逐图签名 receipt，正式 qualification 仍 BLOCKED，不能标 qualified；医学节点仍未开始 |
| CHAIN-06 | Provider（AI 服务提供方）/医学结论隔离 | `CONFIRMED_GUARD` | `ai_medical_status=not_produced`、无 Provider（AI 服务提供方） import | 后续医学阶段另行门禁，不得提前接入 |

## 17. 本轮实现增量与记录时点状态

| ID | 改动 | 状态 | 代码/证据 | 未完成边界 |
|---|---|---|---|---|
| CHAIN-08 | Session 生命周期：创建、取消、append-only session event、查询事件 | `PARTIAL` | `app/models/xray_accuracy/{session,session_event}.py`、`app/service/xray_accuracy/lifecycle_service.py`、`app/api/api_v1/endpoints/xray_lifecycle.py` | 未接入上游生产身份适配器；真实 DB/跨租户回归待部署环境 |
| CHAIN-09 | Study（影像检查） Revision 与 Image（影像） Asset 占位、幂等冲突保护、四集合前的 expected manifest | `PARTIAL` | `app/models/xray_accuracy/{study_snapshot,image_asset}.py`、`app/crud/xray_accuracy/`、`/study-preparations` | 尚未在生产 schema 创建；source image credential resolver 未配置 |
| CHAIN-10 | Worker（异步工作进程）-only OSS（对象存储） boundary、MIME/像素/大小校验、DICOM 元数据读取与单帧 PNG 内存转换 | `PARTIAL/FAIL-CLOSED` | `app/core/imaging/{object_store,ingest,oss_resolver}.py` | OSS（对象存储） 凭证、上游 source fetcher、压缩 DICOM 解码能力待批准；signed URL 不持久化 |
| CHAIN-11 | `prepare_study` Worker（异步工作进程）：所有资产上传后才冻结 `ready_full_study`，失败不生成医学 verdict | `PARTIAL` | `app/service/xray_accuracy/technical_executor.py`、`workers/xray_accuracy_worker/technical_worker.py` | 当前默认 source fetcher/OSS（对象存储） 未配置，执行会阻断；尚无 live Broker（消息代理） |
| CHAIN-12 | Outbox（事务发件箱） 发布/消费状态正交拆分、consumer lease heartbeat/recovery、取消和 retry 上限 | `PARTIAL` | `app/models/xray_accuracy/outbox.py`、`app/crud/xray_accuracy/outbox.py`、`workers/xray_accuracy_worker/technical_worker.py` | 历史已存在 rows 的 backfill 语义未执行；RabbitMQ/Celery live 演练未完成 |
| CHAIN-13 | Diagnosis 冻结 Study（影像检查） 门禁（兼容开关 `XRAY_REQUIRE_FROZEN_STUDY`） | `PARTIAL` | `app/service/xray_accuracy/application_service.py`、`.env.example` | 默认保持 false，待隔离测试库和 Study（影像检查） preparation artifact 审批后再开启 |
| CHAIN-14 | Session subject ownership、CAS 取消、Study（影像检查） preparation request id/metadata fingerprint 幂等 | `PARTIAL` | `app/service/xray_accuracy/lifecycle_service.py`、`app/crud/xray_accuracy/{session,study_snapshot}.py`、`app/schemas/xray_accuracy/lifecycle.py` | 真实身份平台和并发 DB 回归待部署环境 |
| CHAIN-15 | OSS（对象存储） 内容寻址 object key、下载大小限制、DICOM MIME/像素门禁、asset hash/key 绑定 | `PARTIAL/FAIL-CLOSED` | `app/core/imaging/{object_store,ingest,oss_resolver}.py` | 上游 fetcher SSRF/凭证合同仍需外部批准；不持久化 signed URL |
| CHAIN-16 | Provider（AI 服务提供方）/Worker（异步工作进程） 默认使用冻结 Study（影像检查） 的 OSS（对象存储） resolver；真实 Provider（AI 服务提供方） 启用但 OSS（对象存储） 未配置时 fail-closed | `PARTIAL/FAIL-CLOSED` | `workers/xray_accuracy_worker/technical_worker.py`、`app/core/imaging/oss_resolver.py` | 仍需真实 OSS（对象存储） 凭证、source fetcher 和多影像部署验收 |
| CHAIN-17 | ModelCall receipt 保存 expected/resolved/requested/sent 四集合、SHA 和 coverage 状态 | `PARTIAL` | `app/service/xray_accuracy/ai_request_service.py`、`app/service/xray_accuracy/technical_executor.py`、`app/service/xray_accuracy/execution_service.py` | 已增加四组 hash 的逐项格式/数量/顺序校验及逐图 receipt 对账；真实 Provider（AI 服务提供方） receipt 尚未执行，未进入医学分母 |
| CHAIN-18 | Trace（技术追踪） Event 写入前拒绝 secret、Prompt（提示词）、响应、signed URL、原图等敏感字段 | `CONFIRMED_GUARD` | `app/crud/xray_accuracy/trace_event.py` | 仅防止新写入；需部署环境日志/数据库扫描复核历史数据 |
| CHAIN-19 | Provider（AI 服务提供方） HTTP 408 映射为可重试 endpoint_timeout；qualification loader 支持 WebP/GIF/BMP | `CONFIRMED_BASELINE` | `app/core/ai/openai_compatible.py`、`app/core/ai/qualification.py` | 不代表真实 Provider（AI 服务提供方） 或全部格式兼容性已验收 |
| CHAIN-20 | 旧 XRay（X 光） V2 兼容入口映射至 Session/Study（影像检查）/Run/Outbox（事务发件箱）；旧 URL 仅允许批准 hash→opaque ref；任务/报告/segmentation 查询不伪造医学结果 | `PARTIAL` | `app/service/xray_accuracy/legacy_compat_service.py`、`app/api/api_v1/endpoints/xray_legacy_compat.py`、`app/schemas/xray_accuracy/legacy_compat.py` | OSS（对象存储）/source fetcher、live Worker（异步工作进程）、Result/Finding/Report（报告） 未完成 |
| CHAIN-21 | Run 最新查询统一通过 `DalBase.get_data`，列表通过 `get_datas`；Study（影像检查） revision 通过 RequestSnapshot DAL（数据访问层） join/Service（业务服务层） 校验，禁止访问不存在的 Run 字段 | `CONFIRMED_GUARD` | `app/crud/xray_accuracy/run.py`、`app/crud/xray_accuracy/request_snapshot.py`、`app/core/crud.py` | live 并发 DB 回归和部署 schema 仍待完成 |

### 17.1 本轮验证记录

| 验收项 | 结果 | Artifact（不可变产物）/命令 | 说明 |
|---|---|---|---|
| Python compile/import | `PASS-LOCAL` | `python -m compileall -q app workers main.py`；`python -c 'import main'` | 仅证明当前工作树语法和 import 可用 |
| 路由注册 | `PASS-LOCAL` | FastAPI route introspection | 新增 Session/Study（影像检查）/Asset/Event 路径均无 `/{id}` |
| XRay（X 光） metadata | `PASS-LOCAL` | SQLAlchemy metadata inspection | 新增表无 foreign key，字段 comments 非空；未创建 migration |
| PNG/DICOM 工程检查 | `PASS-LOCAL` | inline inspection（未写入测试脚本） | DICOM 单帧可转换为 worker-memory PNG；多帧/解码异常 fail-closed |
| Prompt（提示词） language gate | `PASS-LOCAL` | inline Python smoke；`prompt_language_not_available` | 缺失语言不再静默回退；当前已发布请求门 Prompt（提示词） 固定英文 |
| Trace（技术追踪） sensitive payload gate | `PASS-LOCAL` | inline Python smoke；`_contains_sensitive` | signed URL、authorization、Prompt（提示词）、原图 bytes 等新写入被拒绝 |
| Provider（AI 服务提供方） coverage evidence | `PASS-LOCAL（stub contract）` | inline ProviderRequest/Stub receipt smoke | ModelCall receipt 结构已包含四集合/ordered SHA 结构；未证明真实 Provider（AI 服务提供方） receipt |
| Provider（AI 服务提供方） HTTP timeout mapping | `PASS-LOCAL` | static/compile check | HTTP 408 映射 `endpoint_timeout` 并进入有界 retry；未做网络实测 |
| 真实 Provider（AI 服务提供方） qualification | `PARTIAL / BLOCKED` | `docs/artifacts/ai-provider-qualification.v1.json`、2026-08-11 inline secret-free auth/multi-image probes | endpoint/key/TLS/actual model/两图 transport 已通过；approved fixture、两个 signing key 和 Provider（AI 服务提供方） 逐图 receipt 未满足，禁止强行设置 qualified |
| 医学链/准确率 | `NOT_STARTED` | 无 | 未创建医学节点、Result、Review（人工复核）、Release，也未产生医学 verdict |

### 17.2 变更后的下一步门禁

1. 由平台/安全负责人提供隔离测试库、OSS source fetcher 合同和批准测试影像。
2. 在不改旧数据库的前提下，验证 `prepare_study` 成功、部分失败、重复执行和冻结幂等。
3. 由 Provider owner 提供真实 HTTPS endpoint、secret_ref、model 和逐图 receipt 合同。
4. 通过真实多影像 qualification 后，才允许建设 `ai_*` 控制面表和医学阶段；当前本地资格环境可保持 `XRAY_PROVIDER_ENABLED=true`，但必须继续保持 `XRAY_PROVIDER_QUALIFIED=false`、`XRAY_REQUIRE_FROZEN_STUDY=true`，普通医学请求仍不得放行。

### 17.3 旧 XRay（X 光）V2 兼容链与 `DalBase`（数据访问基类）查询边界（2026-08-12）

本轮借鉴旧 `vet-platform` 已跑通的调用顺序：

```text
session-start → preparations → reports → task/report query → segmentation query
```

在 `ms-image` 内增加兼容适配层，但不复制旧 `MedicalRecord`、`MedicalImage`、
`AsyncXrayTask`、`ReportContent` 表，也不把旧的完整 `image_url/file_url` 写入新事实表。
兼容入口只映射到现有 `xray_accuracy_session`（XRay 会话兼容表）、`xray_accuracy_study_snapshot`（XRay 检查快照兼容表）、
`xray_accuracy_image_asset`（XRay 影像资产兼容表）、`xray_accuracy_run`（XRay 运行记录表）、`xray_accuracy_request_snapshot`（XRay 请求快照表）、
`xray_accuracy_outbox`（XRay 事务发件箱表）。

| 旧语义 | 新入口 | 内部事实 | 状态 |
|---|---|---|---|
| `session-start` | `POST /api/v1/session-start` | `XRaySession` + `session_started` event | `PARTIAL` |
| `preparations` | `POST /api/v1/x_ray/v2/preparations` | Study（影像检查）/Asset 占位 + `prepare_study` Run/Outbox（事务发件箱） | `PARTIAL` |
| `reports` | `POST /api/v1/x_ray/v2/reports` | 冻结 Study（影像检查） 校验 + `diagnose` Run/Outbox（事务发件箱） | `PARTIAL` |
| 任务查询 | `GET /api/v1/x_ray/v2/tasks?task_id=...` | Outbox（事务发件箱） task + Run 投影 | `PARTIAL` |
| 报告查询 | `GET /api/v1/x_ray/v2/reports?session_id=...` | Run/Study（影像检查） 技术状态投影 | `PARTIAL` |
| segmentation 查询 | `GET /api/v1/x_ray/v2/segmentations?session_id=...` | Study（影像检查）/Asset 工程摘要 | `PARTIAL` |

兼容层只返回事实中存在的工程状态。没有 `xray_accuracy_result`、Finding 或医学阶段时，
报告状态明确为 `medical_not_produced`，`decision`、`primary_diagnosis`、
`disease_list` 不填充；没有 segmentation 事实资产时返回 `preview_status=empty`，
不伪造旧链的框、裁剪图或医学结论。

旧请求若携带 `image_url`，只允许经过部署侧批准的
`SHA256(image_url) -> opaque source_image_ref` 映射；原 URL 不落库、不进入 Outbox/Trace。
未配置或未批准的 URL 以 `legacy_image_url_not_approved` 阻断。`force_refresh_*` 不执行旧链的
覆盖/软删除语义；不可变 Study revision 下当前明确返回 `legacy_force_refresh_not_supported`。
`xray_list` 只能匹配完整冻结 Study 的 asset ID 顺序，部分图像选择 fail-closed。

#### `DalBase`（数据访问基类）查询合同

所有兼容查询继续遵守 `API → Service → XxxDal(DalBase) → Model/DB`：

1. 单实体、按条件取最新一条，使用实体 DAL 继承的 `self.get_data(...)`，配合
   `v_where`、`v_order="desc"`、`v_order_field="created_at"`、`v_return_none=True`。
2. 分页/列表查询使用 `self.get_datas(...)`，并显式传入 `page`、`limit`、
   `v_return_count=True`、`v_return_objs=True`。
3. `XRayRunDal.get_latest_for_session_operation` 只负责 Run 的 tenant/session/
   operation/study/status 条件；可选 Study revision 通过 `XRayRequestSnapshot` 的
   DalBase join 条件过滤，不访问不存在的 `XRayRun.study_revision` 字段，也不在 Run 表复制 revision。
4. 空的 `execution_statuses=set()` 代表没有匹配项并直接返回 `None`；未传该参数才代表不限制执行状态。
5. 所有查询保留 tenant 条件；Service 额外校验 Session subject、Study/session 绑定和
   RequestSnapshot revision，防止仅凭 `study_id` 或“最新时间”跨 revision 取错 Run。
6. `DalBase` 只使用其异步方法；API、Service、Worker 不直接拼装 SQL、不直接操作
   `AsyncSession` 查询，不引入第二套 Repository/CRUDBase。

源码证据：`app/crud/xray_accuracy/run.py`、`app/crud/xray_accuracy/request_snapshot.py`、
`app/service/xray_accuracy/legacy_compat_service.py`、
`app/api/api_v1/endpoints/xray_legacy_compat.py`、`app/core/crud.py`。

#### 本轮状态与边界

| 验收项 | 结果 | 说明 |
|---|---|---|
| DAL（数据访问层） 使用 `get_data/get_datas` | `PASS-LOCAL` | 已移除对不存在 `XRayRun.study_revision` 的访问 |
| 兼容路由注册、无 `/{id}` | `PASS-LOCAL` | FastAPI route introspection 已验证 |
| Python compile/import/diff check | `PASS-LOCAL` | `compileall`、`import main`、`git diff --check` 通过 |
| 真实影像准备/OSS（对象存储）/Worker（异步工作进程） | `BLOCKED` | source fetcher、OSS（对象存储） 和 live Broker（消息代理） 尚未验收 |
| AI 医学结果/报告 | `NOT_STARTED` | Result/Finding/Review（人工复核）/Report（报告） 和医学 Prompt（提示词） 尚未实现 |

回滚时关闭兼容路由注册即可；不删除 `xray_accuracy_*` 事实行、不软删除历史 Run、不修改旧数据库。
