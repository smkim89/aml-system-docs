# BOF-S3 · 커넥터·인입 가시성·스키마 매핑 (SFDS-CONN-001~004 · SFDS-MAP-001/002)

> **목표**: 데이터 인입 경로(커넥터)의 운영·가시성(마지막 수신·신호·폴링·큐·백필)과 스키마/PII 매핑 완성.
> **선행**: BOF-S1 (S2 권장 — 대시보드 딥링크 대상). **PPT**: 슬라이드 12~18.

## 공통 참고 문서
- PRD §4.0 **데이터 인입 유형(확정)** — 연동 방식(`ingest_mode` 5종)×표시 신호·수신 API 카탈로그 5종·신호 상태 3종(●/⚠/✕) ← **본 Stage 전 화면의 표시 표준**
- PRD §4.1~§4.4 / API `01-fds-api.md` §4.1(`POST /fds/events` 202)·§4.8(source-systems·connectors·replay/pause/resume)·§5.1(IngestEventRequest)
- 큐·DLQ 정본: integration `01-fds-integration.md` §2(`fds-events` FIFO·`fds-vendor-ingest`·DLQ depth poller PT60S)·§6(멱등·재처리)
- 스키마·매핑: PRD §5.1·§5.2 / 설계서 `01-fdsSvc-sass.md` §6·§13.2 / API(매핑 PUT 4-eyes)

## 태스크

| ID | 구분 | 태스크 | 참고 문서 | Effort | 의존 |
|---|---|---|---|---|---|
| BOF-S3-01 | **SPEC** | **인입 집계 API 명세 확정(선행)** — `GET /api/v1/bo/fds/ingest/catalog`·`GET .../ingest/health` 응답 스키마(API별 호출량·마지막 호출 / 커넥터별 마지막 수신·신호·depth·lag·DLQ·폴링 커서·백필 %)와 집계 원천(게이트웨이/SQS 지표) 확정 → `docs/design/api/01-fds-api.md` 반영 | PRD v5.0 변경 이력 ②(오픈결정) / PRD §4.0·§4.4 | 2 | — |
| BOF-S3-02 | BE | **커넥터 운영 프록시** — `GET /admin/fds/source-systems`·`/connectors`·`GET /connectors/{connectorId}`·`POST .../replay`·`/pause`·`/resume`·`PUT /source-systems/{id}`(4-eyes 상신) 위임 + 감사 | API §4.8(경로 변수 `{connectorId}` 정본) / PRD §4.2 BR-001~006 | 3 | S1-04 |
| BOF-S3-03 | BE | **인입 집계 API 구현** — `/bo/fds/ingest/catalog`·`/ingest/health`(read-only·30~60초 캐시·자동 새로고침 대응) | BOF-S3-01 확정 명세 / integration §2·§6(큐·DLQ 수치 원천) | 4 | S3-01·S1-05 |
| BOF-S3-04 | FE | **SFDS-CONN-001 커넥터 목록** — 컬럼(연동 방식·사용·지연·**마지막 수신·신호 ●/⚠/✕**·최근 오류)·`[인입 모니터링]`→CONN-004·행▶ 상세 | PRD §4.1(BR-005 신호 표준) / PPT 슬라이드 12 | 2 | S3-02 |
| BOF-S3-05 | FE | **SFDS-CONN-002 커넥터 상세/운영** — 기본/인입 신호 패널(폴링=마지막·**다음 폴링 예정·주기**·커서 / 큐=depth·DLQ / REST=TPS), 처리 현황 24h, 재처리(범위 필수·멱등)·커서 이동·일시중지/재개·설정 변경(4-eyes 상신) | PRD §4.2(BR-006 신호·운영 버튼 시나리오 전수) / PPT 슬라이드 13 / API §4.8 | 4 | S3-02 |
| BOF-S3-06 | FE | **SFDS-CONN-003 커넥터 등록/수정** — 연동 방식별 설정 폼(큐 ARN/REST 서명키/폴링 cursor/CDC allowlist/스냅샷), 서명키 마스킹(앞3+뒤4)·자격증명 회전 4-eyes | PRD §4.3 / PPT 슬라이드 14 / API §4.8(credentials rotate) | 3 | S3-02 |
| BOF-S3-07 | FE | **SFDS-CONN-004 ① 수신 API 카탈로그** — API 5종 표(용도·방식 202/동기·24h 호출·마지막 호출·신호) + **연동 방식×표시 신호 확정표(5종 — 큐 행 fds-events(FIFO)·fds-vendor-ingest·DLQ 병기)** 상시 표시 | PRD §4.0 ②·③·§4.4 ① / PPT 슬라이드 15 | 2 | S3-03 |
| BOF-S3-08 | FE | **SFDS-CONN-004 ② 인입 라이브 모니터링** — KPI(24h 수신·라이브 n/n·DLQ 적체·마지막 수신) + 커넥터×방식별 라이브 표(행▶→CONN-002), ⚠/✕ 강조·DASH 알림 딥링크 수신 | PRD §4.4 ②·BR-001~003 / PPT 슬라이드 16 / integration §2(DLQ poller) | 3 | S3-03 |
| BOF-S3-09 | BE | **스키마·매핑 프록시** — `GET /admin/fds/source-systems`(스키마 레지스트리)·`PUT .../{ss}/mappings`(4-eyes `MAPPING` 상신) 위임 | API(매핑) / PRD §5.1·§5.2 / 설계서 §6(canonical 변환)·§13.2 | 2 | S1-04 |
| BOF-S3-10 | FE | **SFDS-MAP-001/002 스키마·필드 매핑** — 레지스트리 목록 + 매핑 편집(필드↔canonical·PII 정책 토큰화/폐기·`FDS-PII-REJECTED` 422 처리)·변경 4-eyes 상신 | PRD §5.1·§5.2 / PPT 슬라이드 17~18 / PRD §16.3(에러) | 4 | S3-09 |

## DoD
- 인입 신호(●/⚠/✕)·마지막 수신·다음 폴링·큐 depth·DLQ·백필 %가 §4.0 확정표와 동일 항목으로 표시.
- replay/pause/resume 동작이 감사 로그에 남고 멱등 재처리 확인. 매핑 변경이 결재함에 상신됨.
- `(제안 API)` 2건은 BOF-S3-01 확정 전 구현 착수 금지(BLOCKED 표기).
