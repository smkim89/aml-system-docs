# 타깃 시스템 아키텍처 정본 (Target Architecture)

> 이 프로젝트가 **설계·기획하는 대상 시스템**의 정본 아키텍처. 모든 에이전트·스킬은 여기서 stack·layout·네이밍을 가져온다. 충돌 시 이 문서가 우선한다.

## 1. 제품

한국 금융시장용 **SaaS형 AML + FDS 플랫폼**. 멀티테넌트·멀티도메인(카드·송금·PG·월렛·코인·대출·보험·정산 등)을 단일 플랫폼으로 수용한다. 참조 구현은 Hanpass PH `fds-svc`(FDS)와 MemberSvc AML WLF.

## 2. 모노레포 구조 (Hanpass PH 패턴)

단일 모노레포 루트에 `services/` 하위 **4개 프로젝트**. 빌드는 Gradle(Java) + 독립 Next.js. 서비스별 독립 배포.

```
<repo-root>/
├── buildSrc/                 # Gradle 컨벤션 플러그인 (Kotlin DSL) — fds/aml/bo-api 공용
├── common/                   # 공유 라이브러리 (점진 추출)
├── gradle/libs.versions.toml # 버전 카탈로그 단일 정본
├── compose/ docker-compose.yml
├── services/
│   ├── fds-svc/   # FDS 엔진 백엔드   — Java 25 / Spring Boot / 헥사고날
│   ├── aml-svc/   # AML 엔진 백엔드   — Java 25 / Spring Boot / 헥사고날
│   ├── bo-api/    # 백오피스 백엔드   — Java 25 / Spring Boot / 패키지-바이-피처
│   └── bo-web/    # 백오피스 프론트   — Next.js 16 / React 19 / TS
└── .github/workflows/        # 서비스별 path-filtered CI
```

## 3. 서비스별 스택 & 레이아웃

### services/fds-svc, services/aml-svc — 엔진 백엔드 (참조: `hanpass-ph/services/fds-svc`)
- Java 25, Spring Boot 3.5.x, Gradle, 헥사고날 아키텍처.
- 패키지: `com.hanpass.<svc>` 하위 `domain/` · `application/`(usecase·port/in·port/out) · `adapter/`(in: rest·sqs·scheduled / out: persistence·external) · `global/`.
- 도메인 규칙·불변식은 `domain`, 유스케이스·트랜잭션 경계는 `application`, I/O는 `adapter`.
- 비동기 SQS, 멀티테넌시(tenant/workspace/data-scope), 룰엔진 + feature catalog, Action·Case·Investigation 모델.

### services/bo-api — 백오피스 백엔드 (참조: `hanpassj-backoffice`)
- Java 25, Spring Boot 3.5.x, Spring Security, Data JPA/JDBC, Flyway, PostgreSQL.
- 패키지: `com.hanpass.backoffice.<feature>` (admin·audit·auth·dashboard·member·setting·menu 등), 각 피처 = `controller/ dto/ entity/ repository/ service`.
- fds-svc·aml-svc의 admin API를 운영자용으로 집약·인증·감사.

### services/bo-web — 백오피스 프론트 (참조: `hanpassr-backoffice`)
- Next.js 16(App Router), React 19, TypeScript, Tailwind v4, radix-ui, @tanstack/react-query, zustand, react-hook-form + zod, next-intl, recharts.
- 디렉토리: `app/`(라우트) · `components/`(피처별) · `lib/` · `hooks/` · `context/` · `i18n/` · `messages/`.
- bo-api를 통해서만 데이터 접근(엔진 직접 호출 금지). 멀티테넌트 권한·data-scope 반영.

## 4. 횡단 원칙
- **배포 모델(핵심)**: AML/FDS는 고객 PII·거래·제재 데이터의 규제·보안 요건이 커서 **고객사별 전용 배포가 기본**이다(공유 SaaS DB 아님). §4.1 참조.
- **멀티테넌시 키**: `tenant_id`/`workspace_id`/`data_scope`는 **배포 내부 분리** 용도다 — `tenant_id`=배포의 고객사(전용 배포에선 사실상 단일 값), `workspace_id`=그 고객사의 서비스/환경(예 retail/corporate, prod/sandbox), `data_scope`=조회·조치 권한 필터. (소규모 공유 배포에서만 `tenant_id`가 고객사 간 격리로 동작.)
- **컴플라이언스**: raw PII 미저장(토큰/해시 마스킹), 4-eyes(작성자≠승인자), 감사로그 전수.
- **규제 보고**: 한국 Policy Pack(STR/CTR/Travel Rule).
- **관측성**: traceId 전파 + 경계별 진입/이탈 구조화 로그.

### 4.1 배포 모델 (deployment topology)
격리는 DB 행/스키마 토글이 아니라 **배포 단위 결정**이다. 화면에서 즉석 선택하는 값이 아니라 **온보딩 프로비저닝 프로세스**의 산출이다. `fds_tenants.deployment_model`(구 `isolation_mode` 대체).

| 모델 | 의미 | 대상 | 프로비저닝 |
|---|---|---|---|
| **`MANAGED_DEDICATED`**(기본) | 플랫폼(우리 클라우드)에 **고객사별 전용 DB·스택** | 일반 금융사 | 온보딩 파이프라인 **IaC(Terraform)** 자동 — 승인→프로비저닝→시크릿/DNS→배포→검증→운영전환(ops 작업, 화면 라디오 아님) |
| **`SELF_HOSTED`** | **고객 자체 인프라**(고객 데이터센터/VPC)에 설치형 | 은행·고PII·내부망 요건 | **설치형 패키지(Helm/Docker/installer)** 를 고객 측이 배포. 플랫폼은 산출물·가이드·라이선스 제공(우리가 자동 생성 불가) |
| **`SHARED`**(옵션) | 공유 DB + `tenant_id` 행 격리 | 소규모/체험 | 즉시(프로비저닝 없음) |

- **한 고객사 = 한 배포(전용 DB)** 가 기본. "고객사 등록"은 격리 라디오가 아니라 **배포 유형 선택 + 온보딩 신청·상태** 관리다(매니지드는 운영자 카탈로그, self-hosted는 고객 단독 BO).
- 온보딩 상태머신: `REQUESTED → PROVISIONING → DEPLOYED → VERIFIED → ACTIVE`(매니지드) / `PACKAGE_ISSUED → CUSTOMER_DEPLOYED → REGISTERED`(self-hosted).

## 5. 개발 착수용 산출물 일습 (ready-to-develop)
| 단계 | 산출물 | 경로 | 담당 에이전트 |
|---|---|---|---|
| 설계 | 시스템 설계서 | `docs/software/NN-<svc>-sass.md` | system-architect |
| 설계 | DB 설계서/ERD | `docs/design/db/NN-<svc>-db.md` | data-modeler |
| 설계 | API 명세서 | `docs/design/api/NN-<svc>-api.md` | api-designer |
| 설계 | 이벤트·연동 명세 | `docs/design/integration/NN-<svc>-integration.md` | integration-designer |
| 기획 | 기능정의서(PRD) | `docs/plan/NN-<svc>-sass-functional-spec.md` | backoffice-planner |
| 기획 | 기획서(PPT) | `docs/plan/BO-<SVC>-SASS-Planning_v*.pptx` | backoffice-planner |
| 실행 | 개발 태스크/WBS(서비스별) | `docs/tasks/<svc>/00-overview.md` + `NN-*.md` | task-planner |
| 실행 | **개발 프로그램 로드맵(전 시스템)** | `docs/tasks/aegis-aml/00-program-overview.md` + `0N-phaseN-*.md`(P0~P8) | task-planner |
| 검증 | 일습 일치 검수 | (리포트) | design-reviewer |

서비스 NN·약칭 예시: `01`=fds(FDS), `02`=aml(AML). DB·API·integration·tasks는 fds-svc·aml-svc·bo-api·bo-web 각각으로 전개한다.

> **태스크 동기화(2층)**: 태스크는 ① **서비스 WBS**(`docs/tasks/<svc>/` — fds/aml 등 서비스별 기능 분해)와 ② **프로그램 로드맵**(`docs/tasks/aegis-aml/` — 구현 모노레포 `aegis-aml`의 P0~P8 단계, 4서비스 통합 + bo-api/bo-web/인프라/CI)으로 구성된다. 설계/기능이 바뀌면 **둘을 함께 갱신·정합**한다(서비스 WBS 태스크 ↔ 프로그램 로드맵 Phase 태스크 ↔ 설계 정본). 구현 패키지는 `com.aegis.{fds,aml,backoffice}`(설계 표기 `com.hanpass`와 구분).

## 6. 참조 레포 (로컬)
- `/Users/smkim/workspace/hanpass/hanpass-ph` — 백엔드 모노레포·헥사고날·convention plugins 정본
- `/Users/smkim/workspace/hanpass/hanpassj-backoffice` — BO 백엔드(Java 25) 정본
- `/Users/smkim/workspace/hanpass/hanpassr-backoffice` — BO 프론트(Next.js) 정본
