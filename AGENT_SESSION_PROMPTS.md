# MS-Image 新会话提示词

> **当前有效恢复入口**：始终先按 `AGENT_HANDOFF.md`、`.agent-handoff/snapshot.md` 和用户本轮授权恢复。项目级当前开发合同为 `docs/ms-image-current-development-contract.md`；每次任务必须先核对其中第 3 章的完成度总账，并声明单一目标、write set、外部权限、完成条件和停止条件。旧完整路线图和下方历史 Prompt 只能解释由来，不能覆盖当前源码、snapshot 或用户授权。
>
> 下方“历史 P1/P2 提示”仅保留用于解释旧会话条件，**禁止**作为当前启动入口；其中的旧 SHA、已实现范围和兼容处理不得覆盖当前 worktree/handoff 事实。

## 开启当前项目开发会话（当前入口）

```text
请在当前工作区继续工作，并严格遵循：
docs/ms-image-current-development-contract.md

开始前必须读取：
1. AGENTS.md
2. AGENT_HANDOFF.md
3. .agent-handoff/snapshot.md
4. .agent-handoff/risks.md
5. .agent-handoff/backlog.md
6. docs/ms-image-current-development-contract.md
7. 当前任务直接相关源码和既有测试

必须先按开发合同第 3 章逐项核对已完成能力，明确本轮不会重复开发哪些能力。
然后读取 snapshot 中明确的 `Active development objective`，并与用户本轮授权核对；如果 snapshot 没有明确 active objective，立即停止并报告，不要自行猜测或选择 backlog 中的其他任务。

第一条回复必须输出：当前唯一目标、阶段、已完成能力核对、代码事实和 file:line、
精确 write set、外部调用权限、完成条件、停止条件。

如果发现目标已完成、文档与源码冲突、需要新增职责或需要超出授权的外部操作，
立即停止并报告，不要自动选择 backlog 中的另一个任务。
```

## 开启当前 XRay Runtime、Nacos Prompt 与完整能力开发会话（历史入口，禁止作为当前入口）

> 当前代码、配置、数据库和真实 AI 网络链的审计结论以 `docs/refactor/24-current-runtime-audit-and-next-development-guide.md（当前运行时审计、完整 XRay 开发路径与新会话交接）` 为准。`21（完整能力合同）`、`22（逐层架构参考）`、`23（旧实施指南）` 仅分别保留目标范围、架构说明和历史阶段目标，不能覆盖 24 号文档中的当前运行事实。

```text
当前任务：基于当前 `/Users/mozhicheng/workspace/code/cy-code/ms-image` 工作树，继续完成 XRay（X 光）完整链路的下一最小可验证切片。目标不是只补基础框架，也不是一次性打开 TargetedReview（专项复核）、Retry（重试）、Fallback（自动降级）和 Race（双通道竞速）；必须按证据和依赖顺序实施。

开始前必须亲自完整阅读：
1. `AGENTS.md`；
2. `AGENT_HANDOFF.md`；
3. `.agent-handoff/snapshot.md`；
4. `.agent-handoff/risks.md`；
5. `.agent-handoff/backlog.md`；
6. `docs/refactor/24-current-runtime-audit-and-next-development-guide.md`；
7. 本切片直接相关的源码、已有测试、模型与迁移文件。

当前唯一可开绿灯的事实：
`MS_IMAGE_CORE_AI_NETWORK_CHAIN_PASSED（MS-Image 核心 AI 网络链路已通过）`。
它只证明非医疗链 `Nacos Prompt（Nacos 提示词）读取 -> Prompt 渲染/消息组装 -> 环境引用密钥解析 -> OpenAI-compatible Gateway（OpenAI 兼容网关）-> 外部平台/模型 -> 严格 JSON Schema（JSON 结构合同）` 已真实通过。

当前不得误报：
`FULL_WORKER_RUNTIME_NOT_QUALIFIED（完整 Worker 运行时未资格化）`；
`MEDICAL_ACCURACY_UNKNOWN（医学准确率未知）`；
`MEDICAL_RELEASE_NO_GO（医学发布不可放行）`。

关键运行事实：
- `BROKER_ENABLED（消息代理开关）=true（开启）`，但这不等于 RabbitMQ/Celery（消息队列/异步任务）已真实资格化；
- `AI_GATEWAY_ENABLED（AI 网关开关）=true（开启）`；
- 启用 Gateway 时固定使用 `EnvironmentReferenceSecretResolver（环境引用密钥解析器）` 与 OSS `AES256（AES-256 加密）` response store（响应存储）；不再存在可切换这两项的环境配置字段；
- 当前进程环境没有匹配 `AI_GATEWAY_SECRET_ENV_PREFIX（AI 网关密钥环境前缀）` 的非空 Secret（密钥）变量，因此真实 `secret_ref（密钥引用）` 仍会 fail-closed（失败关闭）；
- `ALIYUN_OSS_*（阿里云 OSS 配置）` 已完成隔离 synthetic（合成）AES256 PUT/HEAD、Worker GET、同机 signed GET 和 cleanup；Provider（模型提供方）外部可达性与完整任务链仍未资格化；
- 当前 `.env（环境配置文件）` 未见常态化 `NACOS_*（Nacos 配置）` 或 `AI_PROMPT_NACOS_*（AI 提示词 Nacos 配置）`；
- 禁止为了跑通而关闭响应加密、把 Secret（密钥）写入数据库/Nacos/日志，或把 Secret 输出到终端。

数据库事实：
- 旧 MySQL（关系数据库）`ms_image（影像库）` 有 45 张 Legacy（遗留）表；
- 旧 `session_record（会话记录）`、`ai_prompt_template（AI 提示词模板）`、`ai_api_connection（AI 接口连接）`、`ai_model_pool（AI 模型池）` 与目标 Runtime（运行时）ORM 同名不同义；
- 未经用户明确确认，禁止建库、迁移、改表、删表、重命名或执行 `DROP TABLE（删除表）`；
- 推荐目标是保留 `ms_image（旧影像库）` 为 Legacy/Archive（遗留/归档），后续新建 `ms_image_runtime（在线运行时库）` 与 `ms_image_eval（离线评测库）`；
- 不恢复 `file_asset（公共文件资产）` 表，OSS（对象存储）保存对象，领域表保存对象引用及完整性事实。

固定架构合同：
- `API（接口） -> Service（服务） -> DalBase CRUD（数据访问） -> Model/DB（模型/数据库）`；
- 不新建 Repository（仓储）、第二 CRUDBase（数据访问基类）、DatabaseService（数据库服务）、平行 service 包或新微服务；新业务 Service（服务）只进入已有 `apps/backend/services/`；
- 新 MySQL（关系数据库）表不用 Foreign Key（外键）、Enum（枚举）、tenant_id（租户标识）或联合主键；每表使用独立 `VARCHAR(64)` 不透明 `id（主键）`；接口 ID 放 query（查询参数）或 request body（请求体），不使用 `/{id}`；
- 事务内禁止 OSS/Broker/Provider（对象存储/消息代理/模型提供方）网络 I/O（输入输出）；
- Worker（工作进程）只能使用 Task Snapshot（任务冻结快照），不得读取 Nacos latest（Nacos 最新值）或自动发布 Prompt（提示词）；
- 禁止用 Python（程序规则）改写 `normal（正常）/abnormal（异常）/review_required（需复核）/non_diagnostic（影像不可诊断）`；
- 不删除 v1（旧版）兼容链，不生成独立测试脚本或迁移脚本；除非另有明确授权。

严格实施顺序：
`P0 Database Baseline（数据库基线） -> P1 Worker Runtime Security Qualification（工作进程运行时安全资格化） -> E1 Primary-only Runtime（仅主读真实运行链） -> M1 Primary Medical Baseline（主读医学基线） -> Q3 Primary Prompt A/B（主读提示词配对实验） -> Q4 Second Provider Qualification + Model A/B（第二模型资格化与模型对比） -> M2 FamilyRouting + TargetedReview（专项家族路由与专项复核） -> R1 Retry（重试） -> R2 Fallback（自动降级） -> R3 Race（双通道竞速）`。

本轮先从 handoff（代理交接）和源码判断当前所处阶段。默认优先 P1：以最小范围审计并补齐正式 Worker（工作进程）使用的 Secret Resolver（密钥解析器）、Encrypted Response Store（加密响应存储）、OSS Signer（OSS 签名器）和 Provider Attempt Lookup（模型尝试查询）合同，然后才进入 E1。若用户明确要求本轮实现 Prompt（提示词）生命周期，则只实现最小 `PromptPublicationService（提示词发布服务）`：审核完成的版本化 Prompt Package（提示词包）-> Nacos Publish（Nacos 发布）-> Read-after-write（写后回读）-> 现有 PromptImportService（提示词导入服务）-> AIConfig（AI 配置）编译与审计；不新建发布表，复用 `ai_control_audit_record（AI 控制面审计记录）`，绝不允许 Worker 自动发布。

每个切片开始前，第一条回复必须给出：
1. 当前代码事实和 `file:line（文件:行号）` 证据；
2. 目的、为什么现在做、相对上一阶段的唯一主要变量；
3. 输入、处理、输出、下游消费者、状态机和失败语义；
4. 幂等、事务边界、unknown（未知尝试）、取消、迟到结果、重试与恢复策略；
5. 精确 `write set（写入文件集合）`；
6. 是否需要表、字段、迁移、外部配置或新 Service（服务）；没有则写“不需要”；
7. 工程 Gate（工程门禁）、医学 Gate（医学门禁）、Stop（停止）条件和 Rollback（回滚）单位；
8. 哪些真实环境验证尚未运行或未获授权。

完成后：
- 运行改动相关的既有 pytest、Ruff、compileall 和 `git diff --check`；
- 真实 DB/OSS/Broker/Provider（数据库/对象存储/消息代理/模型提供方）或医学验证未运行时明确写 `NOT RUN（未运行）`，不能用 Mock（模拟）代替真实资格；
- 分别报告 `CODE_IMPLEMENTED（代码已实现）`、`RUNTIME_QUALIFIED（运行时已资格化）`、`MEDICALLY_VALIDATED（医学效果已验证）`；
- 更新 `AGENT_HANDOFF.md`、snapshot、work-log、validation、decisions、backlog、risks，并运行 handoff maintenance（交接维护）。
```

## 开启 XRay 后续修正与实施会话（历史入口，不再作为当前入口）

> 完整可复制版本位于 `docs/refactor/23-xray-next-phase-correction-and-implementation-guide.md（X 光后续修正与分阶段实施指南）` 第 16 节。P0-A Targeted Prompt command（专项提示词命令）的 family/focus（家族/关注点）传递已经完成，不得重复修改。新会话从 P0-B Reliable Execution Contracts（可靠执行合同）、Q0 Prompt Inventory（提示词盘点）和 Q1 Prompt Runtime Contract（提示词运行合同）开始，再按证据进入 E1 Primary Runtime（真实单 Provider 主读工程链）。

```text
请继续开发 `/Users/mozhicheng/workspace/code/cy-code/ms-image` 的 XRay（X 光）AI（人工智能）与 Prompt（提示词）完整链路。先完整阅读 `AGENTS.md`、`AGENT_HANDOFF.md`、`.agent-handoff/snapshot.md`、`.agent-handoff/risks.md`、`.agent-handoff/backlog.md` 和 `docs/refactor/23-xray-next-phase-correction-and-implementation-guide.md`，再阅读当前阶段即将修改的源码和现有测试。

当前状态必须保持为：`D5_CODE_FOUNDATION_COMPLETE / ENGINEERING_SEGMENTS_PASSED / FULL_RUNTIME_NOT_QUALIFIED / MEDICAL_ACCURACY_UNKNOWN / MEDICAL_RELEASE_NO_GO`。v2 Targeted Prompt command 的 family_key/focus_key/primary_complete_result 传递已完成并有合同测试，不要重复修改。

本会话先完成三个可分别验收的前置：P0-B 核验并最小补齐 StudyPreparation 调用前资格、unknown Attempt、Task cancel、迟到 Winner、requested_model/actual_model 和报告通知幂等；Q0 只读盘点 Nacos、数据库 Prompt/Connection/ModelPool/Config/Schema/消息合同及引用关系；Q1 选择唯一 Primary 候选，验证安全变量、developer/user/image/schema 分层、不可变 Config、Task 快照与重放一致性。无需迁移或额外外部授权时，直接进入 E1，从 ready revision 经 Outbox、Broker/Worker、OSS、Provider、Attempt/Stage、DecisionFinalization 到不可变 Report 的真实单 Provider Primary 最小切片。

Prompt 必须遵循 `Shared Medical Core（共享医学核心） + Primary Frozen Entry（主读冻结入口） + Targeted Frozen Entry（专项冻结入口）`，只允许安全变量，模型身份由 Connection/ModelPool/Config 冻结，不恢复旧器官 Prompt，不让 Python 投票、拼接或改判医学结果。业务链保持 `API -> Service -> DalBase CRUD -> Model/DB`；不新增无证据表、Service、Family、Repository、CRUDBase、第二套 Runtime 或公共 file_asset。未经授权不新增/执行迁移、不生成独立测试脚本、不删除 v1 兼容链。

开始修改前输出当前事实与 file:line、阶段、精确 write set、输入/处理/输出/失败语义、幂等/事务/恢复策略、工程与医学 Gate、停止条件和回滚单位；然后直接实现当前最小可验证切片。结束时分别报告 `CODE_IMPLEMENTED（代码已实现）`、`RUNTIME_QUALIFIED（运行时已资格化）`、`MEDICALLY_VALIDATED（医学效果已验证）`，并更新 handoff。完整实施顺序和详细合同以 23 号文档第 16 节为准。
```

## 开启完整 XRay AI 与 Prompt 链路开发会话（历史入口，不再作为当前入口）

> 完整版本位于 `docs/refactor/22-xray-full-ai-prompt-chain-development-guide.md（X 光完整 AI 与提示词链路开发指南）` 第 17 节；以下内容可直接复制。

```text
请继续开发 `/Users/mozhicheng/workspace/code/cy-code/ms-image` 的完整 XRay（X 光）AI（人工智能）与 Prompt（提示词）链路。目标不是只完成基础框架，而是按依赖顺序最终完成真实 Primary（主读）运行、Primary 医学基线、FamilyRouting（家族路由）、TargetedReview（专项复核）、Multi-Attempt Retry（多物理尝试重试）、Multi-Provider（多模型提供方）、Automatic Fallback（自动降级）、Dual-Lane Race（双通道竞速）、Prompt 优化、Evaluation（评测）和发布门禁。

启动时：

1. 只操作 `/Users/mozhicheng/workspace/code/cy-code/ms-image`。
2. 完整阅读 `AGENTS.md`、`AGENT_HANDOFF.md`、`.agent-handoff/snapshot.md`、`.agent-handoff/risks.md`、`.agent-handoff/backlog.md`、`docs/refactor/22-xray-full-ai-prompt-chain-development-guide.md` 和 `docs/refactor/21-xray-complete-capability-chain-and-session-prompt.md`，再读当前阶段相关源码和测试。
3. 运行 `git status --short`、`git diff --name-status`、`git diff --stat`；保护其他用户/会话的未提交改动，禁止 reset、clean、checkout、restore、stash、整文件覆盖和 `git add -A`。
4. 当前统一状态是 `D5_CODE_FOUNDATION_COMPLETE（D5 代码基础完成） / ENGINEERING_SEGMENTS_PASSED（工程分段检查通过） / FULL_RUNTIME_NOT_QUALIFIED（完整运行时未资格化） / MEDICAL_ACCURACY_UNKNOWN（医学准确率未知） / MEDICAL_RELEASE_NO_GO（医学发布禁止放行）`。不得把代码存在、Fake/Mock（模拟运行）或分段检查写成完整真实链或医学验证通过。

固定合同：

- 所有业务链保持 `API（接口） -> Service（服务） -> DalBase CRUD（数据访问层） -> Model/DB（模型/数据库）`；Worker 也经 Service/DAL。
- 不新增第二套 Runtime、Repository、CRUDBase、DatabaseService 或平行 service 包。
- 公共 Service 保持 SessionService、StudyService、ImageService、TaskService、ImagingExecutionService、AIConfigService、AIRequestService、ReportService；医学能力放在现有 Stage handler。
- Stage 保持 StudyPreparation（检查准备）、JointPrimaryReader（联合主读）、FamilyRouting（家族路由）、TargetedReview（专项复核）、DecisionFinalization（结果定稿）。
- 固定五个顶层 Family：thoracic（胸腔）、abdominal（腹腔）、appendicular_orthopedic（四肢骨关节）、axial_orthopedic（轴骨骼）、head_neck（头颈）。Family 只用于评测分层、失败归因和确定性专项路由，不按 Family 新建表、Service 或 Prompt，也不默认分别调用模型。
- Prompt v2 保持一份冻结完整 XRay Prompt 正文：没有 PRIMARY_RESULT_JSON（主读结果）时运行 Primary mode（主读模式）；存在主读结果和唯一 Family/Focus（家族/关注点）路由证据时运行 Targeted mode（专项复核模式）。
- TargetedReview 最多一次视觉调用，读取同一完整 Study，输出新的完整病例结果；禁止输出 patch（补丁）后由 Python 拼接。
- 一个医学 Stage 对应一个 Logical Call（逻辑调用）；Retry、Fallback、Race 只增加 Physical Attempt（物理尝试）。Winner 只能由 winner_attempt_id CAS（胜出尝试标识比较交换）和 first_technically_valid（首个技术合同有效结果）决定，禁止医学投票、拼接、选更异常结果或程序改判。
- Retry 只处理同候选的明确临时工程失败；unknown（未知）必须按原模型提供方幂等身份对账，禁止盲发。
- Fallback 只处理明确工程失败，不根据 normal/abnormal（正常/异常）触发；不新增 FallbackService。
- Race 最多两个通道；未证明单通道、候选资格、成本和 Winner 合同前不得启用。
- 不建设公共 file_asset（文件资产）表；OSS 存对象，image_record（影像记录表）存对象键、哈希、大小、状态和版本。
- MySQL 不使用 foreign key（外键）或 enum（枚举）；每表独立 opaque VARCHAR(64) id（不透明字符串主键）；接口 ID 只放 query（查询参数）或 request body（请求体），不使用 `/{id}`。
- 未经明确授权，不新增或执行迁移脚本，不生成独立测试脚本，不删除 v1 兼容链，不处理 Web 管理页面和人工病例复核。

严格按以下累计顺序推进，最终不得漏掉任何一项：

`E1 Primary Runtime（主读真实运行链） -> M1 Primary Medical Baseline（主读医学基线） -> M2 FamilyRouting + TargetedReview（家族路由与专项复核） -> E2 Multi-Attempt Retry（多物理尝试重试） -> E3 Multi-Provider（多模型提供方） -> E4 Automatic Fallback（自动降级） -> E5 Dual-Lane Race（双通道竞速） -> M3 Medical Prompt Optimization（医学提示词优化）`。

先用源码、handoff 和真实运行证据判断当前阶段。若 E1 没有共享非生产真实 `Outbox -> Broker/Worker -> OSS Signed URL -> Provider -> Encrypted Response -> Attempt/Stage Finalize -> DecisionFinalization -> Report` 证据，当前第一任务仍是 E1；不得跳级，也不得把后续能力永久排除。

每阶段修改前先给出：当前代码事实与 file:line 证据；阶段目的；输入、处理、输出和失败语义；幂等、事务边界、retry、unknown、取消、迟到结果和恢复策略；精确 write set；是否需要新字段/表/Service；工程与医学 Gate、停止条件、回滚单位；相对上一阶段唯一主要变量。

实现当前最小可验证切片，优先扩展现有测试。运行相关现有 pytest、Ruff、compileall 和 git diff --check；真实基础设施或医学验证不能运行时明确写 NOT RUN（未运行），不得用 Fake/Mock 替代。

准确率优化必须先做 label audit（标签审计），冻结 Gold、病例版本和图像哈希，建立 ABN->normal、NOR->abnormal、review_required、non_diagnostic、parse/schema、timeout/rate-limit 和 image coverage Failure Bank。每次 Prompt/模型实验只改变一个主要变量，使用同病例、同图像、同 Gold、同 Schema 和同评分器做 Paired A/B；固定 Failure Bank 与完整回归通过后才能进入 Holdout。禁止改标签、跳过失败病例、用模型输出推断标签或用 Python 修改医学结论。

每阶段结束分别报告 CODE_IMPLEMENTED（代码已实现）、RUNTIME_QUALIFIED（运行时已资格化）、MEDICALLY_VALIDATED（医学效果已验证），并按 AGENT_HANDOFF_PROTOCOL 更新 handoff 文件、运行 maintenance。不要为了显得完整而添加没有证据的新表、新服务、新家族或医学规则。
```

## 开启新的重构会话（历史 P1/P2 提示，禁止作为当前启动入口）

```text
请开始重构 /Users/mozhicheng/workspace/code/cy-code/ms-image。

零、任务目标与执行方式

本会话不是继续讨论架构，也不是再生成一份设计文档，而是基于当前代码和已冻结文档直接开始目标实现。
当前已完成 P1 影像接入底座代码；不要重新生成或覆盖 P1。先恢复 handoff（代理交接）、确认当前授权和已提交源码，再决定是做经授权的 P1 真实演练还是进入 P2；不要停在“建议、计划或审计结论”，必须形成与当前任务一致的可验证增量。若源码与设计存在直接冲突，先给出 `file:line` 证据并修正对应权威合同；不要凭偏好
重新命名表、增加 Service、改变 Canonical XRay Chain 或另建平行运行时。

一、授权与禁止动作

1. 本次明确授权完全重构内部业务代码、目录、类和 Worker；旧 `xray_accuracy` 内部结构不是兼容目标。
2. 必要时可以提出新增、拆分或合并目标表，但必须先证明独立事实 owner、生命周期、查询、事务/恢复、
   权限或保留合同，并同步设计母文；不要按“10+4”数字机械建表。
3. 本次不授权：Alembic/数据迁移脚本、新建测试脚本、真实数据库写操作、生产双写、真实对象批量迁移、
   生产发布。上述动作必须单独获得授权；允许运行仓库已有的非破坏性检查和测试。
4. P1 不删除或改写旧 XRay API/表，不开启生产双写；旧入口保持原状，直到 P6 Compatibility Adapter
   （兼容适配器）和迁移方案获得明确授权。

二、启动恢复与脏工作树保护

先确认当前目录的 `AGENTS.md` 已加载，再按顺序亲自读取：
1. `AGENT_HANDOFF.md`
2. `.agent-handoff/snapshot.md`
3. `.agent-handoff/risks.md`
4. `.agent-handoff/backlog.md`
5. 变更长期架构时读取 `.agent-handoff/decisions.md`
6. `docs/refactor/README.md`
7. `docs/refactor/02-target-architecture.md`
8. `docs/refactor/03-database-and-storage-design.md`
9. `docs/refactor/05-development-guide.md`
10. `docs/refactor/06-refactor-migration-and-validation-plan.md`
11. `docs/refactor/08-new-session-handoff.md`
12. `docs/refactor/10-xray-detailed-flow.md`
13. `docs/refactor/12-canonical-xray-layer-responsibility-contract.md`
14. `docs/refactor/13-refactor-base-decision.md`
15. 设计 XRay 专项/Prompt/Targeted 时读取 `docs/refactor/14-xray-specialty-design.md`
16. `docs/ms-image-final-architecture-and-database-design.md` 中与 P0/P1、权限、OSS、
    Session/Study/Series/Image/Outbox 和核心不变量直接相关的章节
17. 即将修改的确切源码；修改前必须亲自完整读取。

恢复当前目标、状态、下一动作、活动文件、阻断和 UNKNOWN。开始编辑前固定运行并阅读：
`git status --short`、`git diff --name-status`、`git diff --stat`。所有已有修改和未跟踪文件默认属于用户；
若与本切片重叠，完整阅读并在现状上合并。禁止 reset、checkout、覆盖、批量删除或回退无关改动。

`9a45209a` 是重构开始时的初始提交；当前分支 `codex/ms-image-refactor` 已包含 P1 收口提交 `6dfd8d1`。不要 reset/clean 到初始提交，也不要重写已完成的 P1。保留公共可靠性语义，后续仅在当前授权下内部模块化替换未完成的 XRay 专项领域；不得另建第二套 API/Runner/Outbox/OSS Gateway/数据库事实源。

`.env` 当前已被 Git ignore（忽略）且不进入版本控制候选。仍然只能检查变量名、文件状态和是否命中 ignore，禁止输出任何值；提交前执行不打印值的 Secret 扫描，禁止直接 `git add -A`。不得自动 commit、stash、reset 或 clean；已有工作树文件不能因为“未提交”就被视为可删除。

三、权威边界：必须按问题分轴，不使用单一总排名

1. 项目规则与授权：当前用户授权 + 当前适用 `AGENTS.md`。
2. 当前实现事实：当前 worktree 的源码、配置、依赖和启动合同。
3. 当前外部事实：经授权读取并绑定环境/时间的真实 DB schema、OSS bytes/hash、Broker/Provider trace。
4. 目标设计：`docs/ms-image-final-architecture-and-database-design.md`。
5. 实施指导：`docs/refactor/*`，不得独立覆盖设计母文。
6. 医学准确率：冻结 Gold + 同病例 paired A/B + 确定性 scorer + isolated Holdout。
7. 历史解释：`docs/history` 和旧外部设计包，只解释由来，不作为当前建表合同。

旧真实 schema 只能证明现状，不能覆盖目标 schema；设计母文定义目标，但不能证明已经实现、迁移或提高
准确率。冲突先归类到对应权威轴，再记录现状与目标差距，并使用
`CONFIRMED / INFERRED / PROPOSED / UNKNOWN / N/A`。

四、Canonical XRay Chain（X 光权威主链）

两个 Profile 的执行边界已经由用户冻结，开发和文档不得自行改变：

1. `xray_primary_v1`：`StudyPreparation -> JointPrimaryReader -> DecisionFinalization -> Report`。
2. `xray_targeted_review_v1`：Primary 后进入确定性 FamilyRouting；`primary_final` 直接进入
   DecisionFinalization，`targeted_review` 最多调用一次 TargetedReview，成功并输出完整病例结果后进入
   DecisionFinalization。
3. FamilyRouting 仅属于 Targeted 实验 Profile，不调用模型、不读 Gold、不修改医学结论。
4. TargetedReview 一旦触发，技术失败必须 fail closed，不能静默回退 Primary。
5. Evaluation Plane 只产生候选证据；人工审批后，Control Plane 才能激活候选配置。

每个目标 Service/Stage 的接收、必填约束、成功输出、失败输出、下游消费者和数据落点，以
`docs/refactor/12-canonical-xray-layer-responsibility-contract.md` 第 20 章为实现合同。实现不能只对上函数名：
必须保证前一层交付对象与下一层接收对象一致，工程失败 TF、调用前覆盖终态 CF 和医学输出 OUT 不得互换。

五、当前执行范围

P1A/P1B/P1C 已完成代码并已提交：Session/Study/Series/Image 的 Model -> Schema -> DAL(DalBase) -> Service、API/依赖注入/路由、唯一 ObjectStorageGateway，以及 Image `validating`/Outbox/Relay/Worker/reconcile/revision。P1 的状态严格是 `CODE_IMPLEMENTED / NOT_MIGRATED / NOT_RUNTIME_VALIDATED`，不得重新生成 P1 或把它写成真实环境通过。

每个新会话先做有界恢复核对：Secret、数据库事务内外部 I/O、身份与资源授权、Broker、Trace/Audit、API/Admin/Worker 启动合同与 Artifact 新鲜度。随后只按用户当前授权执行下列之一：

1. 经单独授权后，设计/执行 P1 的迁移和真实 MySQL/OSS/RabbitMQ 演练；或
2. 开始 P2：复用 P1 的同一 Outbox/Relay，实现 Task + first Stage + Outbox 原子创建、lease/CAS 和 zero-model replay（零模型重放）。

P2 不得创建第二套中继、队列或事实源，也不接医学 Provider。P1 的 Image 校验 Outbox 属于影像生命周期，P2 只扩展同一可靠执行底座。

六、已实现 P1 必须持续满足的不变量

1. `Image uploading -> validating` 与 `Outbox(validate_image)` 在同一数据库事务；事务提交后 Relay 才发布。
2. OSS HEAD、服务端流式 hash/size/MIME/真实格式校验在数据库事务外，由 Worker 执行，不阻塞 API 长请求。
3. 只有服务端完整校验通过才能 ready；失败进入 quarantined。客户端声明 hash、signed URL、OSS ETag 或
   HEAD 结果均不能单独成为最终真相，bytes 和 signed URL 不落库。
4. 替换影像必须创建新 Image version；只有新版本 ready 且 Study revision CAS 成功后，旧版本才 superseded。
5. required Series/Image 集合不完整时 Study 不得 ready；Series count/manifest 从当前 revision 的 ready Image
   确定性重算，不能只做计数增减。
6. 同一个 idempotency key + 不同 payload 必须返回冲突；重复消息由 aggregate version、CAS 和 lease generation
   幂等处理。
7. DB 事务中不得调用 OSS/Broker/Provider；API/Service/Worker 不直接拼 SQLAlchemy，全部数据库访问经实体
   DAL 并复用 `apps.runtime.core.crud.DalBase`。
8. 每张目标表必须有服务端生成、非空、独立 `id VARCHAR(64)` 单列主键；不使用 Foreign Key、数据库 Enum、
   联合主键或 `tenant_id`。状态/类型使用 string/json/timestamp，并有中文候选注释。
9. 不新增 Repository、第二套 CRUDBase、DatabaseService、平行 service 包或第二套 OSS Gateway。
10. P1 代码必须明确区分目标新事实与旧兼容读取；旧 `xray_accuracy` Model/Service 不得成为新实体的基类或
    新写入 owner，LegacyCompat 不能创建新的医学事实。

七、身份与 OSS key 过渡

目标表不保存 `tenant_id` 不等于删除认证。当前可信 tenant claim 可以暂时作为旧 API 的兼容访问范围，
但不得写入目标表或由 request body/query 覆盖。目标资源 owner 使用已验证 subject/service identity、业务 scope
和资源归属校验；请求体不能指定或覆盖 owner 身份。

新 OSS key 使用领域 owner namespace + 全局 image_id + generation/version，不再由 tenant 派生。历史
tenant-derived key 通过现有 OSS 网关内的兼容适配器只读；不得盲目重写旧对象，也不得创建第二套网关。
移除旧 tenant dependency 前，必须先证明目标 owner 授权、旧 key 读取和越权拒绝合同闭环。

八、汇报、完成状态与关闭

修改前简短报告：确认的当前状态、P1 已实现边界、当前授权的切片、预计修改文件、验证方式；然后直接执行，
不要再次询问是否允许内部重构。

第一轮汇报必须明确写出：
- `HEAD=6dfd8d1`（除非新会话发现已推进），且 P1 已提交；
- 当前状态是 `P1_CODE_IMPLEMENTED / NOT_MIGRATED / NOT_RUNTIME_VALIDATED`，P2+ 尚未实现；
- 本轮正在执行 P1 真实验证准备或 P2 中哪一个受授权切片；
- 哪些现有安全/可靠性语义保留，哪些 `xray_accuracy` 专项代码准备替换；
- 验证只证明工程合同，不证明医学准确率。

由于本次未授权迁移、新测试脚本、真实数据库和真实对象演练，P1 即使代码完成，最高只能标记：
`CODE_IMPLEMENTED / NOT_MIGRATED / NOT_RUNTIME_VALIDATED`。不得把静态检查、mock/replay 或现有测试通过
写成 G4 OSS/revision 已通过，更不得宣称医学准确率提高。

结束前更新最小必要 handoff：snapshot、work-log、validation、backlog/risks，长期决策才写 decisions；明确
已实现、未迁移、未运行验证、阻断和 UNKNOWN。运行 handoff maintenance --compact-if-needed，并报告所有
已运行、失败和有意未运行的检查。
```

## 继续特定任务

```text
继续任务：<填写具体任务>。

把“继续”视为明确继续执行，不要空回复。
先读取 AGENT_HANDOFF.md、snapshot.md、risks.md 和 backlog.md，
说明上一步、下一动作和将修改的文件，再读取任务直接相关源码并执行。
不要依赖聊天记录代替仓库事实，不要撤销其他人的未提交改动。
```

## 会话关闭

```text
结束本轮前，请更新：
- .agent-handoff/snapshot.md：替换当前状态和下一动作；
- .agent-handoff/work-log.md：记录实际改动；
- .agent-handoff/validation.md：记录运行、失败和未运行验证；
- .agent-handoff/backlog.md / risks.md：更新待办、阻断和 UNKNOWN；
- .agent-handoff/decisions.md：只记录长期决策。

运行 agent-handoff maintenance --compact-if-needed，
然后说明已完成、已验证、未验证和剩余风险。
```

## 交接质量审查

```text
请审查并直接修复多文档 handoff（代理交接）：
AGENT_HANDOFF.md 只能是索引；snapshot 必须短且替换式更新；
下一动作必须可执行；决策必须有理由和证据；
验证必须区分 passed/failed/not run；
风险和 UNKNOWN 不能藏在工作日志；
禁止保存 Secret、长日志、聊天记录和不可验证猜测。
完成后运行维护检查。
```

## 开启 QJ 借鉴与模块收敛调整会话

```text
当前任务：仅在用户明确授权“执行 `docs/refactor/16-qj-reference-and-modular-convergence-plan.md` 的 QJ 收敛方案”时，对 MS-Image 做受控模块收敛调整。先确认用户本轮授权的 Phase；只有该明确授权下用户未指定切片时，才默认执行 16-Phase A（部署真相、Worker 角色、入口/Compose 边界），不跨 Phase。若用户只说“按文档开始/继续重构”，必须先以当前 snapshot 和 15 号文档的 Phase 2 下一动作判定任务。

工作区：`/Users/mozhicheng/workspace/code/cy-code/ms-image`。
参考仓库：`/Users/mozhicheng/workspace/code/cy-code/qj-open-plataform`，仅作为外部商业控制面、DatabaseRegistry、Compose 和 Kong 边界参考；不要合并仓库、数据库或业务主数据。

开始前严格执行：
1. 阅读 `AGENTS.md`、`AGENT_HANDOFF.md`、`.agent-handoff/snapshot.md`、`risks.md`、`backlog.md`。
2. 阅读 `docs/refactor/08-new-session-handoff.md`、`15-full-chain-gap-analysis-and-execution-plan.md`、`16-qj-reference-and-modular-convergence-plan.md`。
3. 若本轮涉及 AIConfig、AIRequest、Prompt、Schema、Provider-disabled、JointPrimaryReader 或 TargetedReview，必须先读 `docs/refactor/17-prompt-runtime-contract-and-minimal-provider-plan.md`；其调用数、Config Release、编译、泄漏和 provider-disabled 真 Bundle 合同不得因目录收敛而改变。
4. 实现公共/专项边界时再读 `14-xray-specialty-design.md`、`04-service-and-stage-design.md`、`05-development-guide.md`，并亲自完整阅读即将修改的源码。
4. 先运行 `git status --short`、`git diff --name-status`、`git diff --stat`，保护所有未提交改动；禁止 reset、clean、checkout、`git add -A` 或整文件覆盖。

固定架构合同：
- QJ 拥有 Kong、Project/API Key、Capability、限流、Usage/Wallet/Ledger、客户 SDK/Webhook；MS-Image 不复制这些事实。
- MS-Image 公共在线新主链唯一拥有 Session/Study/Series/Image、Task/Stage/Outbox、AI Config/Call、Report；Evaluation 保持独立数据库/队列/Worker。
- 新 XRay 能力只能经 Profile、Prompt、Schema 和 Stage handler 扩展；`xray_accuracy` 当前是 compatibility/legacy 域，消费者与迁移映射 UNKNOWN 前不扩展、不删除。
- 8 个在线业务 Service 保持为 Session/Study/Image/Task/ImagingExecution/AIConfig/AIRequest/Report；Stage handler 位于既有 `apps/runtime/service/` 内部，不新建平行 service 包。
- Stage 归属：StudyPreparation、DecisionFinalization 为 common；JointPrimaryReader、FamilyRouting、TargetedReview 为 XRay。
- 数据访问统一经 `DalBase` 实体 DAL；不新建 Repository/第二 CRUDBase/DatabaseService。
- API 不使用 `/{id}`；新表不使用 FK/Enum/联合主键/tenant_id；事务内禁止 OSS/Broker/Provider I/O。
- 不生成迁移/测试脚本、不连接真实 MySQL/OSS/RabbitMQ/Kong/Nacos/Provider，除非用户明确单独授权。

先在第一条回复中写明：当前 HEAD/dirty state、用户授权的 Phase、计划修改的文件、保留的不变量和验证方式；随后直接执行。结束前更新 handoff，并运行 maintenance。工程 fake/静态检查绝不能表述为真实运行、Provider 资格或医学准确率通过。
```
