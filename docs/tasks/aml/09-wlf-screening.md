# T-09 WLF screening 엔진·scoring·판정·real-time API [BE+BO]

- 서비스: `services/aml-svc` (+ bo) · Effort: XL · 의존: T-04, T-08 · Status: TODO
- BO 화면(WLF 검토 큐·판정·FP whitelist)은 **T-10** 소유(본 태스크는 엔진 BE + 검토큐 데이터 계약까지)

## 목표
이름·생년·국적·문서번호·법인명·주소 기반 fuzzy matching WLF 엔진과 설명 가능한 scoring, 실시간 screening API, fail 정책을 구현한다.

## 구현 항목
- [BE] `ScreenUseCase` + `domain/ScreeningResult`, `aml_screening_results` adapter
- [BE] scoring component: name similarity(exact/token set/edit distance/transliteration), date/country/document/address/relationship/negative signal — score breakdown 저장
- [BE] screening_status enum(NO_MATCH/POSSIBLE_MATCH/TRUE_MATCH/FALSE_POSITIVE/AUTO_DISCOUNTED/ESCALATED). **API 별칭 `POTENTIAL_MATCH` → `POSSIBLE_MATCH` 정규화**
- [BE] Public `POST /api/v1/aml/screen`(동기), `GET /api/v1/aml/screenings/{screeningId}`
- [BE] 비동기 대량 screening 워커(`ScreeningWorker`): `aml-screening-async` 큐(internal, `screening.requested`) — **대량 재screening·watchlist version 재적용** (본 태스크 소유, integration §2.1)
- [BE] fail 정책(D-14): `aml_source_systems.failure_policy`(DB §3.2 컬럼, DTO 표면=`failurePolicy` API §3.9)=MANUAL_REVIEW → 422 `AML.SCREENING_REQUIRES_REVIEW`, FAIL_CLOSED → 503 `AML.SCREENING_UNAVAILABLE`(HTTP 상태코드 정본=API 명세)
- [BE] PII는 hash/token 기반 매칭, 원문 미저장
- [BO] WLF 검토 큐 화면 데이터(POSSIBLE_MATCH/ESCALATED)는 T-10에서 노출

## 참조
- `docs/design/api/02-aml-api.md` §2.2, §3.2(ScreenRequest/ScreenResponse), §4
- `docs/design/db/02-aml-db.md` §3.8, §5.5(screening_status)
- `docs/design/integration/02-aml-integration.md` §5.2(실시간 WLF + fail 정책)
- `docs/software/02-amlSvc-sass.md` §10

## 변경 이력
| 일자 | 변경 |
|---|---|
| 2026-06-08 | #55 헤더에 BO 화면 소유 경계(T-10) 1줄 명시. |
