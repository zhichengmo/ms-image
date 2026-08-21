# MS-Image 新会话交接：QJ 借鉴与模块收敛调整

状态：`CURRENT_NEXT_SESSION_HANDOFF / QJ_CONVERGENCE_PROPOSED / IMPLEMENTATION_PENDING_AUTHORIZATION`

更新日期：2026-08-20

用途：让新的 Codex/开发会话在不依赖历史聊天的情况下，正确恢复当前工程状态，并在获得用户实现授权后按 16 号文档执行模块收敛调整。

> 本文是新会话恢复和执行入口，不重复字段、Stage 或医学设计权威。
> 架构方案以 [16-QJ 借鉴与模块收敛调整方案](16-qj-reference-and-modular-convergence-plan.md) 为准；当前工程门禁以 [15-全链缺口与执行计划](15-full-chain-gap-analysis-and-execution-plan.md) 与 handoff 为准。

---

## 1. 新会话必须读取的顺序

1. 根目录 `AGENTS.md`：项目规则、授权边界和交接维护协议。
2. 根目录 `AGENT_HANDOFF.md`：交接入口。
3. `.agent-handoff/snapshot.md`、`risks.md`、`backlog.md`：当前状态、阻断和下一动作。
4. [重构文档包入口](README.md)：文档权威边界。
5. [QJ 借鉴与模块收敛调整方案](16-qj-reference-and-modular-convergence-plan.md)：本任务的目标、范围、Phase 和停止条件。
6. [全链缺口与分阶段执行计划](15-full-chain-gap-analysis-and-execution-plan.md)：当前 Phase 2 门禁、真实运行和医学发布边界。
7. [Prompt 运行合同与最小 Provider 链路调整方案](17-prompt-runtime-contract-and-minimal-provider-plan.md)：若本轮涉及 AIConfig、AIRequest、Prompt、Schema、Provider-disabled、JointPrimaryReader 或 TargetedReview，必须先读；其调用数、冻结版本、编译和泄漏合同优先约束该切片。
8. [XRay 完整核心架构与专项设计](14-xray-specialty-design.md)：公共/专项、医学 owner 和 Targeted 边界。
9. [Service 与 Stage 设计](04-service-and-stage-design.md)、[开发指南](05-development-guide.md)：8 个 Service、5 个 Stage、分层和代码规则。
10. 即将修改的确切源码；修改前必须完整阅读对应文件。
11. 仅在修改精确字段、状态、索引或迁移策略时，读取设计母文的受影响章节。

> `docs/refactor/README.md` 在本读取顺序中只充当导航。若其“当前一句话状态”与当前 worktree、`.agent-handoff/snapshot.md` 或 15 号文档冲突，必须以后者为准，不得据此重建已有 Task/Stage/Report/Evaluation 代码。

如需理解旧链原因，可读取 `docs/history/README.md`；历史资料不能作为新建表、迁移或新执行链依据。

---

## 2. 当前恢复摘要

### 2.1 Git 与工作树

- 工作区：`/Users/mozhicheng/workspace/code/cy-code/ms-image`。
- 当前分支：以实时 `git branch --show-current` 为准；本次 Runtime Foundation 分支为 `codex/monorepo-runtime-foundation`。
- 16 号 QJ 收敛静态审计基线：`2fa2a8b5cd01777204e4952641b97174d9dc5879`（仅用于解释该文档的审计范围，不是当前 worktree HEAD）。
- 开始实施前必须执行 `git rev-parse HEAD`，并以当前 worktree 与 `.agent-handoff/snapshot.md` 的 HEAD 为实现事实；截至 2026-08-20 的已知 HEAD 是 `9fdd1c64655bbf27af7c0359d58f39df3c467775`，其冻结了 17 号 Prompt 运行合同。
- 当前工作树可能已有用户未提交的文档/handoff 与 `apps/runtime/models/evaluation.py` 格式改动；禁止 `reset`、`clean`、`checkout`、`git add -A` 或整文件覆盖。
- 本次新建/更新的文档可能同样未提交；开始前必须重新运行 `git status --short`、`git diff --name-status`、`git diff --stat`。

### 2.2 当前工程状态

当前已确认：

```text
ONLINE_CODE_IMPLEMENTED
TASK_STAGE_EXECUTION_IMPLEMENTED
PROVIDER_DISABLED_MEDICAL_CHAIN_IMPLEMENTED
PROVIDER_DISABLED_FULL_CHAIN_PASSED
REPORT_CHAIN_IMPLEMENTED
EVALUATION_CODE_IMPLEMENTED
EVALUATION_DB_ISOLATION_IMPLEMENTED
EVALUATION_EXPORTER_IMPLEMENTED
EVALUATION_RELAY_IMPLEMENTED
EVALUATION_WORKER_IMPLEMENTED
EVALUATION_READINESS_IMPLEMENTED
OPERATIONAL_STATUS_IMPLEMENTED
EVALUATION_SCOPE_SEPARATION_IMPLEMENTED
FAKE_SCORER_IMPLEMENTED
PAIRED_AB_SUMMARY_IMPLEMENTED
```

上述仅是摘要；完整状态以 `.agent-handoff/snapshot.md` 为准。新会话不得因摘要遗漏而重建已有 scorer、paired A/B、Task、Stage、Report 或 Evaluation 链。

当前仍然必须保持：

```text
NOT_MIGRATED
NOT_RUNTIME_VALIDATED
PROVIDER_NOT_QUALIFIED
AI_TEST_NOT_STARTED
MEDICAL_ACCURACY_UNKNOWN
MEDICAL_RELEASE_NO_GO
```

`PROVIDER_DISABLED_FULL_CHAIN_PASSED` 只证明 inline fake 工程组合链；不能表述为真实 MySQL/OSS/RabbitMQ/Provider、生产可用或医学准确率通过。

### 2.3 已批准的目标边界

```text
QJ Open Platform
= 外部商业控制面：Kong、Project/API Key、Capability、限流、Usage/Wallet/Ledger、SDK/Webhook

MS-Image
= 独立影像领域内核：Image/OSS、Study revision、Task/Stage/Outbox、AI Call、Report、Evaluation
```

目标公共在线新主链：

```text
Session / Study / Series / Image
Task / StageCheckpoint / Outbox
AIConfigRecord / AICall / Report
```

目标在线业务 Service 固定为：

```text
SessionService / StudyService / ImageService / TaskService
ImagingExecutionService / AIConfigService / AIRequestService / ReportService
```

XRay 新能力只能通过 Profile、Prompt、Schema、Stage handler 和 Stage output 扩展；不得继续新增 `xray_accuracy` 的 Task/Stage/Outbox/Call/Report 事实。

---

## 3. 新会话的第一轮判定

新会话首先判断用户当前授权属于哪一类：

| 用户授权 | 新会话最早动作 |
|---|---|
| 只评审/解释架构 | 只读 16 号文档和相关源码，不改代码 |
| 明确授权“执行 16 号 QJ 收敛方案”但未指定切片 | 从 16 号文档 **Phase A** 开始：部署拓扑、Worker 角色、legacy consumer 清单和入口边界；不迁移、不删旧链 |
| 仅说“按文档开始/继续重构” | 先以当前 snapshot 和 15 号文档的 Phase 2 下一动作判定任务；不得擅自切换到 16-Phase A |
| 明确调整 Stage 收敛 | 执行 16 号文档 **Phase B**；还必须先阅读 17 号 Prompt 合同，以及 `pipeline.py`、`imaging_execution_service.py`、现有 Service/Worker 和相关 Schema |
| 明确调整上传/对象生命周期 | 执行 **Phase C**；先完整阅读 `images.py`、`image_service.py`、ImageDal、ObjectStorageGateway 和 imaging worker |
| 明确调整 DB/入口/Compose | 执行 **Phase D**；先完整阅读 `async_db.py`、`main.py`、`run_servers.py`、Compose、readiness、worker entrypoints |
| 明确接 QJ | 先完成 **Phase E 接口评审**，冻结 identity、idempotency、object owner、状态同步和计费终态；不得先写透明 proxy 或新表 |
| 明确要求迁移、真实运行、Provider 或医学发布 | 先要求并记录专门授权；遵守 15 号文档的门禁 |

不要一次跨越多个 Phase。每个 Phase 必须先完成可复核的代码、部署合同和验证，再进入下一步。

---

## 4. 严格禁止事项

- 不新建 Repository、第二套 CRUDBase、DatabaseService、平行 service 包、第二套 OSS Gateway、第三套 Outbox 或 Task Runner。
- 不在 API、Service、Worker 直接拼 SQLAlchemy 查询；数据库访问仍经实体 `XxxDal(DalBase)`。
- 不使用 `/{id}`；资源 ID 只放 query 或 request body。
- 新 Model 不使用 Foreign Key、数据库 Enum、联合主键或 `tenant_id`。
- 不在数据库事务内调用 OSS、Broker 或 Provider。
- 不把 QJ Project/API Key/Wallet/Ledger/客户 Webhook 复制到 MS-Image。
- 不把 QJ 的动态 HTTP Provider proxy 当作 MS-Image 的 Task/Stage 替代物。
- 不扩展或删除 `xray_accuracy` 表/API/Worker，直到外部消费者、迁移映射和审计期限有证据。
- 不让 XRay Stage 直接拥有第二套 Task/Stage/Outbox/Report 状态机。
- 不生成迁移脚本、测试脚本，不连接真实基础设施，除非用户单独授权。
- 不把工程 fake、静态检查、测试通过写成 Provider 资格、医学准确率或生产发布通过。

---

## 5. 最小实施顺序

### Phase A：部署真相与边界冻结

目标：让源码、Compose、Worker、queue topology、readiness 和 handoff 表述一致。

优先核查：

```text
apps/runtime/main.py
apps/runtime/run_servers.py
docker-compose.yml
apps/runtime/workers/imaging_worker/
apps/runtime/workers/evaluation_worker/
apps/runtime/core/messaging/config.py
apps/runtime/core/readiness.py
```

输出：明确 Runtime user/admin、imaging/evaluation worker/relay 的职责；不得恢复或复制已删除的 legacy XRay worker。

### Phase B：公共 Execution 与 XRay Stage 收敛

目标：`ImagingExecutionService` 是唯一状态机 owner；XRay 只实现专项 handler。

前置条件：涉及 AIConfig、AIRequest、Prompt、Schema、JointPrimaryReader 或 TargetedReview 时，必须先满足 17 号文档的调用数、Config Release、Prompt Compiler、泄漏检查和 provider-disabled 真 Bundle 合同；目录收敛不得改变这些冻结约束。

```text
common stages:
- StudyPreparation
- DecisionFinalization

XRay stages:
- JointPrimaryReader
- FamilyRouting
- TargetedReview
```

Stage 只返回 `StageResult`/DTO；Execution 才写 Stage/Task/Outbox/Report。

### Phase C：Image API 编排下沉

目标：`images.py` 不直接管理多段事务或 OSS 生命周期；唯一对外业务入口保持 `ImageService`。

### Phase D：Registry 与独立入口

目标：借鉴 QJ 的 DatabaseRegistry 和 Compose 薄编排，但保留 `online != evaluation` 的失败关闭；不使用启动 `create_all()`。

### Phase E：QJ Adapter

目标：QJ 只处理商业事实；MS-Image 只处理影像事实。先冻结内部 identity、Task 映射、Object owner、状态同步和计费终态，再写接口。

---

## 6. 新会话结束前

- 更新 `.agent-handoff/snapshot.md`：当前 Phase、修改文件、下一动作、阻断。
- 更新 `.agent-handoff/work-log.md`、`validation.md`、`backlog.md`、`risks.md`；长期决策才更新 `decisions.md`。
- 运行：

```bash
python /Users/mozhicheng/.codex/skills/agent-handoff/scripts/maintain_handoff.py \
  --repo /Users/mozhicheng/workspace/code/cy-code/ms-image \
  --compact-if-needed
```

- 诚实区分：代码实现、fake/静态验证、真实运行资格、Provider 资格和医学证据。

---

## 7. 可直接复制给新会话的启动提示

只需要评审 QJ 借鉴是否适用、尚未授权任何代码调整时，使用 [18-QJ 架构借鉴决策门提示](18-qj-reference-decision-gate-session-prompt.md)。

只有用户明确授权执行 16 号方案的具体最小切片时，才使用根目录 `AGENT_SESSION_PROMPTS.md` 中的 **“开启 QJ 借鉴与模块收敛调整会话”** 提示词。两种入口都不得使用历史 P1/P2 提示替代当前 worktree/handoff 事实。
