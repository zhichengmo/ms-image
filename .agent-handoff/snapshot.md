# Handoff Snapshot

## Current State

- Last updated: 2026-08-30（猫狗 2–5 图 Runtime 代码、Config 预算和真实 8 病例工程资格化全部完成）
- Workspace root: `/Users/mozhicheng/workspace/code/cy-code/ms-image`
- Branch: `codex/xray-2to5-runtime-qualification`
- Base/HEAD before this slice: `d4a216a899f2f8937e5a7039e9c4cee9b30fc45b`
- Objective: 已在不新增 REST、表字段、迁移、医学 Prompt、Evaluation、Report CAS 或分割能力的前提下，把新 X-Ray diagnose Runtime 收紧为 2–5 张诊断原图，并以猫/狗各 2/3/4/5 图完成真实工程资格化。
- Current status: `xray_diagnose_cat@3.0.1` 与 `xray_diagnose_dog@3.0.1` 已按 compile-preview → create → validate → activate 生命周期发布，唯一变化为 Config version 和 `max_input_images=5`；8 个 engineering candidate 病例均真实完成 Task/Report/receipt 验收。
- Current local processes: 本轮 Runtime launcher 与独立 AI Control 已正常停止；8002/8010 未监听，ms-image API/Relay/Worker/Beat 均为 0，owner lock 不存在，imaging queue consumer/messages/unacked 均为 0。

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

- AI Control health/readiness：database、control-plane JWT、Nacos 全部 ready；临时 HS256 Secret/Token 仅在进程内使用，未写盘或输出。
- 猫 global Primary：`xray_diagnose_cat@3.0.1`，active，`xray_primary_v2/global/global`，budget=5，Config SHA `f505355a645fb9cd3cee06a80f667c61062c3b20c13a4af5b23c61c822056f92`，Prompt SHA `fdfe1d48feb51aaf13314d35e86b4e8758ffeb77a524f9a6ebee366034453017`。
- 狗 global Primary：`xray_diagnose_dog@3.0.1`，active，`xray_primary_v2/global/global`，budget=5，Config SHA `1eec6839cd58aff7c746f93aff4085d5289e842c4a42484f8a21b56d42ca4c92`，Prompt SHA `33bee408116866ee44f96785da6a1d2154890c26116142dc7600915cda982405`。
- 两者复用各自 3.0.0 的 Prompt/ModelPool/Schema/Pipeline/Connection；Connection validated 且 capability max_input_images=20。旧 3.0.0 仅退役，未覆盖或删除。
- 唯一 launcher topology：API 1、Relay 1、Worker parent 1、Worker child 1、Beat 0、broker consumer 1；8 格结束后队列与 dead-letter 均为 0，Config SHA 无漂移。
- 猫/狗各 2、3、4、5 图共 8 格均为 Task completed、Report final、C2 v2、receipt v2，receipt image count 等于 N；脱敏 evidence 位于 `docs/evidence/xray-2to5-runtime/20260830T130608Z/`。

## Current Qualification

```text
XRAY_2TO5_RUNTIME_CONTRACT_STATIC_QUALIFIED
XRAY_2TO5_MANIFEST_MATRIX_8_OF_8_STATIC_QUALIFIED
XRAY_2TO5_E2E_HARNESS_STATIC_QUALIFIED
UNIQUE_LOCAL_RUNTIME_TOPOLOGY_QUALIFIED
BACKEND_TESTS_234_PASSED

XRAY_CAT_DOG_2TO5_ENGINEERING_RUNTIME_QUALIFIED
REAL_8_CASE_MATRIX_8_OF_8_PASSED
MEDICAL_ACCURACY_UNKNOWN
MEDICAL_RELEASE_NO_GO
```

该资格仅证明工程链，不证明病例分组权威性、逐图医学评估覆盖或诊断准确率。

## Immediate Next Actions

1. 下一独立阶段按 R4A–R4D 顺序建设 Evaluation DB/metadata/Alembic、Dataset 治理、Gold/Scorer 和 Runtime 等价 Runner。
2. R4A–R4D 完成后建立 M1；只有 M1/Holdout 和正式医学 scorer 就绪后才开始 Primary/Targeted 单变量 Prompt 优化。
3. Harness 每轮结束存在 aiomysql connection `Event loop is closed` 析构告警，退出码与 evidence 不受影响；后续可单独修复连接关闭，不回写本次资格结果。

## Active Files

- `docs/evidence/xray-2to5-runtime/20260830T130608Z/*.json`
- `.agent-handoff/snapshot.md`
- `.agent-handoff/validation.md`
- `.agent-handoff/work-log.md`
- `.agent-handoff/backlog.md`
- `.agent-handoff/risks.md`
- `.agent-handoff/decisions.md`

## Validation Summary

- Pre-change baseline: `192 passed, 38 warnings`。
- Final backend: `234 passed, 41 warnings`。
- Ruff、compileall、E2E `--help`/非法参数、`bash -n`、`docker compose config --quiet`、`git diff --check` 全部 PASS。
- 8 manifests 已按真实数据根回读文件、SHA256、大小、格式、content type 和 projection；8/8 真实 E2E 均通过。
- AI Control Config 生命周期、Runtime readiness、Config/Prompt SHA 冻结、receipt 图像计数与 identity、Report current/history/C2 v2 均动态合格。
- 每轮 Harness 完成后出现非阻塞 aiomysql 析构告警；无业务失败、无 evidence 漂移，已记录为后续工程清理风险。
