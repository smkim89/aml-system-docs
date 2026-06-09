# T-01 모노레포·aml-svc 스캐폴딩·CI·컨벤션 [BE]

- 서비스: `services/aml-svc` · Effort: M · 의존: — · Status: DONE

## 목표
정본 4서비스 모노레포에 `aml-svc`(Java 25 / Spring Boot 3.5.x / 헥사고날)를 스캐폴딩하고, `com.hanpass.aml` 패키지 레이아웃·공통 컨벤션 플러그인·path-filtered CI를 확정한다.

## 구현 항목
- [ ] `services/aml-svc` Gradle 모듈 생성, `gradle/libs.versions.toml` 버전 카탈로그 사용(단일 정본)
- [ ] `buildSrc` 컨벤션 플러그인 적용(fds/aml/bo-api 공용), Java 25 toolchain
- [ ] 패키지 골격: `domain/`, `application/(usecase·port/in·port/out)`, `adapter/(in:rest·sqs·scheduled / out:persistence·external)`, `global/`
- [ ] `global/`: tenant context holder, traceId 전파 필터, PII 마스킹/토큰화 필터, 보안/설정
- [ ] `compose/docker-compose.yml`에 aml-svc·PostgreSQL·LocalStack(SQS) 추가
- [ ] `.github/workflows/` aml-svc path-filtered CI(build·test·lint)
- [ ] 참조 구현 `hanpass-ph/services/fds-svc`(`com.hanpass.fds`) 패턴 정렬

## 참조
- `docs/software/02-amlSvc-sass.md` §6.1(정본 매핑), §6.2(헥사고날 레이아웃)
- `.claude/skills/_shared/target-architecture.md` §2·§3

## 변경 이력
| 일자 | 변경 |
|---|---|
| 2026-06-08 | #50 Status `TODO`→`DONE`(00-overview §2 T-01=DONE과 정합; Phase0 스캐폴딩 완료, P1 이중 등재 아님). |
