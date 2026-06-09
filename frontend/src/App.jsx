import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { getUser } from './store/auth'

// Auth
import Login from './pages/auth/Login'

// Layouts
import ManagerLayout from './layouts/ManagerLayout'
import VendorLayout  from './layouts/VendorLayout'
import OwnerLayout   from './layouts/OwnerLayout'

function RoleRouter() {
  // During development: if not authenticated, default to manager interface
  const user = getUser()
  const role = user?.role || 'manager'

  if (role === 'vendor') return <VendorLayout />
  if (role === 'owner')  return <OwnerLayout />
  // master + manager share the manager interface for now
  return <ManagerLayout />
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/*" element={<RoleRouter />} />
      </Routes>
    </BrowserRouter>
  )
}
