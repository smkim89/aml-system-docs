# T-07 SQS 토폴로지·`fds-events` ingest consumer·DLQ·FIFO 멱등 [BE]

- 서비스: `services/fds-svc` · Effort: L · 의존: T-05, T-06 · Status: TODO

## 목표
비동기 SQS 경계를 구축한다. REST Push/Queue/Polling/CDC connector가 `fds-events`(FIFO)로 적재하고, `FdsEventsConsumer`가 정규화·멱등 처리한다. DLQ·재처리·FIFO 순서보장을 보장한다.

## 구현 항목
- [ ] 큐 토폴로지: `fds-events`(FIFO, in) + `fds-events-dlq`. message attributes `eventType`/`source=fds-svc`/`idempotencyKey`/`correlationId`/`traceparent`
- [ ] **[BE]** `adapter/in/sqs` `FdsEventsConsumer`: deliver(at-least-once) → `fds_canonical_events` upsert → feature/rule 트리거
- [ ] **[BE]** REST `POST /api/v1/fds/events` → 내부 `fds-events` 적재(202 ACCEPTED). `:batch`(최대 500)
- [ ] **[BE]** FIFO `messageDeduplicationId = idempotencyKey`, `messageGroupId = tenantId:workspaceId:transactionRef`(없으면 subjectRef/eventId)
- [ ] **[BE]** 재처리: visibility timeout 후 재수신, maxReceiveCount 5 → DLQ. consumer 멱등(재처리 안전)
- [ ] **[BE]** DLQ depth poller(`adapter/in/scheduled`, PT60S) → metric. DLQ 사유: `FDS-PII-REJECTED`/`FDS-SCHEMA-UNKNOWN`/`FDS-VALIDATION-002`
- [ ] **[BE]** Polling/CDC/Snapshot connector(`adapter/in/scheduled`): cursor·replay window·stable ordering·page checksum·rate limit. `fds_connector_offsets` 상태 추적
- [ ] `sandbox` workspace inbound 처리하되 outbound 미발행

## 참조
- `docs/software/01-fdsSvc-sass.md` §12.1~12.5(connector), §3.1(SQS ingest)
- `docs/design/integration/01-fds-integration.md` §2(큐 토폴로지), §6(멱등·DLQ·순서), §7.1(커넥터 모드)
- `docs/design/db/01-fds-db.md` §5.28(connector_offsets), §5.33(idempotency)
