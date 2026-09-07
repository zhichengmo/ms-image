# Handoff Snapshot

## Current Objective

- Last updated: 2026-09-07，当前未提交改动的审查、修复和离线验证已完成，正在执行安全提交/推送门禁。
- Active objective: 在无剩余 actionable finding、无敏感信息、远端未前进且 staged 清单准确的前提下，将 Basic Auth X-Ray 前端工作流及相关连续性记录提交并普通推送到 `origin/codex/per-flow-model-routing`。
- Evidence level: SOURCE_REVIEW_PASS / BACKEND_FULL_SUITE_PASS / FRONTEND_BUILD_PASS / FRONTEND_LINT_PASS / STATIC_GATES_PASS；本轮真实 AI、OSS、Nacos、数据库和 Runtime NOT RUN。
- Active branch: detached HEAD at `5c2e1ec`；本地 `codex/per-flow-model-routing` 与远端基线同 SHA，但该分支正由另一个含未提交改动的工作树占用。当前工作树将保持 detached，在父提交精确一致的前提下创建提交，并以显式 `HEAD:codex/per-flow-model-routing` 普通推送；禁止修改、reset 或清理另一个工作树。
- Completed capabilities not reimplemented: Session/Study/Series/Image、Revision/finalize、Task/Outbox/Relay/Worker/Gateway、Quality、Diagnose、Localization、Report，以及既有 Prompt/Schema/模型路由。
- This run write set: 当前已审查的 Basic Auth 后端/测试/启动器、`apps/frontend/`、Postman collection/guide、相关 Prompt 快照、`.env.example`、`.gitignore`、开发合同与最小 handoff 状态文件；排除 `.env`、`.playwright-cli/`、`output/`、`node_modules/`、`dist/` 和运行证据缓存。
- External permissions: 仅普通 Git commit/push；不调用 Provider、Nacos、外部数据库、真实 OSS 或 Runtime，不向日志/文件写入 Basic 密码。
- Completion gate: 敏感信息扫描、精确暂存、`git diff --cached --check`、staged name/status/stat 复核已通过；剩余目标分支/远端最终核对、普通推送和远端 SHA 确认。
- Stop gate: 发现真实凭证/签名 URL、未解决缺陷、远端前进、非 fast-forward 或需要 force push 时立即停止；另一工作树占用本地分支已通过 detached HEAD + 显式非强制 refspec 隔离，不触碰其工作区。

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
- WARN: npm 11.5.2 对 Node 18.20.8 有支持范围警告；后端仍有现存 Pydantic Config 和 `datetime.utcnow()` 弃用警告，均未导致验证失败。
- NOT RUN: 本轮未再次调用真实 AI/OSS/Nacos/数据库/Runtime；沿用的真实工程证据仅是既有 Cat 双图 Basic Auth 全链与 AI Stage 重叠验证。

## Next Action And Boundaries

- Next action: 重新暂存本次 handoff 结果，最终核对远端后在 detached HEAD 创建功能提交，并以显式非强制 refspec 普通推送到 `codex/per-flow-model-routing`。
- Blockers: 当前无已知代码阻断。
- Open questions: 猫狗 2–5 图矩阵、医学 Gold/准确率、Localization 医学正确性和生产部署 CORS/HTTPS 仍未验证；继续 `MEDICAL_ACCURACY_UNKNOWN / MEDICAL_RELEASE_NO_GO`。
