import { createRouter, createWebHashHistory } from 'vue-router'
export const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', component: () => import('./views/OverviewView.vue') },
    { path: '/chat', component: () => import('./views/ChatView.vue') },
    { path: '/model', component: () => import('./views/ModelWorkspace.vue') },
    { path: '/providers', redirect: (to) => ({ path: '/model', query: { ...to.query, tab: 'providers' } }) },
    { path: '/persona', redirect: '/personas' },
    { path: '/agents', component: () => import('./views/AgentWorkspace.vue') },
    { path: '/personas', redirect: to => ({ path: '/agents', query: { ...to.query, tab: 'personas' } }) },
    { path: '/settings', component: () => import('./views/RuntimeSettingsView.vue') },
    { path: '/message-processing', redirect: '/settings' },
    { path: '/plugins', component: () => import('./views/PluginWorkspace.vue') },
    { path: '/activity', component: () => import('./views/ActivityWorkspace.vue') },
    ...['events', 'logs', 'tool-calls', 'runs', 'deliveries'].map((tab) => ({
      path: '/' + tab,
      redirect: (to: import('vue-router').RouteLocationGeneric) => ({
        path: '/activity',
        query: { ...to.query, tab },
      }),
    })),
    { path: '/functions', redirect: to => ({ path: '/plugins', query: { ...to.query, tab: to.query.tab === 'skills' ? 'skills' : 'functions' } }) },
    { path: '/:pathMatch(.*)*', name: 'not-found', component: () => import('./views/NotFoundView.vue') },
  ],
  scrollBehavior: () => ({ top: 0 }),
})

router.onError((error, to) => {
  if (/Failed to fetch dynamically imported module|Importing a module script failed|Loading chunk|Failed to load module script/i.test(String(error))) {
    const key = 'sakubot:chunk-reload:' + to.fullPath
    const previous = Number(sessionStorage.getItem(key) || 0)
    if (Date.now() - previous > 60000) {
      sessionStorage.setItem(key, String(Date.now()))
      location.replace(location.pathname + location.search + '#' + to.fullPath)
      location.reload()
      return
    }
  }
  window.dispatchEvent(new CustomEvent('sakubot-navigation-error', { detail: '页面加载失败，请刷新后重试' }))
})
