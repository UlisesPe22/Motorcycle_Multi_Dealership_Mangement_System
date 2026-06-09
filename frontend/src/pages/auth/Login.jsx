import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import { saveAuth } from '../../store/auth'

export default function Login() {
  const navigate = useNavigate()
  const [email,    setEmail]    = useState('')
  const [password, setPassword] = useState('')
  const [error,    setError]    = useState('')
  const [loading,  setLoading]  = useState(false)

  // Check for expired session message
  const expired = new URLSearchParams(window.location.search).get('expired')

  async function handleLogin(e) {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const form = new FormData()
      form.append('username', email)
      form.append('password', password)
      const res = await axios.post('/api/auth/login', form)
      saveAuth(res.data.access_token, {
        user_id:      res.data.user_id,
        name:         res.data.name,
        role:         res.data.role,
        dealership_id: res.data.dealership_id,
      })
      // Redirect based on role
      const roleRoutes = {
        master:  '/',
        owner:   '/dashboard',
        manager: '/',
        vendor:  '/declarar-pago',
      }
      navigate(roleRoutes[res.data.role] || '/')
    } catch (e) {
      setError(e.response?.data?.detail || 'Credenciales incorrectas.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center',
      justifyContent: 'center', background: '#F8FAFC',
    }}>
      <div style={{
        background: '#fff', borderRadius: '0.75rem', padding: '2.5rem',
        width: '100%', maxWidth: '400px',
        boxShadow: '0 4px 24px rgba(0,0,0,0.08)',
      }}>
        <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
          <div style={{ fontWeight: 800, fontSize: '1.5rem', color: '#1E293B' }}>
            Bajaj · Sistema de Gestión
          </div>
          <div style={{ color: '#64748B', fontSize: '0.9rem', marginTop: '0.25rem' }}>
            Inicia sesión para continuar
          </div>
        </div>

        {expired && (
          <div style={{
            background: '#FEF3C7', color: '#92400E', padding: '0.75rem 1rem',
            borderRadius: '0.5rem', fontSize: '0.85rem', marginBottom: '1rem',
            border: '1px solid #FDE68A',
          }}>
            Tu sesión ha expirado. Por favor inicia sesión nuevamente.
          </div>
        )}

        {error && (
          <div style={{
            background: '#FEE2E2', color: '#DC2626', padding: '0.75rem 1rem',
            borderRadius: '0.5rem', fontSize: '0.85rem', marginBottom: '1rem',
            border: '1px solid #FECACA',
          }}>
            {error}
          </div>
        )}

        <form onSubmit={handleLogin} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: '#374151', marginBottom: '0.35rem' }}>
              Correo electrónico
            </label>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="usuario@ejemplo.com"
              required
              style={{ width: '100%' }}
            />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: '#374151', marginBottom: '0.35rem' }}>
              Contraseña
            </label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="••••••"
              required
              style={{ width: '100%' }}
            />
          </div>
          <button
            type="submit"
            className="btn-primary"
            disabled={loading}
            style={{ marginTop: '0.5rem', width: '100%' }}
          >
            {loading ? 'Iniciando sesión...' : 'Iniciar Sesión'}
          </button>
        </form>
      </div>
    </div>
  )
}
