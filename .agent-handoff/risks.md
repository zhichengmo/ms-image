# 风险、阻断与未知项

## 当前阻断

- 目标在线 10 表、评测 4 表和 5 个 Stage Service 尚未实现。
- 稳定 Provider（AI 服务提供方）资格、Secret 外置和医学发布证据未闭环，当前仍为 `NO-GO`。

## 当前风险

- `.env.example` 曾在本地工作树包含看起来可用的 OSS/STS/Gemini 凭据；现已清空且从未进入当前 Git 历史，但仍需凭据持有人完成轮换。
- 后续禁止 `git add -A`；必须逐路径暂存并在每次提交前复核 Secret，防止新的本地配置进入版本控制。
- 旧 AI 模型设计含明文 API key 字段，迁移不当会泄漏 Secret。
- 当前 `ingest_asset_in_db` 和 XRay technical worker 仍可能在数据库事务期间执行对象存储或 Provider I/O；P1C 必须改为短事务 claim、事务外校验、新短事务 CAS 回写，完成前不得复用为目标 Image Worker。
- 删除现有 TraceEvent 前若 AuditSink 未资格化，会丢失技术审计事实。
- 旧 `xray_accuracy_*` 表和 PASS-LOCAL Artifact 容易被误解为目标 schema 已实现。
- 过早启用 FamilyRouting/TargetedReview 会同时改变选择和模型调用，难以归因准确率。
- 多模态若只按 XRay 抽象扩展，可能持续污染公共表。
- 直接删除当前 tenant dependency 会削弱旧 API 授权；tenant claim 只能在目标 owner 授权闭环后退出。
- 目标 owner 授权的生产 subject/service identity 映射仍未知；P1 使用已验证 JWT subject/scope 与资源 `requester_id/subject_id` 校验，不删除旧 tenant compatibility dependency。
- 新旧 OSS key 过渡若另建 Gateway 或盲目重写对象，会产生双事实源、对象丢失和 owner 错配。
- 只完成 P1A 就宣称影像模块闭环，会遗漏 Image validate Outbox/Worker、故障恢复和 revision CAS。

## UNKNOWN（待确认）

- 生产 API/Admin/Worker 启动、资源、liveness/readiness 和 Broker 参数。
- 用户/service/admin/evaluation identity（身份）、scope 和资源归属合同。
- 旧 tenant claim 的兼容期限、目标 subject/service identity 映射和资源 owner 查询合同。
- 新 OSS owner namespace 的精确格式及历史 tenant-derived key 的只读退出门禁。
- OSS bucket/region/KMS/retention/legal hold 和孤儿对象宽限期。
- DICOM/PNG/JPG/视频/WSI 首期格式和转换范围。
- CT/MRI 的 Study/Series/SOP UID 和完成信号质量。
- 候选 Provider 的真实 model ID、图像、JSON、receipt、区域和保留能力。
- trusted Gold、病例级 split、failure bank 和 isolated Holdout 可用规模。
- 旧 XRay API 兼容期限及隔离表归档/只读/导入策略。
- AuditSink 是否满足幂等、授权检索、保留、导出和删除证明。

## 解决方式

- UNKNOWN 必须通过源代码、真实 schema、环境连接、不可变 Artifact 或用户/业务 owner 确认。
- 文档推断和历史 PASS 不能自动升级为当前事实。
