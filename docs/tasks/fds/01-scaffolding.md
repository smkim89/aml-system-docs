# T-01 모노레포·fds-svc 스캐폴딩·CI·컨벤션 [BE]

- 서비스: `services/fds-svc` · Effort: M · 의존: — · Status: TODO

## 목표
정본 4서비스 모노레포에 `fds-svc`(Java 25 / Spring Boot 3.5.x / 헥사고날)를 스캐폴딩하고, `com.hanpass.fds` 패키지 레이아웃·공통 컨벤션 플러그인·path-filtered CI를 확정한다. 참조 구현 `hanpass-ph/services/fds-svc` 패턴 정렬.

## 구현 항목
- [ ] `services/fds-svc` Gradle 모듈 생성, `gradle/libs.versions.toml` 버전 카탈로그 사용(단일 정본)
- [ ] `buildSrc` 컨벤션 플러그인 적용(fds/aml/bo-api 공용), Java 25 toolchain
- [ ] 패키지 골격: `domain/`(CanonicalEvent·Subject·Actor·Instrument·Transaction·Decision·Action·Case·RiskGroup·RuleSet ADT), `application/(usecase·port/in·port/out)`, `adapter/(in:rest·sqs·scheduled / out:persistence·external)`, `global/`
- [ ] `application/port/out`: `CanonicalEventStorePort`, `FeatureStorePort`, `ActionOutboxPort`, `AmlCasePort`(aml-svc), `SchemaRegistryPort`
- [ ] `global/`: tenant context holder(tenant/workspace/data-scope), traceId 전파 필터, PII 마스킹/토큰화 필터, 보안/설정
- [ ] `compose/docker-compose.yml`에 fds-svc·PostgreSQL·LocalStack(SQS) 추가
- [ ] `.github/workflows/` fds-svc path-filtered CI(build·test·lint)

## 참조
- `docs/software/01-fdsSvc-sass.md` §6.1(정본 4서비스 매핑), §6.2(`com.hanpass.fds` 헥사고날 레이아웃), §18 Phase 0
- `.claude/skills/_shared/target-architecture.md` §2·§3
