# 工程证据索引

> 英文术语、状态、缩写和数据库类型请参阅[英文术语中英对照](../术语中英对照.md)；代码标识符保持英文原样。

本目录保存运行、资格验证、发布判断、参考库核验和数据库快照。Artifact（证据产物）证明特定代码、环境和时间点发生过什么，不定义目标架构，也不能单独证明生产可用或医学准确率提升。

当前索引中最新可复核快照截止到 `2026-08-11T04:05:17Z`。该时间之后的工作树、配置、数据库、
Broker 或 Provider 状态不在现有证据覆盖范围内；“当前”只表示这个证据截止点，不表示实时探测。

## 当前冲突解释

| 容易混淆的证据 | 正确解释 |
|---|---|
| 稳定 `ai-provider-*.v1.json` 与 baseline 的 `provider_auth` 不同 | 运行时稳定合同当前直接阻断为 `qualification_artifact_signing_key_missing`；`provider_auth` 是 2026-08-11 历史真实尝试结果，两者都阻断但不可互换 |
| `ms_image_imaging_test` 有 10 张表 | 这是隔离的 `xray_accuracy_*` validation-only 快照，不是目标 `ms_image` 通用十表，不是 Alembic migration 或生产 schema |
| P1 Replay/MySQL 为 PASS-LOCAL | 只证明 Stub/Replay 和临时 metadata 语义；不证明 live RabbitMQ/Celery、真实图像 Provider（AI 服务提供方）、医学节点或准确率 |
| 根设计写 10+4 张目标表 | 状态是 `DESIGNED / NOT IMPLEMENTED`，不能由本目录快照推导成已部署 |

## 运行时读取的稳定契约

以下文件由 `app/core/config.py` 默认读取，不能随意移动或改名：

| Artifact（证据产物） | 用途 |
|---|---|
| [ai-provider-transport-qualification.v1.json](ai-provider-transport-qualification.v1.json) | Provider（AI 服务提供方） transport（AI 服务提供方传输层）资格状态 |
| [ai-provider-qualification.v1.json](ai-provider-qualification.v1.json) | Provider（AI 服务提供方）综合资格状态 |

修改 JSON 合同时必须提升版本并同步代码配置；不得把 Secret、完整 URL credential 或患者信息写入文件。

## 发布与资格判断

| Artifact（不可变产物） | 用途 |
|---|---|
| [release-readiness-summary.md](release-readiness-summary.md) | 当前发布结论摘要 |
| [qualification-matrix.md](qualification-matrix.md) | Provider（AI 服务提供方）、图像、Schema（结构合同）和运行资格矩阵 |
| [module-mapping-audit.md](module-mapping-audit.md) | 当前模块映射和缺口审计 |

## Phase 0（第 0 阶段）合同与边界

| Artifact（不可变产物） | 用途 |
|---|---|
| [p0-auth-tenant-contract.md](p0-auth-tenant-contract.md) | 鉴权、租户和控制面合同 |
| [p0-broker-adr.md](p0-broker-adr.md) | Broker（消息代理）与 Outbox（事务发件箱）决策 |
| [p0-dal-boundary.md](p0-dal-boundary.md) | `DalBase`（数据访问基类）和数据库访问边界 |
| [p0-process-boundary.md](p0-process-boundary.md) | API（应用程序接口）、Admin（管理端）、Worker（异步工作进程）进程边界 |
| [p0-reference-config.md](p0-reference-config.md) | 参考环境配置摘要 |
| [p0-unknowns.md](p0-unknowns.md) | 未确认事实清单 |
| [p0-g0-approval.md](p0-g0-approval.md) | G0 审批状态 |

## Phase 0（第 0 阶段）运行快照

| Artifact（不可变产物） | 用途 |
|---|---|
| [p0-git-snapshot.txt](p0-git-snapshot.txt) | 工作树和版本快照 |
| [p0-import-main.txt](p0-import-main.txt) | import-time 验证输出 |
| [p0-readiness.json](p0-readiness.json) | 本地依赖 readiness（就绪性） |
| [p0-runtime-manifest.json](p0-runtime-manifest.json) | 运行入口和环境清单 |
| [p0-db-rebuild-preflight.txt](p0-db-rebuild-preflight.txt) | 数据库重建前检查 |
| [p0-imaging-test-db-qualification.json](p0-imaging-test-db-qualification.json) | 初次影像测试库资格结果 |
| [p0-imaging-test-db-qualification-rerun.json](p0-imaging-test-db-qualification-rerun.json) | 修订后重复资格结果 |

## Phase 1（第 1 阶段）回放与资格

| Artifact（不可变产物） | 用途 |
|---|---|
| [p1-zero-model-chain-contract.md](p1-zero-model-chain-contract.md) | 零模型链路合同 |
| [p1-zero-model-replay.json](p1-zero-model-replay.json) | 零模型确定性回放结果 |
| [p1-prompt-ai-request-replay.json](p1-prompt-ai-request-replay.json) | Prompt（提示词）和 AI（人工智能）请求回放结果 |
| [p1-mysql-qualification.json](p1-mysql-qualification.json) | MySQL（关系型数据库）持久化资格结果 |

## 参考库与外部方案核验

| Artifact（不可变产物） | 用途 |
|---|---|
| [reference-db-readonly-check.json](reference-db-readonly-check.json) | 参考库首次只读检查 |
| [reference-db-readonly-live.json](reference-db-readonly-live.json) | 参考库只读连接结果 |
| [reference-db-schema-summary.md](reference-db-schema-summary.md) | 参考库表、字段和索引摘要 |
| [github-reference-verification.md](github-reference-verification.md) | 外部开源方案与许可证核验 |

## 基线与数据库快照

| Artifact（不可变产物） | 用途 |
|---|---|
| [xray-implementation-baseline-20260811T040517Z.txt](xray-implementation-baseline-20260811T040517Z.txt) | XRay（X 光） 实现基线快照 |
| [ms_image_imaging_test-20260811T040517Z.sql](ms_image_imaging_test-20260811T040517Z.sql) | 带 UTC 时间戳的测试库 SQL 快照 |
| `ms_image_imaging_test-before-schema-change.sql` | schema 变更前快照；受 `.gitignore` 管理 |
| `ms_image_imaging_test-schema-backup.sql` | schema 备份；受 `.gitignore` 管理 |

SQL dump 可能包含敏感结构或数据，只能保存在受控环境；提交前必须完成脱敏和泄漏检查。被 `.gitignore` 忽略的文件不会随代码提交，不能把本机存在误认为团队已获得。

## 证据使用规则

- 每个新 artifact 必须能追溯生成命令、代码版本、环境、时间和脱敏状态。
- Artifact 还必须声明覆盖范围、是否含脏工作树摘要以及它 supersede 的旧证据；绑定不全的现有文件只能作为时间点线索。
- `PASS-LOCAL` 只表示本地条件通过；没有真实 Broker、Provider 或部署环境证据时不能提升为生产通过。
- 失败、阻断、missing row 和 unknown 结果必须保留，不得只保存成功样本。
- 资格结果发生变化时生成新快照或更新稳定版本契约，同时修订发布摘要。
- 目标表、字段和模块边界仍以 [唯一权威设计](../ms-image-final-architecture-and-database-design.md) 为准。
