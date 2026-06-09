# T-06 Public API 게이트웨이·인증·멱등·envelope [BE]

- 서비스: `services/aml-svc` · Effort: L · 의존: T-01, T-03 · Status: TODO

## 목표
3-plane(Public/Internal/Admin) API 표면과 횡단 규약(인증·tenant/data-scope·HMAC·멱등·envelope·에러)을 구현한다.

## 구현 항목
- [ ] base path: Public `/api/v1/aml/*`·`/api/v1/evidence/aml/*`, Internal `/internal/v1/aml/*`, Admin `/api/v1/admin/aml/*`(bo-api 전용). 버저닝 `/api/v1`·`/internal/v1`
- [ ] 공통 헤더: `Tenant-Id`(필수), `Source-System`(Public ingest/screen), `X-Signature: hmac-sha256=...`(Public), `Idempotency-Key`(쓰기성 Public), `X-Trace-Id`(옵션, 응답 반향)
- [ ] 인증: Public=API Key+HMAC(D-13, OAuth2/mTLS 옵션), Internal=`X-Internal-Service`+mTLS, Admin=bo-api JWT+RBAC+`dataScope` 클레임
- [ ] 권한 scope: `aml:event:write`, `aml:screen:evaluate`, `aml:ra:evaluate`, `aml:tm:evaluate`, `aml:case:read/update`, `aml:evidence:export`, `aml:admin:*`, `aml:pii:reveal`
- [ ] 멱등 store: `Idempotency-Key` 처리(처리중=503 `AML.IDEMPOTENCY_PROCESSING`, 충돌=`AML.IDEMPOTENCY_CONFLICT`)
- [ ] 응답 envelope: 성공 `{data,traceId}`, 목록 `{data,page}`, 실패 `{error{code,message,details,traceId}}`
- [ ] 표준 에러 `AML.*`(BAD_REQUEST·UNKNOWN_SOURCE_SYSTEM·INVALID_SIGNATURE·FORBIDDEN_SCOPE·TENANT_MISMATCH·*_NOT_FOUND·SELF_APPROVAL_FORBIDDEN·APPROVAL_PAYLOAD_CHANGED·INVALID_STATE_TRANSITION·SCREENING_REQUIRES_REVIEW(422)·RATE_LIMITED(429)·SCREENING_UNAVAILABLE(503)·INTERNAL_ERROR)
- [ ] PII 마스킹 응답 필터, `aml:pii:reveal` 시 `aml_audit_events(RAW_DATA_ACCESS)` 기록

## 참조
- `docs/design/api/02-aml-api.md` §0(3-plane), §1(횡단 규약), §4(에러)
- `docs/software/02-amlSvc-sass.md` §15.7
