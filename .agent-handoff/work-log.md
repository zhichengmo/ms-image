# 当前工作日志

## 2026-08-31 — R4A Evaluation 独立数据库与基础设施烟测

- 从 `e452b34` 建立 `codex/xray-evaluation-r4a`，严格限制在 Evaluation metadata/DB/Alembic/readiness/Compose/Fake scorer 基础设施；未进入 Dataset、Gold、真实 Runner、M1、Prompt 或医学规则。
- 新增 `EvaluationBaseModel`/`EvaluationRecordBase`，四个 Evaluation ORM 已从在线 `BaseModel.metadata` 完全移出；独立 metadata 精确为四表且保持 opaque `VARCHAR(64)` 单列主键、无 FK/enum/tenant。
- 新增 `alembic_evaluation.ini`、独立 migration env 与 `20260831_eval_01`；空库、完整 adoption、部分 schema、额外 constraint、空/非空 downgrade 门禁均已真实验证。
- 新增在线 cleanup revision `20260831_01`；临时库证明非空 fail-closed、空表删除和 downgrade 空结构恢复。正式主库四张历史空表在 0 行复核后删除，主库 revision 现为 `20260831_01`。
- 正式创建 `ms_image_eval` 并迁移到 `20260831_eval_01`。Evaluation Control `/health`、`/readiness` 真实 200，database/schema/JWT 三项均 ready。
- 真实启动单 Relay、单 Worker；确认同 broker 的其他 `scheduled` 节点不消费 `evaluation.job.execute`。使用既有 completed Task/Report 导出非医学 smoke Job，Job completed、Run succeeded、5 个 Artifact ready 且 OSS HEAD 均存在。
- Fake scorer 的 `expected_status` 明确标为 schema sentinel，不读取 Artifact 正文或医学指标；保持 `MEDICAL_ACCURACY_UNKNOWN / MEDICAL_RELEASE_NO_GO`。
- 修复两个真实资格化缺陷：Backend 镜像补入 Evaluation Alembic 资产；Evaluation async URL 使用 `URL.create()`，特殊字符密码 round-trip 通过。
- 停止 Evaluation Control/Relay/Worker，清理临时数据库，运行目录移入系统废纸篓；正式评测库和烟测审计记录保留。
- 验证：backend `240 passed, 41 warnings`；Ruff、compileall、Evaluation Alembic current/check、Compose 四 profile、81 route/98 Postman、JSON、diff check 通过。Docker daemon 未运行，镜像 build 阻断；在线主库 `alembic check` 仅被既存 `secret_ref` 注释漂移阻断，因此未记录最终 R4A qualification。

## 2026-08-31 — Anatomy Localization v1 本地收口与静态资格门

- 在 `codex/xray-anatomy-localization-v1`、HEAD `ef15dea` 的既有脏工作区上完成本地实现收口；保留 `.agent-handoff/archive*`、tracked archive index 和根目录 `postman/`，未恢复、删除、暂存或提交。
- 实现严格限定为猫狗 2–5 图 Anatomy Localization：1 Task、2 Stage、1 AI Stage、1 Logical Call、单 primary lane、1 Attempt、一次批量 Provider 请求意图、normalized bbox、Task completed、no Report。
- 新 Stage handler 只生成 `StageExecutionPlan` 并消费 accepted AICall；既有 `AIRequestService` 继续拥有网络、Call/Attempt、图片、receipt、Schema/技术校验和持久化。Gateway、race/Lane/Winner/Attempt/reconcile 实现未改。
- Prompt Source 接通猫狗 exact Nacos Data ID/variant；Config compile/frozen verify 增加 Localization Profile/Prompt/Schema/预算精确合同；查询由现有 `TaskService` 复用现有 DAL 完成完整 fail-closed 血缘校验。
- 扩展现有 `run_e2e_local.py`，未新建 Harness。完成 70 focused、311 full tests、Ruff、compileall、Prompt/Schema/label、Config preview/verify、CLI、Alembic 只读和 diff check。
- 只读回查两个 Nacos exact `1.0.0` Data ID、两个 Prompt identity 和两个 Config identity 均 absent；回读实时 ModelPool/Connection/Platform 非敏感身份与 SHA。未发布 Prompt、未 import/validate、未创建/激活 Config、未调用 Provider。
- 当前允许记录 `ANATOMY_LOCALIZATION_V1_CODE_IMPLEMENTED` 与 `ANATOMY_LOCALIZATION_STATIC_VALIDATION_PASSED`；真实八格和单 Logical Call Runtime 资格仍未授权、未执行。

## 2026-08-31 — Anatomy Localization v1 控制面完成与 Runtime 前置阻断

- 在用户明确授权后完成猫狗 exact Nacos `1.0.0` Prompt 发布/回读、Prompt import/validate、两个不可变 Localization Config compile/create/validate/activate；Prompt/Schema/Label/ModelPool/Connection SHA 对账通过，diagnose active Config 集合未改变。
- 临时 AI Control 使用进程内 Admin secret 完成生命周期后停止；secret/token 未输出、未持久化。
- 启动唯一 `run_local_chain.sh`，验证 API health/readiness、Relay heartbeat、Worker concurrency=1、consumer=1、Beat/reconcile scheduler=0。
- 首个 `cat-02` Harness 命令在 `load_case_manifest()` 阶段因缺少 `MS_IMAGE_XRAY_DATA_ROOT` 返回失败；该阶段早于 token、Runtime client 与 `run_once()`，因此未创建 Task/AICall/Attempt、未调用 Provider，未产生 evidence 文件；仓库外临时空目录随后移除。
- 按用户既定“任一 manifest 失败即停、不重复”合同，未补环境重跑，也未进入其余七格。随后停止 launcher；8002/8010、Runtime/Relay/Worker 与 lock 均已清理，未影响 RabbitMQ 或其他项目进程。
- 仓库、当前 shell 和常用 `.env` 均未提供数据根目录；全盘只读搜索约 60 秒无结果后终止。下一次运行需用户提供路径并明确允许新尝试。
- 本轮未修改业务代码、Prompt/Config 版本、ModelPool/Connection、migration、Docker、Git stage/commit/push 或受保护 archive/postman。

## 2026-08-31 — Anatomy Localization v1 X-Ray 数据根目录只读资格检查

- 用户提供 `/Users/mozhicheng/workspace/documents/X光_没问题_全量过滤` 后，只读核对八份 `cat/dog × 2/3/4/5` manifest；直接调用现有 `load_case_manifest()`，8/8 均通过路径、SHA256、size、JPEG/content type、sequence 和 2–5 图数量门禁。
- 目标集合共 28 张且 28 个 SHA 均唯一；Pillow `verify()+load()` 28/28 成功，尺寸范围 `624×1080` 至 `2100×2088`，无空文件、损坏、零尺寸或内容重复；目标文件无 symlink，根目录可读。
- 只读视觉抽样猫胸腔与犬肌肉骨骼代表图，确认属于可辨识 X-Ray；未做疾病、bbox 或医学准确率判断。
- 结论：该目录可直接作为下一次资格化的 `MS_IMAGE_XRAY_DATA_ROOT`。manifest 仍为 `engineering_candidate`、projection=`UNKNOWN`，不能升级为 Dataset/Gold/医学证据。
- 本轮未启动 Runtime/Relay/Worker，未创建 Task/AICall/Attempt，未调用 Provider，未写 evidence，未修改业务代码、数据文件或受保护 archive/postman。新的八格尝试仍等待用户明确允许。
- 尝试按项目规则派发 3 个 `default` 只读子代理，但当前默认角色配置请求了模型不支持的 reasoning 档位，3 次均在创建前失败；`list_agents` 确认只有主代理运行，最终由主线程完成核验。

## 2026-08-31 — Anatomy Localization v1 `cat-02` 真实资格化失败与停机收口

- 用户明确授权使用 `/Users/mozhicheng/workspace/documents/X光_没问题_全量过滤` 从 `cat-02` 重新开始八格；运行前 exact 回读 Nacos Prompt、Prompt receipt、Localization Config、ModelPool、Connection 和 frozen Config，关键 SHA 均无漂移。
- 启动唯一 Runtime 拓扑并确认 API health/readiness、单 Relay、单 Worker、consumer=1、Beat/reconcile scheduler=0；随后以 `MS_IMAGE_XRAY_DATA_ROOT` 运行 `engineering-candidate-cat-02`。
- 本轮创建 Task `c9f0ddb948444be1aa3f28aee0d29e89`、Logical AICall `4836bebc9a3f42f49587220308c59f4c` 和 Physical Attempt `7a3053aedc484bc191cb3106703dbc09`；2 个 StageCheckpoint、1 provider Stage、1 primary lane、1 Attempt，requested/sent/receipt 均为 2。
- Provider `POST /api/v1/chat/completions` 返回 HTTP 200；通用 JSON Schema 通过后，Localization 技术 validator 以 `anatomy_localization_image_lineage_mismatch` fail-closed。Task、AICall、Attempt 和 Localization Stage 均 failed，winner 为空；Task 保持 `ai_medical_status=not_produced`、`current_report_id=null`。
- 查询 `/anatomy-localizations` 返回 409；Report current 为 null、history 为空。当前失败路径未持久化 rejected parsed payload、Provider request ID 或 response SHA，因此未猜测具体 lineage 漂移字段，也未修改 Prompt、Schema、Config 或 validator。
- 严格执行 stop gate：未重试 `cat-02`，未运行其余七格。保存仓库外脱敏 evidence `/tmp/ms-image-anatomy-localization-r4-20260831.OgbG1e/cat-02-failure-20260831T123942Z.json`，SHA256 `1fa6698e3441c296c504912ec9f85d126a9c44198ac22dd935122722004985a4`。
- 正常停止唯一 launcher；8002/8010、Runtime/Relay/Worker、launcher lock 均清理，RabbitMQ 主队列和 DLQ 为 0 ready/0 unacked/0 consumers。既有 aiomysql teardown warning 继续留在独立 backlog。
- 本轮真实矩阵结论为 `XRAY_ANATOMY_LOCALIZATION_2TO5_RUNTIME_QUALIFICATION_FAILED`；单个失败病例满足单 Call/Attempt 拓扑，但成功八格矩阵未完成，不能记录 `ANATOMY_LOCALIZATION_SINGLE_LOGICAL_CALL_CONFIRMED`。

## 2026-08-31 — `cat-02` lineage 失败现有证据穷尽审计

- 从 online DB 只读回读 Attempt 的 request ID、trace ID、provider idempotency key、sent manifest SHA 和 image count；`provider_request_id`、`response_sha256` 均为空。查询后显式 dispose online/evaluation engines，未写数据库。
- 复核 `AIRequestService` 与 `GatewayClient`：上述关联键随 payload metadata 和 `Idempotency-Key` / `X-Request-ID` / `X-Trace-ID` 发给下游，因此若存在非公开远端审计，可由运维方按这些键检索。
- 使用 Task/Call/Attempt、request/trace/idempotency key、错误码和 `2026-08-31T12:39:42Z` 附近时间窗搜索 `/tmp`、`/var/tmp`、用户与系统日志、仓库、`ms-ai-fast/logs` 和 macOS unified log，均无本轮请求/响应命中；本机 `ms-ai-fast` 日志修改时间早于本轮调用。
- 只读检查当前 AI Platform `/openapi.json`：公开接口没有 request/audit/trace/log 查询能力；没有调用 completion 或 Provider。
- 源码审计确认 definite validator rejection 只把错误码、receipt、sent manifest SHA 和 image count 传到失败落库；Provider request ID、response SHA、usage、被拒绝 parsed result 和字段 diff 在此路径丢失。
- expected receipt 的两张图 lineage 完整，Localization safe context 的 rendered messages 中对应 image ID、series ID、manifest SHA 和 `UNKNOWN` projection 均按预期出现；只能确认 Provider 返回至少一个 lineage 值不一致，无法诚实确认具体图片或字段。
- 本轮未修改业务代码、Prompt、Schema、Config、数据库或运行环境，未重发 `cat-02`，未运行其余七格。下一步改为等待用户审核最小失败可观测性改动。
- 继续只读检查 ORM 与 failure finalizer：AICall/Attempt 已有 provider request ID、response SHA、actual model 字段，Attempt 已有 usage JSON；因此 Provider 摘要落库不需要新字段或 migration。
- 评估不保存原始值的字段级定位方案：将 2–5 图 ordinal 与 5 个 lineage 字段组合为有限稳定错误码，最长 60 字符，可直接使用现有 `error_code VARCHAR(80)`。这避免挪用 parsed result、usage 或 object-ref JSON 字段。
- 建议的审核 write set 收紧为 Localization validator、Gateway definite-response exception、AIRequestService failure finalizer、Worker 传递和既有 gateway contract 测试；仍未实施代码。

## 2026-08-31 — Anatomy Localization 最小失败可观测性实施与静态收口

- 经用户明确授权，在既有 Localization 实现上完成无 migration 的最小失败可观测性；未调用 Provider、未启动 E2E/Runtime、未写 Nacos/Config、未执行 Docker、未 commit/push。
- 将 Localization 逐图 lineage 联合错误拆为 `anatomy_localization_image_<ordinal>_<field>_mismatch`，字段仅限 `image_id/series_id/sequence_no/projection/series_manifest_sha256`；receipt 自身非法继续 fail-closed 为 `anatomy_localization_source_receipt_invalid`，不保存 expected/actual 原值。
- 扩展 `GatewayDefiniteResponseError` 传递已取得的 provider request ID、actual model、usage 和 response SHA；`AIRequestService` 只在三项核心摘要齐全时附加，HTTP rejection、Gateway parse failure 和 unknown delivery 不伪造摘要。
- `finalize_attempt_failure()` 对摘要做长度、lowercase SHA、Mapping 和 definite/unknown 一致性校验；Attempt 写入四项既有审计列，无 winner 的 AICall 写入 request ID/model/response SHA。未写 rejected `parsed_result_json`，未改变 failed/winner/race/reconcile 语义。
- Worker 只把 definite-response exception 的摘要转交现有 finalizer；没有新增服务、Gateway、表、字段或 migration。
- 补齐字段级错误、Worker 传递、finalizer 持久化/负例以及 Localization 技术校验拒绝仍保留 Provider 摘要的测试。初次从 `apps/backend` 运行 pytest 因缺少根路径而收集失败，随后按仓库既有 `PYTHONPATH=.` 入口重跑通过；未为命令环境问题修改代码。
- 验证结果：12 focused passed、相关合同文件 256 passed、后端全量 328 passed；Ruff、compileall、`git diff --check` 全部通过。
- 最终意义审查确认改动只提升未来失败可观测性，不修复或重新解释旧 `cat-02`；旧响应具体漂移字段仍为 UNKNOWN，新的 Provider 尝试继续等待用户明确授权。

## 2026-08-31 — 启用最小可观测性后的新 `cat-02` 单次资格化

- 按用户授权重新从 `cat-02` 开始，但严格只运行一次；运行前 exact 回读 Nacos Prompt、冻结 Config、Schema、Label、ModelPool、Connection、Pipeline 和预算，未发现漂移。
- 使用现有唯一 launcher 启动 1 Runtime API、1 Relay、1 Worker、concurrency=1、consumer=1、Beat/reconcile=0；Runtime health/readiness 均为 200，RabbitMQ 主队列/DLQ 初始为空。
- 新 Task `917f9c5498bc4fdea26bb6f2993875f` 创建 2 个 StageCheckpoint：`study_preparation:v1` completed，`anatomy_localization:v1` failed；只创建 Logical AICall `69233e53112c4c4da69319d0d7365aab` 和 Attempt `06f242e1d3a4417a97b28a08d9a67db3`，`attempt_no=1`、`reconcile_count=0`。
- requested/sent/receipt 均为 2；Provider HTTP 200，request ID `chatcmpl-1788192611`，actual model `gemini-3.5-flash`，response SHA `4664c380cd38352a017f085538fbbe80c2afb90978151fcad0edd4dc82e851fb`；Provider 未返回 usage。
- 通用 JSON Schema 通过后，冻结 Localization validator 精确拒绝 `anatomy_localization_image_1_projection_mismatch`。AICall/Attempt/Localization Stage/Task 全部 failed，winner 和 accepted parsed result 均为空；未保存 Provider body 或 rejected parsed result。
- Task 保持 `report_required=false`、`ai_medical_status=not_produced`、`current_report_id=null`，Report count=0。
- 遵守失败即停：未重试 `cat-02`，未运行 `cat-03/04/05` 或 `dog-02/03/04/05`，未增加 Attempt、修改预算或放宽 validator。
- 正常停止 launcher；8002/8010、Runtime/Relay/Worker、lock、主队列和 DLQ 均清理。仓库外日志 `/tmp/ms-image-anatomy-localization-rerun-20260831.Vq066r/local-chain.log`，SHA256 `e5cb94820161df8bf7a067b6a25683cd9f178cd6605d359091984ab4646738b5`。
- 本轮没有修改业务代码、Prompt、Schema、Config、数据库结构或迁移；完整八格未完成，结论保持 Runtime qualification failed。

## 2026-09-01 — 项目级防偏移规则启用

- 根据用户确认，将 `docs/ms-image-current-development-contract.md` 的完成度复核、单一 active objective、write set、外部权限、完成门和停止门要求加入本项目 `AGENTS.md`，并同步项目文档中心和 `AGENT_SESSION_PROMPTS.md` 的当前入口。
- 具体 active objective 不写死在 `AGENTS.md`，仍由 `.agent-handoff/snapshot.md` 和用户本轮授权动态决定。
- 未修改业务代码、Prompt/Schema/Config、数据库、迁移、Runtime 或 Provider。
- 复核后补齐 `AGENT_HANDOFF.md` 当前入口指针，并在 `snapshot.md` 明确写出 `Active development objective`；新会话 Prompt 遇到缺失目标时必须停止，不得猜测。
- 统一 `AGENT_HANDOFF.md` 与 `snapshot.md` 的最后更新时间为 2026-09-01，消除新会话恢复时的时间歧义。

## 2026-09-01 — 非分割 X-Ray 全接口与独立 Prompt 架构审计

- 按用户修正后的目标，只读审核 `vet-platform-system` 指定提交 `6d1dd28bfb74143fb903503cdd08ced1f06a4d91`；未把目标仓库当前脏工作树当作历史事实。
- 覆盖截图中的 Token、session-start、submit-chief-complaint、重复上传、batch quality check、gen report 和 medical record 查询；明确排除器官分割提交/状态接口及 mask/bbox/crop/overlay 实现。
- 逐源码追踪旧链逐图 body-part/projection AI、图内 AI+本地 QC 并发、跨图 scheduler、full/system/organ 分析任务、A/B/C Prompt 并发、错误隔离和结果汇合；确认旧报告入口对已完成 segmentation task 有硬依赖。
- 完整阅读旧部位识别、Fusion A/B/C 猫犬 Prompt，确认猫犬输出骨架同构但正常变异、阈值、急症、鉴别和风险说明存在实质差异；未将文件存在误报为 DB Runtime 已绑定。
- 对照当前 `ms-image` Session/Study/Image/Task/Report 接口、Pipeline、Prompt command、Nacos mapping、Config compiler、AIRequestService 和 Prompt 资产；确认当前缺独立 Quality、StudyScreening、SystemAnalysis、ReportGeneration Stage，且 Primary/Targeted 共用同物种 v4 双模式正文。
- 新增 `docs/refactor/31-xray-non-segmentation-ai-stage-prompt-and-interface-audit.md`：提出 Cat/Dog 各 6 个独立 Prompt、逐图 Quality fan-out、A/B 并发、Primary/Targeted/Report 串行汇合、Stage Config binding 和 image subset 合同。
- 文档明确调用代价：Primary-only=`N+4`、Targeted=`N+5`，2–5 图为 6–10 Call；阶段拆分不证明准确率提升。
- 本轮未修改业务代码、现有 Prompt/Schema、Nacos/Config、数据库、迁移、Provider、Runtime、Docker、旧对照仓库或受保护 archive/postman。

## 2026-09-01 — 宠物档案与 `pet-info` 迁移

- 只读审计源仓库 `vet-platform` 的宠物档案、归档恢复、历史记录和 `pets_info` 流程，并按用户授权迁入 `ms-image`；源仓库未写入。
- 新增 `PetProfile`、`PetProfileHistory`、`PetInfo` 模型及对应 Schema、Dal、Service、Runtime endpoint；注册模型、依赖和路由，并复用统一 imaging error rollback/mapping 与现有 `DalBase`。
- 宠物档案支持创建幂等、owner 隔离、查询/分页、部分更新、`state_version` CAS、归档/恢复和逐字段历史；`pet-info` 仅作为猫狗品种资料目录，支持模糊查询与首字母分组。
- 新增并执行 `alembic_migrations/versions/20260901_01_add_pet_profile_and_breed_catalog.py`；目标 `ms_image` 当前位于 `20260901_01 (head)`，物理表 `pet_profile`、`pet_profile_history`、`pet_info` 已创建。
- 三表按目标规则重新创建而非复制旧 DDL：opaque `VARCHAR(64)` 单列主键、无 foreign key、无 enum、无 `tenant_id`、所有列有类型/中文 comment，资源 ID 不进入路径。
- 通过临时、非仓库导入工具和现有三个 DAL 迁入 `pet_profile=5091`、`pet_info=152`、`pet_profile_history=0`；源历史表为 0。确定性 UUID5、source identity、request ID 和导入前过滤保证第二次执行新增 0。
- 已核对 owner 语义；严格转换 64 个 `数字kg` 体重和 27 个已验证旧 OSS host 头像 object key。874 个第三方品种图片 URL 和 152 个区间参考体重未做不可靠转换。
- 跨 schema 核对确认档案/目录 missing、extra、owner、species、status、weight mismatch 均为 0；三表无 FK/enum/tenant/空 comment，主键均仅 `id`。
- 相关 Ruff、compileall、diff check 通过；完整测试使用 `PYTHONPATH=<repo> uv run pytest apps/backend/tests -q` 得到 `328 passed, 45 warnings`。指定 conda 环境缺少 `jinja2` 的首次收集失败属于环境依赖问题。
- `alembic check` 唯一报告本轮前已存在的 `ai_api_connection.secret_ref` comment drift，未混入宠物 migration。未运行真实 HTTP API CRUD/CAS/history 并发 E2E，未调用 Nacos/OSS/Provider，未 commit/push。

## 2026-09-01 — Quality Prompt 发布回读与 Cat/Dog 资格边界收口

- Cat/Dog Quality Prompt 已按 exact-version 发布到 Nacos，未覆盖不可变版本；本轮再次只读回读 `1.0.0`，规范化正文 SHA 与仓库冻结 Markdown 完全一致。
- 现有数据库 Prompt `xray_cat_image_quality@1.0.1`、`xray_dog_image_quality@1.0.1` 均为 `validated`；`xray_image_quality_cat/dog@1.0.0` Config 均为 `active` 且绑定 `xray_image_quality_v1`。
- 只读回读 Cat Task `c1cea89ec55d468fa86f1708360d881f`：Task/两个 Stage completed，1 Logical Call succeeded/accepted，1 Attempt succeeded，2 图 sent，Report count 0；GET Quality DTO 经服务端 lineage 重验成功。
- 只读回读 Dog Study `89573c3f3a5e440784deeb7458232665`：当前 `ready`、revision `610b222e9f034b2a9bde4898b32a055a`、Task count 0；首次 Quality POST 的 HTTP 409 发生在 Task 创建前，未调用 Dog Provider。
- 本轮没有业务代码、Prompt、Schema、Config、validator 或 migration 修改，没有 Provider 调用，没有启动 Runtime/Relay/Worker/Docker。

## 2026-09-01 — 目标诊断链缺失 Prompt 发布到 Nacos

- 按目标阶段级设计盘点 12 个 Cat/Dog Prompt identity；已有 BatchImageQualityReview 2 个，本轮缺失并补齐 StudyScreening、SystemAnalysis、PrimaryCaseAdjudication、TargetedReview、ReportGeneration 共 10 个本地不可变 Markdown 资产。
- 10 个资产通过 UTF-8/换行规范化、Jinja 解析、required variables 精确匹配、Strict renderer 完整渲染、Cat/Dog 固定身份与未声明变量检查。
- 只读确认当前部署真实写入口为 Nacos Admin `/v3/admin/ai/prompt/draft|submit|publish`；此前 `/v3/console/ai/prompt/draft` 的 404 是路由选择错误，不是 Prompt Management 不可用。
- 发布前逐个通过 Client exact GET 与 Admin governance 双重预检，确认 10 个 Prompt key/version 均无 online、draft、reviewing 或其他 metadata。
- 在 namespace `c0cc9e0e-0fed-4faf-bc57-e9bab46a78a9` 逐项创建 `1.0.0` draft 并 submit；当前部署无 Prompt publish pipeline，submit 自动进入 online，未调用 force publish、未覆盖同版本。
- 每项发布后立即 exact GET + governance 回读，status=`online`、latest=`1.0.0`，规范化正文 SHA256 与本地冻结资产全部一致。
- 未执行数据库 Prompt import/validate、Config 创建/激活、Provider、Runtime E2E、Docker；未修改 Pipeline、Handler、Schema、Prompt Source mapping 或业务代码。
- Durable handoff maintenance 使用已安装脚本执行 `--compact-if-needed`：`changed=2 / warnings=1 / unresolved=0`，按合同轮转 1 个旧 work-log 日期段并更新 archive index。


## 2026-09-01 — Quality commit-before-response 真实 HTTP 回归

- 将 Runtime Session/Study/Task/Quality 写 endpoint 切换为 `get_explicit_transaction_session`，并用 endpoint-owned `async with db.begin()` 确保 commit-before-response；未修改 Service 业务编排、Prompt、Schema、Config、validator、Nacos 或表结构。
- 静态验证：4 个 endpoint compileall、Ruff、`git diff --check` 均 PASS；`PYTHONPATH=. pytest -q apps/backend/tests/test_ai_gateway_attempt_contracts.py` 为 `256 passed, 45 warnings`。
- 仅启动 Runtime API；对 ready Dog Study `89573c...` 创建请求，POST HTTP 201 得到 Task `8c854ca7d4f64de2943928accb5dedbb`，POST 返回后无 sleep 的第一次 GET 直接 HTTP 200。
- 取消请求 HTTP 200，紧接 GET HTTP 200 且 `cancel_requested_at` 已持久化；相同 request_id 重放返回同一 Task，证明接口不是只能调用一次。
- DAL 只读核验：Task queued/cancel_requested；Stage 1 queued；Outbox 1 pending；AICall/Attempt/Report 均 0。本轮未启动 Relay/Worker，未调用 Provider。
- Runtime 已正常停止，端口 8002 未监听；关闭时出现既有 aiomysql event-loop teardown warning，作为独立 backlog 保留。
- 归属结论：历史首次 409 属于 ms-image Runtime Task 创建边界，不是 Provider 429；response-before-commit 是有证据支持的推断，历史精确冲突子类型仍 UNKNOWN。


## 2026-09-01 — Quality commit-before-response 追加五次稳定性回归

- 按用户要求在同一 ready Dog Study/Revision 上使用 5 个全新 request_id 连续测试；仅启动 Runtime API，没有启动 Relay、Worker、Docker，没有调用 Provider或写 Nacos。
- 5/5 均为 POST HTTP 201、无等待第一次 GET HTTP 200、cancel HTTP 200、取消后无等待 GET HTTP 200；相同 request_id 幂等重放均 HTTP 201 并返回同一 Task。
- POST 耗时范围 14.28–68.36 ms；立即 GET 耗时范围 4.86–6.83 ms；未出现 409、404、429 或 5xx。
- 5 个 Task：`eddb0a...`、`76b9f1...`、`aad827...`、`53a5ee...`、`066205...`。DAL 逐项核验均为 queued/cancel_requested、1 Stage queued、1 Outbox pending、AICall/Attempt/Report 0。
- 累计初次回归与本轮追加测试为 6/6 PASS；按用户指示，该 Runtime 事务可见性问题关闭。
- Runtime 已停止，8002 未监听；关闭时仍出现既有 aiomysql event-loop teardown warning。

## 2026-09-01 — StudyScreening 代码闭环与静态门完成

- 用户将逐个跑通顺序固定为 StudyScreening → SystemAnalysis → PrimaryCaseAdjudication → TargetedReview → ReportGeneration；当前只处理 StudyScreening。
- 完成 `study_screening:v1` Stage/Profile、Cat/Dog exact Prompt Source、Schema/技术 validator、Quality Task 显式引用和安全冻结、Stage-specific Config binding 与 AIRequestService 解析/冻结校验。
- 专项测试暴露 `build_study_screening_ai_request_command()` 调用 `_base_context(prompt_mode="study_screening")` 时必然触发 `prompt_mode_invalid`；已将该 mode 加入允许集合。
- 新增测试覆盖 Cat/Dog exact mapping、跨物种拒绝、Prompt变量与message context顺序、Stage/Root Profile、Config binding、Quality安全冻结、accepted Call消费和lineage漂移拒绝。
- Focused tests `326 passed, 45 warnings`；Backend全量 `335 passed, 45 warnings`；Ruff、compileall、`git diff --check`通过。
- 复核历史记录发现 Cat/Dog StudyScreening Nacos `1.0.0` 已在“10个目标诊断链Prompt”轮次 online并exact回读；纠正 checkpoint 中“尚未写Nacos”的陈旧描述，后续禁止重复发布。
- 本轮只同步合同与handoff，未写Nacos/数据库，未调用Provider，未启动Runtime/Relay/Worker/Docker，未进入SystemAnalysis。


## 2026-09-01 — StudyScreening Cat Prompt Import 422 精确诊断

- 承接逐个跑通顺序，本轮唯一目标仍为 StudyScreening；先报告完成能力账本，业务代码 write set 为空，Nacos 只读、DB 只读/rollback、Provider/Runtime 禁止。
- 对与公共请求完全相同的 `PromptImportRequest` 做无持久化分步诊断：Schema PASS；exact Data ID 为 `ms-image.x-ray.study-screening.cat.zh-CN`；Nacos fetch FOUND；version=`1.0.0`；content SHA=`a3cede45fbda09f07de16bf0289c9b8604a045499b6c6f369103dfc7634e88a8`。
- `normalize_imported_prompt` 推断 required variables 精确为 `OUTPUT_SCHEMA_JSON`、`QUALITY_RESULTS_JSON`、`SAFE_STUDY_CONTEXT_JSON`；变量 resolution PASS。
- 精确失败为 `PromptImportService._normalize_message_contract()` → `AIControlValidationError(prompt_message_contract_invalid)`。源码 allowlist 只接受 `SAFE_STUDY_CONTEXT_JSON` 与 `PRIMARY_RESULT_JSON`，不接受 StudyScreening 的 `QUALITY_RESULTS_JSON`。
- 只读 DB 回查确认失败 request_id 无 Audit，`xray_cat_study_screening@1.0.0` 仍 absent；Dog Prompt、Stage/Root Config、Runtime、Provider 均未执行。
- 按停止门未修改代码、Prompt、Schema、validator 或配置，未重试写接口，未进入 SystemAnalysis。


## 2026-09-01 — StudyScreening 控制面资格化与首次 Cat Runtime 失败关闭

- 承接已完成的 message-contract 最小修复：只在 `prompt-message-contract.v1` 合法 context key 中加入 `QUALITY_RESULTS_JSON`，并补 safe+quality、缺 safe、重复 key、unknown key 精确回归；Backend 全量 `336 passed, 45 warnings`，Ruff、compileall、diff-check PASS。
- 通过公共 AI Control API 完成 Cat/Dog StudyScreening Prompt import/validate；四个 Cat/Dog Stage/Root Config compile-preview、create/validate/activate，且 Runtime 同源 frozen verify 全部 PASS。Nacos 已发布 `1.0.0` 未重复写入或覆盖。
- Runtime 前调用既有 `TaskService._load_verified_xray_quality_review` 重新验证 Cat Quality Task `c1cea89ec55d468fa86f1708360d881f`；Study/Revision/Manifest/Stage/Call/output SHA 全部与冻结预期一致，2 图、complete。
- 启动唯一 `scripts/dev/run_local_chain.sh` owner，确认 Runtime health/readiness、单 Relay、单 Worker、consumer=1、Beat disabled；仅 POST 一次 Cat diagnose Task `e004c8790df349c28342a98a36a1d856`。
- StudyPreparation completed；StudyScreening 唯一 Logical Call `e3e38850270046d789729521f55cf4e4`、唯一 Attempt `7ec8b073bae44dd09c23f728e5d0d0ed` 向 Provider 发送 2 图，HTTP 200，actual model `gemini-3.5-flash`。
- Provider 响应在 StudyScreening lineage validator 处以 `study_screening_source_projection_mismatch` fail-closed；Task/Call/Attempt/Stage failed，winner 为空，Report count=0，未创建第二 Attempt、未重试。
- 只读核对确认 Safe Context 的 `projection` 与 Quality Result 的 `declared_projection` 均为两项 `UNKNOWN`；validator 要求 Provider source_refs projection 逐字相等。被拒绝 parsed result 未持久化，实际 Provider projection 值保持 UNKNOWN。
- 严格执行停止门：未修改 Prompt/Schema/validator、未提高预算、未进入 SystemAnalysis；Runtime/Relay/Worker 与 launcher lock 已清理。关闭时出现既有 aiomysql event-loop teardown warning。


## 2026-09-01 — StudyScreening projection mismatch 无 Provider 深审

- 按 continuation guard 继续唯一目标 StudyScreening；完成能力账本核对，业务代码 write set 为空，未启动 Runtime/Relay/Worker、未访问 Nacos/DB、未调用 Provider。
- 逐行复核 Cat/Dog StudyScreening `1.0.0` Prompt、`study_screening.v1.schema.json`、safe-context builder、image receipt、lineage validator、Gateway definite failure finalizer 和相关测试。
- 确认 Prompt 未要求 `image_id/sequence_no/series_id/series_manifest_sha256/projection` 从冻结引用逐字复制，也未说明 caller-declared `UNKNOWN` 不得改成 null、归一化值或像素推断值。
- 确认 Schema 允许 `source_refs[].projection` 为 null，但 frozen receipt projection 必为非空 string，后置 validator 严格相等；这是合同漂移，不等于已确认本次 Provider 返回 null。
- 确认 Prompt 未明确要求 source_refs 覆盖全部发送图，validator 则要求 image 集完全相等；这是 projection 修订后可能暴露的第二技术拒绝点。
- 确认 definite technical rejection 不持久化被拒绝 parsed result 或原始响应 ObjectRef，只保留 error code、provider request ID、actual model、usage 和 response SHA；因此首次实际 projection 值继续保持 UNKNOWN。
- 现有测试覆盖 validator 的 `VD → DV` projection drift，但未覆盖 `UNKNOWN + caller_declared`、Schema null 对齐、Prompt 逐字复制与全图 coverage 组合。
- 未修改 Prompt/Schema/validator 或业务代码，未重试 Cat Task，未进入 SystemAnalysis。
- 补充确认 StudyScreening projection mismatch 使用聚合错误码，不含图片 ordinal/字段路径；两图输入无法从已持久化证据定位具体 source_ref。

## 2026-09-02 — StudyScreening 合同冲突联合分析

- 读取启动合同、handoff 当前态和 StudyScreening 相关架构文档，点验 Prompt、Schema、validator、Snapshot→Prompt→receipt→AICall→Stage→下游 Profile 的实际源码链。
- 确认四层合同漂移：冻结输入 projection=`UNKNOWN`、Prompt 未要求精确复制、Schema 允许 string/null、validator 要求与 receipt 严格逐值相等；同时确认 source_refs 全图 coverage 是潜在第二阻断。
- 核验 canonicalization 边界：`AIRequestService` 在持久化前有 receipt，但 `_structured_call_response()` 未向 Stage 暴露 receipt；Stage 当前直接把 `parsed_result_json` 作为 `study_screening_result`。
- 裁决采用 v2 provider/canonical 双边界：AICall 保留最小 schema-valid Provider 输出，Stage 使用 receipt 生成完整 canonical lineage；不改写任何医学字段，不新增表/字段/migration。
- 发现并记录独立下游缺口：`xray_diagnose_study_screening_v1` 只保证执行顺序，`build_primary_ai_request_command()` 未消费 `previous_output.study_screening_result`，完整诊断链尚未语义汇合。
- 本轮未修改业务代码、Prompt、Schema 或配置；未写 Nacos/数据库，未调用 Provider，未运行 Runtime/Relay/Worker/Docker。
- 完成 handoff 收口：归档最早三个 validation section，清理 EOF 多余空行；maintenance compact/check 与 `git diff --check -- .agent-handoff/` 均通过。


## 2026-09-02 — StudyScreening 解决方案收敛

- 在不修改业务代码和外部状态的前提下，复核 v1 validator 全部动态检查、receipt 构造、Prompt safe context 与文档 SourceRef 约束。
- 收敛正式方案为 v2 provider/canonical 双边界：Provider 只承担医学输出与最小 anchor，Stage 从 receipt 生成完整 lineage；AICall 保留 raw，Stage 保存 canonical。
- 明确 Provider anchor 与 canonical 结果不能使用含义不一致的同一合同身份；先独立 Screening Profile 验收，再处理 diagnose Root/Primary 消费。
- 本轮未访问 Nacos/数据库/Provider，未启动 Runtime/Relay/Worker/Docker。

## 2026-09-02 — StudyScreening v2 Cat 真实资格化收尾

- Cat Nacos `2.0.0`、DB Prompt 和独立 Config 已完成 exact/readback/frozen verify。
- 唯一 Task `2c48ad93315145d19faa1f89b47b0d50` completed；1 Call、1 Attempt、Provider 200、accepted、2/2/2、Report 0。
- Provider raw 与 Stage canonical 双边界通过，Provider raw 未被 canonicalizer 原地改写。
- 未运行 Dog、SystemAnalysis 或其他下游；未创建第二 Task/Attempt。
- 清理 AI Control、Runtime、Relay、Worker；仅更新合同和 handoff 状态。

## 2026-09-02 — 假设 StudyScreening 通过后完成 Primary 下游单次验证

- 用户明确要求不再等待 StudyScreening；本轮将其限定为 `ASSUMED_PASS`，使用既有 `experiment/full-chain-local-v1` Config 跳过 Screening，没有修改 Nacos、Prompt、Schema、Config 或业务代码。
- 启动唯一 `run_local_chain.sh` owner；readiness 在 Worker 注册后由初始 503 转为 200，并确认只有一个 imaging consumer、reconcile scheduler disabled。
- 仅执行一次 `engineering-candidate-cat-02` E2E；Task `5c6c5612609a4e438c06e39cc6e2848b` completed，Report `fde7e262df494b559eb27a0c77511bbc` final。
- `joint_primary_reader:v2` 创建 AICall `e4862fdb9ec34e569b7bee94ac0660ca` 与 Attempt `617c327e6ed34e2890ef514313a86fab`；Provider HTTP 200，succeeded/accepted，1 Call/1 Attempt，requested/sent/receipt=2/2/2。
- 两个 Provider source_ref 对 Receipt 的 image_id/series_id/projection/manifest_sha256 全部匹配，Receipt 也与冻结 Snapshot 全匹配；本次未发生后置 lineage rejection。
- 下游 `family_routing:v2` route=`primary_final`；没有 targeted candidate，因此未创建 `targeted_review` Stage；`decision_finalization:v2` completed，owner=`primary`。
- Report 的 source Stage/Call、Task current_report_id 和 final content lineage 一致。Stage `produced` 到 Report/Task `normal` 的差异经源码与 2 个定向测试确认是预期持久化投影。
- 本次 Profile 不含 SystemAnalysis 或独立 ReportGeneration AI；不能把它们记为通过。
- 关闭唯一 launcher owner并核验 8002/8010 空闲、lock absent；没有重试或第二 Task。
- Closeout 时安装版 handoff maintenance 首次报告 validation 超限；随后将最早的完整 2026-08-28 validation sections 原样归档为 `archive/validation-20260902T043031Z.md`，最终 check `warnings=0 / unresolved=0`，diff-check 通过。

## 2026-09-02 — Cat SystemAnalysis 控制面与单次真实资格收尾

- 扩展既有 exact-source Prompt Import 资格集合，纳入 `xray_cat_system_analysis` / `xray_dog_system_analysis`；要求显式 namespace/release/version 并核对回读版本一致性。
- 新增 SystemAnalysis Cat/Dog Prompt Import 合同测试；既有相关后端全量验证 `353 passed, 45 warnings`，Ruff、compileall、diff-check 均通过。
- 完成 Cat Prompt `xray_cat_system_analysis@1.0.0` exact import/validate/readback；创建并激活 Config `bbdd49c799044343a1cc60c5ab9afd4a`，frozen integrity PASS。
- 复用冻结 Quality Task `c1cea89ec55d468fa86f1708360d881f` 与 2 图 Manifest，创建唯一 Runtime Task `4e1165980fde4facae1793e637d77cc7`。
- Provider 单次 HTTP 200；唯一 Call/Attempt succeeded/accepted；Task 与 `study_preparation:v1 → system_analysis:v1` completed。
- 完成门脚本最初错误要求可空 `response_object_ref_json` 与 `accepted_call_id` 必须存在。核对模型与 Handler 后，仅删除 `/tmp` 审计脚本中的额外假设；未修改 Runtime、Prompt、Schema 或 validator。
- 最终完成门 PASS：1 Call、1 Attempt、2/2/2、Schema/合同校验、Stage `source_call_id + system_analysis_result + output_sha256` 持久化、Report 0 全部成立。
- 关闭 Runtime launcher、Relay、Worker 与 AI Control；8002/8010、launcher lock 和进程残留核验通过。关闭时仍观察到既有 aiomysql event-loop-close 析构告警。

## 2026-09-02 — 诊断链接口与 Stage 中文注释补齐

- 按完成能力总账限定唯一目标：只补充中文注释、docstring 与 FastAPI OpenAPI `summary`，不修改路由、Schema、Prompt、配置、状态机、请求响应或业务逻辑。
- 为 Session、Study、Series、Image 上传准备/确认/查询、Task 创建/查询、Report current/history 的目标 HTTP 路由补充业务目的、前置条件、归属、幂等/CAS、状态推进、失败关闭和非职责边界。
- 明确外部 `PUT signed OSS URL` 不经过 Runtime；`complete-upload` 只推进 validating 并投递校验；Task HTTP 201 不代表 Worker/Provider/Report 完成；Report current 允许 `data=null`。
- 为 StudyPreparation、BatchImageQualityReview、StudyScreening、SystemAnalysis、Primary、FamilyRouting、TargetedReview、DecisionFinalization 和 ReportService 补充 Provider/lineage/canonicalization/条件执行边界。
- 明确当前不存在独立 `ReportGeneration AI` Stage；报告由 `DecisionFinalization → ReportService.finalize` 确定性持久化，ReportService 不构造 Prompt、不调用 Provider、不重写医学内容。
- 微调 FamilyRouting v1 注释，兼容历史 `provider_disabled → not_produced`：转发的是已有 Primary 状态、医学结果（若存在）和来源 Call，而非假定一定存在 accepted 医学结果。
- 未访问 Nacos、数据库或 Provider；未启动 Runtime、Relay、Worker、Docker；未新增文档、测试脚本或迁移脚本。
- 静态与定向合同验证全部通过：compileall PASS、Ruff PASS、diff-check PASS、pytest `14 passed, 269 deselected, 3 warnings`；告警均为既有弃用告警。

## 2026-09-02 — TargetedReview 本地合同收口

- 按当前唯一候选处理 `TargetedReview`；未调用 Provider、未启动 Runtime/Relay/Worker/Docker，未写 Nacos、数据库、OSS、Broker。
- 补齐 Cat/Dog exact Prompt Source/import、独立七变量 message contract、Targeted stage config binding，以及 Route/StudyScreening/SystemAnalysis 上游结果冻结传递。
- 独立 Targeted accepted 结果若再次返回 `targeted_candidate`，以 `targeted_review_recursive_candidate_forbidden` 失败关闭，避免递归路由；历史双模式 Prompt 保持兼容。
- 新增递归候选拒绝合同测试；定向 Targeted 测试 `12 passed, 1 warning`，两份合同测试全量 `356 passed, 45 warnings`，Backend 全量 `365 passed, 45 warnings`。
- Ruff、compileall、`git diff --check` 全部 PASS；警告为既有 Pydantic/`datetime.utcnow()` 弃用提示。
- 本轮只达到本地工程合同完成，未产生 Targeted Runtime PASS；仍需用户单独授权合法 candidate、真实 Provider 资格化及后续同 Task 汇合审验。

## 2026-09-02 — Anatomy Localization 主链关联接口设计审计

- 用户补充硬约束：Localization 展示链必须与 `diagnose` 主链显式关联，并可由主链 Task 查询。
- 只读核验 Task model/schema/DAL/service、Localization endpoint/result schema 和 pipeline；确认当前没有直接 task-to-task 字段，现有结果查询只能从 Localization Task ID 发起。
- 确认 `quality_review_task_id` 仅为质量审核上游，`study_id + study_revision_id` 只能做一致性校验，均不能替代主链关系。
- 整理推荐方案：公共 `POST /tasks` 创建 Localization 时增加 `source_task_id`；主链查询返回关联摘要；完整 bbox 结果继续复用现有专用结果查询；后续独立补短 TTL 图片展示票据。
- 本轮未修改业务代码、模型或 migration；未运行测试、Runtime、Provider、Nacos、DB、OSS、Broker。

## 2026-09-03 — TargetedReview、ReportGeneration 与同 Task 主链证据收口

- 按用户要求先审计两个单 Stage，再审计同一 Task 全链；没有新增公共 Targeted/ReportGeneration API，也没有新增 Provider 调用。
- 只读交叉核验数据库与 E2E evidence：Task `ae3c77dd32a34a938eaee6f167d438d6` completed；8 Stage、5 AI Call、5 winner Attempt、Report `a65a33292e354c36baffb71e4c4b571c` final。
- TargetedReview：合法 `thoracic/lung_pattern` 路由，Stage/Call/Attempt completed/succeeded/accepted，3/3/3 image receipt，Prompt/Config/Model/response SHA 与下游 lineage 通过。
- ReportGeneration：独立零图片 AI Stage，Stage/Call/Attempt completed/succeeded/accepted，0/0/0 image receipt，DecisionFinalization 冻结医学结果保持一致，Report source Stage/Call 血缘通过。
- 主线程运行 evidence 断言，输出 `TARGETED_REVIEW_SINGLE_STAGE_AUDIT=PASS`、`REPORT_GENERATION_SINGLE_STAGE_AUDIT=PASS`、`SAME_TASK_FULL_CHAIN_EVIDENCE_AUDIT=PASS`。
- 发现先前 launcher 已停止，`127.0.0.1:8010` 当前不监听；没有因此重跑 Provider，已完成 Task 的持久化证据仍有效。
- 将已完成的 2026-08-29 Prompt/Nacos 验证章节移入 `archive/validation-20260903T-full-chain-closeout.md`，并把活动验证总账顶部资格状态更新为当前三项工程 PASS。
- 本轮只修正 `AGENT_HANDOFF.md` 与 `.agent-handoff/` 过期状态；业务代码、Prompt、Schema、Config、数据库、Nacos、OSS、Broker 均未写入。

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
