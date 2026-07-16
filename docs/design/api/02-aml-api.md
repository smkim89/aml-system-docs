# AML Platform API 명세서 (aml-svc · hanpass-ph)

> **시스템 그라운딩**: 본 명세는 **hanpass-ph AML RegOps** 단일 운영 도메인을 대상으로 한다. 결제 거래는 hanpass-ph 5유형(`remit`(해외송금)·`domestic`(국내이체)·`wallet`(지갑: charge(충전)/pay(결제)/withdraw(출금)))이며, crypto·trade-finance·PG·ecommerce·marketplace·B2B 등 가상 advanced domain은 본 명세에서 다루지 않는다(EventFamily enum의 폐쇄 allow-list 잔존 family는 내부 리플레이 fail-safe 용이며 외부 ingest 표면에는 노출하지 않는다, §3.1).
> 정본: `.claude/skills/_shared/target-architecture.md` (4서비스 모노레포 · 멀티테넌시 tenant/workspace/data-scope · raw PII 미저장 마스킹 · 4-eyes · 규제 Policy Pack STR/CTR · bo-web→bo-api만, 엔진 직접호출 금지).
> 입력 진실: `docs/software/02-amlSvc-sass.md` v1.x(유스케이스·port·API group §15.7·§16 배포 모델·온보딩 프로비저닝 상태머신) + `docs/design/db/02-aml-db.md` v1.x(테이블·컬럼·enum 정본 — `aml_tenants.deployment_model`/`onboarding_status`/`infra_ref` §3.1·§5.28/§5.28a/§5.28b 포함, 구 `isolation_mode` V17a/V17b 폐기).
> 공통 inbound 인증 정본: [`00-common-machine-auth.md`](00-common-machine-auth.md) (wire v2 canonical request·credential version·durable nonce·전환/회전).
> 책임 서비스: `services/aml-svc` (Java 25, Spring Boot 3.5.x, 헥사고날, `com.aegis.aml`). 컨트롤러 정본: `services/aml-svc/src/main/java/com/aegis/aml/adapter/in/rest`(AmlEventController·ScreeningController·AlertController·RiskController·WatchlistAdminController·TmScenarioAdminController·ApprovalController 등). 참조: `docs/design/api/01-fds-api.md`(배포 모델·온보딩 FDS 패턴 정본).
> 본 명세의 식별자·필드·enum은 실제 컨트롤러·DTO 및 DB 설계서 §3(테이블)·§5(enum)와 **1:1 동기화**한다(추측 금지). bo-api 소유 서비스·온보딩 엔드포인트(§3.16·§5·§9)는 aml-svc 엔진 API(§2)에 미노출.
> **운영 테넌트**: 데모·운영 단일 테넌트는 `tenant_demo`(= hanpass-ph). 멀티테넌트 라우팅(`Tenant-Id` 헤더)은 코드 truth로 유지하되, 본 명세의 예시는 단일 운영 테넌트 `tenant_demo`(hanpass-ph)를 기준으로 한다(가상 다서비스 예시 금지).

## 0. API 표면 구분 (3-plane)

설계서 §15(외부 연동) + §6.1(정본 매핑)에 따라 AML API는 3개의 plane으로 분리한다.

| Plane | base path | 호출자 | 인증 | 비고 |
|---|---|---|---|---|
| **Public API** (서비스 연동) | `/api/v1/aml/...`, `/aml/v1/...`, `/api/v1/evidence/aml/...` | hanpass-ph 트랜잭션 마이크로서비스(`member-svc`(회원/CDD)·`walletchg-svc`(충전)·`domestic-svc`(국내이체)·`remit-svc`(해외송금)·`wallet-svc`(지갑)·`inbound-svc`(인바운드)) | API Key+HMAC wire v2([공통 정본](00-common-machine-auth.md)) / OAuth2 / mTLS (§15.7, D-13) | event ingest·중립 거래 ingest·screening·RA·TM·evidence |
| **Internal API** (엔진 간) | `/internal/v1/aml/...` | `fds-svc`(fraud escalation/risk), bo-api(PII reveal), 내부 scheduler/onboarding caller(screen) | API Key + HMAC wire v2-only([공통 정본](00-common-machine-auth.md)); 모든 endpoint가 scope를 재검사하고, escalation은 exact `fds-svc`+body/header dataScope, PII reveal은 exact `bo-api`를 추가 강제한다. risk/screen은 각 행의 scope가 caller capability 경계다. mesh mTLS는 P8 보강 | fds↔aml event 연계(D-07 event 우선), risk/screen/PII |
| **Admin API** (운영 콘솔) | `/api/v1/admin/aml/...` | `bo-api`만 (bo-web은 bo-api 경유) | BO edge 세션/JWT+RBAC+data-scope, bo-api→aml-svc는 별도 machine-auth v2 credential | 명단·정책·case·결재·감사·evidence 관리 |

> **bo-web은 Admin API를 직접 호출하지 않는다.** 정본 §3·§4: `bo-web → bo-api(REST only) → aml-svc admin API`. 본 문서의 Admin API는 bo-api가 호출하는 aml-svc 계약이며, bo-web↔bo-api 계약은 bo-api 측 PRD/스펙에서 파생한다.
> P0-03부터 bo-api의 catch-all `/api/v1/admin/{engine}/**` passthrough는 존재하지 않는다. 모든 AML 운영 기능은 endpoint별 typed bo-api controller/DTO/client와 BO RBAC를 거쳐야 하며, 미등록 admin route는 404다.

plane 버저닝은 일반 Public/Admin `/api/v1`, 중립 거래 Public `/aml/v1`, Internal
`/internal/v1`이다. 중립 수집은 기존 공개 계약을 보존하는 명시적 namespace 예외이며 breaking
change는 각각 `/api/v2` 또는 `/aml/v2`로 분기해 병행 운영한다.

> **정본 결정 요약(정합성 리포트 design:api 정정분).** 아래 5건은 본 API 명세를 파생(설계서·연동·태스크·PRD·PPT)의 진실로 확정한다.
> 1. **운영자 집계 API 소유 경계 = bo-api(§9).** 대시보드(플랫폼·서비스별)·서비스 관리(목록/상세/등록/설정)·운영자 감사 조회 화면이 호출하는 집계 엔드포인트는 **bo-api가 소유·집약·인증**한다. aml-svc(엔진)는 저수준 데이터 API만 제공하며, **본 엔진 API 명세(§2)에는 운영자 집계 엔드포인트(대시보드/서비스/감사)를 추가하지 않는다.** PRD/PPT의 해당 화면은 호출 대상을 bo-api(`/api/v1/bo/aml/**`)로 명시한다. (§2.7 `audit-events`는 엔진 측 append-only 저수준 감사 조회이며, 운영자 화면용 감사 집계는 bo-api가 위임 호출한다.)
> 2. **마스터 enum = 본 API enum(전수) 정본.** screening_status 마스터는 `NO_MATCH`/`POSSIBLE_MATCH`/`TRUE_MATCH`/`FALSE_POSITIVE`/`AUTO_DISCOUNTED`/`ESCALATED`다. 결재 `subjectType` 마스터는 §3.7 엔진 enum **21종**(`REPORT_RULE_PARAM` 포함, V41)이 정본이며 설계서·PRD·DB §5.16은 이에 동기화한다.
> 3. **HTTP 상태코드 = §4 정본.** 멱등 충돌 409·결재 미충족/자기승인 409·payload 변경 409·상태전이 위반 409·screening 검토요구 422·rate limit 429·fail-closed 503을 §4로 확정한다.
> 4. **Webhook 콜백 계약 = §8 정본.** screening/case/report 상태변경 outbound 콜백 3종·envelope·`X-Signature` HMAC·재시도/멱등을 §8로 확정한다. 설계서 §15.7 'Webhook API'는 본 §8을 정본으로 참조한다.
> 5. **배포 모델/온보딩 = bo-api 소유, aml-svc 엔진 API 미추가(§9·§3.16).** 서비스(테넌트=서비스) 등록은 격리 토글(구 `isolation_mode` 라디오)이 아니라 **배포 유형 선택(`DeploymentModel`) + 온보딩 신청(`OnboardingStatus` 상태머신)** 흐름이다(정본 §4.1, D-06 결정 확정). `DeploymentModel` 3종·`OnboardingStatus` 8종은 DB §5.28/§5.28a 정본과 1:1(FDS API v1.5 §10 동기화). bo-api 전용 엔드포인트 5종(§5 paths, §9 표) — `GET/POST /api/v1/bo/aml/tenants`, `GET/PUT .../tenants/{tenantId}`, `POST .../onboarding/provision`, `POST .../onboarding/register`, `GET .../onboarding`. `isolationMode` 필드·`isolation_mode` 컬럼·구 enum 전면 폐기. 오픈결정: SELF_HOSTED `registrationToken` 인증 방식(서명·mTLS 등) 상세는 P8 인프라 설계 확정.

---

## 1. 공통 규약 (횡단)

### 1.1 인증·테넌시·data-scope

| 요소 | 전달 방식 | 필수 | 설명 |
|---|---|---|---|
| Tenant | `Tenant-Id` 헤더 (Public/Internal) / bo-api 세션 클레임 (Admin) | Y | DB `tenant_id`(테넌트=서비스, 상위 기관 institution이 운영하는 서비스 1종·1 기관 : N 서비스). 전용 배포(`MANAGED_DEDICATED`/`SELF_HOSTED`)에서는 배포=서비스 단일 값(라우팅은 배포 엔드포인트 단위). `SHARED` 배포에서만 `Tenant-Id` 헤더 행 라우팅·RLS `app.current_tenant` 세션변수로 강제 |
| Workspace | wire v2 canonical `workspace=default` | — | AML은 물리 workspace/header를 사용하지 않으며 항상 `default`로 서명 |
| Source System | `Source-System` 헤더 | Public Ingest/Screen Y (§2.1a 예외) | DB `aml_source_systems.source_system`. source header의 유일한 정본 이름이며 `X-Source-System` 등 alias는 거부. 미등록 source는 거부. 단, 중립 거래 ingest는 아래 endpoint-specific 예외를 따른다 |
| Data-scope | machine 요청 `X-Data-Scope` / bo-api 토큰 클레임 `dataScope` / 쿼리 `dataScope` | N | DB `data_scope`(영업점·법인그룹 하위 격리, 정본 §4). machine header 값은 wire v2 `scopeContext.data-scope`에 결합. §2.1a에서는 P0-01 기준 무결성 결합만 하며 별도 credential allowlist를 추가하지 않음 |
| Credential | `X-Api-Key` | HMAC Y | `aml_api_credentials.credential_id`; DB에는 AES-GCM `secret_ciphertext`만 저장 |
| Timestamp | `X-Timestamp` | HMAC Y | RFC3339 UTC(`Z`), 서버 기준 ±5분 |
| Auth version / nonce | `X-Auth-Version: 2` / `X-Nonce` | v2 Y | nonce=16 random bytes canonical base64url-no-padding 22자, credential-wide 기본 TTL 15분(`>2×skew`) |
| 서명 | `X-Signature: hmac-sha256=...` | HMAC Y | UTF-8/LF/no trailing LF, raw path/query·Tenant-Id·고정 9-key scopeContext·raw-body digest·timestamp·nonce 공식은 [공통 machine-auth 정본](00-common-machine-auth.md)만 따른다. 구 v1 공식은 전환 호환 전용 |
| 운영자 actor | `X-User-Subject` | Admin/Internal write Y | trusted BFF/mesh가 인증 principal에서 파생. wire v2 `scopeContext.user-subject`에 결합되므로 서명 뒤 actor 교체는 401. 브라우저 임의 입력 금지 |
| Idempotency | `Idempotency-Key` 헤더 | 쓰기성 Public Y (§2.1a 예외) | DB `aml_canonical_events.idempotency_key` UNIQUE(tenant_id,idempotency_key). 중립 거래 ingest는 생략 시 body `eventId`를 사용 |
| Trace | `X-Trace-Id`(없으면 생성) | N | 공통 HTTP/BO/admin 안전 상한은 trim 후 128자·제어문자 금지이고 요청 MDC로 전파한다. **canonical AML ingest는 `docs/aml-data.md` 정본의 최대 64자·초과 422를 유지**하며 `aml_canonical_events` 등 canonical lineage는 `VARCHAR(64)`다. admin 감사 `aml_audit_events.trace_id`만 V46부터 `VARCHAR(128)` |
| Correlation | `X-Correlation-Id` | N | 호출/업무 상관 계보. 고정 9-key scopeContext와 현재 singleton 거부 목록 밖 |

credential `allowed_protocol_versions`와 service policy의 교집합만 허용한다. migration 이전 row는 `["v1","v2"]`, 신규 row는 `["v2"]`가 기본이며 명시적 v2 실패를 v1로 fallback하지 않는다. v1 timestamp는 기존 RFC3339 offset 표기를 호환하고 v2는 canonical UTC `Z`만 허용한다. nonce는 HMAC 검증 후 scope/controller 전에 별도 트랜잭션으로 소비하므로 downstream 오류에도 재사용할 수 없고, 업무 replay는 새 nonce로 인증한 뒤 §1.4 멱등 결과를 받는다. TTL은 반드시 `2×timestamp skew`보다 엄격히 길며, 만료 cleanup 기본값은 1분마다 최대 `20×5000` row다.

route policy는 위 교집합을 더 좁힐 수 있다. §2.1a `/aml/v1/**`는 migration 전 dual credential에도
v2-only이며, 다른 기존 AML route의 측정된 v1→v2 전환은 유지한다.

서버는 servlet normalized route로 filter/scope coverage를 판단하고 raw URI를 HMAC에 사용한다. dot/encoded-separator/matrix/double-slash 등 ambiguous raw path와 duplicate singleton header는 body read·credential lookup·nonce 소비 전에 generic 401이다. signed client는 redirect를 자동 추종하지 않고 target 변경 시 새 timestamp/nonce로 재서명한다. bo-api 공용 engine `RestClient`는 `DONT_FOLLOW`를 명시해 실제 origin 302를 그대로 반환하고 target 0회·`X-Api-Key` 미전달을 검증한다. `X-Trace-Id`/`X-Correlation-Id`는 관측성에는 계속 전파하지만 9-key context에는 추가하지 않는다.

BO session의 `platformOperator`는 횡단 tenant target을 고르는 data-scope 속성일 뿐 메뉴/IAM·PII reveal·STR/tipping-off 인가 우회가 아니다. 각 typed BFF의 exact scope/role을 계속 검사하며, 전역 wildcard는 `BO_SUPER_ADMIN`의 effective scope `*`만 인정한다.

local/demo bootstrap/provisioner는 명시적 `local|demo` positive profile + opt-in에서만 허용되는 infrastructure 편의이며 Flyway business seed가 아니다. AML REST simulator, bo-api, FDS escalation은 서로 다른 credential ID/secret을 사용한다. bo-api credential은 endpoint scope union과 별도 `COMPLIANCE`, `aml:pii:reveal` authority token을 포함하고 FDS credential은 `aml:internal:fds-escalation:write`만 가진다. P0-04 local lifecycle은 bootstrap bypass=false가 정본이다. 엔진 STR 열람 감사·모든 admin write의 maker/checker/actor identity는 v2로 서명된 `X-User-Subject`에서 파생한다. 공통 filter는 HMAC 성공 뒤 signed subject의 최대 128자·제어문자/CRLF 금지까지 검증한 값만 내부 verified attribute로 만들고 controller는 `TrustedActorResolver`로 이를 읽는다. signed subject 자체가 이 경계를 어기면 generic 401이다. body/query `makerId`·`checkerId`·`actor`는 생략 가능하며, 존재하면 trim·대소문자 무시 기준으로 같은 signed subject인지 확인하는 호환 assertion일 뿐 identity source가 아니다. body assertion 불일치·초과 길이·제어문자는 command 생성 전에 400으로 거부한다.

scope 또는 role request attribute가 없으면 공통 filter가 local/demo positive profile과 opt-in을 확인한
뒤 내부 request attribute에 정확히 `Boolean.TRUE`로 설정한 bootstrap marker가 있는 경우만 허용한다.
그 밖에는 `ScopeGuard`가 403 `AML-AUTHZ-002`, `RoleGuard`가 403 `AML.FORBIDDEN_SCOPE`로 닫으며,
marker는 wire header나 호출자 입력이 아니다.

> **적용 경계(2026-07-13)**: P0-01로 `/aml/v1/**`가 실제 filter coverage에 포함되어
> §2.1a `/aml/v1/transaction-events`도 공통 v2와 `aml:event:write`를 강제한다. P0-04로
> `/internal/v1/aml/**` v2-only, receiver endpoint scope, FDS→AML signer, BO→FDS signer를 완료했다.
> 남은 미완료는 multipart 최종 raw-byte client 전환(P0-14), credential 생성·scope 변경·자동
> 유예회전·폐기·last-used·rate/network/workload 통제(P1-02)다
> ([공통 정본 §7](00-common-machine-auth.md#7-후속-태스크-경계)).

권한 scope(**마스터=본 §1.1 enum 전수 정본**): public/BO OAuth2·RBAC 13종 `aml:event:write`, `aml:screen:evaluate`, `aml:ra:evaluate`, `aml:tm:evaluate`, `aml:case:read`, `aml:case:update`, `aml:evidence:export`, `aml:admin:watchlist`, `aml:admin:source-system`, `aml:admin:policy`, `aml:admin:approval`, `aml:admin:audit`, `aml:pii:reveal`(원문/raw PII 접근, 사유+감사 `RAW_DATA_ACCESS` 필수, §1.6) + internal machine 전용 `aml:internal:fds-escalation:write` + **`aml:report:callback`(P0-11 — FIU 제출 회신 콜백 전용 최소권한, §2.7 `/reports/{id}/callback`)** 2종 = **총 15종**. PRD §1.4의 사람 권한 13종은 그대로이며, 설계서 §15.7은 13+2(machine) 구분을 본 §1.1에 동기화한다.

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

본 문서에서 **🔒4-eyes** 표기된 엔드포인트는 작성자≠승인자 결재(`aml_approvals`, CHECK `maker_id<>checker_id`)를 거쳐야 실행된다(설계서 §13.4~§13.5). 호출 흐름: `① 상신(maker) → 202 + approvalId(status=SUBMITTED) → ② 승인(checker) → APPROVED → ③ 실행 → EXECUTED`. payload는 `payload_hash`로 고정되어 승인 후 변경 시 무효화. maker와 checker는 모두 브라우저 body가 아니라 인증 principal에서 서버 파생한다. bo-api는 `BackofficePrincipal.email`, aml-svc는 공통 resolver가 반환한 signed `X-User-Subject`를 단일 정본으로 사용한다. 호환용 body `makerId`/`checkerId`/`actor`가 있으면 trim·대소문자 무시 기준으로 같은 subject여야 하며, 다른 문자열 주입은 상신·승인·반려·감사 command 전에 400으로 거부한다. 동일 signed subject의 self-approval은 별도 4-eyes 불변식으로 409다.

> **`DRAFT` 상태는 내부 전이 상태로 API 미노출.** `ApprovalDto.status`(§3.7) 및 API 호출 흐름에서 `DRAFT`는 내부 엔진 초기화 단계이며 외부 호출자(bo-api/bo-web)에게 노출되지 않는다. API 표면 첫 관찰 가능 상태는 `SUBMITTED`(상신 완료, 202 응답)이다(설계서 §13.5 상태머신 대비). PRD/화면은 `DRAFT` 배지 표시 불필요.

### 1.6 PII 마스킹

DTO는 raw PII를 노출하지 않는다(DB §2.2). 식별은 `customerRef`/`entityRef`(토큰), 매칭 근거는 `*Hash`/`scoreBreakdown`만. 원문 접근이 불가피한 화면은 `aml:pii:reveal` scope(§1.1 enum 등재·OpenAPI scopes 정식, 13번째) + 사유 + `aml_audit_events`(`RAW_DATA_ACCESS`) 기록.

> **reveal 가능 `field` 도메인(7종, 2026-06-29 식별정보 확장)**: `NAME`/`DOC`/`ACCOUNT`/`WALLET` + `NATIONALITY`(국적)/`GENDER`(성별)/`DOB`(생년월일). 도메인 `PiiField`(7종)·`aml_pii_vault.field` CHECK(DB §5.35·§3.21, Flyway V23)와 1:1, 미허용 값은 400. WLF 매치 상세(§3.2 `subjectIdentity`)는 회원 본인 식별정보와 워치리스트 엔트리 원문(매칭 후보)을 **주체 무관 균일 4필드(`NAME`/`NATIONALITY`/`GENDER`/`DOB`)** 로 본 reveal 게이트에 노출하되, scope·사유·`RAW_DATA_ACCESS` 감사 없이는 cleartext 미산출(주체가 보유하지 않거나 vault 미적재 필드는 reveal stub 이 빈 값 `""` 반환, fail-closed 불변).

---

## 2. 엔드포인트 표

### 2.1 Ingest API (Public) — 설계서 §8·§15.1·§15.3

| 메서드 | 경로 | scope | 멱등 | 설명 | DB |
|---|---|---|---|---|---|
| POST | `/api/v1/aml/events` | `aml:event:write` | Y | canonical AML event 수신. `customer.cdd.completed`는 동기 1차 RA의 불변 업무결정(`APPROVE`/`REJECT`/`EDD_REQUIRED`)과 score/model snapshot을 함께 반환하며 replay는 최초 결정을 그대로 반환 | `aml_canonical_events`,`aml_cdd_onboarding_decisions` |
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

> **인입 파이프라인 step 7d — 1차 온보딩 RA 엔진 CDD 파생(코드=truth, feature/aml-onboarding-ra-cdd-derivation, 요구 런 11).** `POST /api/v1/aml/events` 로 **`customer.cdd.completed`** 가 인입되면 단일 트랜잭션의 identity projection(step 7, `aml_customers` upsert + `kyc_evidence` + PII vault) **직후** 엔진이 1차 RA 를 CDD 데이터로부터 직접 파생한다(`DeriveOnboardingRaUseCase`·`OnboardingRaDerivationService`) — 별도 `POST /risk-assessments/evaluate` 호출·클라 계산 없이 `aml_risk_scores` 1차 RA 행이 생성된다:
> - **(a) SCREENING** = 회원 WLF 스크리닝(SANCTION/PEP, 주체 키 `memberRef`, idem `cdd-ra:{eventId}`, `TargetType.CUSTOMER`, transient name/dob 는 매칭 토큰만·미저장 §19.2). 매치(POSSIBLE/TRUE, 비 AUTO_DISCOUNTED) 시 SCREENING=100 + **위험등급 HIGH 강제 상향(floor)** + 사유(list_type SANCTION/PEP) + 근거 참조 토큰(screeningId/entryId/listType), 무매치=0.
> - **(b) GEOGRAPHY** = 국적/거주국 × 국가위험 정본(`LookupCountryRiskUseCase.gradeFor`, §2.7 국가위험) → PROHIBITED/HIGH=100·MEDIUM=60·LOW/미등재=15(nationality×residenceCountry **max 결합**).
> - **(c) CUSTOMER** = `kyc_evidence`(sourceOfFunds·kycLevel·occupation) → `clamp((sofRisk+kycLevelRisk)/2 + occupationRisk)` 엔진 파생. 세 값은 ACTIVE ONBOARDING 맵과 exact code로 조회하고 미등록 값은 각 `default`를 적용한다. `kycLevelRisk`는 고객확인 수행 수준의 통제 잔여위험, `occupationRisk`는 평균 항목이 아닌 가산 조정값이다.
> 파생 규칙은 ACTIVE ONBOARDING 모델(`KR_DEFAULT_RA`) `parameters` JSONB 정본(V19)이 소비하며 엔진 상수 하드코딩 없음. **fail-safe**: 스크리닝 미가용(워치리스트 stale/미수입) 시 freshness **boolean 선검사**로 1차 RA **평가 보류**(스코어 미생성)하되 CDD 인입 자체는 `ACCEPTED` — 예외 전파로 인입 TX 를 rollback-only 오염시키지 않는다(§15.5·§20.2 fail-closed). `customer.cdd.completed` 외 이벤트는 no-op.
>
> **CDD 온보딩 업무결정(V42, 코드=truth).** `customer.cdd.completed`의 최초 ACCEPTED 처리에서 생성된 RA snapshot을 `aml_cdd_onboarding_decisions`에 이벤트/멱등키별 불변 projection으로 저장한다. KYC `REJECTED` 또는 RA `PROHIBITED`는 `REJECT`, EDD 필요·고위험 WLF/보류는 `EDD_REQUIRED`, 나머지는 `APPROVE`다. 응답은 `{decision,scoreId,riskScore,riskGrade,requiredAction,modelVersion,reason}`을 포함한다. replay는 idempotency key 소유 **저장 canonical event의 eventId/source/schema/type/occurredAt/payload/hash/dataScope**와 요청을 비교한다. exact replay만 후속 모델·source enabled/schema 변경과 무관하게 최초 snapshot을 200으로 반환하고, 같은 key의 다른 body는 `409 DUPLICATE`다. legacy 복구에서 projection이 없으면 재평가로 새 결정을 발명하지 않고 `EDD_REQUIRED`로 fail-safe 한다.

> **인입 파이프라인 step 7f — FDS 고객 프로필 동기화 outbox.** 신규 CDD가 ACCEPTED되면 동일 트랜잭션에서 `aggregateType=FDS_CUSTOMER_PROFILE`, `eventType=aml.customer.profile.updated`, `aggregateRef=customerRef` outbox를 생성한다. payload는 `sourceEventId/occurredAt/nationality/country/registeredAt/kycCompletedAt/kycLevel/dataScope`만 포함하고 raw name·DOB·문서 식별자는 제외한다. relay가 FDS 내부 API로 전달하며 실패는 기존 outbox retry/backoff로 재시도하므로 FDS 장애가 AML CDD ingest를 rollback하지 않는다. REPLAYED/DUPLICATE는 step 7f에 도달하지 않아 중복 enqueue하지 않는다.

### 2.1a 중립(canonical) 수집 API — `POST /aml/v1/transaction-events` (코드=truth, feature/aml-neutral-canonical-ingest)

소스 중립(canonical) 수집 API. 해외송금·국내송금·카드결제·월렛충전·월렛결제 5개 product 를 **단일 Envelope**(`docs/aml-data.md` §3~§7, ISO 20022/FATF R.16/ISO 4217·3166·8601)로 수신하고, 하나의 POST 로 WLF 스크리닝 + CTR/STR 평가(TM 파이프라인)를 팬아웃한다. 기존 `POST /api/v1/aml/events`(§3.1, 내부 canonical 저장 경로)와 별개의 공개 수집 표면이며, 원천 시스템은 자기 컬럼을 이 표준 필드로 매핑만 하면 동일 API 로 인입한다.

P0-01부터 normalized route `/aml/v1/**`는 공통 machine-auth filter의 실제 coverage다. 이 endpoint와
`POST /api/v1/aml/events`는 모두 `aml:event:write`를 요구하며, scope/role attribute 부재는 공통
filter가 설정한 local-bootstrap `Boolean.TRUE` marker 외에는 403으로 닫힌다.

| 메서드 | 경로 | scope | 멱등 | 헤더 | 설명 | DB |
|---|---|---|---|---|---|---|
| POST | `/aml/v1/transaction-events` | `aml:event:write` | Y | v2 필수=`Tenant-Id`·`X-Api-Key`·`X-Auth-Version: 2`·`X-Timestamp`·`X-Nonce`·`X-Signature`·`Content-Type: application/json`; 업무=`Idempotency-Key`(옵션, 미지정 시 body `eventId` 사용·지정 시 `eventId`와 일치 필수); 선택=`Source-System`·`X-Data-Scope`·`X-Trace-Id` | 인증·scope 통과 뒤 중립 Envelope 수신 → 검증(422) → 비PII 안정 토큰 파생 → canonical event 멱등 저장. 신규 ACCEPTED만 raw PII vault → WLF + CTR/STR 평가하고, REPLAYED/DUPLICATE는 요청-body side-effect 없이 종결. 응답=수신확인 + ACCEPTED 평가요약 | `aml_canonical_events`(+ACCEPTED 한정 `aml_alerts`·CTR/STR 파생) |

**중립 endpoint-specific header 예외.** 일반 Public ingest의 `Source-System`/`Idempotency-Key` 필수
규칙과 달리, 본 endpoint의 canonical `source_system`/`schema_version`은 server property
`aml.neutral.source-system`/`aml.neutral.schema-version`으로 결정하고 Envelope `institutionId`는 별도
보고기관 provenance로 flat payload에 보존한다. `Source-System`은 선택이며 제공되면 v2
`scopeContext`에 exact 결합되지만 server-owned 업무 source를 덮어쓰지 않는다. `Idempotency-Key`는
생략 시 body `eventId`를 사용한다.
`X-Data-Scope`도 선택이며 서명 뒤 값을 바꾸면 401 `AML-AUTH-002`다. P0-01은 valid signature로
새로 서명한 data-scope에 대한 credential allowlist/인가 정책이나 DB 컬럼을 추가하지 않는다.

**인증 실패 무부작용.** 401/403 요청은 controller/usecase에 도달하지 않아
`aml_canonical_events`·`aml_pii_vault`·`aml_screening_results`·`aml_alerts`·
`aml_regulatory_reports`·`aml_risk_scores` 업무 row를 만들지 않는다. 다만 정상 서명 뒤
`aml:event:write` 부족으로 거부된 403은 공통 검증 순서에 따라 nonce가 이미 소비되어
`aml_auth_nonces` row가 유지된다.

**상태코드 매핑**(엔진 `NeutralTransactionEventController#httpStatus` = truth): `ACCEPTED`→`202`, `REPLAYED`(멱등 재전송·동일 canonical payload)→`200`, `DUPLICATE`(동일 키·다른 내용)→`409`, `REJECTED`(검증 실패)→`422`. 검증 실패는 **단일 422** 에 누적 위반 목록을 실어 반환하며 500 을 던지지 않는다(fail-closed). `REPLAYED`/`DUPLICATE`는 raw PII vault·WLF·TM/CTR/STR 전에 즉시 종결되어 재전송 body의 projection/엔진 side-effect가 0건이고 `evaluation=null`이다. canonical payload용 비PII 안정 토큰만 gate 전에 순수 파생한다. raw PII는 canonical hash에 없으므로 신규 `ACCEPTED` body에서만 vault/screening에 사용한다.

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
| `institutionId` | string | R | 보고기관 식별자 provenance. flat payload에 보존하며 server-owned canonical `sourceSystem`과 별개(가정 G8) |
| `status` | string | R | 원천 거래 최종 상태 |
| `originator` | object(Party) | R | 주체 고객. `nationalIdentityKey` 필수(CTR 최소요건 §9). §3.17 Party |
| `amounts` | object | R | 금액 블록. `baseAmount`/`baseCurrency` 필수, `baseCurrency`=테넌트 규제통화(가정 G3). §3.17 Amounts |
| `counterparty` | object(Party) | 조건부 | 상대방. `CROSS_BORDER_REMITTANCE`이면 필수(FATF R.16 당사자 정보 요건 — 인입 계약 검증 규칙, 아래 422 규칙 ⑦) |
| `remittance`/`domesticTransfer`/`cardPayment`/`walletTopup`/`walletPayment` | object | 조건부 | `product`에 대응하는 블록만 채움(§3.17 product 블록) |

**422 검증 규칙**(`NeutralEventValidator` = truth): ① 필수필드 누락(`eventId`/`eventType`/`product`/`direction`/`transactionReference`/`institutionId`/`status`/`occurredAt`/`originator.nationalIdentityKey`/`amounts.baseAmount`/`amounts.baseCurrency`) ② `occurredAt` ISO-8601 offset 위반 ③ 통화 ISO 4217(3자)·국가 ISO 3166-1 alpha-2(2자) 위반 ④ `baseAmount` < 0 ⑤ `amounts.baseCurrency` ≠ **테넌트 기준통화(P0-16, `TenantPolicyBinding.baseCurrency` — tenant 행 바인딩 정본, 구 가정 G3 service-global 상수 대체·tenant_demo=PHP·임계 ₱500,000)**(잘못된 환산으로 CTR 오보고 방지 fail-closed) ⑥ reversal eventType 인데 `relatedReference` 누락 ⑦ `CROSS_BORDER_REMITTANCE`인데 `counterparty` 누락. 위반은 배열로 누적되어 한 번의 422 로 반환된다. 미지 enum 값은 역직렬화 단계에서 `400 AML.BAD_REQUEST`. **인입 step 0(검증 이전) 에서 tenant 관할·통화·Policy Pack revision 바인딩을 먼저 해소**(`TenantPolicyResolver`)하며, 미바인딩/충돌은 검증 위반 배열이 아니라 **`422 AML.TENANT_POLICY_UNBOUND`** 로 fail-closed 한다(§4).

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

**PII 토큰화 경계**(가정 G7/G9, §1.6 원칙 그대로): raw 이름·신분증번호·계좌번호·전화는 컨트롤러→usecase 수신 경계에서만 존재하고, 즉시 토큰화(`PiiTokenPort`)+가역 vault(`aml_pii_vault`) 적재 후 소멸한다. 엔진 payload·canonical event·로그·응답에는 `targetRef`/`counterpartyRef`·`*Masked`만 실린다. **회원 주체 참조 키(`targetRef`, subject)는 회원 업무참조(`originator.partyReference`, 예 `M-1001`)를 토큰화하지 않고 그대로 쓴다**(비PII 업무참조 — integration §10.2a·§19.2): FDS `subject_ref`·CDD `customer_ref`·`aml_risk_scores.target_ref`와 동일 회원 키라 온보딩↔거래 RA 가 이어진다. PII 속성(이름·`nationalIdentityKey`·신분증·전화)만 토큰/vault 로 흐른다. counterparty(외부 수취인) 안정키=이름+거주국+전화(기존 WLF 정본 재사용). 신분증번호(`idNumberToken`)는 vault 만, payload·응답 미포함. 업무참조 부재 레거시 경로만 `originator.nationalIdentityKey` 기반 토큰으로 폴백(잔존 허용).

**응답**(`NeutralIngestResponse` = truth, 가정 G6 — 동기 HOLD 오케스트레이션 미구현): `{ eventId, status(ACCEPTED/REPLAYED/DUPLICATE/REJECTED), accepted(boolean), violations(string[], REJECTED 시만), evaluation }`. `evaluation`(평가된 경우만)=`{ decision(PASS/REPORT — advisory 파생값), alertCount, firedRuleCodes[], screened(boolean) }`. WLF 실패는 인입 실패로 전파하지 않고 `screened=false`로만 표기(가정 G10, best-effort).

**엔진 저장 flat canonical payload**(`NeutralTransactionEventService#flatPayload` = truth — 위 **입력 Envelope**(nested)와 구분되는, 엔진이 canonical event(`aml_canonical_events.payload` JSONB)에 저장하고 TM/CTR/STR 룰 윈도우가 소비하는 **평탄(flat) 키** 정본). 입력 nested 필드를 서버가 평탄화·토큰화·파생한 결과이며, camelCase 단일 depth 다:

| flat 키 | 타입 | 파생/설명 |
|---|---|---|
| `targetRef` | string | **회원 주체 참조 키 = 회원 업무참조**(`originator.partyReference`, 예 `M-1001` — 비PII, 토큰화 안 함, integration §10.2a). subject_ref·`customer_ref`·`aml_risk_scores.target_ref`·`aml_alerts.target_ref`와 동일 값. 업무참조 부재 레거시 경로만 `nationalIdentityKey` 기반 토큰 폴백 |
| `memberRef` | string | 비PII 회원 업무참조(`originator.partyReference`, 예 `M-1001`) — 화면 회원번호 열, FDS `subject_ref` 동형. 주체 키 통일 이후 `targetRef`와 동일 값이나 `payload->>'memberRef'` 직접 소비 하위호환 열로 유지. 부재 시 키 미기록 |
| `transactionRef` | string | `transactionReference`(원천 거래 고유번호) |
| `amountBase` | decimal | 정규화 base 금액. reversal(취소/환불/역거래)은 **음수**(가정 G4·일합산 순증 차감) |
| `baseEquivalent` | decimal | **통화중립 기준통화 환산액**(P0-16) = `amountBase`(항상 기록). `baseCurrency` 와 쌍으로 룰 윈도우가 native 통화로 금액을 해석한다 |
| `baseCurrency` | currency | **테넌트 기준통화**(P0-16, `TenantPolicyBinding.baseCurrency` — tenant 바인딩 정본, 구 service-global @Value 대체) |
| `phpEquivalent` | decimal | PHP 환산액 = `amountBase`. **`baseCurrency='PHP'` 일 때만 생성**(P0-16 — PH-native). 비-PHP 테넌트는 미기록(완전 FX 환산은 phase-2 A1) → KRW 테넌트 CTR/금액 TM 룰 미발동(가짜 PH CTR 누출 없음) |
| `currency` | string | `amounts.baseCurrency`(ISO 4217, 테넌트 규제통화) |
| `channelType` | string | family 매핑(위 family 표)의 engine channelType 토큰(예 `CASH_IN`/`DOMESTIC_REMIT`/`CROSS_BORDER_REMIT`) |
| `direction` | string\|null | `INBOUND`/`OUTBOUND`/`INTERNAL` |
| `counterpartyRef` | string | 단일 canonical 상대방 토큰(flat payload·WLF 스크리닝·vault 공유; 아래 파생 규칙). 부재 시 키 미기록 |
| `corridor` | string\|null | **서버 파생 문자열**(송금 2종만; 아래 파생 규칙). 미해당(WALLET/CARD)은 키 미기록 |
| `product` | string | `CROSS_BORDER_REMITTANCE`/`DOMESTIC_TRANSFER`/`CARD_PAYMENT`/`WALLET_TOPUP`/`WALLET_PAYMENT` |
| `eventLifecycle` | string | `eventType`(`CREATED`/`COMPLETED`/`CANCELLED`/`REFUNDED`/`REVERSED`) |
| `relatedReference` | string | 원거래 참조(reversal 시). 부재 시 키 미기록 |
| `institutionId` | string | 보고기관 식별자 provenance. 입력값을 보존하며 canonical `sourceSystem`은 server property에서 결정(가정 G8) |
| product 신호 | — | `product` 블록별 비PII STR/FDS 신호(`addProductSignals`=truth): REMIT=`destinationCountry`/`payoutPartner`/`relationshipToBeneficiary`/`payoutMethod`, DOMESTIC=`accountHolderNameMatch`/`fundingSourceType`, CARD=`mcc`/`merchantRef`/`merchantCountry`/`balanceBefore`/`balanceAfter`, WALLET_TOPUP=`fundingInstrumentType`/`balanceBefore`/`balanceAfter`/`walletId`, WALLET_PAYMENT=`mcc`/`merchantRef`/`balanceBefore`/`balanceAfter`/`walletId`(값 있을 때만 기록) |

- **`corridor` 서버 파생 규칙**(`corridor()` = truth): 발신국 = **테넌트 관할(`TenantPolicyBinding.jurisdiction`, P0-16 — tenant 행 바인딩 정본, 구 service-global `aml.neutral.regulatory-country`/@Value `PH` 상수 제거)**. `DOMESTIC_TRANSFER` → `{J}-{J}`(예 tenant_demo `PH-PH`·KR 테넌트 `KR-KR`), `CROSS_BORDER_REMITTANCE` → `{J}-{destinationCountry}`(destinationCountry 부재 시 `counterparty.residenceCountry` 폴백; 둘 다 없으면 키 미기록), `WALLET_*`/`CARD_PAYMENT` → 키 미기록. tenant 바인딩 미해소(unbound) 시 인입 자체가 422 `AML.TENANT_POLICY_UNBOUND`(fail-closed, corridor 도출 이전). **flat `corridor` 는 문자열**이며, 입력 §3.17 remittance 블록/§4.2·`corridor` object(nested `{ sendCountry, receiveCountry, sendCurrency, receiveCurrency }`)는 발신측이 싣는 **상세 입력 구성요소**다 — 엔진은 이를 저장 시 위 문자열로 평탄 파생하므로, 룰 윈도우가 소비하는 corridor 정본은 **본 flat 문자열**이고 §3.4d/§3.4a `relatedTransactions[].corridor` 도 이 문자열을 상속한다.
- **`counterpartyRef` 단일화 규칙**(`resolveCounterpartyRef` = truth): 해외송금은 counterparty 블록의 안정 WLF 키(이름+거주국+전화) 토큰, 국내송금(counterparty 블록 없음)은 `domesticTransfer.creditAccount.accountHolderName`(예금주) 기반 receiver 안정 토큰 — 둘 다 flat payload·WLF screen key·vault 가 공유하는 **동일 값**(교차거래 discounting·reveal 정합). 상대방/예금주 신원이 없으면 키 미기록.

### 2.2 Screening API (Public) — 설계서 §10·§15.2·§15.7

| 메서드 | 경로 | scope | 멱등 | 설명 | DB |
|---|---|---|---|---|---|
| POST | `/api/v1/aml/screen` | `aml:screen:evaluate` | Y | 실시간 WLF/제재/PEP screening. **hanpass-ph 해외송금은 거래당 sender(송금 회원)·receiver(수취인) 2회 호출**(§3.2 `transactionRef`로 연결). **COUNTERPARTY 대상은 요청 신원(이름 토큰·country·dob)을 스크리닝 `targetRef` 키로 reveal vault 에 암호화 투영**(2026-07-15 — WLF 상세 수취인 원문 reveal 결선, DB §3.21; 응답·DTO 불변) | `aml_screening_results`, `aml_pii_vault`(COUNTERPARTY 투영) |
| GET | `/api/v1/aml/screenings/{screeningId}` | `aml:screen:evaluate` **또는** `aml:case:read` (requireAny) | — | screening 결과 조회 — 소스시스템 read-back(`aml:screen:evaluate`) 외에 BO 검토 화면 위임(bo-api, `aml:case:read`)도 허용. BO 위임 credential 은 evaluate scope 를 의도적으로 미보유(BOA-S1-01·PRD §1.4)하므로 읽기 전용 상세는 `aml:case:read` 로 열린다(P0-04 credential 분리 후 WLF 상세 403 회귀 교정) | `aml_screening_results` |

> **WLF 스크리닝 대상 = 해외송금 + 국내송금 양당사자(sender + receiver)(hanpass-ph 데모 정합)**: 송금계열 2 product — 해외송금(`CROSS_BORDER_REMITTANCE`, `remit-svc` cross-border)·국내송금(`DOMESTIC_TRANSFER`) — 거래는 송금인(sender = 회원 본인, `targetType=CUSTOMER`, `targetRef`=member UUID keyed token)과 수취인(receiver = 상대방, `targetType=COUNTERPARTY`, 해외송금 수취인 키=이름+국가+전화 토큰)을 **각각 1건씩** screen 한다(수취국 PH/VN/ID 제재 = 진양성). 두 결과는 동일 `transactionRef`(거래번호 keyed token)로 묶여 케이스/증빙에서 거래 단위로 연결된다. receiver 스크리닝은 워치리스트 receiver 엔트리와 매칭하며 `subjectIdentity`(§3.2) 4필드(NAME/NATIONALITY/GENDER/DOB)는 주체 무관 균일(COUNTERPARTY 미보유 필드는 reveal stub 이 빈 값) — 국내송금 receiver 에도 동일 적용된다. 국내송금 receiver 식별은 `domesticTransfer.creditAccount.accountHolderName`(이름) + 상대방 국가(A6, 기본 `PH`)로 해결하고, sender 스크리닝과 동일 `transactionReference` 로 키잉되어 STR party-aware receiver lineage(계약 1·6)가 소비한다. 회원가입·월렛충전·월렛결제 등 잔여(비-송금계열) 거래는 sender(`CUSTOMER`)만 screen. FP 화이트리스트(§2.7·§3.2)는 `(targetRef::matchedEntryId)` fingerprint를 키로 하므로 **특정 거래가 아니라 동일 대상의 재screening 전반에 거래간(across-transaction) 유효**하다(동일 FP 매칭은 `AUTO_DISCOUNTED`로 자동 감점). 엔진 도메인 비변경 — 데모/시뮬레이터/시드 한정. TM STR_PEP·STR_SANCTION 은 receiver COUNTERPARTY 스크리닝 계보를 수취인 명단 평가에 재사용(§3.4a·기능정의서 §7.1 BR-013).

> **fail-closed readiness 게이트 → `503 AML.SCREENING_UNAVAILABLE`(P0-06, feature/p0-06-wlf-source-readiness-rescreen)**: `POST /api/v1/aml/screen`(및 `POST /internal/v1/aml/screen`)는 실제 스크리닝 전 **필수 source readiness 게이트**를 통과해야 한다. 게이트는 tenant 의 **필수 source 정책**(DB §3.6a `aml_mandatory_watchlist_sources`)을 해소해 각 활성 필수 source 가 **screening-ready**(effectiveReadiness ∈ {`READY`, 유효 `OVERRIDDEN`}, DB §3.6 후주)이거나 capability=`NOT_APPLICABLE`+유효(승인·미만료) waiver 여야 통과한다. **필수 정책이 없는(미설정) tenant** 는 fallback=**screening-ready source ≥1건이면 통과, 0건이면 fail-closed**(구 freshness 게이트의 vacuous-truth[빈 목록 allMatch=true] fail-open 제거 — 검색할 명단이 없는데 `NO_MATCH` 로 미탐되던 구조적 결함 차단). 미충족 시 `NO_MATCH` 가 아니라 **`503 AML.SCREENING_UNAVAILABLE`** 로 fail-closed 하며, 응답 `details`(비-PII·source type/code 만)에 사유코드(`ScreeningReadinessReason`)를 담는다 — `NO_MANDATORY_POLICY`(정책 미설정, strict 기본 fail-closed)·`NO_READY_SOURCE`(fallback: ready source 0건)·`MISSING_SOURCE`(필수 source 미등록)·`NOT_READY`(MISSING/IMPORTING)·`STALE`(48h 초과)·`FAILED`(직전 import 실패)·`NOT_APPLICABLE_UNAPPROVED`(waiver 없음). 코드 truth=`WatchlistReadinessGateAdapter`·`WlfScreeningService`(게이트 (0a))·`GlobalExceptionHandler#handleScreeningUnavailable`. rescreen 파이프라인(명단 apply 후 durable 재검색)은 integration §.

### 2.3 Risk Assessment API (Public) — 설계서 §11

| 메서드 | 경로 | scope | 멱등 | 설명 | DB |
|---|---|---|---|---|---|
| POST | `/api/v1/aml/risk-assessments/evaluate` | `aml:ra:evaluate` | Y | 고객(회원)/법인 위험평가 실행(회원가입 RA·재평가) | `aml_risk_scores` |
| GET | `/api/v1/aml/risk-assessments/{scoreId}` | `aml:ra:evaluate` | — | RA 결과 조회 | `aml_risk_scores` |
| GET | `/api/v1/aml/customers/{customerRef}/risk` | `aml:case:read` | — | 대상 최신 등급 조회 | `aml_risk_scores` |
| POST | `/api/v1/admin/aml/risk-scores/{scoreId}:complete-review` | `aml:case:update` | — | SANCTION/PEP 1차 RA 체크리스트 완료. actor=`X-User-Subject`, 세 체크 항목 필수, replay 멱등 | `aml_ra_reviews`, `aml_audit_events(RA_REVIEW)` |

### 2.4 Transaction Monitoring API (Public) — 설계서 §12

| 메서드 | 경로 | scope | 멱등 | 설명 | DB |
|---|---|---|---|---|---|
| POST | `/api/v1/aml/transactions/evaluate` | `aml:tm:evaluate` | Y | 거래 TM 평가·alert 생성 | `aml_alerts`(+`aml_canonical_events`) |
| GET | `/api/v1/aml/alerts?status=&rule=&channel=&corridor=` | `aml:case:read` | — | alert triage 큐 목록(응답 DTO §3.4a `AlertDto[]`). **`status` 미지정 ⇒ 전 상태 반환**('전체' 시맨틱, run3 D1 — 기존 `defaultValue="DETECTED"` 드리프트 해소). `rule`=발동 룰 코드, `channel`/`corridor`=알럿 evidence `relatedTransactions[]` 대표값 클라이언트측 필터(run3 D6·가정 G2 1단계, 엔진 스키마 조인 필터는 후속). 전부 optional | `aml_alerts` |
| GET | `/api/v1/aml/alerts/{alertId}` | `aml:case:read` | — | alert 조회(응답 DTO §3.4a `AlertDto`) | `aml_alerts` |
| GET | `/api/v1/aml/alerts/{alertId}/related-transactions?page=&size=` | `aml:case:read` | — | **알림 발동 근거 거래 서버 페이징**(요구2·A8) — 발동 룰이 결정하는 윈도우(주체 velocity 윈도우 / 영업일 현금 합산 / 단건 그룹)의 근거 거래 **전수**를 페이징(20행 evidence 표시 캡과 별개). 응답 DTO §3.4d `RelatedTransactionsResponse` | `aml_alerts`(+`aml_canonical_events`) |
| POST | `/api/v1/aml/alerts/{alertId}:triage` | `aml:case:update` | — | alert 1차 분류(`DETECTED`→`TRIAGED`). 본문 없음. 응답 §3.4a `AlertDto`(전이 후 상태). 불법 전이 시 **409 `AML.STATE_CONFLICT`** | `aml_alerts` |
| POST | `/api/v1/aml/alerts/{alertId}:dismiss` | `aml:case:update` | — | alert 오탐 종결(`DETECTED`/`TRIAGED`→`DISMISSED`). **optional body `{reason, actor}`**(둘 다 nullable — `reason`=처분 사유 코드 문자열(예 `FALSE_POSITIVE` 계열)·`actor`=처분 행위자). **엔진은 하위호환 optional 로 수용**(본문 없거나 `reason` 부재도 허용)하며, `reason`/`actor` 지정 시 `aml_alerts.disposition_reason`/`disposition_actor`(V30)에 영속해 룰 효과성 오탐율(§12-B.3)·감사 근거를 남긴다. **사유 필수 강제는 bo-api/bo-web 계층 책임**(가정 G1). 응답 §3.4a `AlertDto`(`dispositionReason` 포함). 불법 전이 시 409 `AML.STATE_CONFLICT` | `aml_alerts` |
| POST | `/api/v1/aml/alerts/{alertId}:open-case` | `aml:case:update` | — | 케이스 개설(`TRIAGED`→`CASE_OPENED`). body `{caseType?, actor?}`. 응답 `201 {caseId, caseStatus}`. 불법 전이 시 409 `AML.STATE_CONFLICT` | `aml_alerts`,`aml_cases` |
| POST | `/api/v1/aml/alerts/{alertId}:escalate` | `aml:case:update` | — | 상위 승인(`TRIAGED`→`ESCALATED`, 케이스 개설). body `{caseType?, actor?}`. 응답 `201 {caseId, caseStatus}`. 불법 전이 시 409 `AML.STATE_CONFLICT` | `aml_alerts`,`aml_cases` |
| POST | `/api/v1/aml/alerts/{alertId}:recommend-str` | `aml:case:update` | — | STR 권고(`TRIAGED`→`STR_RECOMMENDED`, STR 케이스 개설 + 아웃박스 적재). body `{caseType?, actor?}`. 응답 `201 {caseId, caseStatus}`. 불법 전이 시 409 `AML.STATE_CONFLICT` | `aml_alerts`,`aml_cases` |

> 엔진(aml-svc) public 알림 목록은 `status`(optional, 미지정=전체)·`rule`·`channel`·`corridor` 필터의 큐 조회다. **운영자 화면용 다중 필터 브라우즈 목록(`sourceOrigin`·`severity`·`scenario`·`channel`·`corridor`·`targetRef`·`from`/`to`)은 bo-api `GET /api/v1/bo/aml/alerts`(§2.5a)** 가 위임·집약한다.

> **알림 lifecycle 상태기계(코드=truth, `AlertController`·`domain/Alert.java`).** `DETECTED ──:triage──▶ TRIAGED ──{:open-case|:dismiss|:escalate|:recommend-str}──▶ {CASE_OPENED|DISMISSED|ESCALATED|STR_RECOMMENDED}`(6종 종결값, DB §5.7). `:dismiss` 만 `DETECTED`/`TRIAGED` 양쪽에서 허용(1차 분류 없이 즉시 오탐 종결 가능)하고, 나머지 3종(`:open-case`/`:escalate`/`:recommend-str`)은 `TRIAGED` 에서만 허용된다. **`dispositionReason`/`dispositionActor` 불변식: `DISMISSED` 전이에서만 non-null**(그 외 상태는 null). 불법 전이는 `IllegalStateException`→**409 `AML.STATE_CONFLICT`**("Expected status TRIAGED but was DETECTED" 등)로 표면화하며, bo-api `AmlEngineClient.mapError` 가 안전한 기대/실제 상태 토큰만 구조화해 bo-web 이 사용자 라벨을 매핑한다(§2.5a·free-text 미에코). 4-eyes 비대상(scope `aml:case:update` 단일 — 케이스 `:close`(EDD_CLOSE)·FDS CASE_CLOSE만 2인 결재, 가정 G2).

> **알림 read 경로 마스킹 verbatim·자동 복호화 없음(코드=truth, `AlertController`·`AlertRelatedTransactionsService`, P0-09).** `GET /api/v1/aml/alerts/{alertId}`·`GET /api/v1/aml/alerts/{alertId}/related-transactions`·`GET /api/v1/aml/alerts`(목록)의 `aml:case:read` 경로는 **저장된 마스킹/토큰 evidence 를 verbatim 반환**하며 어떤 자동 복호화(구 `enrichEvidence`)도 수행하지 않는다 — SANCTION/PEP 당사자 원문·매칭 워치리스트 엔트리 원문·수취인 원문 이름을 이 경로에서 reveal 하지 않는다. `RelatedTransactionDto.counterpartyName` 은 `aml:case:read` 에서 **항상 null**(마스킹 토큰 `counterpartyRef` 폴백)이고, 원문은 오직 감사되는 `aml:pii:reveal` reveal API(`POST /internal/v1/aml/pii/reveal`, §2.6)에서만 요청 한정 transient cleartext 로 산출된다(사유+`RAW_DATA_ACCESS` 감사·fail-closed). Subject360 fund-view read(§2.5a) 역시 COUNTERPARTY 노드를 토큰(+국가 폴백) 라벨로 표시하고 원문 이름을 자동 reveal 하지 않는다.

### 2.5 Regulatory Evidence API (Public) — 설계서 §15.6

| 메서드 | 경로 | scope | 멱등 | 설명 | DB |
|---|---|---|---|---|---|
| GET | `/api/v1/evidence/aml/customers/{customerRef}/profile` | `aml:evidence:export` | — | 고객 CDD/EDD/RA/WLF 프로필 evidence | 다중 |
| GET | `/api/v1/evidence/aml/customers/{customerRef}/activity-summary` | `aml:evidence:export` | — | EDD 소득정합성 재료(최근 30일 건수·합계 + 관측기간 월평균 + exact alert/case/screening/관계·UBO edge/최근 거래상대방 집계 + `degraded`, `ActivitySummaryDto`) | `aml_canonical_events`,`aml_alerts`,`aml_cases`,`aml_screening_results`,`aml_relationships` |
| GET | `/api/v1/evidence/aml/customers/{customerRef}/fund-view?page=&size=` | `aml:evidence:export` | — | 최근 30일 거래피드 서버 페이징(size 1~200) + page-local 자금그래프. 응답 `{transactionFeed,fundGraph,totalCount,degraded}`; totalCount는 exact, `degraded=true`면 0을 실측 0으로 단정하지 않음 | `aml_canonical_events` |
| GET | `/api/v1/evidence/aml/cases/{caseId}/timeline` | `aml:evidence:export` | — | case timeline evidence | `aml_cases` |
| GET | `/api/v1/evidence/aml/reports/str-candidates?from&to` | `aml:evidence:export` | — | STR 후보 기간 조회 | `aml_regulatory_reports` |
| POST | `/api/v1/evidence/aml/exports` | `aml:evidence:export` | Y | evidence pack export 생성(manifest hash) | `aml_evidence_exports` |
| GET | `/api/v1/evidence/aml/exports/{exportId}` | `aml:evidence:export` | — | export 상태·다운로드 URL 조회 | `aml_evidence_exports` |

> **불변 evidence 다운로드 무결성 검증(P0-12 phase-1 CC1, 코드=truth `EvidenceExportService.verifyIntegrity`).** evidence pack 은 생성(COMPLETED) 시점에 렌더한 bytes 를 `aml_evidence_exports.artifact_bytes` 에 **write-once** 로 저장하고 그 SHA-256 을 `object_checksum` 에 고정한다(DB §3.15). 다운로드는 **저장 bytes 를 serve**(재생성·원천 업무 DB 재조회 없음)하며 serve 전 `object_checksum` 재계산·저장값 비교 + `manifest_hash` 존재를 검증한다 — 불일치(at-rest 변조) 시 **409 `AML.EXPORT_TAMPER`**(§4)로 차단하고, 그 직전에 `EXPORT_TAMPER` 감사(§DB 5 audit_event_category, silent 금지)를 기록한다. 따라서 export 후 원천 업무 DB 가 바뀌어도 download bytes·hash 는 불변이다. `object_checksum` 이 없는 legacy export 는 검증 대상이 아니다(폴백). 버전 핀(policy/rule-set/model/watchlist)은 생성 경로 확보값만 채우고 실값 스냅샷은 phase-2, S3 WORM·legal hold·파기 승인/증명은 phase-2 BLOCKED.

### 2.5a 대상 360° 통합 뷰 (bo-api 집계, 신규 — hanpass-ph 재그라운딩)

| 메서드 | 경로 | scope | 멱등 | 설명 | DB |
|---|---|---|---|---|---|
| GET | `/api/v1/bo/aml/subjects/{customerRef}/360?page=&size=` | `aml:case:read` | — | **대상 360° 통합 뷰** — 엔진 fund-view의 동일 page/size를 관통시키며 `transactionFeedTotalCount` exact count와 `transactionFeedDegraded`를 함께 반환한다. UI의 더 보기는 실제 다음 페이지를 요청·병합한다. RA-003 드릴다운·CASE 타임라인·TM 알림 상세의 공통 골격. 응답 DTO §3.4b `Subject360Dto` | 다중(read model) |
| GET | `/api/v1/bo/aml/alerts?status=&severity=&sourceOrigin=&rule=&from=&to=&targetRef=&channel=&corridor=&page=&size=` | `aml:case:read` | — | **TM 알림 브라우즈 목록**(AML-TM-001 ①, 출처 AML/FDS/VENDOR·심각도·상태·룰·기간·채널·corridor·대상 필터). 응답 `AlertDto[]`(§3.4a, `ruleCode`). bo-api `AmlTmController`가 aml-svc 위임. **필터 파라미터명 = `rule`**(문자열 CTR/STR 룰 코드 매칭, v9.21 — 레거시 `scenario` 폐기. aml-svc `GET /api/v1/aml/alerts?rule=` 위임 정합) | `aml_alerts` |
| POST | `/api/v1/bo/aml/alerts/{alertId}:triage` | `aml:case:update` | — | **알림 1차 분류 위임**(`DETECTED`→`TRIAGED`). body optional `AlertTriageRequest{actor?}`. 응답 `AlertActionResponse{alertId, status, caseId?, caseStatus?}`. aml-svc `:triage` 위임(비운영 stub 은 라이브 인메모리 알림 상태 전이·prod 미설정 위임 fail-closed 503 `AML.ENGINE_UNAVAILABLE`, 가정 G7). 감사 `AML_ALERT_TRIAGED`(비-4-eyes) | `aml_alerts` |
| POST | `/api/v1/bo/aml/alerts/{alertId}:dismiss` | `aml:case:update` | — | **알림 오탐 종결 위임**(`DETECTED`/`TRIAGED`→`DISMISSED`). body `AlertDismissRequest{reason 필수(@NotBlank), actor?}` — **`reason` 공백 시 400**(bo-api 계층에서 사유 필수 강제, G1)으로 오탐율(§12-B.3) 실 분모·감사 근거 확보. 위임 시 optional `{reason, actor}` 를 엔진 `:dismiss` 로 전달. 응답 `AlertActionResponse`. 감사 `AML_ALERT_DISMISSED`(사유 동반) | `aml_alerts` |
| POST | `/api/v1/bo/aml/alerts/{alertId}:escalate` | `aml:case:update` | — | **알림 상위 승인 위임**(`TRIAGED`→`ESCALATED`, 케이스 개설). body optional `AlertHandOffRequest{caseType?, actor?}`. 응답 `201 AlertActionResponse`(`caseId`/`caseStatus` 포함). aml-svc `:escalate` 위임(stub 은 케이스 미조작·라이브 알림 전이만). 감사 `AML_ALERT_ESCALATED` | `aml_alerts`,`aml_cases` |
| POST | `/api/v1/bo/aml/alerts/{alertId}:recommend-str` | `aml:case:update` | — | **알림 STR 권고 위임**(`TRIAGED`→`STR_RECOMMENDED`, STR 케이스 개설 + 엔진 아웃박스 적재). body optional `AlertHandOffRequest{caseType?, actor?}`. 응답 `201 AlertActionResponse`(`caseId`/`caseStatus`). aml-svc `:recommend-str` 위임. 감사 `AML_ALERT_STR_RECOMMENDED` | `aml_alerts`,`aml_cases` |
| GET | `/api/v1/bo/aml/tm-scenarios/{scenarioCode}` | `aml:admin:policy` | — | **TM 시나리오 정의 read model**(AML-TM-002). bo-api BFF가 엔진 active `parameters`/`dsl` 또는 non-prod stub template을 `ScenarioDefinition{family, severity, fields[]}`로 디코드해 반환한다(DTO §3.4c). HIGH_RISK_CORRIDOR는 방향·고위험 국가·회랑 윈도우·건수/금액 임계 필드를 노출하고, SIGNAL 계열은 시그널 토글 필드를 노출한다. NUMBER/AMOUNT 임계 필드는 위험등급별 차등 임계(`CriterionField.thresholdsByGrade`, §3.4c)를 동반 노출한다. raw PII 없음, 설정 조회 전용. | 정책 store(read model) |

> bo-api 소유 집계(read-only 파생, raw PII 미노출). STR 건수 등 tipping-off 민감 항목은 준법감시 전담 scope 한정 투영(설계서 §19.2a). 엔진 `GET /aml/customers/{customerRef}/profile`(CDD-002)·`/risk`를 결합하며 별도 영속 테이블 없음.

> **알림 lifecycle 위임 4종 + 409 표면화 계약(코드=truth, `AmlTmController`·`AmlTmService`·`AmlEngineClient`).** bo-api `AmlTmController` 는 위 4개 알림 처분 액션을 aml-svc 엔진 `AlertController`(§2.4 `:triage`/`:dismiss`/`:escalate`/`:recommend-str`)에 위임한다. 위임 모드=`AmlEngineClient` 경유 엔진 호출, 비운영 stub 모드=라이브 인메모리 알림 상태 전이 즉시 반영(동형 응답), 운영 프로필 미설정 위임=fail-closed(503 `AML.ENGINE_UNAVAILABLE`, 가정 G7). 4종 모두 4-eyes 비대상(케이스 `:close`(EDD_CLOSE)·FDS CASE_CLOSE만 2인 결재 유지, 가정 G2)이며 감사 이벤트 `AML_ALERT_TRIAGED`/`AML_ALERT_DISMISSED`/`AML_ALERT_ESCALATED`/`AML_ALERT_STR_RECOMMENDED`(bo-api Flyway V13 `chk_bo_audit_logs_event` allowlist)를 각각 남긴다. **409 `AML.STATE_CONFLICT` 표면화**: `AmlEngineClient.mapError` 는 엔진 free-text detail 을 에코하지 않고(내부/PII 누출 방지, 가정 G8) **알림 상태 6종 enum 토큰(`DETECTED`/`TRIAGED`/`CASE_OPENED`/`DISMISSED`/`ESCALATED`/`STR_RECOMMENDED`)만** 추출해 `"AML.STATE_CONFLICT expected=<상태> actual=<상태>"` 로 구조화하며, 그 외 모든 단어는 폐기한다 — bo-web `lib/error-messages.ts`+i18n 카탈로그가 이 구조화 필드로 "먼저 1차분류하세요" 같은 사용자 라벨을 매핑한다. 비운영 stub 경로도 동일 상태기계를 모사해 동일 409 를 던진다(버튼 무반응 해소).

### 2.6 Internal API (엔진 간) — 설계서 §6.1·§12.3·D-07

| 메서드 | 경로 | 호출자 | 설명 | DB |
|---|---|---|---|---|
| POST | `/internal/v1/aml/fds-escalations` | `fds-svc` | FDS fraud case → AML case/alert escalation 수신(body §3.10 `FdsEscalationRequest` → `FdsDecisionCommand` 어댑팅, `eventId`=멱등키(없으면 `fraudCaseRef`), `action`=FDS handoff verb, 응답 `{ alertId, accepted }`). SQS `aml-fds-decision` 큐 경로(`FdsDecisionConsumer`)와 **동일 usecase·동일 멱등(DB partial UNIQUE)·동일 감사**(T11/AML-ENG-05). non-AWS REST fallback은 wire v2-only, `aml:internal:fds-escalation:write`, signed `X-Internal-Service=fds-svc`, body/header dataScope 일치를 수신 엔진에서 강제한다. | `aml_alerts`(source_origin=FDS) |
| GET | `/internal/v1/aml/customers/{customerRef}/risk` | `fds-svc` | AML high-risk/WLF 상태 조회(FDS risk group 전파용). public `GET /api/v1/aml/customers/{customerRef}/risk`와 동일 `AssessRiskUseCase`·`CustomerRiskResponse` 재사용(가정 A6), 최신 RA 등급 단독(WLF 병합 미정의 → 후속). 미존재 시 404 `AML.NOT_FOUND`. wire v2-only + `aml:case:read`. | `aml_risk_scores`,`aml_screening_results` |

> **RA 검토·설정 계약(2026-07-10)**: `GET /api/v1/aml/customers/{customerRef}/risk`는 최신 점수가 ONGOING이어도 대상의 최신 ONBOARDING 검토를 `onboardingReview`로 함께 반환한다. 상태는 `REQUIRED|COMPLETED|AUTO_COMPLETED`, 필드는 `scoreId/reasonCodes/identityChecked/evidenceChecked/followUpChecked/completionNote/completedBy/completedAt/createdAt`이다. RA model draft 계약은 `scenario`와 `parameters`를 수신하며 ONBOARDING `screening.listTypeScores.{SANCTION,PEP}` 및 ONGOING `ruleSeverityWeights`(STR/CTR/FDS), lookback/count saturation/debounce/EDD 설정을 검증한다. APPROVED/SUPERSEDED 버전 직접 수정은 409/상태 오류이며 신규 DRAFT→simulate→RA_MODEL 4-eyes만 허용한다.
| POST | `/internal/v1/aml/screen` | 내부 onboarding mesh | 내부 서비스용 동기 screening. public `POST /api/v1/aml/screen`와 동일 `ScreenSubjectUseCase`·`ScreenRequest`/`ScreeningResponse` 재사용(가정 A6), `Idempotency-Key` 헤더 필수(가정 A4·공개 경로 일관). wire v2-only + `aml:screen:evaluate`. | `aml_screening_results` |
| POST | `/internal/v1/aml/pii/reveal` | `bo-api` | 마스킹 PII reveal 정본(입력 `targetRef`/`field`/`reason` → 출력 `value`=이 요청 한정 transient cleartext). **`targetRef` = subject 참조**(회원 `customerRef` 또는 워치리스트 엔트리 `entryId`) — vault·엔진이 이 참조로 원문을 해소한다. 마스킹 **값** 토큰(표시명 마스킹·문서/이름 hash·UBO ref 등)을 `targetRef` 로 보내면 해소 불가(run5 #2). `field` 도메인 7종(`NAME`/`DOC`/`ACCOUNT`/`WALLET`/`NATIONALITY`/`GENDER`/`DOB`, §1.6, 2026-06-29 확장) — 이외 값은 **400 `AML.BAD_REQUEST`**. wire v2-only + `aml:pii:reveal` + exact signed `X-Internal-Service=bo-api`를 수신 엔진에서 강제한다. 엔진측 `RAW_DATA_ACCESS` 감사 1건(마스킹 detail). 역참조 미존재·복호화 실패 시 **503 `AML.SCREENING_UNAVAILABLE`**(fail-closed). **비운영 stub 경로**(bo-api, delegate 미설정)에서 vault·데모 카탈로그 어디에도 없는 미인식 `targetRef` 는 가짜 원문 placeholder 를 반환하지 않고 **404 `AML.PII_TARGET_NOT_FOUND`**(감사 미기록 — 실패가 audit 이전, run5 #2). mesh mTLS는 배포계층(P8) 보강. | `aml_pii_vault`(가역암호 vault, DB §3.21) |

### 2.7 Admin API (bo-api 전용) — 설계서 §13~§14·§16

#### Tenant Policy Binding (§16, P0-16)
| 메서드 | 경로 | scope | 4-eyes | 설명 | DB |
|---|---|---|---|---|---|
| PATCH | `/api/v1/admin/aml/tenants/{tenantId}/policy-binding` | `aml:admin:policy` | — | **테넌트 관할·통화·Policy Pack revision 바인딩(P0-16, upsert)** — tenant 를 REST 로 `PH·PHP` 또는 `KR·KRW` 등에 바인딩하는 프로비저닝 진입점(데모 비즈니스 seed 아님). 요청 `BindRequest{ jurisdiction(ISO 3166-1 alpha-2, 필수), baseCurrency(ISO 4217, 필수), reportingCurrency?(생략 시 baseCurrency), timezone?, policyPackVersion(필수) }`. `Tenant-Id` 헤더=경로 `tenantId` 일치 필수(불일치 = cross-tenant write 거부). 잘못된 ISO country/currency → `400 AML.BAD_REQUEST`, 미존재 tenant/비-effective Policy Pack revision → `422 AML.TENANT_POLICY_UNBOUND`. 멱등 upsert. 응답 `200 { tenantId, jurisdiction, baseCurrency, reportingCurrency, timezone, policyPackCode, policyPackVersion, policyPackEffectiveFrom }`(= `TenantPolicyBinding`). | `aml_tenants`(DB §3.1·V53) |

> **정책 표면 구획(§0.5 온보딩 경계와 별개).** §0.5 는 **배포 모델·온보딩 신청**(서비스 등록·프로비저닝 상태머신)을 bo-api 소유로 두고 aml-svc 엔진 API 에 미추가함을 정본으로 한다. 본 `PATCH .../tenants/{id}/policy-binding` 은 그 온보딩 표면이 아니라 **엔진 규제 정책 표면**(관할·통화·Policy Pack revision — 엔진 corridor/통화 해석·evidence 고정의 입력)이며, 이미 등록된 tenant 의 정책 바인딩을 설정한다. 온보딩(`/api/v1/bo/aml/tenants`·`/onboarding/*`, bo-api 전용)과 정책 바인딩(엔진 `/api/v1/admin/aml/tenants/{id}/policy-binding`)은 **서로 다른 표면**으로 구획한다(온보딩=서비스 lifecycle, 정책 바인딩=규제 파라미터). bo-api tenant shadow 의 관할·통화 동기는 후속(phase-2 A1 경계).

#### Watchlist / 명단 (§10)
| 메서드 | 경로 | scope | 4-eyes | 설명 | DB |
|---|---|---|---|---|---|
| GET | `/api/v1/admin/aml/watchlist-sources` | `aml:admin:watchlist` | — | source 목록 | `aml_watchlist_sources` |
| POST | `/api/v1/admin/aml/watchlist-sources` | `aml:admin:watchlist` | — | source 등록 | `aml_watchlist_sources` |
| POST | `/api/v1/admin/aml/watchlist-sources/{sourceCode}/imports` | `aml:admin:watchlist` | — | import 업로드(diff 생성, DRAFT) | `aml_watchlist_entries` |
| POST | `/api/v1/admin/aml/watchlist-sources/{sourceCode}/imports/{version}:apply` | `aml:admin:watchlist` | 🔒4-eyes | import 적용(active_version 승격) | `aml_watchlist_sources` |
| POST | `/api/v1/admin/aml/watchlist-sources/{sourceCode}/sync` | `aml:admin:watchlist` | — (auto-apply, 4-eyes 아님) | **실 무료 공개 제재명단(OFAC SDN·UN Consolidated) 동기화** — fetch→StAX 파싱→멱등 upsert(외부키 `external_ref`)→**auto-apply**(actor `system:sanctions-sync`, 공개·권위 소스는 사람 승인 없이 `active_version` 승격)→DELISTED 정리→버전 prune(최근 2개)→freshness 갱신. 외부망 장애는 예외 미전파(fail-safe, 200+`outcome=FAILED`) — freshness 미갱신 시 48h 게이트가 스크리닝 fail-closed(설계 의도). 응답 `WatchlistSyncResult`(sourceCode·outcome(APPLIED/UNCHANGED/FAILED)·activeVersion·ingestedCount·delistedCount·prunedCount·lastImportedAt). 스케줄러(기본 03:20 UTC, `SanctionsImportScheduler`) 일일 자동 + 본 엔드포인트 수동 트리거. | `aml_watchlist_sources`,`aml_watchlist_entries` |
| GET | `/api/v1/admin/aml/watchlist-entries` | `aml:admin:watchlist` | — | 명단 항목 조회(masked)·**`entryIds`(콤마구분) 지정 시 배치 해소(엔진 `WatchlistEntryQueryService.listByIds`, 요청당 최대 200-id 클램프)** | `aml_watchlist_entries` |
| GET | `/api/v1/admin/aml/mandatory-sources` | `aml:admin:watchlist` | — | **필수 watchlist source 정책 조회(P0-06)** — tenant 의 fail-closed readiness 게이트(§2.2) 기준이 되는 필수 source 목록. 응답 `MandatorySourceResponse[]`(`jurisdiction`·`sourceType`·`sourceCode`·`capability`(PROD/NOT_APPLICABLE)·`notApplicableReason/ApprovedBy/ExpiresAt`·`requiredFrom`·`deprecatedAt`) | `aml_mandatory_watchlist_sources` |
| POST | `/api/v1/admin/aml/mandatory-sources` | `aml:admin:watchlist` | — | **필수 source 정책 등록(upsert)(P0-06)** — REST-only seed 진입점(시뮬레이터/부트스트랩; Flyway 데모 시드 금지). 요청 `RegisterMandatorySourceRequest{ jurisdiction?, sourceType, sourceCode?, capability?(기본 PROD), notApplicableReason?, notApplicableApprovedBy?, notApplicableExpiresAt?(ISO-8601), requiredFrom?, deprecatedAt? }`. `jurisdiction`/`sourceCode` 미지정 시 `'*'` 와일드카드 센티넬로 접어 저장(PK total). config 성격이라 4-eyes 아님. | `aml_mandatory_watchlist_sources` |
| POST | `/api/v1/admin/aml/watchlist-sources/{sourceCode}:override` | `aml:admin:watchlist` | — | **긴급 readiness override(P0-06)** — source 를 시한부로 `OVERRIDDEN`(강제 screening-ready)으로 전이. 요청 `OverrideRequest{ reason, approvedBy, expiresAt(ISO-8601) }`(사유·승인자·만료). 응답 `SourceOverrideResponse{ sourceCode, readinessStatus, readinessOverrideExpiresAt }`. 만료 시 자동 원상(effectiveReadiness 파생, DB §3.6 후주). 사유·승인자·영향 건수는 `WATCHLIST_READINESS` 감사(DB §3.15). | `aml_watchlist_sources`,`aml_audit_events(WATCHLIST_READINESS)` |

> **bo-api `GET /api/v1/bo/aml/watchlist-entries` `entryIds` 배치 해소 모드(코드=truth, run7 RA-003).** 기존 브라우즈 필터(`sourceCode`·`listType`·`status`·`name`·`country`·`addedFrom`/`addedTo`·`version`) 외에 **`entryIds`(콤마구분 문자열, 반복 파라미터 허용)** 를 노출한다. `entryIds` 지정 시 **다른 필터는 무시**하고 지정 엔트리를 배치 해소하며 **요청 id 순서를 보존**(미존재 id 는 결과에서 누락)한다. 위임 경로는 엔진 `GET /api/v1/admin/aml/watchlist-entries?entryIds=`(200-id 청크로 분할)로 위임하고, 비운영(stub) 경로는 stub 소스에서 필터 해소한다(양경로 `AmlWatchlistService.findEntriesByIds`). 응답은 브라우즈와 **동일 페이징 봉투 `WatchlistEntryPage{rows, page, size, totalElements, totalPages}`**(`totalElements`=해소 성공 엔트리 수). 행은 §3.x `WatchlistEntryDto` 공개 필드(`normalizedTokens`·`listType`·`subjectKind`·`country`·`nationality`·`dob`·`program`·`version`·`status`·`createdAt`·`externalRef`) — 공개 제재명단 데이터로 raw PII 미노출 규약 불변. **용도**: RA 상세(AML-RA-003 ①)의 신원 대조 패널에서 `forcedFloorEvidence[].entryId` 를 배치 조회해 회원 신원(reveal 게이트, §2.6 `/pii/reveal`)과 명단 엔트리 원본값을 나란히 비교(공개 명단측만 plaintext).

> **명단 엔트리 브라우저 딥링크 계약(§딥링크 계약).** RA 상세·WLF 매치 근거 패널(§3.3 `forcedFloorEvidence`)의 '명단 엔트리 조회 ▶' 링크는 BE 가 제공하는 참조 토큰만으로 명단 엔트리 브라우저(AML-WL-001 ③, bo-web `/aml/watchlist`)로 딥링크한다: **`/aml/watchlist?listType=<listType>&entry=<entryId>`**. `listType`·`entry` 는 `forcedFloorEvidence[]` 원소의 `listType`/`entryId` 를 그대로 전달하며, 브라우저 진입 시 `listType` 을 엔트리 목록 사전필터로 적용한다. **구 `?source=<sourceCode>` 계약은 폐기** — BE `ForcedFloorEvidence` 는 `sourceCode` 를 제공하지 않는다(raw PII·비제공 토큰 미노출 규약). 토큰 부재 시 브라우저 기본 목록으로 폴백.

> **bo-api 위임(§10.4).** BO 화면 수동 트리거는 `POST /api/v1/bo/aml/watchlist-sources/{sourceCode}/sync`(scope `aml:admin:watchlist` or `BO_SUPER_ADMIN`, `AmlWatchlistController`) → `AmlEngineClient`로 위 엔진 `.../{code}/sync`에 순수 위임한다(응답 `WatchlistSyncResponse` 미러, 운영자 감사 `WATCHLIST_IMPORT_APPLIED`·trigger MANUAL). 제재명단 수집은 엔진 전용 표면이라 **비위임(stub) 모드는 fail-closed 503 `AML.ENGINE_UNAVAILABLE`**(위조 성공 카운트가 48h freshness 게이트를 잘못 갱신하는 것 방지, 4-eyes 계약 대상 아님).

> **명단 import multipart machine-auth v2 서명 규약(P0-14, 코드=truth).** `.../imports`(§339) 업로드 위임은 `multipart/form-data` 본문을 **일반 client 직렬화가 아니라 결정론적 raw bytes 로 먼저 조립**한다(`AmlEngineClient` → `common-security/MultipartFormBodyBuilder`, RFC 7578·CRLF). boundary 는 서명된 one-time `X-Nonce` 에서 유도(`AegisBoundary<nonce>`)하고, 그 exact bytes 와 짝이 되는 `Content-Type`(boundary 포함) 을 서명 전에 확정한다. bo-api 는 `sha-256(rawBytes)`+`Content-Type`(§scopeContext `content-type` 결합)을 machine-auth v2 로 서명하고 **동일 bytes 를 재직렬화 없이** 전송하며, 엔진 공통 filter(`AmlIngestAuthenticationFilter`)가 raw body 를 다시 SHA-256 검증한다 — 운영 HMAC 통과, **서명 뒤 body·`Content-Type` 변조 시 401 fail-closed**. 계약 정본은 [공통 machine-auth §3.4](00-common-machine-auth.md#34-multipart-본문-계약p0-14-코드truth). 종전 빈-body 거부(`AML.MULTIPART_AUTH_UNAVAILABLE`) fail-closed 스텁은 이 raw-byte 서명 전환으로 제거됐다. explicit local/demo bootstrap 은 동일 bytes 를 서명 없이 전송하고, 그 밖의 credential 미보유는 여전히 fail-closed 다.

#### WLF 엔진 설정 (§10.3, AML-WLF-005)

| 메서드 | 경로 | scope | 4-eyes | 설명 | DB |
|---|---|---|---|---|---|
| GET | `/api/v1/admin/aml/wlf-engine-config` | `aml:admin:watchlist` **or** `aml:admin:policy` | — | tenant의 런타임 적용 WLF 룰 버전과 정책팩 버전 이력, SANCTIONS·PEP별 가중치/불일치 감점/검토·고신뢰 임계 조회. 기존 WLF 시뮬레이션 운영자는 현재 적용 기준 조회만 허용한다. `status=ACTIVE && active=true`를 동시에 만족하는 정책팩이 없거나 복수이면 screening 선택과 동일하게 fail-closed한다. typed profile 키가 없는 legacy/pending 이력은 저장된 `wlf.possible-threshold`/`wlf.true-threshold`를 우선 SANCTIONS·PEP에 fan-out하고, 나머지 누락값은 코드 기본 profile(6가중치·negativePenalty 0.20, 기본 band 0.66/0.92)로 하위호환 해석한다. 유효하지 않은 수치·임계 또는 저장된 definitionHash 불일치는 fail-closed하며, V38은 비-DRAFT 이력을 canonical typed form으로 보강한다. | `aml_policy_packs.parameters` |
| POST | `/api/v1/admin/aml/wlf-engine-config:change` | `aml:admin:policy` | 🔒 `POLICY_PACK` | 전체 SANCTIONS·PEP 프로필을 새 정책팩 DRAFT로 상신. maker는 인증 principal에서 파생하고, checker 승인·EXECUTED 전에는 ACTIVE 스크리닝에 영향 없음 | `aml_policy_packs`,`aml_approvals` |

> **BFF 미러.** bo-web은 엔진을 직접 호출하지 않고 `GET/POST /api/v1/bo/aml/wlf-engine-config[:change]`만 사용한다. GET은 `aml:admin:watchlist` 또는 `aml:admin:policy`(기존 WLF-004 simulation 호환), POST는 `aml:admin:policy`만 허용한다(`BO_SUPER_ADMIN` 우회 포함). bo-api는 DTO를 손실 없이 위임하며 delegate 미구성/빈 응답을 성공으로 위조하지 않고 `503 AML.ENGINE_UNAVAILABLE`로 fail-closed한다. 메뉴 `AML-WLF-005`(`/aml/wlf-engine`)는 `aml:admin:policy` 또는 `BO_SUPER_ADMIN`만 접근한다.

`WlfEngineConfigResponse`:

```json
{
  "activeRuleVersion": "wlf-rule-v3",
  "versions": [{
    "policyPackCode": "KR_DEFAULT",
    "policyPackVersion": "v7",
    "status": "ACTIVE",
    "configVersion": "wlf-config-v3",
    "ruleVersion": "wlf-rule-v3",
    "definitionHash": "sha256:...",
    "effectiveFrom": "2026-07-11T00:00:00Z",
    "profiles": {
      "SANCTIONS": {
        "weights": {"NAME": 0.55, "DATE_OF_BIRTH": 0.10, "COUNTRY": 0.10, "DOCUMENT": 0.15, "ADDRESS": 0.05, "RELATIONSHIP": 0.05},
        "negativePenalty": 0.20,
        "reviewThreshold": 0.65,
        "highConfidenceThreshold": 0.92
      },
      "PEP": {
        "weights": {"NAME": 0.55, "DATE_OF_BIRTH": 0.10, "COUNTRY": 0.10, "DOCUMENT": 0.15, "ADDRESS": 0.05, "RELATIONSHIP": 0.05},
        "negativePenalty": 0.20,
        "reviewThreshold": 0.65,
        "highConfidenceThreshold": 0.92
      }
    }
  }]
}
```

`WlfEngineConfigChangeRequest`는 `{ expectedActiveRuleVersion, profiles, reason }`이며 `profiles`는 위와 같은 **SANCTIONS·PEP 닫힌 집합 전체**다. `expectedActiveRuleVersion`은 화면이 편집한 ACTIVE 버전의 필수 낙관적 동시성 토큰이며 현재 값과 다르면 `409 AML.STATE_CONFLICT`로 상신을 거부한다. 호출자 지정 `effectiveFrom`은 지원하지 않고 승인 EXECUTED 시각을 서버가 기록한다. 각 profile은 6개 weight 닫힌 집합, 유한수·`0..1`, 양수 weight 합, `reviewThreshold < highConfidenceThreshold`를 만족해야 한다. 서버는 active policy-pack row lock 아래 단일 DRAFT만 허용하고 `configVersion`과 WLF 전용 `ruleVersion`을 자동 증가시키며 canonical 전체 정의의 `definitionHash`를 계산한다. 반려 시 후보는 `REJECTED`로 종결되어 후속 상신을 막지 않는다. 응답은 `202 { approvalId, status, candidateConfigVersion, candidateRuleVersion, definitionHash }`. PEP/RCA 엔트리는 PEP profile, 그 외 source/list type은 SANCTIONS profile로 평가한다. 한 평가 요청은 ACTIVE 전체 정의를 1회 pin해 후보 전부에 같은 ruleVersion을 적용한다. `highConfidenceThreshold`는 검토 우선순위/evidence 경계이며 분석가 4-eyes 없이 `TRUE_MATCH`를 자동 생성하지 않는다.

> **단건 시뮬레이션 profile 필터.** Admin/BFF `POST .../screenings:simulate` 요청은 `{ name, nameRomanized?, similarityThreshold?, targetType?, dob?, country?, documentHash?, sourceTypes? }`를 사용한다. 이 분석 전용 경로는 기존 WLF 도구의 `aml:admin:watchlist`와 AML-WLF-005의 `aml:admin:policy` 중 하나를 허용한다(일괄 수행·template은 계속 watchlist 권한 전용). `sourceTypes`는 명단 소스 유형의 닫힌 배열이며 AML-WLF-005는 SANCTIONS 탭에서 `['SANCTIONS']`, PEP 탭에서 `['PEP','RCA']`를 보낸다. 생략 시 모든 ACTIVE 명단을 평가한다. 서버는 ACTIVE 전체 정의를 1회 pin하고 후보 조회·profile 선택 모두에 이 필터를 적용한다. 응답의 적용 임계와 `appliedPolicy`는 실제 ACTIVE 설정에서 파생한다. 호출자가 임의 `similarityThreshold`를 보낸 경우 분석용 override이며 ACTIVE `highConfidenceThreshold` 미만이어야 하고 영속 screening/ACTIVE 정책을 변경하지 않는다.

#### Screening 검토 (§10.4)
| 메서드 | 경로 | scope | 4-eyes | 설명 | DB |
|---|---|---|---|---|---|
| GET | `/api/v1/admin/aml/screenings?status=POSSIBLE_MATCH` | `aml:case:read` | — | 검토 큐 조회. `transactionRef`가 있으면 거래번호+`targetType`별 최신 1건을 먼저 투영한 뒤 상태를 필터링하며, 거래번호 없는 독립 screening은 모두 유지 | `aml_screening_results` |
| POST | `/api/v1/admin/aml/screenings/{screeningId}/decision` | `aml:case:update` | 🔒4-eyes(TRUE_MATCH/FP) | WLF 판정(true/false positive) | `aml_screening_results`,`aml_approvals` |
| POST | `/api/v1/admin/aml/screenings/fp-whitelist` | `aml:admin:watchlist` | 🔒4-eyes | false positive whitelist 등록 | `aml_approvals`,`aml_fp_whitelist` |

> **`FpWhitelistRegisterRequest`(FP whitelist 등록 요청, DB `aml_fp_whitelist` §3.8a — 코드=truth).** 4-eyes 상신 payload(bo-api `ScreeningDtos.FpWhitelistRegisterRequest`·aml-svc `WhitelistFalsePositiveUseCase.WhitelistCommand`=truth):
> | 필드 | 타입 | 필수 | 설명 |
> |---|---|---|---|
> | `screeningId` | string(uuid) | Y | 면제를 촉발한 발원 스크리닝 결과 id(DB `screening_id`, **V14**, §3.8 추적성 — 아래 `matchedEntryId`(엔트리 id)와 **별개 슬롯**·discount 키 아님) |
> | `targetRef` | string | Y | 면제 대상 ref(DB `target_ref`) |
> | `matchedEntryId` | string | Y | **면제 대상 워치리스트 엔트리 id**(DB `matched_entry_id`, §3.7 `entry_id`) — **discount matchFeature 슬롯**. 반드시 워치리스트 `entry_id`(절대 `screeningId` 아님 — 과거 이 슬롯에 screeningId 를 넣어 `AUTO_DISCOUNTED` 미발동, run2 D2). 단건(요청당 엔트리 1개) |
> | `targetType` | enum | N | 스크리닝 행의 대상 유형(DB `target_type` §5.23, `CUSTOMER`/`ENTITY`/`COUNTERPARTY`/`CRYPTO_ADDRESS`) — 수취인(COUNTERPARTY) 면제가 하드코딩 CUSTOMER 로 기록되지 않도록 승계 |
> | `makerId` | string | Y | 상신자(4-eyes maker). checker≠maker 승인 필요 |
> | `reason` | string | N | 면제 사유(DB `reason`, **V14**, maker 입력·운영 뷰 표시) |
> | `expiresAt` | string(date-time)\|null | N | 면제 만료일(DB `expires_at`, **V14**, **null=무기한**). 응답·조회에서 `expiresAt < now()` ⇒ **EXPIRED 파생 상태**(DB §3.8a 가정 A5, 스케줄러 없음·조회/discount 판정 시점 파생) 표기 |
>
> **가정 C(정정)**: 직전 초안은 `entryIds` **배치** 배열을 가정했으나 코드=truth 재검증 결과 요청 계약은 **단건 `matchedEntryId`**(bo-api `FpWhitelistRegisterRequest`·aml-svc `WhitelistCommand` 모두 단수)다 — 배치 필드 없음. 본 표는 실제 DTO(단건) 기준으로 확정한다(추측 없음). 응답 `FpWhitelistRegisterResponse{ approvalId, approvalStatus(§ SUBMITTED/…), payloadHash }`, 조회 행 `FpWhitelistEntry{ whitelistId, screeningId, targetRef, status(ACTIVE/EXPIRED/REVOKED), registeredBy, reason, registeredAt, expiresAt, revokedAt }`(bo-api DTO=truth·PII 마스킹). checker 승인(EXECUTED) 시 `aml_fp_whitelist`(active=true) 등록 → 후속 동일 매치 `AUTO_DISCOUNTED` 즉시 적용(§10 예외 규칙).

#### 회원원장(member ledger) read (§CDD·DB §3.22f, AML-CDD-004 / AML-MBR-001)
| 메서드 | 경로 | scope | 4-eyes | 설명 | DB |
|---|---|---|---|---|---|
| GET | `/api/v1/admin/aml/members/{memberRef}/ledger` | `aml:case:read` | — | 회원원장 요약(현재 `kyc_status`·`risk_grade`·재실사 예정일 + CDD/EDD 이력 카운트). 회원 키 `memberRef`(= `originator.partyReference` = `aml_customers.customer_ref`); `nationalIdentityKey`는 부재 시 tenant-keyed fallback 토큰. Masked refs only(raw PII 미노출 §19.2) | `aml_customers` |
| GET | `/api/v1/admin/aml/members/{memberRef}/cdd-history?types=&page=&size=` | `aml:case:read` | — | 회원 CDD/EDD 이력 페이지(최신순). **`types` 반복 파라미터**(예 `types=CDD_INITIAL&types=EDD_OPENED`, 생략 시 전체) enum **6종** `CDD_INITIAL·CDD_REVIEW·EDD_OPENED·EDD_CLOSED·CDD_REISSUE_REQUESTED·EDD_REISSUE_REQUESTED`(DB §3.22f `history_type` = 엔진 `CddHistoryType`, §5.36, V27). 잘못된 유형 토큰은 400. 응답 페이징 봉투 `{ rows, page, size, totalElements, totalPages }`, 행은 masked 스냅샷(`historyId·historyType·kycStatus·riskGrade·sourceEventId·traceId·actor·details·occurredAt`) — raw PII 미노출 | `aml_member_cdd_history` |
| POST | `/api/v1/admin/aml/cdd/customers/{customerRef}/reissue:request` | `aml:case:update` | — | **CDD/EDD 즉시 재이행 접수(RA 상세 AML-RA-003 '관리자 액션', V27)**. 요청 `ReissueRequest{ reissueType(CDD\|EDD), reason(필수), requestId(멱등키), actor?, traceId? }` — maker 는 위임 시 bo-api principal 파생. 접수 시 `aml_member_cdd_history` 에 `CDD_REISSUE_REQUESTED`/`EDD_REISSUE_REQUESTED` append(`source_event_id='reissue-req:'+requestId` 멱등 — 중복 요청은 `REPLAYED`), 원장 상태 무변경. 응답 `202 ReissueResponse{ requestId, historyId, historyType(CDD_REISSUE_REQUESTED\|EDD_REISSUE_REQUESTED), status(ACCEPTED\|REPLAYED) }`. **실 재이행 수행은 계정계 연동 예정**(`AccountSystemReissuePort` no-op 아답터, 코드 토큰 `TODO(계정계-연동)`) — 계정계가 재수행 후 `customer.cdd.completed` 재인입 시 `CDD_REVIEW` 폐루프. 결재 불요(운영 지시 액션 — 접수+감사 기록, 문서 미정의 지점 가정 명시) | `aml_member_cdd_history` |

> **코드=truth 역전파(feature/aml-member-ledger-contract).** 위 두 라우트는 종전 §2.x 에 미정의였다. bo-api BFF(`AmlMemberLedgerController` — `GET /api/v1/bo/aml/members/{ref}/ledger`·`/cdd-history?types=`)가 `AmlEngineClient`(`/api/v1` + path)로 aml-svc admin API(`GET /admin/aml/members/{ref}/{ledger|cdd-history}`)에 위임하므로, Admin API 프리픽스 규약(§본절 line18)을 정본으로 채택해 aml-svc `MemberLedgerController` 라우트(`/api/v1/admin/aml/members/*`)와 `types` 반복 파라미터를 확정한다. 위임 미설정 시 bo-api 는 비-prod 결정적 stub, prod 는 fail-closed(503 `AML.ENGINE_UNAVAILABLE`). enum·응답 필드는 DB §3.22f `aml_member_cdd_history` CHECK(**V26·V27**, §5.36) + 엔진 `CddHistoryType` + bo-api `MemberLedgerDtos.HistoryType` 3중 일치.
>
> **즉시 재이행 위임(feature/aml-ra-detail-admin-actions, V27).** bo-api `AmlReissueController POST /api/v1/bo/aml/members/{memberRef}/reissue:request`(scope `aml:case:update`, 요청 `{ reissueType(CDD|EDD), reason, requestId }` — maker principal 파생, 응답 `ReissueResponse{ memberRef, requestId, historyId, historyType, status }`)가 aml-svc `POST /admin/aml/cdd/customers/{ref}/reissue:request` 로 위임. 비-prod stub 은 `AmlStubStore` overlay(`ReissueOverlay`, requestId replay 멱등)로 회원관리 이력 화면에 영속 노출, prod 는 fail-closed. RA 상세 '관리자 액션' 패널의 나머지 액션은 기존 계약 재사용 — EDD 케이스 착수(`POST /bo/aml/cdd/cases` caseType=EDD_REVIEW)·CDD 재이행 주기 변경(`POST /bo/aml/customers/{ref}/review-cycle:change`, 4-eyes 🔒 PERIODIC_REVIEW_CHANGE).

#### Risk Assessment 정책·override (§11.3)
| 메서드 | 경로 | scope | 4-eyes | 설명 | DB |
|---|---|---|---|---|---|
| GET | `/api/v1/admin/aml/ra-models?modelCode=` | `aml:admin:policy` | — | RA 모델 버전 목록. 운영 family는 `KR_DEFAULT_RA=ONBOARDING`, `KR_ONGOING_RA=ONGOING` 두 개로 고정하며 임의 family를 거부한다. 응답 `RaModelSummary[]` — `scenario`, 전체 `weights`/`parameters`/임계, `isDefault`, 생성·수정 actor/시각, `copiedFromVersion`, canonical `definitionHash`, `latestSimulation`, `pendingApprovalId`를 노출한다. 실제 ACTIVE가 없으면 임의 버전을 현재 적용으로 추정하지 않는다. | `aml_risk_models`,`aml_ra_model_simulations`,`aml_approvals` |
| GET | `/api/v1/admin/aml/ra-models/onboarding-input-catalog?windowDays=` | `aml:admin:policy` | — | 최근 수신 canonical CDD를 tenant+customerRef별 최신 1건으로 축약한 1차 RA 입력 카탈로그. `windowDays` 기본 90·1~365, 축별 최대 100. 응답은 §3.3d의 코드별 집계만 포함하며 raw payload/customerRef/eventId/PII를 반환하지 않는다. | `aml_canonical_events` |
| POST | `/api/v1/admin/aml/ra-models/{modelCode}/versions:copy` | `aml:admin:policy` | — | 선택 버전을 서버측 다음 버전 `v{N+1}` DRAFT로 원자 복제. 요청 `CopyVersionRequest{ sourceVersion }`; 응답 `RaModelSummary`. `scenario`·가중치·parameters·임계를 승계하고 신규 DRAFT의 `isDefault=false`, `copiedFromVersion`/작성자/시각을 기록한다. UI 임의 버전명 생성은 허용하지 않는다. 같은 family에 `pendingApprovalId`가 하나라도 있으면 family lock 안에서 복제를 거부해 상신 대상이 새 버전에 의해 실행 불가능해지는 것을 막는다. | `aml_risk_models`,`aml_approvals` |
| POST | `/api/v1/admin/aml/ra-models` | `aml:admin:policy` | — | `versions:copy`로 서버 발급된 기존 DRAFT 전체 정의만 갱신한다(update-only). 요청 `DraftRequest{ modelCode, version, scenario, weights, mediumThreshold, highThreshold, prohibitedThreshold, parameters }`. 임의 신규 version, family-scenario 불일치, ACTIVE/SUPERSEDED 및 활성화 결재 대기 DRAFT는 수정 불가. 가중치는 scenario factor catalog(ONBOARDING=`GEOGRAPHY/CUSTOMER/SCREENING`, ONGOING=`TRANSACTION_BEHAVIOR/CUSTOMER`)와 `0..100`, 총합 양수를 검증한다. parameters는 §11.3의 scenario별 top-level/nested unknown key를 거부한다. ONBOARDING authoring은 `sofRisk=default+canonical 6종`, `kycLevelRisk=default+canonical 4종`, `occupationRisk=default+안전 분류코드`만 허용한다. 과거 ACTIVE legacy는 조회/복제할 수 있지만 DRAFT 저장·simulate·activate 전에 제거해야 한다. ONGOING 정수값은 소수 절삭 없이 exact integer이며 `lookbackDays=1..3650`, `debounceMinutes=0..525600`, `countSaturation=1..200`, baseline=`KR_DEFAULT_RA`를 강제한다. 작성자는 BFF 인증 principal에서 파생한다. | `aml_risk_models` |
| POST | `/api/v1/admin/aml/ra-models/{modelCode}/simulate` | `aml:admin:policy` | — | 요청 `RaSimulateRequest{ version, samplePopulation }`, 모집단 `RECENT_90D_NEW\|ALL_ACTIVE\|HIGH_RISK_ONLY`(tenant·scenario 격리, 최대 500). candidate와 같은 scenario ACTIVE를 실제 비PII RA 입력으로 재평가하고 결과/definition hash를 영속한다(§3.15). 결재·실제 등급 변경 없음. | `aml_ra_model_simulations`,`aml_risk_scores` |
| POST | `/api/v1/admin/aml/ra-models/{modelCode}/versions/{version}:activate` | `aml:admin:policy` | 🔒4-eyes | 요청 `ActivateRequest{ simulationId, reason }`. 성공한 simulation의 대상 버전·canonical definition hash가 현재 DRAFT와 일치해야 상신된다. `RA_MODEL` payload hash는 전체 정의를 고정하고 approve 시 재검산한다. 승인 실행 시 같은 tenant+scenario 기존 ACTIVE를 SUPERSEDED하고 새 버전을 ACTIVE로 원자 전환한다(ONBOARDING default도 이전). 작성자는 BFF 인증 principal에서 파생. 응답 `202 { approvalId, status: SUBMITTED, payloadHash }`. | `aml_risk_models`,`aml_ra_model_simulations`,`aml_approvals` |
| GET | `/api/v1/admin/aml/risk-scores?riskGrade=&modelVersion=&country=&reviewDueSoon=&targetRef=&scenario=&requiredAction=&registeredWithinDays=&latestPerTarget=&mandatoryHighRisk=&page=&size=` | `aml:case:read` | — | **RA 점수 목록**(모니터링). `riskGrade` 멀티(콤마 구분)·`modelVersion`·**`country`(국적 필터, 엔진이 실제 국가 차원 보유·#7; stub 경로는 `targetRef` seed 파생 결정적 국가 post-filter)**·`reviewDueSoon`(boolean — 재심사 임박)·`targetRef`(contains 검색)·페이지네이션 필터. **RA 목록 서버 필터 4종(2026-07-06, feature/aml-ra-list-filters-dedupe — 전부 optional·additive)**: ① `scenario`=`ONBOARDING`(1차)\|`ONGOING`(2차) — `aml_risk_models.scenario` 모델 레지스트리 exists-join(모델 코드 하드코딩 아님, 잘못된 값 400), 변경이력 9.31 의 "서버측 scenario 필터 후속 과제" 해소; ② `requiredAction`(권고 조치, 콤마 멀티 — `NONE`(조치 없음)·`CDD_UPDATE`(CDD 갱신)·`EDD`(강화된 고객확인)·`RELATIONSHIP_REVIEW`(관계 검토), `NONE` 토큰은 레거시 `required_action IS NULL` 행 포섭); ③ `registeredWithinDays`(양수 int — **인입(온보딩) 회원 필터**, `aml_customers.created_at ≥ now-일수` exists-join); ④ `latestPerTarget`(boolean 기본 false — **회원(targetRef)별 최신 1건 dedupe**, `evaluated_at` max 상관 서브쿼리[tenant·targetRef·modelVersion·scenario 한정] — **dedupe 먼저 선정 후 등급/조치/임박 등 상태 필터를 outer 적용**해 "현재 상태" 목록 의미론 보장, `count`/`items` 동일 술어). **⑤ `mandatoryHighRisk`(당연고위험, 2026-07-12 feature/aml-hrr-closed-loop-visualization — additive·optional 3-value): `true`=당연고위험만·`false`=일반만·미지정=무필터(modelVersion 회귀 교훈 동형). `aml_risk_scores.mandatory_high_risk` outer 필터(latestPerTarget 하 현재 상태 기준). bo-api 위임 경로는 이 서버 param 을 전달하면서 client post-filter(`matchesMandatoryHighRisk`)도 이중으로 걸어 구엔진(param 무시)도 안전하다(PEP 승인 fold 이후 최종 mandatory 플래그로 판정).** 응답은 **페이지 봉투 `RiskScoreListResponse{ items: RiskScoreResponse[], page, size, total }`**(§1.2 envelope 원칙 정합 — `total`은 페이지 무관 전체 건수로 타일↔목록 정합·페이지 이동에 사용) — `items` 원소가 `RiskScoreResponse`(§3.3, `mandatoryHighRisk`·`mandatoryHighRiskReasons`·`forcedFloorEvidence`·`operativeNextReviewDueAt` 포함). bo-api `GET /api/v1/bo/aml/risk-scores` 가 동일 파라미터(`mandatoryHighRisk` 포함)를 pass-through 위임하며, stub 경로도 동일 의미론(scenario=stub 행 시나리오 필터·requiredAction NULL 포섭·registeredWithinDays 는 seed 파생 결정적 가입일 post-filter·latestPerTarget 는 stub 이 target 당 1행이라 no-op·mandatoryHighRisk 는 `RiskScore.mandatoryHighRisk` post-filter) — 패리티 유지. **구현됨**(`RiskScoreAdminController`) | `aml_risk_scores`,`aml_risk_models`,`aml_customers` |
| GET | `/api/v1/admin/aml/risk-scores/distribution?modelVersion=` | `aml:case:read` | — | **RA 등급 분포**. 응답 `RiskDistributionResponse`(§3.3b). **구현됨**(`RiskScoreAdminController`) | `aml_risk_scores` |
| GET | `/api/v1/admin/aml/customers/pipeline-stats?histogramDays=` | `aml:case:read` | — | **CDD/RA 파이프라인 집계**(KYC 상태 분포·신규 등록 윈도우·RA 처리 현황·기간 히스토그램). `Tenant-Id` 헤더 필수·`Workspace-Id` 옵션. `histogramDays` 1~90·기본 14(범위 밖 클램프). 응답 `CddRaPipeline`(§3.3c). 집계 카운트만(raw PII 미노출). **구현됨**(엔진) | `aml_customers`,`aml_risk_scores` |
| POST | `/api/v1/admin/aml/risk-scores/{scoreId}/override` | `aml:case:update` | 🔒4-eyes(하향) | 등급 수동 조정. 요청 `RiskOverrideRequest`(§3.3) | `aml_risk_scores`,`aml_approvals` |

> **BFF 위임.** `GET /api/v1/bo/aml/ra-models/onboarding-input-catalog?windowDays=`가 위 엔진 응답을 1:1 위임한다. 동일 `aml:admin:policy` 권한이며 엔진 delegate가 없거나 빈 응답이면 관측값 stub을 합성하지 않고 `503 AML.ENGINE_UNAVAILABLE`로 fail-closed한다.

#### TM scenario (§12)
| 메서드 | 경로 | scope | 4-eyes | 설명 | DB |
|---|---|---|---|---|---|
| GET | `/api/v1/admin/aml/tm-scenarios` | `aml:admin:policy` | — | scenario 목록 | (정책 store) |
| POST | `/api/v1/admin/aml/tm-scenarios/{scenarioCode}/simulate` | `aml:admin:policy` | — | scenario simulation(응답 DTO §3.15 `SimulationResponse`) | — |
| POST | `/api/v1/admin/aml/tm-scenarios/{scenarioCode}:activate` | `aml:admin:policy` | 🔒4-eyes | scenario 변경 적용 | `aml_approvals` |

#### 사용자 정의 STR/CTR TM 룰 (v9.44)

| 메서드 | 경로 | scope | 4-eyes | 설명 |
|---|---|---|---|---|
| GET | `/api/v1/admin/aml/configurable-report-rules?family=STR\|CTR` | `aml:case:read` | — | 사용자 정의 룰 버전 목록(통계/BFF read) |
| POST | `/api/v1/admin/aml/configurable-report-rules` | `aml:admin:policy` | — | 안전 DSL 사용자 정의 룰 DRAFT 생성(201) |
| POST | `/api/v1/admin/aml/configurable-report-rules/{ruleCode}/simulate` | `aml:admin:policy` | — | 입력 sampleFeatures 결정적 시뮬레이션 |
| POST | `/api/v1/admin/aml/configurable-report-rules/{ruleCode}:activate` | `aml:admin:policy` | 🔒 `TM_SCENARIO` | DRAFT 버전 활성화 상신(202), subjectRef=`CUSTOM_RULE\|code\|version` |

`ConfigurableReportRuleView`: `{ ruleCode, version, family(STR|CTR), displayName, description, reasonCode(STR 필수/CTR null), severity, status(DRAFT|ACTIVE|SUPERSEDED), parameters, dsl, effectiveFrom, createdBy }`. `ruleCode`는 `[A-Z][A-Z0-9_]{2,79}`이며 잠금 기준선과 충돌하는 `STR_`/`CTR_` 접두는 금지한다. DSL은 `cmp`/`and`/`or`/`not`와 `velocity(count|sum, dimension=subject, window=1h..30d)`의 닫힌 문법이며 allowlist 밖 피처·`always`·빈 AND/OR 그룹은 400이다.

bo-api 표면: `GET|POST /api/v1/bo/aml/report-rules/configurable`, `POST .../configurable/{ruleCode}/simulate`, `POST .../configurable/{ruleCode}:activate`. GET은 `aml:case:read`, 변경은 `aml:admin:policy`로 분리한다. DRAFT 생성·활성화 상신의 `makerId`는 브라우저 입력을 신뢰하지 않고 인증된 `BackofficePrincipal.email`로 덮어쓴다. bo-web은 엔진을 직접 호출하지 않는다.

> bo-api의 `GET /api/v1/bo/aml/tm-scenarios/{scenarioCode}`는 운영자 화면용 BFF read model이다. 엔진 저장 권위는 위 Admin API의 정책 store이며, 변경 적용은 기존 `:activate` 4-eyes(`TM_SCENARIO`) 흐름만 사용한다.

#### Case / CDD·EDD (§13)
| 메서드 | 경로 | scope | 4-eyes | 설명 | DB |
|---|---|---|---|---|---|
| GET | `/api/v1/admin/aml/cdd/cases` | `aml:case:read` | — | case 목록(필터: caseType/status/assignedTo) | `aml_cases` |
| GET | `/api/v1/admin/aml/cdd/cases/{caseId}` | `aml:case:read` | — | case 상세·timeline | `aml_cases` |
| POST | `/api/v1/admin/aml/cdd/cases` | `aml:case:update` | — | case 생성. `originAlertId`가 없으면 수동 생성, 있으면 alert row를 먼저 잠그고 tenant/target/CTR·STR type/status를 검증한 정상 handoff로만 생성·상태 전이한다. 임의 case의 alert lineage 선점은 거부 | `aml_alerts`,`aml_cases` |
| PATCH | `/api/v1/admin/aml/cdd/cases/{caseId}` | `aml:case:update` | — | 담당자·우선순위·dueAt 및 working status `OPEN↔INVESTIGATING` 변경. `PENDING_APPROVAL` 진입/이탈과 terminal 전이는 직접 PATCH 불가 | `aml_cases` |
| POST | `/api/v1/admin/aml/cdd/cases/{caseId}/timeline` | `aml:case:update` | — | 메모·증빙 추가 | `aml_cases` |
| POST | `/api/v1/admin/aml/cdd/cases/{caseId}:close` | `aml:case:update` | 🔒4-eyes(`EDD_CLOSE`) | **조사 케이스 결재 종결**(`DISMISSED`/`REPORTED`/`CLOSED` 종결). subjectType=`EDD_CLOSE` 4-eyes(상신 maker→승인 checker, maker≠checker) 승인 시 종결. **케이스 유형 무관 — EDD_REVIEW(강화된 고객확인) 뿐 아니라 알림 트리아지·처분 폐루프에서 전환된 조사 케이스(STR_REVIEW·SAR_REVIEW·CDD)도 동일 결재 종결 경로를 공유**한다(엔진 `Case.closeApproved` 는 케이스 유형 가드 없이 존재·비종결 상태 불변식만 강제 — 과거 `EDD_REVIEW` 전용 가드가 STR_REVIEW `:close` 를 400 "case is not an EDD_REVIEW case" 로 거부하던 결함 해소). 회원원장 EDD 종료 이력(`recordEddClosed`, DB §3.22f)은 `EDD_REVIEW` 케이스에만 기록(알림 파생 조사 케이스는 EDD 이력 대상 아님) | `aml_cases`,`aml_approvals` |
| POST | `/api/v1/admin/aml/cdd/cases/{caseId}:reject-relationship` | `aml:case:update` | 🔒4-eyes | 관계거절/온보딩 보류 확정 | `aml_cases`,`aml_approvals` |

> **케이스 종결·알림 handoff 불변식(V43).** `:close`의 maker는 `X-User-Subject`가 정본이며 body maker는 동일성 assertion일 뿐이다. 상신 성공 즉시 case는 `PENDING_APPROVAL`, checker 승인 시 terminal status로 전이하고 reject 시 직전 조사상태로 복원한다. `REPORTED` 종결은 case type에 맞춰 `STR_REVIEW→STR`, `CTR_REVIEW→CTR`의 연결 보고가 `SUBMITTED` 또는 `ACKNOWLEDGED`일 때만 가능하다. submit과 checker 실행 모두 **case FOR UPDATE→report FOR UPDATE** 순으로 같은 lineage/target/status를 재검증하므로 FIU FAIL callback과 원자적으로 직렬화된다. 다른 case type의 REPORTED는 거부한다. 알림 전환 case는 서버가 알림 종류로 `STR_REVIEW`/`CTR_REVIEW`를 정하고 `(tenant_id,origin_alert_id)`당 하나만 생성한다. handoff 재호출은 alert의 terminal action·recommended type과 기존 case의 tenant/origin/target/type이 모두 같은 경우에만 멱등 replay로 반환하며, 다른 action이나 lineage 불일치는 충돌로 거부한다. 과거 `TRIAGED` alert에 유효한 기존 case만 남은 부분 handoff는 같은 transaction에서 요청 action으로 alert 상태를 동기화하되 case 재생성·재과금은 하지 않는다.

#### Regulatory Reporting (§14)
| 메서드 | 경로 | scope | 4-eyes | 설명 | DB |
|---|---|---|---|---|---|
| GET | `/api/v1/admin/aml/reports?reportType=&status=&caseId=` | `aml:case:read` + **`COMPLIANCE` role 필수(STR 필터 시)** | — | 보고 목록. `status` 미지정은 전 상태, `caseId`는 케이스 연결 보고만 필터한다. 응답은 `caseId`·`createdAt`·`reportDeadlineAt`을 포함하며 STR은 tipping-off 통제와 열람 감사를 적용한다 | `aml_regulatory_reports` |
| GET | `/api/v1/admin/aml/reports/{reportId}` | `aml:case:read` + **STR은 `COMPLIANCE` role 필수** | — | 엔진 저장 보고 상세. `caseId`·보고본문·승인/FIU 제출 계보를 반환하며 STR 비전담에는 존재 자체를 숨긴다 | `aml_regulatory_reports` |
| POST | `/api/v1/admin/aml/reports` | `aml:case:update` | — | 보고 초안 생성(DRAFT). `caseId` 지정 시 case를 tenant-scoped lock하고 `STR↔STR_REVIEW`/`CTR↔CTR_REVIEW`, 동일 targetRef, 비종결 상태, case/type당 기존 보고 부재를 검증하며 target은 case 원장에서 파생한다 | `aml_cases`,`aml_regulatory_reports` |
| POST | `/api/v1/admin/aml/reports/str-drafts` | `aml:case:update` + `COMPLIANCE` role | — | body `{caseId}`. `STR_REVIEW` 케이스와 같은 target/발단 transaction의 기존 STR DRAFT를 연결하거나 멱등 생성한다. 케이스당 STR 1건이며 타 케이스 연결·비-DRAFT 재연결은 거부 | `aml_cases`,`aml_regulatory_reports` |
| POST | `/api/v1/admin/aml/reports/{reportId}:submit` | `aml:case:update` | 🔒4-eyes(REPORTING_OFFICER) | report row를 잠근 뒤 DRAFT/SUBMISSION_FAILED→UNDER_REVIEW와 단일 approval을 원자 생성한다. checker reject 시 UNDER_REVIEW를 DRAFT로 복구해 수정·재상신 가능 | `aml_regulatory_reports`,`aml_approvals` |
| POST | `/api/v1/admin/aml/reports/{reportId}:reject` | `aml:case:update` | 🔒4-eyes(REPORTING_OFFICER) | 보고 기각(`REJECTED` 전이) — **사유 코드(`reasonCode`) 필수**, 자기승인 금지(설계서 §14.1a) | `aml_regulatory_reports`,`aml_approvals` |
| POST | `/api/v1/admin/aml/reports/{reportId}:cancel` | `aml:case:update` | 🔒4-eyes(REPORTING_OFFICER) | 보고 취소(`CANCELLED` 전이) — **사유 코드(`reasonCode`) 필수**, CTR 제외 처리(§14.3) 시 `ctrExemptionCode` 병기(설계서 §14.1a) | `aml_regulatory_reports`,`aml_approvals` |
| POST | `/api/v1/admin/aml/reports/{reportId}/callback` | `aml:report:callback`(**전용 최소권한 scope 신설, P0-11**) | — | **FIU 제출 회신 콜백**(규제기관/ProviderSvc→aml-svc). `SUBMITTED → ACKNOWLEDGED\|SUBMISSION_FAILED` 폐루프를 닫는다(설계서 §14.1a, integration §3.4). AML HMAC ingest 필터(`Tenant-Id`+`X-Api-Key`+`X-Timestamp` ±5m+`X-Signature`, fail-closed) + 전용 scope `aml:report:callback` 로 인가. body `FiuCallbackRequest{ status(ACKNOWLEDGED\|REJECTED), submittedRef, messageId, fiuAckRef, errorCode }` 는 durable 제출 job 과 **이중 대사**(`reportId↔submittedRef`(∨`fiuAckRef`) + 제출 job `provider_message_id` 일치) — 불일치/미존재 job = spoof/stale 로 거부(silent no-op 아님). 멱등: 이미 terminal 인 report 는 안전한 `200` no-op(중복·지연 회신 무오류). replay 는 HMAC nonce(v2) + `submittedRef` 멱등 + `SUBMITTED` 상태가드로 이중 봉쇄 | `aml_regulatory_reports`,`aml_report_submission_jobs` |
| GET | `/api/v1/admin/aml/reports/stats/str-delay?period=7d\|30d\|90d` | `aml:case:read` + **`COMPLIANCE` role 필수** | — | STR 보고 지연일수 분포 집계 원천(PRD §12-B.3 ①). 보고별 candidate(`created_at`)→제출(`submitted_at`) 경과를 법정 SLA(§14.4 BR-006) 대비 상대 버킷 `{ON_TIME,D+1~3,D+4~7,D+8~14,D+15+}`으로 분류. **tipping-off 통제(§19.2a)**: COMPLIANCE 전담 role 필수(없으면 `403 AML.FORBIDDEN_SCOPE`), 열람은 `RAW_DATA_ACCESS` 감사. 응답은 집계 카운트만(보고 행·PII 미노출). 0건 → 빈 분포(honest, seed 없음). 응답 DTO §3.6 `DelayBucket[]` (T4 AML-ENG-04 — **확정**) | `aml_regulatory_reports` |
| GET | `/api/v1/admin/aml/reports/stats/unreported-reasons?period=7d\|30d\|90d` | `aml:case:read` + **`COMPLIANCE` role 필수** | — | STR 미보고(종결 비제출=`REJECTED`/`CANCELLED`) 사유 분포 집계 원천(PRD §12-B.3 ①). 종결 시 영속된 `closure_reason_code` 빈도(미영속 legacy = `UNSPECIFIED` 버킷, 소급 seed 없음). **tipping-off 통제(§19.2a)**: COMPLIANCE 전담 role 필수, `RAW_DATA_ACCESS` 감사. 응답 DTO §3.6 `UnreportedReason[]` (T4 AML-ENG-04 — **확정**) | `aml_regulatory_reports` |

> **STR actor 신뢰경계(P0-00 코드 truth).** bo-api가 사용자 principal에서 파생한 `X-User-Subject`는 machine-auth v2 `scopeContext.user-subject`에 포함된다. STR 목록/상세/통계의 `RAW_DATA_ACCESS` 감사 actor와 draft/submit/reject/cancel maker는 이 signed header를 사용하고, body의 `makerId`가 있으면 동일성 assertion만 수행한다. bo-api machine credential 자체도 `COMPLIANCE` authority token을 가져야 하며, BO edge의 사용자 `AML_COMPLIANCE` 검사와 엔진 `RoleGuard`/`ScopeGuard`를 모두 통과해야 한다.

#### CTR/STR 룰·임계 관리 (§14 — bo-api 관리 콘솔, CTR/STR 모니터링 통합 P4)
> **read overview(`GET /api/v1/bo/aml/stats/report-rules`, §3.6a)와 별개**: 아래는 **룰 활성화 파이프라인·규제 임계 4-eyes 변경**을 담당하는 관리 엔드포인트다(통계 개요는 집계 read-only, 여기는 상태 전이·정책 변경). 실제 구현: `AmlReportRuleController`·`AmlCtrThresholdController`(bo-api).

| 메서드 | 경로 | scope | 4-eyes | 설명 | DB |
|---|---|---|---|---|---|
| GET | `/api/v1/bo/aml/report-rules` | `aml:admin:policy` | — | CTR/STR 룰 카탈로그 목록(`AmlReportRuleCatalog` 10종, `status` ACTIVE/DRAFT — EXECUTED 활성화 반영). 응답 `ReportRuleView[]` | (코드 카탈로그) |
| GET | `/api/v1/bo/aml/report-rules/{ruleCode}` | `aml:admin:policy` | — | 룰 상세(자연어 설명·evaluationMode·actions·reasonCode + **`conditions[]` 발동 조건 행·`params[]` 편집 파라미터 행(resolved 현재값·카탈로그 기본값·min/max·editable)·`pendingParamApprovalId`**) | (코드 카탈로그 + `aml_report_rule_params` 오버라이드) |
| POST | `/api/v1/bo/aml/report-rules/{ruleCode}:activate` | `aml:admin:policy` | 🔒4-eyes(`REPORT_RULE`) | 룰 활성화 DRAFT→ACTIVE(202 + approvalId, **시뮬레이션 요약 동반**). `STR_MANUAL`은 컴플라이언스 수동 전용 → 파이프라인 활성화 거부(`400`, "rule is manual-only and cannot be activated") | `aml_approvals`(bo-api 스텁 4-eyes) |
| POST | `/api/v1/bo/aml/report-rules/{ruleCode}:update-params` | `aml:admin:policy` | 🔒4-eyes(`REPORT_RULE_PARAM`, 승인선 `COMPLIANCE_MANAGER`) | 인증 principal maker로 aml-svc에 상신 자체를 위임하고 엔진의 실제 approvalId를 반환한다. 전체 editable set·AS-IS/TO-BE를 고정하며 checker EXECUTED 전에는 effective 값이 바뀌지 않는다. 스키마/범위/교차검증·maker 위조·self-approval·pending 중복을 차단 | `aml_approvals`,`aml_report_rule_params`(aml-svc V22/V41) |
| GET | `/api/v1/bo/aml/ctr-thresholds` | `aml:admin:policy` | — | 통화별 CTR 규제 임계 목록(EXECUTED 반영값 우선·변경 대기 표기). 응답 `CtrThresholdView[]`(§3.22a) | `aml_ctr_thresholds` |
| GET | `/api/v1/bo/aml/ctr-thresholds/{currency}` | `aml:admin:policy` | — | 통화별 CTR 임계 상세 | `aml_ctr_thresholds` |
| POST | `/api/v1/bo/aml/ctr-thresholds/{currency}:update` | `aml:admin:policy` | 🔒4-eyes(`CTR_THRESHOLD`, 승인선 `REPORTING_OFFICER`) | CTR 규제 임계 변경(202 + approvalId). 엔진 연결 시 bo-api가 aml-svc admin `POST /api/v1/admin/aml/ctr-thresholds/{currency}:update`로 상신을 위임해 AML 결재함에 노출한다. **규제값 hot-reload 우회 불가** — 결재 EXECUTED 시에만 반영(BR-501) | `aml_ctr_thresholds`,`aml_approvals`(aml-svc V23 / 비운영 stub fallback) |

엔진 위임 계약은 `GET /api/v1/admin/aml/report-rules/{ruleCode}/params` → `{ruleCode,params,pendingApprovalId}`와 `POST /api/v1/admin/aml/report-rules/{ruleCode}:update-params`(header `X-User-Subject`, body `{makerId,reason,params}`) → `202 {ruleCode,staged,approvalId,status:"SUBMITTED",subjectType:"REPORT_RULE_PARAM"}`다. body `makerId`는 인증 주체와 일치해야 한다.

> 4-eyes `CTR_THRESHOLD`와 `REPORT_RULE_PARAM`은 모두 **aml-svc 엔진 결재 대상**이다. report-rule BFF는 인증 principal에서 maker를 파생해 엔진 `POST /api/v1/admin/aml/report-rules/{ruleCode}:update-params`로 상신 자체를 위임하고 실제 approvalId를 그대로 노출한다. 엔진은 전체 editable set과 AS-IS/TO-BE staged payload/hash를 고정하며 common approval checker가 EXECUTED로 전환할 때만 `aml_report_rule_params`를 원자 upsert한다. `GET /api/v1/admin/aml/report-rules/{ruleCode}/params`는 effective params와 `pendingApprovalId`를 반환한다. 비운영 엔진 미연결에서만 기존 bo-api stub 폐루프를 허용하고 운영은 fail-closed 한다. `REPORT_RULE` 룰 활성화는 bo-api 애플리케이션 승인 경계를 유지한다.

> **bo-api AML-STAT 집계 BFF**: BO 화면은 엔진 admin 원천을 직접 호출하지 않고 `GET /api/v1/bo/aml/stats/str`(STR 일별 보고 추이 + 기존 퍼널/지연/미보고 집계, COMPLIANCE 전담), `GET /api/v1/bo/aml/stats/ctr`(CTR 일별 보고 추이 + 기존 퍼널, STR 통계와 동일 DTO 규격), `GET /api/v1/bo/aml/stats/scenarios`(TM 룰 효과성), `GET /api/v1/bo/aml/stats/report-rules?family=CTR|STR`(룰군별 룰 개요 — CTR·룰 효과성 통계 메뉴는 `family=CTR`(CTR 룰 개요 CTR_SINGLE·CTR_DAILY), STR·룰 효과성 통계 메뉴는 `family=STR`(STR 룰 개요 8종). `family=STR`은 STR 퍼널과 동일한 tipping-off 전담(COMPLIANCE) 게이트 — 비전담 `403 AML.FORBIDDEN_SCOPE`, CTR은 열림. `hitCount30d`/`draftCount`는 라이브 CTR/STR DRAFT store(비운영 stub 폴백) `firedRules` 위 실집계·소스 없으면 0(seed 없음), `status`는 EXECUTED 활성화 반영 ACTIVE/DRAFT)을 호출한다. 네 endpoint는 bo-api 소유 read aggregate(API §9 경계)이며 응답은 집계 카운트만 포함한다. 응답 DTO §3.6/§3.6a `ReportDailyCount`·`ReportRuleOverviewRow`.

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
| POST | `/api/v1/admin/aml/high-risk-registry/registrations` | `aml:admin:high-risk-registry` | 🔒4-eyes(`HRR_REGISTRATION`, 승인선 `EXECUTIVE_APPROVAL`) | RA 당연고위험 회원 등재 상신(RA 상세 배선·`customerRef` 토큰·`tier` 기본 HIGH). body `{customerRef, tier?, makerId, reason?}`. **신규 상신 = `202 {approvalId, customerRef, subjectType:HRR_REGISTRATION, approvalLine:EXECUTIVE_APPROVAL, status:SUBMITTED}`**. **멱등 no-op(이미 등재 EXECUTED / 상신 대기 PENDING) = `200 {approvalId:null, status:NOOP}`** — 재평가 루프 종료 불변식(A6), 오류 아님. 승인 EXECUTED 시 `RA_HIGH_RISK_CUSTOMERS` 등재 + RA 강제 상향 | `aml_high_risk_registry_items`,`aml_approvals` |
| GET | `/api/v1/admin/aml/high-risk-registry/registrations/{customerRef}` | `aml:admin:high-risk-registry` | — | 당연고위험 등재 상태(미상신/PENDING/EXECUTED) read-back. 응답 `{customerRef, registered, pending, pendingApprovalId}` — RA 상세 등재 결재 상태 패널, no-op 세분(`registered` vs `pending`) 판별 | `aml_high_risk_registry_items`,`aml_approvals` |

> **위임 경로 멱등 no-op 계약(코드=truth, fix-20260707).** bo-api `AmlHighRiskRegistryService.submitRegistration`(`POST /api/v1/bo/aml/**` 위임)는 엔진 등재 응답의 **`status=NOOP`(200·`approvalId=null`)을 정상 멱등 no-op 으로 매핑**(502 로 변환하지 않음) — stub fallback 경로(등재됨/대기중 no-op 가드)와 계약 대칭. **`status` 부재 + `approvalId=null` 인 진짜 프록시 오류만 `502 BAD_GATEWAY`(`AML-PROXY-ERROR`) 유지**. **가정 A(§미정의)**: 엔진 등재 응답은 `alreadyRegistered` vs `pending` 세분 플래그를 no-op 응답에 담지 않으므로, bo-api 는 no-op 직후 `GET .../registrations/{customerRef}` read-back(`RegistrationStateResponse.registered`/`pending`)으로 세분을 판별해 `HrrRegistrationResponse.alreadyRegistered`/`pending` 를 채운다(엔진이 세분 플래그를 응답에 추가하면 read-back 제거). read-back 실패 시 보수적 `pending=true` 폴백(no-op 자체는 200 유지). §10 등재표 `HRR_REGISTRATION` 행 참조.

> **bo-api 공개 등재 상태 read-back 위임(코드=truth, 2026-07-12 feature/aml-hrr-closed-loop-visualization).** 위 엔진 `GET .../registrations/{customerRef}`(engine admin, scope `aml:admin:high-risk-registry`)를 **bo-api 가 공개 read-back 엔드포인트 `GET /api/v1/bo/aml/high-risk-registry/registrations/{customerRef}`(scope `aml:case:read` — 순수 조회)로 위임 노출**한다. RA 상세(AML-RA-003, PRD §12-A.4 BR-006) 당연고위험 폐루프 흐름도가 회원별 현재 단계(②자동상신→③경영진 승인 대기/확정→④등재)를 바인딩하는 데 쓰이며, 응답 `HrrRegistrationState{customerRef, registered, pending, pendingApprovalId, tier, submittedAt, registeredAt}`(위임 경로는 엔진 `registered`/`pending`/`pendingApprovalId` 매핑·`tier`/시각은 null / 비운영 stub 경로는 `AmlStubStore` staged/executed HRR fold 로 `tier`·시각 파생·운영 프로파일 fail-closed `503 AML.ENGINE_UNAVAILABLE`). PII 미포함(토큰 `customerRef`·플래그·시각만). 승인/반려 액션은 별도 신설 없이 공통 결재함 `:approve`/`:reject`(scope `aml:admin:approval`)가 `HRR_REGISTRATION` 을 동일 라우팅(§8·§10) — RA 상세 흐름도가 `pendingApprovalId` 로 결선한다. 흐름도 5단계 도출은 bo-web 순수 함수(`lib/aml-hrr-flow.ts deriveHrrFlow`)로 read-back·최신 결재·`mandatoryHighRisk` 입력만으로 스테퍼 상태를 매핑한다(엔진 계약 변경 없음).

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
| GET | `/api/v1/admin/aml/country-risk` | `aml:admin:policy` | — | 국가위험 등급표 조회(ISO 국가별 risk band·근거·출처(provenance)). `countryCode` 생략 시 유효(ACTIVE) 전체 표 | `aml_country_risk` |
| GET | `/api/v1/admin/aml/country-risk/import-status` | `aml:admin:policy` | — | **국가위험 일일 수집 상태**(소스 메타 + 최근 run diff 10건, §3.12 `CountryRiskImportStatusDto`) — 활성 제공자(EU_COMMISSION 기본/FATF 대안) 병기 | `aml_country_risk_sources`,`aml_country_risk_import_runs` |
| POST | `/api/v1/admin/aml/country-risk:import` | `aml:admin:policy` | — (시스템 provenance 자동 적용 — 결재 없음) | **국가위험 즉시 수집(수동 트리거)** — 동기 실행, 응답 §3.12 `CountryRiskImportResultDto`(SyncResult) | `aml_country_risk`(+`aml_country_risk_sources`,`aml_country_risk_import_runs`) |
| POST | `/api/v1/admin/aml/country-risk:change` | `aml:admin:policy` | 🔒4-eyes(subjectType=`COUNTRY_RISK`) | 국가위험 변경 상신(§13.4 'country risk 변경') | `aml_approvals` |
| POST | `/api/v1/admin/aml/policy-packs:change` | `aml:admin:policy` | 🔒4-eyes(subjectType=`POLICY_PACK`) | tenant policy pack 변경 상신(STR/CTR 기준금액·effective version, 설계서 §14.3·§19.1) | `aml_approvals`(+`aml_tenants.policy_pack_code`) |

> `country-risk:change`·`policy-packs:change`는 결재 상신 진입점이다. 상신 시 §3.7 `subjectType=COUNTRY_RISK`/`POLICY_PACK` 결재가 생성되며(`202 + approvalId`), 승인(checker) 후 실행(EXECUTED) 시점에 정책 store(국가위험 등급표 / `aml_tenants.policy_pack_code` effective version)에 반영된다. policy pack 기준금액(CTR 고액현금거래·STR)은 법령·감독규정 변경 가능성이 있어 effective version으로 관리한다(설계서 §14.3). **활성화(EXECUTED)는 같은 트랜잭션에서 테넌트의 P0-16 pin(`aml_tenants.policy_pack_version`)을 새 ACTIVE revision 으로 자동 전진시킨다**(`pack_code` 일치 + 기존 pin NOT NULL 테넌트 한정 — 미바인딩 테넌트는 불변으로 fail-closed 유지, 감사 detail `tenantPinAdvanced`). 전진이 없으면 pin 이 SUPERSEDED revision 에 남아 이후 중립 인입 전체가 `422 AML.TENANT_POLICY_UNBOUND` 로 차단된다(§4).
>
> **국가위험 일일 자동 수집(country-risk-daily-import, DB §3.22c·V16·V18)**: 일일 스케줄러(`CountryRiskImportScheduler`, cron 기본 `0 40 3 * * *`·`aml.country-risk.import.enabled` 기본 false·single-flight)와 수동 트리거(`:import`)가 동일 유스케이스(`SyncCountryRiskUseCase.sync`)를 실행한다. **수집 소스는 제공자 선택형(`aml.country-risk.feed.provider`) — 기본 `EU_COMMISSION`(EU 집행위 고위험 제3국 페이지, 봇 차단 없음), 대안 `FATF`(black/grey 페이지; 현재 HTTP 403 Akamai 봇 차단으로 수집 불가라 대안으로 강등)**:
> - **EU_COMMISSION(기본)** — 단일 고위험 목록 → 전부 `HIGH`(basis `EU_HIGH_RISK_THIRD_COUNTRY`), provenance `EU_COMMISSION`, 결정적 국가명→ISO-2 매핑 26개국(`EuHighRiskCountryIso`, 미래 신규 미매핑 시 skip+run diff `unmapped` 기록), canonical `eu-<hash12>`.
> - **FATF(대안)** — black(Call for Action)→`PROHIBITED`/grey(Increased Monitoring)→`HIGH`(`FatfGradeMapping`), provenance `FATF_DAILY`, canonical `fatf-<hash12>`.
>
> 활성 제공자별 결정적 매핑으로 **시스템 provenance ACTIVE 버전을 결재 없이 즉시 적용**하고 run diff 를 감사 기록한다(자동 수집은 4-eyes 대상 아님 — 수동 조정만 `:change` 🔒). 동일 버전 재수집 = `SKIPPED_UNCHANGED` no-op(버전 증식 없음), 실패 = fail-safe(기존 등급 유지·`FAILED` 기록). **MANUAL(4-eyes) ACTIVE 등급 우선 — 자동 수집이 덮지 않고 `suppressedManual` 로 기록**. 이탈(delist)은 동일 제공자 provenance ACTIVE 만 supersede(제공자 전환이 타 provenance 보존). bo-api 위임: `GET /api/v1/bo/aml/country-risk/import-status`·`POST /api/v1/bo/aml/country-risk:import`(수동 트리거는 감사 이벤트 `COUNTRY_RISK_IMPORT_TRIGGERED` 기록, bo V8).

#### 결재(공통)·감사·source (§13.5·§19.3·§16)
| 메서드 | 경로 | scope | 4-eyes | 설명 | DB |
|---|---|---|---|---|---|
| GET | `/api/v1/admin/aml/approvals?status=&subjectType=` | `aml:admin:approval` | — | 공통 결재 목록. **`status` 미지정 = 전 상태 수렴**(SUBMITTED·APPROVED·EXECUTED·REJECTED… — 결재함 "처리됨" 탭·승인 이력·HRR 흐름도 read surface), 대기 큐는 `?status=SUBMITTED` 명시. **`subjectType` 미지정 = 전 subject**(신규 필터, `?subjectType=HRR_REGISTRATION` 등 §3.7 값). 잘못된 `status`/`subjectType` enum → 400. **과거 기본 SUBMITTED 계약(미지정=대기만) 제거**(EXECUTED/REJECTED 미노출 결함, 아래 note) | `aml_approvals` |
| GET | `/api/v1/admin/aml/approvals/{approvalId}` | `aml:admin:approval` | — | 결재 상세 | `aml_approvals` |
| POST | `/api/v1/admin/aml/approvals/{approvalId}:approve` | `aml:admin:approval` | — | 승인(checker=trusted `X-User-Subject`, maker≠checker 강제; body 명의 주입 거부) | `aml_approvals` |
| POST | `/api/v1/admin/aml/approvals/{approvalId}:reject` | `aml:admin:approval` | — | 반려(checker=trusted `X-User-Subject`; body 명의 주입 거부) | `aml_approvals` |

> **결재 목록 필터 계약(코드=truth, 2026-07-12 feature/aml-hrr-closed-loop-visualization).** 엔진 `GET /api/v1/admin/aml/approvals`(`ApprovalController#queue`)의 `status` 파라미터는 **기본값 SUBMITTED 를 제거**했다 — 미지정 시 전 상태(SUBMITTED/APPROVED/EXECUTED/REJECTED/…)를 수렴 조회한다. 과거 기본 SUBMITTED 는 결재함 "처리됨" 탭·승인 이력·HRR 폐루프 흐름도(PRD §12-A.4 BR-006)가 EXECUTED/REJECTED 를 read 하지 못하던 결함이었다. **대기 큐는 `?status=SUBMITTED` 명시**로 동작(기존 대기 큐 호출부 무변경). 신규 **`subjectType` 필터**(미지정=전 subject, `?subjectType=HRR_REGISTRATION`/`HIGH_RISK_REGISTRY`/… §3.7 값)로 subject 축 좁힘도 서버에서 지원한다(HRR 흐름도·승인 히스토리 탭이 subjectType 로 좁혀 조회). **bo-api `GET /api/v1/bo/aml/approvals?status=&subjectType=` 위임도 동일 의미론** — stub 경로의 `status=null`/`subjectType=null`=무필터와 수렴(위임↔stub parity). 잘못된 `status`/`subjectType` 값은 `ApprovalStatus`/`ApprovalSubjectType.valueOf` 예외 → 400(무필터로 삼키지 않음).
| GET | `/api/v1/admin/aml/source-systems` | `aml:admin:source-system` | — | source 목록 | `aml_source_systems` |
| POST | `/api/v1/admin/aml/source-systems` | `aml:admin:source-system` | 🔒4-eyes(secret 변경) | source 등록·secret 변경 | `aml_source_systems`,`aml_approvals` |
| GET | `/api/v1/admin/aml/audit-events?eventCategory&from&to&actor&subjectRef&traceId&page&size` | `aml:admin:audit` | — | tenant-scoped append-only 감사 조회. `eventCategory` 허용값(DB §3.15 enum 11종): `WATCHLIST_IMPORT`/`WLF_DECISION`/`FP_WHITELIST`/`RA_MODEL_CHANGE`/`RA_REVIEW`/`RISK_OVERRIDE`/`TM_SCENARIO_CHANGE`/`CASE_APPROVAL`/`REPORT_LIFECYCLE`/`RAW_DATA_ACCESS`/`POLICY_CHANGE`. `actor`는 exact가 아니라 부분검색(`LIKE %value%`), `traceId`는 최대 128자 exact equality다. 응답 `{content,totalElements}`의 exact filtered total, `createdAt DESC, auditId DESC`; normalized `trace_id` 우선·legacy `detail.traceId` fallback | `aml_audit_events` |

> **BO AML 통합 감사(P0-03)**: `GET /api/v1/bo/aml/audit`는 BO exact event 필터 `event`와 engine enum 필터 `eventCategory`를 별도 query로 받는다. `event`를 engine category로 재해석하지 않고 `eventCategory`를 BO event code로 적용하지 않는다. `actor`는 BO/engine 모두 부분검색이고 `traceId`/`subjectId`/`from`/`to`/`page`/`size`는 두 source에 전달한다. bo-api는 BO scoped total + engine `totalElements`를 합산하고 필요한 source page를 수집한 뒤 `occurredAt DESC, sourceService ASC, local id DESC, auditId DESC`로 안정 merge한다. merge를 위해 수집하는 `offset+size`는 최대 10,000행이며 이를 넘으면 400으로 필터/기간 축소를 요구한다. AML engine은 물리 workspace를 갖지 않으므로 unified projection의 engine provenance는 요청 BO tenant + `workspaceId=default`다.

> **configured delegate response integrity(P0-03)**: bo-api의 typed AML 위임은 HTTP 2xx라도 body가 없으면 `502 BO-PROXY-FAILED`로 거부한다. bodyless 성공은 계약이 명시된 `:approve`/`:reject` 등의 별도 204/Void 경로에서만 허용한다. 감사 `{content,totalElements}`는 `content` 누락, 음수/불일치 total, 필수 row(`auditId/eventCategory/actor/detail/createdAt`) 누락을 전체 502로 거부하며, 정상 빈 결과는 `{content:[],totalElements:0}`만 허용한다. 각 engine batch와 이전 page tail→다음 page head는 §2.7 canonical `createdAt DESC, auditId DESC` 순서에 단조여야 하며 out-of-order 2xx는 전체 502다. unified audit은 engine window를 먼저 읽고 local window를 뒤에 읽으며, engine audit list/detail projection 자체는 `PROXY_AML_CALL`을 append하지 않아 반복 offset 조회가 자기 데이터셋을 shift하지 않는다. 일반 AML proxy 호출 감사는 유지한다.
>
> admin 감사 write는 명시적으로 전달된 causal trace를 먼저 사용하고, 값이 없을 때만 request MDC `traceId`를 `aml_audit_events.trace_id`에 기록한다. V46은 **이 감사 컬럼만** `VARCHAR(128)`로 넓힌다. canonical ingest와 `aml_canonical_events`·`aml_member_cdd_history` 등 나머지 lineage의 64자/422 계약은 변경하지 않는다.
>
> typed AML local projection은 명시적 AML event prefix/allowlist만 포함한다(`AML_`/`PROXY_AML_`/WLF·SCREENING·WATCHLIST·RA·TM·CASE·REPORT·CTR·IRA·HRR 등과 열거된 AML 단건 event). FDS projection도 `FDS_`/`PROXY_FDS_`/`NOTIFY_CHANNEL_CHANGE`만 포함한다. `IAM`/`ROLE`/`SECURITY` 또는 unknown BO event를 “not FDS” 같은 보수집합으로 AML에 편입하지 않는다. 이 횡단/미분류 행은 `BO_SUPER_ADMIN` 전용 generic `/api/v1/bo/audit[/{id}]`에서만 조회한다.

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
| `eventType` | enum | R | `<family>.<verb>` 형식. **hanpass-ph eventType taxonomy(`EventFamily` enum 정본)**: 신원 = `customer.*`/`entity.*`/`beneficial-owner.*`(member-svc), 거래(transaction-bearing) = `transaction.*` + hanpass-ph 결제 5유형 `remit.transfer.requested`(해외송금)·`domestic.transfer.requested`(국내이체)·`wallet.charge.requested`(충전)·`wallet.pay.requested`(결제)·`wallet.withdraw.requested`(출금). 내부 생성/위임 = `case.*`/`aml.*`(외부 ingest 불가, `isExternallyIngestable()=false`). **참고**: `EventFamily` enum에는 폐쇄 strict-gate allow-list로 `crypto`/`trade`/`invoice`/`settlement`/`order`/`seller`/`market`/`vendor` family가 잔존하나, 이는 내부 리플레이가 strict 게이트에서 거부되지 않도록 하는 fail-safe이며 **hanpass-ph 외부 ingest 표면에서는 사용하지 않는다**(거래는 `remit`/`domestic`/`wallet`/`transaction` family로만 인입). |
| `occurredAt` | string(date-time) | R | ISO-8601 |
| `payload` | object | R | 정규화 payload. PII는 `*Ref`/`*Hash`만. raw 금지. **연동 키(원문 금지·keyed HMAC)**: `customer.customerRef`←`member.member_id`, `transaction.transactionRef`←`walletchg.charge_order_id`/`domestic.transaction_id`/`remit.transfer_number`/`*.wallet_transaction_id`, cross-border 거래는 `transaction.corridor`(send/receive country·currency←remit) + `transaction.amountBase`(USD←remit usd_amount/report_amount). **주의**: domestic-svc `member_id` varchar(36) join 정규화 |
| `payloadHash` | string | — | raw payload sha256(`stored=false`). DB `payload_hash` NOT NULL. **미제공 시 aml-svc ingest 어댑터가 수신 payload의 sha256을 자동 계산하여 INSERT**(서버 자동계산 방식 확정, DB §3.15 결정 주석 2026-06-08). 호출자가 직접 계산해 제공해도 무방(서버 값 우선). |

canonical varchar 경계는 DB §3.15와 동일하게 ingest 전에 검증한다: tenantId 64, eventId/idempotencyKey 256, sourceSystem 64, schemaVersion/eventType 80, payloadHash 128, dataScope/X-Trace-Id 64자. 초과 입력은 `REJECTED`(HTTP 422)이며 DB DataException/500으로 누출하지 않는다.

응답 `IngestEventResponse`: `{ eventId, accepted, idempotent, traceId, decision?, scoreId?, riskScore?, riskGrade?, requiredAction?, modelVersion?, reason? }`. CDD 외 이벤트는 decision 계열이 null이고, `customer.cdd.completed` ACCEPTED/REPLAYED는 V42 불변 온보딩 decision snapshot을 반환한다.

> **데모 회원 등록 인입 이벤트·`senderHolderName`(비-prod, 데이터 정직화 v9.27, 기능정의서 §1.11 BR-DEMO-HONESTY).** 데모(비-prod stub)는 회원 identity·신고소득의 유일 원천을 **회원 등록 인입 이벤트**로 받는다 — 테스트 인입 페이로드 `{eventType:"member", member:{memberRef, name, nationality, gender, dob, declaredIncomePhp}}` 가 인메모리 member vault(상한·eviction·전송값=열람값 reveal)에 upsert 되며, 미등록 회원의 거래 인입은 identity 의존 판정(명단 매칭·소득 룰)을 skip 한다. 거래 payload 에는 **`senderHolderName`**(nullable, 송금 명의인 이름 — `STR_THIRD_PARTY` 실데이터 신호: 회원 실명과 매처상 불일치 시 발동)이 가산된다. 데모 시드/hash 파생 회원 프로필은 폐기됐다. **비-prod 전용**(prod 프로파일 미노출). raw PII 는 vault reveal(감사 게이트) 로만.

### 3.2 ScreenRequest → `POST /api/v1/aml/screen` (DB `aml_screening_results`, `ScreeningController.ScreenRequest`)

**code truth: 평면(flat) 구조** — 중첩 `subject` 객체·`sourceTypes` 필드 없음. `Idempotency-Key` 헤더 필수. 매칭 입력 원문은 일시 처리 후 미저장(§19.2), 저장은 hash/token만.

| 필드 | 타입 | R | 검증/설명 |
|---|---|---|---|
| `targetRef` | string | R | 대상 ref(토큰). **hanpass-ph**: sender=송금 회원 member UUID keyed token(`CUSTOMER`), receiver=수취인 키(이름+국가+전화)의 keyed token(`COUNTERPARTY`) |
| `targetType` | enum | R | DB §5.23 target_type: `CUSTOMER`/`ENTITY`/`COUNTERPARTY`/`CRYPTO_ADDRESS`. hanpass-ph 송금은 sender=`CUSTOMER`, receiver=`COUNTERPARTY` |
| `nameHash` | string | — | 정규화 이름 HMAC |
| `nameTokens` | array<string> | — | 정규화 이름 토큰(원문 대신 권장) |
| `dob` | string(date) | — | 매칭용. 저장은 hash |
| `country` | string | — | ISO 국가(수취인 receiver 키 구성요소) |
| `documentHash` | string | — | 문서번호 HMAC |
| `walletAddressHash` | string | — | 지갑주소 HMAC(`CRYPTO_ADDRESS` — hanpass-ph 외부 ingest 미사용, enum 보존) |
| `addressTokens` | array<string> | — | 주소 정규화 토큰 |
| `relationshipRefs` | array<string> | — | 관계 ref(공유 계좌·반복 수취인 등) |
| `transactionRef` | string | — | **해외송금 거래번호 keyed token**. 동일 거래의 sender·receiver screening을 묶는 키(§13). receiver 키 자체가 (이름+국가+전화)이므로 동일 수취인은 거래간 누적·FP 화이트리스트 재사용된다 |

응답 `ScreeningResponse` (DB `aml_screening_results`, `ScreeningController.ScreeningResponse` 정본):

| 필드 | 타입 | 설명 |
|---|---|---|
| `screeningId` | string(uuid) | `screening_id` |
| `tenantId` | string | 테넌트(= `tenant_demo` hanpass-ph) |
| `targetRef` | string | 대상 ref(DB `target_ref`, 마스킹 토큰). sender=member token / receiver=이름+국가+전화 token |
| `transactionRef` | string | 동일 거래의 sender·receiver를 묶는 해외송금 거래번호 token(nullable, §13). TM 수취인 명단 평가(§3.4a BR-013)가 이 그룹으로 COUNTERPARTY 스크리닝을 조회 |
| `targetType` | enum | DB §5.23 target_type(`CUSTOMER`/`ENTITY`/`COUNTERPARTY`/`CRYPTO_ADDRESS`) |
| `status` | enum | §5.5 screening_status(`NO_MATCH`/`POSSIBLE_MATCH`/`TRUE_MATCH`/`FALSE_POSITIVE`/`AUTO_DISCOUNTED`/`ESCALATED`). **API 별칭 `POTENTIAL_MATCH`는 `POSSIBLE_MATCH`로 정규화** |
| `score` | number | 유사도 |
| `scoreBreakdown` | object | name/dob/country/document/address/relationship/negative 분해(§10.3). **가중 분모 = 해당 결과에 스냅샷된 ACTIVE profile의 6개 weight 합**이며 overall=`max(0, Σ(weight·score)/sumOfWeights() - negativePenalty×negativeSignal)`이다. 미제공 컴포넌트는 분자 기여 0·분모 유지한다. 주소는 요청 `addressTokens`와 엔트리 attributes 주소 토큰이 모두 있을 때만, negative signal은 결정적 불일치 근거가 있을 때만 적용한다. 과거 결과는 이후 정책 변경에도 이 스냅샷 의미가 변하지 않는다. **후보 recall 재현 스냅샷(P0-05·V49)**: `scoreBreakdown.candidateStrategy` object 에 후보 생성 4전략(S1 exact primary_name_hash∪S2 normalized_tokens 교집합∪S3 pg_trgm word_similarity∪S4 double-metaphone 교집합) 진단을 영속한다 — `{ candidateStrategyVersion(`wlf-cand-v1`), matcherVersion(=`appliedPolicy.definitionHash`), trgmFloor(기본 0.30), candidateCap(기본 200), phoneticEnabled(기본 true), candidateCapHit(상한 도달 여부·true 면 log.warn+증거로 silent truncation 방지), candidateCount(최종 후보수), strategyCounts(전략별 후보수 map) }`. 정밀도는 후단 FuzzyMatchEngine 이 책임하고 이 스냅샷은 recall 재현·튜닝 근거다 |
| `riskGrade` | enum | §5.2(평가 가능 시) |
| `reasonCodes` | array<string> | `reason_codes` (예: `NAME_EXACT_MATCH`,`SANCTIONS_NAME_SIMILARITY`,`DOB_MATCH`,`COUNTRY_MATCH`). 이름 유사 코드는 명단군별 일반형 **`<LISTTYPE>_NAME_SIMILARITY`**(예 `SANCTIONS_NAME_SIMILARITY`/`PEP_NAME_SIMILARITY`/`INTERNAL_NAME_SIMILARITY`, listType 미상 시 `NAME_SIMILARITY`)로 발급(tokenSet≥0.6 또는 edit≥0.85), 완전일치 시 `NAME_EXACT_MATCH`. 일치 여부 플래그만 — 원문 이름/생년/국적 값 미포함 |
| `requiredActions` | array<string> | `MANUAL_REVIEW`/`EDD_REVIEW`/... |
| `matchedEntries` | array<string> | 후보 entry_id(masked). **하위호환 유지** — `matchedCandidates`와 병존(기존 소비자 보존) |
| `matchedCandidates` | array<object> | **가산(additive) 필드.** 매칭 후보 출처계보. 각 원소 `MatchedCandidate`(아래 표) — `matchedEntries`의 각 entry_id를 `aml_watchlist_entries`+`aml_watchlist_sources` 조인으로 enrich한 best-effort 파생값. **raw PII 미포함**(masked entryId·출처·버전·점수·토큰개수만) |
| `matchedRules` | array<object> | 적용된 WLF 룰 참조 `{ ruleCode, threshold, score }`(파생값, DB `rule_version` 기준 투영). `score`(number)는 해당 룰에 대해 산출된 실측 유사도 점수(threshold 대비 판정 근거·엔진 WLF 룰 score 투영, `ScreeningResponse.matchedRules[].score` 코드=truth). 단수 `ruleVersion`과 구분 |
| `appliedPolicy` | object | **가산 엔진 스냅샷.** `{ profile(SANCTIONS\|PEP), configVersion, ruleVersion, definitionHash, reviewThreshold, highConfidenceThreshold, confidenceBand(NO_MATCH\|REVIEW\|HIGH) }`. 결과 생성 시점의 실제 ACTIVE 정의를 고정하며 WLF 검토 상세·재현 검증의 정본이다. `HIGH`도 자동 TRUE_MATCH가 아니라 검토 우선순위 표시다 |
| `subjectIdentity` | object | **가산(additive) 필드(bo-api WLF 매치 상세 투영).** reveal 게이트 대상 식별정보 메타 `SubjectIdentity`(아래 표) — 대상 식별자(`targetRef`) + reveal 가능 필드 키 목록만. **raw PII(이름·국적·성별·생년 원문) 미포함** — 원문은 `aml:pii:reveal`+사유+`RAW_DATA_ACCESS` 경로(§1.6, `POST /internal/v1/aml/pii/reveal` §2.6)로만 노출. **CUSTOMER·counterparty 대상 모두 `[NAME, NATIONALITY, GENDER, DOB]` 4필드 균일**(주체 무관). 주체가 보유하지 않는 필드(예 수취자=상대방의 성별·생년월일)는 reveal stub 이 빈 값(`""`)을 반환한다(placeholder 아님) |
| `ruleVersion` | string | 적용 WLF 룰/threshold 버전(DB `rule_version`) |
| `decidedBy` | string | 판정자(분석가, DB `decided_by`, nullable) |
| `decidedAt` | string(date-time) | 판정 시각(DB `decided_at`, nullable) |
| `createdAt` | string(date-time) | 결과 행 생성 시각(DB `created_at`, `ScreeningResponse.createdAt` 코드=truth). review-queue/history 기간필터·SLA 기준. **미영속 결과(실시간 POST 비저장)는 null 가능** — `decidedAt`(판정 시각)와 병기·구분 |
| `expiresAt` | string(date-time) | 실시간 결과 만료(§15.7) |

> **bo-api enrichment와 passthrough.** `matchedCandidates[]`·`riskGrade`·`requiredActions[]`·`subjectIdentity` 등은 bo-api가 명단/화면 read model로 enrich할 수 있다. 반면 `matchedRules[]`, `ruleVersion`, `scoreBreakdown`(`candidateStrategy` 후보 recall 스냅샷 포함), `appliedPolicy`는 엔진이 산출한 판정 증거이므로 bo-api가 재계산하거나 하드코딩 임계로 덮지 않고 손실 없이 전달한다. raw PII는 어느 경로에도 추가하지 않는다.

> **`screeningHistory`(이전 판정 이력 배열)는 `ScreeningResponse` 미포함.** 동일 `screeningId`의 이전 판정 이력은 `GET /api/v1/aml/screenings/{screeningId}` 상세 조회(§2.2) 응답에서 파생한다. PRD 화면파생 방향 채택 — bo-web/bo-api가 이력 상세가 필요할 경우 단건 조회 엔드포인트를 호출하며, 실시간 screening POST 응답(`ScreeningResponse`)에는 이력 배열을 포함하지 않는다.

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

> **데모 스크리닝 큐 = 실 인입 레코드(비-prod, 데이터 정직화 v9.27, 기능정의서 §1.11 BR-DEMO-HONESTY).** 데모(비위임) 스크리닝 큐/상세(`GET .../admin/aml/screenings`)는 **데모 멤버 집합을 즉석 생성하지 않고**, 송금 거래 인입마다 sender(`CUSTOMER`, 회원 vault 이름)+receiver(`COUNTERPARTY`, payload 이름/국가) **2건의 실매칭 레코드**를 인메모리 스토어(상한·eviction·`transactionRef` 쌍 그룹)에 적재해 그 레코드만 노출한다 — 인입 전이면 큐가 비어 있다. `screeningId` 은 인입 시 부여한 **랜덤 UUID**(자기서술적 hash 인코딩 폐기)이며, 미지의 id 는 not-found. 밴딩은 엔진 동형(≥0.66 `POSSIBLE_MATCH`·<0.66 `NO_MATCH`·`TRUE_MATCH`=분석가 4-eyes만). **부분 식별(이름+국가) 수취인은 overall 상한 0.65(name 0.55+country 0.10, 생년월일 미제공)로 자동 밴딩이 `NO_MATCH` — `FuzzyMatchEngine`(전체 가중치 합 정규화) 동형**이며, TM 명단 룰(§3.4a `watchlistMatch` nameScore 축, 기능정의서 §7.1 BR-011)과의 비대칭은 의도된 정직 동작이다(후속 매처 재정규화 검토). FP 화이트리스트 시드는 폐기(등록 액션만), 벌크런 카운트는 업로드 행 실매칭(transient)이다. **비-prod 전용**(위임/prod 경로 불변).

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
| `factors` | object | — | factor 입력 override(§11.1). **보조 입력 강등(요구 런 11)**: 1차 온보딩 RA 는 엔진이 `customer.cdd.completed` 인입 시 CDD 데이터로부터 직접 파생하고(§2.1 step 7d), `factors` 는 **테스트·수동 재평가용 보조 입력**으로 강등됐다 — 온보딩 인입 경로는 엔진 파생 factors(출처 `cdd:*` = `cdd:country-risk`/`cdd:kyc-evidence`/`cdd:wlf-screening`)를 정본으로 쓰고, 요청 override 유입 시 출처 `override` 로 파생값 위에 후적용·감사 기록(하위호환). 엔진 factor catalog 비변경 |
| `highRiskCountry` | boolean | — | (optional·**보조 입력 강등**) 당연고위험 트리거 — 고위험 국가 연계 신호(`EvaluateCommand`). 미지정=false. 온보딩 GEOGRAPHY 는 엔진이 국가위험 정본에서 파생(§2.1 step 7d (b)) — 본 플래그는 수동 경로 보조 |
| `wlfTrueMatch` | boolean | — | (optional·**보조 입력 강등**) 당연고위험 트리거 — WLF 진성 매치. 미지정=false. 온보딩 SCREENING 은 엔진이 WLF 스크리닝에서 파생(§2.1 step 7d (a)) — 본 플래그는 수동 경로 보조 |
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
| `mandatoryHighRiskReasons` | array&lt;string&gt; | 강제 등급 상향(floor) 적용 사유 코드 배열(영문 코드 passthrough, raw PII 없음). 강제 상향 미적용 시 빈 배열. **값집합 — (a) 당연고위험(HRR) 레지스트리·명단 floor**: `SANCTION`/`PEP`(WLF 진성 매치 명단 유형)·`HIGH_RISK_REGISTRY`(HRR 등록) 등. **(b) 국가위험 등급-기반 floor(V20·기능정의서 §5.1 (b′)·DB §7)**: **`HIGH_RISK_COUNTRY_NATIONALITY`**(고위험 국적)·**`HIGH_RISK_COUNTRY_RESIDENCE`**(고위험 거주국) 2종 — 국적/거주국 국가위험 ACTIVE 등급(`PROHIBITED→HIGH`·`HIGH→MEDIUM`)으로 결정적 상향, 해당 국가만 개별 병기. **국가위험 floor 는 HRR 과 구분**(모델 정본 `aml_risk_models.parameters.countryFloor` 소비, `forcedFloorEvidence` 원소 미추가) — FE(라벨 사전 `lib/aml-risk.ts`)는 국가위험 코드에 "국가위험 floor(HRR 아님)" 배지, HRR 코드에 "HRR" 배지를 매핑한다. 미지 코드는 raw 표기(graceful passthrough) |
| `forcedFloorEvidence` | array&lt;object&gt;\|null | **명단 매치(WLF) 강제 상향 근거 참조**(#1, 명단 매치 floor 전용). 각 원소 `{ listType(string — 매치 명단 유형, 예 `SANCTION`/`PEP`), screeningId(string\|null — 매치 스크리닝 실행 참조 토큰), entryId(string\|null — 매치 명단 엔트리 참조 토큰), label(string\|null — 사유 라벨) }`. **masked 참조 토큰만 — raw PII 없음**. 엔진 `factorBreakdown.forcedFloor` evidence 마커 파생. **국가위험 등급-기반 floor(`HIGH_RISK_COUNTRY_*`)는 이 배열에 원소를 추가하지 않고 `mandatoryHighRiskReasons` 코드로만 노출**(명단 매치가 아니므로 entry/screening 토큰 없음) — 명단 매치가 없으면 `null`/빈 배열. FE 는 명단 유형 뱃지 표시 + 명단 엔트리 브라우저 딥링크(§딥링크 계약)에 사용 |
| `nextReviewDueAt` | string(date-time) | 재심사 예정(DB `next_review_due_at`, nullable). **평가 시점 산출 예정일**(policy 로 재산출) — FE 보조 라벨 |
| `operativeNextReviewDueAt` | string(date-time)\|null | **운영 재심사일** — CDD 재이행 주기 관리 메뉴와 동일한 값(회원 주기 수동 조정 4-eyes 승인이 반영된 `aml_customers.next_review_due_at` 조인). FE 는 이 값을 '재심사일'로 우선 렌더하고 부재 시 `nextReviewDueAt` 로 폴백(#10). additive·nullable |
| `isOverride` | boolean | 수동 등급 조정 여부(DB `is_override`, 4-eyes 대상) |
| `evaluatedAt` | string(date-time) | 평가 시각(DB `evaluated_at`) |
| `inputDataAsOf` | string(date-time) | nullable. **입력 데이터 기준시점**(평가에 사용된 원천 데이터의 as-of 시점). 엔진 응답에 있으면 passthrough, 없으면 best-effort(`evaluatedAt` 대체). RA 상세·점수 목록(`GET .../risk-scores`, §2.7) 응답에 포함 |
| `policyPackVersion` | string | nullable. **정책팩 버전**(평가 시점 적용 Policy Pack(STR/CTR 기준) effective version). 엔진 응답에 있으면 passthrough, 없으면 `null`(stub 상수). RA 상세·점수 목록(§2.7) 응답에 포함 |
| `scenario` | enum | **평가 시나리오**(`ONBOARDING`/`ONGOING`, DB §3.9 `aml_risk_models.scenario`). `ONBOARDING`=1차·회원가입 CDD 완료 시점, `ONGOING`=2차·상시(STR/CTR 발동 시 거래 가중 재평가). 엔진 응답에 값이 없으면 bo-api 는 `ONBOARDING` 으로 안전 기본 처리(graceful) |
| `reassessmentAlerts` | array&lt;object&gt; | **2차(ONGOING) 재평가를 유발한 발동 STR/CTR 알림 계보**(재평가 사유). 각 원소 `{ alertId(string — 참조 토큰), ruleCode(string — 룰 코드 enum), severity(string), detectedAt(string(date-time)) }`. 엔진 `factorBreakdown.triggerAlerts` 파생(V12 parameters `trigger.families [STR,CTR]`). 1차(ONBOARDING) 행은 빈 배열. raw PII 없음(마스킹 토큰·enum·시각만) |
| `reviewShortened` | object\|null | **재이행 주기 단축(from→to)** — 2차 재평가가 재이행 주기를 앞당긴 경우 `{ from(string(date-time) — 단축 전 `next_review_due_at`), to(string(date-time) — 단축 후) }`. 엔진 `factorBreakdown.reviewShortened` 파생, **앞당기기만**(산출 주기가 기존 예정일보다 늦어 min-clamp 로 유지되면 `null`). 1차 행은 `null` |

`RiskOverrideRequest` → `POST /api/v1/admin/aml/risk-scores/{scoreId}/override`(🔒4-eyes, §2.7, scope `aml:case:update`, subjectType=`RISK_OVERRIDE`):

| 필드 | 타입 | R | 설명 |
|---|---|---|---|
| `targetGrade` | enum | R | 조정 목표 등급(§5.2 `LOW`/`MEDIUM`/`HIGH`/`PROHIBITED`). **하향만 허용** — 현재 등급보다 낮은 등급만 선택 가능(상향은 거부). 화면은 위험점수 목록에서 행 선택 후 현재 등급 기준 하향 가능 등급만 select 노출 |
| `reason` | string | R | 조정 사유(필수, 감사·결재 payload) |
| `targetRef` | string | — | 화면 목록·상세가 조회한 RA 대상 참조(customerRef) — 오버레이 폐루프 키·현재 등급 산출 기준을 화면과 통일하기 위해 동봉(#2·#3). 미전달 시 `scoreId` 로 graceful fallback(구 계약 하위호환) |
| `currentGrade` | enum\|null | 화면이 표시한 현재 등급(§5.2). 서버 산출값과 대조해 화면↔검증 불일치를 조기 차단하는 선택 힌트(#2). 미전달 시 서버가 대상 기준으로 산출 |

> **작성자(maker)는 요청 본문이 아니라 인증 principal 에서 서버 파생한다**(신뢰경계·4-eyes 작성자≠승인자). bo-api RA write 3경로 — draft(`POST .../ra-models`)·activate(`.../versions/{v}:activate`)·override(`.../risk-scores/{id}/override`) — 의 계약 record `RaDtos.{DraftRequest, ActivateRequest, OverrideRequest}` 에 `makerId` 필드는 **부재** — 클라이언트가 타 운영자 명의를 주입할 경로가 없고, 감사·결재·엔진 위임 payload 의 maker 는 인증 principal(`principal.email()`)로 채워진다(미인증 시 상신 거부). 형제 PEP 경영진 승인(`:submit-pep-approval`)·CDD 재이행 주기(`periodic-review-policy`) 상신과 동형. 응답 `202 { approvalId, status: "SUBMITTED" }`.

> override는 **블라인드 scoreId 직접 입력이 아니라** 위험점수 목록 조회(`GET .../risk-scores`, 등급 필터+`targetRef`) → 행 선택 → 현재 등급 기준 하향 가능 등급만 선택 → 사유 입력 → 4-eyes 상신 흐름이다(PRD §6.1 AML-RA-002).

> **RA 모델 관리 DTO `scenario`·`parameters`(bo-api BFF, 코드=truth).** bo-api 의 RA 모델 관리 read model `RaModel`(`GET /api/v1/bo/aml/ra-models`)과 그 하위 `RaModelVersion` 은 model-level 축 **`scenario`(ONBOARDING/ONGOING, DB §3.9 `aml_risk_models.scenario` 1:1)** 와 **`parameters`(JSON, DB §3.9 `aml_risk_models.parameters` 1:1)** 를 노출한다 — `RaModelVersion.scenario`/`parameters` 는 소유 `RaModel` 을 승계(같은 modelCode 의 버전은 동일 scenario)해 버전 행이 모델 그룹 밖에서도 자기서술적이다. 운영 family는 `KR_DEFAULT_RA=ONBOARDING`, `KR_ONGOING_RA=ONGOING` 두 개로 고정한다. FE는 `scenario`를 배지에 표시하고, 저장된 전체 정의를 scenario별 typed form으로 엄격 파싱해 ONBOARDING 가중치·CDD 파생 규칙과 ONGOING 가중치·STR/CTR/FDS 규칙을 독립 편집한다. 필수/미지/타입 오류 필드나 family-scenario 불일치는 UI 기본값으로 합성하지 않고 편집·시뮬레이션·활성화를 차단한다. enum 2종 = `ONBOARDING`(1차·온보딩·`KR_DEFAULT_RA`) / `ONGOING`(2차·상시·`KR_ONGOING_RA`, STR/CTR/FDS 발동 시 거래 가중 재평가→주기 단축→EDD 자동 개시). ONGOING 재평가 결과는 §3.3 `RiskScoreResponse.{scenario, reassessmentAlerts, reviewShortened}` 로 화면에 표시한다(bo-api `RaDtos.{ReassessmentAlert,ReviewShortened}` 1:1).

> **bo-api 프로필 `riskSummary.riskGrade` 등급 폴백 체인은 §3.9 후주 참조** — 고객 프로필 aggregate 의 `riskGrade`(top-level → `latestRiskScore.riskGrade` → `LOW`, `AmlCustomerProfileService#resolveGrade`)는 프로필 응답 절(§3.9 `CustomerProfileDto` 후주)에 명문화한다.

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

### 3.3d OnboardingInputCatalog → `GET /api/v1/admin/aml/ra-models/onboarding-input-catalog` · BFF `/api/v1/bo/aml/ra-models/onboarding-input-catalog`

최근 수신 `customer.cdd.completed`를 tenant 내 `customerRef`별 최종 수신 1건으로 축약해 1차 RA 설정과 실제 REST 입력 코드를 대조하는 **집계 전용·PII-safe** read model이다. `windowDays` 기본 90, 허용 1~365, 각 축 `values` 최대 100개(최종 수신시각 내림차순). 응답 shape:

`{ windowDays, windowStart, generatedAt, latestCustomerCount, sourceOfFunds, kycLevels, occupations, nationalities, residenceCountries }`

각 축 `OnboardingInputAxis`는 `{ values: OnboardingInputValue[], ignoredValueCount, truncatedCodeCount }`, 각 값은 `{ code, customerCount, lastReceivedAt, canonical }`이다. `ignoredValueCount`는 blank/unsafe라 원문을 redaction한 고객 값 수, `truncatedCodeCount`는 100개 표시 상한 밖의 정상 distinct code 수로 서로 합치지 않는다.

- 추출 경로: `payload.kyc.sourceOfFunds`, `payload.kyc.kycLevel`, `payload.kyc.occupation`, `payload.nationality`, `payload.kyc.residenceCountry`(blank이면 `payload.country` fallback).
- `canonical=true`: SOF 6종, KYC 4종, 실제 ISO alpha-2, 또는 안전 분류코드인 occupation. SOF/KYC의 계약 외 legacy는 안전한 코드면 값은 보이되 `canonical=false`다.
- 공백·누락·안전 형식 밖 값은 원문을 반환하지 않고 축별 `ignoredValueCount`만 증가시킨다. customerRef/eventId/name/DOB/sourceOfFundsDescription/전체 JSON payload는 응답에 없다.
- BFF는 엔진 응답을 1:1 통과하며 어떤 profile에서도 local stub을 생성하지 않는다. 엔진 미연결·빈 응답은 `503 AML.ENGINE_UNAVAILABLE`다.

### 3.4 TransactionEvaluateRequest → `POST /api/v1/aml/transactions/evaluate` (DB `aml_alerts`, `AlertController.TransactionEvaluateRequest`)

**code truth 8필드**(record): `transactionRef`·`targetRef`·`direction`·`amount`·`amountMinor`·`currency`·`counterpartyRef`·`channelType`(+ optional `geo`·`riskSignals`). corridor·phpEquivalent 등 부가 신호는 거래 정규화 payload(`aml_canonical_events.payload`)에서 velocity/cmp 노드가 읽으며 본 evaluate 요청 바디에는 포함하지 않는다(아래 주석).

| 필드 | 타입 | R | 설명 |
|---|---|---|---|
| `transactionRef` | string | R | 거래 ref(keyed token). hanpass-ph: `remit.transfer_number`/`domestic.transaction_id`/`wallet.*_transaction_id` |
| `targetRef` | string | R | 고객(회원)/법인 ref |
| `direction` | string | — | `INBOUND`/`OUTBOUND`(미지정 가능) |
| `amount` | string(decimal) | — | NUMERIC(24,8) 호환 문자열. 존재 시 velocity/cmp base amount로 우선 |
| `amountMinor` | integer | — | 통화 최소단위(병행, `amount` 부재 시 base, DB `amount_minor`) |
| `currency` | string | — | ISO |
| `counterpartyRef` | string | — | 상대방(수취인 등) |
| `channelType` | string | — | 충전(`CASH_IN`/walletchg)·국내(`DOMESTIC_REMIT`/domestic)·해외(`CROSS_BORDER_REMIT`/remit)·인바운드(`INBOUND_REMIT`/inbound) 등 hanpass-ph 채널 |
| `geo` | object | — | 접속/IP 위치 `{ country, latitude, longitude }`. 위도/경도는 보조 참고값이며 필수 아님(record optional 필드) |
| `riskSignals` | object | — | FDS와 동일한 거래 보조 신호 `{ memberAgeDays, accountChangedWithinHours, deviceChangedWithinHours, manyToOnePattern, oneToManyPattern, electionPeriod, regionalRegistrationSpikeCount, bulkCashAmountBase }`(record optional 필드) |
| `externalSignals` | object | — | FDS 인입 계약과 공유하는 Phase7 외부 인텔리전스 pass-through(flat 19필드, 전부 optional — §3.17 externalSignals 블록 note 와 동일 키·타입). 설정형 CTR/STR 룰 피처 `trade.*`/`seller.*`/`settlement.accelerationRequest`/`vendor.bankAccountRecentlyChanged`/`invoice.approverRoleMismatch`/`crypto.*`/`market.manipulationPattern`/`employee.*` 로 노출 |

> **TM feature 신호(요청 바디 외).** `HIGH_RISK_CORRIDOR`·`RAPID_MOVEMENT`·`REFUND_LAUNDERING`·`ROUND_TRIPPING` 등 금액 시나리오는 `transaction.phpEquivalent`(PHP 환산액)와 `transaction.channelType`을 feature로 사용한다. `phpEquivalent`는 거래 정규화 payload(`payload->>'phpEquivalent'`)에서 노출되며(`TmEvaluationService.buildSnapshot`), 부재 시 미노출 fail-safe(발화 안 함). corridor(`{sendCountry, receiveCountry, sendCurrency, receiveCurrency}`)·`amountBase`(USD 정규화, remit `usd_amount/report_amount`)도 payload 파생이며 evaluate 요청 바디에는 포함하지 않는다. **데이터 신호이며 규제(CTR/STR) 임계 교체가 아니다**(§3.4a evidence). |

> **송금 수취인 정보(v9.26 — 인입 payload `HanpassPhTransactionPayload`, 연동 §4.2).** 송금 거래의 수취인 STR_PEP·STR_SANCTION 동시 명단 평가(§3.4a `watchlistMatch.matchedParty=RECEIVER`, 기능정의서 §7.1 BR-013)를 위해 인입 payload 에 **`receiverName`**(nullable, 비-PII 운영값 — 매칭 transient·미영속)·**`receiverCountry`**(nullable, ISO 수취 국가=국적, **해외송금만**)가 additive 가산된다. 수취인 정보 규격은 **국내송금=이름만 / 해외송금=이름+국가**(성별·생년월일 미제공). 수취인 참조(`receiverRef`)는 서버가 `sha256(name|country)` 로 파생(payload 의 기존 `receiverRef` 우선). 엔진 evaluate 요청 바디(위 8필드)에는 수취인 이름/국가 원문을 싣지 않으며 COUNTERPARTY 스크리닝 계보로만 평가한다. |

> FDS/TM 공통 거래 payload 동기화: AML TM은 FDS 탐지 결정과 같은 실시간 거래 payload를 사용하되, CTR/STR 사후 보고 목적의 룰로 평가한다. 보조 신호는 TM feature snapshot에 `geo.country`, `geo.latitude`, `geo.longitude`, `customer.accountAgeDays`, `account.changedWithinHours`, `device.changedWithinHours`, `behavior.manyToOnePattern`, `behavior.oneToManyPattern`, `election.active`, `election.registrationSpikeCount`, `election.bulkCashAmountBase`로 기록한다.

응답 `TransactionEvaluateResponse`: `{ evaluated: true, alerts: [ { alertId, alertType(enum TM_SCENARIO/SCREENING/RA/FDS_ESCALATION/VENDOR_ALERT — 본 API가 정본, DB §5.18 `alert_type` 1:1), ruleCode(§5.6 — CTR/STR 룰 코드, v9.21), severity(LOW/MEDIUM/HIGH/CRITICAL), status(§5.7), evidence } ] }`. TM 알림은 발동 CTR/STR 룰마다 하나씩 반환된다(레거시 시나리오 발동 폐기).

#### TM 시나리오 카탈로그 (`TmScenario` enum 10종 — code truth, hanpass-ph 데모 phpEquivalent)

`scenarioCode`는 `TmScenario` enum 10종(DB §5.6 `tm_scenario`)이며, 발화 여부는 tenant별 `aml_tm_scenarios`의 ACTIVE 버전(임계·윈도우·DSL)에 따른다. hanpass-ph 데모(`tenant_demo`) ACTIVE 시나리오의 금액 임계는 **phpEquivalent(PHP 환산)** 기준으로 적재된다(Flyway V28, 환산식 = 기존 USD 임계 ×56). 목록·매칭 정합: ACTIVE 시나리오만 발화하며 DRAFT(`REFUND_LAUNDERING`은 데모 ACTIVE, `TRADE_MISPRICING`은 DRAFT 유지)는 발화하지 않는다.

| scenarioCode | 데모 상태 | feature·임계(phpEquivalent) | 비고 |
|---|---|---|---|
| `STRUCTURING` | ACTIVE | count 기반 분할(velocity count) — 금액 무관 | 분할 충전/송금 |
| `RAPID_MOVEMENT` | ACTIVE | velocity count 2h ≥ 3 **AND** phpEquivalent ≥ 56,000 (PHP) | 단기 급증 |
| `HIGH_RISK_CORRIDOR` | ACTIVE(v3) | phpEquivalent ≥ 280,000 (PHP) **AND** channelType=`CROSS_BORDER_REMIT` | 고위험 corridor |
| `REFUND_LAUNDERING` | ACTIVE | velocity count 7d ≥ 6 **AND** phpEquivalent ≥ 28,000 (PHP) | 환불·역송 |
| `ROUND_TRIPPING` | ACTIVE | velocity count 14d ≥ 4 **AND** phpEquivalent ≥ 112,000 (PHP) | 순환 거래 |
| `MULE_NETWORK` | (시드) | count/네트워크 기반 — 금액 무관 | 머니뮬 네트워크 |
| `SHELL_MERCHANT` | DRAFT | — | enum 보존(hanpass-ph 데모 미활성) |
| `TRADE_MISPRICING` | DRAFT | — | enum 보존(hanpass-ph 데모 미활성) |
| `CRYPTO_OFF_RAMP` | (미활성) | — | enum 보존(hanpass-ph 외부 ingest 미사용) |
| `INTERNAL_OVERRIDE_ABUSE` | (미활성) | 내부 override 남용 | 운영 통제 |

> count/네트워크/채널 cmp 노드는 금액과 무관하므로 PHP 환산 대상이 아니다(V28는 ACTIVE amount leaf만 phpEquivalent로 전환). `phpEquivalent`가 적재되지 않은 거래는 금액 노드가 미발화(fail-safe)된다.

### 3.4a AlertDto → `GET /api/v1/aml/alerts/{alertId}` (DB `aml_alerts` §3.10 10컬럼+감사, `AlertController.AlertDto`)

| 필드 | 타입 | 설명 |
|---|---|---|
| `alertId` | string(uuid) | DB `alert_id` PK |
| `alertType` | enum | §5.18 `alert_type`(`TM_SCENARIO`/`SCREENING`/`RA`/`FDS_ESCALATION`/`VENDOR_ALERT`). **API 정본, DB 1:1** |
| `ruleCode` | string\|null | TM_SCENARIO 타입 알림의 안정 발동 룰 코드. 잠금 기준선 `AmlReportRuleCode` 10종 또는 사용자 정의 `ConfigurableReportRule.ruleCode`이며 엔진 DB `scenario_code`를 JSON `ruleCode`로 노출한다. custom evidence는 `trigger.ruleSource=CUSTOM`·`ruleFamily`·`ruleVersion`을 병기한다. 비-TM 알림은 null. |
| `targetRef` | string | 대상 고객/법인 ref(회원번호/대상 식별자, DB `target_ref`, nullable) |
| `transactionRef` | string | 관련 거래 ref(DB `transaction_ref`, nullable). hanpass-ph: charge_order_id/transaction_id/transfer_number/wallet_transaction_id |
| `severity` | enum | §5.19 `alert_severity`(`LOW`/`MEDIUM`/`HIGH`/`CRITICAL`) |
| `status` | enum | §5.7 `alert_status` **6종**: `DETECTED`/`TRIAGED`/`CASE_OPENED`/`DISMISSED`/`ESCALATED`/`STR_RECOMMENDED`(DB CHECK 6종. 이후 조사·보고·종결은 `aml_cases.status` 인계) |
| `evidence` | object | **TM 알림 상세 데이터모델(DB §3.10 정본). 정상 경로는 발동 CTR/STR 룰의 증거(v9.21 — 레거시 시나리오 발동 폐기)**. ① 트리거 `{ ruleCode(AmlReportRuleCode), strReasonCode(STR 룰만 — StrReasonCode: PEP/SANCTION/KYC_MISMATCH/STRUCTURED/NO_PURPOSE/THIRD_PARTY/UNUSUAL_PATTERN/MANUAL), description(룰 카탈로그 자연어) }`. 레거시 시나리오 행이 남아 있으면 트리거가 `{ scenarioCode, strIndicator, description }`일 수 있으며 bo-api는 표시용 fallback으로만 소비한다. ② 집계 패턴 `{ measure, window, count, amount, currency, threshold, thresholdMet, appliedRiskGrade, countThreshold, distinctCounterparties, counterpartyThreshold }` — **CTR 룰**은 (주체, 영업일) 현금거래 합산액·임계, **STR 룰**은 주체 rolling 윈도우 집계(있는 룰에 한함). `measure`는 서술 라벨, `threshold`는 적용된 effective threshold이며 `appliedRiskGrade`/`countThreshold`/`distinctCounterparties`/`counterpartyThreshold`는 차등 임계·건수·다상대 축이 있는 경우에만 채운다. ③ `relatedTransactions[]`(`{ transactionRef, subjectRef(거래 주체 회원번호 토큰), memberRef(비PII 회원 업무참조 = originator.partyReference), channel, amount, currency, corridor, counterpartyRef, occurredAt, fdsDecisionRef }`) — 집계를 구성한 형제거래(최신순, 표시 캡 20; 윈도우 조회 불가·빈 결과 시 평가 거래 단건 폴백). **수취인 원문 이름(`counterpartyName`)은 evidence JSONB 영속 금지**이며 read-path vault reveal(§19.2)로만 해소한다. ④ `fundGraph`(`{ nodes[], edges[], path[], source }`; 윈도우 거래가 있으면 canonical 이벤트 파생 실 그래프 `source=CANONICAL_EVENTS`, 무거래 시만 `PLACEHOLDER_NO_TRANSFER_LINKS`). **노드 kind 는 product 별 파생(v9.33, 코드=truth `FundGraphBuilder`)** — 루트 `SUBJECT` + WALLET_TOPUP→`FUNDING_SOURCE`(충전수단 `fundingInstrumentType`·기본 INBOUND)·CARD_PAYMENT/WALLET_PAYMENT→`MERCHANT`(가맹점 `merchantRef`·label 은 `merchantCountry` 있을 때 `ref (국가)`·기본 OUTBOUND)·CROSS_BORDER_REMITTANCE/DOMESTIC_TRANSFER→`COUNTERPARTY`(`counterpartyRef` 토큰)·신호 전무만 `UNKNOWN_CP` 폴백(노드 first-seen·엣지 amount desc 최대 20·거래 최대 50). **COUNTERPARTY label 은 모든 `aml:case:read` 경로(TM evidence·Subject360 fund-view §2.5a 포함)에서 토큰만**(§19.2, P0-09 — 구 fund-view `이름 (국가)` 자동 vault reveal 은 제거, `counterpartyName==null` 로 빌더 전달). 원문 이름은 `aml:pii:reveal` reveal API(§2.6)로만 산출한다. + `features`(velocity 스냅샷 `{ velocityCount24h, velocitySumPhp, amountPhpEq }`, 있을 때). ⑤ `watchlistMatch`(**STR_PEP·STR_SANCTION 전용**, v9.22~v9.26) `{ listType(PEP\|SANCTIONS), entryId, entryName(마스킹 이름 토큰), sourceCode, provider, matchScore, nameScore(데모 발동 기준 ≥ 0.92), matchReasonCodes[], screeningRef, origin(WATCHLIST_MATCH\|KYC_PEP_FLAG), entryIdentity(v9.31 — 명단 엔트리 식별정보 비교 메타 `{ entryRef, fields[] }`), matchedParty(v9.32 — `MEMBER`\|`RECEIVER`), partyRef, partyIdentity, additionalMatches[] }`. 데모 정본은 당사자 이름(+해외는 국가 보조)을 ACTIVE 명단 엔트리와 실매칭하고, 실엔진은 대상 최신 스크리닝 매칭 엔트리 중 룰 listType 일치 항목을 계보로 삼으며 부재 시 `origin=KYC_PEP_FLAG`로 정직 fallback 한다. 송금 채널(`DOMESTIC_REMIT`·`CROSS_BORDER_REMIT`)은 수취인 COUNTERPARTY 스크리닝 계보가 있으면 RECEIVER 매칭을 함께 수록하고, 계보 부재 시 수취인 평가를 skip 한다. 회원번호/거래번호는 업무 식별자로 노출하고 이름·계좌·지갑 등 raw PII 는 금지 |
| `subject360Ref` | string | 대상 360° 통합뷰 링크 키(= `targetRef`/`customerRef`) → `GET /api/v1/bo/aml/subjects/{customerRef}/360`(§2.5a). nullable |
| `sourceOrigin` | enum | §5.20 `source_origin`(`AML`/`FDS`/`VENDOR`) |
| `externalAlertRef` | string | 외부 벤더 alert 식별자(DB `external_alert_ref`, nullable, `source_origin=VENDOR`일 때) |
| `dispositionReason` | string\|null | **오탐 종결(`DISMISSED`) 처분 사유 코드**(DB `disposition_reason` VARCHAR(64), V30, nullable). `:dismiss` 전이 시 기록한 사유 코드 문자열(예 `FALSE_POSITIVE` 계열)이며, **불변식상 `DISMISSED` 상태에서만 non-null**(그 외 상태·구 알림은 null). 룰 효과성 오탐율(§12-B.3 = `DISMISSED`/알림)·감사의 실집계 근거. 사유 코드 카탈로그는 bo-api/bo-web 이 강제하고 엔진은 CHECK 미부과(하위호환 optional) |
| `dispositionActor` | string\|null | **오탐 종결 처분 행위자**(DB `disposition_actor` VARCHAR(128), V30, nullable). `:dismiss` 를 수행한 분석가 식별값. `dispositionReason` 과 동일 불변식(`DISMISSED` 에서만 non-null). raw PII 아님(운영 행위자 참조) |
| `createdAt` | string(date-time) | 생성 시각 |
| `updatedAt` | string(date-time) | 최종 수정 시각 |
| `aggregationSummary` | object\|null | **목록(브라우즈) 응답 한정 triage 프리뷰 집계.** TM 알림 **목록**(`GET /api/v1/bo/aml/alerts`, §2.5a → bo-api `AlertSummary`) 응답에서만 채워지는 가산 필드. `evidence`(트리거·집계 패턴)에서 목록 시점 파생(N+1 없음·행별 evidence 조립 회피)하며, **raw PII 미포함(집계 수치·라벨만)**. 단건 상세(`AlertDto`)는 `evidence` 전문을 제공하므로 본 요약은 생략 가능(null). 원소 `AggregationSummary`(아래 표) |
| `subjectIdentity` | object\|null | **명단 룰(STR_PEP·STR_SANCTION) 단건 상세 한정 가산 필드(v9.24, bo-api read-time projection — 엔진 API 무변경).** 원거래 대상 회원의 식별정보 비교 메타 — WLF 매치 상세와 **공용 `SubjectIdentity` 타입**(§3.2, `{ targetRef, fields[] }`, `fields ⊆ [NAME, NATIONALITY, GENDER, DOB]`). **raw PII 미포함** — reveal 가능 필드 키만. 원문은 `POST /api/v1/bo/aml/pii/reveal`(`aml:pii:reveal`+사유+`RAW_DATA_ACCESS` 감사, §2.6) 재사용으로만 노출(신규 엔드포인트 없음). 비-명단 룰·구 알림·identity 부재 시 `null` |

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
| `memberRef` | string\|null | 비PII 회원 업무참조(화면 회원번호 열; `subjectRef`/`targetRef` 토큰과 별개, `originator.partyReference` 파생) |
| `counterpartyRef` | string\|null | 상대방 ref(마스킹 토큰) |
| `counterpartyName` | string\|null | 수취인 원문 이름. **`aml:case:read`(본 related-transactions·알림 조회/목록) 경로에서는 항상 null**(P0-09 — 자동 reveal 제거, 화면은 `counterpartyRef` 마스킹 토큰으로 폴백). 원문은 오직 감사되는 `aml:pii:reveal` reveal API(§2.6)에서만 산출. evidence JSONB 미영속 |
| `direction` | string\|null | 거래 방향(입금/출금 등) |
| `amount` | number | 거래 금액(base) |
| `currency` | string\|null | 통화(ISO 4217) |
| `channel` | string\|null | 채널(충전/국내/해외) |
| `corridor` | string\|null | corridor(송금국-수취국) |
| `occurredAt` | string(date-time) | 거래 발생 시각 |
| `fdsDecisionRef` | string\|null | 연계 FDS 판정 ref |

> raw PII 미포함 — `memberRef`·`transactionRef`·`counterpartyRef` 는 업무 식별자/마스킹 토큰으로 노출하고 계좌·지갑 등 원문 PII 는 금지(§1.6·§19.2). party 식별정보(송금인·수취인 신원)는 §3.2 `subjectIdentity` 규약을 상속한다 — evidence JSONB 및 목록 응답에는 마스킹 토큰(`targetRef`/`counterpartyRef`)만 영속·실린다. **`counterpartyName`(수취인 원문 이름)은 이 `aml:case:read` 경로에서 자동 산출하지 않는다(P0-09 — 구 read-path auto-reveal 제거): 항상 `counterpartyName=null` 로 반환되고 화면은 `counterpartyRef` 토큰으로 폴백한다.** 원문은 오직 감사되는 별도 reveal API `POST /internal/v1/aml/pii/reveal`(§2.6, `aml:pii:reveal` scope + 사유 + `RAW_DATA_ACCESS` 감사·fail-closed)에서만 요청 한정 transient cleartext 로 산출한다 — evidence JSONB 에는 미영속(§3.4a evidence 스키마와 정합).

### 3.4b Subject360Dto → `GET /api/v1/bo/aml/subjects/{customerRef}/360` (bo-api 집계 read model, DB §3.16)

| 필드 | 타입 | 설명 |
|---|---|---|
| `customerRef` | string | 대상 키(= `member.member_id`/회원번호). domestic-svc varchar(36) join 정규화 |
| `identity` | object | 신원·CDD 요약(`member-svc`) `{ subjectType(string: `customer`/`transaction-only` — 고객 마스터 보유 여부), displayNameMasked(string: 표시명 마스킹 토큰), kycStatus, country, … }`(hash/token) |
| `pepStatus` | object\|null | **PEP(정치적 주요인물) 상태 요약**(DB §3.3 `aml_customers.is_pep`/`pep_approval_id`, V24). `null` = 거래 전용 주체. `{ isPep(boolean — 경영진 승인 EXECUTED 여부), pepApprovalStatus(string\|null: 진행 중 `PEP_APPROVAL` 결재 상태 `SUBMITTED`/`EXECUTED`/`REJECTED`/null), pepApprovalId(string(uuid)\|null — 확정 결재 증거 링크) }`. 비-PEP은 `isPep=false`. raw PII 미포함(상태·토큰만) |
| `riskSummary` | object\|null | 위험·활동 요약. `null` = **RA 미산정**(거래 전용 주체이거나, 고객 마스터는 있으나 RA read 실패/미산정 — 이 둘은 `identity.kycStatus`/`raAvailable` 조합으로 구분, 아래 참조). `{ riskGrade(§5.2), riskScore, factorBreakdown, nextReviewDueAt, reviewCadenceMonths(integer\|null — 등급별 재이행주기 정책(§3.22) 파생 재확인 주기, 회원 상세 '다음 재심사 기한'·임박 배지 표시), mandatoryHighRisk(**boolean\|null** — 당연고위험 강제 상향 여부; `null`=미상(위임 경로에서 RA read 로 파생 불가) — `false` 단정 금지, CDD profile §3.9 와 1:1), highRiskRegistryReason(**array&lt;string&gt;** — 당연고위험 레지스트리 사유, 단수 아님), screeningStatus(**실 WLF 최근 판정 상태** — `NO_MATCH`/`POSSIBLE_MATCH`/`TRUE_MATCH`/`FALSE_POSITIVE`/`AUTO_DISCOUNTED`/`ESCALATED`(§3.2 `ScreeningStatus`), 판정 부재/조회 실패 시 `UNKNOWN`. 구 계약의 RA 등급 파생 `REVIEW`/`CLEAR` 폐기 — '스크리닝' 라벨과 실 WLF 판정 의미 정합) }`. PEP 확정 시 `riskGrade`=HIGH 강제 상향(PROHIBITED 아님 — 거래 허용+EDD) |
| `raAvailable` | boolean | **RA(위험평가) read 성공 여부 마커.** `true`=RA 산정됨(`riskSummary` 채워짐). `false` + `identity.kycStatus != "NO_CUSTOMER_MASTER"` = **RA 미산정(고객 마스터 있음)** — RA read 404/일시 오류. `false` + `identity.kycStatus == "NO_CUSTOMER_MASTER"` = **거래 전용 주체**(고객 마스터 없음). RA 조회만 실패했을 때 identity 를 보존하며 '거래 전용'으로 오강등하지 않기 위한 구분 필드(run5 #5) |
| `transactionFeed` | array<object> | 최근 30일 통합 이력의 요청 페이지(`transactionRef`·`channel`·`amount`·`currency`·`corridor`·`counterpartyRef`(마스킹 토큰)·`direction`·`status`(`DECIDED`/`MONITORED`/null)·`occurredAt`). 빈 배열 가능 |
| `transactionFeedTotalCount` | integer(long) | 최근 30일 거래 exact count. 현재 배열 길이와 독립이며 다음 페이지 존재 여부의 정본 |
| `transactionFeedDegraded` | boolean | count/page 조회 실패 또는 부분 강등. true이면 빈 배열·0건을 실제 무거래로 단정하지 않고 화면 경고 표시 |
| `fundGraph` | object | `wallet-svc` `transfer_links` 자금그래프(funnel — 노드/엣지 요약, token). `source=PLACEHOLDER_NO_TRANSFER_LINKS` 가능(자금이체 링크 미연동) |
| `caseStrSummary` | object | 케이스·STR 건수 요약 `{ alertCount, openCaseCount, caseCount, strCount }`. 알림·케이스 건수는 엔진 `activity-summary`의 **대상(`targetRef`) exact count**를 재사용하며 목록 page/size와 무관하다. `openCaseCount`의 비종결은 `OPEN`·`INVESTIGATING`·`PENDING_APPROVAL`이다. 고객 profile이 없는 거래전용 주체도 같은 exact endpoint를 조회하고, 엔진 강등/순수 stub일 때만 대상 필터 목록으로 폴백한다. **STR 건수는 준법감시 전담 scope 한정 투영(tipping-off §19.2a)** |
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
| `originAlertId` | string(uuid) | — | **발단 alert**(알림→케이스 전환, DB `origin_alert_id`). GET 상세(`CaseDetail`)가 실값 응답 — 위임(엔진) 경로 유실 결함(run3 D5·D8) 해소 |
| `originScreeningId` | string | — | **발단 screening/RA 스코어 id**(RA→EDD 착수, DB §3.11 `origin_screening_id` **VARCHAR(96)·V15**, FK 아님·문자열 참조 토큰). GET 상세가 실값 응답 — 이 필드 부재로 `null` 하드코딩되던 케이스 상세 '발단' 유실(run3 D8) 해소 |
| `originFdsCaseRef` | string | — | FDS 위임 발단 cross-ref(DB `origin_fds_case_ref`, `source_origin=FDS` 시 채움. fds-svc 역추적용, nullable) |
| `timeline` | array<object> | — | 처리 이력(evidence) |
| `dueAt` / `closedAt` | string(date-time) | — | SLA·종결 |

`CreateCaseRequest`(수동 케이스 생성, `POST .../cdd/cases`): `{ caseType, targetRef?, priority?, assignedTo?, dueAt?, originAlertId?, originScreeningId?, eddTrigger? }` — `originAlertId`(알림→케이스 전환)·`originScreeningId`(RA→EDD 착수)·`eddTrigger` 는 발단 계보로 **생성→재조회에서 실값 영속**(run3 D5·D8, 전부 optional).
`CaseCloseRequest`(🔒4-eyes): `{ resolution, reason, makerId }` → 결재 상신. `makerId`는 인증 principal과 같은지 확인하는 호환 assertion이며 서버는 인증 주체만 maker로 저장한다.
`CaseTimelineEntryRequest`: `{ kind, note, evidenceRefs[] }`.

### 3.6 RegulatoryReportDto (Admin, DB `aml_regulatory_reports`)

| 필드 | 타입 | R(생성) | 설명 |
|---|---|---|---|
| `reportId` | string(uuid) | — | 응답 |
| `reportType` | enum | R | §5.10 report_type |
| `caseId` | string(uuid) | — | 연관 case |
| `targetRef` | string | — | 대상 |
| `status` | enum | — | §5.11 report_status. 허용값 8종(DB §5.11 정본): `DRAFT`/`UNDER_REVIEW`/`APPROVED`/`SUBMITTED`/`ACKNOWLEDGED`/`SUBMISSION_FAILED`/`REJECTED`/`CANCELLED` — FIU 회신 폐루프(설계서 §14.1a) |
| `reportPayload` | object | R | 본문(PII는 hash/token). **STR 보고**는 `{ family:"STR", triggerRef, reasonCodes[], channelType?, watchlistMatches[]? }` — `watchlistMatches[]`(v9.22)는 STR_PEP·STR_SANCTION 발동 시 알림 `evidence.watchlistMatch`(§3.4a ⑤)와 **동일 lineage**(listType·entryId·entryName·sourceCode·provider·matchScore·screeningRef·origin·**matchedParty·partyRef·additionalMatches[]** (v9.25 — 당사자 구분))를 실어 알림-보고 근거를 일치시킨다 |
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

`CaseLinkedStrDraftRequest`: `{ caseId }` → `RegulatoryReportDto`. 같은 case 재호출은 같은 STR draft를 반환하며 `(tenant_id,case_id)`당 STR 하나를 보장한다. 보고 상신의 `makerId`도 인증 principal과 일치해야 한다.

`ReportRejectRequest`/`ReportCancelRequest`(🔒4-eyes, §2.7 `:reject`/`:cancel`): `{ makerId, reasonCode(string ●, 사유 코드 필수), reason(string △), approvalLine: "REPORTING_OFFICER" }` — `:cancel`로 CTR 제외 처리(§14.3) 시 `ctrExemptionCode`(●) 병기. **종결(`REJECTED`/`CANCELLED`) 시 `reasonCode`는 `aml_regulatory_reports.closure_reason_code`(DB §3.12)에 영속**되어 미보고 사유 분포(§2.7 `unreported-reasons`)의 집계 원천이 된다(T4 AML-ENG-04 — **확정**).

`DelayBucket`(§2.7 `reports/stats/str-delay` 응답, T4 AML-ENG-04 — **확정**): `{ bucketCode(enum: ON_TIME/D1_3/D4_7/D8_14/D15_PLUS), label(string), count(long) }` — 5종 버킷 0-fill 고정 배열(분포 모양 안정). 보고 행·PII 미노출(집계 카운트만). 지연 기준 = candidate(`created_at`)→제출(`submitted_at`) 경과의 법정 SLA(§14.4 BR-006, STR=결재승인+3영업일) 대비 상대 일수. SUBMITTED 미도달 건은 지연 모수에서 제외(미보고 사유 분포로 분류).

`UnreportedReason`(§2.7 `reports/stats/unreported-reasons` 응답, T4 AML-ENG-04 — **확정**): `{ reasonCode(string — `closure_reason_code` 코드값 또는 legacy 미영속 = `UNSPECIFIED`), count(long) }` — count 내림차순·reasonCode 사전순 정렬. 보고 행·PII 미노출.

`ReportDailyCount`(bo-api `GET /api/v1/bo/aml/stats/str|ctr` 응답 필드 `dailyTrend`, 2026-07-06 사용자 요청 반영): `{ date(LocalDate, yyyy-MM-dd), count(long), cumulativeCount(long) }` — `createdAt` 기준 기간 내 일별 보고 발생 건수와 조회 기간 누적 건수. 날짜 버킷은 요청 period(7d/30d/90d) 전체를 0-fill한다. STR은 기존 통계와 동일하게 COMPLIANCE 전담 role-gate 뒤에서만 산출하고, CTR은 열림. 보고 행·PII 미노출(집계 카운트만).

#### 3.6a 룰군별 룰 개요 (bo-api AML-STAT, `GET /api/v1/bo/aml/stats/report-rules`)

`ReportRuleOverview`: `{ scope("TENANT"), family("CTR"|"STR"), period("7d"|"30d"|"90d"), rules(ReportRuleOverviewRow[]), generatedAt(ISO-8601), cacheTtlSeconds(int, 45) }` — CTR·룰 효과성 통계 메뉴는 `family=CTR`(CTR 룰 개요), STR·룰 효과성 통계 메뉴는 `family=STR`(STR 룰 개요)을 조회. `family=STR`은 STR 퍼널과 동일한 tipping-off 전담(COMPLIANCE) 게이트 — 비전담 `403 AML.FORBIDDEN_SCOPE`.

`ReportRuleOverviewRow`: `{ ruleCode, family("CTR"|"STR"), reportType, reasonCode, evaluationMode, actions, status, naturalLanguage, hitCount30d, draftCount, lastFiredAt, tuningRecommended, source("BUILT_IN"|"CUSTOM"), conditions[] }`. BUILT_IN은 카탈로그/라이브 보고 store, CUSTOM은 `aml_configurable_report_rules`와 실제 `aml_alerts.scenario_code` lifecycle 집계가 원천이다. 같은 custom 코드에 여러 버전이 있으면 **실제 평가 중인 ACTIVE를 우선 표시**하고, ACTIVE가 없을 때만 최신 DRAFT를 표시한다. custom DRAFT는 발동하지 않으므로 `draftCount=0`; `actions=["TM_ALERT"]`. `conditions[]`는 built-in resolved 파라미터 또는 custom safe DSL leaf를 표시한다.

> **재제출(RESUBMIT)·기각/취소 통제.** `SUBMISSION_FAILED` 건의 정정 후 재제출은 **별도 엔드포인트 없이 기존 `POST .../reports/{reportId}:submit`(🔒 `STR_SUBMIT`/`CTR_SUBMIT`) 신규 결재 사이클을 재사용**하며 서버가 `resubmitCount`를 증가시킨다(연동 §6.2). 보고 기각/취소(`REJECTED`/`CANCELLED`) 전이는 **전용 엔드포인트 `POST .../reports/{reportId}:reject`/`:cancel`(§2.7)** 로 수행하며, CTR 제외 처리(`CANCELLED`+`ctrExemptionCode`)를 포함해 **사유 코드 필수 + 보고책임자 결재(4-eyes, `REPORTING_OFFICER`, 자기승인 금지)** — 설계서 §14.1a/§14.3 정본.
>
> **local/demo mock 규제기관 결정적 폐루프(코드=truth).** `aegis.aml.report.submission.mock.reject-demo=true`일 때 `MockRegulatorSubmissionAdapter`는 manifest `evidenceHash`의 마지막 hex nibble이 `0`인 **최초 제출(`resubmitCount=0`)만** `SUBMISSION_FAILED`/`submissionErrorCode=SUBMISSION_REJECTED`로 닫는다. 같은 report에 위 공식 `:submit`+새 4-eyes 사이클을 수행하면 기존 report/evidence 계보를 보존하면서 `resubmitCount`가 1 이상으로 증가하고, 동일 reject bucket이어도 mock은 `ACKNOWLEDGED`/결정적 `fiuAckRef`로 닫는다. 이는 데모 전용 transport 동작이며 운영 비동기 규제기관 callback의 성공/실패 계약을 제한하지 않는다.

### 3.7 ApprovalDto (Admin, DB `aml_approvals`)

| 필드 | 타입 | 설명 |
|---|---|---|
| `approvalId` | string(uuid) | PK |
| `subjectType` | enum | 엔진 결재 대상 **21종**: `WLF_DECISION`/`FP_WHITELIST`/`RA_MODEL`/`TM_SCENARIO`/`RISK_OVERRIDE`/`EDD_CLOSE`/`STR_SUBMIT`/`CTR_SUBMIT`/`WATCHLIST_IMPORT`/`COUNTRY_RISK`/`POLICY_PACK`/`SECRET_CHANGE`/`RELATIONSHIP_REJECT`/`CHECKLIST_CHANGE`/`PERIODIC_REVIEW_CHANGE`/`IRA_SUBMIT`/`HIGH_RISK_REGISTRY`/`PEP_APPROVAL`/`CTR_THRESHOLD`/`HRR_REGISTRATION`/`REPORT_RULE_PARAM`. `REPORT_RULE_PARAM`은 룰 코드가 subjectRef이고 승인선 `COMPLIANCE_MANAGER`; `tenant\|ruleCode\|afterPairs\|beforePairs` staged payload를 checker 실행 때 검증·적용한다. 나머지 상세는 DB §5.16 정본 |
| `subjectRef` | string | 대상(case_id/report_id 등) |
| `approvalLine` | enum | §5.12 approval_line |
| `status` | enum | §5.13 approval_status **7종(API 노출, `DRAFT` 제외)**: `SUBMITTED`/`APPROVED`/`REJECTED`/`CANCELLED`/`EXPIRED`/`EXECUTED`/`EXECUTION_FAILED`. `DRAFT`는 내부 엔진 전이 상태로 외부 미노출(§1.5) |
| `makerId` | string | 상신자 |
| `checkerId` | string | 승인자 (**maker≠checker**). 응답은 서버 파생 실제 승인자, 요청에서는 인증 principal과 일치할 때만 허용되는 optional 호환 assertion |
| `payloadHash` | string | 고정 hash(변경 시 무효화) |
| `reason` | string | 사유 |
| `stagedPayload` | string\|null | **상신 시점 고정 canonical payload**(상세 전용, DB §3.16 `staged_payload`). 결재함 **상신 내용·변경 전→후(as-is/to-be) 파생 소스** — masked/tokenized only(원문 PII 미저장 §19.2). `null`=live 파생 subject/legacy(run3 D13) |
| `detail` | string\|null | 결재 상세 상신 내용 요약. `CTR_THRESHOLD`는 `<currency> CTR 임계 변경 상신` 형태로 파생한다. |
| `changes` | array\|null | 결재 상세 변경 전→후 표. 원소 `{ label, before, after }`. `CTR_THRESHOLD`는 `tenant\|currency\|toAmount\|reason\|fromAmount`, `REPORT_RULE_PARAM`은 `tenant\|ruleCode\|afterPairs\|beforePairs` staged payload에서 AS-IS/TO-BE를 파생한다. |
| `submittedAt` | string(date-time)\|null | **상신일시**(DB §3.16 `created_at` 매핑, 신규 컬럼 없음·가정 G5). 결재함 정렬(desc) 기준. `null`=live 파생 subject(run3 D13) |
| `expiresAt` / `executedAt` | string(date-time) | 만료·실행(결재≠실행 분리). `expiresAt`=결재함 만료 임박 뱃지 원천(`null`=무기한, run3 D13) |

> **결재함 위임(엔진) 응답 parity(run3 D13, 코드=truth).** 엔진 `ApprovalController.{ApprovalSummary,ApprovalDetail}` 가 `submittedAt`(=`created_at`)·`expiresAt`·`stagedPayload`(Detail)를 응답하도록 결선해 위임 경로에서 상신일시·만료·변경내역·상신내용이 전부 `null` 로 내려와 정렬·만료 뱃지·변경 전후 표가 무력화되던 결함을 해소한다. stub↔엔진 위임 응답 모양 동형(불변식).

승인 `ApprovalDecisionRequest`는 `{ checkerId?, reason? }`, 반려 `ApprovalRejectRequest`는 `{ checkerId?, reason }`다. 액션은 각각 `:approve`/`:reject` 경로가 결정하며 body `decision` 필드는 없다. `checkerId`는 legacy 호환용 assertion일 뿐 신원 정본이 아니며, 서버는 인증 principal에서 checker를 파생하고 nonblank body 값이 principal과 다르면 요청을 거부한다. 인증 checker가 maker와 같으면 body 위조 여부와 무관하게 `409 AML.SELF_APPROVAL_FORBIDDEN`.

### 3.8 EvidenceExportRequest → `POST /api/v1/evidence/aml/exports` (DB `aml_evidence_exports`, UseCase: `ExportEvidenceUseCase`)

> **UseCase 명칭 정본**: 본 API §3.8·§2.5의 `ExportEvidence`(→ `ExportEvidenceUseCase`)가 기준이다. SW 설계서 §6.2 교정 완료 — `ExportEvidenceUseCase`로 정합됨(2026-06-08 QA 이격 해소).

| 필드 | 타입 | R | 설명 |
|---|---|---|---|
| `exportType` | enum | R | `CDD_EDD`/`WLF_REGISTER`/`RA_REPORT`/`TM_HISTORY`/`STR_EVIDENCE`/`CTR_EVIDENCE`/`WATCHLIST_CHANGE`/`VENDOR_CROSSREF`/`PII_ACCESS` |
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
| `nationality` | string\|null | CDD에서 보존한 PII-safe ISO 국적 코드 |
| `country` | string\|null | 고객 원장의 ISO 국가 코드 |
| `onboardingAt` | string(date-time)\|null | AML 고객 원장 최초 온보딩 시각 |
| `registeredAt` | string(date-time)\|null | 소스 시스템 등록 시각(CDD canonical projection) |
| `birthYearMasked` | string\|null | 안전하게 영속된 마스킹 생년만 허용. 현 canonical projection에 정본이 없으면 null이며 raw vault 값으로 합성하지 않음 |
| `isPep` | boolean | **PEP(정치적 주요인물) 여부**(DB `aml_customers.is_pep`, V24). 경영진 승인(`PEP_APPROVAL`) EXECUTED 시 TRUE. TRUE면 `riskGrade`=HIGH 강제 상향(거래 허용+EDD) |
| `pepApprovalStatus` | enum\|null | 진행 중/확정 `PEP_APPROVAL` 결재 상태(`SUBMITTED`/`EXECUTED`/`REJECTED`, 미상신=null). 결재함(§3.7 ApprovalDto)에서 파생 |
| `pepApprovalId` | string(uuid)\|null | PEP 확정 결재 증거 링크(DB `aml_customers.pep_approval_id`, 마스킹 불요·식별 PII 아님). 비-PEP은 null |
| `latestScreening` | object | 최신 screening 결과 요약(`screeningId·status·riskGrade`) |
| `latestRiskScore` | object | 최신 RA 결과 요약(`scoreId·riskScore·riskGrade·evaluatedAt`) |
| `createdAt` | string(date-time) | |

> raw PII(이름·주민번호·여권번호 원문) 미노출. 식별은 `customerRef`(토큰), 매칭 보조는 `*Hash`만(DB §2.2). PII 원문 접근은 `aml:pii:reveal` scope+감사 필요(§1.6).
>
> **bo-api 화면 aggregate `CustomerProfile.riskSummary.mandatoryHighRisk`(당연고위험) 파생(run5 #3).** 위 엔진 evidence `CustomerProfileDto` 는 mandatory(당연고위험 강제 상향) 필드를 싣지 않는다. bo-api 프로필 화면 aggregate(`GET /api/v1/bo/aml/customers/{ref}/profile`)는 동일 위임 컨텍스트의 RA read(`GET /aml/customers/{ref}/risk` → `RiskScoreResponse.{mandatoryHighRisk, mandatoryHighRiskReasons, forcedFloorEvidence}`, §3.3)를 재사용해 `riskSummary.mandatoryHighRisk`(**boolean\|null**) 를 합성한다 — `isPep=true` 면 사유에 `PEP` 포함, RA read 실패 시 `null`(미상, `false` 단정 금지). stub(비운영) 경로는 RA stub 을 단일 소스로 하여 프로필 등급·사유·재확인주기가 RA 상세(§3.3)와 일치한다(PEP 승인·RISK_OVERRIDE 폐루프 양 read 동형, run5 #4).
>
> **bo-api 화면 aggregate `CustomerProfile.riskSummary.riskGrade` 등급 폴백 체인(코드=truth, `AmlCustomerProfileService#resolveGrade`, v9.46).** bo-api 프로필 화면 aggregate 의 `riskSummary.riskGrade` 는 엔진 profile 의 top-level `riskGrade`(위 표 §CustomerProfileDto `riskGrade`) 를 그대로 쓰지 않고 **폴백 체인 — ① top-level `riskGrade` → ② `latestRiskScore.riskGrade`(§CustomerProfileDto `latestRiskScore` 요약) → ③ `LOW`** 로 해소한다. 엔진 evidence profile 이 top-level `riskGrade` 를 **null/blank 로 내리는 계약**(실측)이라 top-level 만 매핑하면 등급이 `LOW` 로 기본값 처리되는 반면 `riskScore` 는 `latestRiskScore.riskScore`(예 `85.39`)를 그대로 써서, `riskSummary` 가 `(riskGrade=LOW, riskScore=85.39)` 로 **모순**되던 결함이 있었다(같은 회원의 `GET .../risk`(§3.3)는 HIGH). 폴백은 top-level 부재 시 **최신 RA 점수 행의 등급으로 내려가** `riskScore`↔`riskGrade` 두 필드를 **동일 소스(최신 RA 점수 행)에 정렬**한다. **① top-level·② latest 가 둘 다 부재(null/blank)할 때만** 최종 `LOW` 기본값을 쓴다(상위 요구서 미정의 지점 — **가정 A4로 진행: 코드=truth**). bo-api 는 등급 코드값을 재해석하지 않고 passthrough(FE i18n 라벨) — 폴백은 **소스 선택**일 뿐 vocab 변환이 아니다.

`ActivitySummaryDto`(GET `/evidence/aml/customers/{customerRef}/activity-summary` 응답 — EDD 소득정합성 판단 재료, read-only 수치 집계, raw PII 미노출):

| 필드(엔진 wire) | 타입 | 설명 |
|---|---|---|
| `recentCount` | integer(long) | 최근 30일 거래 건수(전건, 페이지 절단 없음) |
| `recentSumPhp` | number | 최근 30일 거래 합계(PHP-equivalent, frozen `phpEquivalent`) |
| `monthlyAvgPhp` | number | **최근 3개월 월평균 거래액**(업무 확정 20260709 — 관측기간 전 기간 정규화에서 변경) = (최근 90일 창 Σ phpEquivalent) / min(3, 관측월수). 관측 3개월 미만 신규 회원은 관측월수로 나눠 과소평가를 방지한다. **무거래 판정은 전 기간 관측 부재(첫 거래 없음) 기준** — 최근 30일 창 건수(recentCount)가 아니다. 최근 30일 무거래·과거 이력 보유 회원도 90일 창 정규화로 산출(거래 0건이면 `0`). 화면 표기 "최근 3개월 평균" |
| `observedMonths` | integer | 관측월수(첫 거래~asOf 올림, 최소 1; 거래 0건이면 `1`) |
| `currency` | string | 금액 통화(항상 `PHP`) |
| `windowDays` | integer | 최근 집계 창 일수(30) |
| `alertCount` | integer(long) | 대상의 전체 AML 알림 exact count(목록 page/size 절단 없음) |
| `caseCount` | integer(long) | 대상의 전체 케이스 exact count |
| `openCaseCount` | integer(long) | 대상의 비종결 케이스 exact count(`OPEN`·`INVESTIGATING`·`PENDING_APPROVAL`) |
| `screeningCount` | integer(long) | 대상의 스크리닝 결과 exact count |
| `relationshipCount` | integer(long) | `aml_relationships`의 tenant-scoped outbound 관계·UBO edge 수. 거래 상대방 수가 아님 |
| `recentCounterpartyCount` | integer(long) | 최근 30일 canonical 거래의 distinct `counterpartyRef` 수 |
| `degraded` | boolean | 하나 이상의 집계 소스 실패/부분 강등. true이면 수치 0을 실측 0건으로 단정하지 않음 |

> **위임 wire 필드명 정본(코드=truth).** 엔진 응답 필드명은 `recentSumPhp`·`monthlyAvgPhp`(금액에 `Php` 접미)이다. bo-api aggregate(`GET /api/v1/bo/aml/customers/{ref}/profile` → `transactionActivity`)는 이 wire 를 역직렬화하며 record 내부명(`recentSum`·`monthlyAvgAmount`)에 Jackson `@JsonProperty` 별칭(`recentSumPhp`·`monthlyAvgPhp`)을 부여해 매핑한다 — 별칭 미부여 시 두 금액이 null 로 매핑돼 위임 경로 EDD 소득정합성 신호(`incomeMultiple` = 월평균/신고소득 상한)가 상시 무력화된다. `recentCount`·`observedMonths`·`currency`·`alertCount`·`caseCount`·`openCaseCount` 는 wire·record 필드명이 동일.

`SourceSystemDto`: `{ sourceSystem, ingestMode(§5.14), schemaVersion, authMode(API_KEY_HMAC/OAUTH2/MTLS), failurePolicy(MANUAL_REVIEW/FAIL_CLOSED/DELAY_ALLOWED), status(enum 2종: `ACTIVE`/`DISABLED` — DB §3.2 `aml_source_systems.status` 정본), enabled, createdAt(date-time), updatedAt(date-time) }`. `secretRef`는 응답에서 마스킹.

### 3.10 FdsEscalationRequest → `POST /internal/v1/aml/fds-escalations` (DB `aml_alerts`)

| 필드 | 타입 | R | 설명 |
|---|---|---|---|
| `eventId` | string | — | FDS handoff event/idempotency key. 미제공 시 `fraudCaseRef`로 fallback |
| `fraudCaseRef` | string | R | fds-svc case 식별자 |
| `fdsCaseRef` | string | — | `fraudCaseRef`와 동일 cross-ref를 담는 큐 호환 alias |
| `targetRef` | string | R | 고객/법인 ref |
| `transactionRef` | string | — | 관련 거래 |
| `severity` | enum | R | `LOW`/`MEDIUM`/`HIGH`/`CRITICAL` |
| `suggestedCaseType` | enum | — | 기본 `STR_REVIEW`(§14.2) |
| `action` | enum | — | FDS handoff action verb(`OPEN_AML_CASE`/`REGULATORY_REPORT`). `OPEN_AML_CASE`는 EDD review로 라우팅 |
| `dataScope` | string | — | FDS `workspaceId`에서 변환된 AML data-scope |
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
| `country` | string | ISO 3166-1 alpha-2 국가코드(신규/변경 입력은 실제 코드만 허용) |
| `riskBand` | enum | `LOW`/`MEDIUM`/`HIGH`/`PROHIBITED`(국가위험 등급, RA 등급 §5.2와 동일 축) |
| `basis` | array<string> | 근거(FATF blacklist/greylist·EU 고위험·제재·고위험 corridor 등). 자동 수집분은 `FATF_BLACKLIST`/`FATF_GREYLIST`(FATF, `FatfGradeMapping`) 또는 `EU_HIGH_RISK_THIRD_COUNTRY`(EU 집행위, 기본) |
| `version` | string | 정책 버전 레이블(VARCHAR(80) — 자동 수집분은 canonical SHA-256 파생: `eu-<hash>`/`fatf-<hash>`) |
| `status` | enum | `DRAFT`/`ACTIVE`/`SUPERSEDED`(버전 상태, DB §3.22c) |
| `effectiveFrom` | string(date-time) | 적용 시점 |
| `provenance` | enum | **(V16·V18)** `MANUAL`(수동 4-eyes 오버라이드 — 우선, 자동 수집이 덮지 않음)/`FATF_DAILY`(FATF 자동 수집)/`EU_COMMISSION`(EU 집행위 자동 수집 — 기본 제공자, V18). 시스템 provenance 는 결재 없이 즉시 ACTIVE. enum `CountryRiskProvenance` 1:1 |
| `sourceUrl` | string | **(V16)** 자동 수집분의 원천 URL(EU 고위험 제3국 URL / FATF 공개 목록 URL). 수동 행 null |
| `asOf` | string(date-time) | **(V16)** 소스 관측 시점. 수동 행 null |

`CountryRiskChangeRequest`(🔒4-eyes, `POST .../country-risk:change`): `{ changes: [ { country, riskBand, basis[] } ], reason }` → §3.7 `subjectType=COUNTRY_RISK` 결재 상신. `country`는 실제 ISO 3166-1 alpha-2만 허용하고 batch 내 중복·동일 국가 live pending을 거부한다. `basis` 원소는 null을 허용하지 않고 `reason`은 trim 후 필수·최대 512자(고객 PII 입력 금지)다. maker는 client body가 아니라 bo-api `BackofficePrincipal.email` → trusted `X-User-Subject`로 파생되며 legacy `makerId` 입력은 무시한다. 엔진 응답은 `{ approvalId, status: SUBMITTED }`이고 BFF는 body·nonblank `approvalId`·정확한 상태를 모두 확인한 뒤 동일 식별자/상태와 BFF 감사 digest(`payloadHash`, nullable)를 제공한다. 불완전 응답은 202를 합성하지 않는다. 실제 엔진 approval payload hash는 국가/version뿐 아니라 `riskBand`·정렬된 `basis` 전체를 고정하며 승인 시 advisory lock 아래 live payload를 재계산한다. 실행(EXECUTED) 후 변경 국가를 국적/거주국으로 가진 고객별 최신 수신 CDD **동일 이벤트 snapshot**으로 ACTIVE ONBOARDING 모델을 재평가해 새 `aml_risk_scores`를 append한다. batch는 ACTIVE ONBOARDING modelCode+version을 한 번 pin하고, 각 target lock 뒤 최신 projection-complete eventId와 국가를 재검증해 후보 이후 다른 국가로 이동한 옛 snapshot을 skip한다. 강제 경로는 원 CDD idempotency key의 기존 WLF 결과만 읽고 신규 screening/usage 독립 쓰기를 만들지 않는다. 기존 결과 부재 또는 재평가 실패는 정책 전환·승인 상태·RA append와 함께 rollback된다. DB에 남은 과거 3자리 코드는 persistence/기존 pending 조회 전용 legacy로만 rehydrate하며 신규 상신·canonical CDD lookup에는 사용할 수 없다.

`CountryRiskImportStatusDto`(GET `.../country-risk/import-status` — 국가위험 일일 수집 상태 패널): `{ sourceCode("FATF_DAILY"), provider(활성 feed 제공자 — `EU_COMMISSION` 기본/`FATF` 대안), status(ACTIVE|DISABLED), blackUrl(소스 URL — provenance; **EU 제공자에선 null**, FATF 는 Call-for-Action URL), greyUrl(소스 URL — provenance; **EU 제공자에선 단일 고위험 제3국 URL**, FATF 는 Increased-Monitoring URL), activeVersion(현재 적용 canonical SHA-256 — 첫 적용 전 null), lastImportedAt, lastCheckedAt, lastStatus(APPLIED|SKIPPED_UNCHANGED|FAILED — 시도 전 null), lastError, recentRuns: CountryRiskImportRunDto[](최근 10건) }` — DB §3.22c `aml_country_risk_sources` + `aml_country_risk_import_runs` 1:1. **소스 URL 계약: EU 단일 목록은 `greyUrl` 에 단일 URL·`blackUrl` null(FE 는 `provider` 로 소스 표기 분기), FATF 는 black/grey 쌍**. `provider`/`blackUrl`/`greyUrl` 은 활성 feed 값(`CountryRiskFeedPort.provider()/blackUrl()/greyUrl()`, 라이브 feed 제공자를 소스 메타 라벨보다 우선 표기). `CountryRiskImportRunDto` = `{ runId, sourceCode, startedAt, finishedAt, status, version, added[], upgraded[], downgraded[], delisted[], suppressedManual[], error }`(run diff — ISO 코드 목록: 신규/상향/하향/이탈/수동보존. `runId`/`sourceCode` 로 상태 패널 행 식별).

`CountryRiskImportResultDto`(POST `.../country-risk:import` — 수동 트리거 동기 실행 결과, 엔진 `SyncResult` 1:1): `{ status(APPLIED|SKIPPED_UNCHANGED|FAILED), version, added[], upgraded[], downgraded[], delisted[](이번 run 에 활성 제공자 목록에서 이탈한 ISO — 동일 제공자 provenance ACTIVE 만 supersede), suppressedManual[](MANUAL 오버라이드 우선으로 건너뛴 ISO, 가정 A8), error(FAILED 시 fail-safe 사유 — 기존 등급 유지) }`(엔진 SyncResult 는 `sourceCode`/`importedAt` 미포함).

> bo-api 위임 계약(`GET/POST /api/v1/bo/aml/country-risk*`, `CountryRiskDtos`, 필드 단위 1:1 — QA 런 10 H-1): 등급표 행(`CountryRiskEntry`)은 엔진 `CountryRiskDto` 를 그대로 통과하되(`version` string→FE int 파생(`v7`→7·`fatf-<hash>`→0)·`policyPackCode` 는 bo-api 프레젠테이션 기본값), null body나 알 수 없는/빈 `riskBand`를 빈 표/LOW로 축소하지 않고 fail-closed한다. import-status/import 응답의 run diff 는 **엔진과 동일한 ISO 코드 목록(added/upgraded/downgraded/delisted/suppressedManual: string[])** 을 그대로 통과해 화면이 국가 목록 pill 을 렌더한다(카운트 손실 없음). import-status 는 소스 URL(blackUrl/greyUrl)을 병기하며, import 결과의 `sourceCode`/`importedAt` 은 엔진 SyncResult 에 없어 bo-api 가 요청 맥락(FATF_DAILY·응답 시각)으로 채운다. 수동 트리거는 `COUNTRY_RISK_IMPORT_TRIGGERED` 감사 이벤트(bo V8)를 남긴다.

### 3.13 PolicyPackChangeRequest (Admin, `aml_tenants.policy_pack_code`)

`PolicyPackChangeRequest`(🔒4-eyes, `POST .../policy-packs:change`):

| 필드 | 타입 | R | 설명 |
|---|---|---|---|
| `policyPackCode` | string | R | 대상 pack(`KR_DEFAULT` 등, DB `aml_tenants.policy_pack_code`) |
| `parameters` | object | R | STR/CTR 기준금액·보고 대상·임계치(effective version 관리, 설계서 §14.3) |
| `effectiveFrom` | string(date-time) | — | **호출자 지정 미지원(반드시 생략/null)**. 예약·소급 활성화는 구현하지 않으며 non-null은 400. 실제 `effective_from`은 checker 승인 EXECUTED 시각을 서버가 기록 |
| `reason` | string | R | 변경 사유(감사) |
| `makerId` | string | R | 상신자 |

→ §3.7 `subjectType=POLICY_PACK` 결재 상신. 응답 `{ approvalId, status: SUBMITTED }`. active row lock 아래 pack당 DRAFT 1건만 허용하며 실행 시 tenant policy pack effective version을 갱신한다. 반려 시 후보 artifact는 `REJECTED`로 종결되고 다음 상신은 전체 version 이력의 최대 번호 다음을 사용한다.

### 3.14 (제거됨 — Travel Rule 전면 제거, 2026-07-09, aml V31·bo-api V14)

> 구 `TravelRuleTransferDto` / travel-rule 필터·exception 큐 DTO. Travel Rule 기능 전면 제거(코드=truth, aegis-aml `feature/remove-travel-rule`)로 `aml_travel_rule_transfers` 테이블·`TravelRuleTransferDto`·`CompletenessStatus`·`TravelRuleRiskStatus` enum이 삭제됐다. 섹션 번호는 타 문서 § 참조 보존을 위해 유지한다.

### 3.15 SimulationResponse (Admin, RA/TM simulate 응답)

RA `POST .../ra-models/{modelCode}/simulate`·TM `POST .../tm-scenarios/{scenarioCode}/simulate`의 분석 결과. RA 결과는 activation 증거이므로 영속하지만 실행 자체는 **분석 설정이며 결재·실제 등급 변경이 없다**(설계서 §13.5). RA에는 확정 label이 없으므로 근거 없는 오탐률 0%를 합성하지 않고 등급 이동·설정 diff·운영 영향만 제공한다.

| 필드 | 타입 | 설명 |
|---|---|---|
| `simulationId` | string(uuid) | 시뮬레이션 실행 식별자(감사·재현) |
| `modelCode` / `version` / `scenarioVersion` | string | 대상 모델/시나리오와 버전(RA는 `modelCode`·`version`) |
| `scenario` | enum\|null | RA만: `ONBOARDING\|ONGOING` |
| `definitionHash` | string\|null | RA candidate 전체 canonical 정의 hash. 저장 후 정의 변경 시 기존 결과는 activation에 사용할 수 없다. |
| `baselineVersion` / `baselineDefinitionHash` | string\|null | 같은 scenario에서 현재 실제 적용되는 ACTIVE 기준선 |
| `samplePopulation` | enum | RA 모집단 `RECENT_90D_NEW\|ALL_ACTIVE\|HIGH_RISK_ONLY` |
| `sampleSize` | integer | 선택된 tenant·scenario 표본 수(최대 500) |
| `gradeDistribution` | object\|null | RA candidate `{ LOW, MEDIUM, HIGH, PROHIBITED }` 건수. 합계는 `operationalImpact.evaluatedCount`; ONGOING 표본 중 적용 trigger가 없는 행은 평가에서 제외될 수 있어 `evaluatedCount <= samplePopulation.sampleSize`다. |
| `gradeShift` | object | 등급 이동 추정 `{ LOW(integer), MEDIUM, HIGH, PROHIBITED }`(부호 있는 증감 = 후보 분포 − 기준 분포, PRD '높음 +142 / 중간 -88 / 낮음 -54') |
| `baselineDistribution` | object\|null | **활성 버전 기준 분포**(증감 `gradeShift` 의 기준선) `{ LOW(long), MEDIUM, HIGH, PROHIBITED }`. 표본 부재 시 생략(nullable, #4) |
| `configurationChanges` | array\|null | RA만: baseline 대비 가중치·임계·parameter 변경 경로와 전/후 값(비PII) |
| `operationalImpact` | object\|null | RA만: `{ evaluatedCount, gradeChangedCount, reviewShortenedCount, eddCandidateCount }`. 실제 고객 상태를 변경하지 않는다. |
| `period` | object\|null | 실제 replay 입력 기간 `{ from, to }`. 표본 0이면 두 값 nullable |
| `falsePositiveImpact` | object\|null | TM 등 확정 label 근거가 있는 경우만 제공. RA는 미산출(nullable — 0% 오표시 금지). |
| `evaluatedAt` | string(date-time) | 실행 시각 |

> **RA simulate 요청 `RaSimulateRequest` = `{ version, samplePopulation }`.** 구 `factorWeightOverrides`와 호출자 제공 factor sample은 엔진 미소비/표본 왜곡 경로이므로 제거한다. 엔진이 tenant·scenario별 실제 입력을 선택·재생하고 `aml_ra_model_simulations`에 결과를 남긴다. bo-api는 이를 손실 없이 전달하며 엔진 미연결 write/simulate는 503 `AML.ENGINE_UNAVAILABLE`로 fail-closed한다.

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
| `requestedBy` | string | — | legacy 요청 운영자 assertion(최대 120자). 생략 가능하며 존재하면 인증된 `BackofficePrincipal.email`과 trim·대소문자 무시 기준으로 같아야 한다. persisted onboarding actor의 정본은 session principal |

응답: `202 Accepted` + `{ tenantId, onboardingStatus: "PROVISIONING", infraRef: null, requestedAt }`. `MANAGED_DEDICATED`만 허용 — 다른 deploymentModel이면 `422 AML.ONBOARDING_PROVISION_NOT_APPLICABLE`.

**`OnboardingRegisterRequest`** (POST `/api/v1/bo/aml/tenants/{tenantId}/onboarding/register` — self-hosted 등록 콜백):

| 필드 | 타입 | R | 설명 |
|---|---|---|---|
| `instanceId` | string | R | 고객 인스턴스 식별자(설치 후 생성, DB `infra_ref` 매핑) |
| `registrationToken` | string | R | 플랫폼 발급 등록 토큰(서명·검증 방식은 P8 인프라 설계 확정·오픈결정) |
| `callbackEndpoint` | string | — | self-hosted 인스턴스 헬스 콜백 URL |

응답: `200 OK` + `{ tenantId, onboardingStatus: "REGISTERED", infraRef: "<instanceId>" }`. `SELF_HOSTED`만 허용 — 다른 deploymentModel이면 `422 AML.ONBOARDING_REGISTER_NOT_APPLICABLE`. `registrationToken` 불일치 시 `401 AML.INVALID_REGISTRATION_TOKEN`.

> provision/register 상태 이력의 actor는 모두 인증된 BO principal에서 파생한다. `requestedBy`는 provision의 일치 assertion일 뿐이고, register의 `instanceId`는 `infraRef`이지 actor가 아니다. assertion 위조는 상태 전이·이력 append 전에 400으로 거부한다.

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

> **externalSignals 블록(코드=truth, feature/aml-tm-phase7-ingest-parity — FDS 인입 계약 패리티, 전부 선택·비-PII).** FDS `IngestEventRequest.externalSignals`(fds-api §5.1 v4.13)와 동형의 외부 인텔리전스 pass-through 블록을 중립 인입 Envelope 최상위에 수용한다: `trade{invoiceUnitPriceDeviation(decimal), documentMismatch/highRiskCorridor/splitPaymentPattern(boolean)}` · `seller{riskGrade(string≤64), bankAccountMismatch(boolean)}` · `settlement{accelerationRequest(boolean)}` · `vendor{bankAccountRecentlyChanged, approverRoleMismatch(boolean)}` · `crypto{addressRisk/mixerExposure/depositWithdrawalLatency(decimal), newAddressWithdrawal/apiKeyFirstUse(boolean)}` · `market{manipulationPattern(decimal)}` · `employee{role(string≤64), overrideCount(decimal), approvalBypass/highValueAccess(boolean)}`. 문자열 필드는 64자 초과·제어문자 시 REJECTED(422, `NeutralEventValidator`). 수신 값은 flat canonical payload 의 `externalSignals` 서브트리(비-null 만)로 기록되고 `EvaluateCommand.ExternalSignals` 로 현재 이벤트 평가에 전달되어, **설정형 CTR/STR 룰**(§2.2 configurable-report-rules)의 피처 스냅샷에 FDS 와 동일한 19키(`trade.*`·`seller.*`·`settlement.accelerationRequest`·`vendor.bankAccountRecentlyChanged`·`invoice.approverRoleMismatch`·`crypto.*`·`market.manipulationPattern`·`employee.*`)로 노출된다(`ConfigurableRuleDslPolicy` 허용 스칼라 등재, 부재 시 미노출 fail-safe). 법정 카탈로그 룰(CTR 2·STR 8)은 불변 — 신규 신호는 설정형 룰로 소비한다. 커머스 3블록(order/settlement/document 투영)은 AML 미적용(5-product 폐쇄 계약, FDS 소관).

---

## 4. 표준 에러 모델

Controller/domain 오류는 `{ "error": { "code", "message", "details": "...", "timestamp": "..." } }` envelope를
사용한다. Controller보다 앞에서 종결하는 공통 machine-auth filter 오류는
`{ "code", "status", "detail" }` flat JSON이며 `AML-AUTH-*`/`AML-AUTHZ-*` code를 사용한다.
`ScopeGuard`/`RoleGuard` 같은 controller advice 오류는 전자 envelope와 `AML.<UPPER_SNAKE>` 또는
`AML-AUTHZ-*` code를 따른다. 클라이언트는 HTTP status와 code를 기준으로 처리하고 인증 detail을
원인 oracle로 해석하지 않는다.

| HTTP | code | 발생 |
|---|---|---|
| 400 | `AML.BAD_REQUEST` | 스키마 검증 실패(필수 누락·타입·enum 위반) |
| 400 | `AML.UNKNOWN_SOURCE_SYSTEM` | 미등록 `Source-System` |
| 401 | `AML-AUTH-001` | 공통 machine-auth 대상 경로에서 `Tenant-Id` 또는 `X-Api-Key` 누락 |
| 401 | `AML.UNAUTHENTICATED` | legacy application-layer 인증 실패 alias. 공통 machine-auth filter는 `AML-AUTH-001/002` 사용 |
| 401 | `AML.INVALID_SIGNATURE` | legacy application-layer alias. 공통 machine-auth filter는 상세 원인을 노출하지 않고 아래 `AML-AUTH-002` 사용 |
| 401 | `AML-AUTH-002` | generic machine-auth 실패(credential/protocol/version/nonce/timestamp/canonical/signature/replay 원인 비공개) |
| 503 | `AML-AUTH-003` | nonce replay store 불가 — 인증 fail-closed |
| 413 | `AML-AUTH-004` | 인증 raw-body 상한 초과 |
| 403 | `AML-AUTHZ-002` | scope 부족 또는 `ScopeGuard` request attribute 부재. 공통 local-bootstrap `Boolean.TRUE` marker만 예외 |
| 403 | `AML.FORBIDDEN_SCOPE` | COMPLIANCE 같은 dedicated role 부족 또는 `RoleGuard` authority attribute 부재. 같은 bootstrap marker만 예외 |
| 403 | `AML.TENANT_MISMATCH` | tenant/data-scope 경계 위반(RLS) |
| 404 | `AML.SCREENING_NOT_FOUND` / `AML.CASE_NOT_FOUND` / `AML.REPORT_NOT_FOUND` / `AML.APPROVAL_NOT_FOUND` | 리소스 없음 |
| 409 | `AML.IDEMPOTENCY_CONFLICT` | 동일 키 다른 payload |
| 409 | `AML.SELF_APPROVAL_FORBIDDEN` | maker==checker(4-eyes 위반) |
| 409 | `AML.APPROVAL_PAYLOAD_CHANGED` | 결재 후 payload_hash 불일치(무효화) |
| 409 | `AML.INVALID_STATE_TRANSITION` | case/report/approval 상태 전이 위반 |
| 409 | `AML.EXPORT_TAMPER` | **evidence artifact 무결성 위반(P0-12, `ExportTamperException`)** — 다운로드 시 저장 bytes 의 재계산 `object_checksum` 이 고정값과 불일치하거나 `manifest_hash` 가 부재. 서버가 이미 `EXPORT_TAMPER` 감사(§DB 5 audit_event_category)를 기록한 뒤 차단하며, detail 은 불투명(bytes/hash 미노출) |
| 422 | `AML.SCREENING_REQUIRES_REVIEW` | screening 장애 시 manual-review/fail-closed(§15.7, D-14) |
| 429 | `AML.RATE_LIMITED` | metering/quota 초과(§15.7) |
| 503 | `AML.IDEMPOTENCY_PROCESSING` | 동일 키 처리 중(`Retry-After`) |
| 503 | `AML.SCREENING_UNAVAILABLE` | WLF 엔진 장애·PII reveal 역참조 실패·**필수 source readiness 미충족(P0-06, fail-closed 게이트)**. readiness 미충족 시 `details` 에 사유코드(`NO_MANDATORY_POLICY`/`NO_READY_SOURCE`/`MISSING_SOURCE`/`NOT_READY`/`STALE`/`FAILED`/`NOT_APPLICABLE_UNAPPROVED`, §2.2) — `NO_MATCH` 미탐 대신 fail-closed |
| 409 | `AML.TENANT_DEPLOYMENT_MODEL_IMMUTABLE` | `deploymentModel` 직접 PUT 변경 시도(온보딩 흐름만 허용) |
| 404 | `AML.TENANT_NOT_FOUND` | 대상 tenant 없음(§5 OpenAPI paths·PRD 부록 D 정합) |
| 422 | `AML.TENANT_POLICY_UNBOUND` | **테넌트 관할·통화·Policy Pack revision 바인딩 누락/충돌(P0-16, `TenantPolicyUnboundException`)** — jurisdiction/base_currency/reporting_currency/policy_pack_code/policy_pack_version 미설정, 핀 Policy Pack revision 미존재, 또는 비-effective(비-ACTIVE·effective_from 미도달) revision. 중립 인입(`POST /aml/v1/transaction-events`)·policy-binding upsert(§2.7)에서 fail-closed — 구 service-global PH/PHP 기본으로 조용히 오귀속(오보고·미탐)하지 않고 거부한다 |
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
            aml:internal:fds-escalation:write: FDS escalation internal write only
    Mtls: { type: mutualTLS }
  parameters:
    TenantId: { name: Tenant-Id, in: header, required: true, schema: { type: string } }
    SourceSystem: { name: Source-System, in: header, required: true, schema: { type: string } }
    IdempotencyKey: { name: Idempotency-Key, in: header, required: true, schema: { type: string } }
    Signature: { name: X-Signature, in: header, required: true, schema: { type: string } }
    AuthVersion: { name: X-Auth-Version, in: header, required: true, schema: { type: string, const: '2' } }
    Nonce: { name: X-Nonce, in: header, required: true, schema: { type: string, pattern: '^[A-Za-z0-9_-]{22}$' } }
    Timestamp: { name: X-Timestamp, in: header, required: true, schema: { type: string, format: date-time } }
    TraceId: { name: X-Trace-Id, in: header, required: false, schema: { type: string, maxLength: 64 } }
    UserSubject:
      name: X-User-Subject
      in: header
      required: true
      description: trusted BFF/mesh가 인증 principal에서 파생하고 요청 HMAC에 결합하는 actor. 브라우저 임의 입력·서명 뒤 교체 금지.
      schema: { type: string }
    DataScope: { name: X-Data-Scope, in: header, required: false, schema: { type: string, maxLength: 128 } }
    InternalService: { name: X-Internal-Service, in: header, required: true, schema: { type: string, enum: [fds-svc, bo-api] } }
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
    FdsEscalationRequest:
      type: object
      required: [fraudCaseRef, targetRef, severity]
      properties:
        eventId: { type: string, nullable: true, description: absent이면 fraudCaseRef로 업무 멱등 fallback }
        fraudCaseRef: { type: string }
        fdsCaseRef: { type: string, nullable: true }
        targetRef: { type: string }
        transactionRef: { type: string, nullable: true }
        severity: { type: string, enum: [LOW, MEDIUM, HIGH, CRITICAL] }
        suggestedCaseType: { type: string, nullable: true }
        action: { type: string, nullable: true }
        dataScope: { type: string, nullable: true }
        evidence: { type: object, additionalProperties: true, nullable: true }
    FdsEscalationResponse:
      type: object
      required: [alertId, accepted]
      properties:
        alertId: { type: string, format: uuid }
        accepted: { type: boolean }
    PageMeta:
      type: object
      properties:
        page: { type: integer }
        size: { type: integer }
        totalElements: { type: integer, format: int64 }
        totalPages: { type: integer }
        sort: { type: string }
    ScreenRequest:  # code truth: ScreeningController.ScreenRequest (flat, no nested subject / no sourceTypes)
      type: object
      required: [targetRef, targetType]   # + Idempotency-Key 헤더
      properties:
        targetRef: { type: string, description: 'sender=member token(CUSTOMER) / receiver=이름+국가+전화 token(COUNTERPARTY)' }
        targetType: { type: string, enum: [CUSTOMER, ENTITY, COUNTERPARTY, CRYPTO_ADDRESS] }
        nameHash: { type: string }
        nameTokens: { type: array, items: { type: string } }
        dob: { type: string, format: date }
        country: { type: string }
        documentHash: { type: string }
        walletAddressHash: { type: string }
        addressTokens: { type: array, items: { type: string } }
        relationshipRefs: { type: array, items: { type: string } }
        transactionRef: { type: string, description: '해외송금 거래번호 token — 동일 거래 sender·receiver screening 연결(§13)' }
    ScreeningResponse:  # code truth: ScreeningController.ScreeningResponse
      type: object
      properties:
        screeningId: { type: string, format: uuid }
        tenantId: { type: string }
        targetRef: { type: string }
        transactionRef: { type: string, nullable: true }
        targetType: { type: string, enum: [CUSTOMER, ENTITY, COUNTERPARTY, CRYPTO_ADDRESS] }
        status: { type: string, enum: [NO_MATCH, POSSIBLE_MATCH, TRUE_MATCH, FALSE_POSITIVE, AUTO_DISCOUNTED, ESCALATED] }
        score: { type: number }
        scoreBreakdown: { type: object }
        reasonCodes: { type: array, items: { type: string } }
        matchedEntries: { type: array, items: { type: string } }
        ruleVersion: { type: string }
        appliedPolicy:
          type: object
          nullable: true
          properties:
            profile: { type: string, enum: [SANCTIONS, PEP] }
            configVersion: { type: string }
            ruleVersion: { type: string }
            definitionHash: { type: string }
            reviewThreshold: { type: number }
            highConfidenceThreshold: { type: number }
            confidenceBand: { type: string, enum: [NO_MATCH, REVIEW, HIGH] }
        decidedBy: { type: string, nullable: true }
        decidedAt: { type: string, format: date-time }
        createdAt: { type: string, format: date-time, nullable: true }
        # riskGrade·requiredActions·matchedCandidates·expiresAt 는 bo-api enrichment(§3.2)
    RuleRef:
      type: object
      properties:
        ruleCode: { type: string }
        threshold: { type: number }
        score: { type: number }
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
              ruleCode: { type: string, nullable: true, enum: [CTR_SINGLE, CTR_DAILY, STR_PEP, STR_SANCTION, STR_KYC_INCOME_MISMATCH, STR_STRUCTURED, STR_NO_PURPOSE, STR_THIRD_PARTY, STR_VELOCITY_CASH, STR_MANUAL] }
              severity: { type: string, enum: [LOW, MEDIUM, HIGH, CRITICAL] }
              status: { type: string }
              evidence: { type: object }
    ApprovalDecisionRequest:
      type: object
      properties:
        checkerId: { type: string, description: "인증 principal과 일치해야 하는 호환용 assertion; 서버 파생 checker를 대체하지 못함" }
        reason: { type: string }
    ApprovalRejectRequest:
      type: object
      required: [reason]
      properties:
        checkerId: { type: string, description: "인증 principal과 일치해야 하는 호환용 assertion; 서버 파생 checker를 대체하지 못함" }
        reason: { type: string, minLength: 1 }
    ApprovalSubmittedResponse:
      type: object
      properties:
        approvalId: { type: string, format: uuid }
        status: { type: string, enum: [SUBMITTED] }
    CountryRiskChangeRequest:
      type: object
      description: maker는 body가 아니라 trusted X-User-Subject에서 파생한다.
      required: [changes, reason]
      properties:
        changes:
          type: array
          minItems: 1
          items:
            type: object
            required: [country, riskBand]
            properties:
              country: { type: string, pattern: '^[A-Za-z]{2}$', description: ISO 3166-1 alpha-2 }
              riskBand: { type: string, enum: [LOW, MEDIUM, HIGH, PROHIBITED] }
              basis: { type: array, items: { type: string } }
        reason: { type: string, minLength: 1, maxLength: 512 }
    OnboardingInputValue:
      type: object
      required: [code, customerCount, lastReceivedAt, canonical]
      properties:
        code: { type: string, pattern: '^[A-Z][A-Z0-9_]{0,63}$' }
        customerCount: { type: integer, format: int64, minimum: 1 }
        lastReceivedAt: { type: string, format: date-time }
        canonical: { type: boolean }
    OnboardingInputAxis:
      type: object
      required: [values, ignoredValueCount, truncatedCodeCount]
      properties:
        values:
          type: array
          maxItems: 100
          items: { $ref: '#/components/schemas/OnboardingInputValue' }
        ignoredValueCount:
          type: integer
          format: int64
          minimum: 0
          description: blank/unsafe라 원문을 redaction한 고객 값 수
        truncatedCodeCount:
          type: integer
          format: int64
          minimum: 0
          description: 축별 100개 표시 상한 밖의 정상 distinct code 수
    OnboardingInputCatalog:
      type: object
      required: [windowDays, windowStart, generatedAt, latestCustomerCount, sourceOfFunds, kycLevels, occupations, nationalities, residenceCountries]
      properties:
        windowDays: { type: integer, minimum: 1, maximum: 365, default: 90 }
        windowStart: { type: string, format: date-time }
        generatedAt: { type: string, format: date-time }
        latestCustomerCount: { type: integer, format: int64, minimum: 0 }
        sourceOfFunds: { $ref: '#/components/schemas/OnboardingInputAxis' }
        kycLevels: { $ref: '#/components/schemas/OnboardingInputAxis' }
        occupations: { $ref: '#/components/schemas/OnboardingInputAxis' }
        nationalities: { $ref: '#/components/schemas/OnboardingInputAxis' }
        residenceCountries: { $ref: '#/components/schemas/OnboardingInputAxis' }
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
      properties:
        iacTemplate: { type: string, description: 'IaC 템플릿 버전(기본: 플랫폼 latest)' }
        targetRegion: { type: string, description: '배포 리전 override(기본: tenant region)' }
        requestedBy: { type: string, maxLength: 120, description: 'optional legacy principal consistency assertion' }
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
    EventCategory:
      type: string
      enum:
        - WATCHLIST_IMPORT
        - WLF_DECISION
        - FP_WHITELIST
        - RA_MODEL_CHANGE
        - RA_REVIEW
        - RISK_OVERRIDE
        - TM_SCENARIO_CHANGE
        - CASE_APPROVAL
        - REPORT_LIFECYCLE
        - RAW_DATA_ACCESS
        - POLICY_CHANGE
      description: >
        aml_audit_events.event_category 허용값(11종, DB §3.15 enum 정본).
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
        customerType: { type: string, enum: [PERSON, SOLE_PROPRIETOR, EMPLOYEE] }  # code truth: CustomerType 3종(DB §3.3). 법인은 별도 Entity 모델
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
        modelCode: { type: string, nullable: true }
        version: { type: string, nullable: true }
        modelVersion: { type: string }
        scenarioVersion: { type: string }
        scenario: { type: string, enum: [ONBOARDING, ONGOING], nullable: true }
        definitionHash: { type: string, nullable: true }
        baselineVersion: { type: string, nullable: true }
        baselineDefinitionHash: { type: string, nullable: true }
        samplePopulation:
          oneOf:
            - type: string
              enum: [RECENT_90D_NEW, ALL_ACTIVE, HIGH_RISK_ONLY]
            - type: object
              description: TM simulation population (legacy shared response)
              properties:
                definition: { type: string }
                sampleSize: { type: integer }
                periodFrom: { type: string, format: date-time }
                periodTo: { type: string, format: date-time }
        sampleSize: { type: integer, maximum: 500, nullable: true }
        gradeDistribution:
          type: object
          nullable: true
          additionalProperties: { type: integer }
        gradeShift:
          type: object
          properties:
            LOW: { type: integer }
            MEDIUM: { type: integer }
            HIGH: { type: integer }
            PROHIBITED: { type: integer }
        baselineDistribution:
          type: object
          nullable: true
          properties:
            LOW: { type: integer, format: int64 }
            MEDIUM: { type: integer, format: int64 }
            HIGH: { type: integer, format: int64 }
            PROHIBITED: { type: integer, format: int64 }
        configurationChanges:
          type: array
          nullable: true
          items:
            type: object
            properties:
              path: { type: string }
              before: {}
              after: {}
        operationalImpact:
          type: object
          nullable: true
          properties:
            evaluatedCount: { type: integer, format: int64 }
            gradeChangedCount: { type: integer, format: int64 }
            reviewShortenedCount: { type: integer, format: int64 }
            eddCandidateCount: { type: integer, format: int64 }
        period:
          type: object
          nullable: true
          properties:
            from: { type: string, format: date-time, nullable: true }
            to: { type: string, format: date-time, nullable: true }
        falsePositiveImpact:
          type: object
          nullable: true
          properties:
            deltaPercent: { type: number }
            baseline: { type: number }
            projected: { type: number }
        evaluatedAt: { type: string, format: date-time }
paths:
  /internal/v1/aml/fds-escalations:
    post:
      summary: FDS fraud-case escalation REST fallback
      operationId: acceptFdsEscalation
      security: [ { ApiKeyHmac: [], OAuth2: ['aml:internal:fds-escalation:write'] } ]
      parameters:
        - $ref: '#/components/parameters/TenantId'
        - $ref: '#/components/parameters/AuthVersion'
        - $ref: '#/components/parameters/Nonce'
        - $ref: '#/components/parameters/Timestamp'
        - $ref: '#/components/parameters/Signature'
        - $ref: '#/components/parameters/DataScope'
        - $ref: '#/components/parameters/InternalService'
        - name: Idempotency-Key
          in: header
          required: true
          schema: { type: string }
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/FdsEscalationRequest' }
      responses:
        '202':
          description: created or business-idempotent existing alert accepted
          content:
            application/json:
              schema: { $ref: '#/components/schemas/FdsEscalationResponse' }
        '400': { description: valid signature with wrong caller/dataScope or invalid payload }
        '401': { description: unsigned, invalid signature, target/context/body tamper, or nonce replay }
        '403': { description: valid signature with insufficient endpoint scope }
  /api/v1/aml/screen:
    post:
      summary: 실시간 WLF/제재/PEP screening
      operationId: screenSubject
      security: [ { ApiKeyHmac: [], OAuth2: ['aml:screen:evaluate'] } ]
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
                  data: { $ref: '#/components/schemas/ScreeningResponse' }
        '409': { description: 멱등 충돌, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
        '422': { description: manual-review/fail-closed, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
        '503': { description: WLF 엔진 장애(fail-closed), content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
  /api/v1/admin/aml/screenings/{screeningId}/decision:
    post:
      summary: WLF 판정 (TRUE_MATCH/FALSE_POSITIVE는 4-eyes)
      operationId: decideScreening
      security: [ { OAuth2: ['aml:case:update'] } ]
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
      security: [ { OAuth2: ['aml:admin:approval'] } ]
      parameters:
        - $ref: '#/components/parameters/TenantId'
        - $ref: '#/components/parameters/UserSubject'
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
        '204': { description: 승인 실행 완료 }
        '400': { description: checker identity 불일치/요청 검증 실패, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
        '409':
          description: AML.SELF_APPROVAL_FORBIDDEN / AML.APPROVAL_PAYLOAD_CHANGED
          content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } }
  /api/v1/admin/aml/approvals/{approvalId}:reject:
    post:
      summary: 결재 반려 (maker≠checker 강제)
      operationId: rejectApproval
      security: [ { OAuth2: ['aml:admin:approval'] } ]
      parameters:
        - $ref: '#/components/parameters/TenantId'
        - $ref: '#/components/parameters/UserSubject'
        - name: approvalId
          in: path
          required: true
          schema: { type: string, format: uuid }
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/ApprovalRejectRequest' }
      responses:
        '204': { description: 반려 처리 완료 }
        '400': { description: checker identity 불일치/사유 검증 실패, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
        '409': { description: AML.SELF_APPROVAL_FORBIDDEN / 상태 전이 위반, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
  /api/v1/admin/aml/country-risk:change:
    post:
      summary: 국가위험 변경 상신 (4-eyes, subjectType=COUNTRY_RISK)
      operationId: changeCountryRisk
      security: [ { OAuth2: ['aml:admin:policy'] } ]
      parameters:
        - $ref: '#/components/parameters/TenantId'
        - $ref: '#/components/parameters/UserSubject'
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
              schema: { $ref: '#/components/schemas/ApprovalSubmittedResponse' }
        '403': { description: AML.FORBIDDEN_SCOPE, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
  /api/v1/admin/aml/policy-packs:change:
    post:
      summary: tenant policy pack 변경 상신 (4-eyes, subjectType=POLICY_PACK)
      operationId: changePolicyPack
      security: [ { OAuth2: ['aml:admin:policy'] } ]
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
      security: [ { OAuth2: ['aml:admin:policy'] } ]
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
  /api/v1/admin/aml/ra-models/onboarding-input-catalog:
    get:
      summary: 최근 canonical CDD의 ONBOARDING RA 입력 코드 집계
      operationId: getOnboardingInputCatalog
      security: [ { OAuth2: ['aml:admin:policy'] } ]
      parameters:
        - $ref: '#/components/parameters/TenantId'
        - name: windowDays
          in: query
          required: false
          schema: { type: integer, minimum: 1, maximum: 365, default: 90 }
      responses:
        '200':
          description: tenant별 최근 CDD 고객 최신 1건 기준 aggregate-only 입력 카탈로그
          content:
            application/json:
              schema: { $ref: '#/components/schemas/OnboardingInputCatalog' }
        '400': { description: windowDays 범위 오류, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
        '403': { description: AML.FORBIDDEN_SCOPE, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
  /api/v1/admin/aml/ra-models/{modelCode}/simulate:
    post:
      summary: RA 모델 sample population simulation (분석 설정, 결재 불필요)
      operationId: simulateRaModel
      security: [ { OAuth2: ['aml:admin:policy'] } ]
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
      security: [ { OAuth2: ['aml:admin:policy'] } ]
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
      security: [ { OAuth2: ['aml:admin:policy'] } ]
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
      security: [ { OAuth2: ['aml:admin:policy'] } ]
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
      security: [ { OAuth2: ['aml:admin:policy'] } ]
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
      security: [ { OAuth2: ['aml:admin:policy'] } ]
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
      security: [ { OAuth2: ['aml:admin:policy'] } ]
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
      security: [ { OAuth2: ['aml:admin:policy'] } ]
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
| country risk / policy pack 관리 | `GET .../country-risk`, `GET .../country-risk/import-status`, `POST .../country-risk:import`(FATF 일일 수집 수동 트리거 — 결재 없음), `POST .../country-risk:change`(🔒 COUNTRY_RISK), `POST .../policy-packs:change`(🔒 POLICY_PACK) |
| RA 모델 활성화 / 등급 override | `.../ra-models/.../activate`(🔒), `.../risk-scores/{id}/override`(🔒) |
| TM alert backlog / scenario 관리 | `GET /aml/alerts/{id}`, `.../tm-scenarios/{code}:activate`(🔒) |
| case SLA / CDD·EDD 처리 | `GET /admin/aml/cdd/cases`, `PATCH .../{id}`, `.../{id}:close`(🔒) |
| STR/CTR 후보 현황 / 제출 | `GET /admin/aml/reports`, `.../{id}:submit`(🔒), `.../{id}:reject`(🔒), `.../{id}:cancel`(🔒) |
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
| Policy Pack STR/CTR | reports 엔드포인트·report_type enum(§2.7, §3.6) |
| 표준 에러·페이지네이션·멱등·버저닝 | §1.2~§1.4, §4(HTTP 상태코드 정본) |
| DB 명칭(테이블·컬럼·enum) | 식별자·enum 모두 DB §3/§5와 1:1. `payload_hash`는 서버 자동계산, `subjectType`은 V41 기준 엔진 21종(`REPORT_RULE_PARAM` 포함). `EventCategory` 11종(`RA_REVIEW` 포함) OpenAPI schema. |
| Webhook 콜백(outbound) | §8(3종·envelope·`X-Signature` HMAC·재시도/멱등) — 설계서 §15.7 'Webhook API' 정본 |
| 운영자 집계 = bo-api 소유 | 대시보드/서비스/감사 집계는 bo-api(`/api/v1/bo/aml/**`), 엔진 API §2에 미추가(§0·§9) |
| 배포 모델/온보딩(deployment topology) = bo-api 소유, aml-svc 엔진 API 미추가 | 서비스(테넌트=서비스) 등록은 격리 토글이 아니라 **배포 유형 선택 + 온보딩 신청/상태**다. enum `DeploymentModel{MANAGED_DEDICATED, SELF_HOSTED, SHARED}`(3종) · `OnboardingStatus{REQUESTED, PROVISIONING, DEPLOYED, VERIFIED, ACTIVE, PACKAGE_ISSUED, CUSTOMER_DEPLOYED, REGISTERED}`(8종, §5 OpenAPI)는 DB `aml_tenants.deployment_model`/`onboarding_status` 정본과 1:1(§3.16·§5). `TenantDto`는 `tenantId`/`deploymentModel`/`onboardingStatus`/`region`(=`default_region`)/`infraRef`(=`infra_ref`) — **`isolationMode` 필드 폐기**. 온보딩 엔드포인트(bo-api 전용): `POST /api/v1/bo/aml/tenants/{tenantId}/onboarding/provision`(프로비저닝 트리거), `GET /api/v1/bo/aml/tenants/{tenantId}/onboarding`(상태 조회), `POST /api/v1/bo/aml/tenants/{tenantId}/onboarding/register`(self-hosted 등록 콜백). 상태머신: 매니지드 `REQUESTED→PROVISIONING→DEPLOYED→VERIFIED→ACTIVE` / self-hosted `REQUESTED→PACKAGE_ISSUED→CUSTOMER_DEPLOYED→REGISTERED` / SHARED `REQUESTED→ACTIVE`. tenant_id 라우팅: 전용 배포는 배포=서비스 단일, SHARED만 `Tenant-Id` 헤더 행 라우팅(§9·§1.1). |
| OpenAPI 스니펫 | §5(`RuleRef`/`matchedRules`/`TransactionEvaluateResponse.ruleCode`/`IngestEventResponse`·`DeploymentModel`/`OnboardingStatus`/`TenantDto`/`OnboardingProvisionRequest`/`OnboardingRegisterRequest`/`OnboardingStatusResponse` 포함) |

---

## 8. Webhook 콜백 계약 (outbound)

설계서 §15.7 'Webhook API(screening/case/report callback)'를 정본으로 확정한다. aml-svc(엔진)는 screening·case·report 상태 변경 이벤트를 서비스 등록 URL로 **outbound HTTP POST** 발행한다(`aml_source_systems`의 webhook 설정·`secret_ref` 사용, source secret 회전은 `POST /admin/aml/source-systems`🔒). bo-web/bo-api 운영자 화면과 무관한 **서비스 서버 간 콜백** 채널이며, 연동 명세(02-aml-integration §3.4 `webhook.callback.requested`)의 아웃박스 dispatch가 본 계약을 발행한다.

> **egress SSRF 정책(P0-17, 양 엔진 공통 규약)**: outbound 대상 URL은 공통 `com.aegis.common.security.egress.WebhookUrlPolicy`(`common-security` 모듈, 전송은 `NoRedirectRequestFactory` 결합)가 **3단계 검증**으로 통제한다 — ① 파싱(absolute URI·host 필수, user-info/fragment 금지; production tier(활성 프로파일 `prod`/`production`/`aws`)는 `https`만+port 443/8443/스킴 기본만, 비-production은 `http`/`https`·port 무제한), ② allowlist(`aegis.aml.webhook.allowed-host-suffixes`, env `AML_WEBHOOK_ALLOWED_HOST_SUFFIXES`, 콤마 구분·빈 값=비활성 — host suffix `.` 경계/exact 일치), ③ DNS 해석(**모든 A/AAAA 레코드** 검사 — production은 loopback·RFC1918·`fc00::/7`·link-local(cloud metadata 포함)·multicast·`0.0.0.0/8` 전체·broadcast·CGNAT(`100.64/10`)·IPv4-mapped(`::ffff:`)/NAT64(`64:ff9b::/96`) 임베디드 내부 IPv4 전부 거부, 비-production은 link-local(metadata)만 tier 무관 거부, mixed answer 1건이라도 위험이면 전체 거부). 위반 reason code 9종 = `NOT_ABSOLUTE`/`HOST_MISSING`/`SCHEME_NOT_ALLOWED`/`USER_INFO_FORBIDDEN`/`FRAGMENT_FORBIDDEN`/`PORT_NOT_ALLOWED`/`HOST_NOT_ALLOWLISTED`/`HOST_UNRESOLVABLE`/`ADDRESS_BLOCKED`. **AML 적용 시점**: 콜백 URL 원천은 `aml_api_credentials.webhook_url`(연동 §3.4)이고 **webhook URL 런타임 등록 경로가 없으므로 매 전송 직전 재검증만** 적용된다 — 위반은 delivery 실패로 기록되어 기존 outbox `FAILED`+지수 backoff 계약(§8.4)에 수렴한다(신규 상태 없음). **redirect 미추종** — `setInstanceFollowRedirects(false)`로 3xx 응답은 추종하지 않고 non-2xx delivery 실패로 기록한다(hop 미추적). DNS rebinding은 JVM DNS positive cache TTL로 TOCTOU 창을 완화할 뿐이며 egress proxy/network policy 배포 요건이 백스톱이다(운영 runbook = 코드 레포 `docs/ops/webhook-egress-policy.md`).

### 8.1 이벤트 타입 (`eventName`)
| eventName | 트리거 | 발행 주체(엔진) | 핵심 payload(camelCase, raw PII 미포함) |
|---|---|---|---|
| `AmlScreeningResolved` | WLF 판정 확정(TRUE_MATCH/FALSE_POSITIVE 등 결재 EXECUTED) | Screening | `screeningId`,`targetRef`,`status`(§5.5),`watchlistSourceType`,`reasonCodes`[] |
| `AmlCaseStatusChanged` | case 상태 전이 | Case Mgmt | `caseId`,`caseType`(§5.8),`fromStatus`,`toStatus`(§5.9),`closeReason`(nullable) |
| `AmlReportSubmitted` | STR/CTR 제출·FIU 회신 결과 | Reporting | `reportId`,`reportType`(§5.10),`status`(§5.11: SUBMITTED/ACKNOWLEDGED/SUBMISSION_FAILED/REJECTED — FIU 회신 폐루프, 설계서 §14.1a),`submittedRef`(nullable),`fiuAckRef`(nullable),`submissionErrorCode`(nullable) |

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
- 이 절은 **outbound webhook 전용**이다. inbound machine-auth의 preamble/raw query/scopeContext/content digest/nonce 공식([공통 정본](00-common-machine-auth.md))과 혼용하지 않는다.

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
| 운영자 감사 화면 | `GET /api/v1/bo/aml/audit?event&eventCategory&actor&traceId&subjectId&from&to&page&size` | explicit AML-domain BO local row + aml-svc `{content,totalElements}` 저수준 page를 exact-total/stable-order merge. actor=부분검색, merge window=`offset+size≤10,000`, engine workspace provenance=`default` |

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
| `PUT .../cdd/checklists/{id}` | **`CHECKLIST_CHANGE`** | **CDD/EDD checklist 변경**(§13.4) | `aml:admin:policy` |
| `PUT .../cdd/periodic-review-policy` | **`PERIODIC_REVIEW_CHANGE`** | **periodic review 주기 변경**(§2.6·§13.4) | `aml:admin:policy` |
| `POST .../country-risk:change` | **`COUNTRY_RISK`** | **country risk 변경**(§13.4) | `aml:admin:policy` |
| `POST .../policy-packs:change` | **`POLICY_PACK`** | **tenant policy pack 변경**(§13.4) | `aml:admin:policy` |
| `POST .../source-systems`(secret 변경) | `SECRET_CHANGE` | source credential 변경 | `aml:admin:source-system` |
| `POST .../high-risk-registry/registrations` | **`HRR_REGISTRATION`** | **RA 당연고위험 회원 등재 — 고위경영진 수동승인**(승인선 `EXECUTIVE_APPROVAL`. RA 엔진 자동 상신(maker `system:ra-engine`) + RA 상세 수동 상신 공용 진입점, 이미 등재/PENDING 멱등 no-op `200 status=NOOP`, 결재 EXECUTED 시에만 `RA_HIGH_RISK_CUSTOMERS` 등재+RA 강제 상향, DB §5.16 V28) | `aml:admin:high-risk-registry` |

> 본 표와 §2.7 관리 API는 설계서 §13.4 4-eyes 대상 전수를 진입 엔드포인트와 매핑한다. `REPORT_RULE_PARAM`은 V41부터 engine-owned이고 `STR_SUBMIT`·`CTR_SUBMIT`은 보고 종류별 승인선을 사용한다. 보고 기각·취소는 신규 subject 없이 제출 결재 사이클을 재사용한다.
>
> **WLF 판정 폐루프 예외 규칙(코드=truth, `ScreeningOperationsService`/`ApprovalDispatchService`)** — `POST .../screenings/{id}/decision`·`POST .../screenings/fp-whitelist` 로 산출되는 판정 상태(§5.5)는 4-eyes 적용 시점이 판정별로 갈린다:
> - **`ESCALATED`(상위승인) = staging(지연 적용).** 판정을 즉시 반영하지 않고 4-eyes 상신(`subjectType=WLF_DECISION`, SUBMITTED)한다. **checker 승인(EXECUTED) 시점에만** 실제 상태 전이가 반영된다(maker≠checker·`payload_hash` 고정). 상신·미승인 구간에는 원 판정 상태가 유지된다(성급한 상태 오염 방지).
> - **`AUTO_DISCOUNTED`(자동 낮춤) = 즉시 적용(4-eyes 우회).** FP whitelist(`aml_fp_whitelist`, DB §3.8a) 등록으로 확정된 오탐 면제는 **등록 즉시 후속 동일 매치(matchFeature)를 자동 낮춤**한다 — 별도 승인 게이트를 거치지 않는다(FP whitelist 등록 자체는 `subjectType=FP_WHITELIST` 4-eyes 로 진입하되, 그 산출물인 discount 적용은 조회·판정 시점에 즉시 반영). 만료(`expires_at < now()` ⇒ EXPIRED, DB §3.8a 가정 A5) 후에는 discount 미적용.
> - **§10 미정의 지점 — 가정 B**: 위 두 규칙의 승인 주체/subject_type 매핑은 코드상 approval `subjectType`(`WLF_DECISION`·`FP_WHITELIST`) 기준으로 기술한다. 상세 승인 라인 표현이 §10 표에 없는 부분은 코드 계약(`ApprovalDispatchService` 분기)만 기술하고 추측하지 않는다.

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

`STR_VELOCITY_CASH`의 rolling cash window는 평가 거래를 정확히 1회 포함한다. 중립 canonical 저장의 바깥 transaction과 STR `REQUIRES_NEW` 평가가 분리되어 현재 행이 아직 보이지 않으면 `EvaluateStrCommand`의 triggerRef/channelType/동결 PHP 금액으로 현재 cash 행을 합성한다. 이미 조회된 동일 triggerRef가 있으면 합성하지 않아 전용 STR·재평가 경로의 이중 집계를 막는다. 따라서 effective `count_threshold=N`은 N번째 현금성 거래에서 즉시 발동한다.

### 11.4 CTR freeze·집계 (BR-501)
CTR 평가(`CtrEvaluationService`)는 거래의 **freeze 된 서버 파생 PHP환산액(`amountPhpEq`)을 재계산하지 않는다**(BR-501). neutral ingest는 canonical 저장의 바깥 transaction과 CTR/STR `REQUIRES_NEW` 경계 및 허용 범위 내 원천↔엔진 시계 오차에도 현재 거래를 잃지 않도록 command의 현재-event `phpEquivalent`를 우선 사용한다. 이 값은 canonical `amounts`에서 서버가 확정한 동일 동결값이다. 현재-event 신호가 없는 레거시·직접 TM 호출만 canonical 이벤트 윈도우로 폴백하며, 두 경로 모두 값이 없으면 금액 룰은 fail-safe 미발동한다. `CTR_SINGLE`=단건 amountPhpEq ≥ 임계, `CTR_DAILY`=동일 영업일 현금거래 합산 ≥ 임계(다건 보완재). (테넌트,주체,영업일)당 CTR DRAFT 정확히 1건(부분 UNIQUE `ux_aml_ctr_draft`, DB §3.12) — 후속 현금거래는 `report_amount`에 정확히 1회 누적(`accumulateCtr`, 경합 시 재시도). `due_at`=거래 영업일 +5영업일 17:00 PHT(§11.2).

### 11.5 STR 사유코드 UPSERT
STR 평가(`StrEvaluationService`)는 (테넌트,트리거)당 STR DRAFT 정확히 1건(부분 UNIQUE `ux_aml_str_draft`, DB §3.12) — 동일 트리거에서 여러 STR 룰이 발화하면 **제2 DRAFT 를 만들지 않고** 각 사유코드(`StrReasonCode`)를 `str_reason_codes` JSONB 집합에 fold(UPSERT). `STR_SANCTION`만 RESTRICT(차단) 액션 동반.

### 11.6 PII sha256 — eAMLA ProviderSvc 위임 (`amlc_submission_ref`)
eAMLA 제출은 **raw PII 미전송** — 토큰화된 보고 참조만 전달한다. `MockAmlcSubmissionAdapter`(모의 ProviderSvc)가 결정적으로 `amlc_submission_ref = AMLC-{sha256(tenant|reportId|reportType)[..12]}`를 산출(BR-601, 무작위성 없음·데모 재현 가능). 실 eAMLA 연동 시 이 어댑터를 실 ProviderSvc RestClient 로 교체하되 계약(토큰 참조·PII 미전송)은 유지. 위임 이벤트는 bo-api `bo_audit_logs` `AMLC_SUBMISSION_DELEGATED`(bo-api V6)로 감사. 연동 상세 = integration §3.4(AMLC 위임).

---

## 변경 이력

| 일자 | 변경 | 비고 |
|---|---|---|
| 2026-07-16 | **FDS externalSignals 인입 패리티 역전파(코드=truth, feature/aml-tm-phase7-ingest-parity, additive).** (1) **§3.17 externalSignals 블록 note 신설** — 중립 인입 Envelope 에 FDS 동형 7 서브블록 19필드(trade/seller/settlement/vendor/crypto/market/employee) 수용, 문자열 ≤64자·제어문자 422, flat payload `externalSignals` 서브트리(비-null) 기록 + `EvaluateCommand.ExternalSignals` 전달. (2) **§3.4 `TransactionEvaluateRequest` 표** — `externalSignals`(flat 19 optional) 행 추가(riskSignals 동렬, FDS 계약 공유). (3) 설정형 CTR/STR 룰 피처 카탈로그(`ConfigurableRuleDslPolicy`) 에 FDS 와 동일한 19키 추가 — 법정 카탈로그(CTR 2·STR 8) 불변, 부재 시 미노출 fail-safe. 커머스 3블록(order/settlement/document)은 AML 미적용(5-product 폐쇄 계약, FDS 소관) 명문화. 스키마/Flyway 무변경(JSONB payload). | 코드 truth=aml-svc `domain/tm/{ExternalSignalKeys,ConfigurableRuleDslPolicy}`·`application/port/in/EvaluateTmUseCase.ExternalSignals`·`application/usecase/{ConfigurableReportRuleEvaluationService,NeutralTransactionEventService}`·`domain/neutral/{NeutralExternalSignals,NeutralEventValidator}`·`adapter/in/rest/{NeutralTransactionEventController,AlertController}`. fds-api §5.1 v4.13 대응 |
| 2026-07-15 | **정책 팩 활성화 시 테넌트 P0-16 pin 자동 전진 명문화(코드=truth, fix/scenario-closed-loop-verification).** **§2.7 `policy-packs:change` 후주 보강** — 승인 EXECUTED(활성화)가 같은 트랜잭션에서 `aml_tenants.policy_pack_version` 을 새 ACTIVE revision 으로 자동 전진(`pack_code` 일치 + 기존 pin NOT NULL 테넌트 한정, NULL pin 미바인딩 테넌트는 불변 — fail-closed 유지, 감사 detail `tenantPinAdvanced`). 배경: 전진 부재 시 WLF 엔진 설정 등 정책 팩 4-eyes 승인 1회 만으로 pin 이 SUPERSEDED revision 에 남아 해당 테넌트 중립 인입 전체가 `422 AML.TENANT_POLICY_UNBOUND` 로 영구 차단되던 결함(로컬 폐루프 검증에서 실측) 교정. 엔드포인트·DTO 표면 무변경. | 코드 truth=aml-svc `application/usecase/PolicyPackService#approveChange`·`application/port/out/TenantRegistryPort#advancePolicyPackPin`·`adapter/out/persistence/{TenantJpaRepository,TenantRegistryJpaAdapter}`·`PolicyPackServiceTest`·`WlfEngineConfigurationIntegrationTest`(pin 전진 회귀). DB §3.1 동기화 |
| 2026-07-15 | **WLF 스크리닝 상세 read-back scope 완화 — BO 검토 위임 403 회귀 교정(코드=truth, fix/wlf-screening-detail-scope).** **§2.2 표** `GET /api/v1/aml/screenings/{screeningId}` scope 를 `aml:screen:evaluate` 단독에서 **`aml:screen:evaluate` 또는 `aml:case:read`(requireAny)** 로 정정. 배경: P0-04 에서 bo-api 위임 credential 이 시뮬레이터와 분리되며 스코프 모델(BOA-S1-01 — evaluate 계열은 소스시스템 인입 전용, BO 콘솔 읽기 화면은 `aml:case:read`)대로 evaluate 미보유로 발급됐는데, 상세 read-back 만 evaluate 단독 요구라 bo-api 스크리닝 상세 위임(→WLF 상세 모달의 회원 신원↔명단 원문 비교·매칭 후보 출처계보)이 403 `AML-AUTHZ-002` 로 폴백 렌더되던 회귀. 목록(`GET /admin/aml/screenings`)·TM 알림 상세·회원 위험 조회 등 여타 읽기 표면은 이미 `aml:case:read` — 본 정정으로 읽기 scope 일관. BO credential 에 evaluate 부여(평가 권한 과부여) 방식은 채택하지 않음. | 코드 truth=aml-svc `adapter/in/rest/ScreeningController#getScreening`(`ScopeGuard.requireAny`)·`ScreeningControllerTest`(case:read 200/evaluate 200/무관 scope 403). bo-api `AmlEngineAuthProperties.DELEGATION_SCOPES` 불변(스코프 추가 없음) |
| 2026-07-15 | **제재명단(OFAC/UN) 원문 reveal vault 적재·백필 — SANCTIONS 매치 원문 비교 결선(코드=truth, fix/wlf-screening-detail-scope).** §2.6 reveal 의 워치리스트 엔트리 대상 원천이 수동 업로드 import 경로에만 결선돼 있고 **일일수집(OFAC_SDN·UN_CONSOLIDATED) 엔트리는 vault 미적재**라, WLF 상세의 SANCTIONS 매칭 후보 원문(명단 기재명·국적·생년) reveal 이 503 `AML.SCREENING_UNAVAILABLE`(no vault entry) 로 실패하던 갭 해소. 파서가 raw 원문(NAME/NATIONALITY/DOB)을 vault 전용으로 동반 운반(entry row·attributes·API 응답 미노출, §19.2 유지)하고 sync ingest 가 동일 트랜잭션에서 암호화 배치 upsert. 미적재 기존 설치본은 다음 sync(UNCHANGED 포함)가 externalRef 재대사로 **기존 entryId 그대로 백필**(참조 스크리닝 계속 해소). 교체·prune 되는 entryId 의 vault 행은 동일 트랜잭션 정리(고아 증식 방지). API 표면 불변 — 데이터 가용성 결선. | 코드 truth=aml-svc `WatchlistFeedPort.WatchlistFeedEntry(rawName/rawNationality/rawDob)`·`OfacSdnXmlParser`·`UnConsolidatedXmlParser`·`SanctionsIngestTransaction`(vault seed·cleanup·`backfillRevealVault`)·`SanctionsSyncService`(APPLIED/UNCHANGED 양 경로 fail-safe 백필)·`PiiVaultPersistenceAdapter`(JDBC 배치 upsert/delete·missing 프로브). DB §2.2/§3.21·integration §7.4 동기화 |
| 2026-07-15 | **P0-12 불변 evidence 다운로드 무결성·감사 무결성 역전파(코드=truth, feature/p0-12-immutable-evidence-audit-integrity).** (1) **§4 오류표 `AML.EXPORT_TAMPER`(409) 신설** — 다운로드 시 저장 bytes 의 재계산 `object_checksum` 이 고정값과 불일치하거나 `manifest_hash` 부재(`ExportTamperException`). 서버가 `EXPORT_TAMPER` 감사를 먼저 기록한 뒤 차단하며 detail 불투명(bytes/hash 미노출). (2) **§2.5 evidence export 표 아래 불변 evidence 다운로드 무결성 후주 신설** — export 는 생성 시점 렌더 bytes 를 `artifact_bytes` 에 write-once 저장·`object_checksum` 고정(DB §3.15), 다운로드는 **저장 bytes serve**(재렌더·원천 재조회 없음)+`object_checksum` 재계산·비교+`manifest_hash` 검증, 불일치=at-rest 변조→409 `AML.EXPORT_TAMPER`+`EXPORT_TAMPER` 감사. 원천 업무 DB 변경해도 download 불변, legacy(object_checksum 없음) 폴백. 버전핀 실값·S3 WORM·legal hold·파기 증명은 phase-2 BLOCKED. 감사 hash chain(append-only trigger·`AuditHashChainVerificationJob`·`AUDIT_CHAIN_TAMPER`)는 엔진 내부/DB 계약이라 API 표면 무변경(DB §3.15·software § 참조). 엔드포인트 신설 없음·기존 export 계약 불변. | 코드 truth=aml-svc `application/usecase/EvidenceExportService`(verifyIntegrity·저장 bytes serve)·`application/port/in/EvidenceExportUseCase`(ExportTamperException)·`global/GlobalExceptionHandler`(409 `AML.EXPORT_TAMPER`). DB §3.15/§5/§7 V55·V56·software § 동기화. fds 대칭은 409 `FDS-APPROVAL-PAYLOAD-CHANGED` 재사용(01-fds-api.md). |
| 2026-07-14 | **P0-11 규제 제출 durable boundary·콜백 하드닝 역전파(코드=truth, feature/p0-11-regulatory-submission-boundary).** (1) **§2.7 report 표에 콜백 엔드포인트 1행 추가** — `POST /api/v1/admin/aml/reports/{reportId}/callback`(전용 최소권한 scope **`aml:report:callback`** 신설·HMAC ingest 필터 인가·4-eyes 아님). body `FiuCallbackRequest{ status(ACKNOWLEDGED\|REJECTED), submittedRef, messageId, fiuAckRef, errorCode }` 가 durable 제출 job(`aml_report_submission_jobs`, DB §3.12a)과 **이중 대사**(`reportId↔submittedRef`(∨fiuAckRef) + 제출 job `provider_message_id` 일치·불일치/미존재 job 거부). 멱등(이미 terminal report=`200` no-op)·replay 봉쇄(HMAC nonce v2 + `submittedRef` 멱등 + `SUBMITTED` 상태가드). `SUBMITTED → ACKNOWLEDGED\|SUBMISSION_FAILED` 폐루프. (2) **§1.1 마스터 scope enum 14→15종** — internal machine 전용 2종째로 `aml:report:callback` 추가(13 human + 2 machine). (3) 재제출은 기존 `:submit` 4-eyes 재사용으로 provider 회차를 새 job 으로 멱등 re-enqueue(자연키 `(tenant, report, submitted_ref)`), `provider_message_id` 대사로 회신 결선. **prod 는 async worker 강제(sync-close=false)·비-prod sync-close 데모**. 실 FIU/ProviderSvc HTTP·mTLS/전자서명·form schema versioning·수동 DLQ UI 는 phase-2 BLOCKED. durable worker·provider boundary(aml-svc↔ProviderSvc §14.1a)·reconciliation 정본은 integration §9·§3.4. | 코드 truth=aml-svc `adapter/in/rest/RegulatoryReportController`(callback·`aml:report:callback`·`FiuCallbackRequest`)·`application/usecase/RegulatoryReportService`(verifyCallbackBinding·approveSubmit enqueue·process)·`application/port/in/AcknowledgeReportUseCase`·`application/port/out/{ReportSubmissionPort,AmlcSubmissionPort,ReportSubmissionJobStorePort}`. DB §3.12a/§5.41/§7 V54·integration §9·software § 동기화. 엔드포인트 1 신설·scope 1 신설·기존 엔드포인트/DTO 불변 |
| 2026-07-14 | **P0-16 tenant 관할·통화·Policy Pack revision 강제 역전파(코드=truth, feature/p0-16-tenant-policy-pack-binding).** (1) **§2.7 Tenant Policy Binding 서브섹션 신설** — `PATCH /api/v1/admin/aml/tenants/{tenantId}/policy-binding`(scope `aml:admin:policy`, `Tenant-Id` 헤더=경로 일치, body `BindRequest{jurisdiction, baseCurrency, reportingCurrency?, timezone?, policyPackVersion}`, 잘못된 ISO country/currency→400·미존재/비-effective revision→422, 멱등 upsert, 응답 `TenantPolicyBinding`). (2) **§0.5 경계 구획 note** — policy-binding 은 온보딩(bo-api 소유·엔진 미추가)이 아니라 별개의 **엔진 규제 정책 표면**임을 명문화(온보딩=서비스 lifecycle, 정책 바인딩=규제 파라미터). (3) **§4 오류표 `AML.TENANT_POLICY_UNBOUND`(422) 신설** — 관할/통화/Policy Pack revision 미바인딩·충돌·비-effective, 중립 인입·바인딩 upsert fail-closed(구 PH/PHP 기본 오귀속 제거). (4) **§2.1a 중립 인입 정정** — `baseEquivalent`+`baseCurrency`(통화중립·항상 기록)·`phpEquivalent`(baseCurrency=PHP 일 때만 생성·비-PHP 미기록) payload 필드, corridor 서버 파생 발신국=`TenantPolicyBinding.jurisdiction`(구 `aml.neutral.regulatory-country` 상수 제거), 422 규칙 ⑤ baseCurrency=tenant 바인딩 기준통화·step 0 바인딩 해소 미충족 시 422 `AML.TENANT_POLICY_UNBOUND`. 완전 FX conversion·bo-api tenant shadow 동기는 phase-2(A1). | 코드 truth=aml-svc `domain/tenant/{TenantPolicyBinding,TenantPolicyEvidence,TenantPolicyUnboundException}`·`application/usecase/{TenantPolicyResolver,TenantPolicyBindingService,NeutralTransactionEventService}`·`adapter/in/rest/TenantPolicyBindingAdminController`·`global/GlobalExceptionHandler#handleTenantPolicyUnbound`. DB §3.1/§7 V53·integration §·software § 동기화. 엔드포인트 1 신설·오류코드 1 신설·기존 DTO 불변(중립 payload 필드 정정) |
| 2026-07-14 | **P0-06 WLF 필수 source readiness·재검색 역전파(코드=truth, feature/p0-06-wlf-source-readiness-rescreen).** (1) **§2.2 fail-closed readiness 게이트 note 신설** — `POST /api/v1/aml/screen`(및 `/internal/v1/aml/screen`)가 스크리닝 전 필수 source 정책(DB §3.6a) 기반 readiness 게이트를 통과해야 하며(각 필수 source screening-ready 또는 승인 NOT_APPLICABLE, 정책 없음 tenant 는 fallback ready≥1), 미충족 시 `NO_MATCH` 미탐이 아니라 **503 `AML.SCREENING_UNAVAILABLE`** + 사유코드 7종(`NO_MANDATORY_POLICY`/`NO_READY_SOURCE`/`MISSING_SOURCE`/`NOT_READY`/`STALE`/`FAILED`/`NOT_APPLICABLE_UNAPPROVED`, `ScreeningReadinessReason`)으로 fail-closed(구 freshness 게이트 vacuous-truth fail-open 제거). (2) **§2.7 Watchlist/명단 표에 엔드포인트 3행 추가** — `GET/POST /api/v1/admin/aml/mandatory-sources`(scope `aml:admin:watchlist`, 필수 source 정책 조회·upsert — REST-only seed 진입점, config 성격 4-eyes 아님)·`POST /api/v1/admin/aml/watchlist-sources/{sourceCode}:override`(긴급 readiness override — 사유·승인자·만료·`WATCHLIST_READINESS` 감사·만료 자동 원상). (3) **§4 오류표 `AML.SCREENING_UNAVAILABLE` 행 확장** — WLF 엔진 장애·PII reveal 역참조 실패에 더해 필수 source readiness 미충족(사유코드 details) 추가. rescreen 파이프라인(명단 apply 후 durable 재검색)은 integration §. | 코드 truth=aml-svc `application/usecase/WlfScreeningService`(게이트 (0a))·`adapter/out/persistence/WatchlistReadinessGateAdapter`·`domain/watchlist/{ScreeningReadinessReason,MandatoryWatchlistSource,WatchlistSource(effectiveReadiness)}`·`adapter/in/rest/MandatorySourceAdminController`·`global/GlobalExceptionHandler#handleScreeningUnavailable`. DB §3.6/§3.6a~§3.6c·§7 V50~V52·integration §·software § 동기화. 엔드포인트 3 신설·기존 엔드포인트/DTO 불변 |
| 2026-07-14 | **P0-05 WLF 후보 생성 recall 보강 역전파(코드=truth).** §3.2 `ScreenResponse.scoreBreakdown` 서술에 후보 recall 재현 스냅샷 `scoreBreakdown.candidateStrategy{ candidateStrategyVersion(`wlf-cand-v1`), matcherVersion(=definitionHash), trgmFloor(0.30), candidateCap(200), phoneticEnabled(true), candidateCapHit, candidateCount, strategyCounts }` 를 명문화(후보 4전략 S1 exact∪S2 토큰교집합∪S3 pg_trgm word_similarity∪S4 double-metaphone 교집합의 전략별 후보수·상한 도달 진단, 정밀도는 후단 FuzzyMatchEngine 책임). §3.2 passthrough note 에 `scoreBreakdown`(candidateStrategy 포함)이 엔진 판정 증거로 bo-api 무손실 전달 대상임을 부기. | 코드 truth=aml-svc `WlfScreeningService`(`candidateStrategy` 증거 build·`CANDIDATE_STRATEGY_VERSION="wlf-cand-v1"`)·`WatchlistEntryJpaAdapter`(4전략 UNION 후보 조회·capHit). DDL=DB §3.7/§7·V49, 엔드포인트·DTO 필드 불변(scoreBreakdown 내부 확장) |
| 2026-07-14 | **P0-09 알림 read 경로 마스킹 verbatim·자동 reveal 제거 명문화(코드=truth).** §2.4에 알림 read 경로 계약 note 신설 — `GET /api/v1/aml/alerts/{alertId}`·`/related-transactions`·목록의 `aml:case:read` 경로는 저장된 마스킹 evidence 를 verbatim 반환하며 자동 복호화(구 `enrichEvidence`) 없음. §3.4a evidence fundGraph COUNTERPARTY label 을 모든 `aml:case:read` 경로(Subject360 fund-view 포함)에서 토큰만으로 정정(구 fund-view `이름 (국가)` 자동 vault reveal 제거). §3.4d `RelatedTransactionDto.counterpartyName` 은 `aml:case:read` 에서 항상 null(마스킹 토큰 폴백)로 정정하고, 원문은 §2.6 `aml:pii:reveal` reveal API(`POST /internal/v1/aml/pii/reveal`, 사유+`RAW_DATA_ACCESS`·fail-closed) 전용임을 §3.4d note 에서 재명문화. §1.6/§2.6 reveal 분리 계약은 기존 정본 유지(무변경). | 코드 truth=aml-svc `AlertController`(case:read verbatim)·`EvidenceTimelineService`(fund-view counterpartyName==null 빌더 전달)·`AlertRelatedTransactionsService`(counterpartyName null 폴백)·`PiiRevealInternalController`(reveal 정본 경로·`aml:pii:reveal` 불변). DDL/DTO 필드 불변 |
| 2026-07-13 | **P0-17 outbound webhook egress SSRF 정책.** §8에 양 엔진 공통 `WebhookUrlPolicy` 3단계 검증(파싱: production https+443/8443/기본 port만·user-info/fragment 금지 / allowlist: `aegis.aml.webhook.allowed-host-suffixes` suffix 일치·빈 값=비활성 / DNS: 전 A·AAAA 레코드 검사, production 내부대역·metadata·CGNAT·IPv4-mapped·NAT64 거부, 비-production은 link-local만 tier 무관 거부), reason code 9종, redirect 미추종(3xx=non-2xx delivery 실패), DNS rebinding 한계·egress proxy 백스톱을 신설했다. AML은 콜백 URL 원천이 `aml_api_credentials.webhook_url`이고 런타임 등록 경로가 없어 **매 전송 직전 재검증만** 적용(위반=delivery 실패 → 기존 `FAILED`+지수 backoff 계약 유지)임을 명시했다. | 코드 truth=`common-security` `WebhookUrlPolicy`/`NoRedirectRequestFactory`, `HttpWebhookRelayAdapter`, `WebhookEgressConfiguration`; runbook `docs/ops/webhook-egress-policy.md`; API/DDL 계약 불변 |
| 2026-07-13 | **P0-04 internal service-auth/OpenAPI 완료.** `/internal/v1/aml/**`를 wire v2-only로 전환하고 endpoint별 scope, escalation exact FDS caller/dataScope, PII exact BO caller를 수신 엔진에서 강제했다. FDS→AML fallback은 exact target/final URI/same bytes signer를 사용하고 신규 internal scope를 포함한 public/BO 13 + machine 1 = 총 14종 및 escalation OpenAPI path를 동기화했다. | 코드 truth=`AmlIngestAuthenticationFilter`·internal controllers·`RestAmlHandoffPublisher`; DDL 불변 |
| 2026-07-13 | **P0-03 local/demo mock 규제 제출 실패→공식 재제출 폐루프 명문화.** reject-demo bucket은 최초 제출(`resubmitCount=0`)만 `SUBMISSION_REJECTED`로 실패하고, 동일 report의 기존 `:submit` 4-eyes 재사용은 evidence 계보를 보존·count를 증가시킨 뒤 ACK한다. | 코드 truth=`MockRegulatorSubmissionAdapter`·`RegulatoryReport.toUnderReview`·`MockRegulatorSubmissionAdapterTest` |
| 2026-07-13 | **P0-03 AML admin trusted actor·typed delegation·감사 집계 경계.** common filter가 HMAC 성공 뒤 signed subject의 128자/제어문자 경계를 검증한 값만 verified attribute로 승격하고, `TrustedActorResolver`가 admin write의 maker/checker/actor를 파생한다. invalid signed subject는 generic 401, legacy body/query claim은 생략 가능·대소문자 무시 일치 assertion(불일치 400), 같은 signed actor의 self-approval은 409다. `platformOperator`는 data-scope일 뿐 PII/STR/IAM 우회가 아니고 wildcard `*`만 전역 우회다. bo-api catch-all engine proxy는 삭제하고 typed BFF만 허용한다. AML audit engine은 actor 부분검색·traceId·`{content,totalElements}`를 제공하며 BO는 exact `event`/engine `eventCategory`, 10,000행 merge window, exact total·stable merge와 workspace provenance `default`를 사용한다. V46은 audit trace만 128자로 넓히고 canonical 64자/422는 유지한다. AmlTenant provision/register actor도 principal에서 파생한다. | wire/canonical 필드 삭제 없음. typed AML projection은 explicit AML event만 포함하고 IAM/ROLE/SECURITY/unknown은 generic BO_SUPER_ADMIN surface로 격리 |
| 2026-07-12 | **P0-01 AML 중립 거래 인입 인증 우회 차단 동기화.** Public plane에 `/aml/v1/**`를 등재하고 §1.1/§2.1a에서 실제 common filter coverage, route별 v2-only, 두 ingest의 `aml:event:write`, scope/role attribute 부재 시 공통 local-bootstrap `Boolean.TRUE` marker 외 403, 인증 실패 업무 row 0과 valid-signed scope 403 nonce 보존을 확정했다. Neutral `Source-System`/`Idempotency-Key` endpoint 예외와 `X-Data-Scope` tamper 401만 명시하고 credential별 data-scope 인가 모델은 추가하지 않았다. §4 오류를 `AML-AUTH-001/002`·`AML-AUTHZ-002`·`AML.FORBIDDEN_SCOPE`와 정렬했다. | API/DB schema 무변경. 코드 truth=AML filter registration/spec·`ScopeGuard`·`RoleGuard`·실 filter-chain REST 테스트 |
| 2026-07-12 | **P0-00 공통 inbound machine-auth wire v2 동기화.** §0/§1.1을 `00-common-machine-auth.md` 정본으로 전환해 normalized servlet routing/ambiguous path·duplicate singleton 거부, raw path/query·AML `workspace=default`·고정 9-key scopeContext(trace/correlation 제외)·body digest, v1 offset/v2 UTC `Z`, nonce TTL `>2×skew`·cleanup `20×5000/tick`, signed redirect 거부와 local/demo positive provisioning을 반영했다. simulator/BO AML credential 분리, BO `COMPLIANCE` authority와 signed `X-User-Subject` STR 감사 actor 경계를 명시했다. P0-01/P0-04/P0-14와 P1-02 lifecycle은 미완료이며 §8 outbound webhook 공식은 inbound v2와 별개다. | 코드 truth=`common-security`, AML V44, bo-api AML signer·`RestClientConfig`/`RestClientConfigTest`, `test-vectors/machine-auth-v2.json`, Python simulator transport |
| 2026-07-12 | **당연고위험(HRR) 폐루프 시각화 API 역전파(§2.7 `mandatoryHighRisk` 필터 param 추가 + bo-api 공개 등재 상태 read-back 위임 명문화).** ① **§2.7 `GET .../risk-scores` 에 `mandatoryHighRisk`(당연고위험) 서버 필터 param 추가** — additive·optional 3-value(`true`=당연고위험만·`false`=일반만·미지정=무필터), `aml_risk_scores.mandatory_high_risk` outer 필터. bo-api `GET /api/v1/bo/aml/risk-scores` passthrough(위임 server-param + client post-filter 이중, stub `RiskScore.mandatoryHighRisk` post-filter). ② **bo-api 공개 read-back 위임 `GET /api/v1/bo/aml/high-risk-registry/registrations/{customerRef}`(scope `aml:case:read`) 명문화** — 엔진 admin read-back(§2 HRR surface, `aml:admin:high-risk-registry`)을 RA 상세(PRD §12-A.4 BR-006) 폐루프 흐름도 바인딩용 공개 조회 표면으로 노출(응답 `HrrRegistrationState`·위임/stub/운영 fail-closed 3분기). 승인/반려는 기존 공통 결재함 `:approve`/`:reject`(scope `aml:admin:approval`) 재사용(신설 없음). 엔진 계약 변경 없음. | docs 역전파. 코드=truth. 근거=aml-svc `RiskScoreAdminController`(`mandatoryHighRisk`)·`RiskScoreJpaAdapter`, bo-api `AmlRaService`(passthrough)·`AmlHighRiskRegistryController.registrationState`·`AmlHighRiskRegistryService.registrationState`·`HighRiskRegistryDtos.HrrRegistrationState`·`V16__demo_executive_checker.sql`. PRD §12-A.4 BR-006·§12-B.6 BR-006·§03 §4.2 동기화. |
| 2026-07-12 | **bo-api 프로필 `riskSummary.riskGrade` 등급 폴백 체인 명문화(§3.9 `CustomerProfileDto` 후주, §3.3 포인터, 계약 변경 없음).** 고객 프로필 aggregate `riskSummary.riskGrade` 가 엔진 evidence profile top-level `riskGrade` → `latestRiskScore.riskGrade` → 최종 `LOW` 순으로 폴백해 riskScore↔riskGrade 를 동일 소스로 정렬((LOW, 85.39) 모순 방지, 가정 A4)함을 §3.9 후주에 추가(§3.3 은 포인터). 표기 정합 파생일 뿐 엔진 판정 미변경·스키마/계약 변경 없음. | docs-only 역전파. 코드=truth. 근거=bo-api `aml/profile/service/AmlCustomerProfileService#resolveGrade`(L390~407). plan §6.1·§3.9 동기화. |
| 2026-07-12 | **공통 결재 목록 `GET .../approvals` 필터 계약 변경 역전파(코드=truth, feature/aml-hrr-closed-loop-visualization).** 엔진 `ApprovalController#queue` — ① **`status` 기본값 SUBMITTED 제거**(미지정=전 상태 수렴 — SUBMITTED/APPROVED/EXECUTED/REJECTED…). 과거 기본 SUBMITTED 는 결재함 "처리됨" 탭·승인 이력·HRR 폐루프 흐름도가 EXECUTED/REJECTED 를 볼 수 없던 결함이라 제거, 대기 큐는 `?status=SUBMITTED` 명시로 동작(기존 호출부 무변경). ② **`subjectType` 필터 파라미터 신설**(미지정=전 subject, §3.7 값). 잘못된 enum → 400. bo-api `GET /api/v1/bo/aml/approvals` 위임도 동일 의미론(stub null=무필터 수렴). §결재(공통) 표 행 갱신 + 필터 계약 note 신설. | docs 역전파. 코드=truth. 근거=aml-svc `adapter/in/rest/ApprovalController#queue`(`status`/`subjectType` required=false·valueOf 400), bo-api `/bo/aml/approvals` 위임. PRD §12-A.4 BR-006 흐름도 read surface 정합. |
| 2026-07-12 | **AML lifecycle 폐루프 API 역전파.** CDD exact replay 불변 업무결정 응답, engine-owned REPORT_RULE_PARAM 상신/5필드 응답 검증, origin-alert handoff, case-linked STR/CTR type·target 검증, case PENDING/reject/type-matched REPORTED 및 case→report lock, report 반려 후 재상신과 인증 maker 경계를 반영했다. | 코드=truth. aml V41~V43. |
| 2026-07-11 | **WLF 엔진 가변 설정·적용 증거 API 추가(AML-WLF-005).** `GET/POST /api/v1/admin/aml/wlf-engine-config[:change]`와 bo-api 미러를 신설해 Policy Pack 단일 원장/`POLICY_PACK` 4-eyes 위에서 SANCTIONS·PEP별 6가중치·negative penalty·review/high-confidence band를 관리한다. screening 응답에 결과 생성 시점 `appliedPolicy`(profile·config/rule version·definition hash·threshold·band)를 additive 영속 투영하고, admin simulation `sourceTypes` 필터 및 적용정책 응답을 명문화했다. HIGH는 우선순위 evidence일 뿐 자동 TRUE_MATCH가 아니다. | api-designer. 코드=truth. aml V37~V38·bo-api V15·`verify_aml_wlf_config_closed_loop.py`. |
| 2026-07-10 | **CDD→FDS 고객 프로필 동기화 계약 추가.** §2.1 step 7f에 CDD accepted 트랜잭션의 `FDS_CUSTOMER_PROFILE` outbox와 PII-safe payload, replay/dedup, relay retry 경계를 명시. AML DB V32가 outbox aggregate CHECK 7종을 허용한다. `registeredAt`·`kyc.kycVerifiedAt`은 `docs/aml-data.md` §12.2 정본. | api-designer |
| 2026-07-09 | **Travel Rule 기능 전면 제거 역전파(코드=truth, feature/remove-travel-rule, aml V31·bo-api V14).** (1) **§2.7 Regulatory Reporting 표에서 travel-rule 엔드포인트 2행 삭제** — `GET .../travel-rule/transfers`·`POST .../travel-rule/transfers/{ref}:resolve-exception` 제거. (2) **§3.7 `ApprovalDto.subjectType` 21→20종** — `TRAVEL_RULE_EXCEPTION` enum 행 제거(`ApprovalSubjectType` 20종 코드 정합). (3) **§3.8 `EvidenceExportRequest.exportType`에서 `TRAVEL_RULE` 제거**(`ExportType` 9종). (4) **§3.14 `TravelRuleTransferDto` 섹션을 제거 스텁으로 대체** — `aml_travel_rule_transfers` 테이블·`TravelRuleTransferDto`·`CompletenessStatus`·`TravelRuleRiskStatus` enum 삭제, 섹션 번호는 타 문서 § 참조 보존 위해 유지. (5) **§3.10 FdsEscalation `action` enum에서 `REQUEST_TRAVEL_RULE_INFO` 제거**(fds `ActionType` 22종 정합, `OPEN_AML_CASE`/`REGULATORY_REPORT` 위임 유지). (6) **§5 OpenAPI에서 `TravelRuleTransferDto` schema·`/travel-rule/transfers` path 삭제**. (7) **§6 BO 매핑 `Travel Rule exception` 행·§7 동기화 `Policy Pack STR/CTR/Travel Rule`·§8 `AmlReportSubmitted`·§10 4-eyes `TRAVEL_RULE_EXCEPTION` 행·policy pack/reports 제출 서술의 "STR/CTR/Travel Rule"→"STR/CTR"** 전수 정정. 유지: FATF R.16 당사자 정보 요건(`counterparty` 인입 계약 필수 규칙 — CROSS_BORDER_REMITTANCE)은 규제 근거·라이브 검증 규칙이라 존치(422 규칙 ⑦). | api-designer. 코드=truth. 근거=aegis-aml 84997e1(feature/remove-travel-rule)·삭제된 aml `TravelRuleController`·bo-api `AmlTravelRuleController`·`ApprovalSubjectType`(20)·`CaseType`(11)·`ReportType`(6)·`ExportType`(9)·`EventFamily`(19)·`CompletenessStatus`/`TravelRuleRiskStatus` 삭제·Flyway aml V31·bo-api V14. |
| 2026-07-08 | **알림→케이스 트리아지·처분(disposition) 폐루프 API 역전파(코드=truth, feature/aml-fds-case-triage-disposition, aml-svc V30·bo-api V13).** (1) **§2.4 TM API 표에 알림 lifecycle 4행 신설** — `POST /api/v1/aml/alerts/{alertId}:triage`(`DETECTED`→`TRIAGED`)·`:dismiss`(`DETECTED`/`TRIAGED`→`DISMISSED`, **optional body `{reason, actor}`** — 엔진 하위호환 optional, `reason`/`actor` 지정 시 `disposition_reason`/`disposition_actor`(V30) 영속)·`:escalate`(`TRIAGED`→`ESCALATED`, 201 케이스)·`:recommend-str`(`TRIAGED`→`STR_RECOMMENDED`, 201 STR 케이스+아웃박스), 전부 scope `aml:case:update`·불법 전이 409 `AML.STATE_CONFLICT` + **알림 lifecycle 상태기계 note**(6종 종결값·`dispositionReason` DISMISSED 전이 한정 불변식·4-eyes 비대상 G2). (2) **§3.4a `AlertDto`에 `dispositionReason`/`dispositionActor` 2행 신설** — DB `disposition_reason`(VARCHAR(64))·`disposition_actor`(VARCHAR(128)) V30 1:1, DISMISSED 에서만 non-null, 오탐율(§12-B.3) 실집계 근거. (3) **§2.5a bo-api 위임 표에 알림 처분 4행 신설** — `:triage`(body `AlertTriageRequest{actor?}`)·`:dismiss`(`AlertDismissRequest{reason 필수 @NotBlank, actor?}` — **bo-api 계층 사유 필수 강제, 공백 시 400, G1**)·`:escalate`·`:recommend-str`(`AlertHandOffRequest{caseType?, actor?}`, 201 caseId), 응답 `AlertActionResponse{alertId,status,caseId?,caseStatus?}` + **위임 4종·409 표면화 계약 note**(stub↔위임 동형·prod fail-closed G7·감사 4종 V13·`mapError` 상태 토큰만 구조화 G8). (4) **§2.7 케이스 `:close` 행 일반화(라이브 검증 추가 수정, 커밋 fbb0673)** — `🔒4-eyes(EDD 종결)`→`🔒4-eyes(EDD_CLOSE)`, 종결 대상을 **EDD_REVIEW 전용에서 조사 케이스 일반(EDD_REVIEW·STR_REVIEW·SAR_REVIEW·CDD)으로 정정**. 알림 트리아지·처분 폐루프에서 전환된 STR_REVIEW 케이스가 `:close` 시 400 "case is not an EDD_REVIEW case" 로 거부되던 결함 해소 — 엔진 `Case.closeApproved`(구 `closeEdd`)가 케이스 유형 가드 없이 존재·비종결 상태 불변식만 강제하고, `CddEddService.submitEddClose` 도 EDD_REVIEW 전용 가드 제거(존재·비종결 검증 유지). 회원원장 EDD 종료 이력(`recordEddClosed`)은 EDD_REVIEW 에만 기록(알림 파생 케이스 제외). | aegis-java-implementer(spec). 코드=truth·가정 G1~G3. 근거=aml-svc `adapter/in/rest/AlertController`(`:dismiss` DismissRequest{reason,actor}·AlertDto.dispositionReason/Actor)·`domain/Alert`(dismiss(reason,actor) DISMISSED 한정 불변식)·`domain/Case`(closeApproved 유형 가드 제거)·`application/usecase/CddEddService`(submitEddClose·approveEddClose EDD_REVIEW 이력 한정)·`db/migration/V30__alert_disposition_reason.sql`, bo-api `aml/tm/controller/AmlTmController`(4 액션)·`aml/tm/service/AmlTmService`(위임·stub·감사 4종·prod fail-closed)·`proxy/AmlEngineClient`(409 STATE_CONFLICT 상태 토큰 구조화)·`db/migration/V13__alert_disposition_audit_events.sql`. DB §02-aml §마이그레이션(V30)·plan §02 §7.1·§8.1·§12-B.3 동기화. |
| 2026-07-07 | **RA 당연고위험 등재 폐루프 §3.7·§10 동기화(코드=truth, feature/aml-hrr-ra-registration, V28).** ① **§3.7 `ApprovalDto.subjectType` 19→21종** — 기등재 누락이던 `CTR_THRESHOLD`(V23, §2.7 기술과 enum 행 사이 드리프트 해소)와 신규 `HRR_REGISTRATION`(RA 당연고위험 회원 등재 승인, 승인선 `EXECUTIVE_APPROVAL` 고위경영진 수동승인)을 enum 행에 등재. `HRR_REGISTRATION` 상신 경로 2원화: RA 평가가 `mandatoryHighRisk=true` CUSTOMER 산출 시 **엔진 자동 상신**(maker `system:ra-engine`, 멱등 no-op 재평가 루프 종료) + RA 상세 화면 **수동 상신**(`POST .../high-risk-registry/registrations`) — 승인 EXECUTED 시에만 `RA_HIGH_RISK_CUSTOMERS` 참조 리스트 등재+RA 강제 상향 확정. ② **§10 4-eyes 등재표에 `HRR_REGISTRATION` 행 추가**(scope `aml:admin:high-risk-registry`). ③ 승인 히스토리는 공통 결재함 `?subjectType=HIGH_RISK_REGISTRY\|HRR_REGISTRATION` 재사용(전용 엔드포인트 미신설). | aegis-java-implementer. 코드=truth. 근거=aml-svc `ApprovalSubjectType`(21)·`ReferenceListType`(5)·`RiskAssessmentService#submitHighRiskRegistrationIfMandatory`·`HighRiskCustomerRegistrationService`·`ApprovalLineResolver`(HRR_REGISTRATION→EXECUTIVE_APPROVAL)·`V28`, bo-api `AmlApprovalDtos.SubjectType`(23)·`V11`(감사 `HRR_REGISTRATION_SUBMITTED`+라우팅 seed), bo-web `lib/aml-hrr.ts`(5종 fail-soft)·`HrrRegistrationSection`. DB §5.16/§5.33/§7(V28)·PRD §12-B.6·§03 §4.2 동기화. |
| 2026-07-07 | **HRR 등재 위임 경로 멱등 no-op 계약 명문화(코드=truth, fix-20260707-hrr-registration-delegate-noop).** §2 HRR admin surface 표에 ① `POST .../high-risk-registry/registrations`(🔒 `HRR_REGISTRATION`·승인선 `EXECUTIVE_APPROVAL` — 신규 상신 `202 status=SUBMITTED`, **멱등 no-op(이미 등재/PENDING) `200 status=NOOP`·approvalId=null**) ② `GET .../high-risk-registry/registrations/{customerRef}`(등재 상태 read-back — `{registered, pending, pendingApprovalId}`) 2행 신설 + **위임 경로 멱등 no-op 계약 note** 추가. **결함**: bo-api 위임 분기가 엔진 `status=NOOP` 을 무시하고 `approvalId=null` 이면 무조건 `502 BAD_GATEWAY` 로 변환 → RA 재평가가 이미 등재/PENDING 회원을 재상신하면 stub(정상 no-op)과 발산·재평가 루프 종료 불변식 A6 붕괴. **수정**: `status=NOOP` 을 정상 no-op 으로 매핑(502 미발생), `status` 부재 + approvalId null 인 진짜 오류만 502 유지, stub↔위임 대칭. **가정 A(§미정의)**: 엔진 no-op 응답에 alreadyRegistered vs pending 세분 플래그 부재 → no-op 직후 `registration-state` read-back 으로 판별(read-back 실패 시 보수적 `pending=true` 폴백). | aegis-java-implementer. 코드=truth. 근거=aml-svc `HighRiskRegistryAdminController.submitRegistration`(200 NOOP)·`registrationState`, bo-api `AmlHighRiskRegistryService.submitRegistration`(status=NOOP 분기·`readBackRegistrationState`·`EngineRegistrationState`) + `AmlHrrRegistrationServiceTest`(위임 no-op registered/pending·read-back 실패 폴백·진짜오류 502 회귀). |
| 2026-07-07 | **RA 상세 관리자 액션 — CDD/EDD 즉시 재이행 접수 API 역전파(코드=truth, feature/aml-ra-detail-admin-actions, V27).** §2.x 회원원장 read 절에 `POST /api/v1/admin/aml/cdd/customers/{customerRef}/reissue:request`(202 `ReissueResponse{requestId,historyId,historyType,status(ACCEPTED|REPLAYED)}`, `requestId` 멱등·reason 필수·결재 불요 운영 지시) + bo-api 위임 `POST /api/v1/bo/aml/members/{memberRef}/reissue:request` 콜아웃 신설, `cdd-history` `types` enum 6종(V27) 갱신. **실 재이행 수행은 계정계 연동 예정**(`AccountSystemReissuePort` no-op 아답터, 코드 토큰 `TODO(계정계-연동)`) — 계정계 재수행 결과 `customer.cdd.completed` 재인입이 `CDD_REVIEW` 폐루프. RA 상세 '관리자 액션' 패널의 EDD 케이스 착수·CDD 재이행 주기 변경(4-eyes PERIODIC_REVIEW_CHANGE)은 기존 계약 재사용(신규 라우트 없음). | aegis-java-implementer. 코드=truth. 근거=aml-svc `CddController.reissue`·`DueDiligenceReissueService`, bo-api `aml/reissue/{controller,service,dto}`, bo-web `AmlRaAdminActions`. DB §3.22f·§5.36·§7(V27) 동기화. |
| 2026-07-06 | **CTR 임계 변경 결재 상세 AS-IS/TO-BE 표시 역전파(코드=truth, fix/approval-as-is-to-be).** `ApprovalDetail`에 `detail`·`changes[{label,before,after}]`를 명시하고, `CTR_THRESHOLD` 상신 payload를 `tenant\|currency\|toAmount\|reason\|fromAmount`로 확장해 상신 시점 기존 임계값(AS-IS)과 요청 임계값(TO-BE)을 결재함에서 비교 표시한다. legacy payload는 현재 임계값 fallback으로 표시하며 raw PII 저장 없음 불변. | aegis-java-implementer. 근거=aml-svc `ApprovalController.ApprovalDetail/ApprovalChange`·`CtrThresholdManagementService`·`PayloadHashing.canonicalCtrThreshold`, bo-api `AmlApprovalService` stagedPayload 파생 fallback. |
| 2026-07-06 | **CDD 재이행 주기 조정 `newDueAt` date-only 수용 명문화(코드=truth, fix/cdd-review-cycle-date-only).** `POST /api/v1/bo/aml/customers/{customerRef}/review-cycle:change` 의 FE→bo-api 요청 `newDueAt` 은 화면 date input 값인 `YYYY-MM-DD` 를 수용하며, bo-api가 UTC 자정 ISO instant(`YYYY-MM-DDT00:00:00Z`)로 정규화해 aml-svc `POST /api/v1/admin/aml/cdd/customers/{customerRef}/review-cycle:change`에 위임한다. ISO-8601 instant 입력도 하위호환으로 허용한다. `reason` 필수와 maker 서버 파생 신뢰경계는 불변. | aegis-java-implementer. 코드=truth. 근거=bo-api `ReviewCycleDtos.ReviewCycleChangeRequest`(`newDueAt` string)·`AmlReviewCycleService.requireNewDueAt`(date-only→UTC 자정 정규화)·bo-web `AmlReviewCycle` date input 계약. DB/Flyway 변경 없음. |
| 2026-07-05 | **1차 온보딩 RA 엔진 CDD 파생 API 역전파(코드=truth, feature/aml-onboarding-ra-cdd-derivation, 요구 런 11).** 1차 RA 를 엔진이 `customer.cdd.completed` 인입 시 CDD 데이터(SANCTION/PEP 명단 비교 + 국적별 리스크 + kyc_evidence)로부터 직접 산출하도록 이관. (1) **§2.1 인입 파이프라인 step 7d 콜아웃 신설** — identity projection 직후 엔진이 (a) WLF 스크리닝(SANCTION/PEP·주체 키 memberRef·idem `cdd-ra:{eventId}`) 매치 시 SCREENING=100+HIGH floor+사유+근거, (b) 국적×거주국 국가위험 정본(`LookupCountryRiskUseCase.gradeFor`) max 결합→GEOGRAPHY(PROHIBITED/HIGH=100·MEDIUM=60·LOW/미등재=15), (c) kyc_evidence→CUSTOMER=(SOF+KYC)/2 를 파생해 `aml_risk_scores` 1차 RA 를 생성(별도 evaluate 호출 없이). fail-safe=freshness boolean 선검사로 stale 시 평가 보류·CDD 인입 ACCEPTED(§15.5·§20.2, 인입 TX rollback-only 오염 없음). 파생 규칙=ACTIVE ONBOARDING 모델 `parameters`(V19) 정본·엔진 상수 하드코딩 없음. (2) **§3.3 `factors`/`highRiskCountry`/`wlfTrueMatch` 보조 입력 강등** — 온보딩 인입 경로는 엔진 파생 factors(출처 `cdd:*`)를 정본으로 쓰고, 요청 override 는 테스트·수동 재평가용 보조 입력(출처 `override` 후적용·감사, 하위호환). RA 응답 계약 변경 없음. | aegis-java-implementer(spec). 코드=truth. 근거=aml-svc `application/{port/in/DeriveOnboardingRaUseCase,usecase/OnboardingRaDerivationService}`·`AmlEventIngestService`(step 7d)·`RiskAssessmentService.materialize`(derivedFactors 정본·override 강등)·`AssessRiskUseCase.EvaluateCommand.derivedFactors`·`domain/risk/{OnboardingRaParameters,OnboardingRaFactorDeriver}`·`db/migration/V19__ra_onboarding_derivation_parameters.sql`, `scripts/demo_ingest.py`(클라 계산 제거). DB §3.9/§7 V19·기능정의서 §5.1(v9.27) 동기화. |
| 2026-07-06 | **CTR/STR 룰 발동조건 표시 + 임계·변수 편집 + TM 평가 반영 폐루프 역전파(코드=truth, feature/aml-report-rule-conditions-editing).** (1) **§2.7 report-rules 표** — 룰 상세 행에 `conditions[]`/`params[]`/`pendingParamApprovalId` 보강 + **`POST .../report-rules/{ruleCode}:update-params` 행 신설**(🔒 `REPORT_RULE_PARAM`, 승인선 `COMPLIANCE`, 룰 단위 전체 파라미터 셋 원자 제출·카탈로그 스키마 검증(editable+범위+`band_upper>band_lower`)·읽기전용 키 거부·202). (2) **§2.7 註 갱신** — bo-api subjectType 21→**22종**·감사 `REPORT_RULE_PARAM_CHANGE_SUBMITTED`(V9)·**submit-time 위임 패턴 명문화**(EXECUTED 시 엔진 admin `POST /api/v1/admin/aml/report-rules/{ruleCode}:update-params` 위임[aml-svc `ReportRuleParamAdminController`, `aml.aml_report_rule_params` V22 원자 upsert]·stub 로컬 폐루프·운영 fail-closed·STR 평가 resolve parity·CTR 임계는 `CTR_THRESHOLD` 정본 재사용). (3) **§3.6a** — `ReportRuleOverviewRow.conditions[]`(RuleConditionView, `aml:case:read` 노출 — 표시=조회/편집=admin 분리)·`ReportRuleView.params[]`(RuleParamView)·`pendingParamApprovalId` 계약 추가. | aegis-java-implementer(spec). 코드=truth. 근거=bo-api `aml/reports/{controller/AmlReportRuleController(:update-params),dto/ReportRuleDtos.{RuleConditionView,RuleParamView,ReportRuleParamUpdateRequest/Response},service/AmlReportRuleParamService}`·`aml/stats/dto/StatsDtos.ReportRuleOverviewRow.conditions`·aml-svc `adapter/in/rest/ReportRuleParamAdminController`·`application/usecase/ReportRuleParamService`·`domain/report/{RuleParamSpec,RuleConditionSpec}`. DB §3.22e/§7 V22·bo-api V9·기능정의서 §12-B.3·§03 §4.2 동기화. |
| 2026-07-06 | **CTR 임계 변경 결재함 정합(코드=truth, fix/aml-ctr-threshold-engine-approval).** §2.7 `POST /api/v1/bo/aml/ctr-thresholds/{currency}:update`를 엔진 연결 시 aml-svc admin `POST /api/v1/admin/aml/ctr-thresholds/{currency}:update` 상신 위임으로 정정. `CTR_THRESHOLD`는 aml-svc `ApprovalSubjectType`/`aml_approvals.subject_type` CHECK 20종(V23)에 포함되는 엔진 결재 대상이며 승인선은 `REPORTING_OFFICER`; AML 결재함 `GET /api/v1/admin/aml/approvals`에 노출되고 EXECUTED 시 `aml_ctr_thresholds`를 upsert한다. | 코드=truth. 근거=bo-api `AmlCtrThresholdService`·aml-svc `CtrThresholdAdminController`/`CtrThresholdManagementService`/`ApprovalDispatchService`·DB §5.16/§7 V23·IAM §4.2. |
| 2026-07-05 | **국가위험 수집 소스 제공자화 API 역전파 — EU 집행위 기본·FATF 대안(코드=truth, fix/aml-country-risk-eu-source).** FATF 페이지 403 봇 차단 대응으로 수집 소스가 제공자 선택형(`aml.country-risk.feed.provider` 기본 `EU_COMMISSION`·대안 `FATF`). **§2.7 country risk 표·일일 자동 수집 note** 를 제공자 선택형으로 갱신(EU 단일 고위험→HIGH·basis `EU_HIGH_RISK_THIRD_COUNTRY`·26개국 결정적 ISO 매핑·미매핑 skip+`unmapped`·이탈 판정=동일 제공자 provenance). **§3.12 갱신**: (1) `CountryRiskDto.provenance` enum 에 `EU_COMMISSION` 추가(V18)·`basis` 에 `EU_HIGH_RISK_THIRD_COUNTRY`·`version` 레이블 `eu-<hash>`/`fatf-<hash>`·`sourceUrl` EU/FATF. (2) `CountryRiskImportStatusDto` 소스 URL 계약 명문화 — **EU 는 `greyUrl` 에 단일 URL·`blackUrl` null(FE 는 `provider` 로 표기 분기), FATF 는 black/grey 쌍**, `provider` 는 활성 feed 값(라이브 우선). (3) `CountryRiskImportResultDto.delisted` 판정=동일 제공자 provenance ACTIVE. bo-api `Provenance` enum·`RiskBasisSource` 대칭 확장(1:1). | aegis-java-implementer(spec). 코드=truth. 근거=aml-svc `adapter/in/rest/PolicyAdminController`(`CountryRiskImportStatusDto.from`+feedProvider)·`application/port/out/CountryRiskFeedPort`(provider())·`adapter/out/feed/{Eu*,CountryRiskFeedConfig}`·bo-api `aml/countryrisk/dto/CountryRiskDtos`(Provenance.EU_COMMISSION·FeedProvider·RiskBasisSource.EU_HIGH_RISK_THIRD_COUNTRY)·회귀 `AmlCountryRiskProxyDelegationTest`. DB §3.22c/§7 V18 동기화. |
| 2026-07-05 | **국가위험 위임 계약 1:1 정합 역전파(QA 런 10 수정, 코드=truth, feature/aml-country-risk-daily-import).** §3.12 bo-api↔aml-svc 위임 계약을 필드 단위 1:1 로 교정(H-1): (1) 엔진 `CountryRiskDto.version` 은 **string**(bo-api 가 int Integer 로 오해 → string 소비·FE int 파생으로 정정), `CountryRiskImportRunDto` 에 **`runId`/`sourceCode`/`delisted` 추가**·diff 는 **ISO 코드 목록(string[])** 로 통일(bo-api 가 int 카운트로 lossy 요약하던 것을 제거 — FE 국가 목록 pill 렌더), `CountryRiskImportStatusDto` 에 **`blackUrl`/`greyUrl`(FATF 소스 URL provenance) 추가**(엔진=정본 확장), `CountryRiskImportResultDto` 는 엔진 `SyncResult` 에 없는 `sourceCode`/`importedAt` 을 bo-api 가 요청 맥락으로 채움 명문화. (2) bo-api 위임 계약 註 를 카운트→국가 목록으로 갱신. run diff `delisted` 는 run 이력에 영속(DB §3.22c diff JSONB, L-1). §3.12 DTO 표·bo-api 위임 계약 문단 갱신. | aegis-java-implementer(spec). 코드=truth. 근거=aml-svc `adapter/in/rest/PolicyAdminController`(`CountryRiskImportStatusDto`+blackUrl/greyUrl·`CountryRiskImportRunDto`+runId/sourceCode/delisted)·`application/port/out/CountryRiskSourceStorePort.CountryRiskImportRun`(runId·delisted)·bo-api `aml/countryrisk/{service/AmlCountryRiskService(engine records),dto/CountryRiskDtos}`·회귀 `AmlCountryRiskProxyDelegationTest`. DB §3.22c/§7 V17 동기화. |
| 2026-07-05 | **국가위험 FATF 일일 웹 수집 API 역전파(코드=truth, feature/aml-country-risk-daily-import).** (1) **§2.7 country risk 표에 2행 추가** — `GET .../country-risk/import-status`(FATF 일일 수집 상태: 소스 메타+최근 run diff 10건)·`POST .../country-risk:import`(수동 즉시 수집 트리거 — **결재 없음**, 동기 `SyncResult`), 둘 다 scope `aml:admin:policy`. `GET .../country-risk` 는 `countryCode` 생략 시 유효(ACTIVE) 전체 표·provenance 노출로 갱신. **일일 자동 수집 note 신설** — 스케줄러(cron 기본 `0 40 3 * * *`·enabled 기본 false·single-flight)와 수동 트리거가 동일 유스케이스, FATF black→PROHIBITED/grey→HIGH 결정적 매핑·canonical SHA-256 버전·UNCHANGED no-op·실패 fail-safe·**MANUAL 오버라이드 우선(suppressedManual)**·자동 수집은 4-eyes 비대상(시스템 provenance 즉시 ACTIVE). (2) **§3.12 `CountryRiskDto` 필드 3종 추가** — `provenance`(MANUAL/FATF_DAILY)·`sourceUrl`·`asOf`(V16) + `version` string(80)·`status`(DRAFT/ACTIVE/SUPERSEDED) 코드 정합, **`CountryRiskImportStatusDto`/`CountryRiskImportRunDto`/`CountryRiskImportResultDto` 구조 신설** + bo-api 위임 계약 註(run diff 카운트 요약·blackUrl/greyUrl·`COUNTRY_RISK_IMPORT_TRIGGERED` 감사). (3) §6 BO 매핑 country risk 행에 import 2종 반영. | aegis-java-implementer(spec). 코드=truth. 근거=aml-svc `adapter/in/rest/PolicyAdminController`(`countryRiskImportStatus`/`triggerCountryRiskImport`/`CountryRiskDto`+provenance)·`application/port/in/SyncCountryRiskUseCase.SyncResult`·`adapter/in/scheduled/CountryRiskImportScheduler`·bo-api `aml/countryrisk/{controller/AmlCountryRiskController,dto/CountryRiskDtos}`. DB §3.22c/§7 V16·기능정의서 §12-A.3 동기화. |
| 2026-07-05 | **RA-003 신원 대조 근거용 watchlist-entries `entryIds` 배치 해소 역전파(코드=truth, feature/aml-ra-detail-evidence-run7).** §2.7 명단 조회 note 에 bo-api `GET /api/v1/bo/aml/watchlist-entries` 의 **`entryIds`(콤마구분·반복 파라미터) 배치 해소 모드** 명문화 — 지정 시 다른 필터 무시·요청 순서 보존(미존재 id 누락), 위임=엔진 `?entryIds=`(200-id 청크)·비운영=stub 필터 양경로, 응답 브라우즈 동일 페이징 봉투 `WatchlistEntryPage{rows,page,size,totalElements,totalPages}`(`totalElements`=해소 성공 수), 행=공개 `WatchlistEntryDto` 필드(raw PII 미노출 불변) + 엔진 `GET /api/v1/admin/aml/watchlist-entries` 행에 batch-resolve(200-id 클램프) 註. **가정 A1(코드=truth)**: 직전 §2.7 는 브라우즈 필터만 명시하고 `entryIds` 배치 해소 파라미터 미정의 — 엔진(`WatchlistEntryQueryService.listByIds`, run2 D9)·bo-api 내부(`AmlWatchlistService.findEntriesByIds`) 기존재를 공개 컨트롤러 passthrough(`AmlWatchlistController.listEntries` `entryIds` param) 노출로 정본화. **용도**: RA 상세(AML-RA-003 ①) 신원 대조 패널이 `forcedFloorEvidence[].entryId` 를 배치 조회해 회원 신원(reveal 게이트 `POST /internal/v1/aml/pii/reveal` §2.6)과 명단 엔트리 원본값(공개 명단측만 plaintext)을 나란히 비교. **RA 응답 계약 변경 없음**(`RiskScoreResponse.forcedFloorEvidence` 불변·§3.3) — 일치 필드 하이라이트는 기존 스크리닝 상세 `matchedCandidates[].reasonCodes`(§3.2, `DOB_MATCH`/`NATIONALITY_MATCH`) 를 `screeningId`·`entryId` 로 조인해 FE 파생(가정 A2, 토큰 부재 시 graceful 생략). 재평가(ONGOING) 알림별 근거거래는 기존 `GET .../alerts/{alertId}/related-transactions`(§2.4) 재사용(신설 없음, 가정 A3). Flyway 신규 없음(aml-svc V16 미사용). | aegis-java-implementer(spec). 코드=truth. 근거=bo-api `aml/watchlist/controller/AmlWatchlistController.listEntries`(`entryIds` param)·`service/AmlWatchlistService.{listEntriesPage,findEntriesByIds,entriesByIdsPage}`(위임 200-id 청크·stub 양경로)·aml-svc `adapter/in/rest/WatchlistAdminController.listEntries`(entryIds batch-resolve)·`application/usecase/WatchlistEntryQueryService.listByIds`. Flyway/DB 변경 없음. |
| 2026-07-05 | **RA 점수 목록 페이지 봉투 역전파(코드=truth, fix/aml-ra-envelope-fds-spec-backprop).** §2.3 `GET /api/v1/admin/aml/risk-scores` 응답을 배열 `RiskScoreResponse[]` → **페이지 봉투 `RiskScoreListResponse{ items: RiskScoreResponse[], page, size, total }`**(§1.2 envelope 원칙 정합 — `total`은 페이지 무관 전체 건수로 타일↔목록 정합·페이지 이동)로 정정. 생산자 `RiskScoreAdminController.list` 가 `RiskScoreListResponse(items,page,size,total)` 봉투를 반환하나 문서는 배열로 명시(§2.3 미명시 지점 — 가정 G-H1: 생산자 코드=truth 를 정본으로 봉투 채택)해 bo-api 소비자(`AmlRaService.ENGINE_RISK_SCORES` bare array 기대)가 위임 시 Jackson MismatchedInputException 500 을 냈다. bo-api 를 봉투 소비(`.items()` 추출)로 정합화한 코드 변경(회귀 `AmlRaProxyDelegationTest`)의 동일 작업 단위 역전파. | aegis-spec. 코드=truth. 근거=aml-svc `adapter/in/rest/RiskScoreAdminController.{list,RiskScoreListResponse}`·bo-api `aml/ra/service/AmlRaService`(`EngineRiskScorePage` 봉투 소비). §1.2 envelope 정합. |
| 2026-07-05 | **TM 알림·케이스·보고·결재 흐름 정합(엔진 계약) 역전파(코드=truth, fix/aml-tm-case-report-approval-flow-20260705).** (1) **§2.4 알림 목록** — `GET /api/v1/aml/alerts` 를 표에 명시, `status` optional(미지정=전 상태, `defaultValue="DETECTED"` 드리프트 해소·D1) + `channel`/`corridor` evidence 대표값 클라이언트측 필터(D6·G2 1단계) 추가. (2) **§2.7 보고 목록** — `GET .../reports` `status` optional(미지정=전 상태, `defaultValue="DRAFT"` 드리프트 해소·D11), 응답 `ReportSummary` 에 `createdAt`·`reportDeadlineAt`(=DB `due_at`) 추가(위임 경로 SLA 뱃지·기간 필터 결함 D12 해소, slaStatus 는 back-office 파생 G8). (3) **§3.5 CaseDto/CreateCaseRequest** — `originScreeningId` 를 `string`(VARCHAR(96)·DB §3.11 V15, FK 아님·문자열 토큰)으로 정정, `CreateCaseRequest` 에 `originAlertId`/`originScreeningId`/`eddTrigger` 발단 계보 영속(생성→재조회 실값, D5·D8). (4) **§3.7 ApprovalDto** — `submittedAt`(=DB `created_at`)·`stagedPayload`(=DB `staged_payload`, 상신 내용·변경 전→후 파생) 추가 + 위임 응답 parity 각주(정렬·만료·변경내역 null 결함 D13 해소, submittedAt=created_at 매핑·신규 컬럼 없음·G5). stub↔엔진 위임 응답 동형·prod fail-closed 불변. | aegis-java-implementer. 코드=truth. 근거=aml-svc `AlertController`(queue status optional·channel/corridor)·`RegulatoryReportController.ReportSummary`(createdAt·reportDeadlineAt)·`CaseQueryController.{CreateCaseRequest,CaseDetail}`+`Case.originScreeningId`(V15)·`ApprovalController.{ApprovalSummary,ApprovalDetail}`(submittedAt·expiresAt·stagedPayload)·`domain/approval/ApprovalRequest`. DB §3.11 V15·§3.16(submittedAt/staged_payload) 동기화. |
| 2026-07-05 | **FP whitelist 등록 메타(V14) 동반 API 정정 역전파(코드=truth, fix/aml-fds-spec-backprop-20260704).** DB §7 V14(`aml_fp_whitelist` reason·expires_at·screening_id, §3.8a)에 맞춰 동반 API 필드를 코드 정본으로 일치화: (1) **§3.2 `ScreenResponse.matchedRules`** — 스키마 `{ruleCode, threshold}`→`{ruleCode, threshold, score}`(엔진 WLF 룰 score 투영, `ScreeningResponse.matchedRules[].score` 코드=truth) + OpenAPI `RuleRef.score` 추가. (2) **§3.2 `ScreenResponse`에 `createdAt`(string(date-time), 미영속 결과 null 가능·`ScreeningController.ScreeningResponse.createdAt` 코드=truth) 행 추가** + OpenAPI `ScreenResponse.{decidedAt,createdAt}` 추가. (3) **§10 WLF 판정 폐루프 예외 규칙 명문화** — `ESCALATED`=staging(checker 승인 EXECUTED 시점 반영)·`AUTO_DISCOUNTED`=FP whitelist 등록 즉시 적용(4-eyes 우회, expires_at 만료 후 미적용). 미정의 승인 주체는 코드 `subjectType`(WLF_DECISION·FP_WHITELIST) 기준(가정 B). (4) **§2.3 Screening 검토 `POST .../screenings/fp-whitelist` `FpWhitelistRegisterRequest` 신설** — 단건 `matchedEntryId`(discount 슬롯·엔트리 id)·`screeningId`(발원 결과 id·별개 슬롯)·`targetRef`/`targetType`·`makerId`·`reason`·`expiresAt`(null=무기한, EXPIRED 파생) 필드(DB §3.8a V14 1:1). **가정 C 정정**: 초안의 `entryIds` **배치** 가정을 코드=truth(단건 `matchedEntryId`, bo-api `FpWhitelistRegisterRequest`·aml-svc `WhitelistCommand`) 로 철회 — 배치 필드 없음. | data-modeler. 코드=truth. 근거=aml-svc `adapter/in/rest/ScreeningController.ScreeningResponse`(score·createdAt)·`application/usecase/{ScreeningReviewService,FpWhitelistService}`·`application/port/in/WhitelistFalsePositiveUseCase.WhitelistCommand`(ESCALATED staging vs AUTO_DISCOUNTED 즉시·단건 matchedEntryId)·bo-api `aml/screening/dto/ScreeningDtos.{MatchedRule.score,FpWhitelistRegisterRequest,FpWhitelistStatus.EXPIRED}`·`db/migration/V14__fp_whitelist_registration_metadata.sql`. DB §3.8a/§7 V14 동기화. |
| 2026-07-05 | **RA 4-eyes 작성자(maker) 서버 파생 전환 역전파(코드=truth, fix/aml-ra-4eyes-maker-trust-boundary).** RA write 3경로(draft·activate·override)가 작성자를 요청 본문 `makerId`(비신뢰 클라이언트 입력)로 신뢰하던 신뢰경계 결함을 형제 서비스(PEP 승인·CDD 재이행 주기)와 동형으로 정정: 작성자는 인증 principal(`principal.email()`)에서만 서버 파생하고(미인증 상신 거부), bo-api BFF 계약 `RaDtos.{DraftRequest, ActivateRequest, OverrideRequest}` 에서 `makerId` 필드·`@NotBlank` 제거. (1) **§2.7 `POST .../ra-models`(draft)·`.../versions/{v}:activate`** 행에 maker 서버 파생 註 추가. (2) **§3.3 `RiskOverrideRequest` 하단 註** 를 draft/activate/override 3경로 공통으로 일반화. 엔진 위임·감사 payload 의 maker 는 서버 파생값 유지(계약 필드명 불변). | aegis-java-implementer. 코드=truth. 근거=bo-api `aml/ra/service/AmlRaService.requireMaker(BackofficePrincipal)`(3 호출부 `principal` 전환)·`aml/ra/dto/RaDtos.{DraftRequest,ActivateRequest,OverrideRequest}`(makerId 제거). Flyway/DB 변경 없음. `:bo-api spotlessCheck·test(985)·bootJar` 그린. |
| 2026-07-05 | **RA 근거 계약 정합·FE↔BE `listType` 통일 역전파(코드=truth, fix/aml-ra-flow-backprop).** FE↔BE 근거 필드 계약 단절(FE 오기대 `matchType`/`sourceCode` → 상세 탭 `undefined.toUpperCase()` 크래시) 해소를 코드=정본으로 문서 일치화: (1) **§3.3 `RiskScoreResponse`** — `forcedFloorEvidence[]`(당연고위험 강제 상향 근거, 원소 `{listType,screeningId,entryId,label}` masked 참조 토큰·raw PII 없음)·`operativeNextReviewDueAt`(운영 재심사일=회원 주기 수동조정 승인 반영, FE '재심사일' 우선·부재 시 `nextReviewDueAt` 폴백) 행 추가. (2) **`RiskOverrideRequest`** — `targetRef`(오버레이 폐루프 키·현재등급 산출 기준, 미전달 시 scoreId graceful fallback)·`currentGrade`(화면 표시 현재등급 대조 힌트) 행 추가. (3) **§3.15 `SimulationResponse`** — `baselineDistribution`(기준 분포·증감 기준선, nullable) 추가·`falsePositiveImpact` nullable 명시 + `RaSimulateRequest`=`{modelVersion,samplePopulation}` 로 확정하고 **구 `factorWeightOverrides`(dead 필드) 제거** 명문화. (4) **§2.7 RA 점수 목록** — `country` 필터 파라미터 추가. (5) **§2.3 명단 엔트리 브라우저 딥링크 계약 신설** — `/aml/watchlist?listType=<listType>&entry=<entryId>`(BE 제공 토큰만), 구 `?source=<sourceCode>` 폐기. | aegis-java-implementer. 코드=truth. 근거=bo-api `aml/ra/dto/RaDtos.{RiskScore.forcedFloorEvidence,ForcedFloorEvidence,RiskScore.operativeNextReviewDueAt,OverrideRequest.{targetRef,currentGrade},RaSimulateRequest,SimulationResponse.baselineDistribution}`·aml-svc `adapter/in/rest/RiskScoreAdminController`(country 필터)·bo-web `components/common/WatchlistMatchEvidencePanel`·`lib/aml-risk.AmlForcedFloorEvidence`(listType). DB §7 V13 동기화. |
| 2026-07-04 | **2차 상시 RA(ONGOING) 모델 실환경화·응답 필드 역전파 — `parameters`·`reassessmentAlerts`·`reviewShortened`(코드=truth, V12).** 직전 행(ONGOING=DRAFT placeholder·다음 단계 예정)의 다음 단계를 반영: (1) **§2.7 `GET/POST .../ra-models`** — 응답 `RaModelSummary`·요청 `DraftRequest` 에 **`parameters`(JSON, DB §3.9 `aml_risk_models.parameters` 1:1)** 노출. ONGOING 모델은 트리거·룰 심각도 가중·lookback·최근성·1차 baseline 결합·주기 단축·EDD 임계 정의를 담고 ONBOARDING 은 `{}`. (2) **§3.3 `RiskScoreResponse` 필드 3종 신설** — `scenario`(ONBOARDING/ONGOING·graceful 기본 ONBOARDING)·`reassessmentAlerts[]`(2차 재평가 유발 STR/CTR 알림 계보, 엔진 `factorBreakdown.triggerAlerts` 파생, 1차는 빈 배열)·`reviewShortened`(재이행 주기 단축 from→to, 앞당기기만, 미단축 시 null). (3) **§507 후주 정정** — ONGOING 을 "DRAFT placeholder 자리만"→**실운영 `KR_ONGOING_RA v1 ACTIVE`, 정의는 모델 `parameters` 로 노출**. bo-api `RaDtos.{RaModel.parameters,RaModelVersion.parameters,RiskScore.{scenario,reassessmentAlerts,reviewShortened},ReassessmentAlert,ReviewShortened}` 1:1. | aegis-spec. 코드=truth. 근거=bo-api `aml/ra/dto/RaDtos`·`aml/ra/service/AmlRaService`(3필드 passthrough)·aml-svc `db/migration/V12__ra_ongoing_model_activation.sql`·`domain/risk/{OngoingRaParameters,OngoingRaFactorDeriver}`·`application/usecase/OngoingRaService`. DB §3.9/§7 V12·기능정의서 §6.1 BR-006 동기화. |
| 2026-07-04 | **RA 모델 시나리오 파라미터·응답 필드 역전파(코드=truth, feature/ra-onboarding-lifecycle).** (1) **§2.7 Admin API RA 모델** — `GET .../ra-models` 응답 `RaModelSummary[]` 각 행에 `scenario`(ONBOARDING/ONGOING, DB §3.9 `aml_risk_models.scenario`) 노출, `POST .../ra-models` draft 요청 `DraftRequest` 에 **`scenario?`(옵션, 미지정 시 ONBOARDING — 엔진 `RiskModelAdminController.draft` default)** 추가. (2) RA 모델 응답 DTO 에 `scenario` 필드 노출(bo-api `RaDtos.RaModel.scenario`·`RaModelVersion.scenario` 버전 승계) — `ONBOARDING`(1차 온보딩) / `ONGOING`(2차 상시). 2차 상시(`ONGOING`)는 DRAFT placeholder 로만 시딩(활성화·거래가중 재평가·주기 단축·EDD 자동 개시는 다음 단계 예정, 기능정의서 §6.1 BR-006). | aegis-spec. 코드=truth. 근거=aml-svc `adapter/in/rest/RiskModelAdminController`(draft `scenario` default ONBOARDING)·`domain/enums/RaScenario`·`domain/risk/RiskModel.scenario`, bo-api `aml/ra/dto/RaDtos`(RaScenario·RaModel/RaModelVersion.scenario). DB §3.9/§7 V11·기능정의서 §6.1 동기화. |
| 2026-07-04 | **related-txn 회원/수취인 필드 + flat canonical payload 정본 역전파(코드=truth, fix/related-txn-required-fields).** (1) **§3.4a evidence `relatedTransactions[]`** — `memberRef`(비PII 회원 업무참조=originator.partyReference, evidence JSONB 영속 허용) 키 추가하고 `AlertEvidence.RelatedTransaction.asMap()` 순서와 1:1 정합, `counterpartyName`(수취인 원문 이름)은 evidence 영속 금지·read-path vault reveal만임을 명문화. (2) **§3.4d `RelatedTransactionDto` 표** — `memberRef`·`counterpartyName` 2행 추가(`AlertController.RelatedTransactionDto` 11필드 1:1) + 각주에 counterpartyName read-path reveal·null 폴백 명문화. (3) **§2.1a 엔진 저장 flat canonical payload 표 신설** — `flatPayload` 14키 + product 신호 전수, `corridor` 서버 파생 규칙(`aml.neutral.regulatory-country` 기본 PH·DOMESTIC→`{reg}-{reg}`·CROSS_BORDER→`{reg}-{dest}`)·`counterpartyRef` 단일화(해외=counterparty 안정키·국내=예금주 토큰) 명문화, §4.2 corridor object(입력 상세)와의 상충 해소(입력 nested vs 저장 flat 문자열). | aegis-spec. 코드=truth. 근거=aml-svc `AlertController.RelatedTransactionDto`·`AlertEvidence.RelatedTransaction`·`NeutralTransactionEventService.{flatPayload,corridor,resolveCounterpartyRef,addProductSignals}`. integration §59 동기화. |
| 2026-07-04 | **(H2) 국내송금 양당사자 WLF 스크리닝 역전파(코드=truth, fix/aml-fds-spec-backprop).** **§2.2 Screening API 콜아웃** — WLF 스크리닝 대상 범위를 "해외송금 sender+receiver + 비-cross-border sender-only" → **"해외송금(`CROSS_BORDER_REMITTANCE`) + 국내송금(`DOMESTIC_TRANSFER`) 양당사자 sender(`CUSTOMER`)+receiver(`COUNTERPARTY`)"** 로 확장. sender-only 잔여를 회원가입·월렛충전·월렛결제(비-송금)로 축소(국내송금 제거). 국내송금 receiver 는 수취계좌 명의인/PH fallback best-effort 매칭, `subjectIdentity` 4필드(NAME/NATIONALITY/GENDER/DOB) 주체 무관 균일 동일 적용. 엔진 도메인 비변경 — 데모/시뮬레이터/시드 한정. | aegis-spec. 코드=truth. 근거=aml-svc `NeutralTransactionEventService.RECEIVER_SCREEN_PRODUCTS`(`CROSS_BORDER_REMITTANCE`+`DOMESTIC_TRANSFER`)·`screenCounterpartyBestEffort`(`TargetType.COUNTERPARTY`)·`NeutralTransactionEventServiceTest`(DOMESTIC_TRANSFER co-screen). |
| 2026-07-04 | **(H1) 알림 발동 근거 거래 조회 엔드포인트 역전파(코드=truth, fix/aml-fds-spec-backprop).** (1) **§2.4 TM API 표에 행 추가** — `GET /api/v1/aml/alerts/{alertId}/related-transactions?page=&size=`(scope `aml:case:read`) 발동 근거 거래 서버 페이징(요구2·A8, 발동 룰 윈도우 근거 거래 전수, 20행 evidence 캡과 별개). (2) **§3.4d `RelatedTransactionsResponse` DTO 신설** — 코드 `AlertController.RelatedTransactionsResponse`(rows/page/size/totalCount/ruleCode/window/dimension) + `RelatedTransactionDto`(transactionRef/counterpartyRef/direction/amount/currency/channel/corridor/occurredAt/fdsDecisionRef) 1:1 전사. party 식별정보는 §3.2 `subjectIdentity` 규약 상속(마스킹 토큰 + reveal 가능 필드 키만·raw PII 미포함, 원문은 `aml:pii:reveal`+`RAW_DATA_ACCESS` 경로). | aegis-spec. 코드=truth. 근거=aml-svc `adapter/in/rest/AlertController`(GET related-transactions·`RelatedTransactionsResponse`/`RelatedTransactionDto`)·port `QueryAlertRelatedTransactionsUseCase`·usecase `AlertRelatedTransactionsService`. sass §02-amlSvc 동기화. |
| 2026-07-04 | **중립(canonical) 수집 API 역전파(코드=truth, feature/aml-neutral-canonical-ingest).** (1) **§2.1a 신설** — `POST /aml/v1/transaction-events`(scope `aml:event:write`, 헤더 `Tenant-Id`/`Idempotency-Key`/`X-Trace-Id`) 엔드포인트 행 + 요청 Envelope 스키마 표(공통 15필드) + 상태코드 매핑(202/200/409/422) + 422 검증 규칙 7항(가정 G3 baseCurrency=테넌트 규제통화 fail-closed) + family 매핑 표(5 product → canonical eventType·EventFamily·channelType, 가정 G1 CARD_PAYMENT→transaction 재사용·enum 무확장, WALLET_TOPUP→CASH_IN 만 CTR 현금성) + CTR 순증(net) 규칙(가정 G4 reversal 음수 signed amount) + PII 토큰화 경계(가정 G7/G9) + 응답 계약(가정 G6 accepted+평가요약, HOLD 미구현). (2) **§3.17 신설** — `NeutralEventRequest` Party·Amounts·5 product 블록 스키마 표(엔진 domain record 1:1, STR 신호 결선 가정 G5, 신규 룰코드 없음). 기존 canonical `/api/v1/aml/events`(§3.1)와 별개 공개 수집 표면. | aegis-java-implementer. 코드=truth. 근거=aml-svc `adapter/in/rest/NeutralTransactionEventController`·`application/usecase/NeutralTransactionEventService`·`application/port/in/IngestNeutralTransactionEventUseCase`·`domain/neutral/{NeutralEnums,ProductEventTypeMapper,NeutralEventValidator,NeutralParty,NeutralAmounts,NeutralProductBlocks,NeutralTransactionEvent}`. 정본 요구=`docs/aml-data.md` §2~§9. |
| 2026-07-04 | **회원별 CDD 재이행 주기 관리 역전파(코드=truth, feature/cdd-review-cycle-management, b067310).** (1) 엔진 `GET /api/v1/admin/aml/customers/review-cycle`(bo-api 위임 `GET /api/v1/bo/aml/customers/review-cycle`) — 등록 회원 전체 검색: `customerRef`(부분일치)·`riskGrade`·`kycStatus`·`country`·`pep`·`dueFrom`/`dueTo`(next_review_due_at 범위, 임박순 정렬)·`customerType` 필터 + 페이징 봉투 `{rows,page,size,totalElements,totalPages}`, 행에 최신 RA 점수/모델 조인(N+1 없음). (2) `POST /api/v1/bo/aml/customers/{customerRef}/review-cycle:change` — next_review_due_at 수동 조정 **4-eyes 상신**(newDueAt·reason 필수, PERIODIC_REVIEW_CHANGE 감사, 결재 승인 전 미반영·maker 신뢰경계 검증). 화면: 고객위험·심사 §CDD 이행 주기 관리(/aml/customers/review-cycle) — 기존 EDD 임박 큐(운영 대기열)와 역할 구분. | aegis-java-implementer. 코드=truth. 근거=aml-svc `CddReviewCycleController`·bo-api `reviewcycle` 피처·bo-web `AmlReviewCycle`. |
| 2026-07-04 | **TM 알림 목록 서버 페이징 offset 정합(코드=truth, fix/list-server-pagination).** §2.5a `GET /api/v1/bo/aml/alerts`의 `page` 파라미터가 병합·필터 후 **offset(skip=page×size)으로 실제 적용**됨을 명문화 — 기존 구현은 limit만 적용해 모든 page가 첫 페이지를 반환(목록 화면이 전건을 못 보던 결함). 엔진 위임·stub 양 경로 동일 적용, total 메타 없는 배열 응답 불변(bo-web은 반환 길이<size로 마지막 페이지 판정하는 prev/next 페이저). | aegis-java-implementer. 코드=truth. 근거=bo-api `AmlTmService.listAlerts`(skip(page×limit) 엔진·stub 양 경로). |
| 2026-07-04 | **워치리스트 엔트리 브라우즈 조회 확장 역전파(코드=truth, feature/watchlist-entries-browser).** §2.3 `GET /api/v1/bo/aml/watchlist-entries`(위임: 엔진 `GET /api/v1/admin/aml/watchlist-entries`)에 필터 추가 — `name`(이름 토큰 부분일치·대소문자 무시, normalized_tokens), `country`(ISO-2, attributes.country), `addedFrom`/`addedTo`(created_at 범위 — 날짜별 추가분), `version`(수집 버전), 기존 `sourceCode`/`listType`/`status` 유지. 응답을 배열 → **페이징 봉투 `{rows, page, size, totalElements, totalPages}`**(FDS DecisionPage 명명 일관)로 전환, bo-api passthrough(total 유실 방지). 행: normalizedTokens(공개 명단 원문 토큰)·listType·subjectKind·country·nationality·dob·program·version·status·createdAt·externalRef. 실데이터 42,572건 E2E(이름 ABBAS 110·국적 EG 166·복합 2) 정합. | aegis-java-implementer. 코드=truth. 근거=aml-svc `WatchlistAdminController.listEntries`·`WatchlistEntryQueryService`·bo-api `AmlWatchlistController`. DB V10 인덱스(02-aml-db). |
| 2026-07-03 | **레거시 시나리오 알림 발동 룰 표시 폴백(코드=truth, fix/aml-tm-rule-alert-evidence).** §3.4a `AlertDto` 테이블에 **`ruleCode`(string\|null)** 행 신설 — bo-api `AlertSummary`/`AlertDetail` 매핑 필드로, 정상 CTR/STR 룰 경로는 `AmlReportRuleCode.name()`(예 `STR_VELOCITY_CASH`)이고 엔진이 top-level `ruleCode` 없이 `scenario_code`만 실은 **레거시 시나리오 경로 알림**(예 `STRUCTURING`, `AmlReportRuleCode` 미파싱)은 발동 룰 표시가 비지 않도록 `evidence.trigger.scenarioCode` → 엔진 `scenarioCode` 문자열로 **폴백**함을 명문화. `AmlReportRuleCode` enum 계약 무변경(레거시 코드는 문자열로만 표시), JSON 직렬화 형태 `string\|null` 불변(bo-web `ruleLabel` 문자열 폴백 보유로 무변경). bo-api `AlertSummary`/`AlertDetail.ruleCode` 타입을 enum→String 완화(내부 룰 필터·멱등 키는 `.name()` 정합). | aegis-java. 코드=truth. 근거=bo-api `TmDtos.AlertSummary/AlertDetail.ruleCode`(String)·`AmlTmService.engineRuleCode`/`triggerScenarioCode`/`matchesAlertSummary`. **아울러 §3.4a `evidence` 행에 CTR/STR 룰 경로 변형을 명문화** — 룰 카탈로그 발동 알림의 ① 트리거 `{ ruleCode, strReasonCode(STR만), description }`, ② 실측 윈도우 집계(CTR=(member,bankingDay) 현금 합산·실측 건수 / STR=주체 rolling 24h; 수치 임계 룰만 threshold/thresholdMet), ③ `relatedTransactions[]`=주체 윈도우 형제거래(캡 20·빈 윈도우 단건 폴백), ④ `fundGraph`=윈도우 거래 있으면 `CANONICAL_EVENTS` 실 그래프·무거래 시 `PLACEHOLDER` + `features`·`watchlistMatch`, 윈도우 조회 실패 fail-safe. 근거=aml-svc `TmAlertEvidenceAssembler`·`CtrEvaluationService.persistCtrAlert`·`StrEvaluationService.persistStrAlerts`. DB §3.10 동기화. |
| 2026-07-02 | **데모 데이터 정직화 — 회원 등록 인입 이벤트·스크리닝 실 레코드 명문화(코드=truth, feature/aml-demo-data-honesty, 기능정의서 v9.27).** (1) **§3.1 인입** — 데모 회원 등록 인입 이벤트(`{eventType:"member", member:{memberRef,name,nationality,gender,dob,declaredIncomePhp}}`)→인메모리 member vault(회원 identity·신고소득 유일 원천·미등록 회원 identity 룰 skip) + 거래 payload `senderHolderName`(nullable, STR_THIRD_PARTY 실신호) 명문화, hash 파생 회원 프로필 폐기. (2) **§3.2 스크리닝** — 데모 큐/상세=송금 인입당 sender(CUSTOMER)+receiver(COUNTERPARTY) 2건 실매칭 레코드(인메모리·상한·transactionRef 쌍 그룹·랜덤 UUID screeningId, 데모 멤버 즉석 행·hash 인코딩 id 폐기, 미지 id not-found), 밴딩 엔진 동형(≥0.66 POSSIBLE·TRUE_MATCH=4-eyes만), **부분 식별[이름+국가] 수취인 overall 상한 0.65 자동 NO_MATCH(FuzzyMatchEngine 전체 가중치 합 정규화 동형, TM 명단 룰 nameScore 축과 비대칭=의도된 정직 동작)**, FP 화이트리스트 시드 폐기·벌크런 실카운트. 비-prod 전용(위임/prod 불변). DB 스키마 무변경. | aegis-spec. 코드=truth. 근거=bo-api `AmlDemoMemberVault`·`AmlScreeningRecordStore`·`AmlScreeningService`·`AmlTmService`(라이브 결선·senderHolderName)·`IngestTestController`. 기능정의서 §1.11 BR-DEMO-HONESTY·§3.2·§7.1·§9.1·§12.2·integration §4 동기화. DB 불변. |
| 2026-07-02 | **명단 룰(STR_PEP·STR_SANCTION) 발동 = 실명 매칭 + 송금 수취인 정보 규격 가산(코드=truth, feature/aml-tm-real-watchlist-matching, 기능정의서 v9.26).** (1) **§3.4a `evidence.watchlistMatch`** — `nameScore`(이름 sub-score, **데모 발동 기준 = nameScore ≥ 0.92**, WLF TRUE 임계값을 이름 축에 적용)·`matchReasonCodes[]` 가산, `matchScore`=실제 overall 복합점수·`entryName` 등 lineage=실매칭 엔트리(hash 합성 발동·임의 엔트리·가공 점수 폐기). `partyIdentity` 는 채널별 가용 필드만(국내 [NAME]/해외 [NAME,NATIONALITY]). (2) **§3.4 인입 payload** — `HanpassPhTransactionPayload` 에 `receiverName`·`receiverCountry`(nullable, additive) 명문화, 수취인 정보 규격(국내=이름만/해외=이름+국가, 성별·생년월일 미제공)·`receiverRef`=sha256(name\|country) 파생. 엔진 evaluate 바디는 수취인 원문 미탑재(COUNTERPARTY 스크리닝 계보로만 평가). 데모 자동 발동은 [스크리닝 매칭→분석가 4-eyes 확정→STR] 폐루프 압축 근사(실엔진 라이브 0.66 POSSIBLE 캡·TRUE_MATCH=분석가 확정·회원 발동 pep_flag). DB 스키마 무변경(JSONB 확장). | aegis-spec. 코드=truth. 근거=aml-svc `StrEvaluationService`·`FuzzyMatchEngine`·`MatchRuleSet`(0.92)·`WlfScreeningService`(0.66 POSSIBLE 캡), bo-api `AmlStrLiveReportStore`·`AmlWatchlistMatchLineage`·`AmlDemoPiiCatalog`·`HanpassPhTransactionPayload`(receiverName·receiverCountry). 기능정의서 §7.1 BR-011/013·integration §4.2 동기화. DB 불변. |
| 2026-07-02 | **송금 거래 STR_PEP·STR_SANCTION 을 회원+수취인 당사자별 동시 평가 — 매칭 당사자 구분 가산(코드=truth, feature/aml-tm-receiver-screening, 기능정의서 v9.25).** (1) **§3.4a `evidence.watchlistMatch`** — `matchedParty`(MEMBER\|RECEIVER)·`partyRef`·`partyIdentity`(bo-api read-time projection, 매칭 당사자 식별정보 비교 메타 `SubjectIdentity` 동형)·`additionalMatches[]`(양당사자 동시 매칭 시 나머지 당사자, 동일 스키마, 대표=회원 우선) 확장. 송금 채널(DOMESTIC_REMIT·CROSS_BORDER_REMIT)만 수취인 COUNTERPARTY 스크리닝 계보(transactionRef 그룹·TRUE_MATCH 우선)로 RECEIVER 평가, 부재 시 skip(합성 신호 없음). (2) **§3.6 `reportPayload`** — STR 보고 payload `watchlistMatches[]` 항목에 matchedParty·partyRef·additionalMatches 동반. (거래·룰)당 알림 1건 유지. DB 스키마 무변경(JSONB 확장). | aegis-spec. 코드=truth. 근거=aml-svc `StrEvaluationService`(당사자별 평가·`findCounterpartyScreenings`)·`AlertEvidence.WatchlistMatch`(matchedParty·additionalMatches), bo-api `AmlTmService`(partyIdentity read-time projection)·`AmlStrLiveReportStore`. 기능정의서 §7.1 BR-011/012 동기화. DB 불변. |
| 2026-07-02 | **명단 룰(STR_PEP·STR_SANCTION) 알림 상세에 WLF 동형 식별정보 비교(subjectIdentity·entryIdentity) 가산(코드=truth, feature/aml-tm-watchlist-identity-compare, 기능정의서 v9.24).** (1) **§3.4a AlertDto** — `subjectIdentity`(원거래 대상 회원, 공용 `SubjectIdentity` 타입 §3.2, `{targetRef, fields[]}`) 가산 행 + `evidence.watchlistMatch.entryIdentity`(명단 엔트리, `{entryRef, fields[]}`, `fields ⊆ [NAME,NATIONALITY,GENDER,DOB]` 중 서버 가용 필드만) 확장. 명단 룰 단건 상세 한정·bo-api read-time projection(엔진 API 무변경)·raw PII 미포함(reveal 키만). (2) 열람은 기존 `POST /bo/aml/pii/reveal`(§2.6, `aml:pii:reveal`+`RAW_DATA_ACCESS`) 재사용 — 신규 엔드포인트 없음. identity 부재(구 알림·fallback) 시 null/생략. | aegis-spec. 코드=truth. 근거=bo-api `AmlTmService`(subjectIdentity·entryIdentity read-time projection)·`ScreeningDtos.SubjectIdentity`(공용)·`PiiRevealService`. 기능정의서 §7.1 BR-011 동기화. DB 불변. |
| 2026-07-02 | **STR_PEP·STR_SANCTION 알림 evidence 에 WLF 동형 명단 매칭 근거(watchlistMatch) 가산(코드=truth, feature/aml-tm-pep-match-evidence, 기능정의서 v9.22).** (1) **§3.4a AlertDto `evidence`** ⑤ `watchlistMatch` 신설(`listType`·`entryId`·`entryName`(WLF 마스킹 토큰)·`sourceCode`·`provider`·`matchScore?`·`screeningRef?`·`origin`(WATCHLIST_MATCH\|KYC_PEP_FLAG)) — 엔진은 대상 최신 스크리닝 매칭 엔트리 중 룰 listType 일치 항목을 계보로, 부재 시 KYC_PEP_FLAG 정직 fallback, 다른 룰 미포함. (2) **§3.6 `reportPayload`** — STR 보고 payload 에 `watchlistMatches[]`(알림과 동일 lineage) 명시. DB 스키마 무변경(evidence/payload JSONB 확장). | aegis-spec. 코드=truth. 근거=aml-svc `StrEvaluationService`(resolveWatchlistMatch)·`AlertEvidence.WatchlistMatch`·`WatchlistEntryStorePort.findByEntryId`, bo-api `AmlStrLiveReportStore`·`AmlTmService`. 기능정의서 §7.1 BR-011 동기화. DB 불변. |
| 2026-07-02 | **TM 알림 발동을 CTR/STR 룰 카탈로그로 한정 — 레거시 시나리오 발동 폐기 역전파(코드=truth, fix/aml-tm-ctr-str-rule-scope, 기능정의서 v9.21).** (1) **§3.4a AlertDto** — `scenarioCode` 필드를 **`ruleCode`**(CTR/STR 룰 코드 `AmlReportRuleCode`, nullable)로 교체(JSON 필드명 `ruleCode`), 심각도 매핑(제재매칭 RESTRICT=CRITICAL·그 외 STR=HIGH·CTR=MEDIUM) 명문화. `evidence.트리거` 를 `{ ruleCode, strReasonCode(STR 룰만), description(룰 자연어) }` 로, 집계 패턴을 CTR(주체·영업일 현금 합산)/STR(주체 rolling 윈도우)로 정합(레거시 시나리오 계열 THRESHOLD/SIGNAL 프레이밍 폐기). (2) **§2.5a bo-api `GET /bo/aml/alerts`** — 목록 필터 파라미터 `scenario`→**`rule`**(문자열 룰 코드 매칭, aml-svc `GET /aml/alerts?rule=` 위임 정합). (3) **§3.4 TransactionEvaluateResponse·§5 OpenAPI 스니펫** — `scenarioCode`→`ruleCode`(enum=CTR/STR 10종), TM 알림은 발동 룰마다 하나씩 반환. | aegis-spec. 코드=truth. 근거=aml-svc `application/usecase/{TmEvaluationService,CtrEvaluationService,StrEvaluationService}`·`adapter/in/rest/AlertController`(AlertDto.ruleCode·rule 필터)·`db/migration/V7__tm_alert_rule_codes.sql`, bo-api `AmlTmService`·`TmDtos`. 기능정의서 §7.1 BR-010·DB §3.10/§마이그레이션(V7) 동기화. |
| 2026-07-01 | **CTR/STR 모니터링 통합 역전파(코드=truth, feature/aml-ctr-str-monitoring).** (1) **§2.7 CTR/STR 룰·임계 관리 하위표 신설** — `GET/GET{ruleCode}/POST{ruleCode}:activate report-rules`(🔒 `REPORT_RULE`, 시뮬레이션 요약·STR_MANUAL manual-only 거부)·`GET/GET{currency}/POST{currency}:update ctr-thresholds`(🔒 `CTR_THRESHOLD`, hot-reload 우회 불가) 6행 + read overview(§3.6a)와 별개 명시. 당시 subjectType은 bo-api 애플리케이션 계층으로 표기했으나, 현행은 `CTR_THRESHOLD`가 aml-svc 엔진 결재 대상(V23)이다. (2) **§3.6 `reportDeadlineAt`** — 기한을 Policy Pack 옵션으로 정정: PH_AMLC pack(CTR 거래일+5영업일 17:00 PHT·STR 의심확정+5영업일, 코드=truth)과 KR default pack(CTR+30일·STR+3영업일 §14.4)을 상호 배타 옵션으로 명시(충돌 해소). (3) **§11 CTR/STR 보고 룰 엔진 계약(§14 계열) 신설** — BR-403(TEMP_FREEZE>STR>CTR), 영업일 캘린더/bankingDayKey/17:00 PHT, 룰 카탈로그 10종 표(CTR_SINGLE·CTR_DAILY + STR 8종 + STR_MANUAL DRAFT), CTR freeze/집계(BR-501)·부분 UNIQUE, STR 사유코드 UPSERT, PII sha256 eAMLA ProviderSvc 위임(`amlc_submission_ref`, BR-601). | aegis-spec. 코드=truth. 근거=bo-api `AmlReportRuleController`(report-rules)·`AmlCtrThresholdController`(ctr-thresholds)·`AmlReportRuleService`(STR_MANUAL manual-only 거부), aml-svc `domain/report/{AmlReportRuleCatalog,BankingCalendar}`·`domain/enums/{AmlReportRuleCode,StrReasonCode}`·`application/usecase/{CtrEvaluationService,StrEvaluationService,TransactionReportSideEffectRunner}`·`adapter/out/submission/MockAmlcSubmissionAdapter`. DB §3.12/§3.22a/§3.22b/§5.16·integration §3.4·기능정의서 §7/§9.1/§12-B.3 동기화. |
| 2026-07-01 | **AML TM 라이브 인입 룰베이스 평가 정합(코드=truth) — 채널→시나리오 하드매핑 폐기.** (1) **§3.4a `evidence` 집계 패턴** — 건수 기반 시나리오용 `countThreshold`, 다상대 시나리오(ROUND_TRIPPING/MULE_NETWORK)용 `distinctCounterparties`/`counterpartyThreshold`(nullable superset) 추가 + `measure`=서술 라벨(문자열) 명문화. (2) **§3.4a `evidence.relatedTransactions[]`** — "평가 대상 단건"에서 **발동 시나리오 첫 velocity 윈도우의 형제거래 다건**(집계 구성 거래=다수 상대방; 조회 불가/빈 시 단건 폴백)으로 정정. aml-svc `TmEvaluationService`(실 evaluate)·bo-api 데모 라이브 인입 양 경로 정합. (3) **데모(비-prod) 라이브 인입 룰 평가** — bo-api `IngestTestController`→`AmlTmService.ingestLiveTransaction`가 hanpass-ph 시뮬레이터 거래를 주체 rolling 윈도우로 집계해 ACTIVE THRESHOLD 시나리오의 설정 임계(금액/건수/윈도우/다상대) 충족 시에만 `TM_SCENARIO` 알림을 발동/멱등 갱신((tenant,subject,scenario) upsert), 미충족은 미발동(FDS ALLOW 대응). 시나리오 임계는 `ScenarioTemplates`(룰 관리) 단일 정본. raw PII 미포함 불변. | aegis-spec. 코드=truth. 근거=bo-api `AmlTmService`(appendLiveTxn·evaluateLiveScenario·upsertLiveAlert·windowFor)·`IngestTestController`, aml-svc `TmEvaluationService.addRelatedTransactions`(windowPort.findTransactionsForSubject), bo-web `lib/aml-tm.ts` `AmlEvidenceAggregation`·`AmlTmAlertDetailPanel`, `tools/aml-ingest-simulator`(회원 풀 제한). 기능정의서 AML-TM-001 동기화. |
| 2026-06-30 | **데모·시뮬레이터 hanpass-ph 6 거래유형 정렬 — WLF sender+receiver 양방향·RA 회원가입 factor 계약 보강(코드=truth) — 엔진 도메인 무변경.** (1) **§2.2 Screening API** 표 다음에 콜아웃 신설 — 해외송금(`remit-svc` cross-border)은 sender(회원, `CUSTOMER`) + receiver(상대방, `COUNTERPARTY`)를 **각각 1건씩** screen(수취국 PH/VN/ID 제재 진양성, aml-svc V26 receiver 워치리스트), 비-cross-border 거래는 sender만; `subjectIdentity` 4필드 주체 무관 균일·COUNTERPARTY 미보유 필드 빈 값. (2) **§3.3 `RiskAssessmentRequest.factors`** 설명에 1차 RA = 회원가입(`member-svc`) 시점 1회·factor=`nationality`/`occupation`/`sourceOfFunds`/`kycLevel`(거래 기준 factor 1차 제거) 명문화. 6유형 정렬은 데모/시뮬레이터/시드 한정·엔진 enum/factor catalog 비변경. | aegis-spec. 코드=truth. 근거=bo-api `AmlScreeningService`(sender+receiver COUNTERPARTY)·`AmlRaService`(회원 KYC factor)·`AmlTmService.channelFor`, aml-svc V26(receiver 워치리스트), `scripts/demo_ingest.py`·`demo_stream.py`. 기능정의서 §3/§5(v9.18) 동기화. |
| 2026-06-30 | **WLF 매치 상세 `subjectIdentity` 식별정보 4필드 통일(코드=truth) — 주체 무관 균일.** **§3.2 `ScreenResponse.subjectIdentity` 행·`SubjectIdentity.fields`** — reveal 가능 필드 키를 `CUSTOMER=[NAME,NATIONALITY,GENDER]`·`비-customer=[NAME]`(3필드 비대칭) → **CUSTOMER·counterparty 모두 `[NAME,NATIONALITY,GENDER,DOB]` 4필드 균일**로 갱신. **§1.6** WLF 매치 상세 노출 경로 註記도 균일 4필드로 정정(회원=NAME/NATIONALITY/GENDER + 엔트리=NAME/NATIONALITY/DOB 비대칭 제거). 주체가 보유하지 않는 식별필드(예 수취자=상대방의 성별·생년월일)는 reveal stub 이 빈 값(`""`)을 반환(placeholder 아님). reveal 게이트 불변 — `aml:pii:reveal` scope·사유·`RAW_DATA_ACCESS` 감사·BR-007 마스킹 불변, vault 미적재/미보유 필드 fail-closed. raw PII 미포함 불변. | aegis-spec. 코드=truth. 근거=bo-api `ScreeningDetail.subjectIdentity.fields`(CUSTOMER·counterparty 모두 4필드)·reveal stub(미보유 식별필드 빈 값). 기능정의서 §3.1(v9.17) 동기화. |
| 2026-06-30 | **데모(비위임) WLF 스크리닝 reason code·점수분해 계약 정합(코드=truth).** **§3.2 `ScreenResponse`** — (1) `reasonCodes` 설명에 이름 유사 코드의 명단군별 **일반형 `<LISTTYPE>_NAME_SIMILARITY`**(예 `SANCTIONS_NAME_SIMILARITY`/`PEP_NAME_SIMILARITY`/`INTERNAL_NAME_SIMILARITY`, listType 미상=`NAME_SIMILARITY`; tokenSet≥0.6 또는 edit≥0.85) + 완전일치 `NAME_EXACT_MATCH` 병기. (2) `scoreBreakdown` 설명에 **가중 분모 = 전체 가중치 합(name 0.55+date 0.10+country 0.10+document 0.15+address 0.05+relationship 0.05 = 1.0)** 1줄 + **데모 스텁(bo-api `StubNameMatcher`, aml-svc 미가동·비위임) 점수분해 = name/dob/country 서브셋**(엔진=6 컴포넌트, 의도적 단순화·overall 동일 분모 1:1) 주석. raw PII 미포함 불변. | aegis-spec. 코드=truth. 근거=bo-api `StubNameMatcher`(reason `NAME_EXACT_MATCH`/`<listType>_NAME_SIMILARITY`·full weight sum 1.0·name/date/country 서브셋)·`AmlScreeningService`, aml-svc `FuzzyMatchEngine`/`MatchRuleSet`(`sumOfWeights()`) 미러. 기능정의서 §3(v9.16) 동기화. |
| 2026-06-29 | **위험등급별 차등 TM 임계 계약 명문화(코드=truth).** (1) **§3.4c 신설** — TM 시나리오 velocity DSL 노드 문법에 optional `thresholds`(등급 키 `RiskGrade` 4종·값 numeric·미지 키/비숫자 reject=closed grammar·미설정 등급=base `value` fallback) 명문화 + `aml_tm_scenarios.dsl` 예시에 `thresholds` 포함. 평가 규칙(거래 주체 고객 위험등급으로 effective threshold 선택, 고위험=강화, 등급 미상=base) 명시. (2) **§3.4c `ScenarioDefinition`/`CriterionField` DTO 신설** — `CriterionField.thresholdsByGrade`(`Map<RiskGrade,숫자>`, **NUMBER/AMOUNT 한정·가산(additive)·직렬화 NON_NULL**) + 평탄 parameters 키 인픽스 **`<key>.thresholds.<GRADE>`**(예 `minAmount.thresholds.HIGH`) 왕복 계약(`ScenarioDslCodec` toParameters/decode). (3) **§3.4a `evidence` 집계 패턴에 `appliedRiskGrade`(string\|null) 추가** — 등급 override 적용 시만 채워지고 base 적용 시 null, `threshold`=적용 등급 effective threshold 병기. **§3.4a `AggregationSummary.threshold`** 설명을 effective threshold(차등 임계 발동 시 해당 등급 임계)로 1줄 보강. (4) **§2.5a tm-scenarios read model** 설명에 NUMBER/AMOUNT 필드의 차등 임계 동반 노출 명시. Flyway 없음(`aml_tm_scenarios.dsl` JSONB 구조만 확장). | aegis-spec. 코드=truth. 근거=aml-svc `TmScenarioDslParser`(parseThresholdsByGrade·closed grammar)·`TmCondition.Velocity`(thresholdsByGrade·effectiveThreshold)·`TmEvaluationService`(customer riskGrade 1회 조회·appliedRiskGrade)·`AlertEvidence.Builder.appliedRiskGrade`, bo-api `TmDtos.CriterionField.thresholdsByGrade`·`ScenarioDslCodec`(THRESHOLD_GRADE_INFIX)·`ScenarioTemplates`(RAPID_MOVEMENT base ₱1,000,000·HIGH ₱500,000), bo-web `GradeThresholdInputs`·`lib/aml-tm.ts`. DB §3.10(dsl)·plan §12-A.6 동기화. |
| 2026-06-29 | **위험등급별 EDD 재이행주기 조회 surface 명문화(코드=truth).** (1) **§2.7 CDD/EDD 표에 엔진 GET 2종 추가** — `GET /api/v1/admin/aml/cdd/periodic-review-policy`(scope `aml:case:read`, 현재 정책 조회, 응답 `EnginePeriodicReviewPolicy`)·`GET /api/v1/admin/aml/cdd/due-for-review?windowDays=&riskGrade=`(scope `aml:case:read`, 재심사 임박/경과 큐, 응답 `EngineDueRow[]`, 마스킹). PUT 행 DB 열에 `aml_periodic_review_policy`(DB §3.22) 추가. (2) **§9 bo-api 위임 표에 GET 2종 추가** — `GET /api/v1/bo/aml/cdd/periodic-review-policy`(`PeriodicReviewPolicyView`)·`GET /api/v1/bo/aml/customers/due-for-review?riskGrade=&windowDays=`(`DueForReviewEntry[]`, `daysUntilDue` 음수=경과). (3) **§3.11 DTO 신설** — `PeriodicReviewPolicyView`(`cadenceByGrade`{LOW:12,MEDIUM:6,HIGH:3,PROHIBITED:0}·`gracePeriodDays`=14·`status` APPLIED/PENDING·`effectiveFrom`)·`DueForReviewEntry`(`customerRef` 마스킹·`riskGrade`·`nextReviewDueAt`·`daysUntilDue`·`cadenceMonths`) + 정책 store(DB §3.22) ↔ `next_review_due_at` 파생 관계 주석. (4) **§3.4b `Subject360Dto.riskSummary`에 `reviewCadenceMonths`(integer\|null) 추가** — 등급별 재이행주기 정책 파생, 회원 상세 '다음 재심사 기한'·임박 배지 backing. 모두 마스킹/집계, raw PII 미포함. | aegis-spec. 코드=truth. 근거=aml-svc `CddController`(GET periodic-review-policy·due-for-review)·bo-api `AmlCddPolicyController`·`AmlReviewQueueController`·`ReviewQueueDtos.DueForReviewEntry`·`CddPolicyDtos.PeriodicReviewPolicyView`·`AmlCustomerProfileService.reviewCadenceMonths`. DB §3.22(V25)·기능정의서 §12-A.5 동기화. |
| 2026-06-29 | **PEP 상태 회원 상세·대상 360° 노출 가산(코드=truth).** (1) **§3.4b `Subject360Dto`에 `pepStatus` 행 추가**(`{ isPep, pepApprovalStatus, pepApprovalId }`, DB §3.3 `aml_customers.is_pep`/`pep_approval_id` V24 1:1) + `riskSummary` PEP 확정 시 `riskGrade`=HIGH 강제 상향(거래 허용+EDD) 주석. (2) **§3.9 `CustomerProfileDto`에 `isPep`(boolean)·`pepApprovalStatus`(enum\|null)·`pepApprovalId`(uuid\|null) 행 추가** — 회원 상세 PEP 섹션(상태·상신·히스토리) backing. 모두 상태·토큰만, raw PII 미포함. §3.7 `PEP_APPROVAL`(19종) 결재함과 정합. | aegis-spec. 코드=truth. DB §3.3(V24)·§5.16·plan §02 회원 PEP 플로우 동기화. PEP 마이그레이션=V24(WLF pii_vault=V23 별개). |
|---|---|---|
| 2026-06-30 | **hanpass-ph AML 정본 재그라운딩 + 코드 truth 정합화(추측 제거).** (1) **헤더** — 책임 패키지 `com.hanpass.aml`→실제 `com.aegis.aml`, 컨트롤러 정본 경로 명시, 시스템 그라운딩(hanpass-ph 결제 5유형 `remit`/`domestic`/`wallet`·crypto/trade/PG/ecommerce/marketplace/B2B advanced domain 제외)·운영 테넌트 `tenant_demo`=hanpass-ph 박스 추가. (2) **§0 Public caller** 일반 `PG·VASP 시스템`→hanpass-ph 트랜잭션 마이크로서비스(`member-svc`/`walletchg-svc`/`domestic-svc`/`remit-svc`/`wallet-svc`/`inbound-svc`). (3) **§2.2 WLF 호출 패턴 주석 신설** — 해외송금 거래당 sender(member UUID=`CUSTOMER`)·receiver(이름+국가+전화 token=`COUNTERPARTY`) 2회 screen, `transactionRef`로 연결, FP 화이트리스트는 `(targetRef::matchedEntryId)` fingerprint 키로 거래간(across-transaction) 유효. (4) **§3.1 eventType taxonomy** 를 `EventFamily` enum 정본(hanpass `customer`/`entity`/`beneficial-owner`/`transaction`/`remit`/`domestic`/`wallet` family + 5유형 verb)으로 교체, `crypto.*` 등 잔존 family는 strict-gate fail-safe·외부 ingest 미사용 명문화. (5) **§3.2 ScreenRequest** 코드 truth 평면화(중첩 `subject`·`sourceTypes` 제거, `nameHash`/`addressTokens`/`relationshipRefs`/`transactionRef` 등 실제 `ScreenRequest` 11필드) + **응답을 실제 `ScreeningResponse` 12필드**로 환원(`tenantId`·`transactionRef` 추가, `riskGrade`/`requiredActions`/`matchedCandidates`/`matchedRules`/`decidedAt`/`expiresAt`는 bo-api enrichment로 분리). (6) **§3.4 TransactionEvaluateRequest** 코드 truth 8필드로 환원(`corridor`·`amountBase`는 요청 바디 외 payload feature로 이동), TM feature(`phpEquivalent`·channelType) 주석. (7) **§3.4a TM 시나리오 카탈로그 신설** — `TmScenario` enum 10종·데모 ACTIVE phpEquivalent 임계(Flyway V28: HIGH_RISK_CORRIDOR 280,000·RAPID_MOVEMENT 56,000·REFUND_LAUNDERING 28,000·ROUND_TRIPPING 112,000 PHP). (8) **CustomerType enum 정정** — 8종(MERCHANT/SELLER/VASP_CUSTOMER 등)→코드 truth **3종**(`PERSON`/`SOLE_PROPRIETOR`/`EMPLOYEE`). (9) **§5 OpenAPI** `ScreenRequest`/`ScreeningResponse` schema 코드 정합·`$ref` 갱신. **주**: 이후 v9.20~v9.25(TM 룰 한정·상세 페이지·watchlistMatch·식별정보 비교·수취인 스크리닝)가 §3.4/§3.4a 를 최신화하며 본 항목의 관련 절을 상회한다. | aegis-java-implementer. 코드=truth. 근거=`aml-svc` adapter/in/rest(AmlEventController·ScreeningController·AlertController·RiskController·WatchlistAdminController·TmScenarioAdminController·ApprovalController)·domain/enums(EventFamily·TmScenario·TargetType·CustomerType·WatchlistSourceType·ScreeningStatus·SourceOrigin)·Flyway V28. |
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
