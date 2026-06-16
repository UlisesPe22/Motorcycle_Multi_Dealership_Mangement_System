import { Routes, Route, Navigate } from 'react-router-dom'
import AppShell from './AppShell'

import Dashboard from '../pages/Dashboard'
import RegisterClient from '../pages/RegisterClient'
import ClientList from '../pages/ClientList'
import PurchaseOrder from '../pages/PurchaseOrder'
import OrderConfirmation from '../pages/OrderConfirmation'
import Delivery from '../pages/Delivery'
import DeclarePayment from '../pages/DeclarePayment'
import Placeholders from '../pages/Placeholders'
import RegisterVendedor from '../pages/RegisterVendedor'
import InventoryManagement from '../pages/InventoryManagement'
import VendorSales from '../pages/VendorSales'
import CreateContract from '../pages/CreateContract'
import InventoryEvents from '../pages/InventoryEvents'

export const MANAGER_NAV = [
  { path: '/',                     icon: '⊞', label: 'Panel Principal' },
  { path: '/registrar-cliente',    icon: '+', label: 'Registrar Cliente' },
// { path: '/clientes',             icon: '○', label: 'Buscar Cliente' },
  { path: '/eventos-inventario',   icon: '≡', label: 'Eventos de Inventario' },
  { path: '/declarar-pago',        icon: '◇', label: 'Declarar Pago' },
  { path: '/modificar-inventario', icon: '✕', label: 'Modificar Inventario' },
  { path: '/registrar-empleado',   icon: '◈', label: 'Registrar Empleado' },
]

export default function ManagerLayout({ switcherProps }) {
  return (
    <AppShell navItems={MANAGER_NAV} switcherProps={switcherProps}>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/registrar-cliente" element={<RegisterClient />} />
        <Route path="/clientes" element={<ClientList />} />
        <Route path="/eventos-inventario" element={<InventoryEvents />} />
        <Route path="/orden-compra" element={<PurchaseOrder />} />
        <Route path="/orden-traslado" element={<OrderConfirmation />} />
        <Route path="/registrar-entrega" element={<Delivery />} />
        <Route path="/declarar-pago" element={<DeclarePayment />} />
        <Route path="/validar-venta" element={<Placeholders title="Validar Venta" />} />
        <Route path="/registrar-empleado" element={<RegisterVendedor />} />
        <Route path="/modificar-inventario" element={<InventoryManagement />} />
        <Route path="/mis-ventas" element={<VendorSales />} />
        <Route path="/crear-contrato/:sale_id" element={<CreateContract />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AppShell>
  )
}
