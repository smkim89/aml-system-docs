# T-05 Schema Registry·PII 토큰화/해시·canonical event store [BE]

- 서비스: `services/aml-svc` · Effort: L · 의존: T-02 · Status: TODO

## 목표
원천 이벤트를 canonical AML event로 정규화하는 Schema Registry, raw PII 미저장(tenant-managed tokenization, D-05), canonical event store(멱등)를 구현한다.

## 구현 항목
- [ ] `SchemaRegistryPort`: sourceSystem×schemaVersion → canonical 매핑 검증
- [ ] `PiiTokenizationPort`: 원문 일시 처리 후 token/hash만 저장(`*_ref`, `*_hash` tenant-keyed HMAC, `secret_ref`만 보관)
- [ ] `CanonicalEventStorePort` + `aml_canonical_events` adapter
- [ ] envelope 필드 = `aml_canonical_events` 컬럼 1:1: `schema_version`, `tenant_id`, `data_scope`, `source_system`, `event_id`, `idempotency_key`, `event_type`, `occurred_at`, `trace_id`, `payload`, `payload_hash`(stored=false)
- [ ] 멱등: UNIQUE`(tenant_id, idempotency_key)` + INSERT ON CONFLICT DO NOTHING
- [ ] 금액 payload: `amount`(NUMERIC(24,8) 문자열) + `amountMinor`(BIGINT) 병행
- [ ] eventType 카탈로그 검증(integration §3.1 인바운드 목록)

## 참조
- `docs/design/integration/02-aml-integration.md` §4(envelope), §3.1(eventType), §6.1(멱등)
- `docs/design/db/02-aml-db.md` §3.15(`aml_canonical_events`)
- `docs/software/02-amlSvc-sass.md` §8, §19.2(PII)
