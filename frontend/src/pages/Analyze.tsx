import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  BookOpen, Play, AlertCircle, Loader2,
  ChevronDown, ChevronRight,
} from 'lucide-react'
import api from '../api/client'
import GlassContainer from '../components/layout/GlassContainer'

const GROUP_LABELS: Record<string, string> = {
  basico: 'Básico',
  formato: 'Formato y validación',
  fechas: 'Fechas',
  negocio: 'Reglas de negocio',
  avanzadas: 'Avanzadas',
  integridad: 'Integridad',
  personas: 'Personas',
}

const PERSON_RULES = ['fuzzy_name_match', 'fuzzy_id_match', 'similar_dob', 'person_composite_similarity']

export default function Analyze() {
  const navigate = useNavigate()
  const [projectName, setProjectName] = useState('')
  const [sourceId, setSourceId] = useState('')
  const [selectedRules, setSelectedRules] = useState<string[]>([])
  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>({})
  const [selectedColumns, setSelectedColumns] = useState<string[]>([])
  const [starting, setStarting] = useState(false)
  const [startError, setStartError] = useState('')
  const [similarityLevel, setSimilarityLevel] = useState<string>('profundo')

  const { data: rulesData } = useQuery({
    queryKey: ['rules-groups'],
    queryFn: () => api.get('/rules/groups').then((r) => r.data),
  })

  const groups = (rulesData?.groups ?? []).filter((g: any) => g.name !== 'todo')
  const simLevels = (rulesData?.similarity_levels ?? []) as Array<{ name: string; label: string; desc: string; rules: string[] }>

  useEffect(() => {
    if (groups.length > 0) {
      const all: string[] = groups.flatMap((g: any) => g.rules.map((r: any) => r.name))
      setSelectedRules([...new Set(all)])
      const expanded: Record<string, boolean> = {}
      groups.forEach((g: any) => { expanded[g.name] = true })
      setExpandedGroups(expanded)
    }
  }, [rulesData])

  const changeSimilarityLevel = (level: string) => {
    setSimilarityLevel(level)
    const lvl = simLevels.find((l: any) => l.name === level)
    const levelRules = lvl?.rules ?? []
    setSelectedRules((prev) => {
      const withoutPerson = prev.filter((r) => !PERSON_RULES.includes(r))
      return [...withoutPerson, ...levelRules]
    })
  }

  const { data: sources, isLoading } = useQuery({
    queryKey: ['sources'],
    queryFn: () => api.get('/sources').then((r) => r.data),
  })

  const { data: previewData, isLoading: previewLoading } = useQuery({
    queryKey: ['preview', sourceId],
    queryFn: () => api.post(`/sources/${sourceId}/preview`).then((r) => r.data),
    enabled: !!sourceId,
  })

  useEffect(() => {
    if (previewData?.columns) {
      setSelectedColumns(previewData.columns)
    }
  }, [previewData])

  const handleSubmit = async () => {
    setStartError('')
    setStarting(true)
    try {
      const payload: any = {
        project_name: projectName || `Análisis ${new Date().toLocaleDateString()}`,
        source_id: sourceId,
        rules: selectedRules,
      }
      if (selectedColumns.length > 0 && selectedColumns.length < (previewData?.columns?.length || 0)) {
        payload.columns = selectedColumns
      }
      const res = await api.post('/analyze/start', payload)
      navigate(`/processes/${res.data.project_id}`)
    } catch (err: any) {
      setStarting(false)
      setStartError(err?.response?.data?.detail || 'Error al iniciar el análisis')
    }
  }

  const syncLevelFromRules = (rules: string[]) => {
    const activePerson = rules.filter((r) => PERSON_RULES.includes(r))
    const match = simLevels.find((lvl) => {
      const lvlRules = lvl.rules ?? []
      return lvlRules.length === activePerson.length && lvlRules.every((r) => activePerson.includes(r))
    })
    setSimilarityLevel(match?.name ?? '')
  }

  const toggleGroup = (groupName: string, rules: any[]) => {
    const ruleNames = rules.map((r) => r.name)
    const allSelected = ruleNames.every((r) => selectedRules.includes(r))
    let next: string[]
    if (allSelected) {
      next = selectedRules.filter((r: string) => !ruleNames.includes(r))
    } else {
      const newRules = [...selectedRules]
      ruleNames.forEach((r) => { if (!newRules.includes(r)) newRules.push(r) })
      next = newRules
    }
    setSelectedRules(next)
    if (groupName === 'personas') syncLevelFromRules(next)
  }

  const toggleRule = (ruleName: string) => {
    setSelectedRules((prev) => {
      const next = prev.includes(ruleName) ? prev.filter((r) => r !== ruleName) : [...prev, ruleName]
      if (PERSON_RULES.includes(ruleName)) syncLevelFromRules(next)
      return next
    })
  }

  const toggleExpand = (groupName: string) => {
    setExpandedGroups((prev) => ({ ...prev, [groupName]: !prev[groupName] }))
  }

  const selectAll = () => {
    const all: string[] = groups.flatMap((g: any) => g.rules.map((r: any) => r.name))
    setSelectedRules([...new Set(all)])
    syncLevelFromRules([...new Set(all)])
  }

  const clearAll = () => {
    setSelectedRules([])
    syncLevelFromRules([])
  }

  const sourceLabels: Record<string, string> = {
    postgresql: 'PostgreSQL', mysql: 'MySQL', sqlserver: 'SQL Server',
    sqlite: 'SQLite', csv: 'CSV', excel: 'Excel', json: 'JSON', parquet: 'Parquet',
  }

  const countSelected = selectedRules.length
  const countTotal = groups.reduce((s: number, g: any) => s + g.rules.length, 0)

  return (
    <div>
      <h1 className="text-3xl font-bold mb-8">Nuevo Análisis</h1>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <GlassContainer>
            <h2 className="text-xl font-semibold mb-4">Nombre del Análisis</h2>
            <input type="text" value={projectName} onChange={(e) => setProjectName(e.target.value)}
              className="glass-input" placeholder="Ej: Análisis de ventas Q1" />
          </GlassContainer>

          <GlassContainer>
            <h2 className="text-xl font-semibold mb-4">Fuente de Datos</h2>

            {isLoading ? (
              <div className="flex items-center gap-2 text-muted">
                <Loader2 className="w-4 h-4 animate-spin" /> Cargando fuentes...
              </div>
            ) : sources?.length > 0 ? (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm text-muted mb-1">Seleccionar fuente</label>
                  <select value={sourceId} onChange={(e) => setSourceId(e.target.value)}
                    className="glass-input">
                    <option value="">Seleccionar fuente...</option>
                    {sources.map((s: any) => (
                      <option key={s.id} value={s.id}>
                        {s.name} ({sourceLabels[s.source_type] || s.source_type}{s.query ? ` · ${s.query.slice(0, 60)}` : ''})
                      </option>
                    ))}
                  </select>
                </div>

                {sourceId && (() => {
                  const s = sources.find((x: any) => x.id === sourceId)
                  if (!s) return null
                  return (
                    <div className="text-sm text-muted space-y-1 bg-white/5 rounded-lg p-3">
                      <p><span className="text-indigo-300">Conexión:</span> {s.data_source_name}</p>
                      <p><span className="text-indigo-300">Tipo:</span> {sourceLabels[s.source_type] || s.source_type}</p>
                      {s.query && <p><span className="text-indigo-300">Consulta:</span> <code className="text-xs">{s.query}</code></p>}
                    </div>
                  )
                })()}

                {sourceId && previewLoading && (
                  <div className="flex items-center gap-2 text-xs text-muted">
                    <Loader2 className="w-3 h-3 animate-spin" /> Cargando columnas...
                  </div>
                )}

                {sourceId && previewData?.columns && (
                  <div>
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-sm font-medium">Columnas</span>
                      <span className="text-xs text-muted">{selectedColumns.length}/{previewData.columns.length}</span>
                    </div>
                    <div className="flex gap-2 mb-3">
                      <button onClick={() => setSelectedColumns([...previewData.columns])}
                        className="text-xs px-3 py-1 rounded-full bg-white/10 hover:bg-white/20 transition-colors">Todas</button>
                      <button onClick={() => setSelectedColumns([])}
                        className="text-xs px-3 py-1 rounded-full bg-white/10 hover:bg-white/20 transition-colors">Ninguna</button>
                    </div>
                    <div className="space-y-1">
                      {previewData.columns.map((col: string) => (
                        <label key={col} className="flex items-center gap-2 p-1.5 rounded hover:bg-white/5 cursor-pointer">
                          <input type="checkbox" checked={selectedColumns.includes(col)}
                            onChange={() => {
                              setSelectedColumns((prev) =>
                                prev.includes(col) ? prev.filter((c) => c !== col) : [...prev, col]
                              )
                            }}
                            className="w-3.5 h-3.5 rounded accent-indigo-500" />
                          <span className="text-xs">{col}</span>
                        </label>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-center py-8">
                <BookOpen className="w-12 h-12 mx-auto mb-2 text-muted" />
                <p className="text-muted">No hay fuentes de datos</p>
                <p className="text-xs text-muted mt-1">Crea una fuente en el menú Fuentes primero.</p>
              </div>
            )}
          </GlassContainer>
        </div>

        <div className="space-y-6">
          <GlassContainer>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-semibold">Reglas de Validación</h2>
              <span className="text-xs text-muted">{countSelected}/{countTotal}</span>
            </div>

            <div className="flex gap-2 mb-4">
              <button onClick={selectAll} className="text-xs px-3 py-1 rounded-full bg-white/10 hover:bg-white/20 transition-colors">Todas</button>
              <button onClick={clearAll} className="text-xs px-3 py-1 rounded-full bg-white/10 hover:bg-white/20 transition-colors">Ninguna</button>
            </div>

            <div className="space-y-3">
              {groups.map((group: any) => {
                const ruleNames = group.rules.map((r: any) => r.name)
                const allSelected = ruleNames.every((r: string) => selectedRules.includes(r))
                const someSelected = ruleNames.some((r: string) => selectedRules.includes(r))
                const isExpanded = expandedGroups[group.name]

                return (
                  <div key={group.name} className="rounded-lg bg-white/5 overflow-hidden">
                    <div className="flex items-center gap-2 p-2">
                      <button onClick={() => toggleExpand(group.name)} className="p-1 hover:bg-white/10 rounded">
                        {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                      </button>
                      <input type="checkbox"
                        checked={allSelected}
                        ref={(el) => { if (el && someSelected && !allSelected) el.indeterminate = true }}
                        onChange={() => toggleGroup(group.name, group.rules)}
                        className="w-4 h-4 rounded accent-indigo-500" />
                      <span className="text-sm font-medium">{GROUP_LABELS[group.name] || group.name}</span>
                      <span className="text-xs text-muted ml-auto">{ruleNames.filter((r: string) => selectedRules.includes(r)).length}/{ruleNames.length}</span>
                    </div>

                    {isExpanded && group.name === 'personas' && simLevels.length > 0 ? (
                      <div className="pl-10 pb-3 space-y-2">
                        {simLevels.map((lvl: any) => (
                          <label key={lvl.name} className={`flex items-start gap-2 p-2 rounded-lg cursor-pointer transition-colors ${
                            similarityLevel === lvl.name ? 'bg-indigo-500/15 border border-indigo-500/30' : 'hover:bg-white/5'
                          }`}>
                            <input type="radio" name="similarity-level" checked={similarityLevel === lvl.name}
                              onChange={() => changeSimilarityLevel(lvl.name)}
                              className="w-4 h-4 mt-0.5 accent-indigo-500" />
                            <div className="flex-1 min-w-0">
                              <span className={`text-xs font-medium ${
                                lvl.name === 'rapido' ? 'text-green-300' :
                                lvl.name === 'medio' ? 'text-yellow-300' :
                                lvl.name === 'profundo' ? 'text-red-300' :
                                'text-muted'
                              }`}>{lvl.label}</span>
                              {lvl.desc && <p className="text-[10px] text-muted mt-0.5">{lvl.desc}</p>}
                            </div>
                          </label>
                        ))}
                      </div>
                    ) : isExpanded ? (
                      <div className="pl-10 pb-2 space-y-1">
                        {group.rules.map((rule: any) => (
                          <label key={rule.name} className="flex items-center gap-2 p-1.5 rounded hover:bg-white/5 cursor-pointer">
                            <input type="checkbox" checked={selectedRules.includes(rule.name)}
                              onChange={() => toggleRule(rule.name)}
                              className="w-3.5 h-3.5 rounded accent-indigo-500" />
                            <span className="text-xs">{rule.label}</span>
                            <span className={`text-xs ml-auto px-1.5 py-0.5 rounded-full ${rule.severity === 'error' ? 'bg-red-500/20 text-red-300' : 'bg-yellow-500/20 text-yellow-300'}`}>
                              {rule.severity === 'error' ? 'error' : 'warn'}
                            </span>
                          </label>
                        ))}
                      </div>
                    ) : null}
                  </div>
                )
              })}
            </div>
          </GlassContainer>

          <button onClick={handleSubmit} disabled={!sourceId || starting || selectedRules.length === 0}
            className="btn-primary w-full flex items-center justify-center gap-2 disabled:opacity-50">
            {starting ? (
              <><Loader2 className="w-4 h-4 animate-spin" /> Iniciando...</>
            ) : (
              <><Play className="w-4 h-4" /> Ejecutar Análisis</>
          )}
          </button>

          {startError && (
            <div className="bg-red-500/20 border border-red-500/30 rounded-xl p-4 text-red-300 flex items-start gap-2">
              <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
              <span className="text-sm">{startError}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
