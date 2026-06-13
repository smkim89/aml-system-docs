export const meta = {
  name: 'reconcile-doc-gaps',
  description: 'QA 리포트의 높음 이격을 정본→파생 2웨이브로 정합화하고 재-QA로 높음 0건까지 수렴',
  whenToUse: 'doc-consistency-qa가 FAIL(높음 이격)일 때, 정본(설계서·DB·API)을 먼저 정정하고 파생(연동·태스크·PRD·PPT)을 맞춘 뒤 재검증',
  phases: [
    { title: '정합화-정본', detail: 'system-architect·data-modeler·api-designer: 설계서·DB·API 정정' },
    { title: '정합화-파생', detail: 'integration-designer·task-planner·backoffice-planner: 연동·태스크·PRD·PPT 정합' },
    { title: '재QA', detail: 'doc-consistency-qa 재실행 — 높음 0건 확인' },
  ],
}

// args: { service: "fds"|"aml" (필수), maxIter?: 2, decision?: "<소유경계 등 결정문>" }
const service = (args && args.service) || 'fds'
const maxIter = (args && args.maxIter) || 2
const decision =
  (args && args.decision) ||
  '운영자 집계 API 소유 경계: 대시보드·테넌트 관리·감사 조회는 bo-api가 소유·집약·인증한다. ' +
    'fds-svc/aml-svc는 저수준 데이터 API만 제공하고, 엔진 API 명세(docs/design/api)에는 운영자 집계 엔드포인트(대시보드/테넌트/감사)를 추가하지 않는다. ' +
    'PRD/PPT의 해당 화면은 호출 대상을 bo-api로 명시한다.'

const report = `docs/qa/doc-consistency-report-${service}-latest.md`
const SPEC =
  `정본=.claude/skills/_shared/target-architecture.md + 설계서(docs/software)·DB(docs/design/db)·API(docs/design/api)가 파생(연동·태스크·PRD·PPT)의 진실. ` +
  `action_type 마스터는 API enum(전수)을 정본으로 채택해 설계서를 동기화. HTTP 상태코드는 API 명세를 정본으로. ${decision}`

let qa = null
let iter = 0
while (iter < maxIter) {
  iter++

  // ── 웨이브 1: 정본 문서 정정 (서로 다른 파일이라 병렬 안전) ──
  phase('정합화-정본')
  await parallel([
    () =>
      agent(
        `${report} 의 높음 이격 중 **설계서(docs/software)** 담당 항목을 정본 기준으로 수정하라. ` +
          `예: §12.8 HOLD_TRANSACTION→HOLD_FUNDS 정정, action_type을 API enum(전수)으로 동기화, approval_status 상태머신/scope 보강, OPEN_*_CASE=OPEN_CASE+case_type 매핑 명문화. 담당 외 문서는 건드리지 마라. ${SPEC}`,
        { agentType: 'system-architect', phase: '정합화-정본', label: `fix:설계(${service})` }
      ),
    () =>
      agent(
        `${report} 의 높음/관련 이격 중 **DB 설계서(docs/design/db)** 담당 항목을 정정하라. ` +
          `예: fds_cases.aml_case_id(또는 aml 해당) 컬럼을 명세 표에 정식 행으로 추가, 누락 action_type/case_type/상태 enum 보강. ${SPEC}`,
        { agentType: 'data-modeler', phase: '정합화-정본', label: `fix:DB(${service})` }
      ),
    () =>
      agent(
        `${report} 의 높음 이격 중 **API 명세(docs/design/api)** 담당 항목을 정정하라. ` +
          `소유 경계 결정에 따라 대시보드·테넌트·감사 운영자 집계 엔드포인트는 엔진 API에 추가하지 말고 'bo-api 소유' 경계를 명시하라. action_type/HTTP 상태코드/OpenAPI 누락 필드(matchedRules 등)/Webhook 콜백 계약을 정본으로 확정. ${SPEC}`,
        { agentType: 'api-designer', phase: '정합화-정본', label: `fix:API(${service})` }
      ),
  ])

  // ── 웨이브 2: 파생 문서를 정정된 정본에 정합 ──
  phase('정합화-파생')
  await parallel([
    () =>
      agent(
        `${report} 의 이격 중 **연동 명세(docs/design/integration)** 담당 항목을, 방금 정정된 설계서·DB·API에 맞춰 정합하라. ` +
          `eventFamily 입력필드 격하/서버파생 표기, SUSPEND_MERCHANT capability, envelope 키(eventFamily/schemaVersion) 정합, errorCode camelCase 통일. ${SPEC}`,
        { agentType: 'integration-designer', phase: '정합화-파생', label: `fix:연동(${service})` }
      ),
    () =>
      agent(
        `${report} 의 이격 중 **태스크(docs/tasks/${service})** 담당 항목을 정정된 정본에 맞춰 정합하라. ` +
          `Phase 8(SaaS productization) 태스크 추가(Due=P8), aml_case_id 확정상태 표기 동기화, fds-webhook 큐→태스크 매핑, OPEN_CASE enum 표기. ${SPEC}`,
        { agentType: 'task-planner', phase: '정합화-파생', label: `fix:태스크(${service})` }
      ),
    () =>
      agent(
        `${report} 의 이격 중 **PRD(docs/plan functional-spec)와 기획서 PPT** 담당 항목을 정정된 정본에 맞춰 정합하라. ` +
          `HTTP 상태코드를 API 명세에 맞게 정정(409/422 등), 대시보드·테넌트·감사 화면의 호출 대상을 bo-api로 명시, PPT enum 전수(그룹 종류·용도·approval_line)·표시 용어 통일. PPT는 글로벌 pptx 스킬로 재빌드. ${SPEC}`,
        { agentType: 'backoffice-planner', phase: '정합화-파생', label: `fix:기획(${service})` }
      ),
  ])

  // ── 재QA ──
  phase('재QA')
  qa = await workflow({ scriptPath: '.claude/workflows/doc-consistency-qa.js' }, { service })
  log(`재QA ${iter}/${maxIter}: ${qa && qa.status} (높음 ${qa && qa.highGaps})`)
  if (qa && qa.status === 'PASS') break
}

return {
  service,
  status: qa && qa.status,
  residualHighGaps: qa && qa.highGaps,
  report: qa && qa.report,
  iterations: iter,
}
