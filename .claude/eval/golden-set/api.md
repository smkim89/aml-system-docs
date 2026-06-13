---
artifact: api
target: docs/design/api/NN-<svc>-api.md
version: 1
owner: api-designer
---

# 골든셋 — API 명세서 (예/아니오, 각 1점)

1. 모든 엔드포인트가 **method·path·권한 scope·DTO**로 명세되는가?
2. DTO 필드가 DB 컬럼과 매핑되고, enum이 정본(OpenAPI 스키마)과 **1:1(종수 명시)** 인가?
3. 4-eyes(🔒)·`subjectKind`가 결재 엔드포인트에 표시되는가?
4. 에러코드·HTTP 상태가 일관 정의(정본 매핑)되는가?
5. 페이지네이션·멱등성·소유 경계(bo-api vs engine)가 명시되는가?
6. OpenAPI 스니펫 enum이 본문 enum과 일치하는가?
7. 변경 이력이 DB/설계서 변경과 동기화되는가?
