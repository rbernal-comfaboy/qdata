import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { FileText, ExternalLink, Trash2, AlertTriangle } from 'lucide-react'
import api from '../api/client'
import GlassContainer from '../components/layout/GlassContainer'
import { formatDate } from '../lib/utils'

export default function Reports() {
  const queryClient = useQueryClient()
  const [deletingId, setDeletingId] = useState<string | null>(null)

  const { data: reports, isLoading } = useQuery({
    queryKey: ['reports'],
    queryFn: () => api.get('/reports?limit=50').then((r) => r.data),
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
      <h1 className="text-3xl font-bold text-white mb-8">Reportes</h1>

      {isLoading ? (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="skeleton h-20 rounded-xl" />
          ))}
        </div>
      ) : reports?.length > 0 ? (
        <div className="space-y-4">
          {reports.map((r: any) => (
            <div key={r.id} className="relative">
              <Link to={`/reports/${r.id}`} className="block">
                <GlassContainer className="flex items-center justify-between hover:bg-white/10 transition-all cursor-pointer">
                  <div className="flex items-center gap-4">
                    <FileText className="w-8 h-8 text-indigo-400" />
                    <div>
                      <p className="text-white font-medium">
                        Reporte #{r.id.slice(0, 8)}
                      </p>
                      <p className="text-muted text-sm">{formatDate(r.executed_at)}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="text-right">
                      <p className={`text-xl font-bold ${r.score >= 70 ? 'text-green-400' : r.score >= 50 ? 'text-yellow-400' : 'text-red-400'}`}>
                        {r.score}
                      </p>
                      <span className={`badge badge-${r.label === 'excelente' ? 'success' : r.label === 'critico' ? 'error' : 'warning'}`}>
                        {r.label}
                      </span>
                    </div>
                    <ExternalLink className="w-5 h-5 text-muted" />
                  </div>
                </GlassContainer>
              </Link>
              {deletingId === r.id ? (
                <div className="absolute right-4 bottom-4 flex items-center gap-2 bg-red-500/20 border border-red-500/30 rounded-xl px-3 py-1.5 z-10">
                  <AlertTriangle className="w-4 h-4 text-red-400" />
                  <span className="text-sm text-red-300">¿Eliminar?</span>
                  <button onClick={() => deleteMutation.mutate(r.id)} disabled={deleteMutation.isPending}
                    className="btn-ghost text-xs text-red-400 font-semibold px-2">
                    {deleteMutation.isPending ? '...' : 'Sí'}
                  </button>
                  <button onClick={() => setDeletingId(null)} className="btn-ghost text-xs text-muted px-2">
                    No
                  </button>
                </div>
              ) : (
                <button onClick={(e) => { e.preventDefault(); setDeletingId(r.id) }}
                  className="absolute right-4 bottom-4 p-1.5 hover:bg-red-500/20 rounded-lg transition-colors text-muted hover:text-red-400 z-10"
                  title="Eliminar reporte">
                  <Trash2 className="w-4 h-4" />
                </button>
              )}
            </div>
          ))}
        </div>
      ) : (
        <GlassContainer className="text-center py-12">
          <FileText className="w-12 h-12 mx-auto mb-4 text-muted" />
          <p className="text-muted">No hay reportes aún</p>
          <Link to="/analyze" className="btn-primary inline-block mt-4">
            Ejecutar análisis
          </Link>
        </GlassContainer>
      )}
    </div>
  )
}
