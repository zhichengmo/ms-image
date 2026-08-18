# GitHub Mature Options Verification（GitHub 成熟方案验证）

> 中文阅读说明：本文英文项目名、路径和许可证名称保持原样；通用术语请参阅[英文术语中英对照](../术语中英对照.md)。

日期：2026-08-10。以下只记录公开仓库元数据和适用边界，不复制代码、凭证或数据。

| 项目 | 仓库 | 观测 HEAD | 许可证 | 关键路径 | 采用结论 |
|---|---|---|---|---|---|
| LiteLLM | https://github.com/BerriAI/litellm | `f6b9518` | MIT（enterprise：企业版，部分另行许可，法务需确认） | `litellm/main.py`、`litellm/router.py`、`litellm/proxy/` | 只评估 SDK（软件开发工具包）/Router（路由器）；首轮不引入 Proxy（代理）服务 |
| Portkey Gateway | https://github.com/Portkey-AI/gateway | `669825c` | MIT | `gateway/`、Node gateway source | pre-release（预发布）Gateway（网关）2.0，新增 Node（Node.js 运行时）基础设施，暂不引入 |
| Langfuse | https://github.com/langfuse/langfuse | `ac6020b` | MIT（ee 路径另行许可） | `web/`、`worker/`、`packages/` | 只借鉴 trace（追踪）/prompt（提示词）字段，不引入 ClickHouse/Postgres 数据栈 |
| OpenLLMetry | https://github.com/traceloop/openllmetry | `c2f3f45` | Apache-2.0 | `packages/opentelemetry-instrumentation-openai/`、`packages/traceloop-sdk/` | 后续可选 OTEL instrumentation（OpenTelemetry 可观测性埋点），当前不记录原图/secret（密钥） |
| Celery | https://github.com/celery/celery | `3511be4` | BSD-3-Clause | `docs/userguide/tasks.rst` | 已有 Celery factory（Celery 工厂）；采用 `acks_late`（处理后确认）、idempotent task（幂等任务）、retry（重试）语义 |
| RabbitMQ tutorials | https://github.com/rabbitmq/rabbitmq-tutorials | `6b3bde4` | 以仓库 LICENSE（许可证）为准 | publisher confirms（发布确认）示例 | ADR（架构决策记录）需要 confirms（确认）/durable（持久化）/DLX（死信交换器）；当前不以 result backend（结果后端）为事实源 |
| OpenAI Python | https://github.com/openai/openai-python | `0c09a3f` | Apache-2.0 | `src/openai/_base_client.py`、`src/openai/_client.py` | 后续可复用 Async client（异步客户端）/connection pooling（连接池）；当前保留兼容 Client（客户端） |

## 选择

最终选择 `现有 FastAPI + Service + DalBase` 的内部模块化重构：复用当前 Outbox/Worker/Provider 边界，不引入 LiteLLM Proxy、Portkey、Langfuse、Ray、BentoML 或 vLLM 运行时。
