# 정합성 QA 리포트 — AML v5.8 정책팩·RA / FDS v4.7 규제 팩 토글 변경

| 항목 | 내용 |
|---|---|
| **판정** | **PASS** |
| 검토 대상 변경 | AML v5.8 정책팩(Policy Pack)·RA 변경 / FDS v4.7 규제 팩 토글 변경 |
| 검토 일자 | 2026-06-10 |
| 심각도 높음(high) | 0건 |
| 심각도 중간(medium) | 3건 |
| 심각도 낮음(low) | 10건 |
| 미검증 항목 | 0건 |
| 대상 문서 | `docs/plan/01-fds-sass-functional-spec.md` · `docs/plan/02-aml-sass-functional-spec.md` · `docs/software/01-fdsSvc-sass.md` · `docs/software/02-amlSvc-sass.md` · `generate_fds.py` · `generate_aml.py` |

---

## ① 판정

**PASS** — 높음(high) 0건, 미검증 0건. 개발 착수 가능.

이번 변경 범위에서 구현 오류를 직접 유발하는 블로킹 이격은 발견되지 않았다. 중간(medium) 3건은 PPT 생성기 헤더·라벨 불일치 및 UI 상태 미표현으로 화면 품질에 영향을 주므로 개발 착수 전 정합을 권고한다. 낮음(low) 10건은 표기·명문화 수준의 이격으로 기능 결함은 없으나 구현 담당자에게 서면 공지하고 문서 정합을 완료한다.

---

## ② 심각도별 요약

| 심각도 | 건수 | 핵심 내용 |
|---|---|---|
| **높음(high)** | **0건** | 해당 없음 |
| **중간(medium)** | **3건** | ① AML-RA-002 ① 버전 목록 테이블 컬럼 헤더 불일치 — PRD 정본(`버전/상태/factor 수/작성자/작성일/동작`)과 생성기(`버전/상태/활성화일/factor 수/작성자/""`) 간 컬럼 순서·명칭 모두 다름. ② pp_001 기본팩 구성 표 첫 번째 영역 행 라벨·설명 불일치 — 생성기 `"CDD"`·`"고객확인·실소유자·자금출처/거래목적"` vs PRD `"CDD / 재심사"`·`"고객확인·실소유자(UBO)·자금출처 · 등급별 재심사 주기"`. ③ FDS BR-003 미계약 시 비활성 조건 — 생성기 tnt_002_policy 테이블 행에 `미계약 시 [▸켜기] 비활성` 상태 미표현. |
| **낮음(low)** | **10건** | ① AML KR_DEFAULT baseline 파라미터 항목 수 불일치(PRD §13.2 ④ 데이터 항목 표에 2개만 명시, SW §14.3은 4개) ② PRD §19.1 영역 목록 외 `RA임계`를 독립 영역으로 추가 표기 ③ AML-RA-002 ① 버전 목록 `동작` 컬럼 헤더 빈 문자열 ④ pp_001 info_panel 영역 목록 RCA 누락 ⑤ tnt_002_policy 확장 Policy Pack 패널에 PRD 미정의 `추가 방식` 행 추가 ⑥ pp_001 적용 Policy Pack 패널에 PRD 미정의 `적용 시점` 행 추가 ⑦ TNT-002 ④ BR-004 드릴다운 버튼 라벨 PRD 내부 불일치(`기본팩 전체 보기 ▶` vs `기본팩 전체·확장·버전 이력 ▶`) ⑧ FDS PRD 맺음말 버전 포인터 stale(v3.1·v4.6·DB v1.3·API v1.5) ⑨ FDS PRD §1.1 서비스 경계 패키지 루트 설계 표기/구현 구분 주석 누락 ⑩ FDS PRD [→ SFDS-REG-001 규제 보고] 드릴다운 독립 행 vs 생성기 복합 callout 단일 bullet 혼합. |

---

## ③ 대조쌍별 이격 표

### [aml:sw-prd-policypack] AML — 설계서 ↔ PRD 정책팩

| 심각도 | 항목 | 이격 내용 | 위치 | 권고 |
|---|---|---|---|---|
| 낮음 | KR_DEFAULT baseline 파라미터 항목 수 불일치 — PRD §13.2 ④ 데이터 항목 표에 2개만 명시 | SW §14.3은 KR_DEFAULT baseline parameter를 4개로 정본화한다: `ctrThreshold`(1,000만원), `raHighThreshold`(0.75), `travelRuleThreshold`(100만원 상당), `structuringThreshold`(9,000만원/7일). PRD §13.2 ④ 데이터 항목 표(lines 1462-1466)는 `ctrThreshold`와 `raHighThreshold` 2개만 포함한다. `travelRuleThreshold`와 `structuringThreshold`는 데이터 항목 표에 없다. TNT-002 ④ 화면 와이어프레임(line 1450)에 "Travel Rule 100만원↑"이 기본팩 구성 미리보기 압축 행에 표기되어 있으나 독립 파라미터 행이 아니라 영역 요약 셀이다. PRD §12-A.9(line 1236) ② 기준금액 구성에는 "CTR 고액현금·STR·Travel Rule·분할 의심 임계"를 항목으로 나열하나 수치 데이터 항목 표는 없다. | SW §14.3 (정본) vs PRD §13.2 ④ 정책팩 탭 데이터 항목 표 | PRD §13.2 ④ 데이터 항목 표에 `travelRuleThreshold`(100만원 상당)와 `structuringThreshold`(9,000만원/7일) 2개 파라미터 행을 SW §14.3 기본값과 함께 추가한다. 또는 PRD §12-A.9 ② 기준금액 탭에 4개 파라미터 전수를 수치와 함께 명시하여 SW §14.3과 1:1 정합한다. |
| 낮음 | PRD가 §19.1 영역 목록에 없는 'RA임계'를 독립 영역으로 추가 표기 | SW §19.1 한국 기본 AML policy pack 표(lines 1705-1714)는 8개 영역(CDD/STR/CTR/Sanctions/PEP·RCA/VASP/Privacy/Audit)만 정의한다. PRD §12-A.9(line 1236)의 ③ 영역별 기본 반영 목록에는 "CDD/STR/CTR/Sanctions/PEP·RCA/VASP/**RA임계**/Privacy/Audit"으로 9개를 나열한다. PRD §13.2 ④ 기본팩 구성 미리보기 레이아웃(line 1451)에도 "RA 임계 / Privacy·Audit"이 독립 행으로 표기되어 있다. SW에서 `raHighThreshold`는 §14.3 baseline parameter로 분류되며 §19.1 policy pack 영역(규제·컴플라이언스 기능 범주)과는 별개 계층이다. PRD가 파라미터를 영역 목록과 같은 레벨로 혼용하는 것은 정본 §19.1과 불일치한다. | SW §19.1 (정본 8개 영역) vs PRD §12-A.9 ③ 영역별 기본 반영 / PRD §13.2 ④ 기본팩 구성 미리보기 | PRD §12-A.9 ③ 영역별 기본 반영 목록과 §13.2 ④ 기본팩 구성 미리보기에서 'RA임계'를 영역 항목에서 제거하고, `raHighThreshold`는 ② 기준금액(파라미터) 섹션에서 다루도록 소관을 분리한다. 영역 목록은 SW §19.1 8개 영역(CDD/STR/CTR/Sanctions/PEP·RCA/VASP/Privacy/Audit)에 맞춘다. |

---

### [aml:prd-ppt-ra] AML — PRD ↔ PPT 생성기 RA

| 심각도 | 항목 | 이격 내용 | 위치 | 권고 |
|---|---|---|---|---|
| 중간 | AML-RA-002 ① 버전 목록 — 컬럼 헤더 불일치: `작성일` vs `활성화일` | PRD 컬럼 헤더 5번째는 `작성일`(DRAFT 생성일)이고 `활성화일` 컬럼이 없다. 생성기에는 `활성화일`이 3번째 위치(상태 바로 다음)로 추가되어 있고 `작성일`이 없다. 또한 PRD 마지막 컬럼 `동작`이 생성기에서 빈 문자열 `""`로 선언되어 표시 라벨이 누락되어 있다. 컬럼 순서도 다르다(PRD: factor 수→작성자→작성일; 생성기: 활성화일→factor 수→작성자). | PRD §6.1 버전 목록 테이블 헤더 (`버전 / 상태 / factor 수 / 작성자 / 작성일 / 동작`) vs `generate_aml.py` `ra_002` tab=0 line 625 (`["버전", "상태", "활성화일", "factor 수", "작성자", ""]`) | 생성기 `ra_002` tab=0의 헤더를 PRD 정본(`버전 / 상태 / factor 수 / 작성자 / 작성일 / 동작`)과 일치하도록 수정하거나, PRD §6.1 버전 목록 테이블 헤더에 `활성화일`을 추가하고 컬럼 순서를 생성기 기준으로 정합해야 한다. 어느 쪽을 정본으로 삼든 양쪽 파일을 동일하게 맞춰야 한다. |
| 낮음 | AML-RA-002 ① 버전 목록 — `동작` 컬럼 헤더 빈 문자열 | PRD 버전 목록 테이블 헤더에는 `동작` 컬럼이 명시되어 있으나, 생성기에서는 빈 문자열 `""`로 선언되어 있어 PPT 슬라이드 렌더 시 동작 컬럼 헤더 라벨이 공백으로 출력된다. | `generate_aml.py` `ra_002` tab=0 line 625: 헤더 배열 마지막 원소 `""` vs PRD §6.1 `동작` | 생성기 헤더 배열 마지막 원소를 `""` → `"동작"`으로 수정하여 PRD와 일치시킨다. |

---

### [aml:prd-ppt-policypack] AML — PRD ↔ PPT 생성기 정책팩

| 심각도 | 항목 | 이격 내용 | 위치 | 권고 |
|---|---|---|---|---|
| 중간 | pp_001 기본팩 구성 표 ① 영역 라벨 및 설명값 불일치 | `generate_aml.py`의 pp_001 첫 번째 영역 행이 `["CDD", "고객확인·실소유자·자금출처/거래목적"]`인 반면, PRD §13.2 ④ ASCII 와이어프레임(line 1448)과 같은 파일 tnt_002_policy(line 215)는 `["CDD / 재심사", "고객확인·실소유자(UBO)·자금출처 · 등급별 재심사 주기"]`를 사용. 구체적으로 ①영역 라벨에서 `/ 재심사` 누락, ②설명값에서 `(UBO)` 괄호 병기 누락, `등급별 재심사 주기` 누락, `거래목적` 추가(PRD 미명시). | `generate_aml.py` line 1404 (pp_001 tab=0 table row 1) vs PRD §13.2 ④ ASCII wireframe line 1448 / §12-A.9 BR-003 | pp_001 tab=0 table row 1을 `["CDD / 재심사", "고객확인·실소유자(UBO)·자금출처 · 등급별 재심사 주기"]`로 수정하여 PRD §13.2 ④ ASCII 와이어프레임 및 tnt_002_policy 기본팩 표와 일치시킨다. |
| 낮음 | pp_001 info_panel 영역 목록에서 RCA 누락 | `generate_aml.py`의 pp_001 info_panel이 `"• 영역 CDD/STR/CTR/Sanctions/PEP/VASP/Privacy/Audit"`으로 표기하여 `RCA`가 빠져 있다. PRD §12-A.9 BR-003은 `"CDD·STR/CTR·Sanctions/PEP·RCA/VASP·Privacy/Audit"`로 `RCA`를 명시하며, 같은 파일 pp_001 table row(line 1406)와 tnt_002_policy info_panel(line 227)도 `RCA`를 포함한다. | `generate_aml.py` line 1417 (pp_001 tab=0 info_panel) vs PRD §12-A.9 BR-003 | pp_001 info_panel의 영역 목록을 `"• 영역 CDD/STR/CTR/Sanctions/PEP·RCA/VASP/RA임계/Privacy/Audit"`으로 수정하여 PRD §12-A.9 BR-003 및 pp_001 table row(line 1406)와 일치시킨다. |
| 낮음 | tnt_002_policy 확장 Policy Pack 패널에 PRD 미정의 `추가 방식` 행 추가 | `generate_aml.py`의 tnt_002_policy 확장 Policy Pack 패널이 `["추가 방식", "기본팩 위에 토글 + 4-eyes"]` 행을 포함하나, PRD §13.2 ④ ASCII 와이어프레임(lines 1444-1447)에는 관할/국가 확장 plugin/업권 확장 plugin 3행만 있고 "추가 방식" 행은 없다. 데이터 항목 표(lines 1460-1466)에도 해당 필드가 정의되지 않았다. | `generate_aml.py` line 211 (tnt_002_policy 확장 Policy Pack panel) vs PRD §13.2 ④ ASCII 와이어프레임 lines 1444-1447 및 데이터 항목 표 lines 1460-1466 | PPT 슬라이드가 PRD 와이어프레임 정의를 초과하지 않도록 "추가 방식" 행을 제거하거나, PRD §13.2 ④ 데이터 항목 표에 해당 항목을 명시적으로 추가한다. |
| 낮음 | pp_001 적용 Policy Pack 패널에 PRD 미정의 `적용 시점` 행 추가 | `generate_aml.py`의 pp_001 tab=0 패널이 `["적용 시점", "2026-05-01"]` 행을 포함하나, PRD §12-A.9 구성에서 PP-001 ① 적용 팩 표시 항목으로 나열된 것은 기본 팩(KR_DEFAULT)·effective 버전·확장 plugin뿐이며, `적용 시점`은 별도 데이터 항목으로 명시되지 않았다. 버전 노트(`v12 (2026-05-01)`)와 중복된 정보다. | `generate_aml.py` line 1396 (pp_001 tab=0 적용 Policy Pack panel) vs PRD §12-A.9 구성 및 §13.2 ④ 데이터 항목 표 | "적용 시점" 행을 제거하거나 PRD §12-A.9에 명시적으로 추가한다. effective 버전 행(`v12 (effective 2026-05-01)`)이 이미 날짜를 포함하므로 중복 제거가 더 간결하다. |

---

### [aml:version-consistency] AML — PRD 내부 버전 일관성

| 심각도 | 항목 | 이격 내용 | 위치 | 권고 |
|---|---|---|---|---|
| 낮음 | TNT-002 ④ 정책팩 탭 드릴다운 버튼 라벨 — BR-004 텍스트 vs 와이어프레임 레이아웃 불일치 | PRD BR-004 본문은 `[기본팩 전체 보기 ▶ → AML-PP-001]`로 기술하나, 동일 섹션의 와이어프레임 레이아웃(line 1452)과 생성기 `tnt_002_policy` callout·info_panel(lines 223, 231)은 `[기본팩 전체·확장·버전 이력 ▶ → AML-PP-001]`로 렌더링한다. PRD 내부에서도 BR-004 규칙 기술과 와이어프레임 ASCII 레이아웃이 서로 다른 라벨을 사용하고 있으며, 생성기는 와이어프레임 쪽을 따른다. | PRD §13.2 ④ BR-004 (line 1473) vs PRD §13.2 ④ 레이아웃 (line 1452) 및 `generate_aml.py` lines 223, 231 | PRD §13.2 ④ BR-004 텍스트의 버튼 라벨을 `[기본팩 전체·확장·버전 이력 ▶ → AML-PP-001]`로 통일하거나, 반대로 와이어프레임·생성기를 `[기본팩 전체 보기 ▶ → AML-PP-001]`로 단순화하는 방향 중 하나로 결정해 PRD와 생성기를 동일하게 맞출 것. |

---

### [fds:sw-prd-policypack] FDS — 설계서 ↔ PRD 정책팩

| 심각도 | 항목 | 이격 내용 | 위치 | 권고 |
|---|---|---|---|---|
| 낮음 | PRD 맺음말(§ 끝, line 2142) 버전 포인터 stale | 맺음말에 '본 기능정의서(v3.1)'·'BO-FDS-SASS-Planning_v4.6.pptx'(45슬라이드)로 고정되어 있으나, 문서 헤더(line 11)는 버전 v3.4·짝 문서 v4.7.pptx를 정본으로 선언함. 설계서 정본 버전 표기도 맺음말은 v1.5·DB v1.3·API v1.5 인용이지만 v3.4 변경이력에서 DB v1.4·API v1.6으로 이미 갱신됨. | `/Users/smkim/workspace/smkim89/aml-system-docs/docs/plan/01-fds-sass-functional-spec.md:2142` | 맺음말의 '본 기능정의서(v3.1)' → 'v3.4', '01-fds-db.md v1.3' → 'v1.4', '01-fds-api.md v1.5' → 'v1.6', 'BO-FDS-SASS-Planning_v4.6.pptx' → 'v4.7.pptx'로 갱신. PRD 문서 정보 표 헤더와 동기화. |
| 낮음 | PRD §1.1 서비스 경계 — fds-svc 패키지 루트 설계 표기/구현 구분 누락 | PRD §1.1 서비스 경계 주석에 fds-svc 엔진을 'com.hanpass.fds 헥사고날'로만 기재. 설계서 §6.2는 'com.hanpass.fds = 설계 표기(design notation), 구현(aegis-aml) 패키지 루트는 com.aegis.fds'임을 명시하고 있으나 PRD에는 그 구분 주석이 없음. Policy Pack 모델 내용 자체는 영향 없으나 엔진 패키지명 혼선 가능성 있음. | `/Users/smkim/workspace/smkim89/aml-system-docs/docs/plan/01-fds-sass-functional-spec.md:65` | PRD §1.1의 'com.hanpass.fds 헥사고날' 뒤에 '(설계 표기; 구현 패키지 루트는 com.aegis.fds — 설계서 §6.2)' 주석을 추가하거나, 설계서 §6.2의 구분 표기를 그대로 인용. |

---

### [fds:prd-ppt-policypack] FDS — PRD ↔ PPT 생성기 정책팩

| 심각도 | 항목 | 이격 내용 | 위치 | 권고 |
|---|---|---|---|---|
| 중간 | BR-003 미계약 시 비활성 조건 — Travel Rule / PCI 토글 `[▸켜기]` 비활성화 상태 미표현 | PRD BR-003: "Travel Rule / PCI는 해당 비즈니스 도메인 계약 후에만 토글 ON 가능(미계약 시 비활성)." — 계약이 없으면 `[▸켜기]` 버튼이 비활성(disabled/grayed) 상태임을 명시. 생성기 테이블 행은 "○ OFF  [▸켜기]*"로만 표기하며 미계약 시 버튼 비활성 상태를 표시하지 않고, callout·info_panel 어디에도 "미계약 시 비활성" 조건이 없음. | PRD §3.2 ④ BR-003 (line 608) vs `generate_fds.py` tnt_002_policy table row (line 236) + info_panel (line 247) | tnt_002_policy 테이블 행에서 Travel Rule / PCI 토글 상태 셀을 "○ OFF  [▸켜기 비활성]*"(미계약 상태) 또는 callout에 "미계약 시 [▸켜기] 버튼 비활성(disabled)" 조건을 추가하여 BR-003의 UI 상태 명세를 재현. |
| 낮음 | `[→ SFDS-REG-001 규제 보고]` 드릴다운 — PRD 와이어프레임 내 전용 행 vs 생성기 복합 callout 한 줄에 혼합 | PRD 와이어프레임(스테이징 블록): "각 팩이 생성하는 보고 후보 큐 → [→ SFDS-REG-001 규제 보고]"를 독립된 전용 줄로 표시. 생성기 callout 241번 줄은 한국 기본팩 잠금 안내 + Travel Rule/PCI 계약 조건 + 드릴다운을 단일 bullet에 결합: "한국 기본팩 잠금(필수·끄기 불가) · Travel Rule/PCI는 도메인 계약 후 · 보고 후보 큐 [→ SFDS-REG-001 규제 보고]". PRD 데이터항목 표에도 "규제 보고 드릴다운"을 독립 항목으로 정의(line 602). | PRD §3.2 ④ 와이어프레임 line 590 vs `generate_fds.py` tnt_002_policy callout line 241 | tnt_002_policy callout에서 `[→ SFDS-REG-001 규제 보고]` 드릴다운을 별도 bullet으로 분리하여 PRD 와이어프레임의 전용 행 구조를 재현. 예: callout 마지막 bullet을 "각 팩 보고 후보 큐 → [→ SFDS-REG-001 규제 보고] (읽기)"로 독립 추가. |

---

## ④ 결론 (개발/확정 가능 여부)

### 판정: 개발 착수 가능 (PASS)

높음(high) 이격 0건, 미검증 항목 0건으로 블로킹 이슈가 없다. 개발 착수를 허가한다.

**중간(medium) 3건**은 개발 착수 전 정합을 권고한다. 특히 AML-RA-002 버전 목록 컬럼 헤더 불일치(컬럼 순서·명칭 전면 상이)와 pp_001 기본팩 구성 표 CDD 행 라벨·설명 불일치는 PPT 슬라이드 품질 직결 항목이므로 우선 처리한다.

| 우선순위 | 항목 | 해소 담당 | 핵심 조치 |
|---|---|---|---|
| 1 | AML-RA-002 버전 목록 컬럼 헤더 불일치 | PPT 생성기 담당 | `generate_aml.py` `ra_002` tab=0 헤더를 PRD §6.1 정본(`버전/상태/factor 수/작성자/작성일/동작`)으로 통일하거나 반대 방향으로 PRD 정합 |
| 2 | pp_001 CDD 영역 행 라벨·설명 불일치 | PPT 생성기 담당 | `generate_aml.py` pp_001 tab=0 table row 1을 `["CDD / 재심사", "고객확인·실소유자(UBO)·자금출처 · 등급별 재심사 주기"]`로 수정 |
| 3 | FDS BR-003 미계약 시 비활성 조건 미표현 | PPT 생성기 담당 | `generate_fds.py` tnt_002_policy 테이블 행 또는 callout에 `미계약 시 [▸켜기] 비활성` 조건 추가 |

**낮음(low) 10건**은 표기·명문화 수준으로 기능 결함은 없으나 개발 착수 직전까지 정합을 완료하고 구현 담당자에게 서면 공지한다. KR_DEFAULT baseline 파라미터 4개 전수 명시 및 FDS PRD 맺음말 버전 갱신은 문서 신뢰성에 직결되므로 중간 3건 해소와 병행 처리를 권고한다.

> 중간(medium) 3건 해소 완료 후 `doc-consistency-qa` 워크플로를 재실행하여 최종 PASS 여부를 재확인한다.
