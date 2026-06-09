---
name: feature-docs-pipeline
description: 어떤 기능을 추가·변경하면서 프로젝트의 모든 문서를 한 번에 싱크 맞춰 생성/갱신할 때 사용하는 마스터 오케스트레이션. 설계서(software)→DB→API→연동→태스크→기능정의서(PRD)→백오피스 PPT를 순차 동기화하고 정합성 QA로 이격을 0까지 맞춘다. "<기능> 추가해줘/문서 만들어줘", "이 기능 전체 문서 작성", "기능 반영해서 설계~기획까지 싱크" 요청 시 트리거. PROACTIVELY 사용.
---

# 기능 문서 파이프라인 (전체 싱크)

기능 요청 하나로 **모든 문서를 의존 순서대로 동기화**한다.

## 실행
1. 입력 확정: **기능 설명(feature)** 과 **대상 서비스(service: fds|aml|…)**. service가 불명확하면 사용자에게 1회 확인.
2. 워크플로우 호출:
   `Workflow({ name: "feature-docs-pipeline", args: { feature: "<기능 설명>", service: "<svc>" } })`

## 파이프라인 (순차, 각 단계가 직전 변경점을 입력으로 동기화)
```
① 설계  system-architect      → docs/software/<svc>-sass.md
② DB    data-modeler          → docs/design/db/<svc>-db.md
③ API   api-designer          → docs/design/api/<svc>-api.md
④ 연동  integration-designer  → docs/design/integration/<svc>-integration.md
⑤ 태스크 task-planner          → docs/tasks/<svc>/*
⑥ 기획  backoffice-planner    → docs/plan/<svc>-functional-spec.md + BO PPT
⑦ QA    doc-consistency-qa    → docs/qa/ 리포트
⑧ 정합화 FAIL 시 담당 문서 수정 → 재QA (최대 2회), 잔존 이격은 보고
```

## 동기화 규칙
- 각 단계는 **상위 문서를 진실(source of truth)**로 삼아 명칭·필드·타입·enum·엔드포인트를 맞춘다.
- 직전 단계가 넘긴 `downstreamNotes`(신규 엔티티·필드·이벤트·화면)를 반드시 반영.
- 신규가 아니면 부분 갱신 + 변경 이력 기록.
- 종료 시 status(PASS/FAIL_RESIDUAL)·생성 문서·QA 리포트 경로를 보고.
