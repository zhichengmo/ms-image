# MS-Image 当前开发合同与会话执行规范

> 文档版本：v1.4
>
> 更新日期：2026-09-02
>
> 适用仓库：`/Users/mozhicheng/workspace/code/cy-code/ms-image`
>
> 当前分支：`codex/xray-anatomy-localization-v1`
>
> 当前 HEAD：`ef15deafaa777db1d402fce4e510cf8bdaff462d`

## 0. 文档用途与权威边界

这是一份**当前有效的开发合同**，用于约束后续每个开发会话的目标、范围、架构、验证和停止条件。
它不是聊天记录，也不是把所有未来设想都列成当前任务的总路线图。

本合同只回答四个问题：

1. 当前产品要完成什么；
2. 当前代码允许沿哪条链路扩展；
3. 哪些能力明确不属于当前切片；
4. 每次改动如何证明没有偏离目标。

### 0.1 权威顺序

发生冲突时按以下顺序处理：

```text
用户本轮明确授权
    > AGENTS.md 项目硬规则
    > 当前源码与已取得的真实运行事实
    > .agent-handoff 当前状态文件
    > 本开发合同中的目标与约束
    > 历史路线图、旧 Prompt 和旧会话提示
```

这里要区分两类事实：

- “代码现在实际做什么”以当前源码和真实验证为准；
- “本轮允许做什么”以用户授权、`AGENTS.md` 和本合同为准。

如果源码、handoff（交接）和本合同不一致，不得自行选择一个继续执行，必须先报告冲突。

### 0.2 配套文件职责

| 文件 | 职责 | 是否描述当前下一步 |
|---|---|---:|
| 本文档 | 稳定的当前开发合同、链路边界和验证门禁 | 只保留当前阶段原则 |
| `.agent-handoff/snapshot.md` | 当前状态、当前阻断、下一动作 | 是 |
| `.agent-handoff/risks.md` | 风险、阻断、UNKNOWN | 是 |
| `.agent-handoff/backlog.md` | 可执行待办和延后事项 | 是 |
| `.agent-handoff/validation.md` | 已运行、失败、未运行的验证 | 是 |
| `.agent-handoff/decisions.md` | 有理由和证据的长期决策 | 否 |
| `docs/ms-image-xray-complete-development-architecture-roadmap.md` | 历史完整路线图和候选设计背景 | 否 |
| `AGENT_SESSION_PROMPTS.md` | 新会话可复制启动提示 | 只引用本文和当前 snapshot |

历史路线图不能覆盖本文的当前目标；本文也不能把未实现的目标设计写成已实现事实。

## 1. 当前项目目标

### 1.1 产品目标

当前 X-Ray 产品有两条用户业务链路：

```text
诊断主链：2–5 张原始 X-Ray → 一次或条件性多次诊断调用 → final Report

定位展示链：同一批 2–5 张原始 X-Ray → 一次多图 Localization 调用
          → 逐图器官 normalized bbox → API/UI 展示
```

这两条链路共享冻结的 Study Revision 和原始影像，但拥有不同的 Task 类型、完成语义和输出边界。

### 1.2 当前研发优先级

当前最近完成的 active development objective（活动开发目标）是：

```text
Cat 独立 SystemAnalysis 工程资格化。
结果：单次真实 Runtime PASS；1 Call、1 Attempt、Provider 200、accepted、Task completed、Report 0。
下一候选：条件性 TargetedReview（需要新的 targeted candidate 用例与独立授权）。
```

当前工程状态：

```text
STUDY_SCREENING_V2_ENGINEERING_RUNTIME_PASS
SYSTEM_ANALYSIS_CAT_ENGINEERING_RUNTIME_PASS
PRIMARY_CASE_ADJUDICATION_CAT_ENGINEERING_RUNTIME_PASS  # 独立 experiment Task，跳过 Screening 且不含 SystemAnalysis
FAMILY_ROUTING_RUNTIME_PASS
DECISION_FINALIZATION_RUNTIME_PASS
REPORT_SERVICE_PERSISTENCE_PASS
TARGETED_REVIEW_RUNTIME_UNKNOWN
REPORT_GENERATION_AI_RUNTIME_UNKNOWN
SAME_TASK_FULL_CHAIN_RUNTIME_UNKNOWN
MEDICAL_ACCURACY_UNKNOWN
MEDICAL_RELEASE_NO_GO
```

用户要求按顺序逐个跑通：

```text
StudyScreening
→ SystemAnalysis
→ PrimaryCaseAdjudication
→ TargetedReview
→ ReportGeneration
```

StudyScreening v2 Cat 和独立 SystemAnalysis Cat 均已按单次门禁完成，不得追加第二 Task/Attempt 或自动重跑。
Primary、FamilyRouting、DecisionFinalization 与 ReportService 另有一次跳过 Screening 的独立 experiment Runtime PASS，但不能与前两项拼成同一 Task 的完整链 PASS。
当前不运行 Dog、TargetedReview、ReportGeneration 或 diagnose Root；下一阶段必须重新授权。

当前不允许把以下内容同时设为 active objective：

- diagnose Root Profile 或 Primary 对 Screening 的消费；
- TargetedReview、ReportGeneration 或同 Task 完整诊断链；
- Evaluation R4A–R4D；
- Pixel Mask Segmentation；
- Prompt 医学准确率优化；
- Retry/Fallback/Race；
- Docker 或主库注释漂移；
- 剩余 Localization 资格化矩阵。

## 2. 当前状态基线

### 2.1 状态摘要

| 能力/链路 | 当前状态 | 证据口径 |
|---|---|---|
| `xray_quality_control / BatchImageQualityReview` | `RUNTIME_QUALIFIED`（工程） | Cat/Dog 工程链和写接口回归已有记录；医学准确率仍 UNKNOWN |
| StudyScreening v1 | `RUNTIME_FAILED_CLOSED / FROZEN` | Cat Provider HTTP 200 后因 `study_screening_source_projection_mismatch` 失败；1 Call/1 Attempt/Report 0；不得覆盖或重跑 v1 |
| StudyScreening v2 Provider/Canonical 合同 | `CODE_IMPLEMENTED` | Provider 只输出 `source_ref_id + image_id`；Stage 从 `AI_IMAGE_RECEIPT_V2` 补齐确定性 lineage |
| StudyScreening v2 Task/Profile | `CODE_IMPLEMENTED` | `task_type=xray_study_screening`；`xray_study_screening_v2` 固定两 Stage，不进入 Primary 或 Report |
| StudyScreening v2 静态验证 | `STATIC_VALIDATION_PASSED` | focused `337 passed, 45 warnings`；Ruff、compileall、diff-check 通过 |
| StudyScreening v2 Nacos/DB Prompt/Config/Runtime | `NOT_YET_QUALIFIED` | Cat `2.0.0` 尚待发布、导入、冻结 Config 和一次真实 Runtime；Dog 不在本轮范围 |
| X-Ray 诊断主链 | 已有猫狗 2–5 图真实工程资格记录 | 历史 `validation.md` 记录；本轮不修改 diagnose Root/Primary/Report |
| Anatomy Localization v1 | `CODE_IMPLEMENTED / STATIC_VALIDATION_PASSED / RUNTIME_FAILED` | 当前不是 active objective；首格 projection mismatch 后保持停止 |
| Pixel Mask Segmentation | `NOT_IMPLEMENTED` | 当前只允许 bbox 定位，不创建 mask 任务链 |
| 医学准确率/发布 | `UNKNOWN / NO-GO` | 工程通过不等于医学验证 |
| Evaluation R4A | 独立基础设施有历史烟测，当前不属于 active scope | Fake scorer 不能替代医学 Scorer |

### 2.2 最近一次真实 Localization 事实

最近一次 `cat-02` 只运行了一次，事实如下：

```text
Task：1 个
StageCheckpoint：2 个
Provider-required Stage：1 个
Logical AICall：1 个
Primary lane：1 个
Physical Attempt：1 个
请求图片：2 张
requested/sent/receipt：2/2/2
Provider HTTP：200
通用 JSON Schema：通过
Localization validator：anatomy_localization_image_1_projection_mismatch
Task/Call/Attempt/Stage：failed
Report：没有生成
剩余七格：未运行
```

该事实证明失败关闭和审计边界生效，不证明 Provider、Prompt、bbox 定位或医学准确性。

### 2.3 当前硬性 UNKNOWN

- Provider 返回的具体 `projection` 值是什么：`UNKNOWN`；当前没有保存 Provider body 或 rejected parsed result。
- 该 mismatch 的根因属于 Prompt、safe context、Provider 回显还是其他映射：`UNKNOWN`。
- 3–5 图真实 Provider 是否稳定返回完整逐图结果：`UNKNOWN`。
- 猫狗八格是否全部通过：`UNKNOWN`，因为首格失败后按合同停止。
- bbox 是否医学正确：`UNKNOWN`。
- Pixel mask 能力：`NOT_IMPLEMENTED`，不能用 bbox 结果替代。

## 3. 功能完成度总账（每次执行前必须逐项核对）

本节是“已完成能力索引”，用于防止新会话重复实现、误删或把历史完成项重新列为下一步。
“已完成”必须按证据层级拆开：代码存在不等于真实运行资格，工程资格也不等于医学验证。

### 3.1 影像与可靠执行底座

| 能力 | 状态 | 每轮核对内容 | 主要证据 |
|---|---|---|---|
| Session/Study/Series/Image 领域模型、Schema、DAL、Service、API | `IMPLEMENTED` | 入口、分层、现有 DAL 是否仍被复用 | `apps/backend/models/`、`schemas/`、`crud/`、`services/runtime/service/` |
| OSS 上传准备、确认、HEAD/哈希/格式校验和 ready 状态 | `IMPLEMENTED` | 不新增第二套对象存储网关；signed URL 不落库 | `apps/backend/services/runtime/service/image_upload_workflow.py`、`apps/backend/core/imaging/` |
| Study Revision 与 image manifest 冻结 | `IMPLEMENTED` | 当前 Task 是否绑定冻结 revision/manifest | `apps/backend/core/imaging/manifest.py`、`task_service.py` |
| Task 创建、幂等、状态和取消基础合同 | `IMPLEMENTED` | 不在 endpoint 直接拼 SQL；状态转换仍由 Service 拥有 | `apps/backend/services/runtime/service/task_service.py` |
| StageCheckpoint、Outbox、Relay、RabbitMQ、Worker 执行底座 | `IMPLEMENTED` | 一个运行拓扑只启动一个 owner；事务内无外部 I/O | `apps/backend/workers/`、`apps/backend/services/runtime/` |
| Stage Registry 与版本化 Handler | `IMPLEMENTED` | 新能力只能注册到现有 registry，不另建 Pipeline | `apps/backend/services/runtime/stages/registry.py` |

### 3.2 AI Control 与 Runtime 调用

| 能力 | 状态 | 每轮核对内容 | 主要证据 |
|---|---|---|---|
| Nacos Prompt exact Data ID/variant 映射 | `IMPLEMENTED` | 猫狗不跨物种、不回退 default；运行时不读 latest | `apps/backend/services/ai_control/service/prompt_source.py` |
| Prompt import/normalize/receipt | `IMPLEMENTED` | 不在通用导入服务增加业务专属分支；外部发布显式传 identity | `prompt_source.py`、`prompt_import_service.py` |
| AI Config compile/validate/activate/frozen verify | `IMPLEMENTED` | Config、Schema、Prompt、Pipeline、ModelPool、Connection SHA 不漂移 | `apps/backend/services/ai_control/service/config_compiler.py` |
| ModelPool/Connection/Capability 合同 | `IMPLEMENTED` | `supports_images`、`supports_json_schema`、图片上限和 timeout 前置核对 | AI Control schemas/services、Gateway contracts |
| AIRequestService Logical Call/Physical Attempt | `IMPLEMENTED` | Localization 保持 1 Call/1 Attempt；不复制请求服务 | `apps/backend/services/runtime/service/ai_request_service.py` |
| 多图 image 组装、receipt、技术 Schema/lineage validator | `IMPLEMENTED` | 一次 Call 携带全部 N 张原图；receipt 不含 signed URL | `ai_request_service.py`、`apps/backend/core/ai/` |
| Gateway/Provider 请求与脱敏失败审计 | `IMPLEMENTED` | HTTP rejection、unknown、definite response 不混淆；不保存 Provider 正文 | `apps/backend/core/ai/gateway/`、相关 contract tests |

### 3.3 诊断主链与 StudyScreening 资格链

| 能力 | 状态 | 每轮核对内容 | 主要证据 |
|---|---|---|---|
| `diagnose` Task、cat/dog species 冻结 | `IMPLEMENTED` | species 来自调用方并进入冻结 Snapshot，不运行时查询 latest | `apps/backend/schemas/task.py`、`task_service.py` |
| StudyPreparation → JointPrimaryReader → DecisionFinalization | `RUNTIME_QUALIFIED`（独立实验链） | 保留“跳过 Screening 且不含 SystemAnalysis”的证据边界 | `apps/backend/core/pipeline.py`、`.agent-handoff/validation.md` |
| FamilyRouting/TargetedReview 条件分支 | `PARTIAL_RUNTIME_QUALIFIED` | FamilyRouting 已 PASS；TargetedReview 未触发，不能合并记为通过 | `family_routing.py`、`targeted_review.py`、`.agent-handoff/validation.md` |
| Task → final Report → current/history | `RUNTIME_QUALIFIED`（有历史证据） | StudyScreening 独立资格 Task 不得生成 Report | `.agent-handoff/validation.md` |
| `xray_quality_control` / BatchImageQualityReview | `RUNTIME_QUALIFIED`（工程） | 作为 StudyScreening 的显式冻结上游，不查询 latest、不允许客户端提交 Quality JSON | `image_quality.py`、`xray_quality.py`、`.agent-handoff/validation.md` |
| StudyScreening v1 Prompt/Schema/validator/Profile | `FROZEN / REPLAY_COMPATIBLE` | 保留历史 `1.0.0` 与 strict projection equality，不覆盖、不放宽 | `study_screening_contract.py`、`study_screening.v1.schema.json` |
| StudyScreening v2 Provider anchor contract | `RUNTIME_QUALIFIED`（工程） | Provider source ref 只能含 `source_ref_id + image_id`，必须唯一并覆盖全部 receipt 图像 | `study_screening_contract.py`、`study_screening.v2.schema.json` |
| StudyScreening v2 Stage canonicalization | `RUNTIME_QUALIFIED`（工程） | AICall raw 保持 provider.v2；Stage output 从 receipt 补齐 lineage 并标记 canonical.v2 | `study_screening.py`、`ai_request_service.py` |
| `xray_study_screening` Task 与 `xray_study_screening_v2` Profile | `RUNTIME_QUALIFIED`（工程） | 复用公共 Task API、Quality strict loader、现有 Worker/Gateway；只包含 preparation + screening | `schemas/task.py`、`task_service.py`、`pipeline.py` |
| StudyScreening v2 Cat 控制面和 Runtime | `RUNTIME_QUALIFIED`（工程） | Cat `2.0.0` 已完成单 Logical Call、单 Attempt、Provider 200、accepted、Task completed、Report 0 | `.agent-handoff/validation.md`、当前 snapshot |
| SystemAnalysis Cat 控制面和独立 Runtime | `RUNTIME_QUALIFIED`（工程） | Cat `1.0.0` 已完成单 Logical Call、单 Attempt、Provider 200、accepted、Task completed、2/2/2、Report 0 | `system_analysis.py`、`.agent-handoff/validation.md`、当前 snapshot |

### 3.4 Anatomy Localization v1

| 能力 | 状态 | 每轮核对内容 | 主要证据 |
|---|---|---|---|
| `anatomy_localization` Task Type | `IMPLEMENTED` | 必须提供 cat/dog；不接 clinical context | `apps/backend/schemas/task.py` |
| `xray_anatomy_localization_v1` Profile | `IMPLEMENTED` | 固定两 Stage：study preparation + localization | `apps/backend/core/pipeline.py` |
| Localization Stage Handler | `IMPLEMENTED` | 只生成 StageExecutionPlan/消费 accepted Call，不直连 Provider | `apps/backend/services/runtime/stages/xray/anatomy_localization.py` |
| 猫狗 exact Nacos Prompt 与不可变 Config | `IMPLEMENTED` | 不覆盖 `1.0.0`；新版本必须另行授权 | 当前 snapshot 的 Frozen External Identities |
| 6 个系统、38 个标签、normalized bbox Schema/validator | `STATIC_VALIDATION_PASSED` | 只做结构和技术血缘校验，不做 Python 医学判断 | `apps/backend/core/ai/anatomy_localization_contract.py`、`schemas/anatomy_localization.py` |
| Localization 查询 API | `IMPLEMENTED` | 只返回安全 DTO；不泄露 Prompt、Config、receipt 正文 | `endpoints/anatomy_localizations.py`、`task_service.py` |
| 现有本地 E2E Harness Localization 分支 | `IMPLEMENTED` | 不创建第二套 Harness；默认 diagnose 行为兼容 | `scripts/dev/run_e2e_local.py` |
| Localization 静态/合同验证 | `STATIC_VALIDATION_PASSED` | 只代表代码和合同，不代表 Provider 成功 | `.agent-handoff/validation.md` |
| Localization 真实 2–5 图资格 | `FAILED / NOT_CONFIRMED` | 首格失败即停；不得直接续跑剩余七格 | `.agent-handoff/snapshot.md`、`risks.md` |

### 3.5 Evaluation 与其他支撑能力

| 能力 | 状态 | 每轮核对内容 | 主要证据 |
|---|---|---|---|
| 独立 Evaluation metadata/DB/Alembic/readiness | `ENGINEERING_SMOKE_PASSED` | 不把 Evaluation 迁移或 Docker 问题混入 Localization | `.agent-handoff/validation.md` R4A 记录 |
| Evaluation Job/Outbox/Relay/Worker/Fake scorer/Artifact | `ENGINEERING_SMOKE_PASSED` | Fake scorer 不能冒充医学 Scorer 或 Runtime Runner | `apps/backend/services/evaluation_control/` |
| Evaluation 医学 Gold/Scorer/Failure Bank/Holdout | `NOT_IMPLEMENTED / DEFERRED` | 未经切换授权不得进入 | `.agent-handoff/backlog.md`、`risks.md` |

### 3.6 应用与接口边界

当前工作树有四个独立应用边界，不能把它们合并成一个裸 `/api/v1` 服务：

| 应用 | 外部 root path | 当前版本化路由数 | 已完成职责 |
|---|---|---:|---|
| Runtime | `/ms-image` | 30 | Session、Study、Series、Image、Task、Report、Anatomy Localization、health/readiness |
| Runtime Admin | `/ms-image/admin` | 6 | 管理状态、运行状态、Report publish/void 入口 |
| AI Control | `/ms-image/ai-control` | 31 | Connection、ModelPool、Prompt、Prompt import、Config、Audit、health/readiness |
| Evaluation Control | `/ms-image/evaluation-control` | 11 | health/readiness、Export、Job、Run、Artifact |

当前工作树静态路由总数为：

```text
78 个版本化路由 + 4 个应用根探针 = 82 个 HTTP 路由
```

该数字包含本次未提交 Localization 查询路由。旧路线图中的 79/81 路由口径属于更早代码时点，
不能覆盖当前工作树事实。路由存在只证明接口已注册，不自动证明真实运行资格。

### 3.7 每次执行前的完成度核对清单

任何新会话、代码修改或真实运行前，必须逐项检查并在第一条回复中报告：

```text
[ ] 已读取本文档和 .agent-handoff 当前状态文件
[ ] 已确认本轮目标不是已完成能力的重复实现
[ ] 已确认目标属于哪一条业务链和哪一个 Stage/Profile
[ ] 已确认现有入口、Service、DAL、Worker、Gateway 是否已经拥有该职责
[ ] 已确认不会创建第二套 Service/Worker/Gateway/Repository/Outbox
[ ] 已确认当前能力的状态是 IMPLEMENTED、STATIC、RUNTIME 还是 MEDICAL
[ ] 已确认本轮 write set（写入文件集合）
[ ] 已确认 Provider/Nacos/数据库/Docker 是否获得单独授权
[ ] 已确认完成条件、停止条件和回滚单位
```

如果某项已存在，默认动作是复用、验证或局部修复，而不是重新创建。
如果文档和源码状态不一致，默认动作是停止并报告，而不是自行覆盖文档或代码。

## 4. 两条业务链路

### 4.1 诊断主链（Diagnose）

入口为 `task_type=diagnose`，诊断链拥有医学结论和 Report 的写入权。

```text
Session/Study/Series/Image ready
    → 创建 diagnose Task
    → study_preparation
    → joint_primary_reader（一次多图 Primary 调用）
    → 可选 family_routing / targeted_review
    → decision_finalization
    → Task completed
    → final Report / current / history
```

约束：

- 诊断输入是冻结 Study Revision 的 2–5 张原始 X-Ray；
- `species=cat|dog` 是创建 Task 时的冻结事实；
- Primary 每个医学 Stage 一个 Logical Call；
- Targeted 只在合法 candidate 和对应 experiment profile 下出现；
- Python 只能做路由、Schema/技术校验、持久化和审计，不能改写医学结论；
- 诊断链的 Report 语义不能被 Localization 结果覆盖。

诊断主链内部的 Primary-only、Targeted 和 replay 是同一业务域的分支或兼容模式，不额外创建第二套 Runtime。

### 4.2 Anatomy Localization v1（定位展示链）

入口为 `task_type=anatomy_localization`，当前语义是**器官 bbox 定位展示**，不是像素级分割。

```text
Session/Study/Series/Image ready
    → 创建 anatomy_localization Task
    → study_preparation:v1
    → anatomy_localization:v1
       → 一次多图 AI Logical Call
       → 一次 primary lane
       → 一次 Physical Attempt
    → 逐图 normalized bbox
    → GET /api/v1/anatomy-localizations?task_id=...
    → UI 绘制框或 overlay
```

固定合同：

| 项目 | 合同 |
|---|---|
| 图片数量 | `N ∈ {2,3,4,5}`，第 6 张必须 fail-closed |
| Task | 1 个 `anatomy_localization` Task |
| Stage | 恰好 `study_preparation:v1` + `anatomy_localization:v1` |
| Provider Stage | 恰好 1 个 |
| Logical Call | 恰好 1 个 |
| primary lane | 恰好 1 个 |
| Physical Attempt | 恰好 1 个，`max_attempts=1` |
| Provider 请求 | 一次携带全部 N 张原始图 |
| 输出 | 逐图器官 normalized bbox，受本地 Schema/技术 validator 约束 |
| Report | 永远不生成，不写 `current_report_id` |
| medical status | 保持 `not_produced` |
| 诊断关系 | 不进入诊断 Prompt，不修改诊断结果，不阻塞诊断 Report |

Localization 查询只负责读取已经完成的安全结果。它不是第二套 AI Control 资格化流程，也不应在公共 GET 中重新加载完整 AICall/Attempt/Config/receipt 链做运行资格化。

### 4.3 UI 展示不是第三条 AI 链

UI 只是 Localization 结果的消费者：

```text
Localization result → bbox 坐标换算 → UI 框选/颜色展示
```

UI 不发起第二次诊断调用，不生成医学结论，也不能根据 bbox 面积、形状或 confidence 推断疾病。

Pixel mask、crop、overlay raster 和独立分割 Job 只能作为未来单独立项，不能从当前 bbox 合同中推导出来。

## 5. 共享执行架构与唯一 Owner

### 5.1 共享运行链

两条业务链均复用当前已经跑通的异步底座：

```text
API
 → Service
 → Task / Stage / Outbox
 → Relay
 → RabbitMQ
 → imaging Worker
 → Stage Handler
 → AIRequestService（需要 Provider 的 Stage）
 → Gateway / Provider
 → AICall / Attempt / receipt
 → Stage / Task finalization
```

Localization Stage Handler 只负责生成 `StageExecutionPlan` 和消费 accepted AICall，不直接访问 Gateway、HTTP、SDK、OSS 或 Provider。

### 5.2 Owner 约束

| 事实或职责 | 唯一 Owner |
|---|---|
| Task/Stage 编排 | 现有 `TaskService` / `ImagingExecutionService` |
| 数据访问 | 现有实体 DAL + `DalBase` |
| Prompt/Config 冻结与控制面 | 现有 AI Control Service |
| Logical Call/Physical Attempt/receipt | `AIRequestService` |
| Provider 调用 | 现有 Gateway + `AIRequestService` |
| Localization 医学结果结构 | Provider 输出 + 本地 Schema/技术 validator |
| Report 医学结果 | 诊断链 `DecisionFinalization` / `ReportService` |
| UI 展示 | 前端消费者，不拥有医学事实 |

禁止创建第二个 `LocalizationAIService`、第二个 Gateway、第二个 Worker、第二套 Outbox、Repository 或平行 CRUD 层。

### 5.3 分层合同

所有业务写入继续遵循：

```text
API → Service → DalBase CRUD → Model/DB
```

- API 只做请求校验、依赖注入、鉴权、Service 调用和响应包装；
- Service 编排业务状态和 DAL；
- DAL 继承现有 `DalBase`，不在 Service/API/Worker 中直接拼 SQL；
- Schema 不访问数据库；
- 不新增表、字段、迁移，除非用户单独授权并且有独立事实 owner 证据；
- 新接口资源 ID 只能放 query 或 request body，不使用 `/{id}`；
- 不使用 Foreign Key、数据库 Enum、联合主键或租户字段作为新事实合同。

## 6. Prompt、Nacos 和 Config 合同

### 6.1 当前 StudyScreening Prompt 身份

v1 历史身份保持不可变：

```text
Cat：ms-image.x-ray.study-screening.cat.zh-CN@1.0.0
Dog：ms-image.x-ray.study-screening.dog.zh-CN@1.0.0
```

当前 v2 资格化使用新 Cat release，禁止覆盖 v1：

```text
Data ID：ms-image.x-ray.study-screening.cat.zh-CN
variant：cat
locale：zh-CN
release/version：2.0.0
prompt_key：xray_cat_study_screening
local normalized SHA256：ab6169b1f9b9401e7e79b83ebb75eead719c8af6471f62cf031dfc413c5c0114
schema asset file SHA256：b1979ba5cac37c8a6c34efafd820aec4cf40db62b4e2a3452417532d068a56ab
Config frozen canonical JSON SHA256：f2d0a53cb69c2b0dfe2e0ad318a6018a867c5c9332a9b88a8a3bf8464325071e
```

Dog v2 本地资产已存在，但本轮不得发布或运行。

目标 Cat Config：

```text
config_key=xray_study_screening_cat
profile_key=xray_study_screening_v2
task_type=xray_study_screening
activation_scope=global
scope_key=global
prompt_key=xray_cat_study_screening
prompt_version=2.0.0
```

### 6.2 变量、输入与双边界

Required variables 精确为：

```text
SAFE_STUDY_CONTEXT_JSON
QUALITY_RESULTS_JSON
OUTPUT_SCHEMA_JSON
```

Message context keys 按以下顺序冻结：

```text
SAFE_STUDY_CONTEXT_JSON
QUALITY_RESULTS_JSON
```

固定边界：

- `QUALITY_RESULTS_JSON` 只能来自显式 `quality_review_task_id` 对应的 accepted Quality Task；
- Quality Task 必须与新 Task 的 requester、Study、Revision、species、manifest 全部一致；
- Provider v2 的 `source_refs[]` 只允许 `source_ref_id + image_id`，必须完整覆盖全部发送图像；
- `sequence_no/series_id/series_manifest_sha256/projection/projection_provenance` 由 Stage 从冻结 Receipt 补齐；
- `AICall.parsed_result_json` 保存 Provider raw，Stage `study_screening_result` 保存 canonical；
- signed URL 不写入 Task Snapshot、Prompt、日志或数据库；
- canonicalizer 只能补确定性 lineage，不能改写医学内容。

### 6.3 Profile 与调用次数

当前独立资格 Profile 固定：

```text
study_preparation:v1
study_screening:v2
```

它必须恰好产生：

```text
1 个 Provider-required Stage
1 个 Logical Call
1 个 Physical Attempt
最多 5 张图片
0 个 Report
```

当前不创建或运行新的 diagnose Root Profile，也不验证 Primary 对 Screening 结果的消费。

## 7. 当前实现映射

以下是当前代码中已经存在、可以复用的入口；它们不是新增目标：

| 能力 | 代码入口 |
|---|---|
| Task 类型 | `apps/backend/schemas/task.py` |
| Localization Profile/Stage | `apps/backend/core/pipeline.py` |
| Stage Handler 注册 | `apps/backend/services/runtime/stages/registry.py` |
| Localization Handler | `apps/backend/services/runtime/stages/xray/anatomy_localization.py` |
| Prompt Source/Nacos 坐标 | `apps/backend/services/ai_control/service/prompt_source.py` |
| Config 预算与冻结校验 | `apps/backend/services/ai_control/service/config_compiler.py` |
| AI 请求、图片组装、Call/Attempt、receipt | `apps/backend/services/runtime/service/ai_request_service.py` |
| Localization 查询 | `apps/backend/services/runtime/service/task_service.py` |
| Localization 查询路由 | `apps/backend/services/runtime/api/api_v1/endpoints/anatomy_localizations.py` |
| 既有本地 E2E Harness | `scripts/dev/run_e2e_local.py` |

实现新能力时优先扩展这些入口，不新增平行实现。

### 7.1 当前已知的范围收敛项

以下代码已经存在且测试曾通过，但仍需要在后续**代码收口会话**中单独审核；它们不属于当前
projection 根因只读审计，也不能在本会话顺手修改：

| 项目 | 当前源码事实 | 目标收敛方向 | 当前动作 |
|---|---|---|---|
| Localization 查询 | `TaskService.get_anatomy_localization()` 继续加载 AICall、Attempt、AIConfig、receipt 并重新做完整资格校验 | 公共查询优先收敛为 Task + StageCheckpoint + output SHA + 本地 Response validator；完整 Call/Attempt/receipt 资格放 E2E Harness | `REVIEW_REQUIRED / NOT_THIS_SLICE` |
| PromptImportService | 通用导入服务包含 Localization 专属 exact namespace/release 分支 | Prompt Source 已提供 exact-only 映射；业务专属限制是否应撤回需独立审核，不能无证据继续扩大 | `REVIEW_REQUIRED / NOT_THIS_SLICE` |
| E2E teardown | 既有 Harness 偶发 aiomysql event-loop teardown warning | 不影响当前业务证据，作为独立小修处理 | `DEFERRED` |

这些项目被列出是为了防止新会话误认为“已经最终裁决，无需再看”，也防止它们抢占当前唯一目标。
是否修改必须由用户在 projection 审计之后重新选择切片。

## 8. 失败语义与停止条件

### 8.1 技术失败

以下情况必须 fail-closed：

- 图片数量不在 2–5；
- Study Revision、Image manifest 或 projection 血缘不一致；
- Provider 返回缺失、重复或错误的逐图引用；
- JSON Schema 或 Localization 技术 validator 失败；
- 发送事实不足以证明 N 张图已覆盖；
- Config/Prompt/Schema/ModelPool/Connection SHA 漂移；
- 任务、Stage、Call、Attempt 关系无法验证；
- transport outcome unknown 且没有可安全对账事实。

Python 不得修正、猜测、拼接或改写 Provider 医学输出。

### 8.2 当前首格停止门

资格化矩阵执行时采用：

```text
任一格失败 → 立即停止 → 保存脱敏证据 → 清理 Runtime → 等待用户决定
```

不能因为“只是一个字段错误”就继续跑后续格，也不能失败后自动提高预算、修改 Prompt、放宽 validator 或自动重试。

### 8.3 v1 projection mismatch 修复边界

v1 失败已经关闭，修复只能通过不可变 v2：

- 不覆盖 Cat/Dog `1.0.0`；
- 不放宽 v1 validator；
- 不通过文件名或像素猜测 projection；
- Provider 不再输出 receipt-owned lineage；
- Stage canonicalizer 只从冻结 Receipt 补确定性事实；
- v2 首次真实失败后不现场修改并重试。

## 9. 验证合同

### 9.1 代码实施阶段

只运行与当前切片相关的既有测试和静态检查：

```text
focused pytest
相关后端全量 pytest
Ruff
compileall
git diff --check
```

不得把这些结果写成真实 Provider 资格或医学准确率。

### 9.2 StudyScreening v2 Runtime 资格结果

Cat v2 已于 2026-09-02 完成受控真实资格：

1. Nacos `2.0.0` exact 发布与回读通过，DB Prompt validated；
2. Config `39c17d76abb145fdabc06bdf4ecf7268` 已 active 且 frozen integrity PASS；
3. Task `2c48ad93315145d19faa1f89b47b0d50` completed；preparation:v1 与 screening:v2 均 completed；
4. Logical Call `2a2e7a7c75624894a261a41305eb3f22` succeeded/accepted；
5. 唯一 Attempt `fab095fec7ac4df091c992fbf4fd9eed` succeeded，Provider HTTP 200；
6. requested/sent/receipt=`2/2/2`，无第二 Attempt，无 retry，Report count=0；
7. Provider raw 为 `xray-study-screening-provider.v2` 最小 anchor，Stage output 为 `xray-study-screening.v2` 完整 canonical lineage；
8. `Attempt.parsed_result_json == AICall.parsed_result_json`，canonicalizer 未原地改写 Provider raw。

本资格不证明医学准确率，也不授权运行 Dog、SystemAnalysis 或其他下游。

### 9.3 三层状态必须分别报告

```text
CODE_IMPLEMENTED       代码实现
STATIC_VALIDATION      静态/合同验证
RUNTIME_QUALIFIED      真实运行时资格
MEDICALLY_VALIDATED    医学效果验证
```

当前 StudyScreening 可以记录：

```text
CODE_IMPLEMENTED
STATIC_VALIDATION_PASSED
NACOS_PROMPTS_EXACT_PUBLISHED
STUDY_SCREENING_V2_ENGINEERING_RUNTIME_PASS
STUDY_SCREENING_ACCURACY_UNKNOWN
MEDICAL_RELEASE_NO_GO
```
### 9.4 SystemAnalysis Cat Runtime 资格结果

Cat `xray_system_analysis` 已于 2026-09-02 完成受控真实资格：

1. Nacos `xray_cat_system_analysis@1.0.0` exact 回读与 DB Prompt validated；
2. Config `bbdd49c799044343a1cc60c5ab9afd4a` active 且 frozen integrity PASS；
3. Task `4e1165980fde4facae1793e637d77cc7` completed；preparation:v1 与 system_analysis:v1 completed；
4. exactly 1 Logical Call / 1 Physical Attempt，Provider HTTP 200，Call succeeded/accepted；
5. requested/sent/receipt=`2/2/2`，无 retry/reconcile，Report count=0；
6. Schema 与 `xray-system-analysis.v1` 动态合同校验通过；2 source refs、5 systems；
7. Stage `source_call_id + system_analysis_result + output_sha256` 持久化完成门 PASS。

`accepted_call_id` 和 `response_object_ref_json` 当前均为可空字段，不属于该 Handler 的既有完成门；未来若升级为强合同，必须先修改生产写入语义和测试，不能只在临时审计中增加要求。

本资格不证明医学准确率，也不证明 StudyScreening → SystemAnalysis → Primary 的同一 Task 完整串联。

## 10. 每次改动的执行协议

### 10.1 开始前

新会话必须读取：

```text
AGENTS.md
AGENT_HANDOFF.md
.agent-handoff/snapshot.md
.agent-handoff/risks.md
.agent-handoff/backlog.md
本文件
当前阶段直接相关源码和既有测试
```

第一条回复必须给出：

```text
当前唯一目标：
当前阶段：
代码事实和 file:line：
为什么现在做：
本轮允许修改的文件：
本轮禁止修改的文件/能力：
是否允许 Provider/Nacos/数据库/Docker：
完成条件：
停止条件：
```

没有明确写出 write set（写入文件集合）之前，不得修改文件。

### 10.2 执行中

- 一个会话只执行一个阶段；
- 一个阶段只允许一个主要变量；
- 发现需要新增表、字段、迁移、Service、Worker、Gateway 或外部写入时立即停止；
- 不得因为旧路线图中存在下一阶段就自动进入下一阶段；
- 不得使用“顺便完善”“顺手修复”扩大写入范围；
- 不得重置、清理、覆盖或暂存不属于本切片的用户改动；
- 禁止 `git add -A`。

### 10.3 结束时

必须记录：

```text
实际修改文件
已运行检查及结果
未运行检查及原因
当前状态
新增风险和 UNKNOWN
下一步唯一动作
```

只有长期架构决策才更新 `decisions.md`；当前状态放 `snapshot.md`；验证放 `validation.md`；待办和风险分别放对应文件。

## 11. 当前明确延后范围

以下内容不是当前阶段工程资格目标：

| 能力 | 状态 | 重新打开条件 |
|---|---|---|
| Pixel Mask Segmentation | `DEFERRED / NOT_IMPLEMENTED` | 用户明确把像素级展示提升为下一优先级，并单独冻结产品合同 |
| Segmentation Job/Artifact/Outbox/Worker | `DEFERRED` | 分割产品合同、模型和存储 owner 明确后 |
| Evaluation R4A–R4D | `DEFERRED` | 用户明确切换到离线评测目标 |
| Gold/医学 Scorer/Holdout | `DEFERRED` | Dataset 治理完成并获得医学负责人批准 |
| Prompt 医学准确率优化 | `DEFERRED` | Runtime 稳定、Gold/Scorer/Holdout 可用 |
| Retry/Fallback/Race | `DEFERRED` | 独立工程合同和授权；竞速不在本切片重复实现 |
| Docker build | `DEFERRED` | 用户明确处理部署资格化 |
| `secret_ref` 注释漂移 | `DEFERRED` | 独立数据库修复授权 |

## 12. 当前下一动作

StudyScreening v2 Cat、SystemAnalysis Cat 以及一次独立 Primary/FamilyRouting/DecisionFinalization/ReportService 工程链已有各自 Runtime 证据；不得重跑，也不得拼接成同一 Task 全链 PASS。当前没有自动执行中的下游目标。

下一候选阶段：

```text
TargetedReview（条件执行）
```

开始前必须由用户另行授权，并准备一个会产生 `targeted_candidate` 的受控病例；重新完成能力总账、Prompt/Schema/Config、条件触发、最多一次调用、完成门和停止门核对。若无法预先证明触发条件，必须停止，不能靠反复调用 Provider“碰”出分支。

持续约束：

1. 不修改或覆盖已冻结 StudyScreening/SystemAnalysis Prompt、Schema、validator 与 Config；
2. 不追加已通过 Task 的第二 Attempt，不发布或运行 Dog；
3. 不自动进入 ReportGeneration、diagnose Root 或同 Task 全链改造；
4. 独立阶段 PASS 不得拼成完整链 PASS；
5. `MEDICAL_ACCURACY_UNKNOWN / MEDICAL_RELEASE_NO_GO` 保持不变。

## 13. 新会话可复制启动 Prompt

```text
请在当前工作区
/Users/mozhicheng/workspace/code/cy-code/ms-image
先读取 AGENTS.md、AGENT_HANDOFF.md、snapshot.md、risks.md、backlog.md 和本开发合同。

已确认事实：StudyScreening v2 Cat 与 SystemAnalysis Cat 已分别完成真实工程 Runtime 资格；
Primary/FamilyRouting/DecisionFinalization/ReportService 另有一次跳过 Screening 的独立 PASS。
这些证据不代表同一 Task 完整链，也不证明医学准确性；医学发布仍为 NO-GO。

下一候选是条件性 TargetedReview。只有用户明确授权且能冻结 targeted candidate 用例后才允许开始；
先报告完成能力账本、精确 write set、外部权限、触发门、完成门和停止门，不得自动运行 Dog 或 ReportGeneration。
```

## 14. 变更记录

### v1.4 — 2026-09-02

- Cat SystemAnalysis Prompt/Config 与单次真实 Runtime 已独立工程资格化；
- 记录 1 Call、1 Attempt、Provider 200、accepted、Task completed、2/2/2、Schema/合同/Stage 持久化和 Report 0；
- 明确当前完成门使用 `source_call_id + system_analysis_result + output_sha256`，不把可空审计字段误设为强合同；
- 保持独立阶段证据隔离，下一候选为条件性 TargetedReview；医学准确性继续 UNKNOWN/NO-GO。

### v1.3 — 2026-09-02

- StudyScreening v2 Cat 控制面与单次真实 Runtime 已工程资格化；
- 记录 1 Call、1 Attempt、Provider 200、accepted、Task completed、2/2/2、Report 0 和 Provider raw/Stage canonical 双边界审计；
- 区分 Schema 原始文件 SHA 与 Config frozen canonical JSON SHA；
- 下一候选改为 SystemAnalysis，但必须另行授权，不自动开始；医学准确性保持 UNKNOWN/NO-GO。

### v1.2 — 2026-09-02

- 用户授权实施并真实验证 StudyScreening v2；active objective 从失败关闭的 v1 切换为隔离的 Cat v2 资格化；
- 固定 Provider 最小 anchor 与 Stage Receipt canonical 双边界，v1 Prompt/Schema/validator/replay 保持不可变；
- 固定 `task_type=xray_study_screening`、`profile=xray_study_screening_v2`，不创建独立 HTTP endpoint、不进入 diagnose Root/Primary/Report；
- 固定 Cat `2.0.0` 控制面、单 Call/单 Attempt、首次失败停止和 Dog/下游禁止门。

### v1.1 — 2026-09-01

- 用户将唯一 active objective 切换为 `StudyScreening:v1`，固定后续顺序但禁止提前进入 SystemAnalysis；
- 记录 StudyScreening 代码与静态验证已通过，真实 Runtime 尚未运行；
- 纠正外部状态：Cat/Dog StudyScreening Nacos `1.0.0` 已 online/exact 回读，不得重复发布；
- 固定 Quality Task 显式引用、Stage-specific Config binding、Root/Stage 总预算一致性和首次失败停止门。

### v1.0 — 2026-09-01

- 将当前有效目标收敛为 Anatomy Localization v1 的 bbox 定位合同；
- 明确诊断主链和定位展示链是两条业务链，但当前研发只允许一个 active objective；
- 将 Pixel Mask Segmentation、Evaluation、Docker、Prompt 优化和 Retry/Fallback/Race 标记为延后；
- 固定当前 `cat-02` projection mismatch 的只读审计和停止门；
- 增加已完成能力总账、当前四应用/82 路由工作树口径和每轮强制复核清单；
- 增加每次会话的 write set、外部授权、验证和 handoff 更新协议；
- 将旧完整路线图降为历史背景，不再作为自动执行入口。
