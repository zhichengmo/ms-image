# Canonical XRay Chain（X 光权威主链）逐层目的与责任合同

状态：`CURRENT_LAYER_CONTRACT / P1_PARTIALLY_IMPLEMENTED / P2_PLUS_DESIGNED`（当前逐层合同/P1 部分代码已实现/P2 及后续已设计）

更新日期：2026-08-18

适用范围：架构评审、开发拆分、接口设计、联调定位、故障恢复和实验评测。

权威关系：本文解释 Canonical XRay Chain（X 光权威主链）中每一层为什么存在、如何工作和不能做什么；精确字段、索引、状态候选值和不变量仍以[设计母文](../ms-image-final-architecture-and-database-design.md)为准，完整时序以[XRay 详细链路](10-xray-detailed-flow.md)为准。

P1 的 SessionService（会话服务）、StudyService（检查服务）、ImageService（影像服务）、API、对象存储校验和 Image Outbox/Relay/Worker 已有代码实现，但未迁移且未做真实运行验证；Task、Execution、AI、Report、Evaluation 与所有目标 Stage Service（阶段服务）尚未完整实现。本文中 P2+ 的目标行为均为 `PROPOSED`（候选设计），不能写成线上运行事实。

## 1. 先明确“层”的判断标准

一个节点只有满足至少一个条件才值得独立存在：

1. 拥有独立业务事实或生命周期。
2. 拥有独立事务、幂等、恢复或权限边界。
3. 执行独立且可版本化的输入到输出转换。
4. 拥有独立失败语义，不能由相邻节点准确表达。
5. 它的边际价值可以通过工程验证或医学实验单独判断。

仅仅“代码比较多”“名称听起来重要”或“以后可能用到”不构成独立 Service/Stage 的理由。

## 2. 一张表看懂所有层

| 图中节点 | 类型 | 核心目的 | 是否医学判断者 | 主要事实落点 | 是否首期必需 |
|---|---|---|---:|---|---:|
| `ControlPlane`（控制面） | 治理面 | 决定哪些 Config/Profile/模型有资格被新 Task 使用 | 否 | `ai_config_record` + AuditSink（审计接收器） | 是 |
| `SessionService`（会话服务） | 业务事实层 | 记录一次影像诊疗业务的开始、关闭、取消和幂等根 | 否 | `session_record` | 是；业务闭环必需 |
| `StudyService`（检查服务） | 业务事实层 | 组织 Study/Series/revision 和完整性 | 否 | `study_record`、`series_record` | 是 |
| `ImageService`（影像服务） | 业务事实层 | 管理 OSS 上传、服务端校验、版本替换和隔离 | 否 | `image_record`、Image-owned `outbox_record` | 是 |
| `TaskService`（任务服务） | 业务事实层 | 冻结一次可重放诊断请求并原子启动首 Stage | 否 | `task_record`、首 `stage_checkpoint_record`、`outbox_record` | 是 |
| `ImagingExecutionService`（执行服务） | 可靠执行层 | 用 Checkpoint/Lease/CAS 推进、恢复和结束 Stage | 否 | Task/Stage/Outbox/Call/Report 协调事务 | 是 |
| `StudyPreparationStage`（检查准备阶段） | 公共 Stage | 把冻结 Study 转换为允许模型调用的规范输入 | 否 | `stage_checkpoint_record` | 是 |
| `JointPrimaryReaderStage`（联合主读阶段） | XRay 医学 Stage | 一次读取完整 Study，产生完整病例医学结果 | 是 | Stage output + `ai_call_record` | 是 |
| `FamilyRoutingStage`（家族路由阶段） | XRay 实验 Stage | 确定性判断 Primary 是否需要一次专项复核 | 否 | Stage route output | 仅 Targeted 实验 Profile |
| `TargetedReviewStage`（专项复核阶段） | XRay 实验医学 Stage | 针对一个家族做一次补充完整读片 | 条件是 | Stage output + `ai_call_record` | 仅 Targeted 实验 Profile |
| `DecisionFinalizationStage`（结果定稿阶段） | 公共 Stage | 校验并选择唯一 accepted medical owner（已接受医学所有者） | 否 | Stage output；随后进入最终原子事务 | 是 |
| `ReportService`（报告服务） | 业务事实层 | 保存不可变报告、发布、作废和授权查询 | 否 | `report_record`、Task current pointer（当前报告指针） | 是 |
| `TF`（工程失败终态） | 终态语义 | 表达执行链未能可靠产生医学结果 | 否 | Task/Stage/Call 失败事实 | 是 |
| `CF`（调用前覆盖终态） | 终态语义 | 表达系统正确决定不调用模型 | 否 | Task 完成 + technical report（技术报告） | 是 |
| `OUT`（医学输出） | 结果语义 | 对外提供被选医学 owner 的四类结果 | 来自模型 | Task + current Report | 是 |
| `EvaluationPlane`（离线评测面） | 证据面 | 判断候选是否提高准确率且不破坏安全护栏 | 否 | `ms_image_eval` + 不可变 Artifact（评测产物） | 医学发布前必需 |

## 3. ControlPlane（控制面）

### 3.1 目的与意义

Control Plane 解决“本次 Task 到底允许使用哪一套配置”的问题。模型、Prompt（提示词）、Schema（结构合同）、Profile（流程配置）、预算和资格如果在运行时临时选择，同一病例就无法重放，也无法公平比较实验结果。

### 3.2 功能逻辑

1. 接收候选 `AIConfig`（AI 配置）revision，而不是直接覆盖旧配置。
2. 校验 Prompt/Schema/模型/Provider（AI 服务提供方）能力、固定 Profile、预算和 handler（处理器）版本。
3. 校验 Provider 资格 Artifact、实验候选证据和人工审批事实。
4. 使用 Active Slot CAS（当前槽比较并设置）激活或回滚不可变 revision。
5. Task 创建时只提供冻结快照；Task 启动后不能热切换配置。

### 3.3 输入、输出与落点

- 输入：候选 Config、模型资格 Artifact、Evaluation 候选证据、人工审批。
- 输出：可引用的 `config_revision_id`、`profile_key/version`、release fingerprint（发布指纹）。
- 落点：`ai_config_record`；审批和发布动作进入 AuditSink，不把 Secret 明文写入数据库。

### 3.4 失败与禁止职责

- 资格、版本或审批不完整：拒绝激活；不能创建引用该配置的新 Task。
- 不执行离线评测，不读取 Holdout 调参，不运行医学 Stage。
- 不修改已启动 Task 的快照，不直接写医学 Report。

### 3.5 如果删除会发生什么

配置会退化成 Worker 临时读取环境变量或“当前最新值”，造成无法重放、实验变量混杂、回滚不确定和医学发布不可审计。因此该层必需，但不应扩大为通用配置中心。

## 4. SessionService（会话服务）

### 4.1 目的与意义

Session 是业务生命周期根，回答“这次影像诊疗从何时开始、包含哪些检查、何时关闭或取消”。它不直接提高模型准确率，但使调用请求、多个 Study/Task 和权限归属拥有稳定业务边界。

### 4.2 功能逻辑

1. 根据可信 identity（身份）、业务 request key（请求键）幂等创建 Session。
2. 维护 `open/closed/cancelled` 等字符串状态和 state version（状态版本）。
3. 校验资源 owner、scope（作用域）和关闭/取消状态转换。
4. 为 Study 提供稳定 `session_id`，但不复制宠物、用户或病历全文。

### 4.3 输入、输出与落点

- 输入：可信 requester、外部不透明业务引用、幂等键；旧 `vet-platform` 导入只通过离线迁移适配器提供来源引用。
- 输出：全局唯一 `session_id` 和当前生命周期状态。
- 落点：`session_record`。

### 4.4 失败与禁止职责

- 同一幂等键但 payload 不同：返回冲突。
- 已关闭/取消 Session 不允许新增不符合合同的 Study。
- 不上传文件、不组装影像、不创建 AI Config、不执行医学判断。

### 4.5 如果删除会发生什么

单个 Study 仍可能技术执行，但一次诊疗中的多检查、取消、权限和调用幂等会散落到 Study/Task，形成重复字段和模糊业务根。因此它是业务闭环节点，不是医学 Stage。

## 5. StudyService（检查服务）

### 5.1 目的与意义

Study 是医学检查边界，Series 是检查内的影像分组，revision 是模型实际看到的不可变检查版本。该层保证“补图、替换和顺序变化”不会覆盖已经执行的病例输入。

### 5.2 功能逻辑

1. 创建 Study 和 Series 计划，记录 modality（模态）、body scope（部位）和必需影像集合。
2. 只根据服务端验证通过的当前 Image version 重算 manifest（清单）、顺序和数量。
3. 使用 CAS 生成新 Study revision；任何补图或替换都产生新 revision。
4. 只有必需 Series/Image 完整且无冲突时，revision 才能进入 `ready`。
5. Task 只能冻结一个明确的 ready revision。

### 5.3 输入、输出与落点

- 输入：`session_id`、检查计划、Series 计划、已验证 Image 事实。
- 输出：`study_id`、`series_id`、ready `study_revision_id` 和冻结 manifest。
- 落点：`study_record`、`series_record`；Series 没有必要单独创建业务 Service。

### 5.4 失败与禁止职责

- 必需影像缺失：保持非 ready。
- 同一位置存在冲突版本或校验失败：进入 conflict（冲突）或保持不完整。
- 不把客户端数量声明当真相，不直接读取 OSS bytes，不作医学诊断。

### 5.5 如果删除会发生什么

Task 只能引用零散 Image，无法证明完整性、顺序和版本，也无法区分补图前后结果。模型调用即使成功，也不能证明读取了完整检查。

## 6. ImageService（影像服务）

### 6.1 目的与意义

ImageService 解决“OSS 中的对象是否真的是本业务拥有、格式正确、内容完整的影像”。上传成功只证明对象存储收到了 bytes，不证明对象可信或可诊断。

### 6.2 功能逻辑

1. `prepare_upload`（准备上传）：创建 `image_record(uploading)`，签发短期直传凭证。
2. 客户端事务外上传 bytes 到 OSS。
3. `complete_upload`（完成上传）：事务外完成 multipart/HEAD 快速确认。
4. 同一数据库事务写 `Image -> validating` 和 `Outbox(validate_image)`。
5. Worker 领取 lease 后事务外流式读取对象，校验 SHA256、大小、MIME、真实格式、DICOM/像素和安全边界。
6. 校验通过进入 `ready`；失败进入 `quarantined`（已隔离）。
7. 替换影像创建新 version；新版本 ready 且 Study revision CAS 成功后，旧版本才 superseded（已取代）。

### 6.3 输入、输出与落点

- 输入：可信 owner、Study/Series、预期元数据、OSS 对象流。
- 输出：verified ObjectRef（已验证对象引用）、hash、大小、格式、状态和 generation（代次）。
- 落点：`image_record` 和 Image-owned `outbox_record`；不建设公共 `file_asset`（文件资产）表。

### 6.4 失败与禁止职责

- 客户端 hash、signed URL、ETag 或单次 HEAD 不能单独推进 ready。
- OSS/Broker I/O 不得在数据库事务内。
- 不判断影像是否正常/异常；像素可读性检查不等于医学诊断。

### 6.5 如果删除或并入 StudyService 会发生什么

Study 生命周期与大对象上传/校验的事务、重试、隔离和版本边界会混在一起，API 可能在长事务中读取 OSS，故障恢复也无法独立定位。因此 ImageService 必须独立于 StudyService。

## 7. TaskService（任务服务）

### 7.1 目的与意义

Task 是一次诊断执行的不可变请求快照。它把“业务希望诊断什么”与“执行器此刻如何运行”分开，使同一 Study 可以用不同冻结 Profile 做可比较实验。

### 7.2 功能逻辑

1. 校验 requester 权限、Session/Study 状态和 ready revision。
2. 加载唯一 Active Config 并冻结 Profile、Prompt、Schema、模型、Provider、预算、deadline 和 release fingerprint。
3. 生成不可变 request snapshot（请求快照）和输入 manifest hash。
4. 在一个短事务中创建 Task、首 Stage checkpoint 和 execute Outbox。
5. 立即返回 `task_id`，不在 API 请求中等待 AI。
6. 处理取消意图和 Task 状态 CAS，但不直接执行 Stage。

### 7.3 输入、输出与落点

- 输入：ready `study_revision_id`、诊断类型、run mode（运行模式）、可信 requester、幂等键。
- 输出：冻结 `task_id`、首 `stage_checkpoint_id` 和待发布事件。
- 落点：`task_record`、首 `stage_checkpoint_record`、`outbox_record`。

### 7.4 失败与禁止职责

- Study 非 ready、Config 非 Active、预算不合法：Task 不启动。
- Task/Stage/Outbox 必须全有或全无。
- 不调用 Broker/Provider，不热切换配置，不在 endpoint 中同步跑医学链。

### 7.5 如果删除会发生什么

执行事实会直接挂到 Study 或 Session，导致一次检查只能有一个结果、实验配置无法并存、取消和预算没有 owner，也无法区分“输入事实”和“某次执行事实”。

## 8. ImagingExecutionService（影像执行服务）

### 8.1 目的与意义

该层解决异步系统最难的工程问题：重复消息、Worker 崩溃、lease 过期、迟到结果、unknown Provider Call 和断点恢复。它是流程运行 owner，不是医学结果 owner。

### 8.2 功能逻辑

1. 按 `stage_checkpoint_id + expected_version` 领取 Stage。
2. 使用 owner、lease generation 和 state version 做 CAS。
3. 通过 StageRegistry（阶段注册表）解析冻结 `handler_key/version`。
4. 在数据库事务外执行 handler、OSS、Broker 或 Provider I/O。
5. 成功时原子保存当前 Stage、下一 Stage、Outbox 和 Task 版本。
6. 可恢复失败进入 `retry_wait` 并创建恢复事件；不可恢复或超过 deadline 进入技术终态。
7. Finalization 成功时协调 ReportService，在一个短事务中保存 Stage/Report/Task current pointer。

### 8.3 输入、输出与落点

- 输入：不透明 Stage 事件、冻结 Task/Stage/Config、当前数据库版本。
- 输出：下一 Stage/Outbox、重试、恢复或 Task 终态。
- 落点：协调 `task_record`、`stage_checkpoint_record`、`outbox_record`、`ai_call_record` 和 `report_record`；自身不另建 execution 表。

### 8.4 失败与禁止职责

- 旧 lease generation 的结果永远不能覆盖新 owner。
- 重复/迟到事件必须幂等 ACK 或记录 `late/ignored`。
- sent/unknown Call 必须先 reconcile（对账），不能新建调用掩盖不确定性。
- 不改医学结论，不按“看起来更好”选择结果，不直接拼 SQL。

### 8.5 如果删除或改成通用 WorkflowService 会发生什么

执行语义会散落到 Worker 和各 Stage，导致每个阶段各写一套租约、重试和恢复。使用含糊的 WorkflowService 也容易把业务配置、医学判断和持久化全部吞进去。因此保留有明确影像执行责任的 ImagingExecutionService。

## 9. StudyPreparationStage（检查准备阶段）

### 9.1 目的与意义

Preparation 是模型调用前的最后确定性门禁，证明“本次模型将看到的输入”和 Task 冻结事实完全一致。它把工程输入问题挡在医学调用之前。

### 9.2 功能逻辑

1. 加载冻结 Study revision 和有序 Image manifest。
2. 校验 ObjectRef、hash、version、顺序和 `full_sent` 可满足性。
3. 校验物种、部位、投照覆盖、格式、Provider capability（能力）和泄漏规则。
4. 预留整条链的 deadline 和调用预算。
5. 生成规范 `PreparedStudy`（已准备检查）和 input hash。

### 9.3 输出与失败分流

- 通过：输出 `prepared`，进入 Primary。
- 对象缺失、hash/版本不一致、传输事实不可信：`failed/dead_letter + medical=not_produced`。
- 调用前覆盖、模型能力或预算明确不足：`completed + medical=not_produced`，可生成无医学结论的 technical report。

### 9.4 禁止职责与删除影响

- 不调用医学模型，不用 Python 判断正常/异常，不自动修图补图。
- 若删除，输入完整性检查会散落到 AIRequestService/Primary，工程失败和医学不可诊断会混淆，也无法证明模型实际看到什么。

## 10. JointPrimaryReaderStage（完整 Study 联合主读阶段）

### 10.1 目的与意义

Primary 是默认链唯一医学判断来源。一次发送完整 Study，要求模型同时检查正常与异常、覆盖所有可评估临床家族，并输出同一版本的完整病例 Schema。

### 10.2 功能逻辑

1. 使用冻结 Prompt、Schema、model、Provider 和有序完整原图。
2. AIRequestService 先创建 `prepared` Call 并预留预算，再在事务外发送。
3. 校验 actual model（实际模型）、receipt（回执）、完整发送清单、响应来源和 Schema。
4. 输出 `CompleteMedicalResult`，包括 `normal/abnormal/review_required/non_diagnostic`、Finding、source refs 和覆盖声明。
5. `xray_primary_v1` 中 Primary 是 Final owner；Targeted Profile 中它先作为候选 owner。

### 10.3 输入、输出与落点

- 输入：`PreparedStudy`、最小安全临床上下文、冻结 AI Config。
- 输出：完整医学候选，不是证据碎片或器官投票。
- 落点：`ai_call_record` + Stage output；医学结果不能由 Python 二次改写。

### 10.4 失败与禁止职责

- Provider/传输/完整发送/Schema 不可恢复失败：工程失败 + `not_produced`。
- 医学结果“不满意”不能触发自动 retry；只有运输或受控格式修复可按预算重试。
- 不按犬/猫、器官或系统拆成多次相关模型投票，否则调用次数增加但证据独立性没有增加。

### 10.5 为什么不能删除

没有 Primary 就没有统一对照基线，也无法判断 TargetedReview 的边际价值。Targeted 不能替代全病例 Primary，因为 Router 的输入本身来自 Primary。

## 11. FamilyRoutingStage（家族路由阶段，仅实验 Profile）

### 11.1 目的与意义

FamilyRouting 不负责诊断，只负责回答一个受限问题：“在冻结 Targeted Profile（专项复核流程配置）下，Primary 是否给出了唯一、可追溯、预注册的专项候选，且该专项覆盖、预算与实验资格都满足，值得花费一次专项视觉调用？”“高风险”不是单独触发条件；没有唯一 Family（家族）、Focus（关注点）和来源 Finding（影像发现）的泛化风险描述必须保持 Primary 定稿。

### 11.2 功能逻辑

1. 只读取 Schema-valid Primary 结果、StudyPreparation 的覆盖事实和冻结 Router config（路由配置）。
2. 只接受 Primary 输出的 `targeted_candidate`（专项候选）：唯一 `family_key`（专项键）、唯一 `focus_key`（关注键）、来源 Finding 和稳定 reason code（原因码）必须齐全。
3. 按冻结临床家族目录、白名单规则、required coverage（必需覆盖）、Provider capability（能力）、预算和 deadline（截止时间）计算 route reason（路由原因）。
4. 只能输出 `primary_final` 或 `targeted_review`；覆盖不足、多个候选、无预注册失败假设或预算不足都必须 `primary_final`，不能用 Targeted 掩盖输入不足。
5. 最多选择一个临床家族和一组冻结问题；不按 Finding 数量投票、不按 Python 阈值推断医学异常。
6. route output 连同目录/规则版本、输入摘要、覆盖证明和原因写入 Stage output。

### 11.3 输入、输出与落点

- 输入：完整 Primary 结果、StudyPreparation 覆盖事实、冻结临床家族目录、Router 规则版本、预留预算/deadline。
- 输出：一个确定性 route signal（路由信号）。
- 落点：`stage_checkpoint_record.output_json` 或大型不可变 Artifact 引用；不新增 Family 表。

### 11.4 失败与禁止职责

- 规则无法解析或输入 Schema 不匹配：候选链技术失败，不能偷偷走 Primary。
- 不读取原图、Gold 或 Holdout，不调用模型，不修改 `normal/abnormal`；不得从泛化高风险词、原始置信度或 Python 阈值自行创造专项候选。
- 不比较 Primary 与 Targeted 哪个“更好”，不选择多个家族并行调用。

### 11.5 是否可以删除

默认 `xray_primary_v1` 必须删除该节点，因为没有可选分支时 Router 没有实际价值。`xray_targeted_review_v1` 必须保留它，否则所有病例都会多调用一次模型，实验变量、成本和选择条件失去控制。

## 12. TargetedReviewStage（专项复核阶段，仅实验 Profile）

### 12.1 目的与意义

TargetedReview 是待验证的准确率杠杆：让模型在看到完整原图、完整 Primary 结果和一个冻结的 `family_key + focus_key`（专项键加关注键）问题后，再进行最多一次聚焦复核。它是否提高准确率是实验假设，不是既定事实。临床专项、Focus/Strategy、Prompt Bundle 和 Router 门禁见[XRay 专项完整设计](14-xray-specialty-design.md)。

### 12.2 功能逻辑

1. 只在 Router 输出 `targeted_review` 时创建 Stage instance（阶段实例）。
2. 读取完整原图，不只读取 crop（裁剪图）或 Primary 文字。
3. 使用独立冻结的 Targeted Prompt/Schema/模型配置和 Primary 完整结果。
4. 针对一个临床家族回答冻结问题，同时重新输出完整 `CompleteMedicalResult`。
5. 成功且结果完整时，Targeted 成为该分支唯一 Final owner。

### 12.3 输入、输出与落点

- 输入：完整原图、Primary 完整结果、一个 selected family（选定家族）、冻结问题清单和 Targeted Config。
- 输出：完整病例医学结果，不能只输出 evidence delta（证据增量）。
- 落点：独立 `ai_call_record` + Targeted Stage output。

### 12.4 失败与禁止职责

- 一旦触发后 Provider/Schema/完整发送失败：Task 技术失败 + `medical=not_produced`。
- 禁止静默回退 Primary，否则系统会只在 Targeted 有利时采用结果，形成选择性报告偏差。
- 不允许多家族并行、多 Reader 投票或无限重问。
- 不拼接 Primary 与 Targeted 的有利片段；Final owner 必须完整且唯一。

### 12.5 是否可以删除

可以关闭整个 Targeted Profile 并回到 Primary 基线，这是首选回滚方式。只有同病例 paired A/B 同时改善预注册主指标、正常误报和异常漏诊护栏，且独立 Holdout 通过后，才考虑晋级。

## 13. DecisionFinalizationStage（结果定稿阶段）

### 13.1 目的与意义

Finalization 不是“再读一次片”，而是统一默认链和实验链的结果所有权。它确保每条成功路径恰好选择一个完整、accepted、可追溯的医学 owner。

### 13.2 功能逻辑

1. `xray_primary_v1` 只允许选择 Primary。
2. Targeted Profile 的 `primary_final` 分支只允许选择 Primary。
3. Targeted Profile 的 `targeted_review` 分支只有 Targeted 成功且完整时才允许选择 Targeted。
4. 校验 selected Stage/Call、Schema、source refs、完整发送清单、result hash 和 owner 唯一性。
5. 输出 `decision_finalized` 和 selected source；随后由 ImagingExecutionService 协调 ReportService 原子持久化。

### 13.3 输入、输出与落点

- 输入：冻结 Profile 分支、accepted Stage/Call 和完整医学候选。
- 输出：唯一 selected owner/source，不生成新的医学内容。
- 落点：Finalization Stage output；Report/Task 在随后同一事务写入。

### 13.4 失败与禁止职责

- owner 不唯一、来源断裂、结果不完整或分支不匹配：技术失败，不能猜测 owner。
- 不调用模型、不投票、不设医学阈值、不做 fallback、不修改 Finding。

### 13.5 如果删除会发生什么

默认链可能由 Primary 自己写 Report，实验链又由 Targeted 写另一套 Report，形成两套完成逻辑和双医学事实源。Finalization 提供单一收口，因此应该保留但保持零医学逻辑。

## 14. ReportService（报告服务）

### 14.1 目的与意义

Report 是外部可查询的不可变医学结果版本。它把 Stage 内部产物转换为稳定发布事实，但不得成为第二医学判断层。

### 14.2 功能逻辑

1. 校验 selected owner/source 与 Task 冻结输入一致。
2. 创建不可变 `report_record` revision。
3. 与 Finalization Stage、Task 工程/医学状态和 `current_report_id` 在同一短事务保持一致。
4. 管理 `final/published/void`（已定稿/已发布/已作废）状态和授权查询。
5. 可异步生成展示/PDF 等派生产物，但派生产物不能反向修改规范结果。

### 14.3 输入、输出与落点

- 输入：Finalization selected source 和规范 `CompleteMedicalResult`。
- 输出：不可变 Report revision、current pointer 和查询结果。
- 落点：`report_record`、`task_record.current_report_id`。

### 14.4 失败与禁止职责

- Report/Task/Finalization 任一写入失败：整个最终事务回滚。
- 不新增、删除、合并或改写 Finding，不调用模型。
- 首期没有 callback/ack（回调/确认）生命周期，不另建 DeliveryService（交付服务）。

### 14.5 如果删除会发生什么

Task/Stage 内部 JSON 会直接成为外部合同，无法稳定版本化、作废和授权查询，也难以保留历史报告。因此 ReportService 必需，但渲染器不应拥有医学规则。

## 15. 三类终点为什么必须分开

### 15.1 TF：Engineering Failure（工程失败终态）

- 状态：`execution=failed/dead_letter`，`medical=not_produced`。
- 场景：对象/传输事实不可信、Provider/Schema 不可恢复失败、Targeted 触发后失败、恢复超过 deadline。
- 含义：系统没有可靠完成执行链，不能生成医学 Report。
- 价值：工程故障不会被误统计为模型的 normal/abnormal 错误。

### 15.2 CF：Pre-call Coverage Terminal（调用前覆盖终态）

- 状态：`execution=completed`，`medical=not_produced`。
- 场景：调用前已经确定投照覆盖、Provider 能力或预算不足。
- 含义：系统正确执行了“不应调用模型”的确定性政策，不是系统崩溃。
- 输出：可以生成无医学结论的 technical report，解释未生产医学结果的原因。

### 15.3 OUT：Medical Output（医学输出终态）

| 状态 | 中文含义 | 产生者 | 关键边界 |
|---|---|---|---|
| `normal` | 模型判断未见异常 | selected medical owner | 不等于“工程正常” |
| `abnormal` | 模型判断存在异常 | selected medical owner | 必须包含结构化 Finding/source refs |
| `review_required` | AI 无法确定 | selected medical owner | 首期不自动创建人工复核 |
| `non_diagnostic` | 模型判断影像医学上不可诊断 | selected medical owner | 必须带模型原因，不等于技术失败 |

这四种医学状态只能来自被选模型 owner；Python、Router、Finalization 和 Report 都不能相互转换。

## 16. EvaluationPlane（离线评测面）

### 16.1 目的与意义

Evaluation Plane 解决“候选链是否真的提高准确率”而不是“候选链能不能运行”。没有这一层，复杂链很容易因为报告更长、调用更多或个别病例变好而被误判为整体更准确。

### 16.2 功能逻辑

1. 接收脱敏、冻结、可重放的运行 Artifact，不直接读取或修改在线 Task/Report。
2. 管理病例级 split（数据划分）、trusted Gold（可信金标准）、Failure Bank 和纳入/排除规则。
3. 用相同病例、原图、Primary 配置、scorer 和时间计划运行 Primary Control 与 Targeted Candidate。
4. 计算 paired difference（配对差异）、置信区间、异常漏诊、正常误报、覆盖率、缺失行和技术失败率。
5. Development（开发集）用于调试，Regression（回归集）用于防退化，isolated Holdout 只用于冻结后的最终判断。
6. 产出候选证据和 release recommendation（发布建议），但不能直接激活 Config。
7. 人工审批后，Control Plane 才能使用 CAS 激活候选 revision。

### 16.3 输入、输出与落点

- 输入：脱敏运行 Artifact、冻结数据集 manifest、Gold、实验预注册和 scorer fingerprint。
- 输出：不可变实验结果、统计摘要、失败明细、批准/拒绝建议。
- 落点：隔离 `ms_image_eval` 的 `evaluation_*` 表和不可变 OSS Artifact。

### 16.4 失败与禁止职责

- 病例、图像、Primary 配置、scorer 或分母不一致：比较不可解释，必须判 No-Go。
- 不读取 Holdout 调 Prompt/Router，不修改 Gold 迎合候选，不删除不利病例。
- 工程测试通过、Provider 成功率或单例改善不能升级为医学准确率证据。

### 16.5 如果删除会发生什么

TargetedReview 是否值得上线只能凭主观判断，无法知道提升来自 Router、额外调用、模型变化还是数据泄漏。该层不属于每次在线请求，但属于任何医学发布前的必需治理面。

## 17. 图中每条边的业务含义

| 边 | 前置条件 | 为什么这样连接 | 禁止的捷径 |
|---|---|---|---|
| `ControlPlane -> TaskService` | Config/Profile 已验证并激活 | Task 必须冻结可重放配置 | Worker 运行时取“最新配置” |
| `Session -> Study` | Session owner/状态合法 | Study 需要业务生命周期根 | 把 Session 字段复制到每个 Image/Task |
| `Study -> Image` | Study/Series 计划已存在 | Image 必须有明确领域 owner | 先传匿名文件再猜归属 |
| `Image -> Study` | Image 服务端校验 ready | Study revision 只能由可信影像重算 | 上传/HEAD 成功直接 Study ready |
| `Study -> Task` | revision ready 且 manifest 冻结 | 诊断只能基于不可变完整检查 | Task 引用浮动“当前图片” |
| `Task -> Execution` | Task + first Stage + Outbox 同事务 | API 与异步执行可靠解耦 | API 内同步等待整条 AI 链 |
| `Execution -> Preparation` | Stage lease/CAS 领取成功 | 只有合法 owner 能推进阶段 | 重复消息直接重复调用模型 |
| `Preparation -> Primary` | 输入、能力、预算和泄漏门禁通过 | 医学调用只接收规范输入 | Primary 自行猜测缺图/错图 |
| `Primary -> Finalization` | Profile=`xray_primary_v1` 且结果完整 | 保持最短对照基线 | 无意义地执行 Router |
| `Primary -> FamilyRouting` | Profile=`xray_targeted_review_v1` | 候选链才允许选择专项复核 | 默认链偷偷运行实验节点 |
| `FamilyRouting -> Finalization` | route=`primary_final` | 没有复核价值时保留 Primary | 为了“多调用更准”强制 Targeted |
| `FamilyRouting -> TargetedReview` | route=`targeted_review` 且预算/deadline 已预留 | 最多一次受控准确率实验 | 多家族并行、无限重问 |
| `TargetedReview -> Finalization` | Targeted 成功且输出完整病例结果 | 该分支由 Targeted 成为唯一 owner | 拼接 Primary/Targeted 片段 |
| `Finalization -> Report` | owner 唯一、accepted、来源完整 | 统一两条 Profile 的最终事务 | 各医学 Stage 各写一套 Report |
| `Report -> Evaluation` | 运行产物已脱敏、冻结、可追溯 | 离线评测不污染在线事实 | 直接把生产 DB 当实验工作区 |
| `Evaluation -> ControlPlane` | 候选证据完整且人工审批 | 证据与发布权分离 | 评测 Job 自动改 Active Config |

## 18. 哪些层可以合并，哪些不能

| 调整 | 结论 | 理由 |
|---|---|---|
| SeriesService 并入 StudyService | 可以且当前采用 | Series 没有独立业务用例或事务 owner |
| StudyAssembler/EngineeringGate 并入 Preparation | 可以且当前采用 | 都依赖同一冻结输入，拆开只增加恢复状态 |
| OSS 上传并入 StudyService | 不建议 | 大对象生命周期、校验、隔离和替换有独立事务/恢复边界 |
| TaskService 并入 ExecutionService | 不建议 | 请求冻结与异步运行的权限、事务和调用方不同 |
| ExecutionService 并入 Worker | 不允许 | Worker 是进程入口，可靠状态机必须可复用、可测试并由数据库事实驱动 |
| Primary 按器官拆成多个 Stage | 默认不采用 | 同一图像/模型/Prompt 产生相关证据，调用增加不等于独立性增加 |
| FamilyRouting 放入默认 Profile | 不采用 | 没有 Targeted 分支时 Router 不产生边际价值 |
| FamilyRouting 与 TargetedReview 合并 | 不建议 | 确定性选择与视觉调用的成本、失败和实验变量不同 |
| Finalization 并入 Primary/Targeted | 不允许 | 会产生两套完成逻辑和多个医学事实入口 |
| ReportRenderer（报告渲染器）并入医学 Stage | 不允许 | 展示逻辑不得改变规范医学结果 |
| Evaluation 并入 Control Plane | 不允许 | 证据生产者不能同时拥有自动发布权 |

## 19. 开发和测试应该如何按层验收

| 层 | 最小工程证据 | 医学/业务证据 | Stop（停止）条件 |
|---|---|---|---|
| Control Plane | 不可变 revision、资格校验、Active Slot CAS、回滚 | 审批链可追溯 | 未审批配置可被 Task 使用 |
| Session/Study | 幂等、状态 CAS、revision 不覆盖 | 外部业务归属正确 | 补图覆盖旧 revision |
| Image | 流式 hash/格式校验、隔离、替换、故障恢复 | 模型发送对象与冻结对象一致 | 客户端声明可直接 ready |
| Task | Task/Stage/Outbox 原子创建、快照 hash 稳定 | 同一配置可重放 | 运行中配置发生变化 |
| Execution | 重复消息、lease 过期、崩溃、unknown reconcile | 无选择性结果覆盖 | 重复 Provider 调用或旧 owner 覆盖 |
| Preparation | 输入错误与覆盖不足正确分流 | 纳入/排除规则稳定 | 工程失败被写成医学状态 |
| Primary | 完整发送、Schema、receipt、结果 lineage | 冻结 Gold 上的基线指标 | 正常误报/异常漏诊越过护栏 |
| FamilyRouting | 相同输入必得相同 route，规则版本冻结 | 路由分层与 failure bank 对齐 | 读取 Gold/原图或改变医学结论 |
| TargetedReview | 最多一次调用、完整结果、失败关闭 | paired A/B 有净收益 | 只改善局部但安全护栏退化 |
| Finalization/Report | owner 唯一、最终事务原子、报告不可变 | 对外结果与 selected owner 完全一致 | Renderer/Policy 改写 Finding |
| Evaluation | 病例/分母/fingerprint/缺失行一致 | paired CI + isolated Holdout | 比较变量混杂或 Holdout 泄漏 |

工程证据只能证明链路可靠，不能自动证明医学准确率提高。Targeted 候选只有在预注册 paired A/B 和独立 Holdout 通过后才有资格申请 Gray/Active（灰度/正式激活）。

## 20. 接口级输入输出合同

状态：`MIXED LOGICAL CONTRACT / P1_PARTIALLY_IMPLEMENTED / P2_PLUS_NOT_IMPLEMENTED`（混合逻辑合同/P1 部分代码已实现/P2 及后续尚未实现）。

本节把图中的节点继续拆到可开发边界。下列 `Command/Input/Result/View` 名称是逻辑 Schema（结构合同）候选，
不是仓库中已经存在的 Pydantic（数据校验）类名；实施时可以调整类名，但不得改变字段语义、事实 owner（所有者）、
失败分类和上下游责任。所有调用在进入 Service 前都必须已经得到可信 identity（身份）和 scope（作用域），
请求体中的 owner、状态、hash 或结果声明不能覆盖服务端事实。

### 20.1 通用封装和传递规则

| 合同 | 必填内容 | 产生者 | 消费者 | 规则 |
|---|---|---|---|---|
| `RequestContext`（请求上下文） | `subject_id`、`scopes`、`request_id`、`trace_id` | API/Auth（接口/认证层） | 在线业务 Service | 身份来自已验证 token/service identity（令牌/服务身份），不从业务 body 信任 |
| `IdempotencyEnvelope`（幂等封装） | `idempotency_key`、`payload_hash` | API/调用方 | Session/Study/Image/Task | 相同 key + 不同 hash 必须冲突 |
| `ObjectRef`（对象引用） | `provider`、`bucket`、`object_key`、`version_id`、`content_sha256`、`byte_size`、`mime_type` | ImageService | StudyPreparation/AIRequest | 不保存 signed URL（签名地址）；实际读取前重新授权 |
| `FrozenRef`（冻结引用） | 资源 `id`、`revision/version`、`fingerprint` | 事实 owner Service | Task/Stage/Evaluation | 禁止用“当前最新”替代冻结版本 |
| `TechnicalFailure`（工程失败） | `error_code`、`retryable`、`failed_boundary`、`attempt`、`occurred_at`、脱敏 `detail_ref` | Execution/Stage/Provider adapter（适配器） | Execution/Task/Audit | 不得伪装成医学状态 |
| `MedicalResultEnvelope`（医学结果封装） | `medical_status`、`findings`、`coverage`、`source_refs`、`schema_version`、`result_hash` | Primary 或 Targeted | Finalization/Report | 必须是完整病例结果，医学字段不得由 Python 改写 |

成功响应只说明该层合同成功，不自动说明整条 Task（任务）完成，更不证明医学准确率。异步层返回 accepted（已受理）
或 transition（状态转换）时，最终状态必须继续从数据库事实查询。

### 20.2 ControlPlane（控制面）合同

| 项目 | 合同 |
|---|---|
| 调用方 | 管理端 API、经授权的发布负责人；EvaluationPlane 只能提交候选证据，不能直接激活 |
| 接收 | `CandidateAIConfigCommand`（候选 AI 配置命令）：`config_key`、`candidate_revision`、Prompt/Schema/Provider/model/handler/Profile 冻结引用、调用预算、deadline policy（截止策略）、qualification artifact ref（资格产物引用）、evaluation evidence ref（评测证据引用）、`approval_id`、幂等封装 |
| 必填约束 | revision 不可变；Profile 必须通过固定 PipelineProfileValidator（流水线配置校验器）；资格产物必须签名、未过期且与候选指纹一致；审批人和调用人权限满足分离要求；Secret 只存外部 SecretRef（密钥引用） |
| 成功输出 | `FrozenAIConfigSnapshot`（冻结 AI 配置快照）：`config_revision_id`、`profile_key/version`、各 handler/model/prompt/schema 版本、预算/deadline、`release_fingerprint`、`activated_at` |
| 失败输出 | `ConfigRejected`（配置拒绝）：稳定原因码，如 `qualification_missing`、`profile_invalid`、`approval_missing`、`active_slot_conflict`；不得产生可用 revision |
| 下游消费者 | TaskService 在创建 Task 时读取唯一 Active revision；Worker 只读取 Task 已冻结的 snapshot |
| 数据落点 | `ai_config_record` + AuditSink（审计接收器）；不保存明文 API key，不直接写 Task/Report |

### 20.3 SessionService（会话服务）合同

| 项目 | 合同 |
|---|---|
| 调用方 | 业务/管理 API 的调用端；旧 `vet-platform` 只允许通过 `LegacyMigrationAdapter`（旧系统迁移适配器）离线导入，不能作为在线上游 |
| 接收 | `CreateSessionCommand`（创建会话命令）：`RequestContext`、外部不透明 `business_ref`（业务引用）、幂等封装、可选最小业务标签；`CloseSessionCommand/CancelSessionCommand`（关闭/取消命令）：`session_id`、`expected_state_version`、原因码 |
| 必填约束 | requester 对资源有创建/变更权限；不复制用户、宠物和病历全文；状态只允许 `open -> closed/cancelled` 等预定义迁移；ID 放 query/body，不使用 `/{id}` |
| 成功输出 | `SessionView`（会话视图）：`session_id`、`status`、`state_version`、`created_at/closed_at`、脱敏业务引用 |
| 失败输出 | `idempotency_conflict`、`session_not_found`、`state_conflict`、`forbidden`；不创建下游 Study |
| 下游消费者 | StudyService 使用 `session_id` 建立检查；授权查询使用 owner 事实 |
| 数据落点 | `session_record` |

### 20.4 StudyService（检查服务）合同

| 项目 | 合同 |
|---|---|
| 调用方 | 业务 API 创建 Study/Series；ImageService 在影像版本 ready 后请求重算 revision；TaskService 查询 ready revision |
| 接收 | `CreateStudyCommand`（创建检查命令）：`session_id`、`modality`、`body_scope`、Series 计划、必需影像槽位、幂等封装；`RebuildStudyRevisionCommand`（重建检查版本命令）：`study_id`、已验证 Image version 集合、`expected_study_version`；`SealStudyRevisionCommand`（封存检查版本命令）：`study_revision_id`、服务端 manifest hash |
| 必填约束 | Session 必须 open 且 owner 合法；modality/type 使用可演进 string（字符串）并带代码校验；manifest 只能由当前 ready Image 确定性重算；补图、替换、顺序变化必须生成新 revision，不能覆盖旧 revision |
| 成功输出 | `StudyRevisionView`（检查版本视图）：`study_id`、Series 列表、`study_revision_id`、有序 manifest、`manifest_hash`、完整性原因；满足全部合同后输出 `StudyRevisionReady`（检查版本已就绪） |
| 失败输出 | 非终止的 `incomplete/conflict` 状态及缺失/冲突槽位；CAS 冲突返回 `state_conflict` 后重读，不猜测新版本 |
| 下游消费者 | ImageService 取得 Study/Series owner；TaskService 只接受 ready revision；Preparation 读取冻结 manifest |
| 数据落点 | `study_record`、`series_record`；Series 由 StudyService 管理，不单设 SeriesService |

### 20.5 ImageService（影像服务）合同

| 操作 | 接收及必填约束 | 成功输出 | 失败输出/落点 |
|---|---|---|---|
| `prepare_upload`（准备上传） | `PrepareUploadCommand`：`study_id`、`series_id`、slot/source index（槽位/来源序号）、文件名、预期 size/MIME、幂等封装；Study/Series owner 合法 | `UploadTicket`（上传凭证）：`image_id`、`generation`、目标 ObjectRef 的非敏感部分、短期上传凭证、过期时间 | 冲突或越权不创建记录；成功落 `image_record.status=uploading` |
| `complete_upload`（完成上传） | `CompleteUploadCommand`：`image_id`、`generation`、multipart receipt（分片回执）；HEAD/complete 在事务外完成 | `ImageValidationAccepted`（影像校验已受理）：`image_id`、`status=validating`、事件 ID | 对象缺失/代次不符返回工程错误；同一事务写 Image validating + `outbox_record(validate_image)` |
| `validate_image`（校验影像） | `ValidateImageCommand`：`image_id`、generation、lease/event 版本；Worker 在事务外流式读取 OSS bytes | `ImageValidationResult`：服务端 `ObjectRef`、真实 hash/size/MIME/format/dimensions、`status=ready` | hash/格式/像素/安全失败输出 quarantined 原因；落 `image_record`，并触发 Study revision 重算事件 |
| `replace_image`（替换影像） | 新 generation/version 与被替换 image ref；禁止原地覆盖 | 新版本走完整上传校验；Study CAS 成功后返回新 current version | 新版本失败保留旧 ready 版本；旧版本仅在新 revision 生效后 superseded |

ImageService 的消费者是 StudyService、StudyPreparationStage 和授权查询 API。OSS 保存 bytes（字节），
MySQL 的 `image_record` 保存影像领域事实；不创建 `file_asset`（公共文件资产）表。

### 20.6 TaskService（任务服务）合同

| 项目 | 合同 |
|---|---|
| 调用方 | 诊断 API 或受控实验入口 |
| 接收 | `CreateDiagnosticTaskCommand`（创建诊断任务命令）：`RequestContext`、ready `study_revision_id`、`diagnostic_type`、`run_mode`、可选明确 `profile_key`（需获准）、预算上限、deadline、幂等封装 |
| 必填约束 | Session/Study owner 合法；revision ready 且 manifest 不可变；只能选择已 Active 且与 modality/diagnostic type 匹配的 Config；请求预算不得放宽配置上限 |
| 成功输出 | `TaskAccepted`（任务已受理）：`task_id`、冻结 request/config/profile/input fingerprints（指纹）、首 `stage_checkpoint_id`、`execution_status=queued` |
| 失败输出 | `study_not_ready`、`config_unavailable`、`profile_not_allowed`、`budget_invalid`、幂等冲突；Task/Stage/Outbox 全不写 |
| 下游消费者 | Outbox Relay（发件箱中继）发布首执行事件；ImagingExecutionService 推进任务；查询 API 返回状态 |
| 数据落点 | 一个短事务原子写 `task_record`、首 `stage_checkpoint_record`、`outbox_record` |

### 20.7 ImagingExecutionService（影像执行服务）合同

| 项目 | 合同 |
|---|---|
| 调用方 | Worker 消费 Outbox/Broker 事件；Reconciler（对账器）处理 lease/unknown call；取消命令只写意图 |
| 接收 | `ExecuteStageCommand`（执行阶段命令）：不透明 `event_id`、`task_id`、`stage_checkpoint_id`、`expected_state_version`、`expected_lease_generation`；真实 Task/Stage/Config 必须从数据库重读 |
| 必填约束 | 事件、aggregate version（聚合版本）、lease owner/generation 和 deadline 匹配；冻结 handler 可由 StageRegistry 精确解析；外部 I/O 必须在数据库事务外 |
| 成功输出 | `StageTransitionResult`（阶段转换结果）：`completed_stage_id`、输出 hash/ref、下一 Stage/Outbox，或 Task terminal（任务终态）；重复事件输出 `already_applied` 并安全 ACK |
| 失败输出 | retryable（可重试）时输出 `retry_wait + next_attempt_at`；不可恢复/超 deadline 输出 TF；旧 lease/迟到结果输出 `late/ignored`；sent/unknown Provider Call 先 reconcile，不直接重发 |
| 下游消费者 | 当前 Stage handler、下一 Stage、ReportService、Task 查询和 AuditSink |
| 数据落点 | 协调 `task_record`、`stage_checkpoint_record`、`outbox_record`、`ai_call_record`、`report_record`；不另建 execution 表 |

### 20.8 StudyPreparationStage（检查准备阶段）合同

| 项目 | 合同 |
|---|---|
| 调用方 | ImagingExecutionService，且当前冻结 Stage handler 必须是 Preparation |
| 接收 | `StudyPreparationInput`（检查准备输入）：Task snapshot、ready Study revision、完整有序 Image manifest、冻结 Provider capability（能力）、整链预算/deadline、最小临床上下文引用 |
| 必填约束 | 每个 Image 的 ObjectRef/hash/generation 与 revision 一致；required coverage（必需覆盖）满足；格式可被 Provider 接受或有已资格化的确定性转换；不存在禁止泄漏字段 |
| 成功输出 | `PreparedStudy`（已准备检查）：规范有序输入列表、`prepared_input_hash`、可发送 MIME/转换 lineage（来源链）、覆盖声明、预留预算/deadline |
| 失败输出 | 对象缺失/hash/版本/传输不可信 -> TF；调用前覆盖/能力/预算明确不足 -> CF；二者不得互换 |
| 下游消费者 | JointPrimaryReaderStage |
| 数据落点 | Preparation 的 `stage_checkpoint_record.input/output_json` 或大型不可变 Artifact ObjectRef；不新建 preparation 表 |

### 20.9 JointPrimaryReaderStage（完整 Study 联合主读阶段）合同

| 项目 | 合同 |
|---|---|
| 调用方 | ImagingExecutionService，Preparation 已成功且预算已预留 |
| 接收 | `PrimaryReaderInput`（主读输入）：`PreparedStudy`、最小安全临床上下文、冻结 Primary Prompt/Schema/model/Provider/temperature/tool policy（工具策略）、调用预算 |
| 必填约束 | 一次调用发送完整有序 Study；调用前先持久化 `prepared` AI Call；响应必须匹配实际模型、receipt、发送清单和冻结 Schema |
| 成功输出 | `CompleteMedicalResult`（完整医学结果）：四类 `medical_status`、完整 findings、正常/异常覆盖声明、source refs、限制、schema/result hash；同时输出 Call receipt（调用回执） |
| 失败输出 | Provider/transport/schema/full-sent 不可恢复失败 -> TF；运输/受控格式修复只按冻结预算重试；不得因医学结果“不满意”重问 |
| 下游消费者 | `xray_primary_v1` -> DecisionFinalization；`xray_targeted_review_v1` -> FamilyRouting |
| 数据落点 | `ai_call_record` + Primary `stage_checkpoint_record.output_json/ObjectRef` |

### 20.10 FamilyRoutingStage（家族路由阶段）合同

| 项目 | 合同 |
|---|---|
| 调用方 | 仅 `xray_targeted_review_v1` 的 ImagingExecutionService |
| 接收 | `FamilyRoutingInput`（家族路由输入）：Schema-valid Primary 完整结果、冻结 `family_catalog_version`、Router 规则版本、剩余预算/deadline；不接收 Gold/Holdout/原图 bytes |
| 必填约束 | 路由为确定性纯函数；同一 input hash + rule version 必须得到相同输出；最多选择一个家族和一组冻结问题 |
| 成功输出 | `FamilyRouteDecision`（家族路由决定）：`route=primary_final/targeted_review`、可选 `selected_family_key`、`question_set_version`、预注册 `reason_codes`、input/rule hash |
| 失败输出 | 规则不可解析、输入 Schema 不匹配或预算前置条件破坏 -> 候选链 TF；不得偷偷回到 Primary |
| 下游消费者 | `primary_final` -> DecisionFinalization；`targeted_review` -> TargetedReview |
| 数据落点 | Router `stage_checkpoint_record.output_json`；不新建 family 表，不修改医学结果 |

### 20.11 TargetedReviewStage（专项复核阶段）合同

| 项目 | 合同 |
|---|---|
| 调用方 | 仅 Router 输出 `targeted_review` 后的 ImagingExecutionService |
| 接收 | `TargetedReviewInput`（专项复核输入）：完整原图 `PreparedStudy`、Primary 完整结果及 source refs、一个 `selected_family_key`、冻结问题集、Targeted Prompt/Schema/model/Provider、剩余预算/deadline |
| 必填约束 | 最多一次视觉调用；仍发送完整 Study；Targeted 配置与实验 fingerprint 一致；输出必须是完整病例 Schema，不接受 finding delta（发现增量） |
| 成功输出 | 新的 `CompleteMedicalResult` + Targeted Call receipt；它成为该分支唯一医学 owner，不与 Primary 拼接 |
| 失败输出 | 触发后的 Provider/Schema/full-sent 不可恢复失败 -> TF + `medical=not_produced`；fail closed（失败关闭），禁止回退 Primary |
| 下游消费者 | DecisionFinalization |
| 数据落点 | 独立 `ai_call_record` + Targeted `stage_checkpoint_record.output_json/ObjectRef` |

### 20.12 DecisionFinalizationStage（结果定稿阶段）合同

| 项目 | 合同 |
|---|---|
| 调用方 | Primary 基线分支、Router 的 `primary_final` 分支或成功 Targeted 分支 |
| 接收 | `FinalizationInput`（定稿输入）：冻结 Profile/route、候选 `CompleteMedicalResult`、accepted Stage/Call refs、发送 manifest、Schema/result hash |
| 必填约束 | Profile 与来源分支严格匹配；恰好一个 accepted medical owner；结果完整、source lineage 连续；禁止比较医学内容“哪个好” |
| 成功输出 | `FinalizedDecision`（已定稿决定）：`selected_owner=primary/targeted_review`、`selected_stage_id`、`selected_call_id`、规范 result ref/hash、finalized fingerprint |
| 失败输出 | owner 不唯一、分支不匹配、结果或来源不完整 -> TF；不得猜测、投票、fallback（回退）或改写 Finding |
| 下游消费者 | ReportService；ImagingExecutionService 协调最终原子事务 |
| 数据落点 | Finalization `stage_checkpoint_record.output_json`；不新建 decision 表 |

### 20.13 ReportService（报告服务）合同

| 项目 | 合同 |
|---|---|
| 调用方 | ImagingExecutionService 的 Finalization 完成事务；授权查询/作废 API |
| 接收 | `CreateReportCommand`（创建报告命令）：`task_id`、`FinalizedDecision`、selected `CompleteMedicalResult`、预期 Task/Stage 版本；`VoidReportCommand`（作废报告命令）：`report_id`、原因、预期版本 |
| 必填约束 | selected source 与 Task 输入/Profile 一致；Report revision 不可变；Renderer（渲染器）只能生成展示产物，不能改规范医学 JSON |
| 成功输出 | `ReportView`（报告视图）：`report_id/revision`、`status=final/published/void`、medical status、规范结果、source lineage、`current` 标志；可选派生渲染 ObjectRef |
| 失败输出 | Report/Task/Finalization 任一持久化失败则最终事务整体回滚；授权失败不泄漏报告存在性 |
| 下游消费者 | 对外查询 API、授权调用端、脱敏 Artifact exporter（产物导出器）、EvaluationPlane |
| 数据落点 | `report_record` + `task_record.current_report_id`；首期不建 DeliveryService（交付服务）或 callback/ack 字段 |

### 20.14 TF、CF 与 OUT 的输出合同

| 终点 | 接收 | 对外输出 | 是否有医学报告 | 持久化 |
|---|---|---|---:|---|
| `TF`（工程失败） | `TechnicalFailure` 和最后可信 checkpoint | `TaskTerminalView(execution_status=failed/dead_letter, ai_medical_status=not_produced, error_code, retry_exhausted)` | 否 | Task/Stage/Call 失败事实 + AuditSink |
| `CF`（调用前覆盖终态） | Preparation 产生的确定性 coverage/capability/budget reason | `TaskTerminalView(execution_status=completed, ai_medical_status=not_produced, reason_code)`；可附 technical report（技术说明） | 否 | Task 完成事实；若落报告，只能明确 `medical_not_produced` |
| `OUT`（医学输出） | ReportService 已持久化 current Report | `ReportView` 中的 `normal/abnormal/review_required/non_diagnostic` | 是 | Task current pointer + 不可变 Report |

TF 表示“系统没可靠跑完”，CF 表示“系统正确决定调用前停止”，OUT 才表示“模型已经产生并被选中的医学结果”。
任何 API 聚合响应都必须保留这三个维度，禁止只返回一个含糊 `status`。

### 20.15 EvaluationPlane（离线评测面）合同

| 项目 | 合同 |
|---|---|
| 调用方 | 经授权的离线评测任务；输入来自脱敏、冻结 Artifact exporter，不直接修改在线库 |
| 接收 | `EvaluationExperimentSpec`（评测实验规格）：病例级 dataset/split manifest、Gold revision、control/candidate fingerprints、相同 Primary 配置约束、scorer fingerprint、预注册主指标/护栏/分母/排除规则、随机种子和运行计划 |
| 必填约束 | 同病例、同原图、同 scorer、同分母；只允许预注册变量变化；Development/Regression/Holdout（开发/回归/留出）隔离；缺失行和工程失败不能静默删除 |
| 成功输出 | `EvaluationDecisionEvidence`（评测决策证据）：逐病例配对结果、主指标差、置信区间、正常误报、异常漏诊、coverage（覆盖率）、缺失行、技术失败率、unsafe flips（不安全翻转）、`recommendation=promote/reject/inconclusive` |
| 失败输出 | fingerprint/样本/分母/scorer 不一致 -> `not_interpretable/no_go`（不可解释/禁止放行）；不生成发布批准 |
| 下游消费者 | 人工审批者；批准后由 ControlPlane 接收 approval + evidence ref，Evaluation 不能自行激活 Config |
| 数据落点 | 隔离 `ms_image_eval.evaluation_*` 表 + 不可变 OSS Artifact |

### 20.16 一张端到端 I/O 交接表

| 前一层 | 交付对象 | 下一层 | 下一层开始前必须证明 |
|---|---|---|---|
| ControlPlane | `FrozenAIConfigSnapshot` | TaskService | revision Active、资格/审批/指纹有效 |
| SessionService | `SessionView(open)` | StudyService | owner 和状态合法 |
| StudyService | Study/Series 计划 | ImageService | 影像拥有明确 Study/Series/slot |
| ImageService | verified `ObjectRef` | StudyService | bytes 已由服务端完整校验 |
| StudyService | `StudyRevisionReady` | TaskService | manifest 不可变且完整 |
| TaskService | `TaskAccepted` + first Stage event | ImagingExecutionService | Task/Stage/Outbox 原子存在 |
| ImagingExecutionService | `StudyPreparationInput` | Preparation | lease/CAS/handler 版本合法 |
| Preparation | `PreparedStudy` | Primary | 输入、能力、泄漏、预算和 deadline 通过 |
| Primary | `CompleteMedicalResult` | Finalization 或 Router | Schema/receipt/full-sent/lineage 完整 |
| Router | `FamilyRouteDecision` | Finalization 或 Targeted | 路由确定性、单家族、预算已预留 |
| Targeted | 新 `CompleteMedicalResult` | Finalization | 最多一次调用且完整输出 |
| Finalization | `FinalizedDecision` | ReportService | 唯一 accepted owner，不含新医学内容 |
| ReportService | current `ReportView` | API/Evaluation exporter | Report/Task 指针原子一致 |
| EvaluationPlane | `EvaluationDecisionEvidence` | 人工审批 + ControlPlane | 配对实验可解释且 Holdout 未泄漏 |

## 21. 最终统一口径

```text
Session 定义一次业务会话；Study 定义一次不可变检查版本；Image 证明 OSS 对象可信。
Task 冻结一次诊断请求；Execution 保证异步阶段可恢复。
Preparation 保证输入可调用；Primary 产生默认医学结果。
FamilyRouting 只在实验 Profile 决定是否值得一次 TargetedReview。
Targeted 成功时成为该分支完整医学 owner；Finalization 只选择唯一 owner。
Report 保存不可变对外结果；Evaluation 用冻结证据判断候选是否值得发布。
工程状态、医学状态和发布状态始终分开。
```
