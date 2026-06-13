"""
BO-AML-SAAS-Planning_v8.0.pptx 생성 (도형 기반 · 데이터 인입 가시성 보강)
=========================================================================
정본 PRD: docs/plan/02-aml-sass-functional-spec.md (FS-AML-SAAS-001, 표시 용어=진실)
시각 정본: docs/plan/sample.pptx (맑은 고딕·Ant Design·순수 rect)
컴포넌트: wireframe_lib.py (ASCII 금지, 실제 rect 도형) — FDS v4.0과 동일 품질

용어: 고객사(tenant_id) / 서비스(workspace_id). 1 고객사 : N 서비스.
슬라이드: 1=커버 / 2=변경 이력 / 3~ 기능 ID 전수(AML-*, ID 순 · 목록→상세→액션 흐름 연결)
좌 75% 와이어프레임(실제 도형) + 우 25% info_panel(권한·필터·컬럼·동작·흐름·API)
실행: cd .claude/skills/backoffice-planner && python3 generate_aml.py
"""
import wireframe_lib as wf

TOP = "SaaS AML Platform 백오피스"
# NAV = 논리 그룹(상세 화면은 NAV 항목 아님 — 드릴다운 진입)
NAV = ["AML 종합 대시보드", "고객사 관리", "WLF 검토", "명단 소스·임포트", "국가위험 관리",
       "RA·CDD", "TM 알림·시나리오", "케이스 관리", "규제 보고", "기관 RBA 보고",
       "Travel Rule", "Policy Pack", "결재 대기함", "통계·내부통제", "감사·증적"]
# 기능 ID prefix → NAV active 인덱스
NAVIDX = {
    "DASH": 0, "TNT": 1, "WLF": 2, "WL": 3, "CTRY": 4, "RA": 5, "CDD": 5,
    "HRR": 5, "TM": 6, "CASE": 7, "REP": 8, "IRA": 9, "TR": 10, "PP": 11,
    "APR": 12, "STAT": 13, "EDU": 13, "AUD": 14, "ING": 14,
}


def frame(p, sid, crumb, title, search="검색...", admin="관리자 admin ▼", action=None):
    s = wf.add_slide(p)
    wf.page_title(s, TOP, sid)
    wf.header_bar(s, search_ph=search, admin=admin, action=action, brand="HANPASS AML")
    wf.nav_panel(s, NAV, active=NAVIDX[sid.split("-")[1]])
    wf.breadcrumb_title(s, crumb, title)
    return s


# ═══ 1. AML 종합 현황 대시보드 ═══════════════════════════════════
def dash_001(p):
    s = frame(p, "AML-DASH-001", "AML Console > 종합 현황 대시보드",
              "고객사별·서비스별 AML 종합 현황", search="대상·케이스·보고 검색...")
    y = wf.CON_TOP
    y = wf.filters(s, y, ["고객사 은행 A", "서비스 전체", "기간 최근 7일"])
    y = wf.kpi_cards(s, y, [
        ("WLF 검토 필요", "18 건", "상위승인 2", "blue"),
        ("RA 높음(명)", "1,204", "3% · 중간 12,880", "orange"),
        ("TM 미처리", "126 건", "케이스 전환 42", "green"),
        ("케이스 SLA", "58 건", "임박 7 ⚠ · 초과 0", "red"),
        ("기한 임박 보고", "2 건", "STR D-3 1 · CTR 1 ⚠", "orange"),
        ("결재 대기", "5 건", "만료 임박 2 ⚠", "orange")])
    y = wf.callout(s, y, "운영 알림 (카드·알림 클릭 → 해당 상세로 드릴다운)", [
        "제재 명단 일일 갱신 누락 — 18시간 경과 [클릭 → AML-WL-001 임포트 이력]",
        "WLF 검토 큐 적체 18건 · 상위승인 2건 [클릭 → AML-WLF-001]",
        "법정 보고 기한 임박 2건 (STR 3영업일·CTR 30일, D-3 ⚠) [클릭 → AML-REP-001]",
        "결재 만료 임박 2건 [클릭 → AML-APR-001]  ·  EDD 재심사 임박 7명 [클릭 → AML-CASE-001]"])
    wf.two_panels(s, y, 2.05,
        ("명단 소스 신선도 (클릭 → AML-WL-001)", ["소스", "신선도", "마지막 갱신"],
         [["Dow Jones", "최신", "06-06 03:00"],
          ["OFAC SDN", "지연 ⚠", "06-05 03:00"],
          ["UN 제재", "최신", "06-06 02:30"],
          ["KoFIU 제재", "최신", "06-06 02:00"]],
         [0.46, 0.24, 0.30]),
        ("규제 보고 / Travel Rule (클릭 → REP/TR)", ["항목", "건수"],
         [["STR 후보", "9"], ["CTR 데이터", "21"], ["제출 대기", "3"],
          ["TR 정보 누락", "4"], ["TR 위험 지갑", "2"], ["TR 예외 검토 대기", "1"]],
         [0.66, 0.34]))
    wf.info_panel(s, "AML-DASH-001", [
        "• 권한 자기 고객사 조회 (aml:case:read) · SaaS 운영자는 크로스 고객사",
        "• 상단 고객사 선택 ▼ · 서비스 선택 ▼ + 기간 필터",
        "• 카드 WLF·RA·TM·케이스 SLA·기한 임박 보고·결재 대기 (클릭 드릴다운)",
        "• 기한 임박 보고 — 법정 기한 SLA(STR 3영업일·CTR 30일) D-3 ⚠ → AML-REP-001",
        "• 결재 대기 카드 — 만료 임박 ⚠ · 클릭 → AML-APR-001",
        "• 규제 보고 STR·CTR·제출 대기 / Travel Rule 누락·위험 지갑·예외 대기",
        "• 운영 알림 명단 갱신·WLF 적체·보고 기한·결재 만료·재심사 (딥링크)",
        "• 명단 소스 신선도 / 최근 위험평가(모델 버전·신규 높음)",
        "• 집계 30~60초 캐시 · read-only · raw PII 미포함",
        "▸ API GET /api/v1/bo/aml/dashboard · /tenants/{id}/dashboard (bo-api)"])


# ═══ 2. 고객사 관리 (AML-TNT-001~004) ════════════════════════════
def tnt_001(p):
    """AML-TNT-001 고객사 목록"""
    s = frame(p, "AML-TNT-001", "AML Console > 고객사 관리",
              "고객사 관리 — 목록", search="고객사명 검색...", action="+ 새 고객사")
    y = wf.CON_TOP
    y = wf.filters(s, y, ["배포 유형 전체", "온보딩 상태 전체", "운영 상태 전체", "리전 전체"])
    y = wf.table_block(s, y, 1.85, "고객사 목록 [플랫폼 운영자] (SaaS 운영자 전용)",
        ["고객사 ID", "표시명", "배포 유형", "온보딩 상태", "리전", "상태"],
        [["tnnt-001", "은행 A", "매니지드 전용", "활성", "KR", "운영중 ▶"],
         ["tnnt-002", "핀테크 B", "자체 인프라 설치형", "고객배포완료", "KR", "운영중 ▶"],
         ["tnnt-003", "소규모 C", "소규모 공유", "활성", "KR", "운영중 ▶"]],
        [0.16, 0.18, 0.22, 0.20, 0.08, 0.16])
    wf.callout(s, y, "하단 배포 유형별 집계", [
        "총 3 고객사  /  매니지드 전용 2  ·  자체 인프라 설치형 1  ·  소규모 공유 1"])
    wf.info_panel(s, "AML-TNT-001", [
        "• 권한 SaaS 운영자 전용 (aml:admin:policy · bo-api 소유 엔드포인트)",
        "• 필터 배포 유형 / 온보딩 상태 / 운영 상태 / 리전 4축 + 고객사명 텍스트 (region= API §5 optional)",
        "• 배포 유형 매니지드 전용(MANAGED_DEDICATED) / 자체 인프라 설치형(SELF_HOSTED) / 소규모 공유(SHARED)",
        "• 온보딩 상태 신청/프로비저닝중/배포됨/검증됨/활성 · 패키지 발급/고객배포완료/등록 완료 (8종)",
        "• 상태 온보딩중(ONBOARDING)/운영중(ACTIVE)/정지(SUSPENDED)/해지완료(OFFBOARDED) — 운영 생명주기 4종(DB §5.28b)",
        "• 온보딩 진행 단계 상세 배지는 onboardingStatus 조건으로 렌더링 (status enum 별도)",
        "• 행 클릭 → AML-TNT-002 상세(4탭: 기본정보·배포온보딩·소스시스템·정책팩)  /  [+ 새 고객사] → AML-TNT-003 등록",
        "• 집계 footer 배포 유형별 건수 표시",
        "▸ API GET /api/v1/bo/aml/tenants?deploymentModel=&onboardingStatus=&status=&region= (bo-api · region optional)"])


# 고객사 상세(AML-TNT-002) 4탭 — 같은 부모 탭 바로 연속 전개(SKILL §1.6)
TNT_DETAIL_TABS = ["기본 정보", "배포·온보딩", "소스 시스템", "정책팩"]


def tnt_002_basic(p):
    """AML-TNT-002 고객사 상세 — ① 기본 정보"""
    s = frame(p, "AML-TNT-002", "AML Console > 고객사 관리 > 은행 A > 기본 정보",
              "고객사 상세 — ① 기본 정보 (은행 A)", search="고객사 내부 검색...")
    y = wf.CON_TOP
    y = wf.tab_chips(s, y, TNT_DETAIL_TABS, active=0)
    y = wf.two_panels(s, y, 1.70,
        ("[기본 정보]", ["항목", "값"],
         [["고객사 ID", "tnnt-001  (불변)"],
          ["표시명", "은행 A  [편집]"],
          ["리전", "KR"],
          ["운영 상태", "운영중 ACTIVE  [변경]"],
          ["생성일", "2026-01-12"]],
         [0.40, 0.60]),
        ("[요약 · 탭 바로가기]", ["항목", "값"],
         [["배포 유형", "매니지드 전용  (→ ② 배포·온보딩)"],
          ["온보딩 상태", "활성 ACTIVE"],
          ["소스 시스템", "3건 연결  (→ ③ 소스 시스템)"],
          ["정책팩", "한국 기본팩 KR_DEFAULT  (→ ④ 정책팩)"]],
         [0.40, 0.60]))
    y = wf.table_block(s, y, 1.30, "보고기관 정보 (KoFIU 보고 헤더 — v7.0 보강)  [편집]",
        ["항목", "값", "항목", "값"],
        [["보고기관 코드", "LR0160", "보고기관명", "은행 A 준법감시실"],
         ["보고 책임자", "김책임 (compliance.lead)", "담당자", "이담당 (02-1234-5678)"]],
        [0.18, 0.32, 0.14, 0.36])
    wf.callout(s, y, "보고기관 정보 = STR/CTR 보고 본문 헤더에 파생 결합", [
        "AML-REP-002 ① 보고 본문 헤더에 자동 결합 · 변경은 aml:admin:policy + 감사 기록"])
    wf.info_panel(s, "AML-TNT-002", [
        "• 권한 조회·변경 aml:admin:policy (bo-api 소유)",
        "• 같은 부모 탭 바: 기본 정보 / 배포·온보딩 / 소스 시스템 / 정책팩 (4탭 연속)",
        "• 변경 가능 displayName · status (policyPackCode 변경은 ④ 정책팩 탭 4-eyes)",
        "• 보고기관 정보(v7.0) 보고기관 코드·명·보고 책임자·담당자 — KoFIU 보고 헤더",
        "• 보고기관 정보는 AML-REP-002 ① 보고 본문 헤더에 파생 결합 (제안 API · 후속 정합)",
        "• 진입: AML-TNT-001 목록 → 행 클릭",
        "• 다음 → ② 배포·온보딩",
        "▸ API GET /PUT /api/v1/bo/aml/tenants/{tenantId} (bo-api)"])


def tnt_002_deploy(p):
    """AML-TNT-002 고객사 상세 — ② 배포·온보딩 (온보딩 상태·프로비저닝·이력 통합)"""
    s = frame(p, "AML-TNT-002", "AML Console > 고객사 관리 > 은행 A > 배포·온보딩",
              "고객사 상세 — ② 배포·온보딩 (은행 A)", search="고객사 내부 검색...")
    y = wf.CON_TOP
    y = wf.tab_chips(s, y, TNT_DETAIL_TABS, active=1)
    y = wf.kpi_cards(s, y, [
        ("배포 유형", "매니지드 전용", "MANAGED_DEDICATED", "blue"),
        ("온보딩 상태", "프로비저닝중", "PROVISIONING", "orange"),
        ("인프라 참조", "aml-tnnt-001-kr", "tf-stack (읽기 전용)", "green")])
    y = wf.two_panels(s, y, 1.40,
        ("온보딩 진행 상태 (이력)", ["상태", "시각", "작업자"],
         [["신청(REQUESTED)", "06-08 09:00", "admin"],
          ["프로비저닝중", "06-08 09:05", "시스템"],
          ["배포됨 (예정)", "—", "—"],
          ["검증됨·활성 (예정)", "—", "—"]],
         [0.42, 0.33, 0.25]),
        ("매니지드 전용 IaC 트리거", ["필드", "값"],
         [["IaC 템플릿", "[aml-dedicated-kr-v2 ▼]"],
          ["대상 리전", "[KR ▼]"],
          ["", "[IaC 프로비저닝 시작]"]],
         [0.40, 0.60]))
    wf.callout(s, y, "자체 인프라 설치형 — 고객 등록 콜백 (SELF_HOSTED 전용)", [
        "설치 인스턴스 ID  [______]   등록 토큰  [______]  ※ 보안 채널 전달",
        "콜백 엔드포인트   [______]        [설치형 등록 처리]"])
    wf.info_panel(s, "AML-TNT-002", [
        "• 배포 유형·온보딩 상태·인프라 참조 읽기 전용 (프로비저닝 산출)",
        "• 매니지드 전용 IaC → POST .../onboarding/provision → 202 (PROVISIONING)",
        "• 자체 인프라 설치형 등록 콜백 → POST .../onboarding/register",
        "• deploymentModel 직접 변경 → 409 AML.TENANT_DEPLOYMENT_MODEL_IMMUTABLE",
        "• 이전 ← ① 기본 정보  /  다음 → ③ 소스 시스템",
        "▸ API GET .../onboarding · POST .../provision · POST .../register (bo-api)"])


def tnt_002_source(p):
    """AML-TNT-002 고객사 상세 — ③ 소스 시스템"""
    s = frame(p, "AML-TNT-002", "AML Console > 고객사 관리 > 은행 A > 소스 시스템",
              "고객사 상세 — ③ 소스 시스템 (은행 A)", search="소스 시스템 검색...",
              action="인입 모니터링")
    y = wf.CON_TOP
    y = wf.tab_chips(s, y, TNT_DETAIL_TABS, active=2)
    y = wf.table_block(s, y, 1.75, "연결된 소스 시스템 [이 고객사] · [인입 모니터링 ▶ → AML-ING-001]",
        ["소스 ID", "종류", "연동 방식", "연결 상태", "마지막 수신", "신호", ""],
        [["src-core", "회원·계좌 (CORE)", "REST 전송", "정상", "8초 전", "●", "▶"],
         ["src-txn", "거래 (TRANSACTION)", "큐", "정상", "2초 전", "●", "▶"],
         ["src-kyc", "KYC 데이터 (KYC)", "폴링", "오류", "38분 전", "✕", "▶"]],
        [0.14, 0.24, 0.13, 0.13, 0.15, 0.09, 0.12])
    wf.callout(s, y, "소스 시스템 = 이 고객사의 데이터 인입 경로 (신호 표준 = PRD §1.11 확정)", [
        "회원·거래·KYC 피드를 정규 이벤트로 수집 → 스크리닝·RA·TM 입력",
        "신호 ● 수신중 / ⚠ 지연 / ✕ 중단 · 폴링 시점·큐 적체 상세 → [인입 모니터링 ▶ → AML-ING-001]",
        "명단 소스·임포트 이력은 AML-WL-001(명단 소스·임포트) 메뉴에서 관리"])
    wf.info_panel(s, "AML-TNT-002", [
        "• 권한 조회 aml:admin:policy (bo-api 소유)",
        "• 컬럼 소스 ID · 종류 · 연동 방식 · 연결 상태 · 마지막 수신 · 신호 · ▶",
        "• 연동 방식(v8.0) REST 전송/큐/폴링/변경수집/스냅샷/벤더브릿지 6종",
        "• 마지막 수신·신호(v8.0) §1.11 확정 — ● 수신중/⚠ 지연/✕ 중단",
        "• 종류 회원·계좌(CORE) / 거래(TRANSACTION) / KYC",
        "• [인입 모니터링 ▶ → AML-ING-001] 수신 API·폴링·큐·백필 상세",
        "• 이전 ← ② 배포·온보딩  /  다음 → ④ 정책팩",
        "▸ API GET /api/v1/bo/aml/tenants/{tenantId}/source-systems (bo-api)"])


def tnt_002_policy(p):
    """AML-TNT-002 고객사 상세 — ④ 정책팩"""
    s = frame(p, "AML-TNT-002", "AML Console > 고객사 관리 > 은행 A > 정책팩",
              "고객사 상세 — ④ 정책팩 (은행 A)", search="고객사 내부 검색...")
    y = wf.CON_TOP
    y = wf.tab_chips(s, y, TNT_DETAIL_TABS, active=3)
    y = wf.two_panels(s, y, 1.80,
        ("[기본 Policy Pack — 필수 baseline · 잠금]", ["항목", "값"],
         [["정책팩 코드", "한국 기본팩 (KR_DEFAULT)"],
          ["적용", "● 기본 적용 (필수·끄기 불가)"],
          ["버전", "v12 (effective 2026-05-01)"],
          ["CTR 기준금액", "1거래 1천만원↑ 현금거래 (4-eyes)"],
          ["RA 위험 임계", "0.75 (4-eyes 변경)"]],
         [0.44, 0.56]),
        ("[확장 Policy Pack — plugin · 토글 추가]", ["확장 축", "상태"],
         [["관할(jurisdiction)", "KR 단일"],
          ["국가 확장 plugin", "○ 없음  [▸추가]"],
          ["업권 확장 plugin", "○ 없음  [▸추가]"],
          ["추가 방식", "기본팩 위에 토글 + 4-eyes"]],
         [0.46, 0.54]))
    y = wf.table_block(s, y, 1.58, "기본팩(KR_DEFAULT) 구성 — 필수 baseline 일괄 적용(개별 영역 토글 아님 · 어떤 룰 기반인가)",
        ["영역", "기본 반영 기준"],
        [["CDD / 재심사", "고객확인·실소유자(UBO)·자금출처 · 등급별 재심사 주기"],
         ["STR / CTR", "의심거래 보고 / 1거래 1천만원↑ 현금거래 수집·검증"],
         ["Sanctions·PEP·RCA / VASP", "명단 필터링·정치인(PEP/RCA) 관리 / Travel Rule 100만원↑·지갑 risk"],
         ["RA 임계 / Privacy·Audit", "고위험 0.75↑ → EDD 트리거 / 최소수집·append-only 증적"]],
        [0.30, 0.70])
    wf.callout(s, y, "정책팩 = 기본 번들(잠금) + 확장 plugin(토글) · 변경은 4-eyes(POLICY_PACK)", [
        "KR_DEFAULT는 AML 최소 요건 일괄 적용 — 개별 영역(CDD·STR/CTR…) 토글 불가 · 파라미터(CTR·RA임계)는 버전 변경",
        "국가·업권 확장은 기본팩 위에 plugin 토글로 추가 → [변경 상신 → 4-eyes] → effective",
        "[기본팩 전체·확장·버전 이력 ▶ → AML-PP-001] · 이전 ← ③ 소스 시스템 (상세 4탭 끝)"])
    wf.info_panel(s, "AML-TNT-002", [
        "• 권한 조회 aml:admin:policy · 변경 4-eyes (POLICY_PACK)",
        "• 정책팩 = 기본 번들(KR_DEFAULT·필수·잠금) + 확장 plugin(국가·업권·토글 추가)",
        "• 기본팩 구성 CDD·STR/CTR·Sanctions/PEP·RCA/VASP·RA임계·Privacy/Audit — 일괄 적용(개별 토글 아님)",
        "• FDS와 차이 AML은 단일 baseline 번들 + 확장, FDS는 법령별 팩 개별 토글(서비스 규제 모델 차이)",
        "• 확장 plugin 국가(jurisdiction)·업권 확장을 기본팩 위에 토글 추가(현재 은행 A: KR 단일·확장 없음)",
        "• 파라미터(CTR 기준금액·RA 임계)는 effective 버전에 종속 — 4-eyes 변경",
        "• [기본팩 전체·확장·버전 이력 ▶ → AML-PP-001] 드릴다운(Policy Pack 관리 소관)",
        "• 이전 ← ③ 소스 시스템  (상세 4탭 끝)",
        "▸ API GET /api/v1/bo/aml/tenants/{tenantId} (policyPackCode 파생 표시) · POST /api/v1/admin/aml/policy-packs:change(2인)"])


def tnt_003(p):
    """AML-TNT-003 고객사 등록 (별도 생성 화면 — 상세 4탭과 분리)"""
    s = frame(p, "AML-TNT-003", "AML Console > 고객사 관리 > 새 고객사",
              "고객사 등록 (배포 유형 선택 + 온보딩 신청)", search="검색...")
    y = wf.CON_TOP
    y = wf.callout(s, y, "별도 생성 화면 — 목록 [+ 새 고객사]에서 진입 (상세 4탭 바와 분리)", [
        "배포 유형은 온보딩 신청 시점에 선택하며 등록 후 불변(격리는 프로비저닝 산출)",
        "매니지드 전용 → 등록 후 상세 ② 배포·온보딩에서 IaC 파이프라인 트리거",
        "자체 인프라 설치형 → 패키지 발급 후 고객이 직접 설치·등록"])
    y = wf.two_panels(s, y, 1.75,
        ("등록 기본 정보", ["필드", "입력"],
         [["고객사 ID *", "[__________] (불변)"],
          ["표시명 *", "[__________]"],
          ["기본 리전", "[KR ▼]  (선택, 기본값 KR)"],
          ["정책팩", "[한국 기본팩 ▼]"],
          ["온보딩 상태", "신청(REQUESTED) ← 자동"]],
         [0.35, 0.65]),
        ("배포 유형 선택 *", ["선택", "설명"],
         [["● 매니지드 전용", "플랫폼 클라우드 · 전용 DB · IaC 자동"],
          ["○ 자체 인프라 설치형", "고객 인프라 · Helm/Docker · 패키지 제공"],
          ["○ 소규모 공유", "공유 DB + 행 격리 · 즉시 활성"]],
         [0.35, 0.65]))
    wf.info_panel(s, "AML-TNT-003", [
        "• 권한 SaaS 운영자 전용 aml:admin:policy (bo-api 소유)",
        "• 격리 라디오 없음 — 배포 유형 드롭다운 3종만 (프로비저닝이 격리 산출)",
        "• 기본 리전 선택(기본값 KR) — 필수 아님(API §3.16 region required 미포함)",
        "• 소규모 공유 → 즉시 활성(ACTIVE)  매니지드/설치형 → 온보딩 흐름",
        "• 등록 성공 → AML-TNT-002(상세 ① 기본 정보)로 이동",
        "▸ API POST /api/v1/bo/aml/tenants → 201 + TenantDto (bo-api)"])


# ═══ 3. WLF 검토 큐 → 판정 상세 ═════════════════════════════════
def wlf_001(p):
    # ① 검토 필요 — 검토 큐 + 선택 후보 근거·점수분해(master-detail) + 판정 상신
    s = frame(p, "AML-WLF-001", "AML Console > WLF 검토 > ① 검토 필요",
              "WLF 검토 — ① 검토 필요 (요주의 명단 필터링)", search="대상 식별자 검색...",
              action="시뮬레이션")
    y = wf.CON_TOP
    y = wf.tab_chips(s, y, ["검토 필요", "상위승인", "처리 이력"], active=0)
    y = wf.filters(s, y, ["명단군 전체", "대상 유형 전체", "점수 전체", "기간 전체"])
    y = wf.table_block(s, y, 1.30, "검토 필요 큐 [고객사: 은행 A] · 행 ▶ → 하단 근거·점수 패널",
        ["스크리닝ID", "대상(식별자)", "대상유형", "명단군", "점수", "상태", ""],
        [["scr-9f3a", "cust_…123", "개인", "제재", "0.92", "검토필요", "▶"],
         ["scr-4a18", "cust_…340", "개인", "PEP관련자", "0.66", "검토필요", "▶"]],
        [0.19, 0.22, 0.10, 0.18, 0.10, 0.13, 0.08])
    y = wf.tab_chips(s, y, ["매칭 후보·근거", "점수 분해", "이전 판정 이력"], active=0)
    y = wf.two_panels(s, y, 1.5,
        ("선택 후보 근거 — scr-9f3a (매칭 명단·마스킹)", ["엔트리 / 항목", "값"],
         [["OFAC SDN (제재)", "제재명 유사·생년 일치"], ["UN 제재", "제재명 유사"],
          ["적용 룰버전", "WLF-KR v12"]],
         [0.45, 0.55]),
        ("점수 분해 (factor 기여)", ["factor", "기여"],
         [["이름 유사", "0.55"], ["생년월일", "0.20"], ["국가", "0.10"], ["문서", "0.07"]],
         [0.6, 0.4]))
    wf.callout(s, y, "① 검토 필요 시나리오 — 행 선택 → 근거·점수 확인 → 판정 [상신(2인)]", [
        "판정 드롭다운 [확정 매칭 ▼ / 오탐 / 자동 낮춤 / 상위승인 상신] 사유 입력 후 [상신(2인)] · 자기승인 차단",
        "상위승인 필요 건 → ② [상위 승인] 탭 4-eyes · 오탐 면제 [오탐 면제 등록(2인)] → FP_WHITELIST(만료 가능)",
        "상단 [시뮬레이션] 버튼 → AML-WLF-004 (단건 테스트·임의 수행)  /  하단 ③ [이전 판정 이력] 탭 → 과거 판정"])
    wf.info_panel(s, "AML-WLF-001", [
        "• 권한 조회 aml:case:read · 판정 상신 aml:case:update · 오탐 면제 aml:admin:watchlist",
        "• 탭 ①검토 필요 → ②상위 승인 → ③처리 이력 (업무 순서)",
        "• 상단 [시뮬레이션] 버튼 → AML-WLF-004 도구 화면 (QA #5 정합)",
        "• 하단 상세 탭: 매칭 후보·근거 / 점수 분해 / 이전 판정 이력 (master-detail 3탭)",
        "• 필터 명단군 / 대상 유형 / 점수 / 기간 4축 + 대상 식별자",
        "• 컬럼 스크리닝ID · 대상(식별자) · 대상유형 · 명단군 · 점수 · 상태 · ▶",
        "• 대상유형 개인/법인/상대방/지갑주소",
        "• 판정 드롭다운 확정 매칭/오탐/자동 낮춤/상위승인 상신 — 상위승인 포함",
        "• 판정 4-eyes(WLF_DECISION) 상신→승인(maker≠checker)",
        "• 매칭 임계값(0.66/0.92)·룰버전은 정책팩 파라미터 — 정책팩 4-eyes(POLICY_PACK) 변경 · 본 화면 읽기 전용",
        "• 점수·대상 마스킹 · 원문 aml:pii:reveal+사유+감사",
        "• 다음 → ② 상위 승인 탭 (상신 건 4-eyes 승인)",
        "▸ API GET .../screenings?status=POSSIBLE_MATCH · POST .../screenings/{id}/decision(2인)"])


def wlf_002(p):
    # ② 상위 승인 — 검토 필요에서 상신된 ESCALATED 건의 4-eyes 승인
    s = frame(p, "AML-WLF-002", "AML Console > WLF 검토 > ② 상위 승인",
              "WLF 검토 — ② 상위 승인 (4-eyes · 검토 필요에서 상신)", search="대상 식별자 검색...")
    y = wf.CON_TOP
    y = wf.tab_chips(s, y, ["검토 필요", "상위승인", "처리 이력"], active=1)
    y = wf.filters(s, y, ["명단군 전체", "상신자 전체", "기간 전체"])
    y = wf.table_block(s, y, 1.45, "상위 승인 대상 (① 검토 필요에서 상신 · ESCALATED)",
        ["스크리닝ID", "대상(식별자)", "명단군", "상신 판정", "상신자", "상신일", "동작"],
        [["scr-5b22", "cust_…908 (개인)", "정치인(PEP)", "확정 상신", "analyst.a", "06-08", "[심사]"],
         ["scr-7c01", "ent_…777 (법인)", "부정뉴스", "오탐 상신", "analyst.b", "06-07", "[심사]"]],
        [0.15, 0.22, 0.16, 0.14, 0.13, 0.10, 0.10])
    y = wf.two_panels(s, y, 1.35,
        ("상신 근거 — scr-5b22", ["항목", "값"],
         [["상신 판정", "확정 매칭(SANCTIONS/PEP)"], ["근거", "PEP 명단 일치·점수 0.88"],
          ["이전 판정 이력", "2회 검토필요(자동낮춤)"]],
         [0.40, 0.60]),
        ("상위 승인 결과 (= 4-eyes)", ["동작", "결과"],
         [["[승인](2인)", "확정 → 케이스 자동 생성"], ["[반려](사유)", "① 검토 필요로 회신"]],
         [0.42, 0.58]))
    wf.callout(s, y, "② 상위 승인 시나리오 (4-eyes · maker≠checker)", [
        "[승인(2인)] → 확정 매칭 → 케이스 자동 생성(제재/PEP 검토) → AML-CASE-002 + AML→FDS 전파(BE)",
        "[반려(사유)] → ① 검토 필요로 회신(재검토) · 결재 후 payload 변경 시 무효(APPROVAL_PAYLOAD_CHANGED)",
        "처리 결과(확정/오탐)는 다음 ③ [처리 이력] 탭에 적재"])
    wf.info_panel(s, "AML-WLF-002", [
        "• 권한 조회 aml:case:read · 승인·반려 aml:admin:approval (checker · maker≠checker)",
        "• 탭 ②상위 승인 (①에서 상신된 ESCALATED 건)",
        "• 대상 상신자·상신 판정·이전 판정 이력 표시",
        "• [승인] → 확정·케이스 생성(AML-CASE-002) / [반려] → 검토 필요 회신",
        "• 자기승인 차단 · payload_hash 고정",
        "• 이전 ← ① 검토 필요 / 다음 → ③ 처리 이력",
        "▸ API GET .../screenings?status=ESCALATED · POST .../approvals/{id}:approve(2인) · :reject"])


def wlf_003(p):
    # ③ 처리 이력 — 확정/오탐/면제/자동낮춤 결과 + 통계·증적
    s = frame(p, "AML-WLF-003", "AML Console > WLF 검토 > ③ 처리 이력",
              "WLF 검토 — ③ 처리 이력 (확정·오탐·면제·자동낮춤)", search="대상 식별자 검색...")
    y = wf.CON_TOP
    y = wf.tab_chips(s, y, ["검토 필요", "상위승인", "처리 이력"], active=2)
    y = wf.kpi_cards(s, y, [
        ("확정 매칭", "12 건", "케이스 생성 12", "red"),
        ("오탐", "48 건", "재검토 완료", "green"),
        ("자동 낮춤", "126 건", "재스크리닝 대상", "blue"),
        ("면제(FP_WHITELIST)", "9 건", "만료 후 재스크리닝", "orange"),
        ("평균 처리 SLA", "2.3 일", "처리 완료 기준", "green")])
    y = wf.filters(s, y, ["판정 전체", "명단군 전체", "기간 최근 30일"])
    y = wf.table_block(s, y, 1.85, "처리 이력 (4-eyes 증적 · 감사 연결)",
        ["스크리닝ID", "대상(식별자)", "명단군", "최종 판정", "판정자/승인자", "일시"],
        [["scr-5b22", "cust_…908", "정치인", "확정 매칭", "analyst.a/comp.b", "06-07 14:20"],
         ["scr-7c01", "ent_…777", "부정뉴스", "오탐", "analyst.b/comp.b", "06-07 11:05"],
         ["scr-1d40", "cust_…512", "제재", "오탐 면제", "analyst.c/comp.a", "06-06 09:40"]],
        [0.16, 0.18, 0.16, 0.16, 0.20, 0.14])
    wf.callout(s, y, "면제(FP_WHITELIST) 카드 [면제 현황 ▶ → AML-WL-003 ②] (v7.0)", [
        "면제 생명주기(활성/만료/해제) 관리·만료 임박 배지 → AML-WL-003 ② 오탐 면제 관리"])
    wf.info_panel(s, "AML-WLF-003", [
        "• 권한 조회 aml:case:read",
        "• 탭 ③처리 이력 (확정/오탐/면제/자동낮춤 결과)",
        "• 요약 카드 확정·오탐·면제(FP_WHITELIST)·자동낮춤 건수 / 평균 처리 SLA(일)",
        "• 컬럼 스크리닝ID·대상·명단군·최종 판정·판정자/승인자·일시",
        "• 모든 판정 4-eyes 증적·감사 로그(AML-AUD-001) 연결",
        "• 오탐 면제는 FP_WHITELIST 만료 후 재스크리닝 순환 → ① 검토 필요",
        "• 면제 카드 [면제 현황 ▶ → AML-WL-003 ②] 생명주기 관리 (v7.0)",
        "• 이전 ← ② 상위 승인",
        "▸ API GET .../screenings?status=TRUE_MATCH,FALSE_POSITIVE,AUTO_DISCOUNTED&from&to"])


# ─── AML-WLF-004 스크리닝 시뮬레이션·임의 수행 (v6.0 벤치마크 보강, 2탭) ───
WLF_004_TABS = ["단건 시뮬레이션", "임의 수행(일괄)"]


def wlf_004(p, tab=0):
    titles = ["스크리닝 시뮬레이션·임의 수행 — ① 단건 시뮬레이션",
              "스크리닝 시뮬레이션·임의 수행 — ② 임의 수행(일괄)"]
    crumbs = ["AML Console > WLF 검토 > 시뮬레이션 > 단건 시뮬레이션",
              "AML Console > WLF 검토 > 시뮬레이션 > 임의 수행(일괄)"]
    s = frame(p, "AML-WLF-004", crumbs[tab], titles[tab], search="대상 검색...")
    y = wf.CON_TOP
    y = wf.entry_banner(s, y, "AML-WLF-001 / AML-WL-001 ① 소스 목록에서 [시뮬레이션] 버튼 클릭 → 도구 화면(NAV 비항목)")
    y = wf.tab_chips(s, y, WLF_004_TABS, active=tab)
    if tab == 0:
        y = wf.form_block(s, y, 1.70, "대상 정보 입력 (분석 전용 · 스크리닝 결과 미생성 · 결재 불필요)",
            [("이름 *", "홍길동  [한글→영문 변환]  HONG GILDONG", "input"),
             ("개인/법인 · 국가 · 생년월일", "개인 ▼ · KR ▼ · 1981-05-12", "input"),
             ("유사도 임계(%)", "92 (기본=정책팩 WLF 임계)", "input")])
        y = wf.table_block(s, y, 1.70, "매칭 후보 (즉시 조회 · raw PII 미노출)",
            ["명단군", "엔트리(토큰)", "적중률(%)", "매칭 근거 분해"],
            [["제재", "wl_…7f2", "96.4", "성명 0.97 · 생년 1.0 · 국가 1.0"],
             ["정치인(PEP)", "wl_…a10", "88.1", "성명 0.91 · 음역 변형"],
             ["부정뉴스", "wl_…c55", "74.0", "성명 0.74 (임계 미만 참고)"]],
            [0.18, 0.20, 0.16, 0.46])
        wf.callout(s, y, "① 단건 시뮬레이션 — [매칭 시뮬레이션 실행] · 룰·임계값 튜닝 검증 도구", [
            "임계 조정값은 화면 일시 값 — 정책 반영은 정책팩 파라미터 4-eyes(AML-PP-001) 경유",
            "다음 → ② 임의 수행(일괄) 탭"])
        wf.info_panel(s, "AML-WLF-004", [
            "• 권한 aml:admin:watchlist (시뮬레이션=읽기 전용)",
            "• 진입 AML-WLF-001 / AML-WL-001 [시뮬레이션] 버튼 (도구 화면)",
            "• 탭 ① 단건 시뮬레이션 / ② 임의 수행(일괄)",
            "• 입력 이름(한글→영문 음역 변환)·개인/법인·국가·생년월일",
            "• 유사도 임계(%) 화면 일시 조정 — 기본=정책팩 WLF 임계",
            "• 결과 명단군·엔트리(토큰)·적중률·매칭 근거 분해",
            "• 분석 전용 — 스크리닝 결과 미생성·결재 불필요",
            "• 다음 → ② 임의 수행(일괄)",
            "▸ API POST .../screenings:simulate (제안 · 후속 API 정합)"])
    else:  # tab == 1
        y = wf.callout(s, y, "② 임의 수행 — 정규 배치와 별개의 수시(ad-hoc) 일괄 스크리닝", [
            "[템플릿 다운로드] → 파일 업로드 → [일괄 스크리닝 수행]  ·  수행 자체 감사 기록 · 대량 수행 rate limit",
            "검출 건은 정규 흐름과 동일 POSSIBLE_MATCH 생성 → AML-WLF-001 ① 검토 필요 큐 유입",
            "업로드 대상 정보는 처리 후 원문 미보존(즉시 토큰화 · D-05)"])
        y = wf.table_block(s, y, 2.05, "임의 수행 이력 (감사 기록)",
            ["수행ID", "수행일시", "수행자", "대상 건수", "검출", "유사도(%)", "상태"],
            [["run-072", "06-12 09:30", "analyst.a", "1,250", "7 ▶", "92", "완료"],
             ["run-071", "06-10 16:05", "analyst.c", "40", "1 ▶", "92", "완료"],
             ["run-070", "06-09 11:20", "analyst.a", "3,800", "12 ▶", "90", "완료"]],
            [0.12, 0.18, 0.14, 0.16, 0.10, 0.14, 0.16])
        wf.callout(s, y, "검출 ▶ 클릭 → AML-WLF-001 ① 검토 필요 (해당 수행 건 필터)", [
            "이전 ← ① 단건 시뮬레이션  (시뮬레이션 2탭 끝)"])
        wf.info_panel(s, "AML-WLF-004", [
            "• 권한 aml:admin:watchlist (임의 수행=감사 기록)",
            "• 탭 ② 임의 수행(일괄)",
            "• 흐름 템플릿 다운로드 → 파일 업로드 → 일괄 스크리닝 수행",
            "• 컬럼 수행ID·수행일시·수행자·대상 건수·검출·유사도·상태",
            "• 검출 건 → POSSIBLE_MATCH 생성 → AML-WLF-001 ① 큐 유입",
            "• 업로드 원문 미보존(즉시 토큰화 · D-05) · rate limit(429)",
            "• 이전 ← ① 단건 시뮬레이션  (시뮬레이션 2탭 끝)",
            "▸ API POST .../screenings:bulk-run (제안 · 후속 API 정합)"])


# ═══ 3. 명단 소스·임포트 → 변경분 상세 ══════════════════════════
WL_001_TABS = ["소스 목록", "임포트 이력", "명단 엔트리 조회"]


def wl_001(p, tab=0):
    titles = ["명단 소스 / 임포트 이력 — ① 소스 목록",
              "명단 소스 / 임포트 이력 — ② 임포트 이력",
              "명단 소스 / 임포트 이력 — ③ 명단 엔트리 조회"]
    crumbs = ["AML Console > 명단 소스·임포트 > 소스 목록",
              "AML Console > 명단 소스·임포트 > 임포트 이력",
              "AML Console > 명단 소스·임포트 > 명단 엔트리 조회"]
    s = frame(p, "AML-WL-001", crumbs[tab], titles[tab],
              search="소스명 검색...", action="+ 새 소스" if tab == 0 else None)
    y = wf.CON_TOP
    y = wf.tab_chips(s, y, WL_001_TABS, active=tab)
    if tab == 0:
        y = wf.filters(s, y, ["명단 종류 전체", "상태 전체"])
        y = wf.table_block(s, y, 2.30, "명단 소스 [고객사: 은행 A] · [시뮬레이션 → AML-WLF-004]",
            ["소스 코드", "제공자", "명단 종류", "활성 버전", "마지막 갱신", "상태"],
            [["OFAC_SDN", "美 재무부", "제재", "v141", "06-05 03:00", "지연 ⚠"],
             ["UN_CONSOL", "UN", "제재", "v88", "06-06 02:30", "운영"],
             ["DOWJONES_WL", "Dow Jones", "정치인·제재", "v512", "06-06 03:00", "운영"],
             ["INTERNAL_BL", "자체", "내부블랙", "v23", "06-06 09:00", "운영"]],
            [0.20, 0.16, 0.22, 0.14, 0.18, 0.10])
        wf.callout(s, y, "① 소스 목록 — 소스 코드 immutable · 공통(플랫폼) 소스는 SaaS 운영자 정의", [
            "행 클릭(또는 소스 선택) → [임포트 업로드(diff 생성)]으로 임포트 이력 탭으로 이동",
            "[시뮬레이션] 버튼 → AML-WLF-004 (단건 매칭 사전 테스트·임의 수행 도구)",
            "다음 → ② 임포트 이력 탭에서 OFAC_SDN 등 변경분 확인·적용"])
        wf.info_panel(s, "AML-WL-001", [
            "• 권한 조회·임포트 적용 aml:admin:watchlist",
            "• 탭 ① 소스 목록 / ② 임포트 이력 / ③ 명단 엔트리 조회",
            "• [시뮬레이션] 버튼 → AML-WLF-004 도구 화면 (QA #5 정합)",
            "• 필터 명단 종류 / 상태 + 소스명 텍스트",
            "• 컬럼 소스 코드·제공자·명단 종류·활성 버전·마지막 갱신·상태",
            "• 명단 종류 제재/정치인/PEP관련자/부정뉴스/내부블랙/수사기관/가상자산위험",
            "• 상태 운영/비활성 + 신선도(최신/지연)",
            "• 소스 코드 immutable · 등록·임포트·적용·반려·롤백 감사 보존",
            "• 다음 → ② 임포트 이력",
            "▸ API GET/POST .../watchlist-sources"])
    elif tab == 1:
        y = wf.filters(s, y, ["소스 전체", "상태 전체", "기간 최근 30일"])
        y = wf.table_block(s, y, 2.20, "임포트 이력 — OFAC_SDN · [임포트 업로드(diff 생성)]",
            ["버전", "수신 시각", "수신 건수", "신규/변경/삭제", "검증", "상태"],
            [["v142", "06-06 03:00", "12,043", "+18 / 6 / 2", "통과", "검토대기 ▶"],
             ["v141", "06-05 03:00", "12,027", "+9 / 3 / 0", "통과", "적용완료"],
             ["v140", "06-04 03:00", "12,018", "+5 / 2 / 1", "통과", "적용완료"]],
            [0.10, 0.20, 0.16, 0.24, 0.12, 0.18])
        wf.callout(s, y, "② 임포트 이력 — 변경분(검토대기) 클릭 → AML-WL-002 (diff 상세·4-eyes 적용)", [
            "임포트 직전 활성 버전 대비 변경분(diff) 산출·DRAFT 보관",
            "검토대기 v142 클릭 → AML-WL-002 변경분 상세",
            "이전 ← ① 소스 목록  /  다음 → ③ 명단 엔트리 조회"])
        wf.info_panel(s, "AML-WL-001", [
            "• 권한 임포트 적용 aml:admin:watchlist",
            "• 탭 ② 임포트 이력 (소스별 임포트 버전·변경분)",
            "• 필터 소스 / 상태 / 기간",
            "• 컬럼 버전·수신 시각·수신 건수·신규/변경/삭제·검증·상태",
            "• 상태 검토대기 / 적용완료 / 반려 / 롤백대기",
            "• 흐름 변경분(검토대기) 클릭 → AML-WL-002",
            "• 이전 ← ① 소스 목록  /  다음 → ③ 명단 엔트리 조회",
            "▸ API GET .../watchlist-sources/{code}/imports · POST (diff 생성)"])
    else:  # tab == 2
        y = wf.filters(s, y, ["소스 전체", "명단 종류 전체", "상태 전체"])
        y = wf.table_block(s, y, 2.30, "명단 엔트리 조회 (마스킹 · 소스·정규화 토큰 기준)",
            ["엔트리ID", "소스 코드", "명단 종류", "정규화 토큰(hash)", "상태"],
            [["entry_…C9", "OFAC_SDN", "제재", "tok_…a1b2", "활성"],
             ["entry_…D3", "OFAC_SDN", "제재", "tok_…c4d5", "활성"],
             ["entry_…P5", "DOWJONES_WL", "정치인", "tok_…e8f1", "활성"],
             ["entry_…X2", "OFAC_SDN", "제재", "tok_…g8h9", "삭제(제재해제)"]],
            [0.18, 0.18, 0.18, 0.32, 0.14])
        wf.callout(s, y, "③ 명단 엔트리 조회 — 마스킹 엔트리 기반 조회 (원문 PII 미노출)", [
            "정규화 토큰(hash)으로 조회 · 원문 열람은 aml:pii:reveal + 사유 + 감사 로그",
            "이전 ← ② 임포트 이력  (명단 소스 3탭 끝)"])
        wf.info_panel(s, "AML-WL-001", [
            "• 권한 조회 aml:admin:watchlist / 원문 열람 aml:pii:reveal(감사)",
            "• 탭 ③ 명단 엔트리 조회 (마스킹 엔트리)",
            "• 필터 소스 / 명단 종류 / 상태",
            "• 컬럼 엔트리ID · 소스 코드 · 명단 종류 · 정규화 토큰(hash) · 상태",
            "• 정규화 토큰 hash는 실제 이름·문서번호 해시값 (원문 미노출)",
            "• 상태 활성/삭제(제재해제)/비활성",
            "• 이전 ← ② 임포트 이력  (명단 소스 3탭 끝)",
            "▸ API GET .../watchlist-entries?sourceCode=&listType=&status="])


def wl_002(p):
    s = frame(p, "AML-WL-002", "AML Console > 명단 소스 > 변경분 상세",
              "명단 변경분 상세 / 디프 승인 — OFAC_SDN v142 (4-eyes)",
              search="엔트리 검색...")
    y = wf.CON_TOP
    y = wf.entry_banner(s, y, "AML-WL-001 ② 임포트 이력에서 [변경분(검토대기) ▶] 클릭 → 디프 상세·4-eyes 적용")
    y = wf.two_panels(s, y, 1.35,
        ("변경분 요약 (v141 → v142)", ["항목", "값"],
         [["수신 건수", "12,043"], ["신규(추가)", "+18"],
          ["변경(수정)", "6"], ["삭제", "2"], ["검증", "통과(서명·checksum)"]],
         [0.46, 0.54]),
        ("검증 게이트", ["항목", "값"],
         [["건수·포맷", "통과"], ["중복", "0"],
          ["급증 임계", "통과(배수 미초과)"], ["서명/checksum", "통과"]],
         [0.50, 0.50]))
    y = wf.table_block(s, y, 1.85, "변경 엔트리 디프 (추가/삭제, 마스킹)",
        ["구분", "엔트리ID", "명단 종류", "정규화 토큰(hash)", "근거"],
        [["+ 추가", "entry_…C9", "제재", "tok_…a1b2", "OFAC SDN 신규 지정"],
         ["+ 추가", "entry_…D3", "제재", "tok_…c4d5", "신규 지정"],
         ["~ 변경", "entry_…A1", "제재", "tok_…e6f7", "별칭(alias) 추가"],
         ["- 삭제", "entry_…X2", "제재", "tok_…g8h9", "제재 해제(delisting)"]],
        [0.12, 0.18, 0.16, 0.30, 0.24])
    wf.callout(s, y, "적용 시나리오 (4-eyes · subjectType=WATCHLIST_IMPORT)", [
        "[변경분 적용 상신(2인)] → 승인(maker≠checker) → 활성 버전 v142 승격(EXECUTED)",
        "승인 후에만 명단 반영 + 영향 대상 재스크리닝 트리거(BE) · [반려](사유)",
        "급증·서명/checksum 실패는 검증=경고/실패 → 반영 보류 · 적용 후 롤백도 결재·감사"])
    wf.info_panel(s, "AML-WL-002", [
        "• 권한 임포트 적용 aml:admin:watchlist (2인)",
        "• 진입 AML-WL-001 변경분(검토대기) 클릭",
        "• 변경분 요약 수신·신규/변경/삭제 건수 + 검증 게이트 결과",
        "• 디프 목록 추가/변경/삭제 엔트리(정규화 토큰 hash·마스킹)·근거",
        "• 적용 4-eyes(WATCHLIST_IMPORT) 상신→승인→활성 버전 승격",
        "• 승인 후 명단 반영 + 영향 대상 재스크리닝(BE) · 멱등(중복 1건만)",
        "• 검증 경고/실패(급증·서명·checksum)는 반영 보류",
        "• 적용·반려·롤백 이력 감사 보존(aml_audit_events)",
        "▸ API POST .../watchlist-sources/{code}/imports/{ver}:apply(2인) · GET .../watchlist-entries"])


# ─── AML-WL-003 내부 요주의 명단·오탐 면제 생명주기 (v7.0 벤치마크 2차, 2탭) ───
WL_003_TABS = ["내부 요주의 명단 등록·관리", "오탐 면제(White List) 관리"]


def wl_003(p, tab=0):
    titles = ["내부 요주의 명단·오탐 면제 — ① 내부 요주의 명단 등록·관리",
              "내부 요주의 명단·오탐 면제 — ② 오탐 면제(White List) 관리"]
    crumbs = ["AML Console > 명단 소스·임포트 > 내부 요주의 명단",
              "AML Console > 명단 소스·임포트 > 오탐 면제 관리"]
    s = frame(p, "AML-WL-003", crumbs[tab], titles[tab], search="대상·엔트리 검색...",
              action="+ 수기 등록" if tab == 0 else None)
    y = wf.CON_TOP
    y = wf.tab_chips(s, y, WL_003_TABS, active=tab)
    if tab == 0:
        y = wf.form_block(s, y, 1.85, "내부 요주의 명단 수기 등록 (자체 블랙리스트 · INTERNAL_BL 소스)",
            [("개인/법인 *", "● 개인   ○ 법인", "radio"),
             ("국문명 · 영문명 *", "홍길동 · HONG GILDONG  (저장 시 정규화 토큰화)", "input"),
             ("생년월일·국적 / 등록 사유 *·적용 시작일", "1981-05-12 · KR  /  수사기관 요청 · 2026-06-15", "input")])
        y = wf.table_block(s, y, 1.45, "내부 명단 등록 건 (diff 초안 → AML-WL-002 4-eyes 적용)",
            ["엔트리(토큰)", "등록 사유", "적용 시작일", "결재 상태", "사용 여부"],
            [["tok_…i2b1", "수사기관 요청", "2026-06-15", "검토대기 ▶", "—"],
             ["tok_…i1a9", "내부 적발(직권)", "2026-05-02", "적용완료", "사용"],
             ["tok_…i0f3", "거래 거절 이력", "2026-03-20", "적용완료", "사용"]],
            [0.20, 0.24, 0.18, 0.20, 0.18])
        wf.callout(s, y, "① 내부 명단 — [등록 상신] = diff 초안 생성 (즉시 반영 아님)", [
            "기존 명단 임포트 흐름 재사용 — 검토대기 ▶ → AML-WL-002 디프 승인(WATCHLIST_IMPORT 2인)",
            "적용 시작일(발효일) 도래 시점부터 스크리닝 매칭 대상 · 다음 → ② 오탐 면제 관리"])
        wf.info_panel(s, "AML-WL-003", [
            "• 권한 aml:admin:watchlist (등록·해제 2인)",
            "• 탭 ① 내부 요주의 명단 / ② 오탐 면제(White List)",
            "• 수기 등록 개인/법인·국문/영문명·생년월일·국적·등록 사유(필수)·적용 시작일",
            "• 등록 = diff 초안 → AML-WL-002 4-eyes 적용 재사용(별도 결재 종류 없음)",
            "• 컬럼 엔트리(토큰)·등록 사유·적용 시작일·결재 상태·사용 여부",
            "• PII 정규화 토큰(hash) 표시 — 원문 미보존(D-05)",
            "• 전 이력 감사 보존(aml_audit_events)",
            "• 다음 → ② 오탐 면제 관리",
            "▸ API POST .../watchlist-sources/{code}/entries:draft (제안 · 후속 API 정합)"])
    else:
        y = wf.kpi_cards(s, y, [
            ("활성 면제", "9 건", "FP_WHITELIST 유효", "blue"),
            ("만료 임박(D-7)", "2 건", "만료 후 재스크리닝 ⚠", "orange"),
            ("만료", "3 건", "최근 30일", "green"),
            ("해제", "1 건", "수동 해제(2인)", "red")])
        y = wf.filters(s, y, ["상태 전체", "명단군 전체", "기간 최근 90일"])
        y = wf.table_block(s, y, 1.70, "오탐 면제 목록 — 생명주기(활성/만료/해제) [면제 해제(2인)]",
            ["면제ID", "대상(식별자)", "매칭 엔트리", "등록 사유", "등록일", "만료일", "상태"],
            [["fpw-031", "cust_…512", "tok_…a1b2 (제재)", "동명이인 확인", "05-12", "08-12", "활성"],
             ["fpw-029", "ent_…777", "tok_…c4d5 (부정뉴스)", "기사 오보 확인", "04-02", "06-18 ⚠", "활성"],
             ["fpw-022", "cust_…208", "tok_…e8f1 (정치인)", "동명이인 확인", "03-01", "06-01", "만료"]],
            [0.10, 0.15, 0.20, 0.18, 0.10, 0.13, 0.14])
        wf.callout(s, y, "② 오탐 면제 생명주기 — 등록(WLF-001 4-eyes)→활성→만료(자동)→해제(수동 2인)", [
            "만료·해제 시 해당 대상 재스크리닝 트리거 → 검출 시 AML-WLF-001 ① 검토 필요 큐 순환",
            "진입 AML-WLF-003 면제 카드 [면제 현황 ▶]에서도 가능 · 이전 ← ① 내부 요주의 명단 (2탭 끝)"])
        wf.info_panel(s, "AML-WL-003", [
            "• 권한 aml:admin:watchlist (해제 2인)",
            "• 탭 ② 오탐 면제(White List) 관리",
            "• 카드 활성·만료 임박(D-7 ⚠)·만료·해제",
            "• 컬럼 면제ID·대상·매칭 엔트리·등록 사유·등록일·만료일·상태",
            "• 등록은 AML-WLF-001 FP_WHITELIST 4-eyes(기존) — 본 화면은 생명주기 관리",
            "• 만료(자동)·해제(수동 2인) 시 재스크리닝 → AML-WLF-001 ① 순환",
            "• 등록/만료/해제 전 이력 감사 보존",
            "• 이전 ← ① 내부 요주의 명단 (2탭 끝)",
            "▸ API GET .../screenings/fp-whitelist · POST .../fp-whitelist/{id}:revoke(2인) (제안)"])


# ═══ 4. 국가위험(고위험 국가) 관리 ══════════════════════════════
CTRY_001_TABS = ["국가위험 등급표", "변경 상신·이력"]


def ctry_001(p, tab=0):
    titles = ["국가위험 등급 관리 — ① 국가위험 등급표",
              "국가위험 등급 관리 — ② 변경 상신·이력"]
    crumbs = ["AML Console > 국가위험 관리 > 국가위험 등급표",
              "AML Console > 국가위험 관리 > 변경 상신·이력"]
    s = frame(p, "AML-CTRY-001", crumbs[tab], titles[tab],
              search="국가 검색...", action="+ 변경 상신" if tab == 0 else None)
    y = wf.CON_TOP
    y = wf.tab_chips(s, y, CTRY_001_TABS, active=tab)
    if tab == 0:
        y = wf.filters(s, y, ["위험 등급 전체", "근거 소스 전체"])
        y = wf.table_block(s, y, 2.55, "국가위험 등급표 (정책 store · effective v7) — 근거 소스 분해(벤치마크 보강)",
            ["국가", "위험 등급", "근거 소스 (FATF·제재·CPI 분해)", "버전", "적용 시점"],
            [["IR (이란)", "거래금지", "FATF 고위험 · UN/OFAC/EU 제재", "v7", "2026-03-01"],
             ["KP (북한)", "거래금지", "FATF 고위험 · UN/OFAC 제재", "v7", "2026-03-01"],
             ["MM (미얀마)", "높음", "FATF 이행취약 · CPI 하위", "v7", "2026-03-01"],
             ["PH (필리핀)", "중간", "고위험 corridor", "v7", "2026-03-01"],
             ["KR (한국)", "낮음", "기본", "v7", "2026-03-01"]],
            [0.22, 0.14, 0.34, 0.10, 0.20])
        wf.callout(s, y, "① 등급표 — RA factor '고위험 국가'의 앞단 관리", [
            "근거 소스 = 정책팩 KR_DEFAULT 산정 근거 파생 표시 (FATF 고위험/이행취약·UN/OFAC/EU 제재·부패인식지수)",
            "정책 store(versioned) · 물리 마스터 테이블 미보유(설계서 §2.6)",
            "다음 → ② 변경 상신·이력 탭에서 4-eyes 변경 상신"])
        wf.info_panel(s, "AML-CTRY-001", [
            "• 권한 조회·변경 상신 aml:admin:policy (변경=2인)",
            "• 탭 ① 국가위험 등급표 / ② 변경 상신·이력",
            "• 필터 위험 등급 / 근거 소스 + 국가 텍스트",
            "• 컬럼 국가(ISO) · 위험 등급 · 근거 소스 · 버전 · 적용 시점",
            "• 위험 등급 낮음/중간/높음/거래금지 (RA 등급과 동일 축)",
            "• 근거 소스 FATF 고위험/이행취약·UN/OFAC/EU 제재·부패인식지수(CPI) — 정책팩 산정 근거 파생 표시(외부 지표 자동 갱신=후속 오픈결정)",
            "• 다음 → ② 변경 상신·이력",
            "▸ API GET .../country-risk"])
    else:  # tab == 1
        y = wf.callout(s, y, "② 변경 시나리오 (4-eyes · subjectType=COUNTRY_RISK)", [
            "변경 [국가 추가/등급 조정 ▼]  예: MM 높음 → 거래금지   근거 [FATF 업데이트 ▼]  사유 [______]",
            "[국가위험 변경 상신(2인)] → 승인(maker≠checker) → 정책 store 반영(EXECUTED)",
            "실행 후 변경 국가 관련 대상 재평가(RA) 트리거 · RA factor '고위험 국가 거주'에 반영(→ AML-RA-002)"])
        y = wf.table_block(s, y, 2.10, "변경 상신 이력 (4-eyes 증적)",
            ["결재ID", "변경 내용", "상신자", "상태", "처리일"],
            [["apr-541", "MM 높음 → 거래금지 (FATF 업데이트)", "이감리", "승인", "2026-03-01"],
             ["apr-520", "PH 낮음 → 중간 (고위험 corridor)", "이감리", "승인", "2026-01-15"],
             ["apr-490", "RU 중간 → 높음 (제재 강화)", "이감리", "반려", "2025-12-20"]],
            [0.12, 0.38, 0.14, 0.14, 0.22])
        wf.info_panel(s, "AML-CTRY-001", [
            "• 권한 변경 상신 aml:admin:policy (2인)",
            "• 탭 ② 변경 상신·이력",
            "• 변경 상신 국가 추가/등급 조정 + 근거(FATF/제재/corridor) + 사유",
            "• 변경 4-eyes(COUNTRY_RISK) 상신→승인→정책 store(versioned) 반영",
            "• 실행 후 변경 국가 관련 대상 RA 재평가 트리거",
            "• 이력 컬럼 결재ID · 변경 내용 · 상신자 · 상태 · 처리일",
            "• 모든 변경 상신·승인·적용 감사 보존",
            "• 이전 ← ① 국가위험 등급표  (국가위험 2탭 끝)",
            "▸ API POST .../country-risk:change(2인 · COUNTRY_RISK) · GET (이력)"])


# ═══ 5. RA 분포·고위험 → RA 대상 상세 / EDD 착수 ════════════════
RA_001_TABS = ["점수 분포", "고위험 목록"]


def ra_001(p, tab=0):
    titles = ["RA 점수 분포 / 고위험 현황 — ① 점수 분포",
              "RA 점수 분포 / 고위험 현황 — ② 고위험 목록"]
    crumbs = ["AML Console > RA·CDD > RA 분포 · 고위험 현황 > 점수 분포",
              "AML Console > RA·CDD > RA 분포 · 고위험 현황 > 고위험 목록"]
    s = frame(p, "AML-RA-001", crumbs[tab], titles[tab], search="대상 식별자 검색...")
    y = wf.CON_TOP
    y = wf.tab_chips(s, y, RA_001_TABS, active=tab)
    if tab == 0:
        y = wf.filters(s, y, ["고객사 은행 A", "서비스 전체", "모델 RA-KR v4"])
        y = wf.kpi_cards(s, y, [
            ("낮음", "28,900 명", "68% · 재심사 36개월", "green"),
            ("중간", "12,880 명", "30% · 재심사 24개월", "blue"),
            ("높음", "1,204 명", "3% · 재심사 12개월", "orange"),
            ("거래금지", "0 명", "즉시 케이스 생성", "red")])
        y = wf.two_panels(s, y, 1.45,
            ("다음 재심사 예정", ["항목", "값"],
             [["30일 내", "1,204"], ["기한 임박", "88 ⚠"],
              ["기한 초과", "0"], ["모델 버전", "RA-KR v4 (활성)"]],
             [0.48, 0.52]),
            ("등급 분포 요약", ["등급", "인원", "비율"],
             [["낮음", "28,900", "68%"], ["중간", "12,880", "30%"],
              ["높음", "1,204", "3%"], ["거래금지", "0", "0%"]],
             [0.34, 0.36, 0.30]))
        wf.callout(s, y, "① 점수 분포 — 등급별 현황 카드·분포 요약", [
            "다음 → ② 고위험 목록 탭에서 높음·거래금지 대상 목록 및 상세 진입"])
        wf.info_panel(s, "AML-RA-001", [
            "• 권한 조회 aml:case:read",
            "• 탭 ① 점수 분포 / ② 고위험 목록 (순수 모니터링)",
            "• 필터 고객사 / 서비스 / 모델 버전 선택",
            "• KPI 카드 낮음/중간/높음/거래금지 인원·비율",
            "• 재심사 예정 30일 내 · 기한 임박 ⚠ · 초과",
            "• 다음 → ② 고위험 목록",
            "▸ API GET /api/v1/bo/aml/dashboard (분포 집계·bo-api)"])
    elif tab == 1:
        y = wf.filters(s, y, ["등급 높음·거래금지", "주요 factor 전체", "재심사 임박"])
        y = wf.table_block(s, y, 2.45, "고위험 목록 (높음·거래금지) · 행 ▶ → AML-RA-003 (대상 상세)",
            ["대상(식별자)", "유형", "점수", "등급", "주요 factor", "재심사일", "상세"],
            [["cust_…501", "개인", "88", "높음", "고위험국가", "06-20", "▶"],
             ["ent_…220", "법인", "91", "높음", "UBO 불명", "06-12 ⚠", "▶"],
             ["cust_…780", "개인", "85", "높음", "WLF match", "06-18", "▶"],
             ["cust_…312", "개인", "79", "높음", "고위험국가·UBO", "06-25", "▶"]],
            [0.20, 0.10, 0.09, 0.11, 0.20, 0.18, 0.12])
        wf.callout(s, y, "② 고위험 목록 — 행 클릭 → AML-RA-003 (대상 상세·EDD 착수)", [
            "재심사 기한 임박/초과 ⚠ · 케이스(EDD 재심사) 딥링크",
            "이전 ← ① 점수 분포  (RA 분포 2탭 끝) · 모델 초안 검증·시뮬레이션은 AML-RA-002 ③"])
        wf.info_panel(s, "AML-RA-001", [
            "• 권한 조회 aml:case:read",
            "• 탭 ② 고위험 목록 (높음·거래금지 대상)",
            "• 필터 등급 / 주요 factor / 재심사 임박 ⚠",
            "• 컬럼 대상(식별자) · 유형 · 점수 · 등급 · 주요 factor · 재심사일 · 상세",
            "• 주요 factor 고위험국가·UBO 불명·WLF match·거래 행동 등",
            "• 흐름 행 클릭 → AML-RA-003 (상세·EDD 착수)",
            "• 모델 시뮬레이션은 AML-RA-002 ③ 시뮬레이션 탭에서 수행(모델 저작 활동)",
            "• 이전 ← ① 점수 분포  (RA 분포 2탭 끝)",
            "▸ API GET /api/v1/bo/aml/dashboard (고위험 목록 집계·bo-api) · GET /api/v1/aml/customers/{ref}/risk (개별 조회)"])


RA_002_TABS = ["버전 목록", "factor 편집", "시뮬레이션", "등급 조정 이력"]


def ra_002(p, tab=0):
    titles = ["RA 모델 관리 — ① 버전 목록",
              "RA 모델 관리 — ② factor 편집",
              "RA 모델 관리 — ③ 시뮬레이션",
              "RA 모델 관리 — ④ 등급 조정 이력"]
    crumbs = ["AML Console > RA·CDD > RA 모델 관리 > 버전 목록",
              "AML Console > RA·CDD > RA 모델 관리 > factor 편집",
              "AML Console > RA·CDD > RA 모델 관리 > 시뮬레이션",
              "AML Console > RA·CDD > RA 모델 관리 > 등급 조정 이력"]
    s = frame(p, "AML-RA-002", crumbs[tab], titles[tab])
    y = wf.CON_TOP
    y = wf.tab_chips(s, y, RA_002_TABS, active=tab)
    if tab == 0:
        y = wf.filters(s, y, ["모델 전체", "상태 전체"])
        y = wf.table_block(s, y, 2.30, "RA 모델 버전 목록 [RA-KR]",
            ["버전", "상태", "활성화일", "factor 수", "작성자", ""],
            [["RA-KR v5", "초안(DRAFT)", "—", "8", "이감리", "[편집 ▶]"],
             ["RA-KR v4", "활성(ACTIVE)", "2026-03-01", "7", "이감리", "[비교]"],
             ["RA-KR v3", "비활성", "2025-09-01", "6", "박심사", "[비교]"]],
            [0.18, 0.18, 0.18, 0.12, 0.16, 0.18])
        wf.callout(s, y, "① 버전 목록 — 활성 버전 1개 유지 · 초안 편집 → ② factor 편집 탭", [
            "[새 버전 생성] → 초안(DRAFT) 생성 · [편집 ▶] 클릭 → ② factor 편집 탭",
            "활성화는 ② factor 편집 탭에서 [활성화 상신(2인·RA_MODEL)] → AML-APR-001",
            "다음 → ② factor 편집"])
        wf.info_panel(s, "AML-RA-002", [
            "• 권한 조회·초안 생성 aml:admin:policy",
            "• 탭 ① 버전 목록 / ② factor 편집 / ③ 시뮬레이션 / ④ 등급 조정 이력",
            "• 컬럼 버전 · 상태 · 활성화일 · factor 수 · 작성자",
            "• 상태 초안(DRAFT) / 활성(ACTIVE) / 비활성",
            "• 활성 버전 1개 유지 · 비교 리포트 보존",
            "• 다음 → ② factor 편집",
            "▸ API GET .../ra-models · POST (새 버전)"])
    elif tab == 1:
        y = wf.form_block(s, y, 1.5, "v5 factor 편집 — 문장형 빌더 [모델: RA-KR]",
            [("① 대상 *", "개인·법인 고객", "input"),
             ("② 측정 항목 *", "고위험 국가 거주 여부 ▼ (국가위험 등급표 연동 · AML-CTRY-001)", "input"),
             ("③ 가중치 · ④ 등급 임계 *", "+25 점  ·  높음 70 점 / 거래금지 90 점", "input")])
        y = wf.condition_builder(s, y, 2.15,
            "⑤ 추가 조건 — 여러 조건을 AND/OR로 결합 (충족 시 추가 가산)",
            "AND",
            [("실소유자(UBO) 확인", "상태", "미완료"),
             ("최근 1년 고위험국가 송금", "건수 이상", "3 건"),
             ("WLF 매칭 이력", "상태", "있음")],
            footer_btns=["+ 조건 추가", "+ 그룹(괄호) 추가"],
            group_note="그룹 간 결합: AND ▼")
        wf.callout(s, y, "② factor 편집 — 자연어 미리보기 · 활성화 상신 (4-eyes)", [
            "\"고위험 국가 거주 고객은 25점 가산, 추가조건[UBO 미완료 AND 고위험국가 송금 3건↑ AND WLF 매칭 있음] 모두 만족이면 +15점.",
            " 합산 70점↑ '높음', 90점↑ '거래금지'로 분류한다.\"",
            "[임시저장] [시뮬레이션(→ ③ 시뮬레이션 탭)] [활성화 상신(2인·RA_MODEL)]"])
        wf.info_panel(s, "AML-RA-002", [
            "• 권한 모델 활성화 상신 aml:admin:policy (2인)",
            "• 탭 ② factor 편집",
            "• 문장형 빌더 ①대상 ②측정 항목 ③가중치 ④등급 임계 ⑤추가조건 ⑥동작",
            "• ② 측정 '고위험 국가'는 AML-CTRY-001 국가위험 등급표 연동",
            "• 자연어 미리보기로 결합 논리 확인 → ③ 시뮬레이션 검증 → 활성화 상신",
            "• 모델 활성화 4-eyes(RA_MODEL·준법감시 책임자)",
            "• payload_hash 고정 · 자기 승인 차단",
            "• 이전 ← ① 버전 목록  /  다음 → ③ 시뮬레이션",
            "▸ API GET .../ra-models/versions/{v} · :activate(2인·RA_MODEL)"])
    elif tab == 2:
        y = wf.entry_banner(s, y, "AML-RA-002 ② factor 편집에서 [시뮬레이션] 클릭 → 편집한 RA-KR v5 초안을 활성화 전 검증")
        y = wf.filters(s, y, ["모델 RA-KR v5 초안 ▼", "샘플 최근 90일 신규 ▼"])
        y = wf.kpi_cards(s, y, [
            ("시뮬레이션 결과 - 높음", "+142 명", "현재 대비 증가", "orange"),
            ("시뮬레이션 결과 - 중간", "-88 명", "현재 대비 감소", "blue"),
            ("시뮬레이션 결과 - 낮음", "-54 명", "현재 대비 감소", "green"),
            ("오탐 예상", "+6%", "현재 v4 대비", "red")])
        y = wf.two_panels(s, y, 1.50,
            ("시뮬레이션 설정", ["항목", "값"],
             [["비교 모델", "RA-KR v5 초안(② 편집) vs v4 (활성)"],
              ["샘플 기간", "최근 90일 신규 고객"],
              ["샘플 수", "2,400명"],
              ["실행 시간", "약 30초 (결재 불필요)"]],
             [0.44, 0.56]),
            ("factor 변화 영향", ["factor", "영향"],
             [["고위험국가 가중치", "+5pt → 높음 증가"],
              ["UBO 조건 완화", "중간 일부 낮음으로"],
              ["거래 행동 신규", "기존 v4 미적용"],
              ["오탐율", "v4: 4% → v5: 10%"]],
             [0.50, 0.50]))
        wf.callout(s, y, "③ 시뮬레이션 — 활성화 전 초안 검증(분석 전용 · 등급 변경 없음 · 결재 불필요)", [
            "[시뮬레이션 실행] → factor 변화·등급 이동·오탐율 미리보기",
            "검증 후 활성화는 ② factor 편집 → [활성화 상신(2인·RA_MODEL)] → AML-APR-001",
            "이전 ← ② factor 편집  /  다음 → ④ 등급 조정 이력"])
        wf.info_panel(s, "AML-RA-002", [
            "• 권한 시뮬레이션 aml:admin:policy (결재 불필요·분석 전용)",
            "• 탭 ③ 시뮬레이션 (② factor 편집의 초안 모델 검증 — 모델 저작 흐름)",
            "• 설정 비교 모델(편집 중 초안 vs 활성) / 샘플 기간 / 샘플 수",
            "• 결과 등급 이동(높음/중간/낮음 delta) + 오탐율 예상",
            "• factor 변화 영향 표 (변경 factor별 등급 이동 설명)",
            "• 실행 후 결재 없이 분석 결과만 표시 · 활성화는 ② factor 편집에서 상신",
            "• 이전 ← ② factor 편집  /  다음 → ④ 등급 조정 이력",
            "▸ API POST .../ra-models/{modelCode}/simulate (결재 불필요)"])
    else:  # tab == 3
        y = wf.filters(s, y, ["등급 조정 유형 전체", "기간 전체"])
        y = wf.table_block(s, y, 2.20, "등급 수동 조정 이력 (4-eyes · RISK_OVERRIDE)",
            ["조정ID", "대상(식별자)", "기존 등급", "조정 등급", "사유", "상신자/승인자", "일시"],
            [["ov-090", "cust_…501", "높음(88)", "중간", "EDD 완료", "김분석/이감리", "06-07 15:30"],
             ["ov-085", "ent_…220", "높음(91)", "높음", "재확인", "박심사/이감리", "06-05 11:20"]],
            [0.10, 0.16, 0.14, 0.14, 0.18, 0.18, 0.10])
        wf.callout(s, y, "④ 등급 조정 이력 — 등급 수동 조정은 여기서 신청 + 이력 확인", [
            "등급 수동 조정: score 높음(88) → [중간 ▼] 사유 [EDD 완료] [등급 조정 상신(2인·RISK_OVERRIDE 하향)]",
            "하향 조정 4-eyes(RISK_OVERRIDE) · 상향·동일은 사유 후 즉시(감사) · 사유 필수",
            "이전 ← ③ 시뮬레이션  (RA 모델 4탭 끝)"])
        wf.info_panel(s, "AML-RA-002", [
            "• 권한 등급 조정 aml:case:update (2인 하향)",
            "• 탭 ④ 등급 조정 이력",
            "• 컬럼 조정ID · 대상 · 기존 등급 · 조정 등급 · 사유 · 상신자/승인자 · 일시",
            "• 등급 하향 4-eyes(RISK_OVERRIDE) · 상향/동일 즉시(사유+감사)",
            "• 모든 조정 이력 감사 보존",
            "• 이전 ← ③ 시뮬레이션  (RA 모델 4탭 끝)",
            "▸ API GET .../risk-scores/overrides · POST .../override(2인·RISK_OVERRIDE)"])


RA_003_TABS = ["factor breakdown", "관계·UBO", "재심사 이력"]


def ra_003(p, tab=0):
    titles = ["RA 대상 상세 — ① factor breakdown (cust_…501)",
              "RA 대상 상세 — ② 관계·UBO (cust_…501)",
              "RA 대상 상세 — ③ 재심사 이력 (cust_…501)"]
    crumbs = ["AML Console > RA·CDD > RA 고위험 > 대상 상세 > factor breakdown",
              "AML Console > RA·CDD > RA 고위험 > 대상 상세 > 관계·UBO",
              "AML Console > RA·CDD > RA 고위험 > 대상 상세 > 재심사 이력"]
    s = frame(p, "AML-RA-003", crumbs[tab], titles[tab], search="대상 식별자 검색...")
    y = wf.CON_TOP
    y = wf.tab_chips(s, y, RA_003_TABS, active=tab)
    if tab == 0:
        y = wf.entry_banner(s, y, "AML-RA-001 ② 고위험 목록에서 [대상 행 ▶] 클릭 → 대상 상세·EDD 착수")
        y = wf.two_panels(s, y, 1.60,
            ("대상 / 등급", ["항목", "값"],
             [["대상(식별자)", "cust_…501 (개인)"], ["위험 점수", "88 점"],
              ["등급", "높음(HIGH)"], ["다음 재심사", "06-20"],
              ["권고 조치", "EDD 수행(requiredAction)"]],
             [0.40, 0.60]),
            ("factor breakdown (근거 분해)", ["factor", "기여"],
             [["고위험 국가 거주", "+25"], ["UBO 확인 미완료", "+20"],
              ["WLF 매칭 이력", "+18"], ["고위험국가 송금 다발", "+15"],
              ["거래 행동 이상", "+10"]],
             [0.62, 0.38]))
        y = wf.table_block(s, y, 1.25, "EDD 체크리스트 실행 (강화된 고객확인)",
            ["체크 항목", "필수", "증빙", "상태"],
            [["실소유자(UBO) 확인", "필수", "지분 구조도", "미완료"],
             ["자금 출처·거래 목적", "필수", "소득·계약 증빙", "진행중"],
             ["고위험 국가 거주 확인", "필수", "거주 증빙", "완료"]],
            [0.34, 0.14, 0.30, 0.22])
        wf.callout(s, y, "① factor breakdown — [EDD 케이스 착수] → AML-CASE-002", [
            "[고객 프로필 ▶ → AML-CDD-002] CDD 프로필 원장(read-only) 드릴다운 (v7.0)",
            "등급 수동 조정이 필요하면 → AML-RA-002 ④ 등급 조정 이력(RISK_OVERRIDE 하향 4-eyes)",
            "다음 → ② 관계·UBO 탭"])
        wf.info_panel(s, "AML-RA-003", [
            "• 권한 조회 aml:case:read / EDD 케이스 생성 aml:case:update",
            "• 진입 AML-RA-001 ② 고위험 목록 행 클릭",
            "• 탭 ① factor breakdown / ② 관계·UBO / ③ 재심사 이력",
            "• factor breakdown 국가위험·UBO 불명·WLF match·거래 행동 기여도",
            "• 당연고위험 사유는 AML-HRR-001 분류 기준 파생 표기 (v7.0)",
            "• [고객 프로필 ▶ → AML-CDD-002] 드릴다운 (v7.0)",
            "• 권고 조치 CDD 갱신/EDD/관계검토/없음",
            "• EDD 체크리스트 정의는 AML-CDD-001 정책 따름",
            "• 다음 → ② 관계·UBO",
            "▸ API GET /aml/customers/{ref}/risk · POST .../cdd/cases(EDD 착수)"])
    elif tab == 1:
        y = wf.two_panels(s, y, 1.85,
            ("관계 구조 (연결 상대방)", ["관계 유형", "식별자", "리스크"],
             [["실소유자(UBO)", "cust_…800 (지분 51%)", "높음"],
              ["거래 상대방", "ent_…330 (고위험 corridor)", "중간"],
              ["연결 계좌", "acc_…501 · acc_…502", "—"],
              ["이전 고객사", "핀테크 B (전 고객)", "낮음"]],
             [0.34, 0.40, 0.26]),
            ("UBO 확인 현황", ["항목", "값"],
             [["UBO 확인 상태", "미완료 (지분 구조도 미제출)"],
              ["지분 구조도", "—  (EDD 체크리스트 미완료)"],
              ["UBO 이름", "마스킹(aml:pii:reveal 필요)"],
              ["UBO 국적", "마스킹"]],
             [0.42, 0.58]))
        wf.callout(s, y, "② 관계·UBO — 연결 구조 시각화 · UBO 확인 상태", [
            "UBO 지분 구조도 미제출 → EDD 체크리스트 '실소유자(UBO) 확인' 미완료 상태",
            "원문(UBO 이름·국적) 열람 → aml:pii:reveal + 사유 + 감사 로그 필수",
            "이전 ← ① factor breakdown  /  다음 → ③ 재심사 이력"])
        wf.info_panel(s, "AML-RA-003", [
            "• 권한 조회 aml:case:read / PII 열람 aml:pii:reveal(감사)",
            "• 탭 ② 관계·UBO",
            "• 관계 유형 실소유자(UBO) · 거래 상대방 · 연결 계좌 · 이전 고객사",
            "• UBO 확인 상태 완료/미완료 · 지분 구조도 첨부 여부",
            "• PII(이름·국적) 마스킹 · 원문 열람 감사 자동 기록",
            "• 이전 ← ① factor breakdown  /  다음 → ③ 재심사 이력",
            "▸ API GET /aml/customers/{ref}/relationships · /ubo"])
    else:  # tab == 2
        y = wf.kpi_cards(s, y, [
            ("전체 재심사", "4 회", "최초 2025-06-01~현재", "blue"),
            ("최근 등급", "높음 (88점)", "2026-06-01 평가", "orange"),
            ("등급 변화", "낮음→중간→높음", "2회 상승", "red"),
            ("다음 재심사", "06-20", "12개월 주기", "green")])
        y = wf.table_block(s, y, 2.10, "재심사 이력 (RA 평가 이력)",
            ["평가일", "점수", "등급", "주요 factor 변화", "평가 방식"],
            [["2026-06-01", "88", "높음", "고위험국가 +25, UBO 미완료 +20", "정기 자동"],
             ["2026-01-15", "72", "높음", "WLF match +18 신규", "수동 재평가"],
             ["2025-09-01", "45", "중간", "거래 행동 이상 +10 진입", "정기 자동"],
             ["2025-06-01", "22", "낮음", "기준 충족", "최초 평가"]],
            [0.16, 0.09, 0.12, 0.40, 0.23])
        wf.callout(s, y, "③ 재심사 이력 — 등급 변화 추이·factor 변화 추적", [
            "등급 낮음 → 중간 → 높음 이력 · factor 기여 변화 확인",
            "이전 ← ② 관계·UBO  (RA 대상 상세 3탭 끝)"])
        wf.info_panel(s, "AML-RA-003", [
            "• 권한 조회 aml:case:read",
            "• 탭 ③ 재심사 이력",
            "• 컬럼 평가일 · 점수 · 등급 · 주요 factor 변화 · 평가 방식",
            "• 평가 방식 정기 자동 / 수동 재평가 / EDD 착수",
            "• 등급 변화 추이로 위험 상승 패턴 분석",
            "• 이전 ← ② 관계·UBO  (RA 대상 상세 3탭 끝)",
            "▸ API GET /aml/customers/{ref}/risk/history"])


# ─── AML-CDD-002 고객 CDD 프로필 원장 (v7.0 벤치마크 2차, 드릴다운, 2탭) ───
CDD_002_TABS = ["CDD 프로필(신원확인·검증)", "위험·활동 요약"]


def cdd_002(p, tab=0):
    titles = ["고객 CDD 프로필 원장 — ① CDD 프로필(신원확인·검증) (cust_…501)",
              "고객 CDD 프로필 원장 — ② 위험·활동 요약 (cust_…501)"]
    crumbs = ["AML Console > RA·CDD > 고객 프로필 > CDD 프로필",
              "AML Console > RA·CDD > 고객 프로필 > 위험·활동 요약"]
    s = frame(p, "AML-CDD-002", crumbs[tab], titles[tab], search="대상 식별자 검색...")
    y = wf.CON_TOP
    y = wf.tab_chips(s, y, CDD_002_TABS, active=tab)
    if tab == 0:
        y = wf.entry_banner(s, y, "AML-RA-003 ① / AML-CASE-002 ① / AML-WLF-001 하단 상세에서 [고객 프로필 ▶] 클릭 (read-only 원장)")
        y = wf.two_panels(s, y, 2.25,
            ("공통 · 신원확인 (마스킹)", ["항목", "값"],
             [["대상(식별자)", "cust_…501 (개인)"],
              ["이름 / 실명번호", "마스킹 (pii:reveal 필요)"],
              ["국적 / 거주", "KR / 거주자"],
              ["신원확인 증표", "주민등록증 (대면)"],
              ["검증 방법", "신분증 진위 확인 + 안면 대조"],
              ["고객 상태", "정상 (등록 2025-03-10)"],
              ["KYC 상태", "확인 완료 (2026-01-15)"]],
             [0.40, 0.60]),
            ("개인 추가 정보 (CDD 수집 항목)", ["항목", "값"],
             [["직업 / 업종", "회사원 / 제조업"],
              ["자금 원천", "근로소득"],
              ["거래 목적", "해외 송금(가족 생활비)"],
              ["월평균 소득 구간", "300~500만원"],
              ["대면 여부", "비대면 (영상 확인)"],
              ["추가정보 수집 대상", "예 (EDD L2)"],
              ["변경 이력", "ingest 이벤트 기준 표시"]],
             [0.42, 0.58]))
        wf.callout(s, y, "① CDD 프로필 — read-only 원장 (편집 불가 · 수집/수정은 고객사 소스 시스템 소관)", [
            "법인 고객은 법인 유형·상장 여부·비영리 설립목적 검증·실소유자(UBO) 확인 면제 여부·대표자 요약으로 분기",
            "원문 열람 aml:pii:reveal + 사유 + RAW_DATA_ACCESS 감사 · 다음 → ② 위험·활동 요약 탭"])
        wf.info_panel(s, "AML-CDD-002", [
            "• 권한 조회 aml:case:read (read-only) / 원문 aml:pii:reveal(감사)",
            "• 진입 AML-RA-003 ① · AML-CASE-002 ① · AML-WLF-001 [고객 프로필 ▶]",
            "• 탭 ① CDD 프로필 / ② 위험·활동 요약",
            "• 공통 식별자·국적·신원확인 증표·검증 방법·고객 상태",
            "• 개인 직업·업종·자금 원천·거래 목적·소득 구간",
            "• 법인 법인유형·상장·비영리 설립목적·UBO 확인 면제·대표자",
            "• 편집 불가 — CDD 수집·수정은 고객사 소스 시스템(ingest) 소관",
            "• 다음 → ② 위험·활동 요약",
            "▸ API GET /aml/customers/{ref}/profile (제안 · 후속 API 정합)"])
    else:
        y = wf.kpi_cards(s, y, [
            ("RA 등급", "높음 (88점)", "재이행 예정 06-20", "red"),
            ("스크리닝 이력", "3 건", "확정 1 · 오탐 2", "blue"),
            ("진행 케이스", "1 건", "EDD 조사중 ▶", "orange"),
            ("STR 보고", "1 건", "준법감시 전담 한정", "green")])
        y = wf.two_panels(s, y, 1.85,
            ("당연고위험 사유 (AML-HRR-001 분류 파생)", ["팩터", "해당"],
             [["고위험 국가", "해당 없음"],
              ["고위험 업종", "해당 없음"],
              ["WLF 확정 매칭", "해당 (당연초고위험)"],
              ["고액자산가", "해당 없음"],
              ["거래 거절 이력", "1건 (2025-11)"]],
             [0.56, 0.44]),
            ("관계·UBO 요약 (→ AML-RA-003 ②)", ["항목", "값"],
             [["실소유자(UBO)", "cust_…800 (지분 51%)"],
              ["UBO 확인 상태", "미완료"],
              ["연결 계좌", "acc_…501 · acc_…502"],
              ["거래 상대방", "ent_…330 (고위험 corridor)"]],
             [0.40, 0.60]))
        wf.callout(s, y, "② 위험·활동 요약 — 전 항목 화면 파생값 (각 도메인 집계 · 별도 저장 없음)", [
            "드릴다운 케이스 ▶ → AML-CASE-002 · 스크리닝 ▶ → AML-WLF-003 · RA 상세 ▶ → AML-RA-003",
            "STR 보고 건수·플래그는 준법감시 전담 role에만 렌더링(비전담 미노출 · tipping-off)",
            "이전 ← ① CDD 프로필 (고객 프로필 2탭 끝)"])
        wf.info_panel(s, "AML-CDD-002", [
            "• 권한 조회 aml:case:read / STR 건수 준법감시 전담 한정",
            "• 탭 ② 위험·활동 요약",
            "• 카드 RA 등급·스크리닝 이력·진행 케이스·STR 보고(전담)",
            "• 당연고위험 사유 AML-HRR-001 분류 기준 파생 표기",
            "• 관계·UBO 요약 → AML-RA-003 ② 드릴다운",
            "• 수치 전부 화면 파생값(도메인 조회 API 집계)",
            "• 이전 ← ① CDD 프로필 (2탭 끝)",
            "▸ API GET /aml/customers/{ref}/profile (제안 · 후속 API 정합)"])


# ─── AML-HRR-001 당연고위험 레지스트리 (v7.0 벤치마크 2차, 2탭) ───
HRR_001_TABS = ["당연고위험 분류 기준", "참조 리스트 관리"]


def hrr_001(p, tab=0):
    titles = ["당연고위험 레지스트리 — ① 당연고위험 분류 기준",
              "당연고위험 레지스트리 — ② 참조 리스트 관리"]
    crumbs = ["AML Console > RA·CDD > 당연고위험 레지스트리 > 분류 기준",
              "AML Console > RA·CDD > 당연고위험 레지스트리 > 참조 리스트"]
    s = frame(p, "AML-HRR-001", crumbs[tab], titles[tab], search="팩터·코드 검색...")
    y = wf.CON_TOP
    y = wf.tab_chips(s, y, HRR_001_TABS, active=tab)
    if tab == 0:
        y = wf.two_panels(s, y, 2.25,
            ("분류 팩터 (점수 무관 등급 강제 상향)", ["구분", "팩터"],
             [["당연고위험", "고위험 국가 (AML-CTRY-001 파생)"],
              ["당연고위험", "고위험 업종"],
              ["당연고위험", "고위험 상품/서비스"],
              ["당연고위험", "STR 보고 다발 · FDS 이상거래 연계"],
              ["당연초고위험", "WLF 확정 매칭"],
              ["당연초고위험", "고액자산가"],
              ["당연초고위험", "기타 위험 대상(직권)"]],
             [0.30, 0.70]),
            ("선택 팩터 코드 상세 — 고위험 업종", ["코드", "코드명", "비고"],
             [["6499", "기타 금융업(대부 등)", "—"],
              ["9200", "사행시설 운영", "—"],
              ["4774", "귀금속·보석 소매", "—"],
              ["6612", "환전영업자", "—"],
              ["7399", "가상자산 연계 서비스", "VASP 리스트 연동"]],
             [0.16, 0.50, 0.34]))
        wf.callout(s, y, "① 분류 기준 — RA 모델 점수와 별개의 오버라이드 규칙 가시화", [
            "당연고위험 → 등급 '높음' 강제 · 당연초고위험 → '높음' + EDD 즉시 트리거",
            "RA 결과(AML-RA-003 ①)에 '당연고위험 사유' 별도 표기 — 점수 분해와 구분",
            "국가 팩터 정본은 AML-CTRY-001(파생 표시 · 이중 관리 금지) · 다음 → ② 참조 리스트 탭"])
        wf.info_panel(s, "AML-HRR-001", [
            "• 권한 조회 aml:case:read / 변경 aml:admin:policy(2인)",
            "• 탭 ① 분류 기준 / ② 참조 리스트 관리",
            "• 당연고위험 국가·업종·상품/서비스·STR 다발·FDS 연계",
            "• 당연초고위험 WLF 확정·고액자산가·기타(직권)",
            "• 팩터 행 선택 → 우측 해당 코드 목록 상세",
            "• 등급 강제 상향은 RA 모델 가중치(AML-RA-002)와 독립",
            "• 다음 → ② 참조 리스트 관리",
            "▸ API GET .../high-risk-registry (제안 · 후속 API 정합)"])
    else:
        y = wf.filters(s, y, ["리스트 종류 상품/서비스", "위험도 전체"])
        y = wf.table_block(s, y, 1.55, "상품/서비스 위험 리스트 [템플릿 다운로드] [파일 업로드]",
            ["상품/서비스", "분류", "위험도", "비고"],
            [["선불 상품권", "선불", "중위험", "KoFIU 보고상품 매핑"],
             ["가맹점 정산(PG)", "정산", "저위험", "—"],
             ["해외 송금(고위험 corridor)", "송금", "고위험", "당연고위험 트리거"]],
            [0.30, 0.16, 0.16, 0.38])
        y = wf.table_block(s, y, 1.30, "가상자산사업자(VASP) 식별 리스트",
            ["법인명(토큰)", "사업자번호(hash)", "키워드", "등록일"],
            [["ent_…v01", "biz_…12f", "거래소·코인", "2026-05-02"],
             ["ent_…v02", "biz_…88a", "월렛·커스터디", "2026-04-11"]],
            [0.22, 0.26, 0.30, 0.22])
        wf.callout(s, y, "② 참조 리스트 — 변경 [상신(2인 · HIGH_RISK_REGISTRY 제안)] · 고액자산가 기준 포함", [
            "고액자산가 기준 — 기준금액 30억원 이상 · 추출 주기 월간 (개별 확정·예외는 케이스 흐름 재사용)",
            "리스트 갱신 영향 대상 재평가는 차기 정기 RA 배치 반영(즉시 재평가는 후속 오픈결정)",
            "이전 ← ① 분류 기준 (레지스트리 2탭 끝)"])
        wf.info_panel(s, "AML-HRR-001", [
            "• 권한 변경 aml:admin:policy(2인 · 준법감시 책임자)",
            "• 탭 ② 참조 리스트 관리",
            "• 상품/서비스 위험 리스트 — 상품·분류·위험도",
            "• VASP 식별 리스트 — 법인명(토큰)·사업자번호(hash)·키워드",
            "• 고액자산가 기준 — 기준금액·추출 주기",
            "• 템플릿 다운로드 → 파일 업로드 일괄 등록 + 변경 상신(2인)",
            "• 전 변경 이력 감사 보존",
            "• 이전 ← ① 분류 기준 (2탭 끝)",
            "▸ API PUT .../high-risk-registry/{category}(2인) (제안 · 후속 API 정합)"])


# ═══ 6. CDD/EDD 체크리스트 관리 ═════════════════════════════════
CDD_001_TABS = ["체크리스트 정의", "재심사 주기", "변경 이력"]


def cdd_001(p, tab=0):
    titles = ["CDD/EDD 체크리스트 관리 — ① 체크리스트 정의",
              "CDD/EDD 체크리스트 관리 — ② 재심사 주기",
              "CDD/EDD 체크리스트 관리 — ③ 변경 이력"]
    crumbs = ["AML Console > RA·CDD > 체크리스트 관리 > 체크리스트 정의",
              "AML Console > RA·CDD > 체크리스트 관리 > 재심사 주기",
              "AML Console > RA·CDD > 체크리스트 관리 > 변경 이력"]
    s = frame(p, "AML-CDD-001", crumbs[tab], titles[tab],
              action="+ 변경 상신" if tab < 2 else None)
    y = wf.CON_TOP
    y = wf.tab_chips(s, y, CDD_001_TABS, active=tab)
    if tab == 0:
        y = wf.table_block(s, y, 2.5, "CDD/EDD 체크리스트 항목 (정책 store · 강화된 고객확인 v4)",
            ["항목", "필수", "증빙 유형", "위험 트리거"],
            [["고객확인(신원·실명)", "필수", "신분 증빙", "기본"],
             ["실소유자(UBO) 확인", "필수", "지분 구조도", "법인·고위험"],
             ["자금 출처·거래 목적", "필수", "소득·계약 증빙", "고위험"],
             ["고위험 국가 거주 확인", "조건부", "거주 증빙", "국가위험 높음↑"],
             ["거래 모니터링 동의", "필수", "약관 동의", "기본"]],
            [0.34, 0.12, 0.28, 0.26])
        wf.callout(s, y, "① 체크리스트 정의 — 정책 store(versioned) · 변경은 ③ 변경 이력에서 4-eyes", [
            "체크리스트 항목·필수여부·증빙 유형·위험 트리거(업무 용어, 변수명 비노출)",
            "다음 → ② 재심사 주기 탭"])
        wf.info_panel(s, "AML-CDD-001", [
            "• 권한 조회·변경 상신 aml:admin:policy",
            "• 탭 ① 체크리스트 정의 / ② 재심사 주기 / ③ 변경 이력",
            "• 체크리스트 항목·필수여부·증빙 유형·위험 트리거",
            "• 정책 store(versioned) · 물리 마스터 테이블 미보유",
            "• AML-RA-003 EDD 체크리스트 실행이 본 정의를 따름",
            "• 다음 → ② 재심사 주기",
            "▸ API GET/POST .../cdd/checklists"])
    elif tab == 1:
        y = wf.table_block(s, y, 1.65, "재심사(periodic review) 주기 — 등급별 재확인 주기",
            ["위험 등급", "재확인 주기", "유예 기간"],
            [["낮음", "36개월", "30일"], ["중간", "24개월", "20일"],
             ["높음", "12개월", "10일"], ["거래금지", "—", "—"]],
            [0.34, 0.34, 0.32])
        y = wf.callout(s, y, "② 재심사 주기 — 등급별 주기·유예 기간 · 변경은 4-eyes", [
            "[재심사 주기 변경 상신(2인)] 등급별 주기·유예 변경 → 승인 후 적용 · 차기 재심사 일정 반영",
            "재심사 스케줄은 BE(T-13)가 케이스 자동 생성 → AML-CASE-001",
            "이전 ← ① 체크리스트 정의  /  다음 → ③ 변경 이력"])
        wf.info_panel(s, "AML-CDD-001", [
            "• 권한 변경 상신 aml:admin:policy (2인)",
            "• 탭 ② 재심사 주기",
            "• 등급별 재확인 주기(개월) · 유예 기간(일)",
            "• 재심사 주기 변경 4-eyes(PERIODIC_REVIEW_CHANGE)",
            "• 차기 재심사 일정에 반영 (BE 스케줄러)",
            "• 이전 ← ① 체크리스트 정의  /  다음 → ③ 변경 이력",
            "▸ API PUT .../cdd/periodic-review-policy(2인)"])
    else:  # tab == 2
        y = wf.table_block(s, y, 2.30, "변경 이력 (4-eyes 증적 · CHECKLIST_CHANGE / PERIODIC_REVIEW_CHANGE)",
            ["결재ID", "변경 유형", "변경 내용", "상신자", "상태", "처리일"],
            [["apr-490", "체크리스트 변경", "UBO 항목 '법인·고위험' 조건 추가", "이감리", "승인", "2026-03-15"],
             ["apr-455", "재심사 주기 변경", "높음 24개월 → 12개월 단축", "이감리", "승인", "2026-01-10"],
             ["apr-410", "체크리스트 변경", "거래 모니터링 동의 항목 신규 추가", "박심사", "반려", "2025-11-20"]],
            [0.12, 0.20, 0.34, 0.12, 0.10, 0.12])
        wf.callout(s, y, "③ 변경 이력 — 체크리스트·주기 변경 4-eyes 증적", [
            "체크리스트 변경(CHECKLIST_CHANGE) · 재심사 주기 변경(PERIODIC_REVIEW_CHANGE) 이력",
            "조회·초안은 결재 불필요 · 변경 적용만 4-eyes",
            "이전 ← ② 재심사 주기  (CDD 체크리스트 3탭 끝)"])
        wf.info_panel(s, "AML-CDD-001", [
            "• 권한 조회 aml:admin:policy",
            "• 탭 ③ 변경 이력",
            "• 컬럼 결재ID · 변경 유형 · 변경 내용 · 상신자 · 상태 · 처리일",
            "• 변경 유형 체크리스트 변경(CHECKLIST_CHANGE) / 재심사 주기 변경",
            "• 모든 변경 4-eyes 증적 감사 보존",
            "• 이전 ← ② 재심사 주기  (CDD 체크리스트 3탭 끝)",
            "▸ API GET .../cdd/checklists/history · /periodic-review-policy/history"])


# ═══ 7. TM 알림 적체 → 시나리오 빌더 상세 ═══════════════════════
TM_001_TABS = ["알림 적체", "시나리오 관리"]


def tm_001(p, tab=0):
    titles = ["TM 알림 적체 / 시나리오 관리 — ① 알림 적체",
              "TM 알림 적체 / 시나리오 관리 — ② 시나리오 관리"]
    crumbs = ["AML Console > TM 알림·시나리오 > 알림 적체",
              "AML Console > TM 알림·시나리오 > 시나리오 관리"]
    s = frame(p, "AML-TM-001", crumbs[tab], titles[tab], search="대상 식별자 검색...")
    y = wf.CON_TOP
    y = wf.tab_chips(s, y, TM_001_TABS, active=tab)
    if tab == 0:
        y = wf.filters(s, y, ["시나리오 전체", "출처 전체", "심각도 전체", "상태 전체", "기간 전체"])
        y = wf.table_block(s, y, 1.95, "TM 알림 적체 [고객사: 은행 A] · 행 ▶ → AML-CASE-002 (케이스 생성)",
            ["알림ID", "시나리오", "대상(식별자)", "발생 출처", "심각도", "상태", "동작"],
            [["alt-3301", "구조화거래", "cust_…12", "AML 모니터링", "높음", "탐지", "[케이스]"],
             ["alt-3290", "뮬 네트워크", "ent_…77", "AML 모니터링", "매우높음", "1차분류", "[케이스]"],
             ["alt-3277", "급속이동", "cust_…90", "FDS 에스컬레이션", "높음", "케이스생성", "▶"],
             ["alt-3260", "고위험 corridor", "cust_…45", "AML 모니터링", "중간", "탐지", "[케이스]"]],
            [0.11, 0.18, 0.14, 0.18, 0.11, 0.13, 0.15])
        wf.callout(s, y, "① 알림 적체 — [케이스] 클릭 → AML-CASE-002 케이스 생성", [
            "발생 출처 컬럼·필터 — AML 모니터링 / FDS 에스컬레이션(source_origin) 구분",
            "[기각](사유) · [상위 escalation]은 결재 불필요·감사",
            "다음 → ② 시나리오 관리 탭에서 시나리오 클릭 → AML-TM-002"])
        wf.info_panel(s, "AML-TM-001", [
            "• 권한 조회 aml:case:read / 케이스 전환 aml:case:update",
            "• 탭 ① 알림 적체 / ② 시나리오 관리",
            "• 필터 시나리오·발생 출처·심각도·상태·기간 + 대상 식별자",
            "• 컬럼 알림ID·시나리오·대상(식별자)·발생 출처·심각도·상태·동작",
            "• 발생 출처 AML 모니터링 / FDS 에스컬레이션 / 벤더 경보 (source_origin)",
            "• 심각도 낮음/중간/높음/매우높음",
            "• 상태 탐지/1차분류/케이스생성/기각/상위승인/STR권고",
            "• 다음 → ② 시나리오 관리",
            "▸ API GET /aml/alerts?status=PENDING&sourceOrigin="])
    else:  # tab == 1
        y = wf.filters(s, y, ["시나리오 상태 전체", "시나리오 유형 전체"])
        y = wf.table_block(s, y, 2.50, "TM 시나리오 목록 [고객사: 은행 A] · 행 ▶ → AML-TM-002 (빌더) · 효과성 ▶ → AML-STAT-001",
            ["시나리오 코드", "시나리오명", "활성 버전", "상태", "알림(30일)", "전환율", ""],
            [["STRUCTURING", "구조화거래", "v3", "활성", "48", "31%", "[편집 ▶]"],
             ["RAPID_MOVE", "급속이동", "v2", "활성", "21", "24%", "[편집 ▶]"],
             ["MULE_NETWORK", "뮬 네트워크", "v1", "활성", "33", "39%", "[편집 ▶]"],
             ["HIGH_RISK_CORRIDOR", "고위험 corridor", "v2", "활성", "12", "8% ⚠", "[편집 ▶]"],
             ["FAKE_MERCHANT", "허위가맹점", "v1", "초안(DRAFT)", "0", "—", "[편집 ▶]"]],
            [0.20, 0.20, 0.12, 0.12, 0.13, 0.11, 0.12])
        wf.callout(s, y, "② 시나리오 관리 — 시나리오 클릭 → AML-TM-002 빌더 상세", [
            "효과성 요약(알림 30일·케이스 전환율)은 화면 파생값 — 비정상 전환율 ⚠ = 튜닝 후보 → AML-STAT-001 ② 드릴다운",
            "시나리오 활성화·편집은 AML-TM-002(condition_builder 기반 빌더)에서 4-eyes 진행",
            "이전 ← ① 알림 적체  (TM 2탭 끝)"])
        wf.info_panel(s, "AML-TM-001", [
            "• 권한 시나리오 조회 aml:admin:policy",
            "• 탭 ② 시나리오 관리",
            "• 필터 시나리오 상태(활성/초안/비활성) / 유형",
            "• 컬럼 시나리오 코드·명·활성 버전·상태·알림(30일)·전환율",
            "• 효과성 요약 = 화면 파생값(알림 집계) · ⚠=튜닝 후보 배지",
            "• 효과성 상세 드릴다운 → AML-STAT-001 ② 룰 효과성 (벤치마크 보강)",
            "• 시나리오 구조화거래/급속이동/뮬 네트워크/고위험 corridor/허위가맹점 등",
            "• 시나리오 클릭 → AML-TM-002 빌더 상세 편집",
            "• 이전 ← ① 알림 적체  (TM 2탭 끝)",
            "▸ API GET .../tm-scenarios"])


def tm_002(p):
    s = frame(p, "AML-TM-002", "AML Console > TM 시나리오 > 빌더 상세",
              "TM 시나리오 빌더 — 구조화거래 (4-eyes)", action="DSL 토글")
    y = wf.CON_TOP
    y = wf.entry_banner(s, y, "AML-TM-001 ② 시나리오 관리에서 [시나리오 편집 ▶] 클릭 → 시나리오 빌더")
    y = wf.form_block(s, y, 1.4, "기본 조건 (문장형) [시나리오: 구조화거래(STRUCTURING)]",
        [("① 대상 *", "개인·법인 고객의 입금 거래 ▼", "input"),
         ("② 측정 · ③ 기간 *", "거래 건수 ▼ · 합산 금액 ▼  ·  최근 7일 ▼ 동안", "input"),
         ("④ 기준값 *", "9 건 이상 이고 합산 9,000만원 이상이면 탐지", "input")])
    y = wf.condition_builder(s, y, 2.15,
        "⑤ 추가 조건 — 패턴을 AND/OR로 결합 (구조화/반복/고위험국가/비정상정산)",
        "AND",
        [("개별 거래 금액", "미만", "고액현금거래 기준"),
         ("동일 상대방 반복", "건수 이상", "5 건"),
         ("거래 상대국 위험", "이상", "높음")],
        footer_btns=["+ 조건 추가", "+ 그룹(괄호) 추가"],
        group_note="그룹 간 결합: AND ▼")
    wf.callout(s, y, "자연어 미리보기 · 적용 시나리오 (4-eyes · subjectType=TM_SCENARIO)", [
        "\"최근 7일 입금이 9건 이상이고 합산 9,000만원 이상이며, 추가조건[개별 금액 고액현금 기준 미만 AND 동일 상대방 5건↑ AND 상대국 위험 높음↑]이면",
        " '구조화거래' 높음 심각도 알림을 생성하고 케이스 후보(STR_REVIEW)로 연결한다.\"",
        "[임시저장] [시뮬레이션(과거기간 백테스트·결재 불필요)] [시나리오 변경 적용 상신(2인)]"])
    wf.info_panel(s, "AML-TM-002", [
        "• 권한 시나리오 정책 aml:admin:policy (적용=2인)",
        "• 진입 AML-TM-001 시나리오 목록 클릭",
        "• 문장형 빌더 ①대상 ②측정 ③기간 ④기준값 ⑤추가조건 ⑥동작",
        "• ⑤ 추가 조건 = condition_builder(AND/OR 결합 · 필드+연산자+값 · 그룹 괄호)",
        "• 패턴 구조화거래·반복·고위험국가·비정상정산을 조건으로 구성",
        "• 연산자 미만/이상/초과/같음/포함 등 · 업무 용어 드롭다운(scenario DSL 비노출)",
        "• 자연어 미리보기로 결합 논리 확인 후 결재",
        "• 시나리오 변경 적용 4-eyes(TM_SCENARIO·준법감시 책임자)",
        "• 적용 전 시뮬레이션(과거기간 백테스트) 권장(결재 불필요)",
        "• payload_hash 고정 · 변경 시 무효화 · 자기 승인 차단",
        "▸ API GET .../tm-scenarios · simulate · {code}:activate(2인 · TM_SCENARIO)"])


# ═══ 8. 케이스 목록 → 케이스 상세 ═══════════════════════════════
def case_001(p):
    s = frame(p, "AML-CASE-001", "AML Console > 케이스 관리",
              "케이스 목록", search="대상 식별자 검색...", action="+ 케이스")
    y = wf.CON_TOP
    y = wf.tab_chips(s, y, ["내 케이스", "전체", "기한 임박", "종결"], active=0)
    y = wf.filters(s, y, ["케이스 타입 전체", "상태 전체", "우선순위 전체", "담당자 전체"])
    y = wf.table_block(s, y, 2.35, "케이스 목록 [고객사: 은행 A] · 행 ▶ → AML-CASE-002 (케이스 상세)",
        ["케이스ID", "타입", "대상(식별자)", "상태", "우선", "담당", "기한"],
        [["case-771", "강화된 고객확인", "cust_…501", "조사중", "높음", "김분석", "06-20 ▶"],
         ["case-760", "제재 검토", "cust_…123", "승인대기", "긴급", "이감리", "06-08 ⚠ ▶"],
         ["case-744", "Travel Rule 검토", "ent_…220", "조사중", "중간", "박심사", "06-25 ▶"],
         ["case-732", "대포통장·뮬계좌", "cust_…12", "신규", "높음", "(미배정)", "06-22 ▶"]],
        [0.13, 0.22, 0.17, 0.13, 0.10, 0.13, 0.12])
    wf.callout(s, y, "흐름 · 케이스 발단", [
        "행 클릭 → AML-CASE-002 (케이스 상세 · 타임라인·조치·종결·관계거절)",
        "발단 WLF 확정(AML-WLF-002) · RA 높음(AML-RA-003) · TM 알림(AML-TM-001) · 주기 재심사 · 수동",
        "기한 임박/초과 ⚠ · STR/CTR 필요 시 AML-REP-002 보고 초안 연계(상태 보고)"])
    wf.info_panel(s, "AML-CASE-001", [
        "• 권한 조회 aml:case:read / 생성 aml:case:update",
        "• 탭 내 케이스 / 전체 / 기한 임박 / 종결",
        "• 필터 케이스 타입·상태·우선순위·담당자 + 대상 식별자 · 기한 임박/초과 ⚠",
        "• 컬럼 케이스ID·타입·대상(식별자)·상태·우선·담당·기한",
        "• 타입 제재/요주의 인물/강화된 고객확인/STR/CTR/무역기반/Travel Rule/가맹점·셀러/대포통장/B2B/이커머스 정산/내부통제",
        "• 상태 신규/조사중/승인대기/이상없음/보고/종결 · 우선 낮음/중간/높음/긴급",
        "• 흐름 행 클릭 → AML-CASE-002 (상세·조치·종결)",
        "• 발단 WLF 확정·RA 높음·TM 알림·주기 재심사·수동(발단 식별자 연결)",
        "▸ API GET .../cdd/cases · POST .../cdd/cases"])


CASE_002_TABS = ["타임라인", "CDD/EDD 체크", "관계·UBO", "증빙"]


def case_002(p, tab=0):
    titles = ["케이스 상세 — ① 타임라인 (case-771 강화된 고객확인)",
              "케이스 상세 — ② CDD/EDD 체크 (case-771)",
              "케이스 상세 — ③ 관계·UBO (case-771)",
              "케이스 상세 — ④ 증빙 (case-771)"]
    crumbs = ["AML Console > 케이스 관리 > 케이스 상세 > 타임라인",
              "AML Console > 케이스 관리 > 케이스 상세 > CDD/EDD 체크",
              "AML Console > 케이스 관리 > 케이스 상세 > 관계·UBO",
              "AML Console > 케이스 관리 > 케이스 상세 > 증빙"]
    s = frame(p, "AML-CASE-002", crumbs[tab], titles[tab],
              search="대상 식별자 검색...")
    y = wf.CON_TOP
    y = wf.tab_chips(s, y, CASE_002_TABS, active=tab)
    if tab == 0:
        y = wf.entry_banner(s, y, "AML-CASE-001 케이스 목록에서 [케이스 행 ▶] 클릭 → 케이스 상세")
        y = wf.two_panels(s, y, 1.35,
            ("케이스 개요", ["항목", "값"],
             [["타입", "강화된 고객확인(EDD_REVIEW)"], ["대상(식별자)", "cust_…501"],
              ["상태 / 우선", "조사중 / 높음"], ["담당", "김분석"],
              ["발단", "score-…77 (RA 높음)"]],
             [0.34, 0.66]),
            ("SLA / 종결", ["항목", "값"],
             [["기한", "06-20"], ["경과", "조사 6일차"],
              ["EDD 트리거", "RA 높음·UBO 불명"], ["종결 예정", "—"]],
             [0.40, 0.60]))
        y = wf.table_block(s, y, 1.45, "처리 타임라인 (append-only · 수정 불가)",
            ["시각", "유형", "내용"],
            [["06-05 09:10", "생성", "RA 높음 트리거(AML-RA-003 EDD 착수)"],
             ["06-05 09:30", "배정", "담당 김분석 배정"],
             ["06-06 11:20", "메모", "UBO 지분 구조도 증빙 요청"],
             ["06-06 14:05", "증빙", "소득 증빙 첨부(manifest hash 0x9c…)"]],
            [0.20, 0.14, 0.66])
        wf.callout(s, y, "① 타임라인 — 조치 시나리오 (4-eyes)", [
            "[메모/증빙 추가] [상태·담당·우선 변경] (결재 불필요·timeline append)",
            "[종결 상신(2인·EDD_CLOSE)] → 승인 시 종결 · [STR 보고 연계] → AML-REP-002",
            "[고객 프로필 ▶ → AML-CDD-002] 대상 고객 CDD 프로필 원장 (v7.0) · 다음 → ② CDD/EDD 체크 탭"])
        wf.info_panel(s, "AML-CASE-002", [
            "• 권한 변경·메모 aml:case:update / 종결·관계거절 aml:case:update(2인)",
            "• 진입 AML-CASE-001 행 클릭",
            "• 탭 ① 타임라인 / ② CDD/EDD 체크 / ③ 관계·UBO / ④ 증빙",
            "• 타임라인 생성·배정·메모·증빙(append-only·수정 불가)",
            "• 메모·증빙·상태/담당/우선 변경 결재 불필요",
            "• 케이스 종결 4-eyes(EDD_CLOSE)",
            "• [고객 프로필 ▶ → AML-CDD-002] 드릴다운 (v7.0)",
            "• 다음 → ② CDD/EDD 체크",
            "▸ API GET .../cdd/cases/{id} · PATCH · /timeline"])
    elif tab == 1:
        y = wf.table_block(s, y, 2.30, "CDD/EDD 체크리스트 실행 (AML-CDD-001 정책 기준)",
            ["체크 항목", "필수", "증빙", "상태", "처리자"],
            [["고객확인(신원·실명)", "필수", "신분 증빙", "완료", "김분석"],
             ["실소유자(UBO) 확인", "필수", "지분 구조도", "미완료", "—"],
             ["자금 출처·거래 목적", "필수", "소득·계약 증빙", "진행중", "김분석"],
             ["고위험 국가 거주 확인", "조건부", "거주 증빙", "완료", "김분석"],
             ["거래 모니터링 동의", "필수", "약관 동의", "완료", "시스템"]],
            [0.30, 0.10, 0.22, 0.14, 0.24])
        wf.callout(s, y, "② CDD/EDD 체크 — 미완료 항목은 증빙 요청·메모 처리", [
            "체크 항목 정의·증빙 요건은 AML-CDD-001(체크리스트 정의) 정책 따름",
            "UBO 확인 미완료 → 지분 구조도 증빙 요청(타임라인 메모 추가)",
            "이전 ← ① 타임라인  /  다음 → ③ 관계·UBO"])
        wf.info_panel(s, "AML-CASE-002", [
            "• 권한 체크 상태 변경 aml:case:update",
            "• 탭 ② CDD/EDD 체크",
            "• 컬럼 체크 항목 · 필수 · 증빙 · 상태 · 처리자",
            "• 상태 완료/미완료/진행중",
            "• 체크리스트 정의는 AML-CDD-001 정책 따름",
            "• 이전 ← ① 타임라인  /  다음 → ③ 관계·UBO",
            "▸ API GET .../cdd/cases/{id}/checklist · PATCH (상태 변경)"])
    elif tab == 2:
        y = wf.two_panels(s, y, 1.85,
            ("관계 구조 (연결 상대방)", ["관계 유형", "식별자", "리스크"],
             [["실소유자(UBO)", "cust_…800 (지분 51%)", "높음"],
              ["거래 상대방", "ent_…330 (고위험 corridor)", "중간"],
              ["연결 계좌", "acc_…501 · acc_…502", "—"]],
             [0.34, 0.40, 0.26]),
            ("UBO 확인 현황", ["항목", "값"],
             [["UBO 확인 상태", "미완료"],
              ["지분 구조도", "—  (미제출)"],
              ["UBO 이름", "마스킹(aml:pii:reveal)"],
              ["요청 일자", "06-06 11:20"]],
             [0.42, 0.58]))
        wf.callout(s, y, "③ 관계·UBO — UBO 지분 구조도 미제출 · PII 마스킹", [
            "원문(UBO 이름) 열람 → aml:pii:reveal + 사유 + 감사 로그",
            "관계거절·온보딩 보류 상신(2인·RELATIONSHIP_REJECT) → 승인 시 관계 거절 확정",
            "이전 ← ② CDD/EDD 체크  /  다음 → ④ 증빙"])
        wf.info_panel(s, "AML-CASE-002", [
            "• 권한 조회 aml:case:read / 관계거절 aml:case:update(2인)",
            "• 탭 ③ 관계·UBO",
            "• 관계 유형 UBO · 거래 상대방 · 연결 계좌",
            "• UBO 확인 상태 완료/미완료 · PII 마스킹",
            "• 관계거절·온보딩 보류 4-eyes(RELATIONSHIP_REJECT)",
            "• 이전 ← ② CDD/EDD 체크  /  다음 → ④ 증빙",
            "▸ API GET .../cdd/cases/{id}/relationships · :reject-relationship(2인)"])
    else:  # tab == 3
        y = wf.table_block(s, y, 2.40, "첨부 증빙 목록 (manifest hash 고정 · 변조 불가)",
            ["증빙ID", "유형", "파일명", "첨부일", "manifest hash", ""],
            [["ev-301", "소득 증빙", "income_doc.pdf", "06-06 14:05", "0x9c…", "[다운로드]"],
             ["ev-299", "WLF 근거", "wlf_scr9f3a.pdf", "06-06 10:30", "0xab…", "[다운로드]"],
             ["ev-295", "신분 증빙", "id_doc.pdf", "06-05 10:15", "0x7d…", "[다운로드]"]],
            [0.10, 0.16, 0.22, 0.16, 0.22, 0.14])
        wf.callout(s, y, "④ 증빙 — manifest hash 고정·변조 불가 · [증빙 추가]로 첨부", [
            "[증빙 추가] → 파일 업로드(manifest hash 자동 생성) → 타임라인 append",
            "다운로드 URL 만료 관리 · 원문 접근 감사 자동 기록(aml:pii:reveal)",
            "이전 ← ③ 관계·UBO  (케이스 상세 4탭 끝)"])
        wf.info_panel(s, "AML-CASE-002", [
            "• 권한 증빙 추가·다운로드 aml:case:update / 원문 접근 aml:pii:reveal",
            "• 탭 ④ 증빙",
            "• 컬럼 증빙ID · 유형 · 파일명 · 첨부일 · manifest hash",
            "• manifest hash 고정(업로드 시 생성) · 변조 불가",
            "• 다운로드 만료 URL · 접근 감사 자동 기록",
            "• 이전 ← ③ 관계·UBO  (케이스 상세 4탭 끝)",
            "▸ API GET .../cdd/cases/{id}/evidence · POST (첨부) · GET (다운로드 URL)"])


# ═══ 9. 규제 보고 후보 → 보고 상세/제출 ═════════════════════════
REP_001_TABS = ["STR 후보", "CTR 데이터", "제출 이력"]


def rep_001(p, tab=0):
    titles = ["규제 보고 — ① STR 후보",
              "규제 보고 — ② CTR 데이터",
              "규제 보고 — ③ 제출 이력"]
    crumbs = ["AML Console > 규제 보고 > STR 후보",
              "AML Console > 규제 보고 > CTR 데이터",
              "AML Console > 규제 보고 > 제출 이력"]
    s = frame(p, "AML-REP-001", crumbs[tab], titles[tab],
              search="대상 식별자 검색...", action="+ 보고 초안" if tab == 0 else None)
    y = wf.CON_TOP
    y = wf.tab_chips(s, y, REP_001_TABS, active=tab)
    if tab == 0:
        y = wf.callout(s, y, "정보누설금지 (tipping-off)", [
            "본 화면 정보의 외부 누설은 특정금융정보법 제4조의2 위반 — 준법감시 전담 조회·열람 감사"], h=0.50)
        y = wf.filters(s, y, ["상태 전체", "기간 전체"])
        y = wf.table_block(s, y, 1.85, "STR 후보 목록 [고객사: 은행 A] · 행 ▶ → AML-REP-002 (보고 상세)",
            ["보고ID", "종류", "대상(식별자)", "케이스", "상태", "보고 기한", "발단", "제출 참조"],
            [["rep-220", "STR", "cust_…501", "case-771", "검토중", "D-2 ⚠", "구조화거래 의심", "▶"],
             ["rep-215", "STR", "ent_…77", "case-760", "승인", "D-3 ⚠", "WLF 확정·PEP", "(제출 대기) ▶"],
             ["rep-205", "STR", "cust_…61", "case-701", "제출실패", "초과 ⚠", "TM 고위험", "ERR-FORMAT-12 ▶"],
             ["rep-210", "STR", "cust_…90", "case-732", "초안", "—", "TM escalation", "▶"]],
            [0.10, 0.07, 0.14, 0.11, 0.09, 0.11, 0.19, 0.19])
        wf.callout(s, y, "① STR 후보 — 행 클릭 → AML-REP-002 (보고 상세·제출 4-eyes)", [
            "보고 기한 = 법정 SLA(STR 결재 후 3영업일 · 지체 없이) — D-3 임박/초과 ⚠",
            "기각/취소는 사유 코드 필수 + 보고 책임자 결재(2인·자기승인 금지)",
            "다음 → ② CTR 데이터 탭"])
        wf.info_panel(s, "AML-REP-001", [
            "• 권한 조회 aml:case:read — 준법감시 전담 role 한정(tipping-off)",
            "• 상단 상시 경고 배너 + 열람 감사 · STR 사실 비전담 노출 금지",
            "• 탭 ① STR 후보 / ② CTR 데이터 / ③ 제출 이력",
            "• 컬럼 보고ID·대상·케이스·상태·보고 기한·발단·제출 참조",
            "• 상태 초안/검토중/승인/제출완료/접수/제출실패/반려/취소 (8종)",
            "• 보고 기한 D-3 임박/초과 ⚠ (설계서 §14.4 법정 SLA)",
            "• 기각/취소 사유 코드 필수 + 보고 책임자 4-eyes",
            "• 다음 → ② CTR 데이터",
            "▸ API GET/POST .../reports?type=STR · {reportId}:reject(2인)·:cancel(2인)"])
    elif tab == 1:
        y = wf.filters(s, y, ["기간 전체", "상태 전체"])
        y = wf.kpi_cards(s, y, [
            ("이번달 CTR 대상", "21 건", "1거래 1천만원↑ 현금", "blue"),
            ("접수 완료", "18 건", "FIU 접수번호 수신", "green"),
            ("제출 대기", "3 건", "기한 임박 1 ⚠ (D+30)", "orange"),
            ("CTR 기준", "1천만원", "1거래 현금 · 정책팩 정본", "red")])
        y = wf.table_block(s, y, 1.85, "CTR 데이터 [고객사: 은행 A] · [제외 처리(2인)] — 법정 제외대상",
            ["보고ID", "대상(식별자)", "거래금액", "거래일", "보고 기한", "상태", "제출 참조 / 제외 사유"],
            [["rep-218", "cust_…12", "2,500만원", "06-05", "07-05", "접수", "FIU-2026-000218"],
             ["rep-217", "cust_…45", "1,200만원", "06-06", "07-06", "제출 대기", "▶"],
             ["rep-216", "ent_…80", "5,000만원", "06-06", "07-06", "검토중", "▶"],
             ["rep-214", "ent_…30", "3,000만원", "06-04", "—", "제외(취소)", "금융회사 간 거래"]],
            [0.11, 0.14, 0.12, 0.09, 0.11, 0.13, 0.30])
        wf.callout(s, y, "② CTR 데이터 — 기준: 1거래 1천만원 이상 현금거래(정책팩 정본 기준)", [
            "[제외 처리(2인)] 사유 코드 ▼(국가·지자체/금융회사 간/기타 법정 제외) 필수 + 책임자 승인",
            "제외 이력(사유 코드·증적·처리자·승인자) 표시 · 감사 보존 · 보고 기한 = 거래일+30일",
            "이전 ← ① STR 후보  /  다음 → ③ 제출 이력"])
        wf.info_panel(s, "AML-REP-001", [
            "• 권한 조회 aml:case:read(전담) / 제외 처리 2인(보고 책임자)",
            "• 탭 ② CTR 데이터",
            "• CTR 기준 1거래 1천만원 이상 현금거래(정책팩 정본·AML-PP-001)",
            "• 컬럼 보고ID·대상·거래금액·거래일·보고 기한·상태·제출 참조/제외 사유",
            "• [제외 처리] 법정 제외대상 — 사유 코드 필수 + 4-eyes · 제외 이력·감사",
            "• 보고 기한 거래일+30일 · D-3 임박 ⚠",
            "• 이전 ← ① STR 후보  /  다음 → ③ 제출 이력",
            "▸ API GET .../reports?type=CTR"])
    else:  # tab == 2
        y = wf.filters(s, y, ["보고 종류 전체", "상태 전체", "기간 전체"])
        y = wf.table_block(s, y, 2.55, "제출 이력 — FIU 회신 폐루프 (접수/제출실패·재제출 추적)",
            ["보고ID", "종류", "제출일", "FIU 접수번호", "오류코드", "재제출", "상태"],
            [["rep-218", "CTR", "06-05 14:30", "FIU-2026-000218", "—", "0", "접수"],
             ["rep-200", "STR", "06-01 10:15", "FIU-2026-000200", "—", "0", "접수"],
             ["rep-205", "STR", "05-30 09:20", "—", "ERR-FORMAT-12", "1", "제출실패 ▶"],
             ["rep-195", "CTR", "05-28 09:00", "FIU-2026-000195", "—", "1", "접수"]],
            [0.11, 0.09, 0.17, 0.22, 0.17, 0.10, 0.14])
        wf.callout(s, y, "③ 제출 이력 — FIU 회신으로 종결(접수) 또는 정정 후 재제출", [
            "제출완료(전송·회신 대기) → 접수(FIU 접수번호 저장·종단) / 제출실패(오류코드 저장)",
            "제출실패 → [정정 후 재제출](보고 상세 AML-REP-002 ③ · 기존 제출 4-eyes 재사용)",
            "이전 ← ② CTR 데이터  (규제 보고 3탭 끝)"])
        wf.info_panel(s, "AML-REP-001", [
            "• 권한 조회 aml:case:read(전담)",
            "• 탭 ③ 제출 이력 — FIU 회신 폐루프",
            "• 컬럼 보고ID·종류·제출일·FIU 접수번호·오류코드·재제출·상태",
            "• 상태 제출완료(회신 대기)/접수(종단)/제출실패(재제출 대상)",
            "• 재제출 횟수·회차별 이력 보존(resubmitCount)",
            "• 제출실패 행 ▶ → AML-REP-002 ③ [정정 후 재제출]",
            "• 이전 ← ② CTR 데이터  (규제 보고 3탭 끝)",
            "▸ API GET .../reports?status=SUBMITTED,ACKNOWLEDGED,SUBMISSION_FAILED"])


REP_002_TABS = ["보고 본문", "첨부 증빙", "제출 이력"]


def rep_002(p, tab=0):
    titles = ["보고 상세 — ① 보고 본문 (rep-220 STR)",
              "보고 상세 — ② 첨부 증빙 (rep-220 STR)",
              "보고 상세 — ③ 제출 이력 (rep-220 STR)"]
    crumbs = ["AML Console > 규제 보고 > 보고 상세 > 보고 본문",
              "AML Console > 규제 보고 > 보고 상세 > 첨부 증빙",
              "AML Console > 규제 보고 > 보고 상세 > 제출 이력"]
    s = frame(p, "AML-REP-002", crumbs[tab], titles[tab],
              search="대상 식별자 검색...")
    y = wf.CON_TOP
    y = wf.tab_chips(s, y, REP_002_TABS, active=tab)
    if tab == 0:
        y = wf.entry_banner(s, y, "AML-REP-001에서 [보고 후보 행 ▶] 클릭 → 보고 상세·제출")
        y = wf.callout(s, y, "정보누설금지 (tipping-off)", [
            "본 화면 정보의 외부 누설은 특정금융정보법 제4조의2 위반 — 전담 조회·열람 감사"], h=0.50)
        y = wf.two_panels(s, y, 2.05,
            ("보고 개요", ["항목", "값"],
             [["보고ID / 종류", "rep-220 / STR"], ["대상(식별자)", "cust_…501"],
              ["연관 케이스", "case-771"], ["상태", "검토중(UNDER_REVIEW)"],
              ["발생", "구조화거래 의심"],
              ["의심유형 코드", "102 자금출처 불분명 외 1 ▼"]],
             [0.38, 0.62]),
            ("증빙 manifest", ["항목", "값"],
             [["첨부 증빙", "3건(거래내역·WLF·EDD)"], ["manifest hash", "0xab…(고정)"],
              ["본문 PII", "hash/token 보존"], ["제출 어댑터", "고객사별(D-04)"]],
             [0.42, 0.58]))
        y = wf.table_block(s, y, 1.10, "보고 본문 (요약 · PII는 hash/token)",
            ["항목", "내용"],
            [["의심 거래 요약", "최근 7일 9건 분할 입금 합계 9,500만원(보고 기준 회피 의심)"],
             ["WLF·RA 근거", "제재 명단 유사도 0.92(scr-9f3a) · 위험 등급 높음(88점)·고위험국가·UBO 불명"]],
            [0.26, 0.74])
        wf.callout(s, y, "① 보고 본문 — 편집(초안 결재 불필요) · 제출 4-eyes", [
            "[본문 편집(초안)] · [제출 상신(2인·보고 책임자)] · [기각(사유 코드·2인)] · 다음 → ② 첨부 증빙 탭"])
        wf.info_panel(s, "AML-REP-002", [
            "• 권한 초안 편집 aml:case:update / 제출 aml:case:update(2인·보고 책임자)",
            "• 조회 준법감시 전담 role 한정(tipping-off) · 상시 경고 배너·열람 감사",
            "• 진입 AML-REP-001 행 클릭",
            "• 탭 ① 보고 본문 / ② 첨부 증빙 / ③ 제출 이력",
            "• 본문 의심 거래 요약·WLF 근거·RA 근거 (PII hash/token)",
            "• 의심유형 코드 — KoFIU 분류(KR 정책팩 코드표) 복수 선택, 시나리오별 기본값 자동 제안+수동 보정(벤치마크 보강)",
            "• 초안 편집 결재 불필요 / 제출 4-eyes(STR_SUBMIT) / 기각 사유 코드+2인",
            "• 다음 → ② 첨부 증빙",
            "▸ API GET .../reports/{id} · PATCH (본문 편집) · {id}:reject(2인)·:cancel(2인)"])
    elif tab == 1:
        y = wf.table_block(s, y, 2.30, "첨부 증빙 목록 (manifest hash 고정 · 변조 불가)",
            ["증빙ID", "유형", "파일명", "첨부일", "manifest hash", ""],
            [["ev-301", "거래내역", "txn_hist.pdf", "06-06 14:05", "0x9c…", "[다운로드]"],
             ["ev-299", "WLF 근거", "wlf_scr9f3a.pdf", "06-06 10:30", "0xab…", "[다운로드]"],
             ["ev-295", "EDD 결과", "edd_report.pdf", "06-05 10:15", "0x7d…", "[다운로드]"]],
            [0.10, 0.16, 0.22, 0.16, 0.22, 0.14])
        wf.callout(s, y, "② 첨부 증빙 — [증빙 추가] · manifest hash 자동 생성", [
            "[증빙 추가] → 파일 업로드 → manifest hash 자동 생성(변조 불가)",
            "다운로드 만료 URL · 접근 감사 자동 기록",
            "이전 ← ① 보고 본문  /  다음 → ③ 제출 이력"])
        wf.info_panel(s, "AML-REP-002", [
            "• 권한 증빙 추가 aml:case:update / 다운로드 aml:evidence:export",
            "• 탭 ② 첨부 증빙",
            "• 컬럼 증빙ID · 유형 · 파일명 · 첨부일 · manifest hash",
            "• manifest hash 고정·변조 불가 · 만료 URL",
            "• 이전 ← ① 보고 본문  /  다음 → ③ 제출 이력",
            "▸ API GET .../reports/{id}/evidence · POST"])
    else:  # tab == 2
        y = wf.two_panels(s, y, 1.80,
            ("제출 정보 (FIU 회신 폐루프)", ["항목", "값"],
             [["상태", "제출실패(SUBMISSION_FAILED)"],
              ["FIU 접수번호", "— (접수 시 저장)"],
              ["오류코드", "ERR-FORMAT-12 (FIU 반려)"],
              ["재제출 횟수", "1 회 (이력 보존)"],
              ["제출 어댑터", "고객사별(D-04)"]],
             [0.40, 0.60]),
            ("제출 시나리오", ["동작", "결과"],
             [["[제출 상신(2인)]", "승인 → 외부 전송(회신 대기)"],
              ["FIU 접수", "접수 확정 · 접수번호 저장(종단)"],
              ["전송 실패·반려", "제출실패 · 오류코드 저장"],
              ["[정정 후 재제출(2인)]", "제출실패에서만 · 4-eyes 재사용"]],
             [0.40, 0.60]))
        y = wf.table_block(s, y, 1.45, "회차별 제출·회신 이력 (재제출 추적)",
            ["회차", "제출일", "상태", "FIU 접수번호", "오류코드"],
            [["2차", "(정정 후 재제출 대기)", "검토중 복귀", "—", "—"],
             ["1차", "05-30 09:20", "제출실패", "—", "ERR-FORMAT-12"]],
            [0.10, 0.26, 0.20, 0.24, 0.20])
        wf.callout(s, y, "③ 제출 이력 — [정정 후 재제출]은 제출실패 상태에서만 노출", [
            "정정(검토중 복귀) → [제출 상신(2인·보고 책임자)] 기존 결재 절차 그대로 재사용 · 재제출 횟수 증가",
            "접수 확정 시 FIU 접수번호·manifest hash 증적 저장 · 케이스 상태 보고(REPORTED)",
            "이전 ← ② 첨부 증빙  (보고 상세 3탭 끝)"])
        wf.info_panel(s, "AML-REP-002", [
            "• 권한 제출·재제출 aml:case:update (2인·보고 책임자)",
            "• 탭 ③ 제출 이력 — FIU 회신 폐루프",
            "• 제출 4-eyes(STR_SUBMIT·CTR_SUBMIT) maker≠checker",
            "• 회신 접수(FIU 접수번호·종단) / 제출실패(오류코드)",
            "• [정정 후 재제출] 제출실패에서만 · 기존 4-eyes 재사용",
            "• 재제출 횟수·회차별 이력 보존 · 케이스 보고(REPORTED) 연동",
            "• 이전 ← ② 첨부 증빙  (보고 상세 3탭 끝)",
            "▸ API POST .../reports/{id}:submit(2인·재제출 동일) · GET (이력)"])


# ─── AML-IRA-001 기관 위험평가(ML/TF) 지표 보고 (v6.0 벤치마크 보강, 3탭) ───
IRA_001_TABS = ["보고 회차·지표 등록", "결과·제출 결재", "보고 현황(FIU 회신)"]


def ira_001(p, tab=0):
    titles = ["기관 위험평가 지표 보고 — ① 보고 회차·지표 등록",
              "기관 위험평가 지표 보고 — ② 결과·제출 결재",
              "기관 위험평가 지표 보고 — ③ 보고 현황(FIU 회신)"]
    crumbs = ["AML Console > 기관 RBA 보고 > 보고 회차·지표 등록",
              "AML Console > 기관 RBA 보고 > 결과·제출 결재",
              "AML Console > 기관 RBA 보고 > 보고 현황"]
    s = frame(p, "AML-IRA-001", crumbs[tab], titles[tab], search="지표 검색...",
              action="+ 보고 회차" if tab == 0 else None)
    y = wf.CON_TOP
    y = wf.tab_chips(s, y, IRA_001_TABS, active=tab)
    if tab == 0:
        y = wf.callout(s, y, "보고 회차 — KR 확장 plugin 전용 (정책팩 KR_DEFAULT 위 활성화 고객사만 노출)", [
            "회차: 보고 기준일 2027-03-01 · 데이터 기준월 2026-12 (자동지표 산출 배치 수행 후 잠금)",
            "진행: 확정 87 / 전체 152 지표  ·  입력 원천 = 자동 수집 / 직전 보고값 복사 / 수기(증빙 필수)"])
        y = wf.filters(s, y, ["위험구분 전체", "카테고리 전체", "입력방식 전체", "항목상태 전체"])
        y = wf.table_block(s, y, 2.05, "지표 등록 [회차 2027-03-01] (인라인 편집 · 확정/취소)",
            ["지표번호", "위험구분", "지표명", "배점", "입력방식", "직전값", "입력값", "증빙", "상태"],
            [["I.1.01.01", "고유위험", "고위험 국가 고객 수", "2.0", "자동", "1,180", "1,204", "—", "확정"],
             ["I.1.02.03", "고유위험", "비거주자 고객 비율", "2.0", "자동", "3.1%", "3.4%", "—", "확정"],
             ["O.2.01.02", "운영위험", "AML 교육 이수율", "1.5", "자동(EDU)", "91%", "94%", "—", "미확정"],
             ["O.2.03.01", "운영위험", "전담 인력 자격 보유 수", "1.0", "수기", "8", "9 [입력]", "[첨부]", "미확정"]],
            [0.11, 0.10, 0.25, 0.07, 0.12, 0.10, 0.11, 0.07, 0.07])
        wf.callout(s, y, "① 등록 — [자동 가져오기] [직전보고 가져오기] [확정/취소]", [
            "다음 → ② 결과·제출 결재 탭"])
        wf.info_panel(s, "AML-IRA-001", [
            "• 권한 aml:admin:policy / 조회 aml:case:read",
            "• 탭 ① 회차·지표 등록 / ② 결과·제출 결재 / ③ 보고 현황",
            "• 회차 보고 기준일·데이터 기준월 — 배치 수행 후 기준월 잠금",
            "• 지표 152종 — 위험구분(고유/운영)·카테고리·배점·입력방식(자동/수동)",
            "• 입력 원천 자동 수집(케이스·WLF·RA·EDU 집계) / 직전값 / 수기(증빙 필수)",
            "• 진행 카운터 확정 n / 전체 N · 확정 후 변경 시 재확정 필요",
            "• 지표 마스터 = KR plugin 정책 store(versioned · 고시 개정 시 갱신)",
            "• 다음 → ② 결과·제출 결재",
            "▸ API GET/POST .../ira/reports · PUT .../indicators (제안 · 후속 정합)"])
    elif tab == 1:
        y = wf.kpi_cards(s, y, [
            ("고유위험 점수", "62.4", "배점 합산", "blue"),
            ("운영위험 점수", "28.1", "배점 합산", "orange"),
            ("확정 지표", "152/152", "전수 확정", "green"),
            ("결재 상태", "대기", "보고 책임자(2인)", "red")])
        y = wf.table_block(s, y, 1.55, "결과 집계·제출 결재 (4-eyes · 보고 책임자)",
            ["항목", "값", "동작"],
            [["보고파일", "ira_2027-03-01.xml (manifest hash 0x4e…)", "[보고파일 생성]"],
             ["첨부 증빙", "12건 (수기 지표 증빙)", "[첨부 관리]"],
             ["제출 결재", "상신 → 승인(maker≠checker) → 제출", "[제출 상신(2인)]"]],
            [0.22, 0.50, 0.28])
        wf.callout(s, y, "② 결재 — subjectType=IRA_SUBMIT(제안) · 회차·지표값·증빙·결재 감사 5년 보존", [
            "확정 후 입력값 변경 시 확정 해제 + 재확정 (payload_hash 고정 원칙 준용)",
            "이전 ← ① 회차·지표 등록  /  다음 → ③ 보고 현황"])
        wf.info_panel(s, "AML-IRA-001", [
            "• 권한 제출 2인(보고 책임자) — subjectType=IRA_SUBMIT(제안)",
            "• 탭 ② 결과·제출 결재",
            "• 카드 고유위험·운영위험 점수 / 확정 지표 / 결재 상태",
            "• 보고파일 생성 — manifest hash 고정 · 첨부 증빙 관리",
            "• 확정 변경 시 재확정 · 전 과정 감사 보존(5년)",
            "• 이전 ← ① 등록  /  다음 → ③ 보고 현황",
            "▸ API POST .../ira/reports/{id}:submit (제안 · 2인)"])
    else:  # tab == 2
        y = wf.filters(s, y, ["위험구분 전체", "카테고리 전체"])
        y = wf.table_block(s, y, 2.15, "FIU 회신 — 최근 3회차 점수·peer 비교",
            ["지표번호", "지표명", "최근 점수", "peer 평균", "순위", "직전", "변동"],
            [["I.1.01.01", "고위험 국가 고객 수", "1.6", "1.4", "12/38", "1.4", "+0.2"],
             ["I.1.02.03", "비거주자 고객 비율", "1.2", "1.3", "20/38", "1.3", "-0.1"],
             ["O.2.01.02", "AML 교육 이수율", "1.5", "1.1", "5/38", "1.4", "+0.1"]],
            [0.12, 0.28, 0.12, 0.13, 0.11, 0.11, 0.13])
        wf.callout(s, y, "③ 보고 현황 — FIU 회신 점수·동료그룹(peer) 평균·최근 3회차 추이", [
            "지표 행 클릭 → 회차별 점수 추이 비교(읽기 전용)",
            "이전 ← ② 결과·제출 결재  (기관 RBA 보고 3탭 끝)"])
        wf.info_panel(s, "AML-IRA-001", [
            "• 권한 조회 aml:case:read",
            "• 탭 ③ 보고 현황(FIU 회신)",
            "• 컬럼 지표번호·지표명·최근 점수·peer 평균·순위·직전·변동",
            "• FIU 회신 점수·peer 그룹 평균·최근 3회차 추이 비교",
            "• read-only — 차기 회차 개선 계획 입력 근거",
            "• 이전 ← ② 결과·제출 결재  (3탭 끝)",
            "▸ API GET .../ira/reports/{id}/feedback (제안 · 후속 정합)"])


# ═══ 10. Travel Rule 이전 / 예외 처리 ═══════════════════════════
TR_001_TABS = ["예외 큐", "전체 이전", "처리 이력"]


def tr_001(p, tab=0):
    titles = ["Travel Rule 이전 — ① 예외 큐",
              "Travel Rule 이전 — ② 전체 이전",
              "Travel Rule 이전 — ③ 처리 이력"]
    crumbs = ["AML Console > Travel Rule > 예외 큐",
              "AML Console > Travel Rule > 전체 이전",
              "AML Console > Travel Rule > 처리 이력"]
    s = frame(p, "AML-TR-001", crumbs[tab], titles[tab], search="이전 식별자 검색...")
    y = wf.CON_TOP
    y = wf.tab_chips(s, y, TR_001_TABS, active=tab)
    if tab == 0:
        y = wf.filters(s, y, ["완전성 전체", "위험 전체", "기간 전체", "고객사 거래소 C"])
        y = wf.table_block(s, y, 2.00, "예외 큐 (정보 누락·위험 지갑) [고객사: 거래소 C]",
            ["이전ID", "송신VASP", "수취VASP", "자산", "완전성", "위험", "동작"],
            [["tr-9001", "VASP_A", "VASP_B", "BTC", "정보누락", "—", "[예외처리]"],
             ["tr-8990", "VASP_A", "(미확인)", "ETH", "정보누락", "위험지갑", "[예외처리]"]],
            [0.13, 0.15, 0.15, 0.10, 0.14, 0.14, 0.19])
        wf.callout(s, y, "① 예외 큐 — tr-8990 예외 처리 시나리오 (4-eyes · TRAVEL_RULE_EXCEPTION)", [
            "수취 VASP 정보 미확인 · 수취 지갑주소(hash) 위험 명단(가상자산위험) 매칭",
            "처리 [추가확인 요청 ▼](추가확인/보류/반송/케이스 생성) 사유 [______]",
            "[예외 처리 확정 상신(2인)] → 승인(maker≠checker) → 확정(EXECUTED)",
            "다음 → ② 전체 이전"])
        wf.info_panel(s, "AML-TR-001", [
            "• 권한 조회 aml:case:read / 예외 확정 aml:case:update(2인)",
            "• 탭 ① 예외 큐 / ② 전체 이전 / ③ 처리 이력",
            "• 필터 완전성·위험·기간 + 이전 식별자",
            "• 컬럼 이전ID·송신VASP·수취VASP·자산·완전성·위험·동작",
            "• 예외 처리 4-eyes(TRAVEL_RULE_EXCEPTION)",
            "• 다음 → ② 전체 이전",
            "▸ API GET .../travel-rule/transfers?status=EXCEPTION"])
    elif tab == 1:
        y = wf.filters(s, y, ["완전성 전체", "기간 전체", "자산 전체"])
        y = wf.table_block(s, y, 2.55, "전체 이전 [고객사: 거래소 C] · 대상=마스킹",
            ["이전ID", "송신VASP", "수취VASP", "자산", "금액", "완전성", "처리"],
            [["tr-9005", "VASP_A", "VASP_D", "BTC", "0.5 BTC", "완전", "완료"],
             ["tr-9003", "VASP_B", "VASP_A", "USDT", "10,000", "완전", "완료"],
             ["tr-9001", "VASP_A", "VASP_B", "BTC", "1.2 BTC", "정보누락", "예외처리중"],
             ["tr-8990", "VASP_A", "(미확인)", "ETH", "5.0 ETH", "정보누락", "예외처리중"],
             ["tr-8977", "VASP_A", "VASP_C", "USDT", "50,000", "완전", "완료"]],
            [0.13, 0.14, 0.14, 0.10, 0.14, 0.14, 0.21])
        wf.callout(s, y, "② 전체 이전 — 완전/예외처리중 포함 전체 이전 이력", [
            "완전성 완전 / 정보 누락 · 위험 지갑·제재 지갑 매칭(지갑주소 hash)",
            "이전 ← ① 예외 큐  /  다음 → ③ 처리 이력"])
        wf.info_panel(s, "AML-TR-001", [
            "• 권한 조회 aml:case:read",
            "• 탭 ② 전체 이전",
            "• 필터 완전성 / 기간 / 자산",
            "• 컬럼 이전ID·송신VASP·수취VASP·자산·금액·완전성·처리 상태",
            "• 정보 hash/token만 표시 (원문 PII 미노출)",
            "• 이전 ← ① 예외 큐  /  다음 → ③ 처리 이력",
            "▸ API GET .../travel-rule/transfers (전체)"])
    else:  # tab == 2
        y = wf.filters(s, y, ["처리 유형 전체", "기간 전체"])
        y = wf.table_block(s, y, 2.40, "처리 이력 (4-eyes 증적 · TRAVEL_RULE_EXCEPTION)",
            ["이전ID", "처리 유형", "처리 결과", "상신자/승인자", "처리일"],
            [["tr-8900", "추가확인 요청", "추가 정보 수령 → 완전 처리", "박심사/이감리", "06-05 14:20"],
             ["tr-8850", "케이스 생성", "AML-CASE-002(TR 검토) 생성", "김분석/이감리", "06-04 11:30"],
             ["tr-8800", "보류", "수취 VASP 응답 대기 중", "박심사/이감리", "06-03 10:00"]],
            [0.12, 0.20, 0.36, 0.18, 0.14])
        wf.callout(s, y, "③ 처리 이력 — 4-eyes 예외 처리 증적 · 케이스 연결", [
            "케이스 생성 → AML-CASE-002(Travel Rule 검토) / 보고 필요 → AML-REP-002",
            "이전 ← ② 전체 이전  (Travel Rule 3탭 끝)"])
        wf.info_panel(s, "AML-TR-001", [
            "• 권한 조회 aml:case:read",
            "• 탭 ③ 처리 이력",
            "• 컬럼 이전ID · 처리 유형 · 처리 결과 · 상신자/승인자 · 처리일",
            "• 처리 유형 추가확인 요청/보류/반송/케이스 생성",
            "• 모든 처리 4-eyes 증적 감사 보존",
            "• 이전 ← ② 전체 이전  (Travel Rule 3탭 끝)",
            "▸ API GET .../travel-rule/transfers/exceptions/history"])


# ═══ 11. Policy Pack 관리 ═══════════════════════════════════════
PP_001_TABS = ["적용 팩 / 기준금액", "변경 상신·이력"]


def pp_001(p, tab=0):
    titles = ["Policy Pack 관리 — ① 적용 팩 / 기준금액",
              "Policy Pack 관리 — ② 변경 상신·이력"]
    crumbs = ["AML Console > Policy Pack > 적용 팩 / 기준금액",
              "AML Console > Policy Pack > 변경 상신·이력"]
    s = frame(p, "AML-PP-001", crumbs[tab], titles[tab],
              action="+ 변경 상신" if tab == 0 else None)
    y = wf.CON_TOP
    y = wf.tab_chips(s, y, PP_001_TABS, active=tab)
    if tab == 0:
        y = wf.two_panels(s, y, 1.55,
            ("적용 Policy Pack [고객사: 은행 A]", ["항목", "값"],
             [["기본 팩(필수·잠금)", "한국 기본팩(KR_DEFAULT) ●"],
              ["effective 버전", "v12 (2026-05-01)"],
              ["국가·업권 확장 plugin", "○ 없음 (토글 추가)"],
              ["적용 시점", "2026-05-01"]],
             [0.46, 0.54]),
            ("보고 기준금액 (effective)", ["기준", "값"],
             [["CTR 고액현금거래", "1거래 1천만원↑ 현금(정본)"], ["STR 보고 기준", "의심 시"],
              ["Travel Rule 기준", "100만원 상당 이상"], ["분할 의심 임계", "9,000만원/7일"]],
             [0.56, 0.44]))
        y = wf.table_block(s, y, 1.58, "기본 팩(KR_DEFAULT) 영역별 기본 반영 — 필수 baseline 일괄 적용(개별 토글 아님)",
            ["영역", "기본 반영 기준"],
            [["CDD", "고객확인·실소유자·자금출처/거래목적"],
             ["STR / CTR", "의심거래 후보·보고 / 고액현금거래 수집·검증"],
             ["Sanctions·PEP·RCA / VASP", "명단 필터링·정치인(PEP/RCA) 관리 / Travel Rule·지갑 risk"],
             ["RA 임계 / Privacy·Audit", "고위험 0.75↑ → EDD 트리거 / 최소수집·append-only 증적 보존"]],
            [0.26, 0.74])
        wf.callout(s, y, "① 적용 팩 / 기준금액 — 기본 번들(잠금) + 확장 plugin(토글), 변경은 ② 탭 4-eyes", [
            "KR_DEFAULT는 AML 최소 요건 일괄 적용(개별 영역 토글 불가) · 국가·업권 확장은 plugin 토글로 추가",
            "CTR/STR/Travel Rule 기준금액(파라미터)은 AML-REP-001/002·AML-TM-002에 연동 · 다음 → ② 변경 상신·이력"])
        wf.info_panel(s, "AML-PP-001", [
            "• 권한 조회·변경 상신 aml:admin:policy",
            "• 탭 ① 적용 팩 / 기준금액 · ② 변경 상신·이력",
            "• 적용 팩 한국 기본팩(KR_DEFAULT) + 국가·업권 확장 plugin",
            "• 보고 기준금액 CTR·STR·Travel Rule·분할 의심 임계(effective)",
            "• 영역 CDD/STR/CTR/Sanctions/PEP/VASP/Privacy/Audit",
            "• 다음 → ② 변경 상신·이력",
            "▸ API GET /api/v1/bo/aml/tenants/{tenantId} (policyPackCode 파생) · POST .../policy-packs:change(2인)"])
    else:  # tab == 1
        y = wf.callout(s, y, "② 변경 시나리오 (4-eyes · subjectType=POLICY_PACK)", [
            "변경 [기준금액 조정 / jurisdiction 확장 추가 ▼]  예: CTR 1,000→ effective 갱신  사유 [고시 개정 ▼]",
            "[정책팩 변경 상신(2인·준법감시 책임자)] → 승인 → tenant policy pack effective version 갱신(EXECUTED)",
            "법령·감독규정 변경 가능성으로 effective version 관리 · 국가별 확장은 별도 jurisdiction plugin"])
        y = wf.table_block(s, y, 2.10, "변경 상신 이력 (4-eyes 증적 · POLICY_PACK)",
            ["결재ID", "변경 내용", "상신자", "상태", "처리일"],
            [["apr-490", "CTR 기준금액 800만원 → 1천만원 (고시 개정)", "이감리", "승인", "2026-04-01"],
             ["apr-455", "분할 의심 임계 1억원/7일 → 9,000만원/7일", "이감리", "승인", "2026-01-15"],
             ["apr-380", "Travel Rule 기준 150만원 → 100만원", "박심사", "승인", "2025-07-01"]],
            [0.12, 0.42, 0.14, 0.12, 0.20])
        wf.info_panel(s, "AML-PP-001", [
            "• 권한 변경 상신 aml:admin:policy (2인·준법감시 책임자)",
            "• 탭 ② 변경 상신·이력",
            "• 변경 4-eyes(POLICY_PACK) 상신→승인→effective 갱신",
            "• 이력 컬럼 결재ID · 변경 내용 · 상신자 · 상태 · 처리일",
            "• effective version 관리(법령·감독규정 변경 대응)",
            "• 이전 ← ① 적용 팩 / 기준금액  (Policy Pack 2탭 끝)",
            "▸ API POST .../policy-packs:change(2인·POLICY_PACK) · GET .../approvals?subjectType=POLICY_PACK (이력)"])


# ═══ 12. 결재 대기함 → 결재 상세 ════════════════════════════════
def apr_001(p):
    s = frame(p, "AML-APR-001", "AML Console > 결재 대기함",
              "결재 대기함 / 승인·반려", search="상신자·대상 검색...")
    y = wf.CON_TOP
    y = wf.tab_chips(s, y, ["대기", "내가 상신", "처리 완료"], active=0)
    y = wf.filters(s, y, ["결재 종류 전체", "결재 라인 전체", "기간 전체"])
    y = wf.table_block(s, y, 2.35, "결재 대기 [고객사: 은행 A]",
        ["결재ID", "결재 종류", "대상", "결재 라인", "상신자", "만료"],
        [["apr-551", "WLF 판정 확정", "scr-9f3a", "Maker-Checker", "김분석", "2h ⚠ ▶"],
         ["apr-549", "STR 제출", "rep-215", "보고 책임자", "박심사", "1d ▶"],
         ["apr-544", "RA 모델 활성화", "RA-KR v5", "준법감시 책임자", "이감리", "3d ▶"],
         ["apr-541", "국가위험 변경", "country v8", "준법감시 책임자", "이감리", "2d ▶"],
         ["apr-540", "명단 import 적용", "OFAC v142", "Maker-Checker", "김분석", "6h ▶"]],
        [0.12, 0.21, 0.15, 0.22, 0.14, 0.16])
    wf.callout(s, y, "흐름 · 결재 상세 (행 클릭) — 결재 종류 총 16종", [
        "행 클릭 → 결재 상세 (대상 payload·사유·payload_hash 잠금 확인) · [승인] [반려](사유)",
        "결재 종류 WLF 판정(WLF_DECISION)/오탐 면제(FP_WHITELIST)/RA 모델(RA_MODEL)/등급 조정(RISK_OVERRIDE)/EDD 종결(EDD_CLOSE)/관계거절(RELATIONSHIP_REJECT)",
        "STR 제출(STR_SUBMIT)/CTR 제출(CTR_SUBMIT)/Travel Rule 예외(TRAVEL_RULE_EXCEPTION)/명단 import(WATCHLIST_IMPORT)/국가위험(COUNTRY_RISK)/정책팩(POLICY_PACK)/secret 변경(SECRET_CHANGE)/체크리스트 변경(CHECKLIST_CHANGE)/재심사 주기 변경(PERIODIC_REVIEW_CHANGE)/TM 시나리오(TM_SCENARIO)",
        "상신자와 동일인은 승인 불가(maker≠checker) · 결재 승인 ≠ 실행(승인 후 엔진 실행·결과·시각 표기)"])
    wf.info_panel(s, "AML-APR-001", [
        "• 권한 조회·승인·반려 aml:admin:approval (maker≠checker 강제)",
        "• 탭 대기(SUBMITTED) / 내가 상신 / 처리 완료",
        "• 필터 결재 종류·결재 라인·기간 + 상신자/대상 · 만료 임박 ⚠",
        "• 컬럼 결재ID·결재 종류·대상·결재 라인·상신자·만료",
        "• 결재 종류 총 16종: WLF 판정·오탐 면제·RA 모델·등급 조정·EDD 종결·관계거절·STR 제출(STR_SUBMIT)·CTR 제출(CTR_SUBMIT)·Travel Rule 예외·명단 import·국가위험·정책팩·secret 변경·체크리스트 변경(CHECKLIST_CHANGE)·재심사 주기 변경(PERIODIC_REVIEW_CHANGE)·TM 시나리오(TM_SCENARIO)",
        "• 결재 라인 Maker-Checker/AML 책임자/준법감시 책임자/보고 책임자/보안 관리자/임원",
        "• 흐름 행 클릭 → 결재 상세(payload_hash 잠금 확인·승인/반려)",
        "• 승인 maker≠checker 강제 · 자기 승인 차단(AML.SELF_APPROVAL_FORBIDDEN)",
        "• payload_hash 고정 · 변경 시 무효화(재상신) · 결재 승인 ≠ 실행(분리)",
        "• 만료·취소는 미실행 · AI agent 상신·초안만(승인자 불가)",
        "▸ API GET .../approvals?status=SUBMITTED · {id}:approve · {id}:reject"])


# ─── AML-STAT-001 STR·룰 효과성 통계 (v6.0 벤치마크 보강, 2탭) ───
STAT_001_TABS = ["STR 보고 현황 통계", "룰 효과성"]


def stat_001(p, tab=0):
    titles = ["STR·룰 효과성 통계 — ① STR 보고 현황 통계",
              "STR·룰 효과성 통계 — ② 룰 효과성"]
    crumbs = ["AML Console > 통계·내부통제 > STR 보고 현황 통계",
              "AML Console > 통계·내부통제 > 룰 효과성"]
    s = frame(p, "AML-STAT-001", crumbs[tab], titles[tab], search="시나리오 검색...")
    y = wf.CON_TOP
    y = wf.tab_chips(s, y, STAT_001_TABS, active=tab)
    if tab == 0:
        y = wf.filters(s, y, ["기간 최근 90일", "보고 종류 전체"])
        y = wf.kpi_cards(s, y, [
            ("추출(후보)", "112 건", "기간 내", "blue"),
            ("검토 완료", "98 건", "87.5%", "green"),
            ("결재 완료", "41 건", "보고 책임자", "orange"),
            ("제출 완료", "38 건", "접수 35 · 실패 1", "green"),
            ("지연 보고", "2 건", "법정 SLA 초과 ⚠", "red")])
        y = wf.two_panels(s, y, 1.85,
            ("지연 보고 일수 분포 (법정 SLA 대비)", ["구간", "건수"],
             [["기한 내 (D-3 이전)", "31"], ["임박 (D-3~D-1)", "5"],
              ["당일 (D-day)", "2"], ["초과 ⚠", "2"]],
             [0.62, 0.38]),
            ("미보고(기각·취소) 사유 분포", ["사유 코드", "건수"],
             [["오탐 확정", "38"], ["중복 보고", "9"],
              ["CTR 법정 제외", "7"], ["기타(사유 기재)", "3"]],
             [0.62, 0.38]))
        wf.callout(s, y, "① STR 통계 — 준법감시 전담 role 한정(tipping-off) · read-only 집계", [
            "개별 건 드릴다운 → AML-REP-001 · 지연 보고 일수=법정 SLA(STR 3영업일·CTR 30일) 기준",
            "다음 → ② 룰 효과성 탭"])
        wf.info_panel(s, "AML-STAT-001", [
            "• 권한 aml:case:read — STR 통계는 준법감시 전담 한정(tipping-off)",
            "• 탭 ① STR 보고 현황 통계 / ② 룰 효과성",
            "• 카드 추출→검토→결재→제출 퍼널 + 지연 보고",
            "• 지연 보고 일수 분포 — 법정 SLA(STR 3영업일·CTR 30일) 기준",
            "• 미보고(기각·취소) 사유 코드 분포 — 사후 검증·감사 추적",
            "• 전 항목 read-only 집계 파생값(bo-api 소유·30~60초 캐시·PII 미포함)",
            "• 다음 → ② 룰 효과성",
            "▸ API GET /api/v1/bo/aml/stats/str (제안 · bo-api 집계 소유)"])
    else:  # tab == 1
        y = wf.entry_banner(s, y, "AML-TM-001 ② 시나리오 관리에서 [효과성 ▶] 클릭 → 시나리오 코드 컨텍스트 진입")
        y = wf.filters(s, y, ["기간 최근 30일", "시나리오 상태 활성"])
        y = wf.table_block(s, y, 2.05, "시나리오(룰)별 효과성 — 행 ▶ → AML-TM-002 (시나리오 튜닝)",
            ["시나리오", "알림(A)", "케이스 전환(a)", "보고(B)", "전환율(B/A)", "전월 대비", "권고"],
            [["구조화거래", "48", "19", "15", "31%", "+4%p", "유지"],
             ["뮬 네트워크", "33", "15", "13", "39%", "+1%p", "유지"],
             ["급속이동", "21", "6", "5", "24%", "-2%p", "유지"],
             ["고위험 corridor", "12", "2", "1", "8%", "-6%p", "튜닝 ⚠ ▶"]],
            [0.20, 0.10, 0.15, 0.10, 0.14, 0.13, 0.18])
        wf.callout(s, y, "② 룰 효과성 — 룰 라이프사이클 폐루프(정의→임계→시뮬레이션→효과성 평가)", [
            "전환율 비정상(과소·과다 추출) 시나리오 = 튜닝 후보 ⚠ — 조정·중단은 AML-TM-002 4-eyes 경유",
            "본 화면은 판단 근거만 제공(read-only) · 이전 ← ① STR 보고 현황 통계  (통계 2탭 끝)"])
        wf.info_panel(s, "AML-STAT-001", [
            "• 권한 조회 aml:case:read",
            "• 탭 ② 룰 효과성",
            "• 진입 NAV 통계·내부통제 / AML-TM-001 ② 행 ▶ 드릴다운",
            "• 컬럼 시나리오·알림(A)·케이스 전환(a)·보고(B)·전환율(B/A)·전월 대비·권고",
            "• 튜닝 후보 ⚠ 행 ▶ → AML-TM-002 (조정·중단 4-eyes TM_SCENARIO)",
            "• read-only 집계 — 룰 튜닝 거버넌스의 판단 근거",
            "• 이전 ← ① STR 보고 현황 통계  (통계 2탭 끝)",
            "▸ API GET /api/v1/bo/aml/stats/scenarios (제안 · bo-api 집계 소유)"])


# ─── AML-EDU-001 내부통제 교육·자격 관리 (v6.0 벤치마크 보강, 2탭) ───
EDU_001_TABS = ["교육 과정·이수 현황", "자격 보유 현황"]


def edu_001(p, tab=0):
    titles = ["내부통제 교육·자격 관리 — ① 교육 과정·이수 현황",
              "내부통제 교육·자격 관리 — ② 자격 보유 현황"]
    crumbs = ["AML Console > 통계·내부통제 > 교육 과정·이수 현황",
              "AML Console > 통계·내부통제 > 자격 보유 현황"]
    s = frame(p, "AML-EDU-001", crumbs[tab], titles[tab], search="직원·과정 검색...",
              action="+ 과정 등록" if tab == 0 else None)
    y = wf.CON_TOP
    y = wf.tab_chips(s, y, EDU_001_TABS, active=tab)
    if tab == 0:
        y = wf.filters(s, y, ["교육 대상 전체", "진행 상태 전체", "기간 직전 1년"])
        y = wf.table_block(s, y, 1.85, "교육 과정 (특정금융정보법 §5 내부통제 — 교육·연수)",
            ["과정명", "제작 기관", "형태", "대상", "기간", "시간", "이수율"],
            [["AML 기본 과정", "협회", "온라인", "전 직원", "01-02~12-31", "4h", "94%"],
             ["STR 작성 실무", "자체", "집합", "전담부서", "03-10~03-11", "8h", "100%"],
             ["제재 스크리닝 심화", "외부", "온라인", "전담부서", "05-01~06-30", "6h", "78% ⚠"]],
            [0.22, 0.12, 0.10, 0.14, 0.20, 0.08, 0.14])
        y = wf.table_block(s, y, 1.15, "미이수자 (기준 기간: 직전 1년)",
            ["사번", "표시명", "부서", "미이수 과정", "기한"],
            [["e-1024", "김OO", "준법감시", "제재 스크리닝 심화", "06-30"],
             ["e-1187", "이OO", "운영", "AML 기본 과정", "12-31"]],
            [0.14, 0.14, 0.18, 0.34, 0.20])
        wf.callout(s, y, "① 교육 — 이수 데이터는 AML-IRA-001 운영위험 지표 자동 수집 원천", [
            "다음 → ② 자격 보유 현황 탭"])
        wf.info_panel(s, "AML-EDU-001", [
            "• 권한 등록·관리 aml:admin:policy / 조회 aml:case:read",
            "• 탭 ① 교육 과정·이수 현황 / ② 자격 보유 현황",
            "• 컬럼 과정명·제작 기관·형태·대상(전담부서 포함)·기간·시간·이수율",
            "• 미이수자 목록 — 기준 기간 프리셋(직전 1년)",
            "• 이수 데이터 → AML-IRA-001 운영위험 지표 자동 수집(§12-B.2)",
            "• 기준일자 스냅샷 보존(감독·검사 증적) · 등록·변경 감사 기록",
            "• 다음 → ② 자격 보유 현황",
            "▸ API GET/POST /api/v1/bo/aml/training/courses (제안 · bo-api 소유)"])
    else:  # tab == 1
        y = wf.filters(s, y, ["부서 전체", "자격 전체", "기준일 2026-06-12"])
        y = wf.table_block(s, y, 2.10, "직원 × 자격 보유 매트릭스 (취득일 표시 · 기준일자 스냅샷)",
            ["사번", "표시명", "부서", "CAMS", "KCAMS", "핵심요원(전문)", "핵심요원(기초)"],
            [["e-0901", "박OO", "준법감시", "2023-04-01", "—", "2022-10-15", "2021-05-20"],
             ["e-1024", "김OO", "준법감시", "—", "2024-08-12", "—", "2023-02-10"],
             ["e-1187", "이OO", "운영", "—", "—", "—", "2024-11-03"]],
            [0.11, 0.12, 0.13, 0.16, 0.16, 0.17, 0.15])
        wf.callout(s, y, "② 자격 — [템플릿 다운로드] → 파일 업로드 일괄 등록", [
            "임직원 식별은 사번·표시명 수준(인사 원장 비보유 — IAM/조직 연계는 bo-api 소관)",
            "교육 미이수·자격 미달 임계 알림은 대시보드 운영 알림 연계 후보(후속 오픈결정)",
            "이전 ← ① 교육 과정·이수 현황  (내부통제 2탭 끝)"])
        wf.info_panel(s, "AML-EDU-001", [
            "• 권한 등록·관리 aml:admin:policy",
            "• 탭 ② 자격 보유 현황",
            "• 매트릭스 직원 × 자격(CAMS·KCAMS·핵심요원 전문/기초) 취득일",
            "• 템플릿 다운로드 → 파일 업로드 일괄 등록",
            "• 사번·표시명 수준 식별(인사 원장 비보유 · §1.6 경계 준용)",
            "• 자격 데이터 → AML-IRA-001 운영위험 지표 자동 수집(§12-B.2)",
            "• 이전 ← ① 교육 과정·이수 현황  (내부통제 2탭 끝)",
            "▸ API GET/POST /api/v1/bo/aml/certifications (제안 · bo-api 소유)"])


# ═══ 13. 감사·증적 Export·소스 시스템 관리 ══════════════════════
AUD_001_TABS = ["감사 로그", "증적 Export", "소스 시스템"]


def aud_001(p, tab=0):
    titles = ["감사·증적·소스 — ① 감사 로그",
              "감사·증적·소스 — ② 증적 Export",
              "감사·증적·소스 — ③ 소스 시스템"]
    crumbs = ["AML Console > 감사·증적 > 감사 로그",
              "AML Console > 감사·증적 > 증적 Export",
              "AML Console > 감사·증적 > 소스 시스템"]
    s = frame(p, "AML-AUD-001", crumbs[tab], titles[tab], search="작업자·대상 검색...")
    y = wf.CON_TOP
    y = wf.tab_chips(s, y, AUD_001_TABS, active=tab)
    if tab == 0:
        y = wf.filters(s, y, ["감사 카테고리 전체", "기간 전체"])
        y = wf.table_block(s, y, 2.30, "감사 로그 [고객사: 은행 A] (append-only · hash chain) · 대상=마스킹",
            ["시각", "카테고리", "작업자", "대상", "내용", "체인"],
            [["06-06 10:21", "결재 승인", "이감리", "apr-551", "WLF 확정 승인", "✓"],
             ["06-06 10:05", "원문 접근", "박심사", "cust_…501", "EDD 증빙 열람", "✓"],
             ["06-06 03:00", "명단 import", "시스템", "OFAC v142", "변경분 +18/6/2", "✓"],
             ["06-05 15:30", "정책 변경", "이감리", "country v7", "MM 높음→거래금지", "✓"],
             ["06-05 09:10", "케이스 생성", "시스템", "case-771", "RA 높음 트리거", "✓"]],
            [0.18, 0.16, 0.12, 0.16, 0.24, 0.14])
        wf.callout(s, y, "① 감사 로그 — append-only · hash chain 검증 · 수정·삭제 불가", [
            "감사 카테고리 결재 승인/반려·원문 접근·명단 import·정책 변경·케이스 종결 등",
            "원문(PII) 열람 이력 aml:pii:reveal+사유+자동 감사(RAW_DATA_ACCESS)",
            "다음 → ② 증적 Export"])
        wf.info_panel(s, "AML-AUD-001", [
            "• 권한 감사 조회 aml:admin:audit",
            "• 탭 ① 감사 로그 / ② 증적 Export / ③ 소스 시스템",
            "• 필터 감사 카테고리·기간 + 작업자/대상",
            "• append-only(수정·삭제 불가) · hash chain 검증",
            "• 감사 카테고리 결재 승인/반려·원문 접근·명단 import·정책 변경·케이스 종결",
            "• 다음 → ② 증적 Export",
            "▸ API GET /api/v1/bo/aml/audit (bo-api)"])
    elif tab == 1:
        y = wf.two_panels(s, y, 1.45,
            ("증적 생성 설정", ["항목", "값"],
             [["증적 유형", "[STR 증적 ▼]"],
              ["포맷", "[PDF ▼]  (CSV/Excel/PDF/API)"],
              ["기간", "[2026-01 ~ 2026-03]"],
              ["사유", "[검사 대응]"],
              ["", "[+ 증적 생성]"]],
             [0.40, 0.60]),
            ("생성 이력", ["증적ID", "유형", "포맷", "행 수", "hash"],
             [["exp-77", "STR 증적", "PDF", "1,204", "0xab…"],
              ["exp-71", "CDD/EDD", "CSV", "588", "0x7c…"],
              ["exp-65", "RA 리포트", "Excel", "2,400", "0x3d…"]],
             [0.16, 0.22, 0.14, 0.14, 0.34]))
        wf.callout(s, y, "② 증적 Export — manifest hash 고정 · 만료 URL 다운로드", [
            "증적 유형 CDD/EDD·WLF 등록부·RA 리포트·TM 이력·STR/CTR·Travel Rule·명단 변경·PII 접근",
            "생성자·사유·기간·row count·manifest hash 기록 · 만료 URL 다운로드",
            "이전 ← ① 감사 로그  /  다음 → ③ 소스 시스템"])
        wf.info_panel(s, "AML-AUD-001", [
            "• 권한 증적 export aml:evidence:export",
            "• 탭 ② 증적 Export",
            "• 증적 유형·포맷·기간·사유 설정 후 생성",
            "• 포맷 CSV/Excel/PDF/API",
            "• manifest hash 고정 · 만료 URL 다운로드",
            "• 이전 ← ① 감사 로그  /  다음 → ③ 소스 시스템",
            "▸ API POST /evidence/aml/exports · GET (이력·다운로드 URL)"])
    else:  # tab == 2
        y = wf.table_block(s, y, 2.10, "소스 시스템 관리 [고객사: 은행 A]",
            ["소스 ID", "종류", "연동 방식", "인증", "장애 정책", "상태"],
            [["core-banking", "회원·계좌", "큐(MQ)", "API Key+HMAC", "수동검토", "활성 ✓"],
             ["onboarding", "온보딩", "REST 전송", "mTLS", "차단(fail-closed)", "활성 ✓"],
             ["transaction", "거래", "변경수집(CDC)", "OAuth2", "지연허용(D-14)", "활성 ✓"],
             ["kyc-feed", "KYC", "스냅샷", "mTLS", "수동검토", "지연 ⚠"]],
            [0.18, 0.14, 0.18, 0.16, 0.20, 0.14])
        wf.callout(s, y, "③ 소스 시스템 — 소스 등록·secret 변경 4-eyes(SECRET_CHANGE)", [
            "[+ 소스 등록(2인)] · secret 변경 = 4-eyes(SECRET_CHANGE·보안 관리자) · secret 마스킹",
            "연동 방식 REST 전송/큐/폴링/변경수집/스냅샷/벤더브릿지 · 인증 API Key+HMAC/OAuth2/mTLS",
            "이전 ← ② 증적 Export  (감사·증적 3탭 끝)"])
        wf.info_panel(s, "AML-AUD-001", [
            "• 권한 소스·secret aml:admin:source-system (2인)",
            "• 탭 ③ 소스 시스템",
            "• 컬럼 소스 ID · 종류 · 연동 방식 · 인증 · 장애 정책 · 상태",
            "• 연동 방식 REST/큐/폴링/변경수집/스냅샷/벤더브릿지",
            "• 인증 API Key+HMAC / OAuth2 / mTLS",
            "• 장애 정책 수동검토/차단(fail-closed)/지연허용(D-14)",
            "• 소스 등록·secret 변경 4-eyes(SECRET_CHANGE·보안 관리자)",
            "• 이전 ← ② 증적 Export  (감사·증적 3탭 끝)",
            "▸ API GET/POST .../source-systems · :change-secret(2인·SECRET_CHANGE)"])


# ═══ 빌드 ════════════════════════════════════════════════════════
# ─── AML-ING-001 수신 API 카탈로그·인입 라이브 모니터링 (v8.0, 2탭) ───
ING_001_TABS = ["수신 API 카탈로그", "인입 라이브 모니터링"]


def ing_001(p, tab=0):
    titles = ["수신 API 카탈로그·인입 모니터링 — ① 수신 API 카탈로그",
              "수신 API 카탈로그·인입 모니터링 — ② 인입 라이브 모니터링"]
    crumbs = ["AML Console > 감사·증적 > 인입 모니터링 > 수신 API 카탈로그",
              "AML Console > 감사·증적 > 인입 모니터링 > 인입 라이브"]
    s = frame(p, "AML-ING-001", crumbs[tab], titles[tab], search="소스·API 검색...")
    y = wf.CON_TOP
    y = wf.tab_chips(s, y, ING_001_TABS, active=tab)
    if tab == 0:
        y = wf.table_block(s, y, 1.80, "수신 API 카탈로그 [고객사: 은행 A] (정본 = PRD §1.11 ② · API §3.1~3.4)",
            ["API", "용도", "방식", "인증", "24h 호출", "마지막 호출", "신호"],
            [["POST /aml/events", "이벤트 수신·백필", "비동기(큐)", "HMAC", "1.2M", "2초 전", "●"],
             ["POST /aml/screen", "명단 스크리닝(WLF)", "동기", "HMAC", "48K", "1초 전", "●"],
             ["POST …/risk-assessments/evaluate", "위험평가(RA)", "동기", "OAuth2", "12K", "5초 전", "●"],
             ["POST …/transactions/evaluate", "거래 모니터링(TM)", "동기", "HMAC", "310K", "1초 전", "●"]],
            [0.30, 0.18, 0.10, 0.08, 0.10, 0.13, 0.11])
        y = wf.table_block(s, y, 2.10, "연동 방식 × 표시 신호 확정표 (PRD §1.11 ① 확정 — 6종)",
            ["연동 방식(코드)", "화면 표시 신호 (확정)"],
            [["REST 전송 (REST_PUSH)", "마지막 수신(n초 전) · ● 수신중 · 수신율(TPS) · 서명 실패"],
             ["큐 (QUEUE)", "depth · lag · DLQ 적체 · 마지막 메시지 — aml-ingest(+.fifo) · aml-ingest-dlq"],
             ["폴링 (POLLING)", "마지막 폴링 · 다음 폴링 예정 · 주기 · 현재 커서"],
             ["변경수집 (CDC)", "change stream lag · 마지막 변경분 적용 시각"],
             ["스냅샷 (SNAPSHOT)", "최근 스냅샷 일시 · 초기 적재(백필) 진행률 %"],
             ["벤더브릿지 (VENDOR_BRIDGE)", "마지막 벤더 경보 · VENDOR 인입 건수"]],
            [0.28, 0.72])
        wf.callout(s, y, "① 카탈로그 — 어떤 API로 데이터가 들어오는가 (read-only)", [
            "신호 상태 ● 수신중(기본 60초 내 수신) / ⚠ 지연(SLA 초과) / ✕ 중단 (§1.11 ③ 확정)",
            "초기 셋업(백필) = /aml/events 대량 적재·SNAPSHOT — 진행률 ② 탭 · 다음 → ② 인입 라이브"])
        wf.info_panel(s, "AML-ING-001", [
            "• 권한 aml:admin:source-system (read-only 집계)",
            "• 진입 NAV 감사·증적 / AML-TNT-002 ③ [인입 모니터링 ▶]",
            "• 탭 ① 수신 API 카탈로그 / ② 인입 라이브 모니터링",
            "• 컬럼 API·용도·방식(동기/비동기)·인증·24h 호출·마지막 호출·신호",
            "• 연동 방식×표시 신호 확정표 6종 (PRD §1.11 ① 파생 표시)",
            "• 큐 정본 aml-ingest(+.fifo)·aml-ingest-dlq (integration §2.1)",
            "• 인증 API Key+HMAC / OAuth2 / mTLS (소스별 authMode · D-13)",
            "• 초기 셋업(백필) /aml/events 대량 적재 — SNAPSHOT 연계",
            "• 다음 → ② 인입 라이브 모니터링",
            "▸ API GET /api/v1/bo/aml/ingest/catalog (제안 · 후속 API 정합)"])
    else:
        y = wf.kpi_cards(s, y, [
            ("24h 수신 이벤트", "1.58 M", "15 family", "blue"),
            ("라이브 소스", "4 / 5", "● 수신중 기준", "green"),
            ("DLQ 적체", "3 건", "aml-ingest-dlq ⚠", "red"),
            ("마지막 수신", "2초 전", "전체 소스 최신", "orange")])
        y = wf.table_block(s, y, 2.05, "소스×연동 방식별 라이브 상태 (행 ▶ → AML-AUD-001 ③ 소스 관리)",
            ["소스", "연동 방식", "마지막 수신", "신호", "방식별 상태 (PRD §1.11 ① 확정)"],
            [["src-core", "REST 전송", "8초 전", "●", "TPS 42 · 서명(HMAC) 실패 0"],
             ["src-txn", "큐 aml-ingest.fifo", "2초 전", "●", "depth 120 · lag 4초 · DLQ 0"],
             ["src-kyc", "폴링", "38분 전", "✕", "마지막 09:10 · 다음 09:40 · 주기 30분"],
             ["src-legacy", "벤더브릿지", "4분 전", "●", "벤더 경보 12건/24h (VENDOR)"],
             ["snapshot-init", "스냅샷", "—", "—", "초기 적재(백필) 78% (1.2M/1.55M)"]],
            [0.14, 0.18, 0.12, 0.08, 0.48])
        wf.callout(s, y, "② 라이브 모니터링 — 지금 데이터가 들어오고 있는가 (30~60초 캐시·자동 새로고침)", [
            "⚠/✕ 행은 AML-DASH-001 운영 알림과 동일 이벤트 소스 (알림 클릭 → 본 탭 딥링크)",
            "운영 조치(소스 비활성·secret 변경 2인)는 AML-AUD-001 ③ 소관 — 본 화면 모니터링 전용",
            "이전 ← ① 수신 API 카탈로그 (인입 모니터링 2탭 끝)"])
        wf.info_panel(s, "AML-ING-001", [
            "• 권한 aml:admin:source-system (read-only 집계)",
            "• 카드 24h 수신·라이브 소스·DLQ 적체·마지막 수신",
            "• REST 마지막 수신·TPS / 큐 depth·lag·DLQ / 폴링 마지막·다음·주기",
            "• CDC stream lag / 스냅샷 최근 일시·백필 진행률 / 벤더 마지막 경보",
            "• 큐 정본 aml-ingest(+.fifo)·aml-ingest-dlq (integration §2.1)",
            "• 신호 ● 수신중/⚠ 지연/✕ 중단 (§1.11 ③ · 임계 소스별 설정)",
            "• 운영 조치는 AML-AUD-001 ③ (모니터링/운영 분리)",
            "• 이전 ← ① 수신 API 카탈로그",
            "▸ API GET /api/v1/bo/aml/ingest/health (제안 · 후속 API 정합)"])


SCREENS = [
    dash_001,                          # AML-DASH-001
    tnt_001,                           # AML-TNT-001 고객사 목록
    tnt_002_basic, tnt_002_deploy, tnt_002_source, tnt_002_policy,  # AML-TNT-002 4탭
    tnt_003,                           # AML-TNT-003 고객사 등록
    wlf_001, wlf_002, wlf_003,         # AML-WLF-001~003 검토필요→상위승인→처리이력
    lambda p: wlf_004(p, 0),           # AML-WLF-004 ① 단건 시뮬레이션 (v6.0 벤치마크)
    lambda p: wlf_004(p, 1),           # AML-WLF-004 ② 임의 수행(일괄)
    lambda p: wl_001(p, 0),            # AML-WL-001 ① 소스 목록
    lambda p: wl_001(p, 1),            # AML-WL-001 ② 임포트 이력
    lambda p: wl_001(p, 2),            # AML-WL-001 ③ 명단 엔트리 조회
    wl_002,                            # AML-WL-002 변경분 상세
    lambda p: wl_003(p, 0),            # AML-WL-003 ① 내부 요주의 명단 (v7.0 벤치마크 2차)
    lambda p: wl_003(p, 1),            # AML-WL-003 ② 오탐 면제(White List) 관리
    lambda p: ctry_001(p, 0),          # AML-CTRY-001 ① 국가위험 등급표
    lambda p: ctry_001(p, 1),          # AML-CTRY-001 ② 변경 상신·이력
    lambda p: ra_001(p, 0),            # AML-RA-001 ① 점수 분포
    lambda p: ra_001(p, 1),            # AML-RA-001 ② 고위험 목록
    lambda p: ra_003(p, 0),            # AML-RA-003 ① factor breakdown  (드릴다운: RA-001 ②→)
    lambda p: ra_003(p, 1),            # AML-RA-003 ② 관계·UBO
    lambda p: ra_003(p, 2),            # AML-RA-003 ③ 재심사 이력
    lambda p: cdd_002(p, 0),           # AML-CDD-002 ① CDD 프로필 (v7.0 드릴다운: RA-003 ①→)
    lambda p: cdd_002(p, 1),           # AML-CDD-002 ② 위험·활동 요약
    lambda p: ra_002(p, 0),            # AML-RA-002 ① 버전 목록  (모델 관리)
    lambda p: ra_002(p, 1),            # AML-RA-002 ② factor 편집
    lambda p: ra_002(p, 2),            # AML-RA-002 ③ 시뮬레이션 (모델 초안 검증)
    lambda p: ra_002(p, 3),            # AML-RA-002 ④ 등급 조정 이력
    lambda p: hrr_001(p, 0),           # AML-HRR-001 ① 당연고위험 분류 기준 (v7.0 벤치마크 2차)
    lambda p: hrr_001(p, 1),           # AML-HRR-001 ② 참조 리스트 관리
    lambda p: cdd_001(p, 0),           # AML-CDD-001 ① 체크리스트 정의
    lambda p: cdd_001(p, 1),           # AML-CDD-001 ② 재심사 주기
    lambda p: cdd_001(p, 2),           # AML-CDD-001 ③ 변경 이력
    lambda p: tm_001(p, 0),            # AML-TM-001 ① 알림 적체
    lambda p: tm_001(p, 1),            # AML-TM-001 ② 시나리오 관리
    tm_002,                            # AML-TM-002 시나리오 빌더
    case_001,                          # AML-CASE-001 케이스 목록(필터탭 유지)
    lambda p: case_002(p, 0),          # AML-CASE-002 ① 타임라인
    lambda p: case_002(p, 1),          # AML-CASE-002 ② CDD/EDD 체크
    lambda p: case_002(p, 2),          # AML-CASE-002 ③ 관계·UBO
    lambda p: case_002(p, 3),          # AML-CASE-002 ④ 증빙
    lambda p: rep_001(p, 0),           # AML-REP-001 ① STR 후보
    lambda p: rep_001(p, 1),           # AML-REP-001 ② CTR 데이터
    lambda p: rep_001(p, 2),           # AML-REP-001 ③ 제출 이력
    lambda p: rep_002(p, 0),           # AML-REP-002 ① 보고 본문
    lambda p: rep_002(p, 1),           # AML-REP-002 ② 첨부 증빙
    lambda p: rep_002(p, 2),           # AML-REP-002 ③ 제출 이력
    lambda p: ira_001(p, 0),           # AML-IRA-001 ① 보고 회차·지표 등록 (v6.0 벤치마크)
    lambda p: ira_001(p, 1),           # AML-IRA-001 ② 결과·제출 결재
    lambda p: ira_001(p, 2),           # AML-IRA-001 ③ 보고 현황(FIU 회신)
    lambda p: tr_001(p, 0),            # AML-TR-001 ① 예외 큐
    lambda p: tr_001(p, 1),            # AML-TR-001 ② 전체 이전
    lambda p: tr_001(p, 2),            # AML-TR-001 ③ 처리 이력
    lambda p: pp_001(p, 0),            # AML-PP-001 ① 적용 팩/기준금액
    lambda p: pp_001(p, 1),            # AML-PP-001 ② 변경 상신·이력
    apr_001,                           # AML-APR-001 결재 대기함(필터탭 유지)
    lambda p: stat_001(p, 0),          # AML-STAT-001 ① STR 보고 현황 통계 (v6.0 벤치마크)
    lambda p: stat_001(p, 1),          # AML-STAT-001 ② 룰 효과성
    lambda p: edu_001(p, 0),           # AML-EDU-001 ① 교육 과정·이수 현황 (v6.0 벤치마크)
    lambda p: edu_001(p, 1),           # AML-EDU-001 ② 자격 보유 현황
    lambda p: aud_001(p, 0),           # AML-AUD-001 ① 감사 로그
    lambda p: aud_001(p, 1),           # AML-AUD-001 ② 증적 Export
    lambda p: aud_001(p, 2),           # AML-AUD-001 ③ 소스 시스템
    lambda p: ing_001(p, 0),           # AML-ING-001 ① 수신 API 카탈로그 (v8.0 인입 가시성)
    lambda p: ing_001(p, 1),           # AML-ING-001 ② 인입 라이브 모니터링
]


def build():
    p = wf.new_deck()
    # 1 커버
    wf.cover_slide(p,
        "SaaS AML Platform 백오피스 기획서",
        "멀티 고객사·서비스 자금세탁방지(AML) 운영 콘솔 — 준법감시실 화면 설계",
        ["정본 PRD: docs/plan/02-aml-sass-functional-spec.md (FS-AML-SAAS-001 v8.0)",
         "기능 ID 전수 32화면 (목록→상세→액션→결과 흐름 + 벤치마크 7화면 §12-B + 인입 모니터링 §12.2)",
         "좌 75% 와이어프레임(실제 도형) + 우 25% 기능 설명",
         "WLF(+시뮬레이션)·명단(+내부 명단·오탐 면제)·국가위험·RA/CDD(+당연고위험·고객 프로필)·TM·케이스·규제 보고·기관 RBA 보고·Travel Rule·Policy Pack·결재·통계·내부통제·감사·인입 모니터링·고객사 관리",
         "용어 고객사(tenant)·서비스(workspace) · enum 괄호 병기 · 책임 경계 명시",
         "버전 BO-AML-SAAS-Planning v8.0 (데이터 인입 가시성 보강 — ING-001·인입 유형 확정, 32화면)"],
        brand="HANPASS  ·  SaaS AML Platform")
    # 2 변경 이력
    wf.history_slide(p, "변경 이력",
        ["버전", "일자", "작성자", "변경 내역"],
        [["v2.0", "2026-06-06", "Hanpass Global", "설계서 기준 정합화 전면 재작성 — 14 도메인·BO 화면 10종+대시보드"],
         ["v2.1", "2026-06-07", "Hanpass Global", "정합성 리포트 동기화 — 집계 소유 경계·HTTP 상태코드·표시 용어 사전 정정"],
         ["v3.0", "2026-06-07", "Hanpass Global", "도형 기반 PPT 전면 재생성 — AML-* 11화면 전수(맑은고딕·Ant Design)"],
         ["v4.0", "2026-06-07", "Hanpass Global", "시나리오 흐름 재구성(11→20) — 후속 상세 6종·앞단 정책 관리 3종 신규"],
         ["v5.0", "2026-06-08", "Hanpass Global", "배포 모델 재설계(20→24화면) — 고객사 관리 TNT-001~004 신규, 격리 라디오 폐기"],
         ["v5.1", "2026-06-08", "Hanpass Global", "정합성 정정 — admin scope 통일·DASH Travel Rule 행·TNT-004 설치형 콜백 UI"],
         ["v5.2", "2026-06-08", "Hanpass Global", "정합성 정정 — WLF-002 권한·API 수정, WLF 필터/컬럼·TNT-001 region 필터"],
         ["v5.3", "2026-06-08", "Hanpass Global", "정합성 정정 — WLF 3화면(검토필요→상위승인→처리이력)·결재 16종·면제 카드·status enum"],
         ["v5.4", "2026-06-08", "Hanpass Global", "고객사 상세(TNT-002) 4탭 연속 전개(기본정보→배포온보딩→소스→정책팩), 온보딩 흡수·등록 분리"],
         ["v5.5", "2026-06-08", "Hanpass Global", "멀티탭 상세/플로우 화면 탭 연속 전개 — 13화면(WL-001·CTRY-001·RA-001/002/003·CDD-001·TM-001·CASE-002·REP-001/002·TR-001·PP-001·AUD-001)"],
         ["v5.6", "2026-06-09", "Hanpass Global", "드릴다운 진입 트리거 배너 추가(RA-003·WL-002·CASE-002·REP-002·TM-002) + RA 순서 재배치(모니터→상세→설정)"],
         ["v5.7", "2026-06-10", "Hanpass Global", "RA 시뮬레이션→모델 관리(RA-002 ③) 이동, 정책팩 탭 KR_DEFAULT 미리보기·드릴다운·버전 정합"],
         ["v5.8", "2026-06-10", "Hanpass Global", "정책팩 기본 번들(KR_DEFAULT·잠금)+확장 plugin 구분 모델, FDS와 규제 모델 차이 명시"],
         ["v5.9", "2026-06-10", "Hanpass Global", "준법감시인 검토 반영: FIU 회신 폐루프·tipping-off·법정 SLA·CTR 제외대상 신설"],
         ["v5.10", "2026-06-10", "Hanpass Global", "QA 정합화: WLF-001 이전판정이력 탭·STR 종류 컬럼·WLF-003 SLA 카드·DASH D-3 표기·TNT 소스 오류 상태·드릴다운 ID"],
         ["v5.11", "2026-06-11", "Hanpass Global", "QA 정합화: TM-001 ② 시나리오 목록 타이틀 아웃바운드 ID 표기(ppt-flow MEDIUM), WLF-003 KPI 카드 순서 정정(확정·오탐·자동낮춤·면제·SLA)"],
         ["v5.12", "2026-06-11", "Hanpass Global", "정합성 QA 높음 이격 해소(테넌트 상태 4종·정책팩 경로 정정 등)"],
         ["v5.13", "2026-06-11", "Hanpass Global", "QA 정합화: 보고 기각·취소 결재 엔드포인트 표기"],
         ["v5.14", "2026-06-11", "Hanpass Global", "QA 정합화: TM-001 탭 명칭 정정"],
         ["v5.15", "2026-06-11", "Hanpass Global", "QA 정합화: 화면 범위 표 CTRY·CDD 등재(24화면)"],
         ["v6.0", "2026-06-12", "Hanpass Global", "실계 벤치마크 보강(GTone 80화면): WLF-004·IRA-001·STAT-001·EDU-001 신설(28화면)"],
         ["v7.0", "2026-06-12", "Hanpass Global", "벤치마크 2차 보강: WL-003(내부 명단·오탐 면제)·HRR-001(당연고위험)·CDD-002(고객 프로필) 신설 + TNT-002 ① 보고기관 패널(31화면)"],
         ["v8.0", "2026-06-12", "Hanpass Global", "데이터 인입 가시성: ING-001(수신 API 카탈로그·인입 라이브) 신설·TNT-002 ③ 인입 신호 컬럼·인입 유형 확정 §1.11(32화면)"]],
        col_w=[0.07, 0.11, 0.12, 0.70])
    # 3+ 기능 전수
    for fn in SCREENS:
        fn(p)
    out = "/Users/smkim/workspace/smkim89/aml-system-docs/docs/plan/BO-AML-SAAS-Planning_v8.0.pptx"
    p.save(out)
    print(f"saved {out} · slides={len(p.slides._sldIdLst)}")


if __name__ == "__main__":
    build()
