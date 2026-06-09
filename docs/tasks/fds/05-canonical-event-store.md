# T-05 Canonical event store·멱등/dedup·subject/account/instrument [BE]

- 서비스: `services/fds-svc` · Effort: L · 의존: T-02, T-04 · Status: TODO

## 목표
공통 금융 이벤트 모델(canonical event)의 영속화·이중 멱등 방어·subject/account/instrument materialization을 구현한다. transaction-event 분리, event family 라우팅을 지원한다.

## 구현 항목
- [ ] `fds_canonical_events` upsert(`UNIQUE (tenant_id, workspace_id, idempotency_key)`), `event_type`=`<family>.<verb>`, `event_family` 라우팅 컬럼
- [ ] **[BE]** 이중 멱등: (1) `fds_idempotency_keys`(scope `EVENT`/`DECISION`/`ACTION`) 조회, (2) 테이블 UNIQUE. 재요청 시 결과 재반환(`Idempotency-Replayed: true`)
- [ ] subject/account/instrument materialization(`fds_subjects`/`fds_accounts`/`fds_instruments`), `first_seen_at`(first-seen feature)
- [ ] `fds_transactions` materialization(transaction 단위 decision/action 조회 지원, §7.3)
- [ ] `canonical_payload`는 PII 제거 후 저장. 식별자 token/hash만
- [ ] 필수/조건부 필드 검증(§8.3): tenantId·sourceSystem·eventId·idempotencyKey·eventType·occurredAt·channelType 필수
- [ ] 인덱스: subject velocity(`subject_ref, occurred_at DESC`), tx 조회, family 라우팅

## 참조
- `docs/software/01-fdsSvc-sass.md` §7(데이터 모델), §8(event taxonomy), §8.3(필수 필드)
- `docs/design/db/01-fds-db.md` §5.5~5.9, §5.33(idempotency), §6(인덱스)
- `docs/design/api/01-fds-api.md` §5.1, §3.3(멱등성)
- `docs/design/integration/01-fds-integration.md` §6.1(멱등 이중방어)
