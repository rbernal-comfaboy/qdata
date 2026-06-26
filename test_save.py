import httpx, asyncio

async def main():
    async with httpx.AsyncClient() as c:
        r = await c.post('http://localhost:8000/auth/login', json={'email':'demo@qdata.com','password':'qdata'})
        token = r.json()['access_token']
        print('Token obtained')

        headers = {'Authorization': f'Bearer {token}'}

        r = await c.post('http://localhost:8000/datasources/', headers=headers, json={
            'name': 'Test DB',
            'source_type': 'postgresql',
            'db_fields': {'host': 'postgres', 'port': 5432, 'database': 'qdata', 'username': 'qdata', 'password': 'qdata_pass', 'ssl': False}
        })
        print('Create DS:', r.status_code, r.json() if r.status_code < 400 else r.text)
        ds_id = r.json().get('id', '')

        if ds_id:
            r = await c.post('http://localhost:8000/sources/', headers=headers, json={
                'name': 'Test Source',
                'data_source_id': ds_id,
                'query': 'SELECT * FROM users',
                'selected_columns': [],
                'row_limit': None,
                'storage_mode': 'connection'
            })
            print('Create Source:', r.status_code, r.json() if r.status_code < 400 else r.text)

asyncio.run(main())
