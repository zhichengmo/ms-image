# MS-Image 新会话提示词

> **当前有效恢复入口**：始终先按 `AGENT_HANDOFF.md`、`.agent-handoff/snapshot.md` 和用户本轮授权恢复。涉及 QJ 借鉴与模块收敛时，只使用本文“开启 QJ 借鉴与模块收敛调整会话”章节以及 `docs/refactor/08`、`15`、`16`、`17`。
>
> 下方“历史 P1/P2 提示”仅保留用于解释旧会话条件，**禁止**作为当前启动入口；其中的旧 SHA、已实现范围和兼容处理不得覆盖当前 worktree/handoff 事实。

## 开启新的重构会话（历史 P1/P2 提示，禁止作为当前启动入口）

```text
请开始重构 /Users/mozhicheng/workspace/code/cy-code/ms-image。

零、任务目标与执行方式

本会话不是继续讨论架构，也不是再生成一份设计文档，而是基于当前代码和已冻结文档直接开始目标实现。
当前已完成 P1 影像接入底座代码；不要重新生成或覆盖 P1。先恢复 handoff（代理交接）、确认当前授权和已提交源码，再决定是做经授权的 P1 真实演练还是进入 P2；不要停在“建议、计划或审计结论”，必须形成与当前任务一致的可验证增量。若源码与设计存在直接冲突，先给出 `file:line` 证据并修正对应权威合同；不要凭偏好
重新命名表、增加 Service、改变 Canonical XRay Chain 或另建平行运行时。

一、授权与禁止动作

1. 本次明确授权完全重构内部业务代码、目录、类和 Worker；旧 `xray_accuracy` 内部结构不是兼容目标。
2. 必要时可以提出新增、拆分或合并目标表，但必须先证明独立事实 owner、生命周期、查询、事务/恢复、
   权限或保留合同，并同步设计母文；不要按“10+4”数字机械建表。
3. 本次不授权：Alembic/数据迁移脚本、新建测试脚本、真实数据库写操作、生产双写、真实对象批量迁移、
   生产发布。上述动作必须单独获得授权；允许运行仓库已有的非破坏性检查和测试。
4. P1 不删除或改写旧 XRay API/表，不开启生产双写；旧入口保持原状，直到 P6 Compatibility Adapter
   （兼容适配器）和迁移方案获得明确授权。

二、启动恢复与脏工作树保护

先确认当前目录的 `AGENTS.md` 已加载，再按顺序亲自读取：
1. `AGENT_HANDOFF.md`
2. `.agent-handoff/snapshot.md`
3. `.agent-handoff/risks.md`
4. `.agent-handoff/backlog.md`
5. 变更长期架构时读取 `.agent-handoff/decisions.md`
6. `docs/refactor/README.md`
7. `docs/refactor/02-target-architecture.md`
8. `docs/refactor/03-database-and-storage-design.md`
9. `docs/refactor/05-development-guide.md`
10. `docs/refactor/06-refactor-migration-and-validation-plan.md`
11. `docs/refactor/08-new-session-handoff.md`
12. `docs/refactor/10-xray-detailed-flow.md`
13. `docs/refactor/12-canonical-xray-layer-responsibility-contract.md`
14. `docs/refactor/13-refactor-base-decision.md`
15. 设计 XRay 专项/Prompt/Targeted 时读取 `docs/refactor/14-xray-specialty-design.md`
16. `docs/ms-image-final-architecture-and-database-design.md` 中与 P0/P1、权限、OSS、
    Session/Study/Series/Image/Outbox 和核心不变量直接相关的章节
17. 即将修改的确切源码；修改前必须亲自完整读取。

恢复当前目标、状态、下一动作、活动文件、阻断和 UNKNOWN。开始编辑前固定运行并阅读：
`git status --short`、`git diff --name-status`、`git diff --stat`。所有已有修改和未跟踪文件默认属于用户；
若与本切片重叠，完整阅读并在现状上合并。禁止 reset、checkout、覆盖、批量删除或回退无关改动。

`9a45209a` 是重构开始时的初始提交；当前分支 `codex/ms-image-refactor` 已包含 P1 收口提交 `6dfd8d1`。不要 reset/clean 到初始提交，也不要重写已完成的 P1。保留公共可靠性语义，后续仅在当前授权下内部模块化替换未完成的 XRay 专项领域；不得另建第二套 API/Runner/Outbox/OSS Gateway/数据库事实源。

`.env` 当前已被 Git ignore（忽略）且不进入版本控制候选。仍然只能检查变量名、文件状态和是否命中 ignore，禁止输出任何值；提交前执行不打印值的 Secret 扫描，禁止直接 `git add -A`。不得自动 commit、stash、reset 或 clean；已有工作树文件不能因为“未提交”就被视为可删除。

三、权威边界：必须按问题分轴，不使用单一总排名

1. 项目规则与授权：当前用户授权 + 当前适用 `AGENTS.md`。
2. 当前实现事实：当前 worktree 的源码、配置、依赖和启动合同。
3. 当前外部事实：经授权读取并绑定环境/时间的真实 DB schema、OSS bytes/hash、Broker/Provider trace。
4. 目标设计：`docs/ms-image-final-architecture-and-database-design.md`。
5. 实施指导：`docs/refactor/*`，不得独立覆盖设计母文。
6. 医学准确率：冻结 Gold + 同病例 paired A/B + 确定性 scorer + isolated Holdout。
7. 历史解释：`docs/history` 和旧外部设计包，只解释由来，不作为当前建表合同。

旧真实 schema 只能证明现状，不能覆盖目标 schema；设计母文定义目标，但不能证明已经实现、迁移或提高
准确率。冲突先归类到对应权威轴，再记录现状与目标差距，并使用
`CONFIRMED / INFERRED / PROPOSED / UNKNOWN / N/A`。

四、Canonical XRay Chain（X 光权威主链）

两个 Profile 的执行边界已经由用户冻结，开发和文档不得自行改变：

1. `xray_primary_v1`：`StudyPreparation -> JointPrimaryReader -> DecisionFinalization -> Report`。
2. `xray_targeted_review_v1`：Primary 后进入确定性 FamilyRouting；`primary_final` 直接进入
   DecisionFinalization，`targeted_review` 最多调用一次 TargetedReview，成功并输出完整病例结果后进入
   DecisionFinalization。
3. FamilyRouting 仅属于 Targeted 实验 Profile，不调用模型、不读 Gold、不修改医学结论。
4. TargetedReview 一旦触发，技术失败必须 fail closed，不能静默回退 Primary。
5. Evaluation Plane 只产生候选证据；人工审批后，Control Plane 才能激活候选配置。

每个目标 Service/Stage 的接收、必填约束、成功输出、失败输出、下游消费者和数据落点，以
`docs/refactor/12-canonical-xray-layer-responsibility-contract.md` 第 20 章为实现合同。实现不能只对上函数名：
必须保证前一层交付对象与下一层接收对象一致，工程失败 TF、调用前覆盖终态 CF 和医学输出 OUT 不得互换。

五、当前执行范围

P1A/P1B/P1C 已完成代码并已提交：Session/Study/Series/Image 的 Model -> Schema -> DAL(DalBase) -> Service、API/依赖注入/路由、唯一 ObjectStorageGateway，以及 Image `validating`/Outbox/Relay/Worker/reconcile/revision。P1 的状态严格是 `CODE_IMPLEMENTED / NOT_MIGRATED / NOT_RUNTIME_VALIDATED`，不得重新生成 P1 或把它写成真实环境通过。

每个新会话先做有界恢复核对：Secret、数据库事务内外部 I/O、身份与资源授权、Broker、Trace/Audit、API/Admin/Worker 启动合同与 Artifact 新鲜度。随后只按用户当前授权执行下列之一：

1. 经单独授权后，设计/执行 P1 的迁移和真实 MySQL/OSS/RabbitMQ 演练；或
2. 开始 P2：复用 P1 的同一 Outbox/Relay，实现 Task + first Stage + Outbox 原子创建、lease/CAS 和 zero-model replay（零模型重放）。

P2 不得创建第二套中继、队列或事实源，也不接医学 Provider。P1 的 Image 校验 Outbox 属于影像生命周期，P2 只扩展同一可靠执行底座。

六、已实现 P1 必须持续满足的不变量

1. `Image uploading -> validating` 与 `Outbox(validate_image)` 在同一数据库事务；事务提交后 Relay 才发布。
2. OSS HEAD、服务端流式 hash/size/MIME/真实格式校验在数据库事务外，由 Worker 执行，不阻塞 API 长请求。
3. 只有服务端完整校验通过才能 ready；失败进入 quarantined。客户端声明 hash、signed URL、OSS ETag 或
   HEAD 结果均不能单独成为最终真相，bytes 和 signed URL 不落库。
4. 替换影像必须创建新 Image version；只有新版本 ready 且 Study revision CAS 成功后，旧版本才 superseded。
5. required Series/Image 集合不完整时 Study 不得 ready；Series count/manifest 从当前 revision 的 ready Image
   确定性重算，不能只做计数增减。
6. 同一个 idempotency key + 不同 payload 必须返回冲突；重复消息由 aggregate version、CAS 和 lease generation
   幂等处理。
7. DB 事务中不得调用 OSS/Broker/Provider；API/Service/Worker 不直接拼 SQLAlchemy，全部数据库访问经实体
   DAL 并复用 `apps.runtime.core.crud.DalBase`。
8. 每张目标表必须有服务端生成、非空、独立 `id VARCHAR(64)` 单列主键；不使用 Foreign Key、数据库 Enum、
   联合主键或 `tenant_id`。状态/类型使用 string/json/timestamp，并有中文候选注释。
9. 不新增 Repository、第二套 CRUDBase、DatabaseService、平行 service 包或第二套 OSS Gateway。
10. P1 代码必须明确区分目标新事实与旧兼容读取；旧 `xray_accuracy` Model/Service 不得成为新实体的基类或
    新写入 owner，LegacyCompat 不能创建新的医学事实。

七、身份与 OSS key 过渡

目标表不保存 `tenant_id` 不等于删除认证。当前可信 tenant claim 可以暂时作为旧 API 的兼容访问范围，
但不得写入目标表或由 request body/query 覆盖。目标资源 owner 使用已验证 subject/service identity、业务 scope
和资源归属校验；请求体不能指定或覆盖 owner 身份。

新 OSS key 使用领域 owner namespace + 全局 image_id + generation/version，不再由 tenant 派生。历史
tenant-derived key 通过现有 OSS 网关内的兼容适配器只读；不得盲目重写旧对象，也不得创建第二套网关。
移除旧 tenant dependency 前，必须先证明目标 owner 授权、旧 key 读取和越权拒绝合同闭环。

八、汇报、完成状态与关闭

修改前简短报告：确认的当前状态、P1 已实现边界、当前授权的切片、预计修改文件、验证方式；然后直接执行，
不要再次询问是否允许内部重构。

第一轮汇报必须明确写出：
- `HEAD=6dfd8d1`（除非新会话发现已推进），且 P1 已提交；
- 当前状态是 `P1_CODE_IMPLEMENTED / NOT_MIGRATED / NOT_RUNTIME_VALIDATED`，P2+ 尚未实现；
- 本轮正在执行 P1 真实验证准备或 P2 中哪一个受授权切片；
- 哪些现有安全/可靠性语义保留，哪些 `xray_accuracy` 专项代码准备替换；
- 验证只证明工程合同，不证明医学准确率。

由于本次未授权迁移、新测试脚本、真实数据库和真实对象演练，P1 即使代码完成，最高只能标记：
`CODE_IMPLEMENTED / NOT_MIGRATED / NOT_RUNTIME_VALIDATED`。不得把静态检查、mock/replay 或现有测试通过
写成 G4 OSS/revision 已通过，更不得宣称医学准确率提高。

结束前更新最小必要 handoff：snapshot、work-log、validation、backlog/risks，长期决策才写 decisions；明确
已实现、未迁移、未运行验证、阻断和 UNKNOWN。运行 handoff maintenance --compact-if-needed，并报告所有
已运行、失败和有意未运行的检查。
```

## 继续特定任务

```text
继续任务：<填写具体任务>。

把“继续”视为明确继续执行，不要空回复。
先读取 AGENT_HANDOFF.md、snapshot.md、risks.md 和 backlog.md，
说明上一步、下一动作和将修改的文件，再读取任务直接相关源码并执行。
不要依赖聊天记录代替仓库事实，不要撤销其他人的未提交改动。
```

## 会话关闭

```text
结束本轮前，请更新：
- .agent-handoff/snapshot.md：替换当前状态和下一动作；
- .agent-handoff/work-log.md：记录实际改动；
- .agent-handoff/validation.md：记录运行、失败和未运行验证；
- .agent-handoff/backlog.md / risks.md：更新待办、阻断和 UNKNOWN；
- .agent-handoff/decisions.md：只记录长期决策。

运行 agent-handoff maintenance --compact-if-needed，
然后说明已完成、已验证、未验证和剩余风险。
```

## 交接质量审查

```text
请审查并直接修复多文档 handoff（代理交接）：
AGENT_HANDOFF.md 只能是索引；snapshot 必须短且替换式更新；
下一动作必须可执行；决策必须有理由和证据；
验证必须区分 passed/failed/not run；
风险和 UNKNOWN 不能藏在工作日志；
禁止保存 Secret、长日志、聊天记录和不可验证猜测。
完成后运行维护检查。
```

## 开启 QJ 借鉴与模块收敛调整会话

```text
当前任务：仅在用户明确授权“执行 `docs/refactor/16-qj-reference-and-modular-convergence-plan.md` 的 QJ 收敛方案”时，对 MS-Image 做受控模块收敛调整。先确认用户本轮授权的 Phase；只有该明确授权下用户未指定切片时，才默认执行 16-Phase A（部署真相、Worker 角色、入口/Compose 边界），不跨 Phase。若用户只说“按文档开始/继续重构”，必须先以当前 snapshot 和 15 号文档的 Phase 2 下一动作判定任务。

工作区：`/Users/mozhicheng/workspace/code/cy-code/ms-image`。
参考仓库：`/Users/mozhicheng/workspace/code/cy-code/qj-open-plataform`，仅作为外部商业控制面、DatabaseRegistry、Compose 和 Kong 边界参考；不要合并仓库、数据库或业务主数据。

开始前严格执行：
1. 阅读 `AGENTS.md`、`AGENT_HANDOFF.md`、`.agent-handoff/snapshot.md`、`risks.md`、`backlog.md`。
2. 阅读 `docs/refactor/08-new-session-handoff.md`、`15-full-chain-gap-analysis-and-execution-plan.md`、`16-qj-reference-and-modular-convergence-plan.md`。
3. 若本轮涉及 AIConfig、AIRequest、Prompt、Schema、Provider-disabled、JointPrimaryReader 或 TargetedReview，必须先读 `docs/refactor/17-prompt-runtime-contract-and-minimal-provider-plan.md`；其调用数、Config Release、编译、泄漏和 provider-disabled 真 Bundle 合同不得因目录收敛而改变。
4. 实现公共/专项边界时再读 `14-xray-specialty-design.md`、`04-service-and-stage-design.md`、`05-development-guide.md`，并亲自完整阅读即将修改的源码。
4. 先运行 `git status --short`、`git diff --name-status`、`git diff --stat`，保护所有未提交改动；禁止 reset、clean、checkout、`git add -A` 或整文件覆盖。

固定架构合同：
- QJ 拥有 Kong、Project/API Key、Capability、限流、Usage/Wallet/Ledger、客户 SDK/Webhook；MS-Image 不复制这些事实。
- MS-Image 公共在线新主链唯一拥有 Session/Study/Series/Image、Task/Stage/Outbox、AI Config/Call、Report；Evaluation 保持独立数据库/队列/Worker。
- 新 XRay 能力只能经 Profile、Prompt、Schema 和 Stage handler 扩展；`xray_accuracy` 当前是 compatibility/legacy 域，消费者与迁移映射 UNKNOWN 前不扩展、不删除。
- 8 个在线业务 Service 保持为 Session/Study/Image/Task/ImagingExecution/AIConfig/AIRequest/Report；Stage handler 位于既有 `apps/runtime/service/` 内部，不新建平行 service 包。
- Stage 归属：StudyPreparation、DecisionFinalization 为 common；JointPrimaryReader、FamilyRouting、TargetedReview 为 XRay。
- 数据访问统一经 `DalBase` 实体 DAL；不新建 Repository/第二 CRUDBase/DatabaseService。
- API 不使用 `/{id}`；新表不使用 FK/Enum/联合主键/tenant_id；事务内禁止 OSS/Broker/Provider I/O。
- 不生成迁移/测试脚本、不连接真实 MySQL/OSS/RabbitMQ/Kong/Nacos/Provider，除非用户明确单独授权。

先在第一条回复中写明：当前 HEAD/dirty state、用户授权的 Phase、计划修改的文件、保留的不变量和验证方式；随后直接执行。结束前更新 handoff，并运行 maintenance。工程 fake/静态检查绝不能表述为真实运行、Provider 资格或医学准确率通过。
```
