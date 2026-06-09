import RecordCard from './RecordCard'

export default function ActivitySelector({ activity, loading, selectedRec, setSelectedRec, mode }) {
  if (loading) return <div className="caption">Cargando actividad...</div>
  const hasSales = (activity.sales || []).length > 0
  const resItems = mode === 'transfer'
    ? (activity.reservations || [])
    : (activity.standalone_reservations || [])
  const hasRes = mode !== 'cancel' && mode !== 'transfer' && resItems.length > 0
  const resLabel = mode === 'transfer' ? 'Reservaciones' : 'Reservaciones sin Venta'
  if (!hasSales && !hasRes) return <div className="caption">No hay actividad activa para este cliente.</div>
  return (
    <>
      {hasSales && (
        <>
          <div className="card-section" style={{ marginTop: '0.5rem' }}>Ventas Activas</div>
          {activity.sales.map(s => (
            <RecordCard
              key={`sale-${s.sale_id}`}
              record={{ type: 'sale', id: s.sale_id, data: s }}
              isSelected={selectedRec?.type === 'sale' && selectedRec?.id === s.sale_id}
              onClick={() => setSelectedRec({ type: 'sale', id: s.sale_id, data: s })}
            />
          ))}
        </>
      )}
      {hasRes && (
        <>
          <div className="card-section" style={{ marginTop: '0.5rem' }}>{resLabel}</div>
          {resItems.map(r => (
            <RecordCard
              key={`res-${r.reservation_id}`}
              record={{ type: 'reservation', id: r.reservation_id, data: r }}
              isSelected={selectedRec?.type === 'reservation' && selectedRec?.id === r.reservation_id}
              onClick={() => setSelectedRec({ type: 'reservation', id: r.reservation_id, data: r })}
            />
          ))}
        </>
      )}
    </>
  )
}
