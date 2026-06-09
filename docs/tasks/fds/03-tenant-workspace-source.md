# T-03 고객사·workspace·source system 레지스트리·배포/온보딩 [BE+BO]

- 서비스: `services/fds-svc` + `bo-api` · Effort: M · 의존: T-02 · Status: TODO

## 목표
배포 모델(deployment topology) + 배포 내부 분리 키(tenant/workspace/data-scope)의 레지스트리와 강제 필터를 구현한다. 고객사별 전용 배포가 기본(공유 DB 아님)이며, "격리"는 화면 토글이 아니라 **배포 모델 선택 + 온보딩 프로비저닝의 산출**이다(D-01). source system·connector 설정·fail policy(D-14)를 관리한다.

## 구현 항목
- [ ] `fds_tenants`·`fds_workspaces`·`fds_source_systems` CRUD (tenant_status·**deployment_model**·**onboarding_status**·**default_region**·**infra_ref**·ingest_mode·schema_version·fail_policy)
- [ ] **[BO]** Admin API: `GET/POST /api/v1/admin/fds/source-systems`, `PUT .../{sourceSystem}/mappings`(🔒 MAPPING 결재)
- [ ] **[BO]** source system 속성·capability 매트릭스 수정: `PUT /api/v1/admin/fds/source-systems/{id}`(`displayName`/`enabled`/`schemaVersion`/`ingestMode`/`failPolicy`/`capabilities`). `capabilities`=`control_capability` 9종(DB §4.6) 부분집합 — action router 발행 게이트. 🔒 4-eyes `subjectKind=MAPPING`(subjectRef=`source_system`) → 즉시 미반영, `fds_approval_requests` 상신 후 승인 relay(`FDS-APPROVAL-REQUIRED` 409)
- [ ] **[BE]** tenant context 강제: 모든 `fds_*` 조회/쓰기에 `(tenant_id, workspace_id)` 필터 주입(누락 시 차단)
- [ ] **[BE]** `data_scope` 권한 필터: bo-api 위임 토큰 claim의 `dataScope` 집합을 fds-svc 조회 IN 필터로 주입. scope 밖 row → `FDS-DATASCOPE-DENIED`(403)
- [ ] `sandbox` workspace shadow-only 규칙(`is_sandbox`, outbound 미발행)
- [ ] cross-workspace 접근 차단(`FDS-AUTHZ-003`)
- [ ] **[BO]** 배포 유형 선택 + 온보딩 신청/상태: `deployment_model`(`MANAGED_DEDICATED`/`SELF_HOSTED`/`SHARED`) 선택, **`isolation_mode` 토글 제거**. 온보딩 상태머신(`onboarding_status` 8종) 추적·읽기 표시 — 상세 프로비저닝 파이프라인은 P8 SaaS 제품화(T-22)로 위임
- [ ] **[BE]** 전용 배포 기준 tenantId 의미: 전용 배포(`MANAGED_DEDICATED`/`SELF_HOSTED`)는 배포=고객사 단일 `tenant_id`, 고객사 간 격리는 배포 경계가 보장(행 필터 비의존). `SHARED`만 `tenant_id` 행 격리

## 참조
- `docs/software/01-fdsSvc-sass.md` §13.0(배포 모델), §13.0a(온보딩 프로비저닝), §13.0b(키 의미 재정의), §13.1(배포 내 데이터 분리), §11.6.11(`deployment_model`), §11.6.11a(`onboarding_status`)
- `docs/design/db/01-fds-db.md` v1.3 §2.1(배포 모델), §2.2(키 의미), §4.1/§4.1a(`deployment_model`/`onboarding_status` enum·상태머신), §5.1~5.3(`fds_tenants.deployment_model`/`onboarding_status`/`infra_ref`), §8(Flyway V17), §9(고객사 관리=bo-api 소유 경계)
- `docs/design/api/01-fds-api.md` v1.5 §2.2(헤더), §2.3(scope), §4.8(source admin·`PUT /source-systems/{id}`), §5.17(SourceSystemUpdateRequest·capability 매트릭스), §8(4-eyes `MAPPING`), §10(`DeploymentModel`/`OnboardingStatus` enum·`TenantDto`), §11.2(bo-api 소유 경계·온보딩 엔드포인트)
- 온보딩 프로비저닝 파이프라인(IaC/설치형 패키징)·상태머신 구현: T-22 SaaS 제품화 참조

## 변경 이력
| 일자 | 변경 |
|---|---|
| 2026-06-08 | **격리(isolation_mode) → 배포 모델(deployment topology) 재설계** 반영(설계서 v1.5 §13/§11.6.11/§11.6.11a, DB v1.3 §2.1/§5.1/§9, API v1.5 §10/§11.2, integration v1.5, target-architecture §4.1). 제목·목표·구현 항목을 배포/온보딩으로 재정의: `isolation_mode` 토글 제거 → `deployment_model`(3종)·`onboarding_status`(8종)·`infra_ref` CRUD, 배포 유형 선택+온보딩 신청/상태 표시, 전용 배포 tenantId 의미(배포=고객사 단일·격리=배포 경계, `SHARED`만 행 격리). 상세 프로비저닝 파이프라인은 T-22 위임. 참조 핀 DB v1.3·API v1.5 갱신. 프로그램 로드맵 P1-FDS-02·P3-BOAPI-02·P5-FDS-02와 정합. |
