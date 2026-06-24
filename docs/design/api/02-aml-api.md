# AML Platform API 명세서 (aml-svc)

> 정본: `.claude/skills/_shared/target-architecture.md` (4서비스 모노레포 · 멀티테넌시 tenant/workspace/data-scope · raw PII 미저장 마스킹 · 4-eyes · 규제 Policy Pack STR/CTR/Travel Rule · bo-web→bo-api만, 엔진 직접호출 금지).
> 입력 진실: `docs/software/02-amlSvc-sass.md` v1.x(유스케이스·port·API group §15.7·§16 배포 모델·온보딩 프로비저닝 상태머신) + `docs/design/db/02-aml-db.md` v1.x(테이블·컬럼·enum 정본 — `aml_tenants.deployment_model`/`onboarding_status`/`infra_ref` §3.1·§5.28/§5.28a/§5.28b 포함, 구 `isolation_mode` V17a/V17b 폐기).
> 책임 서비스: `services/aml-svc` (Java 25, Spring Boot 3.5.x, 헥사고날, `com.hanpass.aml`). 참조 컨트롤러 패턴: `hanpass-ph/services/fds-svc/adapter/in/rest`. 참조: `docs/design/api/01-fds-api.md` v1.5(배포 모델·온보딩 FDS 패턴 정본).
> 본 명세의 식별자·필드·enum은 DB 설계서 §3(테이블)·§5(enum)와 **1:1 동기화**한다(추측 금지). bo-api 소유 서비스·온보딩 엔드포인트(§3.16·§5·§9)는 aml-svc 엔진 API(§2)에 미노출.

## 0. API 표면 구분 (3-plane)

설계서 §15(외부 연동) + §6.1(정본 매핑)에 따라 AML API는 3개의 plane으로 분리한다.

| Plane | base path | 호출자 | 인증 | 비고 |
|---|---|---|---|---|
| **Public API** (서비스 연동) | `/api/v1/aml/...`, `/api/v1/evidence/aml/...` | 서비스 core-banking·onboarding·PG·VASP 시스템 | API Key+HMAC / OAuth2 / mTLS (§15.7, D-13) | event ingest·screening·RA·TM·evidence |
| **Internal API** (엔진 간) | `/internal/v1/aml/...` | `fds-svc`(fraud escalation), 내부 스케줄러 | API Key + HMAC(`AmlIngestAuthenticationFilter`; `X-Internal-Service` 선택; mesh mTLS 는 P8 보강, T11/AML-ENG-05·T3) | fds↔aml event 연계(D-07 event 우선) |
| **Admin API** (운영 콘솔) | `/api/v1/admin/aml/...` | `bo-api`만 (bo-web은 bo-api 경유) | bo-api 세션/JWT + RBAC + data-scope | 명단·정책·case·결재·감사·evidence 관리 |

> **bo-web은 Admin API를 직접 호출하지 않는다.** 정본 §3·§4: `bo-web → bo-api(REST only) → aml-svc admin API`. 본 문서의 Admin API는 bo-api가 호출하는 aml-svc 계약이며, bo-web↔bo-api 계약은 bo-api 측 PRD/스펙에서 파생한다.

모든 plane 공통 버저닝: `/api/v1`, `/internal/v1`. breaking change는 `/api/v2`로 분기(병행 운영).

> **정본 결정 요약(정합성 리포트 design:api 정정분).** 아래 5건은 본 API 명세를 파생(설계서·연동·태스크·PRD·PPT)의 진실로 확정한다.
> 1. **운영자 집계 API 소유 경계 = bo-api(§9).** 대시보드(플랫폼·서비스별)·서비스 관리(목록/상세/등록/설정)·운영자 감사 조회 화면이 호출하는 집계 엔드포인트는 **bo-api가 소유·집약·인증**한다. aml-svc(엔진)는 저수준 데이터 API만 제공하며, **본 엔진 API 명세(§2)에는 운영자 집계 엔드포인트(대시보드/서비스/감사)를 추가하지 않는다.** PRD/PPT의 해당 화면은 호출 대상을 bo-api(`/api/v1/bo/aml/**`)로 명시한다. (§2.7 `audit-events`는 엔진 측 append-only 저수준 감사 조회이며, 운영자 화면용 감사 집계는 bo-api가 위임 호출한다.)
> 2. **마스터 enum = 본 API enum(전수) 정본.** screening_status 마스터는 `NO_MATCH`/`POSSIBLE_MATCH`/`TRUE_MATCH`/`FALSE_POSITIVE`/`AUTO_DISCOUNTED`/`ESCALATED`(§3.2·§5)이며 설계서 예시의 `POTENTIAL_MATCH`/`result`는 `POSSIBLE_MATCH`/`status`로 환원한다. 결재 `subjectType` 마스터는 §3.7 enum(총 16종 — `TM_SCENARIO`/`CHECKLIST_CHANGE`/`PERIODIC_REVIEW_CHANGE` 포함)이 정본이며 설계서·PRD·DB §5.16은 이에 동기화한다.
> 3. **HTTP 상태코드 = §4 정본.** 멱등 충돌 409·결재 미충족/자기승인 409·payload 변경 409·상태전이 위반 409·screening 검토요구 422·rate limit 429·fail-closed 503을 §4로 확정한다.
> 4. **Webhook 콜백 계약 = §8 정본.** screening/case/report 상태변경 outbound 콜백 3종·envelope·`X-Signature` HMAC·재시도/멱등을 §8로 확정한다. 설계서 §15.7 'Webhook API'는 본 §8을 정본으로 참조한다.
> 5. **배포 모델/온보딩 = bo-api 소유, aml-svc 엔진 API 미추가(§9·§3.16).** 서비스(테넌트=서비스) 등록은 격리 토글(구 `isolation_mode` 라디오)이 아니라 **배포 유형 선택(`DeploymentModel`) + 온보딩 신청(`OnboardingStatus` 상태머신)** 흐름이다(정본 §4.1, D-06 결정 확정). `DeploymentModel` 3종·`OnboardingStatus` 8종은 DB §5.28/§5.28a 정본과 1:1(FDS API v1.5 §10 동기화). bo-api 전용 엔드포인트 5종(§5 paths, §9 표) — `GET/POST /api/v1/bo/aml/tenants`, `GET/PUT .../tenants/{tenantId}`, `POST .../onboarding/provision`, `POST .../onboarding/register`, `GET .../onboarding`. `isolationMode` 필드·`isolation_mode` 컬럼·구 enum 전면 폐기. 오픈결정: SELF_HOSTED `registrationToken` 인증 방식(서명·mTLS 등) 상세는 P8 인프라 설계 확정.

---

## 1. 공통 규약 (횡단)

### 1.1 인증·테넌시·data-scope

| 요소 | 전달 방식 | 필수 | 설명 |
|---|---|---|---|
| Tenant | `Tenant-Id` 헤더 (Public/Internal) / bo-api 세션 클레임 (Admin) | Y | DB `tenant_id`(테넌트=서비스, 상위 기관 institution이 운영하는 서비스 1종·1 기관 : N 서비스). 전용 배포(`MANAGED_DEDICATED`/`SELF_HOSTED`)에서는 배포=서비스 단일 값(라우팅은 배포 엔드포인트 단위). `SHARED` 배포에서만 `Tenant-Id` 헤더 행 라우팅·RLS `app.current_tenant` 세션변수로 강제 |
| Source System | `Source-System` 헤더 | Public Ingest/Screen Y | DB `aml_source_systems.source_system`. 미등록 source는 거부 |
| Data-scope | bo-api 토큰 클레임 `dataScope` / 쿼리 `dataScope` | N | DB `data_scope`(영업점·법인그룹 하위 격리, 정본 §4) |
| 서명 | `X-Signature: hmac-sha256=...` | Public Y | body HMAC (source `secret_ref` 키), 위변조 방지 |
| Idempotency | `Idempotency-Key` 헤더 | 쓰기성 Public Y | DB `aml_canonical_events.idempotency_key` UNIQUE(tenant_id,idempotency_key) |
| Trace | `X-Trace-Id`(없으면 생성) | N | DB `trace_id` 전파(설계서 §20.3). 응답 `X-Trace-Id` 반향 |

권한 scope(**마스터=본 §1.1 enum 전수 정본**, OAuth2/RBAC 공통, 설계서 §15.7·PRD §1.4는 이에 동기화): `aml:event:write`, `aml:screen:evaluate`, `aml:ra:evaluate`, `aml:tm:evaluate`, `aml:case:read`, `aml:case:update`, `aml:evidence:export`, `aml:admin:watchlist`, `aml:admin:source-system`, `aml:admin:policy`, `aml:admin:approval`, `aml:admin:audit`, `aml:pii:reveal`(원문/raw PII 접근, 사유+감사 `RAW_DATA_ACCESS` 필수, §1.6). 총 13종. 설계서 §15.7 'scope 예시'와 PRD §1.4는 본 §1.1 전수 enum을 정본으로 인용한다.

### 1.2 응답 envelope

참조 구현(`FdsInlineScreenController`)과 동일하게 성공은 `data`, 실패는 `error` 래핑.

```json
// 성공 (단건)
{ "data": { ... }, "traceId": "..." }
// 성공 (목록)
{ "data": [ ... ], "page": { "page": 0, "size": 20, "totalElements": 137, "totalPages": 7, "sort": "createdAt,desc" } }
// 실패
{ "error": { "code": "AML.SCREENING_NOT_FOUND", "message": "...", "details": [], "traceId": "..." } }
```

### 1.3 페이지네이션·정렬·필터

- 페이지: `?page=0&size=20`(size 최대 200). 응답 `page` 메타.
- 정렬: `?sort=createdAt,desc` (다중: `sort` 반복). 허용 필드는 인덱스 컬럼(DB §4)으로 제한.
- 필터: 리소스별 명시 쿼리(예: `status`, `caseType`, `riskGrade`, `from`/`to`). enum 값은 DB §5 코드값.
- 커서: 대량 evidence 조회는 `?cursor=...` 옵션(append-only 테이블).

### 1.4 멱등성

- `Idempotency-Key` + `tenant_id`로 중복 쓰기 차단(DB `ux_event_idem`).
- 동일 키 재요청: 최초 결과 재반환(200). 처리 중 충돌: `409 AML.IDEMPOTENCY_CONFLICT`. 미완료 재시도: `503 AML.IDEMPOTENCY_PROCESSING` + `Retry-After`.

### 1.5 4-eyes(결재) 표기

본 문서에서 **🔒4-eyes** 표기된 엔드포인트는 작성자≠승인자 결재(`aml_approvals`, CHECK `maker_id<>checker_id`)를 거쳐야 실행된다(설계서 §13.4~§13.5). 호출 흐름: `① 상신(maker) → 202 + approvalId(status=SUBMITTED) → ② 승인(checker) → APPROVED → ③ 실행 → EXECUTED`. payload는 `payload_hash`로 고정되어 승인 후 변경 시 무효화.

> **`DRAFT` 상태는 내부 전이 상태로 API 미노출.** `ApprovalDto.status`(§3.7) 및 API 호출 흐름에서 `DRAFT`는 내부 엔진 초기화 단계이며 외부 호출자(bo-api/bo-web)에게 노출되지 않는다. API 표면 첫 관찰 가능 상태는 `SUBMITTED`(상신 완료, 202 응답)이다(설계서 §13.5 상태머신 대비). PRD/화면은 `DRAFT` 배지 표시 불필요.

### 1.6 PII 마스킹

DTO는 raw PII를 노출하지 않는다(DB §2.2). 식별은 `customerRef`/`entityRef`(토큰), 매칭 근거는 `*Hash`/`scoreBreakdown`만. 원문 접근이 불가피한 화면은 `aml:pii:reveal` scope(§1.1 enum 등재·OpenAPI scopes 정식, 13번째) + 사유 + `aml_audit_events`(`RAW_DATA_ACCESS`) 기록.

---

## 2. 엔드포인트 표

### 2.1 Ingest API (Public) — 설계서 §8·§15.1·§15.3

| 메서드 | 경로 | scope | 멱등 | 설명 | DB |
|---|---|---|---|---|---|
| POST | `/api/v1/aml/events` | `aml:event:write` | Y | canonical AML event 수신(customer/entity/transaction/screening/...) | `aml_canonical_events` |
| POST | `/api/v1/aml/events:batch` | `aml:event:write` | Y | 대량 event 배치 수신(queue 대체 동기 경로) | `aml_canonical_events` |
| GET | `/api/v1/aml/events/{eventId}` | `aml:event:write` | — | 수신 event 상태 조회(idempotency 확인) | `aml_canonical_events` |

### 2.2 Screening API (Public) — 설계서 §10·§15.2·§15.7

| 메서드 | 경로 | scope | 멱등 | 설명 | DB |
|---|---|---|---|---|---|
| POST | `/api/v1/aml/screen` | `aml:screen:evaluate` | Y | 실시간 WLF/제재/PEP screening(온보딩·수취인·출금주소) | `aml_screening_results` |
| GET | `/api/v1/aml/screenings/{screeningId}` | `aml:screen:evaluate` | — | screening 결과 조회 | `aml_screening_results` |

### 2.3 Risk Assessment API (Public) — 설계서 §11

| 메서드 | 경로 | scope | 멱등 | 설명 | DB |
|---|---|---|---|---|---|
| POST | `/api/v1/aml/risk-assessments/evaluate` | `aml:ra:evaluate` | Y | 고객/법인/셀러 위험평가 실행 | `aml_risk_scores` |
| GET | `/api/v1/aml/risk-assessments/{scoreId}` | `aml:ra:evaluate` | — | RA 결과 조회 | `aml_risk_scores` |
| GET | `/api/v1/aml/customers/{customerRef}/risk` | `aml:case:read` | — | 대상 최신 등급 조회 | `aml_risk_scores` |

### 2.4 Transaction Monitoring API (Public) — 설계서 §12

| 메서드 | 경로 | scope | 멱등 | 설명 | DB |
|---|---|---|---|---|---|
| POST | `/api/v1/aml/transactions/evaluate` | `aml:tm:evaluate` | Y | 거래 TM 평가·alert 생성 | `aml_alerts`(+`aml_canonical_events`) |
| GET | `/api/v1/aml/alerts/{alertId}` | `aml:case:read` | — | alert 조회(응답 DTO §3.4a `AlertDto`) | `aml_alerts` |

> 엔진(aml-svc) public 알림 목록은 `status` 단일 필터(`GET /api/v1/aml/alerts?status=`)의 저수준 큐 조회다. **운영자 화면용 다중 필터 브라우즈 목록(`sourceOrigin`·`severity`·`scenario`·`channel`·`corridor`·`targetRef`·`from`/`to`)은 bo-api `GET /api/v1/bo/aml/alerts`(§2.5a)** 가 위임·집약한다(엔진 직접 다중필터 미노출).

### 2.5 Regulatory Evidence API (Public) — 설계서 §15.6

| 메서드 | 경로 | scope | 멱등 | 설명 | DB |
|---|---|---|---|---|---|
| GET | `/api/v1/evidence/aml/customers/{customerRef}/profile` | `aml:evidence:export` | — | 고객 CDD/EDD/RA/WLF 프로필 evidence | 다중 |
| GET | `/api/v1/evidence/aml/cases/{caseId}/timeline` | `aml:evidence:export` | — | case timeline evidence | `aml_cases` |
| GET | `/api/v1/evidence/aml/reports/str-candidates?from&to` | `aml:evidence:export` | — | STR 후보 기간 조회 | `aml_regulatory_reports` |
| POST | `/api/v1/evidence/aml/exports` | `aml:evidence:export` | Y | evidence pack export 생성(manifest hash) | `aml_evidence_exports` |
| GET | `/api/v1/evidence/aml/exports/{exportId}` | `aml:evidence:export` | — | export 상태·다운로드 URL 조회 | `aml_evidence_exports` |

### 2.5a 대상 360° 통합 뷰 (bo-api 집계, 신규 — hanpass-ph 재그라운딩)

| 메서드 | 경로 | scope | 멱등 | 설명 | DB |
|---|---|---|---|---|---|
| GET | `/api/v1/bo/aml/subjects/{customerRef}/360` | `aml:case:read` | — | **대상 360° 통합 뷰** — `tx-history-svc` 회원 통합 이력 + `member-svc` CDD/screening(zoloz) + `wallet-svc` `transfer_links` 자금그래프 결합 read model(DB §3.16). RA-003 드릴다운·CASE 타임라인·TM 알림 상세의 공통 골격. 응답 DTO §3.16a `Subject360Dto` | 다중(read model) |
| GET | `/api/v1/bo/aml/alerts?status=&severity=&sourceOrigin=&scenario=&from=&to=&targetRef=&channel=&corridor=&page=&size=` | `aml:case:read` | — | **TM 알림 브라우즈 목록**(AML-TM-001 ①, 출처 AML/FDS/VENDOR·심각도·상태·시나리오·기간·채널·corridor·대상 필터). 응답 `AlertDto[]`(§3.4a). bo-api `AmlTmController`가 aml-svc 위임. **필터 파라미터명 = `scenario`**(엔진 단건 응답의 `scenarioCode`와 키 구분) | `aml_alerts` |

> bo-api 소유 집계(read-only 파생, raw PII 미노출). STR 건수 등 tipping-off 민감 항목은 준법감시 전담 scope 한정 투영(설계서 §19.2a). 엔진 `GET /aml/customers/{customerRef}/profile`(CDD-002)·`/risk`를 결합하며 별도 영속 테이블 없음.

### 2.6 Internal API (엔진 간) — 설계서 §6.1·§12.3·D-07

| 메서드 | 경로 | 호출자 | 설명 | DB |
|---|---|---|---|---|
| POST | `/internal/v1/aml/fds-escalations` | `fds-svc` | FDS fraud case → `STR_REVIEW`/`alert` escalation 수신(body §3.10 `FdsEscalationRequest` → `FdsDecisionCommand` 어댑팅, `fraudCaseRef`=멱등키, 응답 `{ alertId, accepted }`). SQS `aml-fds-decision` 큐 경로(`FdsDecisionConsumer`)와 **동일 usecase·동일 멱등(DB partial UNIQUE)·동일 감사**(T11/AML-ENG-05). 인증 = **API key + HMAC**(ingest 필터 `AmlIngestAuthenticationFilter` 차용, ADR 2026-06-15 D2; mesh mTLS 는 P8 보강). scope 강제는 호출자(fds-svc) 평면 책임(가정 A5). | `aml_alerts`(source_origin=FDS) |
| GET | `/internal/v1/aml/customers/{customerRef}/risk` | `fds-svc` | AML high-risk/WLF 상태 조회(FDS risk group 전파용). public `GET /api/v1/aml/customers/{customerRef}/risk`와 동일 `AssessRiskUseCase`·`CustomerRiskResponse` 재사용(가정 A6), 최신 RA 등급 단독(WLF 병합 미정의 → 후속). 미존재 시 404 `AML.NOT_FOUND`. 인증 = **API key + HMAC**(가정 A1, mesh mTLS 는 P8 보강). | `aml_risk_scores`,`aml_screening_results` |
| POST | `/internal/v1/aml/screen` | 내부 onboarding mesh | 내부 서비스용 동기 screening. public `POST /api/v1/aml/screen`와 동일 `ScreenSubjectUseCase`·`ScreenRequest`/`ScreeningResponse` 재사용(가정 A6), `Idempotency-Key` 헤더 필수(가정 A4·공개 경로 일관). 인증 = **API key + HMAC**(가정 A1, mesh mTLS 는 P8 보강). | `aml_screening_results` |
| POST | `/internal/v1/aml/pii/reveal` | `bo-api` | 마스킹 PII reveal 정본(입력 `targetRef`/`field`/`reason` → 출력 `value`=이 요청 한정 transient cleartext). 인증 = **API key + HMAC**(ingest 필터 `AmlIngestAuthenticationFilter` 차용, T3/AML-ENG-03·ADR 2026-06-15 D2). 엔진측 `RAW_DATA_ACCESS` 감사 1건(마스킹 detail). 역참조 미존재·복호화 실패 시 **503 `AML.SCREENING_UNAVAILABLE`**(fail-closed). scope `aml:pii:reveal` 강제는 호출자(bo-api) 평면 책임(§1.6, 가정 A5). mesh mTLS 는 배포계층(P8) 보강. | `aml_pii_vault`(가역암호 vault, DB §3.x) |

### 2.7 Admin API (bo-api 전용) — 설계서 §13~§14·§16

#### Watchlist / 명단 (§10)
| 메서드 | 경로 | scope | 4-eyes | 설명 | DB |
|---|---|---|---|---|---|
| GET | `/api/v1/admin/aml/watchlist-sources` | `aml:admin:watchlist` | — | source 목록 | `aml_watchlist_sources` |
| POST | `/api/v1/admin/aml/watchlist-sources` | `aml:admin:watchlist` | — | source 등록 | `aml_watchlist_sources` |
| POST | `/api/v1/admin/aml/watchlist-sources/{sourceCode}/imports` | `aml:admin:watchlist` | — | import 업로드(diff 생성, DRAFT) | `aml_watchlist_entries` |
| POST | `/api/v1/admin/aml/watchlist-sources/{sourceCode}/imports/{version}:apply` | `aml:admin:watchlist` | 🔒4-eyes | import 적용(active_version 승격) | `aml_watchlist_sources` |
| GET | `/api/v1/admin/aml/watchlist-entries` | `aml:admin:watchlist` | — | 명단 항목 조회(masked) | `aml_watchlist_entries` |

#### Screening 검토 (§10.4)
| 메서드 | 경로 | scope | 4-eyes | 설명 | DB |
|---|---|---|---|---|---|
| GET | `/api/v1/admin/aml/screenings?status=POSSIBLE_MATCH` | `aml:case:read` | — | 검토 큐 조회 | `aml_screening_results` |
| POST | `/api/v1/admin/aml/screenings/{screeningId}/decision` | `aml:case:update` | 🔒4-eyes(TRUE_MATCH/FP) | WLF 판정(true/false positive) | `aml_screening_results`,`aml_approvals` |
| POST | `/api/v1/admin/aml/screenings/fp-whitelist` | `aml:admin:watchlist` | 🔒4-eyes | false positive whitelist 등록 | `aml_approvals` |

#### Risk Assessment 정책·override (§11.3)
| 메서드 | 경로 | scope | 4-eyes | 설명 | DB |
|---|---|---|---|---|---|
| GET | `/api/v1/admin/aml/ra-models` | `aml:admin:policy` | — | RA 모델 목록 | (정책 store) |
| POST | `/api/v1/admin/aml/ra-models/{modelCode}/simulate` | `aml:admin:policy` | — | sample population simulation(응답 DTO §3.15 `SimulationResponse`) | — |
| POST | `/api/v1/admin/aml/ra-models/{modelCode}/versions/{version}:activate` | `aml:admin:policy` | 🔒4-eyes | RA 모델 활성화 | `aml_approvals` |
| GET | `/api/v1/admin/aml/risk-scores?riskGrade=&modelVersion=&page=&size=` | `aml:case:read` | — | **RA 점수 목록**(모니터링). `riskGrade` 멀티(콤마 구분)·`modelVersion`·페이지네이션 필터. 응답 `RiskScoreResponse[]`(§3.3, `mandatoryHighRisk`·`mandatoryHighRiskReasons` 포함). **구현됨**(`RiskScoreAdminController`) | `aml_risk_scores` |
| GET | `/api/v1/admin/aml/risk-scores/distribution?modelVersion=` | `aml:case:read` | — | **RA 등급 분포**. 응답 `RiskDistributionResponse`(§3.3b). **구현됨**(`RiskScoreAdminController`) | `aml_risk_scores` |
| GET | `/api/v1/admin/aml/customers/pipeline-stats?histogramDays=` | `aml:case:read` | — | **CDD/RA 파이프라인 집계**(KYC 상태 분포·신규 등록 윈도우·RA 처리 현황·기간 히스토그램). `Tenant-Id` 헤더 필수·`Workspace-Id` 옵션. `histogramDays` 1~90·기본 14(범위 밖 클램프). 응답 `CddRaPipeline`(§3.3c). 집계 카운트만(raw PII 미노출). **구현됨**(엔진) | `aml_customers`,`aml_risk_scores` |
| POST | `/api/v1/admin/aml/risk-scores/{scoreId}/override` | `aml:case:update` | 🔒4-eyes(하향) | 등급 수동 조정. 요청 `RiskOverrideRequest`(§3.3) | `aml_risk_scores`,`aml_approvals` |

#### TM scenario (§12)
| 메서드 | 경로 | scope | 4-eyes | 설명 | DB |
|---|---|---|---|---|---|
| GET | `/api/v1/admin/aml/tm-scenarios` | `aml:admin:policy` | — | scenario 목록 | (정책 store) |
| POST | `/api/v1/admin/aml/tm-scenarios/{scenarioCode}/simulate` | `aml:admin:policy` | — | scenario simulation(응답 DTO §3.15 `SimulationResponse`) | — |
| POST | `/api/v1/admin/aml/tm-scenarios/{scenarioCode}:activate` | `aml:admin:policy` | 🔒4-eyes | scenario 변경 적용 | `aml_approvals` |

#### Case / CDD·EDD (§13)
| 메서드 | 경로 | scope | 4-eyes | 설명 | DB |
|---|---|---|---|---|---|
| GET | `/api/v1/admin/aml/cdd/cases` | `aml:case:read` | — | case 목록(필터: caseType/status/assignedTo) | `aml_cases` |
| GET | `/api/v1/admin/aml/cdd/cases/{caseId}` | `aml:case:read` | — | case 상세·timeline | `aml_cases` |
| POST | `/api/v1/admin/aml/cdd/cases` | `aml:case:update` | — | case 생성(수동) | `aml_cases` |
| PATCH | `/api/v1/admin/aml/cdd/cases/{caseId}` | `aml:case:update` | — | 상태·담당자·우선순위 변경 | `aml_cases` |
| POST | `/api/v1/admin/aml/cdd/cases/{caseId}/timeline` | `aml:case:update` | — | 메모·증빙 추가 | `aml_cases` |
| POST | `/api/v1/admin/aml/cdd/cases/{caseId}:close` | `aml:case:update` | 🔒4-eyes(EDD 종결) | case 종결 | `aml_cases`,`aml_approvals` |
| POST | `/api/v1/admin/aml/cdd/cases/{caseId}:reject-relationship` | `aml:case:update` | 🔒4-eyes | 관계거절/온보딩 보류 확정 | `aml_cases`,`aml_approvals` |

#### Regulatory Reporting (§14)
| 메서드 | 경로 | scope | 4-eyes | 설명 | DB |
|---|---|---|---|---|---|
| GET | `/api/v1/admin/aml/reports?reportType=STR&status` | `aml:case:read` + **`COMPLIANCE` role 필수(STR 필터 시)** | — | 보고 목록. **tipping-off 통제(설계서 §19.2a)**: `reportType=STR` 조회 시 COMPLIANCE 전담 role 보유자만 허용 — scope에 `COMPLIANCE` role이 없으면 `403 AML.FORBIDDEN_SCOPE`. 운영자 화면에 정보누설금지(tipping-off) 경고 배너 표시 필요. 열람 이벤트는 `RAW_DATA_ACCESS` 감사 기록 | `aml_regulatory_reports` |
| POST | `/api/v1/admin/aml/reports` | `aml:case:update` | — | 보고 초안 생성(DRAFT) | `aml_regulatory_reports` |
| POST | `/api/v1/admin/aml/reports/{reportId}:submit` | `aml:case:update` | 🔒4-eyes(REPORTING_OFFICER) | STR/CTR/Travel Rule 제출 | `aml_regulatory_reports`,`aml_approvals` |
| POST | `/api/v1/admin/aml/reports/{reportId}:reject` | `aml:case:update` | 🔒4-eyes(REPORTING_OFFICER) | 보고 기각(`REJECTED` 전이) — **사유 코드(`reasonCode`) 필수**, 자기승인 금지(설계서 §14.1a) | `aml_regulatory_reports`,`aml_approvals` |
| POST | `/api/v1/admin/aml/reports/{reportId}:cancel` | `aml:case:update` | 🔒4-eyes(REPORTING_OFFICER) | 보고 취소(`CANCELLED` 전이) — **사유 코드(`reasonCode`) 필수**, CTR 제외 처리(§14.3) 시 `ctrExemptionCode` 병기(설계서 §14.1a) | `aml_regulatory_reports`,`aml_approvals` |
| GET | `/api/v1/admin/aml/reports/stats/str-delay?period=7d\|30d\|90d` | `aml:case:read` + **`COMPLIANCE` role 필수** | — | STR 보고 지연일수 분포 집계 원천(PRD §12-B.3 ①). 보고별 candidate(`created_at`)→제출(`submitted_at`) 경과를 법정 SLA(§14.4 BR-006) 대비 상대 버킷 `{ON_TIME,D+1~3,D+4~7,D+8~14,D+15+}`으로 분류. **tipping-off 통제(§19.2a)**: COMPLIANCE 전담 role 필수(없으면 `403 AML.FORBIDDEN_SCOPE`), 열람은 `RAW_DATA_ACCESS` 감사. 응답은 집계 카운트만(보고 행·PII 미노출). 0건 → 빈 분포(honest, seed 없음). 응답 DTO §3.6 `DelayBucket[]` (T4 AML-ENG-04 — **확정**) | `aml_regulatory_reports` |
| GET | `/api/v1/admin/aml/reports/stats/unreported-reasons?period=7d\|30d\|90d` | `aml:case:read` + **`COMPLIANCE` role 필수** | — | STR 미보고(종결 비제출=`REJECTED`/`CANCELLED`) 사유 분포 집계 원천(PRD §12-B.3 ①). 종결 시 영속된 `closure_reason_code` 빈도(미영속 legacy = `UNSPECIFIED` 버킷, 소급 seed 없음). **tipping-off 통제(§19.2a)**: COMPLIANCE 전담 role 필수, `RAW_DATA_ACCESS` 감사. 응답 DTO §3.6 `UnreportedReason[]` (T4 AML-ENG-04 — **확정**) | `aml_regulatory_reports` |
| GET | `/api/v1/admin/aml/travel-rule/transfers?riskStatus&completenessStatus&from&to` | `aml:case:read` | — | Travel Rule exception 큐(필터/응답 DTO §3.14, riskStatus 4종·completenessStatus 4종) | `aml_travel_rule_transfers` |
| POST | `/api/v1/admin/aml/travel-rule/transfers/{transferRef}:resolve-exception` | `aml:case:update` | 🔒4-eyes | Travel Rule exception 확정 | `aml_travel_rule_transfers`,`aml_approvals` |

#### 기관위험평가(IRA, ML/TF) admin surface (T1 AML-ENG-01, 부록 E v6.0-2 — **확정**)
> aml-svc 엔진 admin surface. scope `aml:admin:ira`. KR 확장 plugin 활성 서비스 한정(부록 E). bo-api는 본 엔진 API를 프록시(후속 T12). 지표 auto-collection은 엔진 RA/TM/screening metric에서 파생(bo-api 로컬 파생 아님).

| 메서드 | 경로 | scope | 4-eyes | 설명 | DB |
|---|---|---|---|---|---|
| GET | `/api/v1/admin/aml/ira/reports?status&page&size` | `aml:admin:ira` | — | IRA 회차 목록(연도·회차·상태·지표 n/N) | `aml_ira_reports` |
| GET | `/api/v1/admin/aml/ira/reports/{reportId}` | `aml:admin:ira` | — | IRA 회차 상세(+지표값) | `aml_ira_reports`,`aml_ira_indicators` |
| POST | `/api/v1/admin/aml/ira/reports` | `aml:admin:ira` | — | 회차 생성(DRAFT, `copyFromPrevious` 직전값 복사) | `aml_ira_reports` |
| GET | `/api/v1/admin/aml/ira/reports/{reportId}/indicators` | `aml:admin:ira` | — | 지표값(자동 수집 + 수동 입력) | `aml_ira_indicators` |
| PUT | `/api/v1/admin/aml/ira/reports/{reportId}/indicators` | `aml:admin:ira` | — | 지표 인라인 저장(수동값·증빙 hash·확정) — 전 지표 확정 시 `CONFIRMED` 자동 전이 | `aml_ira_indicators` |
| POST | `/api/v1/admin/aml/ira/reports/{reportId}/report-file` | `aml:admin:ira` | — | 보고파일 생성(manifest hash, `CONFIRMED` 전제) | `aml_ira_reports` |
| POST | `/api/v1/admin/aml/ira/reports/{reportId}:submit` | `aml:admin:ira` | 🔒4-eyes(`IRA_SUBMIT`, 보고 책임자) | 보고파일 제출(`CONFIRMED→SUBMITTED`, 결재 EXECUTED 시 전이·outbox `IRA_REPORT`) | `aml_ira_reports`,`aml_approvals` |
| POST | `/api/v1/admin/aml/ira/reports/{reportId}:cancel` | `aml:admin:ira` | 🔒4-eyes(`IRA_SUBMIT`) | 회차 취소(`DRAFT`\|`CONFIRMED`→`CANCELLED`) | `aml_ira_reports`,`aml_approvals` |
| POST | `/api/v1/admin/aml/ira/reports/{reportId}/acknowledge` | `aml:admin:ira` | — | FIU 회신 폐루프(`SUBMITTED→ACKNOWLEDGED`, `fiuAckRef`·`fiuScore`·`peerAverage`, 멱등) | `aml_ira_reports` |
| POST | `/api/v1/admin/aml/ira/reports/{reportId}/fail` | `aml:admin:ira` | — | FIU/전송 실패 폐루프(`SUBMITTED→SUBMISSION_FAILED`, 멱등) | `aml_ira_reports` |

#### 당연고위험 레지스트리(High-Risk Registry, HRR) admin surface (T2 AML-ENG-02, 부록 E v7.0 — **확정**)
> aml-svc 엔진 admin surface. scope `aml:admin:high-risk-registry`(부록 E v7.0 미정의 — 결정2의 `aml:admin:policy` vs T2 본문 `aml:admin:high-risk-registry`, IRA `aml:admin:ira` 동형으로 후자 채택, 가정 A1). bo-api는 본 엔진 API를 프록시(후속 T13). 분류 기준(criteria)은 엔진 seed 정책(read-only, 가정 A2 — criteria 변경 API 미정의 → PUT 변경 대상은 참조 리스트로 한정). tenant 단위 정책(workspace 차원 없음, 가정 A3). 참조 리스트 3종 `PRODUCT`/`VASP`/`HIGH_NET_WORTH`(가정 A4), tier 2종 `HIGH`/`VERY_HIGH`(가정 A5). 분류 일치 대상은 결재 EXECUTED 시점에 엔진 RA가 등급을 **강제 상향 재평가**(VERY_HIGH→PROHIBITED·HIGH→HIGH floor, 상향만 보장, 가정 A6·A7).

| 메서드 | 경로 | scope | 4-eyes | 설명 | DB |
|---|---|---|---|---|---|
| GET | `/api/v1/admin/aml/high-risk-registry` | `aml:admin:high-risk-registry` | — | 분류 기준(criteria, read-only) + 참조 리스트(PRODUCT/VASP/HIGH_NET_WORTH) 조회 | `aml_high_risk_registry`,`aml_high_risk_registry_items` |
| PUT | `/api/v1/admin/aml/high-risk-registry/reference-lists/{listType}` | `aml:admin:high-risk-registry` | 🔒4-eyes(`HIGH_RISK_REGISTRY`) | 참조 리스트 변경 상신(전체 교체, `UPDATE\|<version>` subjectRef, 전체 staged payload drift guard) — 결재 EXECUTED 시 적용 + 일치 고객 RA 강제 상향 재평가 트리거 | `aml_high_risk_registry`,`aml_high_risk_registry_items`,`aml_approvals` |

#### CDD/EDD checklist·periodic review 정책 (§2.6·§13.1·§13.4·§13.5)
| 메서드 | 경로 | scope | 4-eyes | 설명 | DB |
|---|---|---|---|---|---|
| GET | `/api/v1/admin/aml/cdd/checklists` | `aml:admin:policy` | — | CDD/EDD checklist 정책 목록(항목·필수여부·증빙요건) | (정책 store) |
| POST | `/api/v1/admin/aml/cdd/checklists` | `aml:admin:policy` | — | checklist 정책 신규(DRAFT) | (정책 store) |
| PUT | `/api/v1/admin/aml/cdd/checklists/{id}` | `aml:admin:policy` | 🔒4-eyes | checklist 변경 적용(§13.4 'CDD checklist 변경' 결재) | `aml_approvals` |
| PUT | `/api/v1/admin/aml/cdd/periodic-review-policy` | `aml:admin:policy` | 🔒4-eyes | periodic review 주기 설정 변경(등급별 재확인 주기) | `aml_approvals` |

> CDD/EDD checklist·periodic review 주기는 RA 모델/TM scenario와 동일하게 **정책 store**(versioned artifact, 설계서 §5.3·§13.5) 산출물로 별도 물리 마스터 테이블은 미보유(DB §1 Account/Instrument 미보유 결정과 동류). 변경 적용은 4-eyes(설계서 §13.4 'CDD checklist 변경'·§2.6 '준법감시실 직접 수행, 개발팀 불필요'). 조회·초안(`GET`/`POST`)은 결재 불필요(§13.5 '조회·요약'/'초안 생성').

#### country risk·policy pack 관리 (§13.4·§13.5·§19.1·§19.3)
| 메서드 | 경로 | scope | 4-eyes | 설명 | DB |
|---|---|---|---|---|---|
| GET | `/api/v1/admin/aml/country-risk` | `aml:admin:policy` | — | 국가위험 등급표 조회(ISO 국가별 risk band·근거) | (정책 store) |
| POST | `/api/v1/admin/aml/country-risk:change` | `aml:admin:policy` | 🔒4-eyes(subjectType=`COUNTRY_RISK`) | 국가위험 변경 상신(§13.4 'country risk 변경') | `aml_approvals` |
| POST | `/api/v1/admin/aml/policy-packs:change` | `aml:admin:policy` | 🔒4-eyes(subjectType=`POLICY_PACK`) | tenant policy pack 변경 상신(STR/CTR/Travel Rule 기준금액·effective version, 설계서 §14.3·§19.1) | `aml_approvals`(+`aml_tenants.policy_pack_code`) |

> `country-risk:change`·`policy-packs:change`는 결재 상신 진입점이다. 상신 시 §3.7 `subjectType=COUNTRY_RISK`/`POLICY_PACK` 결재가 생성되며(`202 + approvalId`), 승인(checker) 후 실행(EXECUTED) 시점에 정책 store(국가위험 등급표 / `aml_tenants.policy_pack_code` effective version)에 반영된다. policy pack 기준금액(CTR 고액현금거래·STR·Travel Rule)은 법령·감독규정 변경 가능성이 있어 effective version으로 관리한다(설계서 §14.3).

#### 결재(공통)·감사·source (§13.5·§19.3·§16)
| 메서드 | 경로 | scope | 4-eyes | 설명 | DB |
|---|---|---|---|---|---|
| GET | `/api/v1/admin/aml/approvals?status=SUBMITTED` | `aml:admin:approval` | — | 결재 대기 큐 | `aml_approvals` |
| GET | `/api/v1/admin/aml/approvals/{approvalId}` | `aml:admin:approval` | — | 결재 상세 | `aml_approvals` |
| POST | `/api/v1/admin/aml/approvals/{approvalId}:approve` | `aml:admin:approval` | — | 승인(checker, maker≠checker 강제) | `aml_approvals` |
| POST | `/api/v1/admin/aml/approvals/{approvalId}:reject` | `aml:admin:approval` | — | 반려 | `aml_approvals` |
| GET | `/api/v1/admin/aml/source-systems` | `aml:admin:source-system` | — | source 목록 | `aml_source_systems` |
| POST | `/api/v1/admin/aml/source-systems` | `aml:admin:source-system` | 🔒4-eyes(secret 변경) | source 등록·secret 변경 | `aml_source_systems`,`aml_approvals` |
| GET | `/api/v1/admin/aml/audit-events?eventCategory&from&to&actor&subjectRef` | `aml:admin:audit` | — | append-only 감사 조회. `eventCategory` 허용값(DB §3.15 enum 10종): `WATCHLIST_IMPORT`/`WLF_DECISION`/`FP_WHITELIST`/`RA_MODEL_CHANGE`/`RISK_OVERRIDE`/`TM_SCENARIO_CHANGE`/`CASE_APPROVAL`/`REPORT_LIFECYCLE`/`RAW_DATA_ACCESS`/`POLICY_CHANGE` | `aml_audit_events` |

---

## 3. DTO 스키마

> 타입: `string`/`integer`/`number`/`boolean`/`object`/`array`/`enum`. R=required. enum 값은 DB §5.

### 3.1 IngestEventRequest → `POST /api/v1/aml/events` (DB `aml_canonical_events`)

| 필드 | 타입 | R | 검증/설명 |
|---|---|---|---|
| `eventId` | string | R | 원천 eventId. (tenant_id,event_id) PK |
| `idempotencyKey` | string | R | 헤더와 일치. UNIQUE |
| `sourceSystem` | string | R | 등록 source(헤더 동일). **hanpass-ph 실서비스 카탈로그(REST sync, DB §3.2 정본)**: `member-svc`/`walletchg-svc`/`domestic-svc`/`remit-svc`/`wallet-svc`/`inbound-svc`(`tx-history-svc`는 대상 360° read 소스로 ingest 미발행) |
| `schemaVersion` | string | R | schema registry 버전 |
| `eventType` | enum | R | §8.1 family: `customer.*`/`entity.*`/`transaction.*`/`screening.*`/`crypto.*`/`case.*`/... (hanpass-ph: member-svc→customer/entity/beneficial-owner, walletchg/domestic/remit/inbound→transaction.requested, remit/wallet→settlement.posted, wallet→account.*) |
| `occurredAt` | string(date-time) | R | ISO-8601 |
| `payload` | object | R | 정규화 payload. PII는 `*Ref`/`*Hash`만. raw 금지. **연동 키(원문 금지·keyed HMAC)**: `customer.customerRef`←`member.member_id`, `transaction.transactionRef`←`walletchg.charge_order_id`/`domestic.transaction_id`/`remit.transfer_number`/`*.wallet_transaction_id`, cross-border 거래는 `transaction.corridor`(send/receive country·currency←remit) + `transaction.amountBase`(USD←remit usd_amount/report_amount). **주의**: domestic-svc `member_id` varchar(36) join 정규화 |
| `payloadHash` | string | — | raw payload sha256(`stored=false`). DB `payload_hash` NOT NULL. **미제공 시 aml-svc ingest 어댑터가 수신 payload의 sha256을 자동 계산하여 INSERT**(서버 자동계산 방식 확정, DB §3.15 결정 주석 2026-06-08). 호출자가 직접 계산해 제공해도 무방(서버 값 우선). |

응답 `IngestEventResponse`: `{ eventId, accepted: boolean, idempotent: boolean, traceId }`.

### 3.2 ScreenRequest → `POST /api/v1/aml/screen` (DB `aml_screening_results`)

| 필드 | 타입 | R | 검증/설명 |
|---|---|---|---|
| `targetRef` | string | R | 대상 customer/entity/counterparty/wallet ref(토큰) |
| `targetType` | enum | R | `CUSTOMER`/`ENTITY`/`COUNTERPARTY`/`CRYPTO_ADDRESS` |
| `subject` | object | R | 매칭 입력. 원문은 일시 처리 후 미저장(§19.2) |
| `subject.nameTokens` | array<string> | — | 정규화 토큰(원문 대신 권장) |
| `subject.dob` | string(date) | — | 매칭용. 저장은 hash |
| `subject.country` | string | — | ISO 국가 |
| `subject.documentHash` | string | — | 문서번호 HMAC |
| `subject.walletAddressHash` | string | — | 지갑주소 HMAC(CRYPTO_ADDRESS) |
| `sourceTypes` | array<enum> | — | 대상 명단군(§5.4) 한정. 기본 전체 |

응답 `ScreenResponse` (DB `aml_screening_results`):

| 필드 | 타입 | 설명 |
|---|---|---|
| `screeningId` | string(uuid) | `screening_id` |
| `targetRef` | string | 대상 ref(DB `target_ref`, 마스킹 토큰) |
| `targetType` | enum | DB §5.23 target_type(`CUSTOMER`/`ENTITY`/`COUNTERPARTY`/`CRYPTO_ADDRESS`) |
| `status` | enum | §5.5 screening_status. **API 별칭 `POTENTIAL_MATCH`는 `POSSIBLE_MATCH`로 정규화**(DB §5.5 주석) |
| `score` | number | 유사도 |
| `scoreBreakdown` | object | name/dob/country/document/address/relationship(§10.3). **hanpass-ph 정합**: `member-svc zoloz_aml_screening`(`hit_results`→후보·항목별 점수, `risk_level`→`riskGrade`, `total_hits`→matched 카운트, `decision`→`status`)를 본 분해로 정규화 |
| `riskGrade` | enum | §5.2(평가 가능 시) |
| `reasonCodes` | array<string> | `reason_codes` (예: `SANCTIONS_NAME_SIMILARITY`,`DOB_MATCH`) |
| `requiredActions` | array<string> | `MANUAL_REVIEW`/`EDD_REVIEW`/... |
| `matchedEntries` | array<string> | 후보 entry_id(masked). **하위호환 유지** — `matchedCandidates`와 병존(기존 소비자 보존) |
| `matchedCandidates` | array<object> | **가산(additive) 필드.** 매칭 후보 출처계보. 각 원소 `MatchedCandidate`(아래 표) — `matchedEntries`의 각 entry_id를 `aml_watchlist_entries`+`aml_watchlist_sources` 조인으로 enrich한 best-effort 파생값. **raw PII 미포함**(masked entryId·출처·버전·점수·토큰개수만) |
| `matchedRules` | array<object> | 적용된 WLF 룰 참조 `{ ruleCode, threshold }`(파생값, DB `rule_version` 기준 투영). 단수 `ruleVersion`과 구분 |
| `ruleVersion` | string | 적용 WLF 룰/threshold 버전(DB `rule_version`) |
| `decidedBy` | string | 판정자(분석가, DB `decided_by`, nullable) |
| `decidedAt` | string(date-time) | 판정 시각(DB `decided_at`, nullable) |
| `expiresAt` | string(date-time) | 실시간 결과 만료(§15.7) |

> **`screeningHistory`(이전 판정 이력 배열)는 `ScreenResponse` 미포함.** 동일 `screeningId`의 이전 판정 이력은 `GET /api/v1/aml/screenings/{screeningId}` 상세 조회(§2.2) 응답에서 파생한다. PRD 화면파생 방향 채택 — bo-web/bo-api가 이력 상세가 필요할 경우 단건 조회 엔드포인트를 호출하며, 실시간 screening POST 응답(`ScreenResponse`)에는 이력 배열을 포함하지 않는다.

`MatchedCandidate`(매칭 후보 출처계보 — `matchedCandidates[]` 원소). **전 필드 nullable(best-effort).** bo-api가 `matchedEntries`의 각 entry_id로 `aml_watchlist_entries`·`aml_watchlist_sources`를 일괄 조인해 enrich하며, raw PII 필드는 일절 포함하지 않는다(masked entryId·출처·버전·점수·토큰개수만):

| 필드 | 타입 | nullable | 출처 매핑 |
|---|---|---|---|
| `entryId` | string | Y | 후보 entry_id(masked). DB §3.7 `aml_watchlist_entries.entry_id` |
| `sourceCode` | string | Y | 명단 source 코드. DB §3.7 `aml_watchlist_entries.source_code`(→§3.6 `aml_watchlist_sources` FK) |
| `provider` | string | Y | 제공처(UN/OFAC/internal 등). DB §3.6 `aml_watchlist_sources.provider` |
| `sourceType` | enum | Y | §5.4 source_type(`SANCTIONS`/`PEP`/`RCA`/`ADVERSE_MEDIA`/`INTERNAL`/`LAW_ENFORCEMENT`/`VASP_RISK`). DB §3.6 `aml_watchlist_sources.source_type` |
| `listType` | enum | Y | PRD 명단군 매핑(§3.9 `WatchlistEntryDto.listType` 정본). DB §3.7 `aml_watchlist_entries.list_type` |
| `subjectKind` | enum | Y | §5.24 subject_kind(watchlist entry 주체). DB §3.7 `aml_watchlist_entries.subject_kind` |
| `entryVersion` | string | Y | 명단 항목 버전. DB §3.7 `aml_watchlist_entries.version` |
| `sourceLastImportedAt` | string(date-time) | Y | 명단 source 최종 import 시각(신선도). DB §3.6 `aml_watchlist_sources.last_imported_at` |
| `matchField` | string | Y | 매칭된 필드(예: name/dob/document). `score_breakdown`·`matched_rules`에서 best-effort 파생 |
| `score` | number | Y | 후보별 유사도 점수. `score_breakdown`에서 best-effort 파생 |
| `threshold` | number | Y | 적용 threshold. `matched_rules`에서 best-effort 파생 |
| `reasonCodes` | array<string> | Y | 사유 코드. **현재 null**(향후 채움) |
| `matchedTokenCount` | number | Y | 매칭 토큰 개수(masked 통계) |

### 3.3 RiskAssessmentRequest → `POST /api/v1/aml/risk-assessments/evaluate` (DB `aml_risk_scores`)

| 필드 | 타입 | R | 설명 |
|---|---|---|---|
| `targetRef` | string | R | customer/entity ref |
| `targetType` | enum | R | `CUSTOMER`/`ENTITY` |
| `modelCode` | string | — | 미지정 시 tenant 기본 모델 |
| `factors` | object | — | factor 입력 override(§11.1) |
| `highRiskCountry` | boolean | — | (optional) 당연고위험 트리거 — 고위험 국가 연계. 미지정=false. 강제 상향 입력 신호(`EvaluateCommand`) |
| `wlfTrueMatch` | boolean | — | (optional) 당연고위험 트리거 — WLF 진성 매치. 미지정=false |
| `uboMismatch` | boolean | — | (optional) 당연고위험 트리거 — UBO 불일치/복잡 구조. 미지정=false |

응답 `RiskScoreResponse` (DB `aml_risk_scores`):

| 필드 | 타입 | 설명 |
|---|---|---|
| `scoreId` | string(uuid) | DB `score_id` |
| `targetRef` | string | 대상 ref(마스킹 토큰) |
| `targetType` | enum | DB §5.23 `target_type`(`CUSTOMER`/`ENTITY`) |
| `modelCode` | string | 적용 RA 모델 코드(DB `model_code`) |
| `modelVersion` | string | 적용 모델 버전(DB `model_version`) |
| `riskScore` | number | 0~100(DB `risk_score`) |
| `riskGrade` | enum | §5.2 risk_grade(`LOW`/`MEDIUM`/`HIGH`/`PROHIBITED`) |
| `factorBreakdown` | object | factor별 점수·근거(DB `factor_breakdown`) |
| `requiredAction` | enum | §5.26(`CDD_UPDATE`/`EDD`/`RELATIONSHIP_REVIEW`/`NONE`) |
| `mandatoryHighRisk` | boolean | 당연고위험 강제 상향 적용 여부. 점수 산식과 별개의 오버라이드 규칙(고위험 국가·WLF 진성·UBO 불일치·HRR 매칭). RA 점수 목록(`GET .../risk-scores`, §2.7) 응답에 포함 |
| `mandatoryHighRiskReasons` | array&lt;string&gt; | 당연고위험 적용 사유(업무 용어 문자열 배열, raw PII 없음). 강제 상향 미적용 시 빈 배열 |
| `nextReviewDueAt` | string(date-time) | 재심사 예정(DB `next_review_due_at`, nullable) |
| `isOverride` | boolean | 수동 등급 조정 여부(DB `is_override`, 4-eyes 대상) |
| `evaluatedAt` | string(date-time) | 평가 시각(DB `evaluated_at`) |
| `inputDataAsOf` | string(date-time) | nullable. **입력 데이터 기준시점**(평가에 사용된 원천 데이터의 as-of 시점). 엔진 응답에 있으면 passthrough, 없으면 best-effort(`evaluatedAt` 대체). RA 상세·점수 목록(`GET .../risk-scores`, §2.7) 응답에 포함 |
| `policyPackVersion` | string | nullable. **정책팩 버전**(평가 시점 적용 Policy Pack(STR/CTR/Travel Rule 기준) effective version). 엔진 응답에 있으면 passthrough, 없으면 `null`(stub 상수). RA 상세·점수 목록(§2.7) 응답에 포함 |

`RiskOverrideRequest` → `POST /api/v1/admin/aml/risk-scores/{scoreId}/override`(🔒4-eyes, §2.7, scope `aml:case:update`, subjectType=`RISK_OVERRIDE`):

| 필드 | 타입 | R | 설명 |
|---|---|---|---|
| `targetGrade` | enum | R | 조정 목표 등급(§5.2 `LOW`/`MEDIUM`/`HIGH`/`PROHIBITED`). **하향만 허용** — 현재 등급보다 낮은 등급만 선택 가능(상향은 거부). 화면은 위험점수 목록에서 행 선택 후 현재 등급 기준 하향 가능 등급만 select 노출 |
| `reason` | string | R | 조정 사유(필수, 감사·결재 payload) |
| `makerId` | string | R | 상신자(maker). 4-eyes — maker≠checker. 응답 `{ approvalId, status: "SUBMITTED" }` |

> override는 **블라인드 scoreId 직접 입력이 아니라** 위험점수 목록 조회(`GET .../risk-scores`, 등급 필터+`targetRef`) → 행 선택 → 현재 등급 기준 하향 가능 등급만 선택 → 사유 입력 → 4-eyes 상신 흐름이다(PRD §6.1 AML-RA-002).

### 3.3b RiskDistributionResponse → `GET /api/v1/admin/aml/risk-scores/distribution` (DB `aml_risk_scores`)

| 필드 | 타입 | 설명 |
|---|---|---|
| `modelVersion` | string | 집계 대상 모델 버전(nullable=전체) |
| `total` | long | 전체 점수 건수 |
| `gradeCounts` | object | 등급별 건수(`{LOW,MEDIUM,HIGH,PROHIBITED}` → count, 0-fill 고정 키) |
| `reviewDueSoon` | long | 30일 내 재심사 예정 건수 |
| `calculatedAt` | string(date-time) | 집계 시각 |

### 3.3c CddRaPipeline → `GET /api/v1/admin/aml/customers/pipeline-stats` (엔진) · `GET /api/v1/bo/aml/ra/pipeline-stats` (bo-api 위임, DB `aml_customers`·`aml_risk_scores`)

CDD/RA 온보딩 파이프라인 집계 read model. 출처 `aml_customers`(`kyc_status`·`onboarding_at`)·`aml_risk_scores`(`evaluated_at`·`next_review_due_at`). tenant 스코프·read-only. **전 항목 집계 카운트만 — raw PII 미포함.** `histogramDays` 1~90·기본 14(범위 밖 클램프). bo-api 경로는 비-prod stub·prod fail-closed(503 `AML.ENGINE_UNAVAILABLE`).

| 필드 | 타입 | 설명 |
|---|---|---|
| `kycStatusCounts` | object | KYC 상태별 고객 수(`{PENDING,VERIFIED,INCOMPLETE,EXPIRED,REJECTED}` → number). `aml_customers.kyc_status` 집계 |
| `registrationWindow` | object | 신규 등록 윈도우 `{ count24h(number), count7d(number), count30d(number) }`. `aml_customers.onboarding_at` 기준 |
| `raProcessing` | object | RA 처리 현황 `{ evaluated(number), pendingReview(number), notEvaluated(number) }`. `aml_risk_scores.evaluated_at`·`next_review_due_at` 기준 |
| `periodHistogram` | array&lt;object&gt; | 기간 RA 평가 히스토그램. 각 원소 `{ date(string: YYYY-MM-DD), evaluatedCount(number) }`. 길이=`histogramDays` |
| `generatedAt` | string(date-time) | 집계 생성 시각 |

### 3.4 TransactionEvaluateRequest → `POST /api/v1/aml/transactions/evaluate` (DB `aml_alerts`)

| 필드 | 타입 | R | 설명 |
|---|---|---|---|
| `transactionRef` | string | R | 거래 ref |
| `targetRef` | string | R | 고객/법인 ref |
| `direction` | enum | — | `INBOUND`/`OUTBOUND` |
| `amount` | string(decimal) | — | NUMERIC(24,8) 호환 문자열 |
| `amountMinor` | integer | — | 통화 최소단위(병행, DB `amount_minor`) |
| `currency` | string | — | ISO |
| `counterpartyRef` | string | — | 상대방 |
| `channelType` | string | — | 충전(walletchg)/국내(domestic)/해외(remit)/인바운드(inbound) 등 (hanpass-ph 채널) |
| `corridor` | object | — | cross-border corridor `{ sendCountry, receiveCountry, sendCurrency, receiveCurrency }`(remit-svc 파생). 국내 거래는 생략 |
| `amountBase` | string(decimal) | — | USD 정규화 금액(remit `usd_amount/report_amount` 파생). corridor 시나리오 집계용. **임계 교체 아님 — 데이터 신호** |

응답 `TransactionEvaluateResponse`: `{ evaluated: true, alerts: [ { alertId, alertType(enum TM_SCENARIO/SCREENING/RA/FDS_ESCALATION/VENDOR_ALERT — 본 API가 정본, DB §5.18 `alert_type` 1:1), scenarioCode(§5.6), severity(LOW/MEDIUM/HIGH/CRITICAL), status(§5.7), evidence } ] }`.

### 3.4a AlertDto → `GET /api/v1/aml/alerts/{alertId}` (DB `aml_alerts` §3.10 10컬럼+감사)

| 필드 | 타입 | 설명 |
|---|---|---|
| `alertId` | string(uuid) | DB `alert_id` PK |
| `alertType` | enum | §5.18 `alert_type`(`TM_SCENARIO`/`SCREENING`/`RA`/`FDS_ESCALATION`/`VENDOR_ALERT`). **API 정본, DB 1:1** |
| `scenarioCode` | enum | §5.6 `tm_scenario`(TM_SCENARIO 타입만, DB `scenario_code`, nullable) |
| `targetRef` | string | 대상 고객/법인 ref(마스킹 토큰, DB `target_ref`, nullable) |
| `transactionRef` | string | 관련 거래 ref(마스킹, DB `transaction_ref`, nullable). hanpass-ph: charge_order_id/transaction_id/transfer_number/wallet_transaction_id keyed token |
| `severity` | enum | §5.19 `alert_severity`(`LOW`/`MEDIUM`/`HIGH`/`CRITICAL`) |
| `status` | enum | §5.7 `alert_status` **6종**: `DETECTED`/`TRIAGED`/`CASE_OPENED`/`DISMISSED`/`ESCALATED`/`STR_RECOMMENDED`(DB CHECK 6종. 이후 조사·보고·종결은 `aml_cases.status` 인계) |
| `evidence` | object | **TM 알림 상세 데이터모델(DB §3.10 정본).** ① 트리거 `{ scenarioCode, strIndicator(데이터 신호 STR_001~015 ← remit.str_indicators), description }`, ② 집계 패턴 `{ measure, window, count, amount, currency, threshold }`(예 "5BD 9건 분할충전 합계 ₱480,000"), ③ `relatedTransactions[]`(`{ transactionRef, channel(충전/국내/해외), amount, currency, corridor, counterpartyRef, occurredAt, fdsDecisionRef }`), ④ `fundGraph`(자금그래프 funnel 미니뷰 — wallet `transfer_links` 그래프 요약). 식별자 token/hash, raw PII 금지 |
| `subject360Ref` | string | 대상 360° 통합뷰 링크 키(= `targetRef`/`customerRef`) → `GET /api/v1/bo/aml/subjects/{customerRef}/360`(§2.5a). nullable |
| `sourceOrigin` | enum | §5.20 `source_origin`(`AML`/`FDS`/`VENDOR`) |
| `externalAlertRef` | string | 외부 벤더 alert 식별자(DB `external_alert_ref`, nullable, `source_origin=VENDOR`일 때) |
| `createdAt` | string(date-time) | 생성 시각 |
| `updatedAt` | string(date-time) | 최종 수정 시각 |
| `aggregationSummary` | object\|null | **목록(브라우즈) 응답 한정 triage 프리뷰 집계.** TM 알림 **목록**(`GET /api/v1/bo/aml/alerts`, §2.5a → bo-api `AlertSummary`) 응답에서만 채워지는 가산 필드. `evidence`(트리거·집계 패턴)에서 목록 시점 파생(N+1 없음·행별 evidence 조립 회피)하며, **raw PII 미포함(집계 수치·라벨만)**. 단건 상세(`AlertDto`)는 `evidence` 전문을 제공하므로 본 요약은 생략 가능(null). 원소 `AggregationSummary`(아래 표) |

> raw PII 미노출. `targetRef`/`transactionRef`는 마스킹 토큰만. 감사 컬럼(`created_by`/`updated_by`/`trace_id`/`data_scope`)은 응답에서 생략.

`AggregationSummary`(`aggregationSummary` 객체 — TM 알림 목록 triage 프리뷰 집계). **전 필드 nullable(집계 파생·best-effort).** `evidence`의 트리거(`strIndicator`)·집계 패턴(`measure`/`window`/`threshold`/`count`/`amount`/`currency`)·`relatedTransactions[]` 에서 목록 시점 파생하며, raw PII는 일절 포함하지 않는다(집계 수치·라벨만):

| 필드 | 타입 | nullable | 설명 |
|---|---|---|---|
| `strIndicator` | string | Y | 데이터 신호 STR 지표(`STR_001`~`STR_015` ← remit.str_indicators). `evidence.트리거.strIndicator` 파생 |
| `windowLabel` | string | Y | 집계 윈도우 라벨(예 "5BD"). `evidence.집계패턴.window` 파생 |
| `measure` | number | Y | 집계 측정 항목(예 분할충전 합계, threshold와 동일 수치축). `evidence.집계패턴.measure` 파생 |
| `threshold` | number | Y | 적용 임계값. `evidence.집계패턴.threshold` 파생(데이터 신호, 규제 임계 교체 아님) |
| `thresholdMet` | boolean | Y | 임계 충족 여부(measure ≥ threshold 파생) |
| `relatedCount` | number | Y | 연관 거래 건수(masked 집계). `evidence.집계패턴.count`/`relatedTransactions[]` 파생 |
| `relatedAmount` | number | Y | 연관 거래 총액(masked 집계). `evidence.집계패턴.amount` 파생 |
| `currency` | string | Y | 합계 통화(ISO). `evidence.집계패턴.currency` 파생 |
| `dominantChannel` | string | Y | 우세 채널(충전/국내/해외). `relatedTransactions[].channel` 최빈값 파생 |

### 3.4b Subject360Dto → `GET /api/v1/bo/aml/subjects/{customerRef}/360` (bo-api 집계 read model, DB §3.16)

| 필드 | 타입 | 설명 |
|---|---|---|
| `customerRef` | string | 대상 키(= `member.member_id` keyed HMAC, 마스킹). domestic-svc varchar(36) join 정규화 |
| `identity` | object | 신원·CDD 요약(`member-svc`) `{ subjectType(string: `customer`/`transaction-only` — 고객 마스터 보유 여부), displayNameMasked(string: 표시명 마스킹 토큰), kycStatus, country, … }`(hash/token) |
| `riskSummary` | object\|null | 위험·활동 요약. `null` = 거래 전용 주체(고객 마스터 없음·RA 미산정). `{ riskGrade(§5.2), riskScore, factorBreakdown, nextReviewDueAt, mandatoryHighRisk(boolean — 당연고위험 강제 상향 여부), highRiskRegistryReason(**array&lt;string&gt;** — 당연고위험 레지스트리 사유, 단수 아님), screeningStatus(zoloz `risk_level`/`decision` 파생) }` |
| `transactionFeed` | array<object> | `tx-history-svc` 통합 이력(충전/국내/해외 타임라인 — `transactionRef`·`channel`·`amount`·`currency`·`corridor`·`direction`·`status`(string optional: `DECIDED`/`MONITORED`/null — 거래 처리 상태)·`occurredAt`, 마스킹). stub/빈 배열 가능 |
| `fundGraph` | object | `wallet-svc` `transfer_links` 자금그래프(funnel — 노드/엣지 요약, token). `source=PLACEHOLDER_NO_TRANSFER_LINKS` 가능(자금이체 링크 미연동) |
| `caseStrSummary` | object | 케이스·STR 건수 요약. **STR 건수는 준법감시 전담 scope 한정 투영(tipping-off §19.2a)** |
| `assembledAt` | string(date-time) | 데이터 신선도 — read model 조립 시각(nullable) |

> read-only 집계 파생. raw PII 미노출(token/hash·마스킹). 엔진 `GET /aml/customers/{customerRef}/profile`·`/risk` + canonical events(transaction.*) + relationships(`USES_ACCOUNT`/`REPEATED_PAYEE`)를 결합하며 별도 영속 테이블 없음(DB §3.16).
>
> **insight/assessment(결론 톤·헤드라인·근거)는 본 응답에 포함되지 않는다.** 대상 화면의 조사 결론(`conclusionTone`·`headline`·`engineReasons[]`·`derivedReasons[]`·`recommendation`)은 **bo-web 클라이언트가 Subject360 단면(알림·RA·자금 집중도 등)에서 로컬 파생**한다(`bo-web/lib/aml-subject-insight.ts`). API/bo-api 계약은 원천 단면(riskSummary·transactionFeed·fundGraph·caseStrSummary)만 제공하고, 톤·문구 합성은 화면 책임이다.

### 3.5 CaseDto (Admin, DB `aml_cases`)

| 필드 | 타입 | R(생성) | 설명 |
|---|---|---|---|
| `caseId` | string(uuid) | — | 응답 |
| `caseType` | enum | R | §5.8 case_type |
| `targetRef` | string | — | 대상(masked 식별자) |
| `status` | enum | — | §5.9 case_status |
| `priority` | enum | — | `LOW`/`MEDIUM`/`HIGH`/`URGENT` |
| `assignedTo` | string | — | 담당 분석가 |
| `eddTrigger` | enum | — | §13.2 EDD trigger. 허용값 8종(DB §5.29 정본): `WLF_TRUE_MATCH`/`HIGH_RA_SCORE`/`HIGH_RISK_COUNTRY`/`UNUSUAL_TRANSACTION`/`COMPLEX_OWNERSHIP`/`TRADE_MISMATCH`/`CRYPTO_RISK`/`INTERNAL_OVERRIDE` |
| `originAlertId` / `originScreeningId` | string(uuid) | — | 발단 |
| `originFdsCaseRef` | string | — | FDS 위임 발단 cross-ref(DB `origin_fds_case_ref`, `source_origin=FDS` 시 채움. fds-svc 역추적용, nullable) |
| `timeline` | array<object> | — | 처리 이력(evidence) |
| `dueAt` / `closedAt` | string(date-time) | — | SLA·종결 |

`CaseCloseRequest`(🔒4-eyes): `{ resolution, reason, makerId }` → 결재 상신.
`CaseTimelineEntryRequest`: `{ kind, note, evidenceRefs[] }`.

### 3.6 RegulatoryReportDto (Admin, DB `aml_regulatory_reports`)

| 필드 | 타입 | R(생성) | 설명 |
|---|---|---|---|
| `reportId` | string(uuid) | — | 응답 |
| `reportType` | enum | R | §5.10 report_type |
| `caseId` | string(uuid) | — | 연관 case |
| `targetRef` | string | — | 대상 |
| `status` | enum | — | §5.11 report_status. 허용값 8종(DB §5.11 정본): `DRAFT`/`UNDER_REVIEW`/`APPROVED`/`SUBMITTED`/`ACKNOWLEDGED`/`SUBMISSION_FAILED`/`REJECTED`/`CANCELLED` — FIU 회신 폐루프(설계서 §14.1a) |
| `reportPayload` | object | R | 본문(PII는 hash/token) |
| `approvalId` | string(uuid) | — | 결재 결과 FK(DB `approval_id`, nullable, 결재 연결 추적용) |
| `submittedRef` | string | — | 외부 제출 식별자(제출 후) |
| `submittedAt` | string(date-time) | — | 제출 시각 |
| `fiuAckRef` | string | — | FIU 접수번호(DB `fiu_ack_ref` — `ACKNOWLEDGED` 확정 시 채움) |
| `submissionErrorCode` | string | — | 전송 실패/FIU 오류 반려 오류코드(DB `submission_error_code` — `SUBMISSION_FAILED` 시 채움) |
| `resubmitCount` | integer | — | 재제출 횟수(DB `resubmit_count`, 기본 0) |
| `ctrExemptionCode` | string | — | CTR 제외(면제) 사유 코드(DB `ctr_exemption_code` — `GOV_ENTITY`/`FINANCIAL_INSTITUTION`/`OTHER_STATUTORY`, 설계서 §14.3) |
| `evidenceHash` | string | — | 제출 manifest hash |
| `reportDeadlineAt` | string(date-time) | — | **보고 기한(파생값, 설계서 §14.4)** — `STR`: 결재승인일 + 영업일 3일 / `CTR`: 거래일 + 30일. 서버가 `approvedAt` 또는 `transactionDate` 기준으로 계산해 채운다. 클라이언트 직접 계산 불필요. |
| `slaStatus` | enum | — | **SLA 상태(파생값, 설계서 §14.4)** — `ON_TIME`/`DUE_SOON`(D-3 이내)/`OVERDUE`. bo-web 화면 배지(D-3 경고·기한 초과 표시)에 사용. |

`ReportSubmitRequest`(🔒4-eyes): `{ makerId, reason, approvalLine: "REPORTING_OFFICER" }`.

`ReportRejectRequest`/`ReportCancelRequest`(🔒4-eyes, §2.7 `:reject`/`:cancel`): `{ makerId, reasonCode(string ●, 사유 코드 필수), reason(string △), approvalLine: "REPORTING_OFFICER" }` — `:cancel`로 CTR 제외 처리(§14.3) 시 `ctrExemptionCode`(●) 병기. **종결(`REJECTED`/`CANCELLED`) 시 `reasonCode`는 `aml_regulatory_reports.closure_reason_code`(DB §3.12)에 영속**되어 미보고 사유 분포(§2.7 `unreported-reasons`)의 집계 원천이 된다(T4 AML-ENG-04 — **확정**).

`DelayBucket`(§2.7 `reports/stats/str-delay` 응답, T4 AML-ENG-04 — **확정**): `{ bucketCode(enum: ON_TIME/D1_3/D4_7/D8_14/D15_PLUS), label(string), count(long) }` — 5종 버킷 0-fill 고정 배열(분포 모양 안정). 보고 행·PII 미노출(집계 카운트만). 지연 기준 = candidate(`created_at`)→제출(`submitted_at`) 경과의 법정 SLA(§14.4 BR-006, STR=결재승인+3영업일) 대비 상대 일수. SUBMITTED 미도달 건은 지연 모수에서 제외(미보고 사유 분포로 분류).

`UnreportedReason`(§2.7 `reports/stats/unreported-reasons` 응답, T4 AML-ENG-04 — **확정**): `{ reasonCode(string — `closure_reason_code` 코드값 또는 legacy 미영속 = `UNSPECIFIED`), count(long) }` — count 내림차순·reasonCode 사전순 정렬. 보고 행·PII 미노출.

> **재제출(RESUBMIT)·기각/취소 통제.** `SUBMISSION_FAILED` 건의 정정 후 재제출은 **별도 엔드포인트 없이 기존 `POST .../reports/{reportId}:submit`(🔒 `STR_SUBMIT`/`CTR_SUBMIT`) 신규 결재 사이클을 재사용**하며 서버가 `resubmitCount`를 증가시킨다(연동 §6.2). 보고 기각/취소(`REJECTED`/`CANCELLED`) 전이는 **전용 엔드포인트 `POST .../reports/{reportId}:reject`/`:cancel`(§2.7)** 로 수행하며, CTR 제외 처리(`CANCELLED`+`ctrExemptionCode`)를 포함해 **사유 코드 필수 + 보고책임자 결재(4-eyes, `REPORTING_OFFICER`, 자기승인 금지)** — 설계서 §14.1a/§14.3 정본.

### 3.7 ApprovalDto (Admin, DB `aml_approvals`)

| 필드 | 타입 | 설명 |
|---|---|---|
| `approvalId` | string(uuid) | PK |
| `subjectType` | enum | `WLF_DECISION`/`FP_WHITELIST`/`RA_MODEL`/`TM_SCENARIO`/`RISK_OVERRIDE`/`EDD_CLOSE`/`STR_SUBMIT`/`CTR_SUBMIT`/`TRAVEL_RULE_EXCEPTION`/`WATCHLIST_IMPORT`/`COUNTRY_RISK`/`POLICY_PACK`/`SECRET_CHANGE`/`RELATIONSHIP_REJECT`/`CHECKLIST_CHANGE`/`PERIODIC_REVIEW_CHANGE`/`IRA_SUBMIT`/`HIGH_RISK_REGISTRY` (총 **18종**. `TM_SCENARIO`=`tm-scenarios/{code}:activate`🔒 결재. `CHECKLIST_CHANGE`=CDD/EDD checklist 정책 변경. `PERIODIC_REVIEW_CHANGE`=periodic review 주기 변경. `IRA_SUBMIT`=기관위험평가(IRA) 회차 제출/취소(`SUBMIT`\|`reportId` / `CANCEL`\|`reportId` subjectRef 접두, T1 AML-ENG-01·부록 E v6.0-2 확정). `HIGH_RISK_REGISTRY`=당연고위험 레지스트리 참조 리스트 변경(`UPDATE`\|`<version>` subjectRef, 전체 staged payload drift guard, 결재 EXECUTED 시 적용 + RA 강제 상향 트리거, T2 AML-ENG-02·부록 E v7.0 확정). §2.7·PRD §11.1 동기화. DB §5.16 동기화 대상) |
| `subjectRef` | string | 대상(case_id/report_id 등) |
| `approvalLine` | enum | §5.12 approval_line |
| `status` | enum | §5.13 approval_status **7종(API 노출, `DRAFT` 제외)**: `SUBMITTED`/`APPROVED`/`REJECTED`/`CANCELLED`/`EXPIRED`/`EXECUTED`/`EXECUTION_FAILED`. `DRAFT`는 내부 엔진 전이 상태로 외부 미노출(§1.5) |
| `makerId` | string | 상신자 |
| `checkerId` | string | 승인자 (**maker≠checker**) |
| `payloadHash` | string | 고정 hash(변경 시 무효화) |
| `reason` | string | 사유 |
| `expiresAt` / `executedAt` | string(date-time) | 만료·실행(결재≠실행 분리) |

`ApprovalDecisionRequest`: `{ checkerId, decision: "APPROVE"|"REJECT", reason }`. 서버는 `checkerId == makerId` 시 `409 AML.SELF_APPROVAL_FORBIDDEN`.

### 3.8 EvidenceExportRequest → `POST /api/v1/evidence/aml/exports` (DB `aml_evidence_exports`, UseCase: `ExportEvidenceUseCase`)

> **UseCase 명칭 정본**: 본 API §3.8·§2.5의 `ExportEvidence`(→ `ExportEvidenceUseCase`)가 기준이다. SW 설계서 §6.2 교정 완료 — `ExportEvidenceUseCase`로 정합됨(2026-06-08 QA 이격 해소).

| 필드 | 타입 | R | 설명 |
|---|---|---|---|
| `exportType` | enum | R | `CDD_EDD`/`WLF_REGISTER`/`RA_REPORT`/`TM_HISTORY`/`STR_EVIDENCE`/`CTR_EVIDENCE`/`TRAVEL_RULE`/`WATCHLIST_CHANGE`/`VENDOR_CROSSREF`/`PII_ACCESS` |
| `format` | enum | R | `CSV`/`EXCEL`/`PDF`/`API` |
| `filterParams` | object | R | 기간/필터(재생성 query snapshot) |
| `reason` | string | R | export 사유(감사) |

응답 `EvidenceExportResponse`: `{ exportId, status, rowCount, manifestHash, downloadUrl(만료형), requestedBy, createdAt }`.

### 3.9 WatchlistSource / WatchlistEntry / SourceSystem / CustomerProfile (Admin)

`WatchlistSourceDto`: `{ sourceCode, sourceType(§5.4), provider, status(ACTIVE/DISABLED), activeVersion, lastImportedAt }`.

`WatchlistEntryDto`(GET `/admin/aml/watchlist-entries` 응답, DB `aml_watchlist_entries` — raw PII 미노출):

| 필드 | 타입 | 설명 |
|---|---|---|
| `entryId` | string(uuid) | DB `entry_id` |
| `sourceCode` | string | 소속 source |
| `listType` | enum | §5.4 watchlist_source_type(`SANCTIONS`/`PEP`/`RCA`/`ADVERSE_MEDIA`/`INTERNAL`/`LAW_ENFORCEMENT`/`VASP_RISK`). **PRD 명단군 매핑 정본** — bo-web 화면의 '명단군' 필터·배지는 이 7종 코드값을 기준으로 표시하며, PRD/PPT는 본 §3.9 `listType` enum을 진실로 인용한다 |
| `subjectKind` | enum | §5.24 subject_kind(`PERSON`/`ENTITY`/`VESSEL`/`CRYPTO_ADDRESS`) |
| `primaryNameHash` | string | 이름 HMAC(원문 미노출, DB `primary_name_hash`) |
| `normalizedTokens` | array<string> | 정규화 토큰(매칭용, 원문 아님) |
| `version` | string | import 버전 |
| `status` | enum | `ACTIVE`/`DELISTED` |
| `createdAt` | string(date-time) | |

> `attributes`(생년/국적/문서 hash/지갑주소 hash 등)는 hash/token만 노출. raw PII 원문 미포함(DB §2.2·§3.7).

`CustomerProfileDto`(GET `/evidence/aml/customers/{customerRef}/profile` 응답 — CDD/EDD/RA/WLF 통합 프로필 evidence, raw PII 미노출):

| 필드 | 타입 | 설명 |
|---|---|---|
| `customerRef` | string | 식별 토큰(원문 아님) |
| `customerType` | enum | §5.1 customer_type |
| `kycStatus` | enum | §5.25 kyc_status(PENDING/VERIFIED/INCOMPLETE/EXPIRED/REJECTED) |
| `riskGrade` | enum | §5.2 최신 RA 등급 |
| `nameHash` | string | 이름 HMAC(DB `name_hash`, 마스킹) |
| `docHash` | string | 신분증번호 HMAC(DB `doc_hash`, 마스킹) |
| `kycEvidence` | object | KYC checklist 상태(DB `kyc_evidence` JSONB, 원문 아님) |
| `nextReviewDueAt` | string(date-time) | 주기적 재확인 예정(DB `next_review_due_at`) |
| `latestScreening` | object | 최신 screening 결과 요약(`screeningId·status·riskGrade`) |
| `latestRiskScore` | object | 최신 RA 결과 요약(`scoreId·riskScore·riskGrade·evaluatedAt`) |
| `createdAt` | string(date-time) | |

> raw PII(이름·주민번호·여권번호 원문) 미노출. 식별은 `customerRef`(토큰), 매칭 보조는 `*Hash`만(DB §2.2). PII 원문 접근은 `aml:pii:reveal` scope+감사 필요(§1.6).

`SourceSystemDto`: `{ sourceSystem, ingestMode(§5.14), schemaVersion, authMode(API_KEY_HMAC/OAUTH2/MTLS), failurePolicy(MANUAL_REVIEW/FAIL_CLOSED/DELAY_ALLOWED), status(enum 2종: `ACTIVE`/`DISABLED` — DB §3.2 `aml_source_systems.status` 정본), enabled, createdAt(date-time), updatedAt(date-time) }`. `secretRef`는 응답에서 마스킹.

### 3.10 FdsEscalationRequest → `POST /internal/v1/aml/fds-escalations` (DB `aml_alerts`)

| 필드 | 타입 | R | 설명 |
|---|---|---|---|
| `fraudCaseRef` | string | R | fds-svc case 식별자 |
| `targetRef` | string | R | 고객/법인 ref |
| `transactionRef` | string | — | 관련 거래 |
| `severity` | enum | R | `LOW`/`MEDIUM`/`HIGH`/`CRITICAL` |
| `suggestedCaseType` | enum | — | 기본 `STR_REVIEW`(§14.2) |
| `evidence` | object | — | FDS decision feature |

→ `aml_alerts`(alert_type=`FDS_ESCALATION`, source_origin=`FDS`) 생성. 응답 `{ alertId, accepted }`.

### 3.11 CddChecklistDto / PeriodicReviewPolicyRequest (Admin, 정책 store)

`CddChecklistDto`(GET/POST `/admin/aml/cdd/checklists`):

| 필드 | 타입 | R(생성) | 설명 |
|---|---|---|---|
| `checklistId` | string | — | 응답. 정책 store 식별자 |
| `caseType` | enum | R | §5.8 case_type 적용 대상(CDD/EDD 등) |
| `version` | integer | — | versioned artifact 버전(응답) |
| `status` | enum | — | `DRAFT`/`ACTIVE`/`SUPERSEDED` |
| `items` | array<object> | R | checklist 항목 `{ itemKey, label, required(boolean), evidenceType, riskTrigger }`(업무 용어, 변수명 비노출 §2.6) |
| `effectiveFrom` | string(date-time) | — | 적용 시점(활성화 시) |

`ChecklistChangeRequest`(🔒4-eyes, `PUT .../cdd/checklists/{id}`): `{ items[], reason, makerId }` → **`subjectType=CHECKLIST_CHANGE`** 결재로 상신(`202 + approvalId`, 설계서 §13.4 'CDD checklist 변경'). `POLICY_PACK`과 별개 subjectType임에 유의.
`PeriodicReviewPolicyRequest`(🔒4-eyes, `PUT .../cdd/periodic-review-policy`): `{ cadenceByGrade: { LOW, MEDIUM, HIGH, PROHIBITED }(개월 주기), gracePeriodDays, reason, makerId }` → **`subjectType=PERIODIC_REVIEW_CHANGE`** 결재 상신. 응답은 결재 상신 `{ approvalId, status: SUBMITTED }`.

### 3.12 CountryRiskDto / CountryRiskChangeRequest (Admin, 정책 store)

`CountryRiskDto`(GET `/admin/aml/country-risk`):

| 필드 | 타입 | 설명 |
|---|---|---|
| `country` | string | ISO 국가코드 |
| `riskBand` | enum | `LOW`/`MEDIUM`/`HIGH`/`PROHIBITED`(국가위험 등급, RA 등급 §5.2와 동일 축) |
| `basis` | array<string> | 근거(FATF blacklist/greylist·제재·고위험 corridor 등) |
| `version` | integer | 정책 버전 |
| `effectiveFrom` | string(date-time) | 적용 시점 |

`CountryRiskChangeRequest`(🔒4-eyes, `POST .../country-risk:change`): `{ changes: [ { country, riskBand, basis[] } ], reason, makerId }` → §3.7 `subjectType=COUNTRY_RISK` 결재 상신. 응답 `{ approvalId, status: SUBMITTED }`. 실행(EXECUTED) 후 변경 국가 관련 대상 재평가(RA) 트리거.

### 3.13 PolicyPackChangeRequest (Admin, `aml_tenants.policy_pack_code`)

`PolicyPackChangeRequest`(🔒4-eyes, `POST .../policy-packs:change`):

| 필드 | 타입 | R | 설명 |
|---|---|---|---|
| `policyPackCode` | string | R | 대상 pack(`KR_DEFAULT` 등, DB `aml_tenants.policy_pack_code`) |
| `parameters` | object | R | STR/CTR/Travel Rule 기준금액·보고 대상·임계치(effective version 관리, 설계서 §14.3) |
| `effectiveFrom` | string(date-time) | — | 적용 시점(미지정 시 승인·실행 시점) |
| `reason` | string | R | 변경 사유(감사) |
| `makerId` | string | R | 상신자 |

→ §3.7 `subjectType=POLICY_PACK` 결재 상신. 응답 `{ approvalId, status: SUBMITTED }`. 실행 시 tenant policy pack effective version 갱신.

### 3.14 TravelRuleTransferDto / 필터 (Admin, DB `aml_travel_rule_transfers`)

`GET /admin/aml/travel-rule/transfers` 필터 쿼리: `?riskStatus=&completenessStatus=&from=&to=`(+ 페이지·정렬). 인덱스 `ix_trt_risk`(tenant_id, risk_status, completeness_status) 기반.

| 필드 | 타입 | 설명 |
|---|---|---|
| `transferRef` | string | DB `transfer_ref`(PK 일부) |
| `originatorRef` / `beneficiaryRef` | string | 송·수신 고객 ref(masked 토큰, 원문 미노출) |
| `assetCode` / `chain` | string | 가상자산 코드·체인 |
| `walletAddressHash` | string | 지갑주소 HMAC(원문 미저장, DB `wallet_address_hash`) |
| `amount` | string(decimal) | NUMERIC(24,8) 호환 문자열 |
| `amountMinor` | integer | 통화 최소단위 정수 병행(DB `amount_minor`) |
| `originatorVasp` / `beneficiaryVasp` | string | 송·수신 VASP |
| `completenessStatus` | enum | **§5.22 정본 4종**: `COMPLETE`/`MISSING_ORIGINATOR`/`MISSING_BENEFICIARY`/`INCOMPLETE` |
| `riskStatus` | enum | **§5.15 정본 4종**: `CLEAR`/`SANCTIONED_ADDRESS`/`MIXER_EXPOSURE`/`HIGH_RISK`. integration의 `REVIEW`는 `HIGH_RISK`로 정규화(DB §5.15) |
| `exceptionReason` | string | exception 처리 사유(4-eyes resolve 후, DB `exception_reason`) |
| `createdAt` | string(date-time) | 수신 시각 |

> exception 큐 트리거: `completenessStatus=INCOMPLETE` 또는 `riskStatus IN (HIGH_RISK, SANCTIONED_ADDRESS, MIXER_EXPOSURE)`(DB §3.14·§5.15·§5.22). `:resolve-exception`(🔒4-eyes)은 §3.7 `subjectType=TRAVEL_RULE_EXCEPTION` 결재.

### 3.15 SimulationResponse (Admin, RA/TM simulate 응답)

RA `POST .../ra-models/{modelCode}/simulate`·TM `POST .../tm-scenarios/{scenarioCode}/simulate` 공통 응답. **분석 설정이므로 결재 불필요**(설계서 §13.5). PRD §5.1(AML-RA-001 '시뮬레이션' 탭: `높음 +142 / 중간 -88 / 낮음 -54`, `오탐 영향 추정 +6%') 화면 의존.

| 필드 | 타입 | 설명 |
|---|---|---|
| `simulationId` | string(uuid) | 시뮬레이션 실행 식별자(감사·재현) |
| `modelVersion` / `scenarioVersion` | string | 대상 모델/시나리오 버전 |
| `samplePopulation` | object | `{ definition, sampleSize, periodFrom, periodTo }`(예: 최근 90일 신규) |
| `gradeShift` | object | 등급 이동 추정 `{ LOW(integer), MEDIUM, HIGH, PROHIBITED }`(부호 있는 증감, PRD '높음 +142 / 중간 -88 / 낮음 -54') |
| `falsePositiveImpact` | object | 오탐 영향 추정 `{ deltaPercent(number), baseline, projected }`(PRD '오탐 영향 추정 +6%') |
| `evaluatedAt` | string(date-time) | 실행 시각 |

### 3.16 TenantDto / TenantCreateRequest / OnboardingProvisionRequest / OnboardingRegisterRequest / OnboardingStatusResponse (bo-api 소유, DB `aml_tenants`)

> **bo-api 소유 서비스(테넌트=서비스)·온보딩 엔드포인트**(§9). aml-svc 엔진 API에는 미노출. 테넌트=서비스이며 상위 기관(institution)은 `institutionRef`(=`aml_tenants.institution_ref`)로 참조한다(1 기관 : N 서비스). 구 `isolationMode` 필드 폐기, `deploymentModel`/`onboardingStatus`로 교체. DB §3.1·§5.28·§5.28a·§5.28b와 1:1.

**`TenantDto`** (GET/PUT `/api/v1/bo/aml/tenants[/{tenantId}]` 응답):

| 필드 | 타입 | R | 설명 |
|---|---|---|---|
| `tenantId` | string | R | 서비스 ID (`aml_tenants.tenant_id`, 테넌트=서비스) |
| `institutionRef` | string | — | 상위 기관(institution) 참조 (`aml_tenants.institution_ref`). 1 기관 : N 서비스(테넌트). nullable·additive |
| `displayName` | string | R | 표시명 |
| `deploymentModel` | enum | R | §5.28: `MANAGED_DEDICATED`/`SELF_HOSTED`/`SHARED`. **온보딩 프로비저닝 산출 — 화면 즉석 라디오 변경 불가** |
| `onboardingStatus` | enum | R | §5.28a 8종: 온보딩 진행 상태. 읽기 전용(운영자 화면), 전이는 `/onboarding/provision`·`/onboarding/register` 통해서만 |
| `status` | enum | R | §5.28b **4종**: `ONBOARDING`/`ACTIVE`/`SUSPENDED`/`OFFBOARDED` (운영 생명주기, onboarding_status와 직교. DB V20 갱신 정본 — DEFAULT `ONBOARDING`, 온보딩 완료→`ACTIVE`, 정지→`SUSPENDED`, 해지완료→`OFFBOARDED`. 구 `OFFBOARDING`/DEFAULT `ACTIVE` 폐기) |
| `region` | string | R | 배포 리전(DB `default_region`, 기본값 `KR`) |
| `infraRef` | string | — | 배포 메타 참조(DB `infra_ref`). 매니지드=Terraform stack/workspace ID, self-hosted=라이선스·설치 인스턴스 ID. **응답 전용(생성 불가)** |
| `policyPackCode` | string | R | 적용 Policy Pack(DB `policy_pack_code`, 기본 `KR_DEFAULT`) |
| `createdAt` | string(date-time) | — | 생성 시각 |
| `updatedAt` | string(date-time) | — | 최종 수정 시각 |

> `isolationMode` 필드는 폐기(구 enum `SHARED`/`SCHEMA`/`DB` 전면 대체). 응답 DTO에 `isolationMode` 미포함.

**`TenantCreateRequest`** (POST `/api/v1/bo/aml/tenants`):

| 필드 | 타입 | R | 검증/설명 |
|---|---|---|---|
| `tenantId` | string | R | 서비스 ID(테넌트=서비스, UUID 또는 slug, 영문소문자+하이픈, 최대 64자) |
| `institutionRef` | string | — | 상위 기관(institution) 참조(`aml_tenants.institution_ref`, 최대 64자). 1 기관 : N 서비스. nullable·additive |
| `displayName` | string | R | 표시명(최대 160자) |
| `deploymentModel` | enum | R | §5.28 3종. **온보딩 신청 시점에 선택** — MANAGED_DEDICATED(기본·매니지드 전용 프로비저닝 시작), SELF_HOSTED(설치형 패키지 발급), SHARED(즉시 전환) |
| `region` | string | — | 배포 리전(기본 `KR`) |
| `policyPackCode` | string | — | Policy Pack 코드(기본 `KR_DEFAULT`) |

응답: `201 Created` + `TenantDto`(onboarding_status=REQUESTED 초기값, deploymentModel 선택값).

**`TenantUpdateRequest`** (PUT `/api/v1/bo/aml/tenants/{tenantId}` — 설정 변경):

| 필드 | 타입 | R | 설명 |
|---|---|---|---|
| `displayName` | string | — | 표시명 변경 |
| `status` | enum | — | 운영 생명주기 전이(ACTIVE→SUSPENDED 등). **`deploymentModel` 변경 불가** |
| `policyPackCode` | string | — | Policy Pack 변경 |

> `deploymentModel` 변경은 온보딩 프로비저닝 흐름(`/onboarding/provision`)만 허용하며 PUT 직접 변경은 `409 AML.TENANT_DEPLOYMENT_MODEL_IMMUTABLE`로 거부.

**`OnboardingProvisionRequest`** (POST `/api/v1/bo/aml/tenants/{tenantId}/onboarding/provision`):

| 필드 | 타입 | R | 설명 |
|---|---|---|---|
| `iacTemplate` | string | — | IaC 템플릿 버전(기본: 플랫폼 latest, Terraform 모듈 ref) |
| `targetRegion` | string | — | 배포 리전 override(기본: tenant `region`) |
| `requestedBy` | string | R | 요청 운영자 ID |

응답: `202 Accepted` + `{ tenantId, onboardingStatus: "PROVISIONING", infraRef: null, requestedAt }`. `MANAGED_DEDICATED`만 허용 — 다른 deploymentModel이면 `422 AML.ONBOARDING_PROVISION_NOT_APPLICABLE`.

**`OnboardingRegisterRequest`** (POST `/api/v1/bo/aml/tenants/{tenantId}/onboarding/register` — self-hosted 등록 콜백):

| 필드 | 타입 | R | 설명 |
|---|---|---|---|
| `instanceId` | string | R | 고객 인스턴스 식별자(설치 후 생성, DB `infra_ref` 매핑) |
| `registrationToken` | string | R | 플랫폼 발급 등록 토큰(서명·검증 방식은 P8 인프라 설계 확정·오픈결정) |
| `callbackEndpoint` | string | — | self-hosted 인스턴스 헬스 콜백 URL |

응답: `200 OK` + `{ tenantId, onboardingStatus: "REGISTERED", infraRef: "<instanceId>" }`. `SELF_HOSTED`만 허용 — 다른 deploymentModel이면 `422 AML.ONBOARDING_REGISTER_NOT_APPLICABLE`. `registrationToken` 불일치 시 `401 AML.INVALID_REGISTRATION_TOKEN`.

**`OnboardingStatusResponse`** (GET `/api/v1/bo/aml/tenants/{tenantId}/onboarding`):

| 필드 | 타입 | 설명 |
|---|---|---|
| `tenantId` | string | 서비스 ID(테넌트=서비스) |
| `deploymentModel` | enum | §5.28 3종 |
| `onboardingStatus` | enum | §5.28a 현재 상태 |
| `infraRef` | string | 배포 메타 참조(nullable) |
| `region` | string | 배포 리전 |
| `history` | array<object> | 상태 전이 이력 `{ status, transitionedAt, actor, note }` |
| `nextExpectedStatus` | string | 다음 예상 상태(상태머신 기반 안내용, nullable) |

---

## 4. 표준 에러 모델

`{ "error": { "code", "message", "details": [], "traceId" } }`. `code`는 `AML.<UPPER_SNAKE>`.

| HTTP | code | 발생 |
|---|---|---|
| 400 | `AML.BAD_REQUEST` | 스키마 검증 실패(필수 누락·타입·enum 위반) |
| 400 | `AML.UNKNOWN_SOURCE_SYSTEM` | 미등록 `Source-System` |
| 401 | `AML.UNAUTHENTICATED` | 인증 실패(키/토큰) |
| 401 | `AML.INVALID_SIGNATURE` | HMAC 서명 불일치 |
| 403 | `AML.FORBIDDEN_SCOPE` | scope/RBAC 부족 |
| 403 | `AML.TENANT_MISMATCH` | tenant/data-scope 경계 위반(RLS) |
| 404 | `AML.SCREENING_NOT_FOUND` / `AML.CASE_NOT_FOUND` / `AML.REPORT_NOT_FOUND` / `AML.APPROVAL_NOT_FOUND` | 리소스 없음 |
| 409 | `AML.IDEMPOTENCY_CONFLICT` | 동일 키 다른 payload |
| 409 | `AML.SELF_APPROVAL_FORBIDDEN` | maker==checker(4-eyes 위반) |
| 409 | `AML.APPROVAL_PAYLOAD_CHANGED` | 결재 후 payload_hash 불일치(무효화) |
| 409 | `AML.INVALID_STATE_TRANSITION` | case/report/approval 상태 전이 위반 |
| 422 | `AML.SCREENING_REQUIRES_REVIEW` | screening 장애 시 manual-review/fail-closed(§15.7, D-14) |
| 429 | `AML.RATE_LIMITED` | metering/quota 초과(§15.7) |
| 503 | `AML.IDEMPOTENCY_PROCESSING` | 동일 키 처리 중(`Retry-After`) |
| 503 | `AML.SCREENING_UNAVAILABLE` | WLF 엔진 장애(fail-closed 기본) |
| 409 | `AML.TENANT_DEPLOYMENT_MODEL_IMMUTABLE` | `deploymentModel` 직접 PUT 변경 시도(온보딩 흐름만 허용) |
| 404 | `AML.TENANT_NOT_FOUND` | 대상 tenant 없음(§5 OpenAPI paths·PRD 부록 D 정합) |
| 422 | `AML.ONBOARDING_PROVISION_NOT_APPLICABLE` | `MANAGED_DEDICATED`가 아닌 배포 모델에 provision 호출 |
| 422 | `AML.ONBOARDING_REGISTER_NOT_APPLICABLE` | `SELF_HOSTED`가 아닌 배포 모델에 register 호출 |
| 401 | `AML.INVALID_REGISTRATION_TOKEN` | self-hosted 등록 토큰 불일치 |
| 409 | `AML.ONBOARDING_INVALID_STATE_TRANSITION` | 온보딩 상태머신 허용되지 않는 전이 시도 |
| 500 | `AML.INTERNAL_ERROR` | 내부 오류 |

> screening 장애 정책(D-14): onboarding·수취인·출금주소 등록은 `422 AML.SCREENING_REQUIRES_REVIEW` 또는 `503 AML.SCREENING_UNAVAILABLE`로 fail-closed/manual-review 유도. batch TM ingest는 replay·reconciliation 전제로 지연 허용.

---

## 5. OpenAPI(YAML) 스니펫

```yaml
openapi: 3.1.0
info:
  title: AML Platform API (aml-svc)
  version: 1.0.0
  description: >
    SaaS AML Platform. Public(서비스)·Internal(엔진)·Admin(bo-api) 3-plane.
    raw PII 미노출(ref/hash), 4-eyes(maker≠checker), 멀티테넌시(tenant/data-scope).
servers:
  - url: https://api.aml.example.com
security:
  - ApiKeyHmac: []
  - OAuth2: []
  - Mtls: []
components:
  securitySchemes:
    ApiKeyHmac: { type: apiKey, in: header, name: X-Api-Key }
    OAuth2:
      type: oauth2
      flows:
        clientCredentials:
          tokenUrl: https://auth.aml.example.com/oauth/token
          scopes:
            aml:event:write: ingest events
            aml:screen:evaluate: real-time screening
            aml:ra:evaluate: risk assessment
            aml:tm:evaluate: transaction monitoring
            aml:case:read: read cases/alerts
            aml:case:update: update cases/decisions
            aml:evidence:export: evidence export
            aml:admin:watchlist: watchlist admin
            aml:admin:source-system: source admin
            aml:admin:policy: RA/TM policy admin
            aml:admin:approval: approval queue
            aml:admin:audit: audit query
            aml:pii:reveal: reveal raw PII (reason + RAW_DATA_ACCESS audit required)
    Mtls: { type: mutualTLS }
  parameters:
    TenantId: { name: Tenant-Id, in: header, required: true, schema: { type: string } }
    SourceSystem: { name: Source-System, in: header, required: true, schema: { type: string } }
    IdempotencyKey: { name: Idempotency-Key, in: header, required: true, schema: { type: string } }
    Signature: { name: X-Signature, in: header, required: true, schema: { type: string } }
    TraceId: { name: X-Trace-Id, in: header, required: false, schema: { type: string } }
  schemas:
    Error:
      type: object
      properties:
        error:
          type: object
          required: [code, message]
          properties:
            code: { type: string, example: AML.INVALID_SIGNATURE }
            message: { type: string }
            details: { type: array, items: { type: object } }
            traceId: { type: string }
    PageMeta:
      type: object
      properties:
        page: { type: integer }
        size: { type: integer }
        totalElements: { type: integer, format: int64 }
        totalPages: { type: integer }
        sort: { type: string }
    ScreenRequest:
      type: object
      required: [targetRef, targetType, subject]
      properties:
        targetRef: { type: string }
        targetType: { type: string, enum: [CUSTOMER, ENTITY, COUNTERPARTY, CRYPTO_ADDRESS] }
        sourceTypes:
          type: array
          items: { type: string, enum: [SANCTIONS, PEP, RCA, ADVERSE_MEDIA, INTERNAL, LAW_ENFORCEMENT, VASP_RISK] }
        subject:
          type: object
          properties:
            nameTokens: { type: array, items: { type: string } }
            dob: { type: string, format: date }
            country: { type: string }
            documentHash: { type: string }
            walletAddressHash: { type: string }
    ScreenResponse:
      type: object
      properties:
        screeningId: { type: string, format: uuid }
        status: { type: string, enum: [NO_MATCH, POSSIBLE_MATCH, TRUE_MATCH, FALSE_POSITIVE, AUTO_DISCOUNTED, ESCALATED] }
        score: { type: number }
        scoreBreakdown: { type: object }
        riskGrade: { type: string, enum: [LOW, MEDIUM, HIGH, PROHIBITED] }
        reasonCodes: { type: array, items: { type: string } }
        requiredActions: { type: array, items: { type: string } }
        matchedEntries: { type: array, items: { type: string } }
        matchedRules:
          type: array
          items: { $ref: '#/components/schemas/RuleRef' }
        ruleVersion: { type: string }
        expiresAt: { type: string, format: date-time }
    RuleRef:
      type: object
      properties:
        ruleCode: { type: string }
        threshold: { type: number }
    IngestEventResponse:
      type: object
      properties:
        eventId: { type: string }
        accepted: { type: boolean }
        idempotent: { type: boolean }
        traceId: { type: string }
    TransactionEvaluateResponse:
      type: object
      properties:
        evaluated: { type: boolean }
        alerts:
          type: array
          items:
            type: object
            properties:
              alertId: { type: string, format: uuid }
              alertType: { type: string, enum: [TM_SCENARIO, SCREENING, RA, FDS_ESCALATION, VENDOR_ALERT] }
              scenarioCode: { type: string, enum: [STRUCTURING, RAPID_MOVEMENT, MULE_NETWORK, HIGH_RISK_CORRIDOR, SHELL_MERCHANT, REFUND_LAUNDERING, TRADE_MISPRICING, ROUND_TRIPPING, CRYPTO_OFF_RAMP, INTERNAL_OVERRIDE_ABUSE] }
              severity: { type: string, enum: [LOW, MEDIUM, HIGH, CRITICAL] }
              status: { type: string }
              evidence: { type: object }
    ApprovalDecisionRequest:
      type: object
      required: [checkerId, decision]
      properties:
        checkerId: { type: string }
        decision: { type: string, enum: [APPROVE, REJECT] }
        reason: { type: string }
    ApprovalSubmittedResponse:
      type: object
      properties:
        approvalId: { type: string, format: uuid }
        status: { type: string, enum: [SUBMITTED] }
    CountryRiskChangeRequest:
      type: object
      required: [changes, reason, makerId]
      properties:
        changes:
          type: array
          items:
            type: object
            required: [country, riskBand]
            properties:
              country: { type: string }
              riskBand: { type: string, enum: [LOW, MEDIUM, HIGH, PROHIBITED] }
              basis: { type: array, items: { type: string } }
        reason: { type: string }
        makerId: { type: string }
    PolicyPackChangeRequest:
      type: object
      required: [policyPackCode, parameters, reason, makerId]
      properties:
        policyPackCode: { type: string, example: KR_DEFAULT }
        parameters: { type: object }
        effectiveFrom: { type: string, format: date-time }
        reason: { type: string }
        makerId: { type: string }
    DeploymentModel:
      type: string
      enum: [MANAGED_DEDICATED, SELF_HOSTED, SHARED]
      description: >
        배포 유형(구 isolation_mode 대체, aml_tenants.deployment_model).
        온보딩 프로비저닝으로 확정. bo-api 소유 /onboarding/** 에서만 변경.
        MANAGED_DEDICATED=매니지드 전용(IaC 자동) / SELF_HOSTED=자체 인프라 설치형 / SHARED=소규모 공유.
    OnboardingStatus:
      type: string
      enum: [REQUESTED, PROVISIONING, DEPLOYED, VERIFIED, ACTIVE, PACKAGE_ISSUED, CUSTOMER_DEPLOYED, REGISTERED]
      description: >
        온보딩 진행 상태(aml_tenants.onboarding_status).
        MANAGED_DEDICATED 경로: REQUESTED→PROVISIONING→DEPLOYED→VERIFIED→ACTIVE.
        SELF_HOSTED 경로: REQUESTED→PACKAGE_ISSUED→CUSTOMER_DEPLOYED→REGISTERED.
        SHARED 경로: REQUESTED→ACTIVE(즉시).
        ACTIVE/REGISTERED 도달 시 tenant status=ACTIVE.
    TenantDto:
      type: object
      description: >
        서비스(테넌트=서비스) 배포/온보딩 메타. bo-api 소유 서비스 레지스트리/온보딩
        (/api/v1/bo/aml/tenants/** + /onboarding/**)에서 노출.
        테넌트=서비스이며 상위 기관(institution)은 institutionRef(=aml_tenants.institution_ref)로 참조(1 기관 : N 서비스).
        aml-svc 엔진 API(§2)에는 미노출(소유 경계, §9). isolationMode 필드 폐기.
      required: [tenantId, displayName, deploymentModel, onboardingStatus, status]
      properties:
        tenantId: { type: string, maxLength: 64 }
        institutionRef: { type: string, maxLength: 64, nullable: true, description: '상위 기관(institution) 참조 (aml_tenants.institution_ref). 1 기관 : N 서비스(테넌트). additive·nullable' }
        displayName: { type: string, maxLength: 160 }
        deploymentModel: { $ref: '#/components/schemas/DeploymentModel' }
        onboardingStatus: { $ref: '#/components/schemas/OnboardingStatus' }
        status: { type: string, enum: [ONBOARDING, ACTIVE, SUSPENDED, OFFBOARDED], description: '운영 생명주기(onboarding_status와 직교). DB §5.28b 4종 정본(V20 갱신). 신규=ONBOARDING, 온보딩완료=ACTIVE, 정지=SUSPENDED, 해지완료=OFFBOARDED. 구 OFFBOARDING/DEFAULT=ACTIVE는 V20에서 폐기' }
        region: { type: string, example: KR, description: '기본 데이터 리전(aml_tenants.default_region)' }
        infraRef: { type: string, nullable: true, description: '배포 메타 참조. 매니지드=Terraform stack/workspace ID, self-hosted=라이선스·인스턴스 ID' }
        policyPackCode: { type: string, example: KR_DEFAULT }
        createdAt: { type: string, format: date-time }
        updatedAt: { type: string, format: date-time }
    TenantCreateRequest:
      type: object
      required: [tenantId, displayName, deploymentModel]
      properties:
        tenantId: { type: string, maxLength: 64, pattern: '^[a-z0-9\-]+$' }
        displayName: { type: string, maxLength: 160 }
        deploymentModel: { $ref: '#/components/schemas/DeploymentModel' }
        region: { type: string, default: KR }
        policyPackCode: { type: string, default: KR_DEFAULT }
    OnboardingProvisionRequest:
      type: object
      required: [requestedBy]
      properties:
        iacTemplate: { type: string, description: 'IaC 템플릿 버전(기본: 플랫폼 latest)' }
        targetRegion: { type: string, description: '배포 리전 override(기본: tenant region)' }
        requestedBy: { type: string }
    OnboardingRegisterRequest:
      type: object
      required: [instanceId, registrationToken]
      properties:
        instanceId: { type: string, description: '고객 설치 인스턴스 식별자(infra_ref 매핑)' }
        registrationToken: { type: string, description: '플랫폼 발급 등록 토큰(SELF_HOSTED 전용)' }
        callbackEndpoint: { type: string, format: uri, description: 'self-hosted 헬스 콜백 URL(선택)' }
    OnboardingStatusResponse:
      type: object
      properties:
        tenantId: { type: string }
        deploymentModel: { $ref: '#/components/schemas/DeploymentModel' }
        onboardingStatus: { $ref: '#/components/schemas/OnboardingStatus' }
        infraRef: { type: string, nullable: true }
        region: { type: string }
        history:
          type: array
          items:
            type: object
            properties:
              status: { $ref: '#/components/schemas/OnboardingStatus' }
              transitionedAt: { type: string, format: date-time }
              actor: { type: string }
              note: { type: string }
        nextExpectedStatus: { type: string, nullable: true }
    PeriodicReviewPolicyRequest:
      type: object
      required: [cadenceByGrade, reason, makerId]
      properties:
        cadenceByGrade:
          type: object
          properties:
            LOW: { type: integer, description: 재확인 주기(개월) }
            MEDIUM: { type: integer }
            HIGH: { type: integer }
            PROHIBITED: { type: integer }
        gracePeriodDays: { type: integer }
        reason: { type: string }
        makerId: { type: string }
    TravelRuleTransferDto:
      type: object
      properties:
        transferRef: { type: string }
        originatorRef: { type: string }
        beneficiaryRef: { type: string }
        assetCode: { type: string }
        chain: { type: string }
        walletAddressHash: { type: string }
        amount: { type: string }
        amountMinor: { type: integer, format: int64 }
        originatorVasp: { type: string }
        beneficiaryVasp: { type: string }
        completenessStatus: { type: string, enum: [COMPLETE, MISSING_ORIGINATOR, MISSING_BENEFICIARY, INCOMPLETE] }
        riskStatus: { type: string, enum: [CLEAR, SANCTIONED_ADDRESS, MIXER_EXPOSURE, HIGH_RISK] }
        exceptionReason: { type: string }
        createdAt: { type: string, format: date-time }
    EventCategory:
      type: string
      enum:
        - WATCHLIST_IMPORT
        - WLF_DECISION
        - FP_WHITELIST
        - RA_MODEL_CHANGE
        - RISK_OVERRIDE
        - TM_SCENARIO_CHANGE
        - CASE_APPROVAL
        - REPORT_LIFECYCLE
        - RAW_DATA_ACCESS
        - POLICY_CHANGE
      description: >
        aml_audit_events.event_category 허용값(10종, DB §3.15 enum 정본).
        GET /admin/aml/audit-events?eventCategory 파라미터 허용값과 동일.
    WatchlistEntryDto:
      type: object
      description: >
        명단 항목 조회 응답(GET /admin/aml/watchlist-entries).
        raw PII 미노출 — primaryNameHash(HMAC)·normalizedTokens만 노출.
      properties:
        entryId: { type: string, format: uuid }
        sourceCode: { type: string }
        listType: { type: string, enum: [SANCTIONS, PEP, RCA, ADVERSE_MEDIA, INTERNAL, LAW_ENFORCEMENT, VASP_RISK] }
        subjectKind: { type: string, enum: [PERSON, ENTITY, VESSEL, CRYPTO_ADDRESS] }
        primaryNameHash: { type: string, description: '이름 HMAC(원문 미노출)' }
        normalizedTokens: { type: array, items: { type: string } }
        version: { type: string }
        status: { type: string, enum: [ACTIVE, DELISTED] }
        createdAt: { type: string, format: date-time }
    CustomerProfileDto:
      type: object
      description: >
        고객 CDD/EDD/RA/WLF 통합 프로필 evidence
        (GET /evidence/aml/customers/{customerRef}/profile).
        raw PII 미노출 — *Hash/token/Ref만 노출. PII 원문 접근은
        aml:pii:reveal scope + RAW_DATA_ACCESS 감사 필요(§1.6).
      properties:
        customerRef: { type: string }
        customerType: { type: string, enum: [PERSON, SOLE_PROPRIETOR, LEGAL_ENTITY, MERCHANT, SELLER, VASP_CUSTOMER, EMPLOYEE, VENDOR] }
        kycStatus: { type: string, enum: [PENDING, VERIFIED, INCOMPLETE, EXPIRED, REJECTED] }
        riskGrade: { type: string, enum: [LOW, MEDIUM, HIGH, PROHIBITED] }
        nameHash: { type: string, nullable: true, description: '이름 HMAC(마스킹)' }
        docHash: { type: string, nullable: true, description: '신분증번호 HMAC(마스킹)' }
        kycEvidence: { type: object, description: 'KYC checklist 상태(JSONB, 원문 아님)' }
        nextReviewDueAt: { type: string, format: date-time, nullable: true }
        latestScreening:
          type: object
          nullable: true
          properties:
            screeningId: { type: string, format: uuid }
            status: { type: string }
            riskGrade: { type: string }
        latestRiskScore:
          type: object
          nullable: true
          properties:
            scoreId: { type: string, format: uuid }
            riskScore: { type: number }
            riskGrade: { type: string }
            evaluatedAt: { type: string, format: date-time }
        createdAt: { type: string, format: date-time }
    SimulationResponse:
      type: object
      properties:
        simulationId: { type: string, format: uuid }
        modelVersion: { type: string }
        scenarioVersion: { type: string }
        samplePopulation:
          type: object
          properties:
            definition: { type: string }
            sampleSize: { type: integer }
            periodFrom: { type: string, format: date-time }
            periodTo: { type: string, format: date-time }
        gradeShift:
          type: object
          properties:
            LOW: { type: integer }
            MEDIUM: { type: integer }
            HIGH: { type: integer }
            PROHIBITED: { type: integer }
        falsePositiveImpact:
          type: object
          properties:
            deltaPercent: { type: number }
            baseline: { type: number }
            projected: { type: number }
        evaluatedAt: { type: string, format: date-time }
paths:
  /api/v1/aml/screen:
    post:
      summary: 실시간 WLF/제재/PEP screening
      operationId: screenSubject
      security: [ { ApiKeyHmac: [], OAuth2: [aml:screen:evaluate] } ]
      parameters:
        - $ref: '#/components/parameters/TenantId'
        - $ref: '#/components/parameters/SourceSystem'
        - $ref: '#/components/parameters/IdempotencyKey'
        - $ref: '#/components/parameters/Signature'
        - $ref: '#/components/parameters/TraceId'
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/ScreenRequest' }
      responses:
        '200':
          description: screening 결과
          content:
            application/json:
              schema:
                type: object
                properties:
                  data: { $ref: '#/components/schemas/ScreenResponse' }
        '409': { description: 멱등 충돌, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
        '422': { description: manual-review/fail-closed, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
        '503': { description: WLF 엔진 장애(fail-closed), content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
  /api/v1/admin/aml/screenings/{screeningId}/decision:
    post:
      summary: WLF 판정 (TRUE_MATCH/FALSE_POSITIVE는 4-eyes)
      operationId: decideScreening
      security: [ { OAuth2: [aml:case:update] } ]
      parameters:
        - $ref: '#/components/parameters/TenantId'
        - name: screeningId
          in: path
          required: true
          schema: { type: string, format: uuid }
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [status, makerId]
              properties:
                status: { type: string, enum: [TRUE_MATCH, FALSE_POSITIVE, AUTO_DISCOUNTED, ESCALATED] }
                makerId: { type: string }
                reason: { type: string }
      responses:
        '202':
          description: 4-eyes 결재 상신됨(approvalId 반환)
          content:
            application/json:
              schema:
                type: object
                properties:
                  data:
                    type: object
                    properties:
                      approvalId: { type: string, format: uuid }
                      status: { type: string, enum: [SUBMITTED] }
        '409': { description: 상태 전이/자기승인 위반, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
  /api/v1/admin/aml/approvals/{approvalId}:approve:
    post:
      summary: 결재 승인 (maker≠checker 강제)
      operationId: approveApproval
      security: [ { OAuth2: [aml:admin:approval] } ]
      parameters:
        - $ref: '#/components/parameters/TenantId'
        - name: approvalId
          in: path
          required: true
          schema: { type: string, format: uuid }
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/ApprovalDecisionRequest' }
      responses:
        '200': { description: 승인/반려 처리 }
        '409':
          description: AML.SELF_APPROVAL_FORBIDDEN / AML.APPROVAL_PAYLOAD_CHANGED
          content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } }
  /api/v1/admin/aml/country-risk:change:
    post:
      summary: 국가위험 변경 상신 (4-eyes, subjectType=COUNTRY_RISK)
      operationId: changeCountryRisk
      security: [ { OAuth2: [aml:admin:policy] } ]
      parameters:
        - $ref: '#/components/parameters/TenantId'
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/CountryRiskChangeRequest' }
      responses:
        '202':
          description: 4-eyes 결재 상신됨(approvalId 반환, subjectType=COUNTRY_RISK)
          content:
            application/json:
              schema:
                type: object
                properties:
                  data: { $ref: '#/components/schemas/ApprovalSubmittedResponse' }
        '403': { description: AML.FORBIDDEN_SCOPE, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
  /api/v1/admin/aml/policy-packs:change:
    post:
      summary: tenant policy pack 변경 상신 (4-eyes, subjectType=POLICY_PACK)
      operationId: changePolicyPack
      security: [ { OAuth2: [aml:admin:policy] } ]
      parameters:
        - $ref: '#/components/parameters/TenantId'
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/PolicyPackChangeRequest' }
      responses:
        '202':
          description: 4-eyes 결재 상신됨(approvalId 반환, subjectType=POLICY_PACK)
          content:
            application/json:
              schema:
                type: object
                properties:
                  data: { $ref: '#/components/schemas/ApprovalSubmittedResponse' }
  /api/v1/admin/aml/cdd/periodic-review-policy:
    put:
      summary: periodic review 주기 설정 변경 (4-eyes)
      operationId: setPeriodicReviewPolicy
      security: [ { OAuth2: [aml:admin:policy] } ]
      parameters:
        - $ref: '#/components/parameters/TenantId'
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/PeriodicReviewPolicyRequest' }
      responses:
        '202':
          description: 4-eyes 결재 상신됨(approvalId 반환)
          content:
            application/json:
              schema:
                type: object
                properties:
                  data: { $ref: '#/components/schemas/ApprovalSubmittedResponse' }
  /api/v1/admin/aml/travel-rule/transfers:
    get:
      summary: Travel Rule exception 큐 조회 (riskStatus 4종·completenessStatus 4종 필터)
      operationId: listTravelRuleTransfers
      security: [ { OAuth2: [aml:case:read] } ]
      parameters:
        - $ref: '#/components/parameters/TenantId'
        - { name: riskStatus, in: query, required: false, schema: { type: string, enum: [CLEAR, SANCTIONED_ADDRESS, MIXER_EXPOSURE, HIGH_RISK] } }
        - { name: completenessStatus, in: query, required: false, schema: { type: string, enum: [COMPLETE, MISSING_ORIGINATOR, MISSING_BENEFICIARY, INCOMPLETE] } }
        - { name: from, in: query, required: false, schema: { type: string, format: date-time } }
        - { name: to, in: query, required: false, schema: { type: string, format: date-time } }
        - { name: page, in: query, required: false, schema: { type: integer } }
        - { name: size, in: query, required: false, schema: { type: integer } }
      responses:
        '200':
          description: exception 큐 목록
          content:
            application/json:
              schema:
                type: object
                properties:
                  data: { type: array, items: { $ref: '#/components/schemas/TravelRuleTransferDto' } }
                  page: { $ref: '#/components/schemas/PageMeta' }
  /api/v1/admin/aml/ra-models/{modelCode}/simulate:
    post:
      summary: RA 모델 sample population simulation (분석 설정, 결재 불필요)
      operationId: simulateRaModel
      security: [ { OAuth2: [aml:admin:policy] } ]
      parameters:
        - $ref: '#/components/parameters/TenantId'
        - { name: modelCode, in: path, required: true, schema: { type: string } }
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                samplePopulation: { type: object }
                modelVersion: { type: string }
      responses:
        '200':
          description: 시뮬레이션 결과(등급 이동·오탐 영향)
          content:
            application/json:
              schema:
                type: object
                properties:
                  data: { $ref: '#/components/schemas/SimulationResponse' }
  # ── bo-api 소유 서비스 관리·온보딩 엔드포인트 (§9·§3.16) ─────────────────────────────
  # 아래 경로는 bo-api가 소유·집약·인증하는 엔드포인트다. aml-svc 엔진이 아닌 bo-api가 구현하며,
  # aml-svc는 bo-api 온보딩 워크플로우의 위임 호출로 aml_tenants 갱신을 수신한다.
  /api/v1/bo/aml/tenants:
    get:
      summary: 서비스 목록 조회 (bo-api 소유)
      operationId: listAmlTenants
      security: [ { OAuth2: [aml:admin:policy] } ]
      parameters:
        - { name: deploymentModel, in: query, required: false, schema: { $ref: '#/components/schemas/DeploymentModel' } }
        - { name: onboardingStatus, in: query, required: false, schema: { $ref: '#/components/schemas/OnboardingStatus' } }
        - { name: status, in: query, required: false, schema: { type: string, enum: [ONBOARDING, ACTIVE, SUSPENDED, OFFBOARDED] } }
        - { name: region, in: query, required: false, schema: { type: string, example: KR }, description: '배포 리전 필터(aml_tenants.default_region 기준)' }
        - { name: page, in: query, required: false, schema: { type: integer } }
        - { name: size, in: query, required: false, schema: { type: integer } }
      responses:
        '200':
          description: 서비스 목록
          content:
            application/json:
              schema:
                type: object
                properties:
                  data: { type: array, items: { $ref: '#/components/schemas/TenantDto' } }
                  page: { $ref: '#/components/schemas/PageMeta' }
    post:
      summary: 서비스 등록 — 배포 유형 선택 + 온보딩 신청 (bo-api 소유)
      operationId: createAmlTenant
      security: [ { OAuth2: [aml:admin:policy] } ]
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/TenantCreateRequest' }
      responses:
        '201':
          description: 서비스 등록 완료. onboarding_status=REQUESTED로 시작.
          content:
            application/json:
              schema:
                type: object
                properties:
                  data: { $ref: '#/components/schemas/TenantDto' }
        '409': { description: tenantId 중복, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
  /api/v1/bo/aml/tenants/{tenantId}:
    get:
      summary: 서비스 상세 조회 (bo-api 소유)
      operationId: getAmlTenant
      security: [ { OAuth2: [aml:admin:policy] } ]
      parameters:
        - { name: tenantId, in: path, required: true, schema: { type: string } }
      responses:
        '200':
          description: 서비스 상세(deploymentModel·onboardingStatus·infraRef 포함)
          content:
            application/json:
              schema:
                type: object
                properties:
                  data: { $ref: '#/components/schemas/TenantDto' }
        '404': { description: AML.TENANT_NOT_FOUND, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
    put:
      summary: 서비스 설정 변경 (bo-api 소유, deploymentModel 불변)
      operationId: updateAmlTenant
      security: [ { OAuth2: [aml:admin:policy] } ]
      parameters:
        - { name: tenantId, in: path, required: true, schema: { type: string } }
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                displayName: { type: string }
                status: { type: string, enum: [ONBOARDING, ACTIVE, SUSPENDED, OFFBOARDED] }
                policyPackCode: { type: string }
      responses:
        '200':
          description: 설정 변경 완료
          content:
            application/json:
              schema:
                type: object
                properties:
                  data: { $ref: '#/components/schemas/TenantDto' }
        '409': { description: AML.TENANT_DEPLOYMENT_MODEL_IMMUTABLE, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
  /api/v1/bo/aml/tenants/{tenantId}/onboarding/provision:
    post:
      summary: 매니지드 IaC 파이프라인 트리거 (bo-api 소유, MANAGED_DEDICATED 전용)
      operationId: provisionAmlTenantOnboarding
      security: [ { OAuth2: [aml:admin:policy] } ]
      parameters:
        - { name: tenantId, in: path, required: true, schema: { type: string } }
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/OnboardingProvisionRequest' }
      responses:
        '202':
          description: IaC 파이프라인 트리거 완료. onboarding_status=PROVISIONING으로 전이.
          content:
            application/json:
              schema:
                type: object
                properties:
                  data:
                    type: object
                    properties:
                      tenantId: { type: string }
                      onboardingStatus: { type: string, enum: [PROVISIONING] }
                      infraRef: { type: string, nullable: true }
                      requestedAt: { type: string, format: date-time }
        '422': { description: AML.ONBOARDING_PROVISION_NOT_APPLICABLE (MANAGED_DEDICATED 아닌 경우), content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
        '409': { description: AML.ONBOARDING_INVALID_STATE_TRANSITION, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
  /api/v1/bo/aml/tenants/{tenantId}/onboarding/register:
    post:
      summary: self-hosted 인스턴스 등록 콜백 (bo-api 소유, SELF_HOSTED 전용)
      operationId: registerAmlTenantOnboarding
      security: [ { OAuth2: [aml:admin:policy] } ]
      parameters:
        - { name: tenantId, in: path, required: true, schema: { type: string } }
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/OnboardingRegisterRequest' }
      responses:
        '200':
          description: self-hosted 등록 완료. onboarding_status=REGISTERED, infra_ref=instanceId로 갱신.
          content:
            application/json:
              schema:
                type: object
                properties:
                  data:
                    type: object
                    properties:
                      tenantId: { type: string }
                      onboardingStatus: { type: string, enum: [REGISTERED] }
                      infraRef: { type: string }
        '401': { description: AML.INVALID_REGISTRATION_TOKEN, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
        '422': { description: AML.ONBOARDING_REGISTER_NOT_APPLICABLE (SELF_HOSTED 아닌 경우), content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
  /api/v1/bo/aml/tenants/{tenantId}/onboarding:
    get:
      summary: 온보딩 상태·단계 이력·infra_ref 조회 (bo-api 소유)
      operationId: getAmlTenantOnboardingStatus
      security: [ { OAuth2: [aml:admin:policy] } ]
      parameters:
        - { name: tenantId, in: path, required: true, schema: { type: string } }
      responses:
        '200':
          description: 온보딩 현황(deploymentModel·onboardingStatus·infraRef·이력)
          content:
            application/json:
              schema:
                type: object
                properties:
                  data: { $ref: '#/components/schemas/OnboardingStatusResponse' }
        '404': { description: AML.TENANT_NOT_FOUND, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
```

---

## 6. BO 화면(PRD) ↔ API 정합

> bo-web 화면(설계서 §20.2 운영 화면)은 bo-api 경유로 아래 aml-svc Admin API를 사용한다.
> **운영자 집계 화면(대시보드/서비스 관리/감사 집계)은 본 엔진 API가 아니라 bo-api 소유 API(`/api/v1/bo/aml/**`)를 호출한다(§9).** 아래 표는 bo-api가 위임 호출하는 aml-svc 저수준 Admin API다.

| BO 화면(PRD 후보) | 호출 API(aml-svc admin / bo-api 소유) |
|---|---|
| **서비스 관리** (목록·상세·배포유형·온보딩상태) | bo-api `GET/POST /api/v1/bo/aml/tenants`, `GET/PUT /api/v1/bo/aml/tenants/{tenantId}` (§9, §3.16). 화면에 '격리 방식' 라디오 **없음** — `deploymentModel` + `onboardingStatus` 읽기 전용 표시 |
| **서비스 등록(배포 유형+온보딩 신청)** | bo-api `POST /api/v1/bo/aml/tenants` (§3.16 `TenantCreateRequest`, deploymentModel 선택 = 온보딩 신청) |
| **온보딩 상태** 화면 (프로비저닝 트리거·self-hosted 등록·이력) | bo-api `POST .../onboarding/provision`(매니지드 IaC 트리거), `GET .../onboarding`(상태·이력 조회), `POST .../onboarding/register`(self-hosted 등록 콜백) (§9, §3.16) |
| WLF 처리량 / 검토 큐 | `GET /admin/aml/screenings?status=POSSIBLE_MATCH`, `POST .../{id}/decision`(🔒) |
| watchlist freshness / import 승인 | `GET/POST /admin/aml/watchlist-sources`, `.../imports/{ver}:apply`(🔒) |
| RA score distribution / high-risk 현황 / 시뮬레이션 | (집계 화면) bo-api `GET /api/v1/bo/aml/dashboard`(§9); (엔진 모니터링) **`GET /api/v1/admin/aml/risk-scores`(목록·`riskGrade`/`modelVersion` 필터)·`GET .../risk-scores/distribution`(등급 분포) — 구현됨**(§2.7); (엔진 저수준) `GET /admin/aml/ra-models`, `GET /aml/customers/{ref}/risk`, `POST .../ra-models/{code}/simulate`(응답 `SimulationResponse` §3.15) |
| CDD/EDD checklist / periodic review 정책 | `GET/POST .../cdd/checklists`, `PUT .../cdd/checklists/{id}`(🔒), `PUT .../cdd/periodic-review-policy`(🔒) |
| country risk / policy pack 관리 | `GET .../country-risk`, `POST .../country-risk:change`(🔒 COUNTRY_RISK), `POST .../policy-packs:change`(🔒 POLICY_PACK) |
| RA 모델 활성화 / 등급 override | `.../ra-models/.../activate`(🔒), `.../risk-scores/{id}/override`(🔒) |
| TM alert backlog / scenario 관리 | `GET /aml/alerts/{id}`, `.../tm-scenarios/{code}:activate`(🔒) |
| case SLA / CDD·EDD 처리 | `GET /admin/aml/cdd/cases`, `PATCH .../{id}`, `.../{id}:close`(🔒) |
| STR/CTR 후보 현황 / 제출 | `GET /admin/aml/reports`, `.../{id}:submit`(🔒), `.../{id}:reject`(🔒), `.../{id}:cancel`(🔒) |
| Travel Rule exception | `GET .../travel-rule/transfers`, `.../{ref}:resolve-exception`(🔒) |
| 결재 대기함 | `GET /admin/aml/approvals?status=SUBMITTED`, `:approve`/`:reject` |
| audit export | `GET /admin/aml/audit-events`, `POST /evidence/aml/exports` |

---

## 7. 정본·상위 문서 동기화 확인

| 정본/상위 요건 | 본 API 반영 |
|---|---|
| 4서비스·bo-web→bo-api만 | Admin API는 bo-api 전용 계약, bo-web 직접 호출 금지 명시(§0) |
| 엔진 직접호출 금지 | Internal API는 fds-svc·mesh만(인증 = API key + HMAC, `AmlIngestAuthenticationFilter`; 호출자 식별 `X-Internal-Service` 선택; mesh mTLS 는 P8 보강) (§2.6, T11/AML-ENG-05) |
| 멀티테넌시 tenant/workspace/data-scope | `Tenant-Id`/`dataScope`/RLS, 전 엔드포인트 강제(§1.1) |
| raw PII 미노출(마스킹) | DTO에 `*Ref`/`*Hash`만, secretRef 마스킹, PII reveal 별도 scope+감사(§1.6, §3) |
| 4-eyes(작성자≠승인자) | 🔒 표기 + `aml_approvals` maker≠checker + 결재 흐름(§1.5, §3.7) + 트리거 등재표(§10, 설계서 §13.4 대상 ↔ subjectType 1:1) |
| 정책 자율운영(§2.6: checklist·periodic review·country risk·policy pack) | admin 정책 엔드포인트 §2.7(CDD/EDD checklist·periodic-review-policy·country-risk·policy-packs) 신설, 변경은 🔒4-eyes(§10) |
| Policy Pack STR/CTR/Travel Rule | reports/travel-rule 엔드포인트·report_type enum(§2.7, §3.6) |
| 표준 에러·페이지네이션·멱등·버저닝 | §1.2~§1.4, §4(HTTP 상태코드 정본) |
| DB 명칭(테이블·컬럼·enum) | 식별자·enum 모두 DB §3/§5와 1:1(각 표 DB 열·각주). `payload_hash` NOT NULL — **서버 자동계산(2026-06-08)으로 §3.1 `payloadHash` optional 전환**(미제공 시 ingest 어댑터 sha256 자동 INSERT). `CaseDto.originFdsCaseRef`·`RegulatoryReportDto.approvalId`·`ScreenResponse.targetRef/targetType/decidedBy/decidedAt` DB 컬럼 1:1 추가. `WatchlistEntryDto`·`CustomerProfileDto` 신설(DB §3.7·§3.3·§3.4 정합). `subjectType` enum 16종 확정(CHECKLIST_CHANGE·PERIODIC_REVIEW_CHANGE 추가, DB §5.16 동기화 대상). `EventCategory` 10종 OpenAPI schema 신설. |
| Webhook 콜백(outbound) | §8(3종·envelope·`X-Signature` HMAC·재시도/멱등) — 설계서 §15.7 'Webhook API' 정본 |
| 운영자 집계 = bo-api 소유 | 대시보드/서비스/감사 집계는 bo-api(`/api/v1/bo/aml/**`), 엔진 API §2에 미추가(§0·§9) |
| 배포 모델/온보딩(deployment topology) = bo-api 소유, aml-svc 엔진 API 미추가 | 서비스(테넌트=서비스) 등록은 격리 토글이 아니라 **배포 유형 선택 + 온보딩 신청/상태**다. enum `DeploymentModel{MANAGED_DEDICATED, SELF_HOSTED, SHARED}`(3종) · `OnboardingStatus{REQUESTED, PROVISIONING, DEPLOYED, VERIFIED, ACTIVE, PACKAGE_ISSUED, CUSTOMER_DEPLOYED, REGISTERED}`(8종, §5 OpenAPI)는 DB `aml_tenants.deployment_model`/`onboarding_status` 정본과 1:1(§3.16·§5). `TenantDto`는 `tenantId`/`deploymentModel`/`onboardingStatus`/`region`(=`default_region`)/`infraRef`(=`infra_ref`) — **`isolationMode` 필드 폐기**. 온보딩 엔드포인트(bo-api 전용): `POST /api/v1/bo/aml/tenants/{tenantId}/onboarding/provision`(프로비저닝 트리거), `GET /api/v1/bo/aml/tenants/{tenantId}/onboarding`(상태 조회), `POST /api/v1/bo/aml/tenants/{tenantId}/onboarding/register`(self-hosted 등록 콜백). 상태머신: 매니지드 `REQUESTED→PROVISIONING→DEPLOYED→VERIFIED→ACTIVE` / self-hosted `REQUESTED→PACKAGE_ISSUED→CUSTOMER_DEPLOYED→REGISTERED` / SHARED `REQUESTED→ACTIVE`. tenant_id 라우팅: 전용 배포는 배포=서비스 단일, SHARED만 `Tenant-Id` 헤더 행 라우팅(§9·§1.1). |
| OpenAPI 스니펫 | §5(`RuleRef`/`matchedRules`/`TransactionEvaluateResponse.scenarioCode`/`IngestEventResponse`·`DeploymentModel`/`OnboardingStatus`/`TenantDto`/`OnboardingProvisionRequest`/`OnboardingRegisterRequest`/`OnboardingStatusResponse` 포함) |

---

## 8. Webhook 콜백 계약 (outbound)

설계서 §15.7 'Webhook API(screening/case/report callback)'를 정본으로 확정한다. aml-svc(엔진)는 screening·case·report 상태 변경 이벤트를 서비스 등록 URL로 **outbound HTTP POST** 발행한다(`aml_source_systems`의 webhook 설정·`secret_ref` 사용, source secret 회전은 `POST /admin/aml/source-systems`🔒). bo-web/bo-api 운영자 화면과 무관한 **서비스 서버 간 콜백** 채널이며, 연동 명세(02-aml-integration §3.4 `webhook.callback.requested`)의 아웃박스 dispatch가 본 계약을 발행한다.

### 8.1 이벤트 타입 (`eventName`)
| eventName | 트리거 | 발행 주체(엔진) | 핵심 payload(camelCase, raw PII 미포함) |
|---|---|---|---|
| `AmlScreeningResolved` | WLF 판정 확정(TRUE_MATCH/FALSE_POSITIVE 등 결재 EXECUTED) | Screening | `screeningId`,`targetRef`,`status`(§5.5),`watchlistSourceType`,`reasonCodes`[] |
| `AmlCaseStatusChanged` | case 상태 전이 | Case Mgmt | `caseId`,`caseType`(§5.8),`fromStatus`,`toStatus`(§5.9),`closeReason`(nullable) |
| `AmlReportSubmitted` | STR/CTR/Travel Rule 제출·FIU 회신 결과 | Reporting | `reportId`,`reportType`(§5.10),`status`(§5.11: SUBMITTED/ACKNOWLEDGED/SUBMISSION_FAILED/REJECTED — FIU 회신 폐루프, 설계서 §14.1a),`submittedRef`(nullable),`fiuAckRef`(nullable),`submissionErrorCode`(nullable) |

> 3종은 정본 콜백 집합. enum 코드값은 DB §5와 동일. payload는 token/hash·마스킹만(원문 미포함).

### 8.2 공통 envelope
```json
{
  "schemaVersion": "aml.webhook.v1",
  "eventFamily": "screening",
  "eventName": "AmlScreeningResolved",
  "eventId": "evt_9a21...",
  "tenantId": "...", "dataScope": "default",
  "occurredAt": "2026-06-06T01:02:03Z",
  "traceId": "9a21...",
  "data": { /* §8.1 핵심 payload */ }
}
```
- 모든 키 **camelCase** 직렬화. `eventFamily`는 `eventName` 접두(screening/case/report)에서 도출.

### 8.3 서명·검증
- 헤더 `X-Signature: hmac-sha256=<hex>` = HMAC-SHA256(secret, `timestamp + "." + rawBody`). 헤더 `X-Webhook-Timestamp`(epoch ms) 동봉, 수신 측 ±5분 허용으로 replay 방어.
- secret은 source의 `secret_ref` 대조 원본(평문 1회 발급, 회전 시 무중단 위해 dual-secret 검증 기간 허용). 설계서 §15.7 'Webhook signature' 정합.

### 8.4 재시도·멱등
- 2xx 미수신 시 지수 backoff 재시도(예: 0s/30s/2m/10m/1h, 최대 24h). 최종 실패는 DLQ + 운영자 알림(연동 §3.4 아웃박스 status=FAILED).
- `eventId`로 **at-least-once** 보장 — 수신 측은 `eventId` 기준 멱등 처리. 동일 이벤트 재전송 시 `eventId`·payload 불변.

---

## 9. 서비스 경계 주의 (운영자 집계 = bo-api 소유)

- **운영자 집계 API 소유 경계(정본 결정).** **대시보드(플랫폼·서비스별)·서비스 관리(목록/상세/등록/설정)·운영자 감사 조회는 bo-api가 소유·집약·인증**한다. aml-svc/fds-svc는 **저수준 데이터 API만** 제공한다. 따라서 본 엔진 API 명세(§2)에는 운영자 집계 엔드포인트(대시보드/서비스/감사)를 **추가하지 않는다**. PRD/PPT의 해당 화면은 호출 대상을 bo-api(`/api/v1/bo/aml/**`)로 명시한다.
- **운영자 화면 ↔ bo-api 소유 API(엔진 API 아님).** 아래 경로(`/api/v1/bo/aml/**`)는 bo-api API 명세에서 확정한다. PRD/PPT는 호출 대상을 **bo-api**로 명시하고, `GET /api/v1/admin/aml/dashboard|tenants` 같은 엔진 직접 집계 경로 표기는 신설하지 않는다.

| BO 운영자 화면(PRD) | 호출 API(**bo-api 소유**) | 집약 데이터 출처(aml-svc 저수준) |
|---|---|---|
| 플랫폼 AML 대시보드 | `GET /api/v1/bo/aml/dashboard` | `GET /admin/aml/screenings`, `GET /admin/aml/cdd/cases`, `GET /admin/aml/reports` 집계 |
| 서비스별 AML 대시보드 | `GET /api/v1/bo/aml/tenants/{tenantId}/dashboard` | 동일 + `Tenant-Id` 위임 필터 |
| CDD/RA 파이프라인 집계 | `GET /api/v1/bo/aml/ra/pipeline-stats?histogramDays=` | 엔진 `GET /admin/aml/customers/pipeline-stats` 위임(`CddRaPipeline`, §3.3c). 비-prod stub·prod fail-closed(503 `AML.ENGINE_UNAVAILABLE`) |
| 서비스 목록/상세/등록(배포유형) | `GET/POST /api/v1/bo/aml/tenants`, `GET/PUT .../tenants/{tenantId}` | bo-api 서비스 레지스트리(`deployment_model`/`onboarding_status`/`policy_pack_code`/`status`/`region`/`infraRef`) |
| 온보딩 프로비저닝 트리거(매니지드 IaC) | `POST /api/v1/bo/aml/tenants/{tenantId}/onboarding/provision` | bo-api 온보딩 워크플로우(`onboarding_status` 전이 → `aml_tenants` 갱신 트리거) |
| 온보딩 상태 조회(읽기) | `GET /api/v1/bo/aml/tenants/{tenantId}/onboarding` | bo-api 온보딩 상태(`deployment_model`/`onboarding_status`/`infra_ref`·이력) |
| self-hosted 인스턴스 등록 콜백 | `POST /api/v1/bo/aml/tenants/{tenantId}/onboarding/register` | bo-api 등록 수신(self-hosted 인스턴스 → `onboarding_status=REGISTERED`) |
| 운영자 감사 화면 | `GET /api/v1/bo/aml/audit?eventCategory&actor&from&to` | bo-api 감사 집약(+ aml-svc `GET /admin/aml/audit-events` 저수준 위임) |

- **운영자 IAM·승인 라인 정책**: bo-api 소유. aml-svc는 엔진 측 결재 게이트(`aml_approvals`)와 엔진 append-only 감사(`aml_audit_events`)만 보유한다.

> **RA 점수 목록/분포(`GET /admin/aml/risk-scores`) — 구현 정합.** 엔진 모니터링 엔드포인트 **`GET /api/v1/admin/aml/risk-scores`(목록·`riskGrade`/`modelVersion`/`page`/`size` 필터)·`GET .../risk-scores/distribution`(`RiskDistributionResponse`)는 구현되어 있다**(`RiskScoreAdminController`, scope `aml:case:read`, §2.7). 운영자 대시보드 집계(`/api/v1/bo/aml/dashboard`)는 bo-api가 별도 소유·집약하며, 엔진 모니터링 목록/분포와 공존한다(구 "미신설" 단언 폐기). PRD AML-RA-001·태스크 §5는 이에 맞춰 정정한다.

> **PRD `aml:api-prd` 높음 이격 정정(§9 정본 경계 확정).** 아래 3건은 PRD/PPT가 수정해야 할 API 경로·파라미터 오기이며, aml-svc 엔진 API(§2)에는 추가하지 않는다(bo-api 소유 경계).
> - **AML-TNT-002 ④ `GET .../tenants/{tenantId}/policy-pack` 경로 오기** — 본 API에 해당 경로 없음. 정본은 **`POST /api/v1/admin/aml/policy-packs:change`**(4-eyes, §2.7)이다. PRD §13.2 ④항을 `POST /api/v1/bo/aml/tenants/{tenantId}` PUT 설정 변경 + `POST .../policy-packs:change`(4-eyes 상신)으로 재기술해야 한다.
> - **AML-TNT-002 ③ `source-systems?tenantId=` 쿼리 파라미터 오기** — `GET /api/v1/admin/aml/source-systems`는 테넌시를 `Tenant-Id` **헤더**로 처리한다(§1.1). `tenantId` 쿼리 파라미터는 정의된 적 없다. PRD §13.2 ③항에서 `?tenantId=…` 표기를 제거하고 `Tenant-Id: <tenantId>` 헤더 방식으로 수정해야 한다.
> - **AML-TNT-002 ③④ GET/POST 혼용 오기** — `policy-packs:change`는 POST 전용(결재 상신 트리거). PRD에서 GET/POST 혼용 표기를 `POST /api/v1/admin/aml/policy-packs:change`로 단일화해야 한다.

> **bo-api 위임 관계(정본 §3·§4).** 본 §2.7 admin 정책 엔드포인트(CDD/EDD checklist·periodic review·country risk·policy pack 포함)는 **bo-api가 운영자 화면을 대신해 위임 호출(delegating call)** 하는 aml-svc 계약이며, bo-web은 bo-api 경유로만 접근한다(엔진 직접호출 금지). 즉 `bo-web → bo-api(REST) → aml-svc /api/v1/admin/aml/**`.

> **서비스 등록 = 배포 유형 선택 + 온보딩 신청/상태(격리 토글 아님, 정본 target-architecture §4.1)**: 서비스(테넌트=서비스) 등록은 '격리 방식(DB 분리/스키마 분리/공유) 라디오' 즉석 선택이 아니라 **배포 유형(`deployment_model`: `MANAGED_DEDICATED`/`SELF_HOSTED`/`SHARED`) 선택 + 온보딩 신청(`onboarding_status` 상태머신)** 흐름이다. 온보딩 프로비저닝 트리거·상태 조회·self-hosted 등록 콜백은 **bo-api 전용 `/onboarding/**`** 경로로만 노출하며, **본 aml-svc 엔진 API(§2)에는 온보딩 엔드포인트를 추가하지 않는다**(소유 경계). aml-svc는 `aml_tenants`의 `deployment_model`/`onboarding_status`/`default_region`/`infra_ref`를 스키마로 보유하되 운영 변경은 bo-api 온보딩 워크플로우가 트리거한다. tenant_id 라우팅 의미: 전용 배포(`MANAGED_DEDICATED`/`SELF_HOSTED`)는 **배포=서비스 단일**(라우팅은 배포 엔드포인트 단위, 서비스 간 격리는 배포 경계가 보장), `SHARED`만 `Tenant-Id` 헤더 행 라우팅(integration 명세 확정).

---

## 10. 4-eyes 결재 트리거 등재표 (🔒 엔드포인트 ↔ subjectType)

설계서 §13.4 4-eyes 대상 + §3.7 `subjectType` enum(전수)을 각 🔒 엔드포인트에 1:1로 등재한다. 모든 🔒 엔드포인트는 `① 상신(maker) → 202 + approvalId(SUBMITTED) → ② 승인(checker, maker≠checker) → ③ 실행(EXECUTED)` 흐름을 따르며 `payload_hash` 고정(§1.5).

| 🔒 엔드포인트 | subjectType(§3.7) | 설계서 §13.4 대상 | scope |
|---|---|---|---|
| `POST .../watchlist-sources/{code}/imports/{ver}:apply` | `WATCHLIST_IMPORT` | 명단 source import 적용 | `aml:admin:watchlist` |
| `POST .../screenings/{id}/decision`(TRUE_MATCH/FP) | `WLF_DECISION` | WLF true match 확정 | `aml:case:update` |
| `POST .../screenings/fp-whitelist` | `FP_WHITELIST` | false positive whitelist 등록 | `aml:admin:watchlist` |
| `POST .../ra-models/{modelCode}/versions/{version}:activate` | `RA_MODEL` | RA 모델 활성화 | `aml:admin:policy` |
| `POST .../risk-scores/{id}/override`(하향) | `RISK_OVERRIDE` | high-risk 등급 수동 하향 | `aml:case:update` |
| `POST .../tm-scenarios/{code}:activate` | `TM_SCENARIO` | TM scenario 변경 | `aml:admin:policy` |
| `POST .../cdd/cases/{id}:close`(EDD) | `EDD_CLOSE` | EDD 승인·종결 | `aml:case:update` |
| `POST .../cdd/cases/{id}:reject-relationship` | `RELATIONSHIP_REJECT` | 관계거절/온보딩 보류 확정 | `aml:case:update` |
| `POST .../reports/{id}:submit` (`reportType=STR`) | `STR_SUBMIT` | STR 제출 승인(COMPLIANCE 전담 4-eyes, tipping-off 통제 §19.2a) | `aml:case:update` |
| `POST .../reports/{id}:submit` (`reportType=CTR`) | `CTR_SUBMIT` | CTR 제출 승인(REPORTING_OFFICER 4-eyes, CTR 제외=`ctrExemptionCode` 필수 §14.3) | `aml:case:update` |
| `POST .../reports/{id}:reject`·`:cancel` | `STR_SUBMIT`/`CTR_SUBMIT`(`reportType` 분기) | 보고 기각·취소 — 사유 코드(`reasonCode`) 필수, REPORTING_OFFICER 4-eyes·자기승인 금지(§14.1a, CTR 제외 §14.3 포함) | `aml:case:update` |
| `POST .../travel-rule/transfers/{ref}:resolve-exception` | `TRAVEL_RULE_EXCEPTION` | Travel Rule exception 확정 | `aml:case:update` |
| `PUT .../cdd/checklists/{id}` | **`CHECKLIST_CHANGE`** | **CDD/EDD checklist 변경**(§13.4) | `aml:admin:policy` |
| `PUT .../cdd/periodic-review-policy` | **`PERIODIC_REVIEW_CHANGE`** | **periodic review 주기 변경**(§2.6·§13.4) | `aml:admin:policy` |
| `POST .../country-risk:change` | **`COUNTRY_RISK`** | **country risk 변경**(§13.4) | `aml:admin:policy` |
| `POST .../policy-packs:change` | **`POLICY_PACK`** | **tenant policy pack 변경**(§13.4) | `aml:admin:policy` |
| `POST .../source-systems`(secret 변경) | `SECRET_CHANGE` | source credential 변경 | `aml:admin:source-system` |

> 본 표로 설계서 §13.4 4-eyes 대상 전수(16종)가 진입 엔드포인트와 1:1 매핑된다. `STR_SUBMIT`·`CTR_SUBMIT`은 동일 경로(`:submit`)이되 `reportType` 파라미터로 분기되며, COMPLIANCE(STR)/REPORTING_OFFICER(CTR) 전담 결재 라인이 구분된다(설계서 §14.1a·§19.2a 정본). 보고 기각·취소(`:reject`/`:cancel`)는 **신규 subjectType 없이** `STR_SUBMIT`/`CTR_SUBMIT` 결재 사이클을 재사용하며 전이 종류(REJECT/CANCEL)·사유 코드는 결재 payload(`payload_hash` 고정)에 포함된다(설계서 §14.1a) — 결재 라인은 두 전이 모두 `REPORTING_OFFICER`. `COUNTRY_RISK`/`POLICY_PACK`은 §3.7 enum 정본이며 §2.7 `country-risk:change`/`policy-packs:change`가 결재 생성 트리거다. `CHECKLIST_CHANGE`/`PERIODIC_REVIEW_CHANGE`는 §3.7 enum 정본(총 16종); DB §5.16 동기화 대상. PRD §11.1·설계서 §13.5 동기화 대상.

---

## 변경 이력

| 일자 | 변경 | 비고 |
|---|---|---|
| 2026-06-24 | **CDD/RA 파이프라인 집계 엔드포인트·DTO 등재(코드=truth).** (1) **§2.7 RA 조회 표**에 엔진 `GET /api/v1/admin/aml/customers/pipeline-stats?histogramDays=`(scope `aml:case:read`, `Tenant-Id` 필수·`Workspace-Id` 옵션, `histogramDays` 1~90·기본14 클램프, 집계 카운트만) 행 추가. (2) **§9 bo-api 소유 경계 표**에 `GET /api/v1/bo/aml/ra/pipeline-stats?histogramDays=`(엔진 위임·비-prod stub·prod fail-closed 503 `AML.ENGINE_UNAVAILABLE`) 행 추가. (3) **§3.3c `CddRaPipeline` DTO 신설** — `kycStatusCounts`(PENDING/VERIFIED/INCOMPLETE/EXPIRED/REJECTED→number)·`registrationWindow`{count24h,count7d,count30d}·`raProcessing`{evaluated,pendingReview,notEvaluated}·`periodHistogram`[{date(YYYY-MM-DD),evaluatedCount}]·`generatedAt`(date-time). 출처 `aml_customers`(kyc_status·onboarding_at)·`aml_risk_scores`(evaluated_at·next_review_due_at), tenant 스코프·read-only·raw PII 미포함. | aegis-spec. 코드=truth. 근거=aml-svc 엔진 pipeline-stats·bo-api `/bo/aml/ra/pipeline-stats`. |
| 2026-06-21 | **RA inputDataAsOf·policyPackVersion + TM AlertSummary aggregationSummary(가산) 코드 정합.** (1) **§3.3 `RiskScoreResponse`** 에 `inputDataAsOf`(date-time, nullable, 입력 데이터 기준시점)·`policyPackVersion`(string, nullable, 정책팩 버전) 2 필드 추가 — 엔진 응답 passthrough, 없으면 best-effort(`inputDataAsOf`=`evaluatedAt`, `policyPackVersion`=null/stub 상수), RA 상세·점수 목록(§2.7) 응답 포함. (2) **§3.4a** 에 `aggregationSummary`(object\|null) 추가 + `AggregationSummary` 표 신설(`strIndicator`·`windowLabel`·`measure`·`threshold`·`thresholdMet`·`relatedCount`·`relatedAmount`·`currency`·`dominantChannel` 9종 전부 nullable) — TM 알림 **목록**(`GET /api/v1/bo/aml/alerts`, bo-api `AlertSummary`) triage 프리뷰 전용, `evidence`에서 목록 시점 파생(N+1 없음), raw PII 미포함(집계만). (3) **§3.4a** `measure`·`relatedAmount` 타입 `number` 정정(기존 string→threshold·measure 동일 수치축 일관, bo-api·bo-web Double·formatAmount 정합). | aegis-spec. 코드=truth. 근거=`bo-api` `RiskScore`·`AlertSummary` DTO. |
| 2026-06-21 | **WLF matchedCandidates 출처계보(가산) 반영.** §3.2 `ScreenResponse`에 가산 필드 `matchedCandidates[]`(원소 `MatchedCandidate`) 추가 + `MatchedCandidate` 출처계보 표 신설(entryId·sourceCode·provider·sourceType·listType·subjectKind·entryVersion·sourceLastImportedAt·matchField·score·threshold·reasonCodes·matchedTokenCount, 전 필드 nullable best-effort, raw PII 미포함). 기존 `matchedEntries`는 하위호환 유지(병존). bo-api가 `aml_watchlist_entries`+`aml_watchlist_sources` 조인으로 enrich. | aegis-spec. 코드=truth. DB §3.8 파생 주석 동기화. |
| 2026-06-21 | **코드 기준 RA·Subject360·override·alerts 정합화(이격 리포트 AML, 코드=truth).** (1) **§3.3 RiskAssessmentRequest** 에 `highRiskCountry`·`wlfTrueMatch`·`uboMismatch`(boolean, optional) 3 필드 추가(당연고위험 트리거, `EvaluateCommand`). (2) **§3.3 RiskScoreResponse** 에 `mandatoryHighRisk`(boolean)·`mandatoryHighRiskReasons`(array&lt;string&gt;) 추가(§2.7 점수 목록 응답). (3) **§3.3 `RiskOverrideRequest` DTO 신설**(`targetGrade` 하향만·`reason` 필수·`makerId` 필수) + override 경로는 **`POST /api/v1/admin/aml/risk-scores/{scoreId}/override`**(`RiskModelAdminController`, 코드 재확인 — 구 doc 경로 이미 정확) 명시. **§3.3b RiskDistributionResponse 신설**. (4) **§2.7 `GET .../risk-scores`(목록·`riskGrade` 멀티/`modelVersion`/page/size)·`GET .../risk-scores/distribution` 2행 추가**(구현됨, `RiskScoreAdminController`) + §5.1·§5 "미신설" 단언 폐기. (5) **§3.4b Subject360Dto** — `identity`에 `subjectType`·`displayNameMasked`, `riskSummary`에 `mandatoryHighRisk`·`highRiskRegistryReason`(단수→**array&lt;string&gt;**)·null(거래전용), `transactionFeed[].status`(DECIDED/MONITORED/null), 루트 `assembledAt` 추가 + **insight/assessment는 bo-web 클라 로컬 파생(`lib/aml-subject-insight.ts`)·API 비포함** 주석. (6) **§2.5a `GET /api/v1/bo/aml/alerts` 브라우즈 목록 행 추가**(필터 status·severity·sourceOrigin·`scenario`·from·to·targetRef·channel·corridor) + §2.4 엔진 public 알림은 status 단일 필터임 명시. | aegis-spec. 근거=`aml-svc` RiskController·RiskScoreAdminController·RiskModelAdminController, `bo-web/lib/aml-subject.ts`·`aml-subject-insight.ts`, `bo-api` AmlTmController. 이격8~16·19·20·24·25 반영. DB §3.9/§3.15·integration §3.4 동기화. |
| 2026-06-19 | **테넌트=서비스 재정의 + 기관 참조(institution_ref) 컬럼 신설(1 기관 : N 서비스).** §0/§1.1(plane·Tenant 라우팅)/§3.16/§5 OpenAPI/§6/§7 설명 텍스트의 '고객사'를 '서비스(테넌트=서비스)'로 정정(계층 기관→서비스(테넌트)→워크스페이스). `TenantDto`/`TenantCreateRequest`에 상위 기관 참조 `institutionRef`(=`aml_tenants.institution_ref`, nullable·additive) 필드 추가 + 설명에 1 기관 : N 서비스 노출(DTO·OpenAPI schema). `tenant_id`/`Tenant-Id` 헤더·RLS `app.current_tenant`·scope 코드·엔드포인트 경로·enum 불변(라벨/설명만). | aegis-spec. 컬럼명·enum·경로 불변. 개인 고객(`aml_customers`/`customerRef`)·기관(institution) 미혼동. |
| 2026-06-19 | **데이터 레이어 hanpass-ph 재그라운딩 + TM 알림 evidence·거래·대상360° 재설계.** §3.1 IngestEventRequest `sourceSystem`/`eventType`/`payload` 를 hanpass-ph 7실서비스·연동 키(member_id/transactionRef←charge_order_id·transaction_id·transfer_number·wallet_transaction_id·corridor·amountBase)로 현행화. §3.2 ScreenResponse scoreBreakdown 을 `member-svc zoloz_aml_screening`(decision/risk_level/total_hits/hit_results)로 정합. §3.4 TransactionEvaluateRequest 에 `corridor`·`amountBase` 추가, channelType 을 hanpass-ph 채널로. §3.4a AlertDto `evidence` 를 **TM 알림 상세 데이터모델**(트리거·strIndicator·집계패턴·relatedTransactions·fundGraph)로 보강 + `subject360Ref`. **§2.5a `GET /api/v1/bo/aml/subjects/{customerRef}/360` 신규** + **§3.4b Subject360Dto 신규**(tx-history + member CDD/screening + wallet transfer_links read model). **규제 임계·기한 불변** — strIndicator(STR_001~015)·sanction_screening_event 는 데이터 신호로만 매핑(규제 STR 분류 KR 정본 유지). | aegis-spec. 식별자 keyed-HMAC·raw PII 금지. domestic-svc member_id varchar(36) join 정규화. DB §3.2/§3.8/§3.10/§3.16·integration §3/§4/§7·PRD §1.5/§7 동기화. |
| 2026-06-16 | **T11 (AML-ENG-05) internal REST 3종 컨트롤러 구축·인증 API key+HMAC 승격(제안→확정).** §2.6 Internal API 표 3행(`POST /internal/v1/aml/fds-escalations`·`GET /internal/v1/aml/customers/{customerRef}/risk`·`POST /internal/v1/aml/screen`)의 인증을 `X-Internal-Service`+mTLS → **API key + HMAC**(ingest 필터 `AmlIngestAuthenticationFilter` 차용, ADR 2026-06-15 D2; pii/reveal T3 선례 일관, mesh mTLS 는 P8 보강)로 승격, 동작 사양 명문화: escalation=§3.10 `FdsEscalationRequest`→`FdsDecisionCommand` 어댑팅(`fraudCaseRef`=멱등키, 응답 `{ alertId, accepted }`)으로 SQS `aml-fds-decision` 큐 경로(`FdsDecisionConsumer`)와 동일 usecase·멱등·감사(가정 A2); risk=public `AssessRiskUseCase`·`CustomerRiskResponse` 재사용·RA 등급 단독(WLF 병합 미정의 → 후속, 가정 A6)·미존재 404; screen=public `ScreenSubjectUseCase`·`ScreenRequest`/`ScreeningResponse` 재사용·`Idempotency-Key` 필수(가정 A4·A6). scope 강제는 호출자 평면 책임(가정 A5). 신규 domain/usecase/Flyway 없음(기존 재사용). 정본=태스크 `20260615-exposed-gap-development-tasks.md` §T11·plan `docs/ai/plans/20260616-aml-eng-05-internal-rest-3.md`. | aegis-java-implementer |
| 2026-06-15 | **T4 (AML-ENG-04) STR 통계 원천 surface 역삽입(제안→확정).** §2.7 admin reports 표에 `GET /admin/aml/reports/stats/str-delay`·`/admin/aml/reports/stats/unreported-reasons`(`aml:case:read`+`COMPLIANCE` role 필수, tipping-off §19.2a, `RAW_DATA_ACCESS` 감사, `period=7d\|30d\|90d`) 2행 추가 — STR 지연일수 분포·미보고 사유 분포 집계 원천(PRD §12-B.3 ①, 응답 집계 카운트만·PII 미노출, 0건=honest 빈 분포). §3.6 응답 DTO `DelayBucket`(5종 버킷 0-fill: ON_TIME/D1_3/D4_7/D8_14/D15_PLUS)·`UnreportedReason`(closure_reason_code 빈도, legacy=UNSPECIFIED) 추가 + `ReportRejectRequest`/`ReportCancelRequest` 종결 시 `reasonCode`→`closure_reason_code`(DB §3.12) 영속 명문화. 지연 버킷은 §14.4 BR-006 SLA 대비 상대 일수(엔진 business-day 계산기 부재로 달력일 근사 — 가정 A3). 엔진(aml-svc)만 구현, bo-api 실집계 결선(`AmlStatsService` 빈배열 제거)은 후속 T15. 정본=태스크 `20260615-exposed-gap-development-tasks.md` §T4·plan `docs/ai/plans/2026-06-15-t4-aml-stat-source-surface.md`·DB §3.12·PRD §12-B.3. | aegis-java-implementer |
| 2026-06-15 | **T3 (AML-ENG-03) PII reveal 정본 엔드포인트 역삽입.** §2.6 Internal API 표에 `POST /internal/v1/aml/pii/reveal`(호출자 bo-api, 입력 `targetRef`/`field`/`reason` → 출력 `value`=transient cleartext) 행 추가 — 인증 = **API key + HMAC**(ingest 필터 `AmlIngestAuthenticationFilter` 차용, ADR 2026-06-15 D2; §2.6 표 행 인증은 `X-Internal-Service`+mTLS 명세였으나 T3 요구(4) 태스크 정본 우선, mTLS 는 P8 보강). 엔진측 `RAW_DATA_ACCESS` 감사·역참조 미존재/복호화 실패 시 503 `AML.SCREENING_UNAVAILABLE`(fail-closed). cleartext 원천 = 가역암호 vault `aml_pii_vault`(DB §3.x, §2.2 "원문(=평문) 컬럼 금지" 유지). scope `aml:pii:reveal` 강제는 bo-api 평면(§1.6, 가정 A5). bo-api 실결선은 후속 T14. 정본=태스크 `20260615-exposed-gap-development-tasks.md` §T3·ADR `docs/ai/decisions/2026-06-15-aml-eng-03-pii-reveal.md`·DB §2.2/§3.x. | aegis-java-implementer |
| 2026-06-11 | QA HIGH(L166) 해소: §4 에러 테이블 `AML.TENANT_NOT_FOUND` HTTP 409 → **404** 정정(§5 OpenAPI paths·PRD 부록 D 정합) + §5 POST /tenants 409 설명에서 TENANT_NOT_FOUND 잔존 표기 제거(409=tenantId 중복만). | api-designer |
| 2026-06-11 | QA HIGH #1(aml:db-api) 해소: §3.9 `SourceSystemDto`에 `status` 필드 추가 — enum 2종(`ACTIVE`/`DISABLED`), DB §3.2 `aml_source_systems.status`(V20) 정본 1:1. | api-designer |
| 2026-06-11 | doc-consistency 리포트(all-latest) **HIGH 이격 — AML API 담당** 정합: ① §5 OpenAPI paths(GET 필터·PUT body) tenant status enum을 **4종**(`ONBOARDING`/`ACTIVE`/`SUSPENDED`/`OFFBOARDED`)으로 교체 — §3.16 TenantDto와 자가 일치(DB §5.28b·V20 정본). ② **§2.7 `POST .../reports/{reportId}:reject`·`:cancel` 신설** — 사유 코드(`reasonCode`) 필수·REPORTING_OFFICER 4-eyes·자기승인 금지(설계서 §14.1a 정본), §3.6 `ReportRejectRequest`/`ReportCancelRequest` DTO 추가, §10 등재(신규 subjectType 없이 `STR_SUBMIT`/`CTR_SUBMIT` 결재 사이클 재사용), §6 STR/CTR 행 동기화 — WBS `17-regulatory-reporting.md` 표기와 정합. | api-designer |
| 2026-06-10 | **QA 리포트 높음·중간 이격(API 명세 담당) 정정.** (1) **§2.7 STR 조회 tipping-off 통제 추가(QA #20)** — `GET .../reports?reportType=STR` 시 COMPLIANCE 전담 role 필수 게이트, 경고 배너·`RAW_DATA_ACCESS` 감사 명시(설계서 §19.2a). (2) **§3.6 `RegulatoryReportDto`에 `reportDeadlineAt`·`slaStatus` 추가(QA #21)** — STR=결재승인+3영업일, CTR=거래일+30일 서버 계산, `slaStatus` 3종(`ON_TIME`/`DUE_SOON`/`OVERDUE`) + D-3 배지 연결(설계서 §14.4). (3) **§10 4-eyes 등재표 `STR_SUBMIT`/`CTR_SUBMIT` 분리(QA #23)** — 동일 `:submit` 경로를 `reportType` 분기로 2행 표기, COMPLIANCE/REPORTING_OFFICER 결재 라인 구분 명시(15행→16행, 설계서 §13.4 16종 정본과 1:1). | api-designer |
| 2026-06-10 | **준법감시인 검토 반영(상위 정본=설계서 §14.1a/§14.3·DB §3.12/§5.11 2026-06-10 갱신) 동기화.** (1) **§3.6 `RegulatoryReportDto.status` 8종 확장** — `ACKNOWLEDGED`/`SUBMISSION_FAILED` 추가(FIU 회신 폐루프). (2) **§3.6 필드 4종 추가** — `fiuAckRef`(FIU 접수번호)·`submissionErrorCode`(오류코드)·`resubmitCount`(재제출 횟수)·`ctrExemptionCode`(CTR 제외 사유 코드), DB §3.12 컬럼 1:1. (3) **재제출=기존 `:submit` 결재 사이클 재사용**(신규 엔드포인트 없음)·기각/취소(`REJECTED`/`CANCELLED`)·CTR 제외 처리=사유 코드 필수+보고책임자 4-eyes 주석. (4) **§8.1 `AmlReportSubmitted` webhook** — status에 `ACKNOWLEDGED`/`SUBMISSION_FAILED` 추가, `fiuAckRef`/`submissionErrorCode` payload 키 추가. | api-designer. 연동 §3.4/§5.4/§6.2·PRD §1.7/§9/§12-A.8·PPT v5.9 동기화 대상. |
| 2026-06-07 | 정합성 리포트 잔존 높음 이격(결재 subjectType 정본이나 결재 생성 진입점 부재 3건) + 중간 이격 정합. **(A) admin 정책 엔드포인트 신설(§2.7, scope `aml:admin:policy`, `/api/v1/admin/aml/**`, fds 패턴=엔진 admin은 aml-svc 소유).** ① **CDD/EDD checklist 정책** — `GET/POST .../cdd/checklists`, `PUT .../cdd/checklists/{id}`(🔒4-eyes, 설계서 §13.4 'CDD checklist 변경') + **periodic review 주기 설정** `PUT .../cdd/periodic-review-policy`(🔒). ② **country risk** — `GET .../country-risk`, `POST .../country-risk:change`(🔒, §3.7 subjectType=`COUNTRY_RISK` 결재 트리거). ③ **tenant policy pack** — `POST .../policy-packs:change`(🔒, subjectType=`POLICY_PACK` 트리거). 각 요청/응답 DTO(§3.11~§3.13), scope, 표준 에러코드(§4 공통), OpenAPI 스니펫(§5: `CountryRiskChangeRequest`/`PolicyPackChangeRequest`/`PeriodicReviewPolicyRequest`/`ApprovalSubmittedResponse` schema + `country-risk:change`/`policy-packs:change`/`periodic-review-policy` path), §3.7 결재 subjectType(`COUNTRY_RISK`/`POLICY_PACK`) 트리거 연결, **4-eyes 결재 트리거 등재표 §10 신설**(설계서 §13.4 대상 ↔ subjectType 1:1, 진입점 부재 해소) 추가. **(B) 중간 이격 정합** — travel-rule 필터/응답 DTO(§3.14 `TravelRuleTransferDto`, riskStatus 4종 §5.15·completenessStatus 4종 §5.22 정본, `from`/`to` 필터·OpenAPI path/schema) + simulation 응답 DTO(§3.15 `SimulationResponse`: `gradeShift`·`falsePositiveImpact`, PRD §5.1 AML-RA-001 '시뮬레이션' 탭 의존, RA/TM simulate 공통 응답) 신설. **(C) bo-api 위임 관계 1줄 명시(§9)** — `bo-web → bo-api → aml-svc /api/v1/admin/aml/**` 위임 호출. §6 BO 매핑·§7 동기화 표 갱신. 정본=`target-architecture.md`(엔진 admin은 aml-svc 소유, bo-web은 bo-api만)·입력=설계서 §2.6/§13.4/§13.5/§15.7·DB §5.15/§5.22/§5.16·PRD §5.1. | api-designer |
| 2026-06-07 | 정합성 리포트(doc-consistency-report-aml-latest) design:api 담당분 재확정. (a) **운영자 집계 API 소유 경계 재명시** — 대시보드(플랫폼·고객사별)·고객사 관리·운영자 감사 조회 집계 엔드포인트는 **bo-api 소유**(`/api/v1/bo/aml/**`, §0·§9)이며 엔진 API §2에 **추가하지 않음** 확정. fds-svc/aml-svc는 저수준 데이터 API만 제공, PRD/PPT 해당 화면(AML-DASH-001 등)은 호출 대상을 bo-api로 명시. (b) **마스터 enum=본 API enum(전수) 정본** — screening_status(`POSSIBLE_MATCH` 정규)·결재 `subjectType`(`TM_SCENARIO` 포함, §3.7) 정본, 설계서 동기화. AML은 FDS의 `action_type`에 해당하는 enum 없음(action_type 마스터는 fds-api §1.1 소관). (c) **HTTP 상태코드=§4 정본** 유지. (d) **OpenAPI 누락 필드** `ScreenResponse.matchedRules`(`RuleRef[]`) 등 §5 반영 유지. (e) **Webhook 콜백=§8 정본** 유지. **(f) `aml:pii:reveal` scope를 §1.1 enum(13종)·OpenAPI scopes 블록에 정식 등재** — API를 단일 정본으로 확정(`aml:db-api`/`aml:design-api`/`aml:api-prd` 잔여 이격 해소), 설계서 §15.7·PRD §1.4는 본 §1.1 전수 enum 인용으로 동기화. | api-designer |
| 2026-06-07 | 정합성 리포트(doc-consistency-aml) 높음 이격 중 API 명세(design:api) 담당 항목 정정. (1) **운영자 집계 API 소유 경계 확정** — 대시보드(플랫폼·고객사별)·고객사 관리·운영자 감사 집계는 bo-api 소유(`/api/v1/bo/aml/**`, §9)로 명시, 엔진 API §2에 미추가. RA `GET /admin/aml/risk-scores` 엔진 직접 집계 엔드포인트 미신설 확정(bo-api dashboard 또는 ra-models/customers/{ref}/risk 사용), PRD AML-RA-001·태스크 §5 정정 대상. (2) **마스터 enum=API enum 정본** — screening_status(`POSSIBLE_MATCH` 정규, `POTENTIAL_MATCH`/`result` 환원), 결재 `subjectType`에 **`TM_SCENARIO` 추가**(§3.7, PRD §11.1·설계서 동기화). (3) **HTTP 상태코드=§4 정본** 확정(멱등409·결재/자기승인409·payload변경409·상태전이409·검토요구422·rate429·fail-closed503). (4) **OpenAPI 누락 필드 보강** — `ScreenResponse.matchedRules`(`RuleRef[]`) 추가, `RuleRef`/`IngestEventResponse`/`TransactionEvaluateResponse`(`scenarioCode`/`severity`) schema 신설. (5) **Webhook 콜백 계약(§8 신설)** — screening/case/report 상태변경 outbound 3종(`AmlScreeningResolved`/`AmlCaseStatusChanged`/`AmlReportSubmitted`)·envelope·`X-Signature` HMAC·재시도/멱등 확정, 설계서 §15.7 'Webhook API'·연동 §3.4 `webhook.callback.requested` 정합. 정본=`target-architecture.md`+설계서(docs/software)·DB(docs/design/db)·API(docs/design/api); 파생(연동·태스크·PRD·PPT)은 본 명세를 동기화한다. | api-designer |
| 2026-06-08 | **§7 동기화 표 stale 문구 정정.** §7 'DB 명칭' 행의 "`payload_hash` NOT NULL → §3.1 R=R 필수화" 표현을 "서버 자동계산(2026-06-08) optional 전환" 사실로 갱신. §3.1 DTO 표(R=—, 서버 자동계산 주석)·§3.5 `eddTrigger` 8종·§3.6 `status` 6종·§3.8 UseCase stale 주석 갱신은 line 1465 이력으로 이미 반영 완료. 정본=DB `02-aml-db.md` §3.15. | api-designer |
| 2026-06-08 | **QA 이격(doc-consistency-report-aml-latest) API 담당 항목 정정.** 상위 문서(DB §3/§5) 기준 동기화. **(1) HIGH: §3.1 `IngestEventRequest.payloadHash` optional 전환** — DB §3.15 결정(2026-06-08) 반영: 서버 자동계산 방식 확정, R=필수→R=— 선택, '미제공 시 aml-svc ingest 어댑터 sha256 자동 계산' 주석 추가. **(2) LOW+cross MEDIUM: §3.5 `CaseDto.eddTrigger` 허용값 8종 명기** — DB §5.29 정본 8종(`WLF_TRUE_MATCH`/`HIGH_RA_SCORE`/`HIGH_RISK_COUNTRY`/`UNUSUAL_TRANSACTION`/`COMPLEX_OWNERSHIP`/`TRADE_MISMATCH`/`CRYPTO_RISK`/`INTERNAL_OVERRIDE`) 직접 열거, '§13.2 EDD trigger'만 참조하던 기술에서 코드값 목록 추가. **(3) LOW: §3.6 `RegulatoryReportDto.status` 허용값 6종 명기** — DB §5.11 정본 6종(`DRAFT`/`UNDER_REVIEW`/`APPROVED`/`SUBMITTED`/`REJECTED`/`CANCELLED`) 직접 열거(Integration §9.1 대조 가능). **(4) LOW: §3.8 UseCase 명칭 stale 주석 갱신** — '설계서 §6.2 교정 대상' → '설계서 §6.2 교정 완료' 갱신. 정본=`target-architecture.md`, 상위=DB `02-aml-db.md` §3.15/§5.11/§5.29. | api-designer |
| 2026-06-08 | **격리(isolation_mode) → 배포 모델(deployment topology) 재설계** 동기화(설계서 `02-amlSvc-sass.md` §16 + DB `02-aml-db.md` §3.1/§5.28/§5.28a/§5.28b V17a/V17b + 정본 target-architecture §4.1 + FDS API v1.5 §10/§11.2/§13 기준). **(1) DTO §3.16 신설** — `TenantDto`(`deploymentModel`/`onboardingStatus`/`status`/`region`/`infraRef`·`isolationMode` 폐기), `TenantCreateRequest`(deploymentModel 선택 = 온보딩 신청), `TenantUpdateRequest`(deploymentModel 불변), `OnboardingProvisionRequest`(IaC 파이프라인 트리거), `OnboardingRegisterRequest`(self-hosted 등록 콜백·registrationToken 인증), `OnboardingStatusResponse`(상태·이력·nextExpectedStatus). **(2) OpenAPI(§5) enum/schema 신설** — `DeploymentModel`(3종)·`OnboardingStatus`(8종, DB §5.28a 1:1)·`TenantDto`/`TenantCreateRequest`/`OnboardingProvisionRequest`/`OnboardingRegisterRequest`/`OnboardingStatusResponse` schema 추가. **(3) OpenAPI(§5) paths 신설** — bo-api 소유 5종: `GET/POST /api/v1/bo/aml/tenants`, `GET/PUT .../tenants/{tenantId}`, `POST .../onboarding/provision`(202 PROVISIONING), `POST .../onboarding/register`(200 REGISTERED), `GET .../onboarding`. **(4) 에러코드(§4) 6종 추가** — `AML.TENANT_DEPLOYMENT_MODEL_IMMUTABLE`·`AML.TENANT_NOT_FOUND`·`AML.ONBOARDING_PROVISION_NOT_APPLICABLE`·`AML.ONBOARDING_REGISTER_NOT_APPLICABLE`·`AML.INVALID_REGISTRATION_TOKEN`·`AML.ONBOARDING_INVALID_STATE_TRANSITION`. **(5) §1.1 Tenant 라우팅** — 전용 배포=배포=고객사 단일·SHARED만 헤더 행 라우팅으로 재정의. **(6) §6 BO 화면 정합** — '고객사 관리', '고객사 등록(배포 유형+온보딩 신청)', '온보딩 상태' 3종 화면 추가. 格離 라디오('격리 방식' 라디오) 폐기·화면 교체 명시. **(7) §9 bo-api 경계 표** — 온보딩 프로비저닝·상태조회·self-hosted 등록 행 추가, isolation_mode 폐기. **(8) §7 동기화 표** — 배포 모델/온보딩 행 추가, enum·DTO·엔드포인트·상태머신·라우팅 의미 확정. 폐기: `isolation_mode` 컬럼·enum(`SHARED`/`SCHEMA`/`DB`)·격리 라디오. aml-svc 엔진 API(§2)에는 온보딩 엔드포인트 미추가(bo-api 전용 소유 경계). 오픈결정: SELF_HOSTED `registrationToken` 서명·mTLS 등 인증 방식 상세는 P8 인프라 설계에서 확정. | api-designer |
| 2026-06-08 | **정합성 리포트(doc-consistency-report-aml-latest) API 담당 이격 정정.** 정본=`target-architecture.md`·DB §3/§5. **(1) HIGH: `§3.1 payloadHash` R=R 필수화** — DB `payload_hash` NOT NULL 계약 일치(호출자 계산 필수 또는 서버 자동계산 시 DB NULLABLE 완화와 함께 결정). **(2) HIGH: `§3.5 CaseDto.originFdsCaseRef` 추가** — DB `aml_cases.origin_fds_case_ref` FK cross-ref 1:1(source_origin=FDS 시 채움, nullable). **(3) HIGH: `§3.7 ApprovalDto.subjectType` 2종 추가** — `CHECKLIST_CHANGE`(CDD/EDD checklist 정책 변경)·`PERIODIC_REVIEW_CHANGE`(periodic review 주기 변경). 총 16종 확정; DB §5.16 동기화 대상. `§3.11 ChecklistChangeRequest·PeriodicReviewPolicyRequest`·`§10 트리거 등재표` subjectType 코드 명시. **(4) MEDIUM: `§3.2 ScreenResponse` 필드 추가** — `targetRef`·`targetType`·`decidedBy`·`decidedAt`(DB §3.8 컬럼 1:1). **(5) MEDIUM: `§3.6 RegulatoryReportDto.approvalId` 추가** — DB `aml_regulatory_reports.approval_id` FK 1:1(nullable). **(6) MEDIUM: `§3.9 WatchlistEntryDto`·`CustomerProfileDto` 신설** — DB §3.7·§3.3·§3.4 정합, raw PII 미노출 마스킹 원칙 명문화. **(7) MEDIUM: `§2.7 audit-events` eventCategory 10종 enum 목록 명시** + `§5 OpenAPI EventCategory`·`WatchlistEntryDto`·`CustomerProfileDto` schema 신설. **(8) HIGH: `§5 OpenAPI GET /api/v1/bo/aml/tenants` `region=` 쿼리 파라미터 추가** — PRD §13.1 region 4축 필터 정합. **(9) MEDIUM: `§3.8` UseCase 명칭 정본 명시** — `ExportEvidenceUseCase`가 기준; SW §6.2 `BuildEvidencePack`/`ExportEvidenceUseCase` 혼용 교정 대상 명시. **(10) LOW: `§1.5` DRAFT 상태 내부 전이 명문화** — API 표면 미노출(설계서 §13.5 DRAFT ↔ API 불일치 해소). **(11) `§0 마스터 enum` 주석** — subjectType 16종으로 갱신. `§7 DB 동기화 표` 정정 내용 반영. | api-designer |
| 2026-06-08 | **정합성 리포트(doc-consistency-report-aml-latest) API 담당 이격 7건 정합화.** **(#37 HIGH) §3.2 `ScreenResponse`에 `screeningHistory` 주석 추가** — 이전 판정 이력은 `GET .../screenings/{id}` 파생, `ScreenResponse` 미포함(PRD 화면파생 방향 채택). **(#26 MED) §10 RA 모델 활성화 경로 교정** — `POST .../ra-models/versions/{v}:activate` → `POST .../ra-models/{modelCode}/versions/{version}:activate`(`{modelCode}` 세그먼트 복원). **(#21 MED) §3.3 `RiskScoreResponse` 테이블 신설** — `targetType`·`modelCode`·`isOverride` 필드 추가(DB §3.9 `target_type`·`model_code`·`is_override` 컬럼 1:1). **(#22 MED) §2.4 응답에 `AlertDto` 참조 명시 + §3.4a `AlertDto` 스키마 신설** — DB §3.10 10컬럼+감사(`alertType`·`scenarioCode`·`targetRef`·`transactionRef`·`severity`·`status` 6종·`evidence`·`sourceOrigin`·`externalAlertRef`·`createdAt`·`updatedAt`) 1:1, raw PII 미노출 명문화. **(#23 LOW) §3.7 `ApprovalDto.status` 7종 직접 열거** — `SUBMITTED`/`APPROVED`/`REJECTED`/`CANCELLED`/`EXPIRED`/`EXECUTED`/`EXECUTION_FAILED`(`DRAFT` 제외, §1.5 내부 전이 상태 근거). **(#24 LOW) §3.9 `SourceSystemDto`에 `createdAt`·`updatedAt` 추가**. **(#38 MED) §3.9 `WatchlistEntryDto.listType` PRD 명단군 매핑 정본 확인 주석** — 7종 코드값이 bo-web 화면 '명단군' 필터·배지의 단일 정본임을 명시. 정본=`target-architecture.md`, 상위=DB §3.9/§3.10/§5.13/§5.18/§5.23. | api-designer |
| 2026-06-06 | 신규 작성(부트스트랩). 설계서 `02-amlSvc-sass.md` §15.7 API group과 DB 설계서 `02-aml-db.md` §3 테이블·§5 enum을 동기화해 AML API 명세 확정: 3-plane(Public/Internal/Admin), 인증·테넌시·data-scope·멱등·페이지네이션·버저닝 횡단 규약, 엔드포인트 표(ingest/screen/RA/TM/evidence/internal/admin), DTO 스키마(식별자·enum DB와 1:1), 표준 에러 모델(AML.*), 🔒4-eyes 표기(maker≠checker `aml_approvals`), OpenAPI 3.1 스니펫, BO 화면↔API 정합표. raw PII 미노출(ref/hash 마스킹), bo-web→bo-api만(엔진 직접호출 금지) 명시. | 정본=`target-architecture.md`, 입력=설계서+DB. `POTENTIAL_MATCH`→`POSSIBLE_MATCH` 정규화 반영. integration/tasks/PRD는 본 엔드포인트·DTO·scope·에러코드를 참조한다. |
