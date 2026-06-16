import asyncio, httpx, json
async def t():
    c = httpx.AsyncClient()
    r = await c.post("http://localhost:8000/auth/login", json={"email":"demo@qdata.com","password":"demo123"})
    h = {"Authorization": "Bearer " + str(r.json().get("access_token",""))}
    payload = {"project_name": "Test CSV Personas", "source_id": "15a6c41e-2efc-4b02-bae2-8a9974a73710", "rules": ["grupo:personas"]}
    r = await c.post("http://localhost:8000/analyze/", headers=h, json=payload)
    print("Status:", r.status_code)
    if r.status_code == 200:
        d = r.json()
        print("Score:", d.get("score"), d.get("label"))
        rid = d.get("report_id")
        r2 = await c.get(f"http://localhost:8000/reports/{rid}", headers=h)
        rd = r2.json()
        results = rd.get("result",{}).get("results",[])
        if not results:
            rj = rd.get("result_json","")
            if isinstance(rj,str) and rj:
                results = json.loads(rj).get("results",[])
        for res in results:
            print(f'  {res["rule_name"]}: pass={res["passed"]} fail={res["failed"]}/{res["total"]}')
    else:
        print(r.text[:1000])
    await c.aclose()
asyncio.run(t())
