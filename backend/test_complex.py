import pandas as pd
from qdata.rules.person_dedup_rules import PersonCompositeSimilarity
df = pd.DataFrame({
    "nombre": ["Ana Maria Garcia Lopez", "Ana Maria Garcia Lopes", "Ana M Garcia Lopez",
               "Juan Carlos Rodriguez", "Juan C Rodriguez",
               "Maria Elena Fernandez", "Maria Elena Fernandez",
               "Pedro Pablo Suarez", "Pedro Suarez"],
    "cedula": ["12345678", "12345679", "12345678",
               "87654321", "87654320",
               "55555555", "55555555",
               "11111111", "22222222"],
    "fecha_nacimiento": pd.to_datetime([
        "1990-05-15", "1990-05-14", "1990-05-15",
        "1985-03-20", "1985-03-21",
        "1975-10-10", "1975-10-10",
        "2000-01-01", "2000-01-01",
    ]),
})
rule = PersonCompositeSimilarity()
res = rule.execute(df)
print(f"Composite: {res.failed}/{res.total} failed")
for d in res.details:
    if isinstance(d, dict) and "groups" in d:
        print(f"  Total groups: {d['total_groups']}")
        for g in d["groups"][:3]:
            print(f"  Group: size={g['group_size']}, score={g['composite_score']}")
            for r in g["rows"]:
                print(f"    row {r['row']}: {r['values']}")
