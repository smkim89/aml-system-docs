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

> **reveal 가능 `field` 도메인(7종, 2026-06-29 식별정보 확장)**: `NAME`/`DOC`/`ACCOUNT`/`WALLET` + `NATIONALITY`(국적)/`GENDER`(성별)/`DOB`(생년월일). 도메인 `PiiField`(7종)·`aml_pii_vault.field` CHECK(DB §5.35·§3.21, Flyway V23)와 1:1, 미허용 값은 400. WLF 매치 상세(§3.2 `subjectIdentity`)는 회원 본인 식별정보와 워치리스트 엔트리 원문(매칭 후보)을 **주체 무관 균일 4필드(`NAME`/`NATIONALITY`/`GENDER`/`DOB`)** 로 본 reveal 게이트에 노출하되, scope·사유·`RAW_DATA_ACCESS` 감사 없이는 cleartext 미산출(주체가 보유하지 않거나 vault 미적재 필드는 reveal stub 이 빈 값 `""` 반환, fail-closed 불변).

---

## 2. 엔드포인트 표

### 2.1 Ingest API (Public) — 설계서 §8·§15.1·§15.3

| 메서드 | 경로 | scope | 멱등 | 설명 | DB |
|---|---|---|---|---|---|
| POST | `/api/v1/aml/events` | `aml:event:write` | Y | canonical AML event 수신(customer/entity/transaction/screening/...) | `aml_canonical_events` |
| POST | `/api/v1/aml/events:batch` | `aml:event:write` | Y | 대량 event 배치 수신(queue 대체 동기 경로) | `aml_canonical_events` |
| GET | `/api/v1/aml/events/{eventId}` | `aml:event:write` | — | 수신 event 상태 조회(idempotency 확인) | `aml_canonical_events` |

> **BO 수신 API 카탈로그 분류(2026-07-01 코드 정합).** 엔진 canonical `/events`는 materialize/호환 경로로 유지하되,
> 운영 화면과 비-prod hanpass-ph 시뮬레이터는 업무 API를 7종으로 분리해 표시한다: 실시간 거래
> `POST /api/v1/aml/transactions/evaluate`(FDS 탐지 결정과 동일 거래 payload 기반, AML TM은 CTR/STR 사후 모니터링),
> 회원가입 후 CDD 승인 `POST /api/v1/aml/customers/cdd-approvals`, 고객 정보 수정
> `POST /api/v1/aml/customers/profile-changes`, KYC/CDD 재이행
> `POST /api/v1/aml/customers/kyc-reviews`, EDD 데이터 제출 `POST /api/v1/aml/customers/edd`,
> RA 평가 `POST /api/v1/aml/risk-assessments/evaluate`, 실시간 WLF
> `POST /api/v1/aml/screen`. 물리 엔진 alias 추가는 별도 버전 작업으로 분리하며, 현재 BO 카탈로그/헬스의 분류 정본은 이 표기다.

### 2.1a 중립(canonical) 수집 API — `POST /aml/v1/transaction-events` (코드=truth, feature/aml-neutral-canonical-ingest)

소스 중립(canonical) 수집 API. 해외송금·국내송금·카드결제·월렛충전·월렛결제 5개 product 를 **단일 Envelope**(`docs/aml-data.md` §3~§7, ISO 20022/FATF R.16/ISO 4217·3166·8601)로 수신하고, 하나의 POST 로 WLF 스크리닝 + CTR/STR 평가(TM 파이프라인)를 팬아웃한다. 기존 `POST /api/v1/aml/events`(§3.1, 내부 canonical 저장 경로)와 별개의 공개 수집 표면이며, 원천 시스템은 자기 컬럼을 이 표준 필드로 매핑만 하면 동일 API 로 인입한다.

| 메서드 | 경로 | scope | 멱등 | 헤더 | 설명 | DB |
|---|---|---|---|---|---|---|
| POST | `/aml/v1/transaction-events` | `aml:event:write` | Y | `Tenant-Id`(필수)·`Idempotency-Key`(옵션, 미지정 시 body `eventId` 사용·지정 시 `eventId`와 일치 필수)·`X-Trace-Id`(옵션) | 중립 Envelope 수신 → 검증(422) → PII 토큰화·vault → canonical event 멱등 저장 → WLF + CTR/STR 평가. 응답=수신확인 + 평가요약 | `aml_canonical_events`(+`aml_alerts`·CTR/STR 파생) |

**상태코드 매핑**(엔진 `NeutralTransactionEventController#httpStatus` = truth): `ACCEPTED`→`202`, `REPLAYED`(멱등 재전송·동일 payload)→`200`, `DUPLICATE`(동일 키·다른 내용)→`409`, `REJECTED`(검증 실패)→`422`. 검증 실패는 **단일 422** 에 누적 위반 목록을 실어 반환하며 500 을 던지지 않는다(fail-closed).

**요청 Envelope 스키마**(공통, `NeutralEventRequest` = truth). 상세 블록·Party·Amounts 는 §3.17.

| 필드 | 타입 | R | 검증/설명 |
|---|---|---|---|
| `eventId` | string(UUID) | R | 이벤트 고유 ID(멱등키). `Idempotency-Key` 헤더와 일치해야 함 |
| `eventType` | enum | R | `CREATED`/`COMPLETED`/`CANCELLED`/`REFUNDED`/`REVERSED`. 취소·환불·역거래는 CTR 순증(§9)을 위해 `relatedReference` 필수 |
| `product` | enum | R | `CROSS_BORDER_REMITTANCE`/`DOMESTIC_TRANSFER`/`CARD_PAYMENT`/`WALLET_TOPUP`/`WALLET_PAYMENT` |
| `direction` | enum | R | `INBOUND`/`OUTBOUND`/`INTERNAL` |
| `transactionReference` | string | R | 원천 거래 고유번호 |
| `relatedReference` | string | 조건부 | 취소/환불/역거래 시 원거래 참조번호(reversal eventType 이면 필수) |
| `occurredAt` | string(date-time) | R | ISO-8601 offset 포함 |
| `valueDate` | string(date) | — | 결제/정산일 |
| `channel` | enum | — | `MOBILE_APP`/`WEB`/`BRANCH`/`API`/`KIOSK` |
| `institutionId` | string | R | 보고기관 식별자(멀티 소스 구분). 엔진 canonical `sourceSystem`으로 매핑(가정 G8) |
| `status` | string | R | 원천 거래 최종 상태 |
| `originator` | object(Party) | R | 주체 고객. `nationalIdentityKey` 필수(CTR 최소요건 §9). §3.17 Party |
| `amounts` | object | R | 금액 블록. `baseAmount`/`baseCurrency` 필수, `baseCurrency`=테넌트 규제통화(가정 G3). §3.17 Amounts |
| `counterparty` | object(Party) | 조건부 | 상대방. `CROSS_BORDER_REMITTANCE`이면 필수(Travel Rule §6.1) |
| `remittance`/`domesticTransfer`/`cardPayment`/`walletTopup`/`walletPayment` | object | 조건부 | `product`에 대응하는 블록만 채움(§3.17 product 블록) |

**422 검증 규칙**(`NeutralEventValidator` = truth): ① 필수필드 누락(`eventId`/`eventType`/`product`/`direction`/`transactionReference`/`institutionId`/`status`/`occurredAt`/`originator.nationalIdentityKey`/`amounts.baseAmount`/`amounts.baseCurrency`) ② `occurredAt` ISO-8601 offset 위반 ③ 통화 ISO 4217(3자)·국가 ISO 3166-1 alpha-2(2자) 위반 ④ `baseAmount` < 0 ⑤ `amounts.baseCurrency` ≠ 테넌트 규제통화(가정 G3, 데모=PHP·임계 ₱500,000 — 잘못된 환산으로 CTR 오보고 방지 fail-closed) ⑥ reversal eventType 인데 `relatedReference` 누락 ⑦ `CROSS_BORDER_REMITTANCE`인데 `counterparty` 누락. 위반은 배열로 누적되어 한 번의 422 로 반환된다. 미지 enum 값은 역직렬화 단계에서 `400 AML.BAD_REQUEST`.

**family 매핑 표**(`ProductEventTypeMapper` = truth, 가정 G1/G2). product+lifecycle → canonical `eventType` 문자열 + engine `channelType` 토큰:

| product | canonical eventType | EventFamily | channelType | CTR 현금성 |
|---|---|---|---|---|
| CROSS_BORDER_REMITTANCE | `remit.transfer.<verb>` | REMIT | `CROSS_BORDER_REMIT` | 비현금 |
| DOMESTIC_TRANSFER | `domestic.transfer.<verb>` | DOMESTIC | `DOMESTIC_REMIT` | 비현금 |
| CARD_PAYMENT | `transaction.card-payment.<verb>` | TRANSACTION(가정 G1, 신규 enum 없음) | `CARD_PAYMENT` | 비현금 |
| WALLET_TOPUP | `wallet.charge.<verb>` | WALLET | `CASH_IN` | **현금성(CTR 대상)** |
| WALLET_PAYMENT | `wallet.pay.<verb>` | WALLET | `WALLET_PAYMENT` | 비현금 |

- `<verb>` = lifecycle 소문자(`created`/`completed`/`cancelled`/`refunded`/`reversed`, 가정 G2). 기존 hanpass `*.requested` 태그는 레거시 커넥터용으로 병존(strict gate 는 family prefix 만 검사).
- `channelType`=`CASH_IN`(WALLET_TOPUP)만 CTR 현금성 게이트(`CtrEvaluationService.CASH_BEARING_CHANNELS`)에 걸려 CTR DRAFT 를 연다. 나머지 product 는 STR/TM 은 평가하되 CTR DRAFT 를 열지 않는다.

**CTR 순증(net) 규칙**(가정 G4, `NeutralTransactionEventService#signedBaseAmount` = truth): reversal eventType(CANCELLED/REFUNDED/REVERSED)은 `amountBase`/`phpEquivalent`를 **음수**로 저장해 동일 `(tenant, subject, bankingDay)` 일합산 윈도우가 원거래를 순증 차감한다. 별도 보정 레코드 없이 DRAFT 가 부호 합산을 누적하며, 임계 재하락 시에도 DRAFT 는 유지된다(자동 철회·삭제 없음, 감사추적 보존).

**PII 토큰화 경계**(가정 G7/G9, §1.6 원칙 그대로): raw 이름·신분증번호·계좌번호·전화는 컨트롤러→usecase 수신 경계에서만 존재하고, 즉시 토큰화(`PiiTokenPort`)+가역 vault(`aml_pii_vault`) 적재 후 소멸한다. 엔진 payload·canonical event·로그·응답에는 `targetRef`/`counterpartyRef`(안정키 토큰)·`*Masked`만 실린다. subject 토큰=`originator.nationalIdentityKey` 기반, counterparty 안정키=이름+거주국+전화(기존 WLF 정본 재사용). 신분증번호(`idNumberToken`)는 vault 만, payload·응답 미포함.

**응답**(`NeutralIngestResponse` = truth, 가정 G6 — 동기 HOLD 오케스트레이션 미구현): `{ eventId, status(ACCEPTED/REPLAYED/DUPLICATE/REJECTED), accepted(boolean), violations(string[], REJECTED 시만), evaluation }`. `evaluation`(평가된 경우만)=`{ decision(PASS/REPORT — advisory 파생값), alertCount, firedRuleCodes[], screened(boolean) }`. WLF 실패는 인입 실패로 전파하지 않고 `screened=false`로만 표기(가정 G10, best-effort).

### 2.2 Screening API (Public) — 설계서 §10·§15.2·§15.7

| 메서드 | 경로 | scope | 멱등 | 설명 | DB |
|---|---|---|---|---|---|
| POST | `/api/v1/aml/screen` | `aml:screen:evaluate` | Y | 실시간 WLF/제재/PEP screening(온보딩·수취인·출금주소) | `aml_screening_results` |
| GET | `/api/v1/aml/screenings/{screeningId}` | `aml:screen:evaluate` | — | screening 결과 조회 | `aml_screening_results` |

> **WLF 스크리닝 대상 = 해외송금 + 국내송금 양당사자(sender + receiver)(hanpass-ph 데모 정합)**: 송금계열 2 product — 해외송금(`CROSS_BORDER_REMITTANCE`, `remit-svc` cross-border)·국내송금(`DOMESTIC_TRANSFER`) — 거래는 송금인(sender = 회원 본인, `targetType=CUSTOMER`)과 수취인(receiver = 상대방, `targetType=COUNTERPARTY`)을 **각각 1건씩** screen 한다(수취국 PH/VN/ID 제재 = 진양성). receiver 스크리닝은 워치리스트 receiver 엔트리(aml-svc Flyway V26)와 매칭하며 `subjectIdentity`(§3.2) 4필드(NAME/NATIONALITY/GENDER/DOB)는 주체 무관 균일(COUNTERPARTY 미보유 필드는 reveal stub 이 빈 값) — 국내송금 receiver 에도 동일 적용된다. 국내송금 receiver 식별은 `domesticTransfer.creditAccount.accountHolderName`(이름) + 상대방 국가(A6, 기본 `PH`)로 해결하고, sender 스크리닝과 동일 `transactionReference` 로 키잉되어 STR party-aware receiver lineage(계약 1·6)가 소비한다. 회원가입·월렛충전·월렛결제 등 잔여(비-송금계열) 거래는 sender(`CUSTOMER`)만 screen. 엔진 도메인 비변경 — 데모/시뮬레이터/시드 한정.

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
| GET | `/api/v1/aml/alerts/{alertId}/related-transactions?page=&size=` | `aml:case:read` | — | **알림 발동 근거 거래 서버 페이징**(요구2·A8) — 발동 룰이 결정하는 윈도우(주체 velocity 윈도우 / 영업일 현금 합산 / 단건 그룹)의 근거 거래 **전수**를 페이징(20행 evidence 표시 캡과 별개). 응답 DTO §3.4d `RelatedTransactionsResponse` | `aml_alerts`(+`aml_canonical_events`) |

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
| GET | `/api/v1/bo/aml/tm-scenarios/{scenarioCode}` | `aml:admin:policy` | — | **TM 시나리오 정의 read model**(AML-TM-002). bo-api BFF가 엔진 active `parameters`/`dsl` 또는 non-prod stub template을 `ScenarioDefinition{family, severity, fields[]}`로 디코드해 반환한다(DTO §3.4c). HIGH_RISK_CORRIDOR는 방향·고위험 국가·회랑 윈도우·건수/금액 임계 필드를 노출하고, SIGNAL 계열은 시그널 토글 필드를 노출한다. NUMBER/AMOUNT 임계 필드는 위험등급별 차등 임계(`CriterionField.thresholdsByGrade`, §3.4c)를 동반 노출한다. raw PII 없음, 설정 조회 전용. | 정책 store(read model) |

> bo-api 소유 집계(read-only 파생, raw PII 미노출). STR 건수 등 tipping-off 민감 항목은 준법감시 전담 scope 한정 투영(설계서 §19.2a). 엔진 `GET /aml/customers/{customerRef}/profile`(CDD-002)·`/risk`를 결합하며 별도 영속 테이블 없음.

### 2.6 Internal API (엔진 간) — 설계서 §6.1·§12.3·D-07

| 메서드 | 경로 | 호출자 | 설명 | DB |
|---|---|---|---|---|
| POST | `/internal/v1/aml/fds-escalations` | `fds-svc` | FDS fraud case → `STR_REVIEW`/`alert` escalation 수신(body §3.10 `FdsEscalationRequest` → `FdsDecisionCommand` 어댑팅, `fraudCaseRef`=멱등키, 응답 `{ alertId, accepted }`). SQS `aml-fds-decision` 큐 경로(`FdsDecisionConsumer`)와 **동일 usecase·동일 멱등(DB partial UNIQUE)·동일 감사**(T11/AML-ENG-05). 인증 = **API key + HMAC**(ingest 필터 `AmlIngestAuthenticationFilter` 차용, ADR 2026-06-15 D2; mesh mTLS 는 P8 보강). scope 강제는 호출자(fds-svc) 평면 책임(가정 A5). | `aml_alerts`(source_origin=FDS) |
| GET | `/internal/v1/aml/customers/{customerRef}/risk` | `fds-svc` | AML high-risk/WLF 상태 조회(FDS risk group 전파용). public `GET /api/v1/aml/customers/{customerRef}/risk`와 동일 `AssessRiskUseCase`·`CustomerRiskResponse` 재사용(가정 A6), 최신 RA 등급 단독(WLF 병합 미정의 → 후속). 미존재 시 404 `AML.NOT_FOUND`. 인증 = **API key + HMAC**(가정 A1, mesh mTLS 는 P8 보강). | `aml_risk_scores`,`aml_screening_results` |
| POST | `/internal/v1/aml/screen` | 내부 onboarding mesh | 내부 서비스용 동기 screening. public `POST /api/v1/aml/screen`와 동일 `ScreenSubjectUseCase`·`ScreenRequest`/`ScreeningResponse` 재사용(가정 A6), `Idempotency-Key` 헤더 필수(가정 A4·공개 경로 일관). 인증 = **API key + HMAC**(가정 A1, mesh mTLS 는 P8 보강). | `aml_screening_results` |
| POST | `/internal/v1/aml/pii/reveal` | `bo-api` | 마스킹 PII reveal 정본(입력 `targetRef`/`field`/`reason` → 출력 `value`=이 요청 한정 transient cleartext). `field` 도메인 7종(`NAME`/`DOC`/`ACCOUNT`/`WALLET`/`NATIONALITY`/`GENDER`/`DOB`, §1.6, 2026-06-29 확장). 인증 = **API key + HMAC**(ingest 필터 `AmlIngestAuthenticationFilter` 차용, T3/AML-ENG-03·ADR 2026-06-15 D2). 엔진측 `RAW_DATA_ACCESS` 감사 1건(마스킹 detail). 역참조 미존재·복호화 실패 시 **503 `AML.SCREENING_UNAVAILABLE`**(fail-closed). scope `aml:pii:reveal` 강제는 호출자(bo-api) 평면 책임(§1.6, 가정 A5). mesh mTLS 는 배포계층(P8) 보강. | `aml_pii_vault`(가역암호 vault, DB §3.21) |

### 2.7 Admin API (bo-api 전용) — 설계서 §13~§14·§16

#### Watchlist / 명단 (§10)
| 메서드 | 경로 | scope | 4-eyes | 설명 | DB |
|---|---|---|---|---|---|
| GET | `/api/v1/admin/aml/watchlist-sources` | `aml:admin:watchlist` | — | source 목록 | `aml_watchlist_sources` |
| POST | `/api/v1/admin/aml/watchlist-sources` | `aml:admin:watchlist` | — | source 등록 | `aml_watchlist_sources` |
| POST | `/api/v1/admin/aml/watchlist-sources/{sourceCode}/imports` | `aml:admin:watchlist` | — | import 업로드(diff 생성, DRAFT) | `aml_watchlist_entries` |
| POST | `/api/v1/admin/aml/watchlist-sources/{sourceCode}/imports/{version}:apply` | `aml:admin:watchlist` | 🔒4-eyes | import 적용(active_version 승격) | `aml_watchlist_sources` |
| POST | `/api/v1/admin/aml/watchlist-sources/{sourceCode}/sync` | `aml:admin:watchlist` | — (auto-apply, 4-eyes 아님) | **실 무료 공개 제재명단(OFAC SDN·UN Consolidated) 동기화** — fetch→StAX 파싱→멱등 upsert(외부키 `external_ref`)→**auto-apply**(actor `system:sanctions-sync`, 공개·권위 소스는 사람 승인 없이 `active_version` 승격)→DELISTED 정리→버전 prune(최근 2개)→freshness 갱신. 외부망 장애는 예외 미전파(fail-safe, 200+`outcome=FAILED`) — freshness 미갱신 시 48h 게이트가 스크리닝 fail-closed(설계 의도). 응답 `WatchlistSyncResult`(sourceCode·outcome(APPLIED/UNCHANGED/FAILED)·activeVersion·ingestedCount·delistedCount·prunedCount·lastImportedAt). 스케줄러(기본 03:20 UTC, `SanctionsImportScheduler`) 일일 자동 + 본 엔드포인트 수동 트리거. | `aml_watchlist_sources`,`aml_watchlist_entries` |
| GET | `/api/v1/admin/aml/watchlist-entries` | `aml:admin:watchlist` | — | 명단 항목 조회(masked) | `aml_watchlist_entries` |

> **bo-api 위임(§10.4).** BO 화면 수동 트리거는 `POST /api/v1/bo/aml/watchlist-sources/{sourceCode}/sync`(scope `aml:admin:watchlist` or `BO_SUPER_ADMIN`, `AmlWatchlistController`) → `AmlEngineClient`로 위 엔진 `.../{code}/sync`에 순수 위임한다(응답 `WatchlistSyncResponse` 미러, 운영자 감사 `WATCHLIST_IMPORT_APPLIED`·trigger MANUAL). 제재명단 수집은 엔진 전용 표면이라 **비위임(stub) 모드는 fail-closed 503 `AML.ENGINE_UNAVAILABLE`**(위조 성공 카운트가 48h freshness 게이트를 잘못 갱신하는 것 방지, 4-eyes 계약 대상 아님).

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

> bo-api의 `GET /api/v1/bo/aml/tm-scenarios/{scenarioCode}`는 운영자 화면용 BFF read model이다. 엔진 저장 권위는 위 Admin API의 정책 store이며, 변경 적용은 기존 `:activate` 4-eyes(`TM_SCENARIO`) 흐름만 사용한다.

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

#### CTR/STR 룰·임계 관리 (§14 — bo-api 관리 콘솔, CTR/STR 모니터링 통합 P4)
> **read overview(`GET /api/v1/bo/aml/stats/report-rules`, §3.6a)와 별개**: 아래는 **룰 활성화 파이프라인·규제 임계 4-eyes 변경**을 담당하는 관리 엔드포인트다(통계 개요는 집계 read-only, 여기는 상태 전이·정책 변경). 실제 구현: `AmlReportRuleController`·`AmlCtrThresholdController`(bo-api).

| 메서드 | 경로 | scope | 4-eyes | 설명 | DB |
|---|---|---|---|---|---|
| GET | `/api/v1/bo/aml/report-rules` | `aml:admin:policy` | — | CTR/STR 룰 카탈로그 목록(`AmlReportRuleCatalog` 10종, `status` ACTIVE/DRAFT — EXECUTED 활성화 반영). 응답 `ReportRuleView[]` | (코드 카탈로그) |
| GET | `/api/v1/bo/aml/report-rules/{ruleCode}` | `aml:admin:policy` | — | 룰 상세(자연어 설명·evaluationMode·actions·reasonCode) | (코드 카탈로그) |
| POST | `/api/v1/bo/aml/report-rules/{ruleCode}:activate` | `aml:admin:policy` | 🔒4-eyes(`REPORT_RULE`) | 룰 활성화 DRAFT→ACTIVE(202 + approvalId, **시뮬레이션 요약 동반**). `STR_MANUAL`은 컴플라이언스 수동 전용 → 파이프라인 활성화 거부(`400`, "rule is manual-only and cannot be activated") | `aml_approvals`(bo-api 스텁 4-eyes) |
| GET | `/api/v1/bo/aml/ctr-thresholds` | `aml:admin:policy` | — | 통화별 CTR 규제 임계 목록(EXECUTED 반영값 우선·변경 대기 표기). 응답 `CtrThresholdView[]`(§3.22a) | `aml_ctr_thresholds` |
| GET | `/api/v1/bo/aml/ctr-thresholds/{currency}` | `aml:admin:policy` | — | 통화별 CTR 임계 상세 | `aml_ctr_thresholds` |
| POST | `/api/v1/bo/aml/ctr-thresholds/{currency}:update` | `aml:admin:policy` | 🔒4-eyes(`CTR_THRESHOLD`) | CTR 규제 임계 변경(202 + approvalId). **규제값 hot-reload 우회 불가** — 결재 EXECUTED 시에만 반영(BR-501) | `aml_ctr_thresholds`,`aml_approvals`(bo-api 스텁 4-eyes) |

> 4-eyes `REPORT_RULE`·`CTR_THRESHOLD`는 **bo-api 애플리케이션 계층 subjectType**(`AmlApprovalDtos.SubjectType` 19→21종, 승인선 `POLICY_ADMIN` / 기능정의서 §03 §4.2 REPORTING_OFFICER·COMPLIANCE 배정)이며 aml-svc 엔진 `ApprovalSubjectType`(19종)·`aml_approvals.subject_type` CHECK(19종)에는 없다(DB §5.16 후주). 감사 이벤트코드는 bo-api `bo_audit_logs`에 3종 추가(`CTR_THRESHOLD_CHANGE_SUBMITTED`·`REPORT_RULE_ACTIVATE_SUBMITTED`·`AMLC_SUBMISSION_DELEGATED`, bo-api V6).

> **bo-api AML-STAT 집계 BFF**: BO 화면은 엔진 admin 원천을 직접 호출하지 않고 `GET /api/v1/bo/aml/stats/str`(STR 보고 퍼널·지연·미보고, COMPLIANCE 전담), `GET /api/v1/bo/aml/stats/ctr`(CTR 보고 퍼널, STR 통계와 동일 DTO 규격), `GET /api/v1/bo/aml/stats/scenarios`(TM 룰 효과성), `GET /api/v1/bo/aml/stats/report-rules?family=CTR|STR`(룰군별 룰 개요 — CTR·룰 효과성 통계 메뉴는 `family=CTR`(CTR 룰 개요 CTR_SINGLE·CTR_DAILY), STR·룰 효과성 통계 메뉴는 `family=STR`(STR 룰 개요 8종). `family=STR`은 STR 퍼널과 동일한 tipping-off 전담(COMPLIANCE) 게이트 — 비전담 `403 AML.FORBIDDEN_SCOPE`, CTR은 열림. `hitCount30d`/`draftCount`는 라이브 CTR/STR DRAFT store(비운영 stub 폴백) `firedRules` 위 실집계·소스 없으면 0(seed 없음), `status`는 EXECUTED 활성화 반영 ACTIVE/DRAFT)을 호출한다. 네 endpoint는 bo-api 소유 read aggregate(API §9 경계)이며 응답은 집계 카운트만 포함한다. 응답 DTO §3.6a `ReportRuleOverviewRow`.

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
> aml-svc 엔진 admin surface. scope `aml:admin:high-risk-registry`(부록 E v7.0 미정의 — 결정2의 `aml:admin:policy` vs T2 본문 `aml:admin:high-risk-registry`, IRA `aml:admin:ira` 동형으로 후자 채택, 가정 A1). bo-api는 본 엔진 API를 프록시(후속 T13). 분류 기준(criteria)은 엔진 seed 정책(read-only, 가정 A2 — criteria 변경 API 미정의 → PUT 변경 대상은 참조 리스트로 한정). tenant 단위 정책(workspace 차원 없음, 가정 A3). 참조 리스트 3종 `PRODUCT`/`VASP`/`HIGH_NET_WORTH`(가정 A4), tier 2종 `HIGH`/`VERY_HIGH`(가정 A5). 분류 일치 대상은 결재 EXECUTED 시점에 엔진 RA가 등급을 **강제 상향 재평가**(VERY_HIGH→PROHIBITED·HIGH→HIGH floor, 상향만 보장, 가정 A6·A7). **(v9.12)** PRD §12-B.6 ③ 승인 히스토리 탭은 **공통 결재함 `GET /api/v1/bo/aml/approvals?subjectType=HIGH_RISK_REGISTRY`(bo-api 소유, §9) 재사용** — HRR 전용 히스토리 엔드포인트는 신설하지 않는다(subjectType=`HIGH_RISK_REGISTRY`로 필터, ApprovalDto §3.7).

| 메서드 | 경로 | scope | 4-eyes | 설명 | DB |
|---|---|---|---|---|---|
| GET | `/api/v1/admin/aml/high-risk-registry` | `aml:admin:high-risk-registry` | — | 분류 기준(criteria, read-only) + 참조 리스트(PRODUCT/VASP/HIGH_NET_WORTH) 조회 | `aml_high_risk_registry`,`aml_high_risk_registry_items` |
| PUT | `/api/v1/admin/aml/high-risk-registry/reference-lists/{listType}` | `aml:admin:high-risk-registry` | 🔒4-eyes(`HIGH_RISK_REGISTRY`) | 참조 리스트 변경 상신(전체 교체, `UPDATE\|<version>` subjectRef, 전체 staged payload drift guard) — 결재 EXECUTED 시 적용 + 일치 고객 RA 강제 상향 재평가 트리거 | `aml_high_risk_registry`,`aml_high_risk_registry_items`,`aml_approvals` |

#### PEP (정치적 주요인물) 경영진 승인 상신 (§5.16 `PEP_APPROVAL`·§5.33 `PEP_INDIVIDUALS`)
> aml-svc 엔진 admin surface. bo-api `AmlPepApprovalService`가 본 엔진 API로 위임(`app.delegate.aml-svc.base-url` 설정 시; 미설정·운영 프로파일은 fail-closed). 본 엔드포인트는 **상신(maker)만** 담당 — 승인/반려는 별도 신설 없이 공통 결재함 `POST /api/v1/admin/aml/approvals/{id}:approve|:reject`가 `PEP_APPROVAL`도 동일 라우팅(aml-svc `ApprovalDispatchService` → `approvePepApproval`). 결재 EXECUTED 시 ① `aml_customers.is_pep=TRUE`·`pep_approval_id` 증거 링크 ② `PEP_INDIVIDUALS` 참조 리스트 등재(tier HIGH, 기존 항목 보존+추가) ③ RA 위험등급 **HIGH 강제 상향**(PROHIBITED 아님 — PEP는 거래 허용+EDD)이 폐루프로 반영(HRR 강제 재평가 재사용). `makerId`는 위임 본문 운반(bo-api가 현재 운영자=maker로 채움), maker≠checker는 승인 시 엔진 재검증. raw PII 미운반(`customerRef`는 토큰, §19.2).

| 메서드 | 경로 | scope | 4-eyes | 설명 | DB |
|---|---|---|---|---|---|
| POST | `/api/v1/admin/aml/customers/{customerRef}:submit-pep-approval` | `aml:case:update` | 🔒4-eyes(`PEP_APPROVAL`, 승인선 `EXECUTIVE_APPROVAL`) | PEP 경영진 승인 상신. body `{makerId, reason?}`, 응답 `202 {approvalId, customerRef, subjectType:PEP_APPROVAL, approvalLine:EXECUTIVE_APPROVAL, status:SUBMITTED}`. 승인 EXECUTED 시 is_pep·PEP_INDIVIDUALS 등재·RA HIGH 상향 폐루프 | `aml_customers`,`aml_high_risk_registry_items`,`aml_approvals` |

#### CDD/EDD checklist·periodic review 정책 (§2.6·§13.1·§13.4·§13.5)
| 메서드 | 경로 | scope | 4-eyes | 설명 | DB |
|---|---|---|---|---|---|
| GET | `/api/v1/admin/aml/cdd/checklists` | `aml:admin:policy` | — | CDD/EDD checklist 정책 목록(항목·필수여부·증빙요건) | (정책 store) |
| POST | `/api/v1/admin/aml/cdd/checklists` | `aml:admin:policy` | — | checklist 정책 신규(DRAFT) | (정책 store) |
| PUT | `/api/v1/admin/aml/cdd/checklists/{id}` | `aml:admin:policy` | 🔒4-eyes | checklist 변경 적용(§13.4 'CDD checklist 변경' 결재) | `aml_approvals` |
| GET | `/api/v1/admin/aml/cdd/periodic-review-policy` | `aml:case:read` | — | **현재 위험등급별 재이행주기 정책 조회**(등급별 재확인 주기·유예일·적용 상태). 응답 `EnginePeriodicReviewPolicy`(§3.11, `cadenceByGrade`/`gracePeriodDays`/`status` ∈ APPLIED·PENDING/`effectiveFrom`). bo-api `GET /api/v1/bo/aml/cdd/periodic-review-policy` 위임 원천. **구현됨**(`CddController`) | `aml_periodic_review_policy` |
| PUT | `/api/v1/admin/aml/cdd/periodic-review-policy` | `aml:admin:policy` | 🔒4-eyes | periodic review 주기 설정 변경(등급별 재확인 주기) | `aml_approvals`,`aml_periodic_review_policy` |
| GET | `/api/v1/admin/aml/cdd/due-for-review?windowDays=&riskGrade=` | `aml:case:read` | — | **재심사 임박/경과 회원 큐**(등급별 cadence 투영). `windowDays`(기본 30)·`riskGrade`(옵션) 필터, `nextReviewDueAt` 오름차순. 응답 `EngineDueRow[]`(§3.11, `customerRef`(회원번호)/`riskGrade`/`nextReviewDueAt`/`cadenceMonths`). bo-api `GET /api/v1/bo/aml/customers/due-for-review` 위임 원천. raw PII 미노출(§19.2). **구현됨**(`CddController`) | `aml_customers`,`aml_periodic_review_policy` |

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
| `targetRef` | string | 대상 ref(DB `target_ref`, 회원번호/대상 식별자) |
| `targetType` | enum | DB §5.23 target_type(`CUSTOMER`/`ENTITY`/`COUNTERPARTY`/`CRYPTO_ADDRESS`) |
| `status` | enum | §5.5 screening_status. **API 별칭 `POTENTIAL_MATCH`는 `POSSIBLE_MATCH`로 정규화**(DB §5.5 주석) |
| `score` | number | 유사도 |
| `scoreBreakdown` | object | name/dob/country/document/address/relationship(§10.3). **hanpass-ph 정합**: `member-svc zoloz_aml_screening`(`hit_results`→후보·항목별 점수, `risk_level`→`riskGrade`, `total_hits`→matched 카운트, `decision`→`status`)를 본 분해로 정규화. **가중 분모 = 전체 가중치 합(name 0.55+date 0.10+country 0.10+document 0.15+address 0.05+relationship 0.05 = 1.0)** — overall=`Σ(weight·score)/sumOfWeights()`이며 미제공 컴포넌트는 분자 기여 0·분모 유지(이름만 완전일치=0.55). **데모 스텁(bo-api `StubNameMatcher`, aml-svc 미가동·비위임) 점수분해는 name/dob/country 서브셋만 산출**(엔진은 6 컴포넌트 — 의도적 단순화·overall은 동일 분모로 1:1) |
| `riskGrade` | enum | §5.2(평가 가능 시) |
| `reasonCodes` | array<string> | `reason_codes` (예: `NAME_EXACT_MATCH`,`SANCTIONS_NAME_SIMILARITY`,`DOB_MATCH`,`COUNTRY_MATCH`). 이름 유사 코드는 명단군별 일반형 **`<LISTTYPE>_NAME_SIMILARITY`**(예 `SANCTIONS_NAME_SIMILARITY`/`PEP_NAME_SIMILARITY`/`INTERNAL_NAME_SIMILARITY`, listType 미상 시 `NAME_SIMILARITY`)로 발급(tokenSet≥0.6 또는 edit≥0.85), 완전일치 시 `NAME_EXACT_MATCH`. 일치 여부 플래그만 — 원문 이름/생년/국적 값 미포함 |
| `requiredActions` | array<string> | `MANUAL_REVIEW`/`EDD_REVIEW`/... |
| `matchedEntries` | array<string> | 후보 entry_id(masked). **하위호환 유지** — `matchedCandidates`와 병존(기존 소비자 보존) |
| `matchedCandidates` | array<object> | **가산(additive) 필드.** 매칭 후보 출처계보. 각 원소 `MatchedCandidate`(아래 표) — `matchedEntries`의 각 entry_id를 `aml_watchlist_entries`+`aml_watchlist_sources` 조인으로 enrich한 best-effort 파생값. **raw PII 미포함**(masked entryId·출처·버전·점수·토큰개수만) |
| `matchedRules` | array<object> | 적용된 WLF 룰 참조 `{ ruleCode, threshold }`(파생값, DB `rule_version` 기준 투영). 단수 `ruleVersion`과 구분 |
| `subjectIdentity` | object | **가산(additive) 필드(bo-api WLF 매치 상세 투영).** reveal 게이트 대상 식별정보 메타 `SubjectIdentity`(아래 표) — 대상 식별자(`targetRef`) + reveal 가능 필드 키 목록만. **raw PII(이름·국적·성별·생년 원문) 미포함** — 원문은 `aml:pii:reveal`+사유+`RAW_DATA_ACCESS` 경로(§1.6, `POST /internal/v1/aml/pii/reveal` §2.6)로만 노출. **CUSTOMER·counterparty 대상 모두 `[NAME, NATIONALITY, GENDER, DOB]` 4필드 균일**(주체 무관). 주체가 보유하지 않는 필드(예 수취자=상대방의 성별·생년월일)는 reveal stub 이 빈 값(`""`)을 반환한다(placeholder 아님) |
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
| `reasonCodes` | array<string> | Y | 후보별 일치 사유 코드(명단군 + scoreBreakdown factor≥0.8 파생) — `SANCTIONS_NAME_SIMILARITY`/`PEP_NAME`/`NAME_SIMILARITY` + `DOB_MATCH`/`NATIONALITY_MATCH`. 일치 여부 플래그만, 원문 생년/국적 값 미포함 |
| `matchedTokenCount` | number | Y | 매칭 토큰 개수(masked 통계) |
| `classification` | string | Y | 공개 분류값(제재 프로그램/PEP 카테고리, provider·listType 기반 best-effort). **인물 식별 PII 아님** — 명단 기재명/국적/생년 cleartext 미포함(노출은 `aml:pii:reveal`+`RAW_DATA_ACCESS` 경로) |

`SubjectIdentity`(WLF 매치 상세의 reveal 게이트 메타 — `subjectIdentity` 값). **raw PII 미포함** — 마스킹 토큰 + reveal 가능 필드 키만 노출하며, 운영자는 `targetRef` + 한 `field`를 reveal 엔드포인트(`POST /internal/v1/aml/pii/reveal`, §2.6)에 제출해 이 요청 한정 transient cleartext 를 얻는다:

| 필드 | 타입 | nullable | 설명 |
|---|---|---|---|
| `targetRef` | string | N | 대상 식별자(예: `MBR-24010501`). reveal 키의 일부 |
| `fields` | array<string> | N | 이 대상의 reveal 가능 필드 키. 허용값 = `NAME`/`NATIONALITY`/`GENDER`/`DOB`(전체 7종 중 식별정보 서브셋, §2.6 `field` 도메인). **CUSTOMER·counterparty 모두 `[NAME, NATIONALITY, GENDER, DOB]` 4필드 균일**(주체 무관). 주체가 보유하지 않는 식별필드는 reveal stub 이 빈 값(`""`)을 반환한다. **원문 값은 미포함** — 키 목록만 |

### 3.3 RiskAssessmentRequest → `POST /api/v1/aml/risk-assessments/evaluate` (DB `aml_risk_scores`)

| 필드 | 타입 | R | 설명 |
|---|---|---|---|
| `targetRef` | string | R | customer/entity ref |
| `targetType` | enum | R | `CUSTOMER`/`ENTITY` |
| `modelCode` | string | — | 미지정 시 tenant 기본 모델 |
| `factors` | object | — | factor 입력 override(§11.1). **hanpass-ph 데모 정합**: 1차 RA는 회원가입(`member-svc` 온보딩) 시점 1회 수행하며 factor=회원 KYC 속성 `nationality`(고위험국)·`occupation`·`sourceOfFunds`·`kycLevel`(거래 기준 factor는 1차 제거 — 2차 활동 재평가·TM 소관). 엔진 factor catalog 비변경 — 데모/시뮬레이터/시드 한정 |
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
| `geo` | object | — | 접속/IP 위치 `{ country, latitude, longitude }`. 위도/경도는 보조 참고값이며 필수 아님 |
| `riskSignals` | object | — | FDS와 동일한 거래 보조 신호 `{ memberAgeDays, accountChangedWithinHours, deviceChangedWithinHours, manyToOnePattern, oneToManyPattern, electionPeriod, regionalRegistrationSpikeCount, bulkCashAmountBase }` |

> FDS/TM 공통 거래 payload 동기화: AML TM은 FDS 탐지 결정과 같은 실시간 거래 payload를 사용하되, CTR/STR 사후 보고 목적의 룰로 평가한다. 보조 신호는 TM feature snapshot에 `geo.country`, `geo.latitude`, `geo.longitude`, `customer.accountAgeDays`, `account.changedWithinHours`, `device.changedWithinHours`, `behavior.manyToOnePattern`, `behavior.oneToManyPattern`, `election.active`, `election.registrationSpikeCount`, `election.bulkCashAmountBase`로 기록한다.

응답 `TransactionEvaluateResponse`: `{ evaluated: true, alerts: [ { alertId, alertType(enum TM_SCENARIO/SCREENING/RA/FDS_ESCALATION/VENDOR_ALERT — 본 API가 정본, DB §5.18 `alert_type` 1:1), scenarioCode(§5.6), severity(LOW/MEDIUM/HIGH/CRITICAL), status(§5.7), evidence } ] }`.

### 3.4a AlertDto → `GET /api/v1/aml/alerts/{alertId}` (DB `aml_alerts` §3.10 10컬럼+감사)

| 필드 | 타입 | 설명 |
|---|---|---|
| `alertId` | string(uuid) | DB `alert_id` PK |
| `alertType` | enum | §5.18 `alert_type`(`TM_SCENARIO`/`SCREENING`/`RA`/`FDS_ESCALATION`/`VENDOR_ALERT`). **API 정본, DB 1:1** |
| `scenarioCode` | enum | §5.6 `tm_scenario`(TM_SCENARIO 타입만, DB `scenario_code`, nullable) |
| `ruleCode` | string\|null | **발동 룰 표시 코드**(bo-api `AlertSummary`/`AlertDetail` 매핑 필드, `AmlTmController` 목록·상세 응답). 정상 CTR/STR 룰 경로는 `AmlReportRuleCode`(카탈로그 §11 10종)의 `.name()`(예 `STR_VELOCITY_CASH`). 엔진이 top-level `ruleCode` 없이 `scenario_code`만 실은 **레거시 시나리오 경로 알림**(예 `STRUCTURING`)은 `AmlReportRuleCode`로 파싱되지 않으므로 **발동 룰 표시가 비지 않도록** `evidence.trigger.scenarioCode` → 엔진 `scenarioCode` 문자열로 **폴백**한다(bo-api `AmlTmService.engineRuleCode`, 코드=truth). `AmlReportRuleCode` enum 계약은 무변경(레거시 코드는 문자열로만 표시). 정상·레거시 모두 부재하면(비-TM 알림 SCREENING/RA/FDS_ESCALATION/VENDOR_ALERT) null. JSON 직렬화 형태는 `string\|null`(enum `.name()`과 동일 — bo-web `ruleLabel` 문자열 폴백 보유) |
| `targetRef` | string | 대상 고객/법인 ref(회원번호/대상 식별자, DB `target_ref`, nullable) |
| `transactionRef` | string | 관련 거래 ref(DB `transaction_ref`, nullable). hanpass-ph: charge_order_id/transaction_id/transfer_number/wallet_transaction_id |
| `severity` | enum | §5.19 `alert_severity`(`LOW`/`MEDIUM`/`HIGH`/`CRITICAL`) |
| `status` | enum | §5.7 `alert_status` **6종**: `DETECTED`/`TRIAGED`/`CASE_OPENED`/`DISMISSED`/`ESCALATED`/`STR_RECOMMENDED`(DB CHECK 6종. 이후 조사·보고·종결은 `aml_cases.status` 인계) |
| `evidence` | object | **TM 알림 상세 데이터모델(DB §3.10 정본). 시나리오 계열(ScenarioFamily)별 증거.** ① 트리거 `{ scenarioCode, strIndicator(데이터 신호 STR_001~015 ← remit.str_indicators), description }`. **THRESHOLD 계열**: ② 집계 패턴 `{ measure, window, count, amount, currency, threshold, appliedRiskGrade, countThreshold, distinctCounterparties, counterpartyThreshold }`(예 "5BD 9건 분할충전 합계 ₱480,000") — `measure`는 **서술 라벨(문자열)**, `threshold`는 **적용된 등급의 effective threshold**(합산 ≥ 임계 시나리오; 건수 기반 시나리오는 미포함)이고 `appliedRiskGrade`(string\|null)는 위험등급별 차등 임계(§3.4c)가 발동 velocity에 적용된 등급(base 임계 적용 시 null), **`countThreshold`(건수 기반 시나리오 STRUCTURING/MULE_NETWORK 등)·`distinctCounterparties`/`counterpartyThreshold`(다상대 시나리오 ROUND_TRIPPING/MULE_NETWORK) = nullable superset**(해당 축 임계를 가진 시나리오에만 채워짐) + ③ `relatedTransactions[]`(`{ transactionRef, subjectRef(거래 주체 회원번호), channel, amount, currency, corridor, counterpartyRef, occurredAt, fdsDecisionRef }`) — **발동 시나리오 첫 velocity 윈도우의 형제거래 다건**(집계를 구성한 거래들 = 다수 상대방; 윈도우 조회 불가·빈 결과 시 평가 거래 단건 폴백). **SIGNAL 계열**(SHELL_MERCHANT·TRADE_MISPRICING·CRYPTO_OFF_RAMP·INTERNAL_OVERRIDE_ABUSE): 집계 대신 ② `signals[]`(`{ code, label, description }` — 발화한 탐지 신호 = 시나리오 정의의 TOGGLE 신호; 거래집계 미사용). ④ `fundGraph`(자금그래프 funnel 미니뷰). **CTR/STR 룰 경로 변형(코드=truth, aml-svc `Ctr/StrEvaluationService`→`TmAlertEvidenceAssembler`):** 룰 카탈로그(§11)로 발동한 TM 알림은 위 THRESHOLD 계열과 **키 동형**이되 ① 트리거를 `{ ruleCode, strReasonCode(STR만), description }`로 싣고(레거시 시나리오 경로는 `scenarioCode` — `ruleCode` 폴백은 위 행 참조), ② 집계는 **실측 윈도우 집계**(CTR=(member, banking day) 현금 채널 합산·실측 건수 — 하드코딩 count=1 제거 / STR=주체 rolling 24h 건수·합산; `threshold`/`thresholdMet`은 수치 임계 룰 `STR_VELOCITY_CASH`·`STR_KYC_INCOME_MISMATCH`·CTR만, 그 외 룰은 미포함·조작 금지), ③ `relatedTransactions[]`는 **주체 윈도우 형제거래**(최신순, 표시 캡 20; 빈 윈도우면 평가 거래 단건 폴백), ④ `fundGraph`는 윈도우 거래가 있으면 canonical 이벤트 파생 실 그래프(`source=CANONICAL_EVENTS`)·무거래 시만 `PLACEHOLDER_NO_TRANSFER_LINKS` + `features`(velocity 스냅샷 `{ velocityCount24h, velocitySumPhp, amountPhpEq }`)·명단 룰 `watchlistMatch`. 윈도우 조회 실패는 fail-safe(발동 유지·현행 수준 evidence). 회원번호/거래번호는 업무 식별자로 노출하고 이름·계좌·지갑 등 raw PII 는 금지 |
| `subject360Ref` | string | 대상 360° 통합뷰 링크 키(= `targetRef`/`customerRef`) → `GET /api/v1/bo/aml/subjects/{customerRef}/360`(§2.5a). nullable |
| `sourceOrigin` | enum | §5.20 `source_origin`(`AML`/`FDS`/`VENDOR`) |
| `externalAlertRef` | string | 외부 벤더 alert 식별자(DB `external_alert_ref`, nullable, `source_origin=VENDOR`일 때) |
| `createdAt` | string(date-time) | 생성 시각 |
| `updatedAt` | string(date-time) | 최종 수정 시각 |
| `aggregationSummary` | object\|null | **목록(브라우즈) 응답 한정 triage 프리뷰 집계.** TM 알림 **목록**(`GET /api/v1/bo/aml/alerts`, §2.5a → bo-api `AlertSummary`) 응답에서만 채워지는 가산 필드. `evidence`(트리거·집계 패턴)에서 목록 시점 파생(N+1 없음·행별 evidence 조립 회피)하며, **raw PII 미포함(집계 수치·라벨만)**. 단건 상세(`AlertDto`)는 `evidence` 전문을 제공하므로 본 요약은 생략 가능(null). 원소 `AggregationSummary`(아래 표) |

> raw PII 미노출. `targetRef`/`transactionRef`는 업무 식별자로 노출하고, 이름·계좌·지갑 등 원문 PII 는 reveal/hash 정책을 따른다. 감사 컬럼(`created_by`/`updated_by`/`trace_id`/`data_scope`)은 응답에서 생략.

`AggregationSummary`(`aggregationSummary` 객체 — TM 알림 목록 triage 프리뷰 집계). **전 필드 nullable(집계 파생·best-effort).** `evidence`의 트리거(`strIndicator`)·집계 패턴(`measure`/`window`/`threshold`/`count`/`amount`/`currency`)·`relatedTransactions[]` 에서 목록 시점 파생하며, raw PII는 일절 포함하지 않는다(집계 수치·라벨만):

| 필드 | 타입 | nullable | 설명 |
|---|---|---|---|
| `strIndicator` | string | Y | 데이터 신호 STR 지표(`STR_001`~`STR_015` ← remit.str_indicators). `evidence.트리거.strIndicator` 파생 |
| `windowLabel` | string | Y | 집계 윈도우 라벨(예 "5BD"). `evidence.집계패턴.window` 파생 |
| `measure` | number | Y | 집계 측정 항목(예 분할충전 합계, threshold와 동일 수치축). `evidence.집계패턴.measure` 파생 |
| `threshold` | number | Y | 적용 임계값 = **적용 등급의 effective threshold**(위험등급별 차등 임계 §3.4c 발동 시 해당 등급 임계, 미적용 시 base). `evidence.집계패턴.threshold` 파생(데이터 신호, 규제 임계 교체 아님) |
| `thresholdMet` | boolean | Y | 임계 충족 여부(measure ≥ threshold 파생) |
| `relatedCount` | number | Y | 연관 거래 건수(masked 집계). `evidence.집계패턴.count`/`relatedTransactions[]` 파생 |
| `relatedAmount` | number | Y | 연관 거래 총액(masked 집계). `evidence.집계패턴.amount` 파생 |
| `currency` | string | Y | 합계 통화(ISO). `evidence.집계패턴.currency` 파생 |
| `dominantChannel` | string | Y | 우세 채널(충전/국내/해외). `relatedTransactions[].channel` 최빈값 파생 |

### 3.4d RelatedTransactionsResponse → `GET /api/v1/aml/alerts/{alertId}/related-transactions` (aml-svc, 발동 근거 거래 서버 페이징)

알림의 **발동 근거 거래 전수**를 서버 페이징한다(요구2·A8). 발동 룰이 근거 윈도우(주체 velocity 윈도우 / 영업일 현금 합산 / 단건 그룹)의 dimension·window 를 결정하고, `evidence.relatedTransactions[]`(표시 캡 20)이 아닌 **전체 근거 거래 집합**을 반환한다. 응답 형상은 aml-svc `AlertController.RelatedTransactionsResponse`(port `QueryAlertRelatedTransactionsUseCase`, usecase `AlertRelatedTransactionsService`)와 1:1:

| 필드 | 타입 | 설명 |
|---|---|---|
| `rows` | array<`RelatedTransactionDto`> | 근거 거래 행(아래 표). 최신순(occurredAt desc) |
| `page` | integer | 0-based 현재 페이지 |
| `size` | integer | 페이지 크기(기본 50) |
| `totalCount` | integer(long) | 전체 근거 거래 수(캡 없음) |
| `ruleCode` | string\|null | 근거 윈도우를 결정한 발동 룰 코드 |
| `window` | string\|null | 근거 윈도우(예 rolling 24h / banking day) 라벨 |
| `dimension` | string\|null | 집계 축(예 subject velocity / cash sum / single-transaction group) |

`RelatedTransactionDto`(`rows` 원소 — 마스킹 ref + 수치 집계만, §19.2):

| 필드 | 타입 | 설명 |
|---|---|---|
| `transactionRef` | string | 거래 업무 식별자(마스킹/토큰) |
| `counterpartyRef` | string\|null | 상대방 ref(마스킹 토큰) |
| `direction` | string\|null | 거래 방향(입금/출금 등) |
| `amount` | number | 거래 금액(base) |
| `currency` | string\|null | 통화(ISO 4217) |
| `channel` | string\|null | 채널(충전/국내/해외) |
| `corridor` | string\|null | corridor(송금국-수취국) |
| `occurredAt` | string(date-time) | 거래 발생 시각 |
| `fdsDecisionRef` | string\|null | 연계 FDS 판정 ref |

> raw PII 미포함 — 회원번호·거래번호는 업무 식별자로 노출하고 이름·계좌·지갑 등 원문 PII 는 금지(§1.6·§19.2). party 식별정보(송금인·수취인 신원)는 §3.2 `subjectIdentity` 규약을 상속한다 — 응답에는 마스킹 토큰(`targetRef`/`counterpartyRef`)과 reveal 가능 필드 키만 실리고, 원문은 `aml:pii:reveal` scope + 사유 + `RAW_DATA_ACCESS` 감사(`POST /internal/v1/aml/pii/reveal` §2.6)로만 산출한다(fail-closed).

### 3.4b Subject360Dto → `GET /api/v1/bo/aml/subjects/{customerRef}/360` (bo-api 집계 read model, DB §3.16)

| 필드 | 타입 | 설명 |
|---|---|---|
| `customerRef` | string | 대상 키(= `member.member_id`/회원번호). domestic-svc varchar(36) join 정규화 |
| `identity` | object | 신원·CDD 요약(`member-svc`) `{ subjectType(string: `customer`/`transaction-only` — 고객 마스터 보유 여부), displayNameMasked(string: 표시명 마스킹 토큰), kycStatus, country, … }`(hash/token) |
| `pepStatus` | object\|null | **PEP(정치적 주요인물) 상태 요약**(DB §3.3 `aml_customers.is_pep`/`pep_approval_id`, V24). `null` = 거래 전용 주체. `{ isPep(boolean — 경영진 승인 EXECUTED 여부), pepApprovalStatus(string\|null: 진행 중 `PEP_APPROVAL` 결재 상태 `SUBMITTED`/`EXECUTED`/`REJECTED`/null), pepApprovalId(string(uuid)\|null — 확정 결재 증거 링크) }`. 비-PEP은 `isPep=false`. raw PII 미포함(상태·토큰만) |
| `riskSummary` | object\|null | 위험·활동 요약. `null` = 거래 전용 주체(고객 마스터 없음·RA 미산정). `{ riskGrade(§5.2), riskScore, factorBreakdown, nextReviewDueAt, reviewCadenceMonths(integer\|null — 등급별 재이행주기 정책(§3.22) 파생 재확인 주기, 회원 상세 '다음 재심사 기한'·임박 배지 표시), mandatoryHighRisk(boolean — 당연고위험 강제 상향 여부), highRiskRegistryReason(**array&lt;string&gt;** — 당연고위험 레지스트리 사유, 단수 아님), screeningStatus(zoloz `risk_level`/`decision` 파생) }`. PEP 확정 시 `riskGrade`=HIGH 강제 상향(PROHIBITED 아님 — 거래 허용+EDD) |
| `transactionFeed` | array<object> | `tx-history-svc` 통합 이력(충전/국내/해외 타임라인 — `transactionRef`·`channel`·`amount`·`currency`·`corridor`·`direction`·`status`(string optional: `DECIDED`/`MONITORED`/null — 거래 처리 상태)·`occurredAt`). stub/빈 배열 가능 |
| `fundGraph` | object | `wallet-svc` `transfer_links` 자금그래프(funnel — 노드/엣지 요약, token). `source=PLACEHOLDER_NO_TRANSFER_LINKS` 가능(자금이체 링크 미연동) |
| `caseStrSummary` | object | 케이스·STR 건수 요약. **STR 건수는 준법감시 전담 scope 한정 투영(tipping-off §19.2a)** |
| `assembledAt` | string(date-time) | 데이터 신선도 — read model 조립 시각(nullable) |

> read-only 집계 파생. raw PII 미노출(token/hash·마스킹). 엔진 `GET /aml/customers/{customerRef}/profile`·`/risk` + canonical events(transaction.*) + relationships(`USES_ACCOUNT`/`REPEATED_PAYEE`)를 결합하며 별도 영속 테이블 없음(DB §3.16).
>
> **insight/assessment(결론 톤·헤드라인·근거)는 본 응답에 포함되지 않는다.** 대상 화면의 조사 결론(`conclusionTone`·`headline`·`engineReasons[]`·`derivedReasons[]`·`recommendation`)은 **bo-web 클라이언트가 Subject360 단면(알림·RA·자금 집중도 등)에서 로컬 파생**한다(`bo-web/lib/aml-subject-insight.ts`). API/bo-api 계약은 원천 단면(riskSummary·transactionFeed·fundGraph·caseStrSummary)만 제공하고, 톤·문구 합성은 화면 책임이다.

### 3.4c TM 시나리오 정의 — velocity DSL 노드 문법 · ScenarioDefinition/CriterionField (TM-002)

> **TM 시나리오 정의 계약(코드=truth).** 엔진은 `aml_tm_scenarios.dsl`(JSONB)을 `TmCondition` 트리로 컴파일하고(`aml-svc TmScenarioDslParser`/`TmCondition`), bo-api BFF(`GET /api/v1/bo/aml/tm-scenarios/{scenarioCode}`, §2.5a)는 active `parameters`/`dsl`(또는 non-prod stub 템플릿)을 `ScenarioDefinition{family, severity, fields[]}`로 디코드한다(`bo-api ScenarioDslCodec`/`ScenarioTemplates`). raw PII 없음(설정값만).

**velocity DSL 노드 문법(closed grammar, `aml_tm_scenarios.dsl`)** — 노드 type은 `and`/`or`/`not`/`cmp`/`velocity`/`always` 6종만 허용(미지 type·미지 연산자·깊이>16·자식>64는 parse 거부). `velocity` 노드는 윈도우·차원 집계(`velocity.<count|sum>.<dimension>.<window>` feature)에 대한 임계 비교다:

```jsonc
{
  "type": "velocity", "agg": "count", "dimension": "subject", "window": "7d",
  "op": ">=", "value": 5,
  // optional — 위험등급별 차등 임계(강화) 오버라이드
  "thresholds": { "HIGH": 3, "PROHIBITED": 1 }
}
```

- `thresholds`(optional) — 거래 주체 고객의 위험등급별 **강화 임계 오버라이드**. 키는 `RiskGrade` 4종(`LOW`/`MEDIUM`/`HIGH`/`PROHIBITED`, 대문자) **한정**, 값은 numeric **한정**. **closed grammar** — 미지 등급 키 또는 비숫자 값은 parse 거부(`TmDslException`). 미설정 등급은 base `value`로 **fallback**, `thresholds` 키 자체 부재 시 모든 등급이 base `value`(하위호환 — 등급 도입 전 시나리오와 동일 동작).
- **평가 규칙**: 평가 시 거래 주체 고객의 위험등급으로 effective threshold를 선택한다(`Velocity.effectiveThreshold`). 고위험일수록 강화(보통 낮은 임계)되어 더 일찍 발동한다. 고객 미조회/등급 미상(`customer.riskGrade` 스냅샷 부재)이면 base `value`를 적용한다. 평가는 순수·결정적(스냅샷+트리 동일 ⇒ 결과 동일).

**`ScenarioDefinition`**(bo-api `GET /bo/aml/tm-scenarios/{scenarioCode}` 응답): `{ scenarioCode, displayName, version, status, severity(§5.19), family(ScenarioFamily — THRESHOLD/SIGNAL 계열), fields[] }`. `fields[]` 원소 `CriterionField`(아래 표).

`CriterionField`(가이드 폼 필드 — FE↔BE 1:1 계약 키 `key` = `ScenarioDslCodec` 평탄 parameters 키):

| 필드 | 타입 | 설명 |
|---|---|---|
| `key` | string | FE↔BE 계약 키(평탄 parameters 키와 1:1) |
| `label` / `helpText` | string | 한국어 표시 라벨·도움말(업무 용어, 내부 DSL/변수명 비노출) |
| `type` | enum | `FieldType`(`NUMBER`/`AMOUNT`/`DURATION`/`SELECT`/`COUNTRY_MULTI`/`SIGNAL_TOGGLE` 등) |
| `value` | object | 현재값(`number`/`string`/`array<string>`/`boolean`) |
| `unit` | string | 타입별 단위(AMOUNT: `KRW`/`USD`/`PHP`, DURATION: `HOURS`/`DAYS`) |
| `options` | array | SELECT/COUNTRY_MULTI 후보 `FieldOption{value,label}` |
| `required` | boolean | 필수 여부 |
| `thresholdsByGrade` | object\|null | **위험등급별 차등 임계(가산·additive, 직렬화 NON_NULL)**. `Map<RiskGrade, 숫자>` — **NUMBER/AMOUNT 타입 한정**으로만 적용, 다른 타입 필드는 `null`/생략(하위호환 — 등급 없는 필드는 기존과 동일). 미설정 등급은 base `value` fallback. 값은 `value`와 동일 형상·단위의 평이한 숫자(PII 없음). 엔진 velocity 노드의 optional `thresholds`로 컴파일된다 |

**평탄 parameters 왕복 계약(`ScenarioDslCodec`)** — `thresholdsByGrade`는 평탄 `parameters` 맵에서 키 인픽스 **`<key>.thresholds.<GRADE>`**(예 `minAmount.thresholds.HIGH`)로 왕복한다. `toParameters`가 등급별 오버라이드를 이 키로 평탄화하고, `decode`가 이 키들을 `CriterionField.thresholdsByGrade`로 복원한다(`parameters` key→value 계약 불변·additive). 오버라이드가 없으면 키 자체가 부재(하위호환 — 등급 없는 필드는 등급 없이 유지).

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
| `reportDeadlineAt` | string(date-time) | — | **보고 기한(파생값·Policy Pack 옵션, 설계서 §14.4·§14)** — 기한은 활성 **regulatory Policy Pack**이 결정한다. ▷ **PH_AMLC pack(hanpass-ph 정본, 코드=truth)**: `CTR`=거래일 +5영업일 17:00 PHT(`BankingCalendar.dueAt`, `CTR_DUE_BUSINESS_DAYS=5`, Asia/Manila 영업일 캘린더·§3.22b) — CTR 발동 시 서버가 `due_at`(DB §3.12)에 freeze. `STR`=의심확정(트리거)일 +5영업일. ▷ **KR default pack(§14.4 기존)**: `STR`=결재승인일 +영업일 3일 / `CTR`=거래일 +30일. 두 pack 은 상호 배타 옵션(테넌트별 활성 pack 1개) — hanpass-ph 데모/운영은 PH_AMLC. 서버가 활성 pack·`approvedAt`/`transactionDate`/영업일 캘린더 기준 계산, 클라이언트 직접 계산 불필요. |
| `slaStatus` | enum | — | **SLA 상태(파생값, 설계서 §14.4)** — `ON_TIME`/`DUE_SOON`(D-3 이내)/`OVERDUE`. bo-web 화면 배지(D-3 경고·기한 초과 표시)에 사용. |

`ReportSubmitRequest`(🔒4-eyes): `{ makerId, reason, approvalLine: "REPORTING_OFFICER" }`.

`ReportRejectRequest`/`ReportCancelRequest`(🔒4-eyes, §2.7 `:reject`/`:cancel`): `{ makerId, reasonCode(string ●, 사유 코드 필수), reason(string △), approvalLine: "REPORTING_OFFICER" }` — `:cancel`로 CTR 제외 처리(§14.3) 시 `ctrExemptionCode`(●) 병기. **종결(`REJECTED`/`CANCELLED`) 시 `reasonCode`는 `aml_regulatory_reports.closure_reason_code`(DB §3.12)에 영속**되어 미보고 사유 분포(§2.7 `unreported-reasons`)의 집계 원천이 된다(T4 AML-ENG-04 — **확정**).

`DelayBucket`(§2.7 `reports/stats/str-delay` 응답, T4 AML-ENG-04 — **확정**): `{ bucketCode(enum: ON_TIME/D1_3/D4_7/D8_14/D15_PLUS), label(string), count(long) }` — 5종 버킷 0-fill 고정 배열(분포 모양 안정). 보고 행·PII 미노출(집계 카운트만). 지연 기준 = candidate(`created_at`)→제출(`submitted_at`) 경과의 법정 SLA(§14.4 BR-006, STR=결재승인+3영업일) 대비 상대 일수. SUBMITTED 미도달 건은 지연 모수에서 제외(미보고 사유 분포로 분류).

`UnreportedReason`(§2.7 `reports/stats/unreported-reasons` 응답, T4 AML-ENG-04 — **확정**): `{ reasonCode(string — `closure_reason_code` 코드값 또는 legacy 미영속 = `UNSPECIFIED`), count(long) }` — count 내림차순·reasonCode 사전순 정렬. 보고 행·PII 미노출.

#### 3.6a 룰군별 룰 개요 (bo-api AML-STAT, `GET /api/v1/bo/aml/stats/report-rules`)

`ReportRuleOverview`: `{ scope("TENANT"), family("CTR"|"STR"), period("7d"|"30d"|"90d"), rules(ReportRuleOverviewRow[]), generatedAt(ISO-8601), cacheTtlSeconds(int, 45) }` — CTR·룰 효과성 통계 메뉴는 `family=CTR`(CTR 룰 개요), STR·룰 효과성 통계 메뉴는 `family=STR`(STR 룰 개요)을 조회. `family=STR`은 STR 퍼널과 동일한 tipping-off 전담(COMPLIANCE) 게이트 — 비전담 `403 AML.FORBIDDEN_SCOPE`.

`ReportRuleOverviewRow`: `{ ruleCode(string — 안정 룰 코드, family=CTR→{CTR_SINGLE,CTR_DAILY}, family=STR→8종), family("CTR"|"STR"), reportType(enum CTR|STR), reasonCode(string|null — STR 사유 코드, CTR 룰은 null), evaluationMode(enum INLINE_AND_ASYNC|ASYNC_ONLY), actions(string[] — 발동 시 액션 CTR_REPORT/STR_FLAG/RESTRICT/EDD_TRIGGER), status(enum ACTIVE|DRAFT — EXECUTED 활성화 반영), naturalLanguage(string — 한국어 설명), hitCount30d(long — 기간 내 발동 건수, 라이브 DRAFT store `firedRules` 실집계·소스 없으면 0), draftCount(long — 기간 내 DRAFT 발동 건수), lastFiredAt(ISO-8601|null — 최근 발동 시각), tuningRecommended(bool — 튜닝/활성화 검토 권고) }` — 카탈로그 순서 고정. 발동/DRAFT 카운트는 비운영 stub 폴백 라이브 store(P2/P3) 위 실집계, seed 없음(운영 미결선 시 0).

> **재제출(RESUBMIT)·기각/취소 통제.** `SUBMISSION_FAILED` 건의 정정 후 재제출은 **별도 엔드포인트 없이 기존 `POST .../reports/{reportId}:submit`(🔒 `STR_SUBMIT`/`CTR_SUBMIT`) 신규 결재 사이클을 재사용**하며 서버가 `resubmitCount`를 증가시킨다(연동 §6.2). 보고 기각/취소(`REJECTED`/`CANCELLED`) 전이는 **전용 엔드포인트 `POST .../reports/{reportId}:reject`/`:cancel`(§2.7)** 로 수행하며, CTR 제외 처리(`CANCELLED`+`ctrExemptionCode`)를 포함해 **사유 코드 필수 + 보고책임자 결재(4-eyes, `REPORTING_OFFICER`, 자기승인 금지)** — 설계서 §14.1a/§14.3 정본.

### 3.7 ApprovalDto (Admin, DB `aml_approvals`)

| 필드 | 타입 | 설명 |
|---|---|---|
| `approvalId` | string(uuid) | PK |
| `subjectType` | enum | `WLF_DECISION`/`FP_WHITELIST`/`RA_MODEL`/`TM_SCENARIO`/`RISK_OVERRIDE`/`EDD_CLOSE`/`STR_SUBMIT`/`CTR_SUBMIT`/`TRAVEL_RULE_EXCEPTION`/`WATCHLIST_IMPORT`/`COUNTRY_RISK`/`POLICY_PACK`/`SECRET_CHANGE`/`RELATIONSHIP_REJECT`/`CHECKLIST_CHANGE`/`PERIODIC_REVIEW_CHANGE`/`IRA_SUBMIT`/`HIGH_RISK_REGISTRY`/`PEP_APPROVAL` (총 **19종**. `TM_SCENARIO`=`tm-scenarios/{code}:activate`🔒 결재. `CHECKLIST_CHANGE`=CDD/EDD checklist 정책 변경. `PERIODIC_REVIEW_CHANGE`=periodic review 주기 변경. `IRA_SUBMIT`=기관위험평가(IRA) 회차 제출/취소(`SUBMIT`\|`reportId` / `CANCEL`\|`reportId` subjectRef 접두, T1 AML-ENG-01·부록 E v6.0-2 확정). `HIGH_RISK_REGISTRY`=당연고위험 레지스트리 참조 리스트 변경(`UPDATE`\|`<version>` subjectRef, 전체 staged payload drift guard, 결재 EXECUTED 시 적용 + RA 강제 상향 트리거, T2 AML-ENG-02·부록 E v7.0 확정). `PEP_APPROVAL`=PEP(정치적 주요인물) 경영진 승인(승인선 `EXECUTIVE_APPROVAL`, subjectRef=customer_ref, staged payload `tenant\|customerRef\|action=PEP` drift guard, 결재 EXECUTED 시 `aml_customers.is_pep=TRUE`+`PEP_INDIVIDUALS` 등재(tier HIGH)+RA HIGH 강제 상향 폐루프, 거래 허용+EDD). §2.7·PRD §11.1 동기화. DB §5.16 동기화 대상) |
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
| `isPep` | boolean | **PEP(정치적 주요인물) 여부**(DB `aml_customers.is_pep`, V24). 경영진 승인(`PEP_APPROVAL`) EXECUTED 시 TRUE. TRUE면 `riskGrade`=HIGH 강제 상향(거래 허용+EDD) |
| `pepApprovalStatus` | enum\|null | 진행 중/확정 `PEP_APPROVAL` 결재 상태(`SUBMITTED`/`EXECUTED`/`REJECTED`, 미상신=null). 결재함(§3.7 ApprovalDto)에서 파생 |
| `pepApprovalId` | string(uuid)\|null | PEP 확정 결재 증거 링크(DB `aml_customers.pep_approval_id`, 마스킹 불요·식별 PII 아님). 비-PEP은 null |
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

`PeriodicReviewPolicyView`(GET `/cdd/periodic-review-policy`, 엔진 `EnginePeriodicReviewPolicy` / bo-api `PeriodicReviewPolicyView`, DB §3.22 `aml_periodic_review_policy`):

| 필드 | 타입 | 설명 |
|---|---|---|
| `cadenceByGrade` | object | 위험등급별 재확인 주기(개월) `{ LOW, MEDIUM, HIGH, PROHIBITED }`(canonical 등급명 키). 기본 baseline `{ LOW:12, MEDIUM:6, HIGH:3, PROHIBITED:0 }` — **위험할수록 짧게**, 0=즉시 재심사 |
| `gracePeriodDays` | integer | 임박 유예 기간(일, 기본 14) |
| `status` | enum | 적용 상태 `APPLIED`/`PENDING`(변경 상신 후 승인 전=`PENDING`, bo-api stub은 closed-loop fold) |
| `effectiveFrom` | string(date-time)\|null | 현재 정책 적용 시점 |

`DueForReviewEntry`(GET `/customers/due-for-review`, 엔진 `EngineDueRow` / bo-api `DueForReviewEntry`, DB §3.22·`aml_customers.next_review_due_at`):

| 필드 | 타입 | 설명 |
|---|---|---|
| `customerRef` | string | 회원번호(업무 식별자 — raw PII 미운반, §19.2) |
| `riskGrade` | enum | §5.2 risk_grade(LOW/MEDIUM/HIGH/PROHIBITED) |
| `nextReviewDueAt` | string(date-time)\|null | 다음 재심사 기한(`aml_customers.next_review_due_at`) |
| `daysUntilDue` | long | 기한까지 남은 일수(**음수=경과(overdue)**, 0 이상=임박). bo-api 응답 전용 파생(엔진 `EngineDueRow`는 미포함) |
| `cadenceMonths` | integer | 해당 등급의 재확인 주기(개월, 정책 store 파생) |

> 위험등급별 재이행주기는 정책 store(`aml_periodic_review_policy`, DB §3.22)가 정본이며, `nextReviewDueAt`은 RA 가 등급별 cadence 로 산정(`aml_customers.next_review_due_at`)한 캐시다. 회원 프로필/대상 360°의 `reviewCadenceMonths`(§3.9 `CustomerProfileDto`·§3.4b `Subject360Dto.riskSummary`)는 이 정책에서 등급으로 파생한 표시값이다. 정책 변경 폐루프(`PERIODIC_REVIEW_CHANGE` 결재 EXECUTED → 정책 저장 + 등급별 회원 `next_review_due_at` 재계산)는 §10 결재 트리거 등재표 참조.

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

### 3.17 NeutralEventRequest 블록 스키마 → `POST /aml/v1/transaction-events` (코드=truth, feature/aml-neutral-canonical-ingest)

§2.1a 중립 수집 API 의 Party·Amounts·product 블록 상세. 필드는 엔진 domain record(`NeutralParty`·`NeutralAmounts`·`NeutralProductBlocks`)와 1:1. raw PII(성명·계좌·신분증번호)는 수신 경계에서만 존재하고 토큰화·vault 후 소멸(§2.1a PII 경계).

**Party**(`originator`/`counterparty` 공통, `PartyDto`):

| 필드 | 타입 | R | 설명 |
|---|---|---|---|
| `partyReference` | string | — | 당사자 내부 식별자 |
| `partyType` | enum | — | `INDIVIDUAL`/`LEGAL_ENTITY` |
| `nationalIdentityKey` | string | R(originator) | 동일인 식별키(CI/해시). subject 토큰의 원천, 분산·차명 탐지 핵심 |
| `fullNameLatin`/`fullNameLocal` | string | — | 로마자/자국어 성명(WLF·실명확인). **토큰화 후 vault**(PiiField.NAME) |
| `dateOfBirth` | string(date) | — | 생년월일(vault, PiiField.DOB) |
| `gender` | enum | — | `M`/`F`/`X`(vault, PiiField.GENDER) |
| `nationality`/`residenceCountry`/`countryOfBirth` | string(country) | — | ISO 3166-1 alpha-2. `nationality`(vault) WLF factor |
| `phone`/`email` | string | — | E.164/이메일. counterparty 안정키 구성(phone) |
| `identification` | array<object> | — | 신분증 배열. `{ idType, idNumberMasked, idNumberToken, issuingCountry, issueDate, expiryDate }`. `idNumberToken`(또는 masked)은 **vault 만**(PiiField.DOC), payload·응답 미포함(가정 G7) |
| `kyc` | object | — | `{ occupation, sourceOfFunds, sourceOfFundsDescription, kycLevel, kycVerifiedAt, cddDueDate, customerRiskRating }` |

**Amounts**(`amounts`, `AmountsDto`):

| 필드 | 타입 | R | 설명 |
|---|---|---|---|
| `grossAmount`/`grossCurrency` | decimal/currency | R | 고객이 낸 총액·ISO 4217 |
| `netAmount`/`netCurrency` | decimal/currency | — | 수취/정산 금액 |
| `baseAmount`/`baseCurrency` | decimal/currency | R | 규제통화 환산액·CTR 임계 판정. `baseCurrency`=테넌트 규제통화(가정 G3, 불일치 시 422) |
| `reportingAmount`/`reportingCurrency` | decimal/currency | — | 감독기관 보고 기준액 |
| `exchangeRate`/`feeAmount`/`feeCurrency` | decimal | — | 환율·수수료 |

**product 블록**(해당 `product`일 때만 채움):

| product | 블록 | 주요 필드(비-PII 신호) | 엔진 payload 파생 |
|---|---|---|---|
| CROSS_BORDER_REMITTANCE | `remittance` | `purpose`·`payoutMethod`(§7)·`destinationCountry`·`payoutPartner`·`relationshipToBeneficiary`·`counterpartyAccount{accountIdentifierMasked,bankCode,bankName,branch,routingType,routingValue}` | `destinationCountry`·`payoutPartner`·`relationshipToBeneficiary`·`payoutMethod`·`corridor`(origin-dest) |
| DOMESTIC_TRANSFER | `domesticTransfer` | `debitAccount`/`creditAccount{accountIdentifierMasked,bankCode,accountHolderName(PII)}`·`accountHolderNameMatch`·`fundingSourceType` | `accountHolderNameMatch`(차명 STR 신호)·`fundingSourceType` |
| CARD_PAYMENT | `cardPayment` | `panMasked`·`issuer`·`cardScheme`·`domesticInternationalFlag`·`merchantId`·`merchantName`·`merchantCategoryCode`(MCC)·`merchantCountry`·`acquiringCity`·`localAmount`/`localCurrency`·`authorizationCode`·`balanceBefore`/`balanceAfter` | `mcc`·`merchantRef`·`merchantCountry`·`balanceBefore`/`After`(고위험 MCC·pass-through) |
| WALLET_TOPUP | `walletTopup` | `fundingInstrumentType`(§7)·`fundingInstrumentMasked`·`isAutoTopup`·`isManualApproval`·`approverId`·`balanceBefore`/`balanceAfter`·`walletId` | `fundingInstrumentType`(분산충전)·`balanceBefore`/`After`(pass-through)·`walletId` |
| WALLET_PAYMENT | `walletPayment` | `merchantId`·`merchantName`·`merchantType`·`settlementCurrency`·`merchantCategoryCode`·`productType`/`productName`·`paymentInstrument`·`balanceBefore`/`balanceAfter`·`walletId` | `mcc`·`merchantRef`·`balanceBefore`/`After`·`walletId` |

> `panMasked`(BIN+말미4)·`accountIdentifierMasked`·`accountHolderName`은 마스킹/PII 필드로, 엔진 payload 에는 토큰/마스킹 신호만 실린다(§2.1a PII 경계). STR 신호(가정 G5)는 신규 룰코드 신설 없이 기존 룰/시나리오가 소비: 차명계좌=`accountHolderNameMatch`→`STR_THIRD_PARTY`, 분할/취소환불=`STR_STRUCTURED`, pass-through·분산충전=`STR_NO_PURPOSE`·`STR_VELOCITY_CASH`, 동일수취인 집중=TM velocity(counterparty), 고위험 MCC=FDS C1213 결선.

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
| 위험등급별 재이행주기 정책 조회 | `GET /api/v1/bo/aml/cdd/periodic-review-policy` | 엔진 `GET /admin/aml/cdd/periodic-review-policy` 위임(`PeriodicReviewPolicyView`, §3.11). delegation 미설정 시 stub closed-loop fold(상신→`PENDING`→승인→`APPLIED`). scope `aml:admin:policy` |
| EDD 재이행(재심사) 임박 큐 | `GET /api/v1/bo/aml/customers/due-for-review?riskGrade=&windowDays=` | 엔진 `GET /admin/aml/cdd/due-for-review` 위임(`DueForReviewEntry[]`, §3.11). 등급별 cadence·`nextReviewDueAt`·임박일수(`daysUntilDue`, 음수=경과). 마스킹 토큰만(raw PII 미노출). scope `aml:case:read` |
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

## 11. CTR/STR 보고 룰 엔진 계약 (설계서 §14 계열, CTR/STR 모니터링 통합 — 코드=truth)

CTR/STR 모니터링 통합(feature/aml-ctr-str-monitoring, 2026-07-01)이 aml-svc 엔진에 구축한 **보고 룰 엔진**의 규칙·계약 정본. 룰 카탈로그는 코드(`AmlReportRuleCatalog`), 통화 임계·영업일은 DB(§3.22a/§3.22b), 4-eyes 관리는 §2.7 CTR/STR 룰·임계 관리, hanpass-ph 기한은 PH_AMLC pack(§3.6 `reportDeadlineAt`).

### 11.1 BR-403 — 보고 의무 우선순위 (TEMP_FREEZE > STR > CTR)
한 거래가 복수 보고 의무를 유발하면 **TEMP_FREEZE > STR > CTR** 우선순위로 표기한다(`TransactionReportSideEffectRunner.priorityLabels`). TEMP_FREEZE(임시동결)는 CTR/STR 룰 엔진이 직접 생성하지 않는 상위 라벨(제재 매칭 등 별도 경로), STR(의심)이 CTR(현금 임계)보다 우선. 우선순위는 발동 표기·정렬 축이며 각 보고는 독립 DRAFT 로 병존한다(멱등 키 상이).

### 11.2 영업일 캘린더·bankingDayKey·기한 17:00 PHT
`BankingCalendar`(도메인, I/O-free)가 모든 기한 산정을 담당한다 — 앵커 Zone=`Asia/Manila`(PHT, UTC+8, DST 없음). ▷ `bankingDayKey(instant)`=거래 instant 의 PHT 캘린더 일자(정산/집계 축, 주말/공휴일 instant 도 자기 일자로 매핑). ▷ `isBusinessDay(date)`=토/일 아님 AND 공휴일 아님(주말은 코드, 공휴일은 `aml_ph_banking_calendar` §3.22b 조회). ▷ `plusBusinessDays(from,N)`=N영업일 전진(앵커를 먼저 영업일로 정규화). ▷ `dueAt(txnTime,N)`=거래 영업일 +N영업일 **17:00 PHT** Instant. CTR 기한 N=5(`CTR_DUE_BUSINESS_DAYS`), STR 기한=의심확정 +5영업일(PH_AMLC pack, §3.6).

### 11.3 CTR/STR 룰 카탈로그 (`AmlReportRuleCatalog` 10종, 코드=truth)
| ruleCode | family | reportType | evaluationMode | reasonCode | actions | status | 자연어 |
|---|---|---|---|---|---|---|---|
| `CTR_SINGLE` | CTR | CTR | INLINE_AND_ASYNC | — | CTR_REPORT | ACTIVE | 단건 현금거래 PHP환산액이 CTR 임계 이상 |
| `CTR_DAILY` | CTR | CTR | ASYNC_ONLY | — | CTR_REPORT | ACTIVE | 동일 영업일 현금거래 합산이 CTR 임계 이상(다건 보완재) |
| `STR_PEP` | STR | STR | ASYNC_ONLY | PEP | STR_FLAG | ACTIVE | PEP 관련 거래 — STR 검토 플래그 |
| `STR_SANCTION` | STR | STR | INLINE_AND_ASYNC | SANCTION | RESTRICT,STR_FLAG | ACTIVE | 제재 매칭 — **유일 차단(RESTRICT)** |
| `STR_KYC_INCOME_MISMATCH` | STR | STR | ASYNC_ONLY | KYC_MISMATCH | STR_FLAG,EDD_TRIGGER | ACTIVE | 거래금액이 신고소득 대비 과다(기본 배수 5) |
| `STR_STRUCTURED` | STR | STR | ASYNC_ONLY | STRUCTURED | STR_FLAG | ACTIVE | CTR 임계 90~99% 3영업일 연속(스머핑) |
| `STR_NO_PURPOSE` | STR | STR | ASYNC_ONLY | NO_PURPOSE | STR_FLAG | ACTIVE | 목적부재+행동이상 다중(메타룰) |
| `STR_THIRD_PARTY` | STR | STR | ASYNC_ONLY | THIRD_PARTY | STR_FLAG | ACTIVE | 송금 명의≠회원 명의 |
| `STR_VELOCITY_CASH` | STR | STR | ASYNC_ONLY | UNUSUAL_PATTERN | STR_FLAG | ACTIVE | 단기간 현금거래 빈도 이상(기본 건수 5) |
| `STR_MANUAL` | STR | STR | ASYNC_ONLY | MANUAL | STR_FLAG | **DRAFT** | 컴플라이언스 수동 STR(임계 미충족도) — 파이프라인 활성화 거부(§2.7) |

구체 CTR 통화 임계값은 카탈로그가 아니라 per-tenant `aml_ctr_thresholds`(§3.22a, `CtrThresholdPort`). `STR_MANUAL`만 DRAFT(off by default) — `AmlReportRuleCatalog.activeRules()`는 9종.

### 11.4 CTR freeze·집계 (BR-501)
CTR 평가(`CtrEvaluationService`)는 거래의 **freeze 된 서버 파생 PHP환산액(`amountPhpEq`)을 재계산하지 않는다**(BR-501, canonical 이벤트 윈도우의 phpEquivalent 그대로). `CTR_SINGLE`=단건 amountPhpEq ≥ 임계, `CTR_DAILY`=동일 영업일 현금거래 합산 ≥ 임계(다건 보완재). (테넌트,주체,영업일)당 CTR DRAFT 정확히 1건(부분 UNIQUE `ux_aml_ctr_draft`, DB §3.12) — 후속 현금거래는 `report_amount`에 정확히 1회 누적(`accumulateCtr`, 경합 시 재시도). `due_at`=거래 영업일 +5영업일 17:00 PHT(§11.2).

### 11.5 STR 사유코드 UPSERT
STR 평가(`StrEvaluationService`)는 (테넌트,트리거)당 STR DRAFT 정확히 1건(부분 UNIQUE `ux_aml_str_draft`, DB §3.12) — 동일 트리거에서 여러 STR 룰이 발화하면 **제2 DRAFT 를 만들지 않고** 각 사유코드(`StrReasonCode`)를 `str_reason_codes` JSONB 집합에 fold(UPSERT). `STR_SANCTION`만 RESTRICT(차단) 액션 동반.

### 11.6 PII sha256 — eAMLA ProviderSvc 위임 (`amlc_submission_ref`)
eAMLA 제출은 **raw PII 미전송** — 토큰화된 보고 참조만 전달한다. `MockAmlcSubmissionAdapter`(모의 ProviderSvc)가 결정적으로 `amlc_submission_ref = AMLC-{sha256(tenant|reportId|reportType)[..12]}`를 산출(BR-601, 무작위성 없음·데모 재현 가능). 실 eAMLA 연동 시 이 어댑터를 실 ProviderSvc RestClient 로 교체하되 계약(토큰 참조·PII 미전송)은 유지. 위임 이벤트는 bo-api `bo_audit_logs` `AMLC_SUBMISSION_DELEGATED`(bo-api V6)로 감사. 연동 상세 = integration §3.4(AMLC 위임).

---

## 변경 이력

| 일자 | 변경 | 비고 |
| 2026-07-04 | **(H2) 국내송금 양당사자 WLF 스크리닝 역전파(코드=truth, fix/aml-fds-spec-backprop).** **§2.2 Screening API 콜아웃** — WLF 스크리닝 대상 범위를 "해외송금 sender+receiver + 비-cross-border sender-only" → **"해외송금(`CROSS_BORDER_REMITTANCE`) + 국내송금(`DOMESTIC_TRANSFER`) 양당사자 sender(`CUSTOMER`)+receiver(`COUNTERPARTY`)"** 로 확장. sender-only 잔여를 회원가입·월렛충전·월렛결제(비-송금)로 축소(국내송금 제거). 국내송금 receiver 는 수취계좌 명의인/PH fallback best-effort 매칭, `subjectIdentity` 4필드(NAME/NATIONALITY/GENDER/DOB) 주체 무관 균일 동일 적용. 엔진 도메인 비변경 — 데모/시뮬레이터/시드 한정. | aegis-spec. 코드=truth. 근거=aml-svc `NeutralTransactionEventService.RECEIVER_SCREEN_PRODUCTS`(`CROSS_BORDER_REMITTANCE`+`DOMESTIC_TRANSFER`)·`screenCounterpartyBestEffort`(`TargetType.COUNTERPARTY`)·`NeutralTransactionEventServiceTest`(DOMESTIC_TRANSFER co-screen). |
| 2026-07-04 | **(H1) 알림 발동 근거 거래 조회 엔드포인트 역전파(코드=truth, fix/aml-fds-spec-backprop).** (1) **§2.4 TM API 표에 행 추가** — `GET /api/v1/aml/alerts/{alertId}/related-transactions?page=&size=`(scope `aml:case:read`) 발동 근거 거래 서버 페이징(요구2·A8, 발동 룰 윈도우 근거 거래 전수, 20행 evidence 캡과 별개). (2) **§3.4d `RelatedTransactionsResponse` DTO 신설** — 코드 `AlertController.RelatedTransactionsResponse`(rows/page/size/totalCount/ruleCode/window/dimension) + `RelatedTransactionDto`(transactionRef/counterpartyRef/direction/amount/currency/channel/corridor/occurredAt/fdsDecisionRef) 1:1 전사. party 식별정보는 §3.2 `subjectIdentity` 규약 상속(마스킹 토큰 + reveal 가능 필드 키만·raw PII 미포함, 원문은 `aml:pii:reveal`+`RAW_DATA_ACCESS` 경로). | aegis-spec. 코드=truth. 근거=aml-svc `adapter/in/rest/AlertController`(GET related-transactions·`RelatedTransactionsResponse`/`RelatedTransactionDto`)·port `QueryAlertRelatedTransactionsUseCase`·usecase `AlertRelatedTransactionsService`. sass §02-amlSvc 동기화. |
| 2026-07-04 | **중립(canonical) 수집 API 역전파(코드=truth, feature/aml-neutral-canonical-ingest).** (1) **§2.1a 신설** — `POST /aml/v1/transaction-events`(scope `aml:event:write`, 헤더 `Tenant-Id`/`Idempotency-Key`/`X-Trace-Id`) 엔드포인트 행 + 요청 Envelope 스키마 표(공통 15필드) + 상태코드 매핑(202/200/409/422) + 422 검증 규칙 7항(가정 G3 baseCurrency=테넌트 규제통화 fail-closed) + family 매핑 표(5 product → canonical eventType·EventFamily·channelType, 가정 G1 CARD_PAYMENT→transaction 재사용·enum 무확장, WALLET_TOPUP→CASH_IN 만 CTR 현금성) + CTR 순증(net) 규칙(가정 G4 reversal 음수 signed amount) + PII 토큰화 경계(가정 G7/G9) + 응답 계약(가정 G6 accepted+평가요약, HOLD 미구현). (2) **§3.17 신설** — `NeutralEventRequest` Party·Amounts·5 product 블록 스키마 표(엔진 domain record 1:1, STR 신호 결선 가정 G5, 신규 룰코드 없음). 기존 canonical `/api/v1/aml/events`(§3.1)와 별개 공개 수집 표면. | aegis-java-implementer. 코드=truth. 근거=aml-svc `adapter/in/rest/NeutralTransactionEventController`·`application/usecase/NeutralTransactionEventService`·`application/port/in/IngestNeutralTransactionEventUseCase`·`domain/neutral/{NeutralEnums,ProductEventTypeMapper,NeutralEventValidator,NeutralParty,NeutralAmounts,NeutralProductBlocks,NeutralTransactionEvent}`. 정본 요구=`docs/aml-data.md` §2~§9. |
| 2026-07-04 | **TM 알림 목록 서버 페이징 offset 정합(코드=truth, fix/list-server-pagination).** §2.5a `GET /api/v1/bo/aml/alerts`의 `page` 파라미터가 병합·필터 후 **offset(skip=page×size)으로 실제 적용**됨을 명문화 — 기존 구현은 limit만 적용해 모든 page가 첫 페이지를 반환(목록 화면이 전건을 못 보던 결함). 엔진 위임·stub 양 경로 동일 적용, total 메타 없는 배열 응답 불변(bo-web은 반환 길이<size로 마지막 페이지 판정하는 prev/next 페이저). | aegis-java-implementer. 코드=truth. 근거=bo-api `AmlTmService.listAlerts`(skip(page×limit) 엔진·stub 양 경로). |
| 2026-07-04 | **워치리스트 엔트리 브라우즈 조회 확장 역전파(코드=truth, feature/watchlist-entries-browser).** §2.3 `GET /api/v1/bo/aml/watchlist-entries`(위임: 엔진 `GET /api/v1/admin/aml/watchlist-entries`)에 필터 추가 — `name`(이름 토큰 부분일치·대소문자 무시, normalized_tokens), `country`(ISO-2, attributes.country), `addedFrom`/`addedTo`(created_at 범위 — 날짜별 추가분), `version`(수집 버전), 기존 `sourceCode`/`listType`/`status` 유지. 응답을 배열 → **페이징 봉투 `{rows, page, size, totalElements, totalPages}`**(FDS DecisionPage 명명 일관)로 전환, bo-api passthrough(total 유실 방지). 행: normalizedTokens(공개 명단 원문 토큰)·listType·subjectKind·country·nationality·dob·program·version·status·createdAt·externalRef. 실데이터 42,572건 E2E(이름 ABBAS 110·국적 EG 166·복합 2) 정합. | aegis-java-implementer. 코드=truth. 근거=aml-svc `WatchlistAdminController.listEntries`·`WatchlistEntryQueryService`·bo-api `AmlWatchlistController`. DB V10 인덱스(02-aml-db). |
| 2026-07-03 | **레거시 시나리오 알림 발동 룰 표시 폴백(코드=truth, fix/aml-tm-rule-alert-evidence).** §3.4a `AlertDto` 테이블에 **`ruleCode`(string\|null)** 행 신설 — bo-api `AlertSummary`/`AlertDetail` 매핑 필드로, 정상 CTR/STR 룰 경로는 `AmlReportRuleCode.name()`(예 `STR_VELOCITY_CASH`)이고 엔진이 top-level `ruleCode` 없이 `scenario_code`만 실은 **레거시 시나리오 경로 알림**(예 `STRUCTURING`, `AmlReportRuleCode` 미파싱)은 발동 룰 표시가 비지 않도록 `evidence.trigger.scenarioCode` → 엔진 `scenarioCode` 문자열로 **폴백**함을 명문화. `AmlReportRuleCode` enum 계약 무변경(레거시 코드는 문자열로만 표시), JSON 직렬화 형태 `string\|null` 불변(bo-web `ruleLabel` 문자열 폴백 보유로 무변경). bo-api `AlertSummary`/`AlertDetail.ruleCode` 타입을 enum→String 완화(내부 룰 필터·멱등 키는 `.name()` 정합). | aegis-java. 코드=truth. 근거=bo-api `TmDtos.AlertSummary/AlertDetail.ruleCode`(String)·`AmlTmService.engineRuleCode`/`triggerScenarioCode`/`matchesAlertSummary`. **아울러 §3.4a `evidence` 행에 CTR/STR 룰 경로 변형을 명문화** — 룰 카탈로그 발동 알림의 ① 트리거 `{ ruleCode, strReasonCode(STR만), description }`, ② 실측 윈도우 집계(CTR=(member,bankingDay) 현금 합산·실측 건수 / STR=주체 rolling 24h; 수치 임계 룰만 threshold/thresholdMet), ③ `relatedTransactions[]`=주체 윈도우 형제거래(캡 20·빈 윈도우 단건 폴백), ④ `fundGraph`=윈도우 거래 있으면 `CANONICAL_EVENTS` 실 그래프·무거래 시 `PLACEHOLDER` + `features`·`watchlistMatch`, 윈도우 조회 실패 fail-safe. 근거=aml-svc `TmAlertEvidenceAssembler`·`CtrEvaluationService.persistCtrAlert`·`StrEvaluationService.persistStrAlerts`. DB §3.10 동기화. |
| 2026-07-01 | **CTR/STR 모니터링 통합 역전파(코드=truth, feature/aml-ctr-str-monitoring).** (1) **§2.7 CTR/STR 룰·임계 관리 하위표 신설** — `GET/GET{ruleCode}/POST{ruleCode}:activate report-rules`(🔒 `REPORT_RULE`, 시뮬레이션 요약·STR_MANUAL manual-only 거부)·`GET/GET{currency}/POST{currency}:update ctr-thresholds`(🔒 `CTR_THRESHOLD`, hot-reload 우회 불가) 6행 + read overview(§3.6a)와 별개 명시 + subjectType bo-api 애플리케이션 계층 註記. (2) **§3.6 `reportDeadlineAt`** — 기한을 Policy Pack 옵션으로 정정: PH_AMLC pack(CTR 거래일+5영업일 17:00 PHT·STR 의심확정+5영업일, 코드=truth)과 KR default pack(CTR+30일·STR+3영업일 §14.4)을 상호 배타 옵션으로 명시(충돌 해소). (3) **§11 CTR/STR 보고 룰 엔진 계약(§14 계열) 신설** — BR-403(TEMP_FREEZE>STR>CTR), 영업일 캘린더/bankingDayKey/17:00 PHT, 룰 카탈로그 10종 표(CTR_SINGLE·CTR_DAILY + STR 8종 + STR_MANUAL DRAFT), CTR freeze/집계(BR-501)·부분 UNIQUE, STR 사유코드 UPSERT, PII sha256 eAMLA ProviderSvc 위임(`amlc_submission_ref`, BR-601). subjectType §3.7 enum 은 19종 유지(CTR_THRESHOLD/REPORT_RULE=bo-api 계층). | aegis-spec. 코드=truth. 근거=bo-api `AmlReportRuleController`(report-rules)·`AmlCtrThresholdController`(ctr-thresholds)·`AmlReportRuleService`(STR_MANUAL manual-only 거부), aml-svc `domain/report/{AmlReportRuleCatalog,BankingCalendar}`·`domain/enums/{AmlReportRuleCode,StrReasonCode}`·`application/usecase/{CtrEvaluationService,StrEvaluationService,TransactionReportSideEffectRunner}`·`adapter/out/submission/MockAmlcSubmissionAdapter`. DB §3.12/§3.22a/§3.22b/§5.16·integration §3.4·기능정의서 §7/§9.1/§12-B.3 동기화. |
| 2026-07-01 | **AML TM 라이브 인입 룰베이스 평가 정합(코드=truth) — 채널→시나리오 하드매핑 폐기.** (1) **§3.4a `evidence` 집계 패턴** — 건수 기반 시나리오용 `countThreshold`, 다상대 시나리오(ROUND_TRIPPING/MULE_NETWORK)용 `distinctCounterparties`/`counterpartyThreshold`(nullable superset) 추가 + `measure`=서술 라벨(문자열) 명문화. (2) **§3.4a `evidence.relatedTransactions[]`** — "평가 대상 단건"에서 **발동 시나리오 첫 velocity 윈도우의 형제거래 다건**(집계 구성 거래=다수 상대방; 조회 불가/빈 시 단건 폴백)으로 정정. aml-svc `TmEvaluationService`(실 evaluate)·bo-api 데모 라이브 인입 양 경로 정합. (3) **데모(비-prod) 라이브 인입 룰 평가** — bo-api `IngestTestController`→`AmlTmService.ingestLiveTransaction`가 hanpass-ph 시뮬레이터 거래를 주체 rolling 윈도우로 집계해 ACTIVE THRESHOLD 시나리오의 설정 임계(금액/건수/윈도우/다상대) 충족 시에만 `TM_SCENARIO` 알림을 발동/멱등 갱신((tenant,subject,scenario) upsert), 미충족은 미발동(FDS ALLOW 대응). 시나리오 임계는 `ScenarioTemplates`(룰 관리) 단일 정본. raw PII 미포함 불변. | aegis-spec. 코드=truth. 근거=bo-api `AmlTmService`(appendLiveTxn·evaluateLiveScenario·upsertLiveAlert·windowFor)·`IngestTestController`, aml-svc `TmEvaluationService.addRelatedTransactions`(windowPort.findTransactionsForSubject), bo-web `lib/aml-tm.ts` `AmlEvidenceAggregation`·`AmlTmAlertDetailPanel`, `tools/aml-ingest-simulator`(회원 풀 제한). 기능정의서 AML-TM-001 동기화. |
| 2026-06-30 | **데모·시뮬레이터 hanpass-ph 6 거래유형 정렬 — WLF sender+receiver 양방향·RA 회원가입 factor 계약 보강(코드=truth) — 엔진 도메인 무변경.** (1) **§2.2 Screening API** 표 다음에 콜아웃 신설 — 해외송금(`remit-svc` cross-border)은 sender(회원, `CUSTOMER`) + receiver(상대방, `COUNTERPARTY`)를 **각각 1건씩** screen(수취국 PH/VN/ID 제재 진양성, aml-svc V26 receiver 워치리스트), 비-cross-border 거래는 sender만; `subjectIdentity` 4필드 주체 무관 균일·COUNTERPARTY 미보유 필드 빈 값. (2) **§3.3 `RiskAssessmentRequest.factors`** 설명에 1차 RA = 회원가입(`member-svc`) 시점 1회·factor=`nationality`/`occupation`/`sourceOfFunds`/`kycLevel`(거래 기준 factor 1차 제거) 명문화. 6유형 정렬은 데모/시뮬레이터/시드 한정·엔진 enum/factor catalog 비변경. | aegis-spec. 코드=truth. 근거=bo-api `AmlScreeningService`(sender+receiver COUNTERPARTY)·`AmlRaService`(회원 KYC factor)·`AmlTmService.channelFor`, aml-svc V26(receiver 워치리스트), `scripts/demo_ingest.py`·`demo_stream.py`. 기능정의서 §3/§5(v9.18) 동기화. |
| 2026-06-30 | **WLF 매치 상세 `subjectIdentity` 식별정보 4필드 통일(코드=truth) — 주체 무관 균일.** **§3.2 `ScreenResponse.subjectIdentity` 행·`SubjectIdentity.fields`** — reveal 가능 필드 키를 `CUSTOMER=[NAME,NATIONALITY,GENDER]`·`비-customer=[NAME]`(3필드 비대칭) → **CUSTOMER·counterparty 모두 `[NAME,NATIONALITY,GENDER,DOB]` 4필드 균일**로 갱신. **§1.6** WLF 매치 상세 노출 경로 註記도 균일 4필드로 정정(회원=NAME/NATIONALITY/GENDER + 엔트리=NAME/NATIONALITY/DOB 비대칭 제거). 주체가 보유하지 않는 식별필드(예 수취자=상대방의 성별·생년월일)는 reveal stub 이 빈 값(`""`)을 반환(placeholder 아님). reveal 게이트 불변 — `aml:pii:reveal` scope·사유·`RAW_DATA_ACCESS` 감사·BR-007 마스킹 불변, vault 미적재/미보유 필드 fail-closed. raw PII 미포함 불변. | aegis-spec. 코드=truth. 근거=bo-api `ScreeningDetail.subjectIdentity.fields`(CUSTOMER·counterparty 모두 4필드)·reveal stub(미보유 식별필드 빈 값). 기능정의서 §3.1(v9.17) 동기화. |
| 2026-06-30 | **데모(비위임) WLF 스크리닝 reason code·점수분해 계약 정합(코드=truth).** **§3.2 `ScreenResponse`** — (1) `reasonCodes` 설명에 이름 유사 코드의 명단군별 **일반형 `<LISTTYPE>_NAME_SIMILARITY`**(예 `SANCTIONS_NAME_SIMILARITY`/`PEP_NAME_SIMILARITY`/`INTERNAL_NAME_SIMILARITY`, listType 미상=`NAME_SIMILARITY`; tokenSet≥0.6 또는 edit≥0.85) + 완전일치 `NAME_EXACT_MATCH` 병기. (2) `scoreBreakdown` 설명에 **가중 분모 = 전체 가중치 합(name 0.55+date 0.10+country 0.10+document 0.15+address 0.05+relationship 0.05 = 1.0)** 1줄 + **데모 스텁(bo-api `StubNameMatcher`, aml-svc 미가동·비위임) 점수분해 = name/dob/country 서브셋**(엔진=6 컴포넌트, 의도적 단순화·overall 동일 분모 1:1) 주석. raw PII 미포함 불변. | aegis-spec. 코드=truth. 근거=bo-api `StubNameMatcher`(reason `NAME_EXACT_MATCH`/`<listType>_NAME_SIMILARITY`·full weight sum 1.0·name/date/country 서브셋)·`AmlScreeningService`, aml-svc `FuzzyMatchEngine`/`MatchRuleSet`(`sumOfWeights()`) 미러. 기능정의서 §3(v9.16) 동기화. |
| 2026-06-29 | **위험등급별 차등 TM 임계 계약 명문화(코드=truth).** (1) **§3.4c 신설** — TM 시나리오 velocity DSL 노드 문법에 optional `thresholds`(등급 키 `RiskGrade` 4종·값 numeric·미지 키/비숫자 reject=closed grammar·미설정 등급=base `value` fallback) 명문화 + `aml_tm_scenarios.dsl` 예시에 `thresholds` 포함. 평가 규칙(거래 주체 고객 위험등급으로 effective threshold 선택, 고위험=강화, 등급 미상=base) 명시. (2) **§3.4c `ScenarioDefinition`/`CriterionField` DTO 신설** — `CriterionField.thresholdsByGrade`(`Map<RiskGrade,숫자>`, **NUMBER/AMOUNT 한정·가산(additive)·직렬화 NON_NULL**) + 평탄 parameters 키 인픽스 **`<key>.thresholds.<GRADE>`**(예 `minAmount.thresholds.HIGH`) 왕복 계약(`ScenarioDslCodec` toParameters/decode). (3) **§3.4a `evidence` 집계 패턴에 `appliedRiskGrade`(string\|null) 추가** — 등급 override 적용 시만 채워지고 base 적용 시 null, `threshold`=적용 등급 effective threshold 병기. **§3.4a `AggregationSummary.threshold`** 설명을 effective threshold(차등 임계 발동 시 해당 등급 임계)로 1줄 보강. (4) **§2.5a tm-scenarios read model** 설명에 NUMBER/AMOUNT 필드의 차등 임계 동반 노출 명시. Flyway 없음(`aml_tm_scenarios.dsl` JSONB 구조만 확장). | aegis-spec. 코드=truth. 근거=aml-svc `TmScenarioDslParser`(parseThresholdsByGrade·closed grammar)·`TmCondition.Velocity`(thresholdsByGrade·effectiveThreshold)·`TmEvaluationService`(customer riskGrade 1회 조회·appliedRiskGrade)·`AlertEvidence.Builder.appliedRiskGrade`, bo-api `TmDtos.CriterionField.thresholdsByGrade`·`ScenarioDslCodec`(THRESHOLD_GRADE_INFIX)·`ScenarioTemplates`(RAPID_MOVEMENT base ₱1,000,000·HIGH ₱500,000), bo-web `GradeThresholdInputs`·`lib/aml-tm.ts`. DB §3.10(dsl)·plan §12-A.6 동기화. |
| 2026-06-29 | **위험등급별 EDD 재이행주기 조회 surface 명문화(코드=truth).** (1) **§2.7 CDD/EDD 표에 엔진 GET 2종 추가** — `GET /api/v1/admin/aml/cdd/periodic-review-policy`(scope `aml:case:read`, 현재 정책 조회, 응답 `EnginePeriodicReviewPolicy`)·`GET /api/v1/admin/aml/cdd/due-for-review?windowDays=&riskGrade=`(scope `aml:case:read`, 재심사 임박/경과 큐, 응답 `EngineDueRow[]`, 마스킹). PUT 행 DB 열에 `aml_periodic_review_policy`(DB §3.22) 추가. (2) **§9 bo-api 위임 표에 GET 2종 추가** — `GET /api/v1/bo/aml/cdd/periodic-review-policy`(`PeriodicReviewPolicyView`)·`GET /api/v1/bo/aml/customers/due-for-review?riskGrade=&windowDays=`(`DueForReviewEntry[]`, `daysUntilDue` 음수=경과). (3) **§3.11 DTO 신설** — `PeriodicReviewPolicyView`(`cadenceByGrade`{LOW:12,MEDIUM:6,HIGH:3,PROHIBITED:0}·`gracePeriodDays`=14·`status` APPLIED/PENDING·`effectiveFrom`)·`DueForReviewEntry`(`customerRef` 마스킹·`riskGrade`·`nextReviewDueAt`·`daysUntilDue`·`cadenceMonths`) + 정책 store(DB §3.22) ↔ `next_review_due_at` 파생 관계 주석. (4) **§3.4b `Subject360Dto.riskSummary`에 `reviewCadenceMonths`(integer\|null) 추가** — 등급별 재이행주기 정책 파생, 회원 상세 '다음 재심사 기한'·임박 배지 backing. 모두 마스킹/집계, raw PII 미포함. | aegis-spec. 코드=truth. 근거=aml-svc `CddController`(GET periodic-review-policy·due-for-review)·bo-api `AmlCddPolicyController`·`AmlReviewQueueController`·`ReviewQueueDtos.DueForReviewEntry`·`CddPolicyDtos.PeriodicReviewPolicyView`·`AmlCustomerProfileService.reviewCadenceMonths`. DB §3.22(V25)·기능정의서 §12-A.5 동기화. |
| 2026-06-29 | **PEP 상태 회원 상세·대상 360° 노출 가산(코드=truth).** (1) **§3.4b `Subject360Dto`에 `pepStatus` 행 추가**(`{ isPep, pepApprovalStatus, pepApprovalId }`, DB §3.3 `aml_customers.is_pep`/`pep_approval_id` V24 1:1) + `riskSummary` PEP 확정 시 `riskGrade`=HIGH 강제 상향(거래 허용+EDD) 주석. (2) **§3.9 `CustomerProfileDto`에 `isPep`(boolean)·`pepApprovalStatus`(enum\|null)·`pepApprovalId`(uuid\|null) 행 추가** — 회원 상세 PEP 섹션(상태·상신·히스토리) backing. 모두 상태·토큰만, raw PII 미포함. §3.7 `PEP_APPROVAL`(19종) 결재함과 정합. | aegis-spec. 코드=truth. DB §3.3(V24)·§5.16·plan §02 회원 PEP 플로우 동기화. PEP 마이그레이션=V24(WLF pii_vault=V23 별개). |
|---|---|---|
| 2026-06-29 | **PEP 경영진 승인 상신 엔진 엔드포인트 명문화(코드=truth) — prod 위임 경로 폐쇄.** §2 당연고위험 레지스트리 표 다음에 **PEP 경영진 승인 상신 서브섹션 신설**: `POST /api/v1/admin/aml/customers/{customerRef}:submit-pep-approval`(scope `aml:case:update`, 🔒4-eyes `PEP_APPROVAL`·승인선 `EXECUTIVE_APPROVAL`, body `{makerId, reason?}` → `202 {approvalId, customerRef, subjectType, approvalLine, status:SUBMITTED}`). bo-api `AmlPepApprovalService` 위임 계약과 1:1(경로·`{approvalId}` 응답). 상신만 담당 — 승인/반려는 공통 결재함 `:approve`/`:reject`가 `PEP_APPROVAL` 동일 라우팅. 승인 EXECUTED 시 is_pep·`PEP_INDIVIDUALS` 등재(tier HIGH)·RA HIGH 강제 상향 폐루프. | aml-java-implementer. 근거=aml-svc `adapter/in/rest/PepApprovalAdminController`(+`@WebMvcTest` 슬라이스)·bo-api `AmlPepApprovalService`(ENGINE_BASE `/admin/aml/customers`·`:submit-pep-approval`·`engine.get("approvalId")`). §3.7 `PEP_APPROVAL`(19종)·DB §5.16 기등록. |
| 2026-06-29 | **AML WLF PII reveal 식별정보 확장(코드=truth) — `field` 7종 + `subjectIdentity` reveal 게이트.** (1) **§1.6** reveal `field` 도메인을 4종 → 7종(`NATIONALITY`/`GENDER`/`DOB` 추가, 도메인 `PiiField`·`aml_pii_vault.field` CHECK V23 1:1)으로 명문화 + WLF 매치 상세 회원/엔트리 식별정보 노출 경로 註記. (2) **§2.6** reveal 행에 7종 `field` 도메인 표기, vault 참조를 DB §3.x → §3.21 로 정정. (3) **§3.2 `ScreenResponse`에 `subjectIdentity`(가산) 행 추가** + `SubjectIdentity` 서브구조 표 신설(`targetRef` 마스킹 토큰 + `fields` reveal 가능 키 목록, **raw PII 미포함** — CUSTOMER=`[NAME,NATIONALITY,GENDER]`, 비-customer=`[NAME]`). 원문은 reveal 엔드포인트 + scope·사유·`RAW_DATA_ACCESS` 감사로만 산출(fail-closed 불변). | aegis-spec. 코드=truth. 근거=aml-svc `PiiField`(7종)·bo-api `ScreeningDtos.SubjectIdentity`·`PiiRevealDtos.ALLOWED_FIELDS`(7종). DB §5.35/§3.21·기능정의서 §3.1 동기화. |
| 2026-06-27 | **TM 알림 evidence 시나리오 계열별 정합(코드=truth) — SIGNAL 계열 발화 신호.** §3.4a `evidence` 모델을 시나리오 계열(ScenarioFamily)별로 명문화: **SIGNAL 계열**(SHELL_MERCHANT·TRADE_MISPRICING·CRYPTO_OFF_RAMP·INTERNAL_OVERRIDE_ABUSE)은 거래집계 대신 `signals[]`(`{code,label,description}` = 시나리오 정의의 발화 TOGGLE 신호)로 판정 근거 노출(거래집계/관련거래 미사용). **THRESHOLD 계열**은 집계+relatedTransactions 유지, HIGH_RISK_CORRIDOR 는 corridor 를 설정 고위험국가(PH-IR 등)로 구성. "모든 시나리오가 동일 거래집계 증거" 결함 해소 — evidence 가 시나리오 정의와 일치. 전부 마스킹/정책 라벨, raw PII 미포함. | aegis-spec. 코드=truth. 근거=bo-api `AmlTmService.stubStructuredEvidence`(family-aware)·`firedSignalsFor`. |
| 2026-06-27 | **TM 알림 회원·거래번호 식별자 노출 강화(코드=truth).** §3.4a `evidence.relatedTransactions[]` 원소 스키마에 `subjectRef`(마스킹 토큰 = 알림 subject 회원번호, nullable) 추가 — 관련 거래내역 각 행이 거래번호 + 회원번호를 함께 노출(이 거래들이 해당 회원의 거래임을 명시). `AlertSummary.transactionRef`(§3.4a 기존 필드)를 목록 응답에서도 채움(대표/트리거 거래번호, 상세와 동일 파생). 전부 마스킹 토큰(cust-***/txn-***), raw PII 미포함. | aegis-spec. 코드=truth. 근거=bo-api `AlertSummary.transactionRef`·`stubStructuredEvidence` relatedTransactions.subjectRef. |
| 2026-06-27 | **WLF 매칭 후보 판단 근거 강화(코드=truth) — `MatchedCandidate`에 `classification` 추가 + `reasonCodes` 후보별 채움.** §3.2 `MatchedCandidate` 표에 `classification`(공개 분류값=제재 프로그램/PEP 카테고리, provider·listType best-effort, **인물 식별 PII 아님**) 행 신설. `reasonCodes` 설명을 "현재 null"→"후보별 일치 사유 코드(명단군 + scoreBreakdown factor≥0.8 파생: SANCTIONS_NAME_SIMILARITY/PEP_NAME/NAME_SIMILARITY + DOB_MATCH/NATIONALITY_MATCH, 원문 생년/국적 값 미포함)"로 갱신. cleartext 명단 기재명/국적/생년은 **계속 미노출**(노출은 `aml:pii:reveal`+`RAW_DATA_ACCESS` 경로). | aegis-spec. 코드=truth. 근거=bo-api `ScreeningDtos.MatchedCandidate`·`AmlScreeningService.classificationFor/candidateReasonCodes`. |
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
