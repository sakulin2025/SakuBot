"""Syntax and entrypoint checks only; never import or execute submitted code."""
import ast


def check(code):
    try:
        tree = ast.parse(code)
        compile(tree, 'script.py', 'exec')
        entry = next((n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name=='main'),None)
        if not entry or [a.arg for a in entry.args.args] != ['ctx','event','tools'] or entry.args.posonlyargs or entry.args.vararg or entry.args.kwarg or entry.args.kwonlyargs or entry.args.defaults:
            raise ValueError('入口须为 main(ctx, event, tools)')
        return {'ok':True,'diagnostics':[]}
    except (SyntaxError,ValueError,TypeError) as exc:
        return {'ok':False,'diagnostics':[{'severity':'error','message':str(exc),'line':getattr(exc,'lineno',1) or 1,'column':getattr(exc,'offset',1) or 1}]}
