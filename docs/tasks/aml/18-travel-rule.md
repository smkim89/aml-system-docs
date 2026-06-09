# T-18 Travel Rule transfer·exception 처리 [BE+BO]

- 서비스: `services/aml-svc` (+ bo) · Effort: M · 의존: T-17 · Status: TODO

## 목표
가상자산 이전 정보 보존·전달(Travel Rule)과 exception 처리를 4-eyes 결재로 운영한다.

## 구현 항목
- [BE] `aml_travel_rule_transfers` adapter, `transfer_ref` 식별자, wallet_address_hash, `amount`(NUMERIC(24,8)) + `amount_minor`(BIGINT, DB §0 병행 규약·§3.14 확정)
- [BE] `risk_status` enum 4종(CLEAR/SANCTIONED_ADDRESS/MIXER_EXPOSURE/HIGH_RISK, DB §5.15 정본). integration payload `REVIEW`는 `HIGH_RISK`로 정규화 매핑(DB enum 정본)
- [BE] crypto payload(integration §4.3): `crypto.deposit/withdrawal/travel-rule-submitted` 수용
- [BE] VASP 정보 보존·전달 증적, exception 사유·상태
- [BE] exception 확정 → TRAVEL_RULE_EXCEPTION 결재 → 아웃박스 `report.submission.requested`(T-16/T-17)
- [BO] Admin: `GET /admin/aml/travel-rule/transfers?riskStatus&completenessStatus&from&to`(exception 큐, 필터/응답 DTO §3.14 `TravelRuleTransferDto`), `:resolve-exception` 🔒
- [BO] 응답/필터 DTO(§3.14): `transferRef`·`originatorRef`/`beneficiaryRef`(masked)·`assetCode`/`chain`·`walletAddressHash`·`amount`/`amountMinor`·`originatorVasp`/`beneficiaryVasp`·`completenessStatus`(§5.22 4종)·`riskStatus`(§5.15 4종)·`exceptionReason`. 필터 `riskStatus`/`completenessStatus`/`from`/`to`는 인덱스 `ix_trt_risk`(tenant_id, risk_status, completeness_status) 기반. exception 큐 트리거: `completenessStatus=INCOMPLETE` 또는 `riskStatus IN (HIGH_RISK, SANCTIONED_ADDRESS, MIXER_EXPOSURE)`
- [BE] `:resolve-exception` 🔒4-eyes는 `subjectType=TRAVEL_RULE_EXCEPTION` 결재(T-12)로 처리
- [BO] Travel Rule exception 화면(bo-web)

## 참조
- `docs/design/db/02-aml-db.md` §3.14(`aml_travel_rule_transfers`)
- `docs/design/api/02-aml-api.md` §2.7(travel-rule/transfers·`:resolve-exception`🔒), §3.14(`TravelRuleTransferDto`/필터 쿼리), §5.15(risk_status)·§5.22(completeness_status), §10(4-eyes 트리거: `TRAVEL_RULE_EXCEPTION`)
- `docs/design/integration/02-aml-integration.md` §4.3, §9.3
- `docs/software/02-amlSvc-sass.md` §14.1, §18.4
