# BOF-S4 · 룰 라이프사이클·효과성·그룹 명단 (SFDS-RULE-001~006 · SFDS-STAT-001 · SFDS-GRP-001~003)

> **목표**: 룰의 전체 폐루프(목록→상세→빌더→임계 변경→결재/활성화→시뮬레이션→**효과성 평가**)와 그룹·명단 운영 완성.
> **선행**: BOF-S1·S3(피처 카탈로그·스키마). **PPT**: 슬라이드 19~33.

## 공통 참고 문서
- PRD §6.1~§6.7(룰·효과성), §7.1~§7.3(그룹) / §1.5(룰 상태머신 `DRAFT/PENDING_APPROVAL/ACTIVE/DISABLED/ARCHIVED`)
- API `01-fds-api.md`: rules CRUD·`/rules/{id}/activate`🔒·`/rollback`🔒·`/disable`·`/rules/simulations`·feature-catalog·risk-groups(±members)
- DB `01-fds-db.md`: `rule_status`(§4.13)·`channel_type` 19종(§4.4)·`decision` 8종(§4.7)·`risk_group_type`·`member_kind` 3종·`close_reason` 8종(§4.11)
- 문장형 룰 빌더 7단계(①대상~⑦탐지 시 동작)·DSL 토글: PRD §6.3 / 설계서 §9(룰엔진·feature catalog)

## 태스크

| ID | 구분 | 태스크 | 참고 문서 | Effort | 의존 |
|---|---|---|---|---|---|
| BOF-S4-01 | BE | **룰 프록시** — rules 목록/상세/버전·feature-catalog·`POST /rules`·`PUT /rules/{id}`(임계 포함)·`activate`🔒·`rollback`🔒·`disable`·simulations 위임 + 감사 | API(rules·simulations) / PRD §6.1~§6.6 | 3 | S1-04 |
| BOF-S4-02 | FE | **SFDS-RULE-001 룰 목록** — 필터 5축·**효과성 요약 컬럼(30일 탐지/오탐 %·튜닝 ⚠)**·`[효과성 ▶ → STAT-001]`·fail-closed 배지·비활성 ⚠ 툴팁 | PRD §6.1(BR-006) / PPT 슬라이드 19 | 2 | S4-01 |
| BOF-S4-03 | FE | **SFDS-RULE-002 룰 상세 5탭** — 현재버전 조건(자연어)/버전 히스토리(비교)/기준값/최근 Hit/결재 로그 — 같은 탭 바 연속 | PRD §6.2 / PPT 슬라이드 20~24 | 4 | S4-01 |
| BOF-S4-04 | FE | **SFDS-RULE-003 룰 빌더** — 문장형 7단계(①대상 ②측정 ③기간 ④집계 ⑤기준값 ⑥추가조건 AND/OR ⑦탐지 시 동작)·자연어 미리보기·DSL 토글·`FDS-VALIDATION-002`(도메인 불일치 측정) 인라인 | PRD §6.3(빌더 정본 순서) / PPT 슬라이드 25 / 설계서 §9(feature catalog) / S1-07 `ConditionBuilder` | 5 | S4-01 |
| BOF-S4-05 | FE | **SFDS-RULE-004 임계치 빠른 변경(Hot-reload)** — 임계값만 단건 변경·변경 사유 필수·결재 상신 | PRD §6.4 / PPT 슬라이드 26 | 2 | S4-01 |
| BOF-S4-06 | FE | **SFDS-RULE-005 결재·활성화·롤백·중지** — 라이프사이클 액션(활성화 상신🔒·롤백🔒·중지)·즉시 평가 룰은 시뮬레이션 첨부 필수 가드 | PRD §6.5(BR-001) / PPT 슬라이드 27 / §1.5 상태머신 | 3 | S4-01 |
| BOF-S4-07 | FE | **SFDS-RULE-006 룰 시뮬레이션(백테스트)** — 대상(미저장 ruleJson/기존 룰)·기간(sampleWindow)·결과 KPI(Hit·차단 영향·추정 오탐·평가 건수)·샘플 Hit·권고·`[결과 첨부 결재 상신]` | PRD §6.6 / PPT 슬라이드 28 / API(simulations) | 3 | S4-01 |
| BOF-S4-08 | **SPEC** | **효과성 통계 API 명세 확정(선행)** — `GET /api/v1/bo/fds/stats/rules`·`/stats/false-positives` 응답(룰별 퍼널·전월 대비·튜닝 권고 기준, FP_* 3종 집계) 확정 → API 문서 반영 | PRD v4.0 변경 이력 ①(오픈결정) / PRD §6.7 | 2 | — |
| BOF-S4-09 | BE | **효과성 통계 집계 구현** — `/bo/fds/stats/rules`(평가→탐지→차단/보류→케이스 전환율)·`/stats/false-positives`(케이스 종결 `close_reason FP_*` 누적) | BOF-S4-08 / PRD §6.7 BR-001~003 / DB §4.11(close_reason) / PRD §11.2 BR-002(오탐 피드백 폐루프) | 4 | S4-08·S1-05 |
| BOF-S4-10 | FE | **SFDS-STAT-001 룰 효과성 2탭** — ①룰 효과성(KPI+룰별 표·행▶ RULE-002·`[백테스트]`→RULE-006) ②오탐 피드백 분석(FP 3종 카드·룰별 추이·튜닝 후보→RULE-004/003) | PRD §6.7 / PPT 슬라이드 29~30 | 3 | S4-09 |
| BOF-S4-11 | BE | **그룹·명단 프록시** — risk-groups CRUD·members `POST`🔒/`DELETE`🔒(CSV 일괄·만료·연장) 위임 | API(risk-groups) / PRD §7.1~§7.3 / DB(`member_kind` 3종 환원 매핑) | 2 | S1-04 |
| BOF-S4-12 | FE | **SFDS-GRP-001/002/003** — 그룹 목록/멤버 조회(만료 임박 7일 하이라이트)·멤버 추가/해제/연장(CSV 업로드 미리보기→확정·사유 필수·4-eyes)·그룹 등록(종류 9종 표시·`groupType` 6종·읽기 전용 필드 4종 구분) | PRD §7.1~§7.3(BR 전수) / PPT 슬라이드 31~33 | 4 | S4-11 |

## DoD
- 룰 폐루프 E2E: 빌더 작성→시뮬레이션 첨부→결재 상신→(S6 결재함 승인)→ACTIVE→효과성 통계에 반영.
- 효과성 ⚠ 튜닝 후보가 RULE-004/006으로 액션 연결. CSV 멤버 일괄 등록 dedup·결과 리포트 동작.
- BOF-S4-08 확정 전 S4-09/10 착수 금지.
