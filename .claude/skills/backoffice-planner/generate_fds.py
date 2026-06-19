"""
BO-FDS-SASS-Planning_v8.0.pptx 생성 (도형 기반 — 메뉴 IA 운영/설정 2영역·3단 재구성)
======================================================================================
정본 PRD: docs/plan/01-fds-sass-functional-spec.md (표시 용어=진실)
시각 정본: docs/plan/sample.pptx (맑은 고딕·Ant Design·순수 rect)
컴포넌트: wireframe_lib.py (ASCII 금지, 실제 rect 도형)

슬라이드: 1=커버 / 2=변경 이력 / 3+=기능 ID 전수(SFDS-*, ID 순)
좌 75% 와이어프레임 + 우 25% info_panel(권한·필터·컬럼·동작·API)
실행: cd .claude/skills/backoffice-planner && python3 generate_fds.py
"""
import wireframe_lib as wf

TOP = "SaaS FDS Platform 백오피스"
# 2영역·3단 NAV (운영/설정) — leaf key = 기능 ID prefix
NAV = [
    ("운영", [
        ("조사·모니터링", [("플랫폼 대시보드", "DASH"), ("탐지 결정", "DEC"),
                          ("이벤트 조회", "EVT"), ("룰 효과 통계", "STAT")]),
        ("케이스·처리", [("케이스 관리", "CASE"), ("액션 운영", "ACT")]),
        ("거버넌스·보고", [("결재함", "APPR"), ("규제 보고", "REG")]),
    ]),
    ("설정", [
        ("연동·데이터", [("서비스 관리", "TNT"), ("커넥터 관리", "CONN"),
                        ("스키마·매핑", "MAP")]),
        ("탐지 정책", [("룰 관리", "RULE"), ("그룹·명단", "GRP")]),
        ("감사·증적", [("감사 로그", "AUDIT"), ("Evidence", "EXP")]),
    ]),
]


def frame(p, sid, crumb, title, search="검색...", admin="관리자 admin ▼", action=None):
    s = wf.add_slide(p)
    wf.page_title(s, TOP, sid)
    wf.header_bar(s, search_ph=search, admin=admin, action=action)
    wf.nav_tree(s, NAV, active_key=sid.split("-")[1])
    wf.breadcrumb_title(s, crumb, title)
    return s


# ── 2. 플랫폼 대시보드 ───────────────────────────────────────────
def dash_001(p):
    s = frame(p, "SFDS-DASH-001", "FDS Console > 플랫폼 대시보드",
              "플랫폼 운영 대시보드 (전체 서비스)", search="서비스·룰·이벤트 검색...")
    y = wf.CON_TOP
    y = wf.filters(s, y, ["기간 최근 24시간"])
    y = wf.kpi_cards(s, y, [
        ("수신 이벤트", "4,182,402 건", "정상 99.7% · 검증실패 0.3%", "blue"),
        ("결정", "312,940 건", "차단 0.31% · 추가인증 0.12%", "green"),
        ("조치·케이스", "1,204 차단·보류", "케이스 신규 88 · 동결 12", "orange")])
    y = wf.callout(s, y, "플랫폼 알림 (카드·알림 클릭 → 해당 상세로 드릴다운)", [
        "[PG B / card-processor] 커넥터 지연 312초 — 임계 초과 [클릭 → SFDS-CONN-001 커넥터 목록]",
        "[은행 A] 스키마 검증 실패 4,201건 — 매핑 점검 필요 [클릭 → SFDS-MAP-001 스키마 레지스트리]",
        "[거래소 C] 액션 발행 실패 큐 적체 58건 [클릭 → SFDS-ACT-001 액션 아웃박스]",
        "규제 보고 제출 기한 임박(전 서비스) 6건 [클릭 → SFDS-REG-001 규제 보고 큐]"])
    wf.two_panels(s, y, 1.75,
        ("서비스별 건전성", ["서비스", "수신", "검증실패", "커넥터lag", "액션실패", "케이스SLA"],
         [["은행 A", "2.1M", "4,201 ⚠", "12초", "0", "정상"],
          ["PG B", "1.4M", "0", "312초 ⚠", "2", "정상"],
          ["거래소 C", "0.6M", "0", "8초", "58 ⚠", "임박 3"]],
         [0.24, 0.15, 0.17, 0.15, 0.13, 0.16]),
        ("케이스 SLA 현황", ["항목", "건수"],
         [["진행 중", "88"], ["기한 임박 24h", "3"], ["기한 초과", "0"], ["오탐 피드백", "17"]],
         [0.72, 0.28]))
    wf.info_panel(s, "SFDS-DASH-001", [
        "• 권한 플랫폼 운영자 전용 (SFDS_PLATFORM:READ)",
        "• 기간 최근 1h/24h/7d/30d 필터 (BR-001 기간 단일축 정본 §2.1)",
        "• 계층 기관(institution) 1 : 서비스(=tenant) N : 워크스페이스(workspace) N — 워크스페이스별 룰셋·커넥터·결재 분리",
        "• 요약 카드 수신·결정·조치/케이스 건수·비율",
        "• 플랫폼 알림 커넥터 지연·검증 실패·액션 적체·보고 기한 (각 상세로 딥링크)",
        "• 서비스별 건전성 수신·검증실패·커넥터lag·액션실패·케이스SLA",
        "• 행 클릭 서비스별 대시보드(DASH-002) 이동",
        "• 갱신 30~60초 캐시 · read-only",
        "▸ API GET /api/v1/bo/fds/dashboard (bo-api 소유·집약)"])


def dash_002(p):
    s = frame(p, "SFDS-DASH-002", "FDS Console > 플랫폼 대시보드 > 서비스",
              "서비스별 상세 대시보드", search="서비스: 은행 A")
    y = wf.CON_TOP
    y = wf.filters(s, y, ["서비스: 은행 A", "워크스페이스: retail", "기간 최근 24시간"])
    y = wf.kpi_cards(s, y, [
        ("수신 상태", "2.1M 수신", "정상 2.09M · 검증실패 4,201 ⚠", "blue"),
        ("결정 추이", "차단 142", "검토 88 · 추가인증 31", "green"),
        ("케이스 SLA", "진행 88", "기한 임박 3 ⚠ · 초과 0", "orange")])
    y = wf.two_panels(s, y, 1.55,
        ("커넥터 상태", ["소스 시스템", "상태", "lag"],
         [["core-banking", "정상", "12초"], ["atm-switch", "정상", "8초"],
          ["audit-log(폴링)", "지연 ⚠", "312초"]],
         [0.5, 0.28, 0.22]),
        ("액션 실패 큐", ["항목", "건수"],
         [["발행 / 성공", "1,204 / 1,202"], ["실패", "2"],
          ["재시도 대기", "2"], ["미처리 DLQ", "0"]],
         [0.62, 0.38]))
    wf.table_block(s, y, 1.55, "룰 hit rate / 오탐",
        ["룰 번호", "동작", "평가", "탐지", "hit율", "오탐(피드백)"],
        [["MULE_BANK", "거래차단", "88,402", "142", "0.16%", "12"],
         ["ATM_GEO", "추가인증", "12,004", "31", "0.26%", "5"]],
        [0.20, 0.16, 0.16, 0.12, 0.14, 0.22])
    wf.info_panel(s, "SFDS-DASH-002", [
        "• 권한 자기 서비스 스코프 조회 (SFDS:READ)",
        "• 필터 서비스 · 워크스페이스(workspace retail/corporate) · 기간 3축",
        "• 상단 [서비스] 드롭다운 (서비스 관리자는 고정·스코프 배지) · sandbox shadow-only 배지",
        "• 수신 상태 수신·정상·검증실패(스키마/서명)",
        "• 결정 추이 차단·검토·추가인증",
        "• 커넥터 상태 소스시스템별 정상/지연 + lag",
        "• 액션 실패 큐 발행·성공·실패·재시도·DLQ",
        "• 룰 hit rate 룰별 평가·탐지·hit율·오탐 피드백",
        "• 임계 초과 ⚠ 강조 · 각 카드 상세 딥링크",
        "▸ API GET /api/v1/bo/fds/tenants/{id}/dashboard"])


# ── 3. 서비스 관리 ───────────────────────────────────────────────
def tnt_001(p):
    s = frame(p, "SFDS-TNT-001", "FDS Console > 서비스 관리", "서비스 목록",
              action="+ 새 서비스")
    y = wf.CON_TOP
    y = wf.filters(s, y, ["상태 전체", "리전 전체", "배포 유형 전체", "서비스명 검색"])
    y = wf.table_block(s, y, 2.6, "서비스 목록 (총 18건 · 운영중 14) · 행 ▶ → SFDS-TNT-002 (서비스 상세)",
        ["서비스 ID", "표시명", "배포 유형", "온보딩 상태", "리전", "상태"],
        [["tenant_bank_a", "은행 A", "매니지드 전용", "활성", "한국", "운영중 ▶"],
         ["tenant_pg_b", "PG B", "자체 인프라 설치형", "등록 완료", "한국", "운영중 ▶"],
         ["tenant_cx_c", "거래소 C", "매니지드 전용", "활성", "한국", "운영중 ▶"],
         ["tenant_mp_d", "마켓플레이스 D", "소규모 공유", "프로비저닝중", "한국", "온보딩 ▶"]],
        [0.22, 0.20, 0.20, 0.16, 0.10, 0.12])
    wf.callout(s, y, "흐름 · 서비스 운영", [
        "행 클릭 → SFDS-TNT-002 (서비스 상세 5탭: 기본정보·배포·온보딩·마스킹·보안·Policy Pack·알림·소스)",
        "[+ 새 서비스] → SFDS-TNT-003 (배포 유형 선택 + 온보딩 신청) → 신청 직후 온보딩, 프로비저닝·검증 통과 후 운영중",
        "상세에서 [설정 변경] → 변경 이력 감사 로그(SFDS-AUDIT-001) 기록 · 배포 유형·온보딩·인프라 참조·리전은 읽기 전용"])
    wf.info_panel(s, "SFDS-TNT-001", [
        "• 권한 조회 SFDS_TENANT:READ / 신규 SFDS_TENANT:ADMIN",
        "• 필터 상태·리전·배포 유형 3축 + 서비스명 검색",
        "• 컬럼 서비스 ID·표시명·배포 유형·온보딩 상태·리전·상태",
        "• 배포 유형 매니지드 전용/자체 인프라 설치형/소규모 공유",
        "• 온보딩 상태 신청/프로비저닝중/배포됨/검증됨/활성·패키지발급/고객배포/등록완료(8종 읽기)",
        "• 상태 온보딩/운영중/정지/해지(tenant_status)",
        "• 플랫폼 운영자 전용 · 흐름 행 클릭 → SFDS-TNT-002 (서비스 상세)",
        "• [+ 새 서비스] ADMIN 권한만 노출 → SFDS-TNT-003 (배포 유형 선택+온보딩)",
        "▸ API GET /api/v1/bo/fds/tenants?status=&region=&deploymentModel= (bo-api 소유)"])


# 서비스 상세(SFDS-TNT-002) 5탭 — 같은 부모 탭 바로 연속 전개(SKILL §1.6)
FDS_DETAIL_TABS = ["기본 정보", "배포·온보딩", "마스킹·보안", "Policy Pack", "알림·소스"]


def tnt_002_basic(p):
    """SFDS-TNT-002 서비스 상세 — ① 기본 정보"""
    s = frame(p, "SFDS-TNT-002", "FDS Console > 서비스 관리 > 은행 A > 기본 정보",
              "서비스 상세 — ① 기본 정보 (은행 A)", action="설정 변경")
    y = wf.CON_TOP
    y = wf.tab_chips(s, y, FDS_DETAIL_TABS, active=0)
    y = wf.entry_banner(s, y, "SFDS-TNT-001 서비스 목록에서 [서비스 행 ▶] 클릭 → 서비스 상세")
    y = wf.two_panels(s, y, 1.70,
        ("[기본 정보]", ["항목", "값"],
         [["서비스 ID", "tenant_bank_a  (불변)"],
          ["표시명", "은행 A  [편집]"],
          ["운영 상태", "운영중 ACTIVE  [변경]"],
          ["배포 리전", "한국 리전"],
          ["생성일", "2026-01-12"]],
         [0.40, 0.60]),
        ("[요약 · 탭 바로가기]", ["항목", "값"],
         [["배포 유형", "매니지드 전용  (→ ② 배포·온보딩)"],
          ["마스킹", "원문 미저장  (→ ③ 마스킹·보안)"],
          ["Policy Pack", "한국 기본  (→ ④ Policy Pack)"],
          ["알림 채널", "Slack·email  (→ ⑤ 알림·소스)"]],
         [0.40, 0.60]))
    wf.info_panel(s, "SFDS-TNT-002", [
        "• 권한 조회 SFDS_TENANT:READ / 변경 SFDS_TENANT:ADMIN",
        "• 같은 부모 탭 바: 기본 정보 / 배포·온보딩 / 마스킹·보안 / Policy Pack / 알림·소스 (5탭 연속)",
        "• 변경 가능 표시명 · 운영 상태",
        "• 진입: SFDS-TNT-001 목록 → 행 클릭",
        "• 다음 → ② 배포·온보딩",
        "▸ API GET·PUT /api/v1/bo/fds/tenants/{id}"])


def tnt_002_deploy(p):
    """SFDS-TNT-002 서비스 상세 — ② 배포·온보딩"""
    s = frame(p, "SFDS-TNT-002", "FDS Console > 서비스 관리 > 은행 A > 배포·온보딩",
              "서비스 상세 — ② 배포·온보딩 (은행 A)", action="설정 변경")
    y = wf.CON_TOP
    y = wf.tab_chips(s, y, FDS_DETAIL_TABS, active=1)
    y = wf.kpi_cards(s, y, [
        ("배포 유형", "매니지드 전용", "MANAGED_DEDICATED", "blue"),
        ("온보딩 상태", "활성", "ACTIVE (읽기)", "green"),
        ("인프라 참조", "infra-bank-a", "한국 리전 (읽기)", "green")])
    y = wf.two_panels(s, y, 1.55,
        ("온보딩 진행 상태 (이력)", ["상태", "시각", "작업자"],
         [["신청(REQUESTED)", "01-12 09:00", "admin"],
          ["프로비저닝·검증", "01-12 09:20", "시스템"],
          ["활성(ACTIVE)", "01-12 10:00", "시스템"]],
         [0.45, 0.33, 0.22]),
        ("데이터 보존 정책", ["항목", "값"],
         [["거래·결정", "13개월 hot / 7년 cold"],
          ["감사", "7년 (하향 불가)"],
          ["변경", "테넌트 관리자 요청 → bo-api 통해 승인"]],
         [0.42, 0.58]))
    wf.info_panel(s, "SFDS-TNT-002", [
        "• 배포 유형·온보딩 상태·인프라 참조·리전 읽기 전용 (프로비저닝 산출)",
        "• 매니지드 전용 IaC / 자체 인프라 설치형 등록 콜백 → 온보딩 API",
        "• 감사 보존 최소 7년 하향 불가",
        "• 이전 ← ① 기본 정보  /  다음 → ③ 마스킹·보안",
        "▸ API GET .../tenants/{id}/onboarding · POST .../onboarding/**"])


def tnt_002_security(p):
    """SFDS-TNT-002 서비스 상세 — ③ 마스킹·보안"""
    s = frame(p, "SFDS-TNT-002", "FDS Console > 서비스 관리 > 은행 A > 마스킹·보안",
              "서비스 상세 — ③ 마스킹·보안 (은행 A)", action="설정 변경")
    y = wf.CON_TOP
    y = wf.tab_chips(s, y, FDS_DETAIL_TABS, active=2)
    y = wf.two_panels(s, y, 1.70,
        ("[마스킹 정책]", ["항목", "값"],
         [["민감 식별자", "토큰 / keyed hash 저장"],
          ["원문 저장", "미저장"],
          ["화면 표시", "앞3 + 뒤4 노출"],
          ["원문 접근", "미제공 (복호화 UI 없음)"]],
         [0.42, 0.58]),
        ("[조치 권한 (Capability)]", ["항목", "값"],
         [["가능 조치", "차단 · 자금보류 · 해제 · 취소"],
          ["케이스 전용", "조치 없음, 케이스만 생성"],
          ["연동", "Capability 매트릭스 (SFDS-ACT-002)"],
          ["변경", "조치 권한 변경 4-eyes"]],
         [0.40, 0.60]))
    wf.info_panel(s, "SFDS-TNT-002", [
        "• 마스킹 앞3+뒤4 · 복호화 UI 없음 · 원문 미저장",
        "• 민감 식별자는 토큰/keyed hash로만 저장 (PII 원문 금지)",
        "• 조치 권한 = 이 서비스가 수행 가능한 액션 집합",
        "• 이전 ← ② 배포·온보딩  /  다음 → ④ Policy Pack",
        "▸ API GET·PUT /api/v1/bo/fds/tenants/{id}"])


def tnt_002_policy(p):
    """SFDS-TNT-002 서비스 상세 — ④ Policy Pack"""
    s = frame(p, "SFDS-TNT-002", "FDS Console > 서비스 관리 > 은행 A > Policy Pack",
              "서비스 상세 — ④ Policy Pack (은행 A)", action="설정 변경")
    y = wf.CON_TOP
    y = wf.tab_chips(s, y, FDS_DETAIL_TABS, active=3)
    y = wf.table_block(s, y, 2.05, "적용 규제 팩 [서비스: 은행 A] — 미리 정의된 팩을 토글로 활성/비활성 (한국 기본팩 잠금)",
        ["팩 이름", "토글 상태", "트리거·보고 양식"],
        [["한국 기본팩", "● ON (잠금·필수)", "STR/CTR 기본 양식, KoFIU 포맷"],
         ["전자금융거래법", "● ON  [▸끄기]", "전자금융거래 이상행위 보고"],
         ["특금법 (AML/CFT)", "● ON  [▸끄기]", "의심거래·고액현금 보고(STR/CTR)"],
         ["개인정보보호법", "● ON  [▸끄기]", "개인정보 침해 대응 보고"],
         ["내부통제기준", "● ON  [▸끄기]", "내부 감사 케이스 생성"],
         ["Travel Rule / PCI", "○ OFF  [▸켜기]*", "*가상자산·카드 계약 후 활성화"]],
        [0.26, 0.18, 0.56])
    wf.callout(s, y, "변경 스테이징(미저장) · 일괄 변경 상신 (SFDS_TENANT:ADMIN + 4-eyes)", [
        "토글로 켜고/끄기를 스테이징 → 영향 미리보기: STR 6건 · CTR 2건 영향 (즉시 반영 아님)",
        "[변경 상신 → 4-eyes 결재(subjectKind=POLICY_PACK)] 스테이징 변경을 한 번에 상신(개별 토글 결재 X) → 승인 후 effective",
        "한국 기본팩 잠금(필수·끄기 불가) · Travel Rule/PCI는 도메인 계약 후 · 보고 후보 큐 [→ SFDS-REG-001 규제 보고]",
        "이전 ← ③ 마스킹·보안  /  다음 → ⑤ 알림·소스"])
    wf.info_panel(s, "SFDS-TNT-002", [
        "• 권한 조회 SFDS_TENANT:READ / 변경 SFDS_TENANT:ADMIN (4-eyes)",
        "• 규제 팩 = 미리 정의된 카탈로그 → 서비스별 토글로 활성(ON)/비활성(OFF)",
        "• 팩별 트리거·보고 양식 표기(어떤 룰 기반인가 전수)",
        "• 한국 기본팩 ON 잠금(최소 규제 요건·끄기 불가) · Travel Rule/PCI는 도메인 계약 후만 ON 가능",
        "• 토글은 즉시 반영 X — 스테이징 → 영향 미리보기(STR/CTR 건수) → 일괄 [변경 상신]",
        "• 일괄 상신 = 스테이징된 변경 한 번에 4-eyes 결재(개별 토글마다 결재 아님)",
        "• 각 팩 생성 보고 후보는 SFDS-REG-001(규제 보고 큐) 양식·트리거에 반영(BR-005)",
        "• 토글 변경 4-eyes subjectKind=POLICY_PACK(대상 tenant_id·기본 COMPLIANCE_MANAGER, 설계서 §16.2)",
        "• Policy Pack 토글·상신·결재 이력은 감사 로그(SFDS-AUDIT-001) 기록",
        "• 모델 차이 FDS=법령·관할별 팩 개별 토글 / AML=KR_DEFAULT 번들+plugin(의도된 차이·BR-006·AML PRD §13.2 ④ BR-005)",
        "• 이전 ← ③ 마스킹·보안  /  다음 → ⑤ 알림·소스",
        "▸ API GET·PUT /api/v1/bo/fds/tenants/{id}"])


def tnt_002_notify(p):
    """SFDS-TNT-002 서비스 상세 — ⑤ 알림·소스"""
    s = frame(p, "SFDS-TNT-002", "FDS Console > 서비스 관리 > 은행 A > 알림·소스",
              "서비스 상세 — ⑤ 알림·소스 (은행 A)", action="설정 변경")
    y = wf.CON_TOP
    y = wf.tab_chips(s, y, FDS_DETAIL_TABS, active=4)
    y = wf.two_panels(s, y, 1.70,
        ("[알림 채널]", ["채널", "대상"],
         [["Slack", "#risk-bank-a"],
          ["Email", "ops-bank-a@…"],
          ["Webhook", "고객 endpoint (FdsDecisionCreated)"]],
         [0.30, 0.70]),
        ("[연결된 소스 시스템]", ["소스 시스템", "연동 방식", "사용", "지연", "최근 오류"],
         [["core-banking", "큐(Queue)", "○", "12초", "—"],
          ["atm-switch", "REST Push", "○", "8초", "—"],
          ["audit-log", "폴링", "○", "312초⚠", "페이지 타임아웃"],
          ["legacy-card", "CDC", "○", "24초", "—"]],
         [0.26, 0.20, 0.08, 0.16, 0.30]))
    wf.info_panel(s, "SFDS-TNT-002", [
        "• 알림 채널 Slack · Email · Webhook (결정·조치 통지)",
        "• 소스 시스템 상세는 커넥터 관리(SFDS-CONN-001)에서 관리",
        "• 이전 ← ④ Policy Pack  (상세 5탭 끝)",
        "▸ API GET /api/v1/admin/fds/source-systems · GET/PUT /api/v1/admin/fds/notify-channels"])


def tnt_003(p):
    s = frame(p, "SFDS-TNT-003", "FDS Console > 서비스 관리 > 등록",
              "서비스 등록 / 수정 (마스터 생성)")
    y = wf.CON_TOP
    wf.form_block(s, y, 4.6, "서비스 마스터 등록 (배포 유형 선택 + 온보딩 신청)",
        [("서비스 ID *", "tenant_bank_a  (영문 소문자·숫자·_ · 변경 불가)", "input"),
         ("표시명 *", "은행 A", "input"),
         ("배포 유형 *", "매니지드 전용 ▼  (매니지드 전용 / 자체 인프라 설치형 / 소규모 공유)", "input"),
         ("온보딩 상태", "신청 (REQUESTED) · 프로비저닝 진행에 따라 자동 갱신 (읽기)", "input"),
         ("인프라 참조", "—  (온보딩 프로비저닝 산출 · 읽기)", "input"),
         ("리전 *", "한국 리전 ▼  (해외는 별도 계약·법무 검토)", "input"),
         ("데이터 보존 *", "거래·결정 13개월 hot / 7년 cold · 감사 7년", "input"),
         ("마스킹 정책 *", "민감 식별자 토큰/해시만 저장 (원문 미저장)", "check"),
         ("Policy Pack *", "한국 기본팩 (추가: Travel Rule / PCI 최소화)", "check"),
         ("알림 채널", "Slack #risk-bank-a · ops-bank-a@…", "input")],
        btns=["취소", "등록·온보딩 신청"])
    wf.info_panel(s, "SFDS-TNT-003", [
        "• 권한 SFDS_TENANT:ADMIN (플랫폼 운영자)",
        "• 입력 서비스 ID·표시명·배포 유형·리전·보존·마스킹·Policy Pack·알림",
        "• 서비스 ID immutable·unique · 중복 시 FDS-VALIDATION-001",
        "• 배포 유형 등록 시 선택 · 실제 격리는 온보딩 프로비저닝의 산출(화면 즉석 선택 아님)",
        "• 온보딩 상태·인프라 참조·리전 읽기 전용 · 변경 시 재배포·마이그레이션",
        "• 신청 직후 온보딩(신청 REQUESTED) → 프로비저닝·검증·활성/등록완료 후 운영중 전환",
        "• 해외 리전 시 동의·계약·법무 검토 체크 필수 · 감사 보존 최소 7년 하향 불가",
        "▸ API POST /api/v1/bo/fds/tenants · PUT …/{id} · 온보딩 …/{id}/onboarding/**"])


# ── 4. 커넥터 관리 ───────────────────────────────────────────────
def conn_001(p):
    s = frame(p, "SFDS-CONN-001", "FDS Console > 커넥터 관리",
              "소스 시스템·커넥터 목록", action="+ 새 커넥터")
    y = wf.CON_TOP
    y = wf.filters(s, y, ["연동 방식 전체", "사용 전체", "상태 전체", "소스시스템 검색"])
    y = wf.table_block(s, y, 2.85, "소스 시스템·커넥터 (hanpass-ph 7실서비스 · REST sync) · 행 ▶ → SFDS-CONN-002 · [인입 모니터링 → SFDS-CONN-004]",
        ["소스 시스템", "연동 방식", "사용", "발행 이벤트(채널)", "마지막 수신", "신호", "최근 오류"],
        [["member-svc", "REST sync", "○", "회원/KYC/제재·PEP(대상 자재화)", "2초 전", "●", "— ▶"],
         ["walletchg-svc", "REST sync", "○", "월렛충전 → CASH_IN", "1초 전", "●", "— ▶"],
         ["domestic-svc", "REST sync", "○", "국내송금 → DOMESTIC_REMIT", "3초 전", "●", "— ▶"],
         ["remit-svc", "REST sync", "○", "해외송금 → CROSS_BORDER_REMIT", "1초 전", "●", "— ▶"],
         ["wallet-svc", "REST sync", "○", "월렛 원장(transfer_links)", "5초 전", "●", "— ▶"],
         ["tx-history-svc", "REST sync", "○", "통합 이력 read(대상 360°)", "4초 전", "●", "— ▶"],
         ["inbound-svc", "REST sync", "○", "파트너 인바운드 → INBOUND_REMIT", "8초 전", "●", "— ▶"]],
        [0.16, 0.13, 0.06, 0.35, 0.12, 0.07, 0.11])
    wf.callout(s, y, "흐름 · 커넥터 운영 (소스 = hanpass-ph 실서비스 · 인입 신호 §4.0 확정)", [
        "소스 = hanpass-ph 송금/월렛 마이크로서비스(REST sync) · cross-border는 corridor·base USD 보존(DB §5.5·연동 §7.2)",
        "행 클릭 → SFDS-CONN-002 (상세·커서·재처리) · [인입 모니터링] → SFDS-CONN-004 (수신 API·라이브)",
        "신호 ● 수신중/⚠ 지연/✕ 중단 · 채널 21종(+CASH_IN·INBOUND_REMIT) · 스키마 MAP-001 연계 · 규제 불변"])
    wf.info_panel(s, "SFDS-CONN-001", [
        "• 권한 조회 :READ / 신규·운영 SFDS_CONNECTOR:OPERATE",
        "• 소스 = hanpass-ph 7실서비스(member/walletchg/domestic/remit/wallet/tx-history/inbound-svc)",
        "• 발행 이벤트 walletchg→CASH_IN·domestic→DOMESTIC_REMIT·remit→CROSS_BORDER_REMIT·inbound→INBOUND_REMIT",
        "• 연동 방식 REST sync(REST_PUSH) · 인증 API Key+HMAC(Source-System 헤더)",
        "• 컬럼 소스시스템·연동방식·사용·발행 이벤트(채널)·마지막 수신·신호·최근오류",
        "• 마지막 수신·신호 §4.0 확정 — ● 수신중/⚠ 지연/✕ 중단",
        "• 연동 키 token/keyed-HMAC(원문 금지, 연동 §7.2) · 규제(CTR/STR/KoFIU) 불변",
        "• [인입 모니터링] → SFDS-CONN-004 수신 API 카탈로그·라이브",
        "• 흐름 행 클릭 → SFDS-CONN-002 · [+ 새 커넥터] → SFDS-CONN-003",
        "▸ API GET /api/v1/admin/fds/source-systems · /connectors"])


def conn_002(p):
    s = frame(p, "SFDS-CONN-002", "FDS Console > 커넥터 관리 > 상세",
              "audit-log 커넥터 (폴링) · 지연", action="일시중지")
    y = wf.CON_TOP
    y = wf.entry_banner(s, y, "SFDS-CONN-001 커넥터 목록에서 [소스시스템 행 ▶] 클릭 → 커넥터 상세")
    y = wf.two_panels(s, y, 1.85,
        ("기본 / 인입 신호 (PRD §4.0 확정)", ["항목", "값"],
         [["연동 방식", "폴링(Polling) · audit-log.v1"],
          ["현재 커서", "2026-06-06T09:58Z"],
          ["마지막 폴링", "06-06 09:58 (성공)"],
          ["다음 폴링 예정", "06-06 10:28 · 주기 30분"],
          ["지연 / 신호", "312초 · ⚠ 지연"]],
         [0.38, 0.62]),
        ("처리 현황 (24h) / 오류", ["항목", "값"],
         [["수신", "88,402"], ["정상", "88,201"],
          ["중복(dedup)", "180"], ["검증 실패", "21"],
          ["최근 오류", "페이지 타임아웃(checksum)"]],
         [0.42, 0.58]))
    y = wf.form_block(s, y, 1.55, "재처리 / 운영",
        [("재처리 범위", "from 2026-06-06 09:00 ~ to 10:00", "input"),
         ("연동별 운영", "폴링=cursor·replay·checksum / 큐=offset / CDC=change stream", "text")],
        btns=["재처리", "커서 이동(=오프셋 replay)", "일시중지", "재개", "설정 변경(승인)"])
    wf.callout(s, y, "버튼 시나리오 · 책임 경계", [
        "[일시중지]/[재개] → 본 커넥터 ingest 즉시 중단·복구 (지연 해소 후 재개) · 감사 로그 기록",
        "[커서 이동(=오프셋 replay)]/[재처리] → POST /replay 입력 범위만 멱등 재수신(dedup) · 범위 미입력 시 제출 불가",
        "[설정 변경(승인)] → PUT /source-systems/{id} 4-eyes(2인) 결재(MAPPING) → SFDS-APPR-001 상신",
        "서명키·시크릿 변경은 본 화면 아님 → SFDS-CONN-003 4-eyes(2인) · 모든 운영 작업 SFDS-AUDIT-001 기록"])
    wf.info_panel(s, "SFDS-CONN-002", [
        "• 권한 조회 :READ / 운영 SFDS_CONNECTOR:OPERATE",
        "• 기본 연동방식·스키마·커서/오프셋·지연·최근오류",
        "• 인입 신호(v7.0) 폴링=마지막·다음 폴링·주기 / 큐=depth·DLQ / REST=TPS (§4.0)",
        "• 처리 현황 수신·정상·중복(dedup)·검증실패",
        "• 운영 재처리·커서이동=replay(/replay)·일시중지/재개(/pause·/resume)",
        "• 재처리 멱등 보장(같은 키 dedup) · 범위 입력 필수",
        "• 설정 변경(승인) PUT /source-systems/{id} 4-eyes(MAPPING)",
        "• secret/서명키 변경은 본 화면 아님 → CONN-003 4-eyes",
        "• 모든 운영 작업 감사 로그 기록",
        "▸ API GET …/connectors/{connectorId} · POST …/replay·/pause·/resume · PUT …/source-systems/{id}"])


def conn_003(p):
    s = frame(p, "SFDS-CONN-003", "FDS Console > 커넥터 관리 > 등록",
              "커넥터 등록 / 수정")
    y = wf.CON_TOP
    wf.form_block(s, y, 4.6, "커넥터 등록 [서비스: 은행 A]",
        [("소스 시스템 *", "core-banking  (생성 후 변경 불가)", "input"),
         ("연동 방식 *", "(●) 큐  ( ) REST Push  ( ) 폴링  ( ) CDC  ( ) 스냅샷", "radio"),
         ("스키마 버전 *", "core-banking.v2 ▼  (스키마 레지스트리 MAP-001)", "input"),
         ("사용", "활성", "check"),
         ("큐 종류", "SQS ▼ (Kafka/SQS/RabbitMQ/PubSub) · 대기열 arn:…", "input"),
         ("서명키 (4-eyes)", "●●●●●●●●  앞3+뒤4 표시 · 변경은 2인 승인", "input"),
         ("자격증명 회전", "[자격증명 회전 요청(승인 필요)]", "text")],
        btns=["취소", "저장"])
    wf.info_panel(s, "SFDS-CONN-003", [
        "• 권한 작성 :OPERATE / secret·서명키 변경 SFDS_CONNECTOR:APPROVE(2인)",
        "• 입력 소스시스템·연동방식·스키마·사용·연동별 설정",
        "• 연동별 큐:종류·ARN / REST:엔드포인트·서명키 / 폴링:URL·cursor / CDC:PII allowlist",
        "• 서명키·시크릿 원문 미표시(앞3+뒤4) · 변경 4-eyes",
        "• 소스시스템 식별자 immutable",
        "• 등록 후 샘플 이벤트 검증 통과 전 ingest 비활성",
        "▸ API POST …/source-systems · POST …/credentials/{id}/rotate(2인)"])


# ─── SFDS-CONN-004 수신 API 카탈로그·인입 라이브 모니터링 (v7.0, 2탭) ───
CONN_004_TABS = ["수신 API 카탈로그", "인입 라이브 모니터링"]


def conn_004(p, tab=0):
    titles = ["수신 API 카탈로그·인입 모니터링 — ① 수신 API 카탈로그",
              "수신 API 카탈로그·인입 모니터링 — ② 인입 라이브 모니터링"]
    crumbs = ["FDS Console > 커넥터 관리 > 인입 모니터링 > 수신 API 카탈로그",
              "FDS Console > 커넥터 관리 > 인입 모니터링 > 인입 라이브"]
    s = frame(p, "SFDS-CONN-004", crumbs[tab], titles[tab], search="소스·API 검색...")
    y = wf.CON_TOP
    y = wf.tab_chips(s, y, CONN_004_TABS, active=tab)
    if tab == 0:
        y = wf.table_block(s, y, 2.15, "수신 API 카탈로그 [서비스: 은행 A] (정본 = PRD §4.0 ② · API §4.1/§5.1)",
            ["API", "용도", "방식", "24h 호출", "마지막 호출", "신호"],
            [["POST /fds/events", "canonical event 수신(단건)", "비동기 202", "2.4M", "1초 전", "●"],
             ["POST /fds/events:batch", "다건(≤500) · 초기 적재(백필)", "비동기 202", "18회", "06-11 02:00", "●"],
             ["POST /fds/decisions/evaluate", "실시간 거래 판단", "동기", "1.1M", "1초 전", "●"],
             ["POST /fds/external-decisions", "벤더 evidence 수신", "비동기", "8.2K", "4분 전", "●"],
             ["GET /fds/events/{eventId}", "수신 상태·정규화 조회", "동기 조회", "3.1K", "12초 전", "●"]],
            [0.27, 0.25, 0.12, 0.11, 0.14, 0.11])
        y = wf.table_block(s, y, 1.85, "연동 방식 × 표시 신호 확정표 (PRD §4.0 ① 확정 — 5종)",
            ["연동 방식(코드)", "화면 표시 신호 (확정)"],
            [["REST 전송 (REST_PUSH)", "마지막 수신(n초 전) · ● 수신중 · 수신율(TPS) · 서명 실패"],
             ["큐 (QUEUE)", "depth · lag · DLQ 적체 · 마지막 메시지 — fds-events(FIFO) · fds-vendor-ingest · DLQ"],
             ["폴링 (POLLING)", "마지막 폴링 · 다음 폴링 예정 · 주기 · 현재 커서"],
             ["변경수집 (CDC)", "change stream lag · 마지막 변경분 적용 시각"],
             ["스냅샷 (SNAPSHOT)", "최근 스냅샷 일시 · 초기 적재(백필) 진행률 %"]],
            [0.28, 0.72])
        wf.callout(s, y, "① 카탈로그 — 어떤 API로 데이터가 들어오는가 (read-only · 인증 API Key+HMAC)", [
            "소스 카탈로그 = hanpass-ph 7실서비스(member/walletchg/domestic/remit/wallet/tx-history/inbound-svc, REST sync) → ② 탭",
            "신호 상태 ● 수신중(기본 60초 내 수신) / ⚠ 지연(SLA 초과) / ✕ 중단 (§4.0 ③ 확정)",
            "초기 셋업(백필) = /fds/events:batch — 진행률 ② 탭 · 다음 → ② 인입 라이브 모니터링"])
        wf.info_panel(s, "SFDS-CONN-004", [
            "• 권한 SFDS_CONNECTOR:READ (read-only 집계)",
            "• 진입 NAV 커넥터 관리 / SFDS-CONN-001 [인입 모니터링]",
            "• 탭 ① 수신 API 카탈로그 / ② 인입 라이브 모니터링",
            "• 컬럼 API·용도·방식(동기/비동기 202)·24h 호출·마지막 호출·신호",
            "• 연동 방식×표시 신호 확정표 5종 (PRD §4.0 ① 파생 표시)",
            "• 큐 정본 fds-events(FIFO)·fds-vendor-ingest·DLQ (integration §2)",
            "• /fds/events 신규=202 Accepted(큐 적재) · 멱등 재반환 200/201",
            "• 초기 셋업(백필) /fds/events:batch 최대 500건",
            "• 다음 → ② 인입 라이브 모니터링",
            "▸ API GET /api/v1/bo/fds/ingest/catalog (제안 · 후속 API 정합)"])
    else:
        y = wf.kpi_cards(s, y, [
            ("24h 수신 이벤트", "3.5 M", "전 커넥터 합산", "blue"),
            ("라이브 커넥터", "4 / 5", "● 수신중 기준", "green"),
            ("DLQ 적체", "2 건", "fds-events-dlq ⚠", "red"),
            ("마지막 수신", "1초 전", "전체 커넥터 최신", "orange")])
        y = wf.table_block(s, y, 2.45, "hanpass-ph 소스×연동 방식별 라이브 상태 (행 ▶ → SFDS-CONN-002 운영)",
            ["소스(hanpass-ph)", "연동 방식", "마지막 수신", "신호", "방식별 상태 (PRD §4.0 ① 확정)"],
            [["member-svc", "REST sync(큐 fds-events)", "2초 전", "●", "TPS 42 · depth 12 · 제재·PEP 신호"],
             ["walletchg-svc", "REST sync", "1초 전", "●", "TPS 86 · CASH_IN · 서명 실패 0"],
             ["domestic-svc", "REST sync", "3초 전", "●", "TPS 51 · DOMESTIC_REMIT(PHP)"],
             ["remit-svc", "REST sync", "1초 전", "●", "TPS 38 · CROSS_BORDER · corridor·USD base"],
             ["wallet-svc", "REST sync", "5초 전", "●", "TPS 64 · 원장 transfer_links"],
             ["tx-history-svc", "REST sync(read)", "4초 전", "●", "통합 이력 read(대상 360°)"],
             ["inbound-svc", "REST sync", "8초 전", "●", "TPS 9 · INBOUND_REMIT · DLQ 0"]],
            [0.16, 0.20, 0.11, 0.07, 0.46])
        wf.callout(s, y, "② 라이브 모니터링 — 지금 데이터가 들어오고 있는가 (30~60초 캐시·자동 새로고침)", [
            "DLQ 감시 = depth poller PT60S (fds-events-dlq·fds-vendor-ingest-dlq, integration §2·§6)",
            "⚠/✕ 행 → SFDS-DASH-001 알림 동일 소스 · 운영 조치(재처리·일시중지)는 SFDS-CONN-002",
            "이전 ← ① 수신 API 카탈로그 (인입 모니터링 2탭 끝)"])
        wf.info_panel(s, "SFDS-CONN-004", [
            "• 권한 SFDS_CONNECTOR:READ (read-only 집계)",
            "• 카드 24h 수신·라이브 커넥터·DLQ 적체·마지막 수신",
            "• 큐 fds-events depth·lag·DLQ / REST 마지막 수신·TPS",
            "• 폴링 마지막·다음 폴링·주기 / CDC stream lag / 스냅샷 백필 %",
            "• 신호 ● 수신중/⚠ 지연/✕ 중단 (§4.0 ③ · 임계 소스별 설정)",
            "• 운영 조치는 SFDS-CONN-002 (모니터링/운영 분리)",
            "• 이전 ← ① 수신 API 카탈로그",
            "▸ API GET /api/v1/bo/fds/ingest/health (제안 · 후속 API 정합)"])


# ── 5. 스키마·매핑 ───────────────────────────────────────────────
def map_001(p):
    s = frame(p, "SFDS-MAP-001", "FDS Console > 스키마·매핑",
              "스키마 레지스트리")
    y = wf.CON_TOP
    y = wf.filters(s, y, ["소스 시스템 전체", "상태 전체", "스키마 버전 검색"])
    y = wf.table_block(s, y, 2.5, "스키마 레지스트리 [서비스: 은행 A] · 행 ▶ → SFDS-MAP-002 (필드 매핑)",
        ["스키마 버전", "소스 시스템", "상태", "검증 실패(24h)", "적용 시작"],
        [["core-banking.v2", "core-banking", "운영중", "0", "2026-05-01 ▶"],
         ["core-banking.v1", "core-banking", "폐지", "—", "2026-01-01 ▶"],
         ["atm-switch.v1", "atm-switch", "운영중", "0", "2026-01-01 ▶"],
         ["audit-log.v1", "audit-log", "운영중", "21 ⚠", "2026-01-01 ▶"]],
        [0.26, 0.22, 0.14, 0.20, 0.18])
    wf.callout(s, y, "흐름 · 스키마 운영", [
        "행 클릭 → SFDS-MAP-002 (필드 매핑·PII 정책) · 매핑 변경은 4-eyes(2인) candidate 결재 후 effective",
        "검증 실패 건수(⚠) 클릭 → SFDS-EVT-001 검증 실패(reject) 필터 프리셋 진입",
        "스키마 버전은 SFDS-CONN-003 커넥터 등록 시 선택 · 폐지 버전은 신규 ingest 불가"])
    wf.info_panel(s, "SFDS-MAP-001", [
        "• 권한 SFDS_MAPPING:READ",
        "• 필터 소스 시스템·상태 + 스키마 버전 검색",
        "• 컬럼 스키마 버전·소스시스템·상태·검증실패(24h)·적용시작",
        "• 상태 운영중/후보/폐지",
        "• 검증 실패 발생 버전 ⚠ 강조",
        "• 흐름 행 클릭 → SFDS-MAP-002 (필드 매핑/PII 정책)",
        "• 검증 실패 건수 → SFDS-EVT-001 검증실패(reject) 필터 딥링크",
        "▸ API GET /api/v1/admin/fds/source-systems"])


def map_002(p):
    s = frame(p, "SFDS-MAP-002", "FDS Console > 스키마·매핑 > 필드 매핑",
              "필드 매핑 / PII 정책 — core-banking.v2", action="변경 결재(2인)")
    y = wf.CON_TOP
    y = wf.entry_banner(s, y, "SFDS-MAP-001 스키마 레지스트리에서 [스키마 버전 행 ▶] 클릭 → 필드 매핑")
    y = wf.table_block(s, y, 2.4, "필드 매핑 [서비스: 은행 A]",
        ["외부 필드(payload)", "정규화 항목", "PII 처리", "필수"],
        [["customer.ssn", "(저장 안 함)", "수신 즉시 폐기", "—"],
         ["account.number", "수단 식별자", "keyed hash", "○"],
         ["card.pan", "(저장 안 함)", "토큰화 후 폐기", "—"],
         ["txn.amount", "거래 금액", "그대로", "○"],
         ["device.ip", "접속 IP", "마스킹", "—"]],
        [0.30, 0.26, 0.30, 0.14])
    wf.callout(s, y, "PII allowlist (저장 허용 컬럼)", [
        "허용: amount · currency · channelType · institutionCode · country",
        "금지(원문): ssn · pan · raw account · raw address · phone",
        "※ 매핑·PII 정책 변경은 4-eyes(작성자≠승인자) · [변경 결재]"])
    wf.info_panel(s, "SFDS-MAP-002", [
        "• 권한 조회 :READ / 변경 SFDS_MAPPING:APPROVE(2인) (4-eyes)",
        "• 컬럼 외부 필드·정규화 항목·PII 처리·필수",
        "• PII 처리 그대로/마스킹/keyed hash/토큰화 후 폐기/수신 즉시 폐기",
        "• 고민감(주민번호·PAN) 매핑 불가 → 토큰화·폐기 / FDS-PII-REJECTED",
        "• CDC·스냅샷 PII allowlist 필수",
        "• 필수 항목 매핑 누락 시 결재 차단",
        "• 진입 SFDS-MAP-001 행 클릭 (스키마 버전 컨텍스트)",
        "• [변경 결재(2인)] → SFDS-APPR-001 결재함(MAPPING) 상신 → 승인 후 effective",
        "• 변경은 새 스키마 candidate 작성·결재 후 effective",
        "▸ API PUT …/source-systems/{ss}/mappings(2인) · /approve·/reject"])


# ── 6. 룰 관리 ───────────────────────────────────────────────────
def rule_001(p):
    s = frame(p, "SFDS-RULE-001", "FDS Console > 룰 관리", "룰 목록",
              action="+ 새 룰")
    y = wf.CON_TOP
    y = wf.filters(s, y, ["도메인 전체", "채널 전체", "상태 전체", "동작 전체", "평가 전체"])
    y = wf.table_block(s, y, 2.6, "룰 목록 (총 142건 · 운영중 118) [서비스: 은행 A] · 행 ▶ → SFDS-RULE-002 · [효과성 ▶ → SFDS-STAT-001]",
        ["룰 번호", "이름", "도메인/채널", "동작", "평가", "30일 탐지/오탐", "상태"],
        [["MULE_BANK", "대포통장 수취 즉시 차단", "국내송금", "거래차단", "즉시", "412 / 4.1%", "운영중 ▶"],
         ["ATM_GEO", "해외 IP ATM 출금 추가인증", "ATM출금", "추가인증", "즉시", "186 / 8.8%", "운영중 ▶"],
         ["CNP_VEL", "신규기기 CNP 다발 차단", "카드결제", "승인거부", "즉시", "1,204 / 5.2%", "운영중 ▶"],
         ["CRYPTO_RISK", "고위험 주소 출금 자금보류", "가상자산", "자금보류", "사후", "88 / 6.4%", "운영중 ▶"],
         ["TBML_INV", "인보이스 단가 이상 검토", "무역대금", "검토", "사후", "12 / 31% ⚠", "비활성 ⚠ ▶"],
         ["SETTLE_HOLD", "신규 셀러 환불급증 정산보류", "정산", "자금보류", "사후", "47 / 3.0%", "운영중 ▶"]],
        [0.13, 0.25, 0.11, 0.10, 0.07, 0.20, 0.14])
    wf.callout(s, y, "흐름 · 룰 운영", [
        "행 클릭 → SFDS-RULE-002 (룰 상세) · [+ 새 룰] → SFDS-RULE-003 (룰 빌더) · [효과성 ▶] → SFDS-STAT-001",
        "빌더에서 [시뮬레이션] → SFDS-RULE-006 백테스트 → [결재 상신] → SFDS-RULE-005 라이프사이클(4-eyes)",
        "임계치만 빠른 변경 → SFDS-RULE-004(Hot-reload) · 비활성(⚠) 행은 사후 자동 비활성·사유 툴팁"])
    wf.info_panel(s, "SFDS-RULE-001", [
        "• 권한 조회 :READ / 신규 SFDS_RULE:AUTHOR",
        "• 필터 도메인·채널·상태·동작·평가 5축 + 룰 번호 검색",
        "• 컬럼 룰 번호·이름·도메인/채널·동작·평가·30일 탐지/오탐·상태",
        "• 효과성 요약(v6.0) 최근 30일 탐지·오탐율 — 화면 파생값·튜닝 후보 ⚠",
        "• 동작 허용/모니터/검토/추가인증/차단/자금보류/동결/규제보고",
        "• 평가 즉시(실시간)/사후(비동기) · 상태 작성/결재대기/운영중/비활성/보관",
        "• 비활성(자동 비활성) 행 ⚠ + 사유 툴팁",
        "• 흐름 행 클릭 → SFDS-RULE-002 · [효과성 ▶ → SFDS-STAT-001] (BR-006)",
        "• 빌더 → 시뮬(RULE-006) → 결재 상신 → 라이프사이클(RULE-005) → ACTIVE",
        "▸ API GET /api/v1/admin/fds/rules"])


# 룰 상세(SFDS-RULE-002) 5탭 — 같은 부모 탭 바로 연속 전개(SKILL §1.6)
RULE_DETAIL_TABS = ["현재버전 조건", "버전 히스토리", "기준값", "최근 Hit", "결재 로그"]


def rule_002(p, tab=0):
    """SFDS-RULE-002 룰 상세 — ① 현재버전 조건"""
    s = frame(p, "SFDS-RULE-002",
              "FDS Console > 룰 관리 > MULE_BANK > 현재버전 조건",
              "[MULE_BANK] 룰 상세 — ① 현재버전 조건", action="비활성")
    y = wf.CON_TOP
    y = wf.tab_chips(s, y, RULE_DETAIL_TABS, active=0)
    y = wf.entry_banner(s, y, "SFDS-RULE-001 룰 목록에서 [룰 행 ▶] 클릭 → 룰 상세")
    y = wf.callout(s, y, "탐지 조건 요약 (자연어)", [
        "수취 계좌가 '대포통장 의심' 명단에 있으면, 그 계좌로의 송금을 차단",
        "도메인: 국내송금 · 계좌이체 채널 · 거래차단 · 즉시(실시간) 평가"])
    y = wf.two_panels(s, y, 1.55,
        ("단계별 동작", ["단계", "내용"],
         [["① 대상", "수취 계좌"],
          ["② 조건", "대포통장 의심 명단 포함 여부"],
          ["③ 기간", "즉시(실시간) 평가"],
          ["④ 탐지 시 동작", "거래 차단 + 케이스 자동 개설"]],
         [0.30, 0.70]),
        ("현재 버전 정보", ["항목", "값"],
         [["버전", "v2 (ACTIVE)"],
          ["작성자", "rule.eng"],
          ["승인자", "compliance.l"],
          ["활성 일시", "2026-05-15 14:30"],
          ["변경 노트", "감시 그룹 추가"]],
         [0.36, 0.64]))
    wf.info_panel(s, "SFDS-RULE-002", [
        "• 권한 SFDS_RULE:READ",
        "• 같은 부모 탭 바: 현재버전 조건 / 버전 히스토리 / 기준값 / 최근 Hit / 결재 로그",
        "• 현재 활성 버전의 탐지 조건·단계별 동작·자연어 요약 표시",
        "• 진입: SFDS-RULE-001 목록 → 행 클릭 (룰 번호 컨텍스트)",
        "• [새 버전] → SFDS-RULE-003 (룰 빌더)  |  [시뮬레이션] → SFDS-RULE-006",
        "• [비활성](OPERATE) / [롤백](APPROVE 2인) → SFDS-RULE-005 라이프사이클",
        "• 다음 → ② 버전 히스토리",
        "▸ API GET …/rules/{id}"])


def rule_002_versions(p):
    """SFDS-RULE-002 룰 상세 — ② 버전 히스토리"""
    s = frame(p, "SFDS-RULE-002",
              "FDS Console > 룰 관리 > MULE_BANK > 버전 히스토리",
              "[MULE_BANK] 룰 상세 — ② 버전 히스토리")
    y = wf.CON_TOP
    y = wf.tab_chips(s, y, RULE_DETAIL_TABS, active=1)
    y = wf.table_block(s, y, 2.55, "버전 히스토리 (변경 이력 · 7년 보존)",
        ["버전", "상태", "작성자", "승인자", "활성 일시", "변경 노트"],
        [["v2", "ACTIVE", "rule.eng", "compliance.l", "2026-05-15", "감시 그룹 추가"],
         ["v1", "SUPERSEDED", "rule.eng", "compliance.l", "2026-01-12", "최초 버전"],
         ["v0", "ARCHIVED", "rule.eng", "—", "—", "DRAFT(활성화 미완료)"]],
        [0.08, 0.14, 0.16, 0.16, 0.18, 0.28])
    wf.callout(s, y, "버전 운영 안내", [
        "각 버전 행 클릭 → 해당 버전 조건 상세 펼침(읽기 전용)",
        "[롤백] → 이전 SUPERSEDED 버전으로 즉시 복귀 (사유 필수 · APPROVE 2인)",
        "모든 버전 변경 이력(작성자·승인자·시각·changeNote) 7년 append-only 보존"])
    wf.info_panel(s, "SFDS-RULE-002", [
        "• 권한 SFDS_RULE:READ",
        "• 버전 히스토리 전수 — 상태별 ACTIVE/SUPERSEDED/ARCHIVED",
        "• 컬럼 버전·상태·작성자·승인자·활성 일시·변경 노트",
        "• 롤백 APPROVE 2인 필요 (사유 입력 필수)",
        "• 이전 ← ① 현재버전 조건  /  다음 → ③ 기준값",
        "▸ API GET …/rules/{id}/versions"])


def rule_002_threshold(p):
    """SFDS-RULE-002 룰 상세 — ③ 기준값"""
    s = frame(p, "SFDS-RULE-002",
              "FDS Console > 룰 관리 > MULE_BANK > 기준값",
              "[MULE_BANK] 룰 상세 — ③ 기준값 (파라미터)")
    y = wf.CON_TOP
    y = wf.tab_chips(s, y, RULE_DETAIL_TABS, active=2)
    y = wf.two_panels(s, y, 1.80,
        ("현재 기준값 파라미터", ["파라미터", "값", "설명"],
         [["명단 그룹", "MULE_ACCOUNTS", "대포통장 의심 계좌 차단 그룹"],
          ["평가 방식", "즉시(실시간)", "이벤트 수신 즉시"],
          ["동작", "거래차단", "차단 + 케이스 자동 개설"],
          ["canary 임계", "hit율 1% / 평가량 10만", "초과 시 자동 DISABLED"]],
         [0.28, 0.26, 0.46]),
        ("변경 이력 (기준값)", ["일시", "변경 전", "변경 후", "작업자"],
         [["2026-05-15", "MULE_OLD", "MULE_ACCOUNTS", "rule.eng"],
          ["2026-01-12", "—", "MULE_OLD", "rule.eng"]],
         [0.24, 0.24, 0.28, 0.24]))
    wf.callout(s, y, "기준값 빠른 변경 안내", [
        "[기준값 빠른 변경] → SFDS-RULE-004 (임계치만 Hot-reload · 본문 변경 불가)",
        "명단 그룹·파라미터 변경은 본 탭에서 확인 후 RULE-004로 이동",
        "규제 수치(CTR 임계 등) 빠른 변경 금지 → 4-eyes(새 버전 RULE-003)"])
    wf.info_panel(s, "SFDS-RULE-002", [
        "• 권한 SFDS_RULE:READ / 빠른 변경 SFDS_RULE:OPERATE",
        "• 현재 활성 버전의 파라미터(기준값·명단 그룹·동작·canary 임계) 표시",
        "• 기준값 변경 이력 — 변경 전/후 값·작업자",
        "• [기준값 빠른 변경] → SFDS-RULE-004 Hot-reload",
        "• 이전 ← ② 버전 히스토리  /  다음 → ④ 최근 Hit",
        "▸ API GET …/rules/{id} · PUT …/rules/{id} (임계 파라미터만)"])


def rule_002_hits(p):
    """SFDS-RULE-002 룰 상세 — ④ 최근 Hit"""
    s = frame(p, "SFDS-RULE-002",
              "FDS Console > 룰 관리 > MULE_BANK > 최근 Hit",
              "[MULE_BANK] 룰 상세 — ④ 최근 Hit")
    y = wf.CON_TOP
    y = wf.tab_chips(s, y, RULE_DETAIL_TABS, active=3)
    y = wf.filters(s, y, ["기간 최근 24시간", "결과 전체"])
    y = wf.table_block(s, y, 2.40, "최근 Hit 목록 (결정 조회 SFDS-DEC-001 프리필터)",
        ["처리시각", "결과", "대상", "금액/통화", "처리 시간"],
        [["06-06 11:02:17", "차단", "subj_8f..", "18,200,000 원", "41ms"],
         ["06-06 09:44:05", "차단", "subj_3c..", "5,500,000 원", "38ms"],
         ["06-05 22:11:30", "차단", "subj_1a..", "12,000,000 원", "44ms"],
         ["06-05 18:03:21", "차단", "subj_7d..", "8,800,000 원", "37ms"]],
        [0.24, 0.14, 0.20, 0.24, 0.18])
    wf.callout(s, y, "Hit 분석 요약", [
        "최근 24시간 Hit 건수: 142건 · hit율: 0.16% · 오탐(피드백): 12건",
        "행 클릭 → SFDS-DEC-002 (해당 결정 상세 · 판정 근거)",
        "[전체 결정 조회] → SFDS-DEC-001 룰 번호=MULE_BANK 프리필터 진입"])
    wf.info_panel(s, "SFDS-RULE-002", [
        "• 권한 SFDS_RULE:READ (DEC-001 READ 포함)",
        "• 최근 Hit 목록 — 처리시각·결과·대상·금액·처리시간",
        "• 기간 필터: 최근 1h/24h/7d · 결과 필터: 전체/차단/추가인증/보류",
        "• 행 클릭 → SFDS-DEC-002 (결정 상세·판정 근거)",
        "• hit율·오탐 피드백은 SFDS-DASH-002 룰 hit rate 패널과 동기",
        "• 이전 ← ③ 기준값  /  다음 → ⑤ 결재 로그",
        "▸ API GET …/rules/{id}/decisions (DEC-001 ruleNo 프리필터)"])


def rule_002_approval_log(p):
    """SFDS-RULE-002 룰 상세 — ⑤ 결재 로그"""
    s = frame(p, "SFDS-RULE-002",
              "FDS Console > 룰 관리 > MULE_BANK > 결재 로그",
              "[MULE_BANK] 룰 상세 — ⑤ 결재 로그")
    y = wf.CON_TOP
    y = wf.tab_chips(s, y, RULE_DETAIL_TABS, active=4)
    y = wf.table_block(s, y, 2.80, "결재 로그 (이 룰의 모든 결재 이력 · 7년 보존)",
        ["결재 일시", "결재 종류", "버전", "상신자", "승인자", "결과", "비고"],
        [["2026-05-15 14:28", "RULE 활성화", "v2", "rule.eng", "compliance.l", "승인", "감시 그룹 추가"],
         ["2026-05-15 14:10", "RULE 활성화", "v2", "rule.eng", "—", "상신", "결재 대기 중(완료)"],
         ["2026-01-12 10:05", "RULE 활성화", "v1", "rule.eng", "compliance.l", "승인", "최초 버전"],
         ["2026-01-12 09:50", "RULE 활성화", "v1", "rule.eng", "—", "상신", "결재 대기 중(완료)"]],
        [0.22, 0.18, 0.08, 0.16, 0.16, 0.10, 0.10])
    wf.callout(s, y, "결재 이력 안내", [
        "이 룰과 연관된 모든 결재(활성화·롤백·비활성) 이력 표시",
        "각 행 클릭 → SFDS-APPR-001 결재함 해당 건 상세(payload_hash·결재 단계)",
        "append-only · 작성자≠승인자 maker-checker 보증 · 7년 보존"])
    wf.info_panel(s, "SFDS-RULE-002", [
        "• 권한 SFDS_RULE:READ",
        "• 이 룰의 전체 결재 이력(활성화·롤백·비활성) 7년 보존",
        "• 컬럼 결재일시·종류·버전·상신자·승인자·결과·비고",
        "• 행 클릭 → SFDS-APPR-001 해당 결재 건 상세",
        "• maker-checker(작성자≠승인자) 규칙 검증 기록",
        "• 이전 ← ④ 최근 Hit  (룰 상세 5탭 끝)",
        "▸ API GET …/approvals?subjectId={ruleId}"])


def rule_003(p):
    s = frame(p, "SFDS-RULE-003", "FDS Console > 룰 관리 > 룰 빌더",
              "룰 빌더 (멀티도메인, 문장형)", action="DSL 토글")
    y = wf.CON_TOP
    y = wf.form_block(s, y, 2.00, "기본 조건 (문장형) [서비스: 은행 A]",
        [("① 도메인/채널 *", "해외송금(CROSS_BORDER_REMIT) ▼   ·   평가 방식 [사후 ▼]", "input"),
         ("② 탐지 대상 기준 *", "회원별 ▼ (회원/계좌/수단/상대방/단말기/가맹점/셀러/직원)", "input"),
         ("③ 측정 항목 *", "지갑주소 위험점수 ▼ (금액합계/건수/상대방수/주소위험/믹서…)", "input"),
         ("④ 집계 기간 *", "최근 24시간 ▼ (1시간/6시간/24시간/7일/30일)", "input"),
         ("⑤ 기준값(임계치) *", "80 점 ▼  이상이면 탐지", "input")])
    y = wf.condition_builder(s, y, 2.20,
        "⑥ 추가 조건 — 여러 조건을 AND/OR로 결합 (기본 조건과 함께 평가)",
        "AND",
        [("등록 경과일", "미만", "7 일"),
         ("Travel Rule 정보", "상태", "누락"),
         ("상대방 위험등급", "이상", "High")],
        footer_btns=["+ 조건 추가", "+ 그룹(괄호) 추가"],
        group_note="그룹 간 결합: AND ▼")
    wf.callout(s, y, "⑦ 탐지 시 동작 + 룰 미리보기 — 자연어", [
        "⑦ 탐지 시 동작 *  자금 보류 ▼  ☑ 컴플라이언스 케이스 자동 개설  (조치 종류 23종·Capability 범위 내)",
        "가상자산 출금·회원별 위험점수 ≥ 80점 이고, 추가조건[등록 7일 미만 AND Travel Rule 누락 AND 상대방 High↑] 모두 만족이면",
        "→ 자금 보류 + 컴플라이언스 케이스 자동 개설      [임시저장(DRAFT)]   [시뮬레이션 후 결재 상신(SUBMITTED)]"])
    wf.info_panel(s, "SFDS-RULE-003", [
        "• 권한 SFDS_RULE:AUTHOR",
        "• ① 채널 21종(DB §4.4) — 월렛충전(CASH_IN)·국내송금(DOMESTIC_REMIT)·해외송금(CROSS_BORDER_REMIT)·파트너인바운드(INBOUND_REMIT) 등 hanpass-ph 재그라운딩",
        "• 문장형 빌더 ①도메인 ②대상 ③측정 ④기간 ⑤기준값 ⑥추가조건 ⑦동작",
        "• ⑥ 추가 조건 여러 조건을 AND(모두 만족)/OR(하나라도)로 결합",
        "• 각 조건 = 필드 + 연산자 + 값 (업무 용어 드롭다운, 변수·필드명 미노출)",
        "• 연산자 이상/이하/미만/초과/같음/포함/누락 등",
        "• 그룹(괄호)으로 (A AND B) OR C 중첩 결합 지원",
        "• 기본 조건(①~⑤)과 추가 조건은 기본 AND 결합(토글 가능)",
        "• 미리보기 자연어로 결합 논리 확인 후 결재 상신",
        "• 쉬운 구성 ↔ DSL(JSON) 양방향 동기화(고급)",
        "▸ API POST/PUT …/rules · GET …/feature-catalog"])


def rule_004(p):
    s = frame(p, "SFDS-RULE-004", "FDS Console > 룰 관리 > 기준값 빠른 변경",
              "기준값(임계치) 빠른 변경 (Hot-reload)")
    y = wf.CON_TOP
    wf.form_block(s, y, 2.7, "기준값 빠른 변경 — [CRYPTO_RISK] [서비스: 은행 A]",
        [("현재 기준값", "80 점", "text"),
         ("새 기준값", "85 점", "input"),
         ("변경 사유 *", "오탐 비율 상승 반영", "input"),
         ("처리 티켓 번호 *", "OPS-2026-0517", "input"),
         ("반영 시간", "적용 후 약 30초 안에 전 인스턴스 반영", "text")],
        btns=["취소", "적용(약 30초)"])
    wf.info_panel(s, "SFDS-RULE-004", [
        "• 권한 SFDS_RULE:OPERATE",
        "• 동작 룰 본문은 두고 임계치 값만 변경하는 빠른 경로",
        "• 입력 새 기준값 · 변경 사유 · 처리 티켓 번호(필수)",
        "• 사유·티켓 미입력 시 제출 불가",
        "• 적용 후 약 30초 안에 전 인스턴스 반영(설정 poll)",
        "• 본문(조건·단계) 변경 불가 → 새 버전(RULE-003) 4-eyes",
        "• 규제 수치(CTR 임계 등) 빠른 변경 금지 → 4-eyes",
        "▸ API PUT …/rules/{id} (임계 파라미터만)"])


def rule_005(p):
    s = frame(p, "SFDS-RULE-005", "FDS Console > 룰 관리 > 라이프사이클",
              "결재·활성화·롤백·중지 (라이프사이클)")
    y = wf.CON_TOP
    y = wf.callout(s, y, "4-eyes 워크플로 (작성자 ≠ 승인자)", [
        "1. 작성자 룰 생성(DRAFT) → 2. 시뮬레이션 실행(과거 이벤트)",
        "3. 활성화 상신 /activate → 4-eyes 결재 게이트 자동 생성(approval_status=SUBMITTED)",
        "4. 승인자 검토·승인(APPROVED) → 5. BE relay → 룰 ACTIVE(canary)"])
    wf.table_block(s, y, 2.5, "라이프사이클 동작·권한·검증",
        ["동작", "권한", "검증·규칙"],
        [["활성화 상신(activate)", "SFDS_RULE:AUTHOR", "즉시 활성 아님 — 결재 게이트(SUBMITTED) 자동 생성"],
         ["승인(approve)(2인)", "SFDS_RULE:APPROVE", "작성자=승인자 → FDS-APPROVAL-SELF(409)"],
         ["relay → 활성(ACTIVE)", "BE 자동", "승인 후 BE relay가 ACTIVE 전이(canary)"],
         ["롤백(rollback)(2인)", "SFDS_RULE:APPROVE", "이전 SUPERSEDED 버전 복귀(사유 필수)"],
         ["중지(suspend)", "SFDS_RULE:OPERATE", "사유+재개 예정일 / canary 자동중지 구분"]],
        [0.26, 0.28, 0.46])
    wf.info_panel(s, "SFDS-RULE-005", [
        "• 권한 상신 AUTHOR / 승인·롤백 APPROVE / 중지 OPERATE",
        "• 흐름 DRAFT→시뮬레이션→activate(상신=SUBMITTED)→승인→relay→ACTIVE(canary)",
        "• activate=결재 상신, 즉시 활성 아님(결재 게이트 자동 생성)",
        "• approve 작성자=승인자 차단 FDS-APPROVAL-SELF",
        "• 미승인 relay 차단 FDS-APPROVAL-REQUIRED",
        "• rollback 이전 SUPERSEDED 버전 즉시 복귀(사유 필수)",
        "• activate 후 canary hit율·평가량 초과 시 자동 DISABLED+알림",
        "• 동시 수정 충돌 FDS-STATE-CONFLICT(409)",
        "▸ API POST …/activate(2인) · /rollback(2인) · /disable · approvals"])


# ── 7. 그룹·명단 ─────────────────────────────────────────────────
def grp_001(p):
    s = frame(p, "SFDS-GRP-001", "FDS Console > 그룹·명단", "그룹 목록 / 멤버 조회",
              action="+ 새 그룹")
    y = wf.CON_TOP
    y = wf.table_block(s, y, 1.85, "그룹 목록 [서비스: 은행 A]",
        ["그룹 코드", "종류", "용도", "등록 방식", "활성 멤버"],
        [["MULE_ACCOUNTS", "계좌", "차단", "수동", "1,204"],
         ["WATCHLIST_PEP_REF", "회원", "감시", "자동", "342"],
         ["BLACKLIST_IP", "IP", "차단", "수동", "156"],
         ["ALLOWLIST_VIP", "회원", "허용", "수동", "88"]],
        [0.34, 0.14, 0.14, 0.18, 0.20])
    y = wf.table_block(s, y, 1.5, "▶ MULE_ACCOUNTS 멤버 (1,204) · [+ 멤버 추가] [CSV]",
        ["식별자(마스킹)", "사유", "등록일", "만료일", "동작"],
        [["110****4567", "대포통장 신고", "2026-05-20", "—", "해제"],
         ["220****8901", "다발 차단", "2026-05-22", "2026-06-21", "해제"]],
        [0.24, 0.24, 0.20, 0.20, 0.12])
    wf.callout(s, y, "흐름 · 그룹·명단 운영", [
        "그룹 행 클릭 → 하단 멤버 패널 로드 · [+ 멤버 추가]/[CSV] → SFDS-GRP-002 (멤버 추가·해제·연장 4-eyes)",
        "[+ 새 그룹] → SFDS-GRP-003 (그룹 마스터 등록) · 그룹은 틀만 생성, 멤버는 GRP-001/002에서 등록",
        "룰 빌더(RULE-003)에서 '룰 hit 자동등록' 그룹은 탐지 시 대상 자동 추가 · 명단 변경 즉시 차단 캐시 무효화"])
    wf.info_panel(s, "SFDS-GRP-001", [
        "• 권한 SFDS_GROUP:READ",
        "• 컬럼 그룹 코드·종류·용도·등록 방식·활성 멤버",
        "• 종류(표시 9종) 회원/계좌/수단/단말기/가맹점/셀러/IP/이메일/상대방",
        "  → 저장 member_kind 3종(SUBJECT/INSTRUMENT/COUNTERPARTY) 환원",
        "• 용도 차단/허용/감시/뮬 네트워크",
        "• 등록 방식 수동/자동(룰 hit 시)",
        "• 멤버 식별자 PII 마스킹(앞3+뒤4) · 만료 임박 하이라이트",
        "• 흐름 [+ 멤버 추가]/[CSV] → SFDS-GRP-002 · [+ 새 그룹] → SFDS-GRP-003 (ADMIN만)",
        "▸ API GET …/risk-groups · /{id}/members"])


def grp_002(p):
    s = frame(p, "SFDS-GRP-002", "FDS Console > 그룹·명단 > 멤버 운영",
              "멤버 추가·해제·연장 (CSV)")
    y = wf.CON_TOP
    y = wf.form_block(s, y, 2.5, "멤버 추가 (단건/CSV 일괄) — MULE_ACCOUNTS",
        [("식별자 종류 *", "계좌 ▼", "input"),
         ("식별자 *", "토큰/해시 입력 (원문 미저장)", "input"),
         ("사유 *", "대포통장 신고", "input"),
         ("만료일", "2026-09-21  (비우면 영구)", "input"),
         ("CSV 일괄", "파일 업로드 → 검증·미리보기 → 확정", "check")],
        btns=["취소", "추가(2인)"])
    wf.table_block(s, y, 1.5, "동작 요약 · 버튼 시나리오 (진입: SFDS-GRP-001 [+ 멤버 추가]/[CSV])",
        ["동작", "규칙 · 결과"],
        [["[추가(2인)]", "단건/CSV → 4-eyes(2인) 승인 후 명단 반영 · 중복 → FDS-IDEMPOTENT-CONFLICT(409) 스킵 리포트"],
         ["[해제]", "사유 필수 · 즉시 효과(차단 캐시 무효화) · 이력 7년 → 차단 룰 즉시 미적용"],
         ["[연장]", "만료일 갱신(사유 권장) · 완료 후 SFDS-GRP-001 목록 복귀"]],
        [0.18, 0.82])
    wf.info_panel(s, "SFDS-GRP-002", [
        "• 권한 SFDS_GROUP:OPERATE",
        "• 추가 식별자 종류·식별자·사유·만료일 / CSV 일괄(검증·미리보기)",
        "• 해제 사유 필수 · 즉시 효과 · 이력 7년 보존",
        "• 연장 만료일 갱신",
        "• 중복 등록 FDS-IDEMPOTENT-CONFLICT(409) · CSV 중복/오류 스킵 리포트",
        "• self-service 방지(본인·관련 계정 직접 변경 불가)",
        "• PII 식별자 CSV도 토큰/해시 저장(원문 미저장)",
        "▸ API POST …/members(2인) · DELETE …/members/{ref}(2인)"])


def grp_003(p):
    s = frame(p, "SFDS-GRP-003", "FDS Console > 그룹·명단 > 그룹 등록",
              "그룹 등록 / 수정 (마스터 생성)")
    y = wf.CON_TOP
    wf.form_block(s, y, 3.6, "그룹 마스터 등록 [서비스: 은행 A]",
        [("그룹 코드 *", "MULE_ACCOUNTS (영문 대문자·숫자·_ · 변경 불가)", "input"),
         ("그룹 종류 *", "계좌 ▼ (회원/계좌/수단/단말기/가맹점/셀러/IP/이메일/상대방)", "input"),
         ("용도(=groupType) *", "(●) 차단  ( ) 허용  ( ) 감시  ( ) 뮬 네트워크", "radio"),
         ("등록 방식", "수동 등록 (읽기 전용 — 서버 관리, PUT 영속 제외)", "text"),
         ("룰 hit 자동등록", "✓ 사용 (읽기 전용 — 룰 빌더에서 관리)", "text"),
         ("기본 만료(일)", "90 · 비우면 영구 (읽기 전용 — 멤버 등록 정책에서 관리)", "text"),
         ("설명", "대포통장 의심 계좌 차단 그룹 (읽기 전용 — 컬럼 부재)", "text")],
        btns=["취소", "등록"])
    wf.info_panel(s, "SFDS-GRP-003", [
        "• 권한 SFDS_GROUP:ADMIN",
        "• 입력(영속) 그룹 코드·종류·용도(표시명·활성 — API §5.18)",
        "• 용도는 독립 usage 필드 없음 — groupType(risk_group_type 6종) enum에 포함",
        "• 등록 방식·자동등록·기본 만료·설명 읽기 전용(서버 관리, PUT 영속 제외)",
        "• 그룹 코드 immutable·unique · 중복 FDS-VALIDATION-001",
        "• 종류 생성 후 변경 불가(식별자 체계 상이)",
        "• 자동+autoEnrollOnHit 그룹만 룰 빌더 자동등록 대상",
        "• 그룹은 틀만 생성 · 멤버는 GRP-001/002에서 등록",
        "• 비활성은 멤버 0 확인 후 · 이력 7년 보존",
        "▸ API POST/PUT /api/v1/admin/fds/risk-groups"])


# ── 8. 탐지 결정 ─────────────────────────────────────────────────
def dec_001(p):
    s = frame(p, "SFDS-DEC-001", "FDS Console > 탐지 결정", "탐지 결정 조회")
    y = wf.CON_TOP
    y = wf.filters(s, y, ["룰 번호", "대상", "동작", "채널", "통화"])
    y = wf.filters(s, y, ["금액 min~max", "corridor 출발→도착", "기간 from~to"])
    y = wf.table_block(s, y, 2.55, "탐지 결정 조회 [서비스: 은행 A] (거래 1건 ≠ 결정 1건) · 행 ▶ → SFDS-DEC-002",
        ["처리시각", "룰 번호", "동작", "결과", "대상", "채널", "금액·통화", "corridor", "평가"],
        [["06-06 11:02:17", "MULE_BANK", "거래차단", "차단", "subj_8f..", "국내송금", "₱180,000", "PH→PH", "즉시 ▶"],
         ["06-06 11:01:55", "ATM_GEO", "추가인증", "추가인증", "subj_3a..", "월렛충전", "₱60,000", "PH→PH", "즉시 ▶"],
         ["06-06 11:00:02", "CRYPTO_RISK", "자금보류", "보류", "subj_7c..", "해외송금", "₱120,000", "PH→VN", "사후 ▶"],
         ["06-06 10:58:44", "TBML_INV", "검토", "통과", "subj_55..", "인바운드", "$2,400", "KR→PH", "사후 ▶"]],
        [0.13, 0.13, 0.10, 0.08, 0.10, 0.10, 0.12, 0.11, 0.13])
    wf.callout(s, y, "흐름 · 결정에서 조사로", [
        "행 클릭 → SFDS-DEC-002 (결정 상세·판정 근거·후속 조치 링크)",
        "대상(subject) 클릭 → SFDS-DEC-003 (Subject 통합 타임라인) · 룰 번호 → SFDS-RULE-002 최근 Hit 탭",
        "결정 → 액션(SFDS-ACT-001) → 케이스(SFDS-CASE-001) → 결재(SFDS-APPR-001) → 규제 보고(SFDS-REG-001)로 이어짐"])
    wf.info_panel(s, "SFDS-DEC-001", [
        "• 권한 SFDS_DECISION:READ",
        "• 필터 룰 번호·대상·동작·채널·통화·금액(min~max)·corridor(출발→도착)·기간(기본 24h)",
        "• 채널·통화·corridor = hanpass-ph 데이터 레이어(DB §5.5·연동 §7.2) — 규제 임계와 무관",
        "• 컬럼 처리시각·룰 번호·동작·결과·대상·채널·금액·통화·corridor·평가",
        "• 결과 통과/차단/추가인증/보류",
        "• 동작 허용/검토/추가인증/차단/자금보류/동결/규제보고",
        "• 한 거래 여러 룰 → 여러 행",
        "• 결정 13개월 즉시 조회 / 이상은 장기 보관소",
        "• 흐름 행 클릭 → SFDS-DEC-002 (결정 상세) · 대상 클릭 → SFDS-DEC-003 (타임라인)",
        "• 핵심 플로우 결정 → 액션(ACT) → 케이스(CASE) → 결재(APPR) → 규제 보고(REG)",
        "▸ API GET /api/v1/fds/decisions"])


def dec_002(p):
    s = frame(p, "SFDS-DEC-002", "FDS Console > 탐지 결정 > 상세",
              "결정 상세 (판정 근거) · [MULE_BANK] 차단")
    y = wf.CON_TOP
    y = wf.entry_banner(s, y, "SFDS-DEC-001 탐지 결정 목록에서 [결정 행 ▶] 클릭 → 결정 상세")
    y = wf.two_panels(s, y, 1.95,
        ("판정", ["항목", "값"],
         [["룰 번호+버전", "MULE_BANK v2"], ["동작 / 결과", "거래차단 / 차단"],
          ["처리시각", "06-06 11:02:17"], ["처리 시간", "41ms"],
          ["평가 방식", "즉시(실시간)"]],
         [0.40, 0.60]),
        ("판정 근거", ["항목", "값"],
         [["조건", "수취 계좌 명단 포함"], ["기준값", "명단(대포통장 의심)"],
          ["집계값", "동일 계좌 송신자 8명"], ["모델 점수", "외부 모델 제공(표시만)"]],
         [0.34, 0.66]))
    wf.two_panels(s, y, 1.45,
        ("대상 거래", ["항목", "값"],
         [["소스 시스템", "core-banking"], ["거래 유형", "계좌이체 송금"],
          ["금액/통화", "18,200,000 원"], ["거래 상태", "차단됨"]],
         [0.36, 0.64]),
        ("후속 조치 (딥링크)", ["항목", "값"],
         [["명단 자동등록", "대포통장 의심 → SFDS-GRP-001"], ["케이스 개설", "case_77f0 → SFDS-CASE-002"],
          ["발행 액션", "거래 차단 → SFDS-ACT-001"], ["타임라인", "→ SFDS-DEC-003"]],
         [0.34, 0.66]))
    wf.info_panel(s, "SFDS-DEC-002", [
        "• 권한 SFDS_DECISION:READ",
        "• 판정 추적번호·룰 번호+버전·동작·결과·처리시각·처리시간·평가",
        "• 판정 근거 집계값·기준값·충족 조건 + 모델 점수·설명",
        "• 대상 거래 원본 거래/이벤트 링크·소스·유형·금액·상태",
        "• 진입 SFDS-DEC-001 행 클릭 (결정 추적번호 컨텍스트)",
        "• 후속 조치 딥링크 그룹등록(GRP-001)·액션(ACT-001)·케이스(CASE-002)·타임라인(DEC-003)",
        "• '왜 차단/탐지'를 사람이 읽도록 설명(감사·CS 핵심)",
        "• ML 점수는 외부 소관(수신값·설명만, 산출 로직 미노출)",
        "▸ API GET /api/v1/fds/decisions/{decisionId}"])


def dec_003(p):
    s = frame(p, "SFDS-DEC-003", "FDS Console > 탐지 결정 > Subject 타임라인",
              "Subject(대상) 타임라인 (조사)")
    y = wf.CON_TOP
    y = wf.entry_banner(s, y, "SFDS-DEC-001 목록 [대상 클릭] · SFDS-DEC-002 후속 조치 [타임라인 ▶] → Subject 타임라인")
    y = wf.filters(s, y, ["대상: subj_8f.. (KYC 2단계)", "기간 최근 30일"])
    wf.table_block(s, y, 3.4, "통합 타임라인 (이벤트·결정·그룹·액션·케이스·보고 머지, 시간 desc)",
        ["시각", "유형", "내용"],
        [["06-06 11:02", "결정", "[MULE_BANK] 거래차단·차단 · 송금 18,200,000원"],
         ["06-06 11:02", "명단", "자동등록(대포통장 의심, 만료 2026-09-04)"],
         ["06-06 11:02", "케이스", "개설(대포통장 조사, case_77f0) [케이스로 이동]"],
         ["06-04 09:14", "결정", "[ATM_GEO] 추가인증 · ATM 출금 요청"],
         ["06-02 13:20", "이벤트", "단말기 변경(기기 정보 변경 감지)"],
         ["06-01 10:05", "규제 보고", "CTR 생성(영업일 누계 52만 페소) [규제 보고로 이동]"]],
        [0.18, 0.16, 0.66])
    wf.info_panel(s, "SFDS-DEC-003", [
        "• 권한 SFDS_DECISION:READ",
        "• 대상 1명의 이벤트·결정·그룹등록·액션·케이스·규제보고 단일 타임라인 머지",
        "• 정렬 시간 desc · 기간 필터(기본 최근 30일)",
        "• 각 항목 상세 화면 딥링크",
        "• 조사 목적 조회는 감사 로그에 기록(누가 무엇을 조회)",
        "• 대상 식별자 토큰/해시 기반 · 원문 회원정보는 서비스 소스 소관",
        "▸ API GET /api/v1/evidence/fds/cases/{caseId}/timeline (+필터 머지)"])


# ── 9. 이벤트 조회 ───────────────────────────────────────────────
def evt_001(p):
    s = frame(p, "SFDS-EVT-001", "FDS Console > 이벤트 조회",
              "Canonical 이벤트 조회")
    y = wf.CON_TOP
    y = wf.filters(s, y, ["소스 시스템 전체", "이벤트 종류 전체", "대상", "거래", "수단"])
    y = wf.table_block(s, y, 2.0, "Canonical 이벤트 조회 [서비스: 은행 A]",
        ["발생시각", "소스시스템", "이벤트 종류", "금액/통화"],
        [["06-06 11:02:01", "core-banking", "거래 요청", "18.2M / 원"],
         ["06-06 10:58:30", "atm-switch", "출금 요청", "200K / 원"],
         ["06-06 10:55:12", "legacy-card", "승인 요청", "52K / 원"]],
        [0.26, 0.24, 0.30, 0.20])
    wf.callout(s, y, "정규화 항목 (fds_canonical_events · raw 미저장)", [
        "tenantId · sourceSystem · schemaVersion · eventId · idempotencyKey",
        "eventType · occurredAt · subjectRef · transactionRef · channelType",
        "amount/currency · payloadHash (raw payload 미저장)"])
    wf.info_panel(s, "SFDS-EVT-001", [
        "• 권한 SFDS_DECISION:READ",
        "• 필터 소스 시스템·이벤트 종류·대상·거래·수단",
        "• 컬럼 발생시각·소스시스템·이벤트 종류·금액/통화",
        "• 흐름 행 클릭 → SFDS-DEC-001 (이 이벤트가 생성한 결정 목록 역참조)",
        "• PII(IP·계좌해시·이메일) BE 마스킹(앞3+뒤4)",
        "• raw payload 원칙 미저장 · 저장 시 break-glass+감사",
        "• 검증 실패(reject) 별도 필터 · payloadHash+사유만 보존",
        "• 13개월 hot / 이상 장기 보관소(서명 URL)",
        "▸ API GET /api/v1/fds/events/{eventId}"])


# ── 10. 액션 운영 ────────────────────────────────────────────────
def act_001(p):
    s = frame(p, "SFDS-ACT-001", "FDS Console > 액션 운영",
              "액션 큐 / 아웃박스")
    y = wf.CON_TOP
    y = wf.filters(s, y, ["조치 종류 전체", "상태 전체", "대상 시스템 전체", "추적 번호 검색"])
    y = wf.table_block(s, y, 2.7, "액션 아웃박스 [서비스: 은행 A] (BE outbox 자동 재시도·DLQ BE 운영)",
        ["발행시각", "조치 종류", "대상 시스템", "상태", "오류"],
        [["06-06 11:02:18", "거래 차단", "core-banking", "발행", "—"],
         ["06-06 11:00:05", "자금 보류", "crypto-wallet", "승인됨🔒", "—"],
         ["06-06 10:59:40", "승인 거부", "atm-switch", "대기", "일시적 응답없음"],
         ["06-06 10:55:20", "정산 보류", "settlement", "실패 ⚠", "권한 없음(404)"]],
        [0.22, 0.18, 0.24, 0.18, 0.18])
    wf.callout(s, y, "흐름 · 하단 동작 · 책임 경계", [
        "행 클릭 → 발단 결정 SFDS-DEC-002 (이 액션을 만든 판정 근거) · [상태 조회] 최신 발행 상태·재시도 횟수 재조회",
        "결재대기(APPROVAL_REQUIRED) 행 → SFDS-APPR-001 결재함에서 승인(2인) 후 BE relay 발행 (수동 재시도 버튼 없음)",
        "재시도=BE outbox 자동(지수 백오프, 5회 초과 → fds-actions-dlq) · DLQ 재처리=BE 운영"])
    wf.info_panel(s, "SFDS-ACT-001", [
        "• 권한 조회 SFDS_VIEWER / 운영 모니터링 SFDS_ACTION:OPERATE",
        "  (재시도는 BO 권한 아님 — BE relay 소관)",
        "• 필터 조치 종류·상태·대상 시스템 + 추적 번호",
        "• 컬럼 발행시각·조치 종류·대상 시스템·상태·오류",
        "• 조치 종류 23종: 거래차단·거래차단(transaction)·자금보류·보류연장·보류해제·거래취소·역전요청·",
        "  계정정지·수단정지·정산보류·셀러지급정지·준비금증액·추가증빙요청·그룹추가·케이스개설·알림발송·",
        "  2차승인요구·출금차단·API키정지·직원세션정지·Travel Rule정보요청·AML케이스개설·규제보고",
        "• 상태 대기/결재대기/승인됨/발행/수신확인/실패/취소",
        "• 흐름 행 클릭 → SFDS-DEC-002 (발단 결정·판정 근거) · 하단 [상태 조회]만",
        "• 재시도=BE outbox 자동 · 5회 초과 → DLQ · DLQ 재처리 BE 운영",
        "• 자금/규제 액션 결재대기 → SFDS-APPR-001 승인(2인) 후 BE relay",
        "• sandbox shadow-only 발행 행 없음",
        "▸ API GET /api/v1/fds/actions/{actionId} (상태 조회)"])


def act_002(p):
    s = frame(p, "SFDS-ACT-002", "FDS Console > 액션 운영 > Capability",
              "Capability 매트릭스", action="변경 결재(2인)")
    y = wf.CON_TOP
    y = wf.entry_banner(s, y, "SFDS-TNT-002 서비스 상세 ③ 마스킹·보안 탭 [조치 권한 매트릭스 ▶] 클릭 → Capability 매트릭스")
    wf.table_block(s, y, 3.6, "Capability 매트릭스 [서비스: 은행 A] (룰 동작이 벗어나면 케이스만)",
        ["소스 시스템", "차단전", "승인거부", "자금보류", "보류해제", "취소", "정지", "케이스만"],
        [["core-banking", "○", "—", "○", "○", "○", "○", "—"],
         ["atm-switch", "○", "○", "—", "—", "—", "○", "—"],
         ["legacy-card", "—", "○", "—", "—", "—", "○", "—"],
         ["audit-log", "—", "—", "—", "—", "—", "—", "○"],
         ["settlement", "—", "—", "○", "○", "—", "—", "—"]],
        [0.24, 0.11, 0.12, 0.12, 0.12, 0.09, 0.09, 0.11])
    wf.info_panel(s, "SFDS-ACT-002", [
        "• 권한 조회 SFDS_VIEWER / 변경 SFDS_ACTION:APPROVE(2인) (4-eyes)",
        "• 소스 시스템별 FDS 가능 조치 정의(control_capability 9종)",
        "• Capability 차단전·승인거부·자금보류·보류해제·취소·정지·케이스만",
        "• 룰 동작이 Capability 벗어나면 케이스 생성만(CAN_OPEN_CASE_ONLY)",
        "• 미지원 조치 발행 시 액션 실패(권한 없음 404)로 표면화",
        "• 변경 4-eyes(작성자≠승인자) · 이력 7년 보존",
        "▸ API GET …/source-systems · PUT …/{ss}(2인)"])


# ── 11. 케이스 관리 ──────────────────────────────────────────────
def case_001(p):
    s = frame(p, "SFDS-CASE-001", "FDS Console > 케이스 관리", "케이스 목록",
              action="+ 케이스")
    y = wf.CON_TOP
    y = wf.filters(s, y, ["케이스 유형 전체", "상태 전체", "우선순위 전체", "담당자 전체", "대상 검색"])
    y = wf.table_block(s, y, 2.6, "케이스 목록 [서비스: 은행 A] · 행 ▶ → SFDS-CASE-002 (케이스 상세)",
        ["케이스 번호", "유형", "대상", "우선", "담당자", "상태", "SLA"],
        [["case_77f0", "대포통장 조사", "subj_8f..", "높음", "analyst.a", "조사중", "14h ▶"],
         ["case_77f1", "AML 조사", "subj_3a..", "높음", "—", "신규", "미배정 ▶"],
         ["case_77f2", "무역금융 검토", "subj_7c..", "중간", "analyst.b", "종결 상신", "— ▶"],
         ["case_77f3", "내부 감사", "actor_55.", "높음", "audit.c", "조사중", "8h ▶"]],
        [0.18, 0.20, 0.14, 0.10, 0.14, 0.14, 0.10])
    wf.callout(s, y, "흐름 · 케이스 발단·진행", [
        "행 클릭 → SFDS-CASE-002 (케이스 상세·타임라인·연결 결정·종결)",
        "발단 결정 자동 개설(SFDS-DEC-002 후속 조치) · 수동 [+ 케이스] · 미배정 케이스는 [배정](OPERATE) 후 조사",
        "상세에서 [규제 보고 전환] → SFDS-REG-001 큐(aml-svc 위임) · [종결 상신] → 4-eyes 종결 승인(2인)"])
    wf.info_panel(s, "SFDS-CASE-001", [
        "• 권한 SFDS_CASE:READ",
        "• 필터 케이스 유형·상태·우선순위·담당자 + 대상 검색",
        "• 컬럼 케이스 번호·유형·대상·우선·담당자·상태·SLA",
        "• 우선순위 치명/높음/중간/낮음",
        "• 상태 신규/배정/조사중/규제전환/종결 상신/사기확정·오탐·보고후 종결",
        "• 헤더 진행·기한 임박·기한 초과 요약 · 임박/초과 행 강조",
        "• 미배정 케이스 분석가 배정(OPERATE) 후 조사",
        "• 흐름 행 클릭 → SFDS-CASE-002 (케이스 상세·종결·규제 전환)",
        "• 발단 결정(DEC-002) 자동 개설 · 수동 [+ 케이스] · 규제 전환 → SFDS-REG-001",
        "▸ API GET /api/v1/fds/cases"])


# 케이스 상세(SFDS-CASE-002) 4탭 — 같은 부모 탭 바로 연속 전개(SKILL §1.6)
CASE_DETAIL_TABS = ["개요·증적", "타임라인", "연결 결정·거래", "코멘트"]


def case_002(p):
    """SFDS-CASE-002 케이스 상세 — ① 개요·증적"""
    s = frame(p, "SFDS-CASE-002",
              "FDS Console > 케이스 관리 > case_77f0 > 개요·증적",
              "케이스 상세 — ① 개요·증적 (case_77f0)", action="종결 승인(2인)")
    y = wf.CON_TOP
    y = wf.tab_chips(s, y, CASE_DETAIL_TABS, active=0)
    y = wf.entry_banner(s, y, "SFDS-CASE-001 케이스 목록에서 [케이스 행 ▶] 클릭 → 케이스 상세")
    y = wf.two_panels(s, y, 2.0,
        ("케이스 개요", ["항목", "값"],
         [["케이스 번호", "case_77f0"],
          ["유형", "대포통장 조사"],
          ["상태", "조사중 (SLA 기한 14h)"],
          ["우선순위", "높음"],
          ["담당자", "analyst.a"],
          ["트리거 룰", "MULE_BANK"]],
         [0.36, 0.64]),
        ("증적 (Evidence)", ["항목", "값"],
         [["연결 결정", "1건 (거래차단)"],
          ["연결 거래", "1건 (송금 18,200,000원)"],
          ["증거 요약", "수취 계좌 명단 일치"],
          ["위험 신호", "동일 계좌 송신자 8명"],
          ["명단 등록", "대포통장 의심 (자동)"]],
         [0.36, 0.64]))
    wf.form_block(s, y, 2.2,
        "종결 처리 (4-eyes) · [재오픈]은 종결 상태에서만 노출(사유 모달) / [규제 보고 전환] → SFDS-REG-001",
        [("담당자", "analyst.a ▼", "input"),
         ("종결 사유 코드 *", "오탐-임계과민 ▼ (오탐 3종·확정 3종·추가조사-AML이관·기타 — 8종, 필수)", "input"),
         ("상세 메모", "조사 결과 보충 설명 (선택 · 코드와 분리 저장)", "input")],
        btns=["재오픈(종결 시)", "배정", "규제 보고 전환", "종결 상신", "종결 승인(2인)"])
    wf.info_panel(s, "SFDS-CASE-002", [
        "• 권한 조사 SFDS_CASE:OPERATE / 종결 승인 SFDS_CASE:APPROVE(2인) (4-eyes)",
        "• 같은 부모 탭 바: 개요·증적 / 타임라인 / 연결 결정·거래 / 코멘트 (4탭 연속)",
        "• 케이스 개요 트리거 룰·유형·상태·우선순위·담당자",
        "• 증적 연결 결정/거래·증빙·위험 신호·명단 등록 여부",
        "• 진입: SFDS-CASE-001 목록 → 행 클릭 (케이스 번호 컨텍스트)",
        "• [종결 상신] → 다른 승인자 [종결 승인(2인)] (FDS-APPROVAL-SELF 차단)",
        "• 종결 사유 코드 필수(8종 드롭다운) + 상세 메모(선택) 분리 (BR-007)",
        "• [재오픈] 종결 상태에서만 — 사유 필수·APPROVE 이상·자기 종결 건 금지(4-eyes)·SLA 재기산 (BR-006)",
        "• 다음 → ② 타임라인",
        "▸ API GET …/cases/{id} · /assign · /close(2인)"])


def case_002_timeline(p):
    """SFDS-CASE-002 케이스 상세 — ② 타임라인"""
    s = frame(p, "SFDS-CASE-002",
              "FDS Console > 케이스 관리 > case_77f0 > 타임라인",
              "케이스 상세 — ② 타임라인 (case_77f0)")
    y = wf.CON_TOP
    y = wf.tab_chips(s, y, CASE_DETAIL_TABS, active=1)
    y = wf.filters(s, y, ["대상: subj_8f..", "기간 최근 30일"])
    y = wf.table_block(s, y, 2.80,
        "통합 타임라인 (이벤트·결정·그룹·액션·케이스·보고 머지 · DEC-003 뷰)",
        ["시각", "유형", "내용"],
        [["06-06 11:02", "결정", "[MULE_BANK] 거래차단·차단 · 송금 18,200,000원"],
         ["06-06 11:02", "명단", "자동등록(대포통장 의심, 만료 2026-09-04)"],
         ["06-06 11:02", "케이스", "개설(대포통장 조사, case_77f0)"],
         ["06-04 09:14", "결정", "[ATM_GEO] 추가인증 · ATM 출금 요청"],
         ["06-02 13:20", "이벤트", "단말기 변경(기기 정보 변경 감지)"],
         ["06-01 10:05", "규제 보고", "CTR 생성(영업일 누계 52만 페소)"]],
        [0.18, 0.16, 0.66])
    wf.callout(s, y, "타임라인 안내", [
        "각 항목 클릭 → 해당 화면 상세 딥링크(결정→DEC-002, 케이스→CASE-002, 규제 보고→REG-001)",
        "조사 목적 조회는 감사 로그에 기록(누가 무엇을 조회) · 기간 필터(기본 30일)"])
    wf.info_panel(s, "SFDS-CASE-002", [
        "• 권한 SFDS_CASE:OPERATE",
        "• 이 케이스 대상의 이벤트·결정·그룹·액션·규제 보고 단일 타임라인 머지",
        "• 정렬 시간 desc · 기간 필터(기본 최근 30일)",
        "• 각 항목 상세 화면 딥링크",
        "• 조사 목적 조회 감사 로그 기록",
        "• 이전 ← ① 개요·증적  /  다음 → ③ 연결 결정·거래",
        "▸ API GET /api/v1/evidence/fds/cases/{caseId}/timeline"])


def case_002_decisions(p):
    """SFDS-CASE-002 케이스 상세 — ③ 연결 결정·거래"""
    s = frame(p, "SFDS-CASE-002",
              "FDS Console > 케이스 관리 > case_77f0 > 연결 결정·거래",
              "케이스 상세 — ③ 연결 결정·거래 (case_77f0)")
    y = wf.CON_TOP
    y = wf.tab_chips(s, y, CASE_DETAIL_TABS, active=2)
    y = wf.table_block(s, y, 1.55, "연결 결정 (이 케이스를 트리거한 탐지 결정)",
        ["처리시각", "룰 번호", "동작", "결과", "처리 시간"],
        [["06-06 11:02:17", "MULE_BANK", "거래차단", "차단", "41ms"]],
        [0.26, 0.22, 0.18, 0.16, 0.18])
    y = wf.table_block(s, y, 1.55, "연결 거래 (결정이 평가한 원본 거래)",
        ["발생시각", "소스 시스템", "거래 유형", "금액/통화", "거래 상태"],
        [["06-06 11:02:01", "core-banking", "계좌이체 송금", "18,200,000 원", "차단됨"]],
        [0.24, 0.22, 0.20, 0.22, 0.12])
    wf.callout(s, y, "연결 항목 딥링크", [
        "결정 행 클릭 → SFDS-DEC-002 (결정 상세 · 판정 근거 · 집계값)",
        "거래 행 클릭 → SFDS-EVT-001 (Canonical 이벤트 조회 · payloadHash)",
        "한 케이스에 여러 결정·거래가 연결될 수 있음 (그룹 탐지 시)"])
    wf.info_panel(s, "SFDS-CASE-002", [
        "• 권한 SFDS_CASE:OPERATE",
        "• 연결 결정 — 이 케이스를 개설한 탐지 결정 전수",
        "• 연결 거래 — 각 결정이 평가한 원본 이벤트(거래)",
        "• 결정 행 클릭 → SFDS-DEC-002 / 거래 행 클릭 → SFDS-EVT-001",
        "• 이전 ← ② 타임라인  /  다음 → ④ 코멘트",
        "▸ API GET …/cases/{id}/decisions · …/cases/{id}/events"])


def case_002_comments(p):
    """SFDS-CASE-002 케이스 상세 — ④ 코멘트"""
    s = frame(p, "SFDS-CASE-002",
              "FDS Console > 케이스 관리 > case_77f0 > 코멘트",
              "케이스 상세 — ④ 코멘트 (case_77f0)")
    y = wf.CON_TOP
    y = wf.tab_chips(s, y, CASE_DETAIL_TABS, active=3)
    y = wf.table_block(s, y, 2.20, "코멘트 이력 (조사 협업 · 7년 보존)",
        ["작성 일시", "작성자", "내용"],
        [["06-06 11:15", "analyst.a", "수취 계좌 명단 일치 확인 · 동일 계좌 송신자 추가 조회 진행"],
         ["06-06 11:30", "compliance.l", "오탐 가능성 낮음 · 규제 보고 전환 검토 요청"],
         ["06-06 12:05", "analyst.a", "규제 전환 요건 미충족 · 사기 확정 종결 상신 예정"]],
        [0.22, 0.18, 0.60])
    y = wf.form_block(s, y, 1.30, "코멘트 작성",
        [("내용 *", "조사 의견·협업 내용 입력 (최대 500자)", "input"),
         ("첨부", "파일 업로드 (PDF·이미지 · 감사 기록)", "check")],
        btns=["취소", "등록"])
    wf.info_panel(s, "SFDS-CASE-002", [
        "• 권한 SFDS_CASE:OPERATE",
        "• 코멘트 조사 담당자·승인자 간 협업 내용 기록 · 7년 보존",
        "• 컬럼 작성 일시·작성자·내용",
        "• 파일 첨부 가능(감사 목적 · 감사 로그 기록)",
        "• 코멘트 수정·삭제 불가(append-only)",
        "• 오탐 분류 종결 시 코멘트는 룰 hit rate 피드백(DASH-002)에 반영",
        "• 이전 ← ③ 연결 결정·거래  (케이스 상세 4탭 끝)",
        "▸ API GET·POST …/cases/{id}/comments · /feedback"])


# ── 12. 결재함 ───────────────────────────────────────────────────
def appr_001(p):
    s = frame(p, "SFDS-APPR-001", "FDS Console > 결재함",
              "결재함 (maker-checker)", admin="관리자 admin ▼")
    y = wf.CON_TOP
    y = wf.filters(s, y, ["유형 전체", "상태 전체", "상신자 전체", "대상 검색"])
    y = wf.table_block(s, y, 2.9, "결재 대기 목록 [서비스: 은행 A]",
        ["결재 종류", "대상", "상신자", "결재 라인", "상태"],
        [["RULE 활성화", "CRYPTO_RISK v3", "rule.eng", "COMPLIANCE_MANAGER", "상신"],
         ["ACTION 자금보류", "case_77f0", "analyst.a", "MAKER_CHECKER", "상신"],
         ["MAPPING 변경", "core-banking.v3", "ops.a", "MAKER_CHECKER", "상신"],
         ["SECRET 회전", "atm-switch key", "ops.a", "SECURITY_ADMIN", "상신"],
         ["GROUP 멤버추가", "MULE +120건", "analyst.b", "RISK_MANAGER", "상신"],
         ["EXPORT 최종본", "검사대응 pack", "comp.a", "COMPLIANCE_MANAGER", "상신"],
         ["CASE_CLOSE 종결", "case_91a2", "analyst.a", "COMPLIANCE_MANAGER", "상신"],
         ["MERCHANT_NORMALIZE", "mrc_5521", "risk.a", "RISK_MANAGER", "상신"],
         ["규제 팩 변경", "tenant_bank_a", "admin.a", "COMPLIANCE_MANAGER", "상신"]],
        [0.20, 0.22, 0.16, 0.28, 0.14])
    wf.callout(s, y, "흐름 · 선택 결재 동작 · 승인 결과", [
        "[승인](2인 · checker≠maker, 위반 시 FDS-APPROVAL-SELF 409) → BE relay 실행 →",
        "  RULE→ACTIVE(SFDS-RULE-005) · ACTION→발행(SFDS-ACT-001) · MAPPING→effective(SFDS-MAP-002)",
        "  GROUP→명단 반영(SFDS-GRP-001) · CASE_CLOSE→케이스 종결(SFDS-CASE-002)",
        "[반려](사유) → 상신 화면 회신 · ▶ 펼침: payload_hash·결재 단계·만료 시각·최대 실행 횟수",
        "payload_hash 고정 · 승인 후 payload 변경 시 무효(PAYLOAD-CHANGED) 재상신 · 만료 시 자동 EXPIRED"])
    wf.info_panel(s, "SFDS-APPR-001", [
        "• 권한 조회 SFDS_VIEWER / 승인·반려 결재 라인별 :APPROVE",
        "• 필터 유형(subject_kind 9종)·상태(8종)·상신자 + 대상",
        "• 결재 종류 ACTION/RULE/MAPPING/SECRET/GROUP/EXPORT/MERCHANT_NORMALIZE/CASE_CLOSE/POLICY_PACK (9종)",
        "• 규제 팩 변경(POLICY_PACK) 대상=tenant_id · 기본 COMPLIANCE_MANAGER (TNT-002 ④ 상신)",
        "• 결재 라인 자기승인차단/maker-checker/컴플라이언스/리스크/보안/임원 (6종)",
        "• 상태 작성/상신/승인/반려/취소/만료/실행/실행실패",
        "• [승인](2인) checker≠maker · AI agent는 maker만",
        "• payload_hash 무결성 · 변경 시 무효 재상신",
        "• 데이터스코프 적용 자기 스코프 결재만",
        "▸ API GET …/approvals · /{id}/approve(2인) · /reject"])


# ── 13. 규제 보고 ────────────────────────────────────────────────
def reg_001(p):
    s = frame(p, "SFDS-REG-001", "FDS Console > 규제 보고",
              "규제 보고 큐 (FDS origin)")
    y = wf.CON_TOP
    y = wf.filters(s, y, ["보고 유형 전체", "상태 전체", "기한 이전", "대상 검색"])
    y = wf.table_block(s, y, 2.4, "규제 보고 큐 [서비스: 은행 A] · 행 ▶ → SFDS-REG-002 (본 처리·제출=aml-svc 위임)",
        ["보고 번호", "유형", "대상", "금액", "트리거 룰", "상태", "제출기한"],
        [["reg_rep_01..", "CTR", "subj_x..", "520,000", "CTR_DAILY", "검토중", "07-10 17시"],
         ["reg_rep_02..", "STR", "subj_y..", "—", "STR_KYC", "검토중", "07-08 17시"],
         ["reg_rep_03..", "TR", "subj_z..", "0.5 BTC", "CRYPTO_TR", "작성", "07-11 17시"]],
        [0.18, 0.08, 0.13, 0.13, 0.16, 0.12, 0.20])
    wf.callout(s, y, "흐름 · 보고 유형 안내 (PEP·제재 대조는 외부 스크리닝 소관)", [
        "행 클릭 → SFDS-REG-002 (보고 후보 상세 · aml-svc 위임 추적, 직접 결재·제출 버튼 없음)",
        "CTR  고액 현금성 — 기준 금액 이상이면 정상 거래도 의무 보고 / STR  의심 거래 — 금액 무관 의심 정황 시 보고",
        "TR   Travel Rule — 가상자산 이전 정보 제공 의무(특금법) · 본 처리·제출=aml-svc 위임(FDS는 후보·추적만)"])
    wf.info_panel(s, "SFDS-REG-001", [
        "• 권한 SFDS_REG:AUTHOR(검토) / SFDS_REG:READ(조회)",
        "• 책임 경계 본 처리·제출=aml-svc 위임 (FDS는 후보·추적만)",
        "• 필터 보고 유형·상태·기한 이전·대상",
        "• 컬럼 보고 번호·유형·대상·금액·트리거 룰·상태·제출기한",
        "• 유형 CTR/STR/Travel Rule(TR)",
        "• 상태 aml-svc 결재 상태 cross-ref(작성/상신/승인/제출/반려/만료)",
        "• 기한 임박(≤24h) 경고색·초과 위험색+컴플라이언스 알림",
        "• 흐름 행 클릭 → SFDS-REG-002 (보고 후보 상세 · aml-svc 위임 추적)",
        "• 발단 케이스 [규제 보고 전환](SFDS-CASE-002) · 본 처리·제출=aml-svc 소관",
        "▸ API GET /api/v1/fds/cases?caseType=REGULATORY_REPORT,… → aml-svc"])


def reg_002(p):
    s = frame(p, "SFDS-REG-002", "FDS Console > 규제 보고 > 후보 상세",
              "보고 후보 상세 / aml-svc 위임 추적")
    y = wf.CON_TOP
    y = wf.entry_banner(s, y, "SFDS-REG-001 규제 보고 큐에서 [보고 행 ▶] 클릭 → 보고 후보 상세")
    y = wf.two_panels(s, y, 1.95,
        ("후보 근거 (읽기 전용)", ["항목", "값"],
         [["보고 번호", "CTR case_91a0"], ["amlCaseRef", "aml_rep_01.."],
          ["대상 / 금액", "subj_x.. / 50만 페소"], ["트리거", "CTR_DAILY"],
          ["근거", "영업일 누계 52만 ≥ 기준 50만"]],
         [0.34, 0.66]),
        ("위임 상태 (cross-ref)", ["항목", "값"],
         [["상태", "aml-svc 검토 중"], ["제출 기한", "07-10 17:00(관할)"],
          ["관할 양식", "한국 CTR 표준 v1 (aml-svc 소관)"], ["raw PII", "미전파"]],
         [0.34, 0.66]))
    wf.callout(s, y, "위임 흐름 (FDS 후보 → fds-aml-handoff → aml-svc) · 읽기 전용", [
        "1. 후보 action(REGULATORY_REPORT) + origin case",
        "2. FdsAmlHandoff(amlCaseRef·handoffType·reasonCodes) ※raw PII 미전파",
        "3. aml-svc: DRAFT → 4-eyes 결재 → 관할 제출 → 접수번호",
        "4. 상태 cross-ref → origin case CLOSED_REPORTED",
        "[aml-svc 보고서로 이동]  ※결재·제출 버튼은 AML 화면 소관"])
    wf.info_panel(s, "SFDS-REG-002", [
        "• 권한 조회 SFDS_REG:READ (본 처리는 aml-svc 권한)",
        "• 책임 경계 직접 결재·제출 버튼·승인자 코멘트 없음",
        "• 후보 근거 트리거 룰·집계값·기준값·연결 거래(읽기 전용)",
        "• 위임 상태 amlCaseRef cross-ref(작성/상신/승인/제출/반려/만료)",
        "• 제출 기한·EXPIRED 전이는 aml-svc 상태머신 소관",
        "• 관할 양식 정의·변환·제출 aml-svc 소관(안내만)",
        "• [aml-svc 보고서로 이동] 딥링크(직접 동작 없음)",
        "• raw PII 미전파(token/hash·집계값만) · 멱등 caseId",
        "▸ API GET …/cases/{id}+amlCaseRef → aml-svc(AML PRD)"])


# ── 14. Evidence Export ──────────────────────────────────────────
def exp_001(p):
    s = frame(p, "SFDS-EXP-001", "FDS Console > Evidence",
              "Evidence Export (검사대응 self-service)", admin="관리자 admin ▼")
    y = wf.CON_TOP
    y = wf.form_block(s, y, 2.85, "Evidence Export self-service [서비스: 은행 A]",
        [("export 종류 *", "결정 리포트 ▼ (결정/케이스 타임라인·결정 리포트·커넥터 보정·오탐·개인정보 접근)", "input"),
         ("형식 *", "PDF ▼  (CSV / EXCEL / PDF / JSON_API)", "input"),
         ("기간 *", "2026-01-01 ~ 2026-01-31", "input"),
         ("최종본(제출용)", "→ 4-eyes 결재(2인) (컴플라이언스 책임자)", "check"),
         ("생성 상태", "요청됨 → 생성중 → 준비완료 · manifest hash 보존", "text")],
        btns=["취소", "생성 요청"])
    wf.callout(s, y, "생성·다운로드 · 무결성", [
        "상태 요청됨 → 생성중 → 준비완료 → 다운로드됨 / 만료 / 실패",
        "[다운로드] READY/DOWNLOADED 상태만 활성 · 다운로드 시 감사 기록",
        "manifest hash(READY 발급)로 무결성 보존 · raw PII 미포함(토큰/해시)"])
    wf.info_panel(s, "SFDS-EXP-001", [
        "• 권한 추출 SFDS_*:EXPORT / 최종본 4-eyes SFDS_REG:APPROVE(2인)",
        "• 입력 export 종류(6종)·형식(4종)·기간(필수) · 미입력 시 비활성",
        "• export 종류 결정/케이스 타임라인·결정 리포트·커넥터 보정·오탐·개인정보 접근",
        "• 최종본 체크 시 4-eyes(subject_kind=EXPORT) 게이트 강제",
        "• 미승인 시 FDS-APPROVAL-REQUIRED(409) 차단",
        "• 상태 요청됨/생성중/준비완료/다운로드됨/만료/실패",
        "• READY 시 manifest_hash 발급·보존 · raw PII 미포함",
        "• [다운로드] 감사 기록 · 데이터스코프 적용",
        "▸ API POST …/exports(2인) · GET …/{id} · /download"])


# ── 15. 감사 로그 ────────────────────────────────────────────────
def audit_001(p):
    s = frame(p, "SFDS-AUDIT-001", "FDS Console > 감사 로그",
              "운영 변경 감사 로그")
    y = wf.CON_TOP
    y = wf.filters(s, y, ["대상 전체", "작업자 전체", "기간 from~to", "대상 ID", "검색"])
    y = wf.table_block(s, y, 2.6, "운영 변경 감사 로그 [서비스: 은행 A] (append-only · 7년)",
        ["시각", "대상", "작업자", "작업", "대상 항목"],
        [["06-06 11:10", "룰", "rule.eng", "새 버전 활성", "MULE_BANK"],
         ["06-06 10:55", "커넥터", "ops.a", "시크릿 변경", "core-banking"],
         ["06-06 10:40", "필드매핑", "ops.a", "PII 정책 변경", "core-bank.v2"],
         ["06-06 10:20", "Capability", "approver.b", "자금보류 허용", "settlement"],
         ["06-06 10:05", "원문 접근", "analyst.c", "break-glass 조회", "subj_8f.."]],
        [0.18, 0.16, 0.18, 0.26, 0.22])
    wf.callout(s, y, "감사 대상·보존 (전 항목 7년)", [
        "룰·커넥터·매핑·Capability·케이스·고위험 액션 override·관리자 권한 변경",
        "원문(raw data) 접근(break-glass)·규제 보고 상태 전이",
        "append-only(수정·삭제 불가) · 변경 전/후 값(diff) 표시"])
    wf.info_panel(s, "SFDS-AUDIT-001", [
        "• 권한 SFDS_AUDIT:READ",
        "• 필터 대상(룰/커넥터/매핑/Capability/케이스/원문접근/권한)·작업자·기간·대상 ID",
        "• 컬럼 시각·대상·작업자·작업·대상 항목",
        "• 2인 결재 위반·우회 시도 탐지 리포트(주기)",
        "• 개인정보 삭제 요청 시 식별자 마스킹 치환(7년 보존 충돌 회피)",
        "• append-only(수정·삭제 불가) · diff 표시",
        "• 데이터스코프 적용(서비스 관리자는 자기 서비스만)",
        "• 1만 건 초과 시 조건 좁히기 안내",
        "▸ API GET /api/v1/bo/fds/audit (bo-api 소유·집약)"])


# ── 빌드 ─────────────────────────────────────────────────────────
def rule_006(p):
    s = frame(p, "SFDS-RULE-006", "FDS Console > 룰 관리 > 시뮬레이션",
              "룰 시뮬레이션 (백테스트 · 과거 데이터)", action="DSL 토글")
    y = wf.CON_TOP
    y = wf.form_block(s, y, 2.25, "시뮬레이션 설정 [서비스: 은행 A]",
        [("대상 룰 *", "신규 빌더 룰(미저장 ruleJson) ▼    |    기존 룰 [MULE_BANK] ▼", "input"),
         ("과거 데이터 기간 *", "[2026-05-01 00:00]  ~  [2026-05-31 23:59]    빠른선택: 최근 7일/30일/90일 ▼", "input"),
         ("평가 범위", "도메인 가상자산 출금 ▼   ·   채널 전체 ▼   ☑ 현재 운영 룰과 비교", "input")],
        btns=["시뮬레이션 실행"])
    y = wf.kpi_cards(s, y, [
        ("탐지(Hit) 건수", "1,284 건", "예상 Hit율 0.31%", "blue"),
        ("차단 시 영향", "902 건", "자금보류 902 · 케이스 88", "orange"),
        ("추정 오탐", "6.4 %", "현재 룰 대비 +0.7%p", "red"),
        ("평가 이벤트", "412,900 건", "2026-05-01 ~ 05-31", "green")])
    y = wf.table_block(s, y, 1.2, "샘플 Hit (과거 기간 · 상위 점수순)",
        ["일시", "대상(식별자)", "측정값", "점수", "시 동작"],
        [["05-14 02:11", "cust_…123", "지갑위험 0.94", "94", "자금보류"],
         ["05-22 19:40", "cust_…777", "지갑위험 0.91", "91", "자금보류"]],
        [0.20, 0.28, 0.22, 0.12, 0.18])
    wf.callout(s, y, "시뮬레이션 권고", [
        "임계치 80→78점이면 Hit +14% · 추정 오탐 +2.1%p (오탐/적중 균형 검토)",
        "[결과 저장(simulationId)]   [이 결과 첨부해 결재 상신]   [룰 빌더로 돌아가기]"])
    wf.info_panel(s, "SFDS-RULE-006", [
        "• 권한 SFDS_RULE:AUTHOR (fds:rule:simulate)",
        "• 대상 신규 빌더 룰(미저장 ruleJson) 또는 기존 룰(ruleId)",
        "• 과거 데이터 기간 sampleWindow[from~to] · 최근 7/30/90일 빠른선택",
        "• 결과 예상 Hit율(estimatedHitRate)·차단 영향·추정 오탐·평가 이벤트",
        "• 샘플 Hit 목록(상위 점수) · 현재 운영 룰 대비 비교",
        "• 권고 임계치 조정 시 Hit·오탐 변화 추정",
        "• 결과는 결재 상신 시 첨부(즉시 평가 룰 필수)",
        "• 과거 적재 이벤트 기준(read-only) · raw PII 미노출(토큰)",
        "▸ API POST …/rules/simulations · GET …/rules/simulations/{id}"])


# ─── SFDS-STAT-001 룰 효과성 통계 (v6.0 벤치마크 보강, 2탭) ───
STAT_001_TABS = ["룰 효과성", "오탐 피드백 분석"]


def stat_001(p, tab=0):
    titles = ["룰 효과성 통계 — ① 룰 효과성 (폐루프: 정의→임계→시뮬→운영→평가)",
              "룰 효과성 통계 — ② 오탐 피드백 분석 (케이스 종결 사유 FP_*)"]
    crumbs = ["FDS Console > 룰 관리 > 룰 효과성 통계 > 룰 효과성",
              "FDS Console > 룰 관리 > 룰 효과성 통계 > 오탐 피드백 분석"]
    s = frame(p, "SFDS-STAT-001", crumbs[tab], titles[tab], search="룰 번호 검색...")
    y = wf.CON_TOP
    y = wf.tab_chips(s, y, STAT_001_TABS, active=tab)
    if tab == 0:
        y = wf.filters(s, y, ["기간 최근 30일", "도메인 전체", "동작 전체"])
        y = wf.kpi_cards(s, y, [
            ("평가 이벤트", "12.4 M", "최근 30일", "blue"),
            ("탐지(Hit)", "4,812 건", "탐지율 0.039%", "orange"),
            ("차단·보류", "1,920 건", "케이스 388", "red"),
            ("케이스 전환율", "8.2 %", "전월 7.4% (+0.8%p)", "green")])
        y = wf.table_block(s, y, 1.70, "룰별 효과성 (행 ▶ → SFDS-RULE-002 · [백테스트] → SFDS-RULE-006)",
            ["룰 번호", "동작", "탐지", "케이스 전환", "오탐율(피드백)", "전월 대비", "권고"],
            [["MULE_BANK", "거래차단", "412", "11.2%", "4.1%", "▲ +0.3%p", "유지 ▶"],
             ["ATM_GEO", "추가인증", "186", "6.1%", "8.8%", "▲ +2.0%p", "임계 검토 ⚠ ▶"],
             ["TBML_INV", "검토", "12", "0.8%", "31.0%", "▲ +9.1%p", "튜닝 후보 ⚠ ▶"]],
            [0.15, 0.11, 0.08, 0.14, 0.17, 0.13, 0.22])
        wf.callout(s, y, "① 룰 효과성 — read-only 집계 (raw PII 미포함 · 30~60초 캐시)", [
            "진입 NAV 룰 관리 / SFDS-RULE-001 룰 행 [효과성 ▶] (룰 번호 컨텍스트)",
            "다음 → ② 오탐 피드백 분석 탭"])
        wf.info_panel(s, "SFDS-STAT-001", [
            "• 권한 SFDS_RULE:READ (read-only 집계)",
            "• 탭 ① 룰 효과성 / ② 오탐 피드백 분석",
            "• 필터 기간(기본 30일)·도메인·동작 + 룰 번호",
            "• 카드 평가 이벤트·탐지·차단/보류·케이스 전환율",
            "• 컬럼 룰·동작·탐지·케이스 전환·오탐율·전월 대비·권고",
            "• 권고 유지/임계 검토 ⚠/튜닝 후보 ⚠ — 판단 근거만 제공",
            "• 개별 건 드릴다운 SFDS-DEC-001(결정)·SFDS-CASE-001(케이스)",
            "• 다음 → ② 오탐 피드백 분석",
            "▸ API GET /api/v1/bo/fds/stats/rules (제안 · 후속 API 정합)"])
    else:
        y = wf.kpi_cards(s, y, [
            ("오탐 피드백 총계", "86 건", "최근 30일 FP_* 종결", "blue"),
            ("오탐-임계과민", "41 건", "FP_THRESHOLD", "orange"),
            ("오탐-정상거래패턴", "33 건", "FP_NORMAL_PATTERN", "green"),
            ("오탐-데이터품질", "12 건", "FP_DATA_QUALITY", "red")])
        y = wf.two_panels(s, y, 1.85,
            ("룰별 오탐율 추이", ["룰 번호", "당월", "전월", "추세"],
             [["TBML_INV", "31.0%", "21.9%", "악화 ⚠"],
              ["ATM_GEO", "8.8%", "6.8%", "악화 ⚠"],
              ["CRYPTO_RISK", "6.4%", "6.6%", "유지"],
              ["MULE_BANK", "4.1%", "3.8%", "유지"]],
             [0.32, 0.20, 0.20, 0.28]),
            ("튜닝 후보 (권고 사유)", ["룰 번호", "권고 사유", "권고 액션"],
             [["TBML_INV", "임계 과민·표본 부족", "[백테스트]→RULE-006"],
              ["ATM_GEO", "정상 패턴 오탐 증가", "[임계 변경]→RULE-004"],
              ["CNP_VEL", "데이터 품질(단말기)", "[매핑 점검]→MAP-002"]],
             [0.22, 0.34, 0.44]))
        wf.callout(s, y, "② 오탐 피드백 — 원천 = 케이스 종결 사유 FP_* 3종 누적 (§11.2 폐루프)", [
            "DASH-002 '룰 hit rate/오탐' 위젯의 상세 분석 화면 — 튜닝 적용은 RULE-003/004/005 4-eyes 경유",
            "이전 ← ① 룰 효과성 (효과성 통계 2탭 끝)"])
        wf.info_panel(s, "SFDS-STAT-001", [
            "• 권한 SFDS_RULE:READ (read-only 집계)",
            "• 탭 ② 오탐 피드백 분석",
            "• 카드 FP 총계·임계과민·정상거래패턴·데이터품질 (close_reason FP_* 3종)",
            "• 룰별 오탐율 추이(당월/전월/추세) + 튜닝 후보(권고 사유·액션)",
            "• 원천 케이스 종결 FP_* 피드백(§11.2 BR-002 폐루프·DB §4.11)",
            "• 본 화면 직접 변경 불가 — 튜닝은 RULE-003/004/005 결재 경유",
            "• 이전 ← ① 룰 효과성 (2탭 끝)",
            "▸ API GET /api/v1/bo/fds/stats/false-positives (제안 · 후속 API 정합)"])


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


def build():
    p = wf.new_deck()
    # 1 커버
    wf.cover_slide(p,
        "SaaS FDS Platform 백오피스 기획서",
        "멀티서비스·멀티도메인 이상거래 탐지 플랫폼 — Admin Console 화면 설계",
        ["정본 PRD: docs/plan/01-fds-sass-functional-spec.md (FS-FDS-001 v6.0)",
         "기능 ID 전수 34화면 (SFDS-DASH ~ SFDS-AUDIT · RULE-001~006·STAT-001·CONN-001~004 포함)",
         "좌 75% 와이어프레임(실제 도형) + 우 25% 기능 설명",
         "표시 용어=PRD 한국어 업무 용어 · enum 괄호 병기 · 책임 경계 명시",
         "목록→상세→액션→케이스→결재→규제 보고 시나리오 흐름 연결(딥링크 전수)",
         "버전 BO-FDS-SASS-Planning v8.2 (테넌트=서비스 재정의 — 고객사→서비스·상위 기관·기관→서비스→워크스페이스)"])
    # 2 변경 이력
    wf.history_slide(p, "변경 이력",
        ["버전", "일자", "작성자", "변경 내역"],
        [["v1.0", "2026-06-06", "SM Kim", "최초 작성 — 12개 화면 그룹(24화면) 정의"],
         ["v3.0", "2026-06-06", "SM Kim", "enum 전수·표시 용어 통일 재빌드"],
         ["v3.1", "2026-06-06", "SM Kim", "API 경로·enum 정합(bo-api 소유 경계)"],
         ["v4.0", "2026-06-07", "SM Kim", "도형 기반 PPT 전면 재생성 — SFDS-* 32화면 전수·시나리오 흐름 딥링크 연결"],
         ["v4.1", "2026-06-08", "SM Kim", "정합성 정정 — 격리→배포 모델(deployment_model) 재설계, TNT 화면 배포·온보딩 반영"],
         ["v4.2", "2026-06-08", "SM Kim", "정합성 정정 — DASH 건전성 컬럼·CONN 설정변경·RULE/APPR 샘플 정합"],
         ["v4.3", "2026-06-08", "SM Kim", "정합성 정정 — DASH 필터 단일축·RULE 컬럼 '도메인/채널'·APPR subject_kind 9종"],
         ["v4.4", "2026-06-08", "SM Kim", "고객사 상세(TNT-002) 5탭 연속 전개(기본정보→배포온보딩→마스킹보안→PolicyPack→알림소스)"],
         ["v4.5", "2026-06-08", "SM Kim", "RULE-002·CASE-002 탭 연속 전개(룰 상세 5탭·케이스 상세 4탭)"],
         ["v4.6", "2026-06-09", "SM Kim", "드릴다운 진입 트리거 배너 — TNT/CONN/MAP/RULE/DEC/ACT/CASE -002 상단 ↩ 배너 전수 추가, 소스 목록 행 ▶ 표기"],
         ["v4.7", "2026-06-10", "SM Kim", "TNT-002 ④ Policy Pack 토글·스테이징 모델 명문화 — 6팩 카탈로그·영향 미리보기·POLICY_PACK 4-eyes"],
         ["v4.8", "2026-06-10", "SM Kim", "준법감시인 검토 반영: 결재함 POLICY_PACK 행 추가, 케이스 재오픈·종결사유코드 신설"],
         ["v4.9", "2026-06-10", "SM Kim", "QA 정합화: ACT 조치 종류 23종·TNT-002 ③ 케이스전용 행·소스 시스템명 정정·REG-001 드릴다운 표기"],
         ["v5.0", "2026-06-11", "SM Kim", "QA 정합화: REG-002 진입 배너 추가(ppt-flow HIGH), 커버 PRD 버전 v3.6, 맺음말 v4.9 포인터 정정"],
         ["v5.1", "2026-06-11", "SM Kim", "정합성 QA 높음 이격 해소(룰 빌더 순서·DEC-003 진입 배너 등)"],
         ["v5.2", "2026-06-11", "SM Kim", "QA 정합화: GRP-003 용도 필드 groupType 통합 표기"],
         ["v5.3", "2026-06-11", "SM Kim", "QA 정합화: TNT-002 ⑤ 소스표 5컬럼·CONN-002 경로 변수 정정"],
         ["v6.0", "2026-06-12", "SM Kim", "실계 벤치마크 보강(GTone 80화면·AML §12-B 대응): STAT-001 룰 효과성 통계 신설·RULE-001 효과성 컬럼(33화면)"],
         ["v7.0", "2026-06-12", "SM Kim", "데이터 인입 가시성: CONN-004(수신 API 카탈로그·인입 라이브) 신설·CONN-001/002 인입 신호·인입 유형 확정 §4.0(34화면)"],
         ["v8.0", "2026-06-19", "SM Kim", "메뉴 IA 재구성 — 운영(조사·모니터링/케이스·처리/거버넌스·보고)·설정(연동·데이터/탐지 정책/감사·증적) 2영역 3단 분리, NAV·슬라이드 순서 재정렬(34화면·콘텐츠 불변), nav_tree 렌더"],
         ["v8.1", "2026-06-19", "SM Kim", "데이터 레이어 hanpass-ph 소스 재그라운딩(소스 카탈로그·CASH_IN/INBOUND_REMIT·corridor·연동 키) — 규제 불변"],
         ["v8.2", "2026-06-19", "SM Kim", "테넌트=서비스 재정의 — 고객사→서비스·상위 기관·기관→서비스→워크스페이스 (고객사 관리→서비스 관리·라벨 정합, 콘텐츠 불변)"]],
        col_w=[0.08, 0.12, 0.10, 0.70])
    # 3+ 기능 전수
    for fn in SCREENS:
        fn(p)
    out = "/Users/smkim/workspace/smkim89/aml-system-docs/docs/plan/BO-FDS-SASS-Planning_v8.2.pptx"
    p.save(out)
    print(f"saved {out} · slides={len(p.slides._sldIdLst)}")


if __name__ == "__main__":
    build()
