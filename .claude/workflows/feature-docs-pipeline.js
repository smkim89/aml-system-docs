export const meta = {
  name: 'feature-docs-pipeline',
  description: '기능 추가·변경 요청 하나로 설계서→DB→API→연동→태스크→PRD→PPT 문서를 순차 동기화 생성/갱신하고, 정합성 QA로 이격을 0까지 맞추는 마스터 파이프라인',
  whenToUse: '특정 기능을 추가/변경하면서 프로젝트의 모든 문서(software·db·api·integration·plan PRD·BO PPT·tasks)를 한 번에 싱크 맞춰 생성/갱신하고 싶을 때',
  phases: [
    { title: '설계', detail: 'system-architect: docs/software 갱신' },
    { title: 'DB', detail: 'data-modeler: docs/design/db 갱신' },
    { title: 'API', detail: 'api-designer: docs/design/api 갱신' },
    { title: '연동', detail: 'integration-designer: docs/design/integration 갱신' },
    { title: '태스크', detail: 'task-planner: 서비스 WBS(docs/tasks/<svc>) + 프로그램 로드맵(docs/tasks/aegis-aml) 2층 동기화' },
    { title: '기획', detail: 'backoffice-planner: docs/plan PRD + BO PPT 갱신' },
    { title: 'QA', detail: 'doc-consistency-qa: 문서 간 이격 대조' },
    { title: '정합화', detail: '이격 FAIL 시 담당 문서 수정 후 재QA (최대 2회)' },
  ],
}

// args: { feature: "<기능 설명>", service: "fds"|"aml"|...(필수), maxReconcile?: 2 }
const feature = (args && args.feature) || ''
const service = (args && args.service) || 'fds'
const maxReconcile = (args && args.maxReconcile) || 2
if (!feature) {
  return { status: 'NO_FEATURE', message: 'args.feature(기능 설명)가 필요하다.' }
}

const SPEC =
  '정본=.claude/skills/_shared/target-architecture.md(4서비스·stack·산출물 매핑). ' +
  '상위 문서와 직전 단계 변경점(downstreamNotes)을 반드시 읽고, 명칭·필드·타입·enum·엔드포인트를 상위와 100% 동기화하라. ' +
  '신규가 아니면 기존 문서를 부분 갱신(append/edit)하고 변경 이력을 남겨라.'

const STAGE_SCHEMA = {
  type: 'object',
  required: ['summary', 'files', 'downstreamNotes'],
  properties: {
    summary: { type: 'string', description: '이 단계에서 만든/바꾼 내용 요약' },
    files: { type: 'array', items: { type: 'string' }, description: '작성/수정 문서 경로' },
    downstreamNotes: {
      type: 'string',
      description: '다음 문서가 반드시 반영해야 할 신규 엔티티·필드·enum·엔드포인트·이벤트·화면(명칭 포함)',
    },
    openDecisions: { type: 'string', description: '미정/오픈 결정(있으면)' },
  },
}

// ── 순차 단계 정의 (의존 순서: 설계→DB→API→연동→태스크→기획) ──────────────
const STAGES = [
  {
    phase: '설계',
    type: 'system-architect',
    task: `docs/software/ 의 ${service} 설계서에 기능 "${feature}" 를 반영하라(도메인 모델·enum·상태·규칙·규제·아키텍처 영향).`,
  },
  {
    phase: 'DB',
    type: 'data-modeler',
    task: `docs/design/db/ 의 ${service} DB 설계서를 갱신하라. 설계서의 기능 "${feature}" 에 대응하는 테이블·컬럼·인덱스·enum·마이그레이션을 동기화.`,
  },
  {
    phase: 'API',
    type: 'api-designer',
    task: `docs/design/api/ 의 ${service} API 명세서를 갱신하라. 기능 "${feature}" 의 엔드포인트·DTO·권한·에러코드를 설계+DB 필드와 동기화.`,
  },
  {
    phase: '연동',
    type: 'integration-designer',
    task: `docs/design/integration/ 의 ${service} 연동 명세서를 갱신하라. 기능 "${feature}" 의 이벤트·메시지 스키마·커넥터·아웃박스를 DB/API 필드와 동기화.`,
  },
  {
    phase: '태스크',
    type: 'task-planner',
    task: `개발 태스크를 **2층 모두 동기화**하라(target-architecture §5). ① 서비스 WBS: docs/tasks/${service}/ 에 기능 "${feature}" 태스크(목표·구현항목·참조섹션·Effort·의존·Status) 추가+의존 그래프. ② 프로그램 로드맵: docs/tasks/aegis-aml/ 의 영향 Phase 파일(0N-phaseN-*.md)에 대응 태스크(ID 접두 P{n}-{FDS|AML|BOAPI|WEB|INFRA}-NN·서비스·구분·Effort·의존·DoD·Status) 추가/갱신 + 00-program-overview.md 매핑·마일스톤 반영. 서비스 WBS↔Phase↔설계 정합. 둘 다 변경 이력 기록.`,
  },
  {
    phase: '기획',
    type: 'backoffice-planner',
    task: `docs/plan/ 의 ${service} 기능정의서(PRD)와 BO 기획서(PPT)를 한 쌍으로 갱신하라. 기능 "${feature}" 의 백오피스 화면을 설계+DB+API+태스크와 동기화하고, 화면 요소 전수·표시 용어 통일·문장형 룰 빌더 적용. PPT는 글로벌 pptx 스킬 사용.`,
  },
]

// ── 순차 실행: 각 단계가 직전 변경점을 입력으로 동기화 ────────────────────
const trail = []
let upstream = `[기능 요청] ${feature}\n[대상 서비스] ${service}`
for (const s of STAGES) {
  phase(s.phase)
  const res = await agent(
    `${s.task}\n\n${SPEC}\n\n[상위/직전 단계 변경점]\n${upstream}\n\n` +
      `해당 에이전트의 스킬 절차를 따르고, 끝나면 STAGE_SCHEMA로 요약·파일·downstreamNotes를 반환하라.`,
    { agentType: s.type, schema: STAGE_SCHEMA, phase: s.phase, label: `${s.phase}:${service}` }
  )
  if (res) {
    trail.push({ phase: s.phase, ...res })
    upstream += `\n\n[${s.phase} 완료] ${res.summary}\n→ 다음 반영필수: ${res.downstreamNotes}` +
      (res.openDecisions ? `\n⚠ 오픈결정: ${res.openDecisions}` : '')
    log(`${s.phase} 완료 — ${(res.files || []).length}개 문서`)
  } else {
    log(`${s.phase} 단계 실패(null) — 다음 단계는 직전까지의 맥락으로 진행`)
  }
}

// ── QA + 정합화 루프 ──────────────────────────────────────────────────
phase('QA')
let qa = await workflow('doc-consistency-qa', { service })
let iter = 0
while (qa && qa.status === 'FAIL' && iter < maxReconcile) {
  iter++
  phase('정합화')
  log(`정합화 ${iter}/${maxReconcile} — 높음 이격 ${qa.highGaps}건 수정`)
  // 각 문서 소유 에이전트가 QA 리포트의 자기 담당 이격을 정본 기준으로 수정
  await parallel(
    STAGES.map((s) => () =>
      agent(
        `${qa.report} 의 이격 중 너의 담당 문서(${s.phase})에 해당하는 항목만 정본 기준으로 수정하라. ` +
          `상위 문서를 진실로 삼아 명칭·필드·enum·엔드포인트를 맞춘다. 담당 외 항목은 건드리지 마라. ${SPEC}`,
        { agentType: s.type, phase: '정합화', label: `fix:${s.phase}` }
      )
    )
  )
  qa = await workflow('doc-consistency-qa', { service })
}

const finalStatus = !qa ? 'QA_ERROR' : qa.status === 'FAIL' ? 'FAIL_RESIDUAL' : qa.status
if (finalStatus === 'FAIL_RESIDUAL') {
  log(`⚠ ${maxReconcile}회 정합화 후에도 높음 이격 ${qa.highGaps}건 잔존 — 수동 검토 필요: ${qa.report}`)
}

return {
  status: finalStatus,
  feature,
  service,
  stages: trail.map((t) => ({ phase: t.phase, files: t.files })),
  qaReport: qa && qa.report,
  residualHighGaps: qa && qa.highGaps,
  reconcileIterations: iter,
}
