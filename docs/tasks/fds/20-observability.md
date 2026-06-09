# T-20 관측성·metric·connector health·운영 대시보드 데이터 [BE+BO]

- 서비스: `services/fds-svc` + `bo-api` · Effort: M · 의존: T-07, T-14 · Status: TODO

## 목표
traceId 전파 기반 구조화 로그와 운영 지표(ingest/decision/action/case/connector lag)를 노출하고, connector health·replay·운영 대시보드 데이터를 제공한다.

## 구현 항목
- [ ] **[BE]** 메트릭: `fds.ingest.received/.accepted/.rejected/.duplicate`, `fds.connector.lag`, `fds.rule.evaluated`, `fds.decision.created`, `fds.action.sent/.failed`, `fds.case.opened`, `fds.aml.handoff/.failed`
- [ ] **[BE]** traceId(`traceparent`)+correlationId 모든 경계(in/out) 구조화 로그 전파(MDC)
- [ ] **[BE]** DLQ depth poller(PT60S) → `*.failed`/`*.rejected` 메트릭(T-07/T-14 연계)
- [ ] **[BE]** connector reconciliation job(`adapter/in/scheduled`): 원천 시퀀스 vs `fds_canonical_events` 누락 비교 → replay. 결과 `export_kind=CONNECTOR_RECON` 증적화
- [ ] **[BO]** connector health API: `GET /admin/fds/connectors`(`fds_connector_offsets` status/lag) 목록, `GET .../connectors/{id}`(단건 health·offset·`lag_seconds`·`last_error_code`·cursor 마스킹, API §5.15 ConnectorDto), `POST .../{id}/replay`
- [ ] **[BO]** connector 운영 제어: `POST /admin/fds/connectors/{id}/pause`(`connector_status`→`DISABLED`, ingest/poll suspend·offset 보존), `POST .../{id}/resume`(`DISABLED`→`HEALTHY`, 보존 offset부터 소비 재개). 멱등(이미 목표 상태면 동일 body 재반환), 상태머신 위반(`ERROR` 강제 resume 등) → `FDS-STATE-CONFLICT`(409), data-scope 밖 → `FDS-DATASCOPE-DENIED`(403)/미존재 → `FDS-NOT-FOUND`(404). API §5.16 ConnectorStateChange*
- [ ] **[BO]** 운영 대시보드 데이터: tenant별 ingest 상태·connector lag/error·schema validation 실패·decision 추이·action 실패 큐·case SLA·룰 hit rate·false positive feedback·데이터 품질

## 참조
- `docs/software/01-fdsSvc-sass.md` §17(운영·관측성·운영 화면)
- `docs/design/db/01-fds-db.md` §5.28(connector_offsets), §6(인덱스)
- `docs/design/integration/01-fds-integration.md` §11(관측성·재제출)
- `docs/design/api/01-fds-api.md` v1.4 §4.8(connectors 목록·`GET /connectors/{id}`·`/pause`·`/resume`·`/replay`), §5.15(ConnectorDto), §5.16(ConnectorStateChange*), §6(`FDS-STATE-CONFLICT`/`FDS-DATASCOPE-DENIED`/`FDS-NOT-FOUND`)
