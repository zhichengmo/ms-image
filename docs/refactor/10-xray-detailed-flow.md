# MS-Image XRay（X 光）详细链路与开发流程图

状态：`CURRENT_REFACTOR_VIEW / DESIGNED_NOT_IMPLEMENTED`（当前重构视图/已设计尚未实现）
更新日期：2026-08-18
适用范围：XRay（X 光）首期重构、代码评审、联调、故障定位和团队讲解。
精确字段、状态候选值和不变量以[设计母文第 6、8、15、16 章](../ms-image-final-architecture-and-database-design.md)为准。

本文把分散在设计母文中的 XRay（X 光）链路集中成开发视图，不建立第二套字段权威。图中的目标
Service（业务服务）、Stage Service（阶段服务）和目标表当前尚未完整实现；不能把 `PROPOSED`（候选设计）
写成线上运行事实。

## 1. 先给结论

首期默认生产候选只有一条最短医学链：

```text
StudyPreparation（检查准备）
-> XRayJointPrimaryReader（X 光联合主读，一次视觉调用）
-> DecisionFinalization（决策定稿，不调用模型、不改判）
-> Report（报告）
```

`FamilyRouting + TargetedReview`（家族路由 + 专项复核）是完整的实验候选，不是默认生产步骤。
它只有在冻结同病例 Paired A/B（配对对照实验）通过后，才允许从 `validation_only/shadow`
（仅验证/影子运行）申请 Gray/Active（灰度/正式激活）。人工复核当前不在链路中。

采用 `existing-entry internal modular refactor`（保留入口的内部模块化重构）：内部代码、目录、类和
Worker（异步工作进程）
可以完全替换，但保留或受控迁移外部入口、唯一事实 owner（所有者）、Outbox（事务发件箱）、CAS
（比较并设置）、lease（租约）、可回滚发布和配对评测合同。完全重写内部实现不等于同时建设第二套
API（应用程序接口）、
Runner（执行器）、数据库事实源或评分器。

## 2. Canonical XRay Chain（X 光权威端到端总链）

```mermaid
flowchart TD
    CP["ControlPlane（控制面）<br/>AIConfig、Prompt、模型资格、冻结 Profile"]
    S["SessionService（会话服务）"]
    ST["StudyService（检查服务）<br/>Study、Series、Revision、完整性"]
    IM["ImageService（影像服务）<br/>OSS 上传、服务端校验、替换、隔离"]
    T["TaskService（任务服务）<br/>冻结请求、Config、Profile、预算"]
    EX["ImagingExecutionService（执行服务）<br/>Stage、Checkpoint、Lease、CAS、恢复"]

    subgraph XR["XRay Pipeline（X 光流水线）"]
        SP["StudyPreparationStage（检查准备）"]
        PR["JointPrimaryReaderStage（完整 Study 联合主读）"]
        FR["FamilyRoutingStage（家族路由）<br/>仅 Targeted 实验 Profile"]
        TR["TargetedReviewStage（专项复核）<br/>最多一次视觉调用"]
        DF["DecisionFinalizationStage（结果定稿）<br/>不调用模型、不改判"]

        SP --> PR
        PR -->|"xray_primary_v1"| DF
        PR -->|"xray_targeted_review_v1"| FR
        FR -->|"primary_final"| DF
        FR -->|"targeted_review"| TR
        TR -->|"成功且输出完整病例结果"| DF
    end

    R["ReportService（报告服务）<br/>不可变报告、发布、作废、授权查询"]
    TF["failed/dead_letter<br/>medical=not_produced"]
    CF["completed<br/>medical=not_produced<br/>调用前覆盖/能力/预算不足"]
    OUT["normal / abnormal / review_required / non_diagnostic"]
    EV["EvaluationPlane（离线评测面）<br/>Gold、Failure Bank、Paired A/B、Holdout"]

    CP -. "冻结配置快照" .-> T
    S --> ST --> IM
    IM -->|"服务端校验后形成 ready revision"| ST
    ST --> T --> EX --> SP

    SP -->|"输入或传输失败"| TF
    SP -->|"调用前覆盖不足"| CF
    PR -->|"Provider 或 Schema 失败"| TF
    TR -->|"不可恢复工程失败"| TF

    DF --> R --> OUT
    R -. "脱敏冻结运行产物" .-> EV
    EV -. "候选证据 + 人工审批" .-> CP
```

本图是当前 Canonical Chain（权威主链）。后文流程图只能展开它的上传、事务、调用和恢复细节，不能改变两个 Profile 的分支、Final owner（最终结果所有者）或失败语义。

图中每个节点的目的、存在理由、输入、处理逻辑、输出、落表、失败语义、禁止职责和删除影响，集中见[Canonical XRay Chain 逐层目的与责任合同](12-canonical-xray-layer-responsibility-contract.md)。

这张图包含四个不同责任面，不能合并成一个“大 Service”：

| 责任面 | 解决的问题 | 为什么必须独立 |
|---|---|---|
| Control Plane（控制面） | 哪个 Prompt、Schema、模型和固定 Profile 有资格执行 | 只接收 Evaluation Plane 的候选证据，必须经人工审批；发布选择不能由普通诊断请求或 Worker 临时决定 |
| Imaging Ingress（影像接入面） | 模型实际看到了哪些可信原图和哪个 Study revision | OSS 上传成功不等于影像完整、格式可信或检查可诊断 |
| Reliable Execution（可靠执行面） | 重复消息、崩溃、租约过期和结果未知如何恢复 | 工程完成与医学正确是两类状态，不能靠一次同步 API 调用混在一起 |
| Medical Pipeline（医学流水线） | 哪个模型输出拥有医学结论，如何生成唯一 Report | Python 路由、持久化和渲染不得成为第二医学判断者 |

## 3. 影像上传到 Study 就绪

```mermaid
sequenceDiagram
    autonumber
    participant U as vet-platform（上游）
    participant API as MS-Image API（接口层）
    participant S as Session/StudyService（会话/检查服务）
    participant I as ImageService（影像服务）
    participant DB as MySQL ms_image（在线数据库）
    participant G as ObjectStorageGateway（对象存储网关）
    participant OSS as OSS（对象存储）
    participant R as OutboxRelay（发件箱中继）
    participant W as ImageValidationWorker（影像校验工作进程）

    U->>API: 创建 Session/Study/Series
    API->>S: 调用会话/检查业务用例
    S->>DB: 经实体 DAL/DalBase 保存业务事实
    U->>API: prepare upload（准备上传）
    API->>I: 可信身份 + study/series + expected metadata
    I->>DB: TX1 经 ImageDal 创建 image_record(uploading)
    I-->>U: 短期 direct PUT/multipart 凭证
    U->>OSS: 事务外直传 bytes
    U->>API: complete upload（完成上传）
    API->>I: 调用完成上传业务用例
    I->>G: 事务外完成上传和快速确认
    G->>OSS: multipart complete + HEAD
    I->>DB: TX2 经 ImageDal/OutboxDal 写 Image -> validating + Outbox(validate_image)
    R->>DB: 经 OutboxDal claim relay lease
    R->>W: 经 Broker 至少一次投递
    W->>I: claim Image validation lease/CAS
    I->>DB: TX3 经 ImageDal 保存 lease
    W->>I: 执行已领取的影像校验用例
    I->>G: 事务外读取对象流
    G->>OSS: stream verified object version
    OSS-->>G: bytes stream（字节流）
    G-->>I: 受控对象流和元数据
    I->>I: hash/格式/DICOM/像素/安全校验
    alt 校验通过
        W->>I: 提交 verified ObjectRef（已验证对象引用）
        I->>DB: TX4 经 ImageDal 将 Image -> ready
        I->>S: 请求重算 Series/Study manifest
        S->>DB: 经 StudyDal CAS 生成新 Study revision；完整时 -> ready
    else 校验失败或对象不一致
        W->>I: 提交稳定失败码和脱敏摘要
        I->>DB: 经 ImageDal 将 Image -> quarantined（已隔离）
        I->>S: 标记检查完整性冲突
        S->>DB: 经 StudyDal 保持非 ready 或进入 conflict（冲突）
    end
```

开发约束：

- MySQL 只保存对象引用、hash、大小、版本和状态，不保存影像 bytes，也不建设 `file_asset`（公共文件资产）表。
- 客户端声明和单次 OSS `HEAD` 都不能直接把 Image 推进为 `ready`（就绪）。
- 替换影像必须创建新 `image_record` 版本；新版本 ready 且 Study CAS 成功前，旧版本不能提前失效。
- 只有 Study revision 的必需 Series/Image 全部完整时，才允许创建诊断 Task（任务）。

## 4. Task 创建与可靠异步执行

```mermaid
sequenceDiagram
    autonumber
    participant U as vet-platform（上游）
    participant API as Task API（任务接口）
    participant T as TaskService（任务服务）
    participant DB as MySQL ms_image（在线数据库）
    participant R as OutboxRelay（发件箱中继）
    participant MQ as Broker（消息代理）
    participant W as ImagingWorker（影像工作进程）
    participant E as ImagingExecutionService（影像执行服务）

    U->>API: 创建诊断任务 request body
    API->>T: 可信 requester + ready study_revision_id + request_id
    T->>DB: 经 DAL 校验唯一 Active Config 和冻结 Study manifest
    T->>DB: TX1 经 DAL 创建 Task(pending) + first Stage(queued) + Outbox(pending)
    T-->>U: task_id（不等待 AI）

    R->>DB: TX2 经 OutboxDal CAS Outbox -> publishing + relay lease
    R->>MQ: 事务外 publish + publisher confirm
    R->>DB: TX3 经 OutboxDal 将 Outbox -> published
    MQ->>W: opaque stage event（不含影像/Prompt/Secret）
    W->>E: stage_checkpoint_id + expected version
    E->>DB: TX4 经 StageDal CAS Stage -> running + lease generation
    E->>E: 事务外执行已冻结 Stage handler
    alt Stage 成功且还有下一阶段
        E->>DB: TX5 经 DAL 原子写当前/下一 Stage + Outbox + Task CAS
    else 最终定稿成功
        E->>DB: TX6 经 DAL 原子写 Decision Stage + Report + Task current_report_id/终态
    else 可恢复技术失败
        E->>DB: 经 DAL 将 Stage/Task -> retry_wait + 恢复 Outbox
    else 不可恢复或超过 deadline
        E->>DB: 经 DAL 写 Stage failed + Task failed/dead_letter + medical not_produced
    end
```

`Outbox published`（发件箱已发布）只证明 Broker 接收过事件，不证明 Stage、Task 或 Report 已完成。
Broker 允许重复投递；真正的幂等边界是 aggregate version、Stage CAS、lease generation 和逻辑 AI Call 幂等键。

## 5. 默认 XRay 医学主链 `xray_primary_v1`

```mermaid
flowchart TD
    A["Stage 1: STUDY_PREPARATION（检查准备）<br/>冻结原图、revision、能力、预算和输入 hash"]
    B["Stage 2: XRAY_JOINT_PRIMARY_READER（X 光联合主读）<br/>一次读取完整检查，输出 CompleteMedicalResult"]
    C["Stage 3: DECISION_FINALIZATION（决策定稿）<br/>验证唯一 Primary owner 和来源；不调用模型、不改判"]
    D["ReportService（报告服务）<br/>原子创建不可变 Report 并切换 Task.current_report_id"]

    F1["execution=failed/dead_letter<br/>medical=not_produced<br/>不生成医学 Report"]
    F2["execution=completed<br/>medical=not_produced<br/>生成无医学结论的 technical report"]
    N["execution=completed<br/>medical=normal（正常）"]
    AB["execution=completed<br/>medical=abnormal（异常）"]
    RR["execution=completed<br/>medical=review_required（AI 无法确定）"]
    ND["execution=completed<br/>medical=non_diagnostic（医学不可诊断）"]

    A -->|"prepared"| B
    A -->|"输入、对象或传输失败"| F1
    A -->|"调用前覆盖/能力/预算不足"| F2
    B -->|"Provider、完整发送或 Schema 技术失败"| F1
    B -->|"Schema-valid 完整医学候选"| C --> D
    D -->|"模型结论原样 normal"| N
    D -->|"模型结论原样 abnormal"| AB
    D -->|"模型结论原样 review_required"| RR
    D -->|"模型结论原样 non_diagnostic + reason"| ND
```

### 5.1 三个 Stage 为什么存在

| Stage Service（阶段服务） | 输入 | 输出 | 医学 owner | 不能删除的理由 | 首期不继续拆分的理由 |
|---|---|---|---:|---|---|
| `StudyPreparationStageService`（检查准备阶段服务） | 冻结 Study revision、原图、Config、Provider 能力和预算 | 规范输入或稳定技术终态 | 否 | 不存在时无法证明模型看到的是完整、确定且允许发送的病例 | 影像组装、完整性、preflight 和预算都依赖同一冻结输入，拆开只增加恢复状态 |
| `XRayJointPrimaryReaderStageService`（X 光联合主读阶段服务） | 完整检查原图、最小临床上下文、冻结 Prompt/Schema | 完整病例 `CompleteMedicalResult`（完整医学结果） | 条件拥有；默认链中即 Final owner | 这是首期唯一医学判断来源 | 器官/系统/犬猫是输出维度和评测分层，不应默认变成多次相互相关的模型调用 |
| `DecisionFinalizationStageService`（决策定稿阶段服务） | 已 accepted（已接受）的唯一 Primary Stage/Call | `decision_finalized` 和来源选择 | 否 | 为默认链和候选分支提供同一唯一收口与事务不变量 | 它只校验和选择，不做医学规则、投票、阈值或报告渲染 |

`ReportService`（报告服务）是业务 Service，不是医学 Stage。它保存、发布、作废和授权查询 Report，
但不得增加、删除、合并或改写模型 Finding（影像发现）。

## 6. 实验性专项链 `xray_targeted_review_v1`

```mermaid
flowchart TD
    P["STUDY_PREPARATION（检查准备）"]
    R["XRAY_JOINT_PRIMARY_READER（X 光联合主读）<br/>所有病例先产生同一 Primary 输出"]
    FR["XRAY_FAMILY_ROUTING（X 光家族路由）<br/>确定性、零模型调用、冻结规则"]
    TR["XRAY_TARGETED_REVIEW（X 光专项复核）<br/>最多一次视觉调用，输出完整病例结果"]
    DF1["DECISION_FINALIZATION（决策定稿）<br/>选择 Primary owner"]
    DF2["DECISION_FINALIZATION（决策定稿）<br/>选择 Targeted owner"]
    RP["ReportService（报告服务）"]
    TF["技术失败<br/>execution=failed/dead_letter<br/>medical=not_produced"]

    P --> R --> FR
    FR -->|"primary_final（证据充分）"| DF1 --> RP
    FR -->|"targeted_review（疑点/冲突/预注册高风险）"| TR
    TR -->|"成功且完整"| DF2 --> RP
    TR -->|"Provider/Schema/完整发送失败"| TF
```

这条候选链必须同时遵守：

1. Family（家族）是报告结构、失败归因和评测 strata（分层），不是一张表或默认一次模型调用。
2. `FamilyRouting`（家族路由）只能输出白名单 `primary_final/targeted_review`，不能修改 normal/abnormal。
3. 每个病例最多选择一个家族进行一次 TargetedReview（专项复核），不能按器官并行多次投票。
4. TargetedReview 必须输出完整病例结果，不能把 Primary 与 Targeted 的有利片段拼接成 Final。
5. 已进入 TargetedReview 后若发生技术失败，必须以 `not_produced` 关闭；不能静默回退 Primary，避免选择性报告。
6. Router 规则、Targeted Prompt、模型、预算和 Schema 都是候选变量的一部分，评测前必须冻结。

## 7. 一次 XRay Provider 调用

```mermaid
sequenceDiagram
    autonumber
    participant E as ImagingExecutionService（执行服务）
    participant A as AIRequestService（AI 请求服务）
    participant DB as AICallDal/DalBase -> MySQL（AI 调用数据访问链）
    participant OSS as ObjectStorageGateway（对象存储网关）
    participant P as Provider（AI 服务提供方）

    E->>A: frozen Stage + image manifest + exact Config
    A->>DB: TX1 创建 prepared Call + 原子预留 Task 预算
    A->>OSS: 事务外读取并复核 hash/size/version（摘要/大小/版本）的完整原图
    A->>P: 事务外发送 Prompt + Schema + ordered images
    alt 收到明确响应
        P-->>A: actual_model + receipt + raw response
        A->>A: 解析并校验 Schema、完整发送和来源
        A->>DB: TX2 Call succeeded + disposition accepted/rejected + hash
        A-->>E: typed Stage result（类型化阶段结果）
    else timeout/断连且无法证明是否接收
        A->>DB: TX2 Call -> unknown + Outbox(reconcile)
        A->>P: 后续按原 idempotency key 查询/对账
    else 明确未发送或明确失败
        A->>DB: TX2 Call -> failed + 释放未消耗预算
    end
```

一个模型 Stage 可以产生 transport retry（传输重试）、format repair（格式修复）或 fallback（降级调用），
但每个逻辑 Provider 请求分别拥有 `ai_call_record`；最终只有一个满足冻结合同的 Call 可以成为 Stage 的
`accepted_call_id`。不能因为模型结论“不满意”而自动重问直到得到想要的答案。

## 8. 表与事务落点

```mermaid
flowchart LR
    S1["SessionService（会话服务）"] --> T1["session_record（会话记录表）"]
    S2["StudyService（检查服务）"] --> T2["study_record（检查记录表）"]
    S2 --> T3["series_record（序列记录表）"]
    S3["ImageService（影像服务）"] --> T4["image_record（影像记录表）"]
    S3 --> T7["outbox_record（事务发件箱记录表）"]
    S4["TaskService（任务服务）"] --> T5["task_record（任务记录表）"]
    S4 --> T6["stage_checkpoint_record（阶段检查点记录表）"]
    S4 --> T7
    S5["AIConfigService（AI 配置服务）"] --> T8["ai_config_record（AI 配置记录表）"]
    S6["AIRequestService（AI 请求服务）"] --> T9["ai_call_record（AI 调用记录表）"]
    S6 --> T7
    S7["ImagingExecutionService（执行服务）"] --> T5
    S7 --> T6
    S7 --> T7
    S7 --> T10["report_record（报告记录表）"]
    S8["ReportService（报告服务）"] --> T10
    S8 --> T5
```

| 原子边界 | 同一事务必须完成 | 事务外动作 | 失败时的事实 |
|---|---|---|---|
| 上传完成 | Image `validating` + `validate_image` Outbox | OSS multipart complete/HEAD | 可重试完成或隔离，不猜测 ready |
| Task 创建 | Task + first Stage + execute Outbox | 不调用 Broker/Provider | 三行全有或全无 |
| Outbox 投递 | claim 和结果分别使用短事务 | Broker publish + confirm | 允许重复发布，由消费端 CAS 去重 |
| Stage 领取 | Stage running + owner/lease generation | Stage 计算和外部 I/O | 旧 generation 永远不能回写新 owner |
| AI 调用准备 | Call prepared + Task 预算预留 | OSS 读取 + Provider 调用 | sent 后未知必须 reconcile，不新建调用掩盖 |
| Stage 推进 | 当前 Stage/Call + 下一 Stage + Outbox + Task CAS | 无 | 崩溃后从最后 completed Stage 恢复 |
| 最终完成 | Decision Stage + Report + Task 医学/工程状态/current pointer | Report 展示产物可后置 | 三者任一失败则全部回滚 |

所有实体写入仍必须经过 `XxxDal -> DalBase`（实体数据访问层 -> 数据访问基类），表访问图不授权
Service、API 或 Worker 直接拼 SQLAlchemy 查询。

## 9. 结果与失败必须分开表达

```mermaid
flowchart TD
    START["XRay Task（X 光任务）"]
    ENG["Engineering Path（工程路径）"]
    MED["Medical Path（医学路径）"]
    EF["failed/dead_letter + not_produced<br/>Provider/传输/Schema/恢复失败"]
    CF["completed + not_produced<br/>调用前覆盖/能力/预算不足"]
    MN["completed + normal（正常）"]
    MA["completed + abnormal（异常）"]
    MR["completed + review_required（AI 无法确定）"]
    MD["completed + non_diagnostic（医学不可诊断）"]

    START --> ENG
    ENG -->|"未产生模型医学结果"| EF
    ENG -->|"调用前覆盖终止"| CF
    ENG -->|"可靠完成模型链"| MED
    MED --> MN
    MED --> MA
    MED --> MR
    MED --> MD
```

| 场景 | `execution_status`（工程状态） | `ai_medical_status`（AI 医学状态） | Report（报告） |
|---|---|---|---|
| AI 正常完成 | `completed` | `normal/abnormal/non_diagnostic` | AI Report；`non_diagnostic` 必须有模型原因 |
| AI 无法确定 | `completed` | `review_required` | AI Report；当前不创建人审任务 |
| 调用前覆盖不足 | `completed` | `not_produced` | 无医学结论的 technical report（技术报告） |
| Provider/Targeted 技术失败 | `failed/dead_letter` | `not_produced` | 不生成医学 Report |
| 用户取消 | `cancelled` | `not_produced` | 不生成新的医学 Report |

以下等式全部错误：

```text
Outbox published != Stage completed
Stage completed != AI Call succeeded
AI Call succeeded != Schema passed
Schema passed != 医学准确
execution completed != medical normal
review_required != 人工已经复核
non_diagnostic != technical failure
Report final != Report published
```

## 10. 崩溃与恢复链

```mermaid
flowchart TD
    X["Worker/Relay/Provider 异常"]
    O{"Outbox relay lease 是否过期？"}
    S{"Stage lease 是否过期？"}
    C{"是否存在 sent/unknown AI Call？"}
    R1["重新 claim Outbox<br/>允许重复发布"]
    R2["新 lease generation 重领 Stage"]
    R3["按原 logical_call_key/idempotency_key<br/>先查 Provider 和 reconcile"]
    R4["恢复已 accepted Call 对应 Stage<br/>或补唯一下一事件"]
    STOP["超过 deadline/不可证明<br/>技术失败 + not_produced"]

    X --> O
    O -->|"是"| R1
    O -->|"否/已发布"| S
    S -->|"否"| R4
    S -->|"是"| C
    C -->|"否"| R2
    C -->|"是"| R3
    R3 -->|"查到原结果"| R4
    R3 -->|"明确未接收且支持幂等"| R2
    R3 -->|"到期仍未知"| STOP
```

恢复永远从数据库事实开始，不从 Worker 内存、Celery 是否显示成功或“模型大概没收到”开始。Task 已终态后
Provider 才返回的结果只记为 `late/ignored`（迟到/忽略），不能覆盖已发布 Report。

## 11. 默认链与候选链的公平比较

| 比较项 | Control：`xray_primary_v1` | Candidate：`xray_targeted_review_v1` |
|---|---|---|
| Study/图像/顺序 | 冻结相同 | 冻结相同 |
| Primary Prompt/Schema/模型/Provider | 冻结相同 | 冻结相同 |
| Primary 输出 | 保存 | 必须复用同一病例 Primary 输出合同 |
| 新增变量 | 无 | 冻结 Router + 最多一次 TargetedReview 的完整策略 |
| Final owner | Primary | 未路由时 Primary；路由且成功时 Targeted |
| Targeted 技术失败 | N/A（不适用） | 技术失败，不静默回退 Primary |
| 运行资格 | Control baseline（对照基线） | `validation_only/shadow`，通过门禁前不可生产 |

候选必须作为 `chain-only candidate`（仅链路候选）整体评测。不能运行后修改路由阈值、挑选有利病例、
更换 Primary 模型或更换 scorer（评分器），否则实验不是单变量，无法证明新增链路提高准确率。

## 12. 开发实现顺序

```mermaid
flowchart LR
    P0["P0 基线与阻断<br/>Secret/事务外 I/O/Trace/启动合同"]
    P1["P1 影像事实<br/>P1A 分层 + P1B API + P1C validate Outbox/Worker"]
    P2["P2 可靠任务<br/>复用 Outbox 扩展 Task/Stage/Call + lease/CAS"]
    P3["P3 零模型链<br/>Registry/Profile/Preparation/Finalization"]
    P4["P4 Primary AI<br/>AIConfig/AIRequest/JointPrimaryReader"]
    P5["P5 Report 闭环<br/>Final/Publish/Query/Cancel"]
    P6["P6 兼容与迁移<br/>Shadow/Gray/Rollback"]
    P7["P7 医学评测<br/>Paired A/B/Holdout/Release Gate"]

    P0 --> P1 --> P2 --> P3 --> P4 --> P5 --> P6 --> P7
```

默认第一个代码阶段按 P1A -> P1B -> P1C 实现公共影像事实、API 和 OSS 异步校验合同，不同时接入
医学 Provider。`Image uploading -> validating + Outbox(validate_image)` 属于 P1C；P2 复用同一
Outbox/Relay 扩展任务执行。每个 Phase（阶段）通过自己的工程门禁后再进入下一阶段。没有迁移、
真实数据库和真实对象演练时，P1 只能标记
`CODE_IMPLEMENTED / NOT_MIGRATED / NOT_RUNTIME_VALIDATED`；业务测试、迁移脚本和真实数据库操作仍需分别授权。

## 13. 开发验收清单

### 13.1 影像输入

- [ ] Task 冻结的 Study revision、Image 顺序、对象版本、hash 和实际发送清单一致。
- [ ] OSS 外部 I/O 不在数据库事务中执行。
- [ ] Image 未经服务端流式校验不能进入 `ready`。
- [ ] 补图或替换只产生新 revision 和新 Task，不覆盖旧执行事实。

### 13.2 可靠执行

- [ ] Task + first Stage + Outbox 同事务创建。
- [ ] Relay 和 Worker 可处理至少一次重复消息。
- [ ] Stage claim、heartbeat 和完成均校验 owner、lease generation 和 state version。
- [ ] sent/unknown Call 先 reconcile，不能用新调用掩盖未知结果。

### 13.3 医学边界

- [ ] 默认 Profile 只有一次视觉调用。
- [ ] Primary 输出覆盖正常、异常、AI 无法确定和医学不可诊断，且 Finding 可追溯到源图。
- [ ] DecisionFinalization 和 Report 不修改医学结论。
- [ ] 技术失败、覆盖不足和医学不可诊断没有混用。
- [ ] FamilyRouting/TargetedReview 默认关闭，只在冻结实验中启用。

### 13.4 报告与发布

- [ ] selected Stage/Call、Report 内容和 Task 医学状态在一个事务中保持一致。
- [ ] `final`（已定稿）与 `published`（已发布）权限语义不同。
- [ ] `review_required` 是合法 AI 终态，不自动创建人工复核。
- [ ] 旧 V2 fallback 结果不复制为新服务医学事实。

## 14. 本文没有决定什么

- 不复制十张在线表和四张评测表的完整字段；字段只以设计母文为准。
- 不宣称 GPT-5.6 Sol、Gemini 3.7 Flash 或任何模型已经通过医学准确率门禁。
- 不宣称 TargetedReview 比 Primary-only 更准确；它仍是待证伪/证实的实验假设。
- 不授权生成 Alembic（数据库迁移）、测试脚本或操作真实数据库。
- 不引入人工复核、任意可拖拽 DAG（有向无环图）或每 Stage 网络微服务化。
