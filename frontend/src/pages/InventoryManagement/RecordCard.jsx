import { fmt } from '../../utils'

export default function RecordCard({ record, isSelected, onClick }) {
  const borderColor = isSelected ? '#1D4ED8' : '#E2E8F0'
  const bg          = isSelected ? '#EFF6FF' : '#FAFAFA'

  if (record.type === 'reservation') {
    const r = record.data
    return (
      <div
        onClick={onClick}
        style={{ border: `2px solid ${borderColor}`, borderRadius: '0.5rem', padding: '0.75rem', marginBottom: '0.5rem', cursor: 'pointer', background: bg }}
      >
        <div style={{ fontWeight: 700 }}>{r.model_name} {r.year}</div>
        <div style={{ fontSize: '0.82rem', color: '#64748B' }}>
          Depósito: ${fmt(r.deposit_amount)} · {r.dealership_name} · Estado: {r.status}
        </div>
        {r.motorcycle && (
          <div style={{ fontSize: '0.82rem', color: '#15803D', marginTop: '0.25rem' }}>
            Moto asignada: {r.motorcycle.model_name} — Serie: {r.motorcycle.serie || '—'} · Motor: {r.motorcycle.motor || '—'}
          </div>
        )}
      </div>
    )
  }

  const s = record.data
  const refundable = (s.events || [])
    .filter(ev => ev.event_type !== 'financing')
    .reduce((sum, ev) => sum + (ev.items || []).reduce((s2, item) => s2 + item.amount, 0), 0)

  // Extract unique event types for display
  const eventTypesArray = (s.events || [])
    .filter(ev => ev.event_type !== 'financing')
    .map(ev => ev.event_type)
  const TYPE_ES = {
    reservation: 'reserva',
    al_contado:  'al contado',
    enganche:    'enganche',
  }
  const uniqueEventTypes = [...new Set(eventTypesArray)]
  const eventTypesLabel = uniqueEventTypes.length > 0
    ? uniqueEventTypes.map(t => TYPE_ES[t] || t).join(' / ')
    : 'Sin pagos'

  return (
    <div
      onClick={onClick}
      style={{ border: `2px solid ${borderColor}`, borderRadius: '0.5rem', padding: '0.75rem', marginBottom: '0.5rem', cursor: 'pointer', background: bg }}
    >
      {s.motorcycle ? (
        <div style={{ fontWeight: 700 }}>{s.motorcycle.model_name} {s.motorcycle.year} — {s.motorcycle.color || '—'}</div>
      ) : (
        <div style={{ fontWeight: 700 }}>Venta sin moto asignada</div>
      )}
      <div style={{ fontSize: '0.82rem', color: '#64748B' }}>
        Total: ${fmt(s.total_price)} · Verificado: ${fmt(s.amount_verified)} · {s.dealership_name || '—'}
      </div>
      
      {/* Event types line */}
      <div style={{ fontSize: '0.82rem', color: '#0284C7', marginTop: '0.25rem', fontWeight: 500 }}>
        Pagos: <span style={{ textTransform: 'capitalize' }}>{eventTypesLabel}</span>
      </div>

      {s.motorcycle && (
        <div style={{ fontSize: '0.82rem', fontFamily: 'monospace', color: '#475569', marginTop: '0.25rem' }}>
          Serie: {s.motorcycle.serie || '—'} · Motor: {s.motorcycle.motor || '—'}
        </div>
      )}
      {refundable > 0 && (
        <div style={{ fontSize: '0.82rem', color: '#D97706', marginTop: '0.25rem' }}>
          A reembolsar: ${fmt(refundable)}
        </div>
      )}
    </div>
  )
}