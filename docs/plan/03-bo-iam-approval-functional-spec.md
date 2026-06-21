# BO IAM·결재선 기능정의서 — 사용자·권한·결재라인 관리 (FS-BO-IAM-001)

> 문서 ID FS-BO-IAM-001 · 작성일 2026-06-19 · 소관 `bo-api`(+`bo-web` 화면)
> 본 문서는 FDS PRD §16.2·AML PRD §1.6·부록 B/C/G가 "**IAM 화면은 bo-api PRD 소관**"·"**결재선 정의는 bo-api IAM 소관**"으로 deferral 한 미작성 영역을 정본화한다.
> 정본 경계: 인증·세션·RBAC·사용자/역할/결재선 관리는 **bo-api 소유**. 도메인 결재 실행(전이·실행)은 엔진(fds-svc/aml-svc) 소유.
> 멀티테넌시 모델: **기관 → 서비스(테넌트=`tenant_id`) → 워크스페이스(`workspace_id`)** (1 기관 : N 서비스, 테넌트 격리 경계=서비스). 사용자는 상위 기관/서비스 스코프로 바인딩한다.
>
> 변경 이력:
> - 2026-06-21 — **구현 정합화(코드 truth)**: P1~P4·사용자 지정 결재선이 Flyway V18~V27로 **구현 완료**됨을 §1~§8 전반에 반영. `bo_user_tenants`(PK `admin_user_id`)·`bo_role_scopes`(V20)·data_scope `tenant|workspace`(V21)·`bo_approval_lines`/`bo_approval_routes`(V22)·`bo_menu`/`bo_menu_permissions`(V23)·`bo_approval_delegations`(V24)·데모 테넌트/라벨 정합(V26)·`bo_approval_route_members`(V27) 정본화. 화면(BO-APRL-003 신설·BO-APRL-002 명칭 정정)·NAV 6종·API 경로(DELETE 사용자 비활성·위임 회수·effective-approver·route-members) 코드 기준 정정. 감사 emit(ROLE_ASSIGNED/REVOKED/PASSWORD_CHANGED·ROLE_SCOPE_CHANGED·APPROVAL_LINE_CHANGE·APPROVAL_DELEGATION_CHANGED) 실재 확인. ROLE_CHANGE 4-eyes 워크플로는 **후속 과제**(현재 RBAC 게이트 + 감사만).
> - 2026-06-19 — 테넌트=서비스 재정의(기관 → 서비스 → 워크스페이스). §0·§2.2 멀티테넌시·`bo_user_tenants`를 사용자↔서비스 바인딩으로 재기술, "고객사"→"서비스"; `tenant_id`/`workspace_id`·data_scope·role/scope 코드명 불변(의미만 서비스).

## 0. 개요

| 항목 | 내용 |
|---|---|
| 목적 | 백오피스 **사용자 관리(계정 생성·권한)** · **권한 관리(역할·scope·RBAC)** · **결재선(결재 라인) 관리**의 필요 기능을 전체 정의 |
| 대상 사용자 | 플랫폼 운영자(platformOperator)·서비스(테넌트, `tenant_id`) 관리자·준법감시/보안 관리자 |
| 현재 상태 | 본 정의서의 P1~P4 + 사용자 지정 결재선이 **구현 완료**(Flyway V18~V27, bo-api 컨트롤러·bo-web 화면). 역할 배정·커스텀 scope·테넌트 바인딩(헤더 위조 방지)·4계층 RBAC·동적 메뉴·결재선 라우팅 정의·다단계/위임/지정 승인자까지 **정의 측(definition plane) 완비**. 잔여: 엔진 런타임이 bo-api 라우팅을 강제 소비(§4.3 비고)·ROLE_CHANGE 4-eyes 워크플로는 **후속**(§1 현행 분석) |
| 비범위 | 도메인별 결재 대상의 비즈니스 로직(룰/시나리오/명단 등 — 01·02 PRD), 엔진 내부 결재 전이 |

## 1. 현행 분석 (As-Is) — EXISTS vs MISSING

| 영역 | 존재(As-Is) | 결손(Gap) |
|---|---|---|
| **사용자** | `bo_admin_users`(email·password_hash BCrypt·name·admin_type·department·status·last_login_at) / `bo_roles` / `bo_user_roles`(N:M). 로그인(`AuthService`, HMAC 세션 토큰). `AdminUserController` 생성·목록·상세·수정·역할 set·비번 리셋·잠금 해제·재활성·비활성(DELETE soft) | ~~생성 시 역할 지정 불가~~ → **해소**(`AdminUserRequest.roleIds` + 수정/비번리셋/unlock/reactivate API, V19 생애주기 감사) · ~~user↔tenant 영속 바인딩 없음~~ → **해소**(`bo_user_tenants` V20, 헤더 위조 방지) · ~~데모 유저 시드 마이그레이션 부재~~ → **해소**(V18 `iam_bootstrap_seed`: test@test.com / V27 데모 승인자 5명) |
| **권한** | `BackofficeRole` enum(FDS 8 + AML 7 + BO_SUPER_ADMIN, scope 보유). `@PreAuthorize` scope/role 게이트. 역할 행 Flyway 시드 | ~~역할↔사용자 배정/회수 API 없음~~ → **해소**(`PUT .../users/{id}/roles`, `bo_user_roles` write) · ~~커스텀 역할 scope 컬럼 없음~~ → **해소**(`bo_role_scopes` V20) · ~~메뉴 4개 하드코딩~~ → **해소**(`bo_menu`/`bo_menu_permissions` V23, MenuController DB 조회) · ~~4계층 RBAC 미구현~~ → **해소**(역할×메뉴×CRUD) · ~~`ROLE_ASSIGNED/ROLE_REVOKED/PASSWORD_CHANGED` emit 없음~~ → **해소**(AdminUserService 실제 emit, V19 생애주기 + `ROLE_SCOPE_CHANGED` V20). 잔여: ROLE_CHANGE 4-eyes 워크플로(후속) |
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
1. **계정 생성**(BO-USR-003): email(고유)·name·department·admin_type + **역할 다중 선택(roleIds)** + 서비스(테넌트) 바인딩(플랫폼 운영자=tenant-agnostic / 서비스(기관) 운영자=tenant_id·workspace 지정) + 초기 비밀번호(또는 초대 토큰) → `bo_admin_users` + `bo_user_roles` + `bo_user_tenants`(신규). 생성 시 `ADMIN_USER_CREATED`·`ROLE_ASSIGNED` 감사.
2. **수정/상태**(BO-USR-004): 정보 수정, 역할 추가/회수(`ROLE_ASSIGNED`/`ROLE_REVOKED`), 비밀번호 리셋(`PASSWORD_CHANGED`), `status` ACTIVE/INACTIVE/LOCKED 전이(잠금 해제), 비활성(soft `deactivate`). 자기 자신 비활성/권한축소 방지(BR).
3. **멀티테넌시 바인딩**(구현 완료, V20) — *테넌트=서비스* 모델(계층: **기관 → 서비스(테넌트=`tenant_id`) → 워크스페이스**, 1 기관 : N 서비스). user↔service(=tenant)/workspace/data-scope를 **영속**(`bo_user_tenants` — 사용자↔서비스 바인딩, 컬럼명 `tenant_id`=서비스 식별자)으로 두고, `TenantContextFilter`가 요청 헤더(Tenant-Id/Workspace-Id)값을 `bo_user_tenants` 바인딩으로 **검증**하여 스코프를 강제한다(플랫폼 운영자는 바인딩 없이 tenant-agnostic으로 제외, 그 외 운영자의 헤더 위조 방지). 사용자는 상위 기관/서비스 스코프로 바인딩되며, 플랫폼 운영자는 전체, 서비스(기관) 운영자는 바인딩된 서비스(테넌트)만.
4. **데모/초기 시드**: 운영 부트스트랩 계정(최초 BO_SUPER_ADMIN)을 **Flyway 시드 또는 부트스트랩 절차**로 정본화(현 스크립트 ad-hoc 해소).

### 2.3 검색조건 (BO-USR-001)
상태(ACTIVE/INACTIVE/LOCKED) · 역할(roleCode) · 테넌트 · 부서 · 마지막 로그인 기간 · 이메일/이름 검색.

### 2.4 데이터·API·테이블
- 테이블: `bo_admin_users`(기존) + **`bo_user_tenants`**(V20 — `admin_user_id`, `tenant_id`, `workspace_id`, `data_scope`, PK `(admin_user_id, tenant_id, workspace_id)`) + `bo_user_roles`(기존, write API 신설).
- API(구현 완료, `AdminUserController`):
  - `POST /api/v1/bo/admin/users`(roleIds 추가) · `PUT /api/v1/bo/admin/users/{id}`(프로필 수정) · `POST .../{id}:reset-password` · `POST .../{id}:unlock` · `POST .../{id}:reactivate` · **`DELETE /api/v1/bo/admin/users/{id}`**(비활성 soft — `:deactivate` 액션이 아니라 DELETE 동사)
  - `PUT /api/v1/bo/admin/users/{id}/roles`(역할 set 교체=배정/회수 diff) · `GET .../{id}/tenants` · `PUT .../{id}/tenants`(테넌트 바인딩 set 교체)
- 권한: `BO_SUPER_ADMIN` 또는 신규 `BO_IAM_ADMIN` scope `bo:admin:iam`.

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
4. **데이터 기반 메뉴**(구현 완료 V23): `MenuController` 하드코딩 4항목 → **DB·역할 기반 동적 메뉴**(`bo_menu` 시드 — 콘솔/영역 노드 포함 약 41행, `bo-web` `lib/nav.ts` 운영·설정 IA와 정합. menu 가시성=사용자 역할 중 하나라도 `can_read` 보유 시 노출, `BO_SUPER_ADMIN`/scope `*` 전체). V26에서 메뉴 라벨 **'고객사 관리' → '서비스 관리'** 정합(`fds-tenants`/`aml-tenants`).
5. **scope→capability**: `@PreAuthorize` scope 게이트 유지 + scope↔화면/액션 매트릭스 정본화.

### 3.4 API·테이블
- 테이블: `bo_roles`(+scopes), **신규** `bo_role_scopes`·`bo_menu`·`bo_menu_permissions`, `bo_user_roles`(write).
- API: `POST/PUT/GET /api/v1/bo/admin/roles`(+scopes) · `PUT .../roles/{code}/scopes` · `PUT .../users/{id}/roles` · `GET /api/v1/bo/menu`(동적·역할 기반).

## 4. 결재선(결재 라인) 관리 (Approval-Line Management) — 핵심 신규

### 4.1 통합 approval_line enum (불일치 해소)
현행 FDS 6종(SELF_APPROVAL_DISABLED·MAKER_CHECKER·COMPLIANCE_MANAGER·RISK_MANAGER·SECURITY_ADMIN·EXECUTIVE_APPROVAL)과 AML 6종(MAKER_CHECKER·AML_OFFICER·COMPLIANCE_MANAGER·REPORTING_OFFICER·SECURITY_ADMIN·EXECUTIVE_APPROVAL)이 상이. → **단일 정본 enum**으로 통합(합집합 + 매핑):
`MAKER_CHECKER · AML_OFFICER · COMPLIANCE_MANAGER · RISK_MANAGER · REPORTING_OFFICER · SECURITY_ADMIN · EXECUTIVE_APPROVAL`(+ 표시 비활성 의미 `SELF_APPROVAL_DISABLED`는 라인이 아니라 **불변 정책 플래그**로 분리). 각 라인 ↔ 승인 권한 역할(scope) 매핑 테이블로 정의.

> 구현 완료(V22 `bo_approval_lines` 7종): 코드(`ApprovalLine` enum)와 정합 — 이격 없음. `required_scope` 컬럼이 라인→승인 권한 scope 매핑(예 COMPLIANCE_MANAGER→`aml:admin:approval`).

### 4.2 결재선 정의 (subject_type별 라우팅 — 부록 C 구현)
- 현행: 모든 결재가 `MAKER_CHECKER` 하드코딩 → **subject_type별 라인 라우팅**을 데이터로 정의(부록 C 정본 구현):
  - 예) RA_MODEL·TM_SCENARIO·COUNTRY_RISK·POLICY_PACK → COMPLIANCE_MANAGER · EDD_CLOSE → AML_OFFICER · STR/CTR → REPORTING_OFFICER · SECRET_CHANGE → SECURITY_ADMIN.
- **subject_type 정합**: `aml_approvals` CHECK(16) → **18**로 확장(IRA_SUBMIT·HIGH_RISK_REGISTRY 추가, Flyway).

### 4.3 기능 요구
1. **결재선 정의 관리**(BO-APRL-001): subject_type × 결재선 × 승인자 역할 매핑을 운영자가 조회·변경. 변경 시 **감사 이벤트 `APPROVAL_LINE_CHANGE` emit**(V22, ApprovalRouteService) — *4-eyes 실행 결재는 후속*, 현재는 RBAC 게이트(`BO_SUPER_ADMIN`/`bo:admin:iam`) + 감사. `PUT .../approval-routes`는 즉시 적용. 테넌트(=서비스)별 override 허용(플랫폼 기본 + 서비스별 커스터마이즈).
2. **다단계(순차) 라인**: 1차→2차→최종 등 N단계 승인 체인 정의(현 단일 maker-checker 확장). 각 단계 승인 역할·필수 여부.
3. **임계값 기반 라우팅**: 금액/위험등급/건수 임계로 라인 상향(예 고액 STR → EXECUTIVE_APPROVAL 추가 단계). PH/KR 등 Policy Pack 임계와 연계(임계 정본은 규제 레이어).
4. **위임·대결(Delegation)**(구현 완료, V24): 승인자 부재 시 대결자·기간([from_at, to_at)) 지정. 생성·회수 공통으로 **감사 이벤트 `APPROVAL_DELEGATION_CHANGED` emit**(ApprovalDelegationService). self-delegation·역전 기간은 CHECK로 거부. 유효 승인자 결의는 활성 위임의 대결자를 라인 기본 scope보다 우선.
5. **불변 정책 유지·확장**: self-approval 금지(maker≠checker)·payload_hash drift guard·staged_payload(기존 유지) + 다단계에서 각 단계 maker/checker 분리.

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

## 5. 데이터 모델 변경 요약 (신규/변경)
| 테이블 | 변경 |
|---|---|
| `bo_admin_users` | (유지). 데모 부트스트랩(V18)·데모 승인자 5명(V27) 시드 |
| `bo_user_tenants` | **V20** — user↔tenant/workspace/data-scope 영속 바인딩. PK `(admin_user_id, tenant_id, workspace_id)`. `data_scope` CHECK는 **V21 이후 `('tenant','workspace')` 2종**(V20의 `platform`은 V21에서 제거 — 바인딩 행은 정의상 tenant/workspace 스코프, platform은 바인딩 없는 플랫폼 운영자 속성). 인덱스 `idx_bo_user_tenants_tenant(tenant_id, workspace_id)`·`idx_bo_user_tenants_user(admin_user_id)` |
| `bo_role_scopes` | **V20** — (role_id FK, scope) 커스텀 역할 scope 집합. 시스템 역할은 `BackofficeRole` enum 권위 |
| `bo_user_roles` | write API 신설(스키마 유지) |
| `bo_menu`·`bo_menu_permissions` | **V23** — 4계층 RBAC·동적 메뉴(role×menu×CRUD). V26에서 메뉴 라벨 '고객사 관리'→'서비스 관리' |
| `bo_approval_lines`·`bo_approval_routes` | **V22** — 결재선 카탈로그(7종)·subject별 라우팅(다단계 step_no·임계 threshold_json) |
| `bo_approval_delegations` | **V24** — 승인자 위임(대결) |
| `bo_approval_route_members` | **V27** — (tenant_id, subject_type, step_no, user_id) 지정 승인자(복수 허용, user_id→`bo_admin_users` FK) |
| `aml_approvals.subject_type` CHECK | **16→18** 확장(IRA_SUBMIT·HIGH_RISK_REGISTRY) |
> Flyway: bo-api·aml-svc 각 신규 마이그레이션(적용분 수정 금지). 모든 변경 additive. 위 bo-api 테이블은 V18~V27로 적용 완료.

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

## 7. 정합·불일치 해소 (본 문서가 정본화)
1. `approval_line` FDS(6)/AML(6) → **단일 통합 enum 7종**(§4.1, V22 `bo_approval_lines`). FDS §16.5·AML 부록 G 동기화 필요(잔여).
2. `aml_approvals.subject_type` CHECK 16 → 18(§4.2).
3. ~~미사용 감사이벤트~~ → `ROLE_ASSIGNED`/`ROLE_REVOKED`/`PASSWORD_CHANGED`를 AdminUserService에서 **실제 emit**(확인 완료) + `ROLE_SCOPE_CHANGED`(V20)·`APPROVAL_LINE_CHANGE`(V22)·`MENU_PERMISSION_CHANGED`(V23)·`APPROVAL_DELEGATION_CHANGED`(V24) 추가.
4. ~~커스텀 역할 scope 0 결손~~ → `bo_role_scopes`로 해소(§3.1, V20).
5. ~~메뉴 하드코딩 4항목~~ → 데이터·역할 기반 동적 메뉴로 해소(§3.3-4, V23).

## 8. 우선순위 로드맵
- **P1 (사용자·역할 기본 결선) — 완료(V18·V19)**: 계정 생성 시 역할 지정(roleIds)·수정/비번리셋/잠금해제·재활성/DELETE 비활성, `bo_user_roles` write + 배정 화면, 생애주기 감사 emit. 부트스트랩 시드 정본화(V18 `iam_bootstrap_seed`).
- **P2 (테넌트 바인딩·권한 매트릭스) — 완료(V20·V21)**: `bo_user_tenants` + 헤더-위조 방지 스코프 강제(TenantContextFilter), 권한 매트릭스 화면, 커스텀 역할 scope(`bo_role_scopes`). data_scope 어휘 정합(V21).
- **P3 (결재선 관리) — 완료(V22)**: 통합 approval_line 7종·subject별 라우팅(부록 C 시드)·subject_type 18 정합. 결재선 정의 화면 bo-web `ApprovalLineRoutes`. 엔진이 bo-api 라우팅을 강제 소비하는 런타임 동기화는 후속(§4.3 비고).
- **P4a (4계층 RBAC·동적 메뉴) — 완료(V23, V26 라벨 정합)**: `bo_menu`/`bo_menu_permissions` 모델·동적 메뉴(MenuController DB 조회), bo-web `MenuPermissions`.
- **P4b (다단계/위임/임계) — 완료(V24)**: 위임(대결) `bo_approval_delegations`·유효 승인자 결의, 다단계(step_no)/임계(threshold_json)는 V22 라우팅에 내장. bo-web `ApprovalDelegations`.
- **사용자 지정 결재선 — 완료(V27)**: (tenant, subject_type, step)별 지정 승인자 `bo_approval_route_members`, bo-web `ApprovalLineMembers`. + 헤더 결재함 배지 `ApprovalInboxMenu`.
- **잔여(후속)**: 엔진 런타임의 bo-api 라우팅·지정 승인자 강제 소비, ROLE_CHANGE 4-eyes 실행 결재 워크플로, FDS §16.5·AML 부록 G 동기화.

## 9. 가정·미해결
- 본 문서는 **기능 정의(요구·화면·데이터·API)** 정본. 구현은 후속 PLAN/태스크로 분해(bo-api 헥사고날 아님 — 피처 패키지).
- 규제 임계(CTR/STR 등)는 §4.3 임계 라우팅의 입력일 뿐, 정본은 Policy Pack(01/02 PRD) 유지.
- KYE 임직원 스크리닝·조직 연계(AML-EDU-001)는 본 IAM의 조직(그룹) 모델과 연계 검토(후속).
- FDS §16.2·AML 부록 B/C/G 및 §1.6 deferral 라인에 본 문서(FS-BO-IAM-001) 포인터 추가 권고(후속 정합).
