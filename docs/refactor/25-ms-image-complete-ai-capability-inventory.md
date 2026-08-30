# MS-Image 全部 AI 能力、Prompt 资产与完整链路现状盘点

更新时间：2026-08-27

适用仓库：`/Users/mozhicheng/workspace/code/cy-code/ms-image`

## 1. 文档目的

本文统一整理当前 `ms-image` 项目中已经存在、正在规划、仅保留兼容或仅用于离线评测的全部 AI 能力，回答以下问题：

1. `ms-image` 当前真正具备哪些 AI 能力；
2. 完整在线链路由哪些控制面、运行面、存储面和评测面组成；
3. 每项 AI 能力的输入、处理、输出和下游消费者是什么；
4. 项目中到底存在多少 Prompt，哪些是正式 Runtime Prompt，哪些只是历史组合素材；
5. 当前已经完成什么、还缺什么，以及为什么尚未完成；
6. 后续应按什么顺序继续开发，避免重复建设或误报完成状态。

本文是现状盘点，不代表医学放行，也不授权数据库迁移、表结构修改或生产配置变更。

---

## 2. 权威事实与禁止误报

当前唯一已经真实通过的事实是：

```text
MS_IMAGE_CORE_AI_NETWORK_CHAIN_PASSED
```

它只证明以下基础网络合同已经跑通：

```text
Nacos Prompt
-> PromptRenderer / PromptMessageAssembler
-> GatewayClient
-> ms-ai-platform
-> Provider Model
-> 严格 JSON Schema
-> Provider Request ID
```

它不证明以下事项：

```text
FULL_WORKER_RUNTIME_NOT_QUALIFIED
MEDICAL_ACCURACY_UNKNOWN
MEDICAL_RELEASE_NO_GO
```

因此本文统一使用以下状态：

| 状态 | 含义 |
|---|---|
| `VERIFIED` | 已有对应真实验证证据 |
| `CODE_READY` | 代码存在且合同可测试，但未完成真实环境资格化 |
| `PARTIAL` | 只有部分代码或局部链路 |
| `PLANNED` | 设计存在，运行实现尚未完成 |
| `LEGACY` | 仅为 v1 兼容或历史素材，不是当前主入口 |
| `OFFLINE` | 仅用于离线评测或治理，不属于在线诊断链 |
| `NOT RUN` | 对应真实环境验证没有运行 |
| `UNKNOWN` | 当前无法证明结果质量 |

---

## 3. 全项目结论先行

### 3.1 当前真正的在线 AI 业务范围

当前代码注册的 Provider AI Stage 只有 XRay：

```text
joint_primary_reader
targeted_review
```

证据：

- `apps/backend/core/pipeline.py:61-77`
- `apps/backend/services/runtime/stages/registry.py:31-36`

`StudyCreate` 虽允许以下影像类型：

```text
xray
ct
mri
ultrasound
endoscopy
pathology
clinical_photo
dental_xray
other
```

证据：`apps/backend/schemas/study.py:9-20`。

但除 XRay 外，当前没有发现对应的：

```text
专用 Pipeline Profile
Runtime Stage Handler
Prompt Command
Nacos Prompt identity
输出 Schema
Provider 调用合同
Report 消费合同
医学评测基线
```

所以，当前不能把“可以创建某种 modality 的 Study”误报为“已经具备该 modality 的 AI 分析能力”。

### 3.2 当前 AI 能力数量

按不同口径统计：

| 统计口径 | 数量 | 构成 |
|---|---:|---|
| 当前最小在线 Runtime Prompt | 1 | XRay Primary |
| 完整 XRay 目标 Runtime Prompt | 2 | Primary + TargetedReview |
| 语义完整 Prompt/Prompt-like 指令 | 3 | Primary + TargetedReview + Offline Failure Analysis |
| 旧 catalog Prompt 资产 | 20 | base、family、focus、strategy、technical evidence、offline evaluation |
| 当前非 XRay 在线 AI 能力 | 0 | 只有 Study 类型，没有 AI Runtime |

### 3.3 当前代码链路的核心缺口

当前不是“缺很多 Prompt 文件”，而是以下工程链还没有取得同一冻结任务的真实证据：

```text
MySQL
-> Outbox
-> Broker
-> Worker
-> OSS image object
-> Attempt Image Signer
-> Gateway
-> Provider
-> Attempt
-> Stage
-> DecisionFinalization
-> Report
```

同时：

- Primary Prompt 已存在并已发布 Nacos，但正式 Config 导入、编译、激活和 Worker 冻结使用仍需同链验证；
- TargetedReview Prompt 已有本地候选，但尚无正式 Nacos identity、Config 和确定性路由触发；
- 输出 Schema 顶层严格、嵌套字段仍偏宽；
- 当前 `ms-image` 内没有宠物档案模型或自动查询宠物档案的 Service；`species` 由调用方在创建诊断 Task 时传入并被冻结；
- Retry、Fallback、Race 属于 Attempt 调度能力，不是额外 Prompt；
- 医学准确率、Gold、Failure Bank 和 Holdout 尚未完成真实资格化。

---

## 4. 完整架构总图

```text
上游业务系统 / medical-record / pet profile
        |
        | session_id、study、pet_id/species 等业务事实
        v
Runtime API
        |
        | API -> Service -> DalBase CRUD -> Model/DB
        v
Session -> Study -> Series -> Image
        |
        | Study finalize / immutable image manifest
        v
TaskService
        |
        | 解析 active AI Config
        | 冻结 species、Study revision、image manifest、Prompt、Schema、模型池和 Pipeline
        v
Task Snapshot + Stage Checkpoint + Outbox Event
        |
        | 事务提交后发布
        v
Broker -> Worker
        |
        v
StudyPreparation
        |
        v
JointPrimaryReader
        |
        | frozen Prompt + safe context + image refs + schema
        v
AIRequestService
        |
        | prepare Logical Call / Physical Attempt（事务内）
        | transaction commit
        | sign images / call Provider（事务外）
        v
AttemptImageSigner -> OSS 短时只读 URL
        |
        v
GatewayClient -> ms-ai-platform -> Provider Model
        |
        | Provider Request ID + strict JSON result + non-sensitive audit facts
        v
Attempt -> AI Call -> Stage output
        |
        +---------------------------+
        |                           |
        v                           v
FamilyRouting                  Primary Final
        |
        | deterministic route signal
        v
TargetedReview（最多一次）
        |
        | same frozen Study + Primary result + targeted route
        v
new complete_medical_result
        |
        v
DecisionFinalization
        |
        v
Report
        |
        v
Evaluation Export -> Gold / Failure Bank / Paired A-B / Holdout
```

### 4.1 六个逻辑平面

| 平面 | 责任 | 主要代码 |
|---|---|---|
| 业务与影像输入面 | Session、Study、Series、Image、Task 输入 | `apps/backend/services/runtime/api/`、`apps/backend/services/runtime/service/` |
| Prompt/模型控制面 | Prompt 导入、Connection、ModelPool、Config 编译与激活 | `apps/backend/services/ai_control/` |
| 可靠执行面 | Task、Outbox、Broker、Worker、Stage 状态推进 | `apps/backend/core/messaging/`、`apps/backend/workers/`、`imaging_execution_service.py` |
| AI Gateway 面 | Prompt 渲染、消息组装、签图、Provider 请求、Schema 校验 | `apps/backend/services/runtime/service/ai_request_service.py`、`apps/backend/core/ai/gateway/` |
| 结果面 | Attempt、Stage、Finalization、Report | `apps/backend/models/ai_call.py`、`apps/backend/models/ai_call_attempt.py`、`report_service.py` |
| 评测治理面 | Dataset、Gold、Failure Bank、Paired A/B、Holdout | `apps/backend/services/evaluation_control/` |

---

## 5. 业务输入与宠物档案现状

### 5.1 Session 的当前职责

`Session` 是一次影像业务会话边界，用于组织多个 Study，并保存上游来源标识：

```text
source_system
source_session_id
source_medical_record_id
requester_id
```

主要实现：

- `apps/backend/models/session.py`
- `apps/backend/schemas/session.py`
- `apps/backend/crud/session.py`
- `apps/backend/services/runtime/service/session_service.py`

当前 `Session` 没有 `subject_id`，也没有必要为了宠物档案增加 `Session.subject_id`。业务系统可以通过 `session_id`、`source_medical_record_id` 或其他上游关系获得宠物 ID，再将最终确认的物种事实传给 Task。

### 5.2 当前 species 的真实来源

当前 `ms-image` 没有独立 `Pet` Model、`PetDal` 或 `PetService`，也没有在创建 Task 时自动访问 `ms-ai-fast` 宠物档案接口。

当前合同是：

```text
调用方创建 diagnose Task
-> TaskCreate.species 必填
-> 只允许 cat / dog
-> TaskService 将 species 冻结到 request_snapshot_json
-> Worker 从冻结 Snapshot 读取
-> Prompt 使用 SAFE_STUDY_CONTEXT_JSON.species
```

证据：

- `apps/backend/schemas/task.py:9-45`
- `apps/backend/services/runtime/service/task_service.py:367-399`
- `apps/backend/services/runtime/stages/xray/prompt_commands.py:155-170`

当前状态：

| 能力 | 状态 |
|---|---|
| diagnose Task 强制 cat/dog | `CODE_READY` |
| species 冻结进 Task Snapshot | `CODE_READY` |
| Prompt 从 Snapshot 获取 species | `CODE_READY` |
| 通过宠物档案自动获取 species | `NOT IMPLEMENTED` |
| 真实宠物档案到 Worker 同链验证 | `NOT RUN` |

后续若接宠物档案，应由上游或现有业务 Service 在创建 Task 前确定物种；Worker 仍不得运行时查询宠物档案 latest，以保证冻结重放。

---

## 6. 影像输入与 OSS 能力

### 6.1 已存在的影像领域能力

当前项目存在：

```text
Session
Study
Series
Image
Study revision
Image manifest
对象上传准备
上传确认
对象校验
对象生命周期与对账
```

主要代码：

- `apps/backend/services/runtime/service/study_service.py`
- `apps/backend/services/runtime/service/image_service.py`
- `apps/backend/services/runtime/service/image_upload_workflow.py`
- `apps/backend/core/imaging/object_store.py`
- `apps/backend/models/image.py`
- `apps/backend/models/series.py`
- `apps/backend/models/study.py`

对象本体存 OSS；领域表保存：

```text
storage_profile
object_key
object_version_id
sha256
size_bytes
content_type
status
生命周期事实
```

项目不恢复 `file_asset`。

### 6.2 Attempt Image Signer

当前存在 `OSSAttemptImageSigner`，职责是为一个 Physical Attempt 生成短时只读图像 URL：

- `apps/backend/core/ai/gateway/image_signer.py:31-152`

已有代码约束：

1. `attempt_id` 必须是合法 opaque ID；
2. TTL 最小 30 秒，最大不超过配置上限，代码上限 900 秒；
3. 图像顺序必须连续并与请求数一致；
4. `storage_profile` 必须匹配当前 OSS；
5. MIME 仅允许 DICOM/JPEG/PNG；
6. SHA-256、大小、Object Version 等不可变事实必须重新校验；
7. 签名 URL 必须是允许域名；
8. `GatewayImageInput.signed_url` 明确不得持久化。

当前状态：

```text
CODE_IMPLEMENTED: YES
RUNTIME_QUALIFIED: NOT RUN
```

仍需用真实 OSS 验证：

- bucket/endpoint host allowlist；
- 对象 key 是否严格限制在冻结 Attempt manifest；
- URL 是否只有 GET/read 权限；
- URL 过期后是否拒绝；
- DB、日志、Task Snapshot 是否完全不持久化签名 URL。

---

## 7. Prompt 控制面能力

### 7.1 控制面链路

```text
Nacos exact dataId
-> PromptImportService
-> normalize_imported_prompt
-> AIPromptTemplate
-> AI Connection
-> AI Model Pool
-> ConfigCompiler
-> AIConfigRecord
-> activate
-> TaskService 冻结到 Task Snapshot
```

主要代码：

- `apps/backend/services/ai_control/service/prompt_source.py`
- `apps/backend/services/ai_control/service/prompt_import_service.py`
- `apps/backend/services/ai_control/service/prompt_template_service.py`
- `apps/backend/services/ai_control/service/api_connection_service.py`
- `apps/backend/services/ai_control/service/model_pool_service.py`
- `apps/backend/services/ai_control/service/config_compiler.py`
- `apps/backend/services/ai_control/service/ai_config_service.py`

### 7.2 XRay 当前唯一正式 Prompt identity

当前 `prompt_source.py` 只接受：

```text
internal prompt_key: xray_primary
variant: common
Nacos dataId: ms-image.x-ray.primary.common.zh-CN
```

证据：`apps/backend/services/ai_control/service/prompt_source.py:42-53,76-143`。

猫犬不是 Prompt identity：

```text
species=cat|dog
```

作为冻结病例事实进入 `SAFE_STUDY_CONTEXT_JSON`。

### 7.3 Worker 的 Prompt 读取规则

Worker 不读取 Nacos latest。v2 Runtime 使用已经冻结的：

```text
config.prompt_content
config.prompt_variables_json
config.output_schema_json
```

然后执行严格渲染和消息组装：

- `apps/backend/services/runtime/service/ai_request_service.py:763-792`
- `apps/backend/core/ai/prompting/message_contract.py:65-85`

这保证同一 Task 可以按相同 Prompt、Schema、模型配置和 Study revision 重放。

---

## 8. 全部 Prompt 资产盘点

### 8.1 正式 Runtime Prompt 1：XRay Primary

身份：

```text
ms-image.x-ray.primary.common.zh-CN
```

本地正文：

```text
prompts/xray/nacos/primary/common/zh-CN/
  ms-image.x-ray.primary.common.zh-CN.v1.0.0.txt
```

输入：

```text
$SAFE_STUDY_CONTEXT_JSON
$OUTPUT_SCHEMA_JSON
同一冻结 Study 的全部有序图像
```

处理：

```text
完整 Study 联合主读
技术质量判断
覆盖范围判断
多视位证据整合
猫犬条件化解释
医学状态选择
结构化结果生成
```

输出：

```text
complete_medical_result
```

下游：

```text
JointPrimaryReader Stage
-> FamilyRouting 或 DecisionFinalization
-> Report
-> Evaluation Export
```

当前状态：

```text
本地 Prompt：存在
Nacos canonical Prompt：已发布
基础网络合同：VERIFIED
正式 Worker 全链：NOT RUN
医学准确率：UNKNOWN
```

### 8.2 未来 Runtime Prompt 2：XRay TargetedReview

建议身份：

```text
internal prompt_key: xray_targeted_review
variant: common
Nacos dataId: ms-image.x-ray.targeted-review.common.zh-CN
```

本地候选：

```text
prompts/xray/nacos/targeted-review/common/zh-CN/
  ms-image.x-ray.targeted-review.common.zh-CN.v1.0.0.txt
```

输入：

```text
$SAFE_STUDY_CONTEXT_JSON
$PRIMARY_RESULT_JSON
$OUTPUT_SCHEMA_JSON
同一冻结 Study 的全部有序图像
```

Targeted safe context 还包括：

```text
selected_family_key
selected_focus_key
selected_strategy_key
source_finding_ids
coverage_proof
route_reason_codes
primary_complete_result
```

处理：

```text
独立复核 Primary 结果
围绕唯一 Family/Focus 提高检查深度
重新检查同一完整 Study
保留或修正 Primary 结论
输出新的完整病例结果
```

输出仍是新的完整：

```text
complete_medical_result
```

禁止输出：

```text
局部 patch
yes/no
Python 医学合并
Python 投票
Python 改写 medical_status
```

当前状态：

```text
本地候选：CODE_READY
模板变量渲染：已通过本地检查
Nacos identity：NOT IMPLEMENTED
Nacos 发布：NOT RUN
Targeted Config：NOT RUN
FamilyRouting 触发：NOT IMPLEMENTED
Provider Targeted 调用：NOT RUN
医学验证：UNKNOWN
```

### 8.3 Offline Prompt 3：Failure Analysis

文件：

```text
prompts/xray/offline_evaluation_failure_analysis.zh-CN.txt
```

职责：

```text
对脱敏 Evaluation Artifact 做失败归因
整理 Failure Bank
形成 Prompt/Model 实验建议
支持 Paired A/B 和回归分析
```

它不能：

```text
修改 Gold
修改线上 Task/Report
修改医学结论
直接激活线上 Config
作为在线 Worker Prompt
```

当前状态：`OFFLINE / NOT CONNECTED`。

### 8.4 旧 catalog 的 20 个资产

`prompts/xray/catalog.zh-CN.json` 共记录 20 个资产：

| 类别 | 数量 | 用途 |
|---|---:|---|
| `joint_primary_base` | 1 | 旧 Primary 基础正文 |
| `joint_primary_module` | 5 | 胸腔、腹腔、四肢骨科、轴骨科、头颈 |
| `targeted_focus` | 7 | base + 6 个专项 focus |
| `review_strategy` | 5 | 高召回、正常闭环、重点征象确认、冲突处理、疑难复核 |
| `technical_evidence` | 1 | 技术证据与来源链 |
| `offline_evaluation` | 1 | 离线失败分析 |

这些资产由旧 `PromptCompiler` 组合：

- `apps/backend/core/ai/prompting/compiler.py:58-168`
- `apps/backend/core/ai/prompting/catalog.py`

它们不是 20 个独立的 v2 Nacos Prompt，不应逐个发布 dataId。正确用途是：

```text
作为医学规则素材
-> 核对并吸收进完整 Primary Prompt
-> 核对并吸收进完整 TargetedReview Prompt
-> 保留离线治理素材
```

### 8.5 不需要新增 Prompt 的能力

以下能力不调用模型：

```text
StudyPreparation
FamilyRouting
DecisionFinalization
Outbox
Broker
Report persistence
Retry scheduling
Fallback scheduling
Race winner selection
```

它们应保持确定性代码合同，不能通过新增 Prompt 代替。

---

## 9. Prompt 输入合同

### 9.1 Primary safe context

`build_primary_ai_request_command()` 为 v2 创建：

```text
prompt_kind=primary
applicable_family_keys=()
safe_context=<frozen context>
```

相关实现：`apps/backend/services/runtime/stages/xray/prompt_commands.py:55-81`。

安全上下文字段：

```text
task_id
prompt_mode
study_revision_id
ordered_image_refs
species
anatomy_regions
view_positions
coverage
technical_limitations
clinical_context_allowlist
technical_evidence_available
```

相关实现：`apps/backend/services/runtime/stages/xray/prompt_commands.py:136-179`。

### 9.2 Targeted 输入合同

Targeted 必须从上一个 Stage 获取：

```text
previous_output.complete_medical_result
selected_family_key
selected_focus_key
```

可选：

```text
selected_strategy_key
source_finding_ids
coverage_proof
route_reason_codes
```

缺少 Primary 完整结果、Family 或 Focus 时必须失败关闭。

相关实现：`apps/backend/services/runtime/stages/xray/prompt_commands.py:84-124`。

### 9.3 图片输入合同

发送给 Provider 的图片必须来自同一冻结 Attempt plan，并按 `sequence_no` 排序。签名 URL 只是短时传输载体，不属于可持久化业务事实。

Gateway 请求中的非敏感冻结事实包括：

```text
attempt_id
logical_call_id
task_id
trace_id
request_id
connection_sha256
provider_type
api_format
requested_model
allowed_actual_models
generation_params
response_schema
messages
images
timeout_ms
provider_idempotency_key
image_manifest_sha256
```

相关实现：`apps/backend/core/ai/gateway/contracts.py:143-184`。

### 9.4 输入合同当前缺口

| 缺口 | 原因 | 后续处理 |
|---|---|---|
| 宠物档案自动获取 species 未接入 | 当前 species 由 Task 调用方传入 | 上游通过 pet/medical-record 取得后创建 Task；冻结后 Worker 不再查询 latest |
| 真实 OSS signed URL 输入未同链验证 | 只有代码和测试合同 | P1 用真实 OSS 验证 host、TTL、read-only、object scope |
| Targeted route input 不可达 | FamilyRouting 固定 `primary_final` | M2 后实现确定性路由和唯一候选选择 |
| Targeted Prompt 无正式 source identity | `prompt_source.py` exact-only Primary | M2 单独增加 identity、Config 和发布流程 |

---

## 10. 输出合同

### 10.1 当前统一输出 Schema

文件：

```text
prompts/xray/complete_medical_result.schema.json
```

顶层约束：

```text
type=object
additionalProperties=false
```

必填字段：

```text
medical_status
findings
normal_basis
coverage
families_not_assessed
limitations
review_reason
source_refs
```

可选字段：

```text
targeted_candidate
```

医学状态只允许：

```text
normal
abnormal
review_required
non_diagnostic
```

### 10.2 输出消费者

```text
Provider strict JSON response
-> schema_validate_result
-> GatewayExecutionResult.parsed_result_json
-> AI Call / Attempt audit facts
-> JointPrimaryReader or TargetedReview Stage
-> DecisionFinalization
-> ReportService
-> EvaluationExportService
```

Stage 不得通过 Python 改写模型输出的四类医学结论。

### 10.3 当前 Schema 缺口

当前 Schema 是“顶层严格、嵌套较宽”：

```json
"findings": {"type": "array", "items": {"type": "object"}},
"coverage": {"type": "object"},
"source_refs": {"type": "array", "items": {"type": "object"}},
"targeted_candidate": {"type": ["object", "null"]}
```

尚未严格固定：

```text
Finding ID、Family、部位、征象、解释、确定性
Finding 到 image/series 的 source_refs
coverage 的 family/view/quality 字段
source_refs 的 object identity 字段
targeted_candidate 的 family/focus/strategy/route evidence
嵌套对象 additionalProperties=false
```

这会影响：

```text
FamilyRouting 稳定消费
Report 稳定展示
Failure Bank 归因
Prompt/Model Paired A/B
长期 Schema 兼容
```

Schema 收紧必须单独版本化，不应在未评估影响时覆盖现有版本。

---

## 11. XRay Pipeline 能力

### 11.1 Profile

当前代码定义：

```text
xray_primary_v1:
  study_preparation
  -> joint_primary_reader
  -> decision_finalization

xray_targeted_review_v1:
  study_preparation
  -> joint_primary_reader
  -> family_routing
  -> conditional targeted_review
  -> decision_finalization
```

证据：`apps/backend/core/pipeline.py:71-114`。

### 11.2 StudyPreparation

职责：

```text
读取冻结 Task Snapshot
检查 Study revision 和图像清单
形成后续 Stage 的稳定输入
不调用 Provider
不作医学判断
```

状态：代码存在；真实主链证据仍需 E1。

### 11.3 JointPrimaryReader

职责：

```text
构建 Primary Prompt Command
发起一个逻辑 AI Call
消费 schema-accepted 结果
将完整结果写入 complete_medical_result
```

主要实现：

- `apps/backend/services/runtime/stages/xray/joint_primary_reader.py`
- `apps/backend/services/runtime/stages/xray/prompt_commands.py`

失败时 Stage 失败，不得伪造 `normal`。

### 11.4 FamilyRouting

目标职责：

```text
确定性读取 Primary complete_medical_result
选择 0 或 1 个 Targeted candidate
输出唯一 family/focus/strategy 和 route evidence
不读取图像
不调用 Provider
不修改医学结论
```

当前实现：

```text
复制 Primary 结果
route_signal=primary_final
不产生 targeted_review signal
```

证据：`apps/backend/services/runtime/stages/xray/family_routing.py:13-39`。

状态：`PARTIAL`。

### 11.5 TargetedReview

代码 Stage Handler 已存在：

- `apps/backend/services/runtime/stages/xray/targeted_review.py`

但正式运行仍缺：

```text
Targeted Prompt source identity
Targeted Prompt Nacos publication
Targeted Config 编译与激活
FamilyRouting 唯一触发规则
真实 Targeted Attempt
医学基线与收益证明
```

状态：`PLANNED / CODE SKELETON`。

### 11.6 DecisionFinalization

职责：

```text
选择上一个已接受 Stage 的完整结果
标记 selected_owner=primary|targeted
保留 source_stage_id/source_call_id
形成最终结果
```

实现：`apps/backend/services/runtime/stages/common/decision_finalization.py:13-41`。

它只选择结果所有者，不进行医学融合或改判。

---

## 12. AI Request、Gateway 与 Provider 能力

### 12.1 Logical Call 与 Physical Attempt

```text
Logical Call：一次医学目的调用
Physical Attempt：一次真实 Provider 发送尝试
```

一个 Logical Call 后续可以有多个 Attempt，用于 Retry、Fallback 或 Race；但每个 Attempt 必须有独立：

```text
attempt_id
provider_idempotency_key
connection/model facts
request hash
provider request ID
status
response digest/audit facts
```

模型：

- `apps/backend/models/ai_call.py`
- `apps/backend/models/ai_call_attempt.py`

### 12.2 事务边界

正确边界：

```text
事务内：
  prepare Call/Attempt
  持久化冻结请求事实
  更新 Stage/Task 状态
  写 Outbox

事务提交后：
  OSS HEAD/签图
  Broker publish
  Provider network I/O
```

事务内不得执行 OSS、Broker 或 Provider 网络 I/O。

### 12.3 Gateway 请求合同

`GatewayRequest` 会对不包含 API Key 和短时 URL 的请求意图计算摘要：

- `apps/backend/core/ai/gateway/contracts.py:143-184`

`GatewayClient` 使用：

```text
AI_PLATFORM_OPENAI_BASE_URL
AI_PLATFORM_API_KEY
```

并发送：

```text
Authorization: Bearer <api key>
Idempotency-Key
X-Request-ID
X-Trace-ID
```

Provider Request ID 必须存在，否则请求结果不接受。

### 12.4 Secret 状态

当前链路已经收口为 `GatewayClient` 直接读取 AI Platform 的 base URL 和 API key 配置，不再依赖旧：

```text
AI_GATEWAY_SECRET_RESOLVER_MODE
AI_GATEWAY_RESPONSE_ENCRYPTION
```

安全目标仍然不变：

```text
API Key 不进入数据库
API Key 不进入 Nacos Prompt
API Key 不进入 Task Snapshot
API Key 不进入日志和审计 payload
```

是否满足正式 Worker 注入和日志脱敏要求，仍需 P1 真实运行资格化。

### 12.5 Provider 原始响应

当前生产合同是：**不持久化 Provider 原始响应正文**。

`GatewayExecutionResult` 只返回：

```text
provider_request_id
actual_model
usage_json
parsed_result_json
response_sha256
duration_ms
transport_mode
```

其中：

- `parsed_result_json` 是严格 JSON Schema 校验后的规范化结构结果；
- `response_sha256` 是 Provider JSON body 的规范化摘要；
- `provider_request_id`、`actual_model`、`usage_json`、`duration_ms` 是非敏感审计事实；
- Provider 原始 body 不写数据库，也不写 OSS。

证据：

- `apps/backend/core/ai/gateway/contracts.py:187-204`
- `apps/backend/services/runtime/service/ai_request_service.py:1231-1267`
- `apps/backend/services/runtime/service/ai_request_service.py:1295-1352`

`AICall` / `AICallAttempt` Model 与 DAL 仍保留 `response_object_ref_json` 遗留字段，但当前 Service/Worker 没有写入调用。该字段属于后续获得数据库/迁移授权后的清理项，不是 P1/E1 Primary 主链阻塞项，也不得据此恢复已删除的 Provider 原始响应加密 OSS 链。

---

## 13. unknown、幂等、取消、迟到结果与恢复

### 13.1 幂等

已有幂等边界：

```text
Session request/source identity
Study source identity
Image upload/confirm identity
Task request_id/business_key
Outbox event key
AI Logical Call idempotency key
Physical Attempt provider_idempotency_key
```

数据库模型对 Attempt provider identity 有唯一约束：

- `apps/backend/models/ai_call_attempt.py:18-39`

### 13.2 unknown

Physical Attempt 状态候选：

```text
prepared
sending
succeeded
failed
unknown
cancelled
```

并保存：

```text
provider_request_id
provider_idempotency_key
next_reconcile_at
```

当前有：

- `apps/backend/core/ai/gateway/attempt_lookup.py`
- `apps/backend/services/runtime/service/ai_attempt_reconcile_service.py`
- `apps/backend/workers/imaging_worker/ai_attempt_reconcile.py`

安全规则：

```text
unknown Attempt 必须按原 provider_idempotency_key / provider request identity 查询
禁止把 unknown 直接当 failed 后盲目创建并发送新 Attempt
```

是否能对当前真实 Provider 执行查询，仍需真实资格化；代码存在不等于 Provider 支持查询。

### 13.3 取消

Session、Task 和执行服务存在取消状态与 CAS 更新。取消要求：

```text
取消请求持久化
尚未发送的 Attempt 不再发送
已经发送的 Provider 请求可能无法物理撤回
迟到结果不得覆盖已取消/已终结任务
保留审计事实
```

### 13.4 迟到结果

迟到 Provider 结果必须根据：

```text
attempt_id
lease_generation
state_version
Task/Stage terminal state
winner ownership
```

进行条件接受。不能因为迟到结果医学内容“更好”就覆盖已经确定的所有者。

### 13.5 Retry / Fallback / Race

这些能力复用同一冻结 Prompt 和 Schema：

```text
Retry：同一 Provider/Model 的新 Physical Attempt
Fallback：换到已资格化的候选 Provider/Model
Race：并发多个已资格化候选，按技术合同选唯一 winner
```

它们不需要新增医学 Prompt。

当前状态：

```text
基础 Attempt/状态合同：存在
正式 Retry：未资格化
正式 Fallback：未资格化
正式 Race：未资格化
```

---

## 14. Report 与 Evaluation 能力

### 14.1 Report

`DecisionFinalization` 形成唯一完整结果后，由 `ReportService` 保存：

- `apps/backend/services/runtime/service/report_service.py`
- `apps/backend/models/report.py`

核心事实：

```text
Report 的 medical_status 必须来自模型完整结果
Report 必须关联 source task/stage/call
重复完成应幂等
不同结果不得静默覆盖
```

### 14.2 Evaluation Control Plane

现有代码包括：

```text
Evaluation dataset/case 管理
Gold 相关数据结构
Evaluation execution
Evaluation export
Paired A/B
Fake scorer（仅工程测试）
Evaluation outbox relay
```

主要目录：

```text
apps/backend/services/evaluation_control/
apps/backend/models/evaluation.py
apps/backend/schemas/evaluation.py
apps/backend/schemas/evaluation_execution.py
apps/backend/schemas/evaluation_export.py
apps/backend/schemas/evaluation_pairing.py
apps/backend/crud/evaluation.py
```

必须明确：

```text
Fake scorer 不是医学评测
Mock 通过不是医学准确率证据
单个病例模型调用不是医学放行
```

真实医学门禁仍需要：

```text
可信 Gold
病例分层
盲法审阅
Failure Bank
Primary Prompt paired A/B
第二 Provider/Model paired A/B
Holdout
回归门禁
```

---

## 15. 全部 AI 能力状态矩阵

| 能力 | 代码 | 真实 Runtime | 医学验证 | 结论 |
|---|---|---|---|---|
| XRay Primary Prompt Source | 有 | Nacos 基础读取已验证 | 未评测 | `PARTIAL` |
| PromptRenderer / MessageAssembler | 有 | 基础网络链已验证 | 不适用 | `VERIFIED`（基础合同） |
| Config 编译与冻结 | 有 | 同一真实 Worker 任务未证明 | 不适用 | `CODE_READY` |
| Task Snapshot | 有 | 真实完整证据未收集 | 不适用 | `CODE_READY` |
| Outbox / Broker / Worker | 有 | 完整 AI 任务链未资格化 | 不适用 | `PARTIAL` |
| OSS 影像对象链 | 有 | Provider 同链签图未资格化 | 不适用 | `PARTIAL` |
| Attempt Image Signer | 有 | 真实 OSS 未资格化 | 不适用 | `CODE_READY` |
| GatewayClient -> ms-ai-platform | 有 | 基础网络链已通过 | 未评测 | `VERIFIED`（非完整 Worker） |
| 严格 JSON Schema | 有 | 基础网络链已通过 | Schema 嵌套待收紧 | `PARTIAL` |
| Provider Request ID | 有 | 基础网络链已通过 | 不适用 | `VERIFIED`（基础合同） |
| Primary Stage | 有 | 正式 Worker 未运行 | 未评测 | `CODE_READY` |
| FamilyRouting | 只有 primary_final | 未触发 Targeted | 未评测 | `PARTIAL` |
| TargetedReview Stage | 有骨架 | 未接入正式 Prompt/Config | 未评测 | `PLANNED` |
| unknown reconcile | 有合同和 worker | 真实 Provider 查询未资格化 | 不适用 | `CODE_READY` |
| Provider 响应最小化持久化 | 当前运行链只存 Schema-valid 结果、摘要与审计事实；遗留对象引用字段未使用 | 正式 Worker 同链审计未运行 | 不适用 | `CODE_READY` |
| Report | 有 | 完整 AI 结果链未证明 | 未评测 | `CODE_READY` |
| Evaluation Plane | 有工程结构 | 真实医学数据未运行 | `UNKNOWN` | `PARTIAL` |
| Retry | 基础 Attempt 结构有 | 未资格化 | 未评测 | `PLANNED` |
| Fallback | 设计有 | 未资格化 | 未评测 | `PLANNED` |
| Race | 设计有 | 未资格化 | 未评测 | `PLANNED` |
| CT/MRI/超声等 AI | 无专用 Stage/Prompt | 未运行 | 未评测 | `NOT IMPLEMENTED` |

---

## 16. 完成全部 XRay 链路仍欠缺的工作

### P0 Database Baseline

目标：

```text
确认当前目标表与 Model 一致
确认必要表存在且字段兼容
保留备份与恢复点
不得误删或重建未授权表
```

当前是否通过：以真实数据库审计结果为准，本文不执行数据库操作。

### P1 Worker Runtime Security Qualification

需要真实证明：

1. 正式 Worker 获得 `AI_PLATFORM_OPENAI_BASE_URL` 与 `AI_PLATFORM_API_KEY`；
2. API Key 不进入 DB、Nacos、日志、Task Snapshot；
3. OSS 签图只允许冻结对象、允许域名、短 TTL、只读访问；
4. 核验 Provider 原始正文不持久化，只保存 Schema-valid 结果、响应摘要、Provider Request ID 和非敏感 Attempt 审计事实；
5. unknown Attempt 按原幂等身份查询，不盲目重发；
6. 收集同一冻结任务的非敏感全链证据。

### E1 Primary-only Runtime

需要跑通：

```text
真实 DB
-> active Primary Config
-> frozen Task Snapshot
-> Outbox
-> Broker
-> Worker
-> OSS image signing
-> Provider
-> Attempt succeeded
-> JointPrimaryReader completed
-> DecisionFinalization completed
-> Report created
```

### M1 Primary Medical Baseline

需要：

```text
真实病例集
Gold
病例分层
盲法复核
错误分类
Primary 指标基线
```

### Q3 Primary Prompt Paired A/B

目的：只改变 Prompt 版本，对同一冻结输入做成对比较。

### Q4 Second Provider Qualification + Model A/B

目的：先证明第二 Provider 的工程资格，再做同病例、同 Prompt、同 Schema 的模型比较。

### M2 FamilyRouting + TargetedReview

需要：

```text
正式 Targeted Prompt identity
Targeted Config
确定性 family/focus/strategy 路由
最多一次 TargetedReview
Targeted 新完整结果所有权
医学增益和不伤害证明
```

### R1 Retry

在相同冻结请求上增加受控 Physical Attempt。

### R2 Fallback

只允许切换到已经独立通过资格化的 Provider/Model。

### R3 Race

只按技术成功合同选择唯一 winner，不能让 Python 比较医学结论后选结果。

---

## 17. 工程 Gate、医学 Gate 与停止条件

### 17.1 工程 Gate

每个阶段至少要求：

```text
可重复执行
幂等键可追踪
事务内无网络 I/O
冻结输入可重放
敏感信息不落库/日志/Snapshot
Attempt/Stage/Task 状态一致
unknown 可恢复
取消和迟到结果不覆盖终态
```

### 17.2 医学 Gate

```text
Python 不改写 medical_status
没有可信 Gold 不讨论准确率放行
没有 paired A/B 不宣称 Prompt 更好
没有 holdout 不宣称医学发布
Targeted 必须证明有增益且不伤害 Primary
```

### 17.3 停止条件

任一情况出现即停止扩大范围：

```text
数据库基线不可信
Task Snapshot 不完整
签名 URL 泄露或越权
Provider Secret 泄露
Provider Request ID 缺失
Schema 校验失败
unknown 无法查询又可能重复发送
同一任务状态链无法追踪
医学 Gold 不可信
```

### 17.4 回滚单位

```text
Prompt version
AI Config version
ModelPool version
Connection version
Pipeline profile/version
单个代码切片
单个经授权的数据库迁移
```

禁止把多种医学变量、Provider 变量和状态机变量混进同一个不可回滚发布。

---

## 18. 推荐的下一步执行顺序

严格保持：

```text
P0 Database Baseline
-> P1 Worker Runtime Security Qualification
-> E1 Primary-only Runtime
-> M1 Primary Medical Baseline
-> Q3 Primary Prompt Paired A/B
-> Q4 Second Provider Qualification + Model A/B
-> M2 FamilyRouting + TargetedReview
-> R1 Retry
-> R2 Fallback
-> R3 Race
```

Prompt 专项当前应做：

1. 保持 `ms-image.x-ray.primary.common.zh-CN` 为唯一 Primary identity；
2. 不拆猫、犬 Prompt；物种来自冻结宠物事实；
3. 核对旧 20 个资产中的有效医学规则是否已进入 Primary/Targeted 两份完整 Prompt；
4. 在 E1/M1 前不发布 Targeted Prompt；
5. 单独设计并版本化收紧 `complete_medical_result` 嵌套 Schema；
6. 不为 Retry、Fallback、Race 创建新 Prompt。

---

## 19. 当前最终状态

```text
CODE_IMPLEMENTED:
  XRay Primary Prompt：YES
  Prompt import/render/message/gateway 基础代码：YES
  XRay Primary Stage：YES
  TargetedReview Stage 骨架：YES
  TargetedReview 本地 Prompt 候选：YES
  Attempt Image Signer：YES
  unknown reconcile 合同：YES
  Report/Evaluation 工程结构：YES

RUNTIME_QUALIFIED:
  Core AI network chain：PASSED
  Formal Worker complete chain：NOT RUN
  Real OSS Attempt signing chain：NOT RUN
  Provider response minimization in formal Worker chain：NOT RUN
  TargetedReview runtime：NOT RUN
  Retry/Fallback/Race：NOT RUN

MEDICALLY_VALIDATED:
  Primary：UNKNOWN
  TargetedReview：UNKNOWN
  Second Provider/Model：UNKNOWN

MEDICAL_RELEASE:
  NO-GO
```

---

## 20. 关键代码索引

### Runtime API / Service

```text
apps/backend/services/runtime/api/api_v1/endpoints/
apps/backend/services/runtime/service/session_service.py
apps/backend/services/runtime/service/study_service.py
apps/backend/services/runtime/service/image_service.py
apps/backend/services/runtime/service/task_service.py
apps/backend/services/runtime/service/imaging_execution_service.py
apps/backend/services/runtime/service/ai_request_service.py
apps/backend/services/runtime/service/ai_attempt_reconcile_service.py
apps/backend/services/runtime/service/report_service.py
```

### Pipeline / Stage

```text
apps/backend/core/pipeline.py
apps/backend/services/runtime/stages/registry.py
apps/backend/services/runtime/stages/xray/joint_primary_reader.py
apps/backend/services/runtime/stages/xray/family_routing.py
apps/backend/services/runtime/stages/xray/targeted_review.py
apps/backend/services/runtime/stages/xray/prompt_commands.py
apps/backend/services/runtime/stages/common/decision_finalization.py
```

### AI Control Plane

```text
apps/backend/services/ai_control/service/prompt_source.py
apps/backend/services/ai_control/service/prompt_import_service.py
apps/backend/services/ai_control/service/prompt_template_service.py
apps/backend/services/ai_control/service/api_connection_service.py
apps/backend/services/ai_control/service/model_pool_service.py
apps/backend/services/ai_control/service/config_compiler.py
apps/backend/services/ai_control/service/ai_config_service.py
```

### Gateway / OSS / Attempt

```text
apps/backend/core/ai/gateway/contracts.py
apps/backend/core/ai/gateway/image_signer.py
apps/backend/core/ai/gateway/attempt_lookup.py
apps/backend/core/ai/gateway_client.py
apps/backend/core/imaging/object_store.py
apps/backend/models/ai_call.py
apps/backend/models/ai_call_attempt.py
```

### Prompt / Schema

```text
prompts/xray/nacos/primary/common/zh-CN/
prompts/xray/nacos/targeted-review/common/zh-CN/
prompts/xray/catalog.zh-CN.json
prompts/xray/complete_medical_result.schema.json
prompts/xray/offline_evaluation_failure_analysis.zh-CN.txt
apps/backend/core/ai/prompting/
```

### Evaluation

```text
apps/backend/services/evaluation_control/
apps/backend/models/evaluation.py
apps/backend/crud/evaluation.py
apps/backend/schemas/evaluation.py
apps/backend/schemas/evaluation_execution.py
apps/backend/schemas/evaluation_export.py
apps/backend/schemas/evaluation_pairing.py
```
