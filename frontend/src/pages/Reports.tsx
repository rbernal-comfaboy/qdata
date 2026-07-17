import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import { FileText, Trash2, AlertTriangle, Database, FileSpreadsheet } from 'lucide-react'
import api from '../api/client'
import { formatDate, getScoreColor } from '../lib/utils'
import { useAuthStore } from '../hooks/useAuth'

export default function Reports() {
  const queryClient = useQueryClient()
  const currentUser = useAuthStore((s) => s.user)
  const isAdmin = currentUser?.role === 'admin'
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [searchParams] = useSearchParams()
  const groupId = searchParams.get('groupId')

  const { data: reports, isLoading } = useQuery({
    queryKey: ['reports', groupId],
    queryFn: () => api.get('/reports?limit=50' + (groupId ? `&group_id=${groupId}` : '')).then((r) => r.data),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/reports/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reports'] })
      setDeletingId(null)
    },
    onError: (err: any) => {
      alert(err?.response?.data?.detail || 'Error al eliminar el reporte')
    },
  })

  return (
    <div>
      <h1 className="text-3xl font-bold text-white mb-8">
        Reportes
        {groupId && (
          <Link to="/groups" className="text-sm text-indigo-400 hover:text-indigo-300 ml-3 font-normal">
            ← Ver todos
          </Link>
        )}
      </h1>

      {isLoading ? (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="skeleton h-20 rounded-xl" />
          ))}
        </div>
      ) : reports?.length > 0 ? (
        <div className="overflow-x-auto rounded-xl border border-white/10">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="bg-white/5 border-b border-white/10">
                <th className="px-4 py-3 text-muted font-semibold">Reporte</th>
                <th className="px-4 py-3 text-muted font-semibold">Fecha de ejecución</th>
                <th className="px-4 py-3 text-muted font-semibold">Proceso</th>
                <th className="px-4 py-3 text-muted font-semibold">Fuente</th>
                <th className="px-4 py-3 text-muted font-semibold">Conexión</th>
                <th className="px-4 py-3 text-muted font-semibold text-right">Score</th>
                <th className="px-4 py-3 text-muted font-semibold text-right">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {reports.map((r: any) => (
                <tr key={r.id} className="border-b border-white/5 hover:bg-white/5 transition-colors">
                  <td className="px-4 py-3">
                    <Link to={`/reports/${r.id}`} className="flex items-center gap-2 text-white hover:text-indigo-300 transition-colors">
                      <FileText className="w-4 h-4 text-indigo-400 shrink-0" />
                      <span className="font-medium">#{r.id.slice(0, 8)}</span>
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-muted">{formatDate(r.executed_at)}</td>
                  <td className="px-4 py-3 text-white">{r.project_name || '—'}</td>
                  <td className="px-4 py-3">
                    <span className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full bg-white/5 text-muted">
                      {r.source_type === 'database' ? (
                        <Database className="w-3 h-3" />
                      ) : (
                        <FileSpreadsheet className="w-3 h-3" />
                      )}
                      {r.source_label || '—'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-muted text-xs max-w-[200px] truncate" title={r.connection_label || ''}>
                    {r.connection_label || '—'}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <span className={`text-lg font-bold ${getScoreColor(r.score ?? 0)}`}>
                      {r.score != null ? Number(r.score).toFixed(2) : '—'}
                    </span>
                    {r.label && (
                      <span className={`ml-2 badge badge-${r.label === 'excelente' ? 'success' : r.label === 'critico' ? 'error' : 'warning'}`}>
                        {r.label}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {isAdmin && (deletingId === r.id ? (
                      <div className="inline-flex items-center gap-1 bg-red-500/20 border border-red-500/30 rounded-lg px-2 py-1">
                        <AlertTriangle className="w-3 h-3 text-red-400" />
                        <span className="text-xs text-red-300">¿Eliminar?</span>
                        <button onClick={() => deleteMutation.mutate(r.id)} disabled={deleteMutation.isPending}
                          className="text-xs text-red-400 font-semibold px-1 hover:underline">
                          {deleteMutation.isPending ? '...' : 'Sí'}
                        </button>
                        <button onClick={() => setDeletingId(null)} className="text-xs text-muted px-1 hover:underline">
                          No
                        </button>
                      </div>
                    ) : isAdmin ? (
                      <button onClick={() => setDeletingId(r.id)}
                        className="p-1.5 hover:bg-red-500/20 rounded-lg transition-colors text-muted hover:text-red-400"
                        title="Eliminar reporte">
                        <Trash2 className="w-4 h-4" />
                      </button>
                    ) : null)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="rounded-xl border border-white/10 bg-white/5 text-center py-12">
          <FileText className="w-12 h-12 mx-auto mb-4 text-muted" />
          <p className="text-muted">No hay reportes aún</p>
          <Link to="/analyze" className="btn-primary inline-block mt-4">
            Ejecutar análisis
          </Link>
        </div>
      )}
    </div>
  )
}
