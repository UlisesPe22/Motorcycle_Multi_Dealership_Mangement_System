import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../api'
import PageHeader from '../components/PageHeader'
import StatusBox from '../components/StatusBox'
import CardSection from '../components/CardSection'

function fmt(n) {
  return Number(n).toLocaleString('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

export default function Sale() {
  const navigate = useNavigate()

  const [clients, setClients]           = useState([])
  const [institutions, setInstitutions] = useState([])
  const [fetchError, setFetchError]     = useState(null)

  const [saleType, setSaleType]         = useState('contado')
  const [selectedClientId, setClientId] = useState('')
  const [motos, setMotos]               = useState([])
  const [motosLoading, setMotosLoading] = useState(false)
  const [selectedMotoId, setMotoId]     = useState('')
  const [paymentMethod, setPayMethod]   = useState('transferencia')

  const [downpayment, setDownpayment]         = useState('')
  const [institutionId, setInstitutionId]     = useState('')
  const [paymentBank, setPaymentBank]         = useState('')
  const [referenceName, setReferenceName]     = useState('')
  const [referencePhone, setReferencePhone]   = useState('')
  const [referenceRelation, setReferenceRelation] = useState('')
  const [colonia, setColonia]                 = useState('')
  const [cp, setCp]                           = useState('')
  const [municipio, setMunicipio]             = useState('')
  const [estado, setEstado]                   = useState('')

  const [loading, setLoading]       = useState(false)
  const [result, setResult]         = useState(null)
  const [lockedMotoId, setLockedMotoId] = useState(null)

  useEffect(() => {
    Promise.all([
      api.get('/sales/clients'),
      api.get('/sales/credit-institutions'),
    ])
      .then(([c, i]) => {
        setClients(c.data)
        setInstitutions(i.data)
      })
      .catch(() => setFetchError('No se puede conectar al servidor.'))
  }, [])

  // Unlock current lock when client changes
  useEffect(() => {
    if (lockedMotoId) {
      api.post('/sales/unlock-motorcycle', {
        motorcycle_id: parseInt(lockedMotoId)
      }).catch(() => {})
      setLockedMotoId(null)
      setMotoId('')
    }
  }, [selectedClientId]) // eslint-disable-line react-hooks/exhaustive-deps

  // Unlock on page leave
  useEffect(() => {
    return () => {
      if (lockedMotoId) {
        api.post('/sales/unlock-motorcycle', {
          motorcycle_id: parseInt(lockedMotoId)
        }).catch(() => {})
      }
    }
  }, [lockedMotoId])

  useEffect(() => {
    if (!selectedClientId) { setMotos([]); setMotoId(''); return }
    setMotosLoading(true);
    (async () => {
      try {
        const r    = await api.get(`/sales/motorcycles?client_id=${selectedClientId}`)
        const data = r.data
        setMotos(data)
        const pre = data.find(m => m.pre_selected)
        if (pre) {
          const preId = String(pre.motorcycle_id)
          try {
            const res = await api.post('/sales/lock-motorcycle', {
              motorcycle_id: pre.motorcycle_id,
              previous_motorcycle_id: null,
            })
            if (res.data.success) {
              setLockedMotoId(preId)
              setMotoId(preId)
            } else {
              setMotoId('')
            }
          } catch {
            setMotoId('')
          }
        } else {
          setMotoId('')
        }
      } catch {
        setMotos([])
      } finally {
        setMotosLoading(false)
      }
    })()
  }, [selectedClientId])

  const selectedMoto = motos.find(m => String(m.motorcycle_id) === selectedMotoId) ?? null
  const motoPrice    = selectedMoto?.price ?? null

  const dp = parseFloat(downpayment) || 0

  const sendDisabled = (() => {
    if (!selectedClientId || !selectedMotoId) return true
    if (saleType === 'credito') {
      if (dp <= 0) return true
      if (!institutionId) return true
      if (!referenceName.trim() || !referencePhone.trim() || !referenceRelation.trim()) return true
      if (!colonia.trim() || !cp.trim() || !municipio.trim() || !estado.trim()) return true
    }
    return false
  })()

  function clearState() {
    setLockedMotoId(null)
    setSaleType('contado'); setClientId(''); setMotos([]); setMotoId('')
    setPayMethod('transferencia'); setDownpayment(''); setInstitutionId('')
    setPaymentBank(''); setReferenceName(''); setReferencePhone('')
    setReferenceRelation(''); setColonia(''); setCp(''); setMunicipio('')
    setEstado(''); setResult(null)
  }

  async function handleSubmit() {
    setLoading(true)
    try {
      const resp = await api.post('/sales/create', {
        client_id:              Number(selectedClientId),
        motorcycle_id:          Number(selectedMotoId),
        sale_type:              saleType,
        payment_method:         paymentMethod,
        payment_downpayment:    saleType === 'credito' ? dp : null,
        payment_institution_id: saleType === 'credito' && institutionId ? Number(institutionId) : null,
        payment_bank:           saleType === 'credito' ? paymentBank || null : null,
        reference_name:         saleType === 'credito' ? referenceName || null : null,
        reference_phone:        saleType === 'credito' ? referencePhone || null : null,
        reference_relation:     saleType === 'credito' ? referenceRelation || null : null,
        buyer_colonia:          saleType === 'credito' ? colonia || null : null,
        buyer_cp:               saleType === 'credito' ? cp || null : null,
        buyer_municipio:        saleType === 'credito' ? municipio || null : null,
        buyer_estado:           saleType === 'credito' ? estado || null : null,
      })
      const data = resp.data
      if (!data.success) throw new Error(data.message)
      setResult({
        success:         true,
        message:         data.message,
        contractId:      data.contract_id,
        contractNumber:  data.contract_number,
        hasSolicitud:    data.has_solicitud ?? false,
      })
    } catch (e) {
      setResult({ success: false, message: e.response?.data?.detail ?? e.message })
    } finally {
      setLoading(false)
    }
  }

  async function downloadDoc(contractId, type, contractNumber) {
    try {
      const resp = await api.get(`/sales/${contractId}/download/${type}`, {
        responseType: 'blob',
      })
      const url  = URL.createObjectURL(resp.data)
      const link = document.createElement('a')
      link.href  = url
      link.download = `${contractNumber}_${type}.docx`
      link.click()
      URL.revokeObjectURL(url)
    } catch {
      alert(`No se pudo descargar el ${type}.`)
    }
  }

  if (loading) {
    return (
      <>
        <PageHeader section="Ventas" title="Iniciar Venta" />
        <div className="col-center">
          <StatusBox type="loading" title="Registrando venta..." message="Por favor espera…" />
        </div>
      </>
    )
  }

  if (result) {
    return (
      <>
        <PageHeader section="Ventas" title="Iniciar Venta" />
        <div className="col-center">
          <StatusBox
            type={result.success ? 'success' : 'error'}
            title={result.success ? 'Venta Registrada' : 'Error en la Venta'}
            message={result.success ? `Contrato: ${result.contractNumber}<br>${result.message}` : result.message}
          />
          {result.success && (
            <div className="btn-row" style={{ justifyContent: 'center' }}>
              <button
                className="btn-download"
                onClick={() => downloadDoc(result.contractId, 'contrato', result.contractNumber)}
              >
                Descargar Contrato
              </button>
              {result.hasSolicitud && (
                <button
                  className="btn-download"
                  onClick={() => downloadDoc(result.contractId, 'solicitud', result.contractNumber)}
                >
                  Descargar Solicitud de Crédito
                </button>
              )}
            </div>
          )}
          <div className="btn-row" style={{ justifyContent: 'center' }}>
            <button className="btn-primary" onClick={() => { clearState(); navigate('/') }}>
              OK — Volver al Menú Principal
            </button>
          </div>
        </div>
      </>
    )
  }

  return (
    <>
      <PageHeader section="Ventas" title="Iniciar Venta" />
      {fetchError && <div className="alert-error">{fetchError}</div>}
      <div className="col-center">
        <div className="bi-card">

          <CardSection title="Tipo de Venta">
            <div className="radio-group">
              {[['contado', 'Al Contado'], ['credito', 'A Crédito']].map(([val, label]) => (
                <label key={val} className={`radio-option${saleType === val ? ' selected' : ''}`}>
                  <input
                    type="radio"
                    name="saleType"
                    value={val}
                    checked={saleType === val}
                    onChange={() => setSaleType(val)}
                  />
                  {label}
                </label>
              ))}
            </div>
          </CardSection>

          <hr className="card-divider" />

          <CardSection title="Cliente">
            <div className="upload-label">Selecciona el cliente que realiza la compra</div>
            <select value={selectedClientId} onChange={e => setClientId(e.target.value)}>
              <option value="">Seleccionar cliente...</option>
              {clients.map(c => (
                <option key={c.client_id} value={c.client_id}>
                  {c.nombre_completo} — CURP: {c.curp}
                </option>
              ))}
            </select>
          </CardSection>

          <hr className="card-divider" />

          <CardSection title="Motocicleta">
            {!selectedClientId ? (
              <div className="caption">Selecciona un cliente primero.</div>
            ) : motosLoading ? (
              <div className="caption">Cargando motocicletas...</div>
            ) : motos.length === 0 ? (
              <div className="caption">No hay motocicletas disponibles para este cliente.</div>
            ) : (
              <>
                <select value={selectedMotoId} onChange={async (e) => {
                  const newMotoId  = e.target.value
                  const prevMotoId = lockedMotoId

                  if (newMotoId === '') {
                    if (prevMotoId) {
                      try {
                        await api.post('/sales/unlock-motorcycle', {
                          motorcycle_id: parseInt(prevMotoId)
                        })
                      } catch (err) {
                        console.error('Unlock failed:', err)
                      }
                      setLockedMotoId(null)
                    }
                    setMotoId('')
                  } else {
                    try {
                      const res = await api.post('/sales/lock-motorcycle', {
                        motorcycle_id:          parseInt(newMotoId),
                        previous_motorcycle_id: prevMotoId ? parseInt(prevMotoId) : null,
                      })
                      if (res.data.success) {
                        setLockedMotoId(newMotoId)
                        setMotoId(newMotoId)
                      } else {
                        alert(res.data.message)
                        setMotoId('')
                        setLockedMotoId(null)
                      }
                    } catch (err) {
                      console.error('Lock failed:', err)
                    }
                  }
                }}>
                  <option value="">Seleccionar motocicleta...</option>
                  {motos.map(m => (
                    <option key={m.motorcycle_id} value={m.motorcycle_id}>
                      {m.pre_selected ? '⭐ ' : ''}{m.model} {m.year} — {m.color} — {m.dealership} — ${fmt(m.price)}
                    </option>
                  ))}
                </select>
                {motoPrice !== null && (
                  <div className="caption" style={{ marginTop: '0.4rem' }}>
                    Precio: ${fmt(motoPrice)}
                  </div>
                )}
              </>
            )}
          </CardSection>

          <hr className="card-divider" />

          <CardSection title="Método de Pago">
            <select value={paymentMethod} onChange={e => setPayMethod(e.target.value)}>
              <option value="transferencia">Transferencia</option>
              <option value="efectivo">Efectivo</option>
            </select>
          </CardSection>

          {saleType === 'credito' && (
            <>
              <hr className="card-divider" />
              <CardSection title="Datos de Crédito">
                <div className="upload-label">Enganche</div>
                <input
                  type="number"
                  min="0.01"
                  step="100"
                  value={downpayment}
                  onChange={e => setDownpayment(e.target.value)}
                  style={{ maxWidth: '200px' }}
                />
                {motoPrice !== null && dp > 0 && (
                  <div className="caption" style={{ marginTop: '0.3rem' }}>
                    Pendiente: ${fmt(motoPrice - dp)}
                    {dp >= motoPrice && (
                      <span className="alert-warning" style={{ marginLeft: '0.5rem', padding: '0.1rem 0.4rem' }}>
                        El enganche es mayor o igual al precio.
                      </span>
                    )}
                  </div>
                )}

                <div className="upload-label" style={{ marginTop: '0.75rem' }}>Institución Financiera</div>
                <select value={institutionId} onChange={e => setInstitutionId(e.target.value)}>
                  <option value="">Seleccionar institución...</option>
                  {institutions.map(i => (
                    <option key={i.credit_institution_id} value={i.credit_institution_id}>
                      {i.name}
                    </option>
                  ))}
                </select>

                <div className="upload-label" style={{ marginTop: '0.75rem' }}>Banco</div>
                <input
                  type="text"
                  placeholder="Nombre del banco"
                  value={paymentBank}
                  onChange={e => setPaymentBank(e.target.value)}
                />
              </CardSection>

              <hr className="card-divider" />
              <CardSection title="Referencia Personal">
                <div className="form-row-3">
                  <div className="form-field">
                    <label>Nombre</label>
                    <input type="text" value={referenceName} onChange={e => setReferenceName(e.target.value)} />
                  </div>
                  <div className="form-field">
                    <label>Teléfono</label>
                    <input type="text" value={referencePhone} onChange={e => setReferencePhone(e.target.value)} />
                  </div>
                  <div className="form-field">
                    <label>Parentesco</label>
                    <input type="text" value={referenceRelation} onChange={e => setReferenceRelation(e.target.value)} />
                  </div>
                </div>
              </CardSection>

              <hr className="card-divider" />
              <CardSection title="Domicilio del Cliente (para solicitud)">
                <div className="caption" style={{ marginBottom: '0.75rem' }}>
                  Estos datos son necesarios para generar la solicitud de crédito.
                </div>
                <div className="form-row">
                  <div className="form-field">
                    <label>Colonia</label>
                    <input type="text" value={colonia} onChange={e => setColonia(e.target.value)} />
                  </div>
                  <div className="form-field">
                    <label>Código Postal</label>
                    <input type="text" value={cp} onChange={e => setCp(e.target.value)} />
                  </div>
                </div>
                <div className="form-row" style={{ marginTop: '0.5rem' }}>
                  <div className="form-field">
                    <label>Alcaldía / Municipio</label>
                    <input type="text" value={municipio} onChange={e => setMunicipio(e.target.value)} />
                  </div>
                  <div className="form-field">
                    <label>Estado</label>
                    <input type="text" value={estado} onChange={e => setEstado(e.target.value)} />
                  </div>
                </div>
              </CardSection>
            </>
          )}
        </div>

        <div className="btn-row">
          <button className="btn-secondary" onClick={() => { clearState(); navigate('/') }}>
            ← Volver
          </button>
          <button className="btn-primary" disabled={sendDisabled} onClick={handleSubmit}>
            Registrar Venta
          </button>
        </div>
      </div>
    </>
  )
}
