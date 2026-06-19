# AML Platform DB 설계서 (aml-svc)

> 정본: `.claude/skills/_shared/target-architecture.md` (PostgreSQL · Flyway, 서비스별 별도 스키마, 멀티테넌시, PII 마스킹, 4-eyes, 규제 Policy Pack STR/CTR/Travel Rule).
> 입력 진실: `docs/software/02-amlSvc-sass.md` (SaaS AML Platform 설계서) — 본 DB 설계서는 설계서 §7~§19의 데이터 모델·enum·규제 요건을 물리 모델로 확정한다.
> 책임 서비스: `services/aml-svc` (Java 25, Spring Boot 3.5.x, 헥사고날, `com.hanpass.aml`). 운영 콘솔·결재·감사 UI는 `bo-api`/`bo-web`가 본 스키마를 admin API 경유로 사용한다.

## 0. 설계 정본·스코프

| 항목 | 결정 | 근거 |
|---|---|---|
| RDBMS | PostgreSQL 16+ | 정본 §3 (bo-api/엔진 Flyway·PostgreSQL) |
| 마이그레이션 | Flyway (additive, `V<NN>__*.sql`) | 정본 §3, 설계서 §17 (additive migration) |
| 스키마 격리 | **`aml` 스키마 전용** (fds-svc·bo-api와 별도 스키마) | 정본 §5·과업 규칙 4 |
| 배포 모델 | **`MANAGED_DEDICATED`(기본·전용 DB·IaC)** / `SELF_HOSTED`(설치형) / `SHARED`(소규모 공유). 격리는 배포 단위 결정이며 온보딩 프로비저닝의 산출. 구 `isolation_mode`(`SHARED`/`SCHEMA`/`DB`) 폐기(정본 §4.1, D-06 결정 확정) | 정본 target-architecture §4.1, 설계서 §16 |
| PII | raw 미저장. `*_hash`(tenant-keyed HMAC) / `*_token`(tenant-managed tokenization)만 저장 (D-05) | 설계서 §19.2, D-05 |
| 금액 | 정수 최소단위 권장. 설계서 DDL의 `NUMERIC(24,8)`은 crypto/외화 소수 수용용으로 유지하되 `*_amount_minor BIGINT`(통화 최소단위) 병행 컬럼 제공 | 스킬 §2 |
| 감사 컬럼 | 전 운영 테이블 `created_at/created_by/updated_at/updated_by` + append-only 감사 evidence 별도 | 정본 §4, 설계서 §19.3 |
| 보존 | 테이블별 `retention_class` 정책(아래 §6) | 설계서 §16.3·§19 |

본 문서가 확정하는 명칭(스키마·테이블·컬럼·enum)은 API 명세서(`docs/design/api/02-aml-api.md`), 연동 명세(`docs/design/integration/02-aml-integration.md`), 태스크(`docs/tasks/aml/`), PRD가 그대로 참조한다.

---

## 1. 도메인 → 논리 모델 (ERD)

설계서 §7.1 핵심 객체와 §5.1(고객·법인 중심) 원칙을 ERD로 도출한다. AML은 거래가 아니라 **고객/법인/실소유자 graph**를 중심에 둔다.

> **Account / Instrument 엔티티 모델링 결정(설계서 §7.1·§8.1 account.\*/instrument.\* event family 대응).** AML 엔진은 계좌·instrument 전용 마스터 테이블(`aml_accounts`/`aml_instruments`)을 **보유하지 않는다**. 근거: (1) AML 도메인 중심은 고객/법인/실소유자 graph이며 계좌·instrument는 거래 맥락 속성으로, 자금 흐름 상태 추적은 FDS 엔진(fds-svc) 소유 경계다. (2) account.\*/instrument.\* canonical event는 `aml_canonical_events`(JSONB payload, PII는 ref/hash)에 그대로 보존되어 TM 윈도우·재screening 입력으로 materialize한다. (3) instrument 중 CRYPTO_ADDRESS(지갑주소)는 `aml_travel_rule_transfers.wallet_address_hash`·`aml_watchlist_entries.attributes`(지갑주소 hash)·screening `target_type=CRYPTO_ADDRESS`로 추적되어 단절되지 않는다. (4) 계좌·instrument의 `*_ref`/`*_hash`는 `aml_alerts.transaction_ref`·`aml_business_documents`·relationship `USES_ACCOUNT` edge로 graph에 연결한다. 별도 마스터가 필요해지면(예: instrument 단위 risk profile 누적) 추가는 §3에 additive 테이블로 가능하나 현 정본은 미보유다.

```mermaid
erDiagram
    AML_TENANTS ||--o{ AML_SOURCE_SYSTEMS : "has"
    AML_TENANTS ||--o{ AML_CUSTOMERS : "scopes"
    AML_TENANTS ||--o{ AML_ENTITIES : "scopes"
    AML_TENANTS ||--o{ AML_WATCHLIST_SOURCES : "scopes"

    AML_CUSTOMERS ||--o{ AML_RELATIONSHIPS : "from/to"
    AML_ENTITIES  ||--o{ AML_RELATIONSHIPS : "from/to"
    AML_CUSTOMERS ||--o{ AML_SCREENING_RESULTS : "target"
    AML_ENTITIES  ||--o{ AML_SCREENING_RESULTS : "target"
    AML_CUSTOMERS ||--o{ AML_RISK_SCORES : "target"
    AML_ENTITIES  ||--o{ AML_RISK_SCORES : "target"

    AML_WATCHLIST_SOURCES ||--o{ AML_WATCHLIST_ENTRIES : "imports"
    AML_WATCHLIST_ENTRIES ||--o{ AML_SCREENING_RESULTS : "matched"

    AML_CANONICAL_EVENTS ||--o{ AML_ALERTS : "triggers"
    AML_ALERTS ||--o{ AML_CASES : "opens"
    AML_SCREENING_RESULTS ||--o{ AML_CASES : "opens"
    AML_RISK_SCORES ||--o{ AML_CASES : "opens"
    AML_CASES ||--o{ AML_REGULATORY_REPORTS : "files"
    AML_CASES ||--o{ AML_APPROVALS : "requires"

    AML_CUSTOMERS ||--o{ AML_BUSINESS_DOCUMENTS : "subject"
    AML_ENTITIES  ||--o{ AML_BUSINESS_DOCUMENTS : "subject"
    AML_BUSINESS_DOCUMENTS ||--o{ AML_TRAVEL_RULE_TRANSFERS : "evidences"

    AML_APPROVALS ||--o{ AML_AUDIT_EVENTS : "logged"
    AML_REGULATORY_REPORTS ||--o{ AML_AUDIT_EVENTS : "logged"

    AML_TENANTS {
        varchar tenant_id PK
        varchar deployment_model
        varchar onboarding_status
        varchar status
    }
    AML_CUSTOMERS {
        varchar tenant_id PK
        varchar customer_ref PK
        varchar customer_type
        varchar risk_grade
    }
    AML_ENTITIES {
        varchar tenant_id PK
        varchar entity_ref PK
        varchar entity_type
    }
    AML_RELATIONSHIPS {
        varchar tenant_id PK
        uuid relationship_id PK
        varchar relationship_type
    }
    AML_SCREENING_RESULTS {
        varchar tenant_id PK
        uuid screening_id PK
        varchar status
    }
    AML_RISK_SCORES {
        varchar tenant_id PK
        uuid score_id PK
        varchar risk_grade
    }
    AML_CASES {
        varchar tenant_id PK
        uuid case_id PK
        varchar case_type
        varchar status
    }
    AML_REGULATORY_REPORTS {
        varchar tenant_id PK
        uuid report_id PK
        varchar report_type
    }
    AML_APPROVALS {
        varchar tenant_id PK
        uuid approval_id PK
        varchar status
    }
```

### 1.1 멀티테넌시 격리 전략 — 배포 모델 기반 (정본 §4.1)

격리는 DB 행/스키마 토글이 아니라 **배포 단위 결정**이다. 화면 라디오 즉석 선택이 아니라 **온보딩 프로비저닝 프로세스**의 산출이다. `aml_tenants.deployment_model`(구 `isolation_mode` 대체).

| 격리 키 | 컬럼 | 타입 | 역할 |
|---|---|---|---|
| tenant | `tenant_id` | `VARCHAR(64) NOT NULL` | **배포의 서비스(테넌트=서비스)**. 상위 기관(institution)이 운영하는 서비스 1종 = tenant 1개(1 기관 : N 서비스, §3.1 `institution_ref`). 전용 배포(`MANAGED_DEDICATED`/`SELF_HOSTED`)에선 사실상 단일 값. 모든 `aml_*` PK 선두 컬럼. `SHARED` 배포에서만 서비스 간 행 격리 키 |
| data-scope | `data_scope` | `VARCHAR(64)` (nullable) | 운영자 row-level **권한 필터** — 저장 격리 아님. bo-api가 운영자 토큰 scope로 강제 필터 |

> **`workspace_id` 미사용 결정(정본 §4 × 설계서 §16.2.1 합의)**: 정본 target-architecture §4는 `tenant_id`/`workspace_id`/`data_scope` 3-key를 언급하나, 본 aml-svc는 **`workspace_id`를 물리 컬럼으로 도입하지 않는다**. 근거: 설계서 §16.2.1 배포 내부 분리 키 표에서 `workspace_id` 행을 명시적으로 제외하고 `tenant_id` + `data_scope` 2-key 모델로 확정했다. `workspace`(retail/corporate, prod/sandbox 등 논리 환경 분리) 필요 시 `data_scope` 하위 규약 또는 future additive column으로 수용하며, 현 정본에서는 미도입이다. 미사용 결정 근거를 설계서 §16.2.1에서 참조·관리한다.

규칙:
- 모든 운영 테이블 PK 선두는 `tenant_id`. UNIQUE·조회 인덱스도 `tenant_id` 선두.
- 격리의 **1차 경계는 배포 모델**(§3.1 `aml_tenants.deployment_model`). 전용 배포는 배포 자체가 서비스(테넌트) 경계이며, 본 DDL은 단일 배포 내부 모델을 기술한다(`SHARED` 배포일 때만 `tenant_id` 행 격리가 서비스 간 경계로 동작). 테넌트=서비스이며 그 상위에 기관(institution)이 있다(1 기관 : N 서비스).
- `SHARED` 배포에서 행 단위 격리는 PostgreSQL **RLS 정책**(`app.current_tenant` 세션 변수)으로 보강한다.
- "서비스 등록"은 격리 라디오가 아니라 **배포 유형 선택 + 온보딩 신청·상태**(`onboarding_status`) 관리다. 온보딩 상태머신은 §5.28 참조.
- `data_scope`(영업점·법인그룹 등 하위 격리)는 `data_scope` 컬럼으로 표현하고 bo-api 권한과 매핑한다(정본 §4).
- 온보딩·배포 메타(`deployment_model`/`onboarding_status`/`default_region`/`infra_ref`)는 `aml_tenants`(§3.1)에 보존한다. 매니지드 전용 IaC 파이프라인·self-hosted 라이선스 발급/검증 방식은 P8 인프라 설계에서 확정(오픈결정).
- **서비스 관리(배포/온보딩) 소유 경계**: bo-api가 `deployment_model`/`onboarding_status` 기준으로 소유·집약하며, 온보딩 프로비저닝/상태조회/self-hosted 등록 콜백 엔드포인트는 **bo-api 전용**이다. aml-svc 엔진 API에는 온보딩 엔드포인트를 두지 않는다.

---

## 2. 물리 모델 — 공통 규약

### 2.1 공통 감사·테넌시 컬럼 (모든 운영 테이블)

| 컬럼 | 타입 | NULL | 기본값 | 설명 |
|---|---|---|---|---|
| `tenant_id` | VARCHAR(64) | N | — | 서비스(테넌트=서비스) 격리 키. 모든 PK·인덱스 선두 |
| `data_scope` | VARCHAR(64) | Y | NULL | 서비스 하위 격리(영업점·법인그룹). NULL=tenant 전역 |
| `created_at` | TIMESTAMPTZ | N | now() | 생성 시각 |
| `created_by` | VARCHAR(128) | N | 'system' | 생성 주체(운영자 ID·system·source-system) |
| `updated_at` | TIMESTAMPTZ | N | now() | 수정 시각(트리거/애플리케이션 갱신) |
| `updated_by` | VARCHAR(128) | Y | NULL | 최종 수정 주체 |
| `trace_id` | VARCHAR(64) | Y | NULL | 관측성 traceId 전파(설계서 §20.3). 동일 timeline 추적 |

> append-only 감사 테이블(`aml_audit_events`)·canonical event store(`aml_canonical_events`)는 불변이므로 `updated_*`를 두지 않는다.

### 2.2 PII 처리 규약 (설계서 §19.2, D-05)

- 주민번호·여권번호·계좌번호·카드번호·CI/DI **원문 컬럼 금지**.
- 식별은 `customer_ref`/`entity_ref`(원천 시스템 ref, 토큰/HMAC) 사용.
- 매칭 보조 필드는 **이름→hash / 문서번호→hash / 계좌→hash / 지갑주소→hash 의미 패턴**(tenant-keyed HMAC-SHA256)으로, 실제 컬럼명은 테이블별 prefix를 따른다: customer는 `name_hash`/`doc_hash`(§3.3), entity는 `legal_name_hash`/`biz_no_hash`(§3.4), watchlist는 `primary_name_hash`(§3.7), travel-rule은 `wallet_address_hash`(§3.14). (account_hash는 canonical event payload·`USES_ACCOUNT` edge 속성으로 보존, §1 Account/Instrument 미보유 결정.)
- 원문이 필요한 WLF matching은 메모리 일시 처리 후 폐기, 저장은 hash/token만(설계서 §19.2).
- `raw_payload`는 기본 미저장. `payload_hash`(sha256: `sha256:<hex>` 형식) 참조만 보존한다. **`stored` 플래그는 설계서 §8.2(2026-06-07 변경이력) 기준 폐기됨 — DB에 `stored` 컬럼을 두지 않는다**(QA issue #7 low 정합).
- **PII reveal 원천 = 가역암호 vault (T3 AML-ENG-03, ADR 2026-06-15 D1).** 위 hash 컬럼은 단방향이라 마스킹 토큰→원문 역참조가 불가능하다. reveal(`POST /internal/v1/aml/pii/reveal`, API §2.6)의 cleartext 산출 원천으로 **`aml_pii_vault`(§3.21)** 를 둔다. vault 는 원문의 **암호문(`ciphertext`)** 만 저장하므로 위 "원문(=평문) 컬럼 금지" 규약은 그대로 유지된다(평문 컬럼 0개). 암복호는 `SecretCipherPort`(AES-256-GCM, `aws`=KMS 스왑). reveal cleartext 는 이 요청 한정 transient — 영속·로그 금지(§19.2). vault 적재 시점·전 필드 확장은 후속(가정 A2).

### 2.3 enum 코드·표시값 병기 규약

enum은 컬럼에 **코드값(대문자 스네이크)** 저장, 표시값(라벨·다국어)은 bo-web/i18n에서 매핑. 본 문서 §5에 코드↔표시 매핑표를 둔다.

---

## 3. 테이블 명세

### 3.1 `aml_tenants` — 서비스 마스터(테넌트=서비스) (설계서 §17.1, §16)
> **계층**: 기관(institution) → 서비스(테넌트, `tenant_id`) → (논리)워크스페이스. `aml_tenants`의 1행 = 한 서비스(테넌트). 상위 기관 1개가 여러 서비스를 운영한다(**1 기관 : N 서비스**). 기관 식별은 `institution_ref`로 참조한다.

| 컬럼 | 타입 | NULL | 기본값 | 제약 | 설명 |
|---|---|---|---|---|---|
| `tenant_id` | VARCHAR(64) | N | — | PK | 서비스 ID(테넌트=서비스, 격리 경계·PK 선두) |
| `institution_ref` | VARCHAR(64) | Y | NULL | | **상위 기관(institution) 참조**. 납품받은 회사/금융기관 식별자. 1 기관 : N 서비스 관계의 외부 키(FK 아님·논리 참조). nullable·additive 신규 컬럼(후속 마이그레이션 §7에서 추가, 기존 row는 NULL 백필 후 매핑) |
| `display_name` | VARCHAR(160) | N | — | | 표시명 |
| `deployment_model` | VARCHAR(32) | N | `'MANAGED_DEDICATED'` | enum §5.28 (3종) | 배포 유형(구 `isolation_mode` 대체). `MANAGED_DEDICATED`/`SELF_HOSTED`/`SHARED`. 온보딩 프로비저닝의 산출 — 화면 라디오 즉석 변경 아님 |
| `onboarding_status` | VARCHAR(32) | N | `'REQUESTED'` | enum §5.28a (8종) | 온보딩 진행 상태. 상태머신: 매니지드=`REQUESTED→PROVISIONING→DEPLOYED→VERIFIED→ACTIVE`, self-hosted=`REQUESTED→PACKAGE_ISSUED→CUSTOMER_DEPLOYED→REGISTERED`, SHARED=`REQUESTED→ACTIVE` |
| `default_region` | VARCHAR(32) | N | `'KR'` | | 기본 데이터 리전(한국 우선, §16.3). 전용 배포 region. |
| `infra_ref` | VARCHAR(160) | Y | NULL | | 배포 메타 참조. 매니지드=Terraform stack/workspace ID, self-hosted=라이선스·설치 인스턴스 ID. 발급·검증 방식은 P8 인프라 설계 확정(오픈결정) |
| `status` | VARCHAR(32) | N | `'ONBOARDING'` | enum §5.28b (**4종**, FDS §11.6.7 동기화) | **운영 생명주기** — `onboarding_status`와 직교. `ONBOARDING`/`ACTIVE`/`SUSPENDED`/`OFFBOARDED` (QA cross #119 high·#127 medium 정합 — FDS `fds_tenants.tenant_status` 4종과 코드값·DEFAULT 동기화. 신규 등록 시 DEFAULT `'ONBOARDING'`, 온보딩 완료 시 `ACTIVE` 전환) |
| `policy_pack_code` | VARCHAR(64) | N | `'KR_DEFAULT'` | | 적용 Policy Pack(STR/CTR/Travel Rule) |
| `retention_policy` | JSONB | N | `'{}'` | | 서비스별 보존·파기 override |
| `created_at/created_by/updated_at/updated_by` | (공통 §2.1) | | | | 감사 컬럼 |

PK: `(tenant_id)`

> **마이그레이션 V17·V20**: 구 `isolation_mode` 컬럼은 V17a/V17b에서 `deployment_model`/`onboarding_status`/`infra_ref` 교체 후 DROP한다. **V20**: `status` enum 3종→4종 갱신(`ONBOARDING` 추가, `OFFBOARDING`→`OFFBOARDED`), DEFAULT `'ACTIVE'`→`'ONBOARDING'` 변경. 자세한 내용은 §7 V17/V20 참조.
> **마이그레이션(institution_ref·후속)**: 상위 기관 참조 컬럼 `institution_ref VARCHAR(64) NULL`은 **다음 마이그레이션에서 additive(nullable)로 추가**한다(1 기관 : N 서비스). 기존 row는 NULL로 시작 후 기관-서비스 매핑이 확정되면 백필한다. 기관 마스터 테이블 정식화는 후속 설계에서 확정.

### 3.2 `aml_source_systems` — 데이터 원천 (설계서 §17.1, §15)

| 컬럼 | 타입 | NULL | 기본값 | 제약 | 설명 |
|---|---|---|---|---|---|
| `tenant_id` | VARCHAR(64) | N | — | PK,FK→aml_tenants | |
| `source_system` | VARCHAR(64) | N | — | PK | 원천 코드. **hanpass-ph 실서비스 카탈로그(REST sync 인입 정본)**: `member-svc`(회원/KYC/CDD/제재·PEP zoloz 스크리닝 — `customer.*`/`entity.*`/`beneficial-owner.*`), `walletchg-svc`(월렛충전 cash-in — `transaction.requested`), `domestic-svc`(국내송금 PHP — `transaction.requested`), `remit-svc`(해외송금 cross-border, `sanction_screening_event`·`str_indicators` 보유 — `transaction.requested`·`settlement.posted`), `wallet-svc`(월렛 원장 `transfer_links` 자금그래프 — `account.*`·`settlement.posted`), `tx-history-svc`(회원 통합 이력 read model — 대상 360° 피드), `inbound-svc`(파트너 인바운드 송금 — `transaction.requested`). generic placeholder(core-banking/kyb/card/wallet/remit)는 위 실서비스의 예시 추상으로만 잔존 — 운영 등록값은 hanpass-ph 코드 |
| `ingest_mode` | VARCHAR(32) | N | — | enum | `REST_PUSH`/`QUEUE`/`POLLING`/`CDC`/`SNAPSHOT`/`VENDOR_BRIDGE` (§15) |
| `schema_version` | VARCHAR(80) | N | — | | schema registry 버전 |
| `auth_mode` | VARCHAR(32) | N | 'API_KEY_HMAC' | enum | `API_KEY_HMAC`/`OAUTH2`/`MTLS` (§15.7, D-13) |
| `secret_ref` | VARCHAR(256) | Y | NULL | | API key/secret **참조만**(원문 미저장, secret store) |
| `failure_policy` | VARCHAR(32) | N | 'MANUAL_REVIEW' | enum | `MANUAL_REVIEW`/`FAIL_CLOSED`/`DELAY_ALLOWED` (§15.7, D-14) |
| `enabled` | BOOLEAN | N | TRUE | | 활성 여부 |
| `status` | VARCHAR(32) | N | `'ACTIVE'` | enum | 운영 상태. `ACTIVE`/`DISABLED`(설계서 §17.1 DDL·§16.2.1 정본 — QA issue #4 HIGH 정합) |
| `data_scope` | VARCHAR(64) | Y | NULL | | 서비스 하위 격리(§2.1 공통 규약 — §2.1에서 전 운영 테이블 적용 원칙이 적용되는 테이블임을 명시. QA issue #5 MEDIUM 정합) |
| `created_at/created_by/updated_at/updated_by/trace_id` | (공통) | | | | |

PK: `(tenant_id, source_system)`

### 3.3 `aml_customers` — 개인/사업자 고객 (설계서 §9.1, §17.2)

| 컬럼 | 타입 | NULL | 기본값 | 제약 | 설명 |
|---|---|---|---|---|---|
| `tenant_id` | VARCHAR(64) | N | — | PK | |
| `customer_ref` | VARCHAR(256) | N | — | PK | 원천 ref(토큰/HMAC, raw PII 아님) |
| `customer_type` | VARCHAR(32) | N | — | enum | §5.1 customer_type |
| `name_hash` | VARCHAR(256) | Y | NULL | | 이름 HMAC(매칭용) |
| `doc_hash` | VARCHAR(256) | Y | NULL | | 신분증번호 HMAC |
| `country` | VARCHAR(8) | Y | NULL | | 거주/국적 ISO |
| `kyc_status` | VARCHAR(32) | Y | NULL | enum | §5.25 kyc_status(PENDING/VERIFIED/INCOMPLETE/EXPIRED/REJECTED). DB 물리 정본 |
| `risk_grade` | VARCHAR(32) | Y | NULL | enum | §5.2 risk_grade(최신 RA 결과 캐시) |
| `kyc_evidence` | JSONB | N | '{}' | | KYC checklist 상태(§7.3, 원문 아님) |
| `source_system` | VARCHAR(64) | Y | NULL | | 유입 원천 |
| `onboarding_at` | TIMESTAMPTZ | Y | NULL | | 온보딩 시각 |
| `next_review_due_at` | TIMESTAMPTZ | Y | NULL | | 주기적 재확인 예정(§11.2) |
| `created_at/created_by/updated_at/updated_by/trace_id/data_scope` | (공통) | | | | |

PK: `(tenant_id, customer_ref)`

### 3.4 `aml_entities` — 법인/merchant/seller/vendor (설계서 §9.2, §17.2)

| 컬럼 | 타입 | NULL | 기본값 | 제약 | 설명 |
|---|---|---|---|---|---|
| `tenant_id` | VARCHAR(64) | N | — | PK | |
| `entity_ref` | VARCHAR(256) | N | — | PK | 원천 ref |
| `entity_type` | VARCHAR(64) | N | — | enum | §5.1 entity_type(LEGAL_ENTITY/MERCHANT/SELLER/VENDOR/VASP_CUSTOMER) |
| `legal_name_hash` | VARCHAR(256) | Y | NULL | | 법인명 HMAC |
| `biz_no_hash` | VARCHAR(256) | Y | NULL | | 사업자번호 HMAC |
| `country` | VARCHAR(8) | Y | NULL | | 설립/영업국 |
| `industry_code` | VARCHAR(64) | Y | NULL | | 업종(MCC 등) |
| `merchant_category` | VARCHAR(64) | Y | NULL | | MCC/marketplace category |
| `risk_grade` | VARCHAR(32) | Y | NULL | enum | 최신 RA 등급 |
| `kyb_evidence` | JSONB | N | '{}' | | KYB·UBO·대표자 checklist(§7.3) |
| `expected_activity` | JSONB | N | '{}' | | 예상 거래규모/국가(§9.2) |
| `status` | VARCHAR(32) | Y | NULL | enum | `ACTIVE`/`SUSPENDED`/`CLOSED` |
| `next_review_due_at` | TIMESTAMPTZ | Y | NULL | | |
| `created_at/created_by/updated_at/updated_by/trace_id/data_scope` | (공통) | | | | |

PK: `(tenant_id, entity_ref)`

### 3.5 `aml_relationships` — 고객/법인/UBO graph (설계서 §7.2, §9.3, §17.2)

| 컬럼 | 타입 | NULL | 기본값 | 제약 | 설명 |
|---|---|---|---|---|---|
| `tenant_id` | VARCHAR(64) | N | — | PK | |
| `relationship_id` | UUID | N | — | PK | |
| `from_ref` | VARCHAR(256) | N | — | | 주체 ref(customer/entity) |
| `to_ref` | VARCHAR(256) | N | — | | 대상 ref |
| `relationship_type` | VARCHAR(64) | N | — | enum | §5.3 relationship_type(OWNS/CONTROLS/REPRESENTS/...) |
| `ownership_percent` | NUMERIC(8,4) | Y | NULL | | 지분율(§9.3 변경 이력) |
| `is_ubo` | BOOLEAN | N | FALSE | | 실소유자 표식 |
| `effective_from` | TIMESTAMPTZ | Y | NULL | | 유효 시작 |
| `effective_to` | TIMESTAMPTZ | Y | NULL | | 유효 종료(NULL=현재) |
| `attributes` | JSONB | N | '{}' | | 추가 속성 |
| `created_at/created_by/updated_at/updated_by/trace_id` | (공통) | | | | |

PK: `(tenant_id, relationship_id)`

### 3.6 `aml_watchlist_sources` — 명단 source (설계서 §10.1, §17.3)

| 컬럼 | 타입 | NULL | 기본값 | 제약 | 설명 |
|---|---|---|---|---|---|
| `tenant_id` | VARCHAR(64) | N | — | PK | |
| `source_code` | VARCHAR(80) | N | — | PK | source 코드 |
| `source_type` | VARCHAR(64) | N | — | enum | §5.4 watchlist_source_type(SANCTIONS/PEP/RCA/ADVERSE_MEDIA/INTERNAL/LAW_ENFORCEMENT/VASP_RISK) |
| `provider` | VARCHAR(128) | Y | NULL | | 제공처(UN/OFAC/internal 등 — generic 유지). **hanpass-ph 정합**: 실시간 제재·PEP 스크리닝 신호 소스는 `member-svc`의 `zoloz_aml_screening`(`decision`/`risk_level`/`total_hits`/`hit_results`)으로, screening 결과(§3.8)에 `member-svc` decision 을 정합 매핑한다. `source_type`(§5.4 SANCTIONS/PEP/RCA/ADVERSE_MEDIA/INTERNAL/LAW_ENFORCEMENT/VASP_RISK)는 유지 |
| `status` | VARCHAR(32) | N | 'ACTIVE' | enum | `ACTIVE`/`DISABLED` |
| `active_version` | VARCHAR(80) | Y | NULL | | 적용 중 import 버전(4-eyes 승인본) |
| `last_imported_at` | TIMESTAMPTZ | Y | NULL | | freshness 모니터링(§20.2). **48h 신선도 초과 시 fail-closed**(스크리닝 차단·재import 강제 — `member-svc zoloz` 신호 포함 전 소스 동일 적용) |
| `created_at/created_by/updated_at/updated_by/trace_id` | (공통) | | | | |

PK: `(tenant_id, source_code)`

### 3.7 `aml_watchlist_entries` — 명단 항목 (설계서 §10.2, §17.3)

| 컬럼 | 타입 | NULL | 기본값 | 제약 | 설명 |
|---|---|---|---|---|---|
| `tenant_id` | VARCHAR(64) | N | — | PK | |
| `entry_id` | UUID | N | — | PK | |
| `source_code` | VARCHAR(80) | N | — | FK→aml_watchlist_sources | |
| `list_type` | VARCHAR(64) | N | — | enum | watchlist_source_type와 동일 도메인 |
| `subject_kind` | VARCHAR(32) | N | 'PERSON' | enum | §5.24 subject_kind(PERSON/ENTITY/VESSEL/CRYPTO_ADDRESS, §10.2) |
| `primary_name_hash` | VARCHAR(256) | Y | NULL | | 이름 HMAC |
| `normalized_tokens` | JSONB | N | '[]' | | 정규화 토큰(다국어/전사 matching) |
| `attributes` | JSONB | N | '{}' | | 생년/국적/문서 hash/지갑주소 hash 등(§10.2) |
| `version` | VARCHAR(80) | N | — | | import 버전 |
| `status` | VARCHAR(32) | N | 'ACTIVE' | enum | `ACTIVE`/`DELISTED` |
| `created_at/created_by` | (공통, append 중심) | | | | |

PK: `(tenant_id, entry_id)`

### 3.8 `aml_screening_results` — WLF/제재 판정 (설계서 §10.3~§10.4, §17.3)

| 컬럼 | 타입 | NULL | 기본값 | 제약 | 설명 |
|---|---|---|---|---|---|
| `tenant_id` | VARCHAR(64) | N | — | PK | |
| `screening_id` | UUID | N | — | PK | API `screeningId`(§15.7 응답) |
| `target_ref` | VARCHAR(256) | N | — | | 대상 ref(customer/entity/counterparty/wallet) |
| `target_type` | VARCHAR(64) | N | — | enum | §5.23 target_type(CUSTOMER/ENTITY/COUNTERPARTY/CRYPTO_ADDRESS) |
| `status` | VARCHAR(32) | N | — | enum | §5.5 screening_status(NO_MATCH/POSSIBLE_MATCH/TRUE_MATCH/FALSE_POSITIVE/AUTO_DISCOUNTED/ESCALATED) |
| `score` | NUMERIC(8,4) | Y | NULL | | 유사도 score |
| `score_breakdown` | JSONB | N | '{}' | | name/dob/country/document/address/relationship 분해(§10.3). **hanpass-ph 정합**: `member-svc zoloz_aml_screening.hit_results`(매칭 후보·항목별 점수)를 본 분해로 정규화 — `risk_level`→§5.2 risk_grade, `total_hits`→`matched_entries` 카운트 매핑 |
| `reason_codes` | JSONB | N | '[]' | | reasonCodes(§15.7). zoloz `decision`(승인/거절/검토) 을 본 status(§5.5)로 정규화하고 reason 을 코드화 |
| `matched_entries` | JSONB | N | '[]' | | 후보 entry_id 목록 |
| `rule_version` | VARCHAR(80) | N | — | | 적용 WLF 룰/threshold 버전 |
| `decided_by` | VARCHAR(128) | Y | NULL | | 판정자(분석가) |
| `decided_at` | TIMESTAMPTZ | Y | NULL | | 판정 시각 |
| `expires_at` | TIMESTAMPTZ | Y | NULL | | 실시간 screening 만료(§15.7) |
| `created_at/created_by/updated_at/updated_by/trace_id` | (공통) | | | | |

PK: `(tenant_id, screening_id)`

### 3.9 `aml_risk_scores` — 고객위험평가 (설계서 §11, §17.4)

| 컬럼 | 타입 | NULL | 기본값 | 제약 | 설명 |
|---|---|---|---|---|---|
| `tenant_id` | VARCHAR(64) | N | — | PK | |
| `score_id` | UUID | N | — | PK | `scoreId` |
| `target_ref` | VARCHAR(256) | N | — | | customer/entity ref |
| `target_type` | VARCHAR(64) | N | — | enum | §5.23 target_type(CUSTOMER/ENTITY 사용) |
| `model_code` | VARCHAR(80) | N | — | | RA 모델 코드 |
| `model_version` | VARCHAR(80) | N | — | | 적용 모델 버전(§11.3, 4-eyes 승인본) |
| `risk_score` | NUMERIC(8,4) | N | — | | 0~100 |
| `risk_grade` | VARCHAR(32) | N | — | enum | §5.2 risk_grade(LOW/MEDIUM/HIGH/PROHIBITED) |
| `factor_breakdown` | JSONB | N | '{}' | | factor별 점수·근거(§11.2) |
| `required_action` | VARCHAR(64) | Y | NULL | enum | §5.26 required_action(CDD_UPDATE/EDD/RELATIONSHIP_REVIEW/NONE) |
| `next_review_due_at` | TIMESTAMPTZ | Y | NULL | | 재심사 예정 |
| `is_override` | BOOLEAN | N | FALSE | | 수동 등급 조정 여부(4-eyes 대상) |
| `evaluated_at` | TIMESTAMPTZ | N | now() | | |
| `created_at/created_by/updated_at/updated_by/trace_id` | (공통) | | | | |

PK: `(tenant_id, score_id)`

### 3.10 `aml_alerts` — TM/룰 경보 (설계서 §12, §17.4)

| 컬럼 | 타입 | NULL | 기본값 | 제약 | 설명 |
|---|---|---|---|---|---|
| `tenant_id` | VARCHAR(64) | N | — | PK | |
| `alert_id` | UUID | N | — | PK | `alertId` |
| `alert_type` | VARCHAR(64) | N | — | enum | §5.18 alert_type(TM_SCENARIO/SCREENING/RA/FDS_ESCALATION/VENDOR_ALERT). API `alertType` 정본 동기화 |
| `scenario_code` | VARCHAR(80) | Y | NULL | enum | §5.6 tm_scenario(STRUCTURING/RAPID_MOVEMENT/...) |
| `target_ref` | VARCHAR(256) | Y | NULL | | 대상 고객/법인(`member.member_id`→`customer_ref` keyed HMAC). **대상 360°(§3.16 뷰)·TM 알림 상세의 대상 링크 키** |
| `transaction_ref` | VARCHAR(256) | Y | NULL | | 관련 거래 ref. **hanpass-ph 정합**: `walletchg.charge_order_id`(충전)·`domestic.transaction_id`(국내)·`remit.transfer_number`(해외)·`*.wallet_transaction_id` 중 하나의 keyed token. TM 알림 상세 '관련 거래 목록'의 join 키 — 다건 거래는 `evidence.relatedTransactions[]`(아래)에 transaction_ref 배열로 보존 |
| `severity` | VARCHAR(32) | N | — | enum | §5.19 alert_severity(LOW/MEDIUM/HIGH/CRITICAL) |
| `status` | VARCHAR(32) | N | 'DETECTED' | enum,CHECK | §5.7 alert_status **6종 종결**(DETECTED/TRIAGED/CASE_OPENED/DISMISSED/ESCALATED/STR_RECOMMENDED, CHECK 6종). 이후 조사·보고·종결(INVESTIGATING/REPORTED/CLOSED)은 `aml_cases.status`(§5.9)가 인계 — alert enum에 미포함 |
| `evidence` | JSONB | N | '{}' | | **TM 알림 상세 데이터모델(정본).** ① 트리거: `scenarioCode`·`strIndicator`(데이터 신호 STR_001~015, `remit.str_indicators` 매핑) ·설명. ② 집계 패턴(측정값/기간/기준 충족, 예 `{ "measure":"분할충전 합계", "window":"5BD", "count":9, "amount":"480000.00", "currency":"PHP", "threshold":"…" }`). ③ `relatedTransactions[]`(관련 거래 — `transactionRef`·`channel`(충전/국내/해외)·`amount`·`currency`·`corridor`·`counterpartyRef`·`occurredAt`·`fdsDecisionRef` 링크). ④ `fundGraph`(자금그래프 funnel 미니뷰 — `wallet.transfer_links` 그래프 노드/엣지 요약). 모든 식별자 token/hash, raw PII 금지 |
| `source_origin` | VARCHAR(32) | N | 'AML' | enum | §5.20 source_origin(AML/FDS/VENDOR, §15.5 dual-run 구분) |
| `external_alert_ref` | VARCHAR(256) | Y | NULL | | 외부 vendor alert 식별자(Legacy Vendor Bridge `vendor_alert_id`). SaaS alert와 dual-run 구분 영속화(integration §7.3). `source_origin=VENDOR`일 때 채움 |
| `created_at/created_by/updated_at/updated_by/trace_id/data_scope` | (공통) | | | | |

PK: `(tenant_id, alert_id)`

### 3.11 `aml_cases` — CDD/EDD/조사 케이스 (설계서 §13, §17.4)

| 컬럼 | 타입 | NULL | 기본값 | 제약 | 설명 |
|---|---|---|---|---|---|
| `tenant_id` | VARCHAR(64) | N | — | PK | |
| `case_id` | UUID | N | — | PK | `caseId` |
| `case_type` | VARCHAR(64) | N | — | enum | §5.8 case_type(SANCTIONS_REVIEW/EDD_REVIEW/STR_REVIEW/...) |
| `target_ref` | VARCHAR(256) | Y | NULL | | 대상 고객/법인 |
| `origin_alert_id` | UUID | Y | NULL | FK→aml_alerts | 발단 alert |
| `origin_screening_id` | UUID | Y | NULL | FK→aml_screening_results | 발단 screening |
| `origin_fds_case_ref` | VARCHAR(96) | Y | NULL | | FDS 위임 발단(cross-ref, FK 아님 — `fds` 스키마). fds-svc가 `OPEN_AML_CASE`/`REGULATORY_REPORT`/`REQUEST_TRAVEL_RULE_INFO` 위임 시 `fds_cases.aml_case_id ↔ aml_cases.case_id` 양방향 연결의 역참조. `source_origin=FDS`일 때 채움 |
| `status` | VARCHAR(32) | N | 'OPEN' | enum | §5.9 case_status(OPEN/INVESTIGATING/PENDING_APPROVAL/DISMISSED/REPORTED/CLOSED) |
| `priority` | VARCHAR(32) | Y | NULL | enum | §5.27 priority(LOW/MEDIUM/HIGH/URGENT) |
| `assigned_to` | VARCHAR(128) | Y | NULL | | 담당 분석가 |
| `edd_trigger` | VARCHAR(64) | Y | NULL | enum | §13.2 EDD trigger |
| `timeline` | JSONB | N | '[]' | | 처리 timeline(evidence, §15.6) |
| `due_at` | TIMESTAMPTZ | Y | NULL | | SLA 기한(§20.1 case.sla.breached) |
| `closed_at` | TIMESTAMPTZ | Y | NULL | | 종결 시각 |
| `created_at/created_by/updated_at/updated_by/trace_id/data_scope` | (공통) | | | | |

PK: `(tenant_id, case_id)`

### 3.12 `aml_regulatory_reports` — STR/CTR/Travel Rule 보고 증적 (설계서 §14, §17.4)

| 컬럼 | 타입 | NULL | 기본값 | 제약 | 설명 |
|---|---|---|---|---|---|
| `tenant_id` | VARCHAR(64) | N | — | PK | |
| `report_id` | UUID | N | — | PK | `reportId` |
| `report_type` | VARCHAR(64) | N | — | enum | §5.10 report_type(STR/CTR/TRAVEL_RULE/EDD_REGISTER/WLF_REGISTER/RA_REPORT/AUDIT_EXPORT) |
| `case_id` | UUID | Y | NULL | FK→aml_cases | 연관 케이스 |
| `target_ref` | VARCHAR(256) | Y | NULL | | 대상 |
| `status` | VARCHAR(32) | N | 'DRAFT' | enum | §5.11 report_status(DRAFT/UNDER_REVIEW/APPROVED/SUBMITTED/ACKNOWLEDGED/SUBMISSION_FAILED/REJECTED/CANCELLED — 8종, 설계서 §14.1a FIU 회신 폐루프) |
| `report_payload` | JSONB | N | '{}' | | 보고 본문(PII는 hash/token) |
| `approval_id` | UUID | Y | NULL | FK→aml_approvals | 결재 결과(§13.5) |
| `submitted_ref` | VARCHAR(256) | Y | NULL | | 외부 제출 식별자(§13.5 evidence) |
| `submitted_at` | TIMESTAMPTZ | Y | NULL | | 제출 시각 |
| `fiu_ack_ref` | VARCHAR(256) | Y | NULL | | FIU 접수번호(`ACKNOWLEDGED` 확정 시 저장, 설계서 §14.1a) |
| `submission_error_code` | VARCHAR(64) | Y | NULL | | 전송 실패/FIU 오류 반려 오류코드(`SUBMISSION_FAILED` 시 저장) |
| `resubmit_count` | INT | N | 0 | | 재제출 횟수(RESUBMIT — 기존 `:submit` 4-eyes 재사용, 회차별 이력 보존) |
| `ctr_exemption_code` | VARCHAR(64) | Y | NULL | | CTR 제외(면제) 사유 코드(설계서 §14.3 — `GOV_ENTITY`/`FINANCIAL_INSTITUTION`/`OTHER_STATUTORY`, `CANCELLED` 제외 처리 시 필수·감사 대상) |
| `closure_reason_code` | VARCHAR(64) | Y | NULL | | 종결(비제출) 사유 코드 — `REJECTED`/`CANCELLED` 전이 시 영속(설계서 §14.1a). `ctr_exemption_code`(CTR 면제 사유)와 **별개 의미·공존**. STR 미보고 사유 분포(API §2.7 `unreported-reasons`, PRD §12-B.3 ①)의 집계 원천. legacy 미영속 행은 통계에서 `UNSPECIFIED` 버킷(소급 seed 없음). 코드값(raw PII 아님). (T4 AML-ENG-04, V16 — **확정**) |
| `evidence_hash` | VARCHAR(128) | Y | NULL | | 제출 manifest hash(§19.4) |
| `created_at/created_by/updated_at/updated_by/trace_id` | (공통) | | | | |

PK: `(tenant_id, report_id)`

### 3.13 `aml_business_documents` — 상업 증빙(trade/commerce) (설계서 §7.3, §17.5)

| 컬럼 | 타입 | NULL | 기본값 | 제약 | 설명 |
|---|---|---|---|---|---|
| `tenant_id` | VARCHAR(64) | N | — | PK | |
| `document_ref` | VARCHAR(256) | N | — | PK | 증빙 ref |
| `document_type` | VARCHAR(64) | N | — | enum | §5.21 document_type(INVOICE/PO/BL/CUSTOMS/ORDER/SETTLEMENT) |
| `subject_ref` | VARCHAR(256) | Y | NULL | | 주체 customer/entity |
| `counterparty_ref` | VARCHAR(256) | Y | NULL | | 상대방 |
| `transaction_ref` | VARCHAR(256) | Y | NULL | | 관련 거래 |
| `amount` | NUMERIC(24,8) | Y | NULL | | 금액(외화/crypto 소수 수용) |
| `amount_minor` | BIGINT | Y | NULL | | 통화 최소단위 정수 병행 |
| `currency` | VARCHAR(12) | Y | NULL | | 통화 ISO |
| `country_from` | VARCHAR(8) | Y | NULL | | 선적/계약국 |
| `country_to` | VARCHAR(8) | Y | NULL | | 수취국 |
| `evidence_hash` | VARCHAR(128) | Y | NULL | | 증빙 원본 hash(원문 미저장) |
| `attributes` | JSONB | N | '{}' | | HS code/품목/단가 등(§18.5 TBML) |
| `created_at/created_by/updated_at/updated_by/trace_id/data_scope` | (공통) | | | | |

PK: `(tenant_id, document_ref)`

### 3.14 `aml_travel_rule_transfers` — 가상자산 Travel Rule (설계서 §14.1, §18.4, §17.5)

| 컬럼 | 타입 | NULL | 기본값 | 제약 | 설명 |
|---|---|---|---|---|---|
| `tenant_id` | VARCHAR(64) | N | — | PK | |
| `transfer_ref` | VARCHAR(256) | N | — | PK | 이전 ref |
| `originator_ref` | VARCHAR(256) | Y | NULL | | 송신 고객 ref |
| `beneficiary_ref` | VARCHAR(256) | Y | NULL | | 수신 고객 ref |
| `asset_code` | VARCHAR(32) | Y | NULL | | 가상자산 코드 |
| `chain` | VARCHAR(32) | Y | NULL | | 체인 |
| `wallet_address_hash` | VARCHAR(256) | Y | NULL | | 지갑주소 HMAC(원문 미저장) |
| `amount` | NUMERIC(24,8) | Y | NULL | | 수량(외화/crypto 소수 수용) |
| `amount_minor` | BIGINT | Y | NULL | | 통화 최소단위 정수 병행(§0 `*_amount_minor` 규약, integration payload `amountMinor`) |
| `originator_vasp` | VARCHAR(128) | Y | NULL | | 송신 VASP |
| `beneficiary_vasp` | VARCHAR(128) | Y | NULL | | 수신 VASP |
| `completeness_status` | VARCHAR(32) | Y | NULL | enum | §5.22 completeness_status(COMPLETE/MISSING_ORIGINATOR/MISSING_BENEFICIARY/INCOMPLETE) |
| `risk_status` | VARCHAR(32) | Y | NULL | enum | §5.15 risk_status: `CLEAR`/`SANCTIONED_ADDRESS`/`MIXER_EXPOSURE`/`HIGH_RISK`. **DB가 enum 정본**(CHECK 4종). exception 큐 트리거(integration §4.3/§9.3의 `REVIEW`)는 `HIGH_RISK`로 정규화 매핑(§5.15 주석) |
| `exception_reason` | VARCHAR(256) | Y | NULL | | exception 처리 사유(4-eyes) |
| `created_at/created_by/updated_at/updated_by/trace_id` | (공통) | | | | |

PK: `(tenant_id, transfer_ref)`

> 위 §3.1~§3.14가 정본 downstream의 **`aml_*` 도메인 테이블 14종**이다.

### 3.17 `aml_ira_reports` — 기관위험평가(IRA, ML/TF) 회차 (T1 AML-ENG-01, 부록 E v6.0-2 확정)

KoFIU 기관위험평가 지표 보고 회차. KR 확장 plugin 활성 서비스 한정(부록 E). 멀티테넌시 키 `(tenant_id, report_id)` — tenant 단위 규제보고(workspace 차원 없음).

| 컬럼 | 타입 | NULL | 기본값 | 제약 | 설명 |
|---|---|---|---|---|---|
| `tenant_id` | VARCHAR(64) | N | — | PK | |
| `report_id` | UUID | N | gen_random_uuid() | PK | 회차 식별자 |
| `report_year` | INTEGER | N | — | | 보고 연도 |
| `period` | VARCHAR(16) | N | — | | 회차/반기(예: `H1`) |
| `status` | VARCHAR(32) | N | 'DRAFT' | enum,CHECK | §5.31 ira_report_status 6종(DRAFT/CONFIRMED/SUBMITTED/ACKNOWLEDGED/SUBMISSION_FAILED/CANCELLED) |
| `indicator_total` | INTEGER | N | 0 | | 지표 총수 |
| `indicator_confirmed` | INTEGER | N | 0 | | 확정 지표 수(지표 확정 n/N) |
| `report_file_hash` | VARCHAR(128) | Y | NULL | | 보고파일 manifest hash(§19.4, CONFIRMED 전제) |
| `approval_id` | UUID | Y | NULL | FK→aml_approvals | 제출 4-eyes 결재(`IRA_SUBMIT`) |
| `submitted_ref` | VARCHAR(256) | Y | NULL | | 외부 제출 ref(=evidence_hash, FIU 폐루프 역참조) |
| `submitted_at` | TIMESTAMPTZ | Y | NULL | | 제출 시각 |
| `fiu_ack_ref` | VARCHAR(256) | Y | NULL | | FIU 접수번호 |
| `submission_error_code` | VARCHAR(64) | Y | NULL | | 전송 실패/FIU 반려 코드 |
| `fiu_score` | DOUBLE PRECISION | Y | NULL | | FIU 회신 점수 |
| `peer_average` | DOUBLE PRECISION | Y | NULL | | 동종 peer 평균(FIU 회신) |
| `evidence_hash` | VARCHAR(128) | Y | NULL | | 제출 manifest hash(§19.4) |
| `created_at/created_by/updated_at/updated_by/data_scope/trace_id` | (공통) | | | | |

PK: `(tenant_id, report_id)`. FK `(tenant_id)`→`aml_tenants`, `(tenant_id, approval_id)`→`aml_approvals`. 인덱스 `ix_ira_status (tenant_id, status, created_at DESC)`, UNIQUE `ux_ira_submitted (tenant_id, submitted_ref) WHERE submitted_ref IS NOT NULL`(FIU 폐루프 멱등). PII 미저장 — 지표는 집계 수치·evidence_hash 토큰만(§19.2).

상태머신: `DRAFT → CONFIRMED → SUBMITTED → ACKNOWLEDGED|SUBMISSION_FAILED`, `DRAFT|CONFIRMED → CANCELLED`. CONFIRMED는 전 마스터 지표 확정 시 자동 도출. SUBMITTED 회차는 cancel/편집 차단(FIU 폐루프 보존).

### 3.18 `aml_ira_indicators` — IRA 회차 지표값 (T1 AML-ENG-01)

회차별 지표값(자동 수집 + 수동 입력). 자동 수집(auto-collection)은 엔진 RA/TM/screening metric에서 파생(고객 위험분포·STR/CTR 건수·제재 적중률·PEP 노출 등) — bo-api 로컬 파생 아님.

| 컬럼 | 타입 | NULL | 기본값 | 제약 | 설명 |
|---|---|---|---|---|---|
| `tenant_id` | VARCHAR(64) | N | — | PK | |
| `report_id` | UUID | N | — | PK,FK→aml_ira_reports | |
| `indicator_code` | VARCHAR(64) | N | — | PK | 지표 코드(KR plugin 마스터 8종) |
| `label` | VARCHAR(128) | Y | NULL | | 표시명 |
| `unit` | VARCHAR(32) | Y | NULL | | 단위(ratio/percent/count/amount) |
| `source` | VARCHAR(16) | N | 'MANUAL' | enum,CHECK | §5.32 ira_indicator_source 2종(AUTO/MANUAL) |
| `auto_value` | DOUBLE PRECISION | Y | NULL | | 엔진 파생 자동값(AUTO) |
| `manual_value` | DOUBLE PRECISION | Y | NULL | | 수동 입력값 |
| `confirmed` | BOOLEAN | N | FALSE | | 지표 확정 여부 |
| `evidence_hash` | VARCHAR(128) | Y | NULL | | 증빙 hash 토큰(원문 미저장) |
| `note` | VARCHAR(512) | Y | NULL | | 비고 |

PK: `(tenant_id, report_id, indicator_code)`. FK `(tenant_id, report_id)`→`aml_ira_reports` ON DELETE CASCADE. 지표 마스터 8종: `CUSTOMER_RISK_DISTRIBUTION`/`HIGH_RISK_CUSTOMER_RATIO`/`STR_FILING_COUNT`/`CTR_FILING_COUNT`/`SANCTIONS_HIT_RATE`/`PEP_EXPOSURE`(AUTO 파생) · `CROSS_BORDER_VOLUME`/`TRAINING_COMPLETION`(MANUAL 전용 — 엔진 원천 부재).

### 3.19 `aml_high_risk_registry` — 당연고위험 레지스트리 헤더 (T2 AML-ENG-02, 부록 E v7.0 확정)

당연고위험 분류 정책의 tenant별 헤더(참조 리스트 변경 버전 관리). 멀티테넌시 키 `(tenant_id)` — tenant 단위 정책(workspace 차원 없음, 가정 A3). 분류 기준(criteria)은 엔진 seed 정책(read-only, 가정 A2)으로 별도 테이블 미보유 — 엔진이 코드로 보유하고 GET 응답에 read-only 파생.

| 컬럼 | 타입 | NULL | 기본값 | 제약 | 설명 |
|---|---|---|---|---|---|
| `tenant_id` | VARCHAR(64) | N | — | PK | |
| `version` | BIGINT | N | 1 | | 참조 리스트 변경 시마다 증가(결재 EXECUTED 적용 시점). subjectRef `UPDATE\|<version>` 와 일치 |
| `created_at/created_by/updated_at/updated_by` | (공통) | | | | |

PK: `(tenant_id)`. FK `(tenant_id)`→`aml_tenants`. 1 tenant = 1 row(GET 첫 접근 시 seed). PII 미저장.

### 3.20 `aml_high_risk_registry_items` — 참조 리스트 항목 (T2 AML-ENG-02)

참조 리스트(상품·VASP·고액자산가) 항목(편집 대상). 항목 일치 고객은 RA 강제 상향 재평가 대상(가정 A6·A7).

| 컬럼 | 타입 | NULL | 기본값 | 제약 | 설명 |
|---|---|---|---|---|---|
| `tenant_id` | VARCHAR(64) | N | — | PK,FK→aml_high_risk_registry | |
| `list_type` | VARCHAR(32) | N | — | PK,enum,CHECK | §5.33 reference_list_type 3종(PRODUCT/VASP/HIGH_NET_WORTH, 가정 A4) |
| `subject_ref` | VARCHAR(128) | N | — | PK | tokenized 고객/상품 식별자(원문 미저장, §19.2) |
| `tier` | VARCHAR(16) | N | — | enum,CHECK | §5.34 classification_tier 2종(HIGH/VERY_HIGH, 가정 A5) |
| `label` | VARCHAR(128) | Y | NULL | | 마스킹 표시명 |

PK: `(tenant_id, list_type, subject_ref)`. FK `(tenant_id)`→`aml_high_risk_registry` ON DELETE CASCADE. 인덱스 `ix_hrr_items_subject (tenant_id, subject_ref)`(RA 강제 상향 매칭 조회). tier→RA 강제 floor: `VERY_HIGH`→PROHIBITED, `HIGH`→HIGH(상향만 보장, 가정 A6).

### 3.21 `aml_pii_vault` — PII reveal 가역암호 vault (T3 AML-ENG-03, ADR 2026-06-15 확정, Flyway V15)

마스킹 토큰(`target_ref`)·필드별 원문의 **암호문** 역참조 저장소. reveal(`POST /internal/v1/aml/pii/reveal`, API §2.6)의 cleartext 산출 원천이다(§2.2). **평문 컬럼 0개** — `ciphertext` 만 저장(§2.2 "원문 컬럼 금지" 유지). 멀티테넌시 키 `(tenant_id, target_ref, field)` — PII reveal 은 고객 단위(workspace 차원 없음, 가정 A3).

| 컬럼 | 타입 | NULL | 기본값 | 제약 | 설명 |
|---|---|---|---|---|---|
| `tenant_id` | VARCHAR(64) | N | — | PK,FK→aml_tenants | |
| `target_ref` | VARCHAR(128) | N | — | PK | tokenized 대상 식별자(원문 미저장, §19.2) |
| `field` | VARCHAR(16) | N | — | enum,CHECK | §5.35 pii_field 4종(NAME/DOC/ACCOUNT/WALLET, §2.2 의미 패턴) |
| `ciphertext` | TEXT | N | — | | `SecretCipherPort.encrypt(원문)`(AES-256-GCM, `aws`=KMS). 평문 절대 미저장 |
| `created_at/updated_at` | TIMESTAMPTZ | N | now() | | upsert 시 갱신 |

PK: `(tenant_id, target_ref, field)`. FK `(tenant_id)`→`aml_tenants`. 인덱스 `ix_aml_pii_vault_target (tenant_id, target_ref)`(target 단위 reveal 역참조). reveal 은 복호화로 transient cleartext 산출 — 영속·로그 금지(§19.2, 가정 A6). vault 적재 시점·전 필드 확장은 후속(가정 A2).

### 3.15 지원 인프라 테이블 (도메인 14종을 떠받치는 필수 보조)

설계서 §8(canonical event), §13.5(결재·아웃박스), §15.7(idempotency), §19.3(append-only audit)이 요구하는 보조 테이블 5종(canonical_events/approvals/audit_events/evidence_exports/outbox).

#### `aml_canonical_events` — 정규화 이벤트 store (설계서 §8.2, append-only)

| 컬럼 | 타입 | NULL | 제약 | 설명 |
|---|---|---|---|---|
| `tenant_id` | VARCHAR(64) | N | PK | |
| `event_id` | VARCHAR(256) | N | PK | 원천 eventId |
| `source_system` | VARCHAR(64) | N | FK | |
| `schema_version` | VARCHAR(80) | N | | |
| `idempotency_key` | VARCHAR(256) | N | UNIQUE(tenant_id,...) | 중복 ingest 방지(§15.7) |
| `event_type` | VARCHAR(80) | N | | §8.1 event family(transaction.completed 등). **hanpass-ph 소스별 emit**: `member-svc`→customer.*/entity.*/beneficial-owner.*, `walletchg/domestic/remit/inbound-svc`→transaction.requested, `remit/wallet-svc`→settlement.posted, `wallet-svc`→account.* |
| `occurred_at` | TIMESTAMPTZ | N | | |
| `payload` | JSONB | N | | 정규화 payload(PII는 ref/hash). **corridor 주석(hanpass-ph)**: cross-border 거래(remit-svc)는 `corridor` 객체(`sendCountry`/`receiveCountry`·`sendCurrency`/`receiveCurrency` ← `remit.send_country/receive_country`·`send_currency/receive_currency`)와 USD 정규화 `amountBase`(← `remit.usd_amount/report_amount`)를 payload 에 보존. TM corridor 시나리오·대상 360°의 거래 corridor 표시 입력 |
| `payload_hash` | VARCHAR(128) | N | NOT NULL | **API 요청 DTO(`IngestEventRequest.payloadHash`)는 optional — DB는 서버 채움 NOT NULL.** 호출자가 미제공 시 aml-svc ingest 어댑터가 수신 raw payload의 sha256을 자동 계산하여 INSERT. raw_payload 원문 미저장은 §2.2 기준(설계서 §8.2 폐기 `stored` 플래그 미사용). (QA 이격 aml:db-api HIGH 정합 완료: API §3.1 `payloadHash` optional 방향 확정, DB NOT NULL 유지. QA #7 low: `stored` 참조 제거 완료) |
| `trace_id` | VARCHAR(64) | Y | | |
| `created_at/created_by` | (공통) | | | append-only |

PK: `(tenant_id, event_id)` · UNIQUE: `(tenant_id, idempotency_key)`

#### `aml_approvals` — 결재(maker-checker / 4-eyes) (설계서 §13.4~§13.5)

| 컬럼 | 타입 | NULL | 제약 | 설명 |
|---|---|---|---|---|
| `tenant_id` | VARCHAR(64) | N | PK | |
| `approval_id` | UUID | N | PK | |
| `subject_type` | VARCHAR(64) | N | enum,CHECK | §5.16 subject_type 18종: `WLF_DECISION`/`FP_WHITELIST`/`RA_MODEL`/`RISK_OVERRIDE`/`EDD_CLOSE`/`STR_SUBMIT`/`CTR_SUBMIT`/`TRAVEL_RULE_EXCEPTION`/`WATCHLIST_IMPORT`/`COUNTRY_RISK`/`POLICY_PACK`/`SECRET_CHANGE`/`RELATIONSHIP_REJECT`/`TM_SCENARIO`/`CHECKLIST_CHANGE`/`PERIODIC_REVIEW_CHANGE`/`IRA_SUBMIT`/`HIGH_RISK_REGISTRY` (§13.5). **API `ApprovalDto.subjectType` enum이 정본**(전수), DB는 이를 동기화. V09 DDL CHECK 16종 → V13 17종(`IRA_SUBMIT`) → V14 18종(`HIGH_RISK_REGISTRY`). |
| `subject_ref` | VARCHAR(256) | N | | 결재 대상 식별(case_id/report_id 등) |
| `approval_line` | VARCHAR(64) | N | enum | §5.12 approval_line(MAKER_CHECKER/AML_OFFICER/COMPLIANCE_MANAGER/REPORTING_OFFICER/SECURITY_ADMIN/EXECUTIVE_APPROVAL) |
| `status` | VARCHAR(32) | N | enum | §5.13 approval_status(DRAFT/SUBMITTED/APPROVED/REJECTED/CANCELLED/EXPIRED/EXECUTED/EXECUTION_FAILED) |
| `maker_id` | VARCHAR(128) | N | | 상신자 |
| `checker_id` | VARCHAR(128) | Y | | 승인자 (CHECK: maker_id ≠ checker_id) |
| `payload_hash` | VARCHAR(128) | N | | 결재 payload 고정 hash(§13.5: 변경 시 무효화) |
| `reason` | VARCHAR(512) | Y | | 승인/반려 사유 |
| `expires_at` | TIMESTAMPTZ | Y | | 승인 만료 |
| `executed_at` | TIMESTAMPTZ | Y | | 실행 시각(결재≠실행 분리 저장) |
| `created_at/created_by/updated_at/updated_by/trace_id` | (공통) | | | |

PK: `(tenant_id, approval_id)` · CHECK: `maker_id <> checker_id` (SELF_APPROVAL_DISABLED, §13.5)

#### `aml_audit_events` — append-only 감사 evidence (설계서 §19.3, hash chain)

| 컬럼 | 타입 | NULL | 제약 | 설명 |
|---|---|---|---|---|
| `tenant_id` | VARCHAR(64) | N | PK | |
| `audit_id` | BIGINT (IDENTITY) | N | PK | 순번 |
| `event_category` | VARCHAR(64) | N | enum | `WATCHLIST_IMPORT`/`WLF_DECISION`/`FP_WHITELIST`/`RA_MODEL_CHANGE`/`RISK_OVERRIDE`/`TM_SCENARIO_CHANGE`/`CASE_APPROVAL`/`REPORT_LIFECYCLE`/`RAW_DATA_ACCESS`/`POLICY_CHANGE` (§19.3) |
| `actor` | VARCHAR(128) | N | | 주체(운영자/AI agent/system) |
| `subject_ref` | VARCHAR(256) | Y | | 대상 |
| `detail` | JSONB | N | | 변경 전후·사유(masked) |
| `prev_hash` | VARCHAR(128) | Y | | 직전 row hash(hash chain) |
| `row_hash` | VARCHAR(128) | N | | 본 row hash |
| `trace_id` | VARCHAR(64) | Y | | |
| `created_at` | TIMESTAMPTZ | N | | append-only(수정·삭제 불가) |

PK: `(tenant_id, audit_id)`

#### `aml_evidence_exports` — 검사 대응 export 증적 (설계서 §15.6, §19.4, D-11)

| 컬럼 | 타입 | NULL | 제약 | 설명 |
|---|---|---|---|---|
| `tenant_id` | VARCHAR(64) | N | PK | |
| `export_id` | UUID | N | PK | |
| `export_type` | VARCHAR(64) | N | enum | `CDD_EDD`/`WLF_REGISTER`/`RA_REPORT`/`TM_HISTORY`/`STR_EVIDENCE`/`CTR_EVIDENCE`/`TRAVEL_RULE`/`WATCHLIST_CHANGE`/`VENDOR_CROSSREF`/`PII_ACCESS` |
| `status` | VARCHAR(32) | N | DEFAULT 'PENDING' | export 진행 상태. `PENDING`/`PROCESSING`/`COMPLETED`/`FAILED`. API `EvidenceExportResponse.status` backing 컬럼(QA #19 정합) |
| `format` | VARCHAR(16) | N | enum | `CSV`/`EXCEL`/`PDF`/`API` |
| `filter_params` | JSONB | N | | 기간/필터(재생성 query snapshot) |
| `row_count` | BIGINT | Y | | row 수 |
| `manifest_hash` | VARCHAR(128) | Y | | hash manifest(§19.4) |
| `requested_by` | VARCHAR(128) | N | | 생성자(사유 포함) |
| `reason` | VARCHAR(512) | N | DEFAULT '' | export 사유. NOT NULL(QA #20 정합 — API `EvidenceExportResponse.reason` 필수와 일치). 기존 nullable 행은 V18 백필 후 NOT NULL 강화 |
| `created_at` | TIMESTAMPTZ | N | | |

PK: `(tenant_id, export_id)`

#### `aml_outbox` — 트랜잭셔널 아웃박스 (설계서 §13.5, integration §8.1, T-16 선행)

> 결재 `EXECUTED`·report 제출·webhook callback·fds-feedback 발행을 **도메인 변경과 동일 트랜잭션**으로 기록하고 `OutboxDispatcher`가 poll→publish→mark(at-least-once + 소비자 멱등). integration §8.1 snake_case 컬럼명을 정본 채택.

| 컬럼 | 타입 | NULL | 기본값 | 제약 | 설명 |
|---|---|---|---|---|---|
| `tenant_id` | VARCHAR(64) | N | — | PK | 서비스(테넌트=서비스) 격리 키 |
| `outbox_id` | UUID | N | — | PK | 아웃박스 항목 ID |
| `data_scope` | VARCHAR(64) | Y | NULL | | 하위 격리(§1.1) |
| `aggregate_type` | VARCHAR(64) | N | — | enum | `REGULATORY_REPORT`/`CASE`/`SCREENING`/`FDS_FEEDBACK`/`WEBHOOK` (발행 집합체) |
| `aggregate_ref` | VARCHAR(256) | N | — | | 발단 집합체 식별(report_id/case_id 등) |
| `event_type` | VARCHAR(80) | N | — | | 발행 이벤트(`report.submission.requested`/`webhook.callback.requested`/`fds.feedback.applied` 등, integration §3.4) |
| `payload` | JSONB | N | '{}' | | 발행 payload(PII는 ref/hash) |
| `payload_hash` | VARCHAR(128) | N | — | | payload sha256(멱등·변조감지) |
| `status` | VARCHAR(32) | N | 'PENDING' | enum | §5.17 outbox_status(`PENDING`/`DISPATCHING`/`DISPATCHED`/`FAILED`) |
| `attempt` | INTEGER | N | 0 | | 발행 시도 횟수 |
| `next_attempt_at` | TIMESTAMPTZ | Y | NULL | | 재시도 backoff 예정(poller `SELECT ... FOR UPDATE SKIP LOCKED`) |
| `published_at` | TIMESTAMPTZ | Y | NULL | | 발행 완료 시각(DISPATCHED) |
| `trace_id` | VARCHAR(64) | Y | NULL | | 관측성 traceId 전파 |
| `created_at/created_by` | (공통, append 중심) | | | | |

PK: `(tenant_id, outbox_id)` · UNIQUE: `(tenant_id, aggregate_type, aggregate_ref, event_type, payload_hash)` (발행 멱등)

### 3.16 대상 360° 통합 뷰 (read model, 신규 — hanpass-ph 재그라운딩)

> **물리 마스터 테이블 미보유** — `tx-history-svc` 회원 통합 이력(read model) + `member-svc` CDD/screening + `wallet-svc` `transfer_links` 자금그래프를 결합한 **읽기 전용 통합 대상뷰**다. RA-003 드릴다운·CASE 타임라인·TM 알림 상세의 공통 골격이며, API `GET /api/v1/bo/aml/subjects/{customerRef}/360`(API §2.x·§3.x)·`GET /aml/customers/{customerRef}/profile`(CDD-002)의 backing 모델로 투영한다(별도 영속 테이블이 아닌 join/aggregation 산출).

| 결합 축 | 원천(hanpass-ph) | AML 매핑 | 비고 |
|---|---|---|---|
| 신원·CDD·screening | `member-svc`(`zoloz_aml_screening`) | `aml_customers`·`aml_screening_results`·`aml_risk_scores` | risk_grade·next_review_due_at·당연고위험 사유 |
| 거래 이력(360° 피드) | `tx-history-svc`(read model) | `aml_canonical_events`(transaction.*) + `aml_alerts.transaction_ref` | 충전/국내/해외 통합 타임라인·corridor |
| 자금그래프(funnel) | `wallet-svc`(`transfer_links`) | `aml_relationships`(`USES_ACCOUNT`/`REPEATED_PAYEE`) | TM 알림 `evidence.fundGraph` 미니뷰 원천 |

- 식별 키: `customer_ref`(= `member.member_id` keyed HMAC). **주의**: `member_id` 가 `domestic-svc`만 varchar(36) 이므로 통합뷰 join 시 문자열 정규화(trim·case) 필요.
- raw PII 미노출(token/hash·마스킹). STR 건수 등 tipping-off 민감 항목은 준법감시 전담 scope 한정 투영(§19.2a).

---

## 4. 인덱스 설계

| 테이블 | 인덱스 | 컬럼 | 용도 |
|---|---|---|---|
| aml_customers | `ux_customers_pk` | (tenant_id, customer_ref) | PK |
| aml_customers | `ix_customers_risk` | (tenant_id, risk_grade, next_review_due_at) | 고위험·재심사 조회(§20.2) |
| aml_customers | `ix_customers_name_hash` | (tenant_id, name_hash) | WLF 후보 매칭 |
| aml_entities | `ix_entities_name_hash` | (tenant_id, legal_name_hash) | 법인 매칭 |
| aml_entities | `ix_entities_risk` | (tenant_id, risk_grade) | 고위험 법인 |
| aml_relationships | `ix_rel_from` | (tenant_id, from_ref) | UBO graph 탐색 |
| aml_relationships | `ix_rel_to` | (tenant_id, to_ref, is_ubo) | 역방향·UBO 탐색 |
| aml_watchlist_entries | `ix_wle_source_ver` | (tenant_id, source_code, version) | import diff/적용 |
| aml_watchlist_entries | `ix_wle_name` | (tenant_id, primary_name_hash) | 매칭 인덱스 |
| aml_watchlist_entries | `gin_wle_tokens` | GIN(normalized_tokens) | fuzzy 토큰 매칭(D-02 보조) |
| aml_screening_results | `ix_scr_target` | (tenant_id, target_ref, created_at DESC) | 대상별 이력 |
| aml_screening_results | `ix_scr_status` | (tenant_id, status, created_at) | 검토 큐(POSSIBLE_MATCH) |
| aml_risk_scores | `ix_ra_target` | (tenant_id, target_ref, evaluated_at DESC) | 최신 등급 |
| aml_risk_scores | `ix_ra_grade` | (tenant_id, risk_grade, evaluated_at) | 등급 분포(§20.2) |
| aml_alerts | `ix_alert_status` | (tenant_id, status, severity, created_at) | alert backlog/triage |
| aml_alerts | `ix_alert_target` | (tenant_id, target_ref) | 대상별 |
| aml_cases | `ix_case_status` | (tenant_id, status, due_at) | SLA·작업 큐 |
| aml_cases | `ix_case_type` | (tenant_id, case_type, status) | 유형별 |
| aml_cases | `ix_case_assignee` | (tenant_id, assigned_to, status) | 담당자별 |
| aml_regulatory_reports | `ix_report_type` | (tenant_id, report_type, status, created_at) | 기간별 제출 조회 |
| aml_canonical_events | `ux_event_idem` | UNIQUE(tenant_id, idempotency_key) | 중복 ingest 차단 |
| aml_canonical_events | `ix_event_type_time` | (tenant_id, event_type, occurred_at) | TM 윈도우 집계 |
| aml_approvals | `ix_appr_status` | (tenant_id, status, subject_type) | 결재 대기 큐 |
| aml_audit_events | `ix_audit_cat` | (tenant_id, event_category, created_at) | 감사 조회 |
| aml_alerts | `ix_alert_ext_ref` | (tenant_id, external_alert_ref) WHERE external_alert_ref IS NOT NULL | vendor dual-run cross-ref 역조회 |
| aml_business_documents | `ix_bizdoc_tx` | (tenant_id, transaction_ref) | 거래-증빙 정합(TBML) |
| aml_travel_rule_transfers | `ix_trt_risk` | (tenant_id, risk_status, completeness_status) | exception 큐 |
| aml_outbox | `ux_outbox_idem` | UNIQUE(tenant_id, aggregate_type, aggregate_ref, event_type, payload_hash) | 발행 멱등 |
| aml_outbox | `ix_outbox_dispatch` | (tenant_id, status, next_attempt_at) | poller 발행 큐(PENDING/FAILED 재시도) |

---

## 5. enum 코드·표시값 정의 (코드 ↔ 표시 병기)

> 컬럼 저장은 코드값. 표시값은 bo-web i18n 매핑.

### 5.28 deployment_model / onboarding_status / status (`aml_tenants`, §3.1, 정본 §4.1)

> **구 `isolation_mode` enum(`SHARED`/`SCHEMA`/`DB`) 폐기**. 아래 3 enum이 대체. FDS `fds_tenants` enum(§4.1 / §4.1a)과 코드값·종수 100% 동기화.

#### §5.28 deployment_model (3종) — 배포 유형

| 코드값 | 표시값 | 의미 | 프로비저닝 |
|---|---|---|---|
| `MANAGED_DEDICATED` | 매니지드 전용 | 플랫폼 클라우드에 **서비스별 전용 DB·스택** | 온보딩 IaC(Terraform) 자동 파이프라인 — 승인→프로비저닝→배포→검증→운영전환 |
| `SELF_HOSTED` | 자체 인프라 설치형 | **고객 자체 인프라**에 설치형 패키지(Helm/Docker) | 플랫폼은 설치 패키지·가이드·라이선스 제공, 고객 측이 배포·등록 콜백 |
| `SHARED` | 소규모 공유 | 공유 DB + `tenant_id` 행 격리 | 즉시(프로비저닝 없음) |

#### §5.28a onboarding_status (8종) — 온보딩 진행 상태 (운영 생명주기 `status`와 직교)

| 코드값 | 표시값 | 적용 경로 |
|---|---|---|
| `REQUESTED` | 신청 | 전 경로 시작 |
| `PROVISIONING` | 프로비저닝중 | `MANAGED_DEDICATED` |
| `DEPLOYED` | 배포완료 | `MANAGED_DEDICATED` |
| `VERIFIED` | 검증완료 | `MANAGED_DEDICATED` |
| `ACTIVE` | 운영전환 | `MANAGED_DEDICATED`, `SHARED` |
| `PACKAGE_ISSUED` | 패키지발급 | `SELF_HOSTED` |
| `CUSTOMER_DEPLOYED` | 고객배포완료 | `SELF_HOSTED` |
| `REGISTERED` | 등록완료 | `SELF_HOSTED` |

```mermaid
stateDiagram-v2
    [*] --> REQUESTED
    state "MANAGED_DEDICATED" as M {
        REQUESTED --> PROVISIONING
        PROVISIONING --> DEPLOYED
        DEPLOYED --> VERIFIED
        VERIFIED --> ACTIVE
    }
    state "SELF_HOSTED" as S {
        REQUESTED --> PACKAGE_ISSUED
        PACKAGE_ISSUED --> CUSTOMER_DEPLOYED
        CUSTOMER_DEPLOYED --> REGISTERED
    }
    REQUESTED --> ACTIVE : SHARED 즉시
    ACTIVE --> [*]
    REGISTERED --> [*]
```

- 온보딩이 `ACTIVE` 또는 `REGISTERED`에 도달하면 `aml_tenants.status`를 `ACTIVE`로 전환한다.
- 표시 라벨(특히 `CUSTOMER_DEPLOYED` '고객배포완료')의 최종 정본은 bo-web i18n 키로 일원화(오픈결정).

#### §5.28b status (**4종**, FDS §11.6.7 동기화) — 운영 생명주기 (`onboarding_status`와 직교)

> **QA cross #119 high 정합**: FDS `fds_tenants.tenant_status`(ONBOARDING/ACTIVE/SUSPENDED/OFFBOARDED 4종)와 코드값·종수 동기화. 구 3종(`ACTIVE`/`SUSPENDED`/`OFFBOARDING`) 폐기. `ONBOARDING` 추가(온보딩 진행 중 상태), `OFFBOARDING`→`OFFBOARDED` 교정(해지 완료 상태. 진행 중 상태는 `onboarding_status` 축이 담당). DEFAULT `'ACTIVE'` → `'ONBOARDING'` 변경(신규 등록 직후 초기 상태). 설계서 §16.0c도 이 4종으로 동기화 대상.

| 코드값 | 표시값 | 비고 |
|---|---|---|
| `ONBOARDING` | 온보딩중 | 신규 등록·온보딩 진행 (DEFAULT) |
| `ACTIVE` | 활성 | 온보딩 완료·운영 중 |
| `SUSPENDED` | 정지 | 일시 정지 |
| `OFFBOARDED` | 해지완료 | 해지·데이터 반출·파기 진행 완료 |

---

### 5.1 customer_type / entity_type (설계서 §9.1)
| 코드 | 표시 | 대상 |
|---|---|---|
| `PERSON` | 개인 | customer |
| `SOLE_PROPRIETOR` | 개인사업자 | customer |
| `LEGAL_ENTITY` | 법인 | entity |
| `MERCHANT` | 가맹점 | entity |
| `SELLER` | 셀러 | entity |
| `VASP_CUSTOMER` | 거래소 회원 | customer/entity |
| `EMPLOYEE` | 내부 직원 | customer |
| `VENDOR` | 공급업체 | entity |

### 5.2 risk_grade (설계서 §11.2)
`LOW`(낮음) / `MEDIUM`(중간) / `HIGH`(높음) / `PROHIBITED`(거래금지)

### 5.3 relationship_type (설계서 §7.2)
`OWNS`(소유) / `CONTROLS`(지배) / `REPRESENTS`(대표/대리) / `OPERATES`(운영) / `USES_ACCOUNT`(계좌사용) / `PAYS_TO`(반복수취) / `RELATED_TO`(관련) / `EMPLOYED_BY`(고용)

### 5.4 watchlist_source_type (설계서 §10.1)
`SANCTIONS`(제재) / `PEP`(정치인) / `RCA`(PEP관련자) / `ADVERSE_MEDIA`(부정뉴스) / `INTERNAL`(내부블랙) / `LAW_ENFORCEMENT`(수사기관) / `VASP_RISK`(가상자산위험)

### 5.5 screening_status (설계서 §10.4)
`NO_MATCH`(매칭없음) / `POSSIBLE_MATCH`(검토필요) / `TRUE_MATCH`(확정) / `FALSE_POSITIVE`(오탐) / `AUTO_DISCOUNTED`(자동낮춤) / `ESCALATED`(상위승인)

> 실시간 API 응답값 `POTENTIAL_MATCH`(§15.7)는 `POSSIBLE_MATCH`와 동일 의미의 API 별칭. 저장값은 `POSSIBLE_MATCH`로 정규화.

### 5.6 tm_scenario (설계서 §12.1)
`STRUCTURING` / `RAPID_MOVEMENT` / `MULE_NETWORK` / `HIGH_RISK_CORRIDOR` / `SHELL_MERCHANT` / `REFUND_LAUNDERING` / `TRADE_MISPRICING` / `ROUND_TRIPPING` / `CRYPTO_OFF_RAMP` / `INTERNAL_OVERRIDE_ABUSE`

### 5.7 alert_status (설계서 §12.2 → §13 case 인계)
`DETECTED` → `TRIAGED` → `CASE_OPENED` → (`DISMISSED` | `ESCALATED` | `STR_RECOMMENDED`)

> **alert_status는 6종으로 종결**(`DETECTED`/`TRIAGED`/`CASE_OPENED`/`DISMISSED`/`ESCALATED`/`STR_RECOMMENDED`)하며 **DB가 물리 정본**(CHECK 6종). 설계서 §12.2 alert lifecycle 후반 전이로 거론되는 `INVESTIGATING`/`REPORTED`/`CLOSED`는 **alert가 아니라 case 단계**의 상태로, `CASE_OPENED`(또는 `STR_RECOMMENDED`)에서 `aml_cases`가 개설된 이후 `case_status`(§5.9 `INVESTIGATING`/…/`REPORTED`/`CLOSED`)가 담당한다. 즉 alert는 case 인계 시점에 6종 종결값(`CASE_OPENED`/`DISMISSED`/`ESCALATED`/`STR_RECOMMENDED`)에 멈추고, 이후 조사·보고·종결 라이프사이클은 `aml_cases.status`로 영속된다. 설계서 §12.2를 'alert 6종 + 이후는 case_status 인계'로 1:1 정합(파생→정본 역삽입 권고). `INVESTIGATING`/`REPORTED`/`CLOSED`는 alert enum에 추가하지 않는다(`aml_alerts.status` CHECK 위반).

### 5.8 case_type (설계서 §13.3 + §18 도메인 확장)
`SANCTIONS_REVIEW` / `PEP_REVIEW` / `EDD_REVIEW` / `STR_REVIEW` / `CTR_REVIEW` / `TBML_REVIEW` / `VASP_TRAVEL_RULE_REVIEW` / `MERCHANT_AML_REVIEW` / `INTERNAL_CONTROL_REVIEW` / `MULE_ACCOUNT_REVIEW` / `B2B_INVOICE_REVIEW` / `ECOMMERCE_SETTLEMENT_REVIEW`

### 5.9 case_status (설계서 §13.3a, §13)
`OPEN` / `INVESTIGATING` / `PENDING_APPROVAL` / `DISMISSED` / `REPORTED` / `CLOSED`

> **case_status 정본 출처는 설계서 §13.3a**(case 라이프사이클). §12.2는 alert lifecycle(§5.7)이므로 인용에서 분리한다. alert(§5.7)에서 거론되는 `INVESTIGATING`/`REPORTED`/`CLOSED`는 alert가 아니라 본 case_status가 보유·영속하는 상태다(§5.7 인계 주석 참조). DB가 case_status 물리 정본이며 6종을 설계서 §13.3a에 1:1 정합.

### 5.10 report_type (설계서 §14.1)
`STR` / `CTR` / `TRAVEL_RULE` / `EDD_REGISTER` / `WLF_REGISTER` / `RA_REPORT` / `AUDIT_EXPORT`

### 5.11 report_status (설계서 §13.5, §14.1a)
`DRAFT` / `UNDER_REVIEW` / `APPROVED` / `SUBMITTED` / `ACKNOWLEDGED` / `SUBMISSION_FAILED` / `REJECTED` / `CANCELLED` (8종)

> **FIU 회신 폐루프(설계서 §14.1a 정본).** `SUBMITTED`(전송 완료·회신 대기) → `ACKNOWLEDGED`(FIU 접수, `fiu_ack_ref` 저장, 종단) | `SUBMISSION_FAILED`(전송 실패/FIU 오류 반려, `submission_error_code` 저장). `SUBMISSION_FAILED → UNDER_REVIEW`(정정 후 재제출 RESUBMIT — 기존 `:submit` 4-eyes 재사용, `resubmit_count` 증가). 기각·취소(`REJECTED`/`CANCELLED`) 전이는 사유 코드 필수 + 보고책임자 결재(4-eyes, 자기승인 금지). CTR 제외 처리는 `CANCELLED` + `ctr_exemption_code`로 기록.

### 5.12 approval_line (설계서 §13.5)
`MAKER_CHECKER` / `AML_OFFICER` / `COMPLIANCE_MANAGER` / `REPORTING_OFFICER` / `SECURITY_ADMIN` / `EXECUTIVE_APPROVAL` (+ `SELF_APPROVAL_DISABLED` 불변식은 CHECK 제약으로 강제)

### 5.13 approval_status (설계서 §13.5)
`DRAFT` → `SUBMITTED` → (`APPROVED` | `REJECTED` | `CANCELLED` | `EXPIRED`) → (`EXECUTED` | `EXECUTION_FAILED`)

### 5.14 ingest_mode (설계서 §15)
`REST_PUSH` / `QUEUE` / `POLLING` / `CDC` / `SNAPSHOT` / `VENDOR_BRIDGE`

### 5.15 risk_status — Travel Rule 위험 (설계서 §14.1, §18.4)
`CLEAR`(정상) / `SANCTIONED_ADDRESS`(제재주소) / `MIXER_EXPOSURE`(믹서노출) / `HIGH_RISK`(고위험)

> **DB가 정본 enum**(CHECK 4종). integration §4.3/§9.3 payload의 `REVIEW`는 본 enum에 없으므로 `HIGH_RISK`로 정규화 매핑한다(exception 큐 트리거는 `risk_status IN (HIGH_RISK, SANCTIONED_ADDRESS, MIXER_EXPOSURE)` 또는 `completeness_status=INCOMPLETE`). integration의 `REVIEW` 표기는 본 enum 4종으로 교정 대상.

### 5.16 subject_type — 결재 대상 (설계서 §13.5) — **18종(확정)**

| 코드값 | 표시값 | 결재 트리거 |
|---|---|---|
| `WLF_DECISION` | WLF 판정 | WLF true-match 확정·FP 화이트리스트 변경 |
| `FP_WHITELIST` | FP 화이트리스트 | FP 화이트리스트 등록/삭제 |
| `RA_MODEL` | RA 모델 변경 | RA 모델·임계값 활성화 |
| `RISK_OVERRIDE` | 위험 등급 수동조정 | risk_grade 수동 override |
| `EDD_CLOSE` | EDD 종결 | EDD 케이스 종결 승인 |
| `STR_SUBMIT` | STR 제출 | 의심거래보고 제출 |
| `CTR_SUBMIT` | CTR 제출 | 고액현금거래보고 제출 |
| `TRAVEL_RULE_EXCEPTION` | Travel Rule 예외 | 예외 사유 확정 승인 |
| `WATCHLIST_IMPORT` | 명단 임포트 | 워치리스트 신규 버전 적용 |
| `COUNTRY_RISK` | 국가위험 변경 | 고위험국 분류 변경 |
| `POLICY_PACK` | Policy Pack 변경 | KR_DEFAULT 등 Policy Pack 활성화 |
| `SECRET_CHANGE` | 시크릿 변경 | API key/auth_mode 변경 |
| `RELATIONSHIP_REJECT` | 관계 거절 | UBO·관계인 등록 거절 |
| `TM_SCENARIO` | TM 시나리오 변경 | TM 시나리오 활성화(`tm-scenarios/{code}:activate`, 4-eyes) |
| `CHECKLIST_CHANGE` | CDD 체크리스트 변경 | CDD checklist 항목 변경·상신(§13.4 CDD, T-12). **API 정본 코드값** — 구 `CDD_CHECKLIST`는 비정본이므로 사용 금지 |
| `PERIODIC_REVIEW_CHANGE` | 주기적 재확인 변경 | periodic review 기준·주기 변경(§11.2 재심사) |
| `IRA_SUBMIT` | 기관위험평가 제출/취소 | IRA(기관위험평가, ML/TF) 회차 보고파일 제출·취소(부록 E v6.0-2, T1 AML-ENG-01). `SUBMIT`\|`reportId` / `CANCEL`\|`reportId` subjectRef 접두로 분기 |
| `HIGH_RISK_REGISTRY` | 당연고위험 레지스트리 변경 | 당연고위험 참조 리스트(상품·VASP·고액자산가) 변경 상신(부록 E v7.0, T2 AML-ENG-02). `UPDATE`\|`<version>` subjectRef, 전체 staged payload drift guard. 결재 EXECUTED 시 적용 + 일치 고객 RA 강제 상향 재평가 트리거 |

> **HIGH_RISK_REGISTRY 추가(17→18종, 확정)**: T2(AML-ENG-02)로 aml-svc 엔진에 당연고위험 레지스트리(HRR) admin surface 정식 구축(부록 E v7.0 "제안 상태" → "확정"). scope `aml:admin:high-risk-registry`(가정 A1). 분류 기준(criteria)은 read-only seed(가정 A2), PUT 변경 대상은 참조 리스트로 한정. `HIGH_RISK_REGISTRY` 단일 subjectType이 참조 리스트 변경을 `UPDATE|<version>` subjectRef + 전체 staged payload self-consistency drift guard(PERIODIC_REVIEW_CHANGE/SECRET_CHANGE 군)로 커버. maker≠checker 일관. 적용은 결재 EXECUTED 시점이며 이때 일치 고객을 엔진 RA가 강제 상향 재평가(VERY_HIGH→PROHIBITED·HIGH→HIGH floor, 상향만 보장, 가정 A6·A7). V14 `aml_approvals.subject_type` CHECK 18종으로 갱신(V3 인라인 + V13 명명 CHECK 양쪽 DROP 후 18종 단일 제약 통합).
> **IRA_SUBMIT 추가(16→17종, 확정)**: T1(AML-ENG-01)로 aml-svc 엔진에 IRA admin surface 정식 구축(부록 E v6.0-2 "제안 상태" → "확정"). `IRA_SUBMIT` 단일 subjectType이 submit·cancel 양 액션을 `subjectRef` 접두(`SUBMIT|`/`CANCEL|`)로 커버(STR_SUBMIT 패턴 차용). maker≠checker·payload drift guard 일관(submit 라인은 live 지표 재파생, cancel 라인은 staged self-consistency). V13 `aml_approvals.subject_type` CHECK 17종으로 갱신.
> **API `ApprovalDto.subjectType` enum이 정본(전수)**, DB `aml_approvals.subject_type`은 이를 동기화한다. `TM_SCENARIO`는 TM 시나리오 활성화 결재 대상으로 추가(API §3.7·PRD §11.1 동기화). `CHECKLIST_CHANGE`(구 `CDD_CHECKLIST` — QA 이격 aml:db-api HIGH 해소: API 정본 코드값으로 교정)·`PERIODIC_REVIEW_CHANGE`는 T-12 결재 상신 API 계약(`PUT .../cdd/checklists/{id}`, API §10) 착수 전 필수. API §3.7 ApprovalDto·§10 등재표도 본 16종(`CHECKLIST_CHANGE` 포함)으로 동기화해야 한다. V09 `aml_approvals.subject_type` DDL CHECK 제약도 16종 기준(`CHECKLIST_CHANGE` 포함)으로 갱신.

### 5.17 outbox_status (integration §8.1)
`PENDING`(대기) / `DISPATCHING`(발행중) / `DISPATCHED`(발행완료) / `FAILED`(실패·재시도)

### 5.30 evidence_export_status (`aml_evidence_exports.status`, QA #19)
`PENDING`(대기) / `PROCESSING`(생성중) / `COMPLETED`(완료) / `FAILED`(실패)

> API `EvidenceExportResponse.status` 필드의 backing enum. DB가 물리 정본.

### 5.31 ira_report_status (`aml_ira_reports.status`, T1 AML-ENG-01, 부록 E v6.0-2)
`DRAFT`(작성중) / `CONFIRMED`(지표 확정 N/N) / `SUBMITTED`(제출·FIU 회신 대기) / `ACKNOWLEDGED`(FIU 접수, fiu_score·peer_average 회신) / `SUBMISSION_FAILED`(전송 실패/FIU 반려) / `CANCELLED`(취소)

> 상태머신 `DRAFT→CONFIRMED→SUBMITTED→ACKNOWLEDGED|SUBMISSION_FAILED`, `DRAFT|CONFIRMED→CANCELLED`. DB가 물리 정본(CHECK 6종, V13). 도메인 enum `IraReportStatus`와 1:1.

### 5.32 ira_indicator_source (`aml_ira_indicators.source`, T1 AML-ENG-01)
`AUTO`(엔진 RA/TM/screening metric 파생) / `MANUAL`(수동 입력 — CROSS_BORDER_VOLUME·TRAINING_COMPLETION 등 엔진 원천 부재 지표)

### 5.33 reference_list_type (`aml_high_risk_registry_items.list_type`, T2 AML-ENG-02, 부록 E v7.0)
`PRODUCT`(당연고위험 상품군) / `VASP`(가상자산사업자) / `HIGH_NET_WORTH`(고액자산가)

> DB가 물리 정본(CHECK 3종, V14). 도메인 enum `ReferenceListType`·bo-api 계약(가정 A4)과 1:1.

### 5.34 classification_tier (`aml_high_risk_registry_items.tier`, T2 AML-ENG-02, 부록 E v7.0)
`HIGH`(당연고위험) / `VERY_HIGH`(당연초고위험)

> DB가 물리 정본(CHECK 2종, V14). 도메인 enum `ClassificationTier`와 1:1. tier→RA 강제 floor: `VERY_HIGH`→PROHIBITED·`HIGH`→HIGH(상향만 보장, 가정 A6).

### 5.35 pii_field (`aml_pii_vault.field`, T3 AML-ENG-03, ADR 2026-06-15)
`NAME`(이름) / `DOC`(신분증·문서번호) / `ACCOUNT`(계좌) / `WALLET`(지갑주소)

> DB가 물리 정본(CHECK 4종, V15). 도메인 enum `PiiField`와 1:1. §2.2 hash 의미 패턴(이름/문서번호/계좌/지갑주소)과 정합. reveal vault(§3.21) 키의 일부.

> DB가 물리 정본(CHECK 2종, V13). 도메인 enum `IraIndicatorSource`와 1:1.

### 5.18 alert_type (설계서 §12, `aml_alerts.alert_type`)
| 코드 | 표시 | 비고 |
|---|---|---|
| `TM_SCENARIO` | 거래모니터링 시나리오 | TM 룰 경보 |
| `SCREENING` | WLF/제재 스크리닝 | screening 발단 alert |
| `RA` | 위험평가 | risk 등급 변동 alert |
| `FDS_ESCALATION` | FDS 에스컬레이션 | fds-svc 위임 발단(`source_origin=FDS`) |
| `VENDOR_ALERT` | 외부 벤더 경보 | Legacy Vendor Bridge(`source_origin=VENDOR`) |

> **API `TransactionEvaluateResponse.alertType` enum이 정본(전수)**, DB `aml_alerts.alert_type`은 이를 동기화(OpenAPI enum 제약 적용 권고).

### 5.19 alert_severity (설계서 §12, `aml_alerts.severity`)
`LOW`(낮음) / `MEDIUM`(중간) / `HIGH`(높음) / `CRITICAL`(심각)

### 5.20 source_origin (설계서 §15.5 dual-run, `aml_alerts.source_origin`)
`AML`(SaaS 엔진) / `FDS`(fds-svc 위임) / `VENDOR`(Legacy Vendor Bridge)

> AML/FDS/VENDOR dual-run 산출 alert를 구분 영속화(integration §7.3). `VENDOR`일 때 `external_alert_ref` 채움.

### 5.21 document_type (설계서 §7.3, `aml_business_documents.document_type`)
| 코드 | 표시 |
|---|---|
| `INVOICE` | 인보이스 |
| `PO` | 발주서(Purchase Order) |
| `BL` | 선하증권(Bill of Lading) |
| `CUSTOMS` | 통관서류 |
| `ORDER` | 주문서 |
| `SETTLEMENT` | 정산명세 |

> §3.13 컬럼·설계서 §7.3 값 집합과 1:1. TBML(§18.5) 증빙 분류 정본.

### 5.22 completeness_status — Travel Rule 정보완전성 (설계서 §14.1·§18.4, `aml_travel_rule_transfers.completeness_status`)
| 코드 | 표시 |
|---|---|
| `COMPLETE` | 완전(송수신 정보 충족) |
| `MISSING_ORIGINATOR` | 송신정보 누락 |
| `MISSING_BENEFICIARY` | 수신정보 누락 |
| `INCOMPLETE` | 불완전(부분 누락) |

> §5.15 risk_status와 동급 enum. exception 큐 트리거는 `completeness_status=INCOMPLETE` 또는 `risk_status IN (HIGH_RISK, SANCTIONED_ADDRESS, MIXER_EXPOSURE)`(§3.14, §5.15).

### 5.23 target_type — screening/risk 대상 축 (`aml_screening_results.target_type`, `aml_risk_scores.target_type`)
| 코드 | 표시 | 적용 |
|---|---|---|
| `CUSTOMER` | 고객 | screening·risk |
| `ENTITY` | 법인 | screening·risk |
| `COUNTERPARTY` | 거래상대방 | screening |
| `CRYPTO_ADDRESS` | 지갑주소 | screening |

> risk_scores.target_type은 `CUSTOMER`/`ENTITY` 2종만 사용. subject_kind(§5.24, watchlist entry 주체 분류)와는 축이 다르다(대상 vs 명단주체).

### 5.24 subject_kind — watchlist entry 주체 (설계서 §10.2, `aml_watchlist_entries.subject_kind`)
`PERSON`(개인) / `ENTITY`(법인) / `VESSEL`(선박) / `CRYPTO_ADDRESS`(지갑주소)

### 5.25 kyc_status (설계서 §13.1 CDD, `aml_customers.kyc_status`)
`PENDING`(대기) / `VERIFIED`(검증완료) / `INCOMPLETE`(미비) / `EXPIRED`(만료) / `REJECTED`(반려)

> **DB가 물리 정본으로 신규 도입**한 enum. 설계서 §13.1 CDD에 5종 코드값 (case_status처럼) 파생→정본 역삽입 권고.

### 5.26 required_action — RA 후속조치 (설계서 §11.2, `aml_risk_scores.required_action`)
`CDD_UPDATE`(CDD 갱신) / `EDD`(강화실사) / `RELATIONSHIP_REVIEW`(관계 재검토) / `NONE`(없음)

### 5.27 priority — case 우선순위 (`aml_cases.priority`)
`LOW`(낮음) / `MEDIUM`(중간) / `HIGH`(높음) / `URGENT`(긴급)

### 5.29 edd_trigger — EDD 강화실사 발동 사유 (설계서 §13.2, `aml_cases.edd_trigger`)

| 코드값 | 표시값 | 설명(설계서 §13.2) |
|---|---|---|
| `WLF_TRUE_MATCH` | WLF 확정 매칭 | 제재·PEP·adverse media 확정 매칭 |
| `HIGH_RA_SCORE` | 고위험 RA 점수 | 고객위험평가 HIGH 등급 산출 |
| `HIGH_RISK_COUNTRY` | 고위험 국가 | 고위험 국가 관련 거래·관계 |
| `UNUSUAL_TRANSACTION` | 이상 거래 | TM alert 상위 위험 발동 |
| `COMPLEX_OWNERSHIP` | 복잡한 소유구조 | UBO 불명확·복잡한 법인 구조 |
| `TRADE_MISMATCH` | 무역 불일치 | 무역 증빙 불일치(TBML 징후) |
| `CRYPTO_RISK` | 가상자산 위험 | mixer 노출·제재주소·Travel Rule 정보 누락 |
| `INTERNAL_OVERRIDE` | 내부 승인 우회 | 내부 승인 우회·내부통제 예외 |

> **DB가 edd_trigger 물리 정본(§3.11 컬럼 참조)**. 설계서 §13.2 Trigger 표를 SCREAMING_SNAKE_CASE 코드값으로 확정한 enum이다. `aml_cases.edd_trigger` 컬럼의 허용값은 본 8종이다. QA 이격(aml:db-api LOW) 해소 — 설계서 §13.2 및 API §3.5 CaseDto `eddTrigger` 필드에도 본 8종 코드값 목록을 반영해야 한다.

---

## 6. 보존·파기 정책 (설계서 §16.3, §19)

| retention_class | 적용 테이블 | 기본 보존 | 파기 방식 |
|---|---|---|---|
| `REGULATORY_LONG` | aml_regulatory_reports, aml_audit_events, aml_evidence_exports | 최소 5년+ (특정금융정보법 기준, tenant override) | 보존기간 경과 후 archive→파기, audit는 영구 chain |
| `CASE_EVIDENCE` | aml_cases, aml_screening_results, aml_risk_scores, aml_alerts | 5년 | tenant policy 기준 파기 |
| `IDENTITY` | aml_customers, aml_entities, aml_relationships | 거래종료+법정기간 | offboarding 시 hash/token 유지·식별정보 파기 |
| `EVENT_RAW` | aml_canonical_events | TM 윈도우 + 감사기간(예 1~2년) | 만료 후 집계 보존·원본 파기 |
| `WATCHLIST` | aml_watchlist_sources/entries | active+직전 버전 + 변경이력 | delisted 버전 archive |
| `TRANSIENT` | aml_outbox | DISPATCHED 후 단기(예 7~30일) | 발행 완료·감사 evidence 이관 후 purge(발행 사실은 aml_audit_events 보존) |

- raw PII는 §2.2에 따라 애초에 미저장(hash/token만). 파기는 token 매핑 폐기로 갈음.
- 보존정책은 `aml_tenants.retention_policy` JSONB로 tenant별 override.
- **법정 수치 정본(설계서 §19.3)**: STR/CTR 보고기록·고객확인(CDD) 기록·의심거래 관련 자료 = **5년**(특정금융정보법 제5조의4), 감사로그(`aml_audit_events`) = **7년**(`REGULATORY_LONG` 7년 override, hash chain 영구).

---

## 7. 마이그레이션 순서 (Flyway, additive)

스키마: `aml`. 파일 위치: `services/aml-svc/src/main/resources/db/migration/`. 버전 의존(FK·인덱스) 순서로 분할.

| 버전 | 파일 | 내용 | 의존 |
|---|---|---|---|
| V01 | `V01__aml_schema_and_tenant.sql` | `CREATE SCHEMA aml`; aml_tenants, aml_source_systems; RLS 정책·`app.current_tenant` | — |
| V02 | `V02__aml_identity.sql` | aml_customers, aml_entities, aml_relationships + 인덱스 | V01 |
| V03 | `V03__aml_watchlist.sql` | aml_watchlist_sources, aml_watchlist_entries (+GIN) | V01 |
| V04 | `V04__aml_screening.sql` | aml_screening_results | V02,V03 |
| V05 | `V05__aml_risk.sql` | aml_risk_scores | V02 |
| V06 | `V06__aml_events.sql` | aml_canonical_events (idempotency UNIQUE) | V01,V02 |
| V07 | `V07__aml_tm_alerts.sql` | aml_alerts (status CHECK 6종 §5.7, alert_type/severity/source_origin CHECK §5.18~§5.20) | V02,V06 |
| V08 | `V08__aml_cases.sql` | aml_cases (FK→alerts/screening, status CHECK 6종 §5.9, case_type CHECK §5.8, priority CHECK §5.27) | V04,V07 |
| V09 | `V09__aml_approvals.sql` | aml_approvals (CHECK maker≠checker; `subject_type` CHECK 16종: WLF_DECISION/FP_WHITELIST/RA_MODEL/RISK_OVERRIDE/EDD_CLOSE/STR_SUBMIT/CTR_SUBMIT/TRAVEL_RULE_EXCEPTION/WATCHLIST_IMPORT/COUNTRY_RISK/POLICY_PACK/SECRET_CHANGE/RELATIONSHIP_REJECT/TM_SCENARIO/CHECKLIST_CHANGE/PERIODIC_REVIEW_CHANGE) | V01 |
| V10 | `V10__aml_reports.sql` | aml_regulatory_reports (FK→cases/approvals) | V08,V09 |
| V11 | `V11__aml_business_docs.sql` | aml_business_documents | V02 |
| V12 | `V12__aml_travel_rule.sql` | aml_travel_rule_transfers | V02 |
| V13 | `V13__aml_audit.sql` | aml_audit_events (append-only, hash chain) | V01 |
| V14 | `V14__aml_evidence_export.sql` | aml_evidence_exports | V01 |
| V15 | `V15__aml_retention_and_rls.sql` | retention_policy seed, RLS 전 테이블 적용, KR_DEFAULT policy pack seed | V01~V14 |
| V16 | `V16__aml_outbox.sql` | aml_outbox(status enum, 발행 멱등 UNIQUE) + `ix_outbox_dispatch`·`ux_outbox_idem`; RLS 적용. T-16 아웃박스 poller 선행 | V01,V10 |
| V17a | `V17a__aml_tenant_deployment_model.sql` | `aml_tenants`에 `deployment_model VARCHAR(32) NOT NULL DEFAULT 'MANAGED_DEDICATED'`, `onboarding_status VARCHAR(32) NOT NULL DEFAULT 'REQUESTED'`, `infra_ref VARCHAR(160)` 컬럼 추가. 기존 row 백필: `isolation_mode='SHARED'` → `deployment_model='SHARED', onboarding_status='ACTIVE'`; `isolation_mode IN ('SCHEMA','DB')` → `deployment_model='MANAGED_DEDICATED', onboarding_status='ACTIVE'`. `default_region` 기본값 `'kr'` → `'KR'` 정규화 UPDATE. 구 `isolation_mode` 컬럼은 V17b에서 DROP(additive-then-drop 2단 분리 권장). | V01 |
| V17b | `V17b__aml_tenant_drop_isolation_mode.sql` | `aml_tenants.isolation_mode` 컬럼 DROP(V17a 백필 검증 후 적용). | V17a |
| V18 | `V18__aml_evidence_export_status.sql` | `aml_evidence_exports`에 `status VARCHAR(32) NOT NULL DEFAULT 'PENDING'` 컬럼 추가(QA #19); `reason VARCHAR(512)` nullable→`NOT NULL DEFAULT ''` 강화(QA #20): ① `UPDATE aml.aml_evidence_exports SET reason='' WHERE reason IS NULL`, ② `ALTER TABLE aml.aml_evidence_exports ALTER COLUMN reason SET NOT NULL`. | V14 |
| V19 | `V19__aml_report_submission_loop.sql` | `aml_regulatory_reports`에 FIU 회신 폐루프 컬럼 추가(설계서 §14.1a/§14.3): `fiu_ack_ref VARCHAR(256)`, `submission_error_code VARCHAR(64)`, `resubmit_count INT NOT NULL DEFAULT 0`, `ctr_exemption_code VARCHAR(64)`. `status` CHECK를 8종(`ACKNOWLEDGED`/`SUBMISSION_FAILED` 추가, §5.11)으로 확장. | V10 |
| V20 | `V20__aml_source_systems_status_and_tenant_status.sql` | (1) `aml_source_systems`에 `status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE'` 컬럼 추가 + `data_scope VARCHAR(64)` 컬럼 추가(§3.2 QA #4 HIGH·#5 MEDIUM 정합). (2) `aml_tenants.status` CHECK 제약을 **4종**(`ONBOARDING`/`ACTIVE`/`SUSPENDED`/`OFFBOARDED`)으로 갱신 + DEFAULT `'ACTIVE'` → `'ONBOARDING'` 변경(QA cross #119 HIGH·#127 MEDIUM): ① `ALTER TABLE aml.aml_tenants ALTER COLUMN status SET DEFAULT 'ONBOARDING'`; ② 기존 row 중 `onboarding_status NOT IN ('ACTIVE','REGISTERED')` → `status='ONBOARDING'` 백필(신규 등록 미완 서비스); ③ `OFFBOARDING` → `OFFBOARDED` 데이터 마이그레이션. CHECK 제약 DROP→재생성(4종 포함). | V01,V17a |
| IRA(구현 `V13__phase_ira_surface.sql`) | `V13__phase_ira_surface.sql` | **T1 AML-ENG-01**: (1) `aml_ira_reports` 생성(§3.17, status CHECK 6종, FK→aml_tenants/aml_approvals, `ix_ira_status`·`ux_ira_submitted`). (2) `aml_ira_indicators` 생성(§3.18, source CHECK 2종, FK→aml_ira_reports ON DELETE CASCADE). (3) `aml_approvals.subject_type` CHECK **16→17종**(`IRA_SUBMIT` 추가, §5.16). (4) `aml_outbox.aggregate_type` CHECK에 `IRA_REPORT` 추가(§3.15 제출 폐루프 enqueue). additive only. | 구현 V1~V12 |
| HRR(구현 `V14__phase_high_risk_registry.sql`) | `V14__phase_high_risk_registry.sql` | **T2 AML-ENG-02**: (1) `aml_high_risk_registry` 생성(§3.19, tenant 1행 헤더, FK→aml_tenants). (2) `aml_high_risk_registry_items` 생성(§3.20, list_type CHECK 3종·tier CHECK 2종, FK→aml_high_risk_registry ON DELETE CASCADE, `ix_hrr_items_subject`). (3) `aml_approvals.subject_type` CHECK **17→18종**(`HIGH_RISK_REGISTRY` 추가, §5.16) — V3 인라인 `aml_approvals_subject_type_check` + V13 명명 `ck_aml_approvals_subject_type` 양쪽 DROP 후 18종 단일 제약 통합. additive only. | 구현 V1~V13 |
| PII vault(구현 `V15__phase_pii_vault.sql`) | `V15__phase_pii_vault.sql` | **T3 AML-ENG-03**: `aml_pii_vault` 생성(§3.21, PK `(tenant_id, target_ref, field)`, field CHECK 4종 §5.35, `ciphertext` 평문 미저장, FK→aml_tenants, `ix_aml_pii_vault_target`). reveal(`/internal/v1/aml/pii/reveal`) cleartext 산출 원천(가역암호). additive only. | 구현 V1~V14 |
| 보고 종결 사유(구현 `V16__report_closure_reason.sql`) | `V16__report_closure_reason.sql` | **T4 AML-ENG-04**: `aml_regulatory_reports`에 `closure_reason_code VARCHAR(64)` 컬럼 추가(§3.12, nullable — legacy 행 무영향). `REJECTED`/`CANCELLED` 종결 시 사유 코드 영속 → STR 미보고 사유 분포(API §2.7 `unreported-reasons`) 집계 원천. `ctr_exemption_code`와 별개·공존. additive only(`ADD COLUMN IF NOT EXISTS`). | 구현 V1~V15 |

> 롤백: Flyway는 forward-only이므로 각 V는 idempotent하게 작성하고, 데이터 변형은 별도 보정 마이그레이션으로 분리. 운영 롤백은 `UNDO` 대신 보상 마이그레이션 + feature flag로 처리. V17a/V17b는 2-phase 적용(additive-then-drop) 권장 — V17a 적용 후 운영 검증을 거쳐 V17b를 별도 배포로 진행한다.

---

## 8. 정본·상위 문서 동기화 확인

| 정본/설계서 요건 | 본 DB 반영 |
|---|---|
| 별도 스키마(4서비스) | `aml` 스키마 전용 (§0, V01) |
| 배포 모델(deployment topology) | `aml_tenants.deployment_model`(3종)·`onboarding_status`(8종)·`infra_ref`·`default_region`='KR'. 구 `isolation_mode` 폐기(V17a/b). 격리 1차 경계=배포, 온보딩 상태머신 §5.28a. 정본 §4.1·설계서 §16 동기화 |
| 멀티테넌시(tenant/data-scope) | 전 테이블 `tenant_id` PK 선두(배포 내부 분리, 테넌트=서비스·상위 기관 참조 `institution_ref`) + `data_scope`(권한 필터) + RLS — `SHARED`에서만 `tenant_id` 행 격리가 서비스 간 경계로 동작 (§1.1, §2.1) |
| raw PII 미저장·토큰/해시 | `*_hash`/`*_token`/`*_ref`, payload_hash, 원문 컬럼 없음 (§2.2) |
| 감사 컬럼·append-only 감사 | 공통 감사 컬럼 + aml_audit_events hash chain (§2.1, §3.15) |
| 4-eyes(작성자≠승인자) | aml_approvals + CHECK `maker_id<>checker_id` (§3.15) |
| 트랜잭셔널 아웃박스(report/webhook/fds-feedback 발행) | aml_outbox + 발행 멱등 UNIQUE + status enum(§3.15, §5.17, V16) — integration §8.1 정본 동기화, T-16 선행 |
| Account/Instrument 핵심 객체(설계서 §7.1) | 전용 마스터 미보유 결정(§1) — canonical event JSONB·`*_ref`/`*_hash`·CRYPTO_ADDRESS screening/travel-rule로 추적 |
| Policy Pack STR/CTR/Travel Rule | report_type enum + aml_regulatory_reports + aml_travel_rule_transfers + KR_DEFAULT seed (§3.12, §3.14, V15) |
| traceId 관측성 | 전 테이블 `trace_id` (§2.1, §20.3) |
| aml-svc=com.hanpass.aml 헥사고날 | out/persistence 어댑터가 본 `aml_*` 테이블 매핑 (설계서 §6.2) |
| bo-api/bo-web 정본 매핑 | 결재·감사·evidence export 테이블을 admin API 경유 사용 (설계서 §6.1) |
| `workspace_id` 미사용 결정 | 정본 §4 3-key 중 `workspace_id`는 본 서비스 미도입 — 설계서 §16.2.1의 2-key(tenant+data_scope) 결정 기록(§1.1 주석) |
| `subject_type` 16종 확정(`CHECKLIST_CHANGE`·`PERIODIC_REVIEW_CHANGE` 추가, 구 `CDD_CHECKLIST` 교정) | §5.16 enum 16종 확정(API 정본 `CHECKLIST_CHANGE` 채택) — T-12 착수 전 API §3.7·§10 동기화 필수. §3.15 인라인 목록·V09 CHECK 제약 동기화 완료 |
| `edd_trigger` enum 8종 물리 정본 | §5.29 신설 — 설계서 §13.2 코드값 SCREAMING_SNAKE_CASE 확정 |
| `payload_hash` NOT NULL 서버 자동계산 결정 | `aml_canonical_events.payload_hash` NOT NULL 유지; 서버 sha256 자동계산 방식으로 API 정합 — API §3.1 IngestEventRequest 주석 추가 필요 |
| `aml_source_systems.status` + `data_scope` 추가(QA #4 HIGH·#5 MEDIUM) | §3.2에 `status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE'`·`data_scope VARCHAR(64)` 정식 행 추가. V20 마이그레이션. 설계서 §17.1 DDL·§16.2.1과 일치 |
| `aml_tenants.status` 4종 동기화·DEFAULT 변경(QA cross #119 HIGH·#127 MEDIUM) | §3.1 `status` DEFAULT `'ACTIVE'`→`'ONBOARDING'`·3종→4종(`ONBOARDING`/`ACTIVE`/`SUSPENDED`/`OFFBOARDED`). §5.28b 4종으로 교체. V20 마이그레이션. FDS §11.6.7·`fds_tenants.tenant_status` 4종과 동기화 |
| `stored` 플래그 폐기(QA #7 low) | §2.2 '`stored=false` 플래그' 표현 제거 + 설계서 §8.2(2026-06-07 폐기 확정) 근거 명시. §3.15 `aml_canonical_events.payload_hash` 설명에서 `stored=false` 참조 제거 |

---

## 변경 이력

| 일자 | 변경 | 비고 |
|---|---|---|
| 2026-06-19 | **테넌트=서비스 재정의 + 기관 참조(institution_ref) 컬럼 신설(1 기관 : N 서비스).** §1.1/§2.1/§8 설명 텍스트의 '고객사'를 '서비스(테넌트=서비스)'로 정정(계층 기관→서비스(테넌트)→워크스페이스). §3.1 `aml_tenants`를 '서비스 마스터(테넌트=서비스)'로 라벨링하고 상위 기관 참조 컬럼 `institution_ref VARCHAR(64) NULL`(additive·후속 마이그레이션) 추가. §3.17 IRA·§3.15 outbox·§5.28 deployment_model 설명의 '고객사' 정정. `tenant_id`/`data_scope`/RLS `app.current_tenant`·scope 코드·PK 선두 규칙 불변(의미만 '서비스'). | data-modeler. 컬럼명·enum·경로 불변(라벨/설명만). |
| 2026-06-19 | **데이터 레이어 hanpass-ph 재그라운딩 + TM 알림 evidence·거래·대상360° 재설계.** §3.2 `aml_source_systems.source_system` 카탈로그를 hanpass-ph 7실서비스(member/walletchg/domestic/remit/wallet/tx-history/inbound-svc)로 현행화(REST sync). §3.6/§3.7 watchlist provider 를 `member-svc zoloz_aml_screening` 신호로 정합·48h 신선도 fail-closed 명시. §3.8 screening score_breakdown/reason_codes 를 zoloz decision/risk_level/total_hits/hit_results 로 매핑. §3.10 `aml_alerts.transaction_ref`·`evidence` 를 **TM 알림 상세 데이터모델**(트리거·집계 패턴·관련 거래 목록·자금그래프 funnel)로 보강. §3.15 canonical_events `event_type`/`payload` 에 hanpass-ph 소스별 emit·corridor(send/receive country·currency·USD amount_base) 주석. **§3.16 대상 360° 통합 뷰 신설**(tx-history + member CDD/screening + wallet transfer_links read model). **규제 레이어(CTR/STR 임계·기한·KoFIU 의심유형) 불변** — 데이터 신호(`StrIndicator`·`sanction_screening_event`)만 매핑하고 규제 STR 분류는 KR 정본 유지. | data-modeler. 식별자 원문 금지(token/keyed-HMAC). domestic-svc `member_id` varchar(36) join 정규화 주의. PRD §1.5/§7·API §2~§3·integration §3/§7 동기화. |
| 2026-06-15 | **T4 (AML-ENG-04) STR 통계 원천 — 보고 종결 사유 컬럼 역삽입 (확정).** **§3.12 `aml_regulatory_reports`에 `closure_reason_code VARCHAR(64)` 컬럼 추가** — nullable(기존 행 무영향). `REJECTED`/`CANCELLED` 종결 시 사유 코드 영속(설계서 §14.1a), STR 미보고 사유 분포(API §2.7 `GET /admin/aml/reports/stats/unreported-reasons`, PRD §12-B.3 ①) 집계 원천. `ctr_exemption_code`(CTR 면제 사유)와 별개 의미·공존. legacy 미영속 행은 통계에서 `UNSPECIFIED`(소급 seed 없음). 코드값(raw PII 아님). **§7 V16(구현 `V16__report_closure_reason.sql`) 마이그레이션 등재**(구현 V1~V15 의존, `ADD COLUMN IF NOT EXISTS` additive only). 지연일수 분포(`str-delay`)는 신규 컬럼 없이 기존 `created_at`/`submitted_at`에서 파생. 정본=태스크 `20260615-exposed-gap-development-tasks.md` §T4·plan `docs/ai/plans/2026-06-15-t4-aml-stat-source-surface.md`·API §2.7/§3.6·PRD §12-B.3. | aegis-java-implementer. API §2.7 stats 행·§3.6 DelayBucket/UnreportedReason DTO와 동기화. |
| 2026-06-15 | **T3 (AML-ENG-03) PII reveal vault 역삽입 (확정).** (1) **§3.21 `aml_pii_vault` 신설** — PK `(tenant_id, target_ref, field)`, `ciphertext`(평문 미저장, AES-256-GCM `SecretCipherPort`), FK→aml_tenants, `ix_aml_pii_vault_target`. reveal(`POST /internal/v1/aml/pii/reveal`, API §2.6) cleartext 산출 원천(가역암호 vault — §2.2 "원문 컬럼 금지" 유지). (2) **§2.2 보강** — "PII reveal 원천 = 가역암호 vault" 명문화(단방향 hash 로는 역참조 불가, vault 는 암호문만 저장하므로 평문 컬럼 금지 유지). (3) **§5.35 pii_field enum 신설** — 4종(NAME/DOC/ACCOUNT/WALLET, CHECK, 도메인 `PiiField` 1:1). (4) **§7 V15(구현 `V15__phase_pii_vault.sql`) 마이그레이션 등재**(구현 V1~V14 의존, additive only). 정본=태스크 `20260615-exposed-gap-development-tasks.md` §T3·ADR `docs/ai/decisions/2026-06-15-aml-eng-03-pii-reveal.md`. vault 적재 시점·전 필드 확장은 후속(가정 A2). | aegis-java-implementer. API §2.6 reveal 행과 동기화. |
| 2026-06-10 | **QA 이격 DB 담당 정합화 (doc-consistency-report-all 기준)**: (1) **HIGH §3.2 `aml_source_systems`에 `status` 컬럼 추가** — `status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE'`(`ACTIVE`/`DISABLED` enum, 설계서 §17.1 DDL·§16.2.1 정본·QA #4). (2) **MEDIUM §3.2 `aml_source_systems`에 `data_scope` 컬럼 추가** — `data_scope VARCHAR(64) Y NULL`(§2.1 공통 규약 전 운영 테이블 적용 원칙, QA #5). (3) **LOW §2.2 `stored` 플래그 폐기 명문화** — §2.2 `stored=false` 표현 제거(설계서 §8.2 2026-06-07 폐기 확정, QA #7); §3.15 `aml_canonical_events.payload_hash` 설명에서 `stored=false` 참조도 제거. (4) **HIGH §5.28b `aml_tenants.status` 4종 동기화** — 3종(`ACTIVE`/`SUSPENDED`/`OFFBOARDING`) 폐기 → 4종(`ONBOARDING`/`ACTIVE`/`SUSPENDED`/`OFFBOARDED`) 신설, §3.1 DEFAULT `'ACTIVE'` → `'ONBOARDING'` 변경(FDS §11.6.7·`fds_tenants.tenant_status` 동기화, QA cross #119 HIGH·#127 MEDIUM). (5) §7 V20 마이그레이션 신설(aml_source_systems 컬럼 추가·aml_tenants.status 4종 갱신·OFFBOARDING→OFFBOARDED 데이터 마이그레이션). (6) §8 동기화 확인 표에 4개 항목 추가. | data-modeler. 설계서 §16.0c도 4종으로 동기화 대상(파생→정본 역삽입). |
| 2026-06-10 | **준법감시인 검토 반영(상위 정본=설계서 §14.1a/§14.3/§19.3 2026-06-10 갱신) 동기화.** (1) **§5.11 report_status 8종 확장** — `ACKNOWLEDGED`(FIU 접수)·`SUBMISSION_FAILED`(전송 실패/FIU 오류 반려) 추가 + FIU 회신 폐루프·재제출(RESUBMIT)·기각/취소 4-eyes 통제 주석. (2) **§3.12 `aml_regulatory_reports` 컬럼 4종 추가** — `fiu_ack_ref`(FIU 접수번호)·`submission_error_code`(오류코드)·`resubmit_count`(재제출 횟수)·`ctr_exemption_code`(CTR 제외 사유 코드, §14.3 제외 처리=CANCELLED+코드·4-eyes·감사). (3) **§6 보존정책 법정 수치 명문화** — STR/CTR·CDD·의심거래 자료 5년(특금법 §5의4)·감사로그 7년. (4) **§7 V19 마이그레이션 등재**(V10 의존). | data-modeler. API §3.6 DTO·연동 §3.4/§5.4·PRD §1.7/§9 동기화 대상. |
| 2026-06-08 | **QA #19/#20 DB 정합화(aml:db-api)**: §3.15 `aml_evidence_exports`에 `status VARCHAR(32) NOT NULL DEFAULT 'PENDING'` 컬럼 추가(API `EvidenceExportResponse.status` backing, QA #19 HIGH); `reason VARCHAR(512)` nullable→`NOT NULL DEFAULT ''` 강화(API 필수 일치, QA #20 MED). §5.30 `evidence_export_status` enum(4종) 신설. §7 V18 마이그레이션 등재(V14 의존). QA #21 확인 — `aml_risk_scores` §3.9의 `target_type`·`model_code`·`is_override` 3컬럼 기존 존재 확인, DB 변경 불필요(API §3.3 추가 대상). QA #24 — DB 변경 불필요. | data-modeler |
| 2026-06-06 | 신규 작성(부트스트랩). 설계서 `02-amlSvc-sass.md` §7~§19를 물리 모델로 확정: `aml` 전용 스키마, 도메인 14종(aml_tenants/source_systems/customers/entities/relationships/watchlist_sources/watchlist_entries/screening_results/risk_scores/alerts/cases/regulatory_reports/business_documents/travel_rule_transfers) + 지원 4종(canonical_events/approvals/audit_events/evidence_exports). 멀티테넌시(tenant_id PK+RLS+data_scope), PII hash/token, 감사 컬럼, append-only audit+hash chain, 4-eyes CHECK, 보존정책, enum 코드·표시 병기, 인덱스, Flyway V01~V15 순서 확정. 정본 4서비스·별도 스키마·규제 Policy Pack 100% 반영. | 정본=`target-architecture.md`, 입력 진실=설계서. `docs/plan/02-aml-sass-functional-spec.md`·PPT는 본 명칭 기준 정합화 대상. API/integration/tasks는 §3 테이블·§5 enum·§7 마이그레이션 명칭을 참조한다. |
| 2026-06-06 | doc-consistency(fds) 정합화 연동: `aml_cases.origin_fds_case_ref VARCHAR(96) NULL`(cross-ref, FK 아님) 추가. fds-svc `fds_cases.aml_case_id`(VARCHAR(96))와 동일 폭으로 FDS↔AML 위임 케이스 양방향 cross-ref 확정. `source_origin=FDS`일 때 채움. | 운영자 집계(대시보드/고객사/감사)는 bo-api 소유 경계 유지. aml-svc는 저수준 데이터 API만 제공. |
| 2026-06-07 | doc-consistency(aml) DB 담당 이격 2차 정합화(높음 1 + 낮음/횡단): (1) **HIGH `alert_status`↔enum 정합** — alert_status는 6종 종결(DB CHECK 6종)로 확정하고 설계서 §12.2 후반 전이(INVESTIGATING/REPORTED/CLOSED)는 `aml_cases.status`(§5.9)가 인계함을 §5.7·§3.10 명문화(alert enum에 3종 미추가, 설계서 §12.2 '6종+case 인계'로 파생→정본 역삽입 권고). (2) §5.9 case_status 출처 인용 '(§12.2,§13)'→'(§13.3a,§13)' 교정(alert/case 상태머신 분리). (3) **§5 정본 enum 표 전수 보강** — §5.18 alert_type(API `alertType` 정본 동기화)·§5.19 alert_severity·§5.20 source_origin·§5.21 document_type·§5.22 completeness_status·§5.23 target_type·§5.24 subject_kind·§5.25 kyc_status(DB 물리 정본)·§5.26 required_action·§5.27 priority 추가, §3 본문 inline enum을 §5 매핑표로 1:1 참조 연결(§2.3 코드↔표시 병기 규약 충족). (4) §2.2 PII 명명 규약을 '의미 패턴'으로 정정해 실제 컬럼명(name_hash/doc_hash/legal_name_hash/biz_no_hash/primary_name_hash/wallet_address_hash)과 일치. | 정본=`target-architecture.md`+설계서·DB·API. action_type/subjectType/alertType 마스터=API enum(전수), HTTP 상태코드=API §4. 운영자 집계(대시보드/고객사/감사)는 bo-api 소유·집약·인증, aml-svc/fds-svc는 저수준 데이터 API만 제공(엔진 API에 집계 엔드포인트 미추가). FDS↔AML 위임 cross-ref는 `fds_cases.aml_case_id`(fds-db §3)·`aml_cases.origin_fds_case_ref`(§3.11) 양 정식 행 유지. | data-modeler |
| 2026-06-08 | **QA 리포트 db-api/design-db 이격 정합화(3차)**: (1) §3.15 `aml_canonical_events.payload_hash` 설명 보강 — 'API 요청 DTO는 optional, DB는 서버 채움 NOT NULL' 계약을 첫 문장에 명시. NOT NULL 제약 열 명기. QA aml:db-api HIGH(payload_hash 필수 여부 모순) 정합 완료. (2) §3.15 `aml_approvals.subject_type` 16종·§5.16·V09 CHECK 제약은 이전 2차 정합(2026-06-08)에서 완료 확인 — 변경 없음. (3) §5.29 `edd_trigger` 8종 권고 주석 유지 — 변경 없음. | data-modeler |
| 2026-06-08 | **doc-consistency-report-aml QA 이격 DB 담당 항목 2차 정합화(aml:design-db HIGH + aml:db-api HIGH 연계 해소)**: (1) **HIGH `subject_type` enum 코드값 교정 + 16종 완전화** — §3.15 `aml_approvals` 인라인 목록을 14종→16종으로 갱신하고, 비정본 코드값 `CDD_CHECKLIST` → API 정본 `CHECKLIST_CHANGE`로 교정(QA aml:db-api HIGH 해소). §5.16 enum 표도 동일 교정(`CHECKLIST_CHANGE` 코드값·설명 및 후주 갱신). §7 V09 migration 내용란에 `subject_type` CHECK 16종 목록 명기(CHECKLIST_CHANGE 포함). §8 동기화 확인 표 갱신. T-12 결재 상신 API 착수 전 API §3.7·§10도 `CHECKLIST_CHANGE`로 동기화 필요. | data-modeler |
| 2026-06-08 | **doc-consistency-report-aml QA 이격 DB 담당 항목 정합화(이전 기록)**: (1) **HIGH `subject_type` enum 16종 확정** — §5.16에 `CDD_CHECKLIST`(CDD checklist 변경·상신, T-12 결재 착수 전 필수)·`PERIODIC_REVIEW_CHANGE`(주기적 재확인 기준 변경) 2종 추가(기존 14종 → 16종). `aml_approvals.subject_type` DDL CHECK 및 API §3.7 ApprovalDto·§10 등재표 동기화 필요. (2) **LOW `edd_trigger` enum §5.29 신설** — 설계서 §13.2 Trigger 표를 SCREAMING_SNAKE_CASE 코드값 8종으로 물리화(`WLF_TRUE_MATCH`/`HIGH_RA_SCORE`/`HIGH_RISK_COUNTRY`/`UNUSUAL_TRANSACTION`/`COMPLEX_OWNERSHIP`/`TRADE_MISMATCH`/`CRYPTO_RISK`/`INTERNAL_OVERRIDE`). API §3.5 CaseDto `eddTrigger` 및 설계서 §13.2 동기화 필요. (3) **HIGH `aml_canonical_events.payload_hash` 정합 결정** — NOT NULL 유지, 서버 sha256 자동계산 방식으로 API 정합(API §3.1 IngestEventRequest `payloadHash` optional 허용, 미제공 시 aml-svc ingest 어댑터 자동계산). §3.15 canonical_events 명세에 결정 주석 추가. (4) **MEDIUM `workspace_id` 미사용 결정 명문화** — §1.1 격리 키 표에 주석 추가: 정본 §4 3-key 중 `workspace_id`는 설계서 §16.2.1의 2-key(tenant+data_scope) 합의에 따라 미도입. (5) §5.28b enum 재작성은 이전 이력(배포 모델 동기화) 참조. | data-modeler |
| 2026-06-08 | **격리(isolation_mode) → 배포 모델(deployment topology) 재설계** 동기화(설계서 §16 + 정본 target-architecture §4.1 + FDS DB §2/§4.1/§4.1a/§5.1/§8 V17): (1) §0 설계 정본 '고객사 격리' 행 → '배포 모델' 행으로 교체(MANAGED_DEDICATED 기본·D-06 결정 확정). (2) §1 ERD `aml_tenants` 박스에 `deployment_model`·`onboarding_status` 추가. (3) §1.1 멀티테넌시 전면 재작성 — 배포 모델 1차 경계 원칙·분리 키 재정의(tenant_id=배포의 고객사·전용 배포=단일값·data_scope=권한필터)·고객사 관리 소유 경계(bo-api 전용 온보딩 엔드포인트). (4) §3.1 `aml_tenants` DDL: `isolation_mode` DROP → `deployment_model`(DEFAULT 'MANAGED_DEDICATED')·`onboarding_status`(DEFAULT 'REQUESTED')·`infra_ref`(VARCHAR 160) 추가, `default_region` DEFAULT 'KR'(대문자) 정규화, `status` 운영 생명주기 직교 설명 추가 + 마이그레이션 V17 주석. (5) §5.28·§5.28a·§5.28b 신설 — deployment_model(3종)·onboarding_status(8종·Mermaid 상태머신)·status(3종) enum + FDS §4.1/§4.1a 100% 동기화. (6) §7 마이그레이션에 V17a(컬럼 추가·백필)·V17b(isolation_mode DROP) 2단 추가. (7) §8 동기화 확인 표에 배포 모델·멀티테넌시 행 갱신. | data-modeler |
| 2026-06-07 | doc-consistency(aml) DB 담당 이격 정합화: (1) **`aml_outbox` 지원 테이블 신규**(§3.15) — integration §8.1 snake_case 컬럼 정본 채택(outbox_id/aggregate_type/aggregate_ref/event_type/payload/payload_hash/status/attempt/next_attempt_at/published_at), 발행 멱등 UNIQUE + `ix_outbox_dispatch`·`ux_outbox_idem` 인덱스 + §5.17 outbox_status enum + retention `TRANSIENT` + Flyway V16(T-16 선행). (2) `aml_alerts.external_alert_ref VARCHAR(256) NULL` 정식 행 추가(§3.10, vendor dual-run cross-ref) + `ix_alert_ext_ref`. (3) `aml_travel_rule_transfers.amount_minor BIGINT NULL` 추가(§3.14, §0 amount_minor 병행 규약). (4) `risk_status` enum §5.15 정본 명문화 — integration `REVIEW`→`HIGH_RISK` 정규화 매핑(DB enum 4종 정본). (5) `aml_approvals.subject_type`에 `TM_SCENARIO` 추가(§5.16) — **API `ApprovalDto.subjectType` enum이 정본(전수)**, DB 동기화. (6) Account/Instrument 전용 마스터 미보유 결정 §1/§8 명문화(canonical event JSONB·`*_ref`/`*_hash`·CRYPTO_ADDRESS 추적). | 정본=`target-architecture.md`. action_type/subjectType 마스터=API enum, HTTP 상태코드=API 명세. 운영자 집계(대시보드/고객사/감사)는 bo-api 소유·집약·인증, aml-svc는 저수준 데이터 API만 제공(엔진 API에 집계 엔드포인트 미추가). case_status(§5.9)·case_type(§5.8)·report_status(§5.11)는 DB가 물리 정본이며 상위 설계서 §13/§14에 상태머신·enum 승격 권고(파생→정본 역삽입). | data-modeler |
