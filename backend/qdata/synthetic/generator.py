import random
import string
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from qdata.synthetic.corruptors import corrupt
from qdata.synthetic.profiles import PROFILES


def _generate_value(col_def: dict) -> any:
    t = col_def["type"]
    if t == "int":
        return random.randint(col_def.get("min", 0), col_def.get("max", 1000))
    elif t == "float":
        mean = col_def.get("mean", 0)
        std = col_def.get("std", 1)
        val = np.random.normal(mean, std)
        return max(col_def.get("min", float("-inf")),
                   min(col_def.get("max", float("inf")), round(val, 2)))
    elif t == "choice":
        return random.choice(col_def["values"])
    elif t == "name":
        first = random.choice(["Ana", "Carlos", "María", "Juan", "Sofía", "Luis", "Elena",
                                "Pedro", "Laura", "Diego", "Valentina", "Andrés", "Camila"])
        last = random.choice(["García", "Rodríguez", "Martínez", "López", "Hernández",
                               "González", "Pérez", "Sánchez", "Ramírez", "Torres"])
        return f"{first} {last}"
    elif t == "email":
        domains = ["gmail.com", "yahoo.com", "hotmail.com", "empresa.com", "outlook.com"]
        name = "".join(random.choices(string.ascii_lowercase, k=8))
        return f"{name}@{random.choice(domains)}"
    elif t == "date":
        start = datetime.strptime(col_def["start"], "%Y-%m-%d")
        end = datetime.strptime(col_def["end"], "%Y-%m-%d")
        delta = (end - start).days
        return (start + timedelta(days=random.randint(0, delta))).strftime("%Y-%m-%d")
    elif t == "string":
        length = col_def.get("length", 10)
        prefix = col_def.get("prefix", "")
        return prefix + "".join(random.choices(string.ascii_uppercase + string.digits, k=length))
    return None


def generate_dataset(profile_name: str, rows: int = 1000) -> pd.DataFrame:
    profile = PROFILES.get(profile_name)
    if not profile:
        available = list(PROFILES.keys())
        raise ValueError(f"Perfil '{profile_name}' no encontrado. Disponibles: {available}")

    data = {}
    for col_def in profile["columns"]:
        data[col_def["name"]] = [_generate_value(col_def) for _ in range(rows)]

    return pd.DataFrame(data)


def generate(
    profile_name: str,
    rows: int = 1000,
    output: str = "",
    null_rate: float = 0.0,
    duplicate_rate: float = 0.0,
    outlier_rate: float = 0.0,
    typo_rate: float = 0.0,
) -> pd.DataFrame:
    df = generate_dataset(profile_name, rows)
    df = corrupt(df, null_rate=null_rate, duplicate_rate=duplicate_rate,
                 outlier_rate=outlier_rate, typo_rate=typo_rate)

    if output:
        ext = output.rsplit(".", 1)[-1].lower()
        if ext == "csv":
            df.to_csv(output, index=False)
        elif ext == "xlsx":
            df.to_excel(output, index=False)
        elif ext == "json":
            df.to_json(output, orient="records", indent=2)
        elif ext == "parquet":
            df.to_parquet(output, index=False)

    return df
