---
name: system-design
description: SaaS AML/FDS 플랫폼의 시스템 설계서(docs/software/NN-<svc>-sass.md)를 작성·갱신할 때 사용. 모노레포 아키텍처·도메인/데이터 모델·멀티테넌시·연동·보안·로드맵 설계 규칙과 절차를 담는다. "설계서 작성/업데이트", "시스템 아키텍처 설계" 요청 시 트리거.
---

# System Design (설계서 작성)

## 0. 정본
- 아키텍처 사실: `_shared/target-architecture.md` (4서비스·stack·네이밍).
- 양식 정본: `docs/software/01-fdsSvc-sass.md`.

## 1. 절차
1. 정본 + 참조 레포(`hanpass-ph`·`hanpassj/r-backoffice`)로 사실 확인 — 추측 금지.
2. 기존 설계서 양식의 섹션 골격을 따른다: 목적 → 제품방향 → 참조구현 → 도메인 범위 → 설계원칙 → 플랫폼 아키텍처 → 공통 데이터모델 → 이벤트 분류 → 룰엔진/Feature Catalog → Action·Case·Investigation → 외부연동 → 멀티테넌시 → DB 설계 → 도메인 확장예시 → 보안·컴플라이언스·감사 → 운영·관측성 → 로드맵 → 오픈 결정사항.
3. 아키텍처·데이터흐름·도메인 모델은 다이어그램(Mermaid/ASCII)으로.

## 2. 필수 반영
멀티테넌시(tenant/workspace/data-scope), raw PII 미저장·마스킹, 4-eyes, 규제 Policy Pack(STR/CTR/Travel Rule), traceId 관측성.

## 3. 산출
`docs/software/NN-<svc>-sass.md`. 기획(backoffice-planner) 입력으로 쓰이도록 enum·API·규칙·규제를 명시. 완료 후 변경 이력 기록.
