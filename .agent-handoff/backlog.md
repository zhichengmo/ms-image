# 重构待办

## 下一会话优先级

- [x] P0 首项：本地 `.env` 已退出版本控制候选；`.env.example` 已脱敏，Secret 扫描未发现其他常见凭据；资产 checkpoint 使用 `codex/ms-image-refactor`，禁止 `git add -A`、reset 或 clean。
- [x] 有界核对 P0 工程阻断：无 P1A 硬阻断；事务内外部 I/O 由 P1C 替换，旧 tenant/Trace 保留到目标 owner/Audit 合同闭环。
- [ ] 内部代码完全重构及开始实现已由新会话提示词明确授权；迁移脚本、新建测试脚本、真实数据库操作和生产发布仍分别确认。
- [ ] 实现 P1A：Session/Study/Series/Image 的 Model（数据模型） -> Schema（接口结构） -> DAL（数据访问层） -> Service（业务服务层）。
- [x] P1A Session：Model/Schema/SessionDal/SessionService 已实现并完成静态合同验证。
- [x] P1A Study+Series：双 Model/Schema/DAL 与单一 StudyService 已实现；revision/manifest ready 等待 Image 事实闭环。
- [x] P1A Image：Model/Schema/ImageDal/ImageService 已实现；上传完成和 ready 状态等待 P1C 可靠性链。
- [ ] 实现 P1B：API、dependency injection（依赖注入）和 route registration（路由注册），资源 ID 只使用 query/body。
- [x] P1B 非存储生命周期 API：Session/Study/Series/Image query/abort、resource auth、Service DI 和路由已注册；上传/replace/finalize 待 P1C。
- [ ] 实现 P1C：在现有 OSS 实现上收敛 ObjectStorageGateway，并闭环 Image validate Outbox/Relay/Worker + reconcile/revision，不接医学 Provider。
- [x] P1C ObjectStorageGateway：现有 OSS 实现已收敛唯一 Gateway，新 owner namespace 与 direct/multipart/完整校验合同完成。
- [x] P1C Image 事务性 Outbox：`outbox_record/OutboxDal` 与 `ValidateImageMessage` 已实现；Image `uploading -> validating` 和 `validate_image` 事件使用同一 DB 事务，重复事件执行 owner/version/hash 自校验。
- [x] P1C Relay：短事务 claim/confirm，事务外 Broker 发布，支持 retry/dead-letter、过期 relay lease reconcile 和 Broker 已接受但 DB confirm 冲突的至少一次恢复。
- [x] Relay 远端 SHA 门禁：实时确认 `origin/codex/ms-image-refactor` 与本地均为 `c4fe4c7415f70302d3be1f7c851a67280d1095fb`。
- [x] P1C 基础：已增加显式事务 session、canonical Series/Study manifest、Image validation lease DAL 和 StudyService 重算入口；未注册 Worker task。
- [ ] P1C Image validation Worker：消费前复核 Outbox owner/version/message；Image lease/CAS claim，事务外 Gateway 完整校验，短事务写 ready/quarantined 与 Series/Study 确定性 revision。
- [ ] P1C 代码完成后按授权如实标记 `CODE_IMPLEMENTED / NOT_MIGRATED / NOT_RUNTIME_VALIDATED`，不得提前通过 G4。
- [ ] 每个 P0/P1 业务 owner 垂直切片完成后运行静态验证、提交并立即推送；推送失败时停止后续实现并报告。
- [ ] P2 复用 P1C 的同一 Outbox/Relay，实现 Task + first Stage + Outbox 原子事务和零模型 replay。

## 后续阶段

- [ ] 实现 StageDefinition/Context/Result、StageRegistry 和固定 Profile Validator。
- [ ] 实现不可变 AI Config、prepared AI Call、预算、receipt 和 unknown reconcile。
- [ ] 实现 XRay Primary-only 医学链和不可变 Report/current pointer。
- [ ] Primary 基线资格化后实现 `xray_targeted_review_v1`，冻结 FamilyRouting + 最多一次 TargetedReview，并进行同病例 paired A/B；通过门禁前只允许 validation-only/shadow。
- [ ] 设计并经单独授权执行旧表语义迁移。
- [ ] 实现 `ms_image_eval` 4 表和 paired A/B 评测控制面。

## 不得提前执行

- 人工复核、在线 Evidence Graph、RiskGate、Topology/OOD 或 Harness。
- 任意 DAG、Stage 网络微服务化和 CT/MRI 医学执行链。
- 未授权迁移脚本、测试脚本和真实数据库变更。
