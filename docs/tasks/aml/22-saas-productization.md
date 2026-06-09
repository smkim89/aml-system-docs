# T-22 SaaS productization — 배포/온보딩 프로비저닝·SDK·sandbox [BE+BO]

- 서비스: `services/aml-svc` (+ bo) · Effort: XL · 의존: T-06, T-07, T-17, T-20 · Status: TODO
- Due(Phase): **P8** — 설계서 §21 **Phase 9(SaaS productization)** 대응. Phase=WBS 착수 우선순위(설계 Phase와 1:1 아님, overview §4 참조).

## 목표
멀티고객사 AML 플랫폼을 외부 고객사가 self-service로 **배포 유형 선택 + 온보딩 프로비저닝(IaC 자동/설치형 패키징)** 후 연동·검증·과금할 수 있도록 상품화한다. 구 `isolation_mode`(SHARED/SCHEMA/DB) 방식은 **D-06 결정 확정으로 폐기**. `deployment_model`(MANAGED_DEDICATED/SELF_HOSTED/SHARED) + `onboarding_status` 8종 상태머신 + **온보딩 프로비저닝 3경로**가 핵심. 코어(ingest·screening·RA·TM·reporting·관측성)가 안정화된 뒤 착수한다.

## 구현 항목

### [BE] 온보딩 프로비저닝 파이프라인 (T-03 `deployment_model` 레지스트리 위에 구현)
- MANAGED_DEDICATED 경로 — IaC(Terraform) 파이프라인 자동 프로비저닝: 전용 DB·스택 생성 → 시크릿/DNS 구성 → 배포 → 검증(`REQUESTED→PROVISIONING→DEPLOYED→VERIFIED→ACTIVE`). `infra_ref`=Terraform stack/workspace ID 저장
- SELF_HOSTED 경로 — 설치형 패키지(Helm chart / Docker compose) 생성 + 라이선스 발급(`REQUESTED→PACKAGE_ISSUED`), 고객 측 배포(`CUSTOMER_DEPLOYED`), 등록 콜백(`REGISTERED`). `infra_ref`=라이선스·설치 인스턴스 ID. 등록 콜백 인증: `registrationToken`(상세 인증방식=오픈결정, API §3.16 등재)
- SHARED 경로 — 즉시 활성(`REQUESTED→ACTIVE`). 추가 인프라 프로비저닝 불필요
- **큐 프로비저닝 자동화**: 전용 배포 온보딩 완료 시 전용 큐 `aml-ingest-{tenantId}-{env}` 자동 생성(IaC 포함). `SHARED`는 공용 큐 `aml-ingest-{env}` 재사용

### [BE] 온보딩 상태머신·`onboarding_status` 라이프사이클 관리
- `onboarding_status` 8종(DB §5.28a) 상태전이 검증 + 위반 시 `409 AML.ONBOARDING_INVALID_STATE_TRANSITION`
- `deployment_model` 불변 원칙: 온보딩 완료 후 변경 불가. PUT 시도 시 `409 AML.TENANT_DEPLOYMENT_MODEL_IMMUTABLE`
- 상태 이력은 `aml_tenants`(DB) + bo-api `GET /api/v1/bo/aml/tenants/{tenantId}/onboarding`으로만 노출(큐/이벤트에 온보딩 상태 변화 별도 미발행)

### [BE] connector SDK·개발자 지원
- connector SDK: source system 연동 클라이언트 라이브러리(ingest envelope·idempotencyKey·traceparent·camelCase 규약, integration §4)
- OpenAPI spec 산출(Public/Internal/Admin 3-plane) + developer portal 게시(API §0 plane 경계 준수)

### [BE] sandbox·conformance·metering·regional
- sandbox tenant: 격리된 시험 data-scope·합성 데이터·conformance test kit(ingest→screen→RA→TM→report end-to-end 검증, shadow-only 외부 미발행)
- tenant billing/usage metering: 이벤트·screening·report 건수 집계(저수준 usage 데이터 API). **운영자 집계/대시보드는 bo-api 소유**(엔진은 저수준 데이터만 제공)
- Korean region production hardening: 전용 배포 기본(`MANAGED_DEDICATED`), 백업·키 회전·부하/장애 격리

### [BE] evidence pack
- 고객사 단위 규제 evidence 번들(T-17·T-19 evidence export 재사용)

### [BO] 운영 화면 (bo-web→bo-api, P8-WEB-01 담당)
- 온보딩 프로비저닝 콘솔: 배포 유형 선택(매니지드 전용/자체 인프라 설치형/[소규모 공유]) + 온보딩 신청 마법사. 화면 명칭: '고객사 등록(배포 유형+온보딩 신청)'
- 온보딩 상태: `onboarding_status` 상태머신 시각화·`infra_ref`·이력 표시 (읽기 전용). 화면 명칭: '온보딩 상태'
- developer portal 운영·usage/billing 대시보드. **모든 집계·집약은 bo-api 소유**(엔진 API에 집계 엔드포인트 미추가)

## 구분
- [BE]: IaC 프로비저닝 파이프라인·설치형 패키지 생성·connector SDK·sandbox·conformance kit·usage metering 백엔드·region hardening (화면 비대상)
- [BO]: 온보딩 프로비저닝 콘솔·온보딩 상태·developer portal 운영·usage/billing 대시보드 (backoffice-planner 화면 대상, bo-api 경유)

## 참조
- `docs/software/02-amlSvc-sass.md` §16.0~§16.0d(배포 모델·온보딩 상태머신·프로비저닝 경로), §16.1(배포 내 데이터 분리), §17.1(aml_tenants DDL V17), §21 Phase 9(SaaS productization), §22(D-06 결정 확정)
- `docs/design/db/02-aml-db.md` §3.1(aml_tenants V17a/V17b), §5.28(deployment_model), §5.28a(onboarding_status), §5.28b(status)
- `docs/design/api/02-aml-api.md` §3.16(DTO 전수: TenantDto·OnboardingProvisionRequest·OnboardingRegisterRequest·OnboardingStatusResponse), §4(에러코드 6종), §5(OpenAPI schema), §6(BO 화면), §9(bo-api 소유 경계)
- `docs/design/integration/02-aml-integration.md` §2.1(큐 물리명 deployment_model 기준), §10.1(tenantId 라우팅 의미), §10.3(온보딩 프로비저닝 연동 흐름 3경로 시퀀스)
- `.claude/skills/_shared/target-architecture.md` §4.1(배포 모델 3종·온보딩 상태머신·한 고객사=한 배포 원칙)
