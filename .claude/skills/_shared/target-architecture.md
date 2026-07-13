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
- **운영자 인가와 engine scope 분리**: BO 사람 요청은 endpoint별 exact capability(`SFDS_*` 등)로 먼저 인가하고, bo-api→engine 호출은 별도의 machine credential scope(`fds:*`/`aml:*`)로 다시 인가한다. `platformOperator`는 tenant/workspace 횡단 target을 선택하는 **data-scope 속성일 뿐** 메뉴·IAM·PII reveal·STR·업무 action의 인가 우회가 아니다. `BO_SUPER_ADMIN`의 exact wildcard scope `*`만 전역 우회이며, machine scope가 BO 역할을 대신하거나 BO 역할명이 engine으로 전달되어서는 안 된다.
- **요청 target 일치**: non-platform 사용자는 인증된 tenant/workspace와 path·query·body target이 모두 일치해야 한다. platform operator도 횡단 호출 때 하나의 명시적 target을 선택해야 하며, target끼리 충돌하면 downstream 호출·업무 처리·감사 기록 전에 fail-closed한다.
- **신뢰 actor와 감사 계보**: maker/checker/actor는 body 자기주장이 아니라 HMAC 검증 뒤 승격한 signed end-user subject에서 파생한다. BO local fallback 결재도 현재 인증 principal을 maker로 저장하며 `ops.agent` 같은 기본 명의를 사용하지 않는다. BO·AML·FDS 감사는 `(tenant_id, workspace_id)`로 격리하고 `trace_id`, subject를 정규화해 같은 projection으로 조회한다. bo-api의 임의 `/api/v1/admin/{engine}/**` passthrough는 금지하며 typed BFF controller/client만 허용한다.
- **식별자·trace 경계**: bo-api의 path·query·body tenant/workspace target은 trim 후 64자 이하, 공통 HTTP/BO/admin `X-Trace-Id`는 128자 이하이며 제어문자(CR/LF 포함)를 금지한다. request trace는 MDC로 전파하고 감사 adapter는 명시적 causal trace를 우선, 없을 때만 MDC를 사용한다. 단, canonical AML ingest 계약은 `docs/aml-data.md` 정본의 64자/422를 유지하며 이를 128자로 넓히지 않는다. machine-auth의 signed `X-User-Subject`도 HMAC 성공 뒤 128자/제어문자 경계를 통과한 값만 verified attribute로 승격한다. 길이 제한은 DB 예외에 맡기지 않고 handler·감사 write 전에 검증한다.
- **FDS fallback 경계**: fds-svc delegate가 없을 때 bo-api의 local FDS 상태는 production에서는 항상 503이고, non-production도 disposable `tenant_demo/default` 복합 scope에서만 사용할 수 있다. 다른 tenant/workspace·scope 부재는 503이며 결재·감사·fallback row는 현재 request scope 밖으로 쓰지 않는다. engine-owned compliance policy는 별도 typed fallback service를 거친다. local payload는 exact `{"base":"KR_BASE","packs":string[],"optional":string[]}`만 허용하고 인증 principal maker로 `POLICY_PACK` 결재를 stage하며 즉시 effective 값을 바꾸지 않는다. 다른 checker의 exact `SFDS_REG:APPROVE`·immutable hash/scope/payload 검증과 authoritative writer 적용이 성공해야 `EXECUTED`가 된다. reject/apply 실패는 기존 policy를 보존하고, delegate가 구성된 뒤의 engine 오류·빈/잘못된 응답은 local projection으로 대체하지 않고 fail-closed한다.
- **규제 보고**: 한국 Policy Pack(STR/CTR). Travel Rule은 현 단계 범위에서 제거한다.
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

### 4.2 운영 seed·secret 경계

- 운영 정규 Flyway location set은 서비스의 `db/migration`(AML의 checksum-pinned Java migration 포함)만 사용하고 `classpath:db/demo`를 포함하지 않는다. 과거 적용 migration은 checksum 불변이며, 알려진 demo 계정·tenant·평가 설정은 신규 forward quarantine migration으로 비활성화한다. `db/demo`의 repeatable reference 설정은 명시적 `demo` profile에서만 추가한다.
- active profile이 비면 configured default profile을 effective profile로 사용한다. `prod`/`production`/`aws` 중 하나라도 effective profile이면 `local`/`demo` 혼합 또는 scalar/indexed environment property의 `db/demo` location override를 bean/Flyway 생성 전에 거부한다. 운영 최종 DB에는 로그인 가능한 공개 demo 사용자, 알려진 demo 복합 fingerprint의 ACTIVE tenant·평가 설정·credential·미종결 승인이 없어야 한다. demo repeatable도 dependent row마다 같은 복합 fingerprint를 다시 확인하며, 거래·고객·alert·case·report 같은 business data는 Flyway가 아니라 서명된 REST simulator가 생성한다.
- `tenant_demo`는 hanpass-ph 운영 tenant ID로도 사용하므로 **ID 단독이나 `demo` 부분 문자열은 demo 판정 근거가 아니다**. immutable seed timestamp·actor·표시명·배포 metadata의 exact 조합과 알려진 seed 사용자·provenance·고정 식별자만 격리·startup 거부 대상으로 삼는다. AML의 FATF country source와 status 없는 CTR threshold/banking calendar도 production base에서는 inert/부재하고 explicit demo repeatable에서만 reference 설정으로 복원한다.
- 최초 운영 `BO_SUPER_ADMIN`은 Flyway가 만들지 않는다. IdP provisioning 또는 secret manager가 한 번만 주입하는 OOB bootstrap secret으로 생성하고, 계정·role 부여·완료 marker를 같은 transaction으로 감사한 뒤 입력을 제거한다.
- BO session HMAC, FDS credential 암호화 master key, AML credential cipher·PII HMAC·evidence token secret은 secret manager가 독립 생성해 주입한 Base64/Base64URL random material(복호화 기준 32 bytes 이상)만 운영에서 허용한다. AML 세 secret의 decoded material 재사용과 blank·공개 기본값·잘못된 encoding·저엔트로피 값은 readiness 전에 거부하며 오류·감사 로그에 값이나 fingerprint를 남기지 않는다.
- BO session key 교체는 기존 token 전부 무효화→재로그인을 전제로 한다. P0-02의 key rollback은 배포 실패 시 **같은 secret-manager current version**으로 되돌리는 절차까지만 뜻한다. machine credential 생성·scope·유예 회전·폐기·last-used는 P1-02, 암호문 `keyId`/tenant·resource AAD/dual-read/background re-encryption/key-use audit는 P1-03 범위이며 P0-02 완료로 간주하지 않는다.

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
