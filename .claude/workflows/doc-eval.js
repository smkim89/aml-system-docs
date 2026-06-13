export const meta = {
  name: 'doc-eval',
  description: '문서 일습을 골든셋(.claude/eval/golden-set)으로 채점하고 정합 게이트(doc-consistency)를 돌려 점수를 scoreboard.md에 append하는 체중계',
  whenToUse: '완성도(품질) 점수를 측정하고 싶을 때 — 개선 루프의 평가(①) 단계, 또는 단독 측정',
  phases: [
    { title: 'Score', detail: '산출물별 골든셋 채점 (선수≠심판·opus)' },
    { title: 'Gate', detail: '정합 게이트(높음 이격 0?) 판정' },
    { title: 'Record', detail: 'scoreboard.md 에 점수 행 append' },
  ],
}

// args: { service: "fds"|"aml"|"all", stamp?: "ISO", reason?: "기능/제안 설명" }
const service = (args && args.service) || 'all'
const stamp = (args && args.stamp) || 'latest'
const reason = (args && args.reason) || '단독 측정'
const ROOT = '/Users/smkim/workspace/smkim89/aml-system-docs'
const GS = ROOT + '/.claude/eval/golden-set'

// 채점 에이전트는 작성 에이전트(system-architect 등)와 분리한다 — agentType 없이 opus 심판.
const SCORE_SCHEMA = {
  type: 'object',
  required: ['skipped', 'passed', 'total', 'criteria'],
  properties: {
    skipped: { type: 'boolean', description: '대상 문서가 없으면 true' },
    passed: { type: 'number' },
    total: { type: 'number' },
    criteria: {
      type: 'array',
      items: {
        type: 'object',
        required: ['n', 'pass'],
        properties: { n: { type: 'number' }, pass: { type: 'boolean' }, note: { type: 'string' } },
      },
    },
  },
}

// 산출물 → (골든셋, 대상 경로 힌트)
const ARTIFACTS = [
  { key: 'software', rubric: GS + '/software.md', target: 'docs/software/NN-' + service + '-sass.md (또는 *Svc-sass.md)' },
  { key: 'db', rubric: GS + '/db.md', target: 'docs/design/db/NN-' + service + '-db.md' },
  { key: 'api', rubric: GS + '/api.md', target: 'docs/design/api/NN-' + service + '-api.md' },
  { key: 'integration', rubric: GS + '/integration.md', target: 'docs/design/integration/NN-' + service + '-integration.md' },
  { key: 'prd', rubric: GS + '/prd.md', target: 'docs/plan/NN-' + service + '-sass-functional-spec.md' },
  { key: 'ppt', rubric: GS + '/ppt.md', target: '.claude/skills/backoffice-planner/generate_' + service + '.py' },
  { key: 'tasks', rubric: GS + '/tasks.md', target: 'docs/tasks/' + service + '/ + docs/tasks/aegis-aml/' },
  { key: 'cross', rubric: GS + '/cross.md', target: '전 문서 횡단(대표 2~3개를 직접 대조)' },
]

const targetServices = service === 'all' ? ['fds', 'aml'] : [service]

phase('Score')
log('채점 대상 서비스=' + targetServices.join(',') + ' · 골든셋 8종')

// 서비스 × 산출물 채점 (병렬)
const jobs = []
for (const svc of targetServices) {
  for (const a of ARTIFACTS) {
    if (a.key === 'cross' && svc !== targetServices[0]) continue // 횡단은 1회만
    jobs.push({ svc, a })
  }
}

const scored = await parallel(
  jobs.map((j) => () => {
    const svcTarget = j.a.target.split('NN-' + service).join('NN-' + j.svc).split('generate_' + service).join('generate_' + j.svc)
    const prompt =
      '너는 문서 품질 채점 심판이다(작성자 아님 — 적대적·엄격). 산출물=' + j.a.key + ' (서비스 ' + j.svc + ').\n' +
      '① 골든셋 루브릭을 Read: ' + j.a.rubric + '\n' +
      '② 대상 문서를 Read(실재하는 파일을 찾아 직접 열기): ' + ROOT + '/' + svcTarget + '\n' +
      '③ 루브릭의 각 기준(예/아니오)을 대상 문서 근거로 채점한다. 근거 없이 통과 주지 말 것. 애매하면 fail.\n' +
      '대상 문서가 없으면 skipped=true, passed=0, total=0. 있으면 criteria 배열에 각 기준 n·pass·note(근거/결손 한 줄).\n' +
      'passed=통과 기준 수, total=루브릭 기준 총수.'
    return agent(prompt, { schema: SCORE_SCHEMA, phase: 'Score', label: 'score:' + j.svc + ':' + j.a.key, model: 'opus' })
      .then((r) => ({ svc: j.svc, key: j.a.key, ...(r || { skipped: true, passed: 0, total: 0, criteria: [] }) }))
  })
)

// ── 정합 게이트 ──────────────────────────────────────────────────────
phase('Gate')
const GATE_SCHEMA = {
  type: 'object',
  required: ['pass', 'highGaps', 'summary'],
  properties: { pass: { type: 'boolean' }, highGaps: { type: 'number' }, summary: { type: 'string' } },
}
const gate = await agent(
  '정합 게이트 판정(선수≠심판). 대상 서비스=' + targetServices.join(',') + '. ' +
    '설계서↔DB↔API↔연동↔PRD↔PPT생성기 간 명칭·필드·타입·enum(종수)·상태·엔드포인트·화면요소가 어긋나거나 ' +
    '없는 엔드포인트/컬럼/enum을 참조하는 **높음(구현 오류 직결)** 이격이 있는지만 빠르게 본다(.claude/skills/_shared/target-architecture.md 정본). ' +
    '핵심 쌍(설계↔DB, DB↔API, API↔PRD, PRD↔PPT생성기)을 표본 대조해 높음 이격 수(highGaps)와 PASS(높음 0) 여부를 반환. 불확실하면 보수적으로 fail.',
  { schema: GATE_SCHEMA, phase: 'Gate', label: 'consistency-gate', model: 'opus' }
)
const gatePass = !!(gate && gate.pass)
const highGaps = (gate && gate.highGaps) || 0

// cross 산출물 점수에 게이트(#5)를 hard 반영: 게이트 fail이면 cross의 마지막 기준 fail 처리
for (const s of scored) {
  if (s.key === 'cross' && !gatePass && s.total > 0) {
    // #5(정합 게이트) 기준을 fail로 강제, passed 조정
    const c5 = (s.criteria || []).find((c) => c.n === 5)
    if (c5 && c5.pass) { c5.pass = false; c5.note = '정합 게이트 FAIL(높음 ' + highGaps + ')'; s.passed = Math.max(0, s.passed - 1) }
  }
}

// ── 집계 ────────────────────────────────────────────────────────────
const totalPassed = scored.reduce((n, s) => n + (s.passed || 0), 0)
const totalMax = scored.reduce((n, s) => n + (s.total || 0), 0)
log('총점 ' + totalPassed + '/' + totalMax + ' · 정합 게이트 ' + (gatePass ? 'PASS' : 'FAIL(높음 ' + highGaps + ')'))

// ── scoreboard.md append ────────────────────────────────────────────
phase('Record')
const board = ROOT + '/.claude/eval/scoreboard.md'
const perDocJson = JSON.stringify(scored.map((s) => ({ svc: s.svc, key: s.key, passed: s.passed, total: s.total, skipped: s.skipped })))
await agent(
  '다음 채점 결과로 scoreboard 에 행을 **append**(기존 내용 보존, 절대 덮어쓰기 금지)한다: ' + board + '\n' +
    'stamp=' + stamp + ', 서비스=' + service + ', 기능/제안=' + reason + ', 골든셋 버전=gs1.\n' +
    '컬럼 순서(software|db|api|integration|prd|ppt|tasks|cross)에 각 "passed/total"을 채우고(skipped는 "—"), ' +
    '총점/만점=' + totalPassed + '/' + totalMax + ', 정합게이트=' + (gatePass ? 'PASS' : 'FAIL') + ', 판정은 비움(루프가 채움). ' +
    '서비스 all이면 fds·aml 행을 각각 또는 합산 1행으로 추가(perDoc 참조). perDoc=' + perDocJson + '\n' +
    'Edit 도구로 마지막 행 아래에 markdown 표 행만 추가하고 한 줄 요약만 반환.',
  { phase: 'Record', label: 'append-scoreboard', model: 'sonnet' }
)

return {
  status: gatePass ? 'SCORED' : 'SCORED_GATE_FAIL',
  service,
  scoreTotal: totalPassed,
  scoreMax: totalMax,
  gatePass,
  highGaps,
  perDoc: scored.map((s) => ({ svc: s.svc, key: s.key, passed: s.passed, total: s.total, skipped: s.skipped })),
}
