import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Settings as SettingsIcon, User, Mail, Shield, Bell, Key, AlertCircle, CheckCircle, Loader2 } from 'lucide-react'
import api from '../api/client'
import { useAuthStore } from '../hooks/useAuth'
import GlassContainer from '../components/layout/GlassContainer'

export default function Settings() {
  const user = useAuthStore((s) => s.user)
  const loadUser = useAuthStore((s) => s.loadUser)
  const queryClient = useQueryClient()

  const [name, setName] = useState(user?.name || '')
  const [email, setEmail] = useState(user?.email || '')
  const [profileMsg, setProfileMsg] = useState<{ type: 'ok' | 'err'; text: string } | null>(null)

  const [currentPwd, setCurrentPwd] = useState('')
  const [newPwd, setNewPwd] = useState('')
  const [confirmPwd, setConfirmPwd] = useState('')
  const [pwdMsg, setPwdMsg] = useState<{ type: 'ok' | 'err'; text: string } | null>(null)

  const profileMutation = useMutation({
    mutationFn: () => api.put('/auth/me', { name, email }),
    onSuccess: async () => {
      await loadUser()
      setProfileMsg({ type: 'ok', text: 'Perfil actualizado' })
      setTimeout(() => setProfileMsg(null), 3000)
    },
    onError: (err: any) => {
      setProfileMsg({ type: 'err', text: err?.response?.data?.detail || 'Error al guardar' })
    },
  })

  const passwordMutation = useMutation({
    mutationFn: () => api.put('/auth/password', { current_password: currentPwd, new_password: newPwd }),
    onSuccess: () => {
      setCurrentPwd('')
      setNewPwd('')
      setConfirmPwd('')
      setPwdMsg({ type: 'ok', text: 'Contraseña cambiada' })
      setTimeout(() => setPwdMsg(null), 3000)
    },
    onError: (err: any) => {
      setPwdMsg({ type: 'err', text: err?.response?.data?.detail || 'Error al cambiar contraseña' })
    },
  })

  return (
    <div>
      <h1 className="text-3xl font-bold text-white mb-8">Ajustes</h1>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <GlassContainer>
            <h2 className="text-xl font-semibold text-white mb-6 flex items-center gap-2">
              <User className="w-5 h-5" />
              Perfil
            </h2>
            {profileMsg && (
              <div className={`flex items-center gap-2 text-sm mb-4 p-3 rounded-lg ${profileMsg.type === 'ok' ? 'text-green-400 bg-green-500/10' : 'text-red-400 bg-red-500/10'}`}>
                {profileMsg.type === 'ok' ? <CheckCircle className="w-4 h-4 shrink-0" /> : <AlertCircle className="w-4 h-4 shrink-0" />}
                {profileMsg.text}
              </div>
            )}
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
              <button onClick={() => profileMutation.mutate()}
                disabled={profileMutation.isPending}
                className="btn-primary flex items-center gap-2">
                {profileMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle className="w-4 h-4" />}
                Guardar Cambios
              </button>
            </div>
          </GlassContainer>

          <GlassContainer>
            <h2 className="text-xl font-semibold text-white mb-6 flex items-center gap-2">
              <Key className="w-5 h-5" />
              Cambiar Contraseña
            </h2>
            {pwdMsg && (
              <div className={`flex items-center gap-2 text-sm mb-4 p-3 rounded-lg ${pwdMsg.type === 'ok' ? 'text-green-400 bg-green-500/10' : 'text-red-400 bg-red-500/10'}`}>
                {pwdMsg.type === 'ok' ? <CheckCircle className="w-4 h-4 shrink-0" /> : <AlertCircle className="w-4 h-4 shrink-0" />}
                {pwdMsg.text}
              </div>
            )}
            <div className="space-y-4 max-w-md">
              <div>
                <label className="block text-sm text-muted mb-1">Contraseña actual</label>
                <input type="password" value={currentPwd} onChange={(e) => setCurrentPwd(e.target.value)}
                  className="glass-input" placeholder="Ingresa tu contraseña actual" />
              </div>
              <div>
                <label className="block text-sm text-muted mb-1">Nueva contraseña</label>
                <input type="password" value={newPwd} onChange={(e) => setNewPwd(e.target.value)}
                  className="glass-input" placeholder="Mínimo 6 caracteres" />
              </div>
              <div>
                <label className="block text-sm text-muted mb-1">Confirmar contraseña</label>
                <input type="password" value={confirmPwd} onChange={(e) => setConfirmPwd(e.target.value)}
                  className="glass-input" placeholder="Repite la nueva contraseña" />
              </div>
              <button onClick={() => {
                if (newPwd !== confirmPwd) {
                  setPwdMsg({ type: 'err', text: 'Las contraseñas no coinciden' })
                  return
                }
                if (newPwd.length < 6) {
                  setPwdMsg({ type: 'err', text: 'La contraseña debe tener al menos 6 caracteres' })
                  return
                }
                passwordMutation.mutate()
              }}
                disabled={passwordMutation.isPending || !currentPwd || !newPwd || !confirmPwd}
                className="btn-primary flex items-center gap-2">
                {passwordMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Key className="w-4 h-4" />}
                Cambiar Contraseña
              </button>
            </div>
          </GlassContainer>
        </div>

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
