# docs/tasks — 백오피스(BO) 개발 태스크

> **목적**: 기획서 `BO-FDS-SASS-Planning_v7.0.pptx`(34화면) · `BO-AML-SAAS-Planning_v8.0.pptx`(32화면)를
> 구현 모노레포 **`/Users/smkim/workspace/smkim89/aegis-aml`** 의 `services/bo-web`(프론트엔드) + `services/bo-api`(백엔드)로
> 개발하기 위한 **단계별·기능 단위 태스크**. 모든 태스크에 참고 문서를 명시해 개발 중 불명확한 부분이 없게 한다.

## 구조

```
docs/tasks/
├── README.md                ← 이 파일
├── bo-fds/                  ← FDS 백오피스 (BO-FDS v7.0 · 34화면)
│   ├── 00-overview.md       ← 단계 개요·태스크 전수 표·의존 그래프·참고 문서 맵
│   └── 01~06-stage*.md      ← Stage 1~6 상세 (기능 단위 FE/BE 태스크)
└── bo-aml/                  ← AML 백오피스 (BO-AML v8.0 · 32화면)
    ├── 00-overview.md
    └── 01~06-stage*.md
```

## 구현 대상 (정본 = `.claude/skills/_shared/target-architecture.md`)

| 서비스 | 스택 | 패키지/디렉토리 | 참조 레포(로컬) |
|---|---|---|---|
| `services/bo-web` | Next.js 16(App Router)·React 19·TS·Tailwind v4·radix-ui·@tanstack/react-query·zustand·react-hook-form+zod·next-intl·recharts | `app/ components/ lib/ hooks/ context/ i18n/ messages/` | `/Users/smkim/workspace/hanpass/hanpassr-backoffice` |
| `services/bo-api` | Java 25·Spring Boot 3.5.x·Spring Security·Data JPA·Flyway·PostgreSQL | `com.aegis.backoffice.<feature>` (feature = `controller/ dto/ entity/ repository/ service`) | `/Users/smkim/workspace/hanpass/hanpassj-backoffice` |

**호출 경계(전 태스크 공통 불변식)**: bo-web → bo-api 만 호출(엔진 직접 호출 금지). bo-api는
① **자기 소유 집계 API**(`/api/v1/bo/{fds|aml}/**` — 대시보드·고객사·감사·통계·인입 모니터링)와
② **엔진 Admin API 위임 프록시**(`/api/v1/admin/{fds|aml}/*` → fds-svc·aml-svc)로 나뉜다.
(FDS API §2/§11·AML API §9 "소유 경계" 정본.)

## 태스크 ID·문서 규칙

- ID: `BOF-S{단계}-{번호}`(FDS) / `BOA-S{단계}-{번호}`(AML). 구분 = `FE`(bo-web) / `BE`(bo-api) / `SPEC`(API 명세 확정 선행).
- Effort 1~5 (`effort-level-guide` 기준). Status: `TODO / DOING / DONE / BLOCKED`.
- **참고 문서 표기**: 화면 정의·업무규칙(BR) = PRD §, 와이어프레임·표시 용어 = PPT 슬라이드 번호, 계약 = API 명세 §, enum·테이블 = DB 설계서 §, 큐·이벤트 = integration §, 아키텍처 = 설계서 §.
- **`(제안 API)` 표기 태스크는 반드시 같은 Stage의 `SPEC` 태스크(API 명세 확정)가 선행**되어야 한다 — PRD 부록 E(AML)·변경 이력(FDS) 오픈결정 목록 정본.

## 공통 참고 문서 (전 태스크 묵시 참조)

| 구분 | FDS | AML |
|---|---|---|
| PRD(기능정의서) | `docs/plan/01-fds-sass-functional-spec.md` v5.0 | `docs/plan/02-aml-sass-functional-spec.md` v8.0 |
| PPT(와이어프레임) | `docs/plan/BO-FDS-SASS-Planning_v7.0.pptx` (49슬라이드) | `docs/plan/BO-AML-SAAS-Planning_v8.0.pptx` (70슬라이드) |
| API 명세 | `docs/design/api/01-fds-api.md` | `docs/design/api/02-aml-api.md` |
| DB 설계 | `docs/design/db/01-fds-db.md` | `docs/design/db/02-aml-db.md` |
| 이벤트·연동 | `docs/design/integration/01-fds-integration.md` | `docs/design/integration/02-aml-integration.md` |
| 시스템 설계서 | `docs/software/01-fdsSvc-sass.md` | `docs/software/02-amlSvc-sass.md` |
| 아키텍처 정본 | `.claude/skills/_shared/target-architecture.md` (스택·레이아웃·배포 모델·호출 경계) | (동일) |
| 화면↔API 전수 매핑 | FDS PRD §16.1 | AML PRD 부록 A |
| 권한 매트릭스 | FDS PRD §16.2 | AML PRD 부록 B |
| 표시 용어 사전 | FDS PRD 본문 enum 병기 | AML PRD 부록 F (enum↔한국어 — i18n 키 원천) |

> 구 엔진(fds-svc·aml-svc) WBS·프로그램 로드맵 문서는 git 이력에서 복구 가능(`git log -- docs/tasks/`).
> 본 태스크는 **백오피스(bo-web·bo-api) 개발 전용**이며, 엔진 Admin API는 "이미 명세 확정(또는 제안)" 상태를 전제로 위임 호출만 다룬다.
