import asyncio, httpx, json
async def t():
    c = httpx.AsyncClient()
    r = await c.post("http://localhost:8000/auth/login", json={"email":"demo@qdata.com","password":"demo123"})
    h = {"Authorization": "Bearer " + str(r.json().get("access_token",""))}
    # Create a direct analysis with in-memory data concept
    from qdata.core.engine import Engine
    import pandas as pd
    df = pd.DataFrame({
        "nombre": ["Ana Maria Garcia Lopez", "Ana Maria Garcia Lopes", "Ana M Garcia Lopez",
                   "Juan Carlos Rodriguez", "Juan C Rodriguez",
                   "Maria Elena Fernandez", "Maria Elena Fernandez",
                   "Pedro Suarez", "Luis Torres"],
        "cedula": ["12345678", "12345679", "12345678",
                   "87654321", "87654320",
                   "55555555", "55555555",
                   "11111111", "99999999"],
        "fecha_nacimiento": pd.to_datetime([
            "1990-05-15", "1990-05-14", "1990-05-15",
            "1985-03-20", "1985-03-21",
            "1975-10-10", "1975-10-10",
            "2000-01-01", "2001-06-15",
        ]),
    })
    engine = Engine(parallel=False)
    results = await engine.run(df, ["grupo:personas"])
    for res in results:
        status = "PASO" if res.passed else "FALLO"
        print(f"{res.rule_name}: {status} ({res.failed}/{res.total})")
        for d in res.details:
            if isinstance(d, dict) and "total_groups" in d:
                print(f"  Grupos: {d['total_groups']}")
                for g in d.get("groups", [])[:2]:
                    print(f"    size={g.get('group_size','?')} score={g.get('composite_score',g.get('avg_similarity','?'))}")
    await c.aclose()
asyncio.run(t())
