# Provider（AI 服务提供方）Qualification（资格验证）Matrix（矩阵）

> 中文阅读说明：`Provider Qualification Matrix` 是“Provider 资格验证矩阵”；其余英文术语请参阅[英文术语中英对照](../术语中英对照.md)。

| 检查项 | 当前结果 | 证据 | 是否放行 |
|---|---|---|---|
| 配置读取 | `blocked / provider_disabled / retryable=false` | `workers/xray_accuracy_worker/provider_qualification.py:20-23` | 否 |
| endpoint（端点）格式 | 代码已增加 scheme（协议）/netloc（网络位置）检查 | `app/core/readiness.py:25-38` | 未执行真实 endpoint（端点） |
| TLS（传输层安全协议）/网络 | 未获得生产连接证据 | OpenAI-compatible client error mapping（OpenAI 兼容客户端错误映射） | 否 |
| API（应用程序接口） key（接口密钥）认证 | 真实检查曾 `provider_auth` | qualification（资格验证）输出/历史记录 | 否 |
| model（模型）可用性 | 未证实 | 无真实 Provider（AI 服务提供方）receipt（回执） | 否 |
| strict JSON（严格 JSON）/schema（结构合同） | Stub（桩实现）/Replay（回放）通过；真实未执行 | `p1-prompt-ai-request-replay.json` | 仅本地 |
| timeout（超时）/retry（重试）/429 | Stub（桩实现）/Replay（回放）通过；真实未执行 | replay artifact（回放证据产物） | 仅本地 |
| ModelCall（模型调用）/Trace（技术追踪）持久化 | Stub（桩实现）/Replay（回放）有；qualification CLI（资格验证命令行）不落库 | `ai_request_service.py:385-503`、qualification.py | 否 |
| 图像输入/逐图 receipt（回执） | 当前 Provider（AI 服务提供方）文本请求，receipt（回执）为 unknown（未知） | `providers.py`、qualification.py:37 | 否 |

允许的稳定错误类：`provider_auth`、`endpoint_timeout`、`network_unreachable`、`tls_failure`、`model_invalid`、`schema_invalid`、`rate_limited`、`provider_unavailable`。
