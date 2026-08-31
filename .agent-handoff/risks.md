# 风险、阻断与未知项

## 2026-08-31 — R4A Evaluation 独立数据库收口风险

- **R4A 功能链已真实通过但最终资格标记暂缓**：独立库、revision、readiness、Relay/Worker/Fake scorer/Artifact 全链已完成；在线主库 `alembic check` 被既存 `ai_api_connection.secret_ref` 注释漂移阻断。该漂移不属于 Evaluation，未经独立审阅不得塞入 R4A cleanup revision。
- **Docker 容器级验证未运行**：本机 Docker daemon 未启动；Compose 四种静态配置和 Dockerfile Evaluation Alembic COPY 已通过，但仍不能声称 `evaluation-migrate` 容器镜像真实启动资格化。
- **Fake scorer 不是医学 Scorer**：本轮 expected status 只是 schema sentinel；任何 `case_result/failure_summary/metric_summary` 内容都未作为资格证据读取，不能生成 Gold、M1、准确率或发布结论。
- **正式 Evaluation 数据不可随意 downgrade**：正式库已有 1 Job、1 Outbox、1 Run、5 Artifact；真实 downgrade 已按 `evaluation_schema_downgrade_blocked_by_rows` 拒绝。不得手工删除或绕过门禁。
- **主库历史 Evaluation 表已删除**：删除前四表均为 0 行；数据不可恢复，downgrade 只可重建空结构。Evaluation 业务事实唯一 owner 现在是 `ms_image_eval`。
- **凭据生命周期未扩展**：本轮临时 HS256 Secret/Token 仅在已结束的本地进程内存在；未写盘、未提交。R4A 不解决生产 Control Plane 密钥生命周期。

## 2026-08-30 — 2–5 图 Runtime 动态资格化后的剩余风险

- **Config budget 阻断已关闭**：`xray_diagnose_cat@3.0.1` 与 `xray_diagnose_dog@3.0.1` 已 active，冻结 `max_input_images=5`；旧 3.0.0 仅 retired。8 格前后 Config/Prompt SHA 无漂移，Connection validated/capability=20。
- **真实 8 病例工程资格已完成**：cat/dog × 2/3/4/5 共 8 格均 Task completed、Report final、C2 v2、receipt v2，receipt image count=N；该结论只授予 `XRAY_CAT_DOG_2TO5_ENGINEERING_RUNTIME_QUALIFIED`。
- **engineering candidate 仍不是医学病例确认**：8 个 manifest 按五字段技术指纹分组，路径中的 NOR/ABN 未进入 Gold 或 evidence；数据方尚未确认病例关系，结果只可用于工程链资格化。
- **发送 N 图仍不等于逐图医学评估覆盖**：receipt 证明同一 Logical Call 实际发送 N 张冻结图片；当前结果 Schema 没有 `image_assessments` 全输入覆盖要求，不得升级为逐图医学结论。
- **Harness 连接清理告警**：8 次成功运行结束均出现 aiomysql connection 在 event loop 关闭后析构的告警；退出码、Task/Report 和 evidence 均为 PASS。应在后续非医学工程切片显式关闭只读核验 session/engine，不修改本次历史结果。
- **历史冻结 Task 兼容已保留**：AIRequest 固定 2–5 门禁只对 v3 X-Ray diagnose Snapshot 生效；v2 frozen Task 不被新数量合同重新解释。未来修改该判断时必须保留此边界。

## 2026-08-30 — 当前 2–5 图 Runtime 全链风险

- **提交后仍有明确排除的本地文件**：`.agent-handoff/archive/`、tracked archive index 和旧根目录 Postman 保持未提交；它们不是当前运行资产。后续禁止用 `git add -A` 把这些历史/重复资产混入。
- **leakage token 子串匹配可能过宽**：`apps/backend/core/ai/prompting/leakage.py` 当前对所有字符串匹配 `path/score/gold/truth` 等禁止 token 子串；中文合同测试通过，但合法英文 clinical context 可能被误伤。未获产品语义证据前不临时放宽或增加医学规则，应在真实英文上游接入前做定向合同评审。

- **Task Snapshot 不保存完整 Prompt 正文**：完整 Prompt 合同在 immutable Config 行，Snapshot 只绑定 Config identity 与多项 SHA；后续 E2E 必须通过 Config detail + Snapshot SHA 证据链验证，不能在 Snapshot 中寻找不存在的 Prompt key/content 字段。
- **真实 2/3/4/5 图矩阵已运行**：本轮 8/8 工程链通过；它仍不能替代多病例医学准确率、正式 Gold、M1 或 Holdout。
- **projection 可信度依赖调用方**：当前体位由调用方在 `prepare-upload` 声明，不是 DICOM 自动提取或 AI 像素识别；错误声明会沿 Image、Manifest、Snapshot、Prompt 和 SourceRef 被一致冻结。
- **Postman 已交付但未执行真实 E2E**：`docs/postman/ms-image-xray-complete.postman_collection.json` 已覆盖 79/79 项目 HTTP 路由，含 Runtime 29、Runtime Admin 6、AI Control 31、Evaluation Control 9 和 4 个根探针；另有 5 个 OSS `noauth` PUT。Collection 已通过 OpenAPI、Schema、query、鉴权和敏感信息静态校验，但未填写真实 Token、Provider Secret 或真实影像，也未运行 Collection Runner/Newman，不能据此宣称 Runtime E2E PASS。
- **Evaluation 不能替代 Runtime 等价实验 Runner**：当前 Evaluation Worker 使用 `FakeEvaluationScorer`，不执行候选 Prompt、Config、Pipeline、Gateway 或 Provider；9 个 Evaluation 接口虽已实现并纳入总账，但 M1、Prompt A/B、Provider A/B 和医学准确率仍未资格化。
- **器官分割当前只是 PROPOSED 文档合同**：仓库没有可执行的 Segmentation API、Job/Artifact/Outbox、Worker 或 Provider，不能宣称已具备分割展示能力。
- **分割关键参数 UNKNOWN**：目标器官 label set、模型及版本、输入尺寸/格式、mask/overlay 编码、坐标系、partial success 和前端透明度语义均待 S0 冻结。
- **`ORGAN_SEG_*` 未接线**：`.env.example` 出现的器官分割变量尚未接入 `apps/backend/core/config.py` 或实际运行链，不能作为功能存在证据。
- **分割隔离必须守住**：若未来把 mask/overlay 输入医学 Prompt、让分割状态驱动 Task/Report，或让分割失败阻塞 final Report，将破坏当前诊断事实 owner 和独立失败域。
- **Report 治理风险不阻塞首份报告**：revision 1 final/current/history 是 P0 终点；publish、void、第二 revision/supersede 的 `state_version` 风险仍为 P1。
- **Evaluation 与医学准确率不在当前阻断链**：Gold、Scorer、Failure Bank、Holdout 和 candidate runner 仍未资格化，但必须等 2–5 图 Runtime E2E 通过后再推进。

## 当前阻断

- 当前 R4A 最终资格标记只被两项阻断：在线主库既存 `ai_api_connection.secret_ref` 注释漂移导致 `alembic check` 非零；Docker daemon 未运行导致容器 build/`evaluation-migrate` 启动未验。两者都不得用无关业务改动绕过。
- 公网/生产安全仍为 `PRODUCTION_API_SECURITY_NOT_QUALIFIED`：Runtime JWT 生产信任/轮换、Admin JWT 与 Artifact 签名生命周期延期；不影响已资格化的内部 Task→Report 和 R4A 技术烟测，但禁止宣称公网或合规上线安全通过。
- 在线主库已到 `20260831_01`，独立 Evaluation 库已到 `20260831_eval_01`；但主库完整 Alembic 从零 replay 仍未证明。既有环境曾使用 `Base.metadata.create_all + stamp` 对齐，不能把本轮追加 migration 当作完整 bootstrap 证明。
- Provider 原请求 lookup/SLA 仍为 `UNKNOWN`；P1-B 只保证 unsupported 在 3 次/10800 秒边界内 fail-closed。Platform qwen 端点的 IP restriction 与正式进程管理仍是部署风险，但不属于 R4A。
- `secret_ref` 仍是主库 `NOT NULL` 兼容占位列，运行凭据唯一合同为 `AI_PLATFORM_OPENAI_BASE_URL + AI_PLATFORM_API_KEY`；物理列删除或注释修正都需要独立 migration 审阅，不能混入 Evaluation cleanup。
- 已确认 Model 注册表继续保留；旧数据恢复必须先进入临时库并做显式映射，不得继续主观删表或直接覆盖正式库。

## 完整能力实施风险

- `StudyPreparation（检查准备）` 当前代码和测试已确认只做技术准备，不产生医学状态；未来扩展对象/格式/数量/Provider 能力/预算检查时，仍须禁止 Python 决定 `non_diagnostic（影像不可诊断）`。
- 当前五个 Family 已在文档中降级为 `v1 routing vocabulary（首版路由词汇）`；真实医学分母仍不足，后续不得把它们直接固化为永久本体或新增第六 Family。
- Prompt 已改为 Shared Medical Core + Primary/Targeted Frozen Entry（共享医学核心加主读/专项冻结入口）；Targeted 携带 Primary 先验仍有锚定风险，是否拆成不同模板必须通过单变量 Paired A/B 决定。
- Targeted structured message contract 已在 Config 编译与冻结重放时强制携带 `PRIMARY_RESULT_JSON`；这只证明运行结构完整，不证明医学专项复核有效或准确率提高。
- P1-B 已用 `first_unknown_at/reconcile_count`、claim CAS 和正式迁移关闭默认 unsupported 无限重排；3 次/10800 秒是冻结工程 fail-closed 初值，不是 Provider SLA。若未来支持真实 lookup 或发布 v2 policy，必须版本化评审，不能原地改变 v1 未完成 Attempt 的含义。
- P1-A 的唯一 owner 只在仓库/本地部署边界内固定为 Celery Beat singleton；目标生产平台若已有外部 CronJob/scheduler，必须保持 Beat schedule flag 与 `scheduler` profile 关闭。双 owner 会制造重复周期消息，虽然 DB CAS 防止双 claim，仍会放大队列和日志噪声。
- 22 号文档中 FamilyRouting（家族路由）的 family_key/focus_keys/reason_codes/contract_version（家族键/关注点键/原因码/合同版本）属于目标合同，不是当前已实现字段；下一会话必须先核对现有 Stage Schema（阶段结构合同），不能把文档目标误写成代码事实。
- 当前 Config（配置）合同严格限制一条 lane（通道）和 `max_attempts=1（最大尝试次数为 1）`；放宽必须版本化并保持旧 Config 和未完成 Task 可重放。
- 当前 `ai_call_attempt_record（物理 AI 尝试表）` 没有 `lane_key（通道键）`。E4 自动降级前需再次确认最小字段方案；不新增 Lane 表或冗余 Winner 字段。
- 多 Attempt（物理尝试）若错误分类、总预算、deadline（截止时间）或 unknown 对账不严，会造成重复计费和重复医学结果。
- 多 Provider（模型提供方）目前只有 OpenAI-compatible Adapter（OpenAI 兼容适配器）代码路径；真实第二种不兼容协议为 `UNKNOWN（未知）`，不得预建无证据 Registry（注册表）。
- 自动降级只能由明确工程失败触发；医学结果、置信表达或正常/异常结论触发降级会形成不可评测的隐式医学判断器。
- 双 lane（通道）会增加成本、取消、迟到结果和并发 Winner 治理复杂度；必须使用技术合同 Winner CAS（胜出结果比较交换），禁止医学投票或拼接。
- 医学 Prompt（提示词）优化若与模型、Family 路由、图片选择或双 lane 同时变化，将无法归因；每轮只能改变一个主要变量。

## 现有工程风险

- 工作树仍保留明确排除的历史/重复资产；继续禁止 destructive Git 命令和 `git add -A`。
- Config/Profile/Stage v1 与 v2 必须长期并存，直至 v1 非终态 Task 清零并获得显式清理授权；删除旧路径会破坏历史冻结重放。
- Session cancel 只表示取消请求已接受，Task 仍需由 Worker 安全收敛；跨连接 create/cancel/complete 时序仍应在发布环境复验。
- 调用方只通过轮询 Task/Report 获取结果，必须遵守 caller scope、退避、总超时和终态停止；当前不增加 callback/notification。
- 当前真实 E2E 只证明工程链与单病例结构化输出，不能替代多病例 Provider 结构稳定性或医学准确率。

## 已确认边界

- 不恢复 `file_asset`，不复制 `ms-ai-fast` 的档案迁移，不新增平行 Repository/CRUDBase/DatabaseService。
- `AI_PLATFORM_API_KEY`、Signed URL 和 Provider 原始响应正文不得进入数据库、Nacos、Task Snapshot、审计或日志；数据库只保存脱敏 receipt、Provider Request ID、规范化结果、响应 SHA 和 Attempt 审计事实。
- Provider/OSS 网络 I/O 保持在数据库事务外；数据库访问统一走 `DalBase` 和实体 DAL。
- `species=cat|dog` 仍由上游显式提供并冻结；ms-image 不回查宠物档案、不猜测物种。上游档案到 `POST /tasks` 的真实继承仍未资格化。
- 当前保持 `MEDICAL_ACCURACY_UNKNOWN / MEDICAL_RELEASE_NO_GO`。

## 2026-08-27 — 统一服务数据模型风险

- **会话语义冲突**：两个仓库都叫 `session_record`，但一个是业务会话聚合，另一个是消息明细；直接合表会导致一行粒度、唯一约束、状态和查询语义全部冲突。
- **Task 伪通用风险**：当前 `task_record` 与创建服务强制依赖 Study/Revision；简单把字段改 nullable 而不建立明确的 case/subject/input 合同，会产生大量无效组合和运行分支。
- **错误尝试映射风险**：fast `ai_task_attempt` 是 Worker/Celery 执行尝试，不是 Provider 网络发送；映射成 `ai_call_attempt_record` 会污染重试、计费、对账和 Winner 事实。
- **过早抽象风险**：未确认全量迁入 `ai_doc/ai_pic/ai_video/ai_voice` 前新增通用病例、消息、媒体和输入绑定表，可能造成第二套未被真实链消费的模型。

## 2026-08-27 — Primary 控制面激活后的风险

- canonical Prompt、Connection、ModelPool 与 active Config 已是真实数据库事实；后续再次把“缺 Prompt/未激活 Config”列为当前阻断会误导开发。
- 2026-08-27 已真实完成正式 Worker 配置注入、ready Study、冻结 Task/Outbox、Provider 外部 OSS 读取、同一 Task 到 Report 的 Primary happy-path、completed duplicate delivery、cancel-before-provider、provider-sent late-result cancellation、cancelled late-result duplicate delivery，以及 unknown unsupported/lease 恢复；2026-08-28 又完成 P1-A 自动调度与 P1-B 持久有界终止。当前核心 Worker Runtime 已资格化；P1-C 只保留为延期的生产安全风险。
- 本轮 API/Compiler 已清除 `secret_ref` 业务链，但物理兼容列仍存在；未经迁移授权不得删除列，也不得重新把它接回鉴权或 Snapshot。

## 2026-08-27 — 本地无 Docker 全链路后的风险

- `scripts/dev/keys/` 含 dev RSA 私钥，虽已 gitignore，但仍在本地磁盘与工作区；任何提交、压缩归档或分享该目录都会泄露 JWT 签名能力。运行完 e2e 后建议保留公钥、按需删除私钥，或定期重生成。
- `AI_PLATFORM_*` 仅从 ms-ai-fast/.env 进程注入；若 ms-ai-fast/.env 轮换密钥，本地脚本会自动取得新值（无需改代码），但任何把该对配置写入 ms-image `.env`/Nacos/数据库的尝试都必须禁止。
- 本地 API 使用 dev JWT（`imaging:run` scope）且无租户/来源校验，仅限本机 127.0.0.1 8443/8010 访问；不得绑定 0.0.0.0 或用于生产/共享环境。
- 8080 端口无冲突但 8000 被 ms-ai-fast 占用，本地运行 API 固定用 8010（脚本约定）；若未来 ms-ai-fast 释放 8000，需同步更新脚本端口或明确 `MS_IMAGE_LOCAL_API_PORT`。

## 2026-08-27 — C1 后合同风险

- **C1.1 已关闭新写入边界缺口**：缺失、未知和冲突组合会在 Report 创建前 fail-closed；Report 列/content 漂移在 DAL 前拒绝。冻结 v1 Stage 仍使用 `produced/not_produced`，不得据此删除旧 handler/profile。
- C1.1 的真实 E2E 只证明状态合同和工程链成立；本轮 Provider 给出的 `review_required` 不是 Gold 或医学准确率证据。
- 存量旧 Task/Report 仍含 `produced`；未经数据修正授权不得回填，进入 M1 前必须排除或按获批 write set 确定性修复。
- 逐图 projection D1 真实两视图 E1-MV 工程链已完成；D2 clinical context v1 代码和冻结合同也已完成，但既有真实任务是否包含有意义、无标签泄漏的上游临床上下文仍取决于调用方。Provider 能按 Snapshot v3 发送全部冻结 Image，不证明模型理解投照位、临床上下文或医学准确率提升。
- legacy ready Study 现已可按 stored SHA 创建 Snapshot v2 Task，新 D1 Study 创建 v3；这解决运行兼容，不等于把 legacy 数据升级为逐图 D1 血缘。未经存量修正授权仍不得回填或改写 Revision。
- 2026-08-28 曾有新旧两组 Celery Worker 混合消费同一 `imaging.image.validate` 队列；现已由 atomic launcher lock、API/Relay/Worker/Beat 启动前预检和严格 `consumer_count=1` 门禁关闭 launcher 路径。残余风险仅是绕过 launcher 手工启动同队列进程；任何复跑仍以 readiness consumer=1 为准。
- Runtime API、Relay 与单一 Worker 已于 C1.1 验收前精确重启并加载当前源码；后续代码再变更时仍必须重启并先排除重复 Worker，不能用源码级验证替代在线进程生效确认。
- DeepSeek 报告的 `object_version_id` 写入顺序根因与当前源码/数据不符：`complete_validation()` 先 CAS 写完整对象事实并回读，再调用 recompute；当前 8 张 ready Image 的 object_version_id 均为 NULL。删除 `object_version_id` 会削弱冻结对象身份，且不能解决 legacy 与 D1 item 结构不同造成的 SHA 差异。
- 上游没有已核实的权威 projection code 集；首版不执行医学枚举、大小写或字符白名单，只保留 trim、非空、现有 `VARCHAR(64)` 长度、显式 `UNKNOWN` 和来源冻结。未来取得真实 payload/DICOM 字典后如需收紧，应走明确的版本化变更，不能把 LAT/VD/DV/LL 文档示例冒充完整临床本体。
- 自由文本字段白名单不能自动阻断医学标签泄漏；M1/A-B 必须审计 clinical context 的来源和诊断时点，Gold 或未来报告衍生上下文会使实验作废。
- 27 号文档内部同时存在“零表/零迁移”和新增 Study 列/segmentation 表、撤销与继续调用 fixed-bank、两步与一步 diagnoses 等冲突；后续只按 29 号 post-C1 指南实施，28 号保留前置裁决，不能将 27 号清单整体转成任务。

## 2026-08-27 — API 与数据库审计新增风险

- **Report 状态接口伪完成**：publish/void 路由、Service 和 DAL 均存在，但 Report 无 `state_version` 列/属性，真实 CAS 会失败；现有 Fake DAL 测试未覆盖该 ORM/物理合同。
- **Report 交付语义仍未完全一致**：新增 current 接口只返回 `final/published`，合法空 pointer 返回 null，pointer 漂移 fail-closed；但 history 和按已知 ID 仍可读取 `void/superseded`，publish 不控制可见性，void 后 Task 仍 completed 且没有 reason/actor/audit。current 接口完成不能替代 Report 治理修复。
- **Evaluation 分库漂移**：运行时强制独立 `ms_image_eval`，metadata/Alembic 却混用主库；当前目标库不存在，主库四张空表会让“表存在”掩盖运行不可用。
- **迁移不可重放**：当前 revision 链不是完整 baseline；P1-B 只验证了 `20260824_02 -> 20260828_01` 追加 upgrade 和降级事实保护，仍不能证明新环境从空库部署。
- **列表接口范围膨胀**：Task/Image/Study/Session page、Report view/stage detail 都有产品价值，但不应与 C1/P1/D1/M1 一次开发；必须按真实消费者和权限/分页合同逐项打开。
- **Series 自动回归覆盖缺口**：`POST /series` revision 漂移已修复，并以真实数据库回滚事务验证；现有 backend 测试集没有该 Service 的自动合同用例，按用户约束未新增测试文件，后续修改 StudyService 时需保留定向验证。
- **Task retry 字段只有读合同**：`TaskResponse.next_retry_at` 已暴露，但 Runtime 没有写入 Task `retry_wait/next_retry_at`；当前重试事实归 Stage/Outbox/Attempt，调用方不能期待该字段已驱动 Task 级自动重试。
- **Image page 大 Series 性能未资格化**：`GET /images/page` 默认 current 和历史查询均使用已有 logical-version 索引、没有全表扫描，但稳定排序出现 `Using filesort`；当前真实库每个 Series 最大仅 1 条，不能据此证明高实例数 DICOM Series 延迟达标。先在生产等量级数据复测，再决定是否授权排序复合索引迁移。
- **Task page 大 Session 性能未资格化**：`GET /tasks/page` 已复用 requester/study/session-created 索引并通过真实小样本正确性验证，但 Session 跨多 Study、叠加 status/type/time 条件时的执行计划与尾延迟尚未按生产等量级验证；在取得证据前不新增索引或迁移。
- **Session cancelled 不是 Task 全部收敛**：该状态只表示取消请求已原子接受；queued/running/retry_wait Task 仍由 Worker 在安全边界推进为终态，调用方必须继续轮询，不能在 cancel 响应后立即假定无执行活动。
- **终态 Session 的既有 Task 重放仍受原幂等合同约束**：已有 business key 不会被 Session 状态门禁直接拒绝，但仍需当前 Study revision、active Config、Snapshot/hash 与原 Task 一致；调用方不能把终态 Session 当成绕过幂等内容校验的缓存读取接口。
- **readiness 剩余边界**：公共 Runtime readiness 已不再依赖 Evaluation；AI Control 已有独立 health/readiness。但 Runtime Admin 聚合 readiness 仍保留全平面 503 合同，Admin operations 尚不能在 Evaluation DB 不可用时返回分平面 degraded 数据，Evaluation Control 仍缺独立探针。
- **AI Control 当前只剩 JWT 配置未就绪**：本机未配置 `ADMIN_SECRET_KEY`，所以 readiness 真实返回 503；这是正确 fail-closed，不是代码失败。Nacos 地址/namespace/凭据已加载，真实 Prompt Client OPTIONS/GET capability、登录和主库探针均通过；临时注入合格 JWT key 的同进程 smoke 为 200/全部 ready。
- **Nacos Prompt namespace 漂移已纠正**：先前 `.env` 的 `NACOS_PROMPT_NAMESPACE_ID` 指向另一 namespace，导致 canonical Prompt 404；用户确认 `image-dev` namespace 后已对齐，latest/`1.0.0` 均可精确读取。通用 `NACOS_NAMESPACE_ID` 保持原值，避免擅自改变 Config/Discovery 边界；已运行的 AI Control 进程仍需重启才会加载新环境值。
- **derived Image provenance 不可信**：`source_manifest` 当前只要求非空，没有验证源 Image owner、版本或 hash；不能直接把 segmentation role 当成已完成合同。
- **Control validate 语义过强**：Connection/ModelPool/Config validated 只证明静态结构/hash，不能作为 Provider 网络、凭据或模型能力资格证据。
- **Prompt import 长事务**：已有 DB replay/read 后才调用 Nacos，网络等待可能持有主库事务快照；需显式拆分短事务。
- **接口完成度误报**：79 个路由已盘点不等于全部可运行，后续仍须分层报告静态、运行和医学资格。

## 2026-08-28 — 真实 D1 E1-MV 修复后的剩余风险

- **Provider fence 阻断已关闭**：仅兼容唯一完整小写 `json` fence，随后仍执行冻结 Schema。Provider 若返回前后说明、无标签、多 fence、非法 JSON 或 Schema 不合格内容仍会 fail-closed，这是预期行为。
- **失败发送 receipt 已关闭代码缺口**：确定响应解析失败会写 Attempt/无 Winner Call 的 `ai-image-receipt.v2`、manifest 与数量；真实本轮 Task 走成功路径，失败双写由现有测试文件的组合合同验证，未额外制造线上失败 Task。
- **启动器缺省与单 owner 缺口已关闭**：`${PYTHONPATH:-}`、atomic lock、stale-lock 处理、重复进程预检、Beat 禁用、Relay heartbeat、readiness 与 consumer=1 门禁已动态验证；第二个 launcher 只拒绝、不停止现有实例，正常 SIGTERM 只回收本 launcher 的进程和锁。
- **Provider v2 技术引用仍有偶发不稳定**：一次 synthetic 批次第 2 轮真实进入 `provider_result_source_fact_mismatch`，后端正确 fail-closed，随后从新批次连续三轮成功。当前不能推断具体 Provider 根因，也不能用静默重试或 Python 补写 source refs 掩盖；下一阶段应先量化发生率并保留 receipt/error_code 证据。
- **本轮医学输出非 Gold**：数据侧 `NOR` 的精确业务释义没有数据集内字典，且本轮没有可信 Gold/评分器；Provider 输出 `abnormal` 不能用于准确率、标签纠正或发布结论。

## 2026-08-28 — 当前未提交改动架构审查风险

- **Connection/Platform 地址一致性保护缺失（中，当前未触发）**：跨仓核对确认 `GatewayClient + AI_PLATFORM_*` 是用户明确要求按 `ms-ai-fast` 复制的唯一可执行出站合同；`ms-ai-fast` 没有 Connection 冻结表。当前数据库唯一 validated Connection `base_url` 与 `ms-ai-fast/.env` Platform URL 完全一致，`ms-image` 未注入 Platform 配置时 runtime gate fail-closed，因此没有实际发错地址证据。剩余风险是 Runtime 未自动比较 frozen Connection URL 与进程 URL，未来部署配置漂移时审计元数据可能失真。
- **Compose Secret 最小权限不足（条件性高）**：共享 `.env-01` anchor 会注入 app/admin/AI Control/Evaluation/Worker 等多个进程。当前本地 `.env-01` 未发现 `AI_PLATFORM_OPENAI_BASE_URL/API_KEY` 键，因此没有证据表明本机已泄露；正式部署一旦把 Provider key 放入该文件，控制面容器也会持有它。
- **`api_format` 校验过晚（中）**：Connection Schema/Service 只做非空、长度和 URL 规范化，Config 可 validate/activate；Runtime 到 Gateway payload 构造时才限制 `chat/chat-completions/openai-chat-completions`。错误配置会从控制面成功状态延迟成 Attempt 失败。
- **Runtime 反向依赖 AI Control service 实现（中）**：`AIRequestService` 直接 import `AIConfigCompiler` 与 `AIControlValidationError`。编译器当前虽为纯验证器且不访问可变来源，但包依赖仍违反跨平面只共享无状态 contract/core 的既有原则，后续控制面重构可能直接影响 Runtime import/startup。
- `TargetedReview` 仍不是默认多调用：global `3.0.0` 继续 Primary-only；只有显式 `XRAY_TARGETED_EXPERIMENT_SCOPE_KEY=full-chain-local-v1` 才选择已资格化的 `4.0.0` experiment 链。不得将工程可达误报为医学效果通过。
- Runtime Provider readiness 静态 `not_implemented` 是已有明确决策的非 required 观察字段，不进入公共 online engineering `ready`；它仍需未来独立资格化，但本轮不列为新增实现缺陷。

## 2026-08-28 — C2 CompleteMedicalResult v2 剩余风险

- **C2 工程合同已通过，医学准确率仍未知**：真实单病例证明 v2 Prompt/Schema/receipt/Report 链可运行，不证明正常/异常准确率、召回率、假阳性率或发布资格；状态保持 `MEDICAL_ACCURACY_UNKNOWN / MEDICAL_RELEASE_NO_GO`。
- **Provider v2 结构稳定性未形成多病例基线**：当前只有一个明确登记的 C2 真实成功病例；Schema/引用负例由自动合同覆盖，但 Provider 在不同病例、图像数量和输出长度下的 parse/schema 失败率仍为 `UNKNOWN`，应先用固定病例工程重放量化，再在 M1 中评估医学表现。
- **最小主链与 Report 治理必须分口径**：第一份 `final` Report 可生成并读取，不依赖 `state_version`；publish、void、第二 revision/supersede 的真实 CAS 会失败。汇报时不能说“Report 全部完成”，也不能误说“首份报告主链必崩”。

## 2026-08-29 — 全链 Prompt 资格化后的当前风险

- **工程跑通不等于医学优化完成**：猫狗 Targeted 完整链已资格化，但没有可信 Gold、人工仲裁、真实医学 Scorer、分母或 Holdout；不得声称准确率提升或医学发布可用。
- **数据集配对与真值来源未证明**：可见 43,931 张 JPG 与同数量 JSON，但简单 basename/dirname 规则无法证明唯一配对；`ABN/NOR`、Disease 与 annotation 无数据字典、专家来源、盲读/仲裁或病例级 split 证据，必须保持为非 Gold。
- **Evaluation 外壳不等于 M1 可运行**：Job/Run/Artifact/export/paired A/B 骨架可复用，但当前 Worker 使用非医学 Fake scorer，隔离 `ms_image_eval` 不可用且 metadata/Alembic/readiness 尚未拆分资格化。
- **Targeted 候选仍由 Primary 模型生成**：FamilyRouting v2 只校验受控 Family/Focus 和 Finding 引用，不能判断候选的医学必要性；候选率、有效复核率、锚定效应和不安全翻转率均为 `UNKNOWN`。
- **`4.0.0` 不可原地调整**：它已发布、导入、激活并被真实 Task 冻结；后续优化必须使用新版本，否则会破坏审计和重放语义。
- **Targeted SourceRef 复制仍有真实波动**：2026-08-29 当前唯一 owner 下新跑 5 个 Task，其中 3 个进入 Targeted；猫/狗各 1 个 Targeted completed/final，另1 个狗 Targeted 因 `provider_result_source_manifest_sha256_mismatch` fail-closed。这不是 Prompt 缺失或路由不可达，但证明 Provider 技术引用稳定性未达到确定性验收；不得将当前 2/3 小样本外推为真实失败率。

## 2026-08-28/29 — 保留的兼容与证据风险

- **冻结 v1 不得原地修改**：`complete_medical_result.schema.json` 是历史 v1 合同；v2 能力只能通过独立 Schema/Profile/Handler/Config 演进。
- **legacy Snapshot 必须 fail-closed**：缺逐图 projection/manifest 的旧 Task 继续使用 v1 Config；未经存量修正授权不得伪造 v3 或回填历史来源。
- **SourceRef 只是技术血缘**：一致的 image/series/projection/manifest 不证明 Finding 医学成立，也不证明模型关注区域准确。
- **历史狗失败细项永久 UNKNOWN**：旧 Task 未保存不合格 Provider 结构，不能从后续成功反推具体失败字段；未来只按现有三个脱敏错误码统计。
- **Prompt 发布物与本地载体分离**：已发布版本不可原地编辑；`.md` 扩展名不是运行身份，不得复制正文制造第二事实源。

## 2026-08-29 — 历史 Evaluation 路线风险（当前延后）

- **正式 baseline 缺失**：尚无绑定 Git、Prompt/Config/Schema/Connection 与运行证据的 `xray-baseline-manifest.v1`；继续医学实验会不可归因。
- **R4A 是 Evaluation 运行前硬阻断**：当前仅有 Evaluation URL 库名隔离，metadata/Alembic/readiness 尚未独立；目标库不存在或主库残留空表都可能让“接口存在”伪装成“Evaluation 可运行”。
- **R4D Runner 未实现**：当前 Evaluation Worker 不执行 Prompt、Config、Pipeline、Gateway 或 Provider；任何现有 Run/Artifact 不能作为候选 Prompt/Model/Targeted 线上等价证据。
- **Gold/Scorer 未建立**：sidecar、文件名、现有 Provider 输出和 `FakeEvaluationScorer` 都不是医学真值；在 R4B/R4C 前准确率、净收益和发布结论必须保持 UNKNOWN/NO-GO。
- **Provider/Connection A/B 不可归因**：当前冻结身份与真正执行目标之间仍有合同缺口，不能仅修改环境变量或 ModelPool 名称后宣称单变量 Provider/Connection 实验。
- **Report 治理只有局部可用**：首次 finalization/current/history 可用，publish/void/第二 revision/supersede 因 `state_version` 合同缺失不可用；后续实现涉及表字段和迁移，必须另行授权。
- **Retry 发送事实不足**：当前只有 `prepared` 持久化事实，缺实际 `sending/sent` 写入路径；在补齐前不能可靠区分 definitely-not-sent 与 sent/outcome-unknown，也不能安全自动重发。
