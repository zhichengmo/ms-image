# ms-image XRay（X 光）独立诊断服务详细开发计划

> 中文阅读说明：`ARCHIVED` 是“已归档”，`development plan` 是“开发计划”；其余英文术语请参阅[英文术语中英对照](../../../术语中英对照.md)。

> `ARCHIVED / 历史资料`：本文是旧计划，不再代表当前开发顺序、完成状态或发布授权。

状态：`ARCHIVED`（已归档）

当前依据：[MS-Image 最终架构、数据库与完整链路设计](../../../ms-image-final-architecture-and-database-design.md)

历史语境：本文后文的“当前”“必须”“执行计划”和完成定义均限定于 2026-08-08 计划时点，不构成当前任务安排。

> 字段审计说明（2026-08-17）：已删除没有独立用途的 `case_request_id`（病例请求标识）、Run（运行）级 `engineering_eligibility`（工程资格）和 `validation_only`（仅验证布尔值）。本计划的 9 张 XRay（X 光）候选表已被当前通用 10 表方案取代。

版本：v1.0（计划稿）
日期：2026-08-08
目标项目：`/Users/mozhicheng/workspace/code/cy-code/ms-image`
逻辑领域名称：`vet-xray-accuracy-service`
历史计划时点状态：工程骨架可继续收口；XRay 业务链、Provider、Worker、Trace 和医学验证尚未实现。

## 1. 结论与开发边界

本计划基于参考仓库 `vet-platform` 的实际 XRay V2/V3 代码，以及专题文档 07（准确率原则、医学分母、paired A/B、Holdout、No-Go）和 08（独立服务架构、接口、状态机、迁移）整理。

核心决策是：在 `ms-image` 内先建立独立的 XRay 领域模块和 Worker，以 `validation-only / shadow` 运行；在 trusted gold、逐例 paired A/B、重复性和隔离 Holdout 全部通过前，不替换 `vet-platform` 的生产 V2，也不宣称准确率提升。

必须保持的边界：

- 医学准确率状态为 `UNKNOWN`，正式盲测为 `PAUSED`，发布状态为 `NO-GO`。
- 原图 Study 是最小医学上下文；完整 Study 联合主读是默认主链。
- 只有 `FinalMedicalReader` 能产生 `ai_final_decision`；Python、Renderer、fallback 和 Human Review 不得改写医学结论。
- 技术失败、图像不完整、Provider 未确认消费、超预算和解析失败必须 fail-closed，不能伪装成 normal/abnormal。
- 新模块只采用 `API → Service → CRUD → Model/DB`，SQLAlchemy 2.x + `AsyncSession`；不混用 MongoEngine，不使用数据库 foreign key，不使用 `/{id}` 路由。
- 数据库访问只使用现有 `app.core.crud.DalBase`。实体 DAL（如 `XxxDal`）在 `app/crud/` 中继承它并调用基类异步方法；Service 通过导入实体 DAL 编排业务，不能重新写 SQL、创建第二套 CRUD/Repository 或新增平行数据库服务。
- 本计划中的“独立服务”是 XRay 领域和部署边界的称呼，不表示在本仓库外再创建一个通用 service 包；实现应复用现有 `app/service/`、`app/crud/` 和 `DalBase`。
- 本文档是开发计划，不创建迁移文件、测试脚本或真实 Provider 代码；实现须在新会话按 Prompt 分阶段完成。

## 2. 证据表与权威顺序

### 2.1 权威顺序

```text
原始验证 JSON / manifest / image hash / model trace / truth audit
> 当前实际代码
> Git commit 与 Prompt 资产
> 专题 07：分母、trusted gold、paired A/B、Holdout、No-Go
> 专题 08：独立服务设计与 ms-image 映射
> 02/04/05/06 历史 V2/V3 方案和日志
```

专题根 README 明确：07 是准确率上游基线，08 是 `ms-image` 独立服务设计；两者与当前代码冲突时必须记录为差异，而不是把方案写成已实现。

### 2.2 计划时点仓库事实（复核后）

| 领域 | 当前事实 | 状态 | 证据 |
|---|---|---|---|
| FastAPI 用户端/管理端 | `main.py` 创建两个 app，用户端注册 `/api/v1`，管理端注册 `/api/v1` | CONFIRMED | `main.py:33-48,108-109` |
| 路由 | 用户端仅 health/version；管理端仅 status/info | CONFIRMED | `app/api/api_v1/api.py:1-7`、`app/api/admin_v1/api.py` |
| 启动兼容层 | `app/lib/__init__.py`、`app/lib/oid.py` 已存在，为脚手架兼容，不含 XRay（X 光） 逻辑 | CONFIRMED | `app/lib/*` |
| 数据库 | 主 MySQL、可选 MS_HD MySQL，异步 SQLAlchemy session | CONFIRMED | `app/core/async_db.py:7-53,97-146` |
| DAL（数据访问层） | `app/core/crud.py` 提供异步 `DalBase`；另有 MongoEngine legacy CRUD | CONFIRMED divergence | `app/core/crud.py:24-36`、`app/crud/base.py` |
| Schema/响应 | `GenericResponse`、`PagedResponse` 已有；业务 XRay（X 光） schema 不存在 | CONFIRMED | `app/schemas/base.py:8-40` |
| Redis | `RedisManager` 已有；用户 app lifespan 初始化，管理 app 的资源边界需再确认 | CONFIRMED divergence | `main.py:20-30,41-48`、`app/core/redis_manager.py` |
| 队列 | requirements 有 Celery/Pika，但 compose 无 RabbitMQ，代码无可用 XRay（X 光） consumer | CONFIRMED missing | `requirements.txt:29-33`、`docker-compose.yml:3-34` |
| 图像/Provider（AI 服务提供方） | 没有 XRay（X 光） 图像接收、签名 URL、hash receipt 或模型 Provider（AI 服务提供方） 适配 | CONFIRMED missing | 全仓检索结果 |
| Run/Trace（技术追踪）/验证 | 没有 XRay（X 光） Run、ModelCall、Outbox（事务发件箱）、Scorer、Holdout runner | CONFIRMED missing | 全仓检索结果 |
| Git | 当前目标目录已有 `.git`，但工作树有用户未提交修改 | CONFIRMED | `git status --short` |

工作树已有修改（`.env.example`、`.gitignore`、认证/config/requirements 及 `app/lib`），实施时必须保留并先做基线快照，不得 reset、checkout 或覆盖。

### 2.3 参考仓库可复用线索

- `vet-platform/app/service/xray_v2/pipeline.py:22-172` 已证明旧链的责任过宽；新服务只复制最小数据合同，不复制旧编排。
- `vet-platform/app/api/api_v1/endpoints/x_ray_v2.py:33-130`、`app/service/xray_v2/report_service.py:23-143`、`tasks/xray_report_task.py:384-468` 提供历史接口/任务行为，仅作迁移对照；其 `/{session_id}` 路径不符合本项目规范。
- `vet-platform/app/service/xray_v2/llm_client.py`、`app/constants/x_ray_constants.py:553-675` 提供 Prompt/LLM trace 线索，但新服务必须拥有自己的版本化 manifest 和 Provider boundary。
- `vet-platform/app/service/oss_service.py`、`app/helper/oss_helper.py` 提供 OSS/MD5 去重参考；不能假设这些能力已存在于 `ms-image`。
- `vet-platform/tasks/celery.py:28-85`、`:117-227` 提供队列分片、ack、重试和 worker 生命周期参考；新服务需要独立 task type/queue namespace。

## 3. 目标架构

```text
vet-platform（鉴权、病例/Study 业务、生产 V2、灰度回切）
        │ 版本化安全 Study 请求（不含 truth/标签/历史结论）
        ▼
ms-image API（受理、校验、幂等、查询、取消）
        │ MySQL Run + RequestSnapshot + Outbox 同事务
        ▼
独立 XRay Worker（状态机事实源为 MySQL，Broker 只传 opaque ID）
        │
        ├─ StudyAssembler（检查组装） → EngineeringGate（工程门禁）
        ├─ JointPrimaryReader（联合主读，B0）
        ├─ SparseTargetedReview（稀疏定向复核，A2，可选且每例最多一次）
        ├─ FinalMedicalReader（最终医学判读，A1/A2，唯一最终医学 owner）
        ├─ DecisionPolicy（决策策略，只校验状态，不增加医学判断）
        └─ TraceWriter（追踪写入） / ReportRenderer（报告渲染） / Human Review Gateway（人工复核网关）
        │
        ├─ 原图存储/短期 signed URL/bytes（只读、hash 审计）
        ├─ Model Provider（实际模型、Prompt、schema、receipt）
        └─ MySQL Run/Stage/ModelCall/Finding/Review/Outbox/Release
```

第一阶段不决定是否拆成独立容器。先在同一仓库内使用独立模块、独立进程和独立队列命名空间；完成 ADR 后再决定部署隔离。

## 4. 目录与分层设计

```text
app/
├── api/api_v1/endpoints/xray_accuracy.py       # 路由、鉴权、响应包装
├── schemas/xray_accuracy/
│   ├── requests.py                             # extra=forbid 的外部请求
│   ├── responses.py                            # 三正交状态、coverage、trace ref
│   ├── internal.py                             # Worker/Provider 合同
│   └── validation.py                           # schema/leakage 合同
├── service/xray_accuracy/
│   ├── application_service.py                  # 用例编排
│   ├── state_machine.py                        # 状态转移/CAS/失败语义
│   ├── study_assembler.py                      # Study revision/ordered hash
│   ├── engineering_gate.py                     # full_sent/receipt/预算门禁
│   ├── decision_policy.py                      # 终态校验，不做医学改写
│   ├── report_renderer.py                      # 纯渲染
│   ├── trace_writer.py                         # append-only trace
│   └── providers/                              # image/model/review adapter
├── crud/xray_accuracy/                         # 每个实体一个 XxxDal
├── models/xray_accuracy/                       # SQLAlchemy 模型，无 FK
└── providers/                                  # 若需跨域复用，再抽受控 adapter
workers/xray_accuracy_worker.py                 # API 外的长任务执行
evaluation/                                     # 离线 manifest/scorer/Holdout
prompts/                                        # 版本化 Prompt manifest/template
alembic_migrations/versions/                    # 仅 schema review 后由用户授权创建
```

分层约束：endpoint 不直接查询数据库、不编排多个 DAL；Service 构造函数接收 `AsyncSession` 并初始化 DAL；DAL 只做数据访问；Schema 不访问数据库；健康/版本接口保留现有例外。

### 4.1 多影像模块化封装约定

本项目不按“每种影像复制一整套服务”的方式扩展，也不把所有影像逻辑堆在 `xray_accuracy` 目录中。采用“公共内核 + 影像适配器”两层边界：

```text
app/
├── core/
│   ├── ai/                    # Provider、Connection、Pool、超时/重试、熔断、凭证引用、qualification
│   ├── messaging/             # Broker topology、Celery factory、Outbox relay、lease、DLQ、reconcile
│   └── imaging/               # modality/pipeline/stage 合同、幂等/CAS、脱敏、Trace 上下文（待补齐）
├── service/
│   ├── imaging/               # 公共 Run/Stage 执行编排（复用现有 app/service，不创建平行 Service 体系）
│   └── xray_accuracy/         # XRay V2 适配器：Prompt、图像集合、Schema、阶段图、XRay 规则
├── crud/
│   ├── imaging/               # 公共实体 DAL（每个实体一个 XxxDal，统一继承 DalBase）
│   └── xray_accuracy/         # 兼容当前 XRay 表的实体 DAL；后续以 modality_key 统一查询
├── schemas/
│   ├── imaging/               # 跨影像请求/事件/回执合同
│   └── xray_accuracy/         # XRay 专用请求和 Provider 输出 Schema
└── workers/
    ├── imaging_worker/        # 公共消费、幂等、租约、重试和恢复
    └── xray_accuracy_worker/  # XRay stage handler 注册，不复制公共 Worker 语义
```

封装边界必须满足：

| 类型 | 放入公共内核 | 保留在影像适配器 |
|---|---|---|
| Provider（AI 服务提供方）/Connection/Model Pool | OpenAI-compatible client、API（应用程序接口） key 引用、健康/cooldown/lease、timeout/retry/fallback、receipt、token/latency 统计 | 仅声明允许的 provider family、模型能力和请求 payload 映射 |
| 异步执行 | RabbitMQ/Celery 拓扑生成、Transactional Outbox（事务发件箱）、publisher/consumer lease、CAS、DLQ、orphan reconcile | modality/pipeline/stage 的白名单和 handler 注册 |
| 数据与审计 | Run/Checkpoint/ModelCall/Trace（技术追踪）/Outbox（事务发件箱） 的通用状态和脱敏字段 | XRay（X 光） 的阶段键、Study（影像检查）/Image（影像） manifest、XRay（X 光） 专用输出 Schema |
| Prompt（提示词） | checksum、published/active、版本选择、变量白名单、泄漏扫描 | `prompts/xray_accuracy/` 下的模板、变量和响应 Schema |
| API（应用程序接口） | tenant、scope、幂等、统一错误/分页/健康语义 | 当前 XRay（X 光） 路由兼容层；新影像通过 `modality`/`pipeline_key` 参数选择，不使用 `/{id}` |

所有可跨影像复用的状态记录都必须带 `modality_key` 和 `pipeline_key`（当前 `xray_accuracy_*` 表在未获迁移授权前保持不变）。Broker 名称由 `topology_for(modality_key)` 生成并保持命名空间隔离；不能为 CT/MRI 再复制一套 relay、Pool 或 readiness。未来确有影像专属大字段时，使用 JSON 或独立扩展表承载，仍不得使用 ForeignKey 或数据库 enum。

当前源码证据：`app/core/messaging/config.py:56-76` 已提供按 domain 生成隔离拓扑的公共函数；`app/core/messaging/outbox_relay.py` 已提供公共 relay；`app/core/ai/config.py` 和 `app/service/xray_accuracy/ai_request_service.py:27-88` 已有 Provider/Pool 合同但仍被 `XRAY_*` 配置和 XRay 命名绑定；`app/service/xray_accuracy/prompt_service.py:92-174` 仍是单一 XRay Prompt Registry；`workers/xray_accuracy_worker/` 仍只注册 XRay task。因此“公共内核 + 适配器”是目标边界，不能把当前文件存在误记为多影像封装已经完成。

实施顺序：先抽取 `modality/pipeline/stage` 及 Provider/Prompt/Worker 注册合同，给现有 XRay 适配器加兼容实现；再把查询、Trace、Outbox 和 readiness 改为按 modality 命名空间；最后才接入 CT/MRI/超声。每一步都必须保持 XRay stub/replay 可回放，真实 Provider qualification 仍独立受门禁控制。

## 5. API（应用程序接口）与数据合同

### 5.1 诊断平面

内部 route（由 `main.py` 的 `/api/v1` prefix 注册）：

```text
POST /api/v1/xray/runs
GET  /api/v1/xray/runs?run_id={run_id}
POST /api/v1/xray/run-cancellations
```

不使用 `/{id}`。外部 `/ms-image` 前缀必须以反向代理配置和受控请求确认，不能仅依据 `root_path`。

`POST /xray/runs` 只做鉴权、schema/leakage 校验、幂等受理和 Outbox 写入，返回 `202` 与 `run_id`；长任务由 Worker 执行。

### 5.2 请求字段

必需：`request_id`、`study_id`、`study_revision_id`、`expected_image_manifest`、`images`、`contract_version`。

允许的安全元数据：`species`、`body_part_hint`、`projection_hint`、`study_date`、图像序号和短期单用途 `image_url/internal_ref`。

拒绝：`ABN/NOR`、疾病码、文件名/目录标签、历史报告/模型输出、failure-bank 标签、truth、score eligibility、bbox/annotation、可推断标签的 EXIF/OCR。Pydantic schema 必须 `extra="forbid"`，递归扫描 key/value/URL/header/tool 参数。

### 5.3 返回字段

返回 `execution_status`、`ai_medical_status`、`delivery_status` 三个正交状态，以及 `coverage`、`findings`、`limitations`、`review`、`decision_owner`、`trace_ref`、受信控制面冻结的 `run_mode`（运行模式）和 `production_eligible`（生产资格）。

`image_count_sent` 仅表示客户端发送数量；Provider 无逐图 receipt 时必须为 `unknown`，不能写成 confirmed。`technical_failure` 不携带医学 verdict；Human Review 结果以新记录保存，不能覆盖 AI trace。

### 5.4 状态与转移

```text
execution_status: queued | dispatched | running | retry_wait | completed |
                  failed | cancelled | dead_letter
ai_medical_status: not_produced | normal | abnormal | review_required |
                   non_diagnostic
delivery_status: not_required | pending | persisted | review_queued |
                 review_queue_failed | published | suppressed
```

状态事实在 MySQL；Redis 只做锁、短状态和限流；Celery result backend 不作为事实源。任何状态变更使用 `expected_version`/CAS，重试使用新的 `attempt_id`，迟到结果只写 late trace。

## 6. 持久化设计（仅计划，不创建迁移）

以下是旧 9 表计划的当前归宿。完整候选字段已删除，不能据此创建 migration（迁移）：

| 历史候选表 | 当前归宿 | 结论 |
|---|---|---|
| `xray_accuracy_run`（X 光运行记录） | `task_record`（任务记录） | 通用化保留 |
| `xray_accuracy_request_snapshot`（X 光请求快照） | Task（任务）不可变快照 | 合并，不独立建表 |
| `xray_accuracy_image`（X 光影像记录） | `series_record`（影像序列记录）+ `image_record`（影像记录）+ Call manifest（调用清单） | 按事实 owner（所有者）拆分 |
| `xray_accuracy_stage_checkpoint`（X 光阶段检查点） | `stage_checkpoint_record`（阶段检查点记录） | 通用化保留 |
| `xray_accuracy_model_call`（X 光模型调用） | `ai_call_record`（AI 调用记录） | 通用化保留 |
| `xray_accuracy_finding`（X 光结构化发现） | Report content（报告内容）+ EvidenceGraph Artifact（证据图产物） | 首期不独立建表 |
| `xray_accuracy_review`（X 光人工复核） | 外部 Review（人工复核）系统 | 条件扩展 |
| `xray_accuracy_outbox`（X 光事务发件箱） | `outbox_record`（事务发件箱记录） | 通用化保留 |
| `xray_accuracy_release_event`（X 光发布事件） | AI Config（AI 配置）+ AuditSink（审计接收端）+ `ms_image_eval`（影像评测控制面） | 三类事实分开拥有 |

当前新表仍使用 String/JSON/Timestamp（字符串/结构化数据/时间）等可演进类型，不声明数据库 Foreign Key（外键）或 Enum（枚举）。

## 7. 状态机与最小医学链

```text
RequestGate（请求门禁） → StudyAssembler（检查组装） → EngineeringGate（工程门禁）
  ├─ INPUT_INVALID / PARTIAL_SENT / TECHNICAL_FAILURE → fail-closed
  ├─ OVER_BUDGET → ai_medical_status=not_produced，转人工或 non-diagnostic
  └─ READY_FULL_STUDY
       → JointPrimaryReader（联合主读）
       →（可选一次 SparseTargetedReview（稀疏定向复核））
       → FinalMedicalReader（最终医学判读）
       → DecisionPolicy（决策策略）
       → ReportRenderer（报告渲染） / TraceWriter（追踪写入）
```

Final 必须重新发送完整原图。`JointPrimaryReader` 只写候选证据，`FamilyRouter` 只做路由，`SparseTargetedReview` 只写 evidence delta；只有 Final 写最终医学状态。

## 8. Worker（异步工作进程）、Outbox（事务发件箱）与 Provider（AI 服务提供方）计划

1. API 事务内创建 Run、RequestSnapshot、首个 StageCheckpoint 和 Outbox。
2. Dispatcher 在 commit 后发布只含 `run_id/task_id/stage_key/release_fingerprint/expected_version` 的消息。
3. Worker claim 使用 lease、heartbeat、CAS；每阶段先写 checkpoint/ModelCall/Trace，再推进下一阶段。
4. Celery/RabbitMQ 仅在真实 Broker 通过 ADR 和部署回归后启用；在此之前只实现可替换 adapter/stub，不能把 Redis get/set 当队列。
5. Provider adapter 接受版本化 `ProviderRequest`，记录实际 model、image receipt 能力、raw/parsed hash、token、延迟、retry/fallback；secret 不落库。
6. 取消、超时、死信和孤儿 Run 都是可审计状态；取消后的 late provider 结果禁止发布。

## 9. Prompt-first（提示词优先）与安全门禁

Prompt manifest 至少固定：`prompt_key/node_key/species_scope/body_scope/language/version/template_path/schema_key/prompt_sha256/owner/active`。

调用前递归检查标签、truth、历史输出、文件名、疾病名、annotation、failure-bank 和 score eligibility。命中即 `leakage_invalid`、停止模型调用、保存 rule/path/value hash，并保留工程审计记录，但不进入医学分母。

JSON parse/schema retry 不回送 `previous_output`；transport retry 生成新的 `attempt_id`；医学结论不满意不能自动重试，必须走预注册复核节点。

## 10. 分阶段执行计划

### Phase 0（第 0 阶段）：P0 工程基线（阻断级）

交付：Git/运行时/依赖 manifest、`import main` artifact、认证与租户合同、DB/Redis/Alembic 语义、Broker ADR、readiness、工作树快照。

门禁：用户端/管理端可独立启动；无硬编码管理凭证；XRay 查询按租户隔离；Redis/DB 可用性可观测；现有未提交修改未被覆盖。

### Phase 1（第 1 阶段）：零模型 Run（运行）/Trace（追踪）骨架

交付：请求 schema、Run/RequestSnapshot/StageCheckpoint/ModelCall/Trace/Outbox 模型草案、API 受理/查询/取消、幂等/CAS、Worker stub/replay、leakage preflight、late result/DLQ/reconcile。

门禁：不调用真实 Provider；重复消息不产生第二个 final；technical failure 不带医学 verdict；trace 可按 fingerprint 重放。

### Phase 2（第 2 阶段）：图像与 EngineeringGate（工程门禁）

交付：短期签名 URL/内部引用适配、MIME/大小/像素/方向校验、原图下载和 SHA256、ordered manifest、provider receipt、full_sent/partial/over-budget 状态。

门禁：请求图像集合与发送集合可逐图对账；缺图、hash 不一致、过期凭证、超预算均 fail-closed；不接收 DICOM/转换能力前不得宣称支持。

### Phase 3（第 3 阶段）：B0/A1 最小医学链（validation-only：仅验证）

交付：JointPrimaryReader、FinalMedicalReader(independent_first)、结构化 finding/source anchor、DecisionPolicy、Renderer、完整 trace。

门禁：同一冻结 manifest、provider/model/prompt/schema/scorer；实际模型消费能力已 qualification；只进入离线 paired 实验，不写生产报告。

### Phase 4（第 4 阶段）：A3a/A2/A3b 实验节点

按顺序实现 Blind Sentinel 离线审计、Sparse Targeted Review、可选 Sentinel evidence；每个节点独立 flag、fingerprint、预算、指标和删除条件。未通过的节点不得进入默认链。

### Phase 5（第 5 阶段）：数据治理与 paired A/B（配对 A/B 对照实验）

建立 trusted gold、双专家盲读/仲裁、StudyEvent 去重、visibility、train/dev/Holdout 隔离和 scorer contract。报告 ABN→normal、NOR→abnormal、strict、safe capture、review、non-diagnostic、engineering/end-to-end、重复性和成本。

### Phase 6（第 6 阶段）：Shadow（影子运行）→ Gray（灰度发布）→ Active（正式激活）

Shadow 仅采样旁路、不影响 V2；Holdout 通过后才允许预注册 Gray。Gray 必须可回切、有人审队列和 SLA；Active 前只能有一个生产 final owner。任何 fallback 标记为 `v2_fallback`，不得计入新链医学正确。

## 11. 验收矩阵

| 层级 | 必须证明 | 失败动作 |
|---|---|---|
| L0 工程启动 | import、依赖、双端、readiness、配置安全 | 停止业务开发 |
| L1 数据/传输 | ordered hash、receipt、full_sent、凭证和媒体边界 | 运行标记不可评估 |
| L2 状态/审计 | 三正交状态、CAS、幂等、late trace、Outbox（事务发件箱） | 禁止真实 Provider（AI 服务提供方） |
| L3 资格实验 | engineering_clean=100%、actual provider、fingerprint 一致 | 退回工程阶段 |
| L4 医学 A/B | trusted gold、paired、分层指标、三次 fresh replicate | No-Go，删除未证实节点 |
| L5 Holdout | 独立冻结集、未调参、claim_allowed=true | 回开发集，重建 Holdout |
| L6 Gray | SLA、成本、回滚演练、监控和单一 owner | 回 Shadow/V2 active |

医学分母固定为：

```text
trusted_gold ∩ study_revision_complete ∩ full_sent
∩ engineering_clean ∩ actual_model_confirmed ∩ scorer_contract_confirmed
```

`TECHNICAL_FAILURE` 不进入模型医学分母，但必须进入工程和端到端总体分母；`REVIEW_REQUIRED`、`NON_DIAGNOSTIC` 进入医学分母并单独报告。

## 12. 风险与回滚

- 启动/依赖风险：先固定 runtime/lock，不能靠当前 shell 缺包结论。
- 认证越权：删除硬编码 Basic Auth，所有查询带 tenant scope。
- 图像泄漏/SSRF：短期单用途凭证、allowlist、重定向/MIME/像素限制、hash 复算。
- Provider 黑盒消费：receipt 不可观测则记 UNKNOWN，不进正式分母。
- 队列重复发布：MySQL CAS + outbox + late trace + final owner。
- 医学误报/漏诊：ABN/NOR 双守护，任何 unsafe flip 触发 No-Go。
- 分母污染：truth/标签/历史输出隔离，Holdout 一次性消费。
- 成本/Review 爆炸：每例调用和人工 SLA 预算；节点独立删除。

工程回滚：停止分流、release state 回 `shadow`、保留不可变 run/trace、V2 恢复唯一 active。医学回滚由新增 ABN→normal、NOR FP、review/non-diagnostic、完整原图审计失败、Provider 漂移或人审 SLA 超限触发。

## 13. 首轮开发完成定义

首轮只算工程完成，不算医学完成。必须能回答：

1. 一次请求如何在 MySQL 中形成不可变 Run、Snapshot、Checkpoint 和 Outbox？
2. 重复投递、取消、超时、死信和 Worker 重启如何避免第二个 final？
3. 每张图的 expected/resolved/requested/sent/receipt/hash 是否可追溯？
4. Prompt、schema、provider、model、retry、fallback 和输出是否可重放？
5. 技术失败是否永远不携带医学 verdict？
6. 普通诊断调用是否无法提交 truth、release、Holdout 或读取别人的 run？

在这些问题全部有代码和 artifact 证据前，不得进入真实医学 Provider、盲测、Shadow、Gray 或 Active。

## 14. 参考资料索引

- `vet-platform/documents/X光V2重构专题/README.md`
- `.../07-准确率优先全链路重构文档包/README.md`
- `.../07-准确率优先全链路重构文档包/02-准确率实验设计与验收门槛.md`
- `.../08-XRay独立诊断服务新项目设计文档包/00-项目总览与权威边界.md`
- `.../08-XRay独立诊断服务新项目设计文档包/01-独立服务架构决策与系统边界.md`
- `.../08-XRay独立诊断服务新项目设计文档包/02-准确率优先全链路与状态机.md`
- `.../08-XRay独立诊断服务新项目设计文档包/03-接口数据合同与持久化设计.md`
- `.../08-XRay独立诊断服务新项目设计文档包/05-验证实验门禁与医学分母.md`
- `.../08-XRay独立诊断服务新项目设计文档包/06-实施迁移灰度与回滚计划.md`
- `.../08-XRay独立诊断服务新项目设计文档包/09-ms-image落地基线与目录映射.md`
- `.../08-XRay独立诊断服务新项目设计文档包/10-ms-image-P0工程基线执行清单.md`

## 15. GitHub 外部参考与借鉴边界

以下项目已进行公开仓库只读检索。它们是工程模式参考，不是医学准确率证据，也不改变专题 07/08 的分母、trusted gold、paired A/B、Holdout 和 No-Go 合同。

| 项目 | 许可证 | 可借鉴内容 | 在 ms-image 中的使用边界 |
|---|---|---|---|
| [dcm4che/dcm4chee-arc-light](https://github.com/dcm4che/dcm4chee-arc-light) | 根 `pom.xml` 声明 MPL-1.1/GPL-2.0/LGPL-2.1 三选一；需法务确认 | `Study → Series → Instance` 层级、UID 查询、completeness/failed retrieve 状态和索引设计；参考 `dcm4chee-arc-entity/.../Study.java`、`Series.java`、`Instance.java` | 只借鉴 Study（影像检查） 完整性和图像身份模型；不引入 Java EE/WildFly/JPA 归档体系，不照搬 enum 和运维状态 |
| [Project-MONAI/MONAILabel](https://github.com/Project-MONAI/MONAILabel) | Apache-2.0 | DICOMWeb 数据接入、可复现缓存 hash、frame 获取和模型服务/标注插件边界；参考 `monailabel/datastore/dicom.py` | 仅在 Phase 2 媒体边界 ADR 允许 DICOM 时再评估；不能把研究标注服务器当作临床诊断链 |
| [OHIF/Viewers](https://github.com/OHIF/Viewers) | MIT | DisplaySet/Instance 组织、SOPInstanceUID 去重和查看器侧 Study（影像检查） 组合 | 只作前端显示与重复实例过滤参考，不承担后端医学状态或 scorer |
| [celery/celery](https://github.com/celery/celery) | BSD-3-Clause | 长任务、ack、retry/countdown、worker 生命周期和 RabbitMQ broker 适配 | 必须与 MySQL Run 状态、CAS、Outbox（事务发件箱）、消费者幂等结合；Celery result backend 不是事实源 |
| [tomorrow-one/transactional-outbox](https://github.com/tomorrow-one/transactional-outbox) | Apache-2.0 | 业务数据和 outbox 同事务、relay 发布后标记、至少一次投递和消费幂等 | 项目基于 Kafka/Java；ms-image 只移植 outbox/relay 思路，按实际 ADR 替换为 RabbitMQ/Celery 或其他 broker |
| [vllm-project/vllm](https://github.com/vllm-project/vllm) | Apache-2.0 | 独立推理 API（应用程序接口）、请求排队、并发与批处理边界 | 仅作为 Provider（AI 服务提供方） 资源调度参考；必须有每例 deadline、图像数、token 和成本预算，不能直接引入 GPU 运行时 |
| [bentoml/BentoML](https://github.com/bentoml/BentoML) | Apache-2.0 | Runner 抽象、模型版本和部署适配 | 可作为后续 Provider（AI 服务提供方） adapter 的候选，不作为首轮强依赖，避免运行时过重 |
| [ray-project/ray](https://github.com/ray-project/ray) | Apache-2.0 | Replica、异步 batching、扩缩容思路 | 只有高并发和资源隔离需求被 ADR 证明后评估；首轮 Worker（异步工作进程） 不引入 Ray 集群 |
| [langfuse/langfuse](https://github.com/langfuse/langfuse) | MIT | trace/span/generation、Prompt（提示词） 版本、dataset/evaluation 记录模型 | 可借鉴字段和 UI 语义；先在 MySQL/现有观测体系中实现最小 trace，不引入其完整自托管栈 |
| [traceloop/openllmetry](https://github.com/traceloop/openllmetry) | Apache-2.0 | OpenTelemetry LLM span 语义和 HTTP→Broker（消息代理）→Worker（异步工作进程） trace context 传播 | 评估异步跨进程上下文传递成本；不得让第三方 instrumentation 记录原图、密钥或长期 signed URL |
| [promptfoo/promptfoo](https://github.com/promptfoo/promptfoo) | MIT | Prompt（提示词） matrix、assertion、回归运行和版本化结果 | 只用于离线 Prompt（提示词） 回归；医学 scorer、trusted gold 和 Holdout 必须由本项目独立定义 |
| [openai/evals](https://github.com/openai/evals) | MIT | 数据集/任务注册、可复现评测 run 和 registry | 参考任务注册表；不能直接使用旧文本 evaluator 替代病例级医学分母 |
| [EleutherAI/lm-evaluation-harness](https://github.com/EleutherAI/lm-evaluation-harness) | Apache-2.0 | task YAML、固定 Holdout、bootstrap 置信区间 | 仅借鉴离线评估组织方式；医学影像需自定义 multimodal adapter 和 paired scorer |
| [stanford-crfm/helm](https://github.com/stanford-crfm/helm) | MIT | scenario/adaptor/metric 分层、结果 lineage 和 benchmark runner | 参考实验编排结构；裁剪为本项目 validation-only runner，不能直接当生产服务 |
| [Arize-ai/phoenix](https://github.com/Arize-ai/phoenix) | ELv2 | OTEL trace、LLM span 和 eval 观测思路 | ELv2 不是常规 OSI 开源许可证，商用或分发前必须法务审查；首轮不作为强依赖 |

### 15.1 推荐吸收顺序

```text
Study/Series/Instance 完整性与去重（dcm4chee/OHIF）
→ DICOMWeb/原图获取边界（MONAILabel，须先过媒体 ADR）
→ MySQL Run + Outbox + relay（transactional-outbox）
→ Celery/RabbitMQ Worker（celery）
→ 最小 trace/Prompt manifest（Langfuse/OpenLLMetry 的字段语义）
→ 离线 Prompt/模型评估（promptfoo/OpenAI Evals/HELM）
```

### 15.2 明确不直接引入的内容

- 不复制任何第三方项目的医学结论、阈值、标签或 scorer；
- 不因为项目支持 DICOM、Batching、Tracing 或 Benchmark 就认为医学链可用；
- 不把 ELv2 项目作为默认依赖；许可证和数据处理条款必须单独审批；
- 不在 P0 引入 Ray、BentoML、vLLM、Langfuse、Phoenix 等大型运行时；先完成可替换接口和零模型工程回归；
- 不将 GitHub 项目的示例数据、公开标签或模型输出混入 trusted gold、Prompt 或 Holdout。
