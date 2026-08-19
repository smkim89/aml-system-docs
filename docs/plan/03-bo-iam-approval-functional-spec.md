# BO IAM·결재선 기능정의서 — 사용자·권한·결재라인 관리 (FS-BO-IAM-001)

> 문서 ID FS-BO-IAM-001 · 작성일 2026-06-19 · 소관 `bo-api`(+`bo-web` 화면)
> 대상 시스템: **hanpass-ph(한패스 PH 해외송금) AML/FDS 백오피스의 IAM·승인(4-eyes)**. 본 정의서는 hanpass-ph 운영 백오피스의 사용자·권한·결재선을 다룬다.
> 본 문서는 FDS PRD §16.2·AML PRD §1.6·부록 B/C/G가 "**IAM 화면은 bo-api PRD 소관**"·"**결재선 정의는 bo-api IAM 소관**"으로 deferral 한 미작성 영역을 정본화한다.
> 정본 경계: 인증·세션·RBAC·사용자/역할/결재선 관리는 **bo-api 소유**. 도메인 결재 실행(전이·실행)은 엔진(fds-svc/aml-svc) 소유.
> 멀티테넌시 모델(코드 truth, 유지): **테넌트(`tenant_id`) → 워크스페이스(`workspace_id`)** 의 2계층 격리. 사용자는 테넌트/워크스페이스 스코프로 바인딩하며, 플랫폼 운영자(platformOperator)는 테넌트 비종속(tenant-agnostic). 멀티테넌트 격리·플랫폼 운영자·테넌트 바인딩은 코드 truth로 유지하되, **운영 배포는 hanpass-ph 단일 테넌트(`tenant_demo`, 표시명 "hanpass PH")** 기준이다(가상 다(多)테넌트 예시는 비범위). `tenant_demo`는 SELF_HOSTED 온프레미스·정책팩 `KR_DEFAULT`·보고기관 `HANPASS`(한패스, V26 시드). V28에서 가상 데모 테넌트(은행 A·핀테크 B·소규모 C)는 제거되어 운영 레지스트리는 hanpass-ph 단일. 따라서 `tenant_demo` **ID 단독은 demo fingerprint가 아니며**, Demo/데모 표시명·demo infra ref·알려진 seed identity/provenance가 결합된 경우에만 P0-02 격리 대상으로 판정한다.
>
> 변경 이력:
> - 2026-08-10 — **§2.2-7·§2.4·§6 본인 테넌트 바인딩 조회 신설 — 바인딩 ≥2 비-플랫폼 오퍼레이터 전면 락아웃 해소(코드=truth, aegis-aml main `76681955`)**: 바로 아래 2026-08-10 행이 "기존 미해결"로 남겨둔 `BO-TENANT-REQUIRED` 를 닫는다. **결함의 실제 크기** — 선택기 미노출에 그치지 않고 **바인딩이 2개 이상인 모든 비-플랫폼 오퍼레이터가 로그인 자체를 못 했다**: `TenantContextFilter` 가 `GET /api/v1/bo/auth/me` 까지 테넌트 컨텍스트를 요구해 403 을 내고, 화면 `SessionGuard` 가 그 403 을 받아 세션을 지우고 `/login` 으로 되돌리는 순환이었다(어느 테넌트를 실어야 하는지 알 방법 자체가 없는 순환 의존). **신규 `GET /api/v1/bo/auth/me/tenants`** — **인증만 요구**하고 **principal 본인 바인딩만** 반환하며 응답은 `tenantId`·`workspaceId` **2필드**다(`dataScope` 는 서버가 매칭된 바인딩에서 파생하는 내부 인가 판정이라 **미노출** — 세션이 이미 헤더로 주장할 수 있는 식별자만 싣는다). **필터 allowlist** — `TenantContextFilter` 에 **정확 일치 3경로**(`/api/v1/bo/auth/me`·`/api/v1/bo/auth/me/tenants`·`/api/v1/bo/auth/logout`)를 self-scoped bootstrap 으로 둔다. 세 응답 모두 **인증 principal 만으로 파생**되고 테넌트 스코프 데이터를 읽지 않으므로 기존 `/actuator`("not tenant-scoped") 선례와 동형이며, **접두·와일드카드가 아니라 정확 집합**이다(이 경로 밑에 생길 미래의 테넌트 스코프 엔드포인트가 면제를 상속하지 못한다 — 드리프트 가드 테스트가 집합과 "접두 미매칭"을 고정). **거부 3규칙 무변경** — ① 바인딩 0 → `BO-TENANT-REQUIRED`(M-3 fail-closed, allowlist 판정보다 **선행**) / ② 바인딩 ≥2 + 헤더 없음 → `BO-TENANT-REQUIRED` / ③ 헤더가 어느 바인딩과도 불일치 → `BO-TENANT-FORBIDDEN`. **테넌트 스코프 전 경로에서 그대로**이고 **권한 완화 0**이다(bootstrap 3경로에서만 미해결 컨텍스트가 통과하며, 이때도 헤더 값은 컨텍스트로 신뢰되지 않아 위조 스코프가 성립하지 않는다 — localStorage 의 낡은 `Tenant-Id` 로 회복 경로 자체가 403 되는 클라이언트 락아웃 방지). **화면(§6)** — 헤더 선택기는 `SFDS_TENANT:READ` 미보유 세션에서 이 본인 바인딩을 소스로 **0건 미노출 / 1건 자동선택 / 2건 이상 선택기 노출**(선택 시 `Tenant-Id` 가 실려 ② 거부가 해소)이고, 스코프 보유 세션은 종전 FDS 테넌트 레지스트리 경로를 그대로 쓴다(두 소스 **상호배타 마운트** — 바로 아래 행의 스코프 가드 계약 무변경).
> - 2026-08-10 — **§6 공통 셸 서비스(테넌트) 선택기 조회 스코프 가드(코드=truth, aegis-aml main `8fc131dd`)**: 앱 셸 헤더가 스코프와 무관하게 `GET /api/v1/bo/fds/tenants` 를 호출해 `aml:*` 전용 계정이 **모든 authorized 화면에서 403** 을 유발하던 결함(기능 영향 0 · 콘솔/감사 노이즈)을 닫는다. 서버 `FdsTenantController` `@PreAuthorize("@fdsAuth.has(authentication, 'SFDS_TENANT:READ')")` 와 **1:1 인 클라이언트 가드**(exact `SFDS_TENANT:READ` 또는 wildcard `*` — §3.3-5·§3.3-7 판정 규칙 그대로) 하에서만 조회를 마운트하고, 권한 없는 세션에는 **빈 서비스 선택기를 렌더하지 않는다**("선택할 서비스가 없다"는 거짓 정보 방지). 테넌트 폴백은 **새로 만들지 않았다** — 서버 `TenantContextFilter` 가 "`Tenant-Id` 헤더 없음 + 바인딩 1개 → 그 바인딩이 기본 컨텍스트"를 이미 소유함을 실측하고 회귀 테스트로 고정했다(**서버 코드 변경 0 · 권한 완화 없음** — §2.2-3 바인딩·위조 방지 계약 불변). **잔존(기존 미해결) → 해소됨**: 바인딩이 2개 이상인 AML 전용 계정은 컨텍스트를 확정할 수 없어 `BO-TENANT-REQUIRED` 가 발생하며, 이는 본 가드 이전과 **동일한 기존 상태**였다(본 변경이 만든 결함이 아니며 해소에는 bo-api 변경이 필요 — 후속). **후속은 같은 날 완료** — 바로 위 2026-08-10 행(본인 테넌트 바인딩 조회 `GET /api/v1/bo/auth/me/tenants` + 필터 allowlist 3경로)이 이를 닫았고, 실제 결함 범위는 선택기 미노출이 아니라 **로그인 자체 불가(전면 락아웃)** 였음이 확인됐다
> - 2026-07-20 — **§4.6 결재 상세 표시 컨텍스트(FP_WHITELIST) 신설(코드=truth, fix/wlf-hit-rawdata-approval-context)**: AML-APR-001 결재 상세(공통 결재함, `(연계)` §4.4)에서 `FP_WHITELIST`(오탐 면제 등록) 대상이 subjectRef 파이프 원문 그대로 노출돼 결재자가 대상을 식별할 수 없던 결함을 **bo-web 표시 계층 파싱**으로 해소함을 정본화. `subjectRef`(aml-svc `FpWhitelistService` 조립 원문)·`payloadHash`(subjectRef sha256 잠금)·maker≠checker 4-eyes 계약은 **완전 불변**(aml-svc·bo-api 코드 변경 0) — bo-web 이 순수 함수로 subjectRef 를 파싱해 거래번호·대상유형·스크리닝 대상/명단 기재명(PII reveal 게이트 적용)·룰버전·스크리닝 링크로 재구성 표시할 뿐 결재 데이터 계약을 바꾸지 않는다.
> - 2026-07-13 — **P0-03 FDS capability·request target·exact 결재·감사·trusted actor 경계(bo-api V18, 코드=truth)**: `platformOperator`는 명시 target을 고르는 data-scope 속성일 뿐이며 메뉴·IAM·PII·STR·FDS action 인가를 우회하지 않는다. wildcard `*`/`BO_SUPER_ADMIN`만 우회하고, FDS 운영자 인가는 중앙 `FdsAuthorizationPolicy`의 exact `SFDS_*` capability로 통일해 system/custom scope를 같은 판정에 사용한다. `SFDS_PLATFORM_OPS`는 횡단 read-only이며 action/evidence/approval capability가 없다. action 목록·상세 API는 모두 `SFDS_ACTION:OPERATE`지만 `/fds/actions` 화면은 액션 운영자 또는 capability checker(`SFDS_ACTION:APPROVE`)가 진입하고 두 projection query를 권한별로 분리한다. engine `fds:*` machine scope는 별도 계층이다. header/path/query/body target·trace 길이/제어문자와 충돌을 service 전에 거부한다. FDS `MAPPING` 결재는 immutable `requiredBoCapability`로 source capability/general setting/field mapping의 maker·checker를 구분하고 subject별 목록·상세·결정을 필터하며 `capabilities: []`도 revoke-all 전체교체다. `bo_audit_logs`는 scoped exact-total/stable projection과 typed direct detail을 사용하며 IAM/unknown event는 super-only generic route로 격리한다. signed actor와 AmlTenant onboarding/local fallback approval maker는 principal에서만 파생한다. generic engine passthrough는 삭제하고 typed BFF만 허용하며 FDS local fallback은 active profile 전부가 명시적 `local|demo|test`이고 scope가 `tenant_demo/default`일 때만 허용한다.
> - 2026-07-12 — **P0-02 운영 Flyway demo seed·기본 secret 분리(bo-api V17, 코드=truth)**: 기존 V2/V16은 checksum 불변의 역사로 보존하고 `V17__quarantine_demo_seed_and_credentials`가 알려진 6개 demo identity의 role/tenant binding을 회수한 뒤 `INACTIVE`+`password_hash='!'`로 만들며, Demo/데모 표시명·demo infra 등 복합 fingerprint의 BO AML/FDS tenant·projection/connector를 비활성화한다. 정규 `db/migration` 최종 상태에는 로그인 가능한 demo 사용자가 없고, explicit `demo` profile의 `db/demo/R__activate_demo_reference_configuration.sql`만 `test@test.com` operator와 `choi.exec@aegis.example` checker 및 demo reference tenant/connector를 복원한다. 최초 운영 `BO_SUPER_ADMIN`은 Flyway가 아닌 IdP 또는 production-only OOB bootstrap으로 생성한다. OOB는 opt-in·강한 Base64 일회성 secret·active SUPER_ADMIN 0건·known demo email 금지·완료 marker를 요구하고 계정/자연키 role/감사 3건을 단일 transaction으로 기록하며 반복 실행을 거부한다. BO session secret도 secret manager 주입 강한 Base64만 운영에서 허용하고 public demo/default·`local|demo` 혼합·active demo DB fingerprint를 readiness 전에 거부한다. 기존 API/DTO/화면 계약 변경 없음.
> - 2026-07-12 — **역사 기록 — 데모 고위경영진(EXECUTIVE) checker 계정 보강(bo-api V16, 현행 운영 효과는 위 P0-02 V17이 격리)**: 당연고위험(`HRR_REGISTRATION`, 승인선 `EXECUTIVE_APPROVAL`) 폐루프의 자동상신 결재를 데모에서 승인할 checker 가 부재하던 갭(FDS checker 부재 전례 대칭)을 해소한다. V2 시드의 `choi.exec@aegis.example`(id=6, admin_type=EXECUTIVE)는 `password_hash='!'`(로그인 불가)·역할/테넌트 바인딩 없음이라 어떤 scope 도 획득하지 못했다. bo-api Flyway **V16__demo_executive_checker** — ① 활성 bcrypt 해시(`test1234!`, test@test.com 동일 데모 비밀번호)로 교체·`ACTIVE`(부재 시 upsert), ② `bo_user_roles` 에 **`AML_APPROVER`(`aml:admin:approval` — 승인/반려)·`AML_VIEWER`(`aml:case:read` — RA 흐름·등재 read-back 조회)·`AML_POLICY_ADMIN`(`aml:admin:high-risk-registry`)** 3역할 자연키(`admin_user_id, role_id`) `ON CONFLICT DO NOTHING` 바인딩(**하드코딩 role_id 금지** — id 하드코딩은 앱 생성 바인딩과 충돌해 `ON CONFLICT (id) DO NOTHING` 이 역할을 조용히 스킵하는 결함이 있어 자연키 멱등), ③ `bo_user_tenants` `tenant_demo` 바인딩(비플랫폼 운영자 0바인딩=락아웃 방지). 이 계정은 현행에서 explicit `demo` location만 다시 활성화한다. 신규 감사 이벤트 없음(승인/반려는 기존 `AML_APPROVAL_APPROVED/REJECTED` 재사용). maker `system:ra-engine`(또는 시뮬레이터 maker)≠checker `choi.exec` 이므로 4-eyes 항상 충족. **가정 A2 유지 — 승인선 라인-역할 강제는 미구현**: 고위경영진 승인은 `aml:admin:approval` scope(또는 BO_SUPER_ADMIN) 게이트만 검증하며, `EXECUTIVE_APPROVAL` 승인선별 역할 강제(§4.2 라인 정의)는 정의 측(definition plane)에만 존재하고 런타임 강제는 후속(§4.3 비고 "엔진이 bo-api 라우팅을 강제 소비"와 동종). PRD §12-A.4 BR-006·§12-B.6 BR-006 참조.
> - 2026-07-12 — **REPORT_RULE_PARAM 엔진 소유 4-eyes 전환(V41, 코드=truth)**: bo-api EXECUTED 후 반영 위임에서 aml-svc가 상신·pending·checker 실행·원자 적용을 전부 소유하는 구조로 전환했다. bo-api는 인증 principal maker로 상신 자체를 위임하고 engine 응답 5필드를 fail-closed 검증한 실제 approvalId를 반환한다. 엔진 `ApprovalSubjectType`/CHECK는 V31 20종→V41 **21종**, 승인선 `COMPLIANCE_MANAGER`; AS-IS/TO-BE staged payload와 trim+case-insensitive self-approval(`Alice`=`alice`)/payload drift를 공통 결재함에서 검증한다.
> - 2026-07-09 — **Travel Rule 전면 제거 정합(코드=truth, feature/remove-travel-rule, aegis-aml 84997e1)**: FDS·AML 양 도메인에서 Travel Rule 기능을 현 단계 불필요로 판단해 완전 삭제. IAM/승인 영향 — ① 결재 subject_type `TRAVEL_RULE_EXCEPTION` 제거: 엔진 `aml_approvals.subject_type` CHECK **21→20**(Flyway **V31**, aml-svc `ApprovalSubjectType` 20종)·bo-api `AmlApprovalDtos.SubjectType` **23→22종**. ② bo-api Flyway **V14__drop_travel_rule** — `bo_menu`/`bo_menu_permissions` 의 `aml-travel-rule` 메뉴 seed(화면 AML-TR-001, `/aml/travel-rule`, V2 seed) DELETE·`bo_approval_routes` 의 `TRAVEL_RULE_EXCEPTION` 라우팅 seed DELETE·`bo_audit_logs` allowlist(`chk_bo_audit_logs_event`)에서 `TRAVEL_RULE_EXCEPTION_RESOLVED` 제거(잔존 감사 행 선행 DELETE + 제약 재생성). §4.2 라우팅·§5 데이터 모델 표에 반영. (참고: 감사 이벤트 `HRR_REGISTRATION_SUBMITTED`·CTR/STR allowlist 는 유지 — Travel Rule 관련 1종만 제거.)
> - 2026-07-07 — **RA 당연고위험 등재 결재선 정합(코드 truth, feature/aml-hrr-ra-registration)**: §4.2 subject_type별 라우팅에 **`HRR_REGISTRATION → EXECUTIVE_APPROVAL`** 추가(RA 당연고위험 회원 등재 = 고위경영진 수동승인 결재선, aml-svc `ApprovalLineResolver` 미러). 엔진 `aml_approvals.subject_type` CHECK **20→21**(Flyway **V28**), bo-api `AmlApprovalDtos.SubjectType` 22→**23종** + `bo_approval_routes` 에 `('platform','HRR_REGISTRATION',1,'EXECUTIVE_APPROVAL')` 라우팅 seed·감사 `HRR_REGISTRATION_SUBMITTED` allowlist(bo-api Flyway **V11**). 상신 주체 2원화 — RA 엔진 자동 상신(maker `system:ra-engine`, 이미 등재/PENDING 멱등 no-op) + RA 상세 수동 상신(`POST .../high-risk-registry/registrations`). 승인 EXECUTED 시에만 `RA_HIGH_RISK_CUSTOMERS` 등재 확정+RA 강제 상향(PRD §12-B.6 BR-005).
> - 2026-07-06 — **CTR 임계 변경 결재함 정합(코드=truth, fix/aml-ctr-threshold-engine-approval)**: `CTR_THRESHOLD`를 bo-api 전용 결재에서 **aml-svc 엔진 결재 대상**으로 승격. 엔진 `aml_approvals.subject_type` CHECK **19→20**(Flyway V23)·`ApprovalLineResolver` 승인선 `REPORTING_OFFICER`·bo-api `AmlCtrThresholdService` 엔진 연결 시 admin 상신 위임(`POST /api/v1/admin/aml/ctr-thresholds/{currency}:update`)으로 정본화. AML 결재함은 엔진 `/admin/aml/approvals`에서 `CTR_THRESHOLD`를 조회한다.
> - 2026-07-06 — **CTR/STR 룰 파라미터 편집 결재 최초 도입(후속 V41로 대체)**: 최초 bo-api 로컬 `COMPLIANCE_OFFICER`/stub 구조는 2026-07-12 V41에서 엔진 소유 `COMPLIANCE_MANAGER` 상신·실행으로 대체됐다. 역사적 V9 도입 배경만 보존하며 현행 계약은 위 2026-07-12 행과 §4.2를 따른다.
> - 2026-07-01 — **CTR/STR 모니터링 통합 결재 정합(코드=truth, feature/aml-ctr-str-monitoring)**: §4.2 subject_type 라우팅에 **`CTR_THRESHOLD → REPORTING_OFFICER`**(CTR 규제 임계 변경)·**`REPORT_RULE → COMPLIANCE`**(CTR/STR 룰 활성화) 추가. 당시 두 값은 bo-api 애플리케이션 계층 subjectType으로 도입했으나, 현행은 위 2026-07-06 항목처럼 `CTR_THRESHOLD`가 엔진 결재 대상이다. §4.3 BR-6 신설 — **CTR 규제 임계 hot-reload 제외**(결재 EXECUTED 시점에만 `aml_ctr_thresholds` 반영, 규제값 무단 변경 방지). §5 데이터 모델 표에 bo-api enum(21종)·`bo_audit_logs` 감사 3종(V6)·`aml_ctr_thresholds`/`aml_ph_banking_calendar`(V5/V7) 행 추가. DB §3.22a/§3.22b/§5.16·API §2.7/§11·기능정의서 §9.1 동기화.
> - 2026-06-30 — **hanpass-ph 기준 정합**: 시스템을 hanpass-ph(한패스 PH) AML/FDS 백오피스 IAM/승인으로 한정. 가상 다(多)서비스 일반화("1 기관 : N 서비스")·가상 데모 테넌트(은행 A/핀테크 B/소규모 C, V28 제거) 예시 삭제, 운영 테넌트=`tenant_demo`(hanpass PH)로 서술. 멀티테넌트 격리·플랫폼 운영자(platformOperator)·테넌트 바인딩은 코드 truth(`BackofficeRole.isPlatformOperator`·`bo_user_tenants`)로 유지하되 운영 배포는 단일 테넌트로 좁힘. 권한·결재유형(4-eyes)·화면·액션은 코드 enum/컨트롤러/`nav.ts`와 1:1 유지.
> - 2026-06-29 — **PEP 경영진 승인 결재선 정합(코드 truth)**: §4.2 subject_type별 라우팅에 **`PEP_APPROVAL → EXECUTIVE_APPROVAL`** 추가(PEP=정치적 주요인물 경영진 결재선, aml-svc `ApprovalLineResolver` 미러). `aml_approvals.subject_type` CHECK **18→19**(PEP_APPROVAL, 엔진 Flyway **V24** — WLF pii_vault V23과 별개)로 §4.2·§5 표·§8 P3 정정. 통합 approval_line 7종(EXECUTIVE_APPROVAL 기보유)·라우팅 데이터 구조 불변.
> - 2026-06-21 — **구현 정합화(코드 truth)**: P1~P4·사용자 지정 결재선이 Flyway V18~V27로 **구현 완료**됨을 §1~§8 전반에 반영. `bo_user_tenants`(PK `admin_user_id`)·`bo_role_scopes`(V20)·data_scope `tenant|workspace`(V21)·`bo_approval_lines`/`bo_approval_routes`(V22)·`bo_menu`/`bo_menu_permissions`(V23)·`bo_approval_delegations`(V24)·데모 테넌트/라벨 정합(V26)·`bo_approval_route_members`(V27) 정본화. 화면(BO-APRL-003 신설·BO-APRL-002 명칭 정정)·NAV 6종·API 경로(DELETE 사용자 비활성·위임 회수·effective-approver·route-members) 코드 기준 정정. 감사 emit(ROLE_ASSIGNED/REVOKED/PASSWORD_CHANGED·ROLE_SCOPE_CHANGED·APPROVAL_LINE_CHANGE·APPROVAL_DELEGATION_CHANGED) 실재 확인. ROLE_CHANGE 4-eyes 워크플로는 **후속 과제**(현재 RBAC 게이트 + 감사만).
> - 2026-06-19 — 테넌트=서비스 재정의(기관 → 서비스 → 워크스페이스). §0·§2.2 멀티테넌시·`bo_user_tenants`를 사용자↔서비스 바인딩으로 재기술, "고객사"→"서비스"; `tenant_id`/`workspace_id`·data_scope·role/scope 코드명 불변(의미만 서비스).

## 0. 개요

| 항목 | 내용 |
|---|---|
| 목적 | hanpass-ph 백오피스 **사용자 관리(계정 생성·권한)** · **권한 관리(역할·scope·RBAC)** · **결재선(결재 라인) 관리**의 필요 기능을 전체 정의 |
| 대상 사용자 | 플랫폼 운영자(platformOperator, 테넌트 비종속)·hanpass-ph 테넌트(`tenant_demo`) 관리자·준법감시/보안 관리자 |
| 현재 상태 | 본 정의서의 P1~P4 + 사용자 지정 결재선이 **구현 완료**(Flyway V18~V27, bo-api 컨트롤러·bo-web 화면). 역할 배정·커스텀 scope·테넌트 바인딩(헤더 위조 방지)·4계층 RBAC·동적 메뉴·결재선 라우팅 정의·다단계/위임/지정 승인자까지 **정의 측(definition plane) 완비**. 잔여: 엔진 런타임이 bo-api 라우팅을 강제 소비(§4.3 비고)·ROLE_CHANGE 4-eyes 워크플로는 **후속**(§1 현행 분석) |
| 비범위 | 도메인별 결재 대상의 비즈니스 로직(룰/시나리오/명단 등 — 01·02 PRD), 엔진 내부 결재 전이 |

## 1. 현행 분석 (As-Is) — EXISTS vs MISSING

| 영역 | 존재(As-Is) | 결손(Gap) |
|---|---|---|
| **사용자** | `bo_admin_users`(email·password_hash BCrypt·name·admin_type·department·status·last_login_at) / `bo_roles` / `bo_user_roles`(N:M). 로그인(`AuthService`, HMAC 세션 토큰). `AdminUserController` 생성·목록·상세·수정·역할 set·비번 리셋·잠금 해제·재활성·비활성(DELETE soft) | ~~생성 시 역할 지정 불가~~ → **해소**(`AdminUserRequest.roleIds` + 수정/비번리셋/unlock/reactivate API, V19 생애주기 감사) · ~~user↔tenant 영속 바인딩 없음~~ → **해소**(`bo_user_tenants` V20, header + P0-03 path/query/body target 위조 방지) · ~~운영 migration과 demo 로그인 계정 혼재~~ → **해소**(P0-02 V17 forward quarantine + explicit `demo` location; 운영 최초 관리자는 IdP/OOB only) |
| **권한** | `BackofficeRole` enum(FDS 8 + AML 7 + BO_SUPER_ADMIN, scope 보유). `@PreAuthorize` scope/role 게이트. 역할 행 Flyway 시드 | ~~역할↔사용자 배정/회수 API 없음~~ → **해소**(`PUT .../users/{id}/roles`, `bo_user_roles` write) · ~~커스텀 역할 scope 컬럼 없음~~ → **해소**(`bo_role_scopes` V20) · ~~메뉴 4개 하드코딩~~ → **해소**(`bo_menu`/`bo_menu_permissions` V23, MenuController DB 조회) · ~~4계층 RBAC 미구현~~ → **해소**(역할×메뉴×CRUD) · ~~FDS controller raw role/scope allowlist 불일치~~ → **해소**(P0-03 exact capability 중앙 policy, custom scope 포함) · ~~`ROLE_ASSIGNED/ROLE_REVOKED/PASSWORD_CHANGED` emit 없음~~ → **해소**(AdminUserService 실제 emit, V19 생애주기 + `ROLE_SCOPE_CHANGED` V20). 잔여: ROLE_CHANGE 4-eyes 워크플로(후속) |
| **감사·actor** | BO/AML/FDS append-only audit와 signed `X-User-Subject` | ~~BO 감사 tenant/workspace 미정규·ID 전역 조회~~ → **해소**(V18 scoped columns/index/query, legacy `platform/default`) · ~~engine/BO 중 한 source만 조회~~ → **해소**(exact-total unified merge + typed composite detail) · ~~body maker/actor 신뢰~~ → **해소**(`TrustedActorResolver`/`BackofficeActorResolver`, AmlTenant 포함) · ~~domain complement 분류로 IAM row 노출~~ → **해소**(explicit FDS/AML allowlist, unknown=super-only) · ~~generic engine proxy 우회~~ → **삭제**(typed BFF only) |
| **결재선** | `aml_approvals`/`bo_fds_*_approval_requests`. 4-eyes(self-approval 금지·maker≠checker CHECK)·payload_hash drift guard·상태머신. `approval_line` 컬럼 존재 | ~~결재선 정의/관리 전무~~ → **해소**(bo-api 정의 측: `bo_approval_lines`(7종, V22)·`bo_approval_routes`(subject별 라인·다단계·임계 JSONB, V22)·`bo_approval_delegations`(위임, V24)·`bo_approval_route_members`(지정 승인자, V27)) · ~~FDS(6)/AML(6) enum 불일치~~ → **해소**(단일 정본 7종, §4.1) · 잔여: 엔진 런타임이 정의를 강제 소비(현 단계는 정의·노출, 런타임 강제는 후속·§4.3 비고) |
| **문서** | FDS §16.2 권한 매트릭스·§16.5 4-eyes 사전 / AML 부록 B·C(subject별 라인)·G(라인 사전) | **bo-api/IAM PRD 부재** · IAM·결재선 관리 **화면/스펙 전무**(본 문서가 정본화) |

## 2. 사용자·계정 관리 (User Management)

### 2.1 화면 (신규)
| 화면 ID | 명칭 | 역할 |
|---|---|---|
| BO-USR-001 | 사용자 목록 | 운영자 계정 조회·검색·상태/역할/테넌트별 필터 |
| BO-USR-002 | 사용자 상세 | 계정 정보·배정 역할·테넌트 스코프·로그인 이력·상태 변경 |
| BO-USR-003 | 사용자 생성 | 계정 생성 + **역할 배정** + 테넌트/워크스페이스/data-scope 바인딩 |
| BO-USR-004 | 사용자 수정 | 정보·역할·스코프 변경, 비밀번호 리셋, 잠금 해제, 비활성/재활성 |

### 2.2 기능 요구
1. **계정 생성**(BO-USR-003): email(고유)·name·department·admin_type + **역할 다중 선택(roleIds)** + 테넌트 바인딩(플랫폼 운영자=tenant-agnostic / hanpass-ph 테넌트 운영자=`tenant_demo`·workspace 지정) + 초기 비밀번호(또는 초대 토큰) → `bo_admin_users` + `bo_user_roles` + `bo_user_tenants`(신규). 생성 시 `ADMIN_USER_CREATED`·`ROLE_ASSIGNED` 감사.
2. **수정/상태**(BO-USR-004): 정보 수정, 역할 추가/회수(`ROLE_ASSIGNED`/`ROLE_REVOKED`), 비밀번호 리셋(`PASSWORD_CHANGED`), `status` ACTIVE/INACTIVE/LOCKED 전이(잠금 해제), 비활성(soft `deactivate`). 자기 자신 비활성/권한축소 방지(BR).
3. **멀티테넌시 바인딩**(구현 완료, V20+P0-03) — 테넌트(`tenant_id`) → 워크스페이스(`workspace_id`) 2계층 격리(코드 truth, 유지). user↔tenant/workspace/data-scope를 **영속**(`bo_user_tenants`)으로 두고, `TenantContextFilter`가 요청 헤더를 바인딩으로 검증한다. P0-03 target guard는 path·query·body의 tenant/workspace도 같은 context와 controller/service 전에 비교한다. target은 trim 후 최대 64자, `X-Trace-Id`는 최대 128자이고 제어문자를 금지한다. non-platform은 자기 복합 scope만, platform operator는 명시한 하나의 target을 handler·downstream header·감사 row에 동일 적용하며 target끼리 충돌하면 거부한다. 이 `platformOperator` 판정은 **data-scope 선택만** 허용하고 메뉴·IAM·PII reveal·STR 열람·업무 action 권한을 주지 않는다. 플랫폼 운영자 판정은 `BackofficeRole.isPlatformOperator` 단일 정본. 운영 배포는 hanpass-ph 단일 테넌트(`tenant_demo`)이지만 멀티테넌트 강제 메커니즘을 유지한다.
4. **운영 최초 관리자**: 최초 `BO_SUPER_ADMIN`은 Flyway가 만들지 않는다. 우선 경로는 IdP provisioning이며, 대안 OOB bootstrap은 production-class profile에서 명시적 opt-in으로 한 번만 실행한다. known demo email을 금지하고 secret manager의 Base64/Base64URL random material(복호화 기준 32 bytes 이상)을 일회성 입력으로 받아 BCrypt 저장, `BO_SUPER_ADMIN` 자연키 role 부여, `ADMIN_USER_CREATED`·`ROLE_ASSIGNED`·완료 marker(`SYSTEM_CONFIG_CHANGED`/`OOB_INITIAL_ADMIN`)를 한 transaction으로 감사한다. active SUPER_ADMIN 또는 완료 marker가 있으면 반복 실행을 거부하고 성공 직후 입력을 제거한다.
5. **demo 계정·세션 secret 경계**: 정규 `db/migration` 최종 상태는 알려진 demo 6계정의 binding을 회수하고 login을 무효화한다(V17). `test@test.com` operator와 `choi.exec@aegis.example` checker는 explicit `demo` profile + `classpath:db/demo`에서만 활성화된다. production-class profile은 `local|demo` 혼합, active demo 복합 fingerprint, blank/public/저엔트로피 session HMAC을 startup에서 거부하고 session signature는 constant-time 비교한다. session secret은 secret manager가 주입하며, 교체 시 기존 session 전부 무효화 후 새 key로 재로그인하고 실패 시 같은 secret-manager current version으로만 rollback한다.
6. **신뢰 actor**: BO write actor는 `BackofficePrincipal.email`에서만 파생하고 body `makerId/checkerId/actor/requestedBy`는 optional 일치 assertion이다. AML/FDS engine 위임 actor는 HMAC 검증 후 128자·제어문자 경계를 통과한 signed `X-User-Subject`에서만 파생한다. AmlTenant provision의 `requestedBy`도 assertion일 뿐이며 register 이력 actor는 `instanceId`가 아니라 principal이다. FDS local fallback 결재 상신 maker도 `BackofficeActorResolver`의 인증 principal이며 `ops.agent` 같은 기본 actor를 사용하지 않는다. 위조는 상태 전이·downstream·감사 append 전에 400으로 거부한다.
7. **본인 테넌트 바인딩 조회**(2026-08-10 신설, 코드=truth) — 오퍼레이터가 **자기 바인딩을 알아야만 `Tenant-Id` 를 실을 수 있다**는 순환 의존을 끊는 세션 부트스트랩 조회다. `GET /api/v1/bo/auth/me/tenants` 는 **인증만 요구**하고 **principal 본인 바인딩만**(`bo_user_tenants`) 반환하며, 응답은 `tenantId`·`workspaceId` **2필드**다 — `dataScope` 는 서버(`TenantContextFilter`)가 매칭된 바인딩에서 파생하는 **내부 인가 판정**이라 세션에 내리지 않는다(운영자가 자기 권한에 대해 더 알게 되는 대가만 있고 UI 이득이 없다). 정렬은 `tenantId`→`workspaceId` 결정적. 이 조회를 위해 `TenantContextFilter` 는 **self-scoped bootstrap allowlist 3경로**를 **정확 일치**로 둔다 — `/api/v1/bo/auth/me`(세션 투영)·`/api/v1/bo/auth/me/tenants`(본인 바인딩)·`/api/v1/bo/auth/logout`(감사 append). 셋 다 응답이 **인증 principal 만으로 파생**되고 테넌트 스코프 데이터를 읽지 않으므로 기존 `/actuator`("not tenant-scoped") 면제와 동형이다. **면제는 엔드포인트별로 논증되며 접두·와일드카드로 상속되지 않는다** — 이 경로 아래에 생기는 테넌트 스코프 엔드포인트는 면제 대상이 아니고, allowlist 정확 집합과 접두 미매칭을 **드리프트 가드 테스트**가 고정한다. **거부 3규칙은 무변경**이다 — ① 바인딩 0 → `BO-TENANT-REQUIRED`(M-3 fail-closed, **allowlist 판정보다 선행**하므로 bootstrap 경로에서도 fail-closed) · ② 바인딩 ≥2 + `Tenant-Id` 없음 → `BO-TENANT-REQUIRED` · ③ 헤더가 어느 바인딩과도 불일치 → `BO-TENANT-FORBIDDEN`. 테넌트 스코프 전 경로에서 그대로이며 **권한 완화는 없다**: bootstrap 3경로에서만 미해결 컨텍스트로 진행하고, 그때도 **헤더 값을 컨텍스트로 신뢰하지 않아** 위조 스코프가 성립하지 않는다(낡은 localStorage `Tenant-Id` 때문에 회복용 엔드포인트가 403 되는 클라이언트 락아웃도 함께 막는다). 이 조회가 없던 동안 **바인딩 2개 이상인 모든 비-플랫폼 오퍼레이터는 `auth/me` 403 → 세션 삭제 → `/login` 순환으로 로그인 자체가 불가**했다(§6 선택기 항 참조).

### 2.3 검색조건 (BO-USR-001)
상태(ACTIVE/INACTIVE/LOCKED) · 역할(roleCode) · 테넌트 · 부서 · 마지막 로그인 기간 · 이메일/이름 검색.

### 2.4 데이터·API·테이블
- 테이블: `bo_admin_users`(기존) + **`bo_user_tenants`**(V20 — `admin_user_id`, `tenant_id`, `workspace_id`, `data_scope`, PK `(admin_user_id, tenant_id, workspace_id)`) + `bo_user_roles`(기존, write API 신설).
- API(구현 완료, `AdminUserController`):
  - `POST /api/v1/bo/admin/users`(roleIds 추가) · `PUT /api/v1/bo/admin/users/{id}`(프로필 수정) · `POST .../{id}:reset-password` · `POST .../{id}:unlock` · `POST .../{id}:reactivate` · **`DELETE /api/v1/bo/admin/users/{id}`**(비활성 soft — `:deactivate` 액션이 아니라 DELETE 동사)
  - `PUT /api/v1/bo/admin/users/{id}/roles`(역할 set 교체=배정/회수 diff) · `GET .../{id}/tenants` · `PUT .../{id}/tenants`(테넌트 바인딩 set 교체)
- 권한: `BO_SUPER_ADMIN` 또는 신규 `BO_IAM_ADMIN` scope `bo:admin:iam`.
- **세션 API(`AuthController`, 관리 API 와 권한 경계가 다름)**: `GET /api/v1/bo/auth/me`(세션 투영) · **`GET /api/v1/bo/auth/me/tenants`**(2026-08-10 신설 — 본인 테넌트 바인딩, 응답 `SelfTenantBindingResponse{tenantId, workspaceId}[]`) · `POST /api/v1/bo/auth/logout`. 세 경로는 **인증만 요구**하고 응답이 principal 만으로 파생되므로 `TenantContextFilter` 의 **정확 일치 self-scoped bootstrap allowlist**(접두·와일드카드 아님)에 속한다(§2.2-7). 관리자용 `GET /api/v1/bo/admin/users/{id}/tenants`(타인 바인딩 조회·`dataScope` 포함)와 **다른 엔드포인트**이며 서로 대체하지 않는다.

## 3. 권한·역할 관리 (Permission/Role Management)

### 3.1 역할 카탈로그 (정본 통합)
- 시스템 역할(is_system, 불변): FDS 8종(SFDS_PLATFORM_OPS/ADMIN·VIEWER·AUTHOR·APPROVER·OPS·ANALYST·ADMIN) · AML 7종(AML_VIEWER·COMPLIANCE·APPROVER·CASE_ANALYST·POLICY_ADMIN·AUDITOR·PII_REVEAL) · BO_SUPER_ADMIN(`*`). scope 정본 = `BackofficeRole`.
- **커스텀 역할**(신규): 운영자가 정의, **scope 집합 보유**. → `bo_roles`에 **`scopes` 컬럼(또는 `bo_role_scopes`) 추가**(현재 커스텀 역할 scope 0 결손 해소). scope 카탈로그(정본)는 별도 enum/표.

### 3.2 화면 (신규)
| 화면 ID | 명칭 | 역할 |
|---|---|---|
| BO-ROLE-001 | 역할 목록·관리 | 시스템/커스텀 역할·scope·사용 사용자 수. bo-web nav는 단일 `/admin/roles` 페이지(`admin-roles`)만 노출 |
| BO-ROLE-002 | 역할 상세·scope 편집 | 커스텀 역할 scope 편집(시스템 역할 읽기전용). 별도 nav 항목/서브경로 없이 **BO-ROLE-001 내 인라인/하위경로**로 제공. scope 변경 시 `ROLE_SCOPE_CHANGED` 감사(V20). **ROLE_CHANGE 4-eyes 결재 워크플로는 후속 과제**(현재 RBAC 게이트 + 감사만) |
| BO-PERM-001 | 권한 매트릭스 | 역할×화면(scope) 매트릭스 뷰(FDS §16.2 + AML 부록 B 통합 정본) |
| BO-MENU-001 | 메뉴·페이지 권한 | 4계층(그룹>직무>메뉴>페이지 CRUD) 매핑 관리 |

### 3.3 기능 요구
1. **역할↔사용자 배정/회수**(§2.2와 연계, 구현 완료): `bo_user_roles` write API(`PUT .../users/{id}/roles`) + 화면. `ROLE_ASSIGNED`/`ROLE_REVOKED` 실제 emit(AdminUserService).
2. **커스텀 역할 + scope**(구현 완료): 생성·scope 편집(시스템 역할 보호, `bo_role_scopes` V20). scope 변경은 `ROLE_SCOPE_CHANGED` 감사. **역할 변경의 4-eyes(`ROLE_CHANGE`) 워크플로는 후속 과제**(현재는 RBAC 게이트 + 감사 emit까지).
3. **4계층 RBAC**(벤치마크 정합, 구현 완료 V23): 그룹(조직) > 직무(역할) > 메뉴 > 페이지 액션(CRUD). `bo_menu`/`bo_menu_permissions`(역할×메뉴×CRUD: `can_read`/`can_create`/`can_update`/`can_delete`) 모델. `MENU_PERMISSION_CHANGED` 감사.
4. **데이터 기반 메뉴**(구현 완료 V23): `MenuController` 하드코딩 4항목 → **DB·역할 기반 동적 메뉴**(`bo_menu` 시드 — 콘솔/영역 노드 포함 약 41행, `bo-web` `lib/nav.ts` 운영·설정 IA와 정합. menu 가시성=사용자 역할 중 하나라도 `can_read` 보유 시 노출, `BO_SUPER_ADMIN`/scope `*`만 전체). `platformOperator`는 메뉴 우회 조건이 아니다. V26에서 메뉴 라벨 **'고객사 관리' → '서비스 관리'** 정합(`fds-tenants`/`aml-tenants`).
5. **scope→capability**: `@PreAuthorize` scope 게이트 유지 + scope↔화면/액션 매트릭스 정본화. FDS는 `FdsAuthorizationPolicy`가 endpoint별 exact `SFDS_*:READ|AUTHOR|OPERATE|APPROVE|ADMIN` capability를 system role matrix와 custom `bo_role_scopes`에 동시에 적용한다. wildcard `*`/`BO_SUPER_ADMIN`만 우회한다. `SFDS_PLATFORM_OPS`는 횡단 read만 가능하고 action·evidence·approval capability가 없으며, action 목록과 상세는 모두 exact `SFDS_ACTION:OPERATE`를 요구한다. `SFDS_PLATFORM_ADMIN`은 tenant admin/write를 포함한다. bo-api→fds-svc의 `fds:*` machine scope는 이 사람 권한과 별도다.
6. **typed engine delegation**: bo-api는 명시 controller/DTO/client로만 AML/FDS admin 기능을 위임한다. catch-all `/api/v1/admin/{engine}/**` route, caller header 임의 전달, engine간 route 전환은 허용하지 않으며 미등록 route는 404다.
7. **typed read capability**: FDS health=`SFDS_CONNECTOR:READ`, case evidence timeline=`SFDS_DECISION:READ`, notify GET=`SFDS_TENANT:READ`, notify PUT=`SFDS_TENANT:ADMIN`(platform admin). AML health=`aml:case:read`. 동일 URL family라는 이유로 export/connector/generic role을 재사용하지 않는다.
8. **fallback 경계**: fds-svc delegate가 없을 때 local FDS fallback은 active profile **전부**가 명시적 `local|demo|test`이고 active scope가 `tenant_demo/default`인 경우에만 허용한다. production denylist가 아니라 positive allowlist이며 unknown/mixed/no-profile, scope 부재, 다른 tenant/workspace는 모두 503이다. local 결재·감사 row는 현재 scope로만 생성한다. compliance-policy는 일반 fallback과 분리된 서비스다. local policy payload는 exact `{"base":"KR_BASE","packs":string[],"optional":string[]}`만 허용한다(세 key 모두 필수, 추가 key 금지, 두 배열 원소는 non-blank). 허용된 local scope의 submit은 인증 principal maker로 `POLICY_PACK` approval만 stage하고 effective policy를 즉시 바꾸지 않는다. 다른 checker가 exact `SFDS_REG:APPROVE`를 보유하고 immutable hash/scope/payload 검증을 통과한 뒤 `FdsTenantWriter` 적용까지 성공해야 `EXECUTED`와 effective 변경이 성립한다. reject 또는 적용 실패 시 effective policy는 그대로다. 엔진이 configured인데 호출 오류/응답 계약 위반이면 local로 강등하지 않고 fail-closed한다. mutating lifecycle 게이트는 inherited URL을 사용하지 않고 FDS/AML/BO/bo-web canonical loopback port(8081/8082/8083/3000)를 강제하여 staging IAM/tenant/policy 변이를 차단한다.

### 3.4 API·테이블
- 테이블: `bo_roles`(+scopes), **신규** `bo_role_scopes`·`bo_menu`·`bo_menu_permissions`, `bo_user_roles`(write).
- API: `POST/PUT/GET /api/v1/bo/admin/roles`(+scopes) · `PUT .../roles/{code}/scopes` · `PUT .../users/{id}/roles` · `GET /api/v1/bo/menu`(동적·역할 기반).

## 4. 결재선(결재 라인) 관리 (Approval-Line Management) — 핵심 신규

### 4.1 통합 approval_line enum (불일치 해소)
현행 FDS 6종(SELF_APPROVAL_DISABLED·MAKER_CHECKER·COMPLIANCE_MANAGER·RISK_MANAGER·SECURITY_ADMIN·EXECUTIVE_APPROVAL)과 AML 6종(MAKER_CHECKER·AML_OFFICER·COMPLIANCE_MANAGER·REPORTING_OFFICER·SECURITY_ADMIN·EXECUTIVE_APPROVAL)이 상이. → **단일 정본 enum**으로 통합(합집합 + 매핑):
`MAKER_CHECKER · AML_OFFICER · COMPLIANCE_MANAGER · RISK_MANAGER · REPORTING_OFFICER · SECURITY_ADMIN · EXECUTIVE_APPROVAL`(+ 표시 비활성 의미 `SELF_APPROVAL_DISABLED`는 라인이 아니라 **불변 정책 플래그**로 분리). 각 라인 ↔ 승인 권한 역할(scope) 매핑 테이블로 정의.

> 구현 완료(V22 `bo_approval_lines` 7종): 코드(`ApprovalLine` enum)와 정합 — 이격 없음. `required_scope` 컬럼이 라인→승인 권한 scope 매핑(예 COMPLIANCE_MANAGER→`aml:admin:approval`).
>
> **표시 라벨 정본(i18n)**: `bo_approval_lines.label` 은 한국어 단일 값이므로 **BO 화면 표시 라벨의 정본이 아니다** — 결재함(FDS·AML 공용 `ApprovalLineBadge`)은 `line_code` 를 프론트 메시지 카탈로그(`amlCust.enum.approvalLine.<CODE>`, ko/en)로 매핑해 표기하고, 카탈로그 미등록 코드에 한해 서버 `label` → 코드 순으로 폴백한다. 서버 `label` 은 운영자 정의 화면(BO-APRL-001)의 관리 값으로 유지한다.

### 4.2 결재선 정의 (subject_type별 라우팅 — 부록 C 구현)
- 현행: 모든 결재가 `MAKER_CHECKER` 하드코딩 → **subject_type별 라인 라우팅**을 데이터로 정의(부록 C 정본 구현):
  - 예) RA_MODEL·TM_SCENARIO·COUNTRY_RISK·POLICY_PACK·**REPORT_RULE_PARAM → COMPLIANCE_MANAGER** · EDD_CLOSE → AML_OFFICER · STR/CTR → REPORTING_OFFICER · SECRET_CHANGE → SECURITY_ADMIN · **PEP_APPROVAL → EXECUTIVE_APPROVAL** · **CTR_THRESHOLD → REPORTING_OFFICER** · REPORT_RULE(bo-api 룰 활성화) → COMPLIANCE · HRR_REGISTRATION → EXECUTIVE_APPROVAL. `REPORT_RULE_PARAM`은 engine `ApprovalLineResolver`와 bo-api 표시 모두 `COMPLIANCE_MANAGER`다.
- **CTR/STR 모니터링 통합 subject_type(코드=truth)**: `CTR_THRESHOLD`와 `REPORT_RULE_PARAM`은 aml-svc 엔진 결재 대상이다. 전자는 `REPORTING_OFFICER`, 후자는 `COMPLIANCE_MANAGER` 승인선이다. bo-api는 상신 자체를 위임하고 실제 approvalId를 공통 결재함에 노출하며 checker EXECUTED 시에만 effective store를 반영한다. `REPORT_RULE` 룰 활성화만 bo-api 애플리케이션 결재 경계를 유지한다.
- **subject_type 정합(엔진)**: V31 Travel Rule 제거 후 20종에서 V41 `REPORT_RULE_PARAM` 추가로 현행 **21종**이다. 도메인 enum·DB CHECK·API §3.7·`ApprovalLineResolver`를 전수 동기화한다.
  > **2026-08-13 확인 — 이름 위험 신호 점수 비례 배수(`parameters.signalScaling`) 도입에 신규 승인 유형은 없다(코드=truth).** 그 파라미터는 RA 모델 정의(`aml_risk_models.parameters`) 안의 선택키이므로 초안 저장 → 시뮬레이션 → 활성화 상신이 **기존 `RA_MODEL` 결재**(승인선 `COMPLIANCE_MANAGER`, scope `aml:admin:policy`)를 그대로 탄다 — subject_type **21종 불변**, 새 결재선·새 테이블·새 스코프 0, DB CHECK·`ApprovalLineResolver` 무변경. 화면도 신규 라우트가 아니라 AML-RA-002 의 ⑤ 탭이다(기능정의서 §6.1 BR-008). 같은 날 신설된 PEP 축 확인 불가 귀결 `RISK_SIGNAL` 역시 엔진 런타임 설정(`aegis.aml.wlf.pep-axis.*`)이라 **결재 대상이 아니다**(테넌트별 4-eyes 편집 승격은 범위 밖 — 승격 시 `POLICY_PACK` 스키마 변경 = 전 테넌트 재승인이 선행돼야 한다).
- **FDS exact checker 매핑(P0-03)**: FDS 결재는 controller 진입 뒤 row별로 다시 판정한다. `ACTION→SFDS_ACTION:APPROVE`, `RULE|RULE_PARAM→SFDS_RULE:APPROVE`, `SECRET→SFDS_CONNECTOR:APPROVE`, `GROUP|MERCHANT_NORMALIZE→SFDS_GROUP:ADMIN`, `EXPORT|POLICY_PACK→SFDS_REG:APPROVE`, `CASE_CLOSE→SFDS_CASE:APPROVE`, **`TENANT_REGULATORY_CURRENCY→SFDS_REG:APPROVE`**(다통화, PLAN 20260818 U17 — `POLICY_PACK` 과 동일 checker capability, DB V32). FE subject 필터/라벨은 `RULE_PARAM`·`TENANT_REGULATORY_CURRENCY` 를 포함한 승인용 **11종**을 사용하며, 감사 `targetKind` resource enum과 공유하지 않는다. `MAPPING`은 결재 row 생성 뒤 변경하지 않는 staged `requiredBoCapability`만 사용한다. field mapping=`SFDS_MAPPING:APPROVE`, source-system capabilities-only=`SFDS_ACTION:APPROVE`, 일반 설정-only=`SFDS_CONNECTOR:OPERATE`; `capabilities` 필드가 있으면 빈 배열 `[]`도 revoke-all 전체 desired set으로 stage하며, 일반 설정과 혼합하면 상신 전에 400이다. marker 누락·미지 legacy row는 fail-closed한다. maker도 operation별 같은 capability를 요구한다.

### 4.3 기능 요구
1. **결재선 정의 관리**(BO-APRL-001): subject_type × 결재선 × 승인자 역할 매핑을 운영자가 조회·변경. 변경 시 **감사 이벤트 `APPROVAL_LINE_CHANGE` emit**(V22, ApprovalRouteService) — *4-eyes 실행 결재는 후속*, 현재는 RBAC 게이트(`BO_SUPER_ADMIN`/`bo:admin:iam`) + 감사. `PUT .../approval-routes`는 즉시 적용. 라우팅은 `platform` 기본 시드 + 테넌트별 override 구조(코드 truth, `tenant_id` 선두 PK)이며, 운영에서는 hanpass-ph(`tenant_demo`)가 `platform` 기본을 그대로 쓰거나 필요 시 override 한다.
2. **다단계(순차) 라인**: 1차→2차→최종 등 N단계 승인 체인 정의(현 단일 maker-checker 확장). 각 단계 승인 역할·필수 여부.
3. **임계값 기반 라우팅**: 금액/위험등급/건수 임계로 라인 상향(예 고액 STR → EXECUTIVE_APPROVAL 추가 단계). hanpass-ph 정책팩 `KR_DEFAULT` 임계와 연계(임계 정본은 규제 레이어, 01/02 PRD).
4. **위임·대결(Delegation)**(구현 완료, V24): 승인자 부재 시 대결자·기간([from_at, to_at)) 지정. 생성·회수 공통으로 **감사 이벤트 `APPROVAL_DELEGATION_CHANGED` emit**(ApprovalDelegationService). self-delegation·역전 기간은 CHECK로 거부. 유효 승인자 결의는 활성 위임의 대결자를 라인 기본 scope보다 우선.
5. **불변 정책 유지·확장**: self-approval 금지(maker≠checker)·payload_hash drift guard·staged_payload(기존 유지) + 다단계에서 각 단계 maker/checker 분리. delegated FDS approve도 bo-api가 현재 pending row의 immutable hash를 요청 `payloadHash`와 먼저 비교한 뒤에만 엔진을 호출하며, 엔진 검증은 독립적으로 유지한다.
6. **CTR 규제 임계 hot-reload 제외(BR, CTR/STR 모니터링 통합 — 코드=truth)**: `CTR_THRESHOLD`(CTR 통화별 규제 임계 변경, §4.2)은 **hot-reload 우회 불가** — 다른 정책 변경과 달리 즉시 적용 경로가 없고 **4-eyes 결재 EXECUTED 시점에만** `aml_ctr_thresholds`(DB §3.22a)에 반영된다(규제값 무단 변경 방지). CTR 임계는 규제 레이어 값이므로 임계값 자체는 Policy Pack(PH_AMLC/KR_DEFAULT) 정본을 따르고 본 결재는 그 반영 통제만 담당한다. `REPORT_RULE`(룰 활성화 DRAFT→ACTIVE)도 결재 EXECUTED 시에만 상태 전이(시뮬레이션 요약 동반, STR_MANUAL 수동 전용 거부).
7. **FDS 결재함 least-privilege**: coarse 진입은 지원 checker capability 하나 이상이면 되지만 목록은 exact-capability row만 필터한 뒤 페이지를 자른다. 상세·승인·반려는 row를 먼저 읽고 subject/marker를 판정하며 실패 시 downstream call/local mutation은 0이다. maker≠checker와 payload drift guard는 그 뒤에도 독립 적용한다. local fallback 상신 maker는 인증 principal이고 기본 actor 대체는 없다.

### 4.4 화면 (신규)
| 화면 ID | 명칭 | 역할 |
|---|---|---|
| BO-APRL-001 | 결재선 정의 | subject_type×라인×승인역할×임계(threshold_json) 매핑 조회·편집(감사 `APPROVAL_LINE_CHANGE`). 다단계(step_no)/임계 편집은 본 화면 내 **EscalationEditor** 섹션. bo-web `ApprovalLineRoutes`(`/admin/approval-lines`) |
| BO-APRL-002 | 결재 위임(대결) 관리 | 대결자 지정·위임 기간·회수(다단계 정의 아님). bo-web `ApprovalDelegations`(`/admin/approval-delegations`) |
| BO-APRL-003 | 사용자 지정 결재선 구성 | (tenant, subject_type, step) 단계별 **특정 등록 운영자**를 승인자로 지정(`bo_approval_route_members`, V27). bo-web `ApprovalLineMembers`. 한 단계 복수 승인자 허용 |
| (연계) AML-APR-001 / SFDS-APPR-001 | 결재 대기함 | 정의된 라인·지정 승인자에 따라 라우팅된 결재 처리(기존 화면, 라인 정본 소비) |

### 4.5 데이터·API
- 테이블(구현 완료):
  - `bo_approval_lines`(line_code·label·required_scope·sort_no, V22)
  - `bo_approval_routes`(PK `(tenant_id, subject_type, step_no)`·line_code·required·threshold_json JSONB, V22)
  - `bo_approval_delegations`(delegation_id·tenant_id·line_code·delegator_user_id·delegate_user_id·from_at·to_at·reason, V24)
  - **`bo_approval_route_members`**(PK `(tenant_id, subject_type, step_no, user_id)`, user_id→`bo_admin_users` FK, V27) — (tenant, subject_type, step)별 지정 승인자(복수 허용)
- 엔진 연계: aml-svc/fds-svc 결재 생성 시 `approval_line`/단계를 **bo-api 라우팅 정의에서 조회**(현 단계는 정의·노출 + aml-svc `ApprovalLineResolver` 미러링; 지정 사용자만 실제 승인 가능한 런타임 강제는 엔진 소관 후속). 실행 전이는 엔진 유지.
- API(구현 완료):
  - 결재선 카탈로그·라우팅: `GET /api/v1/bo/admin/approval-lines` · `GET/PUT .../approval-routes`(`tenantId` 쿼리, PUT=set 교체)
  - 위임: `GET .../approval-delegations`(`tenantId`·`active`) · `POST .../approval-delegations` · **`DELETE .../approval-delegations/{id}`**(위임 회수) · `GET .../approval-lines/{lineCode}/effective-approver`(유효 승인자 결의, `tenantId`)
  - 지정 승인자: `GET/PUT .../approval-route-members`(`tenantId`) · **`GET .../approval-route-members/resolve`**(`tenantId`·`subjectType` — 결재함 노출용 단일 subject 지정 승인자 결의)

### 4.6 결재 상세 표시 컨텍스트 — FP_WHITELIST(오탐 면제 등록) (2026-07-20, 코드=truth, fix/wlf-hit-rawdata-approval-context)

AML-APR-001 결재 대기함(§4.4 `(연계)` — 화면 상세 정의는 `02-aml-sass-functional-spec.md` §11.1)의 상세 모달이 `subjectType=FP_WHITELIST`(WLF 오탐 면제 등록, aml-svc `FpWhitelistService`) 건을 다룰 때의 표시 계약을 정의한다. 이 절은 **표시 계층 전용**이며 §4.5 결재 데이터·API(`aml_approvals` 계약)를 변경하지 않는다.

- **원문 계약(불변)**: `FpWhitelistService`(TAG `FPW2`)가 `subjectRef` 를 `FPW2|targetRef|targetType|matchedEntryId|whitelistVersion|screeningId|expiresAtMillis` 파이프 튜플로 조립(REVOKE 상신은 `REVOKE|whitelistId`)하고, `payloadHash` 는 이 `subjectRef` 문자열로 sha256 잠금된다. bo-api `AmlApprovalService` 는 `subjectLabel=subjectRef` 그대로를 결재 상세 DTO 에 내린다(변경 없음). **`subjectRef`·`payloadHash`·`maker≠checker` 4-eyes 계약은 완전 불변** — 아래 표시 파싱은 이 문자열을 읽기 전용으로 해석만 한다.
- **표시 계층 파싱(bo-web 전용)**: `subjectRef` 원문을 결재자가 그대로 읽지 않도록, bo-web 이 순수 함수 `parseFpWhitelistSubjectRef(subjectRef)` 로 파싱해 사람이 읽는 컨텍스트 카드를 렌더한다 — 백엔드(aml-svc·bo-api) 왕복이나 계약 변경 없이 표시 문자열만 재구성한다. 파싱 실패(포맷 불일치·구버전 subjectRef 등)는 **fallback 계약** — 원문 raw 표기를 그대로 유지해 결재 자체를 막지 않는다.
- **표시 필드**(가정 A4, 문서 §13.5·본 절 미정의 지점에 대한 최소 필드 확정 — 요구 최소 필드): 거래번호(파싱된 `screeningId` 로 `GET /api/v1/bo/aml/screenings/{id}` 상세의 `transactionRef` 보강 조회, 조회 실패는 행 생략), 대상 유형(`targetType` — CUSTOMER/COUNTERPARTY), 스크리닝 대상(`targetRef` + 이름 reveal), 매칭 명단 기재명(`matchedEntryId` + 이름 reveal), 매칭 룰 버전(`whitelistVersion`), 면제 만료일(`expiresAtMillis`→ISO, 부재='무기한'), 스크리닝 상세 링크. REVOKE 상신은 '오탐 면제 회수' 라벨 + `whitelistId` 1행.
- **reveal 게이트(BR-007 과 구분)**: 결재 상세는 `02-aml-sass-functional-spec.md` §3.1 BR-007 의 **자동 열람(auto-reveal)** 대상이 아니다 — 결재함은 WLF 심사 상세 화면이 아니므로, 스크리닝 대상 이름·매칭 명단 기재명은 기본 마스킹 + `PiiRevealRow`(비-auto 모드: 권한 `aml:pii:reveal` + 사유 입력 + `RAW_DATA_ACCESS` 감사) 게이트로만 열람한다.
- **결재 목록(대기함 테이블) '대상' 컬럼**: `FP_WHITELIST` 행은 파싱 성공 시 축약 라벨(`오탐 면제 · {targetRef}`, `title` 속성에 raw 유지)로 표기하고, 검색(hay)은 기존 `subjectRef` 전문 기준을 유지한다(동작 불변).

## 5. 데이터 모델 변경 요약 (신규/변경)
| 테이블 | 변경 |
|---|---|
| `bo_admin_users` | (스키마 유지). V2/V16의 공개 demo hash·identity는 checksum 불변의 역사로 남고 **V17 `quarantine_demo_seed_and_credentials`**가 exact 6계정의 role/tenant binding 회수 + `INACTIVE`/`password_hash='!'`로 forward 격리한다. explicit `demo` location의 repeatable만 `test@test.com` operator와 `choi.exec@aegis.example` checker(AML_APPROVER/VIEWER/POLICY_ADMIN, `tenant_demo`)를 재활성화한다. 운영 최초 SUPER_ADMIN은 IdP/OOB 절차이며 Flyway 사용자 seed가 아니다 |
| `bo_user_tenants` | **V20** — user↔tenant/workspace/data-scope 영속 바인딩. PK `(admin_user_id, tenant_id, workspace_id)`. `data_scope` CHECK는 **V21 이후 `('tenant','workspace')` 2종**(V20의 `platform`은 V21에서 제거 — 바인딩 행은 정의상 tenant/workspace 스코프, platform은 바인딩 없는 플랫폼 운영자 속성). 인덱스 `idx_bo_user_tenants_tenant(tenant_id, workspace_id)`·`idx_bo_user_tenants_user(admin_user_id)` |
| `bo_role_scopes` | **V20** — (role_id FK, scope) 커스텀 역할 scope 집합. 시스템 역할은 `BackofficeRole` enum 권위 |
| `bo_audit_logs` | **V18** — `tenant_id`, `workspace_id`를 nullable add→복원 불가 역사 row `platform/default` backfill→NOT NULL 순으로 적용. `trace_id`(generic/admin 최대 128자), `subject_kind`, `subject_id` 정규 컬럼과 scope/trace/subject 선두 index를 추가한다. 신규 write는 SecurityContext actor + TenantContext target을 캡처하고 명시적 causal trace 우선·없으면 MDC trace를 사용하며 repository는 save/scoped query만 노출한다. FDS/AML typed query는 각 domain explicit prefix/allowlist만 포함하고 IAM/ROLE/SECURITY/unknown event는 `BO_SUPER_ADMIN` generic `/api/v1/bo/audit[/{id}]`만 노출한다. FDS list는 source별 exact total을 합산해 최대 10,000행 merge window에서 `occurredAt DESC, sourceService ASC`, 동률 시 BO numeric ID ASC/FDS string ID ASC로 stable merge하고, detail은 `/api/v1/bo/fds/audit/{sourceService}/{auditId}` direct composite 조회다. AML도 최대 10,000행이고 actor는 partial match이며 BO `event`와 engine `eventCategory`를 분리하고 engine workspace provenance를 `default`로 표기한다. notify 신규 감사에는 raw `webhookHosts`를 저장하지 않고 역사 값은 host별 hash 처리한다. canonical AML ingest trace는 별도 64자/초과 422 계약을 유지한다. |
| `bo_user_roles` | write API 신설(스키마 유지) |
| `bo_menu`·`bo_menu_permissions` | **V23** — 4계층 RBAC·동적 메뉴(role×menu×CRUD). V26에서 메뉴 라벨 '고객사 관리'→'서비스 관리' |
| `bo_approval_lines`·`bo_approval_routes` | **V22** — 결재선 카탈로그(7종)·subject별 라우팅(다단계 step_no·임계 threshold_json) |
| `bo_approval_delegations` | **V24** — 승인자 위임(대결) |
| `bo_approval_route_members` | **V27** — (tenant_id, subject_type, step_no, user_id) 지정 승인자(복수 허용, user_id→`bo_admin_users` FK) |
| `aml_approvals.subject_type` CHECK | **16→19→20→21→20** 확장·정정(IRA_SUBMIT·HIGH_RISK_REGISTRY·PEP_APPROVAL, `CTR_THRESHOLD`(엔진 V23), `HRR_REGISTRATION`(엔진 V28); **V31에서 `TRAVEL_RULE_EXCEPTION` 제거로 현행 20종**). CTR 임계 변경은 엔진 결재함 노출 대상 |
| bo-api `AmlApprovalDtos.SubjectType` | **19→21→22→23→22** — `CTR_THRESHOLD`(CTR 규제 임계 변경, 엔진 연결 시 aml-svc 상신 위임, 승인선 `REPORTING_OFFICER`)·`REPORT_RULE`(CTR/STR 룰 활성화, bo-api 계층)·`REPORT_RULE_PARAM`(CTR/STR 룰 임계·변수 편집, 승인선 코드=`COMPLIANCE_OFFICER` — §4.2 COMPLIANCE 배정 미러)·`HRR_REGISTRATION` 추가 후, **V14(Travel Rule 제거)에서 `TRAVEL_RULE_EXCEPTION` 제거로 현행 22종** |
| bo-api `bo_menu`·`bo_approval_routes`·`bo_audit_logs` (Travel Rule 제거) | **V14__drop_travel_rule** — `aml-travel-rule` 메뉴·권한 seed DELETE, `TRAVEL_RULE_EXCEPTION` 결재 라우팅 seed DELETE, `chk_bo_audit_logs_event` allowlist 에서 `TRAVEL_RULE_EXCEPTION_RESOLVED` 제거(잔존 행 선행 DELETE + 제약 재생성). 엔진 대칭 aml-svc **V31**·fds-svc **V9** |
| bo-api `bo_audit_logs` CHECK | **V6** — CTR/STR 모니터링 감사 이벤트 3종 추가(`CTR_THRESHOLD_CHANGE_SUBMITTED`·`REPORT_RULE_ACTIVATE_SUBMITTED`·`AMLC_SUBMISSION_DELEGATED`) · **V9** — `REPORT_RULE_PARAM_CHANGE_SUBMITTED` 1종 append(기존 allowlist verbatim 보존) · **V24**(다통화, PLAN 20260818 U13) — `CURRENCY_PROFILE_APPLY_SUBMITTED`·`FDS_TENANT_REGULATORY_CURRENCY_CHANGE_SUBMITTED` 2종 append(V22 allowlist verbatim 보존) |
| bo-api `backoffice.aml_ctr_thresholds`·`aml_ph_banking_calendar` | **V5** — CTR 통화 임계·PH 영업일 캘린더(V7 이동공휴일). aml-svc 대칭(엔진 V3/V6, DB §3.22a/§3.22b) |
> Flyway: 적용분 수정 금지, 모든 변경은 additive/forward 보정이다. bo-api 현행 체인의 P0-02 보정은 `V17__quarantine_demo_seed_and_credentials.sql`, demo reference 재활성화는 versioned 운영 체인이 아닌 explicit `db/demo/R__activate_demo_reference_configuration.sql`이다. 플랫폼 role/menu/approval-line catalog는 제품 정의라 운영 migration에 유지하고, 로그인 계정·demo tenant/connector만 분리한다. API/DTO/화면 계약 변경은 없다. aml-svc의 대칭 경계는 DB §7 V45/demo repeatable을 따른다.

## 6. 화면 인벤토리 (신규)
BO-USR-001~004 · BO-ROLE-001/002 · BO-PERM-001 · BO-MENU-001 · BO-APRL-001/002/003 (+ 기존 결재함 AML-APR-001·SFDS-APPR-001 라인 소비).

**시스템 관리 NAV(구현 완료, `lib/nav.ts` `ADMIN_ITEMS`, 플랫폼-레벨 `/admin` 콘솔, `BO_SUPER_ADMIN` 전용) — 6종**:
1. 사용자(`/admin/users`, BO-USR-001)
2. 역할/권한(`/admin/roles`, BO-ROLE-001)
3. 권한 매트릭스(`/admin/permission-matrix`, BO-PERM-001)
4. 메뉴 권한(`/admin/menus`, BO-MENU-001)
5. 결재선 정의(`/admin/approval-lines`, BO-APRL-001 — 지정 승인자 BO-APRL-003 동거)
6. 결재 위임(`/admin/approval-delegations`, BO-APRL-002)

추가: 헤더 **결재함 배지**(`ApprovalInboxMenu`) — 대기 결재 신호 노출.

추가: 공통 셸 **서비스(테넌트) 선택기**(헤더 우측, 2026-08-10 스코프 가드 — 코드=truth) — 목록 `GET /api/v1/bo/fds/tenants` 를 **실제로 받을 수 있는 세션에만 노출**한다. 판정은 서버 `@PreAuthorize`(`SFDS_TENANT:READ`)와 **1:1 인 exact capability**(또는 wildcard `*`)이며(§3.3-7 typed read capability), 스코프가 없는 세션(예 `aml:*` 만 보유한 AML 전용 운영자)에서는 **조회를 발사하지도 빈 드롭다운을 렌더하지도 않는다** — 종전에는 무조건 마운트해 모든 화면에서 확정 403 이 났다(기능 영향 0·감사/콘솔 노이즈). 선택기가 없는 세션의 테넌트 컨텍스트는 **서버 `TenantContextFilter` 가 결정**한다(`Tenant-Id` 헤더 부재 + 바인딩 1개 → 그 바인딩이 기본 컨텍스트, §2.2-3 — 클라이언트 폴백을 새로 만들지 않는다). 플랫폼 운영자에게만 `전체`(tenant-agnostic) 옵션이 붙으며, 선택기는 **data-scope 선택일 뿐 메뉴·IAM·업무 인가를 넓히지 않는다**(§2.2-3 원칙 그대로). 바인딩이 2개 이상인데 선택기가 없는 계정은 컨텍스트 확정 불가로 `BO-TENANT-REQUIRED` 가 났고 이는 **본 가드 이전과 동일한 기존 미해결**이었다(해소는 bo-api 변경 — 후속).

**본인 바인딩 소스 추가(2026-08-10, 코드=truth 후속 — 위 미해결 해소)**: 위 잔존 항목의 실제 크기는 "선택기 미노출"이 아니라 **로그인 자체 불가**였다 — `TenantContextFilter` 가 `GET /api/v1/bo/auth/me` 까지 테넌트 컨텍스트를 요구해 403 을 내고 `SessionGuard` 가 그 403 에 세션을 지워 `/login` 으로 되돌리므로, 바인딩 ≥2 인 **모든** 비-플랫폼 오퍼레이터가 순환에 갇혔다(어느 `Tenant-Id` 를 실어야 하는지 알 방법 자체가 없음). 이를 **본인 바인딩 조회 `GET /api/v1/bo/auth/me/tenants`**(인증만 요구·본인 바인딩만·`tenantId`/`workspaceId` 2필드, §2.2-7·§2.4)를 **선택기의 두 번째 소스**로 붙여 닫는다. 선택기 소스는 **상호배타**다 — `SFDS_TENANT:READ`(또는 `*`) 보유 세션은 종전대로 `GET /api/v1/bo/fds/tenants` 레지스트리를 쓰고(위 스코프 가드 계약 그대로, 스코프 없는 세션의 `fds/tenants` 호출 0회 유지), **미보유 세션만** 본인 바인딩을 소스로 쓴다. 미보유 세션의 표시 규칙은 **0건 = 선택기 미노출**(거짓 정보 방지 원칙 그대로 — 컨텍스트는 서버가 결정) · **1건 = 자동 선택**(서버 폴백과 결과 동일) · **2건 이상 = 선택기 노출**이며, 선택 시 `Tenant-Id` 가 실려 `BO-TENANT-REQUIRED` 가 해소된다. 바인딩은 `(tenant, workspace)` 쌍이라 같은 테넌트가 여러 번 올 수 있어 **테넌트 단위로 접어** 표시한다(라벨은 `tenantId` — 미보유 세션은 레지스트리 표시명을 읽을 권한이 없으므로 표시명을 합성하지 않는다). **거부 3규칙·권한 판정은 무변경**이고(§2.2-7) 선택기는 여전히 **data-scope 선택일 뿐 메뉴·IAM·업무 인가를 넓히지 않는다**.

추가: 공통 셸 **언어 선택기**(`LanguageSwitcher`, 한국어/English) — 헤더 사용자(displayName) 버튼 옆 + 로그인 화면 상단 2곳에 노출(공통 컴포넌트). 쿠키 기반 locale(`NEXT_LOCALE`, 기본 `ko`; `[locale]` URL 라우팅 없음 — URL 구조 불변)이며 선택 시 쿠키 set(path=/, 1년)+`router.refresh()`로 전 화면이 한국어↔영어로 전환된다. 웹에 노출되는 모든 문자열(메뉴·버튼·테이블 헤더·상태/등급 라벨·빈 상태·에러/토스트·aria-label·placeholder)은 next-intl 메시지 카탈로그(`messages/ko.json`·`messages/en.json`, 두 파일 키 셋 100% 일치)로 일원화하고, 서버 enum/코드 값은 프론트 카탈로그에서 라벨 매핑해 표기한다.

## 7. 정합·불일치 해소 (본 문서가 정본화)
1. `approval_line` FDS(6)/AML(6) → **단일 통합 enum 7종**(§4.1, V22 `bo_approval_lines`). FDS §16.5·AML 부록 G 동기화 필요(잔여).
2. `aml_approvals.subject_type` CHECK 16 → 18(§4.2).
3. ~~미사용 감사이벤트~~ → `ROLE_ASSIGNED`/`ROLE_REVOKED`/`PASSWORD_CHANGED`를 AdminUserService에서 **실제 emit**(확인 완료) + `ROLE_SCOPE_CHANGED`(V20)·`APPROVAL_LINE_CHANGE`(V22)·`MENU_PERMISSION_CHANGED`(V23)·`APPROVAL_DELEGATION_CHANGED`(V24) 추가.
4. ~~커스텀 역할 scope 0 결손~~ → `bo_role_scopes`로 해소(§3.1, V20).
5. ~~메뉴 하드코딩 4항목~~ → 데이터·역할 기반 동적 메뉴로 해소(§3.3-4, V23).

## 8. 우선순위 로드맵
- **P1 (사용자·역할 기본 결선) — 완료**: 계정 생성 시 역할 지정(roleIds)·수정/비번리셋/잠금해제·재활성/DELETE 비활성, `bo_user_roles` write + 배정 화면, 생애주기 감사 emit. 과거 demo bootstrap seed는 P0-02 V17이 운영에서 격리하며 demo profile에서만 repeatable로 복원한다. 운영 최초 SUPER_ADMIN은 IdP 또는 single-use OOB bootstrap이다.
- **P2 (테넌트 바인딩·권한 매트릭스) — 완료(V20·V21)**: `bo_user_tenants` + 헤더-위조 방지 스코프 강제(TenantContextFilter), 권한 매트릭스 화면, 커스텀 역할 scope(`bo_role_scopes`). data_scope 어휘 정합(V21).
- **P3 (결재선 관리) — 완료(V22/V23)**: 통합 approval_line 7종·subject별 라우팅(부록 C 시드)·subject_type 20 정합(PEP_APPROVAL→EXECUTIVE_APPROVAL, CTR_THRESHOLD→REPORTING_OFFICER 포함). 결재선 정의 화면 bo-web `ApprovalLineRoutes`. 엔진이 bo-api 라우팅을 강제 소비하는 런타임 동기화는 후속(§4.3 비고).
- **P4a (4계층 RBAC·동적 메뉴) — 완료(V23, V26 라벨 정합)**: `bo_menu`/`bo_menu_permissions` 모델·동적 메뉴(MenuController DB 조회), bo-web `MenuPermissions`.
- **P4b (다단계/위임/임계) — 완료(V24)**: 위임(대결) `bo_approval_delegations`·유효 승인자 결의, 다단계(step_no)/임계(threshold_json)는 V22 라우팅에 내장. bo-web `ApprovalDelegations`.
- **사용자 지정 결재선 — 완료(V27)**: (tenant, subject_type, step)별 지정 승인자 `bo_approval_route_members`, bo-web `ApprovalLineMembers`. + 헤더 결재함 배지 `ApprovalInboxMenu`.
- **잔여(후속)**: 엔진 런타임의 bo-api 라우팅·지정 승인자 강제 소비, ROLE_CHANGE 4-eyes 실행 결재 워크플로, FDS §16.5·AML 부록 G 동기화.

## 9. 가정·미해결
- 본 문서는 **기능 정의(요구·화면·데이터·API)** 정본. 구현은 후속 PLAN/태스크로 분해(bo-api 헥사고날 아님 — 피처 패키지).
- 규제 임계(CTR/STR 등)는 §4.3 임계 라우팅의 입력일 뿐, 정본은 Policy Pack(01/02 PRD) 유지.
- KYE 임직원 스크리닝·조직 연계(AML-EDU-001)는 본 IAM의 조직(그룹) 모델과 연계 검토(후속).
- FDS §16.2·AML 부록 B/C/G 및 §1.6 deferral 라인에 본 문서(FS-BO-IAM-001) 포인터 추가 권고(후속 정합).
