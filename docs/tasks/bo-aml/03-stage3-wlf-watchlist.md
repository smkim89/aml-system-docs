# BOA-S3 · WLF 검토·명단 운영 (AML-WLF-001~004 · AML-WL-001/002/003)

> **목표**: 요주의 명단 필터링의 전 흐름 — 검토 큐→판정(4-eyes)→상위승인→처리 이력→시뮬레이션/임의 수행, 명단 소스→임포트 디프 승인→내부 명단·오탐 면제 생명주기.
> **선행**: BOA-S1. **PPT**: 슬라이드 10~20.

## 공통 참고 문서
- PRD §3.1~§3.3(WLF 3탭 흐름·상태머신 §1.7)·§12-B.1(WLF-004)·§4.1(WL-001)·§12-A.2(WL-002)·§12-B.5(WL-003)
- API `02-aml-api.md`: `GET .../screenings?status=`·`GET .../screenings/{id}`·`POST .../screenings/{id}/decision`🔒(`WLF_DECISION`)·`POST .../screenings/fp-whitelist`🔒(`FP_WHITELIST`)·approvals `:approve/:reject`·watchlist-sources/imports/`{ver}:apply`🔒(`WATCHLIST_IMPORT`)·watchlist-entries
- DB `02-aml-db.md`: `screening_status` §5.5(POSSIBLE_MATCH→…→NO_MATCH)·명단 테이블 §3.x / 표시 = PRD 부록 F
- WLF 임계(0.66/0.92)·룰버전 = 정책팩 파라미터(읽기 전용 — PRD §3.1 BR-009)

## 태스크

| ID | 구분 | 태스크 | 참고 문서 | Effort | 의존 |
|---|---|---|---|---|---|
| BOA-S3-01 | BE | **스크리닝·판정 프록시** — screenings 목록(status별)/상세·`decision` 상신🔒·fp-whitelist 등록🔒·approvals 승인/반려 위임 + 감사 | API(스크리닝·결재) / PRD §3.1~§3.3 BR 전수 | 3 | S1 |
| BOA-S3-02 | FE | **AML-WLF-001 ① 검토 필요** — 큐 목록 + 하단 master-detail 3탭(매칭 후보·근거/점수 분해/이전 판정 이력) + 판정 드롭다운 4종(확정/오탐/자동낮춤/상위승인 상신)·`[오탐 면제 등록(2인)]`·상단 `[시뮬레이션]`→WLF-004 | PRD §3.1(BR-001~010) / PPT 슬라이드 10 | 4 | S3-01 |
| BOA-S3-03 | FE | **AML-WLF-002 ② 상위 승인** — ESCALATED 큐·[심사] 패널(상신 판정·이전 이력)·승인(2인)→확정+케이스 생성 / 반려→① 회신 | PRD §3.2(BR-001~006) / PPT 슬라이드 11 | 3 | S3-01 |
| BOA-S3-04 | FE | **AML-WLF-003 ③ 처리 이력** — 5카드(확정·오탐·자동낮춤·면제·평균 SLA)·이력 표(판정자/승인자)·`[면제 현황 ▶ → AML-WL-003 ②]`·읽기 전용 | PRD §3.3(BR-001~006) / PPT 슬라이드 12 | 2 | S3-01 |
| BOA-S3-05 | **SPEC** | **시뮬레이션·임의 수행 API 명세 확정(선행)** — `POST .../screenings:simulate`(분석 전용)·`:bulk-run`(POSSIBLE_MATCH 생성·rate limit·감사 카테고리) 확정 → API 문서 반영 | PRD 부록 E v6.0-1(오픈결정)·§12-B.1 | 2 | — |
| BOA-S3-06 | BE | **시뮬레이션·임의 수행 프록시** — simulate(결재 불필요)·bulk-run(파일 업로드→토큰화 즉시·원문 미보존 D-05·429) 위임 | BOA-S3-05 확정 명세 / PRD §12-B.1 BR-001~003 | 3 | S3-05 |
| BOA-S3-07 | FE | **AML-WLF-004 2탭** — ①단건 시뮬레이션(이름·한글→영문 변환·유사도 임계 조정·매칭 근거 분해) ②임의 수행(템플릿 다운로드→업로드→일괄 수행→이력·검출▶WLF-001 필터) | PRD §12-B.1 / PPT 슬라이드 13~14 | 3 | S3-06 |
| BOA-S3-08 | BE | **명단 소스·임포트 프록시** — watchlist-sources CRUD·imports(diff 생성)·`{ver}:apply`🔒·watchlist-entries(masked) 위임 | API(watchlist) / PRD §4.1(BR-001~007)·§12-A.2 | 2 | S1 |
| BOA-S3-09 | FE | **AML-WL-001 3탭** — ①소스 목록(신선도·`[시뮬레이션]`→WLF-004) ②임포트 이력(검토대기▶WL-002) ③명단 엔트리 조회(토큰 hash·원문 reveal) | PRD §4.1(BR-007 트리거 포함) / PPT 슬라이드 15~17 | 3 | S3-08 |
| BOA-S3-10 | FE | **AML-WL-002 디프 승인** — 변경분 요약/검증 게이트(급증·서명·checksum)·디프 표(추가/변경/삭제)·`[적용 상신(2인)]`→승인 시 활성 버전 승격+재스크리닝 안내 | PRD §12-A.2 / PPT 슬라이드 18 | 3 | S3-08 |
| BOA-S3-11 | **SPEC** | **내부 명단·면제 생명주기 API 명세 확정(선행)** — `entries:draft`(수기→diff 초안)·`GET .../screenings/fp-whitelist`·`:revoke`🔒·만료 자동 전이 경로 확정 → API 문서 반영 | PRD 부록 E v7.0-1(오픈결정)·§12-B.5 | 2 | — |
| BOA-S3-12 | BE | **내부 명단·면제 프록시** — entries:draft(WL-002 apply 재사용)·fp-whitelist 목록·revoke🔒 위임 | BOA-S3-11 / PRD §12-B.5 BR-001~003 | 2 | S3-11 |
| BOA-S3-13 | FE | **AML-WL-003 2탭** — ①내부 요주의 명단(수기 등록 폼→diff 초안→WL-002 4-eyes·발효일) ②오탐 면제 관리(4카드·활성/만료/해제 생명주기·`[면제 해제(2인)]`·만료 D-7 ⚠) | PRD §12-B.5 / PPT 슬라이드 19~20 | 3 | S3-12 |

## DoD
- WLF 상태머신(§1.7) 전이 전수 E2E: 검토→상신→상위승인/반려 회신→처리 이력, 확정 시 케이스 생성 링크.
- 임의 수행 검출 건이 ① 검토 필요 큐에 유입. 면제 만료/해제 → 재스크리닝 순환 안내 표시.
- `SPEC` 2건(S3-05·S3-11) 확정 전 해당 BE/FE 착수 금지. 판정·면제·임포트 적용 전부 결재함(S6)에 수렴.
