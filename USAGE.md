# MS-Image 本地运行与开发指南

状态：`CURRENT_RUNTIME_GUIDE`（当前运行指南）

说明：本文描述当前仓库可以执行的工程操作，不表示目标通用影像架构已经实现。

## 1. 环境要求

- Python 3.11
- MySQL 8.0
- Redis 7
- RabbitMQ 3.13：只有启用 `broker`（消息代理）Profile 时需要
- OSS（对象存储）和 AI Provider（AI 服务提供方）凭证：只有进行已授权的真实资格验证时需要

所有 Secret（密钥）必须通过本地环境或批准的 Secret Manager（密钥管理服务）注入，不得写入文档、代码、数据库明文字段或提交到 Git。

## 2. 本地安装

```bash
cd /Users/mozhicheng/workspace/code/cy-code/ms-image
python -m venv .venv
source .venv/bin/activate
pip install -r apps/runtime/requirements.txt
cp .env.example .env-01
```

`.env-01` 是当前 `Settings`（配置对象）读取的本地环境文件。只填写本机所需配置，不提交真实密钥。

常用配置：

```dotenv
APPLICATION_NAME=Ms Image Service
APPLICATION_PORT=8000
ENV=dev

MYSQL_DB=ms_image
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PW=

REDIS_HOST=127.0.0.1
REDIS_PORT=6379

BROKER_ENABLED=false
```

## 3. 启动方式

### 3.1 同时启动用户端和管理端

```bash
python apps/runtime/run_servers.py
```

### 3.2 分别启动

```bash
python apps/runtime/start_user_api.py
python apps/runtime/start_admin_api.py
```

从仓库根目录直接使用模块路径时，Runtime 会自动注入唯一的
`apps/runtime` import root；Worker 也可以使用同一套 fully-qualified module path：

```bash
uvicorn apps.runtime.main:app --host 0.0.0.0 --port 8000
celery -A apps.runtime.workers.imaging_worker.celery_app:celery_app worker \
  --loglevel=INFO --queues=imaging.image.validate
```

Compose 容器仍使用镜像内 `/app` 作为 import root，不需要复制第二份 `app` 或 `workers` 源码。

### 3.3 Docker Compose（容器编排）

默认启动用户 API、管理 API、在线 MySQL、隔离 Evaluation MySQL 和 Redis：

```bash
docker compose up --build
```

启用当前 XRay validation-only（X 光仅验证）的 Relay（中继）和 Worker（工作进程）：

```bash
BROKER_ENABLED=true docker compose --profile broker up --build
```

这里的 imaging/evaluation Worker 和 Relay 使用 `broker` Profile；它们仍是当前 Runtime 代码域的一部分，不代表 AI Control 或 Evaluation Control 已独立部署。

## 4. 本地地址

| 用途 | 地址 | 说明 |
|---|---|---|
| 用户 API 文档 | `http://localhost:8000/docs` | 开发环境 OpenAPI（接口规范） |
| 管理 API 文档 | `http://localhost:8001/docs` | 受管理端鉴权约束 |
| 健康检查 | `http://localhost:8000/api/v1/health` | 只证明进程可响应 |
| 用户依赖就绪 | `http://localhost:8000/api/v1/readiness` | 检查 Redis/数据库等当前依赖 |
| 管理依赖就绪 | `http://localhost:8001/api/v1/readiness` | 需要管理身份与 scope（作用域） |
| RabbitMQ 管理界面 | `http://localhost:15672` | 仅 `broker` Profile |

健康检查、readiness（就绪检查）、Provider 调用成功和工程测试均不能证明医学准确率。

## 5. 当前与目标的区别

| 范围 | 当前事实 | 目标设计 |
|---|---|---|
| 影像领域模型 | Runtime 已有公共 Session/Study/Series/Image/Task/Stage/Report 链 | 后续继续按模态资格化 |
| 执行器 | `ImagingExecutionService + StageRegistry + 固定 Profile`，Broker worker/relay 仍在 Runtime | 按需拆分无状态跨服务合同 |
| 数据库 | Compose 提供独立 `ms_image` / `ms_image_eval`，尚未迁移 schema | 在线候选 10 表 + Evaluation 候选 4 表 |
| 医学链 | provider-disabled 工程链已闭环，真实 Provider/准确率仍未知 | Primary 基线 + Targeted 实验链 |
| 发布状态 | `PARTIAL / NO-GO` | 必须通过工程、Provider、paired A/B 和 Holdout 门禁 |

精确差距见 [重构迁移与验证计划](docs/refactor/06-refactor-migration-and-validation-plan.md)。

## 6. 开发分层

新增业务实体按以下顺序实现：

```text
Model（数据库模型）
-> Schema（接口结构）
-> DAL（数据访问层，继承 DalBase）
-> Service（业务服务层）
-> API（接口层，通过依赖注入调用 Service）
```

必须遵守：

- API 不直接访问数据库，不编排多个 DAL。
- Service 接收 `AsyncSession`，负责业务校验、状态流转、幂等和多实体编排。
- CRUD/DAL 统一继承 `app.core.crud.DalBase`；不得绕过基类直接操作 session。
- Model 不承载 HTTP（网络接口）语义；Schema 不访问数据库。
- 资源 ID 放 query（查询参数）或 request body（请求体），不使用 `/{id}`。
- OSS、Broker 和 Provider 外部 I/O 不得在数据库事务内执行。
- 状态、类型等可演进字段使用 string/json/timestamp，并在 SQLAlchemy `comment` 中写候选类型和中文含义。
- 不使用 Foreign Key（外键）、数据库 Enum（枚举）、联合主键或目标 `tenant_id`。

## 7. XRay Profile（X 光流程配置）

```text
xray_primary_v1:
StudyPreparation -> JointPrimaryReader -> DecisionFinalization -> Report

xray_targeted_review_v1:
StudyPreparation -> JointPrimaryReader -> FamilyRouting
-> primary_final -> DecisionFinalization
或
-> targeted_review -> TargetedReview -> DecisionFinalization
-> Report
```

- FamilyRouting 仅属于 Targeted 实验 Profile。
- TargetedReview 最多一次，必须输出完整病例结果。
- TargetedReview 技术失败不得回退 Primary。
- Profile、Prompt（提示词）、Schema（结构合同）、模型和预算必须冻结到 Task 快照。

## 8. 数据库与迁移

目标数据库设计见[数据库与 OSS 设计](docs/refactor/03-database-and-storage-design.md)和[设计母文](docs/ms-image-final-architecture-and-database-design.md)。

未经用户明确授权：

- 不生成 Alembic（数据库迁移）脚本。
- 不执行 `alembic upgrade` 或真实数据库写操作。
- 不迁移旧 XRay 数据、Prompt、Provider Key 或 OSS 对象。
- 不删除、重命名或双写生产表。

迁移获得授权后，也必须先核对真实 schema、数据量、Secret、owner、回滚和验证门禁，不能直接按目标文档推断数据库现状。

## 9. 验证原则

可以运行仓库已有的非破坏性检查，但必须分别报告：

- engineering validity（工程有效性）
- execution completion（执行完成情况）
- medical accuracy（医学准确率）

医学准确率只能由冻结 Gold、同病例 Paired A/B、确定性 scorer（评分器）和隔离 Holdout 证明。不得因为单例结果更详细、Provider 成功或测试通过就宣称准确率提高。

## 10. 故障排查

### 端口占用

```bash
lsof -i :8000
lsof -i :8001
```

### MySQL 或 Redis 未就绪

先检查 `/api/v1/readiness` 的组件状态，再核对 `.env-01`。不要把连接密码粘贴到日志或文档。

### Broker 未消费

确认使用了 `--profile broker` 且 `BROKER_ENABLED=true`，再检查 Relay、Worker 和 RabbitMQ 状态。重复消息由数据库 CAS/lease 处理，不能依赖 Broker 恰好只投递一次。

### AI Provider 不可用

缺少模型资格、签名 Artifact（证据产物）或 Secret 时应 fail closed（失败关闭）。禁止自动换模型、换 Prompt 或把 Stub（桩实现）结果当作医学报告。
