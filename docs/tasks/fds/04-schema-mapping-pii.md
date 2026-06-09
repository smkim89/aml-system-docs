# T-04 Schema Registry·field mapping·PII 토큰화/해시 [BE+BO]

- 서비스: `services/fds-svc` + `bo-api` · Effort: L · 의존: T-02, T-03 · Status: TODO

## 목표
원천 payload를 canonical field로 변환하는 schema registry와 field mapping(PII allowlist 포함)을 구현하고, raw PII 미저장(tenant별 keyed hash/token) 원칙을 ingest 단계에서 강제한다.

## 구현 항목
- [ ] `fds_schema_mappings`(`mapping_def` JSONB: field map + `pii_allowlist`) CRUD, `schema_version` 등록
- [ ] **[BE]** 변환 엔진: `HMAC_TENANT`(subject), `TOKENIZE_DROP_RAW`(PAN/계좌/주소), `DECIMAL_24_8`, enum 매핑(channel/payment_rail/event_family)
- [ ] **[BE]** PII reject: 원천 payload에 주민번호/카드 PAN 포함 시 ingest reject(`FDS-PII-REJECTED`, 422) 또는 tokenization 후 원문 폐기
- [ ] **[BE]** raw payload 미저장: `payload_hash`(`sha256:...`)만 보존(D-06). 예외 시 tenant region 암호화 object storage + hash reference
- [ ] **[BO]** field mapping/PII allowlist 변경 = 4-eyes 결재(`subject_kind=MAPPING`, `MAKER_CHECKER`) via `PUT .../source-systems/{sourceSystem}/mappings`
- [ ] **[BO]** source system 속성·capability 매트릭스 수정(`PUT /api/v1/admin/fds/source-systems/{id}`, `schemaVersion`/`failPolicy`/`capabilities`=`control_capability` DB §4.6 부분집합) — schema/capability 구성과 동일 도메인이므로 4-eyes `subjectKind=MAPPING`(subjectRef=`source_system`) 동일 게이트 적용. T-03 source registry와 분담(레지스트리 CRUD=T-03, schema/capability 정합 검증=T-04)
- [ ] CDC 모드 PII column allowlist 필수 검증
- [ ] 민감도 등급 부여(주민번호·계좌·카드·휴대폰·CI/DI·지갑주소)

## 참조
- `docs/software/01-fdsSvc-sass.md` §5.1, §12.5(CDC), §16.1(PII 원칙)
- `docs/design/db/01-fds-db.md` §5.4(schema_mappings), §7.1(PII 미저장)
- `docs/design/api/01-fds-api.md` v1.4 §4.8(`PUT /source-systems/{sourceSystem}/mappings`·`PUT /source-systems/{id}`), §5.1(rawPayload reject), §5.17(SourceSystemUpdateRequest·capability 매트릭스), §8(4-eyes `MAPPING`)
- `docs/design/integration/01-fds-integration.md` §7.2(필드매핑·mapping_def)
