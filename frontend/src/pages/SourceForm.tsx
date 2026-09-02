import { useState, useEffect, useMemo, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import {
  Save, X, AlertCircle, Database, Loader2,
  Search, Code2, Table2, Lightbulb, Clock, ToggleLeft, ToggleRight, AlertTriangle,
} from 'lucide-react'
import api from '../api/client'
import GlassContainer from '../components/layout/GlassContainer'

interface TableInfo { table: string; column: string; type: string; nullable: boolean }
interface Suggestion { table: string; row_count: number | null; columns: number; col_names: string[]; tags: string[]; score: number; reason: string }
interface SourcePreview { columns: string[]; rows: any[][]; total_rows: number }
interface ColumnInfo { name: string; type: string; nullable: boolean }
interface TableColumns { table: string; columns: ColumnInfo[] }

const sourceLabels: Record<string, string> = {
  postgresql: 'PostgreSQL', mysql: 'MySQL', sqlserver: 'SQL Server',
  oracle: 'Oracle', informix: 'Informix', sqlite: 'SQLite',
  csv: 'CSV', excel: 'Excel', json: 'JSON', parquet: 'Parquet',
}

const isFileType = (st: string) => ['csv', 'excel', 'json', 'parquet'].includes(st)

const extractTablesFromQuery = (q: string): string[] => {
  const names = new Set<string>()
  const re = /\b(?:FROM|JOIN)\s+([^\s;,()]+)/gi
  let m
  while ((m = re.exec(q || ''))) {
    names.add(m[1].replace(/[\[\]`"]/g, '').trim())
  }
  return Array.from(names)
}

const pairKey = (a: string, b: string) => (a < b ? `${a}||${b}` : `${b}||${a}`)

const parseJoinRelations = (q: string, tables: string[]): Record<string, { tableA: string; colA: string; tableB: string; colB: string }> => {
  const aliasOf = new Map<string, string>()
  tables.forEach((t, i) => aliasOf.set(`t${i + 1}`, t))
  const out: Record<string, { tableA: string; colA: string; tableB: string; colB: string }> = {}
  const re = /\bLEFT JOIN\s+([A-Za-z_][\w$]*)\s+([A-Za-z_][\w$]*)\s+ON\s+([A-Za-z_][\w$]*)\.([A-Za-z_][\w$]*)\s*=\s*([A-Za-z_][\w$]*)\.([A-Za-z_][\w$]*)/gi
  let m
  while ((m = re.exec(q || ''))) {
    const joinedAlias = m[3]
    const baseAlias = m[5]
    const tblA = aliasOf.get(baseAlias) || baseAlias
    const tblB = aliasOf.get(joinedAlias) || joinedAlias
    const colA = m[6]
    const colB = m[4]
    const key = pairKey(tblA, tblB)
    out[key] = {
      tableA: tblA < tblB ? tblA : tblB,
      tableB: tblA < tblB ? tblB : tblA,
      colA: tblA < tblB ? colA : colB,
      colB: tblA < tblB ? colB : colA,
    }
  }
  return out
}

export default function SourceForm() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const { id } = useParams()
  const [searchParams] = useSearchParams()
  const duplicateId = searchParams.get('duplicate')
  const isEdit = !!id

  const [name, setName] = useState('')
  const [dsId, setDsId] = useState('')
  const [query, setQuery] = useState('')
  const [selectedColumns, setSelectedColumns] = useState<string[]>([])
  const [rowLimit, setRowLimit] = useState<number | null>(null)
  const [mode, setMode] = useState<'sql' | 'visual'>('visual')
  const [saving, setSaving] = useState(false)
  const [storageMode, setStorageMode] = useState('connection')
  const [refreshCron, setRefreshCron] = useState('')
  const [cronFreq, setCronFreq] = useState('daily')
  const [cronMinute, setCronMinute] = useState('0')
  const [cronHour, setCronHour] = useState('6')
  const [cronWeekday, setCronWeekday] = useState('1')
  const [cronMonthDay, setCronMonthDay] = useState('1')
  const [cronInterval, setCronInterval] = useState('30')
  const [showCronRaw, setShowCronRaw] = useState(false)
  const [cronEnabled, setCronEnabled] = useState(false)
  const [error, setError] = useState('')
  const [saveProgress, setSaveProgress] = useState<{ active: boolean; step: number; total: number; message: string } | null>(null)

  // Visual mode
  const [tables, setTables] = useState<{ name: string; row_count: number | null }[]>([])
  const [tablesLoading, setTablesLoading] = useState(false)
  const [tableSearch, setTableSearch] = useState('')
  const [selectedTables, setSelectedTables] = useState<string[]>([])
  const [tableColumns, setTableColumns] = useState<TableColumns[]>([])
  const [columnsLoading, setColumnsLoading] = useState(false)
  const [combineMode, setCombineMode] = useState<'union' | 'join'>('union')
  const [joinRelations, setJoinRelations] = useState<Record<string, { tableA: string; colA: string; tableB: string; colB: string }>>({})

  // Suggestions
  const [suggestions, setSuggestions] = useState<Suggestion[]>([])
  const [suggestLoading, setSuggestLoading] = useState(false)
  const [showSuggest, setShowSuggest] = useState(false)

  // Preview
  const [formPreview, setFormPreview] = useState<SourcePreview | null>(null)
  const [formPreviewLoading, setFormPreviewLoading] = useState(false)
  const [formPreviewError, setFormPreviewError] = useState('')
  const [columnSamples, setColumnSamples] = useState<Record<string, any>>({})
  const [tablesError, setTablesError] = useState('')
  const [tableActiveTab, setTableActiveTab] = useState<'visual' | 'sql'>('visual')

  const filteredTables = tables.filter(t => t.name.toLowerCase().includes(tableSearch.toLowerCase()))

  const { data: sourceData } = useQuery({
    queryKey: ['source', id],
    queryFn: () => api.get(`/sources/${id}`).then(r => r.data),
    enabled: isEdit,
  })

  const { data: duplicateData } = useQuery({
    queryKey: ['source', duplicateId],
    queryFn: () => api.get(`/sources/${duplicateId}`).then(r => r.data),
    enabled: !!duplicateId,
  })

  const { data: connections } = useQuery({
    queryKey: ['datasources'],
    queryFn: () => api.get('/datasources').then(r => r.data),
  })

  useEffect(() => {
    if (duplicateData) {
      setName(`Copia de ${duplicateData.name}`)
      setDsId(duplicateData.data_source_id)
      setQuery(duplicateData.query || '')
      setSelectedColumns(duplicateData.selected_columns || [])
      setRowLimit(duplicateData.row_limit)
      setStorageMode(duplicateData.storage_mode || 'connection')
      setRefreshCron(duplicateData.refresh_cron || '')
      setCronEnabled(!!duplicateData.refresh_cron)
      const initialMode = duplicateData.query && !duplicateData.selected_columns?.length ? 'sql' : 'visual'
      setMode(initialMode)
      setTableActiveTab(initialMode)
      if (duplicateData.preview_data) setFormPreview(duplicateData.preview_data)
      if (duplicateData.refresh_cron) {
        const parts = (duplicateData.refresh_cron || '').split(/\s+/)
        if (parts.length >= 5 && !duplicateData.refresh_cron.includes('1-5')) {
          const sec = parts[0], min = parts[1], hour = parts[2], day = parts[3], month = parts[4], wday = parts[5] || '*'
          if (sec === '0' && hour !== '*' && min !== '*') {
            if (hour === '*' && min === '0') { setCronFreq('hourly') }
            else if (day === '*' && month === '*' && wday === '*') { setCronFreq('daily'); setCronHour(hour); setCronMinute(min) }
            else if (day === '*' && month === '*' && wday !== '*') { setCronFreq('weekly'); setCronHour(hour); setCronMinute(min); if (wday !== '*') setCronWeekday(wday) }
            else if (day !== '*' && month === '*') { setCronFreq('monthly'); setCronHour(hour); setCronMinute(min); setCronMonthDay(day) }
          } else if (sec === '0' && hour === '*' && min.startsWith('*/')) {
            setCronFreq('minutes'); setCronInterval(min.replace('*/', ''))
          }
        }
      }
      if (initialMode === 'visual') {
        const q = (duplicateData.query || '').trim()
        const tablesInQ = extractTablesFromQuery(q)
        if (tablesInQ.length > 0) {
          setSelectedTables(tablesInQ)
          loadColumnsForTables(duplicateData.data_source_id, tablesInQ, duplicateData.selected_columns || [])
        }
        if (/\bJOIN\b/i.test(q)) {
          setCombineMode('join')
          setJoinRelations(parseJoinRelations(q, tablesInQ))
        } else {
          setCombineMode('union')
          setJoinRelations({})
        }
      }
    }
  }, [duplicateData])

  useEffect(() => {
    if (sourceData) {
      setName(sourceData.name)
      setDsId(sourceData.data_source_id)
      setQuery(sourceData.query || '')
      setSelectedColumns(sourceData.selected_columns || [])
      setRowLimit(sourceData.row_limit)
      setStorageMode(sourceData.storage_mode || 'connection')
      setRefreshCron(sourceData.refresh_cron || '')
      setCronEnabled(!!sourceData.refresh_cron)
      const initialMode = sourceData.query && !sourceData.selected_columns?.length ? 'sql' : 'visual'
      setMode(initialMode)
      setTableActiveTab(initialMode)
      if (sourceData.preview_data) setFormPreview(sourceData.preview_data)
      if (sourceData.refresh_cron) {
        const parts = (sourceData.refresh_cron || '').split(/\s+/)
        if (parts.length >= 5 && !sourceData.refresh_cron.includes('1-5')) {
          const sec = parts[0], min = parts[1], hour = parts[2], day = parts[3], month = parts[4], wday = parts[5] || '*'
          if (sec === '0' && hour !== '*' && min !== '*') {
            if (hour === '*' && min === '0') { setCronFreq('hourly') }
            else if (day === '*' && month === '*' && wday === '*') { setCronFreq('daily'); setCronHour(hour); setCronMinute(min) }
            else if (day === '*' && month === '*' && wday !== '*') { setCronFreq('weekly'); setCronHour(hour); setCronMinute(min); if (wday !== '*') setCronWeekday(wday) }
            else if (day !== '*' && month === '*') { setCronFreq('monthly'); setCronHour(hour); setCronMinute(min); setCronMonthDay(day) }
          } else if (sec === '0' && hour === '*' && min.startsWith('*/')) {
            setCronFreq('minutes'); setCronInterval(min.replace('*/', ''))
          }
        }
      }
      if (initialMode === 'visual') {
        const q = (sourceData.query || '').trim()
        const tablesInQ = extractTablesFromQuery(q)
        if (tablesInQ.length > 0) {
          setSelectedTables(tablesInQ)
          loadColumnsForTables(sourceData.data_source_id, tablesInQ, sourceData.selected_columns || [])
        }
        if (/\bJOIN\b/i.test(q)) {
          setCombineMode('join')
          setJoinRelations(parseJoinRelations(q, tablesInQ))
        } else {
          setCombineMode('union')
          setJoinRelations({})
        }
      }
    }
  }, [sourceData])

  useEffect(() => {
    if (!dsId) { setTables([]); setSelectedTables([]); setTableColumns([]); setSuggestions([]); setTablesError(''); setCombineMode('union'); setJoinRelations({}); return }
    setTablesLoading(true); setTablesError(''); setShowSuggest(false)
    api.get(`/datasources/${dsId}/tables`).then(r => {
      const raw = r.data.tables || []
      setTables(Array.isArray(raw) ? (typeof raw[0] === 'string' ? raw.map((n: string) => ({ name: n, row_count: null })) : raw) : [])
      if (raw.length === 0) setTablesError('No se encontraron tablas en la base de datos')
    }).catch(e => {
      setTablesError(e?.response?.data?.detail || 'Error al cargar tablas')
    }).finally(() => setTablesLoading(false))
  }, [dsId])

  const conn = useMemo(() => (connections || []).find((c: any) => c.id === dsId), [connections, dsId])
  const isFile = conn && isFileType(conn.source_type)

  const allColumnNames = useMemo(() => {
    const names = new Set<string>()
    tableColumns.forEach(g => g.columns.forEach(c => names.add(c.name)))
    return Array.from(names)
  }, [tableColumns])

  const columnsForTable = (t: string): ColumnInfo[] => {
    const g = tableColumns.find(x => x.table === t)
    return g ? g.columns : []
  }

  const buildVisualQuery = useCallback(() => {
    if (selectedTables.length === 0) return ''
    if (selectedColumns.length === 0 && selectedTables.length === 1) {
      return `SELECT * FROM ${selectedTables[0]}`
    }
    const cols = selectedColumns.length > 0
      ? selectedColumns
      : Array.from(new Set(tableColumns.flatMap(g => g.columns.map(c => c.name))))
    if (cols.length === 0) return ''
    return selectedTables.map(t => {
      const tcols = new Set(columnsForTable(t).map(c => c.name))
      const parts = cols.map(c => tcols.has(c) ? c : `NULL AS ${c}`)
      return `SELECT ${parts.join(', ')} FROM ${t}`
    }).join('\nUNION ALL\n')
  }, [selectedTables, selectedColumns, tableColumns])

  const buildJoinQuery = useCallback(() => {
    if (selectedTables.length === 0) return ''
    const aliasOf = new Map<string, string>()
    selectedTables.forEach((t, i) => aliasOf.set(t, `t${i + 1}`))
    const edges: { a: string; b: string; ca: string; cb: string }[] = []
    Object.values(joinRelations).forEach(rel => {
      if (rel.colA && rel.colB) edges.push({ a: rel.tableA, b: rel.tableB, ca: rel.colA, cb: rel.colB })
    })
    const base = selectedTables[0]
    const reach = new Set([base])
    const joins: { nt: string; nc: string; tt: string; tc: string }[] = []
    const used = new Set<number>()
    let progress = true
    while (progress) {
      progress = false
      edges.forEach((e, i) => {
        if (used.has(i)) return
        if (reach.has(e.a) && !reach.has(e.b)) {
          joins.push({ nt: e.b, nc: e.cb, tt: e.a, tc: e.ca })
          reach.add(e.b); used.add(i); progress = true
        } else if (reach.has(e.b) && !reach.has(e.a)) {
          joins.push({ nt: e.a, nc: e.ca, tt: e.b, tc: e.cb })
          reach.add(e.a); used.add(i); progress = true
        }
      })
    }
    if (reach.size !== selectedTables.length) return ''
    const cols = selectedColumns.length > 0 ? selectedColumns : allColumnNames
    if (cols.length === 0) return ''
    const resolved = cols.map(name => {
      for (const t of selectedTables) {
        if (columnsForTable(t).some(c => c.name === name)) return { alias: aliasOf.get(t)!, col: name }
      }
      return { alias: aliasOf.get(base)!, col: name }
    })
    const selectParts = resolved.map(r => `${r.alias}.${r.col} AS ${r.col}`)
    const fromParts = [`FROM ${base} ${aliasOf.get(base)}`]
    joins.forEach(j => {
      fromParts.push(`LEFT JOIN ${j.nt} ${aliasOf.get(j.nt)} ON ${aliasOf.get(j.nt)}.${j.nc} = ${aliasOf.get(j.tt)}.${j.tc}`)
    })
    return `SELECT ${selectParts.join(', ')}\n${fromParts.join('\n')}`
  }, [selectedTables, selectedColumns, tableColumns, allColumnNames, joinRelations])

  const pairRows = useMemo(() => {
    const rows: { a: string; b: string; key: string }[] = []
    for (let i = 0; i < selectedTables.length; i++) {
      for (let j = i + 1; j < selectedTables.length; j++) {
        rows.push({ a: selectedTables[i], b: selectedTables[j], key: pairKey(selectedTables[i], selectedTables[j]) })
      }
    }
    return rows
  }, [selectedTables])

  const setRelation = (a: string, b: string, ca: string, cb: string) => {
    const key = pairKey(a, b)
    setJoinRelations(prev => {
      const next = { ...prev }
      if (!ca && !cb) delete next[key]
      else next[key] = { tableA: a < b ? a : b, tableB: a < b ? b : a, colA: a < b ? ca : cb, colB: a < b ? cb : ca }
      return next
    })
  }

  const previewQuery = useMemo(() => {
    if (!dsId || isFile) return null
    if (mode === 'sql') return query.trim() || null
    if (mode === 'visual' && selectedTables.length > 0) {
      return combineMode === 'join' ? buildJoinQuery() : buildVisualQuery()
    }
    return null
  }, [dsId, isFile, mode, query, buildVisualQuery, buildJoinQuery, selectedTables, combineMode])

  useEffect(() => {
    if (!dsId || !previewQuery) { setFormPreview(null); setFormPreviewError(''); setFormPreviewLoading(false); return }
    setFormPreview(null)
    setFormPreviewError('')
    setFormPreviewLoading(true)
    const timer = setTimeout(async () => {
      try {
        const res = await api.post(`/datasources/${dsId}/preview-query`, {
          query: previewQuery,
          selected_columns: selectedColumns,
          row_limit: rowLimit || undefined,
        })
        if (res.data.total_rows > 0) setFormPreview(res.data)
        else setFormPreview(null)
      } catch (e: any) {
        setFormPreview(null)
        setFormPreviewError(e?.response?.data?.detail || 'Error al cargar vista previa')
      } finally { setFormPreviewLoading(false) }
    }, 300)
    return () => clearTimeout(timer)
  }, [dsId, previewQuery, selectedColumns, rowLimit])

  useEffect(() => {
    if (formPreview?.rows?.[0]) {
      const samples: Record<string, any> = {}
      formPreview.columns.forEach((col, idx) => { samples[col] = formPreview!.rows[0][idx] })
      setColumnSamples(samples)
    }
  }, [formPreview])

  const freqLabels: Record<string, string> = {
    minutes: 'Cada N min', hourly: 'Cada hora',
    daily: 'Cada día', weekly: 'Cada semana', monthly: 'Cada mes',
  }
  const weekdayLabels: Record<string, string> = {
    '0': 'Dom', '1': 'Lun', '2': 'Mar', '3': 'Mié', '4': 'Jue', '5': 'Vie', '6': 'Sáb',
  }

  const buildCron = useCallback(() => {
    const h = cronHour.padStart(2, '0')
    const m = cronMinute.padStart(2, '0')
    switch (cronFreq) {
      case 'minutes': return `0 */${cronInterval} * * * *`
      case 'hourly': return `0 0 * * * *`
      case 'daily': return `0 ${m} ${h} * * *`
      case 'weekly': return `0 ${m} ${h} * * ${cronWeekday}`
      case 'monthly': return `0 ${m} ${h} ${cronMonthDay} * *`
      default: return `0 ${m} ${h} * * *`
    }
  }, [cronFreq, cronMinute, cronHour, cronWeekday, cronMonthDay, cronInterval])

  const getCronDescription = useCallback(() => {
    switch (cronFreq) {
      case 'minutes': return `Cada ${cronInterval} minutos`
      case 'hourly': return `Cada hora en el minuto 0`
      case 'daily': return `Todos los días a las ${cronHour.padStart(2, '0')}:${cronMinute.padStart(2, '0')}`
      case 'weekly': return `Los ${weekdayLabels[cronWeekday]?.toLowerCase()} a las ${cronHour.padStart(2, '0')}:${cronMinute.padStart(2, '0')}`
      case 'monthly': return `El día ${cronMonthDay} de cada mes a las ${cronHour.padStart(2, '0')}:${cronMinute.padStart(2, '0')}`
      default: return ''
    }
  }, [cronFreq, cronMinute, cronHour, cronWeekday, cronMonthDay, cronInterval])

  useEffect(() => {
    if (!showCronRaw) {
      setRefreshCron(buildCron())
    }
  }, [buildCron, showCronRaw])

  const applyCronSuggestion = (label: string) => {
    const presets: Record<string, string> = {
      'Cada 5 min': '0 */5 * * * *',
      'Cada 15 min': '0 */15 * * * *',
      'Cada 30 min': '0 */30 * * * *',
      'Cada hora': '0 0 * * * *',
      'Cada 6 horas': '0 0 */6 * * *',
      'Cada día 6am': '0 0 6 * * *',
      'Cada día 8am': '0 0 8 * * *',
      'Cada lun-vie 8am': '0 0 8 * * 1-5',
      'Lunes 8am': '0 0 8 * * 1',
      'Primero de mes 6am': '0 0 6 1 * *',
    }
    setRefreshCron(presets[label] || label)
    setShowCronRaw(true)
  }

  const loadSuggest = async () => {
    if (!dsId) return
    setSuggestLoading(true)
    try {
      const r = await api.get(`/datasources/${dsId}/suggest`)
      setSuggestions(r.data.suggestions || [])
      setShowSuggest(true)
    } catch {} finally { setSuggestLoading(false) }
  }

  const loadColumnsForTables = async (dsIdParam: string, tablesToLoad: string[], forcedCols?: string[]) => {
    if (tablesToLoad.length === 0) { setTableColumns([]); setSelectedColumns([]); return }
    setColumnsLoading(true)
    try {
      const groups: TableColumns[] = await Promise.all(tablesToLoad.map(async t => {
        try {
          const r = await api.get(`/datasources/${dsIdParam}/tables/${encodeURIComponent(t)}/columns`)
          return { table: t, columns: r.data.columns || [] }
        } catch {
          return { table: t, columns: [] }
        }
      }))
      setTableColumns(groups)
      if (forcedCols) {
        setSelectedColumns(forcedCols)
      } else {
        const names = new Set<string>()
        groups.forEach(g => g.columns.forEach(c => names.add(c.name)))
        setSelectedColumns(Array.from(names))
      }
    } catch {
      setTableColumns([])
    } finally { setColumnsLoading(false) }
  }

  const toggleTable = (t: string) => {
    const isSelected = selectedTables.includes(t)
    const next = isSelected ? selectedTables.filter(x => x !== t) : [...selectedTables, t]
    setSelectedTables(next)
    setJoinRelations(prev => {
      const pruned: Record<string, { tableA: string; colA: string; tableB: string; colB: string }> = {}
      Object.entries(prev).forEach(([k, r]) => {
        if (next.includes(r.tableA) && next.includes(r.tableB)) pruned[k] = r
      })
      return pruned
    })
    if (next.length === 0) {
      setTableColumns([]); setSelectedColumns([]); setFormPreview(null); setCombineMode('union'); setJoinRelations({})
    } else {
      loadColumnsForTables(dsId, next)
    }
  }

  const toggleColumn = (col: string) => {
    setSelectedColumns(prev => prev.includes(col) ? prev.filter(c => c !== col) : [...prev, col])
  }

  const selectAllCols = () => setSelectedColumns(allColumnNames)
  const deselectAllCols = () => setSelectedColumns([])

  const applySuggestion = (s: Suggestion) => {
    setSelectedTables([s.table])
    loadColumnsForTables(dsId, [s.table], s.col_names)
  }

  const handleSave = async () => {
    if (!name || !dsId) return
    const visualQuery = combineMode === 'join' ? buildJoinQuery() : buildVisualQuery()
    if (mode === 'visual' && !visualQuery) {
      setError(combineMode === 'join' && selectedTables.length > 1 ? 'Define las relaciones entre las tablas para generar la consulta' : 'Selecciona al menos una tabla')
      return
    }
    setSaving(true); setError('')
    const steps: { msg: string; pct: number }[] = [
      { msg: 'Validando datos...', pct: 10 },
      { msg: 'Guardando en base de datos...', pct: 40 },
    ]
    if (storageMode === 'memory') {
      steps.push({ msg: 'Configurando almacenamiento en memoria...', pct: 60 })
      steps.push({ msg: 'Precargando datos en caché...', pct: 80 })
    }
    if (cronEnabled && storageMode === 'memory') {
      steps.push({ msg: 'Programando actualización automática...', pct: 92 })
    }
    steps.push({ msg: '¡Listo! Redirigiendo...', pct: 100 })
    let stepIdx = 0

    const advance = () => {
      if (stepIdx < steps.length) {
        const s = steps[stepIdx]
        setSaveProgress({ active: true, step: stepIdx + 1, total: steps.length, message: s.msg })
        stepIdx++
      }
    }

    advance()

    const payload: any = {
      name, data_source_id: dsId,
      query: isFile ? '' : (mode === 'sql' ? query : (combineMode === 'join' ? buildJoinQuery() : buildVisualQuery())),
      selected_columns: selectedColumns,
      row_limit: rowLimit,
      storage_mode: storageMode,
      refresh_cron: cronEnabled && storageMode === 'memory' ? (refreshCron || null) : null,
    }
    try {
      advance()
      if (isEdit) {
        await api.put(`/sources/${id}`, { name, data_source_id: dsId, query: payload.query, selected_columns: selectedColumns, row_limit: rowLimit, storage_mode: storageMode, refresh_cron: payload.refresh_cron })
      } else {
        await api.post('/sources', payload)
      }
      if (storageMode === 'memory') {
        advance()
        advance()
      }
      if (cronEnabled && storageMode === 'memory') {
        advance()
      }
      advance()
      queryClient.invalidateQueries({ queryKey: ['sources'] })
      navigate('/datasources')
    } catch (e: any) {
      setSaveProgress(null)
      setError(e?.response?.data?.detail || 'Error al guardar')
    } finally { setSaving(false) }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold">{isEdit ? 'Editar Fuente' : duplicateId ? 'Duplicar Fuente' : 'Nueva Fuente de Datos'}</h1>
          <p className="text-sm text-muted mt-1">{isEdit ? 'Modifica la configuración de la fuente' : duplicateId ? 'Crea una copia de la fuente con nuevos parámetros' : 'Configura una nueva fuente de datos para analizar'}</p>
        </div>
      </div>

      <GlassContainer>
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
          {/* Left: config (2/5) */}
          <div className="lg:col-span-2 space-y-4">
            <div>
              <label className="block text-sm text-muted mb-1">Nombre</label>
              <input type="text" value={name} onChange={e => setName(e.target.value)}
                className="glass-input" placeholder="Ej: Cartera Clientes" />
            </div>

            <div>
              <label className="block text-sm text-muted mb-1">Conexión</label>
              <select value={dsId} onChange={e => { setDsId(e.target.value); setSelectedTables([]); setTableColumns([]); setSelectedColumns([]); setFormPreview(null); setCombineMode('union'); setJoinRelations({}) }}
                className="glass-input">
                <option value="">Seleccionar conexión...</option>
                {(connections || []).map((c: any) => (
                  <option key={c.id} value={c.id}>{c.name} ({sourceLabels[c.source_type] || c.source_type})</option>
                ))}
              </select>
            </div>

            {dsId && (
              <div>
                <label className="block text-sm text-muted mb-2">Modo de almacenamiento</label>
                <div className="flex gap-3">
                  <button onClick={() => setStorageMode('connection')}
                    className={`flex-1 p-3 rounded-xl border text-sm text-center transition-all ${
                      storageMode === 'connection'
                        ? 'bg-indigo-500/20 border-indigo-400'
                        : 'bg-white/5 border-white/10 text-muted hover:bg-white/10'
                    }`}>
                    <Database className="w-5 h-5 mx-auto mb-1" />
                    Conexión directa
                  </button>
                  <button onClick={() => setStorageMode('memory')}
                    className={`flex-1 p-3 rounded-xl border text-sm text-center transition-all ${
                      storageMode === 'memory'
                        ? 'bg-indigo-500/20 border-indigo-400'
                        : 'bg-white/5 border-white/10 text-muted hover:bg-white/10'
                    }`}>
                    <Database className="w-5 h-5 mx-auto mb-1" />
                    En memoria local
                  </button>
                </div>
              </div>
            )}

            {dsId && storageMode === 'memory' && (
              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="text-sm text-muted">Actualización programada</label>
                  <button
                    onClick={() => { setCronEnabled(!cronEnabled); if (cronEnabled) setRefreshCron('') }}
                    className={`flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-lg border transition-all ${
                      cronEnabled
                        ? 'bg-indigo-500/20 border-indigo-400 text-indigo-300'
                        : 'bg-white/5 border-white/10 text-muted hover:bg-white/10'
                    }`}>
                    {cronEnabled ? <ToggleRight className="w-4 h-4" /> : <ToggleLeft className="w-4 h-4" />}
                    {cronEnabled ? 'Activado' : 'Desactivado'}
                  </button>
                </div>
                {cronEnabled && (
                  <div className="bg-indigo-500/5 border border-indigo-500/20 rounded-xl p-3 space-y-3">
                    {showCronRaw ? (
                      <div className="space-y-2">
                        <div className="flex items-center gap-2">
                          <input type="text" value={refreshCron} onChange={e => setRefreshCron(e.target.value)}
                            className="glass-input font-mono text-sm flex-1" placeholder="0 */30 * * * *" />
                          <button onClick={() => setShowCronRaw(false)}
                            className="text-xs text-indigo-400 hover:text-indigo-300 shrink-0 whitespace-nowrap">
                            Volver al selector
                          </button>
                        </div>
                        <div className="flex flex-wrap gap-1">
                          {['Cada 5 min','Cada 15 min','Cada 30 min','Cada hora','Cada 6 horas','Cada día 6am','Cada día 8am','Lunes 8am'].map(lbl => (
                            <button key={lbl} onClick={() => applyCronSuggestion(lbl)}
                              className="text-[10px] px-2 py-0.5 rounded-full bg-white/5 text-muted hover:bg-white/10 transition-colors">
                              {lbl}
                            </button>
                          ))}
                        </div>
                        <p className="text-[11px] text-muted">
                          Formato: <code className="text-indigo-300">seg min hora día mes día-semana</code>
                        </p>
                      </div>
                    ) : (
                      <>
                        <div className="grid grid-cols-5 gap-1.5">
                          {Object.entries(freqLabels).map(([k, v]) => (
                            <button key={k} onClick={() => setCronFreq(k)}
                              className={`text-[11px] py-1.5 rounded-lg border transition-all ${
                                cronFreq === k
                                  ? 'bg-indigo-500/20 border-indigo-400 text-white'
                                  : 'bg-white/5 border-white/10 text-muted hover:bg-white/10'
                              }`}>
                              {v}
                            </button>
                          ))}
                        </div>

                        {(cronFreq === 'daily' || cronFreq === 'weekly' || cronFreq === 'monthly') && (
                          <div className="flex gap-2">
                            <div className="flex-1">
                              <label className="text-[10px] text-muted">Hora</label>
                              <select value={cronHour} onChange={e => setCronHour(e.target.value)} className="glass-input text-xs py-1">
                                {Array.from({ length: 24 }, (_, i) => (
                                  <option key={i} value={String(i)}>{String(i).padStart(2, '0')}:00</option>
                                ))}
                              </select>
                            </div>
                            <div className="flex-1">
                              <label className="text-[10px] text-muted">Minuto</label>
                              <select value={cronMinute} onChange={e => setCronMinute(e.target.value)} className="glass-input text-xs py-1">
                                {Array.from({ length: 12 }, (_, i) => (
                                  <option key={i} value={String(i * 5)}>{String(i * 5).padStart(2, '0')}</option>
                                ))}
                              </select>
                            </div>
                          </div>
                        )}

                        {cronFreq === 'weekly' && (
                          <div>
                            <label className="text-[10px] text-muted">Día de la semana</label>
                            <div className="grid grid-cols-7 gap-1 mt-1">
                              {Object.entries(weekdayLabels).map(([k, v]) => (
                                <button key={k} onClick={() => setCronWeekday(k)}
                                  className={`text-[10px] py-1 rounded-lg border transition-all ${
                                    cronWeekday === k
                                      ? 'bg-indigo-500/20 border-indigo-400 text-white'
                                      : 'bg-white/5 border-white/10 text-muted hover:bg-white/10'
                                  }`}>
                                  {v}
                                </button>
                              ))}
                            </div>
                          </div>
                        )}

                        {cronFreq === 'monthly' && (
                          <div>
                            <label className="text-[10px] text-muted">Día del mes</label>
                            <select value={cronMonthDay} onChange={e => setCronMonthDay(e.target.value)} className="glass-input text-xs py-1 mt-1">
                              {Array.from({ length: 28 }, (_, i) => (
                                <option key={i + 1} value={String(i + 1)}>{i + 1}</option>
                              ))}
                            </select>
                          </div>
                        )}

                        {cronFreq === 'minutes' && (
                          <div>
                            <label className="text-[10px] text-muted">Intervalo (minutos)</label>
                            <select value={cronInterval} onChange={e => setCronInterval(e.target.value)} className="glass-input text-xs py-1 mt-1">
                              {[5, 10, 15, 30, 60, 120, 180, 360, 720, 1440].map(v => (
                                <option key={v} value={String(v)}>{v} min</option>
                              ))}
                            </select>
                          </div>
                        )}

                        <div className="bg-indigo-500/10 border border-indigo-500/20 rounded-lg p-2 text-xs text-indigo-300 text-center">
                          <Clock className="w-3 h-3 inline mr-1 -mt-0.5" />
                          {getCronDescription()}
                        </div>

                        <div className="flex items-center justify-between">
                          <div className="text-[10px] text-muted">
                            Cron: <code className="font-mono text-indigo-300">{buildCron()}</code>
                          </div>
                          <button onClick={() => setShowCronRaw(true)}
                            className="text-[10px] text-muted hover:text-white transition-colors">
                            Avanzado
                          </button>
                        </div>
                      </>
                    )}
                  </div>
                )}
              </div>
            )}

            {dsId && !isFile && (
              <div>
                <label className="block text-xs text-muted mb-1">
                  Límite filas <span className="opacity-50">(opcional)</span>
                </label>
                <input type="number" value={rowLimit ?? ''} onChange={e => setRowLimit(e.target.value ? parseInt(e.target.value) : null)}
                  className="glass-input" placeholder="ej: 10000" min={1} />
              </div>
            )}

            {dsId && isFile && (
              <p className="text-xs text-muted">No requiere consulta — se usarán todos los datos del archivo.</p>
            )}

            {error && (
              <div className="bg-red-500/20 border border-red-500/30 rounded-xl p-3 text-red-300 text-xs flex items-start gap-2">
                <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                <span>{error}</span>
              </div>
            )}

            <div className="flex gap-3 pt-2">
              <button onClick={handleSave} disabled={!name || !dsId || saving}
                className="btn-primary flex items-center gap-2 text-sm">
                {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                {saving ? 'Guardando...' : (isEdit ? 'Actualizar' : 'Guardar Fuente')}
              </button>
              <button onClick={() => navigate('/datasources')} className="btn-ghost flex items-center gap-2 text-sm">
                <X className="w-4 h-4" /> Cancelar
              </button>
            </div>
          </div>

          {/* Right: table panel + preview (3/5) */}
          {dsId && !isFile ? (
            <div className="lg:col-span-3 flex flex-col gap-3 h-full min-h-[500px]">
              {/* Tab panel: Visual | SQL */}
              <div className="border border-white/10 rounded-xl overflow-hidden flex flex-col flex-1">
                <div className="flex border-b border-white/10 bg-white/5">
                  <button onClick={() => { setTableActiveTab('visual'); setMode('visual') }}
                    className={`flex items-center gap-1.5 px-4 py-2 text-sm font-medium transition-all border-b-2 ${
                      tableActiveTab === 'visual' ? 'border-indigo-400 text-indigo-300' : 'border-transparent text-muted hover:text-white'
                    }`}>
                    <Table2 className="w-4 h-4" /> Visual
                  </button>
                  <button onClick={() => { setTableActiveTab('sql'); setMode('sql') }}
                    className={`flex items-center gap-1.5 px-4 py-2 text-sm font-medium transition-all border-b-2 ${
                      tableActiveTab === 'sql' ? 'border-indigo-400 text-indigo-300' : 'border-transparent text-muted hover:text-white'
                    }`}>
                    <Code2 className="w-4 h-4" /> SQL
                  </button>
                </div>

                <div className="p-3 flex-1 overflow-auto">
                  {tableActiveTab === 'visual' ? (
                    <div className="space-y-3">
                      <div className="relative">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted" />
                        <input type="text" value={tableSearch} onChange={e => setTableSearch(e.target.value)}
                          className="glass-input pl-9 text-sm" placeholder="Buscar tabla..." />
                      </div>

                      {tablesLoading ? (
                        <div className="flex items-center gap-2 text-xs text-muted py-2">
                          <Loader2 className="w-3 h-3 animate-spin" /> Cargando tablas...
                        </div>
                      ) : tablesError ? (
                        <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-2 text-xs text-red-300 flex items-start gap-2">
                          <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                          <span>{tablesError}</span>
                        </div>
                      ) : filteredTables.length > 0 ? (
                        <div className="max-h-40 overflow-y-auto space-y-0.5 border border-white/10 rounded-xl p-1.5">
                          {filteredTables.map(t => (
                            <label key={t.name}
                              className={`flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-xs cursor-pointer transition-all ${
                                selectedTables.includes(t.name) ? 'bg-indigo-500/20 text-indigo-300' : 'text-muted hover:bg-white/5'
                              }`}>
                              <input type="checkbox" checked={selectedTables.includes(t.name)}
                                onChange={() => toggleTable(t.name)} className="w-3 h-3 rounded accent-indigo-500 shrink-0" />
                              <span className="truncate">{t.name}</span>
                              {t.row_count !== null && t.row_count !== undefined && (
                                <span className="ml-auto text-[10px] text-muted shrink-0">{t.row_count.toLocaleString()} registros</span>
                              )}
                            </label>
                          ))}
                        </div>
                      ) : (
                        <p className="text-xs text-muted py-2">No hay tablas disponibles</p>
                      )}

                      {selectedTables.length >= 2 && (
                        <div className="flex gap-1.5">
                          <button onClick={() => setCombineMode('union')}
                            className={`flex-1 px-2 py-1.5 rounded-lg text-[11px] font-medium transition-all border ${
                              combineMode === 'union'
                                ? 'bg-indigo-500/20 border-indigo-400 text-indigo-300'
                                : 'bg-white/5 border-white/10 text-muted hover:bg-white/10'
                            }`}>
                            Combinar filas (UNION ALL)
                          </button>
                          <button onClick={() => setCombineMode('join')}
                            className={`flex-1 px-2 py-1.5 rounded-lg text-[11px] font-medium transition-all border ${
                              combineMode === 'join'
                                ? 'bg-indigo-500/20 border-indigo-400 text-indigo-300'
                                : 'bg-white/5 border-white/10 text-muted hover:bg-white/10'
                            }`}>
                            Relacionar tablas (JOIN)
                          </button>
                        </div>
                      )}

                      {combineMode === 'join' && selectedTables.length >= 2 && (
                        <div className="border border-indigo-500/20 bg-indigo-500/5 rounded-xl p-2 space-y-1.5">
                          <div className="text-[10px] font-semibold text-indigo-300">Relaciones entre tablas</div>
                          {pairRows.map(p => {
                            const rel = joinRelations[p.key]
                            return (
                              <div key={p.key} className="flex items-center gap-1 text-[10px]">
                                <span className="truncate max-w-[64px] text-muted shrink-0">{p.a}</span>
                                <select value={rel?.colA || ''} onChange={e => setRelation(p.a, p.b, e.target.value, rel?.colB || '')}
                                  className="glass-input !py-0.5 !text-[10px] flex-1 min-w-0">
                                  <option value="">— columna —</option>
                                  {columnsForTable(p.a).map(c => <option key={c.name} value={c.name}>{c.name}</option>)}
                                </select>
                                <span className="text-muted shrink-0">=</span>
                                <select value={rel?.colB || ''} onChange={e => setRelation(p.a, p.b, rel?.colA || '', e.target.value)}
                                  className="glass-input !py-0.5 !text-[10px] flex-1 min-w-0">
                                  <option value="">— columna —</option>
                                  {columnsForTable(p.b).map(c => <option key={c.name} value={c.name}>{c.name}</option>)}
                                </select>
                                <span className="truncate max-w-[64px] text-muted shrink-0">{p.b}</span>
                              </div>
                            )
                          })}
                          <p className="text-[9px] text-muted">Indica qué columnas relacionan cada par de tablas. La primera tabla seleccionada es la base.</p>
                        </div>
                      )}

                      {columnsLoading ? (
                        <div className="flex items-center gap-2 text-xs text-muted py-2">
                          <Loader2 className="w-3 h-3 animate-spin" /> Cargando columnas...
                        </div>
                      ) : tableColumns.length > 0 ? (
                        <div>
                          <div className="flex items-center justify-between mb-1">
                            <label className="text-xs text-muted">{selectedTables.length === 1 ? `${selectedTables[0]} · ${allColumnNames.length} col(s)` : `${selectedTables.length} tablas · ${allColumnNames.length} col(s)`}</label>
                            <div className="flex gap-2 text-[10px]">
                              <button onClick={selectAllCols} className="text-indigo-400 hover:text-indigo-300">Todas</button>
                              <button onClick={deselectAllCols} className="text-muted hover:text-white">Ninguna</button>
                            </div>
                          </div>
                          <div className="max-h-48 overflow-y-auto border border-white/10 rounded-xl p-1.5 space-y-1.5">
                            {tableColumns.map(group => (
                              <div key={group.table}>
                                <div className="text-[10px] font-semibold text-muted px-1 py-0.5 sticky top-0 bg-[#1a1a2e] z-10">
                                  {group.table} · {group.columns.length} col(s)
                                </div>
                                {group.columns.map(c => {
                                  const sampleVal = columnSamples[c.name]
                                  return (
                                    <label key={c.name}
                                      className={`flex items-center gap-1.5 px-1.5 py-1 rounded text-[11px] cursor-pointer transition-all ${
                                        selectedColumns.includes(c.name) ? 'bg-indigo-500/15 text-indigo-300' : 'text-muted hover:bg-white/5'
                                      }`}>
                                      <input type="checkbox" checked={selectedColumns.includes(c.name)}
                                        onChange={() => toggleColumn(c.name)} className="w-3 h-3 rounded accent-indigo-500 shrink-0" />
                                      <span className="truncate font-medium">{c.name}</span>
                                      <span className="text-[9px] opacity-40 shrink-0">{c.type}</span>
                                      {sampleVal !== undefined && (
                                        <span className="ml-auto text-[10px] opacity-50 truncate max-w-[140px] font-mono" title={String(sampleVal)}>
                                          {sampleVal === null ? <span className="text-red-400">NULL</span> : String(sampleVal).slice(0, 40)}
                                        </span>
                                      )}
                                    </label>
                                  )
                                })}
                              </div>
                            ))}
                          </div>
                        </div>
                      ) : selectedTables.length > 0 ? <p className="text-xs text-muted">Sin columnas</p> : null}

                      <div className="flex items-center gap-2 pt-1">
                        <button onClick={loadSuggest} disabled={suggestLoading}
                          className="flex items-center gap-1.5 text-xs text-amber-400 hover:text-amber-300 transition-colors">
                          {suggestLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Lightbulb className="w-3 h-3" />}
                          Sugerencias
                        </button>
                        {showSuggest && suggestions.length > 0 && (
                          <div className="flex-1 max-h-28 overflow-y-auto border border-amber-500/20 bg-amber-500/5 rounded-lg p-1 space-y-0.5">
                            {suggestions.map(s => (
                              <button key={s.table} onClick={() => applySuggestion(s)}
                                className="w-full flex items-center justify-between px-2 py-1 rounded text-[11px] hover:bg-amber-500/10 transition-all text-left">
                                <span className="font-medium text-amber-200 truncate">{s.table}</span>
                                <span className="text-[10px] text-muted shrink-0 ml-2">{s.row_count != null ? s.row_count.toLocaleString() : `${s.columns} cols`}</span>
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  ) : (
                    <div>
                      <textarea value={query} onChange={e => setQuery(e.target.value)}
                        className="glass-input font-mono text-sm w-full min-h-[120px] resize-y"
                        placeholder="SELECT * FROM tabla WHERE condicion" />
                    </div>
                  )}
                </div>
              </div>

              {/* Preview panel */}
              <div className="border border-white/10 rounded-xl overflow-hidden flex flex-col flex-1 min-h-[180px]">
                <div className="flex items-center justify-between px-3 py-2 bg-white/5 border-b border-white/10">
                  <div className="flex items-center gap-2">
                    <Database className="w-4 h-4 text-indigo-400" />
                    <span className="text-sm font-medium">Vista previa</span>
                  </div>
                  <div className="flex items-center gap-2 text-xs">
                    {formPreviewLoading && <Loader2 className="w-3 h-3 animate-spin text-muted" />}
                    {formPreview && <span className="text-muted font-mono">{formPreview.total_rows.toLocaleString()} registro(s)</span>}
                  </div>
                </div>
                <div className="flex-1 overflow-auto">
                  {formPreviewError ? (
                    <div className="h-32 flex items-center justify-center text-xs text-red-300 px-4 text-center gap-2">
                      <AlertTriangle className="w-4 h-4 shrink-0" />
                      <span>{formPreviewError}</span>
                    </div>
                  ) : formPreview ? (
                    <table className="w-full text-xs border-collapse">
                      <thead className="sticky top-0 bg-[#1a1a2e] z-10">
                        <tr className="border-b border-white/10">
                          {formPreview.columns.map((col, i) => (
                            <th key={i} className="text-left py-1.5 px-2 font-semibold text-indigo-300 whitespace-nowrap">{col}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {formPreview.rows.map((row, ri) => (
                          <tr key={ri} className="border-b border-white/5 hover:bg-white/5">
                            {row.map((val: any, ci) => (
                              <td key={ci} className="py-1 px-2 truncate max-w-[160px]">{val === null ? <span className="text-red-400">NULL</span> : String(val)}</td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  ) : formPreviewLoading ? (
                    <div className="h-32 flex items-center justify-center text-xs text-muted">
                      <Loader2 className="w-4 h-4 animate-spin mr-2" /> Cargando datos...
                    </div>
                  ) : (
                    <div className="h-32 flex items-center justify-center text-xs text-muted px-4 text-center">
                      {tableActiveTab === 'visual'
                        ? (combineMode === 'join' && selectedTables.length > 1
                          ? 'Define las relaciones entre las tablas para ver la vista previa'
                          : 'Selecciona una tabla para ver la vista previa')
                        : 'Escribe una consulta SQL para ver la vista previa'}
                    </div>
                  )}
                </div>
              </div>
            </div>
          ) : dsId && isFile ? (
            <div className="lg:col-span-3 border border-white/10 rounded-xl p-6 flex flex-col items-center justify-center text-center">
              <Database className="w-8 h-8 text-muted mb-2" />
              <p className="text-sm text-muted">Archivo seleccionado</p>
              <p className="text-xs text-muted mt-1">Los datos se cargarán al ejecutar el análisis</p>
            </div>
          ) : (
            <div className="lg:col-span-3 border border-dashed border-white/10 rounded-xl p-6 flex flex-col items-center justify-center text-center">
              <Database className="w-8 h-8 text-muted mb-2" />
              <p className="text-sm text-muted">Selecciona una conexión</p>
              <p className="text-xs text-muted mt-1">Aparecerá el explorador de tablas aquí</p>
            </div>
          )}
        </div>
      </GlassContainer>

      {saveProgress && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-[#1a1a2e] border border-white/10 rounded-2xl p-6 w-full max-w-md shadow-2xl">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-8 h-8 rounded-full bg-indigo-500/20 border border-indigo-400 flex items-center justify-center">
                <Loader2 className="w-4 h-4 animate-spin text-indigo-300" />
              </div>
              <div>
                <h3 className="text-sm font-semibold">Guardando fuente de datos</h3>
                <p className="text-[11px] text-muted">Paso {saveProgress.step} de {saveProgress.total}</p>
              </div>
            </div>
            <div className="w-full h-2 bg-white/10 rounded-full overflow-hidden mb-3">
              <div
                className="h-full bg-gradient-to-r from-indigo-500 to-indigo-400 rounded-full transition-all duration-500 ease-out"
                style={{ width: `${Math.round((saveProgress.step / saveProgress.total) * 100)}%` }}
              />
            </div>
            <p className="text-xs text-muted flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-pulse" />
              {saveProgress.message}
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
