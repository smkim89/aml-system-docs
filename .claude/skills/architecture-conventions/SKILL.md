---
name: architecture-conventions
description: SaaS AML/FDS 플랫폼 설계·기획에 공통 적용하는 횡단 컨벤션(모노레포 4서비스 구조, 서비스별 스택·레이아웃, 멀티테넌시·컴플라이언스·관측성 원칙, 참조 레포 매핑). 설계서·기능정의서 작성 중 아키텍처 사실을 확인할 때 트리거. "아키텍처 컨벤션", "타깃 구조 확인" 요청 시 사용.
---

# Architecture Conventions

타깃 시스템의 **횡단 컨벤션 정본**은 한 파일에 둔다:

→ **[`../_shared/target-architecture.md`](../_shared/target-architecture.md)**

## 요약 (상세는 정본 참조)
- **모노레포 4서비스**: `fds-svc`·`aml-svc`(Java25 헥사고날) / `bo-api`(Java25 패키지-바이-피처) / `bo-web`(Next.js16).
- **참조 레포**: `hanpass-ph`(엔진·BO백엔드 패턴) / `hanpassj-backoffice`(BO API) / `hanpassr-backoffice`(BO Web).
- **헥사고날**: domain(규칙) / application(usecase·port) / adapter(in·out) / global.
- **횡단 원칙**: 멀티테넌시(tenant/workspace/data-scope) · raw PII 미저장·마스킹 · 4-eyes · 규제 Policy Pack(STR/CTR/Travel Rule) · traceId 관측성.

설계서·PRD의 모든 stack·layout·네이밍 사실은 정본에서 가져오고, 정본과 충돌하면 정본을 우선한다. 정본 변경 시 이 요약도 갱신한다.
