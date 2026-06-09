---
name: integration-design
description: SaaS AML/FDS 플랫폼의 이벤트·연동 명세서(docs/design/integration/NN-<svc>-integration.md)를 작성할 때 사용. canonical event·SQS 스키마·비동기 흐름·커넥터/필드매핑·아웃박스·규제 연동 규칙과 절차를 담는다. "이벤트 명세", "SQS/메시지 설계", "연동/커넥터 설계", "아웃박스 설계" 요청 시 트리거.
---

# Integration Design (이벤트·연동 명세서)

## 0. 정본·입력
- 입력: `docs/software/NN-<svc>-sass.md`(이벤트 분류·외부연동·Action/Outbox) + DB·API 설계.
- 정본: `_shared/target-architecture.md`(비동기 SQS·서비스 경계).
- 참조: `hanpass-ph/services/fds-svc/adapter/in/sqs`, out/external.

## 1. 절차
1. 이벤트 카탈로그: 이벤트명·발행자·구독자·트리거·페이로드 키.
2. 메시지 스키마(JSON): 필드·타입·필수·버전. DB/API 명칭과 정합.
3. 비동기 흐름: 시퀀스 다이어그램(Mermaid), 멱등성·재시도·DLQ·순서보장.
4. 커넥터: 외부 소스시스템 수집·필드매핑(원천→canonical).
5. 아웃박스: 액션 상태머신·Capability 매트릭스.

## 2. 필수
멀티테넌시 라우팅, raw PII 미전파(토큰/마스킹), 규제 제출(STR/CTR/Travel Rule) 흐름·증빙·재제출.

## 3. 산출
`docs/design/integration/NN-<svc>-integration.md` (카탈로그 + 스키마 + 시퀀스 + 매핑 + 아웃박스). 변경 이력 기록.
