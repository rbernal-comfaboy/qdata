export const RULE_DISPLAY_NAMES: Record<string, string> = {
  null_check: 'Campos vacíos',
  type_check: 'Tipo de dato incorrecto',
  unique_check: 'Valores repetidos',
  duplicate_check: 'Registros repetidos',
  range_check: 'Fuera de rango',
  pattern_check: 'Formato incorrecto',
  cardinality_check: 'Cardinalidad extraña',
  correlation_check: 'Columnas correlacionadas',
  distribution_check: 'Distribución anormal',
  email_check: 'Correos inválidos',
  special_chars_check: 'Caracteres extraños',
  string_length_check: 'Longitud incorrecta',
  trim_check: 'Espacios extras',
  case_consistency_check: 'Mayúsculas/minúsculas',
  phone_check: 'Teléfonos mal escritos',
  zip_code_check: 'Códigos postales incorrectos',
  rfc_curp_check: 'RFC/CURP incorrectos',
  cedula_valid: 'Cédulas inválidas',
  nit_valid: 'NIT inválidos',
  invalid_date_check: 'Fechas inválidas',
  date_range_check: 'Fechas fuera de rango',
  date_inconsistency_check: 'Fechas sin coherencia',
  freshness_check: 'Datos desactualizados',
  latency_check: 'Retraso en carga',
  volume_anomaly_check: 'Volumen anormal',
  sequential_integrity_check: 'Saltos en secuencia',
  missing_fk_check: 'FK faltantes',
  referential_integrity_check: 'Datos huérfanos',
  row_completeness_check: 'Filas incompletas',
  multivariate_outlier_check: 'Combinaciones extrañas',
  drift_check: 'Categorías nuevas',
  schema_evolution_check: 'Estructura cambiada',
  cross_consistency_check: 'Inconsistencias entre columnas',
  functional_dependency_check: 'Dependencias incumplidas',
  class_balance_check: 'Columna sin variación',
  boolean_bias_check: 'Columna sesgada',
  derived_column_check: 'Columna calculada incorrecta',
  fuzzy_name_match: 'Nombres similares',
  fuzzy_id_match: 'IDs similares',
  similar_dob: 'Fechas de nacimiento cercanas',
  person_composite_similarity: 'Personas duplicadas',
  personas_similares: 'Personas duplicadas',
  personas_similares_v2: 'Personas similares V2',
  personas_similares_v3: 'Personas similares V3',
  custom_sql_rule: 'Regla SQL personalizada',
  custom_python_rule: 'Regla Python personalizada',
}

export function displayName(ruleName: string): string {
  return RULE_DISPLAY_NAMES[ruleName] || ruleName
}

const EMAIL_COL_RE = /email|correo|e-?mail|mail|contacto/i

export function isEmailColumn(key: string): boolean {
  return EMAIL_COL_RE.test(key)
}

const DOC_NUM_RE = /numdoc|num.*doc|nudo|nuid|numeroidentif|nume.*ident|cod_terc|nide|nu.*terc|numero_documento|numerodocumento|num_doc|nrodoc|nro.*doc|doc.*num/i
const DOC_TYPE_RE = /tipodoc|tip.*doc|tido|tiid|tipoidentif|tip.*ident|tip_terc|tip.*terc|tip_codi|tip.*codi|tipo_documento|tipodocumento/i
const SECOND_NAME_RE = /segnom|seg.*nom|nom2|nombre2|segundo.*nom|seg.*nombre/i
const FIRST_NAME_RE = /prinom|pri.*nom|nom1|nombre1|primer.*nom|primero.*nom|nombusua|nom_terc|clie_noma|first.*nom|nomb|nombre/i
const SECOND_SURNAME_RE = /seg.*ape|ape2|clie_ape2|apellido2|seg.*apellido|ape.*2/i
const FIRST_SURNAME_RE = /priape|pri.*ape|ape1|clie_apel|primer.*ape|apellido1|apel|ape_terc|ape.*1/i

/** Ordered [doc_type, doc_num, first_name, second_name, first_surname, second_surname]
 * keys present in the record, or [] when no identity column is detected. */
export function identityColumns(record: Record<string, any>): string[] {
  const keys = Object.keys(record || {})
  const taken = new Set<string>()
  const pick = (re: RegExp): string | null => {
    for (const k of keys) {
      if (taken.has(k)) continue
      if (re.test(k)) {
        taken.add(k)
        return k
      }
    }
    return null
  }
  const slots = {
    doc_num: pick(DOC_NUM_RE),
    doc_type: pick(DOC_TYPE_RE),
    second_name: pick(SECOND_NAME_RE),
    first_name: pick(FIRST_NAME_RE),
    second_surname: pick(SECOND_SURNAME_RE),
    first_surname: pick(FIRST_SURNAME_RE),
  }
  return ['doc_type', 'doc_num', 'first_name', 'second_name', 'first_surname', 'second_surname']
    .map((k) => slots[k as keyof typeof slots])
    .filter(Boolean) as string[]
}

export function isEmptyEmail(v: any): boolean {
  if (v === null || v === undefined) return true
  if (typeof v === 'number' && Number.isNaN(v)) return true
  if (typeof v === 'string') {
    const s = v.trim().toLowerCase()
    return s === '' || s === 'nan' || s === 'none' || s === 'null' || s === 'nat'
  }
  return false
}

const PHONE_COL_RE = /tele|tel[^e]|celu|celular|mobile|phone|fijo|whatsapp|movil|ntel/i

export function isPhoneColumn(key: string): boolean {
  return PHONE_COL_RE.test(key)
}

export function isContactColumn(key: string): boolean {
  return isEmailColumn(key) || isPhoneColumn(key)
}

/** Contact keys of the requested kind (phone columns for phone projects,
 * email columns for email projects). Mirrors the backend _enrich_full_rows. */
export function contactKeysByMode(keys: string[], mode: 'phone' | 'email' | 'none'): string[] {
  if (mode === 'phone') return keys.filter((k) => isPhoneColumn(k))
  if (mode === 'email') return keys.filter((k) => isEmailColumn(k))
  return []
}

const NO_EMAIL_TEXT = 'No tiene ningun email'

const CC_REASONS: Record<string, string> = {
  longitud_invalida: 'debe tener 6, 7, 8 o 10 dígitos',
  letras_o_caracteres_no_numericos: 'solo debe contener dígitos',
  nuip_debe_iniciar_en_1: 'un NUIP de 10 dígitos debe iniciar en 1',
}

const NIT_REASONS: Record<string, string> = {
  caracteres_invalidos: 'contiene letras o caracteres no numéricos',
  formato_dv_invalido: 'el dígito de verificación debe ser un solo dígito después del guion',
  longitud_invalida: 'debe tener entre 6 y 10 dígitos',
  mas_de_11_digitos: 'supera los 11 dígitos',
  dv_incoherente: 'el dígito de verificación no coincide con el Módulo 11',
  vacio: 'está vacío',
}

const NIT_WARNINGS: Record<string, string> = {
  ceros_a_la_izquierda: 'tenía ceros a la izquierda (se eliminaron antes de validar)',
  longitud_elevada: 'tiene 11 dígitos (longitud excepcional de asignaciones especiales de la DIAN)',
}

export function severityDescription(failurePct: number, total: number, failed: number): string {
  if (failed === 0) return 'Sin errores'
  const per10 = total > 0 ? Math.round(failed / total * 10) : 0
  const level = failurePct >= 50 ? 'La mayoría' : failurePct >= 30 ? 'Muchos' : failurePct >= 10 ? 'Algunos' : 'Pocos'
  return `${level} errores (${per10} de cada 10 registros)`
}

export type ErrorInfo = {
  descripcion: string
  sugerencia: string
  que_hacer: string
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

const GLOSARIO: Record<string, string> = {
  null_check: 'Revisa si hay celdas vacías o sin información',
  type_check: 'Verifica que los datos tengan el formato correcto (texto, número, fecha)',
  unique_check: 'Busca valores repetidos en una columna que deberían ser únicos',
  duplicate_check: 'Detecta filas completas que están repetidas',
  range_check: 'Encuentra valores numéricos fuera del rango normal esperado',
  pattern_check: 'Revisa si los textos siguen un formato específico (como códigos)',
  cardinality_check: 'Analiza si hay muy pocos o demasiados valores distintos en una columna',
  correlation_check: 'Detecta columnas que están tan relacionadas que podrían sobrar',
  distribution_check: 'Revisa si los datos tienen una distribución anormal',
  email_check: 'Verifica que los correos electrónicos tengan formato válido',
  special_chars_check: 'Busca caracteres extraños o problemáticos en los textos',
  string_length_check: 'Revisa si la longitud de los textos está dentro del rango esperado',
  trim_check: 'Detecta espacios adicionales al inicio o final del texto',
  case_consistency_check: 'Revisa que los textos tengan una misma forma (mayúsculas/minúsculas)',
  phone_check: 'Verifica que los números telefónicos tengan un formato correcto',
  zip_code_check: 'Valida que los códigos postales tengan el formato adecuado',
  rfc_curp_check: 'Revisa que RFCs y CURPs cumplan con el formato oficial del SAT',
  cedula_valid: 'Verifica que los números de Cédula de Ciudadanía (CC) tengan el formato colombiano correcto (solo dígitos, 6, 7, 8 o 10 posiciones)',
  nit_valid: 'Valida que los NIT tengan el formato colombiano (base numérica de 6 a 10 dígitos, 11 solo en asignaciones excepcionales; se quitan ceros a la izquierda antes de validar) y que su dígito de verificación coincida con el Módulo 11 DIAN',
  invalid_date_check: 'Detecta fechas mal escritas o que no existen',
  date_range_check: 'Busca fechas fuera del período esperado',
  date_inconsistency_check: 'Verifica que las fechas tengan coherencia (ej: fin ≥ inicio)',
  freshness_check: 'Comprueba que los datos estén actualizados',
  latency_check: 'Mide el tiempo que tarda la información en estar disponible',
  volume_anomaly_check: 'Detecta si llegaron muchos más o muchos menos registros de lo normal',
  sequential_integrity_check: 'Revisa si hay números de folio o ID saltados',
  missing_fk_check: 'Busca valores que deberían existir en otra tabla pero no están',
  referential_integrity_check: 'Detecta datos huérfanos sin relación en otras tablas',
  row_completeness_check: 'Revisa si hay filas con demasiada información faltante',
  multivariate_outlier_check: 'Encuentra combinaciones extrañas de valores en varias columnas',
  drift_check: 'Detecta si aparecieron categorías nuevas no esperadas',
  schema_evolution_check: 'Revisa si la estructura de la tabla cambió con el tiempo',
  cross_consistency_check: 'Verifica reglas de negocio entre columnas relacionadas',
  functional_dependency_check: 'Revisa que un valor siempre corresponda a otro único valor',
  class_balance_check: 'Analiza si una columna tiene un solo valor repetido muchas veces',
  boolean_bias_check: 'Detecta si una columna de sí/no está muy desbalanceada',
  derived_column_check: 'Verifica que una columna calculada tenga el resultado correcto',
  fuzzy_name_match: 'Busca nombres muy parecidos que podrían ser la misma persona',
  fuzzy_id_match: 'Busca IDs muy parecidos que podrían ser errores de captura',
  similar_dob: 'Compara fechas de nacimiento cercanas para detectar duplicados',
  person_composite_similarity: 'Evalúa si dos registros podrían pertenecer a la misma persona',
  personas_similares: 'Evalúa si dos registros podrían pertenecer a la misma persona',
  personas_similares_v2: 'Compara las columnas que elijas con pesos configurables para detectar la misma persona registrada dos veces con pequeñas diferencias',
  personas_similares_v3: 'Reproduce el comportamiento original: compara identificación, nombre y apellido en modo profundo para detectar la misma persona registrada dos veces con pequeñas diferencias',
  custom_sql_rule: 'Aplica una regla personalizada escrita en SQL',
  custom_python_rule: 'Aplica una regla personalizada escrita en Python',
}

export function describeRuleSimple(ruleName: string): string {
  return GLOSARIO[ruleName] || 'Regla de validación de datos'
}

const QUE_HACER: Record<string, string> = {
  null_check: "Revisa los registros marcados y completa la información. Si no tienes el dato, escribe 'No disponible' o un valor por omisión.",
  type_check: "Corrige el formato del dato. Por ejemplo, si es una fecha debe ser '2024-01-01' y no 'ene-2024'.",
  unique_check: 'Revisa si los valores repetidos son válidos. Si no deberían estar duplicados, elimina los sobrantes.',
  duplicate_check: 'Verifica si las filas repetidas son errores y elimina las copias innecesarias.',
  range_check: 'Revisa si el valor fuera de rango es real o fue capturado incorrectamente.',
  pattern_check: 'Aplica un formato estándar. Por ejemplo, un código postal debe tener 5 dígitos.',
  cardinality_check: 'Evalúa si esta columna realmente sirve. Si casi todos los valores son iguales, quizás puedes omitirla.',
  correlation_check: 'Si dos columnas están muy relacionadas, una de las dos podría no ser necesaria.',
  distribution_check: 'Revisa si los datos sesgados podrían transformarse (ej: usar logaritmo) para mejor análisis.',
  email_check: "Corrige la dirección de correo: debe tener formato 'usuario@dominio.com'.",
  special_chars_check: 'Limpia los caracteres extraños usando herramientas de limpieza de texto.',
  string_length_check: 'Ajusta el texto al largo esperado. Si es muy largo, recorta; si es muy corto, verifica que esté completo.',
  trim_check: 'Elimina los espacios de más al inicio y final del texto con una función de limpieza.',
  case_consistency_check: 'Unifica todo a mayúsculas o minúsculas según el estándar que uses.',
  phone_check: 'Estandariza los teléfonos al formato nacional. En Colombia debe ser +57 y 10 dígitos.',
  zip_code_check: 'Corrige el código postal: en México son 5 dígitos, en EE.UU. son 5 o 9 dígitos.',
  rfc_curp_check: 'Verifica que el RFC tenga 13 caracteres y la CURP 18, con el formato oficial del SAT.',
  cedula_valid: 'Verifica el número de cédula en la fuente oficial: solo dígitos, con 6, 7, 8 o 10 posiciones (el NUIP de 10 dígitos inicia en 1). Corrige el valor en el sistema de origen.',
  nit_valid: 'Verifica el NIT contra el certificado de la DIAN o el RUT/RUES. Corrige el número o el dígito de verificación en el sistema de origen. Se recomienda además contrastar contra la DIAN/RUES para confirmar que el NIT existe y está activo.',
  invalid_date_check: "Corrige las fechas al formato AAAA-MM-DD. Por ejemplo, '2024/01/15' → '2024-01-15'.",
  date_range_check: 'Revisa si la fecha fuera de rango es correcta o fue un error de captura.',
  date_inconsistency_check: 'Asegúrate de que la fecha de inicio sea anterior o igual a la fecha de fin.',
  freshness_check: 'Verifica que los datos se estén actualizando correctamente y a tiempo.',
  latency_check: 'Revisa el proceso de carga de datos para que la información llegue más rápido.',
  volume_anomaly_check: 'Investiga por qué la cantidad de registros subió o bajó tanto. Revisa la fuente de datos.',
  sequential_integrity_check: 'Revisa si faltan registros intermedios. Si el consecutivo se reinicia, confirma que sea intencional.',
  missing_fk_check: 'Revisa la tabla donde deberían estar esos valores faltantes y completa los datos.',
  referential_integrity_check: 'Los datos huérfanos no tienen referencia en otra tabla. Hay que agregar los registros padre faltantes.',
  row_completeness_check: 'Completa la información faltante de estas filas o considera si son datos que ya no sirven.',
  multivariate_outlier_check: 'Revisa estas combinaciones de valores. Si son datos reales, mantenlos; si son errores, corrígelos.',
  drift_check: 'Verifica si las categorías nuevas son válidas o si llegaron por error en la carga de datos.',
  schema_evolution_check: 'Si la tabla cambió de estructura, actualiza las reglas de validación para que coincidan.',
  cross_consistency_check: "Revisa la relación entre las columnas. Por ejemplo, si 'total = precio × cantidad' debe cumplirse.",
  functional_dependency_check: 'Un valor debe corresponder a un solo resultado. Corrige los casos que no cumplan esta regla.',
  class_balance_check: 'Si una columna tiene siempre el mismo valor, quizás puedes omitirla del análisis.',
  boolean_bias_check: "Una columna de sí/no con 99% de 'sí' probablemente no aporta información útil.",
  derived_column_check: 'Revisa la fórmula de la columna calculada. Puede tener un error en la cuenta.',
  fuzzy_name_match: 'Compara los nombres similares manualmente para decidir si son la misma persona.',
  fuzzy_id_match: 'Revisa si los IDs parecidos son errores de dedo al capturar o personas distintas.',
  similar_dob: 'Compara estos registros manualmente. Fechas muy cercanas pueden indicar duplicados.',
  person_composite_similarity: 'Revisa los grupos marcados: podrían ser registros duplicados de una misma persona.',
  personas_similares: 'Revisa los grupos marcados: podrían ser registros duplicados de una misma persona.',
  personas_similares_v2: 'Revisa los grupos marcados: podrían ser la misma persona registrada dos veces con pequeñas diferencias.',
  personas_similares_v3: 'Revisa los grupos marcados: podrían ser la misma persona registrada dos veces con pequeñas diferencias.',
  custom_sql_rule: 'Revisa los registros que no pasaron tu regla SQL personalizada. Ajusta los datos o la regla.',
  custom_python_rule: 'Revisa los registros que no pasaron tu regla Python personalizada.',
}

export function getQueHacer(ruleName: string): string {
  return QUE_HACER[ruleName] || 'Revisa este registro en la fuente de datos original'
}

export function getSugerencia(ruleName: string): string {
  return SUGERENCIAS[ruleName] || 'Revisa el valor en la fuente de datos'
}

const SUGERENCIAS: Record<string, string> = {
  null_check: "Completa los datos faltantes o asígnales un valor como 'No especificado'",
  type_check: 'Convierte los datos al formato correcto (número, fecha, texto)',
  unique_check: 'Elimina los valores repetidos o revisa si deben ser únicos',
  duplicate_check: 'Elimina las filas duplicadas',
  range_check: 'Verifica si el valor es real o un error de captura',
  pattern_check: 'Estandariza el formato con una función de limpieza',
  cardinality_check: 'Evalúa si la columna realmente aporta información útil',
  correlation_check: 'Considera eliminar una de las dos columnas o reducir dimensiones',
  distribution_check: 'Aplica una transformación (logaritmo) para mejorar el análisis',
  email_check: 'Corrige el correo: usuario@dominio.com',
  special_chars_check: 'Limpia caracteres extraños del texto',
  string_length_check: 'Ajusta el texto al largo esperado',
  trim_check: 'Quita espacios de más al inicio y final',
  case_consistency_check: 'Unifica mayúsculas/minúsculas',
  phone_check: 'Estandariza los teléfonos al formato nacional',
  zip_code_check: 'Corrige el código postal al formato de 5 dígitos',
  rfc_curp_check: 'Verifica el formato contra el estándar del SAT',
  cedula_valid: 'Corrige el número de cédula en el sistema de origen (solo dígitos, 6-8 o 10 posiciones)',
  nit_valid: 'Corrige el NIT o su dígito de verificación en el sistema de origen; contrasta contra la DIAN/RUES para confirmar existencia',
  invalid_date_check: 'Corrige las fechas al formato AAAA-MM-DD',
  date_range_check: 'Revisa fechas fuera del período esperado',
  date_inconsistency_check: 'Asegura que fecha_inicio ≤ fecha_fin',
  freshness_check: 'Verifica que los datos estén actualizados',
  latency_check: 'Revisa la velocidad de carga de los datos',
  volume_anomaly_check: 'Investiga cambios en el volumen de registros',
  sequential_integrity_check: 'Revisa si faltan registros en la secuencia',
  missing_fk_check: 'Completa los valores faltantes en la tabla relacionada',
  referential_integrity_check: 'Agrega los registros padre que faltan',
  row_completeness_check: 'Completa filas con datos faltantes',
  multivariate_outlier_check: 'Revisa combinaciones de valores anómalos',
  drift_check: 'Verifica si las categorías nuevas son válidas',
  schema_evolution_check: 'Actualiza la validación al nuevo esquema',
  cross_consistency_check: 'Revisa las relaciones entre columnas',
  functional_dependency_check: 'Corrige valores que no cumplen la dependencia funcional',
  class_balance_check: 'Evalúa si columnas con un solo valor aportan información',
  boolean_bias_check: 'Considera si columnas sesgadas son útiles',
  derived_column_check: 'Revisa la fórmula de la columna calculada',
  fuzzy_name_match: 'Compara manualmente los nombres similares',
  fuzzy_id_match: 'Revisa si los IDs parecidos son errores de captura',
  similar_dob: 'Compara estos registros para detectar duplicados',
  person_composite_similarity: 'Revisa los grupos de posibles duplicados',
  personas_similares: 'Revisa los grupos de personas similares — pueden ser duplicados',
  personas_similares_v2: 'Revisa los grupos de personas similares V2 — pueden ser duplicados con pequeñas diferencias',
  personas_similares_v3: 'Revisa los grupos de personas similares V3 — pueden ser duplicados con pequeñas diferencias',
  custom_sql_rule: 'Revisa los registros que no cumplen tu regla SQL',
  custom_python_rule: 'Revisa los registros que no pasan tu validación',
}

export function describeError(ruleName: string, item: Record<string, any>, recommendation?: string): ErrorInfo {
  const row = item.row != null ? Number(item.row) + 2 : null
  const sug = recommendation || getSugerencia(ruleName)
  const qh = getQueHacer(ruleName)

  switch (ruleName) {
    case 'null_check':
      return {
        descripcion: `La columna '${item.column}' tiene un valor vacío`,
        sugerencia: sug,
        que_hacer: qh,
        fila: row,
        columna: item.column || null,
        valor: null,
      }

    case 'type_check':
      return {
        descripcion: `La columna '${item.column}' tiene un dato de tipo incorrecto${item.sample_value ? ` (ej: '${item.sample_value}')` : ''}`,
        sugerencia: sug,
        que_hacer: qh,
        fila: row,
        columna: item.column || null,
        valor: item.sample_value ? valStr(item.sample_value) : null,
      }

    case 'unique_check':
      return {
        descripcion: `El valor '${item.value}' está repetido en la columna '${item.column}'`,
        sugerencia: sug,
        que_hacer: qh,
        fila: row,
        columna: item.column || null,
        valor: item.value != null ? valStr(item.value) : null,
      }

    case 'duplicate_check': {
      if ((item.rows?.length ?? 0) > 0) {
        const rows = item.rows || []
        const count = item.size || rows.length
        const rowNums = rows.map((r: any) => r.row != null ? Number(r.row) + 2 : null).filter((r: any) => r !== null)
        const displayRows = rowNums.length <= 5
          ? rowNums.join(', ')
          : `${rowNums[0]}, ${rowNums[1]}, … (+${rowNums.length - 2} más)`
        const first = rows[0]
        const entries = Object.entries(first?.values || {})
        const emailEntry = entries.find(([k]) => isEmailColumn(k))
        const ordered: string[] = emailEntry
          ? [emailEntry[0], ...entries.filter(([e]) => e[0] !== emailEntry[0]).map(([e]) => e[0])]
          : entries.map(([e]) => e[0])
        const colsText = ordered.slice(0, 3).map((k) => {
          const v = entries.find(([e]) => e[0] === k)?.[1]
          return isEmailColumn(k) && isEmptyEmail(v) ? `${k}=${NO_EMAIL_TEXT}` : `${k}=${v}`
        }).join(', ')
        const valor = emailEntry
          ? `${emailEntry[0]}: ${isEmptyEmail(emailEntry[1]) ? NO_EMAIL_TEXT : emailEntry[1]}`
          : (entries.slice(0, 5).map(([k, v]) => `${k}: ${v}`).join(', ') || null)
        return {
          descripcion: `Filas repetidas (${count} en total): ${colsText}`,
          sugerencia: sug,
          que_hacer: qh,
          fila: displayRows || null,
          columna: null,
          valor,
        }
      }
      // Per-row entry (new format): values are identity + contact columns.
      const entries = Object.entries(item.values || {})
      const contactEntry = entries.find(([k]) => isContactColumn(k))
      const identEntries = entries.filter(([k]) => !isContactColumn(k))
      const colsText = identEntries.slice(0, 4).map(([k, v]) => `${k}=${v ?? '—'}`).join(', ')
      const valor = contactEntry
        ? isEmailColumn(contactEntry[0])
          ? `${contactEntry[0]}: ${isEmptyEmail(contactEntry[1]) ? NO_EMAIL_TEXT : contactEntry[1]}`
          : `${contactEntry[0]}: ${contactEntry[1] ?? '—'}`
        : (entries.slice(0, 5).map(([k, v]) => `${k}: ${v}`).join(', ') || null)
      const groupSize = item.group_size ?? item.size ?? 1
      return {
        descripcion: `Fila duplicada (grupo de ${groupSize} filas repetidas)${colsText ? ': ' + colsText : ''}`,
        sugerencia: sug,
        que_hacer: qh,
        fila: row,
        columna: null,
        valor,
      }
    }

    case 'range_check':
      return {
        descripcion: `El valor '${item.value}' está fuera del rango normal en la columna '${item.column}'`,
        sugerencia: sug,
        que_hacer: qh,
        fila: row,
        columna: item.column || null,
        valor: item.value != null ? valStr(item.value) : null,
      }

    case 'pattern_check':
      return {
        descripcion: `El valor '${item.value}' no tiene el formato esperado en la columna '${item.column}'`,
        sugerencia: sug,
        que_hacer: qh,
        fila: row,
        columna: item.column || null,
        valor: item.value != null ? valStr(item.value) : null,
      }

    case 'cardinality_check':
      return {
        descripcion: `La columna '${item.column}' tiene valores extraños: ${item.warning || ''}`,
        sugerencia: sug,
        que_hacer: qh,
        fila: row,
        columna: item.column || null,
        valor: item.warning || null,
      }

    case 'correlation_check':
      return {
        descripcion: `Hay una correlación alta (${item.correlation}) entre las columnas: ${item.columns || ''}`,
        sugerencia: sug,
        que_hacer: qh,
        fila: null,
        columna: item.columns || null,
        valor: item.correlation != null ? valStr(item.correlation) : null,
      }

    case 'distribution_check':
      return {
        descripcion: `La columna '${item.column}' tiene una distribución anormal: ${(item.flags || []).join(', ')}`,
        sugerencia: sug,
        que_hacer: qh,
        fila: row,
        columna: item.column || null,
        valor: (item.flags || []).join(', '),
      }

    case 'email_check':
      return {
        descripcion: isEmptyEmail(item.value)
          ? `En la columna '${item.column}', el correo no tiene ningún valor`
          : `En la columna '${item.column}', el valor '${item.value}' no es un email válido`,
        sugerencia: sug,
        que_hacer: qh,
        fila: row,
        columna: item.column || null,
        valor: isEmptyEmail(item.value) ? NO_EMAIL_TEXT : (item.value != null ? valStr(item.value) : null),
      }

    case 'cedula_valid':
      return {
        descripcion: `En la columna '${item.column}', el valor '${item.value}' no es una Cédula de Ciudadanía válida${item.reason ? ` (${CC_REASONS[item.reason] || item.reason})` : ''}`,
        sugerencia: sug,
        que_hacer: qh,
        fila: row,
        columna: item.column || null,
        valor: item.value != null ? valStr(item.value) : null,
      }

    case 'nit_valid': {
      const dvInfo = item.reason === 'dv_incoherente' && item.expected != null && item.observed != null
        ? ` (esperado ${item.expected}, registrado ${item.observed})`
        : (item.reason ? ` (${NIT_REASONS[item.reason] || item.reason})` : '')
      const warnInfo = item.warning?.length
        ? ` Además: ${item.warning.map((w: string) => NIT_WARNINGS[w] || w).join('; ')}`
        : ''
      return {
        descripcion: `En la columna '${item.column}', el valor '${item.value}' no es un NIT válido${dvInfo}${warnInfo}`,
        sugerencia: sug,
        que_hacer: qh,
        fila: row,
        columna: item.column || null,
        valor: item.value != null ? valStr(item.value) : null,
      }
    }

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
        descripcion: `${item.column ? `En la columna '${item.column}', el valor '${item.value}' no es válido` : 'Valor inválido'}`,
        sugerencia: sug,
        que_hacer: qh,
        fila: row,
        columna: item.column || null,
        valor: item.value != null ? valStr(item.value) : null,
      }

    case 'date_inconsistency_check':
      return {
        descripcion: `Relación de fechas incorrecta: ${item.col1}=${item.val1} es después de ${item.col2}=${item.val2}`,
        sugerencia: sug,
        que_hacer: qh,
        fila: row,
        columna: `${item.col1} / ${item.col2}`,
        valor: `${item.col1}=${item.val1}, ${item.col2}=${item.val2}`,
      }

    case 'latency_check':
      return {
        descripcion: `Retraso de ${item.latency_h}h entre el evento (${item.event}) y la carga (${item.ingest})`,
        sugerencia: sug,
        que_hacer: qh,
        fila: row,
        columna: null,
        valor: `${item.latency_h}h`,
      }

    case 'sequential_integrity_check':
      return {
        descripcion: item.message || `Hay un salto en la secuencia de la columna '${item.column}'`,
        sugerencia: sug,
        que_hacer: qh,
        fila: row,
        columna: item.column || null,
        valor: item.message || null,
      }

    case 'referential_integrity_check':
      return {
        descripcion: `El valor '${item.value}' en la columna '${item.column}' no existe en la tabla '${item.missing_in}'`,
        sugerencia: sug,
        que_hacer: qh,
        fila: row,
        columna: item.column || null,
        valor: item.value != null ? valStr(item.value) : null,
      }

    case 'row_completeness_check':
      return {
        descripcion: `Esta fila solo tiene el ${item.completeness_pct}% de datos completos. Columnas vacías: ${(item.null_columns || []).slice(0, 5).join(', ')}`,
        sugerencia: sug,
        que_hacer: qh,
        fila: row,
        columna: null,
        valor: `${item.completeness_pct}% completo`,
      }

    case 'multivariate_outlier_check':
      return {
        descripcion: item.values
          ? `Combinación extraña de valores: ${Object.entries(item.values).slice(0, 4).map(([k, v]) => `${k}=${v}`).join(', ')}`
          : 'Se encontró una combinación extraña de valores en varias columnas',
        sugerencia: sug,
        que_hacer: qh,
        fila: row,
        columna: null,
        valor: item.values ? Object.entries(item.values).slice(0, 6).map(([k, v]) => `${k}: ${v}`).join(', ') : null,
      }

    case 'cross_consistency_check':
      return {
        descripcion: `No se cumple la regla interna: ${item.rule || ''}`,
        sugerencia: sug,
        que_hacer: qh,
        fila: row,
        columna: item.rule || null,
        valor: null,
      }

    case 'functional_dependency_check':
      return {
        descripcion: `Dependencia incumplida: ${item.determinant}=${item.value} debería corresponder a ${item.dependent}=${item.dep_values}`,
        sugerencia: sug,
        que_hacer: qh,
        fila: row,
        columna: `${item.determinant} → ${item.dependent}`,
        valor: `${item.determinant}=${item.value}`,
      }

    case 'derived_column_check':
      return {
        descripcion: `La columna '${item.column}' tiene un resultado incorrecto: se esperaba ${item.expected} pero se obtuvo ${item.actual} (diferencia: ${item.diff_pct}%)`,
        sugerencia: sug,
        que_hacer: qh,
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
        que_hacer: qh,
        fila: row,
        columna: null,
        valor: item.values ? trunc(Object.entries(item.values).slice(0, 4).map(([k, v]) => `${k}=${v}`).join(', ')) : null,
      }

    case 'person_composite_similarity':
    case 'personas_similares':
    case 'personas_similares_v2':
    case 'personas_similares_v3':
      return {
        descripcion: item.group_info
          ? `Posible misma persona (confianza: ${(item.group_info.composite_score * 100).toFixed(0)}%, grupo de ${item.group_info.group_size})`
          : 'Posible misma persona detectada',
        sugerencia: sug,
        que_hacer: qh,
        fila: row,
        columna: null,
        valor: item.values ? trunc(Object.entries(item.values).slice(0, 4).map(([k, v]) => `${k}=${v}`).join(', ')) : null,
      }

    default:
      if (item.error) {
        return { descripcion: `Error: ${item.error}`, sugerencia: sug, que_hacer: qh, fila: row, columna: null, valor: null }
      }
      if (item.column && item.value != null) {
        return {
          descripcion: `Valor anómalo en columna '${item.column}': ${valStr(item.value)}`,
          sugerencia: sug,
          que_hacer: qh,
          fila: row,
          columna: item.column || null,
          valor: valStr(item.value),
        }
      }
      if (item.column) {
        return {
          descripcion: `Problema en columna '${item.column}'`,
          sugerencia: sug,
          que_hacer: qh,
          fila: row,
          columna: item.column || null,
          valor: null,
        }
      }
      if (item.message) {
        return { descripcion: item.message, sugerencia: sug, que_hacer: qh, fila: row, columna: null, valor: null }
      }
      return {
        descripcion: 'Error de calidad de datos',
        sugerencia: sug,
        que_hacer: qh,
        fila: row,
        columna: null,
        valor: null,
      }
  }
}

export function describeDetail(ruleName: string, item: Record<string, any>): string {
  switch (ruleName) {
    case 'null_check':
      return `Columna '${item.column}' tiene ${item.nulls} celdas vacías (${item.pct}%)`
    case 'unique_check':
      if (item.columns) {
        return `Columnas [${item.columns.join(', ')}] — ${item.composite_duplicates} combinaciones repetidas (${item.pct}%)`
      }
      return `Columna '${item.column}' — ${item.duplicates} valores repetidos (${item.pct}%), ${item.unique_values} valores distintos`
    case 'duplicate_check':
      if (item.type === 'duplicate_groups') {
        const groups = item.groups || []
        const shown = groups.reduce((s: number, g: any) => s + (g.rows?.length || 0), 0)
        return `${groups.length} grupos de filas repetidas (${shown} filas mostradas)`
      }
      return `${item.count} filas completas repetidas (${item.pct}%)`
    case 'range_check':
      return `Columna '${item.column}' — ${item.outliers} valores fuera de rango (${item.pct}%), rango normal [${item.min}, ${item.max}]`
    case 'pattern_check':
      return `Columna '${item.column}' — patrón '${item.pattern}': ${item.failed} fallos de ${item.total} (${item.pct}%)`
    case 'cardinality_check':
      return `Columna '${item.column}' — ${item.issue}`
    case 'correlation_check':
      if (item.type === 'HIGH_CORRELATION') return `Correlación alta entre ${item.column_x} y ${item.column_y}: ${item.correlation}`
      if (item.type === 'HIGH_VIF') return `La columna ${item.column} está muy relacionada con otras: VIF=${item.vif}`
      return `${item.type}: ${item.column_x} / ${item.column_y}`
    case 'distribution_check':
      return `Columna '${item.column}' — distribución anormal: ${(item.flags || []).join(', ')}, sesgo=${item.skewness}, curtosis=${item.kurtosis}`
    case 'type_check':
      return `Columna '${item.column}' — se declaró como ${item.declared_type} pero parece ${item.inferred_type}${item.expected_type ? `, se esperaba ${item.expected_type}` : ''}${item.mixed_types ? `, tipos mezclados: ${item.mixed_types.join(', ')}` : ''}`
    case 'email_check':
    case 'phone_check':
    case 'zip_code_check':
    case 'rfc_curp_check':
    case 'cedula_valid':
    case 'nit_valid':
    case 'special_chars_check':
    case 'string_length_check':
    case 'trim_check':
    case 'case_consistency_check':
    case 'invalid_date_check':
    case 'date_range_check':
    case 'freshness_check':
    case 'missing_fk_check':
      return `Columna '${item.column}' — ${item.failed} valores incorrectos de ${item.total} (${item.pct}%)`
    case 'date_inconsistency_check':
      return `${item.column_pair} — ${item.failed} fechas sin coherencia de ${item.total} (${item.pct}%)`
    case 'latency_check':
      return `${item.event_col} → ${item.ingest_col}: ${item.failed} retrasos de ${item.total} (${item.pct}%), retraso máximo ${item.max_latency_h}h, promedio ${item.avg_latency_h}h`
    case 'volume_anomaly_check':
      return item.note || `Registros actuales: ${item.actual_rows}, esperados: ${item.expected_rows}, desviación: ${item.deviation_pct}%`
    case 'sequential_integrity_check':
      return `Columna '${item.column}' — ${item.gaps} saltos en la secuencia entre ${item.from} y ${item.to}`
    case 'referential_integrity_check':
      return `${item.child_column} → ${item.parent_column}: ${item.orphans} valores huérfanos de ${item.total} (${item.pct}%)`
    case 'row_completeness_check':
      return `${item.sparse_rows} filas con menos del ${item.min_completeness_pct}% de datos completos de ${item.total_rows} (${item.sparse_pct}%), promedio de completitud ${item.avg_completeness_pct}%`
    case 'multivariate_outlier_check':
      return `${item.outliers} combinaciones extrañas de valores de ${item.total_analyzed} (${item.pct}%)`
    case 'drift_check':
      return item.note || `Columna '${item.column}' — ${item.count} categorías nuevas no esperadas (referencia: ${item.reference_count})`
    case 'schema_evolution_check':
      return `La tabla cambió: +${(item.columns_added || []).length} columnas añadidas, -${(item.columns_removed || []).length} eliminadas, ~${Object.keys(item.columns_type_changed || {}).length} cambios de tipo`
    case 'cross_consistency_check':
      return `${item.rule} — ${item.failed} violaciones de ${item.total} (${item.pct}%)`
    case 'functional_dependency_check':
      return `${item.determinant} → ${item.dependent}: ${item.failed} casos donde no se cumple de ${item.total} (${item.pct}%)`
    case 'class_balance_check':
      return `Columna '${item.column}' — el valor '${item.top_value}' domina con ${item.top_pct}%, ${item.unique_values} valores distintos`
    case 'boolean_bias_check':
      return `Columna '${item.column}' — está muy cargada hacia '${item.bias}': ${item.true_pct || item.false_pct}%`
    case 'derived_column_check':
      return `Columna '${item.column}' — ${item.failed} resultados incorrectos de ${item.total} (${item.pct}%), desviación máxima ${item.max_deviation_pct}%`
    case 'fuzzy_name_match':
    case 'fuzzy_id_match':
    case 'similar_dob':
      return `${item.total_groups || item.groups?.length || 0} grupos de registros con posibles duplicados`
    case 'person_composite_similarity':
      return `${item.total_groups} grupos posibles duplicados, campos: ${(item.available_fields || []).join(', ')}, pesos: ${item.weights ? Object.entries(item.weights).map(([k, v]) => `${k}=${v}`).join(', ') : 'N/A'}`
    case 'personas_similares':
      return `${item.total_groups} grupos posibles duplicados (modo: ${item.mode || 'rápido'})`
    case 'personas_similares_v2':
      return `${item.total_groups} grupos posibles duplicados (modo: ${item.mode || 'rápido'}, campos: ${item.columns || 'N/A'})`
    case 'personas_similares_v3':
      return `${item.total_groups} grupos posibles duplicados (modo: ${item.mode || 'profundo'}, campos: ${item.columns || 'N/A'})`
    default:
      if (item.error) return `Error: ${item.error}`
      if (item.note) return item.note
      if (item.message) return item.message
      if (item.column) return `Columna '${item.column}' — ${item.failed || item.count || item.nulls || item.outliers || '?'} problemas`
      const keys = Object.keys(item)
      const parts = keys.filter(k => !['type', 'threshold'].includes(k)).map(k => `${k}=${item[k]}`)
      return parts.join(', ') || JSON.stringify(item)
  }
}
