# .claude/ — aml-system-docs 하네스

SaaS AML/FDS 플랫폼을 **기획·설계**하기 위한 Claude Code 구성. Hanpass PH `.claude/` 패턴을 문서 프로젝트에 맞게 경량화했다.

## 레이아웃
```
.claude/
├── README.md          # 이 파일
├── agents/            # 7: system-architect · data-modeler · api-designer
│                      #    integration-designer · backoffice-planner · task-planner · design-reviewer
├── workflows/         # feature-docs-pipeline (마스터) · doc-consistency-qa (이격 대조)
└── skills/
    ├── INDEX.md       # 스킬·에이전트 맵 (먼저 읽기)
    ├── _shared/
    │   └── target-architecture.md   # 타깃 모노레포(4서비스) + 산출물 일습 정본
    ├── system-design/ db-design/ api-design/ integration-design/
    ├── backoffice-planner/ task-planning/ doc-consistency-qa/
    └── architecture-conventions/
```

산출물은 `docs/software`(설계) · `docs/design/{db,api,integration}`(상세 설계) · `docs/plan`(PRD+PPT) · `docs/tasks`(WBS)로 나뉘며, 합쳐서 **개발 착수용 문서 일습**을 이룬다.

## 마스터 파이프라인
기능 1건을 요청하면 `feature-docs-pipeline` 워크플로우가 **설계→DB→API→연동→태스크→PRD→PPT**를 의존 순서로 순차 동기화하고, 끝에 정합성 QA + 정합화 루프(최대 2회)까지 자동으로 돈다. 실행:
`Workflow({ name: "feature-docs-pipeline", args: { feature: "<설명>", service: "fds|aml|..." } })`.

## 문서 정합성 QA
문서를 작성·수정한 직후(또는 마스터 파이프라인 내장 단계로) `doc-consistency-qa` 워크플로우가 상위↔파생 문서(설계↔ERD↔API↔연동↔PRD↔PPT↔태스크)의 이격을 쌍별로 대조한다. 결과는 `docs/qa/`에 PASS/FAIL 리포트로 남는다. 실행: `Workflow({ name: "doc-consistency-qa", args: { service: "all" } })`.

## 어디서 시작하나
1. **루트 [`CLAUDE.md`](../CLAUDE.md)** — 프로젝트 목적·레포 구조·작업 흐름.
2. **[`skills/INDEX.md`](skills/INDEX.md)** — 에이전트·스킬 인벤토리와 라이프사이클.
3. **[`skills/_shared/target-architecture.md`](skills/_shared/target-architecture.md)** — 설계·기획이 따르는 타깃 아키텍처 정본.

## 원칙
- 에이전트·스킬 본문은 **500자 내외**. 상세·반복 사실은 `_shared/` 정본으로 위임해 드리프트를 막는다.
- 아키텍처 사실의 단일 출처는 `_shared/target-architecture.md` 하나다.
- 산출물(설계서·기능정의서·PPT)은 한국어 업무 자연어, 기존 `docs/` 정본 샘플 양식을 따른다.
