# T-09 Rule Engine·DSL·decision store·decision reasons [BE]

- 서비스: `services/fds-svc` · Effort: XL · 의존: T-08 · Status: TODO

## 목표
feature catalog 기반 룰 평가 엔진(DSL·threshold·velocity·group match)과 decision store를 구현한다. decision·reason code·matched rules·feature snapshot 증적을 함께 저장한다.

## 구현 항목
- [ ] **[BE]** rule 평가 엔진: `fds_rules.rule_json`(컴파일된 룰) 로딩, threshold/velocity/group match. `dsl_source`(no-code 표현) → `rule_json` 컴파일(자체 DSL, D-03)
- [ ] **[BE]** `fds_rule_sets`/`fds_rules` active 버전 로딩(`ix_rules_set_status`). channel scope 라우팅
- [ ] **[BE]** Decision Engine: decision enum 8종(`ALLOW`/`MONITOR`/`REVIEW`/`CHALLENGE`/`BLOCK`/`HOLD`/`FREEZE`/`REPORT`) 산출
- [ ] **[BE]** `fds_decisions`(append-only) insert: `risk_score`·`matched_rules`(rule_id+version)·`rule_set_version`·`feature_snapshot`·`input_event_hash` 증적
- [ ] **[BE]** `fds_decision_reasons` insert: `reason_code`(`NEW_BENEFICIARY`/`TRANSFER_VELOCITY`/`MULE_ACCOUNT_GROUP`/… §7.2) + detail
- [ ] **[BE]** recommendedActions = enum action_type 코드값(matched rule outcome)
- [ ] 동일 이벤트 replay 시 같은 decision 재현(증적 보존)

## 참조
- `docs/software/01-fdsSvc-sass.md` §10(룰 엔진·룰 예시), §11.1(decision)
- `docs/design/db/01-fds-db.md` §5.10(decisions), §5.11(decision_reasons), §5.16~5.18(rules/versions)
- `docs/design/api/01-fds-api.md` §5.4(DecisionResponse), §7(reason/decision code)
