# 当前工作日志

## 2026-08-25 — XRay 后续修正与分阶段实施交接

- 新建并复核 `docs/refactor/23-xray-next-phase-correction-and-implementation-guide.md`，将其设为当前后续实施权威；内容覆盖三类权威、当前事实、完整链路、逐 Service/Stage 输入输出、Prompt 双入口、可靠执行缺口、数据表边界、分阶段 Gate、回滚单位和新会话 Prompt。
- 局部修正 `docs/refactor/22-xray-full-ai-prompt-chain-development-guide.md`，将其降为完整架构参考，并统一 FamilyRouting 医学所有权、Prompt 合同、实施顺序和三层完成定义。
- 更新 `docs/refactor/README.md`、`AGENT_HANDOFF.md`、`AGENT_SESSION_PROMPTS.md` 和 handoff 状态文件，使新会话入口统一指向 23 号文档。
- 将 backlog 中九项文档合同修正标记为已完成；保留 v2 Targeted family/focus 传递、FamilyRouting 版本化结构、unknown 有界终止和 StudyPreparation/取消/迟到/通知幂等为代码 P0 待办。
- 本轮没有修改业务代码、数据库字段、Alembic 迁移、测试脚本或外部环境，也没有运行真实 Provider 或医学评测。

## 2026-08-25 — XRay P0-A Targeted Prompt 合同修正

- 按 23 号当前实施权威完成 P0 源码核验：FamilyRouting 当前固定 `primary_final` 且透传 Primary 完整结果；StudyPreparation 仅做冻结 revision/hash 技术准备；Targeted v2 command 存在 family/focus 传递断点。
- 修改 `apps/backend/services/runtime/stages/xray/prompt_commands.py`：v1/v2 Targeted 统一验证 Family/Focus 和 Primary 完整结果；v2 将 Family/Focus/Strategy 作为冻结路由证据写入 command/safe context，但仍不按 Family 选择 Prompt 正文。
- 扩展现有 `test_ai_prompt_control_plane_contracts.py` 与 `test_ai_gateway_attempt_contracts.py`，覆盖 v2 Targeted 正反例、FamilyRouting 医学所有权边界和 StudyPreparation 非医学边界；未新建独立测试脚本。
- 确认 P0-B 仍有缺口：unknown/unsupported 有界终止、Task cancel、迟到结果、Report publish/notification 幂等。可靠持久的最大对账次数不应偷用 `state_version` 或 `usage_json`，可能需要现有 Attempt 最小字段和迁移授权。

## 2026-08-25 — Prompt 完善路线与新会话 Prompt 最终收口

- 继续扩写 `docs/refactor/23-xray-next-phase-correction-and-implementation-guide.md`，把 Prompt 明确拆为 `Prompt Runtime Contract（提示词运行合同）`和 `Medical Prompt Optimization（医学提示词优化）`两条线；前者属于 E1 前置，后者必须等待 M1 基线后做 Paired A/B。
- 同步当前代码事实：v2 Targeted Prompt command 的 Family/Focus/Primary 完整结果传递已修复并有合同测试，不再作为下一会话待办。
- 将实施顺序统一为 `P0-A（已完成） -> P0-B + Q0 + Q1 -> E1 -> M1 -> Primary Prompt A/B -> 第二 Provider/Model A/B -> M2 Targeted -> Retry -> Fallback -> Race`。
- 新增 Q0-Q6 Prompt 生命周期、Q0/Q1 分阶段实施卡、Prompt 输入/输出/失败语义、冻结/重放、developer/user/image/schema 分层和医学评测门禁。
- 重写 23 号文档第 16 节可复制 Prompt，并同步 `AGENT_SESSION_PROMPTS.md` 当前入口；新 Prompt 明确保留完整长期能力，但不允许同时启用或用代码骨架代替真实资格化。
- 本轮只修改文档和 handoff；没有修改业务代码、数据库模型、迁移、外部配置或医学 Prompt 正文。
- 本轮没有修改模型、CRUD、数据库、迁移、Prompt 医学正文、运行门禁或外部依赖；没有进入 E1。

## 2026-08-25 — P0-B 取消/迟到结果/报告幂等与 Prompt 冻结合同

- `TaskService.cancel_task()` 改为锁定 Task 行，避免取消请求与 Call/Stage/Report 最终化并发穿透；普通 `get_task()` 保持非锁定读取。
- `AIRequestService` 在初始 Call 预算预留、首个 Attempt、Retry、网络 DTO 冻结和 Attempt 最终化边界统一检查 Task 取消/终态与既有 Winner。
- 迟到 Provider 成功保留完整 Physical Attempt 审计事实，但取消/终态 Task 不接受 Winner；pending Logical Call 收敛 cancelled。
- `ImagingExecutionService` 在 AI Stage 消费结果和 DecisionFinalization 完成前锁定并重检 Task；取消时 Stage/Task 收敛 cancelled，不生成医学结果。
- `ReportService.finalize()` 增加同一 DecisionFinalization source 的内容事实幂等与冲突关闭；`publish()` 对重复发布和 CAS 竞态后的同一 published 事实幂等成功。
- Prompt safe context 增加稳定 `prompt_mode`；Targeted Config 编译和冻结重放都要求 structured message contract 同时承载 `SAFE_STUDY_CONTEXT_JSON` 与 `PRIMARY_RESULT_JSON`，并验证 variables 声明。
- 只扩展现有两个测试文件，新增取消、迟到结果、Stage 取消、Report finalize/publish 幂等、Prompt mode、Targeted Profile 和 frozen-integrity 覆盖；未修改医学 Prompt 正文或 Schema。
- 完整工程门禁通过：`80 passed, 19 warnings`，Ruff、compileall、`git diff --check` 通过；真实基础设施和医学评测未运行。


## 2026-08-25 — ms-ai-fast / Nacos / Platform 在线失败定位与恢复验证

- 读取并核对 `ms-ai-fast` 的 `PromptRuntimeClient -> AiRuntimeService -> GatewayClient` 调用链；确认 Nacos Prompt 在本地严格渲染后，通过 OpenAI-compatible `POST /chat/completions` 统一进入 `ms-ai-platform`，服务本身不直接调用 Provider。
- 用当前 `.env` 脱敏复现：Platform base URL 为 loopback `:8062/api/v1` 且 API Key 已配置，但端口无监听，`GatewayClient` 报 `httpx.ConnectError: All connection attempts failed`；失败发生在 TCP connect，尚未进入 Platform 鉴权、模型路由或 Provider。
- 核对 `/Users/mozhicheng/workspace/code/python_project/ms-ai-platform`：`.env` 的用户 API 端口为 8062，MySQL 3306 与 Redis 6379 均在监听；用 `uvicorn main:app --host 127.0.0.1 --port 8062` 启动会话内实例。
- Platform 启动后 health 200；`ms-ai-fast GatewayClient` 在线请求成功，requested `gemini-3.5-flash`、actual `gpt-5-mini`、usage 160 tokens。
- 使用 `AiRuntimeService.invoke_prompt()` 跑通 `Nacos -> flow.answer.dog.zh-CN -> render -> Gateway -> Platform -> Provider`，Prompt version/hash、gateway request ID、AI content、usage 均存在；total tokens 3159，正文只记录 SHA/长度。
- Platform 运行日志确认 `官方qwen3-max` 因 Provider API Key IP restriction 返回 403；竞速/重试选择 `Custom-gpt-5-mini` 后 200 成功。
- 本轮没有修改 `ms-image`、`ms-ai-fast` 或 `ms-ai-platform` 业务代码；仅启动临时运行实例并更新交接状态。

## 2026-08-25 — 远程 Platform `8060` 复测

- 读取当前 `ms-ai-fast/.env` 的非敏感地址配置，确认 `AI_PLATFORM_OPENAI_BASE_URL` 指向 `http://8.149.245.40:8060/api/v1`。
- 实测远程 `/api/v1/health` 为 HTTP 200/healthy。
- 使用 `ms-ai-fast` 原生 `GatewayClient` 进行最小真实 Chat Completions 调用：request ID 和非空响应存在，requested/actual model 均为 `gemini-3.5-flash`；未记录密钥或原始 AI 正文。远程响应未提供 usage。
- 本次无业务代码、数据库、迁移或配置文件写入。

## 2026-08-25 — 用户要求重新测试

- 未修改业务代码、数据库、迁移或外部配置；重新运行 `ms-image` 后端全量离线测试与静态检查。
- 结果：`80 passed, 19 warnings in 0.83s`；`ruff check apps/backend`、`compileall` 和 `git diff --check` 均通过。
- 本次没有启动或调用真实 MySQL、RabbitMQ/Celery、OSS、Nacos Runtime、Platform/Provider；状态仍为 `MS_IMAGE_FULL_RUNTIME_NOT_QUALIFIED`，不能据此宣称 `ms-image` 全链已经跑通。

## 2026-08-25 — `ms-image` 自身 AI 链实测

- 以 `ms-image` 的 `NacosPromptSourceClient` 真实读取已存在的非医疗 smoke Prompt；`normalize_imported_prompt` 和 `PromptRenderer` 均通过，未记录 Prompt 正文。
- 按 `ms-image` Gateway 真实对象组装并尝试 `OpenAICompatibleGatewayAdapter.execute()`；连接合同在网络 I/O 前拒绝 `http://8.149.245.40:8060/api/v1`，原因是仓库仅接受 HTTPS Provider base URL。
- `https://8.149.245.40:8060/api/v1/health` TLS 握手失败；当前目标不能直接用于 `ms-image` Connection。
- 当前依赖工厂也因 Secret Resolver mode 为 `disabled` 正确 fail closed。本轮未写 `.env`、数据库、Nacos、Prompt 或业务代码，未绕过 HTTPS/加密/OSS 安全门禁。

## 2026-08-25 — `ms-image` Nacos → Platform 核心 AI 链真实 E2E

- 根据用户明确要求，直接按 `ms-ai-fast` 的远程 Platform 合同使用 `http://8.149.245.40:8060/api/v1`；此前 HTTPS-only 的结论已被后续用户决定和连接合同改动取代。
- 通过 Nacos 3.x Admin API 新建并发布独立非医疗 smoke Prompt：`ms-image.xray.ai-gateway-e2e.default.zh-CN@1.0.0`；没有改写任何医学 Prompt。
- 以 `ms-image` 的 `NacosPromptSourceClient` 重新读取该 Prompt，并依次执行 `parse_nacos_prompt_payload`、`normalize_imported_prompt`、`PromptRenderer` 与 `PromptMessageAssembler`。
- 使用 `ms-image` 的 `EnvironmentReferenceSecretResolver`（仅进程内临时环境映射，未写入配置或数据库）和 `OpenAICompatibleGatewayAdapter.execute()` 发起真实请求；远程 Platform 返回 actual model `gemini-3.5-flash`、Provider request ID，严格 JSON Schema 通过，marker 回传一致。
- 未打印凭证、Prompt 正文或 AI 正文；仅保留无敏感内容的 SHA-256、字节数和成功事实。
- 回归复验：AI Prompt/Gateway 两个测试文件 `75 passed, 19 warnings`；`compileall` 与 `git diff --check` 均通过。

## 2026-08-25 — 当前完成度与历史任务只读复核

- 用户要求结合截图框选的历史 Codex 任务、当前源码、真实 AI E2E 和数据库现状重新判断项目完成度；未修改业务源码、运行配置、数据库或迁移。
- 复核历史任务的最终取舍：`ms-image` 保留控制面冻结、Task Snapshot、Logical Call/Physical Attempt、审计和状态机；从 `ms-ai-fast` 借鉴 Nacos Prompt 读取、OpenAI-compatible 请求、多消息/多模态组装与请求追踪边界，不能把参考项目整体迁入。
- 只读查询主库 `ms_image`：45 表；缺少 Alembic 版本表和多张当前完整运行时必需表。该事实使完整 Worker/Report 运行资格仍为否。
- 补充用户问答结论：Secret Resolver 防止 API Key 进入数据库/快照/日志；Encrypted Response Store 保护原始 Provider 响应并支持审计/评测复现。两者可在非医疗 smoke 中绕过，但不应从正式影像诊断链删除。

## 2026-08-25 — 旧表清理范围核验（只读）

- 用户要求检查无意义表是否可去掉，尤其关注旧 Prompt / AI 链表；未执行数据库写入或删除。
- 通过 `information_schema` 列出 45 表、表注释、近似行数；数据库无 foreign key 或 trigger。
- 发现当前控制面仍复用 `ai_prompt_template`、`ai_api_connection`、`ai_model_pool` 三张旧物理表，当前 Session 模型复用 `session_record`；这些不是可直接删的“旧表”。
- 其余表需要按历史影像/报告保留、AI 旧链归档和评测证据三类逐表确认；下次若获明确批准，应先给出精确 DROP 清单、备份位置、调用面移除和回滚条件，不能笼统删除全部 AI 表。

## 2026-08-25 — 当前运行时审计与后续开发交接文档

- 用户要求将当前 AI（人工智能）链、数据库边界、完整 XRay（X 光）后续开发路径整理成详细文档，并提供新会话可复制 Prompt（提示词）。
- 新建 `docs/refactor/24-current-runtime-audit-and-next-development-guide.md`：区分 `CODE_IMPLEMENTED（代码已实现）`、`RUNTIME_QUALIFIED（运行时已资格化）`、`MEDICALLY_VALIDATED（医学效果已验证）`；记录核心 AI 网络实测、正式 Worker（工作进程）安全门禁、45 张遗留表同名冲突、目标 16+4 表、Prompt 发布闭环、P0/P1/E1/M1/Q3/Q4/M2/R1/R2/R3 与 Stop（停止）门禁。
- 更新 `docs/refactor/README.md`、`AGENT_SESSION_PROMPTS.md` 与 `AGENT_HANDOFF.md`：后续开发入口改为 24 号文档；21/22/23 号仍保留目标能力范围、逐层架构和历史阶段目标。
- 本轮没有修改业务代码、`.env（环境配置文件）`、数据库或迁移，也没有连接/写入真实外部依赖。

## 2026-08-25 — 文档权威边界二次收口

- 复核发现 23 号文档仍保留“23 号是当前实施权威”的历史 Prompt 文案，容易将新会话带回过时的环境/Provider（模型提供方）状态。
- 更新 `docs/refactor/README.md` 的阅读顺序；为 17、19、20、21 号文档增加当前事实或历史入口提示；将 23 号第 16 节改标为已废止的历史 Prompt，并在其中明确当前入口为 24 号文档和 `AGENT_SESSION_PROMPTS.md` 顶部当前入口。
- 未改变任何运行合同、业务代码、数据表、迁移、`.env（环境配置文件）` 或外部资源；本次只降低文档冲突导致的新会话误操作风险。
- 已运行交接维护：自动归档并轮转两段超量历史工作日志；没有未解决的交接文件容量错误。

## 2026-08-26 — P1 OSS 读取权限核验

- 未修改业务代码、数据库、迁移或 `.env`。
- 在用户确认现有 `.env` 已含真实依赖凭据后，运行隔离、无病例、无 MySQL、无 Broker、无 Provider 的 OSS 合成探针：AES256 加密 PUT、标准 HEAD、Worker 凭据 `get_bytes`、60 秒 GET signed URL 实际读取、删除和删除后 HEAD。五项均通过。
- 结论限定为：当前运行进程对该 synthetic 对象具有 Worker 直读权限，签发的短期 GET URL 可由同机实际读取；尚未证明外部 Provider 网络可达性，且不代表完整 Worker Runtime。

## 2026-08-26 — 移除不属于 ms-ai-fast 的 Gateway 显式覆盖项

- 先使用 `rg --hidden --no-ignore` 检查 `/Users/mozhicheng/workspace/code/cy-code/ms-ai-fast`，两个精确字段 `AI_GATEWAY_SECRET_RESOLVER_MODE` 与 `AI_GATEWAY_RESPONSE_ENCRYPTION` 均不存在。
- 依用户明确指示，仅从 ms-image `.env` 移除这两个显式键。未删除 `apps/backend/core/config.py` 中的 ms-image Gateway 安全默认值；它们仍是 fail-closed 合同，而不是从 ms-ai-fast 复制的配置。
- 新进程 `Settings()` 复核：两个字段未在 `.env` 中出现，当前有效值由默认值解析为 `disabled`。未调用 Provider、未写数据库或 Broker。

## 2026-08-26 — Gateway selector 移除与固定安全路径

- 按用户指示确认 `/Users/mozhicheng/workspace/code/cy-code/ms-ai-fast`（包含 ignored 文件）不存在 `AI_GATEWAY_SECRET_RESOLVER_MODE`、`AI_GATEWAY_RESPONSE_ENCRYPTION` 或 KMS runtime selector 后，从 ms-image 本地 `.env`、`Settings` 与 Gateway runtime composition 移除这条动态选择链；未输出任何 Secret（密钥）或 `.env` 值。
- `AI_GATEWAY_ENABLED=true` 现在固定构造 `EnvironmentReferenceSecretResolver` 与 `OSSEncryptedResponseStore(..., encryption_algorithm="AES256")`；保留 OSS host allowlist（允许域名列表）、短期签名和 disabled（禁用）总开关。
- 更新既有 Gateway 合同测试，断言固定 resolver / AES256；未改数据库、模型、迁移、医学结论或 v1 兼容链。
- 修正当前入口与交接材料中“已删除字段默认解析为 disabled”的过期表述；不新增独立文档。


## 2026-08-26 — AI/Prompt 链按 ms-ai-fast 收敛

- Worker/Runtime 改为直接注入和调用 `GatewayClient`，使用 `AI_PLATFORM_OPENAI_BASE_URL` 与 `AI_PLATFORM_API_KEY`；移除冻结 `secret_ref` 的运行时解析。
- 删除 `OpenAICompatibleGatewayAdapter`、`EnvironmentReferenceSecretResolver`、`OSSEncryptedResponseStore`、`GatewayRuntimeDependencies` 及对应生产文件；Provider 原始响应不再写 OSS，数据库不再保存 response object reference。
- Prompt/Nacos 改用共享 `NACOS_*` 参数合同，保留 Nacos 原始模板，使用 `StrictUndefined/tojson/$variable` 和任意合法冻结变量；Gateway messages 固定为完整渲染 Prompt 的单条 `user` message。
- 更新既有 Prompt/Gateway 测试以匹配参考链；没有新增独立测试脚本、迁移脚本、表、字段、Service 或微服务。
- 生产扫描确认旧类名、`AI_GATEWAY_*`、`AI_PROMPT_NACOS_*`、`MS_IMAGE_AI_SECRET_*`、`env-secret://`、`SAFE_PROMPT_VARIABLES` 和 Provider 原始响应存储路径无残留。
- 未运行真实 MySQL、OSS、Broker、Nacos、Provider、完整 Worker Runtime 或医学验证。

## 2026-08-26 — 已核验提交与 P0 只读数据库基线，等待数据库边界决定

- 核验分支 `codex/prompt-runtime-ai-gateway` 的 `325dd8e42d596e0b28a22ece3806da001ec4f2a6` 已与 `origin/codex/prompt-runtime-ai-gateway` 同步；工作树干净，额外 `git push origin HEAD` 为 `Everything up-to-date`。
- 离线代码验证：三个现有 AI 合同测试文件 `81 passed, 19 warnings`；相关目录 `compileall` 通过；`git show --check HEAD`、`git diff --check` 通过；已删除 Gateway/Secret/Response Store 生产标识扫描无结果。
- P0 只读连接真实 `ms_image`：45 表、无 `alembic_version`。`ai_prompt_template`（375 行）、`ai_api_connection`（96 行）、`ai_model_pool`（19 行）和 `session_record`（5772 行）已存在且与当前 Runtime ORM/迁移定义不兼容；其他目标 Runtime 表缺失。
- 当前 `20260824_01` 会新建上述同名控制面表，禁止直接对该旧库执行 `alembic upgrade head`。未执行任何 DDL/DML、迁移或外部 Worker/Provider 测试。
- 代码审计同时发现未使用的 legacy `response_object_ref_json` 仍保留于 AI Call/Attempt 模型、DAL 和未部署迁移；当前不改动，待 P0 数据库方案和授权后统一处理。

## 2026-08-26 — 提交 v2 Task Admission 一致性修正并完成 P1 配置差距核验

- 审阅现有未提交 diff 后，只提交 `apps/backend/services/runtime/service/task_service.py` 与现有 `apps/backend/tests/test_ai_gateway_attempt_contracts.py`；提交 `6057ec9 fix(xray): admit qualified provider configs` 已推送到 `origin/codex/prompt-runtime-ai-gateway`。
- Task Admission 对 v2 Config 现在同时冻结并核验规范化 Gateway Profile：`provider_disabled == not provider_enabled`，且 capability manifest 的 profile SHA 必须等于规范化 profile 的 SHA。已资格化的 provider-enabled Config 得以进入既有冻结链；v1 provider-disabled 兼容链保持。
- 验证：Ruff 通过；三份既有 AI 合同测试 `86 passed, 19 warnings`；compileall、diff/cached-diff check、commit 和 push 均通过。warning 仍是已有 Pydantic/datetime deprecation。
- 无数据库、OSS、Broker、Provider 或医学写操作。随后以非敏感布尔 presence 核验本机 Settings：代码读取 `.env-01`，而 `.env` 与 `.env-01` 均无非空 `AI_PLATFORM_OPENAI_BASE_URL` / `AI_PLATFORM_API_KEY`，因此 `settings.ai_platform_configured=False`；OSS 为 ready、Broker enabled、MySQL DB configured。此事实说明真实 Worker Platform 配置仍未资格化，不恢复已删除的 `AI_GATEWAY_*` 链。

## 2026-08-26 — 方案二 XRay 猫/犬 Primary Prompt 发布至 Nacos

- 按用户明确选择的方案二，完整读取 `vet-platform` 猫/犬全图 XRay Prompt，提取技术质量、全图系统扫查、跨系统一致性、防漏诊与防过诊规则；未原样迁移旧 specialist 上游依赖、旧变量、旧状态或旧 JSON 输出。
- 用户进一步确定 XRay 是独立 `xray` 模态、Nacos module 为 `x-ray`，并要求猫犬不再使用混合 `default`。代码将内部 key 固定为 `xray_cat_primary` / `xray_dog_primary`，强制 Nacos variant 为 `cat` / `dog`，XRay 请求不允许 default 或跨物种 fallback。
- 先对两个正式 Data ID 及 latest 进行 Nacos 预检，确认不存在；随后创建 `ms-image.x-ray.primary.cat.zh-CN@1.0.0`（SHA-256：`0be1b353bc4527ff9d70c8dc871300b7b1dd0f746b7e56e81138bd1d23b96b64`）与 `ms-image.x-ray.primary.dog.zh-CN@1.0.0`（SHA-256：`b394ccb6cbcefd9f12ab8819e1ce7d743de5758cb0896f1734b13d13f3998022`）。
- 两个候选的管理端 detail、运行时 exact/latest 以及 `NacosPromptSourceClient -> parse_nacos_prompt_payload -> PromptRenderer -> PromptMessageAssembler` 回读均通过。修复了 Jinja 注入 JSON Schema 的 `$schema`/`$value` 被遗留 `$VARIABLE` 扫描误识别的问题。
- 未写 MySQL、未导入 `ai_prompt_template`、未编译/激活 Config、未创建 Task Snapshot，未调用 Provider；当前用户优先 P0/P1/E1 工程 AI 链，不开展医学评测。完整 Worker Runtime 与医学验证状态不变。

## 2026-08-26 — 宠物档案迁移来源只读审计

- 用户要求参考 `ms-ai-fast` 的宠物档案实现。只读核验其 `20260706_0001_ai_business_tables.py`、`20260721_0011_add_pet_profile_is_neutered.py` 与关联 Service/DAL。
- `ms-ai-fast` 的正确业务模式是“档案 ID + 所属用户校验 -> `pet_type` 归一化”；但其首迁移同时创建 `pet_profile`、`pet_profile_record`、`medical_record`、`session_record`、报告及 AI 任务等多张业务表，不能复制到 `ms-image`。
- 对当前 `.env` 的 `ms_image` 做只读 MySQL 核验：连接成功；`pet_profile`、`study_record`、`task_record` 不存在；现有 `session_record` 是旧聊天记录表，与当前 Runtime ORM 不兼容；未执行 DDL、迁移或代码修改。

## 2026-08-26 — `ms_image` 空旧表备份后清理

- 按用户要求对配置库 `ms_image` 先做全量 `mysqldump` 备份，输出到 `/Users/mozhicheng/workspace/code/cy-code/ms-image-db-backups/ms_image-20260826T102227Z.sql.gz`；metadata 文件为同目录 `ms_image-20260826T102227Z.metadata.json`，raw SQL SHA-256 为 `88d2035fc113af21e6a995ef3990301f3aef13b51a2bccc1084ba7009e897dbe`。
- 只读盘点确认清理前共 45 张表，无 foreign key、view、routine、trigger、event；当前 `Base.metadata` 只声明 20 张目标表，DB 中只有 `ai_prompt_template`、`ai_api_connection`、`ai_model_pool`、`session_record` 4 个同名表，但列结构是旧版/不兼容。
- 为避免误删业务历史，本轮仅删除同时满足以下条件的空旧表：当前 ORM 不建模、当前 ms-image 代码不引用、无外键依赖、DROP 前精确 `COUNT(*)=0`。删除清单：`ai_message`、`xray_validation_run`、`api_request_stats`、`xray_validation_consistency`、`xray_validation_prompt`、`ai_agent_recent`、`ai_conversation`、`x_ray_analysis`、`xray_v3_accuracy_run`、`ai_execution_trace`、`xray_validation_step`、`ai_execution_attempt`、`user_usage_account`、`ai_output_schema`。
- DROP 前额外保存清理元数据与每张被删表 DDL 摘要到 `/Users/mozhicheng/workspace/code/cy-code/ms-image-db-backups/ms_image-cleanup-empty-unused-20260826T103113Z.metadata.json`。
- 清理后复核 `ms_image` 物理表数为 31；上述 14 张表均不存在。未删除任何有数据旧表；未创建/迁移/改名目标 Runtime 表。

## 2026-08-26 — 用户确认后删除剩余非 Runtime legacy 表

- 用户明确表示“没有用的表就要去删掉，不然会干扰判断，反正已经有备份”。据此按“当前 `ms-image` SQLAlchemy ORM 模型集合”为保留边界，删除剩余 27 张不在当前模型集合中的 legacy 表。
- DROP 前保存每张表的精确行数、`SHOW CREATE TABLE` 与 DDL SHA-256 到 `/Users/mozhicheng/workspace/code/cy-code/ms-image-db-backups/ms_image-cleanup-legacy-non-runtime-20260826T103657Z.metadata.json`，并引用先前全量备份 `/Users/mozhicheng/workspace/code/cy-code/ms-image-db-backups/ms_image-20260826T102227Z.sql.gz`。
- 删除清单：`ai_agent`、`ai_agent_action`、`ai_agent_prompt`、`ai_agent_runtime_config`、`ai_config`、`ai_config_pool_override`、`ai_connection_profile`、`ai_governance_change_log`、`ai_governance_model_pool`、`ai_prompt`、`ai_prompt_revision`、`ai_provider`、`ai_request_log`、`ai_stage`、`ai_stage_plan`、`ai_stage_round`、`ai_xray_anatomy_crop`、`async_xray_task`、`gpt_config`、`gpt_config_item`、`medical_images`、`prompt_evaluation_analysis`、`prompt_evaluation_detail`、`prompt_performance`、`prompt_publication`、`prompt_publication_history`、`report_content`。
- 清理后 `ms_image` 仅剩 4 张表：`ai_api_connection`、`ai_model_pool`、`ai_prompt_template`、`session_record`。这 4 张是当前代码同名表，但仍是旧列结构；目标 Runtime 表仍缺失。

## 2026-08-26 — 删除剩余 4 张同名旧结构表

- 用户继续确认“没用的表直接先删掉”。当前 `ms_image` 仅剩 `ai_api_connection`、`ai_model_pool`、`ai_prompt_template`、`session_record` 4 张表；虽然表名在当前 ORM 中存在，但字段结构仍是旧结构，无法作为新 Runtime schema 使用。
- DROP 前保存每张表的精确行数、`SHOW CREATE TABLE` 与 DDL SHA-256 到 `/Users/mozhicheng/workspace/code/cy-code/ms-image-db-backups/ms_image-cleanup-remaining-old-structure-20260826T121615Z.metadata.json`，引用先前全量备份 `/Users/mozhicheng/workspace/code/cy-code/ms-image-db-backups/ms_image-20260826T102227Z.sql.gz`。
- 删除 `ai_api_connection`、`ai_model_pool`、`ai_prompt_template`、`session_record`。清理后 `ms_image` 表数为 0。
- 当前 DB 已去除旧表干扰，但尚未创建任何正式 Runtime 表；下一步是空库建表/baseline，而不是直接宣称 Runtime ready。


## 2026-08-26 — 快速上线 Prompt 共用方向分析

- 读取截图所指 Codex 任务 `审计 XRay Worker 安全资格化` 的近期历史、本地 session 摘要和相关源码，确认历史路径曾要求 cat/dog Prompt 身份隔离，但用户最新目标为快速上线，倾向先不做猫狗医学正文分叉。
- 未修改业务代码、数据库、Nacos、Prompt 内容或环境配置；仅更新 handoff 记录，标明推荐快速路径为 cat/dog 外部身份壳继承/共用 common Primary 正文，而不是直接启用 XRay `default` fallback。

## 2026-08-26 — 重建当前代码有用 Runtime 表

- 用户发现表被清空后要求“有用的表你给我创建”。立即在当前 `ms_image` 空库中按当前代码 SQLAlchemy `Base.metadata` 创建 20 张模型表，没有生成新的迁移脚本。
- 执行 `Base.metadata.create_all` 后运行 `alembic stamp head`，将 `alembic_version` 标记为 `20260824_02`。该操作用于把空库快速对齐当前模型表集合；历史旧表数据没有恢复到当前库，仍只在备份中。
- 复核结果：`ms_image` 当前 21 张物理表（20 张模型表 + `alembic_version`），`model_missing=[]`，`extra_non_model=[]`，`alembic_version=20260824_02`。关键表列数：`ai_prompt_template` 20、`ai_api_connection` 19、`ai_model_pool` 18、`session_record` 17、`task_record` 38、`outbox_record` 22、`ai_config_record` 48、`ai_call_record` 43、`ai_call_attempt_record` 31、`report_record` 15、`study_record` 24、`image_record` 43。所有新表当前 0 行。
- 仍未创建 `pet_profile`/`medical_record`，因为当前 ms-image 代码模型尚不存在这两张表；若用户要按宠物档案选 XRay 猫/犬 Prompt，需下一步补模型/CRUD/Service/迁移。
- 用户随后明确：不再检查当前 Model 内哪些表有用，Model 注册表整体就是保留与建表边界；再次只读复核 20 张 Model 表全部存在，未继续删表。

## 2026-08-26 — 重新审查快速上线 Prompt 身份并修正建议

- 按用户“再好好思考”重新核对 22/23 号 XRay 架构文档、PromptSource、Task Config 选择/激活、Prompt 上下文、Config Compiler 冻结字段、既有合同测试以及 cat/dog 分叉提交来源。
- 结论修正：上一版“cat/dog 两个外部壳共用 common 正文”仍有重复身份债务；当前 Runtime 只有一个 global `xray_diagnose` Config，首版既然不按 species 路由，应直接收敛为一个 `xray_primary` + exact-only `common` variant。
- 明确“传承”只发生在编写/发布阶段；Runtime 不实现父子 Prompt 动态读取或拼接，仍冻结一份完整正文与 SHA。
- 同步修正 handoff 中过时的“数据库仍为空”描述：最新验证已创建 20 张模型表并 stamp `20260824_02`；当前阻断是控制面数据、Config/Task 冻结、Worker Platform 配置和 E1 全链，而不是物理缺表。
- 本轮未修改业务代码、测试、Nacos、数据库或环境；建议等待用户确认后再执行最小精确改动。


## 2026-08-26 — 落地 Task 接口 species 参数与 XRay 单一 common Prompt

- `apps/backend/schemas/task.py`：新增 `TaskCreate.species`；`diagnose` 必传，归一化后只接受 `cat` / `dog`；`replay` 兼容可不传。
- `apps/backend/services/runtime/service/task_service.py`：把接口 species 传给 `_build_request_snapshot()` 并冻结为 Snapshot 顶层字段；只保留三处目标修改，清理了一次非目标 Ruff format 差异。
- `apps/backend/services/ai_control/service/prompt_source.py`：将 XRay source 从 `xray_cat_primary/cat`、`xray_dog_primary/dog` 收敛到 `xray_primary/common`，保持 exact-only、无 default fallback。
- 更新现有 `test_ai_gateway_attempt_contracts.py` 与 `test_ai_prompt_control_plane_contracts.py`，覆盖参数必传/归一化/拒绝非法值、Snapshot 冻结、single common source、非法 variant 拒绝和 Primary/Targeted species safe context。
- 未新增数据库表/字段、迁移脚本、Service、Repository、宠物档案或独立测试脚本；未改 Nacos、MySQL 或环境。

## 2026-08-26 — 宠物档案统一继承方案截图复核

- 截图只标示“评估猫狗统一继承方案”这一历史任务，没有新的表或迁移指令。主线程完整复核当前 Task/Prompt 代码和 `ms-ai-fast` 的宠物档案链。
- 确认当前 `ms-image` 已正确完成下游冻结边界：`TaskCreate.species` 仅允许 cat/dog，Task Snapshot/request SHA 固化该值，Worker 仅向 `SAFE_STUDY_CONTEXT_JSON` 传递冻结值；不回查档案、不猜测物种，Prompt 保持唯一 `xray_primary/common`。
- 确认 `ms-ai-fast` 现有事实为 `medical_record.session_id -> pet_profile_id -> pet_profile.pet_type`。不复制其业务迁移：它同时带 BIGINT、外键、file_asset 和多个非本服务表。正确待办是由上游在创建 XRay Task 前完成该解析，传入已规范化的 species；本轮不改表、字段、迁移、Service 或生产代码。
- 复跑三份既有 AI 合同测试、Ruff、compileall 与 diff check：`94 passed, 19 warnings`；warning 为已有 Pydantic/datetime deprecation。真实上游集成及完整运行链均未运行。

## 2026-08-26 — 猫狗统一继承方案最终复核

- 用户截图仅显示“评估猫狗统一继承方案”历史任务标题，不包含新代码、数据库或迁移指令。
- 主线程重新核验 `ms-image` Task Snapshot / Prompt Source / Worker safe context 与 `ms-ai-fast` 的 `medical_record.session_id -> pet_profile_id -> pet_profile.pet_type` 语义。结论不变：当前 `ms-image` 不应复制上游宠物档案表；上游负责解析 `cat|dog`，`ms-image` 只校验并冻结，Worker 只消费冻结 Snapshot。
- 未修改生产代码、数据库、表、迁移、Nacos 或环境；仅将 backlog 中过时的“species -> Config/Prompt identity”措辞改为“species -> Task Snapshot -> SAFE_STUDY_CONTEXT_JSON -> 唯一 xray_primary/common Prompt”。
- 重跑既有合同测试、Ruff、compileall 和 `git diff --check`，见 `validation.md`；完整上游集成与 Worker Runtime 仍未运行。
