## 2026-09-03 — diagnose 主链工程资格已关闭

- [x] TargetedReview 合法候选真实触发，Stage/Call/Attempt/Provider/3 图 receipt/Prompt/Config/Model/lineage 全部门通过。
- [x] ReportGeneration 独立零图片 AI Stage 真实调用，Stage/Call/Attempt/Provider/0 图 receipt/Prompt/Config/Model/lineage 全部门通过。
- [x] 同一 diagnose Task `ae3c77dd32a34a938eaee6f167d438d6` 的 8 Stage、5 Call、5 Attempt、唯一 final Report 全链通过。
- [x] 保持 Python 不生成 targeted candidate、不重写医学结果、不放宽 projection/lineage validator。
- [ ] 后续新鲜全链回归固定使用 `/Users/mozhicheng/workspace/documents/X光_没问题_全量过滤`，并为每张图提供真实 projection。
- [ ] 医学准确率需另建可信 Gold、Failure Bank、Scorer 与 Holdout；当前继续 `UNKNOWN / NO-GO`。

# 待办清单

## 2026-09-03 — Git 收口与按流程模型路由

- [x] 审计 tracked/untracked 内容、忽略文件、密钥风险与 handoff archive 引用完整性。
- [x] 创建功能提交 `ee2fa3a`，保存 X-Ray Runtime、宠物档案、Prompt/Schema/Postman 与测试资产。
- [x] 创建补充提交 `2b7d66b`，保存按物种校验 full-chain Config 的 harness 改动。
- [x] 提交现有文档和完整 handoff 历史，maintenance 最终无告警，并推送 `codex/xray-anatomy-localization-v1`。
- [x] 创建并推送 `codex/per-flow-model-routing`，已设置 upstream；业务实现尚未开始。
- [ ] 新分支后续目标：按接口/Stage 配置 `model` 与 `reasoning_effort`，先完成本仓库调用边界及跨仓库平台透传审计，再经用户确认实施范围。

## 宠物档案迁移后续资格

- [x] 完成宠物档案与 `pet-info` 的 Model/Schema/CRUD/Service/API 代码迁移和静态/现有测试资格。
- [x] 创建并审阅独立 Alembic revision `20260901_01`，在目标 MySQL 创建 `pet_profile`、`pet_profile_history`、`pet_info`，且未夹带既有 `secret_ref` comment drift。
- [x] 完成 legacy 档案与品种目录映射及受控导入：5091 个档案、152 个品种、0 个源历史；确定性 opaque ID、source identity 与 request ID 保证幂等，第二次执行新增 0。
- [x] 完成跨 schema 数量、缺失/额外、owner、species、status、weight、唯一性及三表 metadata 只读核对。
- [ ] 如需要上线前动态资格，运行真实 HTTP API 的创建/查询/更新/CAS 冲突、归档/恢复、history 原子性和 `pet-info` 查询 E2E；当前数据库建表与数据迁移已完成，但该 API Runtime E2E 未运行。
- [ ] 如未来需要体格数据、医疗记录或体征趋势，必须作为新的独立业务切片重新审核模型边界；不得默认补入本次档案迁移。
## 当前优先级 — xray_quality_control / BatchImageQualityReview

- [x] Quality 使用独立 Task，不作为 diagnose 内部前置 Stage；首要职责为逐图部位识别、观察投照位和基础质量，不做疾病诊断或 Report。
- [x] 现有链路接入、Quality JSON Schema/validator、Stage Registry、Runtime POST/GET、Prompt source/import、AIRequest 与 ConfigCompiler 已完成并通过既有静态验证。
- [x] Cat/Dog Nacos `1.0.0` 已不可变发布并 exact 回读；DB Prompt 已 validated，`xray_image_quality_cat/dog@1.0.0` Config 已 active。
- [x] Cat `cat-02` 真实工程链 PASS：1 Logical Call / 1 Attempt / 2 图 / accepted result / Task completed / 无 Report。
- [x] Dog `dog-02` 上传与 finalize 完成；历史首次 Quality POST 的 HTTP 409 已确认发生在 Runtime Task 创建边界，Provider 未调用；具体内部冲突子类型仍 UNKNOWN。
- [x] 完成 ready Dog Study 单次重试和 Dog 完整工程链：1 Logical Call / 1 Attempt / 2 图 / Provider HTTP 200 / accepted result / Task completed / 无 Report。
- [x] 完成写接口 commit-before-response 真实回归：新 Quality POST HTTP 201 后无等待立即 GET 200；取消后立即 GET 200；相同 request_id 重放返回同一 Task；本轮 Provider 未调用。
- [x] 按用户要求追加 5 次连续 Runtime-only 回归，5/5 全部通过相同门禁；累计 6/6 PASS，历史 409/立即不可见问题关闭，不再重复测试。
- [ ] [USER_AUTHORIZATION_REQUIRED] 6 个回归 Task 当前 queued + cancel_requested，Stage/Outbox pending；未来如需启动 Worker 观察其收敛为 terminal cancelled，必须单独授权，不得手工改库。
- [ ] Cat/Dog 部位、投照位和质量判断的医学准确率后续另行评估；当前保持 `UNKNOWN / NO-GO`。

## 当前完成 — 目标诊断链缺失 Prompt Nacos 先行发布

- [x] 盘点目标非分割诊断链 12 个 Cat/Dog Prompt identity；已有 Quality 2 个，确认缺失 StudyScreening、SystemAnalysis、PrimaryCaseAdjudication、TargetedReview、ReportGeneration 共 10 个。
- [x] 创建 10 个本地不可变 Markdown Prompt 资产，并通过 Jinja 解析、required variables 精确匹配、Strict 渲染和 Cat/Dog 固定身份检查。
- [x] 在 namespace `c0cc9e0e-0fed-4faf-bc57-e9bab46a78a9` 逐个执行 `1.0.0` 不存在预检，并通过 Nacos Admin `draft → submit` 正式生命周期发布；未使用 force publish。
- [x] 10 个 Prompt 均 status=`online`、latest=`1.0.0`，exact 回读规范化 SHA 与本地资产一致。
- [ ] [USER_SCOPE_REQUIRED] 若继续，选择并授权下一实现切片：优先 StudyScreening 的 Prompt Source mapping + Schema/validator + Stage contract；数据库 Prompt import/Config、Runtime 与 Provider 必须分开授权。

## 延后保留 — Anatomy Localization v1 外部资格化

- [x] 发布并 exact 回读猫狗两个 Nacos `1.0.0` Prompt；显式 namespace/release import/validate；创建、验证并激活两个不可变 Localization Config；diagnose active Config 未改变。
- [x] 外部写前实时重验 Nacos namespace、Data ID/version、Prompt/Schema/Label SHA、ModelPool/Connection/Platform identity、capability、generation、timeout 与预算；未发现同版本 SHA 冲突。
- [x] [ENVIRONMENT] 已确认 `MS_IMAGE_XRAY_DATA_ROOT=/Users/mozhicheng/workspace/documents/X光_没问题_全量过滤`；八份 manifest 与 28 张目标图的路径、SHA、size、JPEG 格式、sequence 和本地解码门禁全部 PASS。
- [x] 用户已明确授权使用 `/Users/mozhicheng/workspace/documents/X光_没问题_全量过滤` 从 `cat-02` 重新开始八格；运行前已重新回读冻结身份和 SHA，未发现漂移。
- [x] 首次旧 `cat-02` 已执行：1 Task、2 Stage、1 AI Stage、1 Logical Call、1 primary lane、1 Attempt、1 batch request 和 2 图 requested/sent/receipt 均成立；Provider HTTP 200 后因聚合错误 `anatomy_localization_image_lineage_mismatch` fail-closed。
- [x] 已执行停止门禁：未重试 `cat-02`，未运行 `cat-03/04/05` 或 `dog-02/03/04/05`，未增加 Attempt、修改预算或放宽 validator；Runtime/Relay/Worker 和队列已清理。
- [x] 已确认当前可访问范围内没有可恢复首次旧 `cat-02` 响应的既有只读审计：主库只保留聚合错误与 receipt，本机/`ms-ai-fast` 日志无命中，AI Platform 公开 OpenAPI 无 request/audit/trace/log 查询接口；该审计阶段没有发起新 Provider 请求。
- [x] 已获授权并完成无 migration 的最小失败可观测性：未来 lineage 拒绝使用图片 ordinal + 字段错误码；definite technical rejection 的 provider request ID、response SHA、actual model、usage 写入既有 Attempt/AICall 字段。全量测试和静态检查通过，未调用 Provider。
- [x] 用户授权后仅重新运行一次新 `cat-02`；Provider HTTP 200，最小可观测性精确记录 `anatomy_localization_image_1_projection_mismatch`、Provider request ID、actual model 和 response SHA。Task/Call/Attempt/Stage 严格失败，无 Report、无第二 Attempt、无重试，剩余七格未运行。
- [ ] [USER_DECISION_REQUIRED] 审核第一张图 `projection` 未原样匹配冻结 lineage 的原因；优先做不调用 Provider 的 Prompt/Schema/safe-context 行为分析，再由用户决定是否创建新的不可变 Prompt/Config 版本。禁止放宽 validator、覆盖现有 `1.0.0` 或自动升版。
- [ ] [USER_AUTHORIZATION_REQUIRED] 任何修订后的新八格需再次明确授权，并从 `cat-02` 建立新的独立资格化序列；当前不得直接续跑剩余七格。
- [x] 用户已于 2026-09-03 明确授权提交并推送 `codex/xray-anatomy-localization-v1`；已逐路径暂存，未使用 `git add -A`，脱敏运行证据仅按仓库现有文档/历史边界保存。

## Localization 完整关闭后的路线

- [ ] 独立审核 R4A 最终关闭或明确豁免；当前 `secret_ref` 注释漂移和 Docker 容器 build 仍是 R4A 的独立未关闭项，不回填 Localization。
- [ ] R4B Dataset 治理：建立不可变 image-sidecar pairing、病例级去重/split、标签来源/时点/泄漏审计、freeze/retire 合同。
- [ ] R4C Gold/Scorer：建立 ontology、双盲/仲裁、医学 Scorer、Failure Bank、猫狗分层指标和 Holdout；Fake scorer 不能替代医学 Scorer。
- [ ] R4D Runtime 等价 Runner：冻结并执行 Prompt/Config/Pipeline/ModelPool/Connection/Schema/receipt，保存可重放候选证据。
- [ ] R4B–R4D 完成后才建立 M1；之后才允许 Primary/Targeted Prompt 或 Model 单变量 A/B。

## 独立工程 backlog

- [ ] [MIGRATION_AUTHORIZATION_REQUIRED] 单独审阅并决定是否用最小 migration 修正 `ai_api_connection.secret_ref` ORM/物理列注释漂移；不得混入 Localization 或 R4A cleanup revision。
- [ ] [ENVIRONMENT] Docker daemon 可用后补 R4A Backend image build 与 `evaluation-migrate` 容器启动验证；不修改 Localization 业务代码。
- [ ] 定向修复 `run_e2e_local.py` 只读核验 session/engine 的 aiomysql event-loop teardown warning；除非与当前必改行完全重合，否则单独切片。
- [ ] Report publish/void/第二 revision/supersede 仍需 `state_version` 合同与 migration 授权；第一份 final Report 主链与该治理缺口分开表述。
- [ ] Retry/reconcile 后续若要安全自动重发，先补足 definitely-not-sent / sent / outcome-unknown 发送事实；不得在事实不足时盲发。
- [ ] 生产安全独立处理 Runtime/Admin JWT、Artifact signing、Compose Secret 最小权限和常驻进程资格；不能冒充医学或 Localization 证据。

## 长期兼容与数据质量

- [ ] 继续保护历史冻结 Task、v1/v2 Schema/Config 和已发布 Prompt；任何修正使用新不可变版本，不原地覆盖。
- [ ] 在真实英文 clinical context 接入前定向审计 leakage token 子串边界；不得借此放宽标签泄漏防护或加入 Python 医学判断。
- [ ] projection 当前仍由调用方显式声明；未来 DICOM `ViewPosition` 或 projection QC 必须保留来源与冲突证据，不得从文件名、尺寸或像素猜测并静默覆盖。
- [ ] Localization 未来如需 mask、crop 或 overlay，必须作为新的经审核产品合同；当前 v1 永远只代表 bbox，不追认像素级分割。

## 2026-09-03 — TargetedReview / ReportGeneration / 同 Task 全链关闭

- [x] 完成 TargetedReview Cat/Dog exact Prompt source/import、独立变量与 message contract、stage config binding、上游结果注入和递归 candidate fail-closed。
- [x] 完成 TargetedReview 定向/全量合同测试及静态检查；未调用 Provider、未启动 Runtime。
- [x] 真实 Primary 输出合法 candidate，TargetedReview 单 Stage 完整 Runtime 门 PASS。
- [x] ReportGeneration AI 独立零图片 Stage 实现并完成真实 Runtime 门 PASS。
- [x] StudyScreening → SystemAnalysis → Primary → FamilyRouting → TargetedReview → DecisionFinalization → ReportGeneration 在同一 Task 汇合 PASS。

## 2026-09-02 — 主链关联的 Localization 展示链接口（待授权）

- [ ] [USER_SCOPE_REQUIRED] 确认实施 Slice A：为 Localization Task 增加显式 `source_task_id`，并允许从 `diagnose` 主链 Task 查询关联摘要和当前结果。
- [ ] [MIGRATION_AUTHORIZATION_REQUIRED] 经用户单独授权后，为 `task_record.source_task_id` 和 source/type/time 普通索引编写 Alembic migration；不建新表、不加 foreign key。
- [ ] 冻结多任务语义：同一 source task 最多一个非终态 Localization Task；保留历史终态 Task；主链默认返回确定性的 current，历史可通过公共 Task 分页扩展查询。
- [ ] 创建时验证 source owner、`task_type=diagnose`、study/revision/species、冻结 manifest 和图片集合一致，并把 `source_task_id` 纳入 request snapshot/hash。
- [ ] 扩展主链查询，使 `GET /tasks?id=<diagnose_task_id>` 可选返回 Localization task ID、状态和结果可用性；Localization Task/结果响应回传 `source_task_id`。
- [ ] [USER_SCOPE_REQUIRED] 确认实施 Slice B：新增 `POST /images/prepare-view` 短 TTL 展示票据，严格使用 Localization 冻结 Snapshot 的精确图片版本。
