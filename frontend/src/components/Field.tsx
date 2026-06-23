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

// Type-or-pick: free-text input + preset chips below. No popup that can cover the field.
export function Combobox({
  value, onChange, options, placeholder, type = 'text',
}: {
  value: string
  onChange: (v: string) => void
  options: { value: string; label: string }[]
  placeholder?: string
  type?: 'text' | 'number'
}) {
  return (
    <div>
      <input
        className="field-input"
        type={type}
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
      />
      <div className="flex gap-1.5 mt-2 overflow-x-auto pb-1 chip-row">
        {options.map((o) => (
          <button
            key={o.value}
            type="button"
            onClick={() => onChange(o.value)}
            className="chip shrink-0"
            data-active={value === o.value}
          >
            {o.label}
          </button>
        ))}
      </div>
    </div>
  )
}
