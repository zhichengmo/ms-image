# 当前工作日志

## 2026-09-03 — 当前工作区 Git 收口

- 按用户明确授权开始提交和推送当前有用代码；提交前复核合同第 3 节能力总账，限定为 Git 外部写，不运行 Runtime/Provider/Nacos/DB。
- 审计 45 个 tracked 修改和 151 个未跟踪文件；排除 ignored `.env`、IDE、缓存和依赖目录，确认 Prompt/Postman/测试中无真实凭据。
- 对功能源码、Prompt、Schema、迁移、测试、Postman 和 `scripts/dev/run_e2e_local.py` 使用精确路径暂存，未使用 `git add -A`。
- 创建提交 `ee2fa3a feat: complete xray runtime and pet profile workflows`：86 files，19729 insertions，291 deletions。
- 发现 full-chain harness 仍有一组未进入首个暂存快照的按物种 Config 校验改动；复核后作为有用代码单独提交为 `2b7d66b fix(dev): validate species-specific full-chain configs`。
- 当前正在整理已有文档和 `.agent-handoff/` 历史；下一步运行 handoff maintenance、创建文档提交、推送当前分支，再创建 `codex/per-flow-model-routing`。

## 2026-09-03 — 模型路由分支交接完成

- 创建文档/handoff 提交 `adbd2b1 docs(handoff): preserve xray qualification history`，共 122 files；包含 108 个本次新增 archive 文件与两份架构文档。
- 普通推送并设置 `codex/xray-anatomy-localization-v1` upstream，远端新分支创建成功；未使用 force push。
- 从 `adbd2b1` 创建 `codex/per-flow-model-routing`，普通推送并设置 upstream；两个分支在业务实现开始前共享同一基线。
- 当前分支已切换到 `codex/per-flow-model-routing`；下一轮只读审计模型路由和推理参数传递边界，不自动修改其他仓库。


## 2026-09-03 — AI/Prompt code-owned 路由改造收口

- 按用户要求将新 XRay AI 调用改为 `ms-ai-fast` 风格：各 Stage 直接声明 `MODEL_ROUTE` 与 `PROMPT_KEYS`，本轮统一使用 `gpt-5.6-sol`、`race`，暂不处理 `xhigh`。
- 新增 `AiModelRoute` 和 `PromptRuntimeClient`；Worker 在数据库事务外调用 Prompt HTTP Render API，再进入现有 `AIRequestService` 创建 Call/Attempt 并由 Gateway 请求 ms-ai-platform。
- 新 XRay Task 由代码 profile 编译 runtime identity，不读取 active AI Config DB，不生成 Stage Config bindings；数据库继续保存 Task/Stage/Call/Attempt 和冻结审计事实。
- 保留历史 Config Task/replay 兼容；Anatomy Localization、Image Quality 的 code-owned lineage 从 Call 冻结 runtime snapshot 校验，不读取 Config DAL。
- 修复 TargetedReview/Prompt command 对 code-owned Task 的专用 Prompt 判断，保持 Quality、Screening、System 上下文严格消费。
- 更新现有合同测试，证明新 Task 创建与 code-owned lineage 均不访问 Config DAL；未新增迁移或独立测试脚本。
- 完成 299 个定向合同测试、6 个 Mock Prompt→Gateway 全链测试和 381 个全量测试；真实外部 E2E 因环境变量、数据库、Broker 和 Docker 缺失而阻断，未伪报 Provider PASS。


## 2026-09-03 — code-owned AI 路由 Git 交付

- 创建业务提交 `13f674c refactor: use code-owned AI prompt and model routes`，27 files，1529 insertions，695 deletions。
- 普通推送到 `origin/codex/per-flow-model-routing` 成功；本地 HEAD 与 upstream 均为 `13f674cf82b0dd2fe58b2b7ebe8e959ca73b4ef9`，未使用 force push。
- 推送后工作树干净；真实外部 Prompt Runtime/ms-ai-platform/Provider E2E 仍因环境缺失保持 `ENVIRONMENT_BLOCKED`。

## 2026-09-03 — 当前代码猫狗完整主链重测（Prompt Runtime 环境阻断）

- 按用户验收口径执行当前 `diagnose_full_chain`：猫、狗各一次，要求生成唯一 `final Report` 并通过 task/current/history 三个接口查回；医学准确率不在本轮范围。
- 全量后端测试复跑为 `381 passed, 48 warnings`；唯一 launcher 的 Runtime、Relay、Worker、readiness 与 exactly-one consumer 均启动通过。
- 猫 fresh 2 图（Lateral + VD）完成影像创建、OSS 上传/验证、Study finalize、Quality Task 创建和 preparation Stage；Quality Task 为 `cceffba662d542a0981f3ebd022d1443`。
- Quality AI Stage 调用 `PromptRuntimeClient.render()` 时发生 `httpx.ConnectError: All connection attempts failed`；配置指向 `127.0.0.1:8100`，该端口无 Prompt Runtime 监听。
- 失败发生在 Prompt Render 之前，因此未进入 Gateway/Provider、未创建 Diagnose Task、未生成 Report；按 stop gate 未跑狗，结论为 `ENVIRONMENT_BLOCKED`，不是代码链路或医学结果 PASS/FAIL。
- 中止 E2E 后完成 launcher 温关闭；8010 与 launcher lock 均清理，无遗留 ms-image imaging consumer。
- 只读历史核验确认：`13f674c` 已把 XRay Stage 路由固定为 `gpt-5.6-sol/race`，但 `xhigh/reasoning_effort` 明确未实现；`ms-ai-platform` 当前请求 Schema 也无该字段，且 Provider 请求 model 最终来自平台 Endpoint 配置。
- 当前共享工作树出现未提交 `scripts/dev/run_local_chain.sh` diff：增加 Prompt Runtime 环境变量读取/导出和缺失 fail-fast；该修改不能代替启动 `ms-prompt-service`，本会话未回退或提交它。

## 2026-09-03 — direct-Nacos / AI Platform 猫全链 fresh 复测

- 只读逐行对比 `ms-ai-fast` 与当前 `ms-image`：Nacos Client latest 读取、Jinja2 `StrictUndefined`/`tojson`/`$VARIABLE`、Chat Completions URL/headers/payload、HTTP 500 无自动 retry 和 JSON 提取语义均已对齐；XRay 仅额外保留 species exact-only 与可靠执行审计外壳。
- 将既有 `scripts/dev/run_e2e_local.py` 的 full-chain receipt 审计从旧 Gemini/DB Config 身份改为 code-owned Nacos Prompt identity、`gpt-5.6-sol/race`、AI Platform route、冻结 Schema/messages、Call/Attempt/receipt 审计；补齐 Dog Prompt key 映射，未新建测试脚本。
- harness `py_compile`、Ruff、diff check PASS；用真实 Quality Call 单独执行新的 code-owned 审计 helper PASS。
- fresh 猫 Quality Task `ddaf9f23d79f4e3fafb3151e2fc44075` completed：`xray_cat_image_quality@1.1.3`、HTTP 200、`gpt-5.6-sol`、3/3/3、1 Call/1 Attempt、Report 0。
- Diagnose Task `6574961802f34cea80930c5ce04e51cc` 的 StudyScreening completed：`xray_cat_study_screening@2.0.2`、HTTP 200、3/3/3、1 Call/1 Attempt。
- SystemAnalysis 动态读取并渲染 `xray_cat_system_analysis@1.0.2` 后，AI Platform 对单次 `/chat/completions` 返回 HTTP 500；Call/Attempt/Stage/Task 均以 `provider_http_500_internal_error` failed，未重试、无 Provider request ID/response SHA。
- 脱敏结构对比确认 `1.0.1` 历史 HTTP 200 请求与本次 `1.0.2` 的 model/route/temperature/Schema SHA/合同版本相同；当前没有证据将 500 归因为 Prompt 或 Schema，未修改 Nacos Prompt。
- Primary、Targeted、ReportGeneration 未执行，Report 0；public task/current/history 一致。按猫失败即停规则未跑狗。
- 温关闭唯一 launcher；8010、Runtime/Relay/Worker/lock 清理通过。临时 manifest 与空 evidence 目录已删除；关闭时仍出现既有 aiomysql event-loop-close 析构告警。

## 2026-09-03 — ms-ai-fast 对齐复核与 fresh 猫二次复测

- 按用户要求将范围严格收敛到 `ms-ai-fast` 的 Prompt 获取、模板渲染和 AI 请求；只读逐项核对双方源码，没有新增 AI 抽象、fallback、自动重试或医学修正。
- 现有定向合同测试 `22 passed, 372 deselected`；首次未设置 `PYTHONPATH=.` 的收集错误已按工具调用问题记录。
- 启动唯一 Runtime/Relay/Worker owner，固定 namespace `c0cc9e0e-0fed-4faf-bc57-e9bab46a78a9` 和 AI Platform `http://8.149.245.40:8060/api/v1`，建立新的 Cat `cat-03` 资格序列。
- Quality Task `afcedfac...` completed：exact Prompt `xray_cat_image_quality@1.1.3`、无 fallback、Provider 200、actual model `gpt-5.6-sol`、3/3/3、1 Call/1 Attempt、Report 0。
- Diagnose Task `9baeafdd...` 的 StudyScreening completed：exact Prompt `xray_cat_study_screening@2.0.2`、无 fallback、Provider 200、actual model `gpt-5.6-sol`、3/3/3、1 Call/1 Attempt。
- SystemAnalysis exact Prompt `xray_cat_system_analysis@1.0.2` 已动态读取和渲染；唯一请求约 64 秒后由 AI Platform 返回 HTTP 500，Call/Attempt/Stage/Task 以 `provider_http_500_internal_error` 失败，无 retry、无 Provider request ID/response SHA。
- 按停止门未执行 Primary/Targeted/ReportGeneration 和 Dog；Task/current/history 一致为无 Report。
- 未修改业务 AI/Prompt、Schema、Gateway 或 Stage；温关闭 launcher 并清理临时文件，8010/进程/lock 均无残留；既有 aiomysql event-loop-close warning 仍存在。

## 2026-09-03 — 2 图 Cat 继续运行与 Platform timeout 根因定位

- 只读检查远端 Platform：health 200、模型列表含 `gpt-5.6-sol`、OpenAPI 暴露 Chat Completions 但无 audit/log 查询接口。
- 比较持久化请求事实后发现前两次 500 均为 3 图 SystemAnalysis，而历史 2 图请求曾 200；从已完成历史 Task 冻结事实取得 `cat-02` 两张图均为 `ventrodorsal`，建立新的合法 2 图序列。
- Quality Task `3df2e3a8...` completed；Diagnose Task `2281f037...` 的 StudyScreening、SystemAnalysis、Primary、FamilyRouting、DecisionFinalization 全部 completed，其中三个 AI Stage 均 direct Nacos、Provider 200、actual model `gpt-5.6-sol`。
- 本病例未产生 TargetedReview candidate；零图 ReportGeneration 单次调用约 61 秒后由 Platform 返回 HTTP 500 `internal_error`，Task failed、Report 0、无重试。
- 只读核验本机对应 Platform 源码：Endpoint timeout 默认 60 秒并直接传入 `AsyncOpenAI`；非流式 endpoint 将所有异常统一映射为 500 `internal_error`。结合三次失败耗时与 54 秒成功请求，根因高置信锁定为 Platform 上游 60 秒 timeout。
- 未修改 ms-image Prompt、Schema、Gateway、Stage，也未修改 AI Platform；按用户既定范围保留外部配置阻断。launcher 和临时文件已清理。

## 2026-09-03 — 切换 Gemini 3.5 Flash 并完成猫狗主链

- 将诊断链 ImageQuality、StudyScreening、SystemAnalysis、JointPrimaryReader、TargetedReview、ReportGeneration 的代码路由精确切换为 `gemini-3.5-flash/race`；Anatomy Localization 独立展示链保持 `gpt-5.6-sol`。
- 同步现有 full-chain harness 和直接相关模型路由合同测试；通用 Gateway 夹具中的 `gpt-5.6-sol` 保持不变，避免把业务配置误混入传输合同。
- 首次 2 图 Cat：6 次 Gemini 请求全部 Platform HTTP 200；ReportGeneration 因 Nacos `1.0.1` 未要求完整深拷贝冻结医学对象，被 truth-preserving validator 以 `report_generation_medical_result_rewritten` 正确拒绝。Task `780b6d97...` failed、Report 0、无 retry。
- 新增 Cat/Dog ReportGeneration `1.0.2` Prompt 资产；发布前确认版本不存在，经 Nacos `draft → submit` 自动 online，latest exact 回读模板 SHA 与本地一致，未 force publish、未覆盖旧版本、未修改 Schema/validator。
- Fresh Cat `cat-02` 使用历史冻结的两张 `ventrodorsal` 投照位：Quality Task `20fceba6...`、Diagnose Task `00deb1ff...` completed；8 Stage、5 Call、5 Attempt、TargetedReview 触发；Report `081e9443...` final；所有 requested/actual model 均为 Gemini。
- Fresh Dog `dog-03` 使用已完成 Quality Task `d52f24a2...` 冻结的 3 张 caller-declared `ventrodorsal`：Quality Task `a1369670...`、Diagnose Task `7ec955a6...` completed；FamilyRouting=`primary_final`，7 Stage、4 Call、4 Attempt；Report `646cd3e6...` final；所有 requested/actual model 均为 Gemini。
- 修正既有 harness 对条件 TargetedReview 的错误固定断言：现在分别严格验证 targeted 8/5 与 primary-final 7/4 两种合法拓扑。对已完成 Dog Task 做只读 receipt 复验 PASS，没有再次调用 Provider。
- Backend 全量 `403 passed, 48 warnings`；目标 Ruff、py_compile、diff check 均 PASS。唯一 launcher 已温关闭，8010/Runtime/Relay/Worker/lock 无残留；既有 aiomysql event-loop-close warning 仍保留。

## 2026-09-03 — Gemini 猫狗全链最终收口

- 复核诊断主链 6 个 AI Stage 均为 `gemini-3.5-flash/race`，Anatomy Localization 独立展示链仍为 `gpt-5.6-sol/race`；未修改业务代码或再次调用 Provider。
- 修正 `AGENT_HANDOFF.md` 中已经过期的“真实 E2E 环境阻断”状态与下一动作，使根入口与当前 snapshot、validation 证据一致。
- 将本轮临时运行目录 `/tmp/ms-image-gemini-e2e.WYqqsl` 移入 macOS 废纸篓；该操作可恢复，未触碰其他临时目录。
- 最终收尾检查确认 handoff maintenance 无 warning/unresolved，`git diff --check` 通过，8010 无监听，ms-image Runtime/Relay/Worker 和 `/tmp/ms-image-local-chain-8010.lock` 均无残留。

## 2026-09-04 — Dog ReportGeneration 1.0.4 精确字段差异复现

- 只读回查历史 Dog Task `e4b3d9ab...`，确认 ReportGeneration 的完整冻结输入可恢复，但旧 Provider 失败正文未持久化：Call/Attempt `parsed_result_json` 与 `response_object_ref_json` 均为空。
- 按用户授权执行一次诊断复现：动态读取 namespace `c0cc9e0e-0fed-4faf-bc57-e9bab46a78a9` 的 exact Dog Prompt `1.0.4`，无 fallback；通过现有 Gateway 请求 `gemini-3.5-flash`，未写 Task/Report 数据库。
- Provider request `chatcmpl-1788487790` 返回 Schema-valid `xray-final-report.v1`；顶层 source SHA、medical status、contract version 全部正确。
- 递归深度比较确认只有 `$.final_medical_result.coverage.missing_or_limited_views[0]` 一处不同：模型把“对位和稳定性”改为“对位 and 稳定性”。
- 该事实排除 Nacos envelope、输出 Schema 和 JSON parse 作为本次根因；失败归属于让生成模型精确复制复杂冻结医学对象的职责设计。
- 未修改 Prompt/Schema/validator/业务代码/Nacos；未重试。温关闭唯一 launcher，8010、Runtime/Relay/Worker/lock 清理通过；临时目录移入废纸篓，关闭仍有既有 aiomysql event-loop warning。

## 2026-09-04 — Gemini 3.7 Flash 同输入对照

- 按用户要求仅对 Dog ReportGeneration 做模型对照，不修改六个诊断 Stage 的代码路由。
- AI Platform `/models` 只读探测返回 404，随后按停止合同直接发起恰好一次 `gemini-3.7-flash` Chat Completions；未重试或回退。
- 动态 Prompt 仍为 namespace `c0cc9e0e-0fed-4faf-bc57-e9bab46a78a9`、Dog `1.0.4`、无 fallback；输入与 3.5 差异诊断相同。
- Provider request `chatcmpl-1788488881` 成功，requested/actual model 均为 `gemini-3.7-flash`；Schema、顶层 source SHA/status/version 和完整医学对象深度相等均通过，递归差异数 0。
- 当前只能声明单次 3.7 复制 PASS，不能声明稳定性或医学准确率；业务代码、Prompt、Schema、validator、Nacos、数据库均未修改。

## 2026-09-04 — Gemini 3.8 X-Ray 全 Stage 路由与真实猫狗主链回归

- 按用户授权将 ImageQuality、StudyScreening、SystemAnalysis、JointPrimaryReader、TargetedReview、ReportGeneration、AnatomyLocalization 共 7 个 Provider Stage 统一声明为 `gemini-3.8-flash/race`；现有 E2E harness 与 X-Ray 路由合同断言同步为 3.8，通用 Gateway 的其他模型 fixture 保留。
- 切换后的定向静态验证为 `15 passed, 305 deselected`，相关 Ruff、`py_compile` 与 `git diff --check` 均 PASS。
- 使用 `/Users/mozhicheng/workspace/documents/X光_没问题_全量过滤` 的真实 Cat 2 图和 Dog 3 图 manifest；运行前逐图核验路径、size、SHA-256，全部一致。
- 唯一 launcher 注入 AI Platform `http://8.149.245.40:8060/api/v1` 与 Nacos namespace `c0cc9e0e-0fed-4faf-bc57-e9bab46a78a9`，只动态读取 exact Prompt；未发布/覆盖 Prompt，未增加 retry/fallback。
- Cat：Quality Task `10e0f9ed...`、Diagnose Task `7d53e0d6...` completed，Report `1642f558...` final；Diagnose 7 Stage/4 Call/4 Attempt，另有 Quality 1 Call/1 Attempt，全部 requested/actual model=3.8、单 Attempt、receipt/Prompt/Report 深度门 PASS。
- Dog：Quality Task `38920614...`、Diagnose Task `b6f130ee...` completed，Report `6d1c99c1...` final；Diagnose 7 Stage/4 Call/4 Attempt，另有 Quality 1 Call/1 Attempt，全部 requested/actual model=3.8、单 Attempt、receipt/Prompt/Report 深度门 PASS。
- 两个病例均合法走 `primary_final`，没有物化 TargetedReview；因此本轮证明 Cat/Dog 主链 E2E，但不证明 TargetedReview 条件分支已在 3.8 下真实执行。
- Evidence 已移入废纸篓的两个可恢复目录；launcher 温关闭后 8010、Runtime/Relay/Worker/lock 无残留。既有 aiomysql event-loop-close warning 仍出现，未影响 PASS。

## 2026-09-04 — Gemini 3.8 Pilot Case 1 / Cat Primary 1.0.3 资格回归启动

- 历史目标失败：冻结 Case 1 在 Cat Primary `1.0.1` Provider HTTP 200 后因 `provider_result_source_projection_mismatch` fail-closed；冻结 caller projection=`lateral_indeterminate`，Quality observed projection=`ventrodorsal`/inconsistent。
- 固定病例：仅 `acc-pilot-20260904-01-abn-cat-thorax`，因为它是原冻结 10 例的第一个失败病例；未排除、替换或重抽任何病例。
- Prompt/模型变化：仅新增 Cat Primary 不可变 `1.0.3`，正文 SHA `9f26c46e8f171c8b8cb8dafb163edfdbf80c23f8ff9f7b6e7a0987bd37d72b7e`；Schema SHA 保持 `1ac0ad547e48a88040bbeb93ce7be0abf76e956ec8362452697e4cdfe6a4dc68`；所有诊断节点继续 `gemini-3.8-flash`。
- Nacos 资格：指定 namespace exact/latest `1.0.3` online，output=`json_schema`，变量合同不变；`1.0.2` 保持 offline，未覆盖旧版本，未 force publish。
- Race/调用合同：沿用既有单模型 route 字段；每个 Logical Call 最多一个 Attempt，Provider 失败不重试。
- 预期改善：仅要求消除技术 source projection lineage mismatch；本次不预设医学状态，不把工程通过解释为临床准确率改善。
- 可能回归：模型仍可能在其他 frozen source_ref 字段、Schema、Provider 或后续 Stage 失败；任一首次失败立即停止。
- 下一步判定：若 Case 1 仍在 projection lineage 失败，则继续 Prompt/model 输出归因；若转为其他 Schema/工程失败，按对应层归因；只有 Case 1 全链完成后才启动原冻结 10 例资格序列。
- `xray-v2-accuracy-governor` 指定的 `documents/X光V2重构专题/02-V2重构定稿/10-重构执行日志.md` 在当前工作区及 `/Users/mozhicheng/workspace/documents` 中不存在；依据项目“不自行创建文档”规则，本轮不新建该文档，事实写入既有 handoff 日志与验证账本。

## 2026-09-04 — Anatomy Localization 独立展示接口收口

- 按用户明确授权完成三个展示入口：保留既有 `GET /anatomy-localizations?task_id=`，新增 `POST /anatomy-localizations/prepare-view` 与 `GET /anatomy-localizations/legend`。
- `prepare-view` 复用既有结果 lineage 校验，在短事务内验证 owner、Task v3 冻结 manifest、Image 行精确身份与版本；数据库事务结束后才创建 OSS gateway 并签发短 TTL HTTPS URL。
- Image ID 可省略或选择 1–5 个；请求值规范化、拒绝空值/重复/非冻结图片，响应始终保持冻结 manifest 全局顺序。
- OSS 下载签名新增向后兼容的可选 `object_version_id`；无版本号时保持旧 SDK 调用形态，有版本号时绑定 `versionId`。
- 图例动态读取 `xray-anatomy-labels.v1` 唯一事实源，并 fail-closed 检查 6 系统、38 标签的中文展示映射完整性。
- 展示侧业务写入严格限制在 5 个文件；未修改主链 Stage、Prompt、模型路由、Task/Report 状态、数据库模型、migration 或用户并行修改的测试文件。
- 未调用 Provider/Nacos、真实数据库、真实 OSS 或 Runtime；只执行现有合同测试、静态检查和 fake 边界验证。

## 2026-09-04 — Gemini 3.8 十例资格批次停在 Case 2 Cat Quality

- 复核唯一 Runtime owner/readiness 后按冻结顺序启动批次；首个命令因误传 API root 导致 POST /sessions 404，未进入链路，保留为操作审计并以新 identity 重启。
- 有效批次 Case 1 全链 PASS，医学状态 `review_required`；全部 Quality/Diagnose AI Call 为 `gemini-3.8-flash`、1 Attempt、无 reconcile，Cat Primary 动态命中 `1.0.3`。
- Case 2 在独立 Quality Task 首个 AI Call 后 fail-closed：`xray_image_quality_image_1_projection_consistency_invalid`；Provider 已返回（response SHA 存在），2/2 图、1 Attempt，不是 HTTP/timeout/JSON 体积问题。
- 冻结输入两图 declared projection 均为 canonical `lateral_indeterminate`；当前 Prompt 只定义原始别名 `Lateral` 的 family 规则，未显式定义 canonical 值与 right/left lateral 的 validator 语义。归因为 Prompt/validator 输出合同缺口；未放宽 validator、未加 Python 修正、未跳过病例。
- Case 3–10 未运行；总体准确率未计算。


## 2026-09-04 — 有用代码提交与展示主链关联审计

- 重新核对完成度总账、共享工作树和现有提交边界；未使用 `git add -A`，未 reset/clean/restore。
- 定向验证 Anatomy 展示合同 `69 passed, 251 deselected`；Prompt/AI 路由定向合同 `36 passed, 358 deselected`；两份合同测试全量 `394 passed, 48 warnings`。
- 提交 `4aa46f1`：Prompt source 从 AI Control 迁至 neutral core 并保留兼容导出，Runtime direct Nacos，猫狗 exact variant，全 X-Ray AI Stage `gemini-3.8-flash`，Localization `prepare-view`/`legend` 与冻结 lineage 校验。
- 对开发 E2E 运行 Ruff、py_compile、`--help`、`bash -n`、diff-check；提交 `df1a11e`，改为 code-owned Runtime/Prompt/model receipt 核验。
- 本地未跟踪 Prompt `1.0.2`–`1.0.4` 属准确率/外部发布历史，不是 Runtime 文件依赖，本轮未提交。
- 审计确认剩余主链关联不能用 owner + Study + revision 推断；现有 durable decision 要求 `task_record.source_task_id` 与 migration。本轮未获迁移脚本授权，因此未写不完整 ORM/API 半成品。

## 2026-09-04 — 展示主链显式关联完成并提交

- 用户后续明确要求主链和展示链均完成并允许添加代码；按原子范围新增 `task_record.source_task_id`、普通索引 Alembic migration（无 foreign key）、Schema/DAL/Service/API 关联能力。
- 新建 `anatomy_localization` 强制 `source_task_id`，并校验 owner、source 类型、Study、Revision、species、冻结 manifest 与图片集合；数据库列 nullable 仅为历史任务兼容。
- 冻结同 source 最多一个非终态 Localization；主链 Task 返回关联摘要，Localization result/current/history 返回 source ID，完整 bbox 仍不复制进通用 Task 响应。
- 修复 Prompt render 失败收敛边界，保证缺 Output Schema 等渲染错误在创建 AI Call 前失败；补齐合同测试。
- 验证结果：定向 `72 passed`；Gateway 合同 `323 passed`；后端全量 `406 passed`；Ruff、compileall、diff-check、Alembic head/current 全部通过。
- 真实只读接口验证：Task/current/history/legend 均 HTTP 200；diagnose `a042104cf0d84a4a8bede2bbac4a7036` 精确关联 Localization `9107bd3b102f493996a14b7d7d715f30`。
- 发现独立既有问题：`GET /api/v1/tasks/page` 返回 422；Localization 新 bbox 生成仍被 Nacos `1.0.0` Prompt 缺少 Output Schema 阻断。本轮无 Nacos 写授权，未调用 Provider。
- 精确暂存 10 个功能文件并提交 `5c2e1ec feat(xray): link anatomy display to diagnosis`；未使用 `git add -A`，未纳入其他会话 Prompt/handoff 改动。
- 完成后温和停止本轮 Launcher/Runtime/Relay/Worker，确认 `127.0.0.1:8010` 已释放。

## 2026-09-04 — X-Ray 前端宿主只读探索

- 完整读取根 `AGENTS.md` 要求的 handoff 启动集、当前开发合同，以及新增 X-Ray 前端指南和包含 52 个请求的 Postman Collection。
- 使用一个只读默认子代理做跨目录宿主定位，主线程按 `file:line` 线索抽查；确认仓库没有现成前端技术栈、路由、状态管理、API client、组件库或设计系统。
- 现有应用入口是 FastAPI Runtime/Admin；前端唯一可复用输入是 Postman 接口合同，不构成页面宿主。
- 按用户停止条件未创建 React/Vue 等框架，也未修改任何业务源码、后端接口、数据库、Prompt、模型配置或准确率链；等待用户明确选型或提供外部前端仓库。

## 2026-09-04 — X-Ray 前端实现与 Basic Auth 收口

- 用户授权在 `apps/frontend/` 新建 React 19 + TypeScript + Vite 6 前端；实现上传冻结、三类 Task、报告、Localization bbox viewer 和响应式交互。
- 按最新要求把 Runtime 鉴权从 Bearer Token 表单改为用户名/密码 Basic Auth；UTF-8 凭证编码后仅用于 Runtime API，请求 OSS signed URL 时不附带该 header。
- 连接检查增加受保护只读 Task 探针，避免公共 readiness 让无效凭证被误判为已连接。
- 将 workflow localStorage 改为显式字段白名单，排除临床自由文本、医学正文、完整报告、signed URL、`request_snapshot_json` 和未知服务端字段。
- 新增持久化 `studyStatus`，Quality 仅在 finalize 明确成功并返回 `ready` 后启用。
- 未修改后端、Prompt、数据库、迁移、模型或准确率链；未调用真实 Provider、Nacos、数据库或 OSS。

## 2026-09-04 — Basic Auth 浏览器全链验收

- 启动单实例 Runtime/Relay/Worker 与 Vite，真实验证 health/readiness 均 HTTP 200，DB/Redis/Broker ready；readiness 为 `medical_provider_ready=false`。
- 浏览器确实发送 Basic Header；真实 `GET /tasks?id=basic-auth-e2e-probe` 返回 HTTP 401 `Missing bearer token`，确认当前 FastAPI `HTTPBearer` 边界尚不接受 Basic Auth，UI 错误提示正确。
- 在隔离 Playwright mock 中完成连接、Session、Study、Series、2 图 prepare-upload/OSS PUT/complete-upload、finalize、Quality、Diagnose、Report、Localization 全链；报告 Revision 1、两张 signed view 图片与每图一个 bbox 均正确显示。
- 审计 32 个 Runtime 非 OPTIONS 请求，Basic Header 缺失/错误为 0；4 个 OSS PUT/GET 请求 Authorization 泄漏为 0。
- `sessionStorage` 为空；`localStorage` 仅包含 workflow 白名单，没有用户名、密码、Basic Header、signed URL 或完整报告正文。
- `npm run lint`、`npm run build`、`git diff --check -- apps/frontend` 均 PASS；仅有 Node 18.20.8 与 npm 11.5.2 的官方支持范围警告。
- 未修改业务源码、后端认证、登录模块、Prompt 或数据库；未创建真实业务数据、未调用 Provider，不能形成医学准确率证据。
- 已关闭 Playwright/Vite/Runtime 并清除本轮临时 symlink、测试密钥、浏览器产物和响应文件；端口 8010/5174 无监听，lock 文件已移除。

## 2026-09-04 — 前端诊断主链与展示链并行编排

- 用户纠正原前端串行语义，要求 Diagnose→Report 主链与 Anatomy Localization→prepare-view→bbox 展示链并行执行。
- 复核后端 `TaskService` 合同：Localization 创建仅要求同 owner 的 Diagnose `source_task_id`，不要求 source Diagnose 已 completed；两个创建 POST 因 ID 依赖必须先后发出，但 Task 执行阶段允许并行。
- 修改 `XrayWorkspacePage.tsx`：Diagnose 创建返回后立即创建 Localization，不等待 Diagnose completed；展示链创建失败时保留已启动的 Diagnose 并给出分链错误；手动重试只要求 Diagnose 已创建。
- 修改 `TaskBoard.tsx`：Localization 启用条件改为 Diagnose 已创建；主 CTA 与说明明确“并行启动诊断与定位”和两条链独立执行。
- 隔离 Mock + Playwright 证据：Diagnose 创建后 15ms 创建 Localization；二者同时处于 running；Localization 约 6.05 秒完成时 Diagnose 仍 running，Diagnose 约 10.07 秒完成。
- 最终 UI：两 Task 均 completed；Report Revision 1 显示“并行主链报告已生成”；Localization 历史 1 条、两张影像各 1 个“肺”框，图例“呼吸系统”。
- Diagnose/Localization 请求体分别正确携带 `quality_review_task_id` 与 `source_task_id=diagnose-parallel`；抽查 Task 创建及 prepare-view 请求均携带 Basic Auth。
- `npm run lint`、`npm run build`、`git diff --check -- apps/frontend` 均 PASS；Node 18.20.8/npm 11.5.2 支持范围警告仍存在但未影响结果。
- 未修改后端认证、登录模块、Prompt、数据库或 migration；未调用真实 Provider/OSS，本轮并行 E2E 仅为隔离工程证据。
- 已关闭 Playwright `ms-image-parallel-e2e`、Vite 与 Mock Runtime；`.playwright-cli` 已可恢复地移动到废纸篓；端口 5174/8901 均无监听。

## 2026-09-05 — 可见浏览器现场演示

- 按用户“演示给我看看”要求，在 Codex 可见浏览器重跑前端完整展示，不修改业务源码。
- 使用本机隔离 mock Basic Auth `demo-user/demo-pass`、虚拟病例 `CASE-PARALLEL-DEMO` 和两张无敏感合成 PNG；上传目标仅为 `127.0.0.1:8901`。
- 页面完成 Session/Study/Series、两图上传与冻结、Quality Review；Quality 结果显示两图均 acceptable。
- 点击“并行启动诊断与定位”后，Diagnose 与 Anatomy Localization 同时可见为“处理中”，分别使用 `diagnose-demo` 与 `localization-demo`。
- 定位链先完成时诊断主链仍保持处理中；定位页面成功显示 lateral 与 ventrodorsal 两图，每图各 2 个 bbox，并显示呼吸系统/心血管系统图例。
- 随后诊断主链完成；报告页显示 Revision 1/current、摘要、影像所见、影像印象、建议和技术质量摘要。
- 当前为便于用户继续查看，Vite、mock 和可见浏览器均保留运行；本轮证据仅为隔离 UI/编排演示，不是实际 Runtime、Provider、OSS 或医学准确率证据。

## 2026-09-04 — 真实数据集并行报告页演示（UTC）

- 按用户要求改用 `/Users/mozhicheng/workspace/documents/X光_没问题_全量过滤` 的真实数据，选择同一只猫同一次胸腔检查的 `...0093.jpg/.json` 与 `...0094.jpg/.json`；逐文件复核 SHA-256 与既有冻结值一致。
- 复用前端实际编排：Study/Quality 完成后先创建 Diagnose，拿到 Diagnose ID 后立即以 `source_task_id` 创建 Localization；两个 Task 独立轮询。
- 第二轮浏览器观察到 Diagnose 与 Localization 同时进入 processing；约 15 秒后报告页为“诊断主链处理中 / 展示链已完成”，左侧已经显示两张真实 X-Ray、Lateral/VD 切换和每张 1 个真实数据集 Bounding Box，右侧仍为“最终报告生成中”。
- Diagnose 后续完成并生成 Report R1；最终页同屏展示影像、bbox、技术质量、数据集事实 findings、Impression、Recommendations、Limitations 与审计入口。
- 点击报告 findings 中 `VD` 证据按钮后，左侧切换为影像 #2，DOM alt 为 `X-Ray 影像 2，投照位 ventrodorsal`，证明报告证据与影像联动。
- 页面文案根据 legend 显示“数据集标注框 / 数据集矩形标注 / 原始标注区域”，并明确 bbox 不是像素级 mask；报告不擅译 `Ch07`，明确没有权威代码字典和自然语言放射学报告。
- 生成截图：`output/playwright/xray-real-dataset-localization-first.png`、`xray-real-dataset-final.png`、`xray-real-dataset-evidence-vd.png`。Vite、Mock Runtime 和 Playwright 会话为用户现场查看继续保留。
- 该轮业务源码未修改；只更新演示证据与 handoff。真实 Runtime Basic Auth、真实 Provider/OSS 和医学准确率边界保持不变。

## 2026-09-05 — 报告页视觉收口与真实数据集并行重跑

- 修改 `apps/frontend/src/components/ReportPanel.tsx`：新增诊断主链与定位展示链双泳道、独立状态/Task ID/`source_task_id`/创建开始完成时间，并在最终报告上方明确汇合关系与证据边界。
- 修改 `apps/frontend/src/components/ReportImagingPanel.tsx`：明确“矩形 bbox、非像素 mask”，增加报告证据定位提示，并让报告 source ref 切换对应影像与增强所选 bbox。
- 修改 `apps/frontend/src/styles.css`：将视觉系统收敛为深青黑阅片区、冷灰白报告纸张、青色主操作、绿色完成、黄色风险；桌面双栏等高独立滚动，1100px 以下顺序阅读，并补齐移动端/横屏/reduced-motion 行为。
- 以病例 `CASE-DATASET-CH07-PARALLEL` 重新跑通真实数据集浏览器链：Diagnose 与 Localization 同时 processing，Localization 先完成时 Diagnose 仍 running，最终 R1 与两张真实影像/每图一个数据集 bbox 汇合。
- 点击报告 `VD` 证据后，左侧切换到影像 #2，显示“报告证据已定位”，对应 bbox 视觉增强。
- 完成 Basic/OSS Header、浏览器存储、Cookie、桌面独立滚动、375×812、844×390 与 reduced-motion 检查；唯一 console error 是预期 Mock 鉴权探针 404。
- Bundled Node 24 下 `npm run lint`、`npm run build`、`git diff --check` 均 PASS；39 modules transformed。
- Vite、Mock Runtime 与 Playwright 现场继续保留供用户查看；真实 Runtime Basic Auth 仍 401，未调用 Provider/Nacos/数据库/Docker，医学状态保持 UNKNOWN/NO-GO。

## 2026-09-07 — 真实数据集前端全链重新回归

- 按用户“全链路测试一下”要求，只做已有能力浏览器回归，不修改前后端业务源码。
- 恢复本机 Vite `127.0.0.1:5174` 与数据集 Mock Runtime/OSS `127.0.0.1:8901`，新建无缓存 Playwright 会话 `xray-fullchain-20260907`。
- 使用病例 `CASE-DATASET-CH07-E2E-20260907` 上传用户数据集的 `...0093.jpg` 与 `...0094.jpg`，完成 Session/Study/Series、prepare-upload/PUT/complete-upload、Study finalize 和 Quality Review。
- Diagnose 与 Localization 创建请求保持必要因果顺序；Localization body 带 `source_task_id=diagnose-demo`。二者开始时间相差约 15ms，浏览器捕获双方同时 processing。
- Localization 于 `01:39:18.813Z` 完成时 Diagnose 仍 processing；Diagnose 于 `01:39:32.856Z` 完成，生成 Report R1。
- 报告页显示两张真实 X-Ray、每图 1 个原始矩形 bbox；点击 `VD` 证据后切换到影像 #2 / ventrodorsal 并显示“报告证据已定位”。独立器官定位页也通过。
- 请求审计确认 Runtime API 携带 Basic Authorization；两次 signed upload PUT 与两次 signed image GET 均无 Authorization。localStorage 仅有白名单 workflow，sessionStorage 为空，Cookie 为 0。
- 唯一 console error 是预期的 Mock Basic 鉴权探针 404；无业务请求、图片加载或渲染错误。
- Bundled Node v24.19.0 下 lint/build PASS，39 modules transformed；`git diff --check` PASS。
- 新增 `output/playwright/xray-e2e-20260907-*.png` 验收截图；Vite、Mock 与 Playwright 报告页现场继续保留供用户查看。
- 本轮未启动真实 Runtime、未调用 Provider、未写 Nacos/数据库、未启动 Docker；真实 Runtime Basic Auth 与医学准确率边界不变。
- 完成 handoff 维护复核：`changed=0 warnings=0 unresolved=0`，当前文档状态无需继续轮转或修复。

## 2026-09-07 — Basic Auth 真实 AI 与 Localization 渲染阻断定位

- Runtime Basic Auth 已完成并真实验证：无凭证 401、错误 Basic 401、正确 Basic 越过鉴权进入业务层；Admin 保持 Bearer-only。
- 使用用户真实数据集 Cat Lateral/VD 两张影像，经 Basic Auth 跑通 Quality 与 Diagnose 真实 AI 全链；Diagnose 4 Call/4 Attempt、Provider 全部 HTTP 200、Report final。
- 在同一 Study 上通过公共 API 创建带真实 `source_task_id` 的 Localization Task；HTTP 201，Task/Outbox/Relay/Worker 均已到达，但在 Provider 调用前以 `stage_prompt_render_failed` 失败。
- 只读调用与 Worker 相同的 `PromptRuntimeClient.render()` 坐标，精确复现 `Nacos Prompt 缺少 output schema: ms-image.x-ray.anatomy-localization.cat.zh-CN`。
- 只读回读 Nacos metadata：Cat Prompt version `1.0.0`、存在 content hash、`has_output_schema=false`；未输出 Prompt 正文、凭证或 Secret。
- 复核仓库已有完整 Localization Schema/validator，裁决不通过 Runtime 代码绕过；需用户单独授权创建新不可变 Nacos Prompt 版本，不得覆盖 `1.0.0`。
- 本轮未修改业务源码、Prompt、Nacos、数据库、migration 或 Docker；单一 Runtime/Relay/Worker 继续保留供授权后续跑。

## 2026-09-07 — Basic Auth 真实并行全链与报告页最终验收

- 复用用户指定数据集真实猫 X-Ray `...0093.jpg`、`...0094.jpg`，通过浏览器完成真实 OSS 上传、Study/Revision 冻结、Quality、Diagnose、Localization 和 final Report。
- Diagnose Task `39e55ec4dd7942e7b68414e8432d8f1a` 与 Localization Task `4f28c44a76524d73ae962b565be6c2c7` 执行区间重叠约 48.47 秒；Localization 保持 `source_task_id` 关联且不等待 Diagnose 完成。
- Localization 为 1 Logical Call / 1 Physical Attempt，2 张图各 9 个 normalized bbox；全部坐标有限、在 `[0,1]` 且顺序有效。
- 浏览器验证报告与两张真实 X-Ray 同页、影像切换、系统筛选、缩放/复位和 `ventrodorsal` 证据联动；短效链接过期后通过“重新申请”恢复。
- 修改 `apps/frontend/src/components/ReportPanel.tsx`，把误导性的 `Mock Runtime 演示` 改成 `真实工程链路`。
- 本轮早先为真实 OSS 浏览器上传增加仅开发环境启用且 origin 严格匹配的 Vite signed PUT 代理，涉及 `apps/frontend/vite.config.ts`、`apps/frontend/src/lib/api.ts`；未新增后端上传 API。
- 更新 `output/playwright/report-page.png`、`report-evidence-0094.png`；保留完整并行、两图定位截图和 Playwright trace。
- 未修改医学判断逻辑、validator、数据库、migration 或登录模块；未保存 Basic 密码、Token、signed URL 或 Prompt 正文。

## 2026-09-07 — R3/R4 真实全链复验与实际并发修复

- 恢复已退出的 Runtime/Vite，以进程内 Basic 凭证运行真实数据集同病例两图；R3/R4 均上传、Quality、Diagnose、Localization 和 final Report 完成。
- R3 发现单 Worker 槽位使 AI Stage 串行，不能仅凭 Task 区间宣称 AI 并发；run_local_chain.sh 增加可校验并发参数，默认 2。R4 验证 Screening/Localization 与 SystemAnalysis/Localization 分别重叠 15.338185 / 16.687040 秒。
- TaskDal.page_for_owner 补 source_task_id 到 load_only；真实带范围查询由 MissingGreenlet/500 恢复 200，Study/Session/类型筛选均通过。
- TaskBoard/响应类型读取真实 primary_body_part、declared_projection；展示体位冲突。XrayWorkspacePage 在连接或恢复已完成 Quality 时回读明细；刷新浏览器再登录验证通过。
- ReportImagingPanel 证据文案区分解剖定位与数据集框，避免误称病灶范围。
- 本地自动化内核超时后旧 launcher/Vite 生命周期受影响；在任务全部终态后停止本轮旧进程并恢复唯一 owner。旧 Worker 温关闭后残留，仅终止确认属于本轮且无在途任务的 PID，未清理业务数据。
- 归档旧 risks 原文并语义移除过期 Mock/401/Prompt 阻断；当前风险降至容量限制内。同步开发合同历史状态说明与并发证据门。
- 医学与部署治理不扩张；未增加测试脚本、迁移、数据库表或 Prompt 写入。

## 2026-09-07 — 未提交改动审查与提交前收口

- 按用户要求审查 staged、unstaged 和 untracked 改动；能力总账限定为 Basic Auth、X-Ray 前端主链/Localization 展示链入口与交付门禁，不重做既有运行能力。
- 修复 Postman 新入口仍强制 Bearer 的阻断：48 个 Runtime auth block 全部改为 Basic，5 个 OSS PUT 保持 `noauth`，guide 同步移除 Bearer-only 操作说明。
- 修复 E2E/本地 launcher 未可靠读取仓库 `.env` Basic 凭证的问题：进程环境优先、`.env` fallback、缺失凭证 fail-closed，不打印密码；Worker 默认 concurrency=2 保持两条 AI 链并行执行资格。
- 复核前端凭证只在 React 内存、OSS PUT 不带 Runtime Authorization；Diagnose 与 Localization 创建存在 `source_task_id` 必要顺序，进入 Worker 后独立运行和独立轮询。
- 完成 Basic 定向测试、413 个后端全量测试、Ruff、compileall、shell syntax、E2E 凭证优先级、Postman 认证统计、前端 lint/build 和 diff-check；未重跑真实 AI/OSS/Nacos/DB/Runtime。
- 已 fetch `origin/codex/per-flow-model-routing`；本地 HEAD、本地目标分支与远端均为 `5c2e1ec`，提交前无远端前进。
- handoff maintenance 无 unresolved；精确暂存 80 个文件，敏感信息扫描通过，排除 `.env`、浏览器证据、依赖和构建产物。
- staged diff 首次发现 6 个新前端文件 EOF 多余空行，已修正并使 `git diff --cached --check` 通过；该项是本轮最后一个 actionable finding。
- `git switch codex/per-flow-model-routing` 因该分支被 `/Users/mozhicheng/workspace/code/cy-code/ms-image` 占用而拒绝；只读核对确认其 HEAD 与远端同为 `5c2e1ec` 且存在独立未提交改动，本轮不触碰该工作树。
- 下一步在当前相同父提交的 detached HEAD 创建提交，使用显式 `HEAD:codex/per-flow-model-routing` 普通 fast-forward push 并确认远端 SHA；禁止 `git add -A` 与 force push。
