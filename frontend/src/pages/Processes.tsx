import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import {
  FolderOpen, Play, Trash2, Clock, ExternalLink,
  Database, FileText, AlertTriangle, CheckCircle, Loader2,
} from 'lucide-react'
import api from '../api/client'
import { formatDate, getScoreColor } from '../lib/utils'

export default function Processes() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null)
  const [searchParams] = useSearchParams()
  const groupId = searchParams.get('groupId')

  const { data: processes, isLoading } = useQuery({
    queryKey: ['processes', groupId],
    queryFn: () => api.get('/processes' + (groupId ? `?group_id=${groupId}` : '')).then((r) => r.data),
    refetchInterval: (query) => {
      const data = query.state.data
      if (Array.isArray(data) && data.some((p: any) => p.status === 'running')) return 2000
      return false
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/processes/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['processes'] })
      setConfirmDelete(null)
    },
  })

  const rerunMutation = useMutation({
    mutationFn: (id: string) => api.post(`/processes/${id}/rerun`),
    onSuccess: (_res, id) => {
      queryClient.invalidateQueries({ queryKey: ['processes'] })
      navigate(`/processes/${id}`)
    },
  })

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-3xl font-bold">Procesos de Análisis</h1>
        {groupId && (
          <Link to="/groups" className="text-sm text-indigo-400 hover:text-indigo-300 ml-3">
            ← Ver todos
          </Link>
        )}
        <Link to="/analyze" className="btn-primary flex items-center gap-2">
          <Play className="w-4 h-4" />
          Nuevo Análisis
        </Link>
      </div>

      {isLoading ? (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => <div key={i} className="skeleton h-12 rounded-xl" />)}
        </div>
      ) : processes?.length > 0 ? (
        <div className="overflow-x-auto rounded-xl border border-white/10">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="bg-white/5 border-b border-white/10">
                <th className="px-4 py-3 text-muted font-semibold">Proceso</th>
                <th className="px-4 py-3 text-muted font-semibold">Estado</th>
                <th className="px-4 py-3 text-muted font-semibold">Fuente</th>
                <th className="px-4 py-3 text-muted font-semibold">Conexión</th>
                <th className="px-4 py-3 text-muted font-semibold">Reglas</th>
                <th className="px-4 py-3 text-muted font-semibold">Score</th>
                <th className="px-4 py-3 text-muted font-semibold">Fecha</th>
                <th className="px-4 py-3 text-muted font-semibold text-right">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {processes.map((p: any) => {
                const latest = p.latest_report
                const isRunning = p.status === 'running' || p.status === 'loading'
                const hasTask = p.scheduled_task
                return (
                  <tr key={p.id} className="border-b border-white/5 hover:bg-white/5 transition-colors">
                    <td className="px-4 py-3">
                      <Link to={`/processes/${p.id}`} className="flex items-center gap-2 text-white hover:text-indigo-300 transition-colors">
                        <Database className="w-4 h-4 text-indigo-400 shrink-0" />
                        <span className="font-medium">{p.name}</span>
                      </Link>
                    </td>
                    <td className="px-4 py-3">
                      {isRunning ? (
                        <span className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                          <Loader2 className="w-3 h-3 animate-spin" />
                          Ejecutando
                        </span>
                      ) : hasTask ? (
                        <span className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full bg-blue-500/20 text-blue-300 border border-blue-500/30">
                          <Clock className="w-3 h-3" />
                          Programado
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full bg-green-500/10 text-green-400 border border-green-500/20">
                          <CheckCircle className="w-3 h-3" />
                          Completado
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-white">{p.source_label || '—'}</td>
                    <td className="px-4 py-3 text-muted text-xs">{p.connection_label || '—'}</td>
                    <td className="px-4 py-3 text-muted text-xs">{p.rules_config?.length || 0} reglas</td>
                    <td className="px-4 py-3 text-right">
                      {latest ? (
                        <span className={`text-lg font-bold ${getScoreColor(latest.score ?? 0)}`}>
                          {latest.score}
                        </span>
                      ) : (
                        <span className="text-muted">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-muted text-xs">{formatDate(p.created_at)}</td>
                    <td className="px-4 py-3 text-right">
                      <div className="inline-flex items-center gap-1">
                        {p.status !== 'running' && (
                          <button
                            onClick={() => rerunMutation.mutate(p.id)}
                            disabled={rerunMutation.isPending}
                            className="p-1.5 hover:bg-white/10 rounded-lg transition-colors text-muted hover:text-white"
                            title="Ejecutar ahora"
                          >
                            <Play className="w-4 h-4" />
                          </button>
                        )}
                        <Link to={`/processes/${p.id}`} className="p-1.5 hover:bg-white/10 rounded-lg transition-colors text-muted hover:text-white" title="Ver detalle">
                          <ExternalLink className="w-4 h-4" />
                        </Link>
                        {confirmDelete === p.id ? (
                          <div className="inline-flex items-center gap-1 bg-red-500/20 border border-red-500/30 rounded-lg px-2 py-1">
                            <AlertTriangle className="w-3 h-3 text-red-400" />
                            <button onClick={() => deleteMutation.mutate(p.id)} disabled={deleteMutation.isPending}
                              className="text-xs text-red-400 font-semibold px-1 hover:underline">
                              {deleteMutation.isPending ? '...' : 'Sí'}
                            </button>
                            <button onClick={() => setConfirmDelete(null)} className="text-xs text-muted px-1 hover:underline">
                              No
                            </button>
                          </div>
                        ) : (
                          <button
                            onClick={() => setConfirmDelete(p.id)}
                            className="p-1.5 hover:bg-red-500/20 rounded-lg transition-colors text-muted hover:text-red-400"
                            title="Eliminar"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="rounded-xl border border-white/10 bg-white/5 text-center py-16">
          <FolderOpen className="w-16 h-16 mx-auto mb-4 text-muted" />
          <p className="text-muted text-lg mb-2">No hay procesos de análisis</p>
          <p className="text-muted text-sm mb-6">Ejecuta tu primer análisis para verlo aquí</p>
          <Link to="/analyze" className="btn-primary inline-flex items-center gap-2">
            <Play className="w-4 h-4" />
            Nuevo Análisis
          </Link>
        </div>
      )}
    </div>
  )
}
