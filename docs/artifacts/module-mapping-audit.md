# Module Mapping Audit（模块映射审计）

> 中文阅读说明：本文英文模块名、符号名和路径保持原样；通用术语请参阅[英文术语中英对照](../术语中英对照.md)。

| 目标能力 | 当前文件/符号 | 当前状态 | 后续目标 |
|---|---|---|---|
| Provider config（AI 服务提供方配置） | `app/core/ai/config.py:ProviderRuntimeConfig/provider_config` | `PARTIAL`（部分完成）；已支持 source/prefix（来源/前缀） | 完全 modality-neutral（模态无关） |
| Provider HTTP（AI 服务提供方 HTTP 客户端） | `app/core/ai/openai_compatible.py:OpenAICompatibleClient` | `PARTIAL`（部分完成） | 保留为公共 transport（传输层） |
| XRay Provider adapter（X 光 AI 服务提供方适配器） | `app/service/xray_accuracy/providers.py:OpenAICompatibleProvider` | `CONFIRMED`（已确认）adapter（适配器） | 仅保留 XRay payload/schema（X 光载荷/结构合同）映射 |
| AI Pool（AI 连接池） | `app/service/xray_accuracy/ai_request_service.py:AIConnectionPool` | `PARTIAL`（部分完成） | 抽到公共 imaging/ai，保留兼容 import（导入） |
| Prompt engine（提示词引擎） | `app/service/xray_accuracy/prompt_service.py:XRayPromptRegistry` | `PARTIAL`（部分完成） | 公共 registry engine（注册表引擎）+ modality assets（模态资产） |
| Outbox relay（事务发件箱中继） | `app/core/messaging/outbox_relay.py:TransactionalOutboxRelay` | `CONFIRMED_BASELINE`（已确认基线） | 不复制到 CT（计算机断层成像）/MRI（磁共振成像） |
| Celery factory（Celery 工厂） | `app/core/messaging/celery.py:create_celery_app` | `CONFIRMED_BASELINE`（已确认基线） | worker adapter（工作进程适配器）只注册 task（任务） |
| XRay worker（X 光工作进程） | `workers/xray_accuracy_worker/technical_worker.py:XRayTechnicalWorker` | `PARTIAL`（部分完成） | 公共 worker（工作进程）+ handler registry（处理器注册表） |
| DAL（数据访问层） | `app/crud/xray_accuracy/*Dal` | `CONFIRMED_BASELINE`（已确认基线）/`PARTIAL`（部分完成） | 继续 `DalBase`（数据访问基类）；迁移授权后增加 modality（模态）查询 |
| DB schema（数据库结构） | `app/models/xray_accuracy/*` | `PARTIAL`（部分完成） | 无 FK（外键）/enum（枚举）；无 migration（迁移）/deployed schema（已部署结构） |
