# T-19 Audit evidence hash chain·evidence export(manifest) [BE+BO]

- 서비스: `services/aml-svc` (+ bo) · Effort: L · 의존: T-12, T-13 · Status: TODO

## 목표
append-only audit hash chain과 FIU·금융감독원·내부감사 제출용 evidence export(UI+API+manifest hash, D-11)를 구현한다.

## 구현 항목
- [BE] `AuditEvidencePort` + `aml_audit_events`(append-only, hash chain), 전 경계 진입/이탈 traceId 기록
- [BE] `aml:pii:reveal` 원문 접근 시 RAW_DATA_ACCESS audit
- [BE] `BuildEvidencePackUseCase` + `aml_evidence_exports` adapter
- [BE] Public/Evidence: `GET /api/v1/evidence/aml/customers/{customerRef}/profile`, `cases/{caseId}/timeline`, `reports/str-candidates`, `POST /api/v1/evidence/aml/exports`, `GET .../exports/{exportId}`
- [BE] export: 생성자·사유·기간·filter·row count·`manifest_hash`·`evidence_hash`, 재생성 가능한 query snapshot 보존, CSV/Excel/PDF(각 row에 evidence id·case id)
- [BO] Admin: `admin/aml/audit-events`
- [BO] audit export 화면(bo-web)

## 참조
- `docs/design/api/02-aml-api.md` §2.5(Evidence), §3.8(EvidenceExportRequest/Response), §2.7(audit-events)
- `docs/design/db/02-aml-db.md` §3.15(`aml_audit_events`, `aml_evidence_exports`)
- `docs/software/02-amlSvc-sass.md` §15.6, §19, §20.3
