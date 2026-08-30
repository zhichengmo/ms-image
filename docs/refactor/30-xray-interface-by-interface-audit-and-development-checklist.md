# MS-Image 全接口逐项审计与补齐开发清单

状态：`CURRENT_INTERFACE_AUDIT / DEVELOPMENT_CHECKLIST`

审计日期：2026-08-27

最近全链路复核：2026-08-28

适用范围：当前工作树中的 Runtime、Runtime Admin、AI Control、Evaluation Control 四个 ASGI 应用，以及支撑这些接口的 Service、DalBase、ORM、真实 MySQL 表和 Alembic 边界。

本文目的不是再设计一套“大而全”的 XRay API，而是回答三个具体问题：

1. 当前每一个真实接口是否存在、是否能调用、逻辑是否成立；
2. 哪些现有接口必须修，哪些缺失接口必须补；
3. 后续按什么顺序一个接口一个接口开发和验收。

本文只记录审计和开发要求，不代表已授权修改业务代码、数据库、迁移或测试脚本。实际开发仍按用户逐项授权执行。

---

## 1. 最终结论

### 1.1 不能继续整体照搬 27 号文档

27 号文档提出的 projection（投照位）、clinical context（临床上下文）、Task 列表、Report 视图等方向有价值，但不能按文档中的接口数量直接开工。当前源码已经有一条真实跑通过的底层主链，问题集中在接口合同、状态耦合、数据血缘、数据库部署和产品读取能力，不需要重写整个链路。

本轮动态枚举得到：

| 应用 | 业务 API | 根路由 | 总 method/path | 结论 |
|---|---:|---:|---:|---|
| Runtime | 27 | 1 | 28 | 主链接口齐全；Task detail 轮询字段已补，Session/Study 生命周期、逐图元数据和列表能力仍有缺口 |
| Runtime Admin | 6 | 1 | 7 | 运营读取主体成立；Report publish/void 代码存在但当前不可用 |
| AI Control | 29 | 1 | 30 | 主体最完整；Prompt import 事务边界和 Connection “validate”语义需修正/澄清 |
| Evaluation Control | 9 | 1 | 10 | 路由代码存在，但独立 Evaluation DB 和迁移缺失导致整组接口当前运行不可用 |
| 合计 | 71 | 4 | 75 | 各应用内无重复 method/path；71 个业务 API 均声明了 response model |

这里将四个 ASGI 应用各自的 `GET /` 根路由统一计入总数。旧版把 Runtime 的 27 个业务 API 当成含根路由数量，导致合计少算 1 条；2026-08-28 已修正统计口径。

### 1.2 当前最重要的缺陷

| 优先级 | 缺陷 | 影响 |
|---|---|---|
| P0 | Report 没有 `state_version`，Service/DAL 却按该字段 CAS | Admin publish/void 实际不可调用；Report supersede 分支也会失败 |
| P0 | Evaluation 独立库 `ms_image_eval` 不存在，迁移仍只连主库 | Evaluation 9 个业务接口整体 `CODE_PRESENT / RUNTIME_UNAVAILABLE` |
| P0 | Alembic 两个 revision 不能从空库重建当前 20 张业务表 | 任何新字段迁移都建立在不可重建基线上，发布与回滚不可证明 |
| P1 | Image 写入口没有 projection，replace 也没有继承/重声明语义 | `Image.projection` 10/10 为空，manifest、Snapshot、Prompt 全链断开 |
| P1 | `POST /tasks` 没有 clinical context；逐图 Image facts 也未进入 Snapshot | 模型看不到调用方临床事实和逐图投照位，不能形成可信多视图输入证据 |
| P1（已完成，2026-08-28） | Session complete/cancel 原先不检查或联动 Task | 已采用完整诊断会话语义：complete 增加非终态 Task 门禁，cancel 原子写 Task 取消请求，并让 Task create 与 Session 终态推进共用 Session 行锁 |
| P1 | Runtime readiness 强依赖 Evaluation DB/Worker | 独立评测平面故障会让在线 Runtime readiness 返回 503 |
| P1 | AI Connection `validate` 只做结构和 hash 校验 | `validated` 不等于 Provider 可连接、凭据可用或模型能力已资格化 |
| P2 | Session/Study/Task 缺分页发现接口；Image page 已补 | 调用方重启后仍缺 Task 恢复入口；Session/Study page 是否需要取决于真实消费者 |
| P2 | Report raw content 还没有稳定展示 Schema | 现在实现 `/reports/view` 会把自由结构 `findings` 固化成不可靠 UI 合同 |

### 1.3 当前正确且应保留的基础

- 业务接口主体遵循 `API -> Service -> XxxDal(DalBase) -> Model/DB`。
- Session、Study、Image、Task 的资源归属校验来自 JWT subject，不信任 body 中的 requester ID。
- Image 上传已把数据库短事务和 OSS 网络 I/O 拆开；multipart 初始化失败有 abort 补偿。
- Image complete、Task create/cancel、AI Control 写接口普遍有幂等或 CAS 保护。
- Task/Stage/Outbox/Worker 的重复投递与 cancel-before-provider 已有真实运行证据。
- Session complete/cancel 已与 Task 生命周期联动：Session completed 不再容纳非终态 Task；Session cancelled 表示取消请求已原子接受，后续仍由 Worker 在安全边界收敛 Task。
- AI Control 的 Prompt、Connection、ModelPool、Config 生命周期、Audit replay 和 paired active expectation 主体合理。
- 当前物理表无 foreign key、无 DB Enum，20 张业务表都有独立 `id` 单列主键，符合项目约束。

### 1.4 全链路接口闭环总判定

“全链路跑通”必须拆成四个不同验收层级。否则很容易把本地成功产出一次 Report，误报成上游可恢复、生产可运维或医学已资格化。

| 层级 | 当前判定 | 接口结论 | 仍需完成 |
|---|---|---|---|
| L0 单病例 Primary happy-path | `LOCAL_E2E_PASSED` | Session、Study、Series、Image 上传/完成、Study finalize、Task 创建/查询、Report 查询接口已足以执行一条病例；`POST /series`、`GET /tasks?id=`、`GET /images/page` 已完成本轮修复/补齐 | 不需要为了“再跑一次”新增接口；仍要保留真实 Provider、worker、relay 和数据库运行证据 |
| L1 上游稳定集成与断点恢复 | `MINIMUM_CLOSED` | `GET /images/page`、`GET /tasks/page`、`GET /reports/current?task_id=` 与 Session/Task 生命周期联动均已完成，已形成保存 ID 前提下的最小恢复闭环 | 按真实消费者决定是否补 Session/Study page；仍需在发布环境补并发资格化和等量数据查询计划证据 |
| L2 生产运行与运维资格化 | `NO-GO` | Runtime/Admin 已有 health/readiness/operations 路由，但 readiness 错误耦合 Evaluation；AI Control 无独立 health/readiness | 修 Runtime/Admin readiness 平面隔离；新增 AI Control health/readiness；关闭自动 reconcile、unknown 有界终止、JWT 与 Artifact signing 等非 HTTP 阻断 |
| L3 Evaluation 与医学发布资格化 | `NO-GO` | Evaluation Job/Run/Artifact 路由代码存在，但独立 DB/迁移缺失导致整组不可运行；Fake scorer 不能代表医学准确率 | 先修独立 Evaluation DB 与 Alembic，再新增 Evaluation health/readiness、jobs page，重构 Run owner/幂等与列表分页，最后完成可信 Gold/Scorer/分母/M1 |

#### 1.4.1 近期真正需要新增的接口

| 优先级 | 接口 | 是否阻塞 L0 | 作用 |
|---:|---|---:|---|
| P1（已完成，2026-08-28） | `GET /api/v1/tasks/page` | 否 | 上游按 Session/Study 恢复 Task、继续轮询并发现 `current_report_id` |
| P1（已完成，2026-08-28） | `GET /api/v1/reports/current?task_id=` | 否 | 只读取当前可交付 Report，避免上游自行解释 history 与 void/supersede |
| P1 | AI Control `GET /api/v1/health` | 否 | 独立进程存活探针 |
| P1 | AI Control `GET /api/v1/readiness` | 否 | 验证在线 Config/数据库/Nacos 等控制面依赖是否就绪 |
| P0-EVAL | Evaluation Control `GET /api/v1/health` | 否 | 独立评测进程存活探针 |
| P0-EVAL | Evaluation Control `GET /api/v1/readiness` | 否 | 明确暴露 Evaluation DB/worker 不可用，并作为修复后的部署 Gate |
| P1-EVAL | `GET /api/v1/evaluation/jobs/page` | 否 | Evaluation 修复后的 Job 发现与恢复入口 |

`GET /sessions/page`、`GET /studies/page` 只在上游确实不能稳定保存资源 ID 或产品页面需要跨病例发现时补；它们不阻塞当前单病例主链。`GET /reports/view?task_id=` 等待稳定医学展示 Schema，不应现在固化自由结构内容。

#### 1.4.2 已有接口必须修正，不应重复新增

| 现有接口/接口组 | 当前问题 | 正确动作 |
|---|---|---|
| Image prepare/replace 四个写入口 | 不写 projection，replace 无继承/更正规则 | 扩展现有 request contract，并贯通 Image -> manifest -> Snapshot -> Prompt，不新增 projection 旁路接口 |
| `POST /tasks` | 缺 clinical context，逐图 Image facts 未冻结进 Snapshot | 扩展现有 Task create contract，不新增 `/sessions/context` |
| `POST /sessions/complete`、`POST /sessions/cancel` | 不检查/联动非终态 Task | 修 Service 状态编排，不新增另一套 Session 终止接口 |
| Runtime/Admin readiness | 被 Evaluation DB/worker 拖成 503 | 按 online/evaluation 平面拆分 readiness 判定，不新增重复全局 readiness |
| Admin Report publish/void | Report 缺 `state_version`；publish 与“final 直接可交付”决定冲突 | publish 停用/废弃；void 先明确 reason/actor/audit 与 current delivery 语义，再决定是否迁移修复 |
| AI Connection validate | 只做静态结构/hash 校验 | 明确命名与响应语义为静态校验；真实 Provider qualification 后置，不把 validated 当 available |
| Prompt import | 数据库请求生命周期内等待 Nacos 网络 | 拆 DB 预检、Nacos I/O、DB 短事务，不新增 import v2 旁路 |
| Evaluation Job/Run/Artifact | 独立库不存在、迁移边界错误、Run owner/幂等冲突、列表无分页 | 先修数据库与执行合同，再逐项开放现有接口；不是继续堆新 Evaluation API |

#### 1.4.3 不是接口缺失，但会阻断完整全链路的事项

- 自动 reconcile 必须由唯一 scheduler owner 周期触发，不新增 HTTP reconcile 接口；
- unsupported/unknown Attempt 需要持久化、有界、可恢复的终止合同；
- Runtime/Admin JWT 与 Artifact signing 的密钥生命周期和部署 Gate 尚未资格化；
- Alembic baseline 不能从空库重建当前在线与 Evaluation 表，任何新迁移前必须先修；
- projection、clinical context、Prompt/Provider receipt 属于数据合同和证据链，不是“有路由就算完成”；
- 医学准确性必须由可信 Gold、Scorer、分母、Failure Bank 与 M1 证明，单次 E2E Report 不能替代。

因此，截至 2026-08-28，**四应用的接口盘点已经完成，但接口开发与完整全链路资格化没有完成**。后续逐接口开发应以本节分层为总入口，再进入各接口审计章节执行。

---

## 2. 审计口径与状态标记

### 2.1 四个应用的真实外部前缀

四组接口不是同一个 FastAPI 应用。下文表格优先写应用内相对路径，外部访问时需加对应 root path：

| 应用 | root path | API prefix | 外部示例 |
|---|---|---|---|
| Runtime | `/ms-image` | `/api/v1` | `/ms-image/api/v1/tasks?id=...` |
| Runtime Admin | `/ms-image/admin` | `/api/v1` | `/ms-image/admin/api/v1/reports/void` |
| AI Control | `/ms-image/ai-control` | `/api/v1` | `/ms-image/ai-control/api/v1/ai-configs/active` |
| Evaluation Control | `/ms-image/evaluation-control` | `/api/v1` | `/ms-image/evaluation-control/api/v1/evaluation/jobs` |

因此，27 号文档中把 Admin publish 写成 Runtime 下的 `/api/v1/admin/reports/publish` 不符合真实装配。

### 2.2 状态标记

| 标记 | 含义 |
|---|---|
| `KEEP` | 接口和主体逻辑正确，当前保留 |
| `FIX` | 路由存在，但请求、响应、状态、事务或数据合同需要修正 |
| `BLOCKED` | 代码存在，但运行环境或数据库合同使其当前不可用 |
| `ADD` | 当前确实缺失，已有明确调用方或恢复用途，应新增 |
| `DEFER` | 有产品价值，但不应阻塞当前输入证据链或运行资格化 |
| `REMOVE/DEPRECATE` | 当前语义无消费者或与已确认产品决定冲突，应停用而非继续扩建 |

### 2.3 通用验收标准

每个业务接口开发时至少检查：

1. 请求 schema `extra="forbid"`，字符串归一化，JSON 有版本和尺寸上限；
2. 资源 ID 只放 query 或 request body，不新增 `/{id}`；
3. 鉴权 subject 与资源 owner 在 Service 层核对；
4. 写操作明确幂等键、CAS expectation、终态重放和冲突语义；
5. API 只调 Service，Service 只经实体 DalBase 访问数据库；
6. 网络 I/O 不跨越长数据库事务；
7. 响应不泄露 Secret、签名 URL、内部原始 Provider 正文；
8. 状态候选值与 ORM comment、Schema、Service、Worker、Evaluation 一致；
9. 真实物理表、索引和迁移能支撑接口；
10. 验收既包含正常调用，也包含重复调用、旧版本 CAS、资源越权和依赖失败。

---

## 3. Runtime 公共与健康接口

### 3.1 逐接口结论

| 接口 | 鉴权 | 当前逻辑 | 状态 | 处理要求 |
|---|---|---|---|---|
| `GET /` | 无 | 返回服务消息和 `/docs` | `FIX-P2` | 生产环境若关闭 docs，响应不要继续宣称 `/docs` 可用；Runtime/AI/Evaluation 的 OpenAPI 也应按生产策略关闭或保护 |
| `GET /api/v1/health` | 无 | 只证明进程可响应 | `KEEP` | 作为 liveness 保持无依赖；时间建议统一 UTC ISO-8601 |
| `GET /api/v1/version` | 无 | 返回硬编码 `1.0.0`，并把请求时刻写成 `build_time` | `FIX-P2` | 版本和 build time 应来自构建元数据；没有真实 build time 时删除该字段，不能用当前时间冒充 |
| `GET /api/v1/readiness` | 无 | 检查主库、Evaluation 库、Redis、两组 Worker/Broker | `FIX-P1` | Runtime 在线 readiness 不应被独立 Evaluation 平面拖死；按应用拆分 readiness，保留聚合运营视图 |

### 3.2 readiness 的具体问题

`build_readiness()` 当前把 `ready` 定义为：

```text
online database + redis + imaging worker
AND
evaluation database + evaluation worker
```

这会产生两个问题：

- Evaluation 数据库不存在时，在线 Runtime 即使能接收上传和 Task，也固定返回 503；
- `BROKER_ENABLED=false` 时虽然返回 `service_mode=api_only`，但两个 worker ready 都被置为 false，整体 readiness 仍固定 false。

建议拆为三个投影，不新增表：

- Runtime `/readiness`：主库、Redis、OSS 基本能力、imaging broker/worker；
- Evaluation `/readiness`：Evaluation DB、Evaluation broker/worker、Artifact store；
- Admin `/operations/status`：聚合两个平面的状态和告警，但某一平面失败时仍返回结构化 degraded 数据，而不是整个接口 503。

---

## 4. Session 接口逐项审计

### 4.1 `POST /api/v1/sessions`

状态：`FIX-P1`

当前正确逻辑：

- 要求 `imaging:run`；
- `requester_id` 来自 JWT subject；
- 同 `request_id` 或同 `source_system + source_session_id` 重放会核对不可变字段；
- 不同请求占用同一幂等键返回 409。

已确认问题：

- `source_system` 由请求方自由填写，却参与全局唯一约束；调用方可以冒用其他来源名占位；
- `request_id` 也是全局唯一，而不是 `requester_id + request_id`，两个调用方使用相同普通 request ID 会互相冲突；
- `technical` 层面没有明确 source system 与 JWT client/issuer 的绑定规则。

推荐修法：

- 优先从可信 client claim 或服务端配置映射 `source_system`；若仍允许 body 传入，必须校验它属于当前 client 的 allowlist；
- 明确 request ID 是全局 UUID 还是 caller scoped。若改为 caller scoped，需要模型唯一约束调整和迁移授权；
- 不增加 tenant 字段。

### 4.2 `GET /api/v1/sessions?id=`

状态：`KEEP`

- ownership 校验正确；非 owner 对外返回资源不存在；
- Response 包含状态版本和生命周期时间；
- `SessionQuery` schema 目前未被 endpoint 使用，属于查询合同双源，后续可统一，但不是行为阻断。

### 4.3 `POST /api/v1/sessions/complete`

状态：`FIXED-P1（2026-08-28）`

已确定 Session 采用“完整诊断会话”语义，并完成以下修复：

- complete 先以 `SELECT ... FOR UPDATE` 锁定 Session，要求当前为 processing 且 `state_version` 匹配；
- 保留至少一个 Study、Study/Image 不得仍 ingesting、validating、uploading 的原门禁；
- 通过 `Task -> Study -> session_id` 查询拒绝任意非终态 Task；终态集合固定为 `completed/failed/cancelled/dead_letter`，其他状态均 fail-closed；
- `cancel_requested_at` 已写入但仍为 queued/running/retry_wait 的 Task 仍是非终态，不能完成 Session；
- completed 幂等重放也重新扫描非终态 Task，避免历史脏数据被静默接受；
- `POST /tasks` 创建新 Task 时使用同一 Session 行锁，只有 open/processing Session 可接受新 Task，堵住“complete 检查后又插入 Task”的竞态。

保留问题：包含 invalid Study 的 Session 仍可在其他条件满足时完成，接口尚未提供按 Study 聚合的诊断失败摘要；这不再导致 Task 生命周期穿透，但产品语义仍需单独决定。

### 4.4 `POST /api/v1/sessions/close`

状态：`KEEP`，依赖 4.3 修正后的 complete 语义。

- 只允许 completed -> closed；
- CAS 和终态重放合理；
- 本接口不需要直接查询 Task，前置责任由 complete 承担。

### 4.5 `POST /api/v1/sessions/cancel`

状态：`FIXED-P1（2026-08-28）`

当前合同：

- cancel 先锁定 Session，并在同一个主库事务中按稳定 Task ID 顺序锁定 Session 下全部非终态 Task；
- 对尚未收到取消请求的 Task 写入 `cancel_requested_by_id/cancel_reason/cancel_requested_at`，再 CAS 推进 Session 为 cancelled；任一 Task CAS、owner 或 Session CAS 冲突都会使整个请求事务回滚；
- 已终态 Task 保持 completed/failed/cancelled/dead_letter 原状，不补写取消事实；已有 Task 取消请求采用 first-request-wins，不覆盖首次原因和时间；
- 同 reason 的 cancelled 重放会再次扫描非终态 Task，可修复历史上 Session 已 cancelled、Task 尚未收到取消请求的存量不一致；
- `POST /tasks` 创建新 Task 与 cancel 共用 Session 行锁；取消先成功时新 Task 被拒绝，新 Task 先成功时 cancel 会在同事务中为它写取消请求；
- 保留原有 uploading/validating Image 门禁，没有扩张为 Image 取消工作流。

`Session.status=cancelled` 的精确定义是“Session 取消请求已原子接受”，不表示响应返回时所有 Task 已经变为 cancelled。运行中 Task 不被强制改状态，仍由现有 Worker 在 claim、stage 边界和结果 finalization 前检查取消请求并安全收敛；迟到结果不能重新生成 Report。首版没有新增 `cancelling`、`pending_task_count`、表字段或迁移。

### 4.6 缺失：`GET /api/v1/sessions/page`

状态：`ADD-P2`

用途：调用方重启、页面刷新、按 subject/status 查找历史会话。

建议查询：`subject_id?`、`status?`、`created_from?`、`created_to?`、`page`、`page_size<=100`。Service 必须固定 `requester_id=JWT subject`，不能让调用方查询其他 owner。

数据库已有 `(subject_id, created_at)` 和 `(status, created_at)` 索引；若同时强制 requester 过滤，需在真实查询计划后决定是否补 `(requester_id, created_at)`，本轮不直接生成迁移。

---

## 5. Study / Series 接口逐项审计

### 5.1 `POST /api/v1/studies`

状态：`FIX-P1`

正确逻辑：校验 Session owner 和状态；来源 Study 幂等；创建 Study 后把 open Session CAS 推进到 processing。

问题：

- `identity_status=confirmed` 可由请求直接声明，没有绑定可信认证主体；
- `completeness_attested_by` 也由请求自由填写，可伪造其他操作者；
- `technical_metadata` 是无结构、无尺寸上限 JSON。

建议：

- `identity_status` 首版仅允许可信 system client 设置 confirmed；普通 caller 只能提交 unknown；
- `completeness_attested_by` 由服务端写 JWT subject 或可信上游主体，不直接采用 body 字符串；
- technical metadata 使用版本化 schema 和序列化尺寸上限。

### 5.2 `GET /api/v1/studies?id=`

状态：`KEEP`

- owner 校验正确；
- 返回 Study + 有序 Series，足以替代单独的 Series detail；
- 当前不返回 Image。不要把无限 Image 数组直接塞进 StudyDetail，应新增分页 Image 查询。

### 5.3 `POST /api/v1/studies/finalize`

状态：`KEEP-WITH-PRECONDITION`

正确逻辑包括：

- CAS 检查 `expected_state_version + current_revision_id`；
- identity 必须 confirmed；
- 至少一个 Series，所有 Series ready；
- Image 数量、Series 数量、manifest、completeness 全部一致；
- 已 ready 的同一版本重放可返回原结果。

剩余前置风险是 `POST /studies` 对 confirmed 的信任；`POST /series` 的 revision 缺陷已在本轮修复，不需要重写 finalize。

### 5.4 `POST /api/v1/series`

状态：`FIXED（2026-08-27）`

修复前这是当前 Runtime 最危险的已有接口之一。

修复前只拒绝 `study.status == invalid`，因此 ready Study 仍可新增 Series。创建 Series 后没有调用 Study revision recompute，也没有把 Study 从 ready 退回 validating。

随后 `POST /tasks` 会：

1. 校验 Study 仍是 ready，且使用旧 `resolved_manifest_sha256`；
2. 查询当前全部 Series，包括刚创建的新 Series；
3. 把“旧 Study manifest + 新 Series”冻结进同一个 Task Snapshot。

已采用以下最小修法，不改表、不改 Schema、不改变 Response：

- 只有本请求真正插入新 Series 时，才在同一请求级事务内重算 Study manifest；
- 创建前锁定 Study，并以 locking current read 检查 `series_key`，使相同/不同 key 的并发请求形成稳定串行顺序；
- 通过既有 `state_version + revision_id` CAS 推进 Study revision、清空 `ready_at`、状态改为 `validating`；
- 相同 `series_key + payload` 的幂等重放直接返回既有 Series，不重复推进 revision；
- 相同 `series_key` 但 payload 不同仍返回幂等冲突；
- Study CAS 失败时抛出状态冲突，由 endpoint 回滚整个事务，新 Series 不会单独遗留。

实现复用了 Image 变化已有的 Study manifest/completeness/revision 计算入口，避免 Series 创建和 Image 更新形成两套 revision 规则。当前 `SeriesResponse` 不返回新的 Study revision；调用方若下一步需要 finalize 或创建 Task，仍应通过 `GET /studies?id=` 取得最新 `revision_id/state_version`。

验证证据：定向 Ruff/compileall 通过；backend 现有测试 `94 passed, 22 warnings`；真实数据库回滚事务验证 revision `+1`、幂等重放 `+0`、payload 冲突拒绝和 CAS 失败整体回滚均通过。独立并发资格化证明两个不同 key 各成功并各推进一次 revision，两个相同 key 返回同一资源且只推进一次；临时资格化数据已全部清理。上线前只读扫描未发现 ready Study 下 `Series.created_at > Study.revision_changed_at` 的存量矛盾行。

### 5.5 缺失：`GET /api/v1/studies/page`

状态：`ADD-P2`

建议至少支持 `session_id`、`status`、`modality_type`、分页。先校验 Session owner，再由 StudyDal 分页，不在 endpoint 拼 SQL。

### 5.6 不新增独立 Series detail

状态：`NO-ADD`

当前 `GET /studies?id=` 已返回 Series。除非未来 Series 成为独立页面或需要独立权限，不需要为了 CRUD 完整感新增 `GET /series?id=`。

---

## 6. Image 接口逐项审计

### 6.1 四个 prepare/replace 接口的共同问题（审计基线；D1 已于 2026-08-28 修复）

以下四个接口共享同一组缺口：

- `POST /images/prepare-upload`
- `POST /images/prepare-multipart-upload`
- `POST /images/replace`
- `POST /images/replace-multipart`

共同结论：上传、对象键生成、ownership、幂等、CAS 和 OSS 事务拆分主体正确；医学输入元数据合同不完整。

具体缺口：

1. prepare request 没有 `projection`，虽然 Model/Response 已有该字段；
2. replace request 也没有 projection，无法决定继承旧值还是更正投照位；
3. validation worker 不提取 DICOM projection，当前 10 张真实 Image 的 projection 全为空；
4. canonical series manifest 不包含 projection；
5. Task Snapshot 只保存 Series 摘要；Prompt 的 `ordered_image_refs` 实际也是逐 Series，不是逐 Image；
6. 非 original Image 只要求 `source_manifest` 非空，不校验 source Image 是否存在、是否属于当前 owner、hash 是否匹配；
7. `source_manifest` 和 `technical_metadata` 都是宽松 JSON，没有合同版本对应的结构校验和大小上限。

projection 不能只加一个字符串。首版至少需要：

```json
{
  "projection": "VD",
  "projection_source": "caller_declared"
}
```

推荐候选：`caller_declared`、`dicom_extracted`、`reviewer_confirmed`。数据库仍使用 string/json，不使用 DB Enum。若不新增 `projection_source` 列，可先放入严格的 `technical_metadata.v2`，但 manifest 必须显式投影该来源，不能只把宽松 JSON 整包传给 Prompt。

replace 语义建议固定为：

- payload 未提供 projection：继承旧 Image 的 projection 和 source；
- payload 提供 projection：视为 metadata correction，写入新值和来源；
- 不允许把非空 verified 值静默改为空。

实施更新：上述 projection 四层链已一次完成，没有新增表、字段或迁移。新 prepare 必填 projection，输入只做 trim、非空和现有 `VARCHAR(64)` 最大长度校验，不转换大小写、不新增医学枚举或字符白名单；未知由调用方显式传 `UNKNOWN`。replace 省略时继承、显式值时更正、显式 null 拒绝。Service 生成 `caller_declared/xray-projection.v1` provenance 并拒绝调用方写保留 key；历史空值只规范为 `UNKNOWN/legacy_unspecified`，不伪造来源。canonical `series-image-manifest.v2`、`task-request-snapshot.v3`、Prompt 逐图 refs、Snapshot-only Provider input 和 `ai-image-receipt.v2` 已接通。旧 v1/v2 Snapshot 继续使用 legacy manifest builder。

当前真实库仍有 8 张 ready Image projection 为 NULL、8 个 Series 为 legacy manifest；本轮未获存量回填授权，因此没有改旧行。现有 9 个 v2 Task 只读复核全部仍可重放。新 D1 Revision 可创建 v3 Task；旧 ready Study 必须先形成新的受控 Revision。真实两视图 E1-MV 尚未运行，不能把代码完成写成医学或完整运行资格化。

### 6.2 `POST /api/v1/images/prepare-upload`

状态：`FIX-P1`

当前优点：direct upload ticket 有稳定 object key、Content-Type、TTL、generation；同一 uploading 请求可刷新过期时间；已有 ready 版本时强制走 replace。

必须修改：扩展 projection/provenance 合同，并贯通 `Image -> series manifest -> Task Snapshot -> Prompt`。只改 request schema 判定为未完成。

### 6.3 `POST /api/v1/images/prepare-multipart-upload`

状态：`FIX-P1`

除 6.1 的共同问题外，multipart 的 session 初始化发生在 DB 短事务外，绑定失败会尝试 OSS abort，逻辑正确。不要为 projection 另建 multipart 专用逻辑，应复用同一 schema 基类。

### 6.4 `POST /api/v1/images/replace`

状态：`FIX-P1`

当前正确：只允许替换 ready Image；校验 old state version；新版本先 uploading，验证成功后 CAS supersede old；失败不会提前破坏旧 ready 版本。

必须补：projection 继承/更正规则；derived source manifest 的新旧版本引用规则；metadata correction 应进入 Study revision reason。

### 6.5 `POST /api/v1/images/replace-multipart`

状态：`FIX-P1`

与 direct replace 使用相同的版本链和 CAS，multipart session 补偿合理。修改要求与 6.4 相同。

### 6.6 `POST /api/v1/images/prepare-upload-parts`

状态：`KEEP`

- body 中传 id/version/generation，符合项目禁止 `/{id}` 的规则；
- 校验分片号范围、重复、expected part count 和 ownership；
- 返回的 signed URL 标记为 repr false，源码未发现主动日志持久化。

验收时仍应检查响应和 access log 不记录 query/signature 正文。

### 6.7 `POST /api/v1/images/list-upload-parts`

状态：`KEEP`

虽然语义是读，但请求需要 id、CAS version 和 generation，使用 POST body 可以避免复杂 query，并不构成业务错误。接口会到 OSS 查询真实分片，再返回 receipt。

### 6.8 `POST /api/v1/images/complete-upload`

状态：`KEEP`

正确逻辑：

- direct PUT 使用 head object；multipart 先校验完整 receipts 再 complete；
- 校验 content type、对象版本和 generation；
- DB 状态 uploading -> validating 与 validation Outbox 同事务；
- 重复 complete 会验证既有 Outbox 和 multipart manifest，不重复创建事件。

注意：projection 不能在 complete 阶段临时补，它必须已在 prepare/replace 合同中冻结或由 DICOM validator 以明确来源提取。

### 6.9 `GET /api/v1/images?id=`

状态：`FIX-P2`

ownership 正确，但 Response 是内部宽 DTO，包含 object key、storage profile、KMS key version、validation attempt 等。没有 Secret 或签名 URL，但普通上游是否需要这些字段未定义。

建议拆分：

- Runtime `ImageResponse`：资源身份、version、projection、status、sha/size、error code；
- Admin/diagnostic response：对象存储和 validation 内部字段。

如果现有调用方已依赖字段，先版本化响应或只在新 page 接口使用精简 DTO，不能直接破坏兼容。

### 6.10 `POST /api/v1/images/abort-upload`

状态：`KEEP-WITH-GC-RISK`

multipart 会先调用 OSS abort，再把 DB 状态 CAS 为 quarantined；OSS abort 失败时不会假装 DB 已完成，属于 fail-closed。

direct PUT abort 不删除可能已上传的对象，multipart/complete 的跨边界崩溃也可能遗留对象。需要后台 object GC/reconcile 合同，不需要另加 public delete API。

### 6.11 `GET /api/v1/images/page`

状态：`IMPLEMENTED-P1（2026-08-27）`

这是比把 Images 全部嵌入 Study detail 更必要的恢复接口。

已实现查询：

- 必传 `series_id`；
- `status?`、`image_role?`、`current_only=true`、`page`、`page_size<=100`；
- 默认只返回每个 logical image 的 current version；历史版本需显式 `include_versions=true`。

`include_versions=true` 的优先级高于 `current_only`；`current_only=false` 也会返回历史版本。current 的定义是同一
`logical_image_key` 的绝对最新工作流版本，而不是“最新 ready 版本”。例如 v1 已 ready、v2 正在 uploading 时，默认查询返回
v2；此时 `current_only=true&status=ready` 返回空，不会退回 v1。若调用方需要旧 ready 版本，必须显式使用
`include_versions=true&status=ready` 或 `current_only=false&status=ready`。

实现链路保持：

```text
GET /images/page
-> ImagePageQuery
-> ImageService（Series -> Study -> Session owner，一次性校验）
-> ImageDal(DalBase) 分页
-> PagedResponse[ImagePageItemResponse]
```

分页稳定排序为 `sequence_no ASC -> logical_image_key ASC -> image_version_no DESC -> id ASC`。默认 current 查询在
ImageDal 使用相关 `NOT EXISTS` 排除存在更高版本的行；状态和角色过滤在 current 版本选择外层生效，不能意外回退到旧版本。

分页使用精简 DTO，返回 Image 身份、版本链、序号、role/kind、上传恢复字段、内容摘要、DICOM UID、projection、状态、错误和
时间字段；不暴露 `object_key`、`storage_profile`、`object_version_id`、KMS、validation lease 和
`technical_metadata_json`。DAL 同时使用 `load_only` 避免从数据库读取这些内部列和大 JSON；需要内部宽字段时继续使用
owner-safe 的 `GET /images?id=`。

数据库未改表、未迁移、未增加索引。真实库 EXPLAIN 中主查询和相关子查询选择了已有
`uq_image_record_logical_version(series_id, logical_image_key, image_version_no)`；相关子查询为 `Not exists; Using index`，
没有退化为全表扫描。稳定排序当前仍有 `Using filesort`。由于当前真实库每个 Series 的样本最多只有 1 条，此结果只证明首版
查询形态和索引可用，不能作为大 Series 性能资格化证据；上线前应在生产等量级数据上复跑 EXPLAIN/延迟测试，再决定是否单独
授权增加排序复合索引。

已完成验证：

- OpenAPI 已暴露 `GET /api/v1/images/page` 和全部查询参数，响应为 `PagedResponse[ImagePageItemResponse]`；
- 真实 MySQL 回滚事务构造同 logical key 的 v1 ready、v2 uploading：默认只返回 v2，历史分页共 2 条，
  `current_only=true&status=ready` 不回退旧版本；回滚后无临时数据残留；
- 正确 owner 可查询，错误 owner 抛 `session_access_denied` 并沿用资源不存在映射，不能跨 requester 枚举；
- backend 全量测试 `94 passed, 22 warnings`；Ruff、compileall、`git diff --check` 通过；按项目约束未新增测试文件。

### 6.12 Segmentation 不新增专用 endpoint

状态：`DEFER-P2 / NO-SEPARATE-ENDPOINT`

`image_role=segmentation` 只是候选角色，不等于分割功能已经完成。后续应复用上述 prepare/replace/complete 上传链创建 derived Image，但前提是补齐：

- 版本化 source manifest；
- 源 Image ownership/hash 校验；
- segmentation metadata schema；
- current/history 查询；
- 对象生命周期和删除/作废语义。

不要新增一个只收 `image_id + organ_seg`、却绕过 Image/OSS/version 合同的 `/images/segmentation`。

---

## 7. Task 接口逐项审计

### 7.1 `POST /api/v1/tasks`

状态：`FIX-P1`

当前正确逻辑：

- 校验 Study owner、ready、revision ID 和 resolved manifest；
- 只读取 active immutable AI Config；
- 以 requester + request_id + task_type 构造业务幂等键；
- Task、首 Stage 和 Outbox 在同一事务创建；
- Snapshot 和 hash 冻结，Worker 不回读 mutable Prompt source。

已确认缺口：

1. `TaskCreate` 没有 clinical context；
2. Snapshot 没有逐 Image facts，只有 Series ID/manifest hash/count；
3. Prompt `ordered_image_refs` 是逐 Series，不是逐 Image；
4. C1 happy-path 已修复 `produced` 持久化，但非法 availability/result 组合仍需 C1.1 fail-closed；
5. `task_type=diagnose` 当前 `run_mode=validation_only`，不是生产医学发布；接口名称不能被解释为已获医学放行的生产诊断服务。

clinical context 首版建议严格 allowlist，例如：

```json
{
  "chief_complaint": "...",
  "symptom_duration": "...",
  "known_trauma": true,
  "clinical_question": "..."
}
```

要求：字段限长、禁止自由递归 JSON、进入 Snapshot 和 request SHA、经 leakage policy 后再给 Prompt；不新增 `/sessions/context`。

### 7.2 `GET /api/v1/tasks?id=`

状态：`FIXED（2026-08-27）`

修复前 owner 校验正确，但不满足稳定轮询合同：

- Model 有 `current_report_id`，Response 没有；
- Model 有 `started_at`、`finished_at`、`next_retry_at`、`deadline_at`，Response 没有；
- 27 号文档称它返回 stage summary，实际完全没有 stage 字段；
- Response 暴露 `request_snapshot_json`、Config identity 和 pipeline stages/hash。当前真实 Snapshot 没有 raw Prompt/Secret，但这些仍属于内部执行资料，不应成为普通轮询的长期兼容合同。

长期仍建议拆成：

- `TaskStatusResponse`：id、study/revision、task_type、execution_status、ai_medical_status、state_version、current_report_id、error_code、cancel facts、started_at、finished_at、created_at、updated_at；
- Admin task detail：Snapshot、Config/assignment hashes、Stage 摘要。

本轮采用兼容策略，在现有 `TaskResponse` 增加四个 nullable 字段：

- `current_report_id`：当前可读取 Report ID；未生成、replay、失败、取消或作废后可为空；
- `started_at`：首次从 queued 进入 running 的时间；执行前取消时可为空；
- `finished_at`：completed/failed/cancelled/dead_letter 的终态时间；非终态为空；
- `next_retry_at`：预留为 Task retry_wait 的下一次执行时间；当前 Task 主链没有写入 retry_wait/next_retry_at，实际会返回空，Stage/Outbox/Attempt 的重试时间不投影到这里。

字段直接从已有 Task ORM/物理列投影，不增加 Service 拼装、数据库字段或迁移。因为 `POST /tasks`、`GET /tasks?id=` 和 `POST /tasks/cancel` 共用 `TaskResponse`，三个接口会一致返回这些字段，这是向后兼容扩展。

轮询停止规则：`completed/failed/cancelled/dead_letter` 为终态，调用方停止轮询；`queued/running/retry_wait` 为非终态。`completed + task_type=replay + current_report_id=null` 表示无需 Report；`completed + task_type=diagnose + current_report_id` 可直接查询当前 Report。`completed + task_type=diagnose + current_report_id=null` 不是正常报告定稿结果，当前可能由尚未修复的 Report void 语义造成，调用方应视为 Report 不可用而不是 replay。内部 Snapshot/Config 字段暂不删除，后续在 `/tasks/page` 使用精简 DTO，避免破坏已有调用方。

验证证据：OpenAPI 已包含四个 nullable 字段；真实数据库 9 个终态 Task 均可投影，其中 9/9 有 `finished_at`、4 个有 `current_report_id`、执行前取消的 Task 允许 `started_at=null`、Task `next_retry_at` 当前 9/9 为空；正确 owner 读取成功、错误 owner 仍被拒绝；backend 全量 `94 passed, 22 warnings`。

### 7.3 `POST /api/v1/tasks/cancel`

状态：`KEEP`

- owner 和 expected state version 检查正确；
- 只记录 cancel request，Worker 在安全边界收敛 Task/Stage；
- 已有 cancel request 的重放直接返回当前 Task；
- completed/failed/cancelled/dead_letter 不允许重新取消。

接口文档必须明确这是异步取消请求，不保证响应时 Task 已进入 cancelled；调用方继续轮询至终态。

### 7.4 `GET /api/v1/tasks/page`

状态：`ADDED（2026-08-28）`

已实现查询：`session_id?`、`study_id?`、`execution_status?`、`task_type?`、`created_from?`、`created_to?`、`page`、`page_size`。`session_id` 与 `study_id` 至少提供一个，`page_size` 范围为 1..100；时间范围为闭区间，输入必须携带时区，并在 Schema 边界统一转换为 UTC naive 值后与 MySQL `DATETIME(6)` 比较。状态只接受 `pending/queued/running/retry_wait/completed/failed/cancelled/dead_letter`，Task 类型只接受当前 Runtime 可创建的 `replay/diagnose`。

所有者与作用域采用双层 fail-closed 校验：Service 先读取指定 Study/Session 并按其 Session `requester_id` 校验 JWT subject；两者同时传入时要求 `study.session_id == session_id`，否则返回资源状态冲突。TaskDal 查询仍强制 `Task.requester_id == caller.subject_id`；Task 表没有 `session_id`，因此仅在需要 Session 过滤时由 TaskDal 关联 Study。API/Service 均未直接拼 SQL。

返回 `PagedResponse[TaskStatusResponse]`，按 `created_at DESC, id DESC` 稳定排序。精简项包含 Task/Study/revision、执行与医学状态、state_version、`current_report_id`、trace/error、retry/cancel/终态时间，但不包含 `request_snapshot_json`、预算、Pipeline/assignment hash、错误消息或取消原因等内部执行材料。

本轮没有新增表、字段、迁移或测试文件。现有 `ix_task_record_study_created`、`ix_task_record_requester_created` 和 `ix_study_record_session_created` 可支撑首版 scope/order 查询；大 Session + 多状态/时间组合的执行计划与延迟仍需在等量数据上验证，当前不为未证实的性能问题增加索引。

验证证据：Ruff 与 compileall 通过；OpenAPI 正确暴露 8 个查询参数和 `PagedResponse[TaskStatusResponse]`，且精简 DTO 不含 Snapshot；SQL 合同核实 owner、Session/Study、状态、类型和稳定排序条件同时存在；Service 作用域/错误 owner/mismatch 分支通过；backend 全量 `94 passed, 22 warnings`；真实 MySQL 只读验证通过 Study 查询、Session + status/type 查询、闭区间时间查询、分页和错误 owner 隔离。

### 7.5 Stage 查询不放普通 Runtime

状态：`DEFER-P2-ADMIN`

`StageCheckpointResponse` schema 已存在但无 endpoint。Stage input/output 可能含内部模型结果和执行细节，不建议直接加入 caller `GET /tasks`。

若运维确实需要，新增 Admin `GET /tasks/stages?task_id=`，只返回脱敏 stage status/lease/retry/error/timing；原始 input/output 需要更高权限或不返回。

---

## 8. Report 接口逐项审计

### 8.1 Report 全局阻断：缺 `state_version`

Report ORM、真实 `report_record`、`ReportResponse` 都没有 `state_version`，但：

- `ReportDal.cas_update()` 调用 `DalBase.cas_put_data()`，默认访问 `Report.state_version`；
- `ReportService.publish/void` 传 expected version；
- `ReportService.finalize` 在第二版 Report 出现时读取 `previous.state_version` 做 supersede。

因此不是单纯“Response 少一个字段”，而是完整 CAS 合同不存在。

修复选择：

1. 推荐：Report 新增 string-independent `BIGINT state_version`，ORM/Schema/DAL/物理表一致；
2. 不推荐：取消 CAS，改成只按 status 条件更新。它会让 Report 成为项目中唯一没有版本 expectation 的可变资源。

选择 1 需要表字段和迁移授权；在修复前 publish/void 应视为不可用。

### 8.2 `GET /api/v1/reports?id=`

状态：`KEEP-WITH-VISIBILITY-FIX`

- owner 通过关联 Task 校验，逻辑正确；
- 当前按 ID 可读取 final、published、superseded、void 任意状态内容。

需明确：历史/void 内容是审计可见，还是普通调用方只允许读 current。推荐保留历史可见，但 Response 明确 `status` 和 `is_current`；业务展示只使用 current。

### 8.3 `GET /api/v1/reports/history?task_id=`

状态：`FIX-P2`

owner 校验正确，按 revision 倒序，但当前 `limit=0` 不分页。Report 数量通常较少，不是立即性能阻断；在允许重复修订/作废后应改为 `PagedResponse`。

### 8.4 Admin `POST /api/v1/reports/publish`

状态：`BLOCKED-P0 + REMOVE/DEPRECATE-CANDIDATE`

代码当前因缺 state_version 不可用。即使修好 CAS，现有 Runtime report 查询不以 published 控制可见性，`final` 已直接返回，所以 publish 不改变交付结果。

用户已明确不做人工复核工作流，`review_required` 也是可交付终态。基于这个决定，建议：

- 从当前产品主链移除/停用 publish，而不是为了一个无效果状态继续扩建；
- 如果未来重新引入发布门，必须同时定义 Runtime visibility、actor、audit、delivery 状态和回滚规则。

### 8.5 Admin `POST /api/v1/reports/void`

状态：`BLOCKED/FIX-P0`

当前问题：

- 缺 state_version；
- request 没有 reason；
- endpoint 丢弃 ControlPlane actor；
- 没有 Report 操作 Audit；
- void 后 Task 仍 `execution_status=completed`、`ai_medical_status` 保留原值，只清空 current pointer；
- history 和按 ID 查询仍返回 void 内容。

如果保留 void，至少需要：reason、actor、voided_at、Audit、Task 当前交付状态定义。不要把医学 status 改成 `not_produced` 来覆盖历史真实结果；可在 Task 增加 delivery/current result 投影，或由 `current_report_id=None` 明确表示当前无可交付报告。

### 8.6 已补齐：`GET /api/v1/reports/current?task_id=`

状态：`ADDED（2026-08-28）`

该接口通过 `ReportService.get_current_for_requester()` 按 Task owner 读取当前可交付 Report，只允许返回 `final/published`，避免调用方先取 history 再猜第一条。

Response 允许 `data=null` 表示 Task 尚未产出 Report、replay Task 不要求 Report，或 void 后 `current_report_id` 已被清空。Task 不存在或 owner 不匹配统一返回 404；pointer 指向不存在的 Report、其他 Task 的 Report 或 `void/superseded` Report 时同样 fail-closed 为 404，不能把 pointer 漂移伪装成合法空结果。

### 8.7 缺失：`GET /api/v1/reports/view?task_id=`

状态：`DEFER-P2`

当前 Report `content_json` 是 decision finalization output，`complete_medical_result.findings[*]` 仍是自由 object。现在实现 view 会迫使 Python 猜测 summary、disease list 或字段含义，违反“不在 Python 做医学判断”。

正确顺序：

1. 先完成 CompleteMedicalResult v2 的稳定字段级 Schema；
2. 模型直接输出展示所需医学字段；
3. Python renderer 只做字段选择、排序、缺失标记和原文透传；
4. 再实现 Report view；
5. segmentation 只作为关联 derived Image 投影，不在 renderer 推导。

### 8.8 明确不新增 Report 通知

状态：`NO-ADD`

用户已决定由上游轮询 Task + Report，不增加 webhook、消息通知或回调。本轮只需把轮询终态、current_report_id、退避和总超时合同写清楚。

---

## 9. Runtime Admin 接口逐项审计

### 9.1 公共管理接口

| 接口 | 状态 | 结论 |
|---|---|---|
| Admin `GET /` | `FIX-P2` | 无鉴权根页只返回服务/docs 信息；生产 docs 策略需一致 |
| `GET /api/v1/status` | `KEEP` | admin read scope；只证明鉴权和进程可响应 |
| `GET /api/v1/info` | `FIX-P2` | version 硬编码，timestamp 是请求时间；应接真实 build metadata |
| `GET /api/v1/readiness` | `FIX-P1` | 复用全局 readiness，仍被 Evaluation 平面耦合；Admin 可展示聚合，但需明确 degraded 状态 |
| `GET /api/v1/operations/status` | `FIX/BLOCKED-P1` | 聚合在线/Evaluation 指标合理；Evaluation DB 缺失时依赖注入/查询会让整个接口失败，不能返回部分在线状态 |
| `POST /api/v1/reports/publish` | `BLOCKED/DEPRECATE` | 见 8.4 |
| `POST /api/v1/reports/void` | `BLOCKED/FIX-P0` | 见 8.5 |

### 9.2 operations/status 的推荐降级合同

运营接口应该在某个依赖不可用时仍返回：

```json
{
  "online": {"state": "ready", "metrics": {}},
  "evaluation": {"state": "unavailable", "error_code": "evaluation_database_unavailable"},
  "alerts": []
}
```

不能暴露驱动异常、DSN 或凭据。实现时可让 Service 分段捕获受控依赖错误，或把在线与评测拆成两个子 Service，再由 API 聚合；仍不新增第二套数据库访问基类。

---

## 10. AI Control 接口逐项审计

### 10.1 总体结论

AI Control 是当前接口设计最完整的一组：所有业务写操作都有 `request_id`、Audit replay、CAS；分页接口有 page/page_size；Response 都包含 state_version；Config activate/rollback 对 current active 使用 paired expectation。

需要特别纠正一个语义：Connection、ModelPool、Config 的 `validate` 是静态结构/引用/hash 验证，不等于真实 Provider qualification（资格化）。当前控制面可以激活一条结构正确但运行不可达的 Connection。

AI Control 还有一个无鉴权 `GET /` 根接口，只返回服务/docs 信息，状态为 `FIX-P2`：生产 OpenAPI/docs 策略应与 Runtime 一致。

### 10.2 Prompt 接口

| 接口 | 状态 | 当前逻辑与处理要求 |
|---|---|---|
| `POST /api/v1/ai-prompts` | `KEEP` | draft 创建、request replay、Audit 同事务 |
| `PUT /api/v1/ai-prompts` | `KEEP` | 仅 draft 可改，expected state version CAS |
| `GET /api/v1/ai-prompts/detail?id=` | `KEEP` | admin write scope 下读取完整 Prompt；权限较高，合理 |
| `GET /api/v1/ai-prompts/page` | `KEEP` | prompt_key/status 分页 |
| `POST /api/v1/ai-prompts/validate` | `KEEP` | 校验语言、变量、message contract、content hash；不是医学质量验证 |
| `POST /api/v1/ai-prompts/retire` | `KEEP` | draft/validated -> retired，reason + Audit |
| `POST /api/v1/ai-prompts/import` | `FIX-P1` | Nacos 导入、receipt/hash/audit 正确；但先做 DB replay/read，再在同一 request transaction 内等待 Nacos 网络，应拆成 DB 预检 -> 网络 fetch -> DB 持久化三个阶段 |

Prompt import 的网络拆分可复用 Image workflow 的显式短事务思路，不新增平行 Service/Repository。

### 10.3 Connection 接口

| 接口 | 状态 | 当前逻辑与处理要求 |
|---|---|---|
| `POST /api/v1/ai-connections` | `KEEP` | 只保存非敏感路由和 capability；Secret 仍只来自进程环境 |
| `PUT /api/v1/ai-connections` | `KEEP` | draft-only CAS + Audit |
| `GET /api/v1/ai-connections/detail?id=` | `KEEP` | Response 无 secret_ref，但会返回 base_url；限 admin write scope |
| `GET /api/v1/ai-connections/page` | `KEEP` | provider_type/status 分页 |
| `POST /api/v1/ai-connections/validate` | `KEEP-BUT-CLARIFY` | 当前仅 canonical URL + connection hash 校验，绝不应宣称已连通 Provider |
| `POST /api/v1/ai-connections/retire` | `KEEP` | draft/validated -> retired；已冻结 Config 仍保留 snapshot |

缺失但暂不立即新增：`POST /ai-connections/qualify`。如果要让 active Config 代表可运行，它应产生真实连接、认证、模型能力和时间绑定的 qualification receipt。该能力可能需要持久化 qualification 状态/时间/hash，需单独设计和迁移授权，不能偷偷塞进现有 validate。

### 10.4 ModelPool 接口

| 接口 | 状态 | 当前逻辑与处理要求 |
|---|---|---|
| `POST /api/v1/ai-model-pools` | `KEEP` | draft + request replay + Audit |
| `PUT /api/v1/ai-model-pools` | `KEEP` | draft-only CAS |
| `GET /api/v1/ai-model-pools/detail?id=` | `KEEP` | 返回冻结 lane plan 元数据 |
| `GET /api/v1/ai-model-pools/page` | `KEEP` | execution_mode/status 分页 |
| `POST /api/v1/ai-model-pools/validate` | `KEEP-BUT-CLARIFY` | 校验单 lane 和 Connection binding/hash，不代表模型网络资格化 |
| `POST /api/v1/ai-model-pools/retire` | `KEEP` | draft/validated -> retired |

### 10.5 AI Config 接口

| 接口 | 状态 | 当前逻辑与处理要求 |
|---|---|---|
| `POST /api/v1/ai-configs/compile-preview` | `KEEP` | 纯计算预览，不写 Audit/DB 状态，合理 |
| `POST /api/v1/ai-configs` | `KEEP` | 冻结 Prompt/Model/Schema/Pipeline snapshot，request replay + Audit |
| `GET /api/v1/ai-configs/detail?id=` | `KEEP` | 返回安全摘要，不回传 raw Prompt content/model snapshot |
| `GET /api/v1/ai-configs/page` | `KEEP` | config_key/status 分页 |
| `GET /api/v1/ai-configs/active` | `KEEP` | 按 config/modality/task/scope 查 active slot |
| `POST /api/v1/ai-configs/validate` | `KEEP-BUT-CLARIFY` | 重编译、source/hash 校验；不等于 Provider runtime qualification |
| `POST /api/v1/ai-configs/activate` | `KEEP` | validated-only；paired current expectation；退役旧 active 和激活 target 同事务 |
| `POST /api/v1/ai-configs/retire` | `KEEP` | 可退役 active 并清 slot；调用方必须接受 slot 暂时无 active Config |
| `POST /api/v1/ai-configs/rollback` | `KEEP` | retired v2 target + frozen hash 验证 + paired current expectation |

### 10.6 Audit 接口

| 接口 | 状态 | 当前逻辑与处理要求 |
|---|---|---|
| `GET /api/v1/ai-control-audits/page` | `KEEP` | resource/actor 分页，append-only Audit 的读取入口完整 |

### 10.7 AI Control 缺失的运行探针

| 接口 | 状态 | 要求 |
|---|---|---|
| `GET /api/v1/health` | `ADD-P1` | 只证明 AI Control 进程存活 |
| `GET /api/v1/readiness` | `ADD-P1` | 主库、JWT verifier、Nacos（按是否启用导入决定 required）；不要复用 Runtime+Evaluation 全局 ready |

---

## 11. Evaluation Control 接口逐项审计

### 11.1 整组接口的当前运行状态

所有 Evaluation 业务路由代码都存在，但当前环境：

- `MYSQL_EVALUATION_DB=ms_image_eval`；真实连接返回 MySQL 1049 database not found；
- 四张 Evaluation 表错误地存在主库，且当前均为空；
- Evaluation Model 与在线 Model 共用 `BaseModel.metadata`；
- Alembic 只使用主库 URL，没有 Evaluation metadata filter/独立 env；
- 两份 migration revision 都没有创建 Evaluation 四表。

因此下列接口在修复 DB/迁移前统一标记为 `BLOCKED`。不能因 OpenAPI 能生成就宣称可用。

Evaluation Control 另有一个无鉴权 `GET /` 根接口，只返回服务/docs 信息，状态为 `FIX-P2`：生产 OpenAPI/docs 策略应与其他应用一致。

### 11.2 Job 接口

| 接口 | 代码逻辑 | 状态 | 处理要求 |
|---|---|---|---|
| `POST /api/v1/evaluation/jobs` | fingerprint、split、denominator、Artifact refs；requester+request_id 幂等；Job+Artifact+Outbox 同事务 | `BLOCKED; KEEP-AFTER-DB` | 独立 DB 就绪后保留；继续限制 object_ref/provenance 的版本和尺寸 |
| `POST /api/v1/evaluation/jobs/export` | 从在线 DB 冻结 Task/Report 等事实，写 OSS，再在 Evaluation DB 创建 Job | `BLOCKED; FIX-P1` | 跨 online DB/OSS/eval DB 无补偿；OSS 成功、Job 失败会留孤儿对象，需 deterministic object key + retry reuse 或 GC/compensation |
| `GET /api/v1/evaluation/jobs?id=` | 按 ID 返回 state_version | `BLOCKED; KEEP-AFTER-DB` | 控制面全局资源读取可保留 |
| `POST /api/v1/evaluation/jobs/cancel` | Job CAS cancelled，并取消已 started Run | `BLOCKED; FIX-P1` | 不失效已发布 Outbox；没有 cancel reason/actor audit；补 Worker/outbox cancel contract |

### 11.3 Run / Artifact 接口

| 接口 | 代码逻辑 | 状态 | 处理要求 |
|---|---|---|---|
| `POST /api/v1/evaluation/runs` | 公开手工创建 `len(rows)+1` 的 started Run | `BLOCKED; REMOVE/REDESIGN` | 无 request_id/幂等；与 Worker 固定 `run_no=1` 冲突。首选移除公开创建，由 Worker 单一创建；若保留需 manual run 独立语义和幂等 |
| `GET /api/v1/evaluation/runs?job_id=` | 返回 Job 全部 Runs | `BLOCKED; FIX-P2` | `limit=0`，改分页；先确认 Job 存在 |
| `GET /api/v1/evaluation/runs/detail?id=` | 按 ID 返回 Run/state_version | `BLOCKED; KEEP-AFTER-DB` | 保留 |
| `GET /api/v1/evaluation/artifacts?job_id=` | 返回 Job 全部 Artifacts | `BLOCKED; FIX-P2` | `limit=0`，改分页 |
| `GET /api/v1/evaluation/artifacts/detail?id=` | 返回 object ref、hash、provenance | `BLOCKED; KEEP-AFTER-DB` | 只返回稳定 object ref，不返回长期签名 URL，合理 |

### 11.4 Evaluation 缺失接口

| 接口 | 状态 | 用途与边界 |
|---|---|---|
| `GET /api/v1/health` | `ADD-P1` | Evaluation Control liveness |
| `GET /api/v1/readiness` | `ADD-P0` | 独立 Eval DB、Evaluation Worker/Broker、Artifact store；在 DB 修复后作为部署 Gate |
| `GET /api/v1/evaluation/jobs/page` | `ADD-P1` | 按 status/fingerprint/created time 分页发现 Job |
| `POST /api/v1/evaluation/artifacts/prepare-download` | `DEFER-P2` | 仅当管理 UI/外部评测消费者需要下载时生成短 TTL URL；不把 signed URL持久化进 Artifact JSON |

### 11.5 Fake scorer 的边界

Worker 当前默认 `FakeEvaluationScorer`，源码明确写着 deterministic non-medical scorer。它只能验证冻结状态比较和工程 Artifact 流程，不能证明医学准确率。

在替换为已验证 scorer、建立冻结 Gold、Failure Bank、paired A/B 和 holdout 前：

```text
MEDICAL_ACCURACY = UNKNOWN
MEDICAL_RELEASE = NO-GO
```

不新增 fixed-bank CRUD API；复用 Evaluation Job/Run/Artifact 表达病例集和实验。

---

## 12. 数据库与迁移审计

### 12.1 已确认正确

- 20 张业务表 + `alembic_version`；
- ORM 与当前物理表的列、普通索引、唯一约束一致；
- 每张业务表都有独立非空 `id` 单列主键；
- foreign key 数量 0；DB Enum 数量 0；缺失 comment 的业务字段数量 0；
- 核心父子关系当前无孤儿；Task current report pointer 当前无漂移。

### 12.2 已确认异常

| 项目 | 当前事实 | 影响 |
|---|---|---|
| Report CAS | ORM/物理表均无 state_version | publish/void/supersede 不可用 |
| Evaluation isolation | 独立库不存在，四表在主库 | Evaluation 全接口不可用，隔离目标未实现 |
| Alembic baseline | 两份 revision 只显式 create 5 张表 | 不能从空库重建 20 表，不能证明升级/回滚 |
| Projection | 10 张 Image 的 projection 全为空 | 多视图输入证据链未建立 |
| Medical status legacy | 9 个 Task 中 3 个 produced；4 个 Report 中 3 个 produced | 存量非法状态会污染 Evaluation export；修数需单独授权 |

### 12.3 新接口与表变更关系

| 开发项 | 是否需要新表 | 是否需要字段/迁移 |
|---|---:|---:|
| 修 `POST /series` revision | 否 | 否 |
| Image projection 全链 | 否 | `projection` 已存在；projection source 若放严格 JSON 可暂不迁移 |
| Task clinical context | 否 | 否，冻结在 Snapshot JSON |
| Task/Session/Study/Image page | 否 | 首版复用现有索引；真实 explain 后再决定复合索引 |
| Task Response current report/timing | 否 | Model 字段已存在 |
| Report current endpoint | 否 | 否 |
| Session complete/cancel 与 Task 生命周期联动 | 否 | 否，复用 Session/Task 状态、取消字段和 `state_version` |
| Report CAS | 否 | 是，`report_record.state_version` |
| Evaluation DB 修复 | 否（已有四个目标 Model） | 是，独立迁移环境和四表 migration |
| Segmentation derived Image | 否 | 首版复用 Image；前提是 JSON 合同严格化 |

任何新迁移前先修复空库可重建 baseline。本文不生成迁移脚本。

---

## 13. 必补、后置和明确不补的接口

### 13.1 建议近期补齐

| 顺序 | 接口 | 原因 |
|---:|---|---|
| 1 | `GET /images/page`（已完成） | 上传恢复和资源发现的基础能力；大 Series 排序性能仍需等量数据验证 |
| 2 | `GET /tasks/page`（已完成，2026-08-28） | 按 Session/Study 恢复任务和报告入口；大 Session 性能待等量验证 |
| 3 | `GET /reports/current?task_id=`（已完成，2026-08-28） | owner-safe 暴露当前可交付 Report，并对 pointer 漂移 fail-closed |
| 4 | AI Control `/health`、`/readiness` | 独立应用需要独立部署 Gate |
| 5 | Evaluation `/health`、`/readiness` | 先真实暴露 DB unavailable，再作为修复 Gate |
| 6 | `GET /evaluation/jobs/page` | Evaluation 修复后最基本的控制面发现能力 |

Session/Study page 可在上游页面或恢复流程需要时紧随其后，不阻塞当前单病例主链。

### 13.2 产品后置

- `/reports/view?task_id=`：等待 CompleteMedicalResult v2；
- Admin task/stage 诊断详情：等待真实运维消费者；
- Evaluation Artifact prepare-download：等待下载消费者；
- Connection qualify：需要 qualification 持久合同和真实 Provider Gate；
- 两步 diagnosis plans/commits：上游集成复杂度真的出现后再做；
- Config release-state/shadow/gray：M1 后再设计；
- segmentation 展示：derived Image 合同完成后再做。

### 13.3 明确不新增

- 不新增 `/{id}` 路由；
- 不新增 `/sessions/context`，clinical context 归 Task；
- 不新增独立 fixed-bank CRUD，复用 Evaluation；
- 不新增 `/images/segmentation` 旁路上传；
- 不新增 Report webhook/通知；
- 不新增 HTTP reconcile 接口，unknown attempt 应由可靠 scheduler/worker 自动处理；
- 不新增 `study.projection_summary_json` 双写真相；
- 不新增独立 Series detail，当前 Study detail 已覆盖。

---

## 14. 推荐逐接口开发顺序

这份顺序同时考虑“现有接口是否会产生错误事实”和“用户能否逐个验收”，不是按文档章节顺序机械开发。

### Slice 0：先处理部署和不可调用事实

1. 决定 Admin Report publish 是否直接停用；
2. 若保留 void/revision，授权并补 Report state_version；
3. 修复 Alembic 可重建 baseline；
4. 建立独立 Evaluation migration env/DB，再谈 Evaluation endpoint 功能。

验收：Report CAS 不再 AttributeError/SQL unknown column；空库 migration replay 可重建；主库不再包含目标 Evaluation 表。

### Slice 1：修 `POST /series`（已完成）

文件范围：

- `schemas/study.py`（若增加 revision expectation）；
- `service/study_service.py`；
- `crud/study.py`、`crud/series.py`；
- 不新增表。

验收结果：ready Study 新增 Series 后立即变为 validating 且 revision 已推进，旧 revision 不能再创建 Task；重复 create 不重复推进 revision；CAS 失败时 Series 与 Study 同事务回滚。

### Slice 2：修 `GET /tasks?id=`（已完成）

文件范围：

- `schemas/task.py`；
- `service/task_service.py`；
- `api/.../tasks.py`。

首版已补 `current_report_id`、`started_at`、`finished_at`、`next_retry_at`，并写清终态集合；未实现 stage detail。

验收结果：四字段已进入 OpenAPI 和真实 ORM 投影；终态均有 `finished_at`；completed diagnose 可直接取得 report ID；执行前 cancelled 的 `started_at` 可为空；owner 隔离保持不变。

### Slice 3：新增 `GET /images/page`（已完成）

文件范围：Schema -> ImageDal 分页 -> ImageService ownership -> endpoint。

验收结果：不同 owner 不可枚举；默认 current 不返回 superseded/deleted；分页稳定排序；owner 只沿
Series -> Study -> Session 校验一次，无逐 Image N+1；历史版本需显式 opt-in。最新工作流版本与最新 ready 版本已明确分离，
状态过滤不会回退旧版本。

### Slice 4：D1 projection 四层链（代码完成，E1-MV 待运行）

一次完成：

```text
prepare/replace request
-> Image projection + source
-> canonical series manifest/hash
-> Task Snapshot ordered images/hash
-> Prompt safe context / Provider receipt
```

不能拆成“先加 request 字段，以后再接 manifest”，因为前半段单独上线只会制造死字段。

验收：真实多视图病例逐图对账 Image ID、projection、manifest hash、Snapshot、Prompt command、Provider image receipt；replace 继承/更正均有证据。

2026-08-28 代码验收：OpenAPI、Pydantic 边界、manifest hash、Snapshot v3、Prompt refs、冻结 Provider inputs、receipt v2、replace 继承/更正和旧 v2 replay 均通过定向合同检查；backend 全量 `94 passed, 22 warnings`。真实 E1-MV 病例未运行，因此 Slice 只关闭 `CODE_IMPLEMENTED`，运行证据保持待办。

### Slice 5：D2 Task clinical context

只改现有 `POST /tasks`，不新增 endpoint/表。验收 caller allowlist、长度、Snapshot hash、Prompt leakage 和重放一致性。

### Slice 6：Session 与 Task 生命周期

状态：`COMPLETE（2026-08-28）`。

已采用完整诊断会话语义，并完成：

```text
POST /sessions/complete
-> 锁 Session
-> 检查 Study/Image 原门禁
-> 拒绝任意非终态 Task
-> CAS Session completed

POST /sessions/cancel
-> 锁 Session
-> 锁并枚举全部非终态 Task
-> 原子写 cancel_requested_*
-> CAS Session cancelled
-> Worker 后续安全收敛 Task
```

`POST /tasks` 同步增加 Session 行锁和 open/processing 状态门禁，防止 complete/cancel 与新 Task 创建穿透。没有新增表、迁移、`cancelling` 状态或 `pending_task_count`；cancelled 表示取消请求已接受，不表示响应时全部 Task 已收敛。

验收结果：静态检查、全量 backend 测试 `94 passed`、真实 MySQL 回滚事务合同验证均通过。已验证 active Task 阻止 complete、terminal Task 不阻止 complete、cancel 只请求非终态 Task、first-request-wins、同 reason 重放幂等，以及终态 Session 拒绝创建新 Task。跨连接并发资格化仍应在发布环境执行。

### Slice 7：Task page + Report current

状态：`COMPLETE（2026-08-28）`。`GET /tasks/page` 与 owner-safe 的 `GET /reports/current?task_id=` 均已完成，最小上游恢复与轮询入口已经闭合。后续按真实消费者决定 Session/Study page 和宽 Report view；当前恢复闭环已与 Slice 6 的 Session/Task 生命周期合同对齐。

### Slice 8：Evaluation 接口修复

顺序固定为：

```text
独立 DB/migration
-> /health + /readiness
-> create/get/cancel Job
-> export compensation
-> jobs page
-> Run owner 单一化
-> Run/Artifact pagination
-> 医学 scorer / M1
```

---

## 15. 高风险接口验收卡

### 15.1 Report CAS 验收卡

- 新建 final Report 返回 state_version；
- 相同 expected version 只能有一个 publish/void 成功；
- 旧 expected version 返回 409；
- 第二 revision 原子 supersede previous；
- void 必须记录 actor/reason/audit；
- Task current pointer 与 Report status 不漂移；
- publish 若停用，路由从部署/OpenAPI 明确移除或返回稳定 deprecated 错误，不能静默保留坏实现。

### 15.2 Series revision 验收卡

- ingesting Study 创建首 Series 正常；
- ready Study 创建新 Series 后旧 revision 立即不可用于新 Task；
- 相同 series_key/payload 重放返回同一资源；
- 相同 series_key/不同 payload 返回幂等冲突；
- 并发创建不产生两个 Series，不重复递增 revision。

### 15.3 Task polling 验收卡

- Response 明确 current_report_id；
- cancelled/failed/dead_letter 停止轮询；
- completed + no report（replay）与 completed + report（diagnose）可区分；
- 若未来实现 Task retry_wait，必须同时给出 next_retry_at；当前主链未实现该状态写入；
- caller 不能读取其他 requester Task；
- 不返回 Secret、signed URL、raw Provider response。

### 15.4 Image projection 验收卡

- prepare direct/multipart 接收相同 projection contract；
- replace direct/multipart 采用相同继承/更正规则；
- projection/source 被 canonical hash 覆盖；
- ready Image 更正会产生新 Study revision；
- Task Snapshot 内逐 Image 顺序稳定；
- Prompt 不从 filename/body_part 猜 projection；
- 未知 projection 显式为空/unknown，不伪造标准位。

### 15.5 Evaluation 可用性验收卡

- Evaluation app 在独立 DB 空环境可 upgrade 并启动；
- 主库 migration 不创建 Evaluation 表；
- Evaluation readiness 能区分 DB、worker、artifact store；
- create Job 的 Artifact/Outbox 同事务；
- cancel 后旧 Outbox/Worker 不把 Job 写回 completed；
- export 重试不产生无限 OSS 孤儿；
- Job/Run/Artifact 列表都分页；
- Fake scorer 结果不标注为医学准确率。

---

## 16. 与 DeepSeek 方案相比新增发现

DeepSeek 已正确识别 C1 状态修复、projection 四层链、clinical context、Task list、Report view 后置和 segmentation 复用 Image 的方向。本轮源码/数据库逐接口审计补出了以下它没有覆盖完整的事项：

1. Report publish/void 不是“待完善”，而是因为缺 state_version 当前真实不可调用；
2. Evaluation 不是“接口已经可复用”，而是独立 DB 不存在、迁移边界错误，整组运行不可用；
3. ready Study 新增 Series 曾让旧 manifest 与新 Series 同时进入 Task Snapshot；现已通过同事务 revision 推进修复；
4. Runtime readiness 错误耦合独立 Evaluation 平面；
5. Session complete/cancel 曾与 Task 生命周期完全脱节；现已通过 Session 行锁、complete 非终态门禁和 cancel request 批量联动修复；
6. Image 原先缺最基本的分页发现接口；现已补齐 owner-safe `GET /images/page`；
7. Task detail 原先缺 current_report_id 和终态时间；四个轮询字段已补齐，精简 TaskStatus DTO 与 `/tasks/page` 也已落地；27 号所称 stage summary 仍不存在，且不应直接加入普通 Runtime 接口；
8. `source_manifest` 只校验非空，没有验证 derived Image 的真实来源、owner 和 hash；
9. projection 还缺来源可信度，不能把 caller string 直接当医学事实；
10. Prompt import 在 DB transaction 中等待 Nacos 网络；
11. AI Connection validate 只是结构校验，不是运行资格化；
12. AI Control/Evaluation Control 没有各自的 health/readiness；
13. Evaluation 缺 jobs page，Run/Artifact 列表无分页，public create Run 与 Worker owner 冲突；
14. 当前 Alembic baseline 不能从空库重建全部 20 张表，任何后续 migration 都缺可靠地基；
15. Report publish 与已确认“final 直接可交付、无人工复核工作流”的产品决定冲突，应停用而非继续扩建。

---

## 17. 关键源码与数据库证据索引

| 结论 | 证据位置 |
|---|---|
| 四个应用 root path/路由装配 | `apps/backend/services/runtime/main.py:27-45,77-88`；`services/ai_control/main.py:26-38`；`services/evaluation_control/main.py:26-38` |
| Session create/complete/cancel/close 与 Session 行锁 | `apps/backend/services/runtime/service/session_service.py`；`apps/backend/crud/session.py:get_by_id_for_update` |
| Study create/Series create | `apps/backend/services/runtime/service/study_service.py:92-194` |
| Study finalize/revision recompute | `apps/backend/services/runtime/service/study_service.py:213-376` |
| Task create 与 Snapshot、Session 接受新 Task 门禁 | `apps/backend/services/runtime/service/task_service.py:create_task` |
| Task get/cancel 与 Session 批量取消请求 | `apps/backend/services/runtime/service/task_service.py:get_task,cancel_task,request_cancellation_for_session`；`apps/backend/crud/task.py:list_non_terminal_for_session` |
| Image request/response 缺 projection write | `apps/backend/schemas/image.py:129-197,319-367,383-424` |
| Image prepare/replace/version | `apps/backend/services/runtime/service/image_service.py:330-705` |
| Image complete/validation/revision | `apps/backend/services/runtime/service/image_service.py:893-1026,1426-1510` |
| multipart 网络/事务补偿 | `apps/backend/services/runtime/service/image_upload_workflow.py:177-248,250-393` |
| manifest 丢失 projection | `apps/backend/core/imaging/manifest.py:56-138` |
| Prompt 的 ordered_image_refs 实为逐 Series | `apps/backend/services/runtime/stages/xray/prompt_commands.py:136-179` |
| Report Model/Response 无 state_version | `apps/backend/models/report.py:10-29`；`apps/backend/schemas/report.py:9-36` |
| Report CAS 错误入口 | `apps/backend/crud/report.py:50-54`；`apps/backend/core/crud.py:290-317` |
| Report finalize/publish/void | `apps/backend/services/runtime/service/report_service.py:43-207` |
| Runtime readiness 跨平面耦合 | `apps/backend/core/readiness.py:131-274` |
| Prompt import 在 DB read 后调用 Nacos | `apps/backend/services/ai_control/service/prompt_import_service.py:153-342` |
| Connection validate 仅静态校验 | `apps/backend/services/ai_control/service/api_connection_service.py:353-425` |
| Evaluation endpoint 全集 | `apps/backend/services/evaluation_control/api/api_v1/endpoints/evaluation.py:68-213` |
| Evaluation DB 隔离配置 | `apps/backend/core/async_db.py:12-59,164-178` |
| Alembic 只连接主库共享 metadata | `alembic_migrations/env.py:19-53,85-105` |
| Evaluation Model 混入共享 metadata | `apps/backend/models/__init__.py:17-22`；`apps/backend/models/evaluation.py` |
| Fake scorer 非医学 | `apps/backend/services/evaluation_control/service/evaluation_fake_scorer.py:42-48` |

真实 MySQL 只读检查结果：ORM/物理列与索引一致；20 张业务表主键、foreign key、DB Enum、comment 和核心孤儿检查见 `.agent-handoff/validation.md` 的“API、ORM 与真实 MySQL 只读审计”。该证据绑定 2026-08-27 当前本地环境，不应外推为其他环境状态。

---

## 18. 本文完成定义

本文最初完成的是审计和开发拆分；随着逐接口实施推进，已同步记录 Slice 1、2、3、6、7 的真实实现与验证结果。后续每次仍只选择一个 Slice，并在开工前确认：

- 是否改现有接口或新增接口；
- 是否需要表字段/迁移授权；
- 兼容调用方是谁；
- 正常、重复、并发、取消、越权和依赖失败如何验收；
- 是否需要真实 MySQL/OSS/Broker/Provider 运行证据；
- 是否只证明工程正确，还是已经具备医学证据。

当前在线主链下一项应优先在 D1 projection 四层链、D2 Task clinical context 与 Runtime readiness 平面隔离中选择；Report publish/void 和 Evaluation 仍受迁移地基与产品决策阻塞。在这些合同稳定前，不建议先做宽 Report view、segmentation 或两步 diagnosis orchestration。
