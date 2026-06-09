# T-02 DB 마이그레이션(Flyway V1~V17)·배포 모델·시드 [BE]

- 서비스: `services/fds-svc` · Effort: L · 의존: T-01 · Status: TODO

## 목표
스키마 `fds`의 물리 데이터 모델(33개 `fds_*` 테이블)을 Flyway additive migration V1~V17로 구축한다. 배포 모델(deployment topology) 기반 멀티테넌시(전용 배포 기본), 배포 내부 분리 키(`tenant_id`/`workspace_id`/`data_scope`), `NUMERIC(24,8)` 금액, append-only 감사, enum CHECK, 인덱스를 확정한다. 격리는 화면 토글이 아니라 **배포 모델 선택 + 온보딩 프로비저닝의 산출**이다(D-01).

## 구현 항목
- [ ] `V1__fds_schema.sql` ~ `V16__indexes.sql` 작성(DB §8 순서·FK 의존 고정). 스키마 `fds`, prefix `fds_`
- [ ] 전 운영 테이블 PK = `(tenant_id, workspace_id, <natural key>)`, `workspace_id VARCHAR(64) NOT NULL DEFAULT 'default'`
- [ ] enum VARCHAR + CHECK (또는 앱 enum): decision(8)·action_type(23)·case_type(11)·instrument(12)·channel(19)·payment_rail(18)·capability(9)·approval_line(6)·approval_status(8)·action_status(7) 등 §4 전체
- [ ] 금액 `NUMERIC(24,8)`, `amount`/`amount_base`·`currency`/`base_currency` 분리
- [ ] append-only 테이블(`fds_decisions`/`fds_decision_reasons`/`fds_case_events`/`fds_rule_versions`/`fds_audit_logs`/`fds_external_decisions`) UPDATE/DELETE 금지(트리거/권한)
- [ ] §6 인덱스 일괄(`V16`), 대용량 테이블(`fds_canonical_events`/`fds_decisions`/`fds_audit_logs`) 월 RANGE partition 옵션
- [ ] `fds_cases.aml_case_id VARCHAR(96) NULL` cross-ref 컬럼 + 역조회 인덱스 `ix_case_aml_ref` 포함(DB §5.13 정본 확정·integration §9.1 동일 타입, FK 아님)
- [ ] 배포 모델 컬럼(`fds_tenants`): `deployment_model VARCHAR(32) NOT NULL DEFAULT 'MANAGED_DEDICATED'`(`MANAGED_DEDICATED`/`SELF_HOSTED`/`SHARED`)·`onboarding_status VARCHAR(32) NOT NULL DEFAULT 'REQUESTED'`(8종)·`default_region VARCHAR(32) NOT NULL DEFAULT 'KR'`·`infra_ref VARCHAR(160) NULL`. 본 DDL은 전용 배포(`MANAGED_DEDICATED`) 기준, `SHARED`만 행 격리
- [ ] **`V17` 마이그레이션(additive-then-drop 2단)**: `isolation_mode` 컬럼 DROP → `deployment_model`/`onboarding_status`/`infra_ref` 추가·백필(`SHARED→SHARED`, `SCHEMA/DB→MANAGED_DEDICATED`). 구 `isolation_mode` enum(SHARED/SCHEMA/DB) 폐기
- [ ] 로컬 시드(샘플 tenant/workspace/source_system/feature_catalog)

## 참조
- `docs/design/db/01-fds-db.md` §2.1(배포 모델 3종), §2.2(키 의미 재정의), §4.1(`deployment_model`/`onboarding_status` enum), §4.1a(온보딩 상태머신), §5.1(`fds_tenants` DDL), §6(인덱스), §8(Flyway V17 순서)
- `docs/software/01-fdsSvc-sass.md` §14.1 DDL, §13.0(배포 모델), §13.0b(키 의미), §11.6.11(`deployment_model`)/§11.6.11a(`onboarding_status`)
- 상세 프로비저닝 파이프라인(IaC/설치형)·온보딩 상태머신 구현: T-22 SaaS 제품화 참조

## 변경 이력
| 일자 | 변경 |
|---|---|
| 2026-06-08 | **격리(isolation_mode) → 배포 모델(deployment topology) 재설계** 반영(DB v1.3 §5.1/§8, 설계서 v1.5 §14.1, target-architecture §4.1). 제목 'Flyway V1~V16·격리'→'V1~V17·배포 모델'. `fds_tenants` 배포 컬럼(`deployment_model` DEFAULT `MANAGED_DEDICATED`·`onboarding_status` DEFAULT `REQUESTED`·`default_region`·`infra_ref`) 항목 추가, `V17` 마이그레이션(additive-then-drop: `isolation_mode` DROP→신규 추가·백필 `SHARED→SHARED`·`SCHEMA/DB→MANAGED_DEDICATED`) 추가, 구 `isolation_mode` 토글 항목 폐기. 참조 §2.1/§4.1/§5.1/§8 갱신. 프로그램 로드맵 P1-FDS-01과 정합. |
