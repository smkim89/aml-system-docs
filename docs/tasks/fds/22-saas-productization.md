# T-22 SaaS productization(배포/온보딩 프로비저닝·connector SDK·developer portal·sandbox·conformance·metering·regional) [BE+BO]

- 서비스: `services/fds-svc` + `bo-api` + 인프라(IaC) · Effort: XL · 의존: T-03, T-06, T-19, T-20 · Status: TODO

## 목표
설계서 §18 Phase 8(SaaS productization) 산출물을 제품화한다. **배포/온보딩 프로비저닝**(IaC 파이프라인·self-hosted 설치형 패키징·온보딩 상태머신), connector SDK·OpenAPI/developer portal, sandbox tenant·conformance test kit, billing/usage metering, regional deployment, compliance evidence pack을 구현한다. 고객사별 전용 배포가 기본(공유 DB 아님)이며, 격리는 배포 모델 + 온보딩 프로비저닝의 산출이다. 운영자 집계·고객사 관리 화면은 **bo-api 소유**이며, fds-svc는 저수준 데이터·metering API만 제공한다.

## 구현 항목
- [ ] **[BO+IaC]** **배포/온보딩 프로비저닝 파이프라인**: 배포 유형 선택(`deployment_model` 3종) + 온보딩 신청 워크플로. 매니지드 전용은 **IaC(Terraform) 자동 프로비저닝**(`REQUESTED→PROVISIONING→DEPLOYED→VERIFIED→ACTIVE`: 전용 DB·스택·시크릿·DNS 생성·헬스체크), self-hosted는 **설치형 패키지(Helm/Docker/installer)·가이드·라이선스 발급 + 등록 콜백**(`PACKAGE_ISSUED→CUSTOMER_DEPLOYED→REGISTERED`), `SHARED`는 즉시 활성. `onboarding_status` 8종 상태머신·`infra_ref` 기록
- [ ] **[BO]** 온보딩 API: `POST /api/v1/bo/fds/tenants/{tenantId}/onboarding/provision`(IaC 트리거)·`GET .../onboarding`(상태 읽기)·`POST .../onboarding/register`(self-hosted 등록 콜백). 등록·설정변경은 **bo-api 소유**(운영자 IAM·감사), **`isolation_mode` 토글 제거** — fds-svc는 저수준 tenant 데이터 API만 제공
- [ ] **[BE]** connector SDK(Java + OpenAPI sample, D-07). public ingest/decision/action 계약을 SDK·sample payload로 패키징
- [ ] **[BE]** OpenAPI spec 자동 발행 + developer portal(엔드포인트·DTO·error 모델·scope 문서). API §10 OpenAPI(YAML) 스니펫 정본 기준
- [ ] **[BE]** sandbox tenant·`sandbox` workspace conformance test kit(shadow-only 검증, outbound 큐 미발행 D-13.0 규칙 자동 검사)
- [ ] **[BE]** billing/usage metering: API 호출량·monitored event·decision·evidence export 수를 과금 단위로 집계(저수준 metering 데이터 API 제공, 집약·과금 화면은 bo-api)
- [ ] **[BE/IaC]** regional deployment(데이터 거주성·`default_region`별 전용 배포 프로비저닝, D-01 `MANAGED_DEDICATED` 연계)
- [ ] **[BO]** compliance evidence pack 제품화(T-19 evidence export 연계, 검사대응 표준 산출물 템플릿)
- [ ] 운영자 집계 API 경계: 대시보드/고객사 관리/감사 조회 엔드포인트는 **API 명세(엔진)에 추가하지 않는다**. PRD/PPT 해당 화면은 호출 대상을 bo-api로 명시(fds-svc는 저수준 데이터 API만)

## 참조
- `docs/software/01-fdsSvc-sass.md` §18 Phase 8(SaaS productization), §17.5(metering), §13.0(배포 모델), §13.0a(온보딩 프로비저닝 IaC/설치형), §13.0b(sandbox shadow), §11.6.11(`deployment_model`)/§11.6.11a(`onboarding_status`), §12.8(온보딩 API), §19 D-01/D-07
- `docs/design/api/01-fds-api.md` §10(OpenAPI YAML 스니펫), §11(bo-api 소유 경계), §2.3(scope)
- `docs/design/db/01-fds-db.md` §9(운영자 집계 API 소유 경계: 대시보드/고객사/감사=bo-api), §5(tenant/workspace/source)
- `.claude/skills/_shared/target-architecture.md` §4.1(배포 모델·고객사별 전용 배포 기본·온보딩 상태머신)

## 변경 이력
| 일자 | 변경 |
|---|---|
| 2026-06-08 | **격리(isolation_mode) → 배포 모델(deployment topology) 재설계** 반영(설계서 v1.5 §13.0/§13.0a/§12.8, DB v1.3, API v1.5 §11.2, integration v1.5 §10.2, target-architecture §4.1). 제목·목표를 '배포/온보딩 프로비저닝'으로 재정의(서비스에 IaC 추가). 'tenant onboarding'→배포/온보딩 프로비저닝 파이프라인: 매니지드 전용 IaC(Terraform) 자동 프로비저닝(`REQUESTED→PROVISIONING→DEPLOYED→VERIFIED→ACTIVE`)·self-hosted 설치형 패키지(Helm/Docker)+등록 콜백(`PACKAGE_ISSUED→CUSTOMER_DEPLOYED→REGISTERED`)·`SHARED` 즉시. bo-api 온보딩 API(`/onboarding/provision`·`GET /onboarding`·`/onboarding/register`, `isolation_mode` 토글 제거) 추가. `onboarding_status` 8종 상태머신·`infra_ref` 기록. 프로그램 로드맵 P8-FDS-01·P8-BOAPI-01·P8-WEB-01·P8-INFRA-04와 정합. 오픈결정: self-hosted 라이선스 발급·검증 방식, 매니지드 IaC 도구(Terraform Cloud/Atlantis/자체 러너), `SHARED` 제공 여부는 P8 인프라 설계·영업 정책에서 확정. |
