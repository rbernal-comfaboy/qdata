import asyncio, httpx
async def t():
    c = httpx.AsyncClient()
    r = await c.post("http://localhost:8000/auth/login", json={"email":"demo@qdata.com","password":"demo123"})
    token = r.json()
    h = {"Authorization": "Bearer " + str(token.get("access_token", token.get("token", "")))}
    r = await c.get("http://localhost:8000/sources/", headers=h)
    src = r.json()[0]
    payload = {"source_id": str(src["id"]), "rules_config": ["grupo:personas"]}
    r = await c.post("http://localhost:8000/analyze/", headers=h, json=payload)
    print("Status:", r.status_code)
    print(r.text[:2000])
    await c.aclose()
asyncio.run(t())
