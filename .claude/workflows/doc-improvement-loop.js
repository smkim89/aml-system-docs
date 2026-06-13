export const meta = {
  name: 'doc-improvement-loop',
  description: '평가→제안(기능 1건)→적용→재채점→점수 오를 때만 유지(아니면 revert+오답노트)를 1바퀴 돌고 멈추는 개선 루프(공장). 사람 승인 전엔 commit 안 함.',
  whenToUse: '문서 완성도를 한 걸음 끌어올리고 싶을 때 — 기능 추가(feature) 또는 골든셋 최대 결손 자동 개선',
  phases: [
    { title: 'Baseline', detail: 'doc-eval 로 score_before 측정' },
    { title: 'Propose', detail: '오답노트 읽고 기능 1건/최대 결손 1개 선정' },
    { title: 'Apply', detail: 'feature 파이프라인 단계 인라인 적용 + PPT 재생성' },
    { title: 'Rescore', detail: 'doc-eval 로 score_after 측정' },
    { title: 'Merge', detail: '점수↑ AND 정합 PASS면 유지(미commit), 아니면 revert+오답노트' },
  ],
}

// args: { service: "fds"|"aml"(필수), feature?: "<기능>", stampNow?: "ISO(시각 주입)" }
const service = (args && args.service) || ''
const feature = (args && args.feature) || ''
const stampNow = (args && args.stampNow) || 'now'
const ROOT = '/Users/smkim/workspace/smkim89/aml-system-docs'
const EVAL = ROOT + '/.claude/workflows/doc-eval.js'
const CHANGE_PATHS = 'docs .claude/skills/backoffice-planner/generate_fds.py .claude/skills/backoffice-planner/generate_aml.py'

if (service !== 'fds' && service !== 'aml') {
  return { status: 'BAD_ARGS', message: 'args.service 는 fds|aml 이어야 한다(기능 단위 변경 대상).' }
}

// ── 0. 작업 트리 클린 확인 (.claude/eval 로그 제외) ──────────────────
const GIT_SCHEMA = { type: 'object', required: ['clean', 'detail'], properties: { clean: { type: 'boolean' }, detail: { type: 'string' } } }
const pre = await agent(
  'Bash로 `cd ' + ROOT + ' && git status --porcelain -- ' + CHANGE_PATHS + '` 실행. ' +
    '출력이 비어 있으면(변경 산출물 트리가 깨끗) clean=true. 비어있지 않으면 clean=false, detail에 첫 5줄. ' +
    '(.claude/eval 의 scoreboard/lessons 변경은 무시 대상이라 위 경로에 포함하지 않음.)',
  { schema: GIT_SCHEMA, label: 'git-clean-check', model: 'sonnet' }
)
if (!pre || !pre.clean) {
  return { status: 'DIRTY_TREE', message: '변경 산출물 트리가 깨끗하지 않다 — baseline 측정 불가. 먼저 commit/stash 하라.', detail: pre && pre.detail }
}

// ── 1. Baseline 점수 ────────────────────────────────────────────────
phase('Baseline')
const before = await workflow({ scriptPath: EVAL }, { service, stamp: stampNow + '-before', reason: (feature || 'auto') + ' (before)' })
const scoreBefore = (before && before.scoreTotal) || 0
log('score_before = ' + scoreBefore + '/' + ((before && before.scoreMax) || '?') + ' · 게이트 ' + (before && before.gatePass ? 'PASS' : 'FAIL'))

// ── 2. 제안 (오답노트 읽고 기능 1건 또는 최대 결손 1개) ───────────────
phase('Propose')
const PROPOSE_SCHEMA = {
  type: 'object',
  required: ['title', 'change', 'targetArtifacts'],
  properties: {
    title: { type: 'string', description: '한 줄 제안명' },
    change: { type: 'string', description: '적용할 단일 변경(기능 1건 또는 결손 1개)의 구체 내용' },
    targetArtifacts: { type: 'array', items: { type: 'string' }, description: '영향 산출물(software/db/api/integration/prd/ppt/tasks)' },
  },
}
let proposal
if (feature) {
  proposal = { title: feature, change: feature, targetArtifacts: ['software', 'db', 'api', 'integration', 'prd', 'ppt', 'tasks'] }
} else {
  proposal = await agent(
    '개선 제안 1건을 고른다(한 번에 하나만). 먼저 오답노트를 Read: ' + ROOT + '/.claude/eval/lessons.md (이미 실패한 시도 회피). ' +
      '점수표 Read: ' + ROOT + '/.claude/eval/scoreboard.md (서비스 ' + service + ' 최근 행의 산출물별 결손). ' +
      '골든셋 Read: ' + ROOT + '/.claude/eval/golden-set/*.md. ' +
      '서비스=' + service + '의 **가장 점수가 낮은(결손이 큰) 산출물에서 한 기준을 메우는 단일 변경**을 제안한다(오답노트에 있는 시도는 제외). change에 구체적 수정 내용, targetArtifacts에 영향 산출물.',
    { schema: PROPOSE_SCHEMA, phase: 'Propose', label: 'propose-change', model: 'opus' }
  )
}
if (!proposal) return { status: 'NO_PROPOSAL', scoreBefore, message: '제안 생성 실패.' }
log('제안: ' + proposal.title)

// ── 3. 적용 (feature 파이프라인 단계 인라인 — 중첩 워크플로우 회피) ─────
phase('Apply')
const SPEC =
  '정본=.claude/skills/_shared/target-architecture.md. 상위 문서와 직전 변경점(downstreamNotes)을 반드시 읽고 명칭·필드·타입·enum(종수)·엔드포인트를 100% 동기화하라. ' +
  '신규가 아니면 부분 갱신(append/edit)하고 변경 이력을 남겨라. 골든셋(.claude/eval/golden-set)을 의식해 해당 기준을 충족시켜라.'
const STAGE_SCHEMA = {
  type: 'object',
  required: ['summary', 'downstreamNotes'],
  properties: { summary: { type: 'string' }, files: { type: 'array', items: { type: 'string' } }, downstreamNotes: { type: 'string' } },
}
const STAGES = [
  { phase: 'software', type: 'system-architect', task: 'docs/software/ 의 ' + service + ' 설계서에 변경 "' + proposal.change + '" 를 반영(도메인·enum·상태·규칙·규제·근거).' },
  { phase: 'db', type: 'data-modeler', task: 'docs/design/db/ 의 ' + service + ' DB 설계서에 대응 테이블·컬럼·enum·마이그레이션을 동기화.' },
  { phase: 'api', type: 'api-designer', task: 'docs/design/api/ 의 ' + service + ' API 명세서에 엔드포인트·DTO·권한·에러코드를 설계+DB와 동기화.' },
  { phase: 'integration', type: 'integration-designer', task: 'docs/design/integration/ 의 ' + service + ' 연동 명세서에 이벤트·메시지·커넥터·아웃박스를 동기화.' },
  { phase: 'tasks', type: 'task-planner', task: '서비스 WBS(docs/tasks/' + service + ')와 프로그램 로드맵(docs/tasks/aegis-aml)을 2층 동기화.' },
  { phase: 'prd', type: 'backoffice-planner', task: 'docs/plan/ 의 ' + service + ' PRD와 BO PPT 생성기를 한 쌍으로 갱신(화면 요소 전수·표시 용어·문장형 룰). PPT는 생성기 수정 후 재생성.' },
]
const onlyArtifacts = proposal.targetArtifacts && proposal.targetArtifacts.length ? proposal.targetArtifacts : null
let upstream = '[변경] ' + proposal.change + '\n[대상 서비스] ' + service
for (const s of STAGES) {
  if (onlyArtifacts && !onlyArtifacts.includes(s.phase)) continue
  phase('Apply')
  const res = await agent(
    s.task + '\n\n' + SPEC + '\n\n[상위/직전 변경점]\n' + upstream + '\n\n해당 에이전트 스킬 절차를 따르고 STAGE_SCHEMA로 반환.',
    { agentType: s.type, schema: STAGE_SCHEMA, phase: 'Apply', label: 'apply:' + s.phase }
  )
  if (res) { upstream += '\n\n[' + s.phase + ' 완료] ' + res.summary + '\n→ 다음 반영필수: ' + res.downstreamNotes }
}
// PPT 재생성 (prd 단계가 생성기를 고쳤으면)
if (!onlyArtifacts || onlyArtifacts.includes('ppt') || onlyArtifacts.includes('prd')) {
  await agent(
    'Bash로 `cd ' + ROOT + '/.claude/skills/backoffice-planner && python3 generate_' + service + '.py` 실행해 PPT를 재생성하고 저장 결과(슬라이드 수)를 반환.',
    { label: 'regen-ppt', model: 'sonnet' }
  )
}

// ── 4. Rescore ──────────────────────────────────────────────────────
phase('Rescore')
const after = await workflow({ scriptPath: EVAL }, { service, stamp: stampNow + '-after', reason: proposal.title + ' (after)' })
const scoreAfter = (after && after.scoreTotal) || 0
const gateAfter = !!(after && after.gatePass)
log('score_after = ' + scoreAfter + ' (Δ ' + (scoreAfter - scoreBefore) + ') · 게이트 ' + (gateAfter ? 'PASS' : 'FAIL'))

// ── 5. Merge 판정: 점수↑ AND 정합 PASS → 유지(미commit), else revert ──
phase('Merge')
const improved = scoreAfter > scoreBefore
const keep = improved && gateAfter
let verdict
if (keep) {
  verdict = 'KEEP'
  log('KEEP 권고 — 점수 +' + (scoreAfter - scoreBefore) + ' · 정합 PASS. 변경은 미commit 상태로 둠(사람이 검토 후 commit).')
} else {
  verdict = 'REVERT'
  const why = !improved ? ('점수 미상승(Δ ' + (scoreAfter - scoreBefore) + ')') : '정합 게이트 FAIL'
  await agent(
    'Bash로 `cd ' + ROOT + ' && git checkout -- ' + CHANGE_PATHS + '` 실행해 이번 변경을 **버린다**(.claude/eval 로그는 보존). ' +
      '그 다음 ' + ROOT + '/.claude/eval/lessons.md 에 한 줄 **append**(덮어쓰기 금지): ' +
      '| ' + stampNow + ' | ' + service + ' | ' + proposal.title + ' | Δ' + (scoreAfter - scoreBefore) + ' / ' + (gateAfter ? 'PASS' : 'FAIL') + ' | ' + why + ' | (교훈 한 줄로 요약) | ' +
      ' 실행 결과를 한 줄로 반환.',
    { label: 'revert+lesson', model: 'sonnet' }
  )
  log('REVERT — ' + why + '. 변경 폐기 + 오답노트 기록.')
}

// ── 다음 제안(1바퀴 멈춤 — 사람이 다음을 승인) ────────────────────────
const nextHint = await agent(
  '방금 ' + verdict + '된 변경 이후, 서비스 ' + service + '의 scoreboard.md 최근 행과 golden-set 결손을 보고 ' +
    '**다음 한 걸음** 후보 1개를 한 줄로 제안(아직 적용 금지). lessons.md의 실패 시도는 제외.',
  { label: 'next-step-hint', model: 'sonnet' }
).catch(() => null)

return {
  status: verdict,
  service,
  proposal: proposal.title,
  scoreBefore,
  scoreAfter,
  delta: scoreAfter - scoreBefore,
  gateAfter,
  kept: keep,
  nextStep: nextHint,
  note: keep
    ? '변경이 미commit 상태로 working tree에 남아 있다. 검토 후 commit 하면 머지, 아니면 git checkout 으로 폐기.'
    : '변경은 폐기됨(오답노트 기록). 다음 후보를 승인하면 한 바퀴 더 돈다.',
}
