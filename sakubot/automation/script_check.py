"""Static-only diagnostics. No script imports, execution or network probes."""
import ast
import asyncio
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from .script_contracts import development


class ScriptDiagnosticsError(ValueError):
    def __init__(self, report):
        self.report = report
        super().__init__('脚本未保存：存在类型错误或警告，修正后重试；仅类型诊断可用 hard=true 和 hard_reason 绕过')


def diagnostic(message, *, severity='warning', line=1, column=1, rule='contract'):
    return {'severity':severity,'message':message,'line':line,'column':column,'rule':rule}


async def check(runtime, code, *, sources=(), parameters=None, tool_plugins=None):
    diagnostics = []
    if not isinstance(code,str) or len(code.encode())>200000:
        return {'ok':False,'syntax_ok':False,'diagnostics':[diagnostic('代码须为不超过200 KB的文本',severity='error',rule='syntax')]}
    try:
        tree = ast.parse(code)
        compile(tree,'script.py','exec')
    except (SyntaxError,ValueError,TypeError) as exc:
        return {'ok':False,'syntax_ok':False,'diagnostics':[diagnostic(str(exc),severity='error',line=getattr(exc,'lineno',1) or 1,column=getattr(exc,'offset',1) or 1,rule='syntax')]}
    entry = next((node for node in tree.body if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name=='main'),None)
    if not entry or len(entry.args.args)!=1 or entry.args.vararg or entry.args.kwarg or entry.args.kwonlyargs:
        return {'ok':False,'syntax_ok':False,'diagnostics':[diagnostic('必须定义且只接受一个上下文参数的 main(ctx)',severity='error',rule='entrypoint')]}
    if entry.args.args[0].annotation is None:
        diagnostics.append(diagnostic('main 的 ctx 缺少类型：先读取 script_development，使用 from script_types import ScriptContext 并标注 ctx: ScriptContext',line=entry.lineno))
    elif not ((isinstance(entry.args.args[0].annotation, ast.Name) and entry.args.args[0].annotation.id == 'ScriptContext') or (isinstance(entry.args.args[0].annotation, ast.Attribute) and entry.args.args[0].annotation.attr == 'ScriptContext')):
        diagnostics.append(diagnostic('入口上下文应使用生成的 ScriptContext；不要用 Any 或自行猜测 Context 结构',line=entry.lineno))
    if entry.returns is None:
        diagnostics.append(diagnostic('main 需声明返回类型，例如 -> object 或具体 TypedDict',line=entry.lineno))
    dev = development(runtime,sources=sources,parameters=parameters,tool_plugins=tool_plugins)
    for source in dev['unknown_sources']:
        diagnostics.append(diagnostic('来源未声明，无法确认事件类型：'+source))
    if any(line.lstrip().startswith('# pyright:') for line in code.splitlines()):
        diagnostics.append(diagnostic('脚本包含 Pyright 局部规则覆盖；请移除并使用框架统一检查策略'))
    for node in ast.walk(tree):
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute):
            if node.func.attr=='call' and isinstance(node.func.value,ast.Name) and node.func.value.id==entry.args.args[0].arg:
                diagnostics.append(diagnostic('ctx.call 为动态调用，不能静态确认参数和返回类型；请使用 ctx.tools.<插件>.<工具>(...)',line=node.lineno))
            if isinstance(node.func.value,ast.Attribute) and isinstance(node.func.value.value,ast.Attribute) and node.func.value.value.attr=='tools':
                name=node.func.value.attr+'.'+node.func.attr
                if name in dev['unknown_results']:
                    diagnostics.append(diagnostic('该工具尚未声明返回类型，结果为 object，不要猜结构：'+name,line=node.lineno))
    checker = next((path for path in [Path(os.environ.get('SAKUBOT_PYRIGHT','/app/script-checker/node_modules/pyright/index.js')),
        Path(__file__).resolve().parents[2]/'frontend/node_modules/pyright/index.js'] if path.is_file()),None)
    node = shutil.which('node')
    checker_available = bool(checker and node)
    if not checker_available:
        diagnostics.append(diagnostic('Pyright 不可用，类型检查未完成；安装检查器后重试',severity='error',rule='checker_unavailable'))
    else:
        with tempfile.TemporaryDirectory(prefix='sakubot-script-check-') as folder:
            root=Path(folder)
            (root/'script.py').write_text(code)
            (root/'script_types.py').write_text(dev['sdk'])
            (root/'script_types.pyi').write_text(dev['sdk'])
            config={'include':['script.py'],'pythonVersion':'3.13','typeCheckingMode':'standard',
                'extraPaths':[str(Path(__file__).resolve().parents[2])], 'useLibraryCodeForTypes':True,
                'reportMissingTypeStubs':'none','reportUnknownParameterType':'warning',
                'reportUnknownVariableType':'warning','reportUnknownArgumentType':'warning',
                'reportUnknownMemberType':'warning','reportUnnecessaryTypeIgnoreComment':'warning',
                'enableTypeIgnoreComments':False}
            (root/'pyrightconfig.json').write_text(json.dumps(config))
            process=None
            try:
                process=await asyncio.create_subprocess_exec(node,'--max-old-space-size=512',str(checker),'--outputjson','--project',str(root/'pyrightconfig.json'),cwd=root,
                    stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
                output, errors = await asyncio.wait_for(process.communicate(),45)
                body=json.loads(output)
                if process.returncode not in (0,1) or 'generalDiagnostics' not in body:
                    raise ValueError('检查器未返回有效诊断')
                for row in body['generalDiagnostics']:
                    if Path(row.get('file','')).name!='script.py':
                        if Path(row.get('file','')).name in ('script_types.py','script_types.pyi') and row.get('severity')=='error':
                            checker_available=False
                            diagnostics.append(diagnostic('生成的 SDK 类型无法检查：'+row['message'],severity='error',rule='checker_failed'))
                        continue
                    start=row.get('range',{}).get('start',{})
                    diagnostics.append(diagnostic(row['message'],severity=row['severity'],line=start.get('line',0)+1,column=start.get('character',0)+1,rule=row.get('rule','pyright')))
            except asyncio.CancelledError:
                raise
            except (TimeoutError,OSError,ValueError,KeyError) as exc:
                checker_available=False
                diagnostics.append(diagnostic('类型检查未完成：'+str(exc)[:300],severity='error',rule='checker_failed'))
            finally:
                if process and process.returncode is None:
                    process.kill()
                    await process.wait()
    relevant=[row for row in diagnostics if row['severity'] in ('error','warning')]
    return {'ok':not relevant,'syntax_ok':True,'checker_available':checker_available,'diagnostics':diagnostics[:100], 'diagnostic_count':len(diagnostics),
        'sdk':dev['sdk'],'event_contracts':dev['event_contracts'],
        'sdk_hash':hashlib.sha256(dev['sdk'].encode()).hexdigest(),'checker':'pyright'}
