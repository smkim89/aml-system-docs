# BOF-S2 · 대시보드·고객사 관리 (SFDS-DASH-001/002 · SFDS-TNT-001/002/003)

> **목표**: 운영 진입점(플랫폼/고객사 대시보드)과 고객사 생명주기(목록→상세 5탭→등록·온보딩) 완성.
> **선행**: BOF-S1. **PPT**: 슬라이드 3~11.

## 공통 참고 문서
- PRD `docs/plan/01-fds-sass-functional-spec.md` §2.1·§2.2(대시보드), §3.1~§3.3(고객사), §1.7(멀티테넌시·배포 모델)
- API `docs/design/api/01-fds-api.md` §11(bo-api 소유 `/api/v1/bo/fds/*` — tenants·dashboard), §12(온보딩)
- 배포 모델·온보딩 상태머신: target-architecture §4.1 / FDS PRD §1.7 / DB `docs/design/db/01-fds-db.md`(`deployment_model`·`onboarding_status`)
- 표시 용어: 배포 유형 3종(매니지드 전용/자체 인프라 설치형/소규모 공유)·온보딩 8종 — PRD §3 데이터 항목 표

## 태스크

| ID | 구분 | 태스크 | 참고 문서 | Effort | 의존 |
|---|---|---|---|---|---|
| BOF-S2-01 | BE | **대시보드 집계 API 구현** — `GET /api/v1/bo/fds/dashboard`(플랫폼: 고객사 건전성·ingest 실패·결정 추이·알림) · `GET .../tenants/{tenantId}/dashboard`(고객사: ingest·스키마 실패·룰 hit rate/오탐·케이스 SLA·액션 실패 큐). 엔진 저수준 API 위임 집계 + 30~60초 캐시 | PRD §2.1·§2.2(위젯·항목 전수) / API §11 / 오탐 피드백 = 케이스 종결 `close_reason FP_*`(PRD §11.2 BR-002) | 4 | S1-05 |
| BOF-S2-02 | FE | **SFDS-DASH-001 플랫폼 대시보드** — KPI·고객사 건전성 표·플랫폼 알림(각 행 `[클릭 → SFDS-XXX]` 딥링크) | PRD §2.1 / PPT 슬라이드 3 / BOF-S2-01 | 3 | S2-01 |
| BOF-S2-03 | FE | **SFDS-DASH-002 고객사 대시보드** — ingest 상태·결정 추이(recharts)·룰 hit rate/오탐 위젯·케이스 SLA·액션 실패, 위젯→상세 딥링크 | PRD §2.2 / PPT 슬라이드 4 | 3 | S2-01 |
| BOF-S2-04 | BE | **고객사 CRUD·온보딩 API** — `GET/POST /api/v1/bo/fds/tenants`, `GET/PUT .../tenants/{id}`, 온보딩 `GET .../onboarding`·`POST .../onboarding/provision`(매니지드 IaC 트리거, 202)·`POST .../onboarding/register`(설치형 콜백), `deployment_model` 불변 가드 | API §11.2·§12 / PRD §3.1~§3.3·§1.7 / target-architecture §4.1(상태머신 2경로) | 4 | S1-05 |
| BOF-S2-05 | FE | **SFDS-TNT-001 고객사 목록** — 필터(배포 유형/온보딩 상태/상태)·상태 배지·행▶ 상세·`[+ 새 고객사]` | PRD §3.1 / PPT 슬라이드 5 | 2 | S2-04 |
| BOF-S2-06 | FE | **SFDS-TNT-002 고객사 상세 5탭** — ①기본 정보 ②배포·온보딩(IaC 트리거·설치형 콜백·이력) ③마스킹·보안(Capability 패널·케이스 전용 행) ④Policy Pack(6팩 카탈로그·토글·스테이징·영향 미리보기·`POLICY_PACK` 4-eyes) ⑤알림·소스(소스표 5컬럼·알림 채널 `GET/PUT /admin/fds/notify-channels`) — 같은 부모 탭 바 유지 | PRD §3.2(탭별 데이터 항목·BR 전수) / PPT 슬라이드 6~10 / API §4.8(notify-channels) | 5 | S2-04 |
| BOF-S2-07 | FE | **SFDS-TNT-003 고객사 등록** — 배포 유형 선택(라디오 아님 — 유형+온보딩 신청)·검증·등록 후 상세 이동 | PRD §3.3 / PPT 슬라이드 11 / target-architecture §4.1(격리=프로비저닝 산출 원칙) | 2 | S2-04 |

## DoD
- 고객사 등록→온보딩 상태 전이(매니지드/설치형 2경로) 화면 왕복, `deployment_model` 변경 시도 시 오류 노출.
- 대시보드 알림·위젯 딥링크가 후속 Stage 라우트로 연결(미구현 라우트는 placeholder 허용, S6까지 해소).
- Policy Pack 토글 상신이 결재함(S6 SFDS-APPR-001) 큐에 적재.
