# 代理交接当前快照

## 当前目标与状态

- 最后更新：2026-08-26
- 工作区：`/Users/mozhicheng/workspace/code/cy-code/ms-image`
- 当前分支：`codex/prompt-runtime-ai-gateway`
- 当前 HEAD：`492a249c98175bf818ce092451585db766d73e76`
- 当前目标：保持完整 XRay（X 光）阶段顺序不变，同时将 `ms-image` 的 AI 请求和 Prompt/Nacos 链严格收敛到 `/Users/mozhicheng/workspace/code/cy-code/ms-ai-fast` 的直接运行合同，删除偏离参考链的 Secret Resolver、Provider 原始响应加密存储和 Gateway 适配包装。
- 当前状态：`MS_IMAGE_CORE_AI_NETWORK_CHAIN_PASSED / FULL_WORKER_RUNTIME_NOT_QUALIFIED / MEDICAL_ACCURACY_UNKNOWN / MEDICAL_RELEASE_NO_GO`。

## 当前代码事实

- AI 请求直接使用 `apps/backend/core/ai/gateway_client.py:GatewayClient`；运行凭据只来自 `AI_PLATFORM_OPENAI_BASE_URL` 与 `AI_PLATFORM_API_KEY`，与 `ms-ai-fast` 同语义。正式 Worker 不再解析冻结 `secret_ref`，也不存在 `MS_IMAGE_AI_SECRET_*` 或 `env-secret://...` 运行链。
- Prompt/Nacos 使用共享 `NACOS_*` 配置；请求参数为 `namespaceId/promptKey/version/label`。Prompt 正文保持 Nacos 原文，渲染采用 Jinja `StrictUndefined`、`tojson` 和 `$variable`，允许冻结合同中声明的任意合法变量名。
- Gateway messages 固定为单条 `user` message，内容是完整渲染后的 Nacos Prompt；遗留 `message_contract_json` 字段仅为现有模型/数据库兼容元数据，不再改变实际 Provider messages。
- Provider 原始响应不再写入自定义 OSS response store；数据库保留 Provider Request ID、规范化结构化结果、响应 SHA 和 Attempt 审计事实，不保存原始响应正文或 response object reference。
- OSS signer 仅用于向 Provider 提供受限制的影像短期读取 URL。unknown Attempt 仍通过 `ProviderAttemptLookup` 边界处理；默认 `UnsupportedProviderAttemptLookup` 禁止盲目重发，但尚无真实 Provider 原请求查询能力。
- 已删除 `OpenAICompatibleGatewayAdapter`、`EnvironmentReferenceSecretResolver`、`OSSEncryptedResponseStore`、`GatewayRuntimeDependencies` 及其相关文件/生产引用；生产代码扫描无残留。

## 本切片验证

- `python -m pytest apps/backend/tests/test_ai_prompt_control_plane_contracts.py apps/backend/tests/test_ai_gateway_attempt_contracts.py apps/backend/tests/test_ai_prompt_control_plane_models.py -q`：`81 passed, 19 warnings`。
- 相关 AI、Control Plane Service、Runtime Service 和 Worker 目录 `compileall`：`COMPILE_OK`。
- 旧 Gateway/Secret/Response Store 配置与类名生产代码扫描：无输出；Provider 原始响应存储路径扫描：无输出；`git diff --check`：`DIFF_CHECK_OK`。
- 本轮未执行真实 MySQL、OSS、Broker、Nacos、Provider 或医学验证；上述离线验证不能升级为完整 Worker Runtime 或医学放行。

## 下一动作、阻断与边界

- 下一最小动作仍是 P1 Worker Runtime Qualification：用同一冻结 Task 取得 MySQL -> Outbox -> Broker -> Worker -> OSS image signing -> `GatewayClient` -> Provider -> Attempt -> Stage -> Report 的真实非敏感证据。
- 真实 Worker 启动进程是否加载 `AI_PLATFORM_OPENAI_BASE_URL` 与 `AI_PLATFORM_API_KEY` 尚未在完整任务链中验证；不得用交互进程或单次核心 AI 请求替代该证据。
- `secret_ref` 仍存在于既有 Control Plane 模型、Schema 和 Config 哈希输入中，但不参与 Worker Provider 鉴权。彻底删除该字段需要表/字段/迁移授权，本切片不执行。
- Provider 原请求查询仍为 `UnsupportedProviderAttemptLookup`；unknown 不盲发，但可能长期等待对账。
- 数据库 baseline/migration、建表、改表、删表和重命名均未获本切片授权；不得执行。
- Python 不得改写 `normal / abnormal / review_required / non_diagnostic` 医学结论；`MEDICAL_ACCURACY_UNKNOWN / MEDICAL_RELEASE_NO_GO` 保持不变。

## 当前活动文件

- AI/Prompt 主链：`apps/backend/core/ai/gateway_client.py`、`apps/backend/core/ai/prompting/renderer.py`、`apps/backend/core/ai/prompting/message_contract.py`、`apps/backend/services/ai_control/service/prompt_source.py`、`apps/backend/core/config.py`。
- Runtime/Worker：`apps/backend/services/runtime/service/ai_request_service.py`、`apps/backend/services/runtime/service/ai_attempt_reconcile_service.py`、`apps/backend/workers/imaging_worker/stage_execution.py`、`apps/backend/workers/imaging_worker/ai_attempt_reconcile.py`、`apps/backend/workers/imaging_worker/reconcile.py`、`apps/backend/workers/imaging_worker/celery_app.py`。
- 现有测试：`apps/backend/tests/test_ai_prompt_control_plane_contracts.py`、`apps/backend/tests/test_ai_gateway_attempt_contracts.py`、`apps/backend/tests/test_ai_prompt_control_plane_models.py`。
