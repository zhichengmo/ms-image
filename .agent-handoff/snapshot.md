# Handoff Snapshot

## Current Objective

- Last updated: 2026-09-07，Basic Auth X-Ray 前端工作流已完成审查、修复、离线验证、功能提交和普通推送。
- Active objective: 当前交付已完成，无必需代码动作；下一轮只在用户另行授权后扩展 Runtime、医学或 production 部署证据。
- Evidence level: SOURCE_REVIEW_PASS / BACKEND_FULL_SUITE_PASS / FRONTEND_BUILD_PASS / FRONTEND_LINT_PASS / STATIC_GATES_PASS / FUNCTIONAL_COMMIT_PUSHED；本轮真实 AI、OSS、Nacos、数据库和 Runtime NOT RUN。
- Delivery: 功能提交 `6521a1ed6b017548ad2e25aa8103e3f0d6bcdebf`（`feat(xray): add basic-auth frontend workflow`）已普通推送到 `origin/codex/per-flow-model-routing`，推送后远端 SHA 核对一致。
- Active branch: 当前工作树保持 detached HEAD；本地 `codex/per-flow-model-routing` 被 `/Users/mozhicheng/workspace/code/cy-code/ms-image` 的脏工作树占用且仍停在旧提交，禁止修改、reset、restore、暂存或合并该工作树内容。后续如继续从当前工作树交付，仍需使用显式非强制 refspec 并先 fetch 核对远端。
- Completed capabilities not reimplemented: Session/Study/Series/Image、Revision/finalize、Task/Outbox/Relay/Worker/Gateway、Quality、Diagnose、Localization、Report，以及既有 Prompt/Schema/模型路由。
- Delivered write set: Basic Auth 后端/测试/启动器、`apps/frontend/`、Postman collection/guide、相关 Prompt 快照、`.env.example`、`.gitignore`、开发合同与连续性记录；未提交 `.env`、`.playwright-cli/`、`output/`、`node_modules/`、`dist/` 或运行证据缓存。
- External permissions used: 仅普通 Git commit/push；未调用 Provider、Nacos、外部数据库、真实 OSS 或 Runtime，未向日志/文件写入 Basic 密码。
- Completion gate: 无剩余 actionable finding；敏感信息扫描、精确暂存、staged whitespace/name/status/stat、功能提交、普通推送和远端 SHA 核对均通过。
- Stop gate: 后续若发现真实凭证/签名 URL、远端前进、非 fast-forward、需 force push 或必须触碰另一脏工作树，立即停止并请求用户处理。

## Completed Review And Fixes

- Runtime 继续接受 Basic OR Bearer，Admin 继续 Bearer-only；Basic 未配置时 fail-closed 为 503，用户名/密码使用常量时间比较。
- Postman Runtime 入口已全部切换为 Basic Auth：48 个 Basic auth block、0 个 Bearer auth block；5 个 OSS signed URL PUT 保持 `noauth`，指南同步移除 Bearer-only 操作说明。
- `scripts/dev/run_e2e_local.py` 默认使用 Basic，进程环境优先、仓库 `.env` 仅作 fallback，且不打印凭证。
- `scripts/dev/run_local_chain.sh` 以同样优先级加载并导出 Basic username/password/subject/scopes；缺少用户名或密码时 fail-closed；Worker 默认 concurrency=2。
- 前端 Basic 凭证只存在 React 内存，不写 localStorage；OSS PUT 不附带 Runtime Authorization。
- Diagnose Task 创建后创建关联 Localization Task；创建存在必要的 `source_task_id` 因果顺序，但进入 Worker 后由两个 slot 独立运行。Quality、Diagnose、Localization 使用独立轮询目标，报告和 Localization 页面读取真实后端结果。
- 根 `.gitignore` 已排除 `.playwright-cli/` 与 `output/`，同时保证 `apps/frontend/src/lib/*.ts` 可被 Git 收录。

## Validation

- PASS: Basic Auth 定向测试 `7 passed`。
- PASS: 后端完整测试 `413 passed, 48 warnings`。
- PASS: Ruff、Python `compileall`、`bash -n scripts/dev/run_local_chain.sh`、`git diff --check`。
- PASS: E2E Basic 凭证 `.env` fallback 和 process-env override。
- PASS: Postman JSON 解析及认证统计（48 Basic / 0 Bearer / 5 noauth），collection/guide 无 `runtime_token` 或 Bearer 操作入口。
- PASS: 前端 `npm run lint`、`npm run build`；Vite 39 modules transformed。
- PASS: handoff maintenance `changed=2 warnings=1 unresolved=0`；仅轮转旧 work-log。
- PASS: 80 个 staged blob 敏感信息扫描；`.env`、`.playwright-cli/`、`output/`、`node_modules/`、`dist/` 未进入提交。
- PASS: 首次 staged check 发现并修复 6 个新前端文件 EOF 多余空行，最终 `git diff --cached --check` 通过。
- PASS: 功能提交 `6521a1e` 已创建并普通推送；`HEAD` 与 `origin/codex/per-flow-model-routing` 均为 `6521a1ed6b017548ad2e25aa8103e3f0d6bcdebf`。
- WARN: npm 11.5.2 对 Node 18.20.8 有支持范围警告；后端仍有现存 Pydantic Config 和 `datetime.utcnow()` 弃用警告，均未导致验证失败。
- NOT RUN: 本轮未再次调用真实 AI/OSS/Nacos/数据库/Runtime；沿用的真实工程证据仅是既有 Cat 双图 Basic Auth 全链与 AI Stage 重叠验证。

## Next Action And Boundaries

- Next action: 无必需代码动作；按用户授权可分别补猫狗 2–5 图工程矩阵、真实续传故障注入、医学 Gold/Scorer/Holdout 或 production CORS/HTTPS。
- Blockers: 当前无已知代码阻断。
- Open questions: 猫狗 2–5 图矩阵、医学 Gold/准确率、Localization 医学正确性和生产部署 CORS/HTTPS 仍未验证；继续 `MEDICAL_ACCURACY_UNKNOWN / MEDICAL_RELEASE_NO_GO`。
