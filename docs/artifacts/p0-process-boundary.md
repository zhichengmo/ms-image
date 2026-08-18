# P0 process boundary（进程边界）artifact（证据产物）

> 中文阅读说明：`process boundary` 是“进程边界”，`artifact` 是“证据产物”；其余英文术语请参阅[英文术语中英对照](../术语中英对照.md)。

采集时间（UTC：协调世界时）：2026-08-09T17:02:01Z

| Plane（平面） | ASGI target（ASGI 应用入口） | Internal port（内部端口） | External path contract（外部路径合同） | Current evidence（当前证据） |
|---|---|---:|---|---|
| User（用户端） | `main:app` | 8000 | `/ms-image/api/v1/*` | Local route inspection（本地路由检查）；proxy not verified（代理未验证） |
| Admin（管理端） | `main:admin_app` | 8001 | `/ms-image/admin/api/v1/*` | Compose command（Compose 命令）和 local route inspection（本地路由检查）；proxy not verified（代理未验证） |

两个应用是 Compose（容器编排）中的独立 ASGI（异步服务器网关接口）进程。`root_path`
只是部署元数据，不能证明 Gateway（网关）实际转发了对应前缀。Gateway configuration（网关配置）
和从部署边缘执行的 HTTP smoke（HTTP 冒烟验证）仍是未关闭的阻断项。

当前已检查的 Route contract（路由合同）：

- User（用户端）：`/api/v1/health`、`/api/v1/version`、`/api/v1/readiness`、`/docs`、`/openapi.json`。
- Admin（管理端）：`/`（liveness：存活检查）、`/api/v1/status`、`/api/v1/info`、`/api/v1/readiness`
  （admin JWT：管理端 JSON Web Token + `xray:admin:read`），
  `/api/v1/xray/control/runs?run_id=...`, `/docs`, `/openapi.json`.

管理端文档路由相对于自身 root path（根路径），避免旧 `/ms-image/admin/admin/docs` 的路径歧义。

Admin docs（管理端文档）/OpenAPI（接口规范）仅在 `ENV=dev` 时启用；非开发环境启动时关闭
schema/docs（接口结构/文档）端点。开发环境 wildcard CORS（通配跨域资源共享）不再允许携带凭证的浏览器请求；
XRay（X 光）认证仍使用显式 JWT（JSON Web Token）请求头。

`run_servers.py` 现在监控两个子进程，任一 plane（平面）退出时终止另一进程；
`start_admin_api.py` 使用 `reload=False`，形成稳定的 standalone process contract（独立进程合同）。

历史 independent-process smoke（独立进程冒烟验证，2026-08-09 19:33，发生在 readiness scope
就绪性作用域加固之前；为可追溯性保留）结果：

- `uvicorn main:app --port 18000` → `/api/v1/health` 返回 HTTP（超文本传输协议）`200`。
- `uvicorn main:admin_app --port 18001` → `/api/v1/readiness` 返回 HTTP `503`，原因是
  MySQL（关系型数据库）不可用。该观察对当前 authorization contract（授权合同）已经过时，
  仅作为加固前 baseline（基线）保留。

后续 local TestClient smoke（本地测试客户端冒烟验证，2026-08-10 00:57，无外部网关）：

- admin（管理端）`/` liveness（存活检查）返回 `200`；
- admin（管理端）`/api/v1/readiness` 未携带 token（令牌）时返回 `401`；
- admin readiness（管理端就绪检查）携带有效 `xray:admin:read` token（令牌）时返回 `503`，
  原因是 MySQL 不可用，符合 fail-closed（失败即关闭）依赖语义；
- user（用户端）`/api/v1/health` 和 `/api/v1/version` 返回 `200`；用户端 XRay 和管理端 XRay
  控制路由未携带 token（令牌）时返回 `401`。

Compose（容器编排）默认把 admin host port（管理端宿主机端口）绑定到 `127.0.0.1:8001`；
ingress（入口网关）或 sidecar（边车代理）应是唯一外部暴露路径。这些仅是 local process checks
（本地进程检查），不能证明 production gateway（生产网关）已经通过验证。
