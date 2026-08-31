# MS-Image 代理交接入口

> 这是仓库的跨会话持续记忆入口。新会话先读本文件，再按恢复顺序读取最小状态集。

## 维护合同

- 本文件只做索引和恢复路由，不保存工作日志。
- 当前状态替换写入 `.agent-handoff/snapshot.md`，不得连续追加旧快照。
- 决策、验证、待办、风险和历史分别进入对应文件。
- 只记录仓库或用户可验证的事实；不确定项写 `UNKNOWN`（未知）。
- 不保存 Secret（密钥）、凭证、长日志、完整代码或聊天记录。
- 非简单任务结束前更新最小必要交接文件。

## 文件布局

| 文件 | 中文用途 |
|---|---|
| `.agent-handoff/snapshot.md` | 当前目标、状态、下一动作、活动文件和阻断 |
| `.agent-handoff/workspace.md` | 仓库地图、入口、文档和长期规则 |
| `.agent-handoff/decisions.md` | 跨会话长期决策、理由和证据 |
| `.agent-handoff/work-log.md` | 近期实际修改记录 |
| `.agent-handoff/validation.md` | 已运行、失败和未运行的验证 |
| `.agent-handoff/backlog.md` | 可执行未完成事项 |
| `.agent-handoff/risks.md` | 风险、阻断和 UNKNOWN |
| `.agent-handoff/archive.md` | 压缩旧历史，正常启动不读取 |

## 新会话恢复顺序

1. 本文件。
2. `.agent-handoff/snapshot.md`。
3. `.agent-handoff/risks.md`。
4. `.agent-handoff/backlog.md`。
5. 验证状态重要时读取 `.agent-handoff/validation.md`。
6. 修改架构或长期行为时读取 `.agent-handoff/decisions.md`。
7. 需要仓库定位时读取 `.agent-handoff/workspace.md`。
8. 只在需要近期修改细节时读取 `.agent-handoff/work-log.md`。
9. 最后读取当前任务直接相关的源码和 `docs/refactor/` 文档。

## 当前指针

- 最后更新：2026-08-31
- 工作区：`/Users/mozhicheng/workspace/code/cy-code/ms-image`
- 当前状态：`.agent-handoff/snapshot.md`（R4A Evaluation 独立数据库、metadata/Alembic、readiness 与 Fake scorer 技术烟测已完成；后端 240 tests 通过；最终资格标记被主库既存非 Evaluation 列注释漂移暂缓）
- 下一动作：`.agent-handoff/backlog.md`（先单独处理或明确豁免在线 `alembic check` 的 `ai_api_connection.secret_ref` 注释漂移并补容器构建验证；R4A 关闭后才进入 R4B Dataset 治理）
- 风险来源：`.agent-handoff/risks.md`
- 重构入口：`docs/refactor/README.md`
- 当前 post-C1 XRay 实施权威：`docs/refactor/29-xray-post-c1-development-guide.md`（C1/C1.1、P1-A、P1-B、D1/E1-MV、C2 已实施；P1-C 经用户确认延期）
- 前置裁决：`docs/refactor/28-xray-evidence-driven-development-guide.md`（C1 实施前裁决）；27 号仅保留候选设计背景
- 全部 AI 能力盘点：`docs/refactor/25-ms-image-complete-ai-capability-inventory.md`
- Primary 主链缺口清单：`docs/refactor/26-ms-image-primary-chain-incomplete-capability-checklist.md`
- 完整 XRay 架构参考：`docs/refactor/22-xray-full-ai-prompt-chain-development-guide.md`
- 完整 XRay 能力合同：`docs/refactor/21-xray-complete-capability-chain-and-session-prompt.md`
- 新会话说明：`docs/refactor/08-new-session-handoff.md`
- 可复制启动提示：`AGENT_SESSION_PROMPTS.md` 的“开启当前 XRay Runtime、Nacos Prompt 与完整能力开发会话（当前入口）”章节

## 容量与关闭规则

- Snapshot（当前快照）软限制 16 KiB/240 行，硬限制 32 KiB/400 行。
- Work Log（工作日志）超过 64 KiB 或 30 个日期段时轮转。
- Validation（验证记录）超过 64 KiB 或 200 行时轮转。
- Backlog/Risks（待办/风险）各不超过 32 KiB；风险不能机械删除。
- Archive chunk（归档分片）不超过 128 KiB。
- 非简单任务关闭前更新相关文件，并运行 agent-handoff maintenance（交接维护）检查。
