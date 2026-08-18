# MS-Image 数据库架构决策

> 中文阅读说明：`SUPERSEDED` 是“已被取代”，英文表名和字段名保持原样；通用术语请参阅[英文术语中英对照](../../术语中英对照.md)。

> **SUPERSEDED / 已被合并**：本文内容已经合并进 [MS-Image 最终架构、数据库与完整链路设计](../../ms-image-final-architecture-and-database-design.md)。本文仅保留为历史摘要，8 表方案不再是当前依据。

状态：`SUPERSEDED`（已被取代）

日期：2026-08-14

当前依据：[MS-Image 最终架构、数据库与完整链路设计](../../ms-image-final-architecture-and-database-design.md)

历史语境：本文后文的“必须”“条件扩展”等措辞仅描述 2026-08-14 候选方案，不构成当前实施授权。

## 历史决策

历史候选曾使用 8 张核心表（已被最终 10 表方案取代）：

```text
session_record
study_record
series_record
image_record
task_record
ai_config_record
ai_call_record
report_record
```

字段、索引、状态机、完整链路和旧表映射请以 [MS-Image 最终架构、数据库与完整链路设计](../../ms-image-final-architecture-and-database-design.md) 为准。

## 核心取舍

1. `session_record` 保留，但定义为“一次影像会话一行”，不迁旧聊天消息语义。
2. XRay 只由 `study_record.modality_type=xray` 表示；CT/MRI/超声等使用同一主链。
3. OSS 存文件 bytes；`image_record` 存影像域对象索引、顺序、摘要和 DICOM 技术元数据。
4. 首期将 Task Attempt、调度、lease 和 retry 合并进 `task_record`。
5. 首期任务结果通过查询交付，不建立 `outbox_record`；需要可靠 callback 时再扩展。
6. 连接、Prompt、Schema 和 Pipeline 合并为不可变 `ai_config_record` Revision。
7. 每次 Provider 物理调用写 `ai_call_record`，最终结构化结果写 `report_record`。
8. 用户、宠物、病历、聊天、支付、额度和计费公共表不进入 `ms_image`。

AI 请求主链：

```text
POST /api/v1/tasks
  -> task_record（一次业务 AI 请求）
  -> 冻结 Study/Image 输入和 ai_config_record
  -> Imaging Worker
  -> ai_call_record（一次真实 Provider 请求）
  -> Schema 校验
  -> report_record
  -> task_record(succeeded/failed)
```

一次 Task 可以产生多条 AI Call，因此逻辑任务与物理 Provider 请求不能合并为同一行。

## 为什么是 8 表

| 表 | 不可替代的事实 |
|---|---|
| `session_record` | 会话开始、完成、关闭和取消 |
| `study_record` | 一次影像检查及其模态 |
| `series_record` | CT/MRI 等 Series（影像序列） 分组和完整性 |
| `image_record` | OSS（对象存储） 对象与影像业务归属、顺序、hash、UID |
| `task_record` | 一次不可变输入分析任务和当前执行状态 |
| `ai_config_record` | 一次可重放的完整 AI 运行配置版本 |
| `ai_call_record` | 一次真实 Provider（AI 服务提供方） 调用事实 |
| `report_record` | 一个不可覆盖的结构化报告版本 |

删除任意一张都会丢失独立生命周期或可追溯事实；继续拆分则会提前引入尚未证明需要的治理复杂度。

## 架构范围

采用“保留入口的内部模块化重构”，不做局部改名，也不做全链重写。

保留：

- `FastAPI + Service + CRUD(DalBase) + Model/DB` 分层；
- OSS、Provider transport、Celery/Broker 等基础设施；
- 现有 XRay API 的临时兼容适配能力。

重做：

- 通用 Session/Study/Series/Image/Task/Call/Report 业务模型；
- XRay 专属命名；
- 旧模型中文件、AI 状态和结果混存的问题；
- 12/13 表草案中过细的配置和执行治理。

## 历史方案当时要求

- 不声明数据库 Foreign Key。
- 不使用数据库 Enum；类型和状态用 String，字段 comment 写候选值和中文解释。
- 所有租户业务访问带 `tenant_id`。
- API 资源 ID 放 query 或 request body，不使用 `/{id}`。
- AI 网络调用不持有数据库事务。
- 医学结果只来自模型或医生，Python 不改写。
- 本决策不授权建表、迁移或修改数据库。

## 条件扩展

以下能力不属于首期核心：

```text
outbox_record
task_attempt_record
review_record
finding_record
experiment_record
event_record
拆分后的 AI Prompt/Schema/Connection/Pipeline 治理表
```

只有出现可靠回调、独立 Attempt 审计、人工复核、跨报告查询、实验台账或多人配置治理等明确证据时才增加。
