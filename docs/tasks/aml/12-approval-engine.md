# T-12 4-eyes 결재 엔진(approval·payload_hash·실행 분리) [BE+BO]

- 서비스: `services/aml-svc` (+ bo) · Effort: L · 의존: T-02, T-06 · Status: TODO

## 목표
WLF·RA·TM·CDD/EDD·STR/CTR·Travel Rule·명단·보안 설정에 공통 적용되는 maker-checker 결재 엔진을 구현한다(case workflow와 분리된 통제 계층).

## 구현 항목
- [BE] `RunApprovalUseCase` + `aml_approvals` adapter, `approval_line` enum(MAKER_CHECKER/AML_OFFICER/COMPLIANCE_MANAGER/REPORTING_OFFICER/SECURITY_ADMIN/EXECUTIVE_APPROVAL)
- [BE] 상태머신 `approval_status`: DRAFT→SUBMITTED→APPROVED/REJECTED/CANCELLED/EXPIRED→EXECUTED/EXECUTION_FAILED
- [BE] 4-eyes 강제: `maker_id <> checker_id`(DB CHECK), self-approval 차단 → `AML.SELF_APPROVAL_FORBIDDEN`
- [BE] `payload_hash` 고정: 승인 후 payload 변경 시 무효화 → `AML.APPROVAL_PAYLOAD_CHANGED`
- [BE] 결재≠실행 분리: `executed_at`, 만료시간·승인범위·실행 가능 횟수
- [BE] `subject_type` enum 정본=**API `ApprovalDto.subjectType`(전수 **16종**, §3.7)**: `WLF_DECISION`/`FP_WHITELIST`/`RA_MODEL`/`TM_SCENARIO`/`RISK_OVERRIDE`/`EDD_CLOSE`/`STR_SUBMIT`/`CTR_SUBMIT`/`TRAVEL_RULE_EXCEPTION`/`WATCHLIST_IMPORT`/`COUNTRY_RISK`/`POLICY_PACK`/`SECRET_CHANGE`/`RELATIONSHIP_REJECT`/`CHECKLIST_CHANGE`/`PERIODIC_REVIEW_CHANGE`(DB §5.16 동기화. `CHECKLIST_CHANGE`=CDD/EDD checklist 정책 변경, `PERIODIC_REVIEW_CHANGE`=periodic review 주기 변경 — 설계서 §13.4/§13.5 정본)
- [BE] **admin 정책 결재 트리거 등재(API §10)**: `POST .../country-risk:change`→`subjectType=COUNTRY_RISK`, `POST .../policy-packs:change`→`subjectType=POLICY_PACK`, `PUT .../cdd/checklists/{id}`→`subjectType=CHECKLIST_CHANGE`, `PUT .../cdd/periodic-review-policy`→`subjectType=PERIODIC_REVIEW_CHANGE`. 각 상신 진입점은 도메인 태스크(T-11/T-13) 소유, 결재 상태머신·`maker≠checker`·`payload_hash`·실행분리는 본 태스크가 공통 처리
- [BE] subject_type별 아웃박스/실행 효과(`aml_outbox` DB §3.15·V16, T-16): STR_SUBMIT/CTR_SUBMIT/TRAVEL_RULE_EXCEPTION→`report.submission.requested`, WLF_DECISION(TRUE_MATCH)→`aml.screening.true_match`, RISK_OVERRIDE→`aml.customer.high_risk`, TM_SCENARIO(:activate)→scenario 적용, COUNTRY_RISK→정책 store(국가위험 등급표) 반영+관련 대상 RA 재평가 트리거(T-11), POLICY_PACK→`aml_tenants.policy_pack_code` effective version 갱신(T-03/T-17)
- [BE] 🔒 흐름: ①상신(maker)→202 approvalId(SUBMITTED) ②승인(checker)→APPROVED ③실행→EXECUTED
- [BO] Admin: `admin/aml/approvals`, `:approve`, `:reject`
- [BO] 결재 대기함 화면(bo-web)
- [BE] AI agent는 상신·초안만, 승인자 불가

## 참조
- `docs/design/api/02-aml-api.md` §1.5(4-eyes), §3.7(ApprovalDto/ApprovalDecisionRequest, subjectType **16종**: `CHECKLIST_CHANGE`·`PERIODIC_REVIEW_CHANGE` 포함), §2.7(approvals·country-risk:change·policy-packs:change·cdd/checklists·periodic-review-policy), §10(4-eyes 결재 트리거 등재표: 🔒엔드포인트↔subjectType 1:1)
- `docs/design/db/02-aml-db.md` §3.15(`aml_approvals`), §5.12(approval_line), §5.13(approval_status), §5.16(subject_type enum 16종)
- `docs/design/integration/02-aml-integration.md` §8.2·§8.3(결재 상태머신·아웃박스 효과)
- `docs/software/02-amlSvc-sass.md` §13.4(4-eyes 대상 표·subjectType 16종 매핑), §13.5(결재 시스템·subjectType 정본 주석)

## 변경 이력
| 일자 | 변경 |
|---|---|
| 2026-06-08 | #51 subjectType '14종'→'**16종**'(`CHECKLIST_CHANGE`·`PERIODIC_REVIEW_CHANGE` 추가, 설계서 §13.4/§13.5·API §3.7 정본). admin 정책 결재 트리거에 각 subjectType 코드 명시. 참조에 §5.16·§13.4 추가. |
