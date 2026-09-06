# FDS API 명세서 (fds-svc REST · hanpass-ph)

> **운영 도메인**: 본 명세는 **hanpass-ph**(필리핀 송금·월렛 사업자) AML/FDS RegOps 플랫폼의 fds-svc REST API 정본이다. 거래는 hanpass-ph **5채널**(`CROSS_BORDER_REMIT`(해외송금)·`DOMESTIC_REMIT`(국내송금)·`CASH_IN`(월렛충전)·`WALLET_PAYMENT`(월렛결제)·`WALLET_WITHDRAWAL`(월렛출금))만 다룬다(§3.5). 카드결제·가상자산(crypto)·무역금융(trade)·PG·이커머스·마켓플레이스·B2B 등 비-hanpass 채널/도메인은 운영 대상이 아니다(닫힌 enum에는 잔존하나 hanpass-ph는 미사용).
> 정본: `.claude/skills/_shared/aegis-stack.md` (4서비스 모노레포 · Java 25 · Spring Boot 3.5.x · 헥사고날 · 멀티테넌시 · PII 마스킹 · 4-eyes · 한국 Policy Pack).
> 입력 설계서: `docs/software/01-fdsSvc-sass.md` (§6.2 헥사고날 `adapter/in/rest`, §11 action/case/결재, §12.8 Public API, §13 멀티테넌시, §16 PII/규제).
> 입력 DB: `docs/design/db/01-fds-db.md` (스키마 `fds`, 멀티테넌시 `tenant_id/workspace_id/data_scope`, enum 코드값 §4, 컬럼/타입 §5, `subject_kind` 11종 `CASE_CLOSE`·`POLICY_PACK`·`RULE_PARAM`·`TENANT_REGULATORY_CURRENCY` 포함 §5.23(r13/r20 이격 교정), `fds_cases.aml_case_id` §5.13, **배포 모델 `fds_tenants.deployment_model`(3종)·`onboarding_status`(8종)·`default_region`·`infra_ref` §4.1·§5.1, 구 `isolation_mode` 폐기**, `close_reason` 8종 §4.11, `compliance_policy` JSONB §5.1, **`transaction_type` 폐쇄 enum 12종 §4.19**, `channel_type` §4.4, corridor 컬럼 §5.5).
> 공통 inbound 인증 정본: [`00-common-machine-auth.md`](00-common-machine-auth.md) (wire v2 canonical request·credential version·durable nonce·전환/회전).
> 코드 정본: **`services/fds-svc`** (`com.aegis.fds.adapter.in.rest` 전 컨트롤러·DTO, `com.aegis.fds.domain.enums.ChannelType`·`EventFamily`, Flyway `V17`/`V20`/`V22` 데모 룰). 본 문서의 엔드포인트·요청/응답 DTO·enum은 이 저장소와 1:1 일치한다(추측 금지).
> 책임 서비스: **`services/fds-svc`**. AML/STR/CTR 본 케이스는 `aml-svc`, 운영자 IAM·결재 집약·감사는 `bo-api`. **bo-web은 bo-api만 호출(엔진 직접호출 금지)**.

## 목차
1. [범위·원칙](#1-범위원칙)
2. [인증·인가·격리](#2-인증인가격리)
3. [횡단 규약 (버저닝·페이지네이션·멱등성·에러·hanpass taxonomy)](#3-횡단-규약)
4. [엔드포인트 표 (그룹별)](#4-엔드포인트-표)
5. [DTO 스키마](#5-dto-스키마)
6. [에러 코드](#6-에러-코드)
7. [reason code / decision code 사전](#7-reason-code--decision-code-사전)
8. [4-eyes 결재 대상 엔드포인트](#8-4-eyes-결재-대상-엔드포인트)
9. [Webhook 콜백 계약 (outbound)](#9-webhook-콜백-계약-outbound)
10. [OpenAPI(YAML) 스니펫](#10-openapi-yaml-스니펫)
11. [BO 화면(PRD) ↔ API 매핑](#11-bo-화면prd--api-매핑)
12. [서비스 경계 주의 (운영자 집계 = bo-api 소유)](#12-서비스-경계-주의)
13. [downstream 확정 명칭](#13-downstream-확정-명칭)
14. [변경 이력](#14-변경-이력)

---

## 1. 범위·원칙

- 본 문서는 **fds-svc가 노출하는 HTTP API**를 확정한다. 두 부류로 나눈다.
  - **외부(서비스 시스템) API** — `/api/v1/fds/**`, `/api/v1/evidence/fds/**` (설계서 §12.8). API Key+HMAC / OAuth2 / mTLS 인증. 거래 시스템이 직접 호출.
  - **Admin API** — `/api/v1/admin/fds/**`. **bo-api만** 호출(운영자 토큰 위임). bo-web → bo-api → fds-svc admin API 경로만 허용.
- API path는 정본 버저닝 규약 `/api/v1`을 사용한다(설계서 §12 예시의 `/v1/...`은 게이트웨이 prefix 생략형이며, 본 명세는 `/api/v1`로 정규화).
- 모든 식별자·금액·enum은 DB 설계서(`01-fds-db.md` §4, §5)와 100% 일치. raw PII는 응답 DTO에 미노출(token/hash/마스킹).
- fds-svc는 `OPEN_AML_CASE`/`REGULATORY_REPORT` **후보만 생성**하고 본 처리는 aml-svc로 위임(§12). 본 API는 후보 등록·cross-ref 조회만 제공.

### 1.1 정본 확정 (이 문서가 진실의 출처)

정본 위계는 `_shared/target-architecture.md` + 설계서(`docs/software`)·DB(`docs/design/db`)·API(`docs/design/api`)이며, 파생(integration·tasks·PRD·PPT)은 이를 따른다. 본 API 명세는 다음 항목의 **정본**이다.

- **action_type 마스터 = API `ActionType` enum 22종(전수, §5.7·§7·§10 OpenAPI)**. 설계서 §11.2는 이 22종으로 동기화한다. 설계서 §15의 verb는 정규 매핑(`OPEN_*_CASE`=`OPEN_CASE`+`case_type`, `SUSPEND_MERCHANT`=`SUSPEND_INSTRUMENT`, `SEND_SECURITY_ALERT`=`SEND_ALERT`)으로 흡수한다. `HOLD_TRANSACTION`은 비정본 — 자금 hold는 `HOLD_FUNDS`, 송금 차단은 `BLOCK_TRANSACTION`.
- **HTTP 상태코드 = 본 API 명세 §6이 정본**. PRD/PPT는 §6 매핑을 따른다(요청 필드 검증=400 `FDS-VALIDATION-001`; create-only 상태키 충돌은 409이며 위험그룹 동일 `(tenant,workspace,groupId)` 생성은 `FDS-STATE-CONFLICT`; 결재 누락=409 `FDS-APPROVAL-REQUIRED`, maker=checker=409 `FDS-APPROVAL-SELF`, raw PII=422 `FDS-PII-REJECTED`, rate limit=429 `FDS-RATE-LIMIT`).
- **4-eyes `subjectKind` = DB 정본 `fds_approval_requests.subject_kind` 11종(§5.23, r13/r20 이격 교정)과 1:1**. `ACTION`/`RULE`/`MAPPING`/`SECRET`/`GROUP`/`EXPORT`/`MERCHANT_NORMALIZE`/`CASE_CLOSE`/`POLICY_PACK`/`RULE_PARAM`/`TENANT_REGULATORY_CURRENCY`. **case 종결(`POST /fds/cases/{caseId}/close`)은 `CASE_CLOSE`(subjectRef=`case_id`)로 매핑**하고, **규제 팩 토글 변경(`PUT /api/v1/bo/fds/tenants/{tenantId}` compliance_policy)은 `POLICY_PACK`(subjectRef=`tenant_id`, 설계서 §16.2)로 매핑**하며, **룰 변수 편집(`POST /admin/fds/rules/{ruleId}:update-params`)은 `RULE_PARAM`(subjectRef=`rule_id`)으로 매핑**하며, **테넌트 규제통화 전환(`POST .../compliance/regulatory-currency:change`)은 `TENANT_REGULATORY_CURRENCY`(subjectRef=`tenant_id`, 다통화 PLAN 20260818 U17)로 매핑**한다. integration·tasks는 이 11종을 따른다.
- **BO exact capability와 플랫폼 read-only 경계**: system role과 custom `bo_role_scopes`는 같은 `FdsAuthorizationPolicy`로 평가한다. `platformOperator`는 tenant/workspace 횡단 target 선택을 위한 data-scope 속성일 뿐 메뉴·결재·action·evidence·PII/STR 인가 우회가 아니다. `SFDS_PLATFORM_OPS`는 횡단 조회(`SFDS_PLATFORM/TENANT/DECISION/CASE/AUDIT:READ`)만 가능하며 `SFDS_ACTION:OPERATE`·`SFDS_EVIDENCE:EXPORT`와 어떤 checker capability도 갖지 않는다. `BO_SUPER_ADMIN`의 effective scope `*`만 wildcard이고, `SFDS_PLATFORM_ADMIN`은 tenant admin/write를 별도로 가진다.
- **Webhook 콜백 계약 = §9가 정본**. 4종(`FdsDecisionCreated`/`FdsCaseOpened`/`FdsCaseStatusChanged`/`FdsActionResult`)·핵심 payload·envelope·`X-Signature` HMAC·재시도/멱등을 §9로 확정한다. `FdsActionResult`는 `actionType`(action_type 22종)을 **필수 포함**하고 `status`는 action_status enum 기준이다. integration §3.2·§4.x는 §9.1 핵심 키와 1:1 정렬한다.
- **운영자 집계 API 소유 경계 = bo-api(§12)**. 대시보드(플랫폼·서비스별)·서비스 관리(목록/상세/등록/설정)·통합 감사 조회 화면은 **bo-api가 소유·집약·인증**한다. fds-svc는 P0-03의 scoped 저수준 `GET /api/v1/admin/fds/audit-events`를 포함한 원천 데이터 API만 제공한다. 화면용 `/dashboard|tenants|audit` aggregate를 엔진에 추가하지 않으며 PRD/PPT는 bo-api를 호출 대상으로 명시한다.

---

## 2. 인증·인가·격리

### 2.1 인증 방식 (설계서 §12.8)
| 방식 | 용도 | 적용 API |
|---|---|---|
| API Key + HMAC(`X-Api-Key` + `X-Auth-Version: 2` + `X-Nonce` + `X-Signature`) | 서버 간 기본 연동. wire v2 canonical bytes·raw query·고정 9-key scopeContext·body digest·replay 의미론은 [공통 machine-auth 정본](00-common-machine-auth.md)만 따른다. 구 v1 공식은 기존 credential 전환 호환에만 허용 | 외부 Ingest/Decision/Case/Evidence API, 내부 customer-profile API, bo-api typed 위임 |
| OAuth2 Client Credentials (`Authorization: Bearer`) | 권한 scope 세분화 | 외부 API, Admin API(bo-api 위임 토큰) |
| mTLS | 고위험 action API | Decision/Action 계열 옵션 |
| Webhook signature(`X-Signature`) | 고객 callback 위변조 방지 | Webhook 송신 |

- 인증 주체는 `fds_api_credentials`(`credential_type` = `API_KEY`/`OAUTH2_CLIENT`/`MTLS`/`WEBHOOK`)로 검증. HMAC 검증에는 필요 시 AES-GCM 복호화한 공유 secret을 사용하며 **DB에는 `secret_ciphertext`만 저장**한다(raw secret 미저장·미로그).
- API key·OAuth2 client·webhook은 `(tenantId, workspaceId)`에 바인딩. cross-workspace 접근은 명시적 scope 필요.
- v2 요청은 `Tenant-Id`·최종 raw path/query·FDS workspace·scope context·최종 body bytes·timestamp·nonce를 함께 서명한다. `Source-System`만 source header 정본이며 alias는 허용하지 않는다. credential/service policy 교집합으로 protocol을 제한하고 기존 row=`[v1,v2]`, 신규 row=`[v2]` 전환 정책을 적용한다. v1은 RFC3339 offset timestamp 호환을 유지하지만 v2는 UTC `Z`만 허용한다.
- filter coverage/scope는 servlet normalized route로 판단하고 HMAC은 raw URI를 고정한다. dot segment·encoded separator·matrix parameter·double slash 등 모호한 raw path와 보안/canonical singleton header 중복은 body/credential/nonce 처리 전에 generic 401이다. signed client는 redirect를 자동 추종하지 않고 새 target에 새 nonce로 재서명한다. bo-api 공용 engine `RestClient`도 `DONT_FOLLOW`를 강제해 302 target으로 machine header를 전달하지 않는다. P0-04부터 bo-api→FDS typed client도 final URI/raw query와 정확히 한 번 직렬화한 body bytes를 wire v2로 서명한다.
- `/api/v1/evidence/fds/**`도 `/api/v1/fds/**`와 동일한 machine-auth filter의 protected/external
  surface이며 servlet registration 누락을 허용하지 않는다. Evidence는 기존 FDS API이므로
  credential/service가 v1을 함께 허용하는 동안 공통 정본 §6의 v1/v2 이중 전환을 유지하며,
  route별 canonical v2-only 대상으로 추가하지 않는다. 인증되지 않은 read/write는 401, 정상 인증 후
  `fds:evidence:export` 누락은 403이며 export 생성·download의 actor는 서명 검증 뒤 승격된
  `X-User-Subject`만 사용한다.
- nonce TTL 기본 15분은 `2 × timestamp skew`보다 엄격히 길어야 하고, 만료 row는 기본 1분마다 최대 `20 × 5,000`건을 짧은 batch로 정리한다. local/demo simulator credential provisioner와 bootstrap bypass는 명시적 `local|demo` positive profile + opt-in에서만 허용되며 Flyway business seed가 아니다.
- **적용 경계(2026-07-15)**: P0-04로 `/internal/v1/fds/**` 실제 filter registration과 v2-only 정책, AML profile 최소 scope, bo-api→FDS typed signer를 완료했다. BO credential은 exact `(tenant,workspace)` target에만 해소되며 다른 target/global fallback이 없다. P0-14로 multipart 최종 raw-byte client 전환(nonce 유도 boundary·`sha-256(body)`+exact `Content-Type` 서명·재직렬화 없는 전송, [공통 정본 §3.4](00-common-machine-auth.md#34-multipart-본문-계약p0-14-코드truth))과 production capability guard(security tier vs transport 분리·startup fail-closed)를 완료했다. 남은 미완료는 credential 폐기·자동 유예회전·last-used·rate/network/workload 통제(P1-02)다([공통 정본 §7](00-common-machine-auth.md#7-후속-태스크-경계)).

### 2.2 격리 컨텍스트 (필수 헤더)
| 헤더 | 매핑 컬럼 | 필수 | 설명 |
|---|---|---|---|
| `Tenant-Id` | `tenant_id` | 필수(외부) | SaaS 서비스 경계. **hanpass-ph는 단일 운영 테넌트 `tenant_demo`로 서비스한다**(테넌트=서비스 모델은 코드/스키마 truth로 유지하되 운영 테넌트는 1종). Admin API는 위임 토큰 claim에서 주입 |
| `Workspace-Id` | `workspace_id` | 선택(미지정 시 `default`) | hanpass-ph 운영 workspace는 `default`. `sandbox`는 shadow-only(action 미발행) |
| `X-Data-Scope` | `data_scope` | 선택 | 외부 machine 요청의 권한 context. v2 `scopeContext.data-scope`에 결합 |
| `Source-System` | `source_system` | Ingest/Decision 필수 | connector·schema 식별. source header의 유일한 정본 이름(`X-Source-System` 등 alias 금지) |
| `Idempotency-Key` | `idempotency_key` | 멱등 엔드포인트 필수 | 중복 방지(§3.3) |
| `X-Api-Key` | `credential_id` | HMAC 인증 시 필수 | `(tenant_id, workspace_id, credential_id)` credential |
| `X-User-Subject` | audit/approval actor | 운영자 위임 write 시 필수 | bo-api가 전달하고 v2 서명에 결합. HMAC 성공 후 verified attribute로만 소비하며 raw header/body maker를 직접 신뢰하지 않음 |
| `X-Timestamp` | — | HMAC 인증 시 필수 | RFC3339 UTC(`Z`), ±5분 |
| `X-Auth-Version` | — | v2 필수 | 정확히 `2` |
| `X-Nonce` | `fds_auth_nonces.nonce_hash` | v2 필수 | 16 random bytes canonical base64url-no-padding(22자); raw nonce 미저장, 기본 TTL 15분(`>2×skew`) |
| `X-Signature` | — | HMAC 인증 시 필수 | `hmac-sha256=...` |
| `traceId`(`X-Trace-Id`) | `fds_audit_logs.trace_id` | 선택 | 관측성 전파(설계서 §17). singleton이지만 고정 9-key scopeContext 밖 |
| `correlationId`(`X-Correlation-Id`) | 메시지/로그 계보 | 선택 | 관측성 전파. 고정 9-key scopeContext와 현재 singleton 거부 목록 밖 |

- 외부 machine request의 `dataScope`는 `X-Data-Scope`, Admin 위임의 `dataScope`는 bo-api 운영자 토큰 claim에서 전달된다. bo-api는 claim 집합을 fds-svc 조회의 강제 IN 필터로 주입한다(저장 격리 아님, 조회·조치 권한 필터). `X-Trace-Id`/`X-Correlation-Id`는 관측성 값이며 v2 고정 9-key context에는 추가하지 않는다.
- BO의 사람 capability(`SFDS_*`)는 bo-api가 먼저 검사하며 본 표의 engine OAuth2/machine scope(`fds:*`)와 별도 계층이다. `fds:*`를 가진 credential만으로 브라우저 운영자 기능을 열 수 없고, BO 역할명을 engine scope로 대체하지도 않는다. path/query/body target은 bo-api의 인증 tenant/workspace와 먼저 일치시킨 뒤 선택한 target만 위임 header로 전달한다.
- bo-api target의 `tenantId`/`workspaceId`는 trim 후 최대 64자, `X-Trace-Id`는 최대 128자이며 제어문자(CR/LF 포함)를 금지한다. header를 검증한 뒤에만 request context/MDC를 만들고 path·query·body target을 비교하므로 oversized/control input은 downstream·감사 write 전에 400으로 끝난다. signed `X-User-Subject`는 공통 filter의 128자/제어문자 검증을 통과한 값만 verified attribute로 승격한다(§2.1, 공통 정본).

### 2.3 OAuth2/machine scope (설계서 §12.8, `fds_api_credentials.scopes`)
`fds:event:write` · `fds:decision:evaluate` · `fds:case:read` · `fds:case:update` · `fds:evidence:export` · `fds:rule:simulate` · `fds:admin:source-system` · `fds:admin:rule` · `fds:admin:group` · `fds:admin:credential` · `fds:action:write` · `fds:internal:customer-profile:write`

`fds:internal:customer-profile:write`는 AML CDD projection 전용 최소권한 scope다. BO→FDS machine
credential은 앞의 운영 typed API 9종(`case:read/update`, `action:write`, `evidence:export`,
`rule:simulate`, admin 4종)과 exact 일치하며 `event:write`, `decision:evaluate`, 내부 profile scope를
포함하지 않는다. 전체 정본은 **외부/운영 11종 + internal profile 1종 = 총 12종**이다.

권한 부족 → `403 FDS-AUTHZ-001`. scope 불일치 → `403 FDS-AUTHZ-002`. cross-workspace 접근 차단 → `403 FDS-AUTHZ-003`.

---

## 3. 횡단 규약

### 3.1 버저닝
- base path `/api/v1`. 하위호환 깨는 변경은 `/api/v2`로 분기. 응답 헤더 `X-Api-Version: v1`.

### 3.2 페이지네이션·정렬·필터 (목록 GET 공통)
| 파라미터 | 타입 | 기본 | 설명 |
|---|---|---|---|
| `page` | int | 0 | 0-base 페이지 |
| `size` | int | 20 (max 200) | 페이지 크기 |
| `sort` | string | 엔드포인트별 | `field,asc|desc` (예: `createdAt,desc`) |
| `from` / `to` | ISO-8601 | — | 기간 필터(`occurredAt`/`createdAt` 기준) |

응답 envelope:
```json
{ "content": [ ... ], "page": 0, "size": 20, "totalElements": 134, "totalPages": 7, "sort": "createdAt,desc" }
```

### 3.3 멱등성 (설계서 §12.8 idempotency store ↔ `fds_idempotency_keys`)
- `POST /events`, `POST /decisions/evaluate`, `POST /cases/{caseId}/actions`는 `Idempotency-Key` 필수.
- 동일 `(tenantId, workspaceId, scope, idempotencyKey)` 재요청 → 저장된 결과 재반환(`200`/`201` 동일 body), 신규 처리 없음. 응답 헤더 `Idempotency-Replayed: true`.
- 비동기 큐 적재 엔드포인트(`POST /fds/events`·`:batch`)의 **신규 수신 성공코드는 `202 Accepted`**(큐 적재 후 후속 처리). 멱등 재반환만 `200`/`201`이다(§5.2·§4.1). 연동(integration) 시퀀스의 신규=202/멱등=200·201과 정합.
- key 충돌이지만 payload가 다르면 → `409 FDS-IDEMPOTENT-CONFLICT`.

### 3.4 표준 에러 모델 (RFC7807 호환 + 도메인 코드)
```json
{
  "type": "https://errors.fds.example/FDS-VALIDATION-001",
  "code": "FDS-VALIDATION-001",
  "title": "Invalid request",
  "status": 400,
  "detail": "transaction.amount must be a non-negative decimal",
  "traceId": "8f3c...",
  "errors": [ { "field": "transaction.amount", "reason": "NEGATIVE" } ]
}
```
- 전체 에러 본문은 PII 미노출(마스킹된 field path만).
- **evidence export at-rest 변조 fail-closed(P0-12)**: `GET /exports/{exportId}/download` 가 stored `artifact_bytes` 를 serve 하기 전 `object_checksum == SHA-256(stored bytes)` 재계산·비교 + `manifest_hash` 존재를 검증하며, 불일치 시 신규 에러코드를 도입하지 않고 **기존 `409 FDS-APPROVAL-PAYLOAD-CHANGED` 코드를 재사용**("built/served content hash ≠ approved hash" 계열)해 차단한다(§4.5). (참고: aml 은 전용 `AML.EXPORT_TAMPER` 를 쓰지만 FDS 는 기존 코드 재사용 — 혼동 금지.)
- **`422 FDS.TENANT_CURRENCY_HISTORY_LOCKED`**(다통화, PLAN 20260818 U17): `POST .../tenants/{tenantId}/compliance/regulatory-currency:change`(§4.8a)가 거래성 이력 보유 테넌트의 `regulatory_currency` 전환을 fail-closed 로 거부할 때 반환한다. `{code, title, status, detail, timestamp}` 형태(다른 `FDS-*` 코드와 달리 `FDS.` 점 표기 — `TenantAdminController` 코드=truth).

### 3.5 hanpass-ph 채널·eventType taxonomy·phpEquivalent (코드 정본)

본 절은 `IngestEventRequest`/`EvaluateRequest`가 운반하는 hanpass-ph 거래 분류를 확정한다. 정본 = `com.aegis.fds.domain.enums.ChannelType`·`EventFamily` + Flyway `V17`/`V20`/`V22` 데모 룰.

#### 3.5.1 채널 5유형 (`ChannelType`, `channel.channelType`)
hanpass-ph가 운영하는 거래 채널은 다음 5종이다(`ChannelDto.channelType`·`fds_rules.channel_scope`·decision 필터 `channelType`에 공통 적용).

| `channelType` | 거래유형 | 위험 도메인(`TransactionDomain`) | 소스 시스템(§4.8) |
|---|---|---|---|
| `CROSS_BORDER_REMIT` | 해외송금 | `OTHER` | `remit-svc` |
| `DOMESTIC_REMIT` | 국내송금 | `DOMESTIC_TRANSFER` | `domestic-svc` |
| `CASH_IN` | 월렛충전(top-up) | `WALLET` | `walletchg-svc` |
| `WALLET_PAYMENT` | 월렛결제 | `WALLET` | `wallet-svc` |
| `WALLET_WITHDRAWAL` | 월렛출금 | `WALLET` | `wallet-svc` |

> `ChannelType`은 코드상 닫힌 enum(`fromCode`로 해석)으로 비-hanpass 채널 코드(`CARD_PRESENT`/`CARD_NOT_PRESENT`/`ATM`/`PG_PAYMENT`/`CRYPTO_*`/`EXCHANGE_TRADE`/`TRADE_PAYMENT`/`*_ECOMMERCE_*`/`MARKETPLACE_*`/`B2B_*` 등)를 enum 멤버로 보존하나 **hanpass-ph 운영 대상은 위 5종뿐**이다. 데모 룰 `V22`는 hanpass에 없는 카드결제 룰(`CARD_NOT_PRESENT`)을 `DISABLED`로 비활성한다(행 보존, 발화 중지).

#### 3.5.2 eventType taxonomy (`eventType` = `<family>.<verb>`)
`eventType`은 `<family>.<verb>` 형식이며 family(접두)는 ingest 파이프라인이 `event_type`에서 파생해 `fds_canonical_events.event_family`(`EventFamily`)에 저장한다(인바운드 필드 아님). hanpass-ph 결제 taxonomy family는 **`remit`/`domestic`/`wallet`** 3종이다.

| `eventType` 예시 | `EventFamily` | 채널 매핑 |
|---|---|---|
| `remit.transfer.requested` | `REMIT` | `CROSS_BORDER_REMIT` |
| `domestic.transfer.requested` | `DOMESTIC` | `DOMESTIC_REMIT` |
| `wallet.charge.requested` | `WALLET` | `CASH_IN` |
| `wallet.pay.requested` | `WALLET` | `WALLET_PAYMENT` |
| `wallet.withdraw.requested` | `WALLET` | `WALLET_WITHDRAWAL` |

> `EventFamily`의 `AML`/`CASE` family는 내부 생성/aml-svc 위임 분류로 **외부 connector ingest 불가**(`isExternallyIngestable()=false`). 비-hanpass family(`authorization`/`settlement`/`trade`/`invoice`/`order`/`seller`/`market` 등)는 enum에 잔존하나 hanpass-ph는 미수신.

#### 3.5.3 phpEquivalent 룰 feature (PHP 환산 임계)
hanpass-ph 금액 임계 룰은 서버 파생 PHP 규제금액의 legacy alias `transaction.phpEquivalent`로 평가한다. 같은 값은 `transaction.amountBase`와 전 통화 `transaction.baseEquivalent`에도 노출되며 canonical payload 환산값은 읽지 않는다. 비PHP는 PHP alias를 노출하지 않는다. 파생 실패 시 모두 미노출(fail-safe).

| 채널(`channel.type`) | feature | 임계(`transaction.phpEquivalent`) | `decisionOutcome` |
|---|---|---|---|
| `CROSS_BORDER_REMIT` | `transaction.phpEquivalent` | `≥ 280000` | `REVIEW` |
| `CASH_IN` | `transaction.phpEquivalent` | `≥ 560000` | `BLOCK` |
| `DOMESTIC_REMIT` | `transaction.phpEquivalent` | `≥ 112000` | `REVIEW` |
| `WALLET_PAYMENT` | `transaction.phpEquivalent` | `≥ 168000` | `REVIEW` |
| `WALLET_WITHDRAWAL` | `transaction.phpEquivalent` | `≥ 84000` | `CHALLENGE` |

> **룰팩 18종 도달 가능성(2026-08-23).** `XLS-01`(ATM 2곳)은 별도 ATM 채널을 합성하지 않고 `WALLET_WITHDRAWAL`을 `channel.type`과 `channelScope` 양쪽에 사용한다. 같은 주체의 1시간 내 `merchantRef` distinct count 2에서 REVIEW, 1에서는 미발동한다. 동명 ACTIVE 정의가 구 비canonical 계약이면 `/admin/fds/rules` REST 상태기계로 canonical replacement를 생성·시뮬레이션·4-eyes 활성화한 후 구 정의를 disable/archive한다.
| `DOMESTIC_REMIT` (분할입금) | `velocity(count, counterparty, 24h)` | `≥ 5` | `REVIEW` |

> 기존 PHP 룰 DSL은 `transaction.phpEquivalent` alias를 유지하고, 비PHP profile-authored 룰은 `transaction.baseEquivalent`를 사용한다. 두 alias와 `transaction.amountBase`의 값 원천은 서버 파생 `amount_base` 하나다.

---

## 4. 엔드포인트 표

### 4.1 Ingest API (외부) — `fds:event:write`
| 메서드 | 경로 | 설명 | 인증/scope | 멱등 | 4-eyes |
|---|---|---|---|---|---|
| POST | `/api/v1/fds/events` | canonical event 수신·저장(`fds_canonical_events` insert) **직후 ACTIVE inline 룰을 동기 평가**해 응답에 판정 요약 `decision`(additive)을 동봉한다. 신규=**202 Accepted**(수리+판정 동봉), 멱등 재반환=200/201(§5.2). 평가 실패 시 인입 성공은 유지하고 `decision=null`(fail-safe). 거절 없음 원칙 불변 — 판정 동봉은 표시이지 인입 거부가 아니다(20260718 사용자 지시 재개정, aegis-aml `docs/aml-data.md` §11.7.3) | API Key+HMAC / `fds:event:write` | 필수 | — |
| POST | `/api/v1/fds/events/evaluate` | canonical event 저장 후 ACTIVE inline 룰을 즉시 평가해 ingest 상태 + `DecisionResponse` 반환. 신규/멱등 replay=200, reject/duplicate는 기존 ingest HTTP 의미 유지. `/events` 가 이미 동기 평가해 동일 이벤트에 inline 결정을 남긴 경우 그 결정을 **재사용**한다(신규 decision 행 생성 금지, event-scope 재사용 게이트) | API Key+HMAC / `fds:event:write` + `fds:decision:evaluate` | 필수(EVENT/DECISION scope 분리) | — |
| POST | `/api/v1/fds/events:batch` | 다건 event 수신(최대 500). 신규=**202 Accepted**, per-item 응답에 `decision`(additive) 동기 동봉 — 단건 `/events` 와 동형(항목별 순차 평가, 프리체크 reject 항목은 `decision=null`) | `fds:event:write` | 필수 | — |
| GET | `/api/v1/fds/events` | canonical event 목록 조회(필터: `sourceSystem`,`eventType`,`eventFamily`,`channelType`,`subjectRef`,`transactionRef`,`from`,`to` · 페이지네이션). 거래 인입 내역(원본 이벤트) 브라우즈 — 결정·케이스 화면의 역참조 목록. 마스킹 | `fds:case:read` | — | — |
| GET | `/api/v1/fds/events/{eventId}` | event 단건 상태·정규화 결과·canonicalPayload 조회(마스킹) | `fds:case:read` | — | — |

### 4.2 Decision API (외부) — `fds:decision:evaluate`
| 메서드 | 경로 | 설명 | 인증/scope | 멱등 | 4-eyes |
|---|---|---|---|---|---|
| POST | `/api/v1/fds/decisions/evaluate` | 승인 전 실시간 FDS 판단. `fds_decisions`+`fds_decision_reasons` 생성 | API Key+HMAC/mTLS · `fds:decision:evaluate` | 필수 | — |
| GET | `/api/v1/fds/decisions/{decisionId}` | decision 단건(증적: matched_rules·feature_snapshot 요약) | `fds:case:read` | — | — |
| GET | `/api/v1/fds/decisions/{decisionId}/evidence-transactions?ruleId=&page=&size=` | **판정 발동 룰 근거 거래 전수 페이징**(요구2 — 판정 근거 거래 전수 표시). 발동 룰의 evidence 윈도우(dimension + rolling window + channel scope)를 해소해 근거 거래 **전체**를 페이징(캡된 `feature_snapshot` evidence 는 미절단). `ruleId` 미지정 시 대표 룰(최심각 outcome, A12) 사용. `size` 기본 50·어댑터 200 클램프(A8). 미지 decision 404. 응답 DTO §5.4a `DecisionEvidenceTransactionsResponse` | `fds:case:read` | — | — |
| GET | `/api/v1/fds/decisions` | decision 목록(필터 11종: `transactionRef`,`subjectRef`(대상 토큰),`rule`(적중 룰 id/이름 부분일치 — 대소문자 무시. fds-svc 는 숫자 룰 번호가 없어 목록 행에 표시되는 룰 코드/이름 문자열로 검색),`decision`,`channelType`,`currency`,`amountMin`,`amountMax`,`sendCountry`,`receiveCountry`,`from`,`to` · 페이지네이션). 채널/통화/금액/corridor 축은 연결 canonical event LEFT JOIN 파생(DB §5.10·§5.5) | `fds:case:read` | — | — |

> 장애 정책(D-14): `fds_source_systems.fail_policy`(`FAIL_CLOSED`/`FAIL_OPEN`/`CASE_ONLY`)에 따라 평가 불가 시 응답 `decision` 결정. `CASE_ONLY`는 `REVIEW`+case 후보.

### 4.3 Action API (외부/위임) — `fds:action:write`
| 메서드 | 경로 | 설명 | 인증/scope | 멱등 | 4-eyes |
|---|---|---|---|---|---|
| GET | `/api/v1/fds/actions` | action outbox 목록(`fds_actions`) 조회. 필터: `decisionId`,`caseId`,`actionType`,`status`,`targetSystem`,`targetRef`,`limit`(최대 200), 최신순 | `fds:case:read` | — | — |
| GET | `/api/v1/fds/actions/{actionId}` | action outbox 상태(`fds_actions.status`) 조회 | `fds:case:read` | — | — |
| POST | `/api/v1/fds/cases/{caseId}/actions` | case 기반 수동 action 상신(outbox 등록) | `fds:action:write` | 필수 | 자금/규제성 action 필수 |

> 자금성(`HOLD_FUNDS`/`RELEASE_HOLD`/`CANCEL_TRANSACTION`/`REQUEST_REVERSAL`/`HOLD_SETTLEMENT`) 및 규제성(`REGULATORY_REPORT`/`OPEN_AML_CASE`) action은 `fds_approval_requests`를 생성하고 `status=APPROVAL_REQUIRED`로 hold. 승인 완료 후 relay(§8).

### 4.3a Customer Profile Internal API (AML CDD projection)

| 메서드 | 경로 | 설명 | 인증/격리 | 멱등 |
|---|---|---|---|---|
| PUT | `/internal/v1/fds/customer-profiles/{memberRef}` | AML `customer.cdd.completed`의 PII-safe 프로필을 `fds_subjects`에 upsert | API key + HMAC wire v2-only, exact `(tenant,workspace)` credential, `fds:internal:customer-profile:write`, signed `X-Internal-Service=aml-svc`, signed `X-Data-Scope` | `(tenant,workspace,memberRef)` upsert + AML outbox payload hash |

요청 `CustomerProfileSyncRequest`: `sourceEventId`(필수), `occurredAt`(필수), `nationality`(ISO2), `country`(ISO2), `registeredAt`, `kycCompletedAt`, `kycLevel`, `dataScope`. body `dataScope`는 signed `X-Data-Scope`와 exact 일치해야 한다. 원문 이름·DOB·문서 식별자는 금지한다. `kycCompletedAt < registeredAt`은 400 `FDS-VALIDATION-001`. null은 기존값 보존, CDD의 명시 non-null 값은 최신값으로 갱신하며 `(occurredAt, sourceEventId)`가 현재 버전보다 오래된 역전 도착은 204 no-op 처리한다(DB V11). unsigned/spoofed caller, signature/context/body tamper는 controller 전에 401이고 profile row를 변경하지 않는다. valid signature의 scope 부족은 nonce 소비 뒤 403이다.

### 4.4 Case API (외부/위임) — `fds:case:read` / `fds:case:update`
| 메서드 | 경로 | 설명 | scope | 4-eyes |
|---|---|---|---|---|
| GET | `/api/v1/fds/cases` | case 목록(필터: `status`,`caseType`,`priority`,`assignedTo`,`from/to`,`slaBreached`(boolean — SLA 기한 초과만)) | `fds:case:read` | — |
| GET | `/api/v1/fds/cases/{caseId}` | case 단건 + 요약 | `fds:case:read` | — |
| GET | `/api/v1/fds/cases/{caseId}/events` | case timeline(`fds_case_events`, append-only) | `fds:case:read` | — |
| PATCH | `/api/v1/fds/cases/{caseId}` | status/priority/assignee 변경 | `fds:case:update` | `INTERNAL_AUDIT` 종결 시 필수 |
| POST | `/api/v1/fds/cases/{caseId}/assign` | 담당자 배정 | `fds:case:update` | — |
| POST | `/api/v1/fds/cases/{caseId}/close` | case 종결(`closeReason` **필수** — enum 8종 §5.5 + 상세 메모 선택) | `fds:case:update` | 내부감사·규제 case 필수 |
| POST | `/api/v1/fds/cases/{caseId}/feedback` | false positive feedback 등록 | `fds:case:update` | — |

> hanpass-ph AML 위임 case(`caseType IN (AML_REVIEW, REGULATORY_REPORT)`)는 fds-svc가 origin만 보유. 본 조사·STR/CTR 처리·종결은 aml-svc API(별도 명세). 응답에 `amlCaseRef`(cross-ref) 노출.

> **bo-api 케이스 종결 위임 계약(1클릭 종결 — 코드=truth, `FdsDecisionCaseStubService.closeCase`, 라이브 검증 7fca1a0).** bo-web `/fds/cases` 의 "종결"은 bo-api BFF 계약 `CaseCloseRequest{closeReason, memo}`(사유 계열 8종 §5.5 검증, 위임·스텁 공통)만 받는데, 엔진 `POST /fds/cases/{caseId}/close` 는 **terminal `closedStatus` 가 필수**(`@NotBlank`)이고 엔진 상태기계는 종결 전 **`PENDING_APPROVAL`(종결상신) 경유가 필수**(설계서 §11.6 전이표)다. 따라서 bo-api 위임 경로가 (1) `closeReason` 계열에서 canonical `closedStatus` 를 파생해 동봉하고 — **`FP_*`→`CLOSED_FALSE_POSITIVE`(오탐종결)·`CONFIRMED_*`→`CLOSED_CONFIRMED`(사기확정종결)·`ESCALATED_AML`→`CLOSED_REPORTED`(보고후종결·AML이관)·`OTHER`→확정 계열 보수 기본값(`CLOSED_CONFIRMED`)**(DB §4.11), (2) 현재 상태가 상신 전(`OPEN`/`ASSIGNED`)이면 `PATCH status=IN_REVIEW`→`PATCH status=PENDING_APPROVAL` 을, `IN_REVIEW`/`ESCALATED` 면 `PENDING_APPROVAL` 을 **자동 선행**해 화면 "종결" 1클릭 의도를 유지한다(그 외 불법 전이는 엔진 409 그대로 표면화). 종결 자체는 `CASE_CLOSE` 4-eyes(승인선 `COMPLIANCE_MANAGER`, §8)라 응답은 `pendingApproval` 이면 `SUBMITTED`(종결상신), 아니면 `CLOSED`. 비운영(비위임) 스텁 경로는 `PENDING_APPROVAL` 로 두고 `CLOSED_<closeReason>` 자체 표기를 유지(승인 시점 반영).

> **CASE_CLOSE 결재/반려 상태전이(P0-10, 코드=truth — `CaseWorkflowService`·설계서 §11.5·§11.6.1).** 케이스 종결(`POST /fds/cases/{caseId}/close`)은 `PENDING_APPROVAL`(종결상신) 경유가 필수이고 `CASE_CLOSE` 4-eyes(`COMPLIANCE_MANAGER`, §8)로 게이트된다. (1) **활성 종결 승인 최대 1개** — 케이스가 이미 `PENDING_APPROVAL`(종결상신 계류) 인데 다시 close 하면 승인을 쌓지 않고 `409 FDS-APPROVAL-DUPLICATE`로 거부한다(애플리케이션 가드 `findActiveBySubject` + DB 부분 유니크 인덱스 `uk_fds_approval_pending_case_close` §5.23이 동시 요청 경쟁까지 방어). (2) **반려 시 직전 상태 복구** — `PENDING_APPROVAL` 로 전이하기 직전 상태를 `fds_cases.previous_status`(DB §5.13)에 보존해 두고, 종결 승인이 **반려**되면 케이스가 `PENDING_APPROVAL` 에 고착되지 않고 직전 상태(`IN_REVIEW`/`ESCALATED`)로 복구되어 **재조사·재상신**이 가능하다(반려 시 직전이 `ESCALATED` 였으면 `ESCALATED` 로 복원, 아니면 `IN_REVIEW`). (3) **타임라인 기록** — maker의 close 상신은 `APPROVAL` 이벤트로, checker의 반려는 `STATUS_CHANGE` 이벤트(`rejected=true`·`rejectReason`·`approvalRequestId`·`checker=actor`)로 `fds_case_events` 에 append 한다.

> **bo-api 재오픈 exact capability**: 일반 case patch의 진입 capability는 `SFDS_CASE:OPERATE`다. local demo 경로는 현재 상태를 같은 store에서 읽을 수 있으므로 실제 `CLOSED_*→IN_REVIEW` 재오픈에만 추가 `SFDS_CASE:APPROVE`·사유·closer≠actor를 강제한다. 반면 engine 위임 경로는 현재 FDS HMAC wire에 BO 사람 capability assertion이 없고 GET→조건부 PATCH는 TOCTOU가 되므로, P0-04에서 engine 원자 검증이 추가되기 전까지 **요청 target `status=IN_REVIEW` 전부**를 보수적으로 `SFDS_CASE:APPROVE`로 게이트한다. 권한 실패는 사전 GET 없이 downstream PATCH·local mutation 전에 끝난다.

### 4.5 Evidence API (외부) — `fds:evidence:export`
| 메서드 | 경로 | 설명 | scope | 4-eyes |
|---|---|---|---|---|
| GET | `/api/v1/evidence/fds/customer-profiles/{memberRef}` | FDS에 저장된 AML CDD 비-PII 프로필 read-back. 응답은 `{subjectRef,nationality,country,registeredAt,kycCompletedAt,kycLevel,dataScope}` exact allowlist이며 행 부재는 404. 신고소득·성명·DOB·신분키·raw payload는 미노출 | `fds:case:read` | — |
| GET | `/api/v1/evidence/fds/cases/{caseId}/timeline` | case 증적 timeline | `fds:evidence:export` | — |
| GET | `/api/v1/evidence/fds/reports/decisions` | 기간별 decision 리포트(`from`,`to`) | `fds:evidence:export` | — |
| GET | `/api/v1/evidence/fds/reports/rule-hits` | 기간별 룰 hit 리포트(`from`,`to`, `totalDecisions`, `hitsByRuleId{firedCount,blockedOrHeldCount,caseCount,falsePositiveCount}`) | `fds:evidence:export` | — |
| POST | `/api/v1/evidence/fds/exports` | evidence export 요청(`fds_evidence_exports`) | `fds:evidence:export` | 최종본(`export_kind` 제출용) 필수 |
| GET | `/api/v1/evidence/fds/exports/{exportId}` | export 상태·manifest hash | `fds:evidence:export` | — |
| GET | `/api/v1/evidence/fds/exports/{exportId}/download` | 생성 파일 다운로드(감사 기록). **P0-12 불변**: 저장된 `artifact_bytes` 를 그대로 serve(재렌더 금지)하고 `object_checksum==SHA-256(stored bytes)` 재계산·비교 + `manifest_hash` 존재를 검증, 불일치=at-rest 변조로 차단(409 `FDS-APPROVAL-PAYLOAD-CHANGED`)+`EXPORT_TAMPER` 감사 | `fds:evidence:export` | — |

> 이 표의 7개 endpoint는 모두 FDS servlet machine-auth filter 적용 대상이며, 기존 FDS route의
> credential/service v1/v2 이중 전환을 유지한다. API key/HMAC 인증 실패는 controller 전 401,
> customer-profile read는 `fds:case:read`, 나머지 evidence/export 경로는 credential에 `fds:evidence:export`가 없으면 403이다. export POST/download 감사 actor는 signed
> `X-User-Subject`의 verified request attribute에서만 파생한다.

> **불변 evidence 다운로드 무결성(P0-12, 코드=truth — `EvidenceExportService.download`).** download 는 READY 시 고정된 `artifact_bytes`(DB §5.31)를 재렌더 없이 그대로 serve 하고, serve 전 (1) `object_checksum == SHA-256(stored bytes)` byte-level 재계산·비교 (2) `manifest_hash` 존재를 검증한다. 원천 업무 row(`query_params` 등)가 바뀌어도 다운로드 bytes·hash 는 불변이다. **주의**: FDS 는 manifest_hash 를 stored bytes 에서 재유도하지 않는다 — manifest_hash 는 **논리 콘텐츠(canonical logical content + `export_format` enum) 위 SHA-256**(POI/OpenPDF 바이너리 메타 비결정성 배제, §16.4 정본)이고 stored bytes 의 무결성 앵커는 byte-level `object_checksum` 이다(두 앵커는 별개). 불일치 = at-rest 변조 → `ExportTamperException` 으로 차단(§3.4 **409 `FDS-APPROVAL-PAYLOAD-CHANGED`** 기존 코드 재사용, 신규 에러코드 없음)+`EXPORT_TAMPER` 감사(tamper alert). **V21 이전(pre-V21) row 는 stored bytes 가 없어 1회 결정적 render 폴백**(하위호환). FDS export 는 현재 메타데이터 렌더 수준이며 실 decision/case/timeline row 포함은 **phase-2 BLOCKED**.

### 4.6 Rule / Simulation Admin API (위임) — `fds:admin:rule` / `fds:rule:simulate`
| 메서드 | 경로 | 설명 | scope | 4-eyes |
|---|---|---|---|---|
| GET | `/api/v1/admin/fds/rule-sets` | rule set 목록(`fds_rule_sets`) | `fds:admin:rule` | — |
| GET | `/api/v1/admin/fds/rules` | rule 목록(필터: `ruleSetId`,`status`,`channelScope`,`decisionOutcome`,`evaluationMode`,`ruleNo`(텍스트검색) — PRD §6.1 BR-001 5축). **`status` 미지정 시 `ARCHIVED` 기본 제외**(이력은 `status=ARCHIVED` 명시 조회로만 노출 — 룰 체계 개편(PLAN 20260717 U-F5), 사용자 지시로 룰 전량 대체) | `fds:admin:rule` | — |
| GET | `/api/v1/admin/fds/rules/{ruleId}` | rule 단건 상세. 응답 `ruleJson`은 원본 `valueRef`/`groupRef`를 유지하고 BO 표시용 현재 `value`/`group`을 보강한다. | `fds:admin:rule` | — |
| POST | `/api/v1/admin/fds/rules` | rule 초안 생성(`status=DRAFT`) | `fds:admin:rule` | — |
| PUT | `/api/v1/admin/fds/rules/{ruleId}` | rule 수정(초안) | `fds:admin:rule` | — |
| POST | `/api/v1/admin/fds/rules/{ruleId}/activate` | rule 활성화 상신(`RuleActionRequest`, inline rule은 simulationId 필수) | `fds:admin:rule` | **필수** |
| POST | `/api/v1/admin/fds/rules/{ruleId}/disable` | rule 비활성 | `fds:admin:rule` | tenant policy |
| POST | `/api/v1/admin/fds/rules/{ruleId}/archive` | **룰 아카이브(삭제, terminal, 신규 — PLAN 20260717 U-F5, 사용자 지시로 F-005 해제 범위 내 신설).** `RuleStatus.allowedTransitions()`(`domain/enums/RuleStatus` — `DRAFT｜DISABLED→ARCHIVED`, 그 외 `409 FDS-STATE-CONFLICT`) 준수. §11.6.5 는 상태기계만 정의하고 전이 API·4-eyes 여부는 기존 설계 미정의였다 — **가정 A8(사용자 승인 완료 20260717)**: disable 전례와 동형으로 4-eyes 아닌 즉시 실행(엔진 scope는 disable과 동일 `fds:admin:rule`, bo-api 위임 scope는 `SFDS_RULE:OPERATE`), 감사 이벤트 `RULE_ARCHIVE` 기록. `ACTIVE` 룰은 disable 선행 필요(전이 규칙 그대로) | `fds:admin:rule` | 없음(disable 전례 동형, A8) |
| POST | `/api/v1/admin/fds/rules/{ruleId}/rollback` | 버전 rollback(`fds_rule_versions`, RuleActionRequest.reason 필수) | `fds:admin:rule` | **필수** |
| GET | `/api/v1/admin/fds/rules/{ruleId}/versions` | rule version 이력 | `fds:admin:rule` | — |
| GET | `/api/v1/admin/fds/rules/{ruleId}/params` | rule 튜닝 변수(파라미터) 목록 + pending `RULE_PARAM` 결재 id(`ruleJson` 리프값 파생 카탈로그 + `fds_rule_param_overrides` override 반영) | `fds:admin:rule` | — |
| POST | `/api/v1/admin/fds/rules/{ruleId}:update-params` | rule 변수(임계값) 변경 상신(`UpdateRuleParamsRequest`, unknown-key·[min,max]·정수전용 검증 후 `RULE_PARAM` 결재 생성). 즉시 반영 아님 — 202 Accepted + `approvalRequestId`, 승인 후 override set 원자 적용 | `fds:admin:rule` | **필수** |
| POST | `/api/v1/admin/fds/rules/simulations` | rule simulation 실행(예상 hit rate) | `fds:rule:simulate` | — |
| GET | `/api/v1/admin/fds/rules/simulations/{simulationId}` | simulation 결과 | `fds:rule:simulate` | — |
| POST | `/api/v1/admin/fds/rules/recommendations` | 룰 추천(목표 적중률 → 단일 피처 임계값 역산·엔진 재평가 검증). read-only(결재 불필요), 집계·임계값만 반환(raw PII/피처값 미반환) | `fds:rule:simulate` | — |
| GET | `/api/v1/admin/fds/feature-catalog` | feature catalog(no-code builder) | `fds:admin:rule` | — |

### 4.7 Risk Group Admin API (위임) — `fds:admin:group`
| 메서드 | 경로 | 설명 | scope | 4-eyes |
|---|---|---|---|---|
| GET | `/api/v1/admin/fds/risk-groups` | group 목록(`fds_risk_groups`) | `fds:admin:group` | — |
| POST | `/api/v1/admin/fds/risk-groups` | group master create-only 원자 삽입. 동일 `(tenant_id, workspace_id, group_id)`가 이미 존재하면 `409 FDS-STATE-CONFLICT`이며 기존 master/member/audit는 무변이. `group_id`·`group_type`은 생성 후 immutable | `fds:admin:group` | — |
| PUT | `/api/v1/admin/fds/risk-groups/{groupId}` | group 마스터 수정/비활성 상신(`display_name` 수정·`active=false` 정의 삭제). `group_id`·`group_type` 변경 불가(BR-001/BR-002), 비활성은 멤버 0 선결. 즉시 반영하지 않고 현재 master projection+`approvalRequestId`/`APPROVAL_REQUIRED`를 202로 반환 | `fds:admin:group` | **필수** |
| GET | `/api/v1/admin/fds/risk-groups/{groupId}/members` | member 목록 | `fds:admin:group` | — |
| POST | `/api/v1/admin/fds/risk-groups/{groupId}/members` | member 추가(watchlist/denylist 반영). **즉시 반영(200, `GroupMemberMutationResponse`)** — 결재 없이 동기 mutation. 엔진은 `memberRef` 를 불투명 문자열로 저장·대조하며(in_group 은 memberKind 무관), **전화·계좌 원문의 해시 변환은 bo-api 위임 경로**(`displayKind ∈ {PHONE, ACCOUNT}` + 원문 → aml-data §11.7.9 `SHA-256(숫자만)` 으로 서버측 치환, 엔진 body·멱등키·감사에 원문 부재, 20260906) 가 담당한다 | `fds:admin:group` | — |
| DELETE | `/api/v1/admin/fds/risk-groups/{groupId}/members/{memberRef}` | member 제거. **즉시 반영(200, `GroupMemberMutationResponse`)** — 결재 없이 동기 mutation | `fds:admin:group` | — |
| POST | `/api/v1/admin/fds/merchants/{merchantRef}/normalize` | high-risk merchant 정상화 상신(설계서 §11.5, `subjectKind=MERCHANT_NORMALIZE`, subjectRef=`merchant_ref`) | `fds:admin:group` | **필수** |

> **위험그룹 master 4-eyes·감사(P0-03, 코드=truth)**: `POST /risk-groups`만 master를 즉시 생성하고 save 성공 뒤 `GROUP_CREATE`를 기록한다. `PUT /risk-groups/{groupId}`는 `GROUP`/`RISK_MANAGER` 결재와 immutable payload hash를 staged할 뿐 master를 수정하거나 `GROUP_UPDATE`를 기록하지 않는다. 다른 checker가 승인해 rename 또는 멤버 0인 `active=false` 정의 삭제를 실제 적용한 뒤에만 `GROUP_UPDATE`를 append하며, 반려·자기승인·business 재검증 실패는 master를 보존하고 새 성공 감사를 만들지 않는다. business 재검증 실패만 `EXECUTION_FAILED`로 확정한다. master save/delete 또는 audit append 예외는 승인 트랜잭션 밖으로 전파하여 step/status/master/audit 전체를 rollback하고 원 결재를 `SUBMITTED`·재시도 가능 상태로 유지한다. 두 이벤트의 `targetKind=RISK_GROUP`, `targetRef=group_id`다. create actor는 machine-auth가 검증한 signed end-user subject이고 update actor는 checker다. create는 request MDC trace, update는 staged causal trace 우선·부재 시 checker request MDC를 correlation으로 남긴다. 생성은 canonical after hash, 승인 적용은 before/after hash를 기록한다. 활성 hash는 `tenant|workspace|groupId|generationId|groupType|displayName`, 삭제 hash는 `DELETED|tenant|workspace|groupId|generationId|groupType`의 SHA-256이다. detail은 생성 `{action:CREATE, groupType}` 또는 승인 적용 `{action:MASTER_UPDATE, active?:false}`만 노출하여 display name 원문을 감사 payload에 복제하지 않는다. 이 row는 §4.9a 저수준 조회와 bo-api unified FDS audit에 그대로 포함된다.
>
> **위험그룹 member add/remove/extend 즉시 반영(20260720, 코드=truth — 사용자 확정: 4-eyes 생략)**: `POST`·`DELETE .../risk-groups/{groupId}/members[/{memberRef}]`는 결재를 상신하지 않고 fds-svc `RiskGroupAdminService.addMember`/`removeMember`가 row lock 후 즉시 mutation한다(add는 `fds_risk_group_members` 복합 PK upsert — 동일 `memberRef` 재호출은 만료/kind 갱신인 연장 의미론, remove는 즉시 delete). 응답은 always `200 OK` `GroupMemberMutationResponse{groupId, status="APPLIED", approvalRequestId=null, member}`(remove는 `member=null`) — `approvalRequestId`는 bo-api `EngineGroupApproval` wire 하위호환용으로 유지되나 항상 `null`이다. mutation 성공 직후 `GROUP_UPDATE` 감사(`targetKind=RISK_GROUP`, `targetRef=group_id`, `actorSubject`=요청자, `detailJson={action: ADD|REMOVE, memberKind?}`)를 append하며 canonical ADD/REMOVE payload(§5.10)의 `afterHash`를 그대로 재사용한다. `fds:admin:group` scope·bo-api `SFDS_GROUP:OPERATE` 인가는 무변경. 그룹 master(rename/비활성, `PUT .../risk-groups/{groupId}`)와 merchant normalize(`POST .../merchants/{merchantRef}/normalize`)의 4-eyes는 이 완화와 무관하게 그대로 유지된다. 배포 시점 DB에 잔존한 in-flight 멤버 결재(레거시 `GROUP`/`RISK_MANAGER` 상신)는 결재함 승인 시 여전히 실행되는 레거시 호환 경로이며, 신규 상신 경로는 제거됐다.

### 4.8 Source/Connector/Credential Admin API (위임) — `fds:admin:source-system` / `fds:admin:credential`

> **소스 시스템 카탈로그(hanpass-ph 재그라운딩, DB §5.3a)**: `source_system` 식별자는 hanpass-ph 트랜잭션 마이크로서비스(`member-svc`/`walletchg-svc`/`domestic-svc`/`remit-svc`/`wallet-svc`/`tx-history-svc`/`inbound-svc`)로 등록·예시화한다(generic `card-processor`/`core-banking`/`atm-switch` 대체). 업스트림은 `REST_PUSH`(REST sync 인입, 연동 §7.1) 기준이며, 거래 소스는 hanpass eventType taxonomy(§3.5.2)의 `*.requested`/`transaction.requested` 계열을 emit하고 `channel_type`은 소스별로 `CASH_IN`(walletchg)/`DOMESTIC_REMIT`(domestic)/`CROSS_BORDER_REMIT`(remit)/`WALLET_PAYMENT`·`WALLET_WITHDRAWAL`(wallet)/`INBOUND_REMIT`(inbound)에 대응한다. 연동 키 매핑은 연동 §7.2 정본(원문 금지·token/HMAC). **데이터 레이어 한정 — 규제(CTR/STR) 임계·기한 불변.**
>
> **BO 데모/시뮬레이터 주석**: 로컬 BO 커넥터 관리와 `tools/aml-ingest-simulator`는 FDS 탐지 결정과 AML TM의 공통 거래 payload를 한 화면에서 모니터링하기 위해 집계 connector id `HANPASS_PH`를 사용한다. 이 집계 ID는 운영 실서비스 source catalog를 대체하지 않으며, generic `atm-switch` 커넥터 seed는 사용하지 않는다.

| 메서드 | 경로 | 설명 | scope | 4-eyes |
|---|---|---|---|---|
| GET | `/api/v1/admin/fds/source-systems` | source system 목록 | `fds:admin:source-system` | — |
| POST | `/api/v1/admin/fds/source-systems` | source system 등록 | `fds:admin:source-system` | — |
| PUT | `/api/v1/admin/fds/source-systems/{sourceSystem}/mappings` | field mapping/PII allowlist 변경(`fds_schema_mappings`) | `fds:admin:source-system` | **필수** |
| PUT | `/api/v1/admin/fds/source-systems/{id}` | source system 속성·capability 매트릭스 수정(`enabled`/`schemaVersion`/ingest 설정/`failPolicy`/`capabilities`, `fds_source_systems`) | `fds:admin:source-system` | **필수** |

> **source capability read projection(P0-03, 코드=truth)**: `GET .../source-systems`의 각 `SourceSystemDto.capabilities[]`는 요청의 `(tenant_id, workspace_id, source_system)`에 저장된 실제 `fds_capabilities` desired set을 투영한다. 값이 없는 source/revoke-all 결과는 의미 있는 **명시적 JSON `[]`**이며, bo-api는 이 배열을 그대로 보존한다. `null`/필드 부재는 revoke-all로 정상화하지 않고 `502 BO-PROXY-FAILED`다. source row의 ID·displayName·ingestMode·schemaVersion·enabled·failPolicy·capabilities와 connector row의 ID·sourceSystem·connectorStatus는 필수이고 미지 enum/status도 502다. 고정 빈 배열이나 다른 tenant/workspace의 capability를 합성하지 않는다. BO `GET /api/v1/admin/fds/source-systems`는 `SFDS_CONNECTOR:READ` 또는 capability checker의 `SFDS_ACTION:APPROVE`로 조회하고, update는 기존 exact maker capability를 별도로 적용한다.

> **configured delegate response integrity(P0-03)**: bo-api의 typed FDS 위임은 HTTP 2xx라도 응답 본문이 없거나 필수 DTO/page 필드가 빠지면 `502 BO-PROXY-FAILED`로 fail-closed한다. 컬렉션의 정상 빈 결과는 명시적 JSON `[]`(page는 완전한 빈 page envelope)만 허용한다. path/body resource ID를 반환하는 단건·mutation 응답은 requested ID/parent ID와 exact 일치해야 한다. decision/event/evidence page는 requested page/size, exact total/totalPages/content count, canonical sort(`createdAt,desc`/`occurredAt,desc`)와 page 내부 시각 단조성을 검증한다. decision의 `eventId/createdAt`은 필수이며 transactionRef/subjectRef/riskScore/ruleSetVersion/expiresAt은 nullable을 보존하되 non-null 형식·범위를 검증한다. evidence의 `ruleId/ruleName/outcome/dimension` 등 §5.4a 메타는 nullable 정본을 유지하고, non-null 값과 `transactions`의 page/sort/row 필드를 검증한다. event/case/action/case-event list도 null/incomplete row를 빈 목록·현재시각 등으로 정상화하지 않는다. SourceSystem/Connector/transition/credential의 필수 시각과 enum을 검증하고, pause는 `DISABLED`, resume은 `DISABLED→HEALTHY` 또는 `HEALTHY→HEALTHY` 멱등만 성공으로 승격한다. rule-param·evidence export·connector approval·approval list/detail/decision은 UUID/enum/status/identity를 검증한 후에만 성공 감사/응답으로 승격한다. FDS audit list는 exact sort `occurredAt,desc;sourceService,asc;auditId,asc`, page metadata, batch/page-boundary 단조성과 모든 row의 `sourceService=FDS`·tenant/workspace를 재검증하여 한 row라도 foreign/malformed이면 전체 응답을 거부한다.
>
> 위험그룹 configured 응답은 `groupId`(단건·mutation은 요청 ID와 exact 일치), 알려진 `groupType`, 비공백 `displayName`/`createdBy`/`updatedBy`, 0 이상 정수 `memberCount`, parse 가능한 `createdAt`/`updatedAt`을 모두 검증한다. 목록·POST 응답에 예기치 않은 pending 메타가 있으면 거부하고, PUT 202 응답은 canonical UUID `approvalRequestId`와 exact `status=APPROVAL_REQUIRED`가 모두 있어야 한다. 누락·미지 enum·잘못된 시각·foreign ID는 local fallback으로 승격하지 않고 `502 BO-PROXY-FAILED`다. BO BFF POST는 engine availability 분기 전에 `groupId`/`groupType`/`displayName`을 nonblank·length·known enum으로 공통 검증하고, fds-svc Java `RiskGroupUpsertRequest`와 exact한 세 필드만 전송한다(`displayKind`/`active`/`reason`은 create wire에서 제외). BO BFF PUT의 `RiskGroupUpsertRequest.groupId`는 nonblank·최대 96자이며 path `groupId`와 exact 일치해야 한다. null/blank/oversize/mismatch는 engine availability 확인·HTTP 위임·local mutation보다 먼저 400으로 거부하여 downstream 호출 수를 0으로 만든다. 이 BFF 검증 뒤 fds-svc로 전달하는 engine `RiskGroupMasterUpdateRequest`는 아래 §5.18/OpenAPI대로 path를 identity 정본으로 사용하므로 body `groupId`를 다시 포함하지 않는다.
| GET | `/api/v1/admin/fds/connectors` | connector health 목록(`fds_connector_offsets`) | `fds:admin:source-system` | — |
| GET | `/api/v1/admin/fds/ingest/metrics` | REST 거래 인입 실측 집계. tenant/workspace 내 `fds_canonical_events`의 `transaction_ref IS NOT NULL` accepted row 기준 최근 24h 건수·마지막 수신·최근 60초 TPS를 source system별로 반환(§5.15a) | `fds:admin:source-system` | — |
| GET | `/api/v1/admin/fds/connectors/{connectorId}` | connector 단건 health·offset·lag·last_error 조회(`fds_connector_offsets`) | `fds:admin:source-system` | — |
| POST | `/api/v1/admin/fds/connectors/{connectorId}/pause` | connector 일시중지(`connector_status`→`DISABLED`, ingest/poll suspend) | `fds:admin:source-system` | — |
| POST | `/api/v1/admin/fds/connectors/{connectorId}/resume` | connector 재개(`connector_status`→`HEALTHY`, offset 유지 후 소비 재개) | `fds:admin:source-system` | — |
| POST | `/api/v1/admin/fds/connectors/{connectorId}/replay` | replay/reconciliation 트리거 | `fds:admin:source-system` | — |
| GET | `/api/v1/admin/fds/notify-channels` | tenant 알림 채널 목록(설계서 §13.2 alert channel — `channel`(`SLACK`/`EMAIL`/`WEBHOOK`)·`target`(채널명/주소/URL)·`events`(구독 이벤트, §9.1 webhook eventName 부분집합)). DTO §5.22, `fds_notify_channels`(DB §5.34) | `fds:admin:source-system` | — |
| PUT | `/api/v1/admin/fds/notify-channels` | tenant 알림 채널 설정 변경(전체 교체, 멱등). `SFDS_TENANT:ADMIN` 전용·감사 기록(`NOTIFY_CHANNEL_CHANGE`, PRD TNT-002 ⑤ BR-001). webhook URL 변경은 credential 서명키 정책(rotate) 연계(헤더 `X-Webhook-Url-Changed`). WEBHOOK `target`은 egress SSRF 정책(P0-17, §9) 파싱+DNS 해석 검증 통과 필수 — 위반 시 400(reason code). DTO §5.22 | `fds:admin:source-system` | — |
| GET | `/api/v1/admin/fds/credentials` | API credential 목록(secret 미노출) | `fds:admin:credential` | — |
| POST | `/api/v1/admin/fds/credentials` | credential 생성(secret 1회 반환) | `fds:admin:credential` | **필수(SECURITY_ADMIN)** |
| POST | `/api/v1/admin/fds/credentials/{credentialId}/rotate` | secret/webhook 회전 | `fds:admin:credential` | **필수(SECURITY_ADMIN)** |

> **BO maker/checker exact 매핑(P0-03)**: `PUT .../source-systems/{id}`의 `capabilities` 변경은 다른 일반 설정과 한 요청에 섞을 수 없다. `capabilities`의 **필드 존재 여부**가 operation을 결정하므로 `[]`도 유효한 revoke-all capabilities-only 요청이다. capabilities-only는 maker·checker 모두 `SFDS_ACTION:APPROVE`, 일반 설정-only(`displayName/enabled/schemaVersion/ingestMode/failPolicy`)는 maker·checker 모두 `SFDS_CONNECTOR:OPERATE`가 필요하다. field mapping `PUT .../{sourceSystem}/mappings`는 maker·checker 모두 `SFDS_MAPPING:APPROVE`다. 엔진은 `subjectKind=MAPPING`의 staged `payload_json`에 `requiredBoCapability`와 전체 desired capability set(`[]` 포함)을 함께 저장하고, 생성 뒤 변경 경로가 없는 결재 row의 불변 판정 입력으로 사용한다. bo-api checker는 이 marker를 다시 읽으며 marker가 없거나 미지 값인 legacy `MAPPING` 결재는 fail-closed한다.

### 4.8a Tenant Compliance Admin API (위임) — `fds:admin:source-system` (r11/r20 이격 — 기존 미선언 정리)

> **역전파(코드=truth, `TenantAdminController`)**: 이 서브섹션은 이전까지 문서에 선언되지 않았던 기존 compliance 라우트 2종과 다통화(법인별 자국통화, PLAN 20260818 U15/U17) 신규 2종을 **함께 일괄 선언**한다. `tenant` 리소스(§4.8·§16.0 — 목록/CRUD/온보딩)는 폐기·bo-api 소유이며, 아래는 그와 별개인 **`compliance` 서브리소스**(`compliance_policy`·`regulatory_currency` 다통화 규제 보고/평가 통화 축)만 다룬다.

| 메서드 | 경로 | 설명 | scope | 4-eyes |
|---|---|---|---|---|
| GET | `/api/v1/admin/fds/tenants/{tenantId}/compliance` | 테넌트 compliance 조회 — `compliance_policy`(엔진 source-of-truth)+`regulatory_currency`(다통화, U15 신설 필드)+읽기 전용 `deployment_model`/`onboarding_status`(bo-api 온보딩 메타 투영). 응답 `TenantMetaResponse{tenantId,displayName,tenantStatus,deploymentModel,onboardingStatus,defaultRegion,infraRef,compliancePolicy,regulatoryCurrency}` | `fds:admin:source-system` | — |
| POST | `/api/v1/admin/fds/tenants/{tenantId}/compliance/policy-pack:toggle` | 규제 팩(`compliance_policy`) 토글 4-eyes 상신(`subjectKind=POLICY_PACK`, §8). staged 값은 승인(EXECUTED) 전까지 미적용. `KR_BASE` 잠금(끄기 불가) submit 시점 강제. **EXECUTED 적용은 테넌트 행 무손실 재조립**(`regulatory_currency` 등 타 컬럼 보존, U17-5 결함 교정 반영) | `fds:admin:source-system` | **필수**(`POLICY_PACK`, 승인선 `COMPLIANCE_MANAGER`) |
| POST | `/api/v1/admin/fds/tenants/{tenantId}/compliance/regulatory-currency:change` | **다통화(법인별 자국통화) 테넌트 규제통화 전환 4-eyes 상신**(U17 신설, `subjectKind=TENANT_REGULATORY_CURRENCY`, §8). 요청 `{regulatoryCurrency(ISO 4217 대문자 3자, 필수), reason?}` — 형식 위반 400. 이력 가드: 거래성 이력 보유 테넌트는 **`422 FDS.TENANT_CURRENCY_HISTORY_LOCKED`**(fail-closed, 조용한 no-op 금지). staged 값은 승인(EXECUTED) 전까지 미적용 | `fds:admin:source-system` | **필수**(`TENANT_REGULATORY_CURRENCY`, 승인선 `COMPLIANCE_MANAGER`) |

> **BO 소비 경로(r18 이격 3 — bo-api 위임 표면 병기)**: bo-api 는 `regulatory-currency:change` 를 raw 프록시로 노출하지 않는다. `FdsTenantCompliancePolicyService#submitRegulatoryCurrencyChange`(기준통화 프로파일 apply `STEP FDS_REGULATORY_CURRENCY`, API §3.16a 위임)가 이 엔드포인트를 호출하며, BO 감사 `FDS_TENANT_REGULATORY_CURRENCY_CHANGE_SUBMITTED`(bo-api V24) + `idempotencyKey="regulatory-currency:"+tenantId+":"+통화` 를 남긴다. 엔진 미가용 시 로컬 스테이징 없이 **503 fail-closed**(`policy-pack:toggle` BO 위임 서술과 동형 — §11.5 참조).
>
> **FDS 저작 게이트(r12 Q35)**: 위 두 상신 엔드포인트는 화면 접근 게이트(`aml:admin:policy`)와 별개로, BO apply 오케스트레이션 진입 시점에 `SFDS_TENANT:ADMIN`(regulatory-currency)·`SFDS_RULE:OPERATE`(룰 파라미터) capability 를 요구한다 — 미보유 시 BO STEP 결과가 `FAILED(FDS_AUTHORITY_MISSING)` 로 fail-closed 되며 본 엔드포인트 자체는 호출되지 않는다.

### 4.9 Approval API (위임) — bo-api IAM 연계
| 메서드 | 경로 | 설명 | scope | 4-eyes |
|---|---|---|---|---|
| GET | `/api/v1/admin/fds/approvals` | 결재 대기 목록(`fds_approval_requests`). 필터: `subjectKind`(enum subject_kind 11종), `status`(enum approval_status 8종), `maker`(상신자 token=`maker_subject`). **페이지네이션 미구현 — 필터 결과 전량을 배열로 반환**(코드=truth `ApprovalAdminController.list`, 2026-09-05 대조) | `fds:case:read` | — |
| GET | `/api/v1/admin/fds/approvals/{approvalRequestId}` | 결재 단건(payload_hash 포함) | `fds:case:read` | — |
| POST | `/api/v1/admin/fds/approvals/{approvalRequestId}/approve` | 승인(checker≠maker 강제) | `fds:action:write` | maker≠checker |
| POST | `/api/v1/admin/fds/approvals/{approvalRequestId}/reject` | 반려. 대상별 원상복구 — `ACTION`: 바인딩 액션 취소 / `CASE_CLOSE`: 케이스 직전 상태 복구 / **`RULE`(활성화 상신): 룰 `PENDING_APPROVAL → DRAFT` 복귀**(재상신·아카이브 가능, 감사 `RULE_UPDATE` detail `action=REJECT`; `ROLLBACK` 상신의 ACTIVE 룰은 무변경). 2026-09-05 이전 코드는 RULE 복구가 누락돼 반려된 룰이 PENDING_APPROVAL 에 고착됐다 — 기존 고착분은 Flyway V34 가 DRAFT 로 복구(DB §8) | `fds:action:write` | — |

> 상신자(maker)와 승인자(checker)는 같을 수 없다(`SELF_APPROVAL_DISABLED`). AI agent는 maker만 가능. 운영자 IAM·승인 라인 정책은 bo-api 소유, fds-svc는 엔진 측 게이트(`fds_approval_requests`/`fds_approval_steps`)만 보유.

> **BO 결재함 exact checker 필터**: controller의 coarse 진입 조건은 지원 subject capability 중 하나 이상 보유 여부일 뿐이다. service는 엔진/로컬 row를 먼저 읽고 `subjectKind`와 immutable staged payload로 checker capability를 다시 판정한다. `ACTION→SFDS_ACTION:APPROVE`, `RULE|RULE_PARAM→SFDS_RULE:APPROVE`, `SECRET→SFDS_CONNECTOR:APPROVE`, `GROUP|MERCHANT_NORMALIZE→SFDS_GROUP:ADMIN`, `EXPORT|POLICY_PACK|TENANT_REGULATORY_CURRENCY→SFDS_REG:APPROVE`, `CASE_CLOSE→SFDS_CASE:APPROVE`, `MAPPING→requiredBoCapability`다. 목록은 권한 있는 subject만 필터한 뒤 페이지를 자르고, 상세·승인·반려는 exact 판정 실패 시 엔진 결정 호출·local mutation 전에 거부한다. 미지 subject나 MAPPING marker 부재/미지 값은 fail-closed한다. local fallback 상신의 maker는 항상 현재 인증 principal이며 고정 `ops.agent` 기본값이 없다. bo-web의 `ApprovalSubjectKind`·라벨·필터도 DB/API 11종에 맞춰 `RULE_PARAM`·`TENANT_REGULATORY_CURRENCY`를 포함한다.
>
> 승인 요청의 `payloadHash`는 BO가 현재 pending detail의 hash와 먼저 비교한다. 불일치면 위임 호출 전에 409 `FDS-APPROVAL-PAYLOAD-CHANGED`이며, 일치한 위임도 engine이 maker≠checker·row integrity·상태 전이를 독립 검증한다.
>
> FDS의 운영자 write/audited endpoint는 raw/optional `X-User-Subject`를 controller command에 직접 사용하지
> 않는다. machine-auth가 서명 검증 뒤 승격한 end-user subject(명시적 local/demo bootstrap bypass 포함)를
> 공통 resolver로 필수 해석한다. aggregate도 maker/checker blank·control·128자 초과를 거부하고 trim 후
> 대소문자 무시 동일 actor를 자기결재로 처리한다. `MAPPING`/`POLICY_PACK`은 staged canonical payload를
> 재해시하고 action·required marker·scope/subject·`KR_BASE` 및 exact shape를 apply 직전에 다시 검증한다.
> capability desired-set(`[]` revoke-all 포함)은 동일 `(tenant,workspace,sourceSystem)` source row
> `PESSIMISTIC_WRITE` lock 안에서 delete→flush→insert 전체교체하여 서로 다른 approval row의 병렬 실행도
> union/부분 셋을 만들지 않는다.

### 4.9a Audit Event Query API (저수준 위임) — `fds:case:read`

| 메서드 | 경로 | 설명 | scope | 4-eyes |
|---|---|---|---|---|
| GET | `/api/v1/admin/fds/audit-events` | 인증 context의 tenant/workspace 안에서 FDS append-only audit를 조회. 선택 필터 `actor`, `targetKind`, `subjectId`, `traceId`, `from`, `to`, `page`, `size`; detail은 PII-safe masked 값만 반환 | `fds:case:read` | — |
| GET | `/api/v1/admin/fds/audit-events/{auditId}` | 인증 context의 tenant/workspace와 UUID가 모두 일치하는 FDS 감사 단건. 다른 scope는 존재 여부를 숨기고 404 | `fds:case:read` | — |

tenant/workspace override query/body는 받지 않는다. filter의 인증 context만 repository port로 전달하며, scoped key 없이 ID/목록을 조회하는 port는 노출하지 않는다. 응답 row는 `sourceService=FDS`, `auditId`, `tenantId`, `workspaceId`, `event`, `actorSubject`, `subjectKind`, `subjectId`, `traceId`, `detail`, `occurredAt`의 unified audit projection이다. 여기서 engine filter/storage의 `targetKind`(`SOURCE_SYSTEM`/`CONNECTOR`/`NOTIFY_CHANNEL`/`RULE`/`RISK_GROUP` 등)은 운영 resource 종류이고 approval `subjectKind` 11종과 별도다. 예를 들어 `RULE_PARAM` 실행 감사의 targetKind는 `RULE`, source-system capability/mapping 실행 감사는 `SOURCE_SYSTEM`, `GROUP_CREATE`/`GROUP_UPDATE`의 targetKind/targetRef는 `RISK_GROUP`/`group_id`다. 목록은 exact `totalElements`를 포함한 §3.2 page envelope이며 `occurredAt DESC, auditId ASC`로 안정 정렬한다. `fds_audit_logs.trace_id`는 V16부터 `VARCHAR(128)`이며 명시적 causal trace 우선·부재 시 request MDC를 기록한다. `NOTIFY_CHANNEL_CHANGE`/`NOTIFY_CHANNEL`의 EMAIL/SLACK/WEBHOOK nested `target`은 모두 `sha256:*`, `CONNECTOR_CHANGE`/`CONNECTOR`의 자유입력 `reason`은 `[REDACTED]`로 쓰고, 역사 row도 read-time 재마스킹한다. BO 신규 audit detail은 `webhookHosts` 자체를 저장하지 않으며 역사 `webhookHosts[]`는 read-time에 원소별 hash로 바꾼다. 민감 event의 malformed detail은 원문 대신 fail-closed redacted JSON을 반환한다.

bo-api는 `SFDS_AUDIT:READ`와 current tenant target을 강제한 뒤 local `bo_audit_logs`와 engine page를 source별 exact total로 merge한다. engine window를 먼저 읽고 local window를 뒤에 읽으며, engine audit list/detail 호출 자체는 `PROXY_FDS_CALL`을 append하지 않는다(자기 조회가 매 요청마다 top row를 추가해 offset을 shift하는 self-observation 금지). 일반 FDS proxy 호출 감사는 그대로 유지한다. 안정 정렬은 `occurredAt DESC, sourceService ASC`, 이후 BO `auditId`는 **numeric ASC**, FDS UUID는 canonical string ASC다. merge 수집 window `offset+size`는 최대 10,000행이고 초과 시 400으로 필터/기간 축소를 요구한다. 목록 `GET /api/v1/bo/fds/audit`는 `Page`의 `totalElements`를 보존하며, 단건은 목록 선형 검색이 아니라 typed composite `GET /api/v1/bo/fds/audit/{sourceService}/{auditId}`(`sourceService=BO|FDS`)로 직접 조회한다. generic `GET /api/v1/bo/audit[/{id}]`는 cross-domain raw surface이므로 `BO_SUPER_ADMIN`/wildcard `*` 전용이며 FDS 운영자는 typed route만 사용한다.

### 4.10 External Vendor Bridge API (외부) — `fds:event:write`
| 메서드 | 경로 | 설명 | scope | 4-eyes |
|---|---|---|---|---|
| POST | `/api/v1/fds/external-decisions` | vendor 결과 evidence ingest(`fds_external_decisions`) | `fds:event:write` | — |
| GET | `/api/v1/fds/external-decisions` | dual-run 비교 조회(`transactionRef`) | `fds:case:read` | — |

---

## 5. DTO 스키마

타입 표기: `string`/`integer`/`decimal(24,8)`/`uuid`/`datetime`(ISO-8601 TZ)/`enum`. 필수 = ●. 모든 식별자(`*Ref`)는 token/hash(원문 아님). 응답에 raw PII 없음.

### 5.1 IngestEventRequest (POST /fds/events) — `fds_canonical_events`
| 필드 | 타입 | 필수 | 검증 | 매핑 |
|---|---|---|---|---|
| eventId | string(160) | ● | 원천 unique(`@NotBlank`) | `event_id` |
| eventType | string(100) | ● | `<family>.<verb>`(`@NotBlank`, §3.5.2) | `event_type` |
| occurredAt | datetime | ● | ≤ now+5m(`@NotNull`) | `occurred_at` |
| schemaVersion | string(80) | ● | 등록된 mapping 존재(`@NotBlank`) | `schema_version` |
| messageVersion | string | △(기본 `v1`) | 큐 직렬화 버전(integration §4.1) | (큐 envelope) |
| originator | OriginatorDto | 조건부 | 고객 거래 필수(§4.1 Party 동형 부분집합, **정본** — subject 대체) | `subject_ref`… |
| subject | SubjectDto | △(**deprecated** — legacy 별칭) | originator 부재 시 하위호환 수용, 동시 존재+키 불일치 시 422 | `subject_ref`… |
| actor | ActorDto | 조건부 | 내부감사·직원작업 필수 | `actor_ref` |
| transaction | TransactionDto | 조건부 | 거래 이벤트 필수(블록 존재 시 최소 1 leg — 아래 통화 계약 note) | `transaction_ref`·`send_amount`·`receive_amount`·`send_currency`·`receive_currency`·`amount_base`(서버 파생)… |
| instrument | InstrumentDto | 권장 | 수단 룰 필요 | `instrument_ref`… |
| counterparty | CounterpartyDto | △ | `accountNoHash` 원문 계좌 미수용(A4) | `counterparty_ref`·`canonical_payload.counterparty.institutionCode`·`.accountNoHash` |
| merchant | MerchantDto | △ | | `canonical_payload.merchant` |
| device | DeviceDto | △ | `deviceRef`↔`deviceId` 불일치 422, `os`/`version`/`ip`/`locale` ≤64자(`locale`≤16자)·제어문자 금지(422) | `device_ref`·`device_ip`·`device_locale`·`canonical_payload.device` |
| channel | ChannelDto | ● | `channelType` 필수(§3.5.1) | `channel_type`,`payment_rail` |
| corridor | CorridorDto | △ | remit 계열 corridor | `send_country`·`receive_country`… |
| geoCountry | string | △ | ISO 국가코드(PII 아님) | `geo_country` |
| card | CardDto | △ | 중립 CARD_PAYMENT §6.3 | (canonical_payload) |
| balance | BalanceDto | △ | 중립 §6.3~§6.5 잔액 | (canonical_payload) |
| funding | FundingDto | △ | 중립 WALLET_TOPUP §6.4 | (canonical_payload) |
| order | OrderDto | △ | Phase7 ORDER family 커머스 투영 §14.6 | (canonical_payload 최상위 → `fds_commerce_orders`) |
| settlement | SettlementDto | △ | Phase7 SETTLEMENT family 정산 투영 §14.6 | (canonical_payload 최상위 → `fds_settlements`) |
| document | DocumentDto | △ | Phase7 TRADE/INVOICE family 증빙 투영 §14.6 | (canonical_payload 최상위 → `fds_business_documents`) |
| externalSignals | ExternalSignalsDto | △ | Phase7 외부 인텔리전스 pass-through §15.6~15.11 | (`canonical_payload.externalSignals` → feature 19종) |
| payloadHash | string(128) | △ | `sha256:...` | `payload_hash` |
| canonicalPayload | string(JSON) | △ | 정규화·마스킹된 보조 payload. 규제통화 금액 feature의 원천이 아니며 typed transaction leg에서 서버 파생한다. **인입 시 raw PII 방어 스캔** 후 검출 시 reject | `canonical_payload` |

> `Tenant-Id`/`Workspace-Id`/`Source-System`/`Idempotency-Key`/`X-Correlation-Id`/`traceparent`는 헤더로 전달(body 미포함, `IngestController` 시그니처 정합). **rawPayload·PAN·주민번호 포함 시 ingest reject 또는 tokenization 후 폐기**(§16.1).

> **canonicalPayload raw PII 방어 스캔·reject 계약(코드=truth, `ForbiddenPiiScanner`·`IngestEventService.scanForbiddenPii`, P0-09).** canonical envelope 는 raw PII 를 금지하고 수단/카드/계좌는 opaque 토큰 참조(`instrument.instrumentRef`)로만 운반한다. 엔진은 **persist(`fds_canonical_events`)·outbox(queue)·log 도달 이전**에 `canonicalPayload` 를 방어적으로 스캔하며(유효 JSON 이면 문자열 leaf 별 field-path 순회·비-JSON 이면 전체 문자열 1건 스캔), PAN(Luhn 유효 13–19자리)·계좌(연속 10자리 이상 숫자런)·이메일·KR 주민등록번호를 검출한다. 토큰/참조/금액 키(`instrumentRef`·`accountRef`·`subjectRef`·`counterpartyRef`·`transactionRef`·`amount`·`amountBase`·`phpEquivalent`·`balanceBefore`/`After` 등)는 스캔 예외(정당한 긴 숫자런=참조/수치, 중립 canonical 오탐 방지). 이름 등 자유텍스트는 스캔 범위 밖(토큰 참조·오탐 과다). 검출 시 **`FDS-PII-REJECTED`(422)** 로 reject 하며, **reject reason 은 PII class + field path 만**(예 `raw PII forbidden in canonicalPayload: PAN at $.instrument.pan`) 담고 **원문 값은 절대 미포함**(로그·메트릭에도 원문 미노출).

> **중립(canonical) 수집 블록 확장(코드=truth, feature/aml-neutral-canonical-ingest, additive).** AML 중립 수집 API(aml-api §2.1a)의 5 product 신호를 FDS 판정 경로가 동일 결선으로 소비하도록 `IngestEventRequest`에 `card`/`balance`/`funding` 블록과 `riskSignals.accountHolderNameMatch`/`fundingSourceType`를 추가했다(비-PII 신호만·기존 룰팩 C1213 이 cmp/velocity 노드로 소비 "가능"까지가 목표, 신규 룰팩 신설 없음). PAN·계좌·충전수단 masked 값은 미수용 — 카드/수단은 `instrument.instrumentRef` 토큰으로만 참조(§16.1). feature 카탈로그 등록은 DB §feature catalog V6(01-fds-db.md).

> **고객 프로파일 CDD 동기화(코드=truth, feature/fds-cdd-customer-profile-sync — aegis-aml `docs/aml-data.md` §11.7.1).** 프로필 정본은 거래 인입이 아니라 AML `customer.cdd.completed`다. AML은 성공 트랜잭션에 `FDS_CUSTOMER_PROFILE` outbox를 원자 생성하고 relay가 §4.3a 내부 API로 전달한다. FDS는 `fds_subjects`를 갱신하고 feature 컴퓨트가 `customer.nationality`(STRING)·`customer.signupAgeDays`/`customer.kycAgeDays`(NUMBER)를 파생한다. 기존 `SubjectDto` 3필드는 API 호환용 bootstrap fallback으로만 남아 CDD 값이 있으면 덮어쓰지 못한다. 값 부재 시 feature 미노출(룰 non-matching), `customer.accountAgeDays`는 별도 보존한다. 회원 키 정본: CDD `customerRef` = FDS `subjectRef` = 거래 `originator.partyReference`.
>
> **연령·심야·디바이스 novelty 파생 피처(코드=truth, PLAN 20260717 U-F3/U-F4 — `FeatureComputeAdapter`·`IngestEventService`·`domain/rule/DomainFeatureKeys`, 가정 A1/A2, 사용자 지시로 F-005 해제).** ① `customer.ageYears`(NUMBER) — `originator.dateOfBirth`(ISO-8601 `yyyy-MM-dd`) 를 인입 시 occurredAt 기준 만 나이로 파생해 `fds_subjects.age_years`(DB V28) 에 upsert 하고, **DOB 원문은 기존과 동일하게 미영속·즉시 폐기**한다(비-PII 파생 정수만 저장). ISO-8601 외 형식·DOB 부재 시 파생 스킵(feature 미노출 — 연령 조건 룰 fail-safe 미발동). ② `time.hourOfDay`(NUMBER)·`time.isNight`(BOOL) — `occurredAt` 을 관할 타임존으로 변환한 시(0~23)와 심야(22:00~06:00) 여부(가정 A1). **구현 실측**: fds-svc 는 테넌트 관할 타임존 조회 포트가 없어 `JURISDICTION_ZONE` 이 **항상 `UTC` 고정**이다(P0-16 jurisdiction 바인딩·`Asia/Manila` 변환은 미구현 — 조회 포트 자체 부재로 전 테넌트 UTC 적용, 관할별 변환은 후속 스코프). ③ `device.firstSeenForSubject`(BOOL) — 해당 `subject` 의 이전 이벤트 중 동일 `deviceRef` 이력이 없으면 `true`(`counterparty.firstForSubject` 쿼리 패턴 재사용). 3종 모두 `_global` 피처 카탈로그(DB V28) additive 등재.

> **originator 주체 계약(코드=truth, PLAN 20260717 U2 — `IngestEventRequest.OriginatorDto`·`IngestController.validateOriginatorContract`, aegis-aml `docs/aml-data.md` §11.7.7, 사용자 지시로 F-005 해제).** FDS 인입 주체 블록의 **정본**은 `originator`다(AML Party §4.1 동형 부분집합, 구 `subject` 를 대체). 필드: `partyReference`(string — 회원 키 단일 정본, 구 `subject.subjectRef` = 엔진 `targetRef`), `partyType`(string — 닫힌 매핑 `INDIVIDUAL→PERSON`/`LEGAL_ENTITY→BUSINESS`/부재→`PERSON`, 그 외 값은 422 `FDS-CONTRACT-VIOLATION`), `nationalIdentityKey`(string — `partyReference` 부재 시 PII-safe fallback 토큰 `hmac-sha256:<hex64>` 파생 입력, 원문 미영속), `fullNameLatin`/`dateOfBirth`/`gender`/`phone`/`identification[]{idType,idNumberMasked,issuingCountry}`(수용 즉시 raw PII 스캔 후 **폐기 — FDS 미영속**, 검출 시 422 `FDS-PII-REJECTED`), `nationality`/`residenceCountry`(→ `subject_ref` 국가 필드, §11.7.1 스냅샷), `kyc{occupation,sourceOfFunds,kycLevel,customerRiskRating,kycVerifiedAt}`(`kycVerifiedAt` 만 §11.7.1 `kycCompletedAt` fallback 소비, 나머지는 수용·미영속), `registeredAt`(datetime, FDS 확장 필드 — Party §4.1/§4.3 미정의, §11.7.1 bootstrap fallback 전용). **legacy `subject` 별칭(deprecated)**: `originator` 부재 시 기존 3필드(`nationality`/`registeredAt`/`kycCompletedAt`) bootstrap fallback 으로 계속 수용. `originator`+`subject` 동시 존재 + `subject.subjectRef`≠`originator.partyReference` 는 **422 `FDS-CONTRACT-VIOLATION`**(reason 은 두 키 이름만, 값 미포함).
>
> **device 공통 블록(코드=truth, PLAN 20260717 U2/U3 — `IngestEventRequest.DeviceDto`·`FeatureComputeAdapter`, aegis-aml `docs/aml-data.md` §4.5, 사용자 지시로 F-005 해제).** `DeviceDto` 는 `deviceRef`/`fingerprint`(기존)에 `deviceId`/`os`/`version`/`ip` 4필드가 추가됐다. `deviceId` 는 기존 `deviceRef` 로 coalesce(둘 다 존재·불일치 시 422 `FDS-CONTRACT-VIOLATION`) — 기존 `velocity.*.device.<w>` 6차원 device velocity 차원 키에 그대로 결선되며 신규 카탈로그 행이 필요 없다. `os`/`version`/`ip` 는 준식별자로 원값 저장(IP 마스킹 없음 — 화면 노출 경로 부재, PII §16.1 금지 목록 비해당)하고 canonical payload `device` 노드에 병합, `device.os`/`device.version`/`device.ip`(STRING) feature key 로 노출된다(DB §마이그레이션 V27 피처 카탈로그). ≤64자·제어문자 초과는 422 `FDS-CONTRACT-VIOLATION`.
>
> **device.locale 확장(코드=truth, PLAN 20260717 U-F4 — 룰 체계 개편, 사용자 지시로 F-005 해제).** `DeviceDto` 에 6번째 필드 `locale`(string, BCP-47 예 `zh-CN`, ≤16자·제어문자 금지 — 초과 시 422 `FDS-CONTRACT-VIOLATION`, 기존 device 필드 422 규칙과 동형)이 추가됐다. AML `NeutralDevice.locale` 과 동형 계약(양 계약 동시 확장, `docs/aml-data.md` §4.5). 값은 `fds_canonical_events.device_locale`(DB V28) 전용 컬럼에 기록되고 `device.locale`(STRING) feature key 로 노출된다(DB V28 피처 카탈로그). `locale` 은 device 블록 존재판정(4→5필드)의 5번째 판정 필드다 — `locale` 단독 인입(다른 device 필드 전부 null)이어도 device 블록이 materialize 되어 `device.locale` 피처가 노출된다(CLARIFY-01). 값 부재 시 미노출(fail-safe — locale 조건 룰 미발동).
>
> **transaction 통화 계약·서버측 규제통화 파생·422 규칙(코드=truth).** 클라이언트는 send/receive leg를 전송하고 서버는 tenant 규제통화와 일치하는 leg 금액을 typed `amount_base/base_currency`로 파생한다. 이 값이 velocity SUM·`transaction.amountBase`·전 통화 `transaction.baseEquivalent`의 단일 원천이며 PHP일 때만 `transaction.phpEquivalent` alias를 추가한다. 양 leg가 규제통화가 아니면 세 피처 모두 미노출하되 인입은 202를 유지한다. 구 canonical payload 환산값은 무시한다. leg 불일치/퇴화 블록은 기존 `FDS-CONTRACT-VIOLATION` 계약을 유지한다.

OriginatorDto(**정본**, AML Party §4.1 동형 부분집합): `partyReference`(string — 회원 키 단일 정본), `partyType`(string — `INDIVIDUAL`/`LEGAL_ENTITY`, A3 닫힌 매핑), `nationalIdentityKey`(string — fallback 토큰 파생 입력, 미영속), `fullNameLatin`/`dateOfBirth`/`gender`/`phone`(string, 수용 즉시 스캔 후 폐기 — `phone`(E.164)은 폐기 직전 `subject.phoneHash` 파생 원천, 연속 숫자런 ≤15자리는 전화로 보아 ACCOUNT 원문 판정 제외), `phoneHash`(string ≤64 hex △, 20260906 — 원천이 aml-data §11.7.9 canonical(`SHA-256(숫자만)`)로 사전 해시한 회원 전화 토큰; 제공 시 파생 없이 그대로, 원문 8자리+ 는 422 `FDS-PII-REJECTED`), `nationality`/`residenceCountry`(string), `identification[]`(`idType`/`idNumberMasked`/`issuingCountry`, 수용 즉시 스캔 후 폐기), `kyc`(`occupation`/`sourceOfFunds`/`kycLevel`/`customerRiskRating`/`kycVerifiedAt`, `kycVerifiedAt` 만 소비), `registeredAt`(datetime, FDS 확장 필드). 상세 계약은 위 originator 주체 계약 note 참조.
SubjectDto(**deprecated** — legacy 별칭, originator 부재 시만 수용): `subjectType`(enum subject_type ●), `subjectRef`(string token ●), `country`(string(8)), `nationality`/`registeredAt`/`kycCompletedAt`(△, **legacy bootstrap fallback** — 신규 호출자는 `originator` 또는 CDD 동기화 §4.3a 사용). 이미 CDD master 값이 있으면 거래 값으로 변경되지 않는다.
ActorDto: `actorType`(string), `actorRef`(string).
TransactionDto: `transactionRef`(string ●), `transactionType`(enum `TransactionType` ●), `direction`, send/receive amount·currency, legacy `amount/currency`, corridor, status. `amountBase/baseCurrency`는 입력이 아니라 서버 파생이다. 파생값은 `transaction.amountBase`와 전 통화 `transaction.baseEquivalent`로 노출되고 PHP에서만 `transaction.phpEquivalent` alias를 추가한다.
CorridorDto(△, `CROSS_BORDER_REMIT`/`DOMESTIC_REMIT`/`INBOUND_REMIT` 등 remit 계열): `sendCountry`(string(2), `send_country`), `receiveCountry`(string(2), `receive_country`), `sendCurrency`(string(12), `send_currency`), `receiveCurrency`(string(12), `receive_currency`) — hanpass-ph `remit-svc`/`domestic-svc`/`inbound-svc` corridor 매핑, DB §5.5. 모든 필드 선택(ISO 코드, PII 아님). 미탑재 시 `canonical_payload.corridor`로 표기.
InstrumentDto: `instrumentType`(enum instrument_type ●), `instrumentRef`(string token ●), `accountRef`, `institutionCode`, `country`.
CounterpartyDto: `counterpartyType`(string), `counterpartyRef`(string token — AML G9 안정키(이름+국가+전화), 원문 미수용), `country`, `institutionCode`(string ≤32 △ — 수취 기관 코드, feature `counterparty.institutionCode`(STRING)), `accountNoHash`(string ≤64 hex △ — 원천이 사전 해시한 계좌 식별, 20260906 부터 aml-data §11.7.9 canonical `SHA-256(숫자만)` 으로 확정·feature `counterparty.accountNoHash`(STRING)), `phone`(string E.164 △, 20260906 — 수용 즉시 스캔·`counterparty.phoneHash` 파생 후 폐기, 미영속), `phoneHash`(string ≤64 hex △, 20260906 — 사전 해시 수취인 전화 토큰, feature `counterparty.phoneHash`(STRING)). **원문 계좌번호·전화 해시 필드 원문 미수용(코드=truth, PLAN R3 A4 → 20260906 `phoneHash` 3경로로 일반화·`+` 포함)**: `accountNoHash`/`phoneHash` 값이 숫자·`+`·하이픈·공백만으로 구성되고 숫자가 8자리 이상이면 raw 식별자로 판정해 `FDS-PII-REJECTED`(422, 20260906 `IdentifierHash.looksLikeRawIdentifier` 정본 단일화); 제어문자 포함·64자 초과는 형식 위반 422(§6 `FDS-CONTRACT-VIOLATION`).
MerchantDto: `merchantRef`(string token), `mcc`(string), `country`.
DeviceDto(△): `deviceRef`(string token), `fingerprint`(string token), `deviceId`(string — `deviceRef` coalesce 대상, 둘 다 존재·불일치 422), `os`/`version`/`ip`(string ≤64자·제어문자 금지, 준식별자 원값 저장 — 위 device 공통 블록 note 참조), `locale`(string ≤16자·제어문자 금지, BCP-47 — 20260717 룰 체계 개편 신규 필드, 위 device.locale 확장 note 참조). 이벤트 조회 응답(`GET /fds/events*`)도 `deviceRef`를 마스킹 토큰으로 반환해 DEVICE 시간 윈도우 룰의 현재/이전 거래 비교 근거를 제공한다(raw device fingerprint 미노출).
ChannelDto: `channelType`(enum channel_type ● **21종** — hanpass-ph 운영 5종 `CROSS_BORDER_REMIT`/`DOMESTIC_REMIT`/`CASH_IN`/`WALLET_PAYMENT`/`WALLET_WITHDRAWAL` + `INBOUND_REMIT` 포함, DB §4.4), `paymentRail`(enum payment_rail/string), `entryMode`.
GeoDto(△): `country`(string(2) — 접속/IP 국가), `latitude`(decimal), `longitude`(decimal). 위도/경도는 보조 참고값이며 필수 아님.
RiskSignalsDto(△): `memberAgeDays`(int), `accountChangedWithinHours`(int), `deviceChangedWithinHours`(int), `manyToOnePattern`(boolean), `oneToManyPattern`(boolean), `electionPeriod`(boolean), `regionalRegistrationSpikeCount`(long), `bulkCashAmountBase`(decimal), `accountHolderNameMatch`(boolean △ — 중립 §6.2 국내송금 예금주명 대조; `false`=차명계좌 STR 신호, feature `transfer.accountHolderNameMatch`), `fundingSourceType`(string △ — 중립 §6.2 국내송금 자금원천 유형, feature `transfer.fundingSourceType`).
CardDto(△, 중립 CARD_PAYMENT §6.3 `card` 블록 — 비-PII만): `scheme`(string — VISA/MASTERCARD 등, feature `card.scheme`), `issuerCountry`(string(2), feature `card.issuerCountry`), `domesticInternationalFlag`(string — `INTERNATIONAL`→feature `card.international`=true). `panMasked`(BIN+말미4)는 미수용 — 카드는 `instrument.instrumentRef` 토큰으로만 참조(§16.1).
BalanceDto(△, 중립 §6.3~§6.5 `balance` 블록): `balanceBefore`(decimal, feature `balance.before`), `balanceAfter`(decimal, feature `balance.after`). 파생 feature `balance.delta`(after−before)는 충전 직후 잔액 0 근접 pass-through(환치기) 신호(§6.4 STR 관점).
FundingDto(△, 중립 WALLET_TOPUP §6.4 `funding` 블록): `fundingInstrumentType`(string — CARD/BANK_ACCOUNT 등, feature `funding.instrumentType`; 서로 다른 수단 다수=분산충전), `isAutoTopup`(boolean, feature `funding.autoTopup`), `isManualApproval`(boolean, feature `funding.manualApproval` — 관리자 수동충전 남용 신호). 충전수단 masked 값은 미수용(instrument 토큰 참조, §16.1).

OrderDto(△, Phase7 ORDER family — `fds_commerce_orders` 투영 계약화, 전 필드 선택): `orderRef`(string token — 부재 시 투영 skip), `marketplaceRef`, `sellerRef`, `buyerRef`(string token), `orderStatus`(string — `REFUNDED`/`CHARGEBACK` 이 환불·차지백 비율 분자), `amount`(decimal), `currency`, `shippingCountry`(string(2)), `deliveryStatus`(string — `DELAYED` 가 배송지연 비율 분자), `orderedAt`(datetime, 부재 시 `occurredAt`). canonicalPayload **최상위 필드**로 병합(putIfAbsent — 기존 free-form 인입 하위호환)되어 `CommerceProjectionService` 가 독해한다.
SettlementDto(△, Phase7 SETTLEMENT family — `fds_settlements` 투영 계약화): `settlementRef`(string token — 부재 시 skip), `settlementType`(string, 부재 시 `UNKNOWN`), `sellerRef`, `merchantRef`, `payoutInstrumentRef`(string token), `payoutCountry`(string(2) — **V24 신규 컬럼** 저장, feature `settlement.payoutCountry`), `amount`/`amountBase`(decimal)·`currency`/`baseCurrency`, `reserveAmount`, `chargebackExposure`, `status`, `scheduledAt`/`paidAt`(datetime). 직전 정산 대비 `payoutInstrumentRef` 상이 시 feature `settlement.preSettlementAccountChange`=true(계산, 직전 정산·시각 앵커 부재 시 미노출).
DocumentDto(△, Phase7 TRADE/INVOICE family — `fds_business_documents` 투영 계약화): `documentRef`(string token — 부재 시 skip), `documentType`(string — `INVOICE`/`PURCHASE_ORDER`/…, INVOICE family 기본 `INVOICE`), `documentNoHash`(string — **원문 인보이스 번호 미수용**, 해시만 §7.1), `issueDate`(date), `amount`(decimal), `currency`, `countryFrom`/`countryTo`(string(2)), `documentStatus`, `evidenceHash`.
ExternalSignalsDto(△, Phase7 §15.6~15.11 외부 인텔리전스 pass-through — 소스 제공값을 `canonical_payload.externalSignals` 노드로 병합, feature 부재 시 미노출 fail-safe·엔진 미계산): `trade`(invoiceUnitPriceDeviation decimal→`trade.invoiceUnitPriceDeviation`, documentMismatch/highRiskCorridor/splitPaymentPattern boolean→`trade.*`), `seller`(riskGrade string→`seller.riskGrade`, bankAccountMismatch boolean→`seller.bankAccountMismatch`), `settlement`(accelerationRequest boolean→`settlement.accelerationRequest`), `vendor`(bankAccountRecentlyChanged boolean→`vendor.bankAccountRecentlyChanged`, approverRoleMismatch boolean→`invoice.approverRoleMismatch`), `crypto`(addressRisk/mixerExposure/depositWithdrawalLatency decimal + newAddressWithdrawal/apiKeyFirstUse boolean→`crypto.*`), `market`(manipulationPattern decimal→`market.manipulationPattern`), `employee`(role string + overrideCount decimal + approvalBypass/highValueAccess boolean→`employee.*`). **계산 전환 7종 키(`counterparty.newBeneficiary`·`vendor.onboardingAgeDays`·`invoice.amountDeviation`·`seller.salesSpike`·`seller.gmvSpike`·`settlement.payoutCountry`·`settlement.preSettlementAccountChange`)는 externalSignals 로 주입 불가** — 엔진 계산값만 사용(결정론 유지).

> **Phase7 피처 인입 커버리지 확장(코드=truth, feature/fds-feature-ingest-coverage, additive).** 피처 카탈로그 input-slot 26종(§15.6~15.11)이 룰 조건으로 선택돼도 발동 불가하던 갭을 해소 — ① 7종은 결정적 계산 전환(위 계산 정의·DB §5.25~5.27 상태 기반), ② 19종은 `externalSignals` pass-through, ③ 커머스 투영 free-form payload 를 `order`/`settlement`/`document` 타입 블록으로 계약화(최상위 putIfAbsent 병합, free-form 하위호환 유지). 카탈로그 V24 가 계산 전환 7종 라벨의 "(외부/후속)" 표기를 "(계산 지원)" 으로 갱신. **커머스 3블록은 `eventType` family 일치 시에만 병합**(ORDER→order·SETTLEMENT→settlement·TRADE/INVOICE→document, `IngestController#payloadFamily`) — 3블록이 공유하는 최상위 키(amount/currency/status/sellerRef) 충돌 방지, 불일치 블록은 fail-safe 무시. Phase7 커머스 토큰/해시 키(orderRef·settlementRef·documentRef·sellerRef·buyerRef·marketplaceRef·payoutInstrumentRef·documentNoHash·evidenceHash)는 P0-09 PII 방어 스캔의 EXEMPT_KEYS 에 포함(opaque 토큰·hex 해시의 숫자런 오탐 방지, `ForbiddenPiiScanner`).

> FDS/TM 공통 거래 payload 동기화: FDS `POST /fds/events`·`POST /fds/decisions/evaluate`와 AML TM `POST /aml/transactions/evaluate`는 동일 실시간 거래 신호를 사용한다. 위 보조 필드는 canonical payload feature key `geo.country`, `geo.latitude`, `geo.longitude`, `customer.accountAgeDays`, `account.changedWithinHours`, `device.changedWithinHours`, `behavior.manyToOnePattern`, `behavior.oneToManyPattern`, `election.active`, `election.registrationSpikeCount`, `election.bulkCashAmountBase`로 노출된다.

### 5.2 IngestEventResponse (202 신규 수신 / 200·201 멱등 재반환)
`POST /fds/events`는 canonical event 를 저장한 **직후 ACTIVE inline 룰을 동기 평가**한다(§4.1). 신규 수신 성공 = **202 Accepted**(`status=ACCEPTED`, 저장+평가 완료·판정 요약 `decision` 동봉). 멱등 재요청(동일 `Idempotency-Key`+동일 payload)은 저장된 결과를 **200/201**로 재반환(`Idempotency-Replayed: true`, §3.3) — `decision` 도 저장된 동일 결정을 재표현한다(재평가하지 않음). 중복 event(`event_id` 충돌)는 `status=DUPLICATE`, reject는 `status=REJECTED`(422 계열, §6) — 이 두 경우 `decision=null`. 거절 없음 원칙 불변 — 판정 동봉은 표시이지 인입 거부가 아니다.

| 필드 | 타입 | 설명 |
|---|---|---|
| eventId | string | 수신 event id |
| status | enum | `ACCEPTED`(202 신규 저장+평가)/`DUPLICATE`/`REJECTED` |
| idempotencyReplayed | boolean | 멱등 재반환 여부(true 시 200/201) |
| code | string\|null | §6 에러코드(`FDS-SCHEMA-UNKNOWN`/`FDS-VALIDATION-001`/`FDS-PII-REJECTED`/`FDS-CONTRACT-VIOLATION`), 성공/중복 시 null |
| reason | string\|null | reject/duplicate 사유, 성공 시 null |
| decision | DecisionSummary\|null | **additive**(20260718 사용자 지시, F-005 해제) — 동기 평가 판정 요약. 이벤트가 평가되지 않은 경우(reject/duplicate, 또는 fail-safe 평가 실패) `null` |

**DecisionSummary**(ingest 응답 전용 요약 — §5.4 `DecisionResponse` 와 별개 DTO, 어댑터 DTO 간 결합 없음):

| 필드 | 타입 | 설명 |
|---|---|---|
| decisionId | uuid | `fds_decisions.decision_id` |
| decision | enum decision (8종, DB §4.x) | 판정 결과(`ALLOW`/`REVIEW`/`CHALLENGE`/`BLOCK`/`HOLD` 등) |
| riskScore | decimal(8,4) | §5.4 `riskScore` 동형 |
| matchedRules | MatchedRule[] (`ruleId`,`ruleName`,`outcome`) | 발동 룰 요약 |

`POST /fds/events:batch`(§4.1)는 `BatchIngestResponse{accepted, results: IngestEventResponse[]}` — 항목별로 위 계약과 동형(신규 accepted 건은 `decision` 동봉, 프리체크 reject 항목은 `decision=null`).

`POST /fds/decisions/evaluate`·`POST /fds/events/evaluate`(§5.3·§5.3a) 는 계약 그대로 유지된다 — 단 `/events` 가 동일 이벤트를 이미 동기 평가했으면 그 결정을 **재사용**(신규 decision 행 생성 금지, event-scope 재사용 게이트).

> **데모 인입 테스트 이벤트 transaction payload(비-prod, 데이터 정직화 v6.10, 기능정의서 §8.2/§11.1 BR-005 · AML §7.1 BR-DEMO-HONESTY).** 데모(비위임) 시뮬레이터는 FDS·AML 양쪽에 **동일 nested `transaction` 객체**를 전송한다 — `FdsIngestTestController.TestEvent` 가 AML 인입과 **동일 필드**(`memberRef`·`transactionRef`·`channel`·`amount`·`currency`·`corridor`·`receiverName`·`receiverCountry`·`senderHolderName`)를 소비한다(기존엔 4필드만 소비해 나머지를 버렸음). FDS 라이브 판정(`FdsDecisionCaseStubService.ingestLiveDecision`)은 **`transactionRef` 을 payload 원문 그대로** 쓰고(조작 `txn-live-{seq}` 폐기), `FdsRuleCatalog` ACTIVE 룰을 실 거래 속성(금액밴드·채널·corridor·FDS 신호)으로 실평가해 ALLOW/REVIEW/BLOCK·발동 룰·점수를 낸다(hash 파생 폐기). 따라서 **한 거래가 FDS 판정(§5.5 decision `transactionRef`)과 AML 알림에서 동일 `transactionRef`** 로 상호 참조된다. seed 판정/케이스 픽스처는 폐기(인입 0=빈 목록). **비-prod 전용**(위임/prod fail-closed 불변).

### 5.3 EvaluateRequest (POST /fds/decisions/evaluate) — `DecisionQueryController.EvaluateRequest`
동기 평가 요청. 코드 정본 DTO는 **참조 기반 경량 body**다(이미 수신된 canonical event를 참조하거나 `canonicalPayloadJson`을 직접 동봉).

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| eventId | string | △ | 평가 대상 canonical event 참조 |
| transactionRef | string | △ | 거래 참조 token |
| subjectRef | string | △ | 대상 token |
| sourceSystem | string | △ | 소스 시스템 식별(§4.8) |
| canonicalPayloadJson | string(JSON) | △ | 정규화 보조 payload(규제통화 금액 feature 원천 아님) |

> `Tenant-Id`/`Workspace-Id`/`Idempotency-Key`(필수)는 헤더 전달. 응답에 즉시 decision 포함, `fds_decisions`+`fds_decision_reasons` 동기 생성. (과거 "IngestEventRequest와 동일 구조" 표기는 코드 정합으로 정정.)

#### 5.3a IngestDecisionResponse (POST /fds/events/evaluate)

동기 편의 API의 요청 body/헤더는 §5.1 `IngestEventRequest`와 동일하다. 내부 순서는 기존 ingest use case commit → §5.3 evaluate use case이며 두 단계 멱등 scope(`EVENT`/`DECISION`)는 동일 `Idempotency-Key`를 독립 저장한다. 응답은 `{ingest: IngestEventResponse, decision: DecisionResponse|null}`이다. `ACCEPTED`/`REPLAYED`만 `decision`이 존재하며 `DUPLICATE`/`REJECTED`는 `decision=null`이다. 기존 `/events`와 `/decisions/evaluate` 분리 계약은 불변이다.

### 5.4 DecisionResponse — `fds_decisions` (설계서 §12.8 응답 예시 정합)
| 필드 | 타입 | 매핑 |
|---|---|---|
| decisionId | uuid | `decision_id` |
| eventId | string | 연결 canonical event 참조 |
| transactionRef | string(token) | decision 자체 거래 참조 |
| subjectRef | string(token) | decision 자체 대상 참조 |
| decision | enum decision (8종) | `decision` |
| reasonCodes | string[] | `fds_decision_reasons.reason_code` |
| riskScore | decimal(8,4) (0~100) | `risk_score` (산출 정책 = 소프트웨어 §11.1.1: outcome severity 단조 매핑; 응답은 JSON `number`, webhook은 `"82.0000"` 문자열 — §9·integration §4.5) |
| recommendedActions | enum action_type[] | emit된 `fds_actions.action_type` 투영(capability/4-eyes 게이트·downgrade 반영, integration §142) — 단일 컬럼 1:1 매핑 아님 |
| matchedRules | RuleRef[] (`ruleId`,`versionNo`,`ruleName`,`outcome`) | `matched_rules` (발화 룰 이름·outcome 동봉) |
| ruleSetVersion | string(80) | `rule_set_version` |
| caseId | uuid (nullable) | decision이 연 case(`fds_cases.origin_decision_id`); 미연결 시 null(graceful) |
| amount / currency | decimal(24,8) / string (nullable) | 연결 canonical event LEFT JOIN 파생(거래 컨텍스트) |
| amountBase / baseCurrency | decimal(24,8) / string (nullable) | 서버 파생 규제통화(기준통화; tenant_demo=PHP) 환산 비교 축(통화 혼재 비교, §11.7.6) |
| channelType | string (nullable) | 연결 event 채널(§3.5.1 5종) |
| sendCountry / receiveCountry | string (nullable) | corridor(remit 계열, DB §5.5) |
| evaluationPhase | enum(`INLINE`/`ASYNC`) | `evaluation_phase`(P0-07). 동기 REST 평가=`INLINE`, 사후 큐 소비 평가=`ASYNC`. 자연 멱등키 구성요소(DB §5.10) |
| eventOccurredAt | datetime (nullable) | `event_occurred_at`(P0-07). 평가 시 사용한 velocity asOf(재현성). V19 이전 결정은 null |
| expiresAt | datetime | `expires_at` |
| createdAt | datetime | `created_at` |

> `RuleRef`(코드 정합) = `ruleId`(uuid)·`versionNo`(int)·`ruleName`(string)·`outcome`(string) — UI가 판정을 이끈 발화 룰을 가독 렌더할 수 있도록 이름·outcome 동봉(§10 OpenAPI 보강). `amount`/`currency`/`channelType`/`sendCountry`/`receiveCountry`는 `eventId`로 연결한 canonical event의 마스킹 read projection이며 event 미해석 시 `null`(raw PII 아님). `feature_snapshot`/`input_event_hash`는 증적용이며 기본 응답 미노출(Evidence API 전용 경계).

### 5.4a DecisionEvidenceTransactionsResponse — `GET /api/v1/fds/decisions/{decisionId}/evidence-transactions` (요구2 — 판정 근거 거래 전수)

발동 룰의 evidence 윈도우 메타(발동 룰 + dimension + rolling window + channel scope)와 근거 거래의 페이징 envelope 를 반환한다. 캡된 `feature_snapshot` evidence 는 이 뷰를 절단하지 않는다(전수 페이징). 응답 형상은 fds-svc `DecisionEvidenceTransactionsResponse`(port `QueryDecisionEvidenceUseCase.EvidenceResult`, `DecisionEvidenceQueryPort`)와 1:1:

| 필드 | 타입 | 매핑 |
|---|---|---|
| `ruleId` | string(uuid)\|null | 설명 대상 발동 룰(미지정 시 대표 룰 A12) |
| `ruleName` | string\|null | 발동 룰 이름 |
| `outcome` | enum\|null | 발동 룰 outcome(decision severity) |
| `dimension` | enum\|null | 집계 축(subject velocity / banking-day cash sum / single-transaction group) |
| `dimensionRef` | string\|null | 집계 축 참조 키(주체/그룹 토큰) |
| `window` | string\|null | rolling window(예 `PT6H`) |
| `windowStart` | string(date-time)\|null | 윈도우 시작 시각 |
| `asOf` | string(date-time)\|null | 집계 기준 시각 |
| `channelFilter` | array<string>\|null | 채널 scope 필터 |
| `transactions` | `PageResponse<EventViewResponse>` | 근거 거래 전수 페이지(정렬 `occurredAt,desc`) |

`transactions.content` 원소 = `EventViewResponse`(canonical event 뷰 투영, §5.1 canonical event 필드 미러) — 테넌트 키 토큰만·raw PII 미포함(§16.1), `canonical_payload` 미노출. 주요 필드: `eventId`/`eventType`/`eventFamily`/`occurredAt`/`subjectRef`/`subjectCountry`/`transactionRef`/`transactionType`/`channelType`/`paymentRail`/`sendCountry`/`receiveCountry`/`sendCurrency`/`receiveCurrency`/`sendAmount`/`receiveAmount`/`amount`/`currency`/`amountBase`(규제통화 서버 파생)/`baseCurrency`/`counterpartyRef`/`deviceRef`/`payloadHash`. party 식별정보는 마스킹 토큰만 실리며 원문 PII 는 미포함(§16.1 마스킹/hash 정책).

### 5.5 CaseDto — `fds_cases`
| 필드 | 타입 | 매핑 |
|---|---|---|
| caseId | uuid | `case_id` |
| caseType | enum case_type (10종) | `case_type` |
| subjectRef / transactionRef | string(token) | 동일 |
| originDecisionId | uuid | `origin_decision_id` |
| status | enum case_status | `status` |
| priority | enum case_priority | `priority` |
| assignedTo | string(운영자 token) | `assigned_to` |
| closeReason | string(64) | `close_reason` (DB VARCHAR(64) §5.13). **enum 8종** `FP_THRESHOLD`/`FP_NORMAL_PATTERN`/`FP_DATA_QUALITY`/`CONFIRMED_FRAUD`/`CONFIRMED_MULE`/`CONFIRMED_ATO`/`ESCALATED_AML`/`OTHER`(DB §4.11·설계서 §11.6.1a). `POST .../close` 요청 시 필수, 상세 메모(자유 텍스트)는 case event(`CLOSED` payload) 보조 저장으로 분리 |
| amlCaseRef | string | aml-svc cross-ref(`fds_cases.aml_case_id`, integration 확정) |
| slaDueAt | datetime(nullable) | `sla_due_at` — 케이스 처리 SLA 기한(`CaseSlaPolicy` 파생, 케이스 유형·우선순위 기준). null = SLA 미적용 |
| slaBreached | boolean | `sla_breached` — SLA 기한 초과 여부. 응답은 `CaseSlaPolicy.breached`(`sla_due_at < now AND 비종결`) 라이브 평가값(목록 `slaBreached` boolean 필터 축, L151) |
| createdBy / updatedBy | string(128, nullable) | `created_by` / `updated_by` (DB §5.13) |
| createdAt / updatedAt | datetime | 동일 |

### 5.6 CasePatchRequest (PATCH /fds/cases/{caseId})
`status`(enum case_status), `priority`(enum case_priority), `assignedTo`(string), `reason`(string, 선택 — 단 종결 상태→`status=IN_REVIEW` 재오픈 시 **필수**, 감사 기록용, PRD §11.2 BR-006) — status/priority/assignedTo 중 1개 이상 필수. 내부감사 case 종결은 결재 게이트.

### 5.7 CaseActionRequest (POST /fds/cases/{caseId}/actions) — `fds_actions`
| 필드 | 타입 | 필수 | 매핑 |
|---|---|---|---|
| actionType | enum action_type (22종) | ● | `action_type` |
| targetSystem | string(64) | △ | `target_system` |
| targetRef | string(token) | △ | `target_ref` |
| reason | string | ● | (감사) |

응답 ActionResponse: `actionId`(uuid), `decisionId`(uuid, nullable), `caseId`(uuid, nullable), `actionType`(enum action_type 22종, 필수 — `fds_actions.action_type` DB §5.12 매핑), `targetSystem`, `targetRef`, `status`(enum action_status), `approvalRequestId`(uuid, null 가능), `idempotencyKey`, `retryCount`, `errorCode`, `requestedAt`, `completedAt`. `GET /fds/actions`/`GET /fds/actions/{actionId}` 응답도 동일 스키마(§10 `ActionResponse`).

### 5.8 RuleDto / RuleUpsertRequest — `fds_rules`
| 필드 | 타입 | 필수 | 매핑 |
|---|---|---|---|
| ruleId | uuid | (응답) | `rule_id` |
| ruleSetId | string(80) | ● | `rule_set_id` |
| name | string(160) | ● | `name` |
| channelScope | enum channel_type | △(nullable) | `channel_scope` — **NULL = 전채널 적용**(특정 채널 미한정) |
| dslSource | string | △ | `dsl_source`(no-code 표현) |
| ruleJson | string(JSON) | ● | `rule_json`(JSONB) — wire 는 canonical DSL 트리를 **JSON 직렬화한 문자열**(`RuleUpsertRequest.ruleJson` `@NotBlank String`·`RuleDto.ruleJson` String), 저장 시 JSONB. object 로 전송하면 400 `FDS-VALIDATION-001` |
| decisionOutcome | enum decision | △ | `decision_outcome` |
| evaluationMode | enum | △ | `evaluation_mode`: `INLINE_AND_ASYNC`(실시간+사후), `INLINE_ONLY`(실시간 제한 전용), `ASYNC_ONLY`(사후 모니터링 전용) |
| status | enum rule_status | (응답) | `status` |
| createdBy / updatedBy | string(128, nullable) | (응답) | `created_by` / `updated_by` (DB §5.17) |
| createdAt / updatedAt | datetime | (응답) | `created_at` / `updated_at` (DB §5.17) |

`ruleJson` DSL은 literal `value` 외에 운영 변수 참조를 지원한다. `{"valueRef":"c1213.velocity.6h.count.threshold"}`는 DB `fds_rule_variables.value_json`으로 치환되어 비교/velocity 임계값이 되고, `{"groupRef":"c1213.geo.risk_country.group"}`는 위험그룹 ID로 치환되어 `in_group` 조건에 사용된다. Admin 조회(`GET /admin/fds/rules`, `GET /admin/fds/rules/{ruleId}`)는 원본 참조 키를 유지하면서 BO 표시용 현재값을 `value`/`group`에 보강해 반환한다. 변수 누락/타입 불일치 룰은 해당 룰만 미매칭 처리한다.

> **velocity `distinct_count`·`field` 규약(코드=truth, V10 — aegis-aml `docs/aml-data.md` §11.7.2, DB §5.17)**: `ruleJson` velocity 노드 집계(`agg`)는 `count`(건수)/`sum`(금액합계)/`distinct_count`(서로 다른 값 개수) 3종이다. `distinct_count` 는 `field` **필수** — 닫힌 화이트리스트 `{receiveCountry(수취국가), channelType(이용 채널), counterpartyRef(수취처), deviceRef(단말), ip(접속 IP), merchantRef(가맹점/단말 토큰)}`(`RuleDslParser.DISTINCT_FIELDS`, PLAN 20260717 R3 로 `counterpartyRef` 추가·U-F1 로 `deviceRef`/`ip`/`merchantRef` 추가) 외 값은 파싱 거부(폐그래머·임의 field 주입 불가) — 이고, `count`/`sum` 은 `field` **금지**(기존 노드 문법 불변·무회귀). velocity `count`/`sum` 의 `dimension` 은 `subject`/`instrument`/`counterparty`/`actor`/`merchant`/`device` 6종(counterparty·merchant 차원은 R3 카탈로그 노출). 예: `{"type":"velocity","agg":"distinct_count","field":"counterpartyRef","dimension":"subject","window":"24h","op":">","value":3}` / `{"type":"velocity","agg":"count","dimension":"counterparty","window":"24h","op":">=","value":5}`. 사전계산 feature 키 `velocity.distinct_count.<field>.subject.<window>`(dimension 1차 지원 `subject`, **window 9종 `1m`/`5m`/`10m`/`30m`/`1h`/`6h`/`24h`/`7d`/`30d`** — U-F1 로 `1m`/`5m`/`30m`/`7d`/`30d` 5종 확장, 기존 `10m`/`1h`/`6h`/`24h` 4종 무회귀).
>
> **velocity window 화이트리스트·`scope` 확장(코드=truth, PLAN 20260717 U-F1 — `RuleDslParser.ALLOWED_WINDOWS`/`ALLOWED_SCOPES`, 사용자 지시로 F-005 해제).** `velocity` 노드의 `window` 는 닫힌 화이트리스트 `ALLOWED_WINDOWS = {1m, 5m, 10m, 30m, 1h, 6h, 24h, 7d, 30d}`(미허용 값은 `RuleDslException` 파싱 거부, 기존 4종 `10m`/`1h`/`6h`/`24h` 포함이라 무회귀)로 검증된다. 신규 선택 필드 `scope`(값 `"sameChannel"` 만 허용, 그 외 값은 파싱 거부, 부재=기존 동작)를 도입해 velocity 집계를 평가 대상 이벤트와 동일 `channel.type` 인 이벤트로만 좁힌다. 사전계산 feature 키는 `velocity.<agg>[.<field>].<dimension>[.sameChannel].<window>`(scope 부재 시 기존 키 byte-for-byte 불변). 예: `{"type":"velocity","agg":"count","dimension":"subject","scope":"sameChannel","window":"7d","op":">=","value":5}` → `velocity.count.subject.sameChannel.7d`.
>
> **velocity window 1y(365일) 확장(코드=truth, PLAN 20260719-fds-rule-window-1y-value-hints U1·U9 — `RuleDslParser.ALLOWED_WINDOWS`, 사용자 지시로 F-006 잠금 경로 append-only 해제).** `ALLOWED_WINDOWS` 가 `{1m, 5m, 10m, 30m, 1h, 6h, 24h, 7d, 30d, 1y}`(**10종**)로 확장됐다 — `1y` = 365일 고정(윤년 미보정, `Duration.ofDays(365)`), 반개구간 `(occurredAt−365d, occurredAt]` 의미는 기존 윈도우와 동일. `365d`·`1w`·`2y` 등 그 외 표기는 여전히 파싱 거부(닫힌 집합 유지, 표기 이원화 방지). `1y`는 velocity `count`/`sum`/`distinct_count`·`sameChannel` scope 전 경로에서 동형 지원되며, 근거거래(evidence) 윈도우 해석(`RuleEvidenceWindowResolver.parseWindow`)도 `y` 단위를 인식한다(1y 룰은 SINGLE_TX 로 강등되지 않고 365일 evidence 윈도우로 해석). 사전계산 feature 키 예: `velocity.count.subject.1y`·`velocity.sum.subject.1y`. 룰 빌더(`/fds/rules/new`)는 velocity 계열 피처 선택 시 윈도우 드롭다운(10종)을 노출하고, 기준값 입력 필드에는 피처별 예시 값을 프론트 i18n 카탈로그(ko/en)로 placeholder 표시한다. 신규 카탈로그 대표 키 6종은 DB V29(01-fds-db.md).

> **bo-api 위임 wire 봉투(코드=truth, `FdsRuleGroupService`)**: ① **쓰기(생성/수정)** — bo-api DTO 는 `ruleJson` 을 중첩 object 로 들고 있으나 엔진 `RuleUpsertRequest.ruleJson` 은 `@NotBlank String` 바인딩이므로, 위임 시 `toEnginePayload()` 가 body 를 엔진 계약으로 재성형한다: `ruleJson` → canonical DSL 트리의 **JSON 직렬화 문자열**(object 그대로 보내면 400 `FDS-VALIDATION-001` — 응답 stub 만 검증하는 MockRestServiceServer 로는 미적발되는 wire 갭), `channelScope` → **null(전채널) 포함 원문 그대로 전달**(기본값 주입 금지), bo-api 전용 필드(`ruleNo`/`changeReason`/`ticketId`)는 탈락(엔진 DTO 미보유). ② **읽기(목록/상세 `fromEngine`)** — 엔진 응답 `channelScope` NULL 을 기본 채널로 치환하지 않고 **NULL 그대로 노출**(표시 라벨 "전채널") — 치환하면 목록/상세가 특정 채널로 오표기될 뿐 아니라 편집 round-trip 시 실제 scope 가 해당 채널로 오염된다.

> C-1213/M-2025 룰팩: 초기 시드는 VELOCITY(6h 10회째 차단), DEVICE(변경 후 3h 내 4M KRW 해외송금), GEO(가입 3일 이내 위험국가 그룹 접속), BEHAVIOR(동일 수취계좌 18M KRW 및 다대일/일대다), ELECTION(선거기간 지역 등록 급증·대량 현금) 룰을 포함한다. DEVICE 룰은 `device.changedWithinHours`/`account.changedWithinHours` 소스 신호만으로 차단하지 않고, `device.priorDifferentWithin3h=true`(같은 회원의 3시간 내 이전 거래 중 현재와 다른 device token 존재) 근거를 함께 요구한다. DEVICE/GEO는 제한 룰(`INLINE_ONLY`)과 사후 모니터링 룰(`ASYNC_ONLY`)을 분리한다. 위험국가(VN/KH/CN 초기값)와 임계값/가중치는 코드 상수가 아니라 `fds_rule_variables` 및 `fds_risk_groups` 값으로 운영 변경한다.

RuleActionRequest(`POST /admin/fds/rules/{ruleId}/activate`, `POST /admin/fds/rules/{ruleId}/rollback`):
| 필드 | 타입 | 필수 | 매핑/검증 |
|---|---|---|---|
| reason | string | activate △ / rollback ● | `fds_approval_requests.reason`, rollback 감사 사유 |
| simulationId | uuid | inline activate ● / async-only activate △ | 활성화 결재 payload. `INLINE_AND_ASYNC`/`INLINE_ONLY` 룰 활성화는 사전 simulation 결과 참조 필수 |

### 5.9 RuleSimulationRequest / Response — `fds_rule_simulations`
요청: `ruleId`(uuid, △) 또는 `ruleJson`(object ●), `sampleWindow`({`from`,`to`} object).
응답: `simulationId`(uuid), `estimatedHitRate`(decimal(8,4)), `resultSummary`(object), `createdAt`(datetime, DB §5.19 `created_at`), `createdBy`(string(128), nullable, DB §5.19 `created_by`).

시뮬레이션은 활성 rule variable과 group-backed variable을 현재값으로 해석한 뒤 canonical event 표본을 재평가한다. 따라서 `valueRef`/`groupRef` 기반 룰의 예상 hit rate는 운영 변수·위험그룹 변경값을 반영한다.

**피처 계산 범위(성능, 2026-08-15)**: 표본 재평가는 **후보 룰이 실제로 읽는 피처만** 계산한다. 종전에는 표본마다 전 피처를 계산해 이벤트당 6개 차원 velocity(6쿼리)·sameChannel 윈도우별 조회(10쿼리)·distinct velocity·마스터 조회가 반복됐고, 500 표본에서 DB 행 292,965건·37.0초가 소요돼 라이브 검증(verifier 30초)을 넘겼다(실측). 후보 룰의 조건 트리에서 참조 피처 키를 수집(`RuleFeatureKeys`)해 비싼 velocity 블록을 선택 계산하면 **1.5~2.9초**로 줄고, `estimatedHitRate`·`resultSummary` 는 **동일 값**이다(계산량만 감소·판정 불변, 실측 hitCount 41·hitRate 0.082 일치).

키를 확정할 수 없는 룰(예 `valueRef` 사용)은 **전체 계산으로 폴백**한다 — 필요한 피처가 빠지면 룰이 조용히 미발동해 hit rate가 거짓으로 낮아지므로, 축소는 최적화일 뿐 계약이 아니다. 라이브 인입(탐지) 경로의 피처 계산 범위는 무변경이다.

### 5.9a RuleRecommendationRequest / Response (POST /admin/fds/rules/recommendations)

룰 빌더의 **목표 적중률 → 단일 피처 임계값 역산** 추천. **read-only**(`fds_*` 영속·결재 없음). 모집단(분포·적중률)은 **거래(canonical event) 기준**이며, 윈도우 내 표본 **최대 500건 근사**다. 비수치 피처/빈 표본은 graceful(`sampleSize=0`). 응답은 **집계·임계값만** 반환(raw PII·개별 피처값 미반환).

RuleRecommendationRequest:
| 필드 | 타입 | 필수 | 검증 | 설명 |
|---|---|---|---|---|
| featureKey | string | ● | feature catalog 수치형 | 임계값 역산 대상 피처 키 |
| targetHitRate | decimal | ● | `0 < x ≤ 1` | 목표 적중률(거래 기준 비율) |
| direction | enum `GTE`/`LTE` | △(기본 `GTE`) | | 임계 방향(이상/이하) |
| channelScope | enum channel_type | △(nullable) | | 채널 범위 한정(미지정 시 전체) |
| sampleWindow | object `{from, to}` | △(nullable) | | 표본 기간(미지정 시 기본 윈도우, 최대 500건) |

RuleRecommendationResponse:
| 필드 | 타입 | 설명 |
|---|---|---|
| featureKey | string | 요청 피처 키 |
| operator | enum `GTE`/`LTE` | 적용 연산자(요청 `direction`) |
| recommendedThreshold | decimal | 목표 적중률 percentile로 역산한 추천 임계값 |
| expectedHitRate | decimal(scale 4) | 추천 임계값 단일조건 룰 **엔진 재평가**로 검증한 실제 예상 적중률(거래 기준) |
| targetHitRate | decimal | 요청 목표 적중률(에코) |
| sampleSize | integer | 평가 표본 거래 수(최대 500, 비수치/빈 표본 시 0) |
| alternatives | object[] `{threshold, hitRate, targetHitRate}` | 인접 대안(±1·2%p) 임계값·예상 적중률·해당 목표 적중률 |

### 5.9b RuleParamsResponse / UpdateRuleParamsRequest / UpdateRuleParamsResponse (GET/POST /admin/fds/rules/{ruleId}/params · :update-params)

룰 빌더의 **변수(파라미터) 편집 4-eyes 폐루프**(코드=truth, `RuleParamDtos`·`RuleParamService`). 변수 카탈로그는 룰의 `ruleJson` 수치 리프값에서 파생하며, 승인 완료된 override 는 `fds.fds_rule_param_overrides`(DB §5.36)에 원자 셋으로 적용된다. 판정은 override 를 결정마다 fresh read(캐시 없음). `unit` 은 자유 텍스트(예: `%`, `건`, `PHP`) — 폐쇄 enum 아님.

RuleParamsResponse (GET):
| 필드 | 타입 | 설명 |
|---|---|---|
| ruleId | uuid | 대상 룰 id |
| params | RuleParamItem[] | 튜닝 가능 변수 목록(아래) |
| pendingApprovalId | uuid(nullable) | 진행 중(`SUBMITTED`) `RULE_PARAM` 결재 id(없으면 null) |

RuleParamItem:
| 필드 | 타입 | 설명 |
|---|---|---|
| key | string | 변수 키(`ruleJson` 리프 경로) |
| label | string | 표시 라벨 |
| unit | string(nullable) | 단위 자유 텍스트(`%`/`건`/`PHP` 등, 폐쇄 enum 아님) |
| defaultValue | decimal | 카탈로그 기본값 |
| currentValue | decimal | 현재 유효값(override 존재 시 override, 없으면 default) |
| min | decimal(nullable) | 허용 하한(inclusive) |
| max | decimal(nullable) | 허용 상한(inclusive) |
| integerOnly | boolean | 정수 전용 여부 |
| editable | boolean | 편집 가능 여부(read-only 변수는 상신 거부) |
| overridden | boolean | override 적용 여부 |

UpdateRuleParamsRequest (POST `:update-params` body):
| 필드 | 타입 | 필수 | 검증 | 설명 |
|---|---|---|---|---|
| params | map`<string,string>` | ● | 최소 1개, 키=known+editable, 값=수치·[min,max]·정수전용 | 변경할 `param_key → 값` 셋 |
| reason | string | △(nullable) | | 상신 사유(결재 payload/`reason` 보존) |

UpdateRuleParamsResponse (202 Accepted):
| 필드 | 타입 | 설명 |
|---|---|---|
| approvalRequestId | uuid | 생성된 `RULE_PARAM` 결재 요청 id |

> 검증 실패(unknown key·범위 초과·정수 위반·빈 셋)는 `IllegalArgumentException`(400). 승인 EXECUTED 시 `RULE_PARAM_UPDATE` 감사(targetKind=`RULE`, targetRef=`rule_id`).

### 5.10 RiskGroupMemberRequest — `fds_risk_group_members`
`memberRef`(string token ●), `memberKind`(enum `SUBJECT`/`INSTRUMENT`/`COUNTERPARTY`/`COUNTRY`/`VALUE` ●), `expiresAt`(datetime △). 일반 수동 BO 폼은 앞 3종만 선택하며 `COUNTRY`/`VALUE`는 엔진·시스템 관리 그룹용 wire 값이다.

> 외부 request shape는 바뀌지 않는다. **즉시 적용(20260720)** — 멤버 add/remove는 결재를 상신하지 않고 즉시 mutation하며(§4.7), canonical ADD/REMOVE payload(`SHA-256("tenantId|workspaceId|groupId|generationId")`인 `groupGenerationHash` 포함)는 이제 (1) 즉시 적용 `GROUP_UPDATE` 감사의 `afterHash` 산출과 (2) **레거시 in-flight 결재의 실행 경로에만** 사용된다. ADD exact order는 `action`→`groupId`→`groupGenerationHash`→`memberRef`→`memberKind`→`expiresAt`(키 필수, 값 nullable), REMOVE는 `action`→`groupId`→`groupGenerationHash`→`memberRef`다. 레거시 결재 checker 실행은 group row lock 뒤 current generation hash를 먼저 비교하므로 delete/recreate 뒤 stale member approval은 새 generation에 적용되지 않고 `EXECUTION_FAILED`로 끝난다(이 가드는 즉시 적용 경로와 무관하게 레거시 실행에서만 발동).

### 5.11 EvidenceExportRequest — `fds_evidence_exports`
| 필드 | 타입 | 필수 | 매핑 |
|---|---|---|---|
| exportKind | enum `DECISION_TIMELINE`/`CASE_TIMELINE`/`DECISION_REPORT`/`CONNECTOR_RECON`/`FALSE_POSITIVE`/`PII_ACCESS` | ● | `export_kind` |
| exportFormat | enum export_format(`CSV`/`EXCEL`/`PDF`/`JSON_API`) | ● | `export_format` |
| queryParams | object(`from`,`to`,…) | △ | `query_params` |

응답: `exportId`(uuid), `status`(enum export_status), `manifestHash`(string, READY 시), `approvalRequestId`(uuid, nullable — 결재 대상 export이면 반환·비대상이면 null, DB §5.31 `approval_request_id`), `createdBy`(string(128) — 요청 주체, DB §5.31 `created_by NOT NULL` 정본).

### 5.12 ApprovalRequestDto / ApprovalDecisionRequest — `fds_approval_requests`/`fds_approval_steps`
ApprovalRequestDto: `approvalRequestId`(uuid), `subjectKind`(enum subject_kind 11종 `ACTION`/`RULE`/`MAPPING`/`SECRET`/`GROUP`/`EXPORT`/`MERCHANT_NORMALIZE`/`CASE_CLOSE`/`POLICY_PACK`/`RULE_PARAM`/`TENANT_REGULATORY_CURRENCY` = OpenAPI `SubjectKind`), `subjectRef`, `approvalLine`(enum approval_line 6종 = OpenAPI `ApprovalLine`, DB §4.12 `SELF_APPROVAL_DISABLED`/`MAKER_CHECKER`/`COMPLIANCE_MANAGER`/`RISK_MANAGER`/`SECURITY_ADMIN`/`EXECUTIVE_APPROVAL`), `status`(enum approval_status 8종 = OpenAPI `ApprovalStatus`, DB §4.12 `DRAFT`/`SUBMITTED`/`APPROVED`/`REJECTED`/`CANCELLED`/`EXPIRED`/`EXECUTED`/`EXECUTION_FAILED`), `payloadHash`, `payloadJson`(string △, 상세/BO 위임용 staged payload — masked/tokenized, raw PII/secret 미포함. bo-api는 RULE payload의 `statusBeforeSubmit`/`statusAfterSubmit`/`statusAfterApproval`, `fromVersion`/`toVersion`, `reason`, `simulationId` 등에서 `payloadDiff[{field,before,after}]` AS-IS→TO-BE 표를 파생), `makerSubject`, `reason`(string △, 상신 사유 = DB `fds_approval_requests.reason TEXT` §5.23, NULL 허용), `expiresAt`, `maxExecutions`.

> `subjectKind` enum은 DB 정본 `fds_approval_requests.subject_kind` 11종(§5.23)과 1:1. `CASE_CLOSE`=case 종결 4-eyes(대상=`fds_cases.case_id`, §8 case close 행), `POLICY_PACK`=규제 팩 토글 변경 4-eyes(대상=`fds_tenants.tenant_id`, 설계서 §16.2), `RULE_PARAM`=룰 변수(파라미터) 편집 4-eyes(대상=`fds_rules.rule_id`, §8 update-params 행), `TENANT_REGULATORY_CURRENCY`=테넌트 규제통화 전환 4-eyes(대상=`fds_tenants.tenant_id`, 다통화 PLAN 20260818 U17, §4.8a·§8 regulatory-currency:change 행).
ApprovalDecisionRequest(approve/reject): `comment`(string △). checker는 토큰 주체에서 추출(maker≠checker 강제).

### 5.13 CredentialDto / CredentialCreateRequest — `fds_api_credentials`
요청: `credentialType`(enum `API_KEY`/`OAUTH2_CLIENT`/`MTLS`/`WEBHOOK` ●), `scopes`(string[] ●), `ipAllowlist`(string[] △), `webhookUrl`(string △).
응답(생성 1회만): `credentialId`, `secret`(평문 1회 반환 후 미보존 — 이후 AES-GCM `secret_ciphertext`만), `scopes`. 조회 응답에는 raw secret/ciphertext 모두 미노출.

> **`webhookUrl` egress SSRF 검증(P0-17, §9)**: CREATE 상신 시 egress 정책(파싱·allowlist·DNS 해석) 검증 통과 필수 — 위반은 결재 요청 생성 전 400(reason code). 승인 **apply 시점에 staged `webhookUrl`을 재검증**한다(상신~승인 사이 DNS 변경 방어) — apply 재검증 위반은 적용 실패로 기록되고 credential은 반영되지 않는다.

**CredentialDto (GET /admin/fds/credentials 조회 응답)** — `fds_api_credentials` (DB §5.29). secret 필드 미포함.
| 필드 | 타입 | 매핑 |
|---|---|---|
| credentialId | string(96) | `credential_id` |
| credentialType | enum `API_KEY`/`OAUTH2_CLIENT`/`MTLS`/`WEBHOOK` | `credential_type` |
| scopes | string[] | `scopes` (JSONB) |
| ipAllowlist | string[] | `ip_allowlist` (JSONB, 미지정은 명시적 `[]`) |
| webhookUrl | string (nullable) | `webhook_url` |
| enabled | boolean | `enabled` |
| createdAt | datetime | `created_at` |
| updatedAt | datetime | `updated_at` |

> `secret` / `secret_ciphertext`는 조회 응답 미노출(원문 및 암호문 모두). 생성 시 1회만 `secret`을 안전한 발급 채널로 전달한다. 신규 credential의 `allowedProtocolVersions` 기본은 `["v2"]`; migration 이전 row는 `["v1","v2"]`로 전환한다(DB §5.29, 공통 인증 §6). 생성·scope 변경·유예회전·폐기·last-used 이력과 credential별 rate/network/workload 조건은 P1-02 미완료이며 이 DTO만으로 운영 lifecycle을 충족하지 않는다.

### 5.14 ExternalDecisionRequest — `fds_external_decisions` (§5.30)
`vendorName`(string(96) ●), `vendorDecisionRef`(string(256)), `bridgeMode`(enum `ExternalDecisionMode` 5종, ● — `$ref: '#/components/schemas/ExternalDecisionMode'`, §10 OpenAPI), `transactionRef`(string(256)), `vendorDecision`(string(32)), `evidenceHash`(string(128)).

> length·필수는 DB `fds_external_decisions`(§5.30) 컬럼 제약과 1:1: `vendor_name VARCHAR(96) NOT NULL`(●), `bridge_mode VARCHAR(32) NOT NULL`(enum DB §4.18 5종, ●), `vendor_decision_ref VARCHAR(256)`, `vendor_decision VARCHAR(32)`, `evidence_hash VARCHAR(128)`, `transaction_ref VARCHAR(256)`. `bridgeMode` 허용값: `VENDOR_RESULT_INGEST` / `DB_MIRROR` / `DUAL_RUN` / `SHADOW_DECISION` / `RULE_MIGRATION` (DB §4.18 정본).

### 5.15 ConnectorDto (GET /admin/fds/connectors/{connectorId}) — `fds_connector_offsets` (§5.28)
커넥터 단건 health. raw payload·cursor 원문 비노출(cursor는 토큰화/요약, secret 없음).
| 필드 | 타입 | 매핑 | 설명 |
|---|---|---|---|
| connectorId | string(128) | `connector_id` | PK(`{connectorId}`) |
| sourceSystem | string(64) | `source_system` | connector↔source 식별 |
| connectorStatus | enum connector_status (`HEALTHY`/`LAGGING`/`ERROR`/`DISABLED`) | `connector_status` | DB §4.1 enum |
| cursorValue | string | `cursor_value` (요약) | polling cursor 요약(원문 마스킹) |
| lastSuccessAt | datetime | `last_success_at` | 마지막 성공 소비 시각 |
| lastErrorCode | string(120) | `last_error_code` | 최근 오류 코드(메시지·PII 미포함) |
| lagSeconds | long(int64) | `lag_seconds` | reconciliation 지연 지표(DB BIGINT, OpenAPI `format: int64`) |
| updatedAt | datetime | `updated_at` | |

> `{connectorId}`=`connector_id`(connector 경로 변수는 `{connectorId}`로 전수 통일 — replay·pause·resume 동일). data-scope 밖 connector → `FDS-DATASCOPE-DENIED`(403), 격리 밖/미존재 → `FDS-NOT-FOUND`(404).

### 5.15a IngestMetricsResponse (GET /admin/fds/ingest/metrics) — REST 거래 인입 실측

bo-api의 `/api/v1/bo/fds/ingest/health`가 사용하는 저수준 엔진 read API다. 집계 대상은 tenant/workspace 경계 안에서 `transaction_ref IS NOT NULL`인 `fds_canonical_events` row이며, `received_at`을 수신 시각 정본으로 사용한다. 신규 accepted event만 canonical row를 추가하므로 멱등 replay/duplicate는 수신 건수에 재가산되지 않는다. `/events`·`:batch`·`/events/evaluate`별 HTTP 호출량은 canonical row만으로 구분할 수 없으므로 게이트웨이 APM 범위로 분리한다.

| 필드 | 타입 | 설명 |
|---|---|---|
| generatedAt | datetime | 집계 생성 시각(UTC) |
| windowStartedAt | datetime | 24시간 집계 시작(포함) |
| rateWindowSeconds | integer | TPS 관측 구간. 현재 60초 |
| received24h | long(int64) | 최근 24시간 accepted 거래 이벤트 합계 |
| lastReceivedAt | datetime(nullable) | 전체 REST 거래 소스 중 가장 최근 수신 시각 |
| sources | SourceIngestMetric[] | 등록된 `REST_PUSH` source system별 행(미수신 source도 0건/null로 포함) |

`SourceIngestMetric`: `sourceSystem`(string(64)), `enabled`(boolean), `received24h`(long), `lastReceivedAt`(datetime nullable), `tps`(decimal, 최근 `rateWindowSeconds` accepted 건수 ÷ 구간 초).

bo-api health 집계의 `metricSource=MEASURED`; REST 전용이므로 queue depth/DLQ/backfill 호환 필드는 `0`/`null`이다. source별 응답은 low-level 계산 입력으로 유지하되 `/fds/connectors`는 `POST /api/v1/fds/events` 단일 논리 API 한 행으로 합산한다(24h 전체 합계·전체 최신 수신·source별 TPS 합계). API 상태는 metrics 응답 성공 여부로 표시하며 거래 미수신 freshness와 분리한다. bo-api TTL cache와 bo-web query cache는 tenant/workspace를 key에 포함한다.

### 5.16 ConnectorPauseResponse / ConnectorResumeResponse (POST /admin/fds/connectors/{connectorId}/pause·/resume)
일시중지·재개는 상태 전이만 수행(offset/cursor 보존). 멱등 — 이미 목표 상태면 동일 body 재반환.
| 필드 | 타입 | 설명 |
|---|---|---|
| connectorId | string(128) | 대상 connector |
| previousStatus | enum connector_status | 전이 전 상태 |
| connectorStatus | enum connector_status | 전이 후 상태(pause→`DISABLED`, resume→`HEALTHY`) |
| updatedAt | datetime | 전이 시각 |

요청 body(선택): `reason`(string △, 감사 기록용). pause: `DISABLED`로 전이 후 ingest/poll suspend. resume: `DISABLED`→`HEALTHY` 전이 후 보존 offset부터 소비 재개. `DISABLED`가 아닌 connector resume / 이미 `DISABLED`인 connector pause는 멱등 처리하되 상태머신 위반(예: `ERROR` 상태 강제 resume 불가 정책)은 `FDS-STATE-CONFLICT`(409).

### 5.17 SourceSystemUpdateRequest (PUT /admin/fds/source-systems/{id}) — `fds_source_systems` (§5.3) · `control_capability`(DB §4.6)
소스시스템 속성·capability 매트릭스 수정. **4-eyes 대상**(`subjectKind=MAPPING`, source-system 구성 도메인) — 즉시 반영되지 않고 `fds_approval_requests` 생성 후 승인 relay(§8).
| 필드 | 타입 | 필수 | 검증 | 매핑 |
|---|---|---|---|---|
| displayName | string(160) | △ | | `display_name` |
| enabled | boolean | △ | | `enabled` |
| schemaVersion | string(80) | △ | 등록된 mapping 존재(`fds_schema_mappings`) | `schema_version` |
| ingestMode | enum ingest_mode (`REST_PUSH`/`QUEUE`/`POLLING`/`CDC`/`SNAPSHOT`) | △ | DB §4.1 enum | `ingest_mode` |
| failPolicy | enum (`FAIL_CLOSED`/`FAIL_OPEN`/`CASE_ONLY`) | △ | D-14 정본 | `fail_policy` |
| capabilities | enum control_capability[] | △ | DB §4.6 9종 부분집합 | source-system capability 매트릭스 |

- `{id}`=`source_system`(PK `(tenant_id, workspace_id, source_system)`). 최소 1개 필드 필수.
- `capabilities`는 `control_capability` 9종(`CAN_BLOCK_BEFORE_AUTH`/`CAN_DECLINE_AUTH`/`CAN_HOLD_FUNDS`/`CAN_EXTEND_HOLD`/`CAN_RELEASE_HOLD`/`CAN_CANCEL_BEFORE_SETTLEMENT`/`CAN_REQUEST_REVERSAL`/`CAN_SUSPEND_INSTRUMENT`/`CAN_OPEN_CASE_ONLY`)의 **전체 desired set**이다. 필드가 존재하면 빈 배열 `[]`도 유효한 revoke-all이며, checker EXECUTED 때 scoped `fds_capabilities`를 delete+save로 원자 전체 교체한다. action router는 이 매트릭스로 발행 가능 action을 게이트한다(§5.3 Action capability).
- `capabilities`와 일반 설정 필드를 한 요청에 섞으면 400이다. capabilities 필드 존재-only(`[]` 포함)는 immutable `requiredBoCapability=SFDS_ACTION:APPROVE`, 일반 설정-only는 `requiredBoCapability=SFDS_CONNECTOR:OPERATE`로 상신하며 field mapping은 별도 `SFDS_MAPPING:APPROVE` marker를 사용한다(§4.8·§8).
- 응답 SourceSystemDto: `sourceSystem`, `displayName`, `ingestMode`, `schemaVersion`, `enabled`, `failPolicy`, `capabilities[]`, `updatedAt`. 미승인 상신 시 `approvalRequestId`(uuid) + `status=APPROVAL_REQUIRED`(409 `FDS-APPROVAL-REQUIRED` 또는 상신 수락 본문) 반환, 승인 후 반영.

### 5.17a RiskGroupUpsertRequest (POST /admin/fds/risk-groups) — `fds_risk_groups` (§5.21)

fds-svc Java DTO `adapter.in.rest.dto.RiskGroupUpsertRequest`와 exact한 create-only body다. 세 필드 모두 필수이며 BO 전용 `displayKind`/`active`/`reason`은 engine create wire에 포함하지 않는다.

| 필드 | 타입 | 필수 | 검증 | 매핑 |
|---|---|---|---|---|
| groupId | string(96) | ● | nonblank, ≤96. scoped create-only key | `group_id` |
| groupType | enum risk_group_type (DB §4.14, 7종) | ● | known enum, 생성 후 immutable | `group_type` |
| displayName | string(160) | ● | nonblank, ≤160 | `display_name` |

성공은 `201 Created` + `RiskGroupDto`다. create는 새 `generation_id`를 발급해 즉시 effective master로 저장하며, 동일 `(tenant_id,workspace_id,group_id)`가 존재하면 `409 FDS-STATE-CONFLICT`로 거부하고 기존 master/member/audit를 덮어쓰지 않는다. 삭제 후 같은 ID를 재생성하면 이전과 다른 generation이므로 과거 master/member/merchant-normalize approval은 새 그룹에 자동 재결속하지 않는다.

### 5.18 RiskGroupMasterUpdateRequest (PUT /admin/fds/risk-groups/{groupId}) — `fds_risk_groups` (§5.21)

위험그룹 마스터(틀) 수정/비활성. **4-eyes 대상**(`subjectKind=GROUP`, subjectRef=`group_id`, §8) — 즉시 반영되지 않고 `fds_approval_requests` 생성 후 승인 relay. **DB `fds_risk_groups` 컬럼에 정합하는 필드만 수정 가능**(아래 표). PRD SFDS-GRP-003 화면의 `source`/`autoEnrollOnHit`/`defaultExpiryDays`/`description`은 `fds_risk_groups` 컬럼 부재로 본 마스터 PUT의 영속 대상이 아니다(룰 빌더·멤버 정책에서 관리, 추측 컬럼 미생성).

> **BFF/engine envelope 경계**: bo-web→bo-api 요청은 선택된 `groupId`를 path와 body에 모두 넣고 bo-api가 nonblank·최대 96자·exact 일치를 먼저 검증한다. 그 검증을 통과한 뒤 bo-api→fds-svc typed engine 요청은 path `groupId`를 identity 정본으로 사용하고, 아래 body에는 변경 필드와 immutable `groupType` echo만 보낸다. 따라서 OpenAPI `RiskGroupMasterUpdateRequest`에 `groupId`가 없는 것은 의도된 내부 engine 계약이다.

상신 성공은 **202 Accepted**이며 변경 전/current `RiskGroupDto` projection에 `approvalRequestId`(UUID)와 `status=APPROVAL_REQUIRED`만 붙여 반환한다. 이 시점에는 `fds_risk_groups` mutation과 `GROUP_UPDATE` 감사가 없다. staged payload는 `action=MASTER_UPDATE`, path와 같은 `groupId`, 저장값과 같은 `groupType`, 상신 당시 current master generation을 포함한 canonical `baseMasterHash`, 변경 필드, maker `reason`, 유효한 request causal trace만 포함한다. `baseMasterHash`는 exact `SHA-256("tenantId|workspaceId|groupId|generationId|groupType|displayName")`이며 `active`는 hash material이 아니라 staged 변경 필드다. strict field-shape 검증 뒤 staged semantic JSON을 `action` → `groupId` → `groupType` → `baseMasterHash` → 선택적 `displayName` → 선택적 `active` → `reason` → 선택적 `causalTraceId`의 고정 순서로 재직렬화해 hash한다. PostgreSQL JSONB key 재배열·입력 key 순서·공백은 무결성 의미가 아니며, submit/current/apply가 같은 canonical helper를 사용한다. checker는 group row lock 뒤 current generation을 포함한 master hash와 `baseMasterHash`를 비교하므로 같은 base의 out-of-order approval뿐 아니라 delete/recreate generation ABA도 `EXECUTION_FAILED`로 막고 최신 effective 값을 되돌리지 않는다. approval은 `GROUP`/`RISK_MANAGER`; maker와 다른 checker만 실행할 수 있다.

| 필드 | 타입 | 필수 | 검증 | 매핑 |
|---|---|---|---|---|
| displayName | string(160) | △ | 비공백, ≤160 | `display_name` |
| active | boolean | △ | 비활성(`false`) 시 멤버 0 선결(BR-001) | (상태 전이, §5.18 주) |
| groupType | enum risk_group_type (DB §4.14, `RISK_COUNTRY` 포함) | △(에코) | **변경 불가** — 저장값과 상이 시 거부(BR-002) | `group_type`(read-only) |
| reason | string(500) | ● | 비공백, ≤500 | maker 결재 사유(`fds_approval_requests.reason`), 성공 master 감사 detail에는 원문 미복제 |

- `{groupId}`=`group_id`(PK `(tenant_id, workspace_id, group_id)`). 최소 1개 수정 필드(`displayName`·`active`) 필수 — 둘 다 없으면 `FDS-VALIDATION-001`.
- **`group_id`(=groupCode)·`group_type`(=kind) immutable**(BR-001/BR-002). path `groupId`는 식별자이며 변경 불가. body에 `groupType`을 포함할 경우 저장값과 동일해야 하며, 상이하면 `FDS-VALIDATION-002`(enum/immutable 위반)로 거부.
- **비활성(`active=false`)**: `fds_risk_groups`에 전용 `enabled` 컬럼이 없으므로 비활성은 **멤버 전건(`fds_risk_group_members`) 0 선결** 후 checker 실행 시 그룹 정의를 삭제한다. 상신 시와 checker 실행 시 멤버 수를 모두 검사하며, 어느 시점이든 멤버가 남아 있으면 상신은 409 또는 실행은 `EXECUTION_FAILED`로 끝나고 master는 유지된다. watchlist/denylist 평가 제외는 승인 적용 시점부터 효력이 난다.
- `groupType` 변경이 필요하면 새 그룹을 생성한다(멤버 식별자 체계 상이, BR-002).
- 승인 실행은 staged action/subject/approval line/group id/type/field shape와 위 고정 semantic canonical hash를 다시 검증한다. rename은 `display_name`과 `updated_by`(checker)/`updated_at`을 저장하고, `active=false`는 위 조건에서 정의를 삭제한다. 성공한 실행만 `GROUP_UPDATE`(checker actor, staged causal trace 우선, canonical before/after hash)를 기록한다. 반려·자기승인·payload drift·business 재검증 실패는 effective master를 바꾸지 않고 성공 감사를 만들지 않으며, business 재검증 실패만 `EXECUTION_FAILED`다. save/delete/audit persistence 예외는 삼키지 않고 전파해 동일 승인 트랜잭션의 step/status/master/audit를 전부 rollback하므로 원 결재는 `SUBMITTED`로 남아 재시도할 수 있다.

### 5.19 RiskGroupDto (응답) — `fds_risk_groups` (§5.21)

위험그룹 마스터 단건. raw PII 없음(`group_id`/`display_name`은 운영 식별자, 멤버 token은 미포함).

| 필드 | 타입 | 매핑 |
|---|---|---|
| groupId | string(96) | `group_id` |
| groupType | enum risk_group_type (DB §4.14, `RISK_COUNTRY` 포함) | `group_type` |
| displayName | string(160) | `display_name` |
| memberCount | integer | (`fds_risk_group_members` count, 비활성 선결 판정용) |
| createdBy / updatedBy | string(128, 운영자 token) | `created_by` / `updated_by` |
| createdAt / updatedAt | datetime | `created_at` / `updated_at` |
| approvalRequestId | uuid (nullable) | PUT 미승인 상신 시 canonical 결재 UUID. 목록·POST에는 없음 |
| status | string (nullable) | PUT 미승인 상신 시 exact `APPROVAL_REQUIRED`. 목록·POST에는 없음 |

> PUT 미승인 상신은 **202**로 변경 전/current projection + `approvalRequestId` + `status=APPROVAL_REQUIRED`를 반환한다. 승인 전에는 `display_name`/그룹 정의가 변하지 않으며, 다른 checker가 실행한 뒤 rename 또는 `active=false` 정의 삭제가 반영된다. `group_id`·`group_type`은 응답에 노출되나 read-only.

### 5.20 MerchantNormalizeRequest (POST /admin/fds/merchants/{merchantRef}/normalize) — 4-eyes 상신

high-risk merchant 정상화(차단/제약 해제) 상신. **4-eyes 대상**(`subjectKind=MERCHANT_NORMALIZE`, subjectRef=`merchant_ref`, §8) — 즉시 실행되지 않고 `fds_approval_requests` 생성 후 승인 relay. `merchant_ref`는 token(원문 PII 아님). 정상화는 설계서 §11.5 SUSPEND_INSTRUMENT(대상=MERCHANT_ACCOUNT) 등 제약 액션의 해제 환원에 해당한다.

| 필드 | 타입 | 필수 | 매핑 |
|---|---|---|---|
| reason | string | ● | (감사·결재 사유, `fds_approval_requests.reason`) |
| scope | enum `SINGLE`/`BULK` | △ | 대규모(`BULK`) 시 `approvalLine=EXECUTIVE_APPROVAL`(설계서 §11.5) |

> 응답: `approvalRequestId`(uuid) + `status=APPROVAL_REQUIRED`(409 `FDS-APPROVAL-REQUIRED` 또는 상신 수락 본문). `approvalLine`은 bo-api 승인 라인 정책 소유 — 기본 `RISK_MANAGER`, 대규모(`BULK`)는 `EXECUTIVE_APPROVAL`. 상신 시 merchant가 속한 위험그룹을 `groupId` 오름차순으로 정렬한 exact `groups[{groupId,generationHash}]` snapshot을 canonical payload에 필수 저장한다. 각 `generationHash`는 해당 그룹의 `SHA-256("tenantId|workspaceId|groupId|generationId")`이며 전체 normalize canonical order는 `action`→`merchantRef`→`scope`→`reason`→`groups`다. current/list/get/approve/apply가 동일 schema·정렬·hash를 사용하고, checker는 모든 group row lock을 잡아 모든 generation을 mutation 전에 재검증한다. 어느 한 그룹이라도 삭제·재생성되었으면 stale normalize는 `EXECUTION_FAILED`이고 새 generation의 멤버를 제거하지 않는다. generation 증명이 없는 legacy pending은 실행하지 않는다.

### 5.21 CaseEventDto (GET /fds/cases/{caseId}/events) — `fds_case_events` (§5.14)

case timeline 단건(append-only). raw PII 없음(`payload`는 마스킹, `actorSubject`는 운영자 token). 시간순(`createdAt,asc`) 페이지네이션(§3.2).

| 필드 | 타입 | 매핑 | 설명 |
|---|---|---|---|
| caseEventId | uuid | `case_event_id` | PK |
| caseId | uuid | `case_id` | 소속 case |
| eventKind | enum case_event_kind (6종 `ASSIGNED`/`COMMENT`/`STATUS_CHANGE`/`EVIDENCE_ATTACHED`/`APPROVAL`/`CLOSED`) | `event_kind` | DB §5.14 허용값 |
| payload | object (nullable) | `payload` | 이벤트 상세(마스킹, PII 미포함) |
| actorSubject | string(128, nullable) | `actor_subject` | 수행 운영자 token |
| createdAt | datetime | `created_at` | 불변 |

> `event_kind` 6종은 DB §5.14 정본과 1:1. 응답 envelope는 §3.2 목록 페이지네이션 포맷(`content[]`)을 따른다.

### 5.22 NotifyChannelDto (GET/PUT /admin/fds/notify-channels) — `fds_notify_channels` (§5.34)

tenant 알림 채널 1건(설계서 §13.2 alert channel, PRD TNT-002 ⑤). GET은 `NotifyChannelDto[]`, PUT 요청 body는 `{ "channels": NotifyChannelDto[] }`(전체 desired state — **전체 교체·멱등**), PUT 응답은 교체 후 `NotifyChannelDto[]`. raw PII 없음(`target`은 운영 설정값). **확정**(엔진 T8 FDS-ENG-04 구현 완료 — 컨트롤러 매핑·도메인·Flyway `V14`·감사·Testcontainers 통합 테스트).

| 필드 | 타입 | 매핑 | 설명 |
|---|---|---|---|
| channel | enum notify_channel_type (3종 `SLACK`/`EMAIL`/`WEBHOOK`) | `channel` | 미지원 값 400 `FDS-VALIDATION-001` |
| target | string(512) | `target` | 채널명/주소/URL. WEBHOOK은 `http(s)` URL 강제 + egress SSRF 정책(P0-17, §9) 파싱·allowlist·DNS 해석 검증 통과 필수(위반 400, reason code) |
| events | enum[] (§9.1 webhook eventName 4종 부분집합) | `events`(CSV) | null/빈 배열 허용. 미지원 값 400 `FDS-VALIDATION-001` |

> 멱등: `(channel, target)` 자연키 기준 전체교체 — 동일 payload 재PUT 시 동일 최종 상태·중복 감사 없음. 변경 시 `fds_audit_logs`(`audit_action=NOTIFY_CHANNEL_CHANGE`) 1건. webhook target URL 변경 시 응답 헤더 `X-Webhook-Url-Changed: true` + 감사 detail `rotateRequired=true`(서명키 rotate 정책 §13.2 BR-003 연계 신호 — 실제 rotate 상신/실행은 credential admin 4-eyes 경로). 엔진 scope `fds:admin:source-system`만 강제, 운영자 역할(`SFDS_TENANT:ADMIN`) 게이트는 bo-api 소유(후속 T16).

---

## 6. 에러 코드

| 코드 | HTTP | 의미 | 발생 API |
|---|---|---|---|
| `FDS-VALIDATION-001` | 400 | 요청 필드 검증 실패 | 전체 |
| `FDS-VALIDATION-002` | 400 | enum 코드값 불일치 또는 immutable 위반(decision/action/case/channel/connector_status/control_capability/ingest_mode/risk_group_type·`group_type` 변경…) | 전체 |
| `FDS-PII-REJECTED` | 422 | raw PII(PAN·계좌·이메일·KR 주민등록번호) 포함 payload reject — `canonicalPayload` 방어 스캔(§5.1·§16.1, persist/outbox/log 이전) 검출 시, `originator` 문자열 필드(fullNameLatin/phone/identification 등) raw PII 스캔 검출 시(§5.1 originator 주체 계약 note) 포함. reason=PII class+field path(원문 미포함) | Ingest/Decision |
| `FDS-SCHEMA-UNKNOWN` | 422 | 등록되지 않은 `source_system`/`schema_version` | Ingest/Decision |
| `FDS-CONTRACT-VIOLATION` | 422 | transaction 통화 계약 위반(§5.1) — leg-전무(4필드+레거시 amount/currency 모두 부재) / `amount↔sendAmount`·`currency↔sendCurrency` 불일치 / `counterparty.accountNoHash` 형식 위반(제어문자·64자 초과) / `originator.partyReference`↔legacy `subject.subjectRef` 불일치 / `originator.partyType` 닫힌 enum(`INDIVIDUAL`/`LEGAL_ENTITY`) 이탈 / `device.deviceRef`↔`device.deviceId` 불일치 / `device.os`·`device.version`·`device.ip` 64자 초과·제어문자(§5.1 originator/device note). persist 이전 검출·rejection 은 배치 per-item 보고(예외 미발생) | Ingest/Decision |
| `FDS-AUTH-001` | 401 | 필수 인증 identity/header 부재(`Tenant-Id`/API key/토큰) | 전체 |
| `FDS-AUTH-002` | 401 | generic machine-auth 실패(credential/protocol/version/nonce/timestamp/canonical/signature/replay 원인을 외부에 구분하지 않음) | HMAC API |
| `FDS-AUTH-003` | 503 | nonce replay store 불가 — 인증 fail-closed | HMAC v2 API |
| `FDS-AUTH-004` | 413 | 인증 raw-body 상한 초과 | HMAC API |
| `FDS-AUTHZ-001` | 403 | 권한 부족 | 전체 |
| `FDS-AUTHZ-002` | 403 | scope 불일치 | 전체 |
| `FDS-AUTHZ-003` | 403 | cross-workspace 접근 차단 | 전체 |
| `FDS-DATASCOPE-DENIED` | 403 | data-scope 밖 row 접근 | 조회/조치 |
| `FDS-NOT-FOUND` | 404 | 리소스 없음(격리 밖 포함) | 전체 |
| `FDS-IDEMPOTENT-CONFLICT` | 409 | 동일 key 다른 payload | 멱등 API |
| `FDS-STATE-CONFLICT` | 409 | 상태 전이/create-only key 충돌(예: 이미 CLOSED case, connector `ERROR` 강제 resume, 멤버 잔존 그룹 비활성, 동일 scoped 위험그룹 master 중복 생성) | Case/Action/Approval/Connector/Group |
| `FDS-APPROVAL-REQUIRED` | 409 | 결재 없이 실행 시도 | Action/Rule/Group/Credential/SourceSystem/MerchantNormalize |
| `FDS-APPROVAL-SELF` | 409 | maker=checker 승인 시도 | Approval |
| `FDS-APPROVAL-STATE` | 409 | 현재 상태에서 결정 불가. BO V19 terminal GROUP tombstone의 재승인·반려·apply 포함 | Approval |
| `FDS-APPROVAL-PAYLOAD-INVALID` | 409 | BO local staged payload/역사 tombstone shape·marker·저장 hash 상관 불일치 | Approval |
| `FDS-APPROVAL-PAYLOAD-CHANGED` | 409 | 승인 후 payload_hash 변경 | Approval/실행 |
| `FDS-APPROVAL-DUPLICATE` | 409 | 같은 subject에 활성(SUBMITTED) 승인 요청 중복(P0-10 — 특히 CASE_CLOSE는 케이스당 활성 종결 승인 최대 1개). 애플리케이션 중복 가드(`findActiveBySubject`) 또는 부분 유니크 인덱스 `uk_fds_approval_pending_case_close`(DB §5.23) 위반 시 | Approval |
| `FDS-AML-DELEGATED` | 409 | AML 본 처리는 aml-svc 위임 대상 | Case |
| `FDS-FAIL-CLOSED` | 503 | 평가 불가 + fail-closed 정책 | Decision |
| `FDS-RATE-LIMIT` | 429 | rate limit 초과 | 전체 |

---

## 7. reason code / decision code 사전

### 7.1 decision code (응답 `decision`, DB enum decision §4.7)
`ALLOW` · `MONITOR` · `REVIEW` · `CHALLENGE` · `BLOCK` · `HOLD` · `FREEZE` · `REPORT`

### 7.2 reasonCodes 예시 (`fds_decision_reasons.reason_code`) — hanpass-ph
송금·월렛 도메인 reasonCode 예시: `HIGH_AMOUNT_PHP_EQUIVALENT`(PHP 환산 고액, §3.5.3) · `NEW_BENEFICIARY`(신규 수취인) · `TRANSFER_VELOCITY`(송금 속도) · `STRUCTURING`(분할입금, DOMESTIC velocity) · `MULE_ACCOUNT_GROUP`(머니뮬 그룹) · `GEO_MISMATCH`(corridor 불일치) · `SANCTION_HIT`(제재 적중) · `WALLET_WITHDRAWAL_ANOMALY`(월렛출금 이상) · `WATCHLIST_HIT`(워치리스트). reason_code는 free-form 허용하되 catalog 권장. (카드/crypto/무역/seller 등 비-hanpass reasonCode는 운영 미사용.)

> recommendedActions는 enum action_type(22종) 코드값으로만 반환.

---

## 8. 4-eyes 결재 대상 엔드포인트

설계서 §11.4/§11.5 기준. 아래 호출은 즉시 실행되지 않고 `fds_approval_requests` 생성 → `status=APPROVAL_REQUIRED`/`SUBMITTED` → checker 승인 후 relay/실행.

| 엔드포인트 | subjectKind | 기본 approval_line |
|---|---|---|
| `POST /fds/cases/{caseId}/actions` (자금/규제 action) | `ACTION` | `MAKER_CHECKER` / `EXECUTIVE_APPROVAL`(대규모) |
| `POST /fds/cases/{caseId}/close` (내부감사·규제 case) | `CASE_CLOSE` (subjectRef=`case_id`, 케이스당 활성 SUBMITTED 최대 1개 — 중복 시 `409 FDS-APPROVAL-DUPLICATE`; 반려 시 직전 상태 복구 §4.4) | `COMPLIANCE_MANAGER` |
| `POST /admin/fds/rules/{ruleId}/activate` · `/rollback` | `RULE` | `COMPLIANCE_MANAGER` |
| `POST /admin/fds/rules/{ruleId}:update-params` (룰 변수 편집) | `RULE_PARAM` (subjectRef=`rule_id`) | `COMPLIANCE_MANAGER` |
| `PUT /admin/fds/source-systems/{ss}/mappings` | `MAPPING` (`requiredBoCapability=SFDS_MAPPING:APPROVE`) | `MAKER_CHECKER` |
| `PUT /admin/fds/source-systems/{id}` capabilities-only | `MAPPING` (`requiredBoCapability=SFDS_ACTION:APPROVE`, subjectRef=`source_system`) | `MAKER_CHECKER` |
| `PUT /admin/fds/source-systems/{id}` 일반 설정-only | `MAPPING` (`requiredBoCapability=SFDS_CONNECTOR:OPERATE`, subjectRef=`source_system`) | `MAKER_CHECKER` |
| `PUT /admin/fds/risk-groups/{groupId}` (마스터 수정/비활성) | `GROUP` (subjectRef=`group_id`) | `RISK_MANAGER` |
| ~~`POST` · `DELETE /admin/fds/risk-groups/{groupId}/members`~~ | `GROUP` | `RISK_MANAGER` — **(폐지 20260720 — 즉시 적용, `200 GroupMemberMutationResponse`. 레거시 in-flight pending 결재의 실행만 잔존)** |
| `POST /admin/fds/credentials` · `/rotate` | `SECRET` | `SECURITY_ADMIN` |
| `POST /evidence/fds/exports` (제출용 최종본) | `EXPORT` | `COMPLIANCE_MANAGER` |
| `POST /admin/fds/merchants/{merchantRef}/normalize` (high-risk merchant 정상화) | `MERCHANT_NORMALIZE` (subjectRef=`merchant_ref`) | `RISK_MANAGER`(기본) / `EXECUTIVE_APPROVAL`(대규모 예외) |
| `PUT /api/v1/bo/fds/tenants/{tenantId}` (규제 팩 `compliance_policy` 토글 변경) | `POLICY_PACK` (subjectRef=`tenant_id`, 설계서 §16.2) | `COMPLIANCE_MANAGER` |

규칙: 상신 action·필드 payload는 `payload_hash`로 고정하고, 위 세 `MAPPING` 작업의 staged `payload_json.requiredBoCapability`는 생성 뒤 변경하지 않는 checker/apply 판정 입력이다. capabilities와 일반 설정의 혼합 요청은 상신 전에 400, marker 누락·미지 legacy row는 checker 판정에서 fail-closed한다. fds-svc 승인 실행도 `action↔requiredBoCapability↔payload field shape` 상관을 다시 검증하며 unknown/mismatch/mixed payload는 업무 mutation 없이 `false`를 반환해 결재를 `EXECUTION_FAILED`로 끝낸다. valid `SS_UPDATE` capabilities-only는 `(tenant,workspace,sourceSystem)`의 `fds_capabilities` 전체 셋을 원자 교체하고, general-only는 `fds_source_systems`만 merge하며, `MAPPING_CHANGE`는 `fds_schema_mappings`만 ACTIVE 저장한다. 위험그룹 관련 `GROUP` master와 `MERCHANT_NORMALIZE`는 상신 당시 generation 증명을 필수 결속하고 row lock 뒤 current generation을 mutation 전에 비교한다. master는 generation 포함 `baseMasterHash`, normalize는 groupId 오름차순 `groups[{groupId,generationHash}]` exact snapshot을 쓴다. generation mismatch·legacy 증명 부재는 새 incarnation에 재결속하지 않고 mutation 0의 `EXECUTION_FAILED`다. **member ADD/REMOVE의 `groupGenerationHash` 결속·row lock 비교는 20260720부터 즉시 적용 경로(§4.7)의 `GROUP_UPDATE` 감사 afterHash 산출에만 쓰이며 결재 실행 가드가 아니다 — 이 가드는 배포 시점에 잔존한 레거시 in-flight 멤버 결재의 실행 경로에서만 여전히 발동한다(§5.10).** valid master PUT만 rename 또는 멤버 0인 `active=false` 정의 삭제 후 `GROUP_UPDATE`를 만든다. 승인 후 payload 변경 시 무효(`FDS-APPROVAL-PAYLOAD-CHANGED`). 승인↔실행 분리 저장(`fds_approval_steps` vs action relay). 운영자 IAM·승인 라인 정책은 bo-api 소유.

bo-api V19 이전 local `GROUP` 이력은 API projection에서 임의로 현 generation에 재결속하지 않는다. migration은 모든 기존 local GROUP payload를 exact `action=LEGACY_GENERATION_UNBOUND`/`migration=V19`/`legacyPayload=<old jsonb>`/`legacyPayloadHash=<old payload_hash>` 4필드 tombstone으로 감싸고 `payload_hash` 컬럼을 보존한다. 비종결 `DRAFT`/`SUBMITTED`/`APPROVED`/`APPROVED_PENDING_ENGINE`는 `CANCELLED`; terminal row는 상태를 보존하되 exact marker·terminal status·`legacyPayloadHash == payload_hash`를 모두 통과할 때만 역사 조회할 수 있다. 이 이력의 approve/reject/apply는 `409 FDS-APPROVAL-STATE`로 금지하며 marker-like drift(추가·누락 필드, 잘못된 migration/action/hash)는 `409 FDS-APPROVAL-PAYLOAD-INVALID`로 fail-closed해 원문을 정상 결재처럼 투영하지 않는다.

---

## 9. Webhook 콜백 계약 (outbound)

설계서 §12.8 'Webhook API'를 정본으로 확정한다. fds-svc는 decision/case/action 이벤트를 서비스 등록 URL로 **outbound HTTP POST** 발행한다(`fds_api_credentials.credential_type=WEBHOOK`, `webhook_url`/AES-GCM `secret_ciphertext` 사용, `/admin/fds/credentials/{id}/rotate`로 회전). bo-web/bo-api 운영자 화면과 무관한 **서비스 서버 간 콜백** 채널이다.

> **전송 어댑터 구현 확정(T10)**: 전송은 `fds_webhook_outbox`(DB §5.35, transactional outbox) + 스케줄드 디스패처(`WebhookRelayScheduler`/`WebhookRelayService`/`HttpWebhookSenderAdapter`, 연동 §6.2.2)로 실현된다 — 도메인 변경 트랜잭션 내 enqueue → `SELECT … FOR UPDATE SKIP LOCKED` 클레임 → 서명 POST → 2xx `DISPATCHED` / 비2xx·타임아웃 `FAILED`+지수 backoff(MAX 5) → `DEAD_LETTERED`(DLQ + `WEBHOOK_DEAD_LETTER` 감사). `sandbox`는 미발행(shadow). **아웃바운드 webhook** 서명 material(`timestamp + "." + rawBody`)은 [인바운드 machine-auth v2](00-common-machine-auth.md)의 preamble/query/scopeContext/digest/nonce canonical bytes와 별개이며 혼용하지 않는다. fds/aml 양 엔진 아웃바운드 공식은 동일하다(AML §8.3).

> **egress SSRF 정책(P0-17)**: outbound webhook 대상 URL은 양 엔진 공통 `com.aegis.common.security.egress.WebhookUrlPolicy`(`common-security` 모듈, 전송은 `NoRedirectRequestFactory` 결합)가 **3단계 검증**으로 통제한다. ① **파싱** — absolute URI·host 필수, user-info/fragment 금지(금지 시 각 `USER_INFO_FORBIDDEN`/`FRAGMENT_FORBIDDEN`). production tier(활성 프로파일 `prod`/`production`/`aws`)는 `https`만 + port 443/8443/스킴 기본만 허용, 비-production은 `http`/`https`·port 무제한(로컬 수신기 허용). ② **allowlist** — `aegis.fds.webhook.allowed-host-suffixes`(env `FDS_WEBHOOK_ALLOWED_HOST_SUFFIXES`, 콤마 구분·빈 값=비활성) 설정 시 host가 suffix와 일치(`.` 경계 또는 exact host, 대소문자 무시)해야 한다. ③ **DNS 해석** — 반환된 **모든 A/AAAA 레코드**를 검사한다. production은 loopback·RFC1918·`fc00::/7`·link-local(cloud metadata `169.254.169.254`/`fe80::` 포함)·multicast·`0.0.0.0/8` 전체·broadcast·CGNAT(`100.64/10`)와 IPv4-mapped(`::ffff:`)·NAT64(`64:ff9b::/96`) 임베디드 내부 IPv4 전부 거부, 비-production은 link-local(metadata)만 tier 무관 거부하며, mixed answer 중 1건이라도 위험이면 URL 전체 거부. 위반 **reason code 9종** = `NOT_ABSOLUTE`/`HOST_MISSING`/`SCHEME_NOT_ALLOWED`/`USER_INFO_FORBIDDEN`/`FRAGMENT_FORBIDDEN`/`PORT_NOT_ALLOWED`/`HOST_NOT_ALLOWLISTED`/`HOST_UNRESOLVABLE`/`ADDRESS_BLOCKED`. **적용 시점** — 등록(notify-channels PUT §4.8/§5.22, credential CREATE 상신+승인 apply 재검증 §5.13) + **매 전송 직전 재검증**(위반=`URL_BLOCKED` delivery 실패). **redirect 미추종** — `setInstanceFollowRedirects(false)`로 3xx는 `REDIRECT_REFUSED` delivery 실패로 기록한다(hop 미추적, 기존 `FAILED`+지수 backoff 계약 유지·신규 상태 없음). **한계·백스톱** — DNS rebinding은 검증과 connect가 같은 JVM DNS positive cache TTL 내에 이뤄져 TOCTOU 창을 완화할 뿐이므로, egress proxy/network policy로 내부 대역 outbound를 차단하는 배포 요건이 백스톱이다(운영 runbook = 코드 레포 `docs/ops/webhook-egress-policy.md`).

### 9.1 이벤트 타입 (`eventName`)
| eventName | 트리거 | 발행 주체(엔진) | 핵심 payload |
|---|---|---|---|
| `FdsDecisionCreated` | decision 생성 | Decision Engine | `decisionId`,`decision`,`reasonCodes`,`riskScore`,`recommendedActions`(action_type[]) |
| `FdsCaseOpened` | case origin 생성 | Case Mgmt | `caseId`,`caseType`,`priority`,`originDecisionId` |
| `FdsCaseStatusChanged` | case 상태 전이 | Case Mgmt | `caseId`,`fromStatus`,`toStatus`,`closeReason`(nullable) |
| `FdsActionResult` | action relay 결과(SENT→ACKED/FAILED 전이) | Action relay | `actionId`,`actionType`(action_type 22종, 필수),`status`(enum action_status: §10 OpenAPI `ActionStatus` 7종 / DB §4.9, 통상 `ACKED`/`FAILED`),`errorCode`(nullable) |

> 4종은 정본 콜백 집합. enum 코드값은 DB §4와 동일(action_type 22종·case_type·action_status·case_status). raw PII 미포함(token/hash·마스킹만).

### 9.2 공통 envelope
```json
{
  "schemaVersion": "fds.webhook.v1",
  "eventFamily": "decision",
  "eventName": "FdsDecisionCreated",
  "eventId": "evt_8f3c...",
  "tenantId": "...", "workspaceId": "...",
  "occurredAt": "2026-06-06T01:02:03Z",
  "traceId": "8f3c...",
  "data": { /* §9.1 핵심 payload */ }
}
```
- 모든 키 **camelCase** 직렬화. **webhook envelope의 `eventFamily`는 콜백 그룹핑 enum `decision`/`case`/`action` 3종**이며, `eventName` 접두에서 도출한다(`FdsDecisionCreated`→`decision`, `FdsCaseOpened`·`FdsCaseStatusChanged`→`case`, `FdsActionResult`→`action`). **이는 canonical event_family(설계 §8.1 / DB `event_family` 16종)와 별개 도메인**이다 — ingest 경로의 `event_family`(16종 정규 분류)와 webhook 콜백 그룹핑을 혼동하지 않는다(정본 분리: integration·design webhook 인용은 본 §9.2 3종 enum을 따른다).

### 9.3 서명·검증
- 헤더 `X-Signature: hmac-sha256=<hex>` = HMAC-SHA256(secret, `timestamp + "." + rawBody`). 헤더 `X-Webhook-Timestamp`(epoch ms) 동봉, 수신 측 ±5분 허용으로 replay 방어.
- secret은 credential WEBHOOK의 AES-GCM `secret_ciphertext`를 발송 시점에만 복호화해 사용한다(raw secret 미저장·미로그). 회전 시 새 credential ID 병행 발급→client 전환→clock skew+nonce TTL 경과 후 구 credential 비활성화를 기본으로 한다(공통 인증 §6).

### 9.4 재시도·멱등
- 2xx 미수신 시 지수 backoff 재시도(예: 0s/30s/2m/10m/1h, 최대 24h). 최종 실패는 DLQ + 운영자 알림.
- `eventId`로 **at-least-once** 보장 — 수신 측은 `eventId` 기준 멱등 처리. 동일 이벤트 재전송 시 `eventId`·payload 불변.

> 본 콜백은 outbound(fds-svc→서비스)다. adapter→fds-svc **내부 ack**(`FdsActionResult` 큐 소비로 outbox 상태 SENT→ACKED/FAILED 전이)는 별개 채널이며 외부 webhook 노출 대상이 아니다(integration 명세 §4.3).

---

## 10. OpenAPI(YAML) 스니펫

```yaml
openapi: 3.0.3
info:
  title: FDS Service API
  version: v1
servers:
  - url: https://api.fds.example/api/v1
components:
  securitySchemes:
    ApiKeyHmac:
      type: apiKey
      in: header
      name: X-Api-Key
    OAuth2:
      type: oauth2
      flows:
        clientCredentials:
          tokenUrl: https://auth.fds.example/oauth/token
          scopes:
            fds:event:write: 이벤트 수신
            fds:decision:evaluate: 실시간 판단
            fds:case:read: 케이스 조회
            fds:case:update: 케이스 변경
            fds:evidence:export: 증적 export
            fds:rule:simulate: 룰 시뮬레이션
            fds:admin:rule: 룰 관리
            fds:admin:group: 그룹 관리
            fds:admin:source-system: 소스/커넥터 관리
            fds:admin:credential: 자격증명 관리
            fds:action:write: 액션 상신
            fds:internal:customer-profile:write: AML CDD profile internal write only
  parameters:
    TenantId:
      name: Tenant-Id
      in: header
      required: true
      schema: { type: string, maxLength: 64 }
    WorkspaceId:
      name: Workspace-Id
      in: header
      required: false
      schema: { type: string, maxLength: 64, default: default }
    SourceSystem:
      name: Source-System
      in: header
      required: false
      schema: { type: string, maxLength: 64 }
    IdempotencyKey:
      name: Idempotency-Key
      in: header
      required: true
      schema: { type: string, maxLength: 256 }
    Timestamp:
      name: X-Timestamp
      in: header
      required: true
      schema: { type: string, format: date-time }
    AuthVersion:
      name: X-Auth-Version
      in: header
      required: true
      schema: { type: string, enum: ['2'] }
    Nonce:
      name: X-Nonce
      in: header
      required: true
      schema: { type: string, pattern: '^[A-Za-z0-9_-]{22}$' }
    Signature:
      name: X-Signature
      in: header
      required: true
      schema: { type: string, pattern: '^hmac-sha256=[0-9a-f]{64}$' }
    DataScope:
      name: X-Data-Scope
      in: header
      required: false
      schema: { type: string, maxLength: 128 }
    InternalService:
      name: X-Internal-Service
      in: header
      required: true
      schema: { type: string, enum: [aml-svc] }
  schemas:
    Decision:
      type: string
      description: 판정 결과(fds_decisions.decision, DB §4.7 8종).
      enum: [ALLOW, MONITOR, REVIEW, CHALLENGE, BLOCK, HOLD, FREEZE, REPORT]
    ChannelType:
      type: string
      description: >
        hanpass-ph 운영 채널(com.aegis.fds.domain.enums.ChannelType, §3.5.1).
        운영 5종만 사용. ChannelType enum은 닫힌 집합으로 비-hanpass 코드를 멤버 보존하나 hanpass-ph는 아래 5종만 emit.
      enum: [CROSS_BORDER_REMIT, DOMESTIC_REMIT, CASH_IN, WALLET_PAYMENT, WALLET_WITHDRAWAL]
    EvaluateDecisionRequest:
      type: object
      description: 동기 평가 요청(DecisionQueryController.EvaluateRequest, §5.3). 참조 기반 경량 body — 모든 필드 선택.
      properties:
        eventId: { type: string, description: 평가 대상 canonical event 참조 }
        transactionRef: { type: string, description: 거래 참조 token }
        subjectRef: { type: string, description: 대상 token }
        sourceSystem: { type: string, maxLength: 64, description: 소스 시스템 식별(§4.8) }
        canonicalPayloadJson: { type: string, description: 정규화 보조 payload(JSON, 규제통화 금액 원천 아님) }
    IngestEventRequest:
      type: object
      required: [eventId, eventType, occurredAt, schemaVersion]
      description: Canonical event body(전체 sub-DTO는 §5.1 정본). raw PII 금지.
      properties:
        eventId: { type: string }
        eventType: { type: string }
        occurredAt: { type: string, format: date-time }
        schemaVersion: { type: string }
        messageVersion: { type: string, default: v1 }
        subject: { type: object, additionalProperties: true }
        transaction: { type: object, additionalProperties: true }
        channel: { type: object, additionalProperties: true }
        corridor: { type: object, additionalProperties: true }
        canonicalPayload: { type: string, description: JSON string }
      additionalProperties: true
    IngestEventResponse:
      type: object
      required: [eventId, status, idempotencyReplayed]
      properties:
        eventId: { type: string }
        status: { type: string, enum: [ACCEPTED, REPLAYED, DUPLICATE, REJECTED] }
        idempotencyReplayed: { type: boolean }
        code: { type: string, nullable: true }
        reason: { type: string, nullable: true }
    CustomerProfileSyncRequest:
      type: object
      required: [sourceEventId, occurredAt]
      description: AML CDD projection. raw name/DOB/document identifier is forbidden.
      properties:
        sourceEventId: { type: string }
        occurredAt: { type: string, format: date-time }
        nationality: { type: string, minLength: 2, maxLength: 2, nullable: true }
        country: { type: string, minLength: 2, maxLength: 2, nullable: true }
        registeredAt: { type: string, format: date-time, nullable: true }
        kycCompletedAt: { type: string, format: date-time, nullable: true }
        kycLevel: { type: string, nullable: true }
        dataScope: { type: string, maxLength: 128, nullable: true }
    TransactionType:
      type: string
      description: 거래 유형(fds_transactions.transaction_type, DB §4.19 폐쇄 12종 — 자유 문자열 금지).
      enum: [WITHDRAWAL, DEPOSIT, TRANSFER, REMITTANCE, PAYMENT, REFUND,
        REVERSAL, CHARGE, SETTLEMENT, PAYOUT, EXCHANGE, ADJUSTMENT]
    ActionType:
      type: string
      enum: [DECLINE_AUTHORIZATION, BLOCK_TRANSACTION, HOLD_FUNDS, EXTEND_HOLD,
        RELEASE_HOLD, CANCEL_TRANSACTION, REQUEST_REVERSAL, SUSPEND_ACCOUNT,
        SUSPEND_INSTRUMENT, HOLD_SETTLEMENT, SUSPEND_SELLER_PAYOUT, INCREASE_RESERVE,
        REQUEST_ADDITIONAL_DOCUMENT, ADD_TO_GROUP, OPEN_CASE, SEND_ALERT,
        REQUIRE_SECOND_APPROVAL, BLOCK_WITHDRAWAL, SUSPEND_API_KEY,
        SUSPEND_EMPLOYEE_SESSION, OPEN_AML_CASE, REGULATORY_REPORT]
    CaseType:
      type: string
      description: >
        case 유형(fds_cases.case_type, 도메인 CaseType enum 10종 — 코드 정본).
        hanpass-ph 운영 대상은 FRAUD_REVIEW/AML_REVIEW/MULE_ACCOUNT_REVIEW/INTERNAL_AUDIT/REGULATORY_REPORT.
        TRADE_FINANCE_REVIEW/ECOMMERCE_SETTLEMENT_REVIEW/B2B_INVOICE_REVIEW/CHARGEBACK_REVIEW/MERCHANT_RISK는
        닫힌 enum 멤버로 보존하나 hanpass-ph는 미사용(비-hanpass 도메인).
      enum: [FRAUD_REVIEW, AML_REVIEW, CHARGEBACK_REVIEW, MULE_ACCOUNT_REVIEW,
        INTERNAL_AUDIT, MERCHANT_RISK, REGULATORY_REPORT,
        TRADE_FINANCE_REVIEW, ECOMMERCE_SETTLEMENT_REVIEW, B2B_INVOICE_REVIEW]
    SubjectKind:
      type: string
      enum: [ACTION, RULE, MAPPING, SECRET, GROUP, EXPORT, MERCHANT_NORMALIZE, CASE_CLOSE, POLICY_PACK, RULE_PARAM]
    ActionStatus:
      type: string
      enum: [PENDING, APPROVAL_REQUIRED, APPROVED, SENT, ACKED, FAILED, CANCELLED]
    ActionResponse:
      type: object
      description: 액션 응답(§5.7). actionType은 fds_actions.action_type(DB §5.12) 필수 매핑 — Webhook FdsActionResult와 동일 enum.
      required: [actionId, actionType, status, idempotencyKey]
      properties:
        actionId: { type: string, format: uuid }
        actionType: { $ref: '#/components/schemas/ActionType' }
        status: { $ref: '#/components/schemas/ActionStatus' }
        approvalRequestId: { type: string, format: uuid, nullable: true }
        idempotencyKey: { type: string, maxLength: 256 }
    CasePatchRequest:
      type: object
      minProperties: 1
      description: status/priority/assignedTo 중 1개 이상 필수(§5.6). reason은 종결 상태→IN_REVIEW 재오픈 시 필수(PRD §11.2 BR-006, 감사 기록용).
      properties:
        status: { type: string, description: enum case_status }
        priority: { type: string, description: enum case_priority }
        assignedTo: { type: string, maxLength: 128, description: 운영자 token }
        reason: { type: string, nullable: true, description: 변경 사유 — status=IN_REVIEW 재오픈 시 필수(감사 기록) }
    ApprovalStatus:
      type: string
      description: 결재 요청 상태(fds_approval_requests.status, DB §4.12 8종).
      enum: [DRAFT, SUBMITTED, APPROVED, REJECTED, CANCELLED, EXPIRED, EXECUTED, EXECUTION_FAILED]
    ApprovalLine:
      type: string
      description: 결재 라인(fds_approval_requests.approval_line, DB §4.12 6종).
      enum: [SELF_APPROVAL_DISABLED, MAKER_CHECKER, COMPLIANCE_MANAGER, RISK_MANAGER, SECURITY_ADMIN, EXECUTIVE_APPROVAL]
    CaseEventKind:
      type: string
      description: case timeline 이벤트 종류(fds_case_events.event_kind, DB §5.14 6종).
      enum: [ASSIGNED, COMMENT, STATUS_CHANGE, EVIDENCE_ATTACHED, APPROVAL, CLOSED]
    CaseEventDto:
      type: object
      description: case timeline 단건(append-only). payload 마스킹, actorSubject는 운영자 token(raw PII 없음).
      required: [caseEventId, caseId, eventKind, createdAt]
      properties:
        caseEventId: { type: string, format: uuid }
        caseId: { type: string, format: uuid }
        eventKind: { $ref: '#/components/schemas/CaseEventKind' }
        payload: { type: object, nullable: true, description: 이벤트 상세(마스킹, PII 미포함) }
        actorSubject: { type: string, maxLength: 128, nullable: true, description: 수행 운영자 token }
        createdAt: { type: string, format: date-time }
    ApprovalRequestDto:
      type: object
      description: 결재 요청 단건(fds_approval_requests §5.23). subjectKind/approvalLine/status는 DB §4.12·§5.23 정본 enum.
      required: [approvalRequestId, subjectKind, approvalLine, status]
      properties:
        approvalRequestId: { type: string, format: uuid }
        subjectKind: { $ref: '#/components/schemas/SubjectKind' }
        subjectRef: { type: string, maxLength: 256, nullable: true }
        approvalLine: { $ref: '#/components/schemas/ApprovalLine' }
        status: { $ref: '#/components/schemas/ApprovalStatus' }
        payloadHash: { type: string, maxLength: 128 }
        payloadJson: { type: string, nullable: true, description: 상세/BO 위임용 staged payload(masked/tokenized, raw PII/secret 미포함). RULE 결재함 변경 전/후 표의 파생 원천. }
        makerSubject: { type: string, maxLength: 128 }
        reason: { type: string, nullable: true, description: 상신 사유(fds_approval_requests.reason) }
        expiresAt: { type: string, format: date-time, nullable: true }
        maxExecutions: { type: integer, nullable: true }
    ConnectorStatus:
      type: string
      enum: [HEALTHY, LAGGING, ERROR, DISABLED]
    IngestMode:
      type: string
      enum: [REST_PUSH, QUEUE, POLLING, CDC, SNAPSHOT]
    FailPolicy:
      type: string
      enum: [FAIL_CLOSED, FAIL_OPEN, CASE_ONLY]
    ControlCapability:
      type: string
      enum: [CAN_BLOCK_BEFORE_AUTH, CAN_DECLINE_AUTH, CAN_HOLD_FUNDS, CAN_EXTEND_HOLD,
        CAN_RELEASE_HOLD, CAN_CANCEL_BEFORE_SETTLEMENT, CAN_REQUEST_REVERSAL,
        CAN_SUSPEND_INSTRUMENT, CAN_OPEN_CASE_ONLY]
    ConnectorDto:
      type: object
      required: [connectorId, sourceSystem, connectorStatus]
      properties:
        connectorId: { type: string, maxLength: 128 }
        sourceSystem: { type: string, maxLength: 64 }
        connectorStatus: { $ref: '#/components/schemas/ConnectorStatus' }
        cursorValue: { type: string, description: polling cursor 요약(원문 마스킹) }
        lastSuccessAt: { type: string, format: date-time }
        lastErrorCode: { type: string, maxLength: 120 }
        lagSeconds: { type: integer, format: int64 }
        updatedAt: { type: string, format: date-time }
    ConnectorStateChangeResponse:
      type: object
      required: [connectorId, connectorStatus]
      properties:
        connectorId: { type: string, maxLength: 128 }
        previousStatus: { $ref: '#/components/schemas/ConnectorStatus' }
        connectorStatus: { $ref: '#/components/schemas/ConnectorStatus' }
        updatedAt: { type: string, format: date-time }
    ConnectorStateChangeRequest:
      type: object
      properties:
        reason: { type: string, description: 감사 기록용 }
    SourceSystemUpdateRequest:
      type: object
      minProperties: 1
      properties:
        displayName: { type: string, maxLength: 160 }
        enabled: { type: boolean }
        schemaVersion: { type: string, maxLength: 80 }
        ingestMode: { $ref: '#/components/schemas/IngestMode' }
        failPolicy: { $ref: '#/components/schemas/FailPolicy' }
        capabilities:
          type: array
          items: { $ref: '#/components/schemas/ControlCapability' }
    SourceSystemDto:
      type: object
      required: [sourceSystem, ingestMode, schemaVersion, enabled, failPolicy]
      properties:
        sourceSystem: { type: string, maxLength: 64 }
        displayName: { type: string, maxLength: 160 }
        ingestMode: { $ref: '#/components/schemas/IngestMode' }
        schemaVersion: { type: string, maxLength: 80 }
        enabled: { type: boolean }
        failPolicy: { $ref: '#/components/schemas/FailPolicy' }
        capabilities:
          type: array
          items: { $ref: '#/components/schemas/ControlCapability' }
        approvalRequestId: { type: string, format: uuid, nullable: true }
        status: { type: string, description: APPROVAL_REQUIRED 등 결재 게이트 상태 }
        updatedAt: { type: string, format: date-time }
    ExternalDecisionMode:
      type: string
      description: vendor bridge 운영 모드(fds_external_decisions.bridge_mode, DB §4.18 5종).
      enum: [VENDOR_RESULT_INGEST, DB_MIRROR, DUAL_RUN, SHADOW_DECISION, RULE_MIGRATION]
    RiskGroupType:
      type: string
      description: 위험그룹 용도(Flyway V4/도메인 RiskGroupType 7종).
      enum: [BLACKLIST, WHITELIST, WATCHLIST, MULE_NETWORK, ALLOWLIST, DENYLIST, RISK_COUNTRY]
    RiskGroupUpsertRequest:
      type: object
      additionalProperties: false
      description: 위험그룹 create-only 요청. fds-svc Java RiskGroupUpsertRequest exact 3-field wire.
      required: [groupId, groupType, displayName]
      properties:
        groupId: { type: string, minLength: 1, maxLength: 96 }
        groupType: { $ref: '#/components/schemas/RiskGroupType' }
        displayName: { type: string, minLength: 1, maxLength: 160 }
    DeploymentModel:
      type: string
      description: 배포 유형(구 isolation_mode 대체, fds_tenants.deployment_model). 온보딩 프로비저닝으로 확정. bo-api 소유 /onboarding/** 에서만 변경.
      enum: [MANAGED_DEDICATED, SELF_HOSTED, SHARED]
    OnboardingStatus:
      type: string
      description: 온보딩 진행 상태(fds_tenants.onboarding_status). 매니지드 REQUESTED→PROVISIONING→DEPLOYED→VERIFIED→ACTIVE / self-hosted REQUESTED→PACKAGE_ISSUED→CUSTOMER_DEPLOYED→REGISTERED / SHARED REQUESTED→ACTIVE. ACTIVE/REGISTERED 도달 시 tenant_status=ACTIVE.
      enum: [REQUESTED, PROVISIONING, DEPLOYED, VERIFIED, ACTIVE, PACKAGE_ISSUED, CUSTOMER_DEPLOYED, REGISTERED]
    TenantDto:
      type: object
      description: >
        서비스(테넌트=서비스) 배포/온보딩 메타. bo-api 소유 서비스 레지스트리/온보딩(/api/v1/bo/fds/tenants/** + /onboarding/**)에서 노출.
        테넌트=서비스이며 상위 기관(institution)은 institutionRef(=fds_tenants.institution_ref)로 참조한다(1 기관 : N 서비스).
        fds-svc 엔진 API(§4)에는 미노출(소유 경계, §11.2·§12). isolationMode 필드 폐기.
        DB 컬럼 중 tenant_status(운영 생명주기)·display_name·compliance_policy(JSONB §5.1)는
        bo-api가 집약·노출하는 운영자 집계 전담 필드이므로 fds-svc 엔진 API DTO에 미포함(bo-api 소유 경계).
        PRD/PPT의 tenant_status 표시·compliance_policy 변경(POLICY_PACK 4-eyes)은 bo-api 호출로 명시할 것.
      required: [tenantId, deploymentModel, onboardingStatus]
      properties:
        tenantId: { type: string, maxLength: 64 }
        institutionRef: { type: string, maxLength: 64, nullable: true, description: '상위 기관(institution) 참조 (fds_tenants.institution_ref). 1 기관 : N 서비스(테넌트). additive·nullable' }
        deploymentModel: { $ref: '#/components/schemas/DeploymentModel' }
        onboardingStatus: { $ref: '#/components/schemas/OnboardingStatus' }
        region: { type: string, maxLength: 32, description: fds_tenants.default_region (기본 KR) }
        infraRef: { type: string, maxLength: 160, nullable: true, description: fds_tenants.infra_ref (매니지드 IaC 스택 ref / self-hosted 인스턴스·라이선스 ref) }
    RiskGroupMasterUpdateRequest:
      type: object
      minProperties: 1
      description: displayName 또는 active 중 1개 이상 필수. group_id·group_type 변경 불가.
      required: [reason]
      anyOf:
        - required: [displayName]
        - required: [active]
      properties:
        displayName: { type: string, maxLength: 160 }
        active: { type: boolean, description: false=비활성(멤버 0 선결, BR-001) }
        reason: { type: string, minLength: 1, maxLength: 500, description: maker 결재 사유 }
        groupType:
          allOf: [ { $ref: '#/components/schemas/RiskGroupType' } ]
          description: 에코 전용 read-only. 저장값과 상이 시 거부(immutable, BR-002)
    RiskGroupDto:
      type: object
      required: [groupId, groupType, displayName, memberCount, createdBy, updatedBy, createdAt, updatedAt]
      properties:
        groupId: { type: string, maxLength: 96 }
        groupType: { $ref: '#/components/schemas/RiskGroupType' }
        displayName: { type: string, maxLength: 160 }
        memberCount: { type: integer, format: int64 }
        createdBy: { type: string, maxLength: 128 }
        updatedBy: { type: string, maxLength: 128 }
        createdAt: { type: string, format: date-time }
        updatedAt: { type: string, format: date-time }
        approvalRequestId: { type: string, format: uuid, nullable: true }
        status: { type: string, nullable: true, description: APPROVAL_REQUIRED 등 결재 게이트 상태 }
    RiskGroupMasterUpdateResponse:
      allOf:
        - $ref: '#/components/schemas/RiskGroupDto'
        - type: object
          description: 상신 시점의 변경 전/current master projection과 pending 결재 메타. effective master는 아직 변하지 않는다.
          required: [approvalRequestId, status]
          properties:
            approvalRequestId: { type: string, format: uuid }
            status: { type: string, enum: [APPROVAL_REQUIRED] }
    MerchantNormalizeRequest:
      type: object
      required: [reason]
      description: high-risk merchant 정상화 상신(4-eyes, subjectKind=MERCHANT_NORMALIZE). merchant_ref는 token.
      properties:
        reason: { type: string, description: 결재·감사 사유(fds_approval_requests.reason) }
        scope:
          type: string
          enum: [SINGLE, BULK]
          description: BULK=대규모 정상화, approvalLine EXECUTIVE_APPROVAL(설계서 §11.5)
    Error:
      type: object
      required: [code, status, title]
      properties:
        code: { type: string, example: FDS-VALIDATION-001 }
        status: { type: integer }
        title: { type: string }
        detail: { type: string }
        traceId: { type: string }
    RuleRef:
      type: object
      required: [ruleId, versionNo]
      description: 발화 룰 참조(DecisionResponse.RuleRef 코드 정합). ruleName·outcome 동봉(가독 렌더용).
      properties:
        ruleId: { type: string, format: uuid }
        versionNo: { type: integer }
        ruleNo: { type: string }
        displayName: { type: string }
        ruleName: { type: string, description: 발화 룰 이름 }
        outcome: { type: string, description: 발화 룰 outcome(enum decision) }
        # 룰 종류별 참조 데이터(드릴인) — type: BLOCKLIST_MATCH(대포통장 명단 계좌)/VELOCITY_WINDOW(기여 거래 리스트)/
        # GEO_ANOMALY/WALLET_RISK/MISSING_FIELD. 마스킹 토큰만, raw PII 미포함. nullable.
        reference: { type: object, nullable: true, additionalProperties: true }
    DecisionResponse:
      type: object
      properties:
        decisionId: { type: string, format: uuid }
        eventId: { type: string, description: 연결 canonical event 참조 }
        transactionRef: { type: string }
        subjectRef: { type: string }
        decision: { $ref: '#/components/schemas/Decision' }
        reasonCodes: { type: array, items: { type: string } }
        riskScore: { type: number, format: double, minimum: 0, maximum: 100 }
        recommendedActions:
          type: array
          items: { $ref: '#/components/schemas/ActionType' }
        matchedRules:
          type: array
          items: { $ref: '#/components/schemas/RuleRef' }
        ruleSetVersion: { type: string }
        caseId: { type: string, format: uuid, nullable: true, description: decision이 연 case(fds_cases.origin_decision_id) }
        amount: { type: number, nullable: true, description: 연결 event 거래 금액(레거시=send leg, LEFT JOIN 파생) }
        currency: { type: string, nullable: true }
        sendAmount: { type: number, nullable: true, description: 송금 leg 금액 }
        receiveAmount: { type: number, nullable: true, description: 수취 leg 금액 }
        amountBase: { type: number, nullable: true, description: 규제통화(데모 PHP) 환산 비교 축 — 서버 파생(fds.ingest.regulatory-currency) }
        baseCurrency: { type: string, nullable: true, description: 규제통화 코드(서버 파생) }
        channelType: { $ref: '#/components/schemas/ChannelType' }
        sendCountry: { type: string, nullable: true, description: corridor 송금국(remit 계열) }
        receiveCountry: { type: string, nullable: true, description: corridor 수취국 }
        expiresAt: { type: string, format: date-time }
        createdAt: { type: string, format: date-time }
    IngestDecisionResponse:
      type: object
      required: [ingest]
      properties:
        ingest: { $ref: '#/components/schemas/IngestEventResponse' }
        decision:
          allOf: [ { $ref: '#/components/schemas/DecisionResponse' } ]
          nullable: true
paths:
  /evidence/fds/customer-profiles/{memberRef}:
    get:
      summary: Persisted non-PII AML CDD profile evidence
      security: [ { ApiKeyHmac: [] }, { OAuth2: ['fds:case:read'] } ]
      parameters:
        - $ref: '#/components/parameters/TenantId'
        - $ref: '#/components/parameters/WorkspaceId'
        - name: memberRef
          in: path
          required: true
          schema: { type: string }
      responses:
        '200':
          description: exact masked persisted profile projection
          content:
            application/json:
              schema:
                type: object
                additionalProperties: false
                required: [subjectRef, nationality, country, registeredAt, kycCompletedAt, kycLevel, dataScope]
                properties:
                  subjectRef: { type: string }
                  nationality: { type: string, nullable: true }
                  country: { type: string, nullable: true }
                  registeredAt: { type: string, format: date-time, nullable: true }
                  kycCompletedAt: { type: string, format: date-time, nullable: true }
                  kycLevel: { type: string, nullable: true }
                  dataScope: { type: string, nullable: true }
        '401': { description: unsigned or invalid canonical machine signature }
        '403': { description: valid signature without fds:case:read }
        '404': { description: profile absent in the exact tenant/workspace scope }
  /internal/v1/fds/customer-profiles/{memberRef}:
    servers: [ { url: https://api.fds.example } ]
    put:
      summary: AML CDD PII-safe customer profile upsert
      security: [ { ApiKeyHmac: [] }, { OAuth2: ['fds:internal:customer-profile:write'] } ]
      parameters:
        - $ref: '#/components/parameters/TenantId'
        - $ref: '#/components/parameters/WorkspaceId'
        - $ref: '#/components/parameters/Timestamp'
        - $ref: '#/components/parameters/AuthVersion'
        - $ref: '#/components/parameters/Nonce'
        - $ref: '#/components/parameters/Signature'
        - $ref: '#/components/parameters/DataScope'
        - $ref: '#/components/parameters/InternalService'
        - name: memberRef
          in: path
          required: true
          schema: { type: string }
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/CustomerProfileSyncRequest' }
      responses:
        '204': { description: upsert, stale no-op, or idempotent replay accepted }
        '400': { description: signed caller/dataScope semantic mismatch or payload validation failure }
        '401': { description: unsigned, invalid signature, target/context/body tamper, or nonce replay }
        '403': { description: valid signature with insufficient endpoint scope }
  /fds/events/evaluate:
    post:
      summary: canonical event 동기 인입 + ACTIVE inline 룰 즉시 판단
      security: [ { ApiKeyHmac: [] }, { OAuth2: ['fds:event:write', 'fds:decision:evaluate'] } ]
      parameters:
        - $ref: '#/components/parameters/TenantId'
        - $ref: '#/components/parameters/WorkspaceId'
        - $ref: '#/components/parameters/SourceSystem'
        - $ref: '#/components/parameters/IdempotencyKey'
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/IngestEventRequest' }
      responses:
        '200':
          description: ingest 상태 + 즉시 판단 결과(멱등 replay 포함)
          content:
            application/json:
              schema: { $ref: '#/components/schemas/IngestDecisionResponse' }
        '400': { description: 검증 실패 }
        '409': { description: event/idempotency 충돌 }
        '422': { description: source/schema mapping 미등록 }
  /fds/decisions/evaluate:
    post:
      summary: 승인 전 실시간 FDS 판단
      security: [ { ApiKeyHmac: [] }, { OAuth2: ['fds:decision:evaluate'] } ]
      parameters:
        - $ref: '#/components/parameters/TenantId'
        - $ref: '#/components/parameters/WorkspaceId'
        - $ref: '#/components/parameters/SourceSystem'
        - $ref: '#/components/parameters/IdempotencyKey'
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/EvaluateDecisionRequest' }
      responses:
        '200':
          description: 판단 결과(멱등 재반환 포함)
          content:
            application/json:
              schema: { $ref: '#/components/schemas/DecisionResponse' }
        '400': { description: 검증 실패, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
        '409': { description: 멱등 충돌, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
        '503': { description: fail-closed, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
  /fds/cases/{caseId}:
    patch:
      summary: 케이스 상태/우선순위/담당자 변경
      security: [ { OAuth2: ['fds:case:update'] } ]
      parameters:
        - $ref: '#/components/parameters/TenantId'
        - $ref: '#/components/parameters/WorkspaceId'
        - name: caseId
          in: path
          required: true
          schema: { type: string, format: uuid }
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/CasePatchRequest' }
      responses:
        '200': { description: 변경된 case }
        '403': { description: data-scope 거부, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
        '409': { description: 상태 전이 위반/결재 필요, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
  /fds/cases/{caseId}/events:
    get:
      summary: case timeline 조회(append-only)
      security: [ { OAuth2: ['fds:case:read'] } ]
      parameters:
        - $ref: '#/components/parameters/TenantId'
        - $ref: '#/components/parameters/WorkspaceId'
        - name: caseId
          in: path
          required: true
          schema: { type: string, format: uuid }
        - name: page
          in: query
          required: false
          schema: { type: integer, default: 0 }
        - name: size
          in: query
          required: false
          schema: { type: integer, default: 20, maximum: 200 }
        - name: sort
          in: query
          required: false
          schema: { type: string, default: 'createdAt,asc' }
      responses:
        '200':
          description: case timeline 페이지(content[]=CaseEventDto, §3.2 envelope)
          content:
            application/json:
              schema:
                type: object
                properties:
                  content:
                    type: array
                    items: { $ref: '#/components/schemas/CaseEventDto' }
                  page: { type: integer }
                  size: { type: integer }
                  totalElements: { type: integer, format: int64 }
                  totalPages: { type: integer }
                  sort: { type: string }
        '403': { description: data-scope 거부, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
        '404': { description: 미존재/격리 밖, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
  /admin/fds/rules:
    get:
      summary: rule 목록 조회(필터 6종 — PRD §6.1 BR-001 5축 + 룰 번호 텍스트 검색)
      security: [ { OAuth2: ['fds:admin:rule'] } ]
      parameters:
        - $ref: '#/components/parameters/TenantId'
        - $ref: '#/components/parameters/WorkspaceId'
        - name: ruleSetId
          in: query
          required: false
          schema: { type: string, maxLength: 80 }
        - name: status
          in: query
          required: false
          description: enum rule_status(DB §4.13)
          schema: { type: string, enum: [DRAFT, PENDING_APPROVAL, ACTIVE, DISABLED, ARCHIVED] }
        - name: channelScope
          in: query
          required: false
          description: hanpass-ph 채널(§3.5.1 5종 — CROSS_BORDER_REMIT/DOMESTIC_REMIT/CASH_IN/WALLET_PAYMENT/WALLET_WITHDRAWAL). channel_type enum은 닫힌 집합이나 운영은 5종.
          schema: { $ref: '#/components/schemas/ChannelType' }
        - name: decisionOutcome
          in: query
          required: false
          description: 탐지 시 동작 필터(fds_rules.decision_outcome)
          schema: { $ref: '#/components/schemas/Decision' }
        - name: evaluationMode
          in: query
          required: false
          description: 평가 방식 필터(즉시/사후 — PRD §6.1 표시값)
          schema: { type: string, enum: [INLINE_AND_ASYNC, ASYNC_ONLY] }
        - name: ruleNo
          in: query
          required: false
          description: 룰 번호 텍스트 검색
          schema: { type: string, maxLength: 96 }
        - name: page
          in: query
          required: false
          schema: { type: integer, default: 0 }
        - name: size
          in: query
          required: false
          schema: { type: integer, default: 20, maximum: 200 }
      responses:
        '200': { description: 'rule 페이지(content[]=RuleDto §5.8, §3.2 envelope)' }
        '403': { description: 권한/scope/data-scope 거부, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
  /admin/fds/connectors/{connectorId}:
    get:
      summary: connector 단건 health 조회
      security: [ { OAuth2: ['fds:admin:source-system'] } ]
      parameters:
        - $ref: '#/components/parameters/TenantId'
        - $ref: '#/components/parameters/WorkspaceId'
        - name: connectorId
          in: path
          required: true
          description: connector_id
          schema: { type: string, maxLength: 128 }
      responses:
        '200':
          description: connector health·offset·lag
          content:
            application/json:
              schema: { $ref: '#/components/schemas/ConnectorDto' }
        '403': { description: data-scope 거부, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
        '404': { description: 미존재/격리 밖, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
  /admin/fds/connectors/{connectorId}/pause:
    post:
      summary: connector 일시중지(connector_status→DISABLED)
      security: [ { OAuth2: ['fds:admin:source-system'] } ]
      parameters:
        - $ref: '#/components/parameters/TenantId'
        - $ref: '#/components/parameters/WorkspaceId'
        - name: connectorId
          in: path
          required: true
          description: connector_id
          schema: { type: string, maxLength: 128 }
      requestBody:
        required: false
        content:
          application/json:
            schema: { $ref: '#/components/schemas/ConnectorStateChangeRequest' }
      responses:
        '200':
          description: 일시중지 결과(멱등 재반환 포함)
          content:
            application/json:
              schema: { $ref: '#/components/schemas/ConnectorStateChangeResponse' }
        '403': { description: data-scope 거부, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
        '404': { description: 미존재/격리 밖, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
        '409': { description: 상태 전이 위반, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
  /admin/fds/connectors/{connectorId}/resume:
    post:
      summary: connector 재개(connector_status→HEALTHY, offset 보존 후 소비 재개)
      security: [ { OAuth2: ['fds:admin:source-system'] } ]
      parameters:
        - $ref: '#/components/parameters/TenantId'
        - $ref: '#/components/parameters/WorkspaceId'
        - name: connectorId
          in: path
          required: true
          description: connector_id
          schema: { type: string, maxLength: 128 }
      requestBody:
        required: false
        content:
          application/json:
            schema: { $ref: '#/components/schemas/ConnectorStateChangeRequest' }
      responses:
        '200':
          description: 재개 결과(멱등 재반환 포함)
          content:
            application/json:
              schema: { $ref: '#/components/schemas/ConnectorStateChangeResponse' }
        '403': { description: data-scope 거부, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
        '404': { description: 미존재/격리 밖, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
        '409': { description: '상태 전이 위반(예: ERROR 강제 resume)', content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
  /admin/fds/source-systems/{id}:
    put:
      summary: source system 속성·capability 매트릭스 수정(4-eyes)
      security: [ { OAuth2: ['fds:admin:source-system'] } ]
      parameters:
        - $ref: '#/components/parameters/TenantId'
        - $ref: '#/components/parameters/WorkspaceId'
        - name: id
          in: path
          required: true
          description: source_system
          schema: { type: string, maxLength: 64 }
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/SourceSystemUpdateRequest' }
      responses:
        '200':
          description: 변경 반영(또는 결재 상신 수락) 결과
          content:
            application/json:
              schema: { $ref: '#/components/schemas/SourceSystemDto' }
        '400': { description: 검증 실패(enum 불일치/빈 본문), content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
        '403': { description: 권한/scope/data-scope 거부, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
        '404': { description: 미존재/격리 밖, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
        '409': { description: 결재 필요(FDS-APPROVAL-REQUIRED), content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
        '422': { description: 미등록 schemaVersion(FDS-SCHEMA-UNKNOWN), content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
  /admin/fds/risk-groups:
    post:
      summary: 위험그룹 master 즉시 생성(create-only)
      security: [ { OAuth2: ['fds:admin:group'] } ]
      parameters:
        - $ref: '#/components/parameters/TenantId'
        - $ref: '#/components/parameters/WorkspaceId'
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/RiskGroupUpsertRequest' }
      responses:
        '201':
          description: 새 generation의 위험그룹 master 생성 완료
          content:
            application/json:
              schema: { $ref: '#/components/schemas/RiskGroupDto' }
        '400': { description: 필수 필드/길이/enum 검증 실패(FDS-VALIDATION-001/002), content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
        '403': { description: 권한/scope/data-scope 거부, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
        '409': { description: 동일 scoped groupId create-only 충돌(FDS-STATE-CONFLICT), content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
  /admin/fds/risk-groups/{groupId}:
    put:
      summary: 위험그룹 마스터 수정/비활성(4-eyes)
      security: [ { OAuth2: ['fds:admin:group'] } ]
      parameters:
        - $ref: '#/components/parameters/TenantId'
        - $ref: '#/components/parameters/WorkspaceId'
        - name: groupId
          in: path
          required: true
          description: group_id (immutable)
          schema: { type: string, maxLength: 96 }
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/RiskGroupMasterUpdateRequest' }
      responses:
        '202':
          description: 결재 상신 수락 — 변경 전/current projection + approvalRequestId(UUID) + status=APPROVAL_REQUIRED
          content:
            application/json:
              schema: { $ref: '#/components/schemas/RiskGroupMasterUpdateResponse' }
        '400': { description: 검증 실패(빈 본문/immutable 위반), content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
        '403': { description: 권한/scope/data-scope 거부, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
        '404': { description: 미존재/격리 밖, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
        '409': { description: 멤버 잔존 비활성(FDS-STATE-CONFLICT), content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
  /admin/fds/merchants/{merchantRef}/normalize:
    post:
      summary: high-risk merchant 정상화 상신(4-eyes)
      security: [ { OAuth2: ['fds:admin:group'] } ]
      parameters:
        - $ref: '#/components/parameters/TenantId'
        - $ref: '#/components/parameters/WorkspaceId'
        - name: merchantRef
          in: path
          required: true
          description: merchant_ref (token)
          schema: { type: string, maxLength: 256 }
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/MerchantNormalizeRequest' }
      responses:
        '202': { description: 정상화 상신 수락(결재 게이트, approvalRequestId 반환) }
        '400': { description: 검증 실패, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
        '403': { description: 권한/scope/data-scope 거부, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
        '404': { description: 미존재/격리 밖, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
        '409': { description: 결재 필요(FDS-APPROVAL-REQUIRED), content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
  /admin/fds/approvals:
    get:
      summary: 결재 대기 목록 조회(필터 subjectKind/status/maker)
      security: [ { OAuth2: ['fds:case:read'] } ]
      parameters:
        - $ref: '#/components/parameters/TenantId'
        - $ref: '#/components/parameters/WorkspaceId'
        - name: subjectKind
          in: query
          required: false
          schema: { $ref: '#/components/schemas/SubjectKind' }
        - name: status
          in: query
          required: false
          schema: { $ref: '#/components/schemas/ApprovalStatus' }
        - name: maker
          in: query
          required: false
          description: 상신자 token(maker_subject)
          schema: { type: string, maxLength: 128 }
        - name: page
          in: query
          required: false
          schema: { type: integer, default: 0 }
        - name: size
          in: query
          required: false
          schema: { type: integer, default: 20, maximum: 200 }
      responses:
        '200':
          description: 결재 대기 페이지(content[]=ApprovalRequestDto, §3.2 envelope)
          content:
            application/json:
              schema:
                type: object
                properties:
                  content:
                    type: array
                    items: { $ref: '#/components/schemas/ApprovalRequestDto' }
                  page: { type: integer }
                  size: { type: integer }
                  totalElements: { type: integer, format: int64 }
                  totalPages: { type: integer }
                  sort: { type: string }
        '403': { description: 권한/scope/data-scope 거부, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
  /admin/fds/approvals/{approvalRequestId}/approve:
    post:
      summary: 결재 승인(checker≠maker 강제, 4-eyes)
      security: [ { OAuth2: ['fds:action:write'] } ]
      parameters:
        - $ref: '#/components/parameters/TenantId'
        - $ref: '#/components/parameters/WorkspaceId'
        - name: approvalRequestId
          in: path
          required: true
          schema: { type: string, format: uuid }
      requestBody:
        required: false
        content:
          application/json:
            schema:
              type: object
              properties:
                comment: { type: string, description: 승인 코멘트(감사 기록) }
      responses:
        '200': { description: 승인 완료(ApprovalRequestDto 반환) }
        '403': { description: 권한/scope/data-scope 거부, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
        '404': { description: 미존재/격리 밖, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
        '409': { description: maker=checker 자기 승인(FDS-APPROVAL-SELF) 또는 상태 전이 위반, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
  /admin/fds/approvals/{approvalRequestId}/reject:
    post:
      summary: 결재 반려
      security: [ { OAuth2: ['fds:action:write'] } ]
      parameters:
        - $ref: '#/components/parameters/TenantId'
        - $ref: '#/components/parameters/WorkspaceId'
        - name: approvalRequestId
          in: path
          required: true
          schema: { type: string, format: uuid }
      requestBody:
        required: false
        content:
          application/json:
            schema:
              type: object
              properties:
                comment: { type: string, description: 반려 코멘트(감사 기록) }
      responses:
        '200': { description: 반려 완료(ApprovalRequestDto 반환) }
        '403': { description: 권한/scope/data-scope 거부, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
        '404': { description: 미존재/격리 밖, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
        '409': { description: 상태 전이 위반, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
```

---

## 11. BO 화면(PRD) ↔ API 매핑

bo-web(Next.js)은 **bo-api 경유로만** 아래 API를 호출한다(엔진 직접호출 금지). PRD(`docs/plan/01-fds-sass-functional-spec.md`)가 정합 대상.

### 11.1 fds-svc 저수준 API를 (bo-api 경유) 그대로 위임 호출하는 화면
| BO 화면(PRD) | 호출 API(fds-svc, bo-api 경유) |
|---|---|
| 실시간 판단 모니터 / decision 추이 | `GET /fds/decisions`, `GET /fds/decisions/{id}` |
| Case 큐 / SLA / 담당자 | `GET /fds/cases`, `PATCH /fds/cases/{id}`, `/assign`, `/close` |
| Case timeline 증적 | `GET /fds/cases/{id}/events`, `GET /evidence/fds/cases/{id}/timeline` |
| no-code rule builder / 활성화 승인 | `GET /admin/fds/feature-catalog`, `POST /admin/fds/rules`, `/activate`, `/rollback` |
| rule simulation / 예상 hit rate | `POST /admin/fds/rules/simulations` |
| watchlist/group 관리 | `GET/POST /admin/fds/risk-groups`, `PUT /admin/fds/risk-groups/{groupId}`(마스터 수정/비활성, 4-eyes), `/members` |
| high-risk merchant 정상화(4-eyes 상신) | `POST /admin/fds/merchants/{merchantRef}/normalize` |
| connector health / 단건 / 일시중지·재개 / replay | `GET /admin/fds/connectors`, `GET /admin/fds/connectors/{connectorId}`, `/{connectorId}/pause`, `/{connectorId}/resume`, `/replay` |
| 결재함(maker-checker) | `GET /admin/fds/approvals`, `/approve`, `/reject` |
| evidence export self-service | `POST /evidence/fds/exports`, `/download` |
| source/credential 관리 | `GET/POST /admin/fds/source-systems`, `PUT /admin/fds/source-systems/{id}`(속성·capability, 4-eyes), `/{ss}/mappings`, `/credentials`, `/rotate` |
| 서비스 알림 채널(TNT-002 ⑤ 알림·소스 탭) | `GET/PUT /admin/fds/notify-channels`(설계서 §13.2 alert channel, §4.8) |

> BO typed capability는 route 의미를 따른다. `GET /api/v1/bo/fds/health`는 `SFDS_CONNECTOR:READ`, case evidence timeline BFF는 조사 read인 `SFDS_DECISION:READ`, notify-channel GET은 `SFDS_TENANT:READ`, notify-channel PUT은 platform tenant admin(`SFDS_TENANT:ADMIN` + platform admin identity)이다. engine machine scope와 이 BO 사람 capability를 혼동하지 않는다.

### 11.2 운영자 집계 화면 — **bo-api 소유 API 호출(fds-svc 엔진 API 아님)**
아래 화면이 호출하는 집계 엔드포인트는 **bo-api가 소유·집약·인증**한다. 본 fds-svc 엔진 명세(§4)에는 추가하지 않는다(§1.1·§12). bo-api는 §11.1의 fds-svc 저수준 데이터 API(+ aml-svc·자체 서비스/감사 저장소)를 fan-out·집약하여 다음 경로를 노출한다.

| BO 화면(PRD) | 호출 API(**bo-api 소유**) | 집약 데이터 출처(fds-svc 저수준) |
|---|---|---|
| 플랫폼 대시보드 | `GET /api/v1/bo/fds/dashboard` | `GET /fds/decisions`, `GET /fds/cases`, `GET /admin/fds/connectors` 집계 |
| 서비스별 대시보드 | `GET /api/v1/bo/fds/tenants/{tenantId}/dashboard` | 동일 + `Tenant-Id` 위임 필터 |
| 서비스 목록/상세/등록(배포유형) | `GET/POST /api/v1/bo/fds/tenants`, `GET/PUT /api/v1/bo/fds/tenants/{tenantId}` | bo-api 서비스 레지스트리(`tenant_status`/`deployment_model`/`onboarding_status`/`region`/`infraRef`) |
| 온보딩 프로비저닝 트리거(매니지드 IaC) | `POST /api/v1/bo/fds/tenants/{tenantId}/onboarding/provision` | bo-api 온보딩 워크플로우(`onboarding_status` 전이 → `fds_tenants` 갱신 트리거) |
| 온보딩 상태 조회(읽기) | `GET /api/v1/bo/fds/tenants/{tenantId}/onboarding` | bo-api 온보딩 상태(`deployment_model`/`onboarding_status`/`infra_ref`) |
| self-hosted 인스턴스 등록 콜백 | `POST /api/v1/bo/fds/tenants/{tenantId}/onboarding/register` | bo-api 등록 수신(self-hosted 인스턴스 → `onboarding_status=REGISTERED`) |
| 액션 아웃박스 목록/상세 | `GET /api/v1/bo/fds/actions`, `GET /api/v1/bo/fds/actions/{actionId}` | BO exact `SFDS_ACTION:OPERATE`; `platformOperator`/`SFDS_PLATFORM_OPS` 우회 없음 |
| 감사 로그 조회 | `GET /api/v1/bo/fds/audit?subjectKind&subjectId&actor&traceId&from&to&page&size`, `GET /api/v1/bo/fds/audit/{sourceService}/{auditId}` | bo-api local 감사 + fds-svc scoped list/detail을 exact-total unified merge; composite direct detail |

> 위 `bo-api 소유` 경로(`/api/v1/bo/**`)는 bo-api API 명세에서 확정한다. PRD/PPT의 대시보드·서비스 관리·감사·온보딩 화면은 호출 대상을 **bo-api**로 명시하고, 과거 `GET /api/v1/admin/fds/dashboard|tenants|audit` 표기(엔진 직접 경로)는 폐기한다.
>
> **서비스 등록 = 배포 유형 선택 + 온보딩 신청/상태(격리 토글 아님, 정본 target-architecture §4.1)**: 서비스(테넌트=서비스) 등록은 '격리 방식(DB 분리/스키마 분리/공유) 라디오' 즉석 선택이 아니라 **배포 유형(`deployment_model`: `MANAGED_DEDICATED`/`SELF_HOSTED`/`SHARED`) 선택 + 온보딩 신청(`onboarding_status` 상태머신)** 흐름이다. 온보딩 프로비저닝 트리거·상태 조회·self-hosted 등록 콜백은 **bo-api 전용 `/onboarding/**`** 경로로만 노출하며, **본 fds-svc 엔진 API(§4)에는 온보딩 엔드포인트를 추가하지 않는다**(DB §9 소유 경계). fds-svc는 `fds_tenants`의 `deployment_model`/`onboarding_status`/`default_region`/`infra_ref`를 스키마로 보유하되 운영 변경은 bo-api 온보딩 워크플로우가 트리거한다. tenant_id 라우팅 의미: 전용 배포(`MANAGED_DEDICATED`/`SELF_HOSTED`)는 **배포=서비스 단일**(라우팅은 배포 엔드포인트 단위, 서비스 간 격리는 배포 경계가 보장), `SHARED`만 `Tenant-Id` 헤더 행 라우팅(integration 명세 확정).

---

## 12. 서비스 경계 주의 (운영자 집계 = bo-api 소유)

- **bo-web → bo-api → fds-svc**. bo-web의 fds-svc·aml-svc 직접호출 금지(정본 §3, §4).
- **운영자 집계 API 소유 경계(정본 결정)**: **대시보드(플랫폼·서비스별)·서비스 관리(목록/상세/등록/설정)·통합 감사 조회는 bo-api가 소유·집약·인증**한다. fds-svc/aml-svc는 **저수준 데이터 API**를 제공하고, FDS 감사 원천은 §4.9a다. 엔진은 화면용 aggregate `/dashboard|tenants|audit`를 소유하지 않는다. PRD/PPT는 bo-api(`/api/v1/bo/**`)를 호출 대상으로 명시한다(§11.2).
- **AML/STR/CTR 본 처리**: fds-svc는 후보 action(`OPEN_AML_CASE`/`REGULATORY_REPORT`)·origin case만 생성하고, 본 케이스·sanction/PEP·규제보고는 **aml-svc**가 별도 API로 처리. fds 응답은 `amlCaseRef` cross-ref만 노출(integration 명세에서 `fds_cases.aml_case_id` 확정).
- **운영자 IAM·승인 라인 정책**: bo-api 소유. fds-svc는 엔진 측 결재 게이트(`fds_approval_requests`/`fds_approval_steps`)와 엔진 감사(`fds_audit_logs`)만 보유.
- **data-scope**: bo-api가 운영자 토큰 scope를 fds-svc 조회 IN 필터로 주입. fds-svc는 scope 밖 row 접근을 `FDS-DATASCOPE-DENIED`로 차단.
- **bo-api local FDS fallback**: fds-svc delegate가 없으면 production은 항상 503이다. non-production도 active context가 정확히 `tenant_demo/default`일 때만 fallback state를 읽고 쓸 수 있으며 scope 부재·다른 tenant/workspace는 503이다. fallback 결재는 현재 context의 tenant/workspace와 인증 principal maker로 생성하고 generic hard-coded scope/명의를 사용하지 않는다. engine-owned `compliance_policy`는 별도 `FdsTenantCompliancePolicyService`가 이 경계를 적용한다. local toggle payload는 exact object `{"base":"KR_BASE","packs":[<non-blank string>...],"optional":[<non-blank string>...]}`만 허용한다(세 key 모두 필수, 추가 key·다른 base·비배열/blank 원소는 400 `FDS-POLICY-PAYLOAD-INVALID`). submit은 즉시 BO row를 바꾸지 않고 scoped `POLICY_PACK` approval을 staged하며, 다른 checker의 exact `SFDS_REG:APPROVE`·immutable hash/scope/payload 검증 후 `FdsTenantWriter` 적용이 성공해야 `EXECUTED`/effective가 된다. reject/apply 실패는 effective 값을 보존한다. delegate가 구성된 경우 engine 오류·빈/잘못된 응답은 local policy로 대체하지 않고 그대로 fail-closed한다.

---

## 13. downstream 확정 명칭

integration·tasks·PRD가 그대로 참조할 API 명칭을 확정한다.

- **base path**: `/api/v1`. 외부 `/fds/**`·`/evidence/fds/**`, Admin `/admin/fds/**`.
- **격리 헤더**: `Tenant-Id`(필수), `Workspace-Id`(default `default`/`sandbox` shadow), `Source-System`, `Idempotency-Key`. `dataScope`는 위임 토큰 claim.
- **핵심 엔드포인트**: `POST /fds/events`, `POST /fds/decisions/evaluate`, `GET/PATCH /fds/cases/{caseId}`, `POST /fds/cases/{caseId}/actions`, `POST /evidence/fds/exports`, `POST /admin/fds/rules/simulations`, `POST /admin/fds/rules/{ruleId}/activate`, `POST /admin/fds/approvals/{approvalRequestId}/approve`.
- **OAuth2/machine scope**: 외부/운영 11종 `fds:event:write`/`fds:decision:evaluate`/`fds:case:read`/`fds:case:update`/`fds:evidence:export`/`fds:rule:simulate`/`fds:action:write`/`fds:admin:rule`/`fds:admin:group`/`fds:admin:source-system`/`fds:admin:credential` + internal profile 전용 `fds:internal:customer-profile:write` = **총 12종**(§2.3 정본과 동일).
- **에러 코드 prefix**: `FDS-*`(§6). 표준 envelope(RFC7807 + `code`/`traceId`).
- **응답 enum**: decision 8종·**action_type 22종(API `ActionType` enum이 마스터 정본 §1.1)**·case_type 10종은 DB enum 코드값과 동일(§4 DB). `HOLD_TRANSACTION`은 비정본(→`HOLD_FUNDS`/`BLOCK_TRANSACTION`).
- **HTTP 상태코드**: 본 §6이 정본. 요청 필드 검증=400, create-only 상태키 충돌(위험그룹 scoped duplicate 포함)=409, 결재 누락=409, maker=checker=409, raw PII=422, rate limit=429.
- **DecisionResponse 필수 필드**: `matchedRules`(RuleRef[]: `ruleId`,`versionNo`) 포함(§5.4·§10 OpenAPI, DB `fds_decisions.matched_rules`).
- **Webhook 콜백(outbound)**: `FdsDecisionCreated`·`FdsCaseOpened`·`FdsCaseStatusChanged`·`FdsActionResult` 4종, `X-Signature: hmac-sha256`, `eventId` 멱등, 지수 backoff 재시도(§9).
- **운영자 집계 = bo-api 소유**: 대시보드/서비스/감사 집계 엔드포인트는 bo-api(`/api/v1/bo/**`)가 소유. 엔진 API에 미추가(§1.1·§11.2·§12).
- **배포 모델/온보딩(deployment topology) = bo-api 소유, fds-svc 엔진 API 미추가**: 서비스(테넌트=서비스) 등록은 격리 토글이 아니라 **배포 유형 선택 + 온보딩 신청/상태**다. enum `DeploymentModel{MANAGED_DEDICATED, SELF_HOSTED, SHARED}`(3종) · `OnboardingStatus{REQUESTED, PROVISIONING, DEPLOYED, VERIFIED, ACTIVE, PACKAGE_ISSUED, CUSTOMER_DEPLOYED, REGISTERED}`(8종, §10 OpenAPI)는 DB `fds_tenants.deployment_model`/`onboarding_status` 정본과 1:1. `TenantDto`는 `tenantId`/`deploymentModel`/`onboardingStatus`/`region`(=`default_region`)/`infraRef`(=`infra_ref`) — **`isolationMode` 필드 폐기**. 온보딩 엔드포인트(bo-api 전용): `POST /api/v1/bo/fds/tenants/{tenantId}/onboarding/provision`(프로비저닝 트리거), `GET /api/v1/bo/fds/tenants/{tenantId}/onboarding`(상태 조회), `POST /api/v1/bo/fds/tenants/{tenantId}/onboarding/register`(self-hosted 등록 콜백). 상태머신: 매니지드 `REQUESTED→PROVISIONING→DEPLOYED→VERIFIED→ACTIVE` / self-hosted `REQUESTED→PACKAGE_ISSUED→CUSTOMER_DEPLOYED→REGISTERED` / SHARED `REQUESTED→ACTIVE`(ACTIVE/REGISTERED 도달 시 `tenant_status=ACTIVE`). tenant_id 라우팅: 전용 배포(MANAGED_DEDICATED/SELF_HOSTED)는 배포=서비스 단일(배포 엔드포인트 단위), SHARED만 `Tenant-Id` 헤더 행 라우팅(§11.2·integration).
- **4-eyes 게이트**: action(자금/규제)·rule activate/rollback·**rule 변수 편집**·mapping·group master 수정/비활성·group member·credential·export 최종본·merchant normalize·**case 종결**·**규제 팩 토글**·**테넌트 규제통화 전환** → `fds_approval_requests.subject_kind` **11종**(`ACTION`/`RULE`/`MAPPING`/`SECRET`/`GROUP`/`EXPORT`/`MERCHANT_NORMALIZE`/`CASE_CLOSE`/`POLICY_PACK`/`RULE_PARAM`/`TENANT_REGULATORY_CURRENCY`) 매핑(§8). **case 종결=`CASE_CLOSE`(대상=`case_id`)**, **규제 팩 토글=`POLICY_PACK`(subjectRef=`tenant_id`)**, **룰 변수 편집=`RULE_PARAM`(subjectRef=`rule_id`)**, **테넌트 규제통화 전환=`TENANT_REGULATORY_CURRENCY`(subjectRef=`tenant_id`, 다통화 PLAN 20260818 U17)**, ACTION 아님. integration·tasks·PRD는 이 11종을 따른다.
- **AML 위임 필드**: `amlCaseRef`(= `fds_cases.aml_case_id`, integration 확정 대기).

---

## 14. 변경 이력

| 일자 | 버전 | 변경 내용 | 비고 |
|---|---|---|---|
| 2026-09-06 | v4.25 | **운영자 블랙리스트 5종·식별자 해시 canonical 역전파(코드=truth, aegis-aml PLAN 20260906-fds-operator-blacklists U2·U5·U8, 사용자 지시로 F-025·F-032·FDS-C37 잠금 해제).** §5 `OriginatorDto.phoneHash`·`CounterpartyDto.phone/phoneHash` 추가(raw phone 은 수용 즉시 `SHA-256(숫자만)` 파생 후 폐기, 해시 필드 원문 422 `FDS-PII-REJECTED` — `accountNoHash` A4 가드를 3경로로 일반화·`+` 포함), 신규 feature `subject.phoneHash`·`counterparty.phoneHash`·`counterparty.accountNoHash`(STRING, V35 카탈로그). §4.7 멤버 등록 — bo-api 가 `displayKind` PHONE/ACCOUNT 원문을 서버측 해시로 치환(엔진 body·멱등키·감사 원문 부재). 룰팩 18→23종(BL-01~05: 회원·단말·계좌·회원 전화·수취인 전화 BLOCK)·리스크그룹 5→7종(`fds_member_blacklist`·`fds_phone_blacklist`) | 코드 truth=`services/fds-svc/.../adapter/in/rest/dto/IngestEventRequest`·`IngestController`·`application/usecase/IngestEventService`·`adapter/out/feature/FeatureComputeAdapter`·`domain/event/ForbiddenPiiScanner`·`services/bo-api/.../fds/service/FdsRuleGroupService`·`services/common-security/.../IdentifierHash`. 엔진 케이스 FDS-C41~C43 |
| 2026-09-05 | v4.24 | **RULE 활성화 상신 반려 상태전이 역전파(코드=truth, aegis-aml PLAN 20260905-fds-rule-reject-transition-sim-residue U1·U6).** §4.9 `POST /approvals/{id}/reject` 행에 대상별 원상복구 의미를 명시 — `RULE` 반려 시 룰 `PENDING_APPROVAL → DRAFT`(`RuleAdminService.applyRejected`, 감사 `RULE_UPDATE action=REJECT`), 종전 누락으로 고착된 룰은 V34 복구(DB §8). 요청·응답 스키마 무변경. 같은 §4.9 표의 `GET /approvals` 행에서 선재 드리프트(미구현 페이지네이션 선언)를 코드 기준으로 정정 | 코드 truth=`services/fds-svc/.../application/usecase/{ApprovalService,RuleAdminService}.java`. 엔진 케이스 FDS-C38~C40 |
| 2026-08-19 | v4.23 | **다통화(법인별 자국통화) 테넌트 규제통화 전환 4-eyes + 기존 compliance 라우트 미선언 정리 역전파(코드=truth, PLAN 20260818-currency-profile-bo-setup U13, r11/r20 이격).** ① **§4.8a 신설** — 기존 미선언 `GET .../compliance`·`POST .../compliance/policy-pack:toggle` 2종 + 신규 `POST .../compliance/regulatory-currency:change`(U17, `subjectKind=TENANT_REGULATORY_CURRENCY`) 를 함께 일괄 선언. `TenantMetaResponse`에 `regulatoryCurrency`(읽기 전용, U15) 필드 추가. `policy-pack:toggle` EXECUTED 서술에 '테넌트 행 무손실 재조립' 명기. ② **§3.4** — `422 FDS.TENANT_CURRENCY_HISTORY_LOCKED` 신설. ③ **subjectKind 9종/10종 → 11종 전수 정정**(헤더 입력 핀·§1.1·§4.9·§5.12 `ApprovalRequestDto`·§8·§13 downstream) — `RULE_PARAM`(기존 누락 발견)·`TENANT_REGULATORY_CURRENCY`(신규) 병기, checker capability `TENANT_REGULATORY_CURRENCY→SFDS_REG:APPROVE`. | 코드=truth. 근거=fds-svc `adapter/in/rest/{TenantAdminController,dto/TenantMetaResponse}`·`db/migration/V32__tenant_regulatory_currency_subject_kind.sql`. DB `01-fds-db.md` §5.23 동일 작업 단위. |
| 2026-08-17 | v4.22 | **통화중립 규제금액 feature.** typed `amount_base`를 `transaction.amountBase`와 전 통화 `transaction.baseEquivalent`로 노출하고, `transaction.phpEquivalent`는 PHP-only legacy alias로 제한했다. canonical payload 환산값은 금액 feature 원천이 아니다. | 코드 truth=`FeatureComputeAdapter`·`DomainFeatureKeys`·DB V31 catalog |
| 2026-08-17 | v4.21 | **FDS 고객 프로필 마스킹 evidence read-back 추가.** `GET /api/v1/evidence/fds/customer-profiles/{memberRef}`를 `fds:case:read`·canonical machine-auth·tenant/workspace exact scope로 추가하고, 응답을 persisted 비-PII 7필드 `{subjectRef,nationality,country,registeredAt,kycCompletedAt,kycLevel,dataScope}`로 닫았다. 부재는 404이며 신고소득·성명·DOB·신분키·raw payload는 DTO에 존재하지 않는다. 기존 internal PUT/write 우선순위·FDS-C01~C34·룰/임계는 무변경이다. | 코드 truth=`CustomerProfileEvidenceController`·`CustomerProfileQueryService`·`EvidenceMachineAuthFilterChainTest`; 기존 FDS-C13 profile/key-chain의 read-back 증거 강화 |
| 2026-07-20 | v4.20 | **위험그룹 멤버 add/remove/extend 4-eyes 폐지·즉시 반영 역전파(코드=truth, fix/fds-risk-group-member-immediate-apply — 사용자 확정 방향).** §4.7 표 member POST/DELETE 행의 4-eyes `필수` 마커 제거·"즉시 반영(200, `GroupMemberMutationResponse`)" 로 갱신, 신규 note로 `GroupMemberMutationResponse{groupId,status="APPLIED",approvalRequestId=null,member}` 응답 계약·`GROUP_UPDATE` 감사·`fds:admin:group`/`SFDS_GROUP:OPERATE` 인가 불변·레거시 in-flight 결재 실행 잔존을 명문화(master rename/비활성·merchant normalize 4-eyes는 무변경). §5.10 canonical ADD/REMOVE payload 주석을 "즉시 적용 `GROUP_UPDATE` afterHash 산출 + 레거시 in-flight 결재 실행 전용"으로 재서술. §8 4-eyes 표 `POST`·`DELETE .../members` 행을 취소선 폐지 표기로 갱신하고 규칙 문단의 ADD/REMOVE generation 결속 서술을 레거시 실행 한정으로 조정. | 코드 truth=fds-svc `application/usecase/RiskGroupAdminService`(addMember/removeMember)·`adapter/in/rest/RiskGroupAdminController`·`adapter/in/rest/dto/GroupMemberMutationResponse`·bo-api `FdsRuleGroupService`/`FdsRuleGroupController`. `docs/qa/engine-rule-cases.md` FDS-C33 참조 |
| 2026-07-19 | v4.19 | **velocity 윈도우 1y(365일) 확장 역전파(코드=truth, PLAN 20260719-fds-rule-window-1y-value-hints U1·U9 — 사용자 지시로 F-006 잠금 경로 append-only 해제, F-006 윈도우 닫힌 집합 계약 additive 확장).** §5.8 velocity window 화이트리스트 note 에 1y 확장 문단 신설 — `ALLOWED_WINDOWS` 9종→**10종** `{1m,5m,10m,30m,1h,6h,24h,7d,30d,1y}`(`1y`=365일 고정·윤년 미보정, 반개구간 동일, `365d`/`1w`/`2y` 등은 여전히 파싱 거부), velocity count/sum/distinct_count·sameChannel scope 전 경로 동형 지원, evidence 윈도우 해석(`RuleEvidenceWindowResolver`) `y` 단위 인식(1y 룰 SINGLE_TX 강등 방지). 룰 빌더(`/fds/rules/new`) 윈도우 드롭다운 10종·기준값 예시 placeholder(프론트 i18n) 언급. 신규 카탈로그 대표 키 6종은 DB V29(01-fds-db.md). 엔드포인트·기존 9윈도우 계약 재작성 없음(additive). | 코드 truth=fds-svc `domain/rule/RuleDslParser`(ALLOWED_WINDOWS)·`domain/rule/RuleEvidenceWindowResolver`(parseWindow 'y')·`adapter/out/persistence/CanonicalEventJpaRepository`(velocityWindows)·`adapter/out/feature/FeatureComputeAdapter`(WINDOWS)·DB V29. bo-web `lib/fds-rule-conditions.ts`(VELOCITY_WINDOWS)·`components/common/MetricConditionBuilder.tsx`(윈도우 셀렉터). aegis-aml `docs/aml-data.md` §11.7.8(20260719 개정). |
| 2026-07-18 | v4.18 | **단일 호출 응답 판정 동봉(코드=truth, PLAN 20260718-sync-verdict-in-response U2/U9 — 사용자 지시로 F-005 해제, v4.17 전제 반전).** ① §4.1 `POST /fds/events` 행 재개정 — 직전(v4.17) "`ACCEPTED`=전송 수리(업무 판정 아님), 판정 정본=`/decisions/evaluate`" 서술을 **철회**하고 "저장 직후 ACTIVE inline 룰을 동기 평가해 응답에 `decision`(additive) 동봉, 202=수리+판정 동봉" 으로 재개정. `:batch` 행도 per-item `decision` 동봉으로 동형 개정. `/decisions/evaluate`·`/events/evaluate` 행에 **event-scope 재사용 게이트**(동일 이벤트 inline 결정 존재 시 재사용, 신규 decision 행 생성 금지) 1줄 추가 — 두 엔드포인트 자체 계약(요청/응답 스키마·상태코드)은 불변. ② §5.2 `IngestEventResponse` 표를 실제 6필드(`eventId`/`status`/`idempotencyReplayed`/`code`/`reason`/`decision`)로 정합하고 신규 `DecisionSummary`(`decisionId`/`decision`/`riskScore`/`matchedRules[]`) 스키마 신설 — 멱등 replay 는 저장된 동일 결정 재표현, reject/duplicate/평가 실패(fail-safe)는 `decision=null`. 거절 없음 원칙 명문화. 엔드포인트 경로·기존 5필드·422/409/originator 계약 재작성 없음(additive 필드 1개 추가만). | 코드 truth=fds-svc `adapter/in/rest/dto/IngestEventResponse`(`DecisionSummary`/`MatchedRule`)·`adapter/in/rest/dto/BatchIngestResponse`·`application/usecase/EvaluateDecisionService`(event-scope 재사용 게이트)·`application/usecase/IngestAndEvaluateService`·`adapter/in/rest/IngestController`. aegis-aml `docs/aml-data.md` §11.7.3(20260718 재개정). |
| 2026-07-18 | v4.17 | **인입 판정 가시성·통화 표기 드리프트 정정(계약 무변경, PLAN 20260718-fds-verdict-response-currency U7 — aegis-aml 4cef7fdc).** ① §4.1 `POST /fds/events` 행에 `ACCEPTED`=전송 수리(업무 판정 아님) 1줄 추가 — 판정 정본 경로는 `/decisions/evaluate`(또는 `/events/evaluate`) 응답(aegis-aml `docs/aml-data.md` §11.7.3). ② §5.4 `DecisionResponse.amountBase/baseCurrency` 서술의 문서 드리프트 "USD 환산" → "서버 파생 규제통화(기준통화; tenant_demo=PHP, §11.7.6)"로 정정(코드=truth, v4.13 규제통화 서버 파생 전환분에 개별 표 행 정정 누락). 엔드포인트·필드·계약 변경 0(comment/서술 정정만). | 근거=aegis-aml `services/fds-svc/.../DecisionResponse.java` javadoc·`docs/aml-data.md` §11.7.3/§11.7.6. |
| 2026-07-18 | v4.16 | **FDS 룰 체계 전면 개편 역전파(코드=truth, PLAN 20260717-fds-legacy-rule-overhaul U-F1~U-F5·U-X1 — 사용자 지시로 F-005 해제·룰 전량 대체).** ① §4.6 `GET /admin/fds/rules` 에 `status` 미지정 시 `ARCHIVED` 기본 제외 명시. ② §4.6 `POST /admin/fds/rules/{ruleId}/archive` 신설(terminal, `DRAFT｜DISABLED→ARCHIVED` 그 외 409, scope `fds:admin:rule`, disable 전례 동형 4-eyes 없음 — 가정 A8 사용자 승인 완료, 감사 이벤트 `RULE_ARCHIVE`). §11.6.5 는 상태기계만 정의하고 전이 API 자체는 기존 설계 미정의였음을 명시(A8). ③ §5.1 `DeviceDto` 에 6번째 필드 `locale`(≤16자 BCP-47, AML `NeutralDevice.locale` 동형) 추가 — device 블록 존재판정 5필드로 확장(locale 단독 인입도 materialize). ④ velocity `distinct_count` field 화이트리스트에 `deviceRef`/`ip`/`merchantRef` 추가(6종), `window` 화이트리스트 9종 `{1m,5m,10m,30m,1h,6h,24h,7d,30d}` 명문화, 신규 선택 필드 `scope`(`sameChannel` 만 허용)로 채널 한정 velocity 표현. ⑤ 파생 피처 신설 note — `customer.ageYears`(DOB→만 나이 파생, 원문 미영속)·`time.hourOfDay`/`time.isNight`(관할 타임존 가정 A1, **구현 실측: fds-svc 는 jurisdiction 조회 포트 부재로 항상 UTC** — Manila 등 관할별 변환 미구현, 후속 스코프)·`device.firstSeenForSubject`. 신규 카탈로그·컬럼·시드 룰 21건 아카이브는 DB V28(01-fds-db.md). | 코드 truth=fds-svc `adapter/in/rest/RuleAdminController`(archive)·`adapter/in/rest/dto/IngestEventRequest.DeviceDto`(locale)·`domain/rule/RuleDslParser`(ALLOWED_WINDOWS/ALLOWED_SCOPES/DISTINCT_FIELDS)·`domain/rule/RuleCondition.Velocity`(scope)·`adapter/out/feature/FeatureComputeAdapter`(9윈도우 통합쿼리·파생 피처)·`domain/enums/RuleStatus`·DB V28. bo-api 위임=`FdsRuleGroupController/Service`(archive, `SFDS_RULE:OPERATE`). AML 동형=02-aml-api.md. |
| 2026-07-17 | v4.15 | **FDS originator 주체 계약(subject 대체)·device 4필드 확장(코드=truth, PLAN 20260717 U2~U4 — 사용자 지시로 F-005 해제).** §5.1 표에 `originator`(OriginatorDto, **정본**)·`subject`(deprecated legacy 별칭) 행 분리 + `device` 행에 422 소재 명시. **originator 주체 계약 note 신설** — `partyReference`(회원 키 단일 정본)·`partyType`(A3 닫힌 매핑)·`nationalIdentityKey`(fallback 토큰 파생)·`fullNameLatin`/`dateOfBirth`/`gender`/`phone`/`identification[]`(수용 즉시 스캔 후 폐기)·`nationality`/`residenceCountry`·`kyc{…,kycVerifiedAt}`·`registeredAt`(FDS 확장), `subject` 동시 존재+`subjectRef`≠`partyReference` 불일치 시 422 `FDS-CONTRACT-VIOLATION`. **device 공통 블록 note 신설** — `DeviceDto`에 `deviceId`/`os`/`version`/`ip` 4필드 추가, `deviceId`는 기존 `deviceRef` coalesce(불일치 422)로 `velocity.*.device.<w>` 6차원에 결선(신규 카탈로그 불요), `os`/`version`/`ip`는 준식별자 원값 저장·≤64자·제어문자 금지(422)·feature `device.os`/`device.version`/`device.ip`(DB V27). OriginatorDto/SubjectDto/DeviceDto 필드 설명 개정(§5.1 서술부). §6 error 표 `FDS-PII-REJECTED`에 originator 스캔 경로 추가, `FDS-CONTRACT-VIOLATION`에 originator/device 위반 4종 추가. | 코드 truth=fds-svc `adapter/in/rest/dto/IngestEventRequest`(OriginatorDto·DeviceDto)·`adapter/in/rest/IngestController`(validateOriginatorContract·mapPartyType·checkDeviceStringField)·`adapter/out/crypto/HmacPiiTokenAdapter`·`domain/event/ForbiddenPiiScanner`·`domain/rule/DomainFeatureKeys`(DEVICE_OS/VERSION/IP)·`adapter/out/feature/FeatureComputeAdapter`·DB V27. DB §8 V27·02-aml-api.md §2.1a/§3.17 device 블록 동반 |
| 2026-07-17 | v4.14 | **FDS 인입 계약 개편 — send/receive 통화 4필드·서버측 규제통화 파생·counterparty 식별·집중 룰 차원(코드=truth, PLAN 20260717 R2/R3).** §5.1 `TransactionDto` 를 `sendAmount`/`sendCurrency`·`receiveAmount`/`receiveCurrency` 4필드로 개편(레거시 `amount`/`currency`=send leg 하위호환·양방향 채움, 구 `amountBase`/`baseCurrency` 클라 입력 제거)하고, `transaction.amountBase`(base 통화=규제통화 `fds.ingest.regulatory-currency`, 데모 PHP)를 서버 파생으로 전환(구 `canonicalPayload.transaction.phpEquivalent` 독해 제거·`transaction.phpEquivalent`/`amountBase` 단일 원천). §5.1 `CounterpartyDto` 에 `institutionCode`(≤32)·`accountNoHash`(≤64 hex, 원문 계좌 미수용 A4) 추가. §5.1 통화 계약·422 규칙 note 신설(leg-전무·leg 불일치·accountNoHash 형식 위반 → `FDS-CONTRACT-VIOLATION` 422, raw 계좌 → `FDS-PII-REJECTED` 422). §6 error 표에 `FDS-CONTRACT-VIOLATION`(422) 행 신설. velocity `distinct_count` field 화이트리스트에 `counterpartyRef` 추가·count/sum dimension 6종(counterparty·merchant 포함) 명문. §5.1 표 transaction/counterparty 매핑·EventViewResponse(§5.14)·DecisionResponse(OpenAPI) 에 send/receive leg·서버 파생 amountBase 반영. 신규 feature 카탈로그 키(`transaction.sendAmount`/`receiveAmount`/`sendCurrency`/`receiveCurrency`·`velocity.count\|sum.counterparty\|merchant.<w>`·`velocity.distinct_count.counterpartyRef.subject.<w>`·`counterparty.institutionCode`)는 DB V25/V26(01-fds-db.md §5.10·feature catalog). 신선 스택 검증 전제(기존 행 미백필 A9). | 코드 truth=fds-svc `adapter/in/rest/dto/IngestEventRequest`(TransactionDto·CounterpartyDto)·`application/usecase/IngestEventService`(validateTransactionContract·checkAccountNoHash)·`domain/event/RegulatoryAmountPolicy`·`global/config/FdsIngestProperties`·`domain/rule/RuleDslParser`(DISTINCT_FIELDS)·`adapter/in/rest/dto/EventViewResponse`·`DecisionResponse`·`IngestEventResponse`(FDS-CONTRACT-VIOLATION)·DB V25/V26. DB §5.10·feature catalog 참조 |
| 2026-07-16 | v4.13 | **Phase7 피처 인입 커버리지 확장 역전파(코드=truth, feature/fds-feature-ingest-coverage, fds V24, additive).** §5.1 `IngestEventRequest` 표에 `order`/`settlement`/`document`/`externalSignals` 블록 4행 신설 + `OrderDto`/`SettlementDto`(payoutCountry 포함)/`DocumentDto`(documentNoHash 해시만)/`ExternalSignalsDto`(trade·seller·settlement·vendor·crypto·market·employee 서브블록 → feature 19종 매핑) 설명 신설. 피처 카탈로그 input-slot 26종 발동 불가 갭 해소 note — 7종 결정적 계산 전환(newBeneficiary·vendorOnboardingAgeDays·invoiceAmountDeviation·salesSpike·gmvSpike·payoutCountry·preSettlementAccountChange, externalSignals 주입 불가)·19종 pass-through·커머스 투영(order/settlement/document) 최상위 putIfAbsent 계약화(free-form 하위호환). | 코드 truth=fds-svc `adapter/in/rest/dto/IngestEventRequest`(OrderDto·SettlementDto·DocumentDto·ExternalSignalsDto)·`adapter/in/rest/IngestController#canonicalPayload`·`adapter/out/feature/FeatureComputeAdapter`(copyExternalSignalFeatures·computeAdvancedDomainFeatures)·V24. DB §5.27 payout_country·§feature catalog 참조 |
| 2026-07-15 | v4.12 | **P0-12 불변 evidence 다운로드 무결성 계약(코드=truth).** §4.5 Evidence API `/exports/{exportId}/download` 행에 stored `artifact_bytes` serve(재렌더 금지)·`object_checksum` byte-level 재계산·비교·`manifest_hash` 검증·불일치 차단을 부기하고, download 무결성 note 신설 — manifest_hash(논리 콘텐츠 SHA-256, §16.4)와 object_checksum(byte-level 앵커)의 별개성, 원천 row 변경에도 다운로드 bytes/hash 불변, at-rest 변조 시 `ExportTamperException`, pre-V21 row 1회 결정적 render 폴백, 실 decision/case row 포함 phase-2 BLOCKED. §3.4 표준 에러 모델에 evidence export at-rest 변조가 **신규 에러코드 없이 기존 `409 FDS-APPROVAL-PAYLOAD-CHANGED` 재사용**으로 fail-closed 함을 명시(aml 전용 `AML.EXPORT_TAMPER` 와 asymmetry). 엔진 엔드포인트·scope·응답 계약 무변경 — 무결성 검증·error 재사용만 명문화. | 코드 truth=fds-svc `application/usecase/EvidenceExportService`(download·object_checksum 재계산·`ExportTamperException`)·`domain/AuditHashChain`·DB V21 `artifact_bytes`/`object_checksum`. DB §5.31 참조 |
| 2026-07-14 | v4.11 | **P0-10 CASE_CLOSE 반려·중복 승인 상태머신(코드=truth).** §6 error 표에 `FDS-APPROVAL-DUPLICATE`(409, subsystem `Approval`) 행 신설 — 같은 subject 활성(SUBMITTED) 승인 중복(특히 CASE_CLOSE 케이스당 최대 1개)을 애플리케이션 가드 또는 부분 유니크 인덱스 `uk_fds_approval_pending_case_close`(DB §5.23) 위반 시 반환. §4.4 Case API에 **CASE_CLOSE 결재/반려 상태전이 note** 신설 — 활성 종결 승인 최대 1개(중복 close=409), 반려 시 `fds_cases.previous_status`(DB §5.13)로 직전 상태(`IN_REVIEW`/`ESCALATED`) 복구되어 `PENDING_APPROVAL` 고착 없이 재조사·재상신 가능(직전 `ESCALATED`면 `ESCALATED` 복원), maker close 상신=`APPROVAL`·checker 반려=`STATUS_CHANGE`(rejected/rejectReason/approvalRequestId/checker) 타임라인 기록. §8 case close 행에 활성 1개·반려 복구 병기. 엔진 계약(§4.4 엔드포인트·§5.5) 무변경 — 상태전이·중복 방지·error 계약만 명문화. | 코드 truth=fds-svc `application/usecase/CaseWorkflowService`(previousStatus 보존·반려 복구·중복 close 거부)·`domain/DuplicateApprovalException`·`global/GlobalExceptionHandler`(FDS-APPROVAL-DUPLICATE 409)·DB V20 `previous_status`+`uk_fds_approval_pending_case_close`. 설계서 §11.5·§11.6.1 참조 |
| 2026-07-14 | v4.10 | **P0-09 canonicalPayload raw PII 방어 스캔·reject 계약 명문화(코드=truth).** §5.1 `canonicalPayload` 검증에 인입 시 raw PII(PAN=Luhn 유효 13–19자리·계좌=10자리 이상 숫자런·이메일·KR 주민등록번호) 방어 스캔을 추가하고, `instrumentRef`/`accountRef`/`*Ref`/`amount`/`amountBase`/`phpEquivalent`/`balanceBefore`/`After` 등 토큰·금액 키 예외를 명시했다. §5.1 서술 note 신설 — persist(`fds_canonical_events`)·outbox·log 도달 이전 스캔(JSON 은 field-path 순회·비-JSON 은 전체 문자열), 검출 시 §6 **`FDS-PII-REJECTED`(422)** 로 reject, reason=PII class+field path 만(원문 미포함). §6 error 표 `FDS-PII-REJECTED` 행을 PAN·계좌·이메일·주민번호 + `canonicalPayload` 방어 스캔 경로로 보강. 코드가 기존 §6 정본 코드를 사용하도록 정합. | 코드 truth=fds-svc `domain/event/ForbiddenPiiScanner`·`application/usecase/IngestEventService.scanForbiddenPii`·`adapter/in/rest/dto/IngestEventResponse`(PII_FORBIDDEN→FDS-PII-REJECTED)·`adapter/in/rest/IngestController`(rejectStatus 422); DDL 불변 |
| 2026-07-13 | v4.9 | **P0-17 outbound webhook egress SSRF 정책.** §9에 양 엔진 공통 `WebhookUrlPolicy` 3단계 검증(파싱: absolute·host 필수·user-info/fragment 금지·production https+443/8443/기본 port만 / allowlist: `aegis.fds.webhook.allowed-host-suffixes` suffix 일치·빈 값=비활성 / DNS: 전 A·AAAA 레코드 검사, production 내부대역·metadata·CGNAT·IPv4-mapped·NAT64 전부 거부, 비-production은 link-local만 tier 무관 거부), reason code 9종, redirect 미추종(3xx=`REDIRECT_REFUSED` delivery 실패, 기존 FAILED+backoff 계약 유지), DNS rebinding 한계·egress proxy 백스톱을 신설했다. §4.8/§5.22 notify-channels WEBHOOK target 등록 검증(위반 400), §5.13 credential CREATE `webhookUrl` 상신 400+승인 apply 재검증(위반=적용 실패)을 명시했다. | 코드 truth=`common-security` `WebhookUrlPolicy`/`NoRedirectRequestFactory`, `NotifyChannelAdminService`, `CredentialAdminService`, `HttpWebhookSenderAdapter`; runbook `docs/ops/webhook-egress-policy.md`; DDL 불변 |
| 2026-07-13 | v4.8 | **P0-04 내부 profile·BO→FDS machine-auth 완료.** `/internal/v1/fds/**`를 wire v2-only filter coverage에 넣고 customer profile에 exact AML caller/dataScope 및 전용 scope를 강제했다. BO typed client는 exact target credential/final URI/same bytes signer만 사용하며 unsigned fallback이 없다. OpenAPI security scope와 internal PUT path를 총 12종 정본에 동기화했다. | 코드 truth=`IngestAuthenticationFilter`·`CustomerProfileInternalController`·`FdsEngineClient`; DDL 불변 |
| 2026-07-13 | v4.7 | **P0-03 위험그룹 generation·create 계약 정합.** §5.10/§5.18/§5.20에 master/member/merchant-normalize generation binding과 delete/recreate ABA 차단을 반영했다. bo-api V19는 모든 기존 local GROUP payload를 원 JSONB/hash 보존 exact 4필드 tombstone으로 이관하고 비종결 4상태만 취소하며 terminal exact marker만 역사 read-only로 허용한다. §5.17a 및 OpenAPI에 Java `RiskGroupUpsertRequest` exact 3-field POST와 201/400/403/409를 추가하고, 일반 field validation 400과 scoped create-only conflict `FDS-STATE-CONFLICT` 409를 분리했다. | 코드 truth=FDS V17·`RiskGroupAdminService`·`ApprovalService`, BO V19·`FdsApprovalStubService`·`FdsRuleGroupService` |
| 2026-07-13 | v4.6 | **P0-03 위험그룹 결재 무결성·트랜잭션·BO projection 강화.** `MASTER_UPDATE` hash는 JSONB key 순서와 무관한 고정 semantic field order를 submit/current/apply에 공통 적용한다. business 재검증만 `EXECUTION_FAILED`; master/audit persistence 예외는 승인 트랜잭션 전체 rollback 후 `SUBMITTED` 재시도로 고정했다. configured BO 위임은 exact group ID·enum·필수 actor/time/member 필드와 PUT pending UUID/status를 fail-closed 검증하고 path/body ID 불일치를 위임 전에 거부한다. OpenAPI PUT도 전용 `RiskGroupMasterUpdateRequest`와 202 current projection+pending UUID/status로 교정했다(POST create 불변). | 코드 truth=`RiskGroupAdminService.canonicalMasterUpdatePayload`·`ApprovalService`·`FdsRuleGroupService.fromEngine/updateRiskGroup` |
| 2026-07-13 | v4.5 | **P0-03 위험그룹 master 4-eyes·unified 감사 보완.** POST create만 즉시 저장+`GROUP_CREATE`하고, PUT은 `GROUP`/`RISK_MANAGER`로 staged하여 202 current projection+UUID/status를 반환한다. 다른 checker가 rename 또는 멤버 0인 `active=false` 정의 삭제를 실제 적용한 뒤에만 `GROUP_UPDATE`(checker, staged causal trace 우선, canonical before/after hash)를 기록한다. 반려·자기승인·실행 실패는 mutation/성공 감사가 없다. §4.9a typed FDS projection에는 성공 이벤트만 포함된다. | 코드 truth=`RiskGroupAdminController`·`RiskGroupAdminService`·`ApprovalService`·`RiskGroupAdminServiceTest` |
| 2026-07-13 | v4.4 | **P0-03 FDS 운영자 경계·exact 결재·scoped 감사 정합.** `platformOperator`를 data-scope로만 한정하고 BO exact `SFDS_*` capability와 engine `fds:*` scope를 분리했으며 `SFDS_PLATFORM_OPS`를 횡단 read-only(approval/action/evidence 없음)로 고정했다. action list/detail, delegated `IN_REVIEW` 보수 checker, capability `[]` revoke-all·전체교체, 인증 maker·delegated hash 선비교, compliance-policy staged fallback을 명시했다. §4.9a에 V16 audit trace 128, targetKind/approval subjectKind 분리, 10,000행 merge window·BO numeric tie ASC·민감 detail/역사 webhookHosts hash를 확정했다. | 코드 truth=P0-03 `FdsAuthorizationPolicy`, compliance/fallback service, `SourceSystemAdminService`/`CapabilityAdminPort`, audit query/redactor, bo-api V18 |
| 2026-07-12 | v4.3 | **P0-00 공통 inbound machine-auth wire v2 동기화.** §2를 `00-common-machine-auth.md` 정본으로 전환해 normalized servlet routing/ambiguous raw-path·duplicate singleton 거부, raw path/query·고정 9-key scopeContext(trace/correlation 제외)·body digest, v1 offset/v2 UTC `Z`, nonce TTL `>2×skew`·cleanup `20×5000/tick`, signed redirect 거부와 local/demo positive provisioning을 반영했다. `FDS-AUTH-002/003/004` generic 오류와 P0-01/P0-04/P0-14·P1-02 미완료 경계를 명시했다. FDS credential의 구 hash 컬럼 오기를 실제 AES-GCM `secret_ciphertext`로 전수 정정했으며 §9 outbound webhook `timestamp + "." + rawBody` 공식은 inbound v2와 별개로 유지했다. | 코드 truth=`common-security`, FDS V14, bo-api `RestClientConfig`/`RestClientConfigTest`, `test-vectors/machine-auth-v2.json`, Python simulator transport |
| 2026-07-10 | v4.2 | **BO 단일 REST API 모니터링·cache scope 정합.** fds-svc §5.15a source별 metrics는 저수준 입력으로 유지하고 `/fds/connectors`는 `POST /api/v1/fds/events` 한 행에 전체 24h 수신·최신 수신·TPS 합계·metrics 응답 상태를 표시한다. bo-api TTL cache와 bo-web query cache에 tenant/workspace identity를 강제한다. | api-designer |
| 2026-07-10 | v4.1 | **FDS REST 거래 인입 실측 모니터링 API 추가.** §4.8 `GET /api/v1/admin/fds/ingest/metrics`와 §5.15a DTO를 신설. `fds_canonical_events.received_at`·`transaction_ref IS NOT NULL` accepted row 기준 24h 건수/마지막 수신/60초 TPS를 tenant/workspace/source별로 반환하며 replay/duplicate는 비가산. bo-api health는 `MEASURED`, 경로별 HTTP 호출량은 게이트웨이 APM으로 분리. | api-designer |
| 2026-07-10 | v4.0 | **AML CDD 고객 프로필 동기화 API 추가.** §4.3a `PUT /internal/v1/fds/customer-profiles/{memberRef}`와 PII-safe DTO·tenant/workspace/caller·날짜 검증을 명시. §5.1 거래 `SubjectDto` 프로필은 bootstrap fallback으로 강등하고 CDD master 우선순위를 확정. | api-designer |
| 2026-07-09 | v3.9 | **FDS 룰베이스 확장 역전파(코드=truth, feature/fds-rule-nationality-metric-conditions, fds V10).** (1) §5.1 `SubjectDto` 에 비-PII 프로파일 스냅샷 3필드 추가 — `nationality`(string(2) ISO-3166 alpha-2)·`registeredAt`(datetime)·`kycCompletedAt`(datetime), `fds_subjects` COALESCE upsert(DB §5.6·V10) 후 feature `customer.nationality`/`customer.signupAgeDays`/`customer.kycAgeDays`(= floor((occurredAt−타임스탬프)/일), 부재 시 미노출·`customer.accountAgeDays` 보존) 파생 note 신설. 기존 표기 `kycLevel`/`riskRating` 은 코드 `IngestEventRequest.SubjectDto` 에 없어 정정 삭제(마스터 컬럼일 뿐 인입 DTO 필드 아님). (2) §5.8 `ruleJson` wire 타입을 object → **string(JSON)** 으로 정정(`RuleUpsertRequest.ruleJson` `@NotBlank String`·`RuleDto.ruleJson` String, 저장 JSONB) + `channelScope` **NULL = 전채널** 명기. (3) §5.8 velocity `distinct_count`·`field` 규약 note 신설 — `field` 닫힌 화이트리스트 `{receiveCountry, channelType}`(`RuleDslParser.DISTINCT_FIELDS`), `distinct_count` 필수·`count`/`sum` 금지, 사전계산 키 `velocity.distinct_count.<field>.subject.<window>`(window 10m/1h/6h/24h). (4) §5.8 bo-api 위임 wire 봉투 note 신설 — 쓰기: `toEnginePayload()` 가 `ruleJson` 을 JSON 문자열로 재성형(object 전송 = 400 FDS-VALIDATION-001, MockRestServiceServer 미적발 wire 갭)·`channelScope` null 원문 전달(기본값 주입 금지)·bo-api 전용 필드 탈락 / 읽기: `fromEngine` 이 `channelScope` NULL 을 기본 채널로 치환하지 않고 그대로 노출(라벨 "전채널", round-trip scope 오염 방지). | api-designer. 코드=truth. 근거=fds-svc `adapter/in/rest/dto/{IngestEventRequest,RuleUpsertRequest,RuleDto}`·`domain/rule/{RuleDslParser,RuleCondition,VelocityAggregate}`·bo-api `fds/service/FdsRuleGroupService`(toEnginePayload·EngineRuleUpsertPayload·fromEngine·channelLabel)·aegis-aml 491f46e(+워킹트리 channelScope NULL 노출 수정). |
| 2026-07-09 | v3.8 | **Travel Rule 기능 전면 제거 역전파(코드=truth, feature/remove-travel-rule).** fds-svc `ActionType` **23종→22종**(`REQUEST_TRAVEL_RULE_INFO` 제거) — §1.1 원칙·§4.4 CaseActionRequest·§5.7 `ActionResponse`·§7 recommendedActions·§9.1 `FdsActionResult`·§10 OpenAPI `ActionType` enum·§13 downstream 전수 갱신. fds-svc `CaseType` **11종→10종**(`CRYPTO_TRAVEL_RULE` 제거) — §5.5 `CaseDto`·§10 OpenAPI `CaseType` enum/설명·§13 downstream 갱신. §1 위임 서술·§6 `FDS-AML-DELEGATED`·§12 위임 서술에서 "AML/Travel Rule"→"AML", `REQUEST_TRAVEL_RULE_INFO` 후보 action 제거(`OPEN_AML_CASE`/`REGULATORY_REPORT` 위임은 유지). bo-api/bo-web `travelRuleReference` 삭제(RuleRef.reference travel MISSING_FIELD 본문 소멸 — `MISSING_FIELD`는 데이터품질 reasonCode로 잔존, RuleRef reference variant 주석 불변). FATF R.16 party 정보 요건(originator/counterparty 필드 근거)은 규제 근거로 유지. §5.4·§5.5 엔진 계약 나머지 무변경. | api-designer. 코드=truth. 근거=aegis-aml 84997e1(feature/remove-travel-rule)·삭제된 fds `ActionType`(REQUEST_TRAVEL_RULE_INFO)·`CaseType`(CRYPTO_TRAVEL_RULE)·Flyway V9 DROP. |
| 2026-07-08 | v3.7 | **bo-api 케이스 종결 위임 wire 계약 역전파(코드=truth, feature/aml-fds-case-triage-disposition, 라이브 검증 7fca1a0).** §4.4 케이스 API 표 아래에 **bo-api 케이스 종결 위임 계약 note** 신설 — bo-web 1클릭 "종결"의 BFF 계약 `CaseCloseRequest{closeReason, memo}` 를 엔진 `POST /fds/cases/{caseId}/close`(terminal `closedStatus` 필수·종결 전 `PENDING_APPROVAL` 경유 필수, §11.6 전이표)로 위임할 때 bo-api 가 ① `closeReason` 계열에서 `closedStatus` 파생(`FP_*`→`CLOSED_FALSE_POSITIVE`·`CONFIRMED_*`→`CLOSED_CONFIRMED`·`ESCALATED_AML`→`CLOSED_REPORTED`·`OTHER`→확정 계열 보수 기본값, DB §4.11) ② 상신 전 상태(`OPEN`/`ASSIGNED`→`IN_REVIEW`→`PENDING_APPROVAL`·`IN_REVIEW`/`ESCALATED`→`PENDING_APPROVAL`) 자동 선행(1클릭 유지·그 외 불법 전이 409 표면화) ③ `closeReason` 8종 검증 위임·스텁 공통화. 종결은 `CASE_CLOSE` 4-eyes(`COMPLIANCE_MANAGER`)라 응답 `pendingApproval`→`SUBMITTED`/else `CLOSED`, 비운영 스텁은 `CLOSED_<closeReason>` 자체 표기 유지. 엔진 계약(§4.4·§5.5·§8) 무변경 — bo-api 위임 어댑팅 계약만 명문화. | aegis-java-implementer(spec). 코드=truth. 근거=bo-api `fds/service/FdsDecisionCaseStubService.closeCase`(closedStatusFor·PENDING_APPROVAL 자동 선행·CLOSE_REASONS 검증). 설계서 §11.6·DB §4.11 참조. |
| 2026-07-07 | v3.6 | **FDS 룰 변수(파라미터) 편집 4-eyes 폐루프 역전파(코드=truth, RULE_PARAM).** (1) §4.6 표에 `GET /admin/fds/rules/{ruleId}/params`(scope `fds:admin:rule`, 4-eyes —)·`POST /admin/fds/rules/{ruleId}:update-params`(scope `fds:admin:rule`, **4-eyes 필수**, 202+`approvalRequestId`) 2행 추가. (2) §5.9b DTO 절 신설 — `RuleParamsResponse`(`ruleId`/`params[]`/`pendingApprovalId`)·`RuleParamItem`(`key`/`label`/`unit`/`defaultValue`/`currentValue`/`min`/`max`/`integerOnly`/`editable`/`overridden`)·`UpdateRuleParamsRequest`(`params map<string,string>`/`reason`)·`UpdateRuleParamsResponse`(`approvalRequestId`)를 `RuleParamDtos` 코드와 1:1 기재. `unit`은 자유 텍스트. (3) §8 4-eyes 표에 `POST :update-params → RULE_PARAM(subjectRef=rule_id) → COMPLIANCE_MANAGER` 행 추가(코드 `RuleParamService`가 `ApprovalLine.COMPLIANCE_MANAGER`로 상신). (4) `subject_kind` 참조 전수 **9종→10종**(`RULE_PARAM` 추가) — 헤더·§1.1 원칙·§4.9 approvals 필터·§5.12 `ApprovalRequestDto`·OpenAPI `SubjectKind` enum·§13 downstream. | aegis-java-implementer. 코드=truth. 근거=fds-svc `adapter/in/rest/RuleAdminController`(listParams·updateParams)·`adapter/in/rest/dto/RuleParamDtos`·`application/usecase/RuleParamService`(RULE_PARAM 상신·`RULE_PARAM_UPDATE` 감사)·`domain/enums/SubjectKind`·`db/migration/V7__rule_param_overrides.sql`. |
| 2026-07-06 | v3.5 | **FDS 룰 결재 상세 AS-IS/TO-BE 표시 역전파(코드=truth, fix/approval-as-is-to-be).** `ApprovalRequestDto.payloadJson`을 API/OpenAPI에 노출하고, RULE 활성화 payload에 `ruleName`·`statusBeforeSubmit`·`statusAfterSubmit`·`statusAfterApproval`·`simulationId`·`reason`, rollback payload에 `ruleName`·`fromVersion`·`toVersion`·`statusBeforeApproval`·`statusAfterApproval`·`reason`을 보존해 bo-api 결재함 `payloadDiff[{field,before,after}]`가 변경 전/후 표를 구성한다. raw PII/secret 미포함 불변. | aegis-java-implementer. 근거=fds-svc `ApprovalRequestDto`·`RuleAdminService`, bo-api `FdsApprovalStubService` 엔진/로컬 diff 파생, bo-web `FdsApprovals` 변경 전/후 컬럼. |
| 2026-07-06 | v3.4 | **FDS 룰 활성화/rollback 4-eyes 요청 본문 역전파(코드=truth, fix/fds-rule-approval-flow).** §4.6 activate/rollback 이 `RuleActionRequest(reason, simulationId)` 를 수신하는 계약을 명시. inline rule 활성화는 `simulationId` 필수, rollback은 `reason` 필수로 fail-fast. fds-svc 결재 payload에는 simulationId/reason을 보존하고, bo-api 엔진 위임 응답의 결재 큐 상태는 `SUBMITTED`로 정규화한다. | aegis-spec. 근거=fds-svc `RuleAdminController`·`RuleAdminService`·`RuleActionRequest`, bo-api `FdsRuleGroupService`. |
| 2026-07-05 | v3.3 | **누적 계약 드리프트 역전파(코드=truth, fix/aml-ra-envelope-fds-spec-backprop) — 판정 목록 `rule` 필터·Case SLA 필드·Case 목록 `slaBreached` 필터.** (1) **§4.2 `GET /api/v1/fds/decisions`** 목록 필터의 `ruleNo`(적중 룰 번호) → **`rule`**(적중 룰 id/이름 부분일치·대소문자 무시 — fds-svc 는 숫자 룰 번호가 없어 목록 행의 룰 코드/이름 문자열로 검색) 정정(`DecisionQueryController.listDecisions` `@RequestParam String rule` 1:1). (2) **§5.5 `CaseDto`** 에 `slaDueAt`(datetime, nullable — `CaseSlaPolicy` 파생 처리 SLA 기한)·`slaBreached`(boolean — SLA 초과 여부) 필드 추가(구 문서엔 미표기, 코드 `CaseDto.slaDueAt/slaBreached`·도메인 `Case.getSlaDueAt/isSlaBreached`·`CaseSlaPolicy.dueAt/breached` 정본). (3) **§4.x `GET /api/v1/fds/cases`** 목록 필터에 `slaBreached`(boolean) 추가(`CaseController.listCases` `@RequestParam Boolean slaBreached`). ⚠️ §4.6 `/admin/fds/rules` 의 `ruleNo`(텍스트검색) 및 OpenAPI `RuleRef.ruleNo`(§5.4 응답 필드)는 **코드=truth 그대로 유지**(`RuleAdminController` `@RequestParam ruleNo`·`FdsDecisionCaseDtos.RuleRef.ruleNo` — 별개 계약, 변경 없음). | aegis-spec. 코드=truth. 근거=fds-svc `adapter/in/rest/DecisionQueryController`(rule)·`adapter/in/rest/CaseController`(slaBreached)·`adapter/in/rest/dto/CaseDto`(slaDueAt/slaBreached)·`domain/Case`·`domain/CaseSlaPolicy`. |
| 2026-07-04 | v3.2 | **(H1) 판정 발동 룰 근거 거래 조회 엔드포인트 역전파(코드=truth, fix/aml-fds-spec-backprop).** (1) **§4.2 Decision API 표에 행 추가** — `GET /api/v1/fds/decisions/{decisionId}/evidence-transactions?ruleId=&page=&size=`(scope `fds:case:read`) 판정 근거 거래 전수 페이징(요구2, 발동 룰 evidence 윈도우 해소·`feature_snapshot` 캡 미절단, `ruleId` 미지정 시 대표 룰 A12, size 기본 50·200 클램프 A8, 미지 decision 404). (2) **§5.4a `DecisionEvidenceTransactionsResponse` DTO 신설** — 코드 `DecisionEvidenceTransactionsResponse`(ruleId/ruleName/outcome/dimension/dimensionRef/window/windowStart/asOf/channelFilter/transactions=`PageResponse<EventViewResponse>`) 1:1 전사, rows=EventView 투영(토큰만·raw PII 미포함·canonical_payload 미노출). | aegis-spec. 코드=truth. 근거=fds-svc `adapter/in/rest/DecisionQueryController`(GET evidence-transactions)·`adapter/in/rest/dto/DecisionEvidenceTransactionsResponse`·`EventViewResponse`·port `QueryDecisionEvidenceUseCase`·`DecisionEvidenceQueryPort`. sass §01-fdsSvc 동기화. |
| 2026-07-04 | v3.0 | **중립(canonical) 수집 블록 인입 확장 반영(코드=truth, feature/aml-neutral-canonical-ingest, additive).** §5.1 `IngestEventRequest` 표에 `card`/`balance`/`funding` 블록 행 추가 + `CardDto`(scheme·issuerCountry·domesticInternationalFlag)·`BalanceDto`(balanceBefore·balanceAfter)·`FundingDto`(fundingInstrumentType·isAutoTopup·isManualApproval) 서브-DTO 설명 신설 + `RiskSignalsDto`에 `accountHolderNameMatch`(차명계좌 §6.2)·`fundingSourceType` 가산. AML 중립 수집 API(02-aml §2.1a)의 5 product 신호를 FDS 판정 경로가 동일 feature 결선으로 소비하도록 확장(비-PII만, PAN/계좌/충전수단 masked 미수용·`instrument.instrumentRef` 토큰 참조 §16.1). 기존 룰팩 C1213 이 cmp/velocity 노드로 소비 "가능"까지가 목표(신규 룰팩 신설 없음). feature 카탈로그 등록=DB §feature catalog V6(01-fds-db.md). | aegis-java-implementer. 코드=truth. 근거=fds-svc `adapter/in/rest/dto/IngestEventRequest`(CardDto·BalanceDto·FundingDto·RiskSignalsDto.accountHolderNameMatch/fundingSourceType)·`domain/rule/DomainFeatureKeys`(§6.2~§6.5 blocks). |
| 2026-07-04 | v3.1 | **bo-api 판정 목록 페이징 봉투 역전파(코드=truth, fix/list-server-pagination).** bo-api `GET /api/v1/fds/decisions`(BO 위임 표면)에 `page`(기본 0)·`size`(기본 20·상한 200) 파라미터 추가, 응답을 배열 → **`DecisionPage{rows, page, size, totalElements, totalPages}`** 봉투로 전환(fds-svc `PageResponse` 메타 passthrough — 기존엔 위임 시 totalElements 유실로 목록 화면이 첫 페이지만 표시되던 결함). stub(비위임) 경로도 동일 슬라이스+실측 total. bo-web 탐지결정 목록 페이저(총건수·페이지 표기) 결선. | aegis-java-implementer. 코드=truth. 근거=bo-api `FdsDecisionCaseStubController.listDecisions`(page/size)·`FdsDecisionCaseDtos.DecisionPage`·`FdsDecisionCaseStubService`. |
| 2026-07-02 | v2.11 | **데모 인입 테스트 이벤트 transaction payload 규격·라이브 판정 실 payload 정합(데이터 정직화, 코드=truth, feature/fds-demo-data-honesty, 기능정의서 v6.10 · AML §7.1 BR-DEMO-HONESTY).** §5.1 뒤에 **데모 인입 테스트 이벤트 note 신설** — 데모 시뮬레이터가 FDS·AML 양쪽에 동일 nested `transaction`(AML 과 동일 필드 `memberRef`·`transactionRef`·`channel`·`amount`·`currency`·`corridor`·`receiverName`·`receiverCountry`·`senderHolderName`)을 전송하고 `FdsIngestTestController.TestEvent` 가 그대로 소비(기존 4필드만 소비→나머지 흡수), FDS 라이브 판정(`ingestLiveDecision`)이 `transactionRef` 을 **payload 원문 그대로** 사용(조작 `txn-live-{seq}` 폐기)·`FdsRuleCatalog` ACTIVE 룰 실평가(hash 파생 폐기) → 한 거래가 FDS 판정(§5.5 `transactionRef`)·AML 알림에 동일 `transactionRef`. seed 판정/케이스 픽스처 폐기(인입 0=빈 목록). 비-prod 전용(위임/prod fail-closed 불변). DB 스키마 무변경. | aegis-spec. 코드=truth. 근거=bo-api `FdsDecisionCaseStubService.ingestLiveDecision`·`FdsIngestTestController.TestEvent`·`FdsRuleCatalog`. 기능정의서 §8.2/§11.1 BR-005·integration(동일 transaction FDS+AML)·AML §7.1 BR-DEMO-HONESTY 동기화. DB 불변. |
| 2026-06-30 | v2.10 | **hanpass-ph 재그라운딩(코드 정본 `com.aegis.fds` 1:1 정합).** (1) 헤더 — 운영 도메인=hanpass-ph 5채널 명시, 책임 패키지 `com.hanpass.fds`→`com.aegis.fds` 정정, 코드 정본 핀(컨트롤러·DTO·`ChannelType`/`EventFamily`/Flyway V17·V20·V22) 추가. (2) §2.2 `Tenant-Id`=hanpass-ph 단일 운영 테넌트 `tenant_demo`(테넌트=서비스 모델은 스키마 truth 유지). (3) **§3.5 신설 — hanpass 채널 5유형(`CROSS_BORDER_REMIT`/`DOMESTIC_REMIT`/`CASH_IN`/`WALLET_PAYMENT`/`WALLET_WITHDRAWAL`)·eventType taxonomy(`remit`/`domestic`/`wallet` family, `*.requested`)·phpEquivalent 룰 feature(`transaction.phpEquivalent` PHP 환산 임계 표, V22 정합)**. (4) §5.1 `IngestEventRequest` DTO를 코드 record와 1:1 정합(`messageVersion`/`merchant`/`device`/`corridor`/`geoCountry`/`canonicalPayload` 반영, 가공의 `location`/`LocationDto` 제거, sub-DTO 필드 코드 정합), ChannelDto=운영 5종. (5) §5.3 `EvaluateRequest`를 코드 DTO(`eventId`/`transactionRef`/`subjectRef`/`sourceSystem`/`canonicalPayloadJson` 경량 body)로 정정(과거 "IngestEventRequest 동일 구조" 폐기). (6) §5.4 `DecisionResponse`에 코드 필드(`eventId`/`transactionRef`/`subjectRef`/`caseId`/`amount`/`currency`/`amountBase`/`baseCurrency`/`channelType`/`sendCountry`/`receiveCountry`) + `RuleRef`(`ruleName`/`outcome`) 반영. (7) §7.2 reasonCode 예시를 송금·월렛 도메인으로 교체(비-hanpass crypto/trade/seller/invoice 제거). (8) §10 OpenAPI — `ChannelType`(5종)·`EvaluateDecisionRequest` schema 신설, `RuleRef`/`DecisionResponse` 코드 필드 보강, `channelScope`/`CaseType` 주석에 hanpass 운영 범위·닫힌 enum 보존 명시. (9) §4.8 소스 카탈로그에서 `inbound-svc`/`INBOUND_REMIT` 제거(5채널 범위). enum/엔드포인트/scope/인증/HTTP·4-eyes 정본 불변(코드 닫힌 enum은 보존하되 hanpass 미사용 도메인 주석). `RuleRef` 는 v2.8·v2.9(ours)의 `ruleNo`/`displayName`/`reference` 와 union 유지. | java-implementer |
| 2026-06-28 | v2.9 | **Travel Rule(`TRAVEL_RULE_MISSING`) `reference`(MISSING_FIELD)를 수령방식별로 정합(코드=truth).** 해외송금 수령 방식(`payoutMethod`: ACCOUNT_TRANSFER/CASH_PICKUP/WALLET)에 따라 필수 수취인 정보가 달라, `RuleRef.reference`(type=MISSING_FIELD)가 `{payoutMethod, requiredFields[], missingFields[], corridor}`를 담는다. `requiredFields`=방식별 필수(계좌이체 이름·계좌·은행 / 캐시픽업 이름·전화·신분증 / 지갑 이름·지갑주소), `missingFields`⊆required(캐시픽업은 계좌번호 미보고). 필드 key·방식 코드만(원문 PII 미포함). AML VASP `completenessStatus`(§02-aml §3.14)와는 별개 모델. | aegis-spec. 코드=truth. 근거=bo-api `travelRuleReference`. |
| 2026-06-28 | v2.8 | **`RuleRef`에 룰별 참조 데이터(`reference`) 추가 + 누적 드리프트(`ruleNo`/`displayName`) 정정(코드=truth).** OpenAPI `RuleRef` 스키마에 `reference`(object, nullable — 룰 종류별 드릴인 근거: `BLOCKLIST_MATCH` 대포통장 명단 계좌 / `VELOCITY_WINDOW` 기여 거래 리스트 / `GEO_ANOMALY`·`WALLET_RISK`·`MISSING_FIELD`, **마스킹 토큰만·raw PII 미포함**)와 기존 구현 필드 `ruleNo`·`displayName`을 명시(스키마-코드 누적 이격 해소). §5.4 `DecisionResponse.matchedRules` 가 본 RuleRef 사용. 가산 필드(비파괴). | aegis-spec. 코드=truth. 근거=bo-api `FdsDecisionCaseDtos.RuleRef`·`ruleReferenceFor`. |
| 2026-06-21 | v2.7 | **룰 추천 엔드포인트·빌더 인라인 시뮬 반영(코드 정합).** §4.6 Rule/Simulation Admin 표에 `POST /api/v1/admin/fds/rules/recommendations`(scope `fds:rule:simulate`, 4-eyes —) 추가 — 목표 적중률 → 단일 피처 임계값 percentile 역산 + 엔진 재평가 검증, read-only(결재 불필요), 집계·임계값만 반환(raw PII/피처값 미반환). §5.9a `RuleRecommendationRequest`/`RuleRecommendationResponse` DTO 신설(요청 `featureKey`●·`targetHitRate`●(0<x≤1)·`direction`(GTE/LTE)·`channelScope`·`sampleWindow` / 응답 `recommendedThreshold`·`expectedHitRate`(scale4)·`sampleSize`·`alternatives`[]). 모집단=거래(이벤트) 기준·표본 500 근사·비수치/빈 표본 graceful(`sampleSize=0`). bo-api 제네릭 패스스루 위임(신규 코드 없음), 기존 enum·인증 불변. | api-designer |
| 2026-06-21 | v2.6 | **코드 정합(저장소 fds-svc 컨트롤러 1:1) — 이벤트·결정 조회 API 표면화.** (1) §4.1에 **`GET /api/v1/fds/events` 목록 엔드포인트 신설**(필터 `sourceSystem`/`eventType`/`eventFamily`/`channelType`/`subjectRef`/`transactionRef`/`from`/`to` · 페이지네이션, scope `fds:case:read`) — 거래 인입 내역(원본 이벤트) 브라우즈. 기존 단건 `GET /events/{eventId}` 유지(`EventQueryController`). (2) §4.2 `GET /api/v1/fds/decisions` 필터를 **11종**(`transactionRef`·`subjectRef`·`ruleNo`·`decision`·`channelType`·`currency`·`amountMin`·`amountMax`·`sendCountry`·`receiveCountry`·`from`·`to`)으로 확장(`DecisionQueryController`) — 채널/금액/corridor 축은 연결 canonical event LEFT JOIN 파생(DB §5.10·§5.5). 인증·멱등·기존 enum 불변. | api-designer |
| 2026-06-19 | v2.5 | **테넌트=서비스 재정의 + 기관 참조(institution_ref) 컬럼 신설(1 기관 : N 서비스)**: §1.1/§2.2/§9/§11.1/§11.2/§13 설명 텍스트의 '고객사'를 '서비스(테넌트=서비스)'로 정정(계층 기관→서비스(테넌트)→워크스페이스). `TenantDto`에 상위 기관 참조 `institutionRef`(=`fds_tenants.institution_ref`, nullable·additive) 필드 추가 + 설명에 1 기관 : N 서비스 노출. `tenant_id`/`Tenant-Id` 헤더·scope 코드·엔드포인트 경로·enum 불변(라벨/설명만). | api-designer |
| 2026-06-18 | v2.4 | **데이터 레이어 hanpass-ph 소스 재그라운딩 — 소스 카탈로그·channel·corridor·연동 키**(규제 불변): (1) §4.8 source-systems 엔드포인트에 hanpass-ph 소스 카탈로그(`member-svc`/`walletchg-svc`/`domestic-svc`/`remit-svc`/`wallet-svc`/`tx-history-svc`/`inbound-svc`, REST sync 인입) 주석. (2) §5.1 `ChannelDto.channelType`을 **21종**(`CASH_IN`·`INBOUND_REMIT` 추가) 참조로 갱신, `TransactionDto`에 corridor(`CorridorDto`: `sendCountry`/`receiveCountry`/`sendCurrency`/`receiveCurrency`) + `amountBase`(USD) 출처(remit `usd_amount`/`report_amount`) 명시. (3) §10 OpenAPI `channelScope` enum desc 19→21종. **CTR/STR 임계·기한·KoFIU 분류 미변경(규제 불변)**. | api-designer |
| 2026-06-11 | v2.3 | QA HIGH 3건(L59·L155·L156) 해소: §5.7 `ActionResponse`에 `actionType`(enum action_type 23종, DB §5.12) 필수 응답 필드 추가, §5.6 `CasePatchRequest`에 `reason`(선택 — `status=IN_REVIEW` 재오픈 시 필수, PRD §11.2 BR-006) 추가, §4.6 `GET /admin/fds/rules` 필터에 `decisionOutcome`·`evaluationMode`·`ruleNo` 추가(PRD §6.1 BR-001 5축) — §10 OpenAPI에 `ActionResponse`·`CasePatchRequest` schema 및 `/admin/fds/rules` path 반영. | api-designer |
| 2026-06-11 | v2.2 | QA HIGH 3건(L115·L116·L190) 해소: §5.1 `TransactionDto.transactionType`을 DB §4.19 폐쇄 enum 12종 참조로 변경 + §10 `TransactionType` schema 신설, 헤더 DB 핀 v1.5→v1.7 갱신, §4.8 connector 경로 변수 `{id}`→`{connectorId}` 전수 통일(단건·pause·resume·replay, §5.15/§5.16/§10/§11.1 동기). | api-designer |
| 2026-06-11 | v2.1 | doc-consistency 리포트(all-latest) HIGH 이격 정정: §5.11 evidence export 응답 DTO에 `createdBy`(string(128)) 추가 — DB §5.31 `created_by NOT NULL` 정본 동기화. | api-designer |
| 2026-06-11 | v2.1 | **QA HIGH 이격(api-prd `/connectors/notify-channels` 미정의 경로, doc-consistency-report-all-latest L200) 해소**: §4.8에 `GET/PUT /api/v1/admin/fds/notify-channels` 신설 — tenant 알림 채널(설계서 §13.2 'alert channel' 실재 기능, `channel SLACK/EMAIL/WEBHOOK`·`target`·`events`), scope `fds:admin:source-system`, PUT은 `SFDS_TENANT:ADMIN` 전용·감사 기록(4-eyes 아님, PRD TNT-002 ⑤ BR-001). §11.1 BO 화면 매핑에 'TNT-002 ⑤ 알림·소스 탭' 행 추가. PRD §3.2 비정본 경로 `/connectors/notify-channels`는 본 경로로 교체(설계서↔API↔PRD 3자 일치). | api-designer |
| 2026-06-10 | v2.0 | **QA 리포트 높음 이격(API 명세 담당) 정정.** (1) **§13 4-eyes 게이트 종수 정정** — "8종" → "9종(`POLICY_PACK` 포함)"으로 수정. integration·tasks는 9종을 따른다(QA #9/#17/#45/동일 오류 전수 해소). (2) **§13 OAuth2 scope `fds:` prefix 통일** — `decision:evaluate`~`admin:credential` 단축 표기를 `fds:decision:evaluate`~`fds:admin:credential` 완전 형식으로 정정, §2.3 정본과 동일화(QA #18). (3) **헤더 DB 버전 핀 v1.3 → v1.5 갱신**(QA #11). (4) **헤더 설계서 핀 v1.5 → v1.9 갱신**. (5) **`TenantDto` 소유 경계 주석 확장** — DB §5.1 `tenant_status`·`display_name`·`compliance_policy(JSONB)` 필드가 fds-svc 엔진 DTO에 미포함인 이유를 "bo-api 소유 경계"로 명시(QA #10/#12). PRD/PPT는 해당 필드 노출·변경을 bo-api 호출로 기재할 것. | api-designer |
| 2026-06-10 | v1.9 | **준법감시인 검토 반영(설계서 v1.9·DB v1.5 동기화)**: (1) §5.5 `CaseDto.closeReason`에 enum **8종**(`FP_THRESHOLD`/`FP_NORMAL_PATTERN`/`FP_DATA_QUALITY`/`CONFIRMED_FRAUD`/`CONFIRMED_MULE`/`CONFIRMED_ATO`/`ESCALATED_AML`/`OTHER`, DB §4.11 정본) 확정 — `POST /fds/cases/{caseId}/close` 요청 시 필수, 상세 메모(자유 텍스트)는 case event(`CLOSED` payload) 보조 저장으로 분리. (2) §4.4 close 엔드포인트 설명 동기화(`closeReason` 필수 enum 표기). 재오픈(REOPEN) 상태 전이는 설계서 §11.6.1 정본(케이스 상태 전이는 `PATCH /fds/cases/{caseId}` status 변경 규칙으로 수용, 신규 엔드포인트 없음). | api-designer |
| 2026-06-10 | v1.6 | **규제 팩(Policy Pack) 토글 4-eyes `subjectKind=POLICY_PACK` 추가**(설계서 §11.5·§16.2 v1.6 + DB §5.23 v1.4 동기화, doc-consistency QA #16/#25 해소): `subject_kind` **8종→9종**으로 OpenAPI `SubjectKind` enum·`ApprovalRequestDto`·4-eyes 결재 대상 매핑표·`§4 원칙`·헤더 DB 참조 전수 갱신. 규제 팩 토글 변경(`PUT /api/v1/bo/fds/tenants/{tenantId}` compliance_policy)은 `POLICY_PACK`(subjectRef=`tenant_id`, approval_line `COMPLIANCE_MANAGER`)로 매핑. | api-designer |
| 2026-06-06 | v1.0 | 정본(4서비스·헥사고날) 및 설계서 `01-fdsSvc-sass.md` v1.1 + DB 설계서 `01-fds-db.md` v1.0 기준 fds-svc API 명세서 신규 생성. Ingest/Decision/Action/Case/Evidence 외부 API + Rule/Group/Source/Credential/Approval Admin API 엔드포인트 표, DTO 스키마(DB 컬럼 매핑), 표준 에러 모델(`FDS-*`), reason/decision code 사전, 4-eyes 결재 대상 표, OpenAPI YAML 스니펫, BO 화면↔API 매핑 확정. 격리 `Tenant-Id/Workspace-Id` 헤더·`dataScope` 토큰 claim·멱등성·버저닝(`/api/v1`)·PII 미노출 규약 반영. AML 본처리 aml-svc 위임(`amlCaseRef`), IAM/승인 라인 bo-api 소유 경계 명시. | api-designer |
| 2026-06-06 | v1.1 | 정합성 리포트(doc-consistency-fds) 높음 이격 중 API 명세 담당 항목 정정. (1) **운영자 집계 API 소유 경계 확정** — 대시보드(플랫폼·고객사별)·고객사 관리·감사 조회는 bo-api 소유(`/api/v1/bo/**`)로 명시, 엔진 API §4에 미추가(§1.1·§11.2·§12). 과거 `/api/v1/admin/fds/dashboard|tenants|audit` 엔진 직접 경로 폐기, PRD/PPT는 bo-api 호출로 정정 대상. (2) **action_type 마스터=API enum 23종 정본** 채택, 설계서 §11.2 동기화 지시, `HOLD_TRANSACTION` 비정본 명시. (3) **HTTP 상태코드=§6 정본** 확정(중복400·결재누락409·self409·PII422·rate429). (4) **OpenAPI `DecisionResponse.matchedRules`(RuleRef[]) 추가** — §5.4·DB와 정합, RuleRef schema 신설. (5) **Webhook 콜백 계약(§9 신설)** — 4종 이벤트·envelope·`X-Signature` HMAC·재시도/멱등 확정. | api-designer |
| 2026-06-06 | v1.2 | doc-consistency-fds 재검증 높음 이격(db-api·api-integration·cross) API 명세 담당분 정본 동기화. (1) **`subjectKind` enum=DB 정본 8종(`CASE_CLOSE` 포함, §5.23)으로 확정** — §5.12 ApprovalRequestDto에 `CASE_CLOSE` 추가, OpenAPI `SubjectKind` enum schema 신설, §1.1·§13 downstream 명문화. (2) **case 종결 4-eyes 매핑 `ACTION`→`CASE_CLOSE`(subjectRef=`case_id`) 정정** — §8 case close 행. (3) **`FdsActionResult` 콜백 `actionType`(23종) 필수 명시** + `status`=action_status enum(§4.9) 기준 확정, OpenAPI `ActionStatus` schema 신설(§9.1). (4) **입력 DB 버전 핀 v1.0→v1.1** 갱신(`subject_kind` 8종·`fds_cases.aml_case_id` 반영). 운영자 집계=bo-api 소유 경계는 v1.1 확정분 유지(엔진 API에 대시보드/고객사/감사 미추가). | api-designer |
| 2026-06-07 | v1.4 | 잔존 높음 이격 H2(GRP master) 해소 — §4.7에 위험그룹 마스터 수정 엔드포인트 신설. (1) **`PUT /api/v1/admin/fds/risk-groups/{groupId}`** — 그룹 마스터(틀) 수정/비활성. scope `fds:admin:group`, **4-eyes 대상**(`subjectKind=GROUP`, subjectRef=`group_id`, §8). PRD SFDS-GRP-003 호출 API(`PUT .../risk-groups/{groupId}`) 누락 정합. (2) **DTO §5.18 `RiskGroupUpsertRequest`** — DB `fds_risk_groups`(§5.21) 컬럼 정합 수정 필드만(`displayName`→`display_name`, `active` 비활성 전이), `groupType`(=`group_type`)·`groupId`(=`group_id`) **immutable**(PRD BR-001/BR-002), 변경 시 `FDS-VALIDATION-002`. 비활성(`active=false`)은 `enabled` 컬럼 부재로 **멤버 0 선결**(`fds_risk_group_members` 전건 0) 후 처리, 잔존 시 `FDS-STATE-CONFLICT`(409). PRD 화면의 `source`/`autoEnrollOnHit`/`defaultExpiryDays`/`description`은 `fds_risk_groups` 컬럼 부재로 본 PUT 영속 대상 아님(추측 컬럼 미생성). (3) **응답 DTO §5.19 `RiskGroupDto`** — `groupId`/`groupType`/`displayName`/`memberCount`/`createdBy·updatedBy`/`createdAt·updatedAt` + 결재 게이트 `approvalRequestId`/`status`. (4) OpenAPI 스키마(`RiskGroupType`(DB §4.14 6종)/`RiskGroupUpsertRequest`/`RiskGroupDto`) + path 1종 추가(§10), §6 에러(`FDS-VALIDATION-002` immutable·`FDS-STATE-CONFLICT` 멤버 잔존 Group) 보강, §8 4-eyes 표·§11.1 BO 매핑 갱신. 정본 `target-architecture.md`(bo-web→bo-api→fds-svc, 4-eyes, data-scope) 준수, DB `fds_risk_groups` 컬럼 100% 정합(추측 금지). 운영자 집계=bo-api 소유 경계 유지(미추가). | api-designer |
| 2026-06-08 | v1.5 | **격리(isolation_mode) → 배포 모델(deployment topology) 재설계** 동기화(설계서 `01-fdsSvc-sass.md` v1.5 §13/§11.6.11/§11.6.11a/§12.8 + DB `01-fds-db.md` v1.3 §4.1/§5.1/§9 + 정본 target-architecture §4.1 기준). 본 문서는 **엔진 API 명세**이며 운영자 집계=bo-api 소유 경계에 따라 **온보딩 엔드포인트를 엔진 API(§4)에 추가하지 않는다**. enum/DTO/소유 경계만 동기화: (1) **OpenAPI(§10) enum 2종 신설** — `DeploymentModel{MANAGED_DEDICATED, SELF_HOSTED, SHARED}`(3종)·`OnboardingStatus{REQUESTED, PROVISIONING, DEPLOYED, VERIFIED, ACTIVE, PACKAGE_ISSUED, CUSTOMER_DEPLOYED, REGISTERED}`(8종), DB `fds_tenants.deployment_model`/`onboarding_status`와 1:1. (2) **`TenantDto` schema 신설** — `tenantId`/`deploymentModel`/`onboardingStatus`/`region`(=`default_region`)/`infraRef`(=`infra_ref`), **`isolationMode` 필드 폐기**(bo-api 소유, 엔진 API 미노출). (3) **§11.2 bo-api 소유 경계 표 갱신** — 고객사 등록을 '격리 토글'에서 '배포 유형 선택+온보딩 신청/상태'로, 집약 출처를 `deployment_model`/`onboarding_status`/`region`/`infraRef`로 교체, 온보딩 bo-api 전용 엔드포인트 3종 신설(`POST .../onboarding/provision`, `GET .../onboarding`, `POST .../onboarding/register`). tenant_id 라우팅 의미 재정의(전용 배포=배포=고객사 단일, SHARED만 헤더 행 라우팅) 명문화. (4) **§13 downstream**에 배포 모델/온보딩 enum·DTO·엔드포인트·상태머신·라우팅 의미 확정. (5) 입력 DB 핀 v1.1→v1.3, 설계서 핀 v1.5 갱신. 폐기: `isolation_mode` 컬럼·enum(`SHARED`/`SCHEMA`/`DB`)·격리 라디오. 운영자 집계·온보딩=bo-api 소유 경계 유지. | api-designer |
| 2026-06-08 | v1.6 | 정합성 리포트(doc-consistency-fds-latest) API 명세 담당 이격 정정(상위 DB v1.3·설계서 v1.5 정본 동기화). (1) **db-api length·필수 정합** — §5.14 `ExternalDecisionRequest`: `vendorName` string(96)·`bridgeMode`(●) 필수 추가, `vendorDecisionRef`(256)/`vendorDecision`(32)/`evidenceHash`(128)/`transactionRef`(256) length 병기, DB `fds_external_decisions`(§5.30) NOT NULL·VARCHAR 제약과 1:1. (2) **§5.12 `ApprovalRequestDto.reason`(string △) 추가** — DB `fds_approval_requests.reason TEXT`(§5.23) 표면화(결재함 상신 사유). (3) **MERCHANT_NORMALIZE 엔드포인트 바인딩** — §4.7 `POST /admin/fds/merchants/{merchantRef}/normalize`(scope `fds:admin:group`, 4-eyes) 신설, §8 경로·subjectRef(`merchant_ref`) 채움, approval_line `RISK_MANAGER`(기본)/`EXECUTIVE_APPROVAL`(대규모)로 설계서 §11.5와 동기화, DTO §5.20·OpenAPI `MerchantNormalizeRequest` schema·path·§11.1 매핑·§6 에러 보강. (4) **`POST /fds/events` 비동기 성공코드 정정** — 신규 큐 적재=**202 Accepted**, 멱등 재반환=200/201(§5.2·§4.1·§3.3), 연동 시퀀스와 정합(과거 201 단일 표기 비동기 의미 보강). (5) **§9.1 `FdsActionResult.status` 출처 명확화** — action_status enum 출처를 '§10 OpenAPI ActionStatus 7종 / DB §4.9'로 분리 표기(§4.9 Approval 표와 혼동 제거). (6) **§9.2 webhook `eventFamily` 도메인 분리** — webhook 콜백 그룹핑 enum `decision`/`case`/`action` 3종을 canonical event_family(16종)와 별개로 정본 1줄 고정. 운영자 집계·배포 모델/온보딩 bo-api 소유 경계(v1.5) 유지. | api-designer |
| 2026-06-08 | v1.7 | 정합성 리포트(doc-consistency-fds-latest) API 명세 담당 이격 정정(상위 DB §4.12·§5.14·§5.23 정본 동기화). (1) **`CaseEventDto` 신설(HIGH)** — DTO §5.21에 `caseEventId`/`caseId`/`eventKind`/`payload`/`actorSubject`/`createdAt` 정의(DB `fds_case_events` §5.14 매핑, payload 마스킹·PII 미노출). OpenAPI §10에 `CaseEventKind` enum 6종(`ASSIGNED`/`COMMENT`/`STATUS_CHANGE`/`EVIDENCE_ATTACHED`/`APPROVAL`/`CLOSED`, DB §5.14 정본) + `CaseEventDto` schema 신설, `GET /fds/cases/{caseId}/events` path를 §3.2 페이지네이션 envelope(content[]=CaseEventDto)로 responses/200 연결. event_kind 6종 코드값 명시(LOW 동시 해소). (2) **OpenAPI `ApprovalStatus` enum 신설(MEDIUM)** — 8종(`DRAFT`/`SUBMITTED`/`APPROVED`/`REJECTED`/`CANCELLED`/`EXPIRED`/`EXECUTED`/`EXECUTION_FAILED`, DB §4.12), `ApprovalRequestDto.status` $ref 연결. (3) **OpenAPI `ApprovalLine` enum 신설(MEDIUM)** — 6종(`SELF_APPROVAL_DISABLED`/`MAKER_CHECKER`/`COMPLIANCE_MANAGER`/`RISK_MANAGER`/`SECURITY_ADMIN`/`EXECUTIVE_APPROVAL`, DB §4.12), `ApprovalRequestDto.approvalLine` $ref 연결. `ApprovalRequestDto` OpenAPI schema 신설 + §5.12 산문에 DB §4.12 코드값·OpenAPI enum 참조 명문화. (4) **SFDS-APPR-001 필터 파라미터 정의(MEDIUM)** — §4.9 `GET /admin/fds/approvals`에 `subjectKind`/`status`/`maker` 3종 필터 공식 정의, OpenAPI path 신설(query params + ApprovalRequestDto 페이지 응답)로 PRD §12.1과 정합. (5) **§5.15 `lagSeconds` 타입 표기 정정(LOW)** — 산문 'integer' → 'long(int64)'(DB BIGINT·OpenAPI `format: int64` 일관화). 운영자 집계·배포 모델/온보딩 bo-api 소유 경계(v1.5·v1.6) 유지. | api-designer |
| 2026-06-08 | v1.8 | QA 리포트(doc-consistency-fds-latest) API 담당 중간·낮음 이격 정합화. #1 §10 OpenAPI schemas에 `ExternalDecisionMode` enum 5종(`VENDOR_RESULT_INGEST`/`DB_MIRROR`/`DUAL_RUN`/`SHADOW_DECISION`/`RULE_MIGRATION`) 추가, §5.14 `bridgeMode` `$ref` 연결 및 허용값 명시(DB §4.18 정본). #2 §5.13에 `CredentialDto` 조회 응답 필드표 추가(8종: credentialId/credentialType/scopes/ipAllowlist/webhookUrl/enabled/createdAt/updatedAt, secret 미노출, DB §5.29 정본). #3 §5.11 `EvidenceExportRequest` 응답에 `approvalRequestId`(uuid, nullable) 추가(DB §5.31 정본). #15 §4.9 표에 scope 열 추가(GET=`fds:case:read`, POST approve/reject=`fds:action:write`), §10 OpenAPI POST approve·reject path 신설(security `fds:action:write` 명시, 설계서 §12.8 정합). #16 §13 downstream 핵심 엔드포인트 `GET /admin/fds/approvals/{id}/approve` → `POST /admin/fds/approvals/{approvalRequestId}/approve` 정정(§4.9 정본). #5 §5.5 `CaseDto`에 `createdBy/updatedBy`(string(128), nullable) 추가(DB §5.13 정본). #7 §5.5 `closeReason` 타입 `string` → `string(64)` 정정(DB §5.13 VARCHAR(64) 정본). #6 §5.8 `RuleDto`에 감사 4종(`createdAt`/`updatedAt`/`createdBy`/`updatedBy`) 추가(DB §5.17 정본). #8 §5.9 `RuleSimulationResponse`에 `createdAt`/`createdBy` 추가(DB §5.19 정본). | api-designer |
| 2026-06-06 | v1.3 | 잔존 높음 이격 CONN-002/CONN-003 해소 — §4.8에 커넥터/소스시스템 운영자 엔드포인트 4종 신설. (1) **`GET /admin/fds/connectors/{id}`** — connector 단건 health(`fds_connector_offsets` §5.28, `connector_status`/`lag_seconds`/`last_error_code`, cursor 마스킹) 조회, scope `fds:admin:source-system`. (2) **`POST /admin/fds/connectors/{id}/pause`** — `connector_status`→`DISABLED` 일시중지(offset 보존). (3) **`POST /admin/fds/connectors/{id}/resume`** — `DISABLED`→`HEALTHY` 재개(보존 offset 소비). pause/resume 멱등·`FDS-STATE-CONFLICT`. (4) **`PUT /admin/fds/source-systems/{id}`** — 소스시스템 속성·capability 매트릭스 수정(`enabled`/`schemaVersion`/`ingestMode`/`failPolicy`/`capabilities`=`control_capability` DB §4.6 부분집합, `fds_source_systems` §5.3), **4-eyes 대상**(`subjectKind=MAPPING`, subjectRef=`source_system`, §8). DTO §5.15~§5.17 신설, OpenAPI 스키마(`ConnectorDto`/`ConnectorStateChange*`/`SourceSystemUpdateRequest`/`SourceSystemDto`/`ConnectorStatus`/`IngestMode`/`FailPolicy`/`ControlCapability`) + path 4종 추가(§10), §6 에러 발생 API 보강, §8 4-eyes 표·§11.1 BO 매핑 갱신. 설계서 §9.4 capability·§12 connector 운영 근거 및 정본 target-architecture 준수. 운영자 집계(대시보드/고객사/감사)=bo-api 소유 경계 유지(미추가). | api-designer |
