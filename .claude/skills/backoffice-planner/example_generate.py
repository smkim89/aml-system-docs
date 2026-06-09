"""
와이어프레임 생성 예제 (정본 스타일 = docs/plan/sample.pptx).
wireframe_lib.py 컴포넌트만으로 한 화면을 그린다. ASCII 금지.
실행: cd .claude/skills/backoffice-planner && python3 example_generate.py
검증: soffice --headless --convert-to pdf --outdir /tmp out.pptx && pdftoppm -jpeg -r 90 /tmp/out.pdf /tmp/out
각 화면 = page_title + header_bar + nav_panel + breadcrumb_title + (본문 블록들) + info_panel.
본문 블록은 y-커서를 반환하므로 순서대로 쌓는다: filters→kpi_cards→callout→two_panels/table_block.
"""
import wireframe_lib as wf

NAV = ["플랫폼 대시보드", "테넌트 관리", "커넥터 관리", "스키마·매핑", "룰 관리",
       "그룹·명단", "탐지 결정", "이벤트 조회", "액션 운영", "케이스 관리",
       "결재함", "규제 보고", "Evidence", "감사 로그"]
TOP = "SaaS FDS Platform 백오피스"


def slide_dashboard(p):
    s = wf.add_slide(p)
    wf.page_title(s, TOP, "SFDS-DASH-001")
    wf.header_bar(s, search_ph="테넌트·룰·이벤트 검색...")
    wf.nav_panel(s, NAV, active=0)
    wf.breadcrumb_title(s, "FDS Console > 플랫폼 대시보드", "플랫폼 운영 대시보드 (전체 테넌트)")
    y = wf.CON_TOP
    y = wf.filters(s, y, ["최근 24시간", "테넌트 전체", "도메인 전체"])
    y = wf.kpi_cards(s, y, [
        ("실시간 평가(즉시)", "4,182,402 건", "평균 41ms · 차단 0.24%", "blue"),
        ("사후 평가", "442,910 건", "지연 4.2초 · 미처리 0", "green"),
        ("조치 · 케이스", "1,204 차단·보류", "케이스 신규 88 · 동결 12", "orange")])
    y = wf.callout(s, y, "플랫폼 알림", [
        "[PG B] 커넥터 지연 312초 — 임계초과 (커넥터)",
        "[은행 A] 스키마 검증 실패 4,201건 — 매핑 점검 (매핑)",
        "[거래소 C] 액션 발행 실패 적체 58건 (아웃박스)"])
    wf.two_panels(s, y, 2.10,
        ("테넌트별 건전성", ["테넌트", "수신", "검증실패", "액션실패"],
         [["은행 A", "2.1M", "4,201", "0"], ["PG B", "1.4M", "0", "312"], ["거래소 C", "0.6M", "0", "58"]],
         [0.34, 0.22, 0.22, 0.22]),
        ("AML 보고 기한 현황", ["항목", "건수"],
         [["CTR 기한 24시간 이내", "2"], ["STR 기한 24시간 이내", "1"], ["승인 후 미제출", "0"], ["기한 초과", "0"]],
         [0.7, 0.3]))
    wf.info_panel(s, "SFDS-DASH-001", [
        "• 권한 플랫폼 운영자 전용 조회 (SFDS_PLATFORM:READ)",
        "• 기간 최근 1h/24h/7d/30d + 테넌트·도메인 필터",
        "• 요약 카드 수신·결정·조치/케이스 건수와 비율",
        "• 플랫폼 알림 커넥터 지연·검증 실패·액션 적체",
        "• 테넌트별 건전성 수신·검증실패·lag·액션실패·SLA",
        "• 행 클릭 테넌트별 대시보드(DASH-002) 이동",
        "• 갱신 30~60초 주기 read-only",
        "▸ API GET /admin/fds/dashboard (bo-api 집약)"])


def slide_list(p):
    """목록 화면 archetype = filters + 전폭 table_block."""
    s = wf.add_slide(p)
    wf.page_title(s, TOP, "SFDS-RULE-001")
    wf.header_bar(s)
    wf.nav_panel(s, NAV, active=4)
    wf.breadcrumb_title(s, "FDS Console > 룰 관리", "룰 목록")
    y = wf.CON_TOP
    y = wf.filters(s, y, ["도메인 전체", "채널 전체", "상태 전체", "동작 전체"])
    wf.table_block(s, y, 3.9, "룰 목록 (총 142건 · 운영중 118)",
        ["룰 번호", "이름", "도메인", "동작", "평가", "상태"],
        [["MULE_BANK", "대포통장 수취 즉시 차단", "국내송금", "거래차단", "즉시", "운영중"],
         ["ATM_GEO", "해외 IP ATM 출금 추가인증", "ATM출금", "추가인증", "즉시", "운영중"],
         ["CNP_VEL", "신규기기 CNP 다발 차단", "카드결제", "승인거부", "즉시", "운영중"],
         ["CRYPTO_RISK", "고위험 주소 출금 자금보류", "가상자산", "자금보류", "사후", "운영중"],
         ["TBML_INV", "인보이스 단가 이상 검토", "무역대금", "검토", "사후", "비활성"]],
        [0.16, 0.30, 0.14, 0.14, 0.12, 0.14])
    wf.info_panel(s, "SFDS-RULE-001", [
        "• 권한 운영자 조회 (SFDS_RULE:READ)",
        "• 필터 도메인·채널·상태·동작 4축 + 룰 번호 검색",
        "• 컬럼 룰 번호·이름·도메인·동작·평가·상태",
        "• 상태 작성/결재대기/운영중/비활성/보관",
        "• 행 클릭 룰 상세(RULE-002) 이동",
        "▸ API GET /admin/fds/rules"])


if __name__ == "__main__":
    p = wf.new_deck()
    slide_dashboard(p)
    slide_list(p)
    p.save("/tmp/out.pptx")
    print("saved /tmp/out.pptx")
