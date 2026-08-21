# MS-Image 渐进式 Monorepo 重构：新会话完整启动 Prompt

状态：`SESSION_HANDOFF_PROMPT / MR-1_COMPLETE / RUNTIME_FOUNDATION_IN_PROGRESS / NO_MIGRATION_AUTHORIZED`

日期：2026-08-21

用途：将下方“可直接复制的 Prompt”完整复制到新的 Codex 会话中。该会话的目标是把 MS-Image **渐进式**收敛为可多服务演进的 Monorepo，而不是进行一次不可控的“硬搬家式重写”。

> 本文是新会话的执行提示，不替代现有架构权威。字段、状态机、Stage、Prompt、医学边界仍应以当前源码和引用设计文档为准；新会话开始时必须重新核对工作树和 Git 状态。

---

## 可直接复制的 Prompt

```text
请在下面的工作区中继续 MS-Image 的“渐进式 Monorepo 重构”。

工作区：
/Users/mozhicheng/workspace/code/cy-code/ms-image

请用中文沟通、输出完整绝对路径。此次任务不是把 QJ 平台代码硬复制进来，也不是立即建立多个空壳微服务；目标是把现有 MS-Image 整理为一个可持续演进的 Monorepo，并为后续 AI / Prompt Web 控制面预留清晰、可验证的服务边界。

# 0. 绝对优先的启动步骤

开始前必须先完整读取并遵守：

1. `/Users/mozhicheng/workspace/code/cy-code/ms-image/AGENTS.md`
2. `/Users/mozhicheng/workspace/code/cy-code/ms-image/AGENT_HANDOFF.md`
3. `/Users/mozhicheng/workspace/code/cy-code/ms-image/.agent-handoff/snapshot.md`
4. `/Users/mozhicheng/workspace/code/cy-code/ms-image/.agent-handoff/risks.md`
5. `/Users/mozhicheng/workspace/code/cy-code/ms-image/.agent-handoff/backlog.md`
6. `/Users/mozhicheng/workspace/code/cy-code/ms-image/docs/refactor/15-full-chain-gap-analysis-and-execution-plan.md`
7. `/Users/mozhicheng/workspace/code/cy-code/ms-image/docs/refactor/16-qj-reference-and-modular-convergence-plan.md`
8. `/Users/mozhicheng/workspace/code/cy-code/ms-image/docs/refactor/17-prompt-runtime-contract-and-minimal-provider-plan.md`
9. `/Users/mozhicheng/workspace/code/cy-code/ms-image/docs/refactor/19-ai-prompt-control-plane-web-and-runtime-architecture.md`
10. `/Users/mozhicheng/workspace/code/cy-code/ms-image/docs/refactor/20-monorepo-refactor-new-session-prompt.md`

然后实时执行只读核对：

```bash
pwd
git branch --show-current
git rev-parse HEAD
git status --short
git log -1 --oneline
find . -maxdepth 3 -type d -not -path './.git*' | sort
```

不要把文档里记录的历史 Git SHA 当成当前事实。以本次会话实际命令输出为准。

当前工作树已知存在用户未提交的文档、handoff 文件以及可能的
`/Users/mozhicheng/workspace/code/cy-code/ms-image/apps/runtime/models/evaluation.py`
改动。它们不是本任务的清理对象。禁止使用：

```bash
git reset
git clean
git checkout
git restore
git stash
git add -A
```

如果需要提交，只能对本次明确修改的路径逐个 `git add`。不要覆盖、回退、格式化或批量移动用户已有的未提交文档。

# 1. 当前业务与架构背景（必须保持）

MS-Image 是医学影像在线执行与评测系统，不是 QJ 开放平台的子模块。

MS-Image 自己拥有的在线事实包括：

```text
Session / Study / Series / Image / Study revision
Task / StageCheckpoint / Outbox / lease / CAS / retry / reconcile
AICall（逻辑医学调用）
Report（不可变 revision 与 current pointer）
Evaluation Job / Run / Artifact（独立 Evaluation 数据库）
```

当前主链已存在并必须保持其单一事实所有权：

```text
影像接入
-> Session / Study / Series / Image
-> Task
-> StageCheckpoint / Outbox / Worker
-> AIConfig projection / AICall
-> Report
-> Evaluation Export
-> ms_image_eval
```

当前已经实现但仍未真实资格化的能力：

```text
- 在线 Session/Study/Series/Image、Task/Stage/Outbox、Report 主链；
- provider-disabled 医学调用事实链；
- Evaluation Job/Outbox/Run/Artifact、fake scorer、paired A/B 骨架；
- zh-CN Prompt Catalog、PromptCompiler、CompleteMedicalResult Schema；
- Prompt/Schema/Model policy 的 AI Config Bundle、config_sha256、release_fingerprint；
- Primary 一次逻辑医学调用，Targeted 额外最多一次的合同；
- Targeted experiment-only gate。
```

当前尚未实现或尚未授权的能力：

```text
- 真实 Provider send、receipt、unknown reconcile 的生产资格化；
- AI Connection 管理、模型目录、Prompt Web 编辑、Schema Web 编辑；
- AI Control Release publish event；
- AICallAttempt 与真实模型竞速；
- 真实模型 paired A/B、Gold/Holdout、医学发布；
- 真实数据库迁移、物理旧表删除或归档。
```

历史 legacy XRay/AI runtime 链已经从**当前代码**移除。不得恢复或复制旧的：

```text
ai_config / gpt_config / ai_prompt_template / ai_model_pool / ai_api_connection
旧 XRayPromptRegistry
xray_accuracy ORM/CRUD/Service/API/Worker
MongoEngine CRUDBase
```

物理 `ms_image` 数据库可能还存有历史旧表，但当前代码不应读写它们。物理 archive/drop、数据迁移、清理 API key 都属于另行授权事项。

# 2. Monorepo 的目标：服务边界，而不是复制代码

目标 Monorepo 的概念边界是：

```text
apps/
  runtime/              # 在线病例执行面：现在必须先稳定的服务
  ai_control/           # AI / Prompt 管理控制面：后续 Phase A 才实现
  evaluation_control/   # 独立评测治理面：满足拆分条件后才实现

packages/
  ai_contracts/         # 只放跨服务、版本化、无业务状态的合同；按需创建

deploy/
  compose/              # 服务编排、部署入口、环境模板
```

但是，这不是要求在第一步把三套目录都填满或创建空 FastAPI 服务。必须按下面的边界执行：

| 服务 | 核心职责 | 它拥有的事实 | 它不能拥有 |
|---|---|---|---|
| `runtime` | 在线接收影像、创建/执行 Task、推进 Stage、调用 Provider、生成 Report | Session/Study/Series/Image/Task/Stage/Outbox/AICall/Attempt/Report 和 Runtime AIConfig projection | Prompt 编辑、Connection 编辑、Release 审批、Gold/Holdout |
| `ai_control` | 供未来 Web 管理的 AI 配置控制面 | Connection、Model、Prompt、Prompt Revision、Schema Revision、Release、Audit、Control Outbox | Task/Stage/Report、在线病例状态、Provider 执行 lease |
| `evaluation_control` | 离线评测与发布证据治理 | Dataset、Gold、Split、Experiment、Run、Artifact、Failure Bank、Approval | 在线 Task/Report、直接修改 Active Release |

核心单向关系必须是：

```text
AI Control 发布不可变 Release snapshot
-> Runtime 幂等消费并保存只读的 AIConfig projection
-> Runtime 执行病例并产生 AICall / Report 运行事实
-> Evaluation 产生候选 Release 的证据与审批建议
-> 只有 AI Control 可以执行发布、退役、回滚 Release
```

禁止以下反向或跨库直接写入：

```text
Web 请求直接写 ms_image Runtime DB
Evaluation 直接把候选 Release 改为生产 Active
Runtime 修改 Prompt / Model / Connection 编辑源
AI Control 写 Task / Stage / Report / 医学结果
任一服务直接写另一服务的数据库表
```

# 3. 必须坚持的领域合同

## 3.1 Runtime 医学执行合同

```text
Primary-only = 1 次逻辑医学 Provider 调用
Targeted = 额外 0..1 次逻辑调用
每病例在线医学 Provider 调用 <= 2
```

未来若启用竞速：

```text
一个逻辑 AICall
-> 一个或多个物理 AICallAttempt lane
-> 一个且仅一个 technical winner
```

首期限制：

```text
Primary：单模型或最多 2 lanes
Targeted：只允许单 lane，不允许 Targeted race
每病例物理 Provider attempts <= 3
winner_policy = first_technically_valid
```

Winner 不得由医学内容、Finding 数量、异常严重度、confidence 或措辞选择；只能由下列技术条件决定：

```text
full-sent
receipt / actual model 合格
schema 合格
response hash 合格
deadline 内
CAS 成功
```

## 3.2 Prompt 合同

首期 Prompt 语言固定：

```text
zh-CN
```

必须保持：

```text
无英文 fallback
无双语运行 Prompt
缺失 zh-CN asset 必须 fail closed
语言是 Release fingerprint 的组成部分
Prompt 是 fragment，不是独立 Task/Stage/Table/Provider call
```

JSON Schema key 保持稳定英文；中文只用于字段值内容。Primary 与 Targeted 共用 `complete_medical_result` Schema。

## 3.3 AI Connection 与 Secret 合同

未来 AI Control 中：

```text
base_url       -> 可以保存为受控 Connection metadata
api_key        -> 不得保存到普通数据库字段
secret_ref     -> 数据库只保存 Secret Manager / env 的引用
```

禁止 Secret 进入：

```text
Runtime DB
Prompt 或 Release snapshot
日志
Artifact
错误消息
浏览器/API response
Git
```

## 3.4 Evaluation 合同

Evaluation 的职责是评估候选 Release 是否有足够证据进入下一步；不是在线诊断 executor，也不是生产发布者。

Evaluation 必须保持：

```text
与 Runtime 在线数据库隔离
不写 Task / Report / Active Config
paired A/B 时冻结相同 case/images/Prompt/Schema
比较 single 与 race 时只允许 race plan 成为变量
医学准确率在真实 Gold/Holdout 前保持 UNKNOWN
```

# 4. 本次 Monorepo 重构的原则

## 4.1 借鉴 QJ 的内容

可以借鉴 QJ 开放平台的工程思想：

```text
多服务目录边界
服务独立启动入口
数据库注册/生命周期组织
Compose 编排
外部入口与内部管理边界
跨服务事件而非跨库写入
```

但禁止硬搬 QJ 的业务平台域：

```text
User / Organization / Project
客户 API Key / Kong Consumer / Credential
Capability 商品目录
Usage / Wallet / Ledger / Order / Refund
客户 SDK / 客户 Webhook
QJ platform 数据库和 tenant 模型
```

MS-Image 若将来接入 QJ，只接收可信的 opaque：

```text
requester_id
subject_id
request_id
trace_id
```

MS-Image 不创建 `tenant_id`，不复制 QJ 主数据，不通过 Foreign Key 关联 QJ。

## 4.2 不建立“万能 shared 包”

禁止新建以下类型的包：

```text
common
shared
utils（大杂烩）
base_repository
DatabaseService
第二套 CRUDBase
跨服务的 ORM Model 包
跨服务的 Service 包
```

第一批可以按需创建的唯一共享包是：

```text
packages/ai_contracts/
```

它只能包含：

```text
版本化 Pydantic event schema
Release snapshot 合同
发布/退役事件名与 message version
纯 hash/canonicalization 合同（若确实跨服务共享）
```

它不能包含：

```text
SQLAlchemy ORM
DalBase
数据库 session
Service 业务编排
FastAPI router
Secret 值
Runtime 内部 Prompt 编译实现
```

没有真实的跨服务合同需要时，不要为了目录完整性提前创建它。

## 4.3 先稳定 Runtime，再创建真实新服务

MR-1 的 Runtime 单一源码迁移已经完成；当前第一实施切片是“Runtime Foundation 收口”，而不是重复搬迁或 AI Control 全量开发。

推荐的渐进式目标是：

```text
阶段 MR-1：已完成，现有 Runtime 作为唯一源码收敛到 apps/runtime；
阶段 MR-1F：收敛部署、启动入口、Worker/Relay 生命周期、遗留引用与无 Secret 验证；
阶段 MR-2：在出现真实跨服务 Release 合同时按需抽取无状态合同包；
阶段 AI-A：真正开始 ai_control 的 Connection/Model/Prompt/Schema 控制面；
阶段 AI-B：Release compile/validate；
阶段 AI-C：Control Outbox -> Runtime immutable projection；
阶段 E-A：仅在 Evaluation 有独立 UI、Owner、SLA、队列/资源需求后，再拆 evaluation_control。
```

不要先建空的 `ai_control` 或 `evaluation_control` FastAPI 应用来制造“看起来已经微服务化”的假象。

# 5. 推荐的目录演进方案

## 5.1 阶段 MR-1 已完成结构

MR-1 已完成一次**可回滚的机械性 Runtime 迁移**。`apps/runtime/` 本身就是
Runtime 后端服务根；所有运行时代码使用显式的 `apps.runtime.*` 命名空间：

```text
ms-image/
├── apps/
│   └── runtime/
│       ├── api/                 # 用户 API；内部保留 api_v1 路由版本
│       ├── admin_api/           # 管理 API
│       ├── core/                # 连接、DalBase、消息、对象存储等横切能力
│       ├── crud/
│       ├── models/
│       ├── schemas/
│       ├── service/             # 项目规范固定使用单数 service
│       ├── stages/
│       ├── workers/
│       │   ├── imaging_worker/
│       │   └── evaluation_worker/
│       ├── lib/
│       ├── main.py              # 现有 Runtime FastAPI entry
│       ├── config.py
│       ├── lifespan.py
│       ├── start_user_api.py
│       ├── start_admin_api.py
│       ├── run_servers.py
│       ├── Dockerfile
│       └── requirements.txt 或服务依赖声明
├── packages/                    # 首期可以不存在或为空；禁止造 common
├── deploy/
│   └── compose/                 # 逐步收敛 compose、env 示例、服务命令
├── docs/
├── prompts/                     # 先保持单一权威位置，禁止复制
├── alembic_migrations/          # 仅移动前先审计；本期不生成/执行 migration
├── AGENTS.md
└── ...
```

`apps/runtime/` 是当前唯一 Runtime 源布局；`apps.runtime.*`
是当前正式 import 合同。任何未来命名空间调整都必须单独设计、验证和授权，
不得在其他功能切片中再次搬迁。

严禁同时保留两份可运行源码，例如：

```text
./app + ./apps/runtime
./workers + ./apps/runtime/workers
```

必须是 `git mv` 或等价的单一真相迁移；不得复制后让两份长期并行。

## 5.2 最终服务结构（不是 MR-1 的一次性实施清单）

```text
apps/
├── runtime/
│   ├── api/
│   ├── admin_api/
│   ├── core/
│   ├── crud/
│   ├── models/
│   ├── schemas/
│   ├── service/
│   ├── stages/
│   └── workers/                 # imaging/evaluation 迁出前仍归 Runtime
│   ├── main.py
│   ├── config.py
│   └── lifespan.py
│
├── ai_control/                  # 到 AI-A 才创建真实代码
│   ├── api/
│   ├── core/
│   ├── models/
│   ├── crud/
│   ├── schemas/
│   ├── service/
│   └── outbox/
│   ├── main.py
│   ├── config.py
│   └── lifespan.py
│
└── evaluation_control/          # 达到独立拆分条件才创建真实代码
    ├── api/
    ├── core/
    ├── models/
    ├── crud/
    ├── schemas/
    ├── service/
    └── workers/
    ├── main.py
    └── config.py
```

`runtime` 内当前保留 Evaluation worker 的原因是：现有 Evaluation 仍与 Runtime 代码、模型和运行合同直接耦合。未完成 Dataset/Truth/Experiment 的独立 ownership 之前，强拆只会产生第二个假服务和跨库耦合。

# 6. 每个服务未来的数据库边界

```text
runtime              -> ms_image
evaluation_control   -> ms_image_eval
ai_control           -> ms_image_ai_control
```

## 6.1 Runtime

`ms_image` 继续保存在线执行事实。`ai_config_record` 是 AI Release 在 Runtime 的不可变投影，不是 Prompt 编辑源、Model 编辑源或 Connection 编辑源。

未来在真实 Provider 阶段，`ai_call_attempt_record` 才可在明确授权下增加，用于一个逻辑 AICall 下的物理 lane 事实。

## 6.2 AI Control

AI Control 的未来核心实体是：

```text
ai_connection_record
ai_model_record
ai_prompt_record
ai_prompt_revision_record
ai_schema_record
ai_schema_revision_record
ai_release_record
ai_control_outbox_record
ai_control_audit_record
```

一行 Connection/Model/Prompt Revision/Schema Revision/Release 均是可审计版本；发布后的 Release 不可覆盖，只能退役或创建新版本。

## 6.3 Evaluation Control

独立后拥有：

```text
Dataset
Gold
Split
Experiment
Evaluation Job / Run / Artifact
Failure Bank
Approval evidence
```

它不拥有任何在线医学结果的写入权。

## 6.4 全部 MySQL 表的硬性约束

若后续用户明确授权设计或创建新表，必须遵守：

```text
id VARCHAR(64) NOT NULL：单列主键，服务端 opaque ID
不使用 Foreign Key
不使用数据库 Enum
不使用联合主键
不增加 tenant_id
状态/类型使用 VARCHAR / JSON / timestamp
每个字段写 SQLAlchemy comment，说明候选类型和中文语义
资源 ID 只放 query 或 request body，禁止 /{id}
```

本次 MR-1 不生成迁移脚本、不执行迁移、不操作真实数据库。

# 7. 执行方式：复核现状，按最小切片实施

MR-1 已完成。后续会话不得再次 `git mv` Runtime 源；应先核对当前分支和工作树，再针对 MR-1F 或明确授权的后续切片提出最小 write set。

## 每次会话第一轮必须完成的只读审计

请先读取当前源码并给出精确、可核对的“Monorepo Readiness Audit”，至少包含：

1. 当前 FastAPI user/admin entry、`main.py`、config/lifespan 初始化位置；
2. 当前 Dockerfile、docker-compose、环境文件、工作目录、`PYTHONPATH` 和启动命令；
3. 当前 imaging/evaluation Worker 的入口、Celery app、任务模块及 import 根；
4. 当前 `app` 到 `workers`、`prompts`、`alembic_migrations`、`evaluation` 的路径依赖；
5. 当前 Runtime 的 Model/DAL/Service/API 的依赖方向；
6. 现有 `ms_image` / `ms_image_eval` session 与 metadata 注册位置；
7. 文件移动后最可能发生的 import、容器 build context、配置相对路径、Celery discovery 风险；
8. 哪些文件属于用户未提交改动，必须避开；
9. 当前 MR-1F 或用户指定切片的最小 write set、预期命令、回滚方式；
10. 哪些问题必须等待用户确认，哪些可以安全执行。

审计结论必须区分：

```text
CONFIRMED：当前源码或实时命令直接证明
INFERRED：由多个证据推断
PROPOSED：后续设计建议
UNKNOWN：当前不可证明，不能假设
```

审计后只对尚未授权的具体切片请求确认。MR-1 已有的 Runtime 目录、Docker/Compose、入口和 import 不得重复移动；未获新的明确授权前，仍不得新建空服务、创建数据库表、生成迁移或连接真实基础设施。

## 后续切片获得明确授权后，实施顺序必须是

### MR-1F.1：冻结基线与设计确认

- 重新核对 Git HEAD、branch、dirty state；
- 再次确认没有与用户改动冲突；
- 确认 `apps/runtime` 仍是唯一 Runtime 源目录；
- 确认 `prompts/` 是否仍留在仓库根作为单一资产目录（默认是）；
- 确认 migration 目录处理方式，但不执行 migration；
- 给出精确变更清单后再操作。

### MR-1F.2：只收口启动、生命周期与边界

- 固化 user/admin、imaging/evaluation worker/relay/reconcile 的唯一启动合同；
- 清理已删除 legacy consumer 的失效引用，不恢复旧执行链；
- 保持 API、Service、DAL、Model、Schema 的业务边界不变；
- 不把业务逻辑塞回 `main.py`、Dockerfile 或 Worker；
- 不借 Runtime 收口顺便改业务状态机、Prompt、医学规则或数据库字段。

### MR-1F.3：验证启动、配置、容器与 Compose

- 让 user API、admin API、imaging worker、evaluation worker 在新目录下有明确、唯一的启动方式；
- Docker build context、WORKDIR、COPY、healthcheck 和挂载路径必须与新结构一致；
- 以服务名区分 Runtime user/admin/worker process，但不要把 user/admin 误拆为两个拥有不同业务事实的服务；
- 服务间配置只通过显式 env/config 注入；禁止靠 `../../` 等脆弱相对路径读取 Prompt 或配置；
- 若有新的路径解析需求，应集中在 Runtime config/bootstrap，而不是散落在业务 Service。

### MR-1F.4：只在确有跨服务合同后创建 `packages/ai_contracts`

- 不能把 Runtime 的 ORM、DAL、Service 移入其中；
- 如尚无 Control Outbox event，不要先造无消费者的 event framework；
- 如创建，必须具有明确 `message_version`、JSON/Pydantic schema、hash/fingerprint 校验规则和 ownership 注释。

### MR-1F.5：停止点

MR-1F 完成后必须停止，不自动进入：

```text
AI Control 数据表
Prompt Web 页面
真实 Provider
AICallAttempt
模型竞速
Evaluation 独立拆服务
真实数据库迁移
物理旧表删除
```

进入这些事项前，必须重新提交独立设计、写集、DB/Secret/发布影响和用户授权请求。

# 8. AI Control 的后续实施边界（供 MR-1 后的会话使用）

AI Control 不是“模型调用代理服务”，而是内部管理 Web 的控制平面。

它未来应遵循：

```text
Connection / Model / Prompt Revision / Schema Revision
+ Profile / Budget / Provider Plan / Qualification Evidence
= Immutable AI Release
```

发布链：

```text
AI Control release publish
-> Control Outbox event
-> Runtime 消费 release snapshot
-> Runtime 校验 SHA / fingerprint
-> Runtime 幂等写入 ai_config_record projection
-> Runtime Active Slot CAS
```

绝不允许 Web 请求直接跨数据库写入 Runtime 的 `ai_config_record`。

`ai_control` 首期可逐步实现：

```text
AI-A：Connection/Model/Prompt/Schema 的 CRUD、RBAC、SecretRef；不接真实 Provider
AI-B：Release builder/compiler、validation、fingerprint、Audit；不发布 Runtime
AI-C：Control Outbox、Runtime projection、publish/retire/rollback
AI-D：Runtime single-lane 真实 Provider qualification
AI-E：Primary <=2 lanes race
AI-F：Targeted single lane、paired A/B、Holdout、shadow/gray
```

没有真实 Connection/Model/Prompt/Schema ownership 之前，不创建空 `ai_control` 进程。

# 9. Evaluation Control 的拆分条件

当前 Evaluation 保持在 Runtime 代码域和 `ms_image_eval` 数据边界中。只有同时满足下面事实时，才可提出 `evaluation_control` 独立服务设计：

```text
1. Dataset / Gold / Split / Experiment 有稳定独立模型和 API；
2. 有明确的数据治理 owner 与审批流程；
3. 有独立 Web 使用者或 SLA；
4. 有独立队列/worker 容量需求；
5. 不需要直接 import Runtime ORM/Service；
6. 能通过 versioned Export/Event/Artifact 与 Runtime 交互。
```

如果条件未满足，保持 Evaluation 为独立数据库平面而不是独立部署服务。

# 10. 工程分层与实现硬规则

每一个服务内部必须维持：

```text
API -> Service -> DalBase -> Model/DB
Worker -> Service -> DalBase -> Model/DB
Schema 是接口/事件边界，不访问数据库
```

强制遵守：

```text
- 不新增第二套 CRUDBase、Repository、DatabaseService；
- 所有数据访问经现有 `apps.runtime.core.crud.DalBase` 的实体 DAL；
- API endpoint 不写复杂 SQL、多 DAL 编排或业务状态机；
- Service 不依赖 FastAPI Request / Depends / Router；
- CRUD 不返回 HTTP GenericResponse；
- Worker 不绕过 Service/DAL 直接写数据库；
- 事务中不做 Provider / OSS / Broker I/O；
- 不设计 /{id} 路由；
- 不恢复 legacy XRay/AI runtime；
- 不为了专项创建第二套 Model/CRUD/Service/Worker/表；
- Prompt fragment 不是 Stage、Task、Worker 或独立 Provider call。
```

# 11. 禁止事项与权限边界

除非用户在本会话中明确授权，否则禁止：

```text
生成 Alembic migration 或测试脚本
执行 migration
连接/修改真实 MySQL、OSS、RabbitMQ、Provider
物理 DROP、archive 或清理数据库旧表
读取、展示、复制或提交 api_key / Secret 值
接入真实 Provider
宣称 production ready、医学准确率提升或医学发布可用
```

可以运行已有的只读/静态验证命令；不要为了验证自行生成一套新测试框架或脚本。

# 12. MR-1 的验证合同

在每个小切片完成后，如环境允许，至少执行并如实汇报：

```bash
git diff --check
python -m compileall <新的 runtime Python 源目录>
docker compose config
```

再按实际新启动路径执行不连接外部基础设施的 import/entrypoint 检查。若已有项目测试可安全运行，可以运行现有测试；若未运行，要明确说明原因。禁止伪造“全链路通过”。

MR-1 的最低验收条件：

```text
1. Runtime 源码只有一份，旧 root app/workers 不再是可运行副本；
2. user/admin API 与全部现有 Worker 的导入路径可解析；
3. Dockerfile / Compose 的 build context、command、healthcheck、挂载路径与新布局一致；
4. prompts 仍是唯一权威资产目录，没有复制；
5. 业务 API、Stage、数据库 schema、Prompt 行为、Provider-disabled 合同未被改变；
6. 没有新增数据库表、迁移、真实 Provider 或 Secret 泄漏；
7. Git diff 中不包含用户原有脏文件的意外覆盖。
```

发生下列任一问题必须停止并报告，不要“边猜边修”：

```text
需要修改 Task/Stage/Report 语义才能完成目录迁移
需要新建第二套 DAL/数据库基类
需要复制 Runtime Model 到 AI Control/Evaluation
需要跨库同步但没有 versioned event contract
需要迁移或修改真实数据库
需要读取/打印 Secret
现有 dirty 文件与移动路径冲突且无法安全排除
```

# 13. 交付与提交纪律

每一次实施回复请固定输出：

1. 当前阶段和目标；
2. 已确认事实与不确定项；
3. 修改的绝对路径及其用途；
4. 未修改且刻意保留的边界；
5. 验证命令和真实结果；
6. 风险、停止条件、下一阶段；
7. 是否需要用户新的授权。

仅当确有本次会话自己的完整、可验证变更时，才做小而原子的 commit。严禁把用户已有 dirty 文档带入 commit。不要使用 `git add -A`。

非简单任务结束前，必须按仓库 `AGENTS.md` 的 handoff 协议更新最小相关文件：

```text
.agent-handoff/snapshot.md
.agent-handoff/work-log.md
.agent-handoff/validation.md
.agent-handoff/decisions.md
.agent-handoff/backlog.md
.agent-handoff/risks.md
```

随后运行可用的 handoff maintenance 脚本，并如实报告结果。

# 14. 当前会话的第一项要求

现在先不要重复移动任何代码或目录。请完成“Runtime Foundation Readiness Audit”，并给出：

```text
A. 当前真实启动与导入拓扑；
B. MR-1 已完成事实与 MR-1F 的最小目标；
C. 精确文件修改清单（只列本轮必要路径，不重复移动）；
D. Docker/Compose/Worker/Relay 生命周期风险；
E. 验证与回滚步骤；
F. 哪些内容被明确排除；
G. 只有需要超出 MR-1F 的新权限时，才请求对应的具体授权。
```
```

---

## 使用说明

- 建议**整段复制**，不要只复制末尾“当前会话的第一项要求”。前面的事实、边界、禁止事项是防止新会话将 MS-Image 误改为 QJ 式平台或空壳微服务的必要上下文。
- 该 Prompt 要求新会话先做只读审计；MR-1 已完成，后续只对新的最小切片请求具体授权，避免在当前存在未提交用户文件的前提下重复进行大范围 `git mv`。
- `MR-1` 只是 Monorepo 的基础收敛，不等同于 AI Control、真实 Provider、模型竞速、Evaluation 独立服务已经完成。
