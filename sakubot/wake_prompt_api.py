"""Configuration metadata and side-effect-free wake environment preview."""
from fastapi import Depends, Request

from .wake_prompt import DEFAULT, VARIABLES, CHANGE_DEFAULT, CHANGE_VARIABLES, RISK_DEFAULT, preview_context, render


def register_wake_prompt_api(app, authorize, runtime):
    @app.get('/api/wake-prompt', dependencies=[Depends(authorize)])
    async def catalog(kind: str = 'environment'):
        if kind not in ('environment', 'source_change', 'source_risk'):
            raise ValueError('模板类型无效')
        if kind == 'source_risk':
            return {'default': RISK_DEFAULT, 'variables': [{'name': name, 'label': label} for name, label in VARIABLES.items()]}
        if kind == 'source_change':
            return {'default': CHANGE_DEFAULT, 'variables': [{'name': name, 'label': label} for name, label in CHANGE_VARIABLES.items()]}
        return {'default': DEFAULT, 'variables': [{'name': name, 'label': label} for name, label in VARIABLES.items()]}

    @app.post('/api/wake-prompt/preview', dependencies=[Depends(authorize)])
    async def preview(request: Request):
        data = await request.json()
        if not isinstance(data, dict) or set(data) - {'template', 'kind'} or 'template' not in data:
            raise ValueError('预览参数无效')
        kind = data.get('kind', 'environment')
        if kind not in ('environment', 'source_change', 'source_risk'):
            raise ValueError('模板类型无效')
        variables = preview_context(runtime)
        if kind == 'source_change':
            current = variables['conversation']['current'] or {'id': '', 'name': '未选择', 'available': False, 'trusted': False}
            variables.update(previous_source={'id': '', 'name': '未选择', 'available': False, 'trusted': False}, current_source=current)
        return {'text': render(data['template'], variables, source_change=kind == 'source_change')}
