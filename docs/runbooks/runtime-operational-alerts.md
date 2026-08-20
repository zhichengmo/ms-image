# Runtime 运行告警 Runbook

状态：`PHASE_2A_IMPLEMENTED / NOT_RUNTIME_VALIDATED`

适用范围：admin API 的 `/api/v1/operations/status`（Compose 默认地址为 `http://127.0.0.1:8001/api/v1/operations/status`）的 `alerts` 投影。该接口只返回聚合、非敏感运行事实，不返回资源 ID、对象引用、报告内容、请求内容、URL、异常原文或 Secret。

## 合同

每条告警固定包含 `code`、`severity`、`source`、`observed_value`、`threshold`、`unit`、`captured_at` 与 `summary`。`critical` 表示需要立即停止扩大影响并升级；`warning` 表示需要在值班窗口内调查。它们表达工程运行或 Evaluation 证据质量风险，不表达医学准确率或医学结论。

告警开关和阈值来自 Runtime Settings。`OPERATIONAL_ALERTS_ENABLED=false` 关闭整个投影；任意数值阈值设为 `0` 会关闭对应规则。默认值为：lease count `1`、活动/unknown age `300` 秒、queue depth `100`、DLQ depth `1`、consumer minimum `1`，以及每种 Evaluation 证据指标 `1`。

`oldest_message_age_seconds` 在 AMQP queue.declare 中明确为 unsupported，不产生“消息最老年龄”告警，也不得以 `0` 代替未知值。

## 安全规则

- 先确认同一告警的连续快照和 `captured_at`，再进入人工排查。
- 不自动重跑 Provider、不改 Prompt、不改模型、不删除消息、不人工改写 Task、Stage、Report 或 Evaluation 结果。
- 不将 `provider-disabled` 或 `target_provider_not_qualified` 视为生产故障告警；它们是当前已知资格化边界。
- 需要从日志、Broker 管理端或数据库取得更多细节时，只能由获授权人员在对应系统内完成，且不得把凭证或医学内容复制到告警处理记录。

## 告警处理

| Code | 触发条件与含义 | 首个安全动作 | 禁止自动操作 | 升级条件 |
|---|---|---|---|---|
| `online_database_unavailable` | 在线数据库 readiness 为 false。 | 核对服务实例、连接池健康和受批准的数据库监控。 | 重启后假定恢复、修改数据。 | 连续两个快照或影响 API。 |
| `evaluation_database_unavailable` | Evaluation 数据库 readiness 为 false。 | 核对 Evaluation 独立连接与数据库监控。 | 将 Evaluation 切回在线数据库。 | 连续两个快照或 Job 无法推进。 |
| `redis_unavailable` | Redis readiness 为 false。 | 核对 Redis 监控与 Runtime 网络健康。 | 清空缓存或改写 Task 状态。 | 连续两个快照或 API 受影响。 |
| `online_outbox_expired_relay_leases` | 在线 Outbox 过期 Relay lease 达阈值。 | 核对 Relay 进程存活和 lease reconcile 指标。 | 删除 Outbox 行或手工确认已发布。 | 值持续增长或达到 critical。 |
| `online_outbox_active_age_high` | 在线 Outbox 最早活动事件超过年龄阈值。 | 核对队列积压和 Relay 消费速率。 | 重发未知事件或修改 payload。 | 持续两个采样窗口。 |
| `online_stage_expired_running_leases` | 在线 Stage 过期运行 lease 达阈值。 | 核对 Imaging Worker、lease reconcile 与失败率。 | 直接完成 Stage 或改写结果。 | 影响同一 Task 类型的多项执行。 |
| `online_stage_active_age_high` | 在线 Stage 最早活动执行超过年龄阈值。 | 核对 Worker 容量和当前队列深度。 | 取消正常运行中的 Stage。 | 持续两个采样窗口。 |
| `online_ai_call_unknown_age_high` | 最早 unknown AICall 超过年龄阈值。 | 核对 receipt/reconcile 流程和 Provider 资格记录。 | 自动重发 Provider 或替换 Prompt。 | unknown 数量或年龄持续增加。 |
| `evaluation_job_expired_running_leases` | Evaluation Job 过期运行 lease 达阈值。 | 核对 Evaluation Worker 与 Job reconcile。 | 手工改写 Job/Run 终态。 | Job 积压或重复 lease 增长。 |
| `evaluation_job_active_age_high` | Evaluation Job 最早活动执行超过年龄阈值。 | 核对 Evaluation Worker 容量和 Artifact I/O。 | 跳过 case 或改写分母。 | 持续两个采样窗口。 |
| `evaluation_outbox_expired_relay_leases` | Evaluation Outbox 过期 Relay lease 达阈值。 | 核对 Evaluation Relay 和 Broker publish confirm。 | 删除 Outbox 行或伪造 published。 | 值持续增长。 |
| `evaluation_outbox_active_age_high` | Evaluation Outbox 最早活动事件超过年龄阈值。 | 核对 Relay 消费速率和 broker 状态。 | 重发未知事件或改写 message hash。 | 持续两个采样窗口。 |
| `evaluation_missing_rows` | 最近聚合 Evaluation Run 的 missing rows 达阈值。 | 核对输入 manifest、Artifact 可用性和运行失败分类。 | 从分母移除 missing rows。 | 影响多个 Run 或比率上升。 |
| `evaluation_invalid_comparisons` | 最近聚合 Run 的 invalid comparison 达阈值。 | 核对 schedule、fingerprint 与配对前提。 | 将 invalid comparison 当作可比较结果。 | 候选发布决策依赖该批结果。 |
| `evaluation_coverage_loss` | 最近聚合 Run 的 coverage loss 达阈值。 | 核对 case 可用性和技术失败分类。 | 将 coverage loss 解释为医学结论。 | 覆盖损失持续扩大。 |
| `evaluation_technical_failures` | 最近聚合 Run 的技术失败数达阈值。 | 核对 Worker、Artifact I/O 和稳定错误码。 | 把技术失败标记为医学失败。 | 影响多个 Run 或 Run 无法完成。 |
| `evaluation_artifact_drift` | Artifact hash drift 达阈值。 | 停止使用受影响 Artifact，核对 ObjectRef 与 hash 校验链。 | 覆盖对象、修改 hash 或继续发布结论。 | 任意一次发生即升级。 |
| `imaging_broker_consumer_unavailable` | Imaging Broker 已启用但 consumer 未就绪。 | 核对 Imaging Worker 进程、部署版本和 Broker 连接。 | 修改 queue 绑定或清空队列。 | 连续两个快照或 queue 增长。 |
| `imaging_broker_queue_depth_high` | Imaging queue depth 达阈值。 | 核对 Worker 容量、消费速率和 Relay 发布速率。 | 丢弃、重新排序或手动确认消息。 | 持续两个采样窗口。 |
| `imaging_broker_dlq_depth_high` | Imaging DLQ depth 达阈值。 | 核对稳定错误码、消息版本和处理器兼容性。 | 自动重投 DLQ 或删除失败消息。 | 任意非零默认阈值即升级。 |
| `evaluation_broker_consumer_unavailable` | Evaluation Broker 已启用但 consumer 未就绪。 | 核对 Evaluation Worker 进程、部署版本和 Broker 连接。 | 将任务改投在线队列。 | 连续两个快照或 queue 增长。 |
| `evaluation_broker_queue_depth_high` | Evaluation queue depth 达阈值。 | 核对 Worker 容量、消费速率和 Relay 发布速率。 | 丢弃、重新排序或手动确认消息。 | 持续两个采样窗口。 |
| `evaluation_broker_dlq_depth_high` | Evaluation DLQ depth 达阈值。 | 核对稳定错误码、消息版本和处理器兼容性。 | 自动重投 DLQ 或删除失败消息。 | 任意非零默认阈值即升级。 |

## 收口条件

本 Runbook 只定义软件合同与安全响应。它不证明 Runtime 已连接真实 MySQL、Redis、RabbitMQ、OSS 或 Provider，也不证明医学准确率、医学发布或生产就绪。
