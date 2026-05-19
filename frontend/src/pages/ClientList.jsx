import { useState, useEffect } from 'react'
import PageHeader from '../components/PageHeader'
import api from '../api'

function ClientCard({ client }) {
  const [open, setOpen] = useState(false)

  return (
    <div className="client-card">
      <button className="client-card-header" onClick={() => setOpen(o => !o)}>
        <span>{client.nombre_completo} &nbsp;·&nbsp; CURP: {client.curp}</span>
        <span style={{ fontSize: '0.75rem', color: '#94A3B8' }}>{open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <div className="client-card-body">
          <div className="client-images">
            <img
              src={`/api/clients/image/${client.client_id}/front`}
              alt="Frente del INE"
              className="img-preview"
              onError={e => { e.target.style.display = 'none' }}
            />
            <img
              src={`/api/clients/image/${client.client_id}/back`}
              alt="Reverso del INE"
              className="img-preview"
              onError={e => { e.target.style.display = 'none' }}
            />
          </div>
          <div className="client-info">
            {[
              ['ID Cliente',          client.client_id],
              ['Nombre Completo',      client.nombre_completo],
              ['CURP',                client.curp],
              ['Clave de Elector',    client.clave_de_elector],
              ['Fecha de Nacimiento', client.fecha_nacimiento],
              ['Domicilio',           client.domicilio],
              ['Registrado',          client.registered_at],
            ].map(([label, value]) => (
              <div key={label}>
                <div className="field-label">{label}</div>
                <div className="field-value">{value || '—'}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default function ClientList() {
  const [clients, setClients] = useState([])
  const [error, setError]     = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get('/clients/')
      .then(r => setClients(r.data))
      .catch(() => setError('No se puede conectar al servidor.'))
      .finally(() => setLoading(false))
  }, [])

  return (
    <>
      <PageHeader section="Clientes" title="Buscar Cliente" />

      {loading && <div className="alert-info">Cargando clientes...</div>}
      {error   && <div className="alert-error">{error}</div>}

      {!loading && !error && clients.length === 0 && (
        <div className="alert-info">No hay clientes registrados aún.</div>
      )}

      {clients.length > 0 && (
        <>
          <div className="count-tag">{clients.length} cliente(s) registrado(s)</div>
          {clients.map(c => <ClientCard key={c.client_id} client={c} />)}
        </>
      )}
    </>
  )
}
