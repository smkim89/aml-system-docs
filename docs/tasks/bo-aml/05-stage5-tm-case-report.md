# BOA-S5 · TM·케이스·규제 보고·기관 RBA·Travel Rule (AML-TM-001/002 · AML-CASE-001/002 · AML-REP-001/002 · AML-IRA-001 · AML-TR-001)

> **목표**: 거래 모니터링 알림→케이스 조사→STR/CTR 보고(FIU 폐루프)·기관 위험평가 지표 보고·Travel Rule 예외까지 규제 업무 본선 완성.
> **선행**: BOA-S1·S3(WLF 확정→케이스)·S4(EDD 착수·체크리스트). **PPT**: 슬라이드 39~58. **tipping-off 가드(BOA-S1-03) 전 화면 적용.**

## 공통 참고 문서
- PRD §7.1(TM)·§12-A.6(빌더)·§8.1(케이스)·§12-A.7(상세)·§9.1(REP)·§12-A.8(보고 상세)·§12-B.2(IRA)·§10.1(TR) / 상태머신 §1.7(알림·케이스·보고 8종 FIU 폐루프)·케이스 타입 §1.10
- API `02-aml-api.md`: alerts·tm-scenarios(simulate·`:activate`🔒 `TM_SCENARIO`)·cdd/cases(PATCH·timeline·`:close`🔒·`:reject-relationship`🔒)·reports(`:submit`🔒 STR/CTR_SUBMIT·`:reject`🔒·`:cancel`🔒 — reasonCode 필수)·travel-rule/transfers(`:resolve-exception`🔒)
- DB: `alert_status`·`case_status`·`report_status` 8종·`source_origin`(AML/FDS/VENDOR)·`ctr_exemption_code` — 표시=부록 F / 결재 라인=부록 G
- 법정 SLA: STR=의심 확정 후 지체 없이(내부 3영업일)·CTR=거래일+30일(PRD §9.1 BR·설계서 §14.4)

## 태스크

| ID | 구분 | 태스크 | 참고 문서 | Effort | 의존 |
|---|---|---|---|---|---|
| BOA-S5-01 | BE | **TM 프록시** — alerts 목록/상세·tm-scenarios·simulate·activate🔒 위임 | API / PRD §7.1·§12-A.6 | 2 | S1 |
| BOA-S5-02 | FE | **AML-TM-001 2탭** — ①알림 적체(발생 출처 AML/FDS/VENDOR 컬럼·필터·심각도) ②시나리오 관리(+**효과성 요약 컬럼**(30일 알림·전환율·튜닝 ⚠)·행▶ STAT-001·시나리오▶ TM-002) | PRD §7.1(BR-001~006) / PPT 슬라이드 39~40 | 3 | S5-01 |
| BOA-S5-03 | FE | **AML-TM-002 시나리오 빌더(드릴다운)** — 문장형 ①~⑥(추가조건 AND/OR 그룹)·자연어 미리보기·시뮬레이션(결재 불필요)·`[변경 적용🔒]` | PRD §12-A.6 / PPT 슬라이드 41 / S1-07 `ConditionBuilder` | 4 | S5-01 |
| BOA-S5-04 | BE | **케이스 프록시** — cases CRUD·PATCH·timeline(append-only)·`:close`🔒·`:reject-relationship`🔒 위임 | API / PRD §8.1·§12-A.7 | 3 | S1 |
| BOA-S5-05 | FE | **AML-CASE-001 케이스 목록** — 필터 탭(내 케이스/전체/기한임박/종결·1슬라이드)·케이스 타입 12종·SLA·행▶ 상세 | PRD §8.1 / PPT 슬라이드 42 / §1.10(타입) | 2 | S5-04 |
| BOA-S5-06 | FE | **AML-CASE-002 4탭(드릴다운)** — ①타임라인(개요·SLA·append-only·`[고객 프로필 ▶ → CDD-002]`·`[STR 보고 연계 → REP-002]`) ②CDD/EDD 체크(CDD-001 정책 기준) ③관계·UBO ④증빙(manifest hash) + 종결🔒/관계거절🔒 상신 | PRD §12-A.7(BR-001~003) / PPT 슬라이드 43~46 | 4 | S5-04 |
| BOA-S5-07 | BE | **규제 보고 프록시** — reports 목록/상세·`:submit`🔒·`:reject`🔒·`:cancel`🔒(reasonCode·ctrExemptionCode)·FIU 회신 상태(ACKNOWLEDGED/SUBMISSION_FAILED) 위임 + **보고 본문 헤더에 보고기관 정보 결합**(S2-03 확정) | API §2.7·§10 / PRD §9.1·§12-A.8 / 상태머신 §1.7(8종 폐루프) | 3 | S1·BOA-S2-03 |
| BOA-S5-08 | FE | **AML-REP-001 3탭** — ①STR 후보(종류 컬럼·**보고 기한 D-3 ⚠**) ②CTR 데이터(`[제외 처리]`+제외 사유 코드🔒) ③제출 이력(FIU 접수번호·오류코드·재제출 회차) — 전담 role 한정 | PRD §9.1(BR 전수·tipping-off) / PPT 슬라이드 47~49 | 4 | S5-07 |
| BOA-S5-09 | FE | **AML-REP-002 3탭(드릴다운)** — ①보고 본문(상시 경고 배너·**보고기관 헤더 파생**·**의심유형 코드(KoFIU 분류) 복수 선택**·WLF/RA 근거) ②첨부 증빙(manifest) ③제출 이력(`[정정 후 재제출]` SUBMISSION_FAILED 한정) + 제출🔒/기각🔒/취소🔒 | PRD §12-A.8(BR-001~003) / PPT 슬라이드 50~52 | 4 | S5-07 |
| BOA-S5-10 | **SPEC** | **IRA API 명세 확정(선행)** — `ira/reports`(회차)·`/indicators`(지표값)·`:submit`🔒(subjectType `IRA_SUBMIT` 신설)·지표 마스터(KR plugin store)·자동 수집 경로 확정 → API·DB 반영 | PRD 부록 E v6.0-2(오픈결정)·§12-B.2 | 3 | — |
| BOA-S5-11 | BE | **IRA 프록시** — 회차 CRUD·지표값 인라인 저장·증빙 첨부·확정/취소·보고파일 생성·제출🔒·FIU 회신(peer 비교) 위임 | BOA-S5-10 / PRD §12-B.2 BR-001~003 | 4 | S5-10 |
| BOA-S5-12 | FE | **AML-IRA-001 3탭** — ①회차·지표 등록(자동/수동·직전값 복사·증빙·확정 카운터 n/N) ②결과·제출 결재(보고파일 생성·🔒 보고 책임자) ③보고 현황(FIU 점수·peer 평균·3회차 추이) — KR 확장 plugin 활성 고객사만 노출 | PRD §12-B.2 / PPT 슬라이드 53~55 | 4 | S5-11 |
| BOA-S5-13 | BE | **Travel Rule 프록시** — transfers 목록·`:resolve-exception`🔒 위임 | API / PRD §10.1 | 2 | S1 |
| BOA-S5-14 | FE | **AML-TR-001 3탭** — ①예외 큐(정보 누락 3종·위험 지갑) ②전체 이전 ③처리 이력 + `[예외처리🔒]` | PRD §10.1(BR 전수·completeness 3종) / PPT 슬라이드 56~58 | 3 | S5-13 |

## DoD
- 본선 E2E: TM 알림→케이스 전환→조사·증빙→STR 후보→본문(보고기관 헤더+의심유형)→제출🔒→FIU 회신(접수/실패)→[정정 후 재제출] 폐루프.
- CTR 제외 처리 사유 코드🔒·법정 기한 D-3 배지·tipping-off(비전담 미노출) 동작 확인.
- `SPEC` 1건(S5-10) 확정 전 IRA 구현 착수 금지. 케이스 종결·보고 제출 전부 결재함(S6) 수렴.
