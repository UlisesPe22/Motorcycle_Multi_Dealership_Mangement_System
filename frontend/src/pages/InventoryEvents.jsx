import { useNavigate } from 'react-router-dom'
import PageHeader from '../components/PageHeader'

const EVENTS = [
  { path: '/orden-compra',      icon: '≡', title: 'Orden de Compra',   desc: 'Registrar la compra de nuevas motocicletas' },
  { path: '/orden-traslado',    icon: '▷', title: 'Orden de Traslado', desc: 'Confirmar el traslado de motocicletas en camino' },
  { path: '/registrar-entrega', icon: '✔', title: 'Registrar Entrega', desc: 'Confirmar la entrega de motocicletas al inventario' },
]

export default function InventoryEvents() {
  const navigate = useNavigate()

  return (
    <>
      <PageHeader section="Inventario" title="Eventos de Inventario" />

      <div className="col-center">
        <div style={{ width: '100%', maxWidth: '680px' }}>
          <div className="upload-label" style={{ marginBottom: '1rem', fontSize: '0.95rem' }}>
            Selecciona el tipo de evento
          </div>
          <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
            {EVENTS.map(({ path, icon, title, desc }) => (
              <button
                key={path}
                onClick={() => navigate(path)}
                style={{
                  flex: '1 1 180px', padding: '1.5rem 1rem',
                  border: '2px solid #E2E8F0', borderRadius: '0.75rem',
                  background: '#FAFAFA', cursor: 'pointer',
                  textAlign: 'center', transition: 'border-color 0.15s, background 0.15s',
                }}
                onMouseEnter={e => { e.currentTarget.style.borderColor = '#1D4ED8'; e.currentTarget.style.background = '#EFF6FF' }}
                onMouseLeave={e => { e.currentTarget.style.borderColor = '#E2E8F0'; e.currentTarget.style.background = '#FAFAFA' }}
              >
                <div style={{ fontSize: '1.75rem', marginBottom: '0.5rem' }}>{icon}</div>
                <div style={{ fontWeight: 700, fontSize: '1rem', marginBottom: '0.25rem' }}>{title}</div>
                <div style={{ fontSize: '0.78rem', color: '#64748B' }}>{desc}</div>
              </button>
            ))}
          </div>
        </div>
      </div>
    </>
  )
}
