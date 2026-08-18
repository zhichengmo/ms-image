# vet-platform 与 ms-image 能力对照

> 中文阅读说明：`comparison matrix` 是“对照矩阵”，`ARCHIVED` 是“已归档”；其余英文术语请参阅[英文术语中英对照](../../../术语中英对照.md)。

> `ARCHIVED / 历史资料`：本文是历史比较快照，不代表当前模块或数据库设计。

状态：`ARCHIVED`（已归档）

当前依据：[MS-Image 最终架构、数据库与完整链路设计](../../../ms-image-final-architecture-and-database-design.md)

历史语境：表中的证据、差距和后续动作只描述比较采集时点，不构成当前实现或迁移计划。

| 能力 | vet-platform 历史采集证据 | ms-image 历史采集证据 | 当时差距 | 历史结论 |
|---|---|---|---|---|
| Provider client（AI 服务提供方客户端） | `app/service/llm_service.py:50-84,1417,2935+` | `app/core/ai/openai_compatible.py:25-94` | 当前仅 OpenAI-compatible（OpenAI 兼容）单连接 | 复用公共 adapter（适配器），后续扩展 family（连接家族） |
| Key health/cooldown（密钥健康度/冷却） | `app/service/xray_v2/key_health.py:258-351` | `ai_request_service.py:207-350` | 当前为进程内存，未持久化 key registry（密钥注册表） | 迁移字段/状态语义，不迁移明文 key（密钥） |
| Model pool/routing（模型池/路由） | `app/service/api_pool_manager.py:55-90` | `AIConnectionPool` | 无 durable（持久化）priority（优先级）/score（评分）/model pool（模型池）表 | 先保留 in-memory（内存态），后续 DB（数据库）/DAL（数据访问层）合同 |
| Prompt governance（提示词治理） | `app/service/llm_service.py`、参考 Prompt DAL（提示词数据访问层） | `prompt_service.py:92-174` | 当前只有 XRay 文件 manifest（X 光文件清单） | 抽公共 Registry engine（注册表引擎），内容按 modality（模态）隔离 |
| Request log/stats（请求日志/统计） | `ai_request_log`、`api_request_stats` | `xray_accuracy_model_call`、Trace（技术追踪） | token（令牌计数）未写入；无参考 DB（数据库）数据 | 只迁移脱敏统计字段 |
| Async execution（异步执行） | 参考 Celery/RabbitMQ | `app/core/messaging/`、XRay worker（X 光工作进程） | 生产部署/恢复证据缺失；admin（管理端）手动入口存在 | 复用现有 Outbox（事务发件箱）/Relay（中继） |
| Readiness（就绪性） | 参考 health（健康检查）对 DB（数据库）/Redis/Alembic | `app/core/readiness.py` | Provider qualification（AI 服务提供方资格验证）主要信任 env flag（环境开关） | fail-closed（失败即关闭），待 qualification artifact（资格验证证据产物） |
| Provider/API key（AI 服务提供方/接口密钥） | `ai_api_connection.api_key` 明文、`key_health.py` fingerprint（指纹）/cooldown（冷却）/lease（租约） | `ProviderRuntimeConfig` + `AIConnectionConfig.api_key_ref`，无持久化 key（密钥） | 无 secret manager（密钥管理器）/rotation（轮换）实证；参考实现存在明文风险 | 只迁移 key ref（密钥引用）/fingerprint（指纹）/health（健康状态）语义，禁止复制明文 |
| Request pool（请求池） | `LlmRequest.send_batch_requests` + semaphore（信号量）/race（竞速）/fallback（降级） | `XRayAIRequestService` + `AIRequestPolicy`，进程内 pool（连接池） | 尚未抽成 modality-neutral（模态无关）公共类 | 抽公共 pool（连接池），XRay（X 光）仅做 adapter（适配器） |
| Execution plan（执行计划） | `AiStage/AiStagePlan/AiStageRound` + `AiGovernanceRuntimeService` | 当前只有 Prompt manifest（提示词清单）和 `stage_key` 白名单 | 无治理 DB（数据库）/plan（计划）/revision（修订版本）的 live（在线）证据 | 先冻结 manifest（清单）/contract（合同），授权后再映射 DAL（数据访问层） |
| 请求日志与统计 | `ai_request_log`、`api_request_stats`，可含 raw prompt/output（原始提示词/输出） | `xray_accuracy_model_call`、Trace（技术追踪），保存 hash（摘要）/receipt（回执）摘要 | 真实 Provider qualification（AI 服务提供方资格验证）不落库 | 只迁移非敏感统计和审计摘要 |
| GitHub（代码托管平台）参照 | LiteLLM、Portkey、Langfuse、OpenLLMetry、Celery/RabbitMQ、OpenAI Python | 见 [`github-reference-verification.md`](../../../artifacts/github-reference-verification.md) | 引入 Proxy（代理）/Node（Node.js 运行时）/观测数据库会扩大边界 | 只借鉴 SDK（软件开发工具包）/语义，不引入新网关 |
