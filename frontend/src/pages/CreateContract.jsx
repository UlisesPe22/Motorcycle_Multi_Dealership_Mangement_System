import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import api from '../api'
import { fmt } from '../utils'
import { BLUE, GREEN, GREY, BORDER, LIGHT } from '../constants'

// ─── Helpers ─────────────────────────────────────────────────────────────────
async function downloadDoc(url, filename) {
  const res = await api.get(url, { responseType: 'blob' })
  const href = URL.createObjectURL(new Blob([res.data]))
  const a = document.createElement('a')
  a.href = href
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(href)
}

function Field({ label, value }) {
  return (
    <div style={{ marginBottom: 10 }}>
      <span style={{ fontSize: 12, color: GREY, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
        {label}
      </span>
      <div style={{ fontSize: 14, color: '#202124', marginTop: 2 }}>{value || '—'}</div>
    </div>
  )
}

function Input({ label, value, onChange, required = false, placeholder = '' }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <label style={{ display: 'block', fontSize: 13, fontWeight: 600, color: '#202124', marginBottom: 4 }}>
        {label}{required && <span style={{ color: '#C62828' }}> *</span>}
      </label>
      <input
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        required={required}
        style={{
          width: '100%',
          padding: '8px 12px',
          border: `1px solid ${BORDER}`,
          borderRadius: 4,
          fontSize: 14,
          color: '#202124',
          outline: 'none',
          boxSizing: 'border-box',
        }}
      />
    </div>
  )
}

function Card({ children, style = {} }) {
  return (
    <div style={{
      background: '#fff',
      borderRadius: 8,
      boxShadow: '0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.08)',
      padding: '20px 24px',
      marginBottom: 20,
      ...style,
    }}>
      {children}
    </div>
  )
}

function SectionTitle({ children }) {
  return (
    <div style={{ fontSize: 15, fontWeight: 700, color: '#202124', marginBottom: 16, paddingBottom: 8, borderBottom: `1px solid ${BORDER}` }}>
      {children}
    </div>
  )
}

// ─── Main component ──────────────────────────────────────────────────────────
export default function CreateContract() {
  const { sale_id } = useParams()
  const navigate    = useNavigate()

  const [loadingData, setLoadingData] = useState(true)
  const [loadError,   setLoadError]   = useState(null)
  const [data,        setData]        = useState(null)

  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState(null)
  const [result, setResult] = useState(null)   // success response

  // Form fields
  const [paymentBank,      setPaymentBank]      = useState('')
  const [referenceName,    setReferenceName]    = useState('')
  const [referencePhone,   setReferencePhone]   = useState('')
  const [referenceRelation, setReferenceRelation] = useState('')
  const [buyerColonia,     setBuyerColonia]     = useState('')
  const [buyerCp,          setBuyerCp]          = useState('')
  const [buyerMunicipio,   setBuyerMunicipio]   = useState('')
  const [buyerEstado,      setBuyerEstado]      = useState('')

  // Auto-navigate after success
  useEffect(() => {
    if (!result) return
    const t = setTimeout(() => navigate('/mis-ventas'), 3000)
    return () => clearTimeout(t)
  }, [result, navigate])

  // Fetch pre-populated data on mount
  useEffect(() => {
    api.get(`/sales/contract-data/${sale_id}`)
      .then(r => setData(r.data))
      .catch(() => setLoadError('No se pudo cargar la información de la venta.'))
      .finally(() => setLoadingData(false))
  }, [sale_id])

  async function handleSubmit(e) {
    e.preventDefault()
    setSubmitting(true)
    setSubmitError(null)
    try {
      const res = await api.post('/sales/generate-contract', {
        sale_id:            parseInt(sale_id, 10),
        payment_method:     'transferencia',
        payment_bank:       paymentBank     || null,
        reference_name:     referenceName   || null,
        reference_phone:    referencePhone  || null,
        reference_relation: referenceRelation || null,
        buyer_colonia:      buyerColonia    || null,
        buyer_cp:           buyerCp         || null,
        buyer_municipio:    buyerMunicipio  || null,
        buyer_estado:       buyerEstado     || null,
      })
      if (res.data.success) {
        setResult(res.data)
      } else {
        setSubmitError(res.data.message || 'Error al generar contrato.')
      }
    } catch (err) {
      setSubmitError(err?.response?.data?.detail || 'Error al generar contrato.')
    } finally {
      setSubmitting(false)
    }
  }

  // ── Loading state ───────────────────────────────────────────────────────────
  if (loadingData) {
    return (
      <div style={{ padding: '40px 28px', textAlign: 'center', color: GREY }}>
        Cargando datos de la venta…
      </div>
    )
  }

  if (loadError) {
    return (
      <div style={{ padding: '40px 28px', textAlign: 'center' }}>
        <p style={{ color: '#C62828', marginBottom: 16 }}>{loadError}</p>
        <button
          onClick={() => navigate('/mis-ventas')}
          style={{ padding: '8px 20px', background: BLUE, color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer', fontSize: 14 }}
        >
          Volver a Mis Ventas
        </button>
      </div>
    )
  }

  const isCredito = data?.sale_type === 'credito'

  // ── Success state ───────────────────────────────────────────────────────────
  if (result) {
    return (
      <div style={{ padding: '24px 28px', maxWidth: 680, margin: '0 auto' }}>
        <Card>
          <div style={{ textAlign: 'center', padding: '12px 0' }}>
            <div style={{ fontSize: 48, marginBottom: 12 }}>✅</div>
            <div style={{ fontSize: 18, fontWeight: 700, color: GREEN, marginBottom: 6 }}>
              Contrato generado exitosamente
            </div>
            <div style={{ fontSize: 14, color: GREY, marginBottom: 24 }}>
              {result.contract_number} · Volviendo a Mis Ventas en 3 segundos…
            </div>
            <div style={{ display: 'flex', gap: 12, justifyContent: 'center', flexWrap: 'wrap' }}>
              <button
                onClick={() => downloadDoc(`/sales/${result.contract_id}/download/contrato`, `${result.contract_number}_contrato.docx`)}
                style={{ padding: '9px 20px', background: BLUE, color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer', fontSize: 14, fontWeight: 500 }}
              >
                Descargar Contrato
              </button>
              {result.has_solicitud && (
                <button
                  onClick={() => downloadDoc(`/sales/${result.contract_id}/download/solicitud`, `${result.contract_number}_solicitud.docx`)}
                  style={{ padding: '9px 20px', background: '#fff', color: BLUE, border: `1px solid ${BLUE}`, borderRadius: 4, cursor: 'pointer', fontSize: 14, fontWeight: 500 }}
                >
                  Descargar Solicitud
                </button>
              )}
              <button
                onClick={() => navigate('/mis-ventas')}
                style={{ padding: '9px 20px', background: LIGHT, color: GREY, border: `1px solid ${BORDER}`, borderRadius: 4, cursor: 'pointer', fontSize: 14 }}
              >
                Ir a Mis Ventas
              </button>
            </div>
          </div>
        </Card>
      </div>
    )
  }

  // ── Main form ───────────────────────────────────────────────────────────────
  return (
    <div style={{ padding: '24px 28px', maxWidth: 760, margin: '0 auto' }}>

      {/* Page title */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
        <button
          onClick={() => navigate('/mis-ventas')}
          style={{ background: 'none', border: 'none', cursor: 'pointer', color: GREY, fontSize: 20, padding: 0, lineHeight: 1 }}
          title="Volver"
        >
          ←
        </button>
        <h1 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: '#202124' }}>
          Generar Contrato
        </h1>
      </div>

      {/* ── Section 1: Read-only summary ──────────────────────────────────── */}
      <Card>
        <SectionTitle>Resumen de la Venta</SectionTitle>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '0 24px' }}>
          <Field label="Cliente"     value={data?.client?.nombre_completo} />
          <Field label="Sucursal"    value={data?.motorcycle?.dealership_name} />
          <Field label="Motocicleta" value={data?.motorcycle ? `${data.motorcycle.model_name} ${data.motorcycle.year} · ${data.motorcycle.color}` : null} />
          <Field label="Serie"       value={data?.motorcycle?.serie} />
          <Field label="Motor"       value={data?.motorcycle?.motor} />
          <Field label="Precio"      value={data ? `$${fmt(data.total_price)}` : null} />
          <Field
            label="Tipo de venta"
            value={isCredito ? 'Enganche / Crédito' : 'Al Contado'}
          />
          {isCredito && (
            <>
              <Field label="Financiera"        value={data?.payment_institution_name} />
              <Field label="Enganche declarado" value={data ? `$${fmt(data.payment_downpayment)}` : null} />
            </>
          )}
        </div>
      </Card>

      {/* ── Section 2: Vendor inputs ───────────────────────────────────────── */}
      <Card>
        <SectionTitle>Datos del Contrato</SectionTitle>
        <form onSubmit={handleSubmit}>

          {/* Credit-only fields */}
          {isCredito && (
            <>
              <div style={{ borderBottom: `1px solid ${BORDER}`, margin: '12px 0 16px', fontSize: 12, color: GREY, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                Datos de crédito
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '0 20px' }}>
                <Input label="Banco"                   value={paymentBank}       onChange={setPaymentBank}       required placeholder="Nombre del banco" />
                <Input label="Nombre del aval"         value={referenceName}     onChange={setReferenceName}     required placeholder="Nombre completo" />
                <Input label="Teléfono del aval"       value={referencePhone}    onChange={setReferencePhone}    required placeholder="55 0000 0000" />
                <Input label="Relación con el aval"    value={referenceRelation} onChange={setReferenceRelation} required placeholder="Familiar, amigo…" />
                <Input label="Colonia del comprador"   value={buyerColonia}      onChange={setBuyerColonia}      required placeholder="Colonia" />
                <Input label="Código Postal"           value={buyerCp}           onChange={setBuyerCp}           required placeholder="CP" />
                <Input label="Municipio del comprador" value={buyerMunicipio}    onChange={setBuyerMunicipio}    required placeholder="Municipio" />
                <Input label="Estado del comprador"    value={buyerEstado}       onChange={setBuyerEstado}       required placeholder="Estado" />
              </div>
            </>
          )}

          {submitError && (
            <div style={{ background: '#FFF3F3', border: '1px solid #FFCDD2', borderRadius: 4, padding: '10px 14px', marginBottom: 16, color: '#C62828', fontSize: 14 }}>
              {submitError}
            </div>
          )}

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12, marginTop: 8 }}>
            <button
              type="button"
              onClick={() => navigate('/mis-ventas')}
              style={{ padding: '9px 20px', background: LIGHT, color: GREY, border: `1px solid ${BORDER}`, borderRadius: 4, cursor: 'pointer', fontSize: 14 }}
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={submitting}
              style={{
                padding: '9px 24px',
                background: submitting ? '#A8C7F8' : BLUE,
                color: '#fff',
                border: 'none',
                borderRadius: 4,
                cursor: submitting ? 'not-allowed' : 'pointer',
                fontSize: 14,
                fontWeight: 600,
              }}
            >
              {submitting ? 'Generando…' : 'Generar Contrato'}
            </button>
          </div>
        </form>
      </Card>
    </div>
  )
}
