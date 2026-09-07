# 验证历史

## 记录规则

- 主文件只保留当前资格状态和最近仍有决策价值的证据。
- 截至 2026-09-03 Gemini 收口前的完整验证历史已原样归档至 `archive/validation-20260903T225200-full-history.md`；更早历史见 `archive.md`。
- 工程通过、Provider 医学输出和医学准确率分开报告；文件名、目录名、单病例模型结果不得当作 Gold。

## 2026-09-07 — Basic Auth 前端工作流提交与推送

| 检查 | 结果 | 说明 |
|---|---|---|
| Basic Auth 定向测试 | PASS | `7 passed`；覆盖 Runtime Basic 成功/失败、未配置 fail-closed 与 OpenAPI Basic OR Bearer 合同。 |
| 后端完整测试 | PASS | `413 passed, 48 warnings`；警告为现存 Pydantic Config 与 `datetime.utcnow()` 弃用项。 |
| Ruff / compileall | PASS | 后端 lint 与 Python 编译检查无错误。 |
| launcher shell syntax | PASS | `bash -n scripts/dev/run_local_chain.sh`。 |
| E2E Basic 凭证优先级 | PASS | 仓库 `.env` fallback 与 process-env override 均通过，输出不包含密码。 |
| Postman 认证合同 | PASS | JSON 可解析；48 Basic、0 Bearer、5 noauth；collection/guide 无 `runtime_token` 或 Bearer 操作入口。 |
| 前端 lint / build | PASS | `npm run lint`、`npm run build`；Vite 39 modules transformed。 |
| 全仓 diff | PASS | `git diff --check` 无 whitespace error。 |
| 精确暂存清单 | PASS | 80 个候选文件均由显式路径暂存；`.env`、`.playwright-cli/`、`output/`、`node_modules/`、`dist/` 未进入 index，工作区无剩余 untracked 候选。 |
| staged whitespace | PASS | 首次发现 6 个新前端文件 EOF 多余空行并已修正；随后 `git diff --cached --check` 通过。 |
| 敏感信息扫描 | PASS | 扫描全部 80 个 staged blob；`.env` 未暂存，示例凭证为空或惯用占位，Postman 凭证为变量引用，未发现私钥、真实 Token、API Key、签名 URL 或硬编码 Authorization。 |
| handoff maintenance | PASS WITH ROTATION | `changed=2 warnings=1 unresolved=0`；仅轮转 1 段旧 work-log 并更新 archive 索引。 |
| 提交前远端基线 | PASS | fetch 后父提交、目标本地分支与远端均为 `5c2e1ec`；远端未前进。 |
| 本地分支占用核对 | PASS WITH ISOLATION | 分支由 `/Users/mozhicheng/workspace/code/cy-code/ms-image` 占用且该工作树有未提交改动；不触碰其文件或 index，改用同父提交 detached commit + 显式非强制远端 refspec。 |
| 功能提交 | PASS | `6521a1ed6b017548ad2e25aa8103e3f0d6bcdebf feat(xray): add basic-auth frontend workflow`。 |
| 普通推送与远端 SHA | PASS | `git push origin HEAD:refs/heads/codex/per-flow-model-routing` 成功；fetch 后 `HEAD` 与远端跟踪分支均为 `6521a1ed6b017548ad2e25aa8103e3f0d6bcdebf`，未使用 force push。 |
| 真实外部全链重跑 | NOT RUN | 本轮未调用 AI、OSS、Nacos、数据库或 Runtime；不得将离线门升级为新的真实病例证据。 |
| 医学发布资格 | NO-GO | 既有 Cat 双图工程证据不覆盖猫狗 2–5 图矩阵、医学 Gold/准确率或 Localization 医学正确性。 |

## 2026-09-07 — 前端交付与故障恢复优化

| 检查 | 结果 | 说明 |
|---|---|---|
| 前端 production build | PASS | `cd apps/frontend && npm run build`；Vite 6 完成，39 modules transformed。 |
| 前端 lint | PASS | `cd apps/frontend && npm run lint`；ESLint 无错误。 |
| 全仓 whitespace/diff | PASS | `git diff --check` 无错误。 |
| `src/lib` Git 收录 | PASS | `git add -n apps/frontend/src/lib/api.ts apps/frontend/src/lib/fileMetadata.ts` 显示两个文件均会被添加；未实际暂存。 |
| 后端幂等合同只读核对 | PASS | Session/Study/Series 与 prepare-upload 现有 Service 合同支持同资源重放；不需要后端改造。 |
| 轮询瞬断恢复源码核对 | PASS | 三类 Task 查询失败后有界退避继续轮询，恢复时只清除对应 Task 错误，手动重试可重启 effect。 |
| 上传续传源码核对 | PASS | 固定 `started_at`、复用资源、远端状态对账、ready 后最新 revision finalize 均已实现。 |
| 真实网络/OSS 故障注入 | NOT RUN | 本轮无外部写权限，不声明真实中断恢复 Runtime PASS。 |
| 真实 AI/医学验证 | NOT RUN | 没有新增 Provider 调用；既有 R4 工程证据保持，医学准确率仍 UNKNOWN / NO-GO。 |
| Node/npm 环境 | WARN | Node 18.20.8 + npm 11.5.2 有 npm 官方支持范围警告，但未影响 build/lint。 |

## Current Qualification

```text
GEMINI_CODE_ROUTE_PASS
CAT_FRESH_3_8_PRIMARY_FINAL_RUNTIME_PASS
DOG_FRESH_3_8_PRIMARY_FINAL_RUNTIME_PASS
UNIQUE_FINAL_REPORT_QUERY_PASS
TARGETED_REVIEW_3_8_RUNTIME_NOT_EXERCISED
MEDICAL_ACCURACY_UNKNOWN
MEDICAL_RELEASE_NO_GO
```

## 2026-09-04 — 10 例准确率 Pilot 首例停止

| 检查 | 结果 | 说明 |
|---|---|---|
| 数据集结构审计 | PASS | 43,931 JPEG 与 43,931 JSON 唯一配对；ABN=2,717、NOR=41,214；JPEG SHA 重复组 0。 |
| 医学 Gold 门 | NOT AVAILABLE | `metadata.Disease` 与文件名标签完全重复，annotations 无 finding/病种 Gold；只能做操作标签一致性 Pilot。 |
| 病例分组门 | LIMITED | 候选宠物键 18,690 组中 925 组混合 ABN/NOR；不可直接上卷为病例单一临床标签。 |
| 随机样本冻结 | PASS | seed=20260904；5 ABN+5 NOR；覆盖猫狗、腹部/胸腔/肌骨、2–5 图；失败后不替补。 |
| Case 1 Quality | PASS | Task `f7d7510b...` completed；Cat Prompt `1.1.3`；3.8；1 Call/1 Attempt；Provider 200。 |
| Case 1 Screening/System | PASS | 两 Stage 均 Cat exact Prompt、3.8、单 Attempt、Provider 200/accepted。 |
| Case 1 Primary | FAIL-CLOSED | Task `f4efda18...`；Provider 200 后 `provider_result_source_projection_mismatch`；Prompt `xray_cat_primary_adjudication@1.0.1`；Report 0。 |
| Batch stop gate | PASS | 仅执行 1/10；其余 9 例未运行，无替补、重试、Prompt/Schema/validator 修改。 |
| 准确率 | NOT COMPUTED | 首例在最终医学结果前发生工程 lineage 失败，不能写成 0%/100% 或排除后继续算。 |
| Runtime cleanup | PASS WITH KNOWN WARNING | 8010、Runtime/Relay/Worker/lock 无残留；既有 aiomysql event-loop-close warning 仍出现。 |

## 2026-09-04 — Gemini 3.8 Flash 猫狗真实完整主链

| 检查 | 结果 | 说明 |
|---|---|---|
| 7 个 X-Ray Stage 路由 | PASS | ImageQuality、Screening、System、Primary、Targeted、Report、Localization 源码均声明 `gemini-3.8-flash/race`。 |
| 切换后静态门 | PASS | `15 passed, 305 deselected`；Ruff、`py_compile`、`git diff --check` PASS。 |
| 真实输入门 | PASS | Cat 2 图、Dog 3 图均来自指定数据根；path/size/SHA-256 与 manifest 全部一致。 |
| Cat fresh full chain | PASS | Quality `10e0f9ed...`、Diagnose `7d53e0d6...` completed；Report `1642f558...` final；task/current/history 一致。 |
| Cat Prompt/模型/Attempt | PASS | Quality + 4 个诊断 AI Call 均动态读取 cat exact Prompt、requested/actual=3.8、每 Call 1 Attempt、无 reconcile。 |
| Dog fresh full chain | PASS | Quality `38920614...`、Diagnose `b6f130ee...` completed；Report `6d1c99c1...` final；task/current/history 一致。 |
| Dog Prompt/模型/Attempt | PASS | Quality + 4 个诊断 AI Call 均动态读取 dog exact Prompt、requested/actual=3.8、每 Call 1 Attempt、无 reconcile。 |
| ReportGeneration truth gate | PASS | Cat Prompt `1.0.2`、Dog Prompt `1.0.4`；0 图调用；source SHA/status/Schema 与冻结医学对象深度相等均通过。 |
| 条件拓扑 | PASS WITH COVERAGE LIMIT | 两例均为合法 `primary_final`，各 Diagnose 7 Stage/4 Call/4 Attempt；TargetedReview 未触发，3.8 条件分支 Runtime 仍未覆盖。 |
| 运行清理 | PASS WITH KNOWN WARNING | 8010、Runtime/Relay/Worker/lock 无残留；既有 aiomysql event-loop-close warning 仍出现。 |
| 医学结论 | UNKNOWN / NO-GO | 本轮是工程链验证，没有 Gold/Scorer/Holdout。 |

## 2026-09-04 — Dog ReportGeneration 1.0.4 字段差异诊断

| 检查 | 结果 | 说明 |
|---|---|---|
| 历史失败输入回读 | PASS | Task `e4b3d9ab...` 的 DecisionFinalization 与 ReportGeneration 冻结输入完整可读；旧失败正文未持久化。 |
| 动态 Prompt | PASS | namespace `c0cc9e0e-0fed-4faf-bc57-e9bab46a78a9`、source key `ms-image.x-ray.report-generation.dog.zh-CN`、version `1.0.4`、variant `dog`、fallback=false。 |
| 唯一 Provider 请求 | PASS | request `chatcmpl-1788487790`；requested/actual model=`gemini-3.5-flash`；只执行一次，无 retry。 |
| JSON Schema | PASS | 响应为 `xray-final-report.v1`，顶层 source SHA 与 medical status 正确。 |
| 冻结医学对象深度相等 | FAIL-CLOSED | 仅 `coverage.missing_or_limited_views[0]` 不同：“对位和稳定性”被改成“对位 and 稳定性”。 |
| 根因边界 | CONFIRMED | Prompt/Schema/JSON parse 均成功；失败属于生成模型不能确定性执行复杂对象逐字符复制。 |
| 代码与外部状态写入 | NONE | 未修改业务代码、Prompt、Schema、validator、Nacos 或数据库。 |
| Runtime cleanup | PASS WITH KNOWN WARNING | launcher 温关闭；8010、Runtime/Relay/Worker/lock 无残留；临时目录移入废纸篓；既有 aiomysql event-loop warning 仍存在。 |

## 2026-09-04 — Gemini 3.7 Flash 单次对照

| 检查 | 结果 | 说明 |
|---|---|---|
| Platform 模型目录预检 | UNAVAILABLE | `GET /api/v1/models` 返回 404；平台不提供该查询接口，不代表模型不可用。 |
| 动态 Prompt | PASS | Dog ReportGeneration `1.0.4`、指定 namespace、variant=`dog`、fallback=false。 |
| 唯一 3.7 请求 | PASS | Provider request `chatcmpl-1788488881`；requested/actual model 均为 `gemini-3.7-flash`；无 retry/fallback。 |
| Schema 与顶层门禁 | PASS | `xray-final-report.v1`、source SHA 和 medical status 全部正确。 |
| 冻结医学对象深度相等 | PASS | 递归差异数 0；本次没有复现 3.5 的“和”→`and` 改写。 |
| 稳定性结论 | UNKNOWN | 仅同一病例单次调用，不能证明后续调用均能精确复制。 |
| 业务路由写入 | NONE | 未修改 Stage `MODEL_ROUTE`、Prompt、Schema、validator、Nacos 或数据库。 |

## 2026-09-03 — code-owned AI/Prompt 路由基线

| 检查 | 结果 | 说明 |
|---|---|---|
| Prompt 路径 | PASS | direct Nacos Client latest、StrictUndefined/tojson/$变量、species exact-only。 |
| AI 路径 | PASS | 复用 AIRequestService/Gateway/Worker 与 AI Platform Chat Completions；strict json_schema；HTTP 失败不自动 retry。 |
| 历史全量测试 | PASS | Gemini 切换前 code-owned 基线曾为 `381 passed, 48 warnings`。 |
| 历史慢模型风险 | CLOSED FOR CURRENT GEMINI ROUTE | `gpt-5.6-sol` 曾在约 60 秒边界累计 3 次 Platform 500；当前 Gemini 验证未复现。 |

## 2026-09-03 — Gemini 3.5 Flash 猫狗完整主链资格

| 检查 | 结果 | 说明 |
|---|---|---|
| 诊断 Stage 模型路由 | PASS | 6 个诊断 AI Stage 均为 `gemini-3.5-flash/race`；Anatomy Localization 仍为 `gpt-5.6-sol/race`。 |
| 定向路由合同 | PASS | `15 passed, 305 deselected`；同时断言 6 个诊断 Stage 与 Localization 的不同模型边界。 |
| Prompt 本地验证 | PASS | Cat/Dog ReportGeneration `1.0.2` 的 Jinja required variables 精确为 `FINAL_MEDICAL_RESULT_JSON/QUALITY_RESULTS_JSON/REPORT_SCHEMA_JSON`，Strict render 成功。 |
| Nacos immutable preflight | PASS | 指定 namespace 中 Cat/Dog `1.0.2` 均不存在；旧 `1.0.0/1.0.1` online。 |
| Nacos 发布与 exact readback | PASS | Cat/Dog `1.0.2` 经 `draft → submit` 自动 online；latest template 与本地逐字一致，SHA 分别 `dacc47d9...757a3`、`42b051b0...55d9e`；未 force publish。 |
| 首次 Gemini Cat | FAIL-CLOSED / PROMPT ATTRIBUTED | Task `780b6d97...`：Quality、Screening、System、Primary、Targeted 均 HTTP 200/accepted；ReportGeneration HTTP 200 后因 `report_generation_medical_result_rewritten` failed，Report 0。Nacos `1.0.1` 缺少完整对象深拷贝指令。 |
| Fresh Cat full chain | PASS | Quality `20fceba6...`、Diagnose `00deb1ff...` completed；8 Stage、5 Call、5 Attempt；Targeted 触发；Report `081e9443...` final；task/current/history 一致。 |
| Cat Prompt/model receipts | PASS | ReportGeneration 动态读取 `1.0.2`；Quality + 5 个诊断 AI Call 均单 Attempt，requested/actual model=`gemini-3.5-flash`。 |
| Dog projection evidence | PASS | `dog-03` 三张图片 SHA 在已完成 Quality Task `d52f24a2...` 中均为 caller-declared `ventrodorsal`；未使用 UNKNOWN、文件名或像素猜测。 |
| Fresh Dog full chain | PASS | Quality `a1369670...`、Diagnose `7ec955a6...` completed；FamilyRouting=`primary_final`，7 Stage、4 Call、4 Attempt；Report `646cd3e6...` final；task/current/history 一致。 |
| Dog Prompt/model receipts | PASS | ReportGeneration 动态读取 `1.0.2`；Quality + 4 个诊断 AI Call 均单 Attempt，requested/actual model=`gemini-3.5-flash`；TargetedReview 合法未物化。 |
| Conditional topology harness | PASS | 修复固定 8 Stage/5 Call 假设后，对既有 Dog Task 做只读 receipt helper 复验通过；未新增 Provider 调用。 |
| Backend full suite | PASS | `PYTHONPATH=. python3.12 -m pytest -q apps/backend/tests` → `403 passed, 48 warnings`。 |
| Static checks | PASS | 目标 Ruff、Python py_compile、`git diff --check` 均通过。 |
| Runtime cleanup | PASS WITH KNOWN WARNING | launcher 温关闭；8010、Runtime/Relay/Worker/lock 无残留；aiomysql event-loop-close warning 仍存在。 |
| Final handoff closeout | PASS | 修正根交接入口的过期 E2E 阻断文字；本轮临时 E2E 目录已移入废纸篓；maintenance `changed=0 warnings=0 unresolved=0`，8010、Runtime/Relay/Worker 与 launcher lock 均无残留。 |
| 医学准确率 | NOT EVALUATED / NO-GO | 本轮只证明工程执行、Prompt/model/receipt/Report 血缘；没有 Gold、Scorer、Failure Bank 或 Holdout。 |

## 2026-09-04 — Anatomy Localization 独立展示接口

| 检查 | 结果 | 说明 |
|---|---|---|
| 路由注册 | PASS | `GET /anatomy-localizations`、`POST /anatomy-localizations/prepare-view`、`GET /anatomy-localizations/legend` 均注册。 |
| 冻结影像读取边界 | PASS (FAKE/STATIC) | DB 查询位于短事务内；OSS 签名发生在事务结束后；逆序选择仍按冻结 manifest 顺序返回；非冻结或漂移图片 fail-closed。 |
| URL 安全与版本绑定 | PASS (FAKE/STATIC) | TTL 限制 1–900 秒，只接受无 userinfo 的 HTTPS URL；`object_version_id` 映射 OSS `versionId`，旧无版本调用形态保持兼容；URL 不进入 repr/数据库/Task snapshot。 |
| 图例合同 | PASS | 动态标签事实源完整覆盖 6 个系统、38 个标签，当前仅接受 `xray-anatomy-labels.v1` 与 `zh-CN`。 |
| 目标静态检查 | PASS | 5 个展示侧文件 `ruff check`、`compileall`、`git diff --check` 全部通过。 |
| Localization 定向合同测试 | PASS | `PYTHONPATH=. pytest -q apps/backend/tests/test_ai_gateway_attempt_contracts.py -k 'anatomy_localization'` → `69 passed, 251 deselected, 5 warnings`。 |
| 真实外部验证 | NOT RUN | 未连接真实数据库/OSS，未启动 Runtime，未调用 Provider 或 Nacos。 |

## 2026-09-04 — Gemini 3.8 frozen-10 qualification attempt

| 检查 | 结果 | 证据 |
|---|---|---|
| Runtime readiness/topology | PASS | owner 75826；DB/Redis/Broker ready；consumer=1；queue=0 |
| 操作错误批次 | NOT SCORED | `...T041908Z`；错误 API base 导致 POST /sessions 404，未进入链路 |
| Case 1 full chain | PASS / REVIEW_REQUIRED | Task `35da3f7...` completed；Report `bc5f9cc...` final；全部模型 3.8、单 Attempt；evidence SHA `3061ec500f6e5e2d70f93ad304848d1b3f39c5d8d5a6b38a5c765d14b6ec2ce3` |
| Case 2 Quality | FAIL-CLOSED | Task `9ac1ec8...`；Call `56d53d5...`；`xray_image_quality_image_1_projection_consistency_invalid`；Provider response SHA present |
| Case 3–10 | NOT RUN | 首错停止合同 |
| 医学准确率 | NOT COMPUTED | 完整固定 10 例未完成；`MEDICAL_RELEASE_NO_GO` |


## 2026-09-04 — Prompt/展示代码提交复验

| 检查 | 结果 | 说明 |
|---|---|---|
| `pytest -k anatomy_localization` | PASS | `69 passed, 251 deselected, 5 warnings`。 |
| Prompt/AI 路由定向 pytest | PASS | `36 passed, 358 deselected, 1 warning`。 |
| 两份 AI 合同测试全量 | PASS | `394 passed, 48 warnings`。 |
| 19 个业务/测试文件 Ruff + compileall + diff-check | PASS | 提交 `4aa46f1`。 |
| E2E Python Ruff/py_compile/`--help` | PASS | 参数解析无外部 I/O。 |
| E2E shell `bash -n` + diff-check | PASS | 提交 `df1a11e`。 |
| 真实 DB/OSS/Runtime/Nacos/Provider | NOT RUN | 本轮无授权且静态提交不需要。 |
| 主链到 Localization 直接关联 | SUPERSEDED | 后续已获用户授权并由提交 `5c2e1ec` 完成，见下节。 |

## 2026-09-04 — 主链关联与真实数据复验

| 检查 | 结果 | 说明 |
|---|---|---|
| 展示链/Prompt 失败定向测试 | PASS | `72 passed`。 |
| `test_ai_gateway_attempt_contracts.py` | PASS | `323 passed, 48 warnings`。 |
| 后端全量测试 | PASS | `406 passed, 48 warnings`。 |
| Ruff / compileall / `git diff --check` | PASS | 最新源码无静态、编译或空白错误。 |
| Alembic head/current | PASS | 均为 `20260904_01 (head)`。 |
| `GET /tasks?id=<diagnose_task_id>` | PASS | HTTP 200；返回 Localization 关联摘要。 |
| Localization current/history/legend | PASS | 真实数据只读 HTTP 200；diagnose `a042104cf0d84a4a8bede2bbac4a7036` 精确关联 Localization `9107bd3b102f493996a14b7d7d715f30`。 |
| `GET /api/v1/tasks/page` | FAIL / INDEPENDENT | 无参数及常用筛选返回 422；Localization `history` 分页接口正常，不属于本提交回归。 |
| 新 Localization bbox Provider 生成 | BLOCKED / NOT RUN | Nacos `1.0.0` Prompt 缺少 Output Schema；无 Nacos 写授权，未创建新版本、未调用 Provider。 |
| Runtime shutdown | PASS | 本轮 Launcher/Runtime/Relay/Worker 正常停止，`127.0.0.1:8010` 已释放。 |
| Git 提交 | PASS | `5c2e1ec feat(xray): link anatomy display to diagnosis`，精确 10 个文件。 |

## 2026-09-04 — X-Ray 前端宿主探索

| 检查 | 结果 | 说明 |
|---|---|---|
| 强制启动文档 | PASS | 已读取 handoff 启动集、开发合同、前端指南和完整 52 请求 Postman Collection。 |
| 前端工程标记搜索 | NOT FOUND | 无 `package.json`、Node 锁文件、Vite/Next/Vue/Svelte/TypeScript 配置。 |
| 前端源码搜索 | NOT FOUND | 无 TSX/JSX/Vue/Svelte/HTML/CSS/SCSS/Less 页面或组件源码。 |
| 宿主事实抽查 | PASS | `apps/backend/services/runtime/main.py` 为 FastAPI Runtime/Admin 入口；`apps/backend/requirements.txt` 为 Python 后端依赖。 |
| 前端实现/构建 | NOT RUN | 用户要求无既有宿主时先确认选型，因此未创建框架、未落页面代码。 |
| 外部系统 | NOT RUN | 未启动 Runtime/Docker，未调用 Provider，未写 Nacos/数据库/OSS。 |

## 2026-09-04 — X-Ray 前端与 Basic Auth

| 检查 | 结果 | 说明 |
|---|---|---|
| `npm run lint` | PASS | ESLint 无错误；npm 提示系统 Node 18.20.8 低于 npm 11 官方支持范围，但命令成功。 |
| `npm run build` | PASS | TypeScript build + Vite 6 production build 成功，38 modules transformed。 |
| `git diff --check -- apps/frontend` | PASS | 无空白错误。 |
| Basic Auth header mock | PASS | `mock:pass` 仅在请求头为 `Authorization: Basic bW9jazpwYXNz` 时连接成功；干净会话 0 error / 0 warning。 |
| 凭证持久化 | PASS | 用户名和密码仅 React 内存；刷新后连接弹窗重新出现。 |
| localStorage 污染检查 | PASS | 注入主诉、医学正文与 `request_snapshot_json` 后刷新，持久化结果仅保留白名单字段，敏感字段全部移除。 |
| Study finalize 门禁 | PASS | 浏览器检查结果 `draftDisabled=true`、`readyDisabled=false`。 |
| Basic Auth 弹窗视觉 | PASS | 桌面截图 `/tmp/ms-image-basic-auth-modal.png`；字段标签、说明、禁用态和遮罩正常。 |
| 375px 响应式视觉 | PASS | 截图 `/tmp/ms-image-basic-auth-mobile-375.png`；表单、上传槽位、Task 卡与底部导航无横向溢出。 |
| UI/UX final pass | PASS WITH CAVEAT | 已读取 `pro-rules.md`、Quick Reference 1–3 并运行 UX 搜索；reduced-motion CSS 已存在。未逐项实机验证 dark mode、landscape 和最大动态字体。 |
| Runtime CORS 静态核验 | DEV PASS / PROD UNKNOWN | dev 允许任意 origin/method/header 且不启用 credential cookies；production 无 Runtime CORS middleware。 |
| 真实 Runtime health/readiness | PASS | `GET /api/v1/health` 与 `GET /api/v1/readiness` 均 HTTP 200；DB/Redis/Broker ready；`medical_provider_ready=false`。 |
| 真实 Runtime Basic Auth | BLOCKED / VERIFIED 401 | 浏览器发送 `Authorization: Basic ...`；`GET /api/v1/tasks?id=basic-auth-e2e-probe` 返回 HTTP 401 `Missing bearer token`，UI 显示对应 Basic Auth 无效/未启用提示。 |
| 隔离浏览器完整业务链 | PASS (MOCK) | 连接 → Session → Study → Series → 2 图 prepare/PUT/complete → finalize → Quality → Diagnose → Report → Localization 全部完成；Report Revision 1、两图 signed view 与 bbox overlay 正常。 |
| Runtime 请求认证审计 | PASS (MOCK) | 32 个非 OPTIONS Runtime 请求，Basic Header 缺失或错误 0。 |
| OSS 凭证隔离审计 | PASS (MOCK) | 4 个 OSS 请求（2 PUT、2 GET），携带 Runtime Authorization 0。 |
| 浏览器存储审计 | PASS | `sessionStorage` 为空；`localStorage` 只含 workflow 白名单，未保存用户名、密码、Basic Header、signed URL 或完整报告正文。 |
| 浏览器 console | PASS WITH EXPECTED EVENT | 唯一 error 为 mock 鉴权探针 `/tasks?id=__basic_auth_probe__` 的预期 404，用于证明请求越过认证边界；无其他 console error。 |
| Runtime/Vite/临时资源清理 | PASS | Playwright、Vite、Runtime 已关闭；8010/5174 无监听；lock、临时 symlink、测试密钥和测试产物已清理。 |
| 真实 Provider/OSS/医学结果 | NOT RUN | Provider readiness=false；未调用 Provider，隔离 OSS mock 不是真实 OSS，不形成医学准确率证据。 |
| Handoff maintenance | PASS WITH ROTATION | `maintain_handoff.py --compact-if-needed` → `changed=2 warnings=1 unresolved=0`；按容量规则轮转 1 个旧 work-log 段并更新 archive index。 |

## 2026-09-04 — 前端并行主链/展示链验证

| 检查 | 结果 | 证据 |
|---|---|---|
| 后端 source 合同复核 | PASS | `TaskService` 创建 Localization 只要求有效 Diagnose `source_task_id`，不要求 source 已 completed。 |
| 创建因果与执行并行 | PASS (MOCK) | `diagnose_created` 后 15ms 出现 `localization_created source diagnose-parallel`；两者多次同时 running。 |
| 重叠完成窗口 | PASS (MOCK) | Localization 约 6.05s completed；随后 Diagnose 在约 8.07s 仍 running，约 10.07s completed。 |
| 最终 Task 状态 | PASS (MOCK) | 浏览器 TaskBoard 同时显示 Diagnose 与 Anatomy Localization “已完成”。 |
| Report 展示链 | PASS (MOCK) | Revision 1 / final / completed；摘要“并行主链报告已生成”。 |
| Localization 展示链 | PASS (MOCK) | 历史 1 条；#1 ventrodorsal、#2 lateral 各 1 个 bbox；标签“肺”，图例“呼吸系统”。 |
| 请求关联 | PASS (MOCK) | Localization POST body 含 `source_task_id=diagnose-parallel`；Report/Localization current/history 与 prepare-view 均使用同一 Diagnose source。 |
| Basic Auth 抽查 | PASS (MOCK) | Diagnose Task 创建与 Localization prepare-view 请求均携带预期 `Authorization: Basic ...`；Mock 无 `AUTH_FAIL` 事件。 |
| 浏览器 console | PASS WITH EXPECTED EVENT | 唯一错误仍为鉴权探针 `/tasks?id=__basic_auth_probe__` 的预期 Mock 404，无业务链路错误。 |
| 前端 lint/build | PASS | `npm run lint`；`npm run build`（38 modules，产物成功生成）。 |
| 前端 diff-check | PASS | `git diff --check -- apps/frontend`。 |
| 本轮临时资源清理 | PASS | Playwright 会话已关闭；Vite/Mock Runtime 已停止；`.playwright-cli` 已移动到废纸篓；5174/8901 无监听。 |
| 真实 Runtime/Provider/OSS | NOT RUN | 真实 Runtime 仍只接受 Bearer；`medical_provider_ready=false`；不得把 Mock 并行证据扩大为真实医学链路通过。 |

## 2026-09-05 — 可见浏览器现场演示

| 检查 | 结果 | 证据 |
|---|---|---|
| Basic Auth 连接 | PASS (MOCK) | 页面连接 `http://127.0.0.1:8901/api/v1`，侧栏显示 Runtime 已连接；凭证仅为本机演示账户。 |
| 两图上传与冻结 | PASS (MOCK) | `lateral.png`、`vd.png` 均显示“影像就绪”，进度 2/2，Study `study-demo` 冻结 ready。 |
| Quality Review | PASS (MOCK) | Task `quality-demo` 完成；两图均显示 thorax / acceptable。 |
| 并行重叠可见性 | PASS (MOCK) | 同一页面 B Diagnose 与 C Anatomy Localization 同时显示“处理中”；Task ID 分别为 `diagnose-demo`、`localization-demo`。 |
| 分链完成窗口 | PASS (MOCK) | Localization 先显示“已完成”，Diagnose 在同一观察窗口仍为“处理中”；随后 Diagnose 完成。 |
| Localization 页面 | PASS (MOCK) | lateral 与 ventrodorsal 两张影像均可切换；每图 2 个定位框；肺/左肺与心脏 bbox、呼吸/心血管图例可见。 |
| Report 页面 | PASS (MOCK) | Revision 1/current、medical status complete；摘要“并行诊断主链报告已生成”，完整展示 findings/impression/recommendations。 |
| 业务源码修改 | NONE | 演示 harness 与合成影像位于 `/var/tmp/ms-image-demo/`；仓库业务文件未因本次演示变更。 |
| 真实 Runtime/Provider/OSS | NOT RUN | 真实 Runtime Basic Auth 仍为已知 401 阻断；本轮未产生真实医学数据或准确率证据。 |
| 演示资源状态 | LEFT RUNNING | 为用户继续查看，`127.0.0.1:5174`、`127.0.0.1:8901` 与可见浏览器暂不关闭。 |

## 2026-09-04 — 真实数据集并行报告页浏览器验收（UTC）

| 检查 | 结果 | 证据 |
|---|---|---|
| 数据文件真实性 | PASS | 两张 JPG SHA-256：`97648fcd...7363c`、`25138310...ac5`；两份 JSON：`898a5f4e...9ed`、`20534124...c18`，与冻结样本一致。 |
| Diagnose/Localization 同时运行 | PASS (MOCK RUNTIME) | 点击“并行启动诊断与定位”后，TaskBoard 同时显示 Diagnose 与 Anatomy Localization `processing`。 |
| Localization-first 中间态 | PASS (MOCK RUNTIME + REAL DATASET) | 报告页状态为“诊断主链处理中 / 展示链已完成”；左侧已显示真实影像和 bbox，右侧显示“最终报告生成中”。截图 `output/playwright/xray-real-dataset-localization-first.png`。 |
| 双图与 bbox | PASS | `#1 lateral`、`#2 ventrodorsal` 均显示 1 个定位框；bbox 由各自真实 JSON 像素坐标按原图尺寸归一化。 |
| 数据语义边界 | PASS | 图例为 `dataset_annotation / 数据集矩形标注 / 原始标注区域`；页面明确 bbox 不是 pixel mask；未把韩文原始标签解释为器官或病灶。 |
| 最终报告页 | PASS (MOCK REPORT) | Diagnose 完成后 R1 出现，主链/展示链均 completed；报告只整理可追溯的 `ABN / Ch07 / Lateral / VD / bbox` 数据集事实。截图 `output/playwright/xray-real-dataset-final.png`。 |
| 报告证据联动 | PASS | 点击第一条 finding 的 `VD` 后，左侧切换到影像 #2；DOM alt=`X-Ray 影像 2，投照位 ventrodorsal`。截图 `output/playwright/xray-real-dataset-evidence-vd.png`。 |
| 浏览器 console | PASS WITH EXPECTED EVENT | 唯一错误为 Mock 鉴权探针 `GET /tasks?id=__basic_auth_probe__` 返回 404；无影像加载、任务轮询或报告渲染错误。 |
| 前端 lint/build | PASS | `npm run lint`；`npm run build`，39 modules transformed，生产产物成功。npm 11.5.2 对 Node 18.20.8 的支持范围警告不影响命令成功。 |
| diff/Mock 语法 | PASS | `git diff --check -- apps/frontend`；`node --check /var/tmp/ms-image-demo/server.mjs`。 |
| 真实 Runtime/Provider/OSS/医学准确率 | NOT RUN / NO-GO | 本轮 Runtime、时间线、Report、prepare-view 均为隔离 Mock；真实数据资产不能把 Mock 工程演示升级为真实医疗链路证据。 |
| 演示资源状态 | LEFT RUNNING | Vite `127.0.0.1:5174`、Mock `127.0.0.1:8901`、Playwright `xray-dataset` 保留，页面停留在最终报告且 `VD` 已激活。 |
| Handoff maintenance | PASS WITH ROTATION | `maintain_handoff.py --compact-if-needed` → `changed=2 warnings=1 unresolved=0`；按容量规则轮转 1 个旧 work-log 段并更新 archive index，无 unresolved。 |

## 2026-09-05 — 报告页视觉、并行时序与最终响应式验收

| 检查 | 结果 | 证据 |
|---|---|---|
| 最新病例 | PASS (MOCK RUNTIME + REAL DATASET) | `CASE-DATASET-CH07-PARALLEL`；两张真实 JPG 与配套 JSON 来自用户指定数据集。 |
| Diagnose/Localization 执行重叠 | PASS | 两链同时为 `processing`；两个 `/tasks` POST 独立，Localization 以 `source_task_id=diagnose-demo` 关联 Diagnose。 |
| Localization-first 窗口 | PASS | Localization 已 `completed/result_available` 时，同期 Diagnose 仍为 `running/processing`；随后 Diagnose `completed/result_available`。 |
| 最终报告与影像汇合 | PASS | Report R1、两张真实 X-Ray 与每图一个数据集矩形 bbox 同页显示。 |
| 报告证据联动 | PASS | 点击 `VD` 证据后切换影像 #2，显示“报告证据已定位”，bbox 增强；截图 `output/playwright/xray-real-dataset-final-vd-rerun-1200x740.png`。 |
| 视觉语义 | PASS | 深青黑阅片区、冷灰白报告纸张、青色主操作、绿色完成态、黄色风险态；未再使用互相争抢注意力的高饱和大面积色块。 |
| 桌面双栏滚动 | PASS | 页面 `scrollY` 不变，左/右面板 `scrollTop` 可独立变化；双栏等高。 |
| 375×812 响应式 | PASS | 无横向溢出；截图 `output/playwright/xray-report-mobile-375x812-top.png`、`output/playwright/xray-report-mobile-375x812-content.png`。 |
| 844×390 横屏 | PASS | 无横向溢出；截图 `output/playwright/xray-report-landscape-844x390.png`。 |
| Reduced motion | PASS | `prefers-reduced-motion: reduce` 生效，bbox transition 约 `0.01ms`。 |
| Runtime Basic Header | PASS (MOCK) | Runtime API 请求携带 Basic Authorization。 |
| OSS Authorization 隔离 | PASS (MOCK) | 两张 signed URL PUT 均未携带 Runtime Authorization。 |
| 浏览器存储/Cookie | PASS | localStorage 仅 `ms-image.xray.workflow.v1`；无用户名、密码、Basic Header、signed URL、完整报告；sessionStorage 为空，Cookie=0。 |
| 浏览器 console | PASS WITH EXPECTED EVENT | 唯一 error 是 `GET /api/v1/tasks?id=__basic_auth_probe__` 的预期 404；无任务轮询、图片加载或报告渲染错误。 |
| `npm run lint`（Bundled Node 24） | PASS | ESLint 无错误。 |
| `npm run build`（Bundled Node 24） | PASS | 39 modules transformed；`index-BWGYEOeE.css`、`index-DtF9XNzq.js`。 |
| `git diff --check` | PASS | 无空白错误。 |
| 真实 Runtime/Provider/OSS/医学准确率 | NOT RUN / NO-GO | 真实 Runtime Basic Auth 已知返回 401；本轮未调用 Provider/Nacos/数据库/Docker。 |
| 演示资源状态 | LEFT RUNNING | Vite `127.0.0.1:5174`、Mock `127.0.0.1:8901` 与 Playwright `xray-dataset` 保留供用户查看。 |
| Handoff maintenance | PASS WITH ROTATION | `maintain_handoff.py --compact-if-needed` → `changed=2 warnings=1 unresolved=0`；轮转 1 个旧 work-log 段并更新 archive index。 |

## 2026-09-07 — 真实数据集浏览器全链回归

| 检查 | 结果 | 证据 |
|---|---|---|
| 数据与病例 | PASS (REAL DATASET + MOCK RUNTIME) | `CASE-DATASET-CH07-E2E-20260907`；真实 JPG `...0093.jpg`、`...0094.jpg`。 |
| 上传与 Study | PASS | Session/Study/Series、两次 prepare-upload、两次 PUT、两次 complete-upload、Study finalize 全部 HTTP 200；截图 `xray-e2e-20260907-study-ready.png`。 |
| Quality Review | PASS | Quality Task 从 queued/processing 到 completed/result_available；两图均显示 thorax 与各自投照位。 |
| Diagnose/Localization 执行重叠 | PASS | Diagnose start `01:39:04.729Z`，Localization start `01:39:04.744Z`；同时 processing 截图 `xray-e2e-20260907-both-processing.png`。 |
| `source_task_id` 血缘 | PASS | 第二个 `/tasks` POST body 为 `task_type=anatomy_localization` 且 `source_task_id=diagnose-demo`。 |
| Localization-first | PASS | Localization finish `01:39:18.813Z` 时 Diagnose 仍 processing；Diagnose finish `01:39:32.856Z`；截图 `xray-e2e-20260907-localization-first.png`。 |
| Report R1 与双图 bbox | PASS | R1 可见；#1 lateral、#2 ventrodorsal 各 1 个“原始标注区域”矩形 bbox。 |
| 报告证据联动 | PASS | 点击 `VD` 后切换影像 #2 / ventrodorsal，显示“报告证据已定位”；截图 `xray-e2e-20260907-report-vd-evidence-1200x740.png`。 |
| 独立 Localization 入口 | PASS | 两图序列、每图 1 bbox、任务历史与原图阅片正常；截图 `xray-e2e-20260907-localization-view-1200x740.png`。 |
| Runtime Basic Header | PASS (MOCK) | Runtime POST/GET 带 Basic Authorization；未在 handoff 保存凭证。 |
| signed URL Header 隔离 | PASS (MOCK) | `/upload/1`、`/upload/2`、`/view/1.jpg`、`/view/2.jpg` 请求均无 Authorization。 |
| 浏览器存储 | PASS | localStorage 仅 `ms-image.xray.workflow.v1` 白名单状态；无凭证、signed URL、完整报告；sessionStorage 为空；Cookie=0。 |
| 浏览器 console | PASS WITH EXPECTED EVENT | 唯一 error 为 `__basic_auth_probe__` 的预期 Mock 404；无上传、轮询、影像或报告错误。 |
| 前端 lint/build | PASS | Bundled Node v24.19.0；ESLint PASS；Vite build 39 modules transformed。 |
| `git diff --check` | PASS | 无空白错误。 |
| 真实 Runtime/Provider/OSS/医学准确率 | NOT RUN / NO-GO | 8010 未启动；未调用 Provider/Nacos/数据库/Docker；Mock PASS 不扩张为真实集成或临床证据。 |
| 演示资源状态 | LEFT RUNNING | 5174、8901 与 Playwright `xray-fullchain-20260907` 保留，页面停留在 R1 的 VD 证据状态。 |
| Handoff maintenance | PASS | 第二次 `maintain_handoff.py --compact-if-needed` → `changed=0 warnings=0 unresolved=0`；当前 handoff 无需继续轮转或修复。 |

## 2026-09-07 — Basic Auth 真实 AI 与 Localization Prompt 只读复现

| 检查 | 结果 | 证据边界 |
|---|---|---|
| Runtime Basic Auth 合同 | PASS | 无凭证 401、错误 Basic 401、正确 Basic 返回业务层 404；仅证明 Runtime 鉴权，Admin 未放宽。 |
| 真实 Cat Quality + Diagnose AI E2E | PASS | 真实数据集 Lateral/VD；Quality 1 Call/1 Attempt、Diagnose 4 Call/4 Attempt、Provider 全部 HTTP 200、Task completed、Report final；医学状态仍为 `review_required`。 |
| Localization Task 创建与调度 | PASS | Task `23fee4a60fea4d48ba7b25c64a743d74` 经 Basic Auth HTTP 201，带 `source_task_id`，已通过 Outbox/Relay/Worker。 |
| Localization 执行 | FAIL-CLOSED | `stage_prompt_render_failed`，失败发生于 Provider Call/Attempt 创建前；不能声明 bbox 已生成。 |
| `PromptRuntimeClient.render()` 同坐标只读复现 | CONFIRMED | `RuntimeError: Nacos Prompt 缺少 output schema: ms-image.x-ray.anatomy-localization.cat.zh-CN`。 |
| Nacos Cat Prompt metadata 只读回读 | CONFIRMED | version `1.0.0`、存在 content hash、`has_output_schema=false`；未输出 Prompt 正文或 Secret。 |
| Nacos/业务代码写入 | NOT RUN | 本轮无 Nacos 写授权；未覆盖旧版本、未改 Runtime 绕过 Schema、未重试 Provider。 |

## 2026-09-07 — Basic Auth 真实并行全链最终验证

| 检查 | 结果 | 证据边界 |
|---|---|---|
| 真实病例与上传 | PASS | `REAL-XRAY-20200223-0093-0094-E2E-20260907-R2`；两张真实 JPEG 经 signed PUT 上传并完成 Study/Revision。 |
| Quality | PASS | Task `a1336ad19bbf4f14b42cb3961e5e5412` completed；结果暴露体位/质量限制，未把其当医学 Gold。 |
| Diagnose | PASS (ENGINEERING) | Task `39e55ec4dd7942e7b68414e8432d8f1a` completed；8 Stage completed；Report `ce6ed3b1842341c5a6ad688a91d61f82` final，`medical_status=review_required`。 |
| Localization | PASS (ENGINEERING) | Task `4f28c44a76524d73ae962b565be6c2c7` completed；1 Call/1 Attempt；2/2/2/2 image receipt；18 normalized bbox 技术合同通过。 |
| Diagnose/Localization 并行 | PASS | `03:27:29.078757–03:30:20.160055` 与 `03:27:29.110559–03:28:17.578996` 重叠约 48.47 秒。 |
| 查询接口 | PASS | Report current/history、Localization current/history/result/legend/prepare-view 均 HTTP 200。 |
| 浏览器报告页 | PASS | 双图、各 9 bbox、筛选、100%→125% 缩放/复位、报告 evidence→影像 #2 联动通过。 |
| signed view URL 过期恢复 | PASS | 页面出现过期提示后点击“重新申请”，第二张真实 X-Ray 与 9 bbox 恢复。 |
| 报告证据边界文案 | PASS | DOM 与截图均显示 `真实工程链路`；源码无 `Mock Runtime 演示`。 |
| `npm run build` | PASS | Vite 6，39 modules transformed；仅 Node 18/npm 11 支持范围警告。 |
| `npm run lint` | PASS | ESLint 无错误。 |
| focused pytest | PASS | Runtime Basic Auth + Localization 查询/血缘合同：`13 passed, 1 warning`。 |
| 浏览器 console | PASS WITH EXPECTED EVENT | 唯一 error 为 `GET /api/v1/tasks?id=__basic_auth_probe__` 的预期 404；无 Bearer-only 401。 |
| 截图与 trace | PASS | `output/playwright/{workflow-parallel,report-page,localization-0093,localization-0094,report-evidence-0094}.png`；trace `trace-1788751648145.trace`。 |
| 医学准确率 | NOT QUALIFIED | 无可信 Gold、Scorer、Failure Bank、Holdout；保持 `UNKNOWN / NO-GO`。 |

## 2026-09-07 — R4 真实双槽并发与问题修复最终验收

| 检查 | 结果 | 证据 |
|---|---|---|
| R3 全链 | PASS / PARALLEL GAP FOUND | 7 Stage 报告 d0a88e3ce37945519576c7d383f283aa；Task 重叠但 AI Stage 串行。 |
| R4 全链 | PASS | Quality 0358ea09…；Diagnose 731b7811…；Localization fcf4b946… 全 completed；Report 4820744e… final/review_required。 |
| AI Stage 真正并发 | PASS | Screening 与 Localization 重叠 15.338185 秒，SystemAnalysis 与 Localization 重叠 16.687040 秒。 |
| Stage/Call/Attempt 审计 | PASS | Quality 2/1/1、Diagnose 7/4/4、Localization 2/1/1；所有 Call accepted、gemini-3.8-flash、无重试；见 r4-runtime-audit.json。 |
| Task 分页修复 | PASS | 修前正确 study_id 返回 500，DAL source_task_id 缺列；修后 Study、Session、task_type 三种查询均 200，无范围仍 422。 |
| 鉴权 | PASS | 正确 Basic 业务读取成功；无凭证和错误 Basic 401；Admin 未改。 |
| Quality 前端与刷新 | PASS | 两图 thorax、观察 VD，第 1 张申报 lateral 冲突可见；刷新登录后明细恢复。 |
| 原图/定位/报告交互 | PASS | 2152×2036、1724×2696；11+12 框；normalized 坐标有效；筛选、125%/复位、VD 证据切图成功。 |
| 查询/prepare-view | PASS | current/history/result/legend/prepare-view HTTP 200；刷新登录后重新获取 signed view 并加载双图。 |
| 凭证边界 | PASS | 浏览器 Runtime Basic，OSS GET 无 Authorization；R3 PUT 隔离通过；localStorage 白名单不含凭证/signed URL/报告，sessionStorage 空。 |
| 现有定向 pytest | PASS | Basic 7 passed；Localization 查询 25 passed/298 deselected；既有 Pydantic warning。 |
| 最新前端 build/lint | PASS | 39 modules；Node18/npm11 支持范围 warning。 |
| bash -n / git diff --check | PASS | launcher 语法与补丁空白检查通过。 |
| 医学准确率/完整矩阵/production | NOT RUN | 不把单病例工程并行验证外推为医学稳定性或所有分支资格。 |
| Handoff maintenance | PASS | 语义清理后 risks 小于 32 KiB；changed=2 warnings=1 unresolved=0，自动轮转 1 个旧 work-log 段。 |
