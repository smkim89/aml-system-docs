# BOF-S1 · 공통 기반 (스캐폴딩·인증·레이아웃·프록시) — bo-aml과 공유

> **목표**: 화면 1장도 만들기 전에 필요한 공통 기반을 끝낸다. 이 Stage 산출물은 **FDS·AML 양쪽 콘솔이 공유**한다(BOA-S1은 AML 추가분만).
> **선행**: 없음. **위치**: `aegis-aml/services/bo-web`, `services/bo-api`.

## 공통 참고 문서
- 아키텍처·스택·디렉토리 정본: `.claude/skills/_shared/target-architecture.md` §2·§3·§4
- 참조 레포: bo-web=`/Users/smkim/workspace/hanpass/hanpassr-backoffice`, bo-api=`/Users/smkim/workspace/hanpass/hanpassj-backoffice`, 모노레포 빌드=`/Users/smkim/workspace/hanpass/hanpass-ph`(buildSrc·libs.versions.toml)
- 호출 경계·인증: FDS API `docs/design/api/01-fds-api.md` §2(인증·테넌시)·§11(bo-api 소유) / AML API `docs/design/api/02-aml-api.md` §1·§9
- 권한 Role·scope: FDS PRD §1.3·§16.2 / AML PRD §1.4·부록 B

## 태스크

| ID | 구분 | 태스크 | 참고 문서 | Effort | 의존 |
|---|---|---|---|---|---|
| BOF-S1-01 | BE | **bo-api 스캐폴딩** — `services/bo-api` Gradle 모듈(buildSrc 컨벤션 플러그인 적용), `com.aegis.backoffice` 패키지-바이-피처 골격(`auth/ tenant/ dashboard/ proxy/ audit/ menu/ setting/`), Flyway·PostgreSQL·docker-compose 연결 | target-architecture §2·§3(bo-api) · hanpass-ph `buildSrc/` · hanpassj-backoffice 패키지 구조 | 3 | — |
| BOF-S1-02 | BE | **인증·세션·RBAC** — Spring Security 로그인/세션(또는 JWT), Role(`SFDS_PLATFORM_OPS/ADMIN·SFDS_VIEWER/AUTHOR/APPROVER/OPS/ANALYST/ADMIN` + AML scope 13종)·메뉴/화면 권한 평가, 사용자·권한 변경 감사 | FDS PRD §1.3(권한 매핑)·§16.2 / AML PRD §1.4·부록 B / hanpassj-backoffice `auth·admin` 피처 | 4 | S1-01 |
| BOF-S1-03 | BE | **테넌시 컨텍스트 전파** — 요청별 `Tenant-Id`/`Workspace-Id`/data-scope 해석 → 엔진 위임 호출 헤더 전파, 크로스 고객사는 플랫폼 Role만 허용 | FDS API §2(헤더 규약) / AML API §1.1(`Tenant-Id`·RLS·`AML.TENANT_MISMATCH`) / target-architecture §4(멀티테넌시 키) | 3 | S1-02 |
| BOF-S1-04 | BE | **엔진 Admin API 위임 프록시 골격** — `/api/v1/admin/{fds\|aml}/**` → fds-svc/aml-svc 패스스루(인증·감사·traceId·타임아웃·에러 매핑), 멱등키·`Idempotency-Key` 전달 | FDS API §3(멱등·에러)·§11 / AML API §1(횡단 규약)·§4(HTTP 상태) / target-architecture §4(관측성 traceId) | 3 | S1-03 |
| BOF-S1-05 | BE | **bo-api 소유 집계 API 골격** — `/api/v1/bo/{fds\|aml}/**` 컨트롤러 베이스(30~60초 캐시·read-only·raw PII 미포함 규칙), 대시보드용 집계 서비스 토대 | FDS API §11(소유 경계) / AML API §9 / FDS PRD §2(대시보드 원칙) / AML PRD §2.1 | 3 | S1-03 |
| BOF-S1-06 | FE | **bo-web 스캐폴딩** — `services/bo-web` Next.js 16(App Router)+React 19+TS+Tailwind v4 초기화, 디렉토리 `app/ components/ lib/ hooks/ context/ i18n/ messages/`, 라우트 그룹 `(fds)/`·`(aml)/` 분리 | target-architecture §3(bo-web) · hanpassr-backoffice 디렉토리 정본 | 3 | — |
| BOF-S1-07 | FE | **공통 레이아웃·디자인 시스템** — 헤더(검색·액션 버튼·관리자)·좌측 NAV(활성 하이라이트)·breadcrumb·info 패턴, radix-ui 기반 공통 컴포넌트: `DataTable`(컬럼 설정·페이지네이션·행▶)·`FilterBar`·`KpiCard`·`TabChips`·`Callout`·`FormPanel`·`ConditionBuilder`(문장형 룰)·`EntryBanner`(드릴다운 진입 경로)·상태 Badge | PPT 전 슬라이드 공통 골격(좌 75% 콘텐츠+우 정보) / FDS PRD 각 화면 ASCII 레이아웃 / AML PRD 동 | 4 | S1-06 |
| BOF-S1-08 | FE | **API 클라이언트·상태 관리** — react-query 클라이언트(+`Tenant-Id` 헤더 주입)·zustand(테넌트/서비스 선택 컨텍스트)·react-hook-form+zod 폼 베이스·에러 코드→토스트/인라인 매핑 | FDS PRD §16.3(에러 표) / AML PRD 부록 D / FDS API §3 / AML API §4 | 3 | S1-06 |
| BOF-S1-09 | FE | **i18n·표시 용어 사전** — next-intl 셋업, enum↔한국어 표시 메시지 키 생성(FDS: PRD 본문 enum 병기 전수 / AML: 부록 F 사전 전수), 내부 코드 미노출 원칙 가드 | FDS PRD §1·각 화면 데이터 항목 표 / AML PRD 부록 F·부록 G(결재 라인) | 2 | S1-06 |
| BOF-S1-10 | FE | **인증 화면·세션 가드** — 로그인/로그아웃·세션 만료·Role 기반 메뉴 노출(권한 매트릭스), 고객사/서비스 선택 ▼ 컨텍스트 바 | FDS PRD §16.2 / AML PRD §1.3(운영 주체)·부록 B / BOF-S1-02 API | 3 | S1-07·S1-08 |
| BOF-S1-11 | BE | **CI** — `.github/workflows` path-filtered(bo-web·bo-api), 빌드+테스트+lint 게이트 | target-architecture §2(모노레포·CI) | 2 | S1-01·S1-06 |

## DoD
- bo-web 로그인 → 빈 FDS/AML 콘솔 셸(NAV·헤더·테넌트 선택) 진입, bo-api 경유 헬스 호출 왕복.
- 프록시로 엔진 Admin API 1건(예: `GET /api/v1/admin/fds/rules`) 위임 호출 성공 + 감사 기록.
- 권한 없는 Role의 메뉴·라우트 차단 확인. CI 녹색.
