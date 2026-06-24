import { useEffect, useState } from 'react'
import {
  ChevronLeft, ChevronRight, CheckCircle, AlertTriangle, FileText,
  ExternalLink, Copy, Check, RotateCcw,
} from 'lucide-react'
import type { MatchResult, MatchedOpportunity, Draft, Match } from '../lib/api'

const SOURCE_LABEL: Record<string, string> = {
  grants_gov: 'grants.gov',
  curated: 'curated list',
}

const STATUS = {
  verified: { label: 'Verified', Icon: CheckCircle, tone: 'ok' as const },
  needs_human: { label: 'Needs Review', Icon: AlertTriangle, tone: 'warn' as const },
  draft: { label: 'Draft', Icon: FileText, tone: undefined },
} as const

function fitColor(m: Match): string {
  if (m.low_confidence) return 'var(--muted)'
  return m.fit_score >= 0.7 ? 'var(--ok)' : m.fit_score >= 0.5 ? 'var(--warn)' : 'var(--muted)'
}

// Trail = "issues found vs. resolved across N passes" (DESIGN.md §9). Only shown
// when it ADDS information beyond the badge — i.e. the loop actually did work
// (revision > 0 or unresolved claims). A clean first-pass verified shows nothing
// here (the VERIFIED badge already says it), per the de-dup decision.
function trailLine(d: Draft): { text: string; tone?: 'ok' } | null {
  const passes = d.revision + 1
  const passLabel = `${passes} ${passes === 1 ? 'pass' : 'passes'}`
  if (d.status === 'verified') {
    const found = d.revision
    if (found === 0) return null // redundant with the VERIFIED badge
    return { text: `Found ${found} unsupported ${found === 1 ? 'claim' : 'claims'}, resolved across ${passLabel}`, tone: 'ok' }
  }
  const open = d.unresolved_claims.length
  return { text: `${open} unsupported ${open === 1 ? 'claim' : 'claims'} unresolved after ${passLabel}` }
}

function Banner({ heavy, children }: { heavy?: boolean; children: React.ReactNode }) {
  return (
    <div className="panel p-3.5 mb-4 mono text-[0.8rem] animate-in"
      style={{ borderWidth: heavy ? 3 : 2, color: 'var(--text)' }}>
      {children}
    </div>
  )
}

// Semantic half-circle fit gauge (data-zone register: flat, rounded-cap stroke).
function FitGauge({ m }: { m: Match }) {
  const pct = Math.round(m.fit_score * 100)
  const color = fitColor(m)
  const R = 80, CX = 100, CY = 100, STROKE = 16
  const semi = Math.PI * R                       // length of the half-arc
  const dash = (m.fit_score) * semi
  const arc = `M ${CX - R} ${CY} A ${R} ${R} 0 0 1 ${CX + R} ${CY}`
  return (
    <div className="flex flex-col items-center" role="img"
      aria-label={`Fit score ${pct} percent${m.low_confidence ? ', low confidence' : ''}`}>
      <svg viewBox="0 0 200 116" width="200" height="116" style={{ opacity: m.low_confidence ? 0.6 : 1 }}>
        <path d={arc} fill="none" stroke="var(--line)" strokeWidth={STROKE} strokeLinecap="round" />
        <path d={arc} fill="none" stroke={color} strokeWidth={STROKE} strokeLinecap="round"
          strokeDasharray={`${dash} ${semi}`}
          style={{ transition: 'stroke-dasharray 0.6s var(--ease-spring)' }} />
        <text x="100" y="96" textAnchor="middle"
          style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, fontSize: 38, fill: 'var(--text)' }}>
          {pct}<tspan style={{ fontSize: 18, fill: 'var(--muted)' }}>%</tspan>
        </text>
      </svg>
      {m.low_confidence && <span className="mono text-[0.68rem]" style={{ color: 'var(--muted)' }}>low confidence</span>}
    </div>
  )
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  async function copy() {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch { /* clipboard unavailable; no-op */ }
  }
  return (
    <button className="btn btn-ghost !py-2 !px-3 text-[0.78rem] !shadow-none" onClick={copy}
      aria-label="Copy boilerplate to clipboard">
      {copied ? <Check size={15} strokeWidth={2.5} /> : <Copy size={15} strokeWidth={2.5} />}
      {copied ? 'Copied' : 'Copy'}
    </button>
  )
}

function FlipCard({ item, index }: { item: MatchedOpportunity; index: number }) {
  const [flipped, setFlipped] = useState(false)
  const { opportunity: o, match: m, draft: d } = item
  // Reset to front whenever the card (index) changes.
  useEffect(() => { setFlipped(false) }, [index])

  const front = (
    <div className="flip-face dcard p-5 sm:p-6" data-low={m.low_confidence} data-status={d?.status}>
      <FitGauge m={m} />

      <div className="flex items-center gap-2 mt-2 mb-1.5 justify-center flex-wrap">
        {d && (() => { const { Icon, label, tone } = STATUS[d.status]; return (
          <span className="badge" data-tone={tone}><Icon size={12} strokeWidth={2.5} />{label}</span>
        )})()}
      </div>

      <h3 className="font-semibold text-[1.1rem] leading-snug tracking-tight text-center">{o.title}</h3>
      {o.agency && <div className="text-[0.86rem] mt-0.5 text-center" style={{ color: 'var(--muted)' }}>{o.agency}</div>}

      <ul className="mt-4 text-[0.9rem] grid gap-1" style={{ listStyle: 'none', padding: 0 }}>
        <li className="flex gap-2"><span style={{ color: 'var(--muted)' }}>›</span><span>{m.reasoning}</span></li>
        {d?.eligibility_summary && (
          <li className="flex gap-2"><span style={{ color: 'var(--muted)' }}>›</span><span>{d.eligibility_summary}</span></li>
        )}
        {m.caveats.map((c, i) => (
          <li key={i} className="flex gap-2" style={{ color: 'var(--muted)' }}><span>›</span><span>{c}</span></li>
        ))}
      </ul>

      {/* one source signal: a link that names the source, or a plain label when no url */}
      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-2 items-center mono text-[0.74rem]" style={{ color: 'var(--muted)' }}>
        {o.url ? (
          <a href={o.url} target="_blank" rel="noopener"
            className="inline-flex items-center gap-1 underline decoration-1 underline-offset-2" style={{ color: 'var(--muted)' }}>
            View at {SOURCE_LABEL[o.source] ?? o.source} <ExternalLink size={11} strokeWidth={2.5} />
          </a>
        ) : (
          <span className="source-chip"><span className="src-label">SOURCE</span>{SOURCE_LABEL[o.source] ?? o.source}</span>
        )}
        {o.typical_award && <span>AWARD: {o.typical_award}</span>}
        {o.close_date && <span>DEADLINE: {o.close_date}</span>}
      </div>

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

      {d && (() => { const t = trailLine(d); return t ? <div className="trail" data-tone={t.tone}>{t.text}</div> : null })()}

      {d && (
        <button className="btn btn-ghost mt-4 !py-2 !px-3 text-[0.78rem] !shadow-none" onClick={() => setFlipped(true)}>
          <FileText size={15} strokeWidth={2.5} /> View boilerplate
        </button>
      )}
    </div>
  )

  const back = (
    <div className="flip-face flip-back dcard p-5 sm:p-6 flex flex-col">
      <div className="flex items-center justify-between mb-3">
        <p className="mono text-[0.64rem] uppercase tracking-wider" style={{ color: 'var(--muted)' }}>
          Application boilerplate
        </p>
        {d && <CopyButton text={d.boilerplate} />}
      </div>
      {d && (
        <pre className="p-3 text-[0.82rem] whitespace-pre-wrap font-sans flex-1 overflow-auto"
          style={{ border: '1px solid var(--line)', borderRadius: 8, background: 'var(--paper)' }}>{d.boilerplate}</pre>
      )}
      <button className="btn btn-ghost mt-4 !py-2 !px-3 text-[0.78rem] !shadow-none self-start" onClick={() => setFlipped(false)}>
        <RotateCcw size={15} strokeWidth={2.5} /> Back to summary
      </button>
    </div>
  )

  return (
    <div className="flip-scene">
      <div className="flip-inner" data-flipped={flipped}>
        {front}
        {back}
      </div>
    </div>
  )
}

export function Results({ result, onReset }: { result: MatchResult; onReset: () => void }) {
  const { matches } = result
  const [i, setI] = useState(0)
  const [dir, setDir] = useState<'fwd' | 'back'>('fwd')
  const n = matches.length
  const cur = Math.min(i, Math.max(0, n - 1))

  const goTo = (next: number) => {
    const clamped = Math.max(0, Math.min(next, n - 1))
    setDir(clamped >= cur ? 'fwd' : 'back')
    setI(clamped)
  }

  // Keyboard ←/→ deck navigation.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'ArrowRight') goTo(cur + 1)
      if (e.key === 'ArrowLeft') goTo(cur - 1)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [cur, n])

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

      {n === 0 ? (
        <div className="dcard p-8 text-center">
          <h2 className="font-semibold text-lg">No matches found</h2>
          <p className="mt-1 text-[0.9rem]" style={{ color: 'var(--muted)' }}>
            Try a broader funding focus or removing optional constraints.
          </p>
        </div>
      ) : (
        <>
          <h2 className="label text-[0.85rem] mb-4">
            {n} Ranked Match{n === 1 ? '' : 'es'}
          </h2>

          <div key={matches[cur].opportunity.id} className={dir === 'fwd' ? 'anim-fwd' : 'anim-back'}>
            <FlipCard item={matches[cur]} index={cur} />
          </div>

          {/* deck navigation: prev / position + dots / next */}
          <div className="flex items-center justify-between mt-5">
            <button className="btn btn-ghost !py-2 !px-3" disabled={cur === 0}
              onClick={() => goTo(cur - 1)} aria-label="Previous match">
              <ChevronLeft size={16} strokeWidth={2.5} /> Prev
            </button>

            <div className="flex flex-col items-center gap-1.5">
              <span className="mono text-[0.74rem]" style={{ color: 'var(--muted)' }}>
                {cur + 1} of {n}
              </span>
              <div className="flex gap-1.5">
                {matches.map((mm, k) => (
                  <button key={mm.opportunity.id} aria-label={`Go to match ${k + 1}`}
                    onClick={() => goTo(k)} className="deck-dot" data-active={k === cur} />
                ))}
              </div>
            </div>

            <button className="btn btn-ghost !py-2 !px-3" disabled={cur === n - 1}
              onClick={() => goTo(cur + 1)} aria-label="Next match">
              Next <ChevronRight size={16} strokeWidth={2.5} />
            </button>
          </div>
        </>
      )}
    </section>
  )
}
