# Archived Validation — pre-2026-08-30 sections

> 从 `.agent-handoff/validation.md` 原样归档；原因：活动验证文件超过 64 KiB。

## 2026-08-29 — 全 Stage Prompt 覆盖与当前全链复验

| 检查 | 结果 | 说明 |
|---|---|---|
| 当前小样本 | PASS WITH RISK | 5 个新 Task 中 4 个 completed/final、1 个 fail-closed；3 个进入 Targeted 的 Task 中 2 个成功、1 个 manifest 失败。样本过小，不能当正式失败率。 |
| Prompt/Gateway 定向合同 | PASS | `PYTHONPATH=. python3.12 -m pytest -q apps/backend/tests/test_ai_gateway_attempt_contracts.py apps/backend/tests/test_ai_prompt_control_plane_contracts.py`：`186 passed, 38 warnings`。 |
| Backend 全量 | PASS | `192 passed, 38 warnings`。 |
| 运行态清理 | PASS | Runtime、AI Control、Relay、Worker、Beat、8010/8002 与 launcher lock 均已清理。 |

```text
FULL_MODEL_STAGE_PROMPT_COVERAGE_QUALIFIED
CAT_DOG_FULL_CHAIN_PROMPT_ROUTING_QUALIFIED
CAT_TARGETED_PROMPT_RUNTIME_QUALIFIED
DOG_TARGETED_PROMPT_RUNTIME_QUALIFIED

TARGETED_PROVIDER_SOURCE_REF_STABILITY_NOT_QUALIFIED
MEDICAL_ACCURACY_UNKNOWN
MEDICAL_RELEASE_NO_GO
```

## 2026-08-29 — 完整开发架构路线图文档校验

| 检查 | 结果 | 说明 |
|---|---|---|
| 文档生成 | PASS | `docs/ms-image-xray-complete-development-architecture-roadmap.md` 已新增，共 1626 行、51603 bytes。 |
| Markdown 结构 | PASS | 22 个编号二级章节；136 个代码围栏，数量为偶数；头尾内容抽查正常。 |
| 当前 HTTP 接口计数 | PASS | 源码路由装饰器复核：Runtime 29、Admin 6、AI Control 31、Evaluation 9，共 75 个；文档已纠正历史“Runtime 28”计数。 |
| Diff whitespace | PASS | `git diff --check -- docs/ms-image-xray-complete-development-architecture-roadmap.md` 无输出。 |
| 代码/运行测试 | NOT RUN | 本轮仅新增文档，没有修改代码、Prompt、数据库或运行配置，未重新执行 pytest/E2E。 |

## 2026-08-29 — 评审意见合并后的最终路线图校验

| 检查 | 结果 | 说明 |
|---|---|---|
| 文档规模 | PASS | `docs/ms-image-xray-complete-development-architecture-roadmap.md` 为 2141 行、82970 bytes；原交付版为 1626 行。 |
| Markdown 结构 | PASS | 172 个代码围栏且数量为偶数；143 个标题，无标题层级跳跃。 |
| 关键路线 | PASS | R4 已拆为 R4A–R4D；关键路径从 R0A baseline manifest 开始，经 R0B–R0E、R1、R2 后进入 R3 与 Evaluation 主线。 |
| Evaluation 现状 | PASS | 文档明确当前为 `ENGINEERING_SHELL_ONLY`，candidate runner、医学 Scorer、独立 DB/metadata/Alembic/readiness 均未资格化。 |
| 当前 HTTP 接口计数 | PASS | Runtime `/api/v1` 29、Runtime Admin 6、AI Control 31、Evaluation 9，合计 75；另有 4 个显式 `GET /`，decorator endpoint 合计 79。 |
| Prompt identity/SHA | PASS | cat/dog 独立且禁止 common fallback；cat SHA `7ca40d767157fe9c333cfbe22c5e7f91a8b4d9a93f2289bb03a5bacd22d46b74`，dog SHA `460611ef7cfc9ac95e01a7cc6aaf7abc9bb38ec5568fc7489914b9ddf71d903d`。 |
| 旧错误措辞扫描 | PASS | 未命中 `R4：Dataset`、`Primary-only 4 Stages`、`当前全部 HTTP 接口`、`当前共 75 个 HTTP 接口`、`Model/第二 Provider`。 |
| Diff whitespace | PASS | `git diff --check -- docs/ms-image-xray-complete-development-architecture-roadmap.md` 无输出。 |
| Handoff maintenance | PASS | 维护器完成 work-log/backlog 归档；语义合并过时风险后复跑为 `changed=0 warnings=0 unresolved=0`。 |
| pytest/E2E | NOT RUN | 本轮只修订 Markdown 与 durable handoff，没有修改业务代码、Prompt、数据库、迁移或运行配置。 |

## 2026-08-30 — 2–5 图 Runtime 路线图与 Postman 命名校验

| 检查 | 结果 | 说明 |
|---|---|---|
| 文档规模 | PASS | `docs/ms-image-xray-complete-development-architecture-roadmap.md` 为 2204 行、77285 bytes。 |
| Markdown 结构 | PASS | 136 个代码围栏且数量为偶数；无标题层级跳跃。 |
| Runtime 接口计数 | PASS | 文档表格逐行计数为 Runtime 29、Runtime Admin 6、AI Control 31。 |
| Postman 展示名称 | PASS | 上述 66 个接口均有通俗中文名称；主链 Folder 和 00–14 Item 顺序已冻结。 |
| 动态图像数量 | PASS（文档） | 明确 `N ∈ {2,3,4,5}`、最大 5 张、第 6 张 fail-closed；没有把 4 图写成唯一业务合同。 |
| 旧 Postman 边界 | PASS | 已记录旧 `/ai/api/v1.0/...` 路由、固定 4 图、无自动轮询/断言等差异；未将旧集合作为当前验收基线。 |
| Whitespace | PASS | 文档与本轮 handoff 文件尾随空白扫描无命中；已跟踪 handoff 文件 `git diff --check` 无输出。 |
| 代码/运行测试 | NOT RUN | 本轮没有修改可执行代码，也未启动 Runtime/Relay/Worker/Provider；真实 2–5 图 E2E 仍未资格化。 |

## 2026-08-30 — 最终整合开发文档校验

| 检查 | 结果 | 说明 |
|---|---|---|
| 文档规模 | PASS | `docs/ms-image-xray-complete-development-architecture-roadmap.md` 为 3209 行、122114 bytes。 |
| Markdown 结构 | PASS | 208 个代码围栏且数量为偶数；编号顶级章节 1–24 连续、无重复，无标题层级跳跃。 |
| 体位合同 | PASS（文档） | 明确 projection 当前由调用方声明，不是 AI 自动识别；DICOM `ViewPosition` 与 projection QC 均标记为后续能力。 |
| 多图调用合同 | PASS（文档） | 明确每个 Logical Call 一次携带全部 N 图；receipt 只证明发送，`image_assessments` 才是后续逐图覆盖合同。 |
| 分割隔离 | PASS（文档） | 第 13 章将 Segmentation 标记为 `PROPOSED`、非诊断、非阻塞；5 个接口、3 张表和 S0–S6 均未冒充现有实现。 |
| Postman 主流程 | PASS（文档） | 诊断 10A–13A 与可选分割 10B–13B 可并行，报告只依赖 A 链；旧固定 4 图 Collection 不作为当前基线。 |
| 接口路由规则 | PASS | 目标分割接口未使用 `/{id}`；资源 ID 只在 query 或 request body。 |
| 文件身份 | PASS | SHA256 `157e3bc71b995dc8ddff3684b79bffe212a462be251eff9b3616269a68bfd01f`。 |
| Whitespace | PASS | 目标文档和本轮 handoff 文件无尾随空白；已跟踪文件 `git diff --check` 无输出。 |
| Handoff maintenance | PASS | 最终复跑为 `changed=0 warnings=0 unresolved=0`。 |
| 代码/运行测试 | NOT RUN | 本轮只修改文档和 durable handoff；未实现分割代码，未运行真实 2–5 图诊断 E2E 或分割 E2E。 |

## 2026-08-30 — v3.1 文档与 Postman Collection 最终静态验收

| 检查 | 结果 | 说明 |
|---|---|---|
| OpenAPI 接口覆盖 | PASS | Runtime `29/29`、Runtime Admin `6/6`、AI Control `31/31`；文档实现接口矩阵为 `66`，另列 `5` 个 `PROPOSED_NOT_IMPLEMENTED` 分割接口。 |
| Prompt/Call 口径 | PASS | 文档逐接口区分同步医学 Prompt、后续异步医学 Prompt 与 Provider Logical Call；Prompt Catalog 资产计数为 `20`，未被误写为单病例调用次数。 |
| Postman Collection 结构 | PASS | v2.1 schema、合法 `_postman_id`、共 `91` 个 Item；文件为 `postman/MS-Image X-Ray 2-5图完整诊断链.postman_collection.json`。 |
| JSON 请求体 | PASS | 所有 raw JSON body 在静态替换 Collection 变量后均可解析。 |
| OSS 上传鉴权 | PASS | 5 个 signed URL PUT 请求均显式使用 `noauth`，不会误带 Runtime Bearer Token。 |
| 安全门禁 | PASS | 控制面写操作、Admin 写操作、损坏的 Report publish/void 和未实现分割接口均按对应变量默认跳过；`ai-configs/compile-preview` 作为只读 POST 不被误拦截。 |
| 路由与 Secret 扫描 | PASS | Collection 不含旧 `/ai/api/v1.0/`、不含 `/{id}` 路由、不含真实 Token/Provider Secret；base 变量只保存 origin。 |
| 文档/Postman 一致性 | PASS | 文档与 Collection 对三个 OpenAPI 应用均无 missing/extra；5 个分割请求默认跳过。 |
| Markdown/JSON/whitespace | PASS | Markdown 围栏 `212` 个；`python -m json.tool`、JSON schema diff 和 `git diff --check` 均通过。 |
| 真实 2–5 图 Runtime E2E | NOT RUN / UNKNOWN | 未启动或验证 Runtime、OSS、MySQL/Redis、RabbitMQ、Relay、Worker 或真实 Provider，也未运行 Collection Runner/Newman；不得宣称工程全链 PASS。 |
