import { useState, useEffect, useRef } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft, Play, PauseCircle, StopCircle, Trash2, Clock, Edit3, Save, X,
  AlertCircle, CheckCircle, Loader2, BarChart3, Plus, Activity, List,
  ChevronDown, ChevronRight,
} from 'lucide-react'
import api from '../api/client'
import GlassContainer from '../components/layout/GlassContainer'
import { formatDate } from '../lib/utils'
import { useAuthStore } from '../hooks/useAuth'

const GROUP_LABELS: Record<string, string> = {
  basico: 'Básico', formato: 'Formato y validación', fechas: 'Fechas',
  negocio: 'Reglas de negocio', avanzadas: 'Avanzadas', integridad: 'Integridad',
  personas_similares: 'Personas similares',
}

export default function ProcessDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const currentUser = useAuthStore((s) => s.user)
  const isAdmin = currentUser?.role === 'admin'
  const [editing, setEditing] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [showScheduleForm, setShowScheduleForm] = useState(false)

  const [editName, setEditName] = useState('')
  const [editSourceType, setEditSourceType] = useState('')
  const [editConnStr, setEditConnStr] = useState('')
  const [editQuery, setEditQuery] = useState('')
  const [editFilePath, setEditFilePath] = useState('')
  const [editRules, setEditRules] = useState<string[]>([])
  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>({})

  const esRef = useRef<EventSource | null>(null)
  const logsEndRef = useRef<HTMLDivElement | null>(null)

  const [elapsed, setElapsed] = useState(0)
  const [liveLogs, setLiveLogs] = useState<string[]>([])
  const [logOpen, setLogOpen] = useState(true)
  const [schedName, setSchedName] = useState('')
  const [schedFreq, setSchedFreq] = useState('daily')
  const [schedHour, setSchedHour] = useState('8')
  const [schedMin, setSchedMin] = useState('0')
  const [schedDay, setSchedDay] = useState('1')
  const [schedWeekday, setSchedWeekday] = useState('1')
  const [schedEmails, setSchedEmails] = useState('')

  const { data: process, isLoading } = useQuery({
    queryKey: ['process', id],
    queryFn: () => api.get(`/processes/${id}`).then((r) => r.data),
    enabled: !!id,
    refetchInterval: (query) => {
      const data = query.state.data
      if (data?.status === 'running' || data?.status === 'pending') return 2000
      return false
    },
  })

  const { data: rulesData } = useQuery({
    queryKey: ['rules-groups'],
    queryFn: () => api.get('/rules/groups').then((r) => r.data),
    enabled: editing,
  })

  const groups = (rulesData?.groups ?? []).filter((g: any) => g.name !== 'todo')

  const fmtTime = (s: number) => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`

  // SSE subscription for real-time progress updates
  useEffect(() => {
    if (!id) return

    const token = localStorage.getItem('qdata_token')
    const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
    const es = new EventSource(`${baseUrl}/analyze/${id}/stream?token=${token}`)
    esRef.current = es

    es.addEventListener('progress', (e) => {
      try {
        const data = JSON.parse(e.data)
        queryClient.setQueryData(['process', id], (old: any) => {
          if (!old) return old
          return {
            ...old,
            status: data.status || old.status,
            progress: {
              ...(old.progress || {}),
              total: data.total ?? old.progress?.total ?? 0,
              completed: data.completed ?? old.progress?.completed ?? 0,
              current: data.current ?? old.progress?.current ?? 0,
              current_rule: data.current_rule ?? old.progress?.current_rule ?? '',
              score: data.score ?? old.progress?.score ?? null,
              label: data.label ?? old.progress?.label ?? null,
              report_id: data.report_id ?? old.progress?.report_id ?? null,
              rules: data.rules || old.progress?.rules || [],
              rule_processed: data.rule_processed ?? old.progress?.rule_processed ?? 0,
              rule_total: data.rule_total ?? old.progress?.rule_total ?? 0,
              rule_message: data.rule_message ?? old.progress?.rule_message ?? '',
              rule_phase: data.rule_phase ?? old.progress?.rule_phase ?? '',
              rule_extra: data.rule_extra ?? old.progress?.rule_extra ?? null,
              load_message: data.load_message ?? old.progress?.load_message ?? '',
              records_loaded: data.records_loaded ?? old.progress?.records_loaded ?? 0,
            },
          }
        })
        if (data.logs?.length) {
          setLiveLogs(data.logs)
        }
        if (data.status === 'completed' || data.status === 'failed' || data.status === 'cancelled') {
          queryClient.invalidateQueries({ queryKey: ['process', id] })
        }
      } catch { /* ignore parse errors */ }
    })

    es.addEventListener('error', () => {
      es.close()
      esRef.current = null
    })

    return () => {
      es.close()
      esRef.current = null
    }
  }, [id])

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [liveLogs])

  const rerunMutation = useMutation({
    mutationFn: () => api.post(`/processes/${id}/rerun`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['process', id] })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => api.delete(`/processes/${id}`),
    onSuccess: () => navigate('/processes'),
  })

  const updateMutation = useMutation({
    mutationFn: (data: any) => api.put(`/processes/${id}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['process', id] })
      setEditing(false)
    },
  })

  const scheduleMutation = useMutation({
    mutationFn: (data: any) => api.post('/scheduler/tasks', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['process', id] })
      setShowScheduleForm(false)
    },
  })

  const pauseMutation = useMutation({
    mutationFn: () => api.post(`/processes/${id}/pause`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['process', id] })
    },
  })

  const resumeMutation = useMutation({
    mutationFn: () => api.post(`/processes/${id}/resume`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['process', id] })
    },
  })

  const stopMutation = useMutation({
    mutationFn: () => api.post(`/processes/${id}/stop`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['process', id] })
    },
  })

  const buildCron = () => {
    const h = schedHour.padStart(2, '0')
    const m = schedMin.padStart(2, '0')
    switch (schedFreq) {
      case 'once': return `${m} ${h} ${new Date().getDate()} ${new Date().getMonth() + 1} *`
      case 'daily': return `${m} ${h} * * *`
      case 'weekly': return `${m} ${h} * * ${schedWeekday}`
      case 'monthly': return `${m} ${h} ${schedDay} * *`
      case 'yearly': return `${m} ${h} ${schedDay} ${new Date().getMonth() + 1} *`
      default: return `${m} ${h} * * *`
    }
  }

  const handleEdit = () => {
    const sc = process.source_config || {}
    setEditName(process.name)
    setEditSourceType(sc.source_type || '')
    setEditConnStr(sc.connection_string || '')
    setEditQuery(sc.query || '')
    setEditFilePath(sc.file_path || '')
    setEditRules(process.rules_config || [])
    setEditing(true)
  }

  const handleSave = () => {
    updateMutation.mutate({
      name: editName,
      source_config: { source_type: editSourceType, connection_string: editConnStr, query: editQuery, file_path: editFilePath },
      rules_config: editRules,
    })
  }

  const toggleGroup = (groupName: string, rules: any[]) => {
    const ruleNames = rules.map((r: any) => r.name)
    const allSelected = ruleNames.every((r: string) => editRules.includes(r))
    if (allSelected) {
      setEditRules(editRules.filter((r: string) => !ruleNames.includes(r)))
    } else {
      const newRules = [...editRules]
      ruleNames.forEach((r) => { if (!newRules.includes(r)) newRules.push(r) })
      setEditRules(newRules)
    }
  }

  const toggleRule = (ruleName: string) => {
    setEditRules((prev) => prev.includes(ruleName) ? prev.filter((r) => r !== ruleName) : [...prev, ruleName])
  }

  const toggleExpand = (groupName: string) => {
    setExpandedGroups((prev) => ({ ...prev, [groupName]: !prev[groupName] }))
  }

  const isRunning = process?.status === 'running' || process?.status === 'pending' || process?.status === 'paused' || process?.status === 'loading'

  // Elapsed timer — MUST be before early returns (Rules of Hooks)
  useEffect(() => {
    if (isRunning) {
      const start = Date.now()
      const timer = setInterval(() => setElapsed(Math.floor((Date.now() - start) / 1000)), 1000)
      return () => { clearInterval(timer); setElapsed(0) }
    }
  }, [isRunning])

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="skeleton h-48 rounded-xl" />
        <div className="skeleton h-64 rounded-xl" />
      </div>
    )
  }

  if (!process) {
    return (
      <GlassContainer className="text-center py-12">
        <p className="text-muted">Proceso no encontrado</p>
        <Link to="/processes" className="text-indigo-400 mt-4 inline-block">Volver</Link>
      </GlassContainer>
    )
  }

  const sc = process.source_config || {}
  const reports = process.reports || []
  const tasks = process.scheduled_tasks || []
  const progress = process.progress || {}
  const isPaused = process.status === 'paused'
  const isCancelled = process.status === 'cancelled'
  const rulePct = progress.total > 0 ? Math.round((progress.completed / progress.total) * 100) : 0
  const recordPct = progress.total_records > 0 ? Math.round(((progress.records_processed || 0) / progress.total_records) * 100) : 0
  const pct = Math.round(rulePct * 0.5 + recordPct * 0.5)

  const freqLabels: Record<string, string> = {
    once: 'Una vez', daily: 'Cada día', weekly: 'Cada semana', monthly: 'Cada mes', yearly: 'Cada año',
  }
  const weekdayLabels: Record<string, string> = {
    '0': 'Dom', '1': 'Lun', '2': 'Mar', '3': 'Mié', '4': 'Jue', '5': 'Vie', '6': 'Sáb',
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <Link to="/processes" className="inline-flex items-center gap-2 text-muted hover:text-white transition-colors">
          <ArrowLeft className="w-4 h-4" />
          Volver a procesos
        </Link>
        <div className="flex items-center gap-2">
          {editing ? (
            <>
              <button onClick={handleSave} disabled={updateMutation.isPending}
                className="btn-primary flex items-center gap-2 text-sm">
                <Save className="w-4 h-4" />
                {updateMutation.isPending ? 'Guardando...' : 'Guardar'}
              </button>
              <button onClick={() => setEditing(false)} className="btn-ghost flex items-center gap-2 text-sm">
                <X className="w-4 h-4" />
                Cancelar
              </button>
            </>
          ) : !isRunning ? (
            <>
              <button onClick={handleEdit} className="btn-ghost flex items-center gap-2 text-sm">
                <Edit3 className="w-4 h-4" />
                Editar
              </button>
              <button onClick={() => rerunMutation.mutate()} disabled={rerunMutation.isPending}
                className="btn-ghost flex items-center gap-2 text-sm">
                <Play className="w-4 h-4" />
                {rerunMutation.isPending ? 'Ejecutando...' : 'Ejecutar ahora'}
              </button>
              {isAdmin && (
                <button onClick={() => setConfirmDelete(true)}
                  className="btn-ghost flex items-center gap-2 text-sm text-red-400">
                  <Trash2 className="w-4 h-4" />
                  Eliminar
                </button>
              )}
            </>
          ) : isPaused ? (
            <>
              <button onClick={() => resumeMutation.mutate()} disabled={resumeMutation.isPending}
                className="btn-ghost flex items-center gap-2 text-sm text-green-400">
                <Play className="w-4 h-4" />
                {resumeMutation.isPending ? 'Reanudando...' : 'Reanudar'}
              </button>
              <button onClick={() => stopMutation.mutate()} disabled={stopMutation.isPending}
                className="btn-ghost flex items-center gap-2 text-sm text-red-400">
                <StopCircle className="w-4 h-4" />
                {stopMutation.isPending ? 'Deteniendo...' : 'Detener'}
              </button>
            </>
          ) : isRunning ? (
            <>
              <button onClick={() => pauseMutation.mutate()} disabled={pauseMutation.isPending}
                className="btn-ghost flex items-center gap-2 text-sm text-yellow-400">
                <PauseCircle className="w-4 h-4" />
                {pauseMutation.isPending ? 'Pausando...' : 'Pausar'}
              </button>
              <button onClick={() => stopMutation.mutate()} disabled={stopMutation.isPending}
                className="btn-ghost flex items-center gap-2 text-sm text-red-400">
                <StopCircle className="w-4 h-4" />
                {stopMutation.isPending ? 'Deteniendo...' : 'Detener'}
              </button>
            </>
          ) : null}
        </div>
      </div>

      {confirmDelete && (
        <div className="mb-6 p-4 bg-red-500/10 border border-red-500/20 rounded-xl flex items-center gap-3 flex-wrap">
          <AlertCircle className="w-6 h-6 text-red-400 shrink-0" />
          <span className="text-sm text-red-300">¿Eliminar este proceso con todos sus reportes y tareas?</span>
          <button onClick={() => deleteMutation.mutate()} disabled={deleteMutation.isPending}
            className="btn-primary !bg-red-500 !bg-none text-xs py-1 px-3">
            {deleteMutation.isPending ? 'Eliminando...' : 'Confirmar'}
          </button>
          <button onClick={() => setConfirmDelete(false)} className="btn-ghost text-xs py-1 px-3">Cancelar</button>
        </div>
      )}

      {isCancelled && (
        <div className="mb-6 p-4 bg-yellow-500/10 border border-yellow-500/20 rounded-xl flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-yellow-400 shrink-0" />
          <span className="text-sm text-yellow-300">Análisis cancelado</span>
        </div>
      )}

      {isRunning ? (
        <div className="mb-6 space-y-4">
          {/* Loading phase */}
          {process?.status === 'loading' && (
            <div className="rounded-xl bg-white/5 p-4 border border-white/10 space-y-3">
              <div className="flex items-center gap-3">
                <span className="text-xs font-semibold px-2 py-1 rounded-full bg-blue-500/20 text-blue-300 border border-blue-500/30 flex items-center gap-1.5">
                  <Loader2 className="w-3 h-3 animate-spin" />
                  Cargando datos
                </span>
                <span className="text-xs text-muted flex items-center gap-1.5">
                  <Clock className="w-3 h-3" />
                  {fmtTime(elapsed)}
                </span>
              </div>
              <p className="text-xs text-muted">{progress.load_message || 'Leyendo fuente de datos...'}</p>
              {progress.total_records > 0 && (
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[10px] text-muted">Registros leídos</span>
                    <span className="text-xs font-semibold text-blue-400">
                      {(progress.records_loaded || 0).toLocaleString()} / {progress.total_records.toLocaleString()}
                    </span>
                  </div>
                  <div className="h-2 bg-white/10 rounded-full overflow-hidden">
                    <div className="h-full bg-blue-500 rounded-full transition-all duration-300"
                      style={{ width: `${Math.min((progress.records_loaded || 0) / progress.total_records * 100, 100)}%` }} />
                  </div>
                </div>
              )}
              {progress.total_records === 0 && progress.records_loaded > 0 && (
                <p className="text-xs text-blue-300">{progress.records_loaded.toLocaleString()} registros leídos...</p>
              )}
            </div>
          )}
          {/* Top bar: En vivo badge + elapsed clock */}
          <div className="flex items-center gap-3">
            <span className="text-xs font-semibold px-2 py-1 rounded-full bg-green-500/20 text-green-300 border border-green-500/30 flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
              En vivo
            </span>
            <span className="text-xs text-muted flex items-center gap-1.5">
              <Clock className="w-3 h-3" />
              {fmtTime(elapsed)}
            </span>
            {isPaused && (
              <span className="text-xs font-semibold px-2 py-1 rounded-full bg-yellow-500/20 text-yellow-300 border border-yellow-500/30">
                Pausado
              </span>
            )}
            {progress.current_rule && <span className="text-xs text-muted truncate">· {progress.current_rule}</span>}
          </div>

          {/* Stat panels */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <div className="rounded-xl bg-white/5 p-4 border border-white/10">
              <p className="text-[10px] text-muted uppercase tracking-wider">Reglas</p>
              <p className="text-xl font-bold mt-1">{progress.completed || 0} <span className="text-xs text-muted font-normal">/ {progress.total || 0}</span></p>
            </div>
            <div className="rounded-xl bg-white/5 p-4 border border-white/10">
              <p className="text-[10px] text-muted uppercase tracking-wider">Registros</p>
              <p className="text-xl font-bold mt-1">{(progress.records_processed || 0).toLocaleString()} <span className="text-xs text-muted font-normal">/ {(progress.total_records || 0).toLocaleString()}</span></p>
            </div>
            <div className="rounded-xl bg-white/5 p-4 border border-white/10">
              <p className="text-[10px] text-muted uppercase tracking-wider">Throughput</p>
              <p className="text-xl font-bold mt-1 flex items-center gap-1">
                <Activity className="w-4 h-4 text-green-400" />
                {elapsed > 0 ? Math.round((progress.records_processed || 0) / elapsed) : 0}
              </p>
              <p className="text-[10px] text-muted mt-1">reg/s</p>
            </div>
            <div className="rounded-xl bg-white/5 p-4 border border-white/10">
              <p className="text-[10px] text-muted uppercase tracking-wider">Estado</p>
              <p className="text-xl font-bold mt-1 flex items-center gap-1.5">
                <span className={`w-2 h-2 rounded-full ${isPaused ? 'bg-yellow-400' : progress.total === 0 ? 'bg-amber-400' : 'bg-green-400'} animate-pulse`} />
                {isPaused ? 'Pausado' : progress.total === 0 ? 'Iniciando' : 'Ejecutando'}
              </p>
            </div>
          </div>

          {/* 3 Progress Bars */}
          <div className="rounded-xl bg-white/5 p-4 border border-white/10 space-y-3">
            {/* Bar 1: Rules completed */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2 text-xs">
                  <span className="w-2 h-2 rounded-full bg-indigo-500" />
                  <span className="text-muted">Reglas</span>
                  <span className="text-white/80 font-medium">{progress.completed || 0} / {progress.total || 0}</span>
                </div>
                <span className="text-xs font-semibold text-indigo-400">{rulePct}%</span>
              </div>
              <div className="h-2.5 bg-white/10 rounded-full overflow-hidden">
                <div className="h-full bg-indigo-500 rounded-full transition-all duration-500"
                  style={{ width: `${Math.max(rulePct, progress.completed > 0 ? 3 : 0)}%` }} />
              </div>
            </div>

            {/* Bar 2: Current rule progress */}
            {progress.current_rule && progress.rule_total > 0 && (
              <div>
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-2 text-xs min-w-0">
                    <Loader2 className="w-3 h-3 animate-spin text-cyan-400 shrink-0" />
                    <span className="text-muted truncate">{progress.current_rule}</span>
                    {progress.rule_phase && (
                      <span className="shrink-0 text-[9px] font-semibold px-1.5 py-0.5 rounded-full bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
                        {progress.rule_phase === 'blocking' ? 'Bloqueo' :
                         progress.rule_phase === 'scoring' ? 'Scoring' :
                         progress.rule_phase === 'clustering' ? 'Agrupando' : progress.rule_phase}
                      </span>
                    )}
                  </div>
                  <span className="text-xs font-semibold text-cyan-400 shrink-0">
                    {Math.round((progress.rule_processed / progress.rule_total) * 100)}%
                  </span>
                </div>
                <div className="h-2.5 bg-white/10 rounded-full overflow-hidden">
                  <div className="h-full bg-cyan-500 rounded-full transition-all duration-300"
                    style={{ width: `${Math.max(Math.min((progress.rule_processed / progress.rule_total) * 100, 100), 2)}%` }} />
                </div>
                <div className="flex items-center gap-3 mt-1">
                  <span className="text-[10px] text-muted">{progress.rule_processed.toLocaleString()} / {progress.rule_total.toLocaleString()}</span>
                  {progress.rule_extra?.eta_sec > 0 && (
                    <span className="text-[10px] text-muted">ETA {Math.floor(progress.rule_extra.eta_sec / 60)}:{(progress.rule_extra.eta_sec % 60).toString().padStart(2, '0')}</span>
                  )}
                  {progress.rule_extra?.total_matches > 0 && (
                    <span className="text-[10px] text-green-400">{progress.rule_extra.total_matches.toLocaleString()} coincidencias</span>
                  )}
                </div>
              </div>
            )}

            {/* Bar 3: Records analyzed */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2 text-xs">
                  <span className="w-2 h-2 rounded-full bg-emerald-500" />
                  <span className="text-muted">Registros</span>
                  <span className="text-white/80 font-medium">{(progress.records_processed || 0).toLocaleString()} / {(progress.total_records || 0).toLocaleString()}</span>
                </div>
                <span className="text-xs font-semibold text-emerald-400">{recordPct}%</span>
              </div>
              <div className="h-2.5 bg-white/10 rounded-full overflow-hidden">
                <div className="h-full bg-emerald-500 rounded-full transition-all duration-500"
                  style={{ width: `${Math.max(recordPct, (progress.records_processed || 0) > 0 ? 3 : 0)}%` }} />
              </div>
            </div>

            {/* Overall blended percentage */}
            <div className="flex items-center justify-between pt-2 border-t border-white/5">
              <span className="text-[10px] text-muted uppercase tracking-wider">Progreso general</span>
              <span className="text-sm font-bold text-white/90">{pct}%</span>
            </div>
          </div>

          {/* Current rule details: field averages + score distribution */}
          {progress.current_rule && progress.rule_phase === 'scoring' && progress.rule_extra && (
            <div className="rounded-xl bg-white/5 p-4 border border-white/10 space-y-3">
              {progress.rule_extra.field_avgs && Object.keys(progress.rule_extra.field_avgs).length > 0 && (
                <div>
                  <p className="text-[10px] text-muted uppercase tracking-wider mb-1.5">Promedio por campo</p>
                  <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-1.5">
                    {Object.entries(progress.rule_extra.field_avgs as Record<string, number>).map(([field, avg]) => {
                      const p = Math.round(avg * 100)
                      return (
                        <div key={field} className="flex flex-col items-center rounded-lg bg-white/5 p-1.5">
                          <span className="text-[10px] text-muted uppercase truncate w-full text-center">{field}</span>
                          <span className={`text-xs font-bold ${p >= 80 ? 'text-green-400' : p >= 50 ? 'text-yellow-400' : 'text-red-400'}`}>{p}%</span>
                          <div className="w-full h-1 bg-white/10 rounded-full overflow-hidden mt-0.5">
                            <div className={`h-full rounded-full ${p >= 80 ? 'bg-green-400' : p >= 50 ? 'bg-yellow-400' : 'bg-red-400'}`} style={{ width: `${p}%` }} />
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}
              {progress.rule_extra.score_distribution && (() => {
                const sd = progress.rule_extra.score_distribution as Record<string, number>
                const total = (sd.bajo || 0) + (sd.medio || 0) + (sd.alto || 0)
                if (total === 0) return null
                const bajoPct = ((sd.bajo || 0) / total) * 100
                const medioPct = ((sd.medio || 0) / total) * 100
                const altoPct = ((sd.alto || 0) / total) * 100
                return (
                  <div>
                    <p className="text-[10px] text-muted uppercase tracking-wider mb-1.5">Distribución de scores</p>
                    <div className="h-2 bg-white/10 rounded-full overflow-hidden flex">
                      <div className="h-full bg-red-500/70 transition-all" style={{ width: `${bajoPct}%` }} title={`Bajo: ${sd.bajo?.toLocaleString()}`} />
                      <div className="h-full bg-yellow-500/70 transition-all" style={{ width: `${medioPct}%` }} title={`Medio: ${sd.medio?.toLocaleString()}`} />
                      <div className="h-full bg-green-500/70 transition-all" style={{ width: `${altoPct}%` }} title={`Alto: ${sd.alto?.toLocaleString()}`} />
                    </div>
                    <div className="flex justify-between text-[9px] text-muted mt-0.5">
                      <span>Bajo {sd.bajo?.toLocaleString()}</span>
                      <span>Medio {sd.medio?.toLocaleString()}</span>
                      <span>Alto {sd.alto?.toLocaleString()}</span>
                    </div>
                  </div>
                )
              })()}
            </div>
          )}

          {/* Fallback for non-scoring rules without intra-rule progress */}
          {progress.current_rule && progress.total > 0 && !progress.rule_total && (
            <div className="rounded-xl bg-white/5 p-4 border border-white/10">
              <div className="flex items-center gap-2 text-sm">
                <Loader2 className="w-4 h-4 animate-spin text-indigo-400 shrink-0" />
                <span className="text-indigo-300 font-medium">{progress.current_rule}</span>
                <span className="text-xs text-muted ml-auto">{progress.rule_message}</span>
              </div>
            </div>
          )}

          {/* Rules table */}
          {progress.rules?.length > 0 && (
            <div className="rounded-xl bg-white/5 border border-white/10 overflow-hidden">
              <div className="flex items-center gap-2 p-3 border-b border-white/10">
                <List className="w-3.5 h-3.5 text-muted" />
                <span className="text-xs font-medium text-muted">Reglas ({progress.rules.length})</span>
              </div>
              <div className="max-h-48 overflow-y-auto divide-y divide-white/5">
                {progress.rules.map((r: any, i: number) => (
                  <div key={i} className="flex items-center gap-2 p-2.5 text-xs">
                    {r.status === 'pending' && <div className="w-3 h-3 rounded-full border border-white/20 shrink-0" />}
                    {r.status === 'running' && <Loader2 className="w-3 h-3 animate-spin text-indigo-400 shrink-0" />}
                    {r.status === 'done' && <CheckCircle className="w-3 h-3 text-green-400 shrink-0" />}
                    {r.status === 'failed' && <AlertCircle className="w-3 h-3 text-red-400 shrink-0" />}
                    {r.status === 'skipped' && <X className="w-3 h-3 text-yellow-400 shrink-0" />}
                    <span className={`truncate flex-1 ${r.status === 'running' ? 'text-indigo-300 font-medium' : r.status === 'done' ? 'text-green-300' : r.status === 'failed' ? 'text-red-300' : r.status === 'skipped' ? 'text-yellow-300' : 'text-muted'}`}>
                      {r.label}
                    </span>
                    <span className="text-[10px] text-muted shrink-0">{(r.rule_records_processed || 0).toLocaleString()}</span>
                    {r.status === 'done' && r.failed !== undefined && (
                      <span className={`shrink-0 text-[10px] ${r.failed === 0 ? 'text-green-400' : 'text-yellow-400'}`}>
                        {r.failed === 0 ? '✓' : `${r.failed}`}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Live logs */}
          {liveLogs.length > 0 && (
            <div className="rounded-xl bg-white/5 border border-white/10 overflow-hidden">
              <button onClick={() => setLogOpen(!logOpen)} className="flex items-center gap-2 p-3 w-full text-left border-b border-white/10">
                {logOpen ? <ChevronDown className="w-3.5 h-3.5 text-muted" /> : <ChevronRight className="w-3.5 h-3.5 text-muted" />}
                <span className="text-xs font-medium text-muted">Log en vivo ({liveLogs.length})</span>
              </button>
              {logOpen && (
                <div className="max-h-64 overflow-y-auto p-3 space-y-1 font-mono text-[11px] leading-relaxed">
                  {liveLogs.map((msg, i) => (
                    <div key={i} className="text-white/70 hover:text-white/90 transition-colors">
                      <span className="text-indigo-400 mr-2">&gt;</span>{msg}
                    </div>
                  ))}
                  <div ref={logsEndRef} />
                </div>
              )}
            </div>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
          <GlassContainer className="lg:col-span-2">
            {editing ? (
              <div className="space-y-4">
                <h2 className="text-xl font-bold">Editar Proceso</h2>
                <div>
                  <label className="block text-sm text-muted mb-1">Nombre</label>
                  <input type="text" value={editName} onChange={(e) => setEditName(e.target.value)} className="glass-input" />
                </div>
                <div>
                  <label className="block text-sm text-muted mb-1">Tipo de fuente</label>
                  <select value={editSourceType} onChange={(e) => setEditSourceType(e.target.value)} className="glass-input">
                    <option value="postgresql">PostgreSQL</option>
                    <option value="mysql">MySQL</option>
                    <option value="sqlserver">SQL Server</option>
                    <option value="oracle">Oracle</option>
                    <option value="informix">Informix</option>
                    <option value="sqlite">SQLite</option>
                    <option value="csv">CSV</option>
                    <option value="excel">Excel</option>
                    <option value="json">JSON</option>
                    <option value="parquet">Parquet</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm text-muted mb-1">Connection String</label>
                  <input type="text" value={editConnStr} onChange={(e) => setEditConnStr(e.target.value)} className="glass-input font-mono text-sm" placeholder="postgresql://user:pass@host:5432/db" />
                </div>
                <div>
                  <label className="block text-sm text-muted mb-1">Archivo (path en servidor)</label>
                  <input type="text" value={editFilePath} onChange={(e) => setEditFilePath(e.target.value)} className="glass-input font-mono text-sm" placeholder="/tmp/qdata_uploads/archivo.xlsx" />
                </div>
                <div>
                  <label className="block text-sm text-muted mb-1">Consulta SQL</label>
                  <textarea value={editQuery} onChange={(e) => setEditQuery(e.target.value)} className="glass-input font-mono text-sm min-h-[80px]" />
                </div>

                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="block text-sm text-muted">Reglas de validación</label>
                    <span className="text-xs text-muted">{editRules.length}/{groups.reduce((s: number, g: any) => s + g.rules.length, 0)}</span>
                  </div>
                  <div className="flex gap-2 mb-3">
                    <button onClick={() => setEditRules([...new Set<string>(groups.flatMap((g: any) => g.rules.map((r: any) => r.name as string)))])}
                      className="text-xs px-3 py-1 rounded-full bg-white/10 hover:bg-white/20 transition-colors">Todas</button>
                    <button onClick={() => setEditRules([])}
                      className="text-xs px-3 py-1 rounded-full bg-white/10 hover:bg-white/20 transition-colors">Ninguna</button>
                  </div>
                  <div className="max-h-60 overflow-y-auto space-y-2 pr-1">
                    {groups.map((group: any) => {
                      const ruleNames = group.rules.map((r: any) => r.name)
                      const allSelected = ruleNames.every((r: string) => editRules.includes(r))
                      const someSelected = ruleNames.some((r: string) => editRules.includes(r))
                      const isExpanded = expandedGroups[group.name] ?? true
                      return (
                        <div key={group.name} className="rounded-lg bg-white/5 overflow-hidden">
                          <div className="flex items-center gap-2 p-2">
                            <button onClick={() => toggleExpand(group.name)} className="p-1 hover:bg-white/10 rounded">
                              {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                            </button>
                            <input type="checkbox" checked={allSelected}
                              ref={(el) => { if (el && someSelected && !allSelected) el.indeterminate = true }}
                              onChange={() => toggleGroup(group.name, group.rules)}
                              className="w-4 h-4 rounded accent-indigo-500" />
                            <span className="text-sm font-medium">{GROUP_LABELS[group.name] || group.name}</span>
                            <span className="text-xs text-muted ml-auto">
                              {ruleNames.filter((r: string) => editRules.includes(r)).length}/{ruleNames.length}
                            </span>
                          </div>
                          {isExpanded && (
                            <div className="pl-10 pb-2 space-y-1">
                              {group.rules.map((rule: any) => (
                                <label key={rule.name} className="flex items-center gap-2 p-1.5 rounded hover:bg-white/5 cursor-pointer">
                                  <input type="checkbox" checked={editRules.includes(rule.name)}
                                    onChange={() => toggleRule(rule.name)}
                                    className="w-3.5 h-3.5 rounded accent-indigo-500" />
                                  <span className="text-xs">{rule.label}</span>
                                  <span className={`text-xs ml-auto px-1.5 py-0.5 rounded-full ${rule.severity === 'error' ? 'bg-red-500/20 text-red-300' : 'bg-yellow-500/20 text-yellow-300'}`}>
                                    {rule.severity === 'error' ? 'error' : 'warn'}
                                  </span>
                                </label>
                              ))}
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                </div>
              </div>
            ) : (
              <>
                <h1 className="text-2xl font-bold mb-4">{process.name}</h1>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div><p className="text-muted">Tipo de fuente</p><p className="font-medium">{sc.source_type}</p></div>
                  <div><p className="text-muted">Creado</p><p className="font-medium">{formatDate(process.created_at)}</p></div>
                  <div className="col-span-2">
                    <p className="text-muted">Reglas</p>
                    <p className="font-medium">{(process.rules_config || []).join(', ')}</p>
                  </div>
                  {sc.connection_string && <div className="col-span-2"><p className="text-muted">Connection String</p><p className="font-mono text-xs break-all">{sc.connection_string}</p></div>}
                  {sc.file_path && <div className="col-span-2"><p className="text-muted">Archivo</p><p className="font-mono text-xs break-all">{sc.file_path}</p></div>}
                  {sc.query && <div className="col-span-2"><p className="text-muted">Consulta</p><p className="font-mono text-xs break-all">{sc.query}</p></div>}
                </div>
              </>
            )}
          </GlassContainer>

          <GlassContainer>
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <Clock className="w-4 h-4" />
              Programación
            </h2>
            {!showScheduleForm && tasks.length > 0 ? tasks.map((t: any) => (
              <div key={t.id} className="bg-white/5 rounded-lg p-3 mb-2">
                <p className="text-sm font-medium">{t.name}</p>
                <p className="text-xs text-muted">Cron: {t.cron_expr}</p>
                <p className="text-xs text-muted">Estado: {t.status}</p>
                <Link to="/scheduler" className="text-xs text-indigo-400 mt-1 inline-block">Gestionar todas</Link>
              </div>
            )) : !showScheduleForm ? (
              <div>
                <p className="text-muted text-sm mb-3">Sin programación</p>
                <button onClick={() => { setSchedName(`Ejecución: ${process.name}`); setShowScheduleForm(true) }}
                  className="btn-ghost text-xs py-2 px-3 inline-flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  Programar ejecución
                </button>
              </div>
          ) : isPaused ? (
            <>
              <button onClick={() => resumeMutation.mutate()} disabled={resumeMutation.isPending}
                className="btn-ghost flex items-center gap-2 text-sm text-green-400">
                <Play className="w-4 h-4" />
                {resumeMutation.isPending ? 'Reanudando...' : 'Reanudar'}
              </button>
              <button onClick={() => stopMutation.mutate()} disabled={stopMutation.isPending}
                className="btn-ghost flex items-center gap-2 text-sm text-red-400">
                <StopCircle className="w-4 h-4" />
                {stopMutation.isPending ? 'Deteniendo...' : 'Detener'}
              </button>
            </>
          ) : isRunning ? (
            <>
              <button onClick={() => pauseMutation.mutate()} disabled={pauseMutation.isPending}
                className="btn-ghost flex items-center gap-2 text-sm text-yellow-400">
                <PauseCircle className="w-4 h-4" />
                {pauseMutation.isPending ? 'Pausando...' : 'Pausar'}
              </button>
              <button onClick={() => stopMutation.mutate()} disabled={stopMutation.isPending}
                className="btn-ghost flex items-center gap-2 text-sm text-red-400">
                <StopCircle className="w-4 h-4" />
                {stopMutation.isPending ? 'Deteniendo...' : 'Detener'}
              </button>
            </>
          ) : null}

            {showScheduleForm && (
              <div className="space-y-3 mt-2">
                <div>
                  <label className="block text-xs text-muted mb-1">Nombre</label>
                  <input type="text" value={schedName} onChange={(e) => setSchedName(e.target.value)}
                    className="glass-input text-sm" />
                </div>
                <div>
                  <label className="block text-xs text-muted mb-1">Frecuencia</label>
                  <div className="grid grid-cols-3 gap-1">
                    {['daily', 'weekly', 'monthly'].map((f) => (
                      <button key={f} onClick={() => setSchedFreq(f)}
                        className={`text-xs py-1.5 rounded-lg border transition-all ${schedFreq === f ? 'bg-indigo-500/20 border-indigo-400' : 'bg-white/5 border-white/10 text-muted hover:bg-white/10'}`}>
                        {freqLabels[f]}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="flex gap-2">
                  <div className="flex-1">
                    <label className="block text-xs text-muted mb-1">Hora</label>
                    <select value={schedHour} onChange={(e) => setSchedHour(e.target.value)} className="glass-input text-sm">
                      {Array.from({ length: 24 }, (_, i) => (
                        <option key={i} value={String(i)}>{String(i).padStart(2, '0')}:00</option>
                      ))}
                    </select>
                  </div>
                  <div className="flex-1">
                    <label className="block text-xs text-muted mb-1">Minuto</label>
                    <select value={schedMin} onChange={(e) => setSchedMin(e.target.value)} className="glass-input text-sm">
                      {Array.from({ length: 12 }, (_, i) => (
                        <option key={i} value={String(i * 5)}>{String(i * 5).padStart(2, '0')}</option>
                      ))}
                    </select>
                  </div>
                </div>
                {schedFreq === 'weekly' && (
                  <div>
                    <label className="block text-xs text-muted mb-1">Día de la semana</label>
                    <div className="grid grid-cols-7 gap-1">
                      {Object.entries(weekdayLabels).map(([k, v]) => (
                        <button key={k} onClick={() => setSchedWeekday(k)}
                          className={`text-xs py-1.5 rounded-lg border transition-all ${schedWeekday === k ? 'bg-indigo-500/20 border-indigo-400' : 'bg-white/5 border-white/10 text-muted hover:bg-white/10'}`}>
                          {v}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
                {schedFreq === 'monthly' && (
                  <div>
                    <label className="block text-xs text-muted mb-1">Día del mes</label>
                    <select value={schedDay} onChange={(e) => setSchedDay(e.target.value)} className="glass-input text-sm">
                      {Array.from({ length: 28 }, (_, i) => (
                        <option key={i + 1} value={String(i + 1)}>{i + 1}</option>
                      ))}
                    </select>
                  </div>
                )}
                <div>
                  <label className="block text-xs text-muted mb-1">Notificar (emails separados por coma)</label>
                  <input type="text" value={schedEmails} onChange={(e) => setSchedEmails(e.target.value)}
                    className="glass-input text-sm" placeholder="analista@mail.com" />
                </div>
                <div className="flex gap-2">
                  <button onClick={() => {
                    scheduleMutation.mutate({
                      project_id: id,
                      name: schedName,
                      cron_expr: buildCron(),
                      notify_emails: schedEmails.split(',').map((e: string) => e.trim()).filter(Boolean),
                    })
                  }} disabled={!schedName || scheduleMutation.isPending}
                    className="btn-primary text-xs py-2 flex-1">
                    {scheduleMutation.isPending ? 'Creando...' : 'Crear'}
                  </button>
                  <button onClick={() => setShowScheduleForm(false)} className="btn-ghost text-xs py-2">
                    <X className="w-3 h-3" />
                  </button>
                </div>
                <p className="text-xs text-muted text-center">
                  Cron: <span className="font-mono">{buildCron()}</span>
                </p>
              </div>
            )}
          </GlassContainer>
        </div>
      )}

      {!isRunning && process.status === 'failed' && (
        <GlassContainer className="mb-6">
          <div className="flex items-center gap-3 p-4 bg-red-500/10 border border-red-500/20 rounded-xl">
            <AlertCircle className="w-6 h-6 text-red-400 shrink-0" />
            <div>
              <p className="text-sm font-medium text-red-300">El análisis falló</p>
              <p className="text-xs text-muted mt-1">{process.progress?.error || 'Error desconocido'}</p>
            </div>
          </div>
        </GlassContainer>
      )}

      {!isRunning && !isCancelled && process.status !== 'failed' && (
        <GlassContainer>
          <h2 className="text-xl font-semibold mb-6">Reportes ({reports.length})</h2>
          {reports.length > 0 ? (
            <div className="space-y-3">
              {reports.map((r: any) => (
                <Link key={r.id} to={`/reports/${r.id}`}
                  className="flex items-center justify-between p-4 rounded-xl bg-white/5 hover:bg-white/10 transition-all">
                  <div className="flex items-center gap-4">
                    <span className={`text-xl font-bold ${r.score >= 70 ? 'text-green-400' : r.score >= 50 ? 'text-yellow-400' : 'text-red-400'}`}>{r.score}</span>
                    <div>
                      <span className={`badge badge-${r.label === 'excelente' ? 'success' : r.label === 'critico' ? 'error' : 'warning'}`}>{r.label}</span>
                      <p className="text-xs text-muted mt-1">{formatDate(r.executed_at)}</p>
                    </div>
                  </div>
                  <span className="text-indigo-400 text-xs">Ver detalle</span>
                </Link>
              ))}
            </div>
          ) : (
            <p className="text-muted text-center py-8">Este proceso aún no tiene reportes</p>
          )}
        </GlassContainer>
      )}
    </div>
  )
}
