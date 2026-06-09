# T-08 Feature Store·feature catalog·velocity/window materialization [BE+BO]

- 서비스: `services/fds-svc` + `bo-api` · Effort: XL · 의존: T-05 · Status: TODO

## 목표
룰 평가가 내부 materialized state만 사용하도록(설계서 §5.2) feature store를 구축한다. subject/account/instrument/counterparty/velocity/behavior feature를 미리 materialize하고, no-code rule builder가 노출할 feature catalog를 관리한다.

## 구현 항목
- [ ] **[BE]** velocity/window feature materialization(count/sum by subject/instrument/counterparty in window). `fds_canonical_events` subject-time 인덱스 활용
- [ ] **[BE]** feature category: Subject·Transaction·Instrument·Counterparty·Device·Location·Velocity·Behavior·Group·AML·Merchant·Crypto·Trade·Commerce·Settlement·Corporate Approval(§10.1)
- [ ] **[BE]** enrichment 단계 외부 조회 materialize(룰 평가 중 실시간 외부 API 호출 금지)
- [ ] **[BO]** `fds_feature_catalog` CRUD: `feature_key`(`velocity.count.subject.24h`)·`category`·`value_type`(`NUMBER`/`STRING`/`BOOL`/`ENUM`)·`display_label`. global feature는 tenant `'_global'`
- [ ] **[BO]** Admin API: `GET /api/v1/admin/fds/feature-catalog`(no-code builder 입력)
- [ ] ML score adapter port(외부 score 수신, D-05 외부 우선)

## 참조
- `docs/software/01-fdsSvc-sass.md` §5.2(materialized state), §10.1(feature category)
- `docs/design/db/01-fds-db.md` §5.20(feature_catalog)
- `docs/design/api/01-fds-api.md` §4.6(feature-catalog)
