# Validation Archive — 2026-09-02 TargetedReview closeout

The following complete historical sections were moved from `validation.md` to keep the active validation ledger within its capacity limit.

## 2026-08-29 — SourceRef 精确归因与狗稳定性复验

| 检查 | 结果 | 说明 |
|---|---|---|
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
