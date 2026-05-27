import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../api'
import PageHeader from '../components/PageHeader'
import StatusBox from '../components/StatusBox'
import CardSection from '../components/CardSection'

export default function RegisterVendedor() {
  const navigate = useNavigate()

  const [name, setName]               = useState('')
  const [phone, setPhone]             = useState('')
  const [dealership_id, setDealershipId] = useState('')
  const [dealerships, setDealerships] = useState([])
  const [fetchError, setFetchError]   = useState(null)

  const [loading, setLoading] = useState(false)
  const [ran, setRan]         = useState(false)
  const [success, setSuccess] = useState(false)
  const [message, setMessage] = useState('')

  useEffect(() => {
    api.get('/registrar/dealerships')
      .then(r => setDealerships(r.data))
      .catch(() => setFetchError('No se puede conectar al servidor.'))
  }, [])

  function resetAll() {
    setName(''); setPhone(''); setDealershipId('')
    setRan(false); setSuccess(false); setMessage('')
  }

  async function handleSubmit() {
    setLoading(true)
    try {
      const resp = await api.post('/registrar/vendedor', {
        name:          name.trim(),
        phone:         phone.trim(),
        dealership_id: parseInt(dealership_id),
      })
      const result = resp.data
      setRan(true)
      setSuccess(result.success === true)
      setMessage(result.message)
    } catch (e) {
      setRan(true)
      setSuccess(false)
      setMessage(e.response?.data?.detail ?? e.message)
    } finally {
      setLoading(false)
    }
  }

  const sendDisabled = !name.trim() || !phone.trim() || !dealership_id

  // ── Loading ──────────────────────────────────────────────────────────── //
  if (loading) {
    return (
      <>
        <PageHeader section="Vendedores" title="Registrar Vendedor" />
        <div className="col-center">
          <StatusBox type="loading" title="Registrando vendedor..." message="Por favor espera…" />
        </div>
      </>
    )
  }

  // ── Result ───────────────────────────────────────────────────────────── //
  if (ran) {
    return (
      <>
        <PageHeader section="Vendedores" title="Registrar Vendedor" />
        <div className="col-center">
          <StatusBox
            type={success ? 'success' : 'error'}
            title={success ? 'Vendedor Registrado' : 'Error al Registrar'}
            message={message}
          />
          <div className="btn-row" style={{ justifyContent: 'center' }}>
            {success ? (
              <button className="btn-primary" onClick={resetAll}>
                Registrar otro vendedor
              </button>
            ) : (
              <button className="btn-primary" onClick={() => setRan(false)}>
                Intentar de nuevo
              </button>
            )}
          </div>
        </div>
      </>
    )
  }

  // ── Form ─────────────────────────────────────────────────────────────── //
  return (
    <>
      <PageHeader section="Vendedores" title="Registrar Vendedor" />
      {fetchError && <div className="alert-error">{fetchError}</div>}
      <div className="col-center">
        <div className="bi-card">

          <CardSection title="Nombre">
            <input
              type="text"
              placeholder="Nombre completo del vendedor"
              value={name}
              onChange={e => setName(e.target.value)}
            />
          </CardSection>

          <hr className="card-divider" />

          <CardSection title="Teléfono">
            <input
              type="text"
              placeholder="Número de teléfono"
              value={phone}
              onChange={e => setPhone(e.target.value)}
            />
          </CardSection>

          <hr className="card-divider" />

          <CardSection title="Sucursal">
            <select value={dealership_id} onChange={e => setDealershipId(e.target.value)}>
              <option value="">Seleccionar sucursal...</option>
              {dealerships.map(d => (
                <option key={d.dealership_id} value={d.dealership_id}>{d.name}</option>
              ))}
            </select>
          </CardSection>

        </div>

        <div className="btn-row">
          <button className="btn-secondary" onClick={() => navigate('/')}>
            ← Volver
          </button>
          <button className="btn-primary" disabled={sendDisabled} onClick={handleSubmit}>
            Registrar Vendedor
          </button>
        </div>
      </div>
    </>
  )
}
