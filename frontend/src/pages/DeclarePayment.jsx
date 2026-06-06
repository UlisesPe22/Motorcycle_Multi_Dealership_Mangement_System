import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../api'
import PageHeader from '../components/PageHeader'

const LOCK_MINUTES = 15
const MAX_ITEMS    = 5
const MAX_COLORS   = 3

function fmt(n) {
  return Number(n).toLocaleString('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function fmtTime(secs) {
  const m = Math.floor(secs / 60)
  const s = secs % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

function StepIndicator({ step }) {
  const labels = ['Tipo de Pago', 'Datos', 'Pagos', 'Resumen']
  return (
    <div style={{ display: 'flex', gap: '0', marginBottom: '1.5rem', alignItems: 'center' }}>
      {labels.map((label, i) => {
        const num     = i + 1
        const active  = num === step
        const done    = num < step
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

function Toast({ toast, onClose }) {
  if (!toast) return null
  const bg = toast.type === 'success' ? '#DCFCE7' : '#FEE2E2'
  const fg = toast.type === 'success' ? '#15803D' : '#DC2626'
  return (
    <div style={{
      position: 'fixed', top: '1.5rem', right: '1.5rem', zIndex: 1000,
      background: bg, color: fg, border: `1px solid ${fg}`,
      borderRadius: '0.5rem', padding: '0.75rem 1.25rem',
      fontWeight: 600, fontSize: '0.9rem', boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
      maxWidth: '360px',
    }}>
      {toast.message}
      <button
        onClick={onClose}
        style={{ marginLeft: '1rem', background: 'none', border: 'none', cursor: 'pointer', color: fg, fontWeight: 700 }}
      >
        ×
      </button>
    </div>
  )
}

function LockExpiredModal({ onConfirm }) {
  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 2000,
    }}>
      <div style={{
        background: '#fff', borderRadius: '0.75rem', padding: '2rem',
        maxWidth: '400px', textAlign: 'center', boxShadow: '0 8px 32px rgba(0,0,0,0.25)',
      }}>
        <div style={{ fontSize: '2rem', marginBottom: '0.75rem' }}>⏱</div>
        <div style={{ fontWeight: 700, fontSize: '1.1rem', marginBottom: '0.5rem' }}>
          Tiempo de reserva expirado
        </div>
        <div style={{ color: '#64748B', marginBottom: '1.5rem' }}>
          El tiempo de reserva ha expirado. Por favor reinicia el proceso.
        </div>
        <button className="btn-primary" onClick={onConfirm}>
          Entendido
        </button>
      </div>
    </div>
  )
}

export default function DeclarePayment() {
  const navigate = useNavigate()

  // ── Step control ────────────────────────────────────────────────────────
  const [step, setStep] = useState(1)

  // ── Payment type ─────────────────────────────────────────────────────────
  const [paymentType, setPaymentType] = useState(null)

  // ── Catalog data ─────────────────────────────────────────────────────────
  const [dealerships,    setDealerships]    = useState([])
  const [clients,        setClients]        = useState([])
  const [models,         setModels]         = useState([])
  const [motorcycles,    setMotorcycles]    = useState([])
  const [paymentMethods, setPaymentMethods] = useState([])
  const [financieras,    setFinancieras]    = useState([])
  const [motosLoading,   setMotosLoading]   = useState(false)

  // ── Step 2 selections ────────────────────────────────────────────────────
  const [dealershipId,    setDealershipId]    = useState('')
  const [clientId,        setClientId]        = useState('')
  const [motorcycleId,    setMotorcycleId]    = useState('')
  const [lockedMotoId,    setLockedMotoId]    = useState(null)
  const [modelId,         setModelId]         = useState('')
  const [selectedColors,  setSelectedColors]  = useState([])

  // ── Lock timer ────────────────────────────────────────────────────────────
  const [lockSecondsLeft, setLockSecondsLeft] = useState(null)
  const [lockExpired,     setLockExpired]     = useState(false)
  const timerRef    = useRef(null)
  const lockedRef   = useRef(null)

  // Keep ref in sync so cleanup can access latest value
  useEffect(() => { lockedRef.current = lockedMotoId }, [lockedMotoId])

  // ── Step 3 selections ─────────────────────────────────────────────────────
  const [paymentCount, setPaymentCount] = useState(1)
  const [paymentItems, setPaymentItems] = useState([{ method_id: '', amount: '' }])
  const [financieraId, setFinancieraId] = useState('')

  // ── Submit / toast ────────────────────────────────────────────────────────
  const [submitting, setSubmitting] = useState(false)
  const [toast,      setToast]      = useState(null)

  // ── Fetch all static data on mount ────────────────────────────────────────
  useEffect(() => {
    Promise.all([
      api.get('/declare-payment/dealerships'),
      api.get('/declare-payment/clients'),
      api.get('/declare-payment/models'),
      api.get('/declare-payment/payment-methods'),
      api.get('/declare-payment/financieras'),
    ]).then(([d, c, m, pm, f]) => {
      setDealerships(d.data)
      setClients(c.data)
      setModels(m.data)
      setPaymentMethods(pm.data)
      setFinancieras(f.data)
    }).catch(() => {})
  }, [])

  // ── Fetch motorcycles when selections change ───────────────────────────────
  useEffect(() => {
    if (!dealershipId || !clientId || !paymentType || paymentType === 'reservation') {
      setMotorcycles([])
      return
    }
    setMotosLoading(true)
    api.get(`/declare-payment/motorcycles?dealership_id=${dealershipId}&client_id=${clientId}&payment_type=${paymentType}`)
      .then(r => setMotorcycles(r.data))
      .catch(() => setMotorcycles([]))
      .finally(() => setMotosLoading(false))
  }, [dealershipId, clientId, paymentType])

  // ── Cleanup timer + unlock on unmount ──────────────────────────────────────
  useEffect(() => {
    return () => {
      clearInterval(timerRef.current)
      if (lockedRef.current) {
        api.post('/sales/unlock-motorcycle', { motorcycle_id: parseInt(lockedRef.current) }).catch(() => {})
      }
    }
  }, [])

  // ── Handle lock expiry ────────────────────────────────────────────────────
  useEffect(() => {
    if (lockSecondsLeft === 0 && lockedRef.current) {
      api.post('/sales/unlock-motorcycle', { motorcycle_id: parseInt(lockedRef.current) }).catch(() => {})
      setLockedMotoId(null)
      setMotorcycleId('')
      setLockExpired(true)
    }
  }, [lockSecondsLeft])

  // ── Timer auto-dismiss toast on error ─────────────────────────────────────
  useEffect(() => {
    if (toast?.type === 'error') {
      const t = setTimeout(() => setToast(null), 5000)
      return () => clearTimeout(t)
    }
  }, [toast])

  // ── Timer helpers ─────────────────────────────────────────────────────────
  function startTimer() {
    clearInterval(timerRef.current)
    setLockSecondsLeft(LOCK_MINUTES * 60)
    timerRef.current = setInterval(() => {
      setLockSecondsLeft(prev => {
        if (prev === null || prev <= 1) {
          clearInterval(timerRef.current)
          return 0
        }
        return prev - 1
      })
    }, 1000)
  }

  function stopTimer() {
    clearInterval(timerRef.current)
    setLockSecondsLeft(null)
  }

  // ── Motorcycle lock/unlock ─────────────────────────────────────────────────
  async function handleMotoSelect(newMotoId) {
    const prevMotoId = lockedRef.current
    if (!newMotoId) {
      if (prevMotoId) {
        await api.post('/sales/unlock-motorcycle', { motorcycle_id: parseInt(prevMotoId) }).catch(() => {})
        setLockedMotoId(null)
        stopTimer()
      }
      setMotorcycleId('')
      return
    }
    try {
      const res = await api.post('/sales/lock-motorcycle', {
        motorcycle_id:          parseInt(newMotoId),
        previous_motorcycle_id: prevMotoId ? parseInt(prevMotoId) : null,
      })
      if (res.data.success) {
        setLockedMotoId(newMotoId)
        setMotorcycleId(newMotoId)
        startTimer()
      } else {
        alert(res.data.message ?? 'No se pudo reservar la moto.')
        setMotorcycleId('')
      }
    } catch {
      setMotorcycleId('')
    }
  }

  async function unlockCurrent() {
    const id = lockedRef.current
    if (id) {
      await api.post('/sales/unlock-motorcycle', { motorcycle_id: parseInt(id) }).catch(() => {})
      setLockedMotoId(null)
      stopTimer()
      setMotorcycleId('')
    }
  }

  // ── Payment items ──────────────────────────────────────────────────────────
  function handlePaymentCountChange(count) {
    const n = Number(count)
    setPaymentCount(n)
    setPaymentItems(prev => {
      const next = [...prev]
      while (next.length < n) next.push({ method_id: '', amount: '' })
      return next.slice(0, n)
    })
  }

  function updatePaymentItem(idx, field, value) {
    setPaymentItems(prev => prev.map((item, i) => i === idx ? { ...item, [field]: value } : item))
  }

  // ── Color selection ────────────────────────────────────────────────────────
  function toggleColor(color) {
    setSelectedColors(prev => {
      if (prev.includes(color)) return prev.filter(c => c !== color)
      if (prev.length >= MAX_COLORS) return prev
      return [...prev, color]
    })
  }

  // ── Derived values ─────────────────────────────────────────────────────────
  const selectedModel      = models.find(m => String(m.model_id) === modelId) ?? null
  const availableColors    = selectedModel?.colors ?? []
  const selectedMoto       = motorcycles.find(m => String(m.motorcycle_id) === motorcycleId) ?? null
  const totalPrice         = selectedMoto?.price ?? selectedModel?.price ?? 0
  const paymentSum         = paymentItems.reduce((s, item) => s + (parseFloat(item.amount) || 0), 0)
  const financingAmount    = totalPrice - paymentSum
  const selectedClient     = clients.find(c => String(c.client_id) === clientId) ?? null
  const selectedDealership = dealerships.find(d => String(d.dealership_id) === dealershipId) ?? null
  const selectedFinanciera = financieras.find(f => String(f.credit_institution_id) === financieraId) ?? null

  // ── Validation per step ───────────────────────────────────────────────────
  const step2Valid = (() => {
    if (!dealershipId || !clientId) return false
    if (paymentType === 'reservation') return !!modelId && selectedColors.length > 0
    return !!motorcycleId
  })()

  const step3Valid = (() => {
    const itemsOk = paymentItems.every(item => item.method_id && parseFloat(item.amount) > 0)
    if (!itemsOk) return false
    if (paymentType === 'enganche') return !!financieraId
    return true
  })()

  // ── Navigation ────────────────────────────────────────────────────────────
  function goBack() {
    if (step === 2) {
      unlockCurrent()
      setStep(1)
    } else {
      setStep(s => s - 1)
    }
  }

  function resetAll() {
    clearInterval(timerRef.current)
    setStep(1)
    setPaymentType(null)
    setDealershipId('')
    setClientId('')
    setMotorcycleId('')
    setLockedMotoId(null)
    setModelId('')
    setSelectedColors([])
    setMotorcycles([])
    setPaymentCount(1)
    setPaymentItems([{ method_id: '', amount: '' }])
    setFinancieraId('')
    setLockSecondsLeft(null)
    setLockExpired(false)
  }

  // ── Submit ────────────────────────────────────────────────────────────────
  async function handleSubmit() {
    setSubmitting(true)
    try {
      const body = {
        payment_type:  paymentType,
        dealership_id: parseInt(dealershipId),
        client_id:     parseInt(clientId),
        motorcycle_id: paymentType !== 'reservation' ? parseInt(motorcycleId) : null,
        model_id:      paymentType === 'reservation' ? parseInt(modelId) : null,
        colors:        paymentType === 'reservation' ? selectedColors : null,
        payment_items: paymentItems.map(item => ({
          method_id: parseInt(item.method_id),
          amount:    parseFloat(item.amount),
        })),
        financiera_id: paymentType === 'enganche' ? parseInt(financieraId) : null,
      }
      await api.post('/declare-payment/submit', body)
      setToast({ type: 'success', message: 'Pago declarado exitosamente' })
      setTimeout(() => navigate('/'), 2000)
    } catch (e) {
      const msg = e.response?.data?.detail ?? e.message ?? 'Error al declarar pago.'
      setToast({ type: 'error', message: msg })
    } finally {
      setSubmitting(false)
    }
  }

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <>
      <PageHeader section="Pagos" title="Declarar Pago" />
      <Toast toast={toast} onClose={() => setToast(null)} />
      {lockExpired && (
        <LockExpiredModal onConfirm={() => {
          resetAll()
        }} />
      )}

      <div className="col-center">
        <div style={{ width: '100%', maxWidth: '680px' }}>
          <StepIndicator step={step} />

          {/* ─── WINDOW 1 — Payment type ─────────────────────────────────── */}
          {step === 1 && (
            <div>
              <div className="upload-label" style={{ marginBottom: '1rem', fontSize: '0.95rem' }}>
                Selecciona el tipo de pago
              </div>
              <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                {[
                  { value: 'reservation', label: 'Reservación',  icon: '◈', desc: 'Apartar un modelo del catálogo' },
                  { value: 'al_contado',  label: 'Al Contado',   icon: '◇', desc: 'Pago total por una moto en stock' },
                  { value: 'enganche',    label: 'Enganche',      icon: '▷', desc: 'Pago inicial + financiamiento' },
                ].map(({ value, label, icon, desc }) => (
                  <button
                    key={value}
                    onClick={() => { setPaymentType(value); setStep(2) }}
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
                    <div style={{ fontWeight: 700, fontSize: '1rem', marginBottom: '0.25rem' }}>{label}</div>
                    <div style={{ fontSize: '0.78rem', color: '#64748B' }}>{desc}</div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* ─── WINDOW 2 — Client, dealership, moto / model ─────────────── */}
          {step === 2 && (
            <div className="bi-card">

              <div className="card-section">Sucursal</div>
              <div className="upload-label">Selecciona la sucursal</div>
              <select value={dealershipId} onChange={e => setDealershipId(e.target.value)}>
                <option value="">Seleccionar sucursal...</option>
                {dealerships.map(d => (
                  <option key={d.dealership_id} value={d.dealership_id}>{d.name}</option>
                ))}
              </select>

              <hr className="card-divider" />

              <div className="card-section">Cliente</div>
              <div className="upload-label">Selecciona el cliente</div>
              <select value={clientId} onChange={e => setClientId(e.target.value)}>
                <option value="">Seleccionar cliente...</option>
                {clients.map(c => (
                  <option key={c.client_id} value={c.client_id}>
                    {c.nombre_completo} — {c.rfc}
                  </option>
                ))}
              </select>

              {/* ── Reservación: model + colors ─────────────────────────── */}
              {paymentType === 'reservation' && (
                <>
                  <hr className="card-divider" />
                  <div className="card-section">Modelo</div>
                  <div className="upload-label">Selecciona el modelo a reservar</div>
                  <select value={modelId} onChange={e => { setModelId(e.target.value); setSelectedColors([]) }}>
                    <option value="">Seleccionar modelo...</option>
                    {models.map(m => (
                      <option key={m.model_id} value={m.model_id}>
                        {m.canonical_name} — {m.year}
                      </option>
                    ))}
                  </select>

                  <hr className="card-divider" />
                  <div className="card-section">Colores de Preferencia</div>
                  <div className="upload-label">Selecciona hasta {MAX_COLORS} colores en orden de preferencia</div>
                  {availableColors.length > 0 ? (
                    <div className="color-chips">
                      {availableColors.map(color => (
                        <span
                          key={color}
                          className={`color-chip${selectedColors.includes(color) ? ' selected' : ''}`}
                          onClick={() => toggleColor(color)}
                        >
                          {selectedColors.includes(color)
                            ? `${selectedColors.indexOf(color) + 1}. ${color}`
                            : color}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <div className="caption">
                      {modelId ? 'Este modelo no tiene colores registrados.' : 'Selecciona un modelo para ver colores.'}
                    </div>
                  )}
                  {selectedColors.length > 0 && (
                    <div className="priority-list" style={{ marginTop: '0.5rem' }}>
                      Prioridad: {selectedColors.map((c, i) => `${i + 1}. ${c}`).join('  ')}
                    </div>
                  )}
                </>
              )}

              {/* ── Al Contado / Enganche: motorcycle selector ───────────── */}
              {(paymentType === 'al_contado' || paymentType === 'enganche') && (
                <>
                  <hr className="card-divider" />
                  <div className="card-section">Motocicleta</div>
                  {(!dealershipId || !clientId) ? (
                    <div className="caption">Selecciona sucursal y cliente primero.</div>
                  ) : motosLoading ? (
                    <div className="caption">Cargando motocicletas...</div>
                  ) : motorcycles.length === 0 ? (
                    <div className="caption">No hay motocicletas disponibles para esta combinación.</div>
                  ) : (
                    <>
                      <select
                        value={motorcycleId}
                        onChange={e => handleMotoSelect(e.target.value)}
                      >
                        <option value="">Seleccionar motocicleta...</option>
                        {motorcycles.map(m => (
                          <option key={m.motorcycle_id} value={m.motorcycle_id}>
                            {m.model_name} — {m.color} — Serie: {m.reference_number || '—'} — ${fmt(m.price)}
                            {m.status === 'in_stock_reserved' ? ' ⭐ (Reservada)' : ''}
                          </option>
                        ))}
                      </select>

                      {motorcycleId && lockSecondsLeft !== null && (
                        <div style={{
                          marginTop: '0.5rem', padding: '0.4rem 0.75rem',
                          background: lockSecondsLeft < 120 ? '#FEF2F2' : '#EFF6FF',
                          color: lockSecondsLeft < 120 ? '#DC2626' : '#1D4ED8',
                          borderRadius: '0.4rem', fontSize: '0.82rem', fontWeight: 600, display: 'inline-block',
                        }}>
                          ⏱ Reservada por: {fmtTime(lockSecondsLeft)}
                        </div>
                      )}
                    </>
                  )}
                </>
              )}

              <div className="btn-row" style={{ marginTop: '1.5rem' }}>
                <button className="btn-secondary" onClick={goBack}>← Volver</button>
                <button
                  className="btn-primary"
                  disabled={!step2Valid}
                  onClick={() => setStep(3)}
                >
                  Siguiente →
                </button>
              </div>
            </div>
          )}

          {/* ─── WINDOW 3 — Payment items ─────────────────────────────────── */}
          {step === 3 && (
            <div className="bi-card">
              <div className="card-section">Número de Pagos</div>
              <div className="upload-label">¿Cuántos pagos declaras?</div>
              <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '1.25rem' }}>
                {Array.from({ length: MAX_ITEMS }, (_, i) => i + 1).map(n => (
                  <button
                    key={n}
                    onClick={() => handlePaymentCountChange(n)}
                    style={{
                      width: '2.5rem', height: '2.5rem', borderRadius: '0.4rem', border: '2px solid',
                      borderColor: paymentCount === n ? '#1D4ED8' : '#E2E8F0',
                      background: paymentCount === n ? '#1D4ED8' : '#fff',
                      color: paymentCount === n ? '#fff' : '#1E293B',
                      fontWeight: 700, cursor: 'pointer',
                    }}
                  >
                    {n}
                  </button>
                ))}
              </div>

              {paymentItems.map((item, idx) => (
                <div key={idx} style={{ marginBottom: '1rem' }}>
                  <div className="upload-label">Pago {idx + 1}</div>
                  <div className="form-row">
                    <div className="form-field">
                      <label>Método</label>
                      <select
                        value={item.method_id}
                        onChange={e => updatePaymentItem(idx, 'method_id', e.target.value)}
                      >
                        <option value="">Seleccionar...</option>
                        {paymentMethods.map(m => (
                          <option key={m.method_id} value={m.method_id}>{m.name}</option>
                        ))}
                      </select>
                    </div>
                    <div className="form-field">
                      <label>Monto (MXN)</label>
                      <input
                        type="number"
                        min="0.01"
                        step="100"
                        value={item.amount}
                        onChange={e => updatePaymentItem(idx, 'amount', e.target.value)}
                        placeholder="0.00"
                      />
                    </div>
                  </div>
                </div>
              ))}

              {paymentType === 'enganche' && (
                <>
                  <hr className="card-divider" />
                  <div className="card-section">Financiamiento</div>
                  <div className="upload-label">Institución Financiera</div>
                  <select value={financieraId} onChange={e => setFinancieraId(e.target.value)}>
                    <option value="">Seleccionar financiera...</option>
                    {financieras.map(f => (
                      <option key={f.credit_institution_id} value={f.credit_institution_id}>{f.name}</option>
                    ))}
                  </select>

                  {totalPrice > 0 && (
                    <div style={{
                      marginTop: '0.75rem', padding: '0.6rem 1rem',
                      background: '#F0FDF4', borderRadius: '0.5rem', fontSize: '0.88rem',
                    }}>
                      <span style={{ color: '#64748B' }}>Precio moto: </span>
                      <strong>${fmt(totalPrice)}</strong>
                      <span style={{ margin: '0 0.5rem', color: '#94A3B8' }}>—</span>
                      <span style={{ color: '#64748B' }}>Enganche declarado: </span>
                      <strong>${fmt(paymentSum)}</strong>
                      <span style={{ margin: '0 0.5rem', color: '#94A3B8' }}>→</span>
                      <span style={{ color: '#15803D', fontWeight: 700 }}>
                        Monto a financiar: ${fmt(Math.max(0, financingAmount))}
                      </span>
                    </div>
                  )}
                </>
              )}

              <div className="btn-row" style={{ marginTop: '1.5rem' }}>
                <button className="btn-secondary" onClick={goBack}>← Volver</button>
                <button
                  className="btn-primary"
                  disabled={!step3Valid}
                  onClick={() => setStep(4)}
                >
                  Revisar →
                </button>
              </div>
            </div>
          )}

          {/* ─── WINDOW 4 — Summary + submit ─────────────────────────────── */}
          {step === 4 && (
            <div className="bi-card">
              <div className="card-section">Resumen del Pago</div>

              <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: '1rem', fontSize: '0.88rem' }}>
                <tbody>
                  <tr>
                    <td style={{ padding: '0.35rem 0', color: '#64748B', width: '45%' }}>Tipo</td>
                    <td style={{ padding: '0.35rem 0', fontWeight: 600 }}>
                      {{ reservation: 'Reservación', al_contado: 'Al Contado', enganche: 'Enganche' }[paymentType]}
                    </td>
                  </tr>
                  <tr>
                    <td style={{ padding: '0.35rem 0', color: '#64748B' }}>Cliente</td>
                    <td style={{ padding: '0.35rem 0', fontWeight: 600 }}>
                      {selectedClient?.nombre_completo} <span style={{ color: '#94A3B8', fontWeight: 400 }}>({selectedClient?.rfc})</span>
                    </td>
                  </tr>
                  <tr>
                    <td style={{ padding: '0.35rem 0', color: '#64748B' }}>Sucursal</td>
                    <td style={{ padding: '0.35rem 0', fontWeight: 600 }}>{selectedDealership?.name}</td>
                  </tr>

                  {paymentType === 'reservation' && selectedModel && (
                    <>
                      <tr>
                        <td style={{ padding: '0.35rem 0', color: '#64748B' }}>Modelo</td>
                        <td style={{ padding: '0.35rem 0', fontWeight: 600 }}>
                          {selectedModel.canonical_name} — {selectedModel.year}
                        </td>
                      </tr>
                      <tr>
                        <td style={{ padding: '0.35rem 0', color: '#64748B', verticalAlign: 'top' }}>Colores (prioridad)</td>
                        <td style={{ padding: '0.35rem 0', fontWeight: 600 }}>
                          {selectedColors.map((c, i) => `${i + 1}. ${c}`).join(', ')}
                        </td>
                      </tr>
                    </>
                  )}

                  {paymentType !== 'reservation' && selectedMoto && (
                    <>
                      <tr>
                        <td style={{ padding: '0.35rem 0', color: '#64748B' }}>Modelo</td>
                        <td style={{ padding: '0.35rem 0', fontWeight: 600 }}>{selectedMoto.model_name}</td>
                      </tr>
                      <tr>
                        <td style={{ padding: '0.35rem 0', color: '#64748B' }}>Color</td>
                        <td style={{ padding: '0.35rem 0', fontWeight: 600 }}>{selectedMoto.color || '—'}</td>
                      </tr>
                      <tr>
                        <td style={{ padding: '0.35rem 0', color: '#64748B' }}>No. Serie</td>
                        <td style={{ padding: '0.35rem 0', fontWeight: 600, fontFamily: 'monospace' }}>
                          {selectedMoto.reference_number || '—'}
                        </td>
                      </tr>
                    </>
                  )}
                </tbody>
              </table>

              <hr className="card-divider" />

              <div className="card-section">Ítems de Pago</div>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.88rem', marginBottom: '0.5rem' }}>
                <thead>
                  <tr>
                    <th style={{ textAlign: 'left', padding: '0.35rem 0', color: '#64748B', fontWeight: 600 }}>#</th>
                    <th style={{ textAlign: 'left', padding: '0.35rem 0', color: '#64748B', fontWeight: 600 }}>Método</th>
                    <th style={{ textAlign: 'right', padding: '0.35rem 0', color: '#64748B', fontWeight: 600 }}>Monto</th>
                  </tr>
                </thead>
                <tbody>
                  {paymentItems.map((item, idx) => {
                    const method = paymentMethods.find(m => String(m.method_id) === String(item.method_id))
                    return (
                      <tr key={idx}>
                        <td style={{ padding: '0.3rem 0', color: '#94A3B8' }}>{idx + 1}</td>
                        <td style={{ padding: '0.3rem 0', fontWeight: 600 }}>{method?.name ?? '—'}</td>
                        <td style={{ padding: '0.3rem 0', textAlign: 'right', fontFamily: 'monospace' }}>
                          ${fmt(item.amount)}
                        </td>
                      </tr>
                    )
                  })}
                  <tr style={{ borderTop: '2px solid #E2E8F0' }}>
                    <td colSpan={2} style={{ padding: '0.4rem 0', fontWeight: 700 }}>Total declarado</td>
                    <td style={{ padding: '0.4rem 0', textAlign: 'right', fontWeight: 700, fontFamily: 'monospace' }}>
                      ${fmt(paymentSum)}
                    </td>
                  </tr>
                </tbody>
              </table>

              {paymentType === 'enganche' && selectedFinanciera && (
                <>
                  <hr className="card-divider" />
                  <div className="card-section">Financiamiento</div>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.88rem' }}>
                    <tbody>
                      <tr>
                        <td style={{ padding: '0.35rem 0', color: '#64748B', width: '45%' }}>Financiera</td>
                        <td style={{ fontWeight: 600 }}>{selectedFinanciera.name}</td>
                      </tr>
                      <tr>
                        <td style={{ padding: '0.35rem 0', color: '#64748B' }}>Monto a financiar</td>
                        <td style={{ fontWeight: 700, color: '#15803D', fontFamily: 'monospace' }}>
                          ${fmt(Math.max(0, financingAmount))}
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </>
              )}

              <div className="btn-row" style={{ marginTop: '1.5rem' }}>
                <button className="btn-secondary" onClick={goBack}>← Volver</button>
                <button
                  className="btn-primary"
                  disabled={submitting}
                  onClick={handleSubmit}
                >
                  {submitting ? 'Enviando...' : 'Declarar Pago'}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  )
}
