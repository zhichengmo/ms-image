# 验证历史

## 记录规则

- 只保留当前阶段和下一阶段仍有决策价值的验证；早期完整历史见归档。
- 代码、运行时和医学验证分别报告；Mock、静态检查和单次模型请求不能代替完整 Worker 或医学放行。

## 2026-08-26 — 猫狗统一继承方案复核

| 检查 | 结果 | 结论边界 |
|---|---|---|
| `python -m ruff check`（6 个本轮 XRay 代码/合同测试文件） | 通过 | 静态检查通过。 |
| `python -m compileall -q`（4 个 XRay 生产文件）与 `git diff --check` | 通过 | 语法及 diff 空白检查通过。 |
| 真实上游 `session_id -> medical_record -> pet_profile -> species -> POST /tasks` | NOT RUN | 当前只验证 ms-image 下游冻结边界；不能声称宠物档案继承已经真实集成。 |
| MySQL -> Outbox -> Broker -> Worker -> OSS -> Platform -> Provider -> Attempt -> Stage -> Report | NOT RUN | `RUNTIME_QUALIFIED` 仍未取得。 |


## 2026-08-27 — 统一服务数据库分析验证

| 检查 | 结果 | 结论边界 |
|---|---|---|
| 只读复核 `ms-image` Session/Study/Task/Outbox/Stage/AI Call/Attempt/Report Models、Task Schema/Service 与 21/24 号设计锚点 | PASS / ANALYSIS ONLY | 确认当前 Task 是 Study 强耦合的影像合同；共享 Runtime 与影像输入域可分离。 |
| 只读复核 `ms-ai-fast` Base/SessionRecord/MedicalRecord/AiTask/AiTaskAttempt/FileAsset/ReportContent/PetProfile Models 与 MedicalRecordService | PASS / ANALYSIS ONLY | 确认 BIGINT/FK/TINYINT 遗留结构、消息表语义、业务/投递混合 Task 和 Worker 执行尝试语义。 |
| 代码检查、测试、迁移、DDL、真实 Runtime | NOT RUN | 本轮没有业务代码或数据库变更，不生成测试/迁移，不宣称运行资格化。 |


| 2026-08-27 统一表名/字段命名复核 | PASS / ANALYSIS ONLY | 只读对比两个仓库 Models；未运行代码测试、迁移、DDL 或真实 Runtime。 |

| 2026-08-27 | XRay canonical Prompt 本地检查 | PASS | `PromptRenderer.validate_template`；cat/dog × primary/targeted 四种渲染；Schema `$schema` 字面量保留；变量集合精确为 `SAFE_STUDY_CONTEXT_JSON,OUTPUT_SCHEMA_JSON`；正文 SHA-256 `4443ed48053c0d4212d7826d9f435843742a2adda90bb40b328661b427f28e0a`。 |
| 2026-08-27 | Nacos `ms-image.x-ray.primary.common.zh-CN@1.0.0` 发布与精确回读 | PASS | 指定 namespace 发布成功；回读正文 4291 字符、SHA-256 与本地一致、变量集合一致、`output.format=json`、输出 Schema 一致。控制面导入/Config 激活/Worker/Provider/医学验证 NOT RUN。 |

## 2026-08-27 — Prompt inventory / input-output contract

| Scope | Command / Evidence | Result | Notes |
|---|---|---|---|
| Primary/Targeted Prompt input rendering | inline Python: `normalize_imported_prompt -> PromptRenderer.render -> PromptMessageAssembler.assemble` | PASS | Primary 两变量与 Targeted 三变量均无残留占位符；Targeted 为单条 user message。 |
| XRay output schema asset | Python `json.loads(prompts/xray/complete_medical_result.schema.json)` | PASS WITH GAP | JSON 合法且顶层 strict；嵌套 finding/coverage/source_refs/targeted_candidate 仍为宽合同，尚未医学资格化。 |
| Existing Prompt/control contracts | `python -m pytest -q apps/backend/tests/test_ai_prompt_control_plane_contracts.py` | PASS | `43 passed, 1 warning`；warning 为已有 Pydantic deprecation。 |
| Prompt whitespace | `git diff --check` | PASS | 未发现 whitespace error。 |
| Real Nacos/DB/OSS/Broker/Worker/Provider/medical evaluation | NOT RUN | NOT RUN / UNKNOWN | 新 Targeted 文件仅是本地不可达候选，不能冒充 Runtime 或医学放行。 |


## 2026-08-27 — 全项目 AI 能力文档校验

| 检查 | 结果 | 说明 |
|---|---|---|
| 文档结构与必需状态标识检查 | PASS | 包含 `MS_IMAGE_CORE_AI_NETWORK_CHAIN_PASSED`、`FULL_WORKER_RUNTIME_NOT_QUALIFIED`、`MEDICAL_ACCURACY_UNKNOWN`、`MEDICAL_RELEASE_NO_GO` |
| Primary Prompt 输入变量检查 | PASS | 精确为 `SAFE_STUDY_CONTEXT_JSON`、`OUTPUT_SCHEMA_JSON` |
| Targeted Prompt 输入变量检查 | PASS | 精确为 `SAFE_STUDY_CONTEXT_JSON`、`PRIMARY_RESULT_JSON`、`OUTPUT_SCHEMA_JSON` |
| 输出 Schema 基础合同检查 | PASS | JSON 可解析；顶层 object、`additionalProperties=false`、四类 `medical_status` 枚举符合预期 |
| 关键源码路径存在性检查 | PASS | Pipeline、Stage、Prompt Source、AIRequest、Signer、Attempt Lookup、Evaluation 路径均存在 |
| `git diff --no-index --check /dev/null docs/refactor/25-ms-image-complete-ai-capability-inventory.md` | PASS | 修正更新时间行尾空格后通过 |
| DB / OSS / Broker / Provider / 医学验证 | NOT RUN | 本轮是本地文档盘点，不把静态检查误报为真实 Runtime 或医学资格化 |

## 2026-08-27 — AI 能力盘点与 Primary 缺口文档校验

| 检查 | 结果 | 说明 |
|---|---|---|
| 两份文档源码引用存在性与显式行号范围检查 | PASS | 检查 43 个唯一引用；无缺失文件或越界行号。 |
| `git diff --no-index --check /dev/null <document>` | PASS | 两个 untracked Markdown 文件均无 whitespace error。 |
| Markdown fence 成对检查 | PASS | 25 号 190 个 fence；26 号 76 个 fence；均为偶数。 |
| Provider 原始响应合同复核 | PASS | 文档只允许“不持久化原始正文/不得恢复加密 OSS”；`response_object_ref_json` 仅作为未写入的遗留字段记录。 |
| 数据库/Nacos/OSS/Broker/正式 Worker/Provider/医学验证 | NOT RUN / UNKNOWN | 本轮为本地文档盘点与静态核验，不构成 Runtime 或医学资格证据。 |


## 2026-08-27 — Primary 控制面激活与安全收口验证

| 检查 | 结果 | 说明 |
|---|---|---|
| canonical Nacos Prompt 精确读取 | PASS | `ms-image.x-ray.primary.common.zh-CN@1.0.0`；正文 SHA-256 `4443ed48053c0d4212d7826d9f435843742a2adda90bb40b328661b427f28e0a`。 |
| Prompt/Connection/ModelPool/Config Service 链 | PASS | 真实建立并激活 `xray_diagnose/global/global@1.0.0`；控制面 9 条 Audit 均为 succeeded。 |
| Secret 安全回读 | PASS | 兼容列为空；API/Connection SHA/Config Snapshot/Audit 无 Secret；未输出或持久化 API Key。 |
| `ruff check <7 files>` | PASS | All checks passed。 |
| `python -m compileall -q <7 files>` | PASS | 无输出，退出码 0。 |
| `git diff --check` | PASS | 无 whitespace error。 |
| `pytest -q apps/backend/tests` | ENVIRONMENT ERROR | 首次系统 pytest 未设置仓库根 `PYTHONPATH`，收集阶段 `ModuleNotFoundError: apps`；未执行测试用例。 |
| `PYTHONPATH=. pytest -q apps/backend/tests` | PASS | `91 passed, 19 warnings`；warnings 为既有 Pydantic 与 `datetime.utcnow()` deprecation。 |
| 正式 Worker/同一冻结 Task/Provider 外部 OSS 读取/医学验证 | NOT RUN / UNKNOWN | 不得把控制面激活或单元测试误报为完整 Runtime 或医学放行。 |
| `maintain_handoff.py --compact-if-needed` | PASS WITH MAINTENANCE | `changed=2 warnings=1 unresolved=0`；轮转 1 个旧 work-log section，更新 archive；无未解决错误。 |

## 2026-08-27 — XRay Primary 正式 Worker happy-path 验证

| 检查 | 结果 | 说明 |
|---|---|---|
| 旧 Stage lease recovery | PASS | 现有 Service 首次 `requeued=2/conflicted=0`；HTTP 400 Task 收敛 failed；deadline Task 达恢复上限后 `dead_letter=1`。 |
| 正式 Worker Platform 配置注入 | PASS | 仅从 `ms-ai-fast/.env` 注入 `AI_PLATFORM_OPENAI_BASE_URL + AI_PLATFORM_API_KEY`；不打印值，不写 DB/Nacos/Snapshot。 |
| 同一冻结 Task 全链 | PASS | `task_id=7c37b9b659bb4b8e98b6a6076923c985`；MySQL → Outbox → RabbitMQ → Worker → OSS → Platform/Provider → Attempt/Call → Stage → Report。 |
| OSS/影像事实 | PASS | Study/Series/Image 均 ready；manifest/content SHA 与对象键存在；数据库未持久化对象 URL。 |
| Provider/Attempt/Call | PASS | HTTP 200；Call/Attempt succeeded；Provider Request ID、response SHA、parsed result 存在；`response_object_ref_json` 为空。 |
| Stage/Report/Outbox | PASS | 3 Stage completed；Report final/content SHA 存在；3 Outbox published 且 Broker message ID 存在。 |
| Task Snapshot Secret 扫描 | PASS | `secret/secret_ref/api_key/authorization/access_key/token/password/signed_url` 路径为空。 |
| `ruff check <9 files>` | PASS | All checks passed。 |
| `compileall <8 files>` | PASS | 退出码 0。 |
| `PYTHONPATH=. pytest -q apps/backend/tests/test_ai_gateway_attempt_contracts.py` | PASS | `45 passed, 19 warnings`。 |
| `PYTHONPATH=. pytest -q apps/backend/tests` | PASS | `91 passed, 19 warnings`。 |
| `git diff --check` | PASS | 无 whitespace error。 |
| duplicate/cancel/unknown/late-result 真实环境 | NOT RUN | 单元合同存在，但不能替代真实 Broker/Provider 恢复资格化。 |
| 医学验证 | UNKNOWN | 未运行 Gold、Failure Bank、Paired A/B 或 Holdout；生成 Report 不等于医学正确。 |

## 2026-08-27 — XRay Primary Duplicate Delivery 真实验证

| 检查 | 结果 | 说明 |
|---|---|---|
| 环境非敏感预检 | PASS | 主 MySQL 与 RabbitMQ 坐标存在；`ms-ai-fast/.env` 的 AI Platform 成对配置存在；未输出配置值。 |
| duplicate 输入 | PASS | 原 JointPrimaryReader Outbox `806bf09dbbb74d55aa3f72688608ef83`，相同 message/version/trace/task identity。 |
| 真实 Broker/Worker 重投 | PASS | 隔离 topology `imaging.qualification.duplicate.20260827`；Worker 收到并约 29ms 成功确认。 |
| 幂等数据库证据 | PASS | Task 仍 `completed/state_version=7`；3 个 Stage 仍 `completed/state_version=1`；Call/Attempt/Report 数量仍 `1/1/1`。 |
| 内容与 Winner 不变 | PASS | Call/Attempt ID、Winner、response SHA、Stage output SHA、Report ID/content SHA 均与重投前一致。 |
| 网络副作用 | PASS | completed Stage 在 claim 边界返回，不进入 Prompt/OSS/Platform/Provider；无新 Attempt 即无第二次 Provider POST。 |
| 运行资源清理 | PASS | Worker warm shutdown；隔离 queue、DLQ、exchange、DLX 删除；无残留 imaging 资格化进程。 |
| 业务代码/Schema/迁移 | NOT CHANGED | 本切片只更新 handoff；未修改业务代码、表、字段或迁移。 |
| cancel/unknown/late-result | NOT RUN | 后续恢复切片；因此 `FULL_WORKER_RUNTIME_NOT_QUALIFIED`。 |
| 医学验证 | UNKNOWN | 未运行 Gold、Failure Bank、Paired A/B 或 Holdout。 |

### 验证命令更正记录

- 首次非敏感配置探针误用不存在的 `Settings.MYSQL_DATABASE`，命令失败；改用当前真实字段 `MYSQL_DB` 后 PASS。该失败不是数据库连接失败。
- 首次 Attempt 基线探针误用 `call_id` 过滤字段，命令失败；改用当前 Model 字段 `ai_call_id` 后 PASS。该失败未写数据库。
- `git diff --check`：PASS。
- `maintain_handoff.py --compact-if-needed`：`changed=2 warnings=1 unresolved=0`，轮转一个旧 work-log section；随后 `--check`：`changed=0 warnings=0 unresolved=0`。

## 2026-08-27 — XRay Primary cancel-before-provider 真实验证

| 检查 | 结果 | 说明 |
|---|---|---|
| 修改范围 | PASS | 仅修改 `imaging_execution_service.py` 与现有 `test_ai_gateway_attempt_contracts.py` 的本切片逻辑/测试；无表、字段、迁移、配置或新 Service。 |
| 定向取消合同 | PASS | 6 个取消/迟到相关合同测试通过；包含 queued cancellation convergence 和 cancelled duplicate delivery。 |
| backend 全量测试 | PASS | `PYTHONPATH=. python -m pytest -q apps/backend/tests`：`93 passed, 20 warnings`；warning 为既有 Pydantic/`datetime.utcnow()` deprecation。 |
| 静态与语法 | PASS | 目标 Ruff、compileall、`git diff --check` 均通过。 |
| 真实输入 | PASS | Task `ef0c8b9935f543aa8f70b63f267c73b0`；Stage `b614c6f51039490786f9fef206bcc55d`；Outbox `a3d3c31b667d4f49a77ad6ba170ef06c`；取消在消费前独立提交。 |
| 真实 Broker/Worker | PASS | 隔离 topology `imaging.qualification.cancel.20260827t061156z`；第一次消费约 29ms，重复投递约 7ms，均成功确认。 |
| Task/Stage 收敛 | PASS | Task=`cancelled/state_version=2/ai_medical_status=not_produced`；Stage=`cancelled/state_version=1/error_code=task_cancelled`；finished facts 存在且无 lease owner。 |
| Outbox | PASS | `publish_status=published`，Broker message ID 等于原 event ID。 |
| 网络前置事实 | PASS | Call/Attempt/Report=`0/0/0`；Worker 未注入 AI Platform 配置且仍安全完成；claim 返回发生在 OSS/Platform/Provider 边界之前。 |
| cancelled duplicate | PASS | 相同 event identity 重投后 Task/Stage 版本、状态、错误码、Outbox 和 `0/0/0` 计数完全不变。 |
| 资源清理 | PASS | Worker warm shutdown；隔离 queue、DLQ、exchange、DLX 删除；无本切片残留进程。 |
| late-result / unknown / JWT / Artifact signing | NOT RUN | 仍不得声明完整 Worker Runtime 已资格化。 |
| 医学验证 | UNKNOWN | 未运行 Gold、Failure Bank、Paired A/B 或 Holdout；`MEDICAL_RELEASE_NO_GO`。 |


## 2026-08-27 — unknown Attempt lookup/reconcile

| 检查 | 结果 | 说明 |
|---|---|---|
| `PYTHONPATH=. python -m pytest -q apps/backend/tests/test_ai_gateway_attempt_contracts.py -k 'ai_attempt_reconcile or network_error_is_unknown_delivery'` | PASS | `10 passed, 38 deselected, 17 warnings`；覆盖 unknown/unsupported、claim conflict、ORM candidate 事务内冻结。 |
| `PYTHONPATH=. python -m pytest -q apps/backend/tests` | PASS | `94 passed, 22 warnings`；warning 为既有 Pydantic/`datetime.utcnow()` deprecation。 |
| Ruff + compileall + `git diff --check` | PASS | 本切片生产与既有测试文件静态检查通过。 |
| 真实 MySQL unsupported lookup | PASS | 正式 Connection `supports_request_lookup=false`；隔离 Attempt `claimed=1/unsupported=1`，保持 unknown，同一 idempotency SHA/Provider Request ID，Call 不变，Attempt 不增加。 |
| 真实 MySQL lease crash recovery | PASS | 30 秒 claim 提交后模拟崩溃；未到期 `claimed=0`，31 秒后 `claimed=1/unsupported=1`。 |
| 资格化清理与既有事实保护 | PASS | qualification Call/Attempt 均删除；Attempt 总数恢复为 3；既有 Task/Stage/Call/Attempt/Report 全量摘要前后相同。 |
| 自动 reconcile 周期调度 | NOT RUN / NOT QUALIFIED | Celery task 已注册，但 compose 无 beat/cron/周期发送者。 |
| unsupported unknown 有界终止 | NOT IMPLEMENTED | 无首次 unknown/累计 reconcile 持久字段；未获表/字段/迁移授权。 |
| Provider 网络 POST | NOT RUN | 本切片只走 `UnsupportedProviderAttemptLookup`，不得把它视为 Provider 查询或模型调用。 |
| 医学验证 | UNKNOWN / NOT RUN | 不涉及医学评测，保持 `MEDICAL_RELEASE_NO_GO`。 |


## 2026-08-27 — 本地无 Docker 全链路（用户决策：不用 Docker，代码直接跑）

| 检查 | 结果 | 说明 |
|---|---|---|
| 前置依赖 | PASS | 本地 MySQL 127.0.0.1:3306（ms_image 21 表、active `xray_diagnose` Config 已存在）、RabbitMQ 5672（guest）、Redis 6379、ms-ai-platform 8060（HTTP 404 仅根路径）、OSS `ms-sz` bucket 均可达；ms-image conda 环境缺 jinja2，改用 base python3.12（依赖完整）。 |
| 本地三进程启动 | PASS | Runtime API 8010（dev RSA JWT）、Outbox Relay、Celery Worker（`imaging.image.validate`）全部 ready；worker 注册 `imaging.validate_image` / `imaging.execute_stage` / `imaging.reconcile_ai_attempts`。 |
| API 健康 | PASS | `GET /api/v1/health` 200 healthy。 |
| E2E 全链（HTTP API） | PASS / E2E_COMPLETE | Session -> Study -> Series -> prepare-upload（signed URL）-> PUT OSS 200 -> complete-upload -> ImageValidationWorker ready（1 次轮询）-> finalize Study ready -> `POST /tasks`（diagnose, species=dog, task_id `8ca384148d8440fa88ee01bfda81c9dc`）-> Outbox -> RabbitMQ -> `imaging.execute_stage` x3 -> ms-ai-platform -> Attempt succeeded（`actual_model=gemini-3.5-flash`、`provider_request_id=chatcmpl-1787816773`、`image_count_sent=1`、image receipt 1 张）-> AICall 1 -> 3 Stage 全 completed -> Report(final/produced) -> Task(completed/produced)。 |
| 数据库事实复核 | PASS | `task_record.completed/produced/error_code=None`；`report_record.final/produced`；`stage_checkpoint_record` 3 行全 completed；`ai_call_record` 1；`ai_call_attempt_record` 1 行 `succeeded` 含真实 provider 证据。 |
| 密钥/令牌安全 | PASS | dev RSA 密钥只在 `scripts/dev/keys/`（已 gitignore），token 由 `issue_dev_token.py` 现场签发，不落库、不写日志、不进 git。 |
| 可复现性 | PASS | `scripts/dev/run_local_chain.sh`（启动三进程）+ `scripts/dev/run_e2e_local.py`（全链复跑）已收进仓库；两处一次性修正：`image_kind=instance`（合法枚举不含 `source`）、GET `/studies` 返回嵌套 `study` 对象。 |
| 不误报 | PASS | 本次是工程全链，不涉及医学评测；`RUNTIME_QUALIFIED` 仍按完整 P1 定义保持 NOT QUALIFIED（JWT/Artifact signing/自动调度未资格化）；`MEDICALLY_VALIDATED=UNKNOWN`、`MEDICAL_RELEASE=NO-GO`。 |

## 2026-08-27 — 27 号方案审查与 28 号文档验证

| 检查 | 结果 | 说明 |
|---|---|---|
| 27 号文档完整读取 | PASS | 642 行，主线程逐段读取；未把基础设计文档外包给子代理。 |
| 关键源码合同复核 | PASS | 核对 medical status、Evaluation Export、multi-image load、projection write/manifest/snapshot/prompt、clinical context、result Schema、API root path/cancel method。 |
| 新文档结构 | PASS | 含决策、权威、基线、真实链、候选对照、因果分析、重构级别、目标架构、指标计划、阶段 write set、验证、风险/回滚与 UNKNOWN。 |
| 文档内部冲突扫描 | PASS | 当前不新增 API/表/迁移与后置阶段一致；C1 不改冻结 v1 Stage，v2 再版本化。 |
| `git diff --check -- docs/refactor/README.md docs/refactor/28-xray-evidence-driven-development-guide.md` | PASS | 无 whitespace error。 |
| 业务测试/运行链 | NOT RUN | 本轮仅新增开发文档与交接状态，无业务代码改动；未生成测试或迁移脚本。 |


## 2026-08-27 — C1 医学状态合同修复（28 号文档切片）

| 检查 | 结果 | 说明 |
|---|---|---|
| 持久化边界投影实现 | PASS | `ImagingExecutionService._project_medical_status()`：从嵌套 `complete_medical_result.medical_status` 投影，非法/缺失回退 `not_produced`；`ReportService.finalize` 增加受控枚举校验拒绝 `produced` |
| v1 Stage 语义冻结 | PASS | `joint_primary_reader.py` / `decision_finalization.py` 未修改；Stage output_json 仍含内部标记 `produced` |
| 真实 E2E 验证 | PASS | 新 task `f125fb933401403b89b7e1cd954c4f31`：`task.ai_medical_status=review_required`、`report.medical_status=review_required(final)`、`content_json.medical_status=review_required`；Stage output 仍 `produced` |
| 存量数据 | NOT FIXED（单独授权前不修） | 旧 task（如 8ca384...）仍存 `produced`，数据修正待用户授权 |
| 测试 | PASS | backend 全量 `94 passed, 22 warnings`；合同测试 `48 passed` |
| 偶发 Provider 失败 | PASS（fail-closed 正确） | 一次运行 `provider_response_json_invalid` 正确收敛为 `failed/not_produced`，未误报 |

## 2026-08-27 — C1 复核与 29 号 post-C1 开发指南

| 检查 | 结果 | 说明 |
|---|---|---|
| C1 源码复核 | PASS / PARTIAL HARDENING | 确认 happy-path 投影和 Report 列 allowlist 已实现；确认非法 availability/result 组合仍会静默回退、状态集合重复、content/列一致性未校验。 |
| C1 focused test inventory | GAP CONFIRMED | 现有测试只有 Report 幂等/发布等合同；未直接引用 `_project_medical_status`、`report_medical_status_invalid`，也未覆盖 content/列冲突。 |
| `PYTHONPATH=. python -m pytest -q apps/backend/tests` | PASS | `94 passed, 22 warnings in 1.65s`；warning 为已有 Pydantic/`datetime.utcnow()` deprecation。该结果证明当前工作树回归通过，不代表 C1.1 已实现。 |
| 29 号章节/围栏扫描 | PASS | 13 个一级编号章节完整；Markdown code fence 数为 52（成对）；文档 1050 行。 |
| 尾随空白与 tracked diff check | PASS | 新文档/README/handoff 无尾随空白；`git diff --check` 对 tracked 变更无错误。 |
| Handoff maintenance | PASS WITH ROTATION | `maintain_handoff.py --compact-if-needed`：`unresolved=0`；轮转 3 个旧 work-log section，更新 archive。 |
| 业务代码、DB、迁移 | NOT CHANGED / NOT RUN | 本轮只新增/更新开发文档和 handoff；未修改业务代码、表、字段、迁移或测试脚本，未重跑真实 Provider E2E。 |

## 2026-08-27 — API、ORM 与真实 MySQL 只读审计

| 检查 | 结果 | 说明 |
|---|---|---|
| 四应用动态路由/OpenAPI | PASS | Runtime 27 个业务 API + 根路由、Admin 6 + 根路由、AI Control 29 + 根路由、Evaluation 9 + 根路由；重复路由 `[]`，业务路由缺失 response model `[]`。 |
| ORM/物理表与列 | PASS | `model_missing=[]`、`extra_non_model=[]`、`column_diffs=[]`、普通索引/唯一约束差异 `[]`。 |
| 表规则 | PASS | 20 张业务表均独立 `id` 单列主键；foreign keys=0、DB enum columns=0、无 comment 字段=0。 |
| 引用完整性 | PASS | Study->Session、Series->Study、Image->Series、Task->Study、Stage->Task、Report->Task、Call->Stage、Attempt->Call 孤儿均为 0；current report pointer drift=0。 |
| Report CAS 合同 | FAIL / CODE DEFECT | Report ORM、物理表、Response 无 `state_version`，但 `ReportDal.cas_update()` 调用 `DalBase.cas_put_data()` 默认读取该列；未执行任何写操作。 |
| Evaluation 数据库 | FAIL / UNAVAILABLE | `ms_image_eval` 连接返回 MySQL 1049；四张 Evaluation 表位于主库且均为空。 |
| Alembic 可重建性 | FAIL / SOURCE AUDIT | 当前仅两个 revision，显式 create 5 张表且前置使用 `ai_config_record`；未运行破坏性的空库 replay。 |
| 当前数据状态 | CONFIRMED | Image 10 行且 projection 10 行为空；Task 9 行含 `produced` 3；Report 4 行含 `produced` 3。 |
| 业务测试 | NOT RUN | 本轮无业务代码改动；沿用上一轮 `94 passed` 仅作历史回归证据，不覆盖 Report 真实 DAL CAS。 |
## 2026-08-27 — 四应用全接口逐项审计文档验证

| 检查 | 结果 | 说明 |
|---|---|---|
| 动态 route -> 文档覆盖 | PASS | Runtime 27 个业务 API + 根路由、Admin 6 + 根路由、AI Control 29 + 根路由、Evaluation 9 + 根路由；四组 missing 均为空。 |
| 2026-08-28 四应用路由统计口径复核 | PASS | Runtime 27 个业务 API + 根路由、Admin 6 + 根路由、AI Control 29 + 根路由、Evaluation 9 + 根路由；合计 71 个业务 API + 4 个根路由 = 75。旧版 74 为统计口径错误。 |
| 2026-08-28 全链路接口闭环文档检查 | PASS | 30 号文档已新增 L0/L1/L2/L3 判定，并分离新增接口、现有接口修正、内部非 HTTP 阻断；`git diff --check -- docs/refactor/30-xray-interface-by-interface-audit-and-development-checklist.md` 通过。 |
| 2026-08-28 业务实现/运行验证 | NOT RUN | 该次检查只做接口盘点和文档/交接收口，未修改业务代码、数据库、表、迁移或测试；Task page 在后续独立切片实现并验证，见本文件对应章节。 |
| 关键源码引用存在性/行号 | PASS | 30 号文档 19 个显式 Python source refs 均存在且行号未越界。 |
| Markdown fence/尾随空白 | PASS | 16 个 fence，成对；trailing whitespace=0。 |
| README 入口 | PASS | 30 号文档已登记在文档地图和按任务阅读。 |
| `git diff --check` | PASS | 30 号文档与 README 无 whitespace error。 |
| 业务测试/写接口/DDL | NOT RUN / NOT CHANGED | 本轮只读审计并新增文档；未修改业务代码、数据库、表、迁移或测试脚本。 |

## 2026-08-27 — `POST /series` revision 修复

| 检查 | 结果 | 说明 |
|---|---|---|
| 存量矛盾只读扫描 | PASS | ready Study 下 `Series.created_at > Study.revision_changed_at` 的行数为 0；未修改存量数据。扫描结束时 aiomysql 在 event loop 关闭后输出连接析构 warning，不影响查询结果，后续验证显式 dispose engine。 |
| Ruff / compileall | PASS | `ruff check apps/backend/services/runtime/service/study_service.py` 与目标文件 `compileall` 通过。 |
| backend 全量测试 | PASS | `PYTHONPATH=. python -m pytest -q apps/backend/tests`：`94 passed, 22 warnings in 1.58s`；warning 均为既有 Pydantic/`datetime.utcnow()` deprecation。 |
| 真实 DB revision + 幂等 | PASS | 回滚事务内创建新 Series 后 Study revision/state_version 各 `+1`、status=`validating`、ready_at=`NULL`、manifest 改变；相同 payload 重放 revision `+0`；不同 payload 被拒绝。 |
| 真实 DB CAS 回滚 | PASS | 替换 `StudyDal.cas_revision` 为失败结果后，Service 抛 `study_revision_conflict`；事务回滚后按 key 查询不到新 Series。 |
| 真实 DB 不同 key 并发 | PASS | 两个并发请求在同一临时 ready Study 下均成功，产生两个不同 Series，revision/state_version 各准确 `+2`。 |
| 真实 DB 相同 key 并发 | PASS | 两个并发请求返回同一 Series ID，只新增一个 Series，revision/state_version 只额外 `+1`；证明 MySQL REPEATABLE READ 下 current locking read 可见竞争赢家。 |
| 数据污染 | PASS | 两组验证均显式 rollback，并在独立 session 复核测试 Series 不存在。 |
| 并发资格化清理 | PASS | 临时三条 Series、Study、Session 按精确 ID 删除，并在独立 session 复核全部不存在。 |
| 新测试/迁移 | NOT CREATED | 按用户默认约束未新增测试脚本或迁移脚本；本切片不改表、不改 Schema。 |

## 2026-08-27 — `GET /tasks?id=` 轮询字段补齐

| 检查 | 结果 | 说明 |
|---|---|---|
| ORM/物理字段 | PASS | `current_report_id/started_at/finished_at/next_retry_at` 在 Task ORM 与真实 `task_record` 均存在且 nullable；无需迁移。 |
| Ruff / compileall / diff check | PASS | `apps/backend/schemas/task.py` 定向静态、语法和 whitespace 检查通过。 |
| OpenAPI | PASS | `TaskResponse` 已出现四个 nullable 字段，未改变现有必填字段集合。 |
| 真实 ORM 投影 | PASS | 9 个真实 Task 均可 `TaskResponse.model_validate`；9/9 终态有 finished_at，4 个有 current_report_id，8 个有 started_at，0 个有 next_retry_at。 |
| Service owner 合同 | PASS | 正确 requester 读取 completed Task 并取得 Report/时间字段；错误 requester 仍抛 `TaskAccessDeniedError`。 |
| backend 全量测试 | PASS | `PYTHONPATH=. python -m pytest -q apps/backend/tests`：`94 passed, 22 warnings in 1.25s`；均为既有 deprecation warning。 |
| Task retry_wait | NOT IMPLEMENTED | 全仓 Python 搜索没有 Task `retry_wait/next_retry_at` 写入；当前字段只完成读合同。 |
| 数据/迁移/测试文件 | NOT CHANGED | 验证只读；未新增迁移或测试文件，未修改业务数据。 |

## 2026-08-27 — `GET /images/page` 分页接口

| 检查 | 结果 | 说明 |
|---|---|---|
| Ruff / compileall / diff check | PASS | 四个目标 Python 文件 `ruff`、`compileall` 和全工作树 `git diff --check` 通过。 |
| Runtime OpenAPI | PASS | 存在 `GET /api/v1/images/page`；`series_id` 必填，status/role/current/include_versions/page/page_size 默认值正确；响应为 `PagedResponse[ImagePageItemResponse]`。 |
| DTO 内部字段隔离 | PASS | 30 字段分页 DTO 不包含 object/storage/version/KMS/validation lease/technical metadata；详情仍走 `GET /images?id=`。 |
| ORM 精确列加载 | PASS | 真实 MySQL 查询后 inspection 确认 object/storage/KMS/validation/source manifest/technical metadata 均为 deferred，分页序列化未触发 lazy load。 |
| current/history 语义 | PASS | 回滚事务临时构造同 logical key 的 v1 ready 与 v2 uploading：默认只返回 v2；历史 page 1/page 2 分别返回 v2/v1，总数 2；current + status=ready 结果 0，不回退旧版。 |
| owner 隔离 | PASS | 正确 requester 返回 1 条真实 Image；错误 requester 抛 `SessionAccessDeniedError(session_access_denied)`。 |
| MySQL EXPLAIN | PASS WITH LIMITATION | 主查询走 `uq_image_record_logical_version` 的 series 前缀；anti-join 走 series+logical key 且 `Not exists; Using index`；无全表扫描，但排序为 `Using filesort`。当前最大每 Series 仅 1 条，未资格化大 Series 延迟。 |
| backend 全量测试 | PASS | `python -m pytest -q apps/backend/tests`：`94 passed, 22 warnings in 1.38s`；均为既有 Pydantic/`datetime.utcnow()` deprecation。 |
| 数据/表/迁移/测试文件 | NOT CHANGED | 临时版本数据已回滚并复核残留 0；未改表、Model、迁移或测试文件。 |
| Handoff maintenance | PASS WITH ROTATION | `maintain_handoff.py --compact-if-needed`：`unresolved=0`；自动轮转 1 个旧 work-log section。 |

## 2026-08-28 — `GET /tasks/page` 分页接口

| 检查 | 结果 | 说明 |
|---|---|---|
| Schema 合同 | PASS | ID/status/type 正规化通过；无 Session/Study scope、无时区 datetime、反向时间范围均拒绝；带时区时间统一转为 UTC naive。 |
| SQL 合同 | PASS | 生成查询同时包含 Task requester、Session/Study、status/type、创建时间过滤及 `created_at DESC, id DESC` 稳定排序。 |
| Service scope/owner | PASS | 正确 owner 可查询；错误 owner 被拒绝；Session/Study 不匹配被拒绝；requester ID 始终传入 DAL。 |
| Runtime OpenAPI | PASS | 暴露 `session_id/study_id/execution_status/task_type/created_from/created_to/page/page_size` 8 个参数，响应为 `PagedResponse[TaskStatusResponse]`。 |
| DTO 内部字段隔离 | PASS | 包含 current Report、retry/cancel/终态时间；不包含 request snapshot、预算、Pipeline/assignment hash、错误消息或取消原因。 |
| Ruff / compileall / diff check | PASS | 四个目标 Python 文件静态、语法和 whitespace 检查通过。 |
| backend 全量测试 | PASS | 最终复跑 `python -m pytest -q apps/backend/tests`：`94 passed, 22 warnings in 0.70s`；均为既有 Pydantic/`datetime.utcnow()` deprecation。直接运行 `pytest` 会因入口未加入仓库根目录而在收集期报 `ModuleNotFoundError: apps`，模块方式为有效命令。 |
| 真实 MySQL 只读合同 | PASS | Study 查询、Session + status/type、精确时间闭区间、`page_size=1` 分页和错误 owner 隔离均通过；`study_total=1/session_filtered_total=1/exact_time_total=1`。 |
| 大 Session 性能 | UNKNOWN / NOT RUN | 当前仅完成小样本正确性验证；多 Study、组合过滤的执行计划和尾延迟需生产等量级数据资格化。 |
| 数据/表/迁移/测试文件 | NOT CHANGED | 验证只读；未新增表、字段、迁移或测试文件。 |
| Handoff maintenance | PASS WITH ROTATION | `maintain_handoff.py --compact-if-needed`：`unresolved=0`；自动轮转 1 个旧 work-log section，随后 `--check` 为 `warnings=0/unresolved=0`。 |

## 2026-08-28 — `GET /reports/current?task_id=` 当前报告接口

| 检查 | 结果 | 说明 |
|---|---|---|
| Ruff / compileall / diff check | PASS | `report_service.py` 与 Runtime `reports.py` 静态、语法和 whitespace 检查通过；30 号文档 diff check 通过。 |
| Service current 合同 | PASS | 不落盘 Fake DAL 验证 8 类场景：正确 owner + final/published、空 pointer、错误 owner、缺失 Report、跨 Task pointer、void pointer、superseded pointer。 |
| Runtime OpenAPI | PASS | 注册 `/api/v1/reports/current`；query 参数为 `task_id`；200 响应引用允许 `ReportResponse | None` 的 GenericResponse Schema。 |
| 真实 MySQL 只读合同 | PASS | E2E Task `f125fb933401403b89b7e1cd954c4f31` 按真实 requester 返回 current final Report `0ca6def11b464beba4ac116f05e2d464`；错误 requester 抛 `ReportNotFoundError`。 |
| backend 全量测试 | PASS | `python -m pytest -q apps/backend/tests`：`94 passed, 22 warnings in 0.96s`；均为既有 Pydantic/`datetime.utcnow()` deprecation。 |
| 数据/表/迁移/测试文件 | NOT CHANGED | 本轮验证不写业务数据；未新增表、字段、迁移或测试文件。 |
| Handoff maintenance | PASS | `maintain_handoff.py --compact-if-needed` 与 `--check` 均为 `warnings=0/unresolved=0`；首次运行已轮转 1 个旧 work-log section。 |

## 2026-08-28 — Session complete/cancel 与 Task 生命周期联动

| 检查 | 结果 | 说明 |
|---|---|---|
| 分层与事务审计 | PASS | 保持 `API -> SessionService/TaskService -> SessionDal/TaskDal(DalBase) -> DB`；请求级 `get_async_session()` 包裹同一事务，错误映射先 rollback，Task 取消请求与 Session CAS 不会半提交。 |
| 行锁与状态合同 | PASS | Session complete/cancel 与 Task create 共用 Session 行锁；cancel 按 Task ID 稳定顺序锁定非终态 Task。Task 终态固定为 `completed/failed/cancelled/dead_letter`，已请求取消但仍 queued/running/retry_wait 的 Task 仍属非终态。 |
| Worker 取消消费路径 | PASS | `ImagingExecutionService`、`AIRequestService`、`ReportService` 在 claim、Provider/result finalization 和 Report 边界检查 `cancel_requested_at`；Session cancel 不直接伪造 Task 终态。 |
| Ruff / compileall / diff check | PASS | 四个目标业务文件通过 Ruff 与 compileall；全工作树 `git diff --check` 通过。 |
| backend 全量测试 | PASS | `python -m pytest -q apps/backend/tests`：`94 passed, 22 warnings in 0.86s`；warnings 均为既有 Pydantic 与 `datetime.utcnow()` deprecation。 |
| 真实 MySQL 回滚事务 | PASS | 验证 active Task 阻止 complete、terminal Task 允许 complete、cancel 请求非终态并保留终态、first-request-wins、重放幂等、终态 Session 拒绝新 Task；显式 rollback 后 `transaction_persisted=False`。 |
| 跨连接并发资格化 | NOT RUN | 未提交临时 fixture 执行 create-vs-complete、create-vs-cancel、worker-vs-cancel 的独立连接竞态；当前证据为行锁顺序审计、真实 MySQL 单事务合同和全量回归。 |
| 数据/表/迁移/测试文件 | NOT CHANGED | 本切片未改 API、Model、Schema、数据库表/字段、迁移或测试文件；真实数据库验证未留下数据。 |

## 2026-08-28 — D1 逐图 projection/provenance 四层链

| 检查 | 结果 | 说明 |
|---|---|---|
| projection vocabulary 只读审计 | PASS / AUTHORITY UNKNOWN | 仓库、相邻服务、DICOM validator 和历史数据均无权威完整 code 集；现有 LAT/VD/DV/LL 仅见于文档或 fixture。因此实现不新增医学枚举、大小写转换或字符白名单，只保留 trim、非空、现有 `VARCHAR(64)` 长度与显式 UNKNOWN。 |
| Ruff / compileall | PASS | 撤销额外 token 规则并补 Image page provenance 列加载后，D1 目标 Python 文件通过 `ruff check` 与 `python -m compileall -q`。 |
| OpenAPI | PASS | `ImagePrepareUploadRequest.projection` 为 required；`ImageReplaceRequest.projection` 为 optional；`ImageResponse` 暴露 `projection_provenance`。 |
| Schema/manifest 合同 | PASS | 定向不落盘检查证明 trim、非空/长度边界、缺失 prepare 拒绝、replace null 拒绝、保留 provenance key 拒绝；projection 改变会改变 manifest hash，无关 technical metadata key 不改变 hash。大小写原样保留。 |
| projection 无额外值域规则 | PASS | `Lat oblique 左侧` 经 normalize 与 prepare Schema 后保持原大小写和 Unicode 文本；生成 Schema 只有 `type=string/minLength=1/maxLength=64`，没有 enum 或 pattern。 |
| Snapshot/Prompt/Provider/receipt 合同 | PASS | 双图 LAT+VD 不落盘链验证 `series-image-manifest.v2 -> task-request-snapshot.v3 -> ordered_image_refs/view_positions -> Snapshot-only image_inputs -> ai-image-receipt.v2`；ID、hash、顺序、projection/provenance 一致且 receipt 无 signed URL。 |
| 冻结对象替换兼容 | PASS | Snapshot-only 定向检查在不访问 Image DAL 的情况下仍返回冻结 `image_old/images/old.jpg/LAT`，证明 v3 Provider 输入不受 current Image 替换影响。 |
| backend 定向测试 | PASS | `python -m pytest -q test_ai_gateway_attempt_contracts.py test_ai_prompt_control_plane_contracts.py`：`88 passed, 22 warnings`。首次直接调用 `pytest` 因仓库 root 未进入 import path 在 collection 报 `ModuleNotFoundError: apps`，随后使用项目有效的模块方式重跑。 |
| backend 全量测试 | PASS | 最终复跑 `python -m pytest -q apps/backend/tests`：`94 passed, 22 warnings in 0.80s`；均为既有 deprecation warning。 |
| 真实 MySQL DAL/legacy 只读检查 | PASS | 新 batch DAL 返回 8 Series/8 ready Image 并与全量集合一致；8/8 projection NULL，0 个 D1 manifest、8 个 legacy manifest、0 unmatched；9 个 v2 Task 当前 9/9 可按 legacy builder 重放。未写数据库。 |
| `GET /images/page` provenance 列加载 | PASS | `ImageDal.page_for_series()` 已显式加载 `technical_metadata_json`；真实 MySQL 只读取得 1 行并由 `_page_response()` 完成 projection/provenance 序列化，未触发异步 deferred-load。 |
| DeepSeek D1 P0 报告复核 | PARTIAL CONFIRMED | 5 个 ready Study 的非空 Series 全为 legacy stored SHA，当前 `_build_request_snapshot()` 对其中一例稳定拒绝 `task_series_manifest_snapshot_mismatch`；`e3f976…` stored SHA 与 D1 重算一致，可成功构造 `task-request-snapshot.v3`。legacy 新 Task 兼容缺口成立。 |
| `object_version_id` 根因核验 | REJECTED | 当前 `complete_validation()` 先 CAS 写 `object_version_id/content/hash/size/status=ready` 并 populate-existing 回读，之后才 recompute；真实 8 张 ready Image 的 object_version_id 均为 NULL。手工重算后的 `e3f976…` stored D1 SHA、Series count、Study resolved SHA 全一致。 |
| 本地进程一致性 | FAIL / RESTART REQUIRED | 同一 `imaging.image.validate` 队列同时有 2026-08-27 18:33 与 2026-08-28 11:55 启动的两组 Celery Worker，旧、新源码可能混合消费；本轮只读检查，未停止进程。 |
| 真实两视图 E1-MV / Provider / Report | NOT RUN | 当前没有获确认 projection 的真实两视图输入；不使用重复图片或文档 token 冒充病例。D1 只能标记 code complete，不能标记运行或医学资格化。 |
| 表/字段/迁移/测试文件 | NOT CHANGED | 未新增或修改表、字段、迁移、测试文件；只更新既有本地 E2E 脚本以显式传 UNKNOWN。 |
| Handoff maintenance | PASS WITH ROTATION | `--compact-if-needed` 自动轮转 1 个旧 work-log section，`unresolved=0`；随后 `--check` 为 `warnings=0/unresolved=0`。 |

## 2026-08-28 — Task Snapshot legacy/D1 双轨兼容

| 检查 | 结果 | 说明 |
|---|---|---|
| Series/Study 版本选择 | PASS | 真实 6 个 ready Study 均通过同一个 Study aggregate 校验；5 个 legacy 选择 `task-request-snapshot.v2`，1 个 D1 选择 v3。`e3f976…` 虽为 validating，仍可正确构造 v3。 |
| mixed/neither fail-closed | PASS | 用真实 legacy+D1 Series 组成 mixed Study、并构造 stored SHA 不匹配的 neither Study，均拒绝 `task_series_manifest_snapshot_mismatch`。 |
| 完整 Task create 事务 | PASS | 对真实 legacy ready Study 和 D1 ready Study 分别执行 `TaskService.create_task()`，得到 queued/v2 与 queued/v3；显式 rollback 后二者均未持久化。 |
| legacy Runtime 图片输入 | PASS | 对回滚事务中的新 legacy v2 Task 调用既有 `_load_attempt_image_inputs()`，expected=1/resolved=1，证明下游继续使用 legacy builder；未发 Provider 网络请求。 |
| 静态与全量回归 | PASS | `ruff check task_service.py`、compileall、`git diff --check` 通过；`python -m pytest -q apps/backend/tests` 为 `94 passed, 22 warnings in 0.74s`。 |
| 表/迁移/测试文件/持久数据 | NOT CHANGED | 只修改 `task_service.py`；未改表、迁移、接口 Schema、测试文件或文档，真实 DB 验证全部回滚。 |
| 外部 E2E | USER-PROVIDED PASS | DeepSeek 在清除旧 Worker 后报告新链 `completed / review_required / Report final`；该证据证明单一当前 Worker 新链可运行，但不是本轮 legacy v2 Provider E2E，也不是真实两视图医学验证。 |

## 2026-08-28 — 严格 JSON fence、失败 receipt 与真实 E1-MV

| 检查 | 结果 | 说明 |
|---|---|---|
| Ruff / compileall / diff check | PASS | 6 个目标 Python 文件通过 `ruff check` 与 `python3.12 -m compileall -q`；最终 `git diff --check` 通过。 |
| 严格 fence 合同 | PASS | 裸 JSON、唯一完整小写 `json` fence 通过；fence 解包后 Schema 仍生效；前后说明、无标签、`JSON` 标签、多 fence、非法 JSON 均拒绝。 |
| definite/unknown 发送审计 | PASS | HTTP body/内容解析失败携带脱敏 receipt；Worker 传入 finalizer；Attempt 与无 Winner Call 双写；partial audit 与 unknown receipt 均拒绝；无 signed URL。 |
| 定向测试 | PASS | `PYTHONPATH=. python3.12 -m pytest -q apps/backend/tests/test_ai_gateway_attempt_contracts.py`：`64 passed, 23 warnings in 0.89s`。 |
| backend 全量测试 | PASS | `PYTHONPATH=. python3.12 -m pytest -q apps/backend/tests`：`110 passed, 23 warnings in 0.90s`；warnings 为既有 Pydantic/`datetime.utcnow()` deprecation。 |
| 真实 E1-MV | PASS / ENGINEERING ONLY | Task `baef4d8619494a75aac7c2c7ef805c87`：queued -> running -> completed，医学状态为合法 `abnormal`，current Report `dfeeb929e1e145fbb20466ca999d26e8` 为 final。医学准确率未评估。 |
| Snapshot/receipt DAL 对账 | PASS | Snapshot v3；Call/Attempt succeeded 且唯一 Winner；receipt v2；requested/sent manifest、2/2 数量、VD+Lateral 顺序、SHA、projection/provenance 全一致；Call/Attempt receipt 相等且无 signed URL。 |
| 进程单组 | PASS AFTER CLEANUP | 重启 Worker 后 harness 一度多拉一个 Relay；已停止旧 Relay。最终一个 Relay 与一组 Celery Worker（parent + prefork child）。 |
| 表/字段/迁移/新脚本 | NOT CHANGED | 没有表、字段或迁移；没有新建测试脚本，只扩展现有测试文件。 |

## 2026-08-28 — Runtime readiness 在线平面隔离

| 检查 | 结果 | 说明 |
|---|---|---|
| Runtime 平面隔离定向合同 | PASS | `build_runtime_readiness()` 在 online-ready fixture 下只调用主 `async_engine` 和 imaging topology；未调用 Evaluation engine/topology，响应无 `evaluation_database/evaluation_broker`。 |
| Ruff / compileall / diff check | PASS | readiness core、Runtime health endpoint 和扩展的既有测试文件通过 Ruff；目标代码 compileall 与 `git diff --check` 通过。 |
| backend 定向测试 | PASS | `pytest -q ... -k readiness`：`2 passed, 64 deselected, 1 warning`；同时验证公共 Runtime 隔离与 Admin 聚合合同保持。 |
| backend 全量测试 | PASS | `PYTHONPATH=. python3.12 -m pytest -q apps/backend/tests`：`112 passed, 23 warnings in 1.05s`；均为既有 deprecation warning。 |
| 表/字段/迁移/新脚本 | NOT CHANGED | 本切片只改 readiness builder、Runtime endpoint import 和既有测试文件。 |

## 2026-08-28 — AI Control health/readiness

| 检查 | 结果 | 说明 |
|---|---|---|
| OpenAPI | PASS | `/api/v1/health`、`/api/v1/readiness` 已注册；readiness 响应声明 200 与 503。 |
| 定向合同 | PASS | `4 passed, 40 deselected`：占位 JWT 拒绝、Nacos disabled 不阻断、Nacos 使用只读 server health endpoint、必需依赖失败返回 503。 |
| 本地 health smoke | PASS | TestClient `GET /api/v1/health` 返回 `200/healthy/ai_control`。 |
| 本地 readiness smoke | EXPECTED 503 | 主库 `ready=true`；本机 `ADMIN_SECRET_KEY` 未配置，返回 `control_plane_jwt_key_unavailable`；Nacos 为 optional disabled。使用 lifespan context 后连接池正常关闭。 |
| Ruff / compileall / diff check | PASS | 全部目标文件通过。 |
| backend 全量测试 | PASS | `PYTHONPATH=. python3.12 -m pytest -q apps/backend/tests`：`116 passed, 24 warnings in 0.78s`；均为既有 Pydantic/`datetime.utcnow()` deprecation。 |
| 表/字段/迁移/新脚本 | NOT CHANGED | 新增 endpoint/readiness 模块并扩展既有测试文件；没有数据库或医学合同变化。 |

## 2026-08-28 — AI Control Nacos readiness 探针修正

| 检查 | 结果 | 说明 |
|---|---|---|
| Nacos 配置加载 | PASS | 新 `Settings()` 读取到非空 server、Prompt/general namespace 和凭据；未输出配置值或 Secret。 |
| Nacos 能力分段探针 | PASS | 登录成功；Config Client 对不存在 dataId 返回业务码 20004；Prompt Admin list 返回分页结构；Prompt Client OPTIONS 返回 200 且 `Allow` 含 GET。Console health path 404 被确认是部署版本/网关不兼容。 |
| canonical Prompt 精确读取与 Admin inventory | RISK FOUND | 当前配置的 Prompt/general/public namespace 下 latest 与 `1.0.0` 均为 404；只读遍历 Prompt namespace 212 条 Admin metadata 也无 canonical key。不影响 capability readiness，但会阻断未来重新导入；未读取或输出 Prompt 正文。 |
| 定向测试 | PASS | `PYTHONPATH=. python -m pytest -q apps/backend/tests/test_ai_prompt_control_plane_contracts.py -k readiness`：`5 passed, 40 deselected, 2 warnings`。 |
| Ruff / compileall / diff check | PASS | Nacos readiness 目标文件、既有测试文件与全工作树 whitespace check 通过。 |
| backend 全量测试 | PASS | `PYTHONPATH=. python -m pytest -q apps/backend/tests`：`117 passed, 24 warnings in 0.84s`；均为既有 deprecation warning。 |
| 真实 readiness | PASS WITH EXPECTED JWT BLOCKER | 当前配置为 database ready、Nacos ready、JWT key unavailable，因此整体 false/503；临时进程内注入合格 JWT key后 endpoint 200/全部 ready。未写配置文件。 |
| 表/字段/迁移/新脚本 | NOT CHANGED | 只改 Nacos 探针与既有测试/交接状态；没有数据库、医学或 projection 合同变化。 |

## 2026-08-28 — `image-dev` Prompt namespace 对齐

| 检查 | 结果 | 说明 |
|---|---|---|
| namespace 根因 | PASS | 原 `.env` 的 Prompt/general namespace 均不等于用户确认的 `image-dev`；显式目标 namespace 可读取 canonical latest 与 `1.0.0`，证明 Prompt 未缺失，先前 404 是 namespace 配置漂移。 |
| 配置修正后 canonical source | PASS | 新 `Settings` 的 Prompt namespace 与目标一致；`NacosPromptSourceClient.fetch(..., version='1.0.0')` 返回版本和模板字段，未输出正文。 |
| 配置修正后 readiness | PASS WITH EXPECTED JWT BLOCKER | database ready、Nacos ready；JWT unavailable，故 overall false。既有进程需重启加载 `.env`。 |
| backend 全量测试 | PASS | `PYTHONPATH=. python -m pytest -q apps/backend/tests`：`117 passed, 24 warnings in 0.81s`。 |
| Ruff / compileall / diff check | PASS | Nacos readiness 目标文件、既有测试文件和全工作树 whitespace 均通过。 |
| 外部写入/数据库/迁移 | NOT CHANGED | 只改本地 `.env` 的 Prompt namespace；Nacos 与数据库均只读，没有新脚本、迁移或医学规则。 |

## 2026-08-28 — C1.1 医学状态边界加固

| 检查 | 结果 | 说明 |
|---|---|---|
| focused C1.1 contracts | PASS | 严格组合与持久化边界选择：`22 passed, 66 deselected, 3 warnings`。 |
| 既有 Gateway/Attempt 合同文件 | PASS | `PYTHONPATH=. python -m pytest -q apps/backend/tests/test_ai_gateway_attempt_contracts.py`：`88 passed, 25 warnings in 0.86s`。 |
| backend 全量测试 | PASS | `PYTHONPATH=. python -m pytest -q apps/backend/tests`：`139 passed, 26 warnings in 0.76s`；warnings 均为既有 Pydantic/`datetime.utcnow()` deprecation。 |
| Ruff / compileall / diff check | PASS | C1.1 三个生产文件与既有测试文件通过 Ruff、compileall；全工作树 `git diff --check` 通过。 |
| synthetic incoherent finalization | PASS | `produced` 缺失 complete result 时 Stage/Task 收敛 `failed/not_produced`，错误码 `finalization_medical_result_invalid`，且 ReportService 不被构造。 |
| 单一新 Worker 真实 E2E | PASS / ENGINEERING ONLY | 清除父级 harness 自动补拉造成的重复当前源码消费者后重跑；Task `5dee75ffd0554e78868c5100bc752ddb` 为 `completed/review_required`，current Report `e3f06fccbe1945009f5b0666aa222bf0` 为 final；Task、Report 列、content 顶层一致。 |
| Stage v1 真实兼容 | PASS | DecisionFinalization Stage `366c37406d054bf9b4528bbb365e3d86` 顶层仍为 `produced`，嵌套模型状态为 `review_required`；验收后进程盘点为一个 Relay 和一个 Worker parent/prefork child。 |
| 表/迁移/历史数据 | NOT CHANGED | 无 Model、表、字段或迁移变化；没有回填存量 `produced`。真实 E2E 只新增正常业务链路事实。 |

## 2026-08-28 — P1-A 自动 reconcile 调度

| 检查 | 结果 | 说明 |
|---|---|---|
| scheduler owner 审计 | PASS | 仓库内无 CronJob/平台 scheduler/systemd timer/既有 Beat；唯一 owner 固定为默认关闭、显式启用的独立 Celery Beat singleton。 |
| schedule/route/并发 focused contracts | PASS | 新增定向合同 `11 passed`；完整 Gateway/Attempt 合同文件曾通过 `95 passed, 30 warnings`。覆盖默认关闭、interval/batch 边界、显式 imaging route、task clamp/日志与双 Worker CAS。 |
| 非人工自动触发 | PASS | 只启动 Beat/Worker 后，Beat 日志自动发送 `imaging-ai-attempt-reconcile`；Worker 聚合为 `claimed=1/unsupported=1/due_scanned=1/due_remaining_estimate=0`。测试未调用 `run_once/send_task/apply_async`。 |
| Provider identity / no replacement | PASS | 自动重排后 Provider request ID、idempotency key 均不变，同一 Call Attempt 数保持 1；replacement Provider POST 计数为 0。 |
| Worker crash / lease recovery | PASS | 30 秒 lease claim 后在 90 秒 lookup 中 SIGKILL Worker；lease 到期后新 Worker通过 RabbitMQ 重投唯一恢复，后续 3 条积压周期任务均 `claimed=0`。 |
| 临时数据/进程清理 | PASS | 最终临时 Attempt `state_version=6/status=unknown`；精确删除 Attempt 与父 Call并验证不存在。Beat/Worker 已停止，无 ms-image P1-A 临时进程或 schedule 文件。 |
| backend 全量测试 | PASS | `python -m pytest apps/backend/tests -q`：`146 passed, 31 warnings in 1.12s`；warning 为已有 Pydantic/`datetime.utcnow()` deprecation。 |
| Ruff / compileall / shell / Compose / diff | PASS | P1-A 生产文件与既有测试文件 Ruff 通过；backend compileall、`bash -n scripts/dev/run_local_chain.sh`、broker+scheduler Compose config、`git diff --check` 均通过。 |
| 表/迁移/接口/医学规则 | NOT CHANGED | 无新 HTTP 接口、queue、Model、字段、迁移、测试脚本、医学或 projection 规则。 |
| P1-B unknown 有界终止 | NOT IMPLEMENTED | 默认 unsupported 仍会无限重排；需持久字段/迁移授权与 Provider lookup/SLA 决策，不能据 P1-A 宣称完整 Worker Runtime qualified。 |

## 2026-08-28 — 当前未提交代码架构只读审查

| 检查 | 结果 | 说明 |
|---|---|---|
| Git 范围 | REVIEWED | 59 个 tracked 文件，约 5812 additions/1811 deletions；另有既有未跟踪文档/Prompt/脚本，未清理或回退。 |
| API/Service/CRUD 分层 | PASS | endpoint 未直接拼 SQL/DAL 编排；Service 数据访问经实体 DAL；DAL 继承唯一 `apps.backend.core.crud.DalBase`；未发现第二套 Repository/CRUDBase/DatabaseService。 |
| API 资源 ID/响应 | PASS | 未发现新增 `/{id}` 路由；资源 ID 继续使用 query/body；业务 endpoint 通过 Service，并使用现有统一响应包装。 |
| 冻结执行与医学边界 | PASS WITH HARDENING | Worker 不读取 latest Prompt；Task/Config/Prompt/Call/Attempt 主要血缘冻结；Primary-only 正常路径与唯一结果 owner 守住；Python 不补医学判断。跨仓核对后，Connection/Platform 当前地址一致；剩余为 frozen URL 与 Worker URL 未自动比较的中风险硬化项。 |
| 平面隔离 | PASS WITH FINDINGS | Runtime/Evaluation readiness 主要隔离正确；但 Runtime 反向 import AI Control service verifier，Compose 共享 env_file 具备 Provider key 扩散条件。 |
| TargetedReview | CURRENTLY INACTIVE | Profile/handler 骨架存在，Task 可接受该 profile，但 FamilyRouting 固定 `primary_final`，正常路径不会创建 Targeted Attempt；M1/M2 前不得启用。 |
| Platform strategy | INTENTIONAL CONTRACT | payload `strategy=race` 有真实 400/200 Platform 合同与单 lane/max_attempts=1 约束，不按字段名误报 ms-image 已启用多 lane Race。 |
| backend 全量测试 | PASS | `PYTHONPATH=. python3.12 -m pytest -q apps/backend/tests`：`146 passed, 31 warnings in 1.09s`；warning 为既有 Pydantic/`datetime.utcnow()` deprecation。 |
| 静态/语法/部署/差异 | PASS | Ruff 全目标目录、`python3.12 -m compileall -q apps/backend`、`docker compose --profile broker --profile scheduler config --quiet`、`git diff --check` 均通过。 |
| 医学准确率 | NOT VALIDATED | 工程测试与既有 E1 证据不等于 Gold/Scorer/M1；继续保持 `MEDICAL_ACCURACY_UNKNOWN / MEDICAL_RELEASE_NO_GO`。 |
| 业务文件变更 | NOT CHANGED BY REVIEW | 本轮仅更新 durable handoff；未修复业务代码，等待用户决定是否进入修正。 |

## 2026-08-28 — P1-B unknown Attempt 持久有界终止

| 检查 | 结果 | 说明 |
|---|---|---|
| P1-B focused contracts | PASS | `22 passed`：v1 冻结值、count/age 等号边界、first unknown 只写一次、claim CAS 计数、最后一次 terminal 优先、超限不 lookup、双 Worker、迟到 terminal、无 replacement POST。 |
| Gateway/Attempt 完整合同 | PASS | `102 passed, 37 warnings`；warning 为既有 Pydantic 与 `datetime.utcnow()` deprecation。 |
| backend 全量测试 | PASS | `python -m pytest -q apps/backend/tests`：`153 passed, 38 warnings in 1.03s`。 |
| 正式迁移 upgrade | PASS | 真实 MySQL `20260824_02 -> 20260828_01`；物理列为 `first_unknown_at datetime(6) NULL`、`reconcile_count int NOT NULL DEFAULT 0`。 |
| 存量数据保护 | PASS | 15 条既有 Attempt：首次 unknown 非空=0、非零次数=0、unknown=0、`provider_result_unresolved`=0；未回填或改写业务状态。 |
| migration SQL/head/current | PASS | offline SQL 仅新增两列并推进 version；`alembic heads/current` 均为 `20260828_01`；downgrade guard 在任何 P1-B 事实存在时 fail-closed。 |
| 默认 unsupported 自动终止 | PASS | 单 Beat/Worker 自动 claim count=2 Attempt，执行一次 lookup 后 count=3；聚合 `claimed=1/lookup_authorized=1/unsupported=1/count_limit_reached=1/terminal_unresolved=1`。 |
| 全链终态 | PASS | Attempt `failed/provider_result_unresolved`；Call `failed/failed`；Stage `failed`；Task `failed/not_produced`；Report=0、Attempt=1、Provider identity 不变。 |
| 临时数据/进程 | PASS | 资格化 Task/Stage/Call/Attempt 精确删除并确认不存在；临时 Beat/Worker 与 schedule 文件清理。只保留既有 ms-image outbox relay。 |
| 静态/语法/部署 | PASS | P1-B 文件 Ruff、backend compileall、`bash -n scripts/dev/run_local_chain.sh`、Compose broker+scheduler config、`git diff --check` 全部通过。 |
| 医学准确率 | NOT VALIDATED | P1-B 只关闭工程无限重排；没有新增医学/projection 规则，继续 `MEDICAL_ACCURACY_UNKNOWN / MEDICAL_RELEASE_NO_GO`。 |

## 2026-08-28 — ms-ai-fast Platform 地址合同对照

| 检查 | 结果 | 说明 |
|---|---|---|
| ms-ai-fast 执行目标来源 | CONFIRMED | `Settings.AI_PLATFORM_OPENAI_BASE_URL/API_KEY -> GatewayClient() -> /chat/completions`；没有 AI Connection/Model Pool ORM 表或冻结地址。 |
| ms-image 既有设计授权 | CONFIRMED | durable decision 明确要求按 ms-ai-fast 直接 Gateway 合同；Connection 只保存非敏感路由和能力元数据，Secret 仅由 Worker 进程环境注入。 |
| 当前地址一致性 | PASS | 只读比较显示 `ms-image.ai_api_connection` 唯一 validated 行的 `base_url` 与 `ms-ai-fast/.env` Platform URL 完全一致；未输出 API Key。 |
| 未配置行为 | FAIL-CLOSED | `ms-image` 当前默认 Settings 的 Platform URL 为空；runtime gate 不允许真实 Provider path，不会静默回退到其他 Gateway。 |
| 自动一致性校验 | NOT IMPLEMENTED | Runtime 不比较 frozen Connection URL 与进程 Platform URL；记录为 P2 配置漂移保护，不再声称当前已发生 P1 地址错发。 |
| 业务/外部状态 | NOT CHANGED | 仅只读跨仓与数据库核对、修正 handoff；未写数据库、环境、Nacos、Provider 或业务源码。 |

## 2026-08-28 — P1-C 与核心诊断链相关性核验

| 检查 | 结果 | 说明 |
|---|---|---|
| Runtime JWT 调用点 | ENTRY-ONLY | sessions/studies/images/tasks/reports 等 endpoint 使用 scope dependency；Worker、Provider 调用和 Report 状态机不读取 JWT key。 |
| Admin JWT 调用点 | CONTROL-ONLY | `ADMIN_SECRET_KEY` 用于 AI Control/Admin scope 与 readiness；不进入核心诊断执行。 |
| Artifact signing 调用点 | NOT WIRED TO MAIN CHAIN | 三个环境变量仅见 Compose；生产 Python 主链无读取，签名验证仅在 qualification/egress proof 工具。 |
| 当前范围裁决 | DEFERRED_BY_USER | P1-C 不作为当前核心链阻断；公网/生产 API 安全仍未资格化。 |
| 业务测试 | NOT RUN | 本轮仅只读相关性审计和交接范围更新，未修改业务代码，不需要重复 P1-B 全量回归。 |

## 2026-08-28 — C2 CompleteMedicalResult v2

| 检查 | 结果 | 说明 |
|---|---|---|
| C2 focused contracts | PASS | `160 passed, 38 warnings`；覆盖 v1 冻结、v2 Profile/Schema、Snapshot v3 门禁、SourceRef/receipt 正反例和结果持久化链。 |
| backend 全量测试 | PASS | `PYTHONPATH=. python3.12 -m pytest -q apps/backend/tests`：`166 passed, 38 warnings`；warning 为既有 Pydantic/`datetime.utcnow()` deprecation。 |
| 静态与语法 | PASS | `ruff check apps/backend`、`python3.12 -m compileall -q apps/backend`、`git diff --check` 均通过。 |
| v2 JSON Schema | PASS | `prompts/xray/complete_medical_result.v2.schema.json` 通过 JSON 解析与 Draft 2020-12 `check_schema`。 |
| v1 冻结完整性 | PASS | 旧 `1.0.0/xray_primary_v1` Config retired 后仍可按原 Prompt/Schema/Pipeline SHA 完整重验；v1 handler 未原地改写。 |
| Nacos Primary v2 | PASS | `ms-image.x-ray.primary.common.zh-CN@2.0.0` 发布后 exact readback 一致，content SHA `a20bc6e5f41ee250a01d1c94842c2bdfa00023b586a5c7496675e98c3c1e4cc1`。 |
| Control Plane v2 | PASS | Prompt `713392c2e4b94f2daefbfe8f559c6b1d` validated；Config `8997ea7bbea648488b0e043ace9b9095` active，Profile `xray_primary_v2`，Schema/Pipeline 冻结 SHA 均已对账。 |
| 真实 C2 E2E | PASS | Task `1b33cb9573df496f98d1f23f501ee8eb` 为 `completed/review_required`；Snapshot v3、primary/finalization v2、Attempt/Call succeeded、receipt v2、Report final。 |
| v2 结果一致性 | PASS | summary/impression 非空，Finding=3、SourceRef=1；Attempt、Call、Report 深度一致，存储结果重新运行 receipt 引用校验通过。 |
| Targeted v2 | INTENTIONALLY UNPUBLISHED | 只保留本地候选与不可达 handler；没有修改固定 `primary_final` 路由。 |
| 医学准确率 | NOT VALIDATED | 单病例工程输出没有可信 Gold/Scorer/分母，继续保持 `MEDICAL_ACCURACY_UNKNOWN / MEDICAL_RELEASE_NO_GO`。 |

## 2026-08-28 — 当前 XRay 全链缺口复核

| 检查 | 结果 | 说明 |
|---|---|---|
| 四份奠基文档 | READ | 完整读取 14/25/26/29；其中 25/26 与 29 的早期状态、14 的 6.2/13/15 节仍把后续已完成切片列为缺口，必须以当前源码和本文件后续记录覆盖。 |
| backend 全量测试 | PASS | `PYTHONPATH=. python -m pytest -q apps/backend/tests`：`166 passed, 38 warnings in 1.19s`；warning 为既有 Pydantic/`datetime.utcnow()` deprecation。 |
| Ruff / compileall | PASS | `python -m ruff check apps/backend` 与 `python -m compileall -q apps/backend` 通过。 |
| Compose / diff | PASS | `docker compose --profile broker --profile scheduler config --quiet` 与 `git diff --check` 通过。 |
| Alembic 当前库 | PASS WITH LIMIT | `alembic heads/current` 均为 `20260828_01`；只证明当前库已追加到 head，不证明空库 replay。当前仅三个 revision，metadata 同时导入 Runtime 与 Evaluation Model。 |
| Runtime 在线探针 | PASS WITH STALE PROVIDER SIGNAL | `GET 127.0.0.1:8010/api/v1/health` 与 `/readiness` 均 200；database/Redis/imaging broker ready，consumer=1、queue=0。Provider 子组件仍静态 `not_implemented`，但 required=false。 |
| AI Control 本机进程 | NOT RUNNING | `127.0.0.1:8002` 当前拒绝连接；不据此否定既有 Control v2 数据和真实发布证据，但完整常驻部署需单独启动并满足 JWT readiness。 |
| Evaluation 数据库 | FAIL / UNAVAILABLE | 使用独立 `evaluation_async_engine` 执行只读 `SELECT 1` 返回 `OperationalError`；未输出连接串或凭据。Evaluation Control 无独立 health/readiness 路由。 |
| Git 发布工件 | NOT FROZEN | 分支 `codex/prompt-runtime-ai-gateway`、HEAD `0a9aca4fb5c2`；69 个 tracked 文件修改、55 个 untracked 路径。测试通过的是当前工作树，不是已冻结 commit/image。 |
| 当前资格结论 | SPLIT | `CORE_WORKER_RUNTIME_QUALIFIED / C2_ENGINEERING_QUALIFIED`；`PRODUCTION_API_SECURITY_NOT_QUALIFIED / MEDICAL_ACCURACY_UNKNOWN / MEDICAL_RELEASE_NO_GO`。 |

## 2026-08-28 — DeepSeek 结论与最小工程主链复核

| 检查 | 结果 | 说明 |
|---|---|---|
| D2 clinical context v1 | PASS / IMPLEMENTED | `TaskClinicalContext`、source/allowlist、freeze、Snapshot v3 policy/SHA、Prompt 消费与 Evaluation export 均存在；剩余是上游传值。 |
| C2 CompleteMedicalResult v2 | PASS / ENGINEERING QUALIFIED | v2 合同与测试包含 `summary/impression/findings/source_refs`，并有缺 summary 负例和真实 C2 E2E；医学准确率仍未知。 |
| Report ORM state version | FAIL / MISSING | `Report` 与公共 base 均无 `state_version`，但 DAL publish/void/supersede 使用 CAS；第一份 final 主链不经过该 CAS。 |
| 既有本地 E2E 范围 | PASS WITH HARDENING NEEDED | `run_e2e_local.py` 覆盖 Session/Study/Series/upload/validation/finalize/Task/Worker/Provider/Report/current-history 主链；仍需参数化和稳定性加固。 |
| backend 全量测试 | PASS | `PYTHONPATH=. python -m pytest -q apps/backend/tests`：`178 passed, 38 warnings`。 |
| Ruff / compileall / diff check | PASS | `python -m ruff check apps/backend`、`python -m compileall -q apps/backend`、`git diff --check` 均通过。 |
| Runtime health/readiness | PASS WITH STALE PROVIDER SIGNAL | health/readiness 均 HTTP 200，数据库、Redis、broker 和工程 Worker ready；Provider 观察字段仍静态陈旧且非 required。 |
| 数据库最新 Task/Report | PASS / ENGINEERING EVIDENCE | 最新抽查的 5 个 Task 均为 completed 并有首份 final Report；证明工程链跑过，不证明医学准确。 |
| 本轮写入范围 | HANDOFF ONLY | 未改业务代码、数据库、Nacos、Prompt、迁移或测试脚本；只更新 durable handoff。 |

## 2026-08-28 — DeepSeek 最终输出与 14 号文档验证

| 检查 | 结果 | 说明 |
|---|---|---|
| 真实 current Report 查询 | PASS | Task `4b692c564eca4074a6113dbd92feb193` 对应 Report `efd9977002a84e839304843af3626f9c`；status=`final`、medical_status=`review_required`、result_schema_version=`xray-complete-medical-result.v2`，v2 结果位于 `content_json.complete_medical_result`。 |
| 当前进程只读检查 | NOT QUALIFIED | 发现 1 个 Runtime API、2 个 Outbox Relay、3 个 Celery Worker parent；未停止或修改进程。历史成功链有效，但当前确定性复跑不合格。 |
| Runtime readiness | PARTIAL | HTTP 200，online/database/Redis/broker ready，broker consumer_count=3、queue_message_count=0；Provider transport 仍报告 `not_implemented/target_provider_not_qualified`。 |
| DeepSeek 的 C2 判断 | CORRECTED | C2 v2 工程实现和真实报告已确认；但不能升级为医学准确率通过或医学发布通过。 |
| DeepSeek 的 v1 同步建议 | REJECTED | v1 是冻结历史合同；v2 必须通过独立 Schema/Profile/Handler/Config 演进。 |
| 14 号文档 diff check | PASS | `git diff --check -- docs/refactor/14-xray-specialty-design.md` 无输出。 |
| Markdown/Mermaid 围栏静态检查 | PASS | 6 个 Mermaid 块，Markdown fence 总数 18（偶数）；关键章节 5.2/5.3/5.4 与会议话术引用一致。当前环境未安装 Mermaid CLI，未执行 SVG 渲染。 |
| backend 全量测试 | NOT RERUN | 本轮只改文档和 handoff；引用最新已有记录 `178 passed, 38 warnings`，不是本轮重新运行结果。 |
| 业务/外部状态 | NOT CHANGED | 未改业务代码、数据库、Nacos、Prompt、Schema、迁移、测试脚本或运行进程；未提交 Git。 |

## 2026-08-28 — D2 可重复验收：单主人链路 + 3× 全链 E2E

| 检查 | 结果 | 说明 |
|---|---|---|
| 单主人收敛 | PASS | 清理全部旧进程（含 8/27 老代码 worker 与孤儿）后，仅 1 个 launcher（PID 59944，持有 `/tmp/ms-image-local-chain-8010.lock/owner.pid`）+ 1 API + 1 Relay + 1 Worker；readiness `ready:true`，broker `consumer_count=1`，Beat 未启用（`Reconcile scheduler enabled: false`），RabbitMQ 无旧消费者混跑。 |
| 390 行 launcher 启动合同 | PASS | `bash -n scripts/dev/run_local_chain.sh` 通过；唯一拓扑为 1 API + 1 Relay + 1 Worker parent/child、Beat=0、consumer=1；第二个 launcher 实测以 owner PID 拒绝且不影响现有进程。Celery active/reserved/scheduled 为空后 SIGTERM owner，所有自有进程、8010 与 owner lock 均释放。 |
| E2E 工具参数化 | PASS / VERIFIED IN CODE | `run_e2e_local.py` 已具备 `--api-base/--image/--species/--projection/--body-part/--clinical-context-mode/--context-recorded-at/--repeat`，无硬编码 thorax/dog；`--help` 输出正确。 |
| E2E 非法参数校验 | PASS | `--repeat 0`、空 `--body-part`、`--context-recorded-at` 无时区、`--clinical-context-mode none` + `--context-recorded-at`、空 `--projection`、不支持扩展名、不存在图片文件，7 项均以 `argparse` 错误拒绝退出。 |
| D2 3× 可重复验收 | PASS / `D2_SYNTHETIC_E2E_QUALIFIED` | 固定图片（VS1_CAT NOR 同名 JPEG，sha256 `6758a344...9ec9`）+ 合成临床上下文（`reason/chief_complaint` 均为合成工程文本，context sha256 `fb9003bf...74d9`）连续 3 轮：Session→Study→Series→prepare-upload→OSS PUT→complete-upload→Image ready→Study finalize→Task completed（medical=abnormal，模型投影）→Report final（result_schema_version=xray-complete-medical-result.v2、source_ref_count=1、finding_count=2）→`/reports/current`+history 一致。`E2E_COMPLETE` 输出，`E2E_FAILED` 0 次；batch 校验确认 3 轮 clinical context SHA 与 config fingerprint 一致。 |
| backend 全量回归 | PASS | `PYTHONPATH=. python -m pytest -q apps/backend/tests`：`178 passed, 38 warnings in 1.41s`。 |
| Ruff / compileall / diff check | PASS | `ruff check apps/backend scripts/dev/run_e2e_local.py scripts/dev/issue_dev_token.py`：All checks passed；`python3.12 -m compileall -q` 退出 0；`git diff --check` 无输出。 |
| D2/C2 fail-closed 观察 | PASS WITH RISK | 另一次批次第 2 轮 Task 真实失败为 `provider_result_source_fact_mismatch`，E2E 立即停止且未静默重试；后续从新批次连续三轮成功。证明技术引用门禁生效，但 Provider v2 结构稳定率仍需量化。 |
| Codex 新三轮证据 | PASS | Task `d5f9af4333964374a33c7787f4bf0315`、`09209da4edc146a88dd4e7b9bb9f738f`、`078ffda1472747d184015b36c5ee0692` 均 completed，对应 final Report `949e3dbe450a4ea78855c747f4aba611`、`000cafbf99394f0a90e505b16a8c2374`、`86533fc7f08a46ee80a0efb9ac69c2fb`；context SHA 同为 `d746b498...c1a5`，C2 v2/current/history/D1 source facts 均一致。文件名 `NOR` 未用于 Gold/医学断言。 |
| 本轮写入范围 | SCRIPTS + HANDOFF | 修改既有 `scripts/dev/run_local_chain.sh` 与 `scripts/dev/run_e2e_local.py`，并更新 durable handoff；未改业务 API/数据库/Nacos/Prompt/迁移/测试文件，未提交 Git。 |
