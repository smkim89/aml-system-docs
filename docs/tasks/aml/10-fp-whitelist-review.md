# T-10 False positive whitelist·analyst 검토 큐 [BO]

- 서비스: `services/aml-svc` (+ bo) · Effort: M · 의존: T-09, T-12 · Status: TODO

## 목표
WLF match에 대한 analyst 판정(true/false positive)과 false positive whitelist 관리를 4-eyes 결재로 운영한다. (백오피스 대상)

## 구현 항목
- [BO] WLF 검토 큐: POSSIBLE_MATCH/ESCALATED 목록·필터·정렬, match feature·score breakdown·판정자 표시
- [BO] Admin: `GET /api/v1/admin/aml/screenings?status=POSSIBLE_MATCH`(GET 전용, 컬렉션 POST 미존재), `screenings/{screeningId}/decision` 🔒(TRUE_MATCH/FALSE_POSITIVE 확정=결재)
- [BO] false positive whitelist 등록 `fp-whitelist` 🔒(결재) + whitelist version 저장
- [BE] TRUE_MATCH 확정 시 outbox 효과 `aml.screening.true_match`(T-16 연계), EDD case 트리거
- [BE] analyst decision·whitelist version `aml_audit_events`에 기록

## 참조
- `docs/design/api/02-aml-api.md` §2.7(screenings/decision, fp-whitelist)
- `docs/design/integration/02-aml-integration.md` §8.3(WLF_DECISION → true_match)
- `docs/software/02-amlSvc-sass.md` §13.4, §2.6
