from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from qdata.auth.dependencies import get_current_user
from qdata.core.engine import RULE_REGISTRY, RULE_GROUPS, SIMILARITY_LEVELS
from qdata.db.models import CustomRule, RuleGroup, User
from qdata.db.session import get_session

router = APIRouter()

RULE_METADATA = {
    "nullity": {"label": "Nulos", "group": "basico", "severity": "error", "desc": "Detecta valores nulos y vacíos en todas las columnas"},
    "duplicates": {"label": "Duplicados", "group": "basico", "severity": "error", "desc": "Detecta filas duplicadas exactas"},
    "types": {"label": "Tipos de datos", "group": "basico", "severity": "error", "desc": "Verifica coherencia de tipos de datos"},
    "ranges": {"label": "Rangos y outliers", "group": "basico", "severity": "warning", "desc": "Outliers por IQR y z-score"},
    "patterns": {"label": "Patrones (regex)", "group": "basico", "severity": "error", "desc": "Valida formato contra patrones regex predefinidos"},
    "uniqueness": {"label": "Unicidad", "group": "basico", "severity": "error", "desc": "Verifica unicidad en columnas candidatas a PK"},
    "referential": {"label": "Integridad referencial", "group": "basico", "severity": "error", "desc": "Verifica integridad referencial entre columnas"},
    "cardinality": {"label": "Cardinalidad", "group": "basico", "severity": "error", "desc": "Detecta columnas constantes o con cardinalidad >95%"},
    "distributions": {"label": "Distribuciones", "group": "basico", "severity": "warning", "desc": "Evalúa normalidad, asimetría y curtosis"},
    "correlations": {"label": "Correlaciones", "group": "basico", "severity": "warning", "desc": "Detecta multicolinealidad entre variables numéricas"},
    "email_valid": {"label": "Email válido", "group": "formato", "severity": "error", "desc": "Valida formato de correo electrónico RFC 5322"},
    "special_chars": {"label": "Caracteres especiales", "group": "formato", "severity": "warning", "desc": "Detecta caracteres de control, zero-width, uso privado, seguridad y espacios no estándar"},
    "string_length": {"label": "Longitud de cadenas", "group": "formato", "severity": "error", "desc": "Verifica longitud de cadenas en rango esperado"},
    "trim_check": {"label": "Espacios extra", "group": "formato", "severity": "warning", "desc": "Detecta espacios leading/trailing"},
    "case_check": {"label": "Consistencia mayúsculas", "group": "formato", "severity": "warning", "desc": "Detecta mezcla inconsistente de mayúsculas/minúsculas"},
    "phone_valid": {"label": "Teléfono válido", "group": "formato", "severity": "error", "desc": "Valida formato de números telefónicos"},
    "zip_valid": {"label": "Código postal válido", "group": "formato", "severity": "error", "desc": "Valida formato de código postal (MX, US, UK)"},
    "rfc_curp": {"label": "RFC / CURP", "group": "formato", "severity": "error", "desc": "Valida estructura de RFC y CURP mexicanos"},
    "invalid_dates": {"label": "Fechas inválidas", "group": "fechas", "severity": "error", "desc": "Detecta fechas imposibles (30 feb, año negativo, etc.)"},
    "date_range": {"label": "Rango temporal", "group": "fechas", "severity": "error", "desc": "Fechas fuera de época (<1900 o >hoy)"},
    "date_inconsistency": {"label": "Inconsistencia fechas", "group": "fechas", "severity": "error", "desc": "Relaciones temporales ilógicas entre pares de fechas"},
    "freshness": {"label": "Actualidad (freshness)", "group": "fechas", "severity": "warning", "desc": "Verifica que datos estén dentro de ventana temporal esperada"},
    "latency": {"label": "Latencia de ingesta", "group": "fechas", "severity": "warning", "desc": "Mide delay entre timestamp de evento e ingesta"},
    "cross_consistency": {"label": "Consistencia cruzada", "group": "negocio", "severity": "error", "desc": "Valida relaciones aritméticas entre columnas (total = precio × cantidad)"},
    "functional_dependency": {"label": "Dependencias funcionales", "group": "negocio", "severity": "warning", "desc": "Detecta violaciones de dependencias funcionales"},
    "class_balance": {"label": "Balance de clases", "group": "negocio", "severity": "warning", "desc": "Detecta desbalance extremo en columnas categóricas"},
    "boolean_bias": {"label": "Sesgo booleano", "group": "negocio", "severity": "warning", "desc": "Columnas booleanas con sesgo extremo (>99%)"},
    "derived_columns": {"label": "Columnas derivadas", "group": "negocio", "severity": "error", "desc": "Verifica que columnas calculadas coincidan con su fórmula"},
    "row_completeness": {"label": "Completitud por fila", "group": "avanzadas", "severity": "warning", "desc": "% de campos poblados por registro, detecta filas vacías"},
    "multivariate_outliers": {"label": "Outliers multivariados", "group": "avanzadas", "severity": "warning", "desc": "Outliers con Isolation Forest (no solo IQR)"},
    "drift": {"label": "Deriva categórica", "group": "avanzadas", "severity": "warning", "desc": "Detecta categorías nuevas no vistas en datos históricos"},
    "schema_evolution": {"label": "Evolución de esquema", "group": "avanzadas", "severity": "warning", "desc": "Detecta columnas nuevas, eliminadas o cambios de tipo"},
    "volume_anomaly": {"label": "Anomalía de volumen", "group": "integridad", "severity": "warning", "desc": "Alertar si el conteo de filas se desvía del promedio"},
    "sequential_integrity": {"label": "Integridad secuencial", "group": "integridad", "severity": "warning", "desc": "Verifica que IDs secuenciales no tengan saltos"},
    "missing_fks": {"label": "Llaves foráneas ausentes", "group": "integridad", "severity": "error", "desc": "Detecta IDs referenciados que no existen en tabla padre"},
    "fuzzy_name_match": {"label": "Nombres similares (fuzzy)", "group": "personas", "severity": "warning", "desc": "Detecta registros con nombres muy similares (1-2 caracteres de diferencia)"},
    "fuzzy_id_match": {"label": "ID/Cédula similar (fuzzy)", "group": "personas", "severity": "warning", "desc": "Detecta registros con ID/cédula con 1-2 dígitos diferentes"},
    "similar_dob": {"label": "Fecha de nacimiento cercana", "group": "personas", "severity": "warning", "desc": "Detecta registros con fechas de nacimiento en ventana de ±3 días"},
    "person_composite_similarity": {"label": "Score compuesto de persona", "group": "personas", "severity": "warning", "desc": "Combina nombre+ID+DOB+dirección+teléfono en un score único para detectar la misma persona"},
    "personas_similares": {"label": "Buscar Persona", "group": "personas_similares", "severity": "warning", "desc": "Detecta personas potencialmente duplicadas combinando nombre, ID, fecha de nacimiento, dirección, teléfono y email (modos: rápido y profundo)"},
}

GROUP_METADATA = {
    "basico": {"label": "Básico", "icon": "CheckCircle", "desc": "Reglas esenciales de calidad de datos"},
    "formato": {"label": "Formato y validación", "icon": "FileText", "desc": "Validación de formatos de campos individuales"},
    "fechas": {"label": "Fechas", "icon": "Calendar", "desc": "Validación de fechas y relaciones temporales"},
    "negocio": {"label": "Reglas de negocio", "icon": "Briefcase", "desc": "Validación de lógica de negocio y consistencia interna"},
    "avanzadas": {"label": "Avanzadas", "icon": "Cpu", "desc": "Técnicas estadísticas avanzadas y machine learning"},
    "integridad": {"label": "Integridad", "icon": "Link", "desc": "Integridad de datos a nivel de tabla y volumen"},
    "personas_similares": {"label": "Personas similares", "icon": "Users", "desc": "Detecta personas potencialmente duplicadas con modo rápido o profundo"},
    "todo": {"label": "Todas las reglas", "icon": "List", "desc": "Ejecuta todas las reglas disponibles"},
}

SIMILARITY_LEVEL_METADATA = {
    "ninguno": {"label": "Ninguno", "desc": "Sin detección de duplicados de personas"},
    "rapido": {"label": "Rápido", "desc": "Solo ID y fecha de nacimiento — detecta errores obvios de digitación"},
    "medio": {"label": "Medio", "desc": "ID + DOB + nombre completo — detecta la mayoría de duplicados"},
    "profundo": {"label": "Profundo", "desc": "Todos los campos (nombre+ID+DOB+dir+tel+email) — máximo recall, más lento"},
}


class CustomRuleCreate(BaseModel):
    name: str
    description: str = ""
    rule_type: str = "sql"
    rule_code: str
    severity: str = "error"
    group: str = "custom"


class RuleGroupCreate(BaseModel):
    name: str
    label: str
    description: str = ""
    icon: str = "Shield"


class RuleGroupUpdate(BaseModel):
    label: str | None = None
    description: str | None = None
    icon: str | None = None


@router.get("/")
async def list_rules():
    built_in = [
        {
            "name": name,
            "label": RULE_METADATA.get(name, {}).get("label", name),
            "description": cls().description,
            "group": RULE_METADATA.get(name, {}).get("group", "basico"),
            "severity": RULE_METADATA.get(name, {}).get("severity", "error"),
        }
        for name, cls in RULE_REGISTRY.items()
    ]
    return {"built_in": built_in}


@router.get("/groups")
async def list_rule_groups(
    user: User | None = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    groups = []
    for gname, rule_names in RULE_GROUPS.items():
        meta = GROUP_METADATA.get(gname, {"label": gname, "desc": ""})
        rules = []
        for rname in rule_names:
            rmeta = RULE_METADATA.get(rname, {"label": rname, "severity": "error", "desc": ""})
            if rname in RULE_REGISTRY:
                rules.append({
                    "name": rname,
                    "label": rmeta["label"],
                    "severity": rmeta["severity"],
                    "description": rmeta["desc"],
                })
        groups.append({
            "name": gname,
            "label": meta["label"],
            "description": meta["desc"],
            "rules": rules,
            "is_builtin": True,
        })

    # Load custom groups from DB
    if user:
        db_groups = await session.execute(
            select(RuleGroup).where(
                (RuleGroup.user_id == user.id) | (RuleGroup.is_builtin == True)
            )
        )
        for rg in db_groups.scalars().all():
            if rg.name not in RULE_GROUPS:
                cr_result = await session.execute(
                    select(CustomRule).where(
                        CustomRule.user_id == user.id,
                        CustomRule.group == rg.name,
                    )
                )
                custom_rules = [
                    {"name": cr.name, "label": cr.name, "severity": cr.severity, "description": cr.description or ""}
                    for cr in cr_result.scalars().all()
                ]
                groups.append({
                    "name": rg.name,
                    "label": rg.label,
                    "description": rg.description or "",
                    "rules": custom_rules,
                    "is_builtin": False,
                })

    similarity_levels = [
        {"name": name, **SIMILARITY_LEVEL_METADATA.get(name, {"label": name, "desc": ""}), "rules": rules}
        for name, rules in SIMILARITY_LEVELS.items()
    ]
    return {"groups": groups, "similarity_levels": similarity_levels}


@router.post("/custom")
async def create_custom_rule(
    req: CustomRuleCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    rule = CustomRule(
        user_id=user.id,
        name=req.name,
        description=req.description or req.name,
        rule_type=req.rule_type,
        rule_code=req.rule_code,
        severity=req.severity,
        group=req.group,
    )
    session.add(rule)
    await session.commit()
    await session.refresh(rule)
    return {"id": str(rule.id), "name": rule.name, "group": rule.group}


@router.get("/custom/{rule_id}")
async def get_custom_rule(
    rule_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    import uuid
    result = await session.execute(
        select(CustomRule).where(
            CustomRule.id == uuid.UUID(rule_id),
            CustomRule.user_id == user.id,
        )
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return {
        "id": str(rule.id),
        "name": rule.name,
        "description": rule.description,
        "rule_type": rule.rule_type,
        "rule_code": rule.rule_code,
        "severity": rule.severity,
        "group": rule.group,
    }


@router.put("/custom/{rule_id}")
async def update_custom_rule(
    rule_id: str,
    req: CustomRuleCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    import uuid
    result = await session.execute(
        select(CustomRule).where(
            CustomRule.id == uuid.UUID(rule_id),
            CustomRule.user_id == user.id,
        )
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    rule.name = req.name
    rule.description = req.description or req.name
    rule.rule_type = req.rule_type
    rule.rule_code = req.rule_code
    rule.severity = req.severity
    rule.group = req.group
    await session.commit()
    return {"id": str(rule.id), "name": rule.name, "group": rule.group}


@router.get("/custom")
async def list_custom_rules(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(CustomRule).where(CustomRule.user_id == user.id)
    )
    rules = result.scalars().all()
    return [
        {"id": str(r.id), "name": r.name, "type": r.rule_type, "severity": r.severity, "group": r.group, "rule_code": r.rule_code, "description": r.description}
        for r in rules
    ]


@router.delete("/custom/{rule_id}")
async def delete_custom_rule(
    rule_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    from sqlalchemy.dialects.postgresql import UUID as PG_UUID
    import uuid
    result = await session.execute(
        select(CustomRule).where(
            CustomRule.id == uuid.UUID(rule_id),
            CustomRule.user_id == user.id,
        )
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    await session.delete(rule)
    await session.commit()
    return {"ok": True}


@router.get("/groups/manage")
async def list_user_groups(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(RuleGroup).where(
            (RuleGroup.user_id == user.id) | (RuleGroup.is_builtin == True)
        )
    )
    return [
        {"id": str(g.id), "name": g.name, "label": g.label, "description": g.description, "icon": g.icon, "is_builtin": g.is_builtin}
        for g in result.scalars().all()
    ]


@router.post("/groups/manage")
async def create_user_group(
    req: RuleGroupCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    existing = await session.execute(
        select(RuleGroup).where(RuleGroup.name == req.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Group name already exists")
    group = RuleGroup(
        user_id=user.id,
        name=req.name,
        label=req.label,
        description=req.description,
        icon=req.icon,
    )
    session.add(group)
    await session.commit()
    await session.refresh(group)
    return {"id": str(group.id), "name": group.name, "label": group.label}


@router.put("/groups/manage/{group_id}")
async def update_user_group(
    group_id: str,
    req: RuleGroupUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    import uuid
    result = await session.execute(
        select(RuleGroup).where(
            RuleGroup.id == uuid.UUID(group_id),
            RuleGroup.user_id == user.id,
        )
    )
    g = result.scalar_one_or_none()
    if not g:
        raise HTTPException(status_code=404, detail="Group not found or is built-in")
    if req.label is not None:
        g.label = req.label
    if req.description is not None:
        g.description = req.description
    if req.icon is not None:
        g.icon = req.icon
    await session.commit()
    return {"ok": True}


@router.delete("/groups/manage/{group_id}")
async def delete_user_group(
    group_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    import uuid
    result = await session.execute(
        select(RuleGroup).where(
            RuleGroup.id == uuid.UUID(group_id),
            RuleGroup.user_id == user.id,
        )
    )
    g = result.scalar_one_or_none()
    if not g:
        raise HTTPException(status_code=404, detail="Group not found or is built-in")
    await session.delete(g)
    await session.commit()
    return {"ok": True}
