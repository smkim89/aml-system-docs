# CLAUDE.md

이 레포는 **한국 금융시장용 SaaS형 AML + FDS 플랫폼**을 **기획·설계**하는 문서 프로젝트다(코드 구현 X). 산출물은 설계서·기능정의서(PRD)·와이어프레임 기획서(PPT)다.

## 무엇을 만드는가 (대상 시스템)

설계·기획의 **대상**은 Hanpass PH 패턴을 따르는 모노레포다. `services/` 하위 4개 프로젝트:

| 프로젝트 | 스택 | 참조 레포 |
|---|---|---|
| `fds-svc` | Java 25 / Spring Boot / 헥사고날 | `hanpass-ph/services/fds-svc` |
| `aml-svc` | Java 25 / Spring Boot / 헥사고날 | `hanpass-ph` (MemberSvc AML) |
| `bo-api` | Java 25 / Spring Boot / 패키지-바이-피처 | `hanpassj-backoffice` |
| `bo-web` | Next.js 16 / React 19 / TS | `hanpassr-backoffice` |

> 타깃 아키텍처 정본 = **[`.claude/skills/_shared/target-architecture.md`](.claude/skills/_shared/target-architecture.md)**. stack·layout·네이밍은 항상 여기서 가져온다.

## 레포 구조

```
aml-system-docs/
├── CLAUDE.md                 # 이 파일 — 구조 안내
├── docs/
│   ├── software/             # 시스템 설계서 (NN-<svc>-sass.md) — system-architect
│   ├── design/
│   │   ├── db/               # DB 설계서/ERD (NN-<svc>-db.md) — data-modeler
│   │   ├── api/              # API 명세서 (NN-<svc>-api.md) — api-designer
│   │   └── integration/      # 이벤트·연동 명세 (NN-<svc>-integration.md) — integration-designer
│   ├── plan/                 # 기능정의서(PRD) + 기획서(PPT) — backoffice-planner
│   ├── tasks/                # 개발 태스크 (2층) — task-planner
│   │   ├── <svc>/            #   ① 서비스 WBS (fds·aml: 00-overview + NN-*.md)
│   │   └── aegis-aml/        #   ② 프로그램 로드맵 (00-program-overview + 0N-phaseN-*.md, P0~P8 · 4서비스 통합)
│   └── qa/                   # 문서 정합성 리포트 — doc-consistency-qa 산출
└── .claude/
    ├── README.md             # 하네스 개요
    ├── agents/               # 7개: system-architect·data-modeler·api-designer·integration-designer·backoffice-planner·task-planner·design-reviewer
    ├── workflows/            # doc-consistency-qa (문서 간 이격 대조 팬아웃)
    └── skills/
        ├── INDEX.md          # 스킬·에이전트 맵 (먼저 읽기)
        ├── _shared/          # target-architecture.md (정본)
        ├── system-design/ db-design/ api-design/ integration-design/
        ├── backoffice-planner/ task-planning/ doc-consistency-qa/
        └── architecture-conventions/   # 횡단 컨벤션
```

## 마스터 파이프라인 (기능 1건 → 전체 문서 싱크)

기능 추가·변경을 요청하면 **모든 문서가 의존 순서대로 동기화**되어 생성/갱신된다. 한 번에 돌리려면:

```
Workflow({ name: "feature-docs-pipeline", args: { feature: "<기능 설명>", service: "fds|aml|..." } })
```

```
① 설계 → ② DB → ③ API → ④ 연동 → ⑤ 태스크 → ⑥ 기획(PRD+PPT) → ⑦ QA → ⑧ 정합화(FAIL 시 재QA, 최대 2회)
  각 단계는 상위 문서를 진실로 삼아 직전 변경점(downstreamNotes)을 반영해 명칭·필드·enum·엔드포인트를 동기화한다.
```

개별 단계만 돌리고 싶을 때는 아래 라이프사이클의 각 에이전트를 직접 호출한다.

## 작업 흐름 (개발 착수용 문서 일습 — 단계별)

```
설계 ─ system-architect ─→ docs/software/NN-<svc>-sass.md
        ├ data-modeler ──→ docs/design/db/NN-<svc>-db.md
        ├ api-designer ──→ docs/design/api/NN-<svc>-api.md
        └ integration-designer → docs/design/integration/NN-<svc>-integration.md
기획 ─ backoffice-planner ─→ docs/plan/NN-<svc>-sass-functional-spec.md + BO-<SVC>-SASS-Planning_v*.pptx
실행 ─ task-planner ──────→ (2층 동기화)
        ├ 서비스 WBS      docs/tasks/<svc>/00-overview.md + NN-*.md
        └ 프로그램 로드맵 docs/tasks/aegis-aml/00-program-overview.md + 0N-phaseN-*.md (P0~P8)
검증 ─ doc-consistency-qa ─→ 문서 간 이격 쌍별 대조(서비스WBS↔로드맵↔설계 포함) → docs/qa/ 리포트 + PASS/FAIL
        └ design-reviewer (쌍별 대조·재검증·종합 담당)
```

> **태스크 2층 동기화**: 기능/설계가 바뀌면 task-planner가 **서비스 WBS(docs/tasks/<svc>)와 프로그램 로드맵(docs/tasks/aegis-aml, 구현 모노레포 aegis-aml의 P0~P8 단계)** 을 함께 갱신·정합한다. 마스터 파이프라인 ⑤ 태스크 단계가 둘 다 동기화하고, doc-consistency-qa가 정합을 검증한다.

> **문서를 작성·수정한 직후** `doc-consistency-qa` 워크플로우를 돌려 상위↔파생 문서(특히 설계↔ERD↔API)의 이격을 잡는다. 실행: `Workflow({ name: "doc-consistency-qa", args: { service: "all" } })`.

## 컨벤션

- **언어**: 모든 산출물·표시 용어는 한국어 업무 자연어. 내부 코드(enum)는 괄호 병기.
- **정본 우선**: 아키텍처 사실은 `_shared/target-architecture.md`, 양식은 기존 `docs/software/*`·`docs/plan/*` 정본 샘플을 따른다.
- **에이전트·스킬 작성 규칙**: 각 파일 본문 **500자 내외**로 간결하게. 상세는 `_shared/`·정본 샘플로 위임.
- **도구**: 검색/편집은 전용 도구 우선. 코드 변환 도구(comby/ast-grep)는 이 문서 프로젝트엔 거의 불필요.
