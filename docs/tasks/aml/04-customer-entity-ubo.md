# T-04 Customer·Entity·UBO graph 모델·해소 [BE]

- 서비스: `services/aml-svc` · Effort: L · 의존: T-02 · Status: TODO

## 목표
개인·법인·실소유자·관계자를 graph로 연결하는 Customer/Entity/UBO 도메인 모델과 entity resolution을 구현한다(단일 row 모델 금지).

## 구현 항목
- [ ] `domain/`: Customer, LegalEntity(Entity), BeneficialOwner, Relationship ADT·불변식
- [ ] `aml_customers`·`aml_entities`·`aml_relationships` persistence adapter
- [ ] customer_type/entity_type enum(PERSON/SOLE_PROPRIETOR/LEGAL_ENTITY/MERCHANT/SELLER/VASP_CUSTOMER/EMPLOYEE/VENDOR)
- [ ] relationship_type enum(OWNS/CONTROLS/REPRESENTS/OPERATES/USES_ACCOUNT/PAYS_TO/RELATED_TO/EMPLOYED_BY)
- [ ] UBO graph: 지분율 변경 이력, 동일 UBO 다법인 운영 패턴 탐지, high-risk UBO 연결 전파
- [ ] entity resolution: `customer_ref`/`entity_ref` 기반 매칭, PII는 `name_hash`/`legal_name_hash`/`doc_hash`/`biz_no_hash`만
- [ ] UBO 미제출·불일치 alert 트리거(T-09/T-13 연계)

## 참조
- `docs/design/db/02-aml-db.md` §3.3~§3.5, §5.1(customer/entity_type), §5.3(relationship_type)
- `docs/software/02-amlSvc-sass.md` §7.2·§9
