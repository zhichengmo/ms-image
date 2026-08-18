# MS-Image 重构文档包

状态：`CURRENT_REFACTOR_GUIDE`（当前重构导航）
更新日期：2026-08-18
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
| 8 | [08-new-session-handoff.md](08-new-session-handoff.md) | 新会话恢复顺序、实施起点和完成定义 | Codex/Claude/开发人员 |
| 9 | [09-team-introduction.md](09-team-introduction.md) | 可直接用于向其他开发介绍项目的讲解提纲 | 项目负责人 |
| 10 | [10-xray-detailed-flow.md](10-xray-detailed-flow.md) | Canonical XRay Chain（X 光权威主链）、端到端、候选分支、事务、状态和恢复流程图 | 后端、AI 工程师、测试、架构师 |
| 11 | [11-xray-core-chain-developer-briefing.md](11-xray-core-chain-developer-briefing.md) | 面向新开发讲解 XRay 核心链、每层理由、Service/表落点和统一沟通口径 | 全体新参与开发人员 |
| 12 | [12-canonical-xray-layer-responsibility-contract.md](12-canonical-xray-layer-responsibility-contract.md) | 权威图逐层目的、逻辑、接口级输入输出、调用方、消费者、落表、失败、禁止职责和删除影响 | 架构师、后端、AI、测试、运维 |
| 13 | [13-refactor-base-decision.md](13-refactor-base-decision.md) | `9a45209a` 与当前工作树的 Git 事实、资产/债务、方案评分、保留/替换和回滚边界 | 技术负责人、实施开发、评审者 |

## 2. 按任务阅读

| 任务 | 最小阅读集 |
|---|---|
| 第一次了解项目 | 01 -> 09 -> 02 |
| 给新开发讲解 XRay 核心链 | 11 -> 10（需要展开故障与事务细节时） |
| 评审 XRay 每一层是否有必要、接收什么和输出什么 | 12 -> 10 -> 母文对应精确字段合同 |
| 决定重构代码基线和 preserve/replace 范围 | 13 -> 06 -> 08 |
| 设计或修改表 | 03 -> 母文第 5、6、14 章 -> 07 |
| 开发在线业务 | 02 -> 04 -> 05 -> 06 |
| 开发 XRay（X 光）链路 | 10 -> 04 的 Stage 合同 -> 03 的表导航 -> 母文第 6、8、15、16 章 |
| 接入 CT/MRI（计算机断层/磁共振） | 01 的多模态边界 -> 02 -> 母文第 9 章 |
| 调整 Prompt（提示词）或模型 | 04 -> 06 的医学门禁 -> 07 |
| 开启新重构会话 | 08 -> `AGENT_HANDOFF.md`（代理交接入口） |
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

当前仓库是 XRay validation-only（仅验证）工程骨架，不是目标通用影像系统；当前候选起点仍是 `DESIGNED / NOT IMPLEMENTED`（已设计/尚未实现）的在线 10 表、隔离评测 4 表、8 个在线业务 Service 和 5 个注册 Stage Service。10+4 不是数量上限，必要时可按独立事实证据增表。医学准确率仍为 `UNKNOWN`（未知），发布状态仍为 `PARTIAL / NO-GO`（部分完成/禁止放行）。

## 5. 文档维护合同

- 字段变化：只修改设计母文对应表章节，再更新 03 的导航和 07 的决策。
- Service/Stage 变化：先形成决策证据，再同步母文、04 和 07。
- 当前实现变化：更新 `.agent-handoff/snapshot.md`、工作日志和新 Artifact，不把运行状态写进架构正文。
- 历史方案变化：历史正文原则上冻结，只更新 [history/README.md](../history/README.md) 的归宿说明。
- 所有英文标识首次出现时附中文含义；代码名保持英文，中文只解释。
- 不创建 `final-v2`、`latest-final` 等竞争文件；重大变更用 Decision Log（决策日志）记录。
