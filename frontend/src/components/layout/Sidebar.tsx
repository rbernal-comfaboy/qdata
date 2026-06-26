import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  Search,
  FileText,
  FolderOpen,
  Database,
  BookOpen,
  Shield,
  Clock,
  Settings,
  LogOut,
  Sun,
  Moon,
  FolderTree,
} from 'lucide-react'
import { useAuthStore } from '../../hooks/useAuth'
import { useTheme } from '../../hooks/useTheme'
import { cn } from '../../lib/utils'

const links = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/groups', icon: FolderTree, label: 'Grupos de Análisis' },
  { to: '/processes', icon: FolderOpen, label: 'Procesos' },
  { to: '/connections', icon: Database, label: 'Conexiones' },
  { to: '/datasources', icon: BookOpen, label: 'Fuentes' },
  { to: '/analyze', icon: Search, label: 'Analizar' },
  { to: '/reports', icon: FileText, label: 'Reportes' },
  { to: '/rules', icon: Shield, label: 'Reglas' },
  { to: '/scheduler', icon: Clock, label: 'Programador' },
  { to: '/settings', icon: Settings, label: 'Ajustes' },
]

export default function Sidebar() {
  const logout = useAuthStore((s) => s.logout)
  const user = useAuthStore((s) => s.user)
  const { theme, toggle } = useTheme()

  return (
    <aside className="w-64 h-screen sticky top-0 glass rounded-none flex flex-col shrink-0">
      <div className="p-6 border-b border-white/10">
        <h1 className="text-2xl font-bold text-white flex items-center gap-2" style={{ color: 'var(--text)' }}>
          <Search className="w-6 h-6 text-indigo-400" />
          QData
        </h1>
        <p className="text-sm text-muted mt-1">Calidad de Datos</p>
      </div>

      <nav className="flex-1 p-4 space-y-1">
        {links.map((link) => (
          <NavLink
            key={link.to}
            to={link.to}
            className={({ isActive }) =>
              cn('sidebar-link', isActive && 'active')
            }
          >
            <link.icon className="w-5 h-5" />
            {link.label}
          </NavLink>
        ))}
      </nav>

      <div className="p-4 border-t border-white/10 space-y-2">
        <button
          onClick={toggle}
          className="sidebar-link w-full"
        >
          {theme === 'dark' ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
          {theme === 'dark' ? 'Modo Claro' : 'Modo Oscuro'}
        </button>

        <div className="flex items-center gap-3 mb-2">
          <div className="w-8 h-8 rounded-full bg-indigo-500 flex items-center justify-center text-sm font-semibold text-white">
            {user?.name?.charAt(0) || 'U'}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm truncate" style={{ color: 'var(--text)' }}>{user?.name}</p>
            <p className="text-xs text-muted truncate">{user?.email}</p>
          </div>
        </div>
        <button
          onClick={logout}
          className="sidebar-link w-full text-red-400 hover:text-red-300"
        >
          <LogOut className="w-5 h-5" />
          Cerrar sesión
        </button>
      </div>
    </aside>
  )
}
