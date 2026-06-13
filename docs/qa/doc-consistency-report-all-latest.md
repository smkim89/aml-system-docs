# 문서 정합성 QA 리포트 — 전체(all)

| 항목 | 내용 |
|---|---|
| **판정** | **FAIL** |
| **대상 서비스** | fds · aml · cross |
| **검사 일시** | 2026-06-11 |
| **높음(HIGH)** | **11건** |
| **중간(MEDIUM)** | **59건** |
| **낮음(LOW)** | **49건** |
| **합계** | **119건** |
| **미검증 쌍** | **0개** |
| **상태** | COMPLETE — 전 대조쌍 23개 검사 완료 |

---

## ① 판정

**FAIL** — 높음(HIGH) 이격이 11건 존재한다. 개발 착수 전 HIGH 전수 해소가 필수이며, MEDIUM 59건도 구현 착수 전 정합화가 권고된다.

---

## ② 심각도별 요약

| 심각도 | 건수 | 주요 유형 |
|---|---|---|
| **HIGH** | **11** | ActionResponse.actionType 응답 누락 · STR 보고 실패 페이로드 필드명 오기(errorCode→submissionErrorCode) · AML.TENANT_NOT_FOUND HTTP 상태코드 409→404 오기 · CasePatchRequest.reason 필드 누락 · GET /admin/fds/rules 필터 파라미터 누락(decisionOutcome·evaluationMode) · event family 카운트 cross-reference 오류 · T-10 의존 누락(T-09·T-11) · SCREENS 화면 수 선언 불일치 · D-번호 오인용(isolation_mode=D-01→D-06) · tenant_status enum 교차 주석 구버전 잔류(FDS 3종·OFFBOARDING 표기) |
| **MEDIUM** | **59** | enum 미정의(transaction_status·kyc_status) · DTO 필드 누락(EvidenceExportResponse reason/createdAt/updatedAt · SourceSystemDto data_scope · CounterpartyDto/ActorDto/LocationDto) · approval_status DRAFT 외부 미노출 경계 미명시 · STR approvalLine 값 표기 혼재 · port/in ScreenUseCase 명칭 비대칭 · event family 분류 혼동(chargeback.opened) · outbox event_type 예시 비정본값(fds.feedback.applied) · 4-eyes 항목·metric 표 누락 · WBS 의존 표기 불완전 · PPT 화면 표기 오류 · roadmap Phase §참조 라벨 불완전 · cross: ingest_mode 종수 비대칭·Policy Pack 모델 비대칭·규제 보고 상태머신 교차 참조 부재 |
| **LOW** | **49** | onboarding_status 표시 라벨 1자 차이 · aml.report.sla.breached metric 내부 누락 · aml_cases.status DEFAULT 미동기화 · approval_status DB 노출 정책 주석 누락 · RuleSetDto/FeatureCatalogDto 미정의 · payloadHash stored=false 잔존 표기 · 변경이력 stale scope 코드 잔존 · ManageWatchlistUseCase fp-whitelist 귀속 불명확 · PPT 버전 포인터 불일치 · Capability 매트릭스 컬럼 묶음 미명시 · 로드맵 §참조 비존재 subsection 지정 · cross: approval_line 비대칭 교차 주석 미명시·PII 마스킹 대상 7종 미통일·감사로그 보존기간 미명시·fds:pii:reveal scope 부재 |

---

## ③ 대조쌍별 이격 표

### 대조쌍: fds:db-design (FDS 설계서 ↔ DB 설계서)

| 심각도 | 서비스 | 항목 | 이격 내용 | 위치 | 권고 |
|---|---|---|---|---|---|
| MEDIUM | fds | fds_transactions.status — closed enum 미정의 | 설계서 §8.2 예시에 `transaction.status="REQUESTED"` 사용, §8.3 표에서 transactionType은 폐쇄 enum 참조 명시. 그러나 transaction.status에 대한 폐쇄 enum이 설계서·DB §4·§5.9 어디에도 없음. 자유 문자열 저장 위험 | 설계서 §8.2/§8.3 §14.4 DDL / DB §5.9 fds_transactions | DB §4에 `transaction_status` enum 신설(REQUESTED/AUTHORIZED/COMPLETED/FAILED/CANCELLED/REVERSED). §5.9 컬럼 제약 갱신. 설계서 §11.6.18 보조 enum 표에 역삽입. DB가 정본이므로 DB §4 먼저 확정 후 설계서 동기화 |
| LOW | fds | onboarding_status CUSTOMER_DEPLOYED 표시 라벨 불일치 | DB §4.1: `CUSTOMER_DEPLOYED` 표시값='고객배포'. 설계서 §11.6.11a: '고객배포완료'. 코드값은 동일하나 한국어 라벨 1자 차이. DB 문서에 bo-web i18n 위임 설명 없음 | DB §4.1 / 설계서 §11.6.11a | DB §4.1 표시값을 '고객배포완료'로 통일하거나 두 문서 모두 'bo-web i18n 키가 최종 정본' 주석 추가 |

---

### 대조쌍: aml:db-design (AML 설계서 ↔ DB 설계서)

| 심각도 | 서비스 | 항목 | 이격 내용 | 위치 | 권고 |
|---|---|---|---|---|---|
| MEDIUM | aml | kyc_status enum (aml_customers.kyc_status) | DB §5.25에서 5종(PENDING/VERIFIED/INCOMPLETE/EXPIRED/REJECTED) 물리 정본 도입 후 '설계서 §13.1에 역삽입 권고' 명시. 그러나 설계서 §13.1 CDD 섹션에는 enum 코드값 정의 미부재 | 설계서 §13.1 CDD / DB §5.25 | 설계서 §13.1에 kyc_status 상태 표 추가하여 DB §5.25와 1:1 정합 |
| MEDIUM | aml | aml_tenants.retention_policy 컬럼 | DB §3.1에 `retention_policy JSONB NOT NULL DEFAULT '{}'` 정식 정의. 설계서 §17.1 CREATE TABLE aml_tenants 개념 DDL에 해당 컬럼 없음 | 설계서 §17.1 DDL / DB §3.1 | 설계서 §17.1 DDL에 retention_policy 컬럼 추가(`-- 고객사별 보존·파기 override §16.3·§19`) |
| LOW | aml | aml.report.sla.breached metric 내부 누락 | 설계서 §14.4에서 `aml.report.sla.breached` metric 정의. §20.1 주요 metric 표에는 `aml.case.sla.breached`만 있고 누락 | 설계서 §14.4 vs §20.1 | 설계서 §20.1에 `aml.report.sla.breached | 보고 기한 SLA 위반` 행 추가 |
| LOW | aml | aml_cases.status DEFAULT 값 불일치 | DB §3.11: `status VARCHAR(32) NOT NULL DEFAULT 'OPEN'`. 설계서 §17.4 DDL: `status VARCHAR(32) NOT NULL`로 DEFAULT 없음 | 설계서 §17.4 DDL / DB §3.11 | 설계서 §17.4 status 컬럼에 `DEFAULT 'OPEN'` 추가 |

---

### 대조쌍: fds:api-db (FDS API ↔ DB 설계서)

| 심각도 | 서비스 | 항목 | 이격 내용 | 위치 | 권고 |
|---|---|---|---|---|---|
| HIGH | fds | ActionResponse.actionType 필드 누락 | DB `fds_actions.action_type VARCHAR(64) NOT NULL` 필수 컬럼. API `GET /fds/actions/{actionId}` 및 `POST /fds/cases/{caseId}/actions` 응답 DTO `ActionResponse`(§5.7)에 `actionType` 필드 없음. 클라이언트 처리·감사 추적 직접 차질. Webhook `FdsActionResult`에는 포함됨 | API §5.7 CaseActionRequest/ActionResponse / DB §5.12 fds_actions | API §5.7 `ActionResponse`에 `actionType`(enum action_type 23종, DB 매핑) 필수 응답 필드 추가. OpenAPI §10 schema 반영 |
| MEDIUM | fds | EvidenceExportResponse createdAt / updatedAt 누락 | DB `fds_evidence_exports`에 `created_at`·`updated_at` NOT NULL 컬럼. API §5.11 응답에 exportId/status/manifestHash/approvalRequestId/createdBy만 정의되어 있고 두 타임스탬프 누락 | API §5.11 EvidenceExportRequest 응답 / DB §5.31 | API §5.11 응답에 `createdAt`·`updatedAt`(datetime) 추가 |
| MEDIUM | fds | CounterpartyDto / ActorDto / LocationDto schema 미정의 | `IngestEventRequest`(§5.1)에서 세 DTO를 타입 참조하나 §5·§10 OpenAPI schemas 어디에도 필드 정의 없음. 코드 생성·계약 기반 개발 직접 차질 | API §5.1 IngestEventRequest / DB counterparty_ref/actor_ref | API §5 또는 §10에 세 DTO 필드 정의 추가(DB 컬럼 매핑 포함) |
| LOW | fds | RuleSetDto 미정의 | `GET /api/v1/admin/fds/rule-sets` 응답 DTO 미정의. DB §5.16 컬럼 목록 존재 | API §4.6 / DB §5.16 fds_rule_sets | API §5 또는 §10에 `RuleSetDto` 정의(ruleSetId/displayName/activeVersion/createdBy/updatedBy/createdAt/updatedAt) |
| LOW | fds | FeatureCatalogDto 미정의 | `GET /api/v1/admin/fds/feature-catalog` 응답 DTO 미정의. DB §5.20 컬럼 목록 존재 | API §4.6 / DB §5.20 fds_feature_catalog | API §5 또는 §10에 `FeatureCatalogDto` 정의(featureKey/category/valueType/displayLabel/enabled/createdAt/updatedAt) |

---

### 대조쌍: aml:api-db (AML API ↔ DB 설계서)

| 심각도 | 서비스 | 항목 | 이격 내용 | 위치 | 권고 |
|---|---|---|---|---|---|
| LOW | aml | IngestEventRequest.payloadHash 설명 — `stored=false` 잔존 | DB §2.2에서 `stored` 플래그 폐기 후 참조 제거. 그러나 API §3.1 payloadHash 설명이 `raw payload sha256(\`stored=false\`)` 그대로 남아 있음 | API §3.1 payloadHash 행 / DB §2.2 | API §3.1 payloadHash 설명에서 `(stored=false)` 제거 |
| LOW | aml | aml_approvals.status — DRAFT API 미노출 정책 DB 미기재 | DB §5.13·§3.15: 8종 enum 그대로 기술. API §3.7·§1.5: DRAFT 내부 상태로 외부 미노출(7종 노출) 명시. DB 문서에 노출 정책 역방향 미기재 | DB §5.13 approval_status / API §3.7·§1.5 | DB §5.13 표 또는 §3.15 컬럼 설명에 `(API 노출은 DRAFT 제외 7종 — API §3.7·§1.5 참조)` 주석 추가 |
| MEDIUM | aml | EvidenceExportResponse — `reason` 필드 누락 | DB §3.15 `aml_evidence_exports.reason VARCHAR(512) NOT NULL DEFAULT ''`. 응답 `EvidenceExportResponse`에 reason 필드 없음. 감사 필수 컬럼으로 클라이언트 확인 필요 | API §3.8 EvidenceExportResponse / DB §3.15 | API §3.8 `EvidenceExportResponse`에 `reason: string` 필드 추가 |
| MEDIUM | aml | SourceSystemDto — `data_scope` 필드 누락 | DB §3.2 V20 마이그레이션으로 `data_scope VARCHAR(64) NULL` 추가. API §3.9 SourceSystemDto에 해당 필드 없음 | API §3.9 SourceSystemDto / DB §3.2 | API §3.9 SourceSystemDto에 `dataScope(nullable)` 필드 추가 |
| LOW | aml | CustomerProfileDto — `country` 필드 누락 | DB §3.3 `aml_customers.country VARCHAR(8) Y NULL`. API §3.9 `CustomerProfileDto`에 country 필드·OpenAPI schema 항목 없음. ISO 코드로 PII 아님 | API §3.9 CustomerProfileDto / DB §3.3 | API §3.9 CustomerProfileDto 표 및 OpenAPI schema에 `country: string(nullable)` 추가 |
| LOW | aml | WatchlistEntryDto — `attributes` 필드 DTO 미선언 | DB §3.7 `aml_watchlist_entries.attributes JSONB NOT NULL DEFAULT '{}'`. API §3.9 DTO에 attributes가 주석으로만 처리됨. NOT NULL 기본값이므로 DTO 필드로 명시 필요 | API §3.9 WatchlistEntryDto / DB §3.7 | API §3.9 WatchlistEntryDto에 `attributes: object(nullable)` 행 추가(hash/token만 포함·raw PII 미노출 설명 기재). OpenAPI schema에도 추가 |

---

### 대조쌍: fds:api-design (FDS API ↔ 설계서)

| 심각도 | 서비스 | 항목 | 이격 내용 | 위치 | 권고 |
|---|---|---|---|---|---|
| MEDIUM | fds | Approval API (approve/reject) OAuth2 scope | 설계서 §12.8 Approval API scope란 = `운영자 IAM`(비정규 표현). API §4.9·§2.3·§10: `fds:action:write`로 확정. 구현자가 별도 IAM 계층으로 오해 가능 | 설계서 §12.8 / API §4.9·§2.3·§10 | 설계서 §12.8 Approval API scope를 `fds:case:read`(조회) / `fds:action:write`(승인·반려)로 정정 |
| LOW | fds | 설계서 §11.4 4-eyes 항목 목록 — POLICY_PACK 누락 | 설계서 §11.4 기본 항목 8개 bullet에 '규제 팩 토글 변경'(POLICY_PACK) 없음. API §8 표·§11.5 subjectKind 표 모두 POLICY_PACK 명시 | 설계서 §11.4 bullet list / API §8·설계서 §11.5 | 설계서 §11.4 bullet list에 '규제 팩(`compliance_policy`) 토글 변경' 추가 |
| LOW | fds | 설계서 §12.8 Admin API 그룹 용도 — 알림 채널 관리 미언급 | 설계서 §12.8 Admin API 용도 = 'source, schema, key, scope 관리'만 기술. API §4.8에 notify-channels 관리 명시됨 | 설계서 §12.8 Admin API 행 / API §4.8 | 설계서 §12.8 Admin API 용도 설명에 '알림 채널 설정' 추가 |

---

### 대조쌍: aml:api-design (AML API ↔ 설계서)

| 심각도 | 서비스 | 항목 | 이격 내용 | 위치 | 권고 |
|---|---|---|---|---|---|
| MEDIUM | aml | approval_status DRAFT — API 미노출 여부 경계 주석 부재 | SW 설계서 §13.5: 외부 호출자 관점 구분 없이 8종 전이도 기술. API §3.7·§1.5: DRAFT 내부 상태·API 미노출 명문화. SW 설계서에 경계 주석 없음 | 설계서 §13.5 / API §3.7·§1.5 | 설계서 §13.5 결재 상태머신 서술에 '`DRAFT`는 엔진 내부 초기화 상태이며 API 표면 미노출(API §3.7·§1.5 정본)' 주석 추가 |
| MEDIUM | aml | port/in `ScreenUseCase` ↔ API 엔드포인트 명칭 비대칭 | SW §6.2: `ScreenUseCase`(단수). API §2.2 실시간 screening 2종 + Admin §2.7 screening 운영 다수. Admin screening 엔드포인트 대응 인바운드 port 누락 | 설계서 §6.2 port/in / API §2.2·§2.7 | SW §6.2 주석에 screening 운영 판정·fp-whitelist가 어느 port/in으로 진입하는지 1:1 추적 가능하도록 보강 |
| MEDIUM | aml | STR 제출 `ReportSubmitRequest.approvalLine` 값 표기 혼재 | API §3.6 예시가 CTR과 동일하게 `REPORTING_OFFICER` 하드코딩. 그러나 API §10에서 STR 제출은 `COMPLIANCE 전담 4-eyes`. STR 제출 시 잘못된 approvalLine 전달 위험 | API §3.6 ReportSubmitRequest / API §10 | API §3.6에 'STR 시 `approvalLine: "COMPLIANCE"`, CTR·TravelRule 시 `approvalLine: "REPORTING_OFFICER"`' 명시 또는 reportType별 DTO 예시 분리 |
| LOW | aml | SW 설계서 §6.2 변경이력 stale scope 코드 잔존 | 변경이력 2026-06-10 항목에 구버전 scope `aml:case:write`·`aml:approval:*` 기록. 2026-06-11 이력에서 교정됐으나 이력란 오기가 혼란 유발 | 설계서 변경이력 2026-06-10 항목 / 설계서 §6.2 | 변경이력 2026-06-10 항목 scope를 교정값(`aml:case:update`, `aml:admin:approval`)으로 수정하거나 '2026-06-11 이력에서 교정됨' 각주 추가 |
| LOW | aml | `ManageWatchlistUseCase` port/in — fp-whitelist 귀속 불명확 | SW §6.2: `ManageWatchlistUseCase`가 watchlist-sources만 언급. fp-whitelist 등록(`POST /admin/aml/screenings/fp-whitelist`, scope=`aml:admin:watchlist`)이 ManageWatchlistUseCase 소관인지 불명확 | 설계서 §6.2 / API §2.7 | SW §6.2 port/in 주석에 fp-whitelist 등록 귀속 port 명시 |

---

### 대조쌍: fds:integration-design (FDS 설계서 ↔ 연동 설계서)

| 심각도 | 서비스 | 항목 | 이격 내용 | 위치 | 권고 |
|---|---|---|---|---|---|
| MEDIUM | fds | `chargeback.opened` event family 분류 혼동 | 설계서 §7.3 카드 결제 생명주기 예시에서 `chargeback.opened`를 transaction 맥락으로 암시. 연동 §3.1 정규화 표: `event_family=case`(분쟁 케이스 개시) 정본 | 설계서 §7.3 / 연동 §3.1 | 설계서 §7.3 예시에 '`chargeback.opened`의 `event_family=case` — 연동 §3.1 정본' 주석 추가 |
| MEDIUM | fds | `eventFamily` 서버 파생(읽기전용) 여부 — 설계서 §8.2/§8.3 미명시 | 연동 §4.1·§4.2: `eventFamily`는 서버 파생·발신측 미전송 명시. 설계서 §8.2 JSON 예시·§8.3 필수 필드 표에 `eventFamily` 언급 자체 없음 | 설계서 §8.2·§8.3 / 연동 §4.1·§4.2 | 설계서 §8.3 필수 필드 표에 `eventFamily` 행 추가(필수=서버 파생·발신측 미포함·연동 §4.1 정본) |
| LOW | fds | 설계서 §8.1 `market.*` family — `trade.*` 접두 재사용과 충돌 서술 | 설계서 §15.10의 `trade.order.created`/`trade.executed`(trade 접두)와 §8.1 `market.*` family 정규화 간 관계 미명시. 독자가 거래소 이벤트를 `trade` family로 착각 가능 | 설계서 §8.1 / 연동 §3.1 | 설계서 §8.1 `market.*` 행에 '거래소 정본 eventType은 `market.order.created`/`market.trade.executed`; §15.10의 trade 접두 재사용은 `market` family로 환원(연동 §3.1 참조)' 주석 추가 |
| LOW | fds | `FdsDecisionCreated` webhook `riskScore` 직렬화 규약 혼재 | 설계서 §12.8 응답 예시: `"riskScore": 82.0000`(number). 연동 §4.5 webhook 예시: `"riskScore": "82.0000"`(문자열·정밀도 보존 근거 명시). 구분 없이 혼용 가능 | 설계서 §12.8 / 연동 §4.5 | 설계서 §12.8에 '동기 Decision API=JSON number; Webhook 페이로드=문자열 직렬화(연동 §4.5 정본)' 주석 추가 |
| LOW | fds | `aml.*`/`case.*` inbound 수용 금지 — reject 처리 방식 양쪽 미명시 | 설계서 §8.1·연동 §3.1 동일 제약 서술하나 거부 시 DLQ 사유 코드 양쪽 모두 불명확 | 설계서 §8.1 / 연동 §3.1·§6.3 | 연동 §6.3 DLQ 사유 코드 목록에 `FDS-FAMILY-REJECTED`(또는 `FDS-VALIDATION-002`) 항목 추가. 설계서 §8.1에 연동 §6.3 참조 링크 추가 |

---

### 대조쌍: aml:integration-design (AML 설계서 ↔ 연동 설계서)

| 심각도 | 서비스 | 항목 | 이격 내용 | 위치 | 권고 |
|---|---|---|---|---|---|
| HIGH | aml | §8.1 event family 카운트 표현 cross-reference 오류 | SW §8.1: '15종으로 종결, 연동 §3.1이 14종으로 표기한 것은 오기'라고 명시. 그러나 연동 §3.1은 이미 15종 정본으로 수정 완료 상태. SW §8.1의 cross-reference 주석만 구버전을 지칭하여 오독 유발 | SW §8.1 / Integration §2.1·§3.1 | SW §8.1의 '연동 §3.1이 14종으로 표기' 문구를 '연동 §3.1은 15종 정본과 동기화 완료'로 교체 |
| MEDIUM | aml | 아웃박스 `aggregate_type` 허용값 — outbox event_type 예시 비정본값 | SW §15.8·연동 §8.1 aggregate_type 5종 일치. 단 연동 §8.1에 `fds.feedback.applied` event_type 예시가 등장하나 §3.3/§3.4 카탈로그에 미정의 | SW §15.8 / Integration §8.1 | 연동 §8.1의 `fds.feedback.applied`를 §3.3 정본 3종(`aml.screening.true_match`/`aml.customer.high_risk`/`aml.case.str_recommended`)으로 교체 |
| MEDIUM | aml | `screening.*` family 큐명 — SW 위임 참조 구조적 이격 | SW §8.1: 큐명을 '연동 §2.1 참조'로 위임만 함. 연동 §2.1: `aml-screening-async`(internal). SW 본문에서 `screening.*`가 내부 큐임을 확인 불가 | SW §8.1 / Integration §2.1 | SW §8.1 `screening.*` 행에 '내부 큐 `aml-screening-async`(외부 ingest 비대상)' 병기 |
| MEDIUM | aml | `case.*` family 방향 정의 — SW `aml.case.*` 서술이 webhook eventType 오해 유도 | SW §8.1: 'FDS feedback·webhook은 아웃바운드(`aml.case.*`)'. 연동 §3.3: `aml.case.str_recommended`, 연동 §3.4: `webhook.callback.requested`로 별도 큐·별도 eventType. `aml.case.*`로 통칭하면 webhook eventType 오해 가능 | SW §8.1 / Integration §3.3·§3.4 | SW §8.1 `case.*` 행에 FDS feedback과 webhook의 큐명·eventType이 다름을 명확히 구분 기술 |
| LOW | aml | 아웃박스 상태머신 — maxAttempt 초과 DLQ 종단 SW 미명시 | SW §13.5.1 텍스트: `PENDING→DISPATCHING→DISPATCHED`, `DISPATCHING→FAILED→(재시도|DLQ)`. 연동 §8.1 Mermaid에 `FAILED --maxAttempt 초과--> DLQ + audit` 종단 명시. SW 미반영 | SW §13.5.1 / Integration §8.1 | SW §13.5.1에 `FAILED --(maxAttempt 초과)--> DLQ + aml_audit_events` 종단 전이 추가 |
| LOW | aml | outbox `event_type` 예시 범위 — SW §15.8 미열거로 비정본값 도입 위험 | SW §15.8이 `aml_outbox.event_type` 허용값을 미열거. 연동 §8.1이 비정본값(`fds.feedback.applied`) 도입 원인 | SW §15.8 / Integration §8.1 | SW §15.8에 event_type 허용 예시를 §3.3/§3.4 정본과 함께 병기 |
| LOW | aml | `vendor.*` family cross-reference 순환 구조 | SW §8.1: '연동 §3.1과 정합'. 연동 §3.1: 'SW §8.1에 등재'. 상호 참조로 어느 쪽이 단일 진실인지 불명확 | SW §8.1 / Integration §3.1 | SW §8.1을 단일 진실로 확정. 연동 §3.1 주석을 '정본 SW §8.1을 따른다' 단방향 참조로 교체 |

---

### 대조쌍: fds:integration-api (FDS 연동 ↔ API)

| 심각도 | 서비스 | 항목 | 이격 내용 | 위치 | 권고 |
|---|---|---|---|---|---|
| MEDIUM | fds | FdsActionResult — `completedAt` 필드 누락 | API §9.1 `FdsActionResult` 핵심 payload 표에 `completedAt` 없음. Integration §3.2·§4.3·§12에 `completedAt`(nullable) 명시됨 | API §9.1 / Integration §3.2·§4.3·§12 | API §9.1 FdsActionResult 표에 `completedAt`(nullable, camelCase↔completed_at) 추가 |
| LOW | fds | FdsDecisionCreated Webhook — `riskScore` 타입 표기 | API §9.1 핵심 payload 표에 riskScore 직렬화 타입 미명시. Integration §4.5: decimal(8,4)·문자열 직렬화 명시·예시도 문자열 | API §9.1 / Integration §4.5 | API §9.1에 riskScore 타입 `decimal(8,4), 문자열 직렬화("82.0000")` 명기 |
| LOW | fds | FdsCaseStatusChanged Webhook — `closeReason` 타입 제약 표기 부족 | API §9.1: `closeReason(nullable)`만 표기. Integration §3.2: string(64)·8종 enum 목록 상세 명시 | API §9.1 / Integration §3.2·§12 | API §9.1 closeReason 열에 'string(64), nullable, enum 8종' 표기 추가 |
| LOW | fds | IngestEventMessage `counterparty` 오브젝트 — `counterpartyType` 필드 누락 | API §5.1: `counterparty=CounterpartyDto` 참조. `CounterpartyDto` 내부 필드 정의 없음. Integration §4.2 예시: `counterpartyType: "ATM"`, `counterpartyRef`, `country` 포함 | API §5.1 / Integration §4.2 | API §5.1에 `CounterpartyDto` 필드 목록 추가(counterpartyType/counterpartyRef/country, DB 컬럼 매핑) |
| LOW | fds | IngestEventMessage `actor` 오브젝트 — `actorType` 필드 누락 | API §5.1: `actor=ActorDto` 참조. `ActorDto` 내부 필드 정의 없음. Integration §4.2 예시: `actorType: "CUSTOMER"`, `actorRef` 포함 | API §5.1 / Integration §4.2 | API §5.1에 `ActorDto` 필드 목록 추가(actorType/actorRef, DB actor_ref 컬럼 정합) |
| LOW | fds | 공통 큐 envelope `sourceSystem` 필수 조건 표기 불통일 | API §2.2: `Source-System` '선택(Ingest/Decision 필수)'. Integration §4.1: `sourceSystem` '●(event)'. 동일 규칙의 표기 방식 차이 | API §2.2 / Integration §4.1 | API §2.2 Source-System 필수 조건 표기를 '이벤트 메시지(Ingest/Decision) 필수, 기타 선택'으로 명확화 |

---

### 대조쌍: aml:integration-api (AML 연동 ↔ API)

| 심각도 | 서비스 | 항목 | 이격 내용 | 위치 | 권고 |
|---|---|---|---|---|---|
| HIGH | aml | report.submission.failed 페이로드 `errorCode` vs `submissionErrorCode` | 연동 §3.4: `report.submission.failed` 핵심 키 = `reportId`·`errorCode`. API §3.6·§8.1 정본 필드명 = `submissionErrorCode`(DB `submission_error_code`). 연동 문서 틀림 | 연동 §3.4 / API §3.6·§8.1 | 연동 §3.4 표의 `report.submission.failed` 핵심 키를 `reportId`·`submissionErrorCode`로 교체 |
| MEDIUM | aml | `aml_outbox.event_type` 예시값 `fds.feedback.applied` — 카탈로그 미정의 | 연동 §8.1에 `fds.feedback.applied` 예시. §3.3/§3.4 FDS-feedback outbox 이벤트 타입은 `aml.screening.true_match`·`aml.customer.high_risk`·`aml.case.str_recommended` 3종. `fds.feedback.applied` 미선언 | 연동 §8.1 / 연동 §3.3·§3.4 | 연동 §8.1에서 `fds.feedback.applied` 삭제 후 §3.3 정본 3종으로 교체 |
| LOW | aml | `webhook.callback.requested` 핵심 키 — `data` 내부 payload 필드 미기재 | 연동 §3.4에서 핵심 키를 `subjectRef`·`eventName(API §8.1)`으로만 요약. API §8.1은 이벤트별 data 블록 상세 필드 명시. §3.4만으로 payload 구조 추적 불가 | 연동 §3.4 / API §8.1 | 연동 §3.4 `webhook.callback.requested` 행에 `data: { eventName별 — API §8.1 정본 참조 }` 주석 추가 또는 이벤트별 data 필드 간략 열거 |

---

### 대조쌍: fds:prd-api (FDS PRD ↔ API)

| 심각도 | 서비스 | 항목 | 이격 내용 | 위치 | 권고 |
|---|---|---|---|---|---|
| HIGH | fds | CasePatchRequest.reason 필드 누락 | API §5.6 CasePatchRequest: status·priority·assignedTo 3개 필드만. PRD §11.2 BR-006: 재오픈 시 body에 `{status: IN_REVIEW, reason: <사유>}` 명시. 감사 기록 요구사항이 DTO에 미반영 | API §5.6 / PRD §11.2 BR-006 | API §5.6 CasePatchRequest에 `reason`(string, △ 선택·감사 기록용) 추가. OpenAPI §10 schema에도 반영 |
| HIGH | fds | GET /admin/fds/rules 필터 파라미터 누락 | API §4.6 필터: ruleSetId·status·channelScope 3종. PRD §6.1 SFDS-RULE-001 BR-001: 5축 필터(channelScope·status·decisionOutcome·evaluationMode·룰 번호). decisionOutcome·evaluationMode 2종 누락으로 화면 서버 필터링 불가 | API §4.6 / PRD §6.1 SFDS-RULE-001 BR-001 | API §4.6 `GET /admin/fds/rules` 필터에 `decisionOutcome`·`evaluationMode`·`ruleNo`(텍스트검색) 추가. OpenAPI §10 반영 |
| MEDIUM | fds | ExportStatus·ExportKind·ExportFormat OpenAPI 스키마 미정의 | PRD §14.1: 세 enum 코드값 정의(각 4~6종). API §5.11: prose로 기술. §10 OpenAPI schemas에 named schema 없음. ActionStatus 등 다른 핵심 enum은 schema 정의됨 | API §10 OpenAPI schemas / PRD §14.1 SFDS-EXP-001 | API §10에 ExportStatus(6종)·ExportKind(6종)·ExportFormat(4종) enum schema 신설. §5.11 필드에 $ref 연결 |
| LOW | fds | PRD 맺음말 짝 PPT 버전 포인터 불일치 | PRD 맺음말: 짝 PPT = `BO-FDS-SASS-Planning_v5.0.pptx`. PRD 헤더 §1·변경이력 v3.9: 현행 정본 `BO-FDS-SASS-Planning_v5.3.pptx` | PRD 맺음말 / PRD 헤더 §1 | PRD 맺음말 PPT 버전을 v5.0 → v5.3으로 갱신 |

---

### 대조쌍: aml:prd-api (AML PRD ↔ API)

| 심각도 | 서비스 | 항목 | 이격 내용 | 위치 | 권고 |
|---|---|---|---|---|---|
| HIGH | aml | AML.TENANT_NOT_FOUND HTTP 상태코드 | API §4 에러 테이블: HTTP 409. API §5 OpenAPI paths(GET·PUT /tenants/{tenantId}): HTTP 404. PRD 부록 D: 404. API §4 에러 테이블 틀림 | API §4 에러 테이블 / API §5 OpenAPI paths / PRD 부록 D | API §4 에러 테이블의 AML.TENANT_NOT_FOUND HTTP 상태코드 409 → 404로 수정 |
| MEDIUM | aml | TNT-002 ③ 소스 시스템 탭 — sourceType / connectionStatus 필드 | PRD: `sourceType`(CORE/TRANSACTION/KYC)·`connectionStatus`(정상/오류/미연결). API §3.9 SourceSystemDto에 두 필드 없음 | PRD §13.2 TNT-002 ③ / API §3.9 SourceSystemDto | API §3.9 SourceSystemDto에 sourceType·connectionStatus 추가 또는 PRD에서 기존 ingestMode/status로 대체 |
| MEDIUM | aml | TNT-002 ④ 정책팩 탭 — policyPackVersion / ctrThreshold / raHighThreshold 필드 | PRD ④ 탭: policyPackVersion·ctrThreshold·raHighThreshold 명시. API §3.16 TenantDto에 세 필드 없음 | PRD §13.2 TNT-002 ④ / API §3.16 TenantDto | API §3.16 TenantDto에 세 필드 추가 또는 PRD에 별도 PolicyPackDto 조회 경로 명시 |
| MEDIUM | aml | TNT-002 ③ 소스 시스템 탭 — scope 부여 누락 | API §2.7: GET/POST /admin/aml/source-systems = scope `aml:admin:source-system`. PRD 부록 B AML-TNT-002에 `aml:admin:policy(●)`만 표시. ③ 탭 접근 시 403 발생 위험 | PRD 부록 B / API §2.7 | PRD 부록 B AML-TNT-002에 `admin:source-system(●)` 행 추가 또는 '③ 탭 추가 scope 필요' 주석 명기 |
| MEDIUM | aml | WLF-003 면제(FP_WHITELIST) 건수 집계 API 미정의 | PRD WLF-003 요약 카드: 면제(FP_WHITELIST) 건수 표시. FP_WHITELIST는 screening_status가 아닌 approvals.subjectType. FP_WHITELIST 건수 집계 전용 API 호출 미정의 | PRD §3.3 WLF-003 BR-002 / API §3.2·§2.7 | PRD §3.3 또는 API에 면제 건수 집계 API 호출 `GET .../approvals?subjectType=FP_WHITELIST&status=EXECUTED` 명시 |
| LOW | aml | PRD §1.7 결재 상태머신 — DRAFT 상태 화면 노출 | PRD §1.7: `[*] --> DRAFT`로 시작하여 DRAFT를 첫 관찰 가능 상태처럼 표현. API §1.5: DRAFT는 API 미노출, 첫 관찰 상태는 SUBMITTED | PRD §1.7 / API §1.5·§3.7 | PRD §1.7 다이어그램에서 DRAFT·전이 제거 후 `[*] --> SUBMITTED`로 변경 또는 'DRAFT = 내부 엔진 상태·화면 미노출' 주석 명시 |
| LOW | aml | 부록 B 권한 매트릭스 — 드릴다운·앞단 화면 8종 누락 | PRD §12-A에 정의된 8개 화면(AML-WL-002, AML-CTRY-001, AML-RA-003, AML-CDD-001, AML-PP-001, AML-TM-002, AML-CASE-002, AML-REP-002)이 부록 B에 행 없음 | PRD 부록 B / PRD §12-A | 부록 B에 누락 8개 화면 행 추가 및 각 scope 조합 기입 |
| LOW | aml | PRD §9.1 AML-REP-001 — slaStatus 필드 미명시 | API §3.6 RegulatoryReportDto에 slaStatus(ON_TIME/DUE_SOON/OVERDUE) 정의. PRD §9.1 데이터 항목 표에 slaStatus 필드명 미기재. BR-006 배지 동작 기술하나 slaStatus 값 연결 없음 | PRD §9.1 / API §3.6 | PRD §9.1 데이터 항목 표에 slaStatus(ON_TIME/DUE_SOON/OVERDUE) 행 추가. BR-006 배지가 slaStatus 값에서 파생됨을 명시 |

---

### 대조쌍: fds:ppt-prd (FDS PPT ↔ PRD)

| 심각도 | 서비스 | 항목 | 이격 내용 | 위치 | 권고 |
|---|---|---|---|---|---|
| MEDIUM | fds | SFDS-RULE-003 룰 빌더 ① 행 — 탐지 시 동작 필드 | PRD §6.3 와이어프레임 ① 행: '도메인/채널 + 탐지 시 동작 [자금보류 ▼]'. PPT 슬라이드 23 ① 행: '도메인/채널 + 평가 방식'만 표시. PPT가 틀림(정본=PRD) | PRD §6.3 / PPT 슬라이드 23 | PPT 슬라이드 23 ① 행에 '탐지 시 동작* [자금보류 ▼]' 드롭다운 추가 |
| LOW | fds | PRD §16 맺음말 짝 문서 버전 포인터 | PRD 맺음말: `BO-FDS-SASS-Planning_v5.0.pptx`. PRD §1 헤더: v5.3이 정본. 맺음말이 구버전(v5.0) 동결 | PRD 맺음말 / PRD §1 헤더 | PRD 맺음말 v5.0 → v5.3으로 정정(슬라이드 수·변경 내역 v5.3 기준 업데이트) |
| LOW | fds | SFDS-ACT-002 Capability 매트릭스 컬럼 — CAN_EXTEND_HOLD·CAN_REQUEST_REVERSAL 미표시 | PRD §10.2 데이터 항목: control_capability 9종. PRD 와이어프레임·PPT 슬라이드 35: 7컬럼. 2종(보류 연장·역행 요청) 독립 컬럼 미표시. 양쪽 동일하게 누락하여 내부 정합은 유지되나 9종 선언과 7컬럼 표시 불일치 | PRD §10.2 / PPT 슬라이드 35 | PRD §10.2에 묶음 컬럼 처리 이유 주석 명시 또는 와이어프레임·PPT에 독립 컬럼 추가 |

---

### 대조쌍: aml:ppt-prd (AML PPT ↔ PRD)

| 심각도 | 서비스 | 항목 | 이격 내용 | 위치 | 권고 |
|---|---|---|---|---|---|
| MEDIUM | aml | TNT-002 ③ 소스 시스템 탭 — sourceType CORE 표시명 | PRD 정본: 종류 컬럼 표시명 = '핵심(CORE)'. PPT 슬라이드 12: '회원·계좌 (CORE)'. PRD에 없는 표시명으로 PPT가 오류 | PRD §13.2 ③ / PPT 슬라이드 12 | PPT 슬라이드 12의 표시명을 '핵심(CORE)'으로 PRD §13.2 정본에 맞춰 수정 |
| MEDIUM | aml | REP-001 ① STR 후보 목록 — '발단' 컬럼 초과 | PRD §9.1 ASCII 와이어프레임: 7컬럼(발단 없음). PPT 슬라이드 39: 8컬럼(발단 추가). PRD 미정의 컬럼 PPT에 추가되어 PPT가 오류 | PRD §9.1 / PPT 슬라이드 39 | PPT 슬라이드 39에서 '발단' 컬럼 제거 또는 PRD §9.1에 발단 컬럼 추가 후 정합 |

---

### 대조쌍: fds:ppt-flow (FDS PPT 생성기 ↔ PRD 흐름)

| 심각도 | 서비스 | 항목 | 이격 내용 | 위치 | 권고 |
|---|---|---|---|---|---|
| MEDIUM | fds | history_slide 변경이력 행 v4.9~v5.3 문구 — 한 줄 요약 초과 | SKILL §1.6 원칙 7(변경이력 한 줄 요약). v4.9·v5.0·v5.1·v5.2·v5.3 행의 변경 내역이 복수 항목 열거로 2줄 이상 정보 담음. PPT 셀 폭 0.70으로 넘침 발생 가능 | generate_fds.py history_slide v4.9~v5.3 행 | 각 버전별 가장 대표적인 한 줄 요약 하나만 남기도록 단축 |
| MEDIUM | fds | SFDS-ACT-002 entry_banner 소스 화면 표기 — PRD §10.2 불완전 | 생성기 act_002() entry_banner가 TNT-002 ③탭 단일 진입 경로만 기술. PRD §10.2·§16.1에는 CONN-002 설정 변경 흐름도 진입 경로로 포함 | generate_fds.py act_002() / PRD §10.2 | entry_banner에 'SFDS-CONN-002 설정 변경 흐름 → Capability 매트릭스' 경로 추가 |
| MEDIUM | fds | SFDS-GRP-001 groupId 표시명 혼재 가능성 | grp_003() form_block 첫 행 레이블 '그룹 코드 *'. PRD §7.3 필드는 groupId(immutable). '그룹 코드'와 groupId 혼재 우려 | generate_fds.py grp_003() / PRD §7.3 | grp_003() form_block 레이블을 '그룹 코드(=groupId) *'로 표기 또는 info_panel에 groupId 연계 명시 |
| LOW | fds | SFDS-TNT-001 callout 문구 — 5탭 구성 표기 불일치 | 생성기 callout: '5탭: 기본정보·배포·온보딩·마스킹·보안·Policy Pack·알림·소스'(7개 키워드). PRD §3.2: 5탭 레이블 = ①기본 정보/②배포·온보딩/③마스킹·보안/④Policy Pack/⑤알림·소스 | generate_fds.py tnt_001() / PRD §3.1 BR-003·§3.2 | callout 문구를 PRD §3.2 탭 레이블 5개 그대로 표기 |
| LOW | fds | SFDS-RULE-002 ① 현재버전 탭 entry_banner 누락 | tnt_002_basic()·case_002(): tab_chips() → entry_banner() → two_panels() 패턴. rule_002(): entry_banner 없이 tab_chips() → callout() → two_panels(). SKILL §1.6·PRD v3.3 드릴다운 배너 원칙 미적용 | generate_fds.py rule_002() / SKILL §1.6 | rule_002() 함수에 tab_chips() 직후 entry_banner() 추가 |

---

### 대조쌍: aml:ppt-flow (AML PPT 생성기 ↔ PRD 흐름)

> 아래 항목 중 이격 없음(VERIFIED)으로 확인된 항목은 생략하고 실제 이격만 기재한다.

| 심각도 | 서비스 | 항목 | 이격 내용 | 위치 | 권고 |
|---|---|---|---|---|---|
| HIGH | aml | SCREENS 화면 수 — PRD '총 23화면' vs 생성기 24 기능 ID(CTRY-001·CDD-001 포함) | PRD §1.2 화면 범위 표에 CTRY-001·CDD-001 미등재. 생성기 SCREENS에는 ctry_001·cdd_001 포함. '23화면'과 '51 기능 슬라이드(+커버/이력 2=53)' 괴리. PRD 커버 notes에 '기능 ID 전수 23화면' 고정됨 | generate_aml.py SCREENS / PRD §1.2 | PRD §1.2 화면 범위 표에 CTRY-001·CDD-001 명시 추가 또는 '총 25화면'으로 수정. 또는 §1.2에 '§12-A 앞단 관리 화면으로 별도 표기' 설명 추가 |
| MEDIUM | aml | SCREENS 배열 내 AML-RA-003 위치 — 이격 없음 확인 | SCREENS: ra_001(tab=0·1) → ra_003(tab=0~2) → ra_002(tab=0~3). PRD §5.6 정본 순서 RA-001→RA-003→RA-002와 일치 | generate_aml.py SCREENS / PRD §5.6 | 이격 없음 — 확인 완료 |
| MEDIUM | aml | REP-001 STR 후보 '종류' 컬럼 생성기 포함 여부 — 이격 없음 확인 | 생성기 rep_001(tab=0) 헤더에 '종류' 컬럼 포함. PRD §9.1과 일치 | generate_aml.py rep_001 / PRD §9.1 | 이격 없음 — 확인 완료 |
| MEDIUM | aml | WLF-003 KPI 카드 순서 — 이격 없음 확인 | 생성기 순서 = PRD §3.3 ASCII 순서와 일치 | generate_aml.py wlf_003 / PRD §3.3 | 이격 없음 — 확인 완료 |
| MEDIUM | aml | DASH-001 '결재 대기' KPI 카드 — 이격 없음 확인 | 생성기 '결재 대기 5건·만료 임박 2 ⚠' = PRD §2.1 일치 | generate_aml.py dash_001 / PRD §2.1 | 이격 없음 — 확인 완료 |
| MEDIUM | aml | AML-TNT-001 필터 region= 파라미터 — 이격 없음 확인 | 생성기 tnt_001 info_panel에 region= optional 표기. PRD §13.1 BR-001 정합 | generate_aml.py tnt_001 / PRD §13.1 | 이격 없음 — 확인 완료 |
| MEDIUM | aml | AML-TM-001 ② 시나리오 목록 타이틀 아웃바운드 ID — 이격 없음 확인 | 생성기 tm_001(tab=1) 타이틀에 '행 ▶ → AML-TM-002' 포함. PRD v5.11 변경이력 정합 | generate_aml.py tm_001 / PRD §7.1 | 이격 없음 — 확인 완료 |
| MEDIUM | aml | 소스 목록 화면 행/버튼 아웃바운드 표기 — 이격 없음 확인 | ra_001/tm_001/case_001/rep_001 등 테이블 타이틀에 '행 ▶ → AML-XXX' 전수 포함. PRD v5.10 정합 | generate_aml.py 각 함수 / PRD v5.10 | 이격 없음 — 확인 완료 |
| MEDIUM | aml | AML-CASE-001 단순 필터 탭 1슬라이드 유지 — 이격 없음 확인 | case_001 함수 탭 분기 없이 단일 슬라이드. SKILL §1.6 정합 | generate_aml.py case_001 / SKILL §1.6 | 이격 없음 — 확인 완료 |
| MEDIUM | aml | AML-APR-001 단순 필터 탭 1슬라이드 유지 — 이격 없음 확인 | apr_001 함수 탭 분기 없이 단일 슬라이드. SKILL §1.6 정합 | generate_aml.py apr_001 / SKILL §1.6 | 이격 없음 — 확인 완료 |
| MEDIUM | aml | RA-003 SCREENS 배열 RA-001 ② 직후 배치 — 이격 없음 확인 | SCREENS: ra_001(tab=1) 직후 ra_003(tab=0~2). v5.6 정본 순서 일치 | generate_aml.py SCREENS / PRD §5.6 | 이격 없음 — 확인 완료 |
| MEDIUM | aml | REP-001/REP-002 SCREENS 인접 배치 — 이격 없음 확인 | SCREENS: rep_001(tab=0~2) 직후 rep_002(tab=0~2). 소스→드릴다운 흐름 단절 없음 | generate_aml.py SCREENS / PRD §9.1 | 이격 없음 — 확인 완료 |
| LOW | aml | 변경이력 history_slide 행 — 장문 여부 | v4.0·v5.5·v5.9 행 변경 내역이 한 줄 요약보다 다소 길고 복수 항목 나열. PPT col_w 0.70으로 자동 줄 바꿈 가능 | generate_aml.py build() history_slide | v5.5(13화면 목록)·v5.9(4가지 항목) 등 단일 요약 문장으로 압축 권고 |

---

### 대조쌍: fds:wbs-design (FDS WBS ↔ 설계서)

| 심각도 | 서비스 | 항목 | 이격 내용 | 위치 | 권고 |
|---|---|---|---|---|---|
| MEDIUM | fds | T-13 wallet/account 룰팩 참조 섹션 부재 | T-13 참조가 §15.1~15.5이나 설계서 §15에 Wallet 섹션 없음. wallet/account 룰팩 이벤트 시퀀스·feature·가능 action의 설계서 정본 섹션 미명시 | docs/tasks/fds/13-domain-rulepacks.md / 설계서 §15·§4.1·§18 | 설계서에 §15.x Wallet/Account Transfer 섹션 추가 또는 T-13 참조에 §4.1(Wallet 도메인)·'설계서 §15 Wallet 섹션 미정의' 오픈 항목 기록 |
| MEDIUM | fds | T-11 참조 — `rule_status`(§11.6.5)·`rule_version_status`(§11.6.6) 미참조 | T-11 구현 항목에 rule 활성화·rollback·version 관리 포함하나 rule 상태머신 정본 섹션 참조 누락 | docs/tasks/fds/11-rule-admin-simulation.md / 설계서 §11.6.5·§11.6.6 | T-11 참조에 §11.6.5(rule_status 5종)·§11.6.6(rule_version_status 5종) 추가 |
| MEDIUM | fds | T-16 참조 — `case_status`(§11.6.1)·`case_priority`(§11.6.2) 미참조 | T-16 참조에 §11.3만 있고 case_status 8종 전이도·close_reason 8종·case_priority 4종 섹션 참조 없음 | docs/tasks/fds/16-case-management.md / 설계서 §11.6.1·§11.6.1a·§11.6.2 | T-16 참조에 §11.6.1·§11.6.1a·§11.6.2 추가 |
| LOW | fds | 부록 A 산출물 일습 매핑 — DB 경로 패턴 불일치 | 설계서 §부록 A: DB 경로 `docs/design/db/01-fds-*-db.md`(비실재 패턴). 실제 파일 `docs/design/db/01-fds-db.md` | 설계서 §부록 A / 실제 파일 경로 | 설계서 §부록 A DB 경로를 `docs/design/db/01-fds-db.md`로 정정 |

---

### 대조쌍: aml:wbs-design (AML WBS ↔ 설계서)

| 심각도 | 서비스 | 항목 | 이격 내용 | 위치 | 권고 |
|---|---|---|---|---|---|
| MEDIUM | aml | WBS §7 오픈결정 D-번호 체계 불일치 및 헤더 클레임 과장 | WBS §7 헤더 '설계서 §22와 정합, 신규 미정 없음'이나 14개 중 7개만 등재. WBS D-01 = SW §22 D-06(배포 모델). SW §22 D-01(명단 source)은 WBS에 없음. 번호 체계 상이 | docs/tasks/aml/00-overview.md §7 / 설계서 §22 | WBS §7 헤더를 '태스크 귀속 항목 선별 등재(D-번호는 WBS 고유 순번)'로 수정. 각 항목에 '(SW §22 D-NN 대응)' 병기 |
| LOW | aml | WBS 변경이력 T-12 subjectType '14종' vs SW '16종' | WBS 변경이력(2026-06-07): 'subjectType 전수 14종 명기'. SW §13.4·§13.5 정본: 16종(CHECKLIST_CHANGE·PERIODIC_REVIEW_CHANGE 포함) | docs/tasks/aml/00-overview.md 변경이력 / 설계서 §13.4·§13.5 | WBS 변경이력 2026-06-07 항목의 '14종'을 '16종' 또는 '추후 16종으로 확장' 주석 추가 |
| LOW | aml | WBS T-20 metric 범위 — T-17과 귀속 분산 | WBS T-20: metric 전반 포함. §5 STR/CTR 보고 행: `aml.report.sla.breached`를 T-17 귀속으로 명시. T-20 제목 선언과 충돌 | docs/tasks/aml/00-overview.md §2·§5 / 설계서 §20.1 | WBS T-20에 'SLA metric은 도메인 태스크(T-17·T-13) 소유·T-20은 수집 인프라·대시보드 집약 담당' 구분 명시 |

---

### 대조쌍: fds:wbs-roadmap (FDS WBS ↔ 로드맵)

| 심각도 | 서비스 | 항목 | 이격 내용 | 위치 | 권고 |
|---|---|---|---|---|---|
| HIGH | fds | T-10 의존 열 — T-09 누락 | WBS §2 T-10 의존: `T-05,T-15`. §3 Mermaid 그래프: `T09 --> T10` 엣지 포함. §3 그래프가 정본이며 §2 테이블 틀림 | docs/tasks/fds/00-overview.md §2 T-10 / §3 의존 그래프 | WBS §2 T-10 의존 칸을 `T-05,T-09,T-15`로 수정 |
| HIGH | fds | T-10 의존 — T-11 누락 (WBS ↔ Phase 2 파일) | WBS §2·§3 모두 T-11을 T-10 선행으로 표기 없음. 로드맵 Phase 2 P2-FDS-03 의존: `P1-FDS-04,P2-FDS-04,P2-FDS-06`(=T-05,T-11,T-15). T-11 선행 직접 명시. 정본=Phase 2 파일 | docs/tasks/fds/00-overview.md §2·§3 / 03-phase2-engines-mvp.md P2-FDS-03 | WBS §2 T-10 의존을 `T-05,T-09,T-11,T-15`로 수정. §3 Mermaid에 `T11 --> T10` 엣지 추가 |
| MEDIUM | fds | WBS §5 BO 인벤토리 '정산 보류 큐·도메인 액션' 행 — T-18 보류 태스크 병기 | §5 해당 행 태스크 `T-13,T-18`. T-18은 §2에서 `—(보류: 정책 확정 후 별도 WBS, Phase 미배치)`. 보류 태스크와 활성 태스크 병기로 범위 오해 유발 | docs/tasks/fds/00-overview.md §5 | §5 해당 행 태스크 칸을 `T-13`으로 수정. T-18은 보류 주석 별도 명시 |
| MEDIUM | fds | T-18 Status enum — `TODO` vs 보류 상태 불일치 | WBS §2 T-18 Status = `TODO`. Due = `—(보류: Phase 미배치)`. `TODO`는 활성 범위 태스크 의미로 보류 상태와 충돌 | docs/tasks/fds/00-overview.md §2 T-18 | T-18 Status를 `DEFERRED` 또는 `ON_HOLD`로 변경. 또는 WBS 범례에 보류 상태값 추가 |

---

### 대조쌍: aml:wbs-roadmap (AML WBS ↔ 로드맵)

| 심각도 | 서비스 | 항목 | 이격 내용 | 위치 | 권고 |
|---|---|---|---|---|---|
| MEDIUM | aml | T-22 의존 그래프 — T-03 선행 의존 누락 | WBS T-22 의존 = 'T-06, T-07, T-17, T-20'. 로드맵 P8-AML-01 의존에 T-03(고객사 레지스트리·배포 모델·온보딩) 선행 명시. WBS mermaid에 `T03→T22` 엣지 없음 | docs/tasks/aml/00-overview.md §2·§3 / P8-AML-01 | WBS §2 T-22 의존 컬럼에 T-03 추가. §3 mermaid에 `T03 --> T22` 엣지 추가 |
| MEDIUM | aml | 06-phase5-bo-web.md §2.2 섹션 제목 — `FDS 화면(31)` vs 본문 32화면 | §2.2 섹션 헤더만 `(31)` 구버전 잔류. 헤더·§1·§5·00-program-overview §2 모두 32화면으로 업데이트됨 | docs/tasks/aegis-aml/06-phase5-bo-web.md §2.2 | §2.2 섹션 헤더를 `FDS 화면(32)`으로 정정 |
| LOW | aml | 06-phase5-bo-web.md §4 설계 근거 — FDS 화면 수(31)·PPT 버전(v5.3) 미갱신 | §4: `SFDS-* 31화면`·`PPT v5.3`. 확정값: 32화면·PRD v5.9·PPT v5.9 | docs/tasks/aegis-aml/06-phase5-bo-web.md §4 | §4 FDS 라인을 `SFDS-* 32화면`·`PRD v5.9·PPT v5.9`로 갱신 |

---

### 대조쌍: fds:roadmap-design (FDS 로드맵 ↔ 설계서)

| 심각도 | 서비스 | 항목 | 이격 내용 | 위치 | 권고 |
|---|---|---|---|---|---|
| MEDIUM | fds | P7 §4 FDS 설계 근거 — `§18 Phase 6(관측성·보안)` 오인용 | 설계서 §18 Phase 6 실제 제목: 'Audit Evidence Hub + legacy bridge'. 관측성=§17, 보안=§16이 정본. P7 §4가 §18을 관측성·보안 출처로 기재하여 §번호-내용 불일치 | docs/tasks/aegis-aml/08-phase7-ops-hardening.md §4 / 설계서 §16·§17·§18 | P7 §4 FDS 근거를 `§17(운영·관측성)·§16(보안·컴플라이언스·감사)·§18 Phase 6(legacy bridge 범위)`로 정정 |
| MEDIUM | fds | P5 §2.2 섹션 헤더 화면 수 — `FDS 화면(31)` vs 본문 32화면 | §2.2 헤더만 `(31)` 잔류. 헤더·§1·§5·00-program-overview 모두 32화면 | docs/tasks/aegis-aml/06-phase5-bo-web.md §2.2 | §2.2 헤더를 `FDS 화면(32)`으로 정정 |
| MEDIUM | fds | P5 §4 설계 근거 — `SFDS-* 31화면` 구버전 잔류 | §4에 `SFDS-* 31화면`. §1·§5·헤더는 이미 32화면으로 업데이트됨 | docs/tasks/aegis-aml/06-phase5-bo-web.md §4 | `SFDS-* 31화면` → `SFDS-* 32화면`으로 정정 |
| LOW | fds | P5 §3·§4 AML PPT 버전 불일치 — `PPT v5.3` vs 헤더 `PPT v5.9` | 헤더(line 3): v5.9 업데이트됨. §3·§4: `PPT v5.3` 잔류 | docs/tasks/aegis-aml/06-phase5-bo-web.md §3·§4 | `PRD §13 재구성본·PPT v5.3` → `PRD §13·PPT v5.9`로 통일 |
| LOW | fds | P4 §4 FDS 근거 `§12(action·case·approval)` 오인용 | 설계서 §12 실제 내용: 외부 시스템 연동 방식(connector). approval 정본=§11.5. 개발자가 §12에서 결재 설계 도출 불가 | docs/tasks/aegis-aml/05-phase4-action-case-approval.md §4 / 설계서 §11.5·§12 | `§11.2/§12(action·case·approval)` → `§11.2(action)·§11.5(결재 시스템)·§12.6a(action outbox·handoff 토폴로지)`로 정정 |
| LOW | fds | P0 §2 `target-architecture.md §3.3` 비존재 subsection 참조 | target-architecture.md에 `§3.3` 번호 체계 없음. bo-api 설명은 `### services/bo-api` prose로 존재 | docs/tasks/aegis-aml/01-phase0-foundation.md §2 / target-architecture.md | `§3.3` → `§3(services/bo-api 항)`으로 정정 |
| LOW | fds | P5 헤더 `target-architecture.md §3.4` 비존재 subsection | `§3.4` 번호 체계 없음. bo-web 설명은 `### services/bo-web` prose | docs/tasks/aegis-aml/06-phase5-bo-web.md 헤더 | `§3.4(bo-web)` → `§3(services/bo-web 항)`으로 정정 |
| LOW | fds | P1 §4 `§19/§22 D-01/D-06/D-13` FDS·AML 혼합 표기 | `§19`=FDS 오픈결정, `§22`=AML 오픈결정을 공통 표기로 합쳐 D-번호 소속 불명확 | docs/tasks/aegis-aml/02-phase1-core-infra.md §4 | 서비스별 분리 표기: `docs/software/01-fdsSvc-sass.md §19(D-번호)`, `docs/software/02-amlSvc-sass.md §22(D-번호)` |

---

### 대조쌍: aml:roadmap-design (AML 로드맵 ↔ 설계서)

| 심각도 | 서비스 | 항목 | 이격 내용 | 위치 | 권고 |
|---|---|---|---|---|---|
| HIGH | aml | 오픈 결정 D-번호 오인용 — isolation_mode=D-01·raw PII=D-06 | 로드맵 §6: 'isolation_mode 폐기 확정·D-01 결정(§19 — D-06은 raw payload)'. 설계서 §22: D-01=명단 source, D-05=raw PII, D-06=배포 모델/isolation_mode 폐기. 3중 오류(번호·내용·§참조) | docs/tasks/aegis-aml/00-program-overview.md §6 / 설계서 §22 | 로드맵 §6 구절을 'isolation_mode 폐기 확정·**D-06** 결정(설계서 §22), raw PII 미저장(D-05, tenant-managed tokenization)'으로 교정 |
| MEDIUM | aml | P2 헤더 AML 설계 §21 Phase 2만 인용 — RA·TM 누락 | 헤더: `§21 Phase 2`만. P2 범위에 RA 모델(§21 Phase 3)·TM scenario MVP(§21 Phase 4)·결재 엔진 골격(§13.5) 포함 | docs/tasks/aegis-aml/03-phase2-engines-mvp.md 헤더 / 설계서 §21·§13.5 | 헤더 AML 인용을 `§21 Phase 2~4(WLF·RA·TM 엔진 MVP), §13.5(결재 시스템 골격)`으로 확장 |
| MEDIUM | aml | P3 헤더 AML 설계 §21 Phase 3 라벨 모호 — RA P2 완료분 미명시 | 헤더: `§21 Phase 3`. §21 Phase 3에 RA가 포함되어 있으나 RA는 P2 완료. P3 범위는 CDD/EDD·country risk·policy pack | docs/tasks/aegis-aml/04-phase3-domain-boapi.md 헤더 / 설계서 §21 | 헤더를 `§21 Phase 3 中 CDD/EDD·country risk·policy pack(RA는 P2 완료)` 등으로 명확화 |
| LOW | aml | 설계서 변경이력 2026-06-08 aml_tenants.status 종수 3→4 미갱신 | 2026-06-08 이력: '`status` 3종'. 2026-06-11 이력 4종 교정. 본문 §16.0c는 4종 올바름. 이력란만 3종 잔류 | 설계서 변경이력 2026-06-08 행 / §16.0c | 2026-06-08 이력 항목의 '3종'→'4종' 교정 또는 '2026-06-11 4종으로 정정됨' 각주 추가 |
| LOW | aml | P6 헤더 AML 설계 §21 Phase 5~6 인용 — Phase 6 UI 소관 혼동 | §21 Phase 6(Compliance Operations Console UI)는 P5(bo-web) 소관. P6 헤더에 범위 혼동 유발 | docs/tasks/aegis-aml/07-phase6-regulatory-integration.md 헤더 / 설계서 §21 | P6 헤더를 `§21 Phase 5(Regulatory reporting)·§14·§15.6·§19.2a`로 구체화. §21 Phase 6 UI는 P5 소관 명시 |

---

### 대조쌍: cross:naming-tenancy-pii (FDS ↔ AML 교차 명칭·테넌시·PII)

| 심각도 | 서비스 | 항목 | 이격 내용 | 위치 | 권고 |
|---|---|---|---|---|---|
| HIGH | cross | tenant_status enum 교차 주석 구버전 잔류 | FDS §11.6.7 교차 주석에 'AML 3종 OFFBOARDING'이라고 기재됨. AML §16.0c V20 교정(4종·OFFBOARDED)과 충돌. 두 서비스 4종 정합됐으나 FDS 교차 주석만 구버전 | FDS §11.6.7 / AML §16.0c | FDS §11.6.7 교차 주석의 'AML 3종 OFFBOARDING'을 'AML 4종 OFFBOARDED(§16.0c V20 교정 후 동기화)'로 갱신 |
| MEDIUM | cross | PII 마스킹 대상 목록 — FDS 7종 vs AML 5종 | FDS §16.1: 7종(휴대폰번호·가상자산 주소 포함). AML §19.2: 5종(휴대폰번호·가상자산 주소 누락). target-architecture §4.1에 목록 없음 | FDS §16.1 / AML §19.2 / target-architecture §4.1 | AML §19.2에 휴대폰번호·가상자산 주소 추가. target-architecture §4.1에 7종 목록 정본으로 추가 권고 |
| MEDIUM | cross | 규제 보고 상태머신(report_status) 교차 참조 부재 | FDS: REGULATORY_REPORT action을 aml-svc로 위임. AML: 8종 report_status 상태머신 정의. FDS에 위임 후 AML report_status 추적 방법 기술 없음 | FDS §11.2·§12.6a / AML §14.1a | FDS §11.2 또는 §12.6a에 'REGULATORY_REPORT 위임 후 보고 수명주기는 AML §14.1a 정본이며 FDS는 aml_case_id cross-ref로 연결만 유지' 주석 추가 |
| MEDIUM | cross | ingest_mode enum 종수 비대칭 — bo-web UI 미반영 | FDS: 5종. AML: 6종(VENDOR_BRIDGE 추가). 의도된 차이로 양쪽 명문화됨. 단 bo-web 단일 Admin 콘솔 구현 시 ingest_mode 드롭다운 서비스별 차이 UI 명세 미반영 | FDS §11.6.8 / AML §17.1 DDL·§8.1 / bo-web PRD | bo-api/bo-web 관련 문서 또는 PRD source system 관리 화면에 'FDS=5종, AML=6종(VENDOR_BRIDGE 포함)' 명시 |
| MEDIUM | cross | Policy Pack 모델 구조 비대칭 — bo-web PRD 미반영 | FDS: named pack 개별 토글 모델. AML: KR_DEFAULT 단일 번들 + plugin 추가. bo-web 고객사 상세 Policy Pack 관리 화면에 두 모델 차이 명세 미반영 | FDS §16.2 / AML §5.5 / bo-web PRD | bo-web PRD Policy Pack 관리 화면 명세에 '두 서비스 팩 구조 다름·화면 레이아웃 서비스별 분리' 설계 결정 명시 |
| MEDIUM | cross | subjectKind/subjectType enum 비대칭 — bo-api 분리 명세 부재 | FDS: approval_requests.subject_kind 9종. AML: approvals.subject_type 16종. 컬럼명·값 체계 상이. bo-api 결재 집약 시 통합 enum 없음이 명시되어야 함 | FDS §11.5 / AML §13.4·§13.5 | FDS §11.5·AML §13.4 양쪽에 'bo-api는 엔진별 결재 API를 별도 경로로 집약, 통합 enum 없음' 교차 주석 추가 |
| LOW | cross | approval_line enum 비대칭 — SELF_APPROVAL_DISABLED 위상 차이 | FDS: SELF_APPROVAL_DISABLED = enum 멤버. AML: 횡단 불변식(enum 외부). 동일 값의 위상이 서비스별로 다름. bo-api PRD에 드롭다운 독립 제공 미반영 | FDS §11.5 / AML §13.5 | 양쪽 교차 주석에 비대칭 명시. bo-api 결재 집약 API에서 두 서비스 approval_line 드롭다운이 독립 제공됨을 PRD에 반영 |
| LOW | cross | 규제 보고 법정 보존기간 — FDS 미명시 | AML §19.3: 감사로그 7년 보존(hash chain 영구) 명문화. FDS 설계서에 감사로그 7년 보존 직접 명시 없음(§14.1 DDL 주석에만 간접 언급) | FDS §14·§16.3 / AML §19.3 | FDS §16.3 감사 원칙 절에 fds_audit_logs 보존기간(7년, hash chain 영구)을 법적 근거와 함께 명시 |
| LOW | cross | PII 원문 접근 통제 scope — FDS에 fds:pii:reveal 부재 | AML: `aml:pii:reveal` scope 명시(§15.7·§1.6). FDS §12.8 scope 11종에 raw data access 전용 scope 없음. FDS가 AML보다 PII 접근 통제 덜 구체화 | FDS §16.1·§16.3·§12.8 / AML §15.7·§19.2 | FDS §12.8 scope 목록에 `fds:pii:reveal` 추가. FDS §16.3에 raw data access를 별도 audit 이벤트 코드로 명시 |
| LOW | cross | 감사로그 보존기간 표기 통일 — FDS §14.1 DDL 주석 간접 표기 | FDS §14.1 DDL 주석: 'tenant별 7년 감사 보존' 간접 언급. AML §19.3: 명확히 직접 명시. 같은 요건을 서로 다른 방식으로 기술 | FDS §16.3 / AML §19.3 | FDS §16.3에 AML §19.3과 동일 수준의 명확한 보존기간 명시 |

---

## ④ 개발 착수 권고

### HARD GATE 조건 (착수 전 반드시 해소)

| 순위 | 항목 | 대조쌍 | 이유 |
|---|---|---|---|
| 1 | ActionResponse.actionType 필드 누락 | fds:api-db | 클라이언트·감사 추적 직접 차질 |
| 2 | report.submission.failed `errorCode` → `submissionErrorCode` | aml:integration-api | 연동 페이로드 필드명 오기로 소비자 파싱 실패 |
| 3 | AML.TENANT_NOT_FOUND HTTP 상태코드 409 → 404 | aml:prd-api | API 내부 불일치로 클라이언트 에러 처리 혼동 |
| 4 | CasePatchRequest.reason 필드 누락 | fds:prd-api | PRD 재오픈 감사 요구사항이 DTO에 미반영 |
| 5 | GET /admin/fds/rules 필터 파라미터 누락(decisionOutcome·evaluationMode) | fds:prd-api | 화면 5축 필터 중 2종 서버 필터링 불가 |
| 6 | event family 카운트 cross-reference 오류(SW §8.1 '14종 오기' 지칭) | aml:integration-design | 이미 수정된 연동 §3.1을 오기로 지칭하여 역방향 혼란 |
| 7 | T-10 의존 T-09·T-11 누락 | fds:wbs-roadmap | 착수 순서 오류로 병렬 빌드 시 Race Condition |
| 8 | SCREENS 화면 수 PRD '23화면' vs 생성기 24 기능 ID | aml:ppt-flow | PPT 커버 notes 고정 수치와 실제 생성 슬라이드 불일치 |
| 9 | D-번호 오인용 isolation_mode=D-01(실제 D-06) | aml:roadmap-design | 오픈 결정 추적 혼단 및 잘못된 §참조로 결정사항 도출 불가 |
| 10 | tenant_status enum FDS §11.6.7 교차 주석 구버전(3종·OFFBOARDING) 잔류 | cross:naming-tenancy-pii | FDS·AML 공유 enum 불일치 오해로 DB 마이그레이션 오류 가능 |
| 11 | T-10 의존 T-11 로드맵↔WBS 이격(별도 검증 필요) | fds:wbs-roadmap | Phase 2 정본 P2-FDS-03 의존과 WBS §2·§3 불일치 |

### 권고 사항

1. **HIGH 11건 전수 해소 후 착수 허용** — HIGH는 API DTO 계약·인증 코드·에러 처리·착수 순서에 직접 영향을 미치므로 코드 작성 전 반드시 정합화해야 한다.
2. **MEDIUM 59건 중 API/연동 관련 우선 처리** — `fds:api-db`, `aml:api-db`, `fds:integration-api`, `aml:integration-api` 대조쌍의 MEDIUM 이격은 DTO 필드 누락·enum 미정의로 코드 생성 자동화 실패 원인이 된다.
3. **cross:naming-tenancy-pii 교차 이격** — FDS·AML 공통 개념(tenant_status, PII 목록, report_status, ingest_mode)의 문서 불일치는 서비스 간 통합 테스트 전 통일이 필요하다.
4. **LOW 49건** — 개발 착수를 block하지 않으나 표기 불통일·버전 포인터 불일치·주석 누락이 코드 리뷰·감사 대응 시 혼란을 유발한다. Sprint 1 시작 전 배치 정합 권고.
5. **PPT 생성기(generate_fds.py, generate_aml.py) 수정** — ppt-flow·ppt-prd 대조쌍 이격은 PPT 재생성 시 반복 발생하므로 생성기 소스를 먼저 수정해야 한다.
6. **미검증 쌍 없음** — 23개 전 대조쌍 검사 완료. 재실행 불필요.
