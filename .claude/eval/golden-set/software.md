---
artifact: software
target: docs/software/NN-<svc>-sass.md
version: 1
owner: system-architect
---

# 골든셋 — 시스템 설계서 (예/아니오, 각 1점)

1. 도메인 모델·enum·상태머신이 표로 명시되고, DB/API가 참조할 **정본 명칭**을 가지는가?
2. 멀티테넌시(tenant/workspace/data-scope)·배포 모델이 정본(`_shared/target-architecture.md` §4.1)과 일치하는가?
3. 4-eyes 대상(`subjectKind`)·권한 scope가 **열거(enumerated)** 되어 있는가?
4. 규제·컴플라이언스 요건(Policy Pack·STR/CTR·Travel Rule 등)이 **parameter 기본값·근거**와 함께 명시되는가?
5. 외부연동·canonical event·아웃박스 흐름이 기술되는가?
6. 보안(PII 마스킹·append-only 감사)·관측성 원칙이 있는가?
7. 변경 이력이 최신이고, 파생 문서(DB·API·integration) **버전 핀**이 정확한가?
