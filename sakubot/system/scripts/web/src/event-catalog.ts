export interface EventNode {
  key: string
  id: string
  name: string
  plugin: string
  declared: boolean
  available: boolean
  generic: boolean
  binding?: any
  children: EventNode[]
  bound: number
}

export function matches(pattern: string, value: string) {
  const expression = pattern.split('*').map(part => part.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('.*')
  return new RegExp('^' + expression + '$').test(value)
}

export function eventCatalog(catalog: any, query: string): EventNode[] {
  const sources = catalog.sources || []
  const bindings = catalog.bindings || []
  const ids: string[] = [...new Set<string>([...sources.map((s: any) => s.id), ...bindings.map((b: any) => b.source)])]
  const nodes = new Map<string, EventNode>()
  for (const id of ids) {
    const source = sources.find((s: any) => s.id === id)
    const resolved = source || sources.filter((s: any) => s.id.includes('*') && matches(s.id, id))
      .sort((a: any, b: any) => b.id.replaceAll('*', '').length - a.id.replaceAll('*', '').length)[0]
    const own = bindings.filter((b: any) => b.source === id)
    const generic = id.includes('*')
    const binding = !generic && own.length === 1 ? own[0] : undefined
    nodes.set(id, {
      key: id, id, name: source?.name || id.split('.').pop() || id,
      plugin: resolved?.plugin_id || id.split('.')[0],
      declared: !!resolved, available: !!resolved?.available, generic, binding,
      bound: own.length,
      children: generic || own.length > 1 ? own.map((b: any) => ({
        key: 'binding:' + b.id, id, name: b.name, plugin: resolved?.plugin_id || id.split('.')[0],
        declared: !!resolved, available: !!resolved?.available, generic: false,
        binding: b, children: [], bound: 1,
      })) : [],
    })
  }
  const roots: EventNode[] = []
  for (const node of nodes.values()) {
    const parent = [...nodes.values()]
      .filter(other => other.generic && other.id !== node.id &&
        other.id.replaceAll('*', '').length < node.id.replaceAll('*', '').length && matches(other.id, node.id))
      .sort((a, b) => b.id.replaceAll('*', '').length - a.id.replaceAll('*', '').length)[0]
    if (parent) parent.children.push(node)
    else roots.push(node)
  }
  const term = query.trim().toLowerCase()
  function visit(items: EventNode[], inherited = false): EventNode[] {
    return items.map(node => {
      const match = inherited || !term || JSON.stringify([node.name, node.id, node.plugin, node.binding]).toLowerCase().includes(term)
      const children = visit(node.children, match)
      return { ...node, children, bound: node.binding ? 1 : children.length ? children.reduce((sum, n) => sum + n.bound, 0) : node.bound, match }
    }).filter(node => node.match || node.children.length)
      .sort((a, b) => Number(b.bound > 0) - Number(a.bound > 0) || a.id.localeCompare(b.id) || a.key.localeCompare(b.key))
  }
  return visit(roots)
}
