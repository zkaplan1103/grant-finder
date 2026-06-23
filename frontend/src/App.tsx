import { useEffect, useState } from 'react'
import { Sun, Moon } from 'lucide-react'
import { streamMatch, type MatchResult, type Profile, type Progress } from './lib/api'
import { Wizard } from './components/Wizard'
import { Loading } from './components/Loading'
import { Results } from './components/Results'

type View =
  | { kind: 'form' }
  | { kind: 'loading' }
  | { kind: 'results'; result: MatchResult }
  | { kind: 'error'; message: string }

function useTheme() {
  const [theme, setTheme] = useState<'dark' | 'light'>(
    () => (localStorage.getItem('theme') as 'dark' | 'light') || 'light',
  )
  useEffect(() => {
    document.documentElement.dataset.theme = theme
    localStorage.setItem('theme', theme)
  }, [theme])
  return { theme, toggle: () => setTheme((t) => (t === 'dark' ? 'light' : 'dark')) }
}

export default function App() {
  const [view, setView] = useState<View>({ kind: 'form' })
  const [progress, setProgress] = useState<Progress | null>(null)
  const { theme, toggle } = useTheme()

  async function run(profile: Profile) {
    setProgress(null)
    setView({ kind: 'loading' })
    try {
      const result = await streamMatch(profile, setProgress)
      setView({ kind: 'results', result })
    } catch (e) {
      setView({ kind: 'error', message: e instanceof Error ? e.message : 'Something went wrong.' })
    }
  }

  return (
    <div className="min-h-full max-w-2xl mx-auto px-5">
      <header className="flex items-center justify-between py-5" style={{ borderBottom: '2px solid var(--hairline)' }}>
        <div className="flex items-center gap-3">
          <span className="grid place-items-center w-9 h-9 mono font-bold text-[1.05rem] border-2"
            style={{ background: 'var(--ink)', color: 'var(--ink-on)', borderColor: 'var(--ink)' }}>
            G
          </span>
          <span className="font-bold text-[1.05rem] tracking-wide uppercase">Grant Navigator</span>
        </div>
        <button className="btn-icon" onClick={toggle} aria-label="Toggle light or dark mode" title="Toggle theme">
          {theme === 'dark' ? <Sun size={18} strokeWidth={2.25} /> : <Moon size={18} strokeWidth={2.25} />}
        </button>
      </header>

      <main className="py-10">
        {view.kind === 'form' && (
          <div className="mb-8 animate-in">
            <h1 className="text-[1.9rem] font-bold tracking-tight leading-tight uppercase">
              Find the right funding<br />for your organization
            </h1>
            <p className="mt-3 text-[1.0rem]" style={{ color: 'var(--muted)' }}>
              Tell us about your organization and what you need funding for. We search federal
              and curated grant programs, rank the best fits, and prepare application text for
              each — fact-checked against your details so you can trust what you submit.
            </p>
          </div>
        )}

        {view.kind === 'form' && <Wizard onSubmit={run} />}
        {view.kind === 'loading' && <Loading progress={progress} />}
        {view.kind === 'results' && (
          <Results result={view.result} onReset={() => setView({ kind: 'form' })} />
        )}
        {view.kind === 'error' && (
          <section className="panel p-8 animate-in" style={{ borderColor: 'var(--error)' }}>
            <h2 className="font-bold text-[1.3rem] tracking-tight uppercase">Couldn’t Complete the Search</h2>
            <div className="my-4" style={{ height: 3, background: 'var(--error)', width: '100%' }} />
            <p className="text-[0.95rem]" style={{ color: 'var(--muted)' }}>{view.message}</p>
            <button className="btn btn-primary mt-6" onClick={() => setView({ kind: 'form' })}>Try Again</button>
          </section>
        )}
      </main>

      <footer className="py-8 mono text-[0.76rem]" style={{ color: 'var(--muted)', borderTop: '2px solid var(--hairline)' }}>
        © {new Date().getFullYear()} Zachary Kaplan. All rights reserved.
      </footer>
    </div>
  )
}
