# ADR（架构决策记录）-P0-E-001：Broker（消息代理）、Worker（异步工作进程）与 Outbox（事务发件箱）边界

> 中文阅读说明：`Broker` 是消息代理，`Worker` 是异步执行进程，`Outbox` 是事务发件箱；其余英文术语请参阅[英文术语中英对照](../术语中英对照.md)。

状态：`IMPLEMENTED-LOCAL`（本地已实现）/ `PENDING-PRODUCTION-APPROVAL`（等待生产审批）

日期：2026-08-09

## 决策范围

本 ADR 已完成拓扑、消息白名单、Outbox 事务边界和恢复语义的设计；当前仅有
DB-backed Worker 与 deterministic replay 证据，未获得 Docker/RabbitMQ/Celery 的 live
消费证据。它不启动医学诊断或自动医学结论。XRayTechnicalWorker 仍复用现有
DalBase/AsyncSession；生产 Broker、部署 schema、恢复演练和真实 Provider qualification
需要单独审批证据。

## 候选与选择

选择 `RabbitMQ + Celery` 作为异步执行实现：仓库已有 Celery/Kombu 依赖，
RabbitMQ 提供确认、重投、DLQ 和消费超时语义；Celery 负责 Worker 生命周期。
该选择的生产启用仍需平台/SRE/后端审批；`.env.example` 保持
`BROKER_ENABLED=false`，Compose qualification 才显式覆盖为 true。

## 拓扑（冻结草案）

- exchange：`xray.v2`
- routing keys：`xray.run.stage.requested`、`xray.run.stage.retry`、
  `xray.run.stage.dead`
- queue：`xray.stage.requested`、`xray.stage.retry`、`xray.stage.dlq`
- TTL：普通消息 15 分钟；重试消息按退避表递增，具体数值需在审批 artifact 中固定。
- ack：成功处理且状态 CAS/trace 写入完成后 ack；异常按重试策略 nack/requeue。
- DLQ：超过最大重试、不可解析消息、schema 白名单违规消息进入 DLQ，禁止静默丢弃。

## 消息白名单

消息只能携带：
`run_id`、`task_id`、`stage_key`、`release_fingerprint`、
`expected_version`、`trace_namespace`。

不得携带 Prompt、图像 bytes、signed URL、truth、历史输出或医学结论。

## 事实源与事务

MySQL Run/Checkpoint/Outbox 是状态事实源。创建 Run、RequestSnapshot、
StageCheckpoint 和 Outbox 必须使用同一 `AsyncSession` 事务；commit 后由
relay 发布。Celery result backend 与 Redis 均不是事实源。消费者必须以
`task_id/event_id` 幂等，并使用 `expected_version` 做 CAS。

本地 replay/technical-worker qualification 进一步要求：Run 必须先由可信 tenant-scoped lookup
注册 `tenant_id/release_fingerprint/trace_namespace`；Worker claim 使用 owner/lease/
heartbeat，过期由 reconcile 恢复；CAS 冲突保持可重试，不进入 DLQ；技术 final writer
只能成功一次，取消后的迟到结果只写 late trace。上述语义已由 deterministic replay
与临时 MySQL 直连验收；未证明 RabbitMQ/Celery live 消费，生产并发/恢复演练仍未完成。

## 恢复约束

Worker crash 由 lease/heartbeat 过期检测；reconcile 处理 orphan Run；取消后的
late result 只能写 late trace，不得推进 final/release；重复投递不得产生第二个
final；CAS 冲突不得覆盖新状态。

## 审批门禁

批准人：异步基础设施负责人、SRE、后端负责人。生产批准前不得将生产环境的
`BROKER_ENABLED` 改为 `true`；本地 Compose qualification 的显式覆盖不代表生产验收。
