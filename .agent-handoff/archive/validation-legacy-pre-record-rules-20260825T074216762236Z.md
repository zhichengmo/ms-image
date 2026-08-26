# Archived Validation Legacy Pre Record Rules

- Archived at: 2026-08-25T07:42:16.762406+00:00
- Reason: semantic compaction of pre-record-rules validation history to satisfy current-state size limit

## Original Content

| 日期 | 检查 | 结果 | 说明 |
|---|---|---|---|
| 2026-08-19 | 纯目标态与结构最终检查 | `passed` | 禁用词命中 0；10 个轴、5 个 Family、6 种 Prompt role；文档 1448 行、110 个围栏配对，`git diff --check` 与 handoff check 通过。 |
| 2026-08-19 | 医学效果/真实 Provider/数据库验证 | `not run`（未运行） | 本轮仅完善目标设计，没有运行模型、Gold/Failure Bank/Holdout 或真实环境演练。 |

| 2026-08-19 | Git 起始与两次推送 SHA 核对 | `passed` | 起始本地/远端均为 `462d980`；幂等切片远端=`4ac3fff`；Outbox DAL 切片远端=`a2aa0f9`。 |
| 2026-08-19 | `python -m compileall -q app workers` | `passed` | 两个 Evaluation 切片完成后均通过。 |
| 2026-08-19 | `python -m ruff check` 变更代码 | `passed` | Evaluation Model/Schema/Service/DAL 相关检查通过。 |
| 2026-08-19 | Evaluation Job inline fake 幂等验证 | `passed` | 相同 payload 无重复 Artifact/Outbox；dataset/Gold/scorer/experiment/split/denominator/两类 Artifact SHA 漂移均拒绝；竞态失败方无孤儿 Artifact。 |
| 2026-08-19 | Admin OpenAPI 路由检查 | `corrected/passed` | 首次误查 `main.app` 未发现 Admin 路由；改查 `main.admin_app` 后四个 Evaluation 路由全部存在。 |
| 2026-08-19 | Evaluation Outbox inline fake 可靠性验证 | `passed` | 严格消息与禁止额外字段、claim/confirm、retry、dead-letter、expired relay lease reconcile 均通过。 |
| 2026-08-19 | staged AST / diff / Secret / handoff maintenance | `passed` | 两次提交均 `git diff --cached --check`、staged AST、只报告结果的 Secret/.env 扫描通过；maintenance `changed=0 warnings=0 unresolved=0`。 |
| 2026-08-19 | 真实迁移、MySQL/OSS/RabbitMQ、Provider 与医学评测 | `not run` | 未获相应授权；状态继续 `NOT_MIGRATED / NOT_RUNTIME_VALIDATED / MEDICAL_RELEASE_NO_GO`。 |

| 2026-08-19 | Evaluation runtime/Relay/Worker 注册 | `passed` | topology 精确为 `evaluation.v1` / `evaluation.job.execute` / `evaluation.job.dlq` / `evaluation.execute_job`，Celery task 已注册。 |
| 2026-08-19 | Relay 事务边界 inline fake | `passed` | Broker publish 回调断言数据库事务计数为 0，confirm 在新短事务回写。 |
| 2026-08-19 | EvaluationExecutionService inline fake | `passed` | Job claim、Run 创建、四类输出 Artifact、Run/Job 原子完成和版本推进通过。 |
| 2026-08-19 | Evaluation Worker fake Gateway/scorer 链 | `passed` | verified input/sanitization -> fake scorer -> deterministic objects -> Artifact writeback；重复事件返回 already_applied。 |
| 2026-08-19 | fake scorer 双分母与 failure policy | `passed` | technical failure 保持 not_produced；missing 保留；医学条件与 population 分母、coverage/receipt 指标和三类基础 Artifact 通过。 |
| 2026-08-19 | paired A/B 汇总 | `passed` | matching、invalid schedule comparison、unsafe flip、McNemar、cluster bootstrap 和 paired Artifact 通过。 |
| 2026-08-19 | Artifact ObjectRef/写入/漂移 | `passed` | signed URL 等额外字段拒绝；对象复用一致；hash drift 确定性失败。 |
| 2026-08-19 | compile/ruff/import/OpenAPI/staged AST/Secret | `passed` | 16 个代码文件切片全部通过；未暂存 `.env` 或凭据。 |
| 2026-08-19 | 提交与远端 SHA | `passed` | `8a994f75f9b3546e91d1dfee93e2f0284f57d93f` 已推送且本地/远端一致。 |
| 2026-08-19 | provider-disabled 跨在线链、真实迁移/基础设施/医学评测 | `not run` | Evaluation 子链组件 fake 已通过，但 Caller 到 Report 再到 Evaluation 的组合验收及真实环境仍未执行。 |
| 2026-08-19 | 专项核心架构文档无实现代码检查 | `passed` | 未发现 class/def/SQL/伪代码模式；仅保留架构图、责任表、方案比较和设计分析。 |
| 2026-08-19 | 辩证缺陷覆盖 | `passed` | 静默漏诊、自我路由、Prompt 过载、专项目录粒度、多专项限制、失败关闭可用性、医学分母和配置复杂度均有正反分析及重新评审条件。 |
| 2026-08-19 | 外部证据适用范围 | `passed` | DICOM、兽医报告/AI 专业立场、兽医直接研究、人类 VLM/第二读者/自动化偏差、监管和报告指南均区分直接证据、间接类比和不可外推结论。 |
| 2026-08-19 | 专项文档纯目标态与格式 | `passed` | 禁用词命中 0；918 行、6 个 Mermaid 围栏配对，`git diff --check` 通过。 |
| 2026-08-19 | 医学效果与临床放行 | `not run` | 文档评审不能证明准确率、外部泛化、使用者表现或临床可用性。 |
| 2026-08-19 | XRay 单文档合并检查 | `passed` | 14 号文档顶部不再依赖总体设计/完整流程/逐层责任跳转；内嵌总体架构、数据库、模块、完整链路、逐层责任和专项设计。 |
| 2026-08-19 | 单文档结构与纯架构检查 | `passed` | 1144 行、8 个 Mermaid 围栏配对；未发现 class/def/SQL/实现代码模式；禁用词命中 0，`git diff --check` 通过。 |
| 2026-08-19 | 真实运行/医学验证 | `not run` | 单文档合并不改变当前 provider-disabled fake 验收边界，不能证明真实基础设施、Provider 或医学发布。 |
| 2026-08-20 | 六个责任面中文术语统一 | `passed` | 14 号文档总览图、完整链图、责任表和说明统一为中文在前、英文括号保留；`git diff --check` 通过。 |
| 2026-08-20 | 核心术语中文对照检查 | `passed` | 14 号文档新增术语表；Service、Stage、责任面和关键状态均有中文标识，`git diff --check` 通过。 |
| 2026-08-20 | 物种/解剖 Prompt 上下文实现核对 | `passed with documented gap`（通过，已记录缺口） | 当前实现将 species/anatomy_regions 注入安全 Prompt 上下文，Primary 模块由 applicable_family_keys 选择；尚无物种资产选择和区域自动专项推导。 |
| 2026-08-20 | 解剖区域与裁剪边界检查 | `passed` | 14 号文档明确 anatomy_regions 不含裁剪图、坐标或像素；裁剪/分割/标志点独立为技术证据，完整 Study 输入不变。 |

| 2026-08-21 | Worker/Relay healthcheck Ruff/compile | `passed` | `ruff check services/runtime evaluation/replay` 与 `python -m compileall -q services/runtime evaluation/replay` 通过。 |
| 2026-08-21 | Worker/Relay Compose healthcheck 配置 | `passed` | `docker compose --env-file /dev/null config --quiet` 与 broker profile 配置通过；healthcheck 命令保留可配置 heartbeat path。 |
| 2026-08-21 | Runtime 无 Secret import/module discovery | `passed` | 从 `/tmp` 完成 `services.runtime.*` 根路径与容器式 `main`/`workers.*` 导入；未读取仓库 `.env` 内容。 |
| 2026-08-21 | Relay heartbeat/cycle callback fake | `passed` | 临时目录 `touch_heartbeat()` 成功，fake `OutboxRelay.run_forever(on_cycle=...)` 完成一轮并触发 callback；未连接真实 broker/数据库。 |
| 2026-08-21 | Docker 镜像构建 | `blocked` | 本机 Docker daemon 不可用：`Cannot connect to the Docker daemon at unix:///Users/mozhicheng/.docker/run/docker.sock`。 |
| 2026-08-21 | Reconcile 一次性入口核对 | `passed by source inspection` | `ImageReconciler.run_once()` 在 `services/runtime/workers/imaging_worker/reconcile.py` 中由 `_main()` 单次调用；无长驻循环、Compose 服务或内部 scheduler。 |
| 2026-08-21 | Monorepo foundation CI 等价检查 | `passed` | 唯一 Runtime 路径、根旧路径不存在、Ruff、compileall、两种 Compose config 和 workflow YAML 解析通过；未运行 GitHub-hosted Action。 |

| 2026-08-19 | Evaluation DB 代码隔离 | `passed` | 主/Evaluation engine 和 session factory 不同；API/Relay/Worker 使用 Evaluation session，在线 SessionService 仍使用主 session。 |
| 2026-08-19 | 同数据库名失败关闭 | `passed` | 子进程设置相同 `MYSQL_DB`/`MYSQL_EVALUATION_DB` 时导入按预期失败；未发起真实连接。 |
| 2026-08-19 | Exporter 三段事务 inline fake | `passed` | 在线 DB 事务结束后才执行 OSS；Evaluation Job 只在 Evaluation DB 事务中创建。 |
| 2026-08-19 | Exporter 脱敏/幂等 | `passed` | provider-disabled Report 导出为 not_produced/technical_failure；Report 正文未进入 row；相同请求复用对象，不同 payload 触发 hash drift。 |
| 2026-08-19 | Evaluation Export/Detail OpenAPI | `passed` | export、Run detail、Artifact detail 路由存在，ID 使用 query/body，无 `/{id}`。 |
| 2026-08-19 | compile/ruff/staged AST/Secret | `passed` | DB 隔离与 Exporter 两个切片均通过；未暂存 `.env`、signed URL、API key 或凭据。 |
| 2026-08-19 | 提交与远端 SHA | `passed` | `0951b23`、`a1ac869` 均已推送且本地/远端一致。 |
| 2026-08-19 | provider-disabled 跨模块组合链/真实基础设施 | `not run` | Exporter 子链 fake 已通过，但完整 Caller 到 Evaluation Worker 的组合验收及真实 DB/OSS/Broker 仍未执行。 |

| 2026-08-19 | provider-disabled 正向组合链 | `passed` | 实际 TaskService/ImagingExecutionService 完成 Preparation -> disabled Primary -> Finalization -> Report，再经 Exporter/Relay/Evaluation Worker 生成 3 类 Artifact。 |
| 2026-08-19 | 在线事实不变量 | `passed` | Evaluation 前后 Session/Study/Image/Task/Stage/Call/Report/Config fixture 快照一致。 |
| 2026-08-19 | Worker 故障矩阵 A | `passed` | cancel-before-claim、late writeback、Artifact drift、commit crash 后 retry/object reuse。 |
| 2026-08-19 | 故障矩阵 B | `passed` | Report superseded/void/non-current 拒绝、Targeted max_instances=1、Stage/Evaluation lease reconcile。 |
| 2026-08-19 | diagnose Task 入口 | `passed` | replay/primary/targeted Active Profile 创建、report_required/run_mode、相同 request 漂移冲突。 |
| 2026-08-19 | 双 DB/双 queue readiness | `passed` | Evaluation DB/consumer 故障使总 readiness=false；Provider 未资格化不阻塞工程 readiness；API-only 状态保持。 |
| 2026-08-19 | 文档与提交 | `passed` | `d2b6c18`、`fc5f52d`、`1a0646d`、`249c3bb` 已推送且远端一致。 |
| 2026-08-19 | 真实迁移/基础设施/Provider/医学评测 | `not run` | 未获授权或缺少真实证据；保持 NOT_RUNTIME_VALIDATED / NO-GO。 |

| 2026-08-19 | Operational Status 聚合 | `passed` | fake DAL 聚合 Outbox/Stage/Call/Report/Evaluation metrics、age、Artifact drift，不返回资源顶层 ID。 |
| 2026-08-19 | Operational Status API | `passed` | `/api/v1/operations/status` 注册为 admin read 只读接口。 |
| 2026-08-19 | Broker queue/DLQ metrics | `passed` | fake readiness 验证 Imaging/Evaluation message depth、DLQ depth、consumer count 和 AMQP oldest age unsupported。 |
| 2026-08-19 | Evaluation scope 分离 | `passed` | evaluation read/write、admin read/write、AI Config endpoint 的允许/拒绝矩阵通过。 |
| 2026-08-19 | ruff/compile/AST/Secret/推送 | `passed` | `d4082ad`、`c8e9ad2`、`836e72e`、`2fa2a8b` 均已推送，当前远端一致。 |

| 2026-08-20 | Prompt 链源码/设计审计 | `passed` | 审计目标 AIConfig/AIRequest/Stage、旧 Prompt Registry、旧 AI governance、14/15/16 号文档；确认四个 disabled SHA 为占位标签，目标 Bundle 未实现。 |
| 2026-08-20 | Prompt 最小合同文档结构 | `passed` | 17 号文档 819 行，六种 role、版本模型、调用上限、Provider-disabled、编译、验收与停止条件完整，Markdown 围栏平衡。 |
| 2026-08-20 | Prompt 真实 Provider/医学验证 | `not run` | 本轮只冻结设计；未创建 Catalog/Compiler/Bundle、未修改 AI Config/Request、未调用 Provider。 |

| 2026-08-20 | zh-CN Catalog/Compiler | `passed` | checksum、无英文 fallback、Primary canonical Family 顺序、Targeted 单 Focus/单 Strategy、leakage、超预算 fail closed 通过。 |
| 2026-08-20 | AI Config Prompt Bundle | `passed` | Primary/Targeted Config 冻结 Bundle/Schema/model/config/release SHA；raw Prompt 字段、global Targeted、未知 Focus、错误 Schema/max_calls 均拒绝。 |
| 2026-08-20 | provider-disabled 真 Bundle | `passed` | AICall 写入真实编译 zh-CN rendered/schema SHA；四个 placeholder 不再进入新调用路径；Task snapshot 指纹一致。 |
| 2026-08-20 | Prompt P4 真实 Provider/医学验证 | `not run` | 未接真实 Provider、未迁移、未运行真实 DB/OSS/Broker、未运行 Gold/A-B/Holdout。 |

| 2026-08-20 | target-only ORM metadata | `passed` | BaseModel metadata 精确为 10 在线核心 + cursor + 4 Evaluation 表，共 15 张；无 legacy 表。 |
| 2026-08-20 | legacy API/Worker/引用清理 | `passed` | OpenAPI 无 xray legacy 路径；源码 legacy import/reference 归零；legacy Worker/Prompt/AI runtime 文件删除。 |
| 2026-08-20 | target Compose/Settings | `passed` | Compose 无 xray worker 服务；旧 .env-01 键通过 Settings ignore 兼容；legacy config 表面删除。 |
| 2026-08-20 | legacy purge compile/ruff/Secret | `passed` | compileall、ruff、target API、target messaging topology、Compose YAML、staged AST/Secret 检查通过。 |
| 2026-08-20 | 真实 MySQL Drop | `not run` | 未连接真实数据库，未执行 DROP TABLE；仅删除代码/ORM/metadata。 |

| 2026-08-20 | AI/Prompt 控制面文档结构 | `passed` | 19 号文档 1202 行，服务/数据库/Web/API/竞速/Secret/发布/迁移/验证/新会话提示完整，Markdown 围栏平衡。 |
| 2026-08-20 | AI/Prompt 控制面实现 | `not run` | 本轮仅设计；未创建 `ms_image_ai_control`、控制面表、Web、AICallAttempt、真实 Provider 或迁移。 |
