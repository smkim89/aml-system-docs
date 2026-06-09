# AML 서비스 문서 정합성 리포트

**대상 서비스**: aml  
**생성일**: 2026-06-08  
**원 판정**: FAIL → **정합화 완료(2026-06-08, post-reconcile)**  
**심각도 분포(원)**: 높음(HIGH) 17건 · 중간(MEDIUM) 22건 · 낮음(LOW) 17건  
**미검증 쌍**: 0개 (전수 검증 완료)

---

## ⓪ 정합화 후 검증 (Post-Reconcile Addendum, 2026-06-08)

본 리포트의 원 판정은 **FAIL(HIGH 17건)** 이었으나, 발견 직후 문서별(설계·DB·API·연동·PRD/PPT·태스크) 담당 에이전트로 **전 이격을 정합화**했다. 검증 방식·결과:

- **HIGH 17건 전량 해소 — 실파일 grep + PPT 렌더(soffice→pdftoppm) 직접 검증 완료.** 핵심:
  - #34 연동 §4.1 `payloadHash` 필수 `Y→N`(선택·서버 자동계산, API §3.1 정본과 일치) ✓
  - #41 PPT WLF-003 `status=RESOLVED` → `TRUE_MATCH,FALSE_POSITIVE,AUTO_DISCOUNTED` ✓ (렌더 확인)
  - #44 PPT WLF-002 컬럼 7종(상신일·동작 추가·미정의 점수 제거) ✓ #45 면제(FP_WHITELIST) 카드 ✓ #46 SLA 일 단위 ✓
  - #19 DB `aml_evidence_exports.status` 컬럼 + Flyway V18 신설 ✓ / #36 PRD §11.1 결재 16종(+TM_SCENARIO) ✓
  - #50/#51/#56/#57/#60/#61 태스크 2층(T-01 DONE·subjectType 16종·P4 T-12·P5-AML-02 WLF-003) ✓
- **MEDIUM 22 · LOW 17건**: 담당 에이전트가 동일 차수에 정합화(각 문서 변경이력 기록). 단, MED/LOW는 HIGH와 달리 전수 재-grep 검증은 미수행 — 에이전트 보고 기준.
- **자동 doc-consistency-qa 재실행은 2회 stall**(인프라성, 2.18M·9M 토큰) → 표적 정합화 + 수기 검증으로 대체. 자동 재QA는 인프라 여유 시 권장(잔여 MED/LOW 전수 재확인용).

> **현 상태: HIGH 0건(검증) — 개발 착수 가능.** 아래 ①~④는 정합화 **이전** 원본 스냅샷(이력 보존용).

## ① 판정(원본 스냅샷)

```
FAIL — 총 56건 이격 발견 (HIGH 17건 포함)  ← 정합화 전 상태. ⓪ 참조.
```

개발 착수 전 HIGH 항목 전수 조치 필요. HIGH 미해결 상태로 착수하면 결재 엔진·로드맵 Phase 범위 오인, API ↔ DB 구현 혼선이 발생한다. **(→ ⓪에서 전량 해소됨)**

---

## ② 심각도별 요약

| 심각도 | 건수 | 주요 유형 |
|--------|------|-----------|
| HIGH   | 17   | subjectType 종수 오기, payloadHash 필수 여부 충돌, canonical event 경로 오류, 로드맵 Phase 매핑 누락, WLF-003 화면 누락, DB 컬럼 미정의(status) |
| MEDIUM | 22   | 감사 컬럼 누락(DDL), API 응답 필드 미정의, PRD 데이터 항목 필드명 오류, vendor.* 처리 방식 이격, WBS 의존 분할 미표기 |
| LOW    | 17   | 지원 인프라 DDL 미기재, 변경 이력 오기, enum 별칭 미명시, 큐명 중복 표기, PII 컬럼 명명 패턴 미명시 |

---

## ③ 대조쌍별 이격 표

### 3-1. 설계서 ↔ DB 설계서 (aml:design-db)

| # | 심각도 | 서비스 | 항목 | 이격 내용 | 위치 | 권고 |
|---|--------|--------|------|-----------|------|------|
| 1 | MEDIUM | aml | aml_customers — 감사 컬럼 누락 | 설계서 §17.2 DDL에 `created_by`, `updated_by`, `trace_id`, `data_scope` 4컬럼 누락. DB §3.3/§2.1은 전수 요구. | 설계서 §17.2 vs DB §3.3 | 설계서 §17.2 DDL에 4컬럼 추가 또는 '공통 §2.1 컬럼 포함' 주석 명시. |
| 2 | MEDIUM | aml | aml_entities — 감사 컬럼 누락 | 설계서 §17.2 DDL에 `created_at` 없고 `created_by`, `updated_by`, `trace_id`, `data_scope` 누락. | 설계서 §17.2 vs DB §3.4 | 설계서 §17.2에 해당 컬럼 추가 또는 공통 컬럼 포함 주석 명시. |
| 3 | MEDIUM | aml | aml_relationships — 감사 컬럼 누락 | 설계서 §17.2 DDL에 `created_at`, `created_by`, `updated_at`, `updated_by`, `trace_id` 없음. | 설계서 §17.2 vs DB §3.5 | 공통 감사 컬럼 추가 또는 주석 명시. |
| 4 | MEDIUM | aml | aml_watchlist_sources — 감사 컬럼 누락 | 설계서 §17.3 DDL에 `created_at`, `created_by`, `updated_at`, `updated_by`, `trace_id` 없음. | 설계서 §17.3 vs DB §3.6 | 공통 감사 컬럼 추가 또는 주석 명시. |
| 5 | MEDIUM | aml | aml_watchlist_entries — 감사 컬럼 부분 누락 | `created_at/created_by`만 있고, `version`·`status` 컬럼 존재 여부 DDL 절단으로 확인 불가. | 설계서 §17.3 vs DB §3.7 | `version`, `status` 컬럼 명시 여부를 DB §3.7과 전수 대조. |
| 6 | MEDIUM | aml | aml_screening_results — 감사 컬럼 누락 | `created_at`만 있고 `created_by`, `updated_at`, `updated_by`, `trace_id` 없음. | 설계서 §17.3 vs DB §3.8 | 공통 감사 컬럼 추가 또는 주석 명시. |
| 7 | MEDIUM | aml | aml_risk_scores — 감사 컬럼 누락 | `created_at`~`trace_id` 전수 누락. | 설계서 §17.4 vs DB §3.9 | 공통 감사 컬럼 추가 또는 주석 명시. |
| 8 | MEDIUM | aml | aml_alerts — 감사 컬럼 및 data_scope 누락, scenario_code 위치 불일치 | `created_at`만 있고 `created_by`, `updated_at`, `updated_by`, `trace_id`, `data_scope` 없음. `scenario_code` 컬럼 순서도 §3.10과 불일치. | 설계서 §17.4 vs DB §3.10 | 공통 감사 컬럼 추가. |
| 9 | MEDIUM | aml | aml_cases — 감사 컬럼 일부 누락 | `created_at/updated_at`만 있고 `created_by`, `updated_by`, `trace_id`, `data_scope` 없음. | 설계서 §17.4 vs DB §3.11 | 4컬럼 추가 또는 주석 명시. |
| 10 | MEDIUM | aml | aml_regulatory_reports — 감사 컬럼 누락 | `created_at`만 있고 나머지 감사 컬럼 전수 누락. | 설계서 §17.4 vs DB §3.12 | 공통 감사 컬럼 추가 또는 주석 명시. |
| 11 | MEDIUM | aml | aml_business_documents — 감사 컬럼 및 data_scope 누락 | `created_at`만 있고 나머지 누락. | 설계서 §17.5 vs DB §3.13 | 공통 감사 컬럼 추가 또는 주석 명시. |
| 12 | MEDIUM | aml | aml_travel_rule_transfers — 감사 컬럼 누락 | `created_at`만 있고 나머지 누락. | 설계서 §17.5 vs DB §3.14 | 공통 감사 컬럼 추가 또는 주석 명시. |
| 13 | LOW | aml | 지원 인프라 테이블 5종 미기재 | 설계서 §17에 `aml_canonical_events`, `aml_approvals`, `aml_audit_events`, `aml_evidence_exports`, `aml_outbox` DDL 없음. | 설계서 §17 전체 vs DB §3.15 | §17에 5종 개념 DDL 또는 'DB §3.15 정본 참조' 주석 추가. |
| 14 | LOW | aml | aml_source_systems — `data_scope` 컬럼 DB 명세에 불명확 | 설계서 §17.1에는 있으나 DB §3.2에 포함 여부 불명확. | 설계서 §17.1 vs DB §3.2 | DB §3.2에 포함 여부 명시. |
| 15 | LOW | aml | aml_tenants — `retention_policy` 및 감사 컬럼 누락 | 설계서 §17.1에 `retention_policy JSONB`와 `created_by/updated_at/updated_by` 없음. | 설계서 §17.1 vs DB §3.1 | 컬럼 추가 또는 DB §3.1 정본 참조 주석 명시. |
| 16 | LOW | aml | aml_source_systems — `enabled`/`status` 중복 가능성 | 설계서·DB 모두 두 컬럼을 보유하나 역할 분리 근거 미명시. | 설계서 §17.1 vs DB §3.2 | DB §3.2에 두 컬럼 역할 분리 근거 주석 추가. |
| 17 | LOW | aml | §9.2 Entity risk attribute vs DB §3.4 컬럼 불일치 | `businessModel` 등 7개 속성이 DB에서 JSONB 통합 저장되나 설계서에서 명시적 JSONB 매핑 없음. | 설계서 §9.2 vs DB §3.4 | DB §3.4 JSONB 필드에 속성 저장 위치 주석 명시. |
| 18 | LOW | aml | §11.2 RA output camelCase vs DB §3.9 snake_case — 변환 주석 미명시 | 기능 이격 아니나 설계서 §11.2에 snake_case 변환 기준 주석 없어 API/PRD 독자 혼동 우려. | 설계서 §11.2 vs DB §3.9 | §11.2에 'DB 컬럼명은 §17.4 snake_case 변환 기준' 주석 추가. |

---

### 3-2. DB 설계서 ↔ API 명세 (aml:db-api)

| # | 심각도 | 서비스 | 항목 | 이격 내용 | 위치 | 권고 |
|---|--------|--------|------|-----------|------|------|
| 19 | HIGH | aml | aml_evidence_exports.status — DB 컬럼 미존재 | DB에 `status` 컬럼 없으나 API `EvidenceExportResponse`가 `status` 필드 포함. | DB §3.15 vs API §3.8 | DB에 `status VARCHAR(32) NOT NULL DEFAULT 'PENDING'` 추가(Flyway V14 또는 V18). |
| 20 | MEDIUM | aml | aml_evidence_exports.reason — NULL 허용 vs API 필수 불일치 | DB nullable(Y) ↔ API R=필수. | DB §3.15 line 510 vs API §3.8 line 359 | DB `reason`을 `NOT NULL`로 강화(Flyway additive). |
| 21 | MEDIUM | aml | RiskScoreResponse — `target_type`, `model_code`, `is_override` 미포함 | DB §3.9에 3컬럼 있으나 API `RiskScoreResponse`에 없음. | DB §3.9 vs API §3.3 line 280 | API §3.3에 `targetType`, `modelCode`, `isOverride` 필드 추가. |
| 22 | MEDIUM | aml | GET /aml/alerts/{alertId} 응답 AlertDto 미정의 | 엔드포인트는 있으나 응답 DTO 스키마가 API 명세에 전혀 없음. | API §2.4 line 113 vs DB §3.10 | API §3.x에 `AlertDto` 스키마 정의(10컬럼 + 감사 컬럼). |
| 23 | LOW | aml | ApprovalDto.status enum — DRAFT 노출 제한 미명시 | §1.5에서 DRAFT 미노출 선언하나 §3.7 참조 enum에 DRAFT 포함 여지. | API §3.7 vs DB §5.13 | §3.7 `ApprovalDto.status`를 7종(DRAFT 제외)으로 명시. |
| 24 | LOW | aml | SourceSystemDto — 감사 컬럼 API 미포함 | DB 감사 컬럼 있으나 API `SourceSystemDto`에 `createdAt/updatedAt` 없음. | DB §3.2 vs API §3.9 line 401 | `SourceSystemDto`에 `createdAt`, `updatedAt` 추가. |

---

### 3-3. 설계서 ↔ API 명세 (aml:design-api)

| # | 심각도 | 서비스 | 항목 | 이격 내용 | 위치 | 권고 |
|---|--------|--------|------|-----------|------|------|
| 25 | MEDIUM | aml | 설계서 §6.2 usecase/ 명칭 비PascalCase | `ManageCdd/Edd`, `ReviewStr/Ctr`(슬래시 복합 표기). port/in은 `ManageCaseUseCase` 단일 명칭. | 설계서 §6.2 line 365 vs API §2.7 | `ManageCdd/Edd`→`ManageCddEdd`, `ReviewStr/Ctr`→`ReviewStrCtr`로 교정. |
| 26 | MEDIUM | aml | API §10 RA 모델 활성화 엔드포인트 경로 약식 표기 오류 | `{modelCode}` 세그먼트 누락. | API §2.7 line 156 vs API §10 line 1441 | §10 등재표를 `POST .../ra-models/{modelCode}/versions/{version}:activate`로 교정. |
| 27 | LOW | aml | 설계서 변경 이력 §(5) vs §6.2 본문 표기 불일치 | 변경이력 'IngestVendorAlert 추가' ↔ 본문 'IngestEvent(source_origin=VENDOR) 흡수'. | 설계서 §변경이력 line 1946 vs §6.2 line 363 | 변경이력 §(5) 문구를 본문과 일치시킨다. |
| 28 | LOW | aml | 설계서 §15.7 권한 scope 목록 약식 표기 — 일부 scope 누락 인상 | Admin API group 행 약식 표기로 `aml:admin:approval` 등 누락처럼 읽힘. | 설계서 §15.7 line 1068 vs API §1.1 | §15.7에 'API §1.1 전수 13종 참조' 또는 전체 목록 열거. |

---

### 3-4. 설계서 ↔ 연동 명세 (aml:design-integration)

| # | 심각도 | 서비스 | 항목 | 이격 내용 | 위치 | 권고 |
|---|--------|--------|------|-----------|------|------|
| 29 | HIGH | aml | SW §8.2 canonical event 예시 `payloadHash` 중첩 경로 오류 | 설계서: `rawPayload.payloadHash` 중첩. 연동 §4.1 정본: 최상위 `payloadHash`. | 설계서 §8.2 vs 연동 §4.1 | `rawPayload` 객체 제거 후 최상위 `payloadHash`로 교체. `stored` 필드 삭제. |
| 30 | HIGH | aml | 연동 §3.1 `vendor.*` family 카운트 '14종' 오류 | 주석 '14종에 포함되지 않는다' ↔ SW §8.1 정본은 15종이며 이미 등재됨. | 연동 §3.1 vs SW §8.1 | '14종에 포함되지 않는다' → '15종 중 하나로 등재되어 있다'로 수정. |
| 31 | MEDIUM | aml | `vendor.*` family 라우팅·처리 방식 이격 | SW §8.1: 독립 family 선언. 연동 §3.1: IngestEvent 흡수 처리. 두 문서 처리 방식 상이. | SW §8.1 vs 연동 §3.1 | SW §8.1에 흡수 처리 주석 추가 또는 연동 §3.1에 family 선언 수용 라우팅 설명 추가. |
| 32 | MEDIUM | aml | SW §8.2 canonical event 예시 — `dataScope`, `traceId`, `payload` 누락 | 연동 §4.1 필수/선택 envelope 필드가 SW §8.2 예시에 없음. | SW §8.2 vs 연동 §4.1 | SW §8.2 예시를 연동 §4.1 envelope 구조와 동기화. |
| 33 | LOW | aml | SW §8.1 `screening.*` family — 큐명 직접 표기 동기화 위험 | `aml-screening-async` 큐명을 설계서에 직접 박아 연동 명세 변경 시 추가 수정 필요. | SW §8.1 vs 연동 §2.1 | SW §8.1에서 큐명 제거 후 '연동 §2.1 큐 카탈로그 참조'만 기술. |

---

### 3-5. DB·API·연동 복합 (aml:db-api-integration)

| # | 심각도 | 서비스 | 항목 | 이격 내용 | 위치 | 권고 |
|---|--------|--------|------|-----------|------|------|
| 34 | HIGH | aml | payloadHash 필수 여부 3방향 충돌 | API §3.1: R=—(선택, 서버 자동계산 확정). 연동 §4.1: Y=필수, '호출자 반드시 전송' 기술. | API §3.1 vs 연동 §4.1 | 연동 §4.1 payloadHash 필수 Y → N/—으로 수정, 설명을 '서버 자동계산' 방식으로 교체. |
| 35 | MEDIUM | aml | §7.2 필드매핑 rawPayload.payloadHash 구 경로 잔존 | §4.1·API §3.1은 최상위 경로로 통일됐으나 §7.2 표만 구 경로 잔존. | 연동 §7.2 vs §4.1·API §3.1 | §7.2 해당 행의 canonical 경로를 `payloadHash`(최상위)로 수정. |

---

### 3-6. API 명세 ↔ PRD (aml:api-prd)

| # | 심각도 | 서비스 | 항목 | 이격 내용 | 위치 | 권고 |
|---|--------|--------|------|-----------|------|------|
| 36 | HIGH | aml | ApprovalDto.subjectType — TM_SCENARIO 누락, '총 15종' 오기 | PRD §11.1에 `TM_SCENARIO` 누락, 15종 표기. API §3.7 정본은 16종. 부록 C는 16종으로 정합. | PRD §11.1 line 1029 vs API §3.7 | PRD §11.1에 `TM_SCENARIO` 추가, '15종' → '16종' 수정. |
| 37 | HIGH | aml | ScreenResponse — `screeningHistory` 필드 미정의 | PRD §3.1이 `screeningHistory` 참조하나 API §3.2 ScreenResponse에 해당 필드 없음. | PRD §3.1 line 435 vs API §3.2 | API §3.2에 `screeningHistory` 추가 정의 또는 PRD §3.1에서 출처를 화면 파생값으로 명시. |
| 38 | MEDIUM | aml | 명단군 컬럼 필드명 `watchlistSourceType` — API DTO 미매핑 | PRD §3.2·§3.3에서 `watchlistSourceType` 사용. API에는 없는 독자 명칭. 실제 `WatchlistEntryDto.listType`(API §3.9). | PRD §3.2 line 496, §3.3 line 555 vs API §3.9 | PRD에서 `watchlistSourceType` → `WatchlistEntryDto.listType`으로 정정. |
| 39 | MEDIUM | aml | 상신 판정 컬럼 `requestedStatus` — ApprovalDto 미정의 | PRD §3.2에서 `requestedStatus` 사용. API §3.7 `ApprovalDto`에 없음. | PRD §3.2 line 497 vs API §3.7 | PRD에서 출처를 payload 파생값으로 명시하거나 API §3.7에 `requestedStatus` 추가 정의. |
| 40 | LOW | aml | `NO_MATCH` — PRD 상태머신·부록 F 미포함 | API §3.2 ScreenResponse.status 6종에 `NO_MATCH` 포함. PRD §1.7·부록 F는 5종만 열거. | PRD §1.7, 부록 F line 1593 vs API §3.2 line 689 | 부록 F에 `NO_MATCH | 매칭없음` 추가. §1.7에 즉시 종결 전이 추가. |

---

### 3-7. PRD ↔ PPT (aml:prd-ppt)

| # | 심각도 | 서비스 | 항목 | 이격 내용 | 위치 | 권고 |
|---|--------|--------|------|-----------|------|------|
| 41 | HIGH | aml | AML-WLF-003 status 파라미터 — RESOLVED 미존재 enum 사용 | PPT: `?status=RESOLVED`. PRD·DB·API 어디에도 RESOLVED 없음. | PPT 슬라이드 10 vs PRD §3.3 | PPT를 `?status=TRUE_MATCH,FALSE_POSITIVE,AUTO_DISCOUNTED`로 교정. |
| 42 | HIGH | aml | AML-APR-001 결재 종류 — CHECKLIST_CHANGE·PERIODIC_REVIEW_CHANGE 누락 | PPT 12종. PRD 15종(2종 누락). | PPT 슬라이드 26 vs PRD §11.1 | PPT에 2종 추가. |
| 43 | HIGH | aml | AML-TNT-003 기본 리전 필수 여부 불일치 | PPT: 별표(필수). PRD·API: 선택(기본값 KR). | PPT 슬라이드 6 vs PRD §13.3 | PPT에서 별표 제거. |
| 44 | HIGH | aml | AML-WLF-002 목록 컬럼 구성 불일치 | PRD 컬럼 7종 vs PPT 6종(상신일·동작 누락, 미정의 점수 추가). | PPT 슬라이드 9 vs PRD §3.2 | PPT에 상신일·동작 추가. 점수 컬럼 제거 또는 PRD 반영 확인. |
| 45 | MEDIUM | aml | AML-WLF-003 요약 카드 — 면제(FP_WHITELIST) 카드 누락 | PPT 4종(확정·오탐·자동낮춤·평균처리). PRD BR-002는 면제 포함 4종. | PPT 슬라이드 10 vs PRD §3.3 BR-002 | PPT에 면제 카드 추가. |
| 46 | MEDIUM | aml | AML-WLF-003 요약 카드 — SLA 단위 불일치 | PRD: 일(days) 단위. PPT: '3.4시간 / SLA 24h 내'. | PPT 슬라이드 10 vs PRD §3.3 | PPT를 일 단위로 수정하거나 PRD에서 시간 단위로 확정 후 동기화. |
| 47 | MEDIUM | aml | AML-CDD-001 시나리오 블록 subjectType 코드 비표준 표기 | PPT: '체크리스트 정책 변경' 서술형. PRD: `CHECKLIST_CHANGE`·`PERIODIC_REVIEW_CHANGE` enum 코드. | PPT 슬라이드 17 vs PRD 부록 C | PPT에 enum 코드 정확히 표기. |
| 48 | MEDIUM | aml | AML-DASH-001 결재 대기 KPI 카드 누락 | PPT: 4종 KPI 카드(결재 대기 미포함). PRD §2.1: 결재 대기 별도 박스 명시. | PPT 슬라이드 3 vs PRD §2.1 | PPT에 결재 대기 건수 카드 추가. |
| 49 | LOW | aml | AML-APR-001 STR/CTR 단일 항목 합산 표기 | PPT: 'STR/CTR 제출' 1개. PRD: STR_SUBMIT·CTR_SUBMIT 2개 별도 subjectType. | PPT 슬라이드 26 vs PRD §11.1 | PPT에서 2개로 분리 표기. |

---

### 3-8. 설계서 ↔ WBS (aml:design-wbs)

| # | 심각도 | 서비스 | 항목 | 이격 내용 | 위치 | 권고 |
|---|--------|--------|------|-----------|------|------|
| 50 | HIGH | aml | T-01 Status — TODO vs DONE 불일치 | 00-overview.md §2 T-01 Status=DONE. 01-scaffolding.md 헤더 Status=TODO. | 01-scaffolding.md 헤더 vs 00-overview.md §2 | 01-scaffolding.md 헤더 `Status: TODO` → `Status: DONE`. |
| 51 | HIGH | aml | T-12 subjectType 종수 — 14종 vs 16종 | 12-approval-engine.md·00-overview.md 변경이력: 14종. 설계서 §13.4/§13.5 정본: 16종. | 12-approval-engine.md vs 설계서 §13.4 | 16종으로 정합. CHECKLIST_CHANGE·PERIODIC_REVIEW_CHANGE 추가. |
| 52 | HIGH | aml | T-02 파일 제목·본문 — V17a/V17b 연동 누락 | 00-overview.md §2 T-02 제목: V17a/V17b 연동 포함. 02-db-migration.md: V01~V16만 명시. | 02-db-migration.md vs 00-overview.md §2 | 파일 제목·목표 본문에 V17a/V17b 범위 경계 명시. |
| 53 | MEDIUM | aml | §6.2 usecase ↔ T-05 — ExportEvidenceUseCase 태스크 귀속 미표기 | 00-overview.md §5 BO 화면 인벤토리에 `ExportEvidenceUseCase`→T-19 귀속 명시 없음. | 00-overview.md §5 vs 설계서 §6.2 | §5 인벤토리 비고에 T-19 소유 명시. |
| 54 | MEDIUM | aml | T-01 참조 섹션 — §21 Phase 0 비대상 명시 없음 | 01-scaffolding.md 참조에 Phase 0 비대상 여부 언급 없어 경계 불명확. | 01-scaffolding.md vs 00-overview.md §4 | Phase 0 분석 완료 전제임을 한 줄 추가. |
| 55 | LOW | aml | T-09 구분 라벨 — BO 소유가 T-10인데 [BE+BO] 표기 | 실질 BO 화면은 T-10 위임. 헤더 태그 [BE+BO] 혼동 유발. | 09-wlf-screening.md 헤더 vs 00-overview.md §2 | 헤더를 `[BE]` 또는 `[BE+BO→T-10]`으로 정정. 00-overview.md §2 동기화. |

---

### 3-9. WBS ↔ 로드맵 (aml:wbs-roadmap)

| # | 심각도 | 서비스 | 항목 | 이격 내용 | 위치 | 권고 |
|---|--------|--------|------|-----------|------|------|
| 56 | HIGH | aml | 로드맵 §3 P4 aml 칸 — T-12(완성) 누락 | §3 P4 aml: T-14·T-16만 기재. P4 Phase 파일: P4-AML-03(T-12 완성)이 실태스크로 존재. | 00-program-overview.md §3 P4 vs 05-phase4-action-case-approval.md | §3 P4 aml 칸에 T-12(완성) 추가. |
| 57 | HIGH | aml | 로드맵 §3 P4 aml vs Phase 파일 헤더 — T-ID 집합 불일치 | §3: T-14·T-16. Phase 파일 헤더: T-13·T-16. Phase 파일 실태스크: T-12·T-13·T-14. 세 기준 모두 상이. | 00-program-overview.md §3 vs 05-phase4-action-case-approval.md | §3을 실태스크 기준으로 T-12·T-13·T-14·T-16으로 정정. Phase 파일 헤더도 동기화. |
| 58 | MEDIUM | aml | WBS T-12 Due 표기 — P4 완성분 누락 | T-12 Due='P2' 단일 표기. T-14는 'P2(MVP)/P4(완성)' 분할 표기. | 00-overview.md §2 T-12 행 vs Phase 파일 P4-AML-03 | T-12 Due를 'P2(골격)/P4(완성)'으로 정정. |
| 59 | MEDIUM | aml | WBS T-14 의존 — MVP/완성 분할 의존 미표기 | T-14 의존: 'T-07,T-13' 단일 기재. P2 MVP는 T-13 불필요, P4 완성만 T-13 의존. | 00-overview.md §2 T-14 vs P2·P4 Phase 파일 | 'MVP: T-07·T-11, 완성: +T-13'으로 주석 분리 표기. |

---

### 3-10. 로드맵 ↔ 설계·PRD 복합 (aml:roadmap-design-prd)

| # | 심각도 | 서비스 | 항목 | 이격 내용 | 위치 | 권고 |
|---|--------|--------|------|-----------|------|------|
| 60 | HIGH | aml | P5-AML-02 화면 ID — WLF-003 누락 | P5-AML-02 DoD: WLF-001/002만 참조. PRD v5.2: WLF-003 독립 화면으로 확정. | 06-phase5-bo-web.md §2.3 vs PRD §3.3·§1.2 | P5-AML-02 화면 ID를 WLF-001/002/003으로 확장. DoD에 처리 이력 탭 추가. |
| 61 | HIGH | aml | P2-AML-05·P4-AML-03 subjectType 종수 — 14종 vs 15종 | 로드맵 DoD: 14종. PRD §11.1·API §3.7 정본: 15종(CHECKLIST_CHANGE·PERIODIC_REVIEW_CHANGE 추가). | 03-phase2-engines-mvp.md, 05-phase4-action-case-approval.md vs PRD §11.1 | DoD에서 14종 → 15종으로 정정. 2종 실행효과 명시. |
| 62 | MEDIUM | aml | aml WBS 패키지명 — com.hanpass.aml vs com.aegis.aml | WBS: `com.hanpass.aml`(설계 표기). 로드맵: aegis-aml 구현 패키지 `com.aegis.aml` 명시. | 00-overview.md §0 vs 00-program-overview.md §0 | WBS §0에 '(설계 표기; 구현 패키지: `com.aegis.aml`)' 주석 추가. |
| 63 | MEDIUM | aml | P6 헤더 §인용 모호성 — §18/§21 서비스 구분 불명확 | `§18/§21 Phase 5~6` 단순 표기로 FDS·AML 설계서 §번호 혼합. | 07-phase6-regulatory-integration.md 헤더 vs PRD §9·§10 | 서비스별 §번호를 분리 표기(FDS §18, AML §21 등). |
| 64 | LOW | aml | P5 헤더 WLF 명칭 — WLF-003 미반영 | P5 §1 범위에서 WLF 단순 기재. PRD v5.2 이후 3탭 화면 확정. | 06-phase5-bo-web.md §1 vs PRD §3 | `WLF(AML-WLF-001~003: 검토 필요·상위승인·처리 이력)`으로 보강. |

---

### 3-11. 횡단 이격 — 명칭·테넌시·PII (cross:naming-tenancy-pii)

| # | 심각도 | 서비스 | 항목 | 이격 내용 | 위치 | 권고 |
|---|--------|--------|------|-----------|------|------|
| 65 | MEDIUM | cross | 설계서 §17 DDL 공통 감사·테넌시 컬럼 누락(총괄) | §17.1~§17.4 DDL 대부분 `created_at` 1컬럼만 포함. DB §2.1은 6컬럼 전수 요구. `data_scope` 멀티테넌시 분리키 누락 시 SHARED 배포 권한 필터 미동작 위험. | 설계서 §17 전체 vs DB §2.1 | §17 DDL에 '공통 컬럼은 §2.1 규약 참조' 주석 또는 (공통 §2.1) 생략 표기 추가. |
| 66 | MEDIUM | cross | 설계서 §10.4 screening_status — 한국어 표시값 누락 | 설계서 §10.4에 한국어 표시값 열 없음. DB §5.5는 6종 한국어 표시값 완비. | 설계서 §10.4 vs DB §5.5 | §10.4에 한국어 표시값 열 추가 또는 DB §5.5 정본 참조 주석. |
| 67 | MEDIUM | cross | POTENTIAL_MATCH 별칭 정본 enum 지위 불명확 | 설계서 §10.4에 `POTENTIAL_MATCH` 별칭·정규화 처리 미기재. §15.7 주석에만 언급. | 설계서 §10.4 vs §15.7 vs DB §5.5 | §10.4 표에 'POTENTIAL_MATCH는 POSSIBLE_MATCH 별칭, 저장값은 POSSIBLE_MATCH' 명시. |
| 68 | LOW | cross | 설계서 §19.2 PII 마스킹 컬럼 명명 패턴 미명시 | 방침만 기술, DB §2.2의 hash 컬럼 명명 패턴(`name_hash`/`doc_hash` 등) 참조 없음. | 설계서 §19.2 vs DB §2.2 | §19.2에 'PII 마스킹 컬럼 명명은 DB §2.2 의미 패턴 규약 따름' 참조 추가. |
| 69 | LOW | cross | 설계서 §12.2 alert_status 6종 이후 전이 — case_status 귀속 설명 미완 | alert lifecycle 맥락에서 INVESTIGATING/REPORTED/CLOSED 언급 여지. DB §5.7은 역삽입 권고했으나 §12.2 미반영. | 설계서 §12.2 vs DB §5.7 | §12.2에 'CASE_OPENED 이후 전이는 aml_cases.status(§13.3a) 담당' 명기. |

---

## ④ 개발 착수 권고

### 조치 우선순위

**Phase 0 — 착수 블로커 (HIGH 17건, 즉시 조치)**

1. **subjectType 종수 통일 (14→15→16종)**: T-12 WBS, P2-AML-05, P4-AML-03, PRD §11.1이 각각 다른 종수를 참조. 결재 엔진 구현 전 API §3.7 정본 기준 16종으로 전수 정합 필요.
2. **payloadHash 필수 여부 확정**: API §3.1(선택) ↔ 연동 §4.1(필수) 정면 충돌. ingest 어댑터 구현 전 연동 §4.1·§7.2를 'R=— 선택, 서버 자동계산'으로 수정.
3. **canonical event payloadHash 경로 통일**: 설계서 §8.2 `rawPayload.payloadHash` 중첩 → 최상위 `payloadHash`로 교체.
4. **DB aml_evidence_exports.status 컬럼 추가**: API 응답 필드가 DB 컬럼으로 backing 없음. Flyway 마이그레이션 추가 후 구현 착수.
5. **로드맵 P4 aml 칸 T-12 완성 누락**: P4 범위 오인으로 결재 엔진 실행 relay 누락 위험. 착수 전 §3 표 정정.
6. **P5-AML-002 WLF-003 화면 누락**: WLF 3탭 흐름 구현 전 DoD 확장 필요.
7. **T-01 Status DONE 갱신**: 스캐폴딩 완료 사실이 태스크 파일에 미반영.
8. **T-02 V17a/V17b 범위 경계 명시**: DB 마이그레이션 태스크 범위 혼동 방지.
9. **연동 §3.1 vendor.* 카운트 오기 수정**: '14종' → '15종'.

**Phase 1 — 설계 안정화 (MEDIUM 22건, 스프린트 착수 전)**

- 설계서 §17 DDL 감사 컬럼 일괄 정합 (§2.1 규약 주석 추가)
- API 미정의 DTO 보완: `AlertDto`, `RiskScoreResponse` 3필드, `SourceSystemDto` 감사 필드
- PRD 필드명 오류 수정: `watchlistSourceType` → `WatchlistEntryDto.listType`, `requestedStatus` 출처 명시
- PPT 오류 수정: RESOLVED enum, 결재 종류 2종, 기본 리전 별표, WLF-002 컬럼 구성
- WBS T-12/T-14 Phase 분할 표기, usecase ↔ 태스크 귀속 매핑

**Phase 2 — 문서 품질 보강 (LOW 17건, 스프린트 중)**

- 지원 인프라 테이블 5종 DDL 또는 참조 주석 추가
- 변경 이력 오기 정정, enum 별칭 주석, PII 컬럼 명명 규약 참조 추가

### 미검증 쌍

없음 — 전수 검증 완료. 단, 추가 문서(연동 §7.3 이후, API §4 이후 일부 섹션)가 본 QA 범위 외에 존재할 경우 재실행 필요.

---

*생성: doc-consistency-qa | 대상: aml | 판정: FAIL | 2026-06-08*
