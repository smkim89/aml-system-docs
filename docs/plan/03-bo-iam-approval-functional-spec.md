# BO IAM·결재선 기능정의서 — 사용자·권한·결재라인 관리 (FS-BO-IAM-001)

> 문서 ID FS-BO-IAM-001 · 작성일 2026-06-19 · 소관 `bo-api`(+`bo-web` 화면)
> 본 문서는 FDS PRD §16.2·AML PRD §1.6·부록 B/C/G가 "**IAM 화면은 bo-api PRD 소관**"·"**결재선 정의는 bo-api IAM 소관**"으로 deferral 한 미작성 영역을 정본화한다.
> 정본 경계: 인증·세션·RBAC·사용자/역할/결재선 관리는 **bo-api 소유**. 도메인 결재 실행(전이·실행)은 엔진(fds-svc/aml-svc) 소유.
> 멀티테넌시 모델: **기관 → 서비스(테넌트=`tenant_id`) → 워크스페이스(`workspace_id`)** (1 기관 : N 서비스, 테넌트 격리 경계=서비스). 사용자는 상위 기관/서비스 스코프로 바인딩한다.
>
> 변경 이력: 2026-06-19 — 테넌트=서비스 재정의(기관 → 서비스 → 워크스페이스). §0·§2.2 멀티테넌시·`bo_user_tenants`를 사용자↔서비스 바인딩으로 재기술, "고객사"→"서비스"; `tenant_id`/`workspace_id`·data_scope·role/scope 코드명 불변(의미만 서비스).

## 0. 개요

| 항목 | 내용 |
|---|---|
| 목적 | 백오피스 **사용자 관리(계정 생성·권한)** · **권한 관리(역할·scope·RBAC)** · **결재선(결재 라인) 관리**의 필요 기능을 전체 정의 |
| 대상 사용자 | 플랫폼 운영자(platformOperator)·서비스(테넌트, `tenant_id`) 관리자·준법감시/보안 관리자 |
| 현재 상태 | 인증·역할 enum·결재 4-eyes는 **존재**하나, 역할 배정·커스텀 scope·테넌트 바인딩·4계층 RBAC·**결재선 라우팅 관리**는 **미구현** (§1 현행 분석) |
| 비범위 | 도메인별 결재 대상의 비즈니스 로직(룰/시나리오/명단 등 — 01·02 PRD), 엔진 내부 결재 전이 |

## 1. 현행 분석 (As-Is) — EXISTS vs MISSING

| 영역 | 존재(As-Is) | 결손(Gap) |
|---|---|---|
| **사용자** | `bo_admin_users`(email·password_hash BCrypt·name·admin_type·department·status·last_login_at) / `bo_roles` / `bo_user_roles`(N:M). 로그인(`AuthService`, HMAC 세션 토큰). `AdminUserController` 생성·목록·상세·비활성(soft) | 생성 시 **역할 지정 불가**(`AdminUserRequest`에 roleIds 없음) · 수정/비밀번호 리셋/잠금 해제 API 없음 · **user↔tenant 영속 바인딩 없음**(Tenant-Id 헤더 의존) · 데모 유저 **시드 마이그레이션 부재**(스크립트 ad-hoc) |
| **권한** | `BackofficeRole` enum(FDS 8 + AML 7 + BO_SUPER_ADMIN, scope 보유). `@PreAuthorize` scope/role 게이트. 역할 행 Flyway 시드 | 역할↔사용자 **배정/회수 API 없음**(`bo_user_roles` write 부재) · 커스텀 역할 **scope 컬럼 없음**(DB 역할은 scope 0) · 메뉴 **4개 하드코딩**(MenuController) · **4계층 RBAC(그룹>직무>메뉴>페이지 CRUD) 미구현** · `ROLE_ASSIGNED/ROLE_REVOKED/PASSWORD_CHANGED` 감사이벤트 선언만 되고 emit 없음 |
| **결재선** | `aml_approvals`/`bo_fds_*_approval_requests`. 4-eyes(self-approval 금지·maker≠checker CHECK)·payload_hash drift guard·상태머신. `approval_line` 컬럼 존재 | `approval_line` **전부 `MAKER_CHECKER` 하드코딩**(aml-svc DEFAULT_LINE·bo-api 리터럴, 라우팅 미작동) · **결재선 정의/관리 전무**(subject별 라인·다단계·위임·임계) · FDS(6)·AML(6) `approval_line` enum **불일치** · `subject_type` CHECK(16) < Java enum(18: IRA_SUBMIT·HIGH_RISK_REGISTRY 누락) |
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
1. **계정 생성**(BO-USR-003): email(고유)·name·department·admin_type + **역할 다중 선택(roleIds)** + 서비스(테넌트) 바인딩(플랫폼 운영자=tenant-agnostic / 서비스(기관) 운영자=tenant_id·workspace 지정) + 초기 비밀번호(또는 초대 토큰) → `bo_admin_users` + `bo_user_roles` + `bo_user_tenants`(신규). 생성 시 `ADMIN_USER_CREATED`·`ROLE_ASSIGNED` 감사.
2. **수정/상태**(BO-USR-004): 정보 수정, 역할 추가/회수(`ROLE_ASSIGNED`/`ROLE_REVOKED`), 비밀번호 리셋(`PASSWORD_CHANGED`), `status` ACTIVE/INACTIVE/LOCKED 전이(잠금 해제), 비활성(soft `deactivate`). 자기 자신 비활성/권한축소 방지(BR).
3. **멀티테넌시 바인딩**(핵심 갭) — *테넌트=서비스* 모델(계층: **기관 → 서비스(테넌트=`tenant_id`) → 워크스페이스**, 1 기관 : N 서비스). user↔service(=tenant)/workspace/data-scope를 **영속**(`bo_user_tenants` — 사용자↔서비스 바인딩, 컬럼명 `tenant_id`=서비스 식별자)으로 두고, 세션 토큰·`TenantContextFilter`가 헤더 대신/우선 사용자 바인딩으로 스코프를 강제(헤더 위조 방지). 사용자는 상위 기관/서비스 스코프로 바인딩되며, 플랫폼 운영자는 전체, 서비스(기관) 운영자는 바인딩된 서비스(테넌트)만.
4. **데모/초기 시드**: 운영 부트스트랩 계정(최초 BO_SUPER_ADMIN)을 **Flyway 시드 또는 부트스트랩 절차**로 정본화(현 스크립트 ad-hoc 해소).

### 2.3 검색조건 (BO-USR-001)
상태(ACTIVE/INACTIVE/LOCKED) · 역할(roleCode) · 테넌트 · 부서 · 마지막 로그인 기간 · 이메일/이름 검색.

### 2.4 데이터·API·테이블
- 테이블: `bo_admin_users`(기존) + **신규 `bo_user_tenants`**(user_id, tenant_id, workspace_id, data_scope, PK 복합) + `bo_user_roles`(기존, write API 신설).
- API(신규/변경):
  - `POST /api/v1/bo/admin/users`(roleIds·tenantBindings 추가) · `PUT /api/v1/bo/admin/users/{id}` · `POST .../{id}:reset-password` · `POST .../{id}:unlock` · `POST .../{id}:deactivate`/`:reactivate`
  - `PUT /api/v1/bo/admin/users/{id}/roles`(배정/회수) · `PUT .../{id}/tenants`(테넌트 바인딩)
- 권한: `BO_SUPER_ADMIN` 또는 신규 `BO_IAM_ADMIN` scope `bo:admin:iam`.

## 3. 권한·역할 관리 (Permission/Role Management)

### 3.1 역할 카탈로그 (정본 통합)
- 시스템 역할(is_system, 불변): FDS 8종(SFDS_PLATFORM_OPS/ADMIN·VIEWER·AUTHOR·APPROVER·OPS·ANALYST·ADMIN) · AML 7종(AML_VIEWER·COMPLIANCE·APPROVER·CASE_ANALYST·POLICY_ADMIN·AUDITOR·PII_REVEAL) · BO_SUPER_ADMIN(`*`). scope 정본 = `BackofficeRole`.
- **커스텀 역할**(신규): 운영자가 정의, **scope 집합 보유**. → `bo_roles`에 **`scopes` 컬럼(또는 `bo_role_scopes`) 추가**(현재 커스텀 역할 scope 0 결손 해소). scope 카탈로그(정본)는 별도 enum/표.

### 3.2 화면 (신규)
| 화면 ID | 명칭 | 역할 |
|---|---|---|
| BO-ROLE-001 | 역할 목록 | 시스템/커스텀 역할·scope·사용 사용자 수 |
| BO-ROLE-002 | 역할 상세·편집 | 커스텀 역할 scope 편집(시스템 역할 읽기전용)·4-eyes 결재(ROLE_CHANGE) |
| BO-PERM-001 | 권한 매트릭스 | 역할×화면(scope) 매트릭스 뷰(FDS §16.2 + AML 부록 B 통합 정본) |
| BO-MENU-001 | 메뉴·페이지 권한 | 4계층(그룹>직무>메뉴>페이지 CRUD) 매핑 관리 |

### 3.3 기능 요구
1. **역할↔사용자 배정/회수**(§2.2와 연계): `bo_user_roles` write API + 화면. 감사 emit.
2. **커스텀 역할 + scope**: 생성·scope 편집(시스템 역할 보호). 역할 변경은 4-eyes(`ROLE_CHANGE`) 대상으로 권고.
3. **4계층 RBAC**(벤치마크 정합): 그룹(조직) > 직무(역할) > 메뉴 > 페이지 액션(CRUD). `bo_menu`/`bo_menu_permissions`(역할×메뉴×CRUD) 모델 신설.
4. **데이터 기반 메뉴**(핵심 갭): `MenuController` 하드코딩 4항목 → **DB·역할 기반 동적 메뉴**(bo-web nav와 정합 — `lib/nav.ts` 21채널/운영·설정 IA 반영, 역할 필터 서버화).
5. **scope→capability**: `@PreAuthorize` scope 게이트 유지 + scope↔화면/액션 매트릭스 정본화.

### 3.4 API·테이블
- 테이블: `bo_roles`(+scopes), **신규** `bo_role_scopes`·`bo_menu`·`bo_menu_permissions`, `bo_user_roles`(write).
- API: `POST/PUT/GET /api/v1/bo/admin/roles`(+scopes) · `PUT .../roles/{code}/scopes` · `PUT .../users/{id}/roles` · `GET /api/v1/bo/menu`(동적·역할 기반).

## 4. 결재선(결재 라인) 관리 (Approval-Line Management) — 핵심 신규

### 4.1 통합 approval_line enum (불일치 해소)
현행 FDS 6종(SELF_APPROVAL_DISABLED·MAKER_CHECKER·COMPLIANCE_MANAGER·RISK_MANAGER·SECURITY_ADMIN·EXECUTIVE_APPROVAL)과 AML 6종(MAKER_CHECKER·AML_OFFICER·COMPLIANCE_MANAGER·REPORTING_OFFICER·SECURITY_ADMIN·EXECUTIVE_APPROVAL)이 상이. → **단일 정본 enum**으로 통합(합집합 + 매핑):
`MAKER_CHECKER · AML_OFFICER · COMPLIANCE_MANAGER · RISK_MANAGER · REPORTING_OFFICER · SECURITY_ADMIN · EXECUTIVE_APPROVAL`(+ 표시 비활성 의미 `SELF_APPROVAL_DISABLED`는 라인이 아니라 **불변 정책 플래그**로 분리). 각 라인 ↔ 승인 권한 역할(scope) 매핑 테이블로 정의.

### 4.2 결재선 정의 (subject_type별 라우팅 — 부록 C 구현)
- 현행: 모든 결재가 `MAKER_CHECKER` 하드코딩 → **subject_type별 라인 라우팅**을 데이터로 정의(부록 C 정본 구현):
  - 예) RA_MODEL·TM_SCENARIO·COUNTRY_RISK·POLICY_PACK → COMPLIANCE_MANAGER · EDD_CLOSE → AML_OFFICER · STR/CTR → REPORTING_OFFICER · SECRET_CHANGE → SECURITY_ADMIN.
- **subject_type 정합**: `aml_approvals` CHECK(16) → **18**로 확장(IRA_SUBMIT·HIGH_RISK_REGISTRY 추가, Flyway).

### 4.3 기능 요구
1. **결재선 정의 관리**(BO-APRL-001): subject_type × 결재선 × 승인자 역할 매핑을 운영자가 조회·변경(4-eyes `APPROVAL_LINE_CHANGE`). 테넌트(=서비스)별 override 허용(플랫폼 기본 + 서비스별 커스터마이즈).
2. **다단계(순차) 라인**: 1차→2차→최종 등 N단계 승인 체인 정의(현 단일 maker-checker 확장). 각 단계 승인 역할·필수 여부.
3. **임계값 기반 라우팅**: 금액/위험등급/건수 임계로 라인 상향(예 고액 STR → EXECUTIVE_APPROVAL 추가 단계). PH/KR 등 Policy Pack 임계와 연계(임계 정본은 규제 레이어).
4. **위임·대결(Delegation)**: 승인자 부재 시 대결자·기간 지정, 위임 감사.
5. **불변 정책 유지·확장**: self-approval 금지(maker≠checker)·payload_hash drift guard·staged_payload(기존 유지) + 다단계에서 각 단계 maker/checker 분리.

### 4.4 화면 (신규)
| 화면 ID | 명칭 | 역할 |
|---|---|---|
| BO-APRL-001 | 결재선 정의 | subject_type×라인×승인역할×임계 매핑 조회·편집(4-eyes) |
| BO-APRL-002 | 다단계/위임 관리 | 순차 단계 정의·대결자 지정·위임 기간 |
| (연계) AML-APR-001 / SFDS-APPR-001 | 결재 대기함 | 정의된 라인에 따라 라우팅된 결재 처리(기존 화면, 라인 정본 소비) |

### 4.5 데이터·API
- 테이블(신규): `bo_approval_lines`(line_code·label·required_role/scope) · `bo_approval_routes`(tenant_id·subject_type·step_no·line_code·threshold_json·required) · `bo_approval_delegations`(delegator·delegate·from·to).
- 엔진 연계: aml-svc/fds-svc 결재 생성 시 `approval_line`/단계를 **bo-api 라우팅 정의에서 조회**(현 DEFAULT_LINE 하드코딩 대체). 실행 전이는 엔진 유지.
- API: `GET/PUT /api/v1/bo/admin/approval-lines` · `GET/PUT .../approval-routes` · `POST .../delegations`.

## 5. 데이터 모델 변경 요약 (신규/변경)
| 테이블 | 변경 |
|---|---|
| `bo_admin_users` | (유지) |
| `bo_user_tenants` | **신규** — user↔tenant/workspace/data-scope 영속 바인딩 |
| `bo_roles` | **+`scopes`/`bo_role_scopes`** (커스텀 역할 scope) |
| `bo_user_roles` | write API 신설(스키마 유지) |
| `bo_menu`·`bo_menu_permissions` | **신규** — 4계층 RBAC·동적 메뉴 |
| `bo_approval_lines`·`bo_approval_routes`·`bo_approval_delegations` | **신규** — 결재선 정의·다단계·위임 |
| `aml_approvals.subject_type` CHECK | **16→18** 확장(IRA_SUBMIT·HIGH_RISK_REGISTRY) |
> Flyway: bo-api·aml-svc 각 신규 마이그레이션(적용분 수정 금지). 모든 변경 additive.

## 6. 화면 인벤토리 (신규)
BO-USR-001~004 · BO-ROLE-001/002 · BO-PERM-001 · BO-MENU-001 · BO-APRL-001/002 (+ 기존 결재함 AML-APR-001·SFDS-APPR-001 라인 소비). 신규 NAV: **설정 › 시스템 관리**(사용자·역할·권한 매트릭스·메뉴 권한·결재선) — 플랫폼 운영자/IAM 관리자 전용.

## 7. 정합·불일치 해소 (본 문서가 정본화)
1. `approval_line` FDS(6)/AML(6) → **단일 통합 enum**(§4.1). FDS §16.5·AML 부록 G 동기화 필요.
2. `aml_approvals.subject_type` CHECK 16 → 18(§4.2).
3. 미사용 감사이벤트(`ROLE_ASSIGNED`/`ROLE_REVOKED`/`PASSWORD_CHANGED`)를 §2·§3 기능에서 **실제 emit**.
4. 커스텀 역할 scope 0 결손 → `bo_roles` scope 보유(§3.1).
5. 메뉴 하드코딩 4항목 → 데이터·역할 기반 동적 메뉴(§3.3-4).

## 8. 우선순위 로드맵
- **P1 (사용자·역할 기본 결선)**: 계정 생성 시 역할 지정(roleIds)·수정/비번리셋/잠금해제, `bo_user_roles` write + 배정 화면, 감사 emit. 부트스트랩 시드 정본화.
- **P2 (테넌트 바인딩·권한 매트릭스)**: `bo_user_tenants` + 헤더-위조 방지 스코프 강제, 권한 매트릭스 화면, 커스텀 역할 scope.
- **P3 (결재선 관리)**: 통합 approval_line·subject별 라우팅(부록 C 구현)·subject_type 18 정합, 결재선 정의 화면, 엔진이 bo-api 라우팅 소비.
- **P4 (4계층 RBAC·동적 메뉴·다단계/위임/임계)**: bo_menu 모델·동적 메뉴, 순차 라인·위임·임계 라우팅.

## 9. 가정·미해결
- 본 문서는 **기능 정의(요구·화면·데이터·API)** 정본. 구현은 후속 PLAN/태스크로 분해(bo-api 헥사고날 아님 — 피처 패키지).
- 규제 임계(CTR/STR 등)는 §4.3 임계 라우팅의 입력일 뿐, 정본은 Policy Pack(01/02 PRD) 유지.
- KYE 임직원 스크리닝·조직 연계(AML-EDU-001)는 본 IAM의 조직(그룹) 모델과 연계 검토(후속).
- FDS §16.2·AML 부록 B/C/G 및 §1.6 deferral 라인에 본 문서(FS-BO-IAM-001) 포인터 추가 권고(후속 정합).
