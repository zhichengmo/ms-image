# QJ 架构借鉴决策门：新会话提示词

状态：`CURRENT_REVIEW_ONLY_SESSION_PROMPT / NO_IMPLEMENTATION_BY_DEFAULT`

更新日期：2026-08-20

用途：将本文件中的提示词完整复制给一个新会话。该会话只能先做“借鉴适配评审”，不能因为 QJ 已有某种架构就自动改造 MS-Image。

关联资料：

- [08-new-session-handoff.md](08-new-session-handoff.md)：当前恢复、dirty worktree 和实施授权边界。
- [15-full-chain-gap-analysis-and-execution-plan.md](15-full-chain-gap-analysis-and-execution-plan.md)：当前工程优先级与发布门禁。
- [16-qj-reference-and-modular-convergence-plan.md](16-qj-reference-and-modular-convergence-plan.md)：QJ 借鉴候选与模块收敛方案。
- [17-prompt-runtime-contract-and-minimal-provider-plan.md](17-prompt-runtime-contract-and-minimal-provider-plan.md)：AI/Prompt/Stage 运行合同。

> 当前已知 HEAD 仅作时间点提示；新会话必须自己运行 `git rev-parse HEAD`，以当前 worktree 和 handoff 为准。

---

## 复制以下提示词给新会话

```text
请在以下工作区进行“QJ 架构借鉴适配评审”：

/Users/mozhicheng/workspace/code/cy-code/ms-image

参考仓库：

/Users/mozhicheng/workspace/code/cy-code/qj-open-plataform

## 本轮目标

本轮不是直接执行重构，也不是把 QJ 的架构复制到 MS-Image。

请基于当前 MS-Image 源码、当前 handoff、15/16/17 号文档，以及 QJ 的实际源码，逐项判断：

```text
QJ 的哪些设计应 Adopt（直接采用）
哪些应 Adapt（经适配后采用）
哪些应 Reject（明确不采用）
哪些应 Defer（暂缓，等待真实证据或用户授权）
```

输出必须以事实、风险、收益、前置条件、可回滚性和验证方式为依据。

**默认只读分析，不修改任何业务代码、部署配置、数据库 schema、迁移、测试或文档。**
只有在完成分析、给出最小变更切片、明确风险，并得到用户对该具体切片的再次授权后，才允许开始实施。

## 先读取

1. `AGENTS.md`
2. `AGENT_HANDOFF.md`
3. `.agent-handoff/snapshot.md`
4. `.agent-handoff/risks.md`
5. `.agent-handoff/backlog.md`
6. `docs/refactor/08-new-session-handoff.md`
7. `docs/refactor/15-full-chain-gap-analysis-and-execution-plan.md`
8. `docs/refactor/16-qj-reference-and-modular-convergence-plan.md`
9. `docs/refactor/17-prompt-runtime-contract-and-minimal-provider-plan.md`
10. 即将分析的 MS-Image 源码与 QJ 对应源码。

开始前必须运行：

```bash
git rev-parse HEAD
git status --short
git diff --name-status
git diff --stat
```

当前工作树有用户未提交改动。禁止：

```text
git reset
git clean
git checkout
git stash
git add -A
整文件覆盖
删除、迁移或改写无关用户改动
```

## 核心原则

### 1. QJ 只是参考，不是目标架构权威

QJ 可以提供工程经验，例如：

```text
独立入口
Compose 编排
DatabaseRegistry
Kong 静态/动态边界
外部 API Key 与商业控制面
```

但 MS-Image 的目标架构、医疗安全边界、Task/Stage/Outbox、Report、Evaluation 和发布门禁，必须优先服从：

```text
当前 worktree
AGENTS.md
snapshot / risks / backlog
15 号执行文档
16 号收敛方案
17 号 Prompt 运行合同
设计母文
```

任何 QJ 做法如果与这些合同冲突，默认 Reject 或 Defer，不能硬迁。

### 2. MS-Image 不应复制 QJ 的商业领域

不得建议或实现把以下 QJ 事实复制进 MS-Image：

```text
Project
API Key
Kong Consumer/Credential
Wallet
Ledger
Order
Usage
客户 SDK
客户 Webhook
tenant_id
```

QJ 若未来接入，应是外部商业控制面；MS-Image 继续独占：

```text
Session / Study / Series / Image
Task / StageCheckpoint / Outbox
AIConfigRecord / AICall / Report
Evaluation Job / Run / Artifact
```

### 3. 不能为了“模块化”制造新平行体系

始终保持：

```text
API -> Service -> DalBase -> Model/DB
Worker -> Service -> DalBase -> Model/DB
```

禁止建议或创建：

```text
Repository
第二套 CRUDBase
DatabaseService
平行 service 包
第二套 Outbox
第二套 OSS Gateway
第二套 Task Runner
第二套 Prompt/AI Request Service
```

### 4. 对 XRay legacy 必须保守

`xray_accuracy` 当前是 compatibility / legacy 域。

在以下事实未确认前：

```text
外部消费者
数据迁移映射
审计保留期限
旧 API 兼容要求
```

不得建议或执行：

```text
删除 xray_accuracy
批量迁移 xray_accuracy
把 xray_accuracy 设成新默认路径
新增 xray_accuracy Task/Stage/Outbox/Call/Report 事实
```

### 5. AI / Prompt / Stage 任何调整必须先过 17 号合同

如果分析涉及：

```text
AIConfig
AIRequest
Prompt
Schema
Provider-disabled
JointPrimaryReader
FamilyRouting
TargetedReview
Stage handler
```

必须先满足：

```text
Primary 医学调用 = 1 次
Targeted = 额外 0..1 次
每病例医学 Provider 调用总数 <= 2

AIConfigService = Config Release 唯一版本中心
AIRequestService = 物理 Provider Call 唯一 owner
ImagingExecutionService = lease/CAS/persist/schedule 唯一 owner
XRay Stage = Prompt / Schema / Family / Focus / Strategy 选择
```

不能为了目录收敛破坏调用次数、Config Release、Prompt 编译、泄漏检查、provider-disabled 真 Bundle 或 fail-closed 合同。

## 需要完成的分析输出

请形成一个可供用户决策的矩阵，至少覆盖：

| 借鉴项 | QJ 当前事实 | MS-Image 当前事实 | 结论（Adopt/Adapt/Reject/Defer） | 预期收益 | 风险 | 前置条件 | 最小可逆切片 | 验证方式 | 停止条件 |
|---|---|---|---|---|---|---|---|---|---|

重点审查：

1. 独立 API/Worker 入口与 Compose 编排；
2. DatabaseRegistry；
3. `online` / `evaluation` 隔离；
4. `hd` 外部集成是否应保留、是否应懒初始化；
5. Kong / API Key / Project / 商业计费边界；
6. QJ CapabilityTask 与 MS-Image Task 的关系；
7. 公共 Model 与 `xray_accuracy` legacy Model 的边界；
8. 8 个公共 Service 与 5 个 Stage 的实际拆分；
9. ImageService 和 images endpoint 的事务/OSS 编排；
10. Imaging/Evaluation/XRay legacy Worker 的职责和部署拓扑；
11. readiness、Operational Status、告警、graceful shutdown、prefetch、rolling upgrade；
12. Prompt/Config/AIRequest 合同与 17 号文档的兼容性。

## 决策标准

每个建议必须回答：

```text
1. 这是不是 QJ 已经真实实现的能力，而非草案？
2. 它解决 MS-Image 的哪个已确认问题？
3. 是否与 MS-Image 的唯一事实 owner 冲突？
4. 是否会增加第二套状态机、表、Worker、Outbox 或调用链？
5. 是否会影响医学结果、Provider 调用次数、Evaluation 隔离或发布门禁？
6. 是否可以先用无 schema 变更、可回滚的小切片验证？
7. 失败后如何回退？
8. 哪些事实仍是 UNKNOWN，必须等待用户或真实环境确认？
```

若任何问题无法得到证据支撑，结论必须是 `Defer`，不能因架构偏好推进。

## 本轮禁止实施

本轮默认不允许：

```text
修改业务代码
修改 docker-compose
拆 Service / Stage
移动 Model / DAL
删除 legacy 代码
生成迁移脚本
生成测试脚本
连接真实基础设施
接入 Kong / Nacos / Provider
```

如果分析后认为某项确实值得做，请只提出：

```text
候选最小切片
预计文件范围
不变量
验证方式
回滚方式
需要用户确认的授权
```

然后停止，等待用户确认。

## 第一条回复要求

先简短说明：

1. 当前 HEAD 与 dirty state；
2. 已读取的权威资料；
3. 本轮只读审计范围；
4. 你将如何区分 Adopt / Adapt / Reject / Defer；
5. 明确本轮不会修改代码，除非用户对某个具体最小切片再次授权。
```
