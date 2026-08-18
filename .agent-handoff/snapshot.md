# 代理交接当前快照

## 当前状态

- 最后更新：2026-08-18
- 工作区：`/Users/mozhicheng/workspace/code/cy-code/ms-image`
- 当前目标：以已冻结的 Canonical XRay Chain（X 光权威主链）开始目标架构重构；先完成有界 P0 核对，再按 P1A -> P1B -> P1C 实施通用影像底座。
- 当前状态：`p1a_session_implemented / study_series_next`（P1A Session 已实现/下一切片为 Study+Series）
- 当前分支：`codex/ms-image-refactor`；所有后续工作按业务 owner 垂直切片提交，每次验证后立即推送并核对远端 SHA，推送失败不得进入下一切片。
- 下一步：实施 P1A Study+Series Model -> Schema -> StudyDal/SeriesDal -> StudyService；建立 revision/manifest/完整性与 Session processing CAS。
- 活动入口：
  - `docs/refactor/README.md`
  - `docs/refactor/10-xray-detailed-flow.md`
  - `docs/refactor/11-xray-core-chain-developer-briefing.md`
  - `docs/refactor/12-canonical-xray-layer-responsibility-contract.md`
  - `docs/refactor/13-refactor-base-decision.md`
  - `docs/ms-image-final-architecture-and-database-design.md`
  - `docs/history/README.md`
  - `.agent-handoff/backlog.md`
- 当前阻断：目标表、Stage 和评测控制面尚未实现；未授权迁移、真实数据库和真实对象演练；真实 Provider 和医学发布仍为 `NO-GO`（禁止放行）。
- 开放问题：目标实现、真实 Provider 资格、Gold/paired A/B/Holdout 和生产环境合同仍未闭环；详见 `.agent-handoff/risks.md`。

## 恢复摘要

- 当前代码是 XRay validation-only（X 光仅验证）工程骨架，不是目标通用影像系统。
- 用户允许代码完全重构；旧 `xray_accuracy` 内部目录、类和实现可以替换。
- 新会话提示词本身明确授权开始内部代码重构；迁移脚本、新建测试脚本、真实数据库操作和生产发布仍需单独授权。
- 权威已改为多轴合同：规则授权、当前实现、当前外部事实、目标设计、实施指导、医学准确率和历史解释不能跨轴互相冒充。
- P1 已拆为 P1A 分层、P1B API、P1C Image validate Outbox/Relay/Worker；P2 复用同一 Outbox 扩展 Task/Stage/Call。
- 目标表不保存 `tenant_id` 但保留认证；旧 tenant claim/OSS key 仅作兼容过渡，目标 owner 使用可信 identity/scope/资源归属。
- 当前候选基线是 `ms_image` 在线 10 表、`ms_image_eval` 隔离 4 表、8 个在线业务 Service（业务服务）和 5 个注册 Stage Service（阶段服务）；表数量不设上限，按必要性增减。
- 默认 XRay 链为 `StudyPreparation -> JointPrimaryReader -> DecisionFinalization -> Report`；FamilyRouting + TargetedReview 仅为实验候选。
- Canonical XRay Chain 已由用户确认：`xray_primary_v1` 从 Primary 直接进入 Finalization；`xray_targeted_review_v1` 才进入 FamilyRouting，并选择 `primary_final` 或最多一次 TargetedReview。
- 根 `README.md`、`USAGE.md`、`CLAUDE.md` 已从 MS-Scaffold 脚手架说明重写为 MS-Image 项目入口、真实运行指南和协作上下文。
- 官方 curated（精选）Skill 中未找到适合本地 Markdown 权威治理的专用工具；Notion 文档 Skill 不匹配。当前审计组合为 `evidence-driven-architecture-optimizer`（证据驱动架构优化）+ `agent-handoff`（跨会话交接）。公开 GitHub 搜索结果仅有低采用度第三方候选，未安装。
- 新增 `docs/refactor/11-xray-core-chain-developer-briefing.md` 作为新开发沟通入口，覆盖端到端主链、逐层理由、状态/失败、家族边界、Service/表落点和开发顺序；精确字段仍由设计母文拥有。
- `docs/refactor/11` 已补齐 ControlPlane 发布回路、全链 Service/Stage 输入输出交接矩阵和当前源码 Preserve/Replace 边界，可直接用于 20-30 分钟新开发沟通。
- 新增 `docs/refactor/12-canonical-xray-layer-responsibility-contract.md`，逐节点固定目的、意义、功能逻辑、输入输出、落表、失败语义、禁止职责、删除影响、边合同、可合并边界和分层验收证据。
- `docs/refactor/12` 已补齐接口级调用方、接收、必填约束、成功/失败输出、下游消费者和数据落点；跨文档审计未发现 Canonical Chain 冲突。
- 当前 `HEAD` 已核实就是 `9a45209a`，`9a45209a..HEAD=0`；重构选择当前工作树资产基线 + 保留入口的内部模块化替换，不 reset/clean，也不沿用 `xray_accuracy` 专项模型继续零散修补。
- `.env` 已恢复为 Git ignore；`.env.example` 中 OSS/STS/Gemini 凭据值已清空，脱敏扫描未发现其他常见云密钥或私钥。曾出现的凭据仍需持有人轮换。
- 用户已确认使用 `codex/ms-image-refactor` 和垂直切片提交；每个切片必须独立验证、提交、推送，不 amend/rebase 已推送提交。
- P0 有界工程核对无 P1A 硬阻断：旧事务内外部 I/O 延后到 P1C 替换；JWT subject/scope、Broker/readiness、启动入口可复用；TraceEvent 在 AuditSink 资格化前保留。
- P1A Session 已实现：`session_record`、Session Schema、`SessionDal(DalBase)` 和 `SessionService`；依赖子资源事实的 complete/processing cancel 保持 fail-closed，待 Study/Image DAL 到位后闭环。
- `AGENT_SESSION_PROMPTS.md` 的“开启新的重构会话”已更新为执行型最终入口：先解决 `.env`/checkpoint，再直接实施 P1A -> P1B -> P1C，并按逐层 I/O 合同验收。
- 本轮只修改文档和交接状态，没有修改业务代码、数据库、迁移或测试脚本。
- 本文件是替换式当前快照，不追加旧聊天记录。
