# FDS API 명세서 (fds-svc REST)

> 정본: `.claude/skills/_shared/target-architecture.md` (4서비스 모노레포 · Java 25 · Spring Boot 3.5.x · 헥사고날 · 멀티테넌시 · PII 마스킹 · 4-eyes · 한국 Policy Pack).
> 입력 설계서: `docs/software/01-fdsSvc-sass.md` v1.1 (§6.2 헥사고날 `adapter/in/rest`, §11 action/case/결재, §12.8 Public API, §13 멀티테넌시, §16 PII/규제).
> 입력 DB: `docs/design/db/01-fds-db.md` **v1.7** (스키마 `fds`, 멀티테넌시 `tenant_id/workspace_id/data_scope`, enum 코드값 §4, 컬럼/타입 §5, `subject_kind` 9종 `CASE_CLOSE`·`POLICY_PACK` 포함 §5.23, `fds_cases.aml_case_id` §5.13, **배포 모델 `fds_tenants.deployment_model`(3종)·`onboarding_status`(8종)·`default_region`·`infra_ref` §4.1·§5.1, 구 `isolation_mode` 폐기**, `close_reason` 8종 §4.11, `compliance_policy` JSONB §5.1, **`transaction_type` 폐쇄 enum 12종 §4.19**).
> 입력 설계서 핀: `docs/software/01-fdsSvc-sass.md` **v1.9** (§13 배포 모델·온보딩 프로비저닝·키 의미 재정의, §11.6.11 `deployment_model`, §11.6.11a `onboarding_status` 상태머신, §12.8 서비스 관리=배포 유형+온보딩, §11.6.1a `close_reason` 8종, §11.6.1 REOPEN 전이, §11.5 `subject_kind` 9종, §16.2 규제 팩 토글).
> 책임 서비스: **`services/fds-svc`** (`com.hanpass.fds.adapter.in.rest`). AML/STR/CTR/Travel Rule 본 케이스는 `aml-svc`, 운영자 IAM·결재 집약·감사는 `bo-api`. **bo-web은 bo-api만 호출(엔진 직접호출 금지)**.

## 목차
1. [범위·원칙](#1-범위원칙)
2. [인증·인가·격리](#2-인증인가격리)
3. [횡단 규약 (버저닝·페이지네이션·멱등성·에러)](#3-횡단-규약)
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
- fds-svc는 `OPEN_AML_CASE`/`REGULATORY_REPORT`/`REQUEST_TRAVEL_RULE_INFO` **후보만 생성**하고 본 처리는 aml-svc로 위임(§12). 본 API는 후보 등록·cross-ref 조회만 제공.

### 1.1 정본 확정 (이 문서가 진실의 출처)

정본 위계는 `_shared/target-architecture.md` + 설계서(`docs/software`)·DB(`docs/design/db`)·API(`docs/design/api`)이며, 파생(integration·tasks·PRD·PPT)은 이를 따른다. 본 API 명세는 다음 항목의 **정본**이다.

- **action_type 마스터 = API `ActionType` enum 23종(전수, §5.7·§7·§10 OpenAPI)**. 설계서 §11.2는 이 23종으로 동기화한다. 설계서 §15의 verb는 정규 매핑(`OPEN_*_CASE`=`OPEN_CASE`+`case_type`, `SUSPEND_MERCHANT`=`SUSPEND_INSTRUMENT`, `SEND_SECURITY_ALERT`=`SEND_ALERT`)으로 흡수한다. `HOLD_TRANSACTION`은 비정본 — 자금 hold는 `HOLD_FUNDS`, 송금 차단은 `BLOCK_TRANSACTION`.
- **HTTP 상태코드 = 본 API 명세 §6이 정본**. PRD/PPT는 §6 매핑을 따른다(중복=400 `FDS-VALIDATION-001`, 결재 누락=409 `FDS-APPROVAL-REQUIRED`, maker=checker=409 `FDS-APPROVAL-SELF`, raw PII=422 `FDS-PII-REJECTED`, rate limit=429 `FDS-RATE-LIMIT`).
- **4-eyes `subjectKind` = DB 정본 `fds_approval_requests.subject_kind` 9종(§5.23)과 1:1**. `ACTION`/`RULE`/`MAPPING`/`SECRET`/`GROUP`/`EXPORT`/`MERCHANT_NORMALIZE`/`CASE_CLOSE`/`POLICY_PACK`. **case 종결(`POST /fds/cases/{caseId}/close`)은 `CASE_CLOSE`(subjectRef=`case_id`)로 매핑**하고, **규제 팩 토글 변경(`PUT /api/v1/bo/fds/tenants/{tenantId}` compliance_policy)은 `POLICY_PACK`(subjectRef=`tenant_id`, 설계서 §16.2)로 매핑**한다. integration·tasks는 이 9종을 따른다.
- **Webhook 콜백 계약 = §9가 정본**. 4종(`FdsDecisionCreated`/`FdsCaseOpened`/`FdsCaseStatusChanged`/`FdsActionResult`)·핵심 payload·envelope·`X-Signature` HMAC·재시도/멱등을 §9로 확정한다. `FdsActionResult`는 `actionType`(action_type 23종)을 **필수 포함**하고 `status`는 action_status enum 기준이다. integration §3.2·§4.x는 §9.1 핵심 키와 1:1 정렬한다.
- **운영자 집계 API 소유 경계 = bo-api(§12)**. 대시보드(플랫폼·서비스별)·서비스 관리(목록/상세/등록/설정)·감사 조회 화면이 호출하는 집계 엔드포인트는 **bo-api가 소유·집약·인증**한다. fds-svc/aml-svc는 저수준 데이터 API만 제공하며, **본 엔진 API 명세(§4)에는 운영자 집계 엔드포인트(대시보드/서비스/감사)를 추가하지 않는다**. PRD/PPT의 해당 화면은 호출 대상을 bo-api로 명시한다.

---

## 2. 인증·인가·격리

### 2.1 인증 방식 (설계서 §12.8)
| 방식 | 용도 | 적용 API |
|---|---|---|
| API Key + HMAC(`X-Api-Key` + `X-Signature: hmac-sha256=...`) | 서버 간 기본 연동 | 외부 Ingest/Decision/Case/Evidence API |
| OAuth2 Client Credentials (`Authorization: Bearer`) | 권한 scope 세분화 | 외부 API, Admin API(bo-api 위임 토큰) |
| mTLS | 고위험 action API | Decision/Action 계열 옵션 |
| Webhook signature(`X-Signature`) | 고객 callback 위변조 방지 | Webhook 송신 |

- 인증 주체는 `fds_api_credentials`(`credential_type` = `API_KEY`/`OAUTH2_CLIENT`/`MTLS`/`WEBHOOK`)로 검증. **secret 원문 미저장 — `secret_hash` 대조**.
- API key·OAuth2 client·webhook은 `(tenantId, workspaceId)`에 바인딩. cross-workspace 접근은 명시적 scope 필요.

### 2.2 격리 컨텍스트 (필수 헤더)
| 헤더 | 매핑 컬럼 | 필수 | 설명 |
|---|---|---|---|
| `Tenant-Id` | `tenant_id` | 필수(외부) | SaaS 서비스 경계(테넌트=서비스, 상위 기관 institution이 운영하는 서비스 1종). Admin API는 위임 토큰 claim에서 주입 |
| `Workspace-Id` | `workspace_id` | 선택(미지정 시 `default`) | `retail`/`corporate`/`prod`/`sandbox`. `sandbox`는 shadow-only(action 미발행) |
| `Source-System` | `source_system` | Ingest/Decision 필수 | connector·schema 식별 |
| `Idempotency-Key` | `idempotency_key` | 멱등 엔드포인트 필수 | 중복 방지(§3.3) |
| `X-Signature` | — | HMAC 인증 시 필수 | `hmac-sha256=...` |
| `traceId`(`X-Trace-Id`) | `fds_audit_logs.trace_id` | 선택 | 관측성 전파(설계서 §17) |

- `dataScope`는 **헤더가 아니라 위임 토큰 claim**으로 전달된다. bo-api가 운영자 토큰의 `dataScope` 집합을 Admin API 호출 시 fds-svc 조회의 강제 IN 필터로 주입한다(저장 격리 아님, 조회·조치 권한 필터).

### 2.3 OAuth2 scope (설계서 §12.8, `fds_api_credentials.scopes`)
`fds:event:write` · `fds:decision:evaluate` · `fds:case:read` · `fds:case:update` · `fds:evidence:export` · `fds:rule:simulate` · `fds:admin:source-system` · `fds:admin:rule` · `fds:admin:group` · `fds:admin:credential` · `fds:action:write`

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

---

## 4. 엔드포인트 표

### 4.1 Ingest API (외부) — `fds:event:write`
| 메서드 | 경로 | 설명 | 인증/scope | 멱등 | 4-eyes |
|---|---|---|---|---|---|
| POST | `/api/v1/fds/events` | canonical event 비동기 수신(큐 적재). 신규=**202 Accepted**, 멱등 재반환=200/201(§5.2). `fds_canonical_events` insert | API Key+HMAC / `fds:event:write` | 필수 | — |
| POST | `/api/v1/fds/events:batch` | 다건 event 수신(최대 500). 신규 큐 적재=**202 Accepted** | `fds:event:write` | 필수 | — |
| GET | `/api/v1/fds/events` | canonical event 목록 조회(필터: `sourceSystem`,`eventType`,`eventFamily`,`channelType`,`subjectRef`,`transactionRef`,`from`,`to` · 페이지네이션). 거래 인입 내역(원본 이벤트) 브라우즈 — 결정·케이스 화면의 역참조 목록. 마스킹 | `fds:case:read` | — | — |
| GET | `/api/v1/fds/events/{eventId}` | event 단건 상태·정규화 결과·canonicalPayload 조회(마스킹) | `fds:case:read` | — | — |

### 4.2 Decision API (외부) — `fds:decision:evaluate`
| 메서드 | 경로 | 설명 | 인증/scope | 멱등 | 4-eyes |
|---|---|---|---|---|---|
| POST | `/api/v1/fds/decisions/evaluate` | 승인 전 실시간 FDS 판단. `fds_decisions`+`fds_decision_reasons` 생성 | API Key+HMAC/mTLS · `fds:decision:evaluate` | 필수 | — |
| GET | `/api/v1/fds/decisions/{decisionId}` | decision 단건(증적: matched_rules·feature_snapshot 요약) | `fds:case:read` | — | — |
| GET | `/api/v1/fds/decisions` | decision 목록(필터 11종: `transactionRef`,`subjectRef`(대상 토큰),`ruleNo`(적중 룰 번호),`decision`,`channelType`,`currency`,`amountMin`,`amountMax`,`sendCountry`,`receiveCountry`,`from`,`to` · 페이지네이션). 채널/통화/금액/corridor 축은 연결 canonical event LEFT JOIN 파생(DB §5.10·§5.5) | `fds:case:read` | — | — |

> 장애 정책(D-14): `fds_source_systems.fail_policy`(`FAIL_CLOSED`/`FAIL_OPEN`/`CASE_ONLY`)에 따라 평가 불가 시 응답 `decision` 결정. `CASE_ONLY`는 `REVIEW`+case 후보.

### 4.3 Action API (외부/위임) — `fds:action:write`
| 메서드 | 경로 | 설명 | 인증/scope | 멱등 | 4-eyes |
|---|---|---|---|---|---|
| GET | `/api/v1/fds/actions/{actionId}` | action outbox 상태(`fds_actions.status`) 조회 | `fds:case:read` | — | — |
| POST | `/api/v1/fds/cases/{caseId}/actions` | case 기반 수동 action 상신(outbox 등록) | `fds:action:write` | 필수 | 자금/규제성 action 필수 |

> 자금성(`HOLD_FUNDS`/`RELEASE_HOLD`/`CANCEL_TRANSACTION`/`REQUEST_REVERSAL`/`HOLD_SETTLEMENT`) 및 규제성(`REGULATORY_REPORT`/`OPEN_AML_CASE`) action은 `fds_approval_requests`를 생성하고 `status=APPROVAL_REQUIRED`로 hold. 승인 완료 후 relay(§8).

### 4.4 Case API (외부/위임) — `fds:case:read` / `fds:case:update`
| 메서드 | 경로 | 설명 | scope | 4-eyes |
|---|---|---|---|---|
| GET | `/api/v1/fds/cases` | case 목록(필터: `status`,`caseType`,`priority`,`assignedTo`,`from/to`) | `fds:case:read` | — |
| GET | `/api/v1/fds/cases/{caseId}` | case 단건 + 요약 | `fds:case:read` | — |
| GET | `/api/v1/fds/cases/{caseId}/events` | case timeline(`fds_case_events`, append-only) | `fds:case:read` | — |
| PATCH | `/api/v1/fds/cases/{caseId}` | status/priority/assignee 변경 | `fds:case:update` | `INTERNAL_AUDIT` 종결 시 필수 |
| POST | `/api/v1/fds/cases/{caseId}/assign` | 담당자 배정 | `fds:case:update` | — |
| POST | `/api/v1/fds/cases/{caseId}/close` | case 종결(`closeReason` **필수** — enum 8종 §5.5 + 상세 메모 선택) | `fds:case:update` | 내부감사·규제 case 필수 |
| POST | `/api/v1/fds/cases/{caseId}/feedback` | false positive feedback 등록 | `fds:case:update` | — |

> `caseType IN (AML_REVIEW, CRYPTO_TRAVEL_RULE, REGULATORY_REPORT)`는 fds-svc가 origin만 보유. 본 조사·STR/CTR/Travel Rule 처리·종결은 aml-svc API(별도 명세). 응답에 `amlCaseRef`(cross-ref) 노출.

### 4.5 Evidence API (외부) — `fds:evidence:export`
| 메서드 | 경로 | 설명 | scope | 4-eyes |
|---|---|---|---|---|
| GET | `/api/v1/evidence/fds/cases/{caseId}/timeline` | case 증적 timeline | `fds:evidence:export` | — |
| GET | `/api/v1/evidence/fds/reports/decisions` | 기간별 decision 리포트(`from`,`to`) | `fds:evidence:export` | — |
| POST | `/api/v1/evidence/fds/exports` | evidence export 요청(`fds_evidence_exports`) | `fds:evidence:export` | 최종본(`export_kind` 제출용) 필수 |
| GET | `/api/v1/evidence/fds/exports/{exportId}` | export 상태·manifest hash | `fds:evidence:export` | — |
| GET | `/api/v1/evidence/fds/exports/{exportId}/download` | 생성 파일 다운로드(감사 기록) | `fds:evidence:export` | — |

### 4.6 Rule / Simulation Admin API (위임) — `fds:admin:rule` / `fds:rule:simulate`
| 메서드 | 경로 | 설명 | scope | 4-eyes |
|---|---|---|---|---|
| GET | `/api/v1/admin/fds/rule-sets` | rule set 목록(`fds_rule_sets`) | `fds:admin:rule` | — |
| GET | `/api/v1/admin/fds/rules` | rule 목록(필터: `ruleSetId`,`status`,`channelScope`,`decisionOutcome`,`evaluationMode`,`ruleNo`(텍스트검색) — PRD §6.1 BR-001 5축) | `fds:admin:rule` | — |
| POST | `/api/v1/admin/fds/rules` | rule 초안 생성(`status=DRAFT`) | `fds:admin:rule` | — |
| PUT | `/api/v1/admin/fds/rules/{ruleId}` | rule 수정(초안) | `fds:admin:rule` | — |
| POST | `/api/v1/admin/fds/rules/{ruleId}/activate` | rule 활성화 상신 | `fds:admin:rule` | **필수** |
| POST | `/api/v1/admin/fds/rules/{ruleId}/disable` | rule 비활성 | `fds:admin:rule` | tenant policy |
| POST | `/api/v1/admin/fds/rules/{ruleId}/rollback` | 버전 rollback(`fds_rule_versions`) | `fds:admin:rule` | **필수** |
| GET | `/api/v1/admin/fds/rules/{ruleId}/versions` | rule version 이력 | `fds:admin:rule` | — |
| POST | `/api/v1/admin/fds/rules/simulations` | rule simulation 실행(예상 hit rate) | `fds:rule:simulate` | — |
| GET | `/api/v1/admin/fds/rules/simulations/{simulationId}` | simulation 결과 | `fds:rule:simulate` | — |
| POST | `/api/v1/admin/fds/rules/recommendations` | 룰 추천(목표 적중률 → 단일 피처 임계값 역산·엔진 재평가 검증). read-only(결재 불필요), 집계·임계값만 반환(raw PII/피처값 미반환) | `fds:rule:simulate` | — |
| GET | `/api/v1/admin/fds/feature-catalog` | feature catalog(no-code builder) | `fds:admin:rule` | — |

### 4.7 Risk Group Admin API (위임) — `fds:admin:group`
| 메서드 | 경로 | 설명 | scope | 4-eyes |
|---|---|---|---|---|
| GET | `/api/v1/admin/fds/risk-groups` | group 목록(`fds_risk_groups`) | `fds:admin:group` | — |
| POST | `/api/v1/admin/fds/risk-groups` | group 생성 | `fds:admin:group` | — |
| PUT | `/api/v1/admin/fds/risk-groups/{groupId}` | group 마스터 수정/비활성(`display_name` 수정·`active=false` 비활성, `fds_risk_groups`). `group_id`·`group_type` 변경 불가(BR-001/BR-002), 비활성은 멤버 0 선결 | `fds:admin:group` | **필수** |
| GET | `/api/v1/admin/fds/risk-groups/{groupId}/members` | member 목록 | `fds:admin:group` | — |
| POST | `/api/v1/admin/fds/risk-groups/{groupId}/members` | member 추가(watchlist/denylist 반영) | `fds:admin:group` | **필수** |
| DELETE | `/api/v1/admin/fds/risk-groups/{groupId}/members/{memberRef}` | member 제거 | `fds:admin:group` | **필수** |
| POST | `/api/v1/admin/fds/merchants/{merchantRef}/normalize` | high-risk merchant 정상화 상신(설계서 §11.5, `subjectKind=MERCHANT_NORMALIZE`, subjectRef=`merchant_ref`) | `fds:admin:group` | **필수** |

### 4.8 Source/Connector/Credential Admin API (위임) — `fds:admin:source-system` / `fds:admin:credential`

> **소스 시스템 카탈로그(hanpass-ph 재그라운딩, DB §5.3a)**: `source_system` 식별자는 hanpass-ph 트랜잭션 마이크로서비스(`member-svc`/`walletchg-svc`/`domestic-svc`/`remit-svc`/`wallet-svc`/`tx-history-svc`/`inbound-svc`)로 등록·예시화한다(generic `card-processor`/`core-banking`/`atm-switch` 대체). 업스트림은 `REST_PUSH`(REST sync 인입, 연동 §7.1) 기준이며, 거래 소스는 `transaction.requested`를 emit하고 `channel_type`은 소스별로 `CASH_IN`(walletchg)/`DOMESTIC_REMIT`(domestic)/`CROSS_BORDER_REMIT`(remit)/`INBOUND_REMIT`(inbound)에 대응한다. 연동 키 매핑은 연동 §7.2 정본(원문 금지·token/HMAC). **데이터 레이어 한정 — 규제(CTR/STR) 임계·기한 불변.**

| 메서드 | 경로 | 설명 | scope | 4-eyes |
|---|---|---|---|---|
| GET | `/api/v1/admin/fds/source-systems` | source system 목록 | `fds:admin:source-system` | — |
| POST | `/api/v1/admin/fds/source-systems` | source system 등록 | `fds:admin:source-system` | — |
| PUT | `/api/v1/admin/fds/source-systems/{sourceSystem}/mappings` | field mapping/PII allowlist 변경(`fds_schema_mappings`) | `fds:admin:source-system` | **필수** |
| PUT | `/api/v1/admin/fds/source-systems/{id}` | source system 속성·capability 매트릭스 수정(`enabled`/`schemaVersion`/ingest 설정/`failPolicy`/`capabilities`, `fds_source_systems`) | `fds:admin:source-system` | **필수** |
| GET | `/api/v1/admin/fds/connectors` | connector health 목록(`fds_connector_offsets`) | `fds:admin:source-system` | — |
| GET | `/api/v1/admin/fds/connectors/{connectorId}` | connector 단건 health·offset·lag·last_error 조회(`fds_connector_offsets`) | `fds:admin:source-system` | — |
| POST | `/api/v1/admin/fds/connectors/{connectorId}/pause` | connector 일시중지(`connector_status`→`DISABLED`, ingest/poll suspend) | `fds:admin:source-system` | — |
| POST | `/api/v1/admin/fds/connectors/{connectorId}/resume` | connector 재개(`connector_status`→`HEALTHY`, offset 유지 후 소비 재개) | `fds:admin:source-system` | — |
| POST | `/api/v1/admin/fds/connectors/{connectorId}/replay` | replay/reconciliation 트리거 | `fds:admin:source-system` | — |
| GET | `/api/v1/admin/fds/notify-channels` | tenant 알림 채널 목록(설계서 §13.2 alert channel — `channel`(`SLACK`/`EMAIL`/`WEBHOOK`)·`target`(채널명/주소/URL)·`events`(구독 이벤트, §9.1 webhook eventName 부분집합)). DTO §5.22, `fds_notify_channels`(DB §5.34) | `fds:admin:source-system` | — |
| PUT | `/api/v1/admin/fds/notify-channels` | tenant 알림 채널 설정 변경(전체 교체, 멱등). `SFDS_TENANT:ADMIN` 전용·감사 기록(`NOTIFY_CHANNEL_CHANGE`, PRD TNT-002 ⑤ BR-001). webhook URL 변경은 credential 서명키 정책(rotate) 연계(헤더 `X-Webhook-Url-Changed`). DTO §5.22 | `fds:admin:source-system` | — |
| GET | `/api/v1/admin/fds/credentials` | API credential 목록(secret 미노출) | `fds:admin:credential` | — |
| POST | `/api/v1/admin/fds/credentials` | credential 생성(secret 1회 반환) | `fds:admin:credential` | **필수(SECURITY_ADMIN)** |
| POST | `/api/v1/admin/fds/credentials/{credentialId}/rotate` | secret/webhook 회전 | `fds:admin:credential` | **필수(SECURITY_ADMIN)** |

### 4.9 Approval API (위임) — bo-api IAM 연계
| 메서드 | 경로 | 설명 | scope | 4-eyes |
|---|---|---|---|---|
| GET | `/api/v1/admin/fds/approvals` | 결재 대기 목록(`fds_approval_requests`). 필터: `subjectKind`(enum subject_kind 9종), `status`(enum approval_status 8종), `maker`(상신자 token=`maker_subject`) + 페이지네이션(§3.2) | `fds:case:read` | — |
| GET | `/api/v1/admin/fds/approvals/{approvalRequestId}` | 결재 단건(payload_hash 포함) | `fds:case:read` | — |
| POST | `/api/v1/admin/fds/approvals/{approvalRequestId}/approve` | 승인(checker≠maker 강제) | `fds:action:write` | maker≠checker |
| POST | `/api/v1/admin/fds/approvals/{approvalRequestId}/reject` | 반려 | `fds:action:write` | — |

> 상신자(maker)와 승인자(checker)는 같을 수 없다(`SELF_APPROVAL_DISABLED`). AI agent는 maker만 가능. 운영자 IAM·승인 라인 정책은 bo-api 소유, fds-svc는 엔진 측 게이트(`fds_approval_requests`/`fds_approval_steps`)만 보유.

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
| eventId | string(160) | ● | 원천 unique | `event_id` |
| eventType | string(100) | ● | `<family>.<verb>` | `event_type` |
| occurredAt | datetime | ● | ≤ now+5m | `occurred_at` |
| schemaVersion | string(80) | ● | 등록된 mapping 존재 | `schema_version` |
| subject | SubjectDto | 조건부 | 고객 거래 필수 | `subject_ref`… |
| actor | ActorDto | 조건부 | 내부감사·직원작업 필수 | `actor_ref` |
| transaction | TransactionDto | 조건부 | 거래 이벤트 필수 | `transaction_ref`… |
| instrument | InstrumentDto | 권장 | 수단 룰 필요 | `instrument_ref`… |
| counterparty | CounterpartyDto | △ | | `counterparty_ref` |
| channel | ChannelDto | ● | `channelType` 필수 | `channel_type`,`payment_rail` |
| location | LocationDto | △ | | (canonical_payload) |
| payloadHash | string(128) | △ | `sha256:...` | `payload_hash` |

> `Tenant-Id`/`Workspace-Id`/`Source-System`/`Idempotency-Key`는 헤더로 전달(body 미포함). **rawPayload·PAN·주민번호 포함 시 ingest reject 또는 tokenization 후 폐기**(§16.1).

SubjectDto: `subjectType`(enum subject_type ●), `subjectRef`(string token ●), `country`(string(8)), `kycLevel`, `riskRating`.
TransactionDto: `transactionRef`(string ●), `transactionType`(enum `TransactionType` ●, **DB §4.19 폐쇄 12종 정본** — `WITHDRAWAL`/`DEPOSIT`/`TRANSFER`/`REMITTANCE`/`PAYMENT`/`REFUND`/`REVERSAL`/`CHARGE`/`SETTLEMENT`/`PAYOUT`/`EXCHANGE`/`ADJUSTMENT`, 자유 문자열 금지, §10 `TransactionType` schema), `direction`(enum `INBOUND`/`OUTBOUND`), `amount`(decimal(24,8), ≥0), `currency`(string(12)), `amountBase`(decimal(24,8) — **base 통화 USD**; cross-border는 remit `usd_amount`/`report_amount`에서 산출, DB §5.5), `baseCurrency`(cross-border 기본 `USD`), `corridor`(CorridorDto △, cross-border 송금 시), `status`.
CorridorDto(△, cross-border `CROSS_BORDER_REMIT`/`INBOUND_REMIT` 시): `sendCountry`(string(2), `send_country`), `receiveCountry`(string(2), `receive_country`), `sendCurrency`(string(12), `send_currency`), `receiveCurrency`(string(12), `receive_currency`) — hanpass-ph `remit-svc`/`inbound-svc` corridor 매핑, DB §5.5. 미탑재 시 `canonical_payload.corridor`로 표기.
InstrumentDto: `instrumentType`(enum instrument_type ●), `instrumentRef`(string token ●), `accountRef`, `institutionCode`, `country`.
ChannelDto: `channelType`(enum channel_type ● **21종** — `CASH_IN`(월렛충전)·`INBOUND_REMIT`(파트너 인바운드) 포함, DB §4.4), `paymentRail`(enum payment_rail), `entryMode`.

### 5.2 IngestEventResponse (202 신규 수신 / 200·201 멱등 재반환)
`POST /fds/events`는 **비동기 큐 적재**다(§4.1). 신규 수신 성공 = **202 Accepted**(`status=ACCEPTED`, 큐 적재 완료·정규화/평가는 후속). 멱등 재요청(동일 `Idempotency-Key`+동일 payload)은 저장된 결과를 **200/201**로 재반환(`Idempotency-Replayed: true`, §3.3). 중복 event(`event_id` 충돌)는 `status=DUPLICATE`, reject는 `status=REJECTED`(422 계열, §6).
| 필드 | 타입 | 설명 |
|---|---|---|
| eventId | string | 수신 event id |
| status | enum | `ACCEPTED`(202 신규 큐 적재)/`DUPLICATE`/`REJECTED` |
| idempotencyReplayed | boolean | 멱등 재반환 여부(true 시 200/201) |

### 5.3 EvaluateDecisionRequest (POST /fds/decisions/evaluate)
- body는 `IngestEventRequest`와 동일 구조(동기 평가). 차이: 응답에 즉시 decision 포함, `fds_decisions`+`fds_decision_reasons` 동기 생성.

### 5.4 DecisionResponse — `fds_decisions` (설계서 §12.8 응답 예시 정합)
| 필드 | 타입 | 매핑 |
|---|---|---|
| decisionId | uuid | `decision_id` |
| decision | enum decision (8종) | `decision` |
| reasonCodes | string[] | `fds_decision_reasons.reason_code` |
| riskScore | decimal(8,4) (0~100) | `risk_score` (산출 정책 = 소프트웨어 §11.1.1: outcome severity 단조 매핑; 응답은 JSON `number`, webhook은 `"82.0000"` 문자열 — §9·integration §4.5) |
| recommendedActions | enum action_type[] | emit된 `fds_actions.action_type` 투영(capability/4-eyes 게이트·downgrade 반영, integration §142) — 단일 컬럼 1:1 매핑 아님 |
| matchedRules | RuleRef[] (`ruleId`,`versionNo`) | `matched_rules` |
| ruleSetVersion | string(80) | `rule_set_version` |
| expiresAt | datetime | `expires_at` |
| createdAt | datetime | `created_at` |

> `feature_snapshot`/`input_event_hash`는 증적용이며 기본 응답에서 요약/마스킹. Evidence API에서 전체 제공.

### 5.5 CaseDto — `fds_cases`
| 필드 | 타입 | 매핑 |
|---|---|---|
| caseId | uuid | `case_id` |
| caseType | enum case_type (11종) | `case_type` |
| subjectRef / transactionRef | string(token) | 동일 |
| originDecisionId | uuid | `origin_decision_id` |
| status | enum case_status | `status` |
| priority | enum case_priority | `priority` |
| assignedTo | string(운영자 token) | `assigned_to` |
| closeReason | string(64) | `close_reason` (DB VARCHAR(64) §5.13). **enum 8종** `FP_THRESHOLD`/`FP_NORMAL_PATTERN`/`FP_DATA_QUALITY`/`CONFIRMED_FRAUD`/`CONFIRMED_MULE`/`CONFIRMED_ATO`/`ESCALATED_AML`/`OTHER`(DB §4.11·설계서 §11.6.1a). `POST .../close` 요청 시 필수, 상세 메모(자유 텍스트)는 case event(`CLOSED` payload) 보조 저장으로 분리 |
| amlCaseRef | string | aml-svc cross-ref(`fds_cases.aml_case_id`, integration 확정) |
| createdBy / updatedBy | string(128, nullable) | `created_by` / `updated_by` (DB §5.13) |
| createdAt / updatedAt | datetime | 동일 |

### 5.6 CasePatchRequest (PATCH /fds/cases/{caseId})
`status`(enum case_status), `priority`(enum case_priority), `assignedTo`(string), `reason`(string, 선택 — 단 종결 상태→`status=IN_REVIEW` 재오픈 시 **필수**, 감사 기록용, PRD §11.2 BR-006) — status/priority/assignedTo 중 1개 이상 필수. 내부감사 case 종결은 결재 게이트.

### 5.7 CaseActionRequest (POST /fds/cases/{caseId}/actions) — `fds_actions`
| 필드 | 타입 | 필수 | 매핑 |
|---|---|---|---|
| actionType | enum action_type (23종) | ● | `action_type` |
| targetSystem | string(64) | △ | `target_system` |
| targetRef | string(token) | △ | `target_ref` |
| reason | string | ● | (감사) |

응답 ActionResponse: `actionId`(uuid), `actionType`(enum action_type 23종, 필수 — `fds_actions.action_type` DB §5.12 매핑), `status`(enum action_status), `approvalRequestId`(uuid, null 가능), `idempotencyKey`. `GET /fds/actions/{actionId}` 응답도 동일 스키마(§10 `ActionResponse`).

### 5.8 RuleDto / RuleUpsertRequest — `fds_rules`
| 필드 | 타입 | 필수 | 매핑 |
|---|---|---|---|
| ruleId | uuid | (응답) | `rule_id` |
| ruleSetId | string(80) | ● | `rule_set_id` |
| name | string(160) | ● | `name` |
| channelScope | enum channel_type | △ | `channel_scope` |
| dslSource | string | △ | `dsl_source`(no-code 표현) |
| ruleJson | object | ● | `rule_json` |
| decisionOutcome | enum decision | △ | `decision_outcome` |
| status | enum rule_status | (응답) | `status` |
| createdBy / updatedBy | string(128, nullable) | (응답) | `created_by` / `updated_by` (DB §5.17) |
| createdAt / updatedAt | datetime | (응답) | `created_at` / `updated_at` (DB §5.17) |

### 5.9 RuleSimulationRequest / Response — `fds_rule_simulations`
요청: `ruleId`(uuid, △) 또는 `ruleJson`(object ●), `sampleWindow`({`from`,`to`} object).
응답: `simulationId`(uuid), `estimatedHitRate`(decimal(8,4)), `resultSummary`(object), `createdAt`(datetime, DB §5.19 `created_at`), `createdBy`(string(128), nullable, DB §5.19 `created_by`).

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

### 5.10 RiskGroupMemberRequest — `fds_risk_group_members`
`memberRef`(string token ●), `memberKind`(enum `SUBJECT`/`INSTRUMENT`/`COUNTERPARTY` ●), `expiresAt`(datetime △).

### 5.11 EvidenceExportRequest — `fds_evidence_exports`
| 필드 | 타입 | 필수 | 매핑 |
|---|---|---|---|
| exportKind | enum `DECISION_TIMELINE`/`CASE_TIMELINE`/`DECISION_REPORT`/`CONNECTOR_RECON`/`FALSE_POSITIVE`/`PII_ACCESS` | ● | `export_kind` |
| exportFormat | enum export_format(`CSV`/`EXCEL`/`PDF`/`JSON_API`) | ● | `export_format` |
| queryParams | object(`from`,`to`,…) | △ | `query_params` |

응답: `exportId`(uuid), `status`(enum export_status), `manifestHash`(string, READY 시), `approvalRequestId`(uuid, nullable — 결재 대상 export이면 반환·비대상이면 null, DB §5.31 `approval_request_id`), `createdBy`(string(128) — 요청 주체, DB §5.31 `created_by NOT NULL` 정본).

### 5.12 ApprovalRequestDto / ApprovalDecisionRequest — `fds_approval_requests`/`fds_approval_steps`
ApprovalRequestDto: `approvalRequestId`(uuid), `subjectKind`(enum subject_kind 9종 `ACTION`/`RULE`/`MAPPING`/`SECRET`/`GROUP`/`EXPORT`/`MERCHANT_NORMALIZE`/`CASE_CLOSE`/`POLICY_PACK` = OpenAPI `SubjectKind`), `subjectRef`, `approvalLine`(enum approval_line 6종 = OpenAPI `ApprovalLine`, DB §4.12 `SELF_APPROVAL_DISABLED`/`MAKER_CHECKER`/`COMPLIANCE_MANAGER`/`RISK_MANAGER`/`SECURITY_ADMIN`/`EXECUTIVE_APPROVAL`), `status`(enum approval_status 8종 = OpenAPI `ApprovalStatus`, DB §4.12 `DRAFT`/`SUBMITTED`/`APPROVED`/`REJECTED`/`CANCELLED`/`EXPIRED`/`EXECUTED`/`EXECUTION_FAILED`), `payloadHash`, `makerSubject`, `reason`(string △, 상신 사유 = DB `fds_approval_requests.reason TEXT` §5.23, NULL 허용), `expiresAt`, `maxExecutions`.

> `subjectKind` enum은 DB 정본 `fds_approval_requests.subject_kind` 9종(§5.23)과 1:1. `CASE_CLOSE`=case 종결 4-eyes(대상=`fds_cases.case_id`, §8 case close 행), `POLICY_PACK`=규제 팩 토글 변경 4-eyes(대상=`fds_tenants.tenant_id`, 설계서 §16.2).
ApprovalDecisionRequest(approve/reject): `comment`(string △). checker는 토큰 주체에서 추출(maker≠checker 강제).

### 5.13 CredentialDto / CredentialCreateRequest — `fds_api_credentials`
요청: `credentialType`(enum `API_KEY`/`OAUTH2_CLIENT`/`MTLS`/`WEBHOOK` ●), `scopes`(string[] ●), `ipAllowlist`(string[] △), `webhookUrl`(string △).
응답(생성 1회만): `credentialId`, `secret`(평문 1회 반환 후 미보존 — 이후 `secret_hash`만), `scopes`. 조회 응답에는 secret 미노출.

**CredentialDto (GET /admin/fds/credentials 조회 응답)** — `fds_api_credentials` (DB §5.29). secret 필드 미포함.
| 필드 | 타입 | 매핑 |
|---|---|---|
| credentialId | string(96) | `credential_id` |
| credentialType | enum `API_KEY`/`OAUTH2_CLIENT`/`MTLS`/`WEBHOOK` | `credential_type` |
| scopes | string[] | `scopes` (JSONB) |
| ipAllowlist | string[] (nullable) | `ip_allowlist` (JSONB) |
| webhookUrl | string (nullable) | `webhook_url` |
| enabled | boolean | `enabled` |
| createdAt | datetime | `created_at` |
| updatedAt | datetime | `updated_at` |

> `secret` / `secret_hash`는 조회 응답 미노출(원문 및 hash 모두). 생성 시 1회만 `secret` 반환.

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
- `capabilities`는 `control_capability` 9종(`CAN_BLOCK_BEFORE_AUTH`/`CAN_DECLINE_AUTH`/`CAN_HOLD_FUNDS`/`CAN_EXTEND_HOLD`/`CAN_RELEASE_HOLD`/`CAN_CANCEL_BEFORE_SETTLEMENT`/`CAN_REQUEST_REVERSAL`/`CAN_SUSPEND_INSTRUMENT`/`CAN_OPEN_CASE_ONLY`)의 부분집합. action router는 이 매트릭스로 발행 가능 action을 게이트한다(§5.3 Action capability).
- 응답 SourceSystemDto: `sourceSystem`, `displayName`, `ingestMode`, `schemaVersion`, `enabled`, `failPolicy`, `capabilities[]`, `updatedAt`. 미승인 상신 시 `approvalRequestId`(uuid) + `status=APPROVAL_REQUIRED`(409 `FDS-APPROVAL-REQUIRED` 또는 상신 수락 본문) 반환, 승인 후 반영.

### 5.18 RiskGroupUpsertRequest (PUT /admin/fds/risk-groups/{groupId}) — `fds_risk_groups` (§5.21)

위험그룹 마스터(틀) 수정/비활성. **4-eyes 대상**(`subjectKind=GROUP`, subjectRef=`group_id`, §8) — 즉시 반영되지 않고 `fds_approval_requests` 생성 후 승인 relay. **DB `fds_risk_groups` 컬럼에 정합하는 필드만 수정 가능**(아래 표). PRD SFDS-GRP-003 화면의 `source`/`autoEnrollOnHit`/`defaultExpiryDays`/`description`은 `fds_risk_groups` 컬럼 부재로 본 마스터 PUT의 영속 대상이 아니다(룰 빌더·멤버 정책에서 관리, 추측 컬럼 미생성).

| 필드 | 타입 | 필수 | 검증 | 매핑 |
|---|---|---|---|---|
| displayName | string(160) | △ | 비공백, ≤160 | `display_name` |
| active | boolean | △ | 비활성(`false`) 시 멤버 0 선결(BR-001) | (상태 전이, §5.18 주) |
| groupType | enum risk_group_type (DB §4.14 6종) | △(에코) | **변경 불가** — 저장값과 상이 시 거부(BR-002) | `group_type`(read-only) |

- `{groupId}`=`group_id`(PK `(tenant_id, workspace_id, group_id)`). 최소 1개 수정 필드(`displayName`·`active`) 필수 — 둘 다 없으면 `FDS-VALIDATION-001`.
- **`group_id`(=groupCode)·`group_type`(=kind) immutable**(BR-001/BR-002). path `groupId`는 식별자이며 변경 불가. body에 `groupType`을 포함할 경우 저장값과 동일해야 하며, 상이하면 `FDS-VALIDATION-002`(enum/immutable 위반)로 거부.
- **비활성(`active=false`)**: `fds_risk_groups`에 전용 `enabled` 컬럼이 없으므로 비활성은 **멤버 전건(`fds_risk_group_members`) 0 선결** 후 그룹 정의 해제(틀 비활성)로 처리한다. 멤버가 남아 있으면 `FDS-STATE-CONFLICT`(409, 멤버 잔존). watchlist/denylist 평가 반영(룰 매칭 대상 제외)은 승인 relay 시점에 적용. `updated_by`/`updated_at` 갱신으로 변경 이력 표면화(감사 7년 보존, PRD BR-005).
- `groupType` 변경이 필요하면 새 그룹을 생성한다(멤버 식별자 체계 상이, BR-002).

### 5.19 RiskGroupDto (응답) — `fds_risk_groups` (§5.21)

위험그룹 마스터 단건. raw PII 없음(`group_id`/`display_name`은 운영 식별자, 멤버 token은 미포함).

| 필드 | 타입 | 매핑 |
|---|---|---|
| groupId | string(96) | `group_id` |
| groupType | enum risk_group_type (DB §4.14 6종) | `group_type` |
| displayName | string(160) | `display_name` |
| memberCount | integer | (`fds_risk_group_members` count, 비활성 선결 판정용) |
| createdBy / updatedBy | string(128, 운영자 token) | `created_by` / `updated_by` |
| createdAt / updatedAt | datetime | `created_at` / `updated_at` |
| approvalRequestId | uuid (nullable) | 미승인 상신 시 결재 id |
| status | string (nullable) | `APPROVAL_REQUIRED` 등 결재 게이트 상태 |

> 미승인 상신 시 `approvalRequestId` + `status=APPROVAL_REQUIRED` 반환, 승인 후 `display_name`/비활성 반영. `group_id`·`group_type`은 응답에 노출되나 read-only.

### 5.20 MerchantNormalizeRequest (POST /admin/fds/merchants/{merchantRef}/normalize) — 4-eyes 상신

high-risk merchant 정상화(차단/제약 해제) 상신. **4-eyes 대상**(`subjectKind=MERCHANT_NORMALIZE`, subjectRef=`merchant_ref`, §8) — 즉시 실행되지 않고 `fds_approval_requests` 생성 후 승인 relay. `merchant_ref`는 token(원문 PII 아님). 정상화는 설계서 §11.5 SUSPEND_INSTRUMENT(대상=MERCHANT_ACCOUNT) 등 제약 액션의 해제 환원에 해당한다.

| 필드 | 타입 | 필수 | 매핑 |
|---|---|---|---|
| reason | string | ● | (감사·결재 사유, `fds_approval_requests.reason`) |
| scope | enum `SINGLE`/`BULK` | △ | 대규모(`BULK`) 시 `approvalLine=EXECUTIVE_APPROVAL`(설계서 §11.5) |

> 응답: `approvalRequestId`(uuid) + `status=APPROVAL_REQUIRED`(409 `FDS-APPROVAL-REQUIRED` 또는 상신 수락 본문). `approvalLine`은 bo-api 승인 라인 정책 소유 — 기본 `RISK_MANAGER`, 대규모(`BULK`)는 `EXECUTIVE_APPROVAL`.

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
| target | string(512) | `target` | 채널명/주소/URL. WEBHOOK은 `http(s)` URL 강제 |
| events | enum[] (§9.1 webhook eventName 4종 부분집합) | `events`(CSV) | null/빈 배열 허용. 미지원 값 400 `FDS-VALIDATION-001` |

> 멱등: `(channel, target)` 자연키 기준 전체교체 — 동일 payload 재PUT 시 동일 최종 상태·중복 감사 없음. 변경 시 `fds_audit_logs`(`audit_action=NOTIFY_CHANNEL_CHANGE`) 1건. webhook target URL 변경 시 응답 헤더 `X-Webhook-Url-Changed: true` + 감사 detail `rotateRequired=true`(서명키 rotate 정책 §13.2 BR-003 연계 신호 — 실제 rotate 상신/실행은 credential admin 4-eyes 경로). 엔진 scope `fds:admin:source-system`만 강제, 운영자 역할(`SFDS_TENANT:ADMIN`) 게이트는 bo-api 소유(후속 T16).

---

## 6. 에러 코드

| 코드 | HTTP | 의미 | 발생 API |
|---|---|---|---|
| `FDS-VALIDATION-001` | 400 | 요청 필드 검증 실패 | 전체 |
| `FDS-VALIDATION-002` | 400 | enum 코드값 불일치 또는 immutable 위반(decision/action/case/channel/connector_status/control_capability/ingest_mode/risk_group_type·`group_type` 변경…) | 전체 |
| `FDS-PII-REJECTED` | 422 | raw PII(PAN/주민번호) 포함 payload reject | Ingest/Decision |
| `FDS-SCHEMA-UNKNOWN` | 422 | 등록되지 않은 `source_system`/`schema_version` | Ingest/Decision |
| `FDS-AUTH-001` | 401 | 인증 실패(API key/HMAC/토큰) | 전체 |
| `FDS-AUTH-002` | 401 | HMAC 서명 불일치 | HMAC API |
| `FDS-AUTHZ-001` | 403 | 권한 부족 | 전체 |
| `FDS-AUTHZ-002` | 403 | scope 불일치 | 전체 |
| `FDS-AUTHZ-003` | 403 | cross-workspace 접근 차단 | 전체 |
| `FDS-DATASCOPE-DENIED` | 403 | data-scope 밖 row 접근 | 조회/조치 |
| `FDS-NOT-FOUND` | 404 | 리소스 없음(격리 밖 포함) | 전체 |
| `FDS-IDEMPOTENT-CONFLICT` | 409 | 동일 key 다른 payload | 멱등 API |
| `FDS-STATE-CONFLICT` | 409 | 상태 전이 위반(예: 이미 CLOSED case, connector `ERROR` 강제 resume, 멤버 잔존 그룹 비활성) | Case/Action/Approval/Connector/Group |
| `FDS-APPROVAL-REQUIRED` | 409 | 결재 없이 실행 시도 | Action/Rule/Group/Credential/SourceSystem/MerchantNormalize |
| `FDS-APPROVAL-SELF` | 409 | maker=checker 승인 시도 | Approval |
| `FDS-APPROVAL-PAYLOAD-CHANGED` | 409 | 승인 후 payload_hash 변경 | Approval/실행 |
| `FDS-AML-DELEGATED` | 409 | AML/Travel Rule 본 처리는 aml-svc 위임 대상 | Case |
| `FDS-FAIL-CLOSED` | 503 | 평가 불가 + fail-closed 정책 | Decision |
| `FDS-RATE-LIMIT` | 429 | rate limit 초과 | 전체 |

---

## 7. reason code / decision code 사전

### 7.1 decision code (응답 `decision`, DB enum decision §4.7)
`ALLOW` · `MONITOR` · `REVIEW` · `CHALLENGE` · `BLOCK` · `HOLD` · `FREEZE` · `REPORT`

### 7.2 reasonCodes 예시 (`fds_decision_reasons.reason_code`)
`NEW_BENEFICIARY` · `TRANSFER_VELOCITY` · `MULE_ACCOUNT_GROUP` · `GEO_MISMATCH` · `NEW_INSTRUMENT` · `HIGH_RISK_MERCHANT` · `CRYPTO_ADDRESS_RISK` · `TRAVEL_RULE_MISSING` · `SANCTION_HIT` · `STRUCTURING` · `INVOICE_PRICE_DEVIATION` · `DOCUMENT_MISMATCH` · `SELLER_PAYOUT_ANOMALY` · `APPROVER_ROLE_MISMATCH` · `EMPLOYEE_OVERRIDE_VELOCITY` (tenant별 확장 가능, free-form 허용하되 catalog 권장).

> recommendedActions는 enum action_type(23종) 코드값으로만 반환.

---

## 8. 4-eyes 결재 대상 엔드포인트

설계서 §11.4/§11.5 기준. 아래 호출은 즉시 실행되지 않고 `fds_approval_requests` 생성 → `status=APPROVAL_REQUIRED`/`SUBMITTED` → checker 승인 후 relay/실행.

| 엔드포인트 | subjectKind | 기본 approval_line |
|---|---|---|
| `POST /fds/cases/{caseId}/actions` (자금/규제 action) | `ACTION` | `MAKER_CHECKER` / `EXECUTIVE_APPROVAL`(대규모) |
| `POST /fds/cases/{caseId}/close` (내부감사·규제 case) | `CASE_CLOSE` (subjectRef=`case_id`) | `COMPLIANCE_MANAGER` |
| `POST /admin/fds/rules/{ruleId}/activate` · `/rollback` | `RULE` | `COMPLIANCE_MANAGER` |
| `PUT /admin/fds/source-systems/{ss}/mappings` | `MAPPING` | `MAKER_CHECKER` |
| `PUT /admin/fds/source-systems/{id}` (속성·capability 매트릭스 수정) | `MAPPING` (source-system 구성 도메인, subjectRef=`source_system`) | `MAKER_CHECKER` |
| `PUT /admin/fds/risk-groups/{groupId}` (마스터 수정/비활성) | `GROUP` (subjectRef=`group_id`) | `RISK_MANAGER` |
| `POST` · `DELETE /admin/fds/risk-groups/{groupId}/members` | `GROUP` | `RISK_MANAGER` |
| `POST /admin/fds/credentials` · `/rotate` | `SECRET` | `SECURITY_ADMIN` |
| `POST /evidence/fds/exports` (제출용 최종본) | `EXPORT` | `COMPLIANCE_MANAGER` |
| `POST /admin/fds/merchants/{merchantRef}/normalize` (high-risk merchant 정상화) | `MERCHANT_NORMALIZE` (subjectRef=`merchant_ref`) | `RISK_MANAGER`(기본) / `EXECUTIVE_APPROVAL`(대규모 예외) |
| `PUT /api/v1/bo/fds/tenants/{tenantId}` (규제 팩 `compliance_policy` 토글 변경) | `POLICY_PACK` (subjectRef=`tenant_id`, 설계서 §16.2) | `COMPLIANCE_MANAGER` |

규칙: payload는 `payload_hash`로 고정, 승인 후 변경 시 무효(`FDS-APPROVAL-PAYLOAD-CHANGED`). 승인↔실행 분리 저장(`fds_approval_steps` vs action relay). 운영자 IAM·승인 라인 정책은 bo-api 소유.

---

## 9. Webhook 콜백 계약 (outbound)

설계서 §12.8 'Webhook API'를 정본으로 확정한다. fds-svc는 decision/case/action 이벤트를 서비스 등록 URL로 **outbound HTTP POST** 발행한다(`fds_api_credentials.credential_type=WEBHOOK`, `webhook_url`/`secret_hash` 사용, `/admin/fds/credentials/{id}/rotate`로 회전). bo-web/bo-api 운영자 화면과 무관한 **서비스 서버 간 콜백** 채널이다.

> **전송 어댑터 구현 확정(T10)**: 전송은 `fds_webhook_outbox`(DB §5.35, transactional outbox) + 스케줄드 디스패처(`WebhookRelayScheduler`/`WebhookRelayService`/`HttpWebhookSenderAdapter`, 연동 §6.2.2)로 실현된다 — 도메인 변경 트랜잭션 내 enqueue → `SELECT … FOR UPDATE SKIP LOCKED` 클레임 → 서명 POST → 2xx `DISPATCHED` / 비2xx·타임아웃 `FAILED`+지수 backoff(MAX 5) → `DEAD_LETTERED`(DLQ + `WEBHOOK_DEAD_LETTER` 감사). `sandbox`는 미발행(shadow). 서명 material(`timestamp + "." + rawBody`)은 **인바운드 ingest 필터 material(`timestamp + "\n" + apiKey + "\n" + body`)과 분리**되며 fds/aml 양 엔진 아웃바운드가 동일하다(AML §8.3).

### 9.1 이벤트 타입 (`eventName`)
| eventName | 트리거 | 발행 주체(엔진) | 핵심 payload |
|---|---|---|---|
| `FdsDecisionCreated` | decision 생성 | Decision Engine | `decisionId`,`decision`,`reasonCodes`,`riskScore`,`recommendedActions`(action_type[]) |
| `FdsCaseOpened` | case origin 생성 | Case Mgmt | `caseId`,`caseType`,`priority`,`originDecisionId` |
| `FdsCaseStatusChanged` | case 상태 전이 | Case Mgmt | `caseId`,`fromStatus`,`toStatus`,`closeReason`(nullable) |
| `FdsActionResult` | action relay 결과(SENT→ACKED/FAILED 전이) | Action relay | `actionId`,`actionType`(action_type 23종, 필수),`status`(enum action_status: §10 OpenAPI `ActionStatus` 7종 / DB §4.9, 통상 `ACKED`/`FAILED`),`errorCode`(nullable) |

> 4종은 정본 콜백 집합. enum 코드값은 DB §4와 동일(action_type 23종·case_type·action_status·case_status). raw PII 미포함(token/hash·마스킹만).

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
- secret은 credential WEBHOOK의 `secret_hash` 대조 원본(평문 1회 발급, 회전 시 무중단 위해 dual-secret 검증 기간 허용).

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
  schemas:
    Decision:
      type: string
      enum: [ALLOW, MONITOR, REVIEW, CHALLENGE, BLOCK, HOLD, FREEZE, REPORT]
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
        SUSPEND_EMPLOYEE_SESSION, REQUEST_TRAVEL_RULE_INFO, OPEN_AML_CASE, REGULATORY_REPORT]
    CaseType:
      type: string
      enum: [FRAUD_REVIEW, AML_REVIEW, CHARGEBACK_REVIEW, MULE_ACCOUNT_REVIEW,
        CRYPTO_TRAVEL_RULE, INTERNAL_AUDIT, MERCHANT_RISK, REGULATORY_REPORT,
        TRADE_FINANCE_REVIEW, ECOMMERCE_SETTLEMENT_REVIEW, B2B_INVOICE_REVIEW]
    SubjectKind:
      type: string
      enum: [ACTION, RULE, MAPPING, SECRET, GROUP, EXPORT, MERCHANT_NORMALIZE, CASE_CLOSE, POLICY_PACK]
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
      enum: [BLACKLIST, WHITELIST, WATCHLIST, MULE_NETWORK, ALLOWLIST, DENYLIST]
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
        institutionRef: { type: string, maxLength: 64, nullable: true, description: 상위 기관(institution) 참조 (fds_tenants.institution_ref). 1 기관 : N 서비스(테넌트). additive·nullable }
        deploymentModel: { $ref: '#/components/schemas/DeploymentModel' }
        onboardingStatus: { $ref: '#/components/schemas/OnboardingStatus' }
        region: { type: string, maxLength: 32, description: fds_tenants.default_region (기본 KR) }
        infraRef: { type: string, maxLength: 160, nullable: true, description: fds_tenants.infra_ref (매니지드 IaC 스택 ref / self-hosted 인스턴스·라이선스 ref) }
    RiskGroupUpsertRequest:
      type: object
      minProperties: 1
      description: displayName 또는 active 중 1개 이상 필수. group_id·group_type 변경 불가.
      properties:
        displayName: { type: string, maxLength: 160 }
        active: { type: boolean, description: false=비활성(멤버 0 선결, BR-001) }
        groupType:
          allOf: [ { $ref: '#/components/schemas/RiskGroupType' } ]
          description: 에코 전용 read-only. 저장값과 상이 시 거부(immutable, BR-002)
    RiskGroupDto:
      type: object
      required: [groupId, groupType, displayName]
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
      properties:
        ruleId: { type: string, format: uuid }
        versionNo: { type: integer }
    DecisionResponse:
      type: object
      properties:
        decisionId: { type: string, format: uuid }
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
        expiresAt: { type: string, format: date-time }
        createdAt: { type: string, format: date-time }
paths:
  /fds/decisions/evaluate:
    post:
      summary: 승인 전 실시간 FDS 판단
      security: [ { ApiKeyHmac: [] }, { OAuth2: [fds:decision:evaluate] } ]
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
      security: [ { OAuth2: [fds:case:update] } ]
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
      security: [ { OAuth2: [fds:case:read] } ]
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
      security: [ { OAuth2: [fds:admin:rule] } ]
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
          description: enum channel_type(DB §4.4 21종 — `CASH_IN`·`INBOUND_REMIT` 포함, hanpass-ph 재그라운딩)
          schema: { type: string, maxLength: 64 }
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
        '200': { description: rule 페이지(content[]=RuleDto §5.8, §3.2 envelope) }
        '403': { description: 권한/scope/data-scope 거부, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
  /admin/fds/connectors/{connectorId}:
    get:
      summary: connector 단건 health 조회
      security: [ { OAuth2: [fds:admin:source-system] } ]
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
      security: [ { OAuth2: [fds:admin:source-system] } ]
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
      security: [ { OAuth2: [fds:admin:source-system] } ]
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
        '409': { description: 상태 전이 위반(예: ERROR 강제 resume), content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
  /admin/fds/source-systems/{id}:
    put:
      summary: source system 속성·capability 매트릭스 수정(4-eyes)
      security: [ { OAuth2: [fds:admin:source-system] } ]
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
  /admin/fds/risk-groups/{groupId}:
    put:
      summary: 위험그룹 마스터 수정/비활성(4-eyes)
      security: [ { OAuth2: [fds:admin:group] } ]
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
            schema: { $ref: '#/components/schemas/RiskGroupUpsertRequest' }
      responses:
        '200':
          description: 변경 반영(또는 결재 상신 수락) 결과
          content:
            application/json:
              schema: { $ref: '#/components/schemas/RiskGroupDto' }
        '400': { description: 검증 실패(빈 본문/immutable 위반), content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
        '403': { description: 권한/scope/data-scope 거부, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
        '404': { description: 미존재/격리 밖, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
        '409': { description: 결재 필요(FDS-APPROVAL-REQUIRED) 또는 멤버 잔존 비활성(FDS-STATE-CONFLICT), content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
  /admin/fds/merchants/{merchantRef}/normalize:
    post:
      summary: high-risk merchant 정상화 상신(4-eyes)
      security: [ { OAuth2: [fds:admin:group] } ]
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
      security: [ { OAuth2: [fds:case:read] } ]
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
      security: [ { OAuth2: [fds:action:write] } ]
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
      security: [ { OAuth2: [fds:action:write] } ]
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
| 감사 로그 조회 | `GET /api/v1/bo/fds/audit?subjectKind&actor&from&to` | bo-api 감사 집약(+ fds-svc `fds_audit_logs` 저수준 조회) |

> 위 `bo-api 소유` 경로(`/api/v1/bo/**`)는 bo-api API 명세에서 확정한다. PRD/PPT의 대시보드·서비스 관리·감사·온보딩 화면은 호출 대상을 **bo-api**로 명시하고, 과거 `GET /api/v1/admin/fds/dashboard|tenants|audit` 표기(엔진 직접 경로)는 폐기한다.
>
> **서비스 등록 = 배포 유형 선택 + 온보딩 신청/상태(격리 토글 아님, 정본 target-architecture §4.1)**: 서비스(테넌트=서비스) 등록은 '격리 방식(DB 분리/스키마 분리/공유) 라디오' 즉석 선택이 아니라 **배포 유형(`deployment_model`: `MANAGED_DEDICATED`/`SELF_HOSTED`/`SHARED`) 선택 + 온보딩 신청(`onboarding_status` 상태머신)** 흐름이다. 온보딩 프로비저닝 트리거·상태 조회·self-hosted 등록 콜백은 **bo-api 전용 `/onboarding/**`** 경로로만 노출하며, **본 fds-svc 엔진 API(§4)에는 온보딩 엔드포인트를 추가하지 않는다**(DB §9 소유 경계). fds-svc는 `fds_tenants`의 `deployment_model`/`onboarding_status`/`default_region`/`infra_ref`를 스키마로 보유하되 운영 변경은 bo-api 온보딩 워크플로우가 트리거한다. tenant_id 라우팅 의미: 전용 배포(`MANAGED_DEDICATED`/`SELF_HOSTED`)는 **배포=서비스 단일**(라우팅은 배포 엔드포인트 단위, 서비스 간 격리는 배포 경계가 보장), `SHARED`만 `Tenant-Id` 헤더 행 라우팅(integration 명세 확정).

---

## 12. 서비스 경계 주의 (운영자 집계 = bo-api 소유)

- **bo-web → bo-api → fds-svc**. bo-web의 fds-svc·aml-svc 직접호출 금지(정본 §3, §4).
- **운영자 집계 API 소유 경계(정본 결정)**: **대시보드(플랫폼·서비스별)·서비스 관리(목록/상세/등록/설정)·감사 조회는 bo-api가 소유·집약·인증**한다. fds-svc/aml-svc는 **저수준 데이터 API만** 제공한다. 따라서 본 엔진 API 명세(§4)에는 운영자 집계 엔드포인트(대시보드/서비스/감사)를 **추가하지 않는다**. PRD/PPT의 해당 화면은 호출 대상을 bo-api(`/api/v1/bo/**`)로 명시한다(§11.2).
- **AML/STR/CTR/Travel Rule 본 처리**: fds-svc는 후보 action(`OPEN_AML_CASE`/`REGULATORY_REPORT`/`REQUEST_TRAVEL_RULE_INFO`)·origin case만 생성하고, 본 케이스·sanction/PEP·규제보고는 **aml-svc**가 별도 API로 처리. fds 응답은 `amlCaseRef` cross-ref만 노출(integration 명세에서 `fds_cases.aml_case_id` 확정).
- **운영자 IAM·승인 라인 정책**: bo-api 소유. fds-svc는 엔진 측 결재 게이트(`fds_approval_requests`/`fds_approval_steps`)와 엔진 감사(`fds_audit_logs`)만 보유.
- **data-scope**: bo-api가 운영자 토큰 scope를 fds-svc 조회 IN 필터로 주입. fds-svc는 scope 밖 row 접근을 `FDS-DATASCOPE-DENIED`로 차단.

---

## 13. downstream 확정 명칭

integration·tasks·PRD가 그대로 참조할 API 명칭을 확정한다.

- **base path**: `/api/v1`. 외부 `/fds/**`·`/evidence/fds/**`, Admin `/admin/fds/**`.
- **격리 헤더**: `Tenant-Id`(필수), `Workspace-Id`(default `default`/`sandbox` shadow), `Source-System`, `Idempotency-Key`. `dataScope`는 위임 토큰 claim.
- **핵심 엔드포인트**: `POST /fds/events`, `POST /fds/decisions/evaluate`, `GET/PATCH /fds/cases/{caseId}`, `POST /fds/cases/{caseId}/actions`, `POST /evidence/fds/exports`, `POST /admin/fds/rules/simulations`, `POST /admin/fds/rules/{ruleId}/activate`, `POST /admin/fds/approvals/{approvalRequestId}/approve`.
- **OAuth2 scope**: `fds:event:write`/`fds:decision:evaluate`/`fds:case:read`/`fds:case:update`/`fds:evidence:export`/`fds:rule:simulate`/`fds:action:write`/`fds:admin:rule`/`fds:admin:group`/`fds:admin:source-system`/`fds:admin:credential` (전체 11종 `fds:` prefix 형식, §2.3 정본과 동일).
- **에러 코드 prefix**: `FDS-*`(§6). 표준 envelope(RFC7807 + `code`/`traceId`).
- **응답 enum**: decision 8종·**action_type 23종(API `ActionType` enum이 마스터 정본 §1.1)**·case_type 11종은 DB enum 코드값과 동일(§4 DB). `HOLD_TRANSACTION`은 비정본(→`HOLD_FUNDS`/`BLOCK_TRANSACTION`).
- **HTTP 상태코드**: 본 §6이 정본. 중복=400, 결재 누락=409, maker=checker=409, raw PII=422, rate limit=429.
- **DecisionResponse 필수 필드**: `matchedRules`(RuleRef[]: `ruleId`,`versionNo`) 포함(§5.4·§10 OpenAPI, DB `fds_decisions.matched_rules`).
- **Webhook 콜백(outbound)**: `FdsDecisionCreated`·`FdsCaseOpened`·`FdsCaseStatusChanged`·`FdsActionResult` 4종, `X-Signature: hmac-sha256`, `eventId` 멱등, 지수 backoff 재시도(§9).
- **운영자 집계 = bo-api 소유**: 대시보드/서비스/감사 집계 엔드포인트는 bo-api(`/api/v1/bo/**`)가 소유. 엔진 API에 미추가(§1.1·§11.2·§12).
- **배포 모델/온보딩(deployment topology) = bo-api 소유, fds-svc 엔진 API 미추가**: 서비스(테넌트=서비스) 등록은 격리 토글이 아니라 **배포 유형 선택 + 온보딩 신청/상태**다. enum `DeploymentModel{MANAGED_DEDICATED, SELF_HOSTED, SHARED}`(3종) · `OnboardingStatus{REQUESTED, PROVISIONING, DEPLOYED, VERIFIED, ACTIVE, PACKAGE_ISSUED, CUSTOMER_DEPLOYED, REGISTERED}`(8종, §10 OpenAPI)는 DB `fds_tenants.deployment_model`/`onboarding_status` 정본과 1:1. `TenantDto`는 `tenantId`/`deploymentModel`/`onboardingStatus`/`region`(=`default_region`)/`infraRef`(=`infra_ref`) — **`isolationMode` 필드 폐기**. 온보딩 엔드포인트(bo-api 전용): `POST /api/v1/bo/fds/tenants/{tenantId}/onboarding/provision`(프로비저닝 트리거), `GET /api/v1/bo/fds/tenants/{tenantId}/onboarding`(상태 조회), `POST /api/v1/bo/fds/tenants/{tenantId}/onboarding/register`(self-hosted 등록 콜백). 상태머신: 매니지드 `REQUESTED→PROVISIONING→DEPLOYED→VERIFIED→ACTIVE` / self-hosted `REQUESTED→PACKAGE_ISSUED→CUSTOMER_DEPLOYED→REGISTERED` / SHARED `REQUESTED→ACTIVE`(ACTIVE/REGISTERED 도달 시 `tenant_status=ACTIVE`). tenant_id 라우팅: 전용 배포(MANAGED_DEDICATED/SELF_HOSTED)는 배포=서비스 단일(배포 엔드포인트 단위), SHARED만 `Tenant-Id` 헤더 행 라우팅(§11.2·integration).
- **4-eyes 게이트**: action(자금/규제)·rule activate/rollback·mapping·group member·credential·export 최종본·merchant normalize·**case 종결**·**규제 팩 토글** → `fds_approval_requests.subject_kind` **9종**(`ACTION`/`RULE`/`MAPPING`/`SECRET`/`GROUP`/`EXPORT`/`MERCHANT_NORMALIZE`/`CASE_CLOSE`/`POLICY_PACK`) 매핑(§8). **case 종결=`CASE_CLOSE`(대상=`case_id`)**, **규제 팩 토글=`POLICY_PACK`(subjectRef=`tenant_id`)**, ACTION 아님. integration·tasks·PRD는 이 9종을 따른다.
- **AML 위임 필드**: `amlCaseRef`(= `fds_cases.aml_case_id`, integration 확정 대기).

---

## 14. 변경 이력

| 일자 | 버전 | 변경 내용 | 비고 |
|---|---|---|---|
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
