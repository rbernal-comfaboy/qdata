import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Users, Trash2, Shield, Plus, Loader2, AlertCircle, CheckCircle, ChevronDown, ChevronRight } from 'lucide-react'
import api from '../api/client'
import GlassContainer from '../components/layout/GlassContainer'
import { useAuthStore } from '../hooks/useAuth'

const ROLE_LABELS: Record<string, string> = {
  admin: 'Admin',
  analyst: 'Analista',
  viewer: 'Solo vista',
}

const ROLE_COLORS: Record<string, string> = {
  admin: 'text-purple-400 bg-purple-500/20',
  analyst: 'text-indigo-400 bg-indigo-500/20',
  viewer: 'text-yellow-400 bg-yellow-500/20',
}

export default function AdminUsers() {
  const queryClient = useQueryClient()
  const currentUser = useAuthStore((s) => s.user)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ email: '', password: '', name: '', role: 'analyst' })
  const [formGroups, setFormGroups] = useState<string[]>([])
  const [formError, setFormError] = useState('')
  const [expandedUser, setExpandedUser] = useState<string | null>(null)
  const [editingGroups, setEditingGroups] = useState<string[]>([])

  const { data: users, isLoading } = useQuery({
    queryKey: ['admin-users'],
    queryFn: () => api.get('/admin/users').then((r) => r.data),
  })

  const { data: allGroups = [] } = useQuery({
    queryKey: ['admin-groups'],
    queryFn: () => api.get('/admin/groups').then((r) => r.data),
  })

  const { data: userPermsMap } = useQuery({
    queryKey: ['user-permissions', expandedUser],
    queryFn: async () => {
      if (!expandedUser) return {}
      const r = await api.get(`/admin/users/${expandedUser}/permissions`)
      const ids = (r.data as any[]).map((p: any) => p.group_id)
      setEditingGroups(ids)
      return { [expandedUser]: ids }
    },
    enabled: !!expandedUser,
  })

  const createMutation = useMutation({
    mutationFn: (data: { email: string; password: string; name: string; role: string; group_ids: string[] }) =>
      api.post('/admin/users', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-users'] })
      setShowForm(false)
      setForm({ email: '', password: '', name: '', role: 'analyst' })
      setFormGroups([])
      setFormError('')
    },
    onError: (err: any) => setFormError(err?.response?.data?.detail || 'Error al crear usuario'),
  })

  const updateRoleMutation = useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: string }) =>
      api.put(`/admin/users/${userId}/role`, { role }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin-users'] }),
  })

  const deleteMutation = useMutation({
    mutationFn: (userId: string) => api.delete(`/admin/users/${userId}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin-users'] }),
  })

  const savePermsMutation = useMutation({
    mutationFn: ({ userId, group_ids }: { userId: string; group_ids: string[] }) =>
      api.put(`/admin/users/${userId}/permissions`, { group_ids }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['user-permissions'] })
      setExpandedUser(null)
    },
  })

  const handleToggleGroup = (groupId: string, mode: 'create' | 'edit') => {
    if (mode === 'create') {
      setFormGroups((prev) => prev.includes(groupId) ? prev.filter((g) => g !== groupId) : [...prev, groupId])
    } else {
      setEditingGroups((prev) => prev.includes(groupId) ? prev.filter((g) => g !== groupId) : [...prev, groupId])
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-3xl font-bold flex items-center gap-3">
          <Users className="w-8 h-8 text-indigo-400" />
          Usuarios
        </h1>
        <button onClick={() => setShowForm(!showForm)} className="btn-primary flex items-center gap-2">
          <Plus className="w-4 h-4" />
          Nuevo Usuario
        </button>
      </div>

      {showForm && (
        <GlassContainer className="mb-6">
          <h2 className="text-lg font-semibold mb-4">Crear Usuario</h2>
          {formError && (
            <div className="flex items-center gap-2 text-sm text-red-400 mb-4 p-3 bg-red-500/10 rounded-lg">
              <AlertCircle className="w-4 h-4 shrink-0" />
              {formError}
            </div>
          )}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <input type="text" placeholder="Nombre" value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="glass-input" />
            <input type="email" placeholder="Email" value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              className="glass-input" />
            <input type="password" placeholder="Contraseña" value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              className="glass-input" />
            <select value={form.role}
              onChange={(e) => setForm({ ...form, role: e.target.value })}
              className="glass-input">
              <option value="analyst">Analista</option>
              <option value="admin">Admin</option>
              <option value="viewer">Solo vista</option>
            </select>
          </div>

          {form.role !== 'admin' && (
            <div className="mt-4">
              <label className="block text-sm text-muted mb-2">Grupos de análisis permitidos</label>
              <div className="max-h-40 overflow-y-auto space-y-1.5 bg-white/5 rounded-lg p-3 border border-white/10">
                {allGroups.length === 0 && <p className="text-xs text-muted">No hay grupos disponibles</p>}
                {allGroups.map((g: any) => (
                  <label key={g.id} className="flex items-center gap-2 cursor-pointer hover:bg-white/5 rounded px-2 py-1">
                    <input type="checkbox" checked={formGroups.includes(g.id)}
                      onChange={() => handleToggleGroup(g.id, 'create')}
                      className="w-4 h-4 rounded accent-indigo-500" />
                    <span className="text-sm">{g.name}</span>
                  </label>
                ))}
              </div>
            </div>
          )}

          <div className="flex gap-2 mt-4">
            <button onClick={() => createMutation.mutate({ ...form, group_ids: formGroups })}
              disabled={createMutation.isPending || !form.email || !form.password}
              className="btn-primary text-sm">
              {createMutation.isPending ? 'Creando...' : 'Crear'}
            </button>
            <button onClick={() => { setShowForm(false); setFormError(''); setFormGroups([]) }}
              className="btn-ghost text-sm">Cancelar</button>
          </div>
        </GlassContainer>
      )}

      {isLoading ? (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => <div key={i} className="skeleton h-20 rounded-xl" />)}
        </div>
      ) : (
        <div className="space-y-3">
          {users?.map((u: any) => (
            <div key={u.id}>
              <GlassContainer>
                <div className="flex items-center gap-4">
                  {(u.role !== 'admin') && (
                    <button
                      onClick={() => setExpandedUser(expandedUser === u.id ? null : u.id)}
                      className="p-1 text-muted hover:text-white transition-colors"
                      title="Asignar grupos"
                    >
                      {expandedUser === u.id ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                    </button>
                  )}
                  <div className="w-10 h-10 rounded-full bg-indigo-500/20 flex items-center justify-center text-sm font-semibold text-indigo-400">
                    {(u.name || '?').charAt(0).toUpperCase()}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium">{u.name}</p>
                    <p className="text-sm text-muted truncate">{u.email}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <select
                      value={u.role}
                      onChange={(e) => {
                        if (u.id === currentUser?.id) return
                        updateRoleMutation.mutate({ userId: u.id, role: e.target.value })
                      }}
                      disabled={u.id === currentUser?.id}
                      className={`glass-input !py-1 !px-2 text-xs font-semibold rounded ${ROLE_COLORS[u.role] || ''}`}
                      style={{ border: 'none' }}
                    >
                      <option value="admin">Admin</option>
                      <option value="analyst">Analista</option>
                      <option value="viewer">Solo vista</option>
                    </select>
                    {u.id !== currentUser?.id && (
                      <button
                        onClick={() => { if (confirm('Eliminar este usuario?')) deleteMutation.mutate(u.id) }}
                        disabled={deleteMutation.isPending}
                        className="btn-ghost p-2 text-red-400 hover:text-red-300"
                        title="Eliminar usuario"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                </div>
              </GlassContainer>

              {expandedUser === u.id && (
                <GlassContainer className="mt-1 ml-6">
                  <div className="flex items-center justify-between mb-3">
                    <label className="block text-sm font-medium text-white">Grupos de análisis permitidos</label>
                    {editingGroups.length > 0 && (
                      <button
                        onClick={() => savePermsMutation.mutate({ userId: u.id, group_ids: editingGroups })}
                        disabled={savePermsMutation.isPending}
                        className="text-xs px-3 py-1 bg-indigo-500 hover:bg-indigo-600 text-white rounded-lg transition-colors"
                      >
                        {savePermsMutation.isPending ? 'Guardando...' : 'Guardar'}
                      </button>
                    )}
                  </div>
                  <div className="max-h-48 overflow-y-auto space-y-1.5 bg-white/5 rounded-lg p-3 border border-white/10">
                    {allGroups.length === 0 && <p className="text-xs text-muted">No hay grupos disponibles</p>}
                    {allGroups.map((g: any) => (
                      <label key={g.id} className="flex items-center gap-2 cursor-pointer hover:bg-white/5 rounded px-2 py-1">
                        <input type="checkbox" checked={editingGroups.includes(g.id)}
                          onChange={() => handleToggleGroup(g.id, 'edit')}
                          className="w-4 h-4 rounded accent-indigo-500" />
                        <span className="text-sm">{g.name}</span>
                      </label>
                    ))}
                  </div>
                </GlassContainer>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}