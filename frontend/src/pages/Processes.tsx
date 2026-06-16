import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import {
  FolderOpen, Play, Trash2, Clock, ExternalLink,
  Search, Database, FileText, AlertCircle, CheckCircle, Loader2,
} from 'lucide-react'
import api from '../api/client'
import GlassContainer from '../components/layout/GlassContainer'
import { formatDate, getScoreLabel } from '../lib/utils'

const sourceIcons: Record<string, any> = {
  postgresql: Database, mysql: Database, sqlserver: Database, sqlite: Database,
  csv: FileText, excel: FileText, json: FileText, parquet: FileText, txt: FileText,
}

export default function Processes() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null)

  const { data: processes, isLoading } = useQuery({
    queryKey: ['processes'],
    queryFn: () => api.get('/processes').then((r) => r.data),
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
        <Link to="/analyze" className="btn-primary flex items-center gap-2">
          <Play className="w-4 h-4" />
          Nuevo Análisis
        </Link>
      </div>

      {isLoading ? (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => <div key={i} className="skeleton h-28 rounded-xl" />)}
        </div>
      ) : processes?.length > 0 ? (
        <div className="space-y-4">
          {processes.map((p: any) => {
            const SourceIcon = sourceIcons[p.source_config?.source_type] || Database
            const latest = p.latest_report
            const hasTask = p.scheduled_task
            return (
              <GlassContainer key={p.id} className="hover:bg-white/10 transition-all">
                <div className="flex items-start gap-4">
                  <div className="w-10 h-10 rounded-xl bg-indigo-500/20 flex items-center justify-center flex-shrink-0">
                    <SourceIcon className="w-5 h-5 text-indigo-400" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3">
                      <h3 className="text-lg font-semibold">{p.name}</h3>
                      {p.status === 'running' && (
                        <span className="badge flex items-center gap-1 bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                          <Loader2 className="w-3 h-3 animate-spin" />
                          Ejecutando
                        </span>
                      )}
                      {hasTask && (
                        <span className="badge badge-info flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          Programado
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-muted mt-1">
                      {p.source_config?.source_type} · Creado {formatDate(p.created_at)}
                      {p.rules_config?.length > 0 && ` · ${p.rules_config.length} reglas`}
                    </p>

                    {p.status === 'running' && p.progress && (() => {
                      const prog = p.progress
                      const total = prog.total || 0
                      const completed = prog.completed || 0
                      const pct = total > 0 ? Math.round((completed / total) * 100) : 0
                      return (
                        <div className="mt-3 space-y-2">
                          <div className="flex justify-between text-xs text-muted">
                            <span>{total > 0 ? `${completed} / ${total} reglas` : 'Iniciando...'}</span>
                            <span>{total > 0 ? `${pct}%` : ''}</span>
                          </div>
                          <div className="h-2 bg-white/10 rounded-full overflow-hidden">
                            <div className="h-full bg-gradient-to-r from-indigo-500 to-purple-500 rounded-full transition-all duration-500"
                              style={{ width: `${total > 0 ? Math.max(pct, 5) : 5}%` }} />
                          </div>
                          {prog.current_rule && (
                            <div className="flex items-center gap-1.5 text-xs bg-indigo-500/10 border border-indigo-500/20 rounded-lg px-2.5 py-1.5">
                              <Loader2 className="w-3 h-3 animate-spin text-indigo-400 shrink-0" />
                              <span className="text-indigo-300 font-medium">{prog.current_rule}</span>
                            </div>
                          )}
                          {prog.rules?.length > 0 && (
                            <div className="max-h-20 overflow-y-auto space-y-0.5 text-[11px]">
                              {prog.rules.map((r: any, i: number) => (
                                <div key={i} className={`flex items-center gap-1.5 px-2 py-1 rounded ${
                                  r.status === 'running' ? 'bg-indigo-500/10' :
                                  r.status === 'done' ? 'bg-green-500/5' :
                                  r.status === 'failed' ? 'bg-red-500/10' : ''
                                }`}>
                                  {r.status === 'pending' && <div className="w-2.5 h-2.5 rounded-full border border-white/20 shrink-0" />}
                                  {r.status === 'running' && <Loader2 className="w-2.5 h-2.5 animate-spin text-indigo-400 shrink-0" />}
                                  {r.status === 'done' && <CheckCircle className="w-2.5 h-2.5 text-green-400 shrink-0" />}
                                  {r.status === 'failed' && <AlertCircle className="w-2.5 h-2.5 text-red-400 shrink-0" />}
                                  <span className={`truncate ${
                                    r.status === 'running' ? 'text-indigo-300 font-medium' :
                                    r.status === 'done' ? 'text-green-300' :
                                    r.status === 'failed' ? 'text-red-300' : 'text-muted'
                                  }`}>{r.label}</span>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      )
                    })()}

                    {latest ? (
                      <div className="flex items-center gap-4 mt-3">
                        <span className={`text-lg font-bold ${latest.score >= 70 ? 'text-green-400' : latest.score >= 50 ? 'text-yellow-400' : 'text-red-400'}`}>
                          {latest.score}
                        </span>
                        <span className={`badge badge-${latest.label === 'excelente' ? 'success' : latest.label === 'critico' ? 'error' : 'warning'}`}>
                          {latest.label}
                        </span>
                        <span className="text-xs text-muted">{formatDate(latest.executed_at)}</span>
                      </div>
                    ) : (
                      <p className="text-xs text-muted mt-2">Sin ejecutar aún</p>
                    )}
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    {p.status !== 'running' && (
                      <button
                        onClick={() => rerunMutation.mutate(p.id)}
                        disabled={rerunMutation.isPending}
                        className="btn-ghost p-2"
                        title="Ejecutar ahora"
                      >
                        <Play className="w-4 h-4" />
                      </button>
                    )}
                    <Link to={`/processes/${p.id}`} className="btn-ghost p-2" title="Ver detalle">
                      <ExternalLink className="w-4 h-4" />
                    </Link>
                    <button
                      onClick={() => setConfirmDelete(p.id)}
                      className="btn-ghost p-2 text-red-400 hover:text-red-300"
                      title="Eliminar"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
                {confirmDelete === p.id && (
                  <div className="mt-4 p-3 bg-red-500/10 border border-red-500/20 rounded-lg flex items-center gap-3">
                    <AlertCircle className="w-5 h-5 text-red-400 shrink-0" />
                    <span className="text-sm text-red-300">¿Eliminar este proceso? Los reportes y tareas asociados también se borrarán.</span>
                    <button
                      onClick={() => deleteMutation.mutate(p.id)}
                      disabled={deleteMutation.isPending}
                      className="btn-primary !bg-red-500 !bg-none text-xs py-1 px-3"
                    >
                      {deleteMutation.isPending ? 'Eliminando...' : 'Eliminar'}
                    </button>
                    <button
                      onClick={() => setConfirmDelete(null)}
                      className="btn-ghost text-xs py-1 px-3"
                    >
                      Cancelar
                    </button>
                  </div>
                )}
              </GlassContainer>
            )
          })}
        </div>
      ) : (
        <GlassContainer className="text-center py-16">
          <FolderOpen className="w-16 h-16 mx-auto mb-4 text-muted" />
          <p className="text-muted text-lg mb-2">No hay procesos de análisis</p>
          <p className="text-muted text-sm mb-6">Ejecuta tu primer análisis para verlo aquí</p>
          <Link to="/analyze" className="btn-primary inline-flex items-center gap-2">
            <Play className="w-4 h-4" />
            Nuevo Análisis
          </Link>
        </GlassContainer>
      )}
    </div>
  )
}
