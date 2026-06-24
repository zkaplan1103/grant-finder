import { useState } from 'react'
import { ChevronDown, ChevronLeft, CheckCircle, AlertTriangle, FileText, ExternalLink } from 'lucide-react'
import type { MatchResult, MatchedOpportunity, Draft } from '../lib/api'

const SOURCE_LABEL: Record<string, string> = {
  grants_gov: 'grants.gov',
  curated: 'curated list',
}

function Banner({ heavy, children }: { heavy?: boolean; children: React.ReactNode }) {
  return (
    <div className="panel p-3.5 mb-4 mono text-[0.8rem] animate-in"
      style={{ borderWidth: heavy ? 3 : 2, color: 'var(--text)' }}>
      {children}
    </div>
  )
}

const STATUS = {
  verified: { label: 'Verified', Icon: CheckCircle, tone: 'ok' as const },
  needs_human: { label: 'Needs Review', Icon: AlertTriangle, tone: 'warn' as const },
  draft: { label: 'Draft', Icon: FileText, tone: undefined },
} as const

// Trail = "issues found vs. resolved across N passes", derived from revision + unresolved_claims.
// A clean first-pass draft reads as a confident pass, never as empty data (DESIGN.md §9).
function trailLine(d: Draft): { text: string; tone?: 'ok' } {
  const passes = d.revision + 1 // a draft at revision N went through N+1 verify passes
  const passLabel = `${passes} ${passes === 1 ? 'pass' : 'passes'}`
  if (d.status === 'verified') {
    const found = d.revision // each revision was triggered by a found issue
    if (found === 0) return { text: `Passed verification on the first pass — 0 issues found`, tone: 'ok' }
    return { text: `Found ${found} unsupported ${found === 1 ? 'claim' : 'claims'}, resolved across ${passLabel}`, tone: 'ok' }
  }
  // needs_human
  const open = d.unresolved_claims.length
  return { text: `${open} unsupported ${open === 1 ? 'claim' : 'claims'} unresolved after ${passLabel}` }
}

function MatchCard({ item, index }: { item: MatchedOpportunity; index: number }) {
  const [open, setOpen] = useState(false)
  const { opportunity: o, match: m, draft: d } = item
  const scoreColor = m.fit_score >= 0.7 ? 'var(--ok)' : m.fit_score >= 0.5 ? 'var(--warn)' : 'var(--muted)'

  return (
    <article className="dcard p-5 sm:p-6" data-low={m.low_confidence} data-status={d?.status}>
      {/* header: rank + VERIFICATION badge (trust signal, top) + title + score */}
      <div className="flex justify-between gap-4 items-start">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <span className="mono text-[0.62rem] uppercase tracking-wider" style={{ color: 'var(--muted)' }}>
              Result {String(index + 1).padStart(2, '0')}
            </span>
            {d && (() => { const { Icon, label, tone } = STATUS[d.status]; return (
              <span className="badge" data-tone={tone}><Icon size={12} strokeWidth={2.5} />{label}</span>
            )})()}
          </div>
          <h3 className="font-semibold text-[1.05rem] leading-snug tracking-tight">{o.title}</h3>
          {o.agency && <div className="text-[0.86rem] mt-0.5" style={{ color: 'var(--muted)' }}>{o.agency}</div>}
        </div>
        <div className="mono font-bold text-[1.5rem] shrink-0 tabular-nums" style={{ color: scoreColor }}>
          {Math.round(m.fit_score * 100)}%
          {m.low_confidence && <span className="block text-[0.62rem] font-medium text-right" style={{ color: 'var(--muted)' }}>low confidence</span>}
        </div>
      </div>

      {/* scannable summary: fit reasoning + key facts as bullets (never a naked %) */}
      <ul className="mt-3 text-[0.9rem] grid gap-1" style={{ listStyle: 'none', padding: 0 }}>
        <li className="flex gap-2"><span style={{ color: 'var(--muted)' }}>›</span><span>{m.reasoning}</span></li>
        {m.caveats.map((c, i) => (
          <li key={i} className="flex gap-2" style={{ color: 'var(--muted)' }}><span>›</span><span>{c}</span></li>
        ))}
      </ul>

      {/* metadata row: SOURCE chip (neutral, labeled) + award/deadline + optional link */}
      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-2 items-center mono text-[0.74rem]" style={{ color: 'var(--muted)' }}>
        <span className="source-chip"><span className="src-label">SOURCE</span>{SOURCE_LABEL[o.source] ?? o.source}</span>
        {o.typical_award && <span>AWARD: {o.typical_award}</span>}
        {o.close_date && <span>DEADLINE: {o.close_date}</span>}
        {o.url && (
          <a href={o.url} target="_blank" rel="noopener"
            className="inline-flex items-center gap-1 underline decoration-1 underline-offset-2" style={{ color: 'var(--muted)' }}>
            View on grants.gov <ExternalLink size={11} strokeWidth={2.5} />
          </a>
        )}
      </div>

      {/* needs_human: flagged claims, always visible */}
      {d && d.status === 'needs_human' && d.unresolved_claims.length > 0 && (
        <div className="mt-4 claim-gutter">
          <p className="mono text-[0.64rem] uppercase tracking-wider mb-1" style={{ color: 'var(--err)' }}>
            Flagged — unsupported claims
          </p>
          {d.unresolved_claims.map((c, i) => (
            <div key={i} className="mb-1.5">
              <div className="text-[0.88rem]">{c.claim}</div>
              <div className="text-[0.8rem]" style={{ color: 'var(--muted)' }}>{c.reason}</div>
            </div>
          ))}
        </div>
      )}

      {/* verification trail */}
      {d && (() => {
        const t = trailLine(d)
        return <div className="trail" data-tone={t.tone}>{t.text}</div>
      })()}

      {/* single "Details" disclosure: full eligibility summary + boilerplate */}
      {d && (
        <>
          <button className="btn btn-ghost mt-4 !py-2 !px-3 text-[0.78rem] !shadow-none" onClick={() => setOpen((v) => !v)}>
            <ChevronDown size={15} strokeWidth={2.5} style={{ transform: open ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s var(--ease-spring)' }} />
            {open ? 'Hide details' : 'Details'}
          </button>
          {open && (
            <div className="mt-3 grid gap-3 animate-in">
              <div>
                <p className="mono text-[0.64rem] uppercase tracking-wider mb-1.5" style={{ color: 'var(--muted)' }}>Eligibility summary</p>
                <pre className="p-3 text-[0.82rem] whitespace-pre-wrap font-sans" style={{ border: '1px solid var(--line)', borderRadius: 8, background: 'var(--paper)' }}>{d.eligibility_summary}</pre>
              </div>
              <div>
                <p className="mono text-[0.64rem] uppercase tracking-wider mb-1.5" style={{ color: 'var(--muted)' }}>Application boilerplate</p>
                <pre className="p-3 text-[0.82rem] whitespace-pre-wrap font-sans" style={{ border: '1px solid var(--line)', borderRadius: 8, background: 'var(--paper)' }}>{d.boilerplate}</pre>
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
        <div className="dcard p-8 text-center">
          <h2 className="font-semibold text-lg">No matches found</h2>
          <p className="mt-1 text-[0.9rem]" style={{ color: 'var(--muted)' }}>
            Try a broader funding focus or removing optional constraints.
          </p>
        </div>
      ) : (
        <>
          <h2 className="label text-[0.85rem] mb-4">
            {matches.length} Ranked Match{matches.length === 1 ? '' : 'es'}
          </h2>
          <div className="grid gap-3">
            {matches.map((m, i) => <MatchCard key={m.opportunity.id} item={m} index={i} />)}
          </div>
        </>
      )}
    </section>
  )
}
