import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  PieChart, Pie, Cell, ResponsiveContainer, Tooltip,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
} from 'recharts'
import { BarChart3, FolderOpen, FileText, TrendingUp, AlertTriangle, ChevronDown, X, Check } from 'lucide-react'
import api from '../api/client'
import GlassContainer from '../components/layout/GlassContainer'
import QualityGauge from '../components/charts/QualityGauge'

const COLORS = ['#6366f1', '#48bb78', '#f6ad55', '#f56565', '#3b82f6', '#a855f7', '#ec4899', '#14b8a6']

const PERIODS = [
  { id: 'all', label: 'Todo el tiempo' },
  { id: '7d', label: 'Últimos 7 días' },
  { id: '30d', label: 'Últimos 30 días' },
  { id: '90d', label: 'Últimos 90 días' },
  { id: 'year', label: 'Este año' },
  { id: 'custom', label: 'Rango personalizado' },
]

function fmt(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K'
  return n.toLocaleString()
}

export default function Statistics() {
  const [period, setPeriod] = useState('all')
  const [customStart, setCustomStart] = useState('')
  const [customEnd, setCustomEnd] = useState('')
  const [selectedRules, setSelectedRules] = useState<string[]>([])
  const [rulesOpen, setRulesOpen] = useState(false)
  const [selectedGroups, setSelectedGroups] = useState<string[]>([])
  const [groupsOpen, setGroupsOpen] = useState(false)

  const { data: rulesData } = useQuery({
    queryKey: ['rules-groups'],
    queryFn: () => api.get('/rules/groups').then((r) => r.data),
  })

  const { ruleOptions, ruleLabelMap } = useMemo(() => {
    const byKey = new Map<string, string>()
    const byStored = new Map<string, string>()
    ;(rulesData?.groups ?? []).forEach((g: any) => {
      ;(g.rules || []).forEach((r: any) => {
        byKey.set(r.name, r.label || r.name)
        byStored.set(r.rule_name || r.name, r.label || r.rule_name || r.name)
      })
    })
    const options = [...byKey.entries()].map(([name, label]) => ({ name, label }))
      .sort((a, b) => a.label.localeCompare(b.label))
    const labels = new Map<string, string>([...byStored, ...byKey])
    return { ruleOptions: options, ruleLabelMap: labels }
  }, [rulesData])

  const ruleLabelOf = (name: string) => ruleLabelMap.get(name) || name

  const { start, end } = useMemo(() => {
    const now = new Date()
    let s: string | undefined
    let e: string | undefined
    switch (period) {
      case '7d':
        s = new Date(now.getTime() - 7 * 864e5).toISOString()
        break
      case '30d':
        s = new Date(now.getTime() - 30 * 864e5).toISOString()
        break
      case '90d':
        s = new Date(now.getTime() - 90 * 864e5).toISOString()
        break
      case 'year':
        s = new Date(now.getFullYear(), 0, 1).toISOString()
        break
      case 'custom':
        if (customStart) s = new Date(`${customStart}T00:00:00`).toISOString()
        if (customEnd) e = new Date(`${customEnd}T23:59:59`).toISOString()
        break
    }
    return { start: s, end: e }
  }, [period, customStart, customEnd])

  const { data: groups = [], isLoading, isError } = useQuery({
    queryKey: ['groups', start ?? '', end ?? '', selectedRules.join(',')],
    queryFn: () => api.get('/api/groups', {
      params: {
        start: start || undefined,
        end: end || undefined,
        rules: selectedRules.length > 0 ? selectedRules.join(',') : undefined,
      },
    }).then((r) => r.data),
  })

  const { data: ruleStats = [] } = useQuery({
    queryKey: ['rule-stats', start ?? '', end ?? '', selectedRules.join(','), selectedGroups.join(',')],
    queryFn: () => api.get('/rules/stats', {
      params: {
        start: start || undefined,
        end: end || undefined,
        rules: selectedRules.length > 0 ? selectedRules.join(',') : undefined,
        groups: selectedGroups.length > 0 ? selectedGroups.join(',') : undefined,
      },
    }).then((r) => r.data),
  })

  const sorted = [...groups]
    .filter((g: any) => selectedGroups.length === 0 || selectedGroups.includes(g.id))
    .sort((a: any, b: any) => (b.avg_score ?? 0) - (a.avg_score ?? 0))
  const avgAll = sorted.length > 0
    ? sorted.reduce((s: number, g: any) => s + (g.avg_score ?? 0), 0) / sorted.length
    : 0
  const totalReports = sorted.reduce((s: number, g: any) => s + (g.report_count || 0), 0)
  const totalErrorsAll = sorted.reduce((s: number, g: any) => s + (g.total_errors || 0), 0)
  const totalRecordsAll = sorted.reduce((s: number, g: any) => s + (g.total_records || 0), 0)

  const useRulePct = selectedRules.length > 0
  const scoreAvgGeneral = useRulePct
    ? (totalRecordsAll > 0
      ? Math.min(100, Math.max(0, ((totalRecordsAll - totalErrorsAll) / totalRecordsAll) * 100))
      : 0)
    : avgAll
  const pieData = sorted.filter((g: any) => useRulePct ? (g.total_records || 0) > 0 : g.avg_score != null).map((g: any, i: number) => ({
    name: g.name,
    value: useRulePct
      ? (g.total_records > 0 ? (((g.total_errors || 0) / g.total_records) * 100) : 0)
      : g.avg_score,
    color: g.color || COLORS[i % COLORS.length],
    project_count: g.project_count,
    report_count: g.report_count,
    total_errors: g.total_errors || 0,
    total_records: g.total_records || 0,
  }))

  const ruleBarData = [...ruleStats]
    .map((r: any) => ({
      name: ruleLabelOf(r.rule_name),
      pct: Number((r.pct ?? 0).toFixed(2)),
      failed: r.failed || 0,
      total: r.total || 0,
      rule_name: r.rule_name,
    }))
    .sort((a: any, b: any) => b.pct - a.pct)
    .slice(0, selectedRules.length > 0 ? undefined : 15)

  const toggleRule = (name: string) => {
    setSelectedRules((prev) => prev.includes(name) ? prev.filter((r) => r !== name) : [...prev, name])
  }

  const periodLabel = PERIODS.find((p) => p.id === period)?.label || period

  const hasFilters = start !== undefined || selectedRules.length > 0 || selectedGroups.length > 0

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

      <GlassContainer className="relative z-50 mb-8">
        <div className="flex flex-col lg:flex-row lg:items-center gap-4">
          <div className="flex items-center gap-3 flex-wrap">
            <span className="text-sm text-muted">Período:</span>
            <select
              value={period}
              onChange={(e) => setPeriod(e.target.value)}
              className="bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-sm text-white outline-none focus:border-indigo-400 [color-scheme:dark]"
            >
              {PERIODS.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
            </select>
            {period === 'custom' && (
              <div className="flex items-center gap-2">
                <input
                  type="date"
                  value={customStart}
                  onChange={(e) => setCustomStart(e.target.value)}
                  className="bg-white/5 border border-white/10 rounded-lg px-2 py-1.5 text-sm text-white outline-none [color-scheme:dark]"
                />
                <span className="text-muted text-sm">a</span>
                <input
                  type="date"
                  value={customEnd}
                  onChange={(e) => setCustomEnd(e.target.value)}
                  className="bg-white/5 border border-white/10 rounded-lg px-2 py-1.5 text-sm text-white outline-none [color-scheme:dark]"
                />
              </div>
            )}
          </div>

          <div className="relative">
            <button
              onClick={() => setGroupsOpen((v) => !v)}
              className="flex items-center gap-2 bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-sm text-white hover:bg-white/10 transition-colors"
            >
              <FolderOpen className="w-4 h-4 text-indigo-400" />
              {selectedGroups.length === 0
                ? 'Todos los grupos'
                : `Grupos (${selectedGroups.length})`}
              {selectedGroups.length > 0 && (
                <span
                  role="button"
                  onClick={(e) => { e.stopPropagation(); setSelectedGroups([]) }}
                  className="ml-1 p-0.5 rounded hover:bg-white/20"
                  title="Limpiar grupos"
                >
                  <X className="w-3.5 h-3.5" />
                </span>
              )}
              <ChevronDown className={`w-4 h-4 transition-transform ${groupsOpen ? 'rotate-180' : ''}`} />
            </button>

            {groupsOpen && (
              <div className="absolute z-50 mt-2 w-72 max-h-96 overflow-y-auto rounded-xl border border-white/10 bg-[#0d1117] shadow-2xl">
                <button
                  onClick={() => setSelectedGroups([])}
                  className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-indigo-300 hover:bg-white/5 border-b border-white/10"
                >
                  <Check className="w-4 h-4" /> Ver todos los grupos
                </button>
                {groups.map((g: any) => (
                  <label key={g.id} className="flex items-center gap-3 px-4 py-2 text-sm text-white cursor-pointer hover:bg-white/5">
                    <input
                      type="checkbox"
                      checked={selectedGroups.includes(g.id)}
                      onChange={() => setSelectedGroups(
                        (prev) => prev.includes(g.id) ? prev.filter((x) => x !== g.id) : [...prev, g.id]
                      )}
                      className="accent-indigo-500"
                    />
                    <span className="truncate">{g.name}</span>
                  </label>
                ))}
              </div>
            )}
          </div>

          <div className="relative">
            <button
              onClick={() => setRulesOpen((v) => !v)}
              className="flex items-center gap-2 bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-sm text-white hover:bg-white/10 transition-colors"
            >
              <FileText className="w-4 h-4 text-indigo-400" />
              {selectedRules.length === 0
                ? 'Todas las reglas'
                : `Reglas (${selectedRules.length})`}
              {selectedRules.length > 0 && (
                <span
                  role="button"
                  onClick={(e) => { e.stopPropagation(); setSelectedRules([]) }}
                  className="ml-1 p-0.5 rounded hover:bg-white/20"
                  title="Limpiar reglas"
                >
                  <X className="w-3.5 h-3.5" />
                </span>
              )}
              <ChevronDown className={`w-4 h-4 transition-transform ${rulesOpen ? 'rotate-180' : ''}`} />
            </button>

            {rulesOpen && (
              <div className="absolute z-50 mt-2 w-72 max-h-96 overflow-y-auto rounded-xl border border-white/10 bg-[#0d1117] shadow-2xl">
                <button
                  onClick={() => setSelectedRules([])}
                  className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-indigo-300 hover:bg-white/5 border-b border-white/10"
                >
                  <Check className="w-4 h-4" /> Ver todas las reglas
                </button>
                {ruleOptions.map((r) => (
                  <label key={r.name} className="flex items-center gap-3 px-4 py-2 text-sm text-white cursor-pointer hover:bg-white/5">
                    <input
                      type="checkbox"
                      checked={selectedRules.includes(r.name)}
                      onChange={() => toggleRule(r.name)}
                      className="accent-indigo-500"
                    />
                    <span className="truncate">{r.label}</span>
                  </label>
                ))}
              </div>
            )}
          </div>

          {hasFilters && (
            <div className="flex items-center gap-2 text-xs text-muted">
              <span className="bg-white/5 border border-white/10 rounded-full px-3 py-1">
                Filtrando: {periodLabel} · {selectedRules.length > 0 ? `${selectedRules.length} reglas` : 'todas las reglas'} · {selectedGroups.length > 0 ? `${selectedGroups.length} grupos` : 'todos los grupos'}
              </span>
              {totalRecordsAll > 0 && (
                <span className="bg-white/5 border border-white/10 rounded-full px-3 py-1">
                  {fmt(totalErrorsAll)} errores en {fmt(totalRecordsAll)} registros analizados
                </span>
              )}
            </div>
          )}
        </div>
      </GlassContainer>

      {sorted.length === 0 ? (
        <GlassContainer className="text-center py-16">
          <FolderOpen className="w-16 h-16 text-muted mx-auto mb-4" />
          <p className="text-xl text-muted">No hay datos para los filtros seleccionados</p>
          <p className="text-sm text-muted mt-2">
            Prueba con otro período, sin filtrar por reglas{selectedGroups.length > 0 ? ' o sin filtrar por grupo' : ''}
          </p>
        </GlassContainer>
      ) : (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
            <GlassContainer className="flex items-center gap-4">
              <FolderOpen className="w-10 h-10 text-indigo-400" />
              <div>
                <p className="text-2xl font-bold text-white">{sorted.length}</p>
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
                <p className="text-sm text-muted">
                  {selectedRules.length > 0 ? 'Errores (reglas seleccionadas)' : 'Errores encontrados'}
                </p>
              </div>
            </GlassContainer>
            <GlassContainer className="flex flex-col items-center justify-center py-3">
              <div className="flex items-center gap-3">
                <TrendingUp className="w-6 h-6 text-green-400" />
                <span className="text-4xl font-bold text-white">{scoreAvgGeneral > 0 ? scoreAvgGeneral.toFixed(1) : '-'}</span>
              </div>
              <p className="text-sm text-muted">{useRulePct ? 'Cumplimiento general (reglas seleccionadas)' : 'Score promedio general'}</p>
            </GlassContainer>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-6 mb-8">
            {sorted.map((g: any) => {
              const color = g.color || '#6366f1'
              const errs = g.total_errors || 0
              const recs = g.total_records || 0
              const errPct = recs > 0 ? ((errs / recs) * 100).toFixed(1) : '0.0'
              const passPct = recs > 0 ? Math.min(100, Math.max(0, ((recs - errs) / recs) * 100)) : null
              const gaugeScore = useRulePct ? passPct : g.avg_score
              return (
                <GlassContainer key={g.id} className="flex flex-col items-center text-center">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="w-3 h-3 rounded-full" style={{ backgroundColor: color }} />
                    <h3 className="text-sm font-semibold text-white leading-tight">{g.name}</h3>
                  </div>
                  {gaugeScore != null ? (
                    <QualityGauge score={gaugeScore} size={130} />
                  ) : (
                    <div className="flex items-center justify-center h-[130px] text-muted text-xs">Sin datos</div>
                  )}
                  {useRulePct && (
                    <p className="text-[10px] text-indigo-300 -mt-1">cumplimiento: reglas seleccionadas</p>
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
                {useRulePct ? 'Errores de las reglas seleccionadas por grupo (%)' : 'Comparativa de Scores por Grupo'}
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
                      formatter={(value: number) => [`${value.toFixed(2)}%`, useRulePct ? 'Errores (reglas seleccionadas)' : 'Score']}
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

          {ruleBarData.length > 0 && (
            <GlassContainer>
              <h2 className="text-xl font-semibold text-white mb-1 flex items-center gap-2">
                <BarChart3 className="w-5 h-5 text-indigo-400" />
                Porcentaje de errores por regla
              </h2>
              <p className="text-xs text-muted mb-4">
                {selectedRules.length > 0
                  ? `Reglas seleccionadas: ${selectedRules.map((r) => ruleLabelOf(r)).join(', ')}`
                  : 'Mostrando las 15 reglas con mayor porcentaje en el reporte más reciente de cada proyecto'}
              </p>
              <div className="max-h-96 overflow-y-auto pr-1">
                <ResponsiveContainer width="100%" height={Math.max(ruleBarData.length * 42, 220)}>
                  <BarChart data={ruleBarData} layout="vertical" margin={{ top: 4, right: 20, bottom: 4, left: 8 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" horizontal={false} />
                    <XAxis type="number" domain={[0, 100]} tickFormatter={(v: number) => `${v}%`} stroke="#94a3b8" tick={{ fontSize: 12 }} />
                    <YAxis type="category" dataKey="name" width={190} stroke="#94a3b8" tick={{ fontSize: 12 }} />
                    <Tooltip
                      contentStyle={{
                        background: 'rgba(0,0,0,0.8)',
                        border: '1px solid rgba(255,255,255,0.1)',
                        borderRadius: '8px',
                        color: 'white',
                      }}
                      formatter={(value: number, _name: string, item: any) => [
                        `${Number((value ?? 0).toFixed(2))}%`,
                        `${item?.payload?.failed ?? 0} errores de ${item?.payload?.total ?? 0} registros`,
                      ]}
                    />
                    <Bar dataKey="pct" name="Errores" fill="#6366f1" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </GlassContainer>
          )}
        </>
      )}
    </div>
  )
}