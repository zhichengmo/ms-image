# Handoff Snapshot

## Current Objective

- Last updated: 2026-09-03
- Active branch: `codex/per-flow-model-routing`
- Active objective: 为 `ms-image` 建立按业务接口/流程 Stage 配置模型与推理强度的清晰入口；先完成调用链、冻结 Config 与跨仓库透传边界审计，再决定最小实施写集。
- Evidence level: `GIT_DELIVERED / ROUTING_AUDIT_READY`; 尚未实施或 Runtime 验证新的模型路由。
- Write set: 当前 Git 收口已完成；下一轮在读清目标源码前不预设业务写集，也不修改 `ms-ai-fast` 或 `ms-ai-platform`。
- External permissions: 当前仅 Git commit/push 已获授权并完成；未获 Provider、Nacos、数据库、OSS、Broker 或其他仓库写权限。
- Completion gate for next objective: 明确每个接口/Stage 的 route owner、`model`/`reasoning_effort` 冻结与传递位置、Platform Endpoint 选择语义、兼容策略和精确文件写集；用户确认范围后再实施。
- Stop gate: 发现调用方模型被 Platform 无条件覆盖、Schema 丢弃 `reasoning_effort`、SDK 不支持 `xhigh`、需要跨仓库写入或会产生第二套 Gateway/Provider owner 时，先报告冲突，不直接绕过。

## Git Delivery Status

- Source branch: `codex/xray-anatomy-localization-v1` → `origin/codex/xray-anatomy-localization-v1`
- Target branch: `codex/per-flow-model-routing` → `origin/codex/per-flow-model-routing`；基线为 `adbd2b1`，仅增加本次分支交接状态
- Functional commit: `ee2fa3a feat: complete xray runtime and pet profile workflows`
- Full-chain harness commit: `2b7d66b fix(dev): validate species-specific full-chain configs`
- Documentation/handoff commit: `adbd2b1 docs(handoff): preserve xray qualification history`
- 模型路由业务实现尚未开始；新分支只比源分支增加本次交接状态。

## Validation Baseline

- `PYTHONPATH=. /opt/homebrew/anaconda3/bin/pytest apps/backend/tests -q` → `379 passed, 48 warnings`。
- Python compile/changed-file `py_compile`、Prompt JSON、Postman JSON、migration AST/结构、模块导入、secret scan、handoff archive references 与 patch checks 均通过。
- 218 个 handoff archive 引用、218 个文件、0 missing；最终 maintenance 无 unresolved，轮转文件已纳入交接提交。
- 两个分支均成功执行普通 `git push -u`，未使用 force push；新分支工作树在交接更新前为干净状态。

## Preserved Qualification

```text
TARGETED_REVIEW_RUNTIME_PASS
REPORT_GENERATION_AI_RUNTIME_PASS
SAME_TASK_FULL_CHAIN_RUNTIME_PASS
MEDICAL_ACCURACY_UNKNOWN
MEDICAL_RELEASE_NO_GO
```

- 不因模型路由任务重跑或重写已完成能力：X-Ray 八阶段主链、TargetedReview、ReportGeneration、宠物档案链路、Prompt/Schema/Config 资产继续按冻结事实处理。
- 新实现必须复用现有 AI Control、冻结 Config、`AIRequestService`、Gateway/Worker；API/Stage 不得直接调用 Provider。

## Next Actions

1. 从 `ms-image` endpoint/Stage 开始追踪到 `AIRequestService`、冻结 Config、Gateway request 的完整参数链，定位最合适的 `AiModelRoute` 等价入口。
2. 对照 `/Users/mozhicheng/workspace/code/cy-code/ms-ai-fast` 中 `ai_model_route.py`、各 Flow Service 与 `ai_runtime_service.py` 的代码级映射模式，只借鉴语义，不复制第二套服务。
3. 只读核对 `/Users/mozhicheng/workspace/code/python_project/ms-ai-platform` 的入口 Schema、`ai_proxy_service.py`、Endpoint Config 与 OpenAI SDK 版本，确认 `reasoning_effort="xhigh"` 是否会被丢弃或拒绝。
4. 目标参数保持分离：`model="gpt-5.6-sol"`，`reasoning_effort="xhigh"`；禁止使用伪模型名 `gpt-5.6-sol-xhigh`。
