# 风险、阻断与未知项

## 当前阻断

- D5 代码基础已完成；2026-08-25 已脱敏验证 Redis PING、RabbitMQ 仅连接、主 MySQL `SELECT 1` 和 OSS Bucket 信息读取成功，但没有声明队列、发送消息、写 OSS 或执行完整 Worker Runtime，因此仍是 `FULL_RUNTIME_NOT_QUALIFIED（完整运行时未资格化）`。
- 主库 `ms_image` 可访问，但没有 `alembic_version`，`ai_config_record` 不存在，三张既有 AI 表缺当前 ORM 所需关键字段。直接对含旧数据的库执行未审阅迁移可能造成数据损坏或不可回滚，必须先做兼容、baseline/stamp、备份和回滚审阅。
- 2026-08-25 只读复核确认主库共 45 表，且 `ai_call_record`、`ai_call_attempt_record`、`study_record`、`study_revision_record`、`stage_checkpoint_record`、`outbox_event_record`、`report_record` 也尚不存在；代码/迁移文件存在不等于正式 Schema 已部署。
- 2026-08-26 P1 synthetic probe 已证明当前进程可对隔离对象进行 AES256 写入、HEAD、直读 GET、同机 signed GET 与 cleanup；但 Provider 外部网络是否能访问相同 signed URL 仍为 `UNKNOWN`，不能把本机读取误报为 Provider/Worker 完整链资格化。
- `ms_image` 当前无 MySQL foreign key 和 trigger；若错误删除旧 Prompt / AI 表，不会被数据库阻止。`ai_prompt_template`、`ai_api_connection`、`ai_model_pool` 仍被当前控制面映射，`session_record` 仍被当前 Session 模型映射；删除前必须先移除调用面并确认备份/归档。
- `ms_image_eval（评测库）` 当前不可连接/不存在，Evaluation Plane（评测面）不能运行。
- AI 请求运行合同已改为与 `ms-ai-fast` 一致的 `AI_PLATFORM_OPENAI_BASE_URL + AI_PLATFORM_API_KEY -> GatewayClient` 直连；旧 `AI_GATEWAY_*` 开关、环境引用 Secret Resolver 和 Provider 原始响应 OSS response store 已从生产链删除。真实 Worker 启动进程是否加载这两个 Platform 配置仍未通过完整任务链验证，不能仅凭 `.env` 存在或交互进程调用判定合格。
- Runtime RS256 公钥/Secret 与 Admin HS256 Secret 均未配置；保护接口和管理控制面不能被视为可用。旧项目公钥只有在确认新服务继续信任相同 issuer/audience 后才能迁移。
- `secret_ref` 仍存在于既有 Control Plane 模型、Schema 与 Config 哈希输入中，但不再参与 Worker Provider 鉴权；彻底删除需要模型/字段/迁移授权。当前风险是遗留元数据可能误导后续实现，必须以 `AI_PLATFORM_OPENAI_BASE_URL + AI_PLATFORM_API_KEY` 为唯一运行凭据合同。
- 当前 OpenAI-compatible Provider（OpenAI 兼容模型提供方）没有已确认的原请求查询 API；`UnsupportedProviderAttemptLookup（不支持查询的安全实现）` 会重排 unknown Attempt（未知尝试），不会盲目重发。真实查询合同确认前，unknown 可能长期待对账。
- 目标 Nacos namespace 已有并验证非医疗基础设施 smoke Prompt `ms-image.xray.chain-smoke.default.zh-CN@1.0.0`，但仍没有已确认可供 `ms-image` 导入和冻结的合格 XRay 医学 Prompt；不得把 smoke Prompt 当 Primary 候选。
- `ms-ai-platform` 当前需手工启动 8062 才能承接 `ms-ai-fast`；没有已确认的常驻进程管理时会在 TCP connect 层失败。
- Platform 模型池中的 qwen 端点受 API Key IP restriction 返回 403；当前 gpt-5-mini 后备可成功，但会增加失败日志和延迟，池健康并非全绿。
- 现有迁移只完成离线或隔离环境演练；应用到共享非生产前仍需 baseline/stamp（基线/标记）审阅和明确授权。

## 完整能力实施风险

- 24 号文档是当前事实与下一开发动作权威；22 号保留完整架构参考，23 号保留历史阶段背景。剩余风险是后续实现或汇报再次把“代码存在”误写成“完整运行或医学发布通过”。
- 22/23 号文档已经统一 FamilyRouting（家族路由）只能输出 `primary_final/targeted_review`，不得产生医学状态；剩余风险是当前代码仍固定直达，版本化路由结构尚未实现。
- v2 Targeted Prompt command 的 `family_key/focus_key` 传递断点已修复并有正反例测试；Targeted 当前仍不可达，真正启用必须等待 M2 医学证据和版本化路由合同。
- `StudyPreparation（检查准备）` 当前代码和测试已确认只做技术准备，不产生医学状态；未来扩展对象/格式/数量/Provider 能力/预算检查时，仍须禁止 Python 决定 `non_diagnostic（影像不可诊断）`。
- 当前五个 Family 已在文档中降级为 `v1 routing vocabulary（首版路由词汇）`；真实医学分母仍不足，后续不得把它们直接固化为永久本体或新增第六 Family。
- Prompt 已改为 Shared Medical Core + Primary/Targeted Frozen Entry（共享医学核心加主读/专项冻结入口）；Targeted 携带 Primary 先验仍有锚定风险，是否拆成不同模板必须通过单变量 Paired A/B 决定。
- Targeted structured message contract 已在 Config 编译与冻结重放时强制携带 `PRIMARY_RESULT_JSON`；这只证明运行结构完整，不证明医学专项复核有效或准确率提高。
- unknown reconcile 已有状态机和 Worker 骨架，但默认 Provider lookup 为 unsupported，当前可无限重排；完整“最大等待时间 + 最大对账次数”需要可靠持久事实，建议评审现有 Attempt 最小 `first_unknown_at/reconcile_count` 字段，未经授权不迁移。
- 完成定义已在文档中拆为核心诊断链、医学基线和可选能力逐项资格；剩余风险是实现和发布流程尚未按这三层生成可验证状态证据。

- 22 号文档中 FamilyRouting（家族路由）的 family_key/focus_keys/reason_codes/contract_version（家族键/关注点键/原因码/合同版本）属于目标合同，不是当前已实现字段；下一会话必须先核对现有 Stage Schema（阶段结构合同），不能把文档目标误写成代码事实。
- `FamilyRouting（专项家族路由）` 当前固定 `primary_final（主读直接定稿）`；真正路由必须保持确定性、不读图、不调用模型、不创造 Finding（影像发现），并且只能产生唯一 Family/Focus（专项家族/关注点）。
- `TargetedReview（专项复核）` 已有 Handler（处理器）但当前不会进入；启用前必须证明同病例相对 Primary-only（仅主读）的净收益，不能以“多一次调用”假设更准确。
- 当前 Config（配置）合同严格限制一条 lane（通道）和 `max_attempts=1（最大尝试次数为 1）`；放宽必须版本化并保持旧 Config 和未完成 Task 可重放。
- 当前 `ai_call_attempt_record（物理 AI 尝试表）` 没有 `lane_key（通道键）`。E4 自动降级前需再次确认最小字段方案；不新增 Lane 表或冗余 Winner 字段。
- 多 Attempt（物理尝试）若错误分类、总预算、deadline（截止时间）或 unknown 对账不严，会造成重复计费和重复医学结果。
- 多 Provider（模型提供方）目前只有 OpenAI-compatible Adapter（OpenAI 兼容适配器）代码路径；真实第二种不兼容协议为 `UNKNOWN（未知）`，不得预建无证据 Registry（注册表）。
- 自动降级只能由明确工程失败触发；医学结果、置信表达或正常/异常结论触发降级会形成不可评测的隐式医学判断器。
- 双 lane（通道）会增加成本、取消、迟到结果和并发 Winner 治理复杂度；必须使用技术合同 Winner CAS（胜出结果比较交换），禁止医学投票或拼接。
- 医学 Prompt（提示词）优化若与模型、Family 路由、图片选择或双 lane 同时变化，将无法归因；每轮只能改变一个主要变量。

## 现有工程风险

- 共享 MySQL 已验证基础连接，但尚未验证迁移兼容、due 查询、CAS（比较交换）、锁、唯一约束、Attempt 幂等重放、Winner 并发、重复消费和 Stage lease（阶段租约）恢复。
- Task 取消、迟到 Attempt、Stage 取消和 Report 幂等已通过离线合同测试，但真实 MySQL 行锁顺序、并发 CAS 和事务回滚仍未在共享非生产链验证。
- Report Notification（报告通知）尚无已确认 destination/consumer/event key；在合同缺失前不能声称通知幂等闭环。
- OSS image signer 已有隔离对象的短期 GET 验证，但 Provider 外部网络可达性、域名/对象范围约束、最短必要 TTL 和只读权限仍需在完整任务链中取得非敏感证据；当前代码不再保存 Provider 原始响应对象。
- D5 Stage Worker（阶段工作进程）组合测试是有限 Fake/Mock（伪实现/模拟）集成，不证明真实 Outbox → Broker → Celery → Worker → Report 链路。
- Config v2 与 v1 兼容链并存；v1 非终态 Task 清零前删除旧路径会破坏历史执行。
- 当前工作树包含大量用户与此前会话的未提交/未跟踪改动；禁止 `reset`、`clean`、`checkout`、`restore`、`stash` 和 `git add -A`，提交必须显式列文件。
- Prompt/Nacos/Gateway/Provider 分段在线成功、单元测试和有限 Mock integration（模拟集成）均不等于医学准确率提高。

## 已确认边界

- 七项能力属于完整目标，但当前阶段均未因此自动启用；必须按 `P0-A（已完成） -> P0-B + Q0 + Q1 -> E1 -> M1 -> Primary Prompt A/B -> 第二模型最小资格化 -> Model A/B -> M2 -> Retry -> Fallback -> Race` 的依赖顺序逐项通过 Gate（门禁）。
- 本轮完成 P0-A Prompt command 业务代码修正并扩展现有测试文件；没有修改数据库字段、运行环境或新增迁移/独立测试脚本。
- 24 号文档和会话 Prompt 已同步，17/19/20/21/23 号历史/目标文档也已添加事实边界；但 active Primary Prompt/Config 尚未盘点或冻结，文档完整不等于运行合同完成。
- 不恢复 `file_asset（公共文件资产表）`；不新增平行 Repository/CRUDBase/DatabaseService（仓储层/数据访问基类/数据库服务）。
- `AI_PLATFORM_API_KEY`、Signed URL（签名地址）和 Provider 原始响应正文不得写入数据库、Nacos、Task Snapshot、审计或日志；数据库当前只保存 Provider Request ID、规范化结构化结果、响应 SHA 和 Attempt 审计事实，不保存原始响应对象引用。
- Provider/OSS 网络 I/O 位于数据库事务外；数据库访问继续统一走 `DalBase（数据访问基类）` 和实体 DAL（数据访问层）。
- 当前仍保持 `MEDICAL_ACCURACY_UNKNOWN（医学准确率未知） / MEDICAL_RELEASE_NO_GO（医学发布禁止放行）`。

## 2026-08-25 — 当前核心 AI 出站与正式 Worker（工作进程）边界

- 当前 Connection（连接）合同已经按用户决定允许并规范化 HTTP/HTTPS Provider（模型提供方）地址；非医疗 Nacos（配置中心）Prompt 已通过 `ms-image` 自身 Gateway（网关）真实调用 `http://8.149.245.40:8060/api/v1`，因此“HTTP 地址被 HTTPS-only 合同阻断”是历史事实，不是当前阻断。
- 2026-08-26 已进一步按用户决策删除旧 Secret Resolver、加密 response store、Gateway adapter/composition 整条生产链，并直接复用 `ms-ai-fast` 语义的 `GatewayClient`。仍未完成 Provider Attempt Lookup（模型尝试查询）与同一冻结任务的完整资格化；任何单次 Gateway 冒烟都不等于 Task/Worker/Outbox/Report 或医学链合格。

## 2026-08-25 — 核心 AI 链已验证后的剩余边界

- 新增 Nacos Prompt `ms-image.xray.ai-gateway-e2e.default.zh-CN@1.0.0` 是非医疗 E2E smoke；不得导入为 Primary Prompt 或作为任何医学准确率依据。
- 历史核心网络烟测曾使用临时 Secret 映射；该实现已被 2026-08-26 用户决策覆盖。当前生产代码只从 Worker 进程 Settings 读取 `AI_PLATFORM_OPENAI_BASE_URL` 与 `AI_PLATFORM_API_KEY`，完整 Worker Runtime 仍须证明实际启动器加载配置以及冻结任务全链事实。
- Platform 已至少一次返回满足严格 Schema 的结果；模型偶发不遵从结构化输出时，Gateway 的 fail-closed Schema 拒绝仍是预期正确行为，不能用 Python 修补医学/结构化结果。
- 2026-08-26 P0 只读审计进一步确认：`ms_image` 中已存在且有数据的 `ai_prompt_template`、`ai_api_connection`、`ai_model_pool`、`session_record` 与当前 Runtime ORM/`20260824_01` 的同名表定义不兼容；该 migration 会直接 create 同名表。未先确定新 Runtime 数据库或获审阅的兼容迁移，直接 `alembic upgrade head` 必然高风险，当前禁止执行。
- 2026-08-26 代码审计确认 Provider 原始响应 OSS store 的运行调用已删除，但 `response_object_ref_json` 仍在 AI Call/Attempt Model、DAL allowed fields 和未部署 migration 中作为遗留声明。它当前未被 Service/Worker 写入，却可能误导未来部署；应在 P0 数据库方案和字段迁移授权后统一消除或明确兼容。
