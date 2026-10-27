import { createRouter, createWebHashHistory } from 'vue-router'
export const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', component: () => import('./views/OverviewView.vue') },
    { path: '/chat', component: () => import('./views/ChatView.vue') },
    { path: '/model', component: () => import('./views/ModelWorkspace.vue') },
    { path: '/providers', redirect: (to) => ({ path: '/model', query: { ...to.query, tab: 'providers' } }) },
    { path: '/persona', redirect: '/personas' },
    { path: '/agents', component: () => import('./views/AgentsView.vue') },
    { path: '/personas', component: () => import('./views/PersonasView.vue') },
    { path: '/settings', component: () => import('./views/RuntimeSettingsView.vue') },
    { path: '/message-processing', redirect: '/settings' },
    { path: '/plugins', component: () => import('./views/PluginsView.vue') },
    { path: '/activity', component: () => import('./views/ActivityWorkspace.vue') },
    ...['events', 'logs', 'tool-calls', 'runs', 'deliveries'].map((tab) => ({
      path: '/' + tab,
      redirect: (to: import('vue-router').RouteLocationGeneric) => ({
        path: '/activity',
        query: { ...to.query, tab },
      }),
    })),
    { path: '/functions', component: () => import('./views/CapabilitiesView.vue') },
    { path: '/:pathMatch(.*)*', name: 'not-found', component: () => import('./views/NotFoundView.vue') },
  ],
  scrollBehavior: () => ({ top: 0 }),
})
