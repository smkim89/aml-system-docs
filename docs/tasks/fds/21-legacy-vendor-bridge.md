# T-21 Legacy Vendor Bridge(`fds-vendor-ingest`·dual-run·reconciliation) [BE]

- 서비스: `services/fds-svc` · Effort: L · 의존: T-05, T-12 · Status: TODO

## 목표
기존 FDS/AML 벤더(옥타솔루션 등)와 병행 연동·점진 대체를 지원한다. vendor 결과를 evidence로 수신하고, dual-run/shadow/rule migration 모드를 제공한다. 고객/벤더 DB 직접 write 금지.

## 구현 항목
- [ ] **[BE]** vendor result ingest: `POST /api/v1/fds/external-decisions` + `fds-vendor-ingest`(Standard) 큐. `ExternalDecisionMessage`/`FdsExternalDecisionConsumer`
- [ ] **[BE]** `fds_external_decisions`(evidence, 원천 이벤트 아님): `bridge_mode` enum(VENDOR_RESULT_INGEST/DB_MIRROR/DUAL_RUN/SHADOW_DECISION/RULE_MIGRATION)
- [ ] **[BE]** dual-run: 동일 event를 vendor + SaaS FDS 동시 평가, vendor decision·SaaS decision·고객 action 분리 저장(`fds_decision_id` cross-ref, `ix_ext_tx`)
- [ ] **[BE]** shadow decision: SaaS 결과 action하지 않고 evidence로만 보존
- [ ] **[BE]** vendor DB mirror adapter: read-only replica/export file → 표준 event 변환(core domain은 vendor schema 미인지)
- [ ] **[BE]** heartbeat·reconciliation job: vendor 장애/누락이 운영 증적 누락으로 이어지지 않도록 보정
- [ ] rule migration inventory: 기존 벤더 rule → SaaS DSL 이전 목록

## 참조
- `docs/software/01-fdsSvc-sass.md` §12.6(Legacy Vendor Bridge), §2.4(시장 진입), §18 Phase 6
- `docs/design/db/01-fds-db.md` §4.18(external_decision_mode), §5.30
- `docs/design/api/01-fds-api.md` §4.10(External Vendor Bridge API), §5.14
- `docs/design/integration/01-fds-integration.md` §7.3(vendor bridge 커넥터), §4.6
