# XRay（X 光）V2 独立诊断服务详细开发文档生成 Prompt（提示词）

> 中文阅读说明：`Prompt` 是“提示词”，`ARCHIVED` 是“已归档”；其余英文术语请参阅[英文术语中英对照](../../../术语中英对照.md)。

> `ARCHIVED / 历史资料`：本文仅用于复现旧文档生成上下文，不应作为当前开发会话 Prompt。

状态：`ARCHIVED`（已归档）

当前依据：[MS-Image 最终架构、数据库与完整链路设计](../../../ms-image-final-architecture-and-database-design.md)

历史语境：下方代码块按原 Prompt 保留，其中路径、权限、输出目标和任务要求均可能失效；不得直接执行，也不得据此修改代码、数据库或文档。

> 用途：复制本文件内容到新的 Codex 会话，让新会话只负责阅读代码、专题文档和 GitHub 参考，并生成详细开发文档。
> 目标项目：`/Users/mozhicheng/workspace/code/cy-code/ms-image`

```text
你是一名负责 XRay V2 独立诊断服务规划的高级后端架构师和医学 AI 工程师。

你的唯一任务是：详细阅读目标项目、参考项目、XRay V2 重构专题文档和 GitHub 外部参考，整理一份完整、可执行、可追溯的开发文档。

不要直接实现业务代码。

━━━━━━━━━━━━━━━━━━━━
一、目标项目与参考项目
━━━━━━━━━━━━━━━━━━━━

目标项目：
/Users/mozhicheng/workspace/code/cy-code/ms-image

参考项目：
/Users/mozhicheng/workspace/code/py-project-v2/vet-platform-system/vet-platform

最终开发文档保存为：
/Users/mozhicheng/workspace/code/cy-code/ms-image/docs/history/xray/design/xray-accuracy-detailed-development-document.md

只允许创建或修改上述开发文档，不修改业务代码、配置、数据库、迁移、测试脚本或参考项目。

必须保留目标仓库现有未提交修改，禁止使用：

- git reset --hard
- git checkout --
- git clean
- 覆盖或删除用户已有文件

━━━━━━━━━━━━━━━━━━━━
二、必须阅读的本地文件
━━━━━━━━━━━━━━━━━━━━

请完整阅读：

1. /Users/mozhicheng/workspace/code/cy-code/ms-image/AGENTS.md
2. /Users/mozhicheng/workspace/code/cy-code/ms-image/CLAUDE.md（如果存在）
3. /Users/mozhicheng/workspace/code/cy-code/ms-image/main.py
4. /Users/mozhicheng/workspace/code/cy-code/ms-image/app/
5. /Users/mozhicheng/workspace/code/cy-code/ms-image/requirements.txt
6. /Users/mozhicheng/workspace/code/cy-code/ms-image/docker-compose.yml
7. /Users/mozhicheng/workspace/code/cy-code/ms-image/Dockerfile
8. /Users/mozhicheng/workspace/code/cy-code/ms-image/alembic.ini
9. /Users/mozhicheng/workspace/code/cy-code/ms-image/alembic_migrations/env.py
10. /Users/mozhicheng/workspace/code/cy-code/ms-image/docs/history/xray/plans/xray-accuracy-development-plan.md

重点梳理：

- FastAPI 用户端和管理端
- main.py 生命周期与 root_path
- API 路由注册方式
- AsyncSession 和数据库连接池
- app.core.crud.DalBase
- MongoEngine legacy CRUD
- GenericResponse/PagedResponse
- RedisManager
- 鉴权和租户信息
- requirements 中的 Celery、Pika、Redis、OSS 等依赖
- 当前 Docker 和启动方式
- 当前 Git 工作树状态
- 已有代码与文档描述之间的差异

━━━━━━━━━━━━━━━━━━━━
三、必须阅读的 XRay 专题文档
━━━━━━━━━━━━━━━━━━━━

请完整阅读以下文件：

/Users/mozhicheng/workspace/code/py-project-v2/vet-platform-system/vet-platform/documents/X光V2重构专题/README.md

07-准确率优先全链路重构文档包：

- README.md
- 00-方案包总览与阅读顺序.md
- 01-辩证评审与准确率修订结论.md
- 02-准确率实验设计与验收门槛.md
- 03-落地前合同与状态清单.md
- 40-XRay近半年测试代码Prompt演进复盘与新链决策依据.md
- 41-XRay准确率优先重构决策与公开方法落地计划.md
- 42-XRay下一代全链路阶段节点与Family架构设计.md

08-XRay独立诊断服务新项目设计文档包：

- README.md
- 00-项目总览与权威边界.md
- 01-独立服务架构决策与系统边界.md
- 02-准确率优先全链路与状态机.md
- 03-接口数据合同与持久化设计.md
- 04-Prompt知识库Embedding与小模型边界.md
- 05-验证实验门禁与医学分母.md
- 06-实施迁移灰度与回滚计划.md
- 07-旧资料继承淘汰与代码差距清单.md
- 08-辩证审查与待修订决策清单.md
- 09-ms-image落地基线与目录映射.md
- 10-ms-image-P0工程基线执行清单.md
- 11-XRayV2全量数据审计与盲测治理最终方案.md
- 12-ms-image-Prompt-AI请求-Celery异步链路开发实施文档与新会话Prompt.md
- 13-ms-image新服务首轮开发启动Prompt.md

其他专题目录只作为历史背景和失败证据，不得把历史方案当成当前已实现能力。

━━━━━━━━━━━━━━━━━━━━
四、必须检查的 GitHub 参考
━━━━━━━━━━━━━━━━━━━━

请检查以下公开 GitHub 项目，并记录项目 URL、许可证、关键目录或文件、可借鉴设计、不适合直接复制的部分和与 ms-image 的映射关系：

1. https://github.com/dcm4che/dcm4chee-arc-light
   重点：Study/Series/Instance、UID、完整性和失败重取。请核对实际许可证，不要误写为 Apache-2.0。
2. https://github.com/Project-MONAI/MONAILabel
   重点：DICOMWeb、图像缓存 hash、逐帧访问、模型服务边界。
3. https://github.com/OHIF/Viewers
   重点：DisplaySet、Instance 去重、影像组织方式。
4. https://github.com/celery/celery
   重点：异步任务、ack、retry、worker 生命周期、RabbitMQ。
5. https://github.com/tomorrow-one/transactional-outbox
   重点：事务 Outbox、relay、至少一次投递、消费者幂等。
6. https://github.com/langfuse/langfuse
   重点：trace、span、generation、Prompt 版本和评估记录。
7. https://github.com/traceloop/openllmetry
   重点：OpenTelemetry、LLM span、跨 HTTP/Broker/Worker trace。
8. https://github.com/promptfoo/promptfoo
   重点：Prompt 回归、断言、模型矩阵评估。
9. https://github.com/openai/evals
   重点：评估任务注册、数据集和可复现实验。
10. https://github.com/stanford-crfm/helm
    重点：scenario/adaptor/metric 分层和 benchmark lineage。
11. https://github.com/vllm-project/vllm
12. https://github.com/bentoml/BentoML
13. https://github.com/ray-project/ray
    以上三个项目只作为 Provider、异步推理、批处理和资源调度的未来参考，不作为 P0 强依赖。

━━━━━━━━━━━━━━━━━━━━
五、文档必须包含的内容
━━━━━━━━━━━━━━━━━━━━

1. 执行摘要、背景、旧 V2/V3 链路的问题和独立服务必要性。
2. 目标、非目标、旧平台与 ms-image 的责任边界、数据所有权和部署决策。
3. ms-image 当前代码基线、目录结构、启动方式、依赖、现有能力和差距清单。
4. 目标架构和完整数据流：

   RequestGate（请求门禁） → StudyAssembler（检查组装） → EngineeringGate（工程门禁） → JointPrimaryReader（联合主读）
   → FamilyRouter（证据家族路由） → SparseTargetedReview（稀疏定向复核，可选）→ FinalMedicalReader（最终医学判读）
   → DecisionPolicy（决策策略） → ReportRenderer（报告渲染） → TraceWriter（追踪写入） → Human Review Gateway（人工复核网关）

5. API 请求、响应、错误、鉴权、幂等、取消、查询和版本控制。
   ID 只能通过 query 参数或 request body 传递，禁止设计 `/{id}` 路由。
6. API → Service → CRUD → Model/DB 的目录、模块职责、依赖方向和调用顺序。
7. Run、RequestSnapshot、Image、StageCheckpoint、ModelCall、Finding、Review、Outbox、ReleaseEvent 的 MySQL 逻辑表设计。
   不使用 foreign key，尽量不使用 enum，使用 string/json/timestamp，并在字段说明中写明类型候选和中文含义。
8. execution_status、ai_medical_status、delivery_status 三正交状态，以及 CAS、重试、取消、迟到结果、死信和孤儿任务恢复。
9. Prompt、模型请求、图像传输、ordered SHA256、full_sent、Provider receipt、schema/hash、输入边界和降级隔离。
10. Broker/Worker、Outbox、任务消息白名单、队列、超时、并发、重试、限流和成本计划。
11. P0 工程基线、Run/Trace/Outbox、Study/Image/EngineeringGate、B0/A1、A3a/A2/A3b、trusted gold/paired A/B、shadow/holdout/gray/active 的路线图。
12. 每阶段的输入、输出、文件清单、前置条件、完成定义、阻断条件、回滚方式和负责人角色。
13. Control/B0/A1/A2/A3/A4 实验、医学分母、engineering_clean、full_sent、trusted_gold、paired、fresh replicate、Holdout、指标和 No-Go。
14. 数据访问控制、租户隔离、外部图像地址校验、图像大小限制、敏感日志、内容泄漏防护和数据生命周期。
15. 观测性、审计、SLO、Provider 成本、人审 SLA 和故障演练。
16. 风险登记表、UNKNOWN 清单、ADR 模板、发布门禁和回滚门禁。
17. 文档最后附一份“后续实现 Prompt”。

━━━━━━━━━━━━━━━━━━━━
六、必须遵守的项目约束
━━━━━━━━━━━━━━━━━━━━

- 方案和现状严格分开，不能把 PROPOSED 写成已实现。
- 所有关键代码结论标注绝对路径、行号和符号。
- 遵循 API → Service → CRUD → Model/DB。
- 所有数据库调用必须复用 `app.core.crud.DalBase`。实体 DAL 只能在 `app/crud/` 中继承 `DalBase` 定义一次；Service 通过导入 `XxxDal` 并调用其异步方法完成业务，不得重新写 SQL、直接操作 `AsyncSession` 或创建第二套 CRUD/Repository/DatabaseService。
- “独立服务”只表示 XRay 领域/部署边界；不要因为该称呼再创建平行的 service 包或重复通用服务。
- XRay 只使用 SQLAlchemy 2.x + AsyncSession + DalBase。
- 新表不使用 foreign key，尽量不使用 enum，状态使用 string 并添加中文说明。
- API 不使用 `/{id}`，ID 使用 query 或 body。
- 不复制 vet-platform 旧 XRay Pipeline 的隐式业务逻辑。
- 不把技术完成率、解析率、调用成功率或延迟称为医学准确率。
- 不把 ABN/NOR、Disease-Code、文件名、历史模型结果、弱标签或人工结论送入在线医学 Prompt。
- 不在 Python 中将 abnormal 改写成 normal，或将 review_required 改写为医学结论。
- 不在 trusted gold、paired A/B、fresh replicate、Holdout 和发布门禁前讨论准确率提升或生产替换。
- 不创建迁移文件、测试脚本或无关代码，除非用户另行明确授权。
- 只创建目标开发文档，不修改业务代码、配置、数据库、迁移、测试和参考仓库。

━━━━━━━━━━━━━━━━━━━━
七、证据分类与最终输出
━━━━━━━━━━━━━━━━━━━━

先输出证据表，严格区分：

- CONFIRMED：当前代码或原始证据已确认
- INFERRED：基于多个证据推断
- PROPOSED：计划设计，尚未实现
- UNKNOWN：缺少外部事实
- N/A：当前阶段不适用

完成后返回：

- 开发文档绝对路径
- 章节摘要
- 当前 CONFIRMED 事项
- 当前 PROPOSED 事项
- 主要 UNKNOWN
- 主要风险
- 未执行动作
- 不应提前实现的内容
```
