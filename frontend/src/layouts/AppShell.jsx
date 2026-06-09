import Navbar from '../components/Navbar'
import MasterSwitcher from '../components/MasterSwitcher'

export default function AppShell({ children, navItems, switcherProps }) {
  return (
    <div className="app-layout">
      <aside className="sidebar">
        <Navbar navItems={navItems} />
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
