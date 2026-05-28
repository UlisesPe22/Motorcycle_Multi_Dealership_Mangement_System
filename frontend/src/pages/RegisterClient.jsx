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
  const [email, setEmail]         = useState('')
  const [phone, setPhone]         = useState('')

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
    setStatusMsg('Procesando registro de cliente...')
    try {
      const formData = new FormData()
      formData.append('front_file', frontFile)
      formData.append('back_file', backFile)
      formData.append('email', email.trim().toLowerCase())
      formData.append('phone', phone.trim())
      const resp = await api.post('/clients/register', formData)
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
              onClick={() => { setResult(null); setFrontFile(null); setBackFile(null); setFrontPreview(null); setBackPreview(null); setEmail(''); setPhone('') }}
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
          <CardSection title="Datos de Contacto">
            <div className="upload-label">Correo Electrónico</div>
            <input
              type="email"
              placeholder="correo@ejemplo.com"
              value={email}
              onChange={e => setEmail(e.target.value)}
              required
            />
            <div className="upload-label">Teléfono</div>
            <input
              type="text"
              placeholder="5512345678"
              value={phone}
              onChange={e => setPhone(e.target.value)}
              required
            />
          </CardSection>
        </div>

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
            disabled={!frontFile || !backFile || !email.trim() || !phone.trim()}
            onClick={handleSubmit}
          >
            Enviar y Procesar
          </button>
        </div>
      </div>
    </>
  )
}
