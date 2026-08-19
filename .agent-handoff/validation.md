# 验证历史

| 日期 | 检查 | 结果 | 说明 |
|---|---|---|---|
| 2026-08-18 | `docs/history` 全部 Markdown 分类审查 | `passed`（通过） | 14 份历史文档均有归档/取代状态和当前依据；索引覆盖全部文件 |
| 2026-08-18 | 重构文档本地链接检查 | `passed` | `MISSING_LINKS 0` |
| 2026-08-18 | 设计母文章节锚点检查 | `passed` | 数据库逐表和评测章节锚点全部可解析 |
| 2026-08-18 | Markdown 代码围栏平衡 | `passed` | `UNBALANCED_FENCES 0` |
| 2026-08-18 | Handoff（代理交接）容量和结构检查 | `passed` | `changed=0 warnings=0 unresolved=0` |
| 2026-08-18 | `AGENTS.md` 交接协议标记 | `passed` | 仅一组 START/END 标记 |
| 2026-08-18 | 表数量与完全重构授权一致性 | `passed` | 母文、重构文档和 handoff 均标明 10+4 非上限、内部代码可完全替换，且保留兼容/迁移/回滚边界 |
| 2026-08-18 | XRay 详细流程文档静态检查 | `passed` | 新增 10 个 Mermaid 图块（7 个 flowchart、3 个 sequenceDiagram）；链接缺失 0、围栏不平衡 0、`git diff --check` 通过 |
| 2026-08-18 | 新会话恢复合同审查 | `passed` | 启动提示、snapshot、backlog 和新会话交接一致：有界 P0 后进入 P1；代码重构已授权，迁移/新测试脚本/真实数据库/生产发布未授权 |
| 2026-08-18 | Mermaid（流程图）渲染 | `not run`（未运行） | 环境未安装 `mmdc`；已检查围栏和人工关系，未做浏览器渲染 |
| 2026-08-18 | 业务代码测试/数据库验证 | `not run` | 本轮只改文档和交接文件，没有修改业务代码或数据库 |
| 2026-08-18 | 权威边界与 P1/P2/tenant/OSS 合同交叉检索 | `passed` | 母文、重构导航、计划、交接、详细流程和唯一 Prompt 已同步；历史文档保留原历史表述 |
| 2026-08-18 | 本轮修改文档本地链接检查 | `passed` | `MISSING_LINKS 0`；只检查本轮当前文档，未把历史外链当本地文件 |
| 2026-08-18 | 全仓 Markdown 围栏平衡 | `passed` | `UNBALANCED_FENCES 0` |
| 2026-08-18 | `git diff --check` | `passed` | 无 whitespace error；未跟踪文档另由围栏/链接/内容检查覆盖 |
| 2026-08-18 | Handoff maintenance `--compact-if-needed` | `passed` | `changed=0 warnings=0 unresolved=0` |
| 2026-08-18 | XRay 新开发沟通文档本地链接 | `passed` | `MISSING_LINKS 0` |
| 2026-08-18 | XRay 新开发沟通文档 Markdown 围栏 | `passed` | `UNBALANCED_FENCES 0` |
| 2026-08-18 | XRay 新开发沟通文档 Mermaid 静态结构 | `passed` | 3 个非空 Mermaid flowchart 均有图类型声明 |
| 2026-08-18 | XRay 新开发沟通文档 Mermaid 渲染 | `not run` | 环境仍未安装 `mmdc`，未执行渲染级检查 |
| 2026-08-18 | 新沟通文档 `git diff --check` | `passed` | 无 whitespace error |
| 2026-08-18 | 全仓 Markdown 目标一致性定向审计 | `findings`（发现问题） | 根 README/USAGE/CLAUDE 仍为 MS-Scaffold；当前 XRay 文档内部一致，但与用户最近的 FamilyRouting 必经图存在未冻结决策 |
| 2026-08-18 | Skill 适配性检索 | `passed with no install`（通过/未安装） | 官方 Notion 类 Skill 不适配本地 Markdown 权威治理；公开 GitHub 候选采用度与可信证据不足，继续使用 evidence-driven architecture + agent-handoff |
| 2026-08-18 | `git diff --check`（审计前） | `passed` | 当前工作树无 whitespace error；工作树已有大量用户修改，本轮未回退 |
| 2026-08-18 | Mermaid（流程图）与本地链接完整复验 | `not run`（未运行） | 本轮聚焦语义一致性审计，沿用上一轮静态检查结果；主链确认并修改正文后必须重新执行 |
| 2026-08-18 | Canonical Chain 当前文档交叉检索 | `passed`（通过） | Primary/Targeted 两个 Profile、FamilyRouting 仅实验、Targeted fail closed、Evaluation 候选证据 + 人工审批口径一致 |
| 2026-08-18 | 当前文档本地链接检查 | `passed` | `MISSING_LINKS 0`；检查根入口、Prompt、设计母文、术语表、history 索引和 `docs/refactor/*.md` |
| 2026-08-18 | 当前文档 Markdown 围栏检查 | `passed` | `UNBALANCED_FENCES 0` |
| 2026-08-18 | Mermaid 静态结构检查 | `passed` | 26 个 Mermaid 块均有受支持的图类型声明；未做渲染级检查 |
| 2026-08-18 | `git diff --check` | `passed` | 文档改动无 whitespace error |
| 2026-08-18 | 业务测试/数据库/迁移验证 | `not run`（未运行） | 本轮只修改文档和 handoff，不修改业务实现或真实状态 |
| 2026-08-18 | Handoff maintenance（交接维护） | `passed` | `changed=0 warnings=0 unresolved=0` |
| 2026-08-18 | XRay 逐层责任与设计母文定向核验 | `passed` | Session 状态、Service/表边界、两个 Profile、Targeted fail closed、technical report 和 Evaluation/Control 边界一致 |
| 2026-08-18 | 新逐层文档本地链接检查 | `passed` | `MISSING_LINKS 0`；导航入口均可解析 |
| 2026-08-18 | 当前文档 Markdown 围栏检查 | `passed` | `UNBALANCED_FENCES 0` |
| 2026-08-18 | 当前 Mermaid 静态结构检查 | `passed` | 26 个 Mermaid 块均有有效图类型声明 |
| 2026-08-18 | 业务测试/数据库/迁移验证 | `not run`（未运行） | 本轮只修改文档和 handoff |
| 2026-08-18 | Canonical Chain 跨文档独立审计 | `passed with 2 corrected findings`（通过，修正 2 项） | 默认/Targeted Profile、目标未实现、9a45209a 基线和 reset/clean 口径一致；修正 docs 首页目标库措辞和 01 概览状态 |
| 2026-08-18 | 逐层接口合同完整性检查 | `passed` | 核心 Service/Stage 均包含调用方、接收、约束、成功/失败输出、消费者和落点；Image 按操作矩阵表达，终态按统一输出矩阵表达 |
| 2026-08-18 | Git 基线核验 | `passed` | HEAD=`9a45209a`，`9a45209a..HEAD=0`；27 个已跟踪文件有改动，未跟踪实际文件数在审计时为 149，暂存区为空 |
| 2026-08-18 | `.env` 安全状态检查 | `blocked`（受阻） | `.env` 未跟踪且未被 ignore；只统计 15 个赋值和 3 个敏感类别变量名，未读取值；checkpoint 前必须处理 |
| 2026-08-18 | 业务测试/数据库/迁移验证 | `not run`（未运行） | 本轮仅调整文档与交接状态，不修改业务实现或真实状态 |
| 2026-08-18 | Handoff maintenance（交接维护） | `passed` | `changed=0 warnings=0 unresolved=0`；本轮基线与风险更新后复验 |
| 2026-08-18 | 新会话 Prompt 恢复质量检查 | `passed` | 启动顺序、9a45209a 资产基线、.env/checkpoint、P1A/B/C、Canonical Chain、逐层 I/O 和关闭协议与 handoff/重构文档一致 |
| 2026-08-18 | `AGENT_SESSION_PROMPTS.md` Markdown 围栏 | `passed` | 8 个围栏，配对完整 |
| 2026-08-18 | 业务测试/数据库/迁移验证 | `not run`（未运行） | 本轮仅修改 Prompt、文档和 handoff，不修改业务实现或真实状态 |
| 2026-08-18 | XRay 开发沟通文档结构检查 | `passed` | 388 行；26 个 Markdown 围栏配对完整，Mermaid 块均有有效图类型 |
| 2026-08-18 | XRay 沟通文档链接和源码路径检查 | `passed` | 本地 Markdown 链接与 Preserve/Replace 所列当前源码路径均存在 |
| 2026-08-18 | XRay Canonical Chain 口径检查 | `passed` | 默认链 Primary-only；FamilyRouting/TargetedReview 仅实验；工程状态、医学状态和评测发布边界未混用 |
| 2026-08-18 | P0 `.env` ignore | `passed` | `git check-ignore -v .env` 命中根 `.gitignore`；`.env` 不再出现在 `git status` 候选中 |
| 2026-08-18 | P0 脱敏 Secret 扫描 | `passed with rotation follow-up` | 排除 `.env` 后未发现常见云密钥、Gemini key 或私钥；`.env.example` 敏感值已清空，历史本地凭据仍需持有人轮换 |
| 2026-08-18 | P0 安全文件 `git diff --check` | `passed` | `.gitignore` 与 `.env.example` 无 whitespace error |
| 2026-08-18 | 资产基线 `python -m compileall -q app workers` | `passed` | 当前应用与 Worker Python 源码语法编译通过 |
| 2026-08-18 | 资产基线应用导入与路由装载 | `passed` | `from main import app` 成功，装载 26 条路由 |
| 2026-08-18 | 资产基线全工作树 `git diff --check` | `passed` | 已跟踪差异无 whitespace error |
| 2026-08-18 | P0 Handoff maintenance | `passed` | `changed=0 warnings=0 unresolved=0` |
| 2026-08-18 | 资产 checkpoint 暂存区复核 | `passed` | 175 个资产文件；`git diff --cached --check` 通过，`.env` 未暂存，常见云密钥/私钥扫描零命中 |
| 2026-08-18 | P0 事务边界核对 | `deferred to P1C` | 旧 ingest/technical worker 存在事务期间外部 I/O；不阻止纯数据库 P1A，但禁止直接作为目标 Image Worker |
| 2026-08-18 | P0 身份与授权核对 | `passed for P1` | JWT subject/scope 强校验可复用；目标资源 owner 校验放在 Service，旧 tenant dependency 暂不删除 |
| 2026-08-18 | P0 Broker/Trace/启动核对 | `passed for code implementation` | Broker/readiness/Celery 和 API/Admin 启动入口可装载；TraceEvent 在 AuditSink 资格化前保留，未做真实 Broker 运行验证 |
| 2026-08-18 | P1A Session Python 编译与应用导入 | `passed` | `compileall app workers`、`from main import app`、`SessionService` 导入均成功；应用仍装载 26 条路由 |
| 2026-08-18 | P1A Session ORM/MySQL DDL 合同 | `passed` | `session_record` 17 列；单列 `VARCHAR(64)` 主键、0 FK、0 Enum、0 tenant；唯一约束和双索引符合母文 |
| 2026-08-18 | P1A Session Schema UTC 归一 | `passed` | 带时区 `started_at` 可解析并归一为 UTC naive DATETIME；额外字段拒绝 |
| 2026-08-18 | P1A Session 分层边界 | `passed` | Service 无 SQLAlchemy select/update/delete；数据库访问集中在 `SessionDal(DalBase)` |
| 2026-08-18 | P1A Study+Series Python 编译与应用导入 | `passed` | `compileall app workers`、应用和 `StudyService` 导入成功；路由数量保持 26 |
| 2026-08-18 | P1A Study+Series ORM/MySQL DDL 合同 | `passed` | 两表均为单列 opaque 主键、0 FK、0 Enum、0 tenant；唯一约束和索引按母文定义 |
| 2026-08-18 | P1A Study 稳定 source ID | `passed` | 未提供上游 ID 时完整规范创建载荷生成稳定 ID；载荷变化会改变 ID，长度不超过 128 |
| 2026-08-18 | P1A Study+Series 分层边界 | `passed` | 只有 `StudyService`；Service 无直接 SQL，Study/Series 分别使用对应 `DalBase` DAL |
| 2026-08-18 | P1A Image Python 编译与应用导入 | `passed` | `compileall app workers`、应用和 `ImageService` 导入成功；路由数量保持 26 |
| 2026-08-18 | P1A Image ORM/MySQL DDL 合同 | `passed` | `image_record` 43 列；单列 opaque 主键、0 FK、0 Enum、0 tenant；6 组目标索引与双唯一约束已定义 |
| 2026-08-18 | P1A Image Schema 合同 | `passed` | direct/multipart 互斥字段、UTC expiry、original 无 source manifest、derived 必须有 lineage 均 fail closed |
| 2026-08-18 | P1A Image 分层边界 | `passed` | Service 无直接 SQL；版本查询、创建与 CAS 均由 `ImageDal(DalBase)` 完成，未接 OSS/Broker |
| 2026-08-18 | P1B API Python 编译与 OpenAPI | `passed` | 应用导入成功；OpenAPI 共 27 个 path，其中 8 个为目标 Session/Study/Series/Image 非存储路径 |
| 2026-08-18 | P1B ID 路由合同 | `passed` | 新目标 API 无路径参数；资源 ID 仅使用 `?id=` query 或 request body |
| 2026-08-18 | P1B 认证与 DI | `passed` | 新 resource context 依赖已验证 JWT subject/scope，不要求目标表 tenant；API 仅注入 Service，旧 tenant XRay 路由保持不变 |
| 2026-08-18 | P1B 不可用接口门禁 | `passed` | Gateway/Outbox 未到位前未注册 Image prepare/complete/replace 或 Study finalize，避免假闭环 |
| 2026-08-18 | P1C Gateway 编译与兼容导入 | `passed` | `compileall app workers`、应用、`ObjectStorageGateway` 和旧 `OSSObjectStore` 导入成功；旧调用符号保留 |
| 2026-08-18 | P1C Gateway namespace/安全合同 | `passed` | 新 key 为 `image/{image_id}/{generation}/source.{format}`；拒绝 URL/绝对/遍历 key，上传 URL 和 multipart session 不进入 repr |
| 2026-08-18 | P1C Gateway 内存行为验证 | `passed` | fake OSS 下 direct PUT、HEAD、流式 SHA256/size、PNG 格式、version 和二次 HEAD 变化检测通过；未访问真实 OSS |
| 2026-08-18 | P1C Gateway ETag 边界 | `passed` | ETag 仅用于 multipart manifest 和对象变化检测；完整 ObjectRef SHA256 来自服务端流式 bytes |
| 2026-08-18 | P1C Image Outbox Python 编译与应用导入 | `passed` | `compileall app workers`、应用、`ImageService` 和 `OutboxDal` 导入成功；应用装载 36 条路由 |
| 2026-08-18 | P1C Outbox ORM/MySQL DDL 合同 | `passed` | `outbox_record` 22 列；单列 opaque 主键、0 FK、0 Enum、0 tenant；唯一事件键和三组目标索引符合母文 |
| 2026-08-18 | P1C Outbox 消息合同 | `passed` | canonical JSON hash 对字段顺序稳定；已有事件的 event key/owner/version/message version/trace/hash 会完整自校验，篡改 event key 被拒绝 |
| 2026-08-18 | P1C Image complete 事务边界 | `passed by static contract` | `ImageService` 只经 `ImageDal/OutboxDal` flush，request `AsyncSession.begin()` 负责同事务提交；Service 无直接 SQL，未在 API 内发布 Broker |
| 2026-08-18 | P1C Image Outbox 真实 DB/Broker | `not run` | 未获授权创建迁移或连接真实 MySQL/Broker；当前仅为代码与内存合同验证 |
| 2026-08-18 | P1C Relay Python 编译与兼容导入 | `passed` | `compileall app workers`、应用、旧 `TransactionalOutboxRelay` 和目标 `OutboxRelay` 导入成功；应用仍装载 36 条路由 |
| 2026-08-18 | P1C Relay 事务边界与状态行为 | `passed in memory` | fake session/DAL 覆盖 published、retry_wait、attempt exhausted dead-letter、Broker accepted/DB confirm conflict、invalid message dead-letter；publisher 调用时无活动 DB TX |
| 2026-08-18 | P1C Relay Celery 白名单投递 | `passed in memory` | task ID 使用 Outbox ID；queue/routing/exchange 为 imaging 独立 topology；body 仅含 image ID/version/trace，header 仅含 message version/trace |
| 2026-08-18 | P1C Relay 旧 XRay 兼容 | `passed by import` | 旧 `workers.xray_accuracy_worker.outbox_relay` 继续构造 `TransactionalOutboxRelay`；未修改旧 tenant DAL 合同 |
| 2026-08-18 | P1C Relay 真实 Broker/MySQL | `not run` | 未授权真实数据库或 RabbitMQ 演练；Broker confirm、lease 时钟和多进程竞争仍未运行验证 |
| 2026-08-18 | P1C Relay 远端 SHA 实时确认 | `blocked` | 本地 HEAD 与 remote-tracking ref 均为 `c4fe4c7415f70302d3be1f7c851a67280d1095fb`；SSH 22 端口不可访问，HTTPS 无法解析 `github.com`，故 `git ls-remote` 未能实时确认远端并停止下一切片 |
| 2026-08-18 | P1C Relay 远端 SHA 重试 | `passed` | 网络恢复后 `git ls-remote --heads origin codex/ms-image-refactor` 返回 `c4fe4c7415f70302d3be1f7c851a67280d1095fb`，与本地 HEAD 完全一致，门禁解除 |
| 2026-08-18 | P1C 基础 Python 编译与应用导入 | `passed` | `compileall app workers`、manifest/显式 session/ImageDal/StudyService 导入成功；应用仍装载 36 条路由 |
| 2026-08-18 | P1C canonical manifest | `passed in memory` | 输入顺序变化保持相同 SHA；Series/Study 稳定排序、空 Series 摘要和重复 ready logical key conflict 均验证通过 |
| 2026-08-18 | P1C Image validation lease 基础 | `passed in memory` | fake DAL 验证 claim 强制刷新 readback、lease owner/generation 条件和 terminal state_version 推进；未连接真实 MySQL |
| 2026-08-18 | P1C Study revision 重算基础 | `passed in memory` | fake DAL 下 2 个 ready Image 确定性重算 Series count/manifest，并将 Study revision 1->2、completeness=complete、status=validating |
| 2026-08-18 | P1C Worker task 注册门禁 | `passed` | `workers/imaging_worker` 中仍无 Celery task decorator，基础切片不会消费已发布消息 |
| 2026-08-18 | P1C Image Worker Python/任务注册 | `passed` | `compileall app workers` 和应用导入成功；`imaging.validate_image` 已注册到 imaging Celery app，应用路由仍为 36 条 |
| 2026-08-18 | P1C Image Worker Outbox 合同 | `passed in memory` | event ID/event key、aggregate/version、message hash/version、header trace 均复核；篡改 message version 被拒，终态重复消息返回 already_applied |
| 2026-08-18 | P1C Image Worker 事务边界 | `passed in memory` | fake session/Gateway 断言对象校验时活动 DB TX 为 0；claim 和 terminal 分属短事务，Study conflict 后释放原 lease 重试 |
| 2026-08-18 | P1C Image Worker 失败分类 | `passed in memory` | ready、确定性 hash mismatch -> quarantined、下载失败 -> retry、重复消息、Study revision conflict -> retry 均覆盖 |
| 2026-08-18 | P1C Image Worker 静态检查 | `passed` | Ruff、diff check、Service/Worker 导入均通过；Worker/消息未包含 signed URL、access key 或 Secret 字段 |
| 2026-08-18 | P1C Image reconcile Python/Ruff | `passed` | reconcile、Gateway error normalization、ImageDal/Service 编译和 Ruff 通过；应用仍装载 36 条路由 |
| 2026-08-18 | P1C Image reconcile 状态行为 | `passed in memory` | fake session 覆盖 expired lease recovery、published event 重放、过期 upload accepted/missing 和指定 ready drift invalidated |
| 2026-08-18 | P1C Image reconcile 事务边界 | `passed in memory` | fake Gateway 断言 upload HEAD 与 ready 完整校验时活动 DB TX 均为 0；状态更新使用新短事务 |
| 2026-08-18 | P1C OSS missing 分类 | `passed in memory` | fake OSS `NoSuchKey` 被归一为稳定 `object_not_found`，未暴露 SDK 详情 |
| 2026-08-18 | P1B direct prepare Python/OpenAPI | `passed` | compile/import 成功；新增 `POST /api/v1/images/prepare-upload`，应用路由从 36 增至 37，响应为 `GenericResponse[ImageUploadTicket]` |
| 2026-08-18 | P1B direct prepare 事务边界 | `passed in memory` | fake DB/Gateway 断言 Service 创建行时 TX 活跃、生成 signed PUT grant 时 TX 为 0 |
| 2026-08-18 | P1B direct prepare 幂等/owner | `passed in memory` | 服务端生成 `image/{image_id}/{version}/source.png`；同 uploading 载荷返回同 ID/key，载荷变化冲突，ready logical key 要求 replace |
| 2026-08-18 | P1B direct prepare 安全门禁 | `passed in memory` | signed URL 从 repr 隐藏且无持久化字段；MP4 和超过 64 MiB 请求在 Schema 层 fail closed |
| 2026-08-19 | P1B multipart/complete/abort | `passed in memory` | fake DB/Gateway 覆盖 initiate、part signing、complete、abort、bind 失败补偿；全部 OSS I/O 在 TX 外，part/session URL 从 repr 隐藏 |
| 2026-08-19 | P1B multipart 幂等合同 | `passed in memory` | 规范 part-manifest SHA 写入技术元数据；重复 complete 的 manifest 漂移被拒；NoSuchUpload abort 幂等成功 |
| 2026-08-18 | Mermaid（流程图）渲染 | `not run`（未运行） | 环境没有使用 Mermaid CLI；本轮只做围栏和静态图类型检查 |
| 2026-08-18 | 业务测试/数据库/迁移验证 | `not run`（未运行） | 本轮只修改沟通文档和 handoff，不修改业务实现或真实状态 |

## 记录规则

- 记录已运行、失败和有意未运行的验证。
- 失败只写简明原因和下一动作，不粘贴长日志。
- 文档结构通过不代表目标代码、数据库或医学准确率已经通过。
