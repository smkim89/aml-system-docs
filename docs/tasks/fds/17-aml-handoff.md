# T-17 FDS→AML 위임(`fds-aml-handoff`·`amlCaseRef`·규제 후보) [BE]

- 서비스: `services/fds-svc` · Effort: M · 의존: T-14, T-16 · Status: TODO

## 목표
AML/STR/CTR/Travel Rule 후보를 aml-svc로 위임하는 비동기 handoff를 구현한다. fds-svc는 origin case만 생성하고, 본 케이스·규제보고·sanction/PEP는 aml-svc가 소유한다. raw PII 미전파.

## 구현 항목
- [ ] **[BE]** `OPEN_AML_CASE`/`REGULATORY_REPORT`/`REQUEST_TRAVEL_RULE_INFO` action(정본 action_type 23종, DB §4.8) → `fds-aml-handoff`(FIFO) 발행. `FdsAmlHandoff` 메시지. 코인 룰 `OPEN_COMPLIANCE_CASE` 별칭은 정본 `OPEN_AML_CASE`(+`case_type=CRYPTO_TRAVEL_RULE`/`AML_REVIEW`)로 환원(설계서 §11.2a)
- [ ] **[BE]** `handoffType`(action_type 서브셋), `reportKind`(`STR`/`CTR`/`TRAVEL_RULE`), case_type origin 매핑(AML_REVIEW/CRYPTO_TRAVEL_RULE/REGULATORY_REPORT)
- [ ] **[BE]** `fds_cases.aml_case_id VARCHAR(96) NULL` cross-ref(**DB §5.13 정본 확정 컬럼·integration §9.1 동일 타입, FK 아님**): aml-svc ack(`amlCaseRef`) 수신 → `aml_case_id` 기록 + `fds_case_events` STATUS_CHANGE append
- [ ] **[BE]** PII 미전파: token/hash + base 금액만. 원문 payload·문서번호 원문 금지
- [ ] **[BE]** FIFO group `tenantId:workspaceId:caseId`, 멱등키=caseId. 재제출(실패/반려) 시 신규 case 없이 동일 origin 재handoff
- [ ] **[BE]** DLQ(`fds-aml-handoff-dlq`) + replay. metric `fds.aml.handoff`/`.failed`
- [ ] fds-svc API에서 AML/Travel Rule 본 처리 시도 → `FDS-AML-DELEGATED`(409)

## 참조
- `docs/software/01-fdsSvc-sass.md` §11.3(case), §11.2(action_type 23종)/§11.2a(별칭→정본 매핑), §15.4/§15.10(해외송금·코인 AML action), §16.2(특금법)
- `docs/design/integration/01-fds-integration.md` §2(`fds-aml-handoff`), §4.4(FdsAmlHandoff), §9.1(`fds_cases.aml_case_id VARCHAR(96) NULL` 확정·`amlCaseRef` 매핑)
- `docs/design/db/01-fds-db.md` §4.8(위임 action_type: `OPEN_AML_CASE`/`REGULATORY_REPORT`/`REQUEST_TRAVEL_RULE_INFO`), §4.10(case_type 매핑), §5.13(`aml_case_id` 정본 행·`ix_case_aml_ref`), §9(서비스 경계)
- `docs/design/api/01-fds-api.md` §4.4/§5.5(`amlCaseRef`=`fds_cases.aml_case_id`), §11(경계)
