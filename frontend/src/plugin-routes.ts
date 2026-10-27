import { router } from './router'
import type { PluginPage } from './types'
const installed = new Map<string, { fingerprint: string; remove: () => void }>()
export async function synchronizePluginRoutes(pages: PluginPage[]) {
  const wanted = new Set(pages.map((p) => `extension:${p.plugin_id}:${p.id}`))
  const current = router.currentRoute.value
  for (const [name, entry] of installed)
    if (!wanted.has(name)) {
      entry.remove()
      installed.delete(name)
    }
  for (const page of pages) {
    const name = `extension:${page.plugin_id}:${page.id}`
    const fingerprint = JSON.stringify(page)
    if (installed.get(name)?.fingerprint === fingerprint) continue
    installed.get(name)?.remove()
    const remove = router.addRoute({
      path: page.route,
      alias: page.aliases,
      name,
      component: () => import('./views/PluginPageView.vue'),
      props: { page },
    })
    installed.set(name, { fingerprint, remove })
  }
  if (typeof current.name === 'string' && current.name.startsWith('extension:') && !wanted.has(current.name))
    await router.replace('/')
  else if (current.name === 'not-found') {
    const resolved = router.resolve(current.fullPath)
    await router.replace(resolved.name === 'not-found' ? '/' : current.fullPath)
  }
}
