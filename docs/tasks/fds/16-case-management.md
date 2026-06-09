# T-16 Case Management·timeline·SLA·assignment·close·feedback [BE+BO]

- 서비스: `services/fds-svc` + `bo-api` · Effort: XL · 의존: T-09, T-14, T-15 · Status: TODO

## 목표
조사 케이스(fraud/AML origin/chargeback/mule/merchant/internal audit 등)의 생성·배정·timeline·SLA·종결·false positive feedback workflow를 구현한다. 내부감사·규제 case 종결은 결재 게이트를 거친다.

## 구현 항목
- [ ] **[BE]** `fds_cases` 생성(decision REPORT/FREEZE/REVIEW origin, `origin_decision_id`). case_type 11종, status 8종(`OPEN`~`CLOSED_*`)
- [ ] **[BE]** `fds_case_events`(append-only timeline): `event_kind` ASSIGNED/COMMENT/STATUS_CHANGE/EVIDENCE_ATTACHED/APPROVAL/CLOSED
- [ ] **[BE]** `fds_case_scopes`(다중 data-scope)
- [ ] **[BO]** Case API: `GET /fds/cases`(필터 status/caseType/priority/assignedTo/from-to), `GET /{id}`, `/events`, `PATCH /{id}`, `/assign`, `/close`, `/feedback`
- [ ] **[BO]** case 종결: `close_reason`. 내부감사(INTERNAL_AUDIT)·규제 case 종결은 🔒(`COMPLIANCE_MANAGER`)
- [ ] **[BO]** false positive feedback 등록(재발 방지 rule feedback loop, T-11 연계)
- [ ] **[BE]** SLA·priority(`ix_case_status`, `ix_case_assignee`) — case 큐·담당자 case 조회
- [ ] **[BE]** case 기반 수동 action 상신(`POST /fds/cases/{id}/actions` → T-14 outbox)
- [ ] AML/Travel Rule case는 origin만 보유, 본 처리 aml-svc 위임(`amlCaseRef`, T-17). 본 처리 시도 → `FDS-AML-DELEGATED`
- [ ] **[BE]** case 변경 시 `FdsCaseOpened`/`FdsCaseStatusChanged` webhook 발행(`fds-webhook` Standard, 공통 publisher=T-14): `caseId`·`caseType`·`status`·`amlCaseRef`. PII 없음, `sandbox` 미발행

## 참조
- `docs/software/01-fdsSvc-sass.md` §11.3(case type), §2.6(case 자율운영), §17.2(case SLA)
- `docs/design/db/01-fds-db.md` §4.10~4.11(case enum), §5.13~5.15
- `docs/design/api/01-fds-api.md` §4.4(Case API), §4.3(case action)
- `docs/design/integration/01-fds-integration.md` §3.2/§4.5(`FdsCaseOpened`/`FdsCaseStatusChanged` webhook), §12(`fds-webhook`) — overview §5a 큐 매핑
