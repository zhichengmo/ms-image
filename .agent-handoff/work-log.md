# 当前工作日志

## 2026-08-28 — 重写 14 号 XRay 架构选择与专项设计

- 对照当前 Pipeline、FamilyRouting、StudyPreparation、DecisionFinalization、Prompt identity、20 个 ORM Model、Report CAS 和最新 E1-MV/运行风险证据，重写 `docs/refactor/14-xray-specialty-design.md`。
- 当前决策固定为 Primary-only 作为唯一运行与医学评测基线；Primary + Conditional Targeted 只作为 M1 后的实验候选；默认按器官多调用和多读者辩论均不采用。
- 文档从 1385 行重复总览重写为更紧凑的小白版，增加四方案对比、三种成功边界、当前真实链、已完成/未完成、20 表职责分组、评测方法、停止条件、常见误解、10 分钟讲解话术和中英术语表。
- 新增 5 张 Mermaid 架构图：方案选型、系统总体架构、当前主读执行链、未来条件专项复核、Prompt 冻结链；使用 Mermaid CLI 对 Markdown 全文真实渲染，5 张 PNG/SVG 均生成成功，并完成视觉检查。
- 最新 E1-MV 已按 PASS / ENGINEERING ONLY 写入；没有把合法 `abnormal` 输出当作 Gold 或准确率证据。明确 Targeted 当前因 `primary_final` 固定路由不可达，Report publish/void 与 Evaluation 只能称 code-present、runtime-unusable。
- 本轮只修改文档与 durable handoff；未修改业务代码、数据库、Prompt、表、字段、迁移、测试脚本或医学规则。

## 2026-08-28 — C1.1 医学状态边界加固

- 新增 `services/runtime/medical_status_contract.py`，集中定义模型医学四值、持久化五值和 Stage availability 二值；Runtime 不反向依赖 Evaluation。
- 将 DecisionFinalization 持久化投影改为严格组合矩阵：合法 `produced` 原样投影嵌套医学四值，合法 legacy `not_produced` 保持兼容；缺失、未知和冲突组合稳定 fail-closed，不再静默降级。
- 非法 finalization 在 Report 创建前复用既有失败路径，Stage/Task 收敛为 `failed/not_produced`；取消和终态并发仍先锁 Task 后处理。
- `ReportService.finalize()` 在 DAL 前校验持久化状态集合、content 顶层状态存在且与列值一致；同源幂等 hash/来源约束保持不变。
- 扩展既有 `test_ai_gateway_attempt_contracts.py` 覆盖四个合法模型状态、legacy not-produced、全部非法组合、Runtime/Evaluation 集合一致、冻结 v1 Stage 标记、合法三层持久化、非法无 Report 和 Report DAL 前拒绝；没有新增测试脚本。
- 精确停止修改前的本地 API/Relay/Worker并启动当前源码；父级 harness 随后自动补拉第二组当前源码 Relay/Worker，因此第一轮 E2E 不作为单 Worker 证据。停止启动器自带的重复组后，只保留 harness 一组消费者。
- 最终单 Worker E2E Task `5dee75ffd0554e78868c5100bc752ddb` 完成，current Report `e3f06fccbe1945009f5b0666aa222bf0` 为 final。Stage 顶层仍为 `produced`，嵌套、Task、Report 列与 Report content 均为 `review_required`；验收后进程盘点仍只有一组 Relay/Worker。
- 未修改 Stage v1、医学/projection 规则、模型、表、字段或迁移；未回填历史 `produced` 数据。

## 2026-08-28 — P1-A 自动 reconcile 调度与真实恢复资格化

- 先完成 scheduler ownership 审计：仓库、Compose、本地脚本、CI 和当前 ms-image 进程均无既有周期 owner；选择独立 Celery Beat singleton，默认关闭，外部 scheduler 存在时禁止同时启用。
- 在现有配置增加 opt-in schedule enable、30..3600 秒 interval 和 1..500 batch limit；Beat entry 显式投递既有 `imaging.v1 / imaging.image.validate / imaging.image.validate`。
- Compose 增加独立 `scheduler` profile 的 `imaging-scheduler` 单副本；本地启动器只在显式 true 时启动 Beat，启动前拒绝已有同类 Beat，并把 Beat PID 纳入统一 cleanup。
- reconcile worker 每批读取 `limit + 1` 形成 batch saturation 下界，日志补 `due_scanned/due_remaining_estimate/duration_ms`；没有改变 lookup、医学或 projection 规则。
- 扩展既有 Gateway/Attempt 合同文件，覆盖 schedule 默认关闭/显式 route/参数边界、task clamp 与聚合日志、两个 Worker 重叠扫描只 claim/lookup/reschedule 一次且 replacement POST 为 0。
- 真实 Beat 自动发送周期 task；Worker 自动 claim 1 个临时 unknown Attempt，并以 unsupported 安全重排。Provider request/idempotency key 不变、Call 只有 1 条 Attempt。
- 隔离 Worker使用 30 秒 lease、90 秒 lookup，claim 后 SIGKILL；lease 到期后新 Worker从 RabbitMQ 重投唯一恢复，后续积压周期任务均未再次 claim。
- 最终核对临时 Attempt `state_version=6/status=unknown/error=provider_attempt_lookup_unsupported`，随后精确删除该 Attempt 和父 Call并确认不存在；停止 Beat/Worker，无 ms-image 临时进程或 schedule 文件残留。
- 本轮未新增 HTTP 接口、queue、表、字段、迁移、测试脚本、医学或 projection 规则。P1-B unsupported 有界终止仍独立待授权。

## 2026-08-28 — 当前未提交代码架构只读审查

- 只读审查 59 个 tracked 文件、约 5812 additions/1811 deletions；未修改任何业务代码、配置、数据库、Prompt、表、字段、迁移或测试脚本。
- 确认主干遵循 `API -> Service -> DalBase CRUD -> Model/DB`：endpoint 通过 Service，业务 Service 通过实体 DAL，未出现 Service/API/Worker 直接 SQL、第二套 CRUDBase/Repository/DatabaseService，也没有新增 `/{id}` 资源路由。
- 确认 Runtime 执行冻结 Task/Config/Prompt/Call，Primary-only 正常路径只有 JointPrimaryReader；FamilyRouting 固定 `primary_final`，TargetedReview 仅保留未来不可达骨架。
- 确认模型输出是医学结果唯一来源；DecisionFinalization/Report 只校验、投影、持久化，不用 Python 猜测或补写 Finding/诊断。
- 确认高风险冻结事实断点：Connection `base_url` 被纳入 SHA/frozen lane，但 Runtime network plan 不携带或核对，默认 GatewayClient 从进程环境读取真实 Platform 地址。
- 确认条件性部署 Secret 风险：Compose 共享 `.env-01` 给多个平面；本地文件没有 Platform key 条目，未证明已发生泄露，但模板不满足最小权限。
- 确认两个中风险：Control 对 `api_format` 校验晚于 activate；Runtime 直接 import AI Control service 包内的纯 Config verifier，形成反向实现依赖。
- 排除两个误报：Platform payload `strategy=race` 是已验证的外部 Platform 协议字段，不等于 ms-image 多 lane Race；Provider readiness 静态状态是既有非 required 观察合同，不进入公共 engineering readiness。
- 审查验证全部通过：backend 146 tests、Ruff、compileall、Compose broker+scheduler config 和 `git diff --check`。结果只证明工程回归，不证明医学准确率。

## 2026-08-28 — P1-B unknown Attempt 持久有界终止

- 用户授权 P1-B 所需字段和正式迁移；先只读核验现有 Attempt 状态机、配置传播、迁移链与真实 MySQL，确认目标字段必须落在 Physical Attempt，且当前库 migration head 为 `20260824_02`、unknown=0。
- 冻结 `ai-attempt-reconcile.v1` 为最多 3 次获授权 lookup、首次 unknown 后最多 10800 秒；Settings 对同一 v1 的其他值 fail-closed，避免部署环境静默改变语义。
- 为 `ai_call_attempt_record` 增加 `first_unknown_at/reconcile_count` ORM 字段和正式迁移 `20260828_01`；历史首次时间不回填，降级在任何 P1-B 事实存在时阻断。
- 首次 `prepared -> unknown` 在既有 Attempt CAS 中只写一次时间；claim CAS 原子增加次数；count/age 未超限才授权 lookup，已超限只取得终止 lease，reschedule 前再次检查双边界。
- Worker 对最后一次可信 `succeeded/failed` 正常采用；最后一次 `unknown/unsupported` 或 claim 前已超限时调用 `finalize_unresolved`，复用既有技术失败链并清除 due 时间。
- 新增非敏感聚合 `lookup_authorized/terminal_unresolved/terminal_preserved/count_limit_reached/age_limit_reached`；未新增 HTTP 接口、queue、replacement Attempt、Provider POST、医学或 projection 规则。
- 真实 MySQL 完成 `20260824_02 -> 20260828_01`；15 条既有 Attempt 的首次时间仍全 NULL、次数仍全 0，状态未改写。
- 单一当前源码 Beat/Worker 使用默认 `UnsupportedProviderAttemptLookup` 自动处理 count=2 隔离 Attempt；一次 lookup 后 count=3，全链收敛 Attempt failed、Call failed/failed、Stage failed、Task failed/not_produced、Report 0。
- 真实资格化保持同一 Provider request/idempotency identity、Attempt 总数 1；临时数据按精确 ID 删除，Beat/Worker 与 schedule 文件已清理。现有 outbox relay 未停止，因为不属于 P1-B 临时进程。
- 验证为 focused 22 tests、Gateway/Attempt 102 tests、backend 全量 153 tests；Ruff、compileall、Shell、Compose、Alembic head/current/offline SQL 和 diff check 全部通过。

## 2026-08-28 — P1-C 与核心诊断链范围裁决

- 只读追踪 Runtime/Admin JWT 与三类 Artifact signing key 的生产引用，区分 HTTP 入口鉴权、管理控制面和 Task→Worker→Provider→Report 内部执行。
- Runtime JWT 被业务 HTTP endpoint scope dependency 使用，只决定调用身份；Admin JWT 只保护 AI Control/Admin；两者均不进入 Worker/Provider/Report 状态机。
- 三个 signing 环境变量当前仅见 Compose 注入，生产 Python 主链没有读取；qualification/egress proof 签名工具不阻断正常 Report。
- 用户决定当前不考虑 P1-C。交接状态改为核心 Worker Runtime 已资格化、生产 API 安全未资格化；未来公网/管理/合规上线时恢复。
- 未修改业务代码、配置、数据库、迁移、Prompt 或测试；没有删除现有 JWT dependency，也没有生成或写入任何 Secret。

## 2026-08-28 — 对照 ms-ai-fast 澄清 Platform 地址合同

- 完整读取 `ms-ai-fast` 项目规则与架构说明，定向追踪 `Settings -> GatewayClient -> AiRuntimeService -> ms-ai-platform`。
- 确认 `ms-ai-fast` 只有进程环境中的 `AI_PLATFORM_OPENAI_BASE_URL + AI_PLATFORM_API_KEY` 一个可执行出站目标，没有 AI Connection/Model Pool 数据表或第二份冻结地址。
- 只读查询 `ms-image` 当前 `ai_api_connection`：唯一 validated Connection 的 `base_url` 与 `ms-ai-fast/.env` Platform URL 完全一致；未读取或输出 API Key。
- 确认 `ms-image` 默认 Settings 当前无 Platform URL，未注入时 `_runtime_gate_allows()` 拒绝真实 Provider 路径；历史资格 Worker 按既有决定从 `ms-ai-fast/.env` 成对注入后成功。
- 因此修正上轮结论：复制 GatewayClient 方式正确，无当前地址错发证据；仅保留未来配置漂移时缺少 frozen URL/Worker URL 自动一致性校验的中风险硬化项。
- 本轮未修改业务代码、配置、数据库、Prompt、表、字段、迁移或测试脚本；只修正 durable handoff 事实。

## 2026-08-28 — C2 CompleteMedicalResult v2

- 完整保留 v1 Schema/Profile/Handler/Config，新增 `xray_primary_v2`、`xray_targeted_review_v2`、Stage v2 与 `complete-medical-result.v2`；Task 创建时 v2 Profile 强制 Snapshot v3，legacy Snapshot v2 继续走 v1。
- 新增 `apps/backend/core/ai/xray_result_contract.py`，只将 v2 Finding/SourceRef ID、引用存在性与本次 `ai-image-receipt.v2` 的逐图事实进行技术对账；没有诊断词典、projection 值域、医学一致性或 Python 改判。
- 新增严格 Draft 2020-12 v2 Schema 和 Primary/Targeted v2 Prompt 资产；summary/impression 由模型输出，Python/Report 只验证、投影、持久化。
- 扩展 Config compiler/Profile/Stage registry/Task admission/AI response parse 链，并在既有两个 AI 合同测试文件中增加 v1 冻结、v2 正反例与 Snapshot v3 门禁覆盖；未新建测试脚本。
- 发布并精确回读 Nacos Primary `ms-image.x-ray.primary.common.zh-CN@2.0.0`，content SHA `a20bc6e5f41ee250a01d1c94842c2bdfa00023b586a5c7496675e98c3c1e4cc1`；Targeted v2 未发布。
- 通过既有控制面导入 Prompt `713392c2e4b94f2daefbfe8f559c6b1d` 并编译/激活 Config `8997ea7bbea648488b0e043ace9b9095`（`2.0.0/xray_primary_v2`）；旧 v1 Config retired 但冻结完整性重验通过。
- 使用当前源码单 Worker 跑通真实 Task `1b33cb9573df496f98d1f23f501ee8eb`：Task completed/review_required，Attempt/Call succeeded，Stage 为 preparation v1 + primary/finalization v2，Report final；结果含 3 个 Finding 和 1 个 SourceRef，三层结果一致并通过存储后引用复验。
- 本轮无 HTTP 接口、数据库表、字段或迁移变更。当前 Runtime 8010、Relay 与单一 Celery consumer 保持运行，Beat 关闭。

## 2026-08-28 — 当前 XRay 全链缺口只读复核

- 亲自通读 14/25/26/29 四份架构与实施基线，并按三个只读探子的精确出处抽查控制面、Runtime/Worker、Evaluation/医学发布与分层代码；未修改业务代码、数据库、Nacos、Prompt、表、字段、迁移或测试脚本。
- 将旧文档中的 C1.1、P1-A、P1-B、D1、E1-MV、C2 未完成状态与当前源码/真实验证对齐：这些工程切片现已完成；14/25/26/29 的旧状态段落不能继续作为当前缺口清单直接宣讲。
- 确认当前主阻断是 `ms_image_eval` 不可用、Evaluation 独立迁移/readiness 未闭环、Gold/Scorer/分母/Failure Bank/Regression/Holdout/M1 未建立；当时关于 D2 未实现的判断已被后续源码复核纠正，D2 现为已完成工程合同；医学发布继续 NO-GO。
- 确认生产侧仍缺 JWT/Artifact signing 生命周期、Compose Secret 最小权限、Platform 常驻进程/Secret owner、从零 Alembic replay、冻结发布工件与 Report 交付治理；这些不回退已资格化的内部核心诊断链。
- 确认配置/模块硬化项仍存在：frozen Connection URL 与 Worker URL 未自动比较、api_format 到 Runtime 才拒绝、Runtime 反向 import AI Control verifier、Prompt import 可能跨 Nacos I/O 持有事务、Provider readiness 信号滞后。
- 确认 `ms-ai-fast` 已有 pet_profile/medical_record 数据与 `pet_type=1猫/2狗/3异宠`，但尚未接成 `pet_type -> cat|dog -> POST /tasks`；ms-image 当前仍要求调用方显式传 species，Worker 不回查档案。
- 本轮复跑 backend 全量 166 tests、Ruff、compileall、Compose broker+scheduler config 与 diff check 全部通过；Alembic head/current 均为 `20260828_01`。Runtime health/readiness 200，数据库/Redis/broker ready；AI Control 当前未运行，Evaluation DB 连接失败。

## 2026-08-28 — DeepSeek 结论复核与最小主链计划收口

- 重新按源码、现有 E2E harness、运行态和数据库事实核对 DeepSeek 输出；确认 D2 clinical context v1 已实现，旧 handoff 将其列为未完成是过时状态。
- 确认 C2 CompleteMedicalResult v2 已包含 summary/impression/findings/source_refs、严格负例和真实 C2 E2E；DeepSeek 将其判为未实现不符合当前代码。工程资格化不代表医学准确。
- 通过 ORM/Model/DAL/Service 对账确认 Report 没有 `state_version`；第一份 final 创建、Task completed 和 current/history 读取不受阻断，publish/void/第二 revision CAS 受阻断。
- 确认 `scripts/dev/run_e2e_local.py` 已覆盖上传、OSS、校验 Worker、Study finalize、Task、Outbox/Broker/Celery、Provider、Attempt/Call/Stage、Report 与历史查询；当前缺的是无硬编码、稳定可重复、证据清晰的一键验收合同。
- 将下一步顺序调整为：先固化最小上传到首份报告链，再修 Report 状态治理，再接 `ms-ai-fast`，之后才进入 Evaluation/M1，最后处理生产 JWT/signing/Secret。
- 本轮只读审计和计划，没有修改业务代码、数据库、环境、Nacos、Prompt、表、字段、迁移或测试脚本。

## 2026-08-28 — 14 号架构文档面向讲解重写与 DeepSeek 最终输出复核

- 重写 `docs/refactor/14-xray-specialty-design.md`，面向第一次接触项目的读者补齐中英术语、三种成功边界、DeepSeek 逐项裁决、代码证据索引和 10 分钟会议话术。
- 新增“上传已有 X 光影像 -> OSS -> Image ready -> Study finalize -> Task/Outbox/Broker/Worker -> Provider -> 三阶段 -> final Report -> current/history”的主链架构图，并把重复进程、Report state_version、Evaluation/M1 三条缺口画成独立旁支。
- 确认 v2 CompleteMedicalResult 已工程资格化，结果位于 `Report.content_json.complete_medical_result`；v1 Schema 必须保持冻结，不采纳“同步 v2 字段”的建议。
- 当前现场为 1 个 Runtime API、2 个 Outbox Relay、3 个 Celery Worker parent，readiness 报告 3 个 consumer；因此状态更新为 `DETERMINISTIC_LOCAL_REPLAY_NOT_QUALIFIED`。本轮未停止或重启任何进程。
- 本轮只修改 14 号文档和 durable handoff；未修改业务代码、数据库、Nacos、Prompt、Schema、迁移或测试脚本，未执行 Git 提交。

## 2026-08-28 — DeepSeek D2 验收轮：单主人收敛 + 3× 全链 E2E

- 收敛环境到唯一 owner：终止遗留孤儿进程（旧 launcher 的 55537/55538/55539）与旧代码 worker，8010 端口释放；随后用 Codex 的 390 行 `scripts/dev/run_local_chain.sh` 以 detached 方式启动（pid 59944），确认其成为唯一 owner：API 8010 + 1 Relay + 1 Worker、broker consumer_count=1、Beat 关闭（`Reconcile scheduler enabled: false`）、owner.pid 存活、探活 `ready:true`。
- 核对 `scripts/dev/run_e2e_local.py` 实际代码：Codex 已把 `--species/--projection/--body-part/--clinical-context-mode/--context-recorded-at/--repeat` 全部参数化，无硬编码 species/body_part；`--help` 与 7 项非法参数用例全部按 expect 拒绝。
- 固定验收图（VS1_CAT 同名无关键 JPEG，sha256 `6758a344…9ec9`，未当 Gold 使用）+ 合成临床上下文连跑 3 轮 D2 验收：全部 Task completed→Report final（v2、source_ref=1、finding=2），`E2E_COMPLETE` 且 3 轮 context SHA 与 config fingerprint 一致；medical_status=abnormal 为模型结果投影，不代表医学准确。
- 复跑 backend 全量 `178 passed, 38 warnings`、`ruff check`、`compileall`、`git diff --check`、`bash -n run_local_chain.sh` 全部通过；未提交 Git。
- 本轮未改业务代码/数据库/Nacos/Prompt/迁移/测试脚本，只更新 durable handoff；状态标记 `DETERMINISTIC_LOCAL_ENGINEERING_REPLAY_QUALIFIED / D2_SYNTHETIC_E2E_QUALIFIED`，明确不得声称 D2 真实上游上下文合格或医学准确/发布合格。

## 2026-08-28 — Codex D2 收口复验与 launcher 正常退出

- 完成并复核 `scripts/dev/run_local_chain.sh` 与 `scripts/dev/run_e2e_local.py`：脚本分别为 390/756 行、均可执行；E2E 使用与 launcher 相同的 Python 3.12 签发本地 dev JWT，避免 Homebrew Python 3.13 缺少 PyJWT，未改变 Runtime 鉴权合同。
- 动态验证第二个 launcher 被 `/tmp/ms-image-local-chain-8010.lock` 拒绝且现有进程保持 1 API + 1 Relay + 1 Worker parent/child；Beat=0，readiness consumer=1。
- 一次批次第 2 轮 Task 真实 fail-closed 为 `provider_result_source_fact_mismatch`，立即停止且未计入成功；随后从新批次连续三轮 public-API E2E 全部完成，三轮 context SHA 和 Config/Prompt fingerprint 一致，D1/D2/C2/current/history 全部通过。
- 在 Celery active/reserved/scheduled 全空后向唯一 launcher 正常发送 SIGTERM；launcher-owned API、Relay、Worker parent/child 和 owner lock 全部释放，8010 不再监听。未停止其他项目 Celery 或 deepseek-harness。
- 全量测试 `178 passed, 38 warnings`；D1/D2/C2 定向 `172 passed, 38 warnings`；Ruff、compileall、`bash -n`、CLI help/非法参数和 `git diff --check` 通过。未提交 Git。

## 2026-08-28 — DeepSeek 复核 GPT「猫狗独立 Primary Prompt 调用计划」

- 逐项对照源码与 DB 事实核验 GPT 计划：现有 `xray_primary@2.0.0`（validated，receipt=`ms-image.x-ray.primary.common.zh-CN`/release 2.0.0/variant common/fallback false）与 active `xray_diagnose@2.0.0`（profile xray_primary_v2、model pool xray_primary_single@1.0.0、budget ai-budget-policy.v1、global/global 槽）均属实；双 Config 同时 active 依赖不同 config_key→不同激活槽，成立。
- 发现三处必修：① prompt_source.py 需扩 map（key xray_cat_primary/xray_dog_primary → primary；variant cat/dog；XRAY_PROMPT_VARIANTS+2），现状 cat/dog 与 xray_cat_primary 均被断言为非法；② 现有测试 test_ai_prompt_control_plane_contracts.py:744-795 明确断言 cat/dog 非法，需改写而非仅“补齐”；③ ms-image 无 Nacos 发布能力（client 只读 fetch/readiness，无 publish/脚本），发布只能在 Nacos 侧完成。
- 两处必补：AI Control 是独立服务（services/ai_control/main.py），本地 run_local_chain.sh 不含控制面，需单独启动 + `issue_dev_token.py xray:admin:write`；新 Prompt 需完整复制 2.0.0 变量集（消息合同仅允许 SAFE_STUDY_CONTEXT_JSON/PRIMARY_RESULT_JSON 为 user_context_keys，OUTPUT_SCHEMA_JSON 为渲染变量）。
- 措辞修正：xray_primary_v2 编译链只有 3 静态阶段（无 family_routing 阶段）；family_routing/primary_final 属 targeted profile。E2E 证据需补 config_key/prompt_key 断言（现有 config_fingerprint 不含 config_key）。
- 裁决：计划总体可行，无需新表/字段/迁移；完成标志 `CAT_DOG_PRIMARY_PROMPT_ROUTING_QUALIFIED` 与医学资格区分恰当；本轮纯复核，未改代码。

## 2026-08-28 — DeepSeek 复核 GPT 猫狗 Prompt 计划 v2（含绑定校验）

- v1 的 5 点修正已被完整采纳并落地为可执行条目：prompt_source 三处映射扩展与“common/cat/dog 互不 fallback、default 非法”规则明确；现有测试断言“cat/dog/xray_cat_primary 非法”需改写已写入计划；Nacos 发布外部化（ms-image 无 publish 能力，仅 fetch/readiness）已明确；AI Control 独立启动（代码默认端口确为 8002，root_path=/ms-image/ai-control）+ HS256 Admin Token（ADMIN_ALGORITHM=HS256、ADMIN_SECRET_KEY、iss=ms-image-admin、aud=ms-image-admin-api，control_plane_jwt_readiness 拒绝占位 secret）与现状完全一致；变量集基线以 DB 实测为准：2.0.0 required=[OUTPUT_SCHEMA_JSON, SAFE_STUDY_CONTEXT_JSON]、optional=[]、user_context_keys=[SAFE_STUDY_CONTEXT_JSON]、无 PRIMARY_RESULT_JSON（4821 字符、sha a20bc6e5…）。
- 新增“Config↔Prompt 绑定校验”可行：config.prompt_key 已在 config 模型（models/ai_config_record.py:66），在 _validate_assignable_config 内加 species-aware 断言即可；复用 task_config_invalid 语义合理。
- 目录先例已存在：prompts/xray/nacos/primary/common/zh-CN/ms-image.x-ray.primary.common.zh-CN.v2.0.0.txt，猫狗路径/文件名模式完全匹配。
- 三处执行细节提示：① profile_key 不符时现有错误码实际为 task_profile_not_allowed（task_service.py:375-376），task_config_invalid 是 status/capability 失败语义；绑定校验应在 _validate_assignable_config 内加 species-aware 断言而非改 TASK_PROFILES 常量（保持 v1 兼容）；② 本地文件命名应带版本（…cat.zh-CN.v3.0.0.txt），避免与 Nacos 3.0.0/3.0.1 对不上；③ import 时显式传 message_contract_json（user_context_keys=[SAFE_STUDY_CONTEXT_JSON]）。
- 裁决：v2 可行，硬伤全部修正，输出不得回收；完成标志 CAT_DOG_PRIMARY_PROMPT_ROUTING_QUALIFIED 不升级医学资格，与既有边界一致。本轮纯复核，未改代码。

## 2026-08-29 — 猫狗独立 Primary Prompt 路由实施与真实验收

- 扩展 XRay Prompt Source exact-only 映射，完成 `xray_cat_primary/cat` 与 `xray_dog_primary/dog`；重写旧 cat/dog 非法断言并保留 default/跨物种/fallback 失败关闭。
- Task 创建按冻结 species 选择 `xray_diagnose_cat` 或 `xray_diagnose_dog`，并验证 Config key、`xray_primary_v2` Profile 与 Prompt key 物种绑定；common 仅作历史/应用回退资产，不进入新 Task。
- 新增猫狗 `3.0.0` Prompt 本地资产，按用户要求改为 `.md`；规范化正文、变量集与已发布 Nacos/已导入数据库 SHA 完全一致，历史 `.txt` 冻结资产未改。
- 目标 Nacos 完成猫狗 `3.0.0` 发布与精确回读；临时 AI Control 用内存 Admin Secret/Token 完成双 Prompt import/validate 和双 Config compile/create/validate/activate，未记录凭据或正文。
- 猫 public E2E 完成 Task `cf0bef2bcb5b46749d9fad3df361b739` / Report `63825fb730ea4ea9941c1f92a7df3bf8`；狗 Task `f218a6c77ec44a63a38b7203134ddbc6` 精确命中狗 Config/Prompt，但 Provider HTTP 200 后以 `provider_result_source_fact_mismatch` fail-closed，无 Report。
- 遵守失败门禁：狗未静默重跑、未回退 common、未修改冻结 Task。launcher 与临时 AI Control 均已停止，未提交 Git。
- 后续按用户指示将 SourceRef 技术事实联合错误拆为 `series_id/projection/manifest_sha256` 三个脱敏稳定错误码；未新增字段、迁移、接口或校验规则，未保存/输出 Provider 错误正文。
- 新代码下先跑 1 次狗诊断 E2E，再跑有界 `repeat=3`；四个新 Task 均 completed、Report final、Snapshot v3/狗 Config/Prompt SHA/C2 v2/current/history 通过，三类错误均未触发。
- 因旧失败正文未持久化且新批次无法复现，不能诚实断言旧失败属于三者中的哪一项；决定保留狗 `3.0.0`，不发布没有证据支持的 `3.0.1`。
- 全量回归更新为 `185 passed, 38 warnings`，定向 SourceRef `9 passed`；Ruff、compileall、diff check、launcher 进程和 lock 清理通过。

## 2026-08-29 — 猫狗全链 Prompt 接入与真实资格化

- 按用户“先为全链补 Prompt 并跑通，再逐阶段优化”的目标，确定只有 JointPrimaryReader 和 TargetedReview 需要模型 Prompt；StudyPreparation、FamilyRouting、DecisionFinalization 继续是确定性技术 Stage。
- 新增猫狗 `4.0.0` 版本化 Markdown Prompt，以 `PRIMARY_RESULT_JSON` 是否存在分别进入 Primary 或 Targeted 模式；共享 C2 v2、SourceRef、多视位、技术质量和物种边界。
- 扩展 Prompt 导入合同，允许显式声明 optional `PRIMARY_RESULT_JSON`，并保持渲染变量集与正文推断集精确一致。
- 新增进程级 `XRAY_TARGETED_EXPERIMENT_SCOPE_KEY`；空值继续 global Primary `3.0.0`，`full-chain-local-v1` 精确选择 Targeted experiment Config，缺失时 fail-closed 而不回退。
- 实现 FamilyRouting v2：验证 Primary `targeted_candidate` 的受控 Family/Focus、非空去重 Finding 引用与引用存在性；不读图或生成医学结论。
- 收紧 Stage 动态执行合同：只有 v2 FamilyRouting 的合法 `targeted_review` 信号可插入一个 TargetedReview；Targeted 完成后不得再插入新 Stage，DecisionFinalization 使用 targeted 新完整结果。
- 在 Nacos 对猫狗 `4.0.0` 执行正式 draft/submit/publish，未用 force publish，未覆盖 `3.0.0`；精确版本回读 SHA 与本地规范化正文一致。
- 通过临时 AI Control 完成猫狗 Prompt validate 和 `xray_targeted_review_v2` experiment Config compile/create/validate/activate；Admin Secret/Token 只在进程内存中，未写文件或日志。
- 犬 Task `c2d1bf593ea340b8a91398b6c186089d` / Report `615c02a5fbe844ae9f9641697b8ef487` 与猫 Task `67765479be9d4f46b304934cfc38fe94` / Report `755241f0afb5441c8532b5c88a915f67` 均通过 5 Stage、2 Call、targeted owner、final C2 v2 Report 与 receipt v2。
- 猫 Task `809ba6b383c6405196026b6c3f9109a2` 无合法候选时正确以 `primary_final` 和 1 Call 收敛，证明实现未强制 Targeted。
- 本轮最终验证：定向合同 `186 passed, 38 warnings`，Backend 全量 `192 passed, 38 warnings`，Ruff、compileall、shell syntax 与 `git diff --check` 通过；所有临时进程/端口/lock 已清理，未提交 Git。

## 2026-08-29 — 当前环境全链与全 Stage Prompt 复验

- 逐项审计全部 XRay Profile/Stage/Registry/Handler/Prompt command；确认仅 `joint_primary_reader/v1|v2` 和 `targeted_review/v1|v2` 为 `provider_required=True`，两者均有 AI request 构造和冻结 Prompt 渲染链。`study_preparation`、`family_routing`、`decision_finalization` 为确定性 Stage，不存在“模型 Stage 缺 Prompt”。
- 以 `XRAY_TARGETED_EXPERIMENT_SCOPE_KEY=full-chain-local-v1` 启动唯一 API/Relay/Worker，readiness 确认 broker consumer=1、Beat=0；每轮 E2E 都精确断言对应物种 Config key 与 `4.0.0` Prompt SHA。
- 猫 Task `527a23fc03244cdc82832d50bc4e9149` 与狗 Task `4aeff184cdf246eb8252b0374756cdbb` 分别完成 4 Stage/1 Call/receipt v2/final Report；两者均无合法 Targeted 候选，正确走 `primary_final`。
- 猫 Task `7569c45063dc43aba1a337d132c07db7` 与狗 Task `77a0e506c69045049e020b801f1c9033` 分别完成 5 Stage/2 Call；Primary 和 Targeted Call/Attempt 均 `succeeded/accepted`、持久化 `ai-image-receipt.v2`，DecisionFinalization 后产生 final C2 v2 Report。
- 狗 Task `398e76a28af24072a1d66f7c28189ed6` 的 Primary 成功且 FamilyRouting 生成合法 Targeted，但 Targeted Provider 结果复制错 `manifest_sha256`；Call/Attempt 保存 receipt v2 并以 `provider_result_source_manifest_sha256_mismatch` 失败，Task failed、无 Report。未静默重试或 Python 修正。
- 本轮共 5 个新 Task：4 completed/final，1 Targeted fail-closed；进入 Targeted 的 3 个任务中 2 成功、1 失败。文件名 `ABN` 仅用于选择较可能进入分支的工程样本，未传入 Prompt、未作 Gold。
- 定向 Prompt/Gateway 合同复验 `186 passed, 38 warnings`；Backend 全量 `192 passed, 38 warnings`。launcher 正常退出，API/Relay/Worker/Beat、8010/8002 和 owner lock 均已清理。

## 2026-08-29 — DeepSeek 复核 GPT「逐阶段效果优化」后续计划（v3）

- 计划对现状的断言全部属实（实测）：猫狗 3.0.0（global Primary-only active）与 4.0.0（experiment/full-chain-local-v1 active，profile=xray_targeted_review_v2）均已存在且 validated；双模式 .md + `{% if PRIMARY_RESULT_JSON is defined %}` Jinja 分支真实存在（v4.0.0 cat/dog）；Targeted 链真实成功过（最近任务 profile=xray_targeted_review_v2 completed×4，targeted_review stage completed 4/failed 1，family_routing completed 8）；技术失败事实存在（joint_primary_reader failed 6/dead_letter 1，targeted_review failed 1）支撑“缺口是 Targeted 技术稳定性”；回归基线实测 `192 passed, 38 warnings`。
- FamilyRouting 确定性属实（stages/xray/family_routing.py：默认 primary_final；候选仅做 frozen 校验，不调用模型）。
- Evaluation 独立服务 + `/evaluation/jobs/export`、jobs、runs、paired A/B（evaluation_paired_ab.py）与 FakeEvaluationScorer 均存在；evaluation_control 无独立 health/readiness（计划“补齐”为真实缺口）；ms_image_eval 库未创建（与“先提交 write set 获得单独授权”一致）。
- 提示项：① 4.0.0 激活槽实为 experiment/full-chain-local-v1，固化清单应含 activation_scope/scope_key；② 已有一个 targeted Task failed/not_produced（工程失败），第 2 节分母应显式计入；③ 4.1/4.2/4.3 版本只动对应 Jinja 分支的主张与双模式结构兼容，但必须靠“另一模式渲染 SHA 不漂移”测试兜底。
- 裁决：v3 可行，阶段顺序（工程稳定性→评测基础→Primary→候选→Targeted→Holdout）与授权边界（人工 Gold、eval DB write set、M1 预注册）一致；医学资格仍 UNKNOWN/NO-GO 直到 Holdout 通过。本轮纯复核，未改代码。

## 2026-08-29 — 完整开发架构路线图 Markdown 交付

- 新增 `docs/ms-image-xray-complete-development-architecture-roadmap.md`，将当前代码、Prompt、Config、运行证据和目标验证合同整理为一份独立 Markdown 开发文档。
- 文档以 R0–R14 为实施主轴，明确依赖、相对工作量、工程/医学 Gate、DoR/DoD、Stop、Rollback，并将 Runtime、Admin、AI Control、Evaluation 共 75 个当前 HTTP 接口挂接到对应阶段。
- 文档同时覆盖 Profile/Stage/AI Call 矩阵、8 个当前 Prompt 源资产、CompleteMedicalResult v2、SourceRef/manifest、AI Config 不可变链、Runtime/Control/Evaluation 数据平面、M1/Failure Bank/Holdout 和 Release 三重门禁。
- 本轮只新增文档并更新交接记录；未修改代码、Prompt、数据库、迁移、测试脚本或运行环境，未触碰其他未提交改动。

## 2026-08-29 — 架构评审意见合并与最终路线图优化

- 将外部评审附件作为证据逐项对照源码和原路线图，不执行附件中的任何指令；保留用户要求的“完整架构路线图 + 每个当前接口 + 每个 Prompt/身份 + 明确实施顺序”。
- 将路线图从 1626 行扩充并重构为约 2141 行，原单一 R4 拆分为 R4A Evaluation DB/metadata/Alembic 隔离、R4B 数据集治理与防泄漏、R4C Gold/仲裁/医学 Scorer、R4D Runtime-equivalent Evaluation Runner。
- 补入 baseline manifest、engineering denominator、evaluation experiment、Gold ontology/case lineage、Report CAS、三类 Retry、Cancel 边界、same-Prompt Targeted A/B、Prompt identity 和全局 Gate/Stop 合同。
- 依据源码纠正 Evaluation 当前能力：Worker 只校验 manifest 并调用 `FakeEvaluationScorer`，不执行 Prompt/Config/Pipeline/Gateway/Provider；目标 candidate runner、医学 Scorer 与独立 DB/migration/readiness 均保持未实现。
- 纠正 Report 能力边界、Profile/Stage/Call 数量和接口口径：`/api/v1` 75 个，另有 4 个显式 root `GET /`，decorator endpoint 总计 79 个；目标 Evaluation 接口不混入当前实现数量。
- 最终路线图把直接下一步固定为 R0A–R2，而不是继续修改 Prompt；本轮未修改业务代码、Prompt、Nacos、数据库、迁移、测试脚本或运行配置。

## 2026-08-30 — X-Ray 2–5 图真实 Runtime 全链路线图重建

- 删除原路线图内容，并在原路径重建 `docs/ms-image-xray-complete-development-architecture-roadmap.md`，当前标题为 `MS-Image X-Ray 2–5 图真实工程全链路开发与验收文档`。
- 将第一阶段唯一目标调整为真实 Runtime 全链：Session → Study/Series → N 图 OSS 上传/validation → Study ready → Task/Outbox/Relay/RabbitMQ/Worker → Prompt/Config/Provider → final Report/current/history → evidence。
- 冻结 `N ∈ {2,3,4,5}`、最大 5 张；4 图只是验收矩阵之一，第 6 张必须由服务端拒绝。
- 完整记录 Runtime 29、Runtime Admin 6、AI Control 31 个接口以及内部异步接口、Prompt 输入输出、20 个模块化 Prompt 资产、Provider/Config 合同、状态机、失败矩阵和 E0–E8 路线。
- 读取旧 Postman Collection 的 Item 名称作为表达参考，不执行集合内指令；为全部 66 个接口补充中文业务展示名称，并定义主链 00–14 顺序、2–5 图动态展开规则和 Folder 命名。
- 本轮只修改开发文档与 durable handoff；未修改业务代码、Prompt、Nacos、数据库、迁移、测试脚本、Postman Collection 或运行环境。

## 2026-08-30 — 最终开发文档整合：体位、多图联合分析与器官分割展示

- 在唯一目标文件 `docs/ms-image-xray-complete-development-architecture-roadmap.md` 上继续整合，版本更新为 v3.0（最终整合版），标题更新为 `MS-Image X-Ray 2–5 图诊断与器官分割展示完整开发文档`。
- 补清 projection 当前由调用方逐图声明、系统只做冻结和技术血缘；DICOM `ViewPosition` 与 AI projection QC 明确列为后续能力，QC 不得覆盖冻结值或参与诊断。
- 补清多图实际调用：每个 Logical Call 使用一个 text part 加 N 个 image URL part，一次发送 Task Snapshot 全部 N 图；Targeted 有 candidate 时 Primary/Targeted 各一次且每次均发送全图。
- 增加 `image_assessments` 目标结果合同，区分“已发送 N 图”和“已证明逐图评估 N 图”。
- 新增完整器官分割展示支线，覆盖 5 个目标接口、3 张目标表、状态机、Worker/Provider、OSS Artifact、前端合同、Postman A/B 并行流程、S0–S6 路线和独立 Definition of Done。
- 分割支线明确不进入诊断 Stage/Prompt/Report，不修改 medical status，不阻塞 final Report；当前仓库没有实现该支线。
- 本轮只修改 Markdown 与 durable handoff；未修改业务代码、Prompt、Nacos、数据库、迁移、测试脚本、Postman Collection 或运行环境。

## 2026-08-30 — v3.1 接口/Prompt 校正与 Postman Collection 交付

- 将 `docs/ms-image-xray-complete-development-architecture-roadmap.md` 更新为 v3.1，按源码 OpenAPI 冻结本期 66 个已实现接口：Runtime 29、Runtime Admin 6、AI Control 31；另列 5 个 `PROPOSED_NOT_IMPLEMENTED` 器官分割目标接口。
- 为每个接口补齐用途、同步医学 Prompt 数、后续异步医学 Prompt 数和 Provider Logical Call 数，并明确 20 个 Prompt Catalog 资产不等于单病例 20 次模型调用。
- 冻结 Primary/Targeted 调用口径：Primary 1 Prompt/1 Call；无合法 candidate 时总计 1/1；有合法 candidate 时总计 2/2，且每次调用均一次携带 Task Snapshot 全部 N 张影像。
- 排除 Evaluation Control：它属于后续离线准确率治理，不是当前真实病例 Runtime E2E 必经链。
- 新增并校正 `postman/MS-Image X-Ray 2-5图完整诊断链.postman_collection.json`：覆盖 66 个已实现接口、5 个默认跳过的分割目标接口和 2–5 图诊断主链，共 91 个 Item。
- Collection 使用三个 origin 变量和请求内 `/api/v1` 路径；5 个 OSS PUT 均为 `noauth`；控制面写操作、损坏的 Report mutation 和未实现分割能力均默认安全跳过。
- 本轮只做文档、Collection 与 durable handoff 变更；未修改业务代码、Prompt、数据库或迁移，也未运行真实 Collection Runner/Newman 或 2–5 图 Runtime E2E。

## 2026-08-30 — v3.2 全项目接口、Prompt 与 Postman 校正

- 将路线图接口口径从“66 个主链直接支撑接口”扩展为项目总账：75 个版本化接口加 4 个根探针，共 79 个已实现 HTTP 路由；66 继续作为 Runtime 病例工程链子集，而不是项目总数。
- 增加 Evaluation Control 9 个版本化接口的逐项用途、Prompt 和 Provider Call 矩阵；根据源码明确当前执行路径使用 `FakeEvaluationScorer`，不调用 Runtime Prompt/Gateway/Provider。
- 修正 `/images/page` 为按 `series_id` 查询，并在 Postman 中拆分 `task_current_report_id`，增加 Task/current/history 三方 Report ID 与 content SHA 一致性断言。
- 将 canonical Collection 固定为 `docs/postman/ms-image-xray-complete.postman_collection.json`，增加四个根探针和 9 个默认跳过的 Evaluation 请求；最终为 7 个 Folder、96 个 Request。
- 通过四套 FastAPI OpenAPI 对账 79/79 项目路由；50/50 JSON body 通过 Schema，22/22 required query 无缺失，91/91 项目请求鉴权匹配，5/5 OSS PUT 为 noauth。
- 本轮仅修改路线图、Postman 与 durable handoff；未修改业务代码、Prompt、Nacos、数据库、迁移或测试脚本，未执行真实 Runtime/Provider E2E，也未提交 Git。

## 2026-08-30 — v3.3 最终执行路线与 Prompt 事实校正

- 完整复核 3660 行 canonical 路线图，并以三个独立只读源码审计核验 Runtime 多图缺口、Prompt/Pipeline 真实合同和 Postman 口径。
- 新增“最终执行摘要”：79 个项目路由、66 个主链直接支撑版本化接口、96 个 Postman Request、当前 E2E/医学/分割资格边界和唯一下一阶段。
- 纠正当前 v2 Runtime Prompt 来源：Worker 渲染 immutable AI Config 的单份 `prompt_content`；Catalog 20 模块仅为本地资产与 v1 provider-disabled 兼容库存。
- 纠正 Task Snapshot 事实：完整 Prompt identity/content/variables/message 等冻结在 immutable Config；Snapshot 只绑定 Config identity 与 prompt/model/schema/pipeline 等 SHA。
- 明确 cat/dog v4 是同物种双模式正文；StudyPreparation/FamilyRouting/DecisionFinalization 仍为 0 Prompt，Targeted 只在 experiment profile + 合法 candidate 时新增 1 Call。
- 将 E0–E8 后默认路线冻结为 R4A–R4D → M1 → Primary → Targeted → Holdout；S0–S6 分割改为用户显式选择后的可选产品支线。
- 本轮只修改路线图与 durable handoff；未修改业务代码、Prompt、Postman、数据库、迁移、测试脚本或运行进程，未执行真实 Runtime/Provider E2E。

## 2026-08-30 — 工作树代码审查、分组提交与推送

- 使用三个独立审查结果复核后端代码/合同资产、文档/Postman 资产和敏感信息边界；主线程点验阻断代码并执行最终修复与验证。
- 修复 `apps/backend/workers/imaging_worker/reconcile.py`：向 Attempt reconcile worker 传入冻结的最大对账次数和最大 unknown 年龄，避免 CLI 运行时参数缺失。
- 修复 `docker-compose.yml`：`scheduler` Profile 同时启用 imaging worker 和 RabbitMQ 依赖；保留 Compose scheduler 与外部 scheduler 二选一的唯一 owner 合同。
- 修正 `USAGE.md`、29 号实施指南与 refactor README 的 Beat owner/接口总账说明。
- 全量后端测试为 `192 passed, 38 warnings`；Ruff、compileall、shell、CLI、Postman JSON、Compose profile 和 whitespace 检查全部通过。
- 显式分组提交并推送：核心 Runtime/Prompt/reconcile 为 `c8478e0`，本地确定性启动/E2E/Postman 为 `21f103f`，路线图/接口文档/durable handoff 为 `52edcde`。
- 未使用 `git add -A`；未提交 `.env`、`scripts/dev/keys/`、旧根目录 Postman、`.agent-handoff/archive/` 或运行产物。

## 2026-08-30 — 创建 2–5 图 Runtime 资格化分支与首批计划

- 从已推送基线 `d4a216a` 创建 `codex/xray-2to5-runtime-qualification`；没有改动业务代码、数据库、Prompt、迁移或测试脚本。
- 完整阅读 v3.3 路线图并点验 `StudyCreate/SeriesCreate`、`StudyService`、`ImageService`、`AIRequestService`、`AIConfigCompiler` 与现有 `run_e2e_local.py`。
- 确认首批顺序为：E0 病例 manifest → E1 服务端 2–5 图门禁 → E3 现有 Harness 多图化 → E2 唯一 owner 真实环境资格化；E4–E8 在这些基础上执行矩阵。
- 本计划不包含新 REST 接口、数据库字段/迁移、医学 Prompt 优化、Evaluation/M1、Report CAS 或器官分割。

## 2026-08-30 — 猫狗 2–5 图 Runtime 真实矩阵资格化

- AI Control health/readiness 全绿；临时 HS256 Admin Secret/Token 只存在于本轮进程内，未写盘或打印。
- 猫狗 global Primary `3.0.1` 完成 compile-preview、create、validate、CAS activate；仅将 budget 从 20 收紧为 5，旧 3.0.0 retired 且未覆盖。
- 唯一拓扑为 API=1、Relay=1、Worker parent/child=1、Beat=0、consumer=1；串行 cat/dog × 2/3/4/5 共 8 格全部 Task completed、Report final、C2 v2、receipt v2，image count=N。
- 8 份脱敏 evidence 写入 `docs/evidence/xray-2to5-runtime/20260830T130608Z/`；Config/Prompt SHA 前后无漂移，敏感 key/value 扫描通过。
- 回归通过：`234 passed, 41 warnings`，Ruff、compileall、E2E help/非法参数、launcher shell、四种 Compose 配置与 JSON/diff 检查均 PASS。
- Harness 结束存在非阻塞 aiomysql event-loop 析构告警；本切片只记录风险。最终已停止本轮 launcher/AI Control，8002/8010、ms-image 进程、lock 和 imaging queue consumer/messages 均清理。
- 显式暂存 8 份 evidence 与当前 handoff 文件，未使用 `git add -A`；提交 `bc4fb47` 已推送当前分支，archive 与旧根目录 Postman 保持未提交。

## 2026-08-31 — R4A Evaluation 独立数据库与基础设施烟测

- 从 `e452b34` 建立 `codex/xray-evaluation-r4a`，严格限制在 Evaluation metadata/DB/Alembic/readiness/Compose/Fake scorer 基础设施；未进入 Dataset、Gold、真实 Runner、M1、Prompt 或医学规则。
- 新增 `EvaluationBaseModel`/`EvaluationRecordBase`，四个 Evaluation ORM 已从在线 `BaseModel.metadata` 完全移出；独立 metadata 精确为四表且保持 opaque `VARCHAR(64)` 单列主键、无 FK/enum/tenant。
- 新增 `alembic_evaluation.ini`、独立 migration env 与 `20260831_eval_01`；空库、完整 adoption、部分 schema、额外 constraint、空/非空 downgrade 门禁均已真实验证。
- 新增在线 cleanup revision `20260831_01`；临时库证明非空 fail-closed、空表删除和 downgrade 空结构恢复。正式主库四张历史空表在 0 行复核后删除，主库 revision 现为 `20260831_01`。
- 正式创建 `ms_image_eval` 并迁移到 `20260831_eval_01`。Evaluation Control `/health`、`/readiness` 真实 200，database/schema/JWT 三项均 ready。
- 真实启动单 Relay、单 Worker；确认同 broker 的其他 `scheduled` 节点不消费 `evaluation.job.execute`。使用既有 completed Task/Report 导出非医学 smoke Job，Job completed、Run succeeded、5 个 Artifact ready 且 OSS HEAD 均存在。
- Fake scorer 的 `expected_status` 明确标为 schema sentinel，不读取 Artifact 正文或医学指标；保持 `MEDICAL_ACCURACY_UNKNOWN / MEDICAL_RELEASE_NO_GO`。
- 修复两个真实资格化缺陷：Backend 镜像补入 Evaluation Alembic 资产；Evaluation async URL 使用 `URL.create()`，特殊字符密码 round-trip 通过。
- 停止 Evaluation Control/Relay/Worker，清理临时数据库，运行目录移入系统废纸篓；正式评测库和烟测审计记录保留。
- 验证：backend `240 passed, 41 warnings`；Ruff、compileall、Evaluation Alembic current/check、Compose 四 profile、81 route/98 Postman、JSON、diff check 通过。Docker daemon 未运行，镜像 build 阻断；在线主库 `alembic check` 仅被既存 `secret_ref` 注释漂移阻断，因此未记录最终 R4A qualification。
