# Phase 1（第 1 阶段）零模型 Run（运行）/Trace（追踪）/Outbox（事务发件箱）链路增量

> 中文阅读说明：`Phase` 是“阶段”，`Run/Trace/Outbox` 分别是“运行记录/追踪记录/事务发件箱”；其余英文术语请参阅[英文术语中英对照](../术语中英对照.md)。

状态：`PARTIAL`（部分完成）/ `VALIDATION-ONLY`（仅验证）

本增量用于先收口工程链路，再进入准确率整理。它不接真实 Provider、不生成医学结论、
不创建迁移或测试脚本。

## 当前链路

```text
HTTP JWT + tenant
  -> API (/api/v1/xray/*)
  -> XRayRunService / XRayTraceService
  -> XRay*Dal (app.core.crud.DalBase)
  -> SQLAlchemy Model/DB (Run/Snapshot/Checkpoint/Trace/Outbox)
```

Committed Outbox execution boundary:

```text
Outbox event_id + tenant
  -> XRayTechnicalWorker.execute_outbox_event
  -> Outbox relay lease/CAS
  -> TechnicalExecutor
  -> Prompt -> AI pool -> ModelCall -> Checkpoint/Run/Trace
  -> Outbox published/retry/dead_letter
```

Admin 只读控制面：

```text
Admin JWT + xray:admin:read + tenant
  -> /admin/api/v1/xray/control/runs
  -> same Service -> tenant-scoped DAL
```

## 已实现合同

- `POST /api/v1/xray/runs`：validation-only、request body `extra=forbid`、tenant/subject
  来自 JWT，创建 Run、RequestSnapshot（含不可变 `study_revision`）、StageCheckpoint、TraceEvent
  和 Outbox 草案。
- 当前最小手工调用已验证合法 payload 经过 `XRayRunService.create_run` 后同时生成 queued
  Run、Snapshot、Checkpoint、初始 Trace 和 request_gate Outbox 消息；该调用使用 fake DAL
  作为无 live schema 环境的 qualification，不替代 MySQL 事务验收。
- `GET /api/v1/xray/runs?run_id=`：ID 只走 query，始终 tenant filter。
- `POST /api/v1/xray/run-cancellations`：body 携带 `run_id/expected_version`，CAS 失败返回
  冲突；API 先将 Run 推进到 `cancel_requested` 并写 `run_cancel_requested` Trace，随后由
  cancel Outbox/Worker 使用同一 tenant、release、trace 和 expected_version 合同 CAS 推进到
  `cancelled`，写入唯一 `run_cancelled` Trace。重复 cancel delivery 只返回已取消状态，不再推进
  `state_version` 或重复写终态 Trace。
- `GET /api/v1/xray/traces?run_id=`：只读技术 Trace，跨租户表现为 Run 不存在。
- Admin `GET /api/v1/xray/control/runs?run_id=`：独立 admin JWT scope + tenant filter。
- Outbox message 只允许：`run_id/task_id/stage_key/release_fingerprint/expected_version/trace_namespace`；Outbox
  记录另外保存 `event_id/aggregate_type/aggregate_id/event_type/message_payload_hash/`
  `message_whitelist_version/attempt_count/last_error` 供 relay 对账，但这些字段不进入消息体。
- `event_id` 与 `task_id` 使用不同 opaque UUID；`XRayOutboxDal` 在 flush 前校验消息字段集合、
  规范化 SHA256、白名单版本、聚合/Run/trace/release 对齐和发布状态，避免仅依赖数据库 comment。
- 输入递归拒绝 `ABN/NOR/disease_code/filename/path/history/truth/annotation/OCR/EXIF/
  failure_bank/score/diagnosis/previous_output` 等字段；命中时不进入 Provider。
- `ai_medical_status=not_produced`；replay 只有技术 completion 的 write-once guard，没有医学
  final writer、Provider、Prompt、scorer 或医学 override。
- `prompts/xray_accuracy/request_gate.v1.txt` 与 `XRayPromptRegistry` 提供不可变 Prompt
  revision/manifest：runtime 只接受 `published + active`，按 `module_key + prompt_key + version + language`
  选择，中文请求缺失时显式记录英文 fallback，并校验变量白名单、checksum、TTL cache、
  force refresh、variables JSON、rendered SHA256 和递归泄漏门；当前资产 checksum 已 pin，
  同版本同语言重复 revision 会拒绝，不允许静默选择歧义内容。
- `AIConnectionPool` 提供不触网的多连接工程合同：全局 semaphore、hard/grace timeout、
  transport/429 精确重试、Retry-After、指数退避、失败连接 cooldown、已尝试连接排除、
  备用连接 fallback 和脱敏请求级 trace。参数/schema/不可恢复错误不重试；trace sink 失败
  不阻断主调用。当前 provider factory 只能返回 `StubAIProvider`，连接只使用 `replay://`。
- `XRayAIRequestService` 生成严格技术响应并将 ModelCall fingerprint/receipt、Prompt/Schema
  checksum、实际语言、retry/fallback 和请求 trace 通过 `XRayModelCallDal` 持久化。
  响应校验由已加载 JSON schema 的 required/properties/const 合同驱动；每次 Service 调用有
  独立 request nonce；StageCheckpoint 保持逻辑 task 标识，Provider physical attempt id 在
  retry/re-delivery 间不复用并写入 ModelCall/receipt。
  `TechnicalExecutor` 将 Outbox request_gate 消息串到 Checkpoint → Prompt → AI stub →
  ModelCall → Trace → Run technical completion；stub 永不产生医学 verdict，未 qualification
  的真实 Provider 会被拒绝。
- Run 幂等键由 `(tenant_id, request_id, contract_version)` 唯一约束草案保护；CAS 更新通过
  `DalBase.cas_put_data` 的版本条件保护。
- StageCheckpoint 的 claim、heartbeat、complete、fail、lease 过期恢复由
  `XRayStageCheckpointDal` 统一封装；完成/失败写入要求 owner 与未过期 lease，避免旧
  worker 在 reconcile 窗口覆盖新状态。Outbox relay 的 claim、heartbeat、published、retry、
  dead-letter、lease 恢复由 `XRayOutboxDal` 统一封装，并要求 tenant、owner、lease 和状态
  条件同时匹配。
- `workers/xray_accuracy_worker/replay.py` 提供无 Broker 的重复投递、CAS、取消、迟到 Trace、
  阶段白名单、release/trace/tenant 注册绑定、Run/StageCheckpoint lease/heartbeat、orphan
  recovery、final write-once 和非法消息结构化 DLQ 生命周期；不创建 Celery consumer，DLQ
  仍为内存演练而非持久化事实源。
- `workers/xray_accuracy_worker/technical_worker.py` 提供可被正式 Broker consumer 复用的
  DB-backed 执行入口：`execute_message` 消费白名单消息，`execute_outbox_event` 在本地
  qualification 中同一事务内 claim Outbox、调用 Executor、写成功/失败状态并确认 Outbox；
  Executor CAS 冲突进入 retry，非法消息/不可恢复输出进入 dead-letter，不会被错误标记
  published。
- `ReplayOutboxRelay` 只演练 enqueue、重复事件、retry/backoff、published write-once 和
  dead-letter 脱敏；不连接 RabbitMQ，不把内存状态当作 MySQL Outbox 事实源。
- 迟到消息先经过终态/取消判定，再进行 Run CAS；即使携带旧 `expected_version`，也只能追加
  late trace，不得被误报为可写的 CAS 冲突或重新打开终态；queued/retry/running checkpoint
  都能安全转为 late，确定性 Trace id 使用幂等 append-or-read。
- 取消请求在 `cancel_requested` 或已完成的 `cancelled` 状态下允许携带当前/前一 CAS
  版本重试并返回同一技术状态；更旧版本仍返回冲突。Worker 只接受与 Run 绑定一致的
  release/trace/tenant 和当前 `expected_version`，CAS 冲突进入 retry，不得直接 published。
- Run API 把业务/DB 异常转换成 HTTP 响应前显式 rollback，防止 session dependency 将部分
  Run/Snapshot/Checkpoint/Trace/Outbox 图误提交；TechnicalExecutor 的已持久化技术失败返回
  结构化 retry/failed 结果，由调用事务正常提交，不产生 normal/abnormal。

## 未完成/门禁

- 模型尚未经过 Alembic migration（本阶段明确不创建 migration）。
- DB-backed 运行、真实 RabbitMQ/Celery consumer、lease reconcile、DLQ 持久化尚未验收；当前
  technical worker 入口只可在取得 migration/数据库和 broker 授权后启用。
- 真实 Provider adapter、Provider receipt qualification、Study/Image EngineeringGate、医学节点、
  accuracy 评估全部保持未开始。
- G0/P0 仍未通过，当前 skeleton 不能用于生产，也不能产生医学准确率声明。

## 证据

- 代码：`app/api/api_v1/endpoints/xray_runs.py`、`app/api/admin_v1/endpoints/xray_control.py`。
- Service：`app/service/xray_accuracy/`。
- DAL：`app/crud/xray_accuracy/`。
- Prompt/AI：`prompts/xray_accuracy/`、`app/service/xray_accuracy/prompt_service.py`、
  `app/service/xray_accuracy/ai_request_service.py`、`app/service/xray_accuracy/technical_executor.py`。
- Model 草案：`app/models/xray_accuracy/`。
- Replay：`workers/xray_accuracy_worker/`、`evaluation/replay/`。
- Replay smoke artifact：[`p1-zero-model-replay.json`](p1-zero-model-replay.json)。
- Worker entrypoint：`workers/xray_accuracy_worker/technical_worker.py`。

## 本地验证（2026-08-09 23:54，脱敏配置）

- 缺少 DB 时，带有效 tenant JWT 的 Run 受理返回 `503/SERVICE_NOT_READY`。
- `safe_metadata.truth` 命中 leakage preflight，返回 `422/4002`，不创建 Provider 调用。
- 未认证 XRay 路由返回 `401`；未提供 tenant claim 的已签名 token 返回 `403`。
- Prompt published/active、missing/draft/archived 拒绝、英文 fallback、变量白名单、checksum、
  cache/force-refresh 合同通过；AI pool stub success、timeout、429、transport retry、Retry-After、
  fallback、cooldown、schema failure 和非阻断 trace sink 通过。
- replay 的 Prompt → AI → ModelCall → Checkpoint → Run → Trace、duplicate/cancel/late/orphan/DLQ
  及 retryable transport / non-retryable schema failure 均通过；医学 verdict 仍未产出。
- 这些结果不替代 live MySQL schema、跨租户 DB 回归或网关验证。
