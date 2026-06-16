import asyncio, httpx, json
async def t():
    c = httpx.AsyncClient()
    r = await c.post("http://localhost:8000/auth/login", json={"email":"demo@qdata.com","password":"demo123"})
    h = {"Authorization": "Bearer " + str(r.json().get("access_token",""))}
    r = await c.get("http://localhost:8000/api/connections/", headers=h)
    conns = r.json()
    print(f"Connections ({len(conns)}):")
    json.dumps(conns, indent=2)[:3000]
    for conn in conns:
        print(f"  {conn.get('id','')[:8]}: {conn.get('name','')} type={conn.get('source_type','')} path={conn.get('file_path','')}")
    # Also check sources details
    r = await c.get("http://localhost:8000/sources/", headers=h)
    for src in r.json():
        print(f"  Source: {src.get('name','')} ds_id={src.get('data_source_id','')[:12]}")
    await c.aclose()
asyncio.run(t())
