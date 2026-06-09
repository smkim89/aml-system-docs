# T-18 Commerce/Trade evidence·도메인 확장팩 [BE+BO]

- 서비스: `services/fds-svc` + `bo-api` · Effort: XL · 의존: T-05, T-13 · Status: TODO

## 목표
무역대금·이커머스 해외정산·마켓플레이스 셀러 정산·B2B 인보이스·코인거래소·은행 내부감사 도메인을 위한 상업 증빙(문서·주문·정산) 모델과 도메인 확장팩(Phase 7)을 구현한다.

## 구현 항목
- [ ] `fds_business_documents`(document_type 8종: INVOICE/PURCHASE_ORDER/BILL_OF_LADING/AIR_WAYBILL/CUSTOMS_DECLARATION/DELIVERY_PROOF/TAX_INVOICE/PLATFORM_ORDER)
- [ ] `fds_commerce_orders`(seller/buyer/marketplace ref·delivery_status)·`fds_settlements`(reserve_amount·chargeback_exposure)
- [ ] **[BO]** 무역대금 룰팩: invoice amount·shipment country·unit price deviation·document mismatch → `HOLD_FUNDS`/`REQUIRE_SECOND_APPROVAL`/`OPEN_CASE`(TRADE_FINANCE_REVIEW)/`REQUEST_ADDITIONAL_DOCUMENT`
- [ ] **[BO]** 이커머스 해외정산·마켓플레이스 룰팩: seller age·refund/chargeback ratio·payout country·정산 직전 계좌변경 → `HOLD_SETTLEMENT`/`SUSPEND_SELLER_PAYOUT`/`INCREASE_RESERVE`/`OPEN_CASE`(ECOMMERCE_SETTLEMENT_REVIEW/MERCHANT_RISK)
- [ ] **[BO]** B2B 인보이스 룰팩: vendor age·account 변경·approver role mismatch·duplicate invoice → `REQUIRE_SECOND_APPROVAL`/`OPEN_CASE`(B2B_INVOICE_REVIEW/INTERNAL_AUDIT)
- [ ] **[BO]** 코인거래소·은행 내부감사 룰팩: address risk·travel rule missing·employee override velocity → `BLOCK_WITHDRAWAL`/`SUSPEND_API_KEY`/`SUSPEND_EMPLOYEE_SESSION`/`OPEN_CASE`(CRYPTO_TRAVEL_RULE/INTERNAL_AUDIT)
- [ ] **[BE]** 정산 보류 큐(`ix_settle_status`), settlement type 모델

## 참조
- `docs/software/01-fdsSvc-sass.md` §14.6(commerce/trade), §15.6~15.11(도메인 확장), §18 Phase 7
- `docs/design/db/01-fds-db.md` §4.15(document_type), §5.25~5.27
- `docs/design/api/01-fds-api.md` §4.3(action), §7(reason code)
