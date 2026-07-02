import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Database, Plus, Edit3, Trash2, Save, X, AlertCircle, Upload, Loader2
} from 'lucide-react'
import { useDropzone } from 'react-dropzone'
import api from '../api/client'
import GlassContainer from '../components/layout/GlassContainer'

interface DSForm {
  name: string
  source_type: string
  connection_string: string
  file_path: string
}

const emptyForm: DSForm = { name: '', source_type: 'postgresql', connection_string: '', file_path: '' }

export default function DataSources() {
  const queryClient = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [editId, setEditId] = useState<string | null>(null)
  const [form, setForm] = useState<DSForm>(emptyForm)
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null)
  const [sourceMode, setSourceMode] = useState<'database' | 'file'>('database')
  const [uploading, setUploading] = useState(false)

  const { data: sources, isLoading } = useQuery({
    queryKey: ['datasources'],
    queryFn: () => api.get('/datasources').then((r) => r.data),
  })

  const extMap: Record<string, string> = {
    csv: 'csv', json: 'json', xlsx: 'excel', xls: 'excel',
    parquet: 'parquet', pq: 'parquet', txt: 'csv',
  }

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: { 'text/csv': ['.csv'], 'application/json': ['.json'], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'], 'application/octet-stream': ['.parquet'], 'text/plain': ['.txt'] },
    maxFiles: 1,
    onDrop: async (files) => {
      const f = files[0]
      if (!f) return
      setUploading(true)
      try {
        const fd = new FormData()
        fd.append('file', f)
        const res = await api.post('/upload/upload', fd)
        const ext = f.name.split('.').pop()?.toLowerCase() || 'csv'
        setForm({ ...form, source_type: extMap[ext] || 'csv', file_path: res.data.path })
      } finally {
        setUploading(false)
      }
    },
  })

  const createMutation = useMutation({
    mutationFn: (data: DSForm) => api.post('/datasources', data),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['datasources'] }); resetForm() },
  })

  const updateMutation = useMutation({
    mutationFn: (data: DSForm & { id: string }) => api.put(`/datasources/${data.id}`, data),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['datasources'] }); resetForm() },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/datasources/${id}`),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['datasources'] }); setConfirmDelete(null) },
  })

  const resetForm = () => {
    setShowForm(false); setEditId(null); setForm(emptyForm); setSourceMode('database')
  }

  const handleEdit = (ds: any) => {
    setForm({ name: ds.name, source_type: ds.source_type, connection_string: ds.connection_string || '', file_path: ds.file_path || '' })
    setSourceMode(ds.file_path ? 'file' : 'database')
    setEditId(ds.id)
    setShowForm(true)
  }

  const handleSubmit = () => {
    if (editId) updateMutation.mutate({ ...form, id: editId })
    else createMutation.mutate(form)
  }

  const sourceLabels: Record<string, string> = {
    postgresql: 'PostgreSQL', mysql: 'MySQL', sqlserver: 'SQL Server',
    oracle: 'Oracle', sqlite: 'SQLite',
    csv: 'CSV', excel: 'Excel', json: 'JSON', parquet: 'Parquet',
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-3xl font-bold">Fuentes de Datos</h1>
        <button onClick={() => { resetForm(); setShowForm(!showForm) }}
          className="btn-primary flex items-center gap-2">
          <Plus className="w-4 h-4" />
          {showForm ? 'Cancelar' : 'Nueva Fuente'}
        </button>
      </div>

      {showForm && (
        <GlassContainer className="mb-6">
          <h2 className="text-xl font-semibold mb-4">{editId ? 'Editar Fuente' : 'Nueva Fuente de Datos'}</h2>

          <div className="mb-4">
            <label className="block text-sm text-muted mb-1">Nombre</label>
            <input type="text" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="glass-input" placeholder="Ej: BD Producción" />
          </div>

          <div className="flex gap-4 mb-6">
            <button onClick={() => setSourceMode('database')}
              className={`flex-1 p-4 rounded-xl border transition-all ${
                sourceMode === 'database'
                  ? 'bg-indigo-500/20 border-indigo-400'
                  : 'bg-white/5 border-white/10 text-muted hover:bg-white/10'
              }`}>
              <Database className="w-6 h-6 mx-auto mb-2" />
              <span className="text-sm">Base de Datos</span>
            </button>
            <button onClick={() => setSourceMode('file')}
              className={`flex-1 p-4 rounded-xl border transition-all ${
                sourceMode === 'file'
                  ? 'bg-indigo-500/20 border-indigo-400'
                  : 'bg-white/5 border-white/10 text-muted hover:bg-white/10'
              }`}>
              <Upload className="w-6 h-6 mx-auto mb-2" />
              <span className="text-sm">Archivo</span>
            </button>
          </div>

          {sourceMode === 'database' ? (
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-muted mb-1">Tipo de BD</label>
                  <select value={form.source_type} onChange={(e) => setForm({ ...form, source_type: e.target.value })}
                  className="glass-input">
                  <option value="postgresql">PostgreSQL</option>
                  <option value="mysql">MySQL</option>
                  <option value="sqlserver">SQL Server</option>
                  <option value="oracle">Oracle</option>
                  <option value="sqlite">SQLite</option>
                </select>
              </div>
              <div>
                <label className="block text-sm text-muted mb-1">Connection String</label>
                <input type="text" value={form.connection_string}
                  onChange={(e) => setForm({ ...form, connection_string: e.target.value })}
                  className="glass-input font-mono text-sm" placeholder="postgresql://user:pass@host:5432/db" />
              </div>
            </div>
          ) : (
            <div {...getRootProps()}
              className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all ${
                isDragActive ? 'border-indigo-400 bg-indigo-500/10' : 'border-white/20 hover:border-white/40'
              }`}>
              <input {...getInputProps()} />
              {uploading ? (
                <div><Loader2 className="w-8 h-8 mx-auto mb-2 animate-spin text-muted" /><p className="text-muted text-sm">Subiendo...</p></div>
              ) : form.file_path ? (
                <div>
                  <p className="font-medium">Archivo listo</p>
                  <p className="text-muted text-sm">{form.file_path.split('/').pop() || form.file_path}</p>
                </div>
              ) : (
                <div>
                  <Upload className="w-8 h-8 mx-auto mb-2 text-muted" />
                  <p className="">Arrastra un archivo o haz clic</p>
                  <p className="text-muted text-sm mt-1">CSV, Excel, JSON, Parquet o TXT</p>
                </div>
              )}
            </div>
          )}

          <div className="mt-4 flex gap-3">
            <button onClick={handleSubmit} disabled={!form.name || createMutation.isPending || updateMutation.isPending || uploading}
              className="btn-primary flex items-center gap-2">
              <Save className="w-4 h-4" />
              {editId ? 'Actualizar' : 'Crear'}
            </button>
            <button onClick={resetForm} className="btn-ghost flex items-center gap-2">
              <X className="w-4 h-4" /> Cancelar
            </button>
          </div>
        </GlassContainer>
      )}

      {isLoading ? (
        <div className="space-y-4">{[1, 2].map((i) => <div key={i} className="skeleton h-20 rounded-xl" />)}</div>
      ) : sources?.length > 0 ? (
        <div className="space-y-3">
          {sources.map((ds: any) => (
            <GlassContainer key={ds.id} className="hover:bg-white/10 transition-all">
              <div className="flex items-center gap-4">
                <Database className="w-8 h-8 text-indigo-400 shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="font-semibold">{ds.name}</p>
                  <p className="text-xs text-muted">
                    {sourceLabels[ds.source_type] || ds.source_type}
                    {ds.connection_string && ` · ${ds.connection_string.slice(0, 60)}...`}
                    {ds.file_path && ` · ${ds.file_path.split('/').pop()}`}
                  </p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <button onClick={() => handleEdit(ds)} className="btn-ghost p-2" title="Editar">
                    <Edit3 className="w-4 h-4" />
                  </button>
                  <button onClick={() => setConfirmDelete(ds.id)} className="btn-ghost p-2 text-red-400" title="Eliminar">
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
              {confirmDelete === ds.id && (
                <div className="mt-3 p-3 bg-red-500/10 border border-red-500/20 rounded-lg flex items-center gap-3 flex-wrap">
                  <AlertCircle className="w-5 h-5 text-red-400 shrink-0" />
                  <span className="text-sm text-red-300">¿Eliminar esta fuente?</span>
                  <button onClick={() => deleteMutation.mutate(ds.id)} disabled={deleteMutation.isPending}
                    className="btn-primary !bg-red-500 !bg-none text-xs py-1 px-3">Eliminar</button>
                  <button onClick={() => setConfirmDelete(null)} className="btn-ghost text-xs py-1 px-3">Cancelar</button>
                </div>
              )}
            </GlassContainer>
          ))}
        </div>
      ) : (
        <GlassContainer className="text-center py-16">
          <Database className="w-16 h-16 mx-auto mb-4 text-muted" />
          <p className="text-muted">No hay fuentes de datos configuradas</p>
        </GlassContainer>
      )}
    </div>
  )
}
