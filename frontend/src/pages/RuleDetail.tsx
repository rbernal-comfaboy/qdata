import { useState, useMemo } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft, CheckCircle, XCircle, AlertTriangle, Info, CheckCircle2,
  ChevronLeft, ChevronRight, ExternalLink, Search, Circle, Clock,
} from 'lucide-react'
import api from '../api/client'
import GlassContainer from '../components/layout/GlassContainer'
import { describeError, describeDetail } from '../lib/ruleDescriptions'

const STATUS_OPTIONS = [
  { value: 'sin_accion', label: 'Sin acción', icon: Circle, color: 'text-muted' },
  { value: 'en_revision', label: 'En revisión', icon: Clock, color: 'text-yellow-400' },
  { value: 'solucionado', label: 'Solucionado', icon: CheckCircle2, color: 'text-green-400' },
] as const

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

function renderVal(v: any) {
  if (v === null || v === undefined) return <span className="text-muted">—</span>
  if (Array.isArray(v)) return v.join(', ')
  if (typeof v === 'object') return JSON.stringify(v)
  if (typeof v === 'number') {
    if (Number.isInteger(v)) return v.toLocaleString()
    const s = v.toString()
    if (s.includes('.') && s.split('.')[1].length > 4) return v.toFixed(4)
    return String(v)
  }
  return String(v)
}

function DetailsTable({ details }: { details: any[] }) {
  if (!details.length) return <p className="text-muted text-sm mt-2">Sin detalles</p>
  const keys = Object.keys(details[0])
  return (
    <div className="mt-2 overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-white/10">
            {keys.map((k) => (
              <th key={k} className="text-left p-2 text-muted font-medium whitespace-nowrap">{k}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {details.map((row, ri) => (
            <tr key={ri} className="border-b border-white/5 hover:bg-white/5">
              {keys.map((k) => (
                <td key={k} className="p-2 text-white whitespace-nowrap">{renderVal(row[k])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}



const GROUP_RULE_TYPES: Record<string, string> = {
  person_composite_similarity: 'person_composite_groups',
  personas_similares: 'personas_similares_groups',
  fuzzy_name_match: 'fuzzy_name_groups',
  fuzzy_id_match: 'fuzzy_id_groups',
  similar_dob: 'similar_dob_groups',
}

function getGroupMembers(rule: any, item: any): any[] {
  const typeKey = GROUP_RULE_TYPES[rule.rule_name]
  if (!typeKey) return []
  const detailItem = (rule.details || []).find((d: any) => d.type === typeKey)
  if (!detailItem?.groups) return []
  const rowIdx = item.row
  const group = detailItem.groups.find((g: any) => g.rows?.some((r: any) => r.row === rowIdx))
  return group?.rows || []
}

export default function RuleDetail() {
  const navigate = useNavigate()
  const { reportId, ruleIdx } = useParams<{ reportId: string; ruleIdx: string }>()
  const idx = parseInt(ruleIdx || '0')

  const { data: report, isLoading } = useQuery({
    queryKey: ['report', reportId],
    queryFn: () => api.get(`/reports/${reportId}`).then((r) => r.data),
    enabled: !!reportId,
  })

  const { data: actions = [] } = useQuery({
    queryKey: ['rule-actions', reportId, ruleIdx],
    queryFn: () => api.get(`/reports/${reportId}/rules/${ruleIdx}/actions`).then(r => r.data),
    enabled: !!reportId,
  })

  const inRevisionCount = actions.filter((a: any) => a.status === 'en_revision').length
  const resolvedCount = actions.filter((a: any) => a.status === 'solucionado').length

  const queryClient = useQueryClient()

  const actionMutation = useMutation({
    mutationFn: ({ errorIdx, status }: { errorIdx: number; status: string }) =>
      api.put(`/reports/${reportId}/rules/${ruleIdx}/errors/${errorIdx}/action`, { status }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rule-actions', reportId, ruleIdx] })
    },
  })

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="skeleton h-32 rounded-xl" />
        <div className="skeleton h-96 rounded-xl" />
      </div>
    )
  }

  const rules = report?.result?.results || []
  const rule = rules[idx]

  if (!rule) {
    return (
      <GlassContainer className="text-center py-12">
        <p className="text-muted">Regla no encontrada</p>
        <Link to={reportId ? `/reports/${reportId}` : '/reports'} className="text-indigo-400 mt-4 inline-block">
          Volver al reporte
        </Link>
      </GlassContainer>
    )
  }

  const SeverityIcon = severityIcons[rule.severity] || Info
  const failures: any[] = rule.sample_failures || []
  const hasDetails = rule.details?.length > 0

  const [page, setPage] = useState(0)
  const [pageSize, setPageSize] = useState(25)
  const [failuresPage, setFailuresPage] = useState(0)
  const [failuresPageSize, setFailuresPageSize] = useState(25)
  const [searchTerm, setSearchTerm] = useState('')
  const totalPages = hasDetails ? Math.ceil(rule.details.length / pageSize) : 0
  const paginatedDetails = hasDetails ? rule.details.slice(page * pageSize, (page + 1) * pageSize) : []

  const filteredFailures = useMemo(() => {
    if (!searchTerm.trim()) return failures
    const term = searchTerm.toLowerCase()
    return failures.filter((item: any) => {
      const values = item.values
        ? item.values
        : item.rows
          ? Object.assign({}, ...item.rows.map((r: any) => r.values || {}))
          : item
      return Object.values(values).some((v: any) =>
        String(v).toLowerCase().includes(term)
      )
    })
  }, [failures, searchTerm])

  const failuresTotalPages = Math.ceil(filteredFailures.length / failuresPageSize)
  const paginatedFailures = filteredFailures.slice(failuresPage * failuresPageSize, (failuresPage + 1) * failuresPageSize)

  return (
    <div className="relative">
      <Link
        to={`/reports/${reportId}`}
        className="inline-flex items-center gap-2 text-muted hover:text-white transition-colors mb-6"
      >
        <ArrowLeft className="w-4 h-4" />
        Volver al reporte
      </Link>

      <GlassContainer className="mb-6">
        <div className="flex items-start gap-4">
          {rule.passed ? (
            <CheckCircle className="w-8 h-8 text-green-400 mt-1 flex-shrink-0" />
          ) : (
            <SeverityIcon className={`w-8 h-8 ${severityColors[rule.severity]} mt-1 flex-shrink-0`} />
          )}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-3 flex-wrap">
              <h1 className="text-2xl font-bold text-white">{rule.rule_name}</h1>
              <span className={`badge badge-${rule.severity}`}>{rule.severity}</span>
              <span className={`text-sm font-medium ${rule.passed ? 'text-green-400' : 'text-red-400'}`}>
                {rule.passed ? 'Aprobado' : 'Fallos: ' + rule.failed + '/' + rule.total + ' (' + (rule.failure_pct ?? 0).toFixed(2) + '%)'}
              </span>
              <div className="flex items-center gap-1.5">
                {inRevisionCount > 0 && (
                  <span className="inline-flex items-center gap-1 text-xs text-yellow-400 bg-yellow-500/10 px-2 py-0.5 rounded-full">
                    <Clock className="w-3 h-3" />
                    {inRevisionCount} en revisión
                  </span>
                )}
                {resolvedCount > 0 && (
                  <span className="inline-flex items-center gap-1 text-xs text-green-400 bg-green-500/10 px-2 py-0.5 rounded-full">
                    <CheckCircle2 className="w-3 h-3" />
                    {resolvedCount} solucionado{resolvedCount !== 1 ? 's' : ''}
                  </span>
                )}
              </div>
            </div>
            <p className="text-muted mt-2">{rule.description}</p>
            {rule.recommendation && (
              <p className="text-yellow-400 text-sm mt-3">→ {rule.recommendation}</p>
            )}
          </div>
        </div>
      </GlassContainer>

      {hasDetails && (
        <GlassContainer className="mb-6">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-lg font-semibold text-white">Resumen por columna</h2>
            {rule.details.length > pageSize && (
              <div className="flex items-center gap-2">
                <span className="text-xs text-muted">Mostrar</span>
                <select
                  value={pageSize}
                  onChange={(e) => { setPage(0); setPageSize(Number(e.target.value)) }}
                  className="bg-white/10 border border-white/10 rounded text-xs text-white px-2 py-1"
                >
                  <option value={25}>25</option>
                  <option value={50}>50</option>
                  <option value={100}>100</option>
                  <option value={rule.details.length}>Todos</option>
                </select>
              </div>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {paginatedDetails.map((d: any, i: number) => (
              <div key={i} className="bg-white/5 rounded-lg p-3 text-sm">
                <p className="text-white">{describeDetail(rule.rule_name, d)}</p>
              </div>
            ))}
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-4 pt-3 border-t border-white/10">
              <p className="text-xs text-muted">
                {page * pageSize + 1}–{Math.min((page + 1) * pageSize, rule.details.length)} de {rule.details.length}
              </p>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => setPage(Math.max(0, page - 1))}
                  disabled={page === 0}
                  className="p-1 rounded hover:bg-white/10 disabled:opacity-30 disabled:cursor-not-allowed"
                >
                  <ChevronLeft className="w-4 h-4 text-white" />
                </button>
                {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
                  const start = Math.max(0, page - 3)
                  const idx = start + i
                  if (idx >= totalPages) return null
                  return (
                    <button
                      key={idx}
                      onClick={() => setPage(idx)}
                      className={`w-7 h-7 rounded text-xs font-medium ${
                        idx === page ? 'bg-indigo-500 text-white' : 'text-muted hover:bg-white/10'
                      }`}
                    >
                      {idx + 1}
                    </button>
                  )
                })}
                <button
                  onClick={() => setPage(Math.min(totalPages - 1, page + 1))}
                  disabled={page >= totalPages - 1}
                  className="p-1 rounded hover:bg-white/10 disabled:opacity-30 disabled:cursor-not-allowed"
                >
                  <ChevronRight className="w-4 h-4 text-white" />
                </button>
              </div>
            </div>
          )}

          <details className="mt-3">
            <summary className="text-xs text-muted cursor-pointer hover:text-white">Ver datos originales</summary>
            <DetailsTable details={rule.details} />
          </details>
        </GlassContainer>
      )}

      <GlassContainer>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-white">
            Detalle de errores ({filteredFailures.length})
          </h2>
          <div className="flex items-center gap-2">
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-muted absolute left-2 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Buscar..."
                value={searchTerm}
                onChange={(e) => { setSearchTerm(e.target.value); setFailuresPage(0) }}
                className="bg-white/10 border border-white/10 rounded text-xs text-white pl-7 pr-2 py-1 w-40 placeholder:text-muted focus:outline-none focus:border-indigo-400"
              />
            </div>
            <span className="text-xs text-muted">Mostrar</span>
            <select
              value={failuresPageSize}
              onChange={(e) => { setFailuresPage(0); setFailuresPageSize(Number(e.target.value)) }}
              className="bg-white/10 border border-white/10 rounded text-xs text-white px-2 py-1"
            >
              <option value={25}>25</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
              <option value={500}>500</option>
              <option value={filteredFailures.length}>Todos</option>
            </select>
          </div>
        </div>

        {filteredFailures.length > 0 ? (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-white/10">
                    <th className="text-left p-2 text-muted font-medium whitespace-nowrap w-10">#</th>
                    <th className="text-left p-2 text-muted font-medium whitespace-nowrap">Fila</th>
                    <th className="text-left p-2 text-muted font-medium whitespace-nowrap">Columna</th>
                    <th className="text-left p-2 text-muted font-medium whitespace-nowrap">Valor</th>
                    <th className="text-left p-2 text-muted font-medium whitespace-nowrap">Descripción del error</th>
                    <th className="text-left p-2 text-muted font-medium whitespace-nowrap">Sugerencia</th>
                    <th className="text-left p-2 text-muted font-medium whitespace-nowrap">Estado</th>
                  </tr>
                </thead>
                <tbody>
                  {paginatedFailures.map((item: any, i: number) => {
                    const globalIdx = failuresPage * failuresPageSize + i
                    const info = describeError(rule.rule_name, item, rule.recommendation)
                    return (
                      <tr key={globalIdx} onClick={() => navigate(`/reports/${reportId}/rules/${ruleIdx}/errors/${globalIdx}`)}
                        className="border-b border-white/5 hover:bg-indigo-500/10 cursor-pointer transition-colors">
                        <td className="p-2 text-muted">{globalIdx + 1}</td>
                        <td className="p-2 text-white font-mono">{info.fila ?? '—'}</td>
                        <td className="p-2 text-white">{info.columna ?? '—'}</td>
                        <td className="p-2 text-white max-w-xs truncate font-mono text-xs">{info.valor ?? '—'}</td>
                        <td className="p-2 text-white">{info.descripcion}</td>
                        <td className="p-2 text-yellow-400 text-xs max-w-sm">{info.sugerencia}</td>
                        <td className="p-2" onClick={(e) => e.stopPropagation()}>
                          <div className="flex items-center gap-1">
                            {(() => {
                              const act = actions.find((a: any) => a.error_index === globalIdx)
                              const st = act?.status || 'sin_accion'
                              const opt = STATUS_OPTIONS.find(o => o.value === st)
                              const Icon = opt?.icon || Circle
                              return (
                                <>
                                  <Icon className={`w-3 h-3 ${opt?.color}`} />
                                  <select
                                    value={st}
                                    onChange={(e) => actionMutation.mutate({ errorIdx: globalIdx, status: e.target.value })}
                                    className="bg-transparent border border-white/10 rounded text-xs text-white px-1 py-0.5 appearance-none cursor-pointer hover:bg-white/10 transition-colors max-w-[7rem]"
                                    onClick={(e) => e.stopPropagation()}
                                  >
                                    {STATUS_OPTIONS.map(sopt => (
                                      <option key={sopt.value} value={sopt.value} className="bg-gray-900">{sopt.label}</option>
                                    ))}
                                  </select>
                                </>
                              )
                            })()}
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>

            {failuresTotalPages > 1 && (
              <div className="flex items-center justify-between mt-4 pt-3 border-t border-white/10">
                <p className="text-xs text-muted">
                  {failuresPage * failuresPageSize + 1}–{Math.min((failuresPage + 1) * failuresPageSize, filteredFailures.length)} de {filteredFailures.length}
                </p>
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => setFailuresPage(0)}
                    disabled={failuresPage === 0}
                    className="px-2 py-1 rounded text-xs text-muted hover:bg-white/10 disabled:opacity-30 disabled:cursor-not-allowed"
                  >
                    ««
                  </button>
                  <button
                    onClick={() => setFailuresPage(Math.max(0, failuresPage - 1))}
                    disabled={failuresPage === 0}
                    className="p-1 rounded hover:bg-white/10 disabled:opacity-30 disabled:cursor-not-allowed"
                  >
                    <ChevronLeft className="w-4 h-4 text-white" />
                  </button>
                  {(() => {
                    const maxVisible = 7
                    let start = Math.max(0, failuresPage - Math.floor(maxVisible / 2))
                    let end = Math.min(failuresTotalPages, start + maxVisible)
                    start = Math.max(0, end - maxVisible)
                    const pages = []
                    if (start > 0) {
                      pages.push(
                        <button key={0} onClick={() => setFailuresPage(0)}
                          className="w-7 h-7 rounded text-xs font-medium text-muted hover:bg-white/10">1</button>
                      )
                      if (start > 1) pages.push(<span key="e1" className="text-muted text-xs">…</span>)
                    }
                    for (let i = start; i < end; i++) {
                      pages.push(
                        <button key={i} onClick={() => setFailuresPage(i)}
                          className={`w-7 h-7 rounded text-xs font-medium ${
                            i === failuresPage ? 'bg-indigo-500 text-white' : 'text-muted hover:bg-white/10'
                          }`}>
                          {i + 1}
                        </button>
                      )
                    }
                    if (end < failuresTotalPages) {
                      if (end < failuresTotalPages - 1) pages.push(<span key="e2" className="text-muted text-xs">…</span>)
                      pages.push(
                        <button key={failuresTotalPages - 1} onClick={() => setFailuresPage(failuresTotalPages - 1)}
                          className="w-7 h-7 rounded text-xs font-medium text-muted hover:bg-white/10">{failuresTotalPages}</button>
                      )
                    }
                    return pages
                  })()}
                  <button
                    onClick={() => setFailuresPage(Math.min(failuresTotalPages - 1, failuresPage + 1))}
                    disabled={failuresPage >= failuresTotalPages - 1}
                    className="p-1 rounded hover:bg-white/10 disabled:opacity-30 disabled:cursor-not-allowed"
                  >
                    <ChevronRight className="w-4 h-4 text-white" />
                  </button>
                  <button
                    onClick={() => setFailuresPage(failuresTotalPages - 1)}
                    disabled={failuresPage >= failuresTotalPages - 1}
                    className="px-2 py-1 rounded text-xs text-muted hover:bg-white/10 disabled:opacity-30 disabled:cursor-not-allowed"
                  >
                    »»
                  </button>
                </div>
              </div>
            )}
          </>
        ) : (
          <p className="text-muted text-sm">No hay errores de muestra para esta regla</p>
        )}

        <details className="mt-4">
          <summary className="text-xs text-muted cursor-pointer hover:text-white">Ver datos originales</summary>
          <DetailsTable details={failures} />
        </details>
      </GlassContainer>
    </div>
  )
}
