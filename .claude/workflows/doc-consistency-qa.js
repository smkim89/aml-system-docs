export const meta = {
  name: 'doc-consistency-qa',
  description: '개발 착수용 문서 일습(설계↔DB↔API↔연동↔PRD↔PPT↔태스크) 간 이격(gap)을 전수 대조하고 정합성 리포트를 생성',
  whenToUse: '설계/DB/API/연동/PRD/태스크 문서를 작성·수정한 직후, 개발 착수 전 문서 간 불일치 점검',
  phases: [
    { title: 'Discover', detail: 'docs/ 인벤토리 → 대조 가능한 문서 쌍 목록화' },
    { title: 'Check', detail: '이격 매트릭스 쌍별 정합성 대조 (팬아웃)' },
    { title: 'Verify', detail: '높음 심각도 이격 적대적 재검증' },
    { title: 'Synthesize', detail: '통합 정합성 리포트 작성 + PASS/FAIL' },
  ],
}

// args: { service?: "fds"|"aml"|"bo-api"|"bo-web"|"all", date?: "YYYY-MM-DD" }
const target = (args && args.service) || 'all'
const stamp = (args && args.date) || 'latest'

const SPEC = '.claude/skills/_shared/target-architecture.md 의 산출물 일습 매핑 + doc-consistency-qa 스킬의 이격 매트릭스를 정본 기준으로 삼는다.'

// ── Phase 1: 대조 쌍 발굴 ──────────────────────────────────────────────
phase('Discover')
const DISCOVER_SCHEMA = {
  type: 'object',
  required: ['pairs'],
  properties: {
    pairs: {
      type: 'array',
      items: {
        type: 'object',
        required: ['key', 'service', 'basis', 'docA', 'docB'],
        properties: {
          key: { type: 'string', description: '예: fds:db-api' },
          service: { type: 'string' },
          basis: { type: 'string', description: '대조 기준(엔티티/필드/enum 등)' },
          docA: { type: 'string', description: '상위 문서 경로' },
          docB: { type: 'string', description: '파생 문서 경로' },
        },
      },
    },
  },
}
const discovery = await agent(
  `docs/ 하위를 조사해 실재하는 문서를 인벤토리하고, 이격 매트릭스에서 **양쪽 문서가 모두 존재하는** 대조 쌍만 목록화하라. 대상 서비스=${target}(all이면 전 서비스). ${SPEC} ` +
  `매트릭스 쌍: 설계↔DB, DB↔API, 설계↔API, 설계↔연동, DB/API↔연동, API↔PRD, PRD↔PPT, 설계/DB/API/연동↔서비스WBS(docs/tasks/<svc>), ` +
  `서비스WBS↔프로그램로드맵(docs/tasks/aegis-aml T-ID↔Phase 태스크 매핑·의존·Status), 프로그램로드맵↔설계/PRD(Phase 태스크 참조 §·화면·엔드포인트 실재), 횡단(전 문서 네이밍·테넌시·PII·규제). ` +
  `**PPT흐름**(fds/aml만): key="<svc>:ppt-flow", docA=PRD(docs/plan/NN-<svc>-sass-functional-spec.md), docB=생성기(.claude/skills/backoffice-planner/generate_<svc>.py)가 모두 있으면 추가 — basis="탭 연속성·드릴다운 진입 트리거·변경이력 한 줄(backoffice-planner SKILL §1.6·원칙 7)". ` +
  `횡단은 service="cross", docA/docB에 핵심 문서 2개를 대표로 지정하라. 결과는 pairs 배열만.`,
  { schema: DISCOVER_SCHEMA, phase: 'Discover', label: 'discover-pairs', model: 'sonnet' }
)
const pairs = (discovery && discovery.pairs) || []
log(`대조 쌍 ${pairs.length}개 발굴 (대상=${target})`)
if (pairs.length === 0) {
  return { status: 'NO_PAIRS', message: '양쪽이 모두 존재하는 문서 쌍이 없음 — 문서를 먼저 작성하라.', target }
}

// ── Phase 2~3: 쌍별 대조 → 높음 이격 재검증 (pipeline, 배리어 없음) ──────
const GAP_SCHEMA = {
  type: 'object',
  required: ['findings'],
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object',
        required: ['severity', 'item', 'mismatch', 'recommendation'],
        properties: {
          severity: { type: 'string', enum: ['high', 'medium', 'low'] },
          item: { type: 'string', description: '엔티티/필드/enum/엔드포인트/화면요소' },
          mismatch: { type: 'string', description: '이격 내용(어느 쪽이 무엇이 다른가)' },
          location: { type: 'string', description: '문서·섹션 위치' },
          recommendation: { type: 'string' },
        },
      },
    },
  },
}
const VERDICT_SCHEMA = {
  type: 'object',
  required: ['real', 'reason'],
  properties: {
    real: { type: 'boolean', description: '실제 이격이면 true, 오탐이면 false' },
    reason: { type: 'string' },
  },
}

const checked = await pipeline(
  pairs,
  (pair) =>
    agent(
      `문서 정합성 대조. 대조쌍=${pair.key} (${pair.basis}). 상위=${pair.docA}, 파생=${pair.docB}. ` +
      `두 문서를 읽고 ${pair.basis} 수준에서 명칭·타입·필수·enum값·상태·엔드포인트·화면요소가 어긋나거나 누락된 항목을 이격으로 보고하라. ` +
      (pair.key.endsWith(':ppt-flow')
        ? `**PPT흐름 점검**: 생성기(generate_<svc>.py)를 읽고 — ① 멀티탭 상세/플로우 화면이 1탭=1슬라이드·같은 부모 탭 바·active 일치인가(한 함수/슬라이드에 여러 탭 내용을 욱여넣음·빈 라벨 탭·부모와 다른 탭 바 분리 화면 = high 이격). ② 다른 기능 ID로 가는 드릴다운(xxx_002 등) 첫 슬라이드에 wf.entry_banner(진입 경로)가 있고 소스 목록 화면 행/버튼에 ▶ + "→XXX"가 있는가(없으면 medium~high). ③ 변경이력 history_slide 행 문구가 한 줄 요약인가(장문이면 low). ④ SCREENS 순서상 드릴다운이 소스 화면과 멀리 떨어졌는가(흐름 단절=medium). 단순 필터 탭(내케이스/전체, 대기/상신/완료)은 1슬라이드 정상 — 이격 아님. PRD의 화면 순서·기능 ID와 생성기 SCREENS가 일치하는지도 확인. `
        : '') +
      `${SPEC} 정본과 다르면 정본을 기준으로 어느 문서가 틀렸는지 명시. 이격이 없으면 findings=[].`,
      { schema: GAP_SCHEMA, phase: 'Check', label: `check:${pair.key}`, model: 'sonnet' }
    ),
  async (gap, pair) => {
    if (!gap) return { pair: pair.key, service: pair.service, findings: [], errored: true }
    const highs = (gap.findings || []).filter((f) => f.severity === 'high')
    const others = (gap.findings || []).filter((f) => f.severity !== 'high')
    const verified = await parallel(
      highs.map((f) => () =>
        agent(
          `다음 이격 주장을 적대적으로 재검증하라. 불확실하면 real=false. 대조쌍=${pair.key}, 항목=${f.item}, 주장=${f.mismatch}. 두 문서(${pair.docA}, ${pair.docB})를 직접 확인.`,
          { schema: VERDICT_SCHEMA, phase: 'Verify', label: `verify:${pair.key}`, model: 'opus' }
        ).then((v) => (v && v.real ? { ...f, pair: pair.key, service: pair.service } : null))
      )
    )
    const confirmedHighs = verified.filter(Boolean)
    return {
      pair: pair.key,
      service: pair.service,
      findings: [...confirmedHighs, ...others.map((f) => ({ ...f, pair: pair.key, service: pair.service }))],
    }
  }
)

const erroredPairs = checked.filter((r) => !r || r.errored).map((r) => (r ? r.pair : 'unknown'))
const allFindings = checked.filter(Boolean).flatMap((r) => r.findings)
const highCount = allFindings.filter((f) => f.severity === 'high').length
// 미검증(rate-limit 등으로 실패한) 쌍이 있으면 PASS 불가 — INCOMPLETE 로 표시
const verdict = erroredPairs.length > 0 ? 'INCOMPLETE' : highCount === 0 ? 'PASS' : 'FAIL'
log(`이격 ${allFindings.length}건 (높음 ${highCount}), 미검증 쌍 ${erroredPairs.length}개 → ${verdict}`)

// ── Phase 4: 통합 리포트 작성 ─────────────────────────────────────────
phase('Synthesize')
const reportPath = `docs/qa/doc-consistency-report-${target}-${stamp}.md`
const summary = await agent(
  `다음 문서 정합성 이격 발견사항(JSON)을 한국어 리포트로 정리해 ${reportPath} 에 작성하라(디렉토리 없으면 생성). ` +
  `구성: ① 판정(${verdict}, 높음 ${highCount}건, 미검증 쌍 ${erroredPairs.length}개${erroredPairs.length ? ': ' + erroredPairs.join(',') : ''}) ② 심각도별 요약 ③ 대조쌍별 이격 표(심각도·서비스·항목·이격내용·위치·권고) ④ 개발 착수 권고. ` +
  `INCOMPLETE면 미검증 쌍은 재실행 필요라고 명시. 대상=${target}. 발견사항: ${JSON.stringify(allFindings).slice(0, 100000)}. 작성 후 한 줄 요약만 반환.`,
  { phase: 'Synthesize', label: 'write-report', model: 'sonnet' }
)

return { status: verdict, target, pairs: pairs.length, gaps: allFindings.length, highGaps: highCount, erroredPairs, report: reportPath, summary }
