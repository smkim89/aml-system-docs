# BOF-S5 · 결정·이벤트·액션·케이스 (SFDS-DEC-001~003 · SFDS-EVT-001 · SFDS-ACT-001/002 · SFDS-CASE-001/002)

> **목표**: 탐지 결과의 조사 흐름(결정→근거→Subject 타임라인→액션→케이스→종결/재오픈) 완성.
> **선행**: BOF-S1·S4(룰 표시·효과성 피드백 연계). **PPT**: 슬라이드 34~44.

## 공통 참고 문서
- PRD §8(결정)·§9(이벤트)·§10(액션·Capability)·§11(케이스) / §1.6·§1.6.1(케이스·보고 상태머신 — 재오픈 포함)
- API `01-fds-api.md`: `GET /fds/decisions`·`/{decisionId}`·`GET /fds/events/{eventId}`·`GET /fds/actions/{actionId}`·cases CRUD(`PATCH`·`/assign`·`/close`🔒·`/feedback`)·`POST /fds/cases/{id}/actions`🔒·case timeline(`GET /fds/cases/{id}/events`·evidence timeline)
- DB `01-fds-db.md`: `decision` 8종·`case_status` 8종·`case_priority` 4종·`close_reason` 8종(§4.11)·`action_status`·ActionType 23종(API 정본)
- 액션 relay·아웃박스(BE 자동 재시도·운영자 버튼 없음): PRD §10.1 BR / integration §5(action outbox)

## 태스크

| ID | 구분 | 태스크 | 참고 문서 | Effort | 의존 |
|---|---|---|---|---|---|
| BOF-S5-01 | BE | **결정·이벤트 프록시** — decisions 목록/상세·events 상태/정규화 결과(마스킹) 위임 | API(decisions·events) / PRD §8.1·§8.2·§9.1 | 2 | S1-04 |
| BOF-S5-02 | FE | **SFDS-DEC-001 결정 목록** — 필터·`decision` 8종 표시·행▶ 상세, 핵심 플로우 콜아웃(결정→액션→케이스→결재→규제) | PRD §8.1 / PPT 슬라이드 34 | 2 | S5-01 |
| BOF-S5-03 | FE | **SFDS-DEC-002 결정 상세(판정 근거)** — 룰 hit·점수·feature 값 분해·후속 조치 딥링크 패널(그룹·액션·케이스·타임라인) | PRD §8.2 / PPT 슬라이드 35 | 3 | S5-01 |
| BOF-S5-04 | FE | **SFDS-DEC-003 Subject 타임라인(조사)** — 대상 식별자 기준 시간순(결정·액션·명단 자동등록·케이스) + 진입 배너(DEC-001/002에서) | PRD §8.3 / PPT 슬라이드 36 / API(evidence timeline) | 3 | S5-01 |
| BOF-S5-05 | FE | **SFDS-EVT-001 이벤트 조회** — eventId 단건 조회·정규화 결과·`payload_hash`(raw 미저장 D-06 표시) | PRD §9.1 / PPT 슬라이드 37 / 설계서(raw payload 미저장) | 2 | S5-01 |
| BOF-S5-06 | BE | **액션·Capability 프록시** — `GET /fds/actions/{actionId}`·source-systems Capability(`PUT` 4-eyes 상신) 위임 | API / PRD §10.1·§10.2 | 2 | S1-04 |
| BOF-S5-07 | FE | **SFDS-ACT-001 액션 큐/아웃박스** — `action_status` 표시(발행/승인됨🔒/대기/실패⚠)·`[상태 조회]`(수동 재시도 버튼 없음 — BE 아웃박스 소관)·조치 종류 23종 표시 | PRD §10.1(BR — relay BE 자동 재시도 정본) / PPT 슬라이드 38 | 2 | S5-06 |
| BOF-S5-08 | FE | **SFDS-ACT-002 Capability 매트릭스** — 소스 시스템×조치 가능(`control_capability`)·케이스 전용(CAN_OPEN_CASE_ONLY)·변경 4-eyes 상신 | PRD §10.2 / PPT 슬라이드 39 | 2 | S5-06 |
| BOF-S5-09 | BE | **케이스 프록시** — cases 목록/상세·`PATCH`(상태·재오픈 `{status: IN_REVIEW, reason}`)·`/assign`·`/close`🔒(종결 사유 코드 8종)·`/feedback`·`POST .../actions`🔒·timeline 위임 | API §5.5·§5.6 / PRD §11.1·§11.2(BR-006 재오픈·BR-007 종결 사유) | 3 | S1-04 |
| BOF-S5-10 | FE | **SFDS-CASE-001 케이스 목록** — `case_status` 8종·우선순위 4종·SLA·`[+ 케이스]`·행▶ 상세 | PRD §11.1 / PPT 슬라이드 40 | 2 | S5-09 |
| BOF-S5-11 | FE | **SFDS-CASE-002 케이스 상세 4탭** — 개요/타임라인(append-only)/결정 연결/코멘트 + 종결 모달(**종결 사유 코드 필수 드롭다운 8종 + 상세 메모 분리**)·종결 상신🔒·**[재오픈]**(종결 상태에서만·사유 모달·자기 종결 건 금지)·`[규제 보고 전환 → REG-001]`·케이스 액션 상신🔒 | PRD §11.2(BR-001~007 전수)·§1.6.1(재오픈 전이) / PPT 슬라이드 41~44 | 5 | S5-09 |

## DoD
- 결정→케이스 개설→조사→종결 상신→(S6 승인) 종결→`FP_*` 종결이 효과성 통계(S4 STAT-001 ②)에 누적되는 폐루프 확인.
- 재오픈이 종결 상태에서만 노출·사유 필수·SLA 재기산. 액션 화면에 수동 재시도 버튼이 없음(BE 아웃박스 정본).
- 모든 드릴다운(목록→상세→타임라인)에 진입 배너·breadcrumb 유지.
