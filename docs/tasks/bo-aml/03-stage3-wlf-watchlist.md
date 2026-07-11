# BOA-S3 · WLF 검토·엔진 설정·명단 운영 (AML-WLF-001~005 · AML-WL-001/002/003)

> **목표**: 요주의 명단 필터링의 전 흐름 — SANCTIONS/PEP 엔진 프로필 설정(Policy Pack 4-eyes)→실 REST 평가→검토 큐→판정(4-eyes)→상위승인→처리 이력→시뮬레이션/임의 수행, 명단 소스→임포트 디프 승인→내부 명단·오탐 면제 생명주기.
> **선행**: BOA-S1. **PPT**: 슬라이드 10~20. AML-WLF-005는 원본 PPT 슬라이드 없음(Markdown-only, PRD §12-B.8 정본).

## 공통 참고 문서
- PRD §3.1~§3.3(WLF 3탭 흐름·상태머신 §1.7)·§12-B.1(WLF-004)·**§12-B.8(WLF-005)**·§4.1(WL-001)·§12-A.2(WL-002)·§12-B.5(WL-003)
- API `02-aml-api.md`: `GET .../screenings?status=`·`GET .../screenings/{id}`·`POST .../screenings/{id}/decision`🔒(`WLF_DECISION`)·`POST .../screenings/fp-whitelist`🔒(`FP_WHITELIST`)·**`GET .../wlf-engine-config`·`POST .../wlf-engine-config:change`🔒(`POLICY_PACK`)**·approvals `:approve/:reject`·watchlist-sources/imports/`{ver}:apply`🔒(`WATCHLIST_IMPORT`)·watchlist-entries
- DB `02-aml-db.md`: `screening_status` §5.5(POSSIBLE_MATCH→…→NO_MATCH)·명단 테이블 §3.x / 표시 = PRD 부록 F
- WLF SANCTIONS/PEP 프로필(6가중치·negative penalty·review/high confidence 임계)·WLF 전용 룰버전 = **Policy Pack 단일 정본**. AML-WLF-005에서 typed 편집하되 변경은 기존 `POLICY_PACK` 4-eyes(별도 저장소 금지 — PRD §3.1 BR-009·§12-B.8).

## 태스크

| ID | 구분 | 태스크 | 참고 문서 | Effort | 의존 |
|---|---|---|---|---|---|
| BOA-S3-01 | BE | **스크리닝·판정 프록시** — screenings 목록(status별)/상세·`decision` 상신🔒·fp-whitelist 등록🔒·approvals 승인/반려 위임 + 감사 | API(스크리닝·결재) / PRD §3.1~§3.3 BR 전수 | 3 | S1 |
| BOA-S3-02 | FE | **AML-WLF-001 ① 검토 필요** — 큐 목록 + 하단 master-detail 3탭(매칭 후보·근거/점수 분해/이전 판정 이력) + `appliedPolicy`(프로필·두 임계·confidenceBand·config/ruleVersion·definitionHash) + 판정 드롭다운 4종·`[오탐 면제 등록(2인)]`·상단 `[시뮬레이션]`→WLF-004 | PRD §3.1(BR 전수) / PPT 슬라이드 10 | 4 | S3-01 |
| BOA-S3-03 | FE | **AML-WLF-002 ② 상위 승인** — ESCALATED 큐·[심사] 패널(상신 판정·이전 이력)·승인(2인)→확정+케이스 생성 / 반려→① 회신 | PRD §3.2(BR-001~006) / PPT 슬라이드 11 | 3 | S3-01 |
| BOA-S3-04 | FE | **AML-WLF-003 ③ 처리 이력** — 5카드(확정·오탐·자동낮춤·면제·평균 SLA)·이력 표(판정자/승인자)·`[면제 현황 ▶ → AML-WL-003 ②]`·읽기 전용 | PRD §3.3(BR-001~006) / PPT 슬라이드 12 | 2 | S3-01 |
| BOA-S3-05 | **SPEC** | **시뮬레이션·임의 수행 API 명세 확정(선행)** — `POST .../screenings:simulate`(분석 전용)·`:bulk-run`(POSSIBLE_MATCH 생성·rate limit·감사 카테고리) 확정 → API 문서 반영 | PRD 부록 E v6.0-1(오픈결정)·§12-B.1 | 2 | — |
| BOA-S3-06 | BE | **시뮬레이션·임의 수행 프록시** — simulate(결재 불필요)·bulk-run(파일 업로드→토큰화 즉시·원문 미보존 D-05·429) 위임 | BOA-S3-05 확정 명세 / PRD §12-B.1 BR-001~003 | 3 | S3-05 |
| BOA-S3-07 | FE | **AML-WLF-004 2탭** — ①단건 시뮬레이션(이름·한글→영문 변환·`sourceTypes` 명단군 선택·ACTIVE 프로필/임계·매칭 근거 분해) ②임의 수행(템플릿 다운로드→업로드→일괄 수행→이력·검출▶WLF-001 필터) | PRD §12-B.1 / PPT 슬라이드 13~14 | 3 | S3-06 |
| BOA-S3-08 | BE | **명단 소스·임포트 프록시** — watchlist-sources CRUD·imports(diff 생성)·`{ver}:apply`🔒·watchlist-entries(masked) 위임 | API(watchlist) / PRD §4.1(BR-001~007)·§12-A.2 | 2 | S1 |
| BOA-S3-09 | FE | **AML-WL-001 3탭** — ①소스 목록(신선도·`[시뮬레이션]`→WLF-004) ②임포트 이력(검토대기▶WL-002) ③명단 엔트리 조회(토큰 hash·원문 reveal) | PRD §4.1(BR-007 트리거 포함) / PPT 슬라이드 15~17 | 3 | S3-08 |
| BOA-S3-10 | FE | **AML-WL-002 디프 승인** — 변경분 요약/검증 게이트(급증·서명·checksum)·디프 표(추가/변경/삭제)·`[적용 상신(2인)]`→승인 시 활성 버전 승격+재스크리닝 안내 | PRD §12-A.2 / PPT 슬라이드 18 | 3 | S3-08 |
| BOA-S3-11 | **SPEC** | **내부 명단·면제 생명주기 API 명세 확정(선행)** — `entries:draft`(수기→diff 초안)·`GET .../screenings/fp-whitelist`·`:revoke`🔒·만료 자동 전이 경로 확정 → API 문서 반영 | PRD 부록 E v7.0-1(오픈결정)·§12-B.5 | 2 | — |
| BOA-S3-12 | BE | **내부 명단·면제 프록시** — entries:draft(WL-002 apply 재사용)·fp-whitelist 목록·revoke🔒 위임 | BOA-S3-11 / PRD §12-B.5 BR-001~003 | 2 | S3-11 |
| BOA-S3-13 | FE | **AML-WL-003 2탭** — ①내부 요주의 명단(수기 등록 폼→diff 초안→WL-002 4-eyes·발효일) ②오탐 면제 관리(4카드·활성/만료/해제 생명주기·`[면제 해제(2인)]`·만료 D-7 ⚠) | PRD §12-B.5 / PPT 슬라이드 19~20 | 3 | S3-12 |
| BOA-S3-14 | BE | **WLF 엔진 프로필 폐루프** — Policy Pack `parameters`의 `wlf.*` typed projection/change, SANCTIONS/PEP 닫힌 스키마 검증·WLF 전용 ruleVersion/hash, 6가중치+negative/address 평가 실적용, PEP/RCA 프로필 매핑, 평가당 ACTIVE snapshot 1회 pin, expected rule 낙관적 잠금·DRAFT 1건·반려 REJECTED 종결, 결과 `appliedPolicy` 스냅샷·FP 룰버전 일치 | PRD §3.1 BR-009/012·§12-B.8 / API·DB WLF config | 5 | S1 |
| BOA-S3-15 | BE | **WLF 설정 BFF·메뉴** — `GET /api/v1/bo/aml/wlf-engine-config`·`POST .../wlf-engine-config:change` fail-closed 위임, `aml:admin:policy`, `/aml/wlf-engine` 동적 메뉴·AML-WLF-005 권한 시드(`BO_SUPER_ADMIN`/`AML_POLICY_ADMIN`) | PRD §12-B.8·부록 A/B / API WLF config | 2 | S3-14 |
| BOA-S3-16 | FE | **AML-WLF-005 3탭** — ①버전 현황 ②프로필 기준(SANCTIONS/PEP 하위 탭) ③ACTIVE 단건 simulation(`sourceTypes`), RA 모델 관리 동형 카드/편집 UX·diff·미저장값 시뮬레이션 제외 경고·`POLICY_PACK` 상신 상태, WLF 검토 `appliedPolicy` 표시 | PRD §12-B.8 / **PPT 없음(Markdown-only)** | 4 | S3-14·S3-15 |
| BOA-S3-17 | QA | **실 REST 시뮬레이터 폐루프** — Admin simulation 대상유형·DOB·국가·문서 hash/`sourceTypes` 확인→설정 A/B 각각 승인 실행→Public screen PEP/제재 인입→가중치·negative penalty·밴딩·프로필·rule/hash 확인→동일 멱등키 replay→기존 결과 불변→최초 profile 값 승인 재적용(disposable DB·mutation opt-in, 이력/FP version 비가역) | PRD §12-B.8 BR-006 / `docs/aml-data.md` | 3 | S3-14~16 |

## DoD
- WLF 상태머신(§1.7) 전이 전수 E2E: 검토→상신→상위승인/반려 회신→처리 이력, 확정 시 케이스 생성 링크.
- 임의 수행 검출 건이 ① 검토 필요 큐에 유입. 면제 만료/해제 → 재스크리닝 순환 안내 표시.
- `SPEC` 2건(S3-05·S3-11) 확정 전 해당 BE/FE 착수 금지. 판정·면제·임포트 적용 전부 결재함(S6)에 수렴.
- **WLF 설정 변경은 `POLICY_PACK` 4-eyes EXECUTED 전 평가 불변, 이후 신규 평가부터 적용**. high confidence는 우선순위/evidence일 뿐 자동 TRUE_MATCH 금지. 기존 결과는 당시 `appliedPolicy` 스냅샷 유지.
- disposable local DB에서 `WLF_CONFIG_ALLOW_MUTATION=1`을 명시하고 Admin simulation의 실 입력/`sourceTypes`와 실제 aml-svc Public REST의 SANCTIONS/PEP 설정 A/B 가중치·negative penalty 차이·멱등 replay·과거 결과 불변을 검증한 뒤 최초 profile 값을 새 ruleVersion으로 재적용한다. 정책/승인 이력과 FP whitelist version은 롤백되지 않는다. bo-api stub·화면 mock·DB 직접 시드는 DoD 증거로 인정하지 않는다.
