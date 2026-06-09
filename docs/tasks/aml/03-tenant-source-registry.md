# T-03 고객사·source system 레지스트리·배포 모델·온보딩 [BE+BO]

- 서비스: `services/aml-svc` (+ bo-api/bo-web) · Effort: M · 의존: T-02 · Status: TODO

## 목표
SaaS 멀티테넌시의 기반인 고객사·source system 레지스트리와 **배포 모델(deployment topology)**을 구현한다. 구 `isolation_mode`(SHARED/SCHEMA/DB) 승격 방식은 폐기하고, `deployment_model`(3종: `MANAGED_DEDICATED`/`SELF_HOSTED`/`SHARED`) + `onboarding_status`(8종 상태머신)으로 재정의한다. 온보딩 신청·상태 조회 API는 **bo-api 소유**이며 aml-svc 엔진 API에는 온보딩 엔드포인트를 미추가한다. 운영자(bo) source-system 관리 화면을 노출한다.

## 구현 항목

### [BE] aml-svc 엔진
- `aml_tenants`·`aml_source_systems` CRUD usecase·persistence adapter
- **`deployment_model`** enum 3종(DB §5.28 정본): `MANAGED_DEDICATED`(기본·전용 DB·스택 IaC 자동) / `SELF_HOSTED`(고객 자체 인프라 설치형) / `SHARED`(소규모 공유·즉시)
- **`onboarding_status`** enum 8종(DB §5.28a 정본): `REQUESTED`/`PROVISIONING`/`DEPLOYED`/`VERIFIED`/`ACTIVE`/`PACKAGE_ISSUED`/`CUSTOMER_DEPLOYED`/`REGISTERED`
  - MANAGED_DEDICATED 경로: `REQUESTED→PROVISIONING→DEPLOYED→VERIFIED→ACTIVE`
  - SELF_HOSTED 경로: `REQUESTED→PACKAGE_ISSUED→CUSTOMER_DEPLOYED→REGISTERED`
  - SHARED 경로: `REQUESTED→ACTIVE`(즉시)
- **`status`** enum 3종(운영 생명주기·onboarding_status와 직교): `ACTIVE`/`SUSPENDED`/`OFFBOARDING`
- `aml_tenants` 신규 컬럼: `infra_ref VARCHAR(160)` null(매니지드=Terraform stack/workspace ID, self-hosted=라이선스·설치 인스턴스 ID), `default_region VARCHAR(32) DEFAULT 'KR'`
- **큐 물리명 규칙**(integration §2.1 정본): 전용 배포(`MANAGED_DEDICATED`/`SELF_HOSTED`) → 고객사별 전용 큐 `aml-ingest-{tenantId}-{env}`; `SHARED` → 공용 큐 `aml-ingest-{env}` + attribute `tenantId` 행 라우팅
- `app.current_tenant` 세션변수 주입: `SHARED` 배포에서만 RLS(row-level security) 행 격리 키로 동작. 전용 배포에서는 `tenantId`=배포의 고객사 단일 값·배포 엔드포인트 라우팅 레이블
- `ingest_mode` enum(REST_PUSH/QUEUE/POLLING/CDC/SNAPSHOT/VENDOR_BRIDGE) 등록
- `failure_policy`(DB §3.2 컬럼 snake_case; DTO=`failurePolicy` API §3.9; MANUAL_REVIEW/FAIL_CLOSED/DELAY_ALLOWED, D-14) source-system 속성

### [BE] 마이그레이션
- Flyway V17a(`V17a__aml_tenant_deployment_model.sql`): `deployment_model` 추가 + 데이터 백필(기존 `SHARED`→`SHARED`/`ACTIVE`, `SCHEMA`/`DB`→`MANAGED_DEDICATED`/`ACTIVE`) + `default_region 'KR'` 정규화
- Flyway V17b(`V17b__aml_tenant_drop_isolation_mode.sql`): V17a 검증 완료 후 `isolation_mode` 컬럼 DROP

### [BO] bo-api 고객사·온보딩 API (bo-api 소유, aml-svc 엔진 미추가)
- `GET/POST /api/v1/bo/aml/tenants` — 고객사 목록(deploymentModel/onboardingStatus/status 필터) + 고객사 등록(`TenantCreateRequest`: deploymentModel 선택 + 온보딩 신청, 201, onboarding_status=REQUESTED 초기화)
- `GET/PUT /api/v1/bo/aml/tenants/{tenantId}` — 고객사 상세(`TenantDto`) + 설정 변경(displayName/status/policyPackCode, deploymentModel 불변→409 `AML.TENANT_DEPLOYMENT_MODEL_IMMUTABLE`)
- **온보딩 프로비저닝 API는 P8-BOAPI-01로 위임** (`/onboarding/provision`·`/onboarding/register`·`GET /onboarding`)
- Admin: `POST /api/v1/admin/aml/source-systems` 🔒(secret 변경=결재), `secret_ref`만 저장

### [BO] Admin Policy Pack 변경
- `POST /api/v1/admin/aml/policy-packs:change` 🔒4-eyes(`subjectType=POLICY_PACK`, §2.7·§10). 요청 DTO §3.13 `PolicyPackChangeRequest`(`policyPackCode`·`parameters`{STR/CTR/Travel Rule 기준금액·effective version}·`reason`·`makerId`). 실행(EXECUTED) 시 `aml_tenants.policy_pack_code` effective version 갱신. 기준금액은 법령·감독규정 변경 가능성으로 effective version 관리(설계서 §14.3·§19.1)
- policy pack 변경 결재 상태머신·payload_hash·실행분리는 **T-12 결재 엔진**(`subjectType=POLICY_PACK`) 처리. 본 태스크는 `aml_tenants.policy_pack_code` 상신 진입점·실행 후 effective version 반영만 소유. 변경된 기준금액은 reporting(T-17)이 effective version으로 소비

### [BO] 화면 (bo-web→bo-api)
- 고객사 관리 목록·상세: `deployment_model`(읽기 전용) + `onboarding_status`(읽기 전용) 표시. '격리 방식' 라디오 폐기
- 고객사 등록: `deployment_model` 선택(매니지드 전용/자체 인프라 설치형/[소규모 공유]) + 온보딩 신청. 화면 명칭: '고객사 등록(배포 유형+온보딩 신청)'
- source-system 목록·등록·상태 화면, tenant policy pack 변경 화면
- 온보딩 상태 화면(P8 위임, T-22 참조)

## 참조
- `docs/design/db/02-aml-db.md` §3.1(aml_tenants DDL·V17a/V17b), §3.2(aml_source_systems), §5.14(ingest_mode), §5.28(deployment_model), §5.28a(onboarding_status), §5.28b(status 운영)
- `docs/design/api/02-aml-api.md` §1.1(Tenant 라우팅 재정의), §3.16(TenantDto·TenantCreateRequest·TenantUpdateRequest·DTO 신설), §4(에러코드 AML.TENANT_DEPLOYMENT_MODEL_IMMUTABLE 등), §5(OpenAPI DeploymentModel/OnboardingStatus schema), §6(BO 화면 정합), §9(bo-api 소유 경계)
- `docs/design/api/02-aml-api.md` §2.7(Admin: source-systems·`policy-packs:change`🔒), §3.13(`PolicyPackChangeRequest`), §10(4-eyes 트리거: `POLICY_PACK`)
- `docs/design/integration/02-aml-integration.md` §2.1(큐 물리명 규칙 deployment_model 기준), §10.1(tenantId 라우팅 의미 재정의), §10.3(온보딩 프로비저닝 연동 흐름)
- `docs/software/02-amlSvc-sass.md` §16(배포 모델·온보딩 프로비저닝·배포 내부 분리키), §15(연동 모드)
- `.claude/skills/_shared/target-architecture.md` §4.1(배포 모델 3종·온보딩 상태머신)
