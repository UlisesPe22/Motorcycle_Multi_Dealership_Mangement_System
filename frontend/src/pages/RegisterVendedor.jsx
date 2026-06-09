import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../api'
import { getUser } from '../store/auth'
import PageHeader from '../components/PageHeader'
import StepIndicator from '../components/StepIndicator'
import StatusBox from '../components/StatusBox'
import Toast from '../components/Toast'

// Which roles each role is allowed to register.
const ROLE_OPTIONS = {
  master:  [{ value: 'owner', label: 'Dueño' }, { value: 'manager', label: 'Gerente' }, { value: 'vendor', label: 'Vendedor' }],
  owner:   [{ value: 'manager', label: 'Gerente' }],
  manager: [{ value: 'vendor', label: 'Vendedor' }],
}

const ROLE_LABELS = { master: 'Master', owner: 'Dueño', manager: 'Gerente', vendor: 'Vendedor' }

const OPERATIONS = [
  { value: 'registrar', label: 'Registrar Usuario',   icon: '+', desc: 'Crear una nueva cuenta y enviar credenciales' },
  { value: 'desactivar', label: 'Desactivar Usuario', icon: '⊘', desc: 'Bloquear el acceso de un usuario existente' },
  { value: 'reactivar', label: 'Reactivar Usuario',   icon: '↻', desc: 'Restaurar el acceso de un usuario inactivo' },
]

export default function RegisterVendedor() {
  const navigate = useNavigate()
  const currentUser = getUser()
  const currentRole = currentUser?.role || 'manager'
  const roleOptions = ROLE_OPTIONS[currentRole] || []

  // ── Step control ──────────────────────────────────────────────────────────
  const [step,      setStep]      = useState(1)
  const [operation, setOperation] = useState(null)

  // ── Register form ─────────────────────────────────────────────────────────
  const [name,         setName]         = useState('')
  const [email,        setEmail]        = useState('')
  const [phone,        setPhone]        = useState('')
  const [dealershipId, setDealershipId] = useState('')
  const [role,         setRole]         = useState(roleOptions.length === 1 ? roleOptions[0].value : '')
  const [dealerships,  setDealerships]  = useState([])

  // ── Deactivate / reactivate ───────────────────────────────────────────────
  const [users,          setUsers]          = useState([])
  const [userFilter,     setUserFilter]     = useState('')
  const [selectedUserId, setSelectedUserId] = useState('')

  // ── Submit ────────────────────────────────────────────────────────────────
  const [submitting, setSubmitting] = useState(false)
  const [toast,      setToast]      = useState(null)
  const [done,       setDone]       = useState(null)   // { success, message }

  // ── Load dealerships once ─────────────────────────────────────────────────
  useEffect(() => {
    api.get('/registrar/dealerships')
      .then(r => setDealerships(r.data))
      .catch(() => setToast({ type: 'error', message: 'No se pudieron cargar las sucursales.' }))
  }, [])

  // ── Load users for deactivate / reactivate ────────────────────────────────
  useEffect(() => {
    if (operation === 'desactivar' || operation === 'reactivar') {
      api.get('/registrar/users')
        .then(r => setUsers(r.data))
        .catch(() => setToast({ type: 'error', message: 'No se pudieron cargar los usuarios.' }))
    }
  }, [operation])

  // ── Auto-dismiss error toasts ─────────────────────────────────────────────
  useEffect(() => {
    if (toast?.type === 'error') {
      const t = setTimeout(() => setToast(null), 5000)
      return () => clearTimeout(t)
    }
  }, [toast])

  // ── Derived ───────────────────────────────────────────────────────────────
  const candidates = users.filter(u =>
    operation === 'desactivar' ? u.is_active : !u.is_active
  )
  const filteredUsers = candidates.filter(u =>
    u.name.toLowerCase().includes(userFilter.toLowerCase())
  )
  const selectedUser   = users.find(u => String(u.user_id) === String(selectedUserId))
  const selectedDealer = dealerships.find(d => String(d.dealership_id) === String(dealershipId))

  const step2Valid =
    operation === 'registrar'
      ? !!name.trim() && !!email.trim() && !!dealershipId && !!role
      : !!selectedUserId

  // ── Navigation ────────────────────────────────────────────────────────────
  function chooseOperation(op) {
    setOperation(op)
    if (op === 'registrar') setRole(roleOptions.length === 1 ? roleOptions[0].value : '')
    setStep(2)
  }

  function resetFlow() {
    setOperation(null)
    setName(''); setEmail(''); setPhone(''); setDealershipId('')
    setRole(roleOptions.length === 1 ? roleOptions[0].value : '')
    setUserFilter(''); setSelectedUserId('')
    setDone(null)
    setStep(1)
  }

  function goBack() {
    if (step === 2) { resetFlow() }
    else { setStep(s => s - 1) }
  }

  // ── Submit ────────────────────────────────────────────────────────────────
  async function handleSubmit() {
    setSubmitting(true)
    try {
      let res
      if (operation === 'registrar') {
        res = await api.post('/registrar/usuario', {
          name:          name.trim(),
          email:         email.trim().toLowerCase(),
          phone:         phone.trim() || null,
          dealership_id: parseInt(dealershipId),
          role,
        })
      } else if (operation === 'desactivar') {
        res = await api.post('/registrar/desactivar', { user_id: parseInt(selectedUserId) })
      } else {
        res = await api.post('/registrar/reactivar', { user_id: parseInt(selectedUserId) })
      }
      setDone({ success: true, message: res.data.message })
    } catch (e) {
      setToast({ type: 'error', message: e.response?.data?.detail ?? e.message ?? 'Error al procesar la operación.' })
    } finally {
      setSubmitting(false)
    }
  }

  // ── Result view ───────────────────────────────────────────────────────────
  if (done) {
    return (
      <>
        <PageHeader section="Empleados" title="Gestión de Empleados" />
        <div className="col-center">
          <StatusBox type="success" title="Operación Completada" message={done.message} />
          <div className="btn-row" style={{ justifyContent: 'center' }}>
            <button className="btn-secondary" onClick={() => navigate('/')}>Ir al inicio</button>
            <button className="btn-primary" onClick={resetFlow}>Nueva operación</button>
          </div>
        </div>
      </>
    )
  }

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <>
      <PageHeader section="Empleados" title="Gestión de Empleados" />
      <Toast toast={toast} onClose={() => setToast(null)} />

      <div className="col-center" style={{ maxWidth: '680px' }}>
        <StepIndicator step={step} labels={['Operación', 'Datos', 'Confirmar']} />

        {/* ─── WINDOW 1 — Operation ───────────────────────────────────── */}
        {step === 1 && (
          <div>
            <div className="upload-label" style={{ marginBottom: '1rem', fontSize: '0.95rem' }}>
              Selecciona la operación
            </div>
            <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
              {OPERATIONS.map(({ value, label, icon, desc }) => (
                <button
                  key={value}
                  onClick={() => chooseOperation(value)}
                  style={{
                    flex: '1 1 180px', padding: '1.5rem 1rem',
                    border: '2px solid #E2E8F0', borderRadius: '0.75rem',
                    background: '#FAFAFA', cursor: 'pointer', textAlign: 'center',
                    transition: 'border-color 0.15s, background 0.15s',
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

        {/* ─── WINDOW 2 — Data ────────────────────────────────────────── */}
        {step === 2 && (
          <div className="bi-card">

            {/* ── REGISTRAR ── */}
            {operation === 'registrar' && (
              <>
                <div className="card-section">Datos del Usuario</div>

                <div className="form-field">
                  <label>Nombre completo</label>
                  <input type="text" placeholder="Nombre completo" value={name} onChange={e => setName(e.target.value)} />
                </div>

                <div className="form-field">
                  <label>Correo electrónico</label>
                  <input type="email" placeholder="usuario@ejemplo.com" value={email} onChange={e => setEmail(e.target.value)} />
                </div>

                <div className="form-field">
                  <label>Teléfono (opcional)</label>
                  <input type="text" placeholder="Número de teléfono" value={phone} onChange={e => setPhone(e.target.value)} />
                </div>

                <div className="form-field">
                  <label>Sucursal</label>
                  <select value={dealershipId} onChange={e => setDealershipId(e.target.value)}>
                    <option value="">Seleccionar sucursal...</option>
                    {dealerships.map(d => (
                      <option key={d.dealership_id} value={d.dealership_id}>{d.name}</option>
                    ))}
                  </select>
                </div>

                <div className="form-field">
                  <label>Rol</label>
                  {roleOptions.length === 1 ? (
                    <input type="text" value={roleOptions[0].label} disabled />
                  ) : (
                    <select value={role} onChange={e => setRole(e.target.value)}>
                      <option value="">Seleccionar rol...</option>
                      {roleOptions.map(r => (
                        <option key={r.value} value={r.value}>{r.label}</option>
                      ))}
                    </select>
                  )}
                </div>
              </>
            )}

            {/* ── DESACTIVAR / REACTIVAR ── */}
            {(operation === 'desactivar' || operation === 'reactivar') && (
              <>
                <div className="card-section">
                  {operation === 'desactivar' ? 'Usuario a Desactivar' : 'Usuario a Reactivar'}
                </div>
                <div className="upload-label">Buscar por nombre</div>
                <div style={{ position: 'relative' }}>
                  <input
                    type="text"
                    placeholder="Buscar usuario..."
                    value={userFilter}
                    onChange={e => { setUserFilter(e.target.value); if (selectedUserId) setSelectedUserId('') }}
                    style={{ width: '100%', marginBottom: '0' }}
                  />
                  {userFilter.length > 0 && !selectedUserId && (
                    <div style={{
                      border: '1px solid #E2E8F0', borderRadius: '0 0 0.4rem 0.4rem',
                      maxHeight: '200px', overflowY: 'auto', background: '#fff',
                      boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
                    }}>
                      {filteredUsers.length === 0 ? (
                        <div style={{ padding: '0.6rem 0.75rem', color: '#94A3B8', fontSize: '0.85rem' }}>Sin resultados</div>
                      ) : (
                        filteredUsers.map(u => (
                          <div
                            key={u.user_id}
                            style={{ padding: '0.5rem 0.75rem', cursor: 'pointer', borderBottom: '1px solid #F1F5F9' }}
                            onMouseEnter={e => e.currentTarget.style.background = '#F8FAFC'}
                            onMouseLeave={e => e.currentTarget.style.background = '#fff'}
                            onClick={() => { setSelectedUserId(u.user_id); setUserFilter(u.name) }}
                          >
                            <strong style={{ fontSize: '0.88rem' }}>{u.name}</strong>
                            <span style={{ color: '#94A3B8', fontSize: '0.78rem', marginLeft: '0.5rem' }}>
                              {ROLE_LABELS[u.role] || u.role} · {u.email}
                            </span>
                          </div>
                        ))
                      )}
                    </div>
                  )}
                </div>
                {candidates.length === 0 && (
                  <div className="alert-info" style={{ marginTop: '0.75rem' }}>
                    No hay usuarios {operation === 'desactivar' ? 'activos' : 'inactivos'} para mostrar.
                  </div>
                )}
              </>
            )}

            <div className="btn-row" style={{ marginTop: '1.5rem' }}>
              <button className="btn-secondary" onClick={goBack}>← Volver</button>
              <button className="btn-primary" disabled={!step2Valid} onClick={() => setStep(3)}>
                Siguiente →
              </button>
            </div>
          </div>
        )}

        {/* ─── WINDOW 3 — Confirm ─────────────────────────────────────── */}
        {step === 3 && (
          <div className="bi-card">
            <div className="card-section">Resumen</div>

            <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: '1rem', fontSize: '0.88rem' }}>
              <tbody>
                {operation === 'registrar' ? (
                  <>
                    <tr><td style={tdLabel}>Operación</td><td style={tdValue}>Registrar Usuario</td></tr>
                    <tr><td style={tdLabel}>Nombre</td><td style={tdValue}>{name}</td></tr>
                    <tr><td style={tdLabel}>Correo</td><td style={tdValue}>{email}</td></tr>
                    {phone.trim() && <tr><td style={tdLabel}>Teléfono</td><td style={tdValue}>{phone}</td></tr>}
                    <tr><td style={tdLabel}>Sucursal</td><td style={tdValue}>{selectedDealer?.name || '—'}</td></tr>
                    <tr><td style={tdLabel}>Rol</td><td style={tdValue}>{ROLE_LABELS[role] || role}</td></tr>
                    <tr><td style={tdLabel}>Credenciales</td><td style={{ ...tdValue, color: '#1D4ED8' }}>Se enviarán por correo a {email}</td></tr>
                  </>
                ) : (
                  <>
                    <tr><td style={tdLabel}>Operación</td><td style={tdValue}>{operation === 'desactivar' ? 'Desactivar Usuario' : 'Reactivar Usuario'}</td></tr>
                    <tr><td style={tdLabel}>Usuario</td><td style={tdValue}>{selectedUser?.name}</td></tr>
                    <tr><td style={tdLabel}>Correo</td><td style={tdValue}>{selectedUser?.email}</td></tr>
                    <tr><td style={tdLabel}>Rol</td><td style={tdValue}>{ROLE_LABELS[selectedUser?.role] || selectedUser?.role}</td></tr>
                    <tr>
                      <td style={tdLabel}>Efecto</td>
                      <td style={{ ...tdValue, color: operation === 'desactivar' ? '#DC2626' : '#15803D' }}>
                        {operation === 'desactivar' ? 'El usuario perderá acceso al sistema' : 'El usuario recuperará el acceso'}
                      </td>
                    </tr>
                  </>
                )}
              </tbody>
            </table>

            <div className="btn-row" style={{ marginTop: '1rem' }}>
              <button className="btn-secondary" onClick={goBack}>← Volver</button>
              <button className="btn-primary" disabled={submitting} onClick={handleSubmit}>
                {submitting ? 'Procesando...' : 'Confirmar'}
              </button>
            </div>
          </div>
        )}

      </div>
    </>
  )
}

const tdLabel = { padding: '0.35rem 0', color: '#64748B', width: '40%' }
const tdValue = { padding: '0.35rem 0', fontWeight: 600 }
