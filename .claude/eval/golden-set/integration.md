---
artifact: integration
target: docs/design/integration/NN-<svc>-integration.md
version: 1
owner: integration-designer
---

# 골든셋 — 이벤트·연동 명세서 (예/아니오, 각 1점)

1. canonical event taxonomy·SQS 메시지 스키마가 정의되는가?
2. 비동기 흐름(아웃박스·FIFO·dedup·재시도)이 기술되는가?
3. 외부 소스시스템 커넥터·필드매핑·PII 정책이 명세되는가?
4. 규제 연동(Travel Rule·STR/CTR 제출)이 **책임 경계**와 함께 명시되는가?
5. 큐 이름·식별자·멱등키가 DB/API와 정합하는가?
6. 변경 이력이 상위 문서와 동기화되는가?
