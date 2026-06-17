import { useState } from 'react'

// Generalized searchable dropdown. Behaves like the old ClientDropdown but with
// generic field keys so it can be reused for clients, motorcycles, etc.
export default function SearchableSelect({
  options = [],
  value,
  onChange,
  labelKey,
  subLabelKey = null,
  valueKey,
  placeholder = 'Buscar...',
  disabled = false,
}) {
  // The currently-selected option (if any). Used so the input shows the right
  // label after an external remount/reset (e.g. via a key prop).
  const selectedOption = options.find(o => String(o[valueKey]) === String(value))
  const [filter, setFilter] = useState(selectedOption ? String(selectedOption[labelKey]) : '')

  const hasSelection = value != null && value !== '' && !!selectedOption

  const q = filter.trim().toLowerCase()
  const results = q
    ? options.filter(o => {
        const label = String(o[labelKey] ?? '').toLowerCase()
        const sub = subLabelKey ? String(o[subLabelKey] ?? '').toLowerCase() : ''
        return label.includes(q) || (subLabelKey && sub.includes(q))
      })
    : options

  const showDropdown = filter.length > 0 && !hasSelection

  function handleInput(e) {
    setFilter(e.target.value)
    // Typing after a selection clears it (resets the search).
    if (hasSelection) onChange('')
  }

  function handleSelect(opt) {
    onChange(opt[valueKey])
    setFilter(String(opt[labelKey]))
  }

  return (
    <div style={{ position: 'relative' }}>
      <input
        type="text"
        placeholder={placeholder}
        value={filter}
        disabled={disabled}
        onChange={handleInput}
        style={{ width: '100%', marginBottom: '0' }}
      />
      {showDropdown && (
        <div style={{
          border: '1px solid #E2E8F0', borderRadius: '0 0 0.4rem 0.4rem',
          maxHeight: '180px', overflowY: 'auto', background: '#fff',
          boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
        }}>
          {results.length === 0 ? (
            <div style={{ padding: '0.6rem 0.75rem', color: '#94A3B8', fontSize: '0.85rem' }}>No se encontraron resultados.</div>
          ) : (
            results.map(opt => (
              <div
                key={opt[valueKey]}
                style={{
                  padding: '0.5rem 0.75rem', cursor: 'pointer',
                  borderBottom: '1px solid #F1F5F9',
                }}
                onMouseEnter={e => e.currentTarget.style.background = '#F8FAFC'}
                onMouseLeave={e => e.currentTarget.style.background = '#fff'}
                onClick={() => handleSelect(opt)}
              >
                <strong style={{ fontSize: '0.88rem' }}>{opt[labelKey]}</strong>
                {subLabelKey && (
                  <span style={{ color: '#94A3B8', fontSize: '0.78rem', marginLeft: '0.5rem' }}>{opt[subLabelKey]}</span>
                )}
              </div>
            ))
          )}
        </div>
      )}
    </div>
  )
}
