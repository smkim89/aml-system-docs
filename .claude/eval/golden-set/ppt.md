---
artifact: ppt
target: .claude/skills/backoffice-planner/generate_<svc>.py (+ 산출 .pptx)
version: 1
owner: backoffice-planner
---

# 골든셋 — 기획서 PPT 생성기 (예/아니오, 각 1점)

1. 멀티탭 상세/플로우 화면이 **1탭=1슬라이드·같은 부모 탭 바·active 일치**인가?
2. 다른 기능 ID 드릴다운 첫 슬라이드에 **진입 배너**, 소스 행/버튼에 **▶ + "→XXX"** 가 있는가?
3. 실제 도형(ASCII 박스 금지)이고 렌더 시 **겹침·넘침·빈 화면 없음**인가?
4. PRD의 화면 순서·기능 ID·표시 용어와 생성기 SCREENS가 일치하는가?
5. 변경 이력 행이 **한 줄 요약**이고 커버 슬라이드 수가 정확한가?
6. 단순 필터 탭(대기/상신/완료 등)은 1슬라이드 유지(과분할 아님)인가?
