# 代理交接当前快照

## 当前目标与状态

- 最后更新：2026-08-26
- 工作区：`/Users/mozhicheng/workspace/code/cy-code/ms-image`
- 当前分支：`codex/prompt-runtime-ai-gateway`
- 当前目标：XRay 运行链使用唯一 `xray_primary/common` Prompt；`species=cat|dog` 是创建 Task 前由上游病例/宠物档案边界确定并由 Task 请求显式传入的冻结事实。当前 `ms-image` 不保存或运行时查询 `pet_profile` / `medical_record`。
- 当前状态：`CODE_IMPLEMENTED / FULL_WORKER_RUNTIME_NOT_QUALIFIED / MEDICAL_ACCURACY_UNKNOWN / MEDICAL_RELEASE_NO_GO`。

## 本轮已实现

- `TaskCreate` 新增 `species` 参数；`diagnose` 必传，只允许 `cat` / `dog`，支持首尾空格和大小写归一化；`replay` 为兼容旧链可不传。
- `TaskService` 在创建任务时把归一化后的 `species` 写入 `request_snapshot_json`；该字段参与 `request_sha256`，因此相同幂等请求若改变物种会失败关闭，而不会静默漂移。
- 现有 XRay Prompt Source 改为单一内部 key `xray_primary`，外部 Nacos 坐标为 `ms-image.x-ray.primary.common.zh-CN@<immutable version>`；XRay `common` exact-only，`cat`、`dog`、`default` 均不能 fallback 到 `common`。
- 现有 `prompt_commands.py` 已把 Snapshot 的 `species` 放入 Primary/Targeted `safe_context`，运行时通过 `SAFE_STUDY_CONTEXT_JSON` 交给同一份冻结 Prompt；Worker 不读取宠物档案，也不猜测物种。
- 未新增表、字段、迁移脚本、Service、Repository、宠物档案或独立测试脚本。

## 本轮验证

- `python -m ruff check`：5 个修改文件通过。
- 三个既有 AI 合同测试文件：`94 passed, 19 warnings`；warning 为已有 Pydantic 与 `datetime.utcnow()` deprecation。
- 修改生产文件 `compileall` 通过；`git diff --check` 通过。
- 2026-08-26 再次针对“评估猫狗统一继承方案”复核并重跑三份既有 AI 合同测试：`94 passed, 19 warnings`；无新增生产代码。
- 未运行 Nacos 发布/导入、MySQL 控制面写入、真实 Task、Broker、Worker、OSS、Provider 或医学验证。

## 外部状态与阻断

- 历史 `ms-image.x-ray.primary.cat.zh-CN@1.0.0`、`dog@1.0.0` 和旧 `default@1.0.0` 仍是不可变历史发布物；新链不导入、不激活、不冻结它们，未经授权不删除。
- canonical `ms-image.x-ray.primary.common.zh-CN` 尚未发布，数据库中也尚未导入/激活对应 Prompt、Connection、ModelPool 和 `xray_diagnose` Config。
- 主库已有当前 20 张 Model 表和 `alembic_version=20260824_02`，但业务表当前为空；完整任务链仍未资格化。
- 实际 Worker 仍需安全注入 `AI_PLATFORM_OPENAI_BASE_URL` 与 `AI_PLATFORM_API_KEY`；上游按 `session_id -> medical_record -> pet_profile` 解析物种后调用 Task 接口的真实集成也尚未运行。

## 下一动作

1. 发布一个不可变版本的 `ms-image.x-ray.primary.common.zh-CN` 完整 XRay Prompt，并回读校验正文、变量合同和 SHA。
2. 使用既有控制面导入 `xray_primary/common`，建立 Connection/ModelPool，编译并激活唯一 `xray_diagnose` `global/global` Config。
3. 在上游通过 `session_id -> medical_record -> pet_profile` 确定 `species=cat|dog` 后，创建 Session/Study/Series/Image 并调用 `POST /tasks`；核验冻结 Snapshot/Outbox。
4. 注入真实 Worker Platform 配置后跑通 MySQL -> Outbox -> Broker -> Worker -> OSS -> Platform -> Attempt -> Stage -> Report；通过前不得宣称完整 Runtime 或医学上线合格。
