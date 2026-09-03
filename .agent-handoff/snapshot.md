# Handoff Snapshot

## Current Objective

- Last updated: 2026-09-03
- Active branch: `codex/per-flow-model-routing`
- Active objective: 完成 `ms-image` AI/Prompt 调用去数据库配置化：按 Stage 在代码中直接声明 `MODEL_ROUTE` 与 `PROMPT_KEYS`，复用现有 Worker、`AIRequestService`、Gateway 和运行审计链。
- Evidence level: `CODE_IMPLEMENTED / MOCK_FULL_CHAIN_PASS / FULL_TESTS_PASS / EXTERNAL_E2E_ENVIRONMENT_BLOCKED`。
- Write set: 当前 AI 路由、Prompt Runtime、Task/Worker/Gateway/Stage 改造文件、现有合同测试文件和必要 handoff；不修改 `ms-ai-fast`、`ms-ai-platform`，不新增 migration 或独立测试脚本。
- External permissions: 仅 Git commit/push 已获授权；未执行数据库、Nacos、Provider、OSS、Broker 等外部写入。
- Completion gate: 静态检查通过，现有测试全量 `381 passed`，Mock Prompt→Gateway 全链通过，handoff 完成，普通 commit/push 成功。
- Stop gate: 真实 Prompt Runtime、Platform 或 Provider 环境缺失时只报告 `ENVIRONMENT_BLOCKED`；不得伪报真实外部 E2E，也不得跨仓库绕过 Platform。

## Implemented Runtime Contract

- 新 XRay Task 使用代码拥有的 profile/runtime identity，不调用 active `AIConfigRecordDal`，也不生成 `stage_ai_config_bindings`。
- XRay AI Stage 直接声明 `AiModelRoute(models=("gpt-5.6-sol",), mode="race")` 和按物种 `PROMPT_KEYS`。
- Prompt 链：Stage → `StageAIRequest` → Worker → `PromptRuntimeClient.render()` → `prepare_structured_call()`。
- 模型链：Call/Attempt 冻结 → `load_attempt_for_network()` → `GatewayClient.chat_completions()` → `{AI_PLATFORM_OPENAI_BASE_URL}/chat/completions`。
- Prompt key、模型候选和 route mode 不从 ms-image 数据库读取；数据库继续保存 Task、Stage、Call、Attempt、runtime request snapshot 与审计事实。
- 历史 Config Task/replay 继续保留 frozen Config 校验，避免破坏已有任务回放。
- Anatomy Localization 和 Image Quality 结果查询对 code-owned Task 从 Call 的冻结 runtime snapshot 校验 schema/route/prompt lineage，不读取 Config DAL。
- `xhigh` / `reasoning_effort` 按用户要求本轮不处理。

## Validation Status

- `PYTHONPATH=. /opt/homebrew/anaconda3/bin/pytest apps/backend/tests -q` → `381 passed, 48 warnings`。
- Mock Prompt Runtime → Stage → Call/Attempt → Gateway 定向链 → `6 passed, 4 warnings`。
- Gateway/Attempt 合同定向集 → `299 passed, 48 warnings`。
- `python -m compileall -q apps/backend`、Ruff changed-file check、`git diff --check` 均通过。
- 真实外部 E2E：`ENVIRONMENT_BLOCKED`；`PROMPT_RUNTIME_URL`、`PROMPT_RUNTIME_API_KEY`、`AI_PLATFORM_OPENAI_BASE_URL`、`AI_PLATFORM_API_KEY`、`DATABASE_URL`、`RABBITMQ_URL` 未配置，Docker 不可用。

## Next Actions

1. 提交并普通推送当前改造到 `origin/codex/per-flow-model-routing`。
2. 若后续提供真实 Runtime 环境，再运行一次 Prompt Runtime → ms-ai-platform → Provider 外部 E2E；不得把 Mock PASS 误写为真实 Provider PASS。
3. 如用户恢复推理强度需求，再单独设计并验证 `reasoning_effort` 透传；模型名继续保持 `gpt-5.6-sol`，不拼接 `-xhigh`。
