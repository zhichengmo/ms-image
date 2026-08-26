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

| 2026-08-26 | 方案二 XRay 猫/犬 Primary Prompt 本地合同 | `PromptRenderer.validate_template/render`、`PromptMessageAssembler.assemble`、`test_ai_prompt_control_plane_contracts.py` | PASS | 猫/犬均仅声明 `SAFE_STUDY_CONTEXT_JSON`、`OUTPUT_SCHEMA_JSON`；合同测试最近一次 `42 passed, 1 warning`；未输出正文、Secret 或病例数据。 |
| 2026-08-26 | Nacos XRay 猫/犬 Primary 发布与管理端回读 | qj-nacos：两个目标 `1.0.0`/latest 预检为 not found；`POST /v3/admin/ai/prompt`；admin detail | PASS | 新建 `ms-image.x-ray.primary.cat.zh-CN@1.0.0`（SHA `0be1…96b64`）与 `ms-image.x-ray.primary.dog.zh-CN@1.0.0`（SHA `b394…98022`）；admin detail 的身份、版本与 SHA 一致。 |
| 2026-08-26 | Nacos runtime 与 ms-image source 回读 | qj-nacos runtime exact/latest；`NacosPromptSourceClient -> parse_nacos_prompt_payload -> PromptRenderer -> PromptMessageAssembler` | PASS | 两个候选均 exact/latest/source/render/message 一致；此项只证明 Nacos Prompt 获取基础链，不证明完整 Worker 或医学有效性。 |
| 2026-08-26 | 本轮未运行范围 | MySQL import/Config compile-activate/Task Snapshot/Outbox/Broker/Worker/OSS Provider/医学 Gold | NOT RUN | 当前优先 P0/P1/E1 工程 AI 链；Nacos 发布不替代完整 Worker 或医学验证。 |

| 2026-08-26 | `pymysql` 只读查询 `information_schema.tables`（当前 `.env` 的 `ms_image`） | 通过连接；仅发现目标集合中的 `session_record`，未发现 `pet_profile`、`study_record`、`task_record` | 未写库；真实 `session_record` 是遗留聊天记录结构，不能作为 Runtime 基线 |
| 2026-08-26 | 只读审计 `ms-ai-fast` 宠物档案 migration `20260706_0001`、`20260721_0011`、`20260721_0012` | 不能直接搬迁：链起点/依赖与 ms-image 不同，且 0001 包含非本切片表 | 未生成或运行任何 ms-image 迁移 |
| 2026-08-26 | `python` + `mysqldump --single-transaction --quick --routines --triggers --events --hex-blob --add-drop-table` | PASS | 生成全量备份 `/Users/mozhicheng/workspace/code/cy-code/ms-image-db-backups/ms_image-20260826T102227Z.sql.gz`，raw SQL SHA-256 `88d2035fc113af21e6a995ef3990301f3aef13b51a2bccc1084ba7009e897dbe`。 |
| 2026-08-26 | information_schema 表盘点 + FK/View/Routine/Trigger/Event 查询 | PASS | 清理前 `ms_image` 45 张表；未发现 FK、view、routine、trigger、event。 |
| 2026-08-26 | `rg` 精确表名引用审计 + SQLAlchemy `Base.metadata` 对比 | PASS | 当前代码目标模型 20 张；DB 中仅 4 张同名表，且同名表列结构不兼容；14 张候选空表无当前代码引用且不在模型中。 |
| 2026-08-26 | DROP 前精确 `COUNT(*)` + `SHOW CREATE TABLE` 元数据保存 + `DROP TABLE IF EXISTS` | PASS | 删除 14 张精确 0 行空旧表：`ai_message`、`xray_validation_run`、`api_request_stats`、`xray_validation_consistency`、`xray_validation_prompt`、`ai_agent_recent`、`ai_conversation`、`x_ray_analysis`、`xray_v3_accuracy_run`、`ai_execution_trace`、`xray_validation_step`、`ai_execution_attempt`、`user_usage_account`、`ai_output_schema`。 |
| 2026-08-26 | 清理后 information_schema 复核 | PASS | `ms_image` 剩余 31 张表；14 张清理表均确认不存在；目标 Runtime 表仍缺失。 |
| 2026-08-26 | 真实 Worker / OSS / Broker / Provider / 医学验证 | NOT RUN | 本轮仅数据库备份、只读审计与空旧表 DDL 清理；没有运行完整 XRay 任务链。 |
| 2026-08-26 | `gzip -t /Users/mozhicheng/workspace/code/cy-code/ms-image-db-backups/ms_image-20260826T102227Z.sql.gz` | PASS | 备份 gzip 文件完整性校验通过；未做恢复演练。 |
| 2026-08-26 | 用户确认后按 `Base.metadata` 保留边界删除非 Runtime legacy 表 | PASS | DROP 前保存清理元数据 `/Users/mozhicheng/workspace/code/cy-code/ms-image-db-backups/ms_image-cleanup-legacy-non-runtime-20260826T103657Z.metadata.json`；删除 27 张非当前 ORM 表；`ms_image` 表数 31 -> 4。 |
| 2026-08-26 | 清理后表集合/行数/ORM 对比复核 | PASS | 剩余 `ai_api_connection`(96)、`ai_model_pool`(19)、`ai_prompt_template`(375)、`session_record`(5772)；`DB_NOT_IN_MODELS=[]`；目标 Runtime 多表仍缺失，4 张同名表列结构仍不兼容。 |
| 2026-08-26 | 删除剩余 4 张同名旧结构表前 metadata 保存 + `DROP TABLE IF EXISTS` | PASS | metadata `/Users/mozhicheng/workspace/code/cy-code/ms-image-db-backups/ms_image-cleanup-remaining-old-structure-20260826T121615Z.metadata.json`；删除 `ai_api_connection`、`ai_model_pool`、`ai_prompt_template`、`session_record`。 |
| 2026-08-26 | 清理后 information_schema 复核 | PASS | `ms_image` 表数为 0；当前没有任何物理表。 |
| 2026-08-26 | 快速上线 Prompt 方向审计 | 读取 handoff、截图任务历史、本地 session 摘要；`rg`/`sed` 定位 `prompt_source.py`、`prompt_commands.py`、Prompt import/compile 代码 | HANDOFF-ONLY / NO RUNTIME | 未改业务代码、未改 Nacos/DB/环境；仅更新交接记录，结论为方案建议，不代表 Worker 或医学验证。 |
| 2026-08-26 | `Base.metadata.create_all` on empty `ms_image` + `alembic stamp head` | PASS | 创建当前代码 20 张模型表并写入 `alembic_version=20260824_02`；没有生成新迁移脚本。 |
| 2026-08-26 | 建表后 information_schema / Base.metadata 对比 | PASS | `ms_image` 21 张物理表（20 模型表 + `alembic_version`）；`model_missing=[]`、`extra_non_model=[]`；关键 Runtime 表均存在且当前 0 行。 |
| 2026-08-26 | 用户澄清后再次只读核验 `ms_image` 与 `Base.metadata` | PASS | 21 张物理表；20 张当前 Model 表全部存在且均 0 行；`model_missing=[]`、`extra_non_model=[]`、`alembic_version=20260824_02`；未再执行 DROP。 |
| 2026-08-26 | 快速上线 Prompt 身份二次架构审查 | `rg`/`sed`/`git log`/`git blame` 核对 22/23 号文档、PromptSource、TaskService、PromptCommand、ConfigCompiler 与既有合同测试 | PASS / ANALYSIS ONLY | 结论由 cat/dog 双壳共用正文修正为唯一 `xray_primary/common`；未改业务代码、Nacos、DB、环境，未运行 Worker/Provider/医学验证。 |

| 2026-08-26 | XRay 接口 species + single common Prompt 代码验证 | PASS | Ruff 5 个修改文件通过；3 个既有 AI 合同测试文件 `91 passed, 19 warnings`；生产文件 compileall 与 `git diff --check` 通过。warnings 为已有 Pydantic/`datetime.utcnow()` deprecation。Nacos/MySQL/Worker/Provider/医学验证 NOT RUN。 |
| 2026-08-26 | 猫/犬冻结合同复核 | `PYTHONPATH=/Users/mozhicheng/workspace/code/cy-code/ms-image python -m pytest apps/backend/tests/test_ai_gateway_attempt_contracts.py apps/backend/tests/test_ai_prompt_control_plane_contracts.py apps/backend/tests/test_ai_prompt_control_plane_models.py -q`; Ruff; compileall; `git diff --check` | PASS | `94 passed, 19 warnings`；仅验证现有代码合同。未运行上游按 session 解析物种、Nacos canonical Prompt、Task/Outbox/Broker/Worker/OSS/Provider 或医学验证。 |

## 2026-08-26 — 猫狗统一继承方案复核

| 检查 | 结果 | 结论边界 |
|---|---|---|
| `PYTHONPATH=/Users/mozhicheng/workspace/code/cy-code/ms-image python -m pytest apps/backend/tests/test_ai_gateway_attempt_contracts.py apps/backend/tests/test_ai_prompt_control_plane_contracts.py apps/backend/tests/test_ai_prompt_control_plane_models.py -q` | `94 passed, 19 warnings` | 覆盖 species 入参/冻结、XRay common exact-only、Prompt safe context、Attempt 状态合同；19 条均为既有 Pydantic / `datetime.utcnow()` deprecation warning。 |
| `python -m ruff check`（6 个本轮 XRay 代码/合同测试文件） | 通过 | 静态检查通过。 |
| `python -m compileall -q`（4 个 XRay 生产文件）与 `git diff --check` | 通过 | 语法及 diff 空白检查通过。 |
| 真实上游 `session_id -> medical_record -> pet_profile -> species -> POST /tasks` | NOT RUN | 当前只验证 ms-image 下游冻结边界；不能声称宠物档案继承已经真实集成。 |
| MySQL -> Outbox -> Broker -> Worker -> OSS -> Platform -> Provider -> Attempt -> Stage -> Report | NOT RUN | `RUNTIME_QUALIFIED` 仍未取得。 |
