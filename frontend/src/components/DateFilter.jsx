import { BLUE, GREY, BORDER } from '../constants'

const inputStyle = {
  padding: '8px 10px',
  border: `1px solid ${BORDER}`,
  borderRadius: 4,
  fontSize: 14,
  color: '#202124',
  background: '#fff',
  outline: 'none',
}

function Field({ label, children }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <label style={{ fontSize: 12, fontWeight: 600, color: GREY }}>{label}</label>
      {children}
    </div>
  )
}

// Shared filter bar: two date inputs (Desde / Hasta) + Aplicar button.
// `children` is rendered at the start of the bar for any extra leading
// controls (e.g. a Sucursal selector).
export default function DateFilter({
  dateFrom,
  dateTo,
  onDateFromChange,
  onDateToChange,
  onApply,
  loading,
  children,
}) {
  return (
    <div
      style={{
        background: '#fff',
        borderRadius: 8,
        boxShadow: '0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.08)',
        padding: '14px 16px',
        marginBottom: 12,
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'flex-end',
        gap: 14,
      }}
    >
      {children}

      <Field label="Desde">
        <input
          type="date"
          value={dateFrom}
          onChange={(e) => onDateFromChange(e.target.value)}
          style={inputStyle}
        />
      </Field>

      <Field label="Hasta">
        <input
          type="date"
          value={dateTo}
          onChange={(e) => onDateToChange(e.target.value)}
          style={inputStyle}
        />
      </Field>

      <button
        className="date-filter-apply"
        onClick={onApply}
        disabled={loading}
        style={{
          padding: '8px 22px',
          background: BLUE,
          color: '#fff',
          border: 'none',
          borderRadius: 4,
          fontSize: 14,
          fontWeight: 500,
          cursor: loading ? 'not-allowed' : 'pointer',
          opacity: loading ? 0.7 : 1,
        }}
      >
        Aplicar
      </button>
    </div>
  )
}
