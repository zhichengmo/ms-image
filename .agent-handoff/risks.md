# 风险、阻断与未知项

## 2026-09-03 — diagnose 同一 Task 全链 PASS 后的剩余风险

- **工程闭环已通过但不是医学结论**：Task `ae3c77dd32a34a938eaee6f167d438d6` 已证明 8 Stage、5 AI Call、5 Attempt、Targeted 动态路由、ReportGeneration AI 与 final Report 的工程闭环；没有 Gold/Holdout/医学 Scorer，医学准确率仍 UNKNOWN。
- **可空审计字段不是完成门**：`stage_checkpoint_record.accepted_call_id` 当前可以为空；接受关系由 `ai_call.stage_checkpoint_id`、Call `result_disposition=accepted`、`winner_attempt_id`、Stage `source_call_id` 与 output lineage 共同证明。未来若升级为强合同，必须先改变生产持久化语义和测试。
- **Projection 仍是调用方事实**：原始 `cat-03.json` 的三张 `UNKNOWN` 与 Provider 具体投照位冲突；成功运行使用 `/tmp/ms-image-cat-03-known-projection.json`。不得通过放宽 validator、猜测像素或静默覆盖解决。
- **Runtime teardown warning 仍存在**：关闭 launcher 时曾出现既有 aiomysql event-loop-close 析构告警；不影响已持久化 PASS，但应在独立工程切片处理。
- **运行组件已停止**：8002/8010 空闲，无 Runtime/Relay/Worker/AI Control 常驻；未来新鲜复跑需重新启动唯一 launcher。
- **开发合同状态文字已过期**：`docs/ms-image-current-development-contract.md` 1.2/3.3 仍写 Targeted/ReportGeneration/同 Task UNKNOWN；不得让旧文字覆盖 2026-09-03 数据库、evidence 与源码事实。
- **工作区受保护**：不得 reset、clean、restore、checkout 或覆盖用户/历史未提交修改。

## StudyScreening v2 当前风险与 UNKNOWN

- **工程 Runtime 已通过**：Cat v2 已完成 1 Logical Call、1 Attempt、Provider HTTP 200、accepted、Task completed、Report 0；不得继续写成 `NOT_YET_QUALIFIED`。
- **医学准确率仍 UNKNOWN**：本次只证明工程合同和双边界可运行，不能升级为医学准确率、Gold、Holdout 或发布资格。
- **v1 必须继续冻结**：历史 projection mismatch 的 v1 Prompt/Schema/validator/Task replay 不覆盖、不放宽、不重跑。
- **Provider raw 与 canonical 必须继续分离**：AICall raw 是 provider.v2 anchor；Stage output 是 Receipt 补齐后的 canonical.v2；canonicalizer 不得改写医学字段。
- **Schema 两个 SHA 均正确**：`b197...` 是原始文件字节 SHA，`f2d0...` 是 canonical JSON SHA；Config 冻结合同使用后者，不能误报为漂移。
- **历史独立资格边界继续保留**：旧 SystemAnalysis Task 只证明独立 Stage；当前同 Task 全链 PASS 来自新的 diagnose Task `ae3c77...`，不能倒写旧 Task 的拓扑。
- **主链下游已资格化**：TargetedReview、ReportGeneration AI 与同 Task 汇合已有 2026-09-03 工程证据；未来新增 Provider 调用仍应按一次运行一个证据序列控制。
- **运行组件已停止**：AI Control、Runtime、Relay、Worker 已清理；8002/8010 空闲，launcher lock 不存在。既有 aiomysql teardown warning 是独立问题，不影响本次通过结论。
- **工作区受保护**：不得 reset、clean、restore、checkout 或覆盖用户/历史未提交修改。

## xray_quality_control 当前风险与 UNKNOWN

- **Prompt/Config 缺失已排除**：Cat/Dog Nacos exact `1.0.0` 与本地冻结正文 SHA 一致；DB Prompt validated、Config active。不得再把“Prompt 没上 Nacos”列为阻断。
- **当前 Runtime API 回归累计 6/6 通过**：初次 1 次及本轮追加 5 次均为 Quality POST 201、无等待立即 GET 200、取消后立即 GET 200、相同 request_id 重放返回同一 Task。当前没有其他服务报错，本问题可关闭。
- **历史首次 409 属于 Runtime，但精确子类型仍 UNKNOWN**：当时未形成 Task/Call/Attempt，也没有 Provider request；因此不是 Provider 429。旧响应未保留内部稳定错误码，不能确定是 `session_not_accepting_tasks`、`study_revision_not_ready` 或其他冲突分支。
- **response-before-commit 仅为历史根因推断**：源码时序、旧 `201 → immediate 404` 观察及当前显式事务回归共同支持该推断，但不能把缺少原始错误码的历史 409 精确原因升级为 CONFIRMED。
- **6 个回归 Task 是取消请求态而非 terminal cancelled**：Task 均 queued 且 `cancel_requested_at` 非空，Stage queued、Outbox pending；Relay/Worker 未启动，因此尚未收敛为 cancelled。未来启动 Worker 时会看到这些 pending Outbox，禁止手工改库或绕过取消合同。
- **工程链通过不等于医学通过**：Cat/Dog 均有工程链 PASS 证据，但部位、投照位和基础质量的医学准确率仍 `UNKNOWN`，医学发布 `NO-GO`。
- **Runtime teardown warning 仍为独立工程项**：本轮关闭 Runtime 时出现既有 aiomysql event-loop teardown warning，不影响已返回的 HTTP/事务证据；不得混入 Quality Prompt 或医学合同。
- **运行组件当前停止**：端口 8002 未监听；Relay、Worker、Docker 未启动；本轮没有 Provider 或 Nacos 写入。

## 宠物档案迁移风险与 UNKNOWN

- **数据库与数据迁移已经完成，不再是 NOT_RUN**：目标 MySQL 已处于 revision `20260901_01 (head)`；三张宠物表和 5091/152/0 条目标数据均已通过实库核对。
- **源历史为空**：`vet_platform.pet_profile_history=0`，因此目标历史表保持 0；这不是漏迁，但现有 legacy 档案没有可恢复的变更历史。
- **第三方品种图片未迁为 OSS key**：874 个源图片 URL 来自 `upload.suoweilai.com`，未验证属于目标 OSS，因此目标 ORM 读取为 `image_keys_json=None`；如需展示图片，必须单独设计下载、内容校验、OSS 上传和版权/来源治理流程。
- **品种区间体重未伪造单值**：152 个源参考体重均为区间文本，目标 `reference_weight_kg` 保持空；不得用区间中点冒充事实。
- **真实 HTTP API 事务 E2E 尚未运行**：代码和全量测试已通过，导入也经 `DalBase` 写入，但创建幂等、CAS 冲突、归档/恢复和 history 原子性尚未通过真实 API 并发场景资格化。
- **既有 Alembic 无关漂移仍存在**：`alembic check` 只报告 `ai_api_connection.secret_ref` comment drift；不得把该既存项混入宠物 migration。
- **医疗域仍明确排除**：体格、病历、诊断体征和时间线未迁入；调用方不得把当前档案 API 误认为完整宠物医疗记录能力。
## 非分割阶段级 Prompt 架构风险

- **10 个新 Nacos Prompt 已 online，但不会自动生效**：当前 `AIConfigRecord` 只冻结一份 Prompt，Task 只有一个根 `ai_config_id`，Runtime 还要求 Call Config 与 Task Config 一致；必须先实现 Prompt Source mapping、Stage Schema/validator 和 stage-specific Config binding。
- **新发布版本已经不可变**：StudyScreening、SystemAnalysis、PrimaryCaseAdjudication、TargetedReview、ReportGeneration 的 Cat/Dog `1.0.0` 均已 exact 回读通过；任何正文修订必须新建版本并重新授权，禁止覆盖或 force publish。
- **逐图 Quality 需要图片子集合同**：当前 `StageAIRequest` 只有 Prompt command，`AIRequestService` 默认加载整个 Task Study 的全部图片；若不增加冻结 image selection，每个 Quality Call 不能证明只看到目标图片。
- **调用数量显著增加**：目标 Primary-only 为 `N+4` Call、Targeted 为 `N+5`；2–5 图即 6–10 Call。总预算、deadline、部分失败语义和并发上限未实现，不能用单 Config 预算代替 Task Profile 总预算。
- **阶段拆分不等于准确率提升**：12 个 Prompt 只建立职责、版本、证据和回滚边界；没有 paired A/B、Gold 或 Scorer，医学收益仍为 UNKNOWN。
- **旧 Prompt 正文并不全部可证实**：指定 commit 能确认大量 Config key 和部分本地 Markdown，但 Runtime 从 AI Config DB 获取正文；未读旧数据库的 key 必须保持 UNKNOWN。
- **旧分割依赖禁止回流**：旧 System/Crop/Report 链依赖 segmentation bbox、crop、PiP 和 annotated image；本期仅吸收职责/规则，不复制数据依赖和 17×2 crop Prompt。
- **ReportGeneration 可能重复或漂移医学事实**：当前 CompleteMedicalResult v2 已有 summary/impression；若独立报告 Prompt 新增、删除或改写 Finding/status，必须拒绝结果。Report Prompt 默认不看原图，只能组织冻结 final result。
- **Quality 工程实现已接通，Cat/Dog 工程链均有 PASS 证据**：Registry、Prompt、Task、validator、Config 和路由均已实现；工程通过仍不得外推为 Cat/Dog 医学准确率或主诊断链完整资格。

## Anatomy Localization v1 当前风险

- **新的真实 Runtime 首格仍失败**：启用最小失败可观测性后的 `cat-02` 只运行一次，创建 1 Task、2 Stage、1 Logical AICall、1 primary Attempt 并一次发送 2 图；Provider HTTP 200 且通用 JSON Schema 通过后，Localization 技术 validator 以 `anatomy_localization_image_1_projection_mismatch` fail-closed。其余七格按停止门禁未运行，不得记录 `XRAY_ANATOMY_LOCALIZATION_2TO5_RUNTIME_QUALIFIED` 或 `ANATOMY_LOCALIZATION_SINGLE_LOGICAL_CALL_CONFIRMED`。
- **失败字段已定位，但业务根因尚未审核**：新审计事实仅证明第一张图的 Provider 返回 `projection` 未与冻结 lineage 完全一致；Provider body 和 rejected parsed result 仍未保存，因此不能从现有证据断言它返回了哪个具体值。不得凭猜测修改 Prompt/Schema，也不得放宽 validator。
- **最小可观测性已通过真实失败路径验证**：Attempt/AICall 保存了 Provider request ID、actual model 和 response SHA，字段级错误码适配现有审计合同；Provider 本次未返回 usage，所以 `usage_json=null`。这不等于 Localization 功能或医学结果通过。
- **现有只读审计已经穷尽**：Attempt 关联键已回读，`ms-image` 确认把 request/trace/idempotency key 发给下游；但本机临时目录、系统日志、`ms-ai-fast` 日志均无本轮命中，AI Platform 公开 OpenAPI 也没有 request/audit/trace/log 查询接口。后续不能继续声称“也许现有日志可恢复”，除非用户另行提供非公开下游审计入口。
- **旧失败仍不可恢复，但不再阻断新事实定位**：先前 `cat-02` 的 Provider 响应仍已丢失；本次新运行是独立资格化事实，不能冒充旧响应证据。
- **5 图 Provider 稳定性仍为 UNKNOWN**：矩阵在 2 图首格已经停止，尚未产生任何 3–5 图真实结果；本地 Schema/预算/负例不能证明真实模型一次返回 5 图、最多 190 个 bbox 时不会截断、超时或产生引用漂移。
- **定位准确率仍为 UNKNOWN**：normalized bbox 通过技术合同不等于器官位置正确；当前没有 Gold、Scorer、病例级分母或医学审核，不得声称语义分割、定位准确率或医学发布资格。
- **数据根目录工程门禁通过不消除模型合同失败**：`/Users/mozhicheng/workspace/documents/X光_没问题_全量过滤` 的八份冻结 manifest 和 28/28 张目标图已通过 SHA/size/格式/解码门禁；本轮失败发生在 Provider 响应的 Localization lineage 校验，不是输入文件缺失或解码失败。
- **输入工程可用不等于数据治理或医学资格**：八份 manifest 均为 `engineering_candidate`，projection 为 `UNKNOWN`；路径、哈希、解码和视觉抽样只能证明可作为 Runtime 工程输入，不能证明病例分组、投照位、bbox 定位准确率、Gold 或医学质量。
- **Nacos/Config 已产生不可变身份**：两个 exact Prompt 与两个 Config 均已 online/validated/active；后续运行前仍须 exact 回读 SHA，发现同版本冲突立即停止，不能覆盖或自动升版。
- **后续 Runtime 事实仍需新授权**：本次授权已用于单次新 `cat-02`，且已按失败即停结束。任何再次运行 `cat-02` 或启动新八格都必须获得新的明确授权，并继续遵守首格失败即停、单 Attempt 和不可静默重试。
- **外部运行事实已在本轮前置回读但仍不可视为永久状态**：本轮启动前已重验 ModelPool/Connection/Platform/namespace、Prompt/Config/Schema SHA 和 frozen verify，未发现漂移；任何未来审核或新资格化仍必须实时回读，不能把 handoff 当作运行时配置来源。
- **结果只属于 Localization Stage**：不得写入 Report、诊断主链或 Evaluation 医学 export；任何“必须依赖 Report 才能查询”的实现方向都是停止条件。

## 工作区与范围风险

- **受保护历史改动**：`.agent-handoff/archive*`、tracked archive index 和根目录 `postman/` 保持用户既有状态；禁止恢复、删除、暂存或用 `git add -A` 混入交付。
- **既有排除项继续隔离**：`secret_ref` 注释漂移、Docker build、aiomysql teardown warning、R4A/R4B/R4C/R4D/M1、Report 和 Evaluation 均不属于 Localization 收口；不得为消除无关告警扩大 write set。
- **未知重叠改动必须停审**：若后续发现归属不明且与 Localization Exact Write Set 重叠的用户改动，不得覆盖或重置，必须返回用户确认。
- **禁止产生第二 owner**：Stage/endpoint 不得直接访问 Gateway/Provider，不得新增 LocalizationAIService、Worker、Relay、Outbox、Repository、CRUDBase、表、字段或 migration。

## R4A 与 Evaluation 延后风险

- **R4A 功能链已通过但最终关闭仍有独立阻断**：独立 DB/metadata/Alembic/readiness/Fake scorer 烟测已完成；在线主库仍有非 Evaluation 的 `ai_api_connection.secret_ref` 注释漂移，Docker daemon 未运行导致镜像 build 未资格化。
- **Fake scorer 不是医学 Scorer**：R4A 的 Job/Run/Artifact 只证明基础设施；不能生成 Gold、M1、准确率或发布结论。
- **正式 Evaluation 数据不可随意 downgrade**：`ms_image_eval` 已有烟测 Job/Outbox/Run/Artifact 审计记录；downgrade 应继续 fail-closed，不得手工删数据绕过。
- **R4D Runner 尚未实现**：Evaluation Worker 不执行 Runtime-equivalent Prompt/Config/Pipeline/Gateway/Provider；现有 Artifact 不能作为候选模型或 Prompt 的线上等价证据。

## 医学与数据治理未知项

- **Dataset pairing 和真值来源未证明**：文件名、目录、sidecar、Provider 输出和现有报告都不能自动成为 Gold；病例级关系、标签来源、时点、去重、split 和仲裁仍需 R4B/R4C。
- **工程 receipt 不等于医学覆盖**：receipt 证明 N 张冻结图被发送；Localization result 的 exact lineage 证明逐图结构覆盖，但不证明每个 bbox 医学正确或病灶完整。
- **Prompt/Model 工程资格不等于医学收益**：没有 M1、Failure Bank、paired A/B 和 Holdout 前，不得声称 Prompt、Targeted 或模型带来准确率提升。
- **当前发布状态保持**：`PIXEL_MASK_NOT_IMPLEMENTED / LOCALIZATION_ACCURACY_UNKNOWN / MEDICAL_ACCURACY_UNKNOWN / MEDICAL_RELEASE_NO_GO`。

## 兼容与长期运行风险

- **冻结资产不可原地修改**：历史 Prompt、Config、Schema 与 Task Snapshot 必须保持不可变；新修正只能使用经审核的新版本。
- **SourceRef/lineage 是技术事实，不是医学事实**：image/series/projection/manifest 一致不能证明 Finding 或 bbox 正确；Python 不得猜测、生成或修复模型医学输出。
- **Projection 可信度依赖调用方**：当前 projection 由 prepare-upload 声明，不是 DICOM 自动提取或像素识别；错误输入会被一致冻结。
- **Report 治理只局部可用**：第一份 final/current/history 可用；publish、void、第二 revision/supersede 仍受 `state_version` 合同缺口限制，不能误报为 Report 全部完成。
- **Retry 发送事实仍不足**：缺少完整 sending/sent/outcome-unknown 持久事实时不能安全自动重发；Localization v1 必须保持一个 Attempt。

## 2026-09-03 — TargetedReview / ReportGeneration 工程 PASS 后的风险

- **TargetedReview 已真实 PASS**：合法 candidate `thoracic/lung_pattern` 触发 Stage、3 图 Provider Call、accepted winner Attempt 与下游 lineage；这只证明本次工程执行，不保证所有病例都会产生 candidate。
- **ReportGeneration AI 已真实 PASS**：独立零图片 Stage 的 Provider Call、accepted winner Attempt、DecisionFinalization 冻结结果和 final Report lineage 一致；零图是阶段合同，不是漏传图片。
- **递归候选继续 fail-closed**：Targeted Prompt 若再次返回非空 `targeted_candidate` 仍必须终止，保护最多一次预算。
- **医学准确率仍 UNKNOWN/NO-GO**：单病例工程 PASS 不包含 Gold、Scorer、Failure Bank 或 Holdout，不得据此声称诊断收益。

## 2026-09-02 — Localization 与主链关联风险

- **当前没有直接 Task 血缘**：`task_record`、`TaskCreate`、`TaskResponse` 均无 `source_task_id`/`parent_task_id`；现有 Localization 查询传入 diagnose Task ID 会以 `task_not_anatomy_localization` 失败。
- **Study Revision 不是主从键**：同 requester、同 Study Revision 可创建多个 diagnose/localization Task；按 Study/Revision 回推只能返回候选，不满足用户要求的“通过主链查询”。
- **质量审核引用不可改义**：`quality_review_task_id` 属于 Quality→诊断输入合同，挪作 Localization 关联会污染冻结快照和既有校验。
- **多历史 Task 的 current 语义必须先冻结**：如果不限制并发非终态子任务或不定义稳定排序，主链反查可能返回不确定结果。
- **字段实施需要 migration 授权**：仅写 ORM 或只塞 Snapshot 都会造成物理 schema/查询合同不完整；本轮未生成 migration。
- **展示 URL 不得永久持久化**：未来 view ticket 必须短 TTL、HTTPS、owner-check，不能写入 Task Snapshot、Localization 永久结果或日志，也不能在数据库事务内执行 OSS 签名。

## 2026-09-03 — Git 交付与后续模型路由风险

- **Git 禁止强制覆盖**：当前分支原先没有 upstream；推送必须使用普通 `git push -u`。认证失败、远端同名分支冲突或非快进时立即停止，不得 force push。
- **跨仓库修改尚未授权**：后续模型路由会涉及 `ms-image`、`ms-ai-fast` 和 `ms-ai-platform` 的边界核对；本轮只创建分支，不修改另外两个仓库。
- **模型名与推理参数不可混淆**：目标是 `model=gpt-5.6-sol` 加 `reasoning_effort=xhigh`，不是 `model=gpt-5.6-sol-xhigh`。
- **平台当前可能覆盖请求模型**：已定位 `ms-ai-platform/app/service/ai_proxy_service.py` 会用 Endpoint Config 的 model 覆盖请求；入口 Schema 也需核对是否保留 `reasoning_effort`。只改调用方映射可能不会真正切换 Provider 模型。
- **不得新增第二套 AI owner**：`ms-image` 后续实现必须复用现有 AI Control、冻结 Config、`AIRequestService`、Gateway/Worker 链路；接口或 Stage 不得直接请求 Provider。
