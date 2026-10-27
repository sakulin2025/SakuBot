import type { PluginPage } from './types'
export interface NavItem {
  path: string
  label: string
  icon: string
  order: number
  routeName?: string
}
export interface NavGroup {
  label: string
  order: number
  items: NavItem[]
}
export function buildNavigation(pages: PluginPage[]): NavGroup[] {
  const groups: NavGroup[] = [
    {
      label: '工作台',
      order: 10,
      items: [
        { path: '/', label: '主导览', icon: 'dashboard', order: 0 },
        { path: '/chat', label: '主对话', icon: 'chat', order: 5 },
        { path: '/activity', label: '活动中心', icon: 'events', order: 10 },
      ],
    },
    {
      label: 'Agent',
      order: 20,
      items: [
        ['agents', 'Agent 管理', 'persona'],
        ['model', '模型', 'model'],
        ['personas', '人格', 'persona'],
      ].map(([path, label, icon], order) => ({ path: '/' + path, label: label!, icon: icon!, order })),
    },
    {
      label: '系统',
      order: 90,
      items: [
        ['functions', '能力', 'plugins'],
        ['settings', '运行设置', 'settings'],
        ['plugins', '插件管理', 'plugins'],
      ].map(([path, label, icon], order) => ({ path: '/' + path, label: label!, icon: icon!, order })),
    },
  ]
  for (const page of pages) {
    let group = groups.find((item) => item.label === page.group)
    if (!group) {
      group = { label: page.group, order: page.group_order, items: [] }
      groups.push(group)
    }
    group.items.push({ path: page.route, label: page.title, icon: page.icon, order: page.order + 10,
      routeName: `extension:${page.plugin_id}:${page.id}` })
  }
  return groups
    .sort((a, b) => a.order - b.order)
    .map((g) => ({ ...g, items: g.items.sort((a, b) => a.order - b.order) }))
}
