# 长期决策日志

## 2026-08-30 — 最终开发文档的体位、多图与分割边界

- 当前 projection 权威是调用方在 `prepare-upload` 对每张影像显式声明的值；系统将其冻结到 Image、Series/Study Manifest、Task Snapshot、Prompt context 与 Provider SourceRef。当前没有 DICOM `ViewPosition` 自动回填，也没有 AI 像素体位识别。
- 若未来增加 `xray_projection_qc`，它只能输出 declared/observed projection、confidence、conflict status 和 review required；不得静默覆盖已冻结 projection，也不得参与医学诊断事实生成。
- 每个 Primary 或 Targeted Logical Call 都将同一 Task Snapshot 的全部 N 张影像稳定排序后放入一次 GatewayRequest；N 张图不等于 N 次模型调用。Targeted 有 candidate 时总计两次 Logical Call，但两次都分别携带全部 N 图。
- 当前 `ai-image-receipt.v2.image_count=N` 只能证明全部影像已发送。若要证明 Provider 逐图评估，后续结果 Schema 必须增加 `image_assessments`，并强制其 `image_id` 集合与 Task Snapshot 全部输入完全一致；不能用 `source_refs` 数量替代。
- 器官分割冻结为第二阶段独立展示支线：使用 `segmentation_job`、`segmentation_artifact`、`segmentation_outbox` 和独立 Worker/Provider；不加入诊断 Stage Pipeline，不进入 Primary/Targeted Prompt，不修改 `CompleteMedicalResult`、medical status、Task current report 或 Report 医学正文。
- 分割失败、取消、重试、超时和 dead-letter 均不得阻塞 final Report；诊断 Provider 永远读取原始影像，UI 必须标注“AI 辅助可视化，仅供展示，不代表病灶诊断”。
- 开发顺序冻结为先 E0–E8 跑通真实 2–5 图诊断主链，再执行 S0–S6 分割展示，最后才进入 Evaluation、Gold、Scorer 和医学 A/B。产品运行时诊断与分割可以并行，开发依赖顺序不能倒置。

## 2026-08-28 — 当前全链资格分层与剩余工作顺序

- 当前可以声明 `CORE_WORKER_RUNTIME_QUALIFIED` 与 `C2_ENGINEERING_QUALIFIED`：Primary v2 已完成冻结 Config、真实多视图 Snapshot/receipt、Outbox/Broker/Worker、Provider Attempt、Stage、Finalization、Report、duplicate/cancel/late-result、P1-A 自动 reconcile 和 P1-B unknown 有界终止。
- 当前不能声明生产或医学上线：公网/生产 API 安全仍为 `PRODUCTION_API_SECURITY_NOT_QUALIFIED`，医学状态仍为 `MEDICAL_ACCURACY_UNKNOWN / MEDICAL_RELEASE_NO_GO`。
- 医学主线顺序固定为 `D2 严格临床上下文 -> Evaluation 独立库/迁移/readiness/工程链 -> Gold/Scorer/分母/Failure Bank/Regression/Holdout -> M1`；M1 前不启用 TargetedReview、Prompt/Model A/B、Retry、Fallback 或 ms-image 多 lane Race。
- 生产硬化与医学主线分开：JWT/Artifact signing、Compose Secret 最小权限、Platform 常驻进程、发布工件冻结、Report publish/void、Connection URL 一致性、api_format 前置校验和跨平面 verifier 移位均按独立切片处理，不能用其中任一项冒充 M1 医学证据。
- Platform payload 的 `strategy=race` 是当前已验证的 ms-ai-platform 协议字段；在 ms-image 仍为单 lane/max_attempts=1 时，不把字段名误报为已经启用 ms-image 多 lane Race。

## 2026-08-28 — 14 号文档架构选择口径

- 当前运行与医学评测基线唯一采用 `Primary-only（仅主读）`；它是当前唯一真实可达且通过 E1-MV 工程链的方案，但医学准确率仍为 UNKNOWN，医学发布仍为 NO-GO。
- `Primary + Conditional Targeted（主读 + 条件专项复核）` 是唯一保留的未来增益候选；必须先完成可信 M1，再对唯一 Family/Focus、最多一次复核执行同病例 Paired A/B 和独立 Holdout，证明整体净收益后才可启用。
- 默认每器官多调用与 Multi-reader Debate 不进入当前实施：它们增加冲突、误报、成本、延迟和结果 owner 歧义，且当前没有医学净收益证据。
- 五个 Family 继续只作为 v1 报告组织与评测路由词汇，不是永久医学本体、五个模型、五张表或五次调用。
- 14 号文档作为面向新读者和同事讲解的当前入口；代码存在、工程跑通、医学验证必须分层表达，后续不得引用旧段落把 Targeted、Report publish/void 或 Evaluation 写成已可运行。

## 2026-08-28 — 真实多投照位验收边界

- 数据集验收只接受 paired JSON `metadata.Position` 作为本轮 projection 权威；文件名 token、目录、图像尺寸、像素和模型输出均不得反推 projection。
- 本轮 Provider fenced JSON 属技术传输/解析兼容问题。后续若在 ms-image 修复，只能解包一个覆盖完整正文的 JSON fence，随后仍执行同一冻结 JSON Schema；不得补字段、改状态或加入 Python 医学判断。
- Provider 输出不等于 Gold；即使正文正确引用 VD/Lateral 和两张图，也只证明模型收到/使用了工程上下文，不证明医学准确率。

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
| 2026-08-19 | Clinical Family 首期采用五个临床评估包 | 五家族以完整 Study、输入覆盖、报告子域和评测分母为边界；物种、区域、Focus、Strategy 和技术证据保持正交，避免默认多调用和重复表 | `docs/refactor/14-xray-specialty-design.md` §9；设计母文 §6.12 |
| 2026-08-19 | 历史目标曾将 Prompt 组织为六种角色；默认链只运行一次 JointPrimaryReader | 角色只负责组织检查项和复核策略，不产生多个竞争 Final；当前在线运行事实已收敛为唯一 `xray_primary/common`，Targeted 仍关闭 | `docs/refactor/14-xray-specialty-design.md` §5、§8、§10；`docs/refactor/17-prompt-runtime-contract-and-minimal-provider-plan.md` |

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
| 2026-08-20 | Prompt 链按“目录资产 -> AI Config Release -> Task 快照 -> Prompt Command -> Compiled Prompt -> AI Call -> Report/Evaluation”分成配置发布链和病例运行链 | Prompt Catalog、配置发布版、实际渲染内容和调用记录承担不同事实；混成一条或让 Worker 读取 latest Prompt 会破坏重放、A/B 和审计。Primary 一次、Targeted 最多一次 | `docs/refactor/14-xray-specialty-design.md` §10；`docs/refactor/17-prompt-runtime-contract-and-minimal-provider-plan.md` |
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
| `FamilyRouting（家族路由）` 只能输出 `primary_final/targeted_review`，不得生成或覆盖四类医学状态 | 路由器不读图、不调用模型、不拥有医学结论；`review_required` 是有效医学输出，不是工程路由信号 | `docs/refactor/22-xray-full-ai-prompt-chain-development-guide.md:341-359`；`docs/refactor/14-xray-specialty-design.md` §8、§11 |
| 五个 Family 作为 `v1 routing vocabulary（v1 路由词汇）`，不是永久医学本体 | 当前目录缺少足够 Gold、病例分层和样本量证明最优；全身性、多区域和无法唯一归族病例应保持 Primary-only | `docs/refactor/14-xray-specialty-design.md` §9、§14 |
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
| [SUPERSEDED 2026-08-29] D5 保持 Targeted 关闭，不修改 Prompt 医学正文 | 这是 Primary-only 闭环阶段的范围决策；用户后续授权的猫狗 `4.0.0` experiment 全链见文件末尾新决策 | 历史 D5 范围；2026-08-29 用户新优先级 |
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
| [SUPERSEDED 2026-08-29] P0 不把当前固定 `primary_final` 的 FamilyRouting 提前改成真实路由 | 这是早期 P0 范围决策；v1/global 仍保持该语义，用户后续授权的 v2 experiment 路由见下方全链 Prompt 章节 | 历史 v1 测试；2026-08-29 用户新优先级 |
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

## 2026-08-26 — P0 阻断：禁止直接将当前 Alembic 链应用到旧 `ms_image`

| 决策 | 理由 | 证据 |
|---|---|---|
| 在用户明确选择数据库边界并授权前，不对 `ms_image` 执行 `alembic upgrade head` | 真实库无 `alembic_version`；现有 `ai_prompt_template`、`ai_api_connection`、`ai_model_pool`、`session_record` 均已存在且有数据，结构也不符合 Runtime ORM；`20260824_01` 会直接 `create_table` 同名控制面表 | 2026-08-26 只读 `information_schema` 审计；`20260824_01_ai_prompt_control_plane_phase_a_c.py:112,236,263,289` |
| 将 `response_object_ref_json` 作为待 P0 处理的遗留源代码合同，而不是现有运行路径 | 当前 Service/Worker 没有写入该字段，但 Model、DAL 和未部署 migration 仍声明“原始响应对象引用”，与用户已决定的“不存原始 Provider 响应 OSS 对象”不一致；直接删除需要与数据库兼容计划一起审阅 | `models/ai_call.py:61`、`models/ai_call_attempt.py:86-89`、`crud/ai_call.py:62`、`crud/ai_call_attempt.py:79`、`20260824_02...:269` |

## 2026-08-26 — Task Admission 与 v2 Gateway Profile 必须作同一冻结事实校验

| 决策 | 理由 | 证据 |
|---|---|---|
| v2 Task 创建前同时校验规范化 `gateway_profile_json`、`capability_manifest.provider_disabled` 和 `gateway_profile_sha256` | Compiler 已根据同一 profile 输出 capability manifest，但原 Admission 一律要求 `provider_disabled=true`，会拒绝正式网络路径所需的 qualified/provider-enabled Config，形成内部合同矛盾 | `6057ec9`；`task_service.py:284-334`；`config_compiler.py:460-465`；86 个定向合同测试 |
| 保持 v1 provider-disabled 兼容链，不在本切片变更 Snapshot、Retry、unknown 或数据库契约 | v1 非终态 Task 尚未确认清零；本次只修复冻结准入，不应跨越 P0 数据库授权或引入运行时行为变化 | `task_service.py:326-334`；用户固定约束 |
| 真实 imaging Worker 仍只以 `AI_PLATFORM_OPENAI_BASE_URL + AI_PLATFORM_API_KEY` 作为 Platform 出站配置；当前缺失时停止真实资格化，不回退到已删除的 Gateway selector/secret 链 | 这与 `ms-ai-fast` 请求合同一致；本机 Settings 已证实该成对配置当前未就绪，代码会在 Gateway 网络边界 fail-closed | `core/config.py:228-280`；`gateway_client.py:39-81`；本轮非敏感 Settings presence 核验 |

## 2026-08-26 — 方案二 XRay 猫/犬 Primary Prompt 发布边界

| 决策 | 理由 | 证据 |
|---|---|---|
| 以 `vet-platform` 已发布的猫/犬 XRay 全图 Prompt 为工程候选来源，分别整理为 `ms-image` 猫/犬 Primary Prompt | 现有 `ms-image` Primary Prompt 仅一行，不能承担完整 Study 主读；方案二保留已沉淀的技术质量、全图扫查、防漏诊与防过诊规则，同时移除旧 specialist 依赖、变量、状态与输出合同。两条来源均不是医学确认结论。 | 来源表 `ai_prompt_template`：猫 `678`、犬 `679`；本轮发布回读记录。 |
| XRay 是独立 `xray` 模态，Nacos module 使用 `x-ray`；Primary 必须使用 `cat` / `dog` variant，禁止 `default` fallback | 猫犬影像不能共享或互相兜底 Prompt。将物种写入内部 key 和 Nacos variant，使不合法 key 或物种组合在 Nacos 读取前失败关闭。 | `prompt_source.py:29-58, 81-151`；`test_ai_prompt_control_plane_contracts.py:573-615`。 |
| [SUPERSEDED 2026-08-29] 发布 `ms-image.x-ray.primary.cat.zh-CN@1.0.0` 与 `ms-image.x-ray.primary.dog.zh-CN@1.0.0`，不发布 Targeted 或 A/B 变体 | 该决策保留为历史版本事实；后续已发布并资格化猫狗 `4.0.0` experiment 双模式 Prompt，未覆盖旧版本 | 历史 Nacos 发布；2026-08-29 全链 Prompt 决策 |
| Nacos 发布不视为 Config 激活、Worker Runtime 或医学放行 | 旧 MySQL 未具备兼容的 Runtime 控制面表，不能安全导入/编译/冻结；当前先完成工程 AI 链，医学验证后置。 | P0 审计；`.agent-handoff/snapshot.md`；24 号运行时指南。 |

## 2026-08-26 — 宠物档案只复用 ms-ai-fast 的业务语义，不复制其 Alembic revision

| 决策 | 理由 | 证据 |
|---|---|---|
| 未来 XRay 宠物档案采用“档案归属校验 -> 物种归一化 -> Task 创建时冻结”的语义；Worker 不重新读取档案 | `ms-image` Worker 只能使用冻结 Task Snapshot。执行期重新读取可变档案会造成 Prompt/物种漂移，破坏重放与审计。 | `ms-ai-fast/app/service/pet_profile_service.py:80-85`；`ai_media_execution_service.py:182-197,515-516`；`ms-image/task_service.py:356-416` |
| 不直接复制 `ms-ai-fast` 的 `20260706_0001` 或其后续 revision 到 `ms-image` | 其 revision 起点为 `None`，并同时创建多张 fast 业务表；`ms-image` Alembic head 为 `20260824_02`，当前旧 `ms_image` 又无 version 表且有冲突的 `session_record`。 | `ms-ai-fast/.../20260706_0001_ai_business_tables.py:15-43,45-218`；`ms-image/alembic_migrations/versions/20260824_01...:22-23`；2026-08-26 只读 DB 核验 |
| 仅在独立 Runtime DB 的 P0 边界和用户迁移授权明确后，创建一个 ms-image 原生 PetProfile revision | 需要使用本项目 opaque `VARCHAR(64)` ID、`requester_id`、string `species`、UTC `DATETIME(6)`、不建 FK 的既有模型合同；这些均与 fast 的 `BIGINT/user_uuid/TINYINT` 不同。 | `models/imaging_base.py:15-38`；项目 `AGENTS.md` 数据库规则；`ms-ai-fast/app/models/pet_profile.py:13-48` |

## 2026-08-26 — 数据库清理只删除空旧表，不碰有数据历史表

| 决策 | 理由 | 证据 |
|---|---|---|
| 本轮 DB cleanup 只删除“当前 ORM 不建模 + 当前 ms-image 代码不引用 + 无 FK + 精确 0 行”的表 | 用户要求备份后清理无用表；但大量旧表仍有业务历史数据，直接删除不可逆且可能影响旧链追溯。空表清理能降低噪声，同时不丢失业务行数据。 | 备份 `/Users/mozhicheng/workspace/code/cy-code/ms-image-db-backups/ms_image-20260826T102227Z.sql.gz`；清理元数据 `/Users/mozhicheng/workspace/code/cy-code/ms-image-db-backups/ms_image-cleanup-empty-unused-20260826T103113Z.metadata.json`；清理后表数 31。 |
| 有数据旧表暂不删除，必须另行列清单并确认 | 当前库残留旧 XRay/AI/governance 数据，且部分表名与目标 ORM 冲突；“当前代码不引用”不足以证明历史数据可丢弃。 | 剩余大表包括 `ai_request_log`、`medical_images`、`report_content`、`async_xray_task`；同名不兼容表包括 `ai_prompt_template`、`ai_api_connection`、`ai_model_pool`、`session_record`。 |

## 2026-08-26 — 用户确认后以当前 ORM 表集合清理 legacy DB 噪声

| 决策 | 理由 | 证据 |
|---|---|---|
| 在已有全量备份基础上，删除所有“不在当前 `ms-image` ORM 模型集合中”的剩余物理表 | 用户明确要求无用表应删除，避免干扰判断；当前目标是新 XRay Runtime 链，旧 XRay/AI/governance 表不再作为运行时事实来源。 | 清理元数据 `/Users/mozhicheng/workspace/code/cy-code/ms-image-db-backups/ms_image-cleanup-legacy-non-runtime-20260826T103657Z.metadata.json`；清理后 `DB_NOT_IN_MODELS=[]`，剩余表数 4。 |
| 保留 4 张当前代码同名表，不在本轮直接 DROP | 它们虽是旧列结构，但表名由当前 ORM 声明；删除它们属于 Runtime baseline/rebuild 决策，而不是“非 ORM legacy 噪声清理”。下一步需要单独处理以避免 Alembic/运行时冲突。 | `models/ai_prompt_template.py:13`、`models/ai_api_connection.py:13`、`models/ai_model_pool.py:13`、`models/session.py:11`；清理后列差异复核。 |

## 2026-08-26 — 清空剩余同名旧结构表，转为空库 Runtime baseline

| 决策 | 理由 | 证据 |
|---|---|---|
| 删除 `ai_api_connection`、`ai_model_pool`、`ai_prompt_template`、`session_record` 4 张剩余旧结构表 | 用户要求删除没用表；这 4 张虽与当前 ORM 同名，但字段结构旧且不可直接用于新 Runtime，会干扰下一步判断和 Alembic 建表。全量备份与每表 DDL/行数 metadata 已保存。 | 清理元数据 `/Users/mozhicheng/workspace/code/cy-code/ms-image-db-backups/ms_image-cleanup-remaining-old-structure-20260826T121615Z.metadata.json`；清理后 `information_schema` 表数 0。 |
| 清空旧表不等于 Runtime baseline 完成 | 当前 DB 没有任何物理表、没有 `alembic_version`，所有 Runtime 目标表仍需正式建表/迁移。 | 清理后复核 `table_count=0`；当前模型仍声明 20 张表。 |


## 2026-08-26 — 快速上线阶段 Prompt 内容共用优先于猫犬医学分叉（已被下节修正）

| 决策 | 理由 | 证据 |
|---|---|---|
| 首版快速上线推荐保留 `ms-image.x-ray.primary.cat/dog.zh-CN` 外部身份壳，但让两者继承/共用同一 common XRay Primary 正文 | 这满足用户“先不区分猫狗、快速上线”的目标，同时避免立即改动已通过测试的 XRay fail-closed PromptSource 合同；未来恢复猫/犬差异只需发布不同版本 Prompt。 | 用户 2026-08-26 最新指令；`prompt_source.py` 当前只允许 `xray_cat_primary -> cat` 与 `xray_dog_primary -> dog`；`test_ai_prompt_control_plane_contracts.py` 已覆盖禁止 XRay `default` fallback。 |
| 不把共用正文视为医学放行 | 共用正文只是工程收敛与上线提速策略；未做病例 gold set、Prompt A/B 或医学评测。 | 当前状态仍为 `MEDICAL_ACCURACY_UNKNOWN / MEDICAL_RELEASE_NO_GO`。 |


## 2026-08-26 — 当前 Model 注册表作为数据库保留与建表唯一清单

| 决策 | 理由 | 证据 |
|---|---|---|
| 不再主观判断当前 Model 中哪些表“有用”；`apps/backend/models/__init__.py` 注册的 Model 全部保留并创建 | 用户明确要求基于当前 Model 重建数据库，同时不再做 Model 内部用途筛选；避免再次误删运行链表 | 用户 2026-08-26 指令；最新 DB 复核为 20 张 Model 表 + `alembic_version`，`model_missing=[]`、`extra_non_model=[]` |
| 后续禁止自行删除当前 Model 对应表 | 当前业务数据虽为空，但结构是 Prompt/Config/Task/Worker 完整链的基础；删除会再次破坏 P0 | `apps/backend/models/__init__.py:1-44`；`alembic_version=20260824_02` |

## 2026-08-26 — 快速上线改为唯一 canonical XRay Primary（修正上一节）

| 决策 | 理由 | 证据 |
|---|---|---|
| 首版不按猫/犬选择 Prompt 时，使用唯一内部 key `xray_primary`、唯一 Nacos `primary.common`、唯一 global `xray_diagnose` Config；不再保留两个运行身份壳 | 两个相同正文但不同身份会制造重复 source of truth；当前 Task Runtime 只选择并激活一个 global Config，两个壳不能同时产生运行价值。单一身份更贴合“一份冻结完整 XRay Prompt/唯一 Primary 候选”的既有架构。 | `docs/refactor/22...:769-770`；`docs/refactor/23...:384-397,925-932`；`task_service.py:55-64,102-106,256-282`；`config_compiler.py:488-497` |
| XRay `common` 只能 exact-only，不能充当 cat/dog/default fallback | `common` 表达首版唯一 canonical variant，同时避开历史 `default` Data ID 歧义；fail-closed 仍由精确 key/variant 校验保证。 | `prompt_source.py:81-149` 当前 XRay exact-only 机制；已有历史 default/cat/dog Nacos 身份 |
| “传承”只用于编写/发布阶段复用；Runtime 只消费已物化并冻结的一份完整正文、变量合同和 SHA | 动态父子 Prompt 读取/拼接会新增外部 latest 漂移和第二套解析路径，破坏 Config/Task Snapshot 的不可变、可审计、可重放合同。 | `config_compiler.py:488-497`；Worker 只读冻结 Task Snapshot 的既有决策 |
| 首版 species 是安全上下文，不是 Prompt 路由键；未来只有医学证据支持时才恢复物种分叉 | 可以跳过宠物档案和多 Config 路由的首版复杂度，但不把工程收敛误报为医学合格。 | `docs/refactor/23...:384-397`；当前 `MEDICAL_ACCURACY_UNKNOWN / MEDICAL_RELEASE_NO_GO` |


## 2026-08-26 — XRay 由接口参数区分猫狗并共用单一 Prompt

| 决策 | 理由 | 证据 |
|---|---|---|
| `diagnose` Task request body 必传 `species=cat|dog` | 用户要求快速上线并明确“接口通过传参区分猫狗”；避免新增宠物档案表、自动查询链和运行时猜测。 | `apps/backend/schemas/task.py`；用户 2026-08-26 决定。 |
| species 在 Task 创建期归一化并冻结进 request snapshot | Worker 只消费冻结事实；species 进入 request SHA，可防止相同幂等键下的物种漂移。 | `apps/backend/services/runtime/service/task_service.py`；`apps/backend/services/runtime/stages/xray/prompt_commands.py`。 |
| XRay 只保留 `xray_primary/common` source identity，`common` exact-only | 物种是安全上下文而非 Prompt 路由坐标；单一 Config/Prompt 更符合快速上线和既有 global/global 激活链，同时禁止 `default` 或跨 variant fallback。 | `apps/backend/services/ai_control/service/prompt_source.py`；既有控制面合同测试。 |


## 2026-08-27 — `ms-image` 与 `ms-ai-fast` 未来统一服务的数据边界

| 决策 | 理由 | 证据 |
|---|---|---|
| 统一骨架只复用 `ms-image` 的共享 AI Runtime，不把影像 `Session -> Study -> Series -> Image` 链提升为所有模态的通用业务模型 | 当前 Task/Service 强制校验 Study 与 Study revision；文本、音频、视频不应伪造 Study 才能运行 | `apps/backend/models/task.py`；`apps/backend/schemas/task.py`；`apps/backend/services/runtime/service/task_service.py` |
| fast 的 `session_record` 若迁入，应改为独立消息明细语义，不能直接并入当前 `session_record` | fast 表每行保存 role/content/image/evaluation，是消息；ms-image 表保存来源会话、subject、状态、取消和幂等边界，是会话聚合 | `../ms-ai-fast/app/models/session_record.py`；`apps/backend/models/session.py` |
| fast `ai_task` 的业务任务部分映射到 `task_record`，投递部分映射到 `outbox_record`；fast `ai_task_attempt` 不等同于 Provider `ai_call_attempt_record` | Worker/Celery 执行尝试、Broker 投递和 Provider 网络发送是三个不同事实，合并会破坏恢复、对账和计费语义 | `../ms-ai-fast/app/models/ai_task.py`；`../ms-ai-fast/app/models/ai_task_attempt.py`；`apps/backend/models/outbox.py`；`apps/backend/models/stage_checkpoint.py`；`apps/backend/models/ai_call_attempt.py` |
| 兼容以语义和外部身份为主，目标主键仍使用 opaque `VARCHAR(64)`；旧 ID 通过 `source_system + source_resource_id` 保留 | 复制自增 BIGINT、外键和 TINYINT 状态会把遗留物理设计固化进新服务，且违反当前项目数据合同 | `../ms-ai-fast/app/models/base.py`；`apps/backend/models/imaging_base.py`；项目 `AGENTS.md` |
| 当前先完成 XRay 兼容和共享 Runtime；只有全量迁入 fast 多模态模块时，才新增轻量 `medical_case_record`、消息表和通用输入合同 | 避免为尚未确认的全量合并提前创建 God table、公共文件真相源或空泛抽象，同时保留未来扩展路径 | `docs/refactor/24-current-runtime-audit-and-next-development-guide.md:145-179`；用户的未来统一服务目标 |


## 2026-08-27 — XRay Nacos Prompt 发布集合保持单一 canonical Primary

- 决定：当前只发布 `ms-image.x-ray.primary.common.zh-CN@1.0.0`，本地按 `prompts/xray/nacos/primary/common/zh-CN/` 管理；不把旧 v1 catalog 模块、离线评测素材或输出 Schema 当成独立 Nacos Prompt。
- 理由：当前 `prompt_source.py` 对 XRay 仅允许内部 `xray_primary` + exact-only `common`；猫犬和 primary/targeted 模式均通过冻结安全上下文进入同一正文，源码没有第二个可导入的 XRay Nacos Prompt 身份。
- 边界：发布与回读只证明 Prompt Source 可用；未证明数据库导入、Config 激活、完整 Worker Runtime 或医学准确率。

## 2026-08-27 — XRay Prompt 数量与 Targeted 入口边界

- 当前 v2 Primary-only 正式运行入口只需要并只允许 `xray_primary/common`；猫犬通过冻结 `species` 变量处理，不拆 Prompt。
- 旧 catalog 的 20 个 base/module/focus/strategy/technical/offline 资产是 v1 组合素材，不按数量映射为 v2 Nacos Prompt，也不逐个发布。
- 完整目标链新增的唯一逻辑 Prompt 入口是 Targeted Frozen Entry；FamilyRouting 为确定性程序规则，Retry/Fallback/Race/Provider 切换复用冻结医学 Prompt。
- Targeted 候选可提前在本地准备，但在 Prompt Source identity、Config 和确定性路由接线完成前不得发布为“已接入”或“可运行”。


## 2026-08-27 — 使用三种口径描述 `ms-image` 全部 AI 与 Prompt 能力

- 决定：后续讨论 Prompt 数量时必须明确口径：当前最小在线 Runtime 为 1 个 Primary；完整 XRay 目标 Runtime 为 Primary + TargetedReview 2 个；若包含离线失败分析则为 3 个语义完整 Prompt/Prompt-like 指令。
- 决定：旧 catalog 的 20 个 base/module/focus/strategy/technical/offline 资产继续作为 legacy 组合与医学规则素材，不逐个映射为 Nacos dataId。
- 决定：`StudyCreate.modality_type` 可接受某种影像类型，只代表领域输入能力；没有专用 Pipeline/Stage/Prompt/Schema/Provider/Report 合同时，不得宣称对应 AI 能力已实现。
- 统一盘点文档：`docs/refactor/25-ms-image-complete-ai-capability-inventory.md`。

## 2026-08-27 — Primary Prompt 不再作为主链缺口

- 当前 Primary-only Runtime 的 canonical Prompt 固定为 `xray_primary/common/zh-CN@1.0.0`；本地资产、Nacos 发布和写后回读已完成，后续不得再把“缺 Primary Prompt 正文”列为阻塞。
- Primary 主链下一最小执行序列固定为：导入/激活 Config -> 建立真实 ready Study/Revision -> 创建冻结 Task/Outbox -> 正式 Worker 同链运行。
- Provider 原始响应正文继续不持久化；`response_object_ref_json` 仅作为待数据库授权后处理的遗留字段，不恢复旧加密 OSS response store。
- 证据入口：`docs/refactor/25-ms-image-complete-ai-capability-inventory.md` 与 `docs/refactor/26-ms-image-primary-chain-incomplete-capability-checklist.md`。


## 2026-08-27 — AI Connection 控制面不再承载 Secret 引用

- Worker/Provider 请求的唯一凭据合同固定为进程环境中的 `AI_PLATFORM_OPENAI_BASE_URL + AI_PLATFORM_API_KEY -> GatewayClient`；Connection 只保存非敏感路由与能力元数据。
- API Create/Update/Response、Connection SHA、Config Snapshot、控制面 Audit 与 DAL 更新白名单全部移除 `secret_ref`；禁止后续把遗留物理列重新接回运行链。
- 旧 MySQL `secret_ref NOT NULL` 列只写空字符串兼容占位；未经明确表/字段/迁移授权不删除物理列。
- Provider 原始响应正文继续不持久化，不恢复旧 response store；只保留严格 Schema 后的结构化结果、摘要、Provider Request ID、实际模型、usage、耗时和审计事实。

## 2026-08-27 — Primary 正式 Worker 合同决策

| 决策 | 理由 | 证据 |
|---|---|---|
| ms-image 冻结单 lane 与 Platform `strategy` 分离；Platform payload 使用 `race`，但 ms-image 仍保持单 lane、`max_attempts=1` | Platform 只接受 `round_robin/race`，把单 lane 错映射为 `single` 会稳定返回 HTTP 400；不能因字段名误报已启用业务 Race | `AIRequestService._build_gateway_payload()`；真实 400/200 合同探针；成功 Task `7c37b9b659bb4b8e98b6a6076923c985` |
| Primary happy-path 通过不等于完整 Worker Runtime 资格化 | duplicate/cancel/unknown/late-result 会改变幂等、费用和终态语义，必须分别用真实环境证明 | 本轮同一 Task happy-path 证据；对应真实恢复验证均 `NOT RUN` |
| Provider 原始响应继续不持久化 | 当前用户批准合同只保留规范化结果、摘要、Provider Request ID 和审计事实；恢复 response store 会引入无批准的安全链 | 成功 Call/Attempt 的 response SHA 与 parsed result 存在，`response_object_ref_json` 为空 |

## 2026-08-27 — Duplicate Delivery 资格合同

| 决策 | 理由 | 证据 |
|---|---|---|
| 已完成 Stage 的 Broker 重投必须复用原 Outbox event identity，并在 Stage claim 边界幂等结束；不得新建 Call/Attempt/Report，也不得再次访问 OSS/Provider | duplicate delivery 是消息系统正常恢复语义；以新 event 或新 Attempt “重新执行”会造成重复费用和迟到医学结果覆盖 | 真实重投 Outbox `806bf09dbbb74d55aa3f72688608ef83`；Worker 成功确认；Task/Stage 版本与 Call/Attempt/Report 数量、ID、摘要均不变 |

## 2026-08-27 — cancel-before-provider 在 Stage claim 事务内收敛

| 决策 | 理由 | 证据 |
|---|---|---|
| Task 已记录取消且原 Stage 仍为匹配版本的 `queued` 时，由 `ImagingExecutionService.claim()` 在同一数据库事务内将 Stage/Task 收敛为 `cancelled`，然后返回空 | 只抛 `task_not_executable` 会导致消息拒绝但数据库长期停留 `queued + cancel_requested_at`；claim 是进入 Prompt/OSS/Provider 前的最早权威边界 | `apps/backend/services/runtime/service/imaging_execution_service.py` 本切片实现；真实 Task `ef0c8b9935f543aa8f70b63f267c73b0` 资格化 |
| 已取消 Stage 的相同 Outbox event identity 重投幂等确认，不重复 CAS、claim 或创建运行事实 | Broker duplicate 是正常恢复语义；取消终态是数据库权威事实，重复执行会造成无意义版本推进或网络副作用 | 真实 Outbox `a3d3c31b667d4f49a77ad6ba170ef06c` 第二次投递后所有状态/版本和 Call/Attempt/Report 数量不变 |
| cancel-before-provider 通过不等于完整 P1 通过 | provider-sent late-result 与 unknown lookup/reconcile 具有不同的费用、Winner 和恢复语义，必须作为独立切片验证 | 本轮只证明 Provider 前取消；late-result/unknown/JWT/Artifact signing 均 `NOT RUN` |


## 2026-08-27 — unknown Attempt 安全对账合同

| 决策 | 理由 | 证据 |
|---|---|---|
| due Attempt 在查询事务内立即冻结 `attempt_id + state_version`，Worker 不携带 ORM 实例跨事务 | 正式 session 使用 `expire_on_commit=True`；跨事务读取 ORM 会在真实 MySQL 上触发 `DetachedInstanceError` | `apps/backend/workers/imaging_worker/ai_attempt_reconcile.py` 修复；真实失败探针与新增合同测试 |
| 当前 OpenAI-compatible Connection 不支持原请求查询时，只按同一 Attempt 身份返回 unsupported 并 reschedule；禁止创建替代 Attempt 或 POST Provider | unknown 代表网络交付不确定，盲发会造成重复费用和重复医学结果 | 真实 MySQL qualification：idempotency SHA/Provider Request ID 不变、Attempt 总数不增加、Call 不变 |
| claim lease 是崩溃恢复边界；未到期不得重复处理，到期后可重新 claim | 防止并发 reconciler 重复 lookup，同时允许 claim 后进程崩溃恢复 | 30 秒真实 lease 探针：立即 `claimed=0`，31 秒后恢复 `claimed=1/unsupported=1` |
| 手工 `run_once()` 通过不等于自动 reconcile 已资格化 | 当前部署没有 beat/cron/周期发送者，未知 Attempt 不会自行触发注册的 Celery task | `celery_app.py` task 注册与 `docker-compose.yml` worker command 审计 |
| unsupported unknown 的最大等待/次数必须依赖持久事实，未授权前不借内存计数伪实现 | 进程重启会丢失内存计数；可靠有界终止需要表字段与迁移 | 当前 Attempt 仅有 `next_reconcile_at`；源码无 `first_unknown_at/reconcile_count/max_reconcile_count` |

## 2026-08-27 — 本地无 Docker 全链路作为当前主链运行方式

- **决策**：用户在 P1 资格化完成前明确"不需要使用 Docker，先使用代码全链路跑起来"。以本地进程（uvicorn + outbox relay + celery worker）作为当前 XRay 主链验证与演示方式，`scripts/dev/run_local_chain.sh` 提供一键启动，`scripts/dev/run_e2e_local.py` 提供全链复跑。
- **理由**：Docker Compose 的配置注入断层（`.env-01` 无 AI_PLATFORM_*、Dockerfile 不复制 `.env`）不是当前最小阻断；本地进程直接读取 `.env` + 注入 ms-ai-fast 平台凭据即可闭环，且不修改任何部署配置。
- **证据**：2026-08-27 真实 E2E 全链通过（validation.md 记录非敏感证据）。

## 2026-08-27 — 27 号 XRay API/链路方案的当前实施裁决

| 决策 | 理由 | 证据 |
|---|---|---|
| 不整体照搬 27 号文档，不重写现有主链；采用保留入口的内部模块化重构 | 当前 API -> OSS -> Outbox -> Worker -> Provider -> Report 主链已真实通过；失败集中在状态合同、结果 Schema、逐图元数据和评测证据，不满足全链重写条件 | `docs/refactor/28-xray-evidence-driven-development-guide.md`；`.agent-handoff/snapshot.md` |
| 下一最小代码切片为 C1：在持久化边界从完整模型结果投影合法 medical status，ReportService fail-closed | `produced` 是 v1 Stage availability，却被写入 Report/Task，并被 Evaluation 当作 predicted status；C1 不需表、字段、迁移，也不改变 Prompt/模型 | `joint_primary_reader.py:47-66`；`decision_finalization.py:23-38`；`imaging_execution_service.py:400-410`；`evaluation_execution.py:10-16`；`evaluation_export_service.py:261-269` |
| 保留冻结 v1 Stage 可重放，CompleteMedicalResult v2 再正式版本化 `result_availability` 与严格嵌套结果合同 | 直接改写 v1 handler 语义会损害持久化的 handler version；边界规范化能修复非法持久状态并保持旧任务可完成 | `core/pipeline.py:39-118`；`services/runtime/stages/registry.py:24-41`；`docs/refactor/28-xray-evidence-driven-development-guide.md` §7.2/§9 |
| projection 走 Image -> canonical manifest -> Task Snapshot -> Prompt 逐图血缘；不加 Study projection summary | Model 已有 projection，Provider 已发送全部 ready Images；派生 summary 会复制 Image/Manifest 真相并产生漂移 | `models/image.py:141-145`；`core/imaging/manifest.py:68-109`；`task_service.py:377-399`；`ai_request_service.py:1545-1611` |
| clinical context 随 Task 严格冻结，不新增 Session context；固定病例库复用 Evaluation Job/Run/Artifact | 避免两个上下文 owner；现有 Evaluation Job 已有 fingerprints、split、denominator 和 manifest | `schemas/task.py:9-45`；`schemas/evaluation.py:49-59` |
| C1 裁决时暂不做 segmentation、release-state、fixed-bank 新 API、一步 diagnoses、Task page/report view；后续仅按用户逐项授权打开 | 这些项不阻塞当前医学证据链，部分在 27 号内部自相矛盾；没有消费者和指标前实施只会扩大范围。`GET /tasks/page` 后续因上游恢复诉求明确，已于 2026-08-28 单独授权并实现 | `docs/refactor/28-xray-evidence-driven-development-guide.md` §5/§11/§12；30 号 §7.4 |
- **边界**：密钥只经进程环境注入（AI_PLATFORM_* 来自 ms-ai-fast/.env；dev RSA 密钥在 scripts/dev/keys/ 且已 gitignore）；不写入数据库、Nacos、Task Snapshot、日志或 git。该方式用于工程验证，不等于完整 Worker Runtime 资格化（P1-A 自动 reconcile 后仍欠 JWT/Artifact signing 与 P1-B 有界终止）或医学放行。

## 2026-08-27 — C1 后续实施裁决（29 号文档）

| 决策 | 理由 | 证据 |
|---|---|---|
| DeepSeek 的 C1 结论只标记为 `C1_HAPPY_PATH_IMPLEMENTED`，下一最小切片改为 C1.1 边界加固 | 新 E2E 已正确投影 `review_required`，但 helper 会把多种损坏组合静默降为 `not_produced`，现有测试也未直接覆盖该边界 | `imaging_execution_service.py:46-61,426-454`；`report_service.py:27-53`；`docs/refactor/29-xray-post-c1-development-guide.md` §3/§4 |
| C1.1 严格区分 Stage availability、四值模型医学状态和五值持久化状态；非法组合工程失败，不从 Findings 推断 | `produced/not_produced` 是 v1 availability，不是模型诊断；静默降级会把合同损坏伪装成无结果并污染 Evaluation 分母 | 29 号 §4.2-§4.4；`complete_medical_result.schema.json` 四值 enum |
| P1-A 必须同时交付 scheduler owner、queue/process deployment、聚合观测和非人工自动触发真实资格化，不能只加 Celery Beat schedule | 当前 task 已注册但没有周期发送者；错队列、双 scheduler 或未更新进程定义都会形成“代码存在、运行未发生” | `celery_app.py:125-151`；`scripts/dev/run_local_chain.sh` 当前三进程；29 号 §5.1 |
| P1-A 与 P1-B 分开：自动调度不等于 unknown 有界终止 | 当前默认 lookup 为 unsupported，自动调度只会使永久重排自动发生；可靠上限需要跨重启持久事实和迁移授权 | `ai_call_attempt.py:99-118`；`ai_attempt_reconcile_service.py:89-108`；29 号 §5.2 |
| 医学证据链按 D1 -> E1-MV -> C2 -> D2 -> M1 推进；P1-B/P1-C 等外部决定时可独立推进 D1，但 release Gate 不能绕过 P1 | 先用 v1 结果证明逐图输入血缘，再单独改变结果 Schema，可保持失败归因；工程路线和医学证据路线回答不同问题 | 29 号 §1.2/§1.3/§13 |
| 不做人工复核工作流和 Report 通知；轮询必须补终态、退避、超时和权限合同 | 用户已明确两项非目标；TaskResponse 当前也没有 `current_report_id`，调用方需在 completed 后查询 Report history | 29 号 §11.1/§11.2；`schemas/task.py:60-83`；Runtime tasks/reports endpoints |
| segmentation 保留为 P2 产品需求，但不能把 `image_role=segmentation` 常量当作功能已完成 | 派生 Image 仍缺 source metadata schema、object identity、查询、权限、版本/删除和 lifecycle；它不是 M1 准确率前置条件 | `schemas/image.py:109-120,189-197`；29 号 §11.5 |

## 2026-08-27 — API 与数据库只读审计裁决

| 决策 | 理由 | 证据 |
|---|---|---|
| 保留现有四应用入口和 `API -> Service -> DalBase -> Model`，不做全链重写 | 动态 OpenAPI 无重复路由，主要业务接口的鉴权、资源归属、幂等和分层主体成立；缺陷集中在状态/数据边界 | 四应用路由动态枚举；Runtime endpoint/Service/DAL 源码审计 |
| Report publish/void 在修复前标记为 `CODE_PRESENT / RUNTIME_UNUSABLE` | Service/DAL 使用默认 `state_version` CAS，但 Report ORM/物理表/Response 都没有该字段；调用方也无法取得 expected version | `models/report.py`、`schemas/report.py`、`crud/report.py:50-54`、`core/crud.py:290-329`、真实 `report_record` columns |
| Evaluation Plane 在独立库与迁移边界修复前标记为 `CODE_PRESENT / RUNTIME_UNAVAILABLE` | evaluation session 指向不存在的 `ms_image_eval`，四张空表却位于主库；单一 `BaseModel.metadata` 和主库 Alembic URL 会继续混建 | `core/async_db.py:12-59`、`models/__init__.py:17-22`、`alembic_migrations/env.py:19-53`、只读 DB 1049 证据 |
| 任一新字段迁移前先修复可重建迁移基线 | 当前两份 revision 只创建 5 张表并假定其他表预先存在；现库 `stamp head` 不是空库 replay 证明 | `alembic_migrations/versions/20260824_01*`、`20260824_02*`、当前 `alembic_version=20260824_02` |
| 新增接口继续按核心必须/P2 后置分层，并按用户逐项授权实施 | projection/clinical context 是输入证据链；Task page/Report view/segmentation/intake 不改变 M1 前核心医学有效性。Task page 已作为明确的 L1 上游恢复能力单独完成，不改变其非医学主线定位 | 27/29 号文档与 Runtime 路由/Schema/Service 对照；30 号 §7.4 |

## 2026-08-27 — 四应用逐接口开发裁决

| 决策 | 理由 | 证据 |
|---|---|---|
| 30 号文档作为当前接口逐项审计和补齐入口；29 号继续管理医学/运行资格化顺序 | 用户要求一个接口一个接口检查；75 个 method/path（71 个业务 API + 4 个根路由）已逐项标记，不能再从 27 号候选清单整体开工 | `docs/refactor/30-xray-interface-by-interface-audit-and-development-checklist.md`；动态 route coverage |
| 无表变更的首个接口修复优先选择 `POST /series` | 该接口能制造旧 Study manifest 与新 Series 同时进入 Snapshot 的事实冲突，且可在现有 Service/DAL/revision 合同内修复 | `study_service.py:154-194,274-376`；`task_service.py:115-126,377-390` |
| `GET /images/page` 是首个缺失读取接口；Task page、Report current 随后逐项补 | Image 目前只有按 ID 查询，调用方重启无法恢复 Series 下资源；现有 Series/status/sequence 索引可支撑首版 | `crud/image.py:69-84`；`models/image.py:22-34` |
| Runtime、AI Control、Evaluation Control 必须各自定义 readiness；Admin 只做可降级聚合 | 当前全局 readiness 错误把在线和评测平面绑成同一流量 Gate，Evaluation DB 缺失会影响 Runtime | `core/readiness.py:220-274`；30 号 §3/§9/§10/§11 |
| Connection validate 保持静态合同，不偷做网络 qualification | 网络资格化需要时间绑定 receipt、凭据和模型能力事实，不能在现有静态 CAS 状态中伪装完成 | `api_connection_service.py:353-425`；30 号 §10.3 |

## 2026-08-28 — 全链路接口闭环分层

| 决策 | 理由 | 证据 |
|---|---|---|
| “接口盘点完成”与“接口开发完成/完整全链路完成”分开报告 | 路由存在不能证明合同可用，单次 Report 产出也不能证明上游恢复、生产运维或医学发布资格 | 30 号 §1.4；Report/Evaluation 阻断；2026-08-27 本地 E2E |
| 全链路按 L0 单病例主链、L1 稳定集成恢复、L2 生产运行运维、L3 Evaluation/医学发布四层验收 | 四层依赖和证据完全不同，合并会把工程 happy-path 误报为生产或医学完成 | 30 号 §1.4、§13、§14 |
| `GET /tasks/page` 与 `GET /reports/current?task_id=` 属于 L1 恢复能力，不是 L0 产出 Report 的阻断 | 现有 create/detail/history 足以完成已知 ID 的单病例主链，但调用方重启后缺少稳定发现/current 语义 | 30 号 §7.4、§8.6；本地 E2E |

## 2026-08-27 — `POST /series` revision 修复

| 决策 | 理由 | 证据 |
|---|---|---|
| 允许 ready Study 新增 Series，但必须与 Study manifest/revision 在同一请求级事务内推进 | 保留既有接口兼容，同时立即使旧 revision 失效；拒绝所有 ready Study 变更会破坏已有 Image replace/add 的 revision 模型 | `StudyService.create_series()`；`StudyDal.cas_revision()`；`get_async_session()` |
| 只有真正插入新 Series 的请求推进 revision；唯一键竞争或普通幂等重放直接返回既有资源 | 防止相同 `series_key + payload` 重放重复递增 revision；不同 payload 继续 fail-closed | `StudyService.create_series()`；`SeriesDal.create_idempotent()` |
| Series 创建和 Image 变化复用 `_advance_study_revision()` | manifest、completeness、status 和 revision 只能有一个 Service owner，避免两条写路径漂移 | `apps/backend/services/runtime/service/study_service.py` |
| Series 创建先锁 Study，再对 Series key 做 locking current read | 同一 Study 下不同 key 串行各自成功；相同 key 在 MySQL REPEATABLE READ 下也能看到已提交竞争赢家，不把幂等并发误报为 409 | `StudyDal.get_by_id_for_update()`；`SeriesDal.get_by_key_for_update()`；真实 MySQL 并发资格化 |

## 2026-08-27 — `GET /tasks?id=` 轮询合同补齐

| 决策 | 理由 | 证据 |
|---|---|---|
| 在现有 `TaskResponse` 增加四个 nullable 字段，不新建 detail/status 双 DTO | 当前 POST/create、GET/detail、POST/cancel 已共用同一 Response；只增加字段向后兼容，立即满足轮询，不破坏已有 Snapshot/Config 消费方 | `apps/backend/schemas/task.py`；Runtime OpenAPI |
| `current_report_id/started_at/finished_at/next_retry_at` 直接从 ORM 投影，Service 不重复拼装 | 四列已存在于 ORM 和物理表，写入 owner 已在 Report/Execution Service；新增 Service 计算会制造第二真相源 | `models/task.py`；`report_service.py`；`imaging_execution_service.py` |
| 暴露 `next_retry_at` 不等于 Task retry_wait 已实现 | 源码没有 Task `retry_wait/next_retry_at` 写入路径，重试事实当前属于 Stage/Outbox/Attempt | 全仓 Python 搜索；当前 9 个 Task 该字段均为空 |

## 2026-08-27 — `GET /images/page` 分页与版本合同

| 决策 | 理由 | 证据 |
|---|---|---|
| 默认 current 定义为同一 `logical_image_key` 的绝对最新工作流版本，不是“最新 ready 版本” | 上传/替换恢复必须看到 uploading/validating/quarantined 新版本；按 status 回退旧 ready 会把历史版本伪装成 current | `ImageDal.page_for_series()` 的相关 `NOT EXISTS`；真实 v1 ready/v2 uploading 回滚事务 |
| `include_versions=true` 优先于 `current_only`，`current_only=false` 也显式进入历史视图 | 默认参数需要便于调用方恢复 current；历史访问必须 opt-in，但两个显式开关不能产生相互矛盾结果 | `ImagePageQuery.resolved_current_only`；Runtime OpenAPI |
| page 使用独立精简 DTO，并在 ORM 层 `load_only` 对应列 | 详情接口仍需宽合同，但列表不应暴露或读取 object key、storage profile、KMS、validation lease 和大 JSON | `ImagePageItemResponse`；`ImageDal.page_for_series()`；ORM unloaded inspection |
| 首版不新增排序索引或迁移；先在生产等量级大 Series 上资格化 | 当前 EXPLAIN 使用已有 logical-version 索引且无全表扫描，但稳定排序仍 filesort；真实库每个 Series 最大仅 1 条，样本不足以证明大 Series 性能 | MySQL EXPLAIN；`SHOW INDEX image_record`；30 号 §6.11 |

## 2026-08-28 — `GET /tasks/page` 分页与恢复合同

| 决策 | 理由 | 证据 |
|---|---|---|
| 查询必须至少提供 `session_id` 或 `study_id`，不开放调用方全部 Task 的无界扫描 | 该接口服务于已知 Session/Study 的上游恢复；强制 scope 可限制误用、数据暴露面和大范围查询成本 | `TaskPageQuery.validate_page_scope()`；30 号 §7.4 |
| Service 校验 Session/Study owner 与 scope 一致性，TaskDal 再强制 `Task.requester_id` | 历史数据若父级 owner 与 Task requester 漂移，应 fail-closed；两层校验也防止 Session join 被误改后扩大读取范围 | `TaskService.page_tasks()`；`TaskDal.page_for_owner()`；Service scope 合同验证 |
| 分页使用精简 `TaskStatusResponse`，不复用包含 Snapshot/预算/配置哈希的宽 `TaskResponse` | 上游恢复只需要状态、Report pointer、错误码和时间；冻结执行材料不应进入列表响应或 ORM 列加载 | `apps/backend/schemas/task.py`；`TaskDal.page_for_owner()`；OpenAPI 合同验证 |
| 时间输入必须带时区并转换为 UTC naive，排序固定为 `created_at DESC, id DESC` | MySQL 列为 `DATETIME(6)`；边界统一可避免本地时区歧义，二级 ID 排序可在同微秒时间下保持稳定分页 | `TaskPageQuery.normalize_created_at()`；生成 SQL 合同 |
| 首版不新增 Task 分页索引或迁移 | 现有 requester/study/session-created 索引已支持首版小样本正确性；大 Session、多 Study、状态/时间组合尚未等量资格化，当前没有证据支持新增索引 | 真实 MySQL 只读验证；30 号 §7.4；`.agent-handoff/risks.md` |

## 2026-08-28 — `GET /reports/current?task_id=` 当前报告合同

| 决策 | 理由 | 证据 |
|---|---|---|
| Runtime current 查询必须先校验 Task requester，再读取 Report pointer | 不能先投影 Report 再做 owner 校验；Task 不存在与越权统一隐藏为 404 | `ReportService.get_current_for_requester()`；Runtime 错误映射合同 |
| `current_report_id=None` 返回 `data=null`，但非法 pointer 不返回 null | 空 pointer 是合法业务状态；pointer 指向不存在、其他 Task 或不可交付 Report 是数据漂移，伪装为空会隐藏一致性故障 | `ReportService.get_current_for_requester()`；8 场景合同验证 |
| current 只允许 `final/published`，不从 history 推断当前版本 | `void/superseded` 是历史状态；上游不应按 revision 第一条自行猜交付结果 | `GET /api/v1/reports/current` OpenAPI；30 号 §8.6 |
| 本切片不改表、迁移、publish/void 治理或宽 Report view | current 读取可复用现有 Task pointer 与 Report DAL；CAS、reason/actor/audit、稳定医学展示 Schema 是独立问题 | 目标代码 diff；30 号 §8.4-§8.7 |

## 2026-08-28 — Session 与 Task 生命周期联动合同

| 决策 | 理由 | 证据 |
|---|---|---|
| Session 定义为完整诊断会话；`complete` 只在没有非终态 Task 时成功 | 若只按影像接入完成解释，Session completed 可与 queued/running Task 并存，上游无法把会话终态作为稳定恢复边界 | `SessionService.complete_session()`；`TaskDal.list_non_terminal_for_session()`；30 号 §4.3/Slice 6 |
| Session cancel 写 Task 取消请求，不直接强制执行态 Task 为 cancelled | Worker 可能正处于 Provider I/O 或 finalization；强改终态会制造迟到结果覆盖和账务不一致，现有安全边界已消费 `cancel_requested_at` | `TaskService.request_cancellation_for_session()`；`ImagingExecutionService`、`AIRequestService`、`ReportService` 取消门禁 |
| Session 与其非终态 Task 的取消请求在同一事务内原子提交，首次取消请求不被覆盖 | 任一 owner/CAS 冲突都必须整体回滚；first-request-wins 保留稳定的 actor/reason/time 审计事实 | `SessionService.cancel_session()`；`TaskService._request_cancel_locked_task()`；请求级 `get_async_session()` 事务 |
| `POST /tasks` 与 Session complete/cancel 共用 Session 行锁；终态 Session 只允许已有 business key 继续原幂等校验 | 堵住“complete/cancel 检查后又插入新 Task”的竞态，同时不先于原 Snapshot/hash 合同误杀合法重放 | `TaskService.create_task()`；`SessionDal.get_by_id_for_update()` |
| 首版不新增 `cancelling`、pending counter、表字段或迁移 | 现有 Session/Task 状态、取消字段和 state_version 已足以表达取消请求接受与后续 Worker 收敛；新增派生计数会引入第二真相源 | 本切片代码 diff；真实 MySQL 回滚事务验证 |

## 2026-08-28 — D1 逐图 projection/provenance 合同

| 决策 | 理由 | 证据 |
|---|---|---|
| 新 prepare 必须显式传 projection；未知值用 `UNKNOWN`；首版只做 trim、非空和现有 `VARCHAR(64)` 长度校验，不新增医学枚举、大小写转换或字符白名单 | 当前仓库、相邻上游和真实数据没有权威 code 集；Python 从 filename/pixel/body part 猜测会制造医学事实 | projection 只读审计；`schemas/image.py`；29 号 §6.7 |
| provenance 由 Service 写入保留 `technical_metadata_json.projection_provenance`；调用方不能提交该 key | 现有表已有 projection 和 JSON，零迁移即可保存来源；Service-owned namespace 可防 caller 伪造 `dicom_extracted/reviewer_confirmed` | `build_projection_metadata()`；prepare/replace Schema validator |
| 历史缺失只规范成 `UNKNOWN + legacy_unspecified`，不回填旧行、不冒充 caller 声明 | 既保证旧数据参与后续受控 Revision 时不阻塞，也保持来源诚实；数据修正需要单独授权 | `projection_fact_from_image()`；真实库 8/8 NULL 只读结果 |
| 新 canonical manifest 为 `series-image-manifest.v2`；精确保留 pre-D1 builder 只服务旧 v1/v2 Task 重放 | projection/provenance 必须进入 Series hash；直接替换唯一 builder 会让已冻结 Task 全部 mismatch | `build_series_manifest()` / `build_series_manifest_legacy()`；9/9 旧 v2 Task replay 检查 |
| 新 Config v2 Task 冻结 `task-request-snapshot.v3`；Provider v3 只从 ordered_images 取对象事实，不回查 current Image | replacement 后旧 Task 必须继续发送旧冻结对象，否则 Task Snapshot 不是真正不可变证据 | `TaskService._build_request_snapshot()`；`AIRequestService._load_attempt_image_inputs()`；Snapshot-only 定向检查 |
| Prompt 只投影逐图安全 refs，不传 object key；Attempt/Call 使用不含 signed URL 的 `ai-image-receipt.v2` | 模型需要 image id/hash/order/projection 对照，但不需要存储路径；短期 URL 不能持久化 | `_v3_ordered_image_refs()`；`_image_receipt()`；D1 receipt 检查 |
| 不新增 Study projection summary、表、字段或迁移 | Image + canonical manifest + Snapshot 已是唯一事实链；Study summary 会形成双写真相 | 目标 diff；29/30 号 D1 实施记录 |

## 2026-08-28 — D1 legacy/D1 Task Snapshot 兼容选择

| 决策 | 理由 | 证据 |
|---|---|---|
| Config v2 创建 Task 时按 Series stored SHA 选择 Snapshot：全 D1 -> v3，全 legacy -> 现有 v2，mixed/neither -> 既有 mismatch 错误 fail-closed | 允许存量 ready Study 继续运行且不改写历史事实；新 D1 Study 仍冻结逐图对象/projection 血缘 | `TaskService._build_request_snapshot()`；真实 MySQL 5 个 legacy ready -> v2、1 个 D1 ready -> v3 |
| Study 级不新增 legacy/D1 双算法 | `build_study_manifest()` 只聚合 Series 已落库 SHA/count，与 Series item 合同无关；真实 legacy/D1 Study 均已通过同一 resolved hash 校验 | `build_study_manifest()`；真实 Snapshot 构造验证 |
| D1 SHA 继续包含 `object_version_id`，Task create 不回写 Study/Series | 对象版本属于冻结二进制身份；删除会削弱证据，创建 Task 时静默升级 Revision 会把兼容读取变成数据迁移 | `build_series_manifest()`；本轮代码 diff/数据库回滚验证 |

## 2026-08-28 — Provider JSON fence 与发送审计边界

| 决策 | 理由 | 证据 |
|---|---|---|
| 只兼容正文唯一、完整、精确小写 `json` 标签的 Markdown fence；外层只允许空白 | 解决已观察到的传输包装，同时拒绝前后说明、无标签、大小写漂移和多 fence，避免把宽松文本提取器带入医学结果边界 | `schema_validate_result()`；严格正反例测试 |
| fence 解包后仍执行原 `json.loads + Draft202012Validator`，不补字段、不改状态、不推断 projection | fence 是传输兼容，不是结果修复；医学与 projection 事实仍只能来自冻结输入和模型 Schema 输出 | `contracts.py`；fence 后 Schema rejection 测试 |
| 只有确定 HTTP 响应/响应解析失败携带发送 receipt；timeout/network/remote protocol 保持 unknown 且禁止 definite receipt | 已收到确定响应证明本次请求跨过发送边界；不确定传输不能伪造成 definite sent 事实 | `GatewayResponseParseError`、`GatewayDefiniteResponseError`、Worker 分支与 unknown negative tests |
| definite failure receipt 同时写 Attempt 与无 Winner Logical Call，且不保存 signed URL/原始 Provider 正文 | 成功路径已有双层投影；失败路径保持同一审计语义并避免敏感临时 URL 持久化 | `finalize_attempt_failure()`；Attempt/Call 投影测试与真实 D1 receipt 对账 |

## 2026-08-28 — Runtime readiness 平面边界

| 决策 | 理由 | 证据 |
|---|---|---|
| 公共 Runtime `/readiness` 只以主库、Redis、required imaging consumer 判定 `ready` | Evaluation 是独立数据库/Worker 平面；它的故障不应让仍可处理在线影像链的 Runtime 被摘流量，也不应把 Evaluation 连接超时加入公共探针 | `build_runtime_readiness()`；Runtime 定向隔离测试 |
| Provider qualification 继续作为非 required 观察字段，不进入本轮 Runtime `ready` 布尔值 | 当前 provider readiness 仍是静态未实现事实；本轮只修跨平面错误耦合，不顺带新增资格化规则 | `_provider_ready()`；Runtime readiness response |
| Runtime Admin 暂时继续调用聚合 `build_readiness()` | Admin/operations 的分平面 degraded 输出需要单独重构 Evaluation DB 依赖与响应 Schema；本切片不能用删除信息代替该设计 | Admin readiness/operations 现有调用方；后续 backlog |

## 2026-08-28 — AI Control readiness 依赖边界

| 决策 | 理由 | 证据 |
|---|---|---|
| AI Control health 依赖无关；readiness 只检查主库、Control-plane JWT 与条件性 Nacos | 这些是 AI Control 业务路由的真实依赖；Redis/Broker/Evaluation/Provider 属于其他进程或执行平面，不能拖垮控制面部署 Gate | `services/ai_control/readiness.py`；AI Control 路由审计 |
| 以非空 `NACOS_SERVER_ADDR` 表示 Nacos import dependency 已启用；未配置时 optional disabled | 当前没有独立 enable flag，且手工 Prompt 管理不依赖 Nacos；地址存在时 Prompt import 才具备可探测的服务端目标 | `PromptImportService._fetch_nacos()`；配置合同与定向测试 |
| Nacos readiness 对真实 `/v3/client/ai/prompt` 做无数据 OPTIONS 探测并要求 GET capability，不使用版本不稳定的 Console health path | 当前部署的 Console health path 返回 404，而 Prompt Client 路由 OPTIONS 返回 200/`Allow: GET`；探针仍完成登录、网络和真实业务路由验证，也不依赖某条可变 Prompt 是否存在 | `NacosPromptSourceClient.check_prompt_api_readiness()`；真实 capability smoke |
| Prompt 专用 namespace 只由 `NACOS_PROMPT_NAMESPACE_ID` 指向 `image-dev`；不因 Prompt 修正同步覆盖通用 `NACOS_NAMESPACE_ID` | 两者在配置合同中职责不同；Prompt import/readiness 明确优先使用 Prompt namespace，通用 namespace 可能仍由 Config/Discovery 使用 | `PromptImportService._fetch_nacos()`；`_nacos_ready()`；canonical 只读回读 |
| readiness 只检查 JWT verifier 静态合同，不接受或生成测试 token | 探针必须无凭据且不能泄露 Secret；实际 token claim/scope 仍由业务 endpoint 鉴权 | `control_plane_jwt_readiness()`；Control-plane dependency |

## 2026-08-28 — C1.1 医学状态持久化边界

| 决策 | 理由 | 证据 |
|---|---|---|
| Runtime 共享合同分别拥有模型医学四值、持久化五值与 Stage availability 二值；不依赖 Evaluation | 防止多个 Service 各自维护集合，同时保持 Runtime 与 Evaluation 控制面解耦 | `medical_status_contract.py`；Runtime/Evaluation 集合一致性测试 |
| 只接受 `produced + 合法嵌套四值` 与 `not_produced + complete result 不存在` | availability 是 Stage 内部可用性，不是医学判定；任何缺失、未知或冲突都不能被猜测为 `not_produced` | 严格组合矩阵和全部正反例测试 |
| 非法 finalization 在 Report 前复用既有 Stage/Task 失败收敛，错误码只描述合同失败 | 避免生成非法 final Report，同时不新增医学推断或另一套状态机 | `_apply_stage_result()` synthetic negative contract |
| Report 在任何 DAL 访问前校验列状态、content 状态存在且二者一致 | Report 是最终持久化二次防线；同源幂等检查仍继续比较来源和 content hash | `ReportService.finalize()`；DAL-before-failure tests |
| 冻结 Stage v1 继续使用 `produced/not_produced`，Task/Report 只持久化医学五值 | 保持旧 Task 重放与 handler 语义，阻断内部 availability 泄漏到外部医学事实 | 单元 v1 reader test；真实 Task/Report/Stage 对账 |

## 2026-08-28 — P1-A 自动 reconcile scheduler ownership

| 决策 | 理由 | 证据 |
|---|---|---|
| 仓库内唯一 owner 选择独立 Celery Beat singleton，默认关闭 | 仓库和本地运行环境不存在既有 CronJob、平台 scheduler、systemd timer 或 Beat；默认关闭可避免未知生产平台已有 owner 时形成双调度 | 部署/进程/CI 全仓审计；`AI_ATTEMPT_RECONCILE_SCHEDULE_ENABLED=false` |
| Compose 通过独立 `scheduler` profile 显式取得 ownership；外部 scheduler 已存在时必须保持该 profile 关闭 | ownership 是部署决策，不能让普通 API/Worker 副本隐式启动周期发送者 | `docker-compose.yml`；`USAGE.md` |
| Beat entry 显式路由到既有 imaging exchange/queue/routing key，不新增 reconcile queue | 实际 Worker 只消费 `imaging.image.validate`；依赖默认路由会在配置漂移后产生无人消费任务 | `build_ai_attempt_reconcile_schedule()`；schedule contract tests |
| Beat 单例减少重复投递，DB CAS/lease 才是并发与崩溃正确性边界 | scheduler 误重叠、周期短于 lease 或 RabbitMQ 重投仍可能发生；只有持久 CAS 能保证单次 lookup/reschedule | 双 Worker 重叠合同；SIGKILL + lease 到期真实恢复 |
| P1-A 只自动化现有 lookup/reschedule，不新建 Attempt、不重新 POST Provider | unknown 投递结果不能靠替代请求猜测；原 request/idempotency identity 必须保留 | lookup Protocol；真实自动触发后 Call Attempt 数仍为 1、Provider IDs 不变 |
| P1-B unknown 有界终止不并入 P1-A | 默认 lookup 为 unsupported；可靠次数/时长上限需要跨重启持久字段和迁移授权 | 当前 Model/DAL；真实 unsupported 自动重排证据 |

## 2026-08-28 — ms-ai-fast Platform 地址合同澄清

| 决策 | 理由 | 证据 |
|---|---|---|
| 保持 `AI_PLATFORM_OPENAI_BASE_URL + AI_PLATFORM_API_KEY -> GatewayClient` 为 Worker 唯一可执行出站合同 | 这是用户明确要求复制的 ms-ai-fast 运行方式；ms-ai-fast 没有 Connection 冻结表，也不从数据库解析 Provider Secret/endpoint | `ms-ai-fast/app/core/config.py`、`app/service/gateway_client.py`、`app/service/ai_runtime_service.py`；既有 2026-08-26 决策 |
| Connection `base_url` 继续只视为非敏感 Platform 路由/能力元数据，不恢复 Secret Resolver | 当前唯一 validated Connection URL 与 ms-ai-fast Platform URL 一致；Secret 只允许进程注入 | `core/ai/connection_contract.py`；只读 DB/env URL 对照 |
| 把 URL 自动一致性比较列为 P2 硬化，而不是当前 P1 故障 | 当前没有 A/B 错发证据；未注入 Platform 配置时 runtime gate fail-closed。自动比较仍能防止未来部署漂移导致审计元数据失真 | `AIRequestService._runtime_gate_allows()`；当前 Settings/Connection 只读核对 |

## 2026-08-28 — P1-B unknown Attempt 持久有界终止

| 决策 | 理由 | 证据 |
|---|---|---|
| 冻结 `ai-attempt-reconcile.v1 = max_count 3 / max_unknown_age 10800 秒`，同一 v1 拒绝环境漂移 | 默认首次 unknown 约 5 分钟后对账，unsupported 间隔 1 小时；3 小时允许第三次 lookup 正常执行。它是工程 fail-closed 初值，不冒充 Provider SLA | `Settings.validate_ai_attempt_reconcile_policy()`；边界测试；真实 Beat 资格化 |
| Attempt 最小新增 `first_unknown_at DATETIME(6) NULL` 与 `reconcile_count INT NOT NULL DEFAULT 0` | 首次时间和 lookup 预算必须跨进程/重启持久化；`state_version` 是 CAS fencing，`usage_json` 是 Provider 用量，内存计数不可审计 | ORM、DAL、迁移 `20260828_01`；真实 MySQL schema |
| 首次 unknown 只写一次；每个获授权 lookup 在 claim CAS 中原子计数 | 避免重复消息覆盖年龄起点，避免双 Worker、崩溃或重投取得免费 lookup 预算 | `AIRequestService.finalize_attempt_failure()`；`AICallAttemptDal.claim_reconcile_candidate()`；并发/崩溃测试 |
| count/age 使用 `>=` 终止；最后一次 lookup 的可信 `succeeded/failed` 优先，unknown/unsupported 才 unresolved | 上限限制继续等待，不应丢弃已取得的真实 Provider 终态 | Worker unknown 分支与 terminal 分支；等号边界和最后一次 terminal 测试 |
| unresolved 复用既有技术失败链并使用 `provider_result_unresolved` | 这是工程投递结果不确定，不是医学结果；必须 fail-closed 且不产出 final Report | 真实 Task/Stage/Call/Attempt 对账；Report=0 |
| 不创建替代 Attempt、不重新 POST Provider，不新增 HTTP 接口或 queue | unknown 原请求未确认前补发可能重复计费或产生冲突结果；P1-A 既有调度/队列已足够 | replacement POST=0 测试与真实 provider identity 不变 |
| 历史 `first_unknown_at` 不回填；downgrade 有任何 P1-B 事实即阻断 | 既有时间列不能证明首次 unknown 时刻；删除已产生的审计事实不可恢复 | migration upgrade/downgrade guard；迁移前后 15 条 Attempt 对账 |

## 2026-08-28 — P1-C JWT 与 Artifact signing 延期

| 决策 | 理由 | 证据 |
|---|---|---|
| Admin JWT 当前不实施 | 用户已明确暂不考虑管理后台；`ADMIN_SECRET_KEY` 只被 AI Control/Admin scope 和 readiness 使用，不参与 Task→Worker→Provider→Report | `core/dependencies.py`；AI Control endpoints/readiness |
| Artifact signing 当前不实施 | 三个 signing 环境变量只有 Compose 注入占位，生产 Python 主链没有读取；签名函数只存在于 qualification/egress proof 工具 | 全仓非测试引用检索；`core/ai/qualification.py`、`core/ai/egress_proof.py` |
| Runtime JWT 生产密钥生命周期延期，但保留已有 endpoint dependency | JWT 只决定请求者能否进入 sessions/studies/images/tasks/reports，不参与内部执行；删除 dependency 会扩大未授权访问，不属于“延期” | Runtime endpoint scope dependencies；`get_jwt_data/require_*_scope` |
| 当前核心 Worker Runtime 不再受 P1-C 阻断；公网/生产安全单独保持未资格化 | 功能链与访问控制/证据签名是不同完成口径；用户要求先完成链路功能 | 用户决定；源码调用图 |
| 公网、跨团队、管理控制面或合规证据包上线前必须恢复 P1-C | 延期不等于安全放行；届时需要 issuer/audience/key、轮换、撤销、最小注入与历史验证合同 | 当前 key lifecycle 尚不存在 |

## 2026-08-28 — C2 CompleteMedicalResult v2

| 决策 | 理由 | 证据 |
|---|---|---|
| 保留完整 v1，新增显式 `xray_primary_v2/xray_targeted_review_v2`、Stage handler v2 与 `complete-medical-result.v2` | 历史 Task/Config 的冻结 handler、Schema 和 Prompt 不能被原地改写；新结果合同必须通过 Profile/Config 显式选择 | `core/pipeline.py`；`stages/registry.py`；旧 v1 Config 冻结完整性重验 |
| v2 结果的 `summary/impression/findings/coverage/source_refs` 全部由模型输出，Python 只做 Schema 与技术引用校验 | 防止工程层成为第二医学判断器，同时让 Report 和后续 Evaluation 获得稳定字段 | `complete_medical_result.v2.schema.json`；Primary v2 Prompt；`xray_result_contract.py` |
| SourceRef 必须与本次实际发送的脱敏 `ai-image-receipt.v2` 对账 | Snapshot 证明计划发送事实，receipt 证明本次实际发送事实；结果证据引用必须绑定后者，不能只信模型复制文本 | `validate_xray_result_contract()`；Attempt/Call receipt；真实 v2 Task 存储后复验 |
| 技术校验仅覆盖 ID 唯一、引用存在、图片已发送及四个逐图事实一致 | 病种词典、医学一致性、projection 值域和诊断判断属于 Prompt/模型与 M1，不得在 Python 中新增医学规则 | `xray_result_contract.py` 的有限检查集合与负例测试 |
| v2 Profile 必须使用 `task-request-snapshot.v3`，legacy Snapshot v2 继续只服务 v1 | v2 SourceRef 合同需要逐图冻结 `image_id/series_id/projection/manifest`；缺失这些事实时不能伪造可追溯性 | `TaskService._build_request_snapshot()` 的 `task_result_contract_requires_snapshot_v3` 门禁 |
| [SUPERSEDED 2026-08-29] Targeted v2 仅保留本地版本化资产和不可达 handler，不发布 Nacos、不改变固定 `primary_final` 路由 | 这是 C2 当时的范围决策；用户后续明确改为“先补全 Prompt 链并跑通”，新决策见下方全链 Prompt 章节 | C2 历史范围；2026-08-29 用户新优先级 |
| C2 不新增接口、表、字段或迁移 | 现有 Task/Config/Attempt/Call/Report JSON 持久合同足以承载 v2；不为结构化 JSON 冗余扩表 | C2 write set；真实 Config/Task/Report |

## 2026-08-28 — 最小工程全链优先级裁决

| 决策 | 理由 | 证据 |
|---|---|---|
| 第一阶段先固化“上传影像 -> AI -> 第一份 final Report -> 查询”，不把 Evaluation/M1/JWT/signing 打包进来 | 用户明确要求先把工程链跑通；这些能力属于医学发布或生产安全的不同完成口径 | 用户当前目标；`run_e2e_local.py`；真实 Task/Report |
| D2 不再作为 ms-image 下一开发项 | strict clinical context v1 已有 Schema、冻结、Snapshot、Prompt 和 export 全链；重复开发会制造第二合同 | `schemas/task.py`；`task_service.py`；`prompt_commands.py`；`evaluation_export_service.py` |
| C2 保持 `ENGINEERING_QUALIFIED / MEDICAL_ACCURACY_UNKNOWN` | summary/impression 等 v2 结构已经实现且真实跑过；没有 Gold/Scorer/M1，不能提升为医学资格 | v2 Schema/测试；真实 C2 Task |
| Report `state_version` 列为主链固化后立即修复的治理 P0，而不是首份报告生成阻断 | finalize 首次 insert 不使用 Report CAS；publish/void/supersede 明确调用缺失字段的 CAS | `report_service.py`；`crud/report.py`；`models/report.py` |
| 第一阶段建议 `final` 直接可交付，publish 作为独立治理能力等待用户确认 | 当前 current/history 已能读取 final；把损坏的 publish 强塞进最小链会扩大范围且混淆交付语义 | Report endpoint/service 当前合同；用户“先跑通”要求 |
| 优先增强既有 E2E harness，不新增平行测试脚本 | 项目已有完整路径脚本，复用可避免重复入口并符合用户未授权生成测试脚本的约束 | `scripts/dev/run_e2e_local.py`；项目 AGENTS 规则 |

## 2026-08-28 — DeepSeek 最终输出与 14 号架构文档裁决

| 决策 | 理由 | 证据 |
|---|---|---|
| 架构改造级别采用 `local correction（局部修正）`，不重写主链 | 当前 `API -> Service -> DalBase CRUD -> Model/DB`、Outbox/Broker/Worker 和冻结配置链已能产生首份 final Report；主要缺口是启动稳定性、报告 CAS、上游接线、评测和生产安全 | `docs/refactor/14-xray-specialty-design.md`；真实 Task/Report；现有分层源码 |
| 历史 `complete_medical_result.schema.json` 保持冻结，v2 独立演进 | 原地给 v1 增加 summary/impression 会改变历史 Task/Config 的冻结解释；当前已有独立 v2 Schema/Profile/Handler/Config | `xray_result_contract.py`；`complete_medical_result.v2.schema.json`；C2 冻结完整性验证 |
| “链路曾成功跑通”与“当前可确定性复跑”分开裁决 | 当前存在 2 Relay、3 Worker parent，consumer ownership 不唯一；这不推翻历史成功证据，但阻断安全复跑资格 | 2026-08-28 进程只读检查；Runtime `/readiness` 的 consumer_count=3 |
| 当前 Git 改动先分组审阅，不接受一次性整包提交建议 | 约 130 条状态跨多个能力和历史阶段，单次提交难以审计、验证和回滚，也可能误带环境/敏感配置 | `git status --short`；项目脏工作树保护规则 |

## 2026-08-28 — D2 可重复验收后的下一阶段裁决

| 决策 | 理由 | 证据 |
|---|---|---|
| local chain 只由既有 `run_local_chain.sh` 拥有，Beat 在该 launcher 中强制关闭 | 避免新旧 Worker 与重复 scheduler 混跑；scheduler owner 属于独立 P1-A 部署边界 | atomic lock、进程预检、consumer=1、Beat=0 与重复启动/正常退出实测 |
| public E2E 只验收 Runtime 对外 Task/Report 终态，Stage/Attempt/receipt 继续由既有合同测试覆盖 | Runtime 当前不公开这些内部明细；为验收新增调试 API 或直查数据库会扩大产品面并污染公共边界 | `run_e2e_local.py`；D1/D2/C2 定向 172 tests |
| synthetic context 三轮通过只授予 `D2_SYNTHETIC_E2E_QUALIFIED` | 合成事实证明冻结与传递，不证明真实调用方来源、诊断时点或无标签泄漏 | 三轮相同 context SHA；`TaskClinicalContext v1` 与 Snapshot v3 |
| 下一功能切片优先在 `ms-ai-fast` 接真实 `species + clinical_context`，不为 D2 新增 ms-image API | ms-image 的 Schema、冻结、Prompt 消费和查询链已完成；剩余缺口是调用方映射 | 当前 `POST /tasks`；三轮 synthetic E2E |
| `provider_result_source_fact_mismatch` 先作为工程稳定性证据量化，不增加静默重试或 Python 修正 | 现有 fail-closed 正确保护技术血缘；猜测或补写 source refs 会掩盖 Provider 合同失败 | 一次真实失败、随后新批次连续三次成功；`xray_result_contract.py` |

## 2026-08-29 — 猫狗独立 Primary Prompt 决策

| 决策 | 理由 | 证据 |
|---|---|---|
| 新诊断 Task 按 `species` 选择独立 Config，并在 admission 校验 Config/Profile/Prompt 物种绑定 | 只按 Config key 查询不足以防止控制面误绑另一物种 Prompt；这是工程身份校验，不是医学判断 | `task_service.py`；species route/binding 负例测试 |
| common、cat、dog 均 exact-only 且互不 fallback | 物种 Prompt 错配会污染冻结重放与后续医学实验归因；缺 Config 应显式失败 | `prompt_source.py`；Prompt source 组合测试；真实猫狗 active Config |
| 猫狗新 Prompt 本地资产使用版本化 `.md`，历史 `.txt` 不批量改名 | Markdown 便于维护；扩展名不是 Nacos/数据库身份，规范化正文 SHA 才是发布对账边界；历史冻结资产不应因格式偏好重写 | 猫狗 `.md` 文件；Nacos/DB SHA 对账 |
| 狗 E2E 首次 SourceRef 失败后停止资格任务，不静默重跑或回退 common | 计划的 fail-closed 门禁要求保留失败证据；重跑成功也不能解释具体来源字段漂移 | Task `f218a6c...`; error `provider_result_source_fact_mismatch` |
| 若修订狗 Prompt，使用 `3.0.1` 而非覆盖 `3.0.0` | 已发布/导入/激活版本必须保持不可变，才能重放和审计失败 Task | Nacos/Prompt/Config immutable version contract |
| SourceRef 失败按 series ID、projection、manifest SHA 三类独立错误码持久化 | 旧联合错误无法归因；字段类别足以排障且不需要保存 Provider 正文或错误值，不改变技术校验集合 | `xray_result_contract.py`；三类负例与 Gateway receipt 测试 |
| 当前不发布狗 `3.0.1` | 新诊断代码下相同狗 `3.0.0` 连续 4 次 E2E 全部通过，旧失败未复现且无法确定具体字段；无单变量修正证据时发新版本只会制造无效漂移 | 四个 completed Task/final Report；`185 passed` |

## 2026-08-29 — 先补全 Prompt 链、后逐阶段优化

| 决策 | 理由 | 证据 |
|---|---|---|
| 只为 `JointPrimaryReader` 与 `TargetedReview` 配置模型 Prompt；`StudyPreparation/FamilyRouting/DecisionFinalization` 保持确定性 | 后三者处理技术准备、受控路由和持久化定稿，额外模型调用会引入不必要的非确定性和成本 | Pipeline/Stage handlers；猫狗真实 5 Stage 链 |
| 猫狗各使用一份 `4.0.0` 双模式 Markdown Prompt | Primary 和 TargetedReview 需共享同一物种医学核心与 C2 v2 输出合同；是否传入 `PRIMARY_RESULT_JSON` 可以明确区分两种入口 | 猫狗 v4 `.md`；variables/message contract 测试 |
| 完整链只在显式 experiment scope 中开启，global `3.0.0` 保持 Primary-only | 保留历史重放和应用回退路径，防止未经评测的 Targeted 默认放大 | `XRAY_TARGETED_EXPERIMENT_SCOPE_KEY`；Task config selection tests |
| FamilyRouting v2 只验证 Primary 提供的单一候选，不自主选医学 Family/Focus | Python 可验证受控词汇和引用完整性，不应成为第二医学判断器 | `family_routing.py`；正向/非法 focus/引用测试 |
| Targeted 最多一次，并输出新的完整病例结果 | 避免无界路由、Primary/Targeted 拼接、医学投票或“保留更严重结论”的隐式改判 | Config budget=2；Stage 动态插入门禁；真实 2 Call 证据 |
| 冻结已发布 `4.0.0`，下一阶段从 Primary 开始单变量优化 | 没有 Gold/Scorer/分母前继续改 Prompt 无法判断变好或变差；先稳定 Primary 才能归因 Targeted 增益 | 当前 E2E 仅工程资格；Evaluation 与数据真值审计结论 |

## 2026-08-29 — 最终开发架构路线图耐久决策

| 决策 | 理由 | 证据 |
|---|---|---|
| 原 R4 拆分为 R4A DB/metadata/Alembic、R4B Dataset governance、R4C Gold/Scorer、R4D Runtime-equivalent Runner | “已有 Evaluation 接口”不能替代可运行的独立数据库、可信数据、医学评分与真实候选执行；拆分后每个阻断有独立 DoR/DoD/Stop | Evaluation worker/DB/Alembic/Scorer 源码核验；最终路线图 R4A–R4D |
| Evaluation candidate execution 必须复用 Runtime 执行内核与冻结输入合同 | 另写轻量 runner 会形成第二套 Prompt 渲染、Gateway、receipt、Schema 和错误分类，从而使 A/B 与线上不可比 | Runtime Stage/Gateway 与 Evaluation worker 差异；`evaluation-experiment.v1` |
| Targeted 增益采用 same-Prompt A/B | v3 Primary 对 v4 Targeted 会同时改变 Prompt 与 Pipeline，不能归因 Targeted；Control/Candidate 必须使用同一 Prompt source SHA | 最终路线图 R9；Prompt source identity 审计 |
| Retry 固定为三类语义，不以统一重试次数覆盖 | “确定未发送”“已发送但未知”“已返回非法输出”对应不同幂等与医学采样语义；后两类盲目重发会制造重复调用或新医学样本 | Attempt sending 状态审计；最终路线图 R10 |
| R0A baseline manifest、R2 engineering denominator、Evaluation experiment 三类合同先于 Prompt/Model 优化 | 没有代码/配置/数据/执行身份和稳定分母，任何效果变化都不可归因、不可复现、不可发布 | `xray-baseline-manifest.v1`、`engineering-denominator.v1`、`evaluation-experiment.v1` |
| 完整路线图继续采用现有入口内模块化修正 | 当前 Runtime/Service/DalBase/Outbox/Worker/Gateway 可复用；重写或平行服务会扩大事实 owner 和回归面 | 项目 AGENTS 架构约束；源码三链核验 |

## 2026-08-30 — 2–5 图 Runtime 全链与 Postman 命名耐久决策

| 决策 | 理由 | 证据 |
|---|---|---|
| 当前唯一第一阶段目标改为猫/狗真实 X-Ray Runtime 2–5 图 E2E | 用户要求像旧工程阶段一样完整跑通实际链路，不接受先做 Evaluation、医学优化或外围重构 | 用户当前优先级；重建后的完整路线图第 1、3、14 节 |
| 影像数量合同固定为 `N ∈ {2,3,4,5}`，最大 5 张 | 病例可能有 2、3、4 或 5 张；4 张不是固定合同，第 6 张必须 fail-closed | 路线图第 1.1、5、13、14、16 节 |
| 最大 5 张必须在服务端多层门禁，不仅在脚本拦截 | 仅由调用方限制无法阻止其他客户端写入第 6 张，也可能让 Provider 静默截断输入 | Study/Series schema 与现有 E2E 缺口核验；路线图 E1 |
| 不新增主链接口，复用现有 Session/Study/Series/Image/Task/Report API | 当前已有完整公共入口和内部异步职责；新增 Series finalize、Stage execute 等接口会制造第二事实 owner | Runtime 29 个接口与内部 Task/Outbox/Worker 链源码核验 |
| 全部接口使用通俗中文 Postman 展示名称，技术合同仍以方法和路径为准 | Postman 需要让业务与测试人员看懂，但名称不能改变路由、Schema、状态机或幂等语义 | 路线图第 6.1、6.2–6.4、11.7 节 |
| 主链 Postman Item 使用 00–14 顺序，N 图步骤动态展开且最多到 `.5` | 保留旧集合按业务步骤表达的优点，同时修正旧路由、固定 4 图、无轮询和无断言问题 | 旧 Postman 集合只读核验；路线图第 11.7 节 |
| 当时仅交付 Markdown、不生成新的 Postman JSON、测试脚本或迁移；其中 Postman 部分已被用户后续明确授权取代 | 当时用户只要求开发文档；随后用户明确要求基于项目生成 Postman，因此 Collection 可以交付，但测试脚本与迁移仍无授权 | 用户请求时序；项目 AGENTS 生成约束 |

## 2026-08-30 — v3.1 接口、Prompt 与 Postman 最终校正决策

| 决策 | 理由 | 证据 |
|---|---|---|
| 本期接口清单固定为 Runtime 29、Runtime Admin 6、AI Control 31，合计 66 个已实现接口 | 这是当前真实病例 Runtime 主链、报告治理和 AI 控制面所需的已实现边界；接口矩阵必须与源码 OpenAPI 一致 | 三个应用 OpenAPI 静态枚举；路线图 v3.1 接口矩阵 |
| Evaluation Control 不计入本期 66 个接口 | Evaluation 属于后续离线准确率治理，不是 2–5 图真实病例 Runtime E2E 的必经链；混入会模糊当前唯一 P0 | 当前 E0–E8 优先级；Evaluation 仍缺独立 DB/Gold/Scorer/candidate runner |
| Prompt 计数与 Provider Logical Call 计数分开记录 | Prompt 资产数量、Stage 数和实际模型调用数不是同一个概念；每个接口必须能回答同步/异步 Prompt 数和实际 Logical Call 数 | Pipeline Stage handler、Prompt Catalog 与 Gateway 调用链核验 |
| Primary 为 1 Prompt/1 Call；Targeted 无合法 candidate 为 1 Prompt/1 Call，有合法 candidate 为 2 Prompt/2 Calls；每次调用均携带全部 N 图 | 多图是单次多模态请求，不是按图逐次调用；Targeted 只在 FamilyRouting 产生合法候选时追加一次 | JointPrimaryReader、FamilyRouting、TargetedReview、Gateway request builder |
| FamilyRouting、DecisionFinalization、replay 与器官分割均为 0 医学 Prompt/0 LLM Provider Call | 前三者是确定性编排/持久化；分割是独立视觉展示能力，不进入医学诊断 Prompt 或 Report | Stage handlers；分割隔离合同 |
| Postman Collection 固定交付到 `postman/MS-Image X-Ray 2-5图完整诊断链.postman_collection.json` | 需要稳定、可直接导入且与文档互相引用的唯一交付路径 | 用户明确授权；Collection v2.1 静态校验 |
| Postman 的 `runtime_base_url`、`runtime_admin_base_url`、`ai_control_base_url` 只保存 origin，请求自身拼接 `/api/v1/...` | 避免 base 变量与请求路径重复 `/api/v1`，同时适配三个独立服务端口 | Collection 变量与全部 request URL 校验 |
| 写操作默认由 `control_write_enabled=false`、`admin_write_enabled=false`、`broken_report_mutations_enabled=false`、`segmentation_enabled=false` 保护 | Collection 包含控制面与当前已知损坏/未实现能力，默认跳过可防止误写、误取消或把规划接口当成现有功能 | Collection prerequest scripts；接口现状核验 |
| 静态校验 PASS 与真实 Runtime E2E PASS 必须分开报告 | JSON 可导入、OpenAPI 覆盖和请求体可解析只能证明资产一致性，不能证明 OSS/Broker/Worker/Provider/Report 真链运行 | 本轮未启动 Runtime、Relay、Worker、OSS、Provider，也未运行 Runner/Newman |

## 2026-08-30 — v3.2 全项目接口与 canonical Postman 决策

| 决策 | 理由 | 证据 |
|---|---|---|
| 项目真实 HTTP 路由总数固定为 `79`，不是 `66` | `79 = 75` 个版本化 `/api/v1` 接口 `+ 4` 个非版本化 `GET /` 根探针；项目级接口总账必须覆盖四套 FastAPI App | OpenAPI 静态枚举：Runtime 30、Runtime Admin 7、AI Control 32、Evaluation Control 10 |
| `66` 只表示 Runtime 病例工程链直接支撑子集 | Runtime 29、Runtime Admin 6、AI Control 31 是主链、报告治理和配置控制面；该数字不含四个根探针和 Evaluation 9 个版本化接口 | 路线图 v3.2 的“项目总账”与“主链子集”定义 |
| Evaluation Control 的 9 个版本化接口进入项目接口总账，但不进入 Runtime 病例 E2E 必经链 | Evaluation 是离线治理面，不应从项目接口清单中消失，也不能混入 Session→Report 的在线验收路径 | Evaluation OpenAPI；Evaluation endpoint/worker 源码 |
| 当前 Evaluation 为 `0 Prompt/0 Provider Call` | `FakeEvaluationScorer` 不执行 Runtime Prompt、Config、Pipeline、Gateway 或真实 Provider；Evaluation 接口存在不代表 M1/A-B/医学准确率可用 | Evaluation worker/scorer 源码与路线图 R4 资格边界 |
| canonical Postman Collection 固定为 `docs/postman/ms-image-xray-complete.postman_collection.json` | 文件覆盖四套 App 的全部 79 个项目路由，并加入 5 个 OSS PUT 与 12 个多影像槽请求；统一路径避免继续引用旧 v3.1 Collection | v3.2 Collection 静态校验：7 Folder、96 Request、79/79 项目路由 |
| v3.1 的旧 Collection 路径与 `91` Item 统计被 v3.2 取代 | v3.1 未纳入 Evaluation Control 和四个根探针，不能作为“项目全部接口”的最终交付 | v3.1/v3.2 接口差异与新 Collection 统计 |
| 静态资格化不得升级为 Runtime E2E 或医学资格化 | OpenAPI、JSON、参数、鉴权和描述校验只证明资产一致性；未真实执行 OSS、Broker、Worker、Provider，也没有 Gold/医学 Scorer | `STATIC_CONTRACT_QUALIFIED`、`RUNTIME_E2E_NOT_RUN`、`MEDICAL_ACCURACY_UNKNOWN` 三段式结论 |

## 2026-08-30 — v3.3 最终执行路线与 Prompt 事实决策

| 决策 | 理由 | 证据 |
|---|---|---|
| 唯一下一阶段为 `RUNTIME_2_TO_5_IMAGE_DETERMINISTIC_QUALIFICATION` | 当前服务端没有绝对 2–5 图门禁，E2E Harness 仍固定单图，真实猫狗 2/3/4/5 矩阵未运行；先改医学 Prompt 无法区分工程故障与效果变量 | Study/Series schema、Study/Image/AIRequest service、`run_e2e_local.py` 源码审计 |
| 当前 v2 Runtime 的 Prompt 执行单位是 immutable Config 中的一份完整正文 | v2 Worker 直接渲染 `config.prompt_content`；Catalog 编译器只在历史 v1 provider-disabled 兼容路径执行 | `AIRequestService._render_v2_messages`、`_prepare_v1_provider_disabled_call` |
| Catalog 20 个模块不得再描述成当前 v2 单病例运行 Prompt 或发布数量 | 资产库存、Stage 数、Prompt 渲染数和 Provider Logical Call 数是不同口径；混用会制造错误 Nacos/Config/Stage 实现 | `prompts/xray/catalog.zh-CN.json` 与 v2 request path |
| Task Snapshot 不复制完整 Prompt 正文 | 完整 Prompt identity/content/variables/message/model/schema/pipeline 已在 immutable Config；Snapshot 保存引用和 SHA 用于执行前对账 | `TaskService._build_request_snapshot`、`AIConfigRecord`、`AIRequestService` snapshot verifier |
| cat/dog v4 继续使用同物种双模式正文，确定性 Stage 不新建 Prompt | Primary/Targeted 通过 `PRIMARY_RESULT_JSON` 输入分支区分；FamilyRouting 只做确定性 candidate 校验，DecisionFinalization 不创造医学事实 | cat/dog v4 Markdown、Config compiler、Stage handlers |
| E0–E8 后默认路线是 R4A–R4D → M1 → Primary → Targeted → Holdout | 用户目标是工程链稳定后提高医学 Prompt；没有 Runtime 等价 Runner、可信 Gold/Scorer 与基线就开始改 Prompt 无法归因 | 路线图 v3.3 §0.4 与“E0–E8 后的医学效果路线” |
| S0–S6 分割仅为用户显式选择后的可选产品支线 | 分割当前未实现，且不参与诊断或医学 Prompt；不应默认插到工程资格化与医学基线之间 | Segmentation API/Job/Worker/Provider 均不存在；路线图隔离合同 |

## 2026-08-30 — Scheduler owner 与提交边界决策

| 决策 | 理由 | 证据 |
|---|---|---|
| `run_local_chain.sh` 永远不拥有 Celery Beat | 本地 launcher 的职责固定为单 API、Relay、Worker；让环境开关临时增加 Beat 会破坏单一 owner 和进程清理合同 | launcher 对 `AI_ATTEMPT_RECONCILE_SCHEDULE_ENABLED=true` 明确 fail-closed；USAGE 已同步 |
| 仓库 scheduler owner 是独立 Compose `scheduler` Profile，或由外部调度器拥有，二者不可同时启用 | 自动 reconcile 必须有唯一 owner；Compose profile 需要自包含 worker/RabbitMQ 依赖 | default/broker/scheduler/broker+scheduler 四种 Compose 解析均通过 |
| 当前大工作树按核心、工具、文档/handoff 三组显式提交 | 共享文件高度重叠，按文件职责分组可审阅且避免 `git add -A` 混入私钥、旧资产或归档 | cached path/secret 扫描；提交 `c8478e0`、`21f103f` |
| canonical Postman 只提交 `docs/postman/ms-image-xray-complete.postman_collection.json` | 根目录旧 Collection 是 91 Request/v3.1 资产，已被 96 Request/v3.3 canonical 文件取代 | v3.3 路线图与 79/79 路由静态对账 |
