# 메뉴 IA 운영/설정 재구성 — PRD + PPT 수정 실행계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** FDS·AML 백오피스 메뉴를 `운영(OPERATIONS) / 설정(CONFIGURATION)` 2영역 × 기능그룹 × 메뉴 3단 IA로 재구성하고, 정본 PRD와 PPT(FDS v8.0 / AML v9.0)를 일치시킨다.

**Architecture:** 메뉴 트리는 PPT 생성기(`generate_fds.py`·`generate_aml.py`)의 NAV 데이터와 `wireframe_lib.nav_tree()` 렌더가 정본 시각화이고, PRD 마크다운에 신규 `정보구조(IA)·메뉴 체계` 섹션 + 화면 인벤토리 표(영역/기능그룹 열)가 정본 텍스트다. 화면 콘텐츠 함수는 불변 — 변경은 **NAV 구조·슬라이드 호출 순서·소속 그룹 표기**뿐. AML은 혼재 메뉴(TM 알림/시나리오, RA 운영/모델, CDD 프로필/정책, WLF/명단소스)를 화면 ID 단위로 운영/설정에 분리한다.

**Tech Stack:** Python 3 + python-pptx, `wireframe_lib.py` 컴포넌트, LibreOffice(`soffice`) + `pdftoppm` 렌더 검증, Markdown PRD.

스펙: `docs/superpowers/specs/2026-06-18-menu-ia-operation-setting-design.md`

---

## File Structure

- Modify: `.claude/skills/backoffice-planner/wireframe_lib.py` — `nav_tree()` 신규 추가(기존 `nav_panel()` 유지)
- Modify: `.claude/skills/backoffice-planner/generate_fds.py` — NAV 트리/active 교체, `SCREENS` 재정렬, 버전 v8.0
- Modify: `.claude/skills/backoffice-planner/generate_aml.py` — NAV 트리/active 분리 교체, `SCREENS` 재정렬, 버전 v9.0
- Create: `docs/plan/BO-FDS-SASS-Planning_v8.0.pptx` — 재생성 산출물
- Create: `docs/plan/BO-AML-SAAS-Planning_v9.0.pptx` — 재생성 산출물
- Modify: `docs/plan/01-fds-sass-functional-spec.md` — §1.0 IA 섹션 신설, TOC, §16.1 인벤토리 표, 변경 이력
- Modify: `docs/plan/02-aml-sass-functional-spec.md` — IA 섹션 신설, TOC, 인벤토리 표(혼재 분리), 변경 이력

> **설계 결정(낮은 churn):** 기존 §2~§15(FDS)·§2~§12(AML) 섹션 **번호는 재배열하지 않는다**(자기참조·딥링크 다수 → 고위험). 메뉴 순서 정본은 (1) 신규 IA 섹션 (2) 화면 인벤토리 표 (3) 생성기 SCREENS 순서가 가진다. 본문 섹션에는 "소속 영역/그룹" 한 줄만 보강한다.

---

## Task 1: `nav_tree()` 컴포넌트 추가 (wireframe_lib.py)

**Files:**
- Modify: `.claude/skills/backoffice-planner/wireframe_lib.py` (기존 `nav_panel` 바로 아래, 현재 116행 직후)

- [ ] **Step 1: `nav_tree()` 함수 추가**

`wireframe_lib.py`의 `nav_panel()` 정의가 끝나는 줄(현재 115행, `text(... i == active)])` 다음 빈 줄) 뒤에 아래 함수를 추가한다. 좌표 상수(`NAV_X`, `NAV_W`, `C`)·`rect`/`text` 헬퍼는 기존 파일 것을 그대로 쓴다.

```python
def nav_tree(slide, areas, active_key=None):
    """2영역(운영/설정)·3단(영역→기능그룹→메뉴) NAV.
    areas: [(area_label, [(group_label, [(menu_label, key), ...]), ...]), ...]
    active_key 와 일치하는 menu key 행을 하이라이트하고 active 색을 입힌다.
    행 수에 따라 step·폰트를 동적 축소해 6.12in 패널 안에 항상 수용."""
    rect(slide, NAV_X, 1.18, NAV_W, 6.12, C["panel"], line=C["border"], line_w=0.5)
    rows = 0
    for _, groups in areas:
        rows += 1
        for _, menus in groups:
            rows += 1 + len(menus)
    step = min(0.255, 6.00 / max(rows, 1))
    fs = 8.0 if rows > 24 else 9.0
    y = 1.27
    for area_label, groups in areas:
        rect(slide, NAV_X, y - 0.02, NAV_W, step - 0.01, C["blue"])
        text(slide, NAV_X + 0.08, y, NAV_W - 0.12, step - 0.02,
             [("▼ " + area_label, fs + 1.0, C["white"], True)], wrap=False)
        y += step
        for group_label, menus in groups:
            text(slide, NAV_X + 0.12, y, NAV_W - 0.18, step - 0.02,
                 [("▸ " + group_label, fs, C["mute"], True)], wrap=False)
            y += step
            for menu_label, key in menus:
                on = (key == active_key)
                if on:
                    rect(slide, NAV_X, y - 0.01, NAV_W, step - 0.01, C["active"])
                col = C["blue"] if on else C["text"]
                text(slide, NAV_X + 0.28, y, NAV_W - 0.34, step - 0.02,
                     [(menu_label, fs, col, on)], wrap=False)
                y += step
```

- [ ] **Step 2: 구문 검증**

Run: `cd /Users/smkim/workspace/smkim89/aml-system-docs/.claude/skills/backoffice-planner && python3 -c "import wireframe_lib as wf; print(hasattr(wf,'nav_tree'))"`
Expected: `True` (구문 오류 없이 import 성공)

- [ ] **Step 3: Commit**

```bash
git -C /Users/smkim/workspace/smkim89/aml-system-docs add .claude/skills/backoffice-planner/wireframe_lib.py
git -C /Users/smkim/workspace/smkim89/aml-system-docs commit -m "feat(ppt-lib): 2영역·3단 NAV 렌더 nav_tree() 추가"
```

---

## Task 2: FDS 생성기 NAV/순서 교체 (generate_fds.py)

**Files:**
- Modify: `.claude/skills/backoffice-planner/generate_fds.py:15-21` (NAV/ACTIVE), `:28` (frame nav 호출), `SCREENS` 블록, `build()` 커버·변경이력·출력경로

- [ ] **Step 1: NAV/ACTIVE 정의 교체 (15~21행)**

현재 15~21행:
```python
NAV = ["플랫폼 대시보드", "고객사 관리", "커넥터 관리", "스키마·매핑", "룰 관리",
       "그룹·명단", "탐지 결정", "이벤트 조회", "액션 운영", "케이스 관리",
       "결재함", "규제 보고", "Evidence", "감사 로그"]
# 기능 ID prefix → NAV active 인덱스
ACTIVE = {"DASH": 0, "TNT": 1, "CONN": 2, "MAP": 3, "RULE": 4, "STAT": 4,
          "GRP": 5, "DEC": 6, "EVT": 7, "ACT": 8, "CASE": 9, "APPR": 10,
          "REG": 11, "EXP": 12, "AUDIT": 13}
```
를 아래로 교체:
```python
# 2영역·3단 NAV (운영/설정) — leaf key = 기능 ID prefix
NAV = [
    ("운영", [
        ("조사·모니터링", [("플랫폼 대시보드", "DASH"), ("탐지 결정", "DEC"),
                          ("이벤트 조회", "EVT"), ("룰 효과 통계", "STAT")]),
        ("케이스·처리", [("케이스 관리", "CASE"), ("액션 운영", "ACT")]),
        ("거버넌스·보고", [("결재함", "APPR"), ("규제 보고", "REG")]),
    ]),
    ("설정", [
        ("연동·데이터", [("고객사 관리", "TNT"), ("커넥터 관리", "CONN"),
                        ("스키마·매핑", "MAP")]),
        ("탐지 정책", [("룰 관리", "RULE"), ("그룹·명단", "GRP")]),
        ("감사·증적", [("감사 로그", "AUDIT"), ("Evidence", "EXP")]),
    ]),
]
```

- [ ] **Step 2: frame()의 nav 호출 교체 (현재 28행)**

현재:
```python
    wf.nav_panel(s, NAV, active=ACTIVE[sid.split("-")[1]])
```
를:
```python
    wf.nav_tree(s, NAV, active_key=sid.split("-")[1])
```

- [ ] **Step 3: SCREENS 재정렬 (운영→설정 순)**

기존 `SCREENS = [...]` 블록 전체를 아래로 교체(같은 함수·lambda를 순서만 운영/설정으로 재배열, 화면 누락·추가 없음):
```python
SCREENS = [
    # ── 운영: 조사·모니터링 ──
    dash_001, dash_002,
    dec_001, dec_002, dec_003,
    evt_001,
    lambda p: stat_001(p, 0), lambda p: stat_001(p, 1),
    # ── 운영: 케이스·처리 ──
    case_001, case_002, case_002_timeline, case_002_decisions, case_002_comments,
    act_001, act_002,
    # ── 운영: 거버넌스·보고 ──
    appr_001, reg_001, reg_002,
    # ── 설정: 연동·데이터 ──
    tnt_001, tnt_002_basic, tnt_002_deploy, tnt_002_security, tnt_002_policy, tnt_002_notify,
    tnt_003,
    conn_001, conn_002, conn_003,
    lambda p: conn_004(p, 0), lambda p: conn_004(p, 1),
    map_001, map_002,
    # ── 설정: 탐지 정책 ──
    rule_001, rule_002, rule_002_versions, rule_002_threshold, rule_002_hits, rule_002_approval_log,
    rule_003, rule_004, rule_005, rule_006,
    grp_001, grp_002, grp_003,
    # ── 설정: 감사·증적 ──
    audit_001, exp_001,
]
```

- [ ] **Step 4: 커버/변경이력/출력경로 버전 v8.0 (build())**

`build()` 안:
1. 출력 경로(현재 `..._v7.0.pptx`)를 `BO-FDS-SASS-Planning_v8.0.pptx`로 변경:
```python
    out = "/Users/smkim/workspace/smkim89/aml-system-docs/docs/plan/BO-FDS-SASS-Planning_v8.0.pptx"
```
2. 커버 마지막 불릿(현재 `"버전 BO-FDS-SASS-Planning v7.0 ..."`)을 교체:
```python
         "버전 BO-FDS-SASS-Planning v8.0 (메뉴 IA 운영/설정 2영역·3단 재구성 — 34화면 불변, NAV·순서 변경)"])
```
3. 커버 시나리오 불릿(현재 `"목록→상세→액션→케이스→결재→규제 보고 시나리오 흐름 연결(딥링크 전수)"`) 앞 또는 뒤에 영역 설명 추가는 생략 가능. 단, 시나리오 불릿은 그대로 유지.
4. `history_slide(...)` 의 행 리스트 마지막(`["v7.0", ...]` 다음)에 추가:
```python
         ["v8.0", "2026-06-19", "SM Kim", "메뉴 IA 재구성 — 운영(조사·모니터링/케이스·처리/거버넌스·보고)·설정(연동·데이터/탐지 정책/감사·증적) 2영역 3단 분리, NAV·슬라이드 순서 재정렬(34화면·콘텐츠 불변), nav_tree 렌더"]],
```
(주의: 기존 리스트 마지막 항목의 닫는 `]` 위치를 정확히 맞춰 새 행을 append. 기존 마지막 `... 34화면)"]]` 의 안쪽 `]` 앞에 콤마+새 행 삽입.)

- [ ] **Step 5: 생성 실행 + 슬라이드 수 확인**

Run: `cd /Users/smkim/workspace/smkim89/aml-system-docs/.claude/skills/backoffice-planner && python3 generate_fds.py`
Expected: `saved /Users/.../BO-FDS-SASS-Planning_v8.0.pptx · slides=49`
(슬라이드 수 49 유지 = 화면 무손실. 49가 아니면 SCREENS 누락/중복 → Step 3 재확인)

- [ ] **Step 6: NAV·순서 렌더 검증**

Run:
```bash
cd /Users/smkim/workspace/smkim89/aml-system-docs/docs/plan && \
soffice --headless --convert-to pdf BO-FDS-SASS-Planning_v8.0.pptx --outdir /tmp/fdsppt >/dev/null 2>&1 && \
pdftoppm -png -r 90 -f 3 -l 3 /tmp/fdsppt/BO-FDS-SASS-Planning_v8.0.pdf /tmp/fdsppt/s
```
그 뒤 Read 도구로 `/tmp/fdsppt/s-03.png`(첫 기능 슬라이드=SFDS-DASH-001) 확인.
Expected: 좌측 NAV가 `▼ 운영` 영역 헤더 → `▸ 조사·모니터링` 그룹 → `플랫폼 대시보드`(하이라이트)·탐지 결정·이벤트 조회·룰 효과 통계, 이어서 케이스·처리/거버넌스·보고, `▼ 설정` 영역 → 연동·데이터/탐지 정책/감사·증적 순으로 표시. NAV 항목 겹침·넘침 없음. 우측 info_panel·본문 콘텐츠 정상.

- [ ] **Step 7: Commit**

```bash
git -C /Users/smkim/workspace/smkim89/aml-system-docs add .claude/skills/backoffice-planner/generate_fds.py docs/plan/BO-FDS-SASS-Planning_v8.0.pptx
git -C /Users/smkim/workspace/smkim89/aml-system-docs commit -m "feat(ppt-fds): 메뉴 IA 운영/설정 2영역 재구성 + v8.0 재생성"
```

---

## Task 3: FDS PRD 메뉴 정본 갱신 (01-fds-sass-functional-spec.md)

**Files:**
- Modify: `docs/plan/01-fds-sass-functional-spec.md` — §1.0 신설(현재 `## 1. 개요`(66행) 직전), TOC(`## 목차` 45행), §16.1 인벤토리 표, 변경 이력 표(17행 영역)

- [ ] **Step 1: IA 섹션 신설 — `## 1. 개요`(66행) 바로 앞에 삽입**

```markdown
## 1.0 정보구조(IA)·메뉴 체계 (정본)

좌측 NAV는 **운영(OPERATIONS) / 설정(CONFIGURATION)** 2영역으로 분리하며, 각 영역은 기능그룹 → 메뉴 3단으로 구성한다. 운영 영역이 위, 설정 영역이 아래. 운영자가 매일 쓰는 탐지·조사·케이스가 상단에 오고, 셋업·정책 화면은 설정 영역으로 내린다. 상세 화면은 NAV 항목이 아니라 목록 행/버튼 드릴다운으로 진입한다.

| 영역 | 기능그룹 | 메뉴(화면 ID) |
|---|---|---|
| **운영** | 조사·모니터링 | 플랫폼 대시보드(SFDS-DASH-001/002) · 탐지 결정(SFDS-DEC-001/002/003) · 이벤트 조회(SFDS-EVT-001) · 룰 효과 통계(SFDS-STAT-001) |
| **운영** | 케이스·처리 | 케이스 관리(SFDS-CASE-001/002) · 액션 운영(SFDS-ACT-001/002) |
| **운영** | 거버넌스·보고 | 결재함(SFDS-APPR-001) · 규제 보고(SFDS-REG-001/002) |
| **설정** | 연동·데이터 | 고객사 관리(SFDS-TNT-001/002/003) · 커넥터 관리(SFDS-CONN-001~004) · 스키마·매핑(SFDS-MAP-001/002) |
| **설정** | 탐지 정책 | 룰 관리(SFDS-RULE-001~006) · 그룹·명단(SFDS-GRP-001/002/003) |
| **설정** | 감사·증적 | 감사 로그(SFDS-AUDIT-001) · Evidence(SFDS-EXP-001) |

> 본문 §2~§15 섹션 번호는 역사적 호환을 위해 유지된다. 메뉴 순서·소속 영역의 정본은 본 표(§1.0) · §16.1 인벤토리 · 짝 PPT(NAV)다.
```

- [ ] **Step 2: TOC에 §1.0 줄 추가**

`## 목차`(45행) 블록에서 `1. 개요` 항목 줄 바로 위에 추가:
```markdown
- [1.0 정보구조(IA)·메뉴 체계](#10-정보구조ia메뉴-체계-정본)
```
(기존 TOC 표기 양식이 다르면 동일 양식으로 맞춘다. 예: 번호 목록이면 `- 1.0 정보구조(IA)·메뉴 체계`.)

- [ ] **Step 3: §16.1 화면 인벤토리 표에 영역/그룹 반영**

`grep -n "16.1" docs/plan/01-fds-sass-functional-spec.md` 로 §16.1 표 위치 확인 후, 표의 행 순서를 §1.0 표 순서(운영→설정)로 재정렬하고, 표 맨 앞에 `영역`·`기능그룹` 두 열을 추가한다. 각 행의 영역/그룹은 §1.0 표 매핑을 따른다. (열 추가가 표 폭상 부담이면 기존 그룹 열을 `영역 › 기능그룹` 합성 표기로 대체.)

- [ ] **Step 4: 변경 이력 표에 v6.0 행 추가**

변경 이력 표(현재 최신 `5.0`/`4.0` 행이 21·22행)에 최신 행으로 추가(표 최상단 = 최신 관례 따름):
```markdown
| **6.0** | **2026-06-19** | **SM Kim** | **메뉴 IA 운영/설정 2영역 재구성 — §1.0 정보구조·메뉴 체계 신설(운영: 조사·모니터링/케이스·처리/거버넌스·보고, 설정: 연동·데이터/탐지 정책/감사·증적), §16.1 인벤토리에 영역/기능그룹 열 추가·순서 재정렬. 화면 34종·콘텐츠 불변. 짝 PPT `BO-FDS-SASS-Planning_v8.0.pptx` 재빌드(nav_tree 2영역·3단 NAV).** |
```
(`## 문서 정보`의 PRD 버전 핀이 별도로 있으면 v6.0으로 동기화.)

- [ ] **Step 5: 정합 확인**

Run: `grep -c "정보구조(IA)" docs/plan/01-fds-sass-functional-spec.md`
Expected: `≥ 1`
Run: `grep -n "v8.0\|BO-FDS-SASS-Planning_v8.0" docs/plan/01-fds-sass-functional-spec.md | head`
Expected: 변경 이력에 PPT v8.0 참조 등장.

- [ ] **Step 6: Commit**

```bash
git -C /Users/smkim/workspace/smkim89/aml-system-docs add docs/plan/01-fds-sass-functional-spec.md
git -C /Users/smkim/workspace/smkim89/aml-system-docs commit -m "docs(fds-prd): §1.0 IA 운영/설정 메뉴 체계 신설 + 인벤토리 정합(v6.0)"
```

---

## Task 4: AML 생성기 NAV/순서 교체 + 혼재 분리 (generate_aml.py)

**Files:**
- Modify: `.claude/skills/backoffice-planner/generate_aml.py:17-25` (NAV/NAVIDX), `:32` (frame nav 호출), `SCREENS`(2180-2244), `build()`(출력 2290·커버 2258·변경이력)

- [ ] **Step 1: NAV/active 정의 교체 (17~25행)**

현재 17~25행(`NAV = [...]` + `NAVIDX = {...}`)을 아래로 교체. AML은 혼재 메뉴를 화면 ID로 분리하므로 leaf key 일부는 `PREFIX-NUM` 단위다:
```python
# 2영역·3단 NAV (운영/설정). 혼재 메뉴는 화면 ID 단위로 분리.
NAV = [
    ("운영", [
        ("조사·모니터링", [("AML 종합 대시보드", "DASH"), ("WLF 검토", "WLF"),
                          ("TM 알림", "TM-001"), ("통계", "STAT")]),
        ("고객위험·심사", [("RA 분포·고객위험", "RA-OPS"), ("고객 프로필", "CDD-002"),
                          ("고위험 등록부", "HRR")]),
        ("케이스·처리", [("케이스 관리", "CASE"), ("Travel Rule 예외", "TR")]),
        ("거버넌스·보고", [("규제 보고 STR/CTR", "REP"), ("기관 RBA 보고", "IRA"),
                          ("결재 대기함", "APR")]),
    ]),
    ("설정", [
        ("연동·데이터", [("고객사 관리", "TNT"), ("Ingest 카탈로그", "ING"),
                        ("명단 소스·임포트", "WL")]),
        ("탐지·심사 정책", [("TM 시나리오 빌더", "TM-002"), ("RA 모델 관리", "RA-002"),
                          ("CDD 체크리스트 정책", "CDD-001"), ("국가위험 관리", "CTRY"),
                          ("Policy Pack", "PP")]),
        ("감사·증적·내부통제", [("내부통제 교육", "EDU"), ("감사·증적", "AUD")]),
    ]),
]
# 화면 ID(PREFIX 또는 PREFIX-NUM) → NAV leaf key
NAVKEY = {
    "DASH": "DASH", "TNT": "TNT", "WLF": "WLF", "WL": "WL", "CTRY": "CTRY",
    "HRR": "HRR", "CASE": "CASE", "REP": "REP", "IRA": "IRA", "TR": "TR",
    "PP": "PP", "APR": "APR", "STAT": "STAT", "EDU": "EDU", "AUD": "AUD", "ING": "ING",
    # 혼재 분리(화면 ID 단위)
    "RA-001": "RA-OPS", "RA-003": "RA-OPS", "RA-002": "RA-002",
    "CDD-002": "CDD-002", "CDD-001": "CDD-001",
    "TM-001": "TM-001", "TM-002": "TM-002",
}


def aml_active(sid):
    """sid 예: 'AML-RA-002' → base 'RA-002' 우선, 없으면 prefix 'RA'."""
    parts = sid.split("-")
    base = parts[1] + "-" + parts[2] if len(parts) >= 3 else parts[1]
    return NAVKEY.get(base) or NAVKEY.get(parts[1])
```

- [ ] **Step 2: frame()의 nav 호출 교체 (현재 32행)**

현재:
```python
    wf.nav_panel(s, NAV, active=NAVIDX[sid.split("-")[1]])
```
를:
```python
    wf.nav_tree(s, NAV, active_key=aml_active(sid))
```

- [ ] **Step 3: SCREENS 재정렬 (2180-2244 전체 교체)**

기존 `SCREENS = [...]`(2180~2244) 전체를 아래로 교체. lambda/탭 호출은 보존, 순서만 운영→설정으로 재배열:
```python
SCREENS = [
    # ── 운영: 조사·모니터링 ──
    dash_001,
    wlf_001, wlf_002, wlf_003,
    lambda p: wlf_004(p, 0), lambda p: wlf_004(p, 1),
    lambda p: tm_001(p, 0), lambda p: tm_001(p, 1),
    lambda p: stat_001(p, 0), lambda p: stat_001(p, 1),
    # ── 운영: 고객위험·심사 ──
    lambda p: ra_001(p, 0), lambda p: ra_001(p, 1),
    lambda p: ra_003(p, 0), lambda p: ra_003(p, 1), lambda p: ra_003(p, 2),
    lambda p: cdd_002(p, 0), lambda p: cdd_002(p, 1),
    lambda p: hrr_001(p, 0), lambda p: hrr_001(p, 1),
    # ── 운영: 케이스·처리 ──
    case_001,
    lambda p: case_002(p, 0), lambda p: case_002(p, 1),
    lambda p: case_002(p, 2), lambda p: case_002(p, 3),
    lambda p: tr_001(p, 0), lambda p: tr_001(p, 1), lambda p: tr_001(p, 2),
    # ── 운영: 거버넌스·보고 ──
    lambda p: rep_001(p, 0), lambda p: rep_001(p, 1), lambda p: rep_001(p, 2),
    lambda p: rep_002(p, 0), lambda p: rep_002(p, 1), lambda p: rep_002(p, 2),
    lambda p: ira_001(p, 0), lambda p: ira_001(p, 1), lambda p: ira_001(p, 2),
    apr_001,
    # ── 설정: 연동·데이터 ──
    tnt_001, tnt_002_basic, tnt_002_deploy, tnt_002_source, tnt_002_policy, tnt_003,
    lambda p: ing_001(p, 0), lambda p: ing_001(p, 1),
    lambda p: wl_001(p, 0), lambda p: wl_001(p, 1), lambda p: wl_001(p, 2),
    wl_002, lambda p: wl_003(p, 0), lambda p: wl_003(p, 1),
    # ── 설정: 탐지·심사 정책 ──
    tm_002,
    lambda p: ra_002(p, 0), lambda p: ra_002(p, 1), lambda p: ra_002(p, 2), lambda p: ra_002(p, 3),
    lambda p: cdd_001(p, 0), lambda p: cdd_001(p, 1), lambda p: cdd_001(p, 2),
    lambda p: ctry_001(p, 0), lambda p: ctry_001(p, 1),
    lambda p: pp_001(p, 0), lambda p: pp_001(p, 1),
    # ── 설정: 감사·증적·내부통제 ──
    lambda p: edu_001(p, 0), lambda p: edu_001(p, 1),
    lambda p: aud_001(p, 0), lambda p: aud_001(p, 1), lambda p: aud_001(p, 2),
]
```
> 검증 메모: 위 리스트는 기존 SCREENS의 68개 화면 호출을 순서만 재배열한 것(누락·추가 0). cover+history 2 + 68 = 70슬라이드 보존(아래 Step 5 게이트로 확인).

- [ ] **Step 4: 버전 v9.0 (build())**

1. 출력 경로(2290행) `..._v8.0.pptx` → `BO-AML-SAAS-Planning_v9.0.pptx`:
```python
    out = "/Users/smkim/workspace/smkim89/aml-system-docs/docs/plan/BO-AML-SAAS-Planning_v9.0.pptx"
```
2. 커버 버전 불릿(2258행 `"버전 BO-AML-SAAS-Planning v8.0 ..."`):
```python
         "버전 BO-AML-SAAS-Planning v9.0 (메뉴 IA 운영/설정 2영역·3단 재구성 — 혼재 메뉴 TM/RA/CDD 분리, 32화면 불변)"],
```
3. `history_slide(...)` 행 리스트 마지막 행 다음에 추가(닫는 `]]` 안쪽에 콤마+새 행):
```python
         ["v9.0", "2026-06-19", "Hanpass Global Team", "메뉴 IA 재구성 — 운영(조사·모니터링/고객위험·심사/케이스·처리/거버넌스·보고)·설정(연동·데이터/탐지·심사 정책/감사·증적·내부통제) 2영역 3단. 혼재 메뉴 분리: TM 알림(TM-001)↔시나리오 빌더(TM-002), RA 분포·고객위험(RA-001/003)↔RA 모델(RA-002), 고객 프로필(CDD-002)↔CDD 정책(CDD-001). 32화면·콘텐츠 불변, nav_tree 렌더"]],
```

- [ ] **Step 5: 생성 실행 + 슬라이드 수 확인**

Run: `cd /Users/smkim/workspace/smkim89/aml-system-docs/.claude/skills/backoffice-planner && python3 generate_aml.py`
Expected: `saved /Users/.../BO-AML-SAAS-Planning_v9.0.pptx · slides=70`
(기존 v8.0 70슬라이드 유지 = 무손실. 70이 아니면 SCREENS 항목 누락/중복 → Step 3 재확인)

- [ ] **Step 6: NAV·분리 렌더 검증 (혼재 분리 핵심)**

Run:
```bash
cd /Users/smkim/workspace/smkim89/aml-system-docs/docs/plan && \
soffice --headless --convert-to pdf BO-AML-SAAS-Planning_v9.0.pptx --outdir /tmp/amlppt >/dev/null 2>&1 && \
pdftoppm -png -r 90 -f 3 -l 3 /tmp/amlppt/BO-AML-SAAS-Planning_v9.0.pdf /tmp/amlppt/s
```
Read 도구로 `/tmp/amlppt/s-03.png`(AML-DASH-001) 확인.
Expected: 좌측 NAV `▼ 운영`에 조사·모니터링(AML 종합 대시보드 하이라이트·WLF 검토·TM 알림·통계) / 고객위험·심사(RA 분포·고객위험·고객 프로필·고위험 등록부) / 케이스·처리 / 거버넌스·보고, `▼ 설정`에 연동·데이터 / 탐지·심사 정책(TM 시나리오 빌더·RA 모델 관리·CDD 체크리스트 정책·국가위험·Policy Pack) / 감사·증적·내부통제 표시. TM/RA/CDD가 운영·설정 양쪽에 분리 표기됨. NAV 30행 겹침·넘침 없음(넘치면 Task 1 `nav_tree`의 step/fs 하향 조정).

- [ ] **Step 7: Commit**

```bash
git -C /Users/smkim/workspace/smkim89/aml-system-docs add .claude/skills/backoffice-planner/generate_aml.py docs/plan/BO-AML-SAAS-Planning_v9.0.pptx
git -C /Users/smkim/workspace/smkim89/aml-system-docs commit -m "feat(ppt-aml): 메뉴 IA 운영/설정 재구성 + 혼재 메뉴 TM/RA/CDD 분리 + v9.0 재생성"
```

---

## Task 5: AML PRD 메뉴 정본 갱신 (02-aml-sass-functional-spec.md)

**Files:**
- Modify: `docs/plan/02-aml-sass-functional-spec.md` — IA 섹션 신설(`## 1. 개요` 직전), TOC, 인벤토리(§12-A/§12-B 또는 §1.2 화면 표), 변경 이력(17행 영역)

- [ ] **Step 1: IA 섹션 신설 — `## 1. 개요` 헤더 바로 앞에 삽입**

(`grep -n "^## 1\. " docs/plan/02-aml-sass-functional-spec.md` 로 위치 확인)
```markdown
## 1.0 정보구조(IA)·메뉴 체계 (정본)

좌측 NAV는 **운영(OPERATIONS) / 설정(CONFIGURATION)** 2영역으로 분리하며, 각 영역은 기능그룹 → 메뉴 3단으로 구성한다. 운영자가 매일 쓰는 검토·조사·케이스·보고가 운영 영역(상단), 정책·모델·소스 셋업은 설정 영역(하단)에 위치한다. **운영 동작과 설정이 한 메뉴에 섞여 있던 곳은 화면 ID 단위로 운영/설정에 분리**했다.

| 영역 | 기능그룹 | 메뉴(화면 ID) |
|---|---|---|
| **운영** | 조사·모니터링 | AML 종합 대시보드(AML-DASH-001) · WLF 검토(AML-WLF-001~004) · TM 알림(AML-TM-001) · 통계(AML-STAT-001) |
| **운영** | 고객위험·심사 | RA 분포·고객위험(AML-RA-001/003) · 고객 프로필(AML-CDD-002) · 고위험 등록부(AML-HRR-001) |
| **운영** | 케이스·처리 | 케이스 관리(AML-CASE-001/002) · Travel Rule 예외(AML-TR-001) |
| **운영** | 거버넌스·보고 | 규제 보고 STR/CTR(AML-REP-001/002) · 기관 RBA 보고(AML-IRA-001) · 결재 대기함(AML-APR-001) |
| **설정** | 연동·데이터 | 고객사 관리(AML-TNT-001/002/003) · Ingest 카탈로그(AML-ING-001) · 명단 소스·임포트(AML-WL-001~003) |
| **설정** | 탐지·심사 정책 | TM 시나리오 빌더(AML-TM-002) · RA 모델 관리(AML-RA-002) · CDD 체크리스트 정책(AML-CDD-001) · 국가위험 관리(AML-CTRY-001) · Policy Pack(AML-PP-001) |
| **설정** | 감사·증적·내부통제 | 내부통제 교육(AML-EDU-001) · 감사·증적(AML-AUD-001) |

**혼재 메뉴 분리(운영 ↔ 설정):**

| 기존 단일 메뉴 | → 운영 | → 설정 |
|---|---|---|
| TM 알림·시나리오 | TM 알림(TM-001) | TM 시나리오 빌더(TM-002) |
| RA·CDD | RA 분포·고객위험(RA-001/003), 고객 프로필(CDD-002) | RA 모델 관리(RA-002), CDD 체크리스트 정책(CDD-001) |
| WLF/명단 | WLF 검토(WLF-001~004) | 명단 소스·임포트(WL-001~003) |

> 상세·드릴다운 화면(예: AML-CDD-002, AML-RA-003)은 NAV 직접 항목이자 목록 행 드릴다운으로도 진입한다. 본문 §2~§12 섹션 번호는 유지되며, 메뉴 순서·소속 영역 정본은 본 표(§1.0)·인벤토리·짝 PPT(NAV)다.
```

- [ ] **Step 2: TOC에 §1.0 줄 추가**

`## 목차` 블록의 `1. 개요` 항목 바로 위에 동일 양식으로 추가:
```markdown
- [1.0 정보구조(IA)·메뉴 체계](#10-정보구조ia메뉴-체계-정본)
```

- [ ] **Step 3: 화면 인벤토리 표 정합**

AML 화면 인벤토리(부록 A 또는 §12-A/§12-B 표; `grep -n "부록 A\|화면 인벤\|기능 ID" docs/plan/02-aml-sass-functional-spec.md` 로 위치 확인)에 `영역`·`기능그룹` 열을 추가하거나 비고에 소속을 병기하고, TM-001/TM-002·RA-001·003/RA-002·CDD-002/CDD-001이 운영/설정으로 갈리는 것을 표기한다(§1.0 매핑 일치).

- [ ] **Step 4: 변경 이력 표에 v9.0 행 추가**

변경 이력 표 최상단(최신)에 추가:
```markdown
| **9.0** | **2026-06-19** | **Hanpass Global Team** | **메뉴 IA 운영/설정 2영역 재구성 — §1.0 정보구조·메뉴 체계 신설(운영: 조사·모니터링/고객위험·심사/케이스·처리/거버넌스·보고, 설정: 연동·데이터/탐지·심사 정책/감사·증적·내부통제). 혼재 메뉴를 화면 ID 단위로 분리: TM 알림(TM-001)↔TM 시나리오 빌더(TM-002), RA 분포·고객위험(RA-001/003)↔RA 모델 관리(RA-002), 고객 프로필(CDD-002)↔CDD 체크리스트 정책(CDD-001). 화면 32종·콘텐츠 불변. 짝 PPT `BO-AML-SAAS-Planning_v9.0.pptx` 재빌드(nav_tree 2영역·3단·분리 NAV).** |
```

- [ ] **Step 5: 정합 확인**

Run: `grep -c "정보구조(IA)\|혼재 메뉴 분리" docs/plan/02-aml-sass-functional-spec.md`
Expected: `≥ 2`
Run: `grep -n "BO-AML-SAAS-Planning_v9.0" docs/plan/02-aml-sass-functional-spec.md | head`
Expected: 변경 이력에 PPT v9.0 참조 등장.

- [ ] **Step 6: Commit**

```bash
git -C /Users/smkim/workspace/smkim89/aml-system-docs add docs/plan/02-aml-sass-functional-spec.md
git -C /Users/smkim/workspace/smkim89/aml-system-docs commit -m "docs(aml-prd): §1.0 IA 운영/설정 메뉴 체계 + 혼재 분리 정합(v9.0)"
```

---

## Task 6: 전체 정합 검증 + 브랜치 마무리

**Files:** (검증 전용 — 신규 편집 없음)

- [ ] **Step 1: 두 PPT 슬라이드 수·존재 확인**

Run:
```bash
ls -la /Users/smkim/workspace/smkim89/aml-system-docs/docs/plan/BO-FDS-SASS-Planning_v8.0.pptx \
       /Users/smkim/workspace/smkim89/aml-system-docs/docs/plan/BO-AML-SAAS-Planning_v9.0.pptx
```
Expected: 두 파일 모두 존재(2026-06-19 타임스탬프).

- [ ] **Step 2: 마지막 설정-영역 슬라이드 렌더 확인 (운영→설정 순서 끝단)**

FDS 마지막 슬라이드(=SFDS-EXP-001 Evidence, 설정/감사·증적)와 AML 마지막(=AML-AUD-001 ③, 설정/감사·증적·내부통제)을 렌더해 NAV가 `▼ 설정`의 마지막 메뉴를 하이라이트하는지 확인:
```bash
pdftoppm -png -r 90 -f 49 -l 49 /tmp/fdsppt/BO-FDS-SASS-Planning_v8.0.pdf /tmp/fdsppt/last && \
pdftoppm -png -r 90 -f 70 -l 70 /tmp/amlppt/BO-AML-SAAS-Planning_v9.0.pdf /tmp/amlppt/last
```
Read `/tmp/fdsppt/last-49.png`·`/tmp/amlppt/last-70.png`.
Expected: 운영 영역 화면이 앞쪽, 설정 영역 화면이 뒤쪽으로 정렬됨. NAV 활성 메뉴가 슬라이드 화면 ID와 일치.

- [ ] **Step 3: PRD↔PPT 버전 핀 일치 확인**

Run:
```bash
grep -l "v8.0" /Users/smkim/workspace/smkim89/aml-system-docs/docs/plan/01-fds-sass-functional-spec.md; \
grep -l "v9.0" /Users/smkim/workspace/smkim89/aml-system-docs/docs/plan/02-aml-sass-functional-spec.md
```
Expected: 두 PRD 모두 매칭(짝 PPT 버전 참조 존재).

- [ ] **Step 4: 임시 렌더 산출물 정리**

Run: `rm -rf /tmp/fdsppt /tmp/amlppt`
Expected: 정리 완료(저장소에 임시 파일 미커밋).

- [ ] **Step 5: 브랜치 마무리**

superpowers:finishing-a-development-branch 스킬로 머지/PR 옵션을 사용자에게 제시한다. (aml-system-docs는 한국어 커밋 관례. 푸시/PR은 사용자 승인 후.)

---

## Self-Review

- **스펙 커버리지:** 스펙 §3.1(FDS 구조)=Task 2·3, §3.2(AML 구조)=Task 4·5, §3.3(AML 혼재 분리)=Task 4 Step 1·3 + Task 5 Step 1, §4(편집 범위: PRD+생성기+재생성)=Task 1~5, §5(수용 기준: 누락0·분리·무손실·통계 운영)=Task 2/4 Step 5(슬라이드 수)·Step 6(렌더)·Task 6. 통계 운영 배치=FDS_NAV·AML_NAV 조사·모니터링 leaf. 누락 없음.
- **플레이스홀더:** 코드 블록은 실제 데이터 구조·함수 전문 포함. PRD 본문 표는 실제 마크다운 전문 제공. "위치 확인"용 grep은 섹션 번호가 PRD마다 다를 수 있어 불가피 — 단, 삽입 기준점(`## 1. 개요` 직전)과 삽입 내용은 확정.
- **타입/이름 일관성:** `nav_tree(slide, areas, active_key)` 시그니처가 Task 1 정의 ↔ Task 2/4 호출 일치. FDS leaf key=prefix(`sid.split("-")[1]`)와 FDS_NAV key 일치. AML `NAVKEY`/`aml_active()` base 키(`RA-OPS`·`TM-001`·`CDD-002` 등)가 AML_NAV leaf key와 정확히 일치(RA-OPS, RA-002, CDD-001, CDD-002, TM-001, TM-002).
- **슬라이드 수 보존:** Task 2/4의 SCREENS는 기존 항목을 순서만 재배열 — Step 5의 slides=49/70 게이트로 누락·중복 자동 검출.
