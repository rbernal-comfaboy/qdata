import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, FolderOpen, FileText, CheckCircle, AlertTriangle, Info, TrendingUp } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, ResponsiveContainer, Tooltip, PieChart, Pie, Cell, LineChart, Line } from 'recharts'
import api from '../api/client'
import GlassContainer from '../components/layout/GlassContainer'

const SEVERITY_COLORS: Record<string, string> = { error: '#ef4444', warning: '#f59e0b', info: '#3b82f6' }

export default function GroupDashboard() {
  const { groupId } = useParams<{ groupId: string }>()

  const { data, isLoading } = useQuery({
    queryKey: ['group-dashboard', groupId],
    queryFn: () => api.get(`/api/groups/${groupId}/dashboard`).then(r => r.data),
    enabled: !!groupId,
  })

  if (isLoading) return <div className="space-y-6"><div className="skeleton h-32 rounded-xl" /><div className="skeleton h-96 rounded-xl" /></div>

  if (!data) return (
    <GlassContainer className="text-center py-12">
      <p className="text-muted">Grupo no encontrado</p>
      <Link to="/groups" className="text-indigo-400 mt-4 inline-block">Volver a grupos de análisis</Link>
    </GlassContainer>
  )

  const { group, summary, scores_timeline, project_scores, severity_counts, rule_summary } = data

  const sevPieData = Object.entries(severity_counts).filter(([,v]) => v > 0).map(([k, v]) => ({ name: k, value: v }))

  const ruleChartData = rule_summary.slice(0, 10).map((r: any) => ({
    name: r.rule_name.replace('_check', '').replace('_', ' ').slice(0, 15),
    passed: r.passed,
    failed: r.failed,
    pass_rate: r.pass_rate,
  }))

  return (
    <div>
      <Link to="/groups" className="inline-flex items-center gap-2 text-muted hover:text-white transition-colors mb-6">
        <ArrowLeft className="w-4 h-4" /> Volver a grupos de análisis
      </Link>

      <div className="flex items-center gap-3 mb-8">
        <div className="w-5 h-5 rounded-full" style={{ backgroundColor: group.color }} />
        <h1 className="text-3xl font-bold text-white">{group.name}</h1>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        {[
          { label: 'Análisis', value: summary.total_projects, icon: FolderOpen, color: 'text-blue-400' },
          { label: 'Reportes', value: summary.total_reports, icon: FileText, color: 'text-cyan-400' },
          { label: 'Score Promedio', value: `${summary.avg_score}/100`, icon: TrendingUp, color: summary.avg_score >= 70 ? 'text-green-400' : summary.avg_score >= 40 ? 'text-yellow-400' : 'text-red-400' },
          { label: 'Tasa de Aprobación', value: `${summary.overall_pass_rate.toFixed(2)}%`, icon: CheckCircle, color: 'text-green-400' },
        ].map(s => (
          <GlassContainer key={s.label} className="flex items-center gap-4">
            <s.icon className={`w-10 h-10 ${s.color}`} />
            <div>
              <p className="text-2xl font-bold text-white">{s.value}</p>
              <p className="text-sm text-muted">{s.label}</p>
            </div>
          </GlassContainer>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <GlassContainer>
          <h2 className="text-lg font-semibold text-white mb-4">Evolución de Scores</h2>
          {scores_timeline.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={scores_timeline}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="date" stroke="rgba(255,255,255,0.4)" tickFormatter={v => v?.slice(5, 10) || ''} />
                <YAxis domain={[0, 100]} stroke="rgba(255,255,255,0.4)" />
                <Tooltip contentStyle={{ background: 'rgba(0,0,0,0.8)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', color: 'white' }} />
                <Line type="monotone" dataKey="score" stroke={group.color} strokeWidth={2} dot={{ fill: group.color }} />
              </LineChart>
            </ResponsiveContainer>
          ) : <p className="text-muted text-sm text-center py-8">Sin datos</p>}
        </GlassContainer>

        <GlassContainer>
          <h2 className="text-lg font-semibold text-white mb-4">Scores por Análisis</h2>
          {project_scores.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={project_scores}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="name" stroke="rgba(255,255,255,0.4)" tick={{ fontSize: 11 }} />
                <YAxis domain={[0, 100]} stroke="rgba(255,255,255,0.4)" />
                <Tooltip contentStyle={{ background: 'rgba(0,0,0,0.8)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', color: 'white' }} />
                <Bar dataKey="score" radius={[4, 4, 0, 0]}>
                  {project_scores.map((_: any, i: number) => (
                    <Cell key={i} fill={project_scores[i].score >= 70 ? '#10b981' : project_scores[i].score >= 40 ? '#f59e0b' : '#ef4444'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : <p className="text-muted text-sm text-center py-8">Sin datos</p>}
        </GlassContainer>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        <GlassContainer>
          <h2 className="text-lg font-semibold text-white mb-4">Severidad</h2>
          {sevPieData.length > 0 ? (
            <div className="flex items-center justify-center">
              <ResponsiveContainer width="100%" height={200}>
                <PieChart>
                  <Pie data={sevPieData} cx="50%" cy="50%" outerRadius={70} dataKey="value" label={({ name, value }) => `${name}: ${value}`}>
                    {sevPieData.map((entry: any) => (
                      <Cell key={entry.name} fill={SEVERITY_COLORS[entry.name] || '#6b7280'} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={{ background: 'rgba(0,0,0,0.8)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', color: 'white' }} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          ) : <p className="text-muted text-sm text-center py-8">Sin datos</p>}
          <div className="flex justify-center gap-4 mt-2">
            {Object.entries(severity_counts).map(([k, v]) => (
              <div key={k} className="flex items-center gap-1 text-xs text-muted">
                <div className="w-2 h-2 rounded-full" style={{ backgroundColor: SEVERITY_COLORS[k] }} />
                {k}: {String(v)}
              </div>
            ))}
          </div>
        </GlassContainer>

        <GlassContainer className="lg:col-span-2">
          <h2 className="text-lg font-semibold text-white mb-4">Top Reglas con Fallos</h2>
          {ruleChartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={ruleChartData} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis type="number" stroke="rgba(255,255,255,0.4)" />
                <YAxis type="category" dataKey="name" stroke="rgba(255,255,255,0.4)" width={120} tick={{ fontSize: 11 }} />
                <Tooltip contentStyle={{ background: 'rgba(0,0,0,0.8)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', color: 'white' }} />
                <Bar dataKey="passed" stackId="a" fill="#10b981" name="Aprobadas" />
                <Bar dataKey="failed" stackId="a" fill="#ef4444" name="Fallidas" />
              </BarChart>
            </ResponsiveContainer>
          ) : <p className="text-muted text-sm text-center py-8">Sin datos</p>}
        </GlassContainer>
      </div>

      {rule_summary.length > 0 && (
        <GlassContainer>
          <h2 className="text-lg font-semibold text-white mb-4">Detalle de Reglas</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/10">
                  <th className="text-left p-2 text-muted font-medium">Regla</th>
                  <th className="text-right p-2 text-muted font-medium">Aprobadas</th>
                  <th className="text-right p-2 text-muted font-medium">Fallidas</th>
                  <th className="text-right p-2 text-muted font-medium">Total</th>
                  <th className="text-right p-2 text-muted font-medium">Tasa</th>
                </tr>
              </thead>
              <tbody>
                {rule_summary.map((r: any) => (
                  <tr key={r.rule_name} className="border-b border-white/5">
                    <td className="p-2 text-white font-mono text-xs">{r.rule_name}</td>
                    <td className="p-2 text-green-400 text-right">{r.passed}</td>
                    <td className="p-2 text-red-400 text-right">{r.failed}</td>
                    <td className="p-2 text-white text-right">{r.total}</td>
                    <td className={`p-2 text-right font-medium ${r.pass_rate >= 80 ? 'text-green-400' : r.pass_rate >= 50 ? 'text-yellow-400' : 'text-red-400'}`}>
                      {r.pass_rate.toFixed(2)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </GlassContainer>
      )}
    </div>
  )
}
