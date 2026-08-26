# 代理交接当前快照

## 当前目标与状态

- 最后更新：2026-08-26
- 工作区：`/Users/mozhicheng/workspace/code/cy-code/ms-image`
- 当前分支：`codex/prompt-runtime-ai-gateway`
- 当前 HEAD：`325dd8e42d596e0b28a22ece3806da001ec4f2a6`（已推送至 `origin/codex/prompt-runtime-ai-gateway`）。
- 当前目标：先完成 P0 Database Baseline，再继续 P1 最小代码切片（允许已资格化的 Provider-enabled Config 冻结为 Task）和真实 Worker 链资格化。
- 当前状态：`MS_IMAGE_CORE_AI_NETWORK_CHAIN_PASSED / FULL_WORKER_RUNTIME_NOT_QUALIFIED / MEDICAL_ACCURACY_UNKNOWN / MEDICAL_RELEASE_NO_GO`。

## 本轮只读代码与 P0 审计事实

- 当前工作树干净；`325dd8e` 已提交并推送，`git push origin HEAD` 返回 `Everything up-to-date`。本轮没有业务源码改动、没有数据库写入或迁移。
- AI/Prompt 请求链直接使用 `GatewayClient` 和 `AI_PLATFORM_OPENAI_BASE_URL + AI_PLATFORM_API_KEY`，保持与 `ms-ai-fast` 同语义；旧 `EnvironmentReferenceSecretResolver`、`OpenAICompatibleGatewayAdapter`、`OSSEncryptedResponseStore`、`GatewayRuntimeDependencies` 及 `AI_GATEWAY_*` / `MS_IMAGE_AI_SECRET_*` 生产引用扫描均无残留。
- 代码仍存在未被运行路径使用的 legacy `response_object_ref_json` 模型/DAL/未部署迁移字段：`models/ai_call.py`、`models/ai_call_attempt.py`、`crud/ai_call.py`、`crud/ai_call_attempt.py`、`20260824_02...`。它与“Provider 原始响应不存 OSS/对象引用”的当前合同不一致；删除或兼容处理必须在 P0 确定数据库方案后按授权处理，当前未改动。
- `TaskService._validate_assignable_config()` 仍将 `capability_manifest.provider_disabled is True` 作为 Task 冻结前提；而 `AIRequestService` 网络路径要求 `provider_enabled + qualification_status=qualified`。这是下一最小业务代码切片，但严格顺序要求先完成 P0。
- P0 只读连接 `ms_image` 成功：MySQL `9.3.0`、45 张物理表、无 `alembic_version`；目标 Runtime 表中仅旧的 `session_record`、`ai_prompt_template`、`ai_api_connection`、`ai_model_pool` 同名存在。
- 这些同名表含既有数据且结构与当前 ORM/迁移不兼容：`ai_prompt_template` 375 行、`ai_api_connection` 96 行、`ai_model_pool` 19 行、`session_record` 5772 行；`ai_config_record`、Task/Stage/Outbox/Call/Attempt/Report 等目标表不存在。现有 `20260824_01` 会直接 `create_table` 同名控制面表，因此不得直接对 `ms_image` 执行 `alembic upgrade head`。

## 本轮验证

- `python -m pytest apps/backend/tests/test_ai_prompt_control_plane_contracts.py apps/backend/tests/test_ai_gateway_attempt_contracts.py apps/backend/tests/test_ai_prompt_control_plane_models.py -q`：`81 passed, 19 warnings`。
- 相关 AI、Control Plane、Runtime、Worker 目录 `compileall`：`COMPILE_OK`。
- `git show --check HEAD`、`git diff --check`：通过；工作树干净。
- 未运行真实 MySQL Schema 迁移、Outbox、Broker、正式 Worker、Provider 外网 signed GET 或医学验证。

## 下一动作、阻断与边界

- P0 的唯一阻断是数据库边界选择：必须由用户明确选择新 Runtime 数据库，或授权为旧 `ms_image` 设计经审阅的兼容/迁移方案；在此之前不迁移、不建库、不改表。
- P0 通过后，下一最小代码切片只改 `apps/backend/services/runtime/service/task_service.py` 和现有 `apps/backend/tests/test_ai_gateway_attempt_contracts.py`；不新增表、字段、迁移、配置或 Service。
- 之后才用同一冻结 Task 获取 MySQL -> Outbox -> Broker -> Worker -> OSS -> Provider -> Attempt -> Stage -> Report 的非敏感证据。
- unknown 仍不能盲目重发；当前默认 Provider lookup 是 unsupported，真实 Provider 原请求查询合同尚未确认。
- Python 不得改写 `normal / abnormal / review_required / non_diagnostic`；不恢复 `file_asset`、不删除 v1 兼容链、Worker 不读取 Nacos latest。
