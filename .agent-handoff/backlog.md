# 待办清单

## 2026-08-31 — R4A 当前收口

- [ ] [BLOCKED] 在线主库 `alembic check` 存在既存 `ai_api_connection.secret_ref` 注释漂移；未经独立范围审阅不混入 R4A migration。
- [ ] [ENVIRONMENT] Docker daemon 启动后补一次镜像 build 与 `evaluation-migrate` 容器启动验证；不修改业务代码。
- [ ] 两项关闭后记录计划中的最终 R4A qualification，按明确路径分组提交并推送当前分支。
- [ ] R4A 最终关闭后进入 R4B Dataset 治理；R4C Gold/Scorer、R4D Runtime 等价 Runner、M1 和 Prompt 继续保持后置。

## 2026-08-30 — v3.3 最终路线、全接口与 Postman 静态交付已完成

- [ ] 使用真实环境、真实影像和真实 Provider 执行 Collection Runner/Newman；此项继续归入下方 E0–E8，不由静态交付替代。

## 2026-08-30 — X-Ray 2–5 图真实 Runtime E2E 已完成

- [x] E3：既有 `scripts/dev/run_e2e_local.py` 已支持 case manifest 驱动同 Study 2–5 图、多 Series、receipt 只读核验与脱敏 evidence；未新增第二套 Harness。
- [x] E4：8 格均完成 N 次真实 OSS PUT/complete-upload、N 张 validation ready、Series ready 和 Study finalize ready。
- [x] E5：8 格均跑通 Task、Outbox、Relay、RabbitMQ、Worker、冻结 Config/Prompt/ModelPool/Connection、真实 Provider、receipt 与 DecisionFinalization。
- [x] E6：8 格均得到 revision 1 final Report，并验证 `reports/current`、`reports/history` 与 Task current pointer 一致。
- [x] E7：cat/dog × 2/3/4/5 Primary 验收矩阵 8/8 PASS；每格 receipt requested/sent identity 与 Snapshot 一致，image count=N。
- [x] E8：8 份脱敏 PASS evidence 保存到 `docs/evidence/xray-2to5-runtime/20260830T130608Z/`；工程链已资格化。
- [ ] E8 后增加 `image_assessments` 结果合同：逐图记录 assessment/quality/limitations，并强制 image_id 集合完整覆盖 Task Snapshot 的 N 张输入。
- [ ] [P2] 在真实英文 clinical context 接入前，审计 leakage 禁止 token 的匹配边界，避免 `path/score/gold/truth` 子串误伤合法上下文；不得借此放宽标签泄漏防护或增加医学判断。
- [ ] 后续接入 DICOM `ViewPosition` 的确定性提取和来源优先级；不得从文件名、目录或图像尺寸猜测体位，也不得覆盖调用方冻结值而不留冲突证据。
- [ ] 后续评审独立 `xray_projection_qc`；仅提供体位一致性提示，不进入诊断主链或医学结果 owner。
- [ ] E0–E8 后默认执行 R4A Evaluation DB/metadata/Alembic、R4B Dataset、R4C Gold/Scorer、R4D Runtime 等价 Runner、M1、Primary/Targeted 单变量优化和 Holdout。

以下 S0–S6 为用户明确优先展示能力时才启用的可选支线，不是 E0–E8 后默认下一阶段：

- [ ] S0：冻结器官分割的产品语义、label set、模型/版本、输入格式、mask/overlay/manifest 格式、坐标系、partial success 与非诊断声明。
- [ ] S1：在取得迁移授权后，按独立 opaque `VARCHAR(64)` 主键、无 foreign key、无数据库 enum 的规则增加 `segmentation_job`、`segmentation_artifact`、`segmentation_outbox`。
- [ ] S2：按 `API -> Service -> CRUD(DalBase) -> Model/MySQL` 实现 5 个分割接口：创建、查询状态、查询产物列表、查询产物详情、取消；ID 只放 query/body。
- [ ] S3：实现独立 Segmentation Worker/Provider、幂等、租约、重试、取消、超时和 dead-letter；不得复用诊断 Report owner。
- [ ] S4：实现原图输入、mask、overlay preview、manifest、SHA256、OSS 路径和 signed URL 合同，并验证坐标与原图一致。
- [ ] S5：前端实现原图/叠加图切换、器官筛选、透明度和非诊断免责声明；分割失败不影响报告查看。
- [ ] S6：完成分割独立 happy path、partial success、失败/取消/重试/过期 URL、权限隔离和诊断非回归验收。
- [ ] 数据库迁移和新的测试脚本仍需用户另行明确授权；当前 Postman 授权不自动扩展为迁移或测试脚本生成授权。

## 已完成基础

## P0 审查修正（进入后续能力前）

- [ ] 为 FamilyRouting 建立版本化输入/输出结构：唯一 Family、唯一 Focus、来源 Finding、coverage proof、reason codes、contract version、预算/deadline/资格门禁。
## Prompt（提示词）运行合同与医学优化

- [ ] Q2 Primary Baseline Freeze（主读基线冻结）：E0–E8 与 R4A–R4D 后冻结 Prompt、模型、病例、Revision、影像哈希、Schema 和评分器，形成 M1。
- [ ] Q3 Primary Prompt A/B（主读提示词配对实验）：在 M1 后按 Failure Bank 一次只改变一个 Prompt 主要变量。
- [ ] Q4 Model A/B（模型配对实验）：第二 Provider 工程资格化后，在同 Prompt 和同病例条件下比较模型。
- [ ] Q6 Release and Rollback（发布与回滚）：只通过新不可变 Prompt/Config 发布；回滚激活旧 Config，不原地覆盖历史模板。

## 后续实施依赖顺序

### E1 Primary Runtime（仅主读真实运行链）

- [ ] 审阅现有两版未应用迁移对旧 AI 表和数据的兼容性，形成 backup（备份）、baseline/stamp（基线/标记）、write set（写集合）和 rollback（回滚）方案；未经授权不 upgrade。
- [ ] 创建并迁移 `ms_image_eval（评测库）`；主库迁移后确认 `ai_config_record` 和当前 Connection/Pool/Prompt schema 与 ORM 一致。
- [ ] [DEFERRED_BY_USER] Runtime/Admin JWT（运行时/管理端令牌）生产信任和密钥生命周期；当前不作为核心诊断链开发项，公网/跨团队/管理控制面上线前再恢复。
- [ ] 保持数据库 Connection/Model Pool/Prompt/AI Config 的冻结与审计事实；`secret_ref` 仅作为遗留兼容元数据，不再配置 `MS_IMAGE_AI_SECRET_*` 或进入 Worker 鉴权链。字段级删除等待明确迁移授权。
- [ ] [DEFERRED_BY_USER] 资格化 Artifact（证据产物）签名键；当前生产主链未读取 Compose 中三个 signing 环境变量，不阻断 Task→Report，合规证据包上线前再恢复。
- [ ] [DEFERRED_BY_USER] 验证 Runtime/Admin JWT、Artifact signing 与生产安全/证据生命周期；不阻断当前核心诊断链。

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

## XRay 单一 Prompt 与接口物种参数（2026-08-26）

## 当前开发入口（2026-08-25）

- [x] D2 clinical context v1 已实现并冻结：严格 allowlist/source、Snapshot v3 policy/SHA、Prompt 消费与 Evaluation export 投影均已存在；剩余是 `ms-ai-fast` 上游传真实数据。
- [ ] 当前第一优先级不是医学扩展，而是把既有 E1 固化为可重复的“上传影像 -> AI -> 第一份 final Report -> current/history 读取”一键工程验收；连续通过后再进入 Evaluation/M1。

## 宠物档案（当前不创建）

- [ ] `pet_profile` / `medical_record` 不在当前 ms-image Model 清单；除非用户明确要求新增，否则不建表、不生成迁移、不增加 Service。
- [ ] 若未来启用猫/犬自动选择，由上游按 `session_id -> medical_record -> pet_profile -> species` 解析，再把 `species` 冻结进 Task Snapshot，并通过 `SAFE_STUDY_CONTEXT_JSON.species` 交给唯一 `xray_primary/common` Prompt；Worker 不得运行时回查档案。
- [ ] 上游 `ms-ai-fast` / 病例集成尚未实际执行 `session_id -> medical_record -> pet_profile -> cat|dog -> POST /tasks`；当前 `ms-image` 的 Task 冻结合同已就绪，但不能把调用方手填 `species` 当作已完成档案继承。

## 2026-08-26 — Runtime Schema 重建后待办

- [x] 以当前 `apps/backend/models/__init__.py` 注册 Model 为唯一清单创建 20 张表；P1-B 正式追加迁移后真实主库现为 `20260828_01`。这不证明从空库完整 replay。
- [x] 导入并激活已确定的 XRay Prompt/Config，同时建立 Connection 与 ModelPool 数据。
- [x] 已创建 Session/Study/Series/Image、冻结 Task Snapshot 和 Outbox 事实，并完成真实多视图 v3 任务。
- [x] 已在实际 Worker 注入 AI Platform 成对配置，运行完整冻结任务链并采集脱敏证据。
- [ ] 在用户没有新增 Model/表要求前，不再执行数据库删表或 Model 用途筛选。

## 2026-08-26 — 快速上线 Prompt 收敛

- [x] 采用接口传参区分猫狗：`POST /tasks` request body 对 `diagnose` 必传 `species=cat|dog`；不引入 `pet_profile` / `medical_record` 自动选择链。
- [x] Task Snapshot 冻结 `species`，同一 Prompt 通过 `SAFE_STUDY_CONTEXT_JSON` 获得物种上下文；Prompt source identity 不按物种分叉。
- [x] XRay Prompt 身份收敛为 `xray_primary/common` exact-only；旧 cat/dog/default Nacos 版本不进入新链。
- [x] common Prompt 已发布、导入、编译并激活；冻结 Task 与 Worker AI 全链已跑通，当前 active 为 Primary v2 Config。


## 2026-08-27 — 未来统一服务数据库边界

- [ ] 在任何 Model/表变更前，明确范围是“仅 XRay 与 fast 上游兼容”还是“迁入 ai_doc/ai_pic/ai_video/ai_voice 全部模块”。
- [ ] 若仅 XRay：保持 Study 强耦合 Task，不新增通用病例/消息/媒体表；只设计必要的外部 ID/状态/API 适配。
- [ ] 若全量统一：先评审 `pet_profile -> medical_case_record -> session_record -> modality input -> task_record -> report_record` 的领域合同，再决定 Task 通用输入引用和消息表；不得直接复制 fast DDL。
- [ ] 若开始实施，先提交字段级目标模型、唯一约束、索引、状态映射和兼容 API 方案供用户确认；未获授权不生成迁移或执行 DDL。


- [ ] 用户确认统一服务命名合同后，再输出字段级 canonical 表字典与 legacy -> canonical 映射；确认前不执行物理重命名。

## 2026-08-27 — Prompt 专项后续

- [x] 盘点当前 XRay Prompt：Primary-only 在线缺失 0 个；旧 catalog 20 个资产不转换为 20 个 Nacos Prompt。
- [x] 本地创建唯一缺失的未来 Targeted Frozen Entry 候选，并验证三变量渲染与单 user message 组装。
- [x] 按用户“先补全 Prompt 链并跑通”的新优先级，已以猫狗 `4.0.0` 双模式 Prompt、experiment Config 和 FamilyRouting v2 完成 Targeted 工程接线。
- [x] 已以 C2 v2 版本化收紧 `complete_medical_result`，明确 Finding、coverage、source_refs、targeted_candidate 等结构和技术引用完整性；医学准确率仍待 M1。

## 2026-08-27 — Primary 主链当前唯一执行清单

- [x] 完成全部 AI 能力与 Prompt 资产本地盘点：`docs/refactor/25-ms-image-complete-ai-capability-inventory.md`。
- [x] 完成 Primary 主链未完成功能清单：`docs/refactor/26-ms-image-primary-chain-incomplete-capability-checklist.md`。
- [x] Primary canonical Prompt 本地资产、Nacos 发布与写后回读；当前不缺 Primary Prompt 正文。
- [x] 已只读复核 API/Worker/Relay 使用同一数据库基线和当前 20 张 Model 表；从零迁移重放仍未证明。
- [x] 导入 canonical Primary Prompt，建立 Connection/单 lane ModelPool，编译并激活 `xray_diagnose/global/global` Config。
- [x] 已建立同一真实 Session/Study/Series/Image/OSS 与 ready Revision，并完成真实 E1-MV。
- [x] 已创建冻结 Task Snapshot 与 Outbox，启动 Relay/Broker/Worker，跑通 OSS -> Platform/Provider -> Attempt -> Stage -> Report。
- [x] 资格化真实 duplicate delivery，并收集同一 Task 非敏感幂等证据。
- [x] 已资格化 cancel/late-result、unknown unsupported/lease 恢复、P1-A 自动 reconcile 调度与 P1-B 持久有界终止。
- [x] E1 已通过；TargetedReview 工程调用因用户新优先级已在显式 experiment scope 中资格化。M1/Holdout 前仍不开始医学改善声明、Retry、Fallback 或 ms-image 多 lane Race。


## 2026-08-27 — Primary 控制面安全收口

- [x] API Connection Create/Update/Response 删除 `secret_ref` 业务输入输出。
- [x] Connection SHA、Config Snapshot 和控制面 Audit 不再冻结 `secret_ref`；DAL 禁止更新该字段。
- [x] 保留旧 `NOT NULL` 列空字符串兼容占位，不改表、不迁移。
- [x] 定向 Ruff、compileall、diff check 和 backend 全量测试通过。
- [ ] 将 `AI_PLATFORM_OPENAI_BASE_URL + AI_PLATFORM_API_KEY` 成对注入正式 Worker 启动环境，并运行同一冻结 Task 全链。

## 2026-08-27 — 接口逐项补齐清单

- [x] `POST /series`：新 Series 与 Study manifest/revision 同事务推进；幂等重放不重复推进，CAS 失败整体回滚；未改表/Schema/迁移。
- [ ] Admin Report：决定停用 publish；若保留 void/revision CAS，先授权并补 `report_record.state_version`、reason、actor、audit。
- [x] `GET /tasks?id=`：已补 `current_report_id`、`started_at`、`finished_at`、`next_retry_at` 并明确终态；Task retry_wait 写入仍是独立未实现能力。
- [x] `GET /images/page`：已按 Series、owner、绝对最新 logical version 和显式历史版本完成分页恢复；精简 DTO/列加载、稳定排序和 owner 隔离已验证；大 Series filesort 性能待等量数据资格化。
- [x] `GET /tasks/page`：已按 Session/Study/owner、status/type、UTC 时间闭区间和稳定倒序完成；使用精简状态 DTO，不返回完整 Snapshot；大 Session 性能待等量资格化。
- [x] `GET /reports/current?task_id=`：已完成 owner-safe current 读取；合法空 pointer 返回 null，pointer 漂移和不可交付状态 fail-closed，不固化宽 Report view。
- [x] Image prepare/replace D1 代码链：projection + Service provenance -> `series-image-manifest.v2` -> `task-request-snapshot.v3` -> Prompt 逐图 refs / Snapshot-only Provider input -> `ai-image-receipt.v2`；replace 继承/更正规则已固化。真实两视图 E1-MV 和 legacy adoption 仍是独立待办。
- [x] Task Snapshot manifest 兼容选择：全 D1 stored SHA 匹配冻结 v3；全 legacy stored SHA 匹配冻结现有 v2；neither/mixed fail-closed。没有删除 `object_version_id`，没有在 Task create 中写回 Study/Series。
- [x] 清理本地重复 imaging Worker，只保留一组当前源码 Worker；DeepSeek 已用新链验证 completed/review_required/Report final。
- [ ] 重启 Runtime API 使本轮 v2/v3 兼容代码生效；随后将 `e3f976…` 对应一致但 validating 的 Study 正常 finalize。
- [ ] `POST /tasks`：以严格 allowlist 冻结 clinical context，不新增 `/sessions/context`。
- [x] Session complete/cancel：已采用完整诊断会话语义；complete 阻断非终态 Task，cancel 原子写取消请求，Task create 与终态推进共用 Session 行锁；跨连接发布环境资格化保留为运行验收。
- [ ] health/readiness 分平面：Runtime 公共 `/readiness` 与 AI Control `/health`、`/readiness` 已完成；AI Control Nacos Prompt Client capability 已真实通过，当前 503 只剩 `ADMIN_SECRET_KEY`。仍需 Evaluation Control 独立 health/readiness，以及 Admin operations 平面级 degraded 返回。
- [ ] Prompt import：拆分 DB 预检、Nacos I/O、DB 持久化短事务。
- [ ] 修复 Alembic baseline 与 Evaluation 独立 DB/metadata/migration 后，再逐项开放 Evaluation Job/Run/Artifact API。

## 2026-08-27 — 本地无 Docker 全链路（已完成）

- [x] 本地三进程启动脚本 `scripts/dev/run_local_chain.sh`（API 8010 + relay + worker）
- [x] HTTP API 全链复跑脚本 `scripts/dev/run_e2e_local.py`（session -> study -> series -> 上传 -> 校验 -> finalize -> task -> report）
- [x] dev JWT 工具 `scripts/dev/gen_dev_keys.py` + `scripts/dev/issue_dev_token.py`；`scripts/dev/keys/` 已 gitignore
- [x] 2026-08-27 真实全链通过（证据在 validation.md）

## 2026-08-27 — 本地无 Docker 全链路后的后续（保留）

- [ ] 将 `scripts/dev/` 三个脚本的依赖和要求（ms-ai-fast/.env 平台凭据、本地 MySQL/RabbitMQ/Redis、base python3.12）写入 README/USAGE 或 docs，减少后续会话重新摸索
- [ ] 在本地最终部署形态下重放同一条 Task 链（当前已通过一次，脚本可复跑）
- [x] 当前功能范围的 P1 已关闭：P1-A 自动 reconcile 与 P1-B unknown 有界终止已完成；P1-C Runtime/Admin JWT 与 Artifact signing 延期到生产安全阶段

## 2026-08-27 — 29 号 post-C1 实施顺序

- [x] C1 happy-path：在 `ImagingExecutionService -> ReportService` 持久化边界投影嵌套 medical status，ReportService 拒绝非法列入参；真实 E2E 新 Task/Report/content 为 `review_required`，v1 Stage 仍为 `produced`。
- [x] C1.1：已严格拒绝 availability/complete-result 损坏组合，提取共享状态合同，并在 DAL 前验证 Report 列与 content 一致；focused、全量与单一新 Worker 真实 E2E 均通过，无表/迁移变化。
- [ ] 盘点既有 `task_record/report_record.medical_status=produced` 行；未经数据修正授权不回填，不从 Findings 猜状态。
- [x] P1-A：独立 Celery Beat singleton 是默认关闭的唯一仓库 owner；queue route、本地/Compose 进程定义、观测、重叠 CAS、非人工自动触发、崩溃/lease 恢复与无替代 POST 均已通过。
- [x] P1-B 独立关闭 unsupported unknown 有界终止：字段/迁移、真实 Beat/Worker 和全链技术失败均已通过，未打包医学行为。
- [ ] [DEFERRED_BY_USER] P1-C Runtime/Admin JWT 与 Artifact signing 生命周期；不阻断当前核心诊断链，生产安全阶段再独立关闭。
- [x] C2：已保留 v1 可重放并完成显式 CompleteMedicalResult v2；Finding/Coverage/SourceRef/summary/impression 由模型输出，Python 只做 Schema 与本次 receipt 技术引用校验；真实 Primary v2 全链通过。
- [x] D1 代码完成：`Image.projection + provenance -> canonical manifest -> Task Snapshot v3 -> Prompt/Provider/receipt v2`；未新增 projection summary、表、字段或迁移。真实 E1-MV 工程验收已完成，但不构成医学资格化。
- [ ] D1 legacy adoption：当前 8 张 ready Image projection NULL、8 个 Series 为 legacy manifest；若用户要求旧 ready Study 无重传直接进入 v3，先提交确定性 write set/回滚方案并取得存量修正授权。
- [x] D2：严格 Task clinical context v1 已实现并冻结进 request snapshot；不新增 Session context，不从报告/Gold/模型输出反推。
- [x] E1-MV：真实 VD+Lateral 病例已验证 Snapshot/Prompt/Provider receipt/Report 血缘；输出未作为医学准确率证据。
- [ ] M1：复用 Evaluation Job/Run/Artifact 建立可信 Gold/Scorer/分母/Failure Bank；当前 Targeted 仅有工程可运行资格，M1 前不做 Prompt/Model 医学效果声明、Retry、Fallback、Race。
- [x] Task page 已在上游恢复消费者合同明确并获用户授权后单独实现；不改变其非医学主线定位。
- [ ] Report view、两步 intake 和 segmentation 仅在真实消费者合同明确后实施；segmentation 保留为 P2 产品需求，但派生 Image role 本身不是完整功能；当前不做 release-state/fixed-bank 新 API。

## 2026-08-27 — API/数据库审计新增待办

- [ ] 用户确认 Report 产品语义：建议 `final` 直接可交付，publish 不进入主链；明确 void 后 current/history/by-id 的可见性与 Task delivery state。
- [ ] 若保留 Admin publish/void：设计 `report_record.state_version`，并决定 void reason/actor/audit 的最小持久合同；先给 write set 与迁移/回滚方案，获授权后实施。
- [ ] 在任何新迁移前拆分在线与 Evaluation metadata/Alembic 基线，确保在线 16 表和 Evaluation 4 表均可从空库独立重建；明确当前主库四张空 Evaluation 表的清理方式。
- [ ] 创建并迁移真实 `ms_image_eval` 后，再资格化 Evaluation Job/Export/Run/Artifact；医学 Scorer/Gold/denominator 仍按 M1 单独批准。
- [x] `TaskResponse.current_report_id`、`started_at`、`finished_at`、`next_retry_at` 已补；`next_retry_at` 仍只有读合同。
- [x] 补受 caller scope 的 `GET /tasks/page`；精简 DTO、Session/Study scope、双层 owner 隔离、分页和真实 MySQL 只读验证已完成。
- [x] 补受 caller scope 的 `/reports/current?task_id=`；宽 `/reports/view` 仍等 CompleteMedicalResult v2 后再定。
- [ ] 按真实消费者决定是否补 Study/Session page；Image page 已完成。Stage 摘要要么从 27 号合同删除，要么增加受权限保护的 Task stage 查询。
- [ ] 将 27 号残留错误在下一份实施文档中纠正：四应用外部 root path、Evaluation cancel 为 POST、TaskResponse 无 stage summary、Task 医学状态不得写 `produced`。

## 2026-08-28 — 真实 E1-MV 新阻断

- [x] 关闭 Provider fenced JSON 技术兼容：ms-image 仅做唯一完整小写 `json` fence 解包并复用原冻结 Schema，没有增加医学或 projection 规则。
- [x] 将 definite Provider response 的发送事实与结果解析解耦；JSON/Schema 失败会持久化不含 URL 的 sent manifest、image count 与 `ai-image-receipt.v2`，Attempt/无 Winner Logical Call 投影一致。
- [x] 修复 `scripts/dev/run_local_chain.sh` 的 `${PYTHONPATH:-}` 启动兼容，并以 atomic owner lock、进程预检、consumer=1/heartbeat/readiness 门禁关闭重复实例与旧 Worker 混跑风险。
- [x] 修复后复用 Study `121a23ff51e14aa593167d297e508fdf` / Revision `a94d354e6fe44e3596f4bc8d10960982` 创建 Task `baef4d8619494a75aac7c2c7ef805c87`，已取得 completed、合法医学状态、receipt v2 与 Report final。

## 2026-08-28 — 当前改动架构审查后续

- [ ] P2 保持 `AI_PLATFORM_* -> GatewayClient` 为唯一可执行出站合同；将 Connection `base_url` 明确为非敏感 Platform 路由元数据，并补 frozen URL 与 Worker URL 规范化一致、错配 fail-closed 的既有测试合同。当前真实值已一致，不按 P1 故障处理。
- [ ] P1 拆分 Compose env/secret 注入，保证 `AI_PLATFORM_API_KEY` 不进入 AI Control、Evaluation Control 等无 Provider 调用职责的进程；先保持当前本地配置无 Secret 输出。
- [ ] P2 将 Runtime 支持的 `api_format` 集合提取为共享无状态合同，并在 Connection create/update/validate 与 Config compile 阶段拒绝不支持值。
- [ ] P2 将冻结 Config 纯验证器及其错误合同移到 `core/ai` 或等价无状态共享层，消除 Runtime 对 `services.ai_control.service` 的反向 import；不得复制第二套 verifier。
- [ ] 以上修正必须保持 Primary-only、单 lane/max_attempts=1、Worker 不回读 latest Prompt、Python 不补医学结论、现有 API -> Service -> DalBase 分层和 v1 Task 重放兼容。

## 2026-08-28 — 最小影像到报告主链固化计划

- [x] 确认并收敛 2 个 Relay、3 个 Worker parent，验证单 launcher + 单 API + 单 Relay + 单 Worker owner、Beat=0、broker consumer=1。
- [x] 冻结最小完成定义：上传成功、Image ready、Study finalized、Task completed、Report final、current/history 可读取；第一阶段不依赖 publish。
- [x] 增强既有 `scripts/dev/run_e2e_local.py`：图片/species/projection/body part/context/repeat 参数化，修正 current/history 与 Snapshot v3/D1/D2/C2 断言，只输出非敏感工程证据。
- [x] 修复 `scripts/dev/run_local_chain.sh` 的未设置 `PYTHONPATH` 兼容、重复进程探测、atomic owner lock、只清理自有 PID 和严格 readiness 门禁。
- [ ] 建立主链验收矩阵：单图、多视图、重复投递、Provider Schema 失败、cancel/late result；优先复用现有测试和 E2E harness。
- [ ] 主链稳定后，经授权新增 `report_record.state_version` 与 Response 字段，真实关闭 publish/void/revision CAS 缺口；迁移和审计字段范围单独确认。
- [ ] 接通 `ms-ai-fast`：`pet_type=1猫/2狗 -> cat|dog -> Task.species`，由上游创建 ms-image 资源并轮询 Task/Report；Worker 不回读 mutable pet profile。
- [ ] 上述工程链连续通过后，再创建/迁移 `ms_image_eval` 并启动 M1；JWT/signing/Secret 最小权限继续作为生产安全独立计划。
- [ ] 将当前约 130 条 Git 状态按 Runtime/Worker、C1.1/D1/D2/C2、P1-A/P1-B、E2E/launcher、文档/handoff 分组审阅；不立即整包提交，不包含 `.env`、Secret 或运行产物。

## 2026-08-28 — D2 Synthetic 资格化后的下一阶段

- [ ] 优先接通 `ms-ai-fast` 的真实调用：`pet_type=1/2 -> species=cat/dog`，并从请求时已存在、无标签泄漏的事实生成现有 `TaskClinicalContext v1`；不得让 ms-image 回读可变档案或新增第二个 context 合同。
- [ ] 用固定工程病例量化 Provider parse/schema/source-ref fail-closed 比例；已观察一次 `provider_result_source_fact_mismatch`，当前后端正确拒绝，不得静默重试或在 Python 猜测/纠正 source refs。
- [ ] 若用户优先需要报告发布治理，先获得 `report_record.state_version` 与迁移授权，再实现/验证 publish、void、第二 revision CAS 及最小审计字段。
- [ ] 真实上游 D2 接线稳定后，再申请创建隔离 Evaluation 库和 M1 所需表/Gold/Scorer；未完成前不声称医学准确或发布可用。

## 2026-08-29 — 猫狗独立 Primary Prompt 后续

- [x] 完成 common/cat/dog exact-only Prompt Source、Task species Config 路由、Config/Profile/Prompt 绑定门禁与现有测试改写。
- [x] 完成猫狗本地 `.md` Prompt、Nacos `3.0.0` 精确发布回读、AI Control Prompt/Config 生命周期和双 active slot。
- [x] 完成猫真实 Runtime 资格 E2E：Config key、Prompt SHA、Snapshot v3、C2 v2、final Report/current/history 均通过。
- [x] 将未来狗 SourceRef 失败精确区分为 series ID、projection、manifest SHA 三个脱敏错误码；旧通用失败因正文未持久化保持 `UNKNOWN`，不猜测归因。
- [x] 新诊断代码下狗 `3.0.0` 连续 4 次 E2E completed/final；当前不发布无证据的 `3.0.1`，猫狗路由与 Runtime 工程资格已通过。
- [ ] 用多个固定病例建立 Provider parse/schema/三类 SourceRef fail-closed 分母；只有同一具体字段出现可重复失败时，才评审对应 Prompt 新版本。
- [ ] 猫狗 Runtime 均资格化后再开始正式医学病例标注、Scorer、Failure Bank 与 M1；当前 sidecar/文件名不作 Gold。

## 2026-08-29 — 全链 Prompt 工程资格化后续

- [x] 猫狗各新增一份 `4.0.0` 双模式 Markdown Prompt，同时承载 JointPrimaryReader 与 TargetedReview；确定性 Stage 不新增 Prompt。
- [x] Nacos 猫狗 `4.0.0` 均完成 draft/submit/publish、精确版本回读和本地规范化 SHA 对账；未覆盖历史版本。
- [x] 猫狗 `xray_targeted_review_v2` experiment Config 已 validated/active，只能通过 `XRAY_TARGETED_EXPERIMENT_SCOPE_KEY=full-chain-local-v1` 选择。
- [x] 猫狗真实 Targeted 链均完成 5 Stage、2 AI Call、targeted owner、final Report、C2 v2 与 receipt v2。
- [x] 验证无合法 `targeted_candidate` 时保持 `primary_final` 和单 AI Call，不为通链强制 Targeted。
- [x] 冻结 `4.0.0` 作为工程基线；新优化使用新不可变版本，不原地改动 Nacos/Prompt/Config。
- [ ] 请数据提供方确认不可变 image-sidecar pairing manifest，并审计 `ABN/NOR`、Disease、annotation 的来源、时点、去重与仲裁。
- [ ] 建立真实医学 Scorer、猫/狗分层分母、development/Failure Bank/Holdout，并资格化隔离 `ms_image_eval`。
- [ ] 在修改 `4.0.0` 前，先用固定猫狗病例建立 Primary/Targeted 分层的 parse/schema/series/projection/manifest 技术分母；当前复验的 Targeted 小样本为 2 成功/1 manifest 失败。
- [ ] 第一个优化切片只调 Primary Prompt：猫狗分开、同病例/模型/Schema/Scorer，一次只改一个主要变量。
- [ ] Primary 达到预定门禁后，再独立优化 Targeted 候选质量、FamilyRouting 门禁和 TargetedReview 反锚定/完整输出。

## 2026-08-29 — 历史路线：由 2026-08-30 Runtime E2E 优先级覆盖

以下 R0/R4 项仍是后续工程与医学治理工作，但不再阻塞当前 E0–E8 的 2–5 图 Runtime 全链跑通。

- [ ] [P0] R0A：实现并冻结 `xray-baseline-manifest.v1` 的生成、校验、证据目录与 fail-closed 规则。
- [ ] [P0] R0B–R0D：记录精确 Git/worktree 状态，回读 Prompt/Nacos exact version，并冻结 Config/Profile/Schema/ModelPool/Connection 身份；不得覆盖当前脏工作树。
- [ ] [P0] R0E–R2：在唯一 owner 环境完成工程 E2E、事实 owner map 和 `engineering-denominator.v1`；输出不得当作 Gold。
- [ ] [P0] R4A：设计并在取得用户授权后实现 Evaluation 独立数据库、独立 metadata、独立 Alembic env/migration、empty-db replay、existing-db upgrade 与 readiness。
- [ ] [P0] R4B：建立不可变 image-sidecar pairing、病例级去重/split、标签来源/时点/泄漏审计和 Dataset freeze/retire 合同。
- [ ] [P0] R4C：建立 Gold ontology、双盲/仲裁、医学 Scorer 版本、Failure Bank 与猫狗分层指标；不得继续使用 Fake scorer 声称医学结果。
- [ ] [P0] R4D：在现有 Evaluation 外壳中接入 Runtime-equivalent candidate runner，冻结 Prompt/Config/Pipeline/ModelPool/Connection/Schema/receipt 并保存可重放证据。
- [ ] [P1] 补齐 Provider、Model、Connection 独立变量的实验身份和执行合同后，才允许 R7 分离 A/B；当前只能记为不支持/UNKNOWN。
- [ ] [P1] 在 R4D 与 R4C 完成后执行 R9 same-Prompt Targeted A/B，不得用不同 Prompt 版本宣称 Targeted 增量收益。
- [ ] [P1] R10 按三类发送事实实现 Retry/reconcile；涉及数据库字段或迁移时另行取得用户授权。
