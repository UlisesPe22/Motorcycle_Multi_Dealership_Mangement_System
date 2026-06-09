import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../api'
import { fmt } from '../utils'

// ─── Palette ────────────────────────────────────────────────────────────────
const BLUE   = '#1A73E8'
const GREEN  = '#1E8E3E'
const ORANGE = '#E37400'
const GREY   = '#5F6368'
const LIGHT  = '#F8F9FA'
const BORDER = '#E0E0E0'

// ─── Skeleton block ──────────────────────────────────────────────────────────
function Skeleton({ width = '100%', height = 16, style = {} }) {
  return (
    <div
      style={{
        width,
        height,
        borderRadius: 4,
        background: 'linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%)',
        backgroundSize: '200% 100%',
        animation: 'shimmer 1.4s infinite',
        ...style,
      }}
    />
  )
}

// ─── Progress bar ────────────────────────────────────────────────────────────
function ProgressBar({ verified, total }) {
  const pct   = total === 0 ? 0 : Math.round((verified / total) * 100)
  const color = verified === 0 ? GREY : verified < total ? ORANGE : GREEN

  return (
    <div>
      <span style={{ fontSize: 13, fontWeight: 600, color }}>
        {verified}/{total}
      </span>
      <div style={{
        marginTop: 4,
        height: 4,
        borderRadius: 2,
        background: BORDER,
        overflow: 'hidden',
      }}>
        <div style={{
          width: `${pct}%`,
          height: '100%',
          background: color,
          borderRadius: 2,
          transition: 'width 0.3s',
        }} />
      </div>
    </div>
  )
}

// ─── Main component ──────────────────────────────────────────────────────────
export default function VendorSales() {
  const navigate = useNavigate()
  const [summary, setSummary]   = useState(null)
  const [sales, setSales]       = useState([])
  const [search, setSearch]     = useState('')
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState(null)

  const fetchAll = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [sumRes, activeRes] = await Promise.all([
        api.get('/vendor-sales/summary'),
        api.get('/vendor-sales/active'),
      ])
      setSummary(sumRes.data)
      setSales(activeRes.data)
    } catch {
      setError('Error al cargar ventas. Intenta de nuevo.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchAll() }, [fetchAll])

  // Client-side search filter
  const filtered = search.trim()
    ? sales.filter(s => {
        const q = search.toLowerCase()
        return (
          s.client_name.toLowerCase().includes(q) ||
          s.model_name.toLowerCase().includes(q)
        )
      })
    : sales

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <>
      {/* shimmer keyframe */}
      <style>{`
        @keyframes shimmer {
          0%   { background-position: 200% 0; }
          100% { background-position: -200% 0; }
        }
        .vs-table { width: 100%; border-collapse: collapse; }
        .vs-table th {
          text-align: left;
          font-size: 12px;
          font-weight: 600;
          color: ${GREY};
          text-transform: uppercase;
          letter-spacing: 0.05em;
          padding: 10px 16px;
          border-bottom: 2px solid ${BORDER};
          white-space: nowrap;
        }
        .vs-table td {
          padding: 14px 16px;
          border-bottom: 1px solid ${BORDER};
          font-size: 14px;
          color: #202124;
          vertical-align: middle;
        }
        .vs-table tr:last-child td { border-bottom: none; }
        .vs-table tr:hover td { background: ${LIGHT}; }
        .btn-contract-off {
          padding: 6px 14px;
          border-radius: 4px;
          font-size: 13px;
          font-weight: 500;
          border: 1px solid ${BORDER};
          background: ${LIGHT};
          color: #BDBDBD;
          cursor: not-allowed;
          white-space: nowrap;
        }
        .btn-contract-on {
          padding: 6px 14px;
          border-radius: 4px;
          font-size: 13px;
          font-weight: 500;
          border: none;
          background: ${BLUE};
          color: #fff;
          cursor: pointer;
          white-space: nowrap;
          transition: opacity 0.15s;
        }
        .btn-contract-on:hover { opacity: 0.88; }
        @media (max-width: 640px) {
          .col-pagos { display: none; }
        }
      `}</style>

      <div style={{ padding: '24px 28px', maxWidth: 1100, margin: '0 auto' }}>

        {/* ── Header card ──────────────────────────────────────────────────── */}
        <div style={{
          background: '#fff',
          borderRadius: 8,
          boxShadow: '0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.08)',
          padding: '20px 24px',
          marginBottom: 24,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
            <span style={{ fontSize: 22 }}>👤</span>
            <span style={{ fontSize: 18, fontWeight: 700, color: '#202124' }}>
              {loading || !summary ? <Skeleton width={120} height={20} /> : summary.vendor_name}
            </span>
            <span style={{ marginLeft: 'auto', fontSize: 18, fontWeight: 600, color: GREY }}>
              Mis Ventas
            </span>
          </div>

          <div style={{ borderBottom: `1px solid ${BORDER}`, margin: '14px 0' }} />

          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
            {/* KPI: Ventas Activas */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              background: '#E8F0FE',
              border: `1px solid #C5D8FB`,
              borderRadius: 20,
              padding: '6px 16px',
            }}>
              {loading || !summary ? (
                <Skeleton width={80} height={16} />
              ) : (
                <>
                  <span style={{ fontSize: 16, fontWeight: 700, color: BLUE }}>
                    {summary.sales_in_progress}
                  </span>
                  <span style={{ fontSize: 13, color: BLUE }}>Ventas Activas</span>
                </>
              )}
            </div>

            {/* KPI: Completadas este mes */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              background: '#E6F4EA',
              border: `1px solid #CEEAD6`,
              borderRadius: 20,
              padding: '6px 16px',
            }}>
              {loading || !summary ? (
                <Skeleton width={110} height={16} />
              ) : (
                <>
                  <span style={{ fontSize: 16, fontWeight: 700, color: GREEN }}>
                    {summary.completed_this_month}
                  </span>
                  <span style={{ fontSize: 13, color: GREEN }}>Completadas este mes</span>
                </>
              )}
            </div>
          </div>
        </div>

        {/* ── Search bar ───────────────────────────────────────────────────── */}
        <div style={{
          background: '#fff',
          borderRadius: 8,
          boxShadow: '0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.08)',
          padding: '12px 16px',
          marginBottom: 20,
          display: 'flex',
          alignItems: 'center',
          gap: 10,
        }}>
          <span style={{ fontSize: 16, color: GREY }}>🔍</span>
          <input
            type="text"
            placeholder="Buscar por cliente o modelo..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            style={{
              flex: 1,
              border: 'none',
              outline: 'none',
              fontSize: 14,
              color: '#202124',
              background: 'transparent',
            }}
          />
          {search && (
            <button
              onClick={() => setSearch('')}
              style={{
                border: 'none',
                background: 'none',
                cursor: 'pointer',
                color: GREY,
                fontSize: 16,
                lineHeight: 1,
              }}
            >
              ✕
            </button>
          )}
        </div>

        {/* ── Table card ───────────────────────────────────────────────────── */}
        <div style={{
          background: '#fff',
          borderRadius: 8,
          boxShadow: '0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.08)',
          overflowX: 'auto',
        }}>

          {/* Error state */}
          {error && (
            <div style={{ padding: 40, textAlign: 'center' }}>
              <p style={{ color: '#C62828', marginBottom: 16 }}>{error}</p>
              <button
                onClick={fetchAll}
                style={{
                  padding: '8px 20px',
                  background: BLUE,
                  color: '#fff',
                  border: 'none',
                  borderRadius: 4,
                  cursor: 'pointer',
                  fontSize: 14,
                }}
              >
                Reintentar
              </button>
            </div>
          )}

          {/* Loading skeleton rows */}
          {!error && loading && (
            <table className="vs-table">
              <thead>
                <TableHead />
              </thead>
              <tbody>
                {[1, 2, 3].map(i => (
                  <tr key={i}>
                    <td><Skeleton height={14} width="80%" /></td>
                    <td><Skeleton height={14} width="70%" /></td>
                    <td className="col-pagos"><Skeleton height={14} width="60%" /></td>
                    <td><Skeleton height={14} width="50%" /></td>
                    <td><Skeleton height={14} width="90%" /></td>
                    <td><Skeleton height={28} width={130} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {/* Empty state */}
          {!error && !loading && filtered.length === 0 && (
            <div style={{ padding: '60px 24px', textAlign: 'center' }}>
              <div style={{ fontSize: 48, marginBottom: 16 }}>📋</div>
              <p style={{ color: GREY, fontSize: 15 }}>
                {search
                  ? 'No se encontraron resultados para tu búsqueda.'
                  : 'No tienes ventas activas en este momento.'}
              </p>
            </div>
          )}

          {/* Data table */}
          {!error && !loading && filtered.length > 0 && (
            <table className="vs-table">
              <thead>
                <TableHead />
              </thead>
              <tbody>
                {filtered.map(sale => (
                  <SaleRow
                    key={sale.sale_id}
                    sale={sale}
                    onContract={() => navigate(`/crear-contrato/${sale.sale_id}`)}
                  />
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </>
  )
}

function TableHead() {
  return (
    <tr>
      <th>Modelo</th>
      <th>Cliente</th>
      <th className="col-pagos">Pagos</th>
      <th>Verificados</th>
      <th>Monto</th>
      <th>Contrato</th>
    </tr>
  )
}

function SaleRow({ sale, onContract }) {
  return (
    <tr>
      {/* Modelo */}
      <td>
        <div style={{ fontWeight: 500 }}>
          {sale.model_name} {sale.year}
        </div>
        <div style={{ fontSize: 12, color: GREY, marginTop: 2 }}>
          {sale.color}
        </div>
      </td>

      {/* Cliente */}
      <td style={{ fontWeight: 400 }}>{sale.client_name}</td>

      {/* Pagos (hidden on mobile) */}
      <td className="col-pagos" style={{ color: GREY }}>
        {sale.payment_types}
      </td>

      {/* Verificados */}
      <td style={{ minWidth: 100 }}>
        <ProgressBar verified={sale.verified_count} total={sale.total_count} />
      </td>

      {/* Monto */}
      <td>
        <div style={{ fontSize: '0.88rem', fontWeight: 600 }}>
          ${fmt(sale.amount_verified)} / ${fmt(sale.total_price)}
        </div>
        <div style={{ fontSize: '0.75rem', color: '#64748B' }}>verificado / total</div>
      </td>

      {/* Contrato */}
      <td>
        {sale.contract_unlocked ? (
          <button className="btn-contract-on" onClick={onContract}>
            Generar Contrato
          </button>
        ) : (
          <button className="btn-contract-off" disabled>
            Generar Contrato
          </button>
        )}
      </td>
    </tr>
  )
}
