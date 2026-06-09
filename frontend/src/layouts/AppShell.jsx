import Navbar from '../components/Navbar'

export default function AppShell({ children, navItems }) {
  return (
    <div className="app-layout">
      <aside className="sidebar">
        <Navbar navItems={navItems} />
      </aside>
      <main className="main-content">
        {children}
      </main>
    </div>
  )
}
