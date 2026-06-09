# T-15 FDS↔AML event 연동(escalation·feedback·Internal API) [BE]

- 서비스: `services/aml-svc` · Effort: M · 의존: T-07, T-13, T-14 · Status: TODO

## 목표
fds-svc fraud case escalation을 STR 후보로 수용하고, AML high-risk/true match를 fds-svc로 전파한다. event 연동 우선(D-07) + Internal API 병행. (화면 비대상)

## 구현 항목
- [BE] 인바운드 `aml-fds-decision` 큐(소유): `fds.case.escalated`, `fds.decision.applied` → STR_REVIEW case/alert. fds-svc `OPEN_AML_CASE` 위임 시 `aml_cases.origin_fds_case_ref ↔ fds_cases.aml_case_id`(VARCHAR(96), cross-ref·FK 아님, DB §3.11 확정) 양방향 연결, `source_origin=FDS`
- [BE] 아웃바운드 `aml-fds-feedback` 큐(소유): `aml.screening.true_match`, `aml.customer.high_risk`, `aml.case.str_recommended`
- [BE] Internal API(`X-Internal-Service`+mTLS): `POST /internal/v1/aml/fds-escalations`, `GET /internal/v1/aml/customers/{customerRef}/risk`, `POST /internal/v1/aml/screen`
- [BE] `FdsEscalationRequest` DTO(API §3.10) → `aml_alerts`
- [BE] `FdsCasePort`(out) fds-svc client, traceId cross-service 전파
- [BE] 직접 DB 공유 금지(event/Internal API만)

## 참조
- `docs/design/api/02-aml-api.md` §2.6(Internal), §3.10(FdsEscalationRequest)
- `docs/design/integration/02-aml-integration.md` §3.2·§3.3, §5.3(FDS escalation)
- `docs/software/02-amlSvc-sass.md` §6.1, §12.3, §22(D-07)
