# Handoff Snapshot

## Current State

- Last updated: 2026-08-30（猫狗 2–5 图 Runtime 代码与静态资格化完成，真实 8 病例被 Config budget Gate 阻断）
- Workspace root: `/Users/mozhicheng/workspace/code/cy-code/ms-image`
- Branch: `codex/xray-2to5-runtime-qualification`
- Base/HEAD before this slice: `d4a216a899f2f8937e5a7039e9c4cee9b30fc45b`
- Objective: 在不新增 REST、表字段、迁移、医学 Prompt、Evaluation、Report CAS 或分割能力的前提下，把新 X-Ray diagnose Runtime 收紧为 2–5 张诊断原图，并以猫/狗各 2/3/4/5 图完成真实工程资格化。
- Current status: 代码、8 个 engineering candidate manifest、多图 Harness 和静态回归已完成；唯一运行拓扑已动态合格。猫狗 global Primary active Config 的冻结 `max_input_images=20`，不满足新合同要求的 `5`，因此真实 8 病例未启动并记录为 `BLOCKED`。
- Current local processes: 资格化 topology smoke 后已正常停止；API/Relay/Worker/Beat 均为 0，8010 未监听，`/tmp/ms-image-local-chain-8010.lock` 已释放。

## Completed In This Slice

- 新增统一合同 `apps/backend/core/imaging/xray_contract.py`：X-Ray Study 2–5、Series 1–5、诊断输入固定为 `original + instance`，上传占位状态为 `uploading|validating|ready`。
- Study/Series：StudyCreate 与 Service 复核 2–5；Series 在 Study 行锁内先识别幂等，再校验单 Series 1–5 和聚合 declared budget；finalize 重新核验诊断原图、Series manifest 与 Study 聚合。
- Image：direct/multipart prepare 均锁 Study；新 logical slot 在已有 5 个占位时以 `xray_study_image_capacity_exceeded` fail-closed；同 key uploading replay 在 admission 前返回；derived 不占诊断名额。
- Manifest/Task：新 X-Ray manifest、Snapshot 与 Task input 只使用 ready `original + instance`；Task Snapshot 前再次强制 2–5；legacy manifest builder 未修改。
- AIRequest：Logical Call 准备、network plan 和 Provider 网络调用前均检查新 v3 X-Ray Task 的 2–5 与展开数量一致；历史 v2 frozen Task 不被重新解释。
- Config Compiler：仅 X-Ray diagnose `xray_primary_v2` 新 Config 要求 `max_input_images=5`、Connection capability `>=5`；Targeted 与历史 Config 不被本阶段额外改写。
- E2E Harness：现有 `scripts/dev/run_e2e_local.py` 支持 `--case-manifest`、`--evidence-dir`、`--verify-runtime-receipt`，支持多 Series/N 图上传、Snapshot/Report/receipt 只读核验和脱敏 evidence。
- E0 manifest：`scripts/dev/manifests/xray-2to5/` 已建立 cat/dog × 2/3/4/5 共 8 个 `xray-e2e-case.v1`；路径相对 `MS_IMAGE_XRAY_DATA_ROOT`，全部 projection 为 `UNKNOWN`，不保存 Disease/annotation，不把 NOR/ABN 当 Gold。
- 自动测试只扩展既有测试文件；覆盖 Study N=0..6、Series 1+1/1+2/2+3、超预算、幂等、direct/multipart 第 6 图、derived、Task/AI gate、Provider 前门禁、历史 v2/non-XRay 兼容和 Config capability。

## Dynamic Gate Evidence

- 唯一 launcher topology：API 1、Relay 1、Worker parent 1、Worker child 1、Beat 0、broker consumer 1。
- Runtime readiness：database/Redis/imaging broker/worker 均 ready，HTTP 200；launcher 正常退出后仅清理自有进程和 lock。
- 猫 global Primary：`xray_diagnose_cat@3.0.0`，active，`xray_primary_v2`，Config SHA `392558b06ada121bdb943bf9ae053f821bf48ee8f11c432ad35dd4a8db366e94`，budget=20。
- 狗 global Primary：`xray_diagnose_dog@3.0.0`，active，`xray_primary_v2`，Config SHA `c19dea28f13b62dc0bbd23315bd9800a466aeb510b1f5a17c62db00ac167325c`，budget=20。
- 两者使用的 Connection 均为 validated、frozen SHA 对账一致、capability max_input_images=20；阻塞事实只在 Config budget 不等于 5。
- 未创建 Task、未调用 Provider、未写控制面、未修改或覆盖 3.0.0。

## Current Qualification

```text
XRAY_2TO5_RUNTIME_CONTRACT_STATIC_QUALIFIED
XRAY_2TO5_MANIFEST_MATRIX_8_OF_8_STATIC_QUALIFIED
XRAY_2TO5_E2E_HARNESS_STATIC_QUALIFIED
UNIQUE_LOCAL_RUNTIME_TOPOLOGY_QUALIFIED
BACKEND_TESTS_234_PASSED

XRAY_CAT_DOG_2TO5_ENGINEERING_RUNTIME_BLOCKED
BLOCKER=GLOBAL_PRIMARY_CONFIG_MAX_INPUT_IMAGES_20_NOT_5
REAL_8_CASE_MATRIX_NOT_RUN
MEDICAL_ACCURACY_UNKNOWN
MEDICAL_RELEASE_NO_GO
```

不得记录 `XRAY_CAT_DOG_2TO5_ENGINEERING_RUNTIME_QUALIFIED`，直到 8 格全部通过。

## Immediate Next Actions

1. 经用户确认后，通过现有 AI Control 创建不可变 `xray_diagnose_cat@3.0.1` 与 `xray_diagnose_dog@3.0.1`：复用各自 3.0.0 的 Prompt/ModelPool/Connection/Schema/Profile，只把 budget `max_input_images` 改为 5；compile/validate 后再 activate global/global。不得覆盖 3.0.0。
2. 重新只读确认猫狗 active global Primary 的 profile、budget=5、Connection capability>=5、Config SHA，并在 8 轮期间冻结这两个 SHA。
3. 用唯一 launcher 启动 `1 API + 1 Relay + 1 Worker parent/child + 0 Beat + consumer=1`。
4. 依次执行 cat 2/3/4/5、dog 2/3/4/5，命令必须带 `--expected-config-key`、`--expected-prompt-sha256`、`--verify-runtime-receipt`、`--evidence-dir`；任一格失败立即停止，不静默重试。
5. 8 格全部 PASS 后才记录 `XRAY_CAT_DOG_2TO5_ENGINEERING_RUNTIME_QUALIFIED`，然后进入 R4A–R4D/M1，而不是直接宣称医学准确。

## Active Files

- `apps/backend/core/imaging/xray_contract.py`
- `apps/backend/core/imaging/manifest.py`
- `apps/backend/crud/image.py`
- `apps/backend/crud/ai_call.py`
- `apps/backend/schemas/study.py`
- `apps/backend/services/runtime/service/study_service.py`
- `apps/backend/services/runtime/service/image_service.py`
- `apps/backend/services/runtime/service/task_service.py`
- `apps/backend/services/runtime/service/ai_request_service.py`
- `apps/backend/services/ai_control/service/config_compiler.py`
- `scripts/dev/run_e2e_local.py`
- `scripts/dev/manifests/xray-2to5/*.json`
- `apps/backend/tests/test_ai_gateway_attempt_contracts.py`
- `apps/backend/tests/test_ai_prompt_control_plane_contracts.py`

## Validation Summary

- Pre-change baseline: `192 passed, 38 warnings`。
- Final backend: `234 passed, 41 warnings`。
- Ruff、compileall、E2E `--help`/非法参数、`bash -n`、`docker compose config --quiet`、`git diff --check` 全部 PASS。
- 8 manifests 已按真实数据根回读文件、SHA256、大小、格式、content type 和 projection。
- Docker Desktop daemon 当前未运行，但本机 MySQL/RabbitMQ/Redis 与 launcher topology/readiness 均动态合格；这不是当前阻塞原因。
