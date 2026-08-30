# Handoff Snapshot

## Current State

- Last updated: 2026-08-30（代码审查、分组提交与首轮远端推送完成）
- Workspace root: `/Users/mozhicheng/workspace/code/cy-code/ms-image`
- Current objective: 以 `docs/ms-image-xray-complete-development-architecture-roadmap.md` 为唯一开发入口，先完成猫/狗真实 X-Ray 2–5 图 Runtime E2E；通过后默认建设 R4A–R4D、M1 并开始 Primary/Targeted 单变量医学优化。器官分割只作为用户明确选择后的独立可选展示支线。
- Current status: 路线图与 Postman Collection 已按四套 FastAPI App 的源码/OpenAPI 完成静态资格化。项目总账为 79 个 HTTP 路由：75 个版本化接口（Runtime 29、Runtime Admin 6、AI Control 31、Evaluation Control 9）和 4 个非版本化 `GET /` 根探针；Runtime 病例工程链直接支撑子集仍为 66 个版本化接口。另列 5 个 `PROPOSED_NOT_IMPLEMENTED` 分割目标接口，但不计入 79。
- Postman artifact: `/Users/mozhicheng/workspace/code/cy-code/ms-image/docs/postman/ms-image-xray-complete.postman_collection.json`，Postman v2.1，96 个 Request；覆盖 79/79 项目路由、5 个 OSS `noauth` PUT 和 12 个多影像槽重复请求。Evaluation Folder 默认跳过，5 个未实现分割接口只作为说明，不创建虚构 Request。
- Current architecture decision: `existing-entry internal modular correction`。继续复用 `API -> Service -> CRUD(DalBase) -> Model/MySQL` 与 `Task -> Outbox -> Relay -> RabbitMQ -> Worker -> Stage Registry -> Gateway/Provider -> Report`；禁止创建第二套 Runtime、Repository、CRUDBase、DatabaseService、Pipeline 或医学事实源。
- Current Git evidence: branch `codex/prompt-runtime-ai-gateway`；核心合同 `c8478e0`、本地验收工具 `21f103f`、路线图与文档 `52edcde` 均已推送到 `origin/codex/prompt-runtime-ai-gateway`。剩余工作树只保留明确排除的旧 Postman、tracked archive index 和 handoff archive；继续禁止 reset/clean/restore。
- Current local processes: 本轮未启动或动态核验 Runtime、AI Control、Relay、RabbitMQ、Worker、OSS、Provider 或数据库。

## Completed In This Slice

- 逐文件审查当前代码、Prompt、迁移、脚本、Postman 与敏感信息边界；确认本地 `.env`、`scripts/dev/keys/`、旧根目录 Postman 和 `.agent-handoff/archive/` 不进入提交。
- 修复 `ImageReconciler` 未传 P1-B `max_reconcile_count/max_unknown_age_seconds` 的运行时 `TypeError` 风险。
- 修复 Compose 单独启用 `scheduler` Profile 时未启用 imaging worker/RabbitMQ 依赖的问题；本地 launcher 保持不拥有 Beat，唯一 owner 为 Compose scheduler 或外部调度器。
- 后端全量测试 `192 passed, 38 warnings`；Ruff、compileall、reconcile CLI、launcher shell、E2E CLI help、Postman JSON、四种 Compose profile 和 diff check 全部通过。
- 已生成并推送 `c8478e0 feat(xray): complete runtime prompt and reconciliation contracts`、`21f103f feat(dev): add deterministic local xray chain tooling` 与 `52edcde docs(xray): finalize runtime and medical optimization roadmap`。

- 将路线图更新为 v3.3，新增一页最终执行摘要，明确唯一下一阶段为 `RUNTIME_2_TO_5_IMAGE_DETERMINISTIC_QUALIFICATION`；E0–E8 完成前禁止先做医学 Prompt 优化、Targeted 效果实验、Evaluation M1 或器官分割。
- 纠正 Prompt 事实：当前 v2 Worker 每个 Logical Call 直接渲染 immutable `AIConfigRecord.prompt_content`；Catalog 20 个模块只是本地资产库存与 v1 provider-disabled 兼容输入，不是 v2 单病例逐个执行的 20 份 Prompt。
- 纠正冻结边界：完整 Prompt identity/content/variables/message/schema/model/pipeline 位于 immutable Config 行；Task Snapshot 只保存 Config identity 与 config/release/prompt/model/schema/pipeline SHA 等绑定事实，不复制完整 Prompt 正文。
- 明确 cat/dog v4 是同一物种的双模式正文：`PRIMARY_RESULT_JSON` 缺失时是 Primary，存在时是 Targeted；确定性 Stage 不创建 Prompt，`targeted-review/common` 本地文件当前也不是 Prompt Source importer 可达身份。
- 将 E0–E8 后默认路线改为 R4A Evaluation DB → R4B Dataset → R4C Gold/Scorer → R4D Runtime 等价 Runner → M1 → Primary → Targeted → Holdout；S0–S6 分割降为用户显式选择后的可选产品支线。

- 将路线图更新为 v3.2，并建立“79 个项目路由 / 75 个版本化接口 / 66 个 Runtime 主链直接支撑接口”的分层口径，避免把主链子集误报为项目全部接口。
- 为 Runtime 29、Runtime Admin 6、AI Control 31、Evaluation Control 9 和 4 个根探针逐项明确用途、同步/异步医学 Prompt 数及 LLM Provider Logical Call 数。
- 明确所有 REST handler 同步病例医学 Prompt 均为 0；只有 `POST /api/v1/tasks` 成功后由 Worker 异步触发病例模型链。Primary 为 1 Prompt/1 Call，Targeted 有合法 candidate 时为 2/2，replay 与当前 Evaluation Fake scorer 均为 0/0；N 张影像仍在一次 Logical Call 中联合发送。
- 将 Evaluation Control 纳入项目接口总账与独立 Postman Folder，同时明确当前 Worker 使用 `FakeEvaluationScorer`，不执行 Runtime Prompt、Config、Gateway 或 Provider，不能用于 M1 或医学准确率结论。
- 修正 `/images/page` 为 `series_id` query；修复 Task/current/history 三方 Report ID 一致性证据；增加 `task_current_report_id` 独立变量。
- Collection 固定四套 `/api/v1` base URL 与四套 root origin；AI Control、Admin、损坏 Report mutation 和 Evaluation 请求分别通过实际 `enable_*` 变量默认跳过。
- 5 个 OSS signed URL PUT 均为 `noauth`；Collection 未发现真实 JWT、API key、Private Key、密码、影像、Prompt 正文、Provider 原文或报告正文。

## Current Qualification

```text
XRAY_DOCUMENT_V3_3_STATIC_QUALIFIED
PROJECT_HTTP_ROUTE_MATRIX_79_OF_79
RUNTIME_INTERFACE_MATRIX_29_OF_29
RUNTIME_ADMIN_INTERFACE_MATRIX_6_OF_6
AI_CONTROL_INTERFACE_MATRIX_31_OF_31
EVALUATION_CONTROL_INTERFACE_MATRIX_9_OF_9
POSTMAN_COLLECTION_96_REQUESTS_STATIC_QUALIFIED
POSTMAN_JSON_BODY_SCHEMA_50_OF_50
POSTMAN_REQUIRED_QUERY_22_OF_22
POSTMAN_OSS_NOAUTH_5_OF_5
PROMPT_PROVIDER_COUNT_CONTRACT_FROZEN
SEGMENTATION_5_INTERFACES_PROPOSED_ONLY
EXISTING_ENTRY_INTERNAL_MODULAR_CORRECTION_SELECTED
BACKEND_TESTS_192_PASSED
CORE_AND_LOCAL_TOOLING_PUSHED

RUNTIME_E2E_NOT_RUN_IN_THIS_SLICE
RUNTIME_2_TO_5_IMAGE_E2E_NOT_RUN
MAX_5_IMAGE_SERVER_GUARD_NOT_IMPLEMENTED
MULTI_IMAGE_E2E_HARNESS_NOT_IMPLEMENTED
IMAGE_ASSESSMENTS_COVERAGE_NOT_IMPLEMENTED
SEGMENTATION_RUNTIME_NOT_IMPLEMENTED
CURRENT_RUNTIME_ENVIRONMENT_UNKNOWN
MEDICAL_ACCURACY_UNKNOWN
MEDICAL_RELEASE_NO_GO
```

## Immediate Next Actions

1. E0：准备猫/狗 × 2/3/4/5 的真实病例 manifest；每张图显式记录路径、SHA256、大小、content type、projection、sequence_no。
2. E1：在现有 Schema/Service/AIRequest/Config 路径补齐 `2 <= N <= 5` 门禁；多 Series 总数也不得超过 5，第 6 张必须由服务端拒绝。
3. E2：启动并核验 Runtime、MySQL、Redis、RabbitMQ、Relay、Worker、OSS 与真实 Provider；Compose 使用 `broker` profile。
4. E3：只扩展现有 `scripts/dev/run_e2e_local.py`，把单图硬编码参数化为同一 Study 的 2–5 图；不要新增第二套测试框架。
5. 导入已交付 Collection，填写 Runtime/Admin/AI Control Token、2–5 张真实影像路径、SHA256、bytes、projection 后，以 Runner/Newman 执行诊断主 Folder；不要启用控制面/Admin/Evaluation 写门禁。
6. E4–E6：验证 N 次 OSS PUT、Image Validation、Study finalize、Task/Outbox/Relay/RabbitMQ/Worker、真实 Provider、Task completed、首份 final Report、current/history。
7. E7–E8：执行 cat/dog × 2/3/4/5 验收矩阵并保存 evidence；完成前不得转入 Evaluation、Gold、Scorer 或医学优化。
8. E0–E8 通过后默认推进 R4A–R4D、M1、Primary/Targeted 单变量优化；只有用户明确优先展示能力时才推进 S0–S6，迁移、测试脚本和分割实现仍需另行授权。

## Active Files

- `docs/ms-image-xray-complete-development-architecture-roadmap.md`
- `docs/postman/ms-image-xray-complete.postman_collection.json`
- `AGENT_HANDOFF.md`
- `.agent-handoff/snapshot.md`
- `.agent-handoff/work-log.md`
- `.agent-handoff/validation.md`
- `.agent-handoff/decisions.md`
- `.agent-handoff/backlog.md`
- `.agent-handoff/risks.md`

## Blockers / Open Questions

- 当前 `StudyCreate.expected_image_count` 与 `SeriesCreate.expected_image_count` 尚未证明具备 `le=5`，第 6 张上传服务端门禁未资格化。
- `scripts/dev/run_e2e_local.py` 仍固定单图；`--repeat` 是重复病例，不是同一 Study 多图。
- projection 当前来自调用方声明，不是 AI 自动识别；DICOM `ViewPosition` 与 projection QC 尚未实现。
- receipt 证明一个 Logical Call 发送全部 N 张图，但结果 Schema 尚无 `image_assessments` 全输入覆盖合同。
- cat/dog active Config 的实际 `max_input_images=5` 和当前环境服务就绪状态均未动态确认。
- 分割 API、表、Worker、Provider 和 Artifact 当前均未实现；5 个 Postman 请求只是默认跳过的目标合同。
- Report revision 1 final/current/history 是 P0 终点；publish/void/第二 revision 因 CAS 风险仍不应启用。

## Validation Summary

- 文档：3660 行、151896 bytes、SHA256 `71a1c98a3f1a542ffb3f25685d40d845b5a0248ce0bd097f215f87fa7e531556`。
- Postman：5167 行、206425 bytes、SHA256 `f5f8cfcadc2db872546078ea37296d6bc48615c56aa2b8cc29b15e2846a27f3e`。
- OpenAPI 对照：Runtime 30/30（含根探针）、Runtime Admin 7/7（含根探针）、AI Control 32/32（含根探针）、Evaluation Control 10/10（含根探针）；Collection 79/79 项目路由无 missing/extra，另有 5 个外部 OSS PUT。
- 文档矩阵：Runtime 29/29、Runtime Admin 6/6、AI Control 31/31、Evaluation Control 9/9；四个根探针另表列出；5 个分割目标接口保持未实现。
- Prompt：v2 Runtime 每个 Config 冻结并渲染 1 份完整正文；Catalog 20 个模块是本地/v1 兼容资产库存。单病例实际医学调用固定为 1 或 2，不是 20。
- Postman：96 个 Request；50/50 JSON request body 通过对应 OpenAPI Schema，22/22 required query 请求无缺失，91/91 项目请求鉴权与 OpenAPI 一致，5/5 OSS PUT 为 `noauth`；每个项目请求说明均包含用途和 Prompt/Provider 数。
- Markdown：228 个代码围栏且数量为偶数；`python -m json.tool`、四 App 路由计数和 `git diff --check` 均通过。
- 提交前动态验证：`PYTHONPATH=. pytest -q apps/backend/tests` 为 `192 passed, 38 warnings`；Ruff、compileall、launcher/E2E CLI、reconcile CLI、Postman JSON 与 Compose default/broker/scheduler/broker+scheduler 均 PASS。
- Git：`c8478e0`、`21f103f`、`52edcde` 已成功推送到 `origin/codex/prompt-runtime-ai-gateway`；私钥、`.env`、旧 Postman 与 archive 未进入这些提交。
- 真实 E2E：NOT RUN / UNKNOWN；不得把静态资格化写成 Runtime 全链 PASS。
