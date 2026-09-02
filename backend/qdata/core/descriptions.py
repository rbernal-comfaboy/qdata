import re
from typing import Any


def duplicate_groups(rule: dict) -> list[dict]:
    """Ordered (largest first) list of {size, rows} groups for a duplicate_check
    rule, from the 'duplicate_groups' detail or legacy group-based sample_failures."""
    detail = next((d for d in rule.get("details") or [] if d.get("type") == "duplicate_groups"), None)
    if detail and detail.get("groups"):
        groups = []
        for g in detail["groups"]:
            rows = g.get("rows") or []
            groups.append({"size": g.get("size") or len(rows), "rows": rows})
        return groups
    groups = []
    for item in rule.get("sample_failures") or []:
        if not isinstance(item, dict):
            continue
        rows = item.get("rows") or []
        groups.append({"size": item.get("size") or len(rows), "rows": rows})
    groups.sort(key=lambda g: g["size"], reverse=True)
    return groups


RULE_DISPLAY_NAMES: dict[str, str] = {
    "null_check": "Campos vacíos",
    "type_check": "Tipo de dato incorrecto",
    "unique_check": "Valores repetidos",
    "duplicate_check": "Registros repetidos",
    "range_check": "Fuera de rango",
    "pattern_check": "Formato incorrecto",
    "cardinality_check": "Cardinalidad extraña",
    "correlation_check": "Columnas correlacionadas",
    "distribution_check": "Distribución anormal",
    "email_check": "Correos inválidos",
    "special_chars_check": "Caracteres extraños",
    "string_length_check": "Longitud incorrecta",
    "trim_check": "Espacios extras",
    "case_consistency_check": "Mayúsculas/minúsculas",
    "phone_check": "Teléfonos mal escritos",
    "zip_code_check": "Códigos postales incorrectos",
    "rfc_curp_check": "RFC/CURP incorrectos",
    "invalid_date_check": "Fechas inválidas",
    "date_range_check": "Fechas fuera de rango",
    "date_inconsistency_check": "Fechas sin coherencia",
    "freshness_check": "Datos desactualizados",
    "latency_check": "Retraso en carga",
    "volume_anomaly_check": "Volumen anormal",
    "sequential_integrity_check": "Saltos en secuencia",
    "missing_fk_check": "FK faltantes",
    "referential_integrity_check": "Datos huérfanos",
    "row_completeness_check": "Filas incompletas",
    "multivariate_outlier_check": "Combinaciones extrañas",
    "drift_check": "Categorías nuevas",
    "schema_evolution_check": "Estructura cambiada",
    "cross_consistency_check": "Inconsistencias entre columnas",
    "functional_dependency_check": "Dependencias incumplidas",
    "class_balance_check": "Columna sin variación",
    "boolean_bias_check": "Columna sesgada",
    "derived_column_check": "Columna calculada incorrecta",
    "fuzzy_name_match": "Nombres similares",
    "fuzzy_id_match": "IDs similares",
    "similar_dob": "Fechas de nacimiento cercanas",
    "person_composite_similarity": "Personas duplicadas",
    "custom_sql_rule": "Regla SQL personalizada",
    "custom_python_rule": "Regla Python personalizada",
}


def display_name(rule_name: str) -> str:
    return RULE_DISPLAY_NAMES.get(rule_name, rule_name)


def severity_description(failure_pct: float, total: int, failed: int) -> str:
    if failed == 0:
        return "Sin errores"
    ratio = failure_pct / 100
    parts = []
    if ratio >= 0.5:
        parts.append("La mayoría")
    elif ratio >= 0.3:
        parts.append("Muchos")
    elif ratio >= 0.1:
        parts.append("Algunos")
    elif ratio > 0:
        parts.append("Pocos")
    else:
        parts.append("Sin")
    parts.append("errores")
    desc = " ".join(parts)
    if total > 0:
        per10 = round(failed / total * 10)
        desc += f" ({per10} de cada 10 registros)"
    return desc


def _safe_str(v: Any) -> str:
    if v is None:
        return "—"
    return str(v)


# --- Glossary: qué hace cada regla (lenguaje simple) ---
GLOSARIO: dict[str, str] = {
    "null_check": "Revisa si hay celdas vacías o sin información",
    "type_check": "Verifica que los datos tengan el formato correcto (texto, número, fecha)",
    "unique_check": "Busca valores repetidos en una columna que deberían ser únicos",
    "duplicate_check": "Detecta filas completas que están repetidas",
    "range_check": "Encuentra valores numéricos fuera del rango normal esperado",
    "pattern_check": "Revisa si los textos siguen un formato específico (como códigos)",
    "cardinality_check": "Analiza si hay muy pocos o demasiados valores distintos en una columna",
    "correlation_check": "Detecta columnas que están tan relacionadas que podrían sobrar",
    "distribution_check": "Revisa si los datos tienen una distribución anormal",
    "email_check": "Verifica que los correos electrónicos tengan formato válido",
    "special_chars_check": "Busca caracteres extraños o problemáticos en los textos",
    "string_length_check": "Revisa si la longitud de los textos está dentro del rango esperado",
    "trim_check": "Detecta espacios adicionales al inicio o final del texto",
    "case_consistency_check": "Revisa que los textos tengan una misma forma (mayúsculas/minúsculas)",
    "phone_check": "Verifica que los números telefónicos tengan un formato correcto",
    "zip_code_check": "Valida que los códigos postales tengan el formato adecuado",
    "rfc_curp_check": "Revisa que RFCs y CURPs cumplan con el formato oficial del SAT",
    "invalid_date_check": "Detecta fechas mal escritas o que no existen",
    "date_range_check": "Busca fechas fuera del período esperado",
    "date_inconsistency_check": "Verifica que las fechas tengan coherencia (ej: fin ≥ inicio)",
    "freshness_check": "Comprueba que los datos estén actualizados",
    "latency_check": "Mide el tiempo que tarda la información en estar disponible",
    "volume_anomaly_check": "Detecta si llegaron muchos más o muchos menos registros de lo normal",
    "sequential_integrity_check": "Revisa si hay números de folio o ID saltados",
    "missing_fk_check": "Busca valores que deberían existir en otra tabla pero no están",
    "referential_integrity_check": "Detecta datos huérfanos sin relación en otras tablas",
    "row_completeness_check": "Revisa si hay filas con demasiada información faltante",
    "multivariate_outlier_check": "Encuentra combinaciones extrañas de valores en varias columnas",
    "drift_check": "Detecta si aparecieron categorías nuevas no esperadas",
    "schema_evolution_check": "Revisa si la estructura de la tabla cambió con el tiempo",
    "cross_consistency_check": "Verifica reglas de negocio entre columnas relacionadas",
    "functional_dependency_check": "Revisa que un valor siempre corresponda a otro único valor",
    "class_balance_check": "Analiza si una columna tiene un solo valor repetido muchas veces",
    "boolean_bias_check": "Detecta si una columna de sí/no está muy desbalanceada",
    "derived_column_check": "Verifica que una columna calculada tenga el resultado correcto",
    "fuzzy_name_match": "Busca nombres muy parecidos que podrían ser la misma persona",
    "fuzzy_id_match": "Busca IDs muy parecidos que podrían ser errores de captura",
    "similar_dob": "Compara fechas de nacimiento cercanas para detectar duplicados",
    "person_composite_similarity": "Evalúa si dos registros podrían pertenecer a la misma persona",
    "custom_sql_rule": "Aplica una regla personalizada escrita en SQL",
    "custom_python_rule": "Aplica una regla personalizada escrita en Python",
}


def describe_rule_simple(rule_name: str) -> str:
    return GLOSARIO.get(rule_name, "Regla de validación de datos")


# --- Qué hacer: pasos concretos para cada tipo de error ---
QUE_HACER: dict[str, str] = {
    "null_check": "Revisa los registros marcados y completa la información. Si no tienes el dato, escribe 'No disponible' o un valor por omisión.",
    "type_check": "Corrige el formato del dato. Por ejemplo, si es una fecha debe ser '2024-01-01' y no 'ene-2024'.",
    "unique_check": "Revisa si los valores repetidos son válidos. Si no deberían estar duplicados, elimina los sobrantes.",
    "duplicate_check": "Verifica si las filas repetidas son errores y elimina las copias innecesarias.",
    "range_check": "Revisa si el valor fuera de rango es real o fue capturado incorrectamente.",
    "pattern_check": "Aplica un formato estándar. Por ejemplo, un código postal debe tener 5 dígitos.",
    "cardinality_check": "Evalúa si esta columna realmente sirve. Si casi todos los valores son iguales, quizás puedes omitirla.",
    "correlation_check": "Si dos columnas están muy relacionadas, una de las dos podría no ser necesaria.",
    "distribution_check": "Revisa si los datos sesgados podrían transformarse (ej: usar logaritmo) para mejor análisis.",
    "email_check": "Corrige la dirección de correo: debe tener formato 'usuario@dominio.com'.",
    "special_chars_check": "Limpia los caracteres extraños usando herramientas de limpieza de texto.",
    "string_length_check": "Ajusta el texto al largo esperado. Si es muy largo, recorta; si es muy corto, verifica que esté completo.",
    "trim_check": "Elimina los espacios de más al inicio y final del texto con una función de limpieza.",
    "case_consistency_check": "Unifica todo a mayúsculas o minúsculas según el estándar que uses.",
    "phone_check": "Estandariza los teléfonos al formato nacional. En Colombia debe ser +57 y 10 dígitos.",
    "zip_code_check": "Corrige el código postal: en México son 5 dígitos, en EE.UU. son 5 o 9 dígitos.",
    "rfc_curp_check": "Verifica que el RFC tenga 13 caracteres y la CURP 18, con el formato oficial del SAT.",
    "invalid_date_check": "Corrige las fechas al formato AAAA-MM-DD. Por ejemplo, '2024/01/15' → '2024-01-15'.",
    "date_range_check": "Revisa si la fecha fuera de rango es correcta o fue un error de captura.",
    "date_inconsistency_check": "Asegúrate de que la fecha de inicio sea anterior o igual a la fecha de fin.",
    "freshness_check": "Verifica que los datos se estén actualizando correctamente y a tiempo.",
    "latency_check": "Revisa el proceso de carga de datos para que la información llegue más rápido.",
    "volume_anomaly_check": "Investiga por qué la cantidad de registros subió o bajó tanto. Revisa la fuente de datos.",
    "sequential_integrity_check": "Revisa si faltan registros intermedios. Si el consecutivo se reinicia, confirma que sea intencional.",
    "missing_fk_check": "Revisa la tabla donde deberían estar esos valores faltantes y completa los datos.",
    "referential_integrity_check": "Los datos huérfanos no tienen referencia en otra tabla. Hay que agregar los registros padre faltantes.",
    "row_completeness_check": "Completa la información faltante de estas filas o considera si son datos que ya no sirven.",
    "multivariate_outlier_check": "Revisa estas combinaciones de valores. Si son datos reales, mantenlos; si son errores, corrígelos.",
    "drift_check": "Verifica si las categorías nuevas son válidas o si llegaron por error en la carga de datos.",
    "schema_evolution_check": "Si la tabla cambió de estructura, actualiza las reglas de validación para que coincidan.",
    "cross_consistency_check": "Revisa la relación entre las columnas. Por ejemplo, si 'total = precio × cantidad' debe cumplirse.",
    "functional_dependency_check": "Un valor debe corresponder a un solo resultado. Corrige los casos que no cumplan esta regla.",
    "class_balance_check": "Si una columna tiene siempre el mismo valor, quizás puedes omitirla del análisis.",
    "boolean_bias_check": "Una columna de sí/no con 99% de 'sí' probablemente no aporta información útil.",
    "derived_column_check": "Revisa la fórmula de la columna calculada. Puede tener un error en la cuenta.",
    "fuzzy_name_match": "Compara los nombres similares manualmente para decidir si son la misma persona.",
    "fuzzy_id_match": "Revisa si los IDs parecidos son errores de dedo al capturar o personas distintas.",
    "similar_dob": "Compara estos registros manualmente. Fechas muy cercanas pueden indicar duplicados.",
    "person_composite_similarity": "Revisa los grupos marcados: podrían ser registros duplicados de una misma persona.",
    "custom_sql_rule": "Revisa los registros que no pasaron tu regla SQL personalizada. Ajusta los datos o la regla.",
    "custom_python_rule": "Revisa los registros que no pasaron tu regla Python personalizada.",
}

SUGERENCIAS: dict[str, str] = {
    "null_check": "Completa los datos faltantes o asígnales un valor como 'No especificado'",
    "type_check": "Convierte los datos al formato correcto (número, fecha, texto)",
    "unique_check": "Elimina los valores repetidos o revisa si deben ser únicos",
    "duplicate_check": "Elimina las filas duplicadas",
    "range_check": "Verifica si el valor es real o un error de captura",
    "pattern_check": "Estandariza el formato con una función de limpieza",
    "cardinality_check": "Evalúa si la columna realmente aporta información útil",
    "correlation_check": "Considera eliminar una de las dos columnas o reducir dimensiones",
    "distribution_check": "Aplica una transformación (logaritmo) para mejorar el análisis",
    "email_check": "Corrige el correo: usuario@dominio.com",
    "special_chars_check": "Limpia caracteres extraños del texto",
    "string_length_check": "Ajusta el texto al largo esperado",
    "trim_check": "Quita espacios de más al inicio y final",
    "case_consistency_check": "Unifica mayúsculas/minúsculas",
    "phone_check": "Estandariza los teléfonos al formato nacional",
    "zip_code_check": "Corrige el código postal al formato de 5 dígitos",
    "rfc_curp_check": "Verifica el formato contra el estándar del SAT",
    "invalid_date_check": "Corrige las fechas al formato AAAA-MM-DD",
    "date_range_check": "Revisa fechas fuera del período esperado",
    "date_inconsistency_check": "Asegura que fecha_inicio ≤ fecha_fin",
    "freshness_check": "Verifica que los datos estén actualizados",
    "latency_check": "Revisa la velocidad de carga de los datos",
    "volume_anomaly_check": "Investiga cambios en el volumen de registros",
    "sequential_integrity_check": "Revisa si faltan registros en la secuencia",
    "missing_fk_check": "Completa los valores faltantes en la tabla relacionada",
    "referential_integrity_check": "Agrega los registros padre que faltan",
    "row_completeness_check": "Completa filas con datos faltantes",
    "multivariate_outlier_check": "Revisa combinaciones de valores anómalos",
    "drift_check": "Verifica si las categorías nuevas son válidas",
    "schema_evolution_check": "Actualiza la validación al nuevo esquema",
    "cross_consistency_check": "Revisa las relaciones entre columnas",
    "functional_dependency_check": "Corrige valores que no cumplen la dependencia funcional",
    "class_balance_check": "Evalúa si columnas con un solo valor aportan información",
    "boolean_bias_check": "Considera si columnas sesgadas son útiles",
    "derived_column_check": "Revisa la fórmula de la columna calculada",
    "fuzzy_name_match": "Compara manualmente los nombres similares",
    "fuzzy_id_match": "Revisa si los IDs parecidos son errores de captura",
    "similar_dob": "Compara estos registros para detectar duplicados",
    "person_composite_similarity": "Revisa los grupos de posibles duplicados",
    "custom_sql_rule": "Revisa los registros que no cumplen tu regla SQL",
    "custom_python_rule": "Revisa los registros que no pasan tu validación",
}


# --- describe_detail: una línea de resumen por cada detalle ---

def describe_detail(rule_name: str, item: dict) -> str:
    if rule_name == "null_check":
        col = item.get("column", "?")
        n = item.get("nulls", 0)
        p = item.get("pct", 0)
        return f"Columna '{col}' tiene {n} celdas vacías ({p}%)"

    if rule_name == "unique_check":
        if "columns" in item:
            cols = ", ".join(item["columns"])
            dup = item.get("composite_duplicates", 0)
            p = item.get("pct", 0)
            return f"Columnas [{cols}] — {dup} combinaciones repetidas ({p}%)"
        col = item.get("column", "?")
        dup = item.get("duplicates", 0)
        p = item.get("pct", 0)
        uv = item.get("unique_values", 0)
        return f"Columna '{col}' — {dup} valores repetidos ({p}%), {uv} valores distintos"

    if rule_name == "duplicate_check":
        if item.get("type") == "duplicate_groups":
            groups = item.get("groups") or []
            shown = sum(len(g.get("rows") or []) for g in groups)
            return f"{len(groups)} grupos de filas repetidas ({shown} filas mostradas)"
        c = item.get("count", 0)
        p = item.get("pct", 0)
        return f"{c} filas completas repetidas ({p}%)"

    if rule_name == "range_check":
        col = item.get("column", "?")
        o = item.get("outliers", 0)
        p = item.get("pct", 0)
        mn = item.get("min", "?")
        mx = item.get("max", "?")
        return f"Columna '{col}' — {o} valores fuera de rango ({p}%), rango normal [{mn}, {mx}]"

    if rule_name == "pattern_check":
        col = item.get("column", "?")
        pat = item.get("pattern", "?")
        f = item.get("failed", 0)
        t = item.get("total", 0)
        p = item.get("pct", 0)
        return f"Columna '{col}' — patrón '{pat}': {f} fallos de {t} ({p}%)"

    if rule_name == "cardinality_check":
        col = item.get("column", "?")
        issue = item.get("issue", "?")
        return f"Columna '{col}' — {issue}"

    if rule_name == "correlation_check":
        if item.get("type") == "HIGH_CORRELATION":
            return f"Correlación alta entre {item.get('column_x')} y {item.get('column_y')}: {item.get('correlation')}"
        if item.get("type") == "HIGH_VIF":
            return f"La columna {item.get('column')} está muy relacionada con otras: VIF={item.get('vif')}"
        return f"{item.get('type')}: {item.get('column_x')} / {item.get('column_y')}"

    if rule_name == "distribution_check":
        flags = ", ".join(item.get("flags", []))
        col = item.get("column", "?")
        sk = item.get("skewness", "?")
        ku = item.get("kurtosis", "?")
        return f"Columna '{col}' — distribución anormal: {flags}, sesgo={sk}, curtosis={ku}"

    if rule_name == "type_check":
        col = item.get("column", "?")
        parts = []
        if item.get("expected_type"):
            parts.append(f"se esperaba {item['expected_type']}")
        if item.get("mixed_types"):
            parts.append(f"tipos mezclados: {', '.join(item['mixed_types'])}")
        extra = ", ".join(parts)
        decl = item.get("declared_type", "?")
        inf = item.get("inferred_type", "?")
        return f"Columna '{col}' — se declaró como {decl} pero parece {inf}" + (f" ({extra})" if extra else "")

    if rule_name in ("email_check", "phone_check", "zip_code_check", "rfc_curp_check",
                     "special_chars_check", "string_length_check", "trim_check",
                     "case_consistency_check", "invalid_date_check", "date_range_check",
                     "freshness_check", "missing_fk_check"):
        col = item.get("column", "?")
        f = item.get("failed", 0)
        t = item.get("total", 0)
        p = item.get("pct", 0)
        return f"Columna '{col}' — {f} valores incorrectos de {t} ({p}%)"

    if rule_name == "date_inconsistency_check":
        cp = item.get("column_pair", "?")
        f = item.get("failed", 0)
        t = item.get("total", 0)
        p = item.get("pct", 0)
        return f"{cp} — {f} fechas sin coherencia de {t} ({p}%)"

    if rule_name == "latency_check":
        ec = item.get("event_col", "?")
        ic = item.get("ingest_col", "?")
        f = item.get("failed", 0)
        t = item.get("total", 0)
        p = item.get("pct", 0)
        mx = item.get("max_latency_h", "?")
        prom = item.get("avg_latency_h", "?")
        return f"{ec} → {ic}: {f} retrasos de {t} ({p}%), retraso máximo {mx}h, promedio {prom}h"

    if rule_name == "volume_anomaly_check":
        note = item.get("note")
        if note:
            return note
        actual = item.get("actual_rows")
        esperado = item.get("expected_rows")
        dev = item.get("deviation_pct")
        if actual is not None and esperado is not None:
            return f"Registros actuales: {actual}, esperados: {esperado}, desviación: {dev}%"
        return "Volumen de registros fuera de lo normal"

    if rule_name == "sequential_integrity_check":
        col = item.get("column", "?")
        g = item.get("gaps", 0)
        fr = item.get("from", "?")
        to = item.get("to", "?")
        return f"Columna '{col}' — {g} saltos en la secuencia entre {fr} y {to}"

    if rule_name == "referential_integrity_check":
        cc = item.get("child_column", "?")
        pc = item.get("parent_column", "?")
        o = item.get("orphans", 0)
        t = item.get("total", 0)
        p = item.get("pct", 0)
        return f"{cc} → {pc}: {o} valores huérfanos de {t} ({p}%)"

    if rule_name == "row_completeness_check":
        sr = item.get("sparse_rows", 0)
        mc = item.get("min_completeness_pct", "?")
        tr = item.get("total_rows", 0)
        sp = item.get("sparse_pct", 0)
        ap = item.get("avg_completeness_pct", 0)
        return f"{sr} filas con menos del {mc}% de datos completos de {tr} ({sp}%), promedio de completitud {ap}%"

    if rule_name == "multivariate_outlier_check":
        o = item.get("outliers", 0)
        t = item.get("total_analyzed", 0)
        p = item.get("pct", 0)
        return f"{o} combinaciones extrañas de valores de {t} ({p}%)"

    if rule_name == "drift_check":
        note = item.get("note")
        if note:
            return note
        col = item.get("column", "?")
        c = item.get("count", 0)
        ref = item.get("reference_count", "?")
        return f"Columna '{col}' — {c} categorías nuevas no esperadas (referencia: {ref})"

    if rule_name == "schema_evolution_check":
        added = len(item.get("columns_added") or [])
        removed = len(item.get("columns_removed") or [])
        changed = len(item.get("columns_type_changed") or {})
        return f"La tabla cambió: +{added} columnas añadidas, -{removed} eliminadas, ~{changed} cambios de tipo"

    if rule_name == "cross_consistency_check":
        rule = item.get("rule", "?")
        f = item.get("failed", 0)
        t = item.get("total", 0)
        p = item.get("pct", 0)
        return f"{rule} — {f} violaciones de {t} ({p}%)"

    if rule_name == "functional_dependency_check":
        det = item.get("determinant", "?")
        dep = item.get("dependent", "?")
        f = item.get("failed", 0)
        t = item.get("total", 0)
        p = item.get("pct", 0)
        return f"{det} → {dep}: {f} casos donde no se cumple de {t} ({p}%)"

    if rule_name == "class_balance_check":
        col = item.get("column", "?")
        tv = item.get("top_value", "?")
        tp = item.get("top_pct", 0)
        uv = item.get("unique_values", 0)
        return f"Columna '{col}' — el valor '{tv}' domina con {tp}%, {uv} valores distintos"

    if rule_name == "boolean_bias_check":
        col = item.get("column", "?")
        bias = item.get("bias", "?")
        pct = item.get("true_pct") or item.get("false_pct")
        return f"Columna '{col}' — está muy cargada hacia '{bias}': {pct}%"

    if rule_name == "derived_column_check":
        col = item.get("column", "?")
        f = item.get("failed", 0)
        t = item.get("total", 0)
        p = item.get("pct", 0)
        md = item.get("max_deviation_pct", 0)
        return f"Columna '{col}' — {f} resultados incorrectos de {t} ({p}%), desviación máxima {md}%"

    if rule_name in ("fuzzy_name_match", "fuzzy_id_match", "similar_dob"):
        groups = item.get("groups") or []
        total = item.get("total_groups") or len(groups)
        return f"{total} grupos de registros con posibles duplicados"

    if rule_name == "person_composite_similarity":
        fields = ", ".join(item.get("available_fields") or [])
        weights = item.get("weights")
        w_str = ", ".join(f"{k}={v}" for k, v in (weights or {}).items()) if weights else "N/A"
        return f"{item.get('total_groups')} grupos posibles duplicados, campos: {fields}, pesos: {w_str}"

    if "error" in item:
        return f"Error: {item['error']}"
    if "note" in item:
        return item["note"]
    if "message" in item:
        return item["message"]
    if "column" in item:
        col = item["column"]
        fallos = item.get("failed") or item.get("count") or item.get("nulls") or item.get("outliers") or "?"
        return f"Columna '{col}' — {fallos} problemas"
    parts = [f"{k}={v}" for k, v in item.items() if k not in ("type", "threshold")]
    return ", ".join(parts) if parts else str(item)


# --- describe_error: descripción de cada error individual ---

_NIT_REASONS = {
    "caracteres_invalidos": "contiene letras o caracteres no numéricos",
    "formato_dv_invalido": "el dígito de verificación debe ser un solo dígito después del guion",
    "longitud_invalida": "debe tener entre 6 y 10 dígitos",
    "mas_de_11_digitos": "supera los 11 dígitos",
    "dv_incoherente": "el dígito de verificación no coincide con el Módulo 11",
    "vacio": "está vacío",
}

_NIT_WARNINGS = {
    "ceros_a_la_izquierda": "tenía ceros a la izquierda (se eliminaron antes de validar)",
    "longitud_elevada": "tiene 11 dígitos (longitud excepcional de asignaciones especiales de la DIAN)",
}


def describe_error(rule_name: str, item: dict, recommendation: str | None = None) -> dict:
    row = item.get("row")
    fila = row + 2 if row is not None else None
    sug = recommendation or SUGERENCIAS.get(rule_name, "Revisa el valor en la fuente de datos")
    que_hacer = QUE_HACER.get(rule_name, "Revisa este registro en la fuente de datos original")

    if rule_name == "null_check":
        return {
            "descripcion": f"La columna '{item.get('column')}' tiene un valor vacío",
            "sugerencia": sug,
            "que_hacer": que_hacer,
            "fila": fila,
            "columna": item.get("column"),
            "valor": None,
        }

    if rule_name == "type_check":
        col = item.get("column", "")
        sv = item.get("sample_value")
        desc = f"La columna '{col}' tiene un dato de tipo incorrecto"
        if sv:
            desc += f" (ej: '{sv}')"
        return {
            "descripcion": desc,
            "sugerencia": sug,
            "que_hacer": que_hacer,
            "fila": fila,
            "columna": col,
            "valor": _safe_str(sv) if sv else None,
        }

    if rule_name == "unique_check":
        return {
            "descripcion": f"El valor '{item.get('value')}' está repetido en la columna '{item.get('column')}'",
            "sugerencia": sug,
            "que_hacer": que_hacer,
            "fila": fila,
            "columna": item.get("column"),
            "valor": _safe_str(item.get("value")),
        }

    if rule_name == "duplicate_check":
        if item.get("rows"):
            rows = item.get("rows") or []
            count = item.get("size") or len(rows)
            row_nums = []
            for r in rows:
                rv = r.get("row")
                if rv is not None:
                    row_nums.append(str(rv + 2))
            if len(row_nums) <= 5:
                display_rows = ", ".join(row_nums)
            else:
                display_rows = f"{row_nums[0]}, {row_nums[1]}, … (+{len(row_nums) - 2} más)"
            first = rows[0] if rows else {}
            vals = first.get("values") if first else None
            if vals:
                parts = [f"{k}={v}" for k, v in list(vals.items())[:3]]
                desc = f"Filas repetidas ({count} en total): " + ", ".join(parts)
                val = ", ".join(f"{k}: {v}" for k, v in list(vals.items())[:5])
            else:
                desc = "Estas filas están completamente repetidas"
                val = None
            return {
                "descripcion": desc,
                "sugerencia": sug,
                "que_hacer": que_hacer,
                "fila": display_rows or None,
                "columna": None,
                "valor": val,
            }
        # Per-row entries (new format): values are identity + email columns.
        vals = item.get("values") or {}
        count = item.get("group_size") or item.get("size") or 1
        email_k = None
        for k in vals:
            if re.search(r"(?i)(email|correo|e-?mail|mail|contacto)", k):
                email_k = k
                break
        ident_parts = [f"{k}={v}" for k, v in list(vals.items()) if k != email_k]
        cols_text = ", ".join(ident_parts[:4])
        if email_k is not None:
            ev = vals.get(email_k)
            if ev in (None, "") or (isinstance(ev, str) and ev.strip().lower() in ("", "nan", "none", "null", "nat")):
                val = f"{email_k}: No tiene ningun email"
            else:
                val = f"{email_k}: {ev}"
        elif ident_parts:
            val = ", ".join(f"{k}: {v}" for k, v in ident_parts[:5])
        else:
            val = None
        desc = f"Fila duplicada (grupo de {count} filas repetidas)"
        if cols_text:
            desc += f": {cols_text}"
        return {
            "descripcion": desc,
            "sugerencia": sug,
            "que_hacer": que_hacer,
            "fila": fila,
            "columna": None,
            "valor": val,
        }

    if rule_name == "range_check":
        return {
            "descripcion": f"El valor '{item.get('value')}' está fuera del rango normal en la columna '{item.get('column')}'",
            "sugerencia": sug,
            "que_hacer": que_hacer,
            "fila": fila,
            "columna": item.get("column"),
            "valor": _safe_str(item.get("value")),
        }

    if rule_name in ("email_check", "phone_check", "zip_code_check", "rfc_curp_check",
                     "special_chars_check", "string_length_check", "trim_check",
                     "case_consistency_check", "invalid_date_check", "date_range_check",
                     "freshness_check", "missing_fk_check"):
        return {
            "descripcion": f"En la columna '{item.get('column')}', el valor '{item.get('value')}' no es válido",
            "sugerencia": sug,
            "que_hacer": que_hacer,
            "fila": fila,
            "columna": item.get("column"),
            "valor": _safe_str(item.get("value")),
        }

    if rule_name == "pattern_check":
        return {
            "descripcion": f"El valor '{item.get('value')}' no tiene el formato esperado en la columna '{item.get('column')}'",
            "sugerencia": sug,
            "que_hacer": que_hacer,
            "fila": fila,
            "columna": item.get("column"),
            "valor": _safe_str(item.get("value")),
        }

    if rule_name == "cardinality_check":
        w = item.get("warning", "")
        return {
            "descripcion": f"La columna '{item.get('column')}' tiene valores extraños: {w}",
            "sugerencia": sug,
            "que_hacer": que_hacer,
            "fila": fila,
            "columna": item.get("column"),
            "valor": w or None,
        }

    if rule_name == "correlation_check":
        cols = item.get("columns", "")
        corr = item.get("correlation")
        return {
            "descripcion": f"Hay una correlación alta ({corr}) entre las columnas: {cols}",
            "sugerencia": sug,
            "que_hacer": que_hacer,
            "fila": None,
            "columna": cols or None,
            "valor": _safe_str(corr) if corr is not None else None,
        }

    if rule_name == "distribution_check":
        flags = item.get("flags", [])
        return {
            "descripcion": f"La columna '{item.get('column')}' tiene una distribución anormal: {', '.join(flags)}",
            "sugerencia": sug,
            "que_hacer": que_hacer,
            "fila": fila,
            "columna": item.get("column"),
            "valor": ", ".join(flags),
        }

    if rule_name == "date_inconsistency_check":
        return {
            "descripcion": f"Relación de fechas incorrecta: {item.get('col1')}={item.get('val1')} es después de {item.get('col2')}={item.get('val2')}",
            "sugerencia": sug,
            "que_hacer": que_hacer,
            "fila": fila,
            "columna": f"{item.get('col1')} / {item.get('col2')}",
            "valor": f"{item.get('col1')}={item.get('val1')}, {item.get('col2')}={item.get('val2')}",
        }

    if rule_name == "latency_check":
        lh = item.get("latency_h")
        return {
            "descripcion": f"Retraso de {lh}h entre el evento ({item.get('event')}) y la carga ({item.get('ingest')})",
            "sugerencia": sug,
            "que_hacer": que_hacer,
            "fila": fila,
            "columna": None,
            "valor": f"{lh}h",
        }

    if rule_name == "sequential_integrity_check":
        msg = item.get("message") or f"Hay un salto en la secuencia de la columna '{item.get('column')}'"
        return {
            "descripcion": msg,
            "sugerencia": sug,
            "que_hacer": que_hacer,
            "fila": fila,
            "columna": item.get("column"),
            "valor": item.get("message"),
        }

    if rule_name == "referential_integrity_check":
        return {
            "descripcion": f"El valor '{item.get('value')}' en la columna '{item.get('column')}' no existe en la tabla '{item.get('missing_in')}'",
            "sugerencia": sug,
            "que_hacer": que_hacer,
            "fila": fila,
            "columna": item.get("column"),
            "valor": _safe_str(item.get("value")),
        }

    if rule_name == "row_completeness_check":
        nc = item.get("null_columns", [])[:5]
        return {
            "descripcion": f"Esta fila solo tiene el {item.get('completeness_pct')}% de datos completos. Columnas vacías: {', '.join(nc)}",
            "sugerencia": sug,
            "que_hacer": que_hacer,
            "fila": fila,
            "columna": None,
            "valor": f"{item.get('completeness_pct')}% completo",
        }

    if rule_name == "multivariate_outlier_check":
        vals = item.get("values")
        if vals:
            parts = [f"{k}={v}" for k, v in list(vals.items())[:4]]
            desc = "Combinación extraña de valores: " + ", ".join(parts)
            val = ", ".join(f"{k}: {v}" for k, v in list(vals.items())[:6])
        else:
            desc = "Se encontró una combinación extraña de valores en varias columnas"
            val = None
        return {
            "descripcion": desc,
            "sugerencia": sug,
            "que_hacer": que_hacer,
            "fila": fila,
            "columna": None,
            "valor": val,
        }

    if rule_name == "cross_consistency_check":
        return {
            "descripcion": f"No se cumple la regla interna: {item.get('rule', '')}",
            "sugerencia": sug,
            "que_hacer": que_hacer,
            "fila": fila,
            "columna": item.get("rule"),
            "valor": None,
        }

    if rule_name == "functional_dependency_check":
        return {
            "descripcion": f"Dependencia incumplida: {item.get('determinant')}={item.get('value')} debería corresponder a {item.get('dependent')}={item.get('dep_values')}",
            "sugerencia": sug,
            "que_hacer": que_hacer,
            "fila": fila,
            "columna": f"{item.get('determinant')} → {item.get('dependent')}",
            "valor": f"{item.get('determinant')}={item.get('value')}",
        }

    if rule_name == "derived_column_check":
        return {
            "descripcion": f"La columna '{item.get('column')}' tiene un resultado incorrecto: se esperaba {item.get('expected')} pero se obtuvo {item.get('actual')} (diferencia: {item.get('diff_pct')}%)",
            "sugerencia": sug,
            "que_hacer": que_hacer,
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
        return {
            "descripcion": desc,
            "sugerencia": sug,
            "que_hacer": que_hacer,
            "fila": fila,
            "columna": None,
            "valor": val,
        }

    if rule_name == "nit_valid":
        reason = item.get("reason")
        if reason == "dv_incoherente" and item.get("expected") is not None and item.get("observed") is not None:
            reason_text = f" (esperado {item['expected']}, registrado {item['observed']})"
        else:
            reason_text = f" ({_NIT_REASONS.get(reason, reason)})" if reason else ""
        warns = item.get("warning") or []
        warn_text = " Además: " + "; ".join(_NIT_WARNINGS.get(w, w) for w in warns) if warns else ""
        return {
            "descripcion": f"En la columna '{item.get('column')}', el valor '{item.get('value')}' no es un NIT válido{reason_text}{warn_text}",
            "sugerencia": sug,
            "que_hacer": que_hacer,
            "fila": fila,
            "columna": item.get("column"),
            "valor": _safe_str(item.get("value")),
        }

    if rule_name == "person_composite_similarity":
        gi = item.get("group_info")
        if gi:
            desc = f"Posible misma persona (confianza: {gi.get('composite_score', 0) * 100:.0f}%, grupo de {gi.get('group_size')})"
        else:
            desc = "Posible misma persona detectada"
        vals = item.get("values")
        val = None
        if vals:
            parts = [f"{k}={v}" for k, v in list(vals.items())[:4]]
            val = ", ".join(parts)
        return {
            "descripcion": desc,
            "sugerencia": sug,
            "que_hacer": que_hacer,
            "fila": fila,
            "columna": None,
            "valor": val,
        }

    # Fallback
    if "error" in item:
        return {
            "descripcion": f"Error: {item['error']}",
            "sugerencia": sug,
            "que_hacer": que_hacer,
            "fila": fila,
            "columna": None,
            "valor": None,
        }
    col = item.get("column")
    val = item.get("value")
    if col and val is not None:
        return {
            "descripcion": f"Valor anómalo en columna '{col}': {_safe_str(val)}",
            "sugerencia": sug,
            "que_hacer": que_hacer,
            "fila": fila,
            "columna": col,
            "valor": _safe_str(val),
        }
    if col:
        return {
            "descripcion": f"Problema en columna '{col}'",
            "sugerencia": sug,
            "que_hacer": que_hacer,
            "fila": fila,
            "columna": col,
            "valor": None,
        }
    if "message" in item:
        return {
            "descripcion": item["message"],
            "sugerencia": sug,
            "que_hacer": que_hacer,
            "fila": fila,
            "columna": None,
            "valor": None,
        }
    return {
        "descripcion": "Error de calidad de datos",
        "sugerencia": sug,
        "que_hacer": que_hacer,
        "fila": fila,
        "columna": None,
        "valor": None,
    }
