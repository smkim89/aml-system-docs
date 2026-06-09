# T-11 Rule admin·version·rollback·simulation [BE+BO]

- 서비스: `services/fds-svc` + `bo-api` · Effort: XL · 의존: T-09, T-15 · Status: TODO

## 목표
준법감시실 자율 운영(개발팀 개입 없는 룰 변경)을 위한 no-code rule admin·버전 관리·rollback·simulation(예상 hit rate)을 구현한다. 룰 활성화·rollback은 4-eyes 결재 대상이다.

## 구현 항목
- [ ] **[BO]** rule CRUD: `GET /admin/fds/rule-sets`, `GET/POST/PUT /admin/fds/rules`(`status=DRAFT`), channel scope
- [ ] **[BO]** rule 활성화 `POST /admin/fds/rules/{ruleId}/activate`(🔒 `RULE`/`COMPLIANCE_MANAGER`), `disable`(tenant policy)
- [ ] **[BO]** version rollback `POST .../rollback`(🔒) + `GET .../versions`(`fds_rule_versions`, effective_from/to 증적)
- [ ] **[BO]** rule simulation `POST /admin/fds/rules/simulations`: `sample_window` 평가 → `estimated_hit_rate`·`result_summary`(`fds_rule_simulations`)
- [ ] **[BE]** 배포 전 영향도 분석·예상 hit rate 산출(시뮬레이션 엔진)
- [ ] **[BE]** rule version 활성/비활성 전환 시 active rule 재로딩(T-09 연계)
- [ ] no-code 업무 언어 표현(`dsl_source`) → `rule_json` 컴파일(조건·기간·금액·국가·채널·action 선택)

## 참조
- `docs/software/01-fdsSvc-sass.md` §2.6(자율 운영), §10.2(룰 예시), §11.4/§11.5(4-eyes/결재)
- `docs/design/db/01-fds-db.md` §5.17~5.19(rules/versions/simulations)
- `docs/design/api/01-fds-api.md` §4.6(rule/simulation admin), §8(4-eyes)
