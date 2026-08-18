# 长期决策日志

| 日期 | 决策 | 原因 | 证据 |
|---|---|---|---|
| 2026-08-18 | 使用多文档 Agent Handoff（代理交接）机制 | 当前状态、决策、风险、验证和待办生命周期不同，单文件会持续膨胀 | 用户要求新会话重构；`agent-handoff` 技能合同 |
| 2026-08-18 | 表数量不设上限，10+4 仅为当前候选基线 | 用户明确允许必要时新增表；架构按独立事实而非数字设计 | 用户确认；设计母文第 13 节 |
| 2026-08-18 | 内部代码允许完全重构 | 旧 XRay 专项目录、类和实现不是兼容目标 | 用户明确确认；设计母文第 12.1 节 |
| 2026-08-18 | `docs/history/` 只保存历史证据，不作为实施合同 | 历史混合 6/8/10/12 表、旧 XRay 专表和失效链路 | `docs/history/README.md` |
| 2026-08-18 | 设计母文继续拥有精确字段权威，`docs/refactor/` 只提供实施视图 | 避免复制两套字段字典并发生漂移 | `docs/refactor/README.md` |
| 2026-08-18 | 采用保留入口的内部模块化重构 | 复用 FastAPI、DalBase、OSS、Provider、Outbox 和 Worker 骨架，避免第二运行时 | 设计母文第 12.1 节 |
| 2026-08-18 | 在线 10 表和评测 4 表作为候选基线 | 当前每类事实有独立 owner，仍允许真实证据触发合并/拆分 | 数据库设计和字段最小化审查 |
| 2026-08-18 | 不建设公共 `file_asset`（文件资产）表 | 对象 owner、保留和删除由领域表闭环 | `docs/refactor/03-database-and-storage-design.md` |
| 2026-08-18 | 默认 XRay 使用 Primary-only（仅主读）链 | 固定 FinalReader 已观察退化；复杂候选必须先做 paired A/B | 设计母文第 0.3、1.1、8.6 节 |
| 2026-08-18 | 冻结双 Profile Canonical XRay Chain（X 光权威主链） | 用户确认 Primary Profile 直接定稿，只有 Targeted 实验 Profile 才执行 FamilyRouting 并可触发最多一次 TargetedReview | 用户确认的 Mermaid；`docs/refactor/10-xray-detailed-flow.md` 第 2 节 |
| 2026-08-18 | 根文档以 MS-Image 为唯一项目身份 | 原 README/USAGE/CLAUDE 仍是脚手架说明，会让新开发误解项目目的 | 根 `README.md`、`USAGE.md`、`CLAUDE.md` |
| 2026-08-18 | Canonical Chain 节点按事实/事务/转换/失败/可验证价值决定是否独立 | 防止一表一 Service、无意义 Stage 和“调用越多越准确”的复杂度膨胀 | `docs/refactor/12-canonical-xray-layer-responsibility-contract.md` 第 1、18、19 节 |
| 2026-08-18 | 人工复核首期不实现 | 尚无 owner、领取、SLA、资格和裁决合同 | 用户明确先不考虑；设计母文 |
| 2026-08-18 | 权威按七条轴分别判定，不再使用单一线性排名 | 防止旧 schema 覆盖目标、设计冒充实现、工程检查冒充医学准确率 | `docs/README.md`；设计母文第 0 节 |
| 2026-08-18 | P1 包含 Image 专属最小 validate Outbox/Relay/Worker，P2 复用并扩展 | Image ready 依赖事务后大对象校验和故障恢复，不能同步塞入 API 或推迟到 Task 阶段 | 设计母文 Phase 1/2；`docs/refactor/06-refactor-migration-and-validation-plan.md` |
| 2026-08-18 | 去掉目标表 `tenant_id` 不等于取消认证 | 分区字段与访问控制职责不同；旧 API/OSS 仍使用 tenant 派生语义 | `app/api/deps.py:136-204`；`app/core/imaging/object_store.py:47-82`；设计母文第 5.0.1 节 |
| 2026-08-18 | 重构以当前工作树为资产基线，采用保留入口的内部模块化替换 | 当前 `HEAD` 就是 `9a45209a` 且之后提交数为 0；reset 只会丢弃未提交资产，局部修补又会延续 XRay 专项事实污染 | `docs/refactor/13-refactor-base-decision.md`；当前 Git 和源码点验 |
| 2026-08-18 | 使用 `codex/ms-image-refactor` 并按业务 owner 垂直切片提交，每次提交后立即推送 | 用户要求每完成一部分代码即提交并推送；远端确认是进入下一切片的门禁 | 用户确认的实施计划；`.agent-handoff/backlog.md` |
| 2026-08-18 | 通用 Outbox 只拥有 Broker 发布状态，Image 校验 lease 归 `image_record` | 避免 relay 和业务消费者形成双 lease owner；Image ready 必须由有效业务 lease 的 Worker CAS 回写 | 设计母文第 4.8、4.9、6.7 节；INV-55 至 INV-57 |
| 2026-08-18 | 目标 `OutboxRelay` 与旧 tenant XRay Relay 暂时同模块并行，复用同一 Celery 工厂 | 目标 Outbox 没有 tenant/consumer lease 字段，强行套旧接口会污染合同；保留旧类可避免在 P1 提前破坏兼容 API | `app/core/messaging/outbox_relay.py`；设计母文第 4.8、6.7 节 |
| 2026-08-18 | 新存储 API 使用显式事务 session，旧 API 保持请求级事务依赖 | direct/multipart/HEAD 等 OSS I/O 不能跨数据库事务；全局修改旧依赖会改变现有接口提交语义 | `app/core/async_db.py:get_explicit_transaction_session`；设计母文第 4.9 节 |
| 2026-08-18 | Series/Study manifest 只由 canonical helper 和 StudyService 重算 | 防止 Worker、ImageService 和未来 TaskService 产生不同 hash；StudyService 继续拥有 Series/revision，重复 ready logical key 直接 conflict | `app/core/imaging/manifest.py`；`app/service/study_service.py:recompute_after_image_change`；INV-66 |
| 2026-08-18 | Image Worker 接受 `publishing/published` 两种 Outbox 发布状态 | Broker 可能已接收消息但 Relay 的 DB confirm CAS 尚未成功；事件内容不可变且会被完整复核，拒绝 `publishing` 会破坏至少一次恢复 | `app/service/image_service.py:claim_validation_event`；Relay Broker-accepted/DB-conflict 合同 |
| 2026-08-18 | Image ready 与 Series/Study revision 使用同一终态事务 | 禁止 Image 已 ready 但 manifest/revision 仍旧；Study CAS 冲突回滚 Image ready，再释放原 lease 安排重试 | `ImageService.complete_validation`；设计母文第 4.9、8.2 节；INV-55、INV-66 |
| 2026-08-18 | ready 对象漂移首期按显式 Image ID 有界核查 | 当前表没有 durable scan cursor/next-check 字段；伪造全局前 N 条扫描会永久重复同一批对象。显式核查仍执行完整 Gateway 校验和原子 Study 失效，周期 inventory 留待有运行合同后实现 | `workers/imaging_worker/reconcile.py:verify_ready_image`；未授权迁移边界 |
| 2026-08-18 | OSS HEAD 将 NoSuchKey/NotFound 归一为 `object_not_found` | 过期 upload reconcile 必须区分确定性对象缺失和可重试 HEAD/网络失败，且不能把 SDK 错误详情写入业务状态 | `app/core/imaging/object_store.py:head_object` |
| 2026-08-18 | direct prepare 只对 `uploading` 同载荷重发 grant，`validating` 不重签 | complete 后重签 PUT 会允许客户端覆盖 Worker 正在校验的对象版本；相同 uploading 行可安全刷新 expiry，ready 必须走 replace | `ImageService.prepare_direct_upload` |
| 2026-08-18 | 首期公开上传只资格化 DICOM/JPEG/PNG 且单对象不超过 64 MiB | 当前 Gateway 完整校验会在流式 hash 同时保留有界 bytes 供格式解析，尚无大型 CT/MRI/视频/WSI parser；传输协议实现不能冒充运行资格 | `ImagePrepareUploadRequest`；`MAX_IMAGE_BYTES`；当前范围合同 |

## 记录规则

- 只记录跨会话仍有效的取舍，不记录聊天摘要。
- 每项决策包含理由和可定位证据。
- 证据不足的内容写入 `risks.md` 的 `UNKNOWN`（未知），不伪装成决策。
