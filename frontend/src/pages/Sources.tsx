import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import {
  BookOpen, Plus, Trash2, X, AlertCircle, Database, Loader2, Eye, ListChecks,
} from 'lucide-react'
import api from '../api/client'
import GlassContainer from '../components/layout/GlassContainer'

const sourceLabels: Record<string, string> = {
  postgresql: 'PostgreSQL', mysql: 'MySQL', sqlserver: 'SQL Server',
  oracle: 'Oracle', informix: 'Informix', sqlite: 'SQLite',
  csv: 'CSV', excel: 'Excel', json: 'JSON', parquet: 'Parquet',
}

export default function SourcesPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null)
  const [previewId, setPreviewId] = useState<string | null>(null)
  const [previewData, setPreviewData] = useState<any>(null)
  const [previewLoading, setPreviewLoading] = useState(false)

  const { data: sources, isLoading } = useQuery({
    queryKey: ['sources'],
    queryFn: () => api.get('/sources').then(r => r.data),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/sources/${id}`),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['sources'] }); setConfirmDelete(null) },
  })

  const handlePreview = async (srcId: string) => {
    if (previewId === srcId && previewData) { setPreviewId(null); setPreviewData(null); return }
    setPreviewLoading(true); setPreviewId(srcId); setPreviewData(null)
    try {
      const res = await api.post(`/sources/${srcId}/preview`)
      setPreviewData(res.data)
    } catch { setPreviewId(null) } finally { setPreviewLoading(false) }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold">Fuentes de Datos</h1>
          <p className="text-sm text-muted mt-1">Gestiona las fuentes de datos para tus análisis</p>
        </div>
        <button onClick={() => navigate('/datasources/new')}
          className="btn-primary flex items-center gap-2">
          <Plus className="w-4 h-4" /> Nueva Fuente
        </button>
      </div>

      {isLoading ? (
        <div className="space-y-3">{[1, 2, 3].map(i => <div key={i} className="skeleton h-16 rounded-xl" />)}</div>
      ) : sources?.length > 0 ? (
        <div className="space-y-2">
          {sources.map((s: any) => (
            <GlassContainer key={s.id} className="hover:bg-white/10 transition-all">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-lg bg-indigo-500/15 flex items-center justify-center shrink-0">
                  <BookOpen className="w-4.5 h-4.5 text-indigo-400" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="font-semibold text-sm">{s.name}</p>
                    <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-white/10 text-muted">{sourceLabels[s.source_type] || s.source_type}</span>
                    {s.row_limit && <span className="text-[10px] text-muted">límite {s.row_limit}</span>}
                  </div>
                  <div className="flex items-center gap-2 text-[11px] text-muted flex-wrap mt-0.5">
                    {s.query ? (
                      <code className="text-indigo-300/70">{s.query.slice(0, 100)}</code>
                    ) : (
                      <span>Archivo completo</span>
                    )}
                    {s.total_rows != null && (
                      <span className="flex items-center gap-1 bg-white/5 px-1.5 py-0.5 rounded">
                        <Database className="w-3 h-3" /> {s.total_rows.toLocaleString()} registros
                      </span>
                    )}
                    {s.columns_count != null && (
                      <span className="flex items-center gap-1 bg-white/5 px-1.5 py-0.5 rounded">
                        <ListChecks className="w-3 h-3" /> {s.columns_count} col(s)
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-1 shrink-0">
                  <button onClick={() => handlePreview(s.id)} disabled={previewLoading && previewId === s.id}
                    className="btn-ghost p-1.5" title="Previsualizar">
                    {previewLoading && previewId === s.id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Database className="w-3.5 h-3.5" />}
                  </button>
                  <button onClick={() => navigate(`/datasources/${s.id}/edit`)}
                    className="btn-ghost p-1.5" title="Editar">
                    <Eye className="w-3.5 h-3.5" />
                  </button>
                  <button onClick={() => setConfirmDelete(s.id)} className="btn-ghost p-1.5 text-red-400" title="Eliminar">
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              {previewId === s.id && previewData && (
                <div className="mt-3 border-t border-white/10 pt-3">
                  <div className="flex items-center justify-between mb-2">
                    <p className="text-xs text-muted">
                      {previewData.total_rows.toLocaleString()} filas · {previewData.columns.length} columnas
                    </p>
                    <button onClick={() => { setPreviewId(null); setPreviewData(null) }} className="btn-ghost p-1">
                      <X className="w-3 h-3" />
                    </button>
                  </div>
                  <div className="max-h-64 overflow-auto border border-white/10 rounded-xl">
                    <table className="w-full text-xs border-collapse">
                      <thead className="sticky top-0 bg-[#1a1a2e]">
                        <tr className="border-b border-white/10">
                          {previewData.columns.map((col: string, i: number) => (
                            <th key={i} className="text-left py-1.5 px-2 font-semibold text-indigo-300 whitespace-nowrap">{col}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {previewData.rows.map((row: any[], ri: number) => (
                          <tr key={ri} className="border-b border-white/5 hover:bg-white/5">
                            {row.map((val: any, ci: number) => (
                              <td key={ci} className="py-1 px-2 truncate max-w-[140px]">
                                {val === null ? <span className="text-red-400">NULL</span> : String(val)}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {confirmDelete === s.id && (
                <div className="mt-3 p-2 bg-red-500/10 border border-red-500/20 rounded-lg flex items-center gap-2 flex-wrap">
                  <AlertCircle className="w-4 h-4 text-red-400 shrink-0" />
                  <span className="text-xs text-red-300">¿Eliminar esta fuente?</span>
                  <button onClick={() => deleteMutation.mutate(s.id)} disabled={deleteMutation.isPending}
                    className="btn-primary !bg-red-500 !bg-none text-[10px] py-1 px-2">Eliminar</button>
                  <button onClick={() => setConfirmDelete(null)} className="btn-ghost text-[10px] py-1 px-2">Cancelar</button>
                </div>
              )}
            </GlassContainer>
          ))}
        </div>
      ) : (
        <GlassContainer className="text-center py-12">
          <BookOpen className="w-12 h-12 mx-auto mb-3 text-muted" />
          <p className="text-muted text-sm">No hay fuentes de datos configuradas</p>
          <p className="text-xs text-muted mt-1">Crea una conexión primero, luego una fuente de datos.</p>
        </GlassContainer>
      )}
    </div>
  )
}
