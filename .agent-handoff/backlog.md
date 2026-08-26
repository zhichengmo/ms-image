# 待办清单

## 已完成基础

- [x] AI Prompt Control Plane（AI 提示词控制面）Phase A-C：Prompt、Connection、Model Pool、不可变 Config、Task 快照和审计链。
- [x] Prompt Runtime / AI Gateway（提示词运行时/AI 网关）D1-D4：OpenAI-compatible（OpenAI 兼容）传输、Logical Call/Physical Attempt（逻辑调用/物理尝试）、严格 Schema（结构合同）和三段事务。
- [x] D5 Primary-only Runtime Foundation（仅主读运行时基础）：Logical Call/Physical Attempt、OSS image signer、unknown Attempt reconcile 与三段事务代码基础；旧 Secret Resolver、Provider 原始响应加密存储和 Gateway adapter 已按用户决策删除。
- [x] 21 号完整能力链路和新会话 Prompt（提示词）文档。
- [x] 22 号完整 AI/Prompt（人工智能/提示词）架构参考：逐 Service（服务）、逐 Stage（阶段）合同、表链路、Prompt 生命周期、可靠调用和评测门禁。
- [x] 23 号后续修正与分阶段实施指南：保留阶段依赖、合同修正与历史新会话 Prompt；当前实施入口已迁移至 24 号文档。
- [x] 文档权威收口：17/19/20/21/23 号文档均已明确为早期合同、历史入口或目标能力范围；当前事实与新会话入口统一指向 24 号文档和 `AGENT_SESSION_PROMPTS.md` 顶部当前入口。

## P0 审查修正（进入后续能力前）

- [x] 文档层拆分 current fact（当前实现事实）、approved target contract（批准目标合同）和 medical release evidence（医学发布证据）。
- [x] 文档层统一 FamilyRouting 只输出 `primary_final/targeted_review`，不得产生或修改医学状态。
- [x] 将五个 Family 标为 `v1 routing vocabulary（首版路由词汇）`；全身性、非特异性、多区域和无法唯一归族病例保持 Primary-only。
- [x] 区分 StudyPreparation 的 technical coverage（技术覆盖）与模型判断的 medical assessability（医学可评估性）。
- [x] 统一 Targeted 技术失败合同：当前实验 Profile 不静默回退；未来 Primary fallback 必须使用新 Profile 并独立评测。
- [x] Prompt 合同改为 Shared Medical Core + Primary/Targeted Frozen Entry（共享医学核心加主读/专项冻结入口）。
- [x] 将完成定义拆为核心诊断链、医学基线和 Targeted/Retry/Multi-Provider/Fallback/Race 逐项资格。
- [x] 调整依赖顺序：Prompt/模型单变量实验提前；第二 Provider 先只支持 Model A/B（模型对比）。
- [x] 文档层补充通知幂等、留存/删除、脱敏、成本配额、Task 取消、迟到 Attempt 和 unknown 有界终态合同。
- [x] 核验现有 FamilyRouting 源码并扩展现有测试：当前只固定 `primary_final`，原样透传 Primary 完整结果，不产生医学状态；真正 `targeted_review` 路由仍属于 M2。
- [x] 修复 v2 `build_targeted_ai_request_command()`：验证并向 `XRayPromptCommand`/safe context 写入 `family_key/focus_key`，保持单一冻结 Prompt 正文，并增加正反例合同测试。
- [x] 同步 23 号权威与 `AGENT_SESSION_PROMPTS.md`：将 Targeted family/focus 断点标为 P0-A 已完成，下一会话不得重复修复。
- [ ] 为 FamilyRouting 建立版本化输入/输出结构：唯一 Family、唯一 Focus、来源 Finding、coverage proof、reason codes、contract version、预算/deadline/资格门禁。
- [ ] 为 `UnsupportedProviderAttemptLookup` 定义有界终止策略；不能永久 reschedule，也不能把 unknown 当普通失败盲目重发。
- [x] 核验 StudyPreparation 并增加回归测试：当前只做技术准备，不产生 `non_diagnostic` 或其他医学状态。
- [x] 最小修正 Task cancel、迟到 Winner、AI Stage 最终化和 Report finalize/publish 幂等代码合同；复用现有 Task/Call/Attempt/Stage/Report 表和 DAL。
- [ ] 明确 Report Notification（报告通知）的真实 destination/consumer/event key 合同后再补通知幂等；当前无证据，不新增虚构 Outbox 事件。

## Prompt（提示词）运行合同与医学优化

- [ ] Q0 Prompt Inventory（提示词盘点）：只读确认目标 Nacos、数据库 Prompt/Connection/ModelPool/Config/Schema/消息合同、状态、哈希、引用和 active 事实，不输出 Secret。
- [x] Q0 外部烟测子切片：向目标 Nacos 写入并发布非医疗 smoke Prompt，完成 runtime 读取、规范化、渲染和消息组装；同时核验 `ms-ai-fast` 现有 Nacos Prompt 到 Platform/Provider 的在线参考链。
- [ ] Q0 剩余：盘点并选择合格的 XRay Primary 医学 Prompt/Config；smoke Prompt 不得替代医学候选。
- [ ] Q1 Prompt Runtime Contract（提示词运行合同）：选择唯一 Primary 候选，验证安全变量、确定性渲染、developer/user/image/schema 分层、Config 冻结、Task 快照和重放一致性。
- [x] Q1 子切片：Primary/Targeted `prompt_mode`、Targeted structured user context、`PRIMARY_RESULT_JSON` variables 声明和 frozen Config 重放语义校验。
- [ ] Q2 Primary Baseline Freeze（主读基线冻结）：E1 后冻结 Prompt、模型、病例、Revision、影像哈希、Schema 和评分器，形成 M1。
- [ ] Q3 Primary Prompt A/B（主读提示词配对实验）：在 M1 后按 Failure Bank 一次只改变一个 Prompt 主要变量。
- [ ] Q4 Model A/B（模型配对实验）：第二 Provider 工程资格化后，在同 Prompt 和同病例条件下比较模型。
- [ ] Q5 Targeted Prompt Qualification（专项提示词资格化）：只在 M2 残余失败证明需要后验证反锚定、完整 Study 重读和完整结果输出。
- [ ] Q6 Release and Rollback（发布与回滚）：只通过新不可变 Prompt/Config 发布；回滚激活旧 Config，不原地覆盖历史模板。

## 后续实施依赖顺序

### E1 Primary Runtime（仅主读真实运行链）

- [x] 脱敏确认 MySQL、Redis、RabbitMQ、OSS 基础配置，并验证 Redis PING、RabbitMQ 仅连接、主库 `SELECT 1`、OSS Bucket 信息读取；没有写外部依赖。
- [x] AI/Prompt 链收敛到 `ms-ai-fast`：共享 `NACOS_*`、直接 `GatewayClient`、`AI_PLATFORM_OPENAI_BASE_URL + AI_PLATFORM_API_KEY`、单条 user message；删除旧 `AI_GATEWAY_*` selector、Secret Resolver、response store 和 adapter/composition。
- [ ] 审阅现有两版未应用迁移对旧 AI 表和数据的兼容性，形成 backup（备份）、baseline/stamp（基线/标记）、write set（写集合）和 rollback（回滚）方案；未经授权不 upgrade。
- [ ] 创建并迁移 `ms_image_eval（评测库）`；主库迁移后确认 `ai_config_record` 和当前 Connection/Pool/Prompt schema 与 ORM 一致。
- [ ] 明确 Runtime/Admin JWT（运行时/管理端令牌）信任和密钥生命周期；完成保护 API 与 Control Plane 鉴权配置。
- [ ] 保持数据库 Connection/Model Pool/Prompt/AI Config 的冻结与审计事实；`secret_ref` 仅作为遗留兼容元数据，不再配置 `MS_IMAGE_AI_SECRET_*` 或进入 Worker 鉴权链。字段级删除等待明确迁移授权。
- [ ] 配置并接线资格化 Artifact（证据产物）签名键；确认签名键格式、轮换和调用入口，不能只在 `.env` 声明后就视为闭环。
- [ ] 将 `AI_PLATFORM_OPENAI_BASE_URL` 与 `AI_PLATFORM_API_KEY` 成对安全注入真实 imaging Worker 启动环境（不恢复 `AI_GATEWAY_*`）；本机 2026-08-26 Settings 核验为 `ai_platform_configured=False`。注入后只读确认 presence，再验证 OSS 影像短签名、MySQL、RabbitMQ/Celery、Provider、Attempt/Stage/Report 的同一冻结任务全链。
- [ ] 跑通 Outbox（事务发件箱）→ Worker（工作进程）→ OSS（对象存储）→ Provider（模型提供方）→ Attempt/Stage finalize（物理尝试/阶段终态化）→ DecisionFinalization（结果定稿）→ Report（报告）。
- [ ] 验证重复消息、unknown Attempt、事务边界、冻结 Config（配置）和完整 Artifact（证据产物）。

### M1 Primary Medical Baseline（主读医学基线）

- [ ] 冻结病例、Gold（可信金标准）、图像、Prompt、模型、Schema、预算和评分器。
- [ ] 产出正常/异常分层指标、Failure Bank（失败样本库）、置信区间和 Holdout（留出集）基线。

### Primary Prompt A/B（主读提示词配对实验）

- [ ] 使用 Shared Medical Core + Primary Frozen Entry（共享医学核心加主读冻结入口）建立不可变 Prompt 候选；一次只改变一个主要变量。
- [ ] 在同病例、同图像、同 Gold、同模型、同 Schema 和同评分器下运行 Failure Bank、完整回归、Paired A/B 和隔离 Holdout。

### Second Provider Minimal Qualification + Model A/B（第二模型最小资格化与模型对比）

- [ ] 独立资格化第二个冻结 Connection/模型候选，只用于同病例 Model A/B；不同时启用 Fallback 或 Race。
- [ ] 继续复用与 `ms-ai-fast` 同语义的 `GatewayClient`；只有真实不兼容协议出现后才评审额外客户端或 Registry（注册表）。
- [ ] 同时记录 requested_model/actual_model（请求模型/实际模型），防止 Provider 重定向污染实验变量。

### M2 FamilyRouting + TargetedReview（专项家族路由与专项复核）

- [ ] 将固定 `primary_final（主读直接定稿）` 改为确定性、零模型调用的唯一 Family/Focus（专项家族/关注点）路由。
- [ ] 只使用胸腔、腹腔、四肢骨关节、轴骨骼、头颈五个 Family（专项家族）。
- [ ] 接入最多一次 TargetedReview（专项复核），读取同一完整 Study（检查），输出新的完整病例结果。
- [ ] 与 Primary-only（仅主读）做同病例 Paired A/B（配对 A/B）和 Holdout（留出集）门禁。

### Retry Qualification（多物理尝试重试资格化）

- [ ] 版本化放宽现有 lane（通道）的 `max_attempts（最大尝试次数）`，接入冻结预算、deadline（截止时间）和可重试错误分类。
- [ ] unknown 未按原幂等身份确认前继续禁止盲发；Winner（胜出结果）产生后禁止新 Attempt。

### Fallback Qualification（自动降级资格化）

- [ ] 评审并在确有必要时最小增加 Attempt 的 `lane_key（通道键）`；先报告 write set（写入文件集合）并等待迁移授权。
- [ ] 让 `single（单并发执行）` 支持最多两个有序冻结候选，只在明确工程失败后进入后备候选。
- [ ] 禁止医学结果触发降级，禁止新增 FallbackService（降级服务）。

### Race Qualification（双通道竞速资格化）

- [ ] 版本化启用 `race（并发竞速）`，最多两个通道并发。
- [ ] 使用一个 Logical Call（逻辑调用）、多个 Physical Attempt（物理尝试）和 `winner_attempt_id CAS（胜出尝试标识比较交换）`。
- [ ] Winner 只按 `first_technically_valid（首个技术合同完整结果）` 决定；禁止医学投票、拼接和 Python 改判。

## 长期兼容清理

- [ ] 仅在 v1 Config（旧配置）非终态 Task（任务）清零且用户明确授权后，删除 Catalog/Compiler/Bundle（目录/编译器/组合包）兼容链。

## 当前不实施但不影响七项目标

- [ ] 人工复核流程、Web 管理页面、独立 AI 数据库和无证据的新医学 Family（专项家族）不属于本轮完整目标。

## 2026-08-25 — 已完成核心 AI 网络 E2E；待完整任务链资格化

- [x] 写入 Nacos 非医疗 smoke Prompt，并完成 `NacosPromptSourceClient → PromptRenderer → PromptMessageAssembler → GatewayClient → ms-ai-platform → gemini-3.5-flash` 严格 Schema 网络烟测；旧 SecretResolver/GatewayAdapter 实现随后已删除。
- [ ] 数据库 Model schema 已重建；继续按 E1 顺序完成 Prompt/Connection/ModelPool/Config 数据、冻结 Control Plane、OSS image signer 与 Worker Platform 配置。


## XRay 单一 Prompt 与接口物种参数（2026-08-26）

- [x] 创建 Task 的 request body 已增加 `species`；`diagnose` 必须传 `cat` 或 `dog`，并在 Task 创建期归一化、校验和冻结进 `request_snapshot_json`。
- [x] XRay Prompt Source 已收敛为唯一内部 key `xray_primary` 和 exact-only `common` variant；禁止 `cat/dog/default -> common` fallback。
- [x] Primary/Targeted Prompt command 均从冻结 Snapshot 把 `species` 写入 `SAFE_STUDY_CONTEXT_JSON`；Worker 不回查宠物档案、不猜测物种。
- [ ] 发布并回读校验 `ms-image.x-ray.primary.common.zh-CN@<immutable version>`；历史 cat/dog/default 发布物只保留为不可变历史，不导入、不激活。
- [ ] 使用既有控制面导入 common Prompt，建立 Connection/ModelPool，编译并激活唯一 `xray_diagnose` `global/global` Config。
- [ ] 创建显式传 `species=cat|dog` 的冻结真实 Task，完成 P1/E1 全链资格化；E1 前不进入医学 A/B、TargetedReview、Retry、Fallback 或 Race。

## 当前开发入口（2026-08-25）

- [ ] 完成 P1 Worker Runtime Qualification（工作进程运行时资格化）：当前 AI/Prompt 代码已按 `ms-ai-fast` 收敛，隔离 OSS synthetic 已通过 PUT/HEAD/Worker GET/同机 signed GET/cleanup；仍需确认真实 Worker 加载 `AI_PLATFORM_OPENAI_BASE_URL + AI_PLATFORM_API_KEY`、Provider Attempt Lookup 与同一冻结任务的 MySQL -> Outbox -> Broker -> Worker -> OSS -> Provider -> Attempt -> Stage -> Report 非敏感证据。
- [ ] 在 P1（工作进程运行时安全资格化）通过后，完成 E1 Primary-only Runtime（仅主读真实运行链）：ready Revision（就绪修订）-> Outbox（事务发件箱）-> Broker/Worker（消息代理/工作进程）-> OSS（对象存储）-> Provider（模型提供方）-> Attempt/Stage（物理尝试/阶段）-> Finalization（结果定稿）-> Report（报告）。
- [ ] 仅在 E1（仅主读真实运行链）真实通过后，进入 M1 Primary Medical Baseline（主读医学基线）与 Q3 Primary Prompt A/B（主读提示词配对实验）；之后再按 24 号文档打开 Q4、M2、R1、R2、R3。

## 宠物档案（当前不创建）

- [ ] `pet_profile` / `medical_record` 不在当前 ms-image Model 清单；除非用户明确要求新增，否则不建表、不生成迁移、不增加 Service。
- [ ] 若未来启用猫/犬自动选择，由上游按 `session_id -> medical_record -> pet_profile -> species` 解析，再把 `species` 冻结进 Task Snapshot，并通过 `SAFE_STUDY_CONTEXT_JSON.species` 交给唯一 `xray_primary/common` Prompt；Worker 不得运行时回查档案。
- [ ] 上游 `ms-ai-fast` / 病例集成尚未实际执行 `session_id -> medical_record -> pet_profile -> cat|dog -> POST /tasks`；当前 `ms-image` 的 Task 冻结合同已就绪，但不能把调用方手填 `species` 当作已完成档案继承。

## 2026-08-26 — Runtime Schema 重建后待办

- [x] 以当前 `apps/backend/models/__init__.py` 注册 Model 为唯一清单创建 20 张表，并 stamp `20260824_02`；最新复核 `model_missing=[]`、`extra_non_model=[]`。
- [ ] 导入并激活已确定的 XRay Prompt/Config，同时建立 Connection 与 ModelPool 数据。
- [ ] 创建 Session/Study/Series/Image、冻结 Task Snapshot 和 Outbox 事实。
- [ ] 在实际 Worker 注入 AI Platform 成对配置，运行完整冻结任务链并采集脱敏证据。
- [ ] 在用户没有新增 Model/表要求前，不再执行数据库删表或 Model 用途筛选。

## 2026-08-26 — 快速上线 Prompt 收敛

- [x] 采用接口传参区分猫狗：`POST /tasks` request body 对 `diagnose` 必传 `species=cat|dog`；不引入 `pet_profile` / `medical_record` 自动选择链。
- [x] Task Snapshot 冻结 `species`，同一 Prompt 通过 `SAFE_STUDY_CONTEXT_JSON` 获得物种上下文；Prompt source identity 不按物种分叉。
- [x] XRay Prompt 身份收敛为 `xray_primary/common` exact-only；旧 cat/dog/default Nacos 版本不进入新链。
- [ ] 发布/导入 common Prompt，编译并激活唯一 Config，创建冻结 Task 并跑通 Worker AI 全链。
