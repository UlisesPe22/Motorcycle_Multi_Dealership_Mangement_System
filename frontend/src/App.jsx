import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Navbar from './components/Navbar'
import Dashboard from './pages/Dashboard'
import RegisterClient from './pages/RegisterClient'
import ClientList from './pages/ClientList'
import PurchaseOrder from './pages/PurchaseOrder'
import OrderConfirmation from './pages/OrderConfirmation'
import Delivery from './pages/Delivery'
import DeclarePayment from './pages/DeclarePayment'
import Placeholders from './pages/Placeholders'
import RegisterVendedor from './pages/RegisterVendedor'
import InventoryManagement from './pages/InventoryManagement'
function AppContent() {
  return (
    <div className="app-layout">
      <aside className="sidebar">
        <Navbar />
      </aside>
      <main className="main-content">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/registrar-cliente" element={<RegisterClient />} />
          <Route path="/clientes" element={<ClientList />} />
          <Route path="/orden-compra" element={<PurchaseOrder />} />
          <Route path="/orden-traslado" element={<OrderConfirmation />} />
          <Route path="/registrar-entrega" element={<Delivery />} />
          <Route path="/declarar-pago" element={<DeclarePayment />} />
          <Route path="/validar-venta" element={<Placeholders title="Validar Venta" />} />
          <Route path="/registrar-empleado" element={<RegisterVendedor />} />
          <Route path="/modificar-inventario" element={<InventoryManagement />} />
        </Routes>
      </main>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AppContent />
    </BrowserRouter>
  )
}
