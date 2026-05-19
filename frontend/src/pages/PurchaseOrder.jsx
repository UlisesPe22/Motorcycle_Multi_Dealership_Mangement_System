import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../api'
import PageHeader from '../components/PageHeader'
import StatusBox from '../components/StatusBox'
import CardSection from '../components/CardSection'

export default function PurchaseOrder() {
  const navigate = useNavigate()
  const [pdfFile, setPdfFile]     = useState(null)
  const [loading, setLoading]     = useState(false)
  const [result, setResult]       = useState(null)   // { success, message }

  async function handleSubmit() {
    setLoading(true)
    try {
      const eventResp = await api.post('/events/', null, {
        params: { event_type_name: 'purchase_order' },
      })
      const submissions = eventResp.data.submissions
      const sub = submissions.find(
        s => s.slot_name === 'purchase_order_table' || s.slot_name === 'order_table'
      )
      if (!sub) throw new Error('No se encontró el slot de pedido de compra.')

      const fd = new FormData()
      fd.append('file', pdfFile)
      const resp = await api.post(`/submissions/${sub.submission_id}/upload`, fd)
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
        <PageHeader section="Inventario" title="Registrar Orden de Compra" />
        <div className="col-center">
          <StatusBox type="loading" title="Procesando documento..." message="Procesando PDF con IA…" />
        </div>
      </>
    )
  }

  if (result) {
    return (
      <>
        <PageHeader section="Inventario" title="Registrar Orden de Compra" />
        <div className="col-center">
          <StatusBox
            type={result.success ? 'success' : 'error'}
            title={result.success ? 'Pedido Registrado' : 'Error en el Pedido'}
            message={result.message}
          />
          <div className="btn-row" style={{ justifyContent: 'center' }}>
            <button className="btn-primary" onClick={() => { setResult(null); setPdfFile(null) }}>
              Nueva Carga
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
      <PageHeader section="Inventario" title="Registrar Orden de Compra" />
      <div className="col-center">
        <div className="bi-card">
          <CardSection title="Documento de Pedido de Compra">
            <div className="upload-label">Archivo PDF del pedido de compra</div>
            <input
              type="file"
              accept=".pdf"
              onChange={e => setPdfFile(e.target.files[0] ?? null)}
            />
            {pdfFile && (
              <div className="alert-info" style={{ marginTop: '0.5rem' }}>
                Archivo cargado: {pdfFile.name}
              </div>
            )}
          </CardSection>
        </div>
        <div className="btn-row">
          <button className="btn-secondary" onClick={() => navigate('/')}>Volver</button>
          <button
            className="btn-primary"
            disabled={!pdfFile}
            onClick={handleSubmit}
          >
            Enviar y Procesar
          </button>
        </div>
      </div>
    </>
  )
}
