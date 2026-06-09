# T-19 Evidence Export·manifest hash·검사대응 pack·export webhook callback [BE+BO]

- 서비스: `services/fds-svc` + `bo-api` · Effort: L · 의존: T-15, T-16 · Status: TODO

## 목표
감독기관·내부감사 제출용 evidence pack을 자동 생성하는 self-service export와 decision/case/action webhook callback을 구현한다. export 최종본은 결재 대상이며 manifest hash로 증적을 고정한다.

## 구현 항목
- [ ] **[BO]** Evidence API: `GET /evidence/fds/cases/{id}/timeline`, `GET /evidence/fds/reports/decisions`, `POST /evidence/fds/exports`, `GET /{exportId}`, `/download`
- [ ] **[BE]** `fds_evidence_exports`: `export_kind`(DECISION_TIMELINE/CASE_TIMELINE/DECISION_REPORT/CONNECTOR_RECON/FALSE_POSITIVE/PII_ACCESS), `export_format`(CSV/EXCEL/PDF/JSON_API), `export_status`(6종)
- [ ] **[BE]** `manifest_hash` 보존: export 시점 query 결과 + manifest + hash. evidence id로 원천 row·audit row 재추적
- [ ] **[BO]** 제출용 최종본 export = 4-eyes 결재(`subject_kind=EXPORT`, `COMPLIANCE_MANAGER`)
- [ ] **[BE]** export 생성·다운로드·삭제도 감사(`fds_audit_logs`)
- [ ] **[BE]** evidence export 완료 webhook callback(`fds-webhook` Standard) 발행: export READY 알림. 공통 webhook publisher(`X-Signature`·dedup·재시도 8회·`fds-webhook-dlq`)는 T-14 횡단 모듈 사용. PII 없음(token/마스킹)
- [ ] vendor 병행 시 vendor decision id ↔ SaaS evidence id cross-reference

> **webhook 콜백 소유 경계(integration §3.2/§4.5, overview §5a)**: `FdsDecisionCreated`→T-12, `FdsActionResult`→T-14, `FdsCaseOpened`/`FdsCaseStatusChanged`→T-16, evidence export 콜백→본 T-19. 공통 publisher(서명·dedup·재시도)는 T-14가 횡단 제공. 본 태스크는 evidence 콜백만 담당한다.

## 참조
- `docs/software/01-fdsSvc-sass.md` §12.7(Evidence Export API), §16.4(검사 대응 산출물)
- `docs/design/db/01-fds-db.md` §4.17(export enum), §5.31~5.32
- `docs/design/api/01-fds-api.md` §4.5(Evidence API), §5.11
- `docs/design/integration/01-fds-integration.md` §2(`fds-webhook`), §4.5(callback), §11.2(reconciliation)
