# MS-Image X-Ray 前端 Postman 联调指南

> 对应集合：`docs/postman/ms-image-xray-frontend.postman_collection.json`
>
> 核对日期：2026-09-07
>
> 适用链路：2–5 张原始 X-Ray → Quality Review → Diagnose / Report → Anatomy Localization 展示

## 1. 文档边界

这份资料面向前端页面开发与真实数据联调，只覆盖 Runtime 业务接口，不包含 Runtime Admin、AI Control、Evaluation Control，也不会修改 Prompt、模型配置或数据库。

当前能力边界：

- Session、Study、Series、Image 上传与状态查询：已实现。
- Quality Review Task 与结果查询：已实现。
- Diagnose Task、Report current/history/detail：已实现。
- Anatomy Localization 的 Task、current、history、result、prepare-view、legend：已实现。
- `GET /tasks/page`：真实联调仍有 422 阻断，前端暂时不能依赖。
- `prepare-view`：接口合同测试已通过；真实 OSS `versionId` 下载还需要在有完整 Runtime/OSS 环境时验收。
- 新生成 Localization bbox 的医学准确性尚未资格化；前端可先完成展示逻辑，但不得把工程可展示等同于医学发布通过。

本集合不会打印 Basic Auth 凭证、signed URL、Provider 原文、Prompt 或完整医疗报告。

## 2. 导入与基础配置

在 Postman 中导入：

`docs/postman/ms-image-xray-frontend.postman_collection.json`

Collection 变量至少填写：

| 变量 | 必填 | 示例/说明 |
|---|---:|---|
| `runtime_base_url` | 是 | 默认 `http://127.0.0.1:8010/api/v1` |
| `runtime_username` | 是 | Runtime Basic Auth 用户名，与服务端 `BASIC_AUTH_USERNAME` 一致 |
| `runtime_password` | 是 | Runtime Basic Auth 密码，与服务端 `BASIC_AUTH_PASSWORD` 一致；不要保存到共享 Environment |
| `species` | 是 | `cat` 或 `dog` |
| `image_count` | 是 | 整数 `2..5` |
| `subject_id` | 是 | 本次病例主体标识 |
| `case_key` | 是 | 调用方病例键，仅用于生成幂等来源键 |
| `image_path_N` | 是 | 第 N 张真实影像的本地绝对路径 |
| `image_file_format_N` | 是 | 当前直传模板默认 `jpeg` |
| `image_content_type_N` | 是 | JPEG 使用 `image/jpeg` |
| `image_sha256_N` | 是 | 文件真实 SHA-256，小写 64 位十六进制 |
| `image_size_bytes_N` | 是 | 文件真实字节数 |
| `projection_N` | 是 | 调用方声明投照位；示例 `lateral`、`ventrodorsal` |

`N` 的有效范围由 `image_count` 决定。比如 `image_count=2` 时只填写 1、2 槽；3–5 槽会自动跳过。

本地读取文件事实的常用命令：

```bash
shasum -a 256 /absolute/path/to/image.jpg
wc -c /absolute/path/to/image.jpg
```

注意：

- JPEG 的 `file_format` 必须写 `jpeg`，不能写 `jpg`。
- SHA、字节数、Content-Type 任一与对象实际内容不一致，`complete-upload` 会失败关闭。
- Postman 桌面版需要允许读取图片所在目录。
- OSS PUT 请求明确配置为 `noauth`，不能携带 Runtime Authorization。
- signed URL 有短 TTL。过期后重新调用对应准备接口，不能持久化旧 URL。

## 3. 建议运行方式

首次联调建议运行整个 Collection，顺序已经按真实依赖排列：

```text
readiness
→ Session
→ Study
→ Series
→ 每张图 prepare-upload
→ OSS PUT
→ complete-upload
→ 轮询 Image ready
→ 查询并 finalize Study
→ 创建并轮询 Quality Review
→ 查询 Quality 结果
→ 创建并轮询 Diagnose
→ 查询 Report
→ 创建并轮询 Anatomy Localization
→ 查询 Localization current/history/result
→ prepare-view
→ legend
```

Collection Runner 建议：

- Delay：`1000 ms`，避免状态轮询过密。
- Iterations：`1`。
- 保存响应：关闭，尤其不要持久化 signed URL 与完整医疗结果。
- `image_poll_max` 默认 60 次。
- `task_poll_max` 默认 180 次。
- 状态进入 `failed`、`cancelled` 或 `dead_letter` 时，测试脚本立即终止。
- 手工点击 Send 时，`pm.execution.setNextRequest` 不会替你完成整个 Runner 流程，需要自行重复状态查询。

“取消与会话收尾”中的写请求默认由 `enable_mutations=false` 跳过，避免运行集合时误取消 Task 或关闭 Session。

## 4. 认证与统一响应

除健康类请求和 OSS signed URL 外，Runtime 请求使用：

```http
Authorization: Basic <Postman 根据 runtime_username:runtime_password 自动生成>
```

Collection 已配置 Postman Basic Auth，会使用 `runtime_username` 与 `runtime_password` 自动生成请求头，无需手工 Base64。服务端将该身份映射为配置的 `BASIC_AUTH_SUBJECT` 和 `BASIC_AUTH_SCOPES`；当前链路要求包含 `imaging:run`。资源归属按该调用方身份检查；同一个 ID 换成其他调用方身份，通常表现为 404，而不是泄露资源存在性。

单对象统一响应：

```json
{
  "success": true,
  "message": "操作成功",
  "data": {},
  "error_code": 0
}
```

分页统一响应：

```json
{
  "success": true,
  "message": "查询成功",
  "data": [],
  "page_info": {
    "total": 0,
    "page": 1,
    "limit": 20,
    "total_pages": 0
  },
  "error_code": 0
}
```

常见错误：

| HTTP / error_code | 含义 | 前端建议 |
|---|---|---|
| 401 | Basic 凭证缺失或错误 | 检查 Collection 用户名、密码和服务端配置 |
| 403 | 缺少 `imaging:run` | 提示无影像业务权限 |
| 404 / 4041 | 资源不存在或不属于调用方 | 不区分“不存在”和“无权访问” |
| 409 / 4091 | 同一幂等键对应的请求内容冲突 | 生成新 request_id，或恢复原请求内容 |
| 409 / 4092 | state_version、状态或冻结资源冲突 | 重新 GET 最新状态后决定是否重试 |
| 422 | Schema/参数校验失败 | 展示字段级输入错误；不要自动重试 |
| 503 / 5031 | 数据库等依赖未就绪 | 可退避重试，并保留用户上下文 |
| 503 / 5032 | 对象存储不可用 | 可退避重试 prepare/complete/prepare-view |

## 5. 接口总表

所有资源 ID 均放 query 或 request body，不使用 `/{id}`。

| 阶段 | 方法 | 路径 | 用途 |
|---|---|---|---|
| 环境 | GET | `/readiness` | 检查 DB、Redis、Broker 等依赖 |
| 环境 | GET | `/health` | 进程健康 |
| 环境 | GET | `/version` | 版本信息 |
| Session | POST | `/sessions` | 创建会话 |
| Session | GET | `/sessions?id=...` | 查询会话和 state_version |
| Session | POST | `/sessions/complete` | 完成会话 |
| Session | POST | `/sessions/close` | 关闭会话 |
| Study | POST | `/studies` | 创建 2–5 图 X-Ray Study |
| Study | GET | `/studies?id=...` | 查询 Study、Revision、Series 聚合状态 |
| Study | POST | `/series` | 创建 Series |
| Study | POST | `/studies/finalize` | 冻结 ready Study/Revision |
| Image | POST | `/images/prepare-upload` | 创建 Image 并获取直传票据 |
| OSS | PUT | `{{signed_url_N}}` | 直接上传原始影像，noauth |
| Image | POST | `/images/complete-upload` | 核对对象并进入异步校验 |
| Image | GET | `/images?id=...` | 查询单图状态 |
| Image | GET | `/images/page?series_id=...` | 分页查询 Series 影像 |
| Quality | POST | `/xray-quality-reviews` | 创建质量审查 Task |
| Quality | GET | `/tasks?id=...` | 轮询 Quality Task |
| Quality | GET | `/xray-quality-reviews?task_id=...` | 获取冻结质量结果 |
| Diagnose | POST | `/tasks` | 创建 diagnose Task |
| Diagnose | GET | `/tasks?id=...` | 轮询诊断状态 |
| Report | GET | `/reports/current?task_id=...` | 当前 final/published Report |
| Report | GET | `/reports/history?task_id=...` | Report 历史 |
| Report | GET | `/reports?id=...` | Report 详情 |
| Localization | POST | `/tasks` | 创建 anatomy_localization Task |
| Localization | GET | `/tasks?id=...` | 轮询定位 Task |
| Localization | GET | `/anatomy-localizations/current?source_task_id=...` | 主诊断关联的当前定位摘要 |
| Localization | GET | `/anatomy-localizations/history?source_task_id=...&page=1&page_size=20` | 定位任务历史 |
| Localization | GET | `/anatomy-localizations?task_id=...` | 定位 bbox 结果 |
| Localization | POST | `/anatomy-localizations/prepare-view` | 为冻结原图签发短 TTL 下载地址 |
| Localization | GET | `/anatomy-localizations/legend` | 图例、中文名、颜色、顺序 |
| Task | POST | `/tasks/cancel` | 使用 state_version 取消 Task |

## 6. 关键请求合同

### 6.1 创建 Quality Review

```json
{
  "study_id": "{{study_id}}",
  "study_revision_id": "{{study_revision_id}}",
  "request_id": "quality-{{run_id}}",
  "species": "{{species}}",
  "trace_id": "quality-trace-{{run_id}}"
}
```

返回的 `data.id` 保存为 `quality_review_task_id`。必须先轮询到 `completed`，再查询 Quality 结果并创建 diagnose。

### 6.2 创建 Diagnose

```json
{
  "study_id": "{{study_id}}",
  "study_revision_id": "{{study_revision_id}}",
  "request_id": "diagnose-{{run_id}}",
  "task_type": "diagnose",
  "species": "{{species}}",
  "quality_review_task_id": "{{quality_review_task_id}}",
  "clinical_context": {
    "contract_version": "xray-clinical-context.v1",
    "source": {
      "system": "postman",
      "recorded_at": "{{recorded_at}}",
      "temporal_scope": "available_at_request"
    },
    "chief_complaint": "前端联调病例",
    "study_reason": "X-Ray 检查"
  },
  "trace_id": "diagnose-trace-{{run_id}}"
}
```

约束：

- `quality_review_task_id` 必须与当前 Study、revision、manifest、species 完全一致。
- `clinical_context` 只能用于 diagnose。
- HTTP 201 只代表排队成功，不代表诊断完成。
- `execution_status=completed` 后，再读取 `current_report_id` 与 Report API。

### 6.3 创建 Anatomy Localization

```json
{
  "study_id": "{{study_id}}",
  "study_revision_id": "{{study_revision_id}}",
  "request_id": "localization-{{run_id}}",
  "task_type": "anatomy_localization",
  "species": "{{species}}",
  "source_task_id": "{{diagnose_task_id}}",
  "trace_id": "localization-trace-{{run_id}}"
}
```

约束：

- `source_task_id` 必填，必须指向同一 Study/revision/species 的 diagnose Task。
- 不要传 `clinical_context`。
- 不要传 `pet_profile_id`。
- 不要传 `quality_review_task_id`。
- Localization 是独立展示链，不会生成 Report，也不会改写主诊断结论。

### 6.4 prepare-view

请求全部冻结影像：

```json
{
  "task_id": "{{localization_task_id}}",
  "image_ids": null
}
```

只请求部分影像：

```json
{
  "task_id": "{{localization_task_id}}",
  "image_ids": ["image-id-1", "image-id-2"]
}
```

重要：当前请求 Schema 不接受 `expires_in`。TTL 来自服务端 `OSS_SIGNED_URL_TTL_SECONDS`，当前默认 300 秒，并在响应的 `data.expires_in` 与每张图的 `expires_at` 返回。

示例响应数据：

```json
{
  "task_id": "localization-task-id",
  "source_task_id": "diagnose-task-id",
  "study_id": "study-id",
  "study_revision_id": "revision-id",
  "expires_in": 300,
  "images": [
    {
      "image_id": "image-id-1",
      "series_id": "series-id",
      "sequence_no": 1,
      "projection": "lateral",
      "file_format": "jpeg",
      "content_type": "image/jpeg",
      "pixel_width": 2048,
      "pixel_height": 1536,
      "expires_at": "2026-09-04T08:00:00Z",
      "signed_url": "https://..."
    }
  ]
}
```

前端只在内存中使用 `signed_url`。出现 401/403/过期下载失败时重新调用 `prepare-view`，不要把旧 URL 存入业务库、localStorage、埋点或错误日志。

## 7. Task 与图片状态机

Task 执行状态：

```text
pending / queued / running / retry_wait
                  ↓
completed | failed | cancelled | dead_letter
```

前端处理原则：

- `pending`、`queued`、`running`、`retry_wait`：继续轮询。
- `retry_wait`：如果响应有 `next_retry_at`，以它控制下次刷新时间。
- `completed`：按 Task 类型读取 Quality、Report 或 Localization 结果。
- `failed`、`cancelled`、`dead_letter`：停止轮询，展示 `error_code`，不要无限自动重建 Task。
- 每次取消都必须带最新 `state_version`；409/4092 后先重新查询 Task。

Image 常用状态：

```text
uploading → validating → ready
                    ↘ failed
```

`complete-upload` 返回“已进入校验”不等于 `ready`。Study 只能在所有应有原图 ready 后 finalize。

## 8. Localization bbox 展示合同

结果中的每个 bbox 固定为：

```text
[x_min, y_min, x_max, y_max]
```

约束：

- 四个值均为有限数，范围 `0..1`。
- `x_min < x_max`，`y_min < y_max`。
- 坐标相对完整原始影像，不是裁图、缩略图或容器坐标。
- `status=not_localized` 时不要绘制 bbox；根据 `reason_code` 展示“未定位/证据不足”。
- 颜色与中文名称使用 `legend` 接口，不在前端另造第二份枚举。

如果 overlay 层与实际图片可见区域尺寸完全一致：

```text
left   = x_min × rendered_image_width
top    = y_min × rendered_image_height
width  = (x_max - x_min) × rendered_image_width
height = (y_max - y_min) × rendered_image_height
```

如果图片放在固定容器中并使用 `object-fit: contain`，需要扣除 letterbox：

```text
scale    = min(container_width / natural_width,
               container_height / natural_height)
image_w  = natural_width  × scale
image_h  = natural_height × scale
offset_x = (container_width  - image_w) / 2
offset_y = (container_height - image_h) / 2

left   = offset_x + x_min × image_w
top    = offset_y + y_min × image_h
width  = (x_max - x_min) × image_w
height = (y_max - y_min) × image_h
```

实现注意：

- 优先使用浏览器加载完成后的 `naturalWidth/naturalHeight`；`prepare-view` 返回的 `pixel_width/pixel_height` 可能为空。
- 图片尚未 load 时不要计算 bbox。
- ResizeObserver、窗口缩放、响应式布局和全屏切换后重新计算。
- 图片与 overlay 必须共享同一个定位上下文和变换。
- 如果实现缩放/平移查看器，bbox 应跟随同一 transform，不要单独二次缩放。
- 不要把 bbox 画进原始图片或上传派生标注图；展示层叠加即可。

## 9. 页面与接口建议映射

| 页面/区域 | 推荐接口 |
|---|---|
| 新建病例 | POST sessions、POST studies、POST series |
| 上传进度 | prepare-upload、OSS PUT、complete-upload、GET images / images/page |
| 检查冻结 | GET studies、POST studies/finalize |
| 质量状态 | POST xray-quality-reviews、GET tasks、GET xray-quality-reviews |
| 诊断状态 | POST tasks(diagnose)、GET tasks |
| 报告页 | reports/current、reports/history、reports?id= |
| 定位页 | anatomy-localizations/current/history/result/prepare-view/legend |
| 取消操作 | GET tasks 获取最新版本后 POST tasks/cancel |

前端最好把三个异步 Task ID 分开保存：

- `quality_review_task_id`
- `diagnose_task_id`
- `localization_task_id`

不要复用单个 `task_id` 字段覆盖它们，否则刷新页面后容易读取错结果。

## 10. 幂等、刷新与恢复

- Session：`source_session_id + request_id` 保持稳定时用于恢复原会话。
- Study：同 Session 下 `source_study_id` 应稳定。
- Quality / Diagnose / Localization：每类 Task 使用独立 `request_id` 前缀。
- 同一幂等键内容完全相同可返回原资源。
- 同一幂等键内容变化会返回 409/4091；不能靠盲重试解决。
- 浏览器刷新后，从业务持久状态恢复各资源 ID，再用 GET 接口重新取状态。
- signed URL 不属于可恢复业务状态，刷新后重新申请。
- 不要通过“查询接口”期待 Worker 被推进；GET 全部是观察，不触发执行。

## 11. 当前已知阻断与真实证据

### 11.1 tasks/page

`GET /api/v1/tasks/page` 当前真实调用返回 422。集合把它放在“07 已知阻断”且默认跳过。

前端临时替代方案：

- 已知 ID 的 Task：`GET /tasks?id=...`。
- 当前 Report：`GET /reports/current?task_id=...`。
- Localization 当前/历史：`GET /anatomy-localizations/current` 与 `history`。
- 不要用前端猜测或本地拼装“全部 Task 列表”。

### 11.2 已验证的只读关联样本

已有真实只读 HTTP 200 证据：

```text
diagnose task_id:     a042104cf0d84a4a8bede2bbac4a7036
localization task_id: 9107bd3b102f493996a14b7d7d715f30
```

这两个 ID 只有在 Basic Auth 映射的调用方身份与原资源一致时才可读取；其他身份得到 404/4041 属于预期安全行为。

已真实验证的只读能力包括 Task、Localization current/history/result、legend。完整新数据写入链需要 Runtime、Relay、Worker、Nacos/AI Config、Provider 和 OSS 同时就绪；当前文档生成阶段没有启动这些外部依赖，也没有产生新的 Provider 调用。

## 12. 前端验收清单

- [ ] 2、3、4、5 图上传槽位均可正确工作。
- [ ] OSS PUT 没有携带 Runtime Authorization。
- [ ] Quality 完成前不能提交 diagnose。
- [ ] Diagnose、Quality、Localization 三个 Task ID 不互相覆盖。
- [ ] 所有轮询都有终态和最大次数。
- [ ] Report 支持 `final` 与 `published`。
- [ ] Localization current 允许正常返回 `data=null`。
- [ ] bbox 在原尺寸、响应式缩放、letterbox、全屏下位置一致。
- [ ] `not_localized` 不绘框。
- [ ] 图例来自后端 `legend`。
- [ ] signed URL 只驻留内存，过期会重新申请。
- [ ] 401、403、4041、4091、4092、422、5031、5032 都有明确错误态。
- [ ] 前端没有依赖当前 422 的 `tasks/page`。
- [ ] 页面文案明确“AI 辅助结果”，没有把工程通过表述为医学发布通过。
