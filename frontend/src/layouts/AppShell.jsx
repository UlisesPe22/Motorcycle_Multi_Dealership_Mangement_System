import { useState } from 'react'
import Navbar from '../components/Navbar'
import MasterSwitcher from '../components/MasterSwitcher'

export default function AppShell({ children, navItems, switcherProps }) {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <div className="app-layout">
      {/* Mobile-only hamburger (hidden on desktop via CSS) */}
      <button
        className="hamburger-btn"
        aria-label="Abrir menú"
        onClick={() => setSidebarOpen(o => !o)}
      >
        ☰
      </button>

      {/* Mobile-only backdrop (hidden on desktop via CSS) */}
      <div
        className={`sidebar-backdrop${sidebarOpen ? ' open' : ''}`}
        onClick={() => setSidebarOpen(false)}
      />

      <aside className={`sidebar${sidebarOpen ? ' open' : ''}`}>
        <Navbar navItems={navItems} onNavClick={() => setSidebarOpen(false)} />
        {switcherProps && (
          <MasterSwitcher
            currentInterface={switcherProps.currentInterface}
            onSwitch={switcherProps.onSwitch}
          />
        )}
      </aside>
      <main className="main-content">
        {children}
      </main>
    </div>
  )
}
