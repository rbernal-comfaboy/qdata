import asyncio, httpx, json
async def t():
    c = httpx.AsyncClient()
    r = await c.post("http://localhost:8000/auth/login", json={"email":"demo@qdata.com","password":"demo123"})
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    r = await c.get("http://localhost:8000/sources/", headers=headers)
    src = r.json()[0]
    print("Source:", src["name"])
    payload = {"source_id": str(src["id"]), "rules_config": ["grupo:personas"]}
    r = await c.post("http://localhost:8000/analyze/", headers=headers, json=payload)
    print("Status:", r.status_code)
    d = r.json()
    print("Project:", d.get("project_id","?"))
    for res in d.get("results", []):
        print(f'{res["rule_name"]}: passed={res["passed"]} failed={res["failed"]}/{res["total"]}')
    await c.aclose()
asyncio.run(t())
