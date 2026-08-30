# MS-Image XRay 影像 AI 全链路开发文档（API 与链路设计）

> 版本：v1.3（供评审/实现；定位为需求候选清单与接口合同参考）
> 目标项目：`/Users/mozhicheng/workspace/code/cy-code/ms-image`
> 状态：`PROPOSED`（本文档只做设计与接口合同，不生成代码/迁移/测试脚本；开发实施以 `28-xray-evidence-driven-development-guide.md` 与当前源码为准）
> 对照参考：`vet-platform`（旧平台）X-ray 链路接口与 git 演进
> 复用原则：**能直接使用/迁移 vet-platform 的成熟能力则直接迁移，不在 ms-image 内重复实现；迁移不了的（强依赖 vet 特有表/服务）只对齐产物结构，不复制执行链。**

---

## 0. 文档目的

本文档回答一个问题：**要让 `ms-image` 从「上传一张 X 光影像」到「生成可查询的 AI 报告」完整、可复现地跑通，需要哪些 HTTP 接口，以及这些接口如何串成一条链路。**

阅读约定：

- 接口统一返回 `GenericResponse[T]`（单对象）/ `PagedResponse[T]`（分页）：`{success, message, data, error_code}`。
- 资源 ID 只放 query 参数或 request body，**不使用 `/{id}` 路径**。
- 所有接口分属 4 个 FastAPI 应用（见 §3）。
- 每个接口标注三种状态之一：
  - ✅ **现有**（代码已存在，部分已真实跑通）
  - 🆕 **新增**（需要开发）
  - 🔧 **调整**（现有接口需改造）

---

## 1. 最终链路总览（目标）

```text
┌─────────────────────────── 控制面（一次性/低频）───────────────────────────┐
│ 发布 Prompt → 建 Connection → 建 ModelPool → 编译并激活 Config             │
└───────────────────────────────────────────────────────────────────────────┘
                                    ↓（Task 冻结引用 active Config）
┌─────────────────────────── 在线诊断主链（每次病例）────────────────────────┐
│ Session → Study → Series → Image(OSS直传) → 影像校验 → Study finalize     │
│   → 创建 diagnose Task → Outbox → RabbitMQ → Worker → AI Platform/Provider │
│   → Attempt/Call → Stage → DecisionFinalization → Report(final)           │
└───────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────── 交付与治理（查询/发布/评测）────────────────────┐
│ 查询 Report →（可选 Admin publish）→ Evaluation/医学基线 → release-state   │
└───────────────────────────────────────────────────────────────────────────┘
```

**主链已真实跑通的证据**（2026-08-27 本机非 Docker，task_id `8ca384148d8440fa88ee01bfda81c9dc`）：

```text
Session -> Study -> Series -> prepare-upload -> OSS PUT(200)
-> complete-upload -> ImageValidationWorker(ready) -> finalize(ready)
-> diagnose Task(species=dog) -> Outbox -> RabbitMQ -> execute_stage
-> ms-ai-platform -> Attempt(succeeded, actual_model=gemini-3.5-flash)
-> 3 Stage completed -> Report(final/produced) -> Task(completed/produced)
```

---

## 2. 现状事实（已实现 vs 缺口）

### 2.1 已具备的代码能力（勿重复建设）

- 分层：`API -> Service -> DalBase CRUD -> Model/DB`，事务内禁止 OSS/Broker/Provider 网络 I/O。
- Prompt 控制面：Prompt 导入、Connection、ModelPool、不可变 Config 编译/激活/回滚。
- Task 冻结：`species`、Study revision、manifest、Config/Prompt/Schema/模型池/Pipeline 哈希、`request_sha256`。
- 可靠执行：Outbox（事务发件箱）→ Relay → RabbitMQ → Celery Worker；Stage lease/CAS；Attempt 幂等；unknown 不盲发；取消/迟到结果保护。
- 报告：不可变 `final` 报告 + Admin publish/void + 授权查询。

### 2.2 本次新增/调整的驱动（四个真实缺口，按严重度排序）

0. **状态合同错误（最优先）**：`JointPrimaryReader` 把 Stage 输出 `medical_status` 写成 `produced`（`joint_primary_reader.py:53`），`DecisionFinalization` 原样复制（`decision_finalization.py:23`），导致 `task_record.ai_medical_status` 与 `report_record.medical_status` 存了 **`produced`**——不在任何医学枚举（`not_produced/normal/abnormal/review_required/non_diagnostic`）中，会直接阻断 Evaluation Export 与 M1 医学基线。模型真实判定在 `complete_medical_result.medical_status`（如 `review_required`），需把该值正确投影到 Task/Report 层。
1. **医学元数据断供**：`TaskCreate` 只收 `species`，`ImagePrepareUploadRequest` 无逐图 `projection`；Prompt 依赖的 `view_positions/coverage/clinical_context` 在真实 Snapshot 中**全为空**。注意：模型已能一次收多张影像（`ai_request_service.py:1545 _load_attempt_image_inputs`），缺的是**逐图投照位与临床上下文的可靠数据链**，不是多图输入能力。
2. **上游对接入口缺失**：vet-platform 习惯「一步传 session + 影像列表 + 主诉」，而 ms-image 目前要求上游自己串 5 步（§5.6 需按两步式设计，见下）。
3. **治理闭环缺失**：无 release-state（shadow/gray/active）灰度（M1 后置）；报告无用户可读正文（summary 须由模型输出字段产生，Python 只做投影透传）。

> 说明：GPT-5.6-Sol 评审意见已逐条核实并入本文档（见 §13 评审对照）。其中：状态合同错误、元数据断供、Task 列表路径冲突、一步编排自相矛盾、projection_summary_json 派生缓存风险、fixed-bank 重复、Python 概括 summary 不安全——全部采纳并已修订。

---

## 3. 服务与鉴权边界

| FastAPI 应用 | 端口/前缀 | 鉴权 | 职责 |
|---|---|---|---|
| Runtime `app` | `/api/v1` | `imaging:run`（Runtime JWT RS256） | 用户端：影像/任务/报告 |
| Admin `admin_app` | `/api/v1` | `xray:admin:*`（Admin JWT HS256） | 管理员：报告 publish/void、运营状态 |
| AI Control `app` | `/api/v1` | `xray:admin:write`（ControlPlane JWT） | Prompt/Connection/ModelPool/Config 控制面 |
| Evaluation Control `app` | `/api/v1` | `xray:evaluation:*`（ControlPlane JWT） | 评测 Job/Run/Artifact |

> 说明：本地开发用 `scripts/dev/` 生成的 dev 密钥跑通；正式 JWT 密钥生命周期资格化仍在 P1 待办（见 §8.4）。

---

## 4. 接口全量清单（与链路对齐）

### 4.1 健康与就绪

| 方法 | 路径 | 状态 | 链路位置 |
|---|---|---|---|
| GET | `/api/v1/health` | ✅ | 存活探针 |
| GET | `/api/v1/version` | ✅ | 版本 |
| GET | `/api/v1/readiness` | ✅ | 依赖就绪（MySQL/OSS/Broker/Provider 等） |

### 4.2 Session（会话）

| 方法 | 路径 | 状态 | 说明 |
|---|---|---|---|
| POST | `/api/v1/sessions` | ✅ | 创建会话（`source_system/source_session_id/subject_id/request_id/started_at`），幂等键 request_id |
| GET | `/api/v1/sessions?id=` | ✅ | 查询会话 |
| POST | `/api/v1/sessions/complete` | ✅ | 完成会话（`id/expected_state_version`） |
| POST | `/api/v1/sessions/close` | ✅ | 关闭会话 |
| POST | `/api/v1/sessions/cancel` | ✅ | 取消会话 |
| 🆕 POST | `/api/v1/sessions/context` | ~~🔧🆕~~ | 已取消：并入 5.3 `POST /tasks` 的 `clinical_context`（见 §11.2） |

### 4.3 Study / Series（检查 / 序列）

| 方法 | 路径 | 状态 | 说明 |
|---|---|---|---|
| POST | `/api/v1/studies` | ✅ | 创建 Study（`session_id/modality_type/body_part/metadata_schema_version/expected_image_count/identity_status`…）；session 自动转 `processing` |
| GET | `/api/v1/studies?id=` | ✅ | 查询 Study 详情（含 series 列表） |
| POST | `/api/v1/studies/finalize` | ✅ | 定稿 ready revision（`id/expected_state_version/current_revision_id`） |
| POST | `/api/v1/series` | ✅ | 创建 Series（`study_id/series_key/series_no/metadata_schema_version/expected_image_count`…） |

### 4.4 Image（影像与 OSS 直传）

| 方法 | 路径 | 状态 | 说明 |
|---|---|---|---|
| POST | `/api/v1/images/prepare-upload` | 🔧 | **见 §5.2**：签发 OSS signed URL；入参需增加逐图 `projection` |
| POST | `/api/v1/images/complete-upload` | ✅ | 确认上传完成、触发校验（`id/expected_state_version/generation/trace_id`） |
| GET | `/api/v1/images?id=` | ✅ | 查询影像（含 status/object_key/sha256/size/content_type） |
| POST | `/api/v1/images/abort-upload` | ✅ | 终止上传 |
| POST | `/api/v1/images/replace` | ✅ | 替换影像（版本化） |
| POST | `/api/v1/images/replace-multipart` | ✅ | 替换（分片） |
| POST | `/api/v1/images/prepare-multipart-upload` | ✅ | 分片上传准备 |
| POST | `/api/v1/images/prepare-upload-parts` | ✅ | 分片签名 |
| POST | `/api/v1/images/list-upload-parts` | ✅ | 查询分片（当前 XRay 单图直传未使用，见 §11） |

> 影像状态机：`uploading -> validating -> ready | quarantined | failed`

### 4.5 Task（诊断任务）

| 方法 | 路径 | 状态 | 说明 |
|---|---|---|---|
| POST | `/api/v1/tasks` | 🔧 | **见 §5.3**：创建诊断任务；入参需增加临床上下文 |
| GET | `/api/v1/tasks?id=` | ✅ | 查询任务（execution_status/ai_medical_status/stage 摘要/error_code） |
| POST | `/api/v1/tasks/cancel` | ✅ | 取消（`id/expected_state_version/reason`） |
| 🆕 GET | `/api/v1/tasks?session_id=` | 🆕 | **见 §5.4**：按 session 列出任务 |

> 任务状态机：`queued -> running -> completed | failed | cancelled | dead_letter`；医学状态 `not_produced -> produced`

### 4.6 Report（报告）

| 方法 | 路径 | 状态 | 说明 |
|---|---|---|---|
| GET | `/api/v1/reports?id=` | ✅ | 按 report_id 查报告（鉴权校验 requester） |
| GET | `/api/v1/reports/history?task_id=` | ✅ | 按 task 查报告历史 |
| 🆕 GET | `/api/v1/reports/view?task_id=` | 🆕 | **见 §5.5**：返回用户可读报告视图（含正文摘要） |
| POST | `/api/v1/admin/reports/publish`（Admin） | ✅ | 发布报告 |
| POST | `/api/v1/admin/reports/void`（Admin） | ✅ | 作废报告 |

> 报告状态机：`final -> published | superseded | void`

### 4.7 诊断编排（上游两步接入，暂缓）

| 方法 | 路径 | 状态 | 说明 |
|---|---|---|---|
| 🆕 POST | `/api/v1/xray/diagnosis-plans` | 🆕 | **见 §5.6**：第一步，创建上传计划（Session/Study/Series/Image 计划 + signed URL） |
| 🆕 POST | `/api/v1/xray/diagnosis-commits` | 🆕 | **见 §5.6**：第二步，finalize + 创建 Task，返回 task_id |

### 4.8 AI 控制面（Prompt/Connection/ModelPool/Config）

| 方法 | 路径 | 状态 |
|---|---|---|
| POST/PUT | `/api/v1/ai-prompts`、`/detail`、`/page`、`/validate`、`/retire` | ✅ |
| POST | `/api/v1/ai-prompts/import` | ✅ |
| POST/PUT | `/api/v1/ai-connections`、`/detail`、`/page`、`/validate`、`/retire` | ✅ |
| POST/PUT | `/api/v1/ai-model-pools`、`/detail`、`/page`、`/validate`、`/retire` | ✅ |
| POST | `/api/v1/ai-configs/compile-preview` | ✅ |
| POST | `/api/v1/ai-configs`、`/detail`、`/page`、`/active`、`/validate`、`/activate`、`/retire`、`/rollback` | ✅ |
| GET | `/api/v1/ai-control-audits/page` | ✅ |
| 🆕 GET | `/api/v1/ai-configs/release-state` | 🆕 **见 §5.7** |
| 🆕 POST | `/api/v1/ai-configs/release-state` | 🆕 **见 §5.7** |

### 4.9 评测控制面（Evaluation）

| 方法 | 路径 | 状态 |
|---|---|---|
| POST | `/api/v1/evaluation/jobs` | ✅ |
| POST | `/api/v1/evaluation/jobs/export` | ✅ |
| GET | `/api/v1/evaluation/jobs`、`/jobs/cancel` | ✅ |
| POST | `/api/v1/evaluation/runs`、`/runs`、`/runs/detail` | ✅ |
| GET | `/api/v1/evaluation/artifacts`、`/artifacts/detail` | ✅ |
| ~~🆕 POST~~ | ~~`/api/v1/evaluation/validations/fixed-bank`~~ | ❌ 已撤销（§5.8：复用现有 Job/Run/Artifact） |
| ~~🆕 GET~~ | ~~`/api/v1/evaluation/validations`~~ | ❌ 已撤销 |

### 4.10 运营（Admin）

| 方法 | 路径 | 状态 |
|---|---|---|
| GET | `/api/v1/status`、`/info`、`/readiness` | ✅ |
| GET | `/api/v1/operations/status` | ✅ |

---

## 5. 新增/调整接口详细需求

### 5.1 ~~POST /api/v1/sessions/context —— 临床上下文~~（已并入 5.3，见 §11.2）

> **修订**：独立 `sessions/context` 接口取消，临床上下文统一走 §5.3 `POST /tasks` 的 `clinical_context` 入参，避免重复实现与额外字段迁移。

### 5.2 🔧 POST /api/v1/images/prepare-upload —— 逐图投照位（完整数据链：Image → manifest → Snapshot → Prompt）

- **目的**：修复 Prompt 的 `view_positions/anatomy_regions` 断供；支持「一个 Study 多张不同投照位图」的多视图联合主读。
- **多视图语义（必须明确）**：
  - 一个 Study 可包含多张图（同一 Series 多张，或跨 Series）；每张图是同一检查的**一个投照位**（LAT 侧位 / VD 腹背位 / DV 背腹位 / AP / PA…）。
  - 模型在 **Primary Prompt 内**做多视位互证（正交视图交叉确认病灶、防止单视位过度判断）——这是已实现的模型行为（`prompts/.../primary/common/...v1.0.0.txt` 第四节），**不依赖体位识别**。
  - 模型已能一次收到全部影像（`ai_request_service.py:1545 _load_attempt_image_inputs`），缺的是**逐图投照位的可靠数据链**。
- **新增入参字段（仅逐图有证据的字段）**：
  ```json
  {
    "projection": "LAT"               // 投照位：LAT/VD/DV/AP/PA，对应 model.image.projection
  }
  ```
  > 字段统一叫 **`projection`**（与 `image_record.projection` 一致），不引入 `projection_hint` 词汇（GPT 二轮评审第 4 条）。
  > 注意：`body_part`、`study_date` 已在 Study 层（`study_record.body_part`、`acquired_at`），**不复制到每张 Image**，避免重复事实源。
- **完整数据链（四层都要改，缺一不可）**：
  1. **Image 层**：写入 `image_record.projection`（现有列，当前无写入路径）；
  2. **Manifest 层**：`build_series_manifest`（`manifest.py:68`）的 required 字段**新增 `projection`**，使 canonical manifest 携带逐图投照位（注意：manifest 变化会改变 `manifest_sha256`，需同步验证旧 Snapshot 兼容与 Provider 实际发送顺序对账）；
  3. **Snapshot 层**：`_build_request_snapshot`（`task_service.py:377`）由「逐 Series 摘要」扩展为「逐图事实」（series 内 images 列表含 id/sequence_no/projection/sha256），Task 创建时经 `ImageDal` 聚合当前 ready Images（不新增派生缓存列）；
  4. **Prompt 层**：`_base_context`（`prompt_commands.py:143`）的 `ordered_image_refs` 由「逐 Series」改为「逐图」（每图含 `image_ref/projection/sequence_no`），并输出 `view_positions`（逐图列表）。
- **多视图来源双轨制**：
  - **主路径（上游标注）**：`projection` 由上游拍片端/调用方提供，最可靠、零额外模型成本（vet 已验证：正确标注可识别「侧位+正位=正交互补视图对」）。
  - **兜底（AI 体位识别，本期不做）**：仅当标注缺失时才允许（可借鉴 vet `xray_detection_helper.detect_and_verify_body_part`，其 `enable_race=True`），识别结果须通过防污染校验后才进 Snapshot；多视位互证本身是模型行为，不依赖该识别。
- **出参**：不变（`ImageUploadTicket`）。
- **验收**：`Task.request_snapshot_json` 逐图含 projection；manifest_sha256 含逐图 projection 事实；`SAFE_STUDY_CONTEXT_JSON.view_positions` 与 `ordered_image_refs` 逐图一致传到 Prompt；旧 v1 Snapshot（无 projection）可兼容重放（projection 缺省值合同明确）。
- **新增表/字段**：不需要（`image.projection` 列已存在；其余为 manifest/Snapshot/Prompt 合同内扩展）。

### 5.3 🔧 POST /api/v1/tasks —— 临床上下文入参

- **目的**：让诊断 Task 直接携带临床上下文，修复 Snapshot 中 `clinical_context_allowlist` 恒为空的缺陷（取代 5.1）。
- **新增入参字段**：
  ```json
  {
    "clinical_context": {             // 可选，白名单
      "chief_complaint": "…",
      "study_reason": "…"
    }
  }
  ```
- **处理**：冻结进 `request_snapshot_json` → `SAFE_STUDY_CONTEXT_JSON.clinical_context_allowlist`。
- **验收**：Snapshot 含上下文，Prompt 可消费；不含 ABN/NOR 标签、疾病码、历史结论。
- **来源审计（GPT 二轮评审第 5 条）**：字段白名单不够——自由文本仍可能夹带 Gold 答案、未来报告或病种标签。M1/A-B 前必须记录 `clinical_context` 的**来源与诊断时点**（谁在何时提供），评测时按来源审计污染；上下文仅作"允许使用的临床背景"，不得覆盖图像证据。
- **新增表/字段**：不需要（Snapshot 是 JSON 列，新增 Snapshot 内字段即可；如需独立持久化再评估）。

### 5.4 🆕 GET /api/v1/tasks/page?session_id= —— 任务列表（分页）

- **目的**：上游一次看某个 session 的全部任务状态（对应 vet `/x_ray/xray_task_list`）。
- **路径**：`/tasks/page`（**不用** `/tasks?session_id=`——`GET /tasks?id=` 已占用该路径，见 `tasks.py:26`）。
- **入参**：`session_id`（必填）+ 分页参数（`page/limit`）。
- **出参**：`PagedResponse[TaskResponse]`。
- **处理**：`TaskService -> TaskDal` 查询（不绕过分层）。
- **验收**：按 session 过滤、分页、按 created_at 倒序。

### 5.5 🆕 GET /api/v1/reports/view?task_id= —— 报告视图（纯投影 + 分割展示）

- **目的**：返回用户可读报告视图（vet `/x_ray/v2/reports/{session_id}` 的 decision/summary/disease_list），并**展示器官分割结果**（"秀肌肉"用途，不参与识别链路）。
- **summary 安全约束（GPT 评审第 9 条）**：`complete_medical_result.schema.json` 嵌套结构无约束，**Python Renderer 只做格式化和透传，不得自己概括医学结论**。真正的摘要/印象字段（`summary`/`impression`）应由**版本化输出 Schema 增加模型输出字段**产生（Schema v2 收紧时一并做）；报告视图只投影该字段，字段缺失时返回 null。
- **分割展示方式（派生 Image 合同，不新建表、不依赖 vet 在线）**：
  - 分割产物（标注图/器官裁剪图）作为 `image_role=segmentation` 的**派生 Image** 通过现有 `POST /images/prepare-upload` 入库（schema 已强制非 original 图带 `source_manifest`，指向原图）；
  - 结构化分割元数据（`organs/routing`）放入 `image_record.technical_metadata_json`（现有 JSON 列）；
  - vet 生成产物 → 一次性导入 ms-image（**不是每次请求在线调 vet**，符合 decisions.md「vet 不作目标线上游」）；
  - 报告视图聚合该 Study 下 `segmentation` 角色的 Image 展示。
- **P2 合同缺口声明（GPT 二轮评审第 7 条）**：派生 Image 只是存储方向，**还不是完整功能合同**——仍需定义：严格 segmentation metadata Schema（organs/bbox/confidence 字段校验）、产物版本与来源引用、按 Study 的查询聚合、对象授权与生命周期（展示 URL 签名/过期）、报告投影规则。**本接口归 P2，不阻塞 E1/M1；在合同补齐前不实现。**
- **执行顺序（GPT 二轮评审第 6 条）**：`Task page`（§5.4）与 `Report view`（§5.5）**不阻塞 E1/M1**，应等 `CompleteMedicalResult v2` 收紧 Finding/Coverage/SourceRef 并由模型稳定输出 summary/impression 后再做。
- **出参**：
  ```json
  {
    "task_id": "…",
    "report_id": "…",
    "status": "final",
    "medical_status": "review_required",     // 修正后为真实医学枚举值（见 §5.10）
    "summary": "…",                          // 模型输出字段投影；缺失为 null
    "findings": [ … ],
    "review_required": true,
    "segmentation": {                        // 分割展示（可空；不参与识别/医学判定）
      "images": [
        {
          "image_id": "…",
          "image_view": "LAT",
          "annotated_object_ref": "…",       // 派生 Image 的 ObjectRef（ms-image 自有 OSS）
          "organ_count": 6,
          "organs": [ { "name": "…", "bounding_box": [x,y,w,h], "confidence": 0.92 } ],
          "cropped_images": { "organ_key": "object_ref", … }
        }
      ]
    }
  }
  ```
- **处理**：
  1. 只读投影 `Report.content_json` + 聚合 segmentation 派生 Image；
  2. `summary` 投影模型输出字段，Python 不概括；
  3. 分割展示字段**只做透传**，绝不进入医学判定、不参与 `medical_status`、不写回 Prompt。
- **新增表/字段**：**不需要**（复用 `image_record`（segmentation role + technical_metadata_json）+ 现有上传接口）。
- **验收**：分割产物可展示；分割缺失时 `segmentation` 为 null；分割不影响医学结果；summary 与模型输出逐字一致或为 null。

### 5.6 🆕 POST /api/v1/xray/diagnosis-plans + diagnosis-commits —— 上游两步接入（暂缓）

- **目的**：vet-platform 上游简化接入。**注意**：一次请求既返回 Task ID、又等待客户端 PUT/complete/异步校验/finalize 是自相矛盾的（GPT 评审第 7 条）；若服务端直接读取 `image_url` 还有 SSRF/来源白名单/OSS 所有权问题。
- **设计（两步式）**：
  ```text
  第一步 POST /xray/diagnosis-plans
    入参：request_id/species/body_part/clinical_context/images[{source_image_id, projection, ...}]
    处理：创建 Session/Study/Series/Image 上传计划，返回
          {plan_id, images[{image_id, signed_url, generation}]}
    （客户端逐图 PUT → complete-upload → 等校验 ready）
  第二步 POST /xray/diagnosis-commits
    入参：{plan_id, expected_state_version}
    处理：finalize Study → 创建 diagnose Task，返回 {task_id}
  ```
- **状态**：⚠️ **暂缓**——先确定真实上传模式（上游是否用 signed URL 直传）与调用方，再实施；主链 5 步已可用，不阻塞。
- **新增表/字段**：实施时再评估（计划状态可存 request_snapshot 或独立轻表）。
- **备选**：若上游愿意直接串现有 5 步 API，则本接口不需要。

### 5.7 🆕 GET/POST /api/v1/ai-configs/release-state —— 发布治理（M1 后）

- **目的**：对齐 vet V3 的 shadow/gray/active 灰度状态机，防止候选链误上生产。
- **GET 入参**：`config_key`。
- **POST 入参**：
  ```json
  {
    "config_key": "xray_diagnose",
    "action": "transition",            // transition | rollback
    "target_state": "gray",            // shadow | gray | active
    "rollout_percentage": 10.0,
    "candidate_fingerprint": "sha256",
    "holdout_fingerprint": "sha256",
    "chain_policy": "accuracy_core_v1"
  }
  ```
- **处理**：校验 fingerprint/holdout → 写审计 → 变更 release state；`active` 需 holdout 门禁通过。
- **新增表/字段**：需要（release state 持久化，或复用 config `status` 扩展 + 审计表）。

### 5.8 ~~POST/GET /api/v1/evaluation/validations —— Fixed-bank 验证计划~~（已撤销）

> **撤销理由（GPT 评审第 10 条，已核实）**：现有 Evaluation Job 已含 `dataset_fingerprint/gold_fingerprint/scorer_fingerprint/experiment_fingerprint/case_split/denominator_contract`（`schemas/evaluation.py:49-57`）。真正缺的是可信 Gold、真实 scorer、可用 Evaluation DB 与正确的 Report medical status，不是再包一层 API。**复用现有 `/evaluation/jobs|runs|artifacts`**。

### 5.9 ~~POST /api/v1/images/segmentation —— 分割产物接收~~（已改为派生 Image 合同）

> **修订（GPT 评审第 8 条 + 用户"分割保留展示"意图的调和）**：不新建专用接口、不新建表、不依赖 vet 在线。分割产物作为 `image_role=segmentation` 的**派生 Image**，走现有 `POST /images/prepare-upload`（schema 已强制非 original 图带 `source_manifest` 指向原图）；结构化分割数据放 `image_record.technical_metadata_json`；报告视图（§5.5）聚合展示。vet 产物一次性导入 ms-image 自有 OSS，不成为在线依赖（符合 `decisions.md`「vet 不作目标线上游」）。

### 5.10 🔧 状态合同修复 —— Task/Report medical_status 不再写 `produced`（最优先）

- **问题（GPT 评审第 1 条，已核实）**：`JointPrimaryReader`（`joint_primary_reader.py:53`）输出 `medical_status="produced"`，`DecisionFinalization`（`decision_finalization.py:23`）原样复制，导致 `task_record.ai_medical_status` 与 `report_record.medical_status` 存了 `produced`——不在任何枚举（`not_produced/normal/abnormal/review_required/non_diagnostic`）中，直接阻断 Evaluation Export 与 M1 医学基线。真实判定在 `complete_medical_result.medical_status`（2026-08-27 实测为 `review_required`）。
- **修复合同**：
  1. 唯一医学枚举（持久化层）：`normal / abnormal / review_required / non_diagnostic`，未产生结果时 `not_produced`；
  2. **在持久化边界投影**（`ImagingExecutionService -> ReportService` 边界）：Task/Report 层 `medical_status` 从 `complete_medical_result.medical_status` 投影，**拒绝 `produced`**；不修改已冻结的 v1 Stage 内部语义（Stage 内部可继续用 `produced/not_produced` 表达"是否产出结果"）；
  3. `DecisionFinalization` 只选择并校验唯一 owner，不复制 Stage 内部标记；
  4. 存量数据修正：**单独授权**后才对已有 `produced` 行做数据修正（先确认嵌套 `complete_medical_result.medical_status` 存在合法值再回填）。
- **新增表/字段**：不需要。
- **验收**：新 Task/Report 的 medical_status 恒在枚举内；存量 `produced` 清零（需单独授权）。
- **边界声明（不夸大）**：状态修复**只保证新数据正确**；Evaluation Export 仍受 `ms_image_eval` 库、可信 Gold、真实 Scorer、分母合同与 Artifact signing 约束——修完不等于可评测（GPT 二轮评审第 3 条）。

---

## 6. 数据模型与状态机（摘要）

### 6.1 核心状态机

| 实体 | 状态 |
|---|---|
| Session | `open / processing / completed / closed / cancelled` |
| Study | `ingesting / validating / ready / invalid` |
| Image | `uploading / validating / ready / quarantined` |
| Task | `queued / running / completed / failed / cancelled / dead_letter` |
| AI medical（持久化） | `not_produced / normal / abnormal / review_required / non_diagnostic`（`produced` 是 Stage 内部标记，不得持久化——见 §5.10） |
| Stage | `queued / running / completed / failed / cancelled / dead_letter` |
| Attempt | `prepared / pending / succeeded / failed / unknown` |
| Report | `final / published / superseded / void` |
| Config | `draft / validated / active / retired` |
| Release state | `shadow / gray / active` |

### 6.2 幂等与取消（已实现，勿破坏）

- Task 幂等：`requester_id + request_id + task_type -> business_key`；同键复用，异键冲突。
- Stage/Outbox 幂等：确定性 event_key + idempotent create。
- 取消：`cancel-before-provider` 与 `provider-sent late-result` 均真实通过。
- unknown：按原 Provider 幂等身份查询，不盲发；unsupported 时延后重排。
- 迟到结果：不覆盖 cancelled/terminal 状态；Winner 经 CAS。

---

## 7. 端到端调用序列（接口级）

### 7.1 主链（逐接口，已跑通）

```text
POST /sessions
POST /studies
POST /series
POST /images/prepare-upload        -> {signed_url, image_id, generation}
  （客户端 PUT bytes -> OSS）
POST /images/complete-upload       -> {image status=validating}
  （Worker 校验） GET /images?id=  -> {status=ready}
POST /studies/finalize             -> {study status=ready, revision_id}
POST /tasks {species, clinical_context} -> {task_id, execution_status=queued}
GET /tasks?id=                     -> 轮询到 completed
GET /reports/history?task_id=      -> report(final)
GET /reports/view?task_id=         -> 用户可读视图
```

### 7.2 上游两步接入（§5.6，暂缓）

```text
POST /xray/diagnosis-plans          -> {plan_id, images[{image_id, signed_url, generation}]}
  （客户端逐图 PUT → complete-upload → 等校验 ready）
POST /xray/diagnosis-commits        -> {task_id}
GET /tasks?id=                      -> 轮询
GET /reports/view?task_id=
```

### 7.3 控制面（低频）

```text
POST /ai-prompts/import            -> prompt 入库
POST /ai-connections               -> Connection
POST /ai-model-pools               -> ModelPool
POST /ai-configs/compile-preview
POST /ai-configs                   -> 编译
POST /ai-configs/activate          -> active Config
（release-state 见 §5.7，M1 后）
```

### 7.4 评测（M1 阶段，复用现有 Evaluation，不新增 fixed-bank API）

```text
POST /evaluation/jobs/export       -> 导出在线产物为评测输入
POST /evaluation/jobs              -> 创建 Job（dataset/gold/scorer fingerprint + denominator contract）
POST /evaluation/runs              -> 创建 Run
GET  /evaluation/runs/detail       -> 查询 Run 结果
GET  /evaluation/artifacts         -> 查询产物
```

---

## 8. 实施顺序与门禁（GPT 评审后修订）

> 开发以 `28-xray-evidence-driven-development-guide.md`（证据驱动开发指南）为准；本节仅作 27 号内部的顺序摘要。完整顺序：

```text
C1 状态持久化合同修复（§5.10，最优先）
-> P1 剩余运行资格（自动 reconcile、unknown 有界终止、JWT、Artifact signing）
-> CompleteMedicalResult v2（Schema 收紧 + 模型输出 summary/impression）
-> 逐图 projection 四层数据链（§5.2）
-> clinical context（§5.3）
-> 真实多视图 E1 重放
-> M1 医学基线（Gold/Failure Bank/Holdout，复用现有 Evaluation）
-> 单变量 Prompt A/B -> 单变量 Model A/B
-> Task page / Report view / 分割展示（P2）/ 两步接入（最后，不阻塞医学验证）
```

| 阶段 | 内容 | 依赖/授权 |
|---|---|---|
| C1 | §5.10 状态合同修复（持久化边界投影，拒绝 `produced`；存量数据修正单独授权） | 无表变更 |
| P1 收口 | ① 自动 reconcile 调度；② unknown 有界终止（字段/迁移）；③ JWT/Artifact signing | ①无授权；②③需确认 |
| Schema v2 | 收紧 Finding/Coverage/SourceRef 嵌套 + 模型稳定输出 summary/impression | 无表变更 |
| 元数据链 | §5.2 逐图 projection（统一叫 `projection`，不引入 `projection_hint` 词汇）→ §5.3 clinical context（来源审计） | 无表变更 |
| E1 重放 | 真实多视位病例重跑，验证 Snapshot/Prompt/Provider 一致 | 无 |
| M1 | 复用现有 Evaluation Job/Run/Artifact；`ms_image_eval` 库、Gold、Scorer、分母合同 | M1 再建 |
| P2 展示 | Task page、Report view、分割展示、两步接入——**均不阻塞 E1/M1** | 逐项确认 |

---

## 9. 医学与安全边界（必须保持）

- Python 只做确定性校验、路由、打包、Schema 验证、持久化、审计；**不改写** `normal/abnormal/review_required/non_diagnostic`。
- 医学准确率保持 `UNKNOWN`；无 Gold/Holdout 前 `MEDICAL_RELEASE=NO-GO`。
- `AI_PLATFORM_API_KEY`、OSS Access Key、签名 URL、Provider 原始响应正文 **不得**进入 DB/Nacos/Task Snapshot/日志/审计。
- 影像字段 `study_event_key/view_code` 禁 ABN/NOR、数据集病种码、目录标签。
- Provider/OSS 网络 I/O 在事务外；数据库访问统一走 `DalBase`。
- 新表遵循：独立非空 `id VARCHAR(64)` 主键、无外键、无 enum、无 tenant_id、字段 comment 写候选类型+中文含义。

---

## 10. 最终判定

| 维度 | 状态 |
|---|---|
| 主链（上传→报告） | ✅ 已真实跑通（本机非 Docker） |
| 接口完整性 | 🟡 最小闭环：§5.10 状态合同修复 + 4 个接口改动（§5.2/5.3/5.4/5.5）；§5.6 两步式暂缓；§5.7 M1 后；§5.8/§5.9 已撤销/改派生合同 |
| 数据库 | ✅ 本期零表变更、零迁移（GPT 评审后收敛）；仅 P1 收口需 unknown 有界终止字段（授权后） |
| RUNTIME_QUALIFIED | `PARTIAL`（P1 未完全关闭） |
| MEDICALLY_VALIDATED | `UNKNOWN` |
| MEDICAL_RELEASE | `NO-GO` |

**下一步最小闭环**：先做 §5.10（状态合同修复，最优先）→ §5.2（逐图投照位四层数据链）→ §5.3（临床上下文）→ §5.4（任务列表）→ §5.5（报告视图纯投影 + 分割派生 Image 展示）。全部零表变更；完成后用真实多视位病例重跑 E1 验证。

---

## 11. 冗余与过度设计审查（本次检查结论）

> 目标是「先跑通 XRay 主链」，不是「先建一套通用影像平台」。以下逐项判定：**哪些现有代码是过度设计（可暂缓/可砍），哪些本文档新增项是冗余（应撤回）**。

### 11.1 现有代码中的过度设计（可暂缓，但本轮不删除）

| # | 项目 | 现状证据 | 判定 | 建议 |
|---|---|---|---|---|
| 1 | **分片上传整套链路** | `images.py` 有 `replace-multipart / prepare-multipart-upload / prepare-upload-parts / list-upload-parts` 4 个端点；`image_upload_workflow.py` 29 处 multipart、`image_service.py` 58 处、schema 7 处 | ⚠️ **对当前 XRay 是过度设计**：单张 X 光 JPEG 约 150KB，`MAX_IMAGE_BYTES=64MB`，`direct_put` 直传完全够用；分片是为 WSI/大视频预留的 | **保留代码不动**（已存在、不新增维护成本），但**接口清单中降级为「预留」**，本期不接、不测试、不在主链使用 |
| 2 | **`replace / replace-multipart` 影像替换** | 版本化替换接口已存在 | ⚠️ 当前主链（首诊 XRay）用不到；只有「改图重传」才需要 | 保留，标记预留 |
| 3 | **Session 的 complete/close 双操作** | `complete`（processing→completed）+ `close`（completed→closed） | ⚠️ 两级终态，当前单次诊断场景用 `complete` 即可，`close` 是业务归档语义 | 保留；主链不依赖 close |
| 4 | **Evaluation 4 张表在主库（与 eval 库设计冲突）** | `async_db.py:14-16` 强制 `MYSQL_EVALUATION_DB != MYSQL_DB`，但 `.env` 无 `MYSQL_EVALUATION_DB`，且 `evaluation_*` 4 张表**已建在主库 ms_image**（`information_schema` 实测） | 🔴 **事实矛盾**：eval engine 指向不存在的 `ms_image_eval` 库，表却落在主库 | 见 §11.3 第 3 条——本期**不做评测**，`ms_image_eval` 库先不建；等 M1 再统一 |

### 11.2 本文档新增项中的冗余（应撤回/合并）

| # | 原新增项 | 问题 | 修正 |
|---|---|---|---|
| 1 | `🆕 POST /images/complete-multipart-upload` | **多余**：`ImageCompleteUploadRequest` 已带 `parts` 字段，分片完成本就复用 `complete-upload` | ✅ 已从文档删除 |
| 2 | `🆕 POST /sessions/context`（§5.1） 与 `POST /tasks` 加 `clinical_context`（§5.3） | **二选一即可，两个都做是重复**：上下文最终都进 Task Snapshot | ✅ 合并为**一个**：优先走 `POST /tasks` 加 `clinical_context`（§5.3），**取消** §5.1 的独立 `sessions/context` 接口，省一个字段迁移 |
| 3 | `🆕 POST /xray/diagnoses` 一步编排 | 一步受理自相矛盾（无法既返回 Task ID 又等客户端 PUT/校验/finalize）+ `image_url` 有 SSRF 风险 | ✅ 改为**两步式**（`diagnosis-plans` + `diagnosis-commits`，§5.6）并暂缓 |

### 11.3 明确「本期不做」的项（避免抢跑）

| 项目 | 理由 |
|---|---|
| TargetedReview / FamilyRouting | 属于 M2，主链不需要 |
| Retry / Fallback / Race | 需要先有 unknown 查询能力 + 第二 Provider 资格化（vet 已在其 V1 网格链用 `enable_race=True, race_count=5` 做多供应商竞速，见 commit `6d1dd28`；ms-image 主链单 Provider 单 Attempt，R3 才需要） |
| `ms_image_eval` 独立库 + fixed-bank 验证 | 属于 M1 医学基线阶段，主链工程闭环不需要 |
| `release-state` 灰度治理（§5.7） | 当前只有单 Config 单 Provider，shadow/gray/active 灰度是 M1 之后的事；**本次从「第一优先」降为「后置」** |
| AI 体位识别兜底 | 主路径是上游标注；AI 识别（vet `xray_detection_helper.detect_and_verify_body_part`，`enable_race=True`）仅作兜底，**本期不做**，M1 后按需迁入 |
| 多模态（CT/MRI/超声等）AI Runtime | 只有 XRay 有专用 Stage/Prompt，其余仅 modality 枚举 |

### 11.4 结论：真正的最小闭环（GPT 评审后修订）

```text
第一优先（状态合同，无表变更）：
  §5.10 状态合同修复：Task/Report 不再持久化 produced（最优先，阻断 Evaluation/M1）

必须做（接口级，零表迁移）：
  §5.2 逐图投照位完整数据链（Image→manifest→Snapshot→Prompt 四层）
  §5.3 Task 加 clinical_context（Snapshot 字段）
  §5.4 任务列表（GET /tasks/page?session_id=）
  §5.5 报告视图（GET /reports/view?task_id=，summary 投影模型字段；分割走派生 Image 合同）

可选（上游对接时再定）：
  §5.6 两步式上游编排（diagnosis-plans + diagnosis-commits）

后置（M1 之后）：
  §5.7 release-state、ms_image_eval 库、Targeted/Retry/Fallback/Race、AI 体位识别兜底
  （§5.8 fixed-bank 已撤销——复用现有 Evaluation Job；§5.9 已改为派生 Image 合同——不建表）
```

**GPT 评审后收敛结果：零新表、零新迁移。** 相比 v1.1 版的「5 接口 + 2 张表」，现在只需 4 个接口改动 + 1 个状态合同修复，全部复用现有列/JSON/合同；分割展示通过派生 Image（`image_role=segmentation` + `source_manifest` + `technical_metadata_json`）落地。

### 11.5 分割展示的实现决策（最终版：派生 Image 合同）

| 方案 | 说明 | 判定 |
|---|---|---|
| A. 代码级直迁 vet 分割执行链 | 强依赖 vet 特有模型表与服务 | ❌ 不可行 |
| B. vet 生成 → 新接口接收 → 新表落库 | 新接口+新表，且把 vet 变成在线依赖，违反 decisions.md | ❌ 已被 GPT 评审否决 |
| C. **分割产物 = 派生 Image（segmentation role）** | 走现有 `prepare-upload`（非 original 图强制带 `source_manifest` 指向原图）；`organ_seg` 结构放 `technical_metadata_json`；报告视图聚合展示；vet 产物一次性导入 ms-image 自有 OSS | ✅ **零新接口、零新表、不依赖 vet 在线、满足"展示"诉求** |

> 结论：选 C。执行仍留在 vet（一次性导入），展示在 ms-image 报告视图。

---

## 12. 数据库表重构建议（已获授权 + GPT 评审后修订：本期零迁移）

> 授权：用户明确「数据库的表也可以完完全全进行重构，但是前提是合理」。
> GPT 评审后结论：**本期最小闭环不需要任何表/列变更**——全部复用现有列与 JSON 合同；以下仅记录"若未来需要"的候选，M1 阶段再评审。
> 通用约束（沿用 AGENTS.md/CLAUDE.md）：每表独立非空 `id VARCHAR(64)` 主键、无外键、无 enum、无 tenant_id、字段 `comment` 写候选类型+中文含义。

### 12.1 直接复用（本期全部走这里，零迁移）

| 表.列 | 现状 | 用途 |
|---|---|---|
| `image_record.projection` | 列已存在，**无写入路径** | 逐图投照位（§5.2 只补写入） |
| `image_record.technical_metadata_json` | JSON 列已存在 | 分割 `organ_seg` 结构、临床上下文轻量元数据 |
| `task_record.request_snapshot_json` | JSON 列已存在 | 冻结 clinical_context、逐图 projection/view_positions |
| `image_record` 的 `image_role=segmentation` + `source_manifest` | 合同已存在 | 分割产物作为派生 Image（§5.5/§11.5） |
| `study_record.body_part` / `acquired_at` | 已存在 | Study 级部位/时间，不复制到每张 Image |

### 12.2 ~~建议新增的列~~（GPT 评审后撤销）

| 原建议 | 撤销理由（GPT 评审第 5 条，成立） |
|---|---|
| `study_record.projection_summary_json` | 它是 Image 数据的**派生缓存**，会与 canonical manifest 双写漂移；Task 创建时经 `ImageDal` 聚合当前 ready Images 更小更可靠 |
| `session_record.clinical_context_json` | 上下文只随 Task 冻结即可（Snapshot 字段），不需要 session 级持久化 |

### 12.3 ~~建议新增的表~~（GPT 评审后撤销）

| 原建议 | 撤销理由 |
|---|---|
| `image_segmentation_record` | 分割产物走**派生 Image 合同**（`image_role=segmentation` + `source_manifest` + `technical_metadata_json`），复用现有表，无新表；且避免把 vet 变成在线依赖（decisions.md） |
| `ai_config_release_record` | M1 后再评审（release-state 后置） |

### 12.4 保持现状（明确不加）

| 项 | 理由 |
|---|---|
| `ms_image_eval` 独立库 | M1 前不做；主库 4 张 `evaluation_*` 表已存在 |
| `pet_profile`/`medical_record` | 不在 Model 清单；species 由调用方传入 |
| 通知/回调表 | 无真实 destination/consumer 合同 |

### 12.5 本期迁移清单（最终）

```text
本期：零表变更、零迁移。
待 P1 收口：unknown 有界终止字段（first_unknown_at/reconcile_count，需授权）。
M1 后：ms_image_eval 库 + release-state 持久化评审。
```

---

## 13. GPT-5.6-Sol 评审对照（逐条核实结论）

| # | GPT 意见 | 核实 | 处理 |
|---|---|---|---|
| 1 | `produced` 状态合同错误，阻断 Evaluation | ✅ 属实（注释枚举无 `produced`，真实数据存了它） | §5.10 新增修复项（最优先） |
| 2 | "盲读图"表述不准，模型已收多图 | ✅ 属实（`ai_request_service.py:1545`） | §2.2/§5.2 措辞修正 |
| 3 | §5.2 是完整四层数据链 | ✅ 属实（manifest 无 projection、Snapshot 逐 Series、ordered_image_refs 逐 Series） | §5.2 重写为 Image→manifest→Snapshot→Prompt 四层 |
| 4 | body_part/study_date 不应复制到每图 | ✅ 属实（Study 已有） | §5.2 仅逐图 projection |
| 5 | projection_summary_json 是派生缓存 | ✅ 属实 | §12.2 撤销 |
| 6 | GET /tasks?session_id= 路径冲突 | ✅ 属实（`tasks.py:26` 已用） | §5.4 改 `/tasks/page` |
| 7 | /xray/diagnoses 一步受理自相矛盾 + SSRF | ✅ 属实 | §5.6 改两步式并暂缓 |
| 8 | 分割依赖 vet 在线违反 decisions.md | ✅ 属实（decisions.md "vet 不作目标线上游"） | 调和：§5.9 撤销、改派生 Image 合同（§11.5 方案 C），既保留展示又不依赖 vet 在线 |
| 9 | Python 概括 summary 不安全 | ✅ 属实（Schema 嵌套无约束） | §5.5 summary 改为投影模型输出字段，Python 只透传 |
| 10 | fixed-bank 新接口多余 | ✅ 属实（Evaluation Job 已含全部 fingerprint 合同） | §5.8 撤销，复用现有 |
| — | 评审建议的真实顺序（P1 收口→状态合同→Schema 收紧→元数据链→E1 重跑→M1） | ✅ 与本文档 §8 顺序一致 | 采纳进 §8 |

> 结论：GPT 评审 10 条全部核实成立（个别引用有小出入但不影响结论），已全部纳入本文档 v1.2。

### 13.1 GPT 二轮评审对照（9 条，全部采纳）

| # | 意见 | 处理 |
|---|---|---|
| 1 | §5.10 在持久化边界投影而非改 v1 Stage 语义 | ✅ 已修订（§5.10：`ImagingExecutionService -> ReportService` 边界投影、拒绝 produced、Stage 内部语义不冻结修改） |
| 2 | 存量 produced 数据需单独授权修正 | ✅ 已修订（§5.10：单独授权 + 先确认嵌套结果有合法值） |
| 3 | "修完即可 Evaluation Export"是过度承诺 | ✅ 已修订（§5.10 边界声明：仍受 eval 库/Gold/Scorer/分母/Artifact signing 约束） |
| 4 | 字段统一叫 `projection`；补 provenance/旧 Snapshot 兼容/manifest hash 变化/发送顺序对账 | ✅ 已修订（§5.2：统一 `projection`，补旧 v1 Snapshot 兼容验收与 manifest hash 变化提示） |
| 5 | clinical context 需来源审计与诊断时点 | ✅ 已修订（§5.3 来源审计） |
| 6 | Task page / Report view 不阻塞 E1/M1，等 Schema v2 与 summary 稳定 | ✅ 已修订（§5.5 P2 声明；§8 顺序调整） |
| 7 | 分割作为独立 P2，派生 Image 尚缺完整功能合同 | ✅ 已修订（§5.5 P2 合同缺口清单：metadata Schema/版本来源/查询聚合/对象授权生命周期/报告投影） |
| 8 | 执行顺序漏 P1 剩余项 | ✅ 已修订（§8 顺序含 P1 剩余：自动 reconcile/unknown 有界终止/JWT/Artifact signing） |
| 9 | 27 号正文有相互矛盾章节 | ✅ 已修复（§4.7/§4.9/§5.6/§7.2/§7.4/§11.2 全部对齐两步式与撤销项） |

> 文档定位修正：**27 号是需求候选清单与接口合同参考；开发实施以 `28-xray-evidence-driven-development-guide.md`（证据驱动开发指南）和当前源码为准。**

### 13.1 迁移执行约束（复用至本期后仍适用）

- 所有未来变更走 **Alembic 迁移脚本**（`alembic_migrations/versions/`），不手工 DDL；
- 每步迁移先出 write set 与 rollback 单位，经用户确认后执行；
- 迁移前 `Base.metadata` 与物理表对照复核（沿用既有 `model_missing=[]` 校验法）；
- 旧数据：不做原地迁移（当前业务表 0 行基线），不复制 vet 旧表结构。
