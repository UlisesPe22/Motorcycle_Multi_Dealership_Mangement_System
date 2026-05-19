import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../api'
import PageHeader from '../components/PageHeader'
import StatusBox from '../components/StatusBox'
import CardSection from '../components/CardSection'

export default function RegisterClient() {
  const navigate = useNavigate()
  const [frontFile, setFrontFile] = useState(null)
  const [backFile, setBackFile]   = useState(null)
  const [frontPreview, setFrontPreview] = useState(null)
  const [backPreview, setBackPreview]   = useState(null)
  const [loading, setLoading]     = useState(false)
  const [statusMsg, setStatusMsg] = useState('')
  const [result, setResult]       = useState(null)

  function handleFrontChange(e) {
    const file = e.target.files[0] ?? null
    setFrontFile(file)
    setFrontPreview(file ? URL.createObjectURL(file) : null)
  }

  function handleBackChange(e) {
    const file = e.target.files[0] ?? null
    setBackFile(file)
    setBackPreview(file ? URL.createObjectURL(file) : null)
  }

  async function handleSubmit() {
    setLoading(true)
    setStatusMsg('Creando evento de registro...')
    try {
      const eventResp = await api.post('/events/', null, {
        params: { event_type_name: 'client_registration' },
      })
      const submissions  = eventResp.data.submissions
      const frontSubId = submissions.find(s => s.slot_name === 'id_front')?.submission_id
      const backSubId  = submissions.find(s => s.slot_name === 'id_back')?.submission_id
      if (!frontSubId || !backSubId) throw new Error('Slots de INE no encontrados.')

      setStatusMsg('Validando frente del INE con IA...')
      const frontFd = new FormData()
      frontFd.append('file', frontFile)
      const frontResp = await api.post(`/submissions/${frontSubId}/upload`, frontFd)
      if (!frontResp.data.success) throw new Error(frontResp.data.message)

      setStatusMsg('Validando reverso del INE con IA...')
      const backFd = new FormData()
      backFd.append('file', backFile)
      const backResp = await api.post(`/submissions/${backSubId}/upload`, backFd)
      if (!backResp.data.success) throw new Error(backResp.data.message)

      setResult({ success: true, message: backResp.data.message })
    } catch (e) {
      setResult({ success: false, message: e.response?.data?.detail ?? e.message })
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <>
        <PageHeader section="Clientes" title="Registrar Cliente" />
        <div className="col-center">
          <StatusBox type="loading" title="Procesando documento..." message={statusMsg} />
        </div>
      </>
    )
  }

  if (result) {
    return (
      <>
        <PageHeader section="Clientes" title="Registrar Cliente" />
        <div className="col-center">
          <StatusBox
            type={result.success ? 'success' : 'error'}
            title={result.success ? 'Registro Exitoso' : 'Registro Fallido'}
            message={result.message}
          />
          <div className="btn-row" style={{ justifyContent: 'center' }}>
            <button
              className="btn-primary"
              onClick={() => { setResult(null); setFrontFile(null); setBackFile(null); setFrontPreview(null); setBackPreview(null) }}
            >
              Nuevo Registro
            </button>
            <button className="btn-secondary" onClick={() => navigate('/')}>
              Volver al Panel
            </button>
          </div>
        </div>
      </>
    )
  }

  return (
    <>
      <PageHeader section="Clientes" title="Registrar Cliente" />
      <div className="col-center">
        <div className="bi-card">
          <CardSection title="Frente del INE">
            <div className="upload-label">Parte frontal de la credencial de elector</div>
            <input
              type="file"
              accept=".jpg,.jpeg,.png"
              onChange={handleFrontChange}
            />
            {frontPreview && (
              <img src={frontPreview} alt="Vista previa — Frente" className="img-preview" />
            )}
          </CardSection>

          <hr className="card-divider" />

          <CardSection title="Reverso del INE">
            <div className="upload-label">Parte trasera de la credencial de elector</div>
            <input
              type="file"
              accept=".jpg,.jpeg,.png"
              onChange={handleBackChange}
            />
            {backPreview && (
              <img src={backPreview} alt="Vista previa — Reverso" className="img-preview" />
            )}
          </CardSection>
        </div>

        <div className="btn-row">
          <button className="btn-secondary" onClick={() => navigate('/')}>Volver</button>
          <button
            className="btn-primary"
            disabled={!frontFile || !backFile}
            onClick={handleSubmit}
          >
            Enviar y Procesar
          </button>
        </div>
      </div>
    </>
  )
}
