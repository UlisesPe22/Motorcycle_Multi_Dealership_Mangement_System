import { useState, useEffect, useCallback } from 'react'
import api from '../api'
import VendorHeaderCard from '../components/VendorHeaderCard'
import DateFilter from '../components/DateFilter'
import { BLUE, GREY, LIGHT, BORDER } from '../constants'

// ─── Date helpers ────────────────────────────────────────────────────────────
const fmtISO = (d) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`

function firstOfMonth() {
  const n = new Date()
  return fmtISO(new Date(n.getFullYear(), n.getMonth(), 1))
}

function today() {
  return fmtISO(new Date())
}

// ─── Skeleton block (table rows) ─────────────────────────────────────────────
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

// ─── Main component ──────────────────────────────────────────────────────────
export default function Comisiones() {
  const [summary, setSummary]   = useState(null)
  const [rows, setRows]         = useState([])
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState(null)
  const [dateFrom, setDateFrom] = useState(firstOfMonth)
  const [dateTo, setDateTo]     = useState(today)

  const fetchAll = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [sumRes, completedRes] = await Promise.all([
        api.get('/vendor-sales/summary'),
        api.get('/vendor-sales/completed', {
          params: { date_from: dateFrom, date_to: dateTo },
        }),
      ])
      setSummary(sumRes.data)
      setRows(completedRes.data)
    } catch {
      setError('Error al cargar. Intenta de nuevo.')
    } finally {
      setLoading(false)
    }
  }, [dateFrom, dateTo])

  // Fetch once on mount with the default range; afterwards only on "Aplicar".
  useEffect(() => { fetchAll() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <>
      {/* shimmer keyframe */}
      <style>{`
        @keyframes shimmer {
          0%   { background-position: 200% 0; }
          100% { background-position: -200% 0; }
        }
        .cm-table { width: 100%; border-collapse: collapse; }
        .cm-table th {
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
        .cm-table td {
          padding: 14px 16px;
          border-bottom: 1px solid ${BORDER};
          font-size: 14px;
          color: #202124;
          vertical-align: middle;
        }
        .cm-table tr:last-child td { border-bottom: none; }
        .cm-table tr:hover td { background: ${LIGHT}; }
      `}</style>

      <div style={{ padding: '24px 28px', maxWidth: 1100, margin: '0 auto' }}>

        {/* ── Header card ──────────────────────────────────────────────────── */}
        <VendorHeaderCard
          summary={summary}
          loading={loading}
          title="Comisiones"
          showKpis={true}
        />

        {/* ── Date filter ──────────────────────────────────────────────────── */}
        <DateFilter
          dateFrom={dateFrom}
          dateTo={dateTo}
          onDateFromChange={setDateFrom}
          onDateToChange={setDateTo}
          onApply={fetchAll}
          loading={loading}
        />

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
            <table className="cm-table">
              <thead>
                <TableHead />
              </thead>
              <tbody>
                {[1, 2, 3].map(i => (
                  <tr key={i}>
                    <td><Skeleton height={14} width="80%" /></td>
                    <td><Skeleton height={14} width="70%" /></td>
                    <td><Skeleton height={14} width="50%" /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {/* Empty state */}
          {!error && !loading && rows.length === 0 && (
            <div style={{ padding: '60px 24px', textAlign: 'center' }}>
              <div style={{ fontSize: 48, marginBottom: 16 }}>📋</div>
              <p style={{ color: GREY, fontSize: 15 }}>
                No tienes ventas completadas aún.
              </p>
            </div>
          )}

          {/* Data table */}
          {!error && !loading && rows.length > 0 && (
            <table className="cm-table">
              <thead>
                <TableHead />
              </thead>
              <tbody>
                {rows.map(row => (
                  <tr key={row.sale_id}>
                    <td>
                      <div style={{ fontWeight: 500 }}>
                        {row.model_name} {row.year}
                      </div>
                    </td>
                    <td style={{ fontWeight: 400 }}>{row.client_name}</td>
                    <td>{row.contract_date || '—'}</td>
                  </tr>
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
      <th>Fecha Contrato</th>
    </tr>
  )
}
