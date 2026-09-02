# QData Dev Log

## 2026-08-14 — nit_valid: regla de negocio corregida (base 6-10 dígitos, sanitizar ceros, warnings)

**Request**: el análisis de negocio indicó que el tope 8-15 era incorrecto: los NIT de personas naturales basados en cédula pueden tener 6-7 dígitos, y el 15 proviene solo del algoritmo de relleno del Módulo 11, no de la longitud real. Además, la DIAN acepta ciertos NIT especiales con ceros a la izquierda digitados en campos fijos → mejor SANITIZAR que rechazar. El usuario eligió: **10 válido + 11 como warning (informativo)**, **sanitizar ceros + avisar**, y **DIAN/RUES solo como recomendación** (no se implementa integración).

**Changes made**:
- `backend/qdata/rules/colombian_docs.py` `_validate_nit`: ahora devuelve `warnings: []` además de `reason`. Tras normalizar la base a dígitos: (1) sanitiza `base = base.lstrip("0")` (si queda vacía → `longitud_invalida`); (2) `len(base) < 6` → `longitud_invalida`; (3) `len(base) > 11` → `mas_de_11_digitos`; (4) si la base tenía ceros iniciales → warning `ceros_a_la_izquierda`; (5) si `len(base) == 11` → warning `longitud_elevada`. El DV (Módulo 11) se calcula sobre la base sanitizada. Se elimina la razón `ceros_a_la_izquierda` como fallo y `mas_de_15_digitos` → `mas_de_11_digitos`.
- `NitCheck.execute`: `warning_counts` (agregado por tipo de warning) + `warnings_sample` (hasta 50 filas `"fila N: 'valor' (tipo)"`) en el `details`; el detalle se agrega también cuando hay warnings sin fallos (`if n_fail or warning_counts`). Cada `sample_failure` lleva `warning: []` si la fila fallida tenía warnings. Recomendación actualizada (6-10 dígitos, 11 excepcional, contrastar contra RUT/RUES).
- `backend/qdata/core/descriptions.py`: maps `_NIT_REASONS`/`_NIT_WARNINGS` y rama `nit_valid` en `describe_error` (exports Excel/PDF con razones legibles; antes caía al fallback genérico).
- `frontend/src/lib/ruleDescriptions.ts`: `NIT_REASONS` actualizado (`longitud_invalida` 'debe tener entre 6 y 10 dígitos', `mas_de_11_digitos` 'supera los 11 dígitos', se quita `ceros_a_la_izquierda`); nuevo `NIT_WARNINGS`; `describeError` de nit_valid agrega "Además: <warnings>"; descripción/que-hacer/sugerencia mencionan 6-10 y contrastar con RUT/RUES.

**Verification**:
- Sintéticos en contenedor (15 casos): `123`/`12345`→longitud_invalida, `000000000`/`000000001`→longitud_invalida + warning ceros, `01234567`→válido + warning ceros (strip→1234567), `12345678`/`8001234567`→válidos sin warnings, `12345678901`→válido + warning longitud_elevada, `012345678901`→válido + doble warning, 16 dígitos→mas_de_11_digitos, `800.123.456-7`→dv_incoherente (expected 5), `830000000-1`→válido, DV por columna→válido, vacío→vacio, `ABC123456`→caracteres_invalidos.
- `NitCheck.execute`: df mixto → `failed=1` con `reason_counts={longitud_invalida:1}` y `warning_counts={ceros_a_la_izquierda:1, longitud_elevada:1}`; df solo con warnings → `passed=True, failed=0` y `details=1` con `warning_counts` (los warnings no fallan).
- `npx tsc --noEmit`: solo errores pre-existentes de `@dnd-kit` en `Connections.tsx`.
- Backend reiniciado y healthy (código montado por volumen, sin rebuild).

**Gotchas**:
- `_nit_dv` mantiene el relleno a 15 dígitos: es parte del algoritmo Módulo 11 (los ceros de padding no alteran la suma), NO una regla de longitud del documento.
- Los warnings conviven con fallos: una base fallida (p.ej. 3 dígitos) que además tenía ceros acumula warning en la misma fila del `sample_failure` (informativo).
- `warnings_sample` son strings (`"fila 0: '012345678' (ceros_a_la_izquierda)"`) para que `renderVal` de `DetailsTable` (join de arrays) los muestre legibles; los dicts se renderizarían `[object Object]`.
- Reportes viejos con `mas_de_15_digitos`/`ceros_a_la_izquierda` en `reason` siguen renderizando (fallback `NIT_REASONS[k] || k`).

## 2026-08-14 — nit_valid: validación de longitud mínima (8 dígitos) y ceros a la izquierda

**Problem**: `_validate_nit` solo validaba el tope superior (≤15 dígitos) y los caracteres; un número de 1-7 dígitos ("123", "45") o con ceros a la izquierda ("000000001") pasaba como NIT válido. Los NIT reales de la DIAN tienen 8-15 dígitos.

**Changes made**:
- `backend/qdata/rules/colombian_docs.py` `_validate_nit`: tras normalizar `base` (solo dígitos) se valida en orden — `len(base) < 8` → `longitud_invalida`; `len(base) > 15` → `mas_de_15_digitos`; `base[0] == "0"` → `ceros_a_la_izquierda`. La clasificación jurídica/natural ya no puede tocar ceros iniciales (se rechazan antes). Recomendación actualizada ("número entre 8 y 15 dígitos, sin letras ni ceros a la izquierda").
- `frontend/src/lib/ruleDescriptions.ts`: `NIT_REASONS` agregados `longitud_invalida: 'debe tener entre 8 y 15 dígitos'` y `ceros_a_la_izquierda: 'no debe iniciar con ceros'`.

**Verification**:
- Sintéticos en contenedor (13 casos ok): `123`→longitud_invalida, `000000000`/`000000001`/`01234567`→ceros_a_la_izquierda, `12345678` (mínimo 8)→válido, `8001234567`→válido, `1234567890123456`→mas_de_15_digitos, `800.123.456-7`→dv_incoherente (expected 5), `830000000-1`→válido, `830000000`+col DV `1`→válido, vacío→vacio, `ABC123456`→caracteres_invalidos. `NitCheck.execute` sobre df: `total=5 failed=3` con `reason_counts={longitud_invalida:1, ceros_a_la_izquierda:1, mas_de_15_digitos:1}`.
- `npx tsc --noEmit`: solo errores pre-existentes de `@dnd-kit` en `Connections.tsx`.

**Gotchas**:
- El DV por columna (autoritativo) se evalúa DESPUÉS de longitud/ceros: un `base` inválido nunca llega a calcular Módulo 11 (no se genera `expected`).
- `longitud_invalida` en NIT comparte clave con `cedula_valid` pero tienen textos distintos (cada regla tiene su propio `*_REASONS`).

## 2026-08-13 — Fix nit_valid: validar contra la columna de dígito de verificación (perDigitoVerificacion)

**Problem**: Tras el fix por tipo de documento, `nit_valid` seguía mostrando `0/48856 (0.00%)` en genesys: los NIT reales SÍ traen DV pero en una columna separada (`perDigitoVerificacion`: `1002393387`→9, `1002735765`→9, `10135629`→5) que la regla ignoraba. Además los proyectos de prueba tenían el query y `selected_columns` SIN esa columna.

**Changes made**:
- `backend/qdata/rules/person_fields.py`: nuevo `doc_dv_column(columns)` (regex `digito.*verificacion|dverif|verificacion|\bdv\b`; no confunde con `perNumeroIdentificacion`).
- `backend/qdata/rules/colombian_docs.py`: `_validate_nit(value, check_digit, dv_column_value=None)` — el DV de la columna es autoritativo y tiene prioridad sobre el DV inline con guion; `_is_na` para NaN/None. `NitCheck.execute`: si `check_digit=True` y existe columna DV, la usa por fila (`dv_col` en `details`). Con `check_digit=False` la columna DV se ignora.
- `frontend/src/pages/Analyze.tsx`: texto del panel aclara que con "Sí" valida contra la columna de DV de la fuente o el DV con guion.
- **Datos**: los 7 proyectos NIT se actualizaron (`source_config.query` + `selected_columns` con `perDigitoVerificacion`) y se re-ejecutaron.

**Verification**:
- Sintéticos (16 ok / 0 fail): `doc_dv_column` detecta `perDigitoVerificacion` y no `perNumeroIdentificacion`; columna DV `9.0`→9 (float64); `10135629` DV 5→dv_incoherente expected 9 observed 5; `800123456` DV 7→dv_incoherente expected 5 observed 7; `check_digit=False` ignora la columna DV; columna DV autoritativa sobre inline (`800123456-7` + columna 5 → válido); `_nit_dv("1002393387")=9`, `("10135629")=9`, `("800123456")=5`.
- CORRIDA REAL genesys (query actualizado): `total=48856, failed=1, dv_column=perDigitoVerificacion, scope=doc_number`, `reason_counts={dv_incoherente:1}`, `dvs_present=48797` (59 NITs sin DV), clasificación `juridica=40148, natural=8708`. Único fallo: `7823850141991` → expected 9 observed 1.
- Re-runs API de los 7 proyectos: con `check_digit=True` → `total=48856, failed=1`; con `check_digit=False` → `total=48856, failed=0`.
- `npx tsc --noEmit`: limpio salvo errores pre-existentes de `@dnd-kit` en `Connections.tsx`.

**Gotchas**:
- El `df` que ve la regla es `query` ∩ `selected_columns` del proyecto (rerun hace `df[selected_columns]`). Si la columna DV no está en AMBOS, la regla no la ve → 0 fallos. El fix del source_config fue tan necesario como el de la regla.
- `perDigitoVerificacion` se carga como float64 (decimal) → `_norm_phone_str("9.0")`→"9"; NaN se ignora (ausencia de DV no es fallo, 59 filas).
- Solo 1 DV incoherente en los 48856 NIT reales: el pct se muestra 0.00% pero `failed=1` es real.

## 2026-08-13 — Fix nit_valid: detección de columna NIT por tipo de documento (perNumeroIdentificacion + perTipoIdentificacion='NIT')

**Problem**: En el análisis real sobre genesys Persona, la regla `nit_valid` reportaba `0/0 (0.00%)` (no calculaba nada): `nit_columns()` solo buscaba columnas cuyo NOMBRE contenga "nit", pero los NIT viven en `perNumeroIdentificacion` cuando `perTipoIdentificacion='NIT'` (48856 filas). `cedula_valid` sí calculaba en la misma corrida (total 855010). Además, los NIT reales de Persona NO traen DV (muestras `1002393387`, `1002735765`, `1002606032`).

**Changes made** (solo `backend/qdata/rules/colombian_docs.py`):
- `NitCheck.execute` reescrito: el orden de detección de la columna a validar es (1) `self.columns` explícito → scope `explicit`; (2) columna con nombre "nit" (`nit_columns`) → scope `nit_column`; (3) fallback `doc_number_column` + filtro por tipo NIT → scope `doc_number`. Si existe columna de tipo documento pero no hay ningún valor NIT (`_is_nit_type` sobre `_NIT_TYPE_NORMS` = `NIT`, `NITDIGITODERIFICACION` normalizados), retorna early `passed=True, total=0` (no se puede distinguir). Cada `details[]` ahora incluye `scope`.
- `_is_nit_type` compara tipos NORMALIZADOS EN MAYÚSCULAS (mismo patrón `_is_cc_type`): `.upper()` + elimina no-alfanuméricos; acepta `NIT`, `NIT_DIGITO_VERIFICACION`, `NITDIGITODERIFICACION`, etc.

**Verification**:
- Sintéticos (18 ok / 0 fail, en contenedor): Módulo 11, columna dedicada "nit", escenario genesys (solo filas NIT validadas, `800123456-7`→dv_incoherente expected=5 observed=7, dos DVs malos), tipo de documento sin valores NIT → total=0 (skip), sin columna de tipo → valida todas, `check_digit=False`, `resolve_rules` con config.
- CORRIDA REAL sobre Persona genesys (proyecto "NIT CON DV", 1076239×7): `total=48856, failed=0, scope=doc_number` — coincide con el value_counts de `perTipoIdentificacion`.
- Re-runs de los 7 proyectos de prueba NIT vía API `POST /processes/{id}/rerun` (backend reiniciado): los 7 reportes nuevos muestran `total=48856, failed=0` en `rule_totals` (los NIT reales sin DV → 0 fallos, correcto por diseño).
- `npx tsc --noEmit`: limpio salvo errores pre-existentes de `@dnd-kit` en `Connections.tsx`.

**Gotchas**:
- La causa del `0/0` original: `nit_columns()` es por NOMBRE de columna; en genesys no existe ninguna columna llamada "nit", así que el fallback `doc_number_column` + filtro por tipo es imprescindible.
- `reportes.rule_totals` = lista de dicts `{rule_name, passed, failed, total, severity}`; el modelo `Report` NO tiene atributo `failed`.
- Re-run igual que el botón de la UI: `POST /processes/{id}/rerun` recarga la fuente completa y vuelve a ejecutar; los reportes viejos se sobrescriben/crean nuevos.
- Scripts de verificación temporales se ejecutaron dentro del contenedor (`/app/...`) y se eliminaron al terminar.

## 2026-08-13 — Nuevas reglas: Cédula de Ciudadanía (cedula_valid) y NIT (nit_valid, Módulo 11 DIAN)

**Request**: crear dos reglas de validación de documentos colombianos. CC: solo dígitos + longitud {6,7,8,10} (NUIP de 10 dígitos inicia en 1), clasificación informativa por segmento (ancestros/adulto mayor <20M de 6-7 dígitos, contemporáneo 8 dígitos, jóvenes NUIP 10 dígitos) SIN rechazo por rango; si la fuente tiene columna de tipo de documento (ej. `perTipoIdentificacion`) validar SOLO filas con tipo CC, si no, validar todas. NIT: se evalúa UNA columna seleccionada (auto-detectada por regex, configurable vía `columns`); DV opcional — si el valor trae guion+dígito se valida con Módulo 11 DIAN (toggle Sí/No controla si se aplica el cálculo); ausencia de DV NO es fallo; aceptar y normalizar separadores (`800.123.456-7`, `800123456-7`, `8001234567`); rango/clasificación (jurídica inicia 8/9, natural = cédula) solo informativo, nunca rechaza.

**Changes made**:
- `backend/qdata/rules/person_fields.py`: helpers `doc_number_column()`, `doc_type_column()`, `nit_columns()` (regex `\bnit\b` word-boundary para no matchear "unidad").
- `backend/qdata/rules/colombian_docs.py` (NUEVO): `CedulaCheck` (name=`cedula_valid`) y `NitCheck` (name=`nit_valid`, `check_digit: bool = True`, `columns` opcional). Ambos siguen el patrón `PhoneCheck`: muestrean TODAS las fallas con `values` = fila completa, sin tope intra-regla (reports.py los topa en `MAX_SAMPLE_FAILURES_GENERIC=5000`). Reusan `_norm_phone_str` para columnas numéricas (int64/float64 `.0`). CC: si `doc_type_column()` existe y tiene valores CC-ish (`CC`, `C.C.`, `CEDULA DE CIUDADANIA` normalizados), valida solo esas filas; si no, todas. NIT: `_nit_dv` = Módulo 11 DIAN con pesos `(3,7,13,17,19,23,29,37,41,43,47,53,59,67,71)` derecha→izquierda rellenando a 15 dígitos (derecha × 3); `dv = residuo si residuo<=1 else 11-residuo`. Detalles por columna con `reason_counts`, `clasificacion`, `check_digit`, `dvs_present`, `dvs_checked`. Razones: `letras_o_caracteres_no_numericos`, `longitud_invalida`, `nuip_debe_iniciar_en_1` (CC); `caracteres_invalidos`, `formato_dv_invalido`, `mas_de_15_digitos`, `dv_incoherente` (con `expected`/`observed`), `vacio` (NIT).
- `backend/qdata/core/engine.py`: import + `RULE_REGISTRY["cedula_valid"]`, `RULE_REGISTRY["nit_valid"]` + agregados al grupo `formato`.
- `backend/qdata/web/routes/rules.py`: `RULE_METADATA["cedula_valid"]` ("Cédula válida") y `["nit_valid"]` ("NIT válido").
- `frontend/src/lib/ruleDescriptions.ts`: `RULE_DISPLAY_NAMES` (Cédulas inválidas / NIT inválidos), GLOSARIO, QUE_HACER, SUGERENCIAS, `describeError` para ambas (con razones humanas y `esperado/registrado` para DV), `describeDetail` (grupo de formato).
- `frontend/src/pages/Analyze.tsx`: estado `nitCheckDigit` (default true) + payload `rule_configs.nit_valid = {check_digit}` + panel bajo la regla con toggle Sí/No.

**Verification**:
- Sintéticos en contenedor (32 checks, 0 fail): Módulo 11 `830000000→1`, `900336362→9`; CC válidas 6/7/8/10 dígitos, fallos en 9/11 dígitos, 10 sin iniciar en 1, letras, puntos; filtro por `perTipoIdentificacion` solo CC (CE/TI/NIT con números no-CC NO se marcan); NIT con/sin DV, separadores, int64/float64, `830000000-7`→dv_incoherente (expected 1, observed 7), `830000000-01`→formato_dv_invalido, 16 dígitos→mas_de_15, `ABC123`→caracteres_invalidos, `check_digit=False` deja de fallar por DV, clasificación jurídica/natural, `resolve_rules` con config.
- API `GET /rules/groups` (token, backend reiniciado): `cedula_valid` y `nit_valid` presentes en el grupo `formato`.
- `npx tsc --noEmit`: limpio salvo errores pre-existentes de `@dnd-kit` en `Connections.tsx`.

**Gotchas**:
- Algoritmo Módulo 11: aplicar pesos de DERECHA a izquierda (dígito de las unidades × 3) rellenando con ceros a la izquierda hasta 15 — el padding no altera la suma (ceros × peso). `_nit_dv` usa `_NIT_WEIGHTS[14 - i]`. Verificado con ejemplos publicados: `830.000.000-1` y `900.336.362-9`.
- `_is_cc_type` compara contra tipos NORMALIZADOS EN MAYÚSCULAS (`CC`, `CEDULA`, `CEDULACIUDADANIA`, `CEDULADECIUDADANIA`): `_norm_doc_type` hace `.upper()` y elimina no-alfanuméricos. Bug inicial: tupla en minúsculas → el filtro por tipo nunca aplicaba y se validaban todas las filas.
- Filtro por tipo CC: si `doc_type_column` existe pero no hay valores CC-ish (p.ej. códigos numéricos), se validan TODAS las filas (decisión del usuario). Con `perTipoIdentificacion` real de genesys (CC/CE/NIT) el filtro aplica.
- El tope de sample_failures lo aplica `reports.py` (`MAX_SAMPLE_FAILURES_GENERIC=5000`), no la regla — mismo patrón que phone_check.

## 2026-08-12 — Detalle de errores: la tabla "Registros del grupo" muestra solo las columnas seleccionadas de la fuente

**Request**: en todos los reportes, la tabla "Registros del grupo" (detalle de error de `personas_similares*`, `fuzzy_*`, `similar_dob`, `person_composite_similarity`) mostraba TODAS las columnas de la fila almacenada, no solo los campos seleccionados en la fuente de datos para el análisis. Ejemplo real V3 genesys: `values` guardaba 7 columnas (6 seleccionadas + `perRazonSocial` del query) y `source_config.selected_columns` tenía 6.

**Decisiones del usuario**: (1) aplicar el filtro SOLO a "Registros del grupo"; (2) si la fuente no tiene `selected_columns` (legacy), mantener el comportamiento actual; (3) tomar `selected_columns` de `source_config` actual del proyecto (sin snapshot en el reporte).

**Changes made**:
- `backend/qdata/web/routes/reports.py` `get_report`: devuelve `selected_columns` en la respuesta (de `project.source_config.get("selected_columns") or []`). Antes solo devolvía `source_query`.
- `frontend/src/pages/ErrorDetail.tsx`: `groupMemberKeys` = intersección de `report.selected_columns` con las claves del `values` del miembro del grupo (`selectedIntersection`); si `selected_columns` vacío O intersección vacía (fuente editada), cae a `Object.keys(memberVals0)`. La tabla "Registros del grupo" usa `groupMemberKeys` en header y celdas (antes `recordEntries`). "Registros duplicados" (duplicate_check) y "Registro completo" (reglas por fila) NO cambian.

**Verification**:
- API `GET /reports/{id}`: V3 genesys (`b9ecdab8…`) devuelve `selected_columns` con las 6 columnas (values tiene 7 → la tabla filtra `perRazonSocial`). `phone_check` (`80f86057…`) devuelve `selected_columns=['PerTelefo']`.
- `npx tsc --noEmit`: limpio salvo errores pre-existentes de `@dnd-kit` en `Connections.tsx`.
- Backend reiniciado y healthy.

**Gotchas**:
- `values` en los grupos se guarda de la fila del df cargado (query completa), NO de `selected_columns` — por eso la intersección es necesaria aunque `selected_columns` ⊆ query.
- La tabla "Registros del grupo" usa `member.values || item.values`; la intersección se calcula contra `groupMembers[0]?.values || item.values` (todos los miembros comparten keys).

## 2026-08-12 — Detalle de errores: muestra TODOS los fallos en personas_similares_* (se acabó el tope de 100)

**Problem**: En el detalle de errores de `personas_similares_v3` (genesys, 1417 fallos), la lista "Detalle de errores" mostraba solo `(100)`. La BD guardaba los 1417 (`sample_failures` por fila, tope interno de la regla = 100000), pero `GET /reports/{id}` los recortaba a `MAX_SAMPLE_FAILURES=100` antes de servir.

**Changes made**:
- `backend/qdata/rules/base.py`: nueva constante `MAX_SAMPLE_FAILURES_GENERIC = 5000` y tupla `PERSONAS_SIMILARES_RULES = ("personas_similares", "personas_similares_v2", "personas_similares_v3")`. `MAX_SAMPLE_FAILURES=100` se conserva solo para el tope de grupos de `duplicate_check` y para `custom.py`.
- `backend/qdata/web/routes/reports.py` `get_report`: el recorte ahora es `elif rule_name not in PERSONAS_SIMILARES_RULES and len(sfs) > MAX_SAMPLE_FAILURES_GENERIC: sfs[:MAX_SAMPLE_FAILURES_GENERIC]`. Es decir, V1/V2/V3 sirven TODOS sus fallos; el resto de reglas se topan en 5000 (antes 100).
- Frontend sin cambios: `RuleDetail.tsx` ya pagina (25/50/100/500/Todos).

**Verification** (API con token, backend reiniciado):
- V3 genesys (`b9ecdab8…`): `failed=1417` y `sample_failures_served=1417` — antes solo 100.
- `phone_check` (`80f86057…`, 95166 fallos): al quitar el tope del todo devolvía **402MB en 43.3s**; con el tope de 5000 devuelve **28.8MB en 7.2s**. El usuario eligió "eximir personas_similares* + tope 5000 para el resto" tras ver esos números.
- `npx tsc --noEmit`: solo errores pre-existentes de `@dnd-kit` en `Connections.tsx`.

**Gotchas**:
- `reports` con muchas fallas pueden ser enormes en BD (p.ej. `pg_column_size(result_json)` > 256MB en phone_check); `jsonb_array_length` sobre esas arrays falla con "total size of jsonb array elements exceeds the maximum of 268435455 bytes" — usar `pg_column_size` en su lugar.
- El tope de 5000 sigue dejando respuestas grandes (~28MB) cuando cada `sample_failure` trae la fila completa (196 columnas); el `timeout` de axios es 120s.

## 2026-08-11 — V3: quitar el selector interno de campos; usa los campos de la fuente

**Request**: tras implementar la selección manual de campos DENTRO de la regla V3 (opción 2), el usuario pidió quitar ese selector interno: V3 debe usar los campos seleccionados en el selector de Columnas de la fuente de datos (panel izquierdo de Analyze, `selectedColumns`) y mostrar los campos que se van a comparar. Se implementó así, sin checkboxes dentro de la regla.

**Changes made** (solo `frontend/src/pages/Analyze.tsx`):
- Eliminado estado `v3Columns`, handlers `toggleV3Col`/`toggleV3All`, función `guessV3Columns`, y el bloque UI "Campos a comparar (n/total)" con checkboxes bajo el panel V3 (todo el selector interno de campos de V3).
- `handleSubmit`: `rule_configs.personas_similares_v3.columns = hasCols ? selectedColumns : undefined` (mismo patrón que V1). `hasCols` = selección parcial de columnas en el selector de la fuente (`selectedColumns` entre 1 y n-1 del preview).
- El panel V3 queda solo con los chips de modo + barra de sensibilidad: **sin** selector interno de campos y **sin** lista read-only de columnas (el usuario pidió quitar también la lista informativa). La nota de "Reproduce el análisis original de julio" se conserva.
- Import `Check` eliminado de lucide-react (ya no se usa).

**Verification**:
- `npx tsc --noEmit` limpio salvo errores pre-existentes de `@dnd-kit` en `Connections.tsx`.
- Frontend dev server (vite) recarga los cambios sin rebuild.

**Gotchas**:
- Si el usuario deja TODAS las columnas de la fuente marcadas, `hasCols=false` → `columns=undefined` → V3 usa `_default_columns` (que descarta `perRazonSocial`). Para el caso tipo doc + razón social el usuario debe marcar solo esas 2 columnas en el selector de la fuente.
- El backend no cambió: `SimilarPeopleCheckV3` sigue aceptando `columns` desde `rule_configs`.

## 2026-08-11 — V3: selección manual de campos a comparar en el panel de Analyze

**Request**: el usuario detectó que la corrida V3 al 90% sobre la fuente `ppp` (solo 3 columnas: `perNumeroIdentificacion`, `perRazonSocial`, `perTipoIdentificacion`) produjo un grupo de 493 falsos positivos (cédulas consecutivas con nombres totalmente distintos). Causa: `_default_columns` clasificó `perRazonSocial` como `generic` (no matchea id/name/surname en `_classify_column`), así que V3 comparó SOLO `id`+`tipo` (ambos constantes/1.0 y cédulas consecutivas → composite 0.95 ≥ 0.90), encadenándose por transitividad. El usuario pidió poder hacer el análisis con 2+ campos elegidos manualmente (caso: tipo de documento + razón social como texto completo) y eligió la **opción 2: selección manual de campos en el panel** (patrón V2, sin pesos).

**Changes made** (solo frontend — backend ya aceptaba `columns` desde `rule_configs`):
- `frontend/src/pages/Analyze.tsx`:
  - Estado `v3Columns: string[]`.
  - `toggleRule` (V3) preselecciona `guessV3Columns(preview.columns)`; el `useEffect` de `previewData` también preselecciona si V3 está activa (default selecciona todas las reglas).
  - `guessV3Columns(cols)`: filtra columnas de persona por regex (cedula/identif/nit/dni/tipo doc/razon social/nombre/apellido), excluyendo PK puras (`perid`/`_id`/`^id$`), fechas, `creado`/`modificacion`, `digito`, etc.
  - Handlers `toggleV3Col`/`toggleV3All` (Ninguno/Todos) y bloque UI "Campos a comparar (n/total)" con checkboxes bajo el panel V3.
  - `handleSubmit`: `rule_configs.personas_similares_v3 = {mode, threshold, columns: v3Columns.length ? v3Columns : undefined}`.

**Verification**:
- `resolve_rules(['personas_similares_v3'], {..., columns:['perTipoIdentificacion','perRazonSocial']})` → `mode=profundo threshold=0.9 columns=[...]` OK (backend sin cambios).
- Simulación del caso `ppp` con `columns=['perTipoIdentificacion','perRazonSocial']` al 90%: **1 grupo real de 3** (JOSE FERNANDO GRANADOS PULIDO con cédulas 1002330922/1002330923/1002330931, composite 0.9082) — desaparece el grupo de 493 de personas distintas (KAREN/LUIS/DIEGO ya no agrupan). Duplicado exacto (razón social idéntica) → composite 1.0 → excluido (lo cubre `duplicate_check`).
- `npx tsc --noEmit` limpio salvo errores pre-existentes de `@dnd-kit` en `Connections.tsx`.

**Gotchas**:
- En V3 no hay pesos: es promedio igual-pesado de los campos elegidos. Por eso `perTipoIdentificacion` (constante 1.0) infla el composite; al incluir `perRazonSocial` (o nombres/apellidos) se diluye y los falsos positivos por cédulas consecutivas desaparecen.
- La auto-detección `_default_columns` sigue descartando `perRazonSocial` (generic); si el usuario no selecciona campos, el riesgo de falsos positivos en fuentes reducidas persiste — la selección manual es la salida para esos casos.

## 2026-08-11 — Panel de configuración para Buscar Persona V3 en Analyze (modo + sensibilidad)

**Request**: el usuario confirmó que al hacer un nuevo análisis, la regla `personas_similares_v3` debe mostrar los controles de búsqueda como V1/V2 (chips "⚡ Búsqueda Rápida" / "🧠 Búsqueda Profunda" + barra de sensibilidad %). Esto cambia la decisión previa de "Solo defaults sin panel". El panel modifica `mode`/`threshold`; las columnas se siguen auto-detectando con `_default_columns` (el usuario no elige campos). — **ACTUALIZADO 2026-08-11**: ahora también permite seleccionar los campos manualmente (ver log "V3: selección manual de campos").

**Changes made**:
- `frontend/src/pages/Analyze.tsx`: estado `v3Mode` (default `'profundo'`) y `v3Threshold` (default `90`); `useEffect` resetea threshold a 90/80 según modo; `handleSubmit` arma `rule_configs.personas_similares_v3 = {mode, threshold: v3Threshold/100}`; bloque UI idéntico al de V1/V2 (chips modo + range 50-95) bajo `rule.name === 'personas_similares_v3'`, con nota "Reproduce el análisis original de julio (profundo, 90%)".
- Backend sin cambios: `SimilarPeopleCheckV3.__init__` ya acepta `mode`/`threshold` (threshold default 0.90 profundo / 0.80 rápido); la persistencia y reuso de `rule_configs` en re-runs ya funciona (heredado de V2).

**Verification**:
- `npx tsc --noEmit` limpio salvo errores pre-existentes de `@dnd-kit` en `Connections.tsx` (no relacionados).
- Frontend es dev server (vite `--host 0.0.0.0`): los cambios se reflejan sin rebuild.

**Gotchas**:
- La barra de progreso intra-regla de V3 (fases blocking/scoring/clustering → "Buscando candidatos"/"Similitud"/"Agrupando") ya funcionaba end-to-end (genérica en `analyze.py` `_RuleProgress` + barra 2 en ProcessDetail); el pedido del usuario era el PANEL de configuración, no la barra de progreso.

## 2026-08-11 — PersonasSimilaresV3 ("personas_similares_v3") reproduce el análisis original de julio

**Objective**: crear la regla `personas_similares_v3` que reproduce exactamente el comportamiento original de "personas similares" que generó el análisis genesys de julio ("PERSONAS SIMILARES OLD": **1417/1076239 = 0.13%**, 145 grupos), antes de los cambios posteriores (V1/V2). Solo defaults (sin panel de configuración): `mode=profundo, threshold=0.90, columns=None` → auto-detect id+name+surname.

**Changes made**:
- `backend/qdata/rules/person_dedup_v3.py` (NUEVO): clase `SimilarPeopleCheckV3` (name=`personas_similares_v3`). Replica verbatim la rama de columnas explícitas de V1 (`SimilarPeopleCheck` en `person_dedup_rules.py`): blocking multi-paso por primera letra de CADA columna (profundo) o solo la primera (rápido), `_name_similarity_deep` (max lev/token_sort), promedio compuesto igual-pesado, `composite >= threshold and < 1.0` (excluye duplicados exactos), `_find_connected_components`. Salida `details.type="personas_similares_groups"` (mismo que V1) con `{groups[{group_size, composite_score, mode, columns, rows}], total_groups, mode, columns}` + `sample_failures`. Progreso con `progress_callback` (blocking→scoring batching 5000→clustering) + `log_callback`.
- **`_default_columns`** (V3 propio, NO `_auto_detect_columns` de V1): usa `_classify_column` (de V2) que clasifica con regex precisos; excluye PK puros (`perId`/`id`/`_id`) cuando hay más columnas id descriptivas; ordena id+name+surname. Para genesys produce exactamente las 6 columnas del reporte jul: `perNumeroIdentificacion, perTipoIdentificacion, perPrimerNombre, perSegundoNombre, perPrimerApellido, perSegundoApellido` (sin `perId`). El `_auto_detect_columns` de V1 es defectuoso: matchea `"id"` como substring dentro de `"apellido"` → falsos positivos en `id`.
- `backend/qdata/core/engine.py`: import + `RULE_REGISTRY["personas_similares_v3"]` + agregado al grupo `personas_similares`.
- `backend/qdata/web/routes/rules.py`: `RULE_METADATA["personas_similares_v3"]` ("Buscar Persona V3 (Original)", grupo `personas_similares`).
- `frontend/src/lib/ruleDescriptions.ts`: label, descripciones, glosario y ramas de `personas_similares` para V3.
- `frontend/src/pages/ErrorDetail.tsx` y `RuleDetail.tsx`: `GROUP_RULE_TYPES['personas_similares_v3']='personas_similares_groups'` (comparte render de V1). Sin panel en `Analyze.tsx` en ese momento (decisión posterior revertida: ver log "Panel de configuración para Buscar Persona V3" arriba).

**Verification**:
- **Baseline V3 con defaults contra genesys (1,076,239 filas, ~10 min)**: `failed=1417, pct=0.13, total_groups=145`, columns = las 6 de persona → **MATCH exacto** con el reporte jul `534c91ce` (verificado en BD: mismo `total_groups=145`, misma estructura de detail y `columns`).
- Estructura del reporte jul confirmada en BD: `result_json.results[0].details[0] = {type: personas_similares_groups, groups[{composite_score, mode: profundo, columns, rows}], columns, total_groups}` — idéntica a la que produce V3.
- Sintéticos en contenedor: id con 1 dígito cambiado → 2 failed; grupo transitivo 3 cédulas similares → 3 failed; duplicados exactos (composite=1.0) NO marcados; sin columnas de persona → passed. (OJO: cédulas muy distintas como 111/222/333 dan composite 0.667 < 0.90 → correctamente NO marcadas; cédula idéntica + nombre normalizado → composite 1.0 → excluido.)
- `RULE_REGISTRY` y `RULE_GROUPS` incluyen `personas_similares_v3`.
- TypeScript compila limpio (`npx tsc --noEmit`; pre-existentes `@dnd-kit` en `Connections.tsx` quedan, no relacionados).

**Gotchas**:
- `load_data(source_type, connection_string, query, file_path, storage_mode='connection')` — `storage_mode` es kwarg de `load_data`, NO de `execute`.
- La firma de la corrida baseline: `load_data('sqlserver', cs, 'SELECT * FROM Persona', '', storage_mode='connection')` y `r.execute(df, engine=cs)`; sin nrows (el cache del cubo con nrows=0 devuelve df vacío).
- `_auto_detect_columns` (V1) matchea `"id"` como substring → `perPrimerApellido`/`perSegundoApellido` entran en `id`; no usarlo para reproducir columnas de julio.

## 2026-08-11 — Nueva regla "personas_similares_v2" (Buscar Persona V2): campos + pesos configurable

**Request**: crear una regla nueva de personas similares donde el usuario selecciona los campos de la fuente y se aplican algoritmos de similitud para encontrar un porcentaje de similitud entre registros, con el objetivo de detectar personas creadas dos veces con pequeñas diferencias (cédula con dígito cambiado, mismo nombre, etc.). Decisiones del usuario: V2 coexiste con V1, pesos configurables por campo, persistir config para re-runs, dos modos (rápido/profundo).

**Changes made**:
- `backend/qdata/rules/person_dedup_v2.py` (NUEVO): clase `SimilarPeopleCheckV2` (name=`personas_similares_v2`), reutiliza helpers de `person_dedup_rules`. Clasifica cada columna seleccionada por tipo (`_classify_column`: id/name/surname/dob/phone/email/generic) y aplica similitud específica por tipo (`_id_similarity`, `_name_similarity`, `_date_similarity` con window_days, `_phone_similarity` normalizada a dígitos). Blocking multi-paso por tipo: ID por prefijo `len-2` **y** sufijo `len-2` dígitos (captura cambios/transposición de 1-2 dígitos en cualquier posición), nombre por 1ª letra de los 2 primeros tokens, fecha por año, teléfono por últimos 6 dígitos. Score compuesto ponderado (pesos de usuario renormalizados a suma 1, o defaults por tipo: id .30, name .25, surname .20, dob .15, phone/email/genérico .10), umbral default 0.80 rápido / 0.70 profundo, excluye pares con score exactamente 1.0 (duplicados exactos los cubre `duplicate_check`). Salida `details.type="personas_similares_v2_groups"` con `groups[{group_size, composite_score, fields, mode, columns, rows}]` + `sample_failures` por fila con `group_info`. Progreso con `progress_callback` (blocking→scoring batching 5000 con ETA/field_avgs→clustering) + `log_callback` (mismo patrón V1, alimenta chips "Buscando candidatos"/"Similitud").
- `backend/qdata/core/engine.py`: import + `RULE_REGISTRY["personas_similares_v2"]` + agregado al grupo `personas_similares`.
- `backend/qdata/web/routes/rules.py`: entrada `RULE_METADATA["personas_similares_v2"]` ("Buscar Persona V2", grupo `personas_similares`).
- **Persistencia de config**: `backend/qdata/db/models.py` agrega `Project.rule_configs` (JSON); migración `b2c3d4e5f6a7` (down_revision del head real `c0d1e2f3a4b5`, verificado el árbol de migraciones). `analyze.py` (sync `POST /analyze` y background `POST /analyze/start`) ahora persiste `req.rule_configs`; `processes.py` `get_process` lo devuelve y `rerun_process` lo reutiliza (filtrado a reglas activas; el fallback de `duplicates` se conserva). Esto también arregla la pérdida de config en re-runs de V1.
- `frontend/src/pages/Analyze.tsx`: panel para V2 bajo la regla — modos ⚡Rápida/🧠Profunda, slider de sensibilidad 50-95, multi-select de campos a comparar con checkboxes y un slider de peso (%) por campo (`guessV2Weight` con defaults por tipo; al activar la regla se preseleccionan todas las columnas de la vista previa). `handleSubmit` arma `rule_configs.personas_similares_v2 = {mode, threshold, columns, weights}` (pesos fraccionarios).
- `frontend/src/lib/ruleDescriptions.ts`: label "Personas similares V2", glosario, que-hacer, sugerencia, rama `describeError` compartida con V1 (usa `group_info.composite_score`), y `describeDetail` para `personas_similares_v2`.
- `frontend/src/pages/ErrorDetail.tsx` y `RuleDetail.tsx`: `GROUP_RULE_TYPES["personas_similares_v2"]="personas_similares_v2_groups"` (grupos lado a lado); explicación de error específica en ErrorDetail.

**Verification**:
- Casos sintéticos en el contenedor (todas pasan): cédula con 1 dígito cambiado, 2 dígitos transpuestos, mismo nombre, nombre con tilde/mayúsculas (CARLOS / LÓPEZ), DOB ±1 día, grupo transitivo de 3 (Juan Pérez con 3 cédulas distintas → grupo size 3), duplicados exactos NO marcados, modo rápido, pesos personalizados (solo ID+nombre → 3 grupos).
- Registro verificado vía `resolve_rules(['personas_similares_v2'], {...})` en el contenedor: instancia `SimilarPeopleCheckV2` con mode/threshold correctos.
- Migración `c0d1e2f3a4b5 -> b2c3d4e5f6a7` aplicada al arrancar.
- TypeScript compila limpio (`npx tsc --noEmit`; pre-existentes `@dnd-kit` en `Connections.tsx` quedan, no relacionados).
- Backend reconstruido y healthy.

**Gotchas**:
- El head de migraciones NO era `f0e1d2c3b4a5`; el árbol termina en `c0d1e2f3a4b5` (verificar con grep de `revision`/`down_revision` antes de crear migración).
- Bug encontrado y corregido en pruebas: cuando el usuario pasa `weights` parciales, `use_cols` debe reducirse a las columnas ponderadas (si no, KeyError en el composite sobre columnas sin peso).
- Pesos parciales → solo se comparan las columnas con peso > 0; si ninguno coincide con los campos "fuertes" del modo rápido, se usan los defaults.

## 2026-08-10 — ProcessDetail: fixed "Error al cargar el proceso" flash + confusing "Bloqueo" phase label

**Problem**: Two frontend annoyances while running genesys "personas similares" analyses: (1) right as loading finished, an "Error al cargar el proceso" page flashed for a few seconds, then vanished and showed the report; (2) during the run a "Bloqueo" chip appeared, made users think the analysis was stuck, then cleared and continued.

**Root causes**:
- `GET /processes/{id}` serialized the **full `result_json` + `recommendations` for every report** (processes.py:187-189). For genesys personas_similares that JSON is enormous. When the run completed, the refetch (`queryClient.invalidateQueries`) pulled that giant payload → exceeded the axios `timeout: 15_000` → the page rendered the `isError` "Error al cargar el proceso" state → react-query retried and succeeded seconds later. The ProcessDetail page never used `reports[].result` anyway (only id/score/label/executed_at).
- `progress.rule_phase === 'blocking'` (candidate-pair generation in `person_dedup_rules.py`) was labeled **"Bloqueo"**, which reads as "blocked/frozen" during the longest phase of the run.

**Changes made**:
- `backend/qdata/web/routes/processes.py`: the reports query in `get_process` now uses `.options(defer(Report.result_json), defer(Report.recommendations))` and those two keys are no longer serialized (same pattern as the `/api/groups` dashboard). Process detail responses are now small/fast regardless of report size.
- `frontend/src/api/client.ts`: axios `timeout` raised `15_000 → 120_000` (safety net for big ReportDetail payloads too).
- `frontend/src/pages/ProcessDetail.tsx`:
  - `if (isError)` → `if (isError && !process)`: a transient refetch failure (e.g. timeout) with cached data no longer blanks the page.
  - Phase chip: `'Bloqueo' → 'Buscando candidatos'`, `'Scoring' → 'Similitud'` (clustering stays `'Agrupando'`).
  - SSE `error` handler only calls `es.close()` when the run reached a terminal status; otherwise it lets EventSource auto-reconnect (a transient stream drop during a long run previously froze the progress UI forever).
  - `refetchInterval` now also polls while `status === 'loading'` (not just running/pending), so the page keeps updating if the SSE stream drops mid-load.
- TypeScript compiles clean (`npx tsc --noEmit`; pre-existing `@dnd-kit` errors in `Connections.tsx` remain, unrelated).

**Gotcha**: `defer()` means those columns are NOT loaded — code must not touch `r.result_json`/`r.recommendations` in this endpoint (would trigger a sync lazy-load in an async context). Verify: `GET /processes/{id}` no longer returns a `result`/`recommendations` key per report.

## 2026-08-06 — TELEFONO_DUPLICADO error detail: identity + phone; fixed phone_check silently passing on numeric phone columns

**Problem**: Replicate the EMAIL_DUPLICADO treatment for the 22 `TELEFONO_DUPLICADO_Y_VALIDO_*` projects: error detail for `duplicate_check` ("Registros duplicados") and `phone_check` ("Registro completo (fila n)") should show only tipo doc, número doc, nombres, apellidos and teléfono. Two issues surfaced during verification:

- **Regression in the phone_check rule**: `load_data` without a `progress_callback` uses `pd.read_sql`, which converts SQL Server `decimal` columns to `float64`. `_str_cols(df)` then skips numeric phone columns entirely, and `astype(str)` yields `'7400773.0'` which fails every phone regex. The July reports were generated via the streaming path (kept `Decimal` → object dtype → `'7400773'`). Result: after the first 2026-08-06 re-run, `phone_check` reported `failed=0` for all 13 Person-table sources (ADULTOMAYOR 888→0, ETDHINFINITE 94685→0, TALENTOS 14758→0, ...). SEVEN/SIHOS/GENESYS (string phone cols) were unaffected.
- `identity_field_columns` + `phone_columns` both need `full_df` loaded via the same path, so the fix is in the rule (not the loader): `PhoneCheck.execute` now iterates ALL `df.columns` (not just `_str_cols`), evaluating numeric columns matching `PHONE_COL_RE`, and normalizes float-rendered values via `_norm_phone_str` (`'7400773.0'` → `'7400773'`) before regex validation. Stored `value` uses the normalized string.

**Changes made**:
- `backend/qdata/rules/format_rules.py`: `PhoneCheck.execute` iterates `df.columns`; `is_str_col` gate (`is_object_dtype`/`is_string_dtype`) allows numeric cols only when `PHONE_COL_RE` matches; `_norm_phone_str` + `_FLOAT_SUFFIX_RE` added; `valid`/`value` use the normalized series. Verified ADULTOMAYOR `failed=891` (old 888, data grew slightly) vs `failed=0` before the fix.
- `backend/qdata/rules/person_fields.py`: new `PHONE_COL_RE` (`tele|tel[^e]|celu|celular|mobile|phone|fijo|whatsapp|movil|ntel` — includes `ntel` so NEWHOTEL's `clie_tele` is detected), `_PHONE_EXCLUDE_RE` (drops flags like `SinNumTele`/`MotiNullCel`/`PerMedTel`), `phone_columns()`.
- `backend/qdata/web/routes/analyze.py` `_enrich_full_rows`: chooses contact columns by rule — `phone_check` present → `phone_columns`, else `email_check` → `email_columns`, else `[]`. `df_keep` = identity + contact.
- `backend/qdata/web/routes/processes.py` `rerun_process`: injects `rule_configs["duplicates"]["columns"]` with the phone column when the project has `phone_valid` and empty `selected_columns` (falls back to `email_columns` otherwise).
- `frontend/src/pages/ErrorDetail.tsx`: `isPhoneColumn`, `contactKeysFor`, `contactMode`; `recordTableKeys`/`groupTableKeys` = `[...identity, ...contactKeysFor(phone)]` for `phone_check`/`duplicate_check` (email for `email_check`); full-row fallback otherwise.
- `frontend/src/lib/ruleDescriptions.ts`: `isPhoneColumn`, `isContactColumn`, `contactKeysByMode`, per-row `describeError` branch generalized to contact mode.
- **Re-runs**: first driver re-ran all 22 (per-row format), then a second driver re-ran the 13 degraded Person sources with the fixed rule (ADULTOMAYOR 891, COLEGIO_TUNJA 448, ETDHINFINITE 95166, TALENTOS 14775, SCHOOLPACK 18–51 each). Old degraded reports deleted (kept newest per project), `ErrorAction` rows cleaned for deleted reports. Verified 22/22 reports: `duplicate_check` sample_failures/`duplicate_groups` carry identity+phone `values`, `phone_check` failures restored.
- Backend restarted to deploy the changes.
- TypeScript compiles clean (`npx tsc --noEmit`; pre-existing `@dnd-kit` errors in `Connections.tsx` remain, unrelated).

**Gotchas**:
- Mutating `report.result_json` in place is NOT detected by SQLAlchemy (no UPDATE); assign `rep.result_json = <deepcopy>`.
- Commit can fail with `asyncpg.exceptions.InvalidTextRepresentationError` (Token "NaN" is invalid) when the reloaded report JSON contains Python float `NaN`; run the dict through `_safe_val` before reassigning (converts NaN/Inf to `"nan"`/`"inf"`).
- JSONB columns contain `\u0000`-escaped bytes → JSON casts via SQL fail; verify through the ORM.
- `duplicate_groups` members capped at `MAX_DUPE_GROUP_TOTAL`=20000.
- GENESYS TELEFONO has no identity columns (`SELECT * FROM Ubicacion`) → full-row fallback in the UI.

## 2026-08-06 — duplicate_check "Registros duplicados" table shows identity + email

**Problem**: In the error detail page for `duplicate_check`, the "Registros duplicados" table (rows within a duplicate group) showed only the identity columns (doc type/number, names, surnames) — the email was missing, so users couldn't see which emails were duplicated.

**Changes made**:
- `backend/qdata/web/routes/analyze.py` `_enrich_full_rows`: `duplicate_groups` rows now use `df_keep` (identity columns + email) instead of `df_id` (identity only); `df_id` variable removed. Docstring updated. So NEW reports store identity+email per group row (full-row fallback when no identity detected, e.g. GENESYS → `Ubicacion` columns).
- `frontend/src/pages/ErrorDetail.tsx`: for `duplicate_check` groups with detected identity, `groupTableKeys` is built from `[...identityKeys, emailKey]` (email column ordered after identity) instead of only identity keys; full `Object.keys` fallback otherwise. Matches the `email_check` "Registro completo" pattern.
- **Backfill of existing reports** (data already stored as full rows since the 2026-08-06 re-run): `backfill_dupe_email.py` reloaded each source, recomputed `df_keep`, and re-attached `values` to every `duplicate_groups` row member. All 23/23 reports enriched (e.g. ADULTOMAYOR 2041 rows, COLLEGIO_TUNJA 8969, groups capped at `MAX_DUPE_GROUP_TOTAL`=20000 members).
- **Gotcha found while backfilling**: mutating `report.result_json` dict in place is NOT detected by SQLAlchemy (no UPDATE). Assigning `rep.result_json = <deepcopy>` DOES emit the UPDATE, but the commit then failed with `asyncpg.exceptions.InvalidTextRepresentationError` (Token "NaN" is invalid) because the reloaded report JSON contains Python float `NaN` values. Fix: run the enriched dict through `_safe_val` (from `analyze.py`) before reassigning — it converts NaN/Inf to `"nan"`/`"inf"` strings, exactly like the original save path does. Verified `email=True` for all 23 via API/ORM.
- Backend restarted to deploy the `_enrich_full_rows` change.
- TypeScript compiles clean (`npx tsc --noEmit`; pre-existing `@dnd-kit` errors in `Connections.tsx` remain, unrelated).

## 2026-08-06 — email_check error detail: "Registro completo" restricted to identity + email

**Problem**: In the error detail page for `email_check` errors, the "Registro completo (fila n)" table rendered the full row (196 columns), but users only want to see the person's doc type/number, names, surnames, and the email. Nothing else.

**Changes made**:
- `frontend/src/pages/ErrorDetail.tsx`: computed `recordIdentityKeys` via `identityColumns(fullRecord)` and `recordEmailKey` via `isEmailColumn`; for `email_check` with detected identity columns, `recordEntries` (used by the "Registro completo" table) is built only from `[identity keys..., email]`. When no identity column is detected the full record is kept as fallback (same pattern as the `duplicate_check` "Registros duplicados" table). Other rules keep showing the full row.
- No backend change and no re-run needed — it's a pure display restriction; all 23 regenerated reports keep full-row `email_check` values in storage but only show identity+email in the UI.
- TypeScript compiles clean (`npx tsc --noEmit`; pre-existing `@dnd-kit` errors in `Connections.tsx` remain, unrelated).

## 2026-08-06 — Re-run of all 23 EMAIL_DUPLICADO_Y_VALIDO_* analyses (per-row format end-to-end)

**Problem**: The 2026-08-06 backfill converted the 23 existing reports to the new per-row `duplicate_check` format but from stored data — each group only had the ≤10 rows that had been persisted, `group_size` was degraded (1765→10), and `email_valid` was stale. The user chose to re-run all 23 analyses to regenerate complete reports.

**Key discovery**: these projects were created with `rule_configs={"duplicates": {"columns": [email]}}` (grouping by the email column only, e.g. `PerMail`), which is NOT stored in the Project. `source_config.selected_columns` is empty for 12 of the 23, so a plain re-run with `rule_configs={}` made `duplicate_check` group by ALL 196 columns → 0 duplicates for those projects (wrong). For the other 11, `selected_columns=[email]` so grouping was correct regardless.

**Changes made**:
- `backend/qdata/web/routes/processes.py`: `rerun_process` now derives `rule_configs` — when `selected_columns` is empty and the project includes `duplicates`, it injects `{"duplicates": {"columns": [email_columns(df.columns)[0]]}}` (from `qdata.rules.person_fields`). Fixes future UI re-runs for no-column projects.
- Driver scripts (throwaway, in `/tmp` inside container): `rerun_all.py` (all 23 with `full_df` + cleanup keeping newest report) and `rerun2.py` (re-run the 12 no-`selected_columns` projects with the email-column rule_config; email column taken from `email_check`'s `sample_failures[0].column`, falling back to `email_columns()`).

**Re-runs executed** (driver inside `qdata-backend`, sequential; ~1.9M-row GENESYS = 57s, 500k-row SEVEN = ~5min, NEWHOTEL 387-490k = 80-150s each):
- All 23 regenerated, old degraded reports deleted (kept newest per project).
- Verified every report: `sample_failures` is one entry per row (`{row, group_size, values}`) with identity+email values (Person: `PerTipDoc/PerNumDoc/PerPriNom/PerSegNom`; SEVEN: `TIP_CODI/TER_NIDE/TER_NOMB/TER_APEL`; NEWHOTEL: `clie_tiid/clie_nuid/clie_noma/clie_apel`; SIHOS: `TipoDocu/NuDoTerc/NombUsua/Ape1Usua`; KACTUS: `tip_terc/cod_terc/nom_terc/ape_terc`; GENESYS: Ubicacion fallback since source is `SELECT * FROM Ubicacion` — no person columns available), `duplicate_groups` details with all members (capped at `MAX_DUPE_GROUP_TOTAL`), `email_valid` fresh.
- JSTIBASOSA now `failed=2081`, groups `[1765, 274, 25]` = exactly the original stored numbers, but per-row and complete.

## 2026-08-06 — Full person row in error detail for EMAIL_DUPLICADO_Y_VALIDO_*

**Problem**: In reports `EMAIL_DUPLICADO_Y_VALIDO_*` the "Detalle de errores" only showed the email column (e.g. `{"PerMail": ""}`), so users couldn't see which person the error belonged to (doc type/number, names). Null emails also rendered as blank/NULL instead of an explicit message.

**Changes made**:
- `backend/qdata/web/routes/analyze.py`: added `_row_dict`, `_enrich_full_rows`, `_CONTROL_RE`/`_clean_str`; `_sync_load_and_run` and the background route keep `full_df` and enrich `sample_failures` with full row values before `_safe_val`; `run_analysis_background` accepts optional `full_df`. So NEW reports always store the whole row.
- `backend/scripts/backfill_values.py`: rewrote detection — `_needs_backfill` uses `_distinct_value_columns` (<4 distinct value columns ⇒ partial, even when `selected_columns` is empty, which caught the rule-level column config used by older reports); `_is_partial` compares stored value keys against the actually loaded `df.columns`; `_row_values` attaches the full row. Re-ran for all 23 `EMAIL_DUPLICADO_Y_VALIDO_*` reports — verified via API (`GET /reports/{id}`) that both `duplicate_check` (rows[].values) and `email_check` (values) now carry 196-column Person rows / full rows.
- `frontend/src/pages/ErrorDetail.tsx`: `EMAIL_COL_RE`, `isEmailColumn`, `isEmptyEmail` (treats null/undefined/NaN/''/nan/none/null/nat as empty), `renderVal(v, key?)` renders `<span class="text-orange-300 italic">No tiene ningun email</span>` for empty email cells; the "Valor actual" card shows the same message when the row's email is empty.
- `frontend/src/lib/ruleDescriptions.ts`: exported `isEmailColumn`, `isEmptyEmail`, `NO_EMAIL_TEXT`; `describeError` for `email_check` says "no tiene ningún valor" when empty, and for `duplicate_check` orders the email column first and uses `Email: No tiene ningun email` as `valor`.
- `npx tsc --noEmit`: clean except pre-existing `@dnd-kit` module errors in `src/pages/Connections.tsx`.

## 2026-07-09 — pymssql for SQL Server 2014 compatibility

**Problem**: SQL Server 2014 (172.16.0.111, server PRODSEVENDB) gets `08001 10054` (connection reset) or `HYT00` (login timeout) with Microsoft ODBC Driver 17/18 due to TLS version mismatch (ODBC uses OpenSSL, SQL 2014 on Win 2012 R2 doesn't support TLS 1.2 properly).

**Solution**: Switch from `mssql+pyodbc://` (ODBC) to `mssql+pymssql://` (FreeTDS) for all SQL Server connections.

**Changes made**:
- `backend/qdata/web/routes/datasources.py:89-95`: `build_connection_string` now returns `mssql+pymssql://user:pass@host:port/db` (no instance name, no driver query params, no `TrustServerCertificate`)
- `backend/pyproject.toml`: added `"pymssql>=2.3"` to dependencies
- **DB migration**: All 18 existing SQL Server datasources' `connection_string` updated from `mssql+pyodbc://...` to `mssql+pymssql://...` (with instance name removed from URL — pymssql connects by TCP port, not SQL Browser)
- Container not rebuilt yet; `pip install pymssql` runs in current container; rebuild needed after commit.

**Verification**:
- Direct `pymssql.connect(server='172.16.0.111', port=1433, ...)`: ✅ returns SQL Server 2014 SP2 version 12.0.5000.0
- API `POST /datasources/test` with pymssql URL: ✅ returns `{"success":true,"tables":[...7169 tables...]}`
- API `GET /datasources/{id}/tables` for SEVEN: ✅ returns 200 with tables/columns

## Previous work (earlier sessions)

### Drag-and-drop reorder of connections
**Files**: `backend/qdata/web/routes/datasources.py`, frontend components, Alembic migration `c9d8e7f6a5b4`
- Added `sort_order` column to `DataSource` model
- `PUT /datasources/reorder` endpoint for batch reorder
- Frontend: `@dnd-kit` for sortable drag-and-drop with `GripVertical` handle

### ODBC Driver 17 installation
**File**: `Dockerfile` — added `msodbcsql17` alongside `msodbcsql18`
- `_detect_sqlserver_driver()` prefers ODBC 17 before 18
- Was insufficient for SQL Server 2014 (TLS issue persists with both 17 and 18)

### Fix 1 — numpy.int64 serialization crash
**File**: `backend/qdata/web/routes/sources.py:20-37`
**Problem**: `numpy.int64` from `count(*)` caused 500 in `jsonable_encoder`.
**Fix**: `_safe_val` checks `hasattr(v, "item")` before `isinstance(v, (float, int))`.

### Fix 2 — preview always showed 11 total rows
**File**: `backend/qdata/web/routes/sources.py:306-368`
**Fix**: Computes `SELECT COUNT(*)` first, then loads 11 rows for preview.

### Fix 3 — Edit connection not persisting config
**File**: `backend/qdata/web/routes/datasources.py:267-271`
**Fix**: `{**(ds.config or {}), "db_fields": ...}` (new dict) instead of mutating in-place.

### Fix 4 — Various smaller fixes
- **Sources 307 redirect**: Dual decorators `@router.get("")` + `@router.get("/")`
- **SQL Server LIMIT**: `_apply_limit` uses `SELECT TOP n` for SQL Server
- **Preview error display**: `formPreviewError` state with `<AlertTriangle>` in `SourceForm.tsx`
- **Process/report labels**: `_extract_names` regex for `DATABASE=` in ODBC-style Informix/Oracle connections
- **Duplicate UX**: `handleDuplicate` opens form for editing instead of immediate create

## 2026-07-16 — Group permissions & error-action status

### Group-level permissions
**Problem**: Analyst/viewer users could see all analysis groups, processes, and reports — needed scoping to only their own resources plus groups they're explicitly granted access to.

**Changes made**:
- `backend/qdata/db/models.py:154-165`: New `GroupPermission` table (user_id, group_id) with unique constraint
- Alembic migration `e5f6a7b8c9d0` applied
- `backend/qdata/auth/permissions.py:6-14`: `require_role(["admin"])` dependency for protecting delete endpoints
- `backend/qdata/web/routes/groups.py:27-30`: `GET /api/groups` filters by owned + shared groups for non-admin
- `backend/qdata/web/routes/projects.py:37-49`: Dashboard/processes list filters by owned + shared groups
- `backend/qdata/web/routes/reports.py:32-45`: Reports list filters by owned + shared groups
- All DELETE endpoints across `admin.py`, `datasources.py`, `sources.py`, `groups.py`, `projects.py`, `reports.py`, `rules.py`, `scheduler.py` protected with `require_role(["admin"])`
- `backend/qdata/web/routes/admin.py:126-224`: `GET /admin/groups`, `POST /admin/users` (with `group_ids`), `GET/PUT /admin/users/{id}/permissions` for group permission assignment
- `frontend/src/pages/AdminUsers.tsx`: Rewritten with expandable group-permission multi-select and creation-form group assignment
- Delete buttons hidden for non-admin in Groups, Processes, ProcessDetail, Reports, ReportDetail, Connections
- PDF/Excel export endpoints (`reports.py`) also filter by shared groups

### Error-action status tracker
**Problem**: Users needed to track error resolution progress (sin acción / en revisión / solucionado) on rule error detail pages.

**Changes made**:
- `backend/qdata/db/models.py`: Added `ErrorAction` model (report_id, rule_index, error_index, status, updated_at) with unique constraint
- Alembic migration `f0e1d2c3b4a5` applied
- `backend/qdata/web/routes/reports.py`: Added `PUT /reports/{id}/rules/{ri}/errors/{ei}/action` (upsert) and `GET /reports/{id}/rules/{ri}/actions` endpoints
- `frontend/src/pages/ErrorDetail.tsx`: Status dropdown (sin acción → en revisión → solucionado) with arrow navigation; uses `useMutation` for instant updates
- `frontend/src/pages/RuleDetail.tsx`: Green "X solucionados" badge in the rule header card + "Estado" column (dropdown) in the "Detalle de errores" table for per-error status
- TypeScript compiles clean (`npx tsc --noEmit`)

## 2026-08-05 — Multi-table sources (UNION ALL) in visual mode

**Problem**: In the source editor (módulo fuentes de datos) users could only pick ONE table; needed to combine several tables into one source.

**Decision**: UNION ALL (concatenate rows; columns missing from a table become NULL) — chosen by user over JOIN/per-table loading.

**Changes made** (`frontend/src/pages/SourceForm.tsx` only — backend untouched):
- `selectedTable` (single string) replaced with `selectedTables: string[]`; table list is now checkbox multi-select; checking/unchecking toggles + reloads columns for all selected tables
- `tableColumns` is now `TableColumns[]` (grouped per table); columns panel renders groups with sticky table-name headers; "Todas"/"Ninguna" act across all groups
- Column auto-selection on table pick: 1 table → all its columns; N tables → intersection (shared columns); suggestions/duplicate/edit restore force the saved `selected_columns`
- `buildVisualQuery()` (in `SourceForm.tsx:205`): per table `SELECT col1, ..., NULL AS colX FROM T` joined by `\nUNION ALL\n` (missing column → `NULL AS <name>`); no columns selected → single table `SELECT *`, multi-table → union of ALL columns across tables
- `extractTablesFromQuery()` (module-level): regex `\bFROM\s+([^\s;,()]+)` to restore `selectedTables` when editing/duplicating an existing multi-table source
- `previewQuery`/`handleSave` use `buildVisualQuery()` for visual mode; `handleSave` blocks with "Selecciona al menos una tabla" if visual query is empty
- Verified: `_apply_limit` in `backend/qdata/core/loader.py:13` already wraps the whole union safely (SQL Server `SELECT TOP n * FROM (...) AS _limited_`, Oracle `WHERE ROWNUM <= n`, others `LIMIT n`)
- TypeScript compiles clean for `SourceForm.tsx` (`npx tsc --noEmit`; pre-existing `@dnd-kit` module errors in `Connections.tsx` remain, unrelated)

**Notes / edge cases**:
- **CRITICAL UNION fix (2026-08-05):** never emit bare `SELECT * FROM T1 UNION ALL SELECT * FROM T2` when tables have different column counts → SQL Server error 205. Empty `selected_columns` with multiple tables falls back to the union of all tables' columns. Also `NULL` positions in the FIRST table's SELECT lose their name in the result (pandas names them `''`) — always emit `NULL AS <column>` so union result column names are correct regardless of table order
- Auto-select when picking tables: 1 table → its columns; N tables → **union** of all columns across tables (NOT intersection — intersection is usually empty for differently-structured tables, which previously triggered the error-205 bug)
- UNION result column names come from the FIRST table's SELECT list, so `NULL AS <name>` aliases guarantee stable names
- Per-table columns are fetched in parallel via `Promise.all` (per-table endpoint ~0.1s for SQL Server/MySQL/PG; one Informix subprocess per table)
- Visual mode restore only when `query && !selected_columns?.length` → SQL mode; multi-table visual sources restore to visual mode because they have `selected_columns`

### JOIN mode added (same session) — for genesys: Persona + Ubicacion + PersonaDetalle
**Problem**: UNION ALL was useless for related tables (Persona.perUbicacionPrincipal→Ubicacion.ubiId, PersonaDetalle.pedPersona→Persona.perId) — each row only had values from ONE table, so ubiEmail/ubiTelefonoCelular/pedFechaNacimiento were NULL. User chose to add JOIN support to the visual builder.

**Changes made** (`frontend/src/pages/SourceForm.tsx` only — backend untouched):
- New state `combineMode: 'union' | 'join'` + `joinRelations: Record<pairKey, {tableA, colA, tableB, colB}>`; when `selectedTables.length >= 2` a segmented toggle appears: "Combinar filas (UNION ALL)" vs "Relacionar tablas (JOIN)"
- JOIN mode shows a "Relaciones entre tablas" panel: one row per unordered pair of selected tables with two column dropdowns (`colA = colB`); empty/incomplete relations are ignored; only edges connected to the reachable set (from base = first selected table) are used via BFS
- `buildJoinQuery()` (in `SourceForm.tsx`): aliases `t1..tN` in selection order; `SELECT tX.col AS col, ...` with each selected column resolved to the FIRST table that has it; `FROM <base> t1` + `LEFT JOIN <T> tX ON tX.<colB> = tY.<colA>` per edge; returns `''` if any selected table is unreachable (user must define the relation)
- `extractTablesFromQuery()` now also matches `JOIN` (`\b(?:FROM|JOIN)\s+`) so JOIN sources restore to visual mode; `parseJoinRelations()` reconstructs relations from the saved query (matches `LEFT JOIN T tN ON tx.c = ty.c`, maps aliases back via order)
- Restore (edit/duplicate): `/\bJOIN\b/i` on query → `combineMode='join'` + parsed relations; else union. Reset of combineMode/relations on dsId change and table toggle (pruned to selected tables)
- `handleSave`/`previewQuery` branch on combineMode; save blocked with "Define las relaciones entre las tablas" if the JOIN query is empty
- Verified end-to-end against genesysOld: `FROM Persona t1 LEFT JOIN Ubicacion t2 ON t2.ubiId = t1.perUbicacionPrincipal LEFT JOIN PersonaDetalle t3 ON t3.pedPersona = t1.perId` returns real email/phone/birthdate (1,076,239 rows, no dupes; 936k birthdates, 367k emails, 564k phones non-null — rest are genuine NULLs)
- TypeScript compiles clean (`npx tsc --noEmit`)
