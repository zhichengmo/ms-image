# AI（人工智能）请求基础设施迁移审计、封装边界与实施结论

> 中文阅读说明：`AI infrastructure migration report` 是“AI 基础设施迁移报告”；其余英文术语请参阅[英文术语中英对照](../../../术语中英对照.md)。

> `ARCHIVED / 历史资料`：本文是历史审计结论，当前工程状态以 `docs/artifacts` 最新证据为准。本文中的 `XRayRunService（XRay 运行服务）`、`XRayTechnicalWorker（XRay 技术执行工作进程）`、`XRayPromptRegistry（XRay 提示词注册表）` 等名称均为历史实现符号，完整中文用途见[术语表](../../../术语中英对照.md)。

状态：`ARCHIVED`（已归档）

当前依据：[MS-Image 最终架构、数据库与完整链路设计](../../../ms-image-final-architecture-and-database-design.md)；工程证据按 [Artifact 索引](../../../artifacts/README.md) 逐项核验。

历史语境：本文后文的“当前”“已实施”“下一轮”“最终推荐”和 `CONFIRMED` 均限定于报告采集时点，不表示现在的仓库、环境或生产状态。

## 1. 结论摘要

历史采集时点结论：`PARTIAL / NO-GO`。

- `ms-image` 的 validation-only Stub/Replay 链路已形成 `HTTP → Service → DalBase → MySQL（独立测试库 qualification）→ Outbox → Worker → Prompt → Provider Adapter → ModelCall → Checkpoint → Run → Trace` 的工程骨架；去冗余 schema 上的重新执行证据见 `docs/artifacts/p0-imaging-test-db-qualification-rerun.json`。
- 共享 Broker/Celery、Transactional Outbox、Provider HTTP Client 已抽出，但公共配置仍有 XRay 前缀兼容绑定；多影像适配器注册合同尚未完成。
- 真实 Provider 未通过 qualification。当前环境命令返回 `provider_disabled`；此前真实 endpoint 检查曾返回 `provider_auth`，因此不得设置 `XRAY_PROVIDER_QUALIFIED=true`。
- 参考项目数据库已完成本机 Unix socket 只读核验；参考 `.env` 的 `MYSQL_PW` 为空导致 TCP 方式阻断，但 `vet_platform` 本机库可安全读取非敏感表结构、数量和状态分布；结果见 `docs/artifacts/reference-db-readonly-live.json`。
- Docker daemon、生产代理、部署 schema、Alembic migration、生产 Broker 恢复演练和 G0 审批均未完成。
- 没有进入医学诊断、truth、scorer、准确率、真实 Provider 或原始影像数据修改。
- 去冗余数据库重设计已单独记录于 `docs/history/xray/design/xray-accuracy-database-redesign.md`；已在独立本机 MySQL 9.3 测试库创建并调整 6 张兼容命名表，原有数据库未修改，生产 migration 仍未执行。

## 2. 历史证据边界与事实等级

本报告在采集时以以下文件和当时工作树为准：

1. `/Users/mozhicheng/.codex/attachments/2f5d5382-3d63-4f70-9385-ad39c46f00df/goal-objective.md`
2. `docs/history/xray/design/xray-accuracy-detailed-development-document.md`（历史架构设计基线）
3. `docs/history/xray/plans/xray-accuracy-phase0-development-plan.md`（历史工程状态记录）
4. 采集时源码、脱敏运行输出和 artifacts。

状态含义：

- `CONFIRMED`：源码或当前命令直接证明。
- `PARTIAL`：存在可复用能力，但合同、部署或证据不完整。
- `PROPOSED`：迁移设计，尚未实现。
- `UNKNOWN`：缺少可验证证据。
- `BLOCKED`：需要外部凭证、部署或审批才能继续。

## 3. 参考项目配置与 Provider（AI 服务提供方）审计

参考项目：`/Users/mozhicheng/workspace/code/py-project-v2/vet-platform-system/vet-platform`。

| 能力 | 证据 | 结论 |
|---|---|---|
| MySQL（关系型数据库）/Redis（内存数据存储）/RabbitMQ（消息代理）/OSS（对象存储）/JWT（JSON Web Token）/Gemini（模型服务）配置 | `core/config.py:5-58` | `CONFIRMED`（已确认），配置集中在 Settings（设置）；不迁移明文 secret（密钥） |
| Celery（异步任务框架）并发、LLM race（大模型竞速）、worker（工作进程）参数 | `core/config.py:71-90` | `CONFIRMED`（已确认），只迁移可靠投递和资源治理语义 |
| AI client（AI 客户端）复用、最大重试和超时 | `app/service/llm_service.py:50-84` | `CONFIRMED`（已确认），AsyncOpenAI client（异步 OpenAI 客户端）复用、`max_retries=0`、timeout（超时）300s、全局 semaphore（信号量） |
| 单连接、lease（租约）、timeout（超时）、outer grace（外层宽限期） | `app/service/llm_service.py:2935-3154` | `CONFIRMED`（已确认），可迁移为 Provider（AI 服务提供方） Adapter（AI 服务提供方适配器）的技术语义 |
| race（竞速）/fallback（降级）、key fingerprint（密钥指纹）去重、指数退避 | `app/service/llm_service.py:3231-3682` | `CONFIRMED`（已确认），不复制其医学输出和旧 task（任务）名称 |
| API（应用程序接口） routing（接口路由）、score（评分）、cold start（冷启动）、权重 | `app/service/api_pool_manager.py:55-90` | `CONFIRMED`（已确认），仅迁移可解释的连接选择字段 |
| Redis key cooldown（密钥冷却）/lease（租约）/失败标记 | `app/service/xray_v2/key_health.py:45-63,258-351` | `CONFIRMED`（已确认），Redis 只做短状态/锁，不做事实源 |
| DB model pool（数据库模型池）组合 | `app/helper/ai_helper.py:98-125`、`app/models/ai_api_connection.py:6-18` | `CONFIRMED`（已确认），参考旧链实际把明文 key（密钥）存在 `ai_api_connection.api_key` 并拼接连接字符串；这是安全差距，迁移时禁止复制 |
| HTTP（超文本传输协议）外部 RAGFlow/Grid | `app/service/ragflow/ragflow_client.py:23-100`、`app/service/xray_grid/grid_analyzer.py:541-580` | `CONFIRMED`（已确认），不属于 XRay Provider（X 光 AI 服务提供方）主链，单独隔离 |

参考项目真实链路可还原为（其中 Prompt Revision/Execution Plan 是治理代码路径；旧模板表本身没有完整 revision 字段，见 §4.3）：

```text
业务 Service / `LlmRequest.send_request` 或 `send_json_request`
  → Prompt 模板/治理 Revision（`AiPrompt`/`AiPromptRevision` 或 legacy `AiPromptTemplate`）
  → Execution Plan → Stage → Round（`AiGovernanceRuntimeService.resolve_plan_by_version`）
  → Model Pool / API Pool（`AiGovernanceModelPool`、`AiModelPoolLane`、`ApiPoolManager`）
  → Provider / API Key / Connection Family（旧链 `ai_api_connection` 明文连接串）
  → Redis key health、cooldown、lease（`XRayV2ConnectionHealthRegistry`）
  → AsyncOpenAI Provider Client（复用 registry client）
  → timeout / retry / Retry-After / rate-limit / fallback / race
  → JSON parse / response contract validation
  → `ai_request_log` / `api_request_stats` / trace
  → 业务 Service 结果
```

逐节点迁移核验：

| 节点 | 参考项目实际入口/事实源 | 数据流与失败处理 | ms-image 决策 |
|---|---|---|---|
| 业务请求 | `app/service/llm_service.py:1229,1417,2482`，`LlmRequest.send_request/send_json_request` | 接收业务参数和连接池，进入请求级 deadline；异常进入失败/超时日志 | 只迁移技术请求边界；医学输入另行门禁 |
| Prompt（提示词）/Revision（修订版本） | `app/models/ai_prompt_template.py:6-24`；治理 `app/models/ai_governance/prompt.py`、`app/service/ai/governance/runtime_service.py:33-120` | legacy（遗留）模板没有 checksum（校验摘要）/published（已发布）；治理路径按版本/状态解析，缺失时不能安全运行 | 保留文件 Prompt Registry（提示词注册表）+ checksum（校验摘要）；后续再接治理 DAL（数据访问层），不复制明文日志 |
| Plan（计划）/Stage（阶段）/Round（轮次） | `app/models/ai_governance/stage.py:8-68`、`AiGovernanceRuntimeService.resolve_plan_by_version` | plan（计划）缺失、round（轮次）参数非法或 fallback（降级）不允许时拒绝执行 | 先以 `stage_key/release_fingerprint` 白名单，后续映射公共 plan（计划） |
| Pool（连接池）/Connection（连接） | `app/service/api_pool_manager.py:55-225`、`app/models/model_connection.py:6-13` | pool（连接池）以连接顺序/权重/cold-start（冷启动）选择，旧 `model_pool` 是 `-` 分隔 ID（标识）；连接重复按 family（家族）去重 | 只迁移 connection metadata（连接元数据）、priority（优先级）、family（家族）；不引入第二 Repository（仓储层） |
| API（应用程序接口） Key（接口密钥）/Health（健康状态） | `app/models/ai_api_connection.py:13-18`、`app/service/xray_v2/key_health.py:43-65,258-351` | legacy key（遗留密钥）明文存库；Redis 记录 cooldown（冷却）/lease（租约），后端不可用时旧实现可能 fail-open（失败仍放行） | secret manager（密钥管理器）/env（环境变量）注入；只存 key fingerprint（密钥指纹）；readiness（就绪性）fail-closed（失败即关闭） |
| Provider Client（AI 服务提供方客户端） | `app/service/llm_service.py:50-84,2935-3154` | AsyncOpenAI client（异步 OpenAI 客户端）复用，timeout（超时）、lease（租约）、outer grace（外层宽限期）；429/5xx/网络错误按 key（密钥）/fallback（降级）策略处理 | `app/core/ai/openai_compatible.py` 公共 transport（传输层），真实 Provider qualification（AI 服务提供方资格验证）独立门禁 |
| Request Pool（请求池） | `app/service/llm_service.py:2670-2760`、`ApiPoolManager` | batch（批处理）/并发控制汇总请求结果，单个失败可触发 fallback（降级）；不应把结果 backend（后端）当事实源 | 使用 `AIRequestPolicy` + connection pool（连接池）；请求事实写 ModelCall（模型调用）/Trace（技术追踪） |
| Parse（解析）/ModelCall（模型调用） | `app/crud/ai_request_log_dal.py:22-165`、`ai_request_log` | 旧日志保存完整 prompt（提示词）/output（输出）；schema（结构合同）/timeout（超时）/失败更新状态与耗时 | 只存 hash（摘要）、receipt（回执）、usage（用量）、error_class（错误分类），禁止 raw prompt/output（原始提示词/输出） |
| Stats（统计）/Trace（技术追踪）/业务结果 | `app/models/api_request_stats.py:8-55`、`AiRequestLogger`、Redis stats（统计） | 按模型/日期聚合成功率/耗时；trace（追踪）与业务结果耦合程度高 | MySQL Run（运行）/Checkpoint（检查点）/ModelCall（模型调用）/Trace（技术追踪）为事实源，Redis 仅短状态 |

参考旧链的安全差距必须显式保留：`ai_api_connection.api_key` 为明文列，`ai_request_log` 可保存 `request_params`、原始/渲染 Prompt 和 `response_text`；这些字段只能作为“不得直接迁移”的证据，不能作为新链设计。

## 4. 参考项目数据库只读检查

### 4.1 配置来源

- `.env.example:19-23` 声明 `MYSQL_HOST`、`MYSQL_PORT`、`MYSQL_USER`、`MYSQL_PW`、`MYSQL_DB`。
- `core/async_db.py:9-26` 使用 `mysql+aiomysql` 构造连接。
- 实际 `.env` 的变量名存在，但 `MYSQL_PW` 为空（仅记录 presence/length，不输出值）。

### 4.2 连接结果与数据库事实

按参考 `.env` 直接使用 TCP + 空密码的第一次尝试为 `BLOCKED/incomplete_config`；随后发现
同一配置指向本机 `vet_platform`，使用本机 MySQL Unix socket 做了只读 fallback，连接成功。
完整脱敏结果见 [`docs/artifacts/reference-db-readonly-live.json`](../../../artifacts/reference-db-readonly-live.json)，
字段/索引/唯一约束摘要见 [`docs/artifacts/reference-db-schema-summary.md`](../../../artifacts/reference-db-schema-summary.md)；
初次失败记录见 [`docs/artifacts/reference-db-readonly-check.json`](../../../artifacts/reference-db-readonly-check.json)。

已确认的非敏感事实：

- `ai_api_connection` 96 行、`ai_connection_profile` 85 行、旧 `ai_model_pool` 19 行、治理模型池 20 行、lane 84 行；AI 表之间没有实际 Foreign Key 约束，但有唯一键和索引。
- `ai_prompt` 354 行、`ai_prompt_revision` 354 行且全部 `published`，其中 169 行有英文内容；旧 `ai_prompt_template` 375 行，`ai_output_schema` 当前为 0 行。
- `ai_stage` 338 行、`ai_stage_plan` 338 行且全部 `published`、`ai_stage_round` 340 行且全部为 active serial；`ai_execution_trace`/`ai_execution_attempt` 当前为 0 行。
- `ai_request_log` 167388 行：success 167145、failed 168、pending 75；存在 22 个模型、14 个 connection family、9 个 base URL；token 字段当前均无值，但 request 参数、原始/渲染 Prompt 和响应文本大量持久化。
- `api_request_stats` 当前为 0 行，不能把请求日志误认为聚合统计已形成。
- `ai_api_connection` 的 key 只做长度和 SHA256 fingerprint 数量核验（长度 20–73、30 个 fingerprint 前缀），没有输出原文；表中没有 expiry/health 字段。Redis db0 只观察到 17 个 key，其中 6 个 `round_robin` 持久 key，未发现可证明 key cooldown/lease 的当前值。

参考源码逻辑表已定位：

- `app/models/ai_api_connection.py`
- `app/models/model_connection.py`
- `app/models/ai_request_log.py`
- `app/models/api_request_stats.py`
- `app/models/ai_prompt_template.py`
- DAL：`app/crud/ai_api_connection_dal.py`、`model_connection_dal.py`、`ai_request_log_dal.py`、`ai_prompt_template_dal.py`

参考旧实现的两个安全/事实差距也已确认：

- `ai_api_connection.api_key` 是明文 `String(255)` 列（`app/models/ai_api_connection.py:6-18`），`app/helper/ai_helper.py:97-123` 会把 `base_url|api_key|model_name` 拼成运行时连接字符串；这不是新链可复制的安全做法。
- `app/service/xray_v2/key_health.py:294-316` 在 Redis 后端不可用时受 `XRAY_V2_KEY_LEASE_FAIL_OPEN` 控制，默认可能 fail-open；`:322-351` 的失败标记在后端不可用时直接跳过。新链必须将 Provider readiness 和关键租约按 fail-closed 处理，并把这项作为迁移风险。

参考工作树的实际 `.env` 中还存在非空 Gemini key material，但本报告不读取、不复制其值；数据库密码和 Redis 密码为空，TCP 连接配置不完整，但本机 Unix socket 只读 fallback 已成功。

## 5. 采集时 ms-image（影像服务）链路与差距

| 能力 | 当前证据 | 状态 | 差距 |
|---|---|---|---|
| Prompt Registry（提示词注册表） | `app/service/xray_accuracy/prompt_service.py:92-174` | `PARTIAL`（部分完成） | 只有 XRay（X 光）`request_gate.v1`，无 DB governance（数据库治理）、plan（计划）、revision（修订版本）表 |
| Provider（AI 服务提供方） Client（AI 服务提供方客户端） | `app/core/ai/openai_compatible.py:25-94` | `PARTIAL`（部分完成） | 支持 OpenAI-compatible（OpenAI 兼容协议）；无真实 qualification（资格验证）结果，当前文本请求不携带图像 |
| Provider（AI 服务提供方）/Pool（连接池） | `app/service/xray_accuracy/ai_request_service.py:27-350` | `PARTIAL`（部分完成） | Pool（连接池）可复用，但仍被 XRay Service（X 光服务）命名和设置绑定，进程内存态 |
| Key Health（密钥健康状态） | `ai_request_service.py:207-350` | `PARTIAL`（部分完成） | 有 cooldown（冷却）/stats（统计），无 durable key rotation（持久密钥轮换）/secret manager（密钥管理器） |
| ModelCall（模型调用） | `app/models/xray_accuracy/model_call.py:9-132` | `PARTIAL`（部分完成） | 哈希/receipt（回执）/latency（延迟）/error（错误）字段存在；真实 qualification（资格验证）不落库，token（令牌计数）字段当前未写入 |
| Outbox（事务发件箱）/Worker（异步工作进程） | `app/core/messaging/outbox_relay.py`、`workers/xray_accuracy_worker/` | `PARTIAL`（部分完成） | 本地代码存在；Docker daemon（Docker 守护进程）/生产 Broker（消息代理）/恢复演练无证据；admin（管理端）手动入口仍在 |
| Readiness（就绪性） | `app/core/readiness.py:16-137` | `PARTIAL`（部分完成） | DB（数据库）/Redis/Broker（消息代理）fail-closed（失败即关闭）；Provider（AI 服务提供方）仍主要信任配置布尔值 |
| DAL（数据访问层）边界 | `app/crud/xray_accuracy/` | `CONFIRMED_BASELINE`（已确认基线） | XRay DAL（X 光数据访问层）继承 `DalBase`；无 migration（迁移）/live schema（在线数据库结构）证据 |
| 多影像封装 | `app/core/messaging/config.py:67-95` | `PARTIAL`（部分完成） | 拓扑可命名空间隔离；通用 modality（模态）/pipeline（流水线）/stage registry（阶段注册表）尚未完成 |

当前可执行链路不是“文件存在”推断，已在独立 MySQL 测试库重新执行：

```text
POST /api/v1/xray/runs
→ XRayRunService（XRay 运行服务）.create_run
→ XRayRunDal（XRay 运行数据访问层）/RequestSnapshotDal（请求快照数据访问层）/StageCheckpointDal（阶段检查点数据访问层）/TraceEventDal（追踪事件数据访问层）/OutboxDal（事务发件箱数据访问层）
→ 同一 AsyncSession 事务提交 Run + Snapshot + Checkpoint + Trace + Outbox
→ XRayTechnicalWorker（XRay 技术执行工作进程）.execute_outbox_event（当前本机为直接 DB-backed qualification）
→ TechnicalExecutor（技术执行器）.execute
→ XRayPromptRegistry（XRay 提示词注册表）.render
→ AIConnectionPool（AI 连接池）.request
→ StubAIProvider（桩 AI 提供方）.request（真实 Provider 默认关闭）
→ XRayModelCallDal（XRay 模型调用数据访问层）.create_call
→ Checkpoint complete + Run CAS complete + Trace append + Outbox published
```

关键入口和失败边界：

- HTTP/tenant：`app/api/api_v1/endpoints/xray_runs.py:74-90`，缺 scope/tenant 在依赖层拒绝；异常先 rollback，避免提交半个聚合（`:46-71`）。
- 原子创建：`app/service/xray_accuracy/application_service.py:177-296`，幂等 hash 冲突拒绝；Run/Snapshot/Checkpoint/Trace/Outbox 使用同一 session。
- Relay：`app/core/messaging/outbox_relay.py:21-120`，claim/lease 后发布，失败转 retry/dead_letter；当前 Docker daemon 不可用，live RabbitMQ/Celery 未证明。
- Worker/状态机：`workers/xray_accuracy_worker/technical_worker.py:XRayTechnicalWorker` 与 `app/service/xray_accuracy/technical_executor.py:32-235`，校验 message/release/CAS/lease，取消或终态只写 late trace。
- Prompt/Pool/Provider：`app/service/xray_accuracy/prompt_service.py:XRayPromptRegistry`、`ai_request_service.py:230-470`；默认 `StubAIProvider` 不联网、不产医学结论，真实 adapter 仅在 qualification 后可启用。
- 事实源：6 张 `xray_accuracy_*` MySQL 表；Redis 只用于 readiness/短状态，Celery result backend 不是事实源。

重执行 artifact：[`p0-imaging-test-db-qualification-rerun.json`](../../../artifacts/p0-imaging-test-db-qualification-rerun.json)。它证明本地 socket Stub/Replay 状态闭环，不证明 HTTP edge、Broker live 或真实 Provider。

## 6. 归档时推荐架构：公共内核 + 影像适配器

### 公共内核

放在 `app/core/ai/`、`app/core/messaging/`、计划新增的 `app/core/imaging/`：

- Provider Client、Connection、Pool、retry/backoff、receipt；
- Broker topology、Celery app factory、Outbox relay、DLQ、reconcile；
- Run/Checkpoint/ModelCall/Trace 的通用 CAS、lease、幂等合同；
- tenant/scope、secret redaction、readiness；
- Prompt 版本选择、checksum、变量白名单和泄漏扫描引擎。

### 影像适配器

每种影像只实现：

- `modality_key`、`pipeline_key`、stage 白名单；
- 图像/Study manifest 编排；
- Prompt manifest/template；
- 输入/输出 JSON Schema；
- Provider 请求 payload 映射和技术回执能力；
- modality-specific Worker handler。

公共层禁止导入 `xray_accuracy` Model、Prompt 或医学规则。增加 CT/MRI 时不能复制 Pool、Relay、Readiness 或 Repository。

## 7. 配置迁移映射

| 参考项目 | ms-image 目标 |
|---|---|
| `GEMINI_API_KEYS` / key health | 旧链 `ai_api_connection.api_key` 明文 + Redis health/fingerprint（旧风险） → Secret manager 仅内存 `api_key_ref`；ModelCall 只存 fingerprint |
| `ai_api_connection` | Provider（AI 服务提供方） connection metadata；不存明文 key |
| `model_connection` / model pool | `connection_id`、`family`、`model`、priority、cooldown policy |
| `LLM_RACE_MODE_ENABLED` | `AIRequestPolicy.max_attempts` 和 fallback policy；必须受 deadline 约束 |
| `CELERY_*`、RabbitMQ | `app/core/messaging/config.py` + domain topology；result backend 保持 `None` |
| Prompt（提示词） template/revision | 文件/DB manifest + checksum；published+active 才可运行 |
| request log/stats | `xray_accuracy_model_call`、Trace（技术追踪）、连接统计；只迁移非敏感计数/耗时，不写原始 prompt/output |

环境差异：本地默认 Stub/Replay；集成环境仅在 Provider qualification artifact 存在时开启真实 Provider；生产必须由 secret manager、部署 schema、Broker readiness 和审批共同放行。

## 8. 数据库适配原则

当前阶段不创建 migration。未来 schema 需先提交映射 artifact：

- 公共表增加 `modality_key`、`pipeline_key`，并建立 tenant+modality+created_at 查询索引；
- 状态/类型使用 `String`，可变扩展使用 `JSON`，时间使用 `TIMESTAMP`；
- 不声明 ForeignKey，不使用数据库 enum；
- 每个字段 comment 写候选 SQL 类型和中文含义；
- 所有 DAL 继承 `app.core.crud.DalBase`；
- 不创建第二套 Repository/CRUDBase/DatabaseService；
- 资源 ID 只放 query/body，不设计 `/{id}`。

## 9. 已实施的最小改动

本轮只实施工程基础设施修正：

- `app/core/ai/config.py` 支持注入配置源和前缀，XRay 适配器显式传入 `XRAY_PROVIDER`；
- `app/core/messaging/config.py` 支持注入 broker/runtime 配置和显式拓扑覆盖；
- Provider HTTP 错误统一细分为 `endpoint_timeout`、`network_unreachable`、`tls_failure`、`provider_auth`、`model_invalid`、`schema_invalid`、`rate_limited`、`provider_unavailable`；
- qualification 配置错误和响应 Schema 错误返回稳定 blocked reason，不回显敏感异常；
- OpenAI-compatible 文本适配器不再伪造 `image_count_received=0`，改为 `unknown`；
- ModelCall 允许记录脱敏 Provider adapter 标识，不再把真实 Provider 永久拒绝为“未 qualification”；
- 输入 `safe_metadata` 增加递归值扫描、大小/深度限制；`source_image_ref` 使用 opaque allowlist。

未实施：真实 Provider 调用、Provider/Key/Connection/Pool 持久化表、数据库 migration、医学节点、Prompt 医学调优、测试脚本、原始影像写入。

## 10. Provider（AI 服务提供方）qualification（资格验证）门禁

执行顺序：

```text
配置读取 → endpoint/TLS → API key 认证 → model 可用性
→ 最小技术请求 → strict JSON/schema → timeout/retry/429 receipt
→ ModelCall/Trace 证据 → qualified 或 blocked
```

门禁规则：

- 未启用、配置缺失、kind/base_url 非法：`blocked`；
- Provider 真实调用失败：按稳定错误类返回 `blocked`；
- 无实际 model/request id/Schema 证据：不得 `qualified`；
- Stub/Replay 只能证明工程生命周期，不能证明真实 Provider qualification；
- `XRAY_PROVIDER_QUALIFIED=true` 不得由本地 mock 或手工输出替代真实证据。

当前执行结果：

```json
{"status":"blocked","reason":"provider_disabled","retryable":false}
```

此前真实 endpoint 曾返回 `provider_auth`；因此当前最终状态仍为 `BLOCKED`，不能进入医学链。

## 11. 运行与恢复证据

- `import main`：当前通过，用户端 root path `/ms-image`，管理端 `/ms-image/admin`。
- `docker compose config --quiet`：通过；但 Docker daemon 不可用，不能证明容器启动或 Worker 消费。
- Stub/Replay：已有 `docs/artifacts/p1-zero-model-replay.json`、`p1-prompt-ai-request-replay.json`，状态为本地技术验证而非生产验收。
- 临时 MySQL：`docs/artifacts/p1-mysql-qualification.json` 标明临时 schema、无 migration、无真实 Provider。
- G0：`docs/artifacts/p0-g0-approval.md` 仍为 `PENDING`，签名为 TBD。

## 12. 阻断项与解阻动作

| 阻断项 | 状态 | 解阻动作 |
|---|---|---|
| 真实 Provider（AI 服务提供方）凭证/认证 | `BLOCKED`（受阻） | 注入合规 secret（密钥），重新执行 qualification（资格验证）；失败只记录稳定 reason（原因码） |
| 参考数据库生产/TCP（传输控制协议）凭证为空 | `PARTIAL`（部分完成） | 本机 socket（套接字）只读事实已完成；如需远程/部署环境复核，提供批准的只读账号或脱敏 dump（转储） |
| Docker/RabbitMQ/生产 readiness（就绪性） | `BLOCKED`（受阻） | 启动受控部署环境，执行 edge（边缘入口）、DB（数据库）、Redis、Broker（消息代理）、Worker（异步工作进程）smoke（冒烟验证） |
| Alembic migration（数据库迁移）/deployment schema（部署结构） | `BLOCKED_BY_SCOPE`（受范围限制） | DBA（数据库管理员）/负责人批准后先提交 schema artifact（数据库结构证据产物），再生成 revision（迁移版本） |
| G0 审批 | `NOT_STARTED`（未开始） | 平台、安全、QA（质量保障）/SRE（站点可靠性工程）共同签署 G0 artifact（G0 证据产物） |
| 多影像 registry（注册表）/handler（处理器） | `NOT_STARTED`（未开始） | 先完成公共合同和 XRay（X 光）兼容适配器，再加入第二种影像 replay（回放） |

## 13. GitHub（代码托管平台）成熟方案比较

公开仓库核验、观测提交、许可证、关键路径和采用结论见
[`docs/artifacts/github-reference-verification.md`](../../../artifacts/github-reference-verification.md)。本次不复制代码或引入新网关，结论如下：

| 方案 | 解决问题 | 引入成本/新增依赖 | 与当前 FastAPI + Service（业务服务层） + DalBase 适配性 | 结论 |
|---|---|---|---|---|
| LiteLLM | 多 Provider（AI 服务提供方）路由、重试、fallback（降级）、预算 | 可能引入 Proxy（代理）/大型运行时；许可证需法务确认 | SDK（软件开发工具包）可适配，Proxy（代理）会新增服务边界 | 只作后续 SDK 评估，不引入 Proxy |
| Portkey Gateway（Portkey 网关） | 网关级路由、观测、策略 | Node Gateway（Node.js 网关）、独立部署和网络边界 | 不符合当前 Python 单服务最小改动 | 不引入 |
| Langfuse | Prompt（提示词）/Trace（技术追踪）/评估观测 | Web（网页服务）/worker（工作进程）/数据库栈，ee（企业版）路径需确认 | 可借鉴字段语义，不能替代 MySQL（关系型数据库）事实源 | 不引入运行时 |
| OpenLLMetry | OpenTelemetry LLM instrumentation（大模型可观测性埋点） | OTEL collector（OpenTelemetry 收集器）/导出链路 | 后续可作为 Trace（技术追踪）增强，不改变 DAL（数据访问层） | 后置评估 |
| Celery + RabbitMQ 官方模式 | durable queue（持久队列）、ack（确认）、retry（重试）、DLQ（死信队列）/publisher confirm（发布确认） | 当前已有依赖和代码；仍需 live（在线）部署演练 | 与现有 Outbox（事务发件箱）/Worker（异步工作进程）直接兼容 | 采用现有实现，补 live qualification（在线资格验证） |
| OpenAI Python | Async client（异步客户端）复用、timeout（超时）、连接池 | 仅 SDK（软件开发工具包）依赖 | 与 `app/core/ai` adapter（适配器）兼容 | 借鉴 client（客户端）生命周期，不替换当前边界 |

最终最小方案仍是：现有 FastAPI + Service + DalBase + MySQL 状态事实源 + RabbitMQ/Celery Outbox + 公共 Provider adapter；不引入 LiteLLM Proxy、Portkey Gateway、Langfuse 或新的数据库服务。

## 14. 迁移实施文件清单与数据转换

### 已修改或已具备的文件

| 能力 | 文件/符号 | 当前动作 |
|---|---|---|
| Provider（AI 服务提供方）配置 | `app/core/ai/config.py:ProviderRuntimeConfig/provider_config`、`app/core/config.py:XRAY_PROVIDER_*` | 已支持 source（来源）/prefix（前缀）注入；默认 disabled（禁用） |
| Provider（AI 服务提供方） transport（AI 服务提供方传输层） | `app/core/ai/openai_compatible.py:OpenAICompatibleClient` | 已统一 timeout（超时）/TLS（传输层安全协议）/HTTP（超文本传输协议）错误分类；不记录 key（密钥） |
| XRay（X 光） adapter（X 光适配器） | `app/service/xray_accuracy/providers.py:OpenAICompatibleProvider` | 只负责 payload（载荷）/receipt（回执）适配；当前 text-only（仅文本），图像 receipt（回执）为 unknown（未知） |
| Pool（连接池）/retry（重试） | `app/service/xray_accuracy/ai_request_service.py:AIConnectionPool/XRayAIRequestService` | 已有 cooldown（冷却）、retry（重试）、fallback（降级）、ModelCall（模型调用）；后续抽 modality-neutral（模态无关）公共层 |
| Prompt（提示词） | `app/service/xray_accuracy/prompt_service.py:XRayPromptRegistry`、`prompts/xray_accuracy/` | 已有 checksum（校验摘要）/变量扫描；治理 DB（数据库）迁移后置 |
| DB（数据库）事实源 | `app/models/xray_accuracy/`、`app/crud/xray_accuracy/`、`app/service/xray_accuracy/` | 6 表、`DalBase`（数据访问基类）、`AsyncSession`（异步数据库会话）；无 migration（迁移） |
| 异步 | `app/core/messaging/`、`workers/xray_accuracy_worker/` | relay（中继）/consumer（消费者）/reconcile（对账）代码已存在；live Broker（在线消息代理）未验收 |
| qualification（资格验证） | `workers/xray_accuracy_worker/provider_qualification.py:qualify` | fail-closed（失败即关闭）；当前 `provider_disabled`（Provider（AI 服务提供方） 已禁用） |

### 迁移时允许的数据转换

| 来源 | 目标 | 转换规则 | 风险/门禁 |
|---|---|---|---|
| `ai_api_connection` 的 provider/base_url/model（服务提供方/基础地址/模型） | Provider（AI 服务提供方） connection metadata（AI 服务提供方连接元数据） | 只复制 provider、base_url、model、连接标识和脱敏 fingerprint（指纹） | 明文 `api_key` 禁止迁移；需 secret ref（密钥引用）对账 |
| 旧 pool（连接池）字符串 `ai_model_pool.model_pool` | `connection_id`/priority/family（连接标识/优先级/家族） | 按 `-` 分隔解析，保留顺序为 priority（优先级）；解析失败进入人工复核 | 不直接写生产，先 schema artifact（数据库结构证据产物） |
| legacy prompt template（遗留提示词模板） | Prompt（提示词） manifest/revision（提示词清单/修订版本） | 以内容 SHA256（摘要）生成 revision checksum（修订校验摘要），状态默认 `draft`（草稿），人工发布后才 active（激活） | 旧表无 published（已发布）/checksum（校验摘要），不能自动放行 |
| `api_request_stats` | ModelCall（模型调用）/连接统计 | 仅迁移按日期/模型的 count（数量）、latency（延迟）、failure class（失败分类） | 不迁移原始 prompt（提示词）/output（输出）/token secret（令牌密钥） |
| `ai_request_log` | Trace（技术追踪）/ModelCall（模型调用）审计摘要 | 只取 request id（请求标识）、状态、耗时、错误类、hash（摘要） | `request_params`、Prompt（提示词）、response_text（响应文本）全部排除 |

### 下一轮需要修改的文件（未授权前不执行）

1. `app/core/ai/`：抽出 modality-neutral `ConnectionRegistry`、`ProviderPool` 和 secret-ref resolver。
2. `app/core/imaging/`：新增 modality/pipeline/stage registry 和 manifest contract。
3. `app/service/xray_accuracy/ai_request_service.py`、`providers.py`：改为公共内核兼容适配器。
4. `app/models/`、`app/crud/`、`app/service/`：只有产品确认需要持久化治理配置时，才按 `DalBase` 增加实体；先提交字段/索引/comment artifact。
5. `alembic_migrations/versions/`：仅在 DBA 授权后生成 revision；当前为空是刻意门禁。
6. `docs/artifacts/`：每次 qualification、schema、部署 smoke 都必须生成脱敏 artifact。

## 15. Qualification（资格验证）证据边界

当前命令 `python -m workers.xray_accuracy_worker.provider_qualification` 返回：

```json
{"status":"blocked","reason":"provider_disabled"}
```

这证明 fail-closed 分支可执行，但没有完成真实 Provider 的 ModelCall/Trace 持久化 qualification；当前真实 adapter 只发送 text prompt，`image_count_received` 与 `full_sent` 为 `unknown`。因此：

- `qualified` 只能由真实 endpoint、TLS、认证、model、strict schema、request id、usage/latency、逐图 receipt 和 ModelCall/Trace artifact 共同产生；
- 不得设置 `XRAY_PROVIDER_QUALIFIED=true`；
- Stub/Replay 的 timeout/retry/429/CAS/DLQ 结果不能替代真实 Provider；
- 参考数据库已通过本机 socket 完成只读数量/状态查询；远程/TCP凭证仍未配置，但不再把本机参考数据事实标为 UNKNOWN。

## 16. 归档时判定

`PARTIAL / NO-GO`。

允许继续：公共封装、零模型 Run/Trace、Stub/Replay、配置和审计修正。

禁止继续：真实医学 Provider、医学 Prompt、truth/scorer、准确率声明、Shadow/Gray/Active、生产报告替换、迁移和 Holdout。

只有当真实 Provider qualification、部署 readiness、Broker 恢复演练和 G0 审批全部有当前 artifact 后，才能把工程阶段标记为 `DONE`；参考 DB 本机只读证据已经完成，但不能替代生产 Provider/部署门禁。
