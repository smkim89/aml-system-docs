# T-13 CDD/EDD workflow·case 관리·periodic review·SLA [BE+BO]

- 서비스: `services/aml-svc` (+ bo) · Effort: XL · 의존: T-09, T-11, T-12 · Status: TODO

## 목표
CDD/EDD checklist·case 관리·periodic review·SLA를 구현하고, alert triage→investigation→escalation을 4-eyes 종결과 함께 운영한다.

## 구현 항목
- [BE] `ManageCaseUseCase` + `aml_cases` adapter, case_type enum(SANCTIONS_REVIEW/PEP_REVIEW/EDD_REVIEW/STR_REVIEW/CTR_REVIEW/TBML_REVIEW/VASP_TRAVEL_RULE_REVIEW/MERCHANT_AML_REVIEW/INTERNAL_CONTROL_REVIEW/MULE_ACCOUNT_REVIEW/B2B_INVOICE_REVIEW/ECOMMERCE_SETTLEMENT_REVIEW)
- [BE] case_status enum(OPEN/INVESTIGATING/PENDING_APPROVAL/DISMISSED/REPORTED/CLOSED), 상태 전이 검증 → `AML.INVALID_STATE_TRANSITION`
- [BE] EDD trigger: WLF true match·high RA·high-risk country·unusual transaction·complex ownership·trade mismatch·crypto risk·internal override
- [BE] CDD checklist·periodic review 스케줄러(`adapter/in/scheduled`, `nextReviewDueAt`). 재확인 주기는 `periodic-review-policy`의 등급별 cadence(`cadenceByGrade`)+`gracePeriodDays`를 입력으로 산정
- [BE] SLA 계산·`aml.case.sla.breached` metric
- [BO] Admin: `admin/aml/cdd/cases`(GET/POST/PATCH), `/timeline`, `:close` 🔒, `:reject-relationship` 🔒
- [BO] **CDD/EDD checklist 정책 관리**: `GET /admin/aml/cdd/checklists`(항목·필수여부·증빙요건 목록), `POST /admin/aml/cdd/checklists`(신규 DRAFT, 결재 불필요), `PUT /admin/aml/cdd/checklists/{id}` 🔒4-eyes(checklist 변경 적용, §13.4 'CDD checklist 변경'). 요청 DTO §3.11 `CddChecklistDto`/`ChecklistChangeRequest`(`items[]`·`reason`·`makerId`, checklist 정책 변경 결재로 상신). checklist 정책은 **정책 store**(versioned artifact)로 별도 물리 마스터 테이블 미보유
- [BO] **periodic review 주기 정책 설정**: `PUT /admin/aml/cdd/periodic-review-policy` 🔒4-eyes(등급별 재확인 주기 변경). 요청 DTO §3.11 `PeriodicReviewPolicyRequest`(`cadenceByGrade`{LOW/MEDIUM/HIGH/PROHIBITED 개월}·`gracePeriodDays`·`reason`·`makerId`). 응답=결재 상신 `{ approvalId, status: SUBMITTED }`
- [BE] checklist 변경·periodic review 정책 변경의 결재 상태머신·payload_hash·실행분리는 **T-12 결재 엔진**(API §10 등재)으로 처리. 본 태스크는 정책 store 조회/상신 진입점·실행 후 스케줄러 반영만 소유
- [BO] case SLA·CDD/EDD 처리 화면, case timeline, checklist 정책·periodic review 주기 설정 화면
- [BE] case 변경 audit evidence 기록(T-19)

## 참조
- `docs/design/api/02-aml-api.md` §2.7(cdd/cases·cdd/checklists·`cdd/checklists/{id}`🔒·`periodic-review-policy`🔒), §3.5(CaseDto/CaseCloseRequest/CaseTimelineEntryRequest), §3.11(CddChecklistDto/ChecklistChangeRequest/PeriodicReviewPolicyRequest), §10(4-eyes 트리거: checklist·periodic review 정책 변경)
- `docs/design/db/02-aml-db.md` §3.11, §5.8(case_type), §5.9(case_status)
- `docs/software/02-amlSvc-sass.md` §13
