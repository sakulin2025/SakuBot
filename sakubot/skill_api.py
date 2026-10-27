from fastapi import Depends, Query


def register_skill_api(app, authorize, runtime):
    auth = [Depends(authorize)]

    @app.get('/api/skills', dependencies=auth)
    async def catalog(query: str = ''):
        rows = runtime.skills.catalog()
        search = query.casefold()
        return {'items': [row for row in rows if search in (row['id'] + row['name'] + row['description']).casefold()],
            'errors': runtime.skills.errors}

    @app.get('/api/skills/{identifier}', dependencies=auth)
    async def read(identifier: str):
        return runtime.skills.read(identifier)

    @app.get('/api/skills/{identifier}/file', dependencies=auth)
    async def read_file(identifier: str, path: str, offset: int = Query(0, ge=0), limit: int = Query(200, ge=1, le=500)):
        return runtime.skills.read_file(identifier, path, offset, limit)
