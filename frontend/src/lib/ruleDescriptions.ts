export type ErrorInfo = {
  descripcion: string
  sugerencia: string
  fila: number | string | null
  columna: string | null
  valor: string | null
}

function valStr(v: any): string {
  if (v === null || v === undefined) return '—'
  const s = String(v)
  const SPECIAL_CHARS: Record<string, string> = {
    '\u00A0': '\\u00A0(NBSP)',
    '\u200B': '\\u200B(ZWSP)',
    '\u200C': '\\u200C(ZWNJ)',
    '\u200D': '\\u200D(ZWJ)',
    '\uFEFF': '\\uFEFF(BOM)',
    '\u202A': '\\u202A(LRE)',
    '\u202B': '\\u202B(RLE)',
    '\u202C': '\\u202C(PDF)',
    '\u202D': '\\u202D(LRO)',
    '\u202E': '\\u202E(RLO)',
    '\u2066': '\\u2066(LRI)',
    '\u2067': '\\u2067(RLI)',
    '\u2068': '\\u2068(FSI)',
    '\u2069': '\\u2069(PDI)',
    '\u0000': '\\0', '\u0001': '\\u0001', '\u0002': '\\u0002', '\u0003': '\\u0003',
    '\u0004': '\\u0004', '\u0005': '\\u0005', '\u0006': '\\u0006', '\u0007': '\\u0007',
    '\u0008': '\\u0008', '\u000B': '\\u000B', '\u000C': '\\u000C', '\u000E': '\\u000E',
    '\u000F': '\\u000F', '\u0010': '\\u0010', '\u0011': '\\u0011', '\u0012': '\\u0012',
    '\u0013': '\\u0013', '\u0014': '\\u0014', '\u0015': '\\u0015', '\u0016': '\\u0016',
    '\u0017': '\\u0017', '\u0018': '\\u0018', '\u0019': '\\u0019', '\u001A': '\\u001A',
    '\u001B': '\\u001B', '\u001C': '\\u001C', '\u001D': '\\u001D', '\u001E': '\\u001E',
    '\u001F': '\\u001F', '\u007F': '\\u007F',
    '\u2000': '\\u2000', '\u2001': '\\u2001', '\u2002': '\\u2002', '\u2003': '\\u2003',
    '\u2004': '\\u2004', '\u2005': '\\u2005', '\u2006': '\\u2006', '\u2007': '\\u2007',
    '\u2008': '\\u2008', '\u2009': '\\u2009', '\u200A': '\\u200A', '\u202F': '\\u202F',
    '\u205F': '\\u205F', '\u3000': '\\u3000',
  }
  let result = ''
  for (const ch of s) {
    if (SPECIAL_CHARS[ch]) {
      result += SPECIAL_CHARS[ch]
    } else {
      result += ch
    }
  }
  return result
}

function trunc(s: string, n = 120): string {
  return s.length > n ? s.slice(0, n) + '…' : s
}

const SUGERENCIAS: Record<string, string> = {
  null_check: 'Rellenar con valor por defecto o imputar con media/mediana/moda',
  type_check: 'Convertir al tipo de dato correcto con pd.to_datetime() o pd.to_numeric()',
  unique_check: 'Eliminar duplicados o revisar lógica de clave primaria',
  duplicate_check: 'Eliminar filas duplicadas exactas',
  range_check: 'Verificar si es error de captura o outlier legítimo',
  pattern_check: 'Estandarizar el formato con regex o librerías de validación',
  cardinality_check: 'Evaluar si la columna aporta información útil',
  correlation_check: 'Considerar eliminar variables correlacionadas o usar PCA',
  distribution_check: 'Aplicar transformación logarítmica o Box-Cox',
  email_check: 'Corregir formato de email: usuario@dominio.tld',
  special_chars_check: 'Remover caracteres problemáticos: control, zero-width, uso privado, seguridad y espacios no estándar',
  string_length_check: 'Ajustar longitud al rango esperado',
  trim_check: 'Aplicar .trim() para eliminar espacios extras',
  case_consistency_check: 'Uniformar a mayúsculas o minúsculas según el estándar',
  phone_check: 'Estandarizar formato telefónico: +52 (MX) o +1 (US) con 10 dígitos',
  zip_code_check: 'Corregir código postal: MX=5 dígitos, US=5 o 9 dígitos',
  rfc_curp_check: 'Corregir RFC (13 chars) o CURP (18 chars) según formato SAT',
  invalid_date_check: 'Corregir fechas mal formadas (usar YYYY-MM-DD)',
  date_range_check: 'Revisar fechas fuera del rango esperado',
  date_inconsistency_check: 'Verificar que fecha_inicio <= fecha_fin',
  freshness_check: 'Verificar frescura de la fuente de datos',
  latency_check: 'Revisar pipeline de ingesta para reducir latencia',
  volume_anomaly_check: 'Validar el volumen de registros contra lo esperado',
  sequential_integrity_check: 'Revisar eliminaciones o fallos en generación de IDs',
  missing_fk_check: 'Verificar integridad referencial de llaves foráneas',
  referential_integrity_check: 'Valores huérfanos sin correspondencia en tabla padre',
  row_completeness_check: 'Completar filas con datos faltantes o imputar valores',
  multivariate_outlier_check: 'Revisar combinaciones anómalas de variables',
  drift_check: 'Investigar si las categorías nuevas son datos válidos',
  schema_evolution_check: 'Revisar compatibilidad del esquema actual vs referencia',
  cross_consistency_check: 'Revisar relaciones aritméticas y lógicas entre columnas',
  functional_dependency_check: 'Un valor del determinante debe corresponder a un único valor del dependiente',
  class_balance_check: 'Evaluar si columnas con un solo valor aportan información',
  boolean_bias_check: 'Considerar si columnas extremadamente sesgadas son útiles',
  derived_column_check: 'Verificar la fórmula de cálculo de la columna derivada',
  fuzzy_name_match: 'Revisar nombres similares que podrían ser la misma persona',
  fuzzy_id_match: 'Revisar IDs similares que podrían ser errores de digitación',
  similar_dob: 'Revisar fechas cercanas del mismo registro duplicado',
  person_composite_similarity: 'Revisar grupos detectados como posible misma persona',
  personas_similares: 'Revisar grupos de personas similares detectados — pueden ser duplicados',
  custom_sql_rule: 'Revisar registros que no cumplen la regla SQL personalizada',
  custom_python_rule: 'Revisar registros que no pasan la validación personalizada',
}

export function describeError(ruleName: string, item: Record<string, any>, recommendation?: string): ErrorInfo {
  const row = item.row != null ? Number(item.row) + 2 : null
  const sug = recommendation || SUGERENCIAS[ruleName] || 'Revisar el valor en la fuente de datos'

  switch (ruleName) {
    case 'null_check':
      return {
        descripcion: `Valor nulo o vacío en columna '${item.column}'`,
        sugerencia: sug,
        fila: row,
        columna: item.column || null,
        valor: null,
      }

    case 'type_check':
      return {
        descripcion: `Tipo de dato inesperado en columna '${item.column}'${item.sample_value ? ` (ej: ${item.sample_value})` : ''}`,
        sugerencia: sug,
        fila: row,
        columna: item.column || null,
        valor: item.sample_value ? valStr(item.sample_value) : null,
      }

    case 'unique_check':
      return {
        descripcion: `Valor duplicado en columna '${item.column}'`,
        sugerencia: sug,
        fila: row,
        columna: item.column || null,
        valor: item.value != null ? valStr(item.value) : null,
      }

    case 'duplicate_check': {
      const rows = item.rows || []
      const count = rows.length
      const rowNums = rows.map((r: any) => r.row != null ? Number(r.row) + 2 : null).filter((r: any) => r !== null)
      const displayRows = rowNums.length <= 5
        ? rowNums.join(', ')
        : `${rowNums[0]}, ${rowNums[1]}, … (+${rowNums.length - 2} más)`
      const first = rows[0]
      return {
        descripcion: `Grupo duplicado (${count} filas): ${first?.values ? Object.entries(first.values).slice(0, 3).map(([k, v]) => `${k}=${v}`).join(', ') : ''}`,
        sugerencia: sug,
        fila: displayRows || null,
        columna: null,
        valor: first?.values ? Object.entries(first.values).slice(0, 5).map(([k, v]) => `${k}: ${v}`).join(', ') : null,
      }
    }

    case 'range_check':
      return {
        descripcion: `Valor fuera de rango en columna '${item.column}': ${valStr(item.value)}`,
        sugerencia: sug,
        fila: row,
        columna: item.column || null,
        valor: item.value != null ? valStr(item.value) : null,
      }

    case 'pattern_check':
      return {
        descripcion: `Formato inválido en columna '${item.column}': ${valStr(item.value)}`,
        sugerencia: sug,
        fila: row,
        columna: item.column || null,
        valor: item.value != null ? valStr(item.value) : null,
      }

    case 'cardinality_check':
      return {
        descripcion: `Cardinalidad anómala en columna '${item.column}': ${item.warning || ''}`,
        sugerencia: sug,
        fila: row,
        columna: item.column || null,
        valor: item.warning || null,
      }

    case 'correlation_check':
      return {
        descripcion: `Correlación alta (${item.correlation}) entre columnas: ${item.columns || ''}`,
        sugerencia: sug,
        fila: null,
        columna: item.columns || null,
        valor: item.correlation != null ? valStr(item.correlation) : null,
      }

    case 'distribution_check':
      return {
        descripcion: `Distribución anómala en columna '${item.column}': ${(item.flags || []).join(', ')}`,
        sugerencia: sug,
        fila: row,
        columna: item.column || null,
        valor: (item.flags || []).join(', '),
      }

    case 'email_check':
    case 'phone_check':
    case 'zip_code_check':
    case 'rfc_curp_check':
    case 'special_chars_check':
    case 'string_length_check':
    case 'trim_check':
    case 'case_consistency_check':
    case 'invalid_date_check':
    case 'date_range_check':
    case 'freshness_check':
    case 'missing_fk_check':
    case 'pattern_check_fallback':
      return {
        descripcion: `${item.column ? `En columna '${item.column}'` : ''} valor inválido: ${valStr(item.value)}`,
        sugerencia: sug,
        fila: row,
        columna: item.column || null,
        valor: item.value != null ? valStr(item.value) : null,
      }

    case 'date_inconsistency_check':
      return {
        descripcion: `Relación temporal ilógica: ${item.col1}=${item.val1} > ${item.col2}=${item.val2}`,
        sugerencia: sug,
        fila: row,
        columna: `${item.col1} / ${item.col2}`,
        valor: `${item.col1}=${item.val1}, ${item.col2}=${item.val2}`,
      }

    case 'latency_check':
      return {
        descripcion: `Latencia de ${item.latency_h}h entre evento (${item.event}) e ingesta (${item.ingest})`,
        sugerencia: sug,
        fila: row,
        columna: null,
        valor: `${item.latency_h}h`,
      }

    case 'sequential_integrity_check':
      return {
        descripcion: item.message || `Salto en secuencia en columna '${item.column}'`,
        sugerencia: sug,
        fila: row,
        columna: item.column || null,
        valor: item.message || null,
      }

    case 'referential_integrity_check':
      return {
        descripcion: `Valor huérfano '${item.value}' en columna '${item.column}' no existe en '${item.missing_in}'`,
        sugerencia: sug,
        fila: row,
        columna: item.column || null,
        valor: item.value != null ? valStr(item.value) : null,
      }

    case 'row_completeness_check':
      return {
        descripcion: `Fila con solo ${item.completeness_pct}% de datos completos. Columnas vacías: ${(item.null_columns || []).slice(0, 5).join(', ')}`,
        sugerencia: sug,
        fila: row,
        columna: null,
        valor: `${item.completeness_pct}% completo`,
      }

    case 'multivariate_outlier_check':
      return {
        descripcion: item.values
          ? `Outlier multivariado: ${Object.entries(item.values).slice(0, 4).map(([k, v]) => `${k}=${v}`).join(', ')}`
          : 'Outlier multivariado detectado',
        sugerencia: sug,
        fila: row,
        columna: null,
        valor: item.values ? Object.entries(item.values).slice(0, 6).map(([k, v]) => `${k}: ${v}`).join(', ') : null,
      }

    case 'cross_consistency_check':
      return {
        descripcion: `Violación de consistencia: ${item.rule || ''}`,
        sugerencia: sug,
        fila: row,
        columna: item.rule || null,
        valor: null,
      }

    case 'functional_dependency_check':
      return {
        descripcion: `Dependencia funcional violada: ${item.determinant}=${item.value} → ${item.dependent}=${item.dep_values}`,
        sugerencia: sug,
        fila: row,
        columna: `${item.determinant} → ${item.dependent}`,
        valor: `${item.determinant}=${item.value}`,
      }

    case 'derived_column_check':
      return {
        descripcion: `Columna '${item.column}' no coincide: esperado=${item.expected}, actual=${item.actual} (dif: ${item.diff_pct}%)`,
        sugerencia: sug,
        fila: row,
        columna: item.column || null,
        valor: `actual=${item.actual}, esperado=${item.expected}`,
      }

    case 'fuzzy_name_match':
    case 'fuzzy_id_match':
    case 'similar_dob':
      return {
        descripcion: item.group_similarity
          ? `Posible duplicado (similitud: ${(item.group_similarity * 100).toFixed(0)}%)`
          : 'Posible duplicado de persona',
        sugerencia: sug,
        fila: row,
        columna: null,
        valor: item.values ? trunc(Object.entries(item.values).slice(0, 4).map(([k, v]) => `${k}=${v}`).join(', ')) : null,
      }

    case 'person_composite_similarity':
    case 'personas_similares':
      return {
        descripcion: item.group_info
          ? `Posible misma persona (score compuesto: ${(item.group_info.composite_score * 100).toFixed(0)}%, grupo de ${item.group_info.group_size})`
          : 'Posible misma persona detectada',
        sugerencia: sug,
        fila: row,
        columna: null,
        valor: item.values ? trunc(Object.entries(item.values).slice(0, 4).map(([k, v]) => `${k}=${v}`).join(', ')) : null,
      }

    default:
      if (item.error) {
        return { descripcion: `Error: ${item.error}`, sugerencia: sug, fila: row, columna: null, valor: null }
      }
      if (item.column && item.value != null) {
        return {
          descripcion: `Valor anómalo en columna '${item.column}': ${valStr(item.value)}`,
          sugerencia: sug,
          fila: row,
          columna: item.column || null,
          valor: valStr(item.value),
        }
      }
      if (item.column) {
        return {
          descripcion: `Problema en columna '${item.column}'`,
          sugerencia: sug,
          fila: row,
          columna: item.column || null,
          valor: null,
        }
      }
      if (item.message) {
        return { descripcion: item.message, sugerencia: sug, fila: row, columna: null, valor: null }
      }
      return {
        descripcion: 'Error de calidad de datos',
        sugerencia: sug,
        fila: row,
        columna: null,
        valor: null,
      }
  }
}

export function describeDetail(ruleName: string, item: Record<string, any>): string {
  switch (ruleName) {
    case 'null_check':
      return `Columna '${item.column}' — ${item.nulls} valores nulos (${item.pct}%)`
    case 'unique_check':
      if (item.columns) {
        return `Columnas [${item.columns.join(', ')}] — ${item.composite_duplicates} duplicados compuestos (${item.pct}%)`
      }
      return `Columna '${item.column}' — ${item.duplicates} duplicados (${item.pct}%), ${item.unique_values} valores únicos`
    case 'duplicate_check':
      return `${item.count} filas duplicadas exactas (${item.pct}%)`
    case 'range_check':
      return `Columna '${item.column}' — ${item.outliers} outliers (${item.pct}%), rango [${item.min}, ${item.max}], IQR bounds [${item.lower_bound}, ${item.upper_bound}]`
    case 'pattern_check':
      return `Columna '${item.column}' — patrón '${item.pattern}': ${item.failed} fallos de ${item.total} (${item.pct}%)`
    case 'cardinality_check':
      return `Columna '${item.column}' — ${item.issue}`
    case 'correlation_check':
      if (item.type === 'HIGH_CORRELATION') return `Correlación alta: ${item.column_x} ↔ ${item.column_y} = ${item.correlation}`
      if (item.type === 'HIGH_VIF') return `VIF alto en ${item.column}: ${item.vif}`
      return `${item.type}: ${item.column_x} / ${item.column_y}`
    case 'distribution_check':
      return `Columna '${item.column}' — flags: ${(item.flags || []).join(', ')}, skew=${item.skewness}, kurt=${item.kurtosis}`
    case 'type_check':
      return `Columna '${item.column}' — declarado=${item.declared_type}, inferido=${item.inferred_type}${item.expected_type ? `, esperado=${item.expected_type}` : ''}${item.mixed_types ? `, tipos mixtos: ${item.mixed_types.join(', ')}` : ''}`
    case 'email_check':
    case 'phone_check':
    case 'zip_code_check':
    case 'rfc_curp_check':
    case 'special_chars_check':
    case 'string_length_check':
    case 'trim_check':
    case 'case_consistency_check':
    case 'invalid_date_check':
    case 'date_range_check':
    case 'freshness_check':
    case 'missing_fk_check':
      return `Columna '${item.column}' — ${item.failed} fallos de ${item.total} (${item.pct}%)`
    case 'date_inconsistency_check':
      return `${item.column_pair} — ${item.failed} filas inconsistentes de ${item.total} (${item.pct}%)`
    case 'latency_check':
      return `${item.event_col} → ${item.ingest_col}: ${item.failed} fallos de ${item.total} (${item.pct}%), latencia máx=${item.max_latency_h}h, prom=${item.avg_latency_h}h`
    case 'volume_anomaly_check':
      return item.note || `Actual: ${item.actual_rows}, Esperado: ${item.expected_rows}, Desviación: ${item.deviation_pct}%`
    case 'sequential_integrity_check':
      return `Columna '${item.column}' — ${item.gaps} saltos entre ${item.from} y ${item.to}`
    case 'referential_integrity_check':
      return `${item.child_column} → ${item.parent_column}: ${item.orphans} huérfanos de ${item.total} (${item.pct}%)`
    case 'row_completeness_check':
      return `${item.sparse_rows} filas con <${item.min_completeness_pct}% completas de ${item.total_rows} (${item.sparse_pct}%), promedio ${item.avg_completeness_pct}%`
    case 'multivariate_outlier_check':
      return `${item.outliers} outliers multivariados de ${item.total_analyzed} (${item.pct}%)`
    case 'drift_check':
      return item.note || `Columna '${item.column}' — ${item.count} categorías nuevas de ${item.reference_count} referencia`
    case 'schema_evolution_check':
      return `+${(item.columns_added || []).length} añadidas, -${(item.columns_removed || []).length} eliminadas, ~${Object.keys(item.columns_type_changed || {}).length} cambios de tipo`
    case 'cross_consistency_check':
      return `${item.rule} — ${item.failed} violaciones de ${item.total} (${item.pct}%)`
    case 'functional_dependency_check':
      return `${item.determinant} → ${item.dependent}: ${item.failed} violaciones de ${item.total} (${item.pct}%)`
    case 'class_balance_check':
      return `Columna '${item.column}' — valor dominante '${item.top_value}': ${item.top_pct}%, ${item.unique_values} valores únicos`
    case 'boolean_bias_check':
      return `Columna '${item.column}' — sesgo hacia ${item.bias}: ${item.true_pct || item.false_pct}%`
    case 'derived_column_check':
      return `Columna '${item.column}' — ${item.failed} fallos de ${item.total} (${item.pct}%), desviación máx ${item.max_deviation_pct}%`
    case 'fuzzy_name_match':
    case 'fuzzy_id_match':
    case 'similar_dob':
      return `${item.total_groups || item.groups?.length || 0} grupos de registros similares`
    case 'person_composite_similarity':
      return `${item.total_groups} grupos, campos: ${(item.available_fields || []).join(', ')}, pesos: ${item.weights ? Object.entries(item.weights).map(([k, v]) => `${k}=${v}`).join(', ') : 'N/A'}`
    case 'personas_similares':
      return `${item.total_groups} grupos detectados (modo: ${item.mode || 'rápido'})`
    default:
      if (item.error) return `Error: ${item.error}`
      if (item.note) return item.note
      if (item.message) return item.message
      if (item.column) return `Columna '${item.column}' — ${item.failed || item.count || item.nulls || item.outliers || '?'} fallos`
      const keys = Object.keys(item)
      const parts = keys.filter(k => !['type', 'threshold'].includes(k)).map(k => `${k}=${item[k]}`)
      return parts.join(', ') || JSON.stringify(item)
  }
}
