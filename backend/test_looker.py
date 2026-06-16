import asyncio, httpx, json
async def t():
    c = httpx.AsyncClient()
    r = await c.post("http://localhost:8000/auth/login", json={"email":"demo@qdata.com","password":"demo123"})
    h = {"Authorization": "Bearer " + str(r.json().get("access_token",""))}
    r = await c.get("http://localhost:8000/datasources/", headers=h)
    print("Existing connections:")
    for ds in r.json():
        print(f'  {ds["name"]}: type={ds["source_type"]}, db_fields={json.dumps(ds.get("db_fields",{}))[:120]}')
    
    print("\n--- Test connection (PostgreSQL) ---")
    payload = {"source_type": "postgresql", "db_fields": {"host": "localhost", "port": 5432, "database": "qdata", "username": "qdata", "password": "qdata_pass", "ssl": False}}
    r = await c.post("http://localhost:8000/datasources/test", headers=h, json=payload)
    print(json.dumps(r.json(), indent=2)[:500])
    
    print("\n--- Create new connection ---")
    r = await c.post("http://localhost:8000/datasources/", headers=h, json={
        "name": "BD Test (Looker style)",
        "source_type": "postgresql",
        "db_fields": {"host": "postgres", "port": 5432, "database": "qdata", "username": "qdata", "password": "qdata_pass", "ssl": False}
    })
    new_ds = r.json()
    print(f'Created: {new_ds.get("name","?")}, id={new_ds.get("id","?")[:12]}')
    print(f'  connection_string: {str(new_ds.get("connection_string",""))[:80]}')
    print(f'  db_fields: {json.dumps(new_ds.get("db_fields",{}))[:150]}')
    
    print("\n--- Get single datasource ---")
    did = new_ds["id"]
    r = await c.get(f"http://localhost:8000/datasources/{did}", headers=h)
    gds = r.json()
    print(f'  name={gds["name"]}, db_fields.host={gds.get("db_fields",{}).get("host","?")}')
    await c.aclose()
asyncio.run(t())
