import { useState, useMemo } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  ArrowLeft, AlertTriangle, Search, Wrench, Lightbulb,
  Database, Copy, Users, ExternalLink,
} from 'lucide-react'
import api from '../api/client'
import GlassContainer from '../components/layout/GlassContainer'
import { describeError } from '../lib/ruleDescriptions'

const severityColors: Record<string, string> = {
  error: 'text-red-400', warning: 'text-yellow-400', info: 'text-blue-400',
}

const GROUP_RULE_TYPES: Record<string, string> = {
  person_composite_similarity: 'person_composite_groups',
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

function getErrorExplanation(ruleName: string): { meaning: string; steps: string[] } {
  const map: Record<string, { meaning: string; steps: string[] }> = {
    null_check: { meaning: 'Este valor está vacío o es nulo (None/NaN).', steps: ['Investiga por qué falta el dato.', 'Si debe tener un valor, rellénalo manualmente.', 'Para columnas numéricas, imputa con la media.', 'Si son pocos registros, considera eliminar la fila.'] },
    type_check: { meaning: 'El tipo de dato de esta columna no coincide con lo esperado.', steps: ['Usa pd.to_numeric() para convertir texto a número.', 'Usa pd.to_datetime() para convertir a fecha.', 'Limpia caracteres no numéricos.', 'Agrega validación en la fuente de datos.'] },
    unique_check: { meaning: 'Se esperaba que esta columna tuviera valores únicos, pero se encontraron duplicados.', steps: ['Identifica si los duplicados son errores o datos legítimos.', 'Elimina duplicados exactos.', 'Si es legítimo, reconsidera la clave primaria.'] },
    duplicate_check: { meaning: 'Se encontraron filas idénticas en el dataset.', steps: ['Usa df.drop_duplicates() para eliminar filas duplicadas.', 'Revisa el proceso de ingesta.', 'Agrega una restricción UNIQUE en la BD.'] },
    range_check: { meaning: 'El valor está fuera del rango esperado para esta columna.', steps: ['Verifica si es error de captura.', 'Si es error, corrígelo o elimina la fila.', 'Si es outlier legítimo, documéntalo.', 'Usa IQR o Z-score para detectar outliers.'] },
    pattern_check: { meaning: 'El valor no cumple con el formato esperado.', steps: ['Identifica el patrón esperado.', 'Usa regex para limpiar y estandarizar.', 'Agrega validación en el formulario de captura.'] },
    email_check: { meaning: 'El valor no es una dirección de email válida.', steps: ['Verifica que contenga @ y dominio válido.', 'Corrige errores comunes.', 'Usa email-validator para validar.'] },
    phone_check: { meaning: 'El número de teléfono no tiene formato válido.', steps: ['Estandariza a formato internacional.', 'Elimina caracteres no numéricos.', 'Verifica la longitud.'] },
    zip_code_check: { meaning: 'El código postal no tiene el formato correcto.', steps: ['México: exactamente 5 dígitos.', 'USA: 5 o 9 dígitos.', 'Verifica contra catálogo oficial.'] },
    rfc_curp_check: { meaning: 'El RFC o CURP no cumple con el formato oficial del SAT.', steps: ['RFC persona moral: 12 caracteres.', 'RFC persona física: 13 caracteres.', 'CURP: 18 caracteres.', 'Usa el validador oficial del SAT.'] },
    date_inconsistency_check: { meaning: 'Hay contradicción temporal entre dos fechas.', steps: ['Verifica qué fecha es correcta.', 'Corrige manualmente.', 'Agrega validación CHECK en la BD.'] },
    invalid_date_check: { meaning: 'La fecha no tiene formato válido o no existe.', steps: ['Usa pd.to_datetime() con el formato específico.', 'Verifica meses, días y años.'] },
    date_range_check: { meaning: 'La fecha está fuera del rango esperado.', steps: ['Define un rango válido.', 'Corrige fechas con errores obvios.'] },
    referential_integrity_check: { meaning: 'Un valor referencia un registro que no existe.', steps: ['Identifica si el padre fue eliminado.', 'Agrega FOREIGN KEY para prevenirlo.'] },
    missing_fk_check: { meaning: 'Se encontraron valores FK huérfanos.', steps: ['Identifica los valores huérfanos.', 'Crea el registro padre o corrige el hijo.'] },
    cardinality_check: { meaning: 'La columna tiene cardinalidad anómala.', steps: ['Revisa si contiene datos libres vs categorías.', 'Considera si la columna es útil.'] },
    correlation_check: { meaning: 'Dos variables están altamente correlacionadas.', steps: ['Identifica el par correlacionado.', 'Elimina una del modelo.', 'Usa PCA para combinarlas.'] },
    distribution_check: { meaning: 'La distribución tiene asimetría extrema.', steps: ['Aplica transformación logarítmica.', 'Usa Box-Cox.', 'Considera usar la mediana.'] },
    row_completeness_check: { meaning: 'Esta fila tiene muchas columnas nulas.', steps: ['Si >50% faltante, considera eliminar.', 'Imputa con media/mediana/moda.'] },
    multivariate_outlier_check: { meaning: 'Combinación de valores anómala.', steps: ['Revisa si la combinación es posible.', 'Usa Isolation Forest o DBSCAN.'] },
    sequential_integrity_check: { meaning: 'Saltos en secuencia de IDs.', steps: ['Investiga la causa.', 'Para sistemas críticos, usa UUIDs.'] },
    volume_anomaly_check: { meaning: 'Volumen de datos significativamente diferente.', steps: ['Si menos filas: revisa extracción.', 'Si más filas: revisa duplicados.'] },
    cross_consistency_check: { meaning: 'Se violó una regla de consistencia entre columnas.', steps: ['Identifica qué regla se violó.', 'Corrige los valores inconsistentes.', 'Agrega CHECK constraint en la BD.'] },
    functional_dependency_check: { meaning: 'Se violó una dependencia funcional.', steps: ['Identifica los pares que violan.', 'Determina el valor correcto.', 'Agrega restricción UNIQUE.'] },
    derived_column_check: { meaning: 'Columna calculada no coincide con el valor esperado.', steps: ['Verifica la fórmula.', 'Recalcula la columna.', 'Automatiza verificación en ETL.'] },
    person_composite_similarity: { meaning: 'Registros que podrían ser la misma persona con variaciones.', steps: ['Revisa cada grupo manualmente.', 'Si es la misma persona, unifica.', 'Ajusta el threshold si hay muchos falsos positivos.'] },
    fuzzy_name_match: { meaning: 'Registros con nombres muy similares.', steps: ['Revisa los pares.', 'Si es la misma persona corrige el nombre.', 'Si son diferentes, sube el threshold.'] },
    fuzzy_id_match: { meaning: 'IDs muy similares con 1-2 dígitos de diferencia.', steps: ['Compara dígito por dígito.', 'Si es el mismo, corrige.', 'Agrega validación de dígito verificador.'] },
    similar_dob: { meaning: 'Fechas de nacimiento muy cercanas.', steps: ['Revisa si es la misma persona con error en el día.', 'Ajusta window_days si hay muchos falsos positivos.'] },
  }
  return map[ruleName] || { meaning: 'Se detectó un valor inesperado.', steps: ['Revisa el valor actual.', 'Consulta la fuente original.', 'Corrige si es error de captura.', 'Agrega validaciones en la ingesta.'] }
}

function renderVal(v: any) {
  if (v === null || v === undefined) return <span className="text-muted italic">NULL</span>
  if (Array.isArray(v)) return v.join(', ')
  if (typeof v === 'object') return JSON.stringify(v)
  return String(v)
}

export default function ErrorDetail() {
  const { reportId, ruleIdx, errorIdx } = useParams<{ reportId: string; ruleIdx: string; errorIdx: string }>()
  const ri = parseInt(ruleIdx || '0')
  const ei = parseInt(errorIdx || '0')

  const { data: report, isLoading } = useQuery({
    queryKey: ['report', reportId],
    queryFn: () => api.get(`/reports/${reportId}`).then(r => r.data),
    enabled: !!reportId,
  })

  if (isLoading) return <div className="space-y-6"><div className="skeleton h-32 rounded-xl" /><div className="skeleton h-96 rounded-xl" /></div>

  const rules = report?.result?.results || []
  const rule = rules[ri]
  const failures: any[] = rule?.sample_failures || []
  const item = failures[ei]

  if (!rule || !item) return (
    <GlassContainer className="text-center py-12">
      <p className="text-muted">Error no encontrado</p>
      <Link to={`/reports/${reportId}/rules/${ruleIdx}`} className="text-indigo-400 mt-4 inline-block">Volver a la regla</Link>
    </GlassContainer>
  )

  const info = describeError(rule.rule_name, item, rule.recommendation)
  const explanation = getErrorExplanation(rule.rule_name)
  const fullRecord = item.values || null
  const recordEntries = fullRecord ? Object.entries(fullRecord) : []
  const groupMembers = getGroupMembers(rule, item)
  const [copied, setCopied] = useState(false)

  const extractTable = (query: string): string | null => {
    const cleaned = query.replace(/\/\*.*?\*\//gs, '').replace(/--.*?$/gm, '')
    const match = cleaned.match(/\bFROM\b\s+([^\s,;()]+)/i)
    return match ? match[1].replace(/^"|"$/g, '').replace(/^`|`$/g, '') : null
  }

  const sqlQuery = useMemo(() => {
    const sourceQuery = report?.source_query
    if (!sourceQuery) return null
    const table = extractTable(sourceQuery)
    const vals = item.values || {}
    const entries = Object.entries(vals)
    if (table && entries.length > 0) {
      const whereClauses = entries.filter(([, v]) => v != null && v !== '').slice(0, 5).map(([k, v]) =>
        typeof v === 'number' && !Number.isNaN(v) ? `  ${k} = ${v}` : `  ${k} = '${String(v).replace(/'/g, "''")}'`
      ).join('\n  AND ')
      if (whereClauses) return `SELECT *\nFROM ${table}\nWHERE\n${whereClauses}\nLIMIT 1`
    }
    return null
  }, [report?.source_query, item])

  const handleCopySql = () => {
    if (!sqlQuery) return
    navigator.clipboard.writeText(sqlQuery)
    setCopied(true); setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div>
      <Link to={`/reports/${reportId}/rules/${ruleIdx}`}
        className="inline-flex items-center gap-2 text-muted hover:text-white transition-colors mb-6">
        <ArrowLeft className="w-4 h-4" />
        Volver a {rule.rule_name}
      </Link>

      <GlassContainer>
        <div className="flex items-center gap-3 mb-6">
          <div>
            <h1 className="text-2xl font-bold text-white">{rule.rule_name}</h1>
            <p className="text-muted text-sm mt-1">Error #{ei + 1} de {failures.length}</p>
          </div>
        </div>

        <div className="space-y-6">
          <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-4">
            <div className="flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-red-400 mt-0.5 shrink-0" />
              <div>
                <p className="text-white font-medium">{info.descripcion}</p>
                <p className="text-red-300 text-sm mt-1">{info.sugerencia}</p>
              </div>
            </div>
          </div>

          <div>
            <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
              <Search className="w-4 h-4 text-indigo-400" />
              Detalle del error
            </h3>
            <div className="grid grid-cols-3 gap-3">
              {info.fila != null && (
                <div className="bg-white/5 rounded-lg p-3">
                  <p className="text-xs text-muted mb-1">Fila</p>
                  <p className="text-white font-mono font-medium">{info.fila}</p>
                </div>
              )}
              {info.columna && (
                <div className="bg-white/5 rounded-lg p-3">
                  <p className="text-xs text-muted mb-1">Columna</p>
                  <p className="text-white font-mono font-medium truncate">{info.columna}</p>
                </div>
              )}
              {info.valor != null && (
                <div className="bg-white/5 rounded-lg p-3 col-span-1">
                  <p className="text-xs text-muted mb-1">Valor actual</p>
                  <p className="text-red-400 font-mono text-sm break-all max-h-20 overflow-y-auto">{info.valor}</p>
                </div>
              )}
            </div>
          </div>

          {recordEntries.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                <Database className="w-4 h-4 text-cyan-400" />
                Registro completo (fila {info.fila})
              </h3>
              <div className="bg-white/5 rounded-xl overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-white/10">
                      {recordEntries.map(([key]) => <th key={key} className="text-left p-2 text-muted font-medium whitespace-nowrap">{key}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    <tr className="border-b border-white/5">
                      {recordEntries.map(([key, val]) => (
                        <td key={key} className="p-2 text-white font-mono whitespace-nowrap">{renderVal(val)}</td>
                      ))}
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {groupMembers.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                <Users className="w-4 h-4 text-purple-400" />
                Registros del grupo ({groupMembers.length})
              </h3>
              <div className="bg-white/5 rounded-xl overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-white/10">
                      <th className="text-left p-2.5 text-muted font-medium">#</th>
                      {recordEntries.map(([key]) => <th key={key} className="text-left p-2.5 text-muted font-medium whitespace-nowrap">{key}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {groupMembers.map((member: any, mi: number) => {
                      const isCurrent = member.row === item.row
                      const vals = member.values || item.values || {}
                      return (
                        <tr key={mi} className={'border-b border-white/5 last:border-0 ' + (isCurrent ? 'bg-red-500/10' : '')}>
                          <td className="p-2.5 text-muted font-mono">{isCurrent ? '← este' : mi + 1}</td>
                          {recordEntries.map(([key]) => <td key={key} className="p-2.5 text-white font-mono whitespace-nowrap">{renderVal(vals[key])}</td>)}
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          <div>
            <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
              <Lightbulb className="w-4 h-4 text-yellow-400" />
              ¿Qué significa?
            </h3>
            <p className="text-muted text-sm leading-relaxed">{explanation.meaning}</p>
          </div>

          <div>
            <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
              <Wrench className="w-4 h-4 text-green-400" />
              ¿Cómo solucionarlo?
            </h3>
            <ol className="space-y-2">
              {explanation.steps.map((step, i) => (
                <li key={i} className="flex items-start gap-3 text-sm">
                  <span className="w-5 h-5 rounded-full bg-indigo-500/20 text-indigo-400 flex items-center justify-center text-xs font-bold shrink-0 mt-0.5">{i + 1}</span>
                  <span className="text-muted">{step}</span>
                </li>
              ))}
            </ol>
          </div>

          {sqlQuery && (
            <details className="border border-white/10 rounded-lg" open>
              <summary className="flex items-center gap-2 px-4 py-3 text-xs text-muted cursor-pointer hover:text-white">
                <Database className="w-3.5 h-3.5" /> Ver consulta SQL de la fila
              </summary>
              <div className="px-4 pb-3 space-y-2">
                <pre className="text-xs text-muted font-mono bg-black/30 rounded-lg p-3 overflow-x-auto max-h-48 whitespace-pre-wrap">{sqlQuery}</pre>
                <button onClick={handleCopySql} className="inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-white/10 hover:bg-white/20 text-white transition-colors">
                  <Copy className="w-3 h-3" />{copied ? 'Copiado' : 'Copiar SQL'}
                </button>
              </div>
            </details>
          )}

          <details className="border border-white/10 rounded-lg">
            <summary className="flex items-center gap-2 px-4 py-3 text-xs text-muted cursor-pointer hover:text-white">
              <Database className="w-3.5 h-3.5" /> Ver datos originales del error
            </summary>
            <div className="px-4 pb-3">
              <pre className="text-xs text-muted font-mono bg-white/5 rounded-lg p-3 overflow-x-auto max-h-48">{JSON.stringify(item, null, 2)}</pre>
            </div>
          </details>

          <div className="flex items-center gap-2 text-xs text-indigo-400">
            <ExternalLink className="w-3.5 h-3.5" />
            <span>Regla: {rule.rule_name} — {rule.description}</span>
          </div>
        </div>
      </GlassContainer>
    </div>
  )
}
