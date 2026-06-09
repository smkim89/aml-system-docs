# T-17 Regulatory Reporting(STR/CTR/Travel Rule)·제출·재제출 [BE+BO]

- 서비스: `services/aml-svc` (+ bo) · Effort: XL · 의존: T-12, T-16, T-14 · Status: TODO

## 목표
STR 후보 생성·검토, CTR 데이터 수집·검증, 규제 보고 제출·재제출을 4-eyes 결재·tenant adapter(D-04)로 운영하고 제출 증빙을 보존한다.

## 구현 항목
- [BE] `ReviewStr/CtrUseCase` + `aml_regulatory_reports` adapter, `ReportSubmissionPort`(tenant별 adapter, D-04)
- [BE] report_type enum(STR/CTR/TRAVEL_RULE/EDD_REGISTER/WLF_REGISTER/RA_REPORT/AUDIT_EXPORT)
- [BE] report_status enum(DRAFT/UNDER_REVIEW/APPROVED/SUBMITTED/REJECTED/CANCELLED)
- [BE] STR 후보 경로: WLF true match·EDD 거래거절·TM high severity·FDS escalation·trade mismatch·crypto high-risk·internal suspicious·analyst manual
- [BE] CTR: KR policy pack effective version 기준금액 parameter
- [BE] 제출: 결재 EXECUTED → 아웃박스 `report.submission.requested`(T-16) → adapter 제출 → 콜백(acked/failed) → 재제출
- [BE] 제출 결과·제출 식별자·manifest hash 별도 evidence 저장, report=approvalId 1회 멱등
- [BO] Admin: `admin/aml/reports`, `:submit` 🔒
- [BO] STR/CTR 후보·제출 화면(bo-web)

## 참조
- `docs/design/api/02-aml-api.md` §2.7(reports), §3.6(RegulatoryReportDto/ReportSubmitRequest)
- `docs/design/db/02-aml-db.md` §3.12, §5.10(report_type), §5.11(report_status)
- `docs/design/integration/02-aml-integration.md` §9(STR/CTR/Travel Rule 제출)
- `docs/software/02-amlSvc-sass.md` §14, §22(D-04)
