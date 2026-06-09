# T-20 관측성·metric·운영 대시보드 데이터·connector health [BE+BO]

- 서비스: `services/aml-svc` (+ bo) · Effort: M · 의존: T-07, T-08 · Status: TODO

## 목표
운영 metric·traceId 관측성·connector health를 노출하고, bo-web 운영 대시보드 데이터를 제공한다.

## 구현 항목
- [BE] metric: `aml.ingest.received`, `aml.screening.requested/true_match/false_positive`, `aml.ra.evaluated`, `aml.tm.alert.created`, `aml.case.opened/sla.breached`, `aml.report.created`, `aml.watchlist.import.failed`
- [BE] traceId 전파(global filter) + 경계별 진입/이탈 구조화 로그
- [BE] connector lag·watchlist freshness·reconciliation health
- [BO] 운영 대시보드 데이터 API(고객사별 WLF 처리량, RA score distribution, TM alert backlog, case SLA, STR/CTR 후보, Travel Rule exception, connector lag, audit export)

## 참조
- `docs/software/02-amlSvc-sass.md` §20(운영·관측성)
- `docs/design/integration/02-aml-integration.md` §6.3(DLQ 운영)
