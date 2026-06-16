import asyncio, httpx, json
async def t():
    c = httpx.AsyncClient()
    r = await c.post("http://localhost:8000/auth/login", json={"email":"demo@qdata.com","password":"demo123"})
    h = {"Authorization": "Bearer " + str(r.json().get("access_token",""))}
    payload = {"project_name": "Test Personas 2", "source_id": "6f4a9f12-d501-46c6-8fef-3bb934631f3b", "rules": ["grupo:personas"]}
    r = await c.post("http://localhost:8000/analyze/", headers=h, json=payload)
    print("Status:", r.status_code)
    if r.status_code != 200:
        print("Error:", r.text[:2000])
        return
    d = r.json()
    print("Project:", d.get("project_id"), "Score:", d.get("score"), d.get("label"))
    rid = d.get("report_id")
    r2 = await c.get(f"http://localhost:8000/reports/{rid}", headers=h)
    rd = r2.json()
    results = rd.get("result", []) or rd.get("result_json",{}).get("results", [])
    if not results:
        print("No results found in report. Inspecting...")
        for k,v in rd.items():
            if isinstance(v, list):
                print(f"  report.{k}: list of {len(v)} items")
                if v and isinstance(v[0], dict):
                    print(f"    first item: {json.dumps(v[0], indent=2)[:300]}")
    else:
        for res in results:
            nm = res.get("rule_name","?")
            ps = res.get("passed","?")
            fl = res.get("failed","?")
            tl = res.get("total","?")
            print(f"  {nm}: passed={ps} failed={fl}/{tl}")
    await c.aclose()
asyncio.run(t())
