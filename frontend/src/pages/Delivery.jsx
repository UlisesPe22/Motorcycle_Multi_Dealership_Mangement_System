import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../api'
import PageHeader from '../components/PageHeader'
import StatusBox from '../components/StatusBox'
import CardSection from '../components/CardSection'

export default function Delivery() {
  const navigate = useNavigate()
  const [dealerships, setDealerships]     = useState([])
  const [selectedDealership, setSelected] = useState(null)
  const [declaredCount, setCount]         = useState(1)
  const [deliveryFile, setFile]           = useState(null)
  const [filePreview, setPreview]         = useState(null)
  const [loading, setLoading]             = useState(false)
  const [result, setResult]               = useState(null)
  const [fetchError, setFetchError]       = useState(null)

  useEffect(() => {
    api.get('/delivery-confirmations/dealerships')
      .then(r => {
        setDealerships(r.data)
        if (r.data.length > 0) setSelected(r.data[0])
      })
      .catch(() => setFetchError('No se pudieron cargar las sucursales.'))
  }, [])

  function handleFileChange(e) {
    const file = e.target.files[0] ?? null
    setFile(file)
    if (file && file.type !== 'application/pdf') {
      setPreview(URL.createObjectURL(file))
    } else {
      setPreview(null)
    }
  }

  async function handleSubmit() {
    setLoading(true)
    try {
      const fd = new FormData()
      fd.append('file', deliveryFile)
      fd.append('declared_count', String(declaredCount))
      fd.append('dealership_id', String(selectedDealership.dealership_id))
      const resp = await api.post('/delivery-confirmations/upload', fd)
      if (!resp.data.success) throw new Error(resp.data.message)
      setResult({ success: true, message: resp.data.message })
    } catch (e) {
      setResult({ success: false, message: e.response?.data?.detail ?? e.message })
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <>
        <PageHeader section="Entregas" title="Registrar Entrega" />
        <div className="col-center">
          <StatusBox type="loading" title="Procesando documento..." message="Procesando documento de entrega con IA…" />
        </div>
      </>
    )
  }

  if (result) {
    return (
      <>
        <PageHeader section="Entregas" title="Registrar Entrega" />
        <div className="col-center">
          <StatusBox
            type={result.success ? 'success' : 'error'}
            title={result.success ? 'Entrega Confirmada' : 'Error en la Entrega'}
            message={result.message}
          />
          <div className="btn-row" style={{ justifyContent: 'center' }}>
            <button className="btn-primary" onClick={() => { setResult(null); setFile(null) }}>
              Nueva Carga
            </button>
            <button className="btn-secondary" onClick={() => navigate('/')}>Volver al Panel</button>
          </div>
        </div>
      </>
    )
  }

  return (
    <>
      <PageHeader section="Entregas" title="Registrar Entrega" />
      <div className="col-center">
        {fetchError && <div className="alert-error">{fetchError}</div>}

        <div className="bi-card">
          <CardSection title="Sucursal">
            {dealerships.length > 0 ? (
              <select
                value={selectedDealership?.dealership_id ?? ''}
                onChange={e => {
                  const d = dealerships.find(x => String(x.dealership_id) === e.target.value)
                  setSelected(d ?? null)
                }}
              >
                {dealerships.map(d => (
                  <option key={d.dealership_id} value={d.dealership_id}>{d.name}</option>
                ))}
              </select>
            ) : (
              <div className="alert-error">No se pudieron cargar las sucursales.</div>
            )}
          </CardSection>

          <hr className="card-divider" />

          <CardSection title="Total de Motocicletas">
            <div className="upload-label">Cantidad declarada en el documento de entrega</div>
            <input
              type="number"
              min="1"
              max="100"
              value={declaredCount}
              onChange={e => setCount(Math.max(1, parseInt(e.target.value) || 1))}
              style={{ maxWidth: '120px' }}
            />
          </CardSection>

          <hr className="card-divider" />

          <CardSection title="Documento de Entrega">
            <div className="upload-label">Foto o PDF del documento de entrega física</div>
            <input
              type="file"
              accept=".pdf,.jpg,.jpeg,.png"
              onChange={handleFileChange}
            />
            {deliveryFile && deliveryFile.type === 'application/pdf' && (
              <div className="alert-info" style={{ marginTop: '0.5rem' }}>
                PDF cargado: {deliveryFile.name}
              </div>
            )}
            {filePreview && (
              <img src={filePreview} alt="Vista previa" className="img-preview" />
            )}
          </CardSection>
        </div>

        <div className="btn-row">
          <button className="btn-secondary" onClick={() => navigate('/')}>Volver</button>
          <button
            className="btn-primary"
            disabled={!deliveryFile || !selectedDealership}
            onClick={handleSubmit}
          >
            Enviar y Procesar
          </button>
        </div>
      </div>
    </>
  )
}
