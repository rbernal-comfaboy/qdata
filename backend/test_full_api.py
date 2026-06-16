import asyncio, httpx
async def t():
    c = httpx.AsyncClient()
    r = await c.post("http://localhost:8000/auth/login", json={"email":"demo@qdata.com","password":"demo123"})
    h = {"Authorization": "Bearer " + str(r.json().get("access_token",""))}
    r = await c.get("http://localhost:8000/sources/", headers=h)
    src = r.json()[0]
    payload = {"project_name": "Test Personas", "source_id": str(src["id"]), "rules": ["grupo:personas"]}
    r = await c.post("http://localhost:8000/analyze/", headers=h, json=payload)
    print("Status:", r.status_code)
    import json; d = r.json()
    print("Project:", d.get("project_id","?"), "Score:", d.get("score","?"), d.get("label","?"))
    # Also get the report to see results
    rid = d.get("report_id")
    if rid:
        r2 = await c.get(f"http://localhost:8000/reports/{rid}", headers=h)
        rdata = r2.json()
        for res in rdata.get("result_json",{}).get("results",[]):
            nm = res.get("rule_name","?")
            ps = res.get("passed","?")
            fl = res.get("failed","?")
            tl = res.get("total","?")
            print(f"  {nm}: passed={ps} failed={fl}/{tl}")
    await c.aclose()
asyncio.run(t())
