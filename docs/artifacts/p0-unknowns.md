# P0 `UNKNOWN`（证据不足）清单

> 中文阅读说明：`UNKNOWN` 是“尚无足够证据”；其余英文术语请参阅[英文术语中英对照](../术语中英对照.md)。

| ID（标识） | `UNKNOWN`（证据不足项） | 影响 | Owner（负责人） | 解答所需证据 |
|---|---|---|---|---|
| U-P0-01 | 生产/网关是否真实转发 `/ms-image` 与 `/ms-image/admin` | P0-B/G0 | 网关/SRE | 代理配置与边缘 HTTP smoke |
| U-P0-02 | 管理端是否需要网络层 allowlist、独立域名或额外 mTLS | P0-B/P0-C | 安全/SRE | 部署 ADR |
| U-P0-03 | 用户 JWT 的生产 issuer、audience、tenant claim 实际名称 | P0-C | 身份平台 | 签发方合同与样例（脱敏） |
| U-P0-04 | Alembic URL 的唯一来源及密钥注入方式 | P0-D | DBA/安全 | 配置 ADR；不得把密码写入仓库 |
| U-P0-05 | RabbitMQ 拓扑、TTL、最大重试与消费者超时的最终数值 | P0-E | 异步/SRE | ADR 审批与恢复演练 |
| U-P0-06 | live DB/Redis/RabbitMQ 环境是否可供 G0 验收 | P0-A/B/D/E | SRE | 部署环境 readiness artifact |
| U-P0-07 | Compose/.env.example 中开发凭证与生产密钥的注入边界 | P0-A/P0-C/P0-D | 安全/SRE | 生产 secret manager 与 Compose 部署 ADR |
| U-P0-08 | 生产环境是否继续禁止 MySQL/Redis/RabbitMQ host 端口暴露、是否由私有网络/安全组隔离 | P0-A/P0-B/P0-E | SRE/安全 | 生产网络拓扑、端口扫描和部署 ADR |
| U-P0-09 | Prompt（提示词）/ModelCall/Checkpoint/Trace（技术追踪） 是否已在 live schema 原子落库，以及真实 Provider（AI 服务提供方） 的图像输入、strict JSON、逐图 receipt 和超时行为 | P0-D/P0-E/G0 | Provider（AI 服务提供方）/DBA/后端 | migration 授权、真实环境 TechnicalExecutor 演练和 Provider（AI 服务提供方） qualification artifact |

这些 UNKNOWN 未解决前，Phase 0 不能标记 `DONE`。
