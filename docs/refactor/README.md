# MS-Image 重构文档包

状态：`CURRENT_REFACTOR_GUIDE`（当前重构导航）
更新日期：2026-08-25
适用范围：后续重构会话、架构评审、开发拆分和团队沟通。
设计母文：[MS-Image 最终架构、数据库与完整链路设计](../ms-image-final-architecture-and-database-design.md)
术语表：[MS-Image 英文术语中英对照](../术语中英对照.md)

本目录是“怎么理解和实施当前设计”的工作包，不是第二份字段权威。精确字段、索引、状态候选值和核心不变量以设计母文为准；本目录负责把母文拆成项目介绍、架构、数据库导航、服务合同、开发规范、迁移验证和交接材料。

## 1. 文档地图

| 顺序 | 文档 | 用途 | 主要读者 |
|---:|---|---|---|
| 1 | [01-project-overview-and-business-chain.md](01-project-overview-and-business-chain.md) | 项目目标、边界和端到端业务链 | 全体开发、产品、架构师 |
| 2 | [02-target-architecture.md](02-target-architecture.md) | 目标系统边界、平面、模块和事务原则 | 架构师、后端开发 |
| 3 | [03-database-and-storage-design.md](03-database-and-storage-design.md) | 在线 10 表、评测 4 表、关系图和 OSS 合同 | 后端、数据库、运维 |
| 4 | [04-service-and-stage-design.md](04-service-and-stage-design.md) | 8 个业务 Service、5 个 Stage Service 和调用矩阵 | 后端、AI 工程师 |
| 5 | [05-development-guide.md](05-development-guide.md) | 分层、目录、接口、事务、错误和编码规则 | 实施开发人员 |
| 6 | [06-refactor-migration-and-validation-plan.md](06-refactor-migration-and-validation-plan.md) | 当前到目标差距、分阶段重构、门禁和回滚 | 技术负责人、开发、测试 |
| 7 | [07-decisions-risks-and-open-questions.md](07-decisions-risks-and-open-questions.md) | 已接受、已否决、延后、实验性能力和 UNKNOWN（未知项） | 架构评审者 |
| 8 | [08-new-session-handoff.md](08-new-session-handoff.md) | 当前新会话恢复、QJ 借鉴模块收敛的 Phase 判定和可复制启动提示入口 | Codex/Claude/开发人员 |
| 9 | [09-team-introduction.md](09-team-introduction.md) | 可直接用于向其他开发介绍项目的讲解提纲 | 项目负责人 |
| 10 | [10-xray-detailed-flow.md](10-xray-detailed-flow.md) | Canonical XRay Chain（X 光权威主链）、端到端、候选分支、事务、状态和恢复流程图 | 后端、AI 工程师、测试、架构师 |
| 11 | [11-xray-core-chain-developer-briefing.md](11-xray-core-chain-developer-briefing.md) | 面向新开发讲解 XRay 核心链、每层理由、Service/表落点和统一沟通口径 | 全体新参与开发人员 |
| 12 | [12-canonical-xray-layer-responsibility-contract.md](12-canonical-xray-layer-responsibility-contract.md) | 权威图逐层目的、逻辑、接口级输入输出、调用方、消费者、落表、失败、禁止职责和删除影响 | 架构师、后端、AI、测试、运维 |
| 13 | [13-refactor-base-decision.md](13-refactor-base-decision.md) | `9a45209a` 与当前工作树的 Git 事实、资产/债务、方案评分、保留/替换和回滚边界 | 技术负责人、实施开发、评审者 |
| 14 | [14-xray-specialty-design.md](14-xray-specialty-design.md) | 自包含的 XRay 完整核心架构：总体边界、数据库、Service/Stage、完整链路、逐层责任、专项、评测、缺陷和发布门禁 | 全体开发、AI、评测、架构师 |
| 15 | [15-full-chain-gap-analysis-and-execution-plan.md](15-full-chain-gap-analysis-and-execution-plan.md) | 当前全链工程缺口、执行状态、Phase 2 收口和真实运行/医学门禁 | 技术负责人、开发、测试、运维 |
| 16 | [16-qj-reference-and-modular-convergence-plan.md](16-qj-reference-and-modular-convergence-plan.md) | 借鉴 QJ 的边界、公共/专项/Evaluation 收敛、部署与接入调整方案 | 架构师、后端、平台集成人员 |
| 17 | [17-prompt-runtime-contract-and-minimal-provider-plan.md](17-prompt-runtime-contract-and-minimal-provider-plan.md) | Prompt/Config Release/AI Call 的最小运行合同、Provider-disabled 真 Bundle 与 P4 实施门禁 | AI 工程师、后端、架构师 |
| 18 | [18-qj-reference-decision-gate-session-prompt.md](18-qj-reference-decision-gate-session-prompt.md) | 只读 QJ 借鉴决策门提示；先判定 Adopt/Adapt/Reject/Defer，未经最小切片授权不实施 | 新会话、架构评审者、技术负责人 |
| 19 | [19-ai-prompt-control-plane-web-and-runtime-architecture.md](19-ai-prompt-control-plane-web-and-runtime-architecture.md) | AI Prompt（AI 提示词）控制面、Web 管理面、不可变 Config（配置）和 Runtime（运行时）调用架构 | AI 工程师、后端、前端、架构师 |
| 20 | [20-monorepo-refactor-new-session-prompt.md](20-monorepo-refactor-new-session-prompt.md) | 当前代码事实、D5 Primary-only Runtime Foundation（仅主读运行时基础闭环）、逐组件开发合同、验证门禁和可复制的新会话 Prompt（开发提示） | 下一阶段实施开发、新会话、技术负责人 |
| 21 | [21-xray-complete-capability-chain-and-session-prompt.md](21-xray-complete-capability-chain-and-session-prompt.md) | 当前代码基础之上的完整目标链路：FamilyRouting/TargetedReview（家族路由/专项复核）、多 Attempt（物理尝试）、多 Provider（模型提供方）、自动降级、双 lane（通道）、医学 Prompt（提示词）优化及可复制新会话 Prompt | 完整能力分阶段开发、新会话、技术负责人 |
| 22 | [22-xray-full-ai-prompt-chain-development-guide.md](22-xray-full-ai-prompt-chain-development-guide.md) | 完整架构参考：逐 Service（服务）、逐 Stage（阶段）的目的、输入、处理、输出、落表和失败语义；其中的实现状态须由 24 号文档和当前源码复核 | 完整链路背景、架构讲解 |
| 23 | [23-xray-next-phase-correction-and-implementation-guide.md](23-xray-next-phase-correction-and-implementation-guide.md) | 历史阶段目标与修正背景：三类权威边界、P0 合同修正、完整链路、逐阶段输入输出/Gate/回滚与旧新会话提示；不作为当前运行事实或实施次序权威 | 历史阶段回溯、架构评审 |
| 24 | [24-current-runtime-audit-and-next-development-guide.md](24-current-runtime-audit-and-next-development-guide.md) | 当前代码、配置、数据库与真实 AI 网络实测的审计结论；明确已实现/已资格化/已医学验证边界，给出 P0/P1/E1/M1/Q3/Q4/M2/R1/R2/R3 的后续开发与停止门禁 | 当前后续开发、新会话、技术负责人、架构评审 |

## 2. 按任务阅读

| 任务 | 最小阅读集 |
|---|---|
| 第一次完整了解 XRay 项目 | 14；需要精确字段时再查设计母文 |
| 给新开发讲解 XRay 核心链 | 14 |
| 设计 XRay 专项、FamilyRouting/TargetedReview | 14 |
| 评审 XRay 每一层是否有必要、接收什么和输出什么 | 14 |
| 决定重构代码基线和 preserve/replace 范围 | 13 -> 06 -> 08 |
| 设计或修改表 | 03 -> 母文第 5、6、14 章 -> 07 |
| 开发在线业务 | 02 -> 04 -> 05 -> 06 |
| 开发 XRay（X 光）链路 | 24 -> 当前源码与测试 -> 10 -> 04 的 Stage 合同 -> 03 的表导航 -> 17（早期 AI/Prompt 合同追溯）-> 母文第 6、8、15、16 章 |
| 接入 CT/MRI（计算机断层/磁共振） | 01 的多模态边界 -> 02 -> 母文第 9 章 |
| 调整 Prompt（提示词）或模型 | 24 -> 当前源码与测试 -> 19/20（架构/历史参考）-> 14 -> 06 的医学门禁 -> 07；17 只用于追溯早期最小运行合同 |
| 理解当前 Prompt/Config/AI Runtime（提示词/配置/AI 运行时）实现 | 24 -> 当前源码与测试 -> 19/20（架构/历史参考） |
| 补齐 Targeted、多 Attempt、多 Provider、自动降级、双 lane 与医学 Prompt 完整能力 | 24 -> 21 -> `AGENT_HANDOFF.md`（代理交接入口）-> 当前源码 -> 当前阶段相关测试 |
| 按逐层输入/输出合同实施完整 AI 与 Prompt 链路 | 24 -> 22 -> `AGENT_HANDOFF.md`（代理交接入口）-> 当前源码 -> 当前阶段相关测试 |
| 开启当前后续开发或新会话 | 24 -> `AGENT_HANDOFF.md`（代理交接入口）-> 当前阶段源码和现有测试 |
| 设计 QJ 接入、公共/专项模型或 Service 收敛 | 24 -> 16 -> 17（早期 AI/Stage 合同追溯）-> 04 -> 05 -> 15；精确字段再查设计母文 |
| 仅评审 QJ 借鉴是否适用、暂不实施 | 18 -> 16 -> 17（涉及 AI/Stage 时）-> 当前源码；输出 Adopt/Adapt/Reject/Defer 矩阵 |
| 开启 D5 Primary-only Runtime（仅主读运行时）资格化会话 | 24 -> `AGENT_HANDOFF.md`（代理交接入口）-> 当前源码 |
| 开启完整 XRay 能力分阶段开发会话 | 24 -> 21 -> `AGENT_HANDOFF.md`（代理交接入口）-> 当前源码 |
| 查询通用跨会话恢复原则 | 08 -> `AGENT_HANDOFF.md`（代理交接入口） |
| 查询历史为什么这样改 | [历史演进与冲突索引](../history/README.md) |

## 3. 权威边界

权威必须按问题分轴，不能用一条线性顺序混排：

| 问题 | 权威来源 |
|---|---|
| 当前允许做什么 | 用户当前授权 + `AGENTS.md` |
| 当前代码实际做什么 | 当前 worktree 的源码、配置和运行合同 |
| 当前外部环境实际发生了什么 | 经授权取得的 DB/OSS/Broker/Provider 原始事实及其时间绑定 |
| 目标系统应该是什么 | 设计母文 |
| 目标如何落地 | 本 `docs/refactor/` 文档包 |
| 医学效果是否改善 | 冻结 Gold + paired A/B + 确定性 scorer + isolated Holdout |
| 旧方案为何存在 | `docs/history` 和旧外部设计包 |

- Artifact（工程证据）只能证明其代码、环境和采集时点发生了什么。
- 旧真实 schema 是现状事实，不是目标 schema；母文定义目标，但不能宣称已经实现或已经提高准确率。
- 本目录不得私自新增字段、状态、Stage（阶段）或 Service（业务服务）；发现冲突时先修改母文，再同步实施视图。
- 历史文档不得作为建表或迁移依据。

## 4. 当前一句话状态

当前源码已经具备 Session/Study/Series/Image（会话/检查/序列/影像）、Task/Stage/Outbox/Worker（任务/阶段/事务发件箱/工作进程）、Prompt Import/Config Snapshot（提示词导入/配置冻结）、Logical Call/Physical Attempt（逻辑调用/物理尝试）、Gateway Adapter（网关适配器）、Secret Resolver（密钥解析器）、OSS Attempt Image Signer（OSS 尝试影像签名器）、Encrypted Response Store（加密响应存储器）、unknown Attempt reconcile（未知尝试对账）、Report（报告）和 Evaluation（评测）代码骨架；Nacos Prompt（Nacos 提示词）、Gateway Adapter（网关适配器）到 Platform/Provider（平台/模型提供方）的核心 AI 网络实测已经通过，但完整 XRay Worker Runtime（X 光工作进程运行时）尚未在共享非生产真实 MySQL、OSS、Broker/Worker（消息代理/工作进程）、Secret 和 Provider 上完成资格化。因此统一状态是 `D5_CODE_FOUNDATION_COMPLETE / MS_IMAGE_CORE_AI_NETWORK_CHAIN_PASSED / FULL_WORKER_RUNTIME_NOT_QUALIFIED / MEDICAL_ACCURACY_UNKNOWN / MEDICAL_RELEASE_NO_GO`。本节只作导航摘要；当前实现事实、下一动作和运行资格以 24 号文档、当前 worktree（工作树）与 `.agent-handoff/snapshot.md` 为准；23 号保留旧阶段目标，22 号保留完整架构背景，21 号保留完整能力范围。

## 5. 文档维护合同

- 字段变化：只修改设计母文对应表章节，再更新 03 的导航和 07 的决策。
- Service/Stage 变化：先形成决策证据，再同步母文、04 和 07。
- 当前实现变化：更新 `.agent-handoff/snapshot.md`、工作日志和新 Artifact，不把运行状态写进架构正文。
- 历史方案变化：历史正文原则上冻结，只更新 [history/README.md](../history/README.md) 的归宿说明。
- 所有英文标识首次出现时附中文含义；代码名保持英文，中文只解释。
- 不创建 `final-v2`、`latest-final` 等竞争文件；重大变更用 Decision Log（决策日志）记录。
