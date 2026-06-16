import { getUser } from '../store/auth'

const INTERFACES = [
  { role: 'manager', label: 'Interfaz Gerente',  icon: '⚙', path: '/' },
  { role: 'vendor',  label: 'Interfaz Vendedor', icon: '◇', path: '/mis-ventas' },
  { role: 'owner',   label: 'Interfaz Administrador',    icon: '⊞', path: '/dashboard' },
  { role: 'master',  label: 'Panel Master',       icon: '★', path: '/master' },
]

export default function MasterSwitcher({ currentInterface, onSwitch }) {
  const user = getUser()
  if (user?.role !== 'master') return null

  return (
    <div style={{
      borderTop: '1px solid rgba(255,255,255,0.07)',
      marginTop: '1rem',
      paddingTop: '1rem',
    }}>
      <div style={{
        fontSize: '0.65rem', fontWeight: 700, color: 'rgba(255,255,255,0.35)',
        textTransform: 'uppercase', letterSpacing: '0.08em',
        padding: '0 1rem', marginBottom: '0.5rem',
      }}>
        Vista Master
      </div>
      {INTERFACES.map(({ role, label, icon, path }) => {
        const isActive = currentInterface === role
        return (
          <button
            key={role}
            onClick={() => onSwitch(role, path)}
            style={{
              width: '100%', textAlign: 'left',
              padding: '0.5rem 1rem', border: 'none', cursor: 'pointer',
              background: isActive ? 'rgba(29,78,216,0.25)' : 'transparent',
              color: isActive ? '#93C5FD' : 'rgba(255,255,255,0.55)',
              fontWeight: isActive ? 700 : 400,
              fontSize: '0.82rem', borderRadius: '0.4rem',
              display: 'flex', alignItems: 'center', gap: '0.5rem',
            }}
            onMouseEnter={e => { if (!isActive) e.currentTarget.style.background = 'rgba(255,255,255,0.06)' }}
            onMouseLeave={e => { if (!isActive) e.currentTarget.style.background = 'transparent' }}
          >
            <span>{icon}</span>
            <span>{label}</span>
            {isActive && <span style={{ marginLeft: 'auto', fontSize: '0.7rem', color: '#60A5FA' }}>●</span>}
          </button>
        )
      })}
    </div>
  )
}
