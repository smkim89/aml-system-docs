# aml-system-docs — 스킬·에이전트 맵

이 하네스는 SaaS AML/FDS 플랫폼의 **개발 착수용 문서 일습**을 만든다. 설명 정본은 각 파일 frontmatter의 `description:`이며, 이 파일은 **내비게이션 맵**이다.

## 라이프사이클 (ready-to-develop)

```
설계 → 기획 → 실행 → 검증(QA)
system-architect ─┬─ data-modeler ─┬─ backoffice-planner ─ task-planner ─ [doc-consistency-qa]
                  ├─ api-designer ─┤                                          └ design-reviewer
                  └─ integration-designer
```

> **마스터:** `feature-docs-pipeline` 워크플로우가 위 전 단계를 의존 순서로 순차 동기화 실행하고 끝에 QA·정합화까지 자동으로 돈다. 개별 에이전트는 단계별 보정용.
> **문서 작성/수정 직후** 반드시 `doc-consistency-qa`로 이격을 대조한다(마스터는 내장).

## 에이전트 (`.claude/agents/`, 7)
| 에이전트 | 역할 | 산출 |
|---|---|---|
| `system-architect` | 시스템 설계서 | `docs/software/NN-<svc>-sass.md` |
| `data-modeler` | DB 설계서/ERD | `docs/design/db/NN-<svc>-db.md` |
| `api-designer` | API 명세서 | `docs/design/api/NN-<svc>-api.md` |
| `integration-designer` | 이벤트·연동 명세 | `docs/design/integration/NN-<svc>-integration.md` |
| `backoffice-planner` | 기능정의서(PRD) + 기획서(PPT) | `docs/plan/NN-<svc>-sass-functional-spec.md` + `BO-<SVC>-SASS-Planning_v*.pptx` |
| `task-planner` | 개발 태스크 **2층 동기화** | ① 서비스 WBS `docs/tasks/<svc>/` ② 프로그램 로드맵 `docs/tasks/aegis-aml/`(P0~P8) |
| `design-reviewer` | 문서 일습 일치·착수 검수(읽기전용) | 발견사항 리포트 |

## 스킬 (`.claude/skills/`)
| 스킬 | 트리거 |
|---|---|
| `system-design` | 설계서 작성/업데이트 |
| `db-design` | DB·ERD·스키마 설계 |
| `api-design` | API·엔드포인트·OpenAPI |
| `integration-design` | 이벤트·SQS·연동·아웃박스 |
| `backoffice-planner` | PRD + PPT 작성 |
| `task-planning` | 개발 태스크 분해 + 서비스WBS↔프로그램로드맵 2층 동기화 |
| `doc-consistency-qa` | 문서 간 이격 대조 QA (워크플로우 실행) |
| `feature-docs-pipeline` | 기능 1건 → 전체 문서 싱크 마스터 파이프라인 (워크플로우 실행) |
| `architecture-conventions` | 횡단 컨벤션·타깃 구조 확인 |

## 워크플로우 (`.claude/workflows/`)
| 워크플로우 | 역할 |
|---|---|
| `feature-docs-pipeline` | **마스터.** 기능 1건 → 설계→DB→API→연동→태스크→PRD→PPT 순차 동기화 → QA → 정합화 루프. 실행: `Workflow({ name: "feature-docs-pipeline", args: { feature: "<설명>", service: "<svc>" } })` |
| `doc-consistency-qa` | 설계↔DB↔API↔연동↔PRD↔PPT↔태스크 이격을 쌍별 팬아웃 대조 → 높음 재검증 → `docs/qa/` 리포트 + PASS/FAIL. 실행: `Workflow({ name: "doc-consistency-qa", args: { service: "all" } })` |

## 공유 정본 (`_shared/`)
- `target-architecture.md` — 타깃 모노레포(4서비스)·stack·layout·참조레포·**산출물 일습 매핑** 단일 정본. 모든 에이전트·스킬이 인용.

## 의존 (입력 → 산출)
- DB·API·연동 ← 설계서. API·연동 ← DB(필드). 태스크 ← 설계+DB+API+연동+PRD. PRD/PPT ← 설계+API/DB+태스크. 검증 ← 전체.

## 유지보수
- 에이전트·스킬 본문은 **500자 내외**. 상세는 `_shared/`·정본 샘플로 위임.
- 아키텍처/산출물 매핑 변경은 `_shared/target-architecture.md`에서 단일 수정 후 `architecture-conventions` 요약 갱신.
- 산출물 양식은 기존 `docs/software/*`·`docs/plan/*` 정본 샘플을 따른다.
