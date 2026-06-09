# T-21 Legacy Vendor Bridge(alert ingest·dual-run·reconciliation) [BE]

- 서비스: `services/aml-svc` · Effort: L · 의존: T-05, T-09 · Status: TODO

## 목표
기존 AML 벤더(옥타솔루션 등) alert/case를 evidence로 수신하고, dual-run 비교·reconciliation·rule/model migration inventory를 지원한다. (화면 비대상 — 운영 비교 화면은 후속)

## 구현 항목
- [BE] `VENDOR_BRIDGE` connector(ingest_mode): vendor alert/case → `external_alert` evidence(SaaS alert와 구분)
- [BE] vendor DB export adapter: export file / read-only replica → canonical AML event(직접 write 금지, vendor schema는 adapter만 인지)
- [BE] dual-run: 벤더 판단·SaaS 판단·analyst final decision 분리 저장(integration §7.3). vendor alert id는 `aml_alerts.external_alert_ref`(DB §3.10 VARCHAR(256) NULL 확정, `ix_alert_ext_ref`)에 cross-ref 저장
- [BE] shadow case: 내부 evidence만 보존, 고객 운영 action 없음
- [BE] reconciliation report: freshness·batch 누락·connector health
- [BE] rule/model migration inventory(WLF threshold·RA factor·TM scenario)

## 참조
- `docs/design/integration/02-aml-integration.md` §7.1(VENDOR_BRIDGE), §7.3(Legacy Vendor Bridge 매핑)
- `docs/software/02-amlSvc-sass.md` §15.5, §22(D-10)
