---
name: api-design
description: SaaS AML/FDS 플랫폼의 API 명세서(docs/design/api/NN-<svc>-api.md)를 작성할 때 사용. 엔드포인트 계약·DTO·인증/권한·에러코드·페이지네이션·OpenAPI 규칙과 절차를 담는다. "API 명세", "엔드포인트 설계", "OpenAPI 작성", "인터페이스 계약" 요청 시 트리거.
---

# API Design (API 명세서)

## 0. 정본·입력
- 입력: `docs/software/NN-<svc>-sass.md`(유스케이스·port) + `docs/design/db/NN-<svc>-db.md`(필드).
- 정본: `_shared/target-architecture.md`. bo-web→bo-api만, 엔진 직접호출 금지.
- 참조: `hanpass-ph/services/fds-svc/adapter/in/rest`.

## 1. 절차
1. 유스케이스 → 리소스·엔드포인트 도출. 엔드포인트 표(메서드·경로·설명·권한).
2. DTO: 요청/응답 스키마(타입·필수·검증). DB 필드와 정합, raw PII는 마스킹.
3. 횡단: 표준 에러모델(코드·메시지), 페이지네이션·정렬·필터, 멱등성 키, 버저닝(`/api/v1`).
4. OpenAPI(YAML) 스니펫 첨부.

## 2. 필수
tenant/workspace/data-scope 인증·인가, 4-eyes 대상 엔드포인트 표기, BO 화면(PRD)이 호출할 API 일치.

## 3. 산출
`docs/design/api/NN-<svc>-api.md` (엔드포인트 표 + DTO + 에러코드 + OpenAPI). 변경 이력 기록.
