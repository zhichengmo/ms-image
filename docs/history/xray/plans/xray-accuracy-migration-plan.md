# Provider（AI 服务提供方）/Key（密钥）/Connection（连接）/Pool（连接池）/Prompt（提示词）迁移实施计划

> 中文阅读说明：`migration plan` 是“迁移计划”，`Provider/Key/Connection/Pool/Prompt` 含义见术语表；其余英文术语请参阅[英文术语中英对照](../../../术语中英对照.md)。

> `ARCHIVED / 历史资料`：本文是旧迁移计划，不授权执行数据库、Secret 或生产配置变更。

状态：`ARCHIVED`（已归档）

当前依据：[MS-Image 最终架构、数据库与完整链路设计](../../../ms-image-final-architecture-and-database-design.md)

历史语境：以下目标、阶段和回滚步骤只用于解释旧迁移思路，不构成当前迁移、配置变更或生产操作指令。

## 目标

将参考项目的 AI 基础设施语义迁入 `ms-image`，不迁移明文 secret、医学数据或旧业务结论，不创建平行 Repository/Service。

## 阶段

1. 配置合同：为 Provider、Broker、Prompt、secret ref 定义脱敏 manifest；source/prefix 由适配器注入。
2. 公共 Provider 内核：抽取 Connection、Pool、retry、cooldown、receipt、qualification interface；保留 XRay 兼容调用。
3. Prompt Registry：公共版本选择/checksum/变量扫描；`prompts/xray_accuracy/` 仅保存 XRay assets。
4. 数据映射：先提交字段/索引/comment artifact，再由 DBA 授权 Alembic；本阶段不生成 migration。
5. Worker/Outbox：复用当前 `TransactionalOutboxRelay`，按 `modality_key` 生成拓扑；不迁移旧 task 名称或 Celery result backend。
6. Provider qualification：真实 endpoint、TLS、认证、model、schema、receipt、retry/429 逐项生成 artifact；失败保持 blocked。
7. G0：平台、安全、QA/SRE 审批后，才进入 Phase 1 零模型正式骨架。

## 回滚

公共配置/适配器变更可回滚到 XRay 显式 source/prefix；不回滚或覆盖用户既有修改；不删除真实数据；migration 需采用 expand/contract 并由 DBA 单独批准。
