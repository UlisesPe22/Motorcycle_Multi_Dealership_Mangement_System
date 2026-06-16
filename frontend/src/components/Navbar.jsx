import { useLocation, useNavigate } from 'react-router-dom'
import { getUser, clearAuth, isAuthenticated } from '../store/auth'

const ROLE_LABELS = {
  master:  'Master',
  owner:   'Adminstrador',
  manager: 'Gerente',
  vendor:  'Vendedor',
}

export default function Navbar({ navItems = [] }) {
  const location = useLocation()
  const navigate = useNavigate()
  const user = getUser()

  function handleLogout() {
    clearAuth()
    navigate('/login')
  }

  return (
    <>
      <div className="sidebar-brand">
        <div className="sidebar-brand-name">Moto Dealer</div>
        <div className="sidebar-brand-sub">Bajaj · Sistema de Gestión</div>
      </div>

      <div className="sidebar-section">Operaciones</div>

      {navItems.map(({ path, icon, label }) => {
        const isActive = location.pathname === path
        return isActive ? (
          <div key={path} className="sidebar-nav-active">
            {icon}&nbsp;&nbsp;{label}
          </div>
        ) : (
          <button
            key={path}
            className="sidebar-nav-item"
            onClick={() => navigate(path)}
          >
            {icon}&nbsp;&nbsp;{label}
          </button>
        )
      })}

      <div style={{ flex: 1 }} />

      {user && (
        <div style={{
          padding: '0.9rem 1.1rem',
          borderTop: '1px solid rgba(255,255,255,0.07)',
        }}>
          <div style={{ color: 'rgba(255,255,255,0.85)', fontSize: '0.78rem', fontWeight: 600 }}>
            {user.name}
          </div>
          <div style={{
            color: 'rgba(255,255,255,0.32)', fontSize: '0.6rem',
            letterSpacing: '0.1em', textTransform: 'uppercase', marginTop: '2px',
          }}>
            {ROLE_LABELS[user.role] || user.role}
          </div>
        </div>
      )}

      {isAuthenticated() && (
        <button
          className="sidebar-nav-item"
          onClick={handleLogout}
          style={{ paddingTop: '0.5rem', paddingBottom: '0.9rem' }}
        >
          ⏻&nbsp;&nbsp;Cerrar sesión
        </button>
      )}
    </>
  )
}
