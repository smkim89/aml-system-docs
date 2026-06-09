---
name: task-planning
description: SaaS AML/FDS 플랫폼의 개발 태스크를 ① 서비스 WBS(docs/tasks/<svc>/)와 ② 프로그램 로드맵(docs/tasks/aegis-aml/ P0~P8)으로 작성·동기화할 때 사용. 설계·DB·API·연동·PRD를 입력으로 태스크 분해·Effort·의존·DoD·Status + 2층 정합 규칙과 절차를 담는다. "개발 태스크 분해", "WBS 작성", "로드맵 갱신", "태스크 동기화" 요청 시 트리거.
---

# Task Planning (개발 태스크 — 2층 동기화)

## 0. 정본·입력
- 입력: `docs/software`(설계) + `docs/design/db·api·integration` + `docs/plan`(PRD).
- 정본: `_shared/target-architecture.md` **§5(2층 매핑)**. 구현 패키지 `com.aegis.*`. 확정된 설계 범위만 태스크화.

## 1. 서비스 WBS (`docs/tasks/<svc>/`)
1. `00-overview.md`: 태스크 표(ID·제목·서비스·Effort·의존·Due·Status) + 의존 그래프.
2. 번호별 `NN-*.md`: 목표 / 구현 항목 / 참조(예: `docs/design/api/01-fds-api.md §3`) / Status.
3. 구분: 백오피스 대상(BO CRUD·임계치·감사·시뮬레이션)과 백엔드 전용(SQS·스케줄러).

## 2. 프로그램 로드맵 (`docs/tasks/aegis-aml/`)
1. `00-program-overview.md`: P0~P8 단계·서비스↔Phase 매핑·교차연동·마일스톤·횡단 불변식.
2. `0N-phaseN-*.md`: Phase별 태스크 표(ID 접두 `P{n}-{FDS|AML|BOAPI|WEB|INFRA}-NN`·서비스·구분·Effort·의존·**DoD**·Status) + Mermaid 의존 그래프. 엔진은 서비스 WBS T-ID 참조, bo-api/bo-web/공통은 신규.

## 3. 동기화 (핵심)
설계/기능 변경 시 **서비스 WBS ↔ 프로그램 로드맵 Phase ↔ 설계 정본**을 함께 갱신. 새 기능 → 해당 서비스 WBS 태스크 추가 + 영향 Phase 태스크 추가/갱신 + 변경 이력. 한쪽만 변경 금지. DoD = 하네스 QA 게이트(빌드·테스트·lint·리뷰 높음 0·정본 정합).

## 4. 산출
서비스 WBS + 프로그램 로드맵(정합). doc-consistency-qa가 둘의 정합을 검증. Effort는 글로벌 `effort-level-guide` 참고.
