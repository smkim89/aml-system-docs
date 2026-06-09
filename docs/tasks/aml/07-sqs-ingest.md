# T-07 SQS 토폴로지·ingest consumer·DLQ·FIFO 멱등 [BE]

- 서비스: `services/aml-svc` · Effort: L · 의존: T-05, T-06 · Status: TODO

## 목표
SQS 큐 토폴로지 7종과 ingest consumer(REST_PUSH/QUEUE), DLQ·재시도·FIFO 순서보장·멱등을 구현한다. (화면 비대상)

## 구현 항목
- [ ] 큐 7종 토폴로지: `aml-ingest`(+`.fifo`), `aml-fds-decision`, `aml-screening-async`, `aml-fds-feedback`, `aml-outbox-dispatch`, `aml-report-callback` + 각 `<queue>-dlq`. **소유 귀속(overview §6.1)**: T-07=`aml-ingest`(+`.fifo`)·DLQ 공통; `aml-screening-async`→T-09, `aml-fds-decision`/`aml-fds-feedback`→T-15, `aml-outbox-dispatch`/`aml-report-callback`→T-16
- [ ] 물리명 `aml-<queue>-{env}` 또는 tenant 전용(SCHEMA/DB isolation)
- [ ] FIFO: MessageGroupId=`tenantId:subjectRef`, MessageDeduplicationId=`idempotencyKey`
- [ ] 메시지 attribute: `tenantId`, `idempotencyKey`, `traceparent`, `dataScope`, `schemaVersion`
- [ ] `adapter/in/sqs` consumer(`SqsListener`) — 참조 `fds-svc` `FdsEventsConsumer` 헤더 규약(`idempotencyKey`/`traceparent`)
- [ ] 멱등: canonical store ON CONFLICT(T-05) 재사용, alert/case 자연키 dedupe
- [ ] 재시도·backoff·DLQ 라우팅, DLQ 재처리 도구
- [ ] tenantId/dataScope attribute → `app.current_tenant` RLS 주입

## 참조
- `docs/design/integration/02-aml-integration.md` §2(큐), §3(카탈로그), §6(멱등/재시도/DLQ/순서)
- `docs/software/02-amlSvc-sass.md` §15.3
