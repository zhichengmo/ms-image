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
| 2026-08-19 | `vet-platform` 只作为旧系统/迁移来源，不能作为目标线上游或发布 owner | 用户明确该系统正在迁移到 `ms-image`；继续保留在线鉴权、灰度、回切或查询依赖会导致目标架构无法独立闭环 | 用户澄清；`docs/ms-image-final-architecture-and-database-design.md` §3.5 |
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
| 2026-08-19 | Clinical Family 首期采用五个临床评估包 | 五家族以完整 Study、输入覆盖、报告子域和评测分母为边界；物种、区域、Focus、Strategy 和技术证据保持正交，避免默认多调用和重复表 | `docs/refactor/14-xray-specialty-design.md` §2-4；设计母文 §6.12 |
| 2026-08-19 | Prompt 采用六种目标角色，默认链只运行一次 JointPrimaryReader | Prompt 模块负责组织检查项和复核策略，不产生多个竞争 Final；Targeted 只有唯一 Family/Focus 且通过门禁时才允许一次调用 | `docs/refactor/14-xray-specialty-design.md` §5-13；设计母文 `prompt_bundle_json` 与 §6.12 |

| 2026-08-19 | Evaluation Job 幂等键与完整请求摘要分离 | `requester_id + request_id` 定义幂等作用域，完整规范化 payload SHA 用于检测 fingerprint、split、分母和 Artifact 漂移；把 payload 放进业务键会把冲突误当新 Job | `app/service/evaluation_service.py`；提交 `4ac3fff` |
| 2026-08-19 | Evaluation Outbox 复用通用 `OutboxRelay` 协议但保持独立表/拓扑 | 发布可靠性语义应一致，Evaluation 的队列、权限和运行资源必须与在线医学队列隔离 | `app/crud/evaluation.py`；提交 `a2aa0f9` |

| 2026-08-20 | 当前主线优先完善 Monorepo Foundation，不先推进 Phase 2、AI Control 或 Evaluation Control | 用户明确 Monorepo 架构改动优先；MR-1 已完成，下一步应先收口 Runtime 入口、部署边界、路径与无 Secret 运行验证；控制面和 Evaluation 拆分必须等待各自 ownership/跨服务合同 | 用户当前确认；`docs/refactor/20-monorepo-refactor-new-session-prompt.md` §4.3、§9、§12 |

| 2026-08-19 | Evaluation Job 唯一拥有 Worker lease，Run 只记录执行事实，Outbox 只拥有发布事实 | 避免三张表重复表达同一运行状态；重复消息和迟到写回由 Job state_version + lease generation 拦截 | `app/crud/evaluation.py`；`app/service/evaluation_execution_service.py`；提交 `8a994f7` |
| 2026-08-19 | fake scorer 不作医学判断，所有 row 保留并分别计算医学条件分母和 population 分母 | 工程失败不能变成医学结论或从总体分母消失，review/non_diagnostic 需要显式计入覆盖损失 | `app/service/evaluation_fake_scorer.py`；提交 `8a994f7` |
| 2026-08-19 | paired A/B 不可配对病例必须输出 `invalid_comparison` | 防止 schedule/Provider/manifest/Gold/scorer/非实验变量漂移被静默丢弃并制造虚假收益 | `app/service/evaluation_paired_ab.py`；提交 `8a994f7` |

| 2026-08-19 | Evaluation 使用独立 engine/session，并在数据库名相同时失败关闭 | 只隔离队列而共用在线 DB 仍会泄漏 Gold/Holdout、权限和资源；空连接覆盖可继承主 MySQL transport，但数据库名必须独立 | `app/core/async_db.py`；提交 `0951b23` |
| 2026-08-19 | 在线事实导出使用 online DB 短事务、OSS 事务外、Evaluation DB 短事务三段边界 | 跨数据库无法形成单事务；稳定对象 key、hash 和 Job 幂等可恢复空窗，同时避免在 DB 事务内执行 OSS I/O | `app/service/evaluation_export_service.py`；提交 `a1ac869` |
| 2026-08-19 | Exporter 只产生白名单 case row，不复制 Report 正文、原始请求或 Provider 连接详情 | Evaluation 需要可评分 lineage，不应把在线医学正文、PII、base URL、signed URL 或 Secret 扩散到 Artifact | `app/schemas/evaluation_export.py`；`JsonArtifactStore`；提交 `a1ac869` |

| 2026-08-19 | Caller 诊断 Task 由服务端映射到 `xray_diagnose` Active Config，不允许 Caller 自选 Config | ControlPlane 拥有发布选择；Task 只提交 task_type，Service 冻结唯一 Active Config/Profile | `app/service/task_service.py`；提交 `fc5f52d` |
| 2026-08-19 | provider-disabled 全链通过只升级工程组合状态，不升级 runtime 或医学状态 | inline fake 能证明状态、事务和幂等合同，不能证明真实基础设施或准确率 | 15 号文档 Phase 1；提交 `249c3bb` |
| 2026-08-19 | 工程 readiness 与医学 Provider readiness 正交 | Provider 未资格化不应使 provider-disabled 工程链被误判为不可运行；医学交付仍要求 provider gate | `app/core/readiness.py`；提交 `1a0646d` |

| 2026-08-19 | Operational Status 只返回聚合运行事实，不返回资源 ID/内容/ObjectRef | 运行面需要告警数据，但 Admin 观测端不应成为在线医学或 Artifact 内容读取旁路 | `app/service/operational_status_service.py`；提交 `d4082ad` |
| 2026-08-19 | RabbitMQ readiness 暴露 queue/DLQ depth 与 consumer count，oldest age 明确 unsupported | AMQP queue.declare 不提供可靠消息时间戳；返回虚假 0 会误导告警 | `app/core/readiness.py`；提交 `c8e9ad2` |
| 2026-08-19 | Evaluation read/write scope 分离，write scope 可读但不能替代 admin 权限 | 评测读取、评测变更、运营读取、AI Config 发布是不同职责；避免 Evaluation identity 获得发布权 | `app/api/admin_v1/endpoints/evaluation.py`；提交 `836e72e` |

| 2026-08-20 | QJ 仅作为 MS-Image 外部商业控制面与工程编排参考；不合并仓库、数据库或业务主数据 | QJ 的 Project/API Key/Kong/Usage/Wallet 与 MS-Image 的影像/Task/Report/Evaluation 是不同事实 owner；合并会制造双事实源 | `docs/refactor/16-qj-reference-and-modular-convergence-plan.md` §1、§3、§4；待实现授权 |
| 2026-08-20 | 新 XRay 能力的目标事实只写公共在线十表；`xray_accuracy` 冻结为 compatibility/legacy 域 | 当前存在两套 Session/Stage/Outbox/Call/Worker；目标 8 Service/5 Stage 要求 XRay 通过 Profile/Stage/Schema 扩展，不能继续新增第二套持久化执行面 | `docs/refactor/16-qj-reference-and-modular-convergence-plan.md` §5-§8；旧消费者 UNKNOWN，未授权实施 |
| 2026-08-21 | Stage 具体实现拆到 `stages/common|xray`，但状态机继续唯一归 `ImagingExecutionService` | 需要降低执行服务的专项逻辑密度，同时不得复制 claim/lease/CAS、Outbox、Report 或 Worker owner；handler 只返回 `StageResult`，registry 依据持久化 handler key/version 精确解析 | `apps/backend/services/runtime/service/imaging_execution_service.py`；`apps/backend/services/runtime/stages/contracts.py`；`registry.py` |
| 2026-08-21 | Image 上传三段事务与 OSS 编排由 `ImageService` 内部 workflow 管理 | API 层不应执行 DB 事务、OSS 调用或 multipart 回收；维持一个 ImageService/DalBase 调用链，外部 I/O 保持在 DB 短事务外，并在 multipart session 绑定或 grant identity 失败时补偿 abort | `apps/backend/services/runtime/service/image_upload_workflow.py`；`image_service.py`；`api/api_v1/endpoints/images.py` |

| 2026-08-20 | Prompt 运行时唯一版本中心是 AI Config Release，六种 role 只作为编译片段 | 防止 Prompt 文件版本、Schema 版本、Config 版本和硬编码 SHA 形成多事实源；默认 Primary 一次、Targeted 最多一次，Primary/Targeted 共享完整结果 Schema | `docs/refactor/17-prompt-runtime-contract-and-minimal-provider-plan.md`；提交 `9fdd1c6` |

| 2026-08-20 | 首期运行 Prompt 固定 zh-CN；Config Release 是唯一运行版本中心 | 防止中英文 fallback、硬编码 SHA、旧 Registry、文件路径和 Config version 形成多事实源；Primary 一次、Targeted 最多一次，Primary/Targeted 共享完整结果 Schema | `docs/refactor/17-prompt-runtime-contract-and-minimal-provider-plan.md`；提交 `6359163/9b52214/946447e/984b028` |

| 2026-08-20 | 按用户明确授权从代码库移除 legacy XRay/AI runtime 链，目标 metadata 只保留 10 在线核心 + cursor + 4 Evaluation 表 | legacy 表/模型/API/Worker 已干扰目标分析且形成第二事实源；真实 MySQL 物理表未 drop，等待单独 DDL/archive 授权 | 提交 `1db2261`；target metadata/API/Compose/legacy 引用静态验证 |

| 2026-08-20 | Web 可编辑 Prompt、频繁模型切换和模型竞速采用 AI Control Plane / Runtime 双边界 | 控制面拥有 Connection/Model/Prompt/Schema/Release，Runtime 只拥有冻结 AIConfig projection、Logical Call、Physical Attempt 和技术 Winner；避免恢复旧 AI 多表串联和双 Task/Report 事实源 | `docs/refactor/19-ai-prompt-control-plane-web-and-runtime-architecture.md`；提交 `1c37875`；尚未实施 |

| 2026-08-20 | Monorepo 采用渐进式收敛：先将唯一 Runtime 源迁移到 `services/runtime`，AI Control 和 Evaluation 不创建空壳服务 | 当前 Runtime/Worker/Evaluation 的代码与运行合同仍耦合；硬搬三服务会复制事实、破坏 import/Compose 并制造假边界。跨服务仅通过版本化合同/Outbox，首个候选共享包只能是无状态 `ai_contracts` | `docs/refactor/20-monorepo-refactor-new-session-prompt.md`；需 MR-0 审计和用户 MR-1 授权 |

| 2026-08-21 | Runtime 服务根采用 `apps/runtime/` 扁平布局，不保留冗余 `backend/` | 用户提供的 QJ 后端目录图中 `backend` 是后端项目根；映射到 Monorepo 后 `apps/runtime` 承担同一职责，`api/admin_api/core/crud/models/schemas/service/stages/workers` 与入口同级。避免 `apps/runtime/backend` 双层目录和额外 import namespace；`service` 仍遵守项目规则使用单数 | 用户提供的 QJ 目录截图；`apps/runtime/` 当前文件树；`AGENTS.md` 分层合同 |

| 2026-08-21 | Runtime 正式迁移到 `apps/runtime`，内部 `app` 包暂时保留 | 用户确认 Monorepo 服务边界为 `apps/runtime`、`apps/ai_control`、`apps/evaluation_control`；只移动物理源码目录，暂不重写全部 `from app...` 导入，降低行为差异和回滚成本 | `apps/runtime/` 唯一源码、`apps/runtime/Dockerfile`、`docker-compose.yml`、`.github/workflows/runtime-foundation.yml` |
| 2026-08-21 | `apps/ai_control` 与 `apps/evaluation_control` 本轮只冻结边界，不创建空服务 | 当前没有独立 ownership、SLA、数据库/事件合同和真实消费者；空壳会制造假服务边界并复制运行时事实 | 用户目标结构、`docs/refactor/20-monorepo-refactor-new-session-prompt.md` §4.3/§5.2 |

| 2026-08-20 | MR-0 审计后保持停止，不自动执行 MR-1 | 当前 Compose 无 Worker 服务；`app` 包同时承载在线、AI Config、Evaluation 和双 DB；Evaluation Export/Operational Status 存在明确跨边界读聚合；且 `app/models/evaluation.py` 有用户未提交改动。任何移动或启动调整都必须等待用户确认并处理 dirty 文件 | 当前源码 `main.py`、`docker-compose.yml`、`app/core/async_db.py`、`app/service/evaluation_export_service.py`、`app/service/operational_status_service.py`、`git status` |
| 2026-08-20 | 采用方案 1 完成 MR-1 Runtime 单一源码迁移 | 用户明确确认方案 1 并授权 `evaluation.py` dirty 格式化改动随迁移；保留内部 `app` 包名能避免业务 import 重写，同时不创建空控制面或复制 ORM/DAL/Session/Service | 用户授权；`services/runtime/`、`docker-compose.yml`、`alembic_migrations/env.py`、静态验证 |
| 2026-08-20 | Phase 2A 告警只作为 Operations status 的 additive 非敏感投影 | 阈值判定需要复用现有在线/Evaluation 聚合，但不应新增告警表、事件写入或第二个监控服务；查询时生成可回放的稳定 code，保持 DB/医学事实不变 | `services/runtime/app/service/operational_status_service.py`、`services/runtime/app/schemas/operations.py`、`docs/runbooks/runtime-operational-alerts.md` |
| 2026-08-20 | AI/Prompt 最终数据库收敛为 Prompt、Connection、可复用 Model Pool、唯一 AI Config 快照、Logical Call、Physical Attempt 六类核心表，加一张只追加 Control Audit 表 | 沿用旧链路的业务关系，但移除 `gpt_config_item`、旧 `ai_config.items` 横杠 ID 串和 `ai_config_pool_override`；Prompt 采用单表多版本正文，Runtime 只读 `ai_config_record` 冻结快照；Model Pool 保留用于旧链复用和 Primary 双 lane，Config 激活时复制 lane 快照；Web 编辑/激活/回滚需要独立审计事实 | 旧链源码 `vet-platform` 的 `ai_config/config_item/prompt/pool/connection` 解析；当前 `app/models/ai_config_record.py`、`app/service/task_service.py`；本次只读设计，未实施 |
| 2026-08-20 | Prompt 链按“目录资产 -> AI Config Release -> Task 快照 -> Prompt Command -> Compiled Prompt -> AI Call -> Report/Evaluation”分成配置发布链和病例运行链 | Prompt Catalog、配置发布版、实际渲染内容和调用记录承担不同事实；混成一条或让 Worker 读取 latest Prompt 会破坏重放、A/B 和审计。Primary 一次、Targeted 最多一次，六种 role 仍只是编译片段 | `docs/refactor/14-xray-specialty-design.md` §19.1-19.6；`docs/refactor/17-prompt-runtime-contract-and-minimal-provider-plan.md` |
| 2026-08-21 | Outbox Relay 对具体持久化实现只依赖服务端口，Worker 不导入或构造 Outbox DAL | Worker 保留 Broker 投递与进程生命周期；Runtime/Evaluation Service 作为唯一 DAL owner，复用现有 Outbox DAL 和 Shared Relay 的 lease、confirm、retry、DLQ、reconcile 语义，不创建 Repository 或第二套 CRUD | 提交 `492a249`；`apps/backend/core/messaging/outbox_relay.py`、两个 `*_outbox_relay_service.py`、两个 Worker relay 入口 |

| 2026-08-20 | MR-1F 第一轮只读审计暂不改变 root Compose、Alembic、Prompt 资产边界；Runtime 继续以 `services/runtime` 为唯一源码，先冻结启动/调度/生命周期合同再实施 | 当前 root 资产仍被 Docker、Alembic 和 Prompt 解析直接使用；`evaluation/replay` 有失效 legacy import，Imaging Reconcile 无内部调度，Worker/Relay 无独立 healthcheck；贸然移动或恢复旧链会扩大范围 | `services/runtime/Dockerfile:12-30`、`alembic_migrations/env.py:11-25`、`services/runtime/workers/imaging_worker/reconcile.py:292-313`、`evaluation/replay/__init__.py:3-9`、`docker-compose.yml:1-155` |
| 2026-08-21 | MS-HD 外部数据库集成默认关闭并延迟初始化 | MS-HD 不是当前 Runtime 在线或 Evaluation 事实；import 时创建第三套 engine/session pool 会扩大资源与配置耦合。只有显式 `MYSQL_HD_ENABLED=true` 且调用 HD session 入口时才初始化；默认失败关闭 | `services/runtime/app/core/config.py:95-101`、`services/runtime/app/core/async_db.py:61-103`；默认关闭与 opt-in lifecycle 验证 |
| 2026-08-21 | Relay/双 API graceful shutdown 属于 Runtime Foundation，Worker/Relay 不因目录迁移创建新服务 | 停止信号、子进程失败传播和 Compose grace period 是部署生命周期合同，不改变业务事实；继续复用现有 Outbox/Celery/Service 边界 | 提交 `c59d90f`；`services/runtime/app/core/messaging/lifecycle.py`、`services/runtime/run_servers.py`、`docker-compose.yml` |
| 2026-08-21 | Runtime 继续保留内部 `app` 包名，但由入口 bootstrap 固化 root-qualified import | 机械迁移后同时改写全部绝对 import 会扩大业务差异；在 `main.py` 和 Worker package 入口注入唯一 `services/runtime` 路径，可支持仓库根模块启动而不复制源码 | `services/runtime/main.py`、`services/runtime/workers/__init__.py`；root-qualified 与容器式 import 验证 |
| 2026-08-21 | Worker/Relay Compose 依赖按事实 owner 隔离 | Imaging 只需在线数据库，Evaluation 只需隔离评测数据库；Redis 不是 Worker/Relay 当前运行依赖。移除跨域 `depends_on` 可避免不相关基础设施故障阻塞进程启动 | `docker-compose.yml`；Worker/Relay 源码 import 与 Compose config/YAML assertion |

| 2026-08-21 | Worker readiness 与 Relay liveness 使用进程本地合同 | Celery Worker 用目标节点 `inspect ping` 反映 broker 可达且 consumer 响应；长驻 Relay 用每轮 reconcile/relay 后更新的可配置 heartbeat 文件反映循环仍在推进。两者不新增表、指标服务或真实 broker 依赖，不能升级为真实运行资格 | `docker-compose.yml`；`services/runtime/app/core/messaging/lifecycle.py`；`services/runtime/app/core/messaging/outbox_relay.py`；Imaging/Evaluation Relay 入口；静态/fake 验证 |

| 2026-08-21 | Monorepo 边界用仓库级静态 CI 固化，不新增运行时共享包 | 当前唯一 Runtime 源迁移完成，但没有 CI 防止根 `app`/`workers`/`main.py` 回归；最小可逆方案是在 CI 检查路径、Ruff、compileall 与 Compose config，不触碰数据库、Broker、Provider 或业务结果 | `.github/workflows/runtime-foundation.yml`；本地等价命令通过；Reconcile 入口保持一次性 |

| 2026-08-21 | Foundation CI 同时检查活动旧路径引用并构建 Runtime 镜像 | 目录边界检查只能发现旧目录回归，不能发现 Compose/Alembic/源码重新写入旧 Runtime 路径；镜像构建是 `apps/runtime/Dockerfile` 与仓库根 build context 的最终结构门禁。CI 不连接真实运行依赖，本地 Docker daemon 未启动时保持未验证 | `.github/workflows/runtime-foundation.yml`；本地旧路径扫描、Ruff、compileall、Compose config 通过；Docker build 被 daemon 阻断 |

| 2026-08-21 | 后端 Monorepo 采用 `apps/backend` 共享工作区和 `apps/backend/services/*` 服务布局 | 用户最新提供的 QJ 目录截图明确将 `core`、`crud`、`models`、`schemas` 置于 backend 根，并将独立 API 放入 `services/`；此前三个顶层 `apps/{runtime,ai_control,evaluation_control}` 不符合该布局。保留 `apps/` 作为 Monorepo 产品层，不引入第二个仓库根或重复数据访问层 | 用户截图；`apps/backend/` 当前目录；`AGENTS.md` 的 DalBase/Service 分层合同 |
| 2026-08-21 | Imaging 与 Evaluation Worker 统一置于 `apps/backend/workers/` | 截图将异步进程作为后端根层的独立部署单元；Worker 入口与 API 服务分离能避免把进程拓扑误当成 HTTP 服务内部模块。Worker 继续调用既有 Service/DAL，不改变消息、数据库或业务 owner | 用户截图；`apps/backend/workers/{imaging_worker,evaluation_worker}`；`docker-compose.yml` |
| 2026-08-21 | 共享的 `AIConfigRecord` 和 Evaluation ORM/DAL/Schema 暂留 `apps/backend` 根层 | 当前属于共享后端 Monorepo，而非数据库自治微服务；`AIConfigRecord` 被 Runtime Task/AI Request/Evaluation Export 消费，Evaluation 数据仍有 Operations 读聚合。过早复制/搬迁会制造双事实或平行 DAL；真实 source-of-truth 和事件合同须另行授权 | `apps/backend/models/ai_config_record.py`；`apps/backend/models/evaluation.py`；`apps/backend/services/*`；用户未授权迁移约束 |
| 2026-08-21 | Worker 默认采用单并发、单预取与可覆盖 hard limit 的 warm-shutdown 窗口 | 任务采用 late ack、worker-lost reject 和 lease；默认 CPU 并发会使单实例持有多条未完成消息，30 秒容器强杀窗口又短于默认 120 秒任务上限。固定每进程一条活跃/预取消息并优先按副本扩展，能保持升级时的可观察在途工作边界 | `apps/backend/core/messaging/{config,celery}.py`；`apps/backend/core/config.py`；`docker-compose.yml`；提交 `a0d903b`；本地及隔离容器验证 |

| 2026-08-21 | AI/Prompt 控制面采用单正文 Prompt、Connection、Model Pool、唯一不可变 AI Config、Control Audit、Logical Call 和 Physical Attempt 七表边界 | 当前需求只要求完整 Prompt 正文和可复现运行；role/revision/schema/release/model/lane/outbox/独立数据库没有已证明的独立生命周期。`gpt_config` 杂项配置桶应删除，但 Task 必须通过唯一 `ai_config_record` 冻结 Prompt、模型、连接、Schema、Pipeline、预算和哈希 | `docs/refactor/19-ai-prompt-control-plane-web-and-runtime-architecture.md`；用户关于单正文 Prompt、删除 `gpt_config` 和沿用既有链路的确认 |

| 2026-08-21 | Active Config 槽使用规范化作用域 SHA256，不使用可变长拼接键 | `config_key/modality_type/task_type/activation_scope/scope_key` 的直接字符串拼接存在长度和歧义风险；固定 `CHAR(64)` 可由服务端稳定派生，并利用 MySQL 多个 NULL 的唯一约束只限制 active 行 | `docs/refactor/19-ai-prompt-control-plane-web-and-runtime-architecture.md` §11.2-11.4 |
| 2026-08-21 | 控制面 Audit 的 `request_id/resource_type/action_type` 是命令幂等键 | 写命令重试不能重复修改业务状态；业务行与 succeeded Audit 同事务提交，并发冲突后回读首次结果 | `docs/refactor/19-ai-prompt-control-plane-web-and-runtime-architecture.md` §12.3、§18.1 |
| 2026-08-21 | `late/ignored` 只属于 Physical Attempt；Logical Call Winner 由 CAS 唯一建立 | Call 表示逻辑业务结果，Attempt 表示物理 Provider 事实；Winner 事务同时写 Attempt accepted 与 Call accepted，迟到响应不得覆盖业务结果 | `docs/refactor/19-ai-prompt-control-plane-web-and-runtime-architecture.md` §14.5-14.6 |
| 2026-08-21 | Task 级 AI 预算通过 Task/Call CAS 和 Call reservation 实现，不新增预算表 | 当前预算事实可由冻结 policy、Call 最坏情况预留、Attempt count 和实体 DAL 闭环；额外预算表/Repository 会制造双 owner 和并发歧义 | `docs/refactor/19-ai-prompt-control-plane-web-and-runtime-architecture.md` §11.5、§13.4、§17.5 |

| 2026-08-21 | 本地开发统一使用 Conda `ms-image` 的 Python 3.11 | `apps/backend/Dockerfile` 以 Python 3.11 为基线；固定本地环境为 Python 3.11.15 可避免当前系统 Python 3.13 与部署镜像不一致。依赖仍以仓库唯一的 `apps/backend/requirements.txt` 为准 | `apps/backend/Dockerfile`；`apps/backend/requirements.txt`；本轮本地启动验证 |

| 2026-08-21 | 本地 Conda `ms-image` 按用户指示使用 Python 3.13 | 用户明确要求将本地环境切换为 Python 3.13；Python 3.13.15 已完成依赖、入口、Redis 和 Runtime HTTP 验证。该决定仅覆盖本地 Conda 环境，`apps/backend/Dockerfile` 继续使用 Python 3.11，容器版本对齐需单独授权与验证 | 用户本轮请求；`apps/backend/requirements.txt`；本轮本地验证 |

## 记录规则

- 只记录跨会话仍有效的取舍，不记录聊天摘要。
- 每项决策包含理由和可定位证据。
- 证据不足的内容写入 `risks.md` 的 `UNKNOWN`（未知），不伪装成决策。

## 2026-08-23 — AI Prompt 控制面 Phase A-C 结构实现

- 依据 `docs/refactor/19-ai-prompt-control-plane-web-and-runtime-architecture.md`，在共享 `apps/backend` 中实现 Prompt、Connection、single-lane Pool、Control Audit、不可变 `ai-config.v2`、Task v2 snapshot 和 provider-disabled Runtime；保持 `API -> Service -> DalBase CRUD -> Model/DB`。
- Prompt 保留一个同表版本行的一段 `content`，首期语言唯一接受 `zh-CN`；没有 role/family/focus/strategy 分片或正文拼装。
- 新增纯本地 Connection 合同，将 Base URL 规范化并将 Connection metadata SHA 复用于 Service/Compiler；不解析 `secret_ref`、不联网。
- Config SHA 包含 Prompt/Pool 来源身份与冻结快照，release fingerprint 保持行为输入摘要；Runtime 只验证 Task 冻结 Config 和代码拥有的 Pipeline/Schema/Registry，不读取可变来源表。
- Task deadline 固定为 Task 创建时间加冻结预算窗口，禁止每次 Runtime replay 延展 deadline；终态 Logical Call 仍按 logical key 幂等回读。
- 真实 Provider、Physical Attempt、reconcile、race、migration、测试与 Web 均不属于本次授权。


## 2026-08-24 — AI Prompt 控制面实施与验证决策

| 决策 | 理由 | 证据 |
|---|---|---|
| Phase A-C 交付包含一条增量 Alembic revision 与既有 pytest/CI 接入，但不连接真实基础设施 | 用户已将实施范围从纯结构代码扩展到 migration、测试体系和 CI；Provider/Secret/网络仍明确后置，因而只生成并离线验证 SQL，不运行真实 MySQL 或 Provider | `alembic_migrations/versions/20260824_01_ai_prompt_control_plane_phase_a_c.py`；`.github/workflows/runtime-foundation.yml`；`apps/backend/tests/test_ai_prompt_control_plane_*.py` |
| `20260824_01` 必须被视为已有应用 schema 上的 baseline 后增量，而非 bootstrap | 该项目在 revision 之前已有物理表且没有可串联的历史 Alembic revision；直接对空库 upgrade 会在对既有表的 ALTER 处失败。使用 owner 确认的 stamp/baseline 流程后才能演练 | migration docstring、`down_revision = None`、`.agent-handoff/risks.md` |
| PromptRenderer 规范 JSON 必须拒绝 NaN/Infinity | Python 默认 JSON 序列化可产生非标准 `NaN`，会破坏 freeze/render context SHA 的确定性与 fail-closed 合同；`allow_nan=False` 将其转化为 `prompt_context_not_canonical_json` | `apps/backend/core/ai/prompting/contracts.py`；`apps/backend/tests/test_ai_prompt_control_plane_contracts.py` |
| provider-disabled v2 Runtime 不创建 Physical Attempt | A-C 的唯一可证明事实是 Logical Call 的配置冻结、渲染、预算预留与 `failed(provider_disabled)`；Attempt 会伪造未发生的 Provider I/O，并超出 Phase D 的资格/回写边界 | `apps/backend/services/runtime/service/ai_request_service.py`；migration；19 号设计 Phase C |

| 2026-08-24 | AI 控制面 timestamp server default 使用 `CURRENT_TIMESTAMP(6)`，连接建立时固定 MySQL session 为 UTC | MySQL 9.3.0 实测拒绝 `DATETIME DEFAULT UTC_TIMESTAMP(6)`；只改为 `CURRENT_TIMESTAMP(6)` 会受会话时区影响。以驱动 `init_command` 在应用和 Alembic 连接建立前设 `time_zone='+00:00'`，既可执行 DDL，又保持 UTC 持久化合同，不在 Alembic connection 上额外执行 SQL 以免破坏 MySQL 非事务 DDL 下的 revision marker 提交。 | `apps/backend/core/async_db.py`；`apps/backend/models/imaging_base.py`；`apps/backend/models/ai_control_audit_record.py`；`alembic_migrations/env.py`；`20260824_01` 隔离 MySQL 9.3.0 演练 |
| 2026-08-24 | Alembic 在线连接必须用 `URL.render_as_string(hide_password=False)`，但不得输出 URL | SQLAlchemy 的 `str(URL)` 默认隐藏密码为 `***`，Alembic 会把它当真实认证信息。只将未隐藏 URL 写入进程内 Alembic 配置，既支持密码特殊字符，又不写入仓库、migration、日志或 handoff。 | `alembic_migrations/env.py`；隔离 MySQL 在线 stamp/upgrade/downgrade 演练 |
| 2026-08-24 | Provider 发送必须同时满足冻结 `ai-gateway-profile.v1`（`provider_enabled=true` 且 `qualified`）与运行时门禁 `AI_GATEWAY_ENABLED` + `AI_GATEWAY_ALLOWED_ENVS` | 双门禁保证生产默认 disabled；在 Secret Manager、网络白名单、医学质量与运维门禁完成前不发送真实网络 | `ai_request_service._runtime_gate_allows()`；`core/config.py` |
| 2026-08-24 | Attempt 三段生命周期：事务 A 内 prepare（Logical Call + prepared Attempt）→ 事务 B 外网络 → 事务 C 内 finalize/Winner CAS；同 Attempt 重放复用同一 `provider_idempotency_key`，真重试必须新建 Attempt 与新幂等键 | 防止 Provider I/O 落入数据库事务；网络不确定性与状态机必须可对账（unknown 收敛，不伪造失败无限重发） | `ai_request_service.py`；`ai_call_attempt_record` |
| 2026-08-24 | v2 调用同时冻结 `rendered_messages_json`（legacy 单正文或 `prompt-message-contract.v1`），短期签名 URL 永不写入 DB/审计/普通日志 | 请求意图可复算且不泄漏短期 URL、病例正文或用户身份 | `ai_request_service.py`；`message_contract.py` |
| 2026-08-24 | Nacos Prompt 只在控制面导入/发布时读取；import 阶段解析 requested→default variant 并写入 receipt，Runtime 不读外部最新版、不执行外部模板 | 运行时只消费冻结快照；外部模板必须无损映射到安全变量，否则拒绝导入 | `prompt_source.py`；`prompt_import_service.py` |
| 2026-08-24 | Nacos 默认 namespace 固定为 `c0cc9e0e-0fed-4faf-bc57-e9bab46a78a9` | 用户明确指定 | `core/config.py` `AI_PROMPT_NACOS_NAMESPACE_ID` |

## 2026-08-24 — Prompt Runtime / AI Gateway D3 收敛决策

| 决策 | 理由 | 证据 |
|---|---|---|
| legacy 与 structured Prompt 消息合同互斥；structured developer 只承载规则，user context 只进入 user 消息 | 防止病例/用户数据被当作高优先级 developer 指令，保持消息来源和注入边界可审计 | `core/ai/prompting/message_contract.py`；`prompt_template_service.py`；`prompt_import_service.py` |
| 外部 Prompt 变量只保留可证明别名，移除 `question/content/case_text/past_history/pet_profile/patient_info` 等高歧义映射 | 宽松别名无法证明内容来源和语义等价，会污染冻结上下文或绕过变量 allowlist | `prompt_source.py`；`renderer.py`；`ai_request_service.py` |
| Stage handler 只生成执行计划；唯一网络入口由 Worker 按 prepare+commit → network → finalize+consume+commit 编排 | 与 `ms-ai-fast` 的 commit-before-dispatch 原则一致，同时避免数据库事务跨越 Provider I/O | `stages/contracts.py`；`imaging_execution_service.py`；`workers/imaging_worker/stage_execution.py` |
| 明确 Provider/Secret/Signer/Store 失败必须使 Primary Stage/Task 失败；只有历史 `provider_disabled` 保持 completed/not_produced 兼容 | 禁止把真实基础设施错误伪装成“没有生成医学结果”并继续产出报告 | `stages/xray/joint_primary_reader.py`；`ai_request_service.finalize_attempt_failure()` |
| Targeted 只接收上一 Stage 的 `complete_medical_result` 作为 `PRIMARY_RESULT_JSON` | routing/status/source metadata 不是 Primary 医学结果正文，混入 Prompt 会扩大语义和注入面 | `stages/xray/prompt_commands.py` |
| 非必要实现优先参考 `ms-ai-fast`，但不照搬 Jinja、直接 URL、环境 API Key 与 raw response 流转 | 参考仓库可提供 Attempt/幂等/事务/transport 经验，但缺少当前 D3 的冻结复现、短期 URL、加密存储和 XRay Stage 合同 | `/Users/mozhicheng/workspace/code/cy-code/ms-ai-fast/app/service/gateway_client.py`；`ai_task_service.py`；当前 `core/ai/gateway/` |

## 2026-08-25 — 完整链路辩证审查决策

| 决策 | 理由 | 证据 |
|---|---|---|
| 权威边界拆为当前事实、目标行为和医学发布三类，不再让源码拥有全部权威 | 源码可以证明当前实现，但错误或临时实现不能反向覆盖批准后的目标合同；医学发布必须由冻结评测证据决定 | `docs/refactor/22-xray-full-ai-prompt-chain-development-guide.md:26-36` 当前线性排序；本轮审查 |
| `FamilyRouting（家族路由）` 只能输出 `primary_final/targeted_review`，不得生成或覆盖四类医学状态 | 路由器不读图、不调用模型、不拥有医学结论；`review_required` 是有效医学输出，不是工程路由信号 | `docs/refactor/22-xray-full-ai-prompt-chain-development-guide.md:341-359`；`docs/refactor/14-xray-specialty-design.md:608-627` |
| 五个 Family 作为 `v1 routing vocabulary（v1 路由词汇）`，不是永久医学本体 | 当前目录缺少足够 Gold、病例分层和样本量证明最优；全身性、多区域和无法唯一归族病例应保持 Primary-only | `docs/refactor/14-xray-specialty-design.md:1020-1085,1320-1348` |
| Prompt 目标改为共享医学核心合同加 Primary/Targeted 两个冻结入口 | 初期允许共用正文以减少漂移，但两个任务输入和认知风险不同，必须允许配对实验决定是否拆成两个不可变模板 | `apps/backend/core/ai/prompting/renderer.py`；`docs/refactor/14-xray-specialty-design.md` Targeted 锚定风险 |
| 完成状态拆为核心诊断链、医学基线和逐项可选能力资格 | Retry/Fallback/Race 主要解决可靠性、成本或延迟，不应成为承认 Primary 核心链完成的共同前置；也不得因此永久排除这些能力 | `docs/refactor/22-xray-full-ai-prompt-chain-development-guide.md:690-705`；本轮审查 |
| 不新增 Targeted/Family/Fallback/Race 表或平行 Service；优先在现有 Service 内做纯模块拆分 | 当前实体已能表达事实；真正复杂点集中在 `AIRequestService` 内部职责过多，而不是缺更多边界 | `apps/backend/services/runtime/service/ai_request_service.py`；现有 Model/Service 清单 |

| 2026-08-24 | `ms-image` Nacos Prompt Source 复用 `ms-ai-fast` 已验证的 `qj-nacos` 客户端，不再维护裸 `httpx` 认证实现 | 真实测试证明旧客户端虽然接收 username/password 却不登录，已知 Prompt 返回 403；`qj-nacos` 已负责 Nacos v3 login、token refresh、server failover，并且两仓依赖版本同为 `0.2.0` | `apps/backend/services/ai_control/service/prompt_source.py`；真实 Nacos 对照烟测 |
| 2026-08-24 | 不自动把 `ms-image` 默认 Prompt namespace 改成 `ms-ai-fast` namespace | 用户指定的目标 namespace 当前为空，但 `ms-ai-fast` namespace 的通用问诊 Prompt 变量合同与 XRay 冻结安全变量合同不兼容；换 namespace 不能替代发布正确的 XRay Prompt | Nacos inventory：目标 `total=0`、参考 `total=207`；`flow.answer` import 返回 `prompt_source_placeholder_unmappable` |
| 2026-08-24 | Platform 模型别名与实际模型分开冻结并显式 allowlist | 在线回执证明 requested `gemini-3.5-flash` 实际执行为 `gpt-5-mini`；资格配置必须把实际模型列入 `allowed_actual_models`，不能关闭模型偷换校验 | `apps/backend/core/ai/gateway/openai_compatible.py`；真实 Gateway Adapter 烟测 |

| 2026-08-24 | `ms-image` Prompt Nacos 配置兼容 `ms-ai-fast` 的 `NACOS_*` / `NACOS_PROMPT_*` 环境变量，`AI_PROMPT_NACOS_*` 作为高优先级覆盖 | 真实 Nacos 客户端虽已复用，但两仓环境变量命名不同会导致正常部署仍报未配置；兼容别名复用已验证部署合同，同时不读取参考仓库文件、不复制 Secret，也不改变 Prompt 冻结语义 | `apps/backend/core/config.py`；真实 `PromptImportService._fetch_nacos()` 在线烟测 |

## 2026-08-24 — 下一阶段开发边界

| 决策 | 理由 | 证据 |
|---|---|---|
| 下一阶段采用 `Phase D5：Primary-only Runtime Foundation（仅主读运行时基础闭环）`，属于保留入口的内部模块化收口 | Prompt/Config、Task/Stage、Call/Attempt 和 Gateway Adapter 已存在；当前缺口是生产级依赖装配、unknown 对账和整链资格化，重写主链会增加回归面 | 当前工作树审计；`docs/refactor/20-monorepo-refactor-new-session-prompt.md` |
| D5 默认不新增业务表 | 当前 Config → Task → StageCheckpoint → AICall → AICallAttempt → Report 已能表达 D5 事实；Secret、签名 URL 和原始响应正文不应进入业务表 | 20 号文档第 8、9、10 章 |
| D5 保持 Targeted 关闭，不修改 Prompt 医学正文 | 当前 FamilyRouting 固定 `primary_final`，没有专项准确率证据；先稳定 Primary-only 工程闭环才能隔离评估后续专项增益 | XRay Stage 当前实现；20 号文档第 6、14、15 章 |
| unknown Attempt 必须通过 reconcile 收敛，不得按普通失败直接新请求重发 | 网络结果未知不等于失败；直接重发可能造成重复计费、重复医学结果和 winner 竞争 | `ai_call_attempt_record` 状态与候选查询；20 号文档第 11 章 |
| 19 号文档从“纯设计未实现”转为“已实现基础、D5 待资格化” | 当前源码已超过 19 号文档的阶段性描述；继续保留旧状态会让新会话重复建设控制面或错误修改 Config 运行合同 | `AIRequestService` v2 active/retired 校验；Prompt/Config/Attempt/Gateway 当前实现；19、20 号文档 |

| 2026-08-24 | D5 Worker 只使用一个不可变 `GatewayRuntimeDependencies（网关运行时依赖集合）`，默认 disabled 且配置不完整时 fail closed | 防止 Stage、Celery 和 reconcile 各自装配不同 Provider/Secret/OSS 实现，也避免未资格环境因部分配置意外开启真实网络链 | `apps/backend/core/ai/gateway/runtime_dependencies.py`；`apps/backend/workers/imaging_worker/celery_app.py`；`stage_execution.py` |
| 2026-08-24 | unknown Attempt 对账默认使用 `UnsupportedProviderAttemptLookup（不支持查询的安全实现）`，只重排、不自动重发 | Provider 原请求查询能力尚未确认；把不确定投递重发会破坏物理尝试幂等和 winner 合同 | `apps/backend/core/ai/gateway/attempt_lookup.py`；`apps/backend/services/runtime/service/ai_attempt_reconcile_service.py`；`apps/backend/workers/imaging_worker/ai_attempt_reconcile.py` |
| 2026-08-24 | 不为 D5 reconcile 新增数据库字段，暂以 `next_reconcile_at（下次对账时间）` + `state_version（状态版本）` 实现最小 CAS fencing（栅栏） | 用户明确禁止新增业务表/字段/迁移；现有结构可提供最小安全领取，但不能冒充完整 owner/count/dead-letter 租约审计 | `apps/backend/crud/ai_call_attempt.py`；共享非生产并发行为仍待验证 |
| 2026-08-24 | 保留项目现有 naive UTC（无时区 UTC）时间合同，不在单个 D5 Worker 局部切换为 timezone-aware datetime（带时区时间） | Python 3.12 已对 `datetime.utcnow()` 发出弃用警告，但仓库数据库模型和运行服务广泛使用 naive UTC；局部改变会造成比较/持久化合同不一致 | `apps/backend/workers/imaging_worker/ai_attempt_reconcile.py`；后续应统一设计 UTC helper 后整体迁移 |

## 2026-08-25 — XRay 完整能力目标合同

| 决策 | 理由 | 证据 |
|---|---|---|
| TargetedReview（专项复核）、真正的 FamilyRouting（专项家族路由）、多 Attempt（物理尝试）、多 Provider（模型提供方）、自动降级、双 lane（通道）和医学 Prompt（提示词）优化均属于完整目标，不再写成永久排除项 | 用户明确要求这些链路最终全部完成；但当前工程与医学证据不足以同时启用 | 用户当前要求；`docs/refactor/21-xray-complete-capability-chain-and-session-prompt.md` |
| 完整能力按 `P0-A（已完成） -> P0-B + Q0 + Q1 -> E1 -> M1 -> Primary Prompt A/B -> 第二模型最小资格化 -> Model A/B -> M2 -> Retry -> Fallback -> Race` 累积完成 | 先消除可靠执行和 Prompt 运行合同缺口并建立真实主读基线，再做可归因的 Prompt/模型单变量实验；专项和可靠性能力由残余错误率、SLA 与成本证据触发 | `docs/refactor/23-xray-next-phase-correction-and-implementation-guide.md` 第 8、11、12 节 |
| 不新增 `fallback（降级）` execution mode（执行模式） | 现有 `single（单并发执行）` 可表达顺序候选，`race（并发竞速）` 可表达双通道；新增第三模式没有必要 | `ai_call_record.execution_mode` 候选 single/race；21 号文档第 12.3 节 |
| v2 Prompt 目标使用 Shared Medical Core + Primary/Targeted Frozen Entry（共享医学核心加主读/专项冻结入口） | 初期可共用正文防止漂移，但 Primary 与 Targeted 的输入和锚定风险不同；是否拆成两个不可变模板必须由 Paired A/B 决定，且不恢复旧式多器官 Prompt 家族 | `prompt_commands.py` v2 分支；23 号文档第 8 节 |
| E4 前只评审为现有 Attempt 最小增加 `lane_key（通道键）`，不新增 Lane 表、Call 表、Attempt 表或 Service（服务） | 自动降级和每 lane 多 Attempt 需要稳定通道身份；Winner 已可由 `winner_attempt_id` 表达，其他结构可复用 | 当前 `ai_call_attempt_record` 无 lane_key；`ai_call_record` 已有 winner_attempt_id；21 号文档第 13.3、16 节 |

## 2026-08-25 — 环境配置迁移与启用门禁

| 决策 | 理由 | 证据 |
|---|---|---|
| 旧 `vet-platform/.env` 只作为脱敏配置参考，不成为 `ms-image` 在线运行依赖 | 旧系统是迁移来源而非在线上游；整份复制会把旧 Mongo、路由、裁剪、评测和 Secret 污染当前边界 | 当前/旧 `.env` 键级比较；`apps/backend/core/config.py` 当前消费合同 |
| 不把旧 `GEMINI_API_KEYS` 直接迁入当前 `.env` | 当前架构要求冻结 Connection/Model Pool/Config 的 `secret_ref` 指向唯一受控环境引用；旧 key 列表没有当前连接身份、资格化和轮换语义 | `EnvironmentReferenceSecretResolver` 合同；当前数据库旧表缺 `secret_ref` 等字段 |
| 在数据库控制面、JWT 和 Provider 资格化闭环前显式保持 Broker/Gateway fail-closed | 基础设施连通不等于控制面可运行；当前打开只会形成配置宣称启用、任务实际失败或鉴权缺失的假闭环 | 主库 schema 只读检查、`ms_image_eval` 失败、Settings 解析和 Gateway Runtime 装配逻辑 |
| 不因旧项目存在 `rsa_public.pem` 就直接复制 | 是否继续信任旧 token 取决于 issuer、audience、签发私钥和调用方迁移合同；只复制公钥可能扩大或错误继承信任边界 | `apps/backend/core/config.py` 与 `core/dependencies.py` 的 RS256/issuer/audience 校验 |
| 不直接对当前 `ms_image` 执行 Alembic upgrade | 数据库已有旧 AI 表和数百行数据，但没有 Alembic 版本标记且结构与当前 ORM 不一致；必须先评审兼容、备份、baseline/stamp 和回滚 | `information_schema` 只读检查；现有 `20260824_01`、`20260824_02` 未应用迁移 |

## 2026-08-25 — 完整 AI 与 Prompt 实施权威

| 决策 | 理由 | 证据 |
|---|---|---|
| 23 号文档成为当前后续实施权威；22 号保留完整架构参考，21 号保留长期能力范围 | 23 号已修正三类权威、FamilyRouting 医学所有权、Prompt 双入口、实施依赖和分层完成定义；保留 21/22 的背景价值，但不允许三个入口互相覆盖 | `docs/refactor/23-xray-next-phase-correction-and-implementation-guide.md`；`docs/refactor/22-xray-full-ai-prompt-chain-development-guide.md`；`docs/refactor/21-xray-complete-capability-chain-and-session-prompt.md` |
| Service（服务）负责领域事实、可靠执行和外部依赖；Stage（阶段）负责医学流水线，不按 Family（家族）拆表或拆 Service | 可让每个医学阶段独立优化和调整顺序，同时避免把 OSS、数据库、重试与医学判断混成一层 | 当前 runtime/service 与 runtime/stages 代码结构；22 号文档第 6、7 节 |
| Prompt（提示词）完善纳入完整目标，但必须在冻结基线和 Failure Bank（失败样本库）后逐变量实施 | Prompt 更长或模型调用更多不等于准确率提高；需要固定病例、同图像配对实验和 Holdout（留出集）隔离因果 | xray-v2-accuracy-governor（XRay V2 准确率治理）合同；22 号文档第 8、12、13 节 |

## 2026-08-25 — XRay P0-A 合同决策

| 决策 | 理由 | 证据 |
|---|---|---|
| v2 Targeted 仍使用单一冻结 Prompt 正文，但必须携带并验证唯一 Family/Focus/Strategy 路由事实 | Family/Focus 在 v2 不应重新选择可变 Prompt 正文，但它们是 Targeted 输入、审计和重放的必需事实；遗漏会与 `XRayPromptCommand.compile()` 合同冲突 | `apps/backend/services/runtime/stages/xray/prompt_commands.py`；`test_targeted_v2_command_preserves_unique_route_evidence` |
| P0 不把当前固定 `primary_final` 的 FamilyRouting 提前改成真实路由 | 真正 FamilyRouting/Targeted 属于 M2，必须由 Primary 残余 Failure Bank 和医学 Gate 证明；P0 只锁定不改医学状态和完整结果透传 | `apps/backend/services/runtime/stages/xray/family_routing.py`；`test_xray_family_routing_only_returns_primary_final_and_preserves_primary_result`；23 号文档第 11、12 节 |
| unknown 最大对账次数不复用 `state_version` 或 `usage_json` | `state_version` 是通用 CAS fencing，`usage_json` 是 Provider 用量；偷用会造成含义不稳定、不可审计。若必须满足持久计数，评审现有 Attempt 最小 `first_unknown_at/reconcile_count` 字段并等待迁移授权 | `apps/backend/models/ai_call_attempt.py`；`apps/backend/services/runtime/service/ai_attempt_reconcile_service.py`；P0 源码核验 |

## 2026-08-25 — Prompt 完善与下一实施入口

| 决策 | 理由 | 证据 |
|---|---|---|
| Prompt 完善拆为 Prompt Runtime Contract（提示词运行合同）和 Medical Prompt Optimization（医学提示词优化） | 来源、渲染、消息、Schema、冻结和重放属于工程正确性；正常/异常准确率改善属于医学实验。混为“Prompt 已接通”会造成错误放行 | `docs/refactor/23-xray-next-phase-correction-and-implementation-guide.md` 第 8 节 |
| 下一开发入口为 P0-B + Q0 Prompt Inventory + Q1 Prompt Runtime Contract，之后进入 E1 | P0-A Targeted family/focus 已由源码和测试完成；当前真实阻断是可靠执行合同、active Primary Prompt/Config 事实和完整运行资格 | 23 号文档第 11、12、14、16 节；当前 P0-A 测试证据 |
| Primary Prompt A/B 必须等待 E1 和 M1，Targeted Prompt 资格化必须等待 M2 残余 Failure Bank | 没有真实运行和冻结基线无法归因；Targeted 若无稳定、唯一可路由的残余失败，只会增加成本、锚定和误报风险 | 23 号文档第 8.9-8.11、12.4-12.7 节；xray-v2-accuracy-governor 合同 |
| 新会话 Prompt 保留 Retry、第二 Provider、Fallback 和 Race 为完整长期范围，但逐项资格化 | 用户要求完整链路；同时运行可靠性能力会改变成本、错误分布和模型结果归因，必须按 Gate 分阶段启用 | 23 号文档第 11、16 节 |

## 2026-08-25 — P0-B 可靠执行与 Prompt 重放决策

| 决策 | 理由 | 证据 |
|---|---|---|
| Task 取消与新 Attempt/Stage/Report 最终化通过同一 Task 行锁串行化 | 仅检查时间戳而不锁行会允许取消与 Provider 发送、Winner 或报告创建并发穿透；现有 TaskDal/CAS 足够，无需新表或 Service | `TaskService.cancel_task()`；`AIRequestService` reservation/retry/network/finalize；`ImagingExecutionService.finalize_ai_stage()`；`ReportService.finalize()` |
| 迟到 Provider 结果保留 Physical Attempt 事实，但不得覆盖已取消/终态 Task 或既有 Winner | Attempt 是真实物理调用审计，删除响应会破坏成本和血缘；业务结果只能由 pending Call 的技术 Winner CAS 建立 | `AIRequestService.finalize_attempt()`；`test_late_attempt_success_is_audited_but_cannot_win_cancelled_task` |
| Report Finalization 的幂等身份使用 DecisionFinalization source 与规范内容事实，不新增通知表或新幂等服务 | 同一 Stage 重放应返回同一 Report；同源不同内容必须 fail closed。通知下游合同尚不存在，不能凭空创造事件 | `ReportService.finalize()` / `publish()`；现有 Report DAL；本轮 Report 合同测试 |
| 冻结 Config 重放必须重新验证 Prompt message/profile 语义，不能只校验内容哈希 | 哈希只能证明字节未变，不能证明 Targeted user context 包含 Primary 完整结果或 context key 已在 variables 声明；编译与重放必须对称 | `AIConfigCompiler._validate_prompt_message_contract_variables()`、`_validate_profile_prompt_contract()`、`verify_frozen_integrity()`；frozen Targeted 合同测试 |


## 2026-08-25 — 参考 AI 链运行态判定

| 决策 | 理由 | 证据 |
|---|---|---|
| 前次真实 AI 请求失败定性为 Platform 进程缺失，而不是 Prompt/Nacos/API Key/Provider 错误 | 目标 loopback 8062 无监听，异常为 TCP `ConnectError`；请求没有 HTTP response 或 gateway request ID | `ms-ai-fast` 当前 `.env` 脱敏坐标、`GatewayClient` 最小复现、8062 listener 检查 |
| Platform 启动后可声明 `ms-ai-fast` 参考网络链已真实跑通 | Nacos Prompt 渲染、Platform 鉴权/调度、Provider 返回、actual model、usage、request ID 和 content 均有在线证据 | `AiRuntimeService.invoke_prompt(flow.answer)` 在线烟测；Platform 200 日志 |
| 不把 qwen 403 解释为整体 AI 链失败 | 该端点受 IP restriction 失败，但 Platform 按竞速/重试合同选用 gpt-5-mini 并返回 200；应作为池内降级风险单独治理 | Platform 运行日志和成功响应 actual model |
| 不把参考链成功升级为 `ms-image` E1 或医学资格化 | 本次没有经过 `ms-image` Outbox/Worker/OSS/Encrypted Store/MySQL/Report，也没有 Gold/Holdout 评测 | 本轮验证边界与 23 号 Gate 合同 |
| 保留 Nacos smoke Prompt，等待用户确认后再删除 | 用户明确要求写入 Prompt 测试；保留便于复测，但它是非医疗基础设施 Prompt，不得作为 XRay Primary 候选 | `ms-image.xray.chain-smoke.default.zh-CN@1.0.0` runtime 可读证据 |

## 2026-08-25 — 远程 Platform 验证目标

- **决定/事实**：将 `http://8.149.245.40:8060/api/v1` 视为当前 `ms-ai-fast` 参考运行配置的实际 Platform 目标；不为切换该地址修改 AI 业务调用代码。
- **证据**：该地址 health 为 HTTP 200；经 `ms-ai-fast` 原生 `GatewayClient` 的真实 `chat/completions` 请求成功，requested/actual model 均为 `gemini-3.5-flash`，且 request ID 和非空响应存在。
- **边界**：这只证明该参考网关到 Provider 的技术链路可用，不证明 `ms-image` 的 XRay 真实任务链或医学准确率已资格化。

## 2026-08-25 — `ms-image` Provider 地址安全合同

- **决定/事实**：不为复用 `ms-ai-fast` 的明文 HTTP Platform 地址而放宽 `ms-image` 的 HTTPS-only Connection 合同。
- **理由**：`ms-image` 的 Connection 会承载 Bearer Secret、可能含影像签名 URL 与加密响应证据；降为 HTTP 会破坏现有传输安全边界。
- **证据**：`canonicalize_connection_base_url()` 在出站前拒绝 `http://8.149.245.40:8060/api/v1`；该地址的 HTTPS TLS 握手亦失败。
- **后续**：应由远程服务提供有效 TLS 终止地址后再配置 Connection，并补齐环境 Secret Resolver、加密响应存储与 OSS 资格。

## 2026-08-25 — 取代 HTTPS-only 决策：直接按 `ms-ai-fast` 使用远程 HTTP Platform

| 决策 | 理由 | 证据 |
|---|---|---|
| 允许 `ms-image` Connection/Gateway 使用 `http://8.149.245.40:8060/api/v1` | 用户明确要求直接对齐 `ms-ai-fast`，并要求 production 允许；不再以环境名或 HTTP 协议拒绝该 Platform 链 | `canonicalize_connection_base_url()` 已接受 http/https；真实 `OpenAICompatibleGatewayAdapter.execute()` 请求成功 |
| 将核心 AI 链判为已通过，而非“被拒绝” | Nacos 新写 Prompt 由 `ms-image` runtime 读取、渲染、组装，并经其 Secret Resolver/Gateway 到 Platform；返回指定实际模型、Provider request ID、严格 Schema 与 marker 回传 | `ms-image.xray.ai-gateway-e2e.default.zh-CN@1.0.0` 的在线 E2E；validation 记录 |
| 不将本结果升级为完整 XRay 任务链或医学发布 | 此次未经过 MySQL Control Plane/冻结配置、Outbox/Worker、OSS、响应加密、Attempt/Stage/Report 或医学评测 | 当前验证范围与 23 号 Gate 合同 |

## 2026-08-26 — 移除 Gateway selector，不移除 Secret/原始响应保护

| 决策 | 理由 | 证据 |
|---|---|---|
| 移除 `AI_GATEWAY_SECRET_RESOLVER_MODE` | 该 selector 在 `ms-ai-fast` 不存在，且 Worker 仅允许冻结 `secret_ref` 在请求期经环境引用解析；固定安全路径可避免误配为 disabled（禁用）或其它 resolver。 | `core/ai/gateway/secret_resolver.py`；`runtime_dependencies.py:91-105`；`ms-ai-fast` 精确字段扫描为零 |
| 移除 `AI_GATEWAY_RESPONSE_ENCRYPTION` 与 KMS runtime selector | 原始 Provider 响应仍必须进入不可变 AES256 加密 OSS 对象，数据库仍只记录对象引用与摘要；删除的是部署可选项，不是响应保护能力。 | `core/ai/gateway/response_store.py`；`runtime_dependencies.py:101-105` |
| Gateway 启用后固定安全依赖 | `AI_GATEWAY_ENABLED=true` 固定构造 `EnvironmentReferenceSecretResolver` 和 `OSSEncryptedResponseStore(..., AES256)`；实际 Secret 未配置时继续 fail-closed。 | `runtime_dependencies.py:59-108`；gateway dependency composition probe |

## 2026-08-25 — 旧表清理的保守边界

| 决策 | 理由 | 证据 |
|---|---|---|
| 不执行“删除全部 Prompt / AI 表” | 当前模型仍映射 `ai_prompt_template`、`ai_api_connection`、`ai_model_pool`；删除会直接破坏控制面和后续冻结 Config 链。 | `apps/backend/models/ai_prompt_template.py`、`ai_api_connection.py`、`ai_model_pool.py`；对应 Service/DAL 引用 |
| 不把无 FK / 无 trigger 当作无影响 | 旧库应用层关系不由 MySQL 外键表达；表中还有影像、报告、请求和评测历史数据。 | `information_schema` 清理前只读核验 |
| 删除必须按精确表清单授权 | 先决定历史数据归档/迁移保留，再移除对应调用面，最后使用审阅后的迁移执行；不直接针对共享旧库运行 `DROP TABLE`。 | 项目 AGENTS 数据安全与迁移约束 |

## 2026-08-25 — 当前运行事实与完整能力目标分层

| 决策 | 理由 | 证据 |
|---|---|---|
| 将 24 号文档设为当前后续开发事实权威 | 21/22/23 号保留完整能力范围、逐层架构与历史阶段目标，但当前 `.env（环境配置文件）`、核心 AI 网络实测、45 表旧库审计和 Stage（阶段）缺口需要一个单一、可更新的事实入口。 | `docs/refactor/24-current-runtime-audit-and-next-development-guide.md`；`.agent-handoff/snapshot.md`。 |
| 继续在当前工作树上做分阶段内部模块化收口，不回退旧提交重写 | 当前工作树已经含 Task Snapshot（任务冻结快照）、Logical Call/Physical Attempt（逻辑调用/物理尝试）、Gateway（网关）、Prompt（提示词）消费链和 Stage（阶段）结构；主要问题是运行资格与医学证据不足，能够用 Gate（门禁）逐阶段隔离。 | `docs/refactor/24-current-runtime-audit-and-next-development-guide.md` 第 1、3、6 节；`apps/backend/services/runtime/stages/registry.py:24-41`。 |
| 先 P1（工作进程运行时安全资格化）、后 E1（仅主读真实运行链），再谈医学 Prompt（提示词）或专项 | 正式 Gateway（网关）仍要求环境密钥解析、响应加密、OSS 签名/加密和 unknown（未知）查询合同；单次核心 AI 网络调用不能替代整个业务任务链。 | `apps/backend/core/ai/gateway/runtime_dependencies.py:59-107`；`.agent-handoff/snapshot.md`。 |

## 2026-08-25 — 文档入口去歧义

| 决策 | 理由 | 证据 |
|---|---|---|
| 当前实施事实与可复制启动 Prompt 只以 24 号文档和根目录 `AGENT_SESSION_PROMPTS.md` 顶部当前入口为准 | 17、19、20、21、23 分别包含早期 Provider/Config 状态、历史会话 Prompt 或完整目标能力；若不显式标注，会使新会话错误覆盖当前代码与已验证核心 AI 网络事实。 | `docs/refactor/24-current-runtime-audit-and-next-development-guide.md` 第 2、11 节；各文档顶部提示与 23 号第 16 节。 |
| 保留旧文档内容而不删除 | 旧阶段取舍、完整能力边界与架构解释仍有追溯价值；用“当前事实/目标合同/历史背景”分轴即可降低矛盾，不应通过删历史来制造单一叙事。 | `docs/refactor/README.md` 权威边界；用户要求后续开发按当前代码事实继续。 |

## 2026-08-26 — 区分 OSS 对象读取与 Provider 外部可达性

- 决定：P1 将“Worker 凭据可 `GET` 对象”和“Provider 网络可访问短期 signed GET URL”视为两个独立证据。
- 理由：前者可由本进程的对象存储 API `get_bytes` 证明；后者还依赖 Provider 的网络出站、DNS/TLS 与 bucket endpoint 可达性，不能由本机 signed URL GET 推断。
- 证据：2026-08-26 synthetic probe 已通过 AES256 PUT、HEAD、Worker GET、同机 signed GET 与 cleanup；没有调用 Provider 或写 MySQL。

## 2026-08-26 — 不复制 ms-ai-fast 不存在的 Gateway 环境覆盖

- 决定：在确认 `ms-ai-fast` 全目录（包含 ignored 文件）不存在 `AI_GATEWAY_SECRET_RESOLVER_MODE` 与 `AI_GATEWAY_RESPONSE_ENCRYPTION` 后，按用户指示从 ms-image 移除其 `.env`、Settings 与 Gateway composition root 的选择链。
- 边界：保留并固定 environment-reference Secret Resolver（环境引用密钥解析器）、AES256（AES-256 加密）response store（响应存储）、OSS host allowlist（允许域名列表）与 fail-closed（失败关闭）错误合同；删除的是 mode/encryption/KMS selector，不是安全控制。
- 结果：当前 `AI_GATEWAY_ENABLED=true` 的 dependency composition 成功；当前本机无匹配前缀的非空 Secret（密钥）变量，所以真实 `secret_ref（密钥引用）` 仍 fail-closed，未意外取得完整 Worker Runtime 资格。


## 2026-08-26 — AI/Prompt 运行链以 ms-ai-fast 直接合同覆盖旧安全包装决策

| 决策 | 理由 | 证据 |
|---|---|---|
| `ms-image` 的 AI 请求直接使用与 `ms-ai-fast` 同语义的 `GatewayClient`，凭据来自 `AI_PLATFORM_OPENAI_BASE_URL + AI_PLATFORM_API_KEY` | 用户明确要求请求 AI 完全仿照 `ms-ai-fast`，旧 `secret_ref -> EnvironmentReferenceSecretResolver -> Adapter` 是额外且干扰开发的平行链 | `apps/backend/core/ai/gateway_client.py`；`apps/backend/services/runtime/service/ai_request_service.py:1177-1259`；生产残留扫描无旧类名 |
| 删除 Provider 原始响应 OSS 加密 response store；数据库不保存 response object reference | `ms-ai-fast` 请求链没有该包装，用户明确要求删除；保留 Provider Request ID、规范化结果、response SHA 和 Attempt 审计即可满足当前代码事实 | `apps/backend/services/runtime/service/ai_request_service.py:1250-1350`；原始响应存储残留扫描无输出 |
| Prompt/Nacos 使用共享 `NACOS_*`、原始 Prompt 正文、`StrictUndefined/tojson/$variable` 与单条 user message | 避免 `SAFE_*` 别名和 developer/user 二次拆分形成第二套 Prompt 语言，保持参考链语义 | `prompt_source.py`、`renderer.py`、`message_contract.py`；Prompt 合同测试 |
| `secret_ref` 暂留为 Control Plane/数据库兼容元数据，但不得进入 Worker Provider 鉴权 | 删除字段需要模型、Schema 和迁移授权；当前用户要求的是删除运行链，不允许擅自改表 | `ai_api_connection.py`、`ai_control.py`、`config_compiler.py`；当前无迁移授权 |
| 本决策覆盖同日“Gateway 启用后固定 Secret Resolver + AES256 response store”的旧决策；旧记录保留为历史，不再代表当前生产代码 | 防止后续会话按已删除实现继续扩展；以最新用户明确决定和当前源码为准 | 本节；`.agent-handoff/snapshot.md`；81 个定向测试通过 |
