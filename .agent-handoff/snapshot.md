# 代理交接当前快照

## 当前目标与状态

- 最后更新：2026-08-26
- 工作区：`/Users/mozhicheng/workspace/code/cy-code/ms-image`
- 当前分支：`codex/prompt-runtime-ai-gateway`
- 当前 HEAD：`6057ec950cf329e34a3da308f07a928f7dabb086`（已推送至 `origin/codex/prompt-runtime-ai-gateway`）。
- 当前目标：在 P0 数据库边界未授权变更的前提下，完成 P1 的真实 Worker 配置差距确认；随后只能在明确数据库方案和真实 Worker 配置就绪后取得 E1 同一冻结任务证据。
- 当前状态：`MS_IMAGE_CORE_AI_NETWORK_CHAIN_PASSED / FULL_WORKER_RUNTIME_NOT_QUALIFIED / MEDICAL_ACCURACY_UNKNOWN / MEDICAL_RELEASE_NO_GO`。

## 本轮已提交的最小业务修正

- 提交并推送 `6057ec9 fix(xray): admit qualified provider configs`，只改 `apps/backend/services/runtime/service/task_service.py` 与既有 `apps/backend/tests/test_ai_gateway_attempt_contracts.py`。
- v2 Task Admission 现规范化冻结的 `gateway_profile_json`，并要求 `capability_manifest.provider_disabled == not gateway_profile.provider_enabled` 与 `gateway_profile_sha256` 匹配。因而已资格化、启用 Provider 的 v2 Config 能被安全冻结；profile/capability 不一致、未资格化 Provider 或无效 profile 都会在 Task 创建前拒绝。
- v1 provider-disabled 兼容链保持不变；未改 Task Snapshot 字段、Outbox、Worker、unknown、重试、医学状态、模型、表或迁移。

## P0/P1 当前事实与阻断

- P0 只读连接 `ms_image`：MySQL `9.3.0`、45 张物理表、无 `alembic_version`。有数据的 `ai_prompt_template`（375）、`ai_api_connection`（96）、`ai_model_pool`（19）、`session_record`（5772）同名但与 Runtime ORM/迁移不兼容；`ai_config_record`、Task/Stage/Outbox/Call/Attempt/Report 等目标表不存在。当前禁止在旧库执行 `alembic upgrade head`。
- AI/Prompt 运行代码与 `ms-ai-fast` 同语义：`GatewayClient` 仅使用 `AI_PLATFORM_OPENAI_BASE_URL + AI_PLATFORM_API_KEY`；旧 Secret Resolver、Gateway Adapter、response store、`AI_GATEWAY_*` 和 `MS_IMAGE_AI_SECRET_*` 生产链均已删除。Worker 只从 Task Snapshot 读取冻结 Prompt/Config，不读 Nacos latest。
- 当前本地非敏感 Settings 核验：`Settings.Config.env_file` 指向 `.env-01`；`.env` 与 `.env-01` 均没有非空 `AI_PLATFORM_OPENAI_BASE_URL` / `AI_PLATFORM_API_KEY`，本进程 `settings.ai_platform_configured=False`。OSS Settings 为 ready、Broker enabled、MySQL DB configured，但这不构成 Worker 可调用 Platform 的证据。不得恢复旧 `AI_GATEWAY_*` 配置；应将上述两个现有 ms-ai-fast 配置安全注入真实 imaging Worker 启动环境。
- OSS signer 已限制 profile/object/version/hash/size/MIME、HTTPS host allowlist 和 30–900 秒 TTL；隔离对象的本机 PUT/HEAD/Worker GET/signed GET/cleanup 曾通过。Provider 外部读取短签名 URL 仍为 `UNKNOWN`。
- unknown Attempt 不盲目重发：默认 `UnsupportedProviderAttemptLookup` 仅重排原请求对账；尚缺真实 Platform/Provider 原请求查询合同和有界终态策略。
- 未被运行路径写入的 legacy `response_object_ref_json` 仍在 AI Call/Attempt 模型、DAL 和未部署 migration 中；删除/兼容必须等待 P0 数据库方案和明确迁移授权。

## 本轮验证

- `python -m ruff check apps/backend/services/runtime/service/task_service.py apps/backend/tests/test_ai_gateway_attempt_contracts.py`：PASS。
- `python -m pytest apps/backend/tests/test_ai_prompt_control_plane_contracts.py apps/backend/tests/test_ai_gateway_attempt_contracts.py apps/backend/tests/test_ai_prompt_control_plane_models.py -q`：`86 passed, 19 warnings`。
- `python -m compileall -q apps/backend/services/runtime/service/task_service.py apps/backend/tests/test_ai_gateway_attempt_contracts.py`：PASS。
- `git diff --check`、cached diff check、commit、`git push origin HEAD`：PASS；当前业务工作树干净。
- 未运行 MySQL Schema migration、真实 Outbox/Broker/Celery/Worker、Provider 外网 signed GET、同一冻结 Task 全链或医学验证。

## 下一动作与边界

1. 用户/部署环境将 `AI_PLATFORM_OPENAI_BASE_URL` 与 `AI_PLATFORM_API_KEY` 成对注入实际 imaging Worker 进程（不写入数据库、Nacos、Task Snapshot、日志或交接材料）；然后只读确认 Worker `Settings` 的 presence，不输出值。
2. 用户明确选择 P0：独立 Runtime 数据库，或旧 `ms_image` 的备份/兼容/baseline/stamp/rollback 方案并授权迁移。此前不建库、不迁移、不改表。
3. 两项前提具备后，以同一冻结 Task 采集 MySQL -> Outbox -> Broker -> Worker -> OSS -> ms-ai-platform -> Provider -> Attempt -> Stage -> Report 的脱敏证据；unknown、取消、重复投递和迟到结果另行验证。
4. 不进入 M1/Q3/Q4/M2/R1/R2/R3；Python 不得改写 `normal / abnormal / review_required / non_diagnostic`，不恢复 `file_asset`，不删除 v1 链。
