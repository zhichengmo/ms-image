# MS-Image XRay Primary 主链未完成功能清单

状态：`CURRENT_PRIMARY_CHAIN_EXECUTION_CHECKLIST`

更新日期：2026-08-27

适用工作区：`/Users/mozhicheng/workspace/code/cy-code/ms-image`

## 1. 先说结论

### 1.1 Primary Prompt 已完成，不再缺 Prompt 正文

当前 Primary-only 主链只需要这一份 Runtime Prompt：

```text
prompt_key: xray_primary
variant: common
locale: zh-CN
dataId: ms-image.x-ray.primary.common.zh-CN
version: 1.0.0
```

已经完成：

- 本地 canonical Prompt 文件已创建；
- 已发布到目标 Nacos namespace；
- 已回读核对正文 SHA、变量集合和输出 Schema；
- 猫/犬通过冻结的 `species=cat|dog` 传入同一 Prompt，不拆两个 Prompt；
- Worker 只用冻结 Config/Task Snapshot，不读 Nacos latest。

所以当前结论是：

```text
Primary Prompt 创建：DONE
Primary Prompt Nacos 发布：DONE
Primary Prompt 正文缺失：NO
```

**现在缺的是：把已发布 Prompt 导入控制面、建立并激活 Config，再用一个真实冻结 Task 跑完整 Worker 主链。**

### 1.2 当前状态

```text
唯一真实通过：MS_IMAGE_CORE_AI_NETWORK_CHAIN_PASSED

CODE_IMPLEMENTED：Primary 主链主要代码基础已存在
RUNTIME_QUALIFIED：NOT RUN
MEDICALLY_VALIDATED：UNKNOWN
MEDICAL_RELEASE：NO-GO
```

基础网络 smoke 已证明：

```text
Nacos Prompt
-> Prompt render/message assembly
-> GatewayClient
-> ms-ai-platform
-> Provider
-> strict JSON Schema
-> Provider Request ID
```

它尚未证明同一任务的：

```text
MySQL -> Outbox -> Broker -> Worker -> OSS
-> Provider -> Attempt -> Stage -> Report
```

---

## 2. 本清单只包含当前 Primary 主链

```text
上游病例/宠物事实
-> Session
-> Study
-> Series
-> Image/OSS
-> ready Study Revision
-> Primary Prompt/Connection/ModelPool/Config
-> frozen Task Snapshot
-> Outbox
-> Broker
-> Worker
-> Attempt Image Signer
-> GatewayClient/ms-ai-platform/Provider
-> AI Call Attempt
-> JointPrimaryReader
-> DecisionFinalization
-> Report
```

以下能力放在 Primary 主链真实通过以后，不混入本轮：

```text
M1 医学基线
Q3 Prompt A/B
Q4 第二 Provider/Model A/B
M2 FamilyRouting/TargetedReview
R1 Retry
R2 Fallback
R3 Race
非 XRay modality AI Runtime
```

---

## 3. 还剩多少工作

按实际性质分为三类：

```text
A. 真正可能缺代码：2 项
B. 代码已有，但缺控制面数据/上游接线：3 项
C. 代码和接线基础已有，但缺真实运行资格证据：5 项
```

总计按执行单元整理为 **10 项**：

| # | 未完成项 | 类型 | 是否阻塞 |
|---|---|---|---|
| 1 | 数据库基线最终复核 | C | 阻塞真实运行 |
| 2 | Prompt/Connection/ModelPool/Config 正式数据 | B | 阻塞 Task 创建 |
| 3 | 上游宠物档案到 `species` 的真实接线 | B | 阻塞完整产品链；手工 E1 可先跑 |
| 4 | 同一真实 XRay Study/Series/Image/OSS 数据 | B/C | 阻塞 Task 创建 |
| 5 | 冻结 Task Snapshot 与首个 Outbox 实例 | C | 阻塞 Worker |
| 6 | 正式 Worker/Relay/Reconcile 配置与启动 | C；必要时 A | 阻塞 Worker |
| 7 | Outbox -> Broker -> Worker 真实投递 | C | 阻塞 Stage 执行 |
| 8 | OSS 签图 -> Platform/Provider -> Attempt | C | 阻塞 AI 结果 |
| 9 | Stage -> DecisionFinalization -> Report | C | 阻塞主链完成 |
| 10 | duplicate/cancel/unknown/late-result 与证据包 | A/C | 阻塞 Runtime 资格化 |

真正可能需要新增代码的只有：

1. 如果 `ms-ai-platform` / Provider 提供原请求查询能力，需要补正式 `ProviderAttemptLookup`；
2. 如果当前部署方式无法稳定启动 Worker、Outbox Relay、Reconcile，才补最小启动配置。

其余大部分不是缺类、缺表或缺 Prompt，而是现有代码还没有被正式数据和同一个真实 Task 串起来。

---

## 4. 逐项待办

### 4.1 数据库基线最终复核

**已有**

- 当前 Model 注册对应的 20 张 Runtime 表已存在；
- 当前业务表为空；
- 当前库标记 `alembic_version=20260824_02`。

**还缺**

- 只读确认 API、Worker、Relay 使用同一目标库；
- 只读确认 Model 表、关键字段和索引没有漂移；
- 尚未证明从零 Alembic replay，但这不应在未授权时直接执行。

**执行**

```text
读取实际连接目标
-> 对比 Model metadata 与物理表
-> 输出缺表/多表/缺列清单
-> 不执行 DDL
```

**验收**

```text
model_missing=[]
关键 Runtime 表可正常读写
API/Worker/Relay 指向同一数据库
```

**停止条件**：发现必须改表、迁移或删除表时先停止并单独申请授权。

**新增表/字段/迁移**：不需要。

---

### 4.2 建立正式控制面数据

**已有**

- Primary canonical Prompt 已发布；
- Prompt import、Connection、ModelPool、Config compile/activate 代码存在；
- Task 创建会查找 active Config：`apps/backend/services/runtime/service/task_service.py:102-113`。

**还缺**

当前空业务库中还没有：

```text
导入后的 xray_primary/common@1.0.0 Prompt
AI Connection
单 lane ModelPool
active xray_diagnose Config
```

**执行**

```text
Nacos 精确读取 common@1.0.0
-> PromptImportService 导入
-> 创建 Connection
-> 创建单 lane ModelPool
-> 编译 xray_diagnose/global/global Config
-> 激活并回读
```

**验收**

```text
Prompt identity/version/SHA 与 Nacos 一致
Config status=active
profile_key=xray_primary_v1
provider_disabled=false
Prompt/Schema/Model/Pipeline 哈希完整
```

**停止条件**：Prompt 变量、Schema、模型能力或 Config fingerprint 不一致时不创建 Task。

**新增代码/表/迁移/Service**：原则上都不需要，复用现有控制面 Service。

---

### 4.3 上游宠物档案到 `species` 的真实接线

**已有**

- `diagnose` Task 必传 `species=cat|dog`：`apps/backend/schemas/task.py:9-45`；
- Task 会冻结 species：`apps/backend/services/runtime/service/task_service.py:358-399`；
- Prompt 从 Snapshot 获取 species：`apps/backend/services/runtime/stages/xray/prompt_commands.py:155-170`。

**还缺**

上游尚未真实证明：

```text
session_id
-> medical_record
-> pet_profile
-> cat/dog
-> POST /tasks species
```

**执行原则**

- 第一次 E1 可用已知病例明确传 `cat` 或 `dog`；
- 完整产品链由上游查宠物档案后传参；
- Worker 永远不回查 latest 宠物档案。

**验收**

```text
Task request species 与 pet_profile 一致
Snapshot species 与 request_sha256 一致
Worker 没有档案查询
```

**停止条件**：species 缺失、不是 cat/dog 或与档案冲突时拒绝创建诊断 Task。

**修改 ms-image 表/迁移**：不需要。

---

### 4.4 建立一条真实 XRay 影像输入

**已有**

Session/Study/Series/Image、OSS 上传确认、Study revision/manifest 代码存在；OSS synthetic PUT/HEAD/GET 有局部证据。

**还缺**

没有一条供正式 Primary Worker 使用的同一真实冻结检查。

**执行**

```text
创建 Session
-> 创建 XRay Study
-> 创建 Series
-> 上传并 confirm Image
-> finalize Study
-> 得到 ready revision + resolved_manifest_sha256
```

**验收**

```text
Study status=ready
revision_id 固定
Image status=ready
object_key/version/sha256/size/content_type 完整
Series manifest 与 Study resolved manifest 一致
```

**停止条件**：对象缺失、哈希/尺寸不符、manifest 漂移或格式不允许时不创建 Task。

**新增代码/表/迁移**：不需要。

---

### 4.5 创建冻结 Task Snapshot 与首个 Outbox

**已有**

TaskService 已设计为在同一数据库事务中创建：

```text
Task
首个 StageCheckpoint
execute_stage Outbox event
```

并冻结：

```text
species
study revision/manifest
series manifests/counts
Config identity/hash/release fingerprint
Prompt/Model/Schema/Pipeline hashes
```

代码证据：`apps/backend/services/runtime/service/task_service.py:81-260,358-414`。

**还缺**

没有基于正式 active Config 和真实 ready Study 的持久化实例。

**执行与验收**

```text
创建 diagnose Task
-> Task execution_status=queued
-> first Stage=study_preparation
-> Outbox publish_status=pending
-> Snapshot/request_sha256 可重算
-> Snapshot 不含 API Key、签名 URL、Nacos latest
```

再用同一幂等请求重复一次，应返回同一 Task；改变 species 或 revision 时必须失败关闭。

**新增代码/表/迁移**：不需要。

---

### 4.6 正式 Worker、Relay、Reconcile 配置与启动

**已有**

AI 请求只使用现有：

```text
AI_PLATFORM_OPENAI_BASE_URL
AI_PLATFORM_API_KEY
```

两者成对校验：`apps/backend/core/config.py:228-280`；Gateway 直接读取并调用 Platform：`apps/backend/core/ai/gateway_client.py:21-108`。

**还缺**

- 未证明正式 Worker 启动器实际加载了这对配置；
- 未证明 Worker、Relay、Reconcile 与 API 指向同一 DB/Broker；
- 未形成 `ms-ai-platform` 常驻运行证据。

**执行**

```text
启动 ms-ai-platform
启动 imaging Celery Worker
启动 Outbox Relay
启动 Reconcile 入口
只确认配置存在，不打印 Secret 值
```

**验收**

```text
settings.ai_platform_configured=true
Worker/Relay/API 环境一致
日志无 API Key
DB/Nacos/Snapshot 无 API Key
进程重启后 pending 事件仍可恢复
```

**停止条件**：成对配置不完整、日志泄密、环境指错或 Platform 不可达时停止。

**新配置字段**：不需要；只注入现有配置值。

---

### 4.7 Outbox -> Broker -> Worker 真实投递

**已有**

- Outbox relay：`apps/backend/workers/imaging_worker/outbox_relay.py`；
- Celery Stage task：`apps/backend/workers/imaging_worker/celery_app.py:83-123`；
- Stage claim/lease/CAS：`apps/backend/services/runtime/service/imaging_execution_service.py:81-230`。

**还缺**

没有正式 AI Task 的同一事件投递和消费证据。

**执行与验收**

```text
Outbox pending -> publishing -> published
-> Broker 返回 message id
-> Worker 消费同一 event_id/trace_id
-> claim Stage lease
-> Task queued -> running
```

重复投递同一消息不能创建第二个有效 Stage/Call/Report。

**停止条件**：Outbox 与 Broker 状态不一致、消息 SHA 不一致或重复消息形成重复结果时停止。

**新增代码/表/迁移**：先运行验证，预期不需要。

---

### 4.8 OSS 签图 -> Platform/Provider -> Attempt

**已有**

- Signer 重验 object/version/hash/size/mime；
- 签名 URL 只允许 HTTPS、配置允许 host、30–900 秒 TTL；
- URL 对象明确不得持久化；
- Gateway 校验实际模型、严格 Schema 和 Provider Request ID；
- Provider 原始 body 不持久化，只保存 Schema-valid 结果、摘要和审计事实。

代码证据：

- `apps/backend/core/ai/gateway/image_signer.py:41-152`
- `apps/backend/core/ai/gateway/contracts.py:89-204`
- `apps/backend/services/runtime/service/ai_request_service.py:1120-1352`

**还缺**

本机 signed GET 不等于外部 Provider 可访问；尚无正式 Worker Attempt 同链证据。

**执行**

```text
prepare Call/Attempt
-> 提交事务
-> OSS HEAD + 短时签图
-> Provider 读取图片
-> Gateway 请求
-> Schema 校验
-> Attempt/Call winner finalize
```

**验收**

```text
URL host 在 allowlist，且只读、短 TTL
对象属于冻结 manifest
签名 URL 不进 DB/日志/Snapshot
provider_request_id 存在
actual_model 在冻结 allowlist
parsed_result_json 通过冻结 Schema
response_sha256 存在
response_object_ref_json 未写入
```

**停止条件**：Provider 无法读取图片、URL 越界、实际模型漂移、Schema 拒绝或 Provider Request ID 缺失时停止。

**恢复原始响应加密 OSS**：不需要，且不得恢复。

---

### 4.9 Stage -> DecisionFinalization -> Report

**已有**

- Primary Stage 入口存在；
- `DecisionFinalization` 只选择完整结果，不调用模型、不用 Python 改写医学结论：`apps/backend/services/runtime/stages/common/decision_finalization.py:13-41`；
- Report 有来源与内容 SHA 幂等校验：`apps/backend/services/runtime/service/report_service.py:37-108`。

**还缺**

没有同一正式 Task 的终态链证据。

**执行与验收**

```text
Attempt winner 唯一
-> JointPrimaryReader completed
-> DecisionFinalization completed
-> Report created
-> Task completed
```

必须证明：

```text
Primary complete_medical_result 与 Call parsed_result 一致
DecisionFinalization 未修改完整结果
Report source_call_id/source_stage_id 正确
Report content_sha256 可重算
Task.ai_medical_status 与 Report 一致
重复 finalize 返回同一 Report
```

**停止条件**：Stage/Call/Report 内容或来源不一致、Python 改判或产生多个有效 Report 时停止。

**新增代码/表/迁移**：先验证现有链，预期不需要。

---

### 4.10 恢复语义与非敏感证据包

这项不阻塞第一次看见 Report，但阻塞 `RUNTIME_QUALIFIED`。

#### duplicate delivery

同一消息重复到达，不得重复创建 Call、Attempt 或 Report。

#### cancel

```text
发送前取消：不得调用 Provider
发送后取消：迟到结果不得覆盖取消终态
```

#### unknown

```text
网络交付不确定
-> Attempt=unknown
-> 按原 provider_idempotency_key / Provider identity 查询
-> 未确认前禁止重发
```

当前真实 Provider lookup：`UNKNOWN`。`UnsupportedProviderAttemptLookup` 会安全等待对账，不会盲发，但仍缺 Provider 查询能力或有界人工终止方案：`apps/backend/core/ai/gateway/attempt_lookup.py:47-61`。

#### late result / winner CAS

已有 Winner、Task 取消或终态后到达的结果可以审计，但不得成为新 Winner 或改写 Report。

#### 同一 Task 证据包

至少收集：

```text
task_id/request_id/trace_id/request_sha256
study_revision_id/image_manifest_sha256
config_id/config_sha256/release_fingerprint
prompt_content_sha256/output_schema_sha256/compiled_pipeline_sha256
outbox event_id/event_key/broker message id
stage ids/status/version
ai_call_id/attempt_id/winner_attempt_id
provider_idempotency_key 摘要
provider_request_id 受控值或摘要
response_sha256
report_id/content_sha256/status
```

禁止进入证据包：

```text
AI_PLATFORM_API_KEY
OSS Access Key
完整签名 URL
Provider 原始响应正文
完整病例隐私正文
未脱敏 Prompt 输入
```

**停止条件**：unknown 只能靠盲发解决、迟到结果可覆盖 Winner/Report、重复消息产生重复医学结果或证据泄密时，不能声明 Runtime 资格化。

---

## 5. 最短执行顺序

```text
1. 只读复核 DB 和 Worker 配置
2. 导入已发布 Primary Prompt
3. 建立 Connection + 单 lane ModelPool
4. 编译并激活 xray_diagnose Config
5. 创建一个明确 cat 或 dog 的 ready XRay Study
6. 创建冻结 diagnose Task
7. 启动 Relay + Broker + Worker
8. 执行 OSS 签图 + Platform/Provider Attempt
9. 完成 Primary -> Finalization -> Report
10. 验证 duplicate/cancel/unknown/late-result 并收集证据包
```

最优先三项：

```text
P1. 建立 active Primary Config
P2. 建立一个真实 ready XRay Study/Revision
P3. 启动正式 Worker 并执行同一冻结 Task
```

如果这三项不做，继续新增 Prompt、Family、Targeted、Retry 或第二 Provider 都不会让当前主链更接近完成。

---

## 6. Primary 主链之后才做

| 顺序 | 能力 | 为什么现在不做 |
|---|---|---|
| M1 | Primary Medical Baseline | 先稳定 Runtime，才能区分工程失败和医学失败 |
| Q3 | Primary Prompt Paired A/B | 必须基于冻结 M1 Failure Bank，不能凭感觉改 Prompt |
| Q4 | Second Provider + Model A/B | 单 Provider 主链尚未资格化，先避免多变量 |
| M2 | FamilyRouting + TargetedReview | Targeted 候选已有，但未发布/接线，也没有医学收益证据 |
| R1 | Retry | unknown 未查询清楚前不能自动重发 |
| R2 | Fallback | 需要两个独立资格化候选 |
| R3 | Race | 需要预算、Winner CAS、迟到结果和成本护栏 |
| Schema v2 | 收紧嵌套结构 | 医学基线前版本化完成，不阻塞第一次技术 happy path |
| 非 XRay AI | CT/MRI/超声等 | 当前只有 modality 枚举，没有专用 Runtime |

---

## 7. 本轮明确不需要新增

```text
不需要新增 Primary Prompt
不需要按猫/犬拆 Primary Prompt
不需要新表、新字段或迁移脚本
不需要新 Repository、第二 CRUDBase 或 DatabaseService
不需要新微服务
不需要恢复 file_asset
不需要恢复旧 Gateway Secret Resolver
不需要恢复 Provider 原始响应加密 OSS
不需要现在发布 Targeted Prompt
```

---

## 8. 最终判定

### 已完成

```text
Primary canonical Prompt 本地资产：DONE
Primary Prompt Nacos 发布与回读：DONE
species 冻结合同：CODE DONE
Prompt render/message/Gateway 基础网络：PASSED
Primary Pipeline/Attempt/Report 代码基础：CODE DONE
```

### 主链仍未完成

```text
控制面正式数据：NOT DONE
真实 ready XRay Study：NOT RUN
冻结 Task/Outbox 实例：NOT RUN
正式 Relay/Broker/Worker：NOT RUN
Provider 读取真实 OSS 签图：NOT RUN
Attempt -> Stage -> Report 同链：NOT RUN
duplicate/cancel/unknown/late-result：NOT RUN / UNKNOWN
同一 Task 非敏感证据包：NOT COLLECTED
```

### 必须保持

```text
CODE_IMPLEMENTED：本轮只创建/修正文档；主链代码基础已存在
RUNTIME_QUALIFIED：NOT RUN
MEDICALLY_VALIDATED：UNKNOWN
MEDICAL_RELEASE：NO-GO
```
