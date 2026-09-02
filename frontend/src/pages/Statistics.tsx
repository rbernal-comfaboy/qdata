import { useQuery } from '@tanstack/react-query'
import {
  PieChart, Pie, Cell, ResponsiveContainer, Tooltip,
} from 'recharts'
import { BarChart3, FolderOpen, FileText, TrendingUp, AlertTriangle } from 'lucide-react'
import api from '../api/client'
import GlassContainer from '../components/layout/GlassContainer'
import QualityGauge from '../components/charts/QualityGauge'

const COLORS = ['#6366f1', '#48bb78', '#f6ad55', '#f56565', '#3b82f6', '#a855f7', '#ec4899', '#14b8a6']

function fmt(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K'
  return n.toLocaleString()
}

export default function Statistics() {
  const { data: groups = [], isLoading, isError } = useQuery({
    queryKey: ['groups'],
    queryFn: () => api.get('/api/groups').then((r) => r.data),
  })

  const sorted = [...groups].sort((a: any, b: any) => (b.avg_score ?? 0) - (a.avg_score ?? 0))
  const avgAll = groups.length > 0
    ? groups.reduce((s: number, g: any) => s + (g.avg_score ?? 0), 0) / groups.length
    : 0
  const totalReports = groups.reduce((s: number, g: any) => s + (g.report_count || 0), 0)
  const totalErrorsAll = groups.reduce((s: number, g: any) => s + (g.total_errors || 0), 0)
  const totalRecordsAll = groups.reduce((s: number, g: any) => s + (g.total_records || 0), 0)

  const pieData = sorted.filter((g: any) => g.avg_score != null).map((g: any, i: number) => ({
    name: g.name,
    value: g.avg_score,
    color: g.color || COLORS[i % COLORS.length],
    project_count: g.project_count,
    report_count: g.report_count,
    total_errors: g.total_errors || 0,
    total_records: g.total_records || 0,
  }))

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="skeleton h-12 rounded-xl w-64" />
        <div className="grid grid-cols-4 gap-6">
          {[1, 2, 3, 4].map((i) => <div key={i} className="skeleton h-28 rounded-xl" />)}
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
          {[1, 2, 3, 4].map((i) => <div key={i} className="skeleton h-64 rounded-xl" />)}
        </div>
        <div className="skeleton h-96 rounded-xl" />
      </div>
    )
  }

  if (isError) {
    return (
      <div className="space-y-6">
        <h1 className="text-3xl font-bold text-white mb-6 flex items-center gap-3">
          <BarChart3 className="w-8 h-8 text-indigo-400" />
          Estadísticas por Grupo
        </h1>
        <GlassContainer className="text-center py-16">
          <AlertTriangle className="w-16 h-16 text-red-400 mx-auto mb-4" />
          <p className="text-xl text-white">Error al cargar estadísticas</p>
          <p className="text-sm text-muted mt-2">No se pudieron obtener los grupos de análisis. Intenta recargar la página.</p>
        </GlassContainer>
      </div>
    )
  }

  return (
    <div>
      <h1 className="text-3xl font-bold text-white mb-6 flex items-center gap-3">
        <BarChart3 className="w-8 h-8 text-indigo-400" />
        Estadísticas por Grupo
      </h1>

      {groups.length === 0 ? (
        <GlassContainer className="text-center py-16">
          <FolderOpen className="w-16 h-16 text-muted mx-auto mb-4" />
          <p className="text-xl text-muted">No hay grupos de análisis</p>
          <p className="text-sm text-muted mt-2">Crea un grupo desde la sección Grupos de Análisis</p>
        </GlassContainer>
      ) : (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
            <GlassContainer className="flex items-center gap-4">
              <FolderOpen className="w-10 h-10 text-indigo-400" />
              <div>
                <p className="text-2xl font-bold text-white">{groups.length}</p>
                <p className="text-sm text-muted">Grupos</p>
              </div>
            </GlassContainer>
            <GlassContainer className="flex items-center gap-4">
              <FileText className="w-10 h-10 text-blue-400" />
              <div>
                <p className="text-2xl font-bold text-white">{totalReports}</p>
                <p className="text-sm text-muted">Reportes totales</p>
              </div>
            </GlassContainer>
            <GlassContainer className="flex items-center gap-4">
              <AlertTriangle className="w-10 h-10 text-red-400" />
              <div>
                <p className="text-2xl font-bold text-white">{fmt(totalErrorsAll)}</p>
                <p className="text-sm text-muted">Errores encontrados</p>
              </div>
            </GlassContainer>
            <GlassContainer className="flex flex-col items-center justify-center py-3">
              <div className="flex items-center gap-3">
                <TrendingUp className="w-6 h-6 text-green-400" />
                <span className="text-4xl font-bold text-white">{avgAll > 0 ? avgAll.toFixed(1) : '-'}</span>
              </div>
              <p className="text-sm text-muted">Score promedio general</p>
            </GlassContainer>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-6 mb-8">
            {sorted.map((g: any) => {
              const color = g.color || '#6366f1'
              const errs = g.total_errors || 0
              const recs = g.total_records || 0
              const errPct = recs > 0 ? ((errs / recs) * 100).toFixed(1) : '0.0'
              return (
                <GlassContainer key={g.id} className="flex flex-col items-center text-center">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="w-3 h-3 rounded-full" style={{ backgroundColor: color }} />
                    <h3 className="text-sm font-semibold text-white truncate max-w-[120px]">{g.name}</h3>
                  </div>
                  {g.avg_score != null ? (
                    <QualityGauge score={g.avg_score} size={130} />
                  ) : (
                    <div className="flex items-center justify-center h-[130px] text-muted text-xs">Sin datos</div>
                  )}
                  <div className="flex items-center gap-2 mt-2 text-[10px] text-muted flex-wrap justify-center">
                    <span className="flex items-center gap-1"><FolderOpen className="w-3 h-3" />{g.project_count}</span>
                    <span className="flex items-center gap-1"><FileText className="w-3 h-3" />{g.report_count}</span>
                  </div>
                  <div className="flex items-center gap-3 mt-1 text-[10px]">
                    <span className="text-red-400 font-medium">{fmt(errs)} err</span>
                    <span className="text-muted">/</span>
                    <span className="text-blue-400 font-medium">{fmt(recs)} reg</span>
                    <span className="text-muted">({errPct}%)</span>
                  </div>
                </GlassContainer>
              )
            })}
          </div>

          {pieData.length > 0 && (
            <GlassContainer>
              <h2 className="text-xl font-semibold text-white mb-6 flex items-center gap-2">
                <BarChart3 className="w-5 h-5 text-indigo-400" />
                Comparativa de Scores por Grupo
              </h2>
              <div className="flex flex-col lg:flex-row items-center gap-8">
                <ResponsiveContainer width="100%" height={420}>
                  <PieChart>
                    <Pie
                      data={pieData}
                      cx="50%"
                      cy="50%"
                      innerRadius={80}
                      outerRadius={160}
                      dataKey="value"
                      nameKey="name"
                      label={({ name, value }) => `${name}: ${value.toFixed(1)}%`}
                      labelLine={true}
                      stroke="rgba(0,0,0,0.2)"
                      strokeWidth={2}
                    >
                      {pieData.map((entry: any, i: number) => (
                        <Cell key={i} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{
                        background: 'rgba(0,0,0,0.8)',
                        border: '1px solid rgba(255,255,255,0.1)',
                        borderRadius: '8px',
                        color: 'white',
                      }}
                      formatter={(value: number) => [`${value.toFixed(2)}%`, 'Score']}
                    />
                  </PieChart>
                </ResponsiveContainer>
                <div className="flex flex-col gap-3 shrink-0">
                  {pieData.map((entry: any, i: number) => (
                    <div key={i} className="flex items-center gap-3">
                      <span className="w-3 h-3 rounded-full shrink-0" style={{ backgroundColor: entry.color }} />
                      <span className="text-sm text-white min-w-[100px]">{entry.name}</span>
                      <span className="text-sm font-semibold text-white">{entry.value.toFixed(1)}%</span>
                      <span className="text-[10px] text-red-400">{fmt(entry.total_errors)} err</span>
                      <span className="text-[10px] text-muted">/ {fmt(entry.total_records)} reg</span>
                    </div>
                  ))}
                </div>
              </div>
            </GlassContainer>
          )}
        </>
      )}
    </div>
  )
}
