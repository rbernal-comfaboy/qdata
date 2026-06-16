import { useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  ArrowLeft, CheckCircle, XCircle, AlertTriangle, Info,
  ChevronLeft, ChevronRight, ExternalLink,
} from 'lucide-react'
import api from '../api/client'
import GlassContainer from '../components/layout/GlassContainer'
import { describeError, describeDetail } from '../lib/ruleDescriptions'

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
  const [pageSize, setPageSize] = useState(10)
  const totalPages = hasDetails ? Math.ceil(rule.details.length / pageSize) : 0
  const paginatedDetails = hasDetails ? rule.details.slice(page * pageSize, (page + 1) * pageSize) : []

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
                {rule.passed ? 'Aprobado' : 'Fallos: ' + rule.failed + '/' + rule.total + ' (' + rule.failure_pct + '%)'}
              </span>
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
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted">Mostrar</span>
              <select
                value={pageSize}
                onChange={(e) => { setPage(0); setPageSize(Number(e.target.value)) }}
                className="bg-white/10 border border-white/10 rounded text-xs text-white px-2 py-1"
              >
                <option value={5}>5</option>
                <option value={10}>10</option>
                <option value={20}>20</option>
                <option value={50}>50</option>
                <option value={rule.details.length}>Todos</option>
              </select>
            </div>
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
                {Array.from({ length: totalPages }, (_, i) => (
                  <button
                    key={i}
                    onClick={() => setPage(i)}
                    className={`w-7 h-7 rounded text-xs font-medium ${
                      i === page ? 'bg-indigo-500 text-white' : 'text-muted hover:bg-white/10'
                    }`}
                  >
                    {i + 1}
                  </button>
                ))}
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
            Detalle de errores ({failures.length})
          </h2>
        </div>

        {failures.length > 0 ? (
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
                </tr>
              </thead>
              <tbody>
                {failures.map((item: any, i: number) => {
                  const info = describeError(rule.rule_name, item, rule.recommendation)
                  return (
                    <tr key={i} onClick={() => navigate(`/reports/${reportId}/rules/${ruleIdx}/errors/${i}`)}
                      className="border-b border-white/5 hover:bg-indigo-500/10 cursor-pointer transition-colors">
                      <td className="p-2 text-muted">{i + 1}</td>
                      <td className="p-2 text-white font-mono">{info.fila ?? '—'}</td>
                      <td className="p-2 text-white">{info.columna ?? '—'}</td>
                      <td className="p-2 text-white max-w-xs truncate font-mono text-xs">{info.valor ?? '—'}</td>
                      <td className="p-2 text-white">{info.descripcion}</td>
                      <td className="p-2 text-yellow-400 text-xs max-w-sm">{info.sugerencia}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
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
