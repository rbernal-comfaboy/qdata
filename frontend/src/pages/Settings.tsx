import { useState } from 'react'
import { Settings as SettingsIcon, User, Mail, Shield, Bell } from 'lucide-react'
import { useAuthStore } from '../hooks/useAuth'
import GlassContainer from '../components/layout/GlassContainer'

export default function Settings() {
  const user = useAuthStore((s) => s.user)

  const [name, setName] = useState(user?.name || '')
  const [email, setEmail] = useState(user?.email || '')

  return (
    <div>
      <h1 className="text-3xl font-bold text-white mb-8">Ajustes</h1>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <GlassContainer className="lg:col-span-2">
          <h2 className="text-xl font-semibold text-white mb-6 flex items-center gap-2">
            <User className="w-5 h-5" />
            Perfil
          </h2>
          <div className="space-y-4 max-w-md">
            <div>
              <label className="block text-sm text-muted mb-1">Nombre</label>
              <input type="text" value={name} onChange={(e) => setName(e.target.value)}
                className="glass-input" />
            </div>
            <div>
              <label className="block text-sm text-muted mb-1">Email</label>
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                className="glass-input" />
            </div>
            <div>
              <label className="block text-sm text-muted mb-1">Rol</label>
              <input type="text" value={user?.role || ''} disabled
                className="glass-input opacity-60" />
            </div>
            <button className="btn-primary">Guardar Cambios</button>
          </div>
        </GlassContainer>

        <div className="space-y-6">
          <GlassContainer>
            <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <Shield className="w-4 h-4" />
              Información
            </h3>
            <div className="space-y-2 text-sm text-muted">
              <p>Usuario desde: {user?.created_at || 'N/A'}</p>
              <p>ID: <span className="font-mono">{user?.id || ''}</span></p>
              <p>Versión: 0.1.0</p>
            </div>
          </GlassContainer>

          <GlassContainer>
            <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <Bell className="w-4 h-4" />
              Notificaciones
            </h3>
            <div className="space-y-3">
              <label className="flex items-center justify-between">
                <span className="text-sm text-muted">Reportes por email</span>
                <input type="checkbox" defaultChecked className="accent-indigo-500" />
              </label>
              <label className="flex items-center justify-between">
                <span className="text-sm text-muted">Alertas de errores</span>
                <input type="checkbox" defaultChecked className="accent-indigo-500" />
              </label>
            </div>
          </GlassContainer>
        </div>
      </div>
    </div>
  )
}
