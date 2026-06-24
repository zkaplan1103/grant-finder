import type { ReactNode } from 'react'

export function Field({
  label, hint, required, children,
}: { label: string; hint?: string; required?: boolean; children: ReactNode }) {
  return (
    <label className="block">
      <span className="label block mb-2">
        {label}
        {required && <span> *</span>}
        {hint && (
          <span className="ml-2 normal-case tracking-normal font-normal" style={{ color: 'var(--muted)' }}>
            — {hint}
          </span>
        )}
      </span>
      {children}
    </label>
  )
}

// Format an integer string with thousands separators for display: "300000" -> "300,000".
const withCommas = (digits: string) => (digits === '' ? '' : Number(digits).toLocaleString('en-US'))
// Keep only digits (no negatives, no decimals, no letters).
const digitsOnly = (s: string) => s.replace(/[^\d]/g, '')

// Type-or-pick: free-text input + preset chips that WRAP below it (no scroll, no popup).
export function Combobox({
  value, onChange, options, placeholder, numeric = false,
}: {
  value: string                         // always the raw value (digits for numeric)
  onChange: (v: string) => void
  options: { value: string; label: string }[]
  placeholder?: string
  numeric?: boolean
}) {
  return (
    <div>
      <input
        className="field-input"
        type="text"
        inputMode={numeric ? 'numeric' : 'text'}
        value={numeric ? withCommas(value) : value}
        placeholder={placeholder}
        onChange={(e) => onChange(numeric ? digitsOnly(e.target.value) : e.target.value)}
      />
      <div className="flex flex-wrap gap-1.5 mt-2">
        {options.map((o) => (
          <button
            key={o.value}
            type="button"
            onClick={() => onChange(o.value)}
            className="chip"
            data-active={value === o.value}
          >
            {o.label}
          </button>
        ))}
      </div>
    </div>
  )
}

// Plain numeric field (no presets): no spinner, no negatives, comma display.
export function NumberInput({
  value, onChange, placeholder,
}: { value: string; onChange: (v: string) => void; placeholder?: string }) {
  return (
    <input
      className="field-input"
      type="text"
      inputMode="numeric"
      value={withCommas(value)}
      placeholder={placeholder}
      onChange={(e) => onChange(digitsOnly(e.target.value))}
    />
  )
}
