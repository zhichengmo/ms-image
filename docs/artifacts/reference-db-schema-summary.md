# vet-platform AI（人工智能）数据库只读结构摘要

> 中文阅读说明：`schema` 是“数据库结构”，`read-only` 是“只读”；其余英文术语请参阅[英文术语中英对照](../术语中英对照.md)。

捕获时间：2026-08-10 13:12（Asia/Shanghai）
数据库：`vet_platform`（本机 MySQL 9.3 socket，只读查询）

本文件只记录字段名、索引/唯一约束和脱敏结构，不记录 API key、Prompt 内容、请求参数、响应正文或完整 URL。完整数量/状态/敏感字段聚合见 `reference-db-readonly-live.json`。

## 表与字段

| 表 | 关键字段（按实际 schema） | 事实边界 |
|---|---|---|
| `ai_provider` | `id, provider_key, provider_name, provider_type, base_url, api_key, default_model, models_json, enabled, sort_no, description, created_at, updated_at, is_del` | Provider（AI 服务提供方） 元数据与敏感 key 同表；`api_key` 禁止迁移 |
| `ai_api_connection` | `id, created_at, updated_at, base_url, api_key, model_name, connection_name, human_weight, is_del` | 旧连接事实；key 明文存储是 legacy 风险 |
| `ai_connection_profile` | `id, connection_id, model_key, route_name, route_type, api_format, is_active, created_at, updated_at` | 连接治理投影；不重复存 base_url/key/model |
| `ai_model_pool` | `id, created_at, model_pool, note` | 旧池；`model_pool` 是 `-` 分隔 connection id 字符串 |
| `ai_governance_model_pool` | `id, pool_key, name, model_key, legacy_pool_id, is_active, created_at, updated_at` | 治理池主档，保留 legacy 回溯标识 |
| `ai_model_pool_lane` | `id, pool_id, lane_no, connection_id, is_active, created_at, updated_at` | 有序 lane；串行/竞速都按 lane 解释 |
| `ai_prompt` | `id, prompt_key, name, module_key, legacy_template_id, is_active, created_at, updated_at` | Prompt（提示词） 主档，不保存正文 |
| `ai_prompt_revision` | `id, prompt_id, version, content, content_en, checksum, status, variables, created_at, updated_at` | Prompt（提示词） 版本事实；正文/变量属于敏感业务资产，不迁移到日志 |
| `ai_prompt_template` | `id, created_at, updated_at, template_name, content, content_en, human_weight, is_del, module_category, is_confirmed` | legacy 模板，无 published/checksum 合同 |
| `ai_output_schema` | `id, schema_key, version, schema_json, is_active, created_at, updated_at` | 输出合同；当前无记录 |
| `ai_stage` | `id, stage_key, module_key, pipeline_key, phase_key, task_key, target_key, species, name, source_version, is_active, created_at, updated_at` | Stage（阶段） 目录 |
| `ai_stage_plan` | `id, stage_id, version, status, created_at, updated_at` | Plan 发布状态 |
| `ai_stage_round` | `id, plan_id, round_no, name, prompt_revision_id, output_schema_id, pool_id, mode, race_count, timeout_ms, max_tokens, temperature, fallback_on, is_active, created_at, updated_at` | Round 将 Prompt（提示词）/schema/pool/timeout/fallback 组合在一起 |
| `ai_execution_trace` | `id, request_id, session_id, stage_id, plan_id, status, final_round_no, started_at, finished_at` | 执行事实；当前无记录 |
| `ai_execution_attempt` | `id, trace_id, round_no, lane_no, connection_id, status, is_winner, duration_ms, error_type, error_message, created_at` | 每条 lane 尝试；当前无记录 |
| `ai_request_log` | `id, request_id, api_base_url, model_name, api_connection_id, connection_family, session_id, diagnosis_stage, request_start_time, request_end_time, total_duration_ms, response_status, error_message, input_tokens, output_tokens, total_tokens, business_type, created_at, request_params, original_prompt, rendered_prompt, response_text` | 167388 行历史请求；包含 raw Prompt（提示词）/response，禁止直接迁移 |
| `api_request_stats` | `id, created_at, updated_at, request_type, api_base_url, model_name, total_requests, success_count, failure_count, total_response_time, avg_response_time, success_rate, total_tokens_used, quality_score, performance_score, stats_date, stats_hour` | 聚合统计表；当前无记录 |

## 索引与唯一约束

来自 `information_schema.STATISTICS` 和 `TABLE_CONSTRAINTS` 的脱敏摘要：

- 唯一约束：`ai_provider.uk_ai_provider_key`、`ai_connection_profile.uq_ai_connection_profile_connection_id`、`ai_governance_model_pool.uq_ai_governance_model_pool_key`、`ai_model_pool_lane.uq_ai_model_pool_lane_pool_lane`、`ai_prompt.uq_ai_prompt_prompt_key`、`ai_prompt_revision.uq_ai_prompt_revision_prompt_version`、`ai_stage.uq_ai_stage_stage_key`、`ai_stage_round.uq_ai_stage_round_plan_round`、`ai_execution_trace.uq_ai_execution_trace_request_id`、`ai_request_log.request_id`、`api_request_stats.uk_request_api_date_hour`。
- 主要查询索引：连接 `is_del/model_name`；连接 Profile `model_key/route_type`；Pool lane `connection_id`、`pool_id/lane_no`；Prompt `legacy_template_id/status/template_name`；Stage `module_key/pipeline_key/phase_key/source_version`；Trace `session_id/stage_id`；Request Log `connection_family/diagnosis_stage/model_name/response_status/request_start_time/session_id`；Stats `request_type/api_base_url/stats_date/created_at`。
- AI 相关表实际 Foreign Key 数量：`0`。源码 ORM 中存在部分 ForeignKey 声明，但当前数据库物理约束未建立；ms-image 新表继续遵守“不使用 ForeignKey”规则。

## 迁移判断

允许迁移：provider/connection/model/pool/prompt/stage/plan/round 的非敏感元数据、状态、checksum、统计摘要。
禁止迁移：`ai_provider.api_key`、`ai_api_connection.api_key`、`ai_request_log.request_params`、`original_prompt`、`rendered_prompt`、`response_text` 以及任何 Authorization/原始影像内容。
