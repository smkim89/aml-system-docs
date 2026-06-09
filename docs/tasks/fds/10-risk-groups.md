# T-10 Risk group·watchlist/denylist·group match [BE+BO]

- 서비스: `services/fds-svc` + `bo-api` · Effort: M · 의존: T-05, T-15 · Status: TODO

## 목표
blacklist/whitelist/watchlist/mule network/allowlist/denylist 공통 risk group 모델과 group match 룰 입력을 구현한다. group member 변경은 4-eyes 결재 대상이다.

## 구현 항목
- [ ] `fds_risk_groups` CRUD(`group_type` enum: BLACKLIST/WHITELIST/WATCHLIST/MULE_NETWORK/ALLOWLIST/DENYLIST)
- [ ] `fds_risk_group_members`(`member_kind` SUBJECT/INSTRUMENT/COUNTERPARTY, token `member_ref`, `expires_at`)
- [ ] **[BE]** group match 평가용 인덱스(`ix_group_member` on `member_ref`) — rule engine(T-09) 입력
- [ ] **[BO]** Admin API: `GET/POST /api/v1/admin/fds/risk-groups`, `PUT .../{groupId}`(마스터 수정/비활성), `GET/POST/DELETE .../{groupId}/members`
- [ ] **[BO]** group 마스터(틀) 수정/비활성 `PUT /api/v1/admin/fds/risk-groups/{groupId}`(`RiskGroupUpsertRequest`→`RiskGroupDto`, §4.7/§5.18~§5.19): `display_name` 수정·`active=false` 비활성. `group_id`·`group_type` immutable(BR-001/BR-002 위반=`FDS-VALIDATION-002`), 비활성은 멤버 0 선결(`fds_risk_group_members` 전건 0, 잔존 시 `FDS-STATE-CONFLICT` 409). `source`/`autoEnrollOnHit`/`defaultExpiryDays`/`description`은 `fds_risk_groups` 컬럼 부재로 본 PUT 영속 대상 아님(추측 컬럼 미생성)
- [ ] **[BO]** member 추가/제거 **및 마스터 수정/비활성**(`PUT /{groupId}`) = 4-eyes 결재(`subject_kind=GROUP`, subjectRef=`group_id`, 기본 `RISK_MANAGER`) → `fds_approval_requests` 생성 후 승인 relay(§8). 결재 게이트는 **T-15(approval-gate)** 소유
- [ ] `ADD_TO_GROUP` action(T-14)이 group member 반영

## 참조
- `docs/software/01-fdsSvc-sass.md` §3.1(group), §10.1(Group feature), §11.4(4-eyes)
- `docs/design/db/01-fds-db.md` §4.14(risk_group_type), §5.21~5.22
- `docs/design/api/01-fds-api.md` (v1.4) §4.7(risk-groups·`PUT /{groupId}` 마스터 수정/비활성), §5.18~§5.19(`RiskGroupUpsertRequest`/`RiskGroupDto`), §8(4-eyes `GROUP`)
- 결재 게이트: T-15(approval-gate)
