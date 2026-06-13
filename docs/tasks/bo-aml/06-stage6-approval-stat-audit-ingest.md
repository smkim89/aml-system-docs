# BOA-S6 · 정책팩·결재·통계·내부통제·감사·인입 모니터링 (AML-PP-001 · AML-APR-001 · AML-STAT-001 · AML-EDU-001 · AML-AUD-001 · AML-ING-001)

> **목표**: 전 Stage 4-eyes 상신의 수렴(결재 대기함), 정책팩 거버넌스, 효과성·내부통제 통계, 감사·증적, 데이터 인입 가시성 완성 → **AML 콘솔 32화면 전수 개통**.
> **선행**: BOA-S1 (S2~S5 상신의 수렴점). **PPT**: 슬라이드 59~70.

## 공통 참고 문서
- PRD §12-A.9(PP)·§11.1(APR — subjectType 16종·상태 7종)·§12-B.3(STAT)·§12-B.4(EDU)·§12.1(AUD)·§12.2+§1.11(ING)
- API `02-aml-api.md`: policy-packs`:change`🔒·approvals(`:approve/:reject`)·`GET /bo/aml/audit`(bo-api 소유)·`POST /evidence/aml/exports`·source-systems🔒(`SECRET_CHANGE`)·audit-events(저수준)
- 결재: 부록 C(subjectType↔화면↔API 전수)·부록 G(결재 라인 표시)·상태머신 §1.7 / 큐·인입: integration `02-aml-integration.md` §2.1(큐 카탈로그)

## 태스크

| ID | 구분 | 태스크 | 참고 문서 | Effort | 의존 |
|---|---|---|---|---|---|
| BOA-S6-01 | BE | **정책팩 프록시** — `policy-packs:change`🔒·tenant `policyPackCode` 파생 조회 | API §2.7 / PRD §12-A.9(BR-001~004 — 기본 번들 잠금/확장 plugin) | 2 | S1 |
| BOA-S6-02 | FE | **AML-PP-001 2탭** — ①적용 팩/기준금액(기본 KR_DEFAULT 잠금+확장 plugin·CTR/STR/TR 임계·effective v12) ②변경 상신·이력(4-eyes) | PRD §12-A.9 / PPT 슬라이드 59~60 | 3 | S6-01 |
| BOA-S6-03 | BE | **결재 프록시** — approvals 목록(subjectType 16종)/상세(payload·hash)·`:approve`🔒/`:reject` 위임, 자기승인 409·payload 변경 무효화 표면화 | API §3.7(16종)·§4 / PRD §11.1·부록 C | 3 | S1 |
| BOA-S6-04 | FE | **AML-APR-001 결재 대기함** — 필터 탭(대기/내가 상신/처리 완료·1슬라이드)·종류 16종 배지·결재 라인(부록 G)·[승인(2인)]/[반려(사유)]·만료 임박 ⚠ | PRD §11.1 / PPT 슬라이드 61 / 부록 D(409 계열) | 4 | S6-03 |
| BOA-S6-05 | **SPEC** | **통계 API 명세 확정(선행)** — `GET /bo/aml/stats/str`·`/stats/scenarios`(퍼널·지연 일수·미보고 사유·전환율·튜닝 기준) 확정 | PRD 부록 E v6.0-3·§12-B.3 | 2 | — |
| BOA-S6-06 | BE+FE | **AML-STAT-001 2탭** — BE: bo-api 집계 구현 / FE: ①STR 보고 퍼널·지연 분포·미보고 사유(전담 한정) ②룰 효과성(행▶ TM-002) | BOA-S6-05 / PRD §12-B.3 BR-001~003 / PPT 슬라이드 62~63 | 4 | S6-05 |
| BOA-S6-07 | **SPEC** | **교육·자격 API 명세 확정(선행)** — training/courses·records·certifications(bo-api 소유·IAM 연계·IRA 자동 수집 매핑) 확정 | PRD 부록 E v6.0-4·§12-B.4 | 2 | — |
| BOA-S6-08 | BE+FE | **AML-EDU-001 2탭** — BE: bo-api 소유 CRUD·스냅샷 / FE: ①교육 과정·이수 현황(미이수자·직전 1년 프리셋) ②자격 보유 매트릭스(템플릿 업로드) | BOA-S6-07 / PRD §12-B.4 BR-001~003 / PPT 슬라이드 64~65 | 4 | S6-07 |
| BOA-S6-09 | BE | **감사·증적·소스 API** — 감사 집계 `GET /bo/aml/audit`(bo-api 소유) + 엔진 위임(evidence exports·source-systems 등록/secret🔒) | API §9·§2.x / PRD §12.1(BR — 보존 5년/7년 표기) | 3 | S1 |
| BOA-S6-10 | FE | **AML-AUD-001 3탭** — ①감사 로그(카테고리·작업자·traceId) ②증적 Export(manifest hash·다운로드) ③소스 시스템(등록·인증 모드·장애 정책 D-14·secret 변경🔒) | PRD §12.1 / PPT 슬라이드 66~68 | 3 | S6-09 |
| BOA-S6-11 | **SPEC** | **인입 집계 API 명세 확정(선행)** — `GET /bo/aml/ingest/catalog`·`/ingest/health`(게이트웨이 호출량·큐 depth/lag/DLQ·폴링 커서·백필 %·신호 임계 외부화) 확정 | PRD 부록 E v8.0-1·2(오픈결정)·§1.11·§12.2 | 2 | — |
| BOA-S6-12 | BE | **인입 집계 구현** — catalog(수신 API 4종 호출량)·health(소스×모드 6종 라이브 — `aml-ingest`(+`.fifo`)·DLQ·폴링·백필) | BOA-S6-11 / integration §2.1(큐 카탈로그 정본) / PRD §1.11 ①~③ | 4 | S6-11 |
| BOA-S6-13 | FE | **AML-ING-001 2탭** — ①수신 API 카탈로그(4종 표) + **연동 방식×표시 신호 확정표(6종) 상시 표시** ②인입 라이브(KPI 4카드·소스×모드 표·⚠/✕→DASH 알림 동일 소스·행▶ AUD-001 ③) | PRD §12.2(BR-001~003)·§1.11 / PPT 슬라이드 69~70 | 3 | S6-12 |

## DoD
- S3(WLF 판정·면제·임포트)·S4(모델 활성화·override·정책)·S5(케이스 종결·보고 제출·TR 예외)·S6(정책팩·secret) 상신 **subjectType 16종 전수가 결재 대기함에서 승인/반려**되고 상태머신(§1.7) 전이 일치 — 통합 E2E.
- ING-001 신호가 TNT-002 ③·DASH 소스 신선도와 동일 값(같은 health 소스). STR 통계는 비전담 미노출.
- **AML 콘솔 32화면 전수 개통** — PRD 부록 A 매핑표 기준 누락 0건 체크리스트 통과. `SPEC` 3건 확정 전 해당 구현 착수 금지.
