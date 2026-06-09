import { Routes, Route, Navigate } from 'react-router-dom'
import AppShell from './AppShell'

import MasterDashboard from '../pages/master/MasterDashboard'

export const MASTER_NAV = [
  { path: '/', icon: '⊞', label: 'Panel Master' },
]

export default function MasterLayout({ switcherProps }) {
  return (
    <AppShell navItems={MASTER_NAV} switcherProps={switcherProps}>
      <Routes>
        <Route path="/" element={<MasterDashboard />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AppShell>
  )
}
