# BOA-S1 · AML 기반 추가 (BOF-S1 공통 기반 위)

> **목표**: 공통 기반(BOF-S1 — 스캐폴딩·인증·레이아웃·프록시·i18n)은 그대로 공유하고, **AML 콘솔 고유의 컴플라이언스 가드**만 추가한다.
> **선행**: `docs/tasks/bo-fds/01-stage1-foundation.md`(BOF-S1) 전체.

## 공통 참고 문서
- AML PRD `docs/plan/02-aml-sass-functional-spec.md` §1.3(운영 주체·PII 마스킹)·§1.4(scope 13종)·부록 B(권한+tipping-off 경계)·부록 D(에러)·부록 F(표시 사전)·부록 G(결재 라인)
- AML API `docs/design/api/02-aml-api.md` §1(인증·테넌시·scope)·§4(HTTP 상태)·§9(bo-api 소유 경계)
- 설계서 `docs/software/02-amlSvc-sass.md` §19.2a(tipping-off)·§13(4-eyes)

## 태스크

| ID | 구분 | 태스크 | 참고 문서 | Effort | 의존 |
|---|---|---|---|---|---|
| BOA-S1-01 | BE | **AML scope 권한 모델** — `aml:case:read/update`·`aml:admin:{watchlist,policy,approval,audit,source-system}`·`aml:evidence:export`·`aml:pii:reveal` 13종을 Role↔화면 매트릭스(부록 B)로 평가, **STR 전담 role(COMPLIANCE) 분리** | PRD §1.4·부록 B / API §1.1(확정 scope) | 3 | BOF-S1-02 |
| BOA-S1-02 | BE | **PII reveal 게이트** — 원문 열람 요청 시 사유 입력 필수 → 엔진 위임 → `RAW_DATA_ACCESS` 감사(`aml_audit_events`) 기록, 응답 마스킹 해제는 해당 요청 한정 | PRD §1.3(PII 마스킹 원칙) / API §1.6 / DB `02-aml-db.md` §2.2 | 3 | BOA-S1-01 |
| BOA-S1-03 | FE | **tipping-off 렌더 가드** — STR 관련 메뉴·라우트·검색·딥링크·플래그·건수를 전담 role 외 **컴포넌트 트리에서 제거**(숨김 아님), STR 화면 상시 경고 배너 컴포넌트("외부 누설은 특정금융정보법 제4조의2 위반") | PRD 부록 B 하단(tipping-off 경계)·§12-A.8(경고 배너) / 설계서 §19.2a | 3 | BOA-S1-01 |
| BOA-S1-04 | FE | **PII 마스킹·열람 UI** — 마스킹 셀 공통 컴포넌트(`cust_…501` 토큰 표시) + `[원문 열람]`(사유 모달→reveal 게이트 호출→감사 안내) | PRD §1.3 / BOA-S1-02 API | 2 | S1-02 |
| BOA-S1-05 | FE | **AML NAV·표시 사전** — NAV 15그룹(대시보드~감사·증적, ING는 감사·증적 그룹) 라우팅 + 부록 F 전수 i18n 키(screening/alert/case/report/approval/배포·온보딩/인입 신호 ●⚠✕ 등)·부록 G 결재 라인 표시 | PPT 전 슬라이드 NAV / PRD 부록 F·G | 2 | BOF-S1-09 |
| BOA-S1-06 | BE | **AML 에러 매핑** — `AML.*` 코드→HTTP(409 멱등/자기승인/payload 변경/전이 위반·422 검토요구·429·503 fail-closed)→화면 처리 규약 미들웨어 | PRD 부록 D / API §4 | 2 | BOF-S1-04 |

## DoD
- 비전담 계정으로 로그인 시 STR 메뉴·검색 결과·건수가 DOM에 존재하지 않음(렌더 가드 테스트).
- 원문 열람 1회가 사유와 함께 감사 로그에 남음. `AML.SELF_APPROVAL_FORBIDDEN` 등 에러가 부록 D 규약대로 표시.
