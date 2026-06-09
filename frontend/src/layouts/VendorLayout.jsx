import { Routes, Route, Navigate } from 'react-router-dom'
import AppShell from './AppShell'

import DeclarePayment from '../pages/DeclarePayment'
import VendorSales from '../pages/VendorSales'
import RegisterClient from '../pages/RegisterClient'
import CreateContract from '../pages/CreateContract'

export const VENDOR_NAV = [
  { path: '/declarar-pago',     icon: '◇', label: 'Declarar Pago' },
  { path: '/mis-ventas',        icon: '◉', label: 'Mis Ventas' },
  { path: '/registrar-cliente', icon: '+', label: 'Registrar Cliente' },
]

export default function VendorLayout() {
  return (
    <AppShell navItems={VENDOR_NAV}>
      <Routes>
        <Route path="/declarar-pago" element={<DeclarePayment />} />
        <Route path="/mis-ventas" element={<VendorSales />} />
        <Route path="/registrar-cliente" element={<RegisterClient />} />
        <Route path="/crear-contrato/:sale_id" element={<CreateContract />} />
        <Route path="*" element={<Navigate to="/declarar-pago" replace />} />
      </Routes>
    </AppShell>
  )
}
