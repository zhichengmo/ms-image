# MS-Image 文档中心

> 英文术语、状态、缩写和数据库类型请参阅[英文术语中英对照](术语中英对照.md)；代码标识符保持英文原样。

本目录按“当前权威、实施导航、工程证据、历史资料”分类。文档数量不是问题，关键是每类资料只有一种用途，读者能快速判断它是否仍可指导开发。

> 本项目新会话的当前执行合同是[MS-Image 当前开发合同与会话执行规范](ms-image-current-development-contract.md)。项目级 `AGENTS.md` 会要求每次任务先核对其中的已完成能力总账；具体 active objective 仍以用户授权和 `.agent-handoff/snapshot.md` 为准。

## 先看哪里

| 目的 | 入口 | 权威性 |
|---|---|---|
| 开启当前项目开发、新会话或核对已完成功能 | [MS-Image 当前开发合同与会话执行规范](ms-image-current-development-contract.md) | 当前项目执行合同；必须结合 snapshot 和源码复核 |
| 用一份文档完整理解 XRay 总体架构、数据库、模块、链路、逐层责任和专项设计 | [XRay 完整核心架构与专项设计](refactor/14-xray-specialty-design.md) | 当前自包含交付入口；新开发优先阅读 |
| 开启新重构会话、实施开发或向团队介绍项目 | [MS-Image 重构文档包](refactor/README.md) | 当前实施与讲解导航；不复制字段权威 |
| 设计 QJ 接入、公共/专项模块收敛、入口/Worker/数据库连接调整 | [QJ 借鉴与模块收敛调整方案](refactor/16-qj-reference-and-modular-convergence-plan.md) | 当前架构调整建议；不授权迁移或真实环境操作 |
| 只评审 QJ 借鉴是否适用、暂不修改代码 | [QJ 借鉴决策门新会话提示](refactor/18-qj-reference-decision-gate-session-prompt.md) | 当前只读评审入口；未经最小切片授权不得实施 |
| 设计 Prompt、Config Release、AI Call 或 Provider-disabled 最小链 | [Prompt 运行合同与最小 Provider 链路调整方案](refactor/17-prompt-runtime-contract-and-minimal-provider-plan.md) | 当前 Prompt 运行合同；不授权真实 Provider 或迁移 |
| 查看或开发 XRay（X 光）完整流程 | [XRay（X 光）详细链路与开发流程图](refactor/10-xray-detailed-flow.md) | Canonical XRay Chain（X 光权威主链）和集中开发视图；精确字段仍以设计母文为准 |
| 向新开发讲解 XRay（X 光）核心链路 | [XRay（X 光）核心链路开发沟通文档](refactor/11-xray-core-chain-developer-briefing.md) | 当前沟通入口；展开执行细节时继续读取 10 |
| 设计 XRay 专项 | [XRay 完整核心架构与专项设计](refactor/14-xray-specialty-design.md) | 专项与完整系统架构的统一依据 |
| 审查 XRay 每层目的、功能、输入输出和存在必要性 | [Canonical XRay Chain（X 光权威主链）逐层责任与接口合同](refactor/12-canonical-xray-layer-responsibility-contract.md) | 当前逐层责任和逻辑接口权威；精确数据库字段仍以设计母文为准 |
| 判断基于 `9a45209a` 还是当前工作树重构 | [重构基线决策](refactor/13-refactor-base-decision.md) | 当前 Git 基线与 preserve/replace（保留/替换）决策；不代表已经建立 checkpoint |
| 数据库、模块、API（应用程序接口）、AI（人工智能）、异步执行、数学评测和完整链路设计 | [MS-Image（影像） 最终架构、数据库与完整链路设计](ms-image-final-architecture-and-database-design.md) | 当前唯一设计依据 |
| 当前工程验证、Provider（AI 服务提供方）资格和发布状态 | [工程证据索引](artifacts/README.md) | 事实证据，不定义目标架构 |
| 查看旧方案、XRay（X 光）V2 设计过程和迁移背景 | [历史文档索引](history/README.md) | 仅供追溯，不指导新开发 |
| 英文术语、状态和缩写中文解释 | [英文术语中英对照](术语中英对照.md) | 全部文档共用 |

## 目录分类

```text
docs/
├── README.md
├── ms-image-final-architecture-and-database-design.md
├── refactor/
│   ├── README.md              重构、新会话和团队讲解入口
│   ├── 01-03                  项目、架构、数据库与 OSS
│   ├── 04-07                  Service、开发、迁移、决策与风险
│   ├── 08-09                  新会话交接与团队介绍
│   ├── 10                     XRay 详细链路与开发流程图
│   ├── 11                     XRay 核心链路开发沟通文档
│   ├── 12                     XRay 权威主链逐层责任与接口合同
│   ├── 13                     当前工作树重构基线决策
│   ├── 14                     XRay 专项完整设计
│   ├── 15                     全链缺口与分阶段执行计划
│   ├── 16                     QJ 借鉴与模块收敛调整方案
│   ├── 17                     Prompt 运行合同与最小 Provider 链路调整方案
│   └── 18                     QJ 借鉴决策门新会话提示
├── artifacts/
│   ├── README.md
│   └── 当前运行、资格验证、发布和数据库快照证据
└── history/
    ├── README.md
    ├── design/                 已被取代的通用设计
    └── xray/
        ├── design/            XRay 历史架构和数据库设计
        ├── plans/             历史开发、Phase 和迁移计划
        ├── reports/           历史审计、迁移和比较报告
        └── prompts/           生成历史文档时使用的 Prompt
```

根目录只保留入口和当前唯一权威设计，不再堆放专题稿、阶段稿或运行输出。

## 权威边界

本项目不存在一条可以混用的“总权威排名”。发生冲突时先判断争议属于哪条轴，再使用该轴的权威来源：

| 权威轴 | 权威来源 | 能证明什么 | 不能证明什么 |
|---|---|---|---|
| 项目规则与授权 | 当前用户明确授权 + 当前适用的 `AGENTS.md` | 允许修改什么、必须遵守什么、哪些动作需另行确认 | 当前代码已实现、目标设计正确或医学准确率提升 |
| 当前实现事实 | 当前 worktree 的源码、配置、依赖和启动合同 | 当前代码实际做什么 | 目标系统应该如何设计、生产环境已经相同 |
| 当前外部事实 | 经授权读取的真实 DB schema、OSS bytes/hash、Broker/Provider trace | 对应环境和采集时点实际发生了什么 | 目标 schema、未来行为或医学效果 |
| 目标设计 | [设计母文](ms-image-final-architecture-and-database-design.md) | 目标表、状态、事务、Service 和不变量 | 已经实现、已经迁移或已经验证 |
| 实施指导 | [重构文档包](refactor/README.md) | 如何分阶段实现目标设计 | 独立新增或覆盖母文中的精确合同 |
| 医学准确率 | 冻结 Gold、同病例 paired A/B、确定性 scorer、隔离 Holdout | 候选链是否改善预注册指标和安全 guardrail | 工程测试、调用成功率或单次案例是否代表准确率 |
| 历史解释 | `docs/history` 和旧外部设计包 | 为什么曾经这样设计、旧方案有哪些证据 | 当前实施合同或目标 schema |

同一轴内仍需校验代码版本、环境、命令、时间和完整性。旧真实 schema 对“当前/历史现状”有权威性，
但不能覆盖目标 schema；设计母文定义目标，却不能证明实现或准确率。来源不一致时记录差距并标注
`CONFIRMED / INFERRED / PROPOSED / UNKNOWN / N/A`，不得跨轴互相冒充。

## 当前设计摘要

- 用户已授权内部代码可以完全重构；旧 `xray_accuracy` 目录、类和内部实现可以替换。当前仍推荐保留或受控迁移外部合同、唯一事实 owner 和已验证可靠性语义，不建立第二套并行事实源。
- 当前可复核工程证据截止到 `2026-08-11T04:05:17Z`；之后的代码、配置或环境变化必须重新生成资格 Artifact（证据产物）。
- 目标在线数据库 `ms_image` 的当前候选基线为 10 张核心表。P1 的 Session/Study/Series/Image 与影像校验基础代码已实现，但尚未迁移或做真实运行验证；Task/Stage/AI/Report 等其余目标表仍为 `DESIGNED / NOT IMPLEMENTED`（已设计/尚未实现）。10 表不是数量上限，独立 owner（所有者）、生命周期/状态机、查询、事务/恢复或权限/保留证据可以触发新增、合并或拆表。
- 目标隔离评测数据库 `ms_image_eval` 的当前候选基线为 4 张 `evaluation_*` 表，状态为 `DESIGNED / NOT IMPLEMENTED`（已设计/尚未实现）；它们统一承载 Gold（可信金标准）、实验、统计、校准、拓扑/OOD（分布外检测）和可选 Harness（离线分析执行框架），形成标注工作台或法规逐行审计等独立合同时可以增表。
- XRay（X 光）、CT（计算机断层成像）、MRI（磁共振成像）、超声、视频和 WSI（全切片影像）复用统一 Study（检查）/Series（序列）/Image（影像）/Task（任务）数据边界；各模态医学执行链分别资格化，首期只闭环 XRay。
- 在线核心只有 8 个业务 Service（业务服务）：Session/Study/Image/Task/ImagingExecution/AIConfig/AIRequest/Report；Registry、Validator、Gateway、Relay 和 AuditSink 是组件，不人为扩成额外业务 Service。
- Canonical XRay Chain（X 光权威主链）已冻结：目标代码只注册 5 个有独立责任的 Stage Service（阶段服务），但默认 `xray_primary_v1` 只执行 `StudyPreparation -> JointPrimaryReader -> DecisionFinalization`；`FamilyRouting + TargetedReview` 只成对存在于候选 `xray_targeted_review_v1`，通过配对门禁前仅允许 validation-only/shadow。当前仓库尚未实现这 5 个目标 Stage，不能把设计写成运行事实。
- `StageRegistry`（阶段注册表）精确注册 `handler_key/version`，`PipelineProfileValidator`（流水线配置校验器）首期只校验代码内置固定 Profile、Schema（结构合同）、预算、强制门禁和唯一 Final owner（最终结果负责人）；通用 DAG（有向无环图）能力延后，调整顺序必须创建新的不可变 Config revision（配置修订版本）。
- Task（任务）/Stage（阶段）冻结 compiled pipeline（已编译流水线）与 handler（处理器）版本，运行中不热切换；顺序实验与 Prompt（提示词）/model（模型）/handler（处理器）实验分开评测。
- OSS（对象存储）保存 bytes（文件字节）；`image_record`（影像记录表）保存影像域索引，其他产物使用完整 `ObjectRef`（对象引用），不建设公共文件资产表。实际存储位置见[OSS（对象存储）具体存储位置与环境拓扑](ms-image-final-architecture-and-database-design.md#521-oss对象存储具体存储位置与环境拓扑)，上传、校验、读取、对账、隔离、保留和删除见[OSS（对象存储）完整闭环](ms-image-final-architecture-and-database-design.md#53-oss对象存储完整闭环)。
- Primary（主读）是默认医学结果 owner；只有 targeted Profile 命中且 TargetedReview（专项复核）成功时才由 Targeted 成为 owner。固定 FinalMedicalReader（二次终审）已因现有退化证据被拒绝，DecisionFinalization（决策定稿）不调用模型、不改判。
- Task（任务）只保存 `execution_status`（工程状态）和 `ai_medical_status`（AI 医学状态）；首期没有 callback/ack（回调/确认）生命周期，因此不保存重复的 `delivery_status`。报告持久化、发布和作废由 `current_report_id -> report_record.status` 唯一表达。
- `vet-platform` 是旧系统/迁移来源，不是目标在线上游；`ms_image` 不保存 `result_owner=legacy_fallback` 这类旧发布事实。目标 Shadow/Gray/回切由 `ControlPlane`（控制面）的冻结 release（发布）配置唯一拥有，新报告只由自身 source Stage/Call（来源阶段/调用）证明；旧 V2 结果仅作迁移追溯，不复制为新 Task/Report 医学事实。
- Stage（阶段）小型输入/输出使用 `input_json/output_json`，大型载体使用完整 OSS ObjectRef（对象引用），两组分别严格二选一；迟到只记录为 AI Call（AI 调用）的 `late/ignored` 处置，不增加 Stage `late` 状态。
- 基础 source lineage（来源链）属于在线审计内核；语义证据依赖图只在 `ms_image_eval` 离线实验中作为不可变 Artifact（产物）保存，不为每个 node（节点）/edge（边）增加在线明细表；同源证据不作为独立投票。
- 人工复核当前为 `N/A`；`review_required` 表示 AI 无法确定，是可持久化、可发布终态，不创建人审表、队列或接口。
- 当前发布状态仍为 `PARTIAL / NO-GO`，医学准确率仍为 `UNKNOWN`。
- 当前隔离库中的 10 张 `xray_accuracy_*` 表只是 validation-only 快照，不是目标通用十表；目标在线十表处于 `P1_CODE_IMPLEMENTED / NOT_MIGRATED`（P1 代码已实现/未迁移）与 P2+ `DESIGNED / NOT IMPLEMENTED`（已设计/尚未实现）的混合状态，四张评测表仍为 `DESIGNED / NOT IMPLEMENTED`。
- 目标字段已经按 owner（所有者）、可推导性、查询合同和不可变证据完成最小化；删除项与保留理由见[字段最小化结论](ms-image-final-architecture-and-database-design.md#60-字段最小化结论)。
- 当前稳定 Provider 资格合同的直接阻断是 `qualification_artifact_signing_key_missing`；历史 `provider_auth` 只表示一次旧真实尝试，不能混为同一状态。

详细字段、状态、事务、服务边界和实施门禁以唯一权威设计文档为准，本索引不复制完整设计。

## 新文档放置规则

| 文档类型 | 放置位置 | 必须说明 | 完成或失效后的处理 |
|---|---|---|---|
| 当前总体架构 | 根目录唯一权威文档 | 状态、日期、范围、非目标、事实等级 | 新版本直接修订同一文档；重大旧方案移入 history |
| 重构实施、开发和交接视图 | `refactor/` | 对应母文章节、当前/目标差距、读取顺序和完成定义 | 与母文同步；不复制第二套字段权威 |
| 专题 ADR | 首期并入权威设计对应章节 | 决策、备选、证据、影响和回滚 | 失效后移入 `history/design/` |
| 阶段计划 | `history/xray/plans/`；未来通用计划应建立明确专题目录 | owner、状态、门禁、依赖、完成定义 | 阶段结束后标记历史，不与当前设计并列 |
| 审计或迁移报告 | 对应专题的 `reports/` | 检查范围、证据日期、结论等级 | 保留原结论，不反向修改成“已完成” |
| 机器生成证据 | `artifacts/` | 来源命令/代码版本、时间、环境、脱敏状态 | 生成新快照，不覆盖不可变历史证据 |
| Prompt（提示词） | 对应专题的 `prompts/` | 输入范围、输出文件和安全限制 | 与生成结果一起归档 |

## 状态标签

文档顶部优先使用以下状态，避免“最终版”“最新最终版”这类不可判断的文件名：

| 状态 | 含义 |
|---|---|
| `CURRENT`（当前）/`FINAL_REVIEWED_DESIGN`（已完成最终评审的设计） | 当前评审通过的设计依据，不代表代码已上线 |
| `DRAFT`（草稿） | 仍在讨论，不能作为实现合同 |
| `PARTIAL`（部分完成） | 已有部分工程证据，但尚未闭环 |
| `BLOCKED`（受阻）/`NO-GO`（禁止放行） | 存在阻断，不允许进入下一门禁 |
| `SUPERSEDED`（已被取代） | 已被新文档取代，只保留历史追溯 |
| `ARCHIVED`（已归档） | 任务或阶段已结束，不再维护 |

## 命名与维护规则

- 当前权威文档使用稳定文件名，禁止创建 `final-v2`、`final-new`、`最终版2`。
- 历史文档保留原文件名，通过目录和顶部状态表达生命周期。
- 运行证据使用 `阶段-范围-用途` 命名；不可变快照可追加 UTC 时间戳。
- 稳定运行时契约可以使用版本名，例如 `ai-provider-qualification.v1.json`，修改格式时必须提升版本。
- Markdown 内部链接优先使用相对路径；只有跨仓库来源才使用绝对路径并明确其外部依赖属性。
- 每次改变权威设计时同步更新本索引；每次增加 artifact 时同步更新 [工程证据索引](artifacts/README.md)。
- 引用 Artifact 必须同时写明 `captured_at` 和代码/工作树绑定；缺少命令、版本、环境或脱敏状态时只能标记为历史线索。
- 不删除不利证据，不把 `PASS-LOCAL` 写成生产通过，不把 Provider 成功率写成医学准确率。

## 工程约束

- 每张物理 MySQL 表必须有独立、非空、服务端生成的 `id VARCHAR(64)` 单列 `PRIMARY KEY`；业务 ID、请求 ID、事件键、版本号、哈希和联合 `UNIQUE` 约束不得替代主键，也不得使用联合主键。
- 目标架构不设计 `tenant_id` 或其他租户分区字段；资源 ID 全局唯一，访问控制使用用户/服务身份、业务 scope 和资源归属校验。
- 数据库不使用 Foreign Key 和数据库 Enum；状态使用带中文候选说明的字符串。
- 业务链遵循 `API -> Service -> CRUD(DalBase) -> Model/DB`。
- API 资源 ID 使用 query 参数或 request body，不使用资源 ID 路径占位符。
- 未经明确授权不生成迁移、测试脚本，不修改现有数据库。
- 医学判断只能来自模型或医生，Python 只做路由、校验、持久化和审计。

当前文档目录和目标架构仍属于开发前设计与证据集合，不代表目标表已经创建、旧数据已经迁移或真实医学链路已经上线。
