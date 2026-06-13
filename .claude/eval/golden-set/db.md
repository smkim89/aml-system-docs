---
artifact: db
target: docs/design/db/NN-<svc>-db.md
version: 1
owner: data-modeler
---

# 골든셋 — DB 설계서 (예/아니오, 각 1점)

1. 모든 테이블 컬럼이 **타입·NULL·기본값·제약·PK/FK**로 명세되는가?
2. enum 코드값이 설계서·API와 **1:1 일치(종수 명시)** 하는가?
3. 멀티테넌시 격리 키(`tenant_id`/`workspace_id`)가 PK·인덱스에 반영되는가?
4. Flyway 마이그레이션(V번호·additive-then-drop)이 정의되는가?
5. PII 마스킹(hash/token)·보존정책·append-only 감사가 명시되는가?
6. 파티셔닝/인덱스가 조회 패턴과 정합하는가?
7. 변경 이력이 설계서 변경과 동기화되는가?
