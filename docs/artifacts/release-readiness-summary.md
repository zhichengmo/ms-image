# Release（发布）Readiness（就绪性）Summary（摘要）

> 中文阅读说明：`Release Readiness Summary` 是“发布就绪摘要”；其余英文术语请参阅[英文术语中英对照](../术语中英对照.md)。

日期：2026-08-10

| 门 | 状态 | 证据 |
|---|---|---|
| import main（导入主应用） | `PASS-LOCAL`（本地通过） | `docs/artifacts/p0-import-main.txt`、当前 `import main` |
| Compose config（容器编排配置） | `PASS-CONFIG`（配置检查通过） | `docker compose config --quiet` |
| DB（数据库）/Redis readiness（就绪性） | `UNKNOWN`（证据不足）/`BLOCKED`（受阻） | `docs/artifacts/p0-readiness.json`；无 live（在线）DB/Redis |
| Broker（消息代理）/Worker（异步工作进程）runtime（运行时） | `UNKNOWN`（证据不足）/`BLOCKED`（受阻） | Docker daemon（Docker 守护进程）不可用；无当前容器消费证据 |
| Stub（桩实现）/Replay（回放）lifecycle（生命周期） | `PASS-LOCAL`（本地通过）/`PARTIAL`（部分完成） | `docs/artifacts/p1-zero-model-replay.json`、`p1-prompt-ai-request-replay.json` |
| Reference DB read-only（参考数据库只读核验） | `PASS-LOCAL`（本地通过） | `reference-db-readonly-live.json`、`reference-db-schema-summary.md`；未复制 secret（密钥）/raw prompt（原始提示词） |
| Real Provider（真实 AI 服务提供方） | `BLOCKED`（受阻） | `provider_disabled / retryable=false`；历史真实检查 `provider_auth` |
| G0 approval（G0 审批） | `NOT_STARTED`（未开始） | `docs/artifacts/p0-g0-approval.md` 为 `PENDING`（待处理）/`TBD`（待确定） |

最终发布状态：`PARTIAL`（部分完成）/`NO-GO`（禁止放行）。当前只允许继续工程基础线和脱敏适配，不允许真实医学链或生产发布。
