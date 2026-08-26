# 验证历史

## 记录规则

- 只保留当前阶段和下一阶段仍有决策价值的验证；早期完整历史见归档。
- 代码、运行时和医学验证分别报告；Mock、静态检查和单次模型请求不能代替完整 Worker 或医学放行。

| Date | Scope | Command / Evidence | Result | Notes |
|---|---|---|---|---|
| 2026-08-25 | P0-A Prompt command 业务修正 | 现有合同测试及静态检查 | PASS | 已完成 Prompt command 业务合同；不代表完整 Worker Runtime。 |
| 2026-08-26 | OSS 隔离 synthetic probe | PUT / HEAD / Worker GET / same-host signed GET / cleanup | PASS (isolated only) | Provider 外网可访问性仍为 `UNKNOWN`。 |
| 2026-08-26 | 核心 AI 网络 smoke | Nacos Prompt -> Renderer -> Message Assembler -> GatewayClient -> ms-ai-platform -> strict JSON Schema + Provider Request ID | PASS | 唯一已通过的真实网络事实：`MS_IMAGE_CORE_AI_NETWORK_CHAIN_PASSED`；非医疗 Prompt，不能作为 XRay 医学依据。 |
| 2026-08-26 | 已提交 XRay/Prompt 代码 | `git status --short --branch`; `git show --check HEAD`; `git diff --check`; `git push origin HEAD` | PASS | `325dd8e42d596e0b28a22ece3806da001ec4f2a6` 已同步至 `origin/codex/prompt-runtime-ai-gateway`；push 返回 `Everything up-to-date`。 |
| 2026-08-26 | Offline AI/runtime contract tests | `python -m pytest apps/backend/tests/test_ai_prompt_control_plane_contracts.py apps/backend/tests/test_ai_gateway_attempt_contracts.py apps/backend/tests/test_ai_prompt_control_plane_models.py -q` | PASS | `81 passed, 19 warnings`；warning 为已有 Pydantic/datetime deprecation。 |
| 2026-08-26 | AI/control/runtime/worker syntax | `python -m compileall -q apps/backend/core/ai apps/backend/services/ai_control apps/backend/services/runtime apps/backend/workers/imaging_worker` | PASS | `COMPILE_OK`。 |
| 2026-08-26 | 已移除 Gateway 运行链扫描 | production-source `rg` 查找 resolver/adapter/response-store identifiers | PASS | 无 `EnvironmentReferenceSecretResolver`、`OpenAICompatibleGatewayAdapter`、`OSSEncryptedResponseStore`、`GatewayRuntimeDependencies`、`AI_GATEWAY_*`、`MS_IMAGE_AI_SECRET_*` 或 `env-secret://` 生产引用。 |
| 2026-08-26 | P0 primary database baseline | Read-only PyMySQL `information_schema` audit using configured primary connection | PASS / BLOCKER FOUND | `ms_image` 为 45 表、无 `alembic_version`；有数据的同名旧表与当前 Runtime create-table migrations 冲突；未执行 DB mutation。 |
| 2026-08-26 | Runtime / medical environment | MySQL migration, Outbox, Broker, Worker, provider external signed GET, full Task chain, medical evaluation | NOT RUN | `RUNTIME_QUALIFIED: NOT RUN`；`MEDICALLY_VALIDATED: UNKNOWN`。 |
| 2026-08-26 | v2 Task Admission contract | `ruff`; three existing AI contract test modules; compileall; diff checks | PASS | `86 passed, 19 warnings`; commit `6057ec9` only changes Task Admission validation and existing tests. |
| 2026-08-26 | Git publication | explicit `git add` of two business files; `git commit`; `git push origin HEAD` | PASS | `6057ec950cf329e34a3da308f07a928f7dabb086` is on `origin/codex/prompt-runtime-ai-gateway`. |
| 2026-08-26 | Local Worker Platform configuration presence | non-sensitive parse of `.env` / `.env-01` plus `Settings()` booleans | BLOCKER FOUND | Both files lack nonempty `AI_PLATFORM_OPENAI_BASE_URL` / `AI_PLATFORM_API_KEY`; `settings.ai_platform_configured=False`. OSS ready / Broker enabled does not qualify Platform or full Worker runtime. |
