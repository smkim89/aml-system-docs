# T-08 Watchlist source import·diff·승인·인덱스 [BE+BO]

- 서비스: `services/aml-svc` (+ bo) · Effort: L · 의존: T-05, T-12 · Status: TODO

## 목표
명단 source(제재/PEP/RCA/adverse media/internal/law enforcement/VASP)를 versioned import·diff·4-eyes 승인 후 적용하고 검색 인덱스를 구축한다.

## 구현 항목
- [BE] `aml_watchlist_sources`·`aml_watchlist_entries` adapter, `watchlist_source_type` enum(SANCTIONS/PEP/RCA/ADVERSE_MEDIA/INTERNAL/LAW_ENFORCEMENT/VASP_RISK)
- [BE] versioned import: import version 적재 → diff 산출 → apply 시 인덱스 갱신
- [BE] 검색 인덱스: PostgreSQL GIN(`normalized_tokens`) fallback(D-02). OpenSearch 채택 시 동기화 인덱서 별도 태스크
- [BE] watchlist freshness 스케줄러(`adapter/in/scheduled`) + 실패 metric(`aml.watchlist.import.failed`)
- [BO] Admin: `admin/aml/watchlist-sources`, `admin/aml/watchlist-entries`, `imports/{version}:apply` 🔒(결재 경유)
- [BO] import diff 확인·승인·rollback 화면(bo-web)

## 참조
- `docs/design/db/02-aml-db.md` §3.6·§3.7, §5.4, §4(GIN 인덱스)
- `docs/design/api/02-aml-api.md` §2.7(watchlist-sources/entries)
- `docs/software/02-amlSvc-sass.md` §10.1, §3.1, §13.4
