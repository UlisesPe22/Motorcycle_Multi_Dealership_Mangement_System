import { Routes, Route, Navigate } from 'react-router-dom'
import AppShell from './AppShell'

import OwnerDashboard from '../pages/owner/OwnerDashboard'
import RegisterVendedor from '../pages/RegisterVendedor'

export const OWNER_NAV = [
  { path: '/dashboard',          icon: '⊞', label: 'Panel Principal' },
  { path: '/registrar-empleado', icon: '◈', label: 'Registrar Gerente' },
]

export default function OwnerLayout({ switcherProps }) {
  return (
    <AppShell navItems={OWNER_NAV} switcherProps={switcherProps}>
      <Routes>
        <Route path="/dashboard" element={<OwnerDashboard />} />
        <Route path="/registrar-empleado" element={<RegisterVendedor />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </AppShell>
  )
}
