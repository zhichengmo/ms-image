# Handoff Snapshot

## Current Objective

- Last updated: 2026-09-03
- Active objective: 将当前已验证的 X-Ray Runtime、宠物档案和配套资产按边界提交并推送到 `codex/xray-anatomy-localization-v1`，随后创建 `codex/per-flow-model-routing` 处理按接口/流程节点选择模型及推理强度。
- Evidence level: `LOCAL_VALIDATED / GIT_DELIVERY_IN_PROGRESS`; 不代表医学准确率或生产发布资格。
- Write set: 现有功能代码已形成两个提交；当前仅整理既有 `AGENTS.md`、`AGENT_HANDOFF.md`、`AGENT_SESSION_PROMPTS.md`、`docs/` 与 `.agent-handoff/` 历史文件，不新增业务实现。
- External permissions: 用户已明确授权 Git commit/push；未调用 Provider，未写 Nacos、数据库、OSS 或 Broker。
- Completion gate: 当前分支所有有用内容逐路径提交并成功推送；新分支创建、设置 upstream；最终工作树干净。
- Stop gate: 凭据泄露、合并冲突、非快进、认证失败、未知重叠改动或意外文件进入暂存区时立即停止；禁止 force push、reset、clean、restore 与 `git add -A`。

## Git Delivery Status

- Source branch: `codex/xray-anatomy-localization-v1`
- Functional commit: `ee2fa3a feat: complete xray runtime and pet profile workflows`
- Full-chain harness follow-up: `2b7d66b fix(dev): validate species-specific full-chain configs`
- Documentation/handoff commit: pending
- Source branch push: pending
- Target branch: `codex/per-flow-model-routing` (pending creation)

## Validation Baseline

- `PYTHONPATH=. /opt/homebrew/anaconda3/bin/pytest apps/backend/tests -q` → `379 passed, 48 warnings`。
- Python compile/changed-file `py_compile`、Prompt JSON、Postman JSON、migration AST/结构、模块导入、secret scan、handoff archive references 与 `git diff --check` 均通过。
- 两次环境型 pytest 失败已定位：Homebrew Python 3.13 未安装 pytest；Anaconda pytest 首次缺少 `PYTHONPATH=.` 导致 `ModuleNotFoundError: apps`。设置 `PYTHONPATH=.` 后全量通过。

## Preserved Qualification

```text
TARGETED_REVIEW_RUNTIME_PASS
REPORT_GENERATION_AI_RUNTIME_PASS
SAME_TASK_FULL_CHAIN_RUNTIME_PASS
MEDICAL_ACCURACY_UNKNOWN
MEDICAL_RELEASE_NO_GO
```

- 已完成能力不会因 Git 收口而重新运行：X-Ray 八阶段主链、TargetedReview、ReportGeneration、宠物档案 Model/Schema/DAL/Service/API 与既有 Prompt/Config 资产均按现状保存。
- `.agent-handoff/archive.md` 当前引用的 216 个 archive path 均存在；对应 108 个本次新增 archive 文件必须与索引一起提交，避免历史断链。

## Next Branch Objective

- 在 `codex/per-flow-model-routing` 上先审计并设计 `ms-image` 的“业务接口/Stage → AiModelRoute”入口，复用现有 AI Control、冻结 Config、`AIRequestService` 与 Gateway，不创建第二套 Provider owner。
- 目标模型应表达为 `model="gpt-5.6-sol"` 与独立的 `reasoning_effort="xhigh"`，不能把 `gpt-5.6-sol-xhigh` 当模型名。
- 需同时核对 `/Users/mozhicheng/workspace/code/cy-code/ms-ai-fast` 的代码级路由实现，以及 `/Users/mozhicheng/workspace/code/python_project/ms-ai-platform` 对请求模型、`reasoning_effort` 和 Endpoint 选择的透传/覆盖行为；在用户进一步授权前不修改其他仓库。
