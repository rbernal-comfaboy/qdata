import { useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft, XCircle, AlertTriangle, Info,
  FileDown, FileText, ExternalLink, Clock, Trash2,
} from 'lucide-react'
import api from '../api/client'
import GlassContainer from '../components/layout/GlassContainer'
import QualityGauge from '../components/charts/QualityGauge'
import { formatDate, getScoreLabel } from '../lib/utils'

const severityIcons: Record<string, any> = {
  error: XCircle,
  warning: AlertTriangle,
  info: Info,
}

const severityColors: Record<string, string> = {
  error: 'text-red-400',
  warning: 'text-yellow-400',
  info: 'text-blue-400',
}

export default function ReportDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [confirmDelete, setConfirmDelete] = useState(false)

  const { data: report, isLoading } = useQuery({
    queryKey: ['report', id],
    queryFn: () => api.get(`/reports/${id}`).then((r) => r.data),
    enabled: !!id,
  })

  const deleteMutation = useMutation({
    mutationFn: () => api.delete(`/reports/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reports'] })
      navigate('/reports')
    },
    onError: (err: any) => {
      alert(err?.response?.data?.detail || 'Error al eliminar el reporte')
    },
  })

  const _download = async (endpoint: string, ext: string) => {
    try {
      const res = await api.get(`/reports/${id}${endpoint}`, { responseType: 'blob' })
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      a.download = `reporte_${id?.slice(0, 8)}.${ext}`
      a.click()
      URL.revokeObjectURL(url)
    } catch (err: any) {
      let msg = 'Error al descargar'
      try {
        if (err?.response?.data instanceof Blob) {
          const text = await err.response.data.text()
          const json = JSON.parse(text)
          msg = json.detail || msg
        }
      } catch {}
      alert(msg)
    }
  }

  const handleExportExcel = () => _download('/export/excel', 'xlsx')
  const handleExportPdf = () => _download('/export/pdf', 'pdf')

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="skeleton h-48 rounded-xl" />
        <div className="skeleton h-64 rounded-xl" />
      </div>
    )
  }

  if (!report) {
    return (
      <GlassContainer className="text-center py-12">
        <p className="text-muted">Reporte no encontrado</p>
        <Link to="/reports" className="text-indigo-400 mt-4 inline-block">
          Volver a reportes
        </Link>
      </GlassContainer>
    )
  }

  const rules = report.result?.results || []
  const recommendations = report.recommendations || []
  const totalDuration = rules.reduce((s: number, r: any) => s + (r.duration_ms || 0), 0)
  const fmtDur = (ms: number) => ms >= 1000 ? `${(ms / 1000).toFixed(2)}s` : `${Math.round(ms)}ms`

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <Link to="/reports" className="inline-flex items-center gap-2 text-muted hover:text-white transition-colors">
          <ArrowLeft className="w-4 h-4" />
          Volver a reportes
        </Link>
        <div className="flex items-center gap-2">
          {confirmDelete ? (
            <div className="flex items-center gap-2 bg-red-500/20 border border-red-500/30 rounded-xl px-3 py-1.5">
              <AlertTriangle className="w-4 h-4 text-red-400" />
              <span className="text-sm text-red-300">¿Eliminar?</span>
              <button onClick={() => deleteMutation.mutate()} disabled={deleteMutation.isPending}
                className="btn-ghost text-xs text-red-400 font-semibold px-2">
                {deleteMutation.isPending ? '...' : 'Sí'}
              </button>
              <button onClick={() => setConfirmDelete(false)} className="btn-ghost text-xs text-muted px-2">
                No
              </button>
            </div>
          ) : (
            <button onClick={() => setConfirmDelete(true)} className="btn-ghost flex items-center gap-2 text-sm text-red-400">
              <Trash2 className="w-4 h-4" />
              Eliminar
            </button>
          )}
          <button onClick={handleExportPdf} className="btn-ghost flex items-center gap-2 text-sm">
            <FileText className="w-4 h-4" />
            PDF
          </button>
          <button onClick={handleExportExcel} className="btn-ghost flex items-center gap-2 text-sm">
            <FileDown className="w-4 h-4" />
            Excel
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
        <GlassContainer className="lg:col-span-2">
          <h1 className="text-2xl font-bold text-white mb-4">
            {report.project_name || 'Resumen del Reporte'}
          </h1>
          <div className="flex items-center gap-6">
            <QualityGauge score={report.score} size={150} />
            <div>
              <p className="text-3xl font-bold text-white mb-1">{Number(report.score).toFixed(2)}/100</p>
              <span className={`text-lg ${report.score >= 70 ? 'text-green-400' : report.score >= 50 ? 'text-yellow-400' : 'text-red-400'}`}>
                {getScoreLabel(report.score)}
              </span>
              {report.summary && (
                <p className="text-muted mt-2 text-sm">{report.summary}</p>
              )}
              <p className="text-muted text-xs mt-2">
                Ejecutado: {formatDate(report.executed_at)}
              </p>
              {totalDuration > 0 && (
                <p className="text-muted text-xs mt-1 flex items-center gap-1">
                  <Clock className="w-3 h-3" /> Duración total: {fmtDur(totalDuration)}
                </p>
              )}
            </div>
          </div>
        </GlassContainer>

        <GlassContainer>
          <h2 className="text-lg font-semibold text-white mb-4">Recomendaciones</h2>
          {recommendations.length > 0 ? (
            <div className="space-y-3">
              {recommendations.slice(0, 4).map((rec: any, i: number) => (
                <div key={i} className="bg-white/5 rounded-lg p-3">
                  <p className="text-sm text-white font-medium">{rec.rule}</p>
                  <p className="text-xs text-muted mt-1">{rec.recommendation}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-muted text-sm">Sin recomendaciones</p>
          )}
        </GlassContainer>
      </div>

      <GlassContainer>
        <h2 className="text-xl font-semibold text-white mb-6">Reglas Ejecutadas</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {rules.map((rule: any, i: number) => {
            const SeverityIcon = severityIcons[rule.severity] || Info
            return (
              <div
                key={i}
                className={`rounded-xl p-4 border ${
                  rule.passed
                    ? 'bg-green-500/10 border-green-500/20'
                    : 'bg-red-500/10 border-red-500/20'
                }`}
              >
                <div className="flex items-start gap-3">
                  <QualityGauge
                    score={rule.total > 0 ? Math.round((100 - (rule.failure_pct ?? 0)) * 100) / 100 : 100}
                    size={56}
                  />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <p className="text-white font-medium">{rule.rule_name}</p>
                      <span className={`badge badge-${rule.severity}`}>{rule.severity}</span>
                      <span className={`text-sm ${rule.passed ? 'text-green-400' : 'text-red-400'}`}>
                        {rule.failed}/{rule.total} ({(rule.failure_pct ?? 0).toFixed(2)}%)
                      </span>
                    </div>
                    <p className="text-muted text-sm mt-1">{rule.description}</p>
                    {rule.duration_ms > 0 && (
                      <p className="text-muted text-xs mt-1 flex items-center gap-1">
                        <Clock className="w-3 h-3" /> {fmtDur(rule.duration_ms)}
                      </p>
                    )}
                    <Link
                      to={`/reports/${id}/rules/${i}`}
                      className="inline-flex items-center gap-1.5 text-xs text-indigo-400 hover:text-indigo-300 transition-colors mt-3 font-medium"
                    >
                      <ExternalLink className="w-3.5 h-3.5" />
                      Ver detalle
                    </Link>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </GlassContainer>
    </div>
  )
}
