# T-16 트랜잭셔널 아웃박스·dispatch·report-callback [BE]

- 서비스: `services/aml-svc` · Effort: M · 의존: T-07, T-12 · Status: TODO

## 목표
결재 실행·high-risk 전파·report 제출·webhook 통지를 신뢰성 있게 전달하는 트랜잭셔널 아웃박스와 dispatch·콜백을 구현한다. (화면 비대상)

## 구현 항목
- [BE] `aml_outbox` 테이블 사용(**DB §3.15 신설 확정, Flyway V16** — 이전 선행 이격 종결). snake_case 컬럼 정본: `outbox_id, tenant_id, data_scope, aggregate_type, aggregate_ref, event_type, payload, payload_hash, status, attempt, next_attempt_at, published_at, trace_id, created_at`
- [BE] status enum(DB §5.17): PENDING/DISPATCHING/DISPATCHED/FAILED. 발행 멱등 UNIQUE(`ux_outbox_idem`)·`ix_outbox_dispatch`(status·next_attempt_at)
- [BE] poller(`OutboxDispatcher`): `SELECT FOR UPDATE SKIP LOCKED` → `aml-outbox-dispatch` 큐(소유 큐)
- [BE] dispatch payload(integration §4.5): report submission / fds-feedback / **webhook callback dispatch(서명·상태변경 통지, `webhook.callback.requested`)** — report-callback과 동격
- [BE] `aml-report-callback` 큐 consumer(`ReportCallbackConsumer`): `report.submission.acked/failed` 수신 → 상태 갱신
- [BE] 재시도·backoff·DLQ(`aml-outbox-dlq`)

## 참조
- `docs/design/integration/02-aml-integration.md` §2.1(`aml-outbox-dispatch`/`aml-report-callback`), §3.4(`webhook.callback.requested`), §4.5, §8.1(아웃박스 상태머신)
- `docs/design/db/02-aml-db.md` §3.15(aml_outbox), §5.17(outbox_status), §7(V16)
- `docs/software/02-amlSvc-sass.md` §13.5, §13.5.1, §14, §15.8(트랜잭셔널 아웃박스)
