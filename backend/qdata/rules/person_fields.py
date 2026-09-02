"""Automatic detection of person identity columns (document type/number, names,
surnames) across different source schemas, plus helpers to build light per-row
value subsets so error payloads stay small for giant reports."""

import re

import pandas as pd

EMAIL_COL_RE = re.compile(r"(?i)(email|correo|e-?mail|mail|contacto)")

PHONE_COL_RE = re.compile(r"(?i)(tele|tel[^e]|celu|celular|mobile|phone|fijo|whatsapp|movil|ntel)")

_PHONE_EXCLUDE_RE = re.compile(r"(?i)(sin.*tel|null.*(cel|tel)|moti.*(cel|tel))")

_DOC_TYPE_PATTERNS = (
    r"tipodoc", r"tip.*doc", r"tido", r"tiid", r"tipoidentif", r"tip.*ident",
    r"tip_terc", r"tip.*terc", r"tip_codi", r"tip.*codi", r"tipo_documento",
    r"tipodocumento",
)
_DOC_NUM_PATTERNS = (
    r"numdoc", r"num.*doc", r"nudo", r"nuid", r"numeroidentif", r"nume.*ident",
    r"cod_terc", r"nide", r"nu.*terc", r"numero_documento", r"numerodocumento",
    r"num_doc", r"nrodoc", r"nro.*doc", r"doc.*num",
)
_FIRST_NAME_PATTERNS = (
    r"prinom", r"pri.*nom", r"nom1", r"nombre1", r"primer.*nom", r"primero.*nom",
    r"nombusua", r"nom_terc", r"clie_noma", r"first.*nom", r"nomb", r"nombre",
)
_SECOND_NAME_PATTERNS = (
    r"segnom", r"seg.*nom", r"nom2", r"nombre2", r"segundo.*nom", r"seg.*nombre",
)
_FIRST_SURNAME_PATTERNS = (
    r"priape", r"pri.*ape", r"ape1", r"clie_apel", r"primer.*ape", r"apellido1",
    r"apel", r"ape_terc", r"ape.*1",
)
_SECOND_SURNAME_PATTERNS = (
    r"seg.*ape", r"ape2", r"clie_ape2", r"apellido2", r"seg.*apellido", r"ape.*2",
)

_NIT_COL_RE = re.compile(r"(?i)(^|\W)nit(\W|$)|num.?nit|nit.?num|nit_empresa|nitproveedor|nit_terc")

_DV_COL_RE = re.compile(r"(?i)(digito.*verificacion|dverif|verificacion|\bdv\b)")

_CATEGORY_ORDER = ("doc_type", "doc_num", "first_name", "second_name", "first_surname", "second_surname")


def _claim(columns: list[str], taken: set[str], *patterns: str) -> str | None:
    for pat in patterns:
        rx = re.compile(pat, re.IGNORECASE)
        for c in columns:
            if c in taken:
                continue
            if rx.search(c):
                taken.add(c)
                return c
    return None


def identity_field_columns(columns) -> list[str]:
    """Ordered [doc_type, doc_num, first_name, second_name, first_surname,
    second_surname] present in the given columns, or [] when nothing
    identity-ish is found."""
    cols = list(columns)
    taken: set[str] = set()
    found = {
        "doc_num": _claim(cols, taken, *_DOC_NUM_PATTERNS),
        "doc_type": _claim(cols, taken, *_DOC_TYPE_PATTERNS),
        "second_name": _claim(cols, taken, *_SECOND_NAME_PATTERNS),
        "first_name": _claim(cols, taken, *_FIRST_NAME_PATTERNS),
        "second_surname": _claim(cols, taken, *_SECOND_SURNAME_PATTERNS),
        "first_surname": _claim(cols, taken, *_FIRST_SURNAME_PATTERNS),
    }
    return [found[k] for k in _CATEGORY_ORDER if found.get(k)]


def doc_number_column(columns) -> str | None:
    return _claim(list(columns), set(), *_DOC_NUM_PATTERNS)


def doc_type_column(columns) -> str | None:
    return _claim(list(columns), set(), *_DOC_TYPE_PATTERNS)


def nit_columns(columns) -> list[str]:
    return [c for c in columns if _NIT_COL_RE.search(str(c))]


def doc_dv_column(columns) -> str | None:
    """Columna de dígito de verificación de documento (p.ej. perDigitoVerificacion)."""
    for c in columns:
        if _DV_COL_RE.search(str(c)):
            return c
    return None


def email_columns(columns) -> list[str]:
    return [c for c in columns if EMAIL_COL_RE.search(str(c))]


def phone_columns(columns) -> list[str]:
    all_phone = [
        c for c in columns
        if PHONE_COL_RE.search(str(c)) and not _PHONE_EXCLUDE_RE.search(str(c))
    ]
    # Prioritize PerTelefo as the primary phone column for display, exclude PerTelCel, PerTelCli
    if "PerTelefo" in all_phone:
        return ["PerTelefo"]
    return all_phone


def row_values(df: pd.DataFrame, idx: int, columns=None) -> dict | None:
    """Safe dict of one row's values for the given columns (or all columns)."""
    if idx not in df.index:
        return None
    if columns is not None:
        keep = [c for c in columns if c in df.columns]
        row = df.loc[idx, keep]
        return {c: (row[c].item() if hasattr(row[c], "item") else row[c]) for c in keep}
    row = df.loc[idx]
    return {c: (row[c].item() if hasattr(row[c], "item") else row[c]) for c, v in row.items()}
