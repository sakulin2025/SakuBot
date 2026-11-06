"""Static declaration inventory; never import plugins or invoke their tools."""
import ast
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


class Reference(str):
    pass


def value(node, env):
    if isinstance(node,ast.Constant):return node.value
    if isinstance(node,ast.Name):return env.get(node.id,Reference(node.id))
    if isinstance(node,ast.Attribute):return Reference(str(value(node.value,env))+'.'+node.attr)
    if isinstance(node,(ast.Tuple,ast.List)):return [value(item,env) for item in node.elts]
    if isinstance(node,ast.Dict):return {value(key,env):value(item,env) for key,item in zip(node.keys,node.values) if key is not None}
    if isinstance(node,ast.BinOp) and isinstance(node.op,ast.Add):
        a,b=value(node.left,env),value(node.right,env)
        return a+b if isinstance(a,str) and isinstance(b,str) else None
    if isinstance(node,ast.Call):
        if isinstance(node.func,ast.Name) and node.func.id=='getattr' and len(node.args)>=2:
            return Reference(str(value(node.args[0],env))+'.'+str(value(node.args[1],env)))
        if isinstance(node.func,ast.Attribute) and node.func.attr=='items':
            obj=value(node.func.value,env)
            return list(obj.items()) if isinstance(obj,dict) else []
    return None


def assign(target,item,env):
    if isinstance(target,ast.Name):env[target.id]=item
    elif isinstance(target,(ast.Tuple,ast.List)) and isinstance(item,(tuple,list)):
        for child,current in zip(target.elts,item):assign(child,current,env)


def declarations(path):
    tree=ast.parse(path.read_text())
    found=[]
    def block(nodes,env,cls):
        for node in nodes:
            if isinstance(node,ast.Assign):
                for target in node.targets:assign(target,value(node.value,env),env)
            if isinstance(node,ast.For):
                items=value(node.iter,env)
                if isinstance(items,(list,tuple)):
                    for item in items:
                        local=dict(env);assign(node.target,item,local);block(node.body,local,cls)
                continue
            if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
                env[node.name]=Reference('local.'+node.name)
                block(node.body,dict(env),cls);continue
            if isinstance(node,ast.ClassDef):block(node.body,{'self':Reference('self')},node.name);continue
            if isinstance(node,(ast.If,ast.Try,ast.With,ast.AsyncWith)):
                block(node.body,dict(env),cls)
                block(getattr(node,'orelse',[]),dict(env),cls)
                if isinstance(node,ast.Try):
                    for handler in node.handlers:block(handler.body,dict(env),cls)
                continue
            if not isinstance(node,ast.Expr) or not isinstance(node.value,ast.Call):continue
            call=node.value
            if not isinstance(call.func,ast.Attribute) or call.func.attr not in ('tool','typed_tool','function'):continue
            name=value(call.args[0],env) if call.args and call.func.attr!='function' else next((value(k.value,env) for k in call.keywords if k.arg=='name'),None)
            if not isinstance(name,str) or isinstance(name,Reference):continue
            callback=value(call.args[0] if call.func.attr=='function' else call.args[-1],env) if call.args else None
            found.append({'tool':name,'handler':str(callback),'class':cls,'kind':call.func.attr,'file':str(path),'line':node.lineno,
                'temporary':str(value(call.func.value,env)) not in ('self','self.plugin')})
    block(tree.body,{},'')
    return found


def inventory():
    rows=[]
    for group in ('sakubot/system','sakubot/plugins','extensions'):
        for path in sorted((ROOT/group).rglob('*.py')):
            if path.name not in ('event_types.py','tool_types.py'):
                rows.extend(declarations(path))
    return rows


if __name__=='__main__':
    print(json.dumps(inventory(),ensure_ascii=False,indent=2))
