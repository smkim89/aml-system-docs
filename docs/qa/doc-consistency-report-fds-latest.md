# FDS 문서 정합성 검토 리포트

- **대상 서비스**: fds
- **작성일**: 2026-06-08
- **상태**: COMPLETE

---

## ⓪ 정합화 후 검증 (Post-Reconcile Addendum, 2026-06-08)

원 판정 **FAIL(HIGH 8건)** → 발견 직후 문서별 담당 에이전트로 **전 이격 정합화**. 검증:

- **HIGH 8건 전량 해소 — 실파일 grep + PPT 렌더 검증 완료.** 핵심:
  - #9~12 SW §14.x DDL PK 2열→**3열(tenant_id, workspace_id, natural_key)** + workspace_id·data_scope·created_at 추가(DB §5.x 정본) ✓
  - #13 `/vendor-bridge/decisions`→**`/external-decisions`** / #14 `/admin/fds/approvals/{approvalRequestId}` ✓
  - #17 §12.6a `FdsDecisionConsumer` 삭제(실존 컨슈머 3종으로 교체) ✓ / #4 DB §4.1a Mermaid `ACTIVE_SHARED` 제거 ✓
  - #34 로드맵 P2-FDS-03 의존 `P2-FDS-06` 추가 ✓ / PPT v4.3 DASH 필터 단일축(렌더 확인) ✓
- **MEDIUM 17 · LOW 9건**: 담당 에이전트가 동일 차수 정합(각 문서 변경이력 기록). MED/LOW는 전수 재-grep 미수행 — 에이전트 보고 기준.
- 자동 doc-consistency-qa 재실행은 AML과 동일 사유(인프라 stall)로 미수행 → 표적 정합화+수기 검증 대체.

> **현 상태: HIGH 0건(검증) — 개발 착수 가능.** 아래 ①~③은 정합화 **이전** 원본 스냅샷(이력 보존).

## ① 판정(원본 스냅샷)

| 항목 | 결과 |
|------|------|
| 최종 판정 | **FAIL** → ⓪에서 HIGH 전량 해소 |
| 심각도 높음(high) | **8건** |
| 심각도 중간(medium) | **17건** |
| 심각도 낮음(low) | **9건** |
| 미검증 대조쌍 | **0개** |
| 개발 착수 가능 여부 | **불가 — 높음 이격 전수 수정 후 재검토 필요** |

---

## ② 심각도별 요약

### HIGH (높음) — 8건

높음 등급 이격은 DDL 구조 불일치(PK 열 수·필수 컬럼 누락), API 엔드포인트 경로 오류, 컨슈머 클래스명 불일치 등 구현 착수 즉시 런타임 오류·스키마 마이그레이션 실패·라우팅 장애를 유발하는 항목이다. 전수 수정 전 개발 착수는 금지한다.

- **설계서 §14.3 DDL ↔ DB §5.6~5.8 정본**: `fds_subjects`, `fds_accounts`, `fds_instruments` 세 테이블 PK 열 수 불일치(2열 vs 3열), `workspace_id` 컬럼 누락 (1건)
- **설계서 §14.4 DDL ↔ DB §5.9 정본**: `fds_transactions` PK 열 수 불일치, `workspace_id`·`data_scope` 컬럼 누락 (1건)
- **설계서 §14.3 DDL ↔ DB §5.6 정본**: `fds_subjects` DDL에 `created_at`·`data_scope` 컬럼 누락 (1건)
- **설계서 §14.6 DDL ↔ DB §5.25~5.27 정본**: `fds_business_documents`, `fds_commerce_orders`, `fds_settlements` PK 열 수 불일치, `workspace_id` 누락 (1건)
- **설계서 §12.8 ↔ API §4.10 정본**: External Vendor Bridge API 엔드포인트 경로 오류(`/vendor-bridge/decisions` → `/external-decisions`) (1건)
- **설계서 §12.8 ↔ API §4.9 정본**: Approval API 경로 `/admin/` prefix 및 path 파라미터명(`id` → `approvalRequestId`) 누락 (1건)
- **설계서 §12.6a ↔ Integration 명세 정본**: `FdsDecisionConsumer` 클래스명 미존재 — Integration 명세에 해당 컨슈머 없음 (1건)
- **로드맵 Phase2 파일 ↔ WBS T-10 정본**: P2-FDS-03 의존 칸에서 `P2-FDS-06` 누락 (1건)

### MEDIUM (중간) — 17건

중간 등급 이격은 OpenAPI schema 미정의, DTO 필드 미정의, 상태머신 다이어그램 오류, 엔드포인트 scope 누락, PRD 필드명·경로 변수명 불일치, WBS Due 표기 오류 등 구현 시 스펙 모호성 및 API 계약 위반으로 이어지는 항목이다. 착수 전 수정 권고.

- **DB ↔ API**: `ExternalDecisionMode` enum OpenAPI schema 미정의 (1건)
- **DB ↔ API**: `CredentialDto` GET 응답 필드(credentialType, ipAllowlist 등) API 미정의 (1건)
- **DB ↔ API**: `EvidenceExportRequest` 응답에 `approvalRequestId` 누락 (1건)
- **DB ↔ API**: DB §4.1a `ACTIVE_SHARED` 가상 노드 — enum 8종에 없는 비정규 상태명 (1건)
- **설계서 ↔ API**: Approval API POST approve·reject 엔드포인트 OAuth2 scope 미정의 (1건)
- **API §13 ↔ API §4.9 정본**: downstream 핵심 엔드포인트 목록 approve 경로 메서드(GET→POST)·파라미터명(`id`→`approvalRequestId`) 오류 (1건)
- **Integration 명세 §3.2/§12 ↔ §4.3 정본**: `FdsActionResult.completedAt` 필드 누락 (1건)
- **설계서 §8.3 ↔ Integration §4.1 정본**: `schemaVersion` 필수 필드 표 미열거 (1건)
- **설계서 §8.3 ↔ Integration §4.1 정본**: `correlationId` 필수 필드 표 미열거 (1건)
- **PRD §7.3 ↔ API §5.18~5.19 정본**: SFDS-GRP-003 `groupCode` → `groupId` 미정정 (1건)
- **PRD §7.3 ↔ API §5.18~5.19 정본**: SFDS-GRP-003 `kind` → `groupType` 필드명 불일치 (1건)
- **PRD §12.1 ↔ API §4.9 정본**: SFDS-APPR-001 '필터 파라미터 미정의' 단서 문구 잔존 (1건)
- **PRD §4.2 ↔ API §4.8 정본**: SFDS-CONN-002 path 변수명 `{connectorId}` → `{id}` 불일치 (1건)
- **PRD §4.3·§10.2·§5.2 ↔ API §4.8 정본**: SFDS-CONN-003·ACT-002·MAP-002 path 변수명 `{sourceSystem}` → `{id}` 불일치 (1건)
- **WBS T-12 ↔ 로드맵 §3 정본**: T-12 Due 칸 `P2/P3` → `P2` 단일 표기 오류 (1건)
- **WBS T-18 ↔ 로드맵 §3 정본**: T-18 Due 칸 `P7` 표기 — 로드맵 Phase 미배치 항목에 Phase 번호 기재 모순 (1건)
- **로드맵 §2 ↔ Phase5 파일·PRD 정본**: P5 FDS 화면 수 `32` vs `31` 불일치 (1건)

### LOW (낮음) — 9건

낮음 등급 이격은 감사 필드(createdBy/updatedBy) 누락, 길이 제약 미명시, 이벤트 catalog 항목 누락, 타임존 예시 불일치, 와이어프레임 레이블·샘플 불일치 등 직접적 런타임 장애는 없으나 구현자 오해 및 데이터 일관성 저하 위험이 있는 항목이다.

- **DB §5.13 ↔ API §5.5**: `CaseDto` createdBy/updatedBy 필드 누락 (1건)
- **DB §5.17 ↔ API §5.8**: `RuleDto` 감사 필드 4종(createdAt/updatedAt/createdBy/updatedBy) 누락 (1건)
- **DB §5.13 ↔ API §5.5**: `CaseDto.closeReason` 길이 제약(64) 미명시 (1건)
- **DB §5.19 ↔ API §5.9**: `RuleSimulationResponse` 감사 필드(createdBy/createdAt) 누락 (1건)
- **설계서 §15.6 ↔ Integration §3.1**: `trade.document.submitted` inbound catalog 표 미등재 (1건)
- **설계서 §8.2 ↔ Integration §4.2**: `occurredAt` 타임존 표기 불통일(UTC Z vs KST offset) (1건)
- **PRD §13.1·§13.2 ↔ API §10**: aml-svc cross-ref `ApprovalStatus` 6종 vs 8종 — EXECUTED/EXECUTION_FAILED 제외 근거 미명시 (1건)
- **PPT slide 13 ↔ PRD §6.1**: SFDS-RULE-001 컬럼 헤더 '도메인' vs '도메인/채널' 불일치 (1건)
- **PRD §12.1 와이어프레임 ↔ PPT slide 30**: SFDS-APPR-001 샘플 행 CASE_CLOSE·MERCHANT_NORMALIZE 2종 누락 (1건)

> **cross 서비스 귀속 이격 (별도 집계)**: 아래 표 ③에 포함하였으나 fds 카운트에서는 제외.
> - MEDIUM: `onboarding_status` ACTIVE_SHARED 상태명 (cross:naming-tenancy-pii)
> - LOW: 설계서 §16.1 PII 원문 저장 금지 7종 중 4종만 열거 (cross:naming-tenancy-pii)

---

## ③ 대조쌍별 이격 표

### 3-1. fds:db-api (DB ↔ API 명세)

| # | 심각도 | 서비스 | 항목 | 이격 내용 | 위치 | 권고 |
|---|--------|--------|------|-----------|------|------|
| 1 | MEDIUM | fds | ExternalDecisionRequest.bridgeMode — ExternalDecisionMode enum | DB §4.18 enum 5종 명시, API §10 OpenAPI schema 미정의 → 허용값 확인 불가 | DB §4.18 (01-fds-db.md) vs API §5.14 + §10 OpenAPI (01-fds-api.md) | API §10 schemas에 ExternalDecisionMode enum(5종) 추가 후 bridgeMode $ref 연결. DB §4.18 정본. |
| 2 | MEDIUM | fds | CredentialDto (GET /admin/fds/credentials 조회 응답) | DB fds_api_credentials 8개 컬럼 보유, API §5.13은 생성(1회) 응답만 정의 — 조회 응답 DTO 필드 미명시 | DB §5.29 (01-fds-db.md) vs API §5.13 (01-fds-api.md) | API §5.13에 CredentialDto 조회 응답 필드 표 추가(credentialId/credentialType/scopes/ipAllowlist/webhookUrl/enabled/createdAt/updatedAt). secret 미노출. DB §5.29 정본. |
| 3 | MEDIUM | fds | EvidenceExportRequest 응답 — approvalRequestId 누락 | DB fds_evidence_exports에 approval_request_id(nullable FK) 존재, API §5.11 응답에 approvalRequestId 미포함 | DB §5.31 (01-fds-db.md) vs API §5.11 (01-fds-api.md) | API §5.11 응답에 approvalRequestId(uuid, nullable) 추가. 결재 대상 export이면 반환, 비대상이면 null. DB §5.31 정본. |
| 4 | MEDIUM | fds | DB §4.1a onboarding_status 상태머신 ACTIVE_SHARED 가상 노드 | Mermaid 다이어그램에 ACTIVE_SHARED 사용 — enum 8종 코드값에 없는 비정규 상태명, 본문 텍스트·설계서 §11.6.11a는 ACTIVE로 올바르게 표기 | DB §4.1a (01-fds-db.md) lines 133-152 | Mermaid SHARED 컨테이너 제거 후 최상위 `REQUESTED --> ACTIVE : SHARED 즉시` 전이로 교체. DB §4.1 enum 8종이 정본. |
| 5 | LOW | fds | CaseDto — created_by/updated_by 필드 누락 | DB fds_cases 보유, API §5.5 CaseDto에 createdBy/updatedBy 미정의 | DB §5.13 (01-fds-db.md) vs API §5.5 (01-fds-api.md) | API §5.5 CaseDto에 createdBy/updatedBy(string(128), nullable) 추가. DB §5.13 정본. |
| 6 | LOW | fds | RuleDto — 감사 필드(createdAt/updatedAt/createdBy/updatedBy) 누락 | DB fds_rules 4종 보유, API §5.8 RuleDto 필드 표에 미정의 | DB §5.17 (01-fds-db.md) vs API §5.8 (01-fds-api.md) | API §5.8 RuleDto 응답 필드 표에 4종 추가. DB §5.17 정본. |
| 7 | LOW | fds | CaseDto.closeReason — 길이 제약 미명시 | DB VARCHAR(64), API §5.5 타입 'string'만 기술 — 최대 64 미명시 | DB §5.13 (01-fds-db.md) vs API §5.5 (01-fds-api.md) | API §5.5 closeReason 타입 표기를 string(64)로 정정. DB §5.13 정본. |
| 8 | LOW | fds | RuleSimulationResponse — 감사 필드(createdBy/createdAt) 누락 | DB fds_rule_simulations 2종 보유, API §5.9 응답에 미포함 | DB §5.19 (01-fds-db.md) vs API §5.9 (01-fds-api.md) | API §5.9 RuleSimulationResponse에 createdAt/createdBy 추가. DB §5.19 정본. |

---

### 3-2. fds:design-db (설계서 ↔ DB 명세)

| # | 심각도 | 서비스 | 항목 | 이격 내용 | 위치 | 권고 |
|---|--------|--------|------|-----------|------|------|
| 9 | HIGH | fds | fds_subjects / fds_accounts / fds_instruments PK | 설계서 §14.3 DDL PK 2열(tenant_id, natural_key), DB §5.6~5.8 정본 PK 3열(tenant_id, workspace_id, natural_key) — workspace_id 컬럼 전무 | 설계서 §14.3 DDL lines 1725-1763 vs DB §5.6~5.8 | 설계서 §14.3 세 테이블에 workspace_id VARCHAR(64) NOT NULL DEFAULT 'default' 추가 및 PK 3열 교체. DB §5.6~5.8 정본. |
| 10 | HIGH | fds | fds_transactions PK 및 data_scope 컬럼 | 설계서 §14.4 DDL PK 2열, workspace_id·data_scope 미정의. DB §5.9 정본 PK 3열, data_scope 컬럼 있음 | 설계서 §14.4 DDL lines 1769-1789 vs DB §5.9 | 설계서 §14.4에 workspace_id, data_scope 추가 및 PK 3열 교체. DB §5.9 정본. |
| 11 | HIGH | fds | fds_subjects DDL — created_at 및 data_scope 컬럼 누락 | 설계서 §14.3 DDL created_at 없음. DB §5.6 정본 created_at/updated_at 감사 컬럼 + data_scope 요구. §1 원칙('모든 운영 테이블 created_at/updated_at 강제') 위반 | 설계서 §14.3 DDL lines 1725-1736 vs DB §5.6 | 설계서 §14.3 fds_subjects에 data_scope VARCHAR(128) 및 created_at TIMESTAMPTZ NOT NULL DEFAULT now() 추가. DB §5.6 정본. |
| 12 | HIGH | fds | fds_business_documents / fds_commerce_orders / fds_settlements PK 및 workspace_id 누락 | 설계서 §14.6 DDL PK 2열, workspace_id 전무. DB §5.25~5.27 정본 PK 3열 | 설계서 §14.6 DDL lines 1863-1918 vs DB §5.25~5.27 | 설계서 §14.6 세 테이블에 workspace_id 추가 및 PK 3열 교체. DB §5.25~5.27 정본. |

---

### 3-3. fds:design-api (설계서 ↔ API 명세)

| # | 심각도 | 서비스 | 항목 | 이격 내용 | 위치 | 권고 |
|---|--------|--------|------|-----------|------|------|
| 13 | HIGH | fds | External Vendor Bridge API 엔드포인트 경로 | 설계서 §12.8: `POST /api/v1/fds/vendor-bridge/decisions`. API §4.10 정본: `POST /api/v1/fds/external-decisions` | 설계서 §12.8 API group 표 vs API §4.10 | 설계서 §12.8 행을 `POST /api/v1/fds/external-decisions`로 교체 및 API §4.10 참조 명시. API §4 정본. |
| 14 | HIGH | fds | Approval API 엔드포인트 경로 prefix | 설계서 §12.8: `/admin/` 없음, path 파라미터 `{id}`. API §4.9 정본: `/admin/fds/approvals`, 파라미터명 `{approvalRequestId}` | 설계서 §12.8 API group 표 vs API §4.9 | 설계서 §12.8 행을 `GET /api/v1/admin/fds/approvals`, `POST .../approvals/{approvalRequestId}/approve`로 정정. API §4.9 정본. |
| 15 | MEDIUM | fds | Approval API POST approve·reject 엔드포인트 OAuth2 scope 미정의 | API §4.9 표 scope 열 없음, §10 OpenAPI POST 2종에 security 미정의. GET은 `fds:case:read` 선언. 설계서 §12.8은 `fds:action:write` 기재 | API §4.9·§10 OpenAPI (01-fds-api.md) vs 설계서 §12.8 | API §4.9에 scope 열 추가, §10 OpenAPI POST approve/reject에 security 블록 명시. 설계서 §12.8과 정합 후 §4.9 정본 확정. |
| 16 | MEDIUM | fds | API §13 downstream 핵심 엔드포인트 approve 경로·메서드 오류 | §13 목록: `GET /admin/fds/approvals/{id}/approve`. 정본 §4.9: `POST /admin/fds/approvals/{approvalRequestId}/approve` — 메서드(GET→POST), 파라미터명(`id`→`approvalRequestId`) 모두 오류 | API §13 핵심 엔드포인트 목록 (01-fds-api.md) | §13 목록을 `POST /admin/fds/approvals/{approvalRequestId}/approve`로 정정. API §4.9 정본. |

---

### 3-4. fds:design-integration (설계서 ↔ Integration 명세)

| # | 심각도 | 서비스 | 항목 | 이격 내용 | 위치 | 권고 |
|---|--------|--------|------|-----------|------|------|
| 17 | HIGH | fds | FdsDecisionConsumer — 설계서 §12.6a 컨슈머 명칭 | 설계서 §12.6a: `FdsDecisionConsumer` 존재. Integration 명세 전문에 해당 클래스 없음. 실제 컨슈머: FdsEventsConsumer, SqsFdsActionPublisher, FdsExternalDecisionConsumer | 설계서 §12.6a 표 vs Integration §2·§3.2 (01-fds-integration.md) | 설계서 §12.6a에서 `FdsDecisionConsumer` 행 삭제 또는 실존 클래스명으로 교체. Decision 결과는 Decision Engine이 fds-webhook 큐에 FdsDecisionCreated 발행(§3.2 참조). Integration 정본. |
| 18 | MEDIUM | fds | schemaVersion — 설계서 §8.3 필수 필드 표 누락 | 설계서 §8.3 필수 필드 표: schemaVersion 없음. Integration §4.1 정본: schemaVersion ● 필수(이벤트). 설계서 §8.2 JSON 예시에는 포함 — 내부 불일치 | 설계서 §8.3 (01-fdsSvc-sass.md) vs Integration §4.1 (01-fds-integration.md) | 설계서 §8.3 필수 필드 표에 schemaVersion 추가(조건부 필수: 이벤트 메시지 필수). Integration §4.1 정본. |
| 19 | MEDIUM | fds | correlationId — 설계서 §8.3 필수 필드 표 누락 | 설계서 §8.3 표: correlationId 없음. Integration §4.1 정본: correlationId ● 필수. 설계서 §8.2 JSON 예시에도 미포함 | 설계서 §8.3 (01-fdsSvc-sass.md) vs Integration §4.1 (01-fds-integration.md) | 설계서 §8.3 표에 correlationId 추가(필수, SQS message attribute, traceability). §8.2 예시에도 추가하여 일치. Integration §4.1 정본. |
| 20 | LOW | fds | trade.document.submitted — §3.1 inbound catalog 표 미등재 | 설계서 §15.6 필수 이벤트. Integration §3.1 trade-finance 행: invoice.issued/document.matched만 있음 — document.submitted 누락. normalization 주석에는 언급 있어 내부 불일치 | 설계서 §15.6 (01-fdsSvc-sass.md) vs Integration §3.1 (01-fds-integration.md) | Integration §3.1 trade-finance 행 eventType 열에 trade.document.submitted 추가. 설계서 §15.6 정본. |
| 21 | LOW | fds | occurredAt 타임존 표기 — 예시 불통일 | 설계서 §8.2 JSON 예시: UTC Z suffix. Integration §4.2 JSON 예시: KST +09:00 offset — 구현자 처리 방식 혼동 위험 | 설계서 §8.2 line 510 vs Integration §4.2 line 181 | 설계서 §8.2 예시를 +09:00으로 통일. §8.3 비고에 'ISO-8601 TZ 필수(UTC Z 또는 offset 모두 허용, 내부 저장 UTC)' 정책 명시. Integration §4.2 기준. |

---

### 3-5. fds:dbapi-integration (DB·API ↔ Integration 명세)

| # | 심각도 | 서비스 | 항목 | 이격 내용 | 위치 | 권고 |
|---|--------|--------|------|-----------|------|------|
| 22 | MEDIUM | fds | FdsActionResult.completedAt | Integration §4.3: completedAt 필드 포함·DB 매핑 명시. §3.2 카탈로그 행·§12 downstream 필드 목록(actionId/actionType/status/errorCode)에 completedAt 누락 | Integration §3.2/§12 vs §4.3 (01-fds-integration.md) | §3.2 카탈로그 및 §12 FdsActionResult 목록에 completedAt(nullable) 추가. camelCase 매핑 `completedAt`↔`completed_at` 병기. Integration §4.3 정본. |

---

### 3-6. fds:api-prd (API 명세 ↔ PRD)

| # | 심각도 | 서비스 | 항목 | 이격 내용 | 위치 | 권고 |
|---|--------|--------|------|-----------|------|------|
| 23 | MEDIUM | fds | SFDS-GRP-003 groupCode 필드명 | PRD §7.3 데이터 항목·BR-001: `groupCode`. API §5.19 RiskGroupDto 정본: `groupId`. PRD v2.9 변경이력에 정정됐으나 §7.3만 미정정 | PRD §7.3 (01-fds-sass-functional-spec.md) vs API §5.18·§5.19 | PRD §7.3 `groupCode` → `groupId`, BR-001 '중복 그룹 코드' → '중복 그룹 ID' 일괄 수정. API §5.19 정본. |
| 24 | MEDIUM | fds | SFDS-GRP-003 kind 필드명 | PRD §7.3: `kind`(표시 분류). API §5.18·§5.19 정본: `groupType` | PRD §7.3 (01-fds-sass-functional-spec.md) vs API §5.18·§5.19·§10 OpenAPI | PRD §7.3 `kind` → `groupType`으로 수정. 화면 레이블('종류') 유지. API §5.18·§5.19 정본. |
| 25 | MEDIUM | fds | SFDS-APPR-001 필터 파라미터 '미정의' 단서 문구 잔존 | PRD §12.1 API 셀에 구버전 '미정의' 단서 잔존. API v1.7 §4.9·§10 OpenAPI에서 subjectKind/status/maker 3종 공식 정의 완료 | PRD §12.1 (01-fds-sass-functional-spec.md) vs API §4.9·§10 OpenAPI | PRD §12.1 괄호 단서 문구 삭제 후 API v1.7 §4.9 공식 정의 참조 표기로 교체. API v1.7 §4.9 정본. |
| 26 | MEDIUM | fds | SFDS-CONN-002 path 변수명 {connectorId} vs {id} | PRD §4.2: `{connectorId}`. API §4.8·§10 OpenAPI 정본: `{id}` | PRD §4.2 (01-fds-sass-functional-spec.md) vs API §4.8·§5.15·§10 OpenAPI | PRD §4.2 `{connectorId}` → `{id}` 수정. §16.1 매핑 표도 동일 수정. API §4.8·§10 정본. |
| 27 | MEDIUM | fds | SFDS-CONN-003·ACT-002·MAP-002 path 변수명 {sourceSystem} vs {id} | PRD §4.3·§10.2·§5.2: `{sourceSystem}`. API §4.8·§10 정본: `{id}` | PRD §4.3·§5.2·§10.2 (01-fds-sass-functional-spec.md) vs API §4.8·§5.17·§10 OpenAPI | PRD 세 섹션 `{sourceSystem}` → `{id}` 수정. 주석 '({id} = source_system)' 병기. API §4.8·§10 정본. |
| 28 | LOW | fds | SFDS-REG-001/002 aml-svc cross-ref ApprovalStatus 6종 vs 8종 | PRD §13.1·§13.2: 6종 열거(DRAFT~EXPIRED). API §10 정본: 8종(EXECUTED/EXECUTION_FAILED 포함). 제외 근거 미명시 | PRD §13.1·§13.2 (01-fds-sass-functional-spec.md) vs API §10 ApprovalStatus enum | PRD §13.1·§13.2에 'EXECUTED/EXECUTION_FAILED는 aml-svc 내부 전이, FDS cross-ref 표시 외' 명시 또는 aml-svc PRD 위임 근거 추가. |

---

### 3-7. fds:prd-ppt (PRD ↔ PPT 와이어프레임)

| # | 심각도 | 서비스 | 항목 | 이격 내용 | 위치 | 권고 |
|---|--------|--------|------|-----------|------|------|
| 29 | MEDIUM | fds | SFDS-DASH-001 필터 축 (고객사/서비스 필터) | PRD §2.1 BR-001: 기간 단일축. PPT slide 3: 기간·고객사·서비스 3축 노출. v4.2 도메인 필터 제거 이후에도 고객사·서비스 필터 잔존 | PRD §2.1 BR-001 vs PPT slide 3 (SFDS-DASH-001) | PPT slide 3에서 '고객사 전체 ▼'·'서비스 전체 ▼' 제거, 또는 PRD §2.1 BR-001에 명시적 BR 추가. PRD §2.1 정본. |
| 30 | LOW | fds | SFDS-RULE-001 컬럼명 '도메인/채널' vs '도메인' | PRD §6.1: 컬럼명 '도메인/채널'. PPT slide 13 헤더: '도메인'만 표시 | PRD §6.1 데이터 항목 vs PPT slide 13 (SFDS-RULE-001) | PPT slide 13 헤더를 '도메인' → '도메인/채널'로 수정. PRD §6.1 정본. |
| 31 | LOW | fds | SFDS-APPR-001 PRD 와이어프레임 샘플 행 수 (6종 vs 8종) | PRD §12.1 와이어프레임: 6행(CASE_CLOSE·MERCHANT_NORMALIZE 누락). PPT slide 30: 8행 전수. PRD §16.5 결재 대상 표는 8종 | PRD §12.1 화면 레이아웃 vs PPT slide 30 (SFDS-APPR-001) | PRD §12.1 와이어프레임에 CASE_CLOSE·MERCHANT_NORMALIZE 샘플 행 추가. §16.5 8종이 정본. |

---

### 3-8. fds:design-wbs (설계서 ↔ WBS)

| # | 심각도 | 서비스 | 항목 | 이격 내용 | 위치 | 권고 |
|---|--------|--------|------|-----------|------|------|
| 32 | MEDIUM | fds | fds-svc 구현 패키지 루트 명칭 | WBS L5·L11: `com.hanpass.fds` 단독 표기. 설계서 §6.2·target-architecture §5 정본: 구현 패키지 루트 `com.aegis.fds`(설계 표기 `com.hanpass.fds`와 별도) | WBS docs/tasks/fds/00-overview.md L5·L11 vs 설계서 §6.2·target-architecture §5 | WBS L5·L11을 '설계 표기 `com.hanpass.fds` — 구현 패키지 루트 `com.aegis.fds`(target-architecture §5)'로 정정. 설계서 §6.2 정본. |
| 33 | LOW | fds | T-18 스코프 vs §18 Phase 7 Advanced domain pack 전체 범위 | WBS T-18: Commerce/Trade evidence·도메인 확장팩만 기술. 설계서 §18 Phase 7: cross-border remittance·crypto 등 9개 도메인 전체. WBS에 나머지 도메인 보류 상태 미명시 | WBS T-18(L43)·§4(L110) vs 설계서 §18 Phase 7 | T-18 비고에 '§18 Phase 7 Advanced domain pack 전체(T-18 외 포함) 보류 — 정책 확정 후 별도 WBS' 명시. |

---

### 3-9. fds:wbs-roadmap (WBS ↔ 로드맵)

| # | 심각도 | 서비스 | 항목 | 이격 내용 | 위치 | 권고 |
|---|--------|--------|------|-----------|------|------|
| 34 | HIGH | fds | P2-FDS-03(T-10) 태스크 표 의존 칸 — P2-FDS-06(T-15) 누락 | 로드맵 P2-FDS-03 의존: `P1-FDS-04,P2-FDS-04`. WBS T-10 의존: `T-05,T-15`. §6 의존 그래프에 `P2-FDS-06 --> P2-FDS-03` 엣지 존재. 태스크 표·의존 그래프 불일치 | 로드맵 docs/tasks/aegis-aml/03-phase2-engines-mvp.md §2 P2-FDS-03 의존 칸 | §2 P2-FDS-03 의존 칸을 `P1-FDS-04,P2-FDS-04,P2-FDS-06`으로 수정. WBS T-10·Phase2 의존 그래프 정본. |
| 35 | MEDIUM | fds | T-12 Due(Phase) 표기 — P2/P3 vs P2 단일 | WBS T-12 Due: `P2/P3`. 로드맵 §3·Phase2 파일: T-12=P2 단일. P3 귀속 근거 없음 | WBS docs/tasks/fds/00-overview.md §2 T-12 행 vs 로드맵 §3·Phase2 파일 | WBS T-12 Due 칸을 `P2/P3` → `P2`로 수정. 로드맵 §3·Phase2 파일 정본. |
| 36 | MEDIUM | fds | T-18 Due(Phase) 칸 값 P7 vs 로드맵 §3 Phase 미배치 | WBS T-18 Due: `P7(보류·정책 확정 후 별도 WBS)`. 로드맵 §3 P7 fds 칸: T-20·T-21(T-18 미등재). WBS §4 주석: 'T-18 로드맵 Phase 미배치' — Due 칸 P7 표기와 자기모순 | WBS docs/tasks/fds/00-overview.md §2 T-18 행 vs 로드맵 §3·Phase7 파일 | T-18 Due 칸을 `P7(보류·정책 확정 후 별도 WBS)` → `—(보류: 정책 확정 후 별도 WBS, 로드맵 Phase 미배치)`로 수정. 로드맵 §3 정본. |
| 37 | MEDIUM | fds | 로드맵 §2 P5 FDS 화면 수 FDS 32 vs FDS 31 | 로드맵 §2 P5 행: `FDS 32 + AML 20화면`. Phase5 파일·PRD 인용 전체: `FDS 31화면` 일관 선언 | 로드맵 docs/tasks/aegis-aml/00-program-overview.md §2 P5 행 vs Phase5 파일·PRD 정본 | 로드맵 §2 P5 행을 `FDS 32` → `FDS 31`로 수정. Phase5 파일·PRD 정본. |

---

### 3-10. fds:roadmap-design (로드맵 ↔ 설계서)

| # | 심각도 | 서비스 | 항목 | 이격 내용 | 위치 | 권고 |
|---|--------|--------|------|-----------|------|------|
| 38 | MEDIUM | fds | 설계서 §18 Phase 5 노트의 태스크 ID 참조 — T-11/T-16 vs P5-FDS-04/07/08 | 설계서 §18 Phase 5 주석: 'T-11/T-16 BO UI'. T-11(Due=P2)·T-16(Due=P4)는 fds-svc WBS ID. P5 로드맵 태스크 ID는 P5-FDS-04(T-11 BO UI)·P5-FDS-07/08(T-16 BO UI). WBS T-ID와 로드맵 Phase 태스크 ID 혼용으로 오해 유발 | 설계서 §18 Phase 5 주석 (01-fdsSvc-sass.md) vs 로드맵 §3·Phase5 파일 | 설계서 §18 Phase 5 주석을 '로드맵 Phase 태스크 P5-FDS-04(T-11 BO UI)·P5-FDS-07/08(T-16 BO UI)'로 교체. 엔진 T-11/T-16은 P2/P4 완성, P5는 bo-web UI만 구현 구분. |
| 39 | LOW | fds | P7 Phase 파일 헤더의 §21 소속 문서 미명시 — FDS §12.6 누락 | Phase7 파일 헤더 입력 인용: 'docs/software §21(legacy vendor bridge)' — §21은 02-amlSvc-sass.md 전용 섹션. FDS 측 Vendor Bridge 설계(01-fdsSvc-sass.md §12.6/§12.6a) 미인용. P7-FDS-02 구현 시 설계 근거 미참조 위험 | Phase7 파일 헤더 (08-phase7-ops-hardening.md) vs 설계서 §12.6/§12.6a | Phase7 파일 헤더 입력 인용에 '01-fdsSvc-sass.md §12.6(legacy vendor bridge)' 추가. AML §21과 FDS §12.6 서비스별 경로 명시. |

---

### 3-11. cross:naming-tenancy-pii (Cross 서비스 공통 — 이름·테넌시·PII)

| # | 심각도 | 서비스 | 항목 | 이격 내용 | 위치 | 권고 |
|---|--------|--------|------|-----------|------|------|
| 40 | MEDIUM | cross | onboarding_status ACTIVE_SHARED 상태명 | DB §4.1a Mermaid: `REQUESTED --> ACTIVE_SHARED : 즉시`. enum 8종 코드값에 없음. §4.1a 본문 텍스트·설계서 §11.6.11a: `ACTIVE`로 올바르게 표기 | DB §4.1a Mermaid line 148 (01-fds-db.md) | Mermaid `REQUESTED --> ACTIVE_SHARED : 즉시` → `REQUESTED --> ACTIVE : 즉시(SHARED)`로 수정. enum 코드값 정본 기준. |
| 41 | LOW | cross | PII 원문 저장 금지 대상 목록 — 설계서 §16.1 범위 4종 vs DB §7.1 정본 7종 | 설계서 §16.1 첫 번째 불릿: 4종(계좌번호·카드PAN·주민등록번호·여권번호). DB §7.1 정본: 7종(위 4종 + 휴대폰번호·CI/DI·가상자산 주소). 단서 주석 있으나 동일 문장 외부에 위치 | 설계서 §16.1 lines 2252-2257 (01-fdsSvc-sass.md) vs DB §7.1 | 설계서 §16.1 첫 번째 불릿을 7종 전체로 확장하여 DB §7.1 정본과 동일하게 한 문장에 열거. |

---

## ④ 개발 착수 권고

### 착수 금지 조건 (HIGH 이격 전수 해소 필수)

아래 8건의 HIGH 이격은 개발 착수 전 **반드시** 수정해야 한다. 미수정 상태에서 착수할 경우 DDL 스키마 마이그레이션 실패, API 라우팅 장애, 컨슈머 클래스 참조 오류, 태스크 의존 누락으로 인한 빌드 블록킹이 발생한다.

| 우선순위 | 항목 번호 | 수정 대상 문서 | 수정 내용 요약 |
|---------|-----------|--------------|--------------|
| P0 | #9, #10, #11, #12 | 설계서 §14.3·§14.4·§14.6 DDL | workspace_id 컬럼 추가, PK 3열 교체, created_at/data_scope 추가 |
| P0 | #13, #14 | 설계서 §12.8 API group 표 | Vendor Bridge·Approval API 경로 정정 |
| P0 | #17 | 설계서 §12.6a | FdsDecisionConsumer 행 삭제·교체 |
| P0 | #34 | 로드맵 Phase2 §2 P2-FDS-03 행 | 의존 칸에 P2-FDS-06 추가 |

### 착수 전 권고 수정 (MEDIUM 이격)

HIGH 수정 완료 후 착수 전에 MEDIUM 17건을 일괄 처리한다. 특히 아래 항목은 스펙 모호성이 크다:

- **#15, #16**: Approval API scope 미정의·경로 오류 → Auth 구현 기준 불명확
- **#18, #19**: schemaVersion·correlationId 필수 필드 누락 → 메시지 스키마 계약 위반
- **#22**: FdsActionResult.completedAt 누락 → Integration 계약 불일치
- **#23~#27**: PRD 필드명·경로 변수명 오류 → 프론트엔드·API 연결 오류

### 착수 후 조기 수정 권고 (LOW 이격)

LOW 9건은 감사 필드·레이블·예시 불일치로 런타임 장애 위험은 낮으나 데이터 일관성 및 구현자 혼동 방지를 위해 스프린트 1 내 수정을 권고한다.

### 미검증 대조쌍

미검증 대조쌍: **0개** — 모든 대조쌍이 검토 완료되었다. 재실행 불필요.

---

*리포트 생성 기준: docs/qa/doc-consistency-report-fds-latest.md | 서비스: fds | 판정: FAIL | 작성: 2026-06-08*
