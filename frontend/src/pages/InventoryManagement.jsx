import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../api'
import PageHeader from '../components/PageHeader'
import StepIndicator from '../components/StepIndicator'
import Toast from '../components/Toast'
import { fmt } from '../utils'
import RecordCard from './InventoryManagement/RecordCard'
import ClientDropdown from './InventoryManagement/ClientDropdown'
import ActivitySelector from './InventoryManagement/ActivitySelector'

const EMPTY_ACTIVITY = { sales: [], standalone_reservations: [], reservations: [] }

export default function InventoryManagement() {
  const navigate = useNavigate()

  // ── Step control ─────────────────────────────────────────────────────────
  const [step,          setStep]          = useState(1)
  const [operationType, setOperationType] = useState(null)

  // ── Cancel flow ───────────────────────────────────────────────────────────
  const [cancelClientFilter,   setCancelClientFilter]   = useState('')
  const [clientsWithActivity,  setClientsWithActivity]  = useState([])
  const [cancelClientId,       setCancelClientId]       = useState('')
  const [clientActivity,       setClientActivity]       = useState(EMPTY_ACTIVITY)
  const [activityLoading,      setActivityLoading]      = useState(false)
  const [selectedRecord,       setSelectedRecord]       = useState(null)

  // ── Rechazar flow ─────────────────────────────────────────────────────────
  const [motorInput,        setMotorInput]        = useState('')
  const [serieInput,        setSerieInput]        = useState('')
  const [motoSearchResult,  setMotoSearchResult]  = useState(null)
  const [motoSearchLoading, setMotoSearchLoading] = useState(false)
  const [motoSearchError,   setMotoSearchError]   = useState('')

  // ── Transfer flow ─────────────────────────────────────────────────────────
  const [transferOriginFilter,   setTransferOriginFilter]   = useState('')
  const [clientsWithSales,       setClientsWithSales]       = useState([])
  const [transferOriginId,       setTransferOriginId]       = useState('')
  const [transferOriginActivity, setTransferOriginActivity] = useState(EMPTY_ACTIVITY)
  const [transferOriginLoading,  setTransferOriginLoading]  = useState(false)
  const [transferRecord,         setTransferRecord]         = useState(null)
  const [transferDestFilter,     setTransferDestFilter]     = useState('')
  const [allClients,             setAllClients]             = useState([])
  const [transferDestId,         setTransferDestId]         = useState('')

  // ── Reason + submit ───────────────────────────────────────────────────────
  const [reason,     setReason]     = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [toast,      setToast]      = useState(null)

  // ── Load lists when operation type is chosen ──────────────────────────────
  useEffect(() => {
    if (!operationType) return
    if (operationType === 'cancelar') {
      api.get('/inventory-management/clients-with-activity')
        .then(r => setClientsWithActivity(r.data))
        .catch(() => {})
    }
    if (operationType === 'transferir') {
      Promise.all([
        api.get('/inventory-management/clients-with-sales'),
        api.get('/declare-payment/clients'),
      ]).then(([cs, all]) => {
        setClientsWithSales(cs.data)
        setAllClients(all.data)
      }).catch(() => {})
    }
  }, [operationType])

  // ── Load activity for selected cancel client ──────────────────────────────
  useEffect(() => {
    if (!cancelClientId) return
    setActivityLoading(true)
    setSelectedRecord(null)
    api.get(`/inventory-management/client-activity/${cancelClientId}`)
      .then(r => setClientActivity(r.data))
      .catch(() => setClientActivity(EMPTY_ACTIVITY))
      .finally(() => setActivityLoading(false))
  }, [cancelClientId])

  // ── Load activity for transfer origin ────────────────────────────────────
  useEffect(() => {
    if (!transferOriginId) return
    setTransferOriginLoading(true)
    setTransferRecord(null)
    api.get(`/inventory-management/client-activity/${transferOriginId}`)
      .then(r => setTransferOriginActivity(r.data))
      .catch(() => setTransferOriginActivity(EMPTY_ACTIVITY))
      .finally(() => setTransferOriginLoading(false))
  }, [transferOriginId])

  // ── Auto-dismiss error toasts ─────────────────────────────────────────────
  useEffect(() => {
    if (toast?.type === 'error') {
      const t = setTimeout(() => setToast(null), 5000)
      return () => clearTimeout(t)
    }
  }, [toast])

  // ── Derived: step 2 validity ─────────────────────────────────────────────
  const step2Valid =
    operationType === 'cancelar'   ? (!!cancelClientId && !!selectedRecord) :
    operationType === 'rechazar'   ? !!motoSearchResult :
    operationType === 'transferir' ? (!!transferOriginId && !!transferRecord && !!transferDestId && String(transferOriginId) !== String(transferDestId)) :
    false

  const step3Valid = reason.trim().length > 0 && reason.trim().length <= 128

  // ── Derived: selected client objects ─────────────────────────────────────
  const cancelClient         = clientsWithActivity.find(c => String(c.client_id) === String(cancelClientId))
  const transferOriginClient = clientsWithSales.find(c => String(c.client_id) === String(transferOriginId))
  const transferDestClient   = allClients.find(c => String(c.client_id) === String(transferDestId))

  // ── Computed refund for cancel sale ──────────────────────────────────────
  const cancelRefund = (() => {
    if (operationType !== 'cancelar' || selectedRecord?.type !== 'sale') return 0
    return (selectedRecord.data.events || [])
      .filter(ev => ev.event_type !== 'financing')
      .reduce((sum, ev) => sum + (ev.items || []).reduce((s2, item) => s2 + item.amount, 0), 0)
  })()

  // ── Filtered client lists ─────────────────────────────────────────────────
  const filteredCancelClients = clientsWithActivity.filter(c =>
    c.nombre_completo.toLowerCase().includes(cancelClientFilter.toLowerCase())
  )
  const filteredTransferOrigins = clientsWithSales.filter(c =>
    c.nombre_completo.toLowerCase().includes(transferOriginFilter.toLowerCase())
  )
  const filteredTransferDests = allClients.filter(c =>
    c.nombre_completo.toLowerCase().includes(transferDestFilter.toLowerCase()) &&
    String(c.client_id) !== String(transferOriginId)
  )

  // ── Moto search ───────────────────────────────────────────────────────────
  async function handleSearchMoto() {
    const params = []
    if (motorInput.trim()) params.push(`motor=${encodeURIComponent(motorInput.trim())}`)
    if (serieInput.trim()) params.push(`serie=${encodeURIComponent(serieInput.trim())}`)
    setMotoSearchLoading(true)
    setMotoSearchError('')
    setMotoSearchResult(null)
    try {
      const res = await api.get(`/inventory-management/moto-by-identifier?${params.join('&')}`)
      if (res.data.length === 0) {
        setMotoSearchError('No se encontró motocicleta disponible con ese identificador.')
      } else {
        setMotoSearchResult(res.data[0])
      }
    } catch (e) {
      setMotoSearchError(e.response?.data?.detail ?? 'Error al buscar motocicleta.')
    } finally {
      setMotoSearchLoading(false)
    }
  }

  // ── Navigation ────────────────────────────────────────────────────────────
  function goBack() {
    if (step === 2) {
      setOperationType(null)
      resetFlowData()
      setStep(1)
    } else {
      setStep(s => s - 1)
    }
  }

  function resetFlowData() {
    setCancelClientFilter('')
    setCancelClientId('')
    setClientActivity(EMPTY_ACTIVITY)
    setSelectedRecord(null)
    setMotorInput('')
    setSerieInput('')
    setMotoSearchResult(null)
    setMotoSearchError('')
    setTransferOriginFilter('')
    setTransferOriginId('')
    setTransferOriginActivity(EMPTY_ACTIVITY)
    setTransferRecord(null)
    setTransferDestFilter('')
    setTransferDestId('')
    setReason('')
  }

  // ── Submit ────────────────────────────────────────────────────────────────
  async function handleSubmit() {
    setSubmitting(true)
    try {
      if (operationType === 'cancelar') {
        await api.post('/inventory-management/cancel-activity', {
          sale_id:        selectedRecord.type === 'sale'        ? selectedRecord.id : null,
          reservation_id: selectedRecord.type === 'reservation' ? selectedRecord.id : null,
          reason,
        })
      } else if (operationType === 'rechazar') {
        await api.post('/inventory-management/reject-moto', {
          motorcycle_id: motoSearchResult.motorcycle_id,
          reason,
        })
      } else if (operationType === 'transferir') {
        await api.post('/inventory-management/transfer-client', {
          from_client_id: parseInt(transferOriginId),
          to_client_id:   parseInt(transferDestId),
          sale_id:        transferRecord.type === 'sale'        ? transferRecord.id : null,
          reservation_id: transferRecord.type === 'reservation' ? transferRecord.id : null,
          reason,
        })
      }
      setToast({ type: 'success', message: 'Operación completada exitosamente.' })
      setTimeout(() => navigate('/'), 2000)
    } catch (e) {
      const msg = e.response?.data?.detail ?? e.message ?? 'Error al procesar la operación.'
      setToast({ type: 'error', message: msg })
    } finally {
      setSubmitting(false)
    }
  }

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <>
      <PageHeader section="Inventario" title="Modificar Inventario" />
      <Toast toast={toast} onClose={() => setToast(null)} />

      <div className="col-center">
        <div style={{ width: '100%', maxWidth: '680px' }}>
          <StepIndicator step={step} labels={['Operación', 'Datos', 'Motivo', 'Confirmar']} />

          {/* ─── WINDOW 1 — Operation type ────────────────────────────── */}
          {step === 1 && (
            <div>
              <div className="upload-label" style={{ marginBottom: '1rem', fontSize: '0.95rem' }}>
                Selecciona el tipo de operación
              </div>
              <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                {[
                  { value: 'cancelar',   label: 'Cancelar Reservación / Venta', icon: '✕', desc: 'Cancelar una reservación o venta abierta' },
                  { value: 'rechazar',   label: 'Rechazar Motocicleta',          icon: '⊗', desc: 'Marcar una moto en stock como rechazada' },
                  { value: 'transferir', label: 'Transferir Datos de Pago',      icon: '⇄', desc: 'Cambiar el cliente vinculado a una venta o reservación' },
                ].map(({ value, label, icon, desc }) => (
                  <button
                    key={value}
                    onClick={() => { setOperationType(value); setStep(2) }}
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

          {/* ─── WINDOW 2 — Context selection ────────────────────────── */}
          {step === 2 && (
            <div className="bi-card">

              {/* ── CANCELAR ─── */}
              {operationType === 'cancelar' && (
                <>
                  <div className="card-section">Cliente</div>
                  <div className="upload-label">Buscar cliente con actividad activa</div>
                  <ClientDropdown
                    filter={cancelClientFilter}
                    setFilter={setCancelClientFilter}
                    selectedId={cancelClientId}
                    setSelectedId={id => { setCancelClientId(id); setSelectedRecord(null) }}
                    options={filteredCancelClients}
                    placeholder="Buscar por nombre..."
                  />

                  {cancelClientId && (
                    <>
                      <hr className="card-divider" />
                      <div className="upload-label">Selecciona el registro a cancelar</div>
                      <ActivitySelector
                        activity={clientActivity}
                        loading={activityLoading}
                        selectedRec={selectedRecord}
                        setSelectedRec={setSelectedRecord}
                        mode='cancel'
                      />
                    </>
                  )}
                </>
              )}

              {/* ── RECHAZAR ─── */}
              {operationType === 'rechazar' && (
                <>
                  <div className="card-section">Identificar Motocicleta</div>
                  <div className="upload-label">Ingresa número de motor o de serie (al menos uno)</div>
                  <div className="form-row">
                    <div className="form-field">
                      <label>Número de Motor</label>
                      <input
                        type="text"
                        placeholder="Ej. ABC12345678"
                        value={motorInput}
                        onChange={e => { setMotorInput(e.target.value); setMotoSearchResult(null); setMotoSearchError('') }}
                      />
                    </div>
                    <div className="form-field">
                      <label>Número de Serie</label>
                      <input
                        type="text"
                        placeholder="Ej. MD2A68EZ1NWM00001"
                        value={serieInput}
                        onChange={e => { setSerieInput(e.target.value); setMotoSearchResult(null); setMotoSearchError('') }}
                      />
                    </div>
                  </div>
                  <button
                    className="btn-secondary"
                    disabled={(!motorInput.trim() && !serieInput.trim()) || motoSearchLoading}
                    onClick={handleSearchMoto}
                    style={{ marginTop: '0.5rem' }}
                  >
                    {motoSearchLoading ? 'Buscando...' : 'Buscar'}
                  </button>

                  {motoSearchError && (
                    <div style={{
                      marginTop: '0.75rem', padding: '0.6rem 1rem',
                      background: '#FEF2F2', color: '#DC2626',
                      borderRadius: '0.5rem', fontSize: '0.85rem',
                      border: '1px solid #FECACA',
                    }}>
                      {motoSearchError}
                    </div>
                  )}

                  {motoSearchResult && (
                    <>
                      <hr className="card-divider" />
                      <div className="card-section">Motocicleta Encontrada</div>
                      <div style={{
                        border: '2px solid #15803D', borderRadius: '0.5rem',
                        padding: '0.75rem', background: '#F0FDF4',
                      }}>
                        <div style={{ fontWeight: 700, fontSize: '1rem' }}>
                          {motoSearchResult.model_name} {motoSearchResult.year} — {motoSearchResult.color || '—'}
                        </div>
                        <div style={{ fontSize: '0.82rem', fontFamily: 'monospace', color: '#475569', marginTop: '0.25rem' }}>
                          Serie: {motoSearchResult.serie || '—'} · Motor: {motoSearchResult.motor || '—'}
                        </div>
                        <div style={{ fontSize: '0.82rem', color: '#64748B', marginTop: '0.25rem' }}>
                          {motoSearchResult.dealership} · Estado: {motoSearchResult.status}
                        </div>
                        {motoSearchResult.status === 'in_stock_reserved' && (
                          <div style={{
                            marginTop: '0.5rem', fontSize: '0.82rem',
                            color: '#D97706', fontWeight: 600,
                          }}>
                            ⚠ Esta moto tiene una reservación vinculada. Al rechazarla, la reservación volverá a estado "activa".
                          </div>
                        )}
                      </div>
                    </>
                  )}
                </>
              )}

              {/* ── TRANSFERIR ─── */}
              {operationType === 'transferir' && (
                <>
                  <div className="card-section">Cliente Origen</div>
                  <div className="upload-label">Buscar cliente con ventas o reservaciones</div>
                  <ClientDropdown
                    filter={transferOriginFilter}
                    setFilter={setTransferOriginFilter}
                    selectedId={transferOriginId}
                    setSelectedId={id => { setTransferOriginId(id); setTransferRecord(null); setTransferDestId(''); setTransferDestFilter('') }}
                    options={filteredTransferOrigins}
                    placeholder="Buscar cliente origen..."
                  />

                  {transferOriginId && (
                    <>
                      <hr className="card-divider" />
                      <div className="upload-label">Selecciona el registro a transferir</div>
                      <ActivitySelector
                        activity={transferOriginActivity}
                        loading={transferOriginLoading}
                        selectedRec={transferRecord}
                        setSelectedRec={rec => { setTransferRecord(rec); setTransferDestId(''); setTransferDestFilter('') }}
                        mode='transfer'
                      />
                    </>
                  )}

                  {transferRecord && (
                    <>
                      <hr className="card-divider" />
                      <div className="card-section">Cliente Destino</div>
                      <div className="upload-label">Buscar el nuevo cliente al que se transferirán los datos</div>
                      <ClientDropdown
                        filter={transferDestFilter}
                        setFilter={setTransferDestFilter}
                        selectedId={transferDestId}
                        setSelectedId={setTransferDestId}
                        options={filteredTransferDests}
                        placeholder="Buscar cliente destino..."
                      />
                      {transferDestId && transferDestClient && (
                        <div style={{
                          marginTop: '0.5rem', padding: '0.6rem 1rem',
                          background: '#F0FDF4', borderRadius: '0.5rem',
                          border: '1px solid #BBF7D0', fontSize: '0.88rem',
                        }}>
                          <strong>{transferDestClient.nombre_completo}</strong>
                          <span style={{ color: '#64748B', marginLeft: '0.5rem' }}>{transferDestClient.rfc}</span>
                        </div>
                      )}
                      {transferDestId && String(transferDestId) === String(transferOriginId) && (
                        <div style={{ marginTop: '0.5rem', color: '#DC2626', fontSize: '0.85rem' }}>
                          El cliente destino debe ser diferente al origen.
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

          {/* ─── WINDOW 3 — Reason ───────────────────────────────────── */}
          {step === 3 && (
            <div className="bi-card">
              <div className="card-section">Motivo</div>

              {/* Context summary */}
              <div style={{
                padding: '0.6rem 1rem', background: '#F8FAFC',
                borderRadius: '0.5rem', fontSize: '0.85rem', marginBottom: '1rem',
                border: '1px solid #E2E8F0',
              }}>
                {operationType === 'cancelar' && selectedRecord && (
                  <>
                    <strong>Cancelar {selectedRecord.type === 'reservation' ? 'reservación' : 'venta'}</strong>
                    {' — '}
                    {cancelClient?.nombre_completo}
                    {selectedRecord.type === 'sale' && selectedRecord.data.motorcycle &&
                      ` · ${selectedRecord.data.motorcycle.model_name} ${selectedRecord.data.motorcycle.year}`}
                    {selectedRecord.type === 'reservation' &&
                      ` · ${selectedRecord.data.model_name} ${selectedRecord.data.year}`}
                  </>
                )}
                {operationType === 'rechazar' && motoSearchResult && (
                  <>
                    <strong>Rechazar moto</strong>
                    {` — ${motoSearchResult.model_name} ${motoSearchResult.year} · Serie: ${motoSearchResult.serie || '—'}`}
                  </>
                )}
                {operationType === 'transferir' && transferRecord && (
                  <>
                    <strong>Transferir</strong>
                    {' de '}
                    {transferOriginClient?.nombre_completo}
                    {' a '}
                    {transferDestClient?.nombre_completo}
                    {transferRecord.type === 'sale' && transferRecord.data.motorcycle &&
                      ` · ${transferRecord.data.motorcycle.model_name}`}
                    {transferRecord.type === 'reservation' &&
                      ` · ${transferRecord.data.model_name}`}
                  </>
                )}
              </div>

              <div className="upload-label">Motivo (requerido)</div>
              <textarea
                rows={3}
                maxLength={128}
                value={reason}
                onChange={e => setReason(e.target.value)}
                placeholder="Describe el motivo de la operación..."
                style={{ width: '100%', resize: 'vertical', padding: '0.5rem 0.75rem', borderRadius: '0.4rem', border: '1px solid #CBD5E1', fontSize: '0.9rem', fontFamily: 'inherit' }}
              />
              <div style={{ fontSize: '0.78rem', color: reason.length > 120 ? '#D97706' : '#94A3B8', textAlign: 'right', marginTop: '0.2rem' }}>
                {reason.length}/128
              </div>

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

          {/* ─── WINDOW 4 — Confirmation summary ─────────────────────── */}
          {step === 4 && (
            <div className="bi-card">
              <div className="card-section">Resumen de la Operación</div>

              {/* ── CANCELAR summary ── */}
              {operationType === 'cancelar' && selectedRecord && (
                <>
                  <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: '1rem', fontSize: '0.88rem' }}>
                    <tbody>
                      <tr>
                        <td style={{ padding: '0.35rem 0', color: '#64748B', width: '45%' }}>Operación</td>
                        <td style={{ padding: '0.35rem 0', fontWeight: 600 }}>
                          {selectedRecord.type === 'reservation' ? 'Cancelar Reservación' : 'Cancelar Venta'}
                        </td>
                      </tr>
                      <tr>
                        <td style={{ padding: '0.35rem 0', color: '#64748B' }}>Cliente</td>
                        <td style={{ padding: '0.35rem 0', fontWeight: 600 }}>
                          {cancelClient?.nombre_completo}
                          <span style={{ color: '#94A3B8', fontWeight: 400, marginLeft: '0.4rem' }}>({cancelClient?.rfc})</span>
                        </td>
                      </tr>

                      {selectedRecord.type === 'reservation' && (
                        <>
                          <tr>
                            <td style={{ padding: '0.35rem 0', color: '#64748B' }}>Modelo</td>
                            <td style={{ padding: '0.35rem 0', fontWeight: 600 }}>
                              {selectedRecord.data.model_name} {selectedRecord.data.year}
                            </td>
                          </tr>
                          <tr>
                            <td style={{ padding: '0.35rem 0', color: '#64748B' }}>Depósito</td>
                            <td style={{ padding: '0.35rem 0', fontWeight: 600 }}>${fmt(selectedRecord.data.deposit_amount)}</td>
                          </tr>
                          {selectedRecord.data.motorcycle && (
                            <>
                              <tr>
                                <td style={{ padding: '0.35rem 0', color: '#64748B' }}>Moto asignada</td>
                                <td style={{ padding: '0.35rem 0', fontWeight: 600 }}>
                                  {selectedRecord.data.motorcycle.model_name} — {selectedRecord.data.motorcycle.color || '—'}
                                </td>
                              </tr>
                              <tr>
                                <td style={{ padding: '0.35rem 0', color: '#64748B' }}>Serie / Motor</td>
                                <td style={{ padding: '0.35rem 0', fontFamily: 'monospace', fontSize: '0.82rem' }}>
                                  {selectedRecord.data.motorcycle.serie || '—'} / {selectedRecord.data.motorcycle.motor || '—'}
                                </td>
                              </tr>
                            </>
                          )}
                          <tr>
                            <td style={{ padding: '0.35rem 0', color: '#64748B' }}>Sucursal</td>
                            <td style={{ padding: '0.35rem 0', fontWeight: 600 }}>{selectedRecord.data.dealership_name}</td>
                          </tr>
                          <tr>
                            <td style={{ padding: '0.35rem 0', color: '#64748B' }}>Efecto</td>
                            <td style={{ padding: '0.35rem 0', color: '#DC2626', fontWeight: 600 }}>
                              Reservación → cancelada
                              {selectedRecord.data.motorcycle ? ' · Moto → en_stock' : ''}
                            </td>
                          </tr>
                        </>
                      )}

                      {selectedRecord.type === 'sale' && (
                        <>
                          {selectedRecord.data.motorcycle && (
                            <>
                              <tr>
                                <td style={{ padding: '0.35rem 0', color: '#64748B' }}>Moto</td>
                                <td style={{ padding: '0.35rem 0', fontWeight: 600 }}>
                                  {selectedRecord.data.motorcycle.model_name} {selectedRecord.data.motorcycle.year} — {selectedRecord.data.motorcycle.color || '—'}
                                </td>
                              </tr>
                              <tr>
                                <td style={{ padding: '0.35rem 0', color: '#64748B' }}>Serie / Motor</td>
                                <td style={{ padding: '0.35rem 0', fontFamily: 'monospace', fontSize: '0.82rem' }}>
                                  {selectedRecord.data.motorcycle.serie || '—'} / {selectedRecord.data.motorcycle.motor || '—'}
                                </td>
                              </tr>
                            </>
                          )}
                          <tr>
                            <td style={{ padding: '0.35rem 0', color: '#64748B' }}>Total venta</td>
                            <td style={{ padding: '0.35rem 0', fontWeight: 600 }}>${fmt(selectedRecord.data.total_price)}</td>
                          </tr>
                          <tr>
                            <td style={{ padding: '0.35rem 0', color: '#64748B' }}>Sucursal</td>
                            <td style={{ padding: '0.35rem 0', fontWeight: 600 }}>{selectedRecord.data.dealership_name || '—'}</td>
                          </tr>
                          <tr>
                            <td style={{ padding: '0.35rem 0', color: '#64748B' }}>Efecto</td>
                            <td style={{ padding: '0.35rem 0', color: '#DC2626', fontWeight: 600 }}>
                              Venta → cancelada · Pagos → reembolsados
                              {selectedRecord.data.motorcycle ? ' · Moto → en_stock' : ''}
                            </td>
                          </tr>
                          {cancelRefund > 0 && (
                            <tr>
                              <td style={{ padding: '0.35rem 0', color: '#64748B' }}>Monto a reembolsar</td>
                              <td style={{ padding: '0.35rem 0', fontWeight: 700, color: '#D97706' }}>
                                ${fmt(cancelRefund)}
                              </td>
                            </tr>
                          )}
                        </>
                      )}
                    </tbody>
                  </table>
                </>
              )}

              {/* ── RECHAZAR summary ── */}
              {operationType === 'rechazar' && motoSearchResult && (
                <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: '1rem', fontSize: '0.88rem' }}>
                  <tbody>
                    <tr>
                      <td style={{ padding: '0.35rem 0', color: '#64748B', width: '45%' }}>Operación</td>
                      <td style={{ padding: '0.35rem 0', fontWeight: 600 }}>Rechazar Motocicleta</td>
                    </tr>
                    <tr>
                      <td style={{ padding: '0.35rem 0', color: '#64748B' }}>Modelo</td>
                      <td style={{ padding: '0.35rem 0', fontWeight: 600 }}>
                        {motoSearchResult.model_name} {motoSearchResult.year} — {motoSearchResult.color || '—'}
                      </td>
                    </tr>
                    <tr>
                      <td style={{ padding: '0.35rem 0', color: '#64748B' }}>Serie / Motor</td>
                      <td style={{ padding: '0.35rem 0', fontFamily: 'monospace', fontSize: '0.82rem' }}>
                        {motoSearchResult.serie || '—'} / {motoSearchResult.motor || '—'}
                      </td>
                    </tr>
                    <tr>
                      <td style={{ padding: '0.35rem 0', color: '#64748B' }}>Sucursal</td>
                      <td style={{ padding: '0.35rem 0', fontWeight: 600 }}>{motoSearchResult.dealership}</td>
                    </tr>
                    <tr>
                      <td style={{ padding: '0.35rem 0', color: '#64748B' }}>Estado actual</td>
                      <td style={{ padding: '0.35rem 0', fontWeight: 600 }}>{motoSearchResult.status}</td>
                    </tr>
                    <tr>
                      <td style={{ padding: '0.35rem 0', color: '#64748B' }}>Efecto</td>
                      <td style={{ padding: '0.35rem 0', color: '#DC2626', fontWeight: 600 }}>
                        Estado → rechazada
                        {motoSearchResult.status === 'in_stock_reserved' ? ' · Reservación vinculada → activa' : ''}
                      </td>
                    </tr>
                  </tbody>
                </table>
              )}

              {/* ── TRANSFERIR summary ── */}
              {operationType === 'transferir' && transferRecord && (
                <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: '1rem', fontSize: '0.88rem' }}>
                  <tbody>
                    <tr>
                      <td style={{ padding: '0.35rem 0', color: '#64748B', width: '45%' }}>Operación</td>
                      <td style={{ padding: '0.35rem 0', fontWeight: 600 }}>Transferir Datos de Pago</td>
                    </tr>
                    <tr>
                      <td style={{ padding: '0.35rem 0', color: '#64748B' }}>De</td>
                      <td style={{ padding: '0.35rem 0', fontWeight: 600 }}>
                        {transferOriginClient?.nombre_completo}
                        <span style={{ color: '#94A3B8', fontWeight: 400, marginLeft: '0.4rem' }}>({transferOriginClient?.rfc})</span>
                      </td>
                    </tr>
                    <tr>
                      <td style={{ padding: '0.35rem 0', color: '#64748B' }}>Hacia</td>
                      <td style={{ padding: '0.35rem 0', fontWeight: 600 }}>
                        {transferDestClient?.nombre_completo}
                        <span style={{ color: '#94A3B8', fontWeight: 400, marginLeft: '0.4rem' }}>({transferDestClient?.rfc})</span>
                      </td>
                    </tr>
                    <tr>
                      <td style={{ padding: '0.35rem 0', color: '#64748B' }}>Registro</td>
                      <td style={{ padding: '0.35rem 0', fontWeight: 600 }}>
                        {transferRecord.type === 'reservation'
                          ? `Reservación — ${transferRecord.data.model_name} ${transferRecord.data.year}`
                          : `Venta${transferRecord.data.motorcycle ? ` — ${transferRecord.data.motorcycle.model_name} ${transferRecord.data.motorcycle.year}` : ''}`
                        }
                      </td>
                    </tr>
                    <tr>
                      <td style={{ padding: '0.35rem 0', color: '#64748B' }}>Efecto</td>
                      <td style={{ padding: '0.35rem 0', color: '#1D4ED8', fontWeight: 600 }}>
                        Cliente del registro → {transferDestClient?.nombre_completo}
                      </td>
                    </tr>
                  </tbody>
                </table>
              )}

              <hr className="card-divider" />

              <div style={{ fontSize: '0.85rem', marginBottom: '1rem' }}>
                <span style={{ color: '#64748B' }}>Motivo: </span>
                <span style={{ fontStyle: 'italic' }}>{reason}</span>
              </div>

              <div className="btn-row" style={{ marginTop: '1rem' }}>
                <button className="btn-secondary" onClick={goBack}>← Volver</button>
                <button
                  className="btn-primary"
                  disabled={submitting}
                  onClick={handleSubmit}
                >
                  {submitting ? 'Procesando...' : 'Confirmar Operación'}
                </button>
              </div>
            </div>
          )}

        </div>
      </div>
    </>
  )
}
