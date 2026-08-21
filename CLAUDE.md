# MS-Image 项目协作说明

状态：`CURRENT_PROJECT_CONTEXT`（当前项目上下文）

本仓库是宠物多模态影像 AI（人工智能）服务，不是 MS-Scaffold（通用微服务脚手架）。当前唯一 Runtime 源码位于 `apps/runtime/`，在线 Session/Study/Series/Image、Task/Stage、provider-disabled AI Call、Report、Evaluation Job/Outbox/Relay/Worker、readiness 和 Operational Status 已有代码；状态为 `ONLINE_CODE_IMPLEMENTED / NOT_MIGRATED / NOT_RUNTIME_VALIDATED`。真实 Provider 仍未资格化，医学准确率保持 `UNKNOWN`，发布保持 `NO-GO`。

## 必读顺序

开始非简单任务前依次读取：

1. `AGENTS.md`：项目强制规则和授权边界。
2. `AGENT_HANDOFF.md`：跨会话恢复入口。
3. `.agent-handoff/snapshot.md`、`risks.md`、`backlog.md`：当前状态、风险和下一动作。
4. `docs/README.md`：文档权威边界和阅读导航。
5. 当前任务直接相关的 `docs/refactor/`、设计母文和源码。

本文件只提供项目方向，不复制 `AGENTS.md` 的完整规则；发生冲突时以当前用户授权和 `AGENTS.md` 为准。

## 项目目的

MS-Image 统一承载 XRay（X 光）、CT（计算机断层成像）、MRI（磁共振成像）、超声、视频和 WSI（全切片影像）的：

- Session/Study/Series/Image（会话/检查/序列/影像）接入与 OSS（对象存储）生命周期；
- Task/Stage/Outbox/AI Call（任务/阶段/事务发件箱/AI 调用）可靠执行；
- 不可变 Report（报告）和授权查询；
- 隔离 Gold（可信金标准）、Failure Bank（失败样本库）、Paired A/B（配对对照实验）和 Holdout（隔离留出集）评测。

当前首期只闭环 XRay；公共领域模型不得被 XRay 专项字段污染。

## Canonical XRay Chain（X 光权威主链）

```text
xray_primary_v1:
StudyPreparation -> JointPrimaryReader -> DecisionFinalization -> Report

xray_targeted_review_v1:
StudyPreparation -> JointPrimaryReader -> FamilyRouting
-> primary_final -> DecisionFinalization
或
-> targeted_review -> TargetedReview -> DecisionFinalization
-> Report
```

固定约束：

- FamilyRouting（家族路由）只在 Targeted 实验 Profile（流程配置）中执行，不调用模型、不读 Gold、不改医学结论。
- TargetedReview（专项复核）每例最多一次，必须输出完整病例结果。
- TargetedReview 一旦触发，技术失败必须 fail closed（失败关闭），不得静默回退 Primary（主读）。
- DecisionFinalization（结果定稿）只选择并校验唯一医学 owner（所有者），不调用模型、不投票、不改判。
- Evaluation Plane（离线评测面）只产生候选证据；人工审批后才允许 Control Plane（控制面）激活配置。
- 人工复核当前为 `N/A`（不适用）；`review_required` 表示 AI 无法确定的可发布终态。

详细流程以 `docs/refactor/10-xray-detailed-flow.md` 为准，精确表字段和不变量以 `docs/ms-image-final-architecture-and-database-design.md` 为准。

## 分层合同

```text
API（接口层） -> Service（业务服务层） -> CRUD/DAL（数据访问层） -> Model/DB（模型/数据库）
```

- API 负责路由、鉴权、依赖注入和统一响应。
- Service 接收 `AsyncSession`（异步数据库会话），负责业务校验、状态流转、幂等和多实体编排。
- 实体 DAL 继承 `apps.runtime.core.crud.DalBase`；API、Service、Worker 和脚本不得直接拼 SQLAlchemy 查询。Runtime 后端只存在于 `apps/runtime`，不得在仓库根恢复第二份 `app`/`workers` 源码。
- 不新增 Repository（仓储层）、第二套 CRUDBase、DatabaseService（数据库服务）或平行 service 包。
- Schema（接口结构）不访问数据库，Model（数据库模型）不承载 HTTP（网络接口）语义。

## 数据库与 API 规则

- 每张目标 MySQL 表使用服务端生成、非空、独立的 `id VARCHAR(64)` 单列主键。
- 不使用 Foreign Key（外键）、数据库 Enum（枚举）、联合主键或目标 `tenant_id`（租户字段）。
- 状态和类型使用 string/json/timestamp，并在字段 `comment` 中写候选类型和中文含义。
- 资源 ID 只放 query（查询参数）或 request body（请求体），不使用 `/{id}`。
- OSS 保存 bytes（文件字节）；领域 owner 表保存完整 ObjectRef（对象引用），不建设公共 `file_asset`（文件资产）表。
- 首期没有 Report callback/ack（报告回调/确认）生命周期。

## 可靠执行规则

- DB（数据库）事务中不得调用 OSS、Broker（消息代理）或 Provider（AI 服务提供方）。
- Broker 只提供至少一次触发；MySQL 中的幂等、Outbox、CAS（比较并设置）和 lease（租约）才是恢复事实。
- Task 冻结 Study revision、Config、Profile、Prompt、Schema、模型、预算和 release fingerprint（发布指纹）。
- Python 只能做确定性校验、路由、持久化和审计，不能用阈值、投票或 fallback（回退）产生医学结论。
- 工程失败与医学状态正交；没有合格医学结果时必须使用 `medical=not_produced`。

## 当前实现边界

- Runtime 已实现在线影像、Task/Stage、provider-disabled Call、Report、Evaluation 执行骨架、双库 readiness 和运行状态聚合；代码尚未迁移或真实运行验证。
- Compose 的 `ms_image` 与 `ms_image_eval` 保持独立；没有生成迁移脚本，也没有创建 `ai_control` 或 `evaluation_control` 空服务。
- Runtime user/admin API、imaging/evaluation worker 和 relay 都从 `apps/runtime` 启动；新增跨服务合同前不得创建共享 ORM、Repository 或通用 shared 包。
- 当前医学准确率为 `UNKNOWN`，生产发布为 `NO-GO`。
- 现有代码中的 MS-Scaffold 字符串属于待清理遗留实现，不是项目身份。

## 修改和验证边界

- 用户允许内部代码完全重构，但迁移脚本、新建测试脚本、真实数据库操作、生产双写和生产发布仍需单独授权。
- 历史正文原则上冻结；只通过 `docs/history/README.md` 解释当前归宿。
- 不把目标设计写成已实现，不把 Stub/Replay（桩/重放）写成医学结果，不把工程测试写成准确率证据。
- 结束非简单任务前按 `AGENTS.md` 更新 handoff（交接）并如实记录 passed/failed/not run（通过/失败/未运行）。
