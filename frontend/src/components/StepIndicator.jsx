export default function StepIndicator({ step, labels }) {
  return (
    <div style={{ display: 'flex', gap: '0', marginBottom: '1.5rem', alignItems: 'center' }}>
      {labels.map((label, i) => {
        const num    = i + 1
        const active = num === step
        const done   = num < step
        return (
          <div key={num} style={{ display: 'flex', alignItems: 'center', flex: 1 }}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.25rem' }}>
              <div style={{
                width: '2rem', height: '2rem', borderRadius: '50%', display: 'flex',
                alignItems: 'center', justifyContent: 'center', fontWeight: 700, fontSize: '0.85rem',
                background: done ? '#15803D' : active ? '#1D4ED8' : '#E2E8F0',
                color: (done || active) ? '#fff' : '#64748B',
              }}>
                {done ? '✓' : num}
              </div>
              <div style={{ fontSize: '0.65rem', color: active ? '#1D4ED8' : '#64748B', whiteSpace: 'nowrap' }}>
                {label}
              </div>
            </div>
            {i < labels.length - 1 && (
              <div style={{ flex: 1, height: '2px', background: done ? '#15803D' : '#E2E8F0', margin: '0 0.25rem', marginBottom: '1rem' }} />
            )}
          </div>
        )
      })}
    </div>
  )
}
