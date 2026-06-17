import { useState, useEffect, useCallback } from 'react'
import api from '../../api'
import DateFilter from '../../components/DateFilter'
import { BLUE, GREEN, ORANGE, GREY, LIGHT, BORDER, RED } from '../../constants'

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

function fmtDateTime(iso) {
  const d = new Date(iso)
  if (isNaN(d)) return '—'
  const pad = (x) => String(x).padStart(2, '0')
  return `${pad(d.getDate())}/${pad(d.getMonth() + 1)}/${d.getFullYear()} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

// ─── CSS bar chart ───────────────────────────────────────────────────────────
function BarChart({ data, isMobile }) {
  const max = Math.max(1, ...data.map((d) => d.value))
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
        width: isMobile ? '100%' : 320,
      }}
    >
      {data.map((d) => (
        <div key={d.label} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 140, fontSize: 12, color: GREY, flexShrink: 0 }}>{d.label}</div>
          <div style={{ flex: 1, background: BORDER, borderRadius: 4, height: 18, overflow: 'hidden' }}>
            <div
              style={{
                width: `${(d.value / max) * 100}%`,
                height: '100%',
                background: d.color,
                borderRadius: 4,
                transition: 'width 0.3s',
              }}
            />
          </div>
          <div style={{ width: 28, textAlign: 'right', fontSize: 13, fontWeight: 700, color: d.color }}>
            {d.value}
          </div>
        </div>
      ))}
    </div>
  )
}

// ─── Type badge (cancelled table) ───────────────────────────────────────────
function TypeBadge({ motorcycleId }) {
  const isReservation = motorcycleId == null
  return (
    <span style={{
      background:   isReservation ? 'rgba(26, 115, 232, 0.15)' : 'rgba(217, 48, 37, 0.15)',
      color:        isReservation ? BLUE : RED,
      borderRadius: 4,
      padding:      '2px 8px',
      fontSize:     12,
      fontWeight:   500,
    }}>
      {isReservation ? 'Reserva' : 'Venta Cancelada'}
    </span>
  )
}

// ─── Main component ──────────────────────────────────────────────────────────
export default function OwnerDashboard() {
  const [dealerships, setDealerships]               = useState([])
  const [selectedDealership, setSelectedDealership] = useState(3)
  const [dateFrom, setDateFrom]                     = useState(firstOfMonth)
  const [dateTo, setDateTo]                         = useState(today)
  const [summary, setSummary]                       = useState(null)
  const [cancelled, setCancelled]                   = useState([])
  const [vendors, setVendors]                       = useState([])
  const [loading, setLoading]                       = useState(true)
  const [error, setError]                           = useState(null)
  const [isMobile, setIsMobile]                     = useState(window.innerWidth < 768)

  // Track viewport for responsive chart placement
  useEffect(() => {
    const onResize = () => setIsMobile(window.innerWidth < 768)
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  // Dealership list (one-time)
  useEffect(() => {
    api.get('/reservations/dealerships')
      .then((res) => setDealerships(res.data))
      .catch(() => {})
  }, [])

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    const params = { dealership_id: selectedDealership, date_from: dateFrom, date_to: dateTo }
    try {
      const [sumRes, cancRes, vendRes] = await Promise.all([
        api.get('/owner-dashboard/summary',   { params }),
        api.get('/owner-dashboard/cancelled', { params }),
        api.get('/owner-dashboard/vendors',   { params }),
      ])
      setSummary(sumRes.data)
      setCancelled(cancRes.data)
      setVendors(vendRes.data)
    } catch {
      setError('Error al cargar datos. Intenta de nuevo.')
    } finally {
      setLoading(false)
    }
  }, [selectedDealership, dateFrom, dateTo])

  // Auto-fetch on mount with defaults
  useEffect(() => { fetchData() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const chartData = [
    { label: 'Motos Vendidas',      value: summary?.sold ?? 0,        color: GREEN },
    { label: 'En Stock Reservadas', value: summary?.reserved ?? 0,    color: ORANGE },
    { label: 'Venta en Progreso',   value: summary?.in_progress ?? 0, color: BLUE },
  ]

  return (
    <div style={{ padding: '24px 28px', maxWidth: 1100, margin: '0 auto' }}>
      <style>{`
        .od-table { width: 100%; border-collapse: collapse; }
        .od-table th {
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
        .od-table td {
          padding: 12px 16px;
          border-bottom: 1px solid ${BORDER};
          font-size: 14px;
          color: #202124;
        }
        .od-table tr:last-child td { border-bottom: none; }
        .od-table tbody tr:hover td { background: #F1F3F4; }
        .od-num { text-align: center; }
      `}</style>

      {/* ── Header: title + chart ──────────────────────────────────────────── */}
      <div
        style={{
          background: '#fff',
          borderRadius: 8,
          boxShadow: '0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.08)',
          padding: '20px 24px',
          marginBottom: 20,
          display: 'flex',
          flexDirection: isMobile ? 'column' : 'row',
          alignItems: isMobile ? 'stretch' : 'center',
          justifyContent: 'space-between',
          gap: 20,
        }}
      >
        <div>
          <div style={{ fontSize: 20, fontWeight: 700, color: '#202124' }}>Panel Principal</div>
          <div style={{ fontSize: 13, color: GREY, marginTop: 4 }}>Resumen del periodo seleccionado</div>
        </div>
        {!isMobile && <BarChart data={chartData} isMobile={false} />}
      </div>

      {/* ── Filter bar ─────────────────────────────────────────────────────── */}
      <DateFilter
        dateFrom={dateFrom}
        dateTo={dateTo}
        onDateFromChange={setDateFrom}
        onDateToChange={setDateTo}
        onApply={fetchData}
        loading={loading}
      >
        <Field label="Sucursal">
          <select
            value={selectedDealership}
            onChange={(e) => setSelectedDealership(Number(e.target.value))}
            style={inputStyle}
          >
            {dealerships.length === 0 && <option value={3}>BAJAJ TLALPIZAHUAC</option>}
            {dealerships.map((d) => (
              <option key={d.dealership_id} value={d.dealership_id}>{d.name}</option>
            ))}
          </select>
        </Field>
      </DateFilter>

      {/* ── Error banner ───────────────────────────────────────────────────── */}
      {error && (
        <div
          style={{
            background: '#FDECEA',
            border: `1px solid #F5C6C2`,
            color: RED,
            borderRadius: 6,
            padding: '12px 16px',
            marginBottom: 16,
            fontSize: 14,
          }}
        >
          {error}
        </div>
      )}

      {/* ── Mobile chart (below filters) ───────────────────────────────────── */}
      {isMobile && (
        <div
          style={{
            background: '#fff',
            borderRadius: 8,
            boxShadow: '0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.08)',
            padding: '18px 16px',
            marginBottom: 20,
          }}
        >
          <BarChart data={chartData} isMobile={true} />
        </div>
      )}

      {loading ? (
        <div style={{ padding: 60, textAlign: 'center', color: GREY, fontSize: 15 }}>Cargando…</div>
      ) : (
        <>
          {/* ── Cancelled sales ──────────────────────────────────────────── */}
          <SectionCard title="Cancelaciones">
            <div className="table-scroll-wrapper" style={{ overflowX: 'auto' }}>
              <table className="od-table" style={{ minWidth: 520 }}>
                <thead>
                  <tr>
                    <th>Vendedor</th>
                    <th>Tipo</th>
                    <th>Fecha Cancelación</th>
                    <th>Motivo</th>
                  </tr>
                </thead>
                <tbody>
                  {cancelled.length === 0 ? (
                    <tr>
                      <td colSpan={4} style={{ textAlign: 'center', color: GREY, padding: 40 }}>
                        Sin cancelaciones en este periodo
                      </td>
                    </tr>
                  ) : (
                    cancelled.map((c, i) => (
                      <tr key={`${c.sale_id}-${i}`}>
                        <td>{c.vendor_name}</td>
                        <td><TypeBadge motorcycleId={c.motorcycle_id} /></td>
                        <td>{fmtDateTime(c.cancelled_at)}</td>
                        <td>{c.reason}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </SectionCard>

          {/* ── Vendors ──────────────────────────────────────────────────── */}
          <SectionCard title="Vendedores">
            <div className="table-scroll-wrapper" style={{ overflowX: 'auto' }}>
              <table className="od-table" style={{ minWidth: 480 }}>
                <thead>
                  <tr>
                    <th>Vendedor</th>
                    <th className="od-num">Vendidas</th>
                    <th className="od-num">Reservaciones</th>
                    <th className="od-num">Cancelaciones</th>
                    <th className="od-num">Ventas En Progreso</th>
                  </tr>
                </thead>
                <tbody>
                  {vendors.length === 0 ? (
                    <tr>
                      <td colSpan={5} style={{ textAlign: 'center', color: GREY, padding: 40 }}>
                        Sin vendedores registrados
                      </td>
                    </tr>
                  ) : (
                    <>
                      {vendors.map((v) => (
                        <tr key={v.vendor_id}>
                          <td>{v.vendor_name}</td>
                          <td className="od-num" style={{ color: GREEN, fontWeight: 700 }}>{v.sold}</td>
                          <td className="od-num">{v.reservations}</td>
                          <td
                            className="od-num"
                            style={{ color: v.cancelled > 0 ? RED : GREY, fontWeight: v.cancelled > 0 ? 700 : 400 }}
                          >
                            {v.cancelled}
                          </td>
                          <td className="od-num">{v.in_progress}</td>
                        </tr>
                      ))}
                      <VendorTotalsRow vendors={vendors} />
                    </>
                  )}
                </tbody>
              </table>
            </div>
          </SectionCard>
        </>
      )}
    </div>
  )
}

// ─── Small layout helpers ────────────────────────────────────────────────────
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

function SectionCard({ title, children }) {
  return (
    <div
      style={{
        background: '#fff',
        borderRadius: 8,
        boxShadow: '0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.08)',
        marginBottom: 20,
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          padding: '14px 20px',
          borderBottom: `1px solid ${BORDER}`,
          fontSize: 15,
          fontWeight: 700,
          color: '#202124',
        }}
      >
        {title}
      </div>
      {children}
    </div>
  )
}

function VendorTotalsRow({ vendors }) {
  const t = vendors.reduce(
    (acc, v) => ({
      sold:         acc.sold         + v.sold,
      reservations: acc.reservations + v.reservations,
      cancelled:    acc.cancelled    + v.cancelled,
      in_progress:  acc.in_progress  + v.in_progress,
    }),
    { sold: 0, reservations: 0, cancelled: 0, in_progress: 0 }
  )
  const cell = { borderTop: `2px solid ${BORDER}`, fontWeight: 700 }
  return (
    <tr style={{ background: LIGHT }}>
      <td style={{ ...cell, color: GREY }}>Total</td>
      <td className="od-num" style={{ ...cell, color: GREEN }}>{t.sold}</td>
      <td className="od-num" style={cell}>{t.reservations}</td>
      <td className="od-num" style={{ ...cell, color: t.cancelled > 0 ? RED : GREY }}>{t.cancelled}</td>
      <td className="od-num" style={cell}>{t.in_progress}</td>
    </tr>
  )
}
