---
artifact: cross
target: 전 문서 횡단
version: 1
owner: design-reviewer
---

# 골든셋 — 횡단 (예/아니오, 각 1점)

1. 전 문서 네이밍(엔티티·필드·enum)이 정본 기준 일치하는가?
2. 멀티테넌시 표시 용어(고객사=tenant / 서비스=workspace)가 통일되는가?
3. PII 마스킹·4-eyes·append-only 감사 원칙이 횡단 일관한가?
4. 서비스별 규제 모델 차이(Policy Pack 등)가 **의도적으로 명문화**(양방향 교차참조)되는가?
5. **정합 게이트** — `doc-consistency-qa`가 PASS(높음 이격 0)인가? ← HARD GATE
