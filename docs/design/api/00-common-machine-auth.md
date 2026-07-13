# 공통 Machine Authentication 계약 (AML/FDS inbound wire v2)

> **상태**: P0-03 trusted actor 경계까지 반영, 2026-07-13.
> **적용 대상**: `aml-svc`·`fds-svc`의 `IngestAuthenticationFilter`가 보호하는 서버 간 inbound HTTP 요청.
> **구현 정본**: `aegis-aml/services/common-security`와 저장소 공통 고정 벡터 `aegis-aml/test-vectors/machine-auth-v2.json`.

## 목차

1. [범위와 서명 경계](#1-범위와-서명-경계)
2. [wire v2 헤더](#2-wire-v2-헤더)
3. [canonical request](#3-canonical-request)
4. [검증·replay 의미론](#4-검증replay-의미론)
5. [오류 계약](#5-오류-계약)
6. [credential 전환·회전](#6-credential-전환회전)
7. [후속 태스크 경계](#7-후속-태스크-경계)
8. [변경 이력](#8-변경-이력)

---

## 1. 범위와 서명 경계

- 본 문서는 AML/FDS **인바운드 machine authentication**의 단일 wire 정본이다. API·integration·software 문서는 canonical 공식을 복제하지 않고 본 문서를 참조한다.
- 브라우저 세션/JWT, OAuth2 scope/RBAC, mTLS transport는 별도 인증·인가 계층이다. HMAC 성공은 업무 scope 허용을 대신하지 않는다.
- **아웃바운드 webhook 서명과 혼용하지 않는다.** AML/FDS webhook callback은 기존 `HMAC-SHA256(secret, timestamp + "." + rawBody)`와 `X-Webhook-Timestamp` 계약을 유지한다. 아래 preamble·query·scopeContext·nonce 공식은 inbound 요청에만 적용한다.
- 인증 replay와 업무 멱등은 서로 다른 경계다. `X-Nonce`는 한 HTTP 인증 시도를, `Idempotency-Key`는 업무 명령을 식별한다.
- 서버는 HMAC 입력인 raw URI와 인증 적용 여부를 결정하는 route를 분리한다. 인증 path 매칭은 servlet container가 dispatch한 정규 route(`servletPath + pathInfo`)로 수행하고, 서명에는 최종 raw request URI를 사용한다. 두 의미가 달라질 수 있는 모호한 raw path는 controller 진입 전에 거부한다(§3.1).

## 2. wire v2 헤더

| 헤더 | v2 규칙 | canonical 반영 |
|---|---|---|
| `Tenant-Id` | 필수 | 독립 line |
| `Workspace-Id` | FDS는 선택(부재 시 `default`), AML은 물리 workspace를 사용하지 않아 항상 `default` | `scopeContext.workspace` |
| `X-Data-Scope` | 선택, 부재 시 빈 값 | `scopeContext.data-scope` |
| `X-User-Subject` | trusted BFF/mesh actor가 있을 때 사용 | `scopeContext.user-subject` |
| `X-Internal-Service` | 내부 호출자 식별이 있을 때 사용 | `scopeContext.internal-service` |
| `Source-System` | source header의 **유일한 정본 이름**. `X-Source-System` 등 별칭은 인정하지 않음 | `scopeContext.source-system` |
| `Idempotency-Key` | 업무 계약이 요구할 때 필수 | `scopeContext.idempotency-key` |
| `Content-Type` | 최종 전송 값. multipart면 boundary 포함 | `scopeContext.content-type` |
| `Content-Encoding` | 최종 전송 값 | `scopeContext.content-encoding` |
| `X-Api-Key` | credential ID, 필수 | `scopeContext.credential` |
| `X-Timestamp` | RFC3339 UTC(`Z`), 서버 시각 기준 **±5분** 허용 | 독립 line |
| `X-Auth-Version` | v2 요청은 정확히 `2` | version line |
| `X-Nonce` | CSPRNG 16 bytes를 base64url-no-padding으로 인코딩한 22자 | 독립 line |
| `X-Signature` | `hmac-sha256=<64 lowercase hex>` | canonical bytes의 HMAC-SHA256 결과 |
| `X-Trace-Id` | 선택 관측성 식별자. 공통 안전 경계=trim 후 128자 이하·ISO 제어문자 금지 | **서명 밖**(9-key `scopeContext`에 포함하지 않음) |
| `X-Correlation-Id` | 선택 업무/호출 상관 식별자 | **서명 밖**(9-key `scopeContext`에 포함하지 않음) |

HTTP header 이름 자체는 대소문자를 구분하지 않지만, 값은 본 규칙대로 해석한다. blank 값은 absent로 보고, nonblank 값은 trim하거나 alias 치환해 canonical 의미를 보정하지 않는다.

서버가 singleton으로 취급하는 보안·canonical header(`Tenant-Id`, `Workspace-Id`, `X-Data-Scope`, `X-User-Subject`, `X-Internal-Service`, `Source-System`, `Idempotency-Key`, `X-Api-Key`, `X-Timestamp`, `X-Signature`, `X-Auth-Version`, `X-Nonce`, `Content-Type`, `Content-Encoding`)와 `X-Trace-Id`는 각각 한 번만 나타나야 한다. 같은 값이라도 두 field-line으로 보내면 body read·credential lookup·nonce 소비 전에 generic 401로 거부한다. `X-Correlation-Id`는 관측성 전파 값일 뿐 현재 singleton/canonical 목록에는 포함되지 않는다.

`X-Trace-Id`는 duplicate 검사 뒤 공통 `TraceIdPolicy`가 trim·128자·ISO 제어문자 경계를 검증하고 정규화한 값을 controller의 `@RequestHeader`와 MDC `traceId`에 동일 노출한다. 명시적 causal trace를 가진 background/outbox 감사 write는 그 값을 우선하고, 요청 기반 admin write만 값이 없을 때 MDC를 사용한다. 이 128자는 공통 HTTP/감사 안전 상한이다. **AML canonical ingest는 별도 도메인 계약 `docs/aml-data.md`의 최대 64자를 유지**하므로 65~128자 입력도 인증을 통과한 뒤 업무 검증에서 422로 거부된다. `aml_canonical_events`·CDD history 등 canonical lineage의 `trace_id VARCHAR(64)`를 감사 폭에 맞춰 넓히지 않는다.

`X-User-Subject`는 trusted BFF/mesh가 전달한 actor를 v2 서명에 결합한다. HMAC 검증을 통과한 뒤 공통 filter가 최대 128자·제어문자/CRLF 금지 검증까지 마친 값만 내부 `VERIFIED_USER_SUBJECT_ATTRIBUTE`로 승격한다. HMAC이 유효해도 이 subject 경계를 어기면 verified attribute를 만들지 않고 generic 인증 실패(401)로 끝난다. controller는 raw header를 직접 읽지 않고 `TrustedActorResolver`를 사용한다. resolver는 이 signed subject를 maker/checker/actor 정본으로 반환하며, body/query의 기존 actor 필드는 생략 가능하고 존재하면 trim·대소문자 무시 기준으로 같은 subject인지 확인하는 compatibility assertion일 뿐이다. assertion 불일치·누락 actor·잘못된 body 값은 업무 command 전에 400으로 거부한다.

explicit local/demo bootstrap 요청은 공통 filter가 실제 `BOOTSTRAP_BYPASS_ATTRIBUTE=Boolean.TRUE`를 설정한 경우에만 raw `X-User-Subject`를 resolver 입력으로 사용할 수 있다. bootstrap subject도 filter가 같은 128자/제어문자 경계를 먼저 검증한다. 외부 header로 marker를 주장하거나 production에서 bootstrap actor를 사용하는 경로는 없다. bo-api AML 위임 credential은 엔진 `RoleGuard`가 요구하는 `COMPLIANCE` authority token을 포함해야 한다. 이는 BO edge의 사용자 `AML_COMPLIANCE` RBAC 검사를 대체하지 않는다.

## 3. canonical request

### 3.1 byte 형식

아래 10개 line을 **UTF-8**, 구분자 **LF(`0x0A`)**, **마지막 LF 없음**으로 연결한다.

```text
AEGIS-HMAC-SHA256
2
METHOD
rawPath
rawQuery
Tenant-Id
scopeContext
sha-256=<raw-body lowercase hex>
X-Timestamp
X-Nonce
```

- `METHOD`는 대문자 HTTP token이다.
- `rawPath`는 최종 origin-form request-target의 raw path다. decode/normalize/re-encode하지 않고 percent-encoding을 전송값 그대로 보존한다. query·fragment를 포함하지 않으며 control character를 거부한다.
- 인증 path coverage/scope 판단에는 raw path를 쓰지 않고 servlet의 정규 dispatch route를 사용한다. raw path에 `//`, literal/percent-encoded dot segment, `;` matrix parameter, backslash, percent-encoded `/`·backslash, literal/percent-encoded control, malformed percent escape가 있으면 route와 서명 경계가 어긋날 수 있으므로 generic 401로 거부한다.
- `rawQuery`는 선행 `?` 없는 최종 raw query다. query가 없으면 빈 line이다.
- `rawQuery`는 decode/sort/re-encode하지 않는다. pair 순서, duplicate key, bare/blank 값, `+`, percent-encoding의 대소문자까지 **전송 request-target 그대로** 서명한다.
- content digest는 JSON·empty·multipart를 구분하지 않고 **최종 전송 raw body bytes**에 SHA-256을 적용한다. empty body digest는 `sha-256=e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`다.
- path/query fragment와 raw control character는 거부한다.
- 최종 `X-Signature`는 `hmac-sha256=` + `HMAC-SHA256(UTF-8 secret bytes, 위 canonical bytes)`의 64자리 lowercase hex다. 비교는 constant-time으로 수행한다.
- 서명된 요청은 redirect를 자동 추종하지 않는다. `3xx Location`은 동일 origin 여부와 무관하게 원 응답으로 반환/실패 처리하며, 다른 target을 호출해야 하면 최종 URI를 확정한 뒤 **새 timestamp·nonce·signature**로 새 요청을 만든다. 공통 Python simulator transport는 same-origin/cross-origin redirect를 모두 거부한다. bo-api 공용 engine `RestClient`도 `ClientHttpRequestFactorySettings.Redirects.DONT_FOLLOW`를 강제하며, 실제 origin 302 검증은 302를 그대로 관찰하고 redirect target 0회·`X-Api-Key` 미전달을 확인한다(`RestClientConfigTest`).

### 3.2 고정 `scopeContext`

아래 **9개 key를 ASCII 사전순으로 항상 전부 포함**한다. 없는 값도 `key=`로 포함하고, `key=RFC3986-percent-encoded(value)`를 `&`로 연결한다.

```text
content-encoding=&content-type=&credential=&data-scope=&idempotency-key=&internal-service=&source-system=&user-subject=&workspace=
```

고정 순서는 다음과 같다.

1. `content-encoding`
2. `content-type`
3. `credential`
4. `data-scope`
5. `idempotency-key`
6. `internal-service`
7. `source-system`
8. `user-subject`
9. `workspace`

value는 UTF-8 bytes 기준 RFC3986 percent-encoding을 적용한다. unreserved(`A-Z a-z 0-9 - . _ ~`)만 그대로 두고 나머지는 `%HH` 대문자 hex로 인코딩한다. `credential`은 `X-Api-Key`, `source-system`은 정확히 `Source-System`에서만 가져온다. FDS workspace는 `Workspace-Id` 또는 `default`, AML workspace는 header와 무관하게 `default`다.

### 3.3 공통 고정 벡터

Java server/client와 Python signer가 함께 소비하는 단일 벡터는 **`aegis-aml/test-vectors/machine-auth-v2.json`** 이다. 문서 예시를 별도 벡터로 만들지 않는다. 벡터는 최종 headers/request/body, `scopeContext`, content digest, LF 전문 canonical string, expected signature를 함께 고정한다.

## 4. 검증·replay 의미론

검증 순서는 다음과 같다.

1. duplicate singleton header, servlet 정규 route coverage, 모호한 raw path를 거부한다.
2. 제한된 크기로 raw body를 한 번 읽고 tenant/workspace와 credential을 해소한 뒤 service policy와 credential `allowed_protocol_versions`의 교집합으로 protocol을 허용한다.
3. timestamp freshness, version·nonce 문법, canonical request와 HMAC을 검증한다.
4. **유효한 서명에 한해** nonce를 PostgreSQL에서 원자 소비한다.
5. nonce 소비가 커밋된 뒤 scope 검사와 controller/usecase를 실행한다.
6. HMAC 검증 성공 요청에 한해 signed `X-User-Subject`를 내부 verified request attribute로 승격한다. scope/controller는 actor가 필요할 때 이 attribute만 소비한다.

replay 불변식은 다음과 같다.

- nonce namespace는 credential 전체다. AML PK는 `(tenant_id, credential_id, nonce_hash)`, FDS PK는 `(tenant_id, workspace_id, credential_id, nonce_hash)`다. query/context/body를 바꿔도 같은 credential+nonce를 다시 사용할 수 없다.
- nonce TTL은 소비 시각부터 기본 **15분**이며 설정값은 반드시 `2 × timestamp skew`보다 **엄격히 길어야** 한다(기본 skew 5분). 만료 전 중복은 401이며, 만료된 row는 원자 upsert로 재사용 가능하다.
- invalid signature는 nonce를 소비하지 않는다.
- valid signature의 nonce는 `REQUIRES_NEW` 트랜잭션으로 scope/controller보다 먼저 커밋한다. 이후 4xx/5xx 또는 업무 트랜잭션 rollback이 발생해도 해당 인증 요청은 replay할 수 없다.
- 동일 업무 `Idempotency-Key` 재시도는 **새 nonce와 새 signature**로 인증을 통과한 뒤 기존 업무 멱등 결과를 받아야 한다.
- replay store가 불가하면 fail-closed한다. raw secret·raw nonce·raw body·signature는 replay DB나 로그에 저장하지 않는다. DB에는 `nonce_hash`, canonical request/context hash, content digest, protocol, 소비/만료 시각만 저장한다.
- 만료 정리는 기본 1분 주기, tick당 최대 **20 × 5,000건**을 짧고 독립적인 `REQUIRES_NEW` transaction의 `FOR UPDATE SKIP LOCKED` batch delete로 처리한다. 마지막 batch가 5,000건 미만이면 그 tick을 조기 종료한다.

## 5. 오류 계약

외부 응답은 원인 oracle이 되지 않도록 서비스 prefix(`AML`/`FDS`)만 다르고 동일한 generic detail을 사용한다.

| code | HTTP | 의미 |
|---|---|---|
| `<prefix>-AUTH-002` | 401 | invalid/disabled credential, 허용되지 않은 protocol, missing·malformed·replayed nonce, stale timestamp, canonical/signature/digest 불일치. detail은 `Authentication failed`로 통일 |
| `<prefix>-AUTH-003` | 503 | replay protection store 불가. `Authentication service unavailable`, fail-closed |
| `<prefix>-AUTH-004` | 413 | 인증 전에 허용 raw-body 상한 초과. `Request body too large` |

`Tenant-Id`/`X-Api-Key` 자체가 없는 요청의 기존 `<prefix>-AUTH-001`과 scope 부족의 `<prefix>-AUTHZ-*` 계약은 유지한다. 내부 로그/metric에서는 운영 진단용 reason을 구분할 수 있으나 secret·signature·raw nonce/body를 기록하지 않는다.

## 6. credential 전환·회전

- `allowed_protocol_versions`는 non-empty JSON array이며 값은 `v1`/`v2` 부분집합이다.
- migration 당시 **기존 credential row는 `["v1","v2"]`로 backfill**, migration 이후 **신규 credential은 `["v2"]`가 기본**이다. service policy가 이 allowlist를 더 좁힐 수 있다.
- normalized API route policy도 service/credential 교집합을 더 좁힐 수 있다. P0-01의 AML
  `/aml/v1/**`는 migration 전 credential이 `["v1","v2"]`여도 v2-only이며, 다른 기존 AML/FDS
  route의 측정된 전환은 유지한다. P0-03에서 filter coverage 누락을 복구한 기존 FDS
  `/api/v1/evidence/fds/**`도 이 이중 전환 대상이며 `canonicalV2RequiredPathPrefixes`에 포함하지 않는다.
- header가 없으면 transition 동안 legacy v1, 명시적 `X-Auth-Version: 1`은 v1, 명시적 `2`는 v2로만 검증한다. **v2 실패 후 v1 재검증 fallback은 없다.** v1 timestamp parser는 기존 client 호환을 위해 RFC3339 offset 표기(예: `+09:00`)를 유지하되 서명에는 전송 문자열을 그대로 사용한다. v2 timestamp는 canonical UTC `Z` 표기만 허용한다.
- v1 canonical material(`timestamp/apiKey/method/path/[actor]/body`)은 전환 호환용 legacy일 뿐 신규 client가 복제할 계약이 아니다. query·tenant·scope·nonce를 결합하는 본 v2를 사용한다.
- v1 사용량이 14일 연속 0이고 등록 client 전환 증거가 확보되면 service policy에서 v1을 끈다. 이후 credential allowlist도 v2-only로 축소한다.
- secret 회전은 기존 credential의 in-place overwrite보다 **새 credential ID를 병행 발급**하는 방식을 기본으로 한다. client를 새 ID/secret으로 전환하고, 최대 clock skew(5분)+nonce TTL(15분)이 지난 뒤 구 credential을 비활성화한다. 평문 secret은 발급 채널 밖에 저장·로그하지 않고 DB에는 AES-GCM `secret_ciphertext`만 둔다.

로컬 credential은 business/demo Flyway seed가 아니라 명시적 infrastructure provisioning이다. active profile이 nonempty이고 모든 값이 exact `local` 또는 `demo`인 **positive profile allowlist**와 opt-in property가 모두 참일 때만 provisioner가 생기며, bootstrap bypass property도 같은 판정에서만 효력이 있다. `local+demo`는 허용하지만 no-profile/custom/staging/production과 `local+staging`·`demo+qa` 같은 mixed profile에서는 property가 설정돼도 bypass를 무시하고 fail-closed한다. provisioner는 32자 이상 환경 secret을 정상 cipher로 암호화해 v2-only row로 저장하고 startup 뒤 평문 참조를 제거한다.

P0-04 이후 local/demo는 여섯 logical caller-purpose class를 서로 다른 credential ID/secret으로
provision한다: simulator→AML, simulator→FDS, BO→AML, BO→FDS, AML→FDS customer profile,
FDS→AML escalation. “여섯”은 global secret 수가 아니라 purpose 분리를 뜻하며, shared deployment의
credential은 exact `(purpose, tenantId, workspaceId)` target에 귀속된다. BO→AML credential의 scope
union에는 STR 접근용 `COMPLIANCE`와 internal PII reveal용 `aml:pii:reveal`이 포함된다. BO→FDS는
운영 typed API용 9 scope만 가지며 ingest/decision/internal-profile scope를 가지지 않는다. 서비스 간
credential은 각각 `fds:internal:customer-profile:write` 또는
`aml:internal:fds-escalation:write` 단일 scope만 가진다. 이 편의 provisioner는 운영 credential
lifecycle 구현의 대체물이 아니다.

## 7. 후속 태스크 경계

P0-00은 공통 protocol·credential version·durable nonce 기반을 닫았고, P0-01은 AML
`/aml/v1/**`를 normalized servlet route 기준 실제 filter 대상에 포함했다. 이에 따라
`POST /api/v1/aml/events`와 `POST /aml/v1/transaction-events`는 모두 `aml:event:write`를
요구하며 `/aml/v1/**` authenticated traffic은 route policy로 v2-only다. scope/role request
attribute가 없으면 공통 filter가 local/demo positive profile과
opt-in을 확인한 뒤 내부 request attribute에 정확히 `Boolean.TRUE`로 설정한 bootstrap marker가
있는 경우만 허용하고, 그 밖에는 403으로 fail-closed한다. marker는 외부 wire header가 아니며
호출자가 스스로 주장할 수 없다.

P0-01 인증 실패는 controller/usecase에 진입하지 않으므로 canonical event·PII vault·WLF·TM·CTR/STR·RA
업무 row를 만들지 않는다. 단, 정상 서명 검증 뒤 scope에서 거부된 403은 §4 순서대로 인증 nonce를 이미
소비하므로 `aml_auth_nonces` row는 유지된다. Neutral ingest의 `X-Data-Scope`는 P0-01에서 v2
canonical 무결성에만 결합한다. 기존 서명 뒤 값을 바꾸면 401이고, valid signature로 새로 서명한 값에
대한 credential별 data-scope allowlist/인가 모델은 이 작업에서 추가하지 않는다.

P0-03은 signed `X-User-Subject`와 업무 actor 사이의 마지막 경계를 닫는다. AML admin write의 legacy
`makerId`/`actor`/`checkerId`는 신뢰 원천이 아니며 `TrustedActorResolver`가 반환한 subject와 일치할 때만
허용한다. verified attribute는 서명 검증 전에 생성하지 않고, bootstrap 예외도 위 positive-profile
marker에 한정한다. 이는 machine-auth scope 검사와 maker≠checker 4-eyes 검사를 모두 보완하며 어느 쪽도
대체하지 않는다.

P0-04는 내부 REST와 BO→FDS의 실제 caller 전환을 완료한다. FDS
`/internal/v1/fds/**`와 AML `/internal/v1/aml/**`는 normalized route 기준 filter coverage와
canonical v2-only 정책을 가지며, spoofed `X-Internal-Service`만으로 controller에 진입할 수 없다.
AML→FDS profile, FDS→AML non-AWS REST fallback, bo-api→FDS typed client는 최종 ASCII URI와 한 번
직렬화한 동일 body bytes를 sign/send한다. credential resolver는 exact
`(purpose,tenantId,workspaceId)`만 선택하며 global/cross-target fallback을 허용하지 않는다. 유효한
서명 뒤 endpoint scope가 부족하면 nonce가 소비된 403, 서명·target·body/context 변조는 401이다.
BO의 human capability와 engine machine scope는 별도 계층이며 catch-all proxy는 없다. local lifecycle은
AML/FDS bootstrap bypass를 끈 상태를 정본으로 한다.

다음 항목은 **2026-07-13 현재 미완료**이며 본 문서 존재만으로 적용 완료를 주장하지 않는다.

- **P0-14**: multipart client가 최종 raw bytes를 한 번만 만들고 동일 bytes를 digest/sign/send하는 전환과 production capability guard.
- **P1-02**: 전 machine credential 경로 적용, 생성·scope 변경·유예회전·폐기·last-used 영속 이력, credential별 rate/network/workload 조건과 비민감 실패 metric. P0-00의 protocol allowlist·암호화·권장 회전 절차만으로 이 운영 수명주기가 완료된 것은 아니다.

따라서 각 API는 실제 filter registration과 client signer 전환을 별도 완료 증거로 확인해야 한다. 특히 multipart는 본 raw-byte 계약만 확정됐을 뿐 모든 호출자가 v2로 전환된 것이 아니다.

## 8. 변경 이력

| 일자 | 변경 | 비고 |
|---|---|---|
| 2026-07-13 | P0-04 내부 service-auth·BO→FDS 적용. 두 internal prefix를 v2-only로 닫고 AML→FDS profile/FDS→AML REST fallback/BO→FDS typed client가 final URI·same bytes를 서명한다. exact target credential, service별 최소 scope, bootstrap-off local lifecycle, 6 logical purpose provisioning을 확정했다. | wire 공식 변경 없음. 신규 scope=`fds:internal:customer-profile:write`, `aml:internal:fds-escalation:write`; multipart는 P0-14 fail-closed 유지 |
| 2026-07-13 | P0-03 trusted actor·trace 계약. HMAC 성공 뒤 signed subject의 128자·제어문자 경계를 filter가 검증한 뒤에만 `VERIFIED_USER_SUBJECT_ATTRIBUTE`를 생성하고, `TrustedActorResolver`가 signed/bootstrap-marked subject와 legacy body/query assertion 일치를 검증해 AML admin maker/checker/audit actor의 유일한 입력으로 사용한다. 공통 `X-Trace-Id`는 trim·128자·제어문자 금지 후 MDC로 전파하되 AML canonical ingest는 64자/422 계약을 유지한다. | wire/header/canonical bytes 변경 없음. invalid signed subject/공통 trace=generic 401, body assertion 불일치=400, canonical trace 65~128=422, raw `X-User-Subject` 직접 소비 금지 |
| 2026-07-12 | P0-01 AML neutral ingest 인증 우회 차단. `/aml/v1/**` 실제 filter coverage, 두 AML ingest의 `aml:event:write`, scope/role attribute 부재 시 공통 `Boolean.TRUE` bootstrap marker 외 403, 인증 실패 업무 row 0, valid-signed scope 403의 nonce 보존, neutral `X-Data-Scope` tamper 401 경계를 확정했다. | API/DB 스키마 무변경. AML filter/guard·실 filter-chain 테스트가 코드 truth |
| 2026-07-12 | P0-00 공통 inbound machine-auth wire v2 신규 정본. versioned canonical request, normalized servlet routing과 ambiguous raw-path 거부, duplicate singleton 거부, raw query, 고정 9-key scopeContext(trace/correlation 제외), raw-body digest, v1 offset 호환/v2 UTC `Z`, durable nonce(TTL `>2×skew`, 기본 cleanup `20×5000/tick`), signed redirect 거부, local/demo positive provisioning, BO `COMPLIANCE` actor 경계, generic error, credential transition, 고정 벡터와 후속 P0/P1 범위를 확정. | 코드 truth=`services/common-security`, `scripts/machine_auth.py`, bo-api `RestClientConfig`/`RestClientConfigTest`, AML V44, FDS V14 |
