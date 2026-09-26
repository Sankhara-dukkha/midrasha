import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'

export function Layout() {
  const { user, logout } = useAuth()
  return (
    <div className="shell">
      <header className="topbar">
        <span className="brand">MIDRASHA</span>
        <nav>
          <NavLink to="/dashboard">Dashboard</NavLink>
          <NavLink to="/missions">Missions</NavLink>
          <NavLink to="/settings">Settings</NavLink>
        </nav>
        {user && (
          <button className="link" onClick={logout}>
            Sign out
          </button>
        )}
      </header>
      <main>
        <Outlet />
      </main>
      <footer className="disclaimer">
        Fictional training simulation. All targets, groups and scenarios are invented. Not
        operational advice.
      </footer>
    </div>
  )
}
