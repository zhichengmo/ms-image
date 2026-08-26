# 当前工作日志

## 2026-08-24 — Prompt → Gateway → Primary 组合链路验证

- 使用不落盘的 Python heredoc 组合烟测串联 `normalize_imported_prompt`、`PromptRenderer`、`PromptMessageAssembler`、Fake signer/Secret/response store、`OpenAICompatibleGatewayAdapter` 的 `httpx.MockTransport` 和 `XRayJointPrimaryReaderStageHandler.consume_ai_call()`。
- 验证 structured Prompt 保持 `developer` 规则与 `user` 安全上下文隔离；图片仅在 Gateway 请求时注入最后一个 user 消息，Provider 返回受冻结 JSON Schema 严格校验。
- 验证 provider request ID、actual model、usage、response SHA-256、`encrypted-object-ref.v1`、`ai-image-receipt.v1`、发送图片数量及 Primary `completed/produced` 结果。
- 验证未注入基础设施时首先返回 `ai_gateway_image_signer_disabled`，默认 fail closed 未被绕过。
- 第一次 heredoc 仅因临时 Fake Store 参数别名误写为类型注解而报 `NameError`，未进入项目链路；修正夹具后通过。未发现需要修改的项目代码，未新增测试脚本或迁移脚本。
- 针对性 46 项、全量 52 项 pytest、Ruff、compileall、diff-check 全部通过；真实 MySQL/OSS/Secret/Nacos/Provider 未连接。

## 2026-08-24 — Nacos 认证修复与真实 AI 链路核验

- 使用 `ms-ai-fast` 自身 `.env` 和源码执行不落盘在线烟测，真实跑通 Nacos Prompt → `AiRuntimeService` → 本地 `ms-ai-platform` → Provider；只记录脱敏 lineage、模型、usage 和哈希。
- 对照发现 `ms-image` Nacos Source 的 username/password 从未参与认证；旧实现读取已知存在 Prompt 返回 HTTP 403。
- 修改 `apps/backend/services/ai_control/service/prompt_source.py`，直接复用 `qj-nacos==0.2.0` 的 Nacos v3 登录、token refresh 和 request 合同；保留 404 fallback 与其他错误 fail-closed 语义。
- 修改 `apps/backend/tests/test_ai_gateway_attempt_contracts.py` 的 Nacos 畸形 payload 用例，改为注入 Fake Nacos client，避免测试依赖客户端私有 `httpx` 字段。
- 修复后用 `ms-image` Source Client 真实读取参考 Prompt 成功，version/MD5/template SHA 与 `ms-ai-fast` 一致。
- 读取 Nacos inventory：参考 namespace 共 207 个 Prompt；用户指定目标 namespace 当前 0 个 Prompt。抽查参考 `flow.answer` 无法通过 `ms-image` 的安全变量导入合同，因此未自动切换 namespace。
- 使用 `ms-image` `OpenAICompatibleGatewayAdapter` 对本地真实 Platform 发起 strict JSON Schema 请求，返回真实 Provider request ID；requested `gemini-3.5-flash`，actual `gpt-5-mini`，Schema/usage/response SHA 均通过。

## 2026-08-24 — Nacos 配置合同与在线链路再收敛

- 对照 `ms-ai-fast` 实际 `.env` 与 `PromptRuntimeClient` 后确认：传输客户端已经一致，但 `ms-image` 仅识别 `AI_PROMPT_NACOS_*`，不能直接消费已跑通的 `NACOS_*` / `NACOS_PROMPT_*` 部署配置。
- 在 `apps/backend/core/config.py` 使用 Pydantic `AliasChoices` 增加兼容别名；AI 专用变量优先，共享变量次之，namespace 最终默认仍保持用户指定值。没有从其他仓库自动读取配置或 Secret。
- 在既有 Prompt 控制面测试文件中增加共享配置合同与覆盖优先级用例。
- 使用 `ms-ai-fast` 的真实 Nacos 配置合同启动 `ms-image` 后，正式 `PromptImportService._fetch_nacos()` 在线读取已知 Prompt 成功；参考 Prompt 仍因变量语义不兼容而按设计拒绝导入。
- 再次执行 `ms-ai-fast` Nacos → Platform → Provider 在线调用成功，requested `gemini-3.5-flash`、actual `gpt-5-mini`。

## 2026-08-24 — D5 详细开发文档与新会话交接收口

- 基于当前工作树、Prompt/Config、Task/Stage/Worker、Logical Call/Physical Attempt、Gateway Adapter 和 XRay Stage 实现事实，重写 `docs/refactor/20-monorepo-refactor-new-session-prompt.md`。
- 将下一阶段统一为 `Phase D5：Primary-only Runtime Foundation（D5：仅主读运行时基础闭环）`，不重新建设已存在的 Prompt/AI 主链。
- 文档补齐当前完整链路、五个 Stage 的目的/输入/逻辑/输出/失败语义、Call/Attempt 三段事务、数据库/OSS 边界、真实依赖组件合同、unknown reconcile 状态机、文件级实施地图、Gate（门禁）、停止/回滚条件和可复制的新会话 Prompt。
- 明确 `FamilyRouting（家族路由）` 当前固定 `primary_final`，`TargetedReview（专项复核）` 在 D5 保持关闭；默认不新增业务表、不恢复 `file_asset`、不修改医学 Prompt 正文。
- 更新 `docs/refactor/README.md`，加入 19/20 号文档，并把下一阶段开发阅读顺序调整为 20 → `AGENT_HANDOFF.md` → 当前源码。
- 本轮只修改文档与 handoff，没有修改业务代码、数据库模型、迁移或测试脚本，也没有执行共享基础设施或医学准确率验证。
- 根据独立源码核验，同步修正 19 号文档的过期状态：控制面和 Call/Attempt/Gateway 主体已实现；v2 Task 可继续使用 retired Config 冻结快照，v1 legacy 仍保留 active-only 兼容例外。


## 2026-08-24 — Phase D5 Primary-only Runtime Foundation 代码闭环

- 新增唯一 `GatewayRuntimeDependencies（网关运行时依赖集合）`，装配 OpenAI-compatible Adapter、SecretResolver、OSSAttemptImageSigner、OSSEncryptedResponseStore 和 ProviderAttemptLookup；默认 disabled，启用配置不完整时 fail closed。
- 新增受限 `EnvironmentReferenceSecretResolver（环境引用密钥解析器）`、OSS 图片复验/短签名能力和加密原始响应存储；Secret、Signed URL 和原始响应正文不进入数据库或普通错误信息。
- `StageExecutionWorker（阶段执行工作进程）` 和 Celery composition root（装配根）改为注入统一依赖，Provider/OSS 网络 I/O 保持在数据库事务之外。
- 实现 unknown Attempt（未知物理尝试）到期查询、CAS claim、事务外 Provider lookup、unknown/unsupported 重排、succeeded/failed 终结及有效 Stage lease 恢复；默认 lookup 为 unsupported，禁止盲目重发。
- 修复成功 lookup 字段校验漏洞：必需字段改为 `required.issubset(network_result)`，额外字段不再掩盖字段缺失。
- 只扩展既有 `apps/backend/tests/test_ai_gateway_attempt_contracts.py`，覆盖 due 条件、claim 冲突、四类 lookup 状态、Stage pending/restore、缺失成功字段和重复成功幂等；未新增测试文件、迁移或业务表。
- 完成验证：后端全量 `67 passed`；相关 Ruff、全后端 compileall、`git diff --check` 通过。完整共享非生产 Worker Runtime 和医学评测仍未运行。

## 2026-08-25 — XRay 完整能力链路与新会话 Prompt 文档

- 新建 `docs/refactor/21-xray-complete-capability-chain-and-session-prompt.md`，整理七项完整能力、当前代码事实、在线总链、阶段依赖、FamilyRouting/TargetedReview、重试、多 Provider、自动降级、双 lane、Prompt 评测闭环、表/Service 复用、阶段 Gate 和回滚合同。
- 文档固定五个 Family（专项家族）：胸腔、腹腔、四肢骨关节、轴骨骼、头颈；FamilyRouting 保持确定性、零模型调用，TargetedReview 最多一次视觉调用并输出新的完整病例结果。
- 修正 Prompt 语义为“一份冻结完整 XRay Prompt 正文、Primary/Targeted 两种运行模式”，不引入旧式多 Prompt 家族动态选择。
- 明确自动降级沿用 `single（单并发执行）`，双通道沿用 `race（并发竞速）`；不新增 fallback execution mode、RetryService、FallbackService、VoteService 或 Lane 表。
- 更新 `docs/refactor/README.md` 的 21 号入口和当前 D5 状态摘要。
- 更新 durable handoff（持久交接）的 snapshot、decisions、backlog、risks、work-log 和 validation，使新会话不会把七项能力误读为永久不在范围。
- 本轮没有修改业务代码、数据库模型/字段、迁移、测试脚本或运行环境。

## 2026-08-25 — 完整 XRay AI/Prompt 链路辩证审查

- 只读审查 22 号完整实施文档、14 号专项设计和当前 Stage/Prompt/Gateway/Reconcile 代码，并使用独立探子核验真实调用链与历史文档漂移。
- 总体判断：现有数据表和顶层 Service（服务）按事实所有权划分基本合理；复杂度主要来自把全部可选能力绑定为一个完成定义，以及 `AIRequestService（AI 请求服务）` 内部职责集中，而不是缺少更多表或 Service。
- 定位两个直接阻断：22 号 FamilyRouting 可输出 `review_required` 与“不修改医学结论”冲突；v2 Targeted command 未传 `family_key/focus_key`，启用后会触发 `targeted_prompt_selection_missing`。
- 定位四项需收敛的设计边界：三类权威、技术覆盖与医学可评估性、Targeted 失败回退 Profile、一份 Prompt 正文的非永久性。
- 建议把完成状态拆成核心诊断链、医学基线和逐项可选能力资格；先做真实 Primary 与医学 Failure Bank，再让 Prompt/模型优化和 Targeted 由证据驱动，Fallback/Race 由失败率、SLA 和成本驱动。
- 本轮未修改业务代码、数据库、迁移、测试脚本或现有架构文档；只更新 durable handoff（持久交接）记录。

## 2026-08-25 — OSS 配置事实澄清

- 仅核验当前 `.env（环境配置文件）` 中 `ALIYUN_OSS_ACCESS_KEY_ID`、`ALIYUN_OSS_ACCESS_KEY_SECRET`、`ALIYUN_OSS_ENDPOINT`、`ALIYUN_OSS_BUCKET` 是否存在且非空，未读取、输出或记录任何配置值。
- 确认 `apps/backend/core/config.py（运行配置）` 已将四项 `ALIYUN_OSS_*（阿里云对象存储配置）` 映射至现有 OSS Runtime（对象存储运行时）字段。
- 更新 21 号完整能力文档与 handoff（交接）状态：OSS 静态配置已准备，不再重复增加配置；E1 仍需完成真实 Bucket 权限、上传/读取/签名/加密及端到端运行资格化。
- 继续只输出配置存在性和非敏感解析状态：当前 `.env` 未显式包含 RabbitMQ/AI Gateway（消息队列/AI 网关）门禁项；最终运行配置的 Broker/AI Gateway（消息队列/AI 网关）开关均关闭，AI 密钥解析和响应加密模式均禁用。没有修改 `.env` 或任何运行环境。

## 2026-08-25 — 旧环境对比与当前配置缺口审计

- 按用户授权脱敏读取旧 `vet-platform/.env`：只比较键名、是否非空和同名值是否一致，不输出密码、Token、完整 Endpoint 或 Bucket。
- 确认当前与旧环境的 MySQL、Redis、RabbitMQ、OSS 同名基础连接配置一致；旧环境没有当前所需的 Runtime/Admin JWT、Nacos Prompt Source、AI Gateway 安全门禁或资格化签名配置。
- 不迁移旧 `GEMINI_API_KEYS`、Mongo、OSS STS/Role、旧智能路由、裁剪、评测和 Worker Pool 配置；当前 Provider Endpoint/Model/Key 继续由数据库 Connection/Config 与 Secret Reference 表达。
- 用 `apply_patch` 修改被 Git 忽略的本地 `.env`：主库名为 `ms_image`；新增 `PROJECT_ENV=development`，显式保留 `BROKER_ENABLED=false`、`AI_GATEWAY_ENABLED=false`、`AI_GATEWAY_SECRET_RESOLVER_MODE=disabled`、`AI_GATEWAY_RESPONSE_ENCRYPTION=disabled`。
- 脱敏实连验证 Redis PING、RabbitMQ 仅连接、主 MySQL `SELECT 1`、OSS Bucket 信息读取均成功；没有声明队列、发送消息、上传或删除对象。
- 只读检查确认 `ms_image_eval` 不可连接；主库无 `alembic_version` 和 `ai_config_record`，三张既有 AI 表有旧数据但缺当前 ORM 关键字段。因此没有执行 Alembic upgrade，也没有开启 Broker/Gateway。
- 根据用户“没有的迁移过去”要求，进一步迁入旧环境与当前 Settings 同名且语义兼容的 `APPLICATION_HOST`、`AUTH_DOMAIN`、`LOG_PATH`、`GUNICORN_ERROR_LOG_PATH`；旧 `/www` Gunicorn 日志路径在当前 Mac 不存在，因此按相同用途适配到 `/Users/mozhicheng/workspace/logs/gunicorn_error.log`。
- 迁移后自动比较确认旧 `.env` 中当前 Settings 同名支持的键已无缺失；仍不转换旧 `GEMINI_API_KEYS`，因为当前数据库尚不能提供冻结 Connection 的 `secret_ref` 身份。

## 2026-08-25 — 完整 XRay AI 与 Prompt 开发指南

- 新建 `docs/refactor/22-xray-full-ai-prompt-chain-development-guide.md`，以当前源码事实为起点，展开完整在线总图、六个平面、九类 Service/评测合同、五个 XRay Stage、Prompt 生命周期、Logical Call/Physical Attempt、Retry、Multi-Provider、Fallback、Race、表关系、失败语义、准确率闭环和完成标准。
- 文档明确区分 `CODE_IMPLEMENTED（代码已实现）`、`RUNTIME_QUALIFIED（运行时已资格化）` 和 `MEDICALLY_VALIDATED（医学效果已验证）`；未把当前 transport/attempt（传输/尝试）代码骨架描述为完整 Provider 链或医学放行。
- 更新 `docs/refactor/README.md` 增加 22 号实施权威入口，并更新当前状态导航。
- 更新 `AGENT_SESSION_PROMPTS.md` 增加可直接复制的“完整 XRay AI 与 Prompt 链路开发会话”当前入口；22 号文档第 17 节保存完整版本。
- 更新 `AGENT_HANDOFF.md`、snapshot、decisions 和 backlog 的当前指针；本轮未修改业务代码、数据库字段、迁移、测试脚本或运行环境。

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
