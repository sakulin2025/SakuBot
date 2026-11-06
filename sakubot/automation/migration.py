"""One-way source migration for pre-dictionary scripts; no legacy runtime API."""
import ast


def migrate_source(code):
    tree = ast.parse(code)
    entry = next((n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name=='main'),None)
    if not entry or len(entry.args.args) != 1:
        return code
    ctx_name = entry.args.args[0].arg
    helpers = {n.name for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and any(a.arg==ctx_name for a in n.args.args)}
    class Migrate(ast.NodeTransformer):
        def visit_ImportFrom(self, node):
            return None if node.module=='script_types' else node
        def visit_arg(self, node):
            if node.annotation and 'ScriptContext' in ast.unparse(node.annotation):node.annotation=None
            return node
        def function(self, node):
            if node.name in helpers:
                node.args.args.extend([ast.arg(arg='event'),ast.arg(arg='tools')])
            return self.generic_visit(node)
        visit_FunctionDef = function
        visit_AsyncFunctionDef = function
        def visit_Call(self, node):
            f=node.func
            if isinstance(f,ast.Name) and f.id=='getattr' and len(node.args)>=2 and isinstance(node.args[0],ast.Name) and node.args[0].id==ctx_name and isinstance(node.args[1],ast.Constant):
                key=node.args[1].value
                return ast.Name(id='event',ctx=ast.Load()) if key=='event' else ast.Call(func=ast.Attribute(value=ast.Name(id=ctx_name,ctx=ast.Load()),attr='get',ctx=ast.Load()),args=node.args[1:],keywords=[])
            if isinstance(f,ast.Attribute) and isinstance(f.value,ast.Name) and f.value.id==ctx_name and f.attr=='call':
                name=node.args[1] if len(node.args)>1 else next(kw.value for kw in node.keywords if kw.arg=='tool')
                args=node.args[2] if len(node.args)>2 else next((kw.value for kw in node.keywords if kw.arg=='arguments'),ast.Dict(keys=[],values=[]))
                return ast.Call(func=ast.Subscript(value=ast.Name(id='tools',ctx=ast.Load()),slice=name,ctx=ast.Load()),args=[],keywords=[ast.keyword(arg=None,value=self.visit(args))])
            if isinstance(f,ast.Name) and f.id in helpers and node.args and isinstance(node.args[0],ast.Name) and node.args[0].id==ctx_name:
                node.args.extend([ast.Name(id='event',ctx=ast.Load()),ast.Name(id='tools',ctx=ast.Load())])
            return self.generic_visit(node)
        def visit_Attribute(self,node):
            # ctx.tools.plugin.function -> tools['function']
            v=node.value
            if isinstance(v,ast.Attribute) and isinstance(v.value,ast.Attribute) and isinstance(v.value.value,ast.Name) and v.value.value.id==ctx_name and v.value.attr=='tools':
                return ast.Subscript(value=ast.Name(id='tools',ctx=ast.Load()),slice=ast.Constant(node.attr),ctx=node.ctx)
            if isinstance(v,ast.Attribute) and isinstance(v.value,ast.Name) and v.value.id==ctx_name and v.attr=='state':
                return ast.Subscript(value=ast.Name(id='tools',ctx=ast.Load()),slice=ast.Constant('script_state_'+node.attr),ctx=node.ctx)
            if isinstance(v,ast.Name) and v.id==ctx_name:
                if node.attr=='event':return ast.Name(id='event',ctx=node.ctx)
                if node.attr in ('wake','notify','log'):
                    return ast.Subscript(value=ast.Name(id='tools',ctx=ast.Load()),slice=ast.Constant('script_'+node.attr),ctx=node.ctx)
                return ast.Subscript(value=ast.Name(id=ctx_name,ctx=ast.Load()),slice=ast.Constant(node.attr),ctx=node.ctx)
            return self.generic_visit(node)
    tree=Migrate().visit(tree)
    return ast.unparse(ast.fix_missing_locations(tree))+'\n'
