import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Database, Plus, Edit3, Trash2, Copy, Save, X, AlertCircle, Upload, Loader2, CheckCircle2, XCircle, ChevronDown, ChevronUp, GripVertical,
} from 'lucide-react'
import { useDropzone } from 'react-dropzone'
import { DndContext, closestCenter, PointerSensor, useSensor, useSensors, type DragEndEvent } from '@dnd-kit/core'
import { arrayMove, SortableContext, useSortable, verticalListSortingStrategy } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import api from '../api/client'
import GlassContainer from '../components/layout/GlassContainer'
import { useAuthStore } from '../hooks/useAuth'

interface DBFields {
  host: string
  port: number | null
  database: string
  username: string
  password: string
  ssl: boolean
  instance: string
}

interface DSForm {
  name: string
  source_type: string
  db_fields: DBFields
  file_path: string
}

const defaultPorts: Record<string, number> = {
  postgresql: 5432, mysql: 3306, sqlserver: 1433, oracle: 1521, informix: 9088,
}

const defaultDBFields: DBFields = { host: '', port: null, database: '', username: '', password: '', ssl: false, instance: '' }

const emptyForm: DSForm = { name: '', source_type: 'postgresql', db_fields: { ...defaultDBFields }, file_path: '' }

const extMap: Record<string, string> = {
  csv: 'csv', json: 'json', xlsx: 'excel', xls: 'excel',
  parquet: 'parquet', pq: 'parquet', txt: 'csv',
}

const sourceLabels: Record<string, string> = {
  postgresql: 'PostgreSQL', mysql: 'MySQL', sqlserver: 'SQL Server',
  oracle: 'Oracle', informix: 'Informix', sqlite: 'SQLite',
  csv: 'CSV', excel: 'Excel', json: 'JSON', parquet: 'Parquet',
}

const dbTypes = ['postgresql', 'mysql', 'sqlserver', 'oracle', 'informix', 'sqlite']
const fileTypes = ['csv', 'excel', 'json', 'parquet']

function isDBType(t: string) { return dbTypes.includes(t) }
function isFileType(t: string) { return fileTypes.includes(t) }

function SortableConnectionItem({ ds, confirmDelete, handleEdit, handleDuplicate, setConfirmDelete, deleteMutation, isAdmin }: any) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: ds.id })
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
    zIndex: isDragging ? 50 : 'auto',
  }
  return (
    <div ref={setNodeRef} style={style}>
      <GlassContainer className="hover:bg-white/10 transition-all">
        <div className="flex items-center gap-4">
          <button {...attributes} {...listeners} className="cursor-grab active:cursor-grabbing p-1 text-muted hover:text-white shrink-0" title="Arrastrar para reordenar">
            <GripVertical className="w-4 h-4" />
          </button>
          <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${
            isFileType(ds.source_type) ? 'bg-amber-500/20' : 'bg-indigo-500/20'
          }`}>
            {isFileType(ds.source_type)
              ? <Upload className="w-5 h-5 text-amber-400" />
              : <Database className="w-5 h-5 text-indigo-400" />
            }
          </div>
          <div className="flex-1 min-w-0">
            <p className="font-semibold">{ds.name}</p>
            <p className="text-xs text-muted">
              {sourceLabels[ds.source_type] || ds.source_type}
              {ds.db_fields?.host && (ds.db_fields?.instance
                ? ` · ${ds.db_fields.host}\\${ds.db_fields.instance}`
                : ` · ${ds.db_fields.host}:${ds.db_fields.port || defaultPorts[ds.source_type] || ''}`)}
              {ds.db_fields?.database && `/ ${ds.db_fields.database}`}
              {ds.file_path && ` · ${ds.file_path.split('/').pop()}`}
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button onClick={() => handleEdit(ds)} className="btn-ghost p-2" title="Editar">
              <Edit3 className="w-4 h-4" />
            </button>
            <button onClick={() => handleDuplicate(ds)} className="btn-ghost p-2" title="Duplicar">
              <Copy className="w-4 h-4" />
            </button>
            {isAdmin && (
              <button onClick={() => setConfirmDelete(ds.id)} className="btn-ghost p-2 text-red-400" title="Eliminar">
                <Trash2 className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>
        {confirmDelete === ds.id && (
          <div className="mt-3 p-3 bg-red-500/10 border border-red-500/20 rounded-lg flex items-center gap-3 flex-wrap">
            <AlertCircle className="w-5 h-5 text-red-400 shrink-0" />
            <span className="text-sm text-red-300">¿Eliminar esta conexión?</span>
            <button onClick={() => deleteMutation.mutate(ds.id)} disabled={deleteMutation.isPending}
              className="btn-primary !bg-red-500 !bg-none text-xs py-1 px-3">Eliminar</button>
            <button onClick={() => setConfirmDelete(null)} className="btn-ghost text-xs py-1 px-3">Cancelar</button>
          </div>
        )}
      </GlassContainer>
    </div>
  )
}

export default function Connections() {
  const queryClient = useQueryClient()
  const currentUser = useAuthStore((s) => s.user)
  const isAdmin = currentUser?.role === 'admin'
  const [showForm, setShowForm] = useState(false)
  const [editId, setEditId] = useState<string | null>(null)
  const [form, setForm] = useState<DSForm>(emptyForm)
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null)
  const [sourceMode, setSourceMode] = useState<'database' | 'file'>('database')
  const [uploading, setUploading] = useState(false)
  const [testResult, setTestResult] = useState<{ success: boolean; tables?: string[]; error?: string } | null>(null)
  const [testing, setTesting] = useState(false)
  const [showTables, setShowTables] = useState(false)

  const { data: sources, isLoading } = useQuery({
    queryKey: ['datasources'],
    queryFn: () => api.get('/datasources').then((r) => r.data),
  })

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: { 'text/csv': ['.csv'], 'application/json': ['.json'], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'], 'application/octet-stream': ['.parquet'], 'text/plain': ['.txt'] },
    maxFiles: 1,
    onDrop: async (files) => {
      const f = files[0]
      if (!f) return
      setUploading(true)
      setTestResult(null)
      try {
        const fd = new FormData()
        fd.append('file', f)
        const res = await api.post('/upload/upload', fd)
        const ext = f.name.split('.').pop()?.toLowerCase() || 'csv'
        setForm({ ...form, source_type: extMap[ext] || 'csv', file_path: res.data.path })
      } finally { setUploading(false) }
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

  const reorderMutation = useMutation({
    mutationFn: (items: { id: string; sort_order: number }[]) => api.put('/datasources/reorder', { items }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['datasources'] }),
  })

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } })
  )

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event
    if (!over || active.id === over.id || !sources) return
    const ids = sources.map((ds: any) => ds.id)
    const oldIdx = ids.indexOf(active.id)
    const newIdx = ids.indexOf(over.id)
    if (oldIdx === -1 || newIdx === -1) return
    const reordered = arrayMove(ids, oldIdx, newIdx)
    reorderMutation.mutate(reordered.map((id, i) => ({ id: id as string, sort_order: i })))
  }

  const resetForm = () => {
    setShowForm(false); setEditId(null); setForm(emptyForm); setSourceMode('database'); setTestResult(null)
  }

  const handleEdit = (ds: any) => {
    const fields = ds.db_fields || (ds.config?.db_fields) || { ...defaultDBFields }
    const isFile = isFileType(ds.source_type)
    setForm({
      name: ds.name, source_type: ds.source_type,
      db_fields: { host: fields.host || '', port: fields.port ?? null, database: fields.database || '', username: fields.username || '', password: fields.password || '', ssl: fields.ssl || false, instance: fields.instance || '' },
      file_path: ds.file_path || '',
    })
    setSourceMode(isFile ? 'file' : 'database')
    setEditId(ds.id)
    setShowForm(true)
    setTestResult(null)
  }

  const handleSubmit = () => {
    const payload = { ...form }
    if (sourceMode === 'database') {
      payload.file_path = ''
    } else {
      payload.db_fields = { ...defaultDBFields }
    }
    if (editId) updateMutation.mutate({ ...payload, id: editId })
    else createMutation.mutate(payload)
  }

  const handleDuplicate = (ds: any) => {
    const isFile = isFileType(ds.source_type)
    const fields = isFile ? { ...defaultDBFields } : (ds.db_fields || ds.config?.db_fields || { ...defaultDBFields })
    setForm({
      name: `Copia de ${ds.name}`, source_type: ds.source_type,
      db_fields: { ...fields },
      file_path: ds.file_path || '',
    })
    setSourceMode(isFile ? 'file' : 'database')
    setEditId(null)
    setShowForm(true)
    setTestResult(null)
  }

  const handleTestConnection = async () => {
    setTesting(true)
    setTestResult(null)
    try {
      const payload = sourceMode === 'database'
        ? { source_type: form.source_type, db_fields: form.db_fields }
        : { source_type: form.source_type, file_path: form.file_path }
      const res = await api.post('/datasources/test', payload)
      setTestResult(res.data)
      if (res.data.success) setShowTables(true)
    } catch (e: any) {
      setTestResult({ success: false, error: e?.response?.data?.detail || 'Error de conexión' })
    } finally { setTesting(false) }
  }

  const updateDBField = (key: keyof DBFields, value: any) => {
    setForm({ ...form, db_fields: { ...form.db_fields, [key]: value } })
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-3xl font-bold">Conexiones</h1>
        <button onClick={() => { resetForm(); setShowForm(!showForm) }}
          className="btn-primary flex items-center gap-2">
          <Plus className="w-4 h-4" />
          {showForm ? 'Cancelar' : 'Nueva Conexión'}
        </button>
      </div>

      {showForm && (
        <GlassContainer className="mb-6">
          <h2 className="text-xl font-semibold mb-4">{editId ? 'Editar Conexión' : 'Nueva Conexión'}</h2>

          <div className="mb-4">
            <label className="block text-sm text-muted mb-1">Nombre</label>
            <input type="text" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="glass-input" placeholder="Ej: BD Producción, Cartera Clientes" />
          </div>

          <div className="flex gap-4 mb-6">
            <button onClick={() => { setSourceMode('database'); setTestResult(null) }}
              className={`flex-1 p-4 rounded-xl border transition-all ${
                sourceMode === 'database'
                  ? 'bg-indigo-500/20 border-indigo-400'
                  : 'bg-white/5 border-white/10 text-muted hover:bg-white/10'
              }`}>
              <Database className="w-6 h-6 mx-auto mb-2" />
              <span className="text-sm">Base de Datos</span>
            </button>
            <button onClick={() => { setSourceMode('file'); setTestResult(null) }}
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
                <label className="block text-sm text-muted mb-1">Motor de Base de Datos</label>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  {dbTypes.map((t) => (
                    <button key={t} onClick={() => { setForm({ ...form, source_type: t }); setTestResult(null); if (t === 'sqlite') updateDBField('port', null) }}
                      className={`p-3 rounded-xl border text-center text-sm transition-all ${
                        form.source_type === t
                          ? 'bg-indigo-500/20 border-indigo-400 font-semibold'
                          : 'bg-white/5 border-white/10 text-muted hover:bg-white/10'
                      }`}>
                      {sourceLabels[t]}
                    </button>
                  ))}
                </div>
              </div>

              {form.source_type !== 'sqlite' ? (
                <>
                  <div className="grid grid-cols-4 gap-4">
                    <div className={(form.source_type === 'sqlserver' || form.source_type === 'informix') ? 'col-span-2' : 'col-span-3'}>
                      <label className="block text-sm text-muted mb-1">Host / Servidor</label>
                      <input type="text" value={form.db_fields.host}
                        onChange={(e) => updateDBField('host', e.target.value)}
                        className="glass-input" placeholder="localhost, 192.168.1.100, db.example.com" />
                    </div>
                    {(form.source_type === 'sqlserver' || form.source_type === 'informix') && (
                      <div className="col-span-1">
                        <label className="block text-sm text-muted mb-1">Instancia</label>
                        <input type="text" value={form.db_fields.instance}
                          onChange={(e) => updateDBField('instance', e.target.value)}
                          className="glass-input" placeholder={form.source_type === 'informix' ? 'infonuevo_tcp' : 'MSSQLSERVER'} />
                      </div>
                    )}
                    <div>
                      <label className="block text-sm text-muted mb-1">Puerto</label>
                      <input type="number" value={form.db_fields.port ?? defaultPorts[form.source_type]}
                        onChange={(e) => updateDBField('port', e.target.value ? parseInt(e.target.value) : null)}
                        className="glass-input" placeholder={String(defaultPorts[form.source_type])} />
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm text-muted mb-1">Base de Datos</label>
                    <input type="text" value={form.db_fields.database}
                      onChange={(e) => updateDBField('database', e.target.value)}
                      className="glass-input" placeholder="mi_base_de_datos" />
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm text-muted mb-1">Usuario</label>
                      <input type="text" value={form.db_fields.username}
                        onChange={(e) => updateDBField('username', e.target.value)}
                        className="glass-input" placeholder="usuario" autoComplete="off" />
                    </div>
                    <div>
                      <label className="block text-sm text-muted mb-1">Contraseña</label>
                      <input type="password" value={form.db_fields.password}
                        onChange={(e) => updateDBField('password', e.target.value)}
                        className="glass-input" placeholder="••••••••" autoComplete="off" />
                    </div>
                  </div>

                  <label className="flex items-center gap-2 cursor-pointer">
                    <input type="checkbox" checked={form.db_fields.ssl}
                      onChange={(e) => updateDBField('ssl', e.target.checked)}
                      className="w-4 h-4 rounded accent-indigo-500" />
                    <span className="text-sm">Usar SSL/TLS</span>
                  </label>
                </>
              ) : (
                <div>
                  <label className="block text-sm text-muted mb-1">Ruta del archivo SQLite</label>
                  <input type="text" value={form.db_fields.database}
                    onChange={(e) => updateDBField('database', e.target.value)}
                    className="glass-input font-mono text-sm" placeholder="/path/to/database.db" />
                </div>
              )}
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
                  <CheckCircle2 className="w-8 h-8 mx-auto mb-2 text-green-400" />
                  <p className="font-medium">Archivo listo</p>
                  <p className="text-muted text-sm">{form.file_path.split('/').pop() || form.file_path}</p>
                  <p className="text-xs text-muted mt-1">Haz clic para cambiar</p>
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

          {/* Test Connection */}
          <div className="mt-5 flex flex-wrap items-center gap-3">
            <button onClick={handleTestConnection} disabled={testing || uploading}
              className="btn-ghost flex items-center gap-2 text-sm border border-white/10 hover:border-white/30">
              {testing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Database className="w-4 h-4" />}
              {testing ? 'Probando...' : 'Probar Conexión'}
            </button>
            <button onClick={handleSubmit} disabled={!form.name || createMutation.isPending || updateMutation.isPending || uploading}
              className="btn-primary flex items-center gap-2">
              <Save className="w-4 h-4" />
              {editId ? 'Actualizar' : 'Guardar Conexión'}
            </button>
            <button onClick={resetForm} className="btn-ghost flex items-center gap-2">
              <X className="w-4 h-4" /> Cancelar
            </button>
          </div>

          {testResult && (
            <div className={`mt-4 p-4 rounded-xl border ${
              testResult.success
                ? 'bg-green-500/10 border-green-500/30'
                : 'bg-red-500/10 border-red-500/30'
            }`}>
              <div className="flex items-center gap-2 mb-1">
                {testResult.success
                  ? <CheckCircle2 className="w-5 h-5 text-green-400" />
                  : <XCircle className="w-5 h-5 text-red-400" />
                }
                <span className={`font-semibold text-sm ${testResult.success ? 'text-green-300' : 'text-red-300'}`}>
                  {testResult.success ? 'Conexión exitosa' : 'Error de conexión'}
                </span>
              </div>
              {testResult.error && (
                <p className="text-sm text-red-300/80 mt-1 font-mono text-xs">{testResult.error}</p>
              )}
              {testResult.tables && testResult.tables.length > 0 && (
                <div className="mt-2">
                  <button onClick={() => setShowTables(!showTables)}
                    className="flex items-center gap-1 text-sm text-green-300/80 hover:text-green-200">
                    {showTables ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                    {testResult.tables.length} tabla(s) encontrada(s)
                  </button>
                  {showTables && (
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      {testResult.tables.map((t) => (
                        <span key={t} className="px-2.5 py-1 text-xs rounded-full bg-green-500/15 text-green-300 border border-green-500/20">
                          {t}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </GlassContainer>
      )}

      {isLoading ? (
        <div className="space-y-4">{[1, 2].map((i) => <div key={i} className="skeleton h-20 rounded-xl" />)}</div>
      ) : sources?.length > 0 ? (
        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
          <SortableContext items={sources.map((ds: any) => ds.id)} strategy={verticalListSortingStrategy}>
            <div className="space-y-3">
              {sources.map((ds: any) => (
                <SortableConnectionItem
                  key={ds.id}
                  ds={ds}
                  confirmDelete={confirmDelete}
                  handleEdit={handleEdit}
                  handleDuplicate={handleDuplicate}
                  setConfirmDelete={setConfirmDelete}
                  deleteMutation={deleteMutation}
                  isAdmin={isAdmin}
                />
              ))}
            </div>
          </SortableContext>
        </DndContext>
      ) : (
        <GlassContainer className="text-center py-16">
          <Database className="w-16 h-16 mx-auto mb-4 text-muted" />
          <p className="text-muted">No hay conexiones configuradas</p>
          <p className="text-xs text-muted mt-2">Crea una conexión a una base de datos o sube un archivo.</p>
        </GlassContainer>
      )}
    </div>
  )
}
