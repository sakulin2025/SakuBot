"""One trusted script revision per process; JSONL RPC on original stdout."""
import asyncio
import inspect
import importlib.util
import json
import sys
import traceback
from pathlib import Path
from .sdk import Context


async def run():
    protocol = sys.stdout
    boot = json.loads(sys.stdin.readline())
    sys.stdout = sys.stderr
    ctx = Context(boot, protocol, sys.stdin)
    try:
        namespace = {'__name__':'__sakubot_script__','__file__':boot['code_path']}
        types_path = Path(boot['code_path']).with_suffix('.types.py')
        if types_path.is_file():
            spec = importlib.util.spec_from_file_location('script_types', types_path)
            module = importlib.util.module_from_spec(spec)
            sys.modules['script_types'] = module
            spec.loader.exec_module(module)
        code = Path(boot['code_path']).read_text(encoding='utf-8')
        exec(compile(code, boot['code_path'], 'exec'), namespace)
        result = namespace['main'](ctx)
        if inspect.isawaitable(result):
            result = await result
        ctx.send({'op':'result','result':result})
    except BaseException as exc:
        traceback.print_exc(file=sys.stderr)
        ctx.send({'op':'failed','error':str(exc)[:2000] or type(exc).__name__})
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(asyncio.run(run()))
