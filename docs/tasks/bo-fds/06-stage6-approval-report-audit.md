# BOF-S6 · 결재함·규제 보고·Evidence·감사 (SFDS-APPR-001 · SFDS-REG-001/002 · SFDS-EXP-001 · SFDS-AUDIT-001)

> **목표**: 전 Stage의 4-eyes 상신이 수렴하는 결재함과 규제 보고(aml-svc 위임 추적)·검사대응 Export·감사 로그 완성.
> **선행**: BOF-S1 (S2~S5 상신 동작의 수렴점 — 통합 테스트는 해당 Stage 완료 후). **PPT**: 슬라이드 45~49.

## 공통 참고 문서
- PRD §12.1(결재함 — `subject_kind` 9종·`approval_line` 6종·`approval_status` 8종·payload_hash 무결성), §13(규제 보고 — FDS origin/aml-svc 위임·`amlCaseRef`), §14(Export — `export_kind` 6종·`export_format` 4종·`export_status` 6종), §15(감사)
- API `01-fds-api.md`: `GET /admin/fds/approvals`·`/{id}/approve`🔒·`/reject` / `POST /evidence/fds/exports`🔒(최종본)·`/download` / `GET /api/v1/bo/fds/audit`(bo-api 소유)
- AML 연계: FDS 케이스 `caseType=REGULATORY_REPORT` → aml-svc 위임(integration `01-fds-integration.md` §‘fds-aml-handoff’ 큐 / AML PRD §9)

## 태스크

| ID | 구분 | 태스크 | 참고 문서 | Effort | 의존 |
|---|---|---|---|---|---|
| BOF-S6-01 | BE | **결재 프록시** — approvals 목록/상세·`approve`🔒(self-approval 409)·`reject`(사유) 위임 + 결재 실행 결과(BE relay: RULE→ACTIVE·ACTION→발행·MAPPING→effective·GROUP→명단 반영·CASE_CLOSE→종결) 표시 데이터 | API(approvals) / PRD §12.1(BR — relay 매핑 전수) | 3 | S1-04 |
| BOF-S6-02 | FE | **SFDS-APPR-001 결재함** — 검색(유형/상태/상신자)·`subject_kind` 9종(규제 팩 변경 포함) 배지·행 ▶펼침(payload diff·payload_hash 무결성 표시)·[승인🔒]/[반려(사유)] | PRD §12.1 / PPT 슬라이드 45 / `FDS-APPROVAL-SELF` 409 처리(§16.3) | 4 | S6-01 |
| BOF-S6-03 | BE | **규제 보고 프록시** — `GET /fds/cases?caseType=REGULATORY_REPORT,...` 큐 조회 + aml-svc 위임 상태 cross-ref(`amlCaseRef`) 결합 | PRD §13.1·§13.2 / API(cases) / integration(fds-aml-handoff) | 3 | S1-04 |
| BOF-S6-04 | FE | **SFDS-REG-001/002 규제 보고 큐·상세** — 보고 후보 큐(행▶→REG-002)·상세(진입 배너·aml-svc 위임 추적 타임라인·AML 케이스 링크) — **제출 자체는 AML 콘솔 소관(책임 경계)** | PRD §13.1·§13.2(경계 명시) / PPT 슬라이드 46~47 | 3 | S6-03 |
| BOF-S6-05 | BE | **Evidence Export 프록시** — `POST /evidence/fds/exports`(종류 6·형식 4·기간·최종본=4-eyes `EXPORT`)·상태 폴링·`/download` 위임 | PRD §14.1 / API §4.5 | 2 | S1-04 |
| BOF-S6-06 | FE | **SFDS-EXP-001 Evidence Export** — 생성 요청 폼·`export_status` 6종 배지(요청됨~만료/실패)·manifestHash 표시·다운로드 | PRD §14.1 / PPT 슬라이드 48 | 2 | S6-05 |
| BOF-S6-07 | BE | **감사 집계 API** — `GET /api/v1/bo/fds/audit`(bo-api 소유 — 운영 변경 전수: 누가/언제/무엇/payload_hash·traceId) + bo-api 자체 감사(로그인·권한 변경·프록시 호출) 적재 | PRD §15.1 / API §11 / target-architecture §4(감사 전수) | 3 | S1-05 |
| BOF-S6-08 | FE | **SFDS-AUDIT-001 감사 로그** — 필터(기간·작업자·대상 유형)·상세 diff·Export 연계 | PRD §15.1 / PPT 슬라이드 49 | 2 | S6-07 |

## DoD
- S2(Policy Pack)·S3(매핑·secret)·S4(룰 활성화·그룹)·S5(케이스 종결·액션) 상신 전부가 결재함에서 승인/반려되고 결과 relay가 화면에 반영(통합 E2E).
- self-approval 409·payload 변경 무효화 케이스 처리. 최종본 Export는 4-eyes 후에만 다운로드.
- **FDS 콘솔 34화면 전수 개통** — PRD §16.1 매핑표 기준 누락 0건 체크리스트 통과.
