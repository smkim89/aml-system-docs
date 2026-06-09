# T-12 Decision API(실시간 평가)·fail policy·reason/decision code [BE]

- 서비스: `services/fds-svc` · Effort: L · 의존: T-09 · Status: TODO

## 목표
승인 전 실시간 FDS 판단 API를 제공한다. 동기 평가로 decision·reasonCodes·riskScore·recommendedActions를 즉시 반환하고, 장애 정책(fail-closed/fail-open/case-only)을 적용한다.

## 구현 항목
- [ ] **[BE]** `POST /api/v1/fds/decisions/evaluate`(동기): `fds_decisions`+`fds_decision_reasons` 동기 생성. 멱등 필수
- [ ] **[BE]** 응답 DTO `DecisionResponse`: `decisionId`·`decision`·`reasonCodes`·`riskScore`(0~100)·`recommendedActions`·`matchedRules`·`ruleSetVersion`·`expiresAt`
- [ ] **[BE]** 장애 정책(D-14): `fds_source_systems.fail_policy`(`FAIL_CLOSED`→`FDS-FAIL-CLOSED` 503 / `FAIL_OPEN`→ALLOW / `CASE_ONLY`→REVIEW+case 후보)
- [ ] **[BO]** decision 조회: `GET /api/v1/fds/decisions/{id}`(증적 요약·마스킹), `GET /fds/decisions`(필터 `transactionRef`/`decision`/`from/to`) — decision 추이 대시보드 입력
- [ ] `feature_snapshot`/`input_event_hash`는 기본 응답에서 요약/마스킹(전체는 Evidence API)
- [ ] API timeout/retry/duplicate/late event → idempotency store + reconciliation 기록
- [ ] **[BE]** `fds_decisions` insert 시 `FdsDecisionCreated` webhook 발행(`fds-webhook` Standard, 공통 publisher=T-14): `decisionId`·`decision`·`reasonCodes`·`riskScore`. PII 없음, `sandbox` 미발행

## 참조
- `docs/software/01-fdsSvc-sass.md` §12.8(실시간 판단 API·장애 원칙), §11.1(decision)
- `docs/design/api/01-fds-api.md` §4.2(Decision API), §5.3~5.4, §6(`FDS-FAIL-CLOSED`)
- `docs/design/db/01-fds-db.md` §5.3(fail_policy), §5.10~5.11
- `docs/design/integration/01-fds-integration.md` §3.2/§4.5(`FdsDecisionCreated` webhook), §12(`fds-webhook`) — overview §5a 큐 매핑
