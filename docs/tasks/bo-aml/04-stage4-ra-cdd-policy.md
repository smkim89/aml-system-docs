# BOA-S4 · 위험평가·CDD·정책 앞단 (AML-CTRY-001 · AML-RA-001/002/003 · AML-CDD-001/002 · AML-HRR-001)

> **목표**: RA 모니터링→대상 상세→고객 프로필 원장→모델 관리(시뮬레이션·활성화·override)→당연고위험 레지스트리→CDD 정책의 자기완결 흐름.
> **선행**: BOA-S1 (S3 권장 — WLF 연계 factor 표시). **PPT**: 슬라이드 21~38. **화면 순서 = PPT 순서**(RA-001→RA-003→CDD-002→RA-002→HRR→CDD-001).

## 공통 참고 문서
- PRD §5.1(RA-001)·§6.1(RA-002)·§12-A.3(CTRY)·§12-A.4(RA-003)·§12-A.5(CDD-001)·§12-B.6(HRR)·§12-B.7(CDD-002)
- API `02-aml-api.md`: `country-risk`·`:change`🔒(`COUNTRY_RISK`)·`ra-models`·`/{code}/simulate`·`versions/{v}:activate`🔒(`RA_MODEL`)·`risk-scores/{id}/override`🔒(`RISK_OVERRIDE`)·`/aml/customers/{ref}/risk`(+history·relationships)·cdd/checklists🔒(`CHECKLIST_CHANGE`)·periodic-review-policy🔒(`PERIODIC_REVIEW_CHANGE`)·cases(EDD 착수)
- 분포 집계는 bo-api `GET /bo/aml/dashboard` 재사용(엔진 집계 미신설 — PRD §5.1 API 주석 정본)
- 문장형 factor 빌더·시뮬레이션 분리 원칙(모니터링≠저작): PRD §5.1 BR-001·§6.1

## 태스크

| ID | 구분 | 태스크 | 참고 문서 | Effort | 의존 |
|---|---|---|---|---|---|
| BOA-S4-01 | BE | **국가위험 프록시** — `GET country-risk`·`POST :change`🔒 위임 | API / PRD §12-A.3 | 2 | S1 |
| BOA-S4-02 | FE | **AML-CTRY-001 2탭** — ①등급표(낮음~거래금지 + **근거 소스 분해**: FATF 고위험/이행취약·UN/OFAC/EU·CPI — 정책팩 KR 파생 표시) ②변경 상신·이력(4-eyes) | PRD §12-A.3(v6.0 보강 포함) / PPT 슬라이드 21~22 | 3 | S4-01 |
| BOA-S4-03 | BE | **RA 조회 프록시·분포 집계** — ra-models·customers/{ref}/risk(+history)·분포는 bo-api dashboard 집계 확장 | PRD §5.1(API 소유 주석) / API §9 | 3 | S1 |
| BOA-S4-04 | FE | **AML-RA-001 2탭(모니터링)** — ①점수 분포(모델 버전 필터) ②고위험 목록(행▶ RA-003)·재심사 임박 ⚠ — 등급 변경 동작 없음(순수 모니터링) | PRD §5.1(BR-001~005) / PPT 슬라이드 23~24 | 3 | S4-03 |
| BOA-S4-05 | FE | **AML-RA-003 3탭(드릴다운)** — ①factor breakdown(+당연고위험 사유 별도 표기·EDD 체크리스트 실행·`[EDD 케이스 착수]`→CASE-002·`[고객 프로필 ▶]`→CDD-002) ②관계·UBO(마스킹·reveal) ③재심사 이력 | PRD §12-A.4(BR-001~003) / PPT 슬라이드 25~27 | 4 | S4-03 |
| BOA-S4-06 | **SPEC** | **고객 프로필 API 명세 확정(선행)** — `GET /aml/customers/{ref}/profile`(개인/법인 분기·마스킹·STR 건수 전담 한정) 확정 → API 문서 반영 | PRD 부록 E v7.0-3·§12-B.7 | 2 | — |
| BOA-S4-07 | BE | **고객 프로필 프록시** — profile read-only 위임(+활동 요약 파생 집계) | BOA-S4-06 / PRD §12-B.7 BR-001~003 | 3 | S4-06 |
| BOA-S4-08 | FE | **AML-CDD-002 2탭(read-only 원장)** — ①CDD 프로필(공통·신원확인/개인·법인 분기·편집 불가) ②위험·활동 요약(RA 카드·당연고위험 사유·케이스/스크리닝/STR[전담] 카드·관계 요약) + 진입 배너(RA-003 ①/CASE-002 ①/WLF-001) | PRD §12-B.7 / PPT 슬라이드 28~29 / tipping-off 가드(BOA-S1-03) | 3 | S4-07 |
| BOA-S4-09 | BE | **RA 모델 관리 프록시** — simulate(결재 불필요)·activate🔒·override🔒(하향) 위임 | API / PRD §6.1(BR-001~005) | 2 | S1 |
| BOA-S4-10 | FE | **AML-RA-002 4탭(모델 저작)** — ①버전 목록 ②factor 편집(문장형 빌더·가중치) ③시뮬레이션(초안 검증·등급 이동 delta·진입 배너=② [시뮬레이션]) ④등급 조정 이력(RISK_OVERRIDE 하향 4-eyes) | PRD §6.1 / PPT 슬라이드 30~33 / S1-07 `ConditionBuilder` | 5 | S4-09 |
| BOA-S4-11 | **SPEC** | **당연고위험 레지스트리 명세 확정(선행)** — `GET/PUT high-risk-registry`·subjectType `HIGH_RISK_REGISTRY`·RA 등급 강제 상향 결합 지점·재평가 방식 확정 → API·DB 반영 | PRD 부록 E v7.0-2·§12-B.6 | 2 | — |
| BOA-S4-12 | BE | **레지스트리 프록시** — 분류 기준 조회·참조 리스트(상품/VASP/고액자산가) PUT🔒 위임 | BOA-S4-11 / PRD §12-B.6 BR-001~003 | 2 | S4-11 |
| BOA-S4-13 | FE | **AML-HRR-001 2탭** — ①분류 기준(당연고위험/당연초고위험 팩터→코드 상세, 국가=CTRY 파생) ②참조 리스트(상품·VASP·고액자산가 기준·템플릿 업로드·변경 상신 2인) | PRD §12-B.6 / PPT 슬라이드 34~35 | 3 | S4-12 |
| BOA-S4-14 | BE | **CDD 정책 프록시** — checklists CRUD·PUT🔒·periodic-review-policy PUT🔒 위임 | API / PRD §12-A.5 | 2 | S1 |
| BOA-S4-15 | FE | **AML-CDD-001 3탭** — ①체크리스트 정의(항목·필수·증빙·트리거 — 업무 용어) ②재심사 주기(등급별 개월·유예) ③변경 이력 — 변경 4-eyes 2종 | PRD §12-A.5(BR-001·002) / PPT 슬라이드 36~38 | 3 | S4-14 |

## DoD
- RA 흐름 E2E: 분포→고위험 행▶ 대상 상세→[고객 프로필]→[EDD 착수]→케이스(S5) / 모델 ② 편집→③ 시뮬레이션→활성화 상신(S6 승인).
- 당연고위험 사유가 RA-003 ①·CDD-002 ②에 동일 파생 표기. 시뮬레이션은 결재 불필요·등급 무변경 확인.
- `SPEC` 2건(S4-06·S4-11) 확정 전 해당 구현 착수 금지.
