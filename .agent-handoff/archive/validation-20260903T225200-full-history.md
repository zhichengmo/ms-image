# 验证历史

## 2026-09-02 — Pet profile Task binding

- `PYTHONPATH=. pytest -q apps/backend/tests/test_ai_gateway_attempt_contracts.py apps/backend/tests/test_ai_prompt_control_plane_contracts.py`：356 passed, 45 warnings。
- `PYTHONPATH=. pytest -q apps/backend/tests`：365 passed, 45 warnings。
- `python -m compileall -q apps/backend/schemas/task.py apps/backend/services/runtime/service/task_service.py`：通过。
- `ruff check apps/backend/schemas/task.py apps/backend/services/runtime/service/task_service.py`：通过。
- Pydantic smoke：`pet_profile_id` 空白规范化、非 diagnose Task 拒绝档案绑定：通过。
- 未运行真实 HTTP Task+PetProfile E2E、未启动 Provider/Runtime/Worker、未写数据库/Nacos/OSS/Broker；医学准确率与完整 X-Ray 链路保持 UNKNOWN。

## 记录规则

- 主文件只保留当前资格状态和下一阶段仍有决策价值的证据。
- 2026-08-28 D2 收口前的完整验证历史已原样归档至 `archive/validation-pre-d2-closeout-20260828.md`；更早历史见 `archive.md` 索引。
- 工程通过、Provider 医学输出和医学准确率分开报告；文件名、目录名、单病例模型结果不得当作 Gold。

## Current Qualification

```text
TARGETED_REVIEW_RUNTIME_PASS
REPORT_GENERATION_AI_RUNTIME_PASS
SAME_TASK_FULL_CHAIN_RUNTIME_PASS
MEDICAL_ACCURACY_UNKNOWN
MEDICAL_RELEASE_NO_GO
```

2026-08-29 的猫狗 Prompt 工程资格与 Nacos `4.0.0` exact 回读记录已归档至
`archive/validation-20260903T-full-chain-closeout.md`。

## 2026-08-30 — v3.2 全项目接口、Prompt 与 Postman 校正版静态验收

| 检查 | 结果 | 说明 |
|---|---|---|
| Evaluation 边界 | PASS | Evaluation Control 的 `9` 个版本化接口进入全项目总账；当前 Worker 使用 `FakeEvaluationScorer`，为 `0 Prompt/0 Provider Call`，默认由 `enable_evaluation_requests=false` 跳过。 |
| Markdown/JSON/whitespace | PASS | 路线图 `212` 个 Markdown 围栏且为偶数；Postman JSON 可解析；目标文件 `git diff --check` 通过。 |
| Secret 扫描 | PASS | 未发现真实 JWT、Private Key、AKIA、`sk-*`、密码、`secret_key` 或 `api_key`；未输出 Prompt、病例或报告正文。 |
| 静态合同资格 | `STATIC_CONTRACT_QUALIFIED` | 只证明文档、OpenAPI 与 Postman Collection 静态一致。 |
| 真实 Runtime/Provider E2E | `RUNTIME_E2E_NOT_RUN` | 本轮未启动 Runtime、Relay、Worker、OSS、Broker 或真实 Provider，也未运行 Collection Runner/Newman。 |
| 医学准确率 | `MEDICAL_ACCURACY_UNKNOWN` | 没有正式 Gold、医学 Scorer 或 M1 结果，不得宣称医学准确率或发布资格。 |

## 2026-08-30 — v3.3 最终执行路线与 Prompt 事实校正版

| 检查 | 结果 | 说明 |
|---|---|---|
| 文档规模与结构 | PASS | 路线图 3660 行、151896 bytes、228 个代码围栏且为偶数；SHA256 `71a1c98a3f1a542ffb3f25685d40d845b5a0248ce0bd097f215f87fa7e531556`。 |
| v2 Prompt 来源 | PASS | 源码点验 `AIRequestService._render_v2_messages` 直接渲染 immutable Config `prompt_content`；Catalog 只在 v1 provider-disabled 兼容路径使用。 |
| Task Snapshot 边界 | PASS | 源码点验 Snapshot 保存 Config identity 与 prompt/model/schema/pipeline SHA；完整 Prompt content/variables/message contract 在 `AIConfigRecord`。 |
| Stage Prompt 数 | PASS | StudyPreparation/FamilyRouting/DecisionFinalization 为 0；JointPrimaryReader 为 1；TargetedReview 仅合法 candidate 时新增 1。 |
| 多图当前缺口 | PASS（事实核验） | Study/Series 只有 `ge=0`、prepare-upload 无第 6 图预拒绝、E2E CLI 仍单图；因此 E1/E3 仍是实际缺口。 |
| OpenAPI 路由 | PASS | Runtime `30/30`、Runtime Admin `7/7`、AI Control `32/32`、Evaluation Control `10/10`，合计 79。 |
| Postman | PASS | JSON 可解析；7 Folder、96 Request；本轮未修改 Collection。 |
| Whitespace | PASS | 路线图、Postman 与相关 handoff 文件 `git diff --check` 通过。 |
| 真实 Runtime/Provider E2E | `NOT RUN` | 本轮为文档与源码静态核验，未启动 API/Relay/Worker/OSS/Broker/Provider。 |
| 医学准确率 | `UNKNOWN` | 未运行 Evaluation/M1/Holdout；不得声称 Prompt 效果提升。 |

## 2026-08-30 — 提交前代码、资产与 Compose 验证

| 检查 | 结果 | 说明 |
|---|---|---|
| Backend full tests | PASS | `PYTHONPATH=. pytest -q apps/backend/tests`：`192 passed, 38 warnings`。 |
| Ruff | PASS | `ruff check apps/backend`。 |
| Compile | PASS | `python -m compileall -q apps/backend`。 |
| Local launcher | PASS | `bash -n scripts/dev/run_local_chain.sh`。 |
| E2E CLI | PASS | `python scripts/dev/run_e2e_local.py --help`。 |
| Reconcile CLI | PASS | `PYTHONPATH=. python -m apps.backend.workers.imaging_worker.reconcile --help`；P1-B 参数调用已补齐。 |
| Compose | PASS | default、`broker`、`scheduler`、`broker+scheduler` 四种 `docker compose ... config --quiet` 均通过。 |
| Postman JSON | PASS | canonical Collection 通过 `python -m json.tool`。 |
| Whitespace | PASS | `git diff --check` 与两组 cached diff check 通过。 |
| Secret/path boundary | PASS | cached diff 未发现 Private Key、常见 Token、AWS signed signature；`.env`、`scripts/dev/keys/`、旧根目录 Postman 和 handoff archive 均未暂存。 |
| Git push | PASS | `c8478e0`、`21f103f`、`52edcde` 已推送到 `origin/codex/prompt-runtime-ai-gateway`。 |
| Runtime E2E | NOT RUN | 本轮目标是检查、提交和推送；没有启动业务进程或重新运行真实 Provider 全链。 |

## 2026-08-30 — 2–5 图资格化分支与计划核验

| 检查 | 结果 | 说明 |
|---|---|---|
| Branch base | PASS | `codex/xray-2to5-runtime-qualification` 从 `d4a216a` 创建。 |
| Roadmap reading | PASS | 完整阅读 3660 行 v3.3 路线图；下一阶段与 E0–E8 顺序一致。 |
| Source anchors | PASS | 点验 Study/Series 数量 schema、Study/Image Service、AIRequest/Config 门禁和单图 E2E 写死位置。 |
| Tests | NOT RUN | 本轮只创建分支和整理计划，没有业务代码变化。 |
| Runtime E2E | NOT RUN | 未启动 Runtime、Relay、Worker、OSS、RabbitMQ 或真实 Provider。 |

## 2026-08-31 — Anatomy Localization v1 外部生命周期与 Runtime 阻断

| 检查 | 结果 | 说明 |
|---|---|---|
| Nacos exact publish/readback | PASS | 猫狗 `1.0.0` exact Data ID 均 online；规范化 content SHA 与本地审核载体一致，未覆盖同版本冲突。 |
| Prompt import/validate | PASS | 显式 namespace/release；cat/dog receipt 均为 Nacos exact source、requested=resolved variant、fallback=false，receipt SHA 经 DAL 回读复算。 |
| Config compile/create/validate/activate | PASS | 猫狗 `xray_anatomy_localization_*@1.0.0` 均 active；单 primary lane、`max_input_images=5`、总 Call/Attempt=1、lane Attempt=1；diagnose active 集合不变。 |
| Runtime preflight | PASS | 8002/8010 初始空闲，无 ms-image 进程和 lock；MySQL 3306、RabbitMQ 5672 ready。 |
| Unique launcher readiness | PASS | API health/readiness 200、Relay heartbeat ready、Worker concurrency=1、exactly one imaging consumer、Beat/reconcile scheduler=0。 |
| `cat-02` Harness | BLOCKED BEFORE TASK | `E2E_FAILED: MS_IMAGE_XRAY_DATA_ROOT is required for case manifest mode`；失败发生在 token/client/run_once 前，无 Task/Call/Attempt/Provider。 |
| Evidence directory | CLEAN | `/tmp/ms-image-anatomy-localization-r4-20260831.2vDAN4` 未产生文件并已移除；没有伪造失败病例 evidence。 |
| Remaining seven manifests | NOT RUN | 按任一 manifest 失败即停规则，未运行 cat-03/04/05 或 dog-02/03/04/05。 |
| Runtime cleanup | PASS | 8002/8010 释放，Runtime/Relay/Worker 不存在，launcher lock 清理；RabbitMQ 保持运行。 |
| aiomysql teardown warning | KNOWN / DEFERRED | launcher 正常停止时仍出现既有 event-loop 析构告警；未扩大 Localization 范围修复。 |
| Handoff maintenance | PASS WITH SOFT WARNING | `--check` 为 `changed=0 / unresolved=0`；`work-log.md` 有 31 个日期段，超过软阈值。因 archive 属受保护用户历史，本轮未运行会写 archive 的 compact/rotate。 |
| Runtime qualification | NOT QUALIFIED | 未创建病例 Task，不能声明 2–5 Runtime 或 single Logical Call 资格。 |

## 2026-08-31 — Anatomy Localization v1 X-Ray 数据根目录只读检查

| 检查 | 结果 | 说明 |
|---|---|---|
| 候选数据根目录 | PASS | `/Users/mozhicheng/workspace/documents/X光_没问题_全量过滤` 存在、为可读目录，目标文件均非 symlink。 |
| Harness manifest loader | PASS | 设置候选 `MS_IMAGE_XRAY_DATA_ROOT` 后直接调用现有 `load_case_manifest()`；cat-02/03/04/05 与 dog-02/03/04/05 共 8/8 PASS。 |
| 冻结文件事实 | PASS | 28/28 张目标图路径存在且 SHA256、size、`.jpg`→JPEG、`image/jpeg` 和连续 sequence 与 manifest 精确一致；唯一 SHA=28，无内容重复。 |
| JPEG 解码 | PASS | Pillow 12.1.1 `verify()+load()` 28/28 成功；尺寸 `624×1080` 至 `2100×2088`，format 全为 JPEG，0 损坏/空/零尺寸。 |
| 视觉抽样 | PASS（工程输入） | 抽查 2 张猫胸腔、2 张犬肌肉骨骼目标图，确认为可辨识 X-Ray；未判断疾病、器官 bbox 或医学质量。 |
| 八格覆盖 | PASS | manifests 精确覆盖 cat/dog × 2/3/4/5；总图数 28。 |
| 数据治理边界 | NOT QUALIFIED | manifests 为 `engineering_candidate` 且 projection=`UNKNOWN`；本检查不证明病例分组、投照位、Gold、定位准确率或医学发布。 |
| Runtime/Provider | NOT RUN | 本轮未启动任何服务，未创建 Task/Call/Attempt，未调用 Provider；此前失败后的新八格尝试仍待用户明确允许。 |
| 子代理派发 | TOOL BLOCKED | 3 个 `default` 只读子代理均因默认 reasoning 档位与当前模型不兼容而未创建；`list_agents` 仅有主代理。 |
| Handoff maintenance | PASS WITH SOFT WARNING | `--check` 为 `changed=0 / unresolved=0`；`work-log.md` 有 32 个日期段。自动 compact/rotate 会写受保护 archive，本轮未执行。 |

## 2026-08-31 — Anatomy Localization v1 `cat-02` 真实 Runtime 失败审计

| 检查 | 结果 | 说明 |
|---|---|---|
| Frozen identity preflight | PASS | 运行前 exact 回读 Nacos/Prompt/Config/ModelPool/Connection 并执行 frozen verify；Cat Config `c39ea5b9…ec40`、Prompt `bb9fa5d5…e8a`、Schema `a02062d8…ea70`、Pipeline `bcba1a97…fa4` 无漂移。 |
| Unique runtime topology | PASS | 1 Runtime API、1 Relay、1 Worker、concurrency=1、RabbitMQ consumer=1、Beat/reconcile scheduler=0；health/readiness 200。 |
| `cat-02` task topology | PASS | Task `c9f0ddb948444be1aa3f28aee0d29e89` 有 2 StageCheckpoint、1 provider-required Stage、1 Logical AICall `4836bebc9a3f42f49587220308c59f4c`、1 primary Attempt `7a3053aedc484bc191cb3106703dbc09`，attempt_no=1。 |
| Image delivery | PASS | requested=2、sent=2、receipt=2；requested/sent manifest SHA 一致，receipt contract 为 `ai-image-receipt.v2`。 |
| Provider boundary | PASS TO HTTP / FAIL-CLOSED CONTRACT | `POST /api/v1/chat/completions` 返回 HTTP 200，通用 JSON Schema 通过；Localization 技术 validator 返回 `anatomy_localization_image_lineage_mismatch`。 |
| Persisted terminal state | EXPECTED FAIL-CLOSED | Task、AICall、Attempt、Localization Stage 均 failed；AICall disposition=failed、winner_attempt_id=null、accepted result 未持久化。 |
| Rejected-result observability | INSUFFICIENT | 当前记录未持久化 rejected parsed payload、Provider request ID 或 response SHA，不能从数据库确定具体 lineage 漂移字段。 |
| No-Report boundary | PASS | `ai_medical_status=not_produced`、`current_report_id=null`；Report current data=null、history data=[]；Localization 查询返回 409。 |
| Stop gate | PASS | `cat-03/04/05` 与 `dog-02/03/04/05` 均未运行；未重试 `cat-02`、未增加 Attempt、未提高预算。 |
| Failure evidence JSON | PASS | `/tmp/ms-image-anatomy-localization-r4-20260831.OgbG1e/cat-02-failure-20260831T123942Z.json` 通过 `python -m json.tool`；SHA256 `1fa6698e3441c296c504912ec9f85d126a9c44198ac22dd935122722004985a4`，不含 Prompt 正文、Signed URL、Provider 原文或凭据。 |
| Runtime cleanup | PASS | 8002/8010 空闲，无 Runtime/Relay/Worker 或 launcher lock；主队列/DLQ 均 ready=0、unacked=0、consumers=0。 |
| Qualification | FAILED | `XRAY_ANATOMY_LOCALIZATION_2TO5_RUNTIME_QUALIFICATION_FAILED`；成功八格矩阵未完成，`ANATOMY_LOCALIZATION_SINGLE_LOGICAL_CALL_MATRIX_NOT_CONFIRMED`。 |
| Closeout environment recheck | PASS | 独立 `lsof` 检查确认 8002/8010 无监听；进程表无 Runtime/Relay/Worker/launcher；launcher lock 不存在。 |
| Handoff maintenance | PASS WITH SOFT WARNING | `--check` 返回 `changed=0 / warnings=1 / unresolved=0`；`work-log.md` 有 33 个日期段。自动 rotate 会写受保护 archive，因此本轮不执行。 |
| Git diff whitespace | PASS | `git diff --check` 无输出。受保护 `.agent-handoff/archive*` 与根目录 `postman/` 保持既有工作区状态，未修改、恢复或暂存。 |
| Backend tests after Runtime attempt | NOT RERUN | 本次续作只更新 durable handoff，没有修改业务代码；保留此前 70 focused / 311 full、Ruff、compileall 和静态资格结果。 |

## 2026-08-31 — `cat-02` lineage 失败现有证据穷尽审计

| 检查 | 结果 | 说明 |
|---|---|---|
| Attempt correlation facts | PASS | 只读回读 request ID、trace ID、provider idempotency key、sent manifest SHA 与 image count；`provider_request_id=None`、`response_sha256=None`。查询脚本显式 dispose engines，未写 DB。 |
| Downstream header propagation | PASS | `AIRequestService` payload metadata 与 `GatewayClient` headers 确认 request/trace/idempotency key 已发送给 AI Platform。 |
| Local log search | NO MATCH | 以 Task/Call/Attempt、request/trace/idempotency key、错误码和失败时间窗搜索临时目录、用户/系统日志、仓库、`ms-ai-fast/logs` 与 unified log，均无本轮响应。 |
| AI Platform public audit API | NOT AVAILABLE | 只读 `/openapi.json` 仅包含 health/version/models 与 completion 入口，没有 request/audit/trace/log 查询接口；未调用 completion。 |
| Expected lineage delivery | PASS | receipt 的 2 图 lineage 完整；rendered messages 中两 image ID 各一次、series ID/manifest SHA/`UNKNOWN` 各两次，排除 expected lineage 未进入 Prompt context 的明显缺口。 |
| Specific mismatch field | UNKNOWN | 联合错误码覆盖 `image_id/series_id/sequence_no/projection/series_manifest_sha256`；rejected parsed result 未留存，无法确定具体字段或图片。 |
| Provider retry / remaining matrix | NOT RUN | 遵守 stop gate：未重发 `cat-02`，未运行其余七格。 |
| Business code/tests | NOT CHANGED / NOT RERUN | 本轮只更新非 archive durable handoff；保留此前代码与静态验证结果。 |
| Existing persistence capacity | PASS | AICall/Attempt 已有 provider request ID、response SHA、actual model，Attempt 已有 usage JSON；最小 Provider 摘要持久化无需新字段或 migration。 |
| Stable field-specific error capacity | PASS | 2–5 图 ordinal × 5 lineage 字段候选最长错误码为 60 字符，适配现有 `VARCHAR(80)`；无需保存 expected/actual 原值。 |
| Proposed code change | NOT AUTHORIZED / NOT RUN | 仅形成无 migration 最小 write-set 审核建议；未修改业务代码或执行新测试。 |
| Git diff whitespace | PASS | handoff 更新后 `git diff --check` 无输出。 |
| Handoff maintenance | PASS WITH SOFT WARNING | `--check` 为 `changed=0 / unresolved=0`；仅 `work-log.md` 超过 30 个日期段。因自动轮转会写受保护 archive，本轮未执行 compact/rotate。 |

## 2026-08-31 — Anatomy Localization 最小失败可观测性静态验证

| 检查 | 结果 | 说明 |
|---|---|---|
| Initial focused invocation | COMMAND ENV ERROR | 从 `apps/backend` 直接运行 pytest 时因仓库根路径未进入 `sys.path`，收集阶段报 `ModuleNotFoundError: apps`；未执行测试，也未修改代码或测试配置。 |
| Focused observability tests | PASS | `PYTHONPATH=. python3.12 -m pytest -q apps/backend/tests/test_ai_gateway_attempt_contracts.py -k 'provider_summary or definitive_failure or definite_failure or exact_lineage_mismatch or gateway_parse_failure or persists_receipt or network_dispatches_localization or network_localization_lineage_rejection'`：`12 passed, 244 deselected`。 |
| Gateway/Attempt contract file | PASS | `PYTHONPATH=. python3.12 -m pytest -q apps/backend/tests/test_ai_gateway_attempt_contracts.py`：`256 passed, 45 warnings`。 |
| Backend full tests | PASS | `PYTHONPATH=. python3.12 -m pytest -q apps/backend/tests`：`328 passed, 45 warnings`。 |
| Ruff | PASS | `python3.12 -m ruff check apps/backend`：All checks passed。 |
| Compileall | PASS | `PYTHONPATH=. python3.12 -m compileall -q apps/backend`：退出 0。 |
| Git diff whitespace | PASS | `git diff --check` 无输出。 |

## 2026-09-01 — 非分割 X-Ray Prompt 架构文档验证

| 检查 | 结果 | 说明 |
|---|---|---|
| `vet-platform` authority | PASS | 只使用 Git commit `6d1dd28bfb74143fb903503cdd08ced1f06a4d91` 的 `git show/grep/ls-tree`；当前脏工作树未作为历史代码事实。 |
| Legacy interface trace | PASS | Token 依赖、Session、主诉、上传、批量质检、报告、最终查询均有 commit:path:line；器官分割提交/状态明确排除。 |
| Legacy Prompt trace | PASS WITH UNKNOWN | 部位识别、Fusion A/B/C 猫犬正文完整阅读；大量 Grid/System/Crop Config key 有代码证据，但未读取旧 AI Config DB，未声称所有 key 的 Runtime 正文已绑定。 |
| Current `ms-image` trace | PASS | 核对 Runtime 公共接口、诊断 DAG、Stage provider 标志、Prompt command、Cat/Dog v4、Config 单 Prompt、Task 单 Config 和全 Study image loader。 |
| Target Prompt inventory | PASS | 目标固定为 Cat/Dog × 6 个 AI 阶段，共 12 个 independent Prompt identity；确定性节点明确无 Prompt。 |
| Concurrency/call accounting | PASS | Quality=N 并发，A/B=2 并发，Primary=1，Targeted=0/1，Report=1；Primary-only `N+4`，Targeted `N+5`。 |
| Scope check | PASS | 未设计第二 AIRequestService/Gateway/Provider/race；未把 segmentation/crop/bbox 带入目标运行链；未声称医学准确率提高。 |
| Business tests | NOT RUN | 本轮只新增/更新 Markdown 和 handoff 状态，没有业务代码或 Prompt/Schema 行为变化。 |
| External actions | NOT RUN | 未写 Nacos/DB/Provider/OSS/Broker/Docker，未启动 Runtime。 |
| Git diff whitespace | PASS | 新文档与本轮 handoff 更新通过 `git diff --check`。 |
| Handoff maintenance | PASS WITH SOFT WARNING | `maintain_handoff.py --check` 返回 `changed=0 / warnings=1 / unresolved=0`；`work-log.md` 为 61802 bytes/38 日期段。因 compact/rotate 会写用户受保护的 `.agent-handoff/archive*`，本轮未执行写入式轮转。 |

## 2026-09-01 — 项目级防偏移规则验证

| 检查 | 结果 | 说明 |
|---|---|---|
| 项目级 AGENTS 规则 | PASS | `AGENTS.md` Required Startup Routine 现在要求每次本项目任务先读取当前开发合同、核对完成能力总账，并声明单一目标、write set、外部权限、完成门和停止门。 |
| 项目会话入口同步 | PASS | `AGENT_SESSION_PROMPTS.md`、`docs/README.md` 和 `docs/refactor/README.md` 均指向当前开发合同；旧完整 XRay Prompt 已标为历史入口。 |
| 动态目标边界 | PASS | 具体 active objective 未硬编码进 `AGENTS.md`，继续由 snapshot 与用户授权决定。 |
| 当前入口与目标字段一致性 | PASS | `AGENT_HANDOFF.md` 指向 `AGENT_SESSION_PROMPTS.md` 的当前项目入口；`snapshot.md` 明确提供 `Active development objective`；Prompt 对缺失字段设置停止条件。 |
| Handoff 更新时间一致性 | PASS | `AGENT_HANDOFF.md` 和 `.agent-handoff/snapshot.md` 均为 2026-09-01。 |
| 文档与 whitespace | PASS | `git diff --check -- AGENTS.md AGENT_HANDOFF.md .agent-handoff/decisions.md .agent-handoff/work-log.md .agent-handoff/validation.md docs/ms-image-current-development-contract.md` 无输出。 |
| 外部操作 | NOT RUN | 未调用 Provider/Nacos/数据库/Docker，未启动 Runtime，未提交 Git。 |
| Existing persistence capacity | PASS | AICall/Attempt 的 provider request ID、actual model、response SHA 及 Attempt usage 字段已存在；Alembic 路径无本轮变更，无需 migration。 |
| Failure semantics | PASS | 测试覆盖 definite summary 完整性、非法/半套摘要拒绝、unknown 禁止摘要、HTTP rejection/Gateway parse 不伪造摘要、failed 路径不写 accepted parsed result。 |
| Provider / Runtime / external writes | NOT RUN | 遵守授权边界：未运行 E2E、Runtime launcher、Docker、Provider、Nacos/Config 写入或 Alembic migration。 |

## 2026-08-31 — 启用最小可观测性后的新 `cat-02` 单次 Runtime 验证

| 检查 | 结果 | 说明 |
|---|---|---|
| Frozen external preflight | PASS | Nacos exact Prompt、DB Prompt、冻结 Config、本地 `.md`、Schema、Label、Model snapshot 和 Pipeline SHA 一致；Cat/Dog Config active 且 frozen verify 通过；预算保持 `max_input_images=5 / max_total_calls=1 / max_total_attempts=1 / lane.max_attempts=1`。 |
| Dataset input preflight | PASS | `cat-02` 两张冻结 X-Ray 的路径、SHA、大小、顺序、projection 和 manifest 一致；运行前 RabbitMQ 主队列与 DLQ 均为空。 |
| Unique Runtime topology | PASS | 现有 launcher 启动 1 Runtime API、1 Relay、1 Worker，concurrency=1、consumer=1、Beat/reconcile=0；health/readiness 均为 200。 |
| Task and Stage topology | PASS | Task `917f9c5498bc4fdea26bb6f2993875f` 恰好 2 个 StageCheckpoint；Study Preparation completed，Localization Stage failed；没有 Localization finalization 或 Report Stage。 |
| Logical Call / Attempt topology | PASS FOR THIS FAILED CASE | 仅 1 个 Logical AICall `69233e53112c4c4da69319d0d7365aab`、1 个 primary Attempt `06f242e1d3a4417a97b28a08d9a67db3`；`attempt_no=1`、`reconcile_count=0`，没有第二 Attempt。该事实不能替代成功八格矩阵。 |
| Batch image transport | PASS | requested/sent/receipt=`2/2/2`；一次请求携带全部两张冻结原图。 |
| Provider transport | PASS | HTTP 200；`provider_request_id=chatcmpl-1788192611`、`actual_model=gemini-3.5-flash`、`response_sha256=4664c380cd38352a017f085538fbbe80c2afb90978151fcad0edd4dc82e851fb`。Provider 未返回 usage，故 `usage_json=null`。 |
| Localization result contract | FAIL-CLOSED | 通用 JSON Schema 通过后，冻结 validator 返回 `anatomy_localization_image_1_projection_mismatch`；AICall/Attempt/Localization Stage/Task 全部 failed，`winner_attempt_id=null`、`parsed_result_json=null`。未修正 lineage、未保存 rejected result。 |
| No Report boundary | PASS | `report_required=false`、`ai_medical_status=not_produced`、`current_report_id=null`、Report count=0。 |
| Stop gate | PASS | `cat-02` 未重试；`cat-03/04/05` 和 `dog-02/03/04/05` 均 NOT RUN；未增加 Attempt、修改预算、Prompt、Schema、Config 或 validator。 |
| Runtime cleanup | PASS | launcher 已停止；8002/8010 无监听，Runtime/Relay/Worker/lock 不存在；RabbitMQ 主队列与 DLQ 均 0 ready/0 unacked/0 consumers。 |
| Runtime log evidence | RECORDED OUTSIDE REPO | `/tmp/ms-image-anatomy-localization-rerun-20260831.Vq066r/local-chain.log`，SHA256 `e5cb94820161df8bf7a067b6a25683cd9f178cd6605d359091984ab4646738b5`；未保存 Provider body、Secret、Signed URL 或 rejected parsed result。 |
| Backend tests/Ruff/compileall | NOT RERUN | 本次续作没有业务代码变化；保留此前 12 focused、256 related、328 full、Ruff 和 compileall PASS 基线。 |
| Handoff maintenance | PASS WITH SOFT WARNING | `--check` 返回 `changed=0 / warnings=1 / unresolved=0`；仅 `work-log.md` 为 59091 bytes/36 日期段，超过日期段软阈值。因 compact/rotate 会写受保护 archive，本轮不执行。 |
| Git diff whitespace | PASS | `git diff --check` 无输出。 |

## 2026-09-01 — 宠物档案与 `pet-info` 迁移验证

| 检查 | 结果 | 说明 |
|---|---|---|
| migration revision/head | PASS | `20260901_01` / `down_revision=20260831_01`；`alembic current` 与 `heads` 均为 `20260901_01 (head)` |
| 目标物理表 | PASS | `ms_image.pet_profile`、`pet_profile_history`、`pet_info` 均已创建 |
| 表结构合同 | PASS | 三表单列 `VARCHAR(64)` `id` 主键；0 FK、0 enum/tenant 字段、0 空 comment |
| 源/目标数量 | PASS | source=`5091/152/0`；target=`5091/152/0` |
| 档案完整性 | PASS | missing=0、extra=0、owner mismatch=0、species mismatch=0、status mismatch=0、weight mismatch=0 |
| 档案幂等唯一性 | PASS | `source_pet_id` distinct=5091、`request_id` distinct=5091、总数=5091；第二次导入新增 0 |
| 头像转换 | PASS | 27 个验证 host URL 转 object key；目标 key 含 `://` 数=0；无效/第三方值未迁 |
| 品种完整性 | PASS | missing=0、extra=0、status mismatch=0；`(species, full_name)` distinct=152/152 |
| 不可靠转换门禁 | PASS | 874 个第三方品种图片未转 OSS key，ORM 读取 `image_keys_json=None`；152 个区间体重未填单值 |
| 源历史 | PASS / EMPTY SOURCE | `vet_platform.pet_profile_history=0`，目标历史=0，未伪造历史 |
| 相关 Ruff/compileall | PASS | pet Model/Schema/CRUD/Service/Endpoint 与 migration 均通过 |
| `git diff --check` | PASS | 无 whitespace error |
| 全量后端测试 | PASS | `PYTHONPATH=<repo> uv run pytest apps/backend/tests -q`：`328 passed, 45 warnings in 1.17s` |
| conda pytest 尝试 | ENVIRONMENT FAIL | `/opt/homebrew/anaconda3/envs/ms-image` 缺少 `jinja2`，收集失败；改用具备项目依赖的 `uv run` 后全量通过 |
| `alembic check` | KNOWN UNRELATED DRIFT | 只检测到既有 `ai_api_connection.secret_ref` comment drift；宠物 migration 未夹带该项 |
| 路由/分层 | PASS | 8 条 pet 路由，无 `/{id}`；endpoint/Service 未直接拼 SQL，复用 Service/DAL |
| 真实 HTTP API CRUD/CAS/history E2E | NOT RUN | 数据库建表与 legacy 导入已完成；API 并发事务资格仍可作为上线前独立步骤 |
| 源仓库写入 | NONE | `vet-platform` 始终只读 |

## 2026-09-01 — xray_quality_control 发布状态与真实资格回读

| 检查 | 结果 | 说明 |
|---|---|---|
| Nacos Cat exact readback | PASS | `ms-image.x-ray.image-quality.cat.zh-CN@1.0.0` 存在；remote/local normalized SHA 均为 `a0486c38f16d2683eba9e77568d20457a04eeb24cc170893c2c4859d24e87c1d`。 |
| Nacos Dog exact readback | PASS | `ms-image.x-ray.image-quality.dog.zh-CN@1.0.0` 存在；remote/local normalized SHA 均为 `bc6ae0cabc78026df618bd0eb71fdb9be87f3de5c3e13d7743ae5e9183688438`。 |
| DB Prompt/active Config readback | PASS | Cat/Dog DB Prompt 均 validated；Config `2246ac...` / `03dc97...` 均 active、state version 2、profile `xray_image_quality_v1`，Prompt SHA 与 Nacos/本地一致。 |
| Cat Task persistence | PASS | `c1cea8...` completed；2 Stage completed；Call `9d8a12...` succeeded/accepted；Attempt `dee6c5...` succeeded；2 图 sent；Report count 0。 |
| Cat GET Quality reconstruction | PASS | `TaskService.get_xray_quality_review()` 通过冻结 Config/Schema/receipt/result lineage 重验；两图均 `primary_body_part=thorax`、`observed_projection=ventrodorsal`、`quality_status=limited`。 |
| Dog committed Study readback | PASS | Study `89573c...` 当前 `ready`，revision `610b22...`，state version 4；Task count 0。 |
| Dog Provider | NOT CALLED | 首次 Quality POST 在 Task 创建前 HTTP 409；没有 Dog Task/Call/Attempt，不得表述为 Provider 失败。 |
| Business code/write | NONE | 本轮仅只读 Nacos/DB 核验和 handoff 更新；未覆盖 Prompt/Config，未调用 Provider，未启动 Runtime/Relay/Worker/Docker。 |
| Handoff maintenance | PASS WITH WARNING | `--compact-if-needed`：`changed=2 / warnings=1 / unresolved=0`；按维护合同轮转 1 个旧 work-log 日期段。 |

## 2026-09-01 — 目标诊断链 10 个 Prompt Nacos exact 发布

| 检查 | 结果 | 说明 |
|---|---|---|
| 本地 Prompt 资产 | PASS | 10 个 Cat/Dog Markdown 文件存在；Jinja parse、required variables、Strict render、species identity 和 undeclared-variable 检查通过。 |
| Admin API capability | PASS | `/v3/admin/ai/prompt/draft` Allow=`DELETE,PUT,POST,OPTIONS`；`submit`、`publish` Allow=`POST,OPTIONS`。 |
| 发布前 immutable preflight | PASS | 10 个目标均通过 Client exact `1.0.0` GET + Admin governance 双重检查为 absent；无 metadata/draft/reviewing/online 冲突。 |
| 正式发布生命周期 | PASS | 逐项 `draft → submit`；当前无 Prompt publish pipeline，submit 自动 online；未调用 force publish。 |
| StudyScreening exact readback | PASS | Cat SHA `a3cede45…e88a8`；Dog SHA `a926224c…a4d8`；均 online/latest `1.0.0`。 |
| SystemAnalysis exact readback | PASS | Cat SHA `9cad906f…7823a`；Dog SHA `c6bc6447…04c25`；均 online/latest `1.0.0`。 |
| PrimaryCaseAdjudication exact readback | PASS | Cat SHA `497625c0…ed71`；Dog SHA `d965ed0a…f1c`；均 online/latest `1.0.0`。 |
| TargetedReview exact readback | PASS | Cat SHA `79986898…1f6`；Dog SHA `b47cefca…0d44`；均 online/latest `1.0.0`。 |
| ReportGeneration exact readback | PASS | Cat SHA `b94d939c…bf61`；Dog SHA `78946568…7219`；均 online/latest `1.0.0`。 |
| 数据库/Config/Provider/Runtime | NOT RUN | 本轮无授权；未 import Prompt、未创建或激活 Config、未调用 Provider、未启动 Runtime/Relay/Worker/Docker。 |
| Handoff maintenance | PASS WITH WARNING | 已安装脚本 `--compact-if-needed`：`changed=2 / warnings=1 / unresolved=0`；轮转 1 个旧 work-log 日期段。 |


## 2026-09-01 — Quality commit-before-response 与错误归属回归

| 检查 | 结果 | 说明 |
|---|---|---|
| 4 个 Runtime endpoint compileall | PASS | `sessions.py`、`studies.py`、`tasks.py`、`xray_quality.py`。 |
| 4 个 Runtime endpoint Ruff | PASS | 无 lint error。 |
| 4 个 Runtime endpoint `git diff --check` | PASS | 无 whitespace error。 |
| Gateway/Attempt contracts | PASS | `PYTHONPATH=. pytest -q apps/backend/tests/test_ai_gateway_attempt_contracts.py`：`256 passed, 45 warnings`。 |
| Ready Study 预检 | PASS | Study `89573c...` ready、state version 4、revision `610b22...`、2 张 ready images。 |
| Quality POST | PASS | HTTP 201；Task `8c854ca7d4f64de2943928accb5dedbb`；约 53.37 ms。 |
| POST 后立即 GET | PASS | 无 sleep，第一次 `GET /api/v1/tasks?id=8c854...` 直接 HTTP 200；commit-before-response 可见性回归通过。 |
| Cancel 后立即 GET | PASS | Cancel HTTP 200；紧接 GET HTTP 200，state version 1、`cancel_requested_at` 已持久化。 |
| 同 request_id 幂等重放 | PASS | 再次 POST HTTP 201，返回同一 Task ID；未创建第二个 Task。 |
| DAL persistence | PASS | Task queued/cancel_requested；1 Stage queued；1 Outbox pending；AICall 0、Attempt 0、Report 0。 |
| Provider/Nacos/其他组件 | NOT CALLED / NOT STARTED | 本轮未调用 Provider、未写 Nacos、未启动 Relay/Worker/Docker。 |
| Runtime shutdown | PASS WITH KNOWN WARNING | Runtime 已停止，端口 8002 未监听；存在既有 aiomysql event-loop teardown warning，不影响 HTTP/commit 证据。 |
| 历史错误归属 | CONFIRMED / PARTIAL UNKNOWN | HTTP 409 归属 ms-image Runtime Task 创建边界，非 Provider 429；历史精确 `TaskStateConflictError` 子类型因缺少原始稳定错误码保持 UNKNOWN。 |


## 2026-09-01 — Quality commit-before-response 追加 5 次稳定性回归

| 检查 | 结果 | 说明 |
|---|---|---|
| 重复次数 | PASS | 同一 ready Dog Study/Revision，5 个全新 request_id；累计初次回归共 6 次。 |
| Quality POST | 5/5 PASS | 全部 HTTP 201；耗时 14.28–68.36 ms；未出现 409/429/5xx。 |
| POST 后无等待立即 GET | 5/5 PASS | 全部第一次 GET HTTP 200；耗时 4.86–6.83 ms；未出现 404。 |
| Cancel 与立即 GET | 5/5 PASS | Cancel 全部 HTTP 200；紧接 GET 全部 HTTP 200，cancel_requested 已持久化、state version 1。 |
| 相同 request_id 幂等重放 | 5/5 PASS | 全部 HTTP 201 并返回原 Task ID，没有重复 Task。 |
| DAL 逐 Task 持久化核验 | 5/5 PASS | 每个 Task queued/cancel_requested、1 Stage queued、1 Outbox pending、AICall 0、Attempt 0、Report 0。 |
| 外部调用边界 | PASS | Provider/Nacos 未调用；Relay/Worker/Docker 未启动，因此测试只覆盖 Runtime 与数据库事务边界。 |
| Runtime cleanup | PASS WITH KNOWN WARNING | Runtime 已停止，端口 8002 未监听；关闭时存在既有 aiomysql event-loop teardown warning。 |
| 最终结论 | PASS / CLOSED | commit-before-response 回归累计 6/6 PASS；历史 409 归属 Runtime，但当前问题不再复现，按用户要求关闭。 |

## 2026-09-01 — StudyScreening 静态验证与外部状态边界

| 检查 | 结果 | 说明 |
|---|---|---|
| Focused contract tests | PASS | `PYTHONPATH=. python3.12 -m pytest -q apps/backend/tests/test_ai_prompt_control_plane_contracts.py apps/backend/tests/test_ai_gateway_attempt_contracts.py`：`326 passed, 45 warnings`。 |
| Backend full tests | PASS | `PYTHONPATH=. python3.12 -m pytest -q apps/backend/tests`：`335 passed, 45 warnings`。 |
| Ruff | PASS | StudyScreening相关源码与两个既有测试文件无 lint error。 |
| compileall | PASS | StudyScreening相关源码可编译。 |
| Git diff whitespace | PASS | StudyScreening相关 write set `git diff --check` 无输出。 |
| Runtime command construction | PASS | 专项测试首次发现 `prompt_mode_invalid`，局部修复后 Stage 可构造 `prompt_kind=study_screening` 的 quality-bound AI request。 |
| Nacos historical exact publish evidence | PASS / HISTORICAL FACT | 既有发布记录确认 Cat `a3cede45…e88a8`、Dog `a926224c…a4d8` 均 online/latest `1.0.0`；运行前仍必须实时回读完整正文和 SHA。 |
| DB Prompt/Config | NOT RUN / UNKNOWN | 目标 Prompt 发布轮次明确未 import Prompt、未创建/激活 Config；本轮未连接数据库核对。 |
| Provider/Runtime | NOT RUN | 尚未创建 StudyScreening diagnose Task，未调用 Provider，未启动 Runtime/Relay/Worker/Docker。 |
| Medical accuracy | UNKNOWN / NO-GO | 静态工程合同不能证明筛查医学准确率。 |


## 2026-09-01 — StudyScreening Prompt Import 422 无持久化诊断

| 检查 | 结果 | 证据/备注 |
|---|---|---|
| `PromptImportRequest.model_validate` | PASS | Cat import 请求字段与 namespace 长度合法 |
| Nacos exact fetch | PASS | Data ID `ms-image.x-ray.study-screening.cat.zh-CN`，record version `1.0.0` |
| normalized content SHA | PASS | `a3cede45fbda09f07de16bf0289c9b8604a045499b6c6f369103dfc7634e88a8`，与冻结 Cat Prompt 一致 |
| inferred variables | PASS | `OUTPUT_SCHEMA_JSON`、`QUALITY_RESULTS_JSON`、`SAFE_STUDY_CONTEXT_JSON` |
| PromptImport variable resolution | PASS | required count=3 |
| message contract normalization | FAIL-CLOSED | `AIControlValidationError: prompt_message_contract_invalid`；现有 allowlist 不含 `QUALITY_RESULTS_JSON` |
| DB failure residue | PASS | Audit absent；`xray_cat_study_screening@1.0.0` absent；显式 rollback |
| Runtime/Provider | NOT RUN | 按停止门禁止启动或调用 |
| 运行告警 | NON-BLOCKING | DB 只读脚本结束出现既有 aiomysql event-loop teardown warning；查询结果已返回，不纳入当前修复范围 |


## 2026-09-01 — StudyScreening Cat Runtime 首次资格化

| 验证 | 结果 | 说明 |
|---|---|---|
| `TaskService._load_verified_xray_quality_review(c1cea8...)` | PASS | requester/Study/Revision/manifest/species/Stage/Call/output SHA 全匹配；2 图、complete |
| Local chain health/readiness | PASS | Runtime 8010、单 Relay、单 imaging Worker、consumer=1、Beat disabled |
| `POST /api/v1/tasks`（仅一次） | HTTP 201 | Task `e004c8790df349c28342a98a36a1d856`，Root Config `749920...@5.0.0` |
| Task 轮询 | FAILED-CLOSED | queued → running → failed；`ai_medical_status=not_produced`；Report 0 |
| StudyPreparation | PASS | Stage completed，retry_count=0 |
| StudyScreening Provider 调用 | HTTP 200 / CONTRACT REJECTED | 1 Call / 1 Attempt；2/2/2 图；manifest SHA 一致；actual model `gemini-3.5-flash` |
| Stable failure | `study_screening_source_projection_mismatch` | Call/Attempt/Stage/Task 一致；winner null；无第二 Attempt |
| Provider audit | RECORDED | request ID `chatcmpl-1788270879`；response SHA `3a5f3736fd107e3852f95fc375ee54e460a86a45e386ddd4a44f6a821509e80e` |
| Frozen projection readback | PASS | Safe Context 与 Quality Result 两图均为 caller-declared `UNKNOWN` |
| Rejected actual projection | UNKNOWN | rejection 路径未保存 parsed result/source_refs，不猜测 DV/VD/LL |
| Stop gate / cleanup | PASS | 未重试、未改 Prompt/Schema/validator、未进 SystemAnalysis；8010/Relay/Worker/lock 已清理 |
| Runtime shutdown | WARNING | 既有 aiomysql event-loop closed teardown warning；不改变已持久化失败证据 |


## 2026-09-01 — StudyScreening projection mismatch 无 Provider只读审计

| 验证 | 结果 | 说明 |
|---|---|---|
| Cat/Dog Prompt `1.0.0` source_refs 文案 | GAP CONFIRMED | 只要求真实引用；未要求五个 lineage 字段逐字复制、UNKNOWN 不得改写或全图覆盖 |
| `study_screening.v1.schema.json` projection | CONTRACT DRIFT CONFIRMED | `type=[string,null]`；frozen receipt/manifest 要求非空 string，validator 要求严格相等 |
| Runtime lineage validator | PASS / FAIL-CLOSED | 精确比较 image/sequence/series/manifest/projection，并要求 source_refs 覆盖全部 receipt images |
| Definite rejection persistence | AUDIT GAP CONFIRMED | 保存 request ID/model/usage/response SHA/error code；不保存 rejected parsed result 或 response ObjectRef |
| Existing tests | PARTIAL | 有 projection mismatch validator 回归；无 UNKNOWN+caller_declared、Schema null、Prompt lineage/coverage 组合回归 |
| Provider/Runtime/Nacos/DB | NOT RUN | 本轮纯只读；未重试、未修改外部状态、未进入 SystemAnalysis |
| Projection error granularity | GAP CONFIRMED | 稳定码为聚合 `study_screening_source_projection_mismatch`，无图片 ordinal/字段路径 |

## 2026-09-02 — StudyScreening 架构裁决只读验证

| 检查 | 结果 | 证据/备注 |
|---|---|---|
| Startup/handoff/development contract | PASS | 已读取 `AGENT_HANDOFF.md`、snapshot/risks/backlog、`docs/ms-image-current-development-contract.md`；当前唯一目标仍为 StudyScreening |
| Snapshot→Prompt→receipt→validator | PASS | `task_service.py`、`prompt_commands.py`、`ai_request_service.py`、`study_screening_contract.py` 逐边界点验 |
| Provider schema vs runtime lineage | DRIFT CONFIRMED | v1 Schema projection=`string|null`，Prompt 无逐字段复制要求，validator 与 receipt strict equality |
| Stage canonicalization feasibility | PASS / DESIGN ONLY | AICall 与 Attempt 已持久化 receipt；内部 call_result 当前不含 receipt，增加该内部字段即可由 v2 Stage 纯函数 canonicalize，无 DB 变更 |
| AICall raw / Stage canonical boundary | RECOMMENDED | `parsed_result_json` 当前表示 Schema-valid Provider 结果；Stage output 是独立持久业务结果，适合保留两层证据 |
| Downstream Screening consumption | GAP CONFIRMED | checkpoint 会传 `previous_output`，但 `build_primary_ai_request_command()` 不读取 `study_screening_result`；当前仅顺序接入 |
| Runtime/Provider/Nacos/DB | NOT RUN | 本轮只读分析与 handoff 更新；没有外部写入或真实链路执行 |
| Business tests | NOT RUN | 未修改业务代码；不以只读分析冒充静态或 Runtime 资格 |

## 2026-09-02 — StudyScreening 联合分析收口验证

| 检查 | 结果 | 说明 |
|---|---|---|
| 完成能力台账 | PASS | 目标保持 StudyScreening；未重复实现既有 Task/Stage/AICall/Gateway/receipt 能力 |
| 文档与源码定向点验 | PASS | 四层合同漂移、AICall raw / Stage canonical 边界及 Primary 未消费 Screening 缺口均有直接出处 |
| 外部与业务写入边界 | PASS | 未修改业务代码、Prompt、Schema、配置；未写 Nacos/数据库，未调用 Provider 或启动 Runtime |
| Handoff validation 归档 | PASS | 最早三个完整验证 section 已归档，主文件保留最新 StudyScreening 证据并降至 64 KiB 以下 |
| Handoff maintenance / diff check | PASS | compact/check 均为 changed=0 warnings=0 unresolved=0；`git diff --check -- .agent-handoff/` 通过 |


## 2026-09-02 — StudyScreening 解决方案设计验证

| 检查 | 结果 | 说明 |
|---|---|---|
| v1 动态合同职责点验 | PASS | 版本、物种、receipt、image/sequence、series/manifest/projection、coverage、cross-reference、family coverage 均按源码确认 |
| 修复边界 | PASS / DESIGN ONLY | Prompt-only 与 validator 放宽均排除；v2 anchor + receipt canonicalization 可复用现有 AICall/Attempt 字段，无 DB migration |
| 合同身份分离 | REQUIRED | Provider raw anchor 形状与 Stage canonical 完整形状必须可区分，不得以同一含义不明的 contract version 表达 |
| 验收隔离 | REQUIRED | 先独立 StudyScreening v2，再验收 Root diagnose/Primary consumption；SystemAnalysis 仍未进入 |
| Runtime/Provider/Nacos/DB | NOT RUN | 本轮只读设计与 handoff 更新，无外部写入 |

## 2026-09-02 — StudyScreening v2 Cat 工程 Runtime PASS

| 检查 | 结果 | 证据 |
|---|---|---|
| Nacos exact readback | PASS | `ms-image.x-ray.study-screening.cat.zh-CN@2.0.0`，SHA `ab6169...c0114`，cat→cat，fallback=false |
| DB Prompt | PASS | ID `1b53fa77778e4fd1b74ba7c985f3c5a6`，validated |
| Config frozen verify | PASS | ID `39c17d76abb145fdabc06bdf4ecf7268`，active；Config SHA `3ce197...d891` |
| Task/Stage | PASS | Task `2c48ad93315145d19faa1f89b47b0d50` completed；preparation:v1、screening:v2 completed；retry=0 |
| Logical Call | PASS | `2a2e7a7c75624894a261a41305eb3f22` succeeded/accepted |
| Physical Attempt | PASS | `fab095fec7ac4df091c992fbf4fd9eed`；attempt_no=1；Provider HTTP 200；无第二 Attempt |
| Image receipt | PASS | requested/sent/receipt=`2/2/2` |
| Provider/Canonical boundary | PASS | raw=`xray-study-screening-provider.v2`；Stage=`xray-study-screening.v2`；Attempt raw == AICall raw |
| Report isolation | PASS | Report count=0 |
| Runtime cleanup | PASS | 8002/8010 free；launcher lock absent |

结论：`STUDY_SCREENING_V2_ENGINEERING_RUNTIME_PASS`。医学准确性未验证：`MEDICAL_ACCURACY_UNKNOWN / MEDICAL_RELEASE_NO_GO`。

## 2026-09-02 — StudyScreening v2 收尾文件检查

- Handoff maintenance `--compact-if-needed`: PASS；`unresolved=0`，仅轮转 1 个旧 work-log section。
- 未重新运行 Provider、Runtime 或业务测试；本次收尾只修改合同与 handoff 状态。

## 2026-09-02 — Primary 与可达后续链路真实 Runtime 验证

| 检查 | 结果 | 证据 |
|---|---|---|
| 本轮 Screening 证据隔离 | PASS | `StudyScreening=ASSUMED_PASS`；Task Profile 未创建 screening checkpoint，不冒充真实同链 PASS |
| Runtime owner/readiness | PASS | 唯一 launcher；readiness 200；one imaging consumer；reconcile disabled |
| E2E execution | PASS | 单次 `cat-02`；Task `5c6c5612609a4e438c06e39cc6e2848b` completed；无重跑 |
| Primary Stage | PASS | `joint_primary_reader:v2` completed，retry=0 |
| Logical Call | PASS | `e4862fdb9ec34e569b7bee94ac0660ca` succeeded/accepted，error=null |
| Physical Attempt | PASS | `617c327e6ed34e2890ef514313a86fab`，attempt_no=1，HTTP 200，reconcile=0，无第二 Attempt |
| Image receipt | PASS | requested/sent/receipt=`2/2/2`；receipt=`ai-image-receipt.v2` |
| Dynamic lineage | PASS | 两个 source_ref 的 image_id/series_id/projection/manifest_sha256 对 Receipt 全匹配；Receipt 对 Snapshot 全匹配 |
| Result contract | PASS | `xray-complete-medical-result.v2`；source_refs=2；findings=1；medical_status=normal |
| Family routing | PASS | `family_routing:v2` completed；route=`primary_final`；Primary result 保持一致 |
| TargetedReview | NOT TRIGGERED | `targeted_candidate` 不存在；无 targeted stage/call；不得记为 Runtime PASS |
| DecisionFinalization | PASS | `decision_finalization:v2` completed；selected_owner=primary；source Stage/Call 精确 |
| Report persistence | PASS | Report `fde7e262df494b559eb27a0c77511bbc` final；Task pointer、source Stage/Call 一致 |
| Status persistence boundary | PASS | Stage availability `produced` → persisted model status `normal`；定向 pytest `2 passed, 3 warnings` |
| SystemAnalysis | NOT RUN | experiment Profile 不包含该 Stage |
| ReportGeneration AI | NOT RUN | Profile 无独立 AI Stage；仅验证 DecisionFinalization + ReportService |
| Runtime cleanup | PASS | 8002/8010 free；launcher lock absent |
| Business code/config writes | NONE | 未修改业务代码、Prompt、Schema、Nacos 或 Config |
| Handoff maintenance | PASS | 归档最早完整 validation sections 后，installed skill check `warnings=0 / unresolved=0`；`.agent-handoff/` diff-check 通过 |

结论：Primary、FamilyRouting、DecisionFinalization 与 ReportService 的本次 Cat 工程链真实通过；SystemAnalysis、条件 TargetedReview 和独立 ReportGeneration AI 仍没有本轮 Runtime 证据。医学准确率保持 UNKNOWN。

## 2026-09-02 — Cat SystemAnalysis 独立工程 Runtime PASS

| 检查 | 结果 | 证据 |
|---|---|---|
| Prompt exact import/readback | PASS | `xray_cat_system_analysis@1.0.0`；Prompt ID `309e7f...`；SHA `9cad90...` |
| Config lifecycle/frozen integrity | PASS | Config `bbdd49c7...` active；Config/Schema/Pipeline SHA 均匹配 |
| Frozen Quality lineage | PASS | Quality Task `c1cea89e...`；source Call `9d8a1225...`；2 images；Manifest `a59eb2...` |
| Runtime Task | PASS | Task `4e1165980fde4facae1793e637d77cc7` completed；无第二 Task/重跑 |
| Stage topology | PASS | `study_preparation:v1:completed`；`system_analysis:v1:completed` |
| Logical Call | PASS | exactly 1；succeeded/accepted；actual model `gemini-3.5-flash` |
| Physical Attempt | PASS | exactly 1；attempt_no=1；succeeded；reconcile_count=0；Provider HTTP 200 |
| Image lineage | PASS | requested/sent/receipt=`2/2/2`；2 source refs 覆盖冻结 Receipt |
| Result contract | PASS | Schema validate + `xray-system-analysis.v1` dynamic contract validator；species=cat；5 systems |
| Stage persistence | PASS | `source_call_id`、`system_analysis_result`、`output_sha256` 一致 |
| Report isolation | PASS | Report count=0；Task report pointer=null |
| Completion gate artifact | PASS | `/tmp/ms-image-system-analysis-20260902.xu2YPr/system-analysis-completion-gate.json`，`completion_gate=PASS` |
| Prompt Import code validation | PASS | 相关后端全量 `353 passed, 45 warnings`；Ruff PASS；compileall PASS；diff-check PASS |
| Runtime cleanup | PASS | 8002/8010 free；lock absent；无 launcher/Runtime/Relay/Celery 残留 |
| Handoff closeout | PASS | maintenance `changed=0 warnings=0 unresolved=0`；相关文件 `git diff --check` PASS |
| Medical accuracy | NOT RUN / UNKNOWN | 无 Gold、Scorer、Holdout；`MEDICAL_RELEASE_NO_GO` |

结论：`SYSTEM_ANALYSIS_CAT_ENGINEERING_RUNTIME_PASS`。本结论只覆盖独立 SystemAnalysis 工程链，不覆盖 Dog、同 Task 完整诊断链、TargetedReview、ReportGeneration AI 或医学准确性。

## 2026-09-02 — 诊断链中文注释静态与合同验证

| 检查 | 结果 | 证据 |
|---|---|---|
| 目标范围 | PASS | 5 个 HTTP endpoint 文件、8 个 Stage 文件、1 个 ReportService 文件，共 14 个文件 |
| OpenAPI 中文摘要 | PASS | 目标 Session/Study/Series/Image/Task/Report 路由均存在中文 `summary` |
| HTTP 边界说明 | PASS | 覆盖 OSS 外部 PUT、prepare/complete 状态边界、Task 201 异步语义、纯读轮询、Report `data=null` |
| Stage 边界说明 | PASS | 覆盖 Logical Call/Provider 所有权、lineage/canonicalization、fail-closed、Targeted 最多一次条件执行 |
| Report 边界说明 | PASS | 明确无独立 ReportGeneration AI；ReportService 只校验、幂等、CAS、版本持久化和查询 |
| Python 编译 | PASS | `python3.12 -m compileall -q <14 target files>`，无输出 |
| Ruff | PASS | `ruff check <14 target files>` → `All checks passed!` |
| 定向合同测试 | PASS | `test_ai_gateway_attempt_contracts.py` 定向表达式 → `14 passed, 269 deselected, 3 warnings` |
| 空白与补丁格式 | PASS | `git diff --check -- <14 target files>`，无输出 |
| Runtime/Provider/Nacos/DB/Docker | NOT RUN | 本轮为注释任务，不进行任何外部调用或真实 Runtime 执行 |
| 业务行为变化 | NONE | 仅中文注释、docstring、OpenAPI `summary` 与必要排版 |

警告说明：1 条 Pydantic class-based config 弃用告警、2 条 `datetime.utcnow()` 弃用告警，均为既有代码告警，与本轮注释修改无关。

## 2026-09-02 — TargetedReview 本地工程合同验证

| 检查 | 结果 | 说明 |
|---|---|---|
| Targeted 定向合同测试 | PASS | `PYTHONPATH=. python3.12 -m pytest -q apps/backend/tests/test_ai_prompt_control_plane_contracts.py apps/backend/tests/test_ai_gateway_attempt_contracts.py -k targeted`：`12 passed, 1 warning` |
| 合同测试全量 | PASS | 同两文件全量：`356 passed, 45 warnings`；历史双模式用例保持通过 |
| Backend 全量 | PASS | `PYTHONPATH=. python3.12 -m pytest -q apps/backend/tests`：`365 passed, 45 warnings` |
| 递归 candidate 防护 | PASS | 独立 Targeted Prompt 再返回 `targeted_candidate` 时 `targeted_review_recursive_candidate_forbidden` fail-closed，无医学结果覆盖 |
| 静态检查 | PASS | Ruff、Python 3.12 compileall、`git diff --check` 均通过 |
| Provider/Runtime/Nacos/DB/Docker | NOT RUN | 本轮仅本地代码与合同验证，未产生真实调用或外部写入 |
| 资格结论 | NOT RUNTIME QUALIFIED | Targeted 仍无本轮真实 Provider 证据；同 Task 完整主链、ReportGeneration AI 和医学准确率继续 UNKNOWN/NO-GO |

警告说明：45 条为既有 Pydantic/`datetime.utcnow()` 弃用告警，不影响本轮合同结论。

## 2026-09-02 — Localization 主链关联设计审计

| 检查 | 结果 | 说明 |
|---|---|---|
| 完成能力总账与 handoff 启动文件 | PASS | 已读取 required startup files，并核对合同第 3 节 Anatomy Localization 与接口边界 |
| Task 直接关联字段检索 | ABSENT | Task model/schema/response 未发现 source/parent/upstream/related task 字段 |
| 现有 Localization 查询入口 | CONFIRMED | `GET /anatomy-localizations?task_id=` 只接受 Localization Task ID |
| 临时 Study/Revision 关联 | INSUFFICIENT | 可缩小候选集合，但无法证明属于特定 diagnose Task |
| 推荐实现 | DESIGN ONLY | `source_task_id` + 主链反查 + 冻结 Snapshot 一致性校验；尚未实施 |
| Tests / Runtime / External writes | NOT RUN | 本轮无业务代码变更；未调用 Provider/Nacos/DB/OSS/Broker |

## 2026-09-03 — TargetedReview / ReportGeneration / 同 Task 全链真实证据复核

| 检查 | 结果 | 证据 |
|---|---|---|
| Diagnose Task | PASS | `ae3c77dd32a34a938eaee6f167d438d6` completed；medical status abnormal；current Report `a65a33292e354c36baffb71e4c4b571c` |
| 八阶段拓扑 | PASS | `study_preparation → study_screening → system_analysis → joint_primary_reader → family_routing → targeted_review → decision_finalization → report_generation` 全部 completed |
| TargetedReview 单 Stage | PASS | Stage `866f01...`；Call `b3706e...` succeeded/accepted；Attempt `b67d89...` succeeded；Provider request id/response SHA 存在；3/3/3 图片；route=`thoracic/lung_pattern` |
| ReportGeneration 单 Stage | PASS | Stage `3f8c18...`；Call `c63f93...` succeeded/accepted；Attempt `6cb133...` succeeded；Provider request id/response SHA 存在；0/0/0 图片合同 |
| Prompt/Config/Model | PASS | Targeted Config `56e2e22...`、Report Config `f0674d5...` active；对应 Prompt validated；requested/actual model=`gemini-3.5-flash` |
| Frozen medical lineage | PASS | ReportGeneration `final_medical_result` 等于 DecisionFinalization 冻结结果；Python 未重写医学内容 |
| Final Report lineage | PASS | Report final、唯一 current；source Stage=`3f8c18...`、source Call=`c63f93...`、Task pointer 一致 |
| Evidence artifact | PASS | `/tmp/ms-image-xray-full-chain-evidence-20260903-targeted-r3/engineering-candidate-cat-03-20260902T160745Z-34de55df.json`；mtime `2026-09-03 00:07:45 +0800`；qualification PASS；8/5/5 |
| 主线程断言 | PASS | inline Python 输出三个 PASS：Targeted 单 Stage、ReportGeneration 单 Stage、same-task full chain |
| 独立只读审计 | PASS | DB 与 evidence 交叉一致；确认 Call/Attempt receipt、request id、response SHA、Config/Prompt/Model 和 lineage |
| 当前 Runtime 健康 | STOPPED / NOT A FAILURE | `curl 127.0.0.1:8010` 连接失败，旧 launcher 进程已退出；不影响已持久化 Task 资格 |
| 新 Provider 请求 | NOT RUN | 已有真实证据满足完成门，未重复创建 Task/Attempt 或消耗 Provider |
| 医学准确率 | UNKNOWN / NO-GO | 未运行 Gold、医学 Scorer、Failure Bank 或 Holdout |

## 2026-09-03 — Git 交付前验证

| 检查 | 结果 | 说明 |
|---|---|---|
| Backend 全量测试 | PASS | `PYTHONPATH=. /opt/homebrew/anaconda3/bin/pytest apps/backend/tests -q` → `379 passed, 48 warnings in 1.25s` |
| 首次 pytest 环境检查 | EXPECTED ENV FAILURE | `python3 -m pytest` 使用 Homebrew Python 3.13，环境未安装 pytest；不是代码失败 |
| 第二次 pytest 导入检查 | EXPECTED ENV FAILURE | Anaconda pytest 首次未设置 `PYTHONPATH=.`，报 `ModuleNotFoundError: apps`；补齐后全量通过 |
| Python 编译 | PASS | `python3 -m compileall` 与 changed/untracked Python `py_compile` 均通过 |
| Prompt / Postman JSON | PASS | 所有本轮资产可解析 |
| 宠物迁移结构 | PASS | 无 foreign key、无 enum，目标三表存在；新 Model/Schema/DAL/Service/API 模块导入通过 |
| Secret 扫描 | PASS | 未发现真实凭据；测试中的 `secret-token` / `test-secret` 为 mock 值 |
| Handoff archive | PASS | 216 个索引引用全部存在，0 missing；108 个本次新增 archive 文件纳入后续文档提交 |
| Patch 格式 | PASS | 功能提交前 `git diff --cached --check` 通过；补充 harness 提交前检查通过 |
| 功能提交 | PASS | `ee2fa3a`，86 files / 19729 insertions / 291 deletions |
| Harness 补充提交 | PASS | `2b7d66b`，1 file / 43 insertions / 20 deletions |
| Runtime/Provider/Nacos/DB/OSS/Broker | NOT RUN | 本轮仅 Git 收口；未产生业务外部调用或写入 |

## 2026-09-03 — Git 推送与新分支验证

| 检查 | 结果 | 说明 |
|---|---|---|
| Source branch push | PASS | `git push -u origin codex/xray-anatomy-localization-v1` 创建远端分支并设置 upstream |
| Target branch collision precheck | PASS | 本地无同名分支；`git ls-remote --heads` 确认远端无 `codex/per-flow-model-routing` |
| Target branch create/push | PASS | 从 `adbd2b1` 创建并 `git push -u origin codex/per-flow-model-routing` 成功 |
| Branch tracking | PASS | 两个本地分支分别跟踪对应 `origin/*`，均指向 `adbd2b1` |
| Force/history rewrite | NOT USED | 未执行 force push、reset、clean、restore、rebase 或 amend |
| Runtime/Provider/Nacos/DB/OSS/Broker | NOT RUN | Git 交付与分支创建不触发业务外部系统 |


## 2026-09-03 — code-owned AI/Prompt 路由验证

| 检查 | 结果 | 说明 |
|---|---|---|
| Gateway/Attempt 定向合同 | PASS | `299 passed, 48 warnings`；覆盖请求冻结、Attempt、Gateway 和既有失败语义。 |
| Mock Prompt→Gateway 全链 | PASS | `6 passed, 4 warnings`；覆盖 Prompt HTTP Render 合同、Stage Worker、Call/Attempt、Gateway，以及无 Config DB 的 Task/lineage。 |
| Backend 全量测试 | PASS | `381 passed, 48 warnings`；warnings 为已有 Pydantic 与 `datetime.utcnow()` 弃用警告。 |
| Python compile | PASS | `python -m compileall -q apps/backend`。 |
| Ruff changed files | PASS | NUL-safe 文件列表复核通过；首次 zsh scalar 调用仅因换行列表未拆分产生 `E902 File name too long` 工具调用错误，不是源码诊断。 |
| Patch whitespace | PASS | `git diff --check`。 |
| 真实 Prompt Runtime / ms-ai-platform / Provider E2E | ENVIRONMENT_BLOCKED | Prompt/Platform/DB/RabbitMQ 环境变量未配置且 Docker 不可用；本轮没有发起真实外部调用。 |


## 2026-09-03 — code-owned AI 路由 Git 交付验证

| 检查 | 结果 | 说明 |
|---|---|---|
| Commit | PASS | `13f674c refactor: use code-owned AI prompt and model routes`；提交前 cached diff/secret marker 检查通过。 |
| Push | PASS | `origin/codex/per-flow-model-routing` 从 `8b5fd76` 前进到 `13f674c`；普通 push，无 force。 |
| HEAD/upstream | PASS | 均为 `13f674cf82b0dd2fe58b2b7ebe8e959ca73b4ef9`。 |

## 2026-09-03 — code-owned 路由后的猫狗完整报告链重测

| 检查 | 结果 | 说明 |
|---|---|---|
| 当前提交与工作树 | PASS WITH SHARED-DIFF RISK | HEAD `99db6be`，业务提交 `13f674c`；共享工作树有未提交 `scripts/dev/run_local_chain.sh` 修改，本会话未创建/回退。 |
| Backend 全量 | PASS | `/opt/homebrew/anaconda3/bin/python3.12 -m pytest apps/backend/tests -q` → `381 passed, 48 warnings in 1.34s`。 |
| Runtime 拓扑启动 | PASS | Runtime health、Relay heartbeat、Worker、readiness、exactly-one imaging consumer 均通过。 |
| 猫影像入口 | PASS | fresh 2 图 Lateral + VD 完成 Session/Study/Series、上传、验证和 Study finalize。 |
| 猫 Quality preparation | PASS | Quality Task `cceffba662d542a0981f3ebd022d1443` 创建成功，preparation Stage completed。 |
| 猫 Prompt Runtime | ENVIRONMENT_BLOCKED | `POST {PROMPT_RUNTIME_URL}/api/v1/prompts/render` 建连抛出 `httpx.ConnectError`；目标 `127.0.0.1:8100` 无监听，health/readiness connection refused。 |
| 猫 Gateway/Provider | NOT REACHED | Prompt Render 未完成，未发起真实 Gateway/Provider 请求，不能验证实际模型或 `gpt-5.6-sol` Provider receipt。 |
| 猫 Diagnose/Report | NOT CREATED | 未创建 Diagnose Task，未生成 `final Report`，task/current/history 完整查询门未满足。 |
| 狗完整主链 | NOT RUN | 猫失败即停，符合本轮 stop gate。 |
| 运行态清理 | PASS | E2E 中止后 launcher 温关闭；8010 无监听，`/tmp/ms-image-local-chain-*.lock` 为空。 |
| Prompt 服务定位 | CONFIRMED / NOT STARTED | 独立仓库 `/Users/mozhicheng/workspace/code/cy-code/ms-prompt-service` 的 `.env` 配置 Runtime 8100、Admin 8101；当前 8100/8101 均无监听。 |

## 2026-09-03 — direct-Nacos / AI Platform fresh 猫全链验证

| 检查 | 结果 | 说明 |
|---|---|---|
| `ms-ai-fast` 对照 | PASS | Nacos latest、StrictUndefined + `$VARIABLE`、Chat Completions URL/headers/payload、strict json_schema、HTTP 500 无自动 retry、JSON 提取语义一致。 |
| Full-chain harness | PASS | 旧 Gemini/DB Config 审计改为 code-owned Prompt/route 审计；Cat/Dog key 均覆盖；`py_compile`、Ruff、diff check PASS。 |
| Code-owned audit helper | PASS | 对真实 Quality Call `de186ab8e4024b24afe031971f6ffc30` 核验 Prompt identity、route、Schema/messages、Attempt、receipt 和 actual model 通过。 |
| Cat Quality | PASS | Task `ddaf9f23d79f4e3fafb3151e2fc44075` completed；Prompt `1.1.3`；Provider 200；`gpt-5.6-sol`；3/3/3；1 Call/1 Attempt；Report 0。 |
| Cat StudyScreening | PASS | Diagnose Task `6574961802f34cea80930c5ce04e51cc` 中 Prompt `2.0.2`；Provider 200；3/3/3；1 Call/1 Attempt；Stage completed。 |
| Cat SystemAnalysis | FAIL-CLOSED / EXTERNAL HTTP 500 | Prompt `1.0.2` 已动态读取和渲染；AI Platform 返回 `provider_http_500_internal_error`；1 Call/1 Attempt、retry=0、无 Provider request ID/response SHA。 |
| Prompt/Schema 归因 | NOT SUPPORTED | 历史 `1.0.1` HTTP 200 与本次 model/route/temperature/Schema SHA/合同版本一致；不能把平台 500 认定为 Prompt 错误。 |
| Cat Report queries | CONSISTENT / NO REPORT | failed Task `current_report_id=null`；current absent；history count 0；Primary/Targeted/ReportGeneration 未执行。 |
| Dog full chain | NOT RUN | 猫失败即停，未创建 Dog Task/Call/Attempt。 |
| Runtime cleanup | PASS WITH KNOWN WARNING | launcher 温关闭，8010/进程/lock 均清理；既有 aiomysql event-loop-close warning 仍存在。 |

## 2026-09-03 — ms-ai-fast 严格对齐复核与 fresh 猫再次验证

| 检查 | 结果 | 说明 |
|---|---|---|
| `ms-ai-fast` 源码逐项对照 | PASS | 对照 direct Nacos Client API/latest、Prompt envelope、StrictUndefined/tojson/$变量、单 user message、Chat Completions URL/headers/payload、strict json_schema、HTTP 500 直接失败与 Provider JSON 提取；没有发现需要补一套 AI/Prompt 实现的偏离。 |
| 定向合同测试 | PASS | `PYTHONPATH=. pytest -q ... -k 'prompt_runtime_client or gateway_client or build_gateway_payload or schema_validate_result or renderer_preserves_literal_dollars'` → `22 passed, 372 deselected, 1 warning`。 |
| 首次定向 pytest | ENVIRONMENT INVOCATION ERROR | 未设置 `PYTHONPATH=.` 导致收集期 `ModuleNotFoundError: apps`；补齐后同组测试全过，不是源码失败。 |
| Fresh Cat Quality | PASS | Task `afcedfacb94d4cc8947c866e924bf96b`；Prompt `xray_cat_image_quality@1.1.3` exact/no fallback；Call `1e2c7d...`、Attempt `3e177f...`；HTTP 200；actual model `gpt-5.6-sol`；3/3/3；Report 0。 |
| Fresh Cat StudyScreening | PASS | Diagnose Task `9baeafddd0aa4ebf8a1d3d19a122a355`；Prompt `xray_cat_study_screening@2.0.2` exact/no fallback；Call `c488a6...`、Attempt `5c666e...`；HTTP 200；actual model `gpt-5.6-sol`；3/3/3。 |
| Fresh Cat SystemAnalysis | FAIL-CLOSED / AI PLATFORM HTTP 500 | Prompt `xray_cat_system_analysis@1.0.2` 已动态读取和渲染；Call `e05b68...`、Attempt `4222ab...`；指定 `/chat/completions` 约 64 秒后 HTTP 500；1 Call/1 Attempt、无 retry、无 Provider request ID/response SHA。 |
| Report 查询一致性 | PASS / NO REPORT | Task failed 且 `current_report_id=null`；`/reports/current` data null；`/reports/history` 0 条。 |
| Dog | NOT RUN | 猫失败即停；未创建 Dog Task/Call/Attempt。 |
| Runtime cleanup | PASS WITH KNOWN WARNING | launcher 温关闭；8010、Runtime/Relay/Worker/lock、临时 manifest/evidence 均清理；既有 aiomysql event-loop-close warning 仍存在。 |

## 2026-09-03 — 2 图 Cat 全链与 Platform 60 秒 timeout 定位

| 检查 | 结果 | 说明 |
|---|---|---|
| Platform health/model | PASS | 远端 `/api/v1/health` 200；兼容 models 路由包含 `gpt-5.6-sol`；鉴权、模型存在和平台全局不可用均排除。 |
| Platform OpenAPI | CONFIRMED | `/api/v1/chat/completions` 已公开；没有 audit/trace/log 查询接口，无法从 Runtime API 直接读取该三次请求的服务端异常栈。 |
| Platform timeout source | CONFIRMED IN LOCAL MATCHING SOURCE | Endpoint timeout 默认 60 秒；`AiProxyService._create_client()` 与 OpenAI adapter 均传给 `AsyncOpenAI`；非流式异常统一映射为 HTTP 500 `internal_error`。线上精确 Endpoint 配置值未直接读取。 |
| Projection evidence | PASS | 同一两张图片 SHA 在已完成 Task `3ae7269e95904ddf9739be769dd971d2` 中均冻结为 `ventrodorsal`；本轮未使用 UNKNOWN 或推测。 |
| Cat Quality | PASS | Task `3df2e3a84a43466bbffa65e34e3b0b97` completed；Prompt `1.1.3`；Provider 200；actual model `gpt-5.6-sol`；2/2/2；1 Call/1 Attempt；Report 0。 |
| Cat StudyScreening | PASS | Diagnose Task `2281f03729ff47e997636bbe6dcb4804`；Prompt `2.0.2`；Provider 200；2 图；1 Call/1 Attempt。 |
| Cat SystemAnalysis | PASS | Prompt `1.0.2`；Provider 200，约 54 秒；actual model `gpt-5.6-sol`；2 图；1 Call/1 Attempt。 |
| Cat Primary/route/decision | PASS | Primary Prompt `1.0.1` Provider 200；FamilyRouting 与 DecisionFinalization completed；本病例无 TargetedReview candidate。 |
| Cat ReportGeneration | FAIL-CLOSED / PLATFORM TIMEOUT | 零图 Prompt `1.0.1`；Call `8fa83c...`、Attempt `159af4...`；约 61 秒后 HTTP 500 `internal_error`；无 retry/request ID/response SHA；Report 0。 |
| Timeout attribution | HIGH CONFIDENCE | 3 图 SystemAnalysis 两次约 64 秒 500；零图 ReportGeneration 约 61 秒 500；2 图 SystemAnalysis 约 54 秒 200；与 Platform 60 秒 Endpoint timeout 实现吻合，排除图片数量本身。 |
| Dog | NOT RUN | 猫未生成 final Report，继续执行停止门。 |
| Cleanup | PASS WITH KNOWN WARNING | launcher 温关闭；8010、Runtime/Relay/Worker/lock、临时 manifest/evidence 均清理；既有 aiomysql warning 保留为独立项。 |

## 2026-09-03 — Gemini 3.5 Flash 猫狗完整主链资格

| 检查 | 结果 | 说明 |
|---|---|---|
| 诊断 Stage 模型路由 | PASS | 6 个诊断 AI Stage 均为 `gemini-3.5-flash/race`；Anatomy Localization 仍为 `gpt-5.6-sol/race`。 |
| 定向路由合同 | PASS | `15 passed, 305 deselected`；同时断言 6 个诊断 Stage 与 Localization 的不同模型边界。 |
| Prompt 本地验证 | PASS | Cat/Dog ReportGeneration `1.0.2` 的 Jinja required variables 精确为 `FINAL_MEDICAL_RESULT_JSON/QUALITY_RESULTS_JSON/REPORT_SCHEMA_JSON`，Strict render 成功。 |
| Nacos immutable preflight | PASS | 指定 namespace 中 Cat/Dog `1.0.2` 均不存在；旧 `1.0.0/1.0.1` online。 |
| Nacos 发布与 exact readback | PASS | Cat/Dog `1.0.2` 经 `draft → submit` 自动 online；latest template 与本地逐字一致，SHA 分别 `dacc47d9...757a3`、`42b051b0...55d9e`；未 force publish。 |
| 首次 Gemini Cat | FAIL-CLOSED / PROMPT ATTRIBUTED | Task `780b6d97...`：Quality、Screening、System、Primary、Targeted 均 HTTP 200/accepted；ReportGeneration HTTP 200 后因 `report_generation_medical_result_rewritten` failed，Report 0。Nacos `1.0.1` 缺少完整对象深拷贝指令。 |
| Fresh Cat full chain | PASS | Quality `20fceba6...`、Diagnose `00deb1ff...` completed；8 Stage、5 Call、5 Attempt；Targeted 触发；Report `081e9443...` final；task/current/history 一致。 |
| Cat Prompt/model receipts | PASS | ReportGeneration 动态读取 `1.0.2`；Quality + 5 个诊断 AI Call 均单 Attempt，requested/actual model=`gemini-3.5-flash`。 |
| Dog projection evidence | PASS | `dog-03` 三张图片 SHA 在已完成 Quality Task `d52f24a2...` 中均为 caller-declared `ventrodorsal`；未使用 UNKNOWN、文件名或像素猜测。 |
| Fresh Dog full chain | PASS | Quality `a1369670...`、Diagnose `7ec955a6...` completed；FamilyRouting=`primary_final`，7 Stage、4 Call、4 Attempt；Report `646cd3e6...` final；task/current/history 一致。 |
| Dog Prompt/model receipts | PASS | ReportGeneration 动态读取 `1.0.2`；Quality + 4 个诊断 AI Call 均单 Attempt，requested/actual model=`gemini-3.5-flash`；TargetedReview 合法未物化。 |
| Conditional topology harness | PASS | 修复固定 8 Stage/5 Call 假设后，对既有 Dog Task 做只读 `_read_full_chain_runtime_receipt` 复验通过；未新增 Provider 调用。 |
| Backend full suite | PASS | `PYTHONPATH=. python3.12 -m pytest -q apps/backend/tests` → `403 passed, 48 warnings`。 |
| Static checks | PASS | 目标 Ruff、Python `py_compile`、`git diff --check` 均通过。 |
| Runtime cleanup | PASS WITH KNOWN WARNING | launcher 温关闭；8010、Runtime/Relay/Worker/lock 无残留；aiomysql event-loop-close warning 仍存在。 |
| 医学准确率 | NOT EVALUATED / NO-GO | 本轮只证明工程执行、Prompt/model/receipt/Report 血缘；没有 Gold、Scorer、Failure Bank 或 Holdout。 |
