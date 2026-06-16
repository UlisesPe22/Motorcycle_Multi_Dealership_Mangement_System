import { Routes, Route, Navigate } from 'react-router-dom'
import AppShell from './AppShell'

import DeclarePayment from '../pages/DeclarePayment'
import VendorSales from '../pages/VendorSales'
import RegisterClient from '../pages/RegisterClient'
import CreateContract from '../pages/CreateContract'
import Comisiones from '../pages/Comisiones'

export const VENDOR_NAV = [
  { path: '/mis-ventas',        icon: '◉', label: 'Mis Ventas' },
  { path: '/comisiones',        icon: '💰', label: 'Comisiones' },
  { path: '/declarar-pago',     icon: '◇', label: 'Declarar Pago' },
  { path: '/registrar-cliente', icon: '+', label: 'Registrar Cliente' },
]

export default function VendorLayout({ switcherProps }) {
  return (
    <AppShell navItems={VENDOR_NAV} switcherProps={switcherProps}>
      <Routes>
        <Route path="/declarar-pago" element={<DeclarePayment />} />
        <Route path="/mis-ventas" element={<VendorSales />} />
        <Route path="/comisiones" element={<Comisiones />} />
        <Route path="/registrar-cliente" element={<RegisterClient />} />
        <Route path="/crear-contrato/:sale_id" element={<CreateContract />} />
        <Route path="*" element={<Navigate to="/mis-ventas" replace />} />
      </Routes>
    </AppShell>
  )
}
