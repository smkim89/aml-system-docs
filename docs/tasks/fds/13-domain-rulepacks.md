# T-13 주요 금융 도메인 1차 룰팩(송금·월렛·카드·PG·ATM) [BE+BO]

- 서비스: `services/fds-svc` + `bo-api` · Effort: XL · 의존: T-09, T-12 · Status: TODO

## 목표
설계서 §18 Phase 3 우선순위(domestic transfer → wallet/account → card → PG → ATM)에 대한 1차 도메인 룰팩·feature·action 매핑을 구성한다. 채널별 이벤트·feature·가능 action을 검증한다.

## 구현 항목
- [ ] **[BO]** domestic transfer 룰팩: beneficiary risk·mule account group·first transfer·amount velocity → `BLOCK_TRANSACTION`/`HOLD_FUNDS`/`CANCEL_TRANSACTION`/`OPEN_CASE`(MULE_ACCOUNT_REVIEW)
- [ ] **[BO]** wallet/account 룰팩: 충전 후 즉시 출금·velocity·계정 탈취 → `HOLD_FUNDS`/`SUSPEND_ACCOUNT`
- [ ] **[BO]** card 룰팩: CNP·merchant risk·device fingerprint·refund/chargeback ratio → `DECLINE_AUTHORIZATION`/`CHALLENGE`/`SUSPEND_INSTRUMENT`/`OPEN_CASE`(CHARGEBACK_REVIEW)
- [ ] **[BO]** PG 룰팩: merchant onboarding age·spike·refund ratio·split settlement → `HOLD_SETTLEMENT`/`OPEN_CASE`(MERCHANT_RISK)
- [ ] **[BO]** ATM 룰팩: location·first seen·country mismatch·withdrawal velocity → `DECLINE_AUTHORIZATION`/`SUSPEND_INSTRUMENT`
- [ ] **[BE]** 채널별 이벤트 시퀀스(§15.1~15.5) 정합: authorization/capture/cash.dispensed 등
- [ ] feature catalog(T-08)·reason code 매핑 검증

## 참조
- `docs/software/01-fdsSvc-sass.md` §15.1~15.5(도메인별 확장), §10.2(룰 예시), §18 Phase 3
- `docs/design/api/01-fds-api.md` §7(reason/decision code)
- `docs/design/db/01-fds-db.md` §4.4(channel), §4.8(action_type)
