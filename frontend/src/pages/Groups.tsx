import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { FolderOpen, Plus, Trash2, Edit3, BarChart3, Calendar, FileText } from 'lucide-react'
import api from '../api/client'
import GlassContainer from '../components/layout/GlassContainer'
import { useAuthStore } from '../hooks/useAuth'

const COLORS = ['#6366f1', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#ec4899', '#f97316']

export default function Groups() {
  const qc = useQueryClient()
  const currentUser = useAuthStore((s) => s.user)
  const isAdmin = currentUser?.role === 'admin'
  const [showForm, setShowForm] = useState(false)
  const [editId, setEditId] = useState<string | null>(null)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [color, setColor] = useState(COLORS[0])

  const { data: groups = [], isLoading } = useQuery({
    queryKey: ['groups'],
    queryFn: () => api.get('/api/groups').then(r => r.data),
  })

  const createMut = useMutation({
    mutationFn: (data: any) => api.post('/api/groups', data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['groups'] }); resetForm() },
  })

  const updateMut = useMutation({
    mutationFn: ({ id, ...data }: any) => api.put(`/api/groups/${id}`, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['groups'] }); resetForm() },
  })

  const deleteMut = useMutation({
    mutationFn: (id: string) => api.delete(`/api/groups/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['groups'] }),
  })

  const resetForm = () => { setShowForm(false); setEditId(null); setName(''); setDescription(''); setColor(COLORS[0]) }

  const handleSubmit = () => {
    if (!name.trim()) return
    if (editId) {
      updateMut.mutate({ id: editId, name, description, color })
    } else {
      createMut.mutate({ name, description, color })
    }
  }

  const startEdit = (g: any) => {
    setEditId(g.id); setName(g.name); setDescription(g.description || ''); setColor(g.color || COLORS[0]); setShowForm(true)
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-3xl font-bold text-white">Grupos de Análisis</h1>
        <button onClick={() => { resetForm(); setShowForm(true) }}
          className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-500 hover:bg-indigo-600 text-white rounded-lg transition-colors text-sm font-medium">
          <Plus className="w-4 h-4" /> Nuevo Grupo de Análisis
        </button>
      </div>

      {showForm && (
        <GlassContainer className="mb-6">
          <h3 className="text-lg font-semibold text-white mb-4">{editId ? 'Editar Grupo de Análisis' : 'Nuevo Grupo de Análisis'}</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="text-xs text-muted mb-1 block">Nombre *</label>
              <input value={name} onChange={e => setName(e.target.value)} placeholder="Ej: Proyecto CRM"
                className="w-full bg-white/10 border border-white/10 rounded-lg px-3 py-2 text-white text-sm" />
            </div>
            <div>
              <label className="text-xs text-muted mb-1 block">Descripción</label>
              <input value={description} onChange={e => setDescription(e.target.value)} placeholder="Opcional"
                className="w-full bg-white/10 border border-white/10 rounded-lg px-3 py-2 text-white text-sm" />
            </div>
            <div>
              <label className="text-xs text-muted mb-1 block">Color</label>
              <div className="flex gap-2 mt-1">
                {COLORS.map(c => (
                  <button key={c} onClick={() => setColor(c)}
                    className={`w-7 h-7 rounded-full border-2 transition-all ${color === c ? 'border-white scale-110' : 'border-transparent'}`}
                    style={{ backgroundColor: c }} />
                ))}
              </div>
            </div>
          </div>
          <div className="flex gap-2 mt-4">
            <button onClick={handleSubmit} disabled={!name.trim()}
              className="px-4 py-2 bg-indigo-500 hover:bg-indigo-600 disabled:opacity-30 text-white rounded-lg text-sm font-medium transition-colors">
              {editId ? 'Guardar' : 'Crear'}
            </button>
            <button onClick={resetForm} className="px-4 py-2 bg-white/10 hover:bg-white/20 text-white rounded-lg text-sm transition-colors">
              Cancelar
            </button>
          </div>
        </GlassContainer>
      )}

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[1,2,3].map(i => <div key={i} className="skeleton h-48 rounded-xl" />)}
        </div>
      ) : groups.length === 0 ? (
        <GlassContainer className="text-center py-12">
          <FolderOpen className="w-12 h-12 text-muted mx-auto mb-4" />
          <p className="text-muted text-lg">No hay grupos de análisis creados</p>
          <p className="text-muted text-sm mt-2">Crea un grupo de análisis para organizar tus análisis</p>
        </GlassContainer>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {groups.map((g: any) => (
            <GlassContainer key={g.id} className="relative group">
              {isAdmin && (
                <div className="absolute top-3 right-3 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button onClick={() => startEdit(g)} className="p-1.5 rounded-lg bg-white/10 hover:bg-white/20 text-white transition-colors">
                    <Edit3 className="w-3.5 h-3.5" />
                  </button>
                  <button onClick={() => { if (confirm('¿Eliminar este grupo de análisis?')) deleteMut.mutate(g.id) }}
                    className="p-1.5 rounded-lg bg-white/10 hover:bg-red-500/30 text-white transition-colors">
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              )}
              <div className="flex items-center gap-3 mb-4">
                <div className="w-4 h-4 rounded-full" style={{ backgroundColor: g.color }} />
                <h3 className="text-lg font-semibold text-white">{g.name}</h3>
              </div>
              {g.description && <p className="text-muted text-sm mb-4 line-clamp-2">{g.description}</p>}
              <div className="grid grid-cols-3 gap-3 mb-4">
                <Link to={`/processes?groupId=${g.id}`}
                  className="bg-white/5 rounded-lg p-2 text-center hover:bg-indigo-500/20 transition-colors block">
                  <p className="text-xl font-bold text-white">{g.project_count}</p>
                  <p className="text-xs text-muted">Análisis</p>
                </Link>
                <Link to={`/reports?groupId=${g.id}`}
                  className="bg-white/5 rounded-lg p-2 text-center hover:bg-indigo-500/20 transition-colors block">
                  <p className="text-xl font-bold text-white">{g.report_count}</p>
                  <p className="text-xs text-muted">Reportes</p>
                </Link>
                {g.avg_score !== null && g.avg_score !== undefined ? (
                  <div className={`rounded-lg p-2 text-center ${
                    g.avg_score >= 90 ? 'bg-green-500/20' :
                    g.avg_score >= 70 ? 'bg-emerald-500/20' :
                    g.avg_score >= 50 ? 'bg-yellow-500/20' :
                    'bg-red-500/20'
                  }`}>
                    <p className={`text-xl font-bold ${
                      g.avg_score >= 90 ? 'text-green-400' :
                      g.avg_score >= 70 ? 'text-emerald-400' :
                      g.avg_score >= 50 ? 'text-yellow-400' :
                      'text-red-400'
                    }`}>{g.avg_score}</p>
                    <p className={`text-xs ${
                      g.avg_score >= 90 ? 'text-green-400/70' :
                      g.avg_score >= 70 ? 'text-emerald-400/70' :
                      g.avg_score >= 50 ? 'text-yellow-400/70' :
                      'text-red-400/70'
                    }`}>Score</p>
                  </div>
                ) : (
                  <div className="rounded-lg p-2 text-center bg-white/5">
                    <p className="text-xl font-bold text-muted">—</p>
                    <p className="text-xs text-muted">Score</p>
                  </div>
                )}
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1 text-xs text-muted">
                  <Calendar className="w-3 h-3" />
                  {g.last_analysis ? new Date(g.last_analysis).toLocaleDateString() : 'Sin análisis'}
                </div>
                <Link to={`/groups/${g.id}`}
                  className="inline-flex items-center gap-1 text-xs text-indigo-400 hover:text-indigo-300 transition-colors">
                  <BarChart3 className="w-3 h-3" /> Dashboard
                </Link>
              </div>
            </GlassContainer>
          ))}
        </div>
      )}
    </div>
  )
}
