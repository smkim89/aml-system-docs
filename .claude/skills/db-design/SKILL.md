---
name: db-design
description: SaaS AML/FDS 플랫폼의 DB 설계서(docs/design/db/NN-<svc>-db.md)를 작성할 때 사용. ERD·테이블 명세·인덱스·멀티테넌시 격리·파티셔닝·Flyway 마이그레이션 규칙과 절차를 담는다. "DB 설계", "ERD/테이블 명세", "스키마 설계" 요청 시 트리거.
---

# DB Design (DB 설계서)

## 0. 정본·입력
- 입력: `docs/software/NN-<svc>-sass.md`(데이터 모델·enum·규제).
- 정본: `_shared/target-architecture.md`(PostgreSQL·Flyway, 서비스별 별도 스키마).
- 참조: `hanpassj-backoffice` 엔티티, `hanpass-ph` 마이그레이션.

## 1. 절차
1. 설계서 도메인/집합체 → 논리 모델(ERD) 도출.
2. 물리 모델: 테이블 명세 표(컬럼·타입·NULL·기본값·제약·설명) + PK/FK + 인덱스(조회·유니크).
3. 멀티테넌시: 모든 운영 테이블에 tenant/workspace/data-scope 키 + 격리 전략(스키마/RLS/파티션) 명시.
4. 마이그레이션: Flyway 버전 순서·롤백 고려.

## 2. 필수
raw PII 미저장(토큰/해시 컬럼), 감사 컬럼(created/updated by·at), 보존·파기 정책, 금액은 정수 최소단위. enum은 코드값·표시값 병기.

## 3. 산출
`docs/design/db/NN-<svc>-db.md` (ERD Mermaid + 명세 표 + 마이그레이션 순서). API·태스크가 참조할 명칭 확정. 변경 이력 기록.
