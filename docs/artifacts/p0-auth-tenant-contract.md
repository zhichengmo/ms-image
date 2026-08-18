# P0 authentication（身份认证）and tenant contract（租户合同）

> 中文阅读说明：`authentication` 是“身份认证”，`tenant` 是“租户”；其余英文术语请参阅[英文术语中英对照](../术语中英对照.md)。

Status: `PARTIAL` (contract scaffold plus validation-only XRay routes; live DB isolation not accepted)

- User JWT: configured algorithm/issuer/audience, required `exp`, `iss`, `aud`,
  and `sub`; missing or invalid token is `401`.
- Admin JWT: isolated HS256 key, issuer/audience, and scope dependency;
  missing scope is `403`.
- Known placeholder JWT secrets (for example `replace-with-a-secret-managed-outside-git`)
  are rejected as `503` configuration-not-ready; they cannot be used to forge an admin token.
- Tenant: `tenant_id` is read only from the verified user JWT claim configured
  by `TENANT_CLAIM`. Query/body tenant values must never override it.
- XRay endpoints, once introduced, must depend on
  `require_tenant_scope(...)`; Run/Review/Trace/Release operations must apply
  tenant filtering before DAL access.
- The zero-model user routes (`/api/v1/xray/runs`, `/api/v1/xray/run-cancellations`,
  `/api/v1/xray/traces`) now use `require_tenant_scope()`. The admin read route
  `/admin/api/v1/xray/control/runs` uses an isolated admin JWT plus tenant claim
  and `xray:admin:read` scope.
- Secrets, signed URLs, and original image addresses are not valid response or
  log fields. A future credential service must issue short-lived, single-use,
  allowlist-bound image credentials.
- The legacy exception registration path now logs only status/path and does not
  echo validation bodies or exception detail; XRay handlers must retain this
  fixed-message rule.
- Admin readiness is a control-plane dependency probe and therefore requires
  the same `xray:admin:read` scope; it is not an anonymous infrastructure
  endpoint. Component failures remain fail-closed and are not a substitute for
  the external gateway/security boundary.
- Legacy RSA API-key timestamps must satisfy `0 <= now - timestamp <= 300`; future-dated
  credentials are rejected. Single-use nonce/replay storage remains an open credential-service
  contract and is not claimed by this Phase 0 skeleton.

Open gap: live DB-backed cross-tenant rejection and the full diagnostic-vs-control-plane
write scope matrix still require deployment evidence. No release/truth/Holdout write
route exists in this skeleton.

Local admin scope smoke (2026-08-09 19:31, ephemeral HS256 key): missing token
`401`, wrong issuer `401`, missing `xray:admin:read` scope `403`, valid read scope
`200`. This validates the existing admin boundary only; it is not an XRay tenant
isolation acceptance.
