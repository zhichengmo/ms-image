# Validation Archive — 2026-09-03 full-chain closeout

以下完整历史章节从 `.agent-handoff/validation.md` 移入归档，以保持活动验证总账在容量限制内。

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
