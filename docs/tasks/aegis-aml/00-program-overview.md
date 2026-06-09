# aegis-aml 개발 프로그램 로드맵 (Program Overview)

> **목적**: 설계·기획 정본(`docs/{software,design,plan}`, FDS·AML 정합성 **PASS**)을 실제 모노레포 `aegis-aml`(`/Users/smkim/workspace/smkim89/aegis-aml`)로 구현하는 **전체 개발 단계(Phase)** 를 4서비스 통합 관점으로 분해한다.
> **입력 구조 검토**: 서비스별 상세 WBS는 [`../fds/`](../fds/00-overview.md)(T-01~T-22)·[`../aml/`](../aml/00-overview.md)(T-01~T-22)에 존재. 본 로드맵은 그 위에 **bo-api·bo-web·인프라·교차연동·DevOps**를 더해 **단계별 수직 슬라이스**로 통합·시퀀싱한다. (엔진 WBS의 패키지 `com.hanpass.*`는 설계 표기이며, aegis-aml 구현 패키지는 `com.aegis.{fds,aml,backoffice}`.)

## 0. 대상 서비스 & 현재 스켈레톤 상태

| 서비스 | 스택 | 아키텍처 | 스켈레톤 현황(완료) | 주 산출 |
|---|---|---|---|---|
| `fds-svc` | Java25/Spring Boot | 헥사고날 `com.aegis.fds` | Decision·Rule 도메인·enum·port·usecase·REST·SQS·JPA·Flyway V1(9테이블)·bootJar ✅ | FDS 엔진 |
| `aml-svc` | Java25/Spring Boot | 헥사고날 `com.aegis.aml` | Alert·Case 도메인·enum·port·usecase·REST·SQS(fds→aml)·JPA·Flyway V1(8테이블)·bootJar ✅ | AML 엔진 |
| `bo-api` | Java25/Spring Boot | 피처 `com.aegis.backoffice` | admin·audit·dashboard 피처·Security·OpenAPI·Flyway(5테이블)·compile ✅ | 운영자 집계·위임 |
| `bo-web` | Next.js16/React19/TS | App Router | FDS14+AML13 라우트·사이드바·KPI·TenantContext·api 클라이언트·build ✅ | 백오피스 UI |
| (공통) | Gradle9.4.1·buildSrc·카탈로그·docker-compose | — | 기반 + `.claude` 개발 하네스 ✅ | 인프라·자동화 |

> 스켈레톤 = **부트 가능한 골격 + 설계 도메인 스키마**. 본 로드맵의 각 단계는 이 골격의 TODO(엔진 위임·룰엔진 로직·화면 데이터·연동·규제)를 채운다.

## 1. 개발 프로세스 (단계별 공통)

각 태스크는 aegis-aml 하네스 프로세스를 따른다(`aegis-aml/CLAUDE.md`):
```
① 계획(brainstorming→writing-plans) → ② 개발(executor→implementer) → ③ QA(빌드·테스트·lint·리뷰)
   → [실패] ④ 수정PLAN → ⑤ 수정 → ③ QA 루프 → ⑥ PR
마스터: Workflow dev-qa-pr
```
**완료(DoD) 게이트**: 빌드 성공 + 테스트 통과 + (프론트)lint 0 + 리뷰 **높음 0** + 설계 정본 정합. 단계 종료 = 그 단계 전 태스크 DoD 충족 + 단계 Exit 기준.

## 2. 개발 단계(Phase) 요약

| Phase | 단계명 | 핵심 산출(4서비스) | 파일 |
|---|---|---|---|
| **P0** | 기반·하네스·CI | 모노레포·buildSrc·카탈로그·docker-compose·CI 파이프라인·테스트 인프라·코드 컨벤션 게이트 | [01-phase0-foundation.md](01-phase0-foundation.md) |
| **P1** | 코어 인프라·데이터 | DB/Flyway 전체·고객사/서비스/source 레지스트리·canonical/customer store·Public API GW·인증(API Key·OAuth2·mTLS)·SQS 토폴로지·bo-api 인증/IAM 골격 | [02-phase1-core-infra.md](02-phase1-core-infra.md) |
| **P2** | 엔진 MVP | FDS feature store·rule engine·decision API / AML WLF screening·RA model·TM scenario | [03-phase2-engines-mvp.md](03-phase2-engines-mvp.md) |
| **P3** | 도메인 1차·BO API 집약 | FDS 도메인 룰팩 / AML CDD·국가위험·명단 / bo-api dashboard·admin·audit 집약 + 엔진 위임(RestClient) | [04-phase3-domain-boapi.md](04-phase3-domain-boapi.md) |
| **P4** | 액션·케이스·결재(4-eyes) | action router·outbox / case management / 결재 게이트(payload_hash·실행분리) — FDS·AML 공통 | [05-phase4-action-case-approval.md](05-phase4-action-case-approval.md) |
| **P5** | 백오피스 프론트(bo-web) | 화면 구현(대시보드→목록→상세→빌더→결재함), 컴포넌트 공통화, react-query 연동 — FDS 31 + AML 23화면(20화면 + TNT-001~003 고객사 관리 3화면: 목록·상세[4탭]·등록) | [06-phase5-bo-web.md](06-phase5-bo-web.md) |
| **P6** | 규제·교차연동·증적 | STR/CTR/Travel Rule·Policy Pack / fds→aml handoff / evidence export·webhook callback | [07-phase6-regulatory-integration.md](07-phase6-regulatory-integration.md) |
| **P7** | 운영·관측성·하드닝·DevOps | 관측성·connector health·vendor bridge·보안·성능·CD·배포 | [08-phase7-ops-hardening.md](08-phase7-ops-hardening.md) |
| **P8** | SaaS 제품화 | 배포/온보딩 프로비저닝(IaC·self-hosted 설치형·`onboarding_status`)·connector SDK·dev portal·sandbox·conformance·metering·regional | [09-phase8-saas.md](09-phase8-saas.md) |

## 3. 서비스별 WBS ↔ Phase 매핑

| Phase | fds-svc (WBS) | aml-svc (WBS) | bo-api | bo-web | 공통 |
|---|---|---|---|---|---|
| P0 | T-01 | T-01 | scaffold | scaffold | CI·하네스 |
| P1 | T-02~T-07 | T-02~T-07 | auth/IAM | — | 인프라 |
| P2 | T-08~T-12 · T-15(골격) | T-08~T-12·T-14(MVP) | — | — | — |
| P3 | T-13 | T-13(CDD·국가위험·명단) | dashboard·admin·audit·위임 | — | — |
| P4 | T-14~T-16 | T-12(완성)·T-14(완성)·T-13(완성분)·T-16(outbox) | 결재 집약 | — | — |
| P5 | — | — | 화면별 집약 API 완성 | **전 화면** | — |
| P6 | T-17·T-19 | T-15·T-17·T-18·T-19 | 보고 집약 | 규제 화면 | webhook |
| P7 | T-20·T-21 | T-20·T-21 | 운영 집약 | 운영 화면 | CI/CD·보안 |
| P8 | T-22 | T-22 | 배포/온보딩 프로비저닝·metering 집약 | 배포유형선택·온보딩 상태 UI | dev portal·SDK·전용 배포 IaC |

> bo-api/bo-web/공통은 별도 WBS가 없어 각 Phase 파일에서 태스크로 신규 분해한다.

## 4. 교차연동 핵심 (서비스 간)

- **FDS → AML 위임**: `fds-aml-handoff` 큐(`FdsAmlHandoff` 메시지·cross-ref `amlCaseRef`) — fds T-17 발행 / aml-svc 소비(스켈레톤 `FdsDecisionConsumer` 존재). P6(fds T-17=P6-FDS-01). 핸드오프 큐·메시지·컨슈머·SQS 토폴로지(`*-events`/`*-actions`/`fds-aml-handoff`/`*-webhook`/`*-vendor-ingest`)의 정본은 **integration 명세**(`docs/design/integration/01-fds-integration.md` §2/§9, `02-aml-integration.md`). cross-ref `amlCaseRef`는 **DTO/메시지 필드명**이며 DB 물리 컬럼 정본은 `fds_cases.aml_case_id VARCHAR(96) NULL`(DB §5.13·`ix_case_aml_ref`, integration §9.1 동일 타입, FK 아님)으로 1:1 매핑된다.
- **bo-web → bo-api → 엔진**: 운영자 집계(대시보드/고객사/감사)는 bo-api 소유, 화면별 데이터는 bo-api가 엔진 admin API를 RestClient 위임. P3·P5.
- **규제 보고 본처리**: aml-svc 소관(STR/CTR/Travel Rule), fds는 핸드오프만. P6.
- **공통 SQS 토폴로지**: `*-events`·`*-actions`·`fds-aml-handoff`·`*-webhook`·`*-vendor-ingest` + DLQ. P1에서 토폴로지, 각 도메인 Phase에서 발행/구독.

## 5. 마일스톤

| M | 의미 | 충족 Phase |
|---|---|---|
| **M1 데이터 수신** | 이벤트/고객 ingest → canonical/customer store 적재(멱등) | P1 |
| **M2 판단 MVP** | 룰/스크리닝 → decision/alert 생성, 동기 평가 API | P2 |
| **M3 운영 가능** | BO API 집약 + 액션·케이스·결재 동작 | P3~P4 |
| **M4 콘솔 완성** | bo-web 전 화면 + 연동 | P5 |
| **M5 규제 대응** | STR/CTR/Travel Rule·evidence·검사대응 | P6 |
| **M6 출시 준비** | 관측성·보안·성능·CD | P7 |
| **M7 SaaS** | 멀티고객 배포/온보딩 프로비저닝(전용 배포 IaC·self-hosted 설치형)·SDK·metering | P8 |

## 6. 횡단 불변식 (전 단계 강제 — QA 게이트)

멀티테넌시 키 `(tenant_id, workspace_id, …)` 는 **배포 내부 분리** 용도(FDS·AML 모두 고객사별 전용 배포가 기본 — `fds_tenants.deployment_model` / `aml_tenants.deployment_model` 동일 3종 `MANAGED_DEDICATED`/`SELF_HOSTED`/`SHARED`, 전용 배포는 배포=고객사 단일 `tenant_id`·격리=배포 경계, target-architecture §4.1. `isolation_mode` 폐기 확정·D-06 결정) · 4-eyes(작성자≠승인자) · raw PII 미저장(토큰/마스킹) · traceId MDC 관측성 · 버전 카탈로그(버전 직접 명시 금지) · Flyway 추가만 · (프론트)컴포넌트 공통화·ESLint/Prettier/tsc 0 · 설계 정본(API/DB/PRD) 1:1.

## 변경 이력
| 일자 | 변경 |
|---|---|
| 2026-06-08 | **TNT 화면 구조 변경(4화면→3화면) 정합화** (정본=PRD §13 재구성본·PPT v5.3). §2 P5 행: AML 24화면(TNT-001~004 4화면) → AML 23화면(TNT-001~003 3화면: 목록·상세[4탭]·등록, 구 TNT-004 온보딩 상태를 TNT-002 ② 배포·온보딩 탭으로 흡수). |
| 2026-06-08 | **doc-consistency(aml:wbs-roadmap·aml:roadmap-design-prd) 이격 정합화** (정본=Phase 파일·WBS·PRD·`target-architecture.md`). **(1) §2 P5** `FDS 32`→`FDS 31` 정정(FDS PRD·06-phase5 헤더 정본). **(2) §3 P4 aml 칸** `T-14(완성)·T-15·T-16(outbox)`→`T-14(완성)·T-16(outbox)` (T-15 제거). **(3) §3 P6 aml 칸** `T-17·T-18·T-19`→`T-15·T-17·T-18·T-19` (T-15 추가, 07-phase6 P6-AML-03 정본). aml WBS T-15/T-17/T-18 Due P6 단일화와 동기화. | task-planner |
| 2026-06-08 | **doc-consistency(aml:wbs-roadmap·aml:roadmap-sw-prd) 담당 이격 정합화** (정본=`target-architecture.md`+WBS+PRD). **(1) §2 P5** "FDS 32 + AML 20화면"→"FDS 32 + AML 24화면(20화면 + TNT-001~004 고객사 관리 4화면)"(PRD v5.0 §13 TNT 4화면 추가 반영). **(2) §3 P1 aml 칸** `T-01~T-07`→`T-02~T-07` 정정(T-01은 P0 스캐폴딩 완료, P1 이중 등재 해소). **(3) §3 P6 aml 칸** `T-17·T-19`→`T-17·T-18·T-19` 정정(07-phase6 헤더 T-18 포함 기재와 일치, PRD AML-TR-001 참조). |
| 2026-06-08 | **Phase 7 파일 설계 근거 인용 정정(doc-consistency 3-10 담당 항목)**: `08-phase7-ops-hardening.md` 헤더 입력 인용을 '`docs/software §18/§21 Phase 6~7`'→'`§18 Phase 6·§16(운영·관측성·보안)·§21(legacy vendor bridge)`'으로 정정하고, 설계서 §18 Phase 7 'Advanced domain pack'은 범위 제외(fds T-18 별도 보류)임을 헤더에 명시. P7 태스크 표(P7-FDS/AML/INFRA/BOAPI/WEB)·범위는 변경 없음(인용 정확화). 정본=로드맵 §2 P7·`target-architecture.md` §4. |
| 2026-06-08 | **svcwbs↔roadmap Phase 매핑 정합화(doc-consistency 정정 반영)**: fds WBS Due를 본 로드맵/Phase 파일(실태스크 배치) 정본에 맞춰 정정(T-17 P6-FDS-01·T-20 P7-FDS-01·T-21 P7-FDS-02·T-15 P2-FDS-06 골격/P4-FDS-03 완성·T-18 advanced domain pack 보류). **§3 매핑 P2 fds 칸에 'T-15(골격)' 명시**(§3↔03-phase2 P2-FDS-06 정합). §4 교차연동 `amlCaseRef` 표기 명확화 — 핸드오프 큐/메시지/컨슈머/SQS 토폴로지 정본=integration 명세, `amlCaseRef`(DTO/메시지 필드)↔`fds_cases.aml_case_id`(DB §5.13 물리 컬럼, FK 아님) 1:1 매핑 1줄 고정. fds T-17 위임=P6로 단일화(`P4~P6`→P6). 본 로드맵 §3 매핑·07-phase6·08-phase7 태스크 배치는 변경 없음(WBS를 정본에 정렬). |
| 2026-06-08 | **FDS 격리(isolation_mode) → 배포 모델(deployment topology) 재설계** 2층 동기화(설계서 v1.5·DB v1.3·API v1.5·integration v1.5, target-architecture §4.1). §2 P8 산출·§3 P8 매핑(bo-api 배포/온보딩 프로비저닝·bo-web 배포유형선택/온보딩 상태·공통 전용 배포 IaC)·§5 M7·§6 횡단 불변식(멀티테넌시 키=배포 내부 분리·전용 배포 기본) 갱신. 영향 Phase: P1(P1-FDS-01/02 배포 모델·Flyway V17), P3(P3-BOAPI-02 deployment_model 집약), P5(P5-FDS-02 배포 유형 선택+온보딩 상태), P8(P8-FDS-01/BOAPI-01/WEB-01/INFRA-04 배포/온보딩 프로비저닝). fds T-02/T-03/T-22 WBS와 정합. |
| 2026-06-08 | **AML 고객사 격리(isolation_mode) → 배포 모델(deployment topology) 재설계** 2층 동기화(AML 설계서 §16/§17.1·DB §3.1/§5.28/§5.28a/§5.28b·API §1.1/§3.16/§4/§5/§9·integration §2.1/§10.1/§10.3, target-architecture §4.1, D-06 결정 확정). §6 횡단 불변식: `fds_tenants.deployment_model` 언급에 `aml_tenants.deployment_model` 동일 3종 병기·`isolation_mode` 폐기 확정 명시. 영향 Phase: **P1**(P1-AML-01 Flyway V17a/V17b·P1-AML-02 `deployment_model`(3종)/`onboarding_status`(8종)·큐 물리명 규칙·`isolation_mode` 토글 제거), **P3**(P3-BOAPI-02 AML 고객사 관리 DoD `isolation_mode`→`deployment_model`/`onboardingStatus`/`region`/`infraRef`·`deploymentModel` 불변 409), **P8**(P8-AML-01 배포/온보딩 프로비저닝 3경로·`onboarding_status` 상태머신·큐 프로비저닝 자동화·`registrationToken` 검증, P8-INFRA-04 AML 전용 큐 IaC 보강). aml T-03/T-22 WBS·P1-AML-02·P3-BOAPI-02·P8-AML-01·P8-INFRA-04와 정합. |
| 2026-06-07 | aegis-aml 개발 프로그램 로드맵 신규 작성. fds/aml 서비스 WBS + 스켈레톤 현황 검토 후 P0~P8 단계로 4서비스(엔진·bo-api·bo-web·인프라) 통합 분해. Phase별 파일(01~09) + 서비스 매핑·교차연동·마일스톤·횡단 불변식. |
| 2026-06-08 | #56/#57 §3 P4 aml 칸 T-ID 집합 정정: `T-14(완성)·T-16(outbox)`→`T-12(완성)·T-14(완성)·T-13(완성분)·T-16(outbox)`. T-12 결재 엔진은 P2 골격·P4 완성으로 분리되며 완성분은 P4 배치(05-phase4 P4-AML-03 정본과 정합). |
