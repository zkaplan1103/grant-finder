import { Field, Combobox, NumberInput } from './Field'
import type { FormState } from './Wizard'

type StepProps = {
  form: FormState
  set: <K extends keyof FormState>(key: K, value: FormState[K]) => void
}

const BUDGETS = [
  { value: '50000', label: 'Under $100k' },
  { value: '250000', label: '$100k – $500k' },
  { value: '750000', label: '$500k – $1M' },
  { value: '2000000', label: 'Over $1M' },
]
const AGES = [
  { value: '1', label: 'New (< 2 yrs)' },
  { value: '5', label: 'Established (5 yrs)' },
  { value: '15', label: 'Mature (15+ yrs)' },
]
const FOCUS = [
  { value: 'solar', label: 'Solar' },
  { value: 'clean energy', label: 'Clean energy' },
  { value: 'food security', label: 'Food security' },
  { value: 'youth literacy', label: 'Youth literacy' },
  { value: 'affordable housing', label: 'Affordable housing' },
  { value: 'mental health', label: 'Mental health' },
]
const STAGES = [
  { value: 'planning', label: 'Planning' },
  { value: 'shovel-ready', label: 'Shovel-ready' },
  { value: 'in progress', label: 'In progress' },
]

export function StepRequired({ form, set }: StepProps) {
  return (
    <div className="grid gap-5">
      <Field label="Funding focus" hint="what you need money for" required>
        <Combobox value={form.project_type} onChange={(v) => set('project_type', v)}
          options={FOCUS} placeholder="e.g. solar, food security" />
      </Field>

      <div className="grid grid-cols-2 gap-4 max-[560px]:grid-cols-1">
        <Field label="501(c)(3) status" required>
          <select className="field-input" value={form.is_501c3} onChange={(e) => set('is_501c3', e.target.value)}>
            <option value="true">Yes — 501(c)(3)</option>
            <option value="false">No / other nonprofit</option>
          </select>
        </Field>
        <Field label="Grant or loan?" required>
          <select className="field-input" value={form.funding_preference}
            onChange={(e) => set('funding_preference', e.target.value as FormState['funding_preference'])}>
            <option value="grant">Grant</option>
            <option value="loan">Loan</option>
            <option value="either">Either</option>
          </select>
        </Field>
      </div>

      <div className="grid grid-cols-2 gap-4 max-[560px]:grid-cols-1">
        <Field label="Annual budget (USD)" hint="type or pick" required>
          <Combobox numeric value={form.annual_budget_usd}
            onChange={(v) => set('annual_budget_usd', v)} options={BUDGETS} placeholder="300,000" />
        </Field>
        <Field label="Org age (years)" hint="type or pick" required>
          <Combobox numeric value={form.org_age_years}
            onChange={(v) => set('org_age_years', v)} options={AGES} placeholder="5" />
        </Field>
      </div>
    </div>
  )
}

function OptionalNotice() {
  return (
    <p className="label" style={{ borderTop: '2px solid var(--hairline)', paddingTop: '0.75rem', color: 'var(--muted)' }}>
      All fields on this step are optional — more detail means better matches.
    </p>
  )
}

export function StepGeography({ form, set }: StepProps) {
  return (
    <div className="grid gap-5">
      <OptionalNotice />
      <div className="grid grid-cols-2 gap-4 max-[560px]:grid-cols-1">
        <Field label="State" hint="2-letter, e.g. CA">
          <input className="field-input" maxLength={2} value={form.state}
            onChange={(e) => set('state', e.target.value.toUpperCase())} placeholder="CA" />
        </Field>
        <Field label="Serves a disadvantaged community?">
          <select className="field-input" value={form.disadvantaged_community}
            onChange={(e) => set('disadvantaged_community', e.target.value)}>
            <option value="">Not specified</option>
            <option value="true">Yes</option>
            <option value="false">No</option>
          </select>
        </Field>
      </div>
      <Field label="Service area" hint="free text">
        <input className="field-input" value={form.service_area}
          onChange={(e) => set('service_area', e.target.value)} placeholder="Rural counties in central CA" />
      </Field>
      <div className="grid grid-cols-2 gap-4 max-[560px]:grid-cols-1">
        <Field label="Project sub-type" hint="optional">
          <input className="field-input" value={form.project_specific_type}
            onChange={(e) => set('project_specific_type', e.target.value)} placeholder="rooftop, after-school…" />
        </Field>
        <Field label="Stage">
          <Combobox value={form.stage} onChange={(v) => set('stage', v)}
            options={STAGES} placeholder="planning" />
        </Field>
      </div>
    </div>
  )
}

export function StepMission({ form, set }: StepProps) {
  return (
    <div className="grid gap-5">
      <OptionalNotice />
      <div className="grid grid-cols-2 gap-4 max-[560px]:grid-cols-1">
        <Field label="Estimated project cost (USD)">
          <NumberInput value={form.estimated_cost_usd}
            onChange={(v) => set('estimated_cost_usd', v)} placeholder="250,000" />
        </Field>
        <Field label="Amount needed (USD)">
          <NumberInput value={form.amount_needed_usd}
            onChange={(v) => set('amount_needed_usd', v)} placeholder="100,000" />
        </Field>
      </div>
      <Field label="Mission statement">
        <textarea className="field-input" style={{ minHeight: 90, resize: 'vertical' }}
          value={form.mission_statement} onChange={(e) => set('mission_statement', e.target.value)}
          placeholder="We help low-income households…" />
      </Field>
      <Field label="Populations served" hint="comma-separated">
        <input className="field-input" value={form.populations_served}
          onChange={(e) => set('populations_served', e.target.value)} placeholder="low-income, rural, tribal" />
      </Field>
    </div>
  )
}
