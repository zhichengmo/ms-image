# MS-Image 借鉴 QJ 开放平台与模块收敛调整方案

状态：`PROPOSED_ARCHITECTURE_ADJUSTMENT / READ_ONLY_AUDIT_COMPLETE / NO_SCHEMA_CHANGE_AUTHORIZED`

更新日期：2026-08-20

适用范围：

- `ms-image` 与 `qj-open-plataform` 的边界设计；
- MS-Image 在线公共领域、XRay 专项、Evaluation、兼容遗留和横切基础设施的收敛；
- 后续入口、部署、Worker、数据库连接管理和内部模块化重构；
- 不包含数据库迁移、真实基础设施操作、真实 Provider 接入或医学发布。

2026-08-20 静态审计基线（历史，不是当前 worktree HEAD）：

| 仓库 | Git 基线 | 审计时间 | 工作树结论 |
|---|---|---|---|
| `ms-image` | `2fa2a8b5cd01777204e4952641b97174d9dc5879` | 2026-08-20 | 存在用户未提交的文档/handoff 与 `app/models/evaluation.py` 格式改动；不得 reset/clean/checkout/批量覆盖 |
| `qj-open-plataform` | `8246956cd61b6f2533f0c4fba34364245bda983a` | 2026-08-20 | 审计时工作树干净 |

> 本文是基于现有代码和 QJ 参考仓库形成的调整建议，不是第二份字段权威。
> 上表记录 2026-08-20 进行 QJ 对照时的历史静态审计基线；任何实施前必须重新核验 `git rev-parse HEAD`、dirty state 和该基线之后的提交。后续未重新核验的结论不得继续表述为当前源码 `CONFIRMED`。
> 精确表字段、状态、索引、Stage 合同和医学边界继续以设计母文、14 号 XRay 架构文档、17 号 Prompt 运行合同及当前源码为准。
> 本文不授权生成 Alembic/数据迁移脚本、测试脚本或连接真实 MySQL、OSS、RabbitMQ、Kong、Nacos、Provider。

---

## 1. 结论与不可变边界

### 1.1 推荐决策

```text
Decision: existing-entry internal modular convergence
Confidence: CONFIRMED for current code topology; PROPOSED for future restructuring
```

MS-Image 不应重写成 QJ，也不应把自身合并进 QJ 的共享 `platform` 数据库。推荐关系是：

```text
QJ Open Platform
= 客户/开发者入口 + Project/API Key + Capability + Kong + 限流 + Usage/Wallet/Ledger + SDK/Webhook

MS-Image
= 影像接入 + OSS 对象真相 + Study 修订 + Task/Stage + AI Call + Report + Evaluation
```

两者应保持独立部署、独立数据库所有权和独立发布门禁：

```text
开发者应用
  -> Kong
  -> QJ Platform Runtime
  -> MS-Image 内部影像合同
  -> MS-Image Online Plane
  -> Imaging Outbox / Worker
  -> Report
  -> Evaluation Export
  -> MS-Image Evaluation Plane
```

### 1.2 MS-Image 必须保留的事实所有权

以下事实继续只由 MS-Image 拥有：

- Session、Study、Series、Image 以及 Study revision；
- OSS 对象键、版本、摘要、尺寸、DICOM 技术元数据与服务端校验结果；
- Task 冻结输入、Config/Profile/Prompt/Schema/模型/预算指纹；
- Stage checkpoint、Outbox、AI Call、lease、CAS、重试和 dead-letter；
- 不可变 Report revision 与 `current_report_id`；
- 独立 `ms_image_eval` 中的 Evaluation Job、Run、Outbox、Artifact；
- 工程状态和医学状态的双状态合同。

这些边界已由设计母文的“MS-Image 自己拥有/只保存 opaque ID/不迁入”合同定义，见
`docs/ms-image-final-architecture-and-database-design.md:376-418`。

### 1.3 MS-Image 明确不接管的 QJ 事实

MS-Image 不新增或复制以下事实：

```text
QJ User / Organization / Project
API Key / Kong Consumer / Credential
Capability 商品目录 / 商业 QPS / 套餐
Usage / Wallet / Ledger / Order / Refund
客户 SDK / 客户 Webhook / 管理后台 RBAC
```

对外业务身份只以受信的 opaque ID 进入 MS-Image：

```text
requester_id  = QJ 经过认证和映射后的调用主体 opaque ID
subject_id    = 宠物/患者 opaque ID
request_id    = 可重放的业务幂等键
trace_id      = 跨边界追踪标识
```

禁止把 QJ `project_id`、租户表或钱包状态复制为 MS-Image 目标 `tenant_id`、Foreign Key 或业务主数据。

### 1.4 不进行全链重写

当前不建议：

- 把 MS-Image 改造成 QJ 后端 Monorepo 的一个共享包；
- 新建第二套 Repository/CRUDBase/DatabaseService；
- 重新设计第三套 Outbox、OSS Gateway、Task Runner 或 Evaluation Plane；
- 为“专项”增加一整套新表、DAL、Worker 和医学事实；
- 直接删除 `xray_accuracy` 旧表/API/Worker；
- 用透明 HTTP Proxy 代替 MS-Image 的 Task/Stage/Report 合同。

原因是新通用影像链已具备 Task/Stage/Outbox/Report/Evaluation 代码，当前主要风险是两套链并行、部署编排滞后、代码职责漂移和真实运行未资格化，而不是缺少新的框架。

---

## 2. 事实等级与参考仓库的正确使用方式

### 2.1 本文事实等级

| 标记 | 含义 |
|---|---|
| `CONFIRMED` | 当前源码、配置或 Git 基线直接证明 |
| `INFERRED` | 根据多个已确认事实得出的架构推论，尚未在真实环境验收 |
| `PROPOSED` | 本文规定的后续调整，不表示已经实现 |
| `UNKNOWN` | 需要真实环境、消费者、数据或业务 owner 确认 |
| `N/A` | 当前阶段明确不适用 |

### 2.2 QJ 的实际定位

QJ 当前实现不是强自治微服务体系，而是“共享代码/主要数据库的可独立部署后端 Monorepo”：

```text
Kong
  -> Platform API :9701
  -> Admin API    :9702
  -> Auth API     :9903
  -> Billing Worker / Billing Beat

共享：core / models / schemas / crud / backend pyproject
```

其已实施结构见 `qj-open-plataform/docs/backend-monorepo-architecture.md:173-201`、
`qj-open-plataform/backend/services/platform/main.py:10-24` 和
`qj-open-plataform/deploy/compose/services.yaml:35-214`。

因此 QJ 是可借鉴的“控制面和工程编排参考”，不是可直接复制的影像执行内核。

### 2.3 QJ 文档的使用边界

以下 QJ 内容可作为实际参考：

- 根 `README.md`；
- `docs/backend-monorepo-architecture.md`；
- 当前 `backend/`、`deploy/compose/`、`kong-config/` 源码；
- Git SHA `8246956` 对应的行为。

以下内容只作为目标设计或草案，不得当作当前实现事实：

- `docs/arch.md`；
- `docs/micro-service.md`；
- `docs/new_arch.md`；
- `docs/open-platform-domain-model.md`；
- `docs/arch-blueprint.md`。

例如 `open-platform-domain-model.md` 明确标为 PostgreSQL DDL 草案和目标设计，不能作为 QJ 当前数据库或接口事实。

### 2.4 MS-Image 当前状态的权威顺序

MS-Image 根 README、CLAUDE 和早期重构导航中仍保留“仅 P1 已完成”的历史表述；当前实现状态必须优先使用：

1. 当前 worktree 源码和当前 Git SHA；
2. `.agent-handoff/snapshot.md`、`risks.md`、`backlog.md`；
3. `docs/refactor/15-full-chain-gap-analysis-and-execution-plan.md`；
4. 若涉及 AIConfig、AIRequest、Prompt、Schema 或 XRay 医学 Stage，再读取 `docs/refactor/17-prompt-runtime-contract-and-minimal-provider-plan.md`；
5. 设计母文和 14 号文档定义的目标合同。

截至 2026-08-20，`PROVIDER_DISABLED_FULL_CHAIN_PASSED` 只代表 inline fake 工程组合链通过；不代表真实 MySQL/OSS/RabbitMQ/Provider，也不代表医学准确率或生产发布通过。

---

## 3. 从 QJ 借鉴什么，明确不借鉴什么

| QJ 能力/模式 | 审计事实 | MS-Image 决策 | 调整原则 |
|---|---|---|---|
| 多入口应用工厂、每个服务独立 Settings/lifespan | QJ Platform/Admin/Auth 分别创建应用并通过 Compose 独立运行 | `PROPOSED` 借鉴 | MS-Image 保持同一业务仓库，但 User API、Admin API、Relay、Worker 使用独立入口和生命周期 |
| DatabaseRegistry + 命名 Session | QJ `DatabaseRegistry` 按逻辑名创建 Engine/SessionFactory/healthcheck | `PROPOSED` 借鉴 | `online/evaluation` 是自有数据平面；`hd` 仅是可选外部集成 alias，必须懒初始化，不能成为通用 readiness/startup 依赖；保留 online/evaluation 名称不相同的失败关闭 |
| `manage.py` + Compose 环境覆盖 | QJ 用薄封装选择 Compose 文件，不自行托管 Uvicorn | `PROPOSED` 借鉴 | 替代或逐步淘汰 `run_servers.py` 的多进程监督责任；Worker 作为独立 Compose 服务 |
| Kong + decK 静态/动态边界 | QJ 静态 Route/Plugin 用 decK，运行时 Key Credential 动态维护 | `PROPOSED` 借鉴到系统边界 | Kong、Project、API Key 属于 QJ；MS-Image 不管理 Consumer/Credential |
| API Key 业务二次校验 | QJ 在 Kong 后复核 Key、Project、scope、credential 和 consumer | `PROPOSED` 仅作为外部入口 | QJ 终结外部 API Key；MS-Image 接收内部签名身份或服务 JWT，继续自身资源 owner 校验 |
| 多库读聚合 | QJ 的 Service 可明确接收多个 Session | `PROPOSED` 有条件借鉴 | 仅用于 Operations、Exporter 等明确跨 online/evaluation 读模型；不得伪造跨库原子事务 |
| 账务幂等、冻结余额、补偿扫描 | QJ Billing 有 Wallet/Ledger/Usage 幂等与 reconcile | `PROPOSED` 作为 QJ 侧集成约束 | 计费仍归 QJ；MS-Image 提供可重放的 Task/Report 终态事实 |
| 动态 Capability Provider HTTP Proxy | QJ Runtime 根据路径转发上游并在响应内编排 Usage/结算 | `REJECTED` 作为 MS-Image 主链 | 透明转发不能冻结 Study/Config/Profile/预算，也不适合上传、异步 Stage 和 Report |
| QJ 请求事务内调用上游 HTTP | QJ Runtime 在 session dependency 生命周期内查询/调用 Provider，并存在手动 commit | `REJECTED` | MS-Image 保持“短 DB 事务 -> 事务外 I/O -> 新短 DB 事务 CAS” |
| 启动 `metadata.create_all()` 与演示 seed | QJ lifespan 会初始化表并可 seed demo data | `REJECTED` | 医学在线库与 Evaluation 库必须经单独授权迁移和真实验证，不在启动时建表/seed |
| Integer ID、`/{id}` 路由、统一软删除 | QJ 实际保留多个 path ID 路由和 `BaseModel.id:int` | `REJECTED` | MS-Image 保持 opaque `VARCHAR(64)`、query/body ID、无 FK/Enum、不可变 revision/CAS 语义 |
| Nacos Provider discovery | QJ Model/Schema 可配置 Nacos，但 Runtime 当前拒绝非 `static` Provider | `DEFERRED` | 未完成实例选择/健康过滤/缓存/熔断/观测前，不把 Nacos 当成可用前提 |

---

## 4. 推荐的 QJ 与 MS-Image 集成合同

### 4.1 外部调用与内部身份

```text
外部客户端
  -> Kong + QJ API Key
  -> QJ Platform Runtime 认证、限流、能力授权
  -> QJ 生成受信内部身份和 request context
  -> MS-Image
```

QJ 传入 MS-Image 的身份合同必须满足：

```text
- requester_id：已认证 Project/用户/服务映射得到的全局 opaque ID
- subject_id：宠物/患者的全局 opaque ID
- request_id：稳定业务幂等键
- trace_id：跨系统追踪 ID
- scopes：最小内部资源 scope
```

推荐 QJ 使用其现有的映射原则：

```text
(project_id, external_user_id)
  -> platform_subject_uuid
  -> MS-Image requester_id / 下游主体引用
```

MS-Image 不保存 QJ 的 `project_id`、租户行、钱包余额或 API Key 明文/哈希。

### 4.2 上传对象唯一所有权

推荐：**原始影像对象生命周期由 MS-Image 独占。**

```text
QJ：商业 Task、调用身份、能力授权、计费状态
MS-Image：Image、ObjectRef、对象 key、直传授权、multipart、校验、替换、隔离、reconcile
```

禁止让 QJ `FileObject` 与 MS-Image `image_record` 同时充当同一影像 bytes 的 owner。否则会形成两套 object key、摘要、版本、保留策略、删除和孤儿对象责任。

### 4.3 QJ CapabilityTask 与 MS-Image Task

QJ 的通用 `CapabilityTask` 当前可以创建 `queued` 任务，但没有已确认的 MS-Image 执行 Adapter。接入时必须建立明确的一对一映射：

```text
QJ CapabilityTask
  -> MS-Image Session / Study / Image / Task
  -> MS-Image Report 或终态工程失败
  -> QJ CapabilityTask 状态投影与计费判定
```

第一阶段不建议新增 `qj_task_mapping` 表。优先复用现有：

```text
source_system
requester_id
request_id
business_key
trace_id
Task.request_snapshot_json
```

只有这些字段无法证明一对一重放、状态投影和对账时，才以“独立事实所有权”为理由评审新增表。

### 4.4 计费终态

不得在“MS-Image 创建 Task 返回 201”或“QJ HTTP Proxy 返回 2xx”时直接收费。

计费合同必须预注册并引用稳定任务事实，例如：

```text
billable =
  Task.execution_status == completed
  AND Report.status in {final, published}
  AND 业务合同允许该 medical_status/技术产物计费
```

以下默认不收费，除非商业合同另行冻结：

- Task 创建失败；
- 上传/对象校验失败；
- Provider/Schema/lease/reconcile 技术失败；
- `cancelled`、`dead_letter`；
- `ai_medical_status=not_produced`；
- 客户重复轮询；
- Evaluation 执行失败。

QJ 的 Usage/Wallet/Ledger 是唯一财务事实源。MS-Image 仅提供幂等、可追溯、不可变的业务终态事实。

### 4.5 状态同步与客户 Webhook

首期选择以下之一，并冻结幂等规则：

```text
A. QJ 主动轮询 MS-Image Task/Report 查询接口；
B. MS-Image internal Outbox -> QJ Adapter -> QJ 更新 CapabilityTask；
```

客户 Webhook 继续由 QJ 统一发送：

```text
MS-Image internal event
  -> QJ Adapter
  -> QJ CapabilityTask / Usage
  -> QJ customer webhook
```

MS-Image 首期不新增客户 callback/ack 生命周期，保持当前设计合同。

---

## 5. MS-Image 目标模块分类

### 5.1 分类总览

| 分类 | 事实边界 | 允许新增什么 | 不允许新增什么 |
|---|---|---|---|
| A. 公共在线影像领域 | 多模态共享的 Session/Study/Series/Image/Task/Stage/Outbox/AI Call/Report | 通用实体 DAL、Schema、8 个在线 Service 的内部协作组件 | XRay 专用表、器官/Family 业务表、租户/钱包表 |
| B. XRay 专项 | XRay Profile、Prompt、输出 Schema、Family/Focus/Strategy、XRay Stage handler | `app/service/stages/xray/` 内的处理器、XRay Schema、Config manifest | 第二套 Task/Stage/Outbox/Call/Report 事实源 |
| C. Evaluation | Gold/实验/评分/产物/统计与审批证据 | 独立 Evaluation Model/DAL/Service/Worker/Artifact | 在线 Task/Report/AI Config 的直接写入或 Gold 泄漏 |
| D. 兼容遗留 | `xray_accuracy` 历史 API、历史表、旧 Worker、旧 OSS 映射 | 显式 CompatibilityAdapter、只读/迁移导入、消费者退役审计 | 新业务能力、新默认部署路径、新医学事实 |
| E. 横切基础设施 | DB、Broker、ObjectStore、Provider transport、readiness、logging | Gateway/Registry/Contract/Relay/配置 | 具体医学规则、XRay 表/DAL 依赖、客户商业事实 |

### 5.2 公共在线 Model 与 DAL

以下是目标公共在线事实，继续“一张表 -> 一个 Model -> 一个 Dal”：

| 公共事实 | 当前 Model/DAL | 调整结论 |
|---|---|---|
| Session | `models/session.py` / `crud/session.py` | 保留，作为影像业务生命周期根 |
| Study | `models/study.py` / `crud/study.py` | 保留，拥有 revision、完整性和 ready 状态 |
| Series | `models/series.py` / `crud/series.py` | 保留，属于 Study 的影像分组事实 |
| Image | `models/image.py` / `crud/image.py` | 保留，拥有 ObjectRef、校验、替换与隔离事实 |
| Task | `models/task.py` / `crud/task.py` | 保留，拥有冻结请求、双状态、预算和 current report pointer |
| StageCheckpoint | `models/stage_checkpoint.py` / `crud/stage_checkpoint.py` | 保留，拥有 Stage state、lease、input/output 与 accepted call |
| Outbox | `models/outbox.py` / `crud/outbox.py` | 保留，拥有可靠发布事实 |
| AIConfigRecord | `models/ai_config_record.py` / `crud/ai_config_record.py` | 保留，拥有冻结/激活的 Pipeline、Prompt、Schema、Provider、预算事实 |
| AICall | `models/ai_call.py` / `crud/ai_call.py` | 保留，拥有物理调用准备、回执、unknown 和审计事实 |
| Report | `models/report.py` / `crud/report.py` | 保留，拥有不可变 revision 和发布/作废生命周期 |
| ObjectReconcileCursor | `models/object_reconcile_cursor.py` / `crud/object_reconcile_cursor.py` | 保留为 Image 对账运行游标；不是公共文件资产表 |

公共模型继续继承 `ImagingRecordBase`，使用 opaque `VARCHAR(64)` 单列主键；见
`app/models/imaging_base.py:15-38`。

### 5.3 XRay 专项 Model 的正确归宿

`app/models/xray_accuracy/` 当前含有另一套：

```text
XRaySession / XRaySessionEvent / XRayStudySnapshot / XRayImageAsset
XRayRun / XRayRequestSnapshot / XRayStageCheckpoint / XRayModelCall
XRayOutbox / XRayTraceEvent
```

对应的 `app/crud/xray_accuracy/` 也具有一整套生命周期、Outbox、lease、replay 和调用状态。

`CONFIRMED`：这不是“5 个轻量 Stage handler”，而是第二套持久化/执行面。

`PROPOSED`：目标状态如下：

```text
新 XRay 业务事实
  -> 只能写公共在线十表
  -> XRay 差异进入 AIConfig/Profile/Prompt/Schema/Stage output

旧 xray_accuracy 事实
  -> 仅 Compatibility / LegacyMigrationAdapter / validation-only
  -> 不新增业务字段、表、默认 Worker 或新 API
```

在未确认外部消费者、迁移映射和历史审计期限前，`xray_accuracy` 不删除、不改写、不做批量迁移。

### 5.4 Evaluation Model 的正确归宿

以下模型保持独立 Evaluation Plane：

```text
EvaluationJob
EvaluationOutbox
EvaluationRun
EvaluationArtifact
```

它们拥有独立数据库 session、独立 Broker topology、独立 Worker lease 和 Artifact 合同；不与在线 Task/Report 合表，也不复制 Gold/holdout 到在线库。

`OperationalStatusService` 是受控的跨库只读聚合例外，不是把 Evaluation 合并进在线 Service 的理由。

---

## 6. Service、Stage 与 Worker 的目标边界

### 6.1 8 个公共在线业务 Service

在线业务 Service 数量固定为 8；内部辅助类、Registry、Gateway、Relay、Validator 不计为新的业务 Service。

| Service | 唯一职责 | 可协调的 Dal | 不负责 |
|---|---|---|---|
| `SessionService` | Session 创建、查询、状态推进、owner/幂等 | Session | Study/医学判断/OSS |
| `StudyService` | Study/Series、revision、完整性、finalize | Study、Series、必要 Image 查询 | 直传签名、Provider 调用 |
| `ImageService` | Image 生命周期、替换、对象校验接受、隔离、reconcile 编排 | Image、Series、Study、Outbox、Cursor | 保存 bytes、医学判断 |
| `TaskService` | 只从 ready Study 冻结 Task、首 Stage、首 Outbox | Study、Series、Image、Config、Task、Stage、Outbox | 直接发 Broker/Provider、调用方选择 release |
| `ImagingExecutionService` | Stage claim、状态持久化、下一 Stage、Task 终态、reconcile | Task、Stage、Outbox、AICall、Report | XRay Prompt 细节、Gold、客户计费 |
| `AIConfigService` | Config revision 编译/校验/激活 | AIConfigRecord | 运行病例、写 Report |
| `AIRequestService` | 物理 AI Call 的 prepare/send-reconcile/receipt/budget 合同 | AICall、Task、Stage、Config | 决定 XRay 医学策略、读取 Gold |
| `ReportService` | Report final/publish/void/current pointer/query | Report、Task、Stage | 改写医学 Finding、回调/计费 |

### 6.2 Stage 的公共/专项划分

| Stage | 目标归属 | 当前实现位置 | 调整结论 |
|---|---|---|---|
| `StudyPreparation` | 公共 Stage framework；模态输入适配通过冻结 Config 注入 | `ImagingExecutionService.complete_study_preparation` | 从 Execution 的具体完成方法中抽成 `app/service/stages/common/` handler；返回 `StageResult` |
| `JointPrimaryReader` | XRay 专项医学 Stage | `ImagingExecutionService.complete_joint_primary_reader` 当前为 provider-disabled stub | 移至 `app/service/stages/xray/`；由 XRay Prompt/Schema 构造调用命令，通过公共 `AIRequestService` 执行 |
| `FamilyRouting` | XRay 专项确定性 Stage | `ImagingExecutionService.complete_family_routing` | 移至 `app/service/stages/xray/`；不读图、不读 Gold、不调用 Provider、不改医学结论 |
| `TargetedReview` | XRay 专项医学 Stage | `ImagingExecutionService.complete_targeted_review` 当前为 provider-disabled stub | 移至 `app/service/stages/xray/`；最多一次、完整病例输出、技术失败 fail closed |
| `DecisionFinalization` | 公共 Stage framework | `ImagingExecutionService.complete_decision_finalization` | 移至 `app/service/stages/common/`；只验证唯一 owner 并调用 `ReportService` |

目标目录是现有 `app/service/` 下的内部模块，而不是新的平行 service 包：

```text
app/service/
├── imaging_execution_service.py       # 唯一执行状态 owner：claim/persist/schedule/reconcile
├── ai_request_service.py              # 唯一物理 Provider Call owner
├── report_service.py
└── stages/
    ├── common/
    │   ├── study_preparation.py
    │   └── decision_finalization.py
    └── xray/
        ├── joint_primary_reader.py
        ├── family_routing.py
        └── targeted_review.py
```

每个 Stage：

- 具有固定 `handler_key`、`handler_version`、输入 Schema、输出 Schema；
- 只返回 `StageResult` 或等价 DTO；
- 不直接 `commit()`、不直接 SQL、不直接把 Task/Report 推进到终态；
- 不直接读取 Gold/Holdout；
- 由 `ImagingExecutionService` 在短事务中持久化、创建下一 Stage/Outbox 和处理 lease/CAS。

`StageRegistry` 继续只注册固定 handler/version。当前 `app/core/pipeline.py:61-112` 已注册五个 stage key 和两个 XRay profile，但 handler 实现仍集中在 `ImagingExecutionService`，这是应逐步收敛的实现偏差。

### 6.3 AI 调用层的收敛

当前同时存在：

```text
app/service/ai_request_service.py
app/service/xray_accuracy/ai_request_service.py
```

目标职责分离：

```text
AIRequestService（公共）
  = AICall prepare、idempotency、预算、发送、receipt、unknown 对账、结果技术状态

XRay Reader/Review Stage（专项）
  = 选择冻结 Prompt、XRay Schema、Family/Focus/Strategy、构造 AIRequestCommand
```

因此：

- 不再把 `XRayAIRequestService` 扩展为第二个主调用入口；
- 不把 XRay Prompt、Family/Focus 迁入 `AIRequestService`；
- Provider transport、connection pool、egress proof 可逐步保持在 `app/core/ai/`，但不得反向依赖 `xray_accuracy` 表；
- 当前 `app/core/readiness.py` 对 `XRayPromptRegistry` 的直接依赖，应演进成由通用 provider-readiness contract 收集各模态 contribution，而不是 core 直接 import XRay 专项实现。

### 6.4 ImageService 的内部拆解

`app/service/image_service.py` 约 1446 行，当前同时拥有：

```text
创建/替换
直传签名准备
multipart 初始化/parts/完成/中止
上传完成接收
对象校验 lease
校验成功/重试/隔离
过期上传与 ready object reconcile
```

`PROPOSED`：保留唯一对外 `ImageService`，但将其内部拆为私有用例协作者；这些不是新的公开业务 Service，不单独暴露 DI，不单独拥有表/DAL：

```text
ImageService（对外 facade，唯一 API 入口）
├── ImageUploadWorkflow             # direct upload 准备和失败补偿
├── ImageMultipartWorkflow          # multipart session/parts/complete/abort
├── ImageValidationLifecycle        # claim/heartbeat/finalize/retry/quarantine
└── ImageReconcileWorkflow          # 过期上传、ready object、cursor reconcile
```

第一步必须先将 `app/api/api_v1/endpoints/images.py` 的：

```text
短事务 begin
-> ObjectStorageGateway 外部 I/O
-> 第二短事务/补偿
```

整个顺序下沉到 `app/service/` 内的 Image workflow。API 只保留：

```text
路由 + 鉴权 + payload + 调用 workflow + GenericResponse
```

当前 API 在 `images.py:45-84`、`:92-127` 等处直接创建 gateway、显式管理事务并执行 OSS 调用，属于需要收敛的编排泄漏。此调整不改变“事务外 OSS I/O”的正确性，只把它从 endpoint 移回 Service 边界。

### 6.5 Worker 的目标边界

| Worker | 目标职责 | 当前结论 | 调整方向 |
|---|---|---|---|
| `imaging_worker` | 消费消息、建立短事务、调用公共 Image/Execution Service | 已有 Image validation、Stage execution、reconcile | 保持为主链 Worker；reconcile 中的 DAL 直连逐步下沉到 Service 方法 |
| `evaluation_worker` | 消费 Evaluation Outbox、执行 scorer、写 Evaluation Run/Artifact | 已有独立 session/worker | 保持独立；Evaluation Relay/DAL 调用可继续作为受控基础设施，禁止在线写入 |
| `xray_accuracy_worker` | 旧 validation-only、兼容、历史 qualification/replay | 仍有直接 DAL/technical executor/old outbox 编排 | 不扩展、不设为新默认路径；等消费者/迁移确认后收敛为 compatibility worker 或退役 |

Worker 只负责：

```text
consumer identity
session/transaction boundary
调用 Service
ACK/retry/reject 映射
进程生命周期
```

Worker 不应成为另一个业务状态机 owner。特别是 `workers/xray_accuracy_worker/technical_worker.py` 当前直接构造 XRay DAL 并维护执行编排，是旧链需要隔离的原因，不应复制到新公共 Worker。

---

## 7. 当前代码审计结果与处理顺序

### 7.1 已审计范围

本轮静态审计覆盖：

```text
app/api/
app/service/
app/crud/
app/models/
app/schemas/
app/core/
workers/
main.py
run_servers.py
docker-compose.yml
```

覆盖的代码量约 29,951 行。代码按以下组分类：

| 路径组 | 分类 | 当前处理政策 |
|---|---|---|
| `app/models/{session,study,series,image,task,stage_checkpoint,outbox,ai_config_record,ai_call,report}.py` | 公共在线 Model | 继续作为目标事实源 |
| `app/crud/{session,study,series,image,task,stage_checkpoint,outbox,ai_config_record,ai_call,report}.py` | 公共实体 DAL | 保持 `DalBase`；仅按实体查询/状态 CAS 拆分，不新增 Repository |
| `app/schemas/{session,study,image,task,report,imaging_common,outbox,ai_config}.py` | 公共 API/消息合同 | 继续作为目标合同；专项字段不污染通用请求 |
| `app/service/{session,study,image,task,imaging_execution,ai_config,ai_request,report}.py` | 8 个在线业务 Service | 目标主链；进行内部职责收敛 |
| `app/core/{messaging,imaging,ai}.py` | 横切基础设施 | 保持无业务 owner；移出对 `xray_accuracy` 表/Service 的反向依赖 |
| `workers/imaging_worker/` | 公共执行 Worker | 补进实际部署拓扑，逐步去除直连 DAL 编排 |
| `app/models/evaluation.py`、`app/crud/evaluation.py`、`app/service/evaluation_*.py`、`workers/evaluation_worker/` | Evaluation Plane | 继续隔离数据库、队列、scope 和 Artifact |
| `app/models/xray_accuracy/`、`app/crud/xray_accuracy/`、`app/service/xray_accuracy/`、`workers/xray_accuracy_worker/` | XRay 遗留/兼容平面 | 冻结扩展；经 CompatibilityAdapter/迁移计划逐步收敛 |
| `app/api/api_v1/endpoints/xray_*`、`app/api/admin_v1/endpoints/xray_*` | XRay 专项与兼容入口 | 新能力移向公共 API + XRay Stage；旧入口先标识兼容，不删除 |
| `app/crud/base.py` | 遗留 MongoEngine CRUDBase | 禁止用于 MySQL 目标链 |

### 7.2 高优先级问题

| 优先级 | 发现 | 证据 | 处理决策 |
|---|---|---|---|
| P0 | 新公共影像/评测 Worker 未进入 Compose，旧 XRay relay/worker 却是唯一 broker 默认编排 | `docker-compose.yml:63-110`；`workers/imaging_worker/`、`workers/evaluation_worker/` 已存在 | 先完成部署拓扑文档与 Compose 调整设计；实际改 Compose 前不触真实环境 |
| P0 | 公共 Stage registry 已注册 5 个 stage，但处理逻辑集中在 `ImagingExecutionService` | `app/core/pipeline.py:61-112`；`app/service/imaging_execution_service.py:56-161` | 将 Stage handler 逐步抽到 `app/service/stages/common|xray`，Execution 保留唯一状态机 owner |
| P0 | `ImageService` 过大，Image endpoint 直接编排 transaction + OSS | `app/service/image_service.py`；`app/api/api_v1/endpoints/images.py:45-84` | 先下沉 workflow 编排，API 瘦身；不改变对象校验/补偿语义 |
| P0 | 公共模型和 `xray_accuracy` 模型都通过 `app/models/__init__.py` 注册 | `app/models/__init__.py:1-29` | 新目标链不得 import/写入 XRay legacy Model；迁移前保留注册但显式标记 compatibility |
| P0 | `app/core/imaging/ingest.py`、`oss_resolver.py` 和 readiness 直接依赖 XRay 专项 Model/Prompt | `app/core/imaging/ingest.py`、`app/core/imaging/oss_resolver.py`、`app/core/readiness.py:20-63` | 将 XRay adapter 移出 core 或反转为专项 contribution；core 不反向依赖专项 persistence |
| P1 | 公共和 XRay 各有 AI request/execution/outbox/lifecycle 链 | `app/service/ai_request_service.py`；`app/service/xray_accuracy/ai_request_service.py`；对应 Model/DAL/Worker 目录 | 以公共 Task/Stage/Outbox/AICall/Report 为唯一目标事实；旧链冻结扩展 |
| P1 | Legacy XRay API/Worker 与新链同时暴露 | `app/api/api_v1/endpoints/xray_legacy_compat.py`；`workers/xray_accuracy_worker/` | 建立消费者清单、映射和退役门禁；未知消费者前禁止删除 |
| P1 | `run_servers.py` 自己监督两个 API 进程，`main.py` 承载两个 FastAPI app | `run_servers.py:6-48`；`main.py:25-54` | 借鉴 QJ 独立 app factory/lifespan/Compose 进程；不必拆仓库 |
| P2 | 当前 DB Engine 在 import 时硬编码构造 online/evaluation/hd | `app/core/async_db.py:7-101` | 引入命名 Registry，但必须保留 Evaluation fail-closed 隔离；不借鉴 QJ `create_all` |
| P2 | QJ 尚未实现真实 Nacos Runtime，MS-Image 也尚无需要 | QJ `CapabilityProviderService` 对非 static 直接拒绝 | 不提前引入 Nacos |

### 7.3 大文件不是自动拆分理由

以下文件需要优先审查，但不能只因行数拆出新的业务边界：

```text
app/service/image_service.py                    ~1446 行
app/crud/xray_accuracy/outbox.py                ~919 行
app/crud/evaluation.py                          ~806 行
workers/xray_accuracy_worker/replay.py          ~743 行
app/service/xray_accuracy/execution_service.py  ~647 行
app/service/xray_accuracy/technical_executor.py ~619 行
```

处理原则：

1. 先按“唯一事实 owner、事务边界、I/O 边界、调用者”判断职责；
2. 公共 Service 可以协调多个实体 DAL，不能强行一表一 Service；
3. DAL 可按实体拆文件，但不能把 HTTP、业务流程、Provider 或 Broker 编排搬进去；
4. 专项 Stage 可以拆 handler，但不能拥有第二套 Task/Stage/Outbox/Report；
5. 只有兼容链确认无消费者且有迁移/保留证据后才可删除。

---

## 8. 分阶段调整计划

### Phase A：冻结边界与部署真相（无 schema 变更）

目标：先让“当前应该运行什么”与“当前代码实现了什么”一致。

1. 把本文件、15 号执行计划和 handoff 作为当前调整入口；
2. 明确 `imaging_worker`、`evaluation_worker`、`xray_accuracy_worker` 的运行角色；
3. 为公共 imaging/evaluation relay/worker 补齐拟议 Compose 拓扑和启动合同；
4. 将 legacy XRay relay/worker 标为兼容 profile，而不是默认未来主链；
5. 保持 `NOT_MIGRATED`、`NOT_RUNTIME_VALIDATED`，不启动真实基础设施；
6. 为部署变更建立 graceful shutdown、prefetch、concurrency、rolling upgrade 合同。

通过标准：

```text
代码入口、Compose 入口、readiness、queue topology、Worker 名称和 handoff 状态不再互相矛盾。
```

### Phase B：公共 Execution 与 XRay Stage 收敛（无 schema 变更优先）

目标：让 `ImagingExecutionService` 成为唯一公共执行状态机，XRay 只是 Stage 实现。

前置条件：先读取并保持 17 号 Prompt 运行合同。任何 handler 目录调整不得改变 Primary × 1、Targeted × 0..1、Config Release 唯一版本中心、真实 Prompt/Schema 编译、泄漏检查或 provider-disabled 真 Bundle 的要求。

1. 引入固定 Stage handler protocol；
2. 将 `StudyPreparation`、`DecisionFinalization` 抽为 common handler；
3. 将 `JointPrimaryReader`、`FamilyRouting`、`TargetedReview` 抽为 XRay handler；
4. Handler 返回 `StageResult`，不得直接写 Task/Report；
5. `ImagingExecutionService` 继续负责 claim、CAS、lease、持久化、下一 Stage/Outbox、终态；
6. `AIRequestService` 成为唯一物理调用事实 owner；
7. 当前 provider-disabled 行为必须先保持等价，再谈真实 Provider。

通过标准：

```text
新 XRay Profile 不再新增 xray_accuracy Task/Stage/Outbox/Call/Report 事实；
一个 Stage 的业务结果和状态推进可以通过公共 execution 链审计。
```

### Phase C：Image API 编排下沉（无 schema 变更）

目标：API 不再拥有 OSS/事务业务编排。

1. 将 direct/multipart/replace/complete/abort 的三段事务和外部 I/O 顺序移入 Image workflow；
2. endpoint 仅注入 caller、payload、workflow 和响应；
3. 失败补偿和 ObjectStoreError 映射由 Service 产生稳定业务错误，API 统一包装；
4. ImageWorker reconcile 使用 Service 方法而非直接 DAL 编排；
5. 保持所有现有 query/body ID 和 ObjectRef 合同。

通过标准：

```text
API 层不直接 begin 多段事务，不直接驱动 OSS 生命周期；
事务内仍无 OSS/Broker/Provider I/O。
```

### Phase D：DatabaseRegistry 与独立入口（无 schema 变更）

目标：借鉴 QJ 的可部署性，但保留 MS-Image 的隔离性。

1. 定义 `online`、`evaluation` 命名数据库；`hd` 仅作为可选外部集成 alias，不是 MS-Image 自有数据平面；
2. 将 Engine/SessionFactory/healthcheck/dispose 收敛到 Registry，并让 `hd` 按需、懒初始化；
3. online/evaluation URL 或数据库名相同必须失败关闭；HD owner、最小权限、读写范围、失败是否影响 readiness 未确认前，User/Admin/Imaging/Evaluation 进程不得默认连接或 healthcheck HD；
4. User API、Admin API、Imaging Relay、Imaging Worker、Evaluation Relay、Evaluation Worker 分别拥有应用/进程入口；
5. 用 Compose 薄编排替代 `run_servers.py` 进程监督；
6. 禁止启动时 `create_all`、自动 seed 或隐式迁移。

通过标准：

```text
每个进程明确只取得其所需 Session；
Evaluation Worker 无法获得 online 写 Session；
入口停止/重启不会误启动平行遗留 Worker。
```

### Phase E：QJ 接入 Adapter（需独立接口评审）

目标：把 QJ 作为外部商业面，而不污染 MS-Image 域模型。

1. 冻结 internal identity 和 idempotency contract；
2. 选择轮询或 internal event 的 Task 状态同步方式；
3. 定义上传 owner 和 ObjectRef 传递方式；
4. 定义 QJ CapabilityTask 与 MS-Image Task 的一对一映射；
5. 定义可计费终态、取消、超时、技术失败和重复事件语义；
6. 对 QJ Adapter 使用 fake 双系统契约验证；
7. 只有 QJ 适配器通过后，才设计真实 Kong 路由和客户 SDK 合同。

### Phase F：真实运行与医学门禁（后续单独授权）

顺序不变：

```text
迁移审批
-> MySQL/OSS/RabbitMQ 真实演练
-> Provider qualification
-> Dataset/Truth/Experiment/HumanApproval
-> Development/Failure Bank paired A/B
-> isolated Holdout
-> validation-only/shadow/gray
-> production
```

本调整文档不降低任何真实运行或医学发布门槛。

---

## 9. 停止条件、风险与 UNKNOWN

### 9.1 立即停止条件

| 触发 | 动作 |
|---|---|
| 调整要求新增第二套 Task/Stage/Outbox/Report 或新的 Repository/DatabaseService | 停止，回到公共十表和 `DalBase` 方案 |
| 为 QJ 接入要求在 MS-Image 保存 Project/API Key/Wallet/tenant 表 | 停止，回到外部 identity adapter |
| XRay 专项需要新增独立事实表才能运行 | 停止，先检查是否可由 Profile/Config/Stage output 表达 |
| 提议在 DB 事务内请求 OSS/Broker/Provider | 停止，恢复三段短事务设计 |
| 因收敛而删除 `xray_accuracy` 但未证明无消费者/无审计需求 | 停止，保持 compatibility 域 |
| 因工程 fake 通过而降低 Provider/医学门禁 | 停止，保持 `NO-GO` |

### 9.2 当前 UNKNOWN

- 旧 `xray_accuracy` API、表和 Worker 是否仍有外部消费者；
- 旧 XRay 事实到公共十表的最终迁移映射与审计保留期限；
- QJ 是否选择轮询还是 internal event Adapter；
- QJ 的 CapabilityTask 成功终态与 MS-Image Report/medical status 的计费合同；
- QJ 映射产生的全局 requester/subject opaque ID 的稳定性；
- 真实 Evaluation DB 账号、TLS、备份、RPO/RTO；
- Worker concurrency、prefetch、DLQ retention、rolling upgrade 细节；
- Provider model、receipt、区域与数据保留资格；
- trusted Gold、Failure Bank、Holdout、人工审批 owner。

这些 UNKNOWN 均不得由代码目录、文档命名或 QJ 草案推断填补。

---

## 10. 实施前检查清单

任何代码调整前必须确认：

- [ ] 当前变更只涉及既有 `app/service/`、`app/crud/`、`app/models/`、`app/schemas/` 和 Worker 边界，不新增平行架构；
- [ ] 所有新数据访问仍经 `DalBase` 实体 DAL；
- [ ] API 不使用 `/{id}`，资源 ID 仅在 query/body；
- [ ] 新 Model 不使用 FK、Enum、联合主键或 `tenant_id`；
- [ ] 所有状态/类型字段使用 string/json/timestamp 并带中文 comment；
- [ ] 事务内不执行 OSS/Broker/Provider I/O；
- [ ] XRay 新能力只扩展 Config/Profile/Stage/Schema，不扩展 xray_accuracy persistence；
- [ ] Evaluation 不写在线 Task/Report/AI Config；
- [ ] 不生成迁移脚本、测试脚本，除非用户单独授权；
- [ ] 未连接真实基础设施；
- [ ] handoff、部署合同和源码状态同步更新。

---

## 11. 主要源码证据索引

### MS-Image

| 主题 | 证据 |
|---|---|
| 8 个在线 Service、Stage 与公共/专项边界 | `docs/refactor/04-service-and-stage-design.md`；`docs/refactor/05-development-guide.md:125-132`；设计母文 `:425-857`；涉及 AI/Stage 时另见 `docs/refactor/17-prompt-runtime-contract-and-minimal-provider-plan.md` |
| 5 个 Stage registry/profile | `app/core/pipeline.py:61-112` |
| 公共执行状态机当前集中实现 | `app/service/imaging_execution_service.py:25-270` |
| Task + first Stage + Outbox 原子创建 | `app/service/task_service.py:70-261` |
| 公共 opaque ID base | `app/models/imaging_base.py:15-38` |
| 公共/legacy Model 同时注册 | `app/models/__init__.py:1-29` |
| XRay legacy Base | `app/models/xray_accuracy/base.py:1-33` |
| Image API 事务与 OSS 编排泄漏 | `app/api/api_v1/endpoints/images.py:45-84`、`:92-127` 及后续 multipart endpoints |
| ImageService 职责密度 | `app/service/image_service.py` |
| Worker 直接 DAL 调用 | `workers/imaging_worker/reconcile.py`；`workers/xray_accuracy_worker/technical_worker.py`；`workers/xray_accuracy_worker/outbox_relay.py` |
| Evaluation 双数据库与 Exporter | `app/core/async_db.py:12-64`；`app/service/evaluation_export_service.py`；`workers/evaluation_worker/` |
| Compose 只注册旧 XRay broker Worker | `docker-compose.yml:63-110` |
| core 对 XRay 专项反向依赖 | `app/core/imaging/ingest.py`；`app/core/imaging/oss_resolver.py`；`app/core/readiness.py:20-63` |

### QJ 参考仓库

| 主题 | 证据 |
|---|---|
| 实施型后端 Monorepo 与分层 | `qj-open-plataform/docs/backend-monorepo-architecture.md:173-201` |
| DatabaseRegistry | `qj-open-plataform/backend/core/database/registry.py:19-105` |
| 服务应用工厂 | `qj-open-plataform/backend/core/server.py:26-70` |
| 服务生命周期和 Registry 初始化 | `qj-open-plataform/backend/core/event.py:14-57` |
| Compose 多 API/Worker 编排 | `qj-open-plataform/deploy/compose/services.yaml:35-214` |
| Kong 入口、静态/动态管理边界 | `qj-open-plataform/kong-config/README.md:1-168` |
| API Key 与 Kong identity 二次校验 | `qj-open-plataform/backend/services/platform/service/api_key_service.py:33-77` |
| 动态 Provider proxy 的范围和限制 | `qj-open-plataform/backend/services/platform/service/capability_provider_service.py:82-424` |
| Nacos 当前未完成 Runtime | `qj-open-plataform/backend/services/platform/service/capability_provider_service.py:200-205` |
| QJ Billing 的异步补偿模型 | `qj-open-plataform/backend/services/platform/integrations/billing_queue.py:13-65`；`qj-open-plataform/backend/workers/billing/usage_billing_task.py:25-97` |
| QJ Task 仅创建 queued 记录 | `qj-open-plataform/backend/services/platform/service/capability_task_service.py:22-78` |

---

## 12. 最终口径

MS-Image 借鉴 QJ 的目的，不是增加“平台化”复杂度，而是补齐当前代码到可部署、可隔离、可接入的工程边界：

```text
借鉴：入口分离、数据库 Registry、Compose/管理、Kong 外部边界、身份映射、商业事实外置。

保留：MS-Image 的对象真相、Task/Stage/Outbox/CAS、不可变 Report、Evaluation 隔离与医学门禁。

收敛：公共在线十表/8 Service 为唯一新主链；XRay 退回 Stage/Profile/Schema/兼容适配；Evaluation 保持独立平面。
```

在真实运行、Provider 和医学评测门禁全部通过前，所有调整只能改善工程结构和因果可解释性，不能宣称医学准确率提升或生产可用。
