import { useLocation, useNavigate } from 'react-router-dom'

const NAV_MAIN = [
  { path: '/',                    icon: '⊞', label: 'Panel Principal' },
  { path: '/registrar-cliente',   icon: '+', label: 'Registrar Cliente' },
  { path: '/clientes',            icon: '○', label: 'Buscar Cliente' },
  { path: '/orden-compra',        icon: '≡', label: 'Orden de Compra' },
  { path: '/orden-traslado',      icon: '▷', label: 'Orden de Traslado' },
  { path: '/registrar-entrega',   icon: '✔', label: 'Registrar Entrega' },
  { path: '/reservacion',         icon: '◈', label: 'Registrar Reservación' },
  { path: '/iniciar-venta',       icon: '◇', label: 'Iniciar Venta' },
  { path: '/registrar-empleado',  icon: '◈', label: 'Registrar Empleado' },
]

export default function Navbar() {
  const location = useLocation()
  const navigate = useNavigate()

  return (
    <>
      <div className="sidebar-brand">
        <div className="sidebar-brand-name">Moto Dealer</div>
        <div className="sidebar-brand-sub">Bajaj · Sistema de Gestión</div>
      </div>

      <div className="sidebar-section">Operaciones</div>

      {NAV_MAIN.map(({ path, icon, label }) => {
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

    </>
  )
}
