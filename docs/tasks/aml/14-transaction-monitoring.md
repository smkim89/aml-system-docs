# T-14 Transaction Monitoring 엔진·scenario·alert lifecycle [BE+BO]

- 서비스: `services/aml-svc` (+ bo) · Effort: XL · 의존: T-07, T-13 · Status: TODO

## 목표
구조화·반복·고위험국가·비정상 정산 패턴을 탐지하는 TM 엔진과 scenario builder·simulation·alert lifecycle을 구현한다.

## 구현 항목
- [BE] `EvaluateTransactionUseCase` + `aml_alerts` adapter
- [BE] tm_scenario enum(STRUCTURING/RAPID_MOVEMENT/MULE_NETWORK/HIGH_RISK_CORRIDOR/SHELL_MERCHANT/REFUND_LAUNDERING/TRADE_MISPRICING/ROUND_TRIPPING/CRYPTO_OFF_RAMP/INTERNAL_OVERRIDE_ABUSE)
- [BE] velocity/window 집계, feature store, scenario DSL/model artifact
- [BE] alert_status enum(DETECTED/TRIAGED/CASE_OPENED/DISMISSED/ESCALATED/STR_RECOMMENDED) lifecycle
- [BE] Public `POST /api/v1/aml/transactions/evaluate`, `GET /api/v1/aml/alerts/{alertId}`
- [BE] alert dedupe 자연키(transactionRef/scenario+window)
- [BE] alert→case 전환(T-13), STR_RECOMMENDED→STR 후보(T-17)
- [BO] Admin: `GET /admin/aml/tm-scenarios`, `{scenarioCode}/simulate`, `{scenarioCode}:activate` 🔒
- [BO] TM alert backlog·scenario 관리 화면

## 참조
- `docs/design/api/02-aml-api.md` §2.4, §3.4(TransactionEvaluateRequest/Response), §2.7(tm-scenarios)
- `docs/design/db/02-aml-db.md` §3.10, §5.6(tm_scenario), §5.7(alert_status)
- `docs/software/02-amlSvc-sass.md` §12
