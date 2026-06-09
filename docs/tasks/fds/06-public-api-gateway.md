# T-06 Public API 게이트웨이·인증·scope·envelope [BE]

- 서비스: `services/fds-svc` · Effort: L · 의존: T-01, T-03 · Status: TODO

## 목표
API-first 제품의 외부/Admin HTTP 경계를 구축한다. 인증(API Key+HMAC/OAuth2 Client Credentials/mTLS), OAuth2 scope, 격리 헤더, 페이지네이션·멱등·표준 에러 envelope를 확정한다.

## 구현 항목
- [ ] base path `/api/v1`. 외부 `/fds/**`·`/evidence/fds/**`, Admin `/admin/fds/**`(bo-api 위임만)
- [ ] **[BE]** 인증: API Key+HMAC(`X-Api-Key`+`X-Signature: hmac-sha256=...`), OAuth2 Bearer, mTLS. `fds_api_credentials.secret_hash` 대조(secret 원문 미저장)
- [ ] OAuth2 scope: `fds:event:write`/`decision:evaluate`/`case:read`/`case:update`/`evidence:export`/`rule:simulate`/`action:write`/`admin:rule`/`admin:group`/`admin:source-system`/`admin:credential`
- [ ] 격리 헤더 파싱: `Tenant-Id`(필수), `Workspace-Id`(default `default`), `Source-System`, `Idempotency-Key`, `X-Trace-Id`
- [ ] 횡단 규약: 페이지네이션 envelope(`content/page/size/totalElements`), `X-Api-Version: v1`
- [ ] 표준 에러 모델(RFC7807 + `code`/`traceId`), PII 미노출. 에러 코드 `FDS-*`(§6)
- [ ] credential admin: `GET/POST /admin/fds/credentials`(secret 1회 반환), `/rotate`(🔒 SECURITY_ADMIN)
- [ ] rate limit(`FDS-RATE-LIMIT` 429), IP allowlist

## 참조
- `docs/software/01-fdsSvc-sass.md` §12.8(Public API·인증·scope·장애원칙)
- `docs/design/api/01-fds-api.md` §2(인증·인가·격리), §3(횡단 규약), §6(에러), §10(OpenAPI YAML 스니펫)
- `docs/design/db/01-fds-db.md` §5.29(api_credentials)
