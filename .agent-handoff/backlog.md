# 重构待办

## 下一会话优先级

- [x] P0 首项：本地 `.env` 已退出版本控制候选；`.env.example` 已脱敏，Secret 扫描未发现其他常见凭据；资产 checkpoint 使用 `codex/ms-image-refactor`，禁止 `git add -A`、reset 或 clean。
- [ ] 有界核对 P0 工程阻断：Secret、事务内外部 I/O、身份、Broker、Trace/Audit、启动合同和证据新鲜度；不要停留在纯审计。
- [ ] 内部代码完全重构及开始实现已由新会话提示词明确授权；迁移脚本、新建测试脚本、真实数据库操作和生产发布仍分别确认。
- [ ] 实现 P1A：Session/Study/Series/Image 的 Model（数据模型） -> Schema（接口结构） -> DAL（数据访问层） -> Service（业务服务层）。
- [ ] 实现 P1B：API、dependency injection（依赖注入）和 route registration（路由注册），资源 ID 只使用 query/body。
- [ ] 实现 P1C：在现有 OSS 实现上收敛 ObjectStorageGateway，并闭环 Image validate Outbox/Relay/Worker + reconcile/revision，不接医学 Provider。
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
