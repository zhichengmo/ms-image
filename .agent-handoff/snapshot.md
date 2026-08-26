# 代理交接当前快照

## 当前目标与状态

- 最后更新：2026-08-26
- 工作区：`/Users/mozhicheng/workspace/code/cy-code/ms-image`
- 当前分支：`codex/prompt-runtime-ai-gateway`
- 当前目标：先收口并发布 XRay 猫/犬 Primary Prompt 身份隔离，再在 P0 数据库边界获授权后完成 P1/E1 的真实 AI 任务链；当前不执行医学评测、Prompt A/B 或专项能力开发。
- 当前状态：`MS_IMAGE_CORE_AI_NETWORK_CHAIN_PASSED / FULL_WORKER_RUNTIME_NOT_QUALIFIED / MEDICAL_ACCURACY_UNKNOWN / MEDICAL_RELEASE_NO_GO`。

## XRay 猫/犬 Primary Prompt 候选

- 用户已确定：XRay 是独立模态 `xray`，Nacos module 段为 `x-ray`；Primary 必须按物种分为 `cat` 与 `dog`，XRay 不允许 `default` fallback。
- 已按用户选择的方案二，只读参考 `vet-platform` 的猫 XRay 全图 Prompt（旧 Template `678@1.2.3`）与犬 XRay 全图 Prompt（旧 Template `679@1.3.0`），分别整理候选；没有原样搬运旧变量、旧状态或旧输出 JSON。
- 已创建外部 Nacos 发布物：`ms-image.x-ray.primary.cat.zh-CN@1.0.0`（正文 SHA-256：`0be1b353bc4527ff9d70c8dc871300b7b1dd0f746b7e56e81138bd1d23b96b64`）与 `ms-image.x-ray.primary.dog.zh-CN@1.0.0`（正文 SHA-256：`b394ccb6cbcefd9f12ab8819e1ce7d743de5758cb0896f1734b13d13f3998022`）。
- 严格变量合同仅为 `SAFE_STUDY_CONTEXT_JSON`、`OUTPUT_SCHEMA_JSON`；两个候选均已完成 Nacos admin detail、runtime exact/latest、`NacosPromptSourceClient -> parse_nacos_prompt_payload -> PromptRenderer -> PromptMessageAssembler` 回读。该证据仅资格化 Nacos Prompt 获取基础链，不构成医学基线。
- 历史 `ms-image.ai-pic.xray-primary.default.zh-CN@1.0.0` 与 `ms-image.x-ray.primary.default.zh-CN@1.0.0` 仍在 Nacos；未经用户明确授权不删除，但禁止导入、激活或冻结至 XRay Task。

## P0/P1 当前事实与阻断

- P0 只读连接 `ms_image`：MySQL `9.3.0`、45 张物理表、无 `alembic_version`。有数据的 `ai_prompt_template`（375）、`ai_api_connection`（96）、`ai_model_pool`（19）、`session_record`（5772）同名但与 Runtime ORM/迁移不兼容；`ai_config_record`、Task/Stage/Outbox/Call/Attempt/Report 等目标表不存在。当前禁止在旧库执行 `alembic upgrade head`。
- AI/Prompt 运行代码与 `ms-ai-fast` 同语义：`GatewayClient` 仅使用 `AI_PLATFORM_OPENAI_BASE_URL + AI_PLATFORM_API_KEY`；旧 Secret Resolver、Gateway Adapter、response store、`AI_GATEWAY_*` 和 `MS_IMAGE_AI_SECRET_*` 生产链均已删除。Worker 只从 Task Snapshot 读取冻结 Prompt/Config，不读 Nacos latest。
- 当前本地非敏感 Settings 核验：`Settings.Config.env_file` 指向 `.env-01`；`.env` 与 `.env-01` 均没有非空 `AI_PLATFORM_OPENAI_BASE_URL` / `AI_PLATFORM_API_KEY`，本进程 `settings.ai_platform_configured=False`。OSS Settings 为 ready、Broker enabled、MySQL DB configured，但这不构成 Worker 可调用 Platform 的证据。不得恢复旧 `AI_GATEWAY_*` 配置；应将上述两个现有 ms-ai-fast 配置安全注入真实 imaging Worker 启动环境。
- OSS signer 已限制 profile/object/version/hash/size/MIME、HTTPS host allowlist 和 30–900 秒 TTL；隔离对象的本机 PUT/HEAD/Worker GET/signed GET/cleanup 曾通过。Provider 外部读取短签名 URL 仍为 `UNKNOWN`。
- unknown Attempt 不盲目重发：默认 `UnsupportedProviderAttemptLookup` 仅重排原请求对账；尚缺真实 Platform/Provider 原请求查询合同和有界终态策略。
- 未被运行路径写入的 legacy `response_object_ref_json` 仍在 AI Call/Attempt 模型、DAL 和未部署 migration 中；删除/兼容必须等待 P0 数据库方案和明确迁移授权。

## 本轮验证

- XRay cat/dog Prompt 身份合同、XRay 无 `default` fallback，以及 Jinja 注入 JSON 的 `$schema`/`$value` 渲染兼容已由 `test_ai_prompt_control_plane_contracts.py` 覆盖；最近一次为 `42 passed, 1 warning`。提交前需重跑。
- 未写 MySQL、未导入 Prompt、未编译/激活 Config、未创建 Task Snapshot；未运行真实 Outbox/Broker/Celery/Worker、Provider 外网 signed GET、同一冻结 Task 全链或医学评测。

## 下一动作与边界

1. 复核当前 XRay 猫/犬 Prompt 改动、重跑合同测试、更新交接资料并提交推送；不把 Nacos 基础链误报为完整 Worker 链。
2. 用户明确选择 P0：独立 Runtime 数据库，或旧 `ms_image` 的备份/兼容/baseline/stamp/rollback 方案并授权迁移。此前不建库、不迁移、不改表。
3. P0 就绪后，使用已有 `PromptImportService` 分别导入上述 cat/dog **指定版本**，编译不可变 Primary Config 并在控制面审计后激活；Worker 仍只使用之后冻结的 Task Snapshot，绝不读取 Nacos latest。
4. 用户/部署环境将 `AI_PLATFORM_OPENAI_BASE_URL` 与 `AI_PLATFORM_API_KEY` 成对注入实际 imaging Worker 进程（不写入数据库、Nacos、Task Snapshot、日志或交接材料）；然后只读确认 Worker `Settings` 的 presence，不输出值。
5. 两项前提具备后，以同一冻结 Task 采集 MySQL -> Outbox -> Broker -> Worker -> OSS -> ms-ai-platform -> Provider -> Attempt -> Stage -> Report 的脱敏证据；unknown、取消、重复投递和迟到结果另行验证。
6. 当前用户优先级是先完成 P0/P1/E1 的工程 AI 链，不执行 M1 医学评测、Q3 Prompt A/B、TargetedReview、FamilyRouting、Retry、Fallback 或 Race；Python 不得改写 `normal / abnormal / review_required / non_diagnostic`，不恢复 `file_asset`，不删除 v1 链。
