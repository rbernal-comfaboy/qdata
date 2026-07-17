import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Search, FileText, AlertTriangle, CheckCircle, Clock, Calendar } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, ResponsiveContainer, Tooltip } from 'recharts'
import api from '../api/client'
import GlassContainer from '../components/layout/GlassContainer'
import QualityGauge from '../components/charts/QualityGauge'
import { formatDate, getScoreLabel } from '../lib/utils'

export default function Dashboard() {
  const today = new Date()
  const thirtyDaysAgo = new Date(today)
  thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30)

  const [startDate, setStartDate] = useState(thirtyDaysAgo.toISOString().split('T')[0])
  const [endDate, setEndDate] = useState(today.toISOString().split('T')[0])

  const params = new URLSearchParams({ limit: '1000' })
  if (startDate) params.set('start_date', startDate)
  if (endDate) params.set('end_date', endDate)

  const { data: reports, isLoading } = useQuery({
    queryKey: ['reports', startDate, endDate],
    queryFn: () => api.get(`/reports?${params.toString()}`).then((r) => r.data),
  })

  const latest = reports?.[0]
  const score = latest?.score ?? 0
  const hasReports = reports && reports.length > 0

  const stats = useMemo(() => {
    if (!hasReports) return [
      { label: 'Reportes', value: 0, icon: FileText, color: 'text-blue-400' },
      { label: 'Score Promedio', value: '-', icon: CheckCircle, color: 'text-green-400' },
      { label: 'Críticos', value: 0, icon: AlertTriangle, color: 'text-red-400' },
      { label: 'Último Análisis', value: '-', icon: Clock, color: 'text-yellow-400' },
    ]
    const avgScore = reports.reduce((s: number, r: any) => s + (r.score || 0), 0) / reports.length
    const critical = reports.filter((r: any) => r.label === 'critico').length
    return [
      { label: 'Reportes', value: reports.length, icon: FileText, color: 'text-blue-400' },
      { label: 'Score Promedio', value: `${avgScore.toFixed(2)}/100`, icon: CheckCircle, color: 'text-green-400' },
      { label: 'Críticos', value: critical, icon: AlertTriangle, color: 'text-red-400' },
      { label: 'Último Análisis', value: formatDate(latest.executed_at), icon: Clock, color: 'text-yellow-400' },
    ]
  }, [reports, latest, hasReports])

  const chartData = useMemo(() => {
    if (!hasReports) return []
    return [...reports].reverse().map((r: any) => ({
      name: formatDate(r.executed_at).slice(0, 6),
      score: r.score,
    }))
  }, [reports, hasReports])

  return (
    <div>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
        <h1 className="text-3xl font-bold text-white">Dashboard</h1>
        <div className="flex items-center gap-3">
          <Calendar className="w-5 h-5 text-muted" />
          <input
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            className="glass-input !w-auto"
          />
          <span className="text-muted">—</span>
          <input
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            className="glass-input !w-auto"
          />
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        {stats.map((s) => (
          <GlassContainer key={s.label} className="flex items-center gap-4">
            <s.icon className={`w-10 h-10 ${s.color}`} />
            <div>
              <p className="text-2xl font-bold text-white">{s.value}</p>
              <p className="text-sm text-muted">{s.label}</p>
            </div>
          </GlassContainer>
        ))}
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="skeleton h-80" />
          <div className="skeleton h-80" />
        </div>
      ) : !hasReports ? (
        <GlassContainer className="text-center py-16">
          <FileText className="w-16 h-16 text-muted mx-auto mb-4" />
          <p className="text-xl text-muted">No hay reportes creados en esas fechas</p>
          <p className="text-sm text-muted mt-2">Selecciona un rango de fechas diferente o ejecuta un nuevo análisis</p>
        </GlassContainer>
      ) : (
        <>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <GlassContainer>
              <h2 className="text-xl font-semibold text-white mb-4">Último Score</h2>
              <div className="flex flex-col items-center">
                <QualityGauge score={score} />
                <span className="mt-2 text-lg text-muted">{getScoreLabel(score)}</span>
              </div>
            </GlassContainer>

            <GlassContainer>
              <h2 className="text-xl font-semibold text-white mb-4">Historial de Scores</h2>
              {chartData.length > 0 ? (
                <ResponsiveContainer width="100%" height={250}>
                  <BarChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                    <XAxis dataKey="name" stroke="rgba(255,255,255,0.4)" />
                    <YAxis domain={[0, 100]} stroke="rgba(255,255,255,0.4)" />
                    <Tooltip
                      contentStyle={{
                        background: 'rgba(0,0,0,0.8)',
                        border: '1px solid rgba(255,255,255,0.1)',
                        borderRadius: '8px',
                        color: 'white',
                      }}
                    />
                    <Bar dataKey="score" fill="#6366f1" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <p className="text-muted text-center py-12">Aún no hay reportes</p>
              )}
            </GlassContainer>
          </div>

          <GlassContainer className="mt-6">
            <h2 className="text-xl font-semibold text-white mb-4">Reportes</h2>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-white/10">
                    <th className="text-left p-3 text-muted text-sm">ID</th>
                    <th className="text-left p-3 text-muted text-sm">Proyecto</th>
                    <th className="text-left p-3 text-muted text-sm">Score</th>
                    <th className="text-left p-3 text-muted text-sm">Estado</th>
                    <th className="text-left p-3 text-muted text-sm">Fecha</th>
                  </tr>
                </thead>
                <tbody>
                  {reports.map((r: any) => (
                    <tr key={r.id} className="border-b border-white/5 hover:bg-white/5">
                      <td className="p-3 text-white text-sm font-mono">{r.id.slice(0, 8)}...</td>
                      <td className="p-3 text-white text-sm">{r.project_name || '-'}</td>
                      <td className="p-3">
                        <span className={r.score >= 70 ? 'text-green-400' : r.score >= 50 ? 'text-yellow-400' : 'text-red-400'}>
                          {Number(r.score).toFixed(2)}
                        </span>
                      </td>
                      <td className="p-3">
                        <span className={`badge badge-${r.label === 'excelente' ? 'success' : r.label === 'critico' ? 'error' : 'warning'}`}>
                          {r.label}
                        </span>
                      </td>
                      <td className="p-3 text-muted text-sm">{formatDate(r.executed_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </GlassContainer>
        </>
      )}
    </div>
  )
}