import { useState } from 'react'
import { ChevronDown, ChevronLeft, CheckCircle, AlertTriangle, FileText } from 'lucide-react'
import type { MatchResult, MatchedOpportunity } from '../lib/api'

function Banner({ heavy, children }: { heavy?: boolean; children: React.ReactNode }) {
  return (
    <div className="panel p-3.5 mb-4 mono text-[0.8rem] animate-in"
      style={{ borderWidth: heavy ? 3 : 2, color: 'var(--text)' }}>
      {children}
    </div>
  )
}

const STATUS = {
  verified: { label: 'Verified', Icon: CheckCircle, heavy: false },
  needs_human: { label: 'Needs Review', Icon: AlertTriangle, heavy: true },
  draft: { label: 'Draft', Icon: FileText, heavy: false },
} as const

function MatchCard({ item, index }: { item: MatchedOpportunity; index: number }) {
  const [open, setOpen] = useState(false)
  const { opportunity: o, match: m, draft: d } = item
  return (
    <article className="p-5 sm:p-6" style={{ borderLeft: '2px solid var(--hairline)', borderRight: '2px solid var(--hairline)', borderBottom: '2px solid var(--hairline)' }}>
      {/* header row */}
      <div className="flex justify-between gap-4 items-start">
        <div>
          <div className="label text-[0.62rem] mb-1" style={{ color: 'var(--muted)' }}>
            Result {String(index + 1).padStart(2, '0')}
          </div>
          <h3 className="font-bold text-[1.08rem] leading-snug tracking-tight">
            {o.url ? <a href={o.url} target="_blank" rel="noopener" className="underline decoration-2 underline-offset-2">{o.title}</a> : o.title}
          </h3>
          {o.agency && <div className="text-[0.88rem] mt-0.5" style={{ color: 'var(--muted)' }}>{o.agency}</div>}
        </div>
        <div className="mono font-bold text-[1.4rem] shrink-0 tabular-nums">{Math.round(m.fit_score * 100)}%</div>
      </div>

      <div className="my-3" style={{ borderTop: '1px solid var(--faint)' }} />

      <p className="text-[0.93rem]">{m.reasoning}</p>
      {m.caveats.length > 0 && (
        <ul className="mt-2 text-[0.85rem] list-disc pl-5" style={{ color: 'var(--muted)' }}>
          {m.caveats.map((c, i) => <li key={i}>{c}</li>)}
        </ul>
      )}

      <div className="mt-3 flex flex-wrap gap-2 items-center">
        <span className="badge">{o.source.replace('_', '.')}</span>
        {m.low_confidence && <span className="badge">Low Confidence</span>}
        {d && (
          <span className="badge" data-weight={STATUS[d.status].heavy ? 'heavy' : undefined}>
            {(() => { const I = STATUS[d.status].Icon; return <I size={12} strokeWidth={2.5} /> })()}
            {STATUS[d.status].label}
          </span>
        )}
      </div>
      {(o.typical_award || o.close_date) && (
        <div className="mt-2 flex flex-wrap gap-4 mono text-[0.78rem]" style={{ color: 'var(--muted)' }}>
          {o.typical_award && <span>AWARD: {o.typical_award}</span>}
          {o.close_date && <span>DEADLINE: {o.close_date}</span>}
        </div>
      )}

      {d && d.status === 'needs_human' && d.unresolved_claims.length > 0 && (
        <div className="mt-4 pl-3" style={{ borderLeft: '3px solid var(--error)' }}>
          <p className="label text-[0.66rem] mb-1">Flagged — Unsupported Claims</p>
          {d.unresolved_claims.map((c, i) => (
            <div key={i} className="mb-1.5">
              <div className="text-[0.88rem]">{c.claim}</div>
              <div className="text-[0.8rem]" style={{ color: 'var(--muted)' }}>{c.reason}</div>
            </div>
          ))}
        </div>
      )}

      {d && (
        <>
          <button className="btn btn-ghost mt-4 !py-2 !px-3 text-[0.78rem] !shadow-none" onClick={() => setOpen((v) => !v)}>
            <ChevronDown size={15} strokeWidth={2.5} style={{ transform: open ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s var(--ease-spring)' }} />
            {open ? 'Hide' : 'Show'} Eligibility Summary & Boilerplate
          </button>
          {open && (
            <div className="mt-3 grid gap-3 animate-in">
              <div>
                <p className="label text-[0.64rem] mb-1.5">Eligibility Summary</p>
                <pre className="p-3 mono text-[0.82rem] whitespace-pre-wrap" style={{ border: '1px solid var(--faint)', background: 'var(--bg)' }}>{d.eligibility_summary}</pre>
              </div>
              <div>
                <p className="label text-[0.64rem] mb-1.5">Boilerplate</p>
                <pre className="p-3 mono text-[0.82rem] whitespace-pre-wrap" style={{ border: '1px solid var(--faint)', background: 'var(--bg)' }}>{d.boilerplate}</pre>
              </div>
            </div>
          )}
        </>
      )}
    </article>
  )
}

export function Results({ result, onReset }: { result: MatchResult; onReset: () => void }) {
  const { matches } = result
  return (
    <section className="animate-in">
      <button className="btn btn-ghost mb-5" onClick={onReset}>
        <ChevronLeft size={16} strokeWidth={2.5} /> New Search
      </button>

      {result.profile_sparse && (
        <Banner>Ranked on limited information. Add geography, project specifics, or mission detail for higher-confidence matches.</Banner>
      )}
      {!result.grants_gov_ok && (
        <Banner heavy>
          Live federal results from grants.gov are unavailable right now
          {result.grants_gov_message ? ` (${result.grants_gov_message})` : ''}. Showing curated sources only.
        </Banner>
      )}

      {matches.length === 0 ? (
        <div className="panel p-8 text-center">
          <h2 className="font-bold text-lg">No Matches Found</h2>
          <p className="mt-1 text-[0.9rem]" style={{ color: 'var(--muted)' }}>
            Try a broader funding focus or removing optional constraints.
          </p>
        </div>
      ) : (
        <>
          <h2 className="label text-[0.85rem] mb-4">
            {matches.length} Ranked Match{matches.length === 1 ? '' : 'es'}
          </h2>
          {/* shared-border stack: top border on the group, each card carries the rest */}
          <div style={{ borderTop: '2px solid var(--hairline)' }}>
            {matches.map((m, i) => <MatchCard key={m.opportunity.id} item={m} index={i} />)}
          </div>
        </>
      )}
    </section>
  )
}
