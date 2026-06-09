# T-02 DB 마이그레이션(Flyway V01~V16 코어; V17a/V17b deployment_model 연동)·RLS·시드 [BE]

- 서비스: `services/aml-svc` · Effort: L · 의존: T-01 · Status: TODO

## 목표
`aml` 전용 스키마 물리 모델(도메인 14종 + 지원 인프라 5종)을 Flyway **V01~V16**(코어 전체)으로 구축하고, 멀티테넌시 RLS·append-only audit hash chain·4-eyes CHECK 제약을 강제한다. **V17a**(isolation_mode 컬럼 제거·deployment_model/onboarding_status/status/infra_ref/default_region 추가)·**V17b**(큐 물리명 규칙 컬럼)는 T-03(배포 모델 결정 D-06 확정) 구현과 연동하여 동일 PR 범위로 포함한다(DB §7 Flyway 순서 기준, 00-overview §7 D-06 참조).

## 구현 항목
- [ ] `services/aml-svc/src/main/resources/db/migration/` V01~V16 (순서·의존 DB §7)
- [ ] 도메인 14종: `aml_tenants`, `aml_source_systems`, `aml_customers`, `aml_entities`, `aml_relationships`, `aml_watchlist_sources`, `aml_watchlist_entries`, `aml_screening_results`, `aml_risk_scores`, `aml_alerts`, `aml_cases`, `aml_regulatory_reports`, `aml_business_documents`, `aml_travel_rule_transfers`
- [ ] 지원 인프라 5종: `aml_canonical_events`, `aml_approvals`, `aml_audit_events`, `aml_evidence_exports`, **`aml_outbox`**(V16, §3.15)
- [ ] V16 `aml_outbox`: status enum(§5.17 PENDING/DISPATCHING/DISPATCHED/FAILED)·발행 멱등 UNIQUE(`ux_outbox_idem`)·`ix_outbox_dispatch`·RLS (T-16 선행, 이전 ⚠ 해소)
- [ ] enum 정본 동기화: `aml_approvals.subject_type`에 `TM_SCENARIO` 포함(§5.16, **API `ApprovalDto.subjectType` enum 전수가 정본**), `risk_status` 4종(§5.15), `aml_alerts.external_alert_ref`·`aml_travel_rule_transfers.amount_minor`
- [ ] PK 규약: 전 테이블 `(tenant_id, <id>)` composite, tenant_id 선두
- [ ] 공통 컬럼(운영 테이블): `tenant_id, data_scope, created_at, created_by, updated_at, updated_by, trace_id`
- [ ] RLS 정책: `app.current_tenant` 세션변수 기반 row 격리 + `data_scope`
- [ ] 4-eyes: `aml_approvals` CHECK `maker_id <> checker_id`, `payload_hash` 고정 컬럼
- [ ] audit: `aml_audit_events` append-only hash chain
- [ ] 인덱스(DB §4): WLF GIN(`normalized_tokens`) fallback(D-02), 멱등 UNIQUE`(tenant_id, idempotency_key)`
- [ ] 보존: `retention_class` 5종, `aml_tenants.retention_policy` JSONB override
- [ ] V15 seed: `KR_DEFAULT` policy pack
- [ ] 금액: `NUMERIC(24,8)` + `amount_minor BIGINT` 병행(`aml_travel_rule_transfers` 포함)

## 참조
- `docs/design/db/02-aml-db.md` §3(테이블), §4(인덱스), §5(enum), §6(보존), §7(Flyway 순서; V17a/V17b)
- `docs/software/02-amlSvc-sass.md` §7·§17·§19.2

## 변경 이력
| 일자 | 변경 |
|---|---|
| 2026-06-08 | #52 제목·목표에 V17a(deployment_model 전환)·V17b(큐 물리명 규칙) 범위 경계 명시(DB §7·00-overview §7 D-06 정합). |
