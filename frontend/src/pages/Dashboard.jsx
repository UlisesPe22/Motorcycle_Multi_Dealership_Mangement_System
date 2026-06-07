import { useState, useEffect } from 'react'
import api from '../api'
import PageHeader from '../components/PageHeader'

const ROWS_PER_PAGE = 13

const STATUS_ES = {
  purchased:         'Comprada',
  incoming:          'En camino',
  in_stock:          'En stock',
  not_purchased:     'No comprada',
  rejected:          'Rechazada',
  sold:              'Vendida',
  cancelled:         'Cancelada',
  incoming_reserved: 'En camino (Reservada)',
  in_stock_reserved: 'En stock (Reservada)',
  reserved_for_sale: 'Congelada',
  sale_in_progress:  'Venta Iniciada',
  fully_paid:        'Pago Completo',
}

const STATUS_BADGE = {
  purchased:         { bg: '#DBEAFE', fg: '#1D4ED8' },
  incoming:          { bg: '#FEF3C7', fg: '#92400E' },
  in_stock:          { bg: '#DCFCE7', fg: '#15803D' },
  not_purchased:     { bg: '#F1F5F9', fg: '#64748B' },
  rejected:          { bg: '#FEE2E2', fg: '#DC2626' },
  sold:              { bg: '#CCFBF1', fg: '#0D9488' },
  cancelled:         { bg: '#F1F5F9', fg: '#94A3B8' },
  incoming_reserved: { bg: '#FEF3C7', fg: '#92400E' },
  in_stock_reserved: { bg: '#DCFCE7', fg: '#15803D' },
  reserved_for_sale: { bg: '#E0F2FE', fg: '#0369A1' },
  sale_in_progress:  { bg: '#FEF9C3', fg: '#854D0E' },
  fully_paid:        { bg: '#DCFCE7', fg: '#15803D' },
}

const RESERVED_STATUSES = new Set(['incoming_reserved', 'in_stock_reserved'])

const ALL_MODELS = [
  'Dominar 250', 'Dominar 400 UG', 'Pulsar N125 Car',
  'Pulsar N125 FI CBS', 'Pulsar N160', 'Pulsar N160 Premium',
  'Pulsar N250 FI ABS', 'Pulsar NS200', 'Pulsar NS400Z', 'Pulsar RS200',
]

const EST_OPTIONS = [
  'Todos', 'Comprada', 'En camino', 'En stock', 'No comprada',
  'Rechazada', 'Vendida', 'Cancelada', 'En camino (Reservada)', 'En stock (Reservada)',
  'Congelada', 'Venta Iniciada', 'Pago Completo',
]

function Badge({ status }) {
  const { bg, fg } = STATUS_BADGE[status] ?? { bg: '#F1F5F9', fg: '#64748B' }
  const label = RESERVED_STATUSES.has(status)
    ? `⭐ ${STATUS_ES[status] ?? status}`
    : (STATUS_ES[status] ?? status ?? '—')
  return (
    <span style={{
      background: bg, color: fg,
      fontSize: '0.67rem', fontWeight: 600,
      padding: '0.18rem 0.55rem', borderRadius: '20px',
      whiteSpace: 'nowrap', letterSpacing: '0.02em',
      display: 'inline-block',
    }}>
      {label}
    </span>
  )
}

function v(val) {
  return (val == null || val === '' || val === 'None' || val === 'null') ? '—' : String(val)
}

export default function Dashboard() {
  const [allData, setAllData]         = useState(null)
  const [dealerships, setDealerships] = useState([])
  const [error, setError]             = useState(null)
  const [searched, setSearched]       = useState(false)
  const [page, setPage]               = useState(0)

  const [filterEstado,   setFilterEstado]   = useState('Todos')
  const [filterModelo,   setFilterModelo]   = useState('Todos')
  const [filterSucursal, setFilterSucursal] = useState('Todas')

  useEffect(() => {
    api.get('/motorcycles/')
      .then(r => setAllData(r.data))
      .catch(() => setError('No se puede conectar al servidor.'))
    api.get('/delivery-confirmations/dealerships')
      .then(r => setDealerships(r.data))
      .catch(() => {})
  }, [])

  const ES_TO_RAW = Object.fromEntries(Object.entries(STATUS_ES).map(([k, v]) => [v, k]))

  let filtered = allData ?? []
  if (searched) {
    if (filterEstado !== 'Todos') {
      const raw = ES_TO_RAW[filterEstado]
      if (raw) filtered = filtered.filter(m => m.status === raw)
    }
    if (filterModelo !== 'Todos') {
      filtered = filtered.filter(m => m.model === filterModelo)
    }
    if (filterSucursal !== 'Todas') {
      filtered = filtered.filter(m => m.dealership === filterSucursal)
    }
  }

  const total      = filtered.length
  const totalPages = Math.max(1, Math.ceil(total / ROWS_PER_PAGE))
  const safePage   = Math.min(page, totalPages - 1)
  const start      = safePage * ROWS_PER_PAGE
  const end        = Math.min(start + ROWS_PER_PAGE, total)
  const pageRows   = filtered.slice(start, end)

  function handleBuscar() {
    setPage(0)
    setSearched(true)
  }

  function handleFilterChange() {
    setPage(0)
    setSearched(true)
  }

  return (
    <>
      <PageHeader section="Inicio" title="Panel Principal" />

      {error && <div className="alert-error">{error}</div>}

      {/* Filter bar */}
      <div className="filter-bar">
        <div>
          <div className="card-section">Estado</div>
          <select
            value={filterEstado}
            onChange={e => { setFilterEstado(e.target.value); handleFilterChange() }}
          >
            {EST_OPTIONS.map(o => <option key={o}>{o}</option>)}
          </select>
        </div>
        <div>
          <div className="card-section">Modelo</div>
          <select
            value={filterModelo}
            onChange={e => { setFilterModelo(e.target.value); handleFilterChange() }}
          >
            {['Todos', ...ALL_MODELS].map(o => <option key={o}>{o}</option>)}
          </select>
        </div>
        <div>
          <div className="card-section">Sucursal</div>
          <select
            value={filterSucursal}
            onChange={e => { setFilterSucursal(e.target.value); handleFilterChange() }}
          >
            {['Todas', ...dealerships.map(d => d.name)].map(o => <option key={o}>{o}</option>)}
          </select>
        </div>
        <div style={{ display: 'flex', alignItems: 'flex-end' }}>
          <button className="btn-primary" style={{ width: '100%' }} onClick={handleBuscar}>
            Buscar
          </button>
        </div>
      </div>

      {!searched && (
        <div className="inventory-placeholder">
          <div className="inventory-placeholder-label">Inventario de Motocicletas</div>
          <div className="inventory-placeholder-sub">Selecciona filtros y presiona Buscar</div>
        </div>
      )}

      {searched && total === 0 && (
        <div
          className="count-tag"
          style={{ background: '#FEF2F2', color: '#DC2626' }}
        >
          Sin resultados para los filtros seleccionados
        </div>
      )}

      {searched && total > 0 && (
        <>
          <div className="count-tag">
            Mostrando {start + 1}–{end} de {total} motocicleta(s)
          </div>

          <div className="inventory-table-wrapper">
            <table className="inventory-table">
              <thead>
                <tr>
                  {['Modelo', 'Año', 'Color', 'Estado', 'Sucursal', 'No. Serie', 'No. Motor'].map(h => (
                    <th key={h}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {pageRows.map((m, i) => (
                  <tr key={i}>
                    <td>{v(m.model)}</td>
                    <td>{v(m.year)}</td>
                    <td>{v(m.color)}</td>
                    <td><Badge status={m.status} /></td>
                    <td>{v(m.dealership)}</td>
                    <td className="mono">{v(m.serie)}</td>
                    <td className="mono">{v(m.motor)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {totalPages > 1 && (
            <div className="pagination">
              <button
                className="btn-secondary"
                disabled={safePage === 0}
                onClick={() => setPage(p => p - 1)}
              >
                ← Anterior
              </button>
              <span className="pagination-info">
                Página {safePage + 1} de {totalPages}
              </span>
              <button
                className="btn-secondary"
                disabled={safePage >= totalPages - 1}
                onClick={() => setPage(p => p + 1)}
              >
                Siguiente →
              </button>
            </div>
          )}
        </>
      )}
    </>
  )
}
