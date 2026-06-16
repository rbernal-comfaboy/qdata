import { useQuery } from '@tanstack/react-query'
import { Search, FileText, AlertTriangle, CheckCircle, Clock } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, ResponsiveContainer, Tooltip } from 'recharts'
import api from '../api/client'
import GlassContainer from '../components/layout/GlassContainer'
import QualityGauge from '../components/charts/QualityGauge'
import { formatDate, getScoreLabel } from '../lib/utils'

export default function Dashboard() {
  const { data: reports, isLoading } = useQuery({
    queryKey: ['reports'],
    queryFn: () => api.get('/reports?limit=5').then((r) => r.data),
  })

  const latest = reports?.[0]
  const score = latest?.score ?? 0

  const stats = [
    { label: 'Reportes', value: reports?.length ?? 0, icon: FileText, color: 'text-blue-400' },
    { label: 'Score Promedio', value: latest ? `${score}/100` : '-', icon: CheckCircle, color: 'text-green-400' },
    { label: 'Críticos', value: reports?.filter((r: any) => r.label === 'critico').length ?? 0, icon: AlertTriangle, color: 'text-red-400' },
    { label: 'Último Análisis', value: latest ? formatDate(latest.executed_at) : '-', icon: Clock, color: 'text-yellow-400' },
  ]

  const chartData = (reports || []).slice().reverse().map((r: any) => ({
    name: formatDate(r.executed_at).slice(0, 6),
    score: r.score,
  }))

  return (
    <div>
      <h1 className="text-3xl font-bold text-white mb-8">Dashboard</h1>

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
      ) : (
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
      )}

      <GlassContainer className="mt-6">
        <h2 className="text-xl font-semibold text-white mb-4">Últimos Reportes</h2>
        {reports?.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-white/10">
                  <th className="text-left p-3 text-muted text-sm">ID</th>
                  <th className="text-left p-3 text-muted text-sm">Score</th>
                  <th className="text-left p-3 text-muted text-sm">Estado</th>
                  <th className="text-left p-3 text-muted text-sm">Fecha</th>
                </tr>
              </thead>
              <tbody>
                {reports.map((r: any) => (
                  <tr key={r.id} className="border-b border-white/5 hover:bg-white/5">
                    <td className="p-3 text-white text-sm font-mono">{r.id.slice(0, 8)}...</td>
                    <td className="p-3">
                      <span className={r.score >= 70 ? 'text-green-400' : r.score >= 50 ? 'text-yellow-400' : 'text-red-400'}>
                        {r.score}
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
        ) : (
          <p className="text-muted text-center py-8">Ejecuta tu primer análisis para ver resultados</p>
        )}
      </GlassContainer>
    </div>
  )
}
