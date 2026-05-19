import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../api'
import PageHeader from '../components/PageHeader'
import StatusBox from '../components/StatusBox'
import CardSection from '../components/CardSection'

export default function Reservation() {
  const navigate = useNavigate()
  const [dealerships, setDealerships] = useState([])
  const [clients, setClients]         = useState([])
  const [models, setModels]           = useState([])
  const [fetchError, setFetchError]   = useState(null)

  const [selectedDealershipId, setDealershipId] = useState('')
  const [selectedClientId, setClientId]         = useState('')
  const [selectedModelId, setModelId]           = useState('')
  const [selectedColors, setColors]             = useState([])
  const [depositAmount, setDeposit]             = useState(0)

  const [loading, setLoading] = useState(false)
  const [result, setResult]   = useState(null)

  useEffect(() => {
    Promise.all([
      api.get('/reservations/dealerships'),
      api.get('/reservations/clients'),
      api.get('/reservations/models'),
    ])
      .then(([d, c, m]) => {
        setDealerships(d.data)
        setClients(c.data)
        setModels(m.data)
      })
      .catch(() => setFetchError('No se puede conectar al servidor.'))
  }, [])

  const selectedModel = models.find(m => String(m.model_id) === selectedModelId) ?? null
  const availableColors = selectedModel?.colors ?? []

  function toggleColor(color) {
    setColors(prev =>
      prev.includes(color) ? prev.filter(c => c !== color) : [...prev, color]
    )
  }

  function clearState() {
    setDealershipId(''); setClientId(''); setModelId('')
    setColors([]); setDeposit(0); setResult(null)
  }

  async function handleSubmit() {
    setLoading(true)
    try {
      const resp = await api.post('/reservations/create', {
        client_id:      Number(selectedClientId),
        model_id:       Number(selectedModelId),
        dealership_id:  Number(selectedDealershipId),
        colors:         selectedColors,
        deposit_amount: depositAmount,
      })
      if (!resp.data.success) throw new Error(resp.data.message)
      setResult({
        success: true,
        message: resp.data.message,
        assigned: resp.data.assigned ?? false,
      })
    } catch (e) {
      setResult({ success: false, message: e.response?.data?.detail ?? e.message })
    } finally {
      setLoading(false)
    }
  }

  const sendDisabled =
    !selectedDealershipId || !selectedClientId || !selectedModelId ||
    selectedColors.length === 0 || depositAmount <= 0

  if (loading) {
    return (
      <>
        <PageHeader section="Reservaciones" title="Registrar Reservación" />
        <div className="col-center">
          <StatusBox type="loading" title="Registrando reservación..." message="Por favor espera…" />
        </div>
      </>
    )
  }

  if (result) {
    const extra = result.success
      ? (result.assigned
          ? '<br><small>⭐ Motocicleta en stock asignada automáticamente.</small>'
          : '<br><small>En espera de motocicleta disponible.</small>')
      : ''
    return (
      <>
        <PageHeader section="Reservaciones" title="Registrar Reservación" />
        <div className="col-center">
          <StatusBox
            type={result.success ? 'success' : 'error'}
            title={result.success ? 'Reservación Registrada' : 'Error al Registrar'}
            message={result.message + extra}
          />
          <div className="btn-row" style={{ justifyContent: 'center' }}>
            <button className="btn-primary" onClick={() => navigate('/')}>
              OK — Volver al Menú Principal
            </button>
          </div>
        </div>
      </>
    )
  }

  return (
    <>
      <PageHeader section="Reservaciones" title="Registrar Reservación" />
      {fetchError && <div className="alert-error">{fetchError}</div>}
      <div className="col-center">
        <div className="bi-card">

          <CardSection title="Sucursal">
            <div className="upload-label">Selecciona la sucursal de la reservación</div>
            <select value={selectedDealershipId} onChange={e => setDealershipId(e.target.value)}>
              <option value="">Seleccionar sucursal...</option>
              {dealerships.map(d => (
                <option key={d.dealership_id} value={d.dealership_id}>{d.name}</option>
              ))}
            </select>
          </CardSection>

          <hr className="card-divider" />

          <CardSection title="Cliente">
            <div className="upload-label">Selecciona el cliente que realiza la reservación</div>
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

          <CardSection title="Modelo de Motocicleta">
            <div className="upload-label">Selecciona el modelo que desea reservar</div>
            <select
              value={selectedModelId}
              onChange={e => { setModelId(e.target.value); setColors([]) }}
            >
              <option value="">Seleccionar modelo...</option>
              {models.map(m => (
                <option key={m.model_id} value={m.model_id}>
                  {m.canonical_name} — {m.year}
                </option>
              ))}
            </select>
          </CardSection>

          <hr className="card-divider" />

          <CardSection title="Colores de Preferencia">
            <div className="upload-label">Selecciona uno o más colores en orden de preferencia</div>
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
                {selectedModelId
                  ? 'Este modelo no tiene colores registrados en el catálogo.'
                  : 'Selecciona un modelo para ver colores disponibles.'}
              </div>
            )}
            {selectedColors.length > 0 && (
              <div className="priority-list">
                Prioridad: {selectedColors.map((c, i) => `${i + 1}. ${c}`).join('  ')}
              </div>
            )}
          </CardSection>

          <hr className="card-divider" />

          <CardSection title="Monto de Reservación">
            <div className="upload-label">Monto del depósito de reservación en pesos mexicanos</div>
            <input
              type="number"
              min="0"
              step="100"
              value={depositAmount}
              onChange={e => setDeposit(parseFloat(e.target.value) || 0)}
              style={{ maxWidth: '200px' }}
            />
          </CardSection>
        </div>

        <div className="btn-row">
          <button className="btn-secondary" onClick={() => { clearState(); navigate('/') }}>
            ← Volver
          </button>
          <button className="btn-primary" disabled={sendDisabled} onClick={handleSubmit}>
            Registrar Reservación
          </button>
        </div>
      </div>
    </>
  )
}
