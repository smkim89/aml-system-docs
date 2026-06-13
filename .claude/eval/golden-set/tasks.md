---
artifact: tasks
target: docs/tasks/<svc>/ + docs/tasks/aegis-aml/
version: 1
owner: task-planner
---

# 골든셋 — 개발 태스크(WBS+로드맵) (예/아니오, 각 1점)

1. 서비스 WBS 태스크가 **목표·구현항목·참조섹션·Effort·의존·Status**로 분해되는가?
2. 프로그램 로드맵 Phase(P0~P8) 태스크가 **ID·서비스·구분·Effort·의존·DoD·Status**로 명세되는가?
3. 서비스 WBS ↔ 로드맵 Phase **매핑·의존**이 정합하는가?
4. enum·엔드포인트·식별자가 설계/DB/API/연동과 **1:1**인가?
5. 의존 그래프에 순환 없음·선행 조건이 명시되는가?
6. 변경 이력이 기능/설계 변경과 동기화되는가?
