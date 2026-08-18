# P0 数据访问边界 artifact（证据产物）

> 中文阅读说明：`artifact` 是不可变证据产物；`DAL` 是数据访问层；其余英文术语请参阅[英文术语中英对照](../术语中英对照.md)。

状态：`PARTIAL`

当前源码证据：

- `app/core/crud.py:24` 定义 SQLAlchemy `DalBase`；其异步实体访问方法是新
  XRay 链唯一允许复用的 DAL 基类。
- `app/core/async_db.py` 提供 SQLAlchemy async engine、`AsyncSession` 和
  `get_async_session`。
- `app/crud/base.py:3,14` 仍存在 MongoEngine legacy `CRUDBase`，但 XRay 链
  不得 import 它。
- 目前已增加 validation-only Run/Snapshot/Checkpoint/ModelCall/Trace/Outbox
  model、DAL 和 Service 草案，但没有 migration；Checkpoint 的 claim/heartbeat/
  complete/fail/recover_expired 与 Outbox 的 claim/heartbeat/published/retry/
  dead-letter/recover_expired 均统一通过 DalBase.conditional_update；ModelCall 通过
  `XRayModelCallDal` 写入 Prompt/provider fingerprint 和 receipt 摘要；因此本 artifact 不证明
  DB-backed 业务持久化已经部署完成。TraceEvent 的确定性技术事件使用
  `create_event_once`（append-or-read savepoint），Checkpoint/Trace 查询增加 tenant-leading
  索引，但仍没有 migration。

验收规则：新增实体只能在 `app/crud/xxx.py` 定义一个继承 `DalBase` 的
`XxxDal`；API/Service/Worker 不得直接拼装 SQL 或操作 session；新表不得有
foreign key，状态/类型使用 string/json/timestamp，并为每个字段写候选 SQL
类型和中文 `comment`。租户条件必须出现在所有 Run/Checkpoint/Outbox 读写及
lease/CAS 状态转换中；relay 只能在持有未过期 owner lease 时写 published、retry
或 dead_letter。Outbox 的 `(tenant_id, run_id, task_id)` 与 Checkpoint 的
`(run_id, stage_key, attempt_id)` 由模型唯一约束保护，避免同一技术尝试被重复持久化。
