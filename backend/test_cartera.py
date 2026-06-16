import asyncio, httpx, json, sys, traceback
sys.path.insert(0, "/app")
from qdata.core.loader import load_data
from qdata.core.engine import Engine
from qdata.rules.person_dedup_rules import PersonCompositeSimilarity

async def t():
    # Load the cartera data using connector from sources
    c = httpx.AsyncClient()
    r = await c.post("http://localhost:8000/auth/login", json={"email":"demo@qdata.com","password":"demo123"})
    h = {"Authorization": "Bearer " + str(r.json().get("access_token",""))}
    r = await c.get("http://localhost:8000/sources/", headers=h)
    src = r.json()[0]
    sid = src["id"]
    # Get source details
    r = await c.get(f"http://localhost:8000/sources/{sid}", headers=h)
    sdata = r.json()
    print("Source query:", str(sdata.get("query",""))[:200])
    print("Source data_source:", sdata.get("data_source_id",""))
    dsid = sdata["data_source_id"]
    r = await c.get(f"http://localhost:8000/api/connections/{dsid}", headers=h)
    ds = r.json()
    print("DS type:", ds.get("source_type",""), "path:", ds.get("file_path",""))
    
    # Load data
    df = load_data(ds.get("source_type",""), ds.get("connection_string",""), sdata.get("query",""), ds.get("file_path",""))
    print(f"DataFrame shape: {df.shape}")
    print(f"Columns: {list(df.columns)}")
    print(f"First 3 rows:")
    print(df.head(3).to_string())
    
    # Test composite rule
    rule = PersonCompositeSimilarity()
    try:
        res = rule.execute(df)
        print(f"\nComposite result: failed={res.failed}/{res.total}")
        for d in res.details:
            if isinstance(d, dict):
                print(f"  {d.get('note', '')} {d.get('total_groups', '')}")
    except Exception as e:
        print(f"ERROR: {e}")
        traceback.print_exc()
    await c.aclose()
asyncio.run(t())
