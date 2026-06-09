# P5 · 백오피스 프론트(bo-web)

> 마스터: [00-program-overview.md](00-program-overview.md). 정본: `target-architecture.md` §3.4(bo-web 스택·bo-api 경유). 입력: 기능정의서 `docs/plan/01-fds-sass-functional-spec.md`(SFDS 31화면)·`02-aml-sass-functional-spec.md`(AML 23화면: 20화면 + TNT-001~003 고객사 관리 3화면: 목록·상세[4탭]·등록, 구 TNT-004 온보딩 상태 → TNT-002 ② 배포·온보딩 탭 흡수, PRD §13 재구성본·PPT v5.3), bo-api 집약 API(P3·P4).
> 매핑(개요 §3): bo-web 전 화면 + bo-api 화면별 집약 API 완성. 마일스톤 **M4(콘솔 완성)**. bo-web은 **bo-api만 호출**(엔진 직접 호출 금지).

## 1. 목표·범위

- **이 단계가 끝나면**: 운영자가 백오피스 콘솔에서 **대시보드→목록→상세→빌더→결재함** 전 흐름을 수행한다. FDS 31화면 + AML 23화면(기존 20화면 + TNT-001~003 고객사 관리 3화면: 목록·상세[4탭]·등록, PRD §13 재구성본·PPT v5.3)이 react-query로 bo-api에 연동되고, 공통 컴포넌트(테이블·필터·결재함·탭·폼)로 일관 구현된다.
- **진입 조건**: P3(bo-api dashboard/admin/audit 집약·고객사 관리), P4(결재·케이스·액션 집약 API). 화면이 호출할 bo-api 데이터 계약이 확정되어 있어야 한다.
- **범위 포함**: bo-web 공통 인프라(레이아웃·TenantContext·api 클라이언트·권한 가드·i18n)·공통 컴포넌트 라이브러리 / FDS 화면 그룹(대시보드·고객사·커넥터/매핑·룰 빌더·그룹·결정/이벤트·액션/케이스·결재함·규제 후보·Evidence·감사) / AML 화면 그룹(대시보드·WLF 검토큐/상세/처리이력(WLF-001/002/003)·명단·RA·국가위험·CDD·TM·케이스·규제 보고·Travel Rule·결재함·감사) · 고객사 관리(TNT-001~003 3화면: 목록·상세[4탭: 기본정보·배포온보딩·소스시스템·정책팩]·등록, 구 TNT-004 온보딩 상태 → TNT-002 ② 배포·온보딩 탭 흡수) / 화면별 bo-api 집약 API 최종 완성(미비분).
- **범위 제외**: 엔진 신규 로직(P2~P4 완료분 소비), 규제 보고 본처리 화면 흐름의 백엔드(P6).

## 2. 태스크 표

### 2.1 공통 인프라·컴포넌트 공통화

| ID | 제목 | 서비스 | 구분 | Effort | 의존 | DoD | Status |
|---|---|---|---|---|---|---|---|
| P5-WEB-01 | 앱 셸·레이아웃·사이드바·TenantContext·권한 가드·i18n(next-intl) | bo-web | FE | M | P1-BOAPI-02 | 고객사/서비스 선택·data-scope 배지, 권한별 메뉴 노출, 미인가 차단, ko/en 메시지, tsc 0 | 부분완료 |
| P5-WEB-02 | api 클라이언트·@tanstack/react-query·에러/로딩·인증 토큰 인터셉터 | bo-web | FE | M | P5-WEB-01 | bo-api 전용 클라이언트(엔진 직접호출 금지), query/mutation 표준, 에러코드 표면화, 재시도/캐시 정책 | 부분완료 |
| P5-WEB-03 | 공통 컴포넌트 라이브러리(DataTable·FilterBar·DetailTabs·FormPanel·StatusBadge·ApprovalInbox) | bo-web | FE | L | P5-WEB-02 | radix-ui·Tailwind v4 기반 재사용 컴포넌트, enum 표시값 매핑 단일화, 목록/상세/폼/결재함 archetype, 스토리/스냅샷 | TODO |
| P5-WEB-04 | 결재함 공통 모듈(maker-checker·payload diff·승인/반려)·딥링크 라우팅 | bo-web | FE | M | P5-WEB-03,P4-BOAPI-01 | `subject_kind`/`approval_line`/`approval_status` 배지, self-approval 차단 UX, 대상→상세 딥링크, FDS/AML 공용 | TODO |

### 2.2 FDS 화면(31) — SFDS-*

| ID | 제목 | 화면 ID | 구분 | Effort | 의존 | DoD | Status |
|---|---|---|---|---|---|---|---|
| P5-FDS-01 | 플랫폼/고객사 대시보드·드릴다운 | DASH-001/002 | FE | M | P5-WEB-03,P3-BOAPI-01 | KPI 카드·플랫폼 알림 드릴다운·기간 필터, bo-api dashboard 연동, read-only | TODO |
| P5-FDS-02 | 고객사 관리(목록/상세/배포 유형 선택·온보딩 상태) | TNT-001/002/003 | FE | M | P5-WEB-03,P3-BOAPI-02 | 목록→상세→설정. **배포 유형 선택**(매니지드 전용/자체 인프라 설치형/[소규모 공유]=`deployment_model` 3종)+**온보딩 신청**, **온보딩 상태**(읽기 표시, `onboarding_status` 8종), workspace. 격리 방식 라디오 제거. bo-api tenants 연동(`/api/v1/bo/fds/tenants/**`); 온보딩 프로비저닝 워크플로(provision/상태/register)는 P8-WEB-01 | TODO |
| P5-FDS-03 | 커넥터·소스·매핑(health/일시중지/재개/매핑 결재) | CONN-001/002/003·MAP-001/002 | FE | L | P5-WEB-04 | 커넥터 health·pause/resume·커서·replay, 매핑 변경 4-eyes(MAPPING)→결재함 | TODO |
| P5-FDS-04 | no-code 룰 빌더·시뮬레이션·활성/롤백(RULE) | RULE-001~005 | FE | XL | P5-WEB-04,P2-FDS-04 | 문장형/DSL 토글·feature catalog·시뮬레이션 hit rate·activate/rollback 4-eyes(RULE), 자연어 미리보기 | TODO |
| P5-FDS-05 | 위험 그룹·watchlist 관리(추가/해제/연장) | GRP-001/002/003 | FE | M | P5-WEB-04,P2-FDS-03 | 그룹 마스터·멤버(`member_kind` 3종) 4-eyes(GROUP), 즉시 효과 콜아웃 | TODO |
| P5-FDS-06 | 결정 모니터·상세·이벤트(후속 조치 딥링크) | DEC-001/002/003·EVT-001 | FE | L | P5-WEB-03,P2-FDS-05 | decision 추이·판정 근거·feature snapshot·reason, 액션/케이스/타임라인 딥링크 | TODO |
| P5-FDS-07 | 액션·케이스(큐·배정·종결 상신) | ACT-001/002·CASE-001/002 | FE | L | P5-WEB-04,P4-BOAPI-02 | action 상태 조회(BE 자동재시도)·case 큐/SLA/배정/종결 상신(4-eyes CASE_CLOSE), 규제 보고 전환 딥링크 | TODO |
| P5-FDS-08 | 결재함·규제 후보·Evidence·감사 | APPR-001·REG-001/002·EXP-001·AUDIT-001 | FE | L | P5-WEB-04 | 결재함(공용), 규제 후보=위임 흐름·읽기전용 `[aml-svc 보고서로 이동]` 딥링크(직접 결재/제출 부재), Evidence export self-service, 감사 조회 | TODO |

### 2.3 AML 화면(23) — AML-*

> PRD §13 재구성본·PPT v5.3 기준: 기존 20화면(DASH·WLF·WL·RA·CTRY·CDD/CASE·TM·REP/TR·APR/AUD/PP) + TNT-001~003 고객사 관리 3화면(목록·상세[4탭]·등록) 추가. 총 23화면. 구 TNT-004 온보딩 상태 단독 화면 → TNT-002 상세의 ② 배포·온보딩 탭으로 흡수. (개요 §2 P5 동기화 완료)

| ID | 제목 | 화면 ID | 구분 | Effort | 의존 | DoD | Status |
|---|---|---|---|---|---|---|---|
| P5-AML-01 | AML 종합 대시보드·고위험 현황 | DASH-001 | FE | M | P5-WEB-03,P3-BOAPI-01 | 스크리닝/케이스/보고 집계 KPI, bo-api `bo/aml/dashboard` 연동, 드릴다운 | TODO |
| P5-AML-02 | WLF 검토 큐·상세(판정·FP whitelist)·처리 이력 | WLF-001/002/003 | FE | L | P5-WEB-04,P2-AML-03 | POSSIBLE_MATCH/ESCALATED 큐(WLF-001)·scoring breakdown·`/decision` 4-eyes(WLF-002)·fp-whitelist(WLF-002)·**처리 이력 탭**(WLF-003: 결재 이력·판정 결과·시계열 로그) | TODO |
| P5-AML-03 | 명단 소스·임포트 승인 | WL-001/002 | FE | M | P5-WEB-04,P2-AML-01 | source 목록·import diff·`imports/{version}:apply` 4-eyes | TODO |
| P5-AML-04 | RA 분포·모델 활성화·등급 override | RA-001/002/003 | FE | L | P5-WEB-04,P2-AML-04 | score distribution(집계)·모델 activate 4-eyes·`simulate`(결재無)·`override` 4-eyes | TODO |
| P5-AML-05 | 국가위험 등급표·변경 | CTRY-001 | FE | M | P5-WEB-04,P3-AML-02 | country-risk 등급표·`:change` 4-eyes(COUNTRY_RISK)→결재함, RA 재평가 콜아웃 | TODO |
| P5-AML-06 | CDD/EDD 케이스·checklist·periodic review | CDD-001·CASE-001/002 | FE | L | P5-WEB-04,P4-BOAPI-02 | case 큐·timeline·SLA·`:close`/`:reject-relationship` 4-eyes·checklist/periodic policy PUT 4-eyes | TODO |
| P5-AML-07 | TM 알림 적체·시나리오 관리 | TM-001/002 | FE | L | P5-WEB-04,P4-AML-02 | alert backlog·`{scenarioCode}:simulate`·`:activate` 4-eyes·alert→case 전이 | TODO |
| P5-AML-08 | 규제 보고(STR/CTR 후보·제출)·Travel Rule 예외 | REP-001/002·TR-001 | FE | L | P5-WEB-04,P4-BOAPI-01 | 보고 후보·`:submit` 4-eyes(본처리=aml-svc)·travel-rule 필터·`:resolve-exception` 4-eyes. 화면 흐름, 백엔드 완성=P6 | TODO |
| P5-AML-09 | 결재 대기함·감사·소스 시스템·policy pack | APR-001·AUD-001·PP-001 | FE | M | P5-WEB-04,P3-BOAPI-03 | 결재함(공용)·audit export·source-system·`policy-packs:change` 4-eyes(POLICY_PACK) | TODO |
| P5-AML-10 | 고객사 관리 목록 | TNT-001 | FE | M | P5-WEB-03,P3-BOAPI-02 | 고객사 목록 조회·검색·페이징. `deploymentModel`(3종)·`onboardingStatus`(8종) 배지 표시. bo-api `GET /api/v1/bo/aml/tenants` (§9·§3.16). 행 클릭→TNT-002 상세 딥링크 | TODO |
| P5-AML-11 | 고객사 상세(4탭: 기본정보·배포온보딩·소스시스템·정책팩) | TNT-002 | FE | M | P5-WEB-04,P3-BOAPI-02 | ① 기본정보 탭(이름·코드·상태 조회·수정). ② 배포·온보딩 탭: `deploymentModel`(3종) 읽기 전용 + `onboardingStatus`(8종) 상태 표시·이력. 매니지드: `POST .../onboarding/provision` 트리거. self-hosted: 등록 콜백 UI(`POST .../onboarding/register`). 프로비저닝 IaC=P8. ③ 소스시스템 탭. ④ 정책팩 탭(`policy-packs:change` 4-eyes). bo-api `GET/PUT .../tenants/{tenantId}`, `GET/POST .../onboarding` (§9·§3.16) | TODO |
| P5-AML-12 | 고객사 등록(배포 유형+온보딩 신청) | TNT-003 | FE | M | P5-WEB-04,P3-BOAPI-02 | 배포 유형 선택(`MANAGED_DEDICATED`/`SELF_HOSTED`/`SHARED`) + 온보딩 신청 폼. bo-api `POST /api/v1/bo/aml/tenants` (`TenantCreateRequest`). deploymentModel 선택=온보딩 신청, 불변 확인 UX | TODO |

### 2.4 bo-api 화면별 집약 API 완성

| ID | 제목 | 서비스 | 구분 | Effort | 의존 | DoD | Status |
|---|---|---|---|---|---|---|---|
| P5-BOAPI-01 | 화면별 집약/검색/페이지네이션 API 완성·DTO 정합(FDS/AML 미비분) | bo-api | BE+BO | L | P3-BOAPI-01,P4-BOAPI-02 | 각 화면 필터/정렬/페이징, 화면 DTO ↔ 엔진 DTO 매핑, 운영자 집계 소유 경계 유지, 에러코드 패스스루 | TODO |

## 3. 서비스별 분해

- **bo-web**(신규 분해, 별도 WBS 없음): 기능정의서 화면 그룹/흐름(목록→상세→빌더→결재함)을 근거로 P5-FDS-01~08·P5-AML-01~12로 분해. P5-AML-10~12는 PRD §13 재구성본·PPT v5.3 고객사 관리(TNT-001~003, 3화면) 3개 태스크(TNT-001 목록·TNT-002 상세[4탭: 기본정보·배포온보딩·소스시스템·정책팩, 구 TNT-004 온보딩 상태 흡수]·TNT-003 등록). **컴포넌트 공통화 태스크 별도 포함**(P5-WEB-03 라이브러리·P5-WEB-04 결재함 모듈). 화면 ID는 PRD 정본(SFDS-*/AML-*) 1:1.
- **bo-api**(신규 분해): 화면별 집약 API 미비분 완성(P5-BOAPI-01). 운영자 집계는 bo-api 소유, 엔진은 저수준 데이터만.
- **fds-svc/aml-svc**: 본 Phase 신규 로직 없음 — P2~P4 완료 엔진 API를 bo-api 경유로 소비.

## 4. 설계 근거

- 화면 정본: `docs/plan/01-fds-sass-functional-spec.md`(§2~§15, SFDS-* 31화면·상태머신·권한·BR), `docs/plan/02-aml-sass-functional-spec.md`(§2~§13, AML-* 23화면: 기존 20화면 §2~§12-A + TNT-001~003 §13 고객사 관리 3화면, PRD §13 재구성본·PPT v5.3).
- bo-web 스택·경계: `target-architecture.md` §3.4(bo-api만 호출), `docs/design/api/01-fds-api.md` §11(화면↔API)·§12, `docs/design/api/02-aml-api.md` §6/§9.
- 공통화·시각 정본: PRD 짝 PPT(`BO-FDS-SASS-Planning_v4.0.pptx`·`BO-AML-SAAS-Planning_v4.0.pptx`) archetype(대시보드/목록/상세/폼/결재함).

## 5. DoD / Exit

- **태스크 DoD**: `bo-web` build·ESLint/Prettier 0·tsc strict 0·리뷰 높음 0 + PRD 화면 정의 1:1. 횡단: data-scope 권한 가드, raw PII 화면 미표시(BE 마스킹 소비), traceId 전파, **컴포넌트 공통화**(중복 표 구현 금지) 정합.
- **Phase Exit (M4)**:
  1. FDS 31 + AML 23(기존 20 + TNT-001~003 3화면: 목록·상세[4탭]·등록) = 전 화면이 bo-api 연동으로 렌더·동작.
  2. 핵심 흐름(대시보드 드릴다운→목록→상세→룰/시뮬레이션 빌더→4-eyes 결재함→실행 결과) 끊김 없이 연결.
  3. 4-eyes 화면(룰 활성·그룹·매핑·케이스 종결·국가위험·policy pack·보고·Travel Rule)이 결재함 공용 모듈로 일관 처리.
  4. 규제 후보 화면이 책임 경계(보고 본처리=aml-svc) 준수 — FDS REG 화면은 위임 흐름·읽기전용 딥링크만.
  5. 공통 컴포넌트 라이브러리로 화면 일관성 확보(enum 표시값 단일 매핑).

## 6. 의존 그래프

```mermaid
flowchart TD
    W1[P5-WEB-01 앱셸/Context] --> W2[P5-WEB-02 api/react-query]
    W2 --> W3[P5-WEB-03 공통 컴포넌트]
    W3 --> W4[P5-WEB-04 결재함 모듈]
    W3 --> FDS[FDS 화면군 P5-FDS-01~08]
    W4 --> FDS
    W3 --> AML[AML 화면군(비-TNT) P5-AML-01~09]
    W4 --> AML
    W3 --> TNT[AML 고객사 관리 P5-AML-10~12\nTNT-001목록·TNT-002상세4탭·TNT-003등록]
    W4 --> TNT
    B1[P5-BOAPI-01 집약 API 완성] --> FDS
    B1 --> AML
```

**병렬 가능 그룹**: 공통(W1→W2→W3→W4) 선행 후 {FDS 화면군}·{AML 화면군}을 화면별로 대량 병렬. 화면 내 의존은 해당 bo-api 집약 API 준비도에 종속.

## 변경 이력
| 일자 | 변경 |
|---|---|
| 2026-06-08 | **TNT 화면 구조 변경(4화면→3화면) 정합화** (정본=PRD §13 재구성본·PPT v5.3). 헤더·§1·§2.3·§3·§4·§5·§6 전체: AML 24화면→23화면, TNT-001~004 4화면→TNT-001~003 3화면(상세 TNT-002에 4탭: 기본정보·배포온보딩·소스시스템·정책팩, 구 TNT-004 온보딩 상태 흡수). §2.3 P5-AML-10(TNT-001 목록 단독)·P5-AML-11(TNT-002 상세 4탭, 구 TNT-004 온보딩 프로비저닝·self-hosted 등록·이력 흡수)·P5-AML-12(TNT-003 등록) 태스크 재매핑. mermaid TNT 노드 레이블 명확화. |
| 2026-06-08 | **doc-consistency(aml:roadmap-design-prd) §1 범위 포함 고객사 관리 누락 정합화** (정본=§2.3·§5·PRD §13 v5.0 TNT-001~004). §1 AML 화면 그룹 열거에 `· 고객사 관리(TNT-001~004 4화면: 목록/상세·등록·온보딩 상태)` 추가. §2.3·§3·§5·헤더·개요 §2와 일치. | task-planner |
| 2026-06-08 | **doc-consistency(aml:roadmap-sw-prd) 담당 이격 정합화** (정본=PRD §13 v5.0·API §6/§9/§3.16·target-architecture §4.1). **(1) 헤더·§1·§4·§5** "AML 20화면"→"AML 24화면(20화면 + TNT-001~004 고객사 관리 4화면)"으로 전면 갱신. PRD v5.0 §13 TNT 추가분(고객사 목록/상세·등록·온보딩 상태) 반영. **(2) §2.3** 섹션 제목 `AML 화면(20)`→`AML 화면(24)`, 서두 주석 추가. P5-AML-10(TNT-001/002 목록상세)·P5-AML-11(TNT-003 등록)·P5-AML-12(TNT-004 온보딩 상태) 3개 태스크 신규 추가. DoD에 `deploymentModel`/`onboardingStatus` 필드·API §9·§3.16·온보딩 프로비저닝 P8 위임 명시. **(3) §3** 분해 P5-AML-01~09→P5-AML-01~12, TNT 3개 태스크 설명 추가. **(4) §6** 의존 그래프에 AML 고객사 관리 P5-AML-10~12 노드 추가. 개요 §2·§3 P1 aml칸과 동기화 완료. |
| 2026-06-08 | **FDS 격리 → 배포 모델 재설계** 반영(PRD TNT-003, API v1.5 §11.2, integration v1.5, target-architecture §4.1). P5-FDS-02 고객사 관리 화면(TNT-003) DoD에서 '격리 방식(DB 분리/스키마 분리/공유) 라디오' 제거 → '배포 유형 선택(`deployment_model` 3종)+온보딩 신청'·'온보딩 상태(읽기 표시, `onboarding_status` 8종)'로 교체. 호출 대상 bo-api(`/api/v1/bo/fds/tenants/**`). 상세 온보딩 프로비저닝 워크플로(provision/상태/register 마법사)는 P8-WEB-01 위임. P8-WEB-01·fds T-03/T-22와 정합. |
| 2026-06-07 | P5 백오피스 프론트 Phase 태스크 신규 작성(개요 §2 P5·M4). PRD 화면 그룹/흐름 근거로 FDS 31·AML 20화면 분해 + 공통 컴포넌트/결재함 모듈 별도 태스크 + bo-api 화면별 집약 완성. bo-web=bo-api만 호출 경계 준수. |
| 2026-06-08 | #60 P5-AML-02 화면 ID `WLF-001/002`→`WLF-001/002/003`으로 확장, DoD에 처리 이력 탭(WLF-003) 추가(결재 이력·판정 결과·시계열 로그). #64 §1 AML 화면 그룹 열거에 WLF 화면 3종 명칭(WLF-001/002/003) 보강. |
