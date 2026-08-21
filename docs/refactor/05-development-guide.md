# MS-Image 重构开发指南

状态：`CURRENT_DEVELOPMENT_CONTRACT`（当前开发合同）
适用对象：后续实现目标架构的开发人员和自动化编码代理。
项目规则优先级：根目录 `AGENTS.md`（代理项目规则） > 本文 > 一般示例。

## 1. 开发前先确认状态

当前代码已实现 Session/Study/Series/Image、Task/Stage、provider-disabled
AI Call、Report 与 Evaluation 的工程链路；目标 schema 尚未迁移，真实
MySQL/OSS/Broker/Provider 资格和医学效果仍未验证。开发说明必须区分：

- `CONFIRMED`（已确认）：可由当前代码、schema 或 Artifact 证明。
- `PROPOSED`（候选）：目标合同，尚未实现。
- `UNKNOWN`（未知）：证据不足，不能猜测。

禁止把“文档已设计”写成“代码已完成”，也禁止把旧 `xray_accuracy_*` 表改名后宣称迁移完成。

## 2. 强制分层

```text
API -> Service -> CRUD/DAL(DalBase) -> Model/DB
Schema = API 边界和数据结构合同
Worker -> Service，不直连 ORM
```

| 层 | 允许 | 禁止 |
|---|---|---|
| API（接口层） | 路由、参数、依赖注入、鉴权、统一响应 | 多表编排、复杂状态判断、直接 SQL |
| Service（业务服务层） | 业务规则、事务、多 DAL 编排、CAS/幂等 | FastAPI Request/Depends、返回 HTTP 响应为主设计 |
| CRUD/DAL（数据访问层） | 基于 `DalBase` 的实体查询和持久化 | HTTP 语义、外部网络 I/O、另造 Repository |
| Schema（结构层） | Create/Update/Query/Response 校验 | 数据库访问 |
| Model（模型层） | ORM、字段、索引、约束和中文 comment | 业务流程 |

## 3. 实体模块补齐顺序

每个核心实体按以下顺序开发：

1. `apps/runtime/models/xxx.py`：一张表一个 ORM。
2. `apps/runtime/schemas/xxx.py`：Create/Update/Query/Response 分离。
3. `apps/runtime/crud/xxx.py`：一个 `XxxDal(DalBase)`。
4. `apps/runtime/service/xxx_service.py`：业务用例和事务。
5. `apps/runtime/api/.../endpoints/xxx.py`：薄路由。
6. 在对应 `api.py` 注册路由。
7. 迁移和测试只在用户另行授权后创建。

命名示例：

```text
Model: Session
Table: session_record（会话记录表）
DAL: SessionDal
Service: SessionService
Schema: SessionCreate / SessionUpdate / SessionQuery / SessionResponse
Endpoint file: sessions.py
```

## 4. DAL（数据访问层）规则

- 所有实体 DAL 继承 `apps.runtime.core.crud.DalBase`。
- 构造函数接收 `AsyncSession`，并调用 `super().__init__(db=db, model=YourModel)`。
- 所有 `get_data/get_datas/get_count/create_data/put_data/delete_datas` 调用使用 `await`。
- 实体特有 CAS、lease、claim 和资源归属查询封装为该实体 DAL 方法。
- Service、API、Worker 和脚本不得直接写 `select/update/delete`。
- 不使用遗留 `apps/runtime/crud/base.py:CRUDBase` 作为目标数据访问实现；该历史路径
  不能作为当前 Runtime 的 import 或实现依据。
- DAL `create_data` 只 flush，不代表 commit；事务由 Service 拥有。

## 5. Service（业务服务层）规则

Service 构造函数接收 `AsyncSession` 并初始化所需 DAL。方法应显式表达业务动作：

```python
class SessionService:
    def __init__(self, db: AsyncSession):
        self.session_dal = SessionDal(db)

    async def create_session(self, payload: SessionCreate) -> SessionResponse:
        ...
```

多表原子事务由 Service 编排。OSS、Broker 和 Provider 网络调用必须放在 commit 之后，结果再用新的短事务 CAS 回写。

## 6. API（接口）规则

- 单对象使用 `GenericResponse[T]`（统一对象响应）。
- 分页使用 `PagedResponse[T]`（统一分页响应）。
- 资源 ID 放 query 参数或 request body，禁止 `/{id}`。
- 普通资源接口与 Admin（管理）接口分开。
- 业务 API 不允许调用方覆盖 `run_mode`、实验臂、release fingerprint 或医学状态。
- 只有健康检查、版本和简单静态状态可跳过 Service。

推荐：

```text
POST /sessions
GET  /sessions?id={session_id}
POST /studies/complete-upload     body.image_id
GET  /tasks?id={task_id}
POST /admin/reports/invalidate   body.report_id
```

禁止：

```text
GET /sessions/{id}
POST /tasks/{id}/complete
```

## 7. Model（模型层）规则

- 每表独立 `id VARCHAR(64) PRIMARY KEY`，服务端生成。
- 不声明 Foreign Key，不使用数据库 Enum，不设计 `tenant_id`。
- `tenant_id` 不落目标 Model，但不得删除认证；可信 subject/service identity、scope 和资源归属由 Service/DAL 强制校验。
- 状态用 `VARCHAR` 并在 comment 写候选值和中文含义。
- 不使用联合主键。
- 可演进结构用版本化 JSON，但参与高频查询、唯一约束、CAS 和 lease 的字段不能藏进 JSON。
- `created_at/updated_at` 使用 UTC `DATETIME(6)`。

## 8. Schema（结构合同）规则

- Create 不接受服务端状态、owner、hash 或审计字段。
- Update 默认字段可选，但状态推进使用专用 Command Schema（命令结构），不暴露万能 patch。
- Response 设置 `from_attributes=True`。
- Query 单独定义分页、状态、时间和 owner 范围。
- JSON 字段必须对应明确 `schema_version`，递归拒绝 Secret、truth、label、路径和未授权 metadata。

## 9. Stage（阶段）开发规则

- 公共阶段放 `apps/runtime/stages/common/`，XRay 专项放
  `apps/runtime/stages/xray/`。
- 每个 Stage 实现固定 `handler_key/version` 和输入输出 Schema。
- 只通过 `StageRegistry` 注册，不允许运行时 import string 或 `latest`。
- Stage 返回 `StageResult`，由 `ImagingExecutionService` 持久化和推进。
- Stage 不直接调用 DAL commit；模型调用通过 `AIRequestService`。
- 医学 Stage 的 Prompt、Schema、模型和图像 manifest 必须来自冻结 Config/Task。

## 10. 错误合同

错误分三类，不能混写：

| 类型 | 示例 | 处理 |
|---|---|---|
| Input/Authorization（输入/授权） | 资源不存在、越权、payload/schema 错误 | API 稳定错误，不创建可执行 Task |
| Engineering（工程） | OSS 缺失、Provider timeout、lease 冲突、parse failure | 记录稳定 `error_code`，医学状态 `not_produced` |
| Medical（医学） | `review_required`、`non_diagnostic` | selected model owner 的合法医学终态 |

`error_message` 必须脱敏；日志和数据库不保存 Secret、完整 Prompt、原始 URL query 或未脱敏响应。

## 11. 幂等、CAS 和 lease

- 创建接口使用调用方可稳定重放的 request idempotency key（请求幂等键）。
- 相同幂等键不同 payload 返回冲突，不能静默复用旧结果。
- 所有状态推进匹配 `state_version`。
- Stage 完成匹配 owner + `lease_generation` + state version。
- Provider 首次发送前先持久化 prepared Call 和预算预留。
- unknown Call 只能对账原 Call，不得创建第二逻辑调用。

## 12. OSS 和外部调用

- OSS SDK 只在 `ObjectStorageGateway`（对象存储网关）内。
- 新对象 key 使用领域 owner/image/version；历史 tenant 派生 key 在同一 Gateway 内走兼容读取，不创建平行 OSS 实现。
- Provider SDK/HTTP 只在 Provider Client（服务客户端）内。
- Broker publish 只在 Outbox Relay（发件箱中继）内。
- Service 传递稳定 ObjectRef 和 DTO（数据传输对象），不传持久 signed URL。
- 所有外部调用设置 timeout、大小、重试、预算和稳定错误分类。

## 13. 可观测与审计

至少贯穿：

```text
trace_id
session_id / study_id / task_id / stage_id / call_id / report_id
config_sha256 / compiled_pipeline_sha256 / release_fingerprint
requested/sent/accepted manifest hash
lease owner/generation/state_version
```

日志只用于观测，不替代数据库事实。AuditSink（审计接收端）未完成前，现有 TraceEvent 不能删除。

## 14. 一个功能的完成定义

- [ ] API、Service、DAL、Schema、Model 层次完整。
- [ ] 无 API/Service/Worker 直接 SQL。
- [ ] 事务内无 OSS/Broker/Provider I/O。
- [ ] 幂等、CAS、lease 和重放语义明确。
- [ ] 权限、资源归属和 Secret 脱敏已验证。
- [ ] 字段、状态、索引与设计母文一致。
- [ ] 文档明确区分已实现和候选。
- [ ] 相关 Gate 的可复核 Artifact 已生成。
- [ ] 医学变化通过冻结同病例 paired A/B，而不是只看调用成功。
