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

엔진 전건 검증처럼 tenant/scope 음성 경계를 실 REST로 증명해야 하는 disposable local/demo 스택은 `AEGIS_AML_LOCAL_ADDITIONAL_CREDENTIALS_ENABLED=true`와 `AEGIS_AML_LOCAL_ADDITIONAL_CREDENTIALS_JSON`을 명시할 수 있다. JSON 각 행은 `tenantId/apiKey/secret/scopes[]`의 exact credential이며 secret 32자 이상·안전한 ID/scope·행 간 ID/secret 불중복을 기동 시 fail-closed 검증한다. 정상 cipher port로 암호화한 v2-only row만 저장하고 평문은 startup 직후 폐기한다. 이 opt-in component는 active profile이 전부 `local|demo`일 때만 존재하며 production credential lifecycle/API나 Flyway seed를 추가하지 않는다.

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

> **WLF 스크리닝 NAME 한정 예외(2026-08-22, 코드=truth).** `GET /api/v1/aml/screenings/{screeningId}` 및 `GET /api/v1/admin/aml/screenings`와 bo-api 프록시의 `aml:case:read` 응답은 요청 시점 이름(`requestName`)과 매칭 워치리스트 엔트리의 현재 게시본 이름(`matchedEntryNames`)만 인라인으로 반환한다. 이 두 NAME 값에는 `aml:pii:reveal` scope·사유 입력·reveal 호출이 필요 없고 bo-api가 응답당 `RAW_DATA_ACCESS` 1건을 남긴다. `aml:screen:evaluate` 단독 원천 시스템 호출에는 두 키를 생략하며, DOC/ACCOUNT/WALLET/NATIONALITY/GENDER/DOB와 WLF 이외 read 경로의 기존 reveal 게이트는 불변이다.

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
> **CDD 온보딩 업무결정(V42, 코드=truth).** `customer.cdd.completed`의 최초 ACCEPTED 처리에서 생성된 RA snapshot을 `aml_cdd_onboarding_decisions`에 이벤트/멱등키별 불변 projection으로 저장한다. KYC `REJECTED` 또는 RA `PROHIBITED`는 `REJECT`, EDD 필요·고위험 WLF/보류는 `EDD_REQUIRED`, 나머지는 `APPROVE`다. 응답은 `{decision,scoreId,riskScore,riskGrade,requiredAction,modelVersion,reason}`을 포함한다. replay는 idempotency key 소유 **저장 canonical event의 eventId/source/schema/type/occurredAt/payload/hash/dataScope**와 요청을 비교한다. exact replay만 후속 모델·source enabled/schema 변경과 무관하게 최초 snapshot을 200으로 반환하고, 같은 key의 다른 body는 `409 DUPLICATE`다. legacy 복구에서 projection이 없으면 재평가로 새 결정을 발명하지 않고 `EDD_REQUIRED`로 fail-safe 한다. **1차 RA 요약 additive 확장(20260718 사용자 지시, PLAN 20260718-sync-verdict-in-response U4, F-003 해제)**: 응답에 `mandatoryHighRisk`(boolean\|null)·`mandatoryHighRiskReasons`(string[]\|null)·`wlfHit`(boolean\|null) 3필드가 추가된다 — 당연고위험 강제상향 여부·사유·WLF(제재/PEP) 히트 요약(§3.1). ACCEPTED 경로는 방금 산출한 `RiskScore`(`mandatoryHighRisk`/`mandatoryHighRiskReasons`/`factorBreakdown` SCREENING factor)에서, REPLAYED 경로는 저장된 decision 의 `scoreId` 로 조회한 동일 스코어에서 파생한다(재평가 없음). HELD·스코어 미산정 시 3필드 모두 `null`(fail-safe, 기존 decision 계약 불변). 거절 없음 원칙 불변.

> **CDD 신고소득 숫자 직접 수신(2026-08-17 정합, 사용자 지시로 F-040·F-041 해제, 코드=truth).** `payload.kyc` 가 `declaredIncomeOperator`(`LTE`/`LT`/`EQ`/`GTE`/`GT` 또는 기호)·`declaredIncomeAmount`(양수 JSON number)·`declaredIncomeCurrency`(ISO 4217)·`declaredIncomePeriod`(`MONTHLY`/`ANNUAL`)를 직접 싣는다. **상한을 알 수 있는 연산자만 평가**하며(`GTE`/`GT` 는 상한이 없어 미평가 — 임의 상한을 지어내면 임계가 낮아져 오탐), 신고 통화가 테넌트 기준통화와 다르면 미평가한다(환산 없음). `ANNUAL`은 `MathContext.DECIMAL128`로 /12 월할하고 alert provenance의 `period`에는 원문 `ANNUAL`을 보존한다. `declaredIncomeAmount` 키가 존재하면 그 숫자 경로가 최종 권위라 malformed/null/blank도 레거시로 폴백하지 않는다. `declaredIncomeBand`는 숫자 키가 아예 없을 때만 쓰는 레거시 입력이다. 정본 `docs/aml-data.md` §4.3.1.
>
> **CDD `declaredIncomeBand` 선택 입력 ↔ projection 출력 경계(2026-08-14, 코드=truth).** canonical `payload.kyc.declaredIncomeBand`는 optional이며 입력 enum은 `UNDER_1M_PHP`·`PHP_1M_TO_5M`·`PHP_5M_TO_10M`·`OVER_10M_PHP` 4종 그대로다. `UNKNOWN`은 public 입력의 다섯 번째 값이 아니라 exact `customer.cdd.completed`에서 다른 지원 KYC 차원 하나 이상이 남고 band가 부재/null/blank일 때만 current-state `kycEvidence.declaredIncomeBand`에 나타나는 내부 projection sentinel이다. raw canonical payload/hash는 바꾸지 않고, KYC block/지원 차원이 없으면 sentinel-only evidence를 만들지 않는다. re-CDD non-empty snapshot은 full replace라 omission이 과거 finite projection을 `UNKNOWN`으로 교체하되 과거/현재 raw event는 모두 불변이며 exact replay·changed-body `409` 계약과 no-backfill은 그대로다. `UNKNOWN`은 금액 0·상한·FX·기간값이나 `incomeProxy` provenance를 합성하지 않아 `STR_KYC_INCOME_MISMATCH` income predicate를 skip하고 다른 AML 조건은 독립 평가된다. FDS에는 income field/feature/rule을 신설하지 않는다.

> **인입 파이프라인 step 7f — FDS 고객 프로필 동기화 outbox.** 신규 CDD가 ACCEPTED되면 동일 트랜잭션에서 `aggregateType=FDS_CUSTOMER_PROFILE`, `eventType=aml.customer.profile.updated`, `aggregateRef=customerRef` outbox를 생성한다. payload는 `sourceEventId/occurredAt/nationality/country/registeredAt/kycCompletedAt/kycLevel/dataScope`만 포함하고 raw name·DOB·문서 식별자는 제외한다. relay가 FDS 내부 API로 전달하며 실패는 기존 outbox retry/backoff로 재시도하므로 FDS 장애가 AML CDD ingest를 rollback하지 않는다. REPLAYED/DUPLICATE는 step 7f에 도달하지 않아 중복 enqueue하지 않는다.

> **회원 심사결과 확정은 별개 후속 계약(PLAN 20260903-aml-decision-status-webhooks, 코드=truth).** 위 `customer.cdd.completed` 인입 결정(`aml_cdd_onboarding_decisions`, V42)은 인입 시점의 **불변 스냅샷**이며 이후 어떤 4-eyes 결재도 이 행을 갱신하지 않는다(F-076). 계정계가 "결재를 통해 승인/거절이 완료된 시점"의 상태값을 읽으려면 별도로 **회원(고객 관계) 심사결과 확정**(append-only `aml_member_decisions`, V74)을 쓴다 — 온보딩 보류(`EDD_REQUIRED`) 회원의 EDD 케이스 종결(`EDD_CLOSE`) 4-eyes 결재가 **EXECUTED**되거나 관계거절(`RELATIONSHIP_REJECT`) 결재가 **EXECUTED**될 때만 행이 append되고, 같은 트랜잭션에서 웹훅 `AmlMemberDecisionResolved`(§8.1)가 아웃박스 enqueue된다. 결재 **반려**는 행·웹훅 모두 없음(F-020 `rejectPathNeverEmits` 선례). 조회는 §2.3 `GET /api/v1/aml/customers/{customerRef}/decision`, DB는 §3.x `aml_member_decisions`(DB 문서), 목적지 우선순위·payload 는 §8.1/§12.1a(`docs/aml-data.md`).

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
| `device` | object(Device) | — | 디바이스/네트워크 공통 블록(`docs/aml-data.md` §4.5, PLAN 20260717 — 사용자 지시로 F-005 해제). `deviceId`/`os`/`version`/`ip`/`locale`(모두 optional·string ≤64자(`locale`≤16자)·제어문자 금지, 422). flat payload `device` 서브트리(비-null 필드만)에 기록되고 설정형 CTR/STR 룰 피처 `device.deviceId`/`device.os`/`device.version`/`device.ip`/`device.locale`(5키, `ConfigurableRuleDslPolicy.SCALAR_FEATURES`)로 노출된다 — 법정 CTR2·STR8 카탈로그 룰은 미소비(불변). FDS 인입(§5.1 01-fds-api.md)과 동형 블록(`NeutralDevice` 5-컴포넌트, 4-인자 하위호환 생성자 유지) |

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

**응답**(`NeutralIngestResponse` = truth, 가정 G6 — 동기 HOLD 오케스트레이션 미구현): `{ eventId, status(ACCEPTED/REPLAYED/DUPLICATE/REJECTED), accepted(boolean), violations(string[], REJECTED 시만), evaluation }`. `evaluation`(평가된 경우만)=`{ decision(PASS/REPORT — advisory 파생값), alertCount, firedRuleCodes[], screened(boolean), firedAlerts[], ctrApplicable(boolean), strCandidate(boolean) }`. WLF 실패는 인입 실패로 전파하지 않고 `screened=false`로만 표기(가정 G10, best-effort).

> **evaluation additive 확장·REPLAYED 재구성(코드=truth, 20260718 사용자 지시, PLAN 20260718-sync-verdict-in-response U6, F-003 해제, §11.6 재개정).** 기존 4필드(`decision`/`alertCount`/`firedRuleCodes`/`screened`) 는 불변이며 4-인자 하위호환 생성자로 기존 호출부가 계속 컴파일된다. additive 3필드: `firedAlerts[]{alertId, ruleCode, severity}`(발동 알럿 요약), `ctrApplicable`(boolean — 현금성 채널 게이트, CTR **보고서 확정 자체는 범위 밖** — banking-day 순증 집계는 기존 `/aml/reports` draft 폐루프 유지), `strCandidate`(boolean — 발동 알럿이 STR report-rule family 인지, 정본 `AmlReportRuleCatalog`/`AmlReportRuleFamily`). **REPLAYED 규칙 개정**: 직전 계약("REPLAYED/DUPLICATE 는 `evaluation=null`")을 반전 — **REPLAYED 는 저장된 알럿/스크리닝에서 read-only 로 재구성한 동일 요약을 동봉**한다(canonical event `transactionRef`/`channelType` 를 저장 payload 에서 읽어 파생, 요청 body 는 불신 — 재평가·PII 재사용·projection/엔진 side-effect 는 0). `DUPLICATE`(409)·`REJECTED`(422) 는 기존대로 `evaluation=null`. 거절 없음 원칙 불변 — 판정 동봉은 표시이지 인입 거부가 아니다.

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
| POST | `/api/v1/aml/screen` | `aml:screen:evaluate` | Y | 실시간 WLF/제재/PEP screening. **hanpass-ph 해외송금은 거래당 sender(송금 회원)·receiver(수취인) 2회 호출**(§3.2 `transactionRef`로 연결). **COUNTERPARTY 대상은 요청 신원(이름 토큰·country·dob)을 스크리닝 `targetRef` 키로 reveal vault 에 암호화 투영**(2026-07-15 — WLF 상세 수취인 원문 reveal 결선, DB §3.21; 응답·DTO 불변). **`callbackUrl`?**(요청별 아웃바운드 웹훅 목적지, PLAN 20260903-aml-decision-status-webhooks — 사용자 지시로 F-084 부분 해제) additive — 길이 ≤2048자, 수신 시 `WebhookUrlPolicy` SSRF 사전검증(실패 **400**), 저장은 `aml_screening_results.callback_url`(V74), 응답에는 원문 미노출·`callbackConfigured:boolean`만 동봉(§3.2) | `aml_screening_results`, `aml_pii_vault`(COUNTERPARTY 투영) |
| GET | `/api/v1/aml/screenings/{screeningId}` | `aml:screen:evaluate` **또는** `aml:case:read` (requireAny) | — | screening 결과 조회 — 소스시스템 read-back(`aml:screen:evaluate`) 외에 BO 검토 화면 위임(bo-api, `aml:case:read`)도 허용. BO 위임 credential 은 evaluate scope 를 의도적으로 미보유(BOA-S1-01·PRD §1.4)하므로 읽기 전용 상세는 `aml:case:read` 로 열린다(P0-04 credential 분리 후 WLF 상세 403 회귀 교정). **`pendingDecision`/`callbackConfigured` additive**(PLAN 20260903-aml-decision-status-webhooks DoD 4, §3.2) | `aml_screening_results` |
| GET | `/api/v1/aml/screenings?transactionRef=…\|targetRef=…` | `aml:screen:evaluate` **또는** `aml:case:read` (requireAny) | — | **계정계 WLF 상태조회 read-back**(신규, PLAN 20260903-aml-decision-status-webhooks DoD 4) — 둘 중 하나 필수(둘 다 공란이면 **400**, 둘 다 지정 시 `transactionRef` 우선). `transactionRef`는 해당 거래의 sender+receiver 스크리닝 전건(최신순, **상한 200건** — `ScreeningResultJpaAdapter` 정적 상한, 초과분 절단·hasMore 신호 없음), `targetRef`는 대상의 최신 스크리닝 1건(0~1건)을 반환한다. 각 원소는 기존 `ScreeningResponse`(§3.2) + additive `pendingDecision{approvalId,targetStatus,makerId,submittedAt}`(비-terminal `WLF_DECISION` 4-eyes 결재, Q5)·`callbackConfigured:boolean`(요청별 `callbackUrl` 등록 여부, URL 원문 미노출). bo-api 미러 `GET /api/v1/bo/aml/screenings/by-transaction?transactionRef=&targetRef=`(필드 1:1, 기존 `GET /api/v1/bo/aml/screenings` 8-파라미터 목록 계약은 무변경) | `aml_screening_results` |

> **WLF 스크리닝 대상 = 해외송금 + 국내송금 양당사자(sender + receiver)(hanpass-ph 데모 정합)**: 송금계열 2 product — 해외송금(`CROSS_BORDER_REMITTANCE`, `remit-svc` cross-border)·국내송금(`DOMESTIC_TRANSFER`) — 거래는 송금인(sender = 회원 본인, `targetType=CUSTOMER`, `targetRef`=member UUID keyed token)과 수취인(receiver = 상대방, `targetType=COUNTERPARTY`, 해외송금 수취인 키=이름+국가+전화 토큰)을 **각각 1건씩** screen 한다(수취국 PH/VN/ID 제재 = 진양성). 두 결과는 동일 `transactionRef`(거래번호 keyed token)로 묶여 케이스/증빙에서 거래 단위로 연결된다. receiver 스크리닝은 워치리스트 receiver 엔트리와 매칭하며 `subjectIdentity`(§3.2) 4필드(NAME/NATIONALITY/GENDER/DOB)는 주체 무관 균일(COUNTERPARTY 미보유 필드는 reveal stub 이 빈 값) — 국내송금 receiver 에도 동일 적용된다. 국내송금 receiver 식별은 `domesticTransfer.creditAccount.accountHolderName`(이름) + 상대방 국가(A6, 기본 `PH`)로 해결하고, sender 스크리닝과 동일 `transactionReference` 로 키잉되어 STR party-aware receiver lineage(계약 1·6)가 소비한다. 회원가입·월렛충전·월렛결제 등 잔여(비-송금계열) 거래는 sender(`CUSTOMER`)만 screen. FP 화이트리스트(§2.7·§3.2)는 `(targetRef::matchedEntryId)` fingerprint를 키로 하므로 **특정 거래가 아니라 동일 대상의 재screening 전반에 거래간(across-transaction) 유효**하다(동일 FP 매칭은 `AUTO_DISCOUNTED`로 자동 감점). 엔진 도메인 비변경 — 데모/시뮬레이터/시드 한정. TM STR_PEP·STR_SANCTION 은 receiver COUNTERPARTY 스크리닝 계보를 수취인 명단 평가에 재사용(§3.4a·기능정의서 §7.1 BR-013).

> **fail-closed readiness 게이트 → `503 AML.SCREENING_UNAVAILABLE`(P0-06, feature/p0-06-wlf-source-readiness-rescreen)**: `POST /api/v1/aml/screen`(및 `POST /internal/v1/aml/screen`)는 실제 스크리닝 전 **필수 source readiness 게이트**를 통과해야 한다. 게이트는 tenant 의 **필수 source 정책**(DB §3.6a `aml_mandatory_watchlist_sources`)을 해소해 각 활성 필수 source 가 **screening-ready**(effectiveReadiness ∈ {`READY`, 유효 `OVERRIDDEN`}, DB §3.6 후주)이거나 capability=`NOT_APPLICABLE`+유효(승인·미만료) waiver 여야 통과한다. **필수 정책이 없는(미설정) tenant** 는 fallback=**screening-ready source ≥1건이면 통과, 0건이면 fail-closed**(구 freshness 게이트의 vacuous-truth[빈 목록 allMatch=true] fail-open 제거 — 검색할 명단이 없는데 `NO_MATCH` 로 미탐되던 구조적 결함 차단). 미충족 시 `NO_MATCH` 가 아니라 **`503 AML.SCREENING_UNAVAILABLE`** 로 fail-closed 하며, 응답 `details`(비-PII·source type/code 만)에 사유코드(`ScreeningReadinessReason`)를 담는다 — `NO_MANDATORY_POLICY`(정책 미설정, strict 기본 fail-closed)·`NO_READY_SOURCE`(fallback: ready source 0건)·`MISSING_SOURCE`(필수 source 미등록)·`NOT_READY`(MISSING/IMPORTING)·`STALE`(48h 초과)·`FAILED`(직전 import 실패)·`NOT_APPLICABLE_UNAPPROVED`(waiver 없음). 코드 truth=`WatchlistReadinessGateAdapter`·`WlfScreeningService`(게이트 (0a))·`GlobalExceptionHandler#handleScreeningUnavailable`. rescreen 파이프라인(명단 apply 후 durable 재검색)은 integration §.

> **후보 조회 timeout fail-closed(2026-08-20)**: 4전략 후보 recall SQL이 bounded `statement_timeout`에 걸리면 partial 후보나 `NO_MATCH`, 일반 500을 반환하지 않는다. SQLState `57014`는 typed candidate-recall timeout으로 보존되고, 이미 abort된 transaction에서는 `SET LOCAL statement_timeout = 0`을 재실행하지 않은 채 rollback된다(성공 경로만 reset). Public/Internal screen 응답은 HTTP **503**, code **`AML.SCREENING_UNAVAILABLE`**, details **`CANDIDATE_QUERY_TIMEOUT`**이다. 이 details는 source readiness 7종 `ScreeningReadinessReason`과 별도이며 요청 이름·대상키 등 PII/토큰을 포함하지 않는다. 후보 SQL·timeout 값·V64 인덱스·매처/판정은 불변이다.

### 2.3 Risk Assessment API (Public) — 설계서 §11

| 메서드 | 경로 | scope | 멱등 | 설명 | DB |
|---|---|---|---|---|---|
| POST | `/api/v1/aml/risk-assessments/evaluate` | `aml:ra:evaluate` | Y | 고객(회원)/법인 위험평가 실행(회원가입 RA·재평가) | `aml_risk_scores` |
| GET | `/api/v1/aml/risk-assessments/{scoreId}` | `aml:ra:evaluate` | — | RA 결과 조회 | `aml_risk_scores` |
| GET | `/api/v1/aml/customers/{customerRef}/risk` | `aml:case:read` | — | **대상 stage-aware operative 등급 조회**(PLAN 20260722-ra-tm-2nd-stage-fixed-scenario-consistency, "TM 진입 시 2차 고정") — 상시평가(ONGOING) 점수가 이력에 하나라도 있으면 최신 상시평가(ONGOING) 점수, 없으면 최신 온보딩(ONBOARDING) 점수를 유효 평가로 반환(구 "최신 evaluated_at=유효 등급" 규칙을 대체). 온보딩 모델 재평가(system 재점수)가 상시평가 진입 대상의 유효 평가구분을 1차로 되돌리지 않는다. `onboardingReview` 보조 블록은 최신 온보딩 점수 기준으로 별도 유지(§2.6 후주). | `aml_risk_scores` |
| GET | `/api/v1/aml/customers/{customerRef}/decision` | `aml:case:read` **또는** `aml:event:write` (requireAny) | — | **회원(고객 관계) 심사결과 확정 read-back**(신규, PLAN 20260903-aml-decision-status-webhooks DoD 2) — 계정계가 "결재를 통해 승인/거절이 완료된 시점"의 상태값을 폴링한다. `aml:event:write`(계정계 인입 credential, `aml:case:read` 미보유)도 requireAny 로 허용. 응답 `MemberDecisionDto`(아래)는 확정 행(`aml_member_decisions`)과 CDD 인입 스냅샷(`aml_cdd_onboarding_decisions`)을 병합해 최신순 정렬한 것으로, **`history[0]`이 현재 결정**이다. 온보딩 보류(`EDD_REQUIRED`) 중에도 **200**이며 회원 자체가 없을 때만 **404**. bo-api 미러 `GET /api/v1/bo/aml/customers/{ref}/decision`(scope `aml:case:read`, 필드 1:1) | `aml_member_decisions`,`aml_cdd_onboarding_decisions` |
| POST | `/api/v1/admin/aml/risk-scores/{scoreId}:complete-review` | `aml:case:update` | — | SANCTION/PEP 1차 RA 체크리스트 완료. actor=`X-User-Subject`, 세 체크 항목 필수, replay 멱등 | `aml_ra_reviews`, `aml_audit_events(RA_REVIEW)` |

> **`MemberDecisionDto`(§2.3 `GET .../decision`, 코드 `MemberDecisionController.MemberDecisionResponse`/bo-api `RaDtos.MemberDecision` 1:1, PLAN 20260903-aml-decision-status-webhooks).** 스칼라 필드(`decision`~`requiredAction`)는 `history[0]`을 그대로 미러하며, 회원 프로필은 있으나 결정/스냅샷이 아직 없으면 `null`이다.
>
> | 필드 | 타입 | 설명 |
> |---|---|---|
> | `memberRef` | string | 회원 키(= `customerRef` = 엔진 `targetRef`) |
> | `decision` | enum | **`MemberDecisionKind`**: `APPROVED`\|`REJECTED`\|`EDD_REQUIRED`\|`REPORTED`(EDD 케이스가 STR 제출로 종결된 경우만, 관계 유지 여부는 채널 판단 — workflow-guide §① L65) |
> | `source` | enum | **`MemberDecisionSource`**: `INGEST`(비영속 — CDD 인입 스냅샷 파생)\|`EDD_CLOSE`\|`RELATIONSHIP_REJECT` |
> | `reason` | string\|null | 결재 사유(확정 행 `EDD_CLOSE`/`RELATIONSHIP_REJECT`, 자유문) 또는 **인입 스냅샷 `OnboardingDecisionReason` enum 원문**(INGEST — `aml_cdd_onboarding_decisions.reason` NOT NULL 이므로 non-null, 예 `ONBOARDING_RA_HELD`; 2라운드 QA B1 미러). 확정 행의 결재 사유 공란일 때만 `null` |
> | `decidedAt` | string(date-time) | 확정/인입 시각 |
> | `decidedBy` | string\|null | 결재 checker(확정 행) 또는 `null`(INGEST) |
> | `approvalId`/`caseId` | string(uuid)\|null | 결재 실행 근거(확정 행만, INGEST는 `null`) |
> | `caseType`/`finalStatus` | enum\|null | 케이스 유형·종결 상태(확정 행만) |
> | `scoreId`/`riskGrade`/`requiredAction` | string\|enum\|null | 결재 실행 시점 operative RA 점수 스냅샷 |
> | `mandatoryHighRisk` | boolean | 회원의 **현재** operative RA 점수 기준(항상 최신 — `history[0]`의 source 와 무관) |
> | `ingestDecision` | object\|null | 최신 CDD 인입 스냅샷 `{eventId, decision(`OnboardingDecision` 원문), reason, createdAt}` — 회원이 CDD 인입된 적 없으면 `null` |
> | `pendingApproval` | object\|null | 비-terminal `EDD_CLOSE`/`RELATIONSHIP_REJECT` 4-eyes 결재 `{approvalId, subjectType, status, makerId, submittedAt}` — 없으면 `null`(Q1: 반려 시에도 `null`로 복귀) |
> | `history` | array | 확정 행 + 인입 스냅샷 병합·최신순(상한 50), 원소는 위 스칼라 필드와 동형(`decidedBy`~`requiredAction`) |
>
> **`MemberDecisionKind` ↔ `OnboardingDecision`(§3.1 CDD 인입 응답, `aml-data.md` §12.1) 매핑표** — 두 enum 은 별개 타입이며 응답 필드명도 분리(`ingestDecision.decision`=`OnboardingDecision` 원문, `decision`=`MemberDecisionKind`): `APPROVE`→`APPROVED` · `REJECT`→`REJECTED` · `EDD_REQUIRED`→`EDD_REQUIRED`. `REPORTED`는 결재(`EDD_CLOSE`, finalStatus=`REPORTED`) 경로에서만 생성되며 `OnboardingDecision` 대응값이 없다.
>
> **회원 결정을 만들지 않는 4-eyes 결재(제외 명시)**: `HRR_REGISTRATION`(당연고위험 등재 — `AmlHighRiskRegistrationApproved` 콜백이 별도 담당, §8.1)·`PEP_APPROVAL`(PEP 관계 승인 — 등급·EDD 판정에 반영되어 EDD 케이스 처분으로 귀결)·`RISK_OVERRIDE`(등급 수동 조정 — 점수 이력이지 온보딩 승인/거절 아님)·`HIGH_RISK_REGISTRY`(참조 리스트 변경 — 회원 개별 결정 아님). 이들은 `history`에도 나타나지 않는다. `EDD_CLOSE`는 **온보딩 보류 발단**(케이스 `caseType==EDD_REVIEW` **∧** 확정 전 회원의 현재 결정이 `EDD_REQUIRED`)일 때만 회원 결정을 만든다 — 이미 `APPROVED`인 회원의 2차 RA(ONGOING)·FDS 발단 EDD_REVIEW 종결은 상시감시 결과라 회원 결정을 만들지 않는다(workflow-guide §① L65 정합). `RELATIONSHIP_REJECT`는 케이스 유형·현재 결정과 무관하게 항상 `REJECTED` 회원 결정을 만든다.

### 2.4 Transaction Monitoring API (Public) — 설계서 §12

| 메서드 | 경로 | scope | 멱등 | 설명 | DB |
|---|---|---|---|---|---|
| POST | `/api/v1/aml/transactions/evaluate` | `aml:tm:evaluate` | Y | 거래 TM 평가·alert 생성 | `aml_alerts`(+`aml_canonical_events`) |
| GET | `/api/v1/aml/alerts?status=&rule=&channel=&corridor=&includeRetired=` | `aml:case:read` | — | alert triage 큐 목록(응답 DTO §3.4a `AlertDto[]`). **`status` 미지정 ⇒ 전 상태 반환**('전체' 시맨틱, run3 D1 — 기존 `defaultValue="DETECTED"` 드리프트 해소). `rule`=발동 룰 코드, `channel`/`corridor`=알럿 evidence `relatedTransactions[]` 대표값 클라이언트측 필터(run3 D6·가정 G2 1단계, 엔진 스키마 조인 필터는 후속). **`includeRetired`(기본 false) ⇒ 회수 알림(`RETIRED`) 제외**(2026-08-06) — 어떤 `status` 필터를 주더라도 기본값에서는 회수분이 나오지 않으며, 감사 조회는 `includeRetired=true`(+선택 `status=RETIRED`)로 명시한다. 전부 optional | `aml_alerts` |
| GET | `/api/v1/aml/alerts/{alertId}?includeRetired=` | `aml:case:read` | — | alert 조회(응답 DTO §3.4a `AlertDto`). **회수 알림은 기본 404**이고 `includeRetired=true`에서만 반환한다(목록과 동일 스위치, 2026-08-06) | `aml_alerts` |
| GET | `/api/v1/aml/alerts/{alertId}/related-transactions?page=&size=` | `aml:case:read` | — | **알림 발동 근거 거래 서버 페이징**(요구2·A8) — 발동 룰이 결정하는 윈도우(주체 velocity 윈도우 / 영업일 현금 합산 / 단건 그룹)의 근거 거래 **전수**를 페이징(20행 evidence 표시 캡과 별개). 응답 DTO §3.4d `RelatedTransactionsResponse` | `aml_alerts`(+`aml_canonical_events`) |
| POST | `/api/v1/aml/alerts/{alertId}:triage` | `aml:case:update` | — | alert 1차 분류(`DETECTED`→`TRIAGED`). 본문 없음. 응답 §3.4a `AlertDto`(전이 후 상태). 불법 전이 시 **409 `AML.STATE_CONFLICT`** | `aml_alerts` |
| POST | `/api/v1/aml/alerts/{alertId}:dismiss` | `aml:case:update` | — | alert 오탐 종결(`DETECTED`/`TRIAGED`→`DISMISSED`). **optional body `{reason, actor}`**(둘 다 nullable — `reason`=처분 사유 코드 문자열(예 `FALSE_POSITIVE` 계열)·`actor`=처분 행위자). **엔진은 하위호환 optional 로 수용**(본문 없거나 `reason` 부재도 허용)하며, `reason`/`actor` 지정 시 `aml_alerts.disposition_reason`/`disposition_actor`(V30)에 영속해 룰 효과성 오탐율(§12-B.3)·감사 근거를 남긴다. **사유 필수 강제는 bo-api/bo-web 계층 책임**(가정 G1). 응답 §3.4a `AlertDto`(`dispositionReason` 포함). 불법 전이 시 409 `AML.STATE_CONFLICT` | `aml_alerts` |
| POST | `/api/v1/aml/alerts/{alertId}:open-case` | `aml:case:update` | — | 케이스 개설(`TRIAGED`→`CASE_OPENED`). body `{caseType?, actor?, reason?}`(`reason` additive, B2 — 케이스 `CREATED` note 에 `;REASON=<reason>` 로 영속, bo-api 케이스 전환 모달 사유 전달; 3종 공용 `HandOffRequest`). 응답 `201 {caseId, caseStatus}`. 불법 전이 시 409 `AML.STATE_CONFLICT` | `aml_alerts`,`aml_cases` |
| POST | `/api/v1/aml/alerts/{alertId}:escalate` | `aml:case:update` | — | 상위 승인(`TRIAGED`→`ESCALATED`, 케이스 개설). body `{caseType?, actor?, reason?}`(`reason` additive, B2 — 케이스 `CREATED` note 에 `;REASON=<reason>` 로 영속, bo-api 케이스 전환 모달 사유 전달; 3종 공용 `HandOffRequest`). 응답 `201 {caseId, caseStatus}`. 불법 전이 시 409 `AML.STATE_CONFLICT` | `aml_alerts`,`aml_cases` |
| POST | `/api/v1/aml/alerts/{alertId}:recommend-str` | `aml:case:update` | — | STR 권고(`TRIAGED`→`STR_RECOMMENDED`, STR 케이스 개설 + 아웃박스 적재). body `{caseType?, actor?, reason?}`(`reason` additive, B2 — 케이스 `CREATED` note 에 `;REASON=<reason>` 로 영속, bo-api 케이스 전환 모달 사유 전달; 3종 공용 `HandOffRequest`). 응답 `201 {caseId, caseStatus}`. 불법 전이 시 409 `AML.STATE_CONFLICT` | `aml_alerts`,`aml_cases` |
| GET | `/api/v1/aml/transactions?transactionRef=&eventId=&memberRef=&product=&from=&to=&page=&size=` | `aml:case:read` | — | **거래 브라우즈(최근 거래, PLAN 20260819-aml-tm-recent-transactions AML-4)** — `aml_canonical_events` 의 거래성 family 4종(`transaction\|remit\|domestic\|wallet`, `EventFamily.isTransactionBearing()`)만 최신순(`occurred_at DESC, event_id DESC`) 페이지 조회. `customer.*` 등 신원 이벤트는 나오지 않는다. 필터 5종(파라미터 6개)은 전부 optional·정확일치 — `transactionRef`=`payload->>'transactionRef'` / `eventId`=`event_id` 컬럼 / `memberRef`=`payload->>'targetRef'` **단일 키** 매칭(레거시 payload `memberRef` 키는 필터 미대상 — 표시값만 `COALESCE(targetRef, memberRef)` 레거시 폴백) / `product`=`payload->>'product'` / `from`/`to`=`occurredAt` ISO-8601 instant 구간(파싱 실패 400). 페이지 `size` 기본 20·상한 200 클램프. 응답 `{rows,page,size,totalCount}`(행: `eventId,eventType,transactionRef,memberRef,product,amount,currency,channelType,direction,occurredAt,alertCount,firedRuleCodes[]`). **금액 키**: `amount`/`currency` 는 payload `amountBase`+`currency` 소싱(레거시 행 호환·`CanonicalEventWindowAdapter` 동형 소비)이며, 인입의 422 통화 일치 강제로 **값은 canonical `baseEquivalent`/`baseCurrency`(레포 `docs/aml-data.md` §11.3a 평가 정본)와 항상 동일**하다 — 취소(reversal)/환불(refund) 행은 부호 음수 그대로(netting) 반환. **결측 허용**: 파생 필드(transactionRef·product·amount·currency·channelType·direction 등)는 전건 null 허용·행 제외 없음(비숫자/결측 금액은 fail-safe null), null `transactionRef` 행은 알럿 조인 스킵(`alertCount=0`). `alertCount`/`firedRuleCodes`(distinct `scenario_code`, 최대 5건)는 `aml_alerts` `(tenant_id, transaction_ref)` 매칭 중 **`status<>'RETIRED'`만 집계**(F-034 정합, `includeRetired` 파라미터 없음). 집계·enrich 없는 단순 페이지 조회(알럿 큐 `GET /api/v1/aml/alerts`와 동일 평면·동일 scope, 저수준 데이터 read) | `aml_canonical_events`,`aml_alerts` |

> 엔진(aml-svc) public 알림 목록은 `status`(optional, 미지정=전체)·`rule`·`channel`·`corridor` 필터의 큐 조회다. **운영자 화면용 다중 필터 브라우즈 목록(`sourceOrigin`·`severity`·`scenario`·`channel`·`corridor`·`targetRef`·`from`/`to`)은 bo-api `GET /api/v1/bo/aml/alerts`(§2.5a)** 가 위임·집약한다. **거래(canonical events) 다중 필터 브라우즈는 `GET /api/v1/aml/transactions`(본 표) 를 bo-api `GET /api/v1/bo/aml/transactions`(§2.5a)가 verbatim 위임**한다(집약·enrich 없음) — 이 예외는 aml-svc 에 canonical events 서버 페이징 브라우즈 경로가 이미 없다는 뜻이 아니다: **증적(evidence) 평면 `GET /api/v1/evidence/aml/customers/{customerRef}/fund-view`(§2.5, scope `aml:evidence:export`)가 주체(customerRef) 한정·`FEED_WINDOW` 30일 고정·알럿 조인 없이 기존재**한다. `GET /api/v1/aml/transactions`는 그와 **계약이 분리된 운영 조회 평면 신설**이다 — 엔진이 `aml_canonical_events` 소유자로서 **테넌트 전역·전 기간·알럿 동봉(RETIRED 제외)** 저수준 페이지 조회를 scope `aml:case:read`로 직접 제공한다(§1.1 실측·PLAN 20260819 A13). '기존 브라우즈 경로 전무'라는 서술은 부정확하다.

> **알림 lifecycle 상태기계(코드=truth, `AlertController`·`domain/Alert.java`).** `DETECTED ──:triage──▶ TRIAGED ──{:open-case|:dismiss|:escalate|:recommend-str}──▶ {CASE_OPENED|DISMISSED|ESCALATED|STR_RECOMMENDED}`(6종 종결값, DB §5.7). `:dismiss` 만 `DETECTED`/`TRIAGED` 양쪽에서 허용(1차 분류 없이 즉시 오탐 종결 가능)하고, 나머지 3종(`:open-case`/`:escalate`/`:recommend-str`)은 `TRIAGED` 에서만 허용된다. **`dispositionReason`/`dispositionActor` 불변식: `DISMISSED` 전이에서만 non-null**(그 외 상태는 null). 불법 전이는 `IllegalStateException`→**409 `AML.STATE_CONFLICT`**("Expected status TRIAGED but was DETECTED" 등)로 표면화하며, bo-api `AmlEngineClient.mapError` 가 안전한 기대/실제 상태 토큰만 구조화해 bo-web 이 사용자 라벨을 매핑한다(§2.5a·free-text 미에코). 4-eyes 비대상(scope `aml:case:update` 단일 — 케이스 `:close`(EDD_CLOSE)·FDS CASE_CLOSE만 2인 결재, 가정 G2).
>
> **`RETIRED` 는 위 상태기계의 일부가 아니다(별도 축, 2026-08-06 V63).** 진입 경로는 설정형 룰 회수(`:retire` 4-eyes 승인 실행) 하나뿐이고 `aml:case:update` 액션으로는 도달할 수 없다. 룰이 무효화됐으므로 그 알림을 운영 목록·룰 효과성 통계에서 빼되 **행은 삭제하지 않고 보존**하며(감사 추적), 이미 케이스가 개설된 알림은 회수 대상에서 제외된다. `DISMISSED`(분석가의 오탐 종결)와 의미가 달라 그 상태를 재사용하지 않는다 — 오탐 종결된 알림도 회수될 수 있고, 그때 `dispositionReason`/`dispositionActor` 는 그대로 남는다. `RETIRED` 알림에 대한 triage 액션(`:triage`/`:dismiss` 등)은 409 `AML.STATE_CONFLICT`.

> **알림 read 경로 마스킹 verbatim·자동 복호화 없음(코드=truth, `AlertController`·`AlertRelatedTransactionsService`, P0-09).** `GET /api/v1/aml/alerts/{alertId}`·`GET /api/v1/aml/alerts/{alertId}/related-transactions`·`GET /api/v1/aml/alerts`(목록)의 `aml:case:read` 경로는 **저장된 마스킹/토큰 evidence 를 verbatim 반환**하며 어떤 자동 복호화(구 `enrichEvidence`)도 수행하지 않는다 — SANCTION/PEP 당사자 원문·매칭 워치리스트 엔트리 원문·수취인 원문 이름을 이 경로에서 reveal 하지 않는다. `RelatedTransactionDto.counterpartyName` 은 `aml:case:read` 에서 **항상 null**(마스킹 토큰 `counterpartyRef` 폴백)이고, 원문은 오직 감사되는 `aml:pii:reveal` reveal API(`POST /internal/v1/aml/pii/reveal`, §2.6)에서만 요청 한정 transient cleartext 로 산출된다(사유+`RAW_DATA_ACCESS` 감사·fail-closed). Subject360 fund-view read(§2.5a) 역시 COUNTERPARTY 노드를 토큰(+국가 폴백) 라벨로 표시하고 원문 이름을 자동 reveal 하지 않는다.

> **P0-09 국지 카브아웃.** 위 마스킹 계약은 알림·근거거래·Subject360·evidence 평면에 그대로 적용된다. 다만 WLF 스크리닝 읽기 두 표면(`GET /aml/screenings/{id}`·`GET /admin/aml/screenings`)의 `requestName`·`matchedEntryNames` NAME 2종만 §1.6의 인라인 예외를 적용하며, `counterpartyName` 또는 다른 PII 필드를 이 예외로 확장하지 않는다.

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
| POST | `/api/v1/bo/aml/alerts/{alertId}:triage` | `aml:case:update` | — | **알림 1차 분류 위임**(`DETECTED`→`TRIAGED`). body optional `AlertTriageRequest{actor?}`. 응답 `AlertActionResponse{alertId, status, caseId?, caseStatus?, dispositionReason?}`(`dispositionReason` 은 `:dismiss` 전용 에코 — `:triage` 는 null·NON_NULL 생략). aml-svc `:triage` 위임(비운영 stub 은 라이브 인메모리 알림 상태 전이·prod 미설정 위임 fail-closed 503 `AML.ENGINE_UNAVAILABLE`, 가정 G7). 감사 `AML_ALERT_TRIAGED`(비-4-eyes) | `aml_alerts` |
| POST | `/api/v1/bo/aml/alerts/{alertId}:dismiss` | `aml:case:update` | — | **알림 오탐 종결 위임**(`DETECTED`/`TRIAGED`→`DISMISSED`). body `AlertDismissRequest{reason 필수(@NotBlank), actor?, note?(@Size≤1000)}` — **`reason` 공백 시 400**(bo-api 계층에서 사유 필수 강제, G1)으로 오탐율(§12-B.3) 실 분모·감사 근거 확보. 위임 시 optional `{reason, actor}` 를 엔진 `:dismiss` 로 전달한다. **`note`(판단 근거 자유 메모, 기능정의서 §7.1 BR-002a)는 엔진에 싣지 않고 bo-api 감사 detail 에 보조 저장**한다 — 엔진 `:dismiss` 계약이 `{reason, actor}` 뿐이고 `aml_alerts.disposition_reason` 은 코드 컬럼(VARCHAR(64))이라 자유 텍스트를 담을 자리가 없다(FDS 기능정의서 §11.2 BR-007 · DB §4.11 "코드와 분리 보조 저장" 동형). 공백만 입력한 메모는 감사 detail 에 키를 만들지 않는다. 응답 `AlertActionResponse` — **`dispositionReason` 서버 에코**(엔진 `AlertDto.dispositionReason` 우선, 엔진이 비우면 요청 `reason` 폴백; stub 경로도 동일 값 반환)로 호출자가 재조회 없이 기록된 사유를 확인한다. 감사 `AML_ALERT_DISMISSED`(사유 + 메모 동반) | `aml_alerts` |
| POST | `/api/v1/bo/aml/alerts/{alertId}:escalate` | `aml:case:update` | — | **알림 상위 승인 위임**(`TRIAGED`→`ESCALATED`, 케이스 개설). body optional `AlertHandOffRequest{caseType?, actor?}`. 응답 `201 AlertActionResponse`(`caseId`/`caseStatus` 포함). aml-svc `:escalate` 위임(stub 은 케이스 미조작·라이브 알림 전이만). 감사 `AML_ALERT_ESCALATED` | `aml_alerts`,`aml_cases` |
| POST | `/api/v1/bo/aml/alerts/{alertId}:recommend-str` | `aml:case:update` | — | **알림 STR 권고 위임**(`TRIAGED`→`STR_RECOMMENDED`, STR 케이스 개설 + 엔진 아웃박스 적재). body optional `AlertHandOffRequest{caseType?, actor?}`. 응답 `201 AlertActionResponse`(`caseId`/`caseStatus`). aml-svc `:recommend-str` 위임. 감사 `AML_ALERT_STR_RECOMMENDED` | `aml_alerts`,`aml_cases` |
| GET | `/api/v1/bo/aml/transactions?transactionRef=&eventId=&memberRef=&product=&from=&to=&page=&size=` | `aml:case:read` | — | **TM 알림 큐와 별도인 최근 거래 목록 위임**(AML-TM-001 ③, PLAN 20260819 BOA-1). aml-svc `GET /api/v1/aml/transactions`(위 §2.4)를 위임(응답 가공·enrich 없음 — plane parity 대상). 단 요청 경계 2건은 bo-api 가 흡수한다(2026-08-19 리뷰 H2·M1): ① **`from`/`to` date-only(`YYYY-MM-DD`) 파싱 계약 흡수** — 알럿 브라우즈 `AmlTmService#parseInstant` 선례와 동형으로 `from`=당일 00:00Z, `to`=**익일 00:00Z 배타** 정규화 후 ISO instant 로 위임(ISO instant 입력은 그대로, 파싱 불가 400 `AML.BAD_REQUEST`), ② 쿼리 값별 `UriUtils.encodeQueryParam` 인코딩(특수문자 파라미터 주입 차단). 위임 미설정 비운영은 `AmlStubFallbackGuard` 통과 후 결정적 stub 고정 3행(`transactionRef` 필터만 인메모리 적용), prod 미설정 위임은 fail-closed 503 `AML.ENGINE_UNAVAILABLE`. 응답 `ApiResponse<{rows,page,size,totalCount}>`(행 필드 동일 — A13). `@PreAuthorize("hasAuthority('aml:case:read') or hasRole('BO_SUPER_ADMIN')")` | — |
| GET | `/api/v1/bo/aml/tm-scenarios/{scenarioCode}` | `aml:admin:policy` | — | **TM 시나리오 정의 read model**(AML-TM-002, **V61 이후 자유형 코드 — generic decode**). `scenarioCode` 는 형식만 검증(`^[A-Z][A-Z0-9_]{2,64}$`, 레거시 닫힌 enum 파싱 폐기). bo-api BFF가 엔진 active `parameters`/`dsl`을 **per-code 템플릿 없이(`ScenarioTemplates` 삭제)** `ScenarioDefinition{family, severity, fields[]}`로 generic 디코드해 반환한다(DTO §3.4c) — `family` 는 dsl 트리에 `velocity` 노드 존재 여부로 `THRESHOLD`/`SIGNAL` 파생, `fields[]` 는 `parameters` 값 타입(Number/Boolean/List/String)으로 파생(per-code switch 없음). NUMBER/AMOUNT 임계 필드는 위험등급별 차등 임계(`CriterionField.thresholdsByGrade`, §3.4c)를 동반 노출한다. **정의 부재(engine/stub 공통) = 404**(레거시 정의 10종 제거로 신선 배포·미저작 코드는 항상 404가 정상). raw PII 없음, 설정 조회 전용. **이 read model 이 반환하는 active `dsl` 은 §2.7 `:activate` read-back(아래) 의 원문 보존 입력이기도 하다.** | 정책 store(read model) |

> bo-api 소유 집계(read-only 파생, raw PII 미노출). STR 건수 등 tipping-off 민감 항목은 준법감시 전담 scope 한정 투영(설계서 §19.2a). 엔진 `GET /aml/customers/{customerRef}/profile`(CDD-002)·`/risk`를 결합하며 별도 영속 테이블 없음.

> **알림 lifecycle 위임 4종 + 409 표면화 계약(코드=truth, `AmlTmController`·`AmlTmService`·`AmlEngineClient`).** bo-api `AmlTmController` 는 위 4개 알림 처분 액션을 aml-svc 엔진 `AlertController`(§2.4 `:triage`/`:dismiss`/`:escalate`/`:recommend-str`)에 위임한다. 위임 모드=`AmlEngineClient` 경유 엔진 호출, 비운영 stub 모드=라이브 인메모리 알림 상태 전이 즉시 반영(동형 응답), 운영 프로필 미설정 위임=fail-closed(503 `AML.ENGINE_UNAVAILABLE`, 가정 G7). 4종 모두 4-eyes 비대상(케이스 `:close`(EDD_CLOSE)·FDS CASE_CLOSE만 2인 결재 유지, 가정 G2)이며 감사 이벤트 `AML_ALERT_TRIAGED`/`AML_ALERT_DISMISSED`/`AML_ALERT_ESCALATED`/`AML_ALERT_STR_RECOMMENDED`(bo-api Flyway V13 `chk_bo_audit_logs_event` allowlist)를 각각 남긴다. **409 `AML.STATE_CONFLICT` 표면화**: `AmlEngineClient.mapError` 는 엔진 free-text detail 을 에코하지 않고(내부/PII 누출 방지, 가정 G8) **알림 상태 6종 enum 토큰(`DETECTED`/`TRIAGED`/`CASE_OPENED`/`DISMISSED`/`ESCALATED`/`STR_RECOMMENDED`)만** 추출해 `"AML.STATE_CONFLICT expected=<상태> actual=<상태>"` 로 구조화하며, 그 외 모든 단어는 폐기한다 — bo-web `lib/error-messages.ts`+i18n 카탈로그가 이 구조화 필드로 "먼저 1차분류하세요" 같은 사용자 라벨을 매핑한다. 비운영 stub 경로도 동일 상태기계를 모사해 동일 409 를 던진다(버튼 무반응 해소).

### 2.6 Internal API (엔진 간) — 설계서 §6.1·§12.3·D-07

| 메서드 | 경로 | 호출자 | 설명 | DB |
|---|---|---|---|---|
| POST | `/internal/v1/aml/fds-escalations` | `fds-svc` | FDS fraud case → AML case/alert escalation 수신(body §3.10 `FdsEscalationRequest` → `FdsDecisionCommand` 어댑팅, `eventId`=멱등키(없으면 `fraudCaseRef`), `action`=FDS handoff verb, 응답 `{ alertId, accepted }`). SQS `aml-fds-decision` 큐 경로(`FdsDecisionConsumer`)와 **동일 usecase·동일 멱등(DB partial UNIQUE)·동일 감사**(T11/AML-ENG-05). non-AWS REST fallback은 wire v2-only, `aml:internal:fds-escalation:write`, signed `X-Internal-Service=fds-svc`, body/header dataScope 일치를 수신 엔진에서 강제한다. | `aml_alerts`(source_origin=FDS) |
| GET | `/internal/v1/aml/customers/{customerRef}/risk` | `fds-svc` | AML high-risk/WLF 상태 조회(FDS risk group 전파용). public `GET /api/v1/aml/customers/{customerRef}/risk`와 동일 `AssessRiskUseCase`·`CustomerRiskResponse` 재사용(가정 A6) — **동일 stage-aware operative 선정**(PLAN 20260722-ra-tm-2nd-stage-fixed-scenario-consistency B1, "FDS 가 보는 등급 = 화면 등급" 단일 정본, WLF 병합 미정의 → 후속). 미존재 시 404 `AML.NOT_FOUND`. wire v2-only + `aml:case:read`. | `aml_risk_scores`,`aml_screening_results` |

> **RA 검토·설정 계약(2026-07-10)**: `GET /api/v1/aml/customers/{customerRef}/risk`는 최신 점수가 ONGOING이어도 대상의 최신 ONBOARDING 검토를 `onboardingReview`로 함께 반환한다. 상태는 `REQUIRED|COMPLETED|AUTO_COMPLETED`, 필드는 `scoreId/reasonCodes/identityChecked/evidenceChecked/followUpChecked/completionNote/completedBy/completedAt/createdAt`이다. RA model draft 계약은 `scenario`와 `parameters`를 수신하며 ONBOARDING `screening.listTypeScores.{SANCTION,PEP}` 및 ONGOING `ruleSeverityWeights`(STR/CTR/FDS), lookback/count saturation/debounce/EDD 설정을 검증한다. APPROVED/SUPERSEDED 버전 직접 수정은 409/상태 오류이며 신규 DRAFT→simulate→RA_MODEL 4-eyes만 허용한다.
| POST | `/internal/v1/aml/screen` | 내부 onboarding mesh | 내부 서비스용 동기 screening. public `POST /api/v1/aml/screen`와 동일 `ScreenSubjectUseCase`·`ScreenRequest`/`ScreeningResponse` 재사용(가정 A6), `Idempotency-Key` 헤더 필수(가정 A4·공개 경로 일관). wire v2-only + `aml:screen:evaluate`. | `aml_screening_results` |
| POST | `/internal/v1/aml/pii/reveal` | `bo-api` | 마스킹 PII reveal 정본(입력 `targetRef`/`field`/`reason` → 출력 `value`=이 요청 한정 transient cleartext). **`targetRef` = subject 참조**(회원 `customerRef` 또는 워치리스트 엔트리 `entryId`) — vault·엔진이 이 참조로 원문을 해소한다. 마스킹 **값** 토큰(표시명 마스킹·문서/이름 hash·UBO ref 등)을 `targetRef` 로 보내면 해소 불가(run5 #2). `field` 도메인 7종(`NAME`/`DOC`/`ACCOUNT`/`WALLET`/`NATIONALITY`/`GENDER`/`DOB`, §1.6, 2026-06-29 확장) — 이외 값은 **400 `AML.BAD_REQUEST`**. wire v2-only + `aml:pii:reveal` + exact signed `X-Internal-Service=bo-api`를 수신 엔진에서 강제한다. 엔진측 `RAW_DATA_ACCESS` 감사 1건(마스킹 detail). 역참조 미존재·복호화 실패 시 **503 `AML.SCREENING_UNAVAILABLE`**(fail-closed). **비운영 stub 경로**(bo-api, delegate 미설정)에서 vault·데모 카탈로그 어디에도 없는 미인식 `targetRef` 는 가짜 원문 placeholder 를 반환하지 않고 **404 `AML.PII_TARGET_NOT_FOUND`**(감사 미기록 — 실패가 audit 이전, run5 #2). mesh mTLS는 배포계층(P8) 보강. | `aml_pii_vault`(가역암호 vault, DB §3.21) |

### 2.7 Admin API (bo-api 전용) — 설계서 §13~§14·§16

#### Tenant Policy Binding (§16, P0-16)
| 메서드 | 경로 | scope | 4-eyes | 설명 | DB |
|---|---|---|---|---|---|
| PATCH | `/api/v1/admin/aml/tenants/{tenantId}/policy-binding` | `aml:admin:policy` | — | **테넌트 관할·통화·Policy Pack revision 바인딩(P0-16, upsert)** — tenant 를 REST 로 `PH·PHP` 또는 `KR·KRW` 등에 바인딩하는 프로비저닝 진입점(데모 비즈니스 seed 아님). 요청 `BindRequest{ jurisdiction(ISO 3166-1 alpha-2, 필수), baseCurrency(ISO 4217, 필수), reportingCurrency?(생략 시 baseCurrency), timezone(유효 IANA region ID, 필수), policyPackVersion(필수) }`. `Tenant-Id` 헤더=경로 `tenantId` 일치 필수(불일치 = cross-tenant write 거부). null·blank·invalid timezone과 fixed-offset ID(`+10:00`, `GMT+10:00`), 잘못된 ISO country/currency는 write 전에 `400 AML.VALIDATION_ERROR`, 이미 저장된 legacy missing/invalid/fixed-offset timezone은 인입에서 `422 AML.TENANT_POLICY_UNBOUND`(Manila 기본값 없음), 미존재 tenant/비-effective Policy Pack revision도 `422 AML.TENANT_POLICY_UNBOUND`다. **거래성 이력 보유 테넌트의 기준통화(`baseCurrency`) 변경은 fail-closed — `422 AML.TENANT_CURRENCY_HISTORY_LOCKED`**(다통화, PLAN 20260818 — `baseCurrency` 이외 필드 변경은 이력과 무관하게 허용). 멱등 upsert. `reportCutoffTime` 필드는 본 PATCH 로 갱신하지 않는다(전용 PUT 서브리소스로 분리 — 아래 행). 응답 스키마 불변 `200 { tenantId, jurisdiction, baseCurrency, reportingCurrency, timezone, policyPackCode, policyPackVersion, policyPackEffectiveFrom }`(= `TenantPolicyBinding`). | `aml_tenants`(DB §3.1·V53) |
| PUT | `/api/v1/admin/aml/tenants/{tenantId}/policy-binding/report-cutoff-time` | `aml:admin:policy` | — | **법정 보고 마감시각 always-write 전용 서브리소스**(다통화, PLAN 20260818 — `PATCH .../policy-binding` 은 cutoff 무접촉). 요청 `CutoffRequest{ reportCutoffTime: "HH:mm" }` — 명시 `null` 은 컬럼 clear(필드가 "부재"로 취급되지 않는다). tenant 행 미존재 시 404. 응답 `200 { tenantId, reportCutoffTime }`. | `aml_tenants.report_cutoff_time` |
| GET | `/api/v1/admin/aml/tenants/{tenantId}/policy-binding` | `aml:admin:policy` | — | **raw 바인딩 read-back**(다통화, PLAN 20260818 — U1 작업 5(b), `resolve()` 단독 사용 금지). `resolve()` 를 거치지 않고 tenant 행을 그대로 12키 투영한다: `{ tenantId, jurisdiction, baseCurrency, reportingCurrency, timezone, policyPackCode, policyPackVersion, policyPackEffectiveFrom, reportCutoffTime, calendarCoverage("PRESENT"/"MISSING"), policyPackResolved(boolean), transactionalHistory(boolean) }`. jurisdiction/baseCurrency/reportingCurrency/timezone 4열 중 하나라도 미설정이거나 이미 저장된 legacy timezone이 유효 IANA region이 아닌 값(`Not/A_Zone`, `+10:00`, `GMT+10:00` 등)이면 `422 AML.TENANT_POLICY_UNBOUND`(=미바인딩, invalid raw 값 미노출). 4열이 모두 유효하지만 핀 Policy Pack revision 이 비-effective(stale/absent/DRAFT)면 **200 + `policyPackResolved=false`**로 구분한다(바인딩 존재와 pin 유효성을 혼동하지 않음 — r4 이격 2). | `aml_tenants`(DB §3.1·V53) |

> **정책 표면 구획(§0.5 온보딩 경계와 별개).** §0.5 는 **배포 모델·온보딩 신청**(서비스 등록·프로비저닝 상태머신)을 bo-api 소유로 두고 aml-svc 엔진 API 에 미추가함을 정본으로 한다. 본 `PATCH .../tenants/{id}/policy-binding` 은 그 온보딩 표면이 아니라 **엔진 규제 정책 표면**(관할·통화·Policy Pack revision — 엔진 corridor/통화 해석·evidence 고정의 입력)이며, 이미 등록된 tenant 의 정책 바인딩을 설정한다. 온보딩(`/api/v1/bo/aml/tenants`·`/onboarding/*`, bo-api 전용)과 정책 바인딩(엔진 `/api/v1/admin/aml/tenants/{id}/policy-binding`)은 **서로 다른 표면**으로 구획한다(온보딩=서비스 lifecycle, 정책 바인딩=규제 파라미터). bo-api tenant shadow 의 관할·통화 동기는 후속(phase-2 A1 경계).

#### Watchlist / 명단 (§10)
| 메서드 | 경로 | scope | 4-eyes | 설명 | DB |
|---|---|---|---|---|---|
| GET | `/api/v1/admin/aml/watchlist-sources` | `aml:admin:watchlist` | — | source 목록 | `aml_watchlist_sources` |
| POST | `/api/v1/admin/aml/watchlist-sources` | `aml:admin:watchlist` | — | source 등록 | `aml_watchlist_sources` |
| POST | `/api/v1/admin/aml/watchlist-sources/{sourceCode}/imports` | `aml:admin:watchlist` | — | import 업로드(diff 생성, DRAFT) | `aml_watchlist_entries` |
| POST | `/api/v1/admin/aml/watchlist-sources/{sourceCode}/imports/{version}:apply` | `aml:admin:watchlist` | 🔒4-eyes | import 적용(active_version 승격) | `aml_watchlist_sources` |
| POST | `/api/v1/admin/aml/watchlist-sources/{sourceCode}/sync` | `aml:admin:watchlist` | — (auto-apply, 4-eyes 아님) | **명단 소스 동기화 — 코드 7종**(`OFAC_SDN`·`UN_CONSOLIDATED`·`EU_CFSL`·`UK_OFSI`·`AU_DFAT`·`JP_MOF_FEFTA`·`DILISENSE_CONSOLIDATED`, `WatchlistFeedRouter` 라우팅). 공개 6종은 OFAC/UN/EU/UK StAX XML, AU 자체 XLSX reader, JP HTML→CSV 2단계 discovery 파서를 사용하고 dilisense는 JSON Lines 전량/delta를 사용한다 — fetch→파싱→멱등 upsert(외부키 `external_ref`, entry-id 승계)→**auto-apply**(actor `system:sanctions-sync`, 공개·권위 소스는 사람 승인 없이 `active_version` 승격)→DELISTED 보존→freshness 갱신. 외부망 장애는 예외 미전파(fail-safe, 200+`outcome=FAILED`) — freshness 미갱신 시 48h 게이트가 스크리닝 fail-closed(설계 의도). **`DILISENSE_CONSOLIDATED`는 API 키 미설정(`AML_WATCHLIST_DILISENSE_API_KEY`) 시 항상 `outcome=FAILED`**(설정 오류를 fail-safe 로 흡수 — 예외 미전파)이며, 필수(mandatory) 정책으로 별도 등록(§343)하지 않는 한 이 FAILED 자체가 스크리닝을 차단하지 않는다(비-mandatory 소스는 freshness 게이트 대상 밖). 응답 `WatchlistSyncResult`(sourceCode·outcome(APPLIED/UNCHANGED/FAILED)·activeVersion·ingestedCount·delistedCount·prunedCount·lastImportedAt). 스케줄러(기본 03:20 UTC, `SanctionsImportScheduler`) 일일 자동 + 본 엔드포인트 수동 트리거. | `aml_watchlist_sources`,`aml_watchlist_entries` |
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
| GET | `/api/v1/admin/aml/wlf-engine-config` | `aml:admin:watchlist` **or** `aml:admin:policy` | — | tenant의 런타임 적용 WLF 룰 버전과 정책팩 버전 이력, SANCTIONS·PEP별 가중치/불일치 감점/검토·고신뢰 임계 조회. 기존 WLF 시뮬레이션 운영자는 현재 적용 기준 조회만 허용한다. `status=ACTIVE && active=true`를 동시에 만족하는 정책팩이 없거나 복수이면 screening 선택과 동일하게 fail-closed한다. typed profile 키가 없는 legacy/pending 이력은 저장된 `wlf.possible-threshold`/`wlf.true-threshold`를 우선 SANCTIONS·PEP에 fan-out하고, 나머지 누락값은 코드 기본 profile(6가중치·negativePenalty 0.20, 기본 band 0.66/0.92)로 하위호환 해석한다. 유효하지 않은 수치·임계 또는 저장된 definitionHash 불일치는 fail-closed하며, V38은 비-DRAFT 이력을 canonical typed form으로 보강한다. **응답 `pepAxis` 유효정책 블록(2026-08-13 additive, 읽기 전용)**: `{ enabled, policyVersion(`wlf-pep-axis-v2`), unknownOutcome(`SUPPRESS`\|`MATCH`\|`RISK_SIGNAL`), customerRequiresCorroborator, customerMinimumCorroborators, acceptedCorroborators[], dobCorroboratorFloor, counterpartyRiskSignalOnly }` — 이 테넌트에서 **지금 유효한** PEP 축 분리 정책이다. 건별 `scoreBreakdown.pepAxis` 는 후보가 있었던 스크리닝 행에만 붙어 운영자가 테넌트 유효값을 알려면 억제된 건을 하나 찾아 열어야 했다. 값은 정책팩(4-eyes 승인 대상)이 아니라 aml-svc 런타임 설정(`aegis.aml.wlf.pep-axis.*`)이라 **이 응답에서는 읽기 전용**이며 `:change` 요청 스키마는 무변경이다(테넌트별 4-eyes 편집 승격은 범위 밖 — policy-pack 스키마 변경 = 전 테넌트 재승인). bo-api BFF 미러는 이 블록의 필드를 하나도 버리지 않고 통과시키며(구버전 엔진이 안 내려주면 `null`), bo-web `/aml/wlf-engine` 화면 상단이 배지로 표기한다. | `aml_policy_packs.parameters` |
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

> **단건 시뮬레이션 profile 필터.** Admin/BFF `POST .../screenings:simulate` 요청은 `{ name, nameRomanized?, similarityThreshold?, targetType?, dob?, country?, documentHash?, sourceTypes? }`를 사용한다. 이 분석 전용 경로는 기존 WLF 도구의 `aml:admin:watchlist`와 AML-WLF-005의 `aml:admin:policy` 중 하나를 허용한다(일괄 수행·template은 계속 watchlist 권한 전용). `sourceTypes`는 명단 소스 유형의 닫힌 배열이며 AML-WLF-005는 SANCTIONS 탭에서 `['SANCTIONS']`, PEP 탭에서 `['PEP','RCA']`를 보낸다. 생략 시 모든 ACTIVE 명단을 평가한다. 서버는 ACTIVE 전체 정의를 1회 pin하고 후보 조회·profile 선택 모두에 이 필터를 적용한다. 응답의 적용 임계와 `appliedPolicy`는 실제 ACTIVE 설정에서 파생한다. 호출자가 임의 `similarityThreshold`를 보낸 경우 분석용 override이며 ACTIVE `highConfidenceThreshold` 미만이어야 하고 영속 screening/ACTIVE 정책을 변경하지 않는다. **저장 정밀도 진단(`scoreBreakdown.scorePrecision`, 2026-08-11)**: 응답의 `score`는 저장 스케일(`numeric(8,4)`)이고 밴드는 반올림 전 원본 정밀도로 결정되므로, 두 값이 서로 다른 밴드를 낳을 때만 `{ storedScore, comparedScore, band, storageScaleBand, decidedOn:"FULL_PRECISION" }`를 기존 free-form `scoreBreakdown` 안에 **가산 키**로 동봉한다(밴드가 일치하면 키 자체가 없어 응답 바이트 동일). `SimulateResult` 레코드 시그니처·WLF-004 응답 계약은 불변이다. **실운영 판정 parity(2026-08-12)**: 시뮬레이션은 실운영 스크리닝과 **같은 순수 판정 함수**(`WlfMatchVerdict`)와 **같은 PEP 축 정책 인스턴스**를 사용한다 — 이전에는 simulate 가 PEP 축 분리 정책도 §10.3a 이름 강한 일치 승격도 건너뛴 자체 계산을 해 같은 입력이 시뮬레이션 `REVIEW` / 실운영 `NO_MATCH` 로 갈렸고, 운영자가 실운영에 존재하지 않는 보류율을 근거로 임계를 조정하거나 4-eyes 승인을 낼 수 있었다. 호출자의 `similarityThreshold` 는 **review 임계 override 로만** 쓰이며 상위 밴드(`highConfidenceThreshold`) 판정은 override 대상이 아니다. 축 정책이 시뮬레이션의 매치를 억제하면 실운영과 **같은 형태의 `pepAxis` 근거 블록**(§3.2)을 기존 free-form `scoreBreakdown` 안에 가산 키로 동봉한다(억제가 없으면 키 자체가 없어 응답 바이트 동일). `targetType` 신뢰 경계도 실운영과 동일하게 적용해 등록 회원의 `COUNTERPARTY` 선언은 더 엄격한 CUSTOMER 축으로 정정하되, 후보 recall 은 선언된 축 기준을 유지한다. bo-api BFF `SimulateResponse` 는 이 블록을 `pepAxis` 컴포넌트로 투영한다(가산 — 정책 비적용 시 생략, 다른 필드 직렬화 불변). **후보 회수 옵션 parity(2026-08-13 — 위 parity 서술의 사실 정정·보강)**: 위 조항은 **판정 함수·정책 인스턴스** 축만 닫은 것이었고, **후보를 무엇으로 회수하는가**는 여전히 갈려 있었다 — 시뮬레이션은 `CandidateOptions.defaults()`(cap 200 / trgm floor 0.30 / phonetic on / statement timeout 10 s)를 자체 조립했고, 실운영은 `aegis.aml.wlf.candidate.{cap,trgm-floor,phonetic-enabled,statement-timeout-ms}` 로 조립했다. 두 값이 다른 테넌트에서는 **같은 판정 함수를 태워도 후보 집합이 달라 결과가 반대로 갈린다**(운영 cap 500 인 테넌트에서 축 rank 201 의 진성 제재 후보 → 실운영 `POSSIBLE_MATCH` / 시뮬레이션 `NO_MATCH`, cap 을 낮춘 테넌트에서는 반대 방향). 이제 **조립 지점은 실운영 스크리닝 한 곳**이며(`ScreenSubjectUseCase.candidateRecallOptions()` 로 공표), 시뮬레이션은 값을 복제하지 않고 그 유스케이스에서 **읽어 간다** — 배선 실수로도 갈릴 수 없고 새 회수 knob 이 생기면 자동 반영된다. 어떤 옵션·절단 상태로 돌았는지는 응답 `scoreBreakdown.candidateRecall`(§3.2, 가산 키)로 드러낸다. 회수 knob 은 **what-if 입력이 아니다** — 요청 스키마에 회수 파라미터를 신설하지 않으며 what-if 축은 `similarityThreshold` 하나로 유지된다.

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
| POST | `/api/v1/admin/aml/ra-models` | `aml:admin:policy` | — | `versions:copy`로 서버 발급된 기존 DRAFT 전체 정의만 갱신한다(update-only). 요청 `DraftRequest{ modelCode, version, scenario, weights, mediumThreshold, highThreshold, prohibitedThreshold, parameters }`. 임의 신규 version, family-scenario 불일치, ACTIVE/SUPERSEDED 및 활성화 결재 대기 DRAFT는 수정 불가. 가중치는 scenario factor catalog(ONBOARDING=`GEOGRAPHY/CUSTOMER/SCREENING`, ONGOING=`TRANSACTION_BEHAVIOR/CUSTOMER`)와 `0..100`, 총합 양수를 검증한다. parameters는 §11.3의 scenario별 top-level/nested unknown key를 거부한다. ONBOARDING authoring은 `sofRisk=default+canonical 6종`, `kycLevelRisk=default+canonical 4종`, `occupationRisk=default+안전 분류코드`만 허용한다. 과거 ACTIVE legacy는 조회/복제할 수 있지만 DRAFT 저장·simulate·activate 전에 제거해야 한다. ONGOING 정수값은 소수 절삭 없이 exact integer이며 `lookbackDays=1..3650`, `debounceMinutes=0..525600`, `countSaturation=1..200`, baseline=`KR_DEFAULT_RA`를 강제한다. **ONGOING `parameters` 는 선택키 `signalScaling` 을 허용한다(2026-08-13 additive — 허용키 7 → 8)**: `{ "<origin>": { rules[], curve(LINEAR\|STEP), floorScore, ceilingScore, minMultiplier, maxMultiplier } }` 형태이며 하위 unknown key 도 거부한다. 불변식은 `0 ≤ floorScore < ceilingScore ≤ 1` · `0 < minMultiplier ≤ maxMultiplier ≤ 1` · `rules` 비어있지 않고 중복 없음 · 룰코드 `(STR\|CTR\|FDS)_.+` · **`STR_SANCTION` 포함 거부**(제재는 이름 유사도로 스케일하지 않는다) · origin 키 `[A-Z][A-Z0-9_]{0,63}` 이고, 위반은 **저장 시점 400**(부팅 전 fail-fast)이다. **허용키에 없으면 이 블록을 담은 DRAFT 저장 자체가 400 이 되어 "관리 메뉴에서 고친 점수가 엔진에 반영된다" 가 성립하지 않으므로 읽기·쓰기 두 경로가 함께 확장됐다.** 키 자체가 **선택**이라 기존 ACTIVE 정의는 무영향(전 테넌트 재승인 불요)이고 부재 = 미적용(배수 항등원 1.0). 의미론 정본은 설계서 §11.3a. 작성자는 BFF 인증 principal에서 파생한다. | `aml_risk_models` |
| POST | `/api/v1/admin/aml/ra-models/{modelCode}/simulate` | `aml:admin:policy` | — | 요청 `RaSimulateRequest{ version, samplePopulation }`, 모집단 `RECENT_90D_NEW\|ALL_ACTIVE\|HIGH_RISK_ONLY`(tenant·scenario 격리, 최대 500). candidate와 같은 scenario ACTIVE를 실제 비PII RA 입력으로 재평가하고 결과/definition hash를 영속한다(§3.15). 결재·실제 등급 변경 없음. | `aml_ra_model_simulations`,`aml_risk_scores` |
| POST | `/api/v1/admin/aml/ra-models/{modelCode}/versions/{version}:activate` | `aml:admin:policy` | 🔒4-eyes | 요청 `ActivateRequest{ simulationId, reason }`. 성공한 simulation의 대상 버전·canonical definition hash가 현재 DRAFT와 일치해야 상신된다. `RA_MODEL` payload hash는 전체 정의를 고정하고 approve 시 재검산한다. 승인 실행 시 같은 tenant+scenario 기존 ACTIVE를 SUPERSEDED하고 새 버전을 ACTIVE로 원자 전환한다(ONBOARDING default도 이전). 작성자는 BFF 인증 principal에서 파생. 응답 `202 { approvalId, status: SUBMITTED, payloadHash }`. | `aml_risk_models`,`aml_ra_model_simulations`,`aml_approvals` |
| GET | `/api/v1/admin/aml/risk-scores?riskGrade=&modelVersion=&country=&reviewDueSoon=&targetRef=&scenario=&requiredAction=&registeredWithinDays=&latestPerTarget=&mandatoryHighRisk=&excludeOngoingTargets=&operativePerTarget=&page=&size=` | `aml:case:read` | — | **RA 점수 목록**(모니터링). `riskGrade` 멀티(콤마 구분)·`modelVersion`·**`country`(국적 필터, 엔진이 실제 국가 차원 보유·#7; stub 경로는 `targetRef` seed 파생 결정적 국가 post-filter)**·`reviewDueSoon`(boolean — 재심사 임박)·`targetRef`(contains 검색)·페이지네이션 필터. **RA 목록 서버 필터 4종(2026-07-06, feature/aml-ra-list-filters-dedupe — 전부 optional·additive)**: ① `scenario`=`ONBOARDING`(1차)\|`ONGOING`(2차) — `aml_risk_models.scenario` 모델 레지스트리 exists-join(모델 코드 하드코딩 아님, 잘못된 값 400), 변경이력 9.31 의 "서버측 scenario 필터 후속 과제" 해소; ② `requiredAction`(권고 조치, 콤마 멀티 — `NONE`(조치 없음)·`CDD_UPDATE`(CDD 갱신)·`EDD`(강화된 고객확인)·`RELATIONSHIP_REVIEW`(관계 검토), `NONE` 토큰은 레거시 `required_action IS NULL` 행 포섭); ③ `registeredWithinDays`(양수 int — **인입(온보딩) 회원 필터**, `aml_customers.created_at ≥ now-일수` exists-join); ④ `latestPerTarget`(boolean 기본 false — **회원(targetRef)별 최신 1건 dedupe**, `evaluated_at` max 상관 서브쿼리[tenant·targetRef·modelVersion·scenario 한정] — **dedupe 먼저 선정 후 등급/조치/임박 등 상태 필터를 outer 적용**해 "현재 상태" 목록 의미론 보장, `count`/`items` 동일 술어). **⑤ `mandatoryHighRisk`(당연고위험, 2026-07-12 feature/aml-hrr-closed-loop-visualization — additive·optional 3-value): `true`=당연고위험만·`false`=일반만·미지정=무필터(modelVersion 회귀 교훈 동형). `aml_risk_scores.mandatory_high_risk` outer 필터(latestPerTarget 하 현재 상태 기준). bo-api 위임 경로는 이 서버 param 을 전달하면서 client post-filter(`matchesMandatoryHighRisk`)도 이중으로 걸어 구엔진(param 무시)도 안전하다(PEP 승인 fold 이후 최종 mandatory 플래그로 판정).** **⑥ `excludeOngoingTargets`(boolean, 기본 false, 2026-07-22 PLAN 20260722-ra-tm-2nd-stage-fixed-scenario-consistency A2 — additive): `true` 시 해당 targetRef 가 이력에 상시평가(ONGOING) 모델 점수를 1건이라도 보유하면 그 target 의 전 행을 목록에서 제외한다("2차 진입 대상" 전량 배제) — `scenario` 필터와 직교(행별 scenario 필터가 아니라 target 단위 술어). 1차(ONBOARDING) 탭이 `scenario=ONBOARDING&excludeOngoingTargets=true` 조합으로 상시평가 진입 대상을 제외하는 데 쓰인다(2차 탭은 미사용, 현행 `scenario=ONGOING` 유지). bo-api `GET /api/v1/bo/aml/risk-scores` 가 동일 파라미터를 pass-through 위임하며, 비운영 stub 경로는 stub 이 ONBOARDING 행만 생성하므로 no-op(필터 파싱만·행 제외 없음).** **⑦ `operativePerTarget`(boolean, 기본 false, 2026-07-22 feature/ra-high-risk-tab-operative-parity, F-018 후속 — additive): `true` 시 회원(targetRef)별 정확히 1행 = **operative 점수**(상시평가(ONGOING) 점수 보유 시 최신 ONGOING, 없으면 최신 전체=최신 온보딩(ONBOARDING) — §2.3 상세 operative 선정과 동일 규칙). operative 행 선정이 먼저이고, 등급·조치·임박·국가·당연고위험·`modelVersion`·`scenario` 등 상태 필터는 선정 후 **outer** 적용("현재 상태" 목록 의미론, `latestPerTarget` 동형), `count`/`items` 동일 술어, 동률(evaluatedAt 동일)은 `scoreId` 문자열 내림차순 결정적. `latestPerTarget` 와 동시 지정 시 **`operativePerTarget` 우선**(엔진 usecase 정규화, 결과 불변). bo-api `GET /api/v1/bo/aml/risk-scores` 가 동일 파라미터를 pass-through 위임하며, 비운영 stub 경로는 target 당 1행(ONBOARDING)만 생성하므로 no-op(필터 파싱만·행 제외/선정 없음). 고위험·EDD 탭이 이 모드로 RA 상세(§2.3/§3.3)와 등급/점수 파리티를 이룬다. **구현됨**(`RiskScoreAdminController`, bo-api `AmlRiskReadController`).** 응답은 **페이지 봉투 `RiskScoreListResponse{ items: RiskScoreResponse[], page, size, total }`**(§1.2 envelope 원칙 정합 — `total`은 페이지 무관 전체 건수로 타일↔목록 정합·페이지 이동에 사용) — `items` 원소가 `RiskScoreResponse`(§3.3, `mandatoryHighRisk`·`mandatoryHighRiskReasons`·`forcedFloorEvidence`·`operativeNextReviewDueAt` 포함). bo-api `GET /api/v1/bo/aml/risk-scores` 가 동일 파라미터(`mandatoryHighRisk` 포함)를 pass-through 위임하며, stub 경로도 동일 의미론(scenario=stub 행 시나리오 필터·requiredAction NULL 포섭·registeredWithinDays 는 seed 파생 결정적 가입일 post-filter·latestPerTarget 는 stub 이 target 당 1행이라 no-op·mandatoryHighRisk 는 `RiskScore.mandatoryHighRisk` post-filter) — 패리티 유지. **bo-api 응답도 엔진과 동일 페이지 봉투 `{ data: { items, page, size, total } }`(§1.2 envelope) 를 반환한다(`RaDtos.RiskScorePage`, `AmlRiskReadController#riskScores`, bo-web `useAmlRisk.ts` 소비 계약과 1:1)** — 위임(delegate) 경로의 `total`은 엔진 봉투 `total`을 그대로 passthrough(엔진 무응답 시 빈 봉투 `total=0`), **stub 경로의 `total`은 전수 스캔이 불가한 윈도우 스캔 구조라 `page*size + 이번 페이지 rows 건수`의 best-effort 하한(lower bound)** 으로 산출한다(정확한 전체 건수 아님 — 문서 미정의 지점이었던 stub total 산식을 코드=truth 로 명문화). **구현됨**(`RiskScoreAdminController`, bo-api `AmlRiskReadController`) | `aml_risk_scores`,`aml_risk_models`,`aml_customers` |
| GET | `/api/v1/admin/aml/risk-scores/held-onboarding?targetRef=&receivedWithinDays=&page=&size=` | `aml:case:read` | — | **점수 없는 1차 RA 평가 보류 업무목록**. `aml_cdd_onboarding_decisions`와 `aml_ra_evaluation_jobs`를 동일 `(tenant_id,event_id)`로 read-only join하고 `decision=EDD_REQUIRED`·`reason=ONBOARDING_RA_HELD`·`score_id IS NULL`·job `PENDING\|PROCESSING`인 현재 행만 반환한다. `targetRef`는 대소문자 무시 부분검색, `receivedWithinDays`는 optional 1~365, page/size 기본 0/50(size 최대 200), 정렬 `receivedAt DESC,eventId DESC`. 응답은 §3.3e `HeldOnboardingDecisionPage`; score 필드는 계약에 없다. BFF `GET /api/v1/bo/aml/risk-scores/held-onboarding`가 exact typed 위임하며 profile 무관 engine-unavailable 503 fail-closed(stub 없음). retry 성공으로 job이 `COMPLETED`되면 이 목록에서 빠지고 실제 score는 기존 ONBOARDING 목록에만 나타난다. V42 immutable decision/replay snapshot은 갱신하지 않는다. | `aml_cdd_onboarding_decisions`,`aml_ra_evaluation_jobs` |
| GET | `/api/v1/admin/aml/risk-scores/distribution?modelVersion=` | `aml:case:read` | — | **RA 등급 분포**. 응답 `RiskDistributionResponse`(§3.3b). **구현됨**(`RiskScoreAdminController`) | `aml_risk_scores` |
| GET | `/api/v1/admin/aml/customers/pipeline-stats?histogramDays=` | `aml:case:read` | — | **CDD/RA 파이프라인 집계**(KYC 상태 분포·신규 등록 윈도우·RA 처리 현황·기간 히스토그램). `Tenant-Id` 헤더 필수·`Workspace-Id` 옵션. `histogramDays` 1~90·기본 14(범위 밖 클램프). 응답 `CddRaPipeline`(§3.3c). 집계 카운트만(raw PII 미노출). **구현됨**(엔진) | `aml_customers`,`aml_risk_scores` |
| POST | `/api/v1/admin/aml/risk-scores/{scoreId}/override` | `aml:case:update` | 🔒4-eyes(하향) | 등급 수동 조정. 요청 `RiskOverrideRequest`(§3.3) | `aml_risk_scores`,`aml_approvals` |

> **셋업 경로(시뮬레이터, REST-only — 2026-08-13).** 개발·데모 스택에서 `KR_ONGOING_RA` 의 `parameters.signalScaling` 을 켜는 것은 Flyway/DB 시드가 아니라 셋업 스테이지 `demo_ingest.ensure_ra_signal_scaling` 이며, **위 운영 엔드포인트만** 쓴다: `versions:copy`(ACTIVE → DRAFT) → `POST .../ra-models`(그 키 하나만 병합한 초안 저장) → `:simulate`(`samplePopulation=ALL_ACTIVE`) → `versions/{v}:activate`(202 approvalId, maker) → 공통 결재함 `approvals/{id}:approve`(**checker ≠ maker**). **멱등** — ACTIVE 정의의 블록이 이미 목표와 같으면(숫자 float 정규화 비교) 신규 상신·신규 승인 0 으로 스킵한다. **CDD 인입 이후에 실행한다** — `ALL_ACTIVE` 시뮬레이션이 활성 주체 전량을 재평가하므로 주체가 먼저 존재해야 표본이 비지 않는다(실측: 311주체 38.2초 → 이 호출만 타임아웃 180초). `ensure_watchlists`·`ensure_high_risk_registry`·`setup_fds_rulepack` 과 동형이며 새 엔드포인트·새 승인 유형을 만들지 않는다.
>
> **BFF 위임.** `GET /api/v1/bo/aml/ra-models/onboarding-input-catalog?windowDays=`가 위 엔진 응답을 1:1 위임한다. 동일 `aml:admin:policy` 권한이며 엔진 delegate가 없거나 빈 응답이면 관측값 stub을 합성하지 않고 `503 AML.ENGINE_UNAVAILABLE`로 fail-closed한다.

#### TM scenario (§12)
| 메서드 | 경로 | scope | 4-eyes | 설명 | DB |
|---|---|---|---|---|---|
| GET | `/api/v1/admin/aml/tm-scenarios?scenarioCode=`(**V61 — optional, additive·하위호환**) | `aml:admin:policy` | — | `scenarioCode` 지정 시 해당 코드의 버전 목록, **미지정 시 테넌트 전체 정의 list-all**(bo-api 목록 위임원, §2.5a). 레거시 정의 10종 제거 후 신선 배포의 정상 응답은 빈 배열 | (정책 store) |
| POST | `/api/v1/admin/aml/tm-scenarios/{scenarioCode}/simulate` | `aml:admin:policy` | — | scenario simulation(응답 DTO §3.15 `SimulationResponse`) | — |
| POST | `/api/v1/admin/aml/tm-scenarios/{scenarioCode}:activate` | `aml:admin:policy` | 🔒4-eyes | scenario 변경 적용. `scenarioCode` 는 자유형(형식 `^[A-Z][A-Z0-9_]{2,64}$`, 예약 코드 `CUSTOM_RULE` draft 단계 거부). **bo-api BFF 위임 시 3-call 시퀀스(2026-08-02, 코드=truth)**: `GET .../tm-scenarios?scenarioCode=`(기존 버전 read-back) → `POST .../tm-scenarios`(draft — 기존 정의 존재 시 그 활성 dsl 원문을 `compile(existingDsl, fields)` 로 보존, 존재하지 않으면 generic fallback 합성) → 본 `:activate`(4-eyes 상신). §3.4c `thresholdsByGrade` 컴파일 규칙 참조 | `aml_approvals` |

#### 사용자 정의 STR/CTR TM 룰 (v9.44)

| 메서드 | 경로 | scope | 4-eyes | 설명 |
|---|---|---|---|---|
| GET | `/api/v1/admin/aml/configurable-report-rules?family=STR\|CTR` | `aml:case:read` | — | 사용자 정의 룰 버전 목록(통계/BFF read) |
| POST | `/api/v1/admin/aml/configurable-report-rules` | `aml:admin:policy` | — | 안전 DSL 사용자 정의 룰 DRAFT 생성(201) |
| POST | `/api/v1/admin/aml/configurable-report-rules/{ruleCode}/simulate` | `aml:admin:policy` | — | 입력 sampleFeatures 결정적 시뮬레이션 |
| POST | `/api/v1/admin/aml/configurable-report-rules/{ruleCode}:activate` | `aml:admin:policy` | 🔒 `TM_SCENARIO` | DRAFT 버전 활성화 상신(202), subjectRef=`CUSTOM_RULE\|code\|version` |
| POST | `/api/v1/admin/aml/configurable-report-rules/{ruleCode}:retire` | `aml:admin:policy` | 🔒 `TM_SCENARIO` | ACTIVE 버전 **회수** 상신(202), subjectRef=`CUSTOM_RULE_RETIRE\|code\|version`. body `{version, makerId, reason?}` |
| POST | `/api/v1/admin/aml/configurable-report-rules/{ruleCode}:discard` | `aml:admin:policy` | **— (4-eyes 없음)** | **미활성 `DRAFT` 버전 폐기**(200). body `{version, actorId}`, 응답 `DiscardResponse{ruleCode, version, status, alreadyAbsent}`. `DRAFT` 한정 — `ACTIVE`/`SUPERSEDED`·활성화 상신 대기·알럿 결속은 409 |

> **설정형 룰 회수(retire, 2026-08-06 신설)**: `:retire`는 `:activate`와 **동형의 4-eyes**다 — 승인 유형은 신규 값을 만들지 않고 `TM_SCENARIO`를 재사용하되 subjectRef 접두사(`CUSTOM_RULE_RETIRE|` vs `CUSTOM_RULE|`)로 라우팅을 가른다(구분자 위치가 달라 상호 접두사 매칭 불가). 따라서 payload drift guard(`canonicalSubjectRefOnly`)·결재함·checker 경로가 그대로 동작하고 bo-api/bo-web의 subjectType enum 동기화가 불필요하다. `CUSTOM_RULE_RETIRE`는 자유 서식 TM 시나리오 코드 예약어에 추가돼 draft 단계에서 거부된다(오라우팅 차단).
>
> 승인이 EXECUTED되면 (1) 룰이 `ACTIVE→SUPERSEDED`(기존 도메인 전이 재사용 — 신규 전이 없음)가 되어 이후 동일 인입에 발동하지 않고, (2) **그 룰이 만든 TM 알림이 회수**된다(`aml_alerts.status=RETIRED` + `retired_at`/`retired_by`/`retire_reason`, DB V63). **케이스가 개설된 알림(`CASE_OPENED`/`ESCALATED`/`STR_RECOMMENDED`)은 회수하지 않는다** — 케이스·STR draft 계보가 끊기면 규제 산출물이 사라지기 때문이며, 건너뛴 건수는 응답과 `CUSTOM_RULE_RETIRED` 감사 이벤트(`TM_SCENARIO_CHANGE`)에 보고된다.
>
> 응답 `RetirementResponse`: `{ approvalId(회수 완료 상태면 null), status("SUBMITTED"|"ALREADY_RETIRED"), alreadyRetired(boolean), retirableAlertCount(int), caseLinkedAlertCount(int) }` — 뒤 두 필드는 상신 시점 미리보기이고 실제 회수 건수는 승인 실행 감사 이벤트(`retiredAlertCount`·`caseLinkedAlertSkipped`·`alreadyRetiredCount`)가 정본이다. **멱등**: 이미 `SUPERSEDED`면 200 + `alreadyRetired=true`로 신규 상신 0, 같은 버전에 대기 중 상신이 있으면 그 `approvalId`를 재사용. **`DRAFT` 룰 회수는 409 `AML.STATE_CONFLICT`**, 미상 버전은 400. 회수된 룰 코드는 **같은 버전으로 재 draft 불가**(PK `(tenant_id, rule_code, version)`)이고 **새 버전으로는 draft→활성화가 가능**하다(ACTIVE UNIQUE는 `status='ACTIVE'` 부분 인덱스).

> **설정형 룰 미활성 DRAFT 폐기(discard, 2026-08-10 신설 — 코드=truth, aegis-aml main `76681955`)**: 저작된 DRAFT 를 되돌릴 수단이 없어 잔여 버전이 남고, 같은 버전 재저작이 PK 충돌로 막히던 막다른 길을 닫는 경로다. `:retire`(효력을 가졌던 ACTIVE 버전의 회수)와 **대상·통제가 다르다**.
>
> - **요청/응답**: 엔진 `POST /api/v1/admin/aml/configurable-report-rules/{ruleCode}:discard`, 헤더 `Tenant-Id` 필수, body `DiscardRequest{version, actorId}`. 응답 **200** `DiscardResponse{ruleCode, version, status("DISCARDED"|"ALREADY_ABSENT"), alreadyAbsent(boolean)}`. `actorId`는 신뢰 actor 경계(`TrustedActorResolver`)를 통과한 값만 감사에 쓰인다(브라우저 입력 그대로 신뢰하지 않음).
> - **권한 — 4-eyes 없음(설계 근거)**: 요구 scope 는 **DRAFT 저작(`POST /configurable-report-rules`)과 동일한 `aml:admin:policy`** 이고 승인 결재를 요구하지 않는다. 근거는 대칭성이다 — DRAFT 저작 자체가 단독 권한이며 그 버전은 **한 번도 효력을 가진 적이 없다**(TM 평가 미참여·발동 0·알럿 0). 효력 자산을 다루는 `:activate`·`:retire` 의 🔒`TM_SCENARIO` 4-eyes 는 **무변경**이다.
> - **대상 — `DRAFT` 한정**: `ACTIVE`·`SUPERSEDED` 버전은 정책 계보이므로 **409 `AML.STATE_CONFLICT`** 로 거부한다(무력화는 `:retire` 가 담당하는 별도 경로). 해당 버전에 결속된 TM 알럿(`evidence.trigger.ruleVersion` 기준)이 하나라도 있으면 역시 409 — DRAFT 는 평가에 참여하지 않으므로 정상 상태에서 이 값은 항상 0 이고, 0 이 아니면 그 자체가 이상 신호다.
> - **4-eyes 우회 차단**: 같은 버전에 **활성화 상신(`TM_SCENARIO`, subjectRef `CUSTOM_RULE|code|version`)이 PENDING 이면 폐기를 409 로 거부**한다. 폐기 후 같은 버전을 재저작하면 대기 중이던 결재가 **maker 가 상신하지 않은 새 DRAFT** 를 발효시킬 수 있기 때문이다(subjectRef 동일). 대기 결재를 먼저 정리해야 폐기가 성립한다.
> - **멱등**: 이미 없는 버전에 대한 재폐기는 **200 + `status="ALREADY_ABSENT"`·`alreadyAbsent=true`** 이며 **신규 부작용 0**(감사 이벤트도 남기지 않는다) — 재시도가 안전하다.
> - **감사**: 실제 폐기 시 `TM_SCENARIO_CHANGE` 카테고리에 `action="CUSTOM_RULE_DRAFT_DISCARDED"`·`ruleCode`·`version`·`family` 를 기록한다(subjectRef 는 활성화 계열과 같은 `CUSTOM_RULE|code|version`).
> - **행 처리**: 폐기는 `aml_configurable_report_rules` 의 해당 DRAFT **행 물리 삭제**다. F-034 회수의 "행은 삭제하지 않는다"는 **`ACTIVE→SUPERSEDED` 회수 경로와 그 알럿에 한정된 정책 계보 보존 계약**이므로 이 경로와 충돌하지 않는다(효력을 가진 적 없는 버전에는 보존할 계보가 없다). 폐기 후 같은 버전 재저작이 가능해진다.
> - **bo-api 표면**: `POST /api/v1/bo/aml/report-rules/configurable/{ruleCode}:discard`, 권한 `aml:admin:policy`(또는 `BO_SUPER_ADMIN`), body `{version, actorId}`, 응답 200 `{ruleCode, version, status, alreadyAbsent}`. `actorId`는 인증 principal 로 덮어쓰며(`BackofficeActorResolver`), **판정(DRAFT 여부·결재 대기·알럿 결속)은 전부 엔진 계약**이다 — bo-api 는 자체 판정 없이 위임하고 엔진 미가용 시 **503 `AML.ENGINE_UNAVAILABLE` fail-closed**(성공으로 둔갑시키지 않음), 엔진 409/400 은 기존 매핑 그대로 전파한다.
> - **화면 계약(bo-web)**: 룰 빌더는 제안 버전이 이미 점유돼 있으면 점유자 상태로 갈라 처리한다 — **미활성 `DRAFT` 점유는 그 사실을 명시하고 명시적 폐기 액션으로만 정리**하며(**자동·무단 폐기 0** — 남의 저작물일 수 있어 확인이 선행된다), `ACTIVE`/`SUPERSEDED` 점유는 폐기를 제안하지 않고 **위쪽 첫 빈 버전을 제안**한다(점유 중인 DRAFT 도 건너뛴다). 버전 표기가 `v<숫자>` 규칙 밖이면 추측하지 않고 사용자 입력을 받는다. 비-admin 세션에는 폐기 액션을 노출하지 않는다.

`ConfigurableReportRuleView`: `{ ruleCode, version, family(STR|CTR), displayName, description, reasonCode(STR 필수/CTR null), severity, status(DRAFT|ACTIVE|SUPERSEDED), parameters, dsl, effectiveFrom, createdBy }`. `ruleCode`는 `[A-Z][A-Z0-9_]{2,79}`이며 잠금 기준선과 충돌하는 `STR_`/`CTR_` 접두는 금지한다. DSL은 `cmp`/`and`/`or`/`not`와 `velocity(count|sum, dimension=subject, window=1h..30d)`의 닫힌 문법이며 allowlist 밖 피처·`always`·빈 AND/OR 그룹은 400이다.

bo-api 표면: `GET|POST /api/v1/bo/aml/report-rules/configurable`, `POST .../configurable/{ruleCode}/simulate`, `POST .../configurable/{ruleCode}:activate`, **`POST .../configurable/{ruleCode}:discard`**(미활성 DRAFT 폐기, 위 note). GET은 `aml:case:read`, 변경은 `aml:admin:policy`로 분리한다. DRAFT 생성·활성화 상신의 `makerId`는 브라우저 입력을 신뢰하지 않고 인증된 `BackofficePrincipal.email`로 덮어쓴다. bo-web은 엔진을 직접 호출하지 않는다.

> bo-api의 `GET /api/v1/bo/aml/tm-scenarios/{scenarioCode}`는 운영자 화면용 BFF read model이다. 엔진 저장 권위는 위 Admin API의 정책 store이며, 변경 적용은 기존 `:activate` 4-eyes(`TM_SCENARIO`) 흐름만 사용한다.

#### Case / CDD·EDD (§13)
| 메서드 | 경로 | scope | 4-eyes | 설명 | DB |
|---|---|---|---|---|---|
| GET | `/api/v1/admin/aml/cdd/cases` | `aml:case:read` | — | case 목록(필터: caseType/status/assignedTo + **`priority`/`targetRef`(정확일치)/`dueSoon`(boolean, true 이면 `dueAt<=now+72h AND status NOT IN terminal`), PLAN 20260902-aml-case-workbench U5**) | `aml_cases` |
| GET | `/api/v1/admin/aml/cdd/cases/{caseId}` | `aml:case:read` | — | case 상세·timeline | `aml_cases` |
| GET | `/api/v1/admin/aml/cdd/cases/{caseId}/workbench` | `aml:case:read` | — | **조사관 작업대 단일 응답(PLAN 20260902-aml-case-workbench U4·U5)** — `CaseDetail` 필드(§3.5) 평탄화 + `createdBy`/`closeReason`/`updatedAt` + `lineage`(발단 alert/screening/score 요약, backfill 이면 `inferred=true`) + `relatedAlerts`(대상의 관련 알럿, 회수(RETIRED) 제외·최대 50건·최신순) + `riskSummary`(회원 위험 요약, `AssessRiskUseCase.findOperativeForTarget` 정본) + `linkedReports`(연결 STR/CTR) + `pendingApproval`(대기 4-eyes, `EDD_CLOSE`→`RELATIONSHIP_REJECT` 순) + `relationships`(관계 에지 both direction) + `memberCases`(이 회원의 전체/열린 케이스 건수) + `checklistProgress`. 하위 조회 실패는 fail-soft(null/빈 리스트, 예외로 전체 500화 금지). 없는 케이스는 404 | `aml_cases`,`aml_alerts`,`aml_risk_scores`,`aml_screening_results`,`aml_regulatory_reports`,`aml_approvals`,`aml_relationships`,`aml_case_checklist_items` |
| GET | `/api/v1/admin/aml/cdd/cases/{caseId}/checklist` | `aml:case:read` | — | 케이스 체크리스트(활성 템플릿과 병합 — 미저장 항목은 `status=PENDING`) + 진행률(`checklistProgress`) | `aml_case_checklist_items`,`aml_cdd_checklists` |
| PUT | `/api/v1/admin/aml/cdd/cases/{caseId}/checklist/{itemKey}` | `aml:case:update` | — | 체크리스트 항목 상태/메모/증빙 갱신. body `{status(PENDING\|DONE\|NOT_APPLICABLE), note?(≤2000), evidenceRef?(≤512), actor?}`. 케이스 미존재 **404**, 케이스가 `OPEN`/`INVESTIGATING` 이 아니면(PENDING_APPROVAL·terminal) **409 `AML.STATE_CONFLICT`**, 템플릿에 없는 `itemKey`·길이 초과·`status` null/blank/미지값은 **400**. 합성 타임라인 note(`<itemKey>:<status> — <note>`)는 2000자 절단. 갱신마다 감사 이벤트(`CASE_APPROVAL`, action `CHECKLIST_ITEM`) 기록. 저장마다 `CHECKLIST_ITEM` 타임라인 append | `aml_case_checklist_items`,`aml_cases` |
| GET | `/api/v1/admin/aml/cdd/customers/{customerRef}/relationships` | `aml:case:read` | — | 관계 그래프 에지 목록(both direction — `fromRef`/`toRef` 양쪽 조회, `RelationshipEdgeDto`, 유효기간은 도메인 미매핑으로 응답에 없음) | `aml_relationships` |
| POST | `/api/v1/admin/aml/cdd/cases` | `aml:case:update` | — | case 생성. `originAlertId`가 없으면 수동 생성, 있으면 alert row를 먼저 잠그고 tenant/target/CTR·STR type/status를 검증한 정상 handoff로만 생성·상태 전이한다. 임의 case의 alert lineage 선점은 거부. body `actor?`(additive — `TrustedActorResolver` 로 신뢰 경계 통과, 신규 케이스는 `CREATED` 타임라인 1행 자동 append) | `aml_alerts`,`aml_cases` |
| PATCH | `/api/v1/admin/aml/cdd/cases/{caseId}` | `aml:case:update` | — | 담당자·우선순위·dueAt 및 working status `OPEN↔INVESTIGATING` 변경. `PENDING_APPROVAL` 진입/이탈과 terminal 전이는 직접 PATCH 불가. body `actor?`(additive). **실제로 변경된 항목마다** `ASSIGNED`/`PRIORITY_CHANGED`/`DUE_CHANGED`/`STATUS_CHANGE` 타임라인 1행씩 append(동일값 재전송은 0행)(담당자 `null`/빈값 해제 계약 없음 — 미전송=무변경) | `aml_cases` |
| POST | `/api/v1/admin/aml/cdd/cases/{caseId}/timeline` | `aml:case:update` | — | 메모·증빙 추가 | `aml_cases` |
| POST | `/api/v1/admin/aml/cdd/cases/{caseId}:close` | `aml:case:update` | 🔒4-eyes(`EDD_CLOSE`) | **조사 케이스 결재 종결**(`DISMISSED`/`REPORTED`/`CLOSED` 종결). subjectType=`EDD_CLOSE` 4-eyes(상신 maker→승인 checker, maker≠checker) 승인 시 종결. **케이스 유형 무관 — EDD_REVIEW(강화된 고객확인) 뿐 아니라 알림 트리아지·처분 폐루프에서 전환된 조사 케이스(STR_REVIEW·SAR_REVIEW·CDD)도 동일 결재 종결 경로를 공유**한다(엔진 `Case.closeApproved` 는 케이스 유형 가드 없이 존재·비종결 상태 불변식만 강제 — 과거 `EDD_REVIEW` 전용 가드가 STR_REVIEW `:close` 를 400 "case is not an EDD_REVIEW case" 로 거부하던 결함 해소). 회원원장 EDD 종료 이력(`recordEddClosed`, DB §3.22f)은 `EDD_REVIEW` 케이스에만 기록(알림 파생 조사 케이스는 EDD 이력 대상 아님) | `aml_cases`,`aml_approvals` |
| POST | `/api/v1/admin/aml/cdd/cases/{caseId}:reject-relationship` | `aml:case:update` | 🔒4-eyes | 관계거절/온보딩 보류 확정 | `aml_cases`,`aml_approvals` |

> **bo-api 위임(PLAN 20260902-aml-case-workbench U7)**: `GET /api/v1/bo/aml/cdd/cases/{caseId}/workbench` · `GET/PUT /api/v1/bo/aml/cdd/cases/{caseId}/checklist(/{itemKey})` · `GET /api/v1/bo/aml/cdd/customers/{customerRef}/relationships` 가 위 4종을 그대로 위임한다(경로 접두만 `/api/v1/bo/aml/cdd/...`, scope·4-eyes·응답 동형). bo-api `CaseWorkbench` DTO는 엔진 응답과 **필드명·중첩 구조 1:1**이며 `sourceOrigin`(bo-api 파생, FDS/AML 발신 구분)만 추가 필드로 허용한다. 체크리스트 `PUT` 의 bo-api 요청 본문(`CaseChecklistUpdateRequest{status, note, evidenceRef}`)은 `actor` 를 받지 않으며(위조 여지 0), 엔진 위임 시 인증 principal 을 `actor` 로 주입한다. 엔진 미연결(스텁) 환경은 워크벤치=상세+빈 하위 컬렉션, 체크리스트=템플릿 3항목 PENDING, 관계=빈 리스트로 폴백한다. 워크벤치 `timeline[]` 원소는 엔진 `{entryId, kind, note, evidenceRefs[], actor, createdAt}` 1:1 에 bo-web 하위호환 alias `occurredAt`(=`createdAt`) 을 더한 `WorkbenchTimelineEntry` 다(구 `CaseDetail.timeline` 의 `{kind,…,occurredAt}` 계약은 불변). bo-api 경로 세그먼트(`caseId` UUID 검증·`itemKey`/`customerRef` 인코딩)는 위임 전 정규화된다.

> **케이스 종결·알림 handoff 불변식(V43).** `:close`의 maker는 `X-User-Subject`가 정본이며 body maker는 동일성 assertion일 뿐이다. 상신 성공 즉시 case는 `PENDING_APPROVAL`, checker 승인 시 terminal status로 전이하고 reject 시 직전 조사상태로 복원한다. `REPORTED` 종결은 case type에 맞춰 `STR_REVIEW→STR`, `CTR_REVIEW→CTR`의 연결 보고가 `SUBMITTED` 또는 `ACKNOWLEDGED`일 때만 가능하다. submit과 checker 실행 모두 **case FOR UPDATE→report FOR UPDATE** 순으로 같은 lineage/target/status를 재검증하므로 FIU FAIL callback과 원자적으로 직렬화된다. 다른 case type의 REPORTED는 거부한다. 알림 전환 case는 서버가 알림 종류로 `STR_REVIEW`/`CTR_REVIEW`를 정하고 `(tenant_id,origin_alert_id)`당 하나만 생성한다. handoff 재호출은 alert의 terminal action·recommended type과 기존 case의 tenant/origin/target/type이 모두 같은 경우에만 멱등 replay로 반환하며, 다른 action이나 lineage 불일치는 충돌로 거부한다. 과거 `TRIAGED` alert에 유효한 기존 case만 남은 부분 handoff는 같은 transaction에서 요청 action으로 alert 상태를 동기화하되 case 재생성·재과금은 하지 않는다.

> **케이스 담당자 디렉토리(feature/aml-case-assignee-picker).** bo-api `AmlCaseAssigneeController GET /api/v1/bo/aml/cdd/case-assignees?keyword=`(scope `aml:case:read` 또는 `BO_SUPER_ADMIN`) — `backoffice.bo_admin_users` 읽기 전용 **최소 투영** `[{ email, name, department }]`(이름·이메일 오름차순; 역할코드·상태·로그인 이력 미포함). 포함 조건: 상태 활성(`ACTIVE`) ∧ 유효 역할 scope 에 `aml:case:update`(또는 `*`) — 유효 역할은 로그인과 동일 정본(`BackofficeRole.effectiveRoleCodes`: 부여 역할이 없으면 비-wildcard `adminType` 폴백) ∧ (플랫폼 컨텍스트 ∣ 플랫폼 운영자(`BackofficeRole.isPlatformOperator` 단일 정본) ∣ **현재 테넌트·워크스페이스 바인딩**(`bo_user_tenants`, `TenantContextFilter` 와 동일 규칙)). 테넌트 컨텍스트 부재 시 403 `BO-TENANT-REQUIRED`(fail-closed), keyword 는 100자 절단, 결과 상한 없음(후속). 엔진 미경유·감사 로그 없음(읽기). 케이스 `assignedTo` 는 계속 로그인 이메일 문자열이며 서버 화이트리스트 검증은 두지 않는다(UI 선택지 제한).

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
| GET | `/api/v1/admin/aml/reports/stats/str-delay?period=7d\|30d\|90d` | `aml:case:read` + **`COMPLIANCE` role 필수** | — | STR 보고 지연일수 분포 집계 원천(PRD §12-B.3 ①). legacy 운영 지표로 보고별 candidate(`created_at`) + **72 elapsed hours**→제출(`submitted_at`) 경과를 상대 버킷 `{ON_TIME,D+1~3,D+4~7,D+8~14,D+15+}`으로 분류한다. 관할별 법정 `reportDeadlineAt`(nullable freeze)과 별개이며 이 지표로 법정 기한을 재구성하지 않는다. **tipping-off 통제(§19.2a)**: COMPLIANCE 전담 role 필수(없으면 `403 AML.FORBIDDEN_SCOPE`), 열람은 `RAW_DATA_ACCESS` 감사. 응답은 집계 카운트만(보고 행·PII 미노출). 0건 → 빈 분포(honest, seed 없음). 응답 DTO §3.6 `DelayBucket[]` (T4 AML-ENG-04 — **확정**) | `aml_regulatory_reports` |
| GET | `/api/v1/admin/aml/reports/stats/unreported-reasons?period=7d\|30d\|90d` | `aml:case:read` + **`COMPLIANCE` role 필수** | — | STR 미보고(종결 비제출=`REJECTED`/`CANCELLED`) 사유 분포 집계 원천(PRD §12-B.3 ①). 종결 시 영속된 `closure_reason_code` 빈도(미영속 legacy = `UNSPECIFIED` 버킷, 소급 seed 없음). **tipping-off 통제(§19.2a)**: COMPLIANCE 전담 role 필수, `RAW_DATA_ACCESS` 감사. 응답 DTO §3.6 `UnreportedReason[]` (T4 AML-ENG-04 — **확정**) | `aml_regulatory_reports` |

#### AMLC 계정 관리 (테넌트별 포털 로그인 계정, feature/aml-reports-amlc-migration §1.4-A)
| 메서드 | 경로 | scope | 4-eyes | 설명 | DB |
|---|---|---|---|---|---|
| GET | `/api/v1/admin/aml/amlc-credential` | `aml:case:read` | — | 테넌트 AMLC 포털 계정 마스킹 조회. 응답 `MaskedView{ configured, username, enabled, updatedAt, updatedBy }` — 시크릿(비밀번호)은 어떤 형태로도 포함하지 않는다. 미설정 시 `configured=false`·나머지 `null`/`false` | `aml_amlc_credentials` |
| PUT | `/api/v1/admin/aml/amlc-credential` | `aml:case:update` | — (즉시 반영, **4-eyes 미적용** — §1.4-C 결정, RI 헤더 편집과 동급) | 테넌트 AMLC 포털 계정 upsert. body `SaveRequest{ username, password }` — `password`는 `SecretCipherPort`(AES-256-GCM)로 즉시 암호화 후 저장, 평문은 로그/응답/감사 어디에도 남기지 않는다. 저장 시 `AMLC_CREDENTIAL_SAVED` 감사 이벤트 기록. 응답은 GET과 동일한 `MaskedView` | `aml_amlc_credentials`,`aml_audit_events(POLICY_CHANGE)` |

> **bo-api 위임 프록시**: `GET/PUT /api/v1/bo/aml/amlc-credential`(scope `aml:case:read`/`aml:case:update` 또는 `BO_SUPER_ADMIN`)이 위 엔진 API를 그대로 위임한다(`AmlcCredentialController`→`AmlcCredentialService`, 로컬 stub 없음 — delegate 불가 시 fail closed). bo-web `/aml/reports/amlc-account` 화면(설정됨 배지·username 표시·비밀번호 입력전용)의 데이터 원천.

> **STR actor 신뢰경계(P0-00 코드 truth).** bo-api가 사용자 principal에서 파생한 `X-User-Subject`는 machine-auth v2 `scopeContext.user-subject`에 포함된다. STR 목록/상세/통계의 `RAW_DATA_ACCESS` 감사 actor와 draft/submit/reject/cancel maker는 이 signed header를 사용하고, body의 `makerId`가 있으면 동일성 assertion만 수행한다. bo-api machine credential 자체도 `COMPLIANCE` authority token을 가져야 하며, BO edge의 사용자 `AML_COMPLIANCE` 검사와 엔진 `RoleGuard`/`ScopeGuard`를 모두 통과해야 한다.

#### §2.7a 아웃바운드 Webhook 자격증명 관리 (테넌트 콜백 목적지 + 서명 시크릿, 2026-08-10 신설 — 코드=truth, aegis-aml main `a0d1e5d9`)
> **무엇을 닫는 경로인가**: §8 아웃바운드 콜백의 목적지(`aml_api_credentials.webhook_url`)와 서명 시크릿(`secret_ciphertext`)을 **런타임에 등재·교체하는 유일한 REST 경로**다. 종전에는 등록 수단이 **DB 직접 INSERT 뿐**이라 "데모 시드 금지(REST-only)" 원칙과 충돌해 아무도 등록하지 못했고, 그 결과 `credential_type='WEBHOOK'` 행이 0개여서 HRR 승인 콜백 서명 검증(엔진 케이스 RA-C12)이 **실행 불가**였다. 선례는 §2.7 AMLC 계정 관리(`AmlcCredentialAdminController`) — 마스킹 GET / upsert PUT / 즉시 반영·4-eyes 없음(결정 C)과 **동형**이다. ~~**bo-api·bo-web 표면은 없다**(운영자 화면 미도입 — 엔진 admin REST 전용).~~ **(2026-08-10 정정, aegis-aml main `48e8e697`)** 신설 당시의 이 서술은 **더 이상 사실이 아니다** — 아래 **bo-api 위임 표면**(`GET|PUT /api/v1/bo/aml/webhook-credential`)과 bo-web 운영자 화면 `/aml/webhook-credential`(**AML-WHK-001**, 기능정의서 §12.3)이 신설됐다. **엔진 계약(경로·scope·검증·감사·마스킹·SSRF 처리) 자체는 무변경**이며, 아래 엔진 표·註는 그대로 유효하다.

| 메서드 | 경로 | scope | 4-eyes | 설명 | DB |
|---|---|---|---|---|---|
| GET | `/api/v1/admin/aml/webhook-credential` | `aml:case:read` | — | 테넌트 아웃바운드 webhook 자격증명 마스킹 조회. 헤더 `Tenant-Id` 필수. 응답 `MaskedView{ configured, credentialId, webhookUrl, secretConfigured, enabled, updatedAt, updatedBy }` **7필드** — **시크릿 필드 자체가 없다**(평문·암호문·마스킹 힌트 어느 것도 아닌, 존재 여부 불리언 `secretConfigured` 까지만). 미등재 시 `configured=false`·`secretConfigured=false`·`enabled=false`·나머지 `null` | `aml_api_credentials` |
| PUT | `/api/v1/admin/aml/webhook-credential` | **`aml:admin:policy`** | — (즉시 반영, **4-eyes 없음** — §2.7 AMLC 결정 C 동형) | 테넌트 webhook 자격증명 upsert. body `SaveRequest{ webhookUrl, secret, enabled }` — `secret`은 `SecretCipherPort`(AES-GCM)로 **암호문 저장**(평문 컬럼 없음·응답/로그 미반영), `enabled` 생략(`null`)은 활성화. 응답 200 = GET 과 동일한 `MaskedView` | `aml_api_credentials`,`aml_audit_events(POLICY_CHANGE)` |

> - **쓰기 scope 상향 근거**: 선례 AMLC 는 `aml:case:update` 지만 이 값은 **AML 알림이 어디로 나가는지**를 바꾸는 **아웃바운드 유출 경로**다. 케이스 담당자가 테넌트의 알림 스트림을 재지향할 수 있어서는 안 되므로 쓰기를 **정책 관리 scope `aml:admin:policy` 로 상향**하고, 마스킹 읽기는 `aml:case:read` 에 둔다. 쓰기 scope 미보유 호출은 **403**(읽기는 `aml:case:read` 로 정상 200).
> - **actor 경계**: 쓰기 actor 는 `TrustedActorResolver`(검증된 `X-User-Subject`)에서만 취하며 body 는 actor 를 싣지 않는다. 검증 actor 가 없으면 **400 `AML.VALIDATION_ERROR`** `details="verified X-User-Subject is required"`.
> - **검증**: `secret` 이 빈 문자열·공백·키 누락이면 **400 `AML.VALIDATION_ERROR`** `details="webhook secret must not be blank"`(제출값을 응답·로그에 되비추지 않는다). 시크릿 없는 자격증명은 릴레이가 매 전송마다 `webhook endpoint secret is unset` 으로 실패하는 상태라 **REST 표면이 그 상태 생성 자체를 거부**한다. 거부 시 **기존 등재분은 훼손되지 않는다**(거부 후 GET 이 종전 값 유지).
> - **멱등·upsert 대상 행**: 같은 값 재PUT 은 **자격증명 행·암호문·`updatedAt`·`updatedBy`를 갱신하지 않는다**(AES-GCM 은 IV 가 매번 달라 암호문 비교가 성립하지 않으므로 저장 암호문을 복호해 비교). 단, 성공한 관리 쓰기 호출의 추적성은 아래 감사 규칙대로 **매 PUT 1건**을 append한다. 업서트 대상은 릴레이가 고르는 바로 그 행이다 — 정렬은 `enabled` 우선 → `webhook_url` 존재 우선 → `credential_id` 이며, 기존 행은 `credentialId`·`createdAt` 을 보존한 채 제자리 갱신한다(테넌트당 `WEBHOOK` 행이 중복 누적돼 릴레이의 목적지 해석이 비결정적으로 갈리는 것을 막는다). 신규 생성 시 `credential_id` 는 `webhook-primary`.
> - **인바운드 권한 0**: 저장 시 `scopes` 를 **빈 배열 `[]`** 로 고정한다 — 아웃바운드 서명 자격증명이 인바운드 API 호출 권한을 갖는 일이 없다(`allowed_protocol_versions` 는 기본 `["v2"]`).
> - **감사**: **성공한 PUT 마다(같은 값 재PUT 포함)** `event_category=POLICY_CHANGE` · `subject_ref=<credentialId>`(신규 등재 시 `webhook-primary`) · `detail.action="WEBHOOK_CREDENTIAL_SAVED"` · `detail.operation="CREATE"|"REPLACE"` · `webhookUrlConfigured` · `webhookHost` · `enabled` · `updatedBy` · `savedAt` 을 **정확히 1건** 기록한다. 같은 값 재PUT 은 `operation="REPLACE"`이며 자격증명 행·암호문·수정 메타데이터는 불변이다. **detail 에 시크릿은 없고 목적지도 host 까지만**(경로·쿼리는 토큰을 실을 수 있어 제외 — 릴레이의 로깅 규약과 동형).
> - **`webhookUrl=null` 허용**: 목적지 없이 **서명 시크릿만** 등재하는 구성이 유효하다 — `AmlHighRiskRegistrationApproved`(§8.1)처럼 아웃박스 행이 요청별 `webhook_target_url` 오버라이드를 싣는 이벤트는 테넌트 사전등록 URL 이 필요 없고 **서명 시크릿만 테넌트 소유**이기 때문이다(2026-07-24 예외 문단·가정 A5 **무변경**).
> - **쓰기 시점 SSRF 검증 없음(의도)**: 목적지는 §8 SSRF 정책(`WebhookUrlPolicy` 3단계)으로 **매 전송 직전에** 재검증되며, 등재 시점에는 검증하지 않는다. 엔진 케이스 RA-C12 ⑦(사설 IP 콜백도 **등재는 정상 완료**되고 전달 단계에서 릴레이 `FAILED` 로 수렴, 결재 롤백 없음)의 기대를 보존하기 위한 판단이다 — 쓰기 차단은 그 기대와 모순된다.
> - **마이그레이션 0**: 신규 Flyway 없음. `aml_api_credentials` 가 `webhook_url`·`secret_ciphertext`·`enabled`·`created_by`/`updated_by` 를 이미 갖고 `credential_type` CHECK 에 `WEBHOOK` 이 이미 있어(DB §3.15) **엔티티 매핑만 추가**했다.
> - ~~**알려진 한계**: 미등록 테넌트(`aml_tenants` 부재)로 PUT 하면 FK 위반이 **500** 으로 나온다(응답 본문에 내부 정보 누출은 없음). 400/404 가 적절하며 **후속 과제**다.~~
> - **미등록 테넌트 쓰기 = 400(2026-08-10 확정, 위 한계 해소 — aegis-aml main `48e8e697`)**: 미등록 테넌트(`aml_tenants` 부재)로 PUT 하면 **400 `AML.VALIDATION_ERROR`** `details="unknown tenant"` 로 거부한다(종전 FK 위반 500 대체). 문구·에러코드는 인입의 `AmlEventIngestService` VALIDATION `unknown tenant` 관례를 그대로 재사용하며 **신규 에러 체계는 0** 이다. **404 가 아닌 이유** — `Tenant-Id` 는 경로 자원이 아니라 **헤더 차원**이고, 같은 경로 `GET` 은 미등록 테넌트에도 **200 `configured=false`** 를 주므로 PUT 만 404 면 자기모순이다(GET 은 **무변경** — 미등재 200 은 완료 요건 F-048 회귀 테스트가 고정한 정본 동작이다). **가드 위치** — FK 를 소유한 **영속 어댑터(`WebhookCredentialAdminJpaAdapter.save`)** 에 두어 REST 한 경로가 아니라 **포트의 모든 호출자**(아래 bo-api 위임 포함)를 덮는다. 거부 메시지에 제출값·제약명·테이블명을 싣지 않는다. **외부 도달성 한계(사실)** — 라이브에서는 인증 필터가 (테넌트, API 키) 자격증명을 찾지 못해 **401 로 먼저 끊기므로** 이 400 은 **외부 직접 호출로는 관측되지 않는다**. 즉 위임·in-process 호출자에 대한 **선제 방어**이며, 계약은 Testcontainers 통합 테스트(`WebhookCredentialUnknownTenantIntegrationTest`)로 고정돼 있다.
> - **셋업 경로(시뮬레이터, REST-only)**: 개발·데모 스택은 `demo_ingest.ensure_webhook_credential`(sim-web 스테이지 **⓪⁗ `setup.webhook-credential`**, 기존 ⓪·⓪′·⓪″·⓪‴ 다음)이 이 PUT 으로 등재한다 — **멱등**(평문 보유 + 목적지 동일 + `enabled` 이면 PUT 없이 신규 0)이고 **평문 시크릿은 stdout·로그·화면 어디에도 출력하지 않는다**. 엔진 케이스 카탈로그 RA-C14~C18(자격증명 REST 자체)·RA-C12(콜백 서명 폐루프)가 이 경로를 전제로 실행된다.

##### bo-api 위임 표면 (BO 운영자 화면 AML-WHK-001, 2026-08-10 신설 — 코드=truth, aegis-aml main `48e8e697`)

> 종전에는 이 자격증명을 **machine credential 로만** 바꿀 수 있어 운영자가 콜백 목적지·서명 시크릿을 화면에서 등록·교체할 수 없었다. 아래 2경로가 그 갭을 닫는다 — 선례 §2.7 AMLC 계정 관리의 bo-api 위임 프록시(`AmlcCredentialController`→`AmlcCredentialService`)와 **동형**이다.

| 메서드 | 경로 | 권한(BO 세션) | 위임 대상(엔진) | 설명 |
|---|---|---|---|---|
| GET | `/api/v1/bo/aml/webhook-credential` | **`aml:case:read` OR `aml:admin:policy`**(+`BO_SUPER_ADMIN`) | `GET /api/v1/admin/aml/webhook-credential` | 마스킹 뷰 7필드를 엔진에서 **그대로** 반환(로컬 stub 없음 — 등재되지 않은 상태를 "설정됨"으로 꾸며 보이지 않게 **fail-closed**, 엔진 미가용 시 **503 `AML.ENGINE_UNAVAILABLE`**). BO facade DTO 도 **시크릿 필드를 갖지 않는다**(엔진 `MaskedView` 와 1:1) |
| PUT | `/api/v1/bo/aml/webhook-credential` | **`aml:admin:policy`**(+`BO_SUPER_ADMIN`) | `PUT /api/v1/admin/aml/webhook-credential` | body `{webhookUrl, secret, enabled}` 를 그대로 위임. **검증 actor 는 인증 principal 에서 파생**돼 `AmlEngineClient` 가 machine-auth v2 서명에 결속된 `X-User-Subject` 로 전달한다(엔진 `TrustedActorResolver` 가 신뢰하는 바로 그 재료 — body 는 actor 를 싣지 않는다). bo-api 는 **자체 bean validation 을 두지 않는다**(엔진이 이 계약의 단일 권위 — 빈 시크릿 400·actor 누락 400·scope 403·미등록 테넌트 400 이 **원래 상태·`AML.*` 코드 그대로** bo-web 까지 올라간다. 삼키거나 500 으로 뭉개지 않는다) |

> - **권한 조합 근거(GET 이 두 scope 인 이유)**: 엔진의 `ScopeGuard` 는 **machine credential** 을 검사하므로 운영자 게이트는 전적으로 bo-api 에 있다. 엔진은 읽기 `aml:case:read`·쓰기 `aml:admin:policy` 로 이름 붙였지만, `aml:admin:policy` 를 가진 유일한 역할 `AML_POLICY_ADMIN` 은 **`aml:case:read` 를 갖지 않는다**(`BackofficeRole`). 읽기를 1:1 로 좁히면 **유일한 쓰기 권한자가 덮어쓸 대상(현재 목적지)을 화면에서 보지 못하는 모순**이 생긴다. GET 이 주는 것은 **시크릿이 어떤 형태로도 없는 마스킹 뷰**라 이미 값을 교체할 수 있는 역할에게 읽기를 여는 것은 **노출 증가가 아니다**. 같은 조합은 형제 정책 화면 `AmlTenantController` 가 이미 쓰고 있다. **쓰기는 좁게 유지**한다 — `aml:admin:policy`(+super admin)만.
> - **감사**: bo-api 는 위임 호출을 `PROXY_AML_CALL` 로 남기고(`AmlEngineClient` 자동), 엔진은 종전대로 `POLICY_CHANGE / WEBHOOK_CREDENTIAL_SAVED` 를 남긴다 — **감사 계약 무변경**(신규 이벤트 코드 0).
> - **메뉴·NAV**: 화면 `/aml/webhook-credential`(**AML-WHK-001**)은 bo-web NAV **설정 › 연동·데이터**(`aml-config` → `aml-config-connect`, 서비스 관리·Ingest 카탈로그·명단 소스 옆)에 위치하고, 동적 메뉴 카탈로그 행은 bo-api Flyway **V23 `V23__webhook_credential_menu.sql`**(additive·멱등)이 등재한다(DB §7 bo-api 註). **런타임 인가는 계속 scope 기반**(위 `@PreAuthorize`)이고 메뉴 행은 정적 NAV 트리와의 정합용이다.
> - **화면 계약(기능정의서 §12.3 정본)**: 시크릿은 **전면 비노출**(마스킹조차 아님 — 조회 응답에 필드 자체가 없고, 편집 Modal 의 **입력 전용** 필드로만 존재하며 기존 값 미리채움 금지), `webhookUrl=null` 등재는 **"오버라이드 전용"** 으로 정확히 표기(목적지가 있는 것처럼 보이는 거짓 표시 금지), 쓰기 scope 미보유 세션은 **편집 진입점 0 + 읽기 전용 안내**.

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

> **엔진 CTR 임계 read 표면(다통화, PLAN 20260818 — U18 신설).** 위 bo-api `/api/v1/bo/aml/ctr-thresholds` 2종과 별개로, aml-svc 엔진이 **동일 `CtrThresholdAdminController`**(scope `aml:admin:policy`, `Tenant-Id` 헤더 필수) 상에 다음 2종 read-back 을 소유한다 — 기준통화 프로파일 apply 오케스트레이션(§14 U5 `STEP CTR_THRESHOLD`·게이트 ⓒ·현황 `GET .../currency-profile` 응답 `ctrThresholds[]`, CTR-C14 케이스)의 판정 정본이며 위 `POST {currency}:update` 상신 위임과 동일 subjectType(`CTR_THRESHOLD`)·테넌트 범위를 공유한다.
>
> | 메서드 | 경로 | scope | 설명 | DB |
> |---|---|---|---|---|
> | GET | `/api/v1/admin/aml/ctr-thresholds` | `aml:admin:policy` | 테넌트 전체 통화의 CTR 임계 행 목록(`findByTenantIdOrderByCurrency` 정렬). 응답 `CtrThresholdResponse[]{ currency, amount, updatedAt }` — **EXECUTED 반영값만**(상신 스테이징 미반영). 미설정 통화는 배열에서 생략(합성 폴백 없음 — F-077 'CTR 미개설' 사실 그대로 노출) | `aml_ctr_thresholds` |
> | GET | `/api/v1/admin/aml/ctr-thresholds/{currency}` | `aml:admin:policy` | 단건 통화 CTR 임계 행. 응답 `CtrThresholdResponse{ currency, amount, updatedAt }`. **행 부재 시 404(합성 `DEFAULT_THRESHOLD` 폴백 금지)** | `aml_ctr_thresholds` |

엔진 위임 계약은 `GET /api/v1/admin/aml/report-rules/{ruleCode}/params` → `{ruleCode,params,pendingApprovalId}`와 `POST /api/v1/admin/aml/report-rules/{ruleCode}:update-params`(header `X-User-Subject`, body `{makerId,reason,params}`) → `202 {ruleCode,staged,approvalId,status:"SUBMITTED",subjectType:"REPORT_RULE_PARAM"}`다. body `makerId`는 인증 주체와 일치해야 한다.

> 4-eyes `CTR_THRESHOLD`와 `REPORT_RULE_PARAM`은 모두 **aml-svc 엔진 결재 대상**이다. report-rule BFF는 인증 principal에서 maker를 파생해 엔진 `POST /api/v1/admin/aml/report-rules/{ruleCode}:update-params`로 상신 자체를 위임하고 실제 approvalId를 그대로 노출한다. 엔진은 전체 editable set과 AS-IS/TO-BE staged payload/hash를 고정하며 common approval checker가 EXECUTED로 전환할 때만 `aml_report_rule_params`를 원자 upsert한다. `GET /api/v1/admin/aml/report-rules/{ruleCode}/params`는 effective params와 `pendingApprovalId`를 반환한다. 비운영 엔진 미연결에서만 기존 bo-api stub 폐루프를 허용하고 운영은 fail-closed 한다. `REPORT_RULE` 룰 활성화는 bo-api 애플리케이션 승인 경계를 유지한다.

> **전수 인과 verifier 계약(2026-08-23).** BO catalog의 CTR 2/ACTIVE STR 7/DRAFT STR 1을 먼저 대조하고, 공유 CTR 임계 1축(소비자 `CTR_SINGLE`·`CTR_DAILY`)과 STR editable 6축을 각각 독립 실행한다. 승인 전 응답 approvalId는 detail의 makerId·subjectType/ref·reason·stagedPayload/hash·rule/currency/requestedAmount 및 target pending ID와 결속한 뒤에만 실행한다. 각 축은 변경 전/후 fresh canonical 거래의 반대 판정, exact alert/report/ONGOING RA lineage, 동일 event replay 신규 0, BO typed full-snapshot 원상복원을 모두 만족해야 하며 한 축 미실행도 전체 FAIL이다.

> **bo-api AML-STAT 집계 BFF**: BO 화면은 엔진 admin 원천을 직접 호출하지 않고 `GET /api/v1/bo/aml/stats/str`(STR 일별 보고 추이 + 기존 퍼널/지연/미보고 집계, COMPLIANCE 전담), `GET /api/v1/bo/aml/stats/ctr`(CTR 일별 보고 추이 + 기존 퍼널, STR 통계와 동일 DTO 규격), `GET /api/v1/bo/aml/stats/scenarios`(TM 룰 효과성 — 행마다 집계 + **룰 카탈로그 보강 7필드**(`family`·`reasonCode`·`evaluationMode`·`actions`·`naturalLanguage`·`source`·`conditions[]`)와 STR tipping-off 플래그 `strRestricted`, §3.6), `GET /api/v1/bo/aml/stats/report-rules?family=CTR|STR`(룰군별 룰 개요 — CTR·룰 효과성 통계 메뉴는 `family=CTR`(CTR 룰 개요 CTR_SINGLE·CTR_DAILY), STR·룰 효과성 통계 메뉴는 `family=STR`(STR 룰 개요 8종). `family=STR`은 STR 퍼널과 동일한 tipping-off 전담(COMPLIANCE) 게이트 — 비전담 `403 AML.FORBIDDEN_SCOPE`, CTR은 열림. `hitCount30d`는 엔진 알림 집계(룰코드별) 정본이고 라이브 store 폴백을 쓴다. `draftCount`는 라이브 CTR/STR DRAFT store `firedRules` 위 실집계이되 **엔진 위임 배치에서는 룰별 귀속 불가라 `null`('집계 불가')** 이다(BUILT_IN·CUSTOM 동일 기준, §3.6a), `status`는 EXECUTED 활성화 반영 ACTIVE/DRAFT)을 호출한다. 네 endpoint는 bo-api 소유 read aggregate(API §9 경계)이며 응답은 집계 카운트만 포함한다. 응답 DTO §3.6/§3.6a `ReportDailyCount`·`ReportRuleOverviewRow`.

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
| GET | `/api/v1/admin/aml/high-risk-registry` | `aml:admin:high-risk-registry` | — | 분류 기준(criteria, read-only) + 참조 리스트 5종 조회 — 운영자 관리 3종 `PRODUCT`·`VASP`·`HIGH_NET_WORTH` + 자동 등재 2종 `PEP_INDIVIDUALS`·`RA_HIGH_RISK_CUSTOMERS`(read-only, 결재 폐루프로만 적재) | `aml_high_risk_registry`,`aml_high_risk_registry_items` |
| PUT | `/api/v1/admin/aml/high-risk-registry/reference-lists/{listType}` | `aml:admin:high-risk-registry` | 🔒4-eyes(`HIGH_RISK_REGISTRY`) | 참조 리스트 변경 상신(**대상 `listType` 교체** — 운영자 관리 3종 `PRODUCT`·`VASP`·`HIGH_NET_WORTH` 한정. 자동 등재 2종 `PEP_INDIVIDUALS`·`RA_HIGH_RISK_CUSTOMERS` 는 listType 상신 시 400 `AML.VALIDATION_ERROR`로 거부되며 bo-api 위임도 엔진 상태·코드를 보존해 동일하게 400 전달, `UPDATE\|<version>` subjectRef, 전체 staged payload drift guard) — 결재 EXECUTED 적용 시 자동 등재 2종은 적용 시점 저장본을 보존하고 관리 3종만 교체, version 은 적용 시점 현재+1(상신 시 `UPDATE\|<version>` 은 상신 시점 예상값) + 일치 고객 RA 강제 상향 재평가 트리거 | `aml_high_risk_registry`,`aml_high_risk_registry_items`,`aml_approvals` |
| POST | `/api/v1/admin/aml/high-risk-registry/registrations` | `aml:admin:high-risk-registry` | 🔒4-eyes(`HRR_REGISTRATION`, 승인선 `EXECUTIVE_APPROVAL`) | RA 당연고위험 회원 등재 상신(RA 상세 배선·`customerRef` 토큰·`tier` 기본 HIGH). body `{customerRef, tier?, makerId, reason?}`. **신규 상신 = `202 {approvalId, customerRef, subjectType:HRR_REGISTRATION, approvalLine:EXECUTIVE_APPROVAL, status:SUBMITTED}`**. **멱등 no-op(이미 등재 EXECUTED / 상신 대기 PENDING) = `200 {approvalId:null, status:NOOP}`** — 재평가 루프 종료 불변식(A6), 오류 아님. 승인 EXECUTED 시 `RA_HIGH_RISK_CUSTOMERS` 등재 + RA 강제 상향 | `aml_high_risk_registry_items`,`aml_approvals` |
| GET | `/api/v1/admin/aml/high-risk-registry/registrations/{customerRef}` | `aml:admin:high-risk-registry` | — | 당연고위험 등재 상태(미상신/PENDING/EXECUTED) read-back. 응답 `{customerRef, registered, pending, pendingApprovalId}` — RA 상세 등재 결재 상태 패널, no-op 세분(`registered` vs `pending`) 판별 | `aml_high_risk_registry_items`,`aml_approvals` |

> **위임 경로 멱등 no-op 계약(코드=truth, fix-20260707).** bo-api `AmlHighRiskRegistryService.submitRegistration`(`POST /api/v1/bo/aml/**` 위임)는 엔진 등재 응답의 **`status=NOOP`(200·`approvalId=null`)을 정상 멱등 no-op 으로 매핑**(502 로 변환하지 않음) — stub fallback 경로(등재됨/대기중 no-op 가드)와 계약 대칭. **`status` 부재 + `approvalId=null` 인 진짜 프록시 오류만 `502 BAD_GATEWAY`(`AML-PROXY-ERROR`) 유지**. **가정 A(§미정의)**: 엔진 등재 응답은 `alreadyRegistered` vs `pending` 세분 플래그를 no-op 응답에 담지 않으므로, bo-api 는 no-op 직후 `GET .../registrations/{customerRef}` read-back(`RegistrationStateResponse.registered`/`pending`)으로 세분을 판별해 `HrrRegistrationResponse.alreadyRegistered`/`pending` 를 채운다(엔진이 세분 플래그를 응답에 추가하면 read-back 제거). read-back 실패 시 보수적 `pending=true` 폴백(no-op 자체는 200 유지). §10 등재표 `HRR_REGISTRATION` 행 참조.

> **bo-api 위임 본문 필드명 정정(코드=truth, 2026-09-04 PLAN 20260904-aml-hrr-registration-followups).** bo-api `POST /api/v1/bo/aml/high-risk-registry/registrations` 공개 본문 `{ memberRef, tier?, reason? }`(공개 DTO `HrrRegistrationRequest.memberRef` — bo-web·본 문서 계약 무변경)는 엔진 위임 시 `{ customerRef, tier, makerId, reason }`로 매핑된다(엔진 계약 `RegistrationRequest.customerRef` 1:1). 이전에는 위임 본문 필드명이 `memberRef`로 정정 전 전송되어 엔진이 `customerRef is required`(400)로 항상 거부했다 — 이 경로는 결함 정정 전까지 실사용 불가였고, 라이브 HRR_REGISTRATION 86건은 전부 엔진 자동상신(maker `system:ra-engine`)이라 드러나지 않았다.

> **bo-api 공개 등재 상태 read-back 위임(코드=truth, 2026-07-12 feature/aml-hrr-closed-loop-visualization).** 위 엔진 `GET .../registrations/{customerRef}`(engine admin, scope `aml:admin:high-risk-registry`)를 **bo-api 가 공개 read-back 엔드포인트 `GET /api/v1/bo/aml/high-risk-registry/registrations/{customerRef}`(scope `aml:case:read` — 순수 조회)로 위임 노출**한다. RA 상세(AML-RA-003, PRD §12-A.4 BR-006) 당연고위험 폐루프 흐름도가 회원별 현재 단계(②자동상신→③경영진 승인 대기/확정→④등재)를 바인딩하는 데 쓰이며, 응답 `HrrRegistrationState{customerRef, registered, pending, pendingApprovalId, tier, submittedAt, registeredAt}`(위임 경로는 엔진 `registered`/`pending`/`pendingApprovalId` 매핑·`tier`/시각은 null / 비운영 stub 경로는 `AmlStubStore` staged/executed HRR fold 로 `tier`·시각 파생·운영 프로파일 fail-closed `503 AML.ENGINE_UNAVAILABLE`). PII 미포함(토큰 `customerRef`·플래그·시각만). 승인/반려 액션은 별도 신설 없이 공통 결재함 `:approve`/`:reject`(scope `aml:admin:approval`)가 `HRR_REGISTRATION` 을 동일 라우팅(§8·§10) — RA 상세 흐름도가 `pendingApprovalId` 로 결선한다. 흐름도 5단계 도출은 bo-web 순수 함수(`lib/aml-hrr-flow.ts deriveHrrFlow`)로 read-back·최신 결재·`mandatoryHighRisk` 입력만으로 스테퍼 상태를 매핑한다(엔진 계약 변경 없음).

> **bo-api 레지스트리 조회 scope 분리(2026-09-04, feature/aml-hrr-registry-search).** `GET /api/v1/bo/aml/high-risk-registry` 는 `aml:case:read` 또는 `aml:admin:high-risk-registry`(또는 `BO_SUPER_ADMIN`)로 조회 가능(§12-B.6 조회 권한 정합). `PUT`·`POST /registrations` 는 계속 전용 scope. 엔진 admin surface 의 machine scope 는 무변경.

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

응답 `IngestEventResponse`: `{ eventId, accepted, idempotent, traceId, decision?, scoreId?, riskScore?, riskGrade?, requiredAction?, modelVersion?, reason?, mandatoryHighRisk?, mandatoryHighRiskReasons?, wlfHit? }`. CDD 외 이벤트는 decision 계열이 null이고, `customer.cdd.completed` ACCEPTED/REPLAYED는 V42 불변 온보딩 decision snapshot을 반환한다. 마지막 3필드(`mandatoryHighRisk`/`mandatoryHighRiskReasons`/`wlfHit`)는 **additive**(20260718 사용자 지시, F-003 해제, §2.1 note 참조) — 1차 RA 요약이며 기존 11필드 이름·순서·타입은 불변이다.

> **데모 회원 등록 인입 이벤트·`senderHolderName`(비-prod, 데이터 정직화 v9.27, 기능정의서 §1.11 BR-DEMO-HONESTY).** 데모(비-prod stub)는 회원 identity·신고소득의 유일 원천을 **회원 등록 인입 이벤트**로 받는다 — 테스트 인입 페이로드 `{eventType:"member", member:{memberRef, name, nationality, gender, dob, declaredIncomePhp}}` 가 인메모리 member vault(상한·eviction·전송값=열람값 reveal)에 upsert 되며, 미등록 회원의 거래 인입은 identity 의존 판정(명단 매칭·소득 룰)을 skip 한다. 거래 payload 에는 **`senderHolderName`**(nullable, 송금 명의인 이름 — `STR_THIRD_PARTY` 실데이터 신호: 회원 실명과 매처상 불일치 시 발동)이 가산된다. 데모 시드/hash 파생 회원 프로필은 폐기됐다. **비-prod 전용**(prod 프로파일 미노출). raw PII 는 vault reveal(감사 게이트) 로만.

### 3.2 ScreenRequest → `POST /api/v1/aml/screen` (DB `aml_screening_results`, `ScreeningController.ScreenRequest`)

**code truth: 평면(flat) 구조** — 중첩 `subject` 객체·`sourceTypes` 필드 없음. `Idempotency-Key` 헤더 필수. 매칭 입력 원문은 일시 처리 후 미저장(§19.2), 저장은 hash/token만.

> **동기 응답 계약 확인(20260718, PLAN 20260718-sync-verdict-in-response U8, 무변경 — WLF-C07).** `POST /api/v1/aml/screen` 은 이미 `status`/`score`/`matchedEntries`/`reasonCodes` 등 판정 결과를 **동기 단일 응답**으로 반환한다(별도 2차 조회 불요). 본 계획은 이 계약을 접촉하지 않으며 확인·케이스 고정만 수행한다.

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
| `callbackUrl` | string | — | **요청별 아웃바운드 웹훅 목적지 오버라이드**(PLAN 20260903-aml-decision-status-webhooks — 사용자 지시로 F-084 부분 해제). 이 스크리닝의 결재 실행 결과(`AmlScreeningResolved`/`AmlScreeningWhitelistChanged`, §8.1)를 받을 목적지. 길이 ≤2048자. 수신 시 `WebhookUrlPolicy`(SSRF 정책, §8 서명 게이트와 동일 규칙)로 **1회 사전검증**하며 위반 시 **400**으로 요청 자체를 거부한다(§12.1 CDD `callbackUrl`이 형식검증 없이 발송 시점에만 재검증하는 것과 다른 계약). 값이 없으면 목적지는 테넌트 사전등록 `webhook_url`(§8)로 폴백. 저장은 `aml_screening_results.callback_url`(V74). 발송 시점에도 §8 SSRF 게이트를 재검증한다(수신 통과 후 목적지가 더 이상 안전하지 않으면 relay 가 실패로 기록) |

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
| `scoreBreakdown` | object | name/dob/country/document/address/relationship/negative 분해(§10.3). **가중 분모 = 해당 결과에 스냅샷된 ACTIVE profile의 6개 weight 합**이며 overall=`max(0, Σ(weight·score)/sumOfWeights() - negativePenalty×negativeSignal)`이다. 미제공 컴포넌트는 분자 기여 0·분모 유지한다. 주소는 요청 `addressTokens`와 엔트리 attributes 주소 토큰이 모두 있을 때만, negative signal은 결정적 불일치 근거가 있을 때만 적용한다. 과거 결과는 이후 정책 변경에도 이 스냅샷 의미가 변하지 않는다. **후보 recall 재현 스냅샷(P0-05·V49)**: `scoreBreakdown.candidateStrategy` object 에 후보 생성 4전략(S1 exact primary_name_hash∪S2 normalized_tokens 교집합∪S3 pg_trgm word_similarity∪S4 double-metaphone 교집합) 진단을 영속한다 — `{ candidateStrategyVersion(`wlf-cand-v2`), matcherVersion(=`appliedPolicy.definitionHash`), trgmFloor(기본 0.30), candidateCap(기본 200), candidateCapScope(`"PER_LIST_TYPE_AXIS"`), phoneticEnabled(기본 true), candidateCapHit(상한 도달 여부·true 면 log.warn+증거로 silent truncation 방지), candidateCount(최종 후보수), strategyCounts(전략별 후보수 map), axisCounts(명단축별 후보수 map `{SANCTIONS_LAW, PEP, OTHER}`) }`. 정밀도는 후단 FuzzyMatchEngine 이 책임하고 이 스냅샷은 recall 재현·튜닝 근거다. **매처 알고리즘 스냅샷(`wlf-name-v4`)**: `scoreBreakdown.nameMatcher` object 에 `{ version, dominantComponent, components{exact,tokenSet,edit,compact,alignment,containment,phonetic,boundarySet} }` 를 영속하고, `candidateStrategy.nameMatcherVersion` 에 같은 버전을 함께 핀한다. 이 축이 **정책팩 `definitionHash` 와 분리**돼 있는 이유는 정의해시가 가중치·페널티·임계만 해시하기 때문이다 — 이름 산식이 바뀌어도 정의해시는 회전하지 않으므로, 이 핀이 없으면 서로 다른 매처가 낸 두 결과가 하나의 `rule_version` 아래에서 구분되지 않는다. `rule_version` 을 대신 회전시키지 않는 이유는 그것이 **승인된 오탐 화이트리스트의 키**이기 때문이다(회전 시 전건 무효화). **`nameMatcher` 키가 없는 과거 결과는 `wlf-name-v1`(exact/tokenSet/edit 블렌드)로 해석한다 — 이 규칙은 코드에 남지 않으므로 본 문서가 유일 정본이다.** 토큰 정렬 계열 컴포넌트(`alignment`·`containment`·`boundarySet`)는 **인자 순서와 무관**하며(페어 강도 내림차순 배정, 동점은 방향 독립 키로 해소) `components` 맵의 **직렬화 키 순서까지 결정적**이다 — 동일 입력은 언제나 동일 증거를 낳는다(§9 감사 재현성). **이름 강한 일치 승격 감사 스냅샷**: `scoreBreakdown.nameEscalation`은 승격 적용 결과에만 `{ applied:true, nameScore, threshold }`로 기록하고 미승격 결과에는 생략한다. **후보 절단 가시화(2026-08-11)**: `candidateStrategy.recallComplete`(boolean, `= !candidateCapHit`)와 절단 시에만 붙는 `candidateStrategy.truncatedBy`(`"CANDIDATE_CAP"`)를 함께 영속한다 — 절단된 회수 집합이 완전 판정으로 읽히면 안 되고, 소비자가 `candidateCapHit` 로부터 추론하지 않아도 되게 한다(사유코드는 추가하지 않는다 — 케이스 카탈로그가 verbatim 단언). **명단축별 후보 cap(2026-08-12, `wlf-cand-v2` — 제재 미탐 차단)**: `candidateCap` 은 전역 1개가 아니라 **명단축(`SANCTIONS_LAW`=SANCTIONS·LAW_ENFORCEMENT / `PEP` / `OTHER`)별**로 적용된다 — 전역 cap 에서는 흔한 이름의 PEP 후보가 cap 을 채워 진짜 제재 엔트리를 후보 집합 밖으로 밀어냈고, 그 엔트리는 정책 평가에 도달조차 못 한 채 `NO_MATCH` 가 됐다. **제재·법집행은 오직 다른 제재·법집행에만 잘린다**(계약)는 뜻이며, 회수는 strictly additive 이고 후보 총량 상한만 `cap` → `3 × cap` 으로 늘어난다. 진단은 `candidateCapScope`(`"PER_LIST_TYPE_AXIS"` — 과거 전역 cap 증거와 구분하는 키)·`axisCounts`(축별 최종 후보수)·절단 시에만 붙는 `truncatedAxes[]`(잘린 축 이름 배열, 예 `["PEP"]`)이며 `candidateCapHit`·`recallComplete`·`truncatedBy` 의 의미는 불변이다(축 중 하나라도 잘리면 true). **PEP 축 분리 억제 감사 블록(`pepAxis`, 2026-08-12)**: PEP 축 정책이 매치 승격을 보류한 결과에만 붙는다(그 외에는 키 자체가 없어 응답이 바이트 동일) — `{ applied:true, policyVersion(`wlf-pep-axis-v2`), axis(`CUSTOMER`|`COUNTERPARTY` — 정책이 실제로 적용한 **실효** 축), listType, decision(`CUSTOMER_CORROBORATION_MISSING`\|`CUSTOMER_CORROBORATION_UNKNOWN`\|**`CUSTOMER_CORROBORATION_UNKNOWN_SIGNAL`**(2026-08-13)\|`COUNTERPARTY_RISK_SIGNAL`), suppressedStatus(`POSSIBLE_MATCH`), suppressedBand(억제되지 않았다면 착지했을 밴드), riskScore(매처가 실제로 낸 가중 유사도 — 폐기하지 않는다), entryId, reviewThreshold }` + **역할 불일치 방어가 발동한 결과에만** `declaredAxis`(호출자가 선언한 축)·`axisMismatch:true` + **CUSTOMER 축 세 갈래(`CUSTOMER_CORROBORATION_MISSING`·`CUSTOMER_CORROBORATION_UNKNOWN`·`CUSTOMER_CORROBORATION_UNKNOWN_SIGNAL`)에만** `matchedCorroborators[]`·`acceptedCorroborators[]`·`requiredCorroborators`·`corroboration`(코로보레이터별 4상태 map `{ COUNTRY, DOB }` ∈ `MATCH`|`MISMATCH`|`UNKNOWN_LIST_DATA`|`UNKNOWN_TARGET_DATA`)·`unknownOutcome`(`SUPPRESS`\|`MATCH`\|**`RISK_SIGNAL`**(2026-08-13) — 전부 확인 불가일 때의 정책 귀결, 기본 `SUPPRESS`) + **`CUSTOMER_CORROBORATION_UNKNOWN_SIGNAL` 에만** `riskSignal:true`·`signalOrigin`(`"PEP_CORROBORATION_UNKNOWN"` — 하류가 이 신호를 수취인 이름 신호와 구분해 등록하는 키. 사유 코드와는 다른 네임스페이스다: 사유 코드는 "왜 매치가 아닌가", origin 은 "어느 신호 계열인가"). 다른 판정의 근거 블록은 **바이트 동일**하다. 직렬화 키 순서는 결정적(`LinkedHashMap`, `nameMatcher` 와 동형). `MISSING`(등재 값과 실제로 다르다)과 `UNKNOWN`(어느 쪽에 값이 없거나 읽히지 않아 확인 불가)은 결과가 같아도 사유가 반대이므로 코드·근거를 분리한다 — 뭉개면 잠재 미탐이 통계에서 사라진다. **저장 정밀도 진단(`scorePrecision`)**: 저장·응답 값은 `numeric(8,4)` 인데 임계 비교·밴드·이름 floor·후보 순위는 **반올림 전 원본 정밀도**로 결정하므로, 두 값이 다른 밴드를 낳을 때만 `{ storedScore, comparedScore, band, storageScaleBand, decidedOn:"FULL_PRECISION" }` 를 동봉해 어느 값이 결정했는지 밝힌다(일치하면 키 자체가 없어 응답 바이트 동일). PEP 축으로 억제된 행은 밴드가 정의상 `NO_MATCH` 라 이 진단을 생략한다. **시뮬레이션 회수 계약 진단(`candidateRecall`, 2026-08-13 — `:simulate` 응답 한정)**: admin/BFF `screenings:simulate`(§2.4) 응답에만 붙는 가산 블록으로, 그 시뮬레이션이 **어떤 회수 옵션으로 돌았는지**를 못 박는다 — `{ optionsSource(`"PRODUCTION_SCREENING"` — 자체 기본값을 조립하지 않고 실운영 스크리닝 유스케이스에서 읽어 왔다는 사실 자체의 기록), candidateCap, trgmFloor, phoneticEnabled, statementTimeoutMillis, candidateCapScope(`"PER_LIST_TYPE_AXIS"`), recalledCount(회수 후보수), candidateCount(`sourceTypes` 필터 후 채점 대상수), candidateCapHit, recallComplete(`= !candidateCapHit`), 절단 시에만 truncatedAxes[] }`. 직렬화 키 순서는 결정적이며(옵션 → 결과 → 절단), 밴드만으로는 두 경로가 같은 후보 집합을 봤는지 확인할 수 없기 때문에 필요하다. 종전 시뮬레이션은 회수 결과에서 후보 목록만 취해 `candidateCapHit` 를 통째로 버렸고, 운영자는 **잘린 후보 집합 위에서 내려진 판정**으로 임계를 튜닝하면서도 그 사실을 알 수 없었다. 영속 결과의 `candidateStrategy`(위)와는 별개 키다 — 이쪽은 실운영 screening 결과에 영속되는 recall 재현 스냅샷이고, `candidateRecall` 은 비영속 시뮬레이션 응답의 회수 계약 공표다. **기존 키·필드 삭제·이름 변경 0**이며 `SimulateResult` 레코드 시그니처는 불변이다. **BO 도달 범위(현재 사실)**: 이 블록은 **엔진 REST 응답까지만** 실린다 — bo-api BFF 는 `scoreBreakdown` 을 숫자 값만 남기는 map 으로 투영하므로(`AmlScreeningService.engineScoreBreakdown`) 중첩 블록은 전용 컴포넌트 투영이 있는 `pepAxis` 를 제외하고 BO 응답에 도달하지 않는다(`candidateRecall`·`candidateStrategy`·`nameMatcher`·`appliedPolicy` 동일). BO 화면 노출이 필요해지면 `pepAxis` 와 같은 전용 투영을 추가하는 별건이다. |
| `riskGrade` | enum | §5.2(평가 가능 시) |
| `reasonCodes` | array<string> | `reason_codes` (예: `NAME_COMPACT_MATCH`,`SANCTIONS_NAME_SIMILARITY`,`DOB_MATCH`,`COUNTRY_MATCH`). 이름 사유 코드는 **독립 2트랙**으로 발급한다(매처 `wlf-name-v4`). **트랙1 — 지배 컴포넌트**: name 서브스코어가 0 보다 크면 **항상 정확히 1개** 발급하며, 동점 우선순위는 `EXACT > COMPACT > ALIGNMENT > CONTAINMENT > TOKEN_SET > EDIT > PHONETIC` 이다 — `NAME_EXACT_MATCH`(토큰집합 완전일치) / `NAME_COMPACT_MATCH`(구분자 무관 일치) / `NAME_TOKEN_ALIGNMENT`(토큰 1:1 정렬 유사) / `NAME_TOKEN_CONTAINMENT`(짧은 이름이 긴 이름에 완전 포함 — 미들네임 누락형) / `NAME_TOKEN_SET`(토큰집합 유사) / `NAME_EDIT_DISTANCE`(철자 유사) / `NAME_PHONETIC`(발음 유사). `boundarySet`은 기존 7성분 최고점보다 엄격히 클 때만 우세해 `NAME_TOKEN_BOUNDARY_SET`을 발급하며, 동점이면 기존 dominant를 보존한다. 점수에 기여한 이름 유사도가 증거에 남지 않는 일이 없도록 하는 설명가능성 요건이다. **트랙2 — 명단군**: 기존 일반형 **`<LISTTYPE>_NAME_SIMILARITY`**(예 `SANCTIONS_NAME_SIMILARITY`/`PEP_NAME_SIMILARITY`/`INTERNAL_NAME_SIMILARITY`, listType 미상 시 `NAME_SIMILARITY`)를 `tokenSet≥0.6` 또는 `edit≥0.85` **또는 최종 name 점수 ≥0.85** 일 때 발급한다(기존 발화 조건 무수정 + OR 추가 = 하위호환). 두 트랙은 배타가 아니므로 완전일치 결과는 `NAME_EXACT_MATCH` 와 `<LISTTYPE>_NAME_SIMILARITY` 를 **함께** 갖는다. **`NAME_HIGH_CONFIDENCE`**는 이름 성분 점수가 `highConfidenceThreshold` 이상이고 negative 신호가 0인 강한 이름 일치가 overall `reviewThreshold` 미달을 승격시킨 경우에만 추가 발급한다. **PEP 축 분리 사유코드 4종(2026-08-12 3종 + 2026-08-13 1종, `listType=PEP` 한정 — 제재는 무영향)**: **`PEP_CORROBORATION_REQUIRED`**(회원(`CUSTOMER`) 축에서 국적·생년 코로보레이터가 요건에 못 미치고 **불일치 근거가 실재**해 매치로 승격하지 않음) · **`PEP_CORROBORATION_UNKNOWN`**(같은 회원 축이되 원인이 불일치가 아니라 **확인 불가** — 명단·고객 어느 쪽에 값이 없거나 읽히지 않음, 귀결은 `unknown-outcome` 노브) · **`PEP_NAME_RISK_SIGNAL`**(수취인(`COUNTERPARTY`) 축에서 이름 일치를 매치가 아닌 위험 신호로만 기록 — 이 신호는 STR PEP 룰·2차 상시 RA 로 실제 소비된다, §3.4a) · **`PEP_CORROBORATION_UNKNOWN_RISK_SIGNAL`**(2026-08-13 신설 — 같은 회원 축 "확인 불가" 이되 테넌트가 `unknown-outcome=RISK_SIGNAL` 을 선택해 **억제하되 계량 가능한 위험 신호로 표식**한 경우. `status` 는 `NO_MATCH` 그대로이고 억제와 갈리는 것은 사유 코드와 `pepAxis.riskSignal`·`signalOrigin` 2키뿐이다. **STR 발동 게이트에는 연결되지 않으며**(STR_PEP 발동 조건 무변경) 2026-08-13 시점 **엔진 하류 소비 경로도 아직 없다** — 정책 결정 대기). 네 코드는 `status=NO_MATCH` 인 결과에만 붙고 `scoreBreakdown.pepAxis` 블록과 짝을 이룬다. **`WLF_TARGET_ROLE_MISMATCH`**(2026-08-12): 등록 회원의 키로 `targetType=COUNTERPARTY` 스크리닝이 들어와 서버가 더 엄격한 CUSTOMER 축으로 정정한 경우 함께 발급하며 `pepAxis.declaredAxis`·`axisMismatch` 와 짝을 이룬다(요청은 거부하지 않는다). 일치 여부 플래그만 — 원문 이름/생년/국적 값 미포함 |
| `requiredActions` | array<string> | `MANUAL_REVIEW`/`EDD_REVIEW`/... |
| `matchedEntries` | array<string> | 후보 entry_id(masked). **하위호환 유지** — `matchedCandidates`와 병존(기존 소비자 보존) |
| `requestName` | string\|null | **WLF 읽기 응답 한정** 요청 시점 이름 스냅샷. `nameTokens`를 호출 순서·대소문자 그대로 공백 결합한 값이며, 스냅샷 없는 과거 결과와 복호화 불가 값은 키를 생략한다. `aml:case:read` 보유 호출자에게만 반환하고 `aml:screen:evaluate` 단독에는 생략한다. `POST /aml/screen` 동기 응답은 이 읽기 투영을 수행하지 않는다. |
| `matchedEntryNames` | object(`entryId`→string)\|null | **WLF 읽기 응답 한정** `matchedEntries`의 각 안정 entry id를 vault NAME으로 해소한 현재 게시본 명단 기재명 맵. vault 행이 없는 entry id는 키를 만들지 않으며, 재sync로 표기가 바뀔 수 있는 현재값(스크리닝 시점 스냅샷 아님)이다. `aml:case:read` 보유 호출자에게만 반환하고 `aml:screen:evaluate` 단독에는 생략한다. |
| `matchedCandidates` | array<object> | **가산(additive) 필드.** 매칭 후보 출처계보. 각 원소 `MatchedCandidate`(아래 표) — `matchedEntries`의 각 entry_id를 `aml_watchlist_entries`+`aml_watchlist_sources` 조인으로 enrich한 best-effort 파생값. **raw PII 미포함**(masked entryId·출처·버전·점수·토큰개수만) |
| `matchedRules` | array<object> | 적용된 WLF 룰 참조 `{ ruleCode, threshold, score }`(파생값, DB `rule_version` 기준 투영). `score`(number)는 해당 룰에 대해 산출된 실측 유사도 점수(threshold 대비 판정 근거·엔진 WLF 룰 score 투영, `ScreeningResponse.matchedRules[].score` 코드=truth). 단수 `ruleVersion`과 구분 |
| `appliedPolicy` | object | **가산 엔진 스냅샷.** `{ profile(SANCTIONS\|PEP), configVersion, ruleVersion, definitionHash, reviewThreshold, highConfidenceThreshold, confidenceBand(NO_MATCH\|REVIEW\|HIGH) }`. 결과 생성 시점의 실제 ACTIVE 정의를 고정하며 WLF 검토 상세·재현 검증의 정본이다. `HIGH`도 자동 TRUE_MATCH가 아니라 검토 우선순위 표시다. **이름 강한 일치 승격 시(2026-07-29)** `confidenceBand`는 `REVIEW`로 승격되며(overall 이 `reviewThreshold` 미달이어도 `status=POSSIBLE_MATCH`), `AUTO_DISCOUNTED` 오탐 화이트리스트는 승격보다 우선한다 — §10.3a·§12-B.8 BR-004. `POST /api/v1/aml/screen`(simulate 아님, 실 판정) 경로에만 적용되며 **simulate(WLF-004) 밴드 분석에는 미적용**(status 미생성 도구 — §Q5) |
| `subjectIdentity` | object | **가산(additive) 필드(bo-api WLF 매치 상세 투영).** reveal 게이트 대상 식별정보 메타 `SubjectIdentity`(아래 표) — 대상 식별자(`targetRef`) + reveal 가능 필드 키 목록만. **raw PII(이름·국적·성별·생년 원문) 미포함** — 원문은 `aml:pii:reveal`+사유+`RAW_DATA_ACCESS` 경로(§1.6, `POST /internal/v1/aml/pii/reveal` §2.6)로만 노출. **CUSTOMER·counterparty 대상 모두 `[NAME, NATIONALITY, GENDER, DOB]` 4필드 균일**(주체 무관). 주체가 보유하지 않는 필드(예 수취자=상대방의 성별·생년월일)는 reveal stub 이 빈 값(`""`)을 반환한다(placeholder 아님) |
| `ruleVersion` | string | 적용 WLF 룰/threshold 버전(DB `rule_version`) |
| `decidedBy` | string | 판정자(분석가, DB `decided_by`, nullable) |
| `decidedAt` | string(date-time) | 판정 시각(DB `decided_at`, nullable) |
| `createdAt` | string(date-time) | 결과 행 생성 시각(DB `created_at`, `ScreeningResponse.createdAt` 코드=truth). review-queue/history 기간필터·SLA 기준. **신규 영속 결과(`POST /api/v1/aml/screen` 유효 Idempotency-Key insert 경로)는 non-null 보장** — insert 후 DB `created_at` read-back(`ScreeningResultInserter` saveAndFlush+refresh), 응답은 `createdAt`만 population하는 additive 계약으로 신규/replay 응답이 대칭이다(2026-07-28 fix/wlf-freshness-createdat). `/internal/v1/aml/screen`도 동일 유스케이스라 유효 키 시 동형 non-null. **미영속(simulate 등 비저장)·blank Idempotency-Key 경로 한정으로 null 가능** — `decidedAt`(판정 시각)와 병기·구분 |
| `expiresAt` | string(date-time) | 실시간 결과 만료(§15.7) |
| `pendingDecision` | object\|null | **가산(additive) 필드**(PLAN 20260903-aml-decision-status-webhooks DoD 4, `GET .../screenings/{id}`·`GET .../screenings?transactionRef=\|targetRef=` 한정 — 심사 대기열/결정 제출 표면은 항상 `null`). 이 스크리닝에 걸린 비-terminal `WLF_DECISION` 4-eyes 결재 `{approvalId, targetStatus(`TRUE_MATCH`\|`FALSE_POSITIVE`\|`ESCALATED`), makerId, submittedAt}`(Q5). 없으면 `null` |
| `callbackConfigured` | boolean | **가산(additive) 필드**(PLAN 20260903-aml-decision-status-webhooks DoD 4, read-back 표면 `GET .../screenings/{id}`·`GET .../screenings?…` **및 `POST /api/v1/aml/screen` 응답**(영속된 `callback_url` 기준 — 멱등 replay 시에도 영속값) — 그 외 표면은 `false` 고정. **내부 메시 `POST /internal/v1/aml/screen` 은 `callbackUrl` 을 수락·검증·영속하지만 응답은 `false` 고정**(비대칭, 내부 호출자는 read-back 표면으로 확인)). 이 스크리닝에 요청별 `callbackUrl`(§3.2)이 등록돼 있는지 여부. URL 원문은 노출하지 않는다 |

> **bo-api enrichment와 passthrough.** `matchedCandidates[]`·`riskGrade`·`requiredActions[]`·`subjectIdentity` 등은 bo-api가 명단/화면 read model로 enrich할 수 있다. 반면 `requestName`·`matchedEntryNames`·후보 `listName`은 엔진이 허용한 WLF NAME 값을 변형·합성·마스킹하지 않고 전달하며, `matchedRules[]`, `ruleVersion`, `scoreBreakdown`(`candidateStrategy` 후보 recall 스냅샷 포함), `appliedPolicy`도 재계산하거나 하드코딩 임계로 덮지 않는다. raw PII는 승인된 NAME 카브아웃 외 어느 경로에도 추가하지 않는다.

> **`screeningHistory`(이전 판정 이력 배열)는 `ScreeningResponse` 미포함.** 동일 `screeningId`의 이전 판정 이력은 `GET /api/v1/aml/screenings/{screeningId}` 상세 조회(§2.2) 응답에서 파생한다. PRD 화면파생 방향 채택 — bo-web/bo-api가 이력 상세가 필요할 경우 단건 조회 엔드포인트를 호출하며, 실시간 screening POST 응답(`ScreeningResponse`)에는 이력 배열을 포함하지 않는다.

`MatchedCandidate`(매칭 후보 출처계보 — `matchedCandidates[]` 원소). **전 필드 nullable(best-effort).** bo-api가 `matchedEntries`의 각 entry_id로 `aml_watchlist_entries`·`aml_watchlist_sources`를 일괄 조인해 enrich하며, `listName`만 승인된 WLF NAME 인라인 카브아웃이다.

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
| `listName` | string | Y | 승인된 WLF NAME 인라인 값. `matchedEntryNames[entryId]`와 같은 현재 게시본 명단 기재명이며, 이름이 없는 엔트리는 `null`/키 생략으로 둔다. 재sync 표기 변경을 따라갈 수 있고 다른 PII field를 함께 열지 않는다. |

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
| `scenario` | enum | **평가 시나리오**(`ONBOARDING`/`ONGOING`, DB §3.9 `aml_risk_models.scenario`). `ONBOARDING`=1차·회원가입 CDD 완료 시점, `ONGOING`=2차·상시(STR/CTR 발동 시 거래 가중 재평가). **엔진(aml-svc `RiskScoreAdminController`·`CustomerRiskController`, `RiskScoreScenarioProjection.scenarioOf`)이 `factorBreakdown.scenario` 마커에서 파생해 explicit 필드로 목록·상세 응답에 직접 동봉**(대소문자 무시 파싱, 부재/미지=`ONBOARDING` graceful 기본). bo-api(`AmlRaService.fromEngineRisk`)는 이 explicit 값을 **우선 사용**하고, explicit 이 없는 구엔진 응답에 한해 자체 `scenarioFromBreakdown` 마커 파생으로 폴백한다 |
| `reassessmentAlerts` | array&lt;object&gt; | **2차(ONGOING) 재평가를 유발한 발동 STR/CTR 알림 계보**(재평가 사유). 각 원소 `{ alertId(string — 참조 토큰), ruleCode(string — 룰 코드 enum), severity(string), detectedAt(string(date-time)) }`. **엔진이 `factorBreakdown.triggerAlerts` 마커(V12 parameters `trigger.families [STR,CTR]`)에서 파생해 explicit 필드로 직접 동봉**(`RiskScoreScenarioProjection.reassessmentAlertsOf`). 1차(ONBOARDING) 행은 빈 배열. bo-api 는 explicit 값 우선, 부재 시 `reassessmentAlertsFromBreakdown` 마커 파생 폴백. raw PII 없음(마스킹 토큰·enum·시각만) |
| `reviewShortened` | object\|null | **재이행 주기 단축(from→to)** — 2차 재평가가 재이행 주기를 앞당긴 경우 `{ from(string(date-time) — 단축 전 `next_review_due_at`), to(string(date-time) — 단축 후) }`. **엔진이 `factorBreakdown.reviewShortened` 마커에서 파생해 explicit 필드로 직접 동봉**(`RiskScoreScenarioProjection.reviewShortenedOf`), **앞당기기만**(산출 주기가 기존 예정일보다 늦어 min-clamp 로 유지되거나 `applied` 미판별 시 `null`). 1차 행은 `null`. bo-api 는 explicit 값 우선, 부재 시 `reviewShortenedFromBreakdown` 마커 파생 폴백 |
| `signalScaling` | object\|null | **이름 위험 신호 점수 비례 스케일링 근거**(2026-08-13 additive, 설계서 §11.3a). 2차(ONGOING) 재평가가 이름만 닮은 신호 계보(현 운영 origin `PEP_NAME_RISK_SIGNAL`)의 **이름 하위점수**에 비례해 `STR_PEP` 기여 가중에 곱한 배수와 그 산출 파라미터다. `{ origin, alertId(참조 토큰), ruleCode, rawScore(number\|null — 스케일 입력이 된 이름 점수 0~1, 점수 미상이면 생략), multiplier(실제 적용 배수, `(0,1]`), curve(`LINEAR`\|`STEP`), floorScore, ceilingScore, minMultiplier, maxMultiplier, modelVersion, severityDriver(boolean — 그 알럿이 `max` 집계의 최대 기여를 실제로 점유했는가; false 면 배수를 바꿔도 RA 점수가 움직이지 않는다) }`. **엔진은 이 블록을 `factorBreakdown.signalScaling` 중첩 객체로 싣지만 `factorBreakdown` 노출 타입이 `Map<String, Double>`(요인→기여점수)이라 중첩 객체를 담을 수 없다** — bo-api 가 `triggerAlerts`·`reviewShortened` 선례와 동형으로 **전용 필드**로 파생하고 동시에 그 키를 요인 목록에서 배제한다(예약키 미등재 시 요인으로 오인돼 조용히 버려진다). 스케일 대상 알럿이 없으면 `null`(키 생략). 하위 필드 전부 nullable(엔진 evidence 손상·구 스키마 graceful 파생). raw PII 없음 — 점수·룰 코드·참조 토큰만. 1차(ONBOARDING) 행은 `null` |

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

### 3.3e HeldOnboardingDecisionPage → `GET /api/v1/admin/aml/risk-scores/held-onboarding` · BFF `/api/v1/bo/aml/risk-scores/held-onboarding`

`HeldOnboardingDecisionPage{ items, page, size, total }`은 아직 실제 `aml_risk_scores`가 없는 현재 HELD 업무만 나타낸다. 각 `HeldOnboardingDecision`은 `{ eventId, targetRef, decision, reason, retryStatus, retryAttempts, nextRetryAt, receivedAt }` 8필드다. `decision`은 `EDD_REQUIRED`, `reason`은 `ONBOARDING_RA_HELD`, `retryStatus`는 `PENDING|PROCESSING`; `receivedAt`은 V42 decision `created_at`(CDD 수신 트랜잭션의 최초 결정시각) verbatim이다. `scoreId/riskScore/riskGrade/requiredAction/modelVersion`은 누락값이 아니라 **존재하지 않는 별도 DTO 계약**이며 어떤 plane도 합성하지 않는다. targetRef는 비PII 회원 업무참조이고 raw canonical payload는 join·응답하지 않는다.

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

> **TM feature 신호(요청 바디 외, 과거 사실 — V61 이후 정의 소멸).** 레거시 시나리오(`HIGH_RISK_CORRIDOR`·`RAPID_MOVEMENT`·`REFUND_LAUNDERING`·`ROUND_TRIPPING` 등)는 `transaction.phpEquivalent`(PHP 환산액)와 `transaction.channelType`을 feature로 사용했으나, 이 정의 10종은 **2026-08-01(V61)로 전량 제거**됐다(거래 인입 경로에서 전혀 발동하지 않는 것이 v9.21 확정 사실, F-025 실측). `phpEquivalent`/corridor/`amountBase` 등 payload 파생 필드 자체는 evaluate 요청 바디 외 여전히 존재하나(CTR/STR 룰 카탈로그·기타 evidence 소비), 레거시 시나리오 feature 소비처는 소멸했다. **데이터 신호이며 규제(CTR/STR) 임계 교체가 아니다**(§3.4a evidence). |

> **송금 수취인 정보(v9.26 — 인입 payload `HanpassPhTransactionPayload`, 연동 §4.2).** 송금 거래의 수취인 STR_PEP·STR_SANCTION 동시 명단 평가(§3.4a `watchlistMatch.matchedParty=RECEIVER`, 기능정의서 §7.1 BR-013)를 위해 인입 payload 에 **`receiverName`**(nullable, 비-PII 운영값 — 매칭 transient·미영속)·**`receiverCountry`**(nullable, ISO 수취 국가=국적, **해외송금만**)가 additive 가산된다. 수취인 정보 규격은 **국내송금=이름만 / 해외송금=이름+국가**(성별·생년월일 미제공). 수취인 참조(`receiverRef`)는 서버가 `sha256(name|country)` 로 파생(payload 의 기존 `receiverRef` 우선). 엔진 evaluate 요청 바디(위 8필드)에는 수취인 이름/국가 원문을 싣지 않으며 COUNTERPARTY 스크리닝 계보로만 평가한다. |

> FDS/TM 공통 거래 payload 동기화: AML TM은 FDS 탐지 결정과 같은 실시간 거래 payload를 사용하되, CTR/STR 사후 보고 목적의 룰로 평가한다. 보조 신호는 TM feature snapshot에 `geo.country`, `geo.latitude`, `geo.longitude`, `customer.accountAgeDays`, `account.changedWithinHours`, `device.changedWithinHours`, `behavior.manyToOnePattern`, `behavior.oneToManyPattern`, `election.active`, `election.registrationSpikeCount`, `election.bulkCashAmountBase`로 기록한다.

응답 `TransactionEvaluateResponse`: `{ evaluated: true, alerts: [ { alertId, alertType(enum TM_SCENARIO/SCREENING/RA/FDS_ESCALATION/VENDOR_ALERT — 본 API가 정본, DB §5.18 `alert_type` 1:1), ruleCode(§5.6 — CTR/STR 룰 코드, v9.21), severity(LOW/MEDIUM/HIGH/CRITICAL), status(§5.7), evidence } ] }`. TM 알림은 발동 CTR/STR 룰마다 하나씩 반환된다(레거시 시나리오 발동 폐기).

#### TM 시나리오 카탈로그 — **V61(2026-08-01) 로 레거시 10종 정의 제거, 자유형 저작으로 전환**

`scenarioCode`는 더 이상 닫힌 enum이 아니다(과거 `TmScenario` enum 10종·hanpass-ph 데모 phpEquivalent ACTIVE 6종 카탈로그는 **삭제됨** — v9.21 확정 사실대로 거래 인입 경로에서 전혀 발동하지 않았기 때문, F-025 실측). 형식은 `^[A-Z][A-Z0-9_]{2,64}$`(DB §5.6) 이며 예약 코드 `CUSTOM_RULE`은 거부된다. 신선 배포 후 `aml_tm_scenarios` 정의 목록은 **0행이 정상**이고, REST 저작(`draft`/`simulate`/`:activate`, §2.7)으로 자유형 코드를 등록할 수 있으나 **신규 저작 시나리오도 거래 인입 경로에서 자동 발동하지 않는다**(신규 발동 정본은 CTR/STR 룰 카탈로그뿐 — §3.4a evidence·v9.21). 옛 10종 코드값 표·phpEquivalent 임계표는 과거 시드 이력이며 본 절에서 제거한다.

### 3.4a AlertDto → `GET /api/v1/aml/alerts/{alertId}` (DB `aml_alerts` §3.10 10컬럼+감사, `AlertController.AlertDto`)

| 필드 | 타입 | 설명 |
|---|---|---|
| `alertId` | string(uuid) | DB `alert_id` PK |
| `alertType` | enum | §5.18 `alert_type`(`TM_SCENARIO`/`SCREENING`/`RA`/`FDS_ESCALATION`/`VENDOR_ALERT`). **API 정본, DB 1:1** |
| `ruleCode` | string\|null | TM_SCENARIO 타입 알림의 안정 발동 룰 코드. 잠금 기준선 `AmlReportRuleCode` 10종 또는 사용자 정의 `ConfigurableReportRule.ruleCode`이며 엔진 DB `scenario_code`를 JSON `ruleCode`로 노출한다. custom evidence는 `trigger.ruleSource=CUSTOM`·`ruleFamily`·`ruleVersion`·**`condition`**을, **법정 카탈로그 evidence는 `trigger.ruleSource=BUILT_IN`·`ruleFamily`·`condition`을 병기한다(20260806 — `ruleVersion`은 법정 계열에 부재가 정상)**. 비-TM 알림은 null. |
| `targetRef` | string | 대상 고객/법인 ref(회원번호/대상 식별자, DB `target_ref`, nullable) |
| `transactionRef` | string | 관련 거래 ref(DB `transaction_ref`, nullable). hanpass-ph: charge_order_id/transaction_id/transfer_number/wallet_transaction_id |
| `severity` | enum | §5.19 `alert_severity`(`LOW`/`MEDIUM`/`HIGH`/`CRITICAL`) |
| `status` | enum | §5.7 `alert_status` **6종**: `DETECTED`/`TRIAGED`/`CASE_OPENED`/`DISMISSED`/`ESCALATED`/`STR_RECOMMENDED`(DB CHECK 6종. 이후 조사·보고·종결은 `aml_cases.status` 인계) |
| `evidence` | object | **TM 알림 상세 데이터모델(DB §3.10 정본). 정상 경로는 발동 CTR/STR 룰의 증거(v9.21 — 레거시 시나리오 발동 폐기)**. ① 트리거 `{ ruleCode(AmlReportRuleCode), strReasonCode(STR 룰만 — StrReasonCode: PEP/SANCTION/KYC_MISMATCH/STRUCTURED/NO_PURPOSE/THIRD_PARTY/UNUSUAL_PATTERN/MANUAL), description(룰 카탈로그 자연어) }`. **설정형(configurable) STR/CTR 룰 발동 알림**은 같은 트리거에 `{ ruleCode(ConfigurableReportRule.ruleCode), ruleFamily(STR\|CTR), ruleVersion, ruleSource=CUSTOM, description(운영자 입력), strReasonCode(STR만), condition }` 을 싣는다(v9.36) — `condition` 은 룰 DSL 조건식의 **사람이 읽는 요약**(예 `device.os = 'android'`·`count(subject, 24h) >= 5`)이며 locale 중립(영문 연산자 토큰) 결정적 문법의 저장 시점 고정 문자열(감사 재현성 — 번역 대상 아님, BO 는 행 라벨만 i18n)이고 요약 실패 시 키 자체를 생략한다(fail-safe, 알림 영속·발동 판정에 영향 0). 설정형 룰 알림은 evidence 최상위에 `features`(발동 시점 관측 피처 스냅샷 — `ConfigurableRuleDslPolicy` whitelist 키만, 비PII)·`parameters`(룰 파라미터)·`policyPack` 을 함께 싣는다(기존 계약). **(20260806 additive)** 법정 카탈로그 룰 알림은 여기에 `ruleSource="BUILT_IN"`·`ruleFamily(STR|CTR)`·`condition`을 함께 싣는다. `condition`은 **발동 당시 실효 파라미터로 치환된** 조건 요약(예 `band_lower >= 0.90 AND band_upper < 0.99 AND min_consecutive_days >= 3`)이며 설정형 계열과 같은 결정적 문법(영문 연산자 토큰·` AND ` join)·locale 중립(좌변은 파라미터 키 토큰 — 한국어 라벨 미탑재)을 따르고 요약 실패 시 키 자체를 생략한다(fail-safe). **`ruleVersion`은 법정 계열에 싣지 않는다** — 룰·`aml_report_rule_params` 어디에도 version 컬럼이 없어 합성 시 감사 메타 위조가 되며, 발동 시점 개정 앵커는 `policyPack.version`이 담당한다. **`name_match_threshold`(0.92)는 `condition`에 미포함** — `editable=false`·WLF 소유로 STR 평가식이 소비하지 않는 표시 전용 참고 지표다. **소급 백필 없음** — 키 부재는 "20260806 스냅샷 도입 이전 알림"으로 읽는다. 레포 계약 정본 `aegis-aml/docs/aml-data.md` §11.9, 케이스 STR-C18·CTR-C08. 레거시 시나리오 행이 남아 있으면 트리거가 `{ scenarioCode, strIndicator, description }`일 수 있으며 bo-api는 표시용 fallback으로만 소비한다. ② 집계 패턴 `{ measure, window, count, amount, currency, threshold, thresholdMet, appliedRiskGrade, countThreshold, distinctCounterparties, counterpartyThreshold }` — **CTR 룰**은 (주체, 영업일) 현금거래 합산액·임계, **STR 룰**은 주체 rolling 윈도우 집계(있는 룰에 한함). `measure`는 서술 라벨, `threshold`는 적용된 effective threshold이며 `appliedRiskGrade`/`countThreshold`/`distinctCounterparties`/`counterpartyThreshold`는 차등 임계·건수·다상대 축이 있는 경우에만 채운다. ③ `relatedTransactions[]`(`{ transactionRef, subjectRef(거래 주체 회원번호 토큰), memberRef(비PII 회원 업무참조 = originator.partyReference), channel, amount, currency, corridor, counterpartyRef, occurredAt, fdsDecisionRef }`) — 집계를 구성한 형제거래(최신순, 표시 캡 20; 윈도우 조회 불가·빈 결과 시 평가 거래 단건 폴백). **수취인 원문 이름(`counterpartyName`)은 evidence JSONB 영속 금지**이며 read-path vault reveal(§19.2)로만 해소한다. ④ `fundGraph`(`{ nodes[], edges[], path[], source }`; 윈도우 거래가 있으면 canonical 이벤트 파생 실 그래프 `source=CANONICAL_EVENTS`, 무거래 시만 `PLACEHOLDER_NO_TRANSFER_LINKS`). **노드 kind 는 product 별 파생(v9.33, 코드=truth `FundGraphBuilder`)** — 루트 `SUBJECT` + WALLET_TOPUP→`FUNDING_SOURCE`(충전수단 `fundingInstrumentType`·기본 INBOUND)·CARD_PAYMENT/WALLET_PAYMENT→`MERCHANT`(가맹점 `merchantRef`·label 은 `merchantCountry` 있을 때 `ref (국가)`·기본 OUTBOUND)·CROSS_BORDER_REMITTANCE/DOMESTIC_TRANSFER→`COUNTERPARTY`(`counterpartyRef` 토큰)·신호 전무만 `UNKNOWN_CP` 폴백(노드 first-seen·엣지 amount desc 최대 20·거래 최대 50). **COUNTERPARTY label 은 모든 `aml:case:read` 경로(TM evidence·Subject360 fund-view §2.5a 포함)에서 토큰만**(§19.2, P0-09 — 구 fund-view `이름 (국가)` 자동 vault reveal 은 제거, `counterpartyName==null` 로 빌더 전달). 원문 이름은 `aml:pii:reveal` reveal API(§2.6)로만 산출한다. + `features`(velocity 스냅샷 `{ velocityCount24h, velocitySumPhp, amountPhpEq }`, 있을 때). ⑤ `watchlistMatch`(**STR_PEP·STR_SANCTION 전용**, v9.22~v9.26) `{ listType(PEP\|SANCTIONS), entryId, entryName(마스킹 이름 토큰), sourceCode, provider, matchScore, nameScore(데모 발동 기준 ≥ 0.92), matchReasonCodes[], screeningRef, origin(WATCHLIST_MATCH\|KYC_PEP_FLAG\|PEP_NAME_RISK_SIGNAL — 후자는 PEP 축 분리 정책이 수취인 이름 일치를 매치가 아닌 위험 신호로 강등한 `NO_MATCH` 행에서 유래한 계보이며 `listType=PEP` 한정, 확정 매칭과 반드시 구분한다), entryIdentity(v9.31 — 명단 엔트리 식별정보 비교 메타 `{ entryRef, fields[] }`), matchedParty(v9.32 — `MEMBER`\|`RECEIVER`), partyRef, partyIdentity, additionalMatches[] }`. 데모 정본은 당사자 이름(+해외는 국가 보조)을 ACTIVE 명단 엔트리와 실매칭하고, 실엔진은 대상 최신 스크리닝 매칭 엔트리 중 룰 listType 일치 항목을 계보로 삼으며 부재 시 `origin=KYC_PEP_FLAG`로 정직 fallback 한다. 송금 채널(`DOMESTIC_REMIT`·`CROSS_BORDER_REMIT`)은 수취인 COUNTERPARTY 스크리닝 계보가 있으면 RECEIVER 매칭을 함께 수록하고, 계보 부재 시 수취인 평가를 skip 한다. 회원번호/거래번호는 업무 식별자로 노출하고 이름·계좌·지갑 등 raw PII 는 금지 |
| `subject360Ref` | string | 대상 360° 통합뷰 링크 키(= `targetRef`/`customerRef`) → `GET /api/v1/bo/aml/subjects/{customerRef}/360`(§2.5a). nullable |
| `sourceOrigin` | enum | §5.20 `source_origin`(`AML`/`FDS`/`VENDOR`) |
| `externalAlertRef` | string | 외부 벤더 alert 식별자(DB `external_alert_ref`, nullable, `source_origin=VENDOR`일 때) |
| `dispositionReason` | string\|null | **오탐 종결(`DISMISSED`) 처분 사유 코드**(DB `disposition_reason` VARCHAR(64), V30, nullable). `:dismiss` 전이 시 기록한 사유 코드 문자열(예 `FALSE_POSITIVE` 계열)이며, **불변식상 `DISMISSED` 상태에서만 non-null**(그 외 상태·구 알림은 null). 룰 효과성 오탐율(§12-B.3 = `DISMISSED`/알림)·감사의 실집계 근거. 사유 코드 카탈로그는 bo-api/bo-web 이 강제하고 엔진은 CHECK 미부과(하위호환 optional). **bo-api 투영(20260805)**: 목록 `AlertSummary`·단건 `AlertDetail`·처분 응답 `AlertActionResponse` 3경로 모두에 verbatim passthrough 한다(이전에는 bo-api 역직렬화 단계에서 버려져 종결 사유가 회수 불가였다 — 쓰기 전용 사유 결함 해소). bo-web 은 알림 상세 **처분 근거** 블록과 목록 상태 칸에 사유 코드를 카탈로그 라벨(ko/en)로 매핑해 표기하고, 미상 코드는 원본 코드로 폴백한다 |
| `dispositionActor` | string\|null | **오탐 종결 처분 행위자**(DB `disposition_actor` VARCHAR(128), V30, nullable). `:dismiss` 를 수행한 분석가 식별값. `dispositionReason` 과 동일 불변식(`DISMISSED` 에서만 non-null). raw PII 아님(운영 행위자 참조). **bo-api 투영(20260805)**: 단건 `AlertDetail` 에 verbatim passthrough(목록 `AlertSummary` 는 사유 코드만 — 처리자는 상세 전용) |
| `retiredAt` | string(date-time)\|null | **회수 시각**(DB `retired_at` TIMESTAMPTZ, V63, nullable). 발동한 설정형 룰이 `:retire` 4-eyes 로 회수될 때 기록되며, **불변식상 `RETIRED` 상태에서만 non-null**(DB CHECK `ck_aml_alerts_retired_at` 이 양방향 강제). 오탐 종결(`disposition_*`)과 **별개 컬럼** — 회수는 룰 자체의 무효화라 분석가의 업무 판단과 의미가 다르고, 회수해도 그때까지의 처분 필드는 보존된다 |
| `retiredBy` | string\|null | **회수 실행자**(DB `retired_by` VARCHAR(128), V63). 회수 승인을 실행한 checker. raw PII 아님(운영 행위자 참조) |
| `retireReason` | string\|null | **회수 사유**(DB `retire_reason` VARCHAR(256), V63). 상신 body `reason` 이며 미지정 시 엔진이 `RULE_RETIRED:{ruleCode}` 로 채운다. 비-PII 문자열 |
| `dispositionNote` | string\|null | **오탐 종결 판단 근거 자유 메모 — bo-api 단건 상세(`GET /api/v1/bo/aml/alerts/{alertId}`) 한정 파생 필드**(엔진 미보유). 처분 모달의 자유 메모(기능정의서 §7.1 BR-002a)는 엔진 스키마(`disposition_reason` 코드 컬럼)에 자리가 없어 bo-api 감사 로그(`AML_ALERT_DISMISSED` detail 의 `note`)에 보조 저장되며, 상세 조회 시 bo-api 가 그 감사 항목에서 회수해 싣는다(FDS §11.2 BR-007 · DB §4.11 동형). `DISMISSED` + 메모를 남긴 건에만 non-null(목록 `AlertSummary` 는 미탑재 — 코드 축만 노출). 분석가 작성 원문이므로 화면 언어로 번역하지 않는다. 감사 조회 실패 시 null 로 fail-soft(상세는 계속 서빙) |
| `createdAt` | string(date-time) | 생성 시각 |
| `updatedAt` | string(date-time) | 최종 수정 시각 |
| `aggregationSummary` | object\|null | **목록(브라우즈) 응답 한정 triage 프리뷰 집계.** TM 알림 **목록**(`GET /api/v1/bo/aml/alerts`, §2.5a → bo-api `AlertSummary`) 응답에서만 채워지는 가산 필드. `evidence`(트리거·집계 패턴)에서 목록 시점 파생(N+1 없음·행별 evidence 조립 회피)하며, **raw PII 미포함(집계 수치·라벨만)**. 단건 상세(`AlertDto`)는 `evidence` 전문을 제공하므로 본 요약은 생략 가능(null). 원소 `AggregationSummary`(아래 표) |
| `subjectIdentity` | object\|null | **명단 룰(STR_PEP·STR_SANCTION) 단건 상세 한정 가산 필드(v9.24, bo-api read-time projection — 엔진 API 무변경).** 원거래 대상 회원의 식별정보 비교 메타 — WLF 매치 상세와 **공용 `SubjectIdentity` 타입**(§3.2, `{ targetRef, fields[] }`, `fields ⊆ [NAME, NATIONALITY, GENDER, DOB]`). **raw PII 미포함** — reveal 가능 필드 키만. 원문은 `POST /api/v1/bo/aml/pii/reveal`(`aml:pii:reveal`+사유+`RAW_DATA_ACCESS` 감사, §2.6) 재사용으로만 노출(신규 엔드포인트 없음). 비-명단 룰·구 알림·identity 부재 시 `null` |

> **KYC 신고소득 계보(2026-08-16, `STR_KYC_INCOME_MISMATCH` 전용).** 이 룰의 발동 알림은 기존 built-in `trigger.condition` 스냅샷과 함께 `trigger.incomeProxy = { band?, amount, source, basis, currency, period, approximate }`를 싣는다. 숫자 신고는 `source="KYC_DECLARED_INCOME"`, `basis="UPPER_BOUND"|"EXACT"`이며 신고 통화·기간을 보존하고 `EQ`만 `approximate=false`다. 숫자 키가 없을 때의 레거시 밴드는 `source="KYC_DECLARED_INCOME_BAND"`·`basis="UPPER_BOUND"`·`currency="PHP"`·`period="MONTHLY"`·`approximate=true`이고 `band`를 함께 보존한다. `amount`는 평가 진입에서 1회 resolve 해 월 정규화한 값이며 judge·효과 임계·evidence가 공유하고 evidence 조립 시 고객 원장을 재조회하지 않는다. 구 알림·비해당 룰은 키 부재가 정상이고, 키 부재를 exact 숫자 신고로 해석하지 않는다.
>
> raw PII 미노출. `targetRef`/`transactionRef`는 업무 식별자로 노출하고, 이름·계좌·지갑 등 원문 PII 는 reveal/hash 정책을 따른다. 감사 컬럼(`created_by`/`updated_by`/`trace_id`/`data_scope`)은 응답에서 생략.

법정 CTR/STR 알럿의 `evidence` 최상위에는 발동 당시 관련거래 범위를
`evidenceWindow{dimension,windowStart?,asOf,startInclusive,cashOnly,label,timezone?}`로 동결한다.
`GET .../{alertId}/related-transactions`는 이 snapshot을 현재 tenant binding보다 우선한다.
`CTR_DAILY`·`STR_STRUCTURED`는 `[windowStart,asOf]`, rolling 24h는 `(windowStart,asOf]`이며,
snapshot 없는 legacy 알럿만 현재 정책 기반 fallback을 쓴다.

`AggregationSummary`(`aggregationSummary` 객체 — TM 알림 목록 triage 프리뷰 집계). **전 필드 nullable(집계 파생·best-effort).** **설정형(configurable) 룰 알림 폴백 파생(코드=truth, verify-V2 N-2)**: 설정형 룰은 윈도우 집계가 없는 단건 술어 룰이라 evidence 에 `aggregation`·`relatedTransactions[]` 가 없고 STR 지표를 `trigger.strReasonCode` 에, 평가 피처를 `features` 에 싣는다. bo-api 는 `strIndicator ← trigger.strIndicator ?? trigger.strReasonCode`, `dominantChannel ← features["transaction.channelType"]`, `currency ← features["transaction.currency"]` 로 폴백 파생한다. **집계 수치는 만들지 않는다** — `windowLabel`·`measure`·`threshold`·`thresholdMet`·`relatedCount`·`relatedAmount` 는 null 유지(임계 없는 룰의 거래금액을 `measure` 로 실으면 null 임계와 짝지어 오해를 만든다). `evidence`의 트리거(`strIndicator`)·집계 패턴(`measure`/`window`/`threshold`/`count`/`amount`/`currency`)·`relatedTransactions[]` 에서 목록 시점 파생하며, raw PII는 일절 포함하지 않는다(집계 수치·라벨만):

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

> §3.2 WLF 스크리닝의 `requestName`·`matchedEntryNames` NAME 2종 인라인 카브아웃은 이 `counterpartyName` 계약을 바꾸지 않는다. 알림·근거거래는 계속 마스킹 토큰/null이며, WLF 이외 이름을 `aml:case:read`만으로 해소하지 않는다.

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

> **TM 시나리오 정의 계약(코드=truth, **V61 이후 자유형 generic decode**).** 엔진은 `aml_tm_scenarios.dsl`(JSONB)을 `TmCondition` 트리로 컴파일하고(`aml-svc TmScenarioDslParser`/`TmCondition`), bo-api BFF(`GET /api/v1/bo/aml/tm-scenarios/{scenarioCode}`, §2.5a)는 active `parameters`/`dsl`을 `ScenarioDefinition{family, severity, fields[]}`로 **generic 디코드**한다(`bo-api ScenarioDslCodec` — per-code 템플릿 `ScenarioTemplates` 는 2026-08-01 삭제됨, 목록이 비는 것이 정상이라 카탈로그 기본값 개념 자체가 소멸). raw PII 없음(설정값만).

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

> **`scenarioCode`/`displayName` 계약(V61 이후, 코드=truth).** `scenarioCode` 는 자유형 String(형식 `^[A-Z][A-Z0-9_]{2,64}$`, 예약 코드 `CUSTOM_RULE` 거부 — DB §5.6). **`displayName` 필드는 유지되며 값은 항상 코드 원문**(레거시 10종 한글 라벨 카탈로그 폐기 — 자유형 코드는 카탈로그 라벨을 가질 수 없다). `family` 는 active `dsl` 트리에 `velocity` 노드가 있으면 `THRESHOLD`, 없으면 `SIGNAL`(`ScenarioDslCodec.familyOf`, per-code 템플릿 제거). `fields[]` 는 `parameters` 맵을 **generic 파생**한다(per-code switch 없음) — 값 타입이 `Boolean`→`TOGGLE`, `Number`→`NUMBER`, `List`→`COUNTRY_MULTI`, 그 외→`SELECT`, `key`=`label`(생성 라벨 없음), `severity`/등급 오버라이드 인픽스 키는 제외.

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
| `thresholdsByGrade` | object\|null | **위험등급별 차등 임계(가산·additive, 직렬화 NON_NULL)**. `Map<RiskGrade, 숫자>` — **NUMBER/AMOUNT 타입 한정**으로만 적용, 다른 타입 필드는 `null`/생략(하위호환 — 등급 없는 필드는 기존과 동일). 미설정 등급은 base `value` fallback. 값은 `value`와 동일 형상·단위의 평이한 숫자(PII 없음). **활성화(`:activate`) 시 컴파일 규칙(2026-08-02, 코드=truth FX-U1/FX-U2)**: 기존 정의 편집(대상 `scenarioCode`에 버전 1건 이상 존재)은 그 **활성(ACTIVE 우선, 없으면 최신) 버전의 엔진 `dsl` 원문을 그대로 보존**하며 `thresholdsByGrade`(및 base velocity `thresholds`)는 이 원문 운반으로 무손실 유지된다 — 변경은 `parameters`(평탄 키)만 갱신. **최초 저작(대상 코드에 버전 0건)**은 generic fallback(`type=and`/`cmp` 나열)을 합성하며 이 fallback 은 `velocity` 노드를 만들지 않으므로 `thresholds`/`thresholdsByGrade` 도 dsl 로 컴파일되지 않는다 — velocity·`thresholds` 를 포함한 **구조 DSL 저작은 aml-svc `POST /admin/aml/tm-scenarios` draft 전용**(원 PLAN Q6)이며 bo-api BFF generic 편집 경로로는 최초 저작할 수 없다 |

**평탄 parameters 왕복 계약(`ScenarioDslCodec`)** — `thresholdsByGrade`는 평탄 `parameters` 맵에서 키 인픽스 **`<key>.thresholds.<GRADE>`**(예 `minAmount.thresholds.HIGH`)로 왕복한다. `toParameters`가 등급별 오버라이드를 이 키로 평탄화하고, `decode`가 이 키들을 `CriterionField.thresholdsByGrade`로 복원한다(`parameters` key→value 계약 불변·additive). 오버라이드가 없으면 키 자체가 부재(하위호환 — 등급 없는 필드는 등급 없이 유지).

### 3.5 CaseDto (Admin, DB `aml_cases`)

| 필드 | 타입 | R(생성) | 설명 |
|---|---|---|---|
| `caseId` | string(uuid) | — | 응답 |
| `caseType` | enum | R | §5.8 case_type |
| `targetRef` | string | — | 대상(masked 식별자) |
| `status` | enum | — | §5.9 case_status |
| `priority` | enum | — | `LOW`/`MEDIUM`/`HIGH`/`URGENT` |
| `assignedTo` | string | — | 담당 분석가(로그인 이메일 — bo-web 담당자 선택 팝업이 디렉토리에서 고른 값) |
| `eddTrigger` | enum | — | §13.2 EDD trigger. 허용값 8종(DB §5.29 정본): `WLF_TRUE_MATCH`/`HIGH_RA_SCORE`/`HIGH_RISK_COUNTRY`/`UNUSUAL_TRANSACTION`/`COMPLEX_OWNERSHIP`/`TRADE_MISMATCH`/`CRYPTO_RISK`/`INTERNAL_OVERRIDE` |
| `originAlertId` | string(uuid) | — | **발단 alert**(알림→케이스 전환, DB `origin_alert_id`). GET 상세(`CaseDetail`)가 실값 응답 — 위임(엔진) 경로 유실 결함(run3 D5·D8) 해소 |
| `originScreeningId` | string | — | **발단 screening/RA 스코어 id**(RA→EDD 착수, DB §3.11 `origin_screening_id` **VARCHAR(96)·V15**, FK 아님·문자열 참조 토큰). GET 상세가 실값 응답 — 이 필드 부재로 `null` 하드코딩되던 케이스 상세 '발단' 유실(run3 D8) 해소. **(V72, PLAN 20260902-aml-case-workbench A1) A6 접두 토큰 규약**: 값은 `risk-score:<uuid>`(RA 스코어 발단) 또는 `screening:<uuid>`(WLF 스크리닝 발단)이며, **접두 없는 legacy 값은 `screening` 으로 하위호환 해석**한다(수동 생성 경로가 채운 원문 값). 컬럼 신설 없이 기존 슬롯을 재사용한다(새 컬럼 `originScoreId` 는 존재하지 않는다) |
| `originFdsCaseRef` | string | — | FDS 위임 발단 cross-ref(DB `origin_fds_case_ref`, `source_origin=FDS` 시 채움. fds-svc 역추적용, nullable) |
| `createdBy` | string | — | **(V72, PLAN 20260902-aml-case-workbench U2·U5)** 케이스 생성 행위자(예 `system:ra-engine`/`system:ra-onboarding`/`fds-svc`/요청 actor, 없으면 `system`). `CaseJpaEntity.createdBy`·`Case.createdBy` 1:1, 기존 컬럼(V1 baseline) 매핑 누락 보강 — 신규 컬럼 아님 |
| `timeline` | array<object> | — | 처리 이력(evidence). append-only, 항목 = `{kind, note, evidenceRefs[], actor, occurredAt}`. `kind` 는 조사 증적(`CREATED`/`NOTE`/`MEMO`/`EVIDENCE`/`STATUS_CHANGE`/`INVESTIGATION_NOTE`)과 **4-eyes 처분 증적**(`CLOSE_SUBMITTED`/`CLOSE_APPROVED`/`CLOSE_REJECTED`/`RELATIONSHIP_REJECT_SUBMITTED`/`RELATIONSHIP_REJECT_APPROVED`)을 함께 담는다 — 처분 증적은 엔진(`CddEddService`·`CaseManagementService`)이 상신·승인·반려 시점에 기록하며 `actor` 는 maker/checker, `note` 는 운영자가 입력한 사유 원문(없으면 생략)이다. 표시 라벨은 BO 프론트가 `kind` 코드를 메시지 카탈로그로 매핑한다(서버는 표시 문구를 생성하지 않는다). **(V72, PLAN 20260902-aml-case-workbench U3) 감사 타임라인 4종 추가** — `ASSIGNED`(note `<old>→<new>` 담당자)·`PRIORITY_CHANGED`(note `<old>→<new>` 우선순위)·`DUE_CHANGED`(note `<old>→<new>` ISO-8601 기한)·`CHECKLIST_ITEM`(note `<itemKey>:<status>`, 메모가 있으면 `" — " + note` 접미)은 `PatchCaseCommand`/체크리스트 갱신이 **실제로 변경된 필드마다** append하며(동일값 재요청은 0행), `kind` 카탈로그(F-033)에 additive로 편입된다. `CREATED` note 형식은 발단별로 고정 어휘다: 2차 RA 자동 개시 `EDD_TRIGGER=<trigger>`(evidenceRefs에 `risk-score:`/`alert:`/`txn:` 토큰), 알림 hand-off `ALERT_HANDOFF=<scenarioCode>;ACTION=<alertStatus>`(bo-api 전환 사유가 있으면 `;REASON=<reason>` 접미), FDS 위임 `FDS_DECISION=<fdsAction>`, 수동 생성 `MANUAL`(사유가 있으면 `MANUAL;REASON=<reason>` — BR-008 필수 사유가 여기에 영속), V72 backfill 소급 `EDD_TRIGGER=<trigger>;LINEAGE=BACKFILL_INFERRED;window=-60s..+5s`(actor=`system:migration`), **V73 확정 계보 소급**(CREATED 없는 레거시 케이스 — origin 컬럼 확정값이라 추정 아님, 화면 '추정' 배지 대상 아님) `ALERT_HANDOFF=<scenario_code>;ACTION=<alert.status>;LINEAGE=BACKFILL` / `FDS_DECISION=UNKNOWN;LINEAGE=BACKFILL` / `EDD_TRIGGER=<trigger>;LINEAGE=BACKFILL` / `SCREENING;LINEAGE=BACKFILL` / `MANUAL;LINEAGE=BACKFILL`(actor=`<created_by(≤118)>:migration`, created_at=케이스 생성 시각). `REASON=` 은 자유 문구라 항상 **마지막 필드**이며 파서는 첫 `REASON=` 이후 전체를 값으로 읽는다(길이는 bo-api `reason ≤1900` + note 2000 절단) — 전부 `KEY=VALUE` 고정 형식이며 자유 문구가 아니다. `evidenceRefs` 원소는 A6 참조 토큰(`alert:<uuid>`/`txn:<transactionRef>`/`screening:<uuid>`/`risk-score:<uuid>`/`report:<uuid>`/`approval:<uuid>`/`manifest:<sha256>`) 이며 **접두 없는 값은 `manifest`** 로 해석한다(origin_screening_id 문맥의 기본값 `screening` 과 다름에 주의) |
| `dueAt` / `closedAt` | string(date-time) | — | SLA·종결 |

`CreateCaseRequest`(수동 케이스 생성, `POST .../cdd/cases`): `{ caseType, targetRef?, priority?, assignedTo?, dueAt?, originAlertId?, originScreeningId?, eddTrigger?, actor?, reason? }` — `originAlertId`(알림→케이스 전환)·`originScreeningId`(RA→EDD 착수)·`eddTrigger` 는 발단 계보로 **생성→재조회에서 실값 영속**(run3 D5·D8, 전부 optional). `actor`(V72 additive)는 `TrustedActorResolver` 로 신뢰 경계를 통과한 값만 `createdBy`·`CREATED` 타임라인 `actor` 로 쓰인다(검증된 `X-User-Subject` 필수 — 없으면 400). `reason`(additive)은 `CREATED` note 에 `;REASON=<reason>` 로 영속된다(bo-api 는 화면 필수 사유를 그대로 위임).
`CaseCloseRequest`(🔒4-eyes): `{ resolution, reason, makerId }` → 결재 상신. `makerId`는 인증 principal과 같은지 확인하는 호환 assertion이며 서버는 인증 주체만 maker로 저장한다.
`CaseTimelineEntryRequest`: `{ kind, note, evidenceRefs[] }`.
`PatchCaseRequest`: `{ status?, assignedTo?, priority?, dueAt?, actor? }` — `actor`(V72 additive)는 위 감사 타임라인 4종의 `actor` 값.

**(V72, PLAN 20260902-aml-case-workbench U4·U5) `CaseWorkbenchDto`** (`GET .../cases/{caseId}/workbench` 응답, 엔진 record 필드 1:1): `CaseDetail` 필드(위 표) 전부 평탄화 + 아래 중첩 객체.

| 필드 | 타입 | 설명 |
|---|---|---|
| `lineage` | object | `{ alert, screening, score, fdsCaseRef, inferred }` — `alert`/`screening`/`score` 는 케이스의 origin 슬롯이 가리키는 것만 채워지고 나머지는 `null`. `alert={alertId,scenarioCode,alertType,severity,status,transactionRef,detectedAt,triggerDescription,ruleFamily,strReasonCode}`(설명 필드는 `evidence.trigger` 맵에서 파생, 없으면 `null`). `screening={screeningId(원문 토큰 string),status,score,matchedEntries[],reasonCodes[],transactionRef,decidedAt}` — UUID 파싱 실패·미존재 시 `screeningId` 만 남고 나머지 `null`(500 아님). `score={scoreId,modelCode,scenario("ONBOARDING"\|"ONGOING"),riskGrade,riskScore,mandatoryHighRisk,evaluatedAt,triggerAlerts[]}`. `inferred=true` 는 V72 backfill 로 채워진 '추정' 계보 `score.triggerAlerts[]={alertId,scenarioCode,transactionRef,severity}` — 점수 `factorBreakdown.triggerAlerts` 원소에서 파생하며 저장 키가 `ruleCode` 면 `scenarioCode` 로 폴백하고, `transactionRef` 는 없으면 `relatedAlerts`(alertId 일치)에서 보강한다. |
| `relatedAlerts` | array<object> | 대상의 관련 알럿(DB `LIMIT 50`, detectedAt DESC) — `{alertId,scenarioCode,alertType,severity,status,transactionRef,detectedAt,triggerDescription,origin}`. 회수(RETIRED) 제외, 최대 **50건**, 최신순. `origin=true` 는 발단 알럿이거나 `lineage.score.triggerAlerts` 포함 |
| `riskSummary` | object\|null | `{scoreId,modelCode,scenario,riskGrade,riskScore,mandatoryHighRisk,requiredAction,nextReviewDueAt,evaluatedAt}` — 정본 조회(`findOperativeForTarget`) 결과 없으면 `null` |
| `linkedReports` | array<object> | 연결 STR/CTR — `{reportId,reportType,status,submittedAt,fiuAckRef}` |
| `pendingApproval` | object\|null | 대기 4-eyes(`EDD_CLOSE`→`RELATIONSHIP_REJECT` 순 우선) — `{approvalId,subjectType,status,makerId,requestedFinalStatus,createdAt}`. 없으면 `null` |
| `relationships` | array<`RelationshipEdgeDto`> | 관계 그래프 에지(both direction) |
| `memberCases` | object | `{totalCases,openCases}` — 이 회원의 전체/열린 케이스 건수 |
| `checklistProgress` | object | `{checklistType,version,total,required,done,requiredDone,templateMissing}` |

**`CaseChecklistDto`** (`GET/PUT .../checklist(/{itemKey})`): `{checklistType, version, templateMissing, editable, items[], progress}` — `items[]`(`ChecklistItemView`) = `{itemKey,label,required,evidenceType,riskTrigger,status,note,evidenceRef,actor,updatedAt}`(미저장 항목은 `status="PENDING"`·`actor=null`). `editable = status ∈ {OPEN, INVESTIGATING}`. `PUT` body: `{status(PENDING\|DONE\|NOT_APPLICABLE), note?, evidenceRef?, actor?}` → 200 갱신된 `CaseChecklistDto`. `IllegalStateException`(비-editable) → 409 `AML.STATE_CONFLICT`, 템플릿 밖 `itemKey` → 400.

**`RelationshipEdgeDto`** (`GET .../relationships`): `{relationshipId, fromRef, toRef, relationshipType, ownershipPercent, ubo, direction("OUTBOUND"|"INBOUND")}` — 유효기간(`effectiveFrom`/`effectiveTo`)은 도메인(`Relationship`)·JPA 엔티티 미매핑으로 **범위 밖**(계획 리뷰 G5, DB DDL 에는 컬럼이 있으나 도메인 계층 부재).

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
| `amlcSubmissionRef` | string | — | **AMLC 포털 실 lodgement 접수번호**(DB `amlc_submission_ref`, V58, feature/aml-reports-amlc-migration §1.4-C) — `PlaywrightAmlcSubmissionAdapter`(브라우저 자동화)가 AMLC 포털에 직접 lodge 후 반환한 확인번호. `submittedRef`(제출 manifest 해시)와 값이 다르며 혼동 금지. 이중 lodge 방지(멱등) — 값이 non-null 이면 재상신 시 어댑터를 재호출하지 않는다 |
| `reportDeadlineAt` | string(date-time)\|null | — | **보고 기한(nullable freeze)** — 현재 코드로 확정·계산하는 정책은 PH AMLC뿐이다. `jurisdiction=PH`, `timezone=Asia/Manila`, cutoff가 NULL(레거시) 또는 정확히 `17:00`이면 `CTR`은 거래 시각, `STR`은 의심 트리거 시각을 anchor로 +5영업일 17:00 PHT를 DRAFT 개설 시 동결한다. 사유 누적/replay는 기한을 이동시키지 않는다. 다른 PH cutoff와 KR/AU/JP 등 비PH는 탐지·DRAFT를 보존하되 `null`로 응답하고 `AML.REPORT_DEADLINE_POLICY_UNCONFIGURED` 구조화 WARN을 남긴다. KR의 STR 승인+3영업일/CTR 거래+30일 서술은 정확한 cutoff·anchor·lifecycle 결선 전에는 서버가 추정 계산하지 않는다. 클라이언트도 null을 자체 계산으로 채우지 않는다. |
| `slaStatus` | enum | — | **SLA 상태(파생값, 설계서 §14.4)** — `ON_TIME`/`DUE_SOON`(D-3 이내)/`OVERDUE`. bo-web 화면 배지(D-3 경고·기한 초과 표시)에 사용. |

`ReportSubmitRequest`(🔒4-eyes): `{ makerId, reason, approvalLine: "REPORTING_OFFICER" }`.

`CaseLinkedStrDraftRequest`: `{ caseId }` → `RegulatoryReportDto`. 같은 case 재호출은 같은 STR draft를 반환하며 `(tenant_id,case_id)`당 STR 하나를 보장한다. 보고 상신의 `makerId`도 인증 principal과 일치해야 한다.

`ReportRejectRequest`/`ReportCancelRequest`(🔒4-eyes, §2.7 `:reject`/`:cancel`): `{ makerId, reasonCode(string ●, 사유 코드 필수), reason(string △), approvalLine: "REPORTING_OFFICER" }` — `:cancel`로 CTR 제외 처리(§14.3) 시 `ctrExemptionCode`(●) 병기. **종결(`REJECTED`/`CANCELLED`) 시 `reasonCode`는 `aml_regulatory_reports.closure_reason_code`(DB §3.12)에 영속**되어 미보고 사유 분포(§2.7 `unreported-reasons`)의 집계 원천이 된다(T4 AML-ENG-04 — **확정**).

`DelayBucket`(§2.7 `reports/stats/str-delay` 응답, T4 AML-ENG-04 — **확정**): `{ bucketCode(enum: ON_TIME/D1_3/D4_7/D8_14/D15_PLUS), label(string), count(long) }` — 5종 버킷 0-fill 고정 배열(분포 모양 안정). 보고 행·PII 미노출(집계 카운트만). 지연 기준은 legacy 운영 기준선(candidate `created_at` + **72 elapsed hours**) 대비 `submitted_at` 상대 일수다. 이는 관할별 법정 `reportDeadlineAt`과 별도이며, PH frozen dueAt이나 미확정 관할 기한을 대체·추정하지 않는다. SUBMITTED 미도달 건은 지연 모수에서 제외(미보고 사유 분포로 분류).

`UnreportedReason`(§2.7 `reports/stats/unreported-reasons` 응답, T4 AML-ENG-04 — **확정**): `{ reasonCode(string — `closure_reason_code` 코드값 또는 legacy 미영속 = `UNSPECIFIED`), count(long) }` — count 내림차순·reasonCode 사전순 정렬. 보고 행·PII 미노출.

`ReportDailyCount`(bo-api `GET /api/v1/bo/aml/stats/str|ctr` 응답 필드 `dailyTrend`, 2026-07-06 사용자 요청 반영): `{ date(LocalDate, yyyy-MM-dd), count(long), cumulativeCount(long) }` — `createdAt` 기준 기간 내 일별 보고 발생 건수와 조회 기간 누적 건수. 날짜 버킷은 요청 period(7d/30d/90d) 전체를 0-fill한다. STR은 기존 통계와 동일하게 COMPLIANCE 전담 role-gate 뒤에서만 산출하고, CTR은 열림. 보고 행·PII 미노출(집계 카운트만).

`ScenarioEffectiveness`(bo-api `GET /api/v1/bo/aml/stats/scenarios` 응답): `{ scope("TENANT"), period("7d"|"30d"|"90d"), scenarios(ScenarioRow[]), generatedAt(ISO-8601), cacheTtlSeconds(int, 45) }`.

`ScenarioRow`: `{ scenarioCode, scenarioName, alertCount, caseCount, reportCount, conversionRate, caseConversionRate, falsePositiveRate, relatedTxnCount, relatedTxnAmount, recommendation("KEEP"|"REVIEW"|"TUNE"), family("CTR"|"STR"), reasonCode, evaluationMode, actions[], naturalLanguage, source("BUILT_IN"|"CUSTOM"), conditions[], ruleMetaUnavailable(Boolean, nullable), strRestricted(boolean) }`. 앞의 집계 11필드는 TM 알림 lifecycle 실집계(BR-001/BR-004)이고, **`family` 이후 7필드는 룰 카탈로그 보강**이다(2026-08-06 신설, 시나리오 상세 화면이 룰 상세와 같은 발동 조건·임계를 보이게 하기 위함). 보강 근거는 **`scenarioCode` ≡ 룰 코드**다 — 알림 집계 어댑터가 알림 JSON 의 `ruleCode`(폴백 `aml_alerts.scenario_code` 칼럼, 둘 다 룰 코드)로 폴딩한다(§3.4a, v9.21). `conditions[]`는 **§3.6a `ReportRuleOverviewRow.conditions[]`와 동일 생산자**(BUILT_IN=resolved 카탈로그 파라미터, CUSTOM=safe DSL leaf)라 두 화면의 조건 문자열이 항상 일치한다. 카탈로그(CTR2·STR8)·설정형(`aml_configurable_report_rules`) 어디에도 없는 고아 `scenarioCode`는 보강 7필드와 `ruleMetaUnavailable`을 **모두 생략**한다(`@JsonInclude(NON_NULL)` — 합성·추정 금지). 반대로 설정형 룰 목록 조회가 실패하거나 엔진이 미가용해 고아 여부를 판정할 수 없으면 보강 7필드는 생략하되 **`ruleMetaUnavailable=true`만 additive로 내려보낸다**. CTR/STR 중 일부 family만 실패한 경우에도 성공 family에서 코드를 찾지 못하면 미확정으로 처리하고, 성공 family에서 코드를 찾으면 정상 메타를 우선한다. 어느 경우에도 효과성 집계 11필드는 계속 반환한다(보강 장애 강등). **STR tipping-off**: `family=STR` 룰의 보강 필드는 §2.7 `report-rules?family=STR`과 동일하게 준법감시 전담(COMPLIANCE) 한정이며, 비전담 호출자에게는 403 대신(집계 자체는 종전대로 제한 없음 — 계약 보존) 해당 행의 보강 6필드를 비우고 `strRestricted=true`만 내린다. 보고 행·PII 미노출(집계 카운트 + 룰 정의만).

#### 3.6a 룰군별 룰 개요 (bo-api AML-STAT, `GET /api/v1/bo/aml/stats/report-rules`)

`ReportRuleOverview`: `{ scope("TENANT"), family("CTR"|"STR"), period("7d"|"30d"|"90d"), rules(ReportRuleOverviewRow[]), generatedAt(ISO-8601), cacheTtlSeconds(int, 45) }` — CTR·룰 효과성 통계 메뉴는 `family=CTR`(CTR 룰 개요), STR·룰 효과성 통계 메뉴는 `family=STR`(STR 룰 개요)을 조회. `family=STR`은 STR 퍼널과 동일한 tipping-off 전담(COMPLIANCE) 게이트 — 비전담 `403 AML.FORBIDDEN_SCOPE`.

`ReportRuleOverviewRow`: `{ ruleCode, family("CTR"|"STR"), reportType, reasonCode, evaluationMode, actions, status, naturalLanguage, hitCount30d, draftCount, lastFiredAt, tuningRecommended, source("BUILT_IN"|"CUSTOM"), conditions[] }`. BUILT_IN은 카탈로그/라이브 보고 store, CUSTOM은 `aml_configurable_report_rules`와 실제 `aml_alerts.scenario_code` lifecycle 집계가 원천이다. 같은 custom 코드에 여러 버전이 있으면 **실제 평가 중인 ACTIVE를 우선 표시**하고, ACTIVE가 없을 때만 최신 DRAFT를 표시한다. `draftCount`는 **nullable** 이며 BUILT_IN·CUSTOM 이 **같은 기준**을 쓴다 — 엔진 위임 배치(알림 집계 소스 가동)에서는 보고 목록이 발동 룰코드를 싣지 않아 룰별 DRAFT 귀속이 구조적으로 불가능하므로 `null`(화면 '집계 불가'), 비위임(local/CI) 배치에서는 라이브 리포트 store `firedRules` 위 실집계다. **조용한 `0` 은 '발동한 초안 없음' 으로 오독되므로 금지**한다(한쪽만 0 이면 같은 열에서 판정 기준이 갈린다). **`tuningRecommended`는 BUILT_IN·CUSTOM 공통 알림 lifecycle 휴리스틱**(오탐률·케이스 전환율)으로 판정하며, 구 BUILT_IN `draftCount>=5` 기준은 폐기한다. `actions=["TM_ALERT"]`. `conditions[]`는 built-in resolved 파라미터 또는 custom safe DSL leaf를 표시한다.

**`RuleConditionView`**(`conditions[]` 원소 — §2.7 룰 상세 `ReportRuleView.conditions[]` 와 공용 leaf, FDS `RuleConditionView` 와 동형): `{ label, op, value, unit, paramKey }`. **`unit` 은 nullable** — 특히 CTR 조건행(카탈로그 단위 토큰 `{BASE_CCY}` 행, `CTR_SINGLE`·`CTR_DAILY`·`ctr_threshold` 파라미터 결합행)의 `unit` 은 **서버가 해석한 테넌트 기준(보고)통화 코드 또는 `null`**(미바인딩/해석 불가 — **PHP 폴백 금지**, 코드=truth bo-api `AmlReportRuleParamService#conditionViews`·`TenantCurrencyBindingService#reportingCurrencyOrNull`)이다. 클라이언트는 `unit=null` 을 "단위 무표기 + CTR 임계 편집 폼 미노출(미바인딩 안내)" 로 처리하고 기본 통화를 합성하지 않는다(기능정의서 §12-B.3 3-상태 렌더 규칙). `paramKey` non-null 행은 편집 파라미터에 결합된 행(값은 오버라이드 반영 resolved 현재값)이다.

BUILT_IN `conditions[]`는 aml-svc 평가 카탈로그의 조건 키·연산자·값을 그대로 투영한다. 특히 다음 행은 조사역이 화면 문자열대로 재현할 수 있어야 하며, 점수 행이 실제 boolean 게이트를 대신하지 않는다.

| ruleCode | 실제 발동 게이트 | `conditions[]` 표시 계약 |
|---|---|---|
| `STR_STRUCTURED` | 일 현금합산이 CTR 임계의 `[band_lower, band_upper)`에 들고 연속 영업일 수가 임계 이상 | `일 현금합산 밴드 하한 >= 0.90`, `일 현금합산 밴드 상한 < 0.99`, `연속 영업일 >= 3` |
| `STR_THIRD_PARTY` | `accountHolderNameMatch=false` 또는 명의인 토큰 ≠ 회원 identity 토큰 | `송금 명의 vs 회원 명의 = 불일치`(수치 유사도 임계 없음) |
| `STR_NO_PURPOSE` | pass-through·scatter funding·many-to-one·one-to-many 신호 합계 `>=2` | `목적부재/행동이상 신호 수 >= 2건`(단일 플래그만으로 미발동) |
| `STR_PEP` | judge 입력 `pep=true` | `PEP 명단 매칭 = TRUE` + `명단 매칭 점수 >= 0.92`(참고 지표·read-only) |
| `STR_SANCTION` | judge 입력 `sanctionHit=true` | `제재 명단 매칭 = TRUE` + `명단 매칭 점수 >= 0.92`(참고 지표·read-only) |

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
| `detail` | string\|null | 결재 상신 내용 요약. `CTR_THRESHOLD`는 `<currency> CTR 임계 변경 상신`, `REPORT_RULE_PARAM`은 `<ruleCode> CTR/STR 룰 파라미터 변경 상신` 형태로 파생한다. **`HIGH_RISK_REGISTRY`는 staged payload 에서 적용 결과 스냅샷 `v<version> · PRODUCT=n · VASP=n · HIGH_NET_WORTH=n · PEP_INDIVIDUALS=n · RA_HIGH_RISK_CUSTOMERS=n` 을 파생하며, 이 값만 `ApprovalSummary`(목록)에도 실린다** — 승인 히스토리(기능정의서 §12-B.6 ③)가 대상 `UPDATE|<version>` 만으로는 무엇이 바뀐 결재인지 식별하지 못하던 결함(감사 추적성) 해소. 파생 소스가 없는 subjectType·구 엔진 행은 `null`(화면 폴백 `-`). 문자열은 코드+숫자만이라 로케일 중립이다 |
| `changes` | array\|null | 결재 상세 변경 전→후 표. 원소 `{ label, before, after }`. `CTR_THRESHOLD`는 `tenant\|currency\|toAmount\|reason\|fromAmount`, `REPORT_RULE_PARAM`은 `tenant\|ruleCode\|afterPairs\|beforePairs` staged payload에서 AS-IS/TO-BE를 파생한다. |
| `submittedAt` | string(date-time)\|null | **상신일시**(DB §3.16 `created_at` 매핑, 신규 컬럼 없음·가정 G5). 결재함 정렬(desc) 기준. `null`=live 파생 subject(run3 D13) |
| `expiresAt` / `executedAt` | string(date-time) | 만료·실행(결재≠실행 분리). `expiresAt`=결재함 만료 임박 뱃지 원천(`null`=무기한, run3 D13). **`executedAt` 은 상세(`ApprovalDetail`)와 목록 요약(`ApprovalSummary`) 양쪽에 노출**한다(2026-08-05) — 승인 히스토리 화면(PRD §12-B.6 BR-004)의 '결재 시점' 컬럼이 상세 재조회 없이 목록만으로 4-eyes 증적(상신→결재)을 완결한다. 미실행 건은 `null` |

> **참조 리스트 변경 결재의 변경 요약 한계(코드=truth).** `HIGH_RISK_REGISTRY` 결재 행은 **변경 전 상태를 담지 않는다**(staged payload 는 적용 결과 참조 세트 전량). 따라서 추가/제거된 개별 `subjectRef` diff 는 결재 행만으로 산출할 수 없어 `detail` 은 **결과 스냅샷**을 싣고, 화면은 그 사실을 각주로 밝힌다. 리스트가 0건이 된 경우도 보이도록 전 `listType` 을 항상 포함한다(조용한 누락 금지). 저장 형식·`payloadHash` 무변경이라 기존 결재 행에도 소급 적용된다.

> **결재함 위임(엔진) 응답 parity(run3 D13, 코드=truth).** 엔진 `ApprovalController.{ApprovalSummary,ApprovalDetail}` 가 `submittedAt`(=`created_at`)·`expiresAt`·`stagedPayload`(Detail)를 응답하도록 결선해 위임 경로에서 상신일시·만료·변경내역·상신내용이 전부 `null` 로 내려와 정렬·만료 뱃지·변경 전후 표가 무력화되던 결함을 해소한다. stub↔엔진 위임 응답 모양 동형(불변식). 승인 히스토리·결재함이 **목록만으로** 4-eyes 증적(상신자·승인자·상신/결재 시점)과 **변경 요약**을 완결하도록 `ApprovalSummary` 는 `executedAt` 과 `detail` 을 함께 싣는다(bo-api `ApprovalView.detail` 로 그대로 통과).

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
| `kycEvidence` | object | KYC checklist current-state(DB `kyc_evidence` JSONB, 원문 아님) — `{ occupation, sourceOfFunds, declaredIncomeOperator, declaredIncomeAmount, declaredIncomeCurrency, declaredIncomePeriod, declaredIncomeBand, kycLevel, residenceCountry, kycVerifiedAt }`(숫자 신고 4키는 2026-08-16 추가, 신고한 경우에만 존재). `declaredIncomeBand` 출력은 canonical 입력 4종에 더해 내부 projection sentinel `UNKNOWN`이 가능하다(입력 enum 확장 아님). 단 **숫자로 신고한 회원에게는 `UNKNOWN` 을 부여하지 않는다** — 소득을 어떤 형태로도 신고하지 않았을 때만 미상이다(2026-08-16). raw amount-key presence가 있으나 numeric tuple이 malformed/null/blank라 공개 숫자 4키가 모두 null이어도 internal marker는 공개하지 않고 `declaredIncomeBand=null`로 투영해 finite band 재폴백을 막는다. `kycVerifiedAt`은 §4.3 실사 완료 시점으로 ISO-8601 문자열을 verbatim 반영(파싱·재포맷 없음, 비-PII) |
| `nextReviewDueAt` | string(date-time) | 주기적 재확인 예정(DB `next_review_due_at`) |
| `nationality` | string\|null | CDD에서 보존한 PII-safe ISO 국적 코드 |
| `country` | string\|null | 고객 원장의 ISO 국가 코드 |
| `onboardingAt` | string(date-time)\|null | AML 고객 원장 최초 온보딩 시각 |
| `registeredAt` | string(date-time)\|null | 소스 시스템 등록 시각(CDD canonical projection) |
| `birthYearMasked` | string\|null | 마스킹 생년(`YYYY-**-**` 형식, 20260720 실값 계약). CDD 인입 시 canonical `dob` 선두 4자리(연도, `1900..현재연도` 검증)를 `kyc_evidence.birthYear` 로 파생·영속해 조립. 해당 projection이 없으면 null이며 raw vault 값으로 합성하지 않음(월·일·원문 dob 미노출) |
| `genderMasked` | string\|null | 고정 마스킹 토큰 `"***"`(20260720 추가) — vault 에 해당 고객의 성별 필드가 존재할 때만 값, 존재 여부만 확인하고 복호화하지 않는다. 원문 성별은 read model 에 비영속·비노출, 열람은 기존 `GENDER` PII-reveal 감사 경로(§1.6)로만 |
| `isPep` | boolean | **PEP(정치적 주요인물) 여부**(DB `aml_customers.is_pep`, V24). 경영진 승인(`PEP_APPROVAL`) EXECUTED 시 TRUE. TRUE면 `riskGrade`=HIGH 강제 상향(거래 허용+EDD) |
| `pepApprovalStatus` | enum\|null | 진행 중/확정 `PEP_APPROVAL` 결재 상태(`SUBMITTED`/`EXECUTED`/`REJECTED`, 미상신=null). 결재함(§3.7 ApprovalDto)에서 파생 |
| `pepApprovalId` | string(uuid)\|null | PEP 확정 결재 증거 링크(DB `aml_customers.pep_approval_id`, 마스킹 불요·식별 PII 아님). 비-PEP은 null |
| `latestScreening` | object | 최신 screening 결과 요약(`screeningId·status·riskGrade`) |
| `latestRiskScore` | object | **stage-aware operative** RA 결과 요약(`scoreId·riskScore·riskGrade·evaluatedAt`) — §2.3 `GET .../risk` 와 **동일 operative 선정**(상시평가(ONGOING) 점수가 이력에 있으면 최신 ONGOING, 없으면 최신 온보딩(ONBOARDING); 온보딩 모델 재평가(system 재점수)가 프로필을 1차 점수로 되돌리지 않음, PLAN 20260722-ra-tm-2nd-stage-fixed-scenario-consistency). 프로필 `riskSummary` ↔ RA 상세(§3.3) 점수/등급 **단일 정본**(`EvidenceTimelineService#customerProfile` → `AssessRiskUseCase#findOperativeForTarget`). 위 §3.9 후주 `riskGrade` 폴백 체인은 이 operative 점수 행 기준으로 그대로 적용 |
| `createdAt` | string(date-time) | |

> raw PII(이름·주민번호·여권번호 원문) 미노출. 식별은 `customerRef`(토큰), 매칭 보조는 `*Hash`만(DB §2.2). PII 원문 접근은 `aml:pii:reveal` scope+감사 필요(§1.6).
>
> **bo-api 화면 aggregate `CustomerProfile.riskSummary.mandatoryHighRisk`(당연고위험) 파생(run5 #3).** 위 엔진 evidence `CustomerProfileDto` 는 mandatory(당연고위험 강제 상향) 필드를 싣지 않는다. bo-api 프로필 화면 aggregate(`GET /api/v1/bo/aml/customers/{ref}/profile`)는 동일 위임 컨텍스트의 RA read(`GET /aml/customers/{ref}/risk` → `RiskScoreResponse.{mandatoryHighRisk, mandatoryHighRiskReasons, forcedFloorEvidence}`, §3.3)를 재사용해 `riskSummary.mandatoryHighRisk`(**boolean\|null**) 를 합성한다 — `isPep=true` 면 사유에 `PEP` 포함, RA read 실패 시 `null`(미상, `false` 단정 금지). stub(비운영) 경로는 RA stub 을 단일 소스로 하여 프로필 등급·사유·재확인주기가 RA 상세(§3.3)와 일치한다(PEP 승인·RISK_OVERRIDE 폐루프 양 read 동형, run5 #4).
>
> **bo-api 화면 aggregate `CustomerProfile.riskSummary.riskGrade` 등급 폴백 체인(코드=truth, `AmlCustomerProfileService#resolveGrade`, v9.46).** bo-api 프로필 화면 aggregate 의 `riskSummary.riskGrade` 는 엔진 profile 의 top-level `riskGrade`(위 표 §CustomerProfileDto `riskGrade`) 를 그대로 쓰지 않고 **폴백 체인 — ① top-level `riskGrade` → ② `latestRiskScore.riskGrade`(§CustomerProfileDto `latestRiskScore` 요약) → ③ `LOW`** 로 해소한다. 엔진 evidence profile 이 top-level `riskGrade` 를 **null/blank 로 내리는 계약**(실측)이라 top-level 만 매핑하면 등급이 `LOW` 로 기본값 처리되는 반면 `riskScore` 는 `latestRiskScore.riskScore`(예 `85.39`)를 그대로 써서, `riskSummary` 가 `(riskGrade=LOW, riskScore=85.39)` 로 **모순**되던 결함이 있었다(같은 회원의 `GET .../risk`(§3.3)는 HIGH). 폴백은 top-level 부재 시 **최신 RA 점수 행의 등급으로 내려가** `riskScore`↔`riskGrade` 두 필드를 **동일 소스(최신 RA 점수 행)에 정렬**한다. **① top-level·② latest 가 둘 다 부재(null/blank)할 때만** 최종 `LOW` 기본값을 쓴다(상위 요구서 미정의 지점 — **가정 A4로 진행: 코드=truth**). bo-api 는 등급 코드값을 재해석하지 않고 passthrough(FE i18n 라벨) — 폴백은 **소스 선택**일 뿐 vocab 변환이 아니다.
>
> **bo-api 화면 aggregate `CustomerProfile.person` PERSON 분기 매핑(20260720 — CDD 1차 RA 가시화).** bo-api 프로필 aggregate 는 엔진 evidence profile 의 flat `birthYearMasked`·`genderMasked`(위 표)를 `subjectType=PERSON` 일 때 `person.birthYearMasked`·`person.genderMasked` 로 pass-through 한다(재해석·복호화 없음). `person.genderMasked`는 `MaskedCell field="GENDER"` reveal 대상(기존 §1.6 감사 경로), `person.birthYearMasked`는 원문 dob 미노출·연도만. 엔진이 신규 필드를 싣지 않는 구 계약 응답이면 `null`(합성 금지). top-level `country`(위 표) 는 PERSON/ENTITY 공통 원장 거주국으로 aggregate top-level `CustomerProfile.country` 에도 동일하게 pass-through 한다(ENTITY 는 기존 `nationality` 슬롯 유지). `kycEvidence.kycVerifiedAt`(위 표) 도 aggregate `kycEvidence.kycVerifiedAt` 로 동일 verbatim pass-through.
>
> **bo-api `UNKNOWN` pass-through와 소득 배율.** 엔진 `kycEvidence.declaredIncomeBand=UNKNOWN`은 BO aggregate에도 그대로 전달되고 Java/read model의 `transactionActivity.incomeMultiple`은 `null`이다. 기존 `@JsonInclude(NON_NULL)` producer JSON에서는 이 component key를 생략한다. bo-web consumer는 key 생략과 explicit null을 모두 “배율 산출 불가”로 처리한다. `UNKNOWN`에는 band 상한이 없으므로 월평균 거래액을 나눌 분모를 합성하지 않는다. 화면은 이를 정상/정합 배율로 오인하지 않고 배율을 표시하지 않으며, band 자체는 등록된 ko/en 라벨(`미상`/`Unknown`)로 표시한다.

> **bo-api `transactionActivity.incomeMultiple` numeric-first 계약(2026-08-17, 코드=truth).** BO aggregate는 기존 공개 `kycEvidence` 숫자 4키(`declaredIncomeOperator`/`declaredIncomeAmount`/`declaredIncomeCurrency`/`declaredIncomePeriod`) 중 하나라도 있으면 공유 `DeclaredIncomePolicy`로 숫자 tuple을 해석한다. incomplete·malformed·하한-only 또는 activity currency 불일치는 `incomeMultiple=null`이고 legacy band로 폴백하지 않는다. **네 키가 모두 없을 때만** legacy band 상한을 사용한다. 유한 양수 resolution·양수 `monthlyAvgAmount`·같은 currency일 때만 `monthlyAvgAmount / declaredIncomeMonthly`를 scale 2 HALF_UP으로 계산한다. DTO/JSON key 추가는 없으며, 기존 `incomeMultiple` nullable·`NON_NULL` 생략 계약은 불변이다.
> raw amount key가 존재했지만 public 숫자 4키가 모두 null이 된 malformed/null/blank 신고는 엔진이 internal marker를 공개하지 않는 대신 `declaredIncomeBand=null`로 투영한다. 따라서 이 경우도 BO의 legacy band 조건을 충족하지 않아 `incomeMultiple=null`이며, marker용 공개 DTO/JSON key는 추가하지 않는다.

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

### 3.16a CurrencyProfile* DTOs — 기준통화 프로파일 카탈로그/현황/apply (bo-api 소유, 다통화 PLAN 20260818, U5/U13)

> bo-api 전용 엔드포인트 4종(§9 표) — `GET /api/v1/bo/aml/currency-profiles`, `GET /api/v1/bo/aml/tenants/{tenantId}/currency-binding`, `GET /api/v1/bo/aml/tenants/{tenantId}/currency-profile`, `POST /api/v1/bo/aml/tenants/{tenantId}/currency-profile:apply`. scope `aml:admin:policy`(화면 접근 게이트). `{tenantId}` 경로는 `"current"` 별칭(ambient `Tenant-Id`)을 허용하며, 명시 tenantId 가 ambient 테넌트와 다르면 `400 AML.BAD_REQUEST`(교차 테넌트 오염 차단). `apply` 의 FDS 축 저작(규제통화 전환·룰 파라미터 상신)은 화면 게이트와 별개로 FDS capability 게이트를 추가로 통과해야 한다(아래 참조).

**`CurrencyProfileView`**(`GET /currency-profiles` 배열 원소, repo `config/currency-profiles/*.json` bundled read-only 카탈로그):

| 필드 | 타입 | 설명 |
|---|---|---|
| `code` | string | 프로파일 코드(예: `php`, `krw`) |
| `baseCurrency` | string | ISO 4217 기준통화 |
| `jurisdiction` | string | 관할 코드(ISO 3166-1 alpha-2) |
| `timezone` | string | IANA timezone |
| `ctrThresholdAmount` | number | CTR 법정 임계(원본 JSON 문자열 scale 보존) |
| `roundingUnit` | integer | FDS 파생 금액 반올림 단위 |
| `reportCutoffTime` | string(HH:mm) | 법정 보고 마감시각. 미확정 프로파일은 null |
| `complianceReview` | enum | `CONFIRMED` / `PROVISIONAL` |
| `thresholdBasis` | string | 임계 산정 근거 설명 |
| `amountFeatureKey` | string | FDS 룰 DSL 참조 금액 피처 키 — `baseCurrency=="PHP"` 면 `transaction.phpEquivalent`, 그 외는 `transaction.baseEquivalent` |
| `derivedFdsAmounts` | map<string,number> | 룰코드 → 파생 금액 임계(ratio × CTR 임계, HALF_EVEN 반올림) |

**`GET /tenants/{tenantId}/currency-binding`** — raw 바인딩 read-back 프록시(aml-svc `GET .../policy-binding` 위임, §2.7). 응답 `{ bound: boolean, binding: TenantCurrencyBinding | null }` — 미바인딩(엔진 422)이면 `bound=false, binding=null`.

**`ApplyRequest`**(`POST .../currency-profile:apply` 요청): `{ profileCode: string, reason?: string }`. `profileCode` blank/미등재/번들 부재 시 `400 AML.BAD_REQUEST`(STEP 미실행·상신 0·감사 미기록).

**`ApplyStepResult`**(steps[] 원소 — 코드만, 안내 '문장' 없음. `engineMessage` 는 developer-only·화면 미표시):

| 필드 | 타입 | 설명 |
|---|---|---|
| `step` | enum | `FDS_REGULATORY_CURRENCY` / `BINDING` / `CTR_THRESHOLD` / `REPORT_RULES` / `FDS_RULES` — **나열 순서 = 실제 방출 순서**(코드=truth `CurrencyProfileApplyService#apply`; STEP 순서 = 배열 순서 정본). `FDS_REGULATORY_CURRENCY` 는 규제통화 전환 게이트가 발동한 pass 에만 선두 방출되며, **미실행 STEP 은 `steps[]` 에 포함되지 않는다**(예: 조기 종결 pass 는 `BINDING` 1건만 응답) |
| `status` | enum | `APPLIED` / `SUBMITTED` / `SKIPPED` / `PENDING` / `NOT_APPLICABLE` / `NOT_FOUND` / `AMBIGUOUS` / `BLOCKED_HISTORY` / `DEFERRED`(reasonCode `CTR_GAP_FAIL_CLOSED`·`FDS_CURRENCY_PENDING`) / `FEATURE_KEY_MISMATCH` / `CURRENCY_MISMATCH` / `FAILED`(reasonCode **8종**: `POLICY_PACK_UNRESOLVED`·`POLICY_PACK_AMBIGUOUS`·`BIND_REJECTED`·`ENGINE_UNAVAILABLE`·`PARAM_KEY_UNRESOLVED`·`FDS_TENANT_ABSENT`·`FDS_AUTHORITY_MISSING`·`ENGINE_REJECTED` — DEFERRED 사유 2종과 합쳐 bo-web `lib/currency-profile.ts` `CurrencyProfileApplyReasonCode` 유니온 10종과 1:1) / `FAILED_RANGE`. 다중키 `FDS_RULES` STEP 은 룰코드별 결과를 `params`(`"GATE-01"→"SUBMITTED"`, `"GATE-01.approvalId"→"…"`)에 접어넣고 `status` 는 worst-case rollup(`FAILED` > `AMBIGUOUS`/`FAILED_RANGE` > `SUBMITTED` > `SKIPPED`/`NOT_FOUND`/`NOT_APPLICABLE`). `PARAM_KEY_UNRESOLVED` 는 `FDS_RULES` 룰키 결과에서 대상 룰의 편집 파라미터 키를 해석하지 못한 경우다 |
| `reasonCode` | string | nullable |
| `params` | map<string,string> | nullable |
| `approvalId` | string | nullable(상신된 경우) |
| `engineErrorCode` | string | nullable |
| `engineMessage` | string | nullable, developer-only |

**FDS 저작 가드(r12 — apply 는 화면 게이트와 별개로 FDS capability 를 추가 검사한다)**: `STEP FDS_REGULATORY_CURRENCY` 상신은 `SFDS_TENANT:ADMIN`(+ 플랫폼/수퍼 역할), `STEP FDS_RULES` 상신은 `SFDS_RULE:OPERATE` 를 요구한다. 미보유 시 해당 STEP 만 `FAILED(FDS_AUTHORITY_MISSING)` 로 fail-closed(다른 STEP 은 계속 진행). 읽기(`GET .../currency-profile` 현황)는 이 게이트를 거치지 않고 `aml:admin:policy` 만으로 판정한다.

**`ApplyResponse`**(`POST .../currency-profile:apply` — 항상 `200`, 실패는 STEP 단위): `{ tenantId, profileCode, steps: ApplyStepResult[], warnings: string[] }`.

**apply `warnings[]` 코드 열거(방출 전체 집합 — 코드=truth `CurrencyProfileApplyService` 상수·add 지점, 자유 서술 문자열 없음)**:

| 코드 | 방출 조건 |
|---|---|
| `CTR_REPORTING_GAP:{ccy}` | 게이트 pass(최초 바인딩·통화 변경)에서 기존 CTR 임계 행이 프로파일 임계와 불일치 — `STEP BINDING` 은 `DEFERRED(CTR_GAP_FAIL_CLOSED)` 동행 |
| `CONFIGURABLE_AMOUNT_RULE:{family}:{ruleCode}` | 금액 피처(`*.phpEquivalent`/`*.baseEquivalent`) leaf 를 참조하는 **ACTIVE 설정형(CTR/STR) 룰** 은 apply 가 자동 갱신하지 않음 — 수동 점검 대상을 룰별로 방출(`STEP REPORT_RULES`) |
| `CONFIGURABLE_RULES_UNCHECKED` | 설정형 룰 목록 조회 실패로 위 금액 피처 점검 자체를 수행하지 못함(`STEP REPORT_RULES` 는 `NOT_APPLICABLE` 유지) |
| `CTR_PENDING_DIVERGENT` | `CTR_THRESHOLD` 대기 상신(`PENDING`)의 스테이징 금액이 프로파일 임계와 다름 |
| `CALENDAR_UNPROVISIONED` | 바인딩 반영 후 read-back 의 `calendarCoverage=MISSING`(관할 영업일 캘린더 미적재) |
| `FDS_REGULATORY_CURRENCY_MISMATCH` | FDS 규제통화가 프로파일 기준통화와 불일치(매 pass 진단 — 게이트 pass 에서만 차단성) |
| `FDS_REGULATORY_CURRENCY_UNSET` | FDS 규제통화 legacy NULL(비차단) |
| `FDS_CURRENCY_APPLIED_BINDING_PENDING` | 2-pass 전환 중간 창 — FDS 규제통화는 이미 프로파일 통화로 EXECUTED, AML 바인딩은 미완결(FDS 금액 룰 무발동 구간) |
| `PACK_PROFILE_DIVERGENCE` | 통화 프로파일 팩 배포 테넌트가 REST 규제통화 전환을 상신 — 라이브 상태가 팩 JSON 정본과 영구 이격(§7 Q17 r11) |

> `StatusResponse.warnings` 의 `STATUS_SOURCE_UNAVAILABLE:{소스}` 는 **현황 조회 전용** 코드로 apply 응답에는 방출되지 않는다(집합 분리).

**`StatusResponse`**(`GET .../currency-profile` — 항상 `200`. 모든 top-level 키가 항상 존재하며, 조회 불가한 소스는 명시적 `null` + `STATUS_SOURCE_UNAVAILABLE:{소스}` warning 으로 투영한다 — 오판정 방지):

| 필드 | 타입 | 설명 |
|---|---|---|
| `tenantId` | string | — |
| `bound` | boolean\|null | `true`/`false`(미바인딩, 엔진 422 read-back)/`null`(판독 불가) 3-상태 |
| `binding` | `TenantCurrencyBinding`\|null | AML 바인딩(§2.7 raw read-back) |
| `ctrThresholds` | array | `CtrThresholdStatusRow[]{ currency, amount, updatedAt, activeForReporting }` — `activeForReporting`=현재 reporting currency 행 여부(구 통화 임계 잔존 행은 false) |
| `ctrPendingApprovalId` | string\|null | CTR_THRESHOLD 상신 대기 approvalId |
| `fdsRegulatoryCurrency` | string\|null | FDS 엔진 `regulatoryCurrency`(§2.7 compliance GET 위임) |
| `fdsRegulatoryCurrencyMatchesBinding` | boolean\|null | AML 바인딩 `baseCurrency` 와 일치 여부 |
| `fdsRegulatoryCurrencyPendingApprovalId` | string\|null | `TENANT_REGULATORY_CURRENCY` 상신 대기 approvalId |
| `fdsRules` | array | `FdsRuleStatusRow[]{ ruleKey, resolution, ruleId, name, featureKeyMatched, currencyMatched, currentAmount, derivedAmount, drifted, pendingApprovalId, paramReadFailed }` — 6종 고정 `_ratios.json` 키. `resolution` 값 집합 = `MATCHED`/`NOT_FOUND`/`AMBIGUOUS`(bo-web `FdsRuleStatusResolution` 유니온 1:1 — `ruleId`·`name` 등 룰 결합 필드는 `MATCHED` 시만 non-null). `getParams` 조회 실패는 원소 단위 `paramReadFailed=true`(소스 단위 warning 미병기) |
| `profileAlignment` | array | `ProfileAlignmentRow[]{ profileCode, bindingMatched, ctrMatched, fdsRulesMatched }` — 카탈로그 프로파일별 현재 테넌트 상태 정렬 일치 여부 |
| `warnings` | array<string> | 코드(+콜론 파라미터) 형식만. `STATUS_SOURCE_UNAVAILABLE:{AML_BINDING\|AML_CTR\|FDS_COMPLIANCE\|FDS_RULES}`(해당 소스 판독 불가 — 이 경우 `FDS_REGULATORY_CURRENCY_UNSET` 은 함께 병기하지 않는다), `FDS_REGULATORY_CURRENCY_UNSET`(legacy NULL — 비차단), `PACK_PROFILE_DIVERGENCE`(팩 배포 테넌트가 REST 로 전환됨), `FDS_CURRENCY_APPLIED_BINDING_PENDING`(2-pass 전환 중간 창 — FDS 규제통화 EXECUTED 후 AML 바인딩 완결 전 구간, FDS 금액 룰 무발동) |

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

**Device**(`device`, `DeviceDto` — `docs/aml-data.md` §4.5, PLAN 20260717, 사용자 지시로 F-005 해제):

| 필드 | 타입 | R | 설명 |
|---|---|---|---|
| `deviceId` | string(≤64) | — | 디바이스 식별자(제어문자 금지, 422) |
| `os` | string(≤64) | — | 디바이스 운영체제. 설정형 룰 피처 `device.os` |
| `version` | string(≤64) | — | 디바이스 앱/OS 버전. 설정형 룰 피처 `device.version` |
| `ip` | string(≤64) | — | 접속 IP(준식별자, 원값 저장). 설정형 룰 피처 `device.ip` |
| `locale` | string(≤16) | — | 디바이스 로케일(BCP-47, 예 `zh-CN`, 제어문자 금지, 422). 설정형 룰 피처 `device.locale`. FDS `DeviceDto.locale`(01-fds-api.md §5.1)과 동형 확장(PLAN 20260717 U-A1, 사용자 지시로 F-005 해제) |

비-null 필드만 flat payload `device` 서브트리에 기록되며(`NeutralTransactionEventService#addDeviceSignals`, `externalSignals` 결선과 동형), 재시도 경로(`FanoutRetryService`)에서도 동일 서브트리가 복원된다. `deviceId`/`os`/`version`/`ip`/`locale` 5키는 `ConfigurableRuleDslPolicy.SCALAR_FEATURES`에 등록되어 **설정형**(family CTR/STR) 룰만 조건 피처로 소비할 수 있다 — 법정 CTR2·STR8 카탈로그 룰은 불변. `NeutralDevice` 도메인 record 는 `(deviceId, os, version, ip, locale)` 5-컴포넌트로 확장됐으며, 기존 4-인자 생성자는 하위호환용으로 유지(`locale=null` — 잠금 테스트 `DeviceSignalsIngestParityIntegrationTest` 무수정 컴파일 보장). FDS 인입(01-fds-api.md §5.1 device 공통 블록)과 동형 계약.

> **customer.ageYears 설정형 피처(코드=truth, PLAN 20260717 U-A1 — 가정 A2, 사용자 지시로 F-005 해제).** `originator.dateOfBirth`(ISO-8601 `yyyy-MM-dd`)를 이벤트 시점(occurredAt) 기준 만 나이로 파생해 설정형 룰 피처 `customer.ageYears`(`ConfigurableRuleDslPolicy.SCALAR_FEATURES`)로 노출한다. FDS `customer.ageYears`(01-fds-api.md)와 동형 파생 — **DOB 원문은 AML 도 미영속·즉시 폐기**(F-005 계약 유지, 파생 정수만 사용). DOB 부재·형식 위반 시 미노출(fail-safe). 법정 CTR2·STR8 카탈로그 룰은 불변(설정형 룰만 소비 가능).

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
| 400 | `AML.VALIDATION_ERROR` | policy-binding 등 application validation 실패(예: 필수 IANA region timezone null·blank·invalid/fixed-offset). endpoint별 상세 계약을 따른다 |
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
| 503 | `AML.SCREENING_UNAVAILABLE` | WLF 엔진 장애·PII reveal 역참조 실패·**필수 source readiness 미충족(P0-06, fail-closed 게이트)**·**후보 recall SQL timeout**. readiness 미충족 시 `details`에 7종 사유코드(`NO_MANDATORY_POLICY`/`NO_READY_SOURCE`/`MISSING_SOURCE`/`NOT_READY`/`STALE`/`FAILED`/`NOT_APPLICABLE_UNAPPROVED`), 후보 timeout 시 별도 `CANDIDATE_QUERY_TIMEOUT`(§2.2) — 둘 다 `NO_MATCH`/일반 500 대신 fail-closed |
| 409 | `AML.TENANT_DEPLOYMENT_MODEL_IMMUTABLE` | `deploymentModel` 직접 PUT 변경 시도(온보딩 흐름만 허용) |
| 404 | `AML.TENANT_NOT_FOUND` | 대상 tenant 없음(§5 OpenAPI paths·PRD 부록 D 정합) |
| 422 | `AML.TENANT_POLICY_UNBOUND` | **테넌트 관할·통화·시간대·Policy Pack revision 바인딩 누락/충돌(P0-16, `TenantPolicyUnboundException`)** — jurisdiction/base_currency/reporting_currency/timezone/policy_pack_code/policy_pack_version 미설정, timezone invalid/fixed-offset, 핀 Policy Pack revision 미존재, 또는 비-effective(비-ACTIVE·effective_from 미도달) revision. 중립 인입(`POST /aml/v1/transaction-events`)·policy-binding upsert(§2.7)에서 fail-closed — 구 service-global PH/PHP/Manila 기본으로 조용히 오귀속(오보고·미탐)하지 않고 거부한다 |
| 422 | `AML.TENANT_CURRENCY_HISTORY_LOCKED` | **거래성 canonical 이벤트 보유 테넌트의 기준통화(`baseCurrency`) 변경 거부(다통화, PLAN 20260818)** — `PATCH .../tenants/{tenantId}/policy-binding`(§2.7)이 기존 바인딩 대비 `baseCurrency` 를 바꾸려 할 때, 해당 테넌트에 거래성 canonical 이벤트가 이미 존재하면 fail-closed 로 거부한다(단일 통화 윈도우 보호 — 이력 있는 테넌트의 통화 소급 변경은 CTR/STR 임계·FX 해석을 소급 오염시킨다). `baseCurrency` 외 필드(`reportingCurrency`/`timezone`/`policyPackVersion`) 변경은 이력과 무관하게 허용 |
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
        requestName: { type: string, nullable: true, description: 'WLF 읽기 한정 요청 nameTokens 순서 보존 스냅샷; aml:case:read에만 반환' }
        matchedEntryNames:
          type: object
          nullable: true
          additionalProperties: { type: string }
          description: 'WLF 읽기 한정 entryId→현재 게시본 명단 기재명; aml:case:read에만 반환'
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
    CurrencyProfileView:
      type: object
      description: '기준통화 프로파일 카탈로그 원소(§3.16a) — repo config/currency-profiles/*.json bundled read-only'
      properties:
        code: { type: string, example: php }
        baseCurrency: { type: string, example: PHP }
        jurisdiction: { type: string, example: PH }
        timezone: { type: string, example: Asia/Manila }
        ctrThresholdAmount: { type: number }
        roundingUnit: { type: integer }
        reportCutoffTime: { type: string, nullable: true, example: '17:00' }
        complianceReview: { type: string, enum: [CONFIRMED, PROVISIONAL] }
        thresholdBasis: { type: string }
        amountFeatureKey: { type: string }
        derivedFdsAmounts: { type: object, additionalProperties: { type: number } }
    TenantCurrencyBinding:
      type: object
      description: 'aml-svc raw policy-binding read-back 투영(§2.7 GET .../policy-binding, 12키)'
      properties:
        tenantId: { type: string }
        jurisdiction: { type: string }
        baseCurrency: { type: string }
        reportingCurrency: { type: string }
        timezone: { type: string }
        policyPackCode: { type: string }
        policyPackVersion: { type: string }
        policyPackEffectiveFrom: { type: string, format: date-time, nullable: true }
        reportCutoffTime: { type: string, nullable: true }
        calendarCoverage: { type: string, enum: [PRESENT, MISSING] }
        policyPackResolved: { type: boolean }
        transactionalHistory: { type: boolean }
    CurrencyProfileApplyRequest:
      type: object
      required: [profileCode]
      properties:
        profileCode: { type: string }
        reason: { type: string, nullable: true }
    CurrencyProfileApplyStepResult:
      type: object
      properties:
        step: { type: string, enum: [FDS_REGULATORY_CURRENCY, BINDING, CTR_THRESHOLD, REPORT_RULES, FDS_RULES], description: '나열 순서 = 실제 방출 순서(미실행 STEP 은 steps[] 미포함, §3.16a)' }
        status: { type: string, enum: [APPLIED, SUBMITTED, SKIPPED, PENDING, NOT_FOUND, AMBIGUOUS, NOT_APPLICABLE, DEFERRED, FEATURE_KEY_MISMATCH, CURRENCY_MISMATCH, BLOCKED_HISTORY, FAILED, FAILED_RANGE] }
        reasonCode: { type: string, nullable: true }
        params: { type: object, additionalProperties: { type: string }, nullable: true }
        approvalId: { type: string, nullable: true }
        engineErrorCode: { type: string, nullable: true }
        engineMessage: { type: string, nullable: true, description: developer-only(화면 미표시) }
    CurrencyProfileApplyResponse:
      type: object
      properties:
        tenantId: { type: string }
        profileCode: { type: string }
        steps: { type: array, items: { $ref: '#/components/schemas/CurrencyProfileApplyStepResult' } }
        warnings: { type: array, items: { type: string }, description: '§3.16a apply warnings 코드 집합 9종(콜론 파라미터형 CTR_REPORTING_GAP:{ccy}·CONFIGURABLE_AMOUNT_RULE:{family}:{ruleCode} 포함) — 자유 서술 문자열 없음' }
    CurrencyProfileStatusResponse:
      type: object
      description: '§3.16a — 모든 top-level 키가 항상 존재(조회 불가 소스는 null + STATUS_SOURCE_UNAVAILABLE warning)'
      properties:
        tenantId: { type: string }
        bound: { type: boolean, nullable: true }
        binding: { $ref: '#/components/schemas/TenantCurrencyBinding' }
        ctrThresholds:
          type: array
          items:
            type: object
            properties:
              currency: { type: string }
              amount: { type: string }
              updatedAt: { type: string, format: date-time }
              activeForReporting: { type: boolean }
        ctrPendingApprovalId: { type: string, nullable: true }
        fdsRegulatoryCurrency: { type: string, nullable: true }
        fdsRegulatoryCurrencyMatchesBinding: { type: boolean, nullable: true }
        fdsRegulatoryCurrencyPendingApprovalId: { type: string, nullable: true }
        fdsRules:
          type: array
          items:
            type: object
            properties:
              ruleKey: { type: string }
              resolution: { type: string }
              ruleId: { type: string, nullable: true }
              name: { type: string, nullable: true }
              featureKeyMatched: { type: boolean, nullable: true }
              currencyMatched: { type: boolean, nullable: true }
              currentAmount: { type: string, nullable: true }
              derivedAmount: { type: string, nullable: true }
              drifted: { type: boolean, nullable: true }
              pendingApprovalId: { type: string, nullable: true }
              paramReadFailed: { type: boolean }
        profileAlignment:
          type: array
          items:
            type: object
            properties:
              profileCode: { type: string }
              bindingMatched: { type: boolean, nullable: true }
              ctrMatched: { type: boolean, nullable: true }
              fdsRulesMatched: { type: boolean, nullable: true }
        warnings: { type: array, items: { type: string } }
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
        kycEvidence: { type: object, description: 'KYC current-state(JSONB, 원문 아님). declaredIncomeBand 출력은 입력 4종 또는 internal projection UNKNOWN이며 UNKNOWN은 public input enum이 아님' }
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
  /api/v1/aml/transactions:
    get:
      summary: 거래 브라우즈(최근 거래) — 거래성(transaction-bearing) canonical events 최신순 페이지 조회(알럿 수·발동 룰 동봉, 회수(RETIRED) 알럿 제외)
      operationId: browseTransactionEvents
      security: [ { OAuth2: ['aml:case:read'] } ]
      parameters:
        - $ref: '#/components/parameters/TenantId'
        - { name: transactionRef, in: query, required: false, schema: { type: string }, description: payload transactionRef 정확일치 }
        - { name: eventId, in: query, required: false, schema: { type: string }, description: event_id 정확일치 }
        - { name: memberRef, in: query, required: false, schema: { type: string }, description: payload targetRef 단일 키 정확일치(레거시 memberRef 키 필터 미대상) }
        - { name: product, in: query, required: false, schema: { type: string } }
        - { name: from, in: query, required: false, schema: { type: string, format: date-time }, description: "occurredAt 하한(ISO-8601 instant, 파싱 실패 400)" }
        - { name: to, in: query, required: false, schema: { type: string, format: date-time }, description: "occurredAt 상한(ISO-8601 instant, 파싱 실패 400)" }
        - { name: page, in: query, required: false, schema: { type: integer, default: 0, minimum: 0 } }
        - { name: size, in: query, required: false, schema: { type: integer, default: 20, minimum: 1, maximum: 200 } }
      responses:
        '200':
          description: 페이지 봉투(루트 — §1.2 data 래핑 없음). 파생 행 필드는 전건 nullable(결측 null 반환·행 제외 없음)
          content:
            application/json:
              schema:
                type: object
                required: [rows, page, size, totalCount]
                properties:
                  rows:
                    type: array
                    items:
                      type: object
                      properties:
                        eventId: { type: string }
                        eventType: { type: string }
                        transactionRef: { type: string, nullable: true, description: null 이면 알럿 조인 스킵(alertCount=0) }
                        memberRef: { type: string, nullable: true, description: "COALESCE(targetRef, memberRef) 레거시 폴백 표시값" }
                        product: { type: string, nullable: true }
                        amount: { type: number, nullable: true, description: "payload amountBase 소싱(레거시 행 호환) — 값은 baseEquivalent/baseCurrency 와 항상 동일, 취소(reversal)/환불(refund) 음수 부호 보존" }
                        currency: { type: string, nullable: true }
                        channelType: { type: string, nullable: true }
                        direction: { type: string, nullable: true }
                        occurredAt: { type: string, format: date-time }
                        alertCount: { type: integer, format: int64, description: "(tenant_id, transaction_ref) 매칭 중 status<>'RETIRED' 만 집계" }
                        firedRuleCodes: { type: array, items: { type: string }, description: distinct scenario_code 최대 5건(RETIRED 제외) }
                  page: { type: integer }
                  size: { type: integer }
                  totalCount: { type: integer, format: int64 }
        '400': { description: from/to ISO-8601 instant 파싱 실패, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
        '403': { description: scope aml:case:read 부재, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
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
  /api/v1/admin/aml/ctr-thresholds:
    get:
      summary: 테넌트 전체 통화의 CTR 임계 행 목록 (EXECUTED 반영값만 — §2.7, 다통화 U18)
      operationId: listCtrThresholds
      security: [ { OAuth2: ['aml:admin:policy'] } ]
      parameters:
        - $ref: '#/components/parameters/TenantId'
      responses:
        '200':
          description: 통화 오름차순 정렬(findByTenantIdOrderByCurrency). 미설정 통화는 배열에서 생략(합성 폴백 없음 — F-077)
          content:
            application/json:
              schema:
                type: array
                items:
                  type: object
                  properties:
                    currency: { type: string, example: PHP }
                    amount: { type: number }
                    updatedAt: { type: string, format: date-time }
  /api/v1/admin/aml/ctr-thresholds/{currency}:
    get:
      summary: 단건 통화 CTR 임계 행 (행 부재 404 — 합성 DEFAULT_THRESHOLD 폴백 금지, §2.7)
      operationId: getCtrThreshold
      security: [ { OAuth2: ['aml:admin:policy'] } ]
      parameters:
        - $ref: '#/components/parameters/TenantId'
        - { name: currency, in: path, required: true, schema: { type: string } }
      responses:
        '200':
          description: 'CtrThresholdResponse{ currency, amount, updatedAt } — EXECUTED 반영값만(상신 스테이징 미반영)'
          content:
            application/json:
              schema:
                type: object
                properties:
                  currency: { type: string }
                  amount: { type: number }
                  updatedAt: { type: string, format: date-time }
        '404': { description: 행 부재(합성 폴백 없음), content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
  # ── bo-api 소유 서비스 관리·온보딩 엔드포인트 (§9·§3.16) ─────────────────────────────
  # 아래 경로는 bo-api가 소유·집약·인증하는 엔드포인트다. aml-svc 엔진이 아닌 bo-api가 구현하며,
  # aml-svc는 bo-api 온보딩 워크플로우의 위임 호출로 aml_tenants 갱신을 수신한다.
  /api/v1/bo/aml/transactions:
    get:
      summary: BO 최근 거래 목록 위임(AML-TM-001 ③) — aml-svc GET /api/v1/aml/transactions 위임(응답 가공 없음, from/to date-only 흡수·쿼리 인코딩은 bo-api 담당 §2.5a)
      operationId: listBoAmlTransactions
      security: [ { OAuth2: ['aml:case:read'] } ]
      parameters:
        - { name: transactionRef, in: query, required: false, schema: { type: string } }
        - { name: eventId, in: query, required: false, schema: { type: string } }
        - { name: memberRef, in: query, required: false, schema: { type: string } }
        - { name: product, in: query, required: false, schema: { type: string } }
        - { name: from, in: query, required: false, schema: { type: string }, description: "ISO instant 또는 date-only(YYYY-MM-DD → 당일 00:00Z 정규화, §2.5a H2)" }
        - { name: to, in: query, required: false, schema: { type: string }, description: "ISO instant 또는 date-only(YYYY-MM-DD → 익일 00:00Z 배타 정규화, §2.5a H2)" }
        - { name: page, in: query, required: false, schema: { type: integer, default: 0 } }
        - { name: size, in: query, required: false, schema: { type: integer, default: 20 } }
      responses:
        '200':
          description: ApiResponse 봉투 — data 하위 페이지 객체 ≡ 엔진 GET /api/v1/aml/transactions 200 루트(rows/page/size/totalCount, plane parity 대상). 위임 미설정 비운영은 결정적 stub 고정 3행(transactionRef 필터만 인메모리 적용)
        '503': { description: prod 위임 미설정 fail-closed(AML.ENGINE_UNAVAILABLE) }
  /api/v1/bo/aml/currency-profiles:
    get:
      summary: 기준통화 프로파일 카탈로그 목록 (bo-api 소유, §3.16a)
      operationId: listCurrencyProfiles
      security: [ { OAuth2: ['aml:admin:policy'] } ]
      responses:
        '200':
          description: 카탈로그 목록
          content:
            application/json:
              schema:
                type: object
                properties:
                  data: { type: array, items: { $ref: '#/components/schemas/CurrencyProfileView' } }
  /api/v1/bo/aml/tenants/{tenantId}/currency-binding:
    get:
      summary: 테넌트 통화/Policy Pack 바인딩 read-back (bo-api 소유, aml-svc raw read-back 위임)
      operationId: getCurrencyBinding
      security: [ { OAuth2: ['aml:admin:policy'] } ]
      parameters:
        - { name: tenantId, in: path, required: true, schema: { type: string }, description: "'current' 별칭 허용(ambient Tenant-Id)" }
      responses:
        '200':
          description: bound=false 이면 binding=null(미바인딩)
          content:
            application/json:
              schema:
                type: object
                properties:
                  data:
                    type: object
                    properties:
                      bound: { type: boolean }
                      binding: { $ref: '#/components/schemas/TenantCurrencyBinding' }
  /api/v1/bo/aml/tenants/{tenantId}/currency-profile:apply:
    post:
      summary: 기준통화 프로파일 일괄 적용 (STEP 체인 — 4-eyes 상신 포함, bo-api 소유, §3.16a)
      operationId: applyCurrencyProfile
      security: [ { OAuth2: ['aml:admin:policy'] } ]
      parameters:
        - { name: tenantId, in: path, required: true, schema: { type: string } }
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/CurrencyProfileApplyRequest' }
      responses:
        '200':
          description: 항상 200(실패는 steps[] 원소 단위 FAILED/BLOCKED_HISTORY 등으로 표현)
          content:
            application/json:
              schema:
                type: object
                properties:
                  data: { $ref: '#/components/schemas/CurrencyProfileApplyResponse' }
        '400': { description: 'AML.BAD_REQUEST — profileCode blank/미등재/번들 부재', content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
  /api/v1/bo/aml/tenants/{tenantId}/currency-profile:
    get:
      summary: 기준통화 프로파일 현황 (바인딩·CTR·FDS 룰·정렬 일치 여부, bo-api 소유, §3.16a)
      operationId: getCurrencyProfileStatus
      security: [ { OAuth2: ['aml:admin:policy'] } ]
      parameters:
        - { name: tenantId, in: path, required: true, schema: { type: string } }
      responses:
        '200':
          description: 항상 200. 조회 불가 소스는 null + STATUS_SOURCE_UNAVAILABLE warning
          content:
            application/json:
              schema:
                type: object
                properties:
                  data: { $ref: '#/components/schemas/CurrencyProfileStatusResponse' }
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
| **콜백 자격증명 설정**(AML-WHK-001, 2026-08-10 신설) | bo-api `GET/PUT /api/v1/bo/aml/webhook-credential`(읽기 `aml:case:read` **또는** `aml:admin:policy` / 쓰기 `aml:admin:policy`) → 엔진 `GET/PUT /api/v1/admin/aml/webhook-credential` **fail-closed 위임**(§2.7a). 조회 응답에 **시크릿 필드 없음** |
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

> **egress SSRF 정책(P0-17, 양 엔진 공통 규약)**: outbound 대상 URL은 공통 `com.aegis.common.security.egress.WebhookUrlPolicy`(`common-security` 모듈, 전송은 `NoRedirectRequestFactory` 결합)가 **3단계 검증**으로 통제한다 — ① 파싱(absolute URI·host 필수, user-info/fragment 금지; production tier(활성 프로파일 `prod`/`production`/`aws`)는 `https`만+port 443/8443/스킴 기본만, 비-production은 `http`/`https`·port 무제한), ② allowlist(`aegis.aml.webhook.allowed-host-suffixes`, env `AML_WEBHOOK_ALLOWED_HOST_SUFFIXES`, 콤마 구분·빈 값=비활성 — host suffix `.` 경계/exact 일치), ③ DNS 해석(**모든 A/AAAA 레코드** 검사 — production은 loopback·RFC1918·`fc00::/7`·link-local(cloud metadata 포함)·multicast·`0.0.0.0/8` 전체·broadcast·CGNAT(`100.64/10`)·IPv4-mapped(`::ffff:`)/NAT64(`64:ff9b::/96`) 임베디드 내부 IPv4 전부 거부, 비-production은 link-local(metadata)만 tier 무관 거부, mixed answer 1건이라도 위험이면 전체 거부). 위반 reason code 9종 = `NOT_ABSOLUTE`/`HOST_MISSING`/`SCHEME_NOT_ALLOWED`/`USER_INFO_FORBIDDEN`/`FRAGMENT_FORBIDDEN`/`PORT_NOT_ALLOWED`/`HOST_NOT_ALLOWLISTED`/`HOST_UNRESOLVABLE`/`ADDRESS_BLOCKED`. **AML 적용 시점**: 콜백 URL 원천은 `aml_api_credentials.webhook_url`(연동 §3.4)이고 **매 전송 직전 재검증만** 적용된다 — **(2026-08-10 정정)** 종전 근거였던 "webhook URL 런타임 등록 경로가 없음"은 §2.7a `PUT /api/v1/admin/aml/webhook-credential` 신설로 **더 이상 사실이 아니며**, 그럼에도 검증 시점은 그대로다: 등재 시점 SSRF 검증을 **의도적으로 넣지 않았다**(엔진 케이스 RA-C12 ⑦ — 사설 IP 콜백도 등재는 정상 완료되고 전달 단계에서 릴레이 `FAILED` 로 수렴, 결재 롤백 없음 — 의 기대 보존). 위반은 delivery 실패로 기록되어 기존 outbox `FAILED`+지수 backoff 계약(§8.4)에 수렴한다(신규 상태 없음). **redirect 미추종** — `setInstanceFollowRedirects(false)`로 3xx 응답은 추종하지 않고 non-2xx delivery 실패로 기록한다(hop 미추적). DNS rebinding은 JVM DNS positive cache TTL로 TOCTOU 창을 완화할 뿐이며 egress proxy/network policy 배포 요건이 백스톱이다(운영 runbook = 코드 레포 `docs/ops/webhook-egress-policy.md`).

### 8.1 이벤트 타입 (`eventName`)
| eventName | 트리거 | 발행 주체(엔진) | 핵심 payload(camelCase, raw PII 미포함) |
|---|---|---|---|
| `AmlScreeningResolved` | WLF 판정 확정(TRUE_MATCH/FALSE_POSITIVE 등 결재 EXECUTED) | Screening | 기존 `screeningId`,`targetRef`,`status`(§5.5),`watchlistSourceType`,`reasonCodes`[] + **additive**(PLAN 20260903-aml-decision-status-webhooks DoD 5) `transactionRef`,`targetType`,`score`,`approvalId`,`decidedBy`,`decidedAt`,`matchedEntries`[] |
| `AmlCaseStatusChanged` | case 상태 전이 | Case Mgmt | `caseId`,`caseType`(§5.8),`fromStatus`,`toStatus`(§5.9),`closeReason`(nullable) |
| `AmlReportSubmitted` | STR/CTR 제출·FIU 회신 결과 | Reporting | `reportId`,`reportType`(§5.10),`status`(§5.11: SUBMITTED/ACKNOWLEDGED/SUBMISSION_FAILED/REJECTED — FIU 회신 폐루프, 설계서 §14.1a),`submittedRef`(nullable),`fiuAckRef`(nullable),`submissionErrorCode`(nullable) |
| `AmlHighRiskRegistrationApproved` | `HRR_REGISTRATION`(당연고위험 등재) 4-eyes 승인 EXECUTED(**거절 시 미발행**) | RA(1차 온보딩 파생) | `memberRef`,`approvalId`,`decision`("APPROVED"),`tier`(§5 `ClassificationTier`),`checkerId`,`approvedAt` |
| `AmlMemberDecisionResolved` | (신규, PLAN 20260903-aml-decision-status-webhooks) `EDD_CLOSE`/`RELATIONSHIP_REJECT` 4-eyes 결재 EXECUTED(**거절 시 미발행**) | Member Decision(§2.3) | `memberRef`,`decision`(`APPROVED`\|`REJECTED`\|`EDD_REQUIRED`\|`REPORTED`),`source`(`EDD_CLOSE`\|`RELATIONSHIP_REJECT`),`reason`,`approvalId`,`caseId`,`caseType`,`finalStatus`,`scoreId`,`riskGrade`,`requiredAction`,`checkerId`,`decidedAt` |
| `AmlScreeningWhitelistChanged` | (신규, PLAN 20260903-aml-decision-status-webhooks) `FP_WHITELIST`(등록/취소) 4-eyes 결재 EXECUTED | Screening | `whitelistId`,`targetRef`,`targetType`,`matchedEntryId`,`action`(`GRANTED`\|`REVOKED`),`approvalId`,`checkerId`,`executedAt`,`expiresAt`(nullable) |

> 6종은 정본 콜백 집합(2026-07-24 `AmlHighRiskRegistrationApproved` 신설, 2026-09-03 `AmlMemberDecisionResolved`·`AmlScreeningWhitelistChanged` 신설 + `AmlScreeningResolved` data additive 보강). enum 코드값은 DB §5와 동일. payload는 token/hash·마스킹만(원문 미포함).
>
> **(2026-07-24 예외 — 목적지 원천)** 위 3종(screening/case/report)은 콜백 URL 원천이 `aml_api_credentials.webhook_url`(테넌트 사전등록, 아래 SSRF 정책 문단 참조)이지만, `AmlHighRiskRegistrationApproved` 는 **CDD 요청(`customer.cdd.completed`, aml-data §12.1 `callbackUrl`)이 실어 보낸 요청별 URL** 로 직접 발행된다(테넌트 사전등록 URL 아님) — `HRR_REGISTRATION` 상신 시 그 요청의 `callbackUrl` 이 승인 행에 결부되고, 승인(approve) 완료 시점에 그 URL 로 콜백이 나간다. **서명 시크릿은 URL 오버라이드 여부와 무관하게 여전히 테넌트 사전등록 자격증명(`aml_api_credentials`, `credential_type=WEBHOOK`) 소유** — 목적지만 요청별로 바뀔 뿐 신뢰 앵커는 테넌트다. SSRF 3단계 검증(아래 문단)은 이 요청별 URL 에도 매 전송 직전 동일 적용된다(완화 없음).
>
> **(2026-09-03 신설, PLAN 20260903-aml-decision-status-webhooks — 목적지 우선순위 확장)** `AmlMemberDecisionResolved`·`AmlScreeningResolved`·`AmlScreeningWhitelistChanged` 도 같은 요청별-URL 우선 패턴을 따른다: ① **회원 결정** — 그 회원의 최신 `customer.cdd.completed` 인입 `callbackUrl`(`aml_canonical_events.callback_url`, §12.1) 우선 → 없으면 테넌트 `webhook_url`. ② **WLF(스크리닝/화이트리스트)** — 원 스크리닝의 요청별 `callbackUrl`(`aml_screening_results.callback_url`, §3.2, V74) 우선 → 없으면 테넌트 `webhook_url`. 서명 시크릿은 두 경우 모두 여전히 테넌트 사전등록 자격증명 소유(목적지만 오버라이드). 결재 **반려**는 세 이벤트 모두 미발행(F-020 선례).

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
- 모든 키 **camelCase** 직렬화. `eventFamily`는 `eventName` 접두에서 도출(`AmlScreening*`→`screening`, `AmlCase*`→`case`, `AmlReport*`→`report`, `AmlHighRiskRegistration*`→`hrr`, **`AmlMember*`→`member`**(신규, PLAN 20260903-aml-decision-status-webhooks), 그 외→`unknown`).

### 8.3 서명·검증
- 헤더 `X-Signature: hmac-sha256=<hex>` = HMAC-SHA256(secret, `timestamp + "." + rawBody`). 헤더 `X-Webhook-Timestamp`(epoch ms) 동봉, 수신 측 ±5분 허용으로 replay 방어.
- secret은 source의 `secret_ref` 대조 원본(평문 1회 발급, 회전 시 무중단 위해 dual-secret 검증 기간 허용). 설계서 §15.7 'Webhook signature' 정합.
- **저장·등재 정본(코드=truth, 2026-08-10)**: 릴레이(`HttpWebhookRelayAdapter`)가 실제로 서명에 쓰는 시크릿은 테넌트 자격증명 `aml_api_credentials`(`credential_type=WEBHOOK`)의 `secret_ciphertext`(AES-GCM, 전송 시점에만 복호)이며, 위 `secret_ref` 는 그 발급·회전 개념 계보다. 이 행의 **런타임 등재·교체 경로는 §2.7a `PUT /api/v1/admin/aml/webhook-credential` 하나뿐**이다(종전에는 DB 직접 INSERT 만 가능했다). 아웃박스 행이 `webhook_target_url` 로 목적지를 오버라이드해도(§8.1 2026-07-24 예외) **서명 시크릿은 이 테넌트 자격증명 것을 쓴다** — 신뢰 앵커는 목적지가 아니라 테넌트다.
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
| 기준통화 프로파일 일괄 셋업(AML-CUR-001, 다통화 PLAN 20260818) | `GET /api/v1/bo/aml/currency-profiles`, `GET .../tenants/{tenantId}/currency-binding`, `GET .../tenants/{tenantId}/currency-profile`, `POST .../tenants/{tenantId}/currency-profile:apply`(§3.16a) | repo `config/currency-profiles/*.json` bundled 카탈로그 + aml-svc `GET .../policy-binding`·`GET .../ctr-thresholds[/{currency}]`(§2.7) + FDS `GET .../compliance`·`GET .../fds/rules`(01-fds-api.md §2.7) 다중 소스 오케스트레이션. apply 는 CTR `CTR_THRESHOLD`·FDS `RULE_PARAM`/`TENANT_REGULATORY_CURRENCY` 4-eyes 상신을 파생시킨다 |

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

### 11.2 관할 영업일 캘린더·bankingDayKey·보고 마감시각
`BankingCalendar`(도메인, I/O-free)가 영업일·일합산 경계를 계산하고, `JurisdictionCalendarPolicy`가 테넌트 바인딩의 `timezone`(V53)과 `report_cutoff_time`(V69)을 한 번 해소해 달력에 주입한다. ▷ `bankingDayKey(instant)`=거래 instant의 테넌트 관할 캘린더 일자. ▷ `startOfDay`/`startOfNextDay`=같은 관할의 반개구간 자정 경계. ▷ `isBusinessDay(date)`=토/일 아님 AND 관할 override 아님. ▷ `plusBusinessDays(from,N)`=N영업일 전진. ▷ `dueAt(txnTime,N)`=달력 계산 primitive이며, 법정 기한으로 영속할 수 있는지는 별도 `ReportDeadlinePolicy`가 결정한다. 현재는 PH+`Asia/Manila`+cutoff NULL(레거시) 또는 17:00만 허용한다. AU/JP/KR와 다른 PH cutoff는 달력/탐지/evidence window는 정상 사용하되 `reportDeadlineAt=null`을 보존한다. CTR·STR 달력 생성과 조회/evidence window는 평가 시점 동일 snapshot을 공유한다.

### 11.3 CTR/STR 룰 카탈로그 (`AmlReportRuleCatalog` 10종, 코드=truth)
| ruleCode | family | reportType | evaluationMode | reasonCode | actions | status | 자연어 |
|---|---|---|---|---|---|---|---|
| `CTR_SINGLE` | CTR | CTR | INLINE_AND_ASYNC | — | CTR_REPORT | ACTIVE | 단건 현금거래의 테넌트 기준통화 금액이 해당 통화 CTR 임계 이상 |
| `CTR_DAILY` | CTR | CTR | ASYNC_ONLY | — | CTR_REPORT | ACTIVE | 동일 영업일 현금거래 합산이 CTR 임계 이상(다건 보완재) |
| `STR_PEP` | STR | STR | ASYNC_ONLY | PEP | STR_FLAG | ACTIVE | PEP 관련 거래 — STR 검토 플래그 |
| `STR_SANCTION` | STR | STR | INLINE_AND_ASYNC | SANCTION | RESTRICT,STR_FLAG | ACTIVE | 제재 매칭 — **유일 차단(RESTRICT)** |
| `STR_KYC_INCOME_MISMATCH` | STR | STR | ASYNC_ONLY | KYC_MISMATCH | STR_FLAG,EDD_TRIGGER | **ACTIVE** | 신고소득(숫자 직접 수신, 2026-08-16)의 월 상한을 테넌트 기준통화로 공급; 상한 없는 신고(`>=`·`>`)·통화 불일치·부재·미상은 fail-safe skip. 레거시 `declaredIncomeBand` 는 숫자 미신고 시 폴백 |
| `STR_STRUCTURED` | STR | STR | ASYNC_ONLY | STRUCTURED | STR_FLAG | ACTIVE | CTR 임계 90~99% 3영업일 연속(스머핑) |
| `STR_NO_PURPOSE` | STR | STR | ASYNC_ONLY | NO_PURPOSE | STR_FLAG | ACTIVE | 목적부재+행동이상 다중(메타룰) |
| `STR_THIRD_PARTY` | STR | STR | ASYNC_ONLY | THIRD_PARTY | STR_FLAG | ACTIVE | 송금 명의≠회원 명의 |
| `STR_VELOCITY_CASH` | STR | STR | ASYNC_ONLY | UNUSUAL_PATTERN | STR_FLAG | ACTIVE | 단기간 현금거래 빈도 이상(기본 건수 5) |
| `STR_MANUAL` | STR | STR | ASYNC_ONLY | MANUAL | STR_FLAG | **DRAFT** | 컴플라이언스 수동 STR(임계 미충족도) — 파이프라인 활성화 거부(§2.7) |

구체 CTR 통화 임계값은 카탈로그가 아니라 per-tenant `aml_ctr_thresholds`(§3.22a, `CtrThresholdPort`)다. `STR_KYC_INCOME_MISMATCH`는 고객 원장의 숫자 신고 4키를 `DeclaredIncomePolicy`로 해석해 상한이 있는 `LTE`/`LT`/`EQ`만 월소득으로 공급한다. `ANNUAL`은 `MathContext.DECIMAL128`로 /12 월할하되 evidence에는 원문 period를 보존하고, 신고 통화와 테넌트 기준통화가 다르면 환산 없이 skip한다. **`declaredIncomeAmount` 키가 존재하면 그 숫자 경로가 최종 권위**이므로 값이 잘못됐거나 `GTE`/`GT`여도 레거시 밴드로 폴백하지 않는다. 숫자 키 자체가 없을 때만 `declaredIncomeBand`를 해석하며, 유한 3종은 PHP/MONTHLY 상한 proxy, `OVER_10M_PHP`·부재·미상은 skip한다. 판단과 evidence는 평가 진입에서 한 번 resolve한 동일 값을 공유한다. `STR_MANUAL`만 DRAFT·수동 전용으로 자동 평가·활성화 파이프라인에서 제외된다. `AmlReportRuleCatalog.activeRules()`는 9종.

`STR_VELOCITY_CASH`의 rolling cash window는 평가 거래를 정확히 1회 포함한다. 중립 canonical 저장의 바깥 transaction과 STR `REQUIRES_NEW` 평가가 분리되어 현재 행이 아직 보이지 않으면 `EvaluateStrCommand`의 triggerRef/channelType/동결 **테넌트 기준통화 금액**으로 현재 cash 행을 합성한다. 이미 조회된 동일 triggerRef가 있으면 합성하지 않아 전용 STR·재평가 경로의 이중 집계를 막는다. 따라서 effective `count_threshold=N`은 N번째 현금성 거래에서 즉시 발동한다.

### 11.4 CTR freeze·집계 (BR-501)
CTR 평가(`CtrEvaluationService`)는 거래의 **freeze 된 서버 파생 테넌트 기준통화 금액(`baseEquivalent`)을 재계산하지 않는다**(BR-501). neutral ingest는 canonical 저장의 바깥 transaction과 CTR/STR `REQUIRES_NEW` 경계 및 허용 범위 내 원천↔엔진 시계 오차에도 현재 거래를 잃지 않도록 command의 current-event 기준통화 금액을 우선 사용한다. 이 값은 canonical `amounts`에서 서버가 확정한 동일 동결값이며 PHP 테넌트만 `phpEquivalent` 하위호환 별칭을 함께 갖는다. 현재-event 신호가 없는 레거시·직접 TM 호출만 canonical 이벤트 윈도우의 `COALESCE(baseEquivalent, phpEquivalent)`로 폴백하며, 두 경로 모두 값이 없으면 금액 룰은 fail-safe 미발동한다. `CTR_SINGLE`=단건 기준통화 금액 ≥ 해당 통화 임계, `CTR_DAILY`=동일 **관할 영업일** 현금거래 합산 ≥ 임계(다건 보완재). DB 합산 구간은 `BankingCalendar.startOfDay/startOfNextDay`의 정확한 `[start,nextStart)` SQL이며 PostgreSQL microsecond 반올림에도 다음 자정 행을 섞지 않는다. 알럿의 표시 조회 범위는 평가 시점 `asOf` 상한까지 `evidenceWindow`에 별도 동결한다. (테넌트,주체,영업일)당 CTR DRAFT 정확히 1건(부분 UNIQUE `ux_aml_ctr_draft`, DB §3.12)이며 후속 현금거래는 `report_amount`에 정확히 1회 누적한다(`accumulateCtr`, 경합 시 재시도). `due_at`은 `ReportDeadlinePolicy`가 허용한 PH AMLC에서만 freeze하고 다른 관할은 null을 보존한다.

### 11.5 STR 사유코드 UPSERT
STR 평가(`StrEvaluationService`)는 (테넌트,트리거)당 STR DRAFT 정확히 1건(부분 UNIQUE `ux_aml_str_draft`, DB §3.12) — 동일 트리거에서 여러 STR 룰이 발화하면 **제2 DRAFT 를 만들지 않고** 각 사유코드(`StrReasonCode`)를 `str_reason_codes` JSONB 집합에 fold(UPSERT). `STR_SANCTION`만 RESTRICT(차단) 액션 동반.

### 11.6 PII sha256 — AMLC 포털 lodgement (`amlc_submission_ref`)
AMLC 제출은 **raw PII 미전송** — 토큰화된 보고 참조·PDF 아티팩트(§19.2 원문 미포함)만 전달한다. `AmlcSubmissionPort` 어댑터는 `aegis.aml.report.submission.amlc.mode`(`mock`|`browser`) 로 분기한다 — `mock`(`MockAmlcSubmissionAdapter`)은 결정적으로 `amlc_submission_ref = AMLC-{sha256(tenant|reportId|reportType)[..12]}`를 산출(BR-601, 무작위성 없음·데모 재현 가능). `browser`(**`PlaywrightAmlcSubmissionAdapter`**, feature/aml-reports-amlc-migration §1.4-C, prod 기본)는 `AmlcCredentialPort`로 조회한 테넌트별 저장 계정으로 AMLC 포털에 브라우저 자동화(Playwright for Java) 로그인 후 보고서 파일(PDF)을 업로드하고 확인번호를 파싱해 실 `amlcSubmissionRef`를 반환한다 — **aml-svc가 포털에 직접 lodge하며 별도 ProviderSvc로 위임하지 않는다**(구 서술 대체). `RegulatoryReportService`는 report 의 `amlcSubmissionRef` 가 non-null이면 어댑터를 재호출하지 않아 이중 lodge를 방지한다(멱등). prod 셀렉터/도메인(`portal.amlc.gov.ph`)은 실 포털 DOM 미검증 placeholder — go-live 전 실 포털 대조 필요(§1.6-G). 연동 상세 = integration §3.4(AMLC 포털 lodgement).

---

## 변경 이력

| 일자 | 변경 | 비고 |
|---|---|---|
| 2026-09-04 | **HRR 참조 리스트 변경 결재 EXECUTED 적용 시 자동 등재 2종 보존·version 규칙 정정(코드=truth, PLAN 20260904-aml-hrr-registry-apply-staged, aegis-aml F-093).** §12-B.6 admin surface `PUT .../reference-lists/{listType}` 행을 "전체 교체 … 전체 staged payload drift guard" 서술에서 "대상 `listType` 교체(운영자 관리 3종 `PRODUCT`·`VASP`·`HIGH_NET_WORTH` 한정 — 자동 등재 2종 `PEP_INDIVIDUALS`·`RA_HIGH_RISK_CUSTOMERS` listType 상신은 400 `AML.VALIDATION_ERROR`로 거부, bo-api 위임도 엔진 상태·코드를 보존해 동일 400 전달)"로 정정. 결재 EXECUTED 적용 시 자동 등재 2종은 적용 시점 저장본을 그대로 보존하고 관리 3종만 staged 스냅샷으로 교체하며, version 은 적용 시점 현재+1(상신 시 `UPDATE\|<version>` subjectRef 는 상신 시점 예상값이며 사이에 자동 등재가 있으면 적용 version 과 다를 수 있음)로 정정 — 종전 "전 5종 교체·상신 시점 목표 version 절대값 기록"은 결함이었다. | 코드=truth. 근거=aml-svc `HighRiskRegistryService#applyStaged`·`ReferenceListType#isAutoRegistered`. PRD §12-B.6 BR-002/003/004 동일 작업 단위. |
| 2026-09-04 | **bo-api HRR 등재 상신 위임 본문 필드명 정정(코드=truth, PLAN 20260904-aml-hrr-registration-followups).** HRR admin surface 절 `POST .../registrations` 위임 노트 하단에 bo-api 공개 본문 `{memberRef, tier?, reason?}` → 엔진 위임 본문 `{customerRef, tier, makerId, reason}` 매핑을 명문화(정정 전에는 위임 본문이 `memberRef`로 전송되어 엔진이 항상 400으로 거부). | 코드=truth. 근거=bo-api `AmlHighRiskRegistryService`. PRD §12-B.6 BR-008 동일 작업 단위. |
| 2026-09-04 | **bo-api HRR 레지스트리 조회 scope 분리(코드=truth, PLAN 20260904-aml-hrr-registry-search).** HRR admin surface 절 하단에 `GET /api/v1/bo/aml/high-risk-registry` 가 `aml:case:read` 또는 `aml:admin:high-risk-registry`(또는 `BO_SUPER_ADMIN`)로 조회 가능함을 명문화(§12-B.6 조회 권한 정합, 2026-09-04 라이브 실측 — `AML_COMPLIANCE`(`aml:case:read`) 세션이 조회에서 403). `PUT`·`POST /registrations`는 계속 전용 scope, 엔진 admin surface machine scope 무변경. | 코드=truth. 근거=bo-api `AmlHighRiskRegistryController`·`AmlStage4RbacWebMvcTest`. PRD §12-B.6 BR-008 동일 작업 단위. |
| 2026-09-04 | **케이스 담당자 디렉토리 포함 조건 정정(QA fix1, feature/aml-case-assignee-picker).** 위 노트를 코드 정합화 — 유효 역할 판정을 로그인 정본(`BackofficeRole.effectiveRoleCodes`: 부여 역할 0개 시 비-wildcard `adminType` 폴백)과 단일화, 바인딩 축을 테넌트만에서 **테넌트 ∧ 워크스페이스**(`TenantContextFilter` 동일 규칙)로 정정, 테넌트 컨텍스트 부재 403 `BO-TENANT-REQUIRED`(fail-closed)·keyword 100자 절단·결과 상한 없음(후속) 명시. | 코드=truth. 근거=bo-api `AdminAccountDirectoryService`·`BackofficeRole.effectiveRoleCodes`·`CaseAssigneeService`·`TenantContextFilter`. `docs/plan/03-bo-iam-approval-functional-spec.md` §2.4 동일 작업 단위. |
| 2026-09-03 | **회원 심사결과 확정 read-back + WLF 결재 웹훅 보강(코드=truth, PLAN 20260903-aml-decision-status-webhooks, 사용자 지시로 F-084 부분 해제).** §2.1 `customer.cdd.completed` 후주에 결재 실행 시점 확정 계약(`aml_member_decisions`, V74) 신설 문단. §2.2 `POST /aml/screen` 행에 `callbackUrl`? additive(SSRF 사전검증 400·`callbackConfigured` 응답), 신규 행 `GET /aml/screenings?transactionRef=\|targetRef=`(requireAny, `pendingDecision`/`callbackConfigured` additive), 기존 `GET /aml/screenings/{id}` 행에 동일 additive 표기. §2.3 신규 행 `GET /aml/customers/{customerRef}/decision`(requireAny `aml:case:read`\|`aml:event:write`, 404=회원 미존재·보류 중 200) + `MemberDecisionDto` 스키마·`OnboardingDecision` 매핑표·제외 결재 유형 서술. §3.2 `ScreenRequest.callbackUrl` 행 + `ScreeningResponse.pendingDecision`/`callbackConfigured` 행. §8.1 신규 `AmlMemberDecisionResolved`(family `member`)·`AmlScreeningWhitelistChanged` 행 + `AmlScreeningResolved` data additive + 목적지 우선순위(요청/인입별 URL → 테넌트) 신설 문단. §8.2 `eventFamily` 파생 규칙에 `AmlMember*`→`member` 추가. bo-api 미러: `GET /api/v1/bo/aml/customers/{ref}/decision`·`GET /api/v1/bo/aml/screenings/by-transaction?transactionRef=&targetRef=`(기존 `GET /api/v1/bo/aml/screenings` 8-파라미터 목록 계약 무변경). | 코드=truth. 근거=aml-svc `MemberDecisionController`·`ScreeningController`·`QueryMemberDecisionUseCase`·`MemberDecisionService`·`WebhookOutboxEmitter`·`domain/decision/MemberDecision`·`domain/enums/{MemberDecisionKind,MemberDecisionSource}`·`V74__member_decisions_and_screening_callback.sql`; bo-api `AmlRiskReadController`·`RaDtos.MemberDecision*`·`AmlScreeningController`·`ScreeningDtos`. `docs/aml-data.md` §11.6a·§12.1·§12.1a·§12.6 동일 작업 단위(U0). 엔진 케이스 RA-C22/WLF-C23(사용자 승인 후 카탈로그 append). |
| 2026-08-25 | **§2.7 legacy invalid timezone raw read fail-closed 정합.** policy-binding GET은 4열 null/blank뿐 아니라 이미 저장된 invalid/fixed-offset timezone도 `422 AML.TENANT_POLICY_UNBOUND`로 거부해 raw 잘못된 값을 노출하지 않는다. valid timezone + stale/DRAFT policy-pack pin의 기존 `200 + policyPackResolved=false` 3상태는 유지한다. CTR event-time 관할 일합산은 §11.2의 기존 거래 instant 정본 이격을 코드가 수렴한 것이므로 wire 문서 변경은 없다. | 코드=truth. 근거=aegis-aml `TenantPolicyBindingAdminController`, `TmEvaluationService`, `EvaluateTmUseCase.TransactionSignals`, CTR-C13. |
| 2026-08-24 | **§2.7a 동일값 Webhook 자격증명 PUT 감사 계약 정정(F-048/RA-C15).** 같은 값 재PUT 은 자격증명 행·AES-GCM 암호문·`updatedAt`·`updatedBy`를 회전시키지 않는 저장 멱등성을 유지하되, 성공한 관리 쓰기 호출은 `POLICY_CHANGE`/`WEBHOOK_CREDENTIAL_SAVED`/`operation=REPLACE` 감사 1건을 append한다. 아래 2026-08-10 신설 이력의 "같은 값 재PUT 감사 없음"은 본 행으로 명시 폐기되며 현재 계약이 아니다. 감사 detail에는 시크릿이 없고 목적지는 host까지만 남긴다. | 코드=truth. 근거=aegis-aml `WebhookCredentialAdminService#save`, `WebhookCredentialAdminServiceTest`, `WebhookCredentialAdminIntegrationTest`, 엔진 케이스 RA-C15. |
| 2026-08-22 | **WLF 요청 이름 스냅샷·NAME 인라인 읽기 카브아웃(코드=truth).** §1.6·§2.4 P0-09·§3.2·§3.4b에 `requestName`/`matchedEntryNames`를 추가했다. 요청명은 persisted `screeningId`의 `WLFREQ-{screeningId}` vault NAME 스냅샷이며 `nameTokens` 순서 보존 결합값, 과거 결과는 폴백 없이 생략한다. 매칭 명단명은 안정 entry id의 vault NAME을 현재 게시본으로 해소하므로 재sync로 표기가 바뀔 수 있다. `aml:case:read`만 두 NAME 값을 읽고 `aml:screen:evaluate` 단독은 키를 받지 않으며, bo-api가 이름이 실제 반환된 읽기 요청당 `RAW_DATA_ACCESS` 1건을 남긴다. 알림·근거거래·Subject360 및 비-NAME reveal 계약은 불변이다. | 코드=aml-svc `WlfScreeningService`·`ScreeningIdentityProjectionService`·`ScreeningController`, bo-api `AmlScreeningService`·`ScreeningDtos`. DB §3.21·SW §19.2·기능정의서 AML-WLF-001/002/003 동기화. |
| 2026-08-19 | **TM 최근 거래 브라우즈 API 신설(코드=truth, PLAN 20260819-aml-tm-recent-transactions, 역전파 DOCS-1).** (1) **§2.4 신규 행** — aml-svc `GET /api/v1/aml/transactions`(scope `aml:case:read`·`Tenant-Id`): 거래성 family 4종(`transaction\|remit\|domestic\|wallet`) canonical events 최신순 페이지 조회. 필터 5종(transactionRef/eventId/memberRef/product/from·to) 전부 optional·정확일치(memberRef 는 `payload->>'targetRef'` 단일 키), `size` 기본 20·상한 200, 응답 페이지 봉투 `{rows,page,size,totalCount}`. 금액 키 = `amount`/`currency`(payload `amountBase`+`currency` 소싱, 레거시 행 호환 — 값은 canonical `baseEquivalent`/`baseCurrency` 와 항상 동일·음수 부호 보존). 파생 필드 전건 null 허용·행 제외 없음. `alertCount`/`firedRuleCodes`(distinct·최대 5건)는 회수(`RETIRED`) 알럿 제외 집계(F-034 정합·`includeRetired` 파라미터 없음). (2) **§2.4 후주 재작성** — 기존 증적 평면 `fund-view` 브라우즈(주체 한정·30일 윈도우) 기존재 사실 기준으로 정정('기존 브라우즈 경로 전무' 서술 금지), 본 API 는 계약 분리된 운영 조회 평면 신설·bo-api verbatim 위임. (3) **§2.5a 행 추가** — bo-api `GET /api/v1/bo/aml/transactions`(위임+비운영 stub 폴백+prod fail-closed 503). (4) **§5 OpenAPI paths 등재** — 엔진·bo-api 2행(행 필드 nullable·plane parity 註 포함). (5) **리뷰 H2·M1 반영(같은 날)** — bo-api 프록시가 `from`/`to` date-only 를 흡수(`AmlTmService#parseInstant` 동형: from=당일 00:00Z·to=익일 00:00Z 배타, 실패 400)하고 쿼리 값별 `UriUtils.encodeQueryParam` 인코딩(주입 차단) — 엔진 §2.4 계약(ISO instant, 파싱 실패 400)은 불변. | 코드=truth. 근거=aml-svc `TransactionQueryController`·`TransactionEventBrowseService`·`TransactionEventBrowseAdapter`·`V70__canonical_event_browse_indexes.sql`, bo-api `aml/transactions/{controller,service,dto}`. DB `02-aml-db.md` §7 V70·기능정의서 AML-TM-001 BR-014 동일 작업 단위. |
| 2026-08-19 | **통화 프로파일 spec 리뷰 중간·낮음 이격 보완(코드=truth, U13 후속 정합).** (1) **§3.16a apply `warnings[]` 코드 열거 확정(M1)** — `string[]` 서술을 방출 전체 집합 9종 표로 확정: `CTR_REPORTING_GAP:{ccy}`·`CONFIGURABLE_AMOUNT_RULE:{family}:{ruleCode}`·`CONFIGURABLE_RULES_UNCHECKED`·`CTR_PENDING_DIVERGENT`·`CALENDAR_UNPROVISIONED`·`FDS_REGULATORY_CURRENCY_MISMATCH`·`FDS_REGULATORY_CURRENCY_UNSET`·`FDS_CURRENCY_APPLIED_BINDING_PENDING`·`PACK_PROFILE_DIVERGENCE`(+ `STATUS_SOURCE_UNAVAILABLE:{소스}` 는 현황 전용 — 집합 분리 註). `FAILED` reasonCode 열거에 `PARAM_KEY_UNRESOLVED` 추가(총 8종 — bo-web `lib/currency-profile.ts` `CurrencyProfileApplyReasonCode` 유니온 1:1). (2) **§3.16a STEP enum 나열 순서를 실제 방출 순서로 정렬(L2)** — `FDS_REGULATORY_CURRENCY`→`BINDING`→`CTR_THRESHOLD`→`REPORT_RULES`→`FDS_RULES`, 미실행 STEP `steps[]` 미포함 명시(§5 schema enum 순서·description 동기). (3) **§3.16a `FdsRuleStatusRow.resolution` 값 집합 열거(L3)** — `MATCHED`/`NOT_FOUND`/`AMBIGUOUS`(bo-web `FdsRuleStatusResolution` 1:1). (4) **§5 OpenAPI paths 등재(M4)** — 엔진 `GET /api/v1/admin/aml/ctr-thresholds`·`GET .../ctr-thresholds/{currency}` 2행 신설(§2.7 표와 동일 계약 — 404=행 부재·합성 폴백 없음). (5) **§3.6a `RuleConditionView` leaf 정의 신설 + `unit` nullable 명기(M5)** — CTR 조건행 `unit` = 서버 해석 테넌트 기준(보고)통화 코드 또는 `null`(미바인딩/해석 불가 — PHP 폴백 금지), 클라이언트 합성 금지·3-상태 렌더 규칙 cross-ref. | 코드=truth. 근거=bo-api `aml/currencyprofile/service/CurrencyProfileApplyService`(WARN_* 상수·add 지점·STEP 방출 순서)·`aml/reports/service/AmlReportRuleParamService#conditionViews`·`aml/reports/dto/ReportRuleDtos.RuleConditionView`, aml-svc `adapter/in/rest/CtrThresholdAdminController`, bo-web `lib/currency-profile.ts`. 기능정의서 §13.4·§12-B.3 동일 작업 단위. |
| 2026-08-19 | **다통화(법인별 자국통화) 기준통화 프로파일 일괄 셋업 역전파(코드=truth, PLAN 20260818-currency-profile-bo-setup U13).** (1) **§2.7 Tenant Policy Binding** — PATCH 행에 거래성 이력 보유 테넌트의 `baseCurrency` 변경 fail-closed(422 `AML.TENANT_CURRENCY_HISTORY_LOCKED`) 주석 + `reportCutoffTime` cutoff 무접촉 명시(응답 스키마 불변), 신규 **전용 `PUT .../policy-binding/report-cutoff-time`**(항상-쓰기·명시 null 허용) 행 + 신규 **raw `GET .../policy-binding`**(12키 read-back — `policyPackResolved`·`calendarCoverage`·`transactionalHistory` 포함, 4열 미설정 422) 행 추가. 같은 절에 엔진 CTR 임계 read 2종(`GET /api/v1/admin/aml/ctr-thresholds`·`GET .../ctr-thresholds/{currency}`, 행 부재 404·합성 폴백 없음) 신설 — 기준통화 프로파일 apply STEP `CTR_THRESHOLD`/현황 `ctrThresholds[]` 판정 정본. (2) **§3.16a 신설** — bo-api 소유 신규 엔드포인트 4종(`GET /currency-profiles`, `GET .../currency-binding`, `GET .../currency-profile`, `POST .../currency-profile:apply`) DTO 전수(`CurrencyProfileView`·`ApplyRequest`·`ApplyStepResult`·`ApplyResponse`·`CurrencyBindingResponse`·`StatusResponse`), STEP 5종(`BINDING`/`FDS_REGULATORY_CURRENCY`/`CTR_THRESHOLD`/`REPORT_RULES`/`FDS_RULES`)·상태 11종·FDS 저작 가드(`SFDS_TENANT:ADMIN`/`SFDS_RULE:OPERATE` 미보유 시 `FAILED(FDS_AUTHORITY_MISSING)`)·warnings 코드 계약 명세. (3) **§4 오류표** — `AML.TENANT_CURRENCY_HISTORY_LOCKED`(422) 신설. (4) **§5 OpenAPI** — 신규 bo-api 4종 paths + `CurrencyProfileView`/`TenantCurrencyBinding`/`CurrencyProfileApplyRequest`/`CurrencyProfileApplyStepResult`/`CurrencyProfileApplyResponse`/`CurrencyProfileStatusResponse` schema 6종 신설. (5) **§9 표** — AML-CUR-001 화면 행 추가. | 코드=truth. 근거=bo-api `aml/currencyprofile/{controller/CurrencyProfileController,dto/CurrencyProfileDtos,service/CurrencyProfileCatalogService,service/CurrencyProfileApplyService}`, aml-svc `adapter/in/rest/TenantPolicyBindingAdminController`·`CtrThresholdAdminController`. DB §02-aml-db.md §7 V24·integration §01-fds-integration.md·기능정의서 §13.4 동일 작업 단위. |
| 2026-08-17 | **숫자 신고소득·동결 evidence window·관할 보고기한 fail-safe 정합화.** 숫자 amount 키 presence가 malformed/null일 때 legacy band 폴백을 막고, ANNUAL은 DECIMAL128 월할·원문 period provenance를 보존한다. public `kycEvidence`는 numeric 4키를 additive로 반환한다. TM alert는 `evidenceWindow`를 동결해 binding 변경 뒤에도 동일 관련거래를 재현하며 malformed snapshot은 current binding으로 재해석하지 않는다. `reportDeadlineAt`은 원본 binding이 PH+Asia/Manila일 때만 계산하고 다른 관할은 DRAFT 유지+null+구조화 WARN으로 명문화했다. 기존 STR 지연 bucket은 법정 dueAt이 아닌 legacy `created_at+72 elapsed hours` 운영 기준선임을 분리했다. | 코드=truth. 근거=aegis-aml `DeclaredIncomePolicy`·`IdentityProjectionService`·`EvidenceTimelineService`·`AlertEvidenceWindowResolver`·`ReportDeadlinePolicy`·`StrReportingStats`. DB §3.3/§3.10/§3.12 동기화. |
| 2026-08-14 | **CDD `declaredIncomeBand` optional input과 internal `UNKNOWN` projection output 경계 역전파.** canonical 입력 enum 4종 유지, exact CDD completed omission/null/blank의 조건부 current-state sentinel, sentinel-only evidence 금지, re-CDD full replace/raw event 불변/replay·409/no-backfill을 명문화했다. §3.9 `CustomerProfileDto.kycEvidence`는 output `UNKNOWN` 가능, BO Java/read model `incomeMultiple=null`이며 기존 `NON_NULL` producer JSON은 key를 생략한다. bo-web은 생략/explicit null을 모두 배율 산출 불가로 소비하고 ko/en `미상`/`Unknown` 표시 계약을 분리한다. `UNKNOWN`은 amount/proxy/provenance를 만들지 않아 income predicate만 skip하고 다른 AML/FDS 평가를 막지 않는다. | 코드=truth. 근거=aegis-aml `IdentityProjectionService`·`DeclaredIncomeBandPolicy`·`AmlCustomerProfileService`·`CddSnapshotPanel` messages/tests. DB §3.3·기능정의서 v9.86 동기화. endpoint/DTO field/Flyway 신규 0. |
| 2026-08-13 | **RA 모델 `signalScaling` 선택키 + RA 점수 `signalScaling` 근거 필드 + `pepAxis` 유효정책 블록 + `UnknownOutcome` 3값 역전파(코드=truth, aegis-aml `feature/pep-name-risk-score-scaling` `206b7558`. 전부 additive — 기존 필드 삭제·이름 변경 0, Flyway 신규 0).** (1) **§2.3 `POST .../ra-models`** — ONGOING `parameters` 허용키 **7 → 8**(`signalScaling` 선택키). 스키마 `{ "<origin>": { rules[], curve, floorScore, ceilingScore, minMultiplier, maxMultiplier } }`, 불변식 6종 + `STR_SANCTION` 거부 + origin 키 패턴을 **저장 시점 400** 으로 fail-fast. 종전 문서는 "`parameters` 는 §11.3 의 scenario별 top-level/nested unknown key 를 거부한다" 만 적었는데 그 허용키 목록에 새 키를 넣지 않으면 **4-eyes draft 저장 자체가 400** 이라 관리 메뉴→엔진 반영 폐루프가 물리적으로 성립하지 않는다 — 읽기·쓰기 두 경로가 함께 확장됐음을 명문화. 키 부재 = 미적용(항등원 1.0)이라 기존 ACTIVE 정의 무영향·전 테넌트 재승인 불요. (2) **§3.3 `RiskScoreResponse.signalScaling` 신설(12필드)** — 엔진은 `factorBreakdown.signalScaling` **중첩 객체**로 싣지만 `factorBreakdown` 노출 타입이 `Map<String, Double>` 이라 중첩을 담을 수 없어 `triggerAlerts`·`reviewShortened` 선례와 동형으로 전용 필드 파생 + 예약키 배제(미등재 시 요인으로 오인돼 **조용히 버려진다**). `rawScore` 는 `matchScore`(=overall)가 아니라 **이름 하위점수**이고 `severityDriver` 가 "배수를 바꿔도 점수가 안 움직이는" 경계를 기계 판정한다. (3) **§2.2 `GET .../wlf-engine-config` 응답 `pepAxis` 유효정책 블록 8필드**(읽기 전용·additive) — 건별 근거는 후보가 있었던 행에만 붙어 테넌트 유효값을 읽을 수 없었다. `:change` 요청 스키마 무변경(4-eyes 편집 승격은 범위 밖). (4) **§3.2 PEP 축 사유코드 3종 → 4종** — `PEP_CORROBORATION_UNKNOWN_RISK_SIGNAL` 신설, `pepAxis.decision` 에 `CUSTOMER_CORROBORATION_UNKNOWN_SIGNAL`, `unknownOutcome` 에 `RISK_SIGNAL`, 그 판정 전용 표식 2키(`riskSignal`·`signalOrigin`) 추가. status·차단 계약 무변경, STR 발동 게이트 무연결, **엔진 하류 소비 경로는 아직 없음(정책 결정 대기)** 을 사실대로 기록. 다른 판정의 근거 블록은 바이트 동일. | 코드=truth. 근거=aml-svc `domain/risk/{SignalScaling,OngoingRaParameters,RiskModelDefinitionValidator,AlertSignalMark}`·`application/usecase/OngoingRaService`(`signalScalingEvidence`)·`domain/screening/match/{PepAxisPolicy,WlfMatchVerdict}`·`adapter/in/rest/WlfEngineConfigurationController.PepAxisResponse`, bo-api `aml/ra/dto/RaDtos.SignalScaling`·`aml/ra/service/AmlRaService`(`signalScalingFromBreakdown`·`RESERVED_BREAKDOWN_KEYS`)·`aml/screening/dto/ScreeningDtos.PepAxisEvidence`·`aml/wlfconfig/dto/WlfEngineConfigDtos.WlfPepAxisPolicyView`. 검증=`RiskModelDefinitionValidatorTest`·`RaOngoingSignalScalingIntegrationTest`·`AmlRaServiceSignalScalingTest`·`WlfEngineConfigurationControllerTest`·`AmlWlfEngineConfigControllerTest`·`WlfPepAxisUnknownRiskSignalScreeningTest`. 설계서 §11.3a·§10.3b · DB §3.9 · 기능정의서 §6.1·§12-B.8 BR-007 동일 작업 단위. |
| 2026-08-13 | **`:simulate` 후보 회수 옵션 단일화 + 회수 계약 진단 `candidateRecall` 역전파 — 재리뷰 REJECT 높음 해소분(코드=truth, aegis-aml main `3d3f8bc0`. 엔드포인트·요청 스키마 불변, 응답은 가산 키 1개만·DB/Flyway 무변경).** (1) **§2.4 단건 시뮬레이션 註 사실 정정** — 직전 행이 등재한 "실운영 판정 parity" 는 **판정 함수·정책 인스턴스 축만** 닫은 것이었고 **후보 회수 축은 그대로 갈려 있었다**(시뮬레이션 `CandidateOptions.defaults()` = cap 200/trgm 0.30/phonetic on/timeout 10 s vs 실운영 `aegis.aml.wlf.candidate.*`). 두 값이 다르면 같은 판정 함수를 태워도 후보 집합이 달라 결과가 반대로 갈린다 — 운영 cap 500 테넌트에서 축 rank 201 의 진성 제재 후보는 실운영 `POSSIBLE_MATCH` / 시뮬레이션 `NO_MATCH` 이고, cap 을 낮춘 테넌트에서는 반대 방향이다. **운영자는 그 시뮬레이션으로 임계를 튜닝하고 4-eyes 승인까지 낸다.** 이제 조립 지점은 실운영 스크리닝 한 곳(`ScreenSubjectUseCase.candidateRecallOptions()` 공표)이며 시뮬레이션이 값을 복제하지 않고 읽어 간다. 회수 knob 은 what-if 입력이 아니며 요청 스키마 신설 0(what-if 축은 `similarityThreshold` 하나 유지). (2) **§3.2 `scoreBreakdown.candidateRecall` 신설(simulate 응답 한정)** — `{ optionsSource(`"PRODUCTION_SCREENING"`), candidateCap, trgmFloor, phoneticEnabled, statementTimeoutMillis, candidateCapScope, recalledCount, candidateCount, candidateCapHit, recallComplete, 절단 시 truncatedAxes[] }`. 종전 시뮬레이션은 회수 결과에서 후보 목록만 취해 `candidateCapHit` 를 버렸고 운영자는 **잘린 후보 집합 위의 판정**임을 알 수 없었다. 영속 결과의 `candidateStrategy` 와는 별개 키(영속 recall 스냅샷 vs 비영속 시뮬레이션 회수 계약 공표)이며 기존 키 삭제·이름 변경 0, `SimulateResult` 시그니처 불변. **BO 도달 범위 명시** — bo-api 가 `scoreBreakdown` 을 숫자 값만 남겨 투영하므로 이 블록은 엔진 REST 응답까지만 실린다(`pepAxis` 만 전용 컴포넌트 투영 보유). | 코드=truth. 근거=aml-svc `application/port/in/ScreenSubjectUseCase`(`candidateRecallOptions`)·`application/usecase/{WlfScreeningService,ScreeningOperationsService}`(`candidateRecallEvidence`), bo-api `aml/screening/service/AmlScreeningService.engineScoreBreakdown`(숫자 한정 투영 — BO 미도달 근거). 검증=`WlfSimulateCandidateOptionsParityTest`(회수 프로파일 4 × 축 2 = 8건, 수정 전 8/8 FAIL 로 red 실증)·`ScreeningOperationsServiceTest`(회수 옵션 pass-through). 소프트웨어 설계서 §10.3b·연동 §3.1b-1 동일 작업 단위. |
| 2026-08-12 | **PEP 축 정책 v2 + 후보 회수 축 분리 역전파 — 독립 리뷰 REJECT 높음 4건 해소분(코드=truth, aegis-aml main `d9520f0b`. 전부 additive — 엔드포인트·요청 스키마 불변, 응답은 가산 키만).** (1) **§3.2 `reasonCodes`** — PEP 축 사유코드 **2종 → 3종**: `PEP_CORROBORATION_UNKNOWN`(회원 축 요건 미달 원인이 불일치가 아니라 **확인 불가**) 신설로 `PEP_CORROBORATION_REQUIRED`(불일치 근거 실재)와 사유를 가른다. `WLF_TARGET_ROLE_MISMATCH`(등록 회원의 `targetType=COUNTERPARTY` 선언을 서버가 CUSTOMER 축으로 정정) 병기. (2) **§3.2 `scoreBreakdown.pepAxis`** — `policyVersion` **`wlf-pep-axis-v1`→`wlf-pep-axis-v2`**, `decision` 3값(`CUSTOMER_CORROBORATION_UNKNOWN` 가산), 근거 키 `corroboration`(코로보레이터별 4상태 `MATCH`/`MISMATCH`/`UNKNOWN_LIST_DATA`/`UNKNOWN_TARGET_DATA`)·`unknownOutcome`(`SUPPRESS`|`MATCH`)·역할 불일치 시에만 `declaredAxis`·`axisMismatch` 가산. 코로보레이터 3키의 부착 조건이 `MISSING` 단독 → `MISSING`·`UNKNOWN` 두 갈래로 확장. (3) **§3.2 `scoreBreakdown.candidateStrategy`** — `candidateStrategyVersion` **`wlf-cand-v1`→`wlf-cand-v2`**(전역 cap → **명단축별 cap**), `candidateCapScope`(`"PER_LIST_TYPE_AXIS"`)·`axisCounts`·절단 시 `truncatedAxes[]` 가산. 계약: **제재·법집행 후보는 PEP 물량에 잘리지 않는다**(구 전역 cap 은 동일 이름 PEP 다수가 제재 엔트리를 후보 집합 밖으로 밀어내 `NO_MATCH`→ALLOW 를 만들었다). 기존 진단 키 삭제·이름 변경 0. (4) **§2.4 단건 시뮬레이션 註** — `:simulate` 가 실운영과 **같은 순수 판정 함수·같은 정책 인스턴스**를 사용(구: 정책·§10.3a 이름 상향을 건너뛰어 반대 결과), 억제 시 동일 형태 `pepAxis` 동봉, `similarityThreshold` 는 review 임계 override 전용, bo-api `SimulateResponse.pepAxis` 투영. 엔진 `SimulateResult` 시그니처는 불변. (5) **§3.4a 알림 `evidence.watchlistMatch.origin`** — `WATCHLIST_MATCH`|`KYC_PEP_FLAG` **2종 → 3종**(`PEP_NAME_RISK_SIGNAL` 가산): 수취인 축 강등 행이 STR PEP 신호·계보로 실제 소비되며 확정 매칭과 구분된다. | 코드=truth. 근거=aml-svc `domain/screening/match/{PepAxisPolicy,WlfMatchVerdict,MatchScore}`·`domain/screening/PepNameRiskSignal`·`domain/watchlist/{BirthDate,CountryIso}`·`domain/tm/AlertEvidence`·`application/service/ScreeningAxisResolver`·`application/port/out/WatchlistEntryStorePort.RecallAxis`·`adapter/out/persistence/WatchlistEntryJpaAdapter`·`application/usecase/{WlfScreeningService,ScreeningOperationsService,StrEvaluationService,TransactionReportSideEffectRunner}`·`global/config/WlfPepAxisConfig`, bo-api `aml/screening/dto/ScreeningDtos.PepAxisEvidence`. 소프트웨어 설계서 §10.2b-1·§10.3b · 기능정의서 §12-B.8 BR-007·§3.1·§3.3·§12-B.1 동일 작업 단위. DB 스키마·Flyway 무변경. |
| 2026-08-12 | **PEP 축 분리 정책 + WLF 점수 정밀도 진단 + 후보 절단 가시화 역전파(코드=truth, aegis-aml `staging/round15` `e7d53836`·main `7e00b79d`·`596ec1ab`, 전부 additive — 엔드포인트·DTO 필드 스키마 불변).** (1) **§3.2 `reasonCodes`** — PEP 축 사유코드 2종 `PEP_CORROBORATION_REQUIRED`(회원 축 코로보레이터 부족)·`PEP_NAME_RISK_SIGNAL`(수취인 축 이름 일치를 위험 신호로 강등) 병기. `listType=PEP` 한정이며 제재(SANCTIONS)·범죄감시(LAW_ENFORCEMENT)는 무영향, 두 코드는 `status=NO_MATCH` 결과에만 붙는다. (2) **§3.2 `scoreBreakdown`** — 억제 감사 블록 `pepAxis{applied,policyVersion(도입 시 `wlf-pep-axis-v1` → 같은 날 `d9520f0b` 에서 **`wlf-pep-axis-v2`** 로 회전, 위 행),axis,listType,decision,suppressedStatus,suppressedBand,riskScore,entryId,reviewThreshold}`(+CUSTOMER 축 한정 `matchedCorroborators[]`·`acceptedCorroborators[]`·`requiredCorroborators`) 주석 신설 — **억제되지 않은 결과에는 키가 없어 응답 바이트 동일**, `riskScore`(매처가 실제 낸 유사도)는 폐기하지 않고 위험 신호로 보존. 저장 정밀도 진단 `scorePrecision{storedScore,comparedScore,band,storageScaleBand,decidedOn}` 주석 신설(저장·응답은 `numeric(8,4)`, 임계 비교·밴드·이름 floor·후보 순위는 반올림 전 원본 정밀도 — 반올림이 임계를 뒤집던 미탐 결함 수정). 후보 절단 가시화 `candidateStrategy.recallComplete`·`truncatedBy` 주석 신설. (3) **§2.4 단건 시뮬레이션 註** — admin/BFF `screenings:simulate` 밴드 불일치 시 `scorePrecision` 동봉(일치 시 응답 바이트 동일, `SimulateResult` 시그니처 불변). | 코드=truth. 근거=aml-svc `domain/screening/match/{PepAxisPolicy,MatchScore}`·`application/usecase/{WlfScreeningService,ScreeningOperationsService}`. 설정 축 `aegis.aml.wlf.pep-axis.*`(전부 기본값이 정책 정본, `enabled=false` 로 이전 동작 복귀). 소프트웨어 설계서 §10.3a·§10.4·기능정의서 §12-B.8 BR-007 동일 작업 단위 개정 |
| 2026-08-10 | **§2.7a 후속 2건 종결 — 미등록 테넌트 쓰기 4xx 확정 + BO 운영자 표면(bo-api 위임) 신설(코드=truth, aegis-aml main `48e8e697`).** 같은 날 신설분(`a0d1e5d9` 행)이 **의도적으로 남긴 후속 2건**을 닫는다. **① 미등록 테넌트 PUT = 400** — 종전 FK 위반 **500** 을 **400 `AML.VALIDATION_ERROR`** `details="unknown tenant"` 로 확정한다(인입 `AmlEventIngestService` 의 VALIDATION `unknown tenant` 관례 재사용 — **신규 에러 체계 0**). **404 가 아닌 이유**: `Tenant-Id` 는 경로 자원이 아니라 **헤더 차원**이고 같은 경로 `GET` 이 미등록 테넌트에도 **200 `configured=false`** 를 주므로 PUT 만 404 면 자기모순이다. **가드 위치**는 FK 를 소유한 **영속 어댑터(`save`)** 라 REST 한 경로가 아니라 **포트의 모든 호출자**(bo-api 위임 포함)를 덮는다. **`GET` 은 무변경**(미등록 테넌트 200 `configured=false` — F-048 회귀 테스트가 고정한 정본 동작). **외부 도달성 한계(사실)** — 라이브에서는 인증 필터가 (테넌트, API 키) 자격증명을 못 찾아 **401 로 먼저 끊기므로** 이 400 은 외부 직접 호출로 관측되지 않는다(위임·in-process 호출자에 대한 **선제 방어**이며 계약은 Testcontainers 통합 테스트로 고정). **② bo-api 위임 표면 2경로 신설** — `GET\|PUT /api/v1/bo/aml/webhook-credential`(엔진 `/admin/aml/webhook-credential` 로 **fail-closed 위임**, 로컬 stub 0, 엔진 에러 **무삼킴**(원 상태·`AML.*` 코드 그대로), 쓰기 시 **검증 actor 를 principal 에서 파생해 `X-User-Subject` 로 전달**). **권한 조합** — **`GET` = `aml:case:read` OR `aml:admin:policy`**(+`BO_SUPER_ADMIN`), **`PUT` = `aml:admin:policy`**. 읽기를 엔진과 1:1 로 좁히지 않은 근거: `aml:admin:policy` 보유 역할 `AML_POLICY_ADMIN` 이 `aml:case:read` 를 갖지 않아 **유일한 쓰기 권한자가 화면을 읽지 못하는 모순**이 생기고, GET 이 주는 것은 **시크릿 없는 마스킹 뷰**라 이미 쓸 수 있는 역할에게 읽기를 여는 것은 노출 증가가 아니다(선례 `AmlTenantController` 동형). **③ 화면** — bo-web `/aml/webhook-credential`(**AML-WHK-001**, 기능정의서 §12.3 v9.80), NAV **설정 › 연동·데이터**(`aml-config-connect`), 메뉴 카탈로그 행은 bo-api Flyway **V23**(additive·멱등). 시크릿 **전면 비노출**(편집 Modal 입력 전용·미리채움 금지), `webhookUrl=null` 은 **"오버라이드 전용"** 표기, 쓰기 scope 미보유 세션은 **편집 진입점 0**. **④ 무변경** — 엔진 계약(경로·scope·검증·감사·마스킹)·SSRF 처리 시점·Flyway(aml-svc) 전부 무변경, 신규 감사 이벤트 코드 0. 같은 날 `a0d1e5d9` 행의 **(11) bo-api·bo-web 표면 없음 · (12) 미등록 테넌트 500 · 후속 과제** 서술을 본 행이 **정정**한다(원 서술은 이력 보존을 위해 삭제하지 않고 취소선으로 남긴다). | 코드=truth. 근거=aml-svc `adapter/out/persistence/WebhookCredentialAdminJpaAdapter#save`·`application/port/out/WebhookCredentialAdminPort`, bo-api `aml/webhook/{controller/WebhookCredentialController,service/WebhookCredentialService,dto/WebhookCredentialDtos}`·`db/migration/V23__webhook_credential_menu.sql`, bo-web `components/aml/AmlWebhookCredentialSettings`·`components/common/CredentialStatusPanel`(AMLC 화면과 공통 추출)·`lib/nav.ts`·`app/(authorized)/aml/webhook-credential`. 테스트 `WebhookCredentialUnknownTenantIntegrationTest`·`WebhookCredentialAdmin{Controller,JpaAdapter}Test`·`AmlWebhookCredentialProxyDelegationTest`·`AmlWebhookCredentialSettings{,.i18n}.test.tsx`. 기능정의서 §1.0·§12.3·부록 A/B v9.80, DB §7 bo-api 註 동기화. integration·software **무수정**(이벤트·큐·아웃박스·서명·포트 경계 무변경). |
| 2026-08-10 | **§2.7a 아웃바운드 Webhook 자격증명 관리 REST 신설(코드=truth, aegis-aml main `a0d1e5d9`·`202af505`).** §8 콜백의 목적지·서명 시크릿을 등록할 수단이 **DB 직접 INSERT 뿐**이라 REST-only 원칙과 충돌해 `credential_type='WEBHOOK'` 행이 0개였고 HRR 승인 콜백 서명 검증(엔진 케이스 RA-C12)이 **실행 불가**이던 상태를 닫는다. (1) **`GET /api/v1/admin/aml/webhook-credential`**(`aml:case:read`) — 마스킹 뷰 **7필드** `{configured, credentialId, webhookUrl, secretConfigured, enabled, updatedAt, updatedBy}`, **시크릿 필드 자체가 없다**(존재 여부 불리언까지만). (2) **`PUT` 동 경로**(**`aml:admin:policy`**) — body `{webhookUrl, secret, enabled}`, 200 마스킹 뷰, **upsert·즉시 반영·4-eyes 없음**(§2.7 AMLC 결정 C 동형). (3) **쓰기 scope 상향** — 선례 AMLC 는 `aml:case:update` 지만 이 값은 **AML 알림이 어디로 나가는지**를 바꾸는 아웃바운드 유출 경로라 정책 관리 scope 로 올렸다(미보유 쓰기 **403**, 읽기는 `aml:case:read` 200). (4) **저장 형태** — `SecretCipherPort` **AES-GCM 암호문**, 평문 컬럼·응답·로그 없음. (5) **검증** — 빈·공백·키 누락 시크릿은 **400 `AML.VALIDATION_ERROR`** `details="webhook secret must not be blank"`(거부 후 기존 등재 **미훼손**), 검증 actor 누락은 **400** `details="verified X-User-Subject is required"`(actor 는 `TrustedActorResolver` 만). (6) **감사** — 성공한 PUT 마다 `POLICY_CHANGE` / `subject_ref=webhook-primary`(신규 등재 시) / `detail.action=WEBHOOK_CREDENTIAL_SAVED` / `detail.operation=CREATE\|REPLACE`, **detail 에 시크릿 없음·목적지는 host 까지만**. (7) **멱등** — 같은 값 재PUT 은 자격증명 행·암호문·수정 메타데이터 갱신 없음(감사 append는 2026-08-24 정정 행이 우선), 업서트 대상은 릴레이가 고르는 그 행(`enabled`→`webhook_url` 존재→`credentialId` 정렬, `credentialId`/`createdAt` 보존, 신규 `webhook-primary`). `scopes` 는 **`[]` 고정**(아웃바운드 서명 자격증명에 인바운드 권한 0). (8) **`webhookUrl=null` 허용** — 서명 시크릿만 등재하는 구성(요청별 `webhook_target_url` 오버라이드 이벤트용, 2026-07-24 예외·가정 A5 **무변경**). (9) **쓰기 시점 SSRF 검증 없음(의도)** — §8 정책은 매 전송 직전 재검증이며 RA-C12 ⑦(사설 IP 목적지도 등재는 정상 완료·전달 단계 `FAILED` 수렴) 기대를 보존한다. §8 SSRF 문단의 "런타임 등록 경로가 없으므로" 근거 문구를 **정정**(검증 시점 결론은 불변). (10) **마이그레이션 0** — `aml_api_credentials` 가 필요한 컬럼을 이미 갖고 `credential_type` CHECK 에 `WEBHOOK` 이 이미 있어 엔티티 매핑만 추가(DB §3.15). (11) **bo-api·bo-web 표면 없음**(엔진 admin REST 전용). (12) ~~**알려진 한계** — 미등록 테넌트 PUT 은 FK 위반으로 **500**(본문 누출 없음), 400/404 가 적절 — 후속 과제.~~ **(2026-08-10 정정 — 아래 `48e8e697` 행 참조)** 이 "500 · 후속 과제" 서술은 같은 날 해소되어 **더 이상 사실이 아니다**: 미등록 테넌트 PUT 은 **400 `AML.VALIDATION_ERROR`** `details="unknown tenant"` 이고, 가드는 FK 를 소유한 영속 어댑터에 있어 포트의 모든 호출자를 덮는다(`GET` 은 무변경). 또한 같은 행의 **(11) "bo-api·bo-web 표면 없음"** 도 BO 운영자 표면 신설로 사실이 아니게 됐다(엔진 계약 자체는 무변경). | 코드=truth. 근거=aml-svc `adapter/in/rest/WebhookCredentialAdminController`·`application/usecase/WebhookCredentialAdminService`·`application/port/out/WebhookCredentialAdminPort`·`adapter/out/persistence/{WebhookCredentialAdminJpaAdapter,ApiCredentialJpaRepository#findWebhookCredentialsForAdmin,ApiCredentialJpaEntity}`. 테스트 `WebhookCredentialAdmin{Controller,Service,JpaAdapter}Test`·`WebhookCredentialAdminIntegrationTest`. 시뮬레이터 `scripts/demo_ingest.py#ensure_webhook_credential`·sim-web ⓪⁗ `setup.webhook-credential`·`scripts/verify_hrr_approval_callback.py`(RA-C12 자동화, 검증 로직 ①~⑦ 바이트 동일). 엔진 케이스 `docs/qa/engine-rule-cases.md` RA-C14~C18 append·RA-C12 전제 열 정정. DB §3.15·§8, integration §3.4 동기화. 기능정의서 **무수정**(BO 화면 표면 0). |
| 2026-08-10 | **§2.4 설정형 보고룰 미활성 DRAFT 폐기(`:discard`) 신설(코드=truth, aegis-aml main `76681955`).** (1) **엔진 `POST /api/v1/admin/aml/configurable-report-rules/{ruleCode}:discard`** — body `DiscardRequest{version, actorId}`, 응답 **200** `DiscardResponse{ruleCode, version, status(DISCARDED\|ALREADY_ABSENT), alreadyAbsent}`. 저작된 DRAFT 를 되돌릴 수단이 없어 잔여 버전이 남고 같은 버전 재저작이 PK 충돌로 막히던 막다른 길을 닫는다. (2) **4-eyes 없음 — 대칭 근거 명문화**: 요구 scope 는 DRAFT 저작과 동일한 `aml:admin:policy` 이며 승인 결재를 요구하지 않는다(저작 자체가 단독 권한이고 그 버전은 **한 번도 효력을 가진 적이 없다** — TM 평가 미참여·발동 0·알럿 0). 효력 자산을 다루는 `:activate`·`:retire` 의 🔒`TM_SCENARIO` 4-eyes 는 **무변경**. (3) **대상 `DRAFT` 한정** — `ACTIVE`·`SUPERSEDED` 는 정책 계보라 409 `AML.STATE_CONFLICT`(무력화는 `:retire` 별도 경로), 해당 버전에 결속된 알럿(`evidence.trigger.ruleVersion`)이 있으면 409. (4) **4-eyes 우회 차단** — 같은 버전의 활성화 상신(`TM_SCENARIO`, subjectRef `CUSTOM_RULE\|code\|version`)이 PENDING 이면 409 거부(폐기 후 같은 버전 재저작 시 대기 결재가 미상신 DRAFT 를 발효시키는 구멍). (5) **멱등** — 이미 없는 버전 재폐기는 200 `ALREADY_ABSENT`·신규 부작용 0(감사 이벤트도 없음). (6) **감사** — `TM_SCENARIO_CHANGE` / `action=CUSTOM_RULE_DRAFT_DISCARDED`(+`ruleCode`·`version`·`family`). (7) **행 물리 삭제**이며 F-034 회수의 "행 보존"은 `ACTIVE→SUPERSEDED` 회수 경로·그 알럿 한정 계약이라 충돌 없음. (8) **bo-api `POST /api/v1/bo/aml/report-rules/configurable/{ruleCode}:discard`** — `aml:admin:policy`, `actorId` 는 인증 principal 로 덮어쓰고 판정은 전부 엔진 계약, 엔진 미가용 시 503 `AML.ENGINE_UNAVAILABLE` fail-closed. (9) 화면은 제안 버전과 충돌하는 **미활성 DRAFT 를 명시적 폐기 액션으로만** 정리하고(자동·무단 폐기 0) `ACTIVE`/`SUPERSEDED` 충돌은 다음 빈 버전을 제안한다. **DDL 변경 0**(DB §3.10b 스키마·제약 무변경). | 코드=truth. 근거=aml-svc `adapter/in/rest/ConfigurableReportRuleAdminController#discard`·`application/port/in/ManageConfigurableReportRuleUseCase#discardDraft`·`application/usecase/ConfigurableReportRuleService#discardDraft`·`application/port/out/ConfigurableReportRuleStorePort#delete`, bo-api `aml/reports/controller/AmlReportRuleController#discardConfigurableRule`·`aml/reports/service/AmlConfigurableReportRuleService#discard`·`aml/reports/dto/ReportRuleDtos`, bo-web `lib/aml-configurable-rules.ts`(`planAmlConfigurableRuleVersion` — FREE/DRAFT_CONFLICT/TAKEN/MANUAL)·`components/aml/AmlConfigurableRuleBuilder`. 테스트 `ConfigurableReportRuleDiscardControllerTest`·`ConfigurableReportRuleDiscardServiceTest`·`AmlConfigurableReportRuleServiceTest`·`AmlConfigurableRuleBuilder.versionConflict.test.tsx`. 기능정의서 §12-B.3 BR-008/BR-009 동기화. |
| 2026-08-07 | **§3.6 `ScenarioRow.ruleMetaUnavailable` nullable marker 신설(코드=truth, aegis-aml fix/aml-scenario-meta-degrade-distinction).** 설정형 룰 조회 실패·엔진 미가용을 성공 빈 카탈로그의 진짜 고아 코드와 구분한다. 장애 시 `true`, 정상 보강/진짜 고아는 필드 생략(`NON_NULL`)이며 효과성 집계는 계속 반환한다. | 코드 truth=bo-api `AmlStatsService.CustomRuleLookup`·`StatsDtos.ScenarioRow`, bo-web `AmlScenarioStatsDetail`; 기능정의서 §12-B.3 BR-009 v9.66 동기화. |
| 2026-08-06 | **§3.6a BUILT_IN `conditions[]`를 aml-svc 실제 평가식과 일치화(코드=truth, aegis-aml fix/aml-rule-condition-display-parity).** `STR_STRUCTURED` 상한을 `<`로 정정하고, `STR_THIRD_PARTY`의 존재하지 않는 수치 임계를 명의 불일치 boolean/token 게이트로 교체했으며, `STR_NO_PURPOSE`를 4종 행동신호 합계 `>=2`로 명시했다. `STR_PEP`·`STR_SANCTION`은 실제 boolean 게이트(`=TRUE`)와 read-only 점수 참고행을 함께 표시한다. bo-api 드리프트 검출 테스트가 aml-svc 카탈로그 소스와 조건 수·라벨·연산자·값·단위·paramKey를 대조한다. 엔드포인트·DTO·권한·4-eyes 계약은 무변경. | 코드 정본=aml-svc `domain/report/AmlReportRuleCatalog`, 표시 복제=bo-api `aml/tm/rule/AmlReportRuleCatalog`, 회귀=`AmlReportRuleCatalogParityTest`. 기능정의서 §12-B.3 v9.58 동기화. |
| 2026-08-06 | **§2.4 설정형 보고룰 회수(`:retire`) + TM 알림 회수 축(`RETIRED`) 신설(코드=truth, aegis-aml feature/aml-configurable-rule-retire, aml-svc V63).** (1) **`POST /api/v1/admin/aml/configurable-report-rules/{ruleCode}:retire`** — `:activate` 와 동형 4-eyes. 승인 유형은 **신규 값을 만들지 않고 `TM_SCENARIO` 재사용**, subjectRef 접두사 `CUSTOM_RULE_RETIRE|`(vs 활성화 `CUSTOM_RULE|` — 구분자 위치가 달라 상호 접두사 매칭 불가)로 라우팅 분기. drift guard(`canonicalSubjectRefOnly`)·결재함·checker 경로 무변경이고 bo-api/bo-web subjectType enum 동기화 불요. `CUSTOM_RULE_RETIRE` 를 TM 시나리오 예약어에 추가(오라우팅 차단). 승인 EXECUTED 시 도메인 `supersede()` **재사용**으로 `ACTIVE→SUPERSEDED`(신규 전이 없음) + 그 룰의 TM 알림 회수. 응답 `RetirementResponse{approvalId, status, alreadyRetired, retirableAlertCount, caseLinkedAlertCount}`, **멱등**(이미 SUPERSEDED=200·신규 상신 0 / 대기 상신 재사용), DRAFT 회수 409·미상 버전 400. (2) **§3.4a `AlertDto` + `AlertStatus` 에 회수 축** — `RETIRED` 상태와 `retiredAt`/`retiredBy`/`retireReason`(V63) 3필드 **additive**. `DISMISSED`(오탐 종결) 재사용 금지 — 업무 판단 vs 룰 무효화로 의미가 다르며 회수해도 `disposition_*` 는 보존. **케이스 개설 알림(CASE_OPENED/ESCALATED/STR_RECOMMENDED)은 회수하지 않는다**(규제 산출물 계보 보호) — 건너뛴 건수를 응답·`CUSTOM_RULE_RETIRED` 감사 이벤트에 보고. (3) **§2.4 목록·상세 `includeRetired`(기본 false)** — 회수 알림은 운영 목록·상세(404)·2차 RA lookback·대상별 집계에서 기본 제외하고 감사 조회만 명시 포함, **행은 삭제하지 않는다**. (4) 데모 데이터 DELETE 는 마이그레이션에 넣지 않는다(REST-only) — 기존 잔재는 `:retire` REST 1회 실행으로 회수. | aegis-java-implementer. 코드=truth. 근거=aml-svc `adapter/in/rest/ConfigurableReportRuleAdminController`(:retire)·`AlertController`(includeRetired·AlertDto 3필드)·`application/usecase/ConfigurableReportRuleService`(submitRetire/approveRetire)·`ApprovalDispatchService`(RETIRE prefix 라우팅)·`TmScenarioService`(예약어)·`domain/Alert`(retire/canRetire)·`domain/enums/AlertStatus`(RETIRED)·`db/migration/V63__alert_retirement.sql`, 테스트 `ConfigurableReportRuleRetireIntegrationTest`·`ConfigurableReportRuleRetireServiceTest`·`ConfigurableReportRuleRetireControllerTest`·`AlertControllerRetiredVisibilityTest`. 시뮬레이터 러너 `scripts/verify_aml_configurable_rules.py` 자기정리(검증 후 회수) 동반. DB §02-aml §마이그레이션(V63)·§5.7 동기화. |
| 2026-08-06 | **§3.6 `ScenarioRow` 룰 카탈로그 보강 7필드 + STR tipping-off 플래그 신설(코드=truth, aegis-aml feature/aml-scenario-detail-conditions).** `GET /api/v1/bo/aml/stats/scenarios` 응답 행에 `family`·`reasonCode`·`evaluationMode`·`actions[]`·`naturalLanguage`·`source`·`conditions[]`(+`strRestricted`)를 **additive** 로 실어, ② 룰 효과성 행▶ 시나리오 상세 화면이 룰 상세(§2.7 `report-rules/{ruleCode}`)와 **같은 발동 조건·임계**를 표시하도록 한다. 보강 근거는 `scenarioCode` ≡ 룰 코드(알림 집계 어댑터가 `ruleCode`/폴백 `scenario_code` 로 폴딩, §3.4a v9.21)이고, `conditions[]`는 §3.6a 와 **동일 생산자**(BUILT_IN=resolved 카탈로그 파라미터 / CUSTOM=safe DSL leaf)를 재사용한다. 설정형 룰(`AML_SIM_*` 등)은 코드 접두로 룰군을 파생할 수 없어 **`family` 는 서버가 정본**이다. 카탈로그·설정형 미등재 고아 코드는 보강 7필드 전부 생략(`NON_NULL` — 합성 금지), 엔진 설정형 조회 실패 시에도 집계는 그대로 내려간다. **STR 은 §2.7 `report-rules?family=STR` 과 동일한 전담(COMPLIANCE) 게이트** — 비전담은 보강 필드 미노출 + `strRestricted=true`(집계·엔드포인트·스코프·4-eyes 계약 무변경). | aegis-java-implementer. 코드=truth. 근거=bo-api `aml/stats/dto/StatsDtos.ScenarioRow`·`aml/stats/service/AmlStatsService`(ScenarioMetaContext·builtInRule·loadCustomRules)·`aml/stats/controller/AmlStatsController`(principal 전달), 테스트 `AmlStatsScenarioRuleMetaTest`·`AmlStatsScenarioRuleMetaWebMvcTest`. 기능정의서 §12-B.3 BR-009(v9.57) 동기화. |
| 2026-08-06 | **알림 오탐 종결 자유 메모 보조 저장·회수 역전파(코드=truth, aegis-aml fix/tm-dismiss-note-and-hrr-labels).** (1) **§2.5a `POST /api/v1/bo/aml/alerts/{alertId}:dismiss` 바디 확장** — `AlertDismissRequest{reason 필수(@NotBlank), actor?, note?(@Size≤1000)}`. `note`(판단 근거 자유 메모, 기능정의서 §7.1 BR-002a)는 **엔진에 싣지 않고 bo-api 감사 `AML_ALERT_DISMISSED` detail 에 보조 저장**한다 — 엔진 `:dismiss` 계약(§2.4)이 `{reason, actor}` 뿐이고 `aml_alerts.disposition_reason` 은 코드 컬럼(VARCHAR(64))이라 자유 텍스트를 담을 자리가 없다(FDS 기능정의서 §11.2 BR-007·DB §4.11 "코드와 분리 보조 저장" 동형). 공백만 입력한 메모는 detail 에 키 미생성. (2) **§3.4a `dispositionNote` 행 신설** — bo-api **단건 상세 한정 파생 필드**(엔진 미보유)로, 상세 조회 시 bo-api 가 위 감사 항목에서 회수해 싣는다. `DISMISSED`+메모 보유 건에만 non-null, 목록 `AlertSummary` 는 미탑재(코드 축만), 감사 조회 실패 시 null fail-soft. 엔진(aml-svc)·DB 마이그레이션 **diff 0**(신규 컬럼 없음). | aegis-web/java-implementer. 코드=truth. 근거=bo-api `aml/tm/dto/TmDtos`(AlertDismissRequest.note·AlertDetail.dispositionNote)·`aml/tm/service/AmlTmService`(auditLifecycle note·withDispositionNote)·`audit/service/AuditLogService.latestSubjectDetail`, bo-web `components/aml/AmlTmAlertDetailSections`(DispositionSection)·`lib/aml-tm`·messages ko/en. plan §02 §7.1 BR-002a 동기화. |
| 2026-08-05 | **룰 개요 draftCount 정직화 · TM 목록 근거요약 설정형 폴백 역전파(코드=truth, aegis-aml `fix/bo-stats-tm-summary-i18n` — verify-V2 N-1·N-2).** (1) **§3.6a·§2.7** — `ReportRuleOverviewRow.draftCount` 를 **nullable** 로 정정(`null`=집계 불가). 직전 계약의 "위임 경로 honest 0" 은 화면에서 "발동한 초안 없음"으로 오독됐고, 그 0 에 매인 `tuningRecommended` (ACTIVE 룰 `draftCount>=5`)가 BUILT_IN 전건 **항상 false** 로 사문화됐다. 룰별 DRAFT 귀속의 대체 정본 경로는 없음을 확인했다 — 엔진 `ReportSummary` 에 룰코드 부재(목록 `reportPayload={}` 실측), `ScenarioAggregate.reportCount` 는 `status=STR_RECOMMENDED` 알림 수(퍼널 B leg)라 DRAFT 귀속이 아님. → 0 대신 null + 화면 "집계 불가" 표기, `tuningRecommended` 는 **BUILT_IN·CUSTOM 공통 알림 lifecycle 휴리스틱**으로 통일. (2) **§3.4a** — `AggregationSummary` 의 설정형 룰 폴백 파생 명문화(`strIndicator ← trigger.strReasonCode`, `dominantChannel`/`currency ← features.*`). 설정형 알림 101/188건이 목록 근거요약 없음(`-`)으로 렌더되던 bo-api 파생 드리프트 해소 — 엔진 무변경, 집계 수치는 미합성. 엔드포인트·DTO 스키마 그 외 불변. | 코드 truth=bo-api `AmlStatsService`(`overviewRow`·`tuningRecommended`)·`AmlTmService#aggregationSummaryFromEvidence`. 회귀 `AmlStatsServiceTest#reportRuleOverviewReportsDraftCountUnavailableOnDelegatedBatch`·`#reportRuleOverviewRecommendsTuningFromAlertLifecycleForBuiltInRules`·`AmlTmServiceConfigurableAggregationSummaryTest`(5건). 엔진·DB 스키마 불변 |
| 2026-08-05 | **§3.7 결재 응답 `detail` 확장(HIGH_RISK_REGISTRY 변경 요약·목록 동봉) + §2.7/§3.6a `draftCount` nullable 기준 통일(코드=truth, aegis-aml fix/ra-review-due-monotonic-and-audit).** (1) **§3.7 `detail`** — `HIGH_RISK_REGISTRY` 결재는 staged payload 에서 **적용 결과 스냅샷**(`v<version> · PRODUCT=n · VASP=n · HIGH_NET_WORTH=n · PEP_INDIVIDUALS=n · RA_HIGH_RISK_CUSTOMERS=n`)을 파생하며, 이 값은 `ApprovalDetail` 뿐 아니라 **`ApprovalSummary`(목록)** 에도 실린다 — 승인 히스토리(기능정의서 §12-B.6 ③)가 대상 `UPDATE|<version>` 만으로 무엇이 바뀐 결재인지 식별하지 못하던 감사 추적성 결함 해소. 파생 소스 없는 subjectType·구 엔진은 `null`. 문자열은 코드+숫자만이라 로케일 중립. **한계 각주 신설** — 결재 행에 변경 전 상태가 없어 항목 단위 add/remove diff 는 산출 불가(결과 스냅샷 대체). (2) **§2.7·§3.6a `ReportRuleOverviewRow.draftCount`** — BUILT_IN·CUSTOM **동일 기준**으로 정정: 엔진 위임 배치는 보고 목록이 발동 룰코드를 싣지 않아 룰별 DRAFT 귀속 불가 → `null`('집계 불가'), 비위임(local/CI)은 라이브 store 실집계. 종전 CUSTOM 고정 `0` 은 '발동한 초안 없음' 오독을 유발(같은 열에서 판정 기준 분기). **응답 필드 additive·엔드포인트/스코프/4-eyes 계약 무변경.** | aegis-java-implementer. 코드=truth. 근거=aml-svc `adapter/in/rest/{HighRiskRegistryApprovalDigest,ApprovalController}`(ApprovalSummary.detail·toDetail HIGH_RISK_REGISTRY 분기), bo-api `aml/approval/service/AmlApprovalService#fromEngineSummary`·`aml/stats/service/AmlStatsService#customOverviewRows`, bo-web `components/aml/AmlHighRiskRegistry`. 기능정의서 §12-A.5 BR-003·§12-B.6 BR-004(v9.56) 동기화. |
| 2026-08-05 | **룰 개요 발동 카운트 원천 교정 역전파(코드=truth, fix/bo-api-stats-fds-wlf-mappers — F-1 stub↔engine 드리프트).** §3.6a·§2.7 BFF 註 — `GET /api/v1/bo/aml/stats/report-rules` 의 `hitCount30d` 를 **BUILT_IN·CUSTOM 공통으로 실제 `aml_alerts.scenario_code` lifecycle 집계**(엔진 `GET /aml/alerts` 룰코드별 fold, period 창)로 정정. 직전 계약(BUILT_IN=라이브 DRAFT store `firedRules` 집계)은 엔진 위임 배치에서 store 가 비어 있고 엔진 보고 payload 가 `firedRules` 키를 쓰지 않아(CTR=`ruleCode`·STR=`reasonCodes`) BUILT_IN 전건 0 을 내던 드리프트였다(실측: CTR_SINGLE 3·CTR_DAILY 11·STR_STRUCTURED 11 발동에도 0). 알림 집계 미보유 룰코드는 라이브 store fold 폴백, 양쪽 부재 시 0(seed 없음). `draftCount`/`lastFiredAt` 은 **라이브 store 전용**으로 명문화 — 엔진 `ReportSummary`(§2.7)가 행에 발동 룰코드를 싣지 않아 위임 경로 룰별 보고 귀속 불가(honest 0/null, 룰코드 투영은 미구현·예정). 엔드포인트·DTO 스키마 불변(필드값 원천만 교정). | 코드 truth=bo-api `aml/stats/service/AmlStatsService`(`alertAggregatesByRuleCode`·`overviewRow`). 회귀 `AmlStatsServiceTest#reportRuleOverviewCountsBuiltInHitsFromEngineAlertAggregates`·`#reportRuleOverviewKeepsHonestZeroWhenRuleNeverFired`. 엔진·DB 스키마 불변 |
| 2026-08-05 | **TM 알림 오탐 종결 사유·처리자 bo-api 투영 역전파(코드=truth, fix/tm-disposition-reason-passthrough — T7R N-8 정정).** 엔진 `AlertDto` 는 이미 `dispositionReason`/`dispositionActor` 를 목록·상세·처분응답 3경로에 실었으나 bo-api 가 역직렬화 단계(`AmlTmService$EngineAlert`)에서 두 필드를 버려 **종결 사유가 쓰기 전용**(입력 후 어디에서도 회수 불가)이었다. (1) **§3.4a `dispositionReason`/`dispositionActor`** — bo-api 가 `AlertSummary`(사유)·`AlertDetail`(사유+처리자)·`AlertActionResponse`(사유 에코)로 verbatim passthrough 함을 명문화. (2) **§2.5a `:triage`/`:dismiss` 위임 행** — `AlertActionResponse` 형상에 `dispositionReason?` 추가(`:dismiss` 전용 에코 — 엔진 응답 우선·엔진 미탑재 시 요청 `reason` 폴백, `:triage`/`:escalate`/`:recommend-str` 은 null·NON_NULL 생략). **엔진 API·DB(V30)·불변식(DISMISSED 전이 한정 non-null)·감사 계약은 무변경**(bo-api 투영 결손만 해소, additive). | 코드 truth=bo-api `aml/tm/service/AmlTmService`(EngineAlert 컴포넌트 14→16·fromEngineSummary/fromEngineDetail·dismissAlert 에코·stub `recordLiveDisposition`)·`aml/tm/dto/TmDtos`(AlertSummary/AlertDetail/AlertActionResponse), bo-web `components/aml/AmlTmAlertDetailSections`(DispositionSection)·`AmlTmAlerts`(목록 상태 칸)·`messages/bundles/{ko,en}/aml-monitoring.json`. 회귀=`AmlTmServiceDispositionReasonTest`·`AmlTmAlertDetailSections.disposition.test.tsx`·`AmlTmAlerts.disposition.test.tsx`. 기능정의서 §12-A AML-TM-001/알림 상세 동기화. 사용자 지시로 완료요건 F-021 잠금 해제(잠금 테스트는 리플렉션 인자 수만 보정·계약 무변경). |
| 2026-08-03 | **dilisense AML Database 소스 임포트 완결 역전파(F-024 잔여분 완결 — U7, feature/dilisense-source-import-completion).** §10 watchlist-sources sync 절을 코드 7종(`OFAC_SDN`·`UN_CONSOLIDATED`·`EU_CFSL`·`UK_OFSI`·`AU_DFAT`·`JP_MOF_FEFTA`·`DILISENSE_CONSOLIDATED`) 나열로 갱신 + `DILISENSE_CONSOLIDATED` API 키 미설정 시 `outcome=FAILED`(비-mandatory·스크리닝 비차단) 계약 1문장 추가. | 코드 truth=`WatchlistFeedRouter`·`DilisenseConsolidatedFeedAdapter`·`SanctionsImportScheduler`. DB §·integration §7.4 동기화(같은 커밋). |
| 2026-08-05 | **STR 보고 기한 확정 시점 명문화 + TM 알럿 `ruleCode` 자유형 계약 정합 역전파(코드=truth, fix/bo-str-draft-link-and-tm-rulecode).** (1) **§3.6 `reportDeadlineAt`** — `STR`=의심확정(트리거)일 +5영업일이 **STR DRAFT 개설 시점에 freeze** 됨을 명시(`RegulatoryReport.strDraft(... dueAt)`, `StrEvaluationService` 가 `BankingCalendarPort` 로 CTR 과 동일한 `BankingCalendar.dueAt` 경로 사용 — STR 전용 산식 없음; 사유 누적은 기한 불변; 배선 이전 legacy 행은 `null`). 종전 코드는 `strDraft()` 가 `due_at` 을 세팅하지 않아 제출·접수 이후까지 NULL 이던 BR-011 위반이었다. (2) **§3.4a `AlertDto.ruleCode` 계약 재확인** — 법정 카탈로그 10종뿐 아니라 **설정형(configurable) 룰의 자유형 코드**(예 `AML_SIM_STR_DEVICE_OS`)도 그대로 실린다(엔진 `AlertDto.ruleCode = Alert.getScenarioCode()`, F-026 자유형 전환). bo-api 위임 매퍼가 이 자유형 코드를 enum 파싱 실패로 드롭해 `/aml/tm` 목록·상세가 `null` 을 받던 드리프트를 수정(엔진 응답 계약 무변경 — bo-api 매퍼만 엔진 실제 필드에 정합). (3) **§2.7 `POST .../reports/str-drafts`** — bo-web 화면 접점(기능정의서 §12-A.7 BR-002 `[STR 보고서 작성]`)이 실제로 배선되어 케이스↔STR `caseId` 계보가 목록·딥링크(`?amlCaseRef=`)에서 성립한다. **엔드포인트·요청/응답 필드 신설 없음.** | 코드=truth. 근거=aml-svc `domain/report/RegulatoryReport#strDraft`·`application/usecase/StrEvaluationService#strDueAt`, bo-api `aml/tm/service/AmlTmService#engineRuleCode`·`aml/reports/service/AmlReportService#draftStrForCase`, bo-web `components/aml/AmlCaseDetail`. DB §3.12·기능정의서 §9.1 BR-011/§12-A.7 BR-002 동기화. |
| 2026-08-02 | **TM 시나리오 activate — 기존 dsl 원문 보존·차등 임계 왕복 복원 API 역전파(코드=truth, fix/tm-scenario-dsl-preserve-thresholds — FX-U1·FX-U2 QA 이격 정정).** 20260801 자유형 전환 시 미구현으로 남았던 결함 2건을 해소하고 §3.4c/§2.5a/§2.7 서술을 코드와 재일치. (1) **§3.4c `CriterionField.thresholdsByGrade` 컴파일 규칙 세분화** — 기존 정의 편집(`:activate`)은 활성 버전의 엔진 `dsl` 원문을 보존(velocity `thresholds` 무손실 운반)하고 `parameters` 만 갱신, 최초 저작(정의 0건)은 generic fallback 이 `velocity` 노드를 합성하지 않으므로 `thresholds`/`thresholdsByGrade` 도 dsl 로 컴파일되지 않는다(구조 DSL 저작은 aml-svc `POST /admin/aml/tm-scenarios` draft 전용, 원 PLAN Q6). `decode` 가 평탄 `<key>.thresholds.<GRADE>` 키를 `thresholdsByGrade` 로 복원하는 §3.4c 953행 계약은 `ScenarioDslCodec.decode` 2-pass 구현으로 재일치(서술 유지). (2) **§2.5a `GET /bo/aml/tm-scenarios/{scenarioCode}`** — read model 의 active `dsl` 이 `:activate` read-back 의 원문 보존 입력임을 1줄 추가. (3) **§2.7 `:activate`** — bo-api BFF 위임이 draft POST 전 `GET .../tm-scenarios?scenarioCode=` 로 기존 버전(ACTIVE 우선·없으면 최신)을 read-back 하는 3-call 시퀀스(GET→draft→`:activate`)임을 명시. | 코드 truth=bo-api `aml/tm/scenario/ScenarioDslCodec`(decode 2-pass thresholdsByGrade 복원)·`aml/tm/service/AmlTmService`(activate 기존 dsl read-back·`activeOf` 헬퍼 3곳 공용화). 엔진 접촉(STR, CTR) — 케이스 재검증 대상. 원 PLAN=`docs/ai/plans/20260801-remove-legacy-tm-scenarios.md`§U4/Q6, 수정 PLAN=`docs/ai/plans/fix-20260802-tm-scenario-dsl-preserve-thresholds.md`. |
| 2026-08-01 | **레거시 TM 시나리오 정의 10종 제거 + 자유형 코드 전환 API 역전파(코드=truth, refactor/remove-legacy-tm-scenarios).** v9.21 확정 사실(TM 알림 발동 정본=CTR/STR 룰 카탈로그, F-025 실측)에 따라 정의 10종을 제거한 코드 변경(DB §7 V61)을 API 계약에 정합화. (1) **§2.5a `GET /bo/aml/tm-scenarios/{scenarioCode}`** — generic decode(per-code 템플릿 `ScenarioTemplates` 삭제)·정의 부재=404 로 서술 갱신. (2) **§2.7 `GET /admin/aml/tm-scenarios`** — `scenarioCode` 파라미터 **optional 화(additive)**, 미지정 시 테넌트 전체 list-all(신설 `TmScenarioStorePort.findAll`, `findAllActive`는 원래 죽은 메서드라 제거). `:activate` 행에 자유형 코드 형식·예약어(`CUSTOM_RULE`) 거부 명시. (3) **§3.4c `ScenarioDefinition`/`CriterionField`** — `scenarioCode` 자유형·`displayName`=코드 원문(레거시 라벨 카탈로그 폐기, 필드 자체는 계약 유지)·`family`=dsl `velocity` 노드 존재 파생·`fields[]`=`parameters` 값 타입(Boolean/Number/List/그 외) generic 파생 명시. (4) **§3.4a TM feature 신호·TM 시나리오 카탈로그(구 816·824~840행)** — 레거시 10종 표·phpEquivalent 임계표를 "V61 로 제거된 과거 사실"로 교체, 신규 자유형 저작도 자동 발동하지 않음을 재확인. **`ck_aml_alerts_scenario_code`(§3.10)·CTR/STR 룰 카탈로그·`AlertDto` 계약은 무변경.** | 코드 truth=aml-svc `adapter/in/rest/TmScenarioAdminController`·`application/port/out/TmScenarioStorePort`(findAll 신설)·`application/usecase/TmScenarioService`, bo-api `aml/tm/service/AmlTmService`(listScenarios·getDefinition)·`aml/tm/scenario/ScenarioDslCodec`(generic decode/compile/familyOf). DB §3.10a/§5.6/§7 V61 동기화. |
| 2026-07-29 | **WLF 이름 강한 일치 검토 승격(escalation floor, additive) 역전파.** §3.2 — `reasonCodes` 행에 `NAME_HIGH_CONFIDENCE`(이름 성분 ≥ `highConfidenceThreshold`·negative 0 일 때 overall 미달을 승격시킨 사유코드) 병기, `scoreBreakdown` 행에 승격 결과 한정 감사 스냅샷 `nameEscalation{applied,nameScore,threshold}` 주석 추가, `appliedPolicy.confidenceBand` 서술에 승격 시 `REVIEW` 승격·`AUTO_DISCOUNTED` 우선 1줄 및 simulate(WLF-004) 미적용 구분 명기. 엔드포인트·필드 스키마 자체는 불변(additive 값만). | 코드 truth=aml-svc WLF 스코어링 엔진. 엔진 케이스 카탈로그 WLF-C18(`docs/qa/engine-rule-cases.md`) 신규 검증. 소프트웨어 설계서 §10.3a·기능정의서 §12-B.8 BR-004 동일 작업 단위 개정 |
| 2026-07-28 | **WLF 스크리닝 신규 insert 응답 `createdAt` non-null 보장 역전파(코드=truth, fix/wlf-freshness-createdat, additive).** §3.2 `ScreeningResponse.createdAt` 행 — 신규 영속 결과(`POST /api/v1/aml/screen` 유효 Idempotency-Key insert 경로) non-null 보장(insert 후 DB `created_at` read-back, `ScreeningResultInserter` saveAndFlush+refresh)·신규/replay 응답 대칭, `/internal/v1/aml/screen` 동형 포괄. null 가능은 미영속(simulate 등)·blank Idempotency-Key 경로 한정으로 축소 명확화. 엔드포인트·DTO 스키마 불변(응답 필드값 population 만 보강). | 코드 truth=aml-svc `adapter/out/persistence/{ScreeningResultInserter,ScreeningResultJpaAdapter}#insertIdempotent`. 엔진 케이스 카탈로그 WLF-C17(`docs/qa/engine-rule-cases.md`) 신규 검증. bo-web `/aml/wlf` 3탭 목록 신선도(수동 새로고침+30초 자동 갱신·창 포커스 재조회) 동반 역전파는 기능정의서(02-aml-sass-functional-spec.md) §3.1 참조 |
| 2026-07-24 | **설정형(configurable) STR/CTR 룰 알림 evidence `trigger.condition` additive 역전파(코드=truth, feature/aml-str-rule-detail-condition, v9.36).** (1) **§3.4a `ruleCode` 행** — custom evidence 병기 필드에 `condition`(룰 DSL 조건식의 사람이 읽는 요약) 추가. (2) **§3.4a `evidence` 행 ① 트리거** — 설정형 룰 발동 알림 변형 `{ ruleCode, ruleFamily(STR\|CTR), ruleVersion, ruleSource=CUSTOM, description, strReasonCode(STR만), condition }` 명문화 + `condition` 의 locale 중립(영문 연산자 토큰) 결정적 문법·저장 시점 고정(감사 재현성·번역 대상 아님)·요약 실패 시 키 생략(fail-safe, 발동 판정·영속 영향 0) 계약, evidence 최상위 `features`(관측 피처 스냅샷·비PII whitelist 키)·`parameters`·`policyPack` 동반 명기, 법정 카탈로그 룰(STR8/CTR2) 트리거 **무변경**(`condition` 미탑재) 재확인. 발동 로직·임계·기존 evidence 키 무변경(additive only) — DDL/DTO 스키마 불변(JSONB 내부 확장). | 코드 truth=aml-svc `application/usecase/ConfigurableReportRuleEvaluationService.evidence()`·`domain/tm/ConfigurableRuleDslSummarizer`(신규 요약 포매터), bo-api `aml/tm/service/AmlTmService.fromEngineDetail`(trigger verbatim passthrough — 회귀 `AmlTmServiceEvidenceTriggerPassthroughTest`), bo-web `lib/aml-tm.ts`(`AmlEvidenceTrigger` additive 4필드·`ruleSourceLabel`/`ruleFamilyLabel`)·`components/aml/AmlTmAlertDetailSections.tsx`(TriggerSection 분류·조건·버전 행 + FeatureParameterSection). 엔진 케이스 카탈로그 STR-C12(`docs/qa/engine-rule-cases.md`) 검증, STR-C01~C11·CTR 전건 재PASS 로 발동 반전 없음 실증. DB §3.10 evidence 동기화 |
| 2026-07-24 | **CDD 인입 요청별 콜백 URL + HRR_REGISTRATION 승인 완료 아웃바운드 콜백 신설(코드=truth, feature/aml-cdd-hrr-approval-callback).** (1) **`docs/aml-data.md` §12.1 envelope 에 옵션 필드 `callbackUrl` 신설** — `customer.cdd.completed` 전용, `mandatoryHighRisk=false` 인 CDD 는 무시(에러 아님). (2) **§8.1 에 4번째 webhook 이벤트 `AmlHighRiskRegistrationApproved` 신설** — `HRR_REGISTRATION`(당연고위험 등재) 4-eyes 승인 EXECUTED 시에만 발행(거절 시 미발행), payload `{memberRef,approvalId,decision,tier,checkerId,approvedAt}`. (3) **§8 SSRF 정책 문단에 목적지 원천 예외 명문화** — 기존 3종(screening/case/report)은 테넌트 사전등록 `aml_api_credentials.webhook_url` 로 발행하지만, 이 신규 이벤트는 **CDD 요청이 실어 보낸 요청별 URL** 로 직접 발행(테넌트 사전등록 URL 아님) — 서명 시크릿만 여전히 테넌트 소유, SSRF 3단계 검증은 예외 없이 동일 적용. (4) `aml_canonical_events`/`aml_approvals`/`aml_outbox` 3개 테이블에 nullable 컬럼 3종 추가(Flyway V59, DB §마이그레이션 동기화). 엔진 RA 케이스 카탈로그 RA-C12(`docs/qa/engine-rule-cases.md`) 신설·검증. | 코드 truth=aml-svc `adapter/in/rest/AmlEventController`·`application/{port/in/{IngestAmlEventUseCase,AssessRiskUseCase,RegisterHighRiskCustomerUseCase},usecase/{AmlEventIngestService,OnboardingRaDerivationService,RiskAssessmentService,HighRiskCustomerRegistrationService,ApprovalDispatchService,WebhookOutboxEmitter},port/out/{CanonicalEventStorePort,OutboxStorePort,WebhookEndpointPort}}`·`adapter/{in/scheduled/OnboardingRaRetryScheduler,out/{persistence/{CanonicalEventJpaAdapter,ApprovalJpaAdapter,OutboxJpaAdapter,ApiCredentialJpaRepository,WebhookEndpointJpaAdapter},webhook/HttpWebhookRelayAdapter}}`·`db/migration/V59__hrr_registration_callback.sql`. `docs/aml-data.md` §12.1·DB §02-aml-db.md §마이그레이션 동기화. PLAN 20260724-cdd-hrr-approval-callback |
| 2026-07-24 | **워치리스트(제재) 실 공개 소스 4종 신규 추가 역전파(코드=truth, feature/aml-watchlist-4-sanctions-sources U15).** **§2.4 `POST .../watchlist-sources/{sourceCode}/sync` 표 설명 확장** — 대상 소스를 "OFAC SDN·UN Consolidated" 2종에서 **"OFAC SDN·UN Consolidated·EU Consolidated Financial Sanctions·UK OFSI·Australia DFAT·Japan MOF(FEFTA)" 6종**으로 확장, 파싱 방식 병기(OFAC/UN/EU/UK=StAX XML, AU=xlsx, JP=2단계 discovery 후 CSV), 스케줄러 일일 자동 대상을 6개 소스 순차로 갱신. 엔드포인트 URL·요청/응답 스키마(`WatchlistSyncResult`)·auto-apply/freshness 계약은 **1도 변경 없음**(real-sanctions-daily-import 아키텍처 그대로 확장). WLF 스크리닝(`POST /api/v1/aml/screen`) 계약도 무변경(후보 풀만 확대). WLF-C10(신규 4소스) 엔진 케이스 신설 대상. | 코드 truth=aml-svc `adapter/in/scheduled/SanctionsImportScheduler`(6-source 목록)·`adapter/out/feed/{EuCfslFeedAdapter,UkOfsiFeedAdapter,AuDfatFeedAdapter,JpMofFeftaFeedAdapter,WatchlistFeedRouter}`·`db/migration/V60__eu_uk_au_jp_sanctions_watchlist_sources.sql`. DB §7 V60·integration §7.4 동기화 |
| 2026-07-22 | **§2.7 `GET /admin/aml/risk-scores` operativePerTarget 신설 — 고위험/EDD 탭 operative 통일(코드=truth, feature/ra-high-risk-tab-operative-parity, F-018 후속).** `operativePerTarget`(boolean, 기본 false, additive) 파라미터 신설 — true 시 회원(targetRef)별 정확히 1행 = operative 점수(상시평가(ONGOING) 점수 보유 시 최신 ONGOING, 없으면 최신 전체=최신 온보딩(ONBOARDING), §2.3 상세 operative 선정과 동일 규칙). 선정 먼저·상태 필터(등급·조치·임박·국가·당연고위험·`modelVersion`·`scenario`) outer 적용("현재 상태" 목록 의미론, `latestPerTarget` 동형), `count`/`items` 동일 술어, 동률은 `scoreId` 문자열 내림차순 결정적. `latestPerTarget` 와 동시 지정 시 `operativePerTarget` 우선(엔진 usecase 정규화). bo-api `GET /api/v1/bo/aml/risk-scores` pass-through 위임(stub 경로는 target 당 1행이라 no-op). `/aml/ra` 고위험·EDD 탭이 이 모드로 RA 상세와 등급/점수 파리티를 이룬다. 산정(scoring) 로직·Flyway·기존 응답 필드 무변경(additive). | 코드 truth=aml-svc `adapter/out/persistence/{RiskScoreJpaRepository,RiskScoreJpaAdapter}`·`application/port/out/RiskScoreStorePort`·`application/port/in/AssessRiskUseCase`·`application/usecase/RiskAssessmentService`·`adapter/in/rest/RiskScoreAdminController`, bo-api `aml/ra/{service/AmlRaService,controller/AmlRiskReadController}`, bo-web `hooks/useAmlRisk.ts`·`components/aml/AmlRiskMonitoring.tsx`. 엔진 케이스 카탈로그 RA-C11(`docs/qa/engine-rule-cases.md`) 검증. |
| 2026-07-22 | **RA 평가구분 "TM 진입 시 2차 고정" stage-aware operative 선정 + `excludeOngoingTargets` 목록 필터 역전파(코드=truth, feature/ra-tm-2nd-stage-fixed-scenario-consistency, F-017 후속).** (1) **§2.3 `GET /api/v1/aml/customers/{ref}/risk`** — 유효 평가 선정 규칙을 구 "최신 evaluated_at=유효 등급" 에서 **stage-aware operative 선정**(상시평가(ONGOING) 점수가 이력에 하나라도 있으면 최신 ONGOING 점수, 없으면 최신 온보딩(ONBOARDING) 점수 — 온보딩 모델 재평가(system 재점수)가 상시평가 진입 대상을 1차로 되돌리지 않음)으로 정정. `onboardingReview` 보조 블록 계약 무변경. (2) **§2.6** `internal .../customers/{ref}/risk`(fds-svc 호출) 도 동형 규칙 명기(가정 B1, "FDS 가 보는 등급 = 화면 등급" 단일 정본). (3) **§2.7 `GET /admin/aml/risk-scores`** 에 **`excludeOngoingTargets`**(boolean, 기본 false, additive) 파라미터 신설 — true 시 상시평가(ONGOING) 점수 보유 target 의 전 행 제외(target 단위 술어, `scenario` 필터와 직교); 1차 탭은 `scenario=ONBOARDING&excludeOngoingTargets=true` 조합 사용. bo-api `GET /api/v1/bo/aml/risk-scores` pass-through 위임, stub 경로는 no-op. **(4) §3.9 `CustomerProfileDto.latestRiskScore`**(GET `/evidence/aml/customers/{ref}/profile`, `EvidenceTimelineService#customerProfile`) 도 동일 operative 선정으로 정정(구 `findLatestByTarget`=최신 전체 → `findOperativeForTarget`) — 프로필 `riskSummary`↔RA 상세(§2.3/§3.3) 점수/등급 단일 정본(RA-C10 라이브 검증에서 profile 45.83 ↔ RA read 83.75 불일치로 발견·수정). 산정(scoring) 로직·Flyway·응답 필드·기존 파라미터 무변경(additive). | 코드 truth=aml-svc `application/port/in/AssessRiskUseCase#findOperativeForTarget`·`application/usecase/EvidenceTimelineService`·`application/usecase/RiskAssessmentService`·`adapter/in/rest/{CustomerRiskController,CustomerRiskInternalController,RiskScoreAdminController}`·`adapter/out/persistence/{RiskScoreJpaAdapter,RiskScoreJpaRepository}`, bo-api `aml/ra/{controller/AmlRiskReadController,service/AmlRaService}`, bo-web `hooks/useAmlRisk.ts`·`components/aml/AmlRiskMonitoring.tsx`. 엔진 케이스 카탈로그 RA-C10(`docs/qa/engine-rule-cases.md`) 검증. |
| 2026-07-22 | **§2.7 `GET /api/v1/bo/aml/risk-scores`(bo-api 위임) 응답 페이지 봉투 명문화(코드=truth, feature/ra-i18n-raw-key-and-stage-label-consistency, QA 이격 정정 fix/20260722-ra-c09-list-envelope-spotless).** bo-api 응답도 엔진 목록과 동일 페이지 봉투 `{ data: { items, page, size, total } }`(§1.2 envelope)를 반환함을 §2.7 `risk-scores` 행에 명문화. `total` 산식을 경로별로 구분 — **위임(delegate) 경로**는 엔진 봉투 `total` 을 그대로 passthrough(엔진 무응답 시 빈 봉투 `total=0`), **stub 경로**는 전수 스캔 불가(윈도우 스캔 구조)라 `page*size + 이번 페이지 rows 건수`의 best-effort 하한(정확한 전체 건수 아님)으로 산출함을 주석 처리 — 종전 문서 미정의 지점 해소(코드=truth 역전파). API 계약 필드·엔드포인트 무변경. | 코드 truth=bo-api `aml/ra/controller/AmlRiskReadController#riskScores`·`aml/ra/dto/RaDtos.RiskScorePage`·`aml/ra/service/AmlRaService#riskScorePage`, bo-web `hooks/useAmlRisk.ts`. |
| 2026-07-22 | **RA `scenario`/`reassessmentAlerts`/`reviewShortened` 엔진 explicit 동봉 역전파(코드=truth, feature/ra-i18n-raw-key-and-stage-label-consistency).** §3.3 `RiskScoreResponse` 3필드 서술을 "엔진 응답에 값이 없으면 bo-api 가 파생"에서 **"엔진(aml-svc `RiskScoreAdminController`·`CustomerRiskController`)이 `factorBreakdown.{scenario,triggerAlerts,reviewShortened}` 마커에서 직접 파생해 목록·상세 응답에 explicit 필드로 동봉(`RiskScoreScenarioProjection`), bo-api(`AmlRaService.fromEngineRisk`)는 explicit 값 우선·구엔진(explicit 부재) 한정 자체 마커 파생 폴백"** 으로 정정 — 목록(③ 고위험 목록 등)·상세 간 평가구분(scenario) 파리티 이행(엔진 케이스 RA-C09). API 계약 필드·타입 무변경(additive 구현 정합). | 코드 truth=aml-svc `adapter/in/rest/support/RiskScoreScenarioProjection`·`RiskScoreAdminController.RiskScoreResponse`·`CustomerRiskController.CustomerRiskResponse`, bo-api `aml/ra/service/AmlRaService.fromEngineRisk`·`aml/ra/dto/RaDtos.EngineCustomerRisk`. 기능정의서 §5.1/§12-A.4 동기화(같은 작업 단위) |
| 2026-07-21 | **AMLC lodge 트랜잭션 경계 분리(QA 발견 H1 수정, 코드=truth, fix/amlc-lodge-transaction-boundary).** (1) **§3.6 `amlcSubmissionRef`** — API 계약(필드·null 의미)은 무변경이나, 서버측 산출 경로가 승인(approve) 동기 REST 응답 시점이 아니라 **이후 비동기 워커가 채운다**는 점을 명시(값이 즉시 채워지지 않고 이후 폴링/조회 시 채워질 수 있음 — 클라이언트는 폴링 또는 재조회로 확인). (2) 확인번호 저장 전 길이(128자)·형식 검증 추가(M1) — 계약된 필드 형식(영숫자·하이픈·언더스코어·슬래시·마침표, ≤128자) 명시. | 코드 truth=aml-svc `application/usecase/report/AmlcLodgementCoordinator`(신규)·`adapter/out/submission/PlaywrightAmlcSubmissionAdapter`. §3.6 동기화 |
| 2026-07-21 | **AML 보고 제출 KoFIU→AMLC(GoTRACS) 전환 역전파(코드=truth, feature/aml-reports-amlc-migration).** (1) **§2.7 AMLC 계정 관리 하위표 신설** — `GET/PUT /api/v1/admin/aml/amlc-credential`(테넌트별 AMLC 포털 로그인 계정, `aml:case:read`/`update`, 4-eyes 미적용) + bo-api 위임 프록시(`/api/v1/bo/aml/amlc-credential`). (2) **§3.6 `RegulatoryReportDto`에 `amlcSubmissionRef` 필드 추가**(DB V58) — AMLC 포털 실 lodgement 접수번호, `submittedRef`와 별개. (3) **§11.6 정정** — `AmlcSubmissionPort`가 `mode=mock`(결정적 데모)\|`browser`(**`PlaywrightAmlcSubmissionAdapter`**, 브라우저 자동화로 aml-svc가 AMLC 포털에 직접 lodge) 로 분기함을 명시, "ProviderSvc 위임" 구서술을 대체. | 코드 truth=aml-svc `adapter/in/rest/AmlcCredentialAdminController`·`application/usecase/AmlcCredentialAdminService`·`application/port/out/{AmlcCredentialPort,AmlcSubmissionPort}`·`adapter/out/submission/{MockAmlcSubmissionAdapter,PlaywrightAmlcSubmissionAdapter}`·`domain/report/{AmlcCredential,RegulatoryReport}`, bo-api `aml/amlc/{controller/AmlcCredentialController,service/AmlcCredentialService,dto/AmlcCredentialDtos}`. DB §3.12·§3.12b·§7 V57/V58·integration §3.4·기능정의서 동기화. |
| 2026-07-20 | **CDD 1차 RA 인입 데이터 전면 가시화 — read model 신규 필드 역전파(코드=truth, feature/aml-cdd-visibility).** (1) **§3.9 `CustomerProfileDto.kycEvidence`** — 5필드 → 6필드(`kycVerifiedAt` 추가, `kyc.kycVerifiedAt` ISO-8601 verbatim). (2) **§3.9 `CustomerProfileDto.birthYearMasked`** — canonical projection 실값 계약 정정: CDD 인입 시 `dob` 선두 4자리(연도, `1900..현재연도`)를 `kyc_evidence.birthYear` 로 파생·영속해 `YYYY-**-**` 조립(구 "currently null" 서술 폐기, 원문 dob 비영속 유지). (3) **§3.9 `CustomerProfileDto.genderMasked` 신설(string\|null)** — vault 성별 필드 존재 시 고정 토큰 `"***"`(복호화 없이 존재확인만), 원문 read model 비영속·비노출, 열람은 기존 `GENDER` PII-reveal 감사 경로. (4) **bo-api 화면 aggregate 콜아웃 신설** — `CustomerProfile.person.birthYearMasked`·`person.genderMasked`(PERSON 분기 pass-through), top-level `country`·`kycEvidence.kycVerifiedAt` pass-through 명문화. RA 스코어 산식·엔진 룰 무변경(`OnboardingRaDerivationService` CUSTOMER 요인은 `sourceOfFunds`/`kycLevel`/`residenceCountry` 만 소비, additive 키 미소비). DB 스키마 무변경(JSONB `kyc_evidence` 확장). | 코드 truth=aml-svc `application/usecase/{IdentityProjectionService,EvidenceTimelineService}`·`application/port/{in/EvidenceTimelineUseCase,out/CustomerStorePort}`·`adapter/out/persistence/CustomerJpaAdapter`, bo-api `aml/profile/{dto/CustomerProfileDtos,service/AmlCustomerProfileService}`. 엔진 RA 케이스 카탈로그 RA-C08(`docs/qa/engine-rule-cases.md`) 검증. 기능정의서 §12-A.10/§12-B.7 동기화 |
| 2026-07-18 | **단일 호출 응답 판정 동봉(코드=truth, PLAN 20260718-sync-verdict-in-response U4/U6/U9 — 사용자 지시로 F-003 해제).** ① **§2.1/§3.1 CDD 응답 additive 확장** — `POST /api/v1/aml/events` 의 `IngestEventResponse` 에 `mandatoryHighRisk`(boolean\|null)·`mandatoryHighRiskReasons`(string[]\|null)·`wlfHit`(boolean\|null) 3필드 추가(1차 RA 요약, ACCEPTED=방금 산출 스코어·REPLAYED=`scoreId` 조회 동일 스코어에서 파생, HELD/미산정 시 null). 기존 11필드 이름·순서·타입 불변. ② **§2.1a 중립 인입 evaluation 확장·REPLAYED 재구성** — `NeutralIngestResponse.evaluation` 에 `firedAlerts[]`(alertId/ruleCode/severity)·`ctrApplicable`(현금성 게이트, CTR 보고서 확정 자체는 범위 밖)·`strCandidate`(`AmlReportRuleCatalog` 정본 판별) 3필드 additive. **REPLAYED 규칙 반전** — 직전 "REPLAYED/DUPLICATE 는 evaluation=null" 을 "REPLAYED 는 저장 알럿/스크리닝에서 read-only 재구성한 동일 요약 동봉(재평가·side-effect 0), DUPLICATE/REJECTED 는 기존대로 null" 로 재개정. ③ **§3.2 WLF 동기 계약 확인(무변경)** — `POST /api/v1/aml/screen` 이미 동기 단일 응답임을 확인·명문화(WLF-C07, 계약 접촉 없음). 거절 없음 원칙 전 구간 불변 — 판정 동봉은 표시이지 인입 거부가 아니다. 엔드포인트 경로·상태코드·기존 필드 재작성 없음(additive 필드만). | 코드 truth=aml-svc `application/port/in/IngestAmlEventUseCase`(`RiskSummary`)·`application/usecase/AmlEventIngestService`·`adapter/in/rest/AmlEventController`(`IngestEventResponse`), `application/port/in/IngestNeutralTransactionEventUseCase`(`EvaluationSummary.FiredAlert`)·`application/usecase/NeutralTransactionEventService`(REPLAYED 재구성)·`adapter/in/rest/NeutralTransactionEventController`(`EvaluationSummaryDto`/`FiredAlertDto`). 01-fds-api.md v4.18 동반. |
| 2026-07-18 | **AML 설정형 룰 피처 2키 확장·device.locale 결선(코드=truth, PLAN 20260717-fds-legacy-rule-overhaul U-A1/U-A2·U-X1 — FDS 룰 체계 전면 개편 동형, 사용자 지시로 F-005 해제).** (1) **`device` 블록에 `locale` 5번째 필드 추가**(§2.1a·§3.17) — `NeutralDevice` record 5-컴포넌트(`deviceId,os,version,ip,locale`) 확장, 기존 4-인자 생성자는 하위호환 유지(`locale=null`, 잠금 테스트 `DeviceSignalsIngestParityIntegrationTest` 무수정). 설정형 룰 피처 `device.locale` 신규 노출(SCALAR_FEATURES 5키). (2) **`customer.ageYears` 설정형 피처 신설** — `originator.dateOfBirth`→이벤트 시점 만 나이 파생(가정 A2, FDS 동형), DOB 원문 미영속·부재 시 미노출(fail-safe). (3) 두 키 모두 `ConfigurableRuleDslPolicy.SCALAR_FEATURES` additive 등록 — **법정 CTR2·STR8 카탈로그 룰은 불변**(설정형 룰만 조건 피처로 소비 가능). bo-web 카탈로그 등재는 하드코딩 한국어 `displayLabel` 방식(`lib/aml-configurable-rules.ts`, i18n 미전환 — PLAN 가정 A11(b)). Flyway 없음(flat payload jsonb + 코드 whitelist). | 코드 truth=aml-svc `domain/neutral/NeutralDevice`(locale 5-컴포넌트)·`domain/neutral/NeutralEventValidator`(locale ≤16자·제어문자 검증)·`adapter/in/rest/NeutralTransactionEventController`·`application/usecase/NeutralTransactionEventService`(addDeviceSignals·ageYears 파생)·`application/port/in/EvaluateTmUseCase`(ageYears 전달)·`domain/tm/ConfigurableRuleDslPolicy`(SCALAR_FEATURES 2키 추가). bo-web `lib/aml-configurable-rules.ts`. 01-fds-api.md v4.16·01-fds-db.md 동반 |
| 2026-07-17 | **AML 중립 인입 device 공통 블록 확장(코드=truth, PLAN 20260717 U6~U7 — 사용자 지시로 F-005 해제).** (1) **§2.1a Envelope 스키마 표에 `device` 행 신설** — `device{deviceId,os,version,ip}`(전부 optional·string ≤64자·제어문자 금지, 422), flat payload `device` 서브트리(비-null 만) + 설정형 CTR/STR 룰 피처 `device.deviceId`/`device.os`/`device.version`/`device.ip`(`ConfigurableRuleDslPolicy.SCALAR_FEATURES`, 법정 CTR2·STR8 카탈로그 룰 불변) 노출. FDS 인입(01-fds-api.md §5.1 device 공통 블록)과 동형. (2) **§3.17 Device 블록 스키마 표 신설** — 필드 4종 상세, `addDeviceSignals`(externalSignals 결선과 동형 패턴)·재시도 경로(`FanoutRetryService`) 복원 동반. 엔드포인트·scope·기존 응답 계약 무변경(신규 필드 additive). 스키마 무변경(flat payload jsonb+코드 whitelist, Flyway 없음). | 코드 truth=aml-svc `adapter/in/rest/NeutralTransactionEventController`(DeviceDto)·`domain/neutral/{NeutralTransactionEvent,NeutralEventValidator,NeutralDevice}`·`application/usecase/NeutralTransactionEventService`(addDeviceSignals)·`application/port/in/EvaluateTmUseCase`(Device 블록)·`domain/tm/ConfigurableRuleDslPolicy`(SCALAR_FEATURES 4키)·`application/usecase/fanout/FanoutRetryService`(device 서브트리 복원). 01-fds-api.md v4.15·01-fds-db.md v4.9 동반 |
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
