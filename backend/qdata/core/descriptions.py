from typing import Any

SUGERENCIAS: dict[str, str] = {
    "null_check": "Rellenar con valor por defecto o imputar con media/mediana/moda",
    "type_check": "Convertir al tipo de dato correcto con pd.to_datetime() o pd.to_numeric()",
    "unique_check": "Eliminar duplicados o revisar lógica de clave primaria",
    "duplicate_check": "Eliminar filas duplicadas exactas",
    "range_check": "Verificar si es error de captura o outlier legítimo",
    "pattern_check": "Estandarizar el formato con regex o librerías de validación",
    "cardinality_check": "Evaluar si la columna aporta información útil",
    "correlation_check": "Considerar eliminar variables correlacionadas o usar PCA",
    "distribution_check": "Aplicar transformación logarítmica o Box-Cox",
    "email_check": "Corregir formato de email: usuario@dominio.tld",
    "special_chars_check": "Limpiar caracteres de control y zero-width Unicode",
    "string_length_check": "Ajustar longitud al rango esperado",
    "trim_check": "Aplicar .trim() para eliminar espacios extras",
    "case_consistency_check": "Uniformar a mayúsculas o minúsculas según el estándar",
    "phone_check": "Estandarizar formato telefónico: +52 (MX) o +1 (US) con 10 dígitos",
    "zip_code_check": "Corregir código postal: MX=5 dígitos, US=5 o 9 dígitos",
    "rfc_curp_check": "Corregir RFC (13 chars) o CURP (18 chars) según formato SAT",
    "invalid_date_check": "Corregir fechas mal formadas (usar YYYY-MM-DD)",
    "date_range_check": "Revisar fechas fuera del rango esperado",
    "date_inconsistency_check": "Verificar que fecha_inicio <= fecha_fin",
    "freshness_check": "Verificar frescura de la fuente de datos",
    "latency_check": "Revisar pipeline de ingesta para reducir latencia",
    "volume_anomaly_check": "Validar el volumen de registros contra lo esperado",
    "sequential_integrity_check": "Revisar eliminaciones o fallos en generación de IDs",
    "missing_fk_check": "Verificar integridad referencial de llaves foráneas",
    "referential_integrity_check": "Valores huérfanos sin correspondencia en tabla padre",
    "row_completeness_check": "Completar filas con datos faltantes o imputar valores",
    "multivariate_outlier_check": "Revisar combinaciones anómalas de variables",
    "drift_check": "Investigar si las categorías nuevas son datos válidos",
    "schema_evolution_check": "Revisar compatibilidad del esquema actual vs referencia",
    "cross_consistency_check": "Revisar relaciones aritméticas y lógicas entre columnas",
    "functional_dependency_check": "Un valor del determinante debe corresponder a un único valor del dependiente",
    "class_balance_check": "Evaluar si columnas con un solo valor aportan información",
    "boolean_bias_check": "Considerar si columnas extremadamente sesgadas son útiles",
    "derived_column_check": "Verificar la fórmula de cálculo de la columna derivada",
    "fuzzy_name_match": "Revisar nombres similares que podrían ser la misma persona",
    "fuzzy_id_match": "Revisar IDs similares que podrían ser errores de digitación",
    "similar_dob": "Revisar fechas cercanas del mismo registro duplicado",
    "person_composite_similarity": "Revisar grupos detectados como posible misma persona",
    "custom_sql_rule": "Revisar registros que no cumplen la regla SQL personalizada",
    "custom_python_rule": "Revisar registros que no pasan la validación personalizada",
}


def _safe_str(v: Any) -> str:
    if v is None:
        return "—"
    return str(v)


def describe_error(rule_name: str, item: dict, recommendation: str | None = None) -> dict:
    row = item.get("row")
    fila = row + 2 if row is not None else None
    sug = recommendation or SUGERENCIAS.get(rule_name, "Revisar el valor en la fuente de datos")

    if rule_name == "null_check":
        return {
            "descripcion": f"Valor nulo o vacío en columna '{item.get('column')}'",
            "sugerencia": sug,
            "fila": fila,
            "columna": item.get("column"),
            "valor": None,
        }

    if rule_name == "type_check":
        col = item.get("column", "")
        sv = item.get("sample_value")
        desc = f"Tipo de dato inesperado en columna '{col}'"
        if sv:
            desc += f" (ej: {sv})"
        return {"descripcion": desc, "sugerencia": sug, "fila": fila, "columna": col, "valor": _safe_str(sv) if sv else None}

    if rule_name == "unique_check":
        return {
            "descripcion": f"Valor duplicado en columna '{item.get('column')}'",
            "sugerencia": sug,
            "fila": fila,
            "columna": item.get("column"),
            "valor": _safe_str(item.get("value")),
        }

    if rule_name == "duplicate_check":
        vals = item.get("values")
        if vals:
            parts = [f"{k}={v}" for k, v in list(vals.items())[:4]]
            desc = "Fila duplicada: " + ", ".join(parts)
            val = ", ".join(f"{k}: {v}" for k, v in list(vals.items())[:6])
        else:
            desc = "Fila duplicada"
            val = None
        return {"descripcion": desc, "sugerencia": sug, "fila": fila, "columna": None, "valor": val}

    if rule_name == "range_check":
        return {
            "descripcion": f"Valor fuera de rango en columna '{item.get('column')}': {_safe_str(item.get('value'))}",
            "sugerencia": sug,
            "fila": fila,
            "columna": item.get("column"),
            "valor": _safe_str(item.get("value")),
        }

    if rule_name in ("email_check", "phone_check", "zip_code_check", "rfc_curp_check",
                     "special_chars_check", "string_length_check", "trim_check",
                     "case_consistency_check", "invalid_date_check", "date_range_check",
                     "freshness_check", "missing_fk_check"):
        return {
            "descripcion": f"En columna '{item.get('column')}' valor inválido: {_safe_str(item.get('value'))}",
            "sugerencia": sug,
            "fila": fila,
            "columna": item.get("column"),
            "valor": _safe_str(item.get("value")),
        }

    if rule_name == "pattern_check":
        return {
            "descripcion": f"Formato inválido en columna '{item.get('column')}': {_safe_str(item.get('value'))}",
            "sugerencia": sug,
            "fila": fila,
            "columna": item.get("column"),
            "valor": _safe_str(item.get("value")),
        }

    if rule_name == "cardinality_check":
        w = item.get("warning", "")
        return {
            "descripcion": f"Cardinalidad anómala en columna '{item.get('column')}': {w}",
            "sugerencia": sug,
            "fila": fila,
            "columna": item.get("column"),
            "valor": w or None,
        }

    if rule_name == "correlation_check":
        cols = item.get("columns", "")
        corr = item.get("correlation")
        return {
            "descripcion": f"Correlación alta ({corr}) entre columnas: {cols}",
            "sugerencia": sug,
            "fila": None,
            "columna": cols or None,
            "valor": _safe_str(corr) if corr is not None else None,
        }

    if rule_name == "distribution_check":
        flags = item.get("flags", [])
        return {
            "descripcion": f"Distribución anómala en columna '{item.get('column')}': {', '.join(flags)}",
            "sugerencia": sug,
            "fila": fila,
            "columna": item.get("column"),
            "valor": ", ".join(flags),
        }

    if rule_name == "date_inconsistency_check":
        return {
            "descripcion": f"Relación temporal ilógica: {item.get('col1')}={item.get('val1')} > {item.get('col2')}={item.get('val2')}",
            "sugerencia": sug,
            "fila": fila,
            "columna": f"{item.get('col1')} / {item.get('col2')}",
            "valor": f"{item.get('col1')}={item.get('val1')}, {item.get('col2')}={item.get('val2')}",
        }

    if rule_name == "latency_check":
        lh = item.get("latency_h")
        return {
            "descripcion": f"Latencia de {lh}h entre evento ({item.get('event')}) e ingesta ({item.get('ingest')})",
            "sugerencia": sug,
            "fila": fila,
            "columna": None,
            "valor": f"{lh}h",
        }

    if rule_name == "sequential_integrity_check":
        msg = item.get("message") or f"Salto en secuencia en columna '{item.get('column')}'"
        return {"descripcion": msg, "sugerencia": sug, "fila": fila, "columna": item.get("column"), "valor": item.get("message")}

    if rule_name == "referential_integrity_check":
        return {
            "descripcion": f"Valor huérfano '{item.get('value')}' en columna '{item.get('column')}' no existe en '{item.get('missing_in')}'",
            "sugerencia": sug,
            "fila": fila,
            "columna": item.get("column"),
            "valor": _safe_str(item.get("value")),
        }

    if rule_name == "row_completeness_check":
        nc = item.get("null_columns", [])[:5]
        return {
            "descripcion": f"Fila con solo {item.get('completeness_pct')}% de datos completos. Columnas vacías: {', '.join(nc)}",
            "sugerencia": sug,
            "fila": fila,
            "columna": None,
            "valor": f"{item.get('completeness_pct')}% completo",
        }

    if rule_name == "multivariate_outlier_check":
        vals = item.get("values")
        if vals:
            parts = [f"{k}={v}" for k, v in list(vals.items())[:4]]
            desc = "Outlier multivariado: " + ", ".join(parts)
            val = ", ".join(f"{k}: {v}" for k, v in list(vals.items())[:6])
        else:
            desc = "Outlier multivariado detectado"
            val = None
        return {"descripcion": desc, "sugerencia": sug, "fila": fila, "columna": None, "valor": val}

    if rule_name == "cross_consistency_check":
        return {
            "descripcion": f"Violación de consistencia: {item.get('rule', '')}",
            "sugerencia": sug,
            "fila": fila,
            "columna": item.get("rule"),
            "valor": None,
        }

    if rule_name == "functional_dependency_check":
        return {
            "descripcion": f"Dependencia funcional violada: {item.get('determinant')}={item.get('value')} → {item.get('dependent')}={item.get('dep_values')}",
            "sugerencia": sug,
            "fila": fila,
            "columna": f"{item.get('determinant')} → {item.get('dependent')}",
            "valor": f"{item.get('determinant')}={item.get('value')}",
        }

    if rule_name == "derived_column_check":
        return {
            "descripcion": f"Columna '{item.get('column')}' no coincide: esperado={item.get('expected')}, actual={item.get('actual')} (dif: {item.get('diff_pct')}%)",
            "sugerencia": sug,
            "fila": fila,
            "columna": item.get("column"),
            "valor": f"actual={item.get('actual')}, esperado={item.get('expected')}",
        }

    if rule_name in ("fuzzy_name_match", "fuzzy_id_match", "similar_dob"):
        sim = item.get("group_similarity")
        desc = f"Posible duplicado (similitud: {sim * 100:.0f}%)" if sim else "Posible duplicado de persona"
        vals = item.get("values")
        val = None
        if vals:
            parts = [f"{k}={v}" for k, v in list(vals.items())[:4]]
            val = ", ".join(parts)
        return {"descripcion": desc, "sugerencia": sug, "fila": fila, "columna": None, "valor": val}

    if rule_name == "person_composite_similarity":
        gi = item.get("group_info")
        if gi:
            desc = f"Posible misma persona (score compuesto: {gi.get('composite_score', 0) * 100:.0f}%, grupo de {gi.get('group_size')})"
        else:
            desc = "Posible misma persona detectada"
        vals = item.get("values")
        val = None
        if vals:
            parts = [f"{k}={v}" for k, v in list(vals.items())[:4]]
            val = ", ".join(parts)
        return {"descripcion": desc, "sugerencia": sug, "fila": fila, "columna": None, "valor": val}

    # Fallback
    if "error" in item:
        return {"descripcion": f"Error: {item['error']}", "sugerencia": sug, "fila": fila, "columna": None, "valor": None}
    col = item.get("column")
    val = item.get("value")
    if col and val is not None:
        return {"descripcion": f"Valor anómalo en columna '{col}': {_safe_str(val)}", "sugerencia": sug, "fila": fila, "columna": col, "valor": _safe_str(val)}
    if col:
        return {"descripcion": f"Problema en columna '{col}'", "sugerencia": sug, "fila": fila, "columna": col, "valor": None}
    if "message" in item:
        return {"descripcion": item["message"], "sugerencia": sug, "fila": fila, "columna": None, "valor": None}
    return {"descripcion": "Error de calidad de datos", "sugerencia": sug, "fila": fila, "columna": None, "valor": None}


def describe_detail(rule_name: str, item: dict) -> str:
    if rule_name == "null_check":
        return f"Columna '{item.get('column')}' — {item.get('nulls')} valores nulos ({item.get('pct')}%)"

    if rule_name == "unique_check":
        if "columns" in item:
            cols = ", ".join(item["columns"])
            return f"Columnas [{cols}] — {item.get('composite_duplicates')} duplicados compuestos ({item.get('pct')}%)"
        return f"Columna '{item.get('column')}' — {item.get('duplicates')} duplicados ({item.get('pct')}%), {item.get('unique_values')} valores únicos"

    if rule_name == "duplicate_check":
        return f"{item.get('count')} filas duplicadas exactas ({item.get('pct')}%)"

    if rule_name == "range_check":
        return (f"Columna '{item.get('column')}' — {item.get('outliers')} outliers ({item.get('pct')}%), "
                f"rango [{item.get('min')}, {item.get('max')}], "
                f"IQR bounds [{item.get('lower_bound')}, {item.get('upper_bound')}]")

    if rule_name == "pattern_check":
        return f"Columna '{item.get('column')}' — patrón '{item.get('pattern')}': {item.get('failed')} fallos de {item.get('total')} ({item.get('pct')}%)"

    if rule_name == "cardinality_check":
        return f"Columna '{item.get('column')}' — {item.get('issue')}"

    if rule_name == "correlation_check":
        if item.get("type") == "HIGH_CORRELATION":
            return f"Correlación alta: {item.get('column_x')} ↔ {item.get('column_y')} = {item.get('correlation')}"
        if item.get("type") == "HIGH_VIF":
            return f"VIF alto en {item.get('column')}: {item.get('vif')}"
        return f"{item.get('type')}: {item.get('column_x')} / {item.get('column_y')}"

    if rule_name == "distribution_check":
        flags = ", ".join(item.get("flags", []))
        return f"Columna '{item.get('column')}' — flags: {flags}, skew={item.get('skewness')}, kurt={item.get('kurtosis')}"

    if rule_name == "type_check":
        extra = ""
        if item.get("expected_type"):
            extra = f", esperado={item['expected_type']}"
        if item.get("mixed_types"):
            extra += f", tipos mixtos: {', '.join(item['mixed_types'])}"
        return f"Columna '{item.get('column')}' — declarado={item.get('declared_type')}, inferido={item.get('inferred_type')}{extra}"

    if rule_name in ("email_check", "phone_check", "zip_code_check", "rfc_curp_check",
                     "special_chars_check", "string_length_check", "trim_check",
                     "case_consistency_check", "invalid_date_check", "date_range_check",
                     "freshness_check", "missing_fk_check"):
        return f"Columna '{item.get('column')}' — {item.get('failed')} fallos de {item.get('total')} ({item.get('pct')}%)"

    if rule_name == "date_inconsistency_check":
        return f"{item.get('column_pair')} — {item.get('failed')} filas inconsistentes de {item.get('total')} ({item.get('pct')}%)"

    if rule_name == "latency_check":
        return (f"{item.get('event_col')} → {item.get('ingest_col')}: {item.get('failed')} fallos de {item.get('total')} ({item.get('pct')}%), "
                f"latencia máx={item.get('max_latency_h')}h, prom={item.get('avg_latency_h')}h")

    if rule_name == "volume_anomaly_check":
        note = item.get("note")
        if note:
            return note
        return f"Actual: {item.get('actual_rows')}, Esperado: {item.get('expected_rows')}, Desviación: {item.get('deviation_pct')}%"

    if rule_name == "sequential_integrity_check":
        return f"Columna '{item.get('column')}' — {item.get('gaps')} saltos entre {item.get('from')} y {item.get('to')}"

    if rule_name == "referential_integrity_check":
        return f"{item.get('child_column')} → {item.get('parent_column')}: {item.get('orphans')} huérfanos de {item.get('total')} ({item.get('pct')}%)"

    if rule_name == "row_completeness_check":
        return (f"{item.get('sparse_rows')} filas con <{item.get('min_completeness_pct')}% completas de {item.get('total_rows')} "
                f"({item.get('sparse_pct')}%), promedio {item.get('avg_completeness_pct')}%")

    if rule_name == "multivariate_outlier_check":
        return f"{item.get('outliers')} outliers multivariados de {item.get('total_analyzed')} ({item.get('pct')}%)"

    if rule_name == "drift_check":
        note = item.get("note")
        if note:
            return note
        return f"Columna '{item.get('column')}' — {item.get('count')} categorías nuevas de {item.get('reference_count')} referencia"

    if rule_name == "schema_evolution_check":
        added = len(item.get("columns_added") or [])
        removed = len(item.get("columns_removed") or [])
        changed = len(item.get("columns_type_changed") or {})
        return f"+{added} añadidas, -{removed} eliminadas, ~{changed} cambios de tipo"

    if rule_name == "cross_consistency_check":
        return f"{item.get('rule')} — {item.get('failed')} violaciones de {item.get('total')} ({item.get('pct')}%)"

    if rule_name == "functional_dependency_check":
        return f"{item.get('determinant')} → {item.get('dependent')}: {item.get('failed')} violaciones de {item.get('total')} ({item.get('pct')}%)"

    if rule_name == "class_balance_check":
        return f"Columna '{item.get('column')}' — valor dominante '{item.get('top_value')}': {item.get('top_pct')}%, {item.get('unique_values')} valores únicos"

    if rule_name == "boolean_bias_check":
        pct = item.get("true_pct") or item.get("false_pct")
        return f"Columna '{item.get('column')}' — sesgo hacia {item.get('bias')}: {pct}%"

    if rule_name == "derived_column_check":
        return f"Columna '{item.get('column')}' — {item.get('failed')} fallos de {item.get('total')} ({item.get('pct')}%), desviación máx {item.get('max_deviation_pct')}%"

    if rule_name in ("fuzzy_name_match", "fuzzy_id_match", "similar_dob"):
        groups = item.get("groups") or []
        total = item.get("total_groups") or len(groups)
        return f"{total} grupos de registros similares"

    if rule_name == "person_composite_similarity":
        fields = ", ".join(item.get("available_fields") or [])
        weights = item.get("weights")
        w_str = ", ".join(f"{k}={v}" for k, v in (weights or {}).items()) if weights else "N/A"
        return f"{item.get('total_groups')} grupos, campos: {fields}, pesos: {w_str}"

    if "error" in item:
        return f"Error: {item['error']}"
    if "note" in item:
        return item["note"]
    if "message" in item:
        return item["message"]
    if "column" in item:
        return f"Columna '{item['column']}' — {item.get('failed') or item.get('count') or item.get('nulls') or item.get('outliers') or '?'} fallos"
    parts = [f"{k}={v}" for k, v in item.items() if k not in ("type", "threshold")]
    return ", ".join(parts) if parts else str(item)
