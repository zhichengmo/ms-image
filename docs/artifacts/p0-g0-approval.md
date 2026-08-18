# G0 审批记录模板

> 中文阅读说明：`G0` 是第 0 级发布门禁；`PENDING` 是“待处理”；其余英文术语请参阅[英文术语中英对照](../术语中英对照.md)。

状态：`PENDING`（待处理）

Phase 0（第 0 阶段）在以下角色签名和 artifact（证据产物）链接齐全前不得标记 `DONE`（已完成）：

| 角色 | 姓名/工号 | 审批时间 | 结论 | 签名/链接 |
|---|---|---|---|---|
| 平台负责人 | TBD（待确定） | TBD（待确定） | PENDING（待处理） | TBD（待确定） |
| 安全负责人 | TBD（待确定） | TBD（待确定） | PENDING（待处理） | TBD（待确定） |
| QA（质量保障）/SRE（站点可靠性工程） | TBD（待确定） | TBD（待确定） | PENDING（待处理） | TBD（待确定） |

必附 artifact（证据产物）：git snapshot（代码版本快照）、runtime manifest（运行时清单）、import（导入验证）、双端进程/代理记录、
auth/tenant（认证/租户）合同、DB（数据库）/Redis readiness（就绪性）、Broker ADR（消息代理架构决策记录）、UNKNOWN（证据不足）清单，以及后续
stub（桩实现）/replay（回放）恢复演练记录。当前仅有本地 fail-closed smoke（失败即关闭冒烟验证），不能替代审批。
