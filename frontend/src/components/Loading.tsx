import type { Progress } from '../lib/api'

// Pipeline stages in order. Each shows DONE / WORKING / PENDING based on current stage.
const STAGES = [
  { key: 'discovery', line: 'Searching federal and curated grant sources' },
  { key: 'match', line: 'Scoring how well each grant fits your organization' },
  { key: 'draft', line: 'Drafting and fact-checking application materials' },
]

function overall(p: Progress | null): number {
  if (!p) return 3
  const frac = p.total > 0 ? p.done / p.total : 0
  if (p.stage === 'discovery') return 3 + frac * 12
  if (p.stage === 'match') return 15 + frac * 55
  if (p.stage === 'draft') return 70 + frac * 30
  return 6
}

function statusOf(stageKey: string, current: string | undefined): 'DONE' | 'WORKING' | 'PENDING' {
  if (!current) return stageKey === 'discovery' ? 'WORKING' : 'PENDING'
  const order = STAGES.map((s) => s.key)
  const ci = order.indexOf(current)
  const si = order.indexOf(stageKey)
  if (si < ci) return 'DONE'
  if (si === ci) return 'WORKING'
  return 'PENDING'
}

export function Loading({ progress }: { progress: Progress | null }) {
  const pct = Math.min(99, Math.round(overall(progress)))

  return (
    <section className="panel p-7 sm:p-8 animate-in">
      <h2 className="text-[1.3rem] font-bold tracking-tight mb-5">Finding Your Matches</h2>

      {/* Flat progress bar */}
      <div className="border-2 h-3" style={{ borderColor: 'var(--hairline)' }}>
        <div className="h-full" style={{ width: `${pct}%`, background: 'var(--ink)', transition: 'width 0.5s var(--ease-spring)' }} />
      </div>
      <p className="mono text-right text-[0.85rem] mt-2 font-bold">{pct}%</p>

      {/* Live terminal log */}
      <div className="mt-5 p-4 mono text-[0.82rem]" style={{ border: '2px solid var(--hairline)', background: 'var(--bg)' }}>
        {STAGES.map((s) => {
          const status = statusOf(s.key, progress?.stage)
          const counts =
            status === 'WORKING' && progress && progress.total > 1 && progress.stage !== 'discovery'
              ? ` (${progress.done}/${progress.total})`
              : ''
          return (
            <div key={s.key} className="flex items-baseline gap-2 py-0.5"
              style={{ color: status === 'PENDING' ? 'var(--muted)' : 'var(--text)' }}>
              <span>&gt;</span>
              <span className="flex-1">{s.line}{counts}</span>
              <span className="font-bold">
                {status === 'DONE' && '[DONE]'}
                {status === 'WORKING' && '[WORKING]'}
                {status === 'PENDING' && '[PENDING]'}
              </span>
            </div>
          )
        })}
        <div className="py-0.5"><span className="cursor-blink">_</span></div>
      </div>

      <p className="mono text-[0.78rem] mt-4" style={{ color: 'var(--muted)' }}>
        This usually takes 30–60 seconds.
      </p>
    </section>
  )
}
