# Reference Configuration Audit（参考配置审计，已脱敏）

> 中文阅读说明：`Reference Configuration Audit` 是“参考配置审计”；其余英文术语请参阅[英文术语中英对照](../术语中英对照.md)。

日期：2026-08-10

| 来源 | 配置项/符号 | 证据 | 当前结论 |
|---|---|---|---|
| vet-platform | MySQL/Redis/RabbitMQ/OSS（对象存储）/JWT/Gemini | `core/config.py:5-58` | 已读取配置结构；不输出值 |
| vet-platform | Celery pool/concurrency/race | `core/config.py:71-90` | 已读取运行参数结构 |
| vet-platform | `.env` keys | `.env.example:19-23`、实际 `.env` 仅检查变量名 | MYSQL_PW 为空，TCP 配置不完整；本机 Unix socket 只读连接已成功 |
| ms-image | Provider（AI 服务提供方） settings | `app/core/config.py:96-105` | 默认 disabled、key/model empty、qualified false |
| ms-image | Broker（消息代理） settings | `app/core/config.py:79-95`、`docker-compose.yml:1-95` | 默认 `BROKER_ENABLED=false`；Compose 静态包含 relay/worker，但 live runtime 待验证 |
| ms-image | Shared config injection | `app/core/ai/config.py`、`app/core/messaging/config.py` | 已补 source/prefix 注入，XRay（X 光） 兼容默认保留 |

安全边界：本 artifact 不包含 endpoint secret、API key、Authorization header、密码或完整 URL。参考工作树实际 `.env` 存在非空 Gemini key material，但仅核验 presence/length，未复制或输出；这属于旧项目 secret 管理风险。

## 未完成

- 生产环境变量来源、secret manager 路径和 rotation 合同尚未审批。
- 参考项目远程/TCP数据库连接仍被空密码阻断；本机 socket 只读结构/数量/状态证据已归档于 `reference-db-readonly-live.json`。
- 当前 manifest `docs/artifacts/p0-runtime-manifest.json` 已更新为默认 Broker disabled；它只证明静态配置和捕获时工作树，不证明 Docker/RabbitMQ live runtime。
