import { useState } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { getUser, getSavedInterface, saveInterface } from './store/auth'

// Auth
import Login from './pages/auth/Login'

// Layouts
import ManagerLayout from './layouts/ManagerLayout'
import VendorLayout  from './layouts/VendorLayout'
import OwnerLayout   from './layouts/OwnerLayout'
import MasterLayout  from './layouts/MasterLayout'

function RoleRouter() {
  const user = getUser()
  const role = user?.role || 'manager'

  const [masterInterface, setMasterInterface] = useState(
    role === 'master' ? (getSavedInterface() || 'manager') : role
  )

  function handleSwitch(newInterface, path) {
    saveInterface(newInterface)
    setMasterInterface(newInterface)
    window.location.href = path
  }

  const activeInterface = role === 'master' ? masterInterface : role

  const switcherProps = role === 'master'
    ? { currentInterface: masterInterface, onSwitch: handleSwitch }
    : null

  if (activeInterface === 'vendor')  return <VendorLayout  switcherProps={switcherProps} />
  if (activeInterface === 'owner')   return <OwnerLayout   switcherProps={switcherProps} />
  if (activeInterface === 'master')  return <MasterLayout  switcherProps={switcherProps} />
  return <ManagerLayout switcherProps={switcherProps} />
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
