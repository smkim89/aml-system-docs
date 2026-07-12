# 공통 Machine Authentication 계약 (AML/FDS inbound wire v2)

> **상태**: P0-00 정본, 2026-07-12.
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
| `X-Trace-Id` | 선택 관측성 식별자 | **서명 밖**(9-key `scopeContext`에 포함하지 않음) |
| `X-Correlation-Id` | 선택 업무/호출 상관 식별자 | **서명 밖**(9-key `scopeContext`에 포함하지 않음) |

HTTP header 이름 자체는 대소문자를 구분하지 않지만, 값은 본 규칙대로 해석한다. blank 값은 absent로 보고, nonblank 값은 trim하거나 alias 치환해 canonical 의미를 보정하지 않는다.

서버가 singleton으로 취급하는 보안·canonical header(`Tenant-Id`, `Workspace-Id`, `X-Data-Scope`, `X-User-Subject`, `X-Internal-Service`, `Source-System`, `Idempotency-Key`, `X-Api-Key`, `X-Timestamp`, `X-Signature`, `X-Auth-Version`, `X-Nonce`, `Content-Type`, `Content-Encoding`)와 `X-Trace-Id`는 각각 한 번만 나타나야 한다. 같은 값이라도 두 field-line으로 보내면 body read·credential lookup·nonce 소비 전에 generic 401로 거부한다. `X-Correlation-Id`는 관측성 전파 값일 뿐 현재 singleton/canonical 목록에는 포함되지 않는다.

`X-User-Subject`는 trusted BFF/mesh가 전달한 actor를 v2 서명에 결합한다. AML STR 조회·기안·상신·거부·취소의 감사 actor/maker는 body의 자기주장 값이 아니라 이 서명된 header에서 파생하며, bo-api AML 위임 credential은 엔진 `RoleGuard`가 요구하는 `COMPLIANCE` authority token을 포함해야 한다. 이는 BO edge의 사용자 `AML_COMPLIANCE` RBAC 검사를 대체하지 않는다.

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
- header가 없으면 transition 동안 legacy v1, 명시적 `X-Auth-Version: 1`은 v1, 명시적 `2`는 v2로만 검증한다. **v2 실패 후 v1 재검증 fallback은 없다.** v1 timestamp parser는 기존 client 호환을 위해 RFC3339 offset 표기(예: `+09:00`)를 유지하되 서명에는 전송 문자열을 그대로 사용한다. v2 timestamp는 canonical UTC `Z` 표기만 허용한다.
- v1 canonical material(`timestamp/apiKey/method/path/[actor]/body`)은 전환 호환용 legacy일 뿐 신규 client가 복제할 계약이 아니다. query·tenant·scope·nonce를 결합하는 본 v2를 사용한다.
- v1 사용량이 14일 연속 0이고 등록 client 전환 증거가 확보되면 service policy에서 v1을 끈다. 이후 credential allowlist도 v2-only로 축소한다.
- secret 회전은 기존 credential의 in-place overwrite보다 **새 credential ID를 병행 발급**하는 방식을 기본으로 한다. client를 새 ID/secret으로 전환하고, 최대 clock skew(5분)+nonce TTL(15분)이 지난 뒤 구 credential을 비활성화한다. 평문 secret은 발급 채널 밖에 저장·로그하지 않고 DB에는 AES-GCM `secret_ciphertext`만 둔다.

로컬 credential은 business/demo Flyway seed가 아니라 명시적 infrastructure provisioning이다. `local` 또는 `demo`라는 **positive profile allowlist**와 opt-in property가 모두 참일 때만 provisioner가 생기며, bootstrap bypass property도 같은 두 profile에서만 효력이 있다. 그 밖의 profile(no-profile/custom/staging/production 포함)에서는 property가 설정돼도 bypass를 무시하고 fail-closed한다. provisioner는 32자 이상 환경 secret을 정상 cipher로 암호화해 v2-only row로 저장하고 startup 뒤 평문 참조를 제거한다.

AML local/demo는 REST simulator용 `SIMULATOR_AML_API_KEY`/`SIMULATOR_AML_HMAC_SECRET`과 bo-api 위임용 `BO_AML_API_KEY`/`BO_AML_HMAC_SECRET`을 서로 다른 credential ID/secret으로 provision한다. bo-api credential의 scope union에는 STR 접근용 `COMPLIANCE` authority가 포함된다. FDS local/demo provisioner는 simulator credential을 별도로 만든다. 이 편의 provisioner는 운영 credential lifecycle 구현의 대체물이 아니다.

## 7. 후속 태스크 경계

P0-00은 공통 protocol·credential version·durable nonce 기반만 닫는다. 다음 항목은 **2026-07-12 현재 미완료**이며 본 문서 존재만으로 적용 완료를 주장하지 않는다.

- **P0-01**: `/aml/v1/**` 중립 거래 인입 filter coverage.
- **P0-04**: AML/FDS 내부 service-auth 전 경로와 bo-api→FDS signer 전환.
- **P0-14**: multipart client가 최종 raw bytes를 한 번만 만들고 동일 bytes를 digest/sign/send하는 전환과 production capability guard.
- **P1-02**: 전 machine credential 경로 적용, 생성·scope 변경·유예회전·폐기·last-used 영속 이력, credential별 rate/network/workload 조건과 비민감 실패 metric. P0-00의 protocol allowlist·암호화·권장 회전 절차만으로 이 운영 수명주기가 완료된 것은 아니다.

따라서 각 API는 실제 filter registration과 client signer 전환을 별도 완료 증거로 확인해야 한다. 특히 multipart는 본 raw-byte 계약만 확정됐을 뿐 모든 호출자가 v2로 전환된 것이 아니다.

## 8. 변경 이력

| 일자 | 변경 | 비고 |
|---|---|---|
| 2026-07-12 | P0-00 공통 inbound machine-auth wire v2 신규 정본. versioned canonical request, normalized servlet routing과 ambiguous raw-path 거부, duplicate singleton 거부, raw query, 고정 9-key scopeContext(trace/correlation 제외), raw-body digest, v1 offset 호환/v2 UTC `Z`, durable nonce(TTL `>2×skew`, 기본 cleanup `20×5000/tick`), signed redirect 거부, local/demo positive provisioning, BO `COMPLIANCE` actor 경계, generic error, credential transition, 고정 벡터와 후속 P0/P1 범위를 확정. | 코드 truth=`services/common-security`, `scripts/machine_auth.py`, bo-api `RestClientConfig`/`RestClientConfigTest`, AML V44, FDS V14 |
