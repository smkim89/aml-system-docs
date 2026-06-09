# T-15 4-eyes 결재 게이트(approval·payload_hash·실행 분리) [BE+BO]

- 서비스: `services/fds-svc` + `bo-api` · Effort: L · 의존: T-02, T-06 · Status: TODO

## 목표
준법감시실 자율 운영을 위한 결재 시스템(4-eyes보다 넓은 maker-checker)의 엔진 측 게이트를 구현한다. 상신자≠승인자 강제, payload_hash 고정, 결재 완료와 실행 분리를 보장한다.

## 구현 항목
- [ ] **[BE]** `fds_approval_requests`/`fds_approval_steps`: `subject_kind`(ACTION/RULE/MAPPING/SECRET/GROUP/EXPORT/MERCHANT_NORMALIZE), `approval_line`(6종), `status`(8종)
- [ ] **[BE]** maker≠checker 강제(`SELF_APPROVAL_DISABLED`): `FDS-APPROVAL-SELF`(409). AI agent는 maker만 가능(checker 불가, bo-api IAM 강제)
- [ ] **[BE]** `payload_hash` 고정: 승인 후 payload 변경 시 무효(`FDS-APPROVAL-PAYLOAD-CHANGED`)
- [ ] **[BE]** 승인↔실행 분리 저장: 승인(`fds_approval_steps`) vs 실행(action relay/rule deploy). `expires_at`·`max_executions`·`reason`
- [ ] **[BO]** Approval API: `GET /api/v1/admin/fds/approvals`, `/{id}`(payload_hash), `/approve`, `/reject`
- [ ] **[BE]** 결재 필요 여부 판단(tenant policy): 자금/규제/정책변경/보안설정/예외승인 = 필수, 조회/초안 = 불필요
- [ ] **[BE]** `subjectKind=GROUP` 게이트 대상: risk group member 추가/제거(`POST`·`DELETE .../{groupId}/members`) **및 group 마스터 수정/비활성**(`PUT /admin/fds/risk-groups/{groupId}`, subjectRef=`group_id`, 기본 `RISK_MANAGER`, §8) — T-10 호출, 승인 후 relay(payload_hash 고정)
- [ ] 운영자 IAM·승인 라인 정책은 bo-api 소유(fds-svc는 엔진 게이트만)

## 참조
- `docs/software/01-fdsSvc-sass.md` §11.4(4-eyes), §11.5(결재 시스템·상태 모델)
- `docs/design/db/01-fds-db.md` §4.12(approval), §5.23~5.24
- `docs/design/api/01-fds-api.md` (v1.4) §4.9(Approval API), §8(4-eyes 게이트 표·`GROUP` 행: `PUT /risk-groups/{groupId}` 마스터 수정/비활성 + members)
- GROUP 게이트 호출자: T-10(risk-groups)
- `docs/design/integration/01-fds-integration.md` §5.2(결재 게이트), §8.3
