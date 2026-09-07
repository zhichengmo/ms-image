# Historical risk snapshot — superseded on 2026-09-07

Not current state; see ../risks.md.

# 风险、阻断与未知项

## 2026-09-07 — Basic Auth 真实全链完成后的剩余边界

- **工程全链已通过，不再受 Bearer-only 401 或 Localization Prompt Schema 阻断**：真实浏览器、Runtime Basic Auth、OSS、Quality、Diagnose、Localization 与 Report 已在同一病例完成；不要继续沿用旧快照的阻断状态。
- **医学准确率仍为 UNKNOWN / NO-GO**：单病例真实 Provider 成功、Report final 和 normalized bbox 技术合同通过，不等于 finding、器官框或病例结论具有医学 Gold 级正确性。
- **输入/观察体位冲突需人工复核**：Quality 将两图观察为 `ventrodorsal`，第 1 张冻结申报为侧位；报告已将其列为限制，不能由 Python 或 UI 静默修正。
- **bbox 不是像素分割**：本次每图 9 个矩形框，共 18 个 normalized bbox；没有 mask、像素轮廓或医学标注仲裁。
- **短效 OSS 链接会正常过期**：页面已验证“重新申请”可恢复影像与框；不得持久化 signed URL，也不能把过期提示误判为 AI 链失败。
- **production 部署资格未完成**：开发环境 Vite 同源代理已解决本地浏览器 PUT CORS；非 localhost 仍需 HTTPS、同源网关/CORS 和 Authorization 日志脱敏。
- **首次 CORS 失败遗留部分 Study**：`e2434f58540f43a6b2487b4a37e1e18f` 没有 AI Task；当前只记录，不自动删除。

## 2026-09-04 — 准确率 Pilot 当前阻断

- **不能声明临床准确率认证**：数据集只有图像级 ABN/NOR 操作标签，`metadata.Disease` 是同一标签的重复，不存在独立医学报告、病种/finding Gold 或仲裁。
- **病例标签不可直接上卷**：候选宠物键中 925 组同时含 ABN/NOR，加入检查日期后仍有 648 组；混合组不能被静默剔除后用来宣称总体病例准确率。
- **首例工程失败阻断分母**：Case 1 在 Primary 后处理以 `provider_result_source_projection_mismatch` 失败，无 final medical result，不能分类为 ABN 命中/漏诊；10 例指标保持 NOT COMPUTED。
- **Prompt 输入存在冲突证据**：冻结 lineage 为 `lateral_indeterminate`，Quality observed 为 `ventrodorsal` 且 consistency=inconsistent；Primary Prompt 未明确区分“技术 source_ref 必须复制 caller lineage”和“医学解释可使用 observed projection”。
- **失败正文不可恢复**：只保存 Provider request ID、response SHA、actual model 和稳定错误码；没有 rejected parsed result，因此不能断言模型具体返回了 `ventrodorsal`。
- **不得放宽 validator 或过滤 Lateral/AP/ML**：修复应使用新的不可变 Prompt 版本明确 source_refs 复制合同，先固定失败回归；不能只保留 VD 病例制造通过率。
- **展示链隔离**：准确率本轮未修改 Anatomy Localization、查询 endpoint、TaskService display DTO 或 pipeline；其他会话可以在不触碰共享 Primary/Prompt/E2E 文件的前提下独立收口。

## 2026-09-04 — Gemini 3.8 猫狗 fresh 主链后的剩余边界

- **主链工程门已通过**：fresh Cat Task `7d53e0d6...` 与 Dog Task `b6f130ee...` 均 completed、唯一 final Report、task/current/history 一致；Quality 和诊断所有实际 Call 均 requested/actual=`gemini-3.8-flash`、单 Attempt、动态 species exact Prompt。
- **TargetedReview 3.8 Runtime 未覆盖**：本轮 Cat/Dog 都由 FamilyRouting 合法选择 `primary_final`，因此 TargetedReview 未物化。源码路由和静态断言是 3.8，但不能据此声称该条件分支已真实运行。
- **Anatomy Localization 仍是独立失败链**：模型路由虽已切到 3.8，历史 `projection_mismatch` 与展示查询收口仍需独立审核；诊断主链 PASS 不会自动修复或资格化 Localization。
- **ReportGeneration 复制风险没有被理论消除**：Dog `1.0.4` 本次深度相等 PASS 只证明该请求成功；生成模型长期逐字符复制稳定性仍未知，truth-preserving validator 不能移除或放宽。
- **医学准确率不变**：engineering candidate 真实输入不等于 Gold；没有可信 Failure Bank、Scorer、Holdout，继续 `UNKNOWN / NO-GO`。
- **既有 teardown warning 保留**：E2E 和 launcher 温关闭仍出现 aiomysql event-loop-close 析构告警；不影响本轮已持久化结果，应在独立工程切片处理。
- **运行组件已停止**：8010 无监听，Runtime/Relay/Worker/launcher lock 无残留；evidence 已移入废纸篓，可恢复。

## 2026-09-04 — ReportGeneration v1 精确复制风险已确认

- **失败字段已确认**：Dog `1.0.4` 诊断复现中只有 `$.final_medical_result.coverage.missing_or_limited_views[0]` 不同；Gemini 把中文“和”改为英文 `and`，其余深度比较字段一致。
- **不是 Schema 或 Nacos 对齐问题**：exact Prompt `1.0.4` 动态读取成功、无 fallback，响应通过 v1 JSON Schema，顶层 SHA/status/version 正确；Schema 只能约束结构，不能表达“输出对象必须等于输入对象”。
- **继续堆 Prompt 仍不确定**：即使本次只错一个词，也已证明生成模型会规范化冻结字符串；多跑几次偶尔成功不能建立确定性合同。
- **原始失败可观测性仍有限**：历史业务失败正文未持久化，本次完整响应只在诊断进程内展示与比较，未落库；若未来需要长期失败字段审计，应单独设计受控、脱敏、加密的 rejected-result 证据边界。
- **v2 尚未实施**：两个摘要分片并发 + 冻结事实确定性组装目前只是用户审阅中的方案；不得描述为已有能力，也不得据此恢复展示链接口。
- **医学准确率不变**：本次只定位输出复制技术失败，不验证任何 Finding 的医学正确性；继续 `UNKNOWN / NO-GO`。
- **3.7 单次成功不是确定性保证**：同一 Dog 输入在 `gemini-3.7-flash` 上一次返回差异数 0，但没有重复样本、猫样本或 fresh 全链证据；不能据此取消 truth-preserving validator 或直接声明路由升级完成。
- **模型切换范围仍需用户裁决**：当前 6 个诊断 Stage 均为 3.5；用户本轮语境聚焦 ReportGeneration，未经明确范围确认不得把 ImageQuality、Screening、System、Primary、Targeted 一并切换到 3.7。

## 2026-09-03 — Gemini 猫狗全链通过后的当前风险

- **工程链已关闭，不等于医学准确率通过**：Fresh Cat Task `00deb1ff...` 和 Fresh Dog Task `7ec955a6...` 均 completed、唯一 final Report、task/current/history 一致；没有 Gold/Failure Bank/医学 Scorer/Holdout，医学准确率仍 `UNKNOWN / NO-GO`。
- **条件拓扑不能被误报为漏 Stage**：Cat 产生 TargetedReview candidate，走 8 Stage/5 AI Call；Dog 的 FamilyRouting=`primary_final`，合法走 7 Stage/4 AI Call。只有存在合法 candidate 时才应物化 TargetedReview。
- **ReportGeneration Prompt 版本必须保持不可变**：Cat/Dog `1.0.2` 已 online，新增规则只要求深拷贝冻结医学对象；旧 `1.0.0/1.0.1` 不覆盖、不删除。任何后续正文修订继续使用新版本。
- **不得把 Prompt 修复变成 Python 医学修正**：`report_generation_medical_result_rewritten` 首次失败通过 Prompt `1.0.2` 修复；truth-preserving validator 未放宽，后续也不得在代码中重写 Provider 医学输出。
- **旧模型 timeout 是历史风险，不再是当前 Gemini 阻断**：`gpt-5.6-sol` 曾在约 60 秒边界累计 3 次 Platform 500；本轮 Gemini 所有请求均 HTTP 200。若切回慢模型，Platform Endpoint timeout 仍需独立确认，ms-image 不加自动 retry/fallback。
- **运行组件已停止**：8010 无监听，无 Runtime/Relay/Worker/launcher lock；关闭和 DAL 审计仍出现既有 aiomysql event-loop-close warning，应作为独立工程项处理。

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

## 2026-09-02 — Localization 与主链关联风险（2026-09-04 已收口）

- **直接 Task 血缘已实现**：`task_record.source_task_id`、Schema、DAL、Service、API 与 migration 已由 `5c2e1ec` 原子交付；新建 Localization 必填，物理 nullable 仅保留历史读取兼容。
- **禁止 Study Revision 推断仍有效**：所有新关联均使用精确 `source_task_id`；`quality_review_task_id` 继续只承担 Quality→诊断输入合同。
- **多任务语义已冻结**：同 source 最多一个非终态 Localization；终态历史保留，current/history 使用稳定排序和专用查询。
- **展示 URL 真实签名仍需独立验收**：本轮真实只读验证覆盖 Task/current/history/legend，未取得目标 OSS `versionId` 下载成功证据；短 TTL、owner-check、冻结版本绑定和事务外签名合同仍由测试覆盖。

## 2026-09-03 — code-owned AI/Prompt 路由剩余风险

- **当前真实 E2E 阻断在 Prompt Runtime 进程**：MySQL、RabbitMQ、Redis、OSS、ms-image Runtime/Relay/Worker 已真实可用；猫在 Quality AI Stage 连接 `127.0.0.1:8100` 时失败。`ms-prompt-service` 环境端口已配置但进程未启动，因此仍为 `ENVIRONMENT_BLOCKED`。
- **平台可能覆盖请求模型**：`ms-image` 的 code route 会发送 `gpt-5.6-sol`，但 `ms-ai-platform` Provider 请求最终使用 Endpoint Config 的 `model`；在真实 Gateway/Provider receipt 出现前，不能声称实际模型已切换。
- **`xhigh` 明确延期**：当前 `AiModelRoute` 仅有 `models/mode`，ms-image 与已核验的平台请求 Schema 均未传递 `reasoning_effort`；不得把模型名写成 `gpt-5.6-sol-xhigh`。
- **共享 launcher 有未提交修改**：`scripts/dev/run_local_chain.sh` 当前 diff 会从 `ms-ai-fast/.env` 读取 Prompt Runtime 配置并 fail-fast，但不会启动 Prompt Runtime。后续运行前必须确认该 diff 属于用户预期且不再被其他会话并发改写，不得擅自回退。
- **相邻 Prompt 仓库有未跟踪文件**：`ms-prompt-service` 当前存在未跟踪文档/导出资产；若只为启动服务，不得清理、reset 或提交这些文件。
- **历史 Config 分支是兼容边界**：新 XRay 调用不读取 Config DB；旧 frozen Task/replay 仍会读取历史 Config，这是有意兼容，不应误删或误判为新链依赖。
- **数据库仍保存审计事实**：Task/Stage/Call/Attempt 与 runtime snapshot 继续持久化；“不用数据库”不代表删除可靠执行和审计记录。
- **不得新增第二套 AI owner**：后续改动继续复用 `AIRequestService`、Gateway/Worker；Stage/API 不得直接请求 Provider。

## 2026-09-04 — Cat Quality canonical projection Prompt gap

- `lateral_indeterminate` 是实际冻结输入 canonical 值，但 Nacos Cat Quality `1.1.3` 只明确了原始别名 `Lateral`；Gemini 可按自然语义给出与 validator 不同的 `projection_consistency`。
- Provider 被拒正文未持久化，实际字段对 UNKNOWN；修复只能基于确定的 Prompt/validator 规则缺口，不能宣称已看到原始返回。
- 当前完整 10 例只完成 Case 1；任何总体准确率数字都会误导，医学状态保持 UNKNOWN/NO_GO。


## 2026-09-04 — 展示链提交后的剩余风险

- `4aa46f1` 的展示接口与 `5c2e1ec` 的 diagnose→Localization 显式 Task 血缘均已交付；不得再按旧阻断重复实现。
- `GET /api/v1/tasks/page` 当前返回 422，是通用 Task 分页的独立问题；专用 Localization `history` 已真实 HTTP 200。
- Localization 新 bbox 生成被 Nacos Cat `1.0.0` Prompt 缺少 Output Schema 阻断；2026-09-07 已通过与 Worker 相同的 `PromptRuntimeClient.render()` 精确复现，并只读确认 `has_output_schema=false`。无 Nacos 写授权时不得覆盖旧版本、创建新版本或用代码绕过 Schema。
- 真实 `prepare-view` OSS 下载和 `versionId` 行为尚未完成受控验收，不能把只读 DB/API HTTP 200 扩大解释为完整浏览器图片加载 PASS。
- 医学与定位准确率仍为 UNKNOWN，工程接口完成不构成医学发布资格。

## 2026-09-04 — X-Ray 前端认证与部署边界

- 前端已创建于 `apps/frontend/`，原“宿主缺失/等待选型”风险已关闭。
- Runtime Basic Auth 已实现并通过合同验证；正确 Basic 已越过鉴权进入业务层，真实 Diagnose AI 全链也已在 Basic Auth 下 PASS。Admin 仍为 Bearer-only，后续不得把 Runtime 放宽误扩展到 Admin。
- Basic 凭证只允许通过进程环境注入，不得写入仓库、evidence、handoff、URL、浏览器持久存储或日志；非 localhost 必须使用 HTTPS。
- Runtime 仅在 `ENV=dev` 时配置 `allow_origins=["*"]`、`allow_headers=["*"]`；production 跨域访问为 `UNKNOWN`，部署必须使用同源反向代理或在网关显式配置 CORS。
- Basic 用户名和密码只在页面内存；但 Basic 凭证本身不是加密机制，非 localhost 环境必须使用 HTTPS，代理与访问日志不得记录 Authorization header。
- 隔离 mock 已覆盖完整 2 图上传、任务轮询、Report、prepare-view、signed image 与 bbox 浏览器链，但真实 Runtime 在认证层之前停止，因此 mock PASS 不能替代真实 Runtime/OSS 集成门。
- 前端原有“等待 Diagnose completed 后才启动 Localization”的串行风险已关闭；当前只保留创建请求的必要因果顺序（先取得 Diagnose ID），Task 执行阶段已验证并行重叠。不得把两个 POST 非同时发出误判为执行链串行。
- 本轮 readiness 为 `medical_provider_ready=false`；即使后续认证接通，也必须先满足 Provider readiness 才能产生真实 AI 链路证据。
- 前端展示完成仍只代表工程 UI 能力；Localization bbox 医学准确率继续为 `UNKNOWN / NO-GO`。

## 2026-09-04 — 真实数据集报告页演示边界

- 浏览器中的 JPG 与 bbox 来自用户指定真实数据集，但 Runtime、任务时间线、prepare-view 和 Report 响应仍由隔离 Mock 提供；因此证据级别是“真实数据资产 + 真实前端编排/渲染”，不是“真实 Runtime/Provider/OSS 全链”。
- 数据集只提供 JPG、逐图 JSON、`Disease=ABN`、`Disease-Name=Ch07`、Projection 与矩形 Bounding Box；没有自然语言报告、病种 Gold 或权威 `Ch01–Ch07` 字典。不得把 `Ch07` 擅译为具体疾病。
- 原始 bbox 标签为 `부위표시`，无法证明是器官轮廓、病灶范围或像素级 mask；页面已明确显示为“数据集矩形标注 / 原始标注区域”。
- Console 唯一错误是 Mock 鉴权探针 `GET /api/v1/tasks?id=__basic_auth_probe__` 返回 404；该请求用于验证 Basic Header 已越过 Mock 认证边界，不是影像、报告或任务链失败。

## 2026-09-05 — 报告页视觉收口后的剩余边界

- 颜色、双栏布局、证据联动和响应式已经通过当前桌面/手机/横屏验收，但仍是浏览器工程验证，不代表临床阅片可用性研究或无障碍认证。
- 当前 Mock 用 `source_task_id=diagnose-demo` 演示关联，页面病例为 `CASE-DATASET-CH07-PARALLEL`；这些演示 ID 不是生产数据库记录。
- 双链“并行”仅指 Diagnose 与 Localization 的执行时间区间重叠；Localization 创建仍必须等待 Diagnose 创建响应取得 ID，这是正确因果关系，不应为了表面同时请求而移除。
- Vite、Mock Runtime 和 Playwright 会话仍保留运行供用户查看；它们不是生产常驻服务，后续结束演示时应显式关闭。

## 2026-09-07 — 全链回归后的剩余边界

- 本轮新证据仍是“真实数据集资产 + 真实 React 前端 + Mock Runtime/OSS”；没有启动 8010、没有访问 Provider、Nacos、数据库或真实 OSS，不能升级为生产集成 PASS。
- 浏览器 console 唯一 error 仍是 Mock Basic 鉴权探针的预期 404；若后续要求 console 严格零 error，可单独调整 Mock probe 响应，但这不是当前业务链失败。
- Diagnose/Localization 的执行重叠已由精确时间戳和两个中间状态证明；创建 POST 仍必须先取得 Diagnose ID，再把它作为 Localization `source_task_id`，该因果顺序不属于串行执行缺陷。
- FastAPI Runtime 的 Bearer-only 阻断已关闭；当前真实集成首要阻断仅剩 Localization Prompt Output Schema。production CORS、真实 bbox 医学正确性与医学准确率仍未关闭。
- Vite、Mock Runtime 和 Playwright `xray-fullchain-20260907` 仍保留运行供用户查看；它们不是生产常驻服务。
