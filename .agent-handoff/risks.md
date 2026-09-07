# 风险、阻断与未知项

## 2026-09-07 — Basic Auth 前端提交的剩余证据边界

- **本轮没有重跑真实外部全链**：413 个后端测试、前端 build/lint、Postman 与 launcher 检查只证明离线工程合同；新的真实 AI/OSS/Nacos/DB/Runtime 运行证据为 NOT RUN。
- **并行不是无因果同时创建**：Localization 必须引用 Diagnose `source_task_id`，两个 POST 存在短暂顺序；并行资格来自 Task 创建后的独立 Worker slot 与 AI Stage 实际执行重叠，默认 launcher concurrency=2。若部署覆盖为 1，运行时仍会串行。
- **凭证必须由部署环境管理**：仓库只保留变量名和 `.env.example` 占位；任何真实 Basic 密码、Bearer token、Private/API Key 或 signed URL 出现在 staged diff 都是提交停止条件。
- **真实证据边界不扩张**：既有 Cat 双图 Basic Auth 全链不覆盖猫狗 2–5 图矩阵、医学 Gold/准确率、Localization 医学正确性或生产 HTTPS/CORS；继续 `MEDICAL_ACCURACY_UNKNOWN / MEDICAL_RELEASE_NO_GO`。
- **目标本地分支被另一工作树占用**：`/Users/mozhicheng/workspace/code/cy-code/ms-image` 当前有独立未提交改动，禁止切换、清理、暂存或合并它们；本轮只从相同父提交 detached commit 并 fast-forward 远端。推送后该工作树的本地分支会落后远端，后续所有者需在保留其改动的前提下自行同步。

## 2026-09-07 — 前端故障恢复优化后的证据边界

- **真实网络/OSS 故障注入未运行**：当前结论来自源码合同、TypeScript/Vite 构建和静态核对；不能声称浏览器断网、Runtime 重启或 OSS PUT 中断均已真实复现通过。
- **刷新后 `File` 不可恢复是浏览器安全边界**：远端 `ready`/`validating` 影像可自动恢复；若影像仍为 `uploading` 且对象内容未完成，用户必须重新选择原文件，页面不会持久化文件字节或 signed URL。
- **恢复依赖后端当前幂等合同**：Session/Study/Series/prepare-upload 的关键输入必须保持稳定；未来若后端改变幂等键，需同步更新前端恢复合同和测试。
- **轮询仍有有界停止门**：单 Task 最多 180 次查询，连续失败退避上限 30 秒；长期不可达时会要求人工刷新，不进行无限重试。
- **医学证据没有变化**：本轮未调用 AI；R4 工程链证据仍有效，但医学准确率继续 UNKNOWN / NO-GO。

## 2026-09-07 — Basic Auth 真实全链完成后的剩余边界

- **工程全链已通过，不再受 Bearer-only 401 或 Localization Prompt Schema 阻断**：真实浏览器、Runtime Basic Auth、OSS、Quality、Diagnose、Localization 与 Report 已在同一病例完成；不要继续沿用旧快照的阻断状态。
- **医学准确率仍为 UNKNOWN / NO-GO**：单病例真实 Provider 成功、Report final 和 normalized bbox 技术合同通过，不等于 finding、器官框或病例结论具有医学 Gold 级正确性。
- **输入/观察体位冲突需人工复核**：R4 Quality 将两图观察为 `ventrodorsal`，第 1 张冻结申报为侧位；报告已将其列为限制，不能由 Python 或 UI 静默修正。
- **bbox 不是像素分割**：历史 R2 每图 9 个框；当前 R4 为 11+12=23 个 normalized bbox；没有 mask、像素轮廓或医学标注仲裁。
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
- **ReportGeneration 复制风险没有被理论消除**：Dog `1.0.4` 本次深度相等 PASS 只证明该请求成功；生成模型长期逐字符复制稳定性仍未知，truth-preserving validator 不能移除或放宽。
- **医学准确率不变**：engineering candidate 真实输入不等于 Gold；没有可信 Failure Bank、Scorer、Holdout，继续 `UNKNOWN / NO-GO`。
- **既有 teardown warning 保留**：E2E 和 launcher 温关闭仍出现 aiomysql event-loop-close 析构告警；不影响本轮已持久化结果，应在独立工程切片处理。

## 2026-09-04 — ReportGeneration v1 精确复制风险已确认

- **失败字段已确认**：Dog `1.0.4` 诊断复现中只有 `$.final_medical_result.coverage.missing_or_limited_views[0]` 不同；Gemini 把中文“和”改为英文 `and`，其余深度比较字段一致。
- **不是 Schema 或 Nacos 对齐问题**：exact Prompt `1.0.4` 动态读取成功、无 fallback，响应通过 v1 JSON Schema，顶层 SHA/status/version 正确；Schema 只能约束结构，不能表达“输出对象必须等于输入对象”。
- **继续堆 Prompt 仍不确定**：即使本次只错一个词，也已证明生成模型会规范化冻结字符串；多跑几次偶尔成功不能建立确定性合同。
- **原始失败可观测性仍有限**：历史业务失败正文未持久化，本次完整响应只在诊断进程内展示与比较，未落库；若未来需要长期失败字段审计，应单独设计受控、脱敏、加密的 rejected-result 证据边界。
- **v2 尚未实施**：两个摘要分片并发 + 冻结事实确定性组装目前只是用户审阅中的方案；不得描述为已有能力，也不得据此恢复展示链接口。
- **医学准确率不变**：本次只定位输出复制技术失败，不验证任何 Finding 的医学正确性；继续 `UNKNOWN / NO-GO`。
- **3.7 单次成功不是确定性保证**：同一 Dog 输入在 `gemini-3.7-flash` 上一次返回差异数 0，但没有重复样本、猫样本或 fresh 全链证据；不能据此取消 truth-preserving validator 或直接声明路由升级完成。

## 2026-09-03 — Gemini 猫狗全链通过后的当前风险

- **工程链已关闭，不等于医学准确率通过**：Fresh Cat Task `00deb1ff...` 和 Fresh Dog Task `7ec955a6...` 均 completed、唯一 final Report、task/current/history 一致；没有 Gold/Failure Bank/医学 Scorer/Holdout，医学准确率仍 `UNKNOWN / NO-GO`。
- **条件拓扑不能被误报为漏 Stage**：Cat 产生 TargetedReview candidate，走 8 Stage/5 AI Call；Dog 的 FamilyRouting=`primary_final`，合法走 7 Stage/4 AI Call。只有存在合法 candidate 时才应物化 TargetedReview。
- **ReportGeneration Prompt 版本必须保持不可变**：Cat/Dog `1.0.2` 已 online，新增规则只要求深拷贝冻结医学对象；旧 `1.0.0/1.0.1` 不覆盖、不删除。任何后续正文修订继续使用新版本。
- **不得把 Prompt 修复变成 Python 医学修正**：`report_generation_medical_result_rewritten` 首次失败通过 Prompt `1.0.2` 修复；truth-preserving validator 未放宽，后续也不得在代码中重写 Provider 医学输出。
- **旧模型 timeout 是历史风险，不再是当前 Gemini 阻断**：`gpt-5.6-sol` 曾在约 60 秒边界累计 3 次 Platform 500；本轮 Gemini 所有请求均 HTTP 200。若切回慢模型，Platform Endpoint timeout 仍需独立确认，ms-image 不加自动 retry/fallback。

## 2026-09-03 — diagnose 同一 Task 全链 PASS 后的剩余风险

- **工程闭环已通过但不是医学结论**：Task `ae3c77dd32a34a938eaee6f167d438d6` 已证明 8 Stage、5 AI Call、5 Attempt、Targeted 动态路由、ReportGeneration AI 与 final Report 的工程闭环；没有 Gold/Holdout/医学 Scorer，医学准确率仍 UNKNOWN。
- **可空审计字段不是完成门**：`stage_checkpoint_record.accepted_call_id` 当前可以为空；接受关系由 `ai_call.stage_checkpoint_id`、Call `result_disposition=accepted`、`winner_attempt_id`、Stage `source_call_id` 与 output lineage 共同证明。未来若升级为强合同，必须先改变生产持久化语义和测试。
- **Projection 仍是调用方事实**：原始 `cat-03.json` 的三张 `UNKNOWN` 与 Provider 具体投照位冲突；成功运行使用 `/tmp/ms-image-cat-03-known-projection.json`。不得通过放宽 validator、猜测像素或静默覆盖解决。
- **Runtime teardown warning 仍存在**：关闭 launcher 时曾出现既有 aiomysql event-loop-close 析构告警；不影响已持久化 PASS，但应在独立工程切片处理。
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
- **工作区受保护**：不得 reset、clean、restore、checkout 或覆盖用户/历史未提交修改。

## xray_quality_control 当前风险与 UNKNOWN

- **Prompt/Config 缺失已排除**：Cat/Dog Nacos exact `1.0.0` 与本地冻结正文 SHA 一致；DB Prompt validated、Config active。不得再把“Prompt 没上 Nacos”列为阻断。
- **当前 Runtime API 回归累计 6/6 通过**：初次 1 次及本轮追加 5 次均为 Quality POST 201、无等待立即 GET 200、取消后立即 GET 200、相同 request_id 重放返回同一 Task。当前没有其他服务报错，本问题可关闭。
- **历史首次 409 属于 Runtime，但精确子类型仍 UNKNOWN**：当时未形成 Task/Call/Attempt，也没有 Provider request；因此不是 Provider 429。旧响应未保留内部稳定错误码，不能确定是 `session_not_accepting_tasks`、`study_revision_not_ready` 或其他冲突分支。
- **response-before-commit 仅为历史根因推断**：源码时序、旧 `201 → immediate 404` 观察及当前显式事务回归共同支持该推断，但不能把缺少原始错误码的历史 409 精确原因升级为 CONFIRMED。
- **6 个回归 Task 是取消请求态而非 terminal cancelled**：Task 均 queued 且 `cancel_requested_at` 非空，Stage queued、Outbox pending；Relay/Worker 未启动，因此尚未收敛为 cancelled。未来启动 Worker 时会看到这些 pending Outbox，禁止手工改库或绕过取消合同。
- **工程链通过不等于医学通过**：Cat/Dog 均有工程链 PASS 证据，但部位、投照位和基础质量的医学准确率仍 `UNKNOWN`，医学发布 `NO-GO`。
- **Runtime teardown warning 仍为独立工程项**：本轮关闭 Runtime 时出现既有 aiomysql event-loop teardown warning，不影响已返回的 HTTP/事务证据；不得混入 Quality Prompt 或医学合同。

## 宠物档案迁移风险与 UNKNOWN

- **数据库与数据迁移已经完成，不再是 NOT_RUN**：目标 MySQL 已处于 revision `20260901_01 (head)`；三张宠物表和 5091/152/0 条目标数据均已通过实库核对。
- **源历史为空**：`vet_platform.pet_profile_history=0`，因此目标历史表保持 0；这不是漏迁，但现有 legacy 档案没有可恢复的变更历史。
- **第三方品种图片未迁为 OSS key**：874 个源图片 URL 来自 `upload.suoweilai.com`，未验证属于目标 OSS，因此目标 ORM 读取为 `image_keys_json=None`；如需展示图片，必须单独设计下载、内容校验、OSS 上传和版权/来源治理流程。
- **品种区间体重未伪造单值**：152 个源参考体重均为区间文本，目标 `reference_weight_kg` 保持空；不得用区间中点冒充事实。
- **真实 HTTP API 事务 E2E 尚未运行**：代码和全量测试已通过，导入也经 `DalBase` 写入，但创建幂等、CAS 冲突、归档/恢复和 history 原子性尚未通过真实 API 并发场景资格化。
- **既有 Alembic 无关漂移仍存在**：`alembic check` 只报告 `ai_api_connection.secret_ref` comment drift；不得把该既存项混入宠物 migration。
- **医疗域仍明确排除**：体格、病历、诊断体征和时间线未迁入；调用方不得把当前档案 API 误认为完整宠物医疗记录能力。
## 非分割阶段级 Prompt 架构风险

- 历史单 Config / Stage binding 缺口已由 code-owned Stage 路由及真实全链关闭；历史 frozen Task/replay 兼容仍须保留。
- **新发布版本已经不可变**：StudyScreening、SystemAnalysis、PrimaryCaseAdjudication、TargetedReview、ReportGeneration 的 Cat/Dog `1.0.0` 均已 exact 回读通过；任何正文修订必须新建版本并重新授权，禁止覆盖或 force publish。
- 当前 Quality 为一次多图 BatchImageQualityReview；未来若改逐图调用，必须另外建立冻结图片子集合同。
- 旧逐图 Quality 方案 N+4/N+5 不是当前 Batch 拓扑的调用数量；总预算、deadline、部分失败语义仍需独立评估。
- **阶段拆分不等于准确率提升**：12 个 Prompt 只建立职责、版本、证据和回滚边界；没有 paired A/B、Gold 或 Scorer，医学收益仍为 UNKNOWN。
- **旧 Prompt 正文并不全部可证实**：指定 commit 能确认大量 Config key 和部分本地 Markdown，但 Runtime 从 AI Config DB 获取正文；未读旧数据库的 key 必须保持 UNKNOWN。
- **旧分割依赖禁止回流**：旧 System/Crop/Report 链依赖 segmentation bbox、crop、PiP 和 annotated image；本期仅吸收职责/规则，不复制数据依赖和 17×2 crop Prompt。
- **ReportGeneration 可能重复或漂移医学事实**：当前 CompleteMedicalResult v2 已有 summary/impression；若独立报告 Prompt 新增、删除或改写 Finding/status，必须拒绝结果。Report Prompt 默认不看原图，只能组织冻结 final result。
- **Quality 工程实现已接通，Cat/Dog 工程链均有 PASS 证据**：Registry、Prompt、Task、validator、Config 和路由均已实现；工程通过仍不得外推为 Cat/Dog 医学准确率或主诊断链完整资格。

## Anatomy Localization v1 当前风险

- Cat 两图真实工程链已通过；旧 projection mismatch / Output Schema 失败保留为历史事实，不再作为当前阻断。尚未完成猫狗 2–5 图全矩阵，尤其 3–5 图完整性、超时与输出截断风险仍 UNKNOWN。
- 历史被拒 Provider 正文不可恢复，不能断言旧响应的具体 projection；不得放宽 validator 或猜测修复医学字段。
- receipt 与 normalized bbox 只证明技术覆盖；没有 Gold/Scorer，定位医学准确率仍 UNKNOWN，不能称为像素分割。
- 输入 manifest 的工程可用性不证明病例配对、投照位或医学真值。新运行保留调用方事实及模型冲突证据。
- 新 Prompt/Config 必须不可变；运行时 exact 身份和 SHA 不能由历史 handoff 代替。
- Localization 保持独立 Task、单 Logical Call/Attempt，不生成 Report、不改写诊断结果；source_task_id 必须精确关联。

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
- 真实 prepare-view 与 OSS 原图加载、短效链接重新申请已通过；不得外推为所有版本、所有对象的覆盖。

## 2026-09-03 — code-owned AI/Prompt 路由剩余风险

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
- Task 分页无 Study/Session 范围的 422 属于正常约束；带范围的 500 已定位为 DAL 漏加载 source_task_id，并在 R3 后补字段、实库与重启 HTTP 200 验证通过。
- Localization Cat 缺 Output Schema 的旧阻断已通过不可变新版本关闭；旧版本不得覆盖，历史失败不可倒写为成功。
- 真实 prepare-view 与 OSS 原图加载、短效链接重新申请已通过；不得外推为所有版本、所有对象的覆盖。
- 医学与定位准确率仍为 UNKNOWN，工程接口完成不构成医学发布资格。

## 前端认证、展示与部署剩余边界

- Runtime Basic Auth 真实验证通过；Admin 仍 Bearer-only。凭证仅留进程/页面内存，不写文件、URL、日志或浏览器持久存储。
- 开发环境 OSS 同源代理已通过真实 PUT；生产 HTTPS、同源网关/CORS、Authorization 日志脱敏仍需部署验证。
- Basic 凭证和 Vite OSS 代理目标未持久化；本地进程退出后需重新注入配置。旧会话“保留运行”不是持续可用性承诺。
- 旧 Mock 演示证据只属于历史，当前真实 Task/OSS/Provider 证据见 snapshot。数据集 Ch07 无权威病种字典，原始标签 부위표시 也不证明器官/病灶 Gold。
- 页面视觉和响应式验证不代表临床可用性或无障碍认证；数据时间戳未带时区，页面时区呈现尚需规范。
- 并行应验证 Provider Attempt 或 AI Stage 实际执行重叠；仅 Task 生命周期重叠不足。R3 查明 concurrency=1 导致 Stage 串行，现有 launcher 已改默认 2，R4 AI Stage 实际重叠已通过（15.338185 秒与 16.687040 秒）。
- readiness 的 medical_provider_ready=false 来自 core/readiness.py 固定 not_implemented 占位，尚未接入真实 Provider 资格事实；不能当作当前调用结果。
- RabbitMQ 死信队列本轮启动前已有 7 条，本轮不清理、不重放；后续需独立审计。

- R3/R4 同影像报告所见不完全一致，模型观察体位亦有 DV/VD 变化；医学重复稳定性 UNKNOWN。后端未单独提供技术质量摘要，页面如实显示缺失。
