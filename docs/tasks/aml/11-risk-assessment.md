# T-11 RA 모델·factor catalog·simulation·등급·override [BE+BO]

- 서비스: `services/aml-svc` (+ bo) · Effort: XL · 의존: T-04, T-12 · Status: TODO

## 목표
고객·법인·셀러·가맹점 위험평가(RA) 엔진과 versioned model·factor catalog·simulation·4-eyes 활성화·등급 override를 구현한다.

## 구현 항목
- [BE] `EvaluateRiskUseCase` + `aml_risk_scores` adapter, `RiskModelPort`
- [BE] factor catalog(Customer/Geography/Product/Channel/Transaction Behavior/Screening/Entity Structure/Merchant/Crypto/Trade)
- [BE] RA output: `riskScore`(0~100), `risk_grade`(LOW/MEDIUM/HIGH/PROHIBITED), factorBreakdown, modelVersion, `nextReviewDueAt`, requiredAction
- [BE] Public `POST /api/v1/aml/risk-assessments/evaluate`, `GET /api/v1/aml/risk-assessments/{scoreId}`, `GET /api/v1/aml/customers/{customerRef}/risk`
- [BE] versioned model: draft → simulation(sample population) → score distribution → 4-eyes 승인 → effective_from, 이전 모델 비교 리포트 보존
- [BO] Admin: `GET /admin/aml/ra-models`, `ra-models/{modelCode}/simulate`(응답 DTO §3.15 `SimulationResponse`), `ra-models/{modelCode}/versions/{v}:activate` 🔒, `risk-scores/{scoreId}/override` 🔒(등급 수동 하향). 엔진 `GET /admin/aml/risk-scores` 목록은 **미신설**
- [BO] simulation 응답 DTO(§3.15 `SimulationResponse`): `simulationId`·`modelVersion`·`samplePopulation`·`gradeShift`(등급별 부호 증감)·`falsePositiveImpact`(오탐 영향 추정). PRD §5.1 AML-RA-001 '시뮬레이션' 탭(높음/중간/낮음 증감·오탐 영향) 화면 의존. 분석 설정이므로 **결재 불필요**
- [BO] country risk 등급표 조회·변경 화면 연계: `GET /admin/aml/country-risk`(ISO 국가별 risk band·근거 조회), `POST /admin/aml/country-risk:change` 🔒4-eyes(`subjectType=COUNTRY_RISK`, §2.7·§10). 변경 상신→승인→실행(EXECUTED) 시 정책 store 반영. country risk는 RA factor catalog(Geography)의 입력 정책으로, 변경 실행 후 해당 국가 관련 대상 **재평가(RA) 트리거**(§3.12 `CountryRiskChangeRequest` 비고)
- [BE] country risk 변경 결재는 **T-12 결재 엔진**(`subjectType=COUNTRY_RISK`)으로 처리. 본 태스크는 정책 store 조회/상신 진입점·실행 후 재평가 연계만 소유(결재 상태머신·payload_hash·실행분리는 T-12)
- [BE] high-risk 확정 시 outbox `aml.customer.high_risk`(RISK_OVERRIDE) 전파(T-16)

## 참조
- `docs/design/api/02-aml-api.md` §2.3, §3.3, §2.7(ra-models·risk-scores/override·country-risk·`country-risk:change`🔒), §3.12(`CountryRiskDto`/`CountryRiskChangeRequest`), §3.15(`SimulationResponse`), §10(4-eyes 트리거: `COUNTRY_RISK`)
- `docs/design/db/02-aml-db.md` §3.9, §5.2(risk_grade)
- `docs/software/02-amlSvc-sass.md` §11
