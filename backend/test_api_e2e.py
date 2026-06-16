import asyncio, httpx, json

async def run_analyze():
    c = httpx.AsyncClient()
    # Login
    r = await c.post("http://localhost:8000/auth/login", json={"email":"demo@qdata.com","password":"demo123"})
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Get sources
    r = await c.get("http://localhost:8000/sources/", headers=headers)
    sources = r.json()
    print(f"Sources: {len(sources)}")
    for s in sources:
        print(f"  {s['id']}: {s['name']} (conn={s.get('data_source_id','?')})")

    if not sources:
        print("No sources found, creating one...")
        # Get connections
        r = await c.get("http://localhost:8000/api/connections/", headers=headers)
        conns = r.json()
        print("Connections:", conns)
        return

    # Pick first source
    src = sources[0]
    print(f"\nAnalyzing source: {src['name']}")

    # Run analyze with persona group rules
    payload = {
        "source_id": str(src["id"]),
        "rules_config": ["grupo:personas"],
    }
    r = await c.post("http://localhost:8000/analyze", headers=headers, json=payload)
    result = r.json()
    print(f"Analyze status: {result.get('status', '?')}")
    print(f"Project ID: {result.get('project_id', '?')}")
    print(f"Results count: {len(result.get('results', []))}")
    for res in result.get("results", []):
        print(f"  {res['rule_name']}: passed={res['passed']}, failed={res['failed']}/{res['total']}")
    await c.aclose()

asyncio.run(run_analyze())
