# AML 서비스 문서 정합성 리포트

**대상 서비스**: aml  
**생성일**: 2026-06-12  
**판정**: **FAIL**  
**심각도별 요약**: 높음(high) 17건 · 중간(medium) 30건 · 낮음(low) 23건  
**미검증 쌍**: 0개  
**총 이격 건수**: 70건

---

## ① 판정

> **FAIL** — 높음(high) 17건 포함. 개발 착수 전 필수 교정 필요.

---

## ② 심각도별 요약

| 심각도 | 건수 | 주요 영역 |
|--------|------|-----------|
| **높음(high)** | **17** | RISK_OVERRIDE 방향 모순, completeness_status 트리거 조건 불일치, STR :submit 결재 role, aml.report.sla.breached 관측성 미등재, P5 화면 수(31 vs 23) 8화면 이격, 06-phase5-bo-web.md PRD v5.9 고정, §12-B 신규 6개 화면 WBS 미등재, aml_tenants DDL retention_policy·감사컬럼 누락 |
| **중간(medium)** | **30** | kyc_status enum 역삽입 미이행, CustomerProfileDto 필드 누락(country/source_system/onboarding_at), JSONB 하위 구조 미정의, ApprovalDto DRAFT 제외 근거 주석 미비, UseCase 명칭 누락·불일치, PRD 신규 화면 API 미정의(AML-IRA-001·AML-WL-003·AML-STAT-001·AML-EDU-001), 결재 상태머신 DRAFT 표기, AML-CDD-002 scope 오류, RA 모델 활성화 경로변수 오타, audit export 엔드포인트 누락, fds.feedback.applied 이벤트 미등재, 로드맵 P2 T-12 한정자 누락 등 |
| **낮음(low)** | **23** | retention_policy 역삽입, data_scope 감사 컬럼 표기, aml_outbox API 미노출 명문화, account.suspended 카탈로그 누락, schema_version NOT NULL 명시, history_slide 요약 원칙 위반, WBS D-03/D-14 누락·오류, high-risk registry 태스크 미반영, WBS §4 병렬 그룹 Phase 표기 등 |

---

## ③ 대조쌍별 이격 표

### 대조쌍: aml:design-db (설계서 ↔ DB 설계서)

| 심각도 | 서비스 | 항목 | 이격 내용 | 위치 | 권고 |
|--------|--------|------|-----------|------|------|
| medium | aml | aml_customers.kyc_status enum (5종) | DB §5.25가 kyc_status 5종을 확정했으나 설계서 §13.1 CDD 본문에 해당 enum 정의 없음. DB §5.25 역삽입 권고 주석 미이행 상태. | 상위: docs/software/02-amlSvc-sass.md §13.1 / 파생: docs/design/db/02-aml-db.md §3.3, §5.25 | 설계서 §13.1 CDD(또는 §9.1 Customer type 하위)에 kyc_status 상태머신(5종: PENDING→VERIFIED/INCOMPLETE/EXPIRED/REJECTED)과 aml_customers.kyc_status 컬럼 매핑을 역삽입. 정본: DB §5.25. |
| low | aml | aml_tenants.retention_policy 컬럼 | DB §3.1에 retention_policy JSONB NOT NULL DEFAULT '{}' 존재. 설계서 §16.2는 data retention을 tenant 설정으로 나열하지만 §17.1 DDL에는 해당 컬럼 없음. policy_pack_code 등 다른 운영 컬럼은 포함되어 일관성 없음. | 상위: docs/software/02-amlSvc-sass.md §17.1, §16.2 / 파생: docs/design/db/02-aml-db.md §3.1, §6 | 설계서 §17.1 aml_tenants DDL에 retention_policy JSONB NOT NULL DEFAULT '{}'를 추가하고 §16.2에 'tenant별 보존 override 컬럼 = aml_tenants.retention_policy(DB §3.1)' 참조 명시. |

---

### 대조쌍: aml:db-api (DB 설계서 ↔ API 명세서)

| 심각도 | 서비스 | 항목 | 이격 내용 | 위치 | 권고 |
|--------|--------|------|-----------|------|------|
| medium | aml | aml_customers.country / CustomerProfileDto | DB §3.3에 country VARCHAR(8) 존재. API §3.9 CustomerProfileDto에 country 필드 없음. CDD/EDD 증거 프로필 응답에서 국적 정보 누락. | DB §3.3 vs API §3.9 | CustomerProfileDto에 country 필드(string, nullable, ISO 국가코드) 추가 또는 내부 전용 명문화. 정본: DB §3.3. |
| medium | aml | aml_customers.source_system / CustomerProfileDto | DB §3.3에 source_system VARCHAR(64) 존재. API §3.9 CustomerProfileDto에 대응 필드 없음. | DB §3.3 vs API §3.9 | CustomerProfileDto에 sourceSystem 필드 추가 또는 미노출 결정 명문화. 정본: DB §3.3. |
| medium | aml | aml_customers.onboarding_at / CustomerProfileDto | DB §3.3에 onboarding_at TIMESTAMPTZ 존재. API §3.9 CustomerProfileDto에 onboardingAt 필드 없음. | DB §3.3 vs API §3.9 | CustomerProfileDto에 onboardingAt 필드(string date-time, nullable) 추가 또는 미노출 결정 명시. 정본: DB §3.3. |
| low | aml | aml_customers.data_scope / CustomerProfileDto | DB §3.3에 data_scope 공통 컬럼 존재. API §3.9에 dataScope 없음. AlertDto 주석에는 감사 컬럼 생략이 명시되나 CustomerProfileDto에는 미명시. | DB §3.3 vs API §3.9 | CustomerProfileDto 설명에 'data_scope 등 감사 컬럼은 응답에서 생략' 명시 또는 AlertDto 주석과 통일. |
| medium | aml | aml_screening_results.score_breakdown(JSONB) vs ScreenResponse.scoreBreakdown 타입 | DB §3.8 score_breakdown JSONB는 name/dob/country/document/address/relationship 분해 설명. API §3.2 ScreenResponse scoreBreakdown은 object 타입으로만 선언, 하위 구조 미정의. | DB §3.8 vs API §3.2, §5 | OpenAPI §5 ScreenResponse.scoreBreakdown 하위 속성(name, dob, country, document, address, relationship)을 명시하거나, DB §3.8 매핑 주석 추가. |
| medium | aml | aml_risk_scores.factor_breakdown(JSONB) vs RiskScoreResponse.factorBreakdown 타입 | DB §3.9 factor_breakdown JSONB는 'factor별 점수·근거' 설명. API §3.3 RiskScoreResponse factorBreakdown은 object 타입으로만 선언, schema 미정의. | DB §3.9 vs API §3.3, §5 | API §3.3 RiskScoreResponse.factorBreakdown 하위 구조를 OpenAPI schema에 추가하거나 DB §3.9 매핑 명시. |
| medium | aml | aml_approvals.status enum — DRAFT 포함(DB) vs DRAFT 제외(API) | DB §3.15 aml_approvals.status enum은 DRAFT 포함 8종. API §3.7 ApprovalDto.status는 DRAFT 제외 7종(§1.5에서 내부 전이 명시). 의도적 불일치이나 DB §3.15에 주석 미비. | DB §3.15 vs API §3.7 | DB §3.15 aml_approvals 테이블 status 컬럼에 'DRAFT는 DB 내부 전이 상태로 API 노출 제외(§1.5)' 주석 추가. |
| low | aml | aml_cases.source_origin 컬럼 누락 | API §3.5 CaseDto의 originFdsCaseRef 설명에 'source_origin=FDS 시 채움'이라고 명시. 그러나 DB §3.11 aml_cases에 source_origin 컬럼 없음(aml_alerts §3.10에만 존재). | DB §3.11 vs API §3.5 | DB §3.11에 source_origin 컬럼 실제 존재 여부 확인. 없다면 API §3.5 설명을 'origin_fds_case_ref IS NOT NULL 시 채움'으로 수정. 정본: DB §3.11. |
| low | aml | aml_outbox 테이블 — API 응답 DTO 미정의 | DB §3.15에 aml_outbox 정의. API §2, §3에 outbox 상태 조회·응답 DTO·엔드포인트 없음. 내부 dispatch 전용 의도로 보이나 명문화 없음. | DB §3.15 vs API §2 | API §2 또는 §9에 'aml_outbox는 내부 트랜잭셔널 아웃박스 전용으로 외부 API 미노출' 주석 추가. |
| low | aml | aml_canonical_events.payload(JSONB) vs IngestEventRequest.payload(object) — 타입 명칭 일치하나 schema 미정의 | DB §3.15 payload NOT NULL, API §3.1 payload 필수(R). PII 제약 표현 차이는 의미상 일치. 그러나 eventType별 payload schema가 양 문서 모두 미정의. | DB §3.15 vs API §3.1 | DB §3.15 또는 API §3.1에 eventType별 payload 구조를 최소 참조 링크 수준으로 명시. |

---

### 대조쌍: aml:design-api (설계서 ↔ API 명세서)

| 심각도 | 서비스 | 항목 | 이격 내용 | 위치 | 권고 |
|--------|--------|------|-----------|------|------|
| medium | aml | SW §6.2 usecase/ 목록 — ManageCaseUseCase 누락 | SW §6.2 usecase/ 목록에 ManageCase 없음. port/in/에는 ManageCaseUseCase 명시. API §2.7 cdd/cases 엔드포인트는 ManageCaseUseCase를 진입점으로 함. usecase/ ↔ port/in/ 1:1 매핑 파괴. | docs/software/02-amlSvc-sass.md §6.2 line 367-370 | SW §6.2 usecase/ 주석에 ManageCase 추가 또는 ManageCddEdd를 ManageCase로 명칭 통일하고 CDD/EDD 세부 유스케이스임을 명시. |
| medium | aml | SW §6.2 usecase/ 목록 — ManagePolicyUseCase 누락 | SW §6.2 usecase/ 목록에 ManagePolicyUseCase 없음. port/in/ (line 375)에는 ManagePolicyUseCase 명시. API §2.7 cdd/checklists·cdd/periodic-review-policy 엔드포인트는 이 UseCase 요구. | docs/software/02-amlSvc-sass.md §6.2 line 367-370 | SW §6.2 usecase/ 주석에 ManagePolicy 추가하여 port/in/ ManagePolicyUseCase와 1:1 매핑 복원. |
| low | aml | SW §6.2 usecase/ vs port/in/ 명칭 스타일 불일치 (UseCase suffix) | usecase/ 블록은 UseCase suffix 없음. port/in/ 블록은 UseCase suffix 일관 사용. 동일 §6.2 내 명칭 비대칭. API §3.8 주석은 port/in/ 명칭 기준. | docs/software/02-amlSvc-sass.md §6.2 line 367-377 | usecase/ 블록 명칭을 port/in/ 명칭(UseCase suffix)과 통일하거나, usecase/=구현 클래스·port/in/=인터페이스 구분 주석 추가. |
| low | aml | SW §11.2 requiredAction — enum 코드값 미기재 | SW §11.2 requiredAction이 자연어('CDD update, EDD, relationship review')로 기재. API §3.3은 DB §5.26 enum 4종(CDD_UPDATE/EDD/RELATIONSHIP_REVIEW/NONE) SCREAMING_SNAKE_CASE로 명시. SW에 NONE 값 누락. | docs/software/02-amlSvc-sass.md §11.2 line 678 | SW §11.2 requiredAction 행의 설명을 DB §5.26 코드값(CDD_UPDATE/EDD/RELATIONSHIP_REVIEW/NONE)으로 교체 또는 병기. |
| low | aml | SW §6.2 변경이력 2026-06-10 — stale scope 코드 잔존 | 변경이력 2026-06-10 항목이 'aml:case:write', 'aml:approval:*'를 기록. API §1.1 정본은 aml:case:update, aml:admin:approval. 본문은 정합이나 이력 내 구 코드 잔류로 독자 혼동 유발. | docs/software/02-amlSvc-sass.md 변경이력 2026-06-10 행 | 변경이력 2026-06-10 scope 표기를 aml:case:update/aml:admin:approval로 수정하거나 '2026-06-11 정정됨' 주석 추가. |

---

### 대조쌍: aml:design-integration (설계서 ↔ 연동 명세서)

| 심각도 | 서비스 | 항목 | 이격 내용 | 위치 | 권고 |
|--------|--------|------|-----------|------|------|
| **high** | aml | RISK_OVERRIDE subjectType 방향·의미 | SW §13.4: RISK_OVERRIDE = '고위험 등급 수동 하향(override)'. Integration §8.3: RISK_OVERRIDE(→HIGH) → 아웃박스 aml.customer.high_risk 전파. SW는 '하향' 방향, 연동은 '→HIGH(상향)' 방향 표기 — 방향 모순. SW가 정본이므로 Integration §8.3이 오류. | 상위: docs/software/02-amlSvc-sass.md §13.4 / 파생: docs/design/integration/02-aml-integration.md §8.3 | Integration §8.3 RISK_OVERRIDE 행을 SW §13.4 정의에 맞춰 수정. '(→HIGH)' 표기 제거, 하향 확정 시 FDS 효과(제거 이벤트 또는 audit만 발행)를 SW §13.4·§15.8과 함께 재정의. |
| medium | aml | 아웃박스 event_type 예시 — fds.feedback.applied 미정의 이벤트 타입 | Integration §8.1 outbox event_type 예시에 'fds.feedback.applied' 기재. 그러나 SW §12.3 및 §3.3 아웃바운드 카탈로그 어디에도 이 이름이 없음. 실제 FDS_FEEDBACK 아웃바운드 eventType은 §3.3 3종뿐. | 파생: docs/design/integration/02-aml-integration.md §8.1 | Integration §8.1 outbox event_type 예시를 §3.3 정본 3종(aml.screening.true_match·aml.customer.high_risk·aml.case.str_recommended)으로 수정, 미정의 'fds.feedback.applied' 삭제. |
| low | aml | account.* 이벤트 카탈로그 — account.suspended 누락 | SW §8.1: account.* = created/suspended/closed 3종 verb. Integration §3.1: account.created/account.closed 2종만 정의, account.suspended 누락. | 상위: docs/software/02-amlSvc-sass.md §8.1 / 파생: docs/design/integration/02-aml-integration.md §3.1 | Integration §3.1 account.* 섹션에 account.suspended 행 추가(발행자·핵심 페이로드 키·후속 usecase 포함). |

---

### 대조쌍: aml:dbapi-integration (DB·API ↔ 연동 명세서)

| 심각도 | 서비스 | 항목 | 이격 내용 | 위치 | 권고 |
|--------|--------|------|-----------|------|------|
| **high** | aml | completeness_status exception 큐 트리거 조건 | DB §5.15·§5.22 note: completeness_status=INCOMPLETE 단일 값. Integration §9.3: completeness_status∈{MISSING_ORIGINATOR, MISSING_BENEFICIARY, INCOMPLETE} 3종 트리거. DB §5.22 enum 정의(4종)와 Integration §4.3 note도 3종 확인. DB §5.15/§5.22 note가 좁음. 정본: Integration §9.3. | DB: docs/design/db/02-aml-db.md §5.22 note, §5.15 note / Integration: docs/design/integration/02-aml-integration.md §9.3 | DB §5.15 note와 §5.22 note를 'completeness_status∈{MISSING_ORIGINATOR, MISSING_BENEFICIARY, INCOMPLETE}' 3종으로 확장. |
| low | aml | aml_canonical_events schema_version 컬럼 NOT NULL vs envelope sourceSchemaVersion 필수(Y) — 명시 수준 차이 | DB §3.15 schema_version NOT NULL이나 표 형식상 제약 컬럼 없어 Integration §4.1 필수(Y) 표현 대비 명시 수준 낮음. 실질 불일치 없음. | DB: docs/design/db/02-aml-db.md §3.15 / Integration: docs/design/integration/02-aml-integration.md §4.1 | DB §3.15 aml_canonical_events 컬럼 표에 schema_version NOT NULL 제약 및 Integration 매핑 참조 주석 보강. |
| low | aml | settlement.executed 이벤트 핵심 페이로드 키 payoutAccountHash — DB 컬럼 미매핑 | Integration §3.1에서 settlement.executed 핵심 페이로드 키로 payoutAccountHash 열거. DB §3 전체에 payout_account_hash 컬럼 없음. Integration §7.2 필드매핑 표에도 매핑 행 없음. | Integration: docs/design/integration/02-aml-integration.md §3.1 / DB: docs/design/db/02-aml-db.md §3 전체 | Integration §7.2 필드매핑 표에 settlement.payoutAccountHash → payload.*.accountHash(HMAC) → canonical event payload JSONB 경로를 추가. |

---

### 대조쌍: aml:api-prd (API 명세서 ↔ PRD 기능정의서)

| 심각도 | 서비스 | 항목 | 이격 내용 | 위치 | 권고 |
|--------|--------|------|-----------|------|------|
| **high** | aml | AML-TNT-002 ① 기본 정보 탭 — reportingInstitution 필드 | PRD v7.0에서 reportingInstitution 필드를 화면에 표시 명시. API §3.16 TenantDto, §5 OpenAPI, §9 bo-api 엔드포인트, §6 정합 표 어디에도 해당 필드·엔드포인트 없음. API가 정본이며 PRD가 API 대비 선행. | PRD §13.2 ① 기본 정보 탭 / 부록 E v7.0 | API §3.16 TenantDto에 reportingInstitution 객체 필드 추가 또는 PRD 해당 항목에 '미확정 — API 정합 전까지 화면 미노출' 상태 명기. |
| **high** | aml | AML-IRA-001 — GET/POST .../ira/reports, IRA_SUBMIT subjectType | PRD §12-B.2는 /ira/reports 엔드포인트 군과 IRA_SUBMIT subjectType 사용 명시. API §2 엔드포인트 표, §3.7 subjectType enum 16종, §10 4-eyes 결재 트리거 표 어디에도 없음. | PRD §1.2 화면 범위 표(AML-IRA-001 행), §12-B.2, 부록 A·C | API §2.7에 IRA 엔드포인트 군 추가 및 §3.7 subjectType에 IRA_SUBMIT 추가(16→17종) 또는 PRD를 '제안 — 후속 API 정합 필요' 상태로 명기. |
| **high** | aml | AML-WL-003 — POST .../entries:draft, GET/POST .../fp-whitelist, POST .../fp-whitelist/{id}:revoke | PRD §12-B.5는 수기 등록·면제 현황 조회·면제 해제 엔드포인트를 호출 명시. API §2.7에는 POST .../fp-whitelist(등록)만 존재. GET 면제 현황·entries:draft·revoke 미정의. | PRD §1.2(AML-WL-003 행), §12-B.5, 부록 A | API §2.7에 GET /fp-whitelist, POST .../entries:draft, POST .../fp-whitelist/{id}:revoke 추가 또는 PRD를 제안 상태로 명확화. |
| medium | aml | AML-TNT-002 ③ 소스 시스템 탭 — sourceType 표시값(CORE/TRANSACTION/KYC) | PRD §13.2 ③ 탭의 종류 컬럼이 CORE/TRANSACTION/KYC로 표기. API §3.9 SourceSystemDto의 ingestMode(DB §5.14)는 REST/큐/폴링/변경수집/스냅샷/벤더브릿지이며, CORE/TRANSACTION/KYC enum은 API·DB 어디에도 없음. | PRD §13.2 ③ 소스 시스템 탭 | PRD §13.2 ③ 탭 종류 컬럼을 API §3.9 실제 필드(ingestMode, authMode)로 정정 또는 API에 sourceCategory 필드 추가. |
| medium | aml | AML-STAT-001 — GET /api/v1/bo/aml/stats/str, GET .../stats/scenarios | PRD §12-B.3이 두 엔드포인트 호출 명시. API §9 bo-api 소유 엔드포인트 표에 없음. PRD 자체는 '제안 — 후속 API 정합 필요' 표기이나 부록 A는 확정된 것처럼 기술, 일관성 없음. | PRD §1.2(AML-STAT-001 행), §12-B.3, 부록 A | API §9에 STR·룰 효과성 집계 엔드포인트 추가 또는 PRD 부록 A·§12-B.3 전체에 '제안 — 후속 API 정합 필요' 일관 표기. |
| medium | aml | AML-EDU-001 — GET/POST /api/v1/bo/aml/training/courses 등 | PRD §12-B.4가 /training/courses·/training/records·/certifications 엔드포인트 호출 명시. API §9 bo-api 엔드포인트 표에 없음. | PRD §1.2(AML-EDU-001 행), §12-B.4, 부록 A | API §9에 교육·자격 관리 엔드포인트 추가 또는 PRD 전체(§12-B.4·부록 A)에 '제안 — 후속 API 정합 필요' 일관 표기. |
| medium | aml | AML-RA-001 — 고위험 목록 개별 고객 위험 조회 API 경로 prefix 불일치 | PRD §12-A.4 AML-RA-003 API 항목이 GET /aml/customers/{customerRef}/risk로 /api/v1/ prefix 누락. API §2.3 및 부록 A는 GET /api/v1/aml/customers/{customerRef}/risk로 일치. | PRD §5.1, §12-A.4, 부록 A AML-RA-001 행 | PRD §12-A.4 AML-RA-003의 API 표기를 GET /api/v1/aml/customers/{customerRef}/risk로 정정. |
| medium | aml | 결재 approval_status 상태 머신 — PRD §1.7의 DRAFT 전이 표시 | PRD §1.7 mermaid 다이어그램에 [*]→DRAFT, DRAFT→SUBMITTED 포함. API §1.5·§3.7은 DRAFT를 내부 상태로 미노출 명시. API가 정본. 단 PRD §1.7 하단 상태 목록에는 DRAFT 없으므로 다이어그램만 불일치. | PRD §1.7 결재 상태 머신(mermaid), API §1.5, §3.7 ApprovalDto | PRD §1.7 mermaid에서 [*]→DRAFT·DRAFT→SUBMITTED 전이를 제거, [*]→SUBMITTED(API §1.5 정본)로 수정. |
| medium | aml | AML-CDD-002 — GET /aml/customers/{ref}/profile scope 오류 | PRD §1.4 권한 매핑의 AML-CDD-002 scope = aml:case:read. API §2.5에서 해당 엔드포인트 required scope = aml:evidence:export. 불일치. API §2.5가 정본. | PRD §12-B.7, §1.4 권한 매핑, 부록 B | PRD §1.4 AML-CDD-002 scope를 aml:case:read → aml:evidence:export로 정정. 부록 B 해당 행도 동일 수정. |
| low | aml | AML-RA-002 — 시뮬레이션 응답 필드 gradeShift·falsePositiveImpact·simulationId 암묵적 매핑 | PRD §6.1 ③ 시뮬레이션 탭 화면 레이아웃 수치 표시는 API §3.15 gradeShift·falsePositiveImpact.deltaPercent와 매핑 가능하나 PRD 데이터 항목 표에 API 필드명 미기재. 매핑이 암묵적. | PRD §6.1 AML-RA-002 ③ 시뮬레이션 탭, API §3.15 SimulationResponse | PRD §6.1 ③ 탭 데이터 항목 표에 gradeShift·falsePositiveImpact.deltaPercent·simulationId 등 API §3.15 필드명 괄호 병기. |
| low | aml | AML-TNT-001 목록 화면 — 배포 유형별 집계 숫자 표시 근거 미명시 | PRD §13.1 화면 레이아웃에 배포 유형별 집계 숫자 표시 컴포넌트 존재. API §5 GET /api/v1/bo/aml/tenants 응답 스키마는 TenantDto 배열·PageMeta만 정의, 배포 유형별 집계 필드 없음. 클라이언트 파생인지 API 추가 필드인지 미명시. | PRD §13.1, API §5 OpenAPI | PRD §13.1 BR 또는 데이터 항목 표에 해당 집계가 클라이언트 파생인지 별도 집계 API가 필요한지 명시. 후자라면 API §9에 집계 엔드포인트 추가. |

---

### 대조쌍: aml:prd-ppt (PRD 기능정의서 ↔ PPT 기획서)

| 심각도 | 서비스 | 항목 | 이격 내용 | 위치 | 권고 |
|--------|--------|------|-----------|------|------|
| medium | aml | AML-RA-003 ① 고객 프로필 아웃바운드 트리거 누락 | PRD v7.0 AML-RA-003 ①에 '[고객 프로필 ▶ → AML-CDD-002]' 트리거 명시. PPT v6.0 AML-RA-003 슬라이드에 해당 트리거 없음. | docs/plan/02-aml-sass-functional-spec.md AML-RA-003 §(v7.0) / BO-AML-SAAS-Planning_v6.0.pptx AML-RA-003 슬라이드 | PPT v7.0 AML-RA-003 슬라이드에 '[고객 프로필 ▶ → AML-CDD-002]' 네비게이션 트리거 추가. |
| medium | aml | AML-CASE-002 ① 타임라인 — 고객 프로필 아웃바운드 트리거 누락 | PRD v7.0 AML-CASE-002 ① 타임라인에 '[고객 프로필 ▶ → AML-CDD-002]' 트리거 명시. PPT v6.0에 없음. | docs/plan/02-aml-sass-functional-spec.md AML-CASE-002 ①(v7.0) / BO-AML-SAAS-Planning_v6.0.pptx AML-CASE-002 ① 슬라이드 | PPT v7.0 AML-CASE-002 ① 슬라이드에 '[고객 프로필 ▶ → AML-CDD-002]' 트리거 추가. |
| medium | aml | AML-WLF-003 처리 이력 — 면제 현황 아웃바운드 트리거 누락 | PRD v7.0 AML-WLF-003에 '[면제 현황 ▶ → AML-WL-003 ②]' 트리거 명시. PPT v6.0에 없음. | docs/plan/02-aml-sass-functional-spec.md AML-WLF-003(v7.0) / BO-AML-SAAS-Planning_v6.0.pptx AML-WLF-003 슬라이드 | PPT v7.0 AML-WLF-003 슬라이드에 '[면제 현황 ▶ → AML-WL-003 ②]' 트리거 추가. |
| low | aml | 화면 수 불일치: PRD 31화면 vs PPT 28화면 | PRD v7.0 §1.2 총 31화면 선언. PPT v6.0 커버 28화면 표기. 신설 3화면(AML-WL-003·AML-HRR-001·AML-CDD-002) 차이. | docs/plan/02-aml-sass-functional-spec.md §1.2 / BO-AML-SAAS-Planning_v6.0.pptx 커버 | PPT v7.0 커버 슬라이드 화면 수를 31로 갱신하고 신설 3화면 슬라이드 추가. |

---

### 대조쌍: aml:ppt-flow (PPT 슬라이드 생성기 ↔ PRD 화면 흐름)

| 심각도 | 서비스 | 항목 | 이격 내용 | 위치 | 권고 |
|--------|--------|------|-----------|------|------|
| **high** | aml | AML-WLF-001 / AML-WL-001 ① — [시뮬레이션] 버튼 → AML-WLF-004 아웃바운드 트리거 누락 | PRD §12-B.1 진입 선언: AML-WLF-001 상단·AML-WL-001 ① [시뮬레이션] 버튼으로 WLF-004 진입. wlf_001(), wl_001(tab=0) 함수 어디에도 AML-WLF-004 아웃바운드 참조 없음. | generate_aml.py: wlf_001() (line ~281), wl_001(tab=0) (line ~453) | wlf_001()의 callout 또는 table_block 타이틀에 '[시뮬레이션 ▶ → AML-WLF-004]' 추가. wl_001(tab=0) 소스 목록 행에도 동일 추가. |
| medium | aml | AML-WLF-001 하단 상세 — [고객 프로필 ▶ → AML-CDD-002] 아웃바운드 트리거 누락 | PRD §12-B.7 진입 선언: AML-WLF-001 하단 상세에서 [고객 프로필 ▶] 클릭으로 CDD-002 진입. wlf_001()에 '고객 프로필' 또는 'AML-CDD-002' 참조 전혀 없음. ra_003·case_002는 정상 포함. | generate_aml.py: wlf_001() 함수 전체 | wlf_001()의 master-detail 하단 callout 또는 info_panel에 '[고객 프로필 ▶ → AML-CDD-002]' 트리거 추가. |
| medium | aml | AML-CDD-002 드릴다운이 소스 화면 AML-CASE-002보다 14슬라이드 앞에 배치 — PPT 흐름 단절 | CDD-002(슬라이드 28-29)가 두 번째 소스 CASE-002(슬라이드 43-46)보다 14슬라이드 앞. 드릴다운이 소스보다 먼저 등장하는 역순 구조. | generate_aml.py SCREENS list: cdd_002 슬라이드 28-29 / case_002 슬라이드 43-46 | CDD-002 슬라이드를 CASE-002 직후에 추가 배치하거나, PRD §12-B.7 진입 선언에서 CASE-002 ①를 제외하고 RA-003 ① 전용 드릴다운으로 정정. |
| low | aml | history_slide 변경이력 행 v5.5·v5.11 — 한 줄 요약 원칙 위반(장문) | backoffice-planner SKILL §1.6·원칙 7은 변경이력 행을 한 줄 요약으로 요구. v5.5(118자)·v5.11(98자) 행이 장문으로 원칙 위반. | generate_aml.py build() 함수: history_slide rows (line 2178~2202) | v5.5 행을 '멀티탭 상세/플로우 화면 탭 연속 전개 — 13화면 확장(슬라이드 29→53)' 수준으로 단축. v5.11 행을 'QA 정합화: TM-001 탭 명칭·WLF-003 KPI 카드 순서 정정' 수준으로 요약. |

---

### 대조쌍: aml:design-wbs (설계서 ↔ WBS 태스크)

| 심각도 | 서비스 | 항목 | 이격 내용 | 위치 | 권고 |
|--------|--------|------|-----------|------|------|
| medium | aml | T-21 태스크 표 제목 — Legacy Vendor Bridge 지원 모드 3종 누락 | WBS §2 T-21 제목에 alert ingest·dual-run·reconciliation 3종만 기재. 설계서 §15.5는 5종 모드(Vendor Alert Ingest·Vendor DB Export Adapter·Dual Run·Shadow Case·Rule/Model Migration) 정의. WBS 표 제목 vs 상세 파일 간 이격. | WBS docs/tasks/aml/00-overview.md §2 T-21 / 설계서 docs/software/02-amlSvc-sass.md §15.5 | WBS §2 T-21 행 제목에 'Vendor DB Export Adapter·Shadow Case·Rule/Model Migration'을 추가하거나 '(§15.5 5종 모드 전수)' 주석 추가. |
| medium | aml | WBS §4 Phase 매핑 노트의 설계 §21 Phase 1~5·7 미명시 | WBS §4는 '전수 매핑 종결' 선언이나 Phase 0·6·8·9만 명시. Phase 1(Tenant/identity)·2(WLF MVP)·3(RA+CDD/EDD)·4(TM)·5(Regulatory)·7(Audit Evidence Hub) 6개 매핑 없음. | WBS docs/tasks/aml/00-overview.md §4 / 설계서 docs/software/02-amlSvc-sass.md §21 | WBS §4 Phase 매핑 주석에 누락된 6개 Phase의 WBS 대응 관계 명시. '전수 매핑 종결' 선언은 추가 이후에만 유지. |
| medium | aml | 설계 §21 Phase 4 'FDS decision 연계' vs WBS T-15 배치 Phase(P6) | 설계 §21 Phase 4는 FDS decision 연계를 포함. WBS T-14(TM 엔진)는 P2/P4, FDS 연동 T-15는 P6로 분리. 분리 배경 설명 없음. | WBS docs/tasks/aml/00-overview.md §4 / 설계서 docs/software/02-amlSvc-sass.md §21 Phase 4 | WBS §4에 'T-14 TM 엔진은 설계 Phase 4이나 FDS decision 연계는 T-14 완성 후 의존성으로 T-15(P6)로 분리' 주석 추가. |
| low | aml | WBS §7 오픈 결정 D-03(RA DSL) 누락 | 설계서 §22 D-03('자체 factor model/JSON logic/CEL')은 미확정 오픈 결정. WBS §7에 D-01·D-02·D-04·D-05·D-07·D-10·D-14는 등재되나 D-03 누락. T-11 착수 전 결정 필요. | WBS docs/tasks/aml/00-overview.md §7 / 설계서 docs/software/02-amlSvc-sass.md §22 D-03 | WBS §7 오픈 결정 목록에 'D-03 RA DSL: 자체 factor model/JSON logic/CEL — §22 권장: 자체 factor model+JSON rule. 태스크 귀속: T-11 착수 전' 추가. |
| low | aml | 설계 §21 Phase 3 'high-risk registry' vs WBS 미반영 | 설계서 §21 Phase 3 구성 항목에 'high-risk registry' 명시. WBS §2 어느 행(T-11·T-13)에도 해당 항목 없음. WBS §5 BO 인벤토리에 간접 대응만. | WBS docs/tasks/aml/00-overview.md §2 / 설계서 docs/software/02-amlSvc-sass.md §21 Phase 3 | WBS §2 T-11 또는 T-13에 'high-risk 고객 registry(조회·현황)' 구현 항목 추가. |

---

### 대조쌍: aml:db-wbs (DB 설계서 ↔ WBS 태스크)

| 심각도 | 서비스 | 항목 | 이격 내용 | 위치 | 권고 |
|--------|--------|------|-----------|------|------|
| medium | aml | T-02 retention_class 종수 | WBS T-02 구현항목에 'retention_class 5종'. DB §6에는 6종(REGULATORY_LONG/CASE_EVIDENCE/IDENTITY/EVENT_RAW/WATCHLIST/TRANSIENT). TRANSIENT(aml_outbox, V16)가 DB §3.15·§6 변경이력 2026-06-07에 추가됐으나 T-02 미갱신. DB §6이 정본. | WBS docs/tasks/aml/02-db-migration.md 구현항목 20번 / DB docs/design/db/02-aml-db.md §6 | T-02 구현항목의 'retention_class 5종'을 'retention_class 6종(TRANSIENT 포함)'으로 갱신. V15 retention seed 항목에도 TRANSIENT 명시 추가. |
| medium | aml | WBS §7 D-14 failure_policy enum 누락값 | WBS 00-overview §7 D-14는 'MANUAL_REVIEW/FAIL_CLOSED' 2종만 열거. DB §3.2 aml_source_systems.failure_policy는 'MANUAL_REVIEW/FAIL_CLOSED/DELAY_ALLOWED' 3종. DELAY_ALLOWED 누락. DB §3.2가 정본. | docs/tasks/aml/00-overview.md §7 D-14 / docs/design/db/02-aml-db.md §3.2 | WBS §7 D-14를 'MANUAL_REVIEW/FAIL_CLOSED/DELAY_ALLOWED(DB §3.2 3종 정본)'로 수정. |
| low | aml | aml_business_documents 도메인 로직 소유 태스크 미명시 | DB §3.13은 aml_business_documents를 14종 도메인 중 하나로 정의. WBS T-02가 V11 DDL을 포함하나 도메인 로직(persistence 어댑터·usecase·포트) 소유 태스크가 §2에 없음. WBS §4에 'TBML/B2B = Phase 8 별도 WBS'로 기재되어 있어 현 WBS 범위인지 미래 범위인지 불명확. | WBS docs/tasks/aml/00-overview.md §2 / DB docs/design/db/02-aml-db.md §3.13·V11 | WBS §2 또는 §4에 aml_business_documents 도메인 로직 소유 경계 명시. 현 WBS라면 적합 태스크에 추가, 아니면 'DDL만(도메인 로직=Phase 8)'을 T-02 범위 표에 명시. |

---

### 대조쌍: aml:api-wbs (API 명세서 ↔ WBS 태스크)

| 심각도 | 서비스 | 항목 | 이격 내용 | 위치 | 권고 |
|--------|--------|------|-----------|------|------|
| medium | aml | RA 모델 활성화 엔드포인트 경로 변수명 — {v} vs {version} | API 정본: POST .../ra-models/{modelCode}/versions/{version}:activate. WBS §5 T-11 행: versions/{v}:activate로 {v} 축약. | WBS docs/tasks/aml/00-overview.md §5 L136 / API docs/design/api/02-aml-api.md §2.7·§10 | WBS §5 T-11 행의 versions/{v}:activate를 versions/{version}:activate로 정정. |
| medium | aml | audit export BO 화면 행 — POST /evidence/aml/exports 엔드포인트 누락 | API §6: GET /admin/aml/audit-events, POST /evidence/aml/exports 두 엔드포인트. WBS §5: admin/aml/audit-events만 기재, POST /evidence/aml/exports(T-19 소유) 누락. | WBS docs/tasks/aml/00-overview.md §5 L145 / API docs/design/api/02-aml-api.md §6 L1393 | WBS §5 해당 행 주요 API에 POST /evidence/aml/exports(T-19 소유) 추가. |
| low | aml | TM scenario simulate·activate 경로 표기 — 기반 경로 분리로 경로 불완전 | API 정본: POST /api/v1/admin/aml/tm-scenarios/{scenarioCode}/simulate, .../activate. WBS §5 T-14 행: admin/aml/tm-scenarios, {scenarioCode}/simulate, {scenarioCode}:activate를 별도 토큰으로 분리. 다른 행과 표기 일관성 이격. | WBS docs/tasks/aml/00-overview.md §5 L140 / API docs/design/api/02-aml-api.md §2.7 L163-164 | WBS §5 T-14 행의 경로를 admin/aml/tm-scenarios/{scenarioCode}/simulate, admin/aml/tm-scenarios/{scenarioCode}:activate 형식으로 합쳐서 표기. |

---

### 대조쌍: aml:integration-wbs (연동 명세서 ↔ WBS 태스크)

| 심각도 | 서비스 | 항목 | 이격 내용 | 위치 | 권고 |
|--------|--------|------|-----------|------|------|
| **high** | aml | STR :submit 결재 role — integration §9.1 시퀀스 vs WBS §5 | integration §9.1 시퀀스: STR :submit에 'REPORTING_OFFICER 결재' 표기. WBS §5와 API §10 정본: STR=COMPLIANCE 전담(STR_SUBMIT). integration §9.1이 정본과 불일치. | integration docs/design/integration/02-aml-integration.md §9.1 / WBS docs/tasks/aml/00-overview.md §5 | integration §9.1 시퀀스 ':submit (REPORTING_OFFICER 결재)' 레이블을 ':submit (COMPLIANCE 결재, subjectType=STR_SUBMIT)'으로 수정. |
| **high** | aml | aml.report.sla.breached metric — WBS §5/T-17 참조 vs integration §11 관측성 표 부재 | WBS §5(T-17 scope)와 변경이력 #87이 metric 'aml.report.sla.breached'를 T-17 구현 항목으로 명시. integration §11 관측성 표에는 이 metric 없음(aml.report.submission.failed만 등재). | WBS docs/tasks/aml/00-overview.md §5 / integration docs/design/integration/02-aml-integration.md §11 | integration §11 관측성 표에 'aml.report.sla.breached | ReportDeadlineChecker(T-17) | SLA 위반 즉시 alert' 행 추가. |
| medium | aml | approval_status EXPIRED 전이 — integration §8.2 정의 vs WBS T-12/§5 결재 대기함 scope 누락 | integration §8.2: SUBMITTED→EXPIRED(expires_at 경과) 전이 정의. WBS T-12 제목·§5 결재 대기함 행(:approve·:reject만)에는 EXPIRED 상태 처리(만료 스케줄러·알림) 구현 범위 없음. | integration docs/design/integration/02-aml-integration.md §8.2 / WBS docs/tasks/aml/00-overview.md §2 T-12·§5 | WBS T-12 설명에 'expires_at 경과 시 EXPIRED 자동 전이(스케줄러·aml_audit_events 기록)' 구현 항목 추가. §5 결재 대기함 행에 만료 상태 표시 항목 보완. |
| medium | aml | fds.feedback.applied outbox event_type — integration §8.1 예시 vs §3.3 카탈로그 미등재 | integration §8.1 event_type 예시에 'fds.feedback.applied' 언급(§3.4 참조). 그러나 §3.3 아웃바운드 카탈로그·§3.4 dispatch 카탈로그에 해당 eventType 없음. WBS §6.1 T-15/T-16 귀속도 불명확. | integration docs/design/integration/02-aml-integration.md §8.1, §3.3, §3.4 / WBS docs/tasks/aml/00-overview.md §6.1 | integration §3.3 또는 §3.4에 fds.feedback.applied 등재(트리거·핵심 키·구독자 포함). T-15 vs T-16 귀속 WBS §6.1에 명확히 반영. |
| medium | aml | 결재 대기함 BO 화면 — :cancel(maker 취소) 액션 누락 | integration §8.2: SUBMITTED→CANCELLED(maker 취소) 공식 전이 정의. WBS §5 결재 대기함 행: :approve·:reject만 있고 :cancel 누락. | integration docs/design/integration/02-aml-integration.md §8.2 / WBS docs/tasks/aml/00-overview.md §5 | WBS §5 결재 대기함 행 주요 API에 'admin/aml/approvals/{approvalId}:cancel 🔒(maker, SUBMITTED 상태 한정)' 추가. |
| low | aml | integration §8.3 subject_type 표 범위 주석 '16종' vs WBS T-12 §2 표 미반영 | integration §8.3은 subjectType 16종 전수 커버를 명시. WBS §2 T-12 설명·§5 비고에 이 사실의 참조 링크 없음. T-12 구현 범위 가늠이 어려움. | integration docs/design/integration/02-aml-integration.md §8.3 / WBS docs/tasks/aml/00-overview.md §2 T-12 | WBS §2 T-12 설명 또는 §5 결재 대기함 비고에 'subjectType 16종 전수(integration §8.3 정본)' 참조 링크 추가. |
| low | aml | integration §11 connector health metric 서술 vs WBS T-20 scope 표현 | integration §11: connector health·watchlist freshness·reconciliation report를 관측성 운영 항목으로 명시. WBS T-20: connector health 포함이나 watchlist freshness·reconciliation report는 T-08로 분산. integration §11 단일 절과 WBS 태스크 귀속이 분리. | integration docs/design/integration/02-aml-integration.md §11 / WBS docs/tasks/aml/00-overview.md §2 T-20 | WBS §6 BE 전용 섹션 또는 T-20 설명에 'watchlist freshness·reconciliation report 모니터링(integration §11 정본)'이 T-08/T-20 공동 소유임을 명시. |

---

### 대조쌍: aml:wbs-roadmap (WBS 태스크 ↔ 프로그램 로드맵)

| 심각도 | 서비스 | 항목 | 이격 내용 | 위치 | 권고 |
|--------|--------|------|-----------|------|------|
| medium | aml | 로드맵 §3 P2 aml 칸 T-12 한정자 누락 | 로드맵 §3 P2 aml 칸: T-08~T-12·T-14(MVP). T-12는 P2(골격)/P4(완성) 분할. P4 칸에는 T-12(완성) 별도 등재. P2 칸이 분할 상태 미명시로 T-12 전부 완성처럼 오독 가능. FDS 트랙 P2 칸은 T-15(골격) 한정자 명시. | docs/tasks/aegis-aml/00-program-overview.md §3 P2 aml 칸 | 로드맵 §3 P2 aml 칸을 T-08~T-11·T-12(골격)·T-14(MVP)로 수정. FDS 트랙 T-15(골격) 패턴 준용. |
| medium | aml | WBS §4 병렬 가능 그룹 {T-19, T-20} Phase 불일치 | WBS §4: {T-19, T-20} 병렬 가능 그룹. T-19 Due=P6, T-20 Due=P7. 로드맵 §3은 T-19=P6, T-20=P7으로 Phase 명확히 분리. 동일 병렬 그룹 표기로 동일 Phase 병렬 착수로 오해 가능. | docs/tasks/aml/00-overview.md §4 / docs/tasks/aegis-aml/00-program-overview.md §3 | WBS §4에서 {T-19, T-20}을 T-19(P6 단독)·T-20(P7 착수)으로 Phase 구분 명시 또는 분리 표기. |
| low | aml | WBS §4 병렬 가능 그룹 {T-03, T-04, T-05} — T-03 분할 Due 미반영 | WBS §4: {T-03, T-04, T-05} 병렬 그룹 단순 열거. T-03 Due=P1(레지스트리·온보딩)/P3(policy pack 변경 일부). T-04·T-05 Due=P1. P1 시점에만 T-04·T-05와 병렬임을 명확히 하지 않음. 로드맵 §3 P3 칸에 T-03 일부 분리 정확히 반영. | docs/tasks/aml/00-overview.md §4 / docs/tasks/aegis-aml/00-program-overview.md §3 | WBS §4 병렬 가능 그룹을 '{T-03(레지스트리·온보딩 부분), T-04, T-05} — P1 시점 병렬'로 명확화. |
| low | aml | WBS §2 T-13 의존 표기 T-12 한정 미명시 | WBS §2 T-13 의존 칸: T-09,T-11,T-12. 로드맵 P3 의존은 T-12 골격만으로 착수 가능. T-12 완성(P4)보다 T-13 Due(P3)가 앞섬. | docs/tasks/aml/00-overview.md §2 T-13 / docs/tasks/aegis-aml/04-phase3-domain-boapi.md | WBS §2 T-13 의존 칸을 T-09,T-11,T-12(골격)으로 수정. |
| low | aml | 로드맵 §3 P2 aml 칸 연속범위 T-08~T-12 — T-12 분할 표기 불일관 | 로드맵 §3 P2 fds 칸은 T-15(골격) 한정자 명시. aml 칸은 T-08~T-12를 연속 범위로 묶어 T-12 분할 미명시. | docs/tasks/aegis-aml/00-program-overview.md §3 P2 aml 칸 | 로드맵 §3 P2 aml 칸의 T-08~T-12를 T-08~T-11·T-12(골격)으로 분리 표기. |

---

### 대조쌍: aml:roadmap-design (프로그램 로드맵 ↔ 설계서)

| 심각도 | 서비스 | 항목 | 이격 내용 | 위치 | 권고 |
|--------|--------|------|-----------|------|------|
| medium | aml | P2 Phase 파일 헤더의 AML 설계 §21 Phase 참조 범위 누락 | P2 헤더는 'AML §21 Phase 2'만 인용. 실제 P2 구현 범위는 WLF(§21 Phase 2)+RA P2-AML-04(Phase 3)+TM MVP P2-AML-06(Phase 4) 포함. | docs/tasks/aegis-aml/03-phase2-engines-mvp.md 헤더 line 3 | P2 Phase 파일 헤더 AML 설계 인용을 §21 Phase 2~4로 수정 또는 각 태스크에 §21 Phase 번호 병기. |
| medium | aml | P6 Phase 파일 헤더의 AML 설계 §21 Phase 6 인용 오류 | P6 헤더는 AML §21 Phase 5~6 인용. §21 Phase 6는 Compliance Operations Console(P5 범위). P6 실제 범위는 규제 보고·FDS 연동·증적(Phase 5). 동일 파일 §4도 Phase 5·§14·§15.6만 인용. | docs/tasks/aegis-aml/07-phase6-regulatory-integration.md 헤더 line 3 | P6 Phase 파일 헤더 AML 설계 인용을 §21 Phase 5로 정정(Phase 6 제거). |

---

### 대조쌍: aml:roadmap-prd (프로그램 로드맵 ↔ PRD 기능정의서)

| 심각도 | 서비스 | 항목 | 이격 내용 | 위치 | 권고 |
|--------|--------|------|-----------|------|------|
| **high** | aml | P5 Phase 산출 AML 화면 수 (23 vs 31) | 로드맵 §2 P5 AML 화면 수 '23화면'. PRD v7.0 §1.2 총 31화면 확정. v6.0(+4화면)·v7.0(+3화면) 갱신 미반영. 이격 8화면. 정본: PRD §1.2 v7.0. | docs/tasks/aegis-aml/00-program-overview.md §2 L37 / docs/plan/02-aml-sass-functional-spec.md §1.2 | 로드맵 §2 P5 행 'AML 23화면'을 'AML 31화면(23화면+§12-B 벤치마크 보강 8화면)'으로 갱신. 06-phase5-bo-web.md 헤더·§1·§2.3·§5도 동기 수정. |
| **high** | aml | 06-phase5-bo-web.md 인용 PRD 버전 (v5.9 vs v7.0) | Phase 파일이 'PRD v5.9·PPT v5.9(23화면)'을 정본 인용. PRD는 v7.0(31화면)으로 갱신됨. §12-B 신규 7개 화면에 대한 P5 태스크 분해 및 Phase Exit 기준 전무. | docs/tasks/aegis-aml/06-phase5-bo-web.md 헤더·§1·§2.3·§4·§5 | 헤더·§1·§2.3·§4·§5의 PRD/PPT 버전 인용을 v7.0으로 갱신. §2.3에 §12-B 7개 신규 화면 태스크(P5-AML-13~19) 추가. Phase Exit §5 'AML 23' → 31 수정. |
| **high** | aml | AML-STAT-001 화면의 WBS 태스크 미등재 | PRD §1.2가 AML-STAT-001을 T-20에 귀속. WBS T-20 제목·DoD에 STR 보고 퍼널·시나리오별 전환율 집계 기능 없음. 정본: PRD v6.0 §12-B.3. | PRD §1.2 / docs/tasks/aml/00-overview.md §2·§5 | WBS T-20에 AML-STAT-001 범위 추가. §5 BO 화면 인벤토리에 AML-STAT-001 행 추가. |
| **high** | aml | AML-EDU-001 화면의 WBS 태스크 미등재 | PRD §1.2가 AML-EDU-001을 T-20에 귀속. WBS T-20 제목·DoD에 교육·자격 관리 기능 없음. | PRD §1.2 / docs/tasks/aml/00-overview.md §2·§5 | WBS T-20에 AML-EDU-001 범위 추가. §5 BO 화면 인벤토리에 AML-EDU-001 행 추가. |
| **high** | aml | AML-WL-003 화면의 WBS 태스크 미등재 | PRD §1.2가 AML-WL-003을 T-08·T-10에 귀속. WBS T-08·T-10에 수기 등록 diff 초안·오탐 면제 생명주기 관리 전용 화면 없음. | PRD §1.2 / docs/tasks/aml/00-overview.md §2·§5 | WBS T-08 또는 T-10에 AML-WL-003 범위 추가. §5 BO 화면 인벤토리에 AML-WL-003 행 추가. |
| **high** | aml | AML-HRR-001 화면의 WBS 태스크 미등재 | PRD §1.2가 AML-HRR-001을 T-11에 귀속. WBS T-11에 당연고위험 분류 기준 관리·참조 리스트 4-eyes 기능 없음. | PRD §1.2 / docs/tasks/aml/00-overview.md §2·§5 | WBS T-11에 AML-HRR-001 범위 추가. §5 BO 화면 인벤토리에 AML-HRR-001 행 추가. |
| **high** | aml | AML-CDD-002 화면의 WBS 태스크 미등재 | PRD §1.2가 AML-CDD-002를 T-13에 귀속. WBS T-13에 고객 CDD 프로필 360° read-only 원장 화면 없음. | PRD §1.2 / docs/tasks/aml/00-overview.md §2·§5 | WBS T-13에 AML-CDD-002 범위 추가. §5 BO 화면 인벤토리에 AML-CDD-002 행 추가. |
| medium | aml | 06-phase5-bo-web.md §2.3 서두 주석의 PRD 버전 참조 | §2.3 서두가 'PRD §13 재구성본·PPT v5.3 기준: 23화면'으로 고정. PRD v6.0·v7.0의 §12-B 7개 신규 화면 구현 태스크(P5-AML-13 이하) 없음. 8화면 누락 위험. | docs/tasks/aegis-aml/06-phase5-bo-web.md §2.3 L39 | §2.3 서두를 'PRD v7.0 기준: 23화면+§12-B 보강 8화면=총 31화면'으로 갱신. §12-B 7개 화면 P5 태스크 추가. |
| medium | aml | 로드맵 §3 P5 bo-web 열 실제 반영 화면 수 | §3 P5 bo-web 칸이 '전 화면'으로 §2의 '23화면'과 연계. PRD v7.0 기준 31화면 확정이나 §3도 갱신 안 됨. | docs/tasks/aegis-aml/00-program-overview.md §3 P5 bo-web 칸 | §3 P5 bo-web 칸을 'AML 31화면(23화면+§12-B 벤치마크 보강 8화면)'으로 갱신. |
| low | aml | PRD §1.2 화면 범위 표에 AML-WL-002 행 미등재 | 부록 A에 AML-WL-002 독립 행 존재. §1.2 화면 범위 표에는 WL-001 행만 있고 WL-002 없음. 화면 수 산정은 드릴다운 제외로 보이나 §1.2 표와 부록 A 간 표기 불일치. | PRD docs/plan/02-aml-sass-functional-spec.md §1.2·부록 A | §1.2 AML-WL-001 행에 '(행 클릭 → AML-WL-002 디프 승인 드릴다운)' 주석 추가 또는 AML-WL-002를 드릴다운 전용으로 별도 행 등재. |

---

### 대조쌍: cross:naming-tenancy-pii (횡단: 명명·테넌시·PII 규약)

| 심각도 | 서비스 | 항목 | 이격 내용 | 위치 | 권고 |
|--------|--------|------|-----------|------|------|
| **high** | cross | aml_tenants DDL — retention_policy 컬럼 | DB §3.1 정본: retention_policy JSONB NOT NULL DEFAULT '{}'. 설계서 §17.1 개념 DDL에 해당 컬럼 없음. | 설계서 docs/software/02-amlSvc-sass.md §17.1 / DB docs/design/db/02-aml-db.md §3.1 | 설계서 §17.1 aml_tenants DDL에 retention_policy JSONB NOT NULL DEFAULT '{}'::jsonb 추가. DB §3.1이 정본. |
| **high** | cross | aml_tenants DDL — 감사 컬럼(created_by·updated_at·updated_by·trace_id) 누락 | DB §2.1 공통 규약: 전 운영 테이블에 5종 감사 컬럼 요구. DB §3.1 'created_at(공통 §2.1)' 명시. 설계서 §17.1 DDL에는 created_at만 있고 나머지 4종(created_by·updated_at·updated_by·trace_id) 없음. | 설계서 docs/software/02-amlSvc-sass.md §17.1 / DB docs/design/db/02-aml-db.md §3.1·§2.1 | 설계서 §17.1 aml_tenants DDL에 created_by·updated_at·updated_by·trace_id 4종 컬럼 추가. DB §3.1·§2.1이 정본. |
| medium | cross | workspace_id 결정 확정 수준 표현 불일치 | 설계서 §16.2.1: workspace_id '미적용 — 결정 보류'. DB §1.1: '미사용 결정(정본 §4 × 설계서 §16.2.1 합의)'. target-architecture §4는 3-key 명시적 요구. 두 문서가 확정 수준을 다르게 표현. | 설계서 docs/software/02-amlSvc-sass.md §16.2.1 / DB docs/design/db/02-aml-db.md §1.1 | 두 문서 표현을 통일. 'AML 1차 범위에서 물리 컬럼 미도입 — 추후 재검토 조건 명문화'로 동일 표현 적용. |
| medium | cross | aml_tenants — data_scope 컬럼 예외 처리 명문화 부재 | DB §2.1 공통 규약: data_scope 전 운영 테이블 적용. DB §3.1 aml_tenants 컬럼 표·설계서 §17.1 DDL에 data_scope 없음. 테넌시 기준 테이블로 의도적 제외로 보이나 명문화 없음. | DB docs/design/db/02-aml-db.md §2.1·§3.1 / 설계서 docs/software/02-amlSvc-sass.md §17.1 | DB §3.1 aml_tenants 컬럼 표에 'data_scope: 해당 없음 — 본 테이블이 격리 기준 테이블이므로 하위 data_scope 필터 비적용' 명문화. 설계서 §17.1도 동일 반영. |
| medium | cross | 감사로그(aml_audit_events) detail JSONB PII masking 요건 — 설계서 §19.2 미명시 | DB §3.15 aml_audit_events.detail JSONB에 'masked' 처리 명시. 설계서 §19.2 PII·민감정보 규약·§19.3 감사 대상 목록에 감사로그 detail의 PII masking 요건 미기술. | 설계서 docs/software/02-amlSvc-sass.md §19.2 / DB docs/design/db/02-aml-db.md §3.15 | 설계서 §19.2 또는 §19.3에 '감사로그 detail JSONB는 PII(이름·계좌번호 등)를 hash/token 참조만 포함하고 원문 포함 금지(masked — DB §3.15 정본)' 명문화. |
| low | cross | 설계서 §6.2 변경이력 — 구 scope 표현(aml:case:write·aml:approval:*) 잔류 | 설계서 본문은 교정된 aml:case:update·aml:admin:approval 사용. 변경이력(2026-06-10)에 구 표현 aml:case:write·aml:approval:* 잔류. 이력란에 구 비정본 scope 혼재. | 설계서 docs/software/02-amlSvc-sass.md 변경이력 2026-06-10 | 변경이력 해당 항목 scope를 aml:case:update·aml:admin:approval로 교정. 교정 전 코드를 기록할 경우 '(구 오기 →교정)' 맥락 명기. |

---

## ④ 개발 착수 권고

**현재 판정: FAIL — 개발 착수 불가.**

높음(high) 17건이 미해결 상태이며 다음 영역에서 즉시 교정이 필요하다.

### 즉시 교정 필요 (높음 17건)

| 우선순위 | 이격 항목 | 교정 대상 문서 |
|----------|-----------|----------------|
| 1 | RISK_OVERRIDE 방향 모순 — 연동 §8.3이 '→HIGH' 방향 오기 | docs/design/integration/02-aml-integration.md §8.3 |
| 2 | completeness_status 트리거 조건 — DB §5.15/§5.22 note가 3종 미포함 | docs/design/db/02-aml-db.md §5.15, §5.22 |
| 3 | STR :submit 결재 role — integration §9.1이 REPORTING_OFFICER 오기 | docs/design/integration/02-aml-integration.md §9.1 |
| 4 | aml.report.sla.breached metric — integration §11 관측성 표 미등재 | docs/design/integration/02-aml-integration.md §11 |
| 5 | AML-WLF-001/WL-001 → AML-WLF-004 아웃바운드 트리거 누락 | .claude/skills/backoffice-planner/generate_aml.py wlf_001(), wl_001() |
| 6 | aml_tenants DDL — retention_policy·감사 컬럼(4종) 누락 | docs/software/02-amlSvc-sass.md §17.1 |
| 7 | P5 AML 화면 수 23화면 고정 (PRD v7.0 기준 31화면) | docs/tasks/aegis-aml/00-program-overview.md §2, 06-phase5-bo-web.md 전반 |
| 8 | AML-STAT-001·AML-EDU-001·AML-WL-003·AML-HRR-001·AML-CDD-002 WBS 미등재 (5건) | docs/tasks/aml/00-overview.md §2, §5 |
| 9 | AML-TNT-002 reportingInstitution — API TenantDto 미정의 | docs/design/api/02-aml-api.md §3.16 |
| 10 | AML-IRA-001 — /ira/reports·IRA_SUBMIT subjectType API 미정의 | docs/design/api/02-aml-api.md §2.7, §3.7 |
| 11 | AML-WL-003 — entries:draft·GET fp-whitelist·revoke API 미정의 | docs/design/api/02-aml-api.md §2.7 |
| 12 | 06-phase5-bo-web.md PRD v5.9 고정 — §12-B 7개 신규 화면 P5 태스크 분해 전무 | docs/tasks/aegis-aml/06-phase5-bo-web.md 전반 |

### 개발 착수 조건

아래 조건이 모두 충족되어야 개발 착수 가능:

1. 높음 17건 전수 교정 완료
2. `doc-consistency-qa` 재실행 후 높음 0건 PASS
3. 중간 이격 중 API 미정의 항목(AML-STAT-001·AML-EDU-001 제안 API)은 착수 전 정합 여부를 설계팀이 결정·명문화
4. PRD 부록 E v6.0·v7.0 오픈 결정 항목 중 개발 착수 전 결정 필요 건 확인

---

*리포트 생성: 2026-06-12 | 대상: aml | 정합화 도구: doc-consistency-qa*
