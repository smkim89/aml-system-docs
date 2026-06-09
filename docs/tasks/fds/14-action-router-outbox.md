# T-14 Action Router·아웃박스·`fds-actions` relay·capability 매트릭스 [BE]

- 서비스: `services/fds-svc` · Effort: L · 의존: T-09, T-15 · Status: TODO

## 목표
capability 기반 action router와 트랜잭셔널 아웃박스를 구현한다. `fds_actions` outbox row를 `fds-actions`(FIFO)로 relay하고, 대상 시스템 capability 미지원 시 case-only로 강등한다.

## 구현 항목
- [ ] **[BE]** `fds_actions` outbox insert(`status=PENDING`, 자금/규제성→`APPROVAL_REQUIRED`). `UNIQUE (tenant_id, workspace_id, idempotency_key)`
- [ ] **[BE]** 아웃박스 relay poller(`SELECT FOR UPDATE SKIP LOCKED`): `PENDING`/`APPROVED` row → `fds-actions` 발행(at-least-once)
- [ ] **[BE]** 상태머신: `PENDING`/`APPROVAL_REQUIRED`/`APPROVED`/`SENT`/`ACKED`/`FAILED`/`CANCELLED`. 상태 전이 위반 → `FDS-STATE-CONFLICT`
- [ ] **[BE]** FIFO `messageGroupId = tenantId:workspaceId:targetRef`, `messageDeduplicationId = idempotencyKey`
- [ ] **[BE]** `FdsActionResult`(adapter→fds-svc) 처리: `status=ACKED|FAILED`·`error_code`·`completed_at` 갱신. retry(지수 백오프, 5회 → DLQ)
- [ ] **[BE]** capability 매트릭스: action_type × control_capability 검증. 미지원 시 `OPEN_CASE`로 강등(CANCEL_TRANSACTION→REQUEST_REVERSAL)
- [ ] **[BE]** `sandbox` workspace shadow-only(`PENDING`/`APPROVED`에서 발행 안 함)
- [ ] action enum 23종 라우팅. 자금성 action은 `approval_request_id` 없으면 relay 금지
- [ ] **[BE]** 공통 webhook publisher(`fds-webhook` Standard, 횡단 모듈): `X-Signature` 서명·idempotencyKey dedup·재시도 8회·`fds-webhook-dlq`. T-12/T-16/T-19 도메인 콜백이 본 모듈 사용. `sandbox` 미발행
- [ ] **[BE]** action 완료 시 `FdsActionResult` webhook 발행(고객 endpoint). 인바운드 `FdsActionResult` ack(adapter→fds-svc) 소비와 구분

## 참조
- `docs/software/01-fdsSvc-sass.md` §5.3(capability), §11.2(action), §11.2a(비정본 verb→정본 매핑), §9.4(control_capability)
- `docs/design/db/01-fds-db.md` §4.8(action_type 23종, API `ActionType` enum 정본), §4.9(action_status), §5.12(actions)
- `docs/design/integration/01-fds-integration.md` §8.1(상태머신), §8.2(capability 매트릭스), §5.1(relay), §3.2/§4.5(`FdsActionResult` webhook·공통 publisher), §12(`fds-webhook`) — overview §5a 큐 매핑
