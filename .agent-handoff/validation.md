# 验证历史

## 2026-08-30 — X-Ray 2–5 图 Runtime 最终真实资格化

| Check | Result | Evidence |
|---|---|---|
| Pre-change backend baseline | PASS | `192 passed, 38 warnings` |
| Final backend full suite | PASS | `234 passed, 41 warnings` |
| Ruff | PASS | `python3.12 -m ruff check apps/backend scripts/dev/run_e2e_local.py` |
| Compileall | PASS | `PYTHONPATH=. python3.12 -m compileall -q apps/backend scripts/dev` |
| E2E CLI help/invalid args | PASS | `--case-manifest/--evidence-dir/--verify-runtime-receipt` 可见；缺 qualification Config 参数、非法 Prompt SHA、`repeat=0` 均在业务请求前以 exit 2 失败 |
| Manifest readback | PASS | 8/8 文件存在，SHA256/bytes/format/content-type/projection 与 JSON 一致 |
| Launcher syntax/Compose | PASS | `bash -n`；default、broker、scheduler、broker+scheduler 四种 `docker compose config --quiet` 均通过 |
| Unique local topology | PASS | API=1、Relay=1、Worker parent=1、child=1、Beat=0、broker consumer=1 |
| Runtime readiness | PASS | database/Redis/imaging broker/worker ready，HTTP 200 |
| AI Control health/readiness | PASS | database、临时进程内 control-plane JWT、Nacos 均 ready；Secret/Token 未写盘或打印 |
| Cat global Primary Config | PASS | 不可变 `xray_diagnose_cat@3.0.1` active，profile primary v2，global/global，budget=5；旧 3.0.0 retired |
| Dog global Primary Config | PASS | 不可变 `xray_diagnose_dog@3.0.1` active，profile primary v2，global/global，budget=5；旧 3.0.0 retired |
| Frozen Config identity | PASS | 猫 Config SHA `f505355a...56f92`、Prompt SHA `fdfe1d48...53017`；狗 Config SHA `1eec6839...a4c92`、Prompt SHA `33bee408...2405`；8 格前后无漂移 |
| Connection capability | PASS | validated，max_input_images=20，满足 Config budget=5；Prompt/ModelPool/Schema/Pipeline/Connection 与各自 3.0.0 对账一致 |
| Cat 2/3/4/5 real Provider matrix | PASS | 4/4 Task completed、Report final、C2 v2、receipt v2，receipt image count 分别为 2/3/4/5 |
| Dog 2/3/4/5 real Provider matrix | PASS | 4/4 Task completed、Report final、C2 v2、receipt v2，receipt image count 分别为 2/3/4/5 |
| Evidence redaction | PASS | 8 份 JSON 只保存 opaque ID、数量与 SHA；敏感 key/value 扫描未发现 Token、Signed URL、绝对影像路径、Prompt/Provider/Report 正文 |
| Post-matrix topology | PASS | active Config identity 无漂移；Runtime ready、consumer=1、queue=0、dead-letter=0 |
| Runtime/AI Control cleanup | PASS | 8002/8010 未监听，ms-image API/Relay/Worker/Beat=0，owner lock absent；imaging queue consumer/messages/unacked=0 |
| Harness teardown | PASS WITH WARNING | 8 次均 exit 0 且 evidence PASS；每次结束出现 aiomysql connection `Event loop is closed` 析构告警，未影响业务或证据 |

## 记录规则

- 主文件只保留当前资格状态和下一阶段仍有决策价值的证据。
- 2026-08-28 D2 收口前的完整验证历史已原样归档至 `archive/validation-pre-d2-closeout-20260828.md`；更早历史见 `archive.md` 索引。
- 工程通过、Provider 医学输出和医学准确率分开报告；文件名、目录名、单病例模型结果不得当作 Gold。

## 2026-08-28 — 当前工程资格摘要

| 能力 | 结果 | 证据与边界 |
|---|---|---|
| 最小上传到首份 Report 主链 | PASS | public API 已完成 Session → Study → Series → OSS upload → Image ready → Study finalize → Task/Outbox/Broker/Worker/Provider → Task completed → Report final → current/history。 |
| C1.1 医学状态边界 | PASS / ENGINEERING | Stage v1 `produced/not_produced` 保持冻结；Task/Report 只持久化批准医学状态。存量 `produced` 未经授权不回填。 |
| D1 projection 四层链 | PASS / ENGINEERING | Image → series manifest v2 → Task Snapshot v3 → Prompt/receipt/SourceRef 技术事实一致；不从文件名/像素推断 projection。 |
| D2 clinical context v1 | PASS / SYNTHETIC ONLY | Schema、allowlist、canonical SHA、Snapshot v3 与 Prompt 消费已通过三轮 synthetic E2E；真实上游 `ms-ai-fast` 尚未接线。 |
| C2 CompleteMedicalResult v2 | PASS / ENGINEERING | 独立 v2 Schema/Profile/Handler/Config、receipt 技术引用校验与 final Report 已真实运行；v1 保持冻结。 |
| 医学准确率与发布 | NOT QUALIFIED | 无可信 Gold、Scorer、分母、M1/Holdout；保持 `MEDICAL_ACCURACY_UNKNOWN / MEDICAL_RELEASE_NO_GO`。 |
| Report publish/void/revision | BLOCKED | `report_record` 缺少 `state_version`，第一份 final/current/history 不受阻断；CAS 治理需字段与迁移授权。 |
| Evaluation | BLOCKED | 隔离 `ms_image_eval` 不可用，独立迁移/readiness/Gold/Scorer 未完成。 |

## 2026-08-28 — 单 owner launcher 动态验收

| 检查 | 结果 | 说明 |
|---|---|---|
| 旧进程收敛 | PASS | 清理旧代码 Worker 与 orphan API/Relay/Worker 前先确认 Celery active/reserved/scheduled 全空；未停止其他项目 Celery 或 deepseek-harness。 |
| 唯一拓扑 | PASS | 1 launcher + 1 API + 1 Relay + 1 Worker parent + 1 fork child；Beat=0；Runtime readiness `ready=true/worker_ready=true`，broker `consumer_count=1`。 |
| 重复启动保护 | PASS | 第二个 `scripts/dev/run_local_chain.sh` 实测返回 owner PID 冲突并退出，不停止现有进程。 |
| 正常退出 | PASS | 在队列无任务时 SIGTERM launcher，launcher-owned API/Relay/Worker parent/child 全部退出，8010 和 `/tmp/ms-image-local-chain-8010.lock` 均释放。 |
| 静态合同 | PASS | `bash -n scripts/dev/run_local_chain.sh`、`git diff --check` 通过；`${PYTHONPATH:-}`、stale-lock、heartbeat、consumer=1 门禁均在当前脚本。 |

## 2026-08-28 — 参数化 E2E 与三轮证据

| 检查 | 结果 | 说明 |
|---|---|---|
| CLI 参数 | PASS | `--api-base/--image/--species/--projection/--body-part/--clinical-context-mode/--context-recorded-at/--repeat` 已实现；默认不传 body part。 |
| 请求前非法输入 | PASS | 不存在图片、非法 species、空 projection、repeat=0、无时区 context 时间、none+时间冲突均以 argparse 失败，未发业务请求。 |
| 日志脱敏 | PASS | 不输出 Token、Signed URL/headers、Provider 原文、clinical context/Report 正文；失败只输出 method/path/status 或稳定 error。 |
| 固定输入 | PASS / NON-GOLD | JPEG SHA `6758a3441044cf617aaccf247580c46e2bc6ab67af935d4e127c64b2247c9ec9`，species=cat、projection=UNKNOWN、body part 不传；文件名 `NOR` 未参与医学断言。 |
| 连续 3× public E2E | PASS / `D2_SYNTHETIC_E2E_QUALIFIED` | Task `d5f9af4333964374a33c7787f4bf0315`、`09209da4edc146a88dd4e7b9bb9f738f`、`078ffda1472747d184015b36c5ee0692` 均 completed；Report `949e3dbe450a4ea78855c747f4aba611`、`000cafbf99394f0a90e505b16a8c2374`、`86533fc7f08a46ee80a0efb9ac69c2fb` 均 final。三轮 context SHA 同为 `d746b498...c1a5`，Config/Prompt fingerprint 一致，Snapshot v3、D1、C2 v2、current/history 断言全部通过。 |
| fail-closed 观察 | PASS WITH RISK | 另一批次第 2 轮真实失败 `provider_result_source_fact_mismatch`，E2E 立即停止且未计入三连；随后从新批次连续三轮成功。需量化 Provider v2 技术引用稳定率，不得静默重试或由 Python 补写 source refs。 |

## 2026-08-28 — 自动化与静态回归

| 检查 | 结果 | 说明 |
|---|---|---|
| D1/D2/C2 定向合同 | PASS | `PYTHONPATH=. python3.12 -m pytest -q apps/backend/tests/test_ai_gateway_attempt_contracts.py apps/backend/tests/test_ai_prompt_control_plane_contracts.py`：`172 passed, 38 warnings`。 |
| Backend 全量 | PASS | `PYTHONPATH=. python3.12 -m pytest -q apps/backend/tests`：`178 passed, 38 warnings`，不低于既有基线。 |
| Ruff | PASS | `python3.12 -m ruff check apps/backend scripts/dev/run_e2e_local.py scripts/dev/issue_dev_token.py`：All checks passed。 |
| compileall | PASS | `python3.12 -m compileall -q apps/backend scripts/dev/run_e2e_local.py scripts/dev/issue_dev_token.py` 退出 0。 |
| Shell/diff | PASS | `bash -n scripts/dev/run_local_chain.sh` 与 `git diff --check` 通过。 |
| Git 发布工件 | NOT FROZEN | 当前约 130 条状态跨多个能力切片；未提交 Git，不能把工作树测试结果冒充已冻结 commit/image。 |

## Current Qualification

```text
DETERMINISTIC_LOCAL_ENGINEERING_REPLAY_QUALIFIED
D2_SYNTHETIC_E2E_QUALIFIED

D2_REAL_UPSTREAM_CONTEXT_NOT_QUALIFIED
MEDICAL_ACCURACY_UNKNOWN
MEDICAL_RELEASE_NO_GO
```

## 2026-08-29 — SourceRef 精确归因与狗稳定性复验

| 检查 | 结果 | 说明 |
|---|---|---|
| 三类字段错误合同 | PASS | series ID、projection、manifest SHA 分别产生独立脱敏错误码；定向 `9 passed`，Gateway failure receipt 行为不变。 |
| 旧失败事后归因 | UNKNOWN / UNRECOVERABLE | 旧 Task 只保存联合错误码与发送 receipt，不保存不合格 Provider 结构；不能诚实判定具体字段。 |
| 狗单次诊断 E2E | PASS | Task `e02a7d3f1bb54ddb96b4e1b26c072859` completed，Report `2f65001c7fd849f98809837d6d0ba3a8` final。 |
| 狗有界 3× E2E | PASS | Task `9048d346...`、`a88b3ba7...`、`e681160e...` 均 completed；对应 Report 均 final；context/config fingerprint、狗 Config/Prompt SHA、Snapshot v3、C2 v2/current/history 通过。 |
| Prompt 版本裁决 | KEEP 3.0.0 | 连续 4 次未复现任一字段漂移，无单变量修订证据；未创建、发布、导入或激活 `3.0.1`。 |
| Backend full pytest | PASS | `185 passed, 38 warnings`。 |
| Static/process cleanup | PASS | Ruff、compileall、`git diff --check` 通过；8010/8002、Relay/Worker、Beat 与 launcher lock 均已清理。 |

```text
CAT_DOG_PRIMARY_PROMPT_ROUTING_QUALIFIED
CAT_PRIMARY_PROMPT_RUNTIME_QUALIFIED
DOG_PRIMARY_PROMPT_RUNTIME_QUALIFIED
PROVIDER_SOURCE_REF_STABILITY_SLO_NOT_ESTABLISHED
MEDICAL_ACCURACY_UNKNOWN
MEDICAL_RELEASE_NO_GO
```

## 2026-08-29 — 猫狗独立 Primary Prompt 初次验证（历史中间状态）

| 检查 | 结果 | 说明 |
|---|---|---|
| Nacos exact version readback | PASS | `primary.cat@3.0.0` 与 `primary.dog@3.0.0` 均 online；按导入规范计算的 SHA 与本地资产一致，无 fallback。 |
| 本地 Markdown Prompt | PASS | 猫狗资产均为 `.md`；规范化 SHA 分别为 `fdfe1d48...3017`、`33bee408...2405`，变量仅含 `OUTPUT_SCHEMA_JSON/SAFE_STUDY_CONTEXT_JSON`。 |
| AI Control health/readiness | PASS | 临时 AI Control 的 database、control-plane JWT、Nacos 均 ready；进程完成控制面操作后已停止。 |
| Prompt/Config lifecycle | PASS | 猫狗 Prompt validated；`xray_diagnose_cat@3.0.0`、`xray_diagnose_dog@3.0.0` active，Prompt/ModelPool/Profile 绑定正确，slot/Config SHA/release fingerprint 不同。 |
| Backend full pytest | PASS | `python3.12 -m pytest -q apps/backend/tests`：`183 passed, 38 warnings`。 |
| Prompt/Task core pytest | PASS | 两个核心测试文件：`177 passed, 38 warnings`。 |
| Static checks | PASS | Ruff、compileall、`bash -n scripts/dev/run_local_chain.sh`、E2E help/非法参数、`git diff --check` 全部通过。 |
| Cat public E2E | PASS | Task `cf0bef2bcb5b46749d9fad3df361b739` completed；Report `63825fb730ea4ea9941c1f92a7df3bf8` final；Snapshot v3/C2 v2/config key/Prompt SHA/current/history 断言通过。 |
| Dog public E2E | HISTORICAL FAIL-CLOSED | Task `f218a6c77ec44a63a38b7203134ddbc6` 冻结狗 Config/Prompt，Provider HTTP 200；旧联合错误导致 failed/not_produced。该中间状态已由上方“SourceRef 精确归因与狗稳定性复验”更新。 |
| Runtime cleanup | PASS | 唯一 launcher 正常停止；Runtime/Relay/Worker/Beat/AI Control 当前均未保留本轮进程。 |

## 2026-08-29 — 猫狗全链 Prompt 工程资格化

| 检查 | 结果 | 说明 |
|---|---|---|
| 本地 Prompt 资产 | PASS | 猫狗各有一份版本化 `4.0.0.md`；required 为 `SAFE_STUDY_CONTEXT_JSON/OUTPUT_SCHEMA_JSON`，optional 为 `PRIMARY_RESULT_JSON`；无 Primary 结果走 Primary，有冻结 Primary 结果走 Targeted。 |
| Nacos 发布/回读 | PASS | 猫 `4.0.0` SHA `7ca40d76...6b74`，狗 `4.0.0` SHA `460611ef...903d`；均通过 draft/submit/publish 和 exact-version readback，与本地规范化 SHA 一致，未覆盖 `3.0.0`。 |
| AI Control Prompt/Config | PASS | 猫 Config `a290e1c556854f8cade4e5ff13fd7160`，狗 Config `2f3a6f4fb99e4d098577d21a23f428b4`；均为 `xray_targeted_review_v2` / experiment / `full-chain-local-v1` / max 2 calls 且 active。 |
| 犬完整 Targeted E2E | PASS | Task `c2d1bf593ea340b8a91398b6c186089d`，Report `615c02a5fbe844ae9f9641697b8ef487`；5 Stage completed、2 Call succeeded/accepted、selected owner targeted、Report final、C2 v2、receipt v2。 |
| 猫完整 Targeted E2E | PASS | Task `67765479be9d4f46b304934cfc38fe94`，Report `755241f0afb5441c8532b5c88a915f67`；5 Stage completed、2 Call succeeded/accepted、selected owner targeted、Report final、C2 v2、receipt v2。 |
| 无 Targeted 候选收敛 | PASS | 猫 Task `809ba6b383c6405196026b6c3f9109a2` 没有合法候选，走 `primary_final`、1 Call，未为资格化强制插入 Targeted。 |
| 定向合同测试 | PASS | `186 passed, 38 warnings`；覆盖 dual-mode Prompt 变量/渲染、Targeted Config、experiment 选择、FamilyRouting v2、动态 Stage 与结果引用合同。 |
| Backend 全量 | PASS | `192 passed, 38 warnings`。 |
| 静态检查 | PASS | Ruff、compileall、`bash -n scripts/dev/run_local_chain.sh`、`git diff --check` 通过。 |
| 运行态清理 | PASS | Runtime、AI Control、Relay、Worker、Beat、8010/8002 端口和 launcher lock 均已清理。 |
| 医学资格 | NOT QUALIFIED | 没有可信 Gold、医学 Scorer、分母、Failure Bank/Holdout；保持 `MEDICAL_ACCURACY_UNKNOWN / M1_BASELINE_NOT_QUALIFIED / MEDICAL_RELEASE_NO_GO`。 |

```text
CAT_DOG_FULL_CHAIN_PROMPT_ROUTING_QUALIFIED
CAT_TARGETED_PROMPT_RUNTIME_QUALIFIED
DOG_TARGETED_PROMPT_RUNTIME_QUALIFIED
MEDICAL_ACCURACY_UNKNOWN
M1_BASELINE_NOT_QUALIFIED
MEDICAL_RELEASE_NO_GO
```

## 2026-08-29 — Nacos `4.0.0` 实时同步复核

| 检查 | 结果 | 说明 |
|---|---|---|
| Prompt namespace/config | PASS | 当前进程配置的 Prompt Nacos 地址与 namespace 均已加载；未输出用户名、密码或 Token。 |
| 猫 exact-version readback | PASS / NO-OP | `ms-image.x-ray.primary.cat.zh-CN@4.0.0` 存在；远端/本地规范化 SHA 均为 `7ca40d767157fe9c333cfbe22c5e7f91a8b4d9a93f2289bb03a5bacd22d46b74`。 |
| 狗 exact-version readback | PASS / NO-OP | `ms-image.x-ray.primary.dog.zh-CN@4.0.0` 存在；远端/本地规范化 SHA 均为 `460611ef7cfc9ac95e01a7cc6aaf7abc9bb38ec5568fc7489914b9ddf71d903d`。 |
| 发布动作 | SKIPPED AS IDEMPOTENT | 精确版本已存在且正文一致，因此没有重复 publish、force-publish 或覆盖已发布版本。 |

## 2026-08-29 — 全 Stage Prompt 覆盖与当前全链复验

| 检查 | 结果 | 说明 |
|---|---|---|
| Stage/Prompt 覆盖审计 | PASS | Registry 中只有 `joint_primary_reader/v1|v2` 与 `targeted_review/v1|v2` 为 `provider_required=true`，两者均有 AI request command 与冻结 Prompt 渲染路径；`study_preparation`、`family_routing`、`decision_finalization` 为确定性 Stage，不需要 Prompt。 |
| 猫 Primary-only 分支 | PASS | Task `527a23fc03244cdc82832d50bc4e9149` / Report `ce28696eccac42889d223a94f5c15a1c`；4 Stage、1 AI Call、final C2 v2 Report。 |
| 狗 Primary-only 分支 | PASS | Task `4aeff184cdf246eb8252b0374756cdbb` / Report `b3fc489b25ed42ff9d72fc80a812a701`；4 Stage、1 AI Call、final C2 v2 Report。 |
| 猫完整 Targeted 分支 | PASS | Task `7569c45063dc43aba1a337d132c07db7` / Report `e245b39b697445c09e68c94bce2686d7`；5 Stage、2 AI Call 均 succeeded/accepted、两份 `ai-image-receipt.v2`、final C2 v2 Report。 |
| 狗完整 Targeted 分支 | PASS | Task `77a0e506c69045049e020b801f1c9033` / Report `1e28fb896091474db946180e169595df`；5 Stage、2 AI Call 均 succeeded/accepted、两份 `ai-image-receipt.v2`、final C2 v2 Report。 |
| Targeted 技术引用失败 | EXPECTED FAIL-CLOSED / OPEN STABILITY RISK | 狗 Task `398e76a28af24072a1d66f7c28189ed6` 已成功完成 Primary/FamilyRouting 并真实发送 Targeted；Provider 复制错 `manifest_sha256` 后以 `provider_result_source_manifest_sha256_mismatch` 失败，无 Report，Attempt/Call 仍保存脱敏 receipt v2；未静默重试、回退或由 Python 修正。 |
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

## 2026-08-30 — v3.2 全项目接口、Prompt 与 Postman 校正版静态验收

| 检查 | 结果 | 说明 |
|---|---|---|
| 项目 HTTP 路由覆盖 | PASS | 四套 FastAPI App 与 Collection 静态对账：Runtime `30/30`、Runtime Admin `7/7`、AI Control `32/32`、Evaluation Control `10/10`，合计 `79/79`；每套均包含一个非版本化 `GET /` 根探针。 |
| 版本化接口矩阵 | PASS | 路线图逐项列出 Runtime `29/29`、Runtime Admin `6/6`、AI Control `31/31`、Evaluation Control `9/9`，无 missing/extra。 |
| Postman Collection 结构 | PASS | canonical 文件为 `docs/postman/ms-image-xray-complete.postman_collection.json`，共 `7` 个 Folder、`96` 个 Request；其中 `79` 个项目路由、`5` 个 OSS signed URL PUT、`12` 个多影像槽重复请求。 |
| JSON 请求体 | PASS | 静态解析并按 OpenAPI 校验 `50/50` 个 JSON body，无失败。 |
| 必填 query 参数 | PASS | 静态校验 `22/22` 个含必填 query 的项目请求，无缺失。 |
| 鉴权边界 | PASS | 项目请求 `91/91` 的鉴权配置符合对应 App；`5/5` 个 OSS signed URL PUT 显式 `noauth`。 |
| Prompt/Provider 口径 | PASS | 所有项目 Request description 均明确用途、同步/异步医学 Prompt 与 Provider Logical Call；`POST /tasks` 的模型链发生在 HTTP 返回后的 Worker，Primary 为 `1 Prompt/1 Call`，Targeted 最多 `2 Prompt/2 Calls`，N 张图不增加 Prompt 次数。 |
| Evaluation 边界 | PASS | Evaluation Control 的 `9` 个版本化接口进入全项目总账；当前 Worker 使用 `FakeEvaluationScorer`，为 `0 Prompt/0 Provider Call`，默认由 `enable_evaluation_requests=false` 跳过。 |
| Markdown/JSON/whitespace | PASS | 路线图 `212` 个 Markdown 围栏且为偶数；Postman JSON 可解析；目标文件 `git diff --check` 通过。 |
| Secret 扫描 | PASS | 未发现真实 JWT、Private Key、AKIA、`sk-*`、密码、`secret_key` 或 `api_key`；未输出 Prompt、病例或报告正文。 |
| 静态合同资格 | `STATIC_CONTRACT_QUALIFIED` | 只证明文档、OpenAPI 与 Postman Collection 静态一致。 |
| 真实 Runtime/Provider E2E | `RUNTIME_E2E_NOT_RUN` | 本轮未启动 Runtime、Relay、Worker、OSS、Broker 或真实 Provider，也未运行 Collection Runner/Newman。 |
| 医学准确率 | `MEDICAL_ACCURACY_UNKNOWN` | 没有正式 Gold、医学 Scorer 或 M1 结果，不得宣称医学准确率或发布资格。 |

## 2026-08-30 — v3.3 最终执行路线与 Prompt 事实校正版

| 检查 | 结果 | 说明 |
|---|---|---|
| 文档规模与结构 | PASS | 路线图 3660 行、151896 bytes、228 个代码围栏且为偶数；SHA256 `71a1c98a3f1a542ffb3f25685d40d845b5a0248ce0bd097f215f87fa7e531556`。 |
| v2 Prompt 来源 | PASS | 源码点验 `AIRequestService._render_v2_messages` 直接渲染 immutable Config `prompt_content`；Catalog 只在 v1 provider-disabled 兼容路径使用。 |
| Task Snapshot 边界 | PASS | 源码点验 Snapshot 保存 Config identity 与 prompt/model/schema/pipeline SHA；完整 Prompt content/variables/message contract 在 `AIConfigRecord`。 |
| Stage Prompt 数 | PASS | StudyPreparation/FamilyRouting/DecisionFinalization 为 0；JointPrimaryReader 为 1；TargetedReview 仅合法 candidate 时新增 1。 |
| 多图当前缺口 | PASS（事实核验） | Study/Series 只有 `ge=0`、prepare-upload 无第 6 图预拒绝、E2E CLI 仍单图；因此 E1/E3 仍是实际缺口。 |
| OpenAPI 路由 | PASS | Runtime `30/30`、Runtime Admin `7/7`、AI Control `32/32`、Evaluation Control `10/10`，合计 79。 |
| Postman | PASS | JSON 可解析；7 Folder、96 Request；本轮未修改 Collection。 |
| Whitespace | PASS | 路线图、Postman 与相关 handoff 文件 `git diff --check` 通过。 |
| 真实 Runtime/Provider E2E | `NOT RUN` | 本轮为文档与源码静态核验，未启动 API/Relay/Worker/OSS/Broker/Provider。 |
| 医学准确率 | `UNKNOWN` | 未运行 Evaluation/M1/Holdout；不得声称 Prompt 效果提升。 |

## 2026-08-30 — 提交前代码、资产与 Compose 验证

| 检查 | 结果 | 说明 |
|---|---|---|
| Backend full tests | PASS | `PYTHONPATH=. pytest -q apps/backend/tests`：`192 passed, 38 warnings`。 |
| Ruff | PASS | `ruff check apps/backend`。 |
| Compile | PASS | `python -m compileall -q apps/backend`。 |
| Local launcher | PASS | `bash -n scripts/dev/run_local_chain.sh`。 |
| E2E CLI | PASS | `python scripts/dev/run_e2e_local.py --help`。 |
| Reconcile CLI | PASS | `PYTHONPATH=. python -m apps.backend.workers.imaging_worker.reconcile --help`；P1-B 参数调用已补齐。 |
| Compose | PASS | default、`broker`、`scheduler`、`broker+scheduler` 四种 `docker compose ... config --quiet` 均通过。 |
| Postman JSON | PASS | canonical Collection 通过 `python -m json.tool`。 |
| Whitespace | PASS | `git diff --check` 与两组 cached diff check 通过。 |
| Secret/path boundary | PASS | cached diff 未发现 Private Key、常见 Token、AWS signed signature；`.env`、`scripts/dev/keys/`、旧根目录 Postman 和 handoff archive 均未暂存。 |
| Git push | PASS | `c8478e0`、`21f103f`、`52edcde` 已推送到 `origin/codex/prompt-runtime-ai-gateway`。 |
| Runtime E2E | NOT RUN | 本轮目标是检查、提交和推送；没有启动业务进程或重新运行真实 Provider 全链。 |

## 2026-08-30 — 2–5 图资格化分支与计划核验

| 检查 | 结果 | 说明 |
|---|---|---|
| Branch base | PASS | `codex/xray-2to5-runtime-qualification` 从 `d4a216a` 创建。 |
| Roadmap reading | PASS | 完整阅读 3660 行 v3.3 路线图；下一阶段与 E0–E8 顺序一致。 |
| Source anchors | PASS | 点验 Study/Series 数量 schema、Study/Image Service、AIRequest/Config 门禁和单图 E2E 写死位置。 |
| Tests | NOT RUN | 本轮只创建分支和整理计划，没有业务代码变化。 |
| Runtime E2E | NOT RUN | 未启动 Runtime、Relay、Worker、OSS、RabbitMQ 或真实 Provider。 |
