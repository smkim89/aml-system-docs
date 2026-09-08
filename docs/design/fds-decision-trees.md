# FDS 정책 디시전트리 계약

2026-09-08 사용자 요청에 따른 개발 계약. 기존 룰 엔진과 거래 피처 기반 트리를 모두 평가한다. 구현 브랜치 feature/fds-dual-evaluation. 구현/검증 상태는 코드 저장소 PLAN을 따른다.

## 3. 거래 평가 계약

```mermaid
flowchart TD
  A[거래 REST 인입] --> B[멱등 확인 및 공통 피처 계산]
  B --> R[기존 ACTIVE 룰 평가]
  B --> T[적용 범위의 ACTIVE 트리 평가]
  R --> C[두 결과 결합]
  T --> C
  C --> D[최종 결정 및 양쪽 근거 저장]
  D --> E[응답 및 BO 탐지결정]
  D --> F[기존 조치와 AML 통지]
```

- 두 평가를 **항상 각각 호출**한다. 룰 BLOCK이어도 트리를 short-circuit하지 않는다. 동시 스레드 실행은 필요 없으며 두 평가 모두 요청 처리 안에서 끝난다.
- `POST /api/v1/fds/events`의 동기 인입 결선, `/api/v1/fds/events/evaluate`, `/api/v1/fds/decisions/evaluate`, ASYNC consumer의 공통 평가 경로를 모두 다룬다.
- 기존 FeatureComputePort의 **같은 snapshot을 1회 계산**하여 양쪽에 제공한다. 트리 evaluator 내부에 DB/HTTP/현재 시각 조회는 없다.
- 거래의 tenant/workspace/channel/evaluationPhase에 적용되는 활성 트리 1개를 조회한다. 한 트리를 여러 정확한 scope에 배포할 수 있지만 scope당 배포 포인터는 1개다. wildcard 우선순위·복수 트리 충돌을 만들지 않는다.
- 적용 가능한 트리가 없으면 `NOT_CONFIGURED`이고 기존 룰 결과가 최종이다. 미설정을 tree ALLOW/PASS로 위장하지 않는다. 룰만·트리만 구성된 scope도 각각 명시적으로 지원한다.
- 정상 신규 결정은 ruleOutcome, treeOutcome(nullable), treeStatus, treeId/version/hash, visited node/leaf/reasonCode, finalOutcome을 증거로 남긴다.
- 최종 `matchedRules`에는 실제 룰만 들어간다. 트리 단독 적중을 가짜 ruleId/룰명으로 합성하지 않는다.
- 기존 riskScore 산식은 **최종 outcome의 기존 RiskScoringPolicy 매핑**을 사용한다. tree 확률·ML 점수는 만들지 않는다.

### 3.1 결합표 (신규 계약 제안 A1)

정본 software §11.1에 이중 평가 결합이 미정의 — 기존 severity 순서를 명시적 결합표로 확장한다. enum ordinal에 의존하는 새 코드는 만들지 않는다.
트리 leaf는 ALLOW/MONITOR/REVIEW/CHALLENGE/BLOCK 5종, 기존 룰 8종은 유지한다.

| 룰 ↓ / 트리 → | ALLOW | MONITOR | REVIEW | CHALLENGE | BLOCK |
|---|---|---|---|---|---|
| ALLOW | ALLOW | MONITOR | REVIEW | CHALLENGE | BLOCK |
| MONITOR | MONITOR | MONITOR | REVIEW | CHALLENGE | BLOCK |
| REVIEW | REVIEW | REVIEW | REVIEW | CHALLENGE | BLOCK |
| CHALLENGE | CHALLENGE | CHALLENGE | CHALLENGE | CHALLENGE | BLOCK |
| BLOCK | BLOCK | BLOCK | BLOCK | BLOCK | BLOCK |
| HOLD | HOLD | HOLD | HOLD | HOLD | HOLD |
| FREEZE | FREEZE | FREEZE | FREEZE | FREEZE | FREEZE |
| REPORT | REPORT | REPORT | REPORT | REPORT | REPORT |

최종 outcome만 기존 DecisionActionRouter에 **1회** 전달한다. REVIEW→CHALLENGE일 때 OPEN_CASE가 아니라 SEND_ALERT가 되는 기존 action 매핑까지 테스트한다.
양쪽 조치를 합집합으로 실행하지 않는다. 룰의 강도를 낮추지 않는 계약이며 기존 BLOCK 오탐 해제 기능은 이번 범위가 아니다.
트리 단독 BLOCK도 진짜 최종 BLOCK으로 계정계 응답 및 기존 AML 통지를 발생시킨다. 별도 tree evidence를 조회 가능하게 하되 기존 AML matchedRules 계약은 유지한다.

### 3.2 실패·멱등·트리 교체 (신규 계약 제안 A2)

- 선택된 트리의 피처 누락은 정의된 missing 간선을 따른다. 타입 오류/정의 손상/한도 초과는 `ERROR`, 후보 outcome=null, 진단 code만 저장한다.
- 트리 오류 발생 시 유효한 룰 outcome과 **REVIEW fallback**을 위 결합 순서로 비교한다. rule BLOCK 이상은 유지하며 오류를 ALLOW로 통과시키지 않는다.
- 공통 feature compute 자체 실패는 기존 source-system fail_policy 계약을 유지하고 두 평가 상태를 `NOT_EVALUATED`로 기록한다. 기존 FAIL_OPEN을 이번 기능에서 임의로 변경하지 않는다.
- 저장/배포 조회 인프라 실패를 rule-only 성공으로 삼키지 않는다. 기존 트랜잭션 실패 경로로 반환하며 부분 결정·부분 outbox를 남기지 않는다.
- 기존 결정 자연키 `(tenant,workspace,event,phase,ruleSetVersion)`와 Idempotency-Key 계약을 유지한다. treeVersion을 ruleSetVersion 문자열에 덧붙이지 않는다.
- 기존 replay/동시 저장 패자는 저장된 최종 결정·tree evidence를 그대로 반환하고 두 평가/부작용을 재실행하지 않는다(경쟁 중 계산이 수행됐더라도 저장 승자만 발행).
- tree v2 배포 후 새 거래는 v2, 이전 동일 거래 replay는 v1 근거 그대로. ASYNC 단계는 기존 독립 단계·룰셋버전 계약을 유지한다.
- 트리 정의·버전은 평가 중 불변이다. 배포 조회에서 읽은 id/version/hash와 실제 사용 정의를 하나로 결속한다. 속도 최적화 캐시는 1차에 추가하지 않는다.

## 4. 트리 문법·등록·관리 메뉴

### 4.1 독립 정책 트리

- 입력은 materialized 거래 피처. branch는 featureKey/operator/typedValue, true/false/missing 대상 nodeId. leaf는 outcome/reasonCode.
- compound AND/OR는 순차 branch로 표현한다. 기존 RuleDslParser의 문법·missing 의미는 수정하지 않는다.
- number는 BigDecimal, boolean/string은 정확 타입. null/키 부재는 missing, 타입 불일치는 ERROR.
- 숫자 연산 EQ/NE/GT/GTE/LT/LTE, boolean/string EQ/NE. 잘못된 타입·연산 조합은 draft validation에서 거부한다.
- root 1개, nodeId 중복/미정 간선/cycle/도달 불가 거부. 최대 node=128, root depth 0 기준 간선 깊이=16(방문 node≤17), JSON=64KiB.
- 금액 피처는 서버 파생 baseEquivalent/amountBase를 사용한다. 등록 화면은 기준통화·값 타입·단위를 노출한다.
- feature catalog와 실제 materialized key를 검증한다. 원문 PII나 임의 code/SpEL/SQL 실행식은 받지 않는다.
- 트리 예시 템플릿은 초안 생성만 수행하며 운영 임계/자동 활성화는 제공하지 않는다. 운영자가 설정하는 범용 관리 기능이므로 특정 채널·업무 임계를 제품 코드에 고정하지 않는다.

### 4.2 관리 UX·라이프사이클

- FDS 탐지 정책 영역에 **디시전트리 관리** 메뉴 `/fds/decision-trees` 추가. 목록·검색·상태·적용 채널/단계·현재 배포 버전·작성일 제공.
- `/new`: 이름/설명, 카탈로그 피처 선택, 조건·분기·leaf 입력, 구조 검증, 초안 저장. JSON 코드만 입력하는 화면으로 대체하지 않는다.
- `/{treeId}`: 초안 편집, 버전 목록·차이, 분기 구조, 테스트 거래 simulation, 적용 범위 선택, 활성화/중지/롤백 상신, 승인 이력.
- 편집은 새 draft version으로 저장한다. 활성/승인대기 버전은 불변. 버전 번호/내용 hash를 분리하고 optimistic revision을 검사한다.
- simulation은 같은 evaluator로 저장 snapshot에 대해 실행한다. snapshot 없음/빈 객체=UNAVAILABLE, 개별 feature 부재는 missing. 현재 고객/그룹 데이터로 과거 snapshot을 대체하지 않는다.
- 샘플 대상 결정 ID는 명시 최대 50개, 한 scope·phase로 제한. 총수=성공+미평가+오류, leaf/branch coverage와 원결정·트리·결합 후보를 제공한다. 동일 request idempotency 유지.
- 활성화와 롤백은 동일 tree version/hash의 성공 simulationId를 요구한다. simulation input IDs·버전·시각·결과를 보존한다.
- 배포 상태는 scope별 포인터가 소유한다. 상신 시 기존 활성 포인터는 그대로 유지; 승인 실행 시에만 교체한다. 중지/rollback도 4-eyes 및 generation 검사 대상이다.
- archive는 활성 배포/승인대기 참조가 없는 트리만 허용한다. version/실결정 evidence를 hard delete하지 않는다.
- 권한: `SFDS_RULE:READ` 조회, `AUTHOR` 초안/시뮬레이션, `OPERATE` 배포 상신/중지/롤백/archive, `APPROVE` 승인/반려. UI 숨김과 BE 권한을 모두 검사한다.
- 기존 공통 form/table/status/modal을 재사용한다. node 편집/trace가 반복되는 부분은 components/common으로 추출한다. ko/en 동시, keyboard 입력/간선 선택/오류 focus 지원.
- `/fds/decisions/{decisionId}`에 **룰 평가 / 트리 평가 / 최종 결정**을 별도 표기하고 사용 버전과 분기 경로 표시. NOT_CONFIGURED/ERROR/NOT_EVALUATED를 번역된 상태로 구분한다.

### 4.3 저장·API·결재

- 구현 테이블: `fds_decision_trees`, `fds_decision_tree_versions`, `fds_tree_simulations`, `fds_tree_deployments`; `fds_decisions`에 nullable `tree_evaluation JSONB` 추가(기존 행 nullable).
- tenant/workspace 선두 복합키·FK·RLS. deployment PK에 channel/evaluationPhase, generation 포함. 동일 scope 동시 상신은 409, 승인 시 이전 generation이 다르면 stale approval 거부.
- simulation은 JSON 결과+고정 input IDs/hash를 저장하고 policy/evidence 보존 정책 적용, 자동 purge 없음. list는 페이지 size 1~100, default 20.
- 새 approval subjectKind `DECISION_TREE`를 engine enum/DB CHECK/BO exact permission/FE ko·en·결재 필터에 함께 추가한다. RULE subjectKind로 위장하지 않는다.
- 승인 payloadHash는 target tree/version/content hash, scope, 원하는 배포/중지 상태, 이전 generation, simulationId에 결속한다. maker/checker는 인증 principal에서 도출, self approval 409, 변조/stale 409.
- 엔진 `/api/v1/admin/fds/decision-trees`; BO `/api/v1/bo/fds/decision-trees` typed routes/client. 기존 BO admin 경로 별칭을 복사해 generic passthrough를 만들지 않는다.
- create POST 201, list/detail GET 200, draft version POST 201, simulations POST 201(동일 key replay 200), deployments POST 202, archive POST 200. 승인/반려는 기존 결재함 경로 사용.
- get version/simulation은 treeId 하위 조회. 잘못된 문법/크기/피처·입력 400/413, 인증 401, 권한 403, scope 밖·없음 404, revision/state/payload/idempotency conflict 409, 엔진 unavailable 503. 공통 error envelope와 trace 규약 유지.
- 비밀/원문 PII/전체 snapshot을 UI에 반환하지 않는다. trace는 nodeId·피처 label·operator·분기 결과·reasonCode, 허용된 값만 마스킹/요약한다.
- tree-only BLOCK의 ruleDecision=ALLOW, matchedRules=[]는 정직한 결과다. 최종 BLOCK 근거는 treeEvaluation과 reasonCode로 조회. AML 통지의 기존 필수 필드를 비우거나 가짜 룰로 채우지 않는다.



## 구현 계약 보충 (2026-09-09)

### HTTP 경로 및 응답

엔진 base = `/api/v1/admin/fds/decision-trees`, BO base = `/api/v1/bo/fds/decision-trees`.
BO는 typed delegate이며 엔진 미구성 시 503; 엔진 저장소를 직접 조회하거나 stub 정책을 생성하지 않는다.

| method / path suffix | 요청 | 응답 / 권한 |
|---|---|---|
| GET / | query, includeArchived, page(0~1000000), size(1~100; 기본20) | `{rows,total,page,size}` / READ |
| POST / | name, description, definition | Tree / 201 / AUTHOR |
| GET /{treeId} | — | `{tree,versions,deployments}` / READ |
| POST /{treeId}/versions | name, description, definition, expectedRevision | 새 immutable version을 가진 Tree / 201 / AUTHOR |
| GET /{treeId}/versions[/{version}] | — | VersionView 배열 또는 단건 / READ |
| POST /{treeId}/simulations | version, decisionIds(1~50 distinct UUID); Idempotency-Key 필수 | Simulation / 엔진 201(신규)·200(replay), BO 200 / AUTHOR |
| GET /{treeId}/simulations[/{simulationId}] | — | 최근 50건 또는 단건 / READ |
| GET /deployments | — | tenant/workspace의 scope 포인터 목록 / READ |
| POST /{treeId}/deployments | operation(ACTIVATE/STOP/ROLLBACK), channelType, evaluationPhase, version, expectedGeneration, simulationId, reason | `{approvalRequestId,payloadHash,status:SUBMITTED}` / 202 / OPERATE |
| POST /{treeId}/archive | expectedRevision | Tree / 200 / OPERATE |

STOP은 version/simulationId를 보내지 않으며 현재 활성 treeId를 대상으로 한다. ROLLBACK은 같은 활성 트리의 더 낮은 버전과 그 버전의 simulation 증거를 선택한다.
실제 승인/반려는 기존 결재 API를 사용한다. 새 `DECISION_TREE` subject의 checker 권한은 정확히 `SFDS_RULE:APPROVE`이다.

Tree: tenantId, workspaceId, treeId, name, description, latestVersion, revision, archived, createdBy, createdAt, updatedAt.
VersionView: treeId, version, definition, definitionHash, createdBy, createdAt, numericLiterals, browserEditable.
Deployment: channelType, evaluationPhase, treeId(nullable), version(nullable), generation, pendingApprovalId(nullable), updatedBy, updatedAt.

### 숫자 및 개인정보 경계

- Draft/version 요청은 원문 JSON에서 scoped BigDecimal mapper로 파싱한다. BO version definition readback도 exact decimal reader를 사용한다. 다른 API의 mapper 설정은 바꾸지 않는다.
- numericLiterals는 nodeId별 정확한 숫자 표기 문자열이다. 브라우저가 손실 없이 편집할 수 없는 버전은 browserEditable=false로 제공한다. 화면은 이 값을 정확히 조회하고 편집만 제한하며, 저장된 버전의 simulation/배포는 가능하다. API BigDecimal 값의 범위를 JS Number에 맞춰 줄이지 않는다.
- 문자열 literal은 기존 ForbiddenPiiScanner의 이메일/주민번호/카드/계좌 패턴을 검사한다. opaque ref의 숫자 예외와 canonical hex hash는 유지한다. hash 항목의 원문 전화/계좌형 값은 거부한다. 에러·trace에 거부된 원문 값을 넣지 않는다.
- TreeEvaluation.path는 nodeId, featureKey, operator, branch(TRUE/FALSE/MISSING)만 반환한다. 실제 고객 피처 값과 비교 literal은 결정 trace에 포함하지 않는다.

### 결정 증거 및 실패

신규 정상 결정 응답은 기존 필드에 ruleDecision, treeEvaluation을 추가한다. 상세 BO projection은 evaluationPhase도 전달한다.
TreeEvaluation = status, treeId, version, definitionHash, outcome(nullable), leafId, reasonCode, path.
상태는 EVALUATED / NOT_CONFIGURED / NOT_EVALUATED / ERROR이며 simulation은 UNAVAILABLE도 사용한다. 기존 결정의 증거가 없는 경우 nullable로 유지한다.
공통 피처 계산 실패는 기존 fail_policy를 따른다. 트리 자체 오류는 ERROR로 기록하고 기존 룰과 REVIEW fallback을 결합한다.
인입 저장과 평가 트랜잭션은 기존 계약대로 분리된다. 평가 인프라 장애 시 인입은 보존하되 decision=null이며, 부분 결정/조치/outbox는 생성하지 않는다.
`matchedRules`에는 실제 룰만 유지한다. tree-only BLOCK도 기존 BLOCK 통지 채널로 AML에 전달하며, 빈 matchedRules를 가짜 룰로 채우지 않는다.

### 거버넌스·저장

- FDS V37: tree/version/simulation/deployment 4테이블, tenant/workspace 선두 복합키·FK·forced RLS. version update/delete 불가.
- FDS V38: `DECISION_TREE` approval CHECK 확장, simulation 증거 update/delete 불가.
- FDS V39: fds_decisions.tree_evaluation nullable JSONB 추가. 저장 값은 `{ruleDecision,treeEvaluation}`. 기존 자연 멱등키 및 과거 행은 변경하지 않는다.
- 배포 상신/승인은 tree master → scope 포인터 순서로 잠근다. 같은 scope 동시 상신은 1건만 성공한다. 승인 대기 중 새 draft version을 만들어도 pending version/hash는 불변이다.
- 승인 payload는 tree/version/hash·scope·operation·generation·simulationId에 결속한다. JPA approval INSERT는 JDBC 포인터 FK 갱신 전에 flush하여 같은 트랜잭션에서 원자적으로 반영한다.
- 조회·시뮬레이션·승인 후 사용 버전 이력은 archive 후에도 보존한다. 기존 event/decision/outbox replay는 최초 결과를 반환하며 tree 배포 교체로 중복 조치를 생성하지 않는다.

### BO 메뉴 및 시뮬레이터

FDS 설정의 정책 그룹에 `/fds/decision-trees`를 추가한다(기존 FDS 14개 메뉴 보존 + 신규1 = 15).
`/new`는 AUTHOR, 목록/상세는 READ, 배포·중지·롤백·보관은 OPERATE, 결재는 APPROVE로 분리한다.
화면은 조건·TRUE/FALSE/MISSING 분기 편집, 버전 비교, 저장 결정 표본 simulation, 성공 이력 선택, 승인 요청, 결정 경로 조회를 제공한다.
sim-web `setup.fds-tree`는 BO에서 설정한 포인터를 읽기 확인하며, `fds.dual-evaluate`는 명시 memberRef/ref로 실제 거래를 인입한다.
미완성 preview는 requiredParams/body=null/signed=false를 반환하고 execute는 필수 키 누락을 거부한다. 사업 식별자를 자동 채우지 않는다.

### 검증 증거의 구분

FDS-C46~C51은 REST 경계/조합/버전/복원과 실제 BO·sim-web 브라우저 흐름을 검증한다.
2×2 테넌트·워크스페이스 및 ASYNC lookup, 저장소 손상·인프라 fault는 명시된 Testcontainers 클래스와 결합한다. 이러한 in-process 증거를 실제 REST 실행이라고 표시하지 않는다.
기존 FDS45 + 신규6 + 횡단9 = 60개의 선택된 카탈로그 사례가 gate이며, 모든 결과·원복·미실행 여부는 코드 저장소 PLAN 및 case artifact에 남긴다.
