import { useState } from 'react'
import type { Profile } from '../lib/api'
import { StepRequired, StepGeography, StepMission } from './steps'

export interface FormState {
  // required
  project_type: string
  is_501c3: string
  funding_preference: 'grant' | 'loan' | 'either'
  annual_budget_usd: string
  org_age_years: string
  // geography + project
  state: string
  disadvantaged_community: string
  service_area: string
  project_specific_type: string
  stage: string
  // mission + amounts
  estimated_cost_usd: string
  amount_needed_usd: string
  mission_statement: string
  populations_served: string
}

const EMPTY: FormState = {
  project_type: '', is_501c3: 'true', funding_preference: 'grant',
  annual_budget_usd: '', org_age_years: '',
  state: '', disadvantaged_community: '', service_area: '',
  project_specific_type: '', stage: '',
  estimated_cost_usd: '', amount_needed_usd: '', mission_statement: '', populations_served: '',
}

const numOpt = (v: string) => (v.trim() === '' ? undefined : Number(v))
const strOpt = (v: string) => (v.trim() === '' ? undefined : v.trim())
const boolOpt = (v: string) => (v === '' ? null : v === 'true')

function toProfile(f: FormState): Profile {
  return {
    org_basics: {
      is_501c3: f.is_501c3 === 'true',
      annual_budget_usd: Number(f.annual_budget_usd),
      org_age_years: Number(f.org_age_years),
    },
    project_type: f.project_type.trim(),
    funding_preference: f.funding_preference,
    geography: {
      state: strOpt(f.state),
      service_area: strOpt(f.service_area),
      disadvantaged_community: boolOpt(f.disadvantaged_community),
    },
    project: {
      project_type: strOpt(f.project_specific_type),
      stage: strOpt(f.stage),
      estimated_cost_usd: numOpt(f.estimated_cost_usd),
      amount_needed_usd: numOpt(f.amount_needed_usd),
    },
    mission: {
      mission_statement: strOpt(f.mission_statement),
      populations_served: f.populations_served.split(',').map((s) => s.trim()).filter(Boolean),
    },
  }
}

const STEPS = ['Your Organization', 'Geography & Project', 'Mission & Amounts']
const SHORT = ['ORG', 'GEOGRAPHY', 'MISSION']

export function Wizard({ onSubmit }: { onSubmit: (p: Profile) => void }) {
  const [step, setStep] = useState(0)
  const [dir, setDir] = useState<'fwd' | 'back'>('fwd')
  const [form, setForm] = useState<FormState>(EMPTY)
  const set = <K extends keyof FormState>(key: K, value: FormState[K]) =>
    setForm((f) => ({ ...f, [key]: value }))

  const go = (next: number) => { setDir(next > step ? 'fwd' : 'back'); setStep(next) }

  const requiredOk =
    form.project_type.trim() !== '' &&
    form.annual_budget_usd.trim() !== '' &&
    form.org_age_years.trim() !== ''

  const last = step === STEPS.length - 1

  return (
    <section className="panel p-6 sm:p-8 animate-in">
      {/* Numbered-square stepper */}
      <div className="flex items-center mb-8">
        {STEPS.map((label, i) => (
          <div key={label} className="flex items-center" style={{ flex: i < STEPS.length - 1 ? '1' : '0 0 auto' }}>
            <div className="flex flex-col items-center gap-1.5">
              <div className="grid place-items-center w-8 h-8 mono text-[0.85rem] font-bold border-2"
                style={{
                  background: i <= step ? 'var(--ink)' : 'transparent',
                  color: i <= step ? 'var(--ink-on)' : 'var(--muted)',
                  borderColor: i <= step ? 'var(--ink)' : 'var(--faint)',
                }}>
                {i + 1}
              </div>
              <span className="label text-[0.62rem]"
                style={{ color: i === step ? 'var(--text)' : 'var(--muted)' }}>
                {SHORT[i]}
              </span>
            </div>
            {i < STEPS.length - 1 && (
              <div className="flex-1 mx-2 mb-4" style={{ height: 2, background: i < step ? 'var(--ink)' : 'var(--faint)' }} />
            )}
          </div>
        ))}
      </div>

      <div key={step} className={dir === 'fwd' ? 'anim-fwd' : 'anim-back'}>
        {step === 0 && <StepRequired form={form} set={set} />}
        {step === 1 && <StepGeography form={form} set={set} />}
        {step === 2 && <StepMission form={form} set={set} />}
      </div>

      <div className="flex justify-between mt-8 pt-6" style={{ borderTop: '2px solid var(--faint)' }}>
        {step > 0 ? (
          <button className="btn btn-ghost" onClick={() => go(step - 1)}>Back</button>
        ) : <span />}
        {last ? (
          <button className="btn btn-primary" disabled={!requiredOk} onClick={() => onSubmit(toProfile(form))}>
            Find Funding Matches
          </button>
        ) : (
          <button className="btn btn-primary" disabled={step === 0 && !requiredOk} onClick={() => go(step + 1)}>
            Next
          </button>
        )}
      </div>
      {step === 0 && !requiredOk && (
        <p className="mono text-[0.78rem] mt-3" style={{ color: 'var(--muted)' }}>
          Funding focus, budget, and org age are required to continue.
        </p>
      )}
    </section>
  )
}
