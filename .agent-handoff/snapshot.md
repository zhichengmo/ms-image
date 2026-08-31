# Handoff Snapshot

## Current State

- Last updated: 2026-08-31（R4A Evaluation 独立库、readiness 与 Fake scorer 技术烟测完成；最终资格标记被主库既存 Alembic 注释漂移暂缓）
- Workspace root: `/Users/mozhicheng/workspace/code/cy-code/ms-image`
- Branch: `codex/xray-evaluation-r4a`
- Base: `e452b34`
- Objective: 将 Evaluation 从在线 metadata/Alembic 中隔离为独立 `ms_image_eval`，并资格化空库重建、既有同构表接管、独立 readiness、Compose 迁移顺序和 Fake scorer 基础设施链；不进入 Dataset、Gold、Runtime 等价 Runner、M1 或 Prompt。
- Current process state: Evaluation Control、Relay、Worker 已停止；8003 无监听。本轮临时 Secret/Token 只存在于已结束进程内，未写文件或输出。

## Completed In This Slice

- 四个 Evaluation ORM 已改用独立 `EvaluationBaseModel.metadata`；在线 `BaseModel.metadata` 不再包含 `evaluation_*`。
- 新增独立 `alembic_evaluation.ini`、`alembic_evaluation_migrations/` 和初始 revision `20260831_eval_01`。
- 独立 migration 已验证空库重建、同构 adoption、部分 schema 拒绝、额外 constraint 拒绝和有数据 downgrade 拒绝。
- 主库 cleanup revision `20260831_01` 已验证非空 fail-closed、空表删除和空结构 downgrade；正式 `ms_image` 已升级到该 revision，四张历史 Evaluation 空表已删除。
- 正式 `ms_image_eval` 已创建并迁移到 `20260831_eval_01`；当前保留 1 个技术烟测 Job、1 个 Outbox、1 个 Run、5 个 Artifact 作为审计记录。
- Evaluation Control 新增公开 `/api/v1/health` 与 `/api/v1/readiness`；真实运行时 database/schema/JWT 三项均 ready、HTTP 200。
- Compose 新增 `evaluation-migrate`；Control/Relay/Worker 等待 migration 成功。Backend 镜像补入独立 Alembic 资产，Evaluation runtime URL 使用 `URL.create()` 安全编码凭据。
- 真实链已完成：Runtime completed Task/Report export → Evaluation Job → Outbox → Relay → RabbitMQ → 单 Worker → Fake scorer → Run/5 Artifacts；Job completed、Run succeeded，5 个 OSS ObjectRef 均通过 HEAD。
- 后端全量测试为 `240 passed, 41 warnings`；Ruff、compileall、Evaluation Alembic current/check、Compose 四种配置、81 路由/98 Postman 对账、JSON 与 diff check 通过。

## Current Qualification Boundary

```text
R4A_IMPLEMENTATION_COMPLETE
EVALUATION_CONTROL_READINESS_RUNTIME_SMOKE_PASSED
EVALUATION_FAKE_SCORER_INFRASTRUCTURE_SMOKE_PASSED
EVALUATION_R4A_FINAL_QUALIFICATION_BLOCKED
MEDICAL_ACCURACY_UNKNOWN
MEDICAL_RELEASE_NO_GO
```

尚未记录计划中的最终 `EVALUATION_R4A_DATABASE_ISOLATION_QUALIFIED` / `EVALUATION_CONTROL_READINESS_QUALIFIED`，原因是在线主库 `alembic check` 暴露既存、非 Evaluation 的 `ai_api_connection.secret_ref` 列注释漂移。R4A 不顺带修改该历史列。

## Blockers and Next Actions

1. 单独审阅主库 `ai_api_connection.secret_ref` 物理注释与 ORM 注释的差异；若用户授权，使用独立最小 migration 修复，再重跑主库 `alembic check`。
2. Docker daemon 当前未运行，`docker build` 无法执行；Compose 静态解析已通过。若需要容器级资格化，启动现有 Docker 环境后只验证镜像构建与 `evaluation-migrate` 启动，不扩展业务范围。
3. 两项关闭后复核脱敏 evidence，记录最终 R4A qualification，分组提交并推送当前分支。
4. R4A 最终关闭后下一独立阶段才是 R4B Dataset 治理；不得跳到 Gold/Scorer、Runner、M1 或 Prompt 优化。

## Evidence

- `docs/evidence/evaluation-r4a/20260831T023611Z/database-isolation.json`
- `docs/evidence/evaluation-r4a/20260831T023611Z/fake-scorer-smoke.json`
- `docs/evidence/evaluation-r4a/20260831T023611Z/validation.json`

## Active Files

- `apps/backend/core/async_db.py`
- `apps/backend/models/evaluation_base.py`
- `apps/backend/models/evaluation.py`
- `alembic_evaluation.ini`
- `alembic_evaluation_migrations/`
- `alembic_migrations/versions/20260831_01_remove_evaluation_tables_from_online.py`
- `apps/backend/services/evaluation_control/`
- `docker-compose.yml`
- `apps/backend/Dockerfile`
- `docs/evidence/evaluation-r4a/20260831T023611Z/`
