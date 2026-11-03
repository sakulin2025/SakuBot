"""One-time retirement of plugin-local notification rules without replaying history."""
import time


def migrate_events(plugin):
    if plugin.state.get('events_migrated_v2', False):
        return
    service = plugin.runtime.scripts
    source = plugin.id + '.workout_added.*'
    old_source = plugin.id + '.workout_completed'
    rules = plugin.state.get('rules', {})
    monitor = plugin.state.get('monitor', {})
    # Keep original configuration and audit records, but never execute the old pending actions.
    archive = plugin.state.get('legacy_events_v1') or {
        'rules': rules, 'pending': monitor.get('pending', {}),
        'history': monitor.get('history', []), 'archived_at': time.time(),
    }
    plugin.state.set('legacy_events_v1', archive)
    bindings = service.repo.list('bindings')
    for binding in bindings:
        if binding['source'] == old_source and not any(row['source'] == source for row in service.repo.list('bindings')):
            service.save_binding({**binding, 'source': source})
    active = [rule for rule in rules.values() if rule.get('enabled')]
    if len(active) == 1 and active[0].get('mode') == 'wake' and not active[0].get('delay_minutes', 0):
        rule = active[0]
        binding_id = 'freereps_' + rule['id']
        current = service.repo.list('bindings')
        if not any(row['source'] == source for row in current):
            service.save_binding({
                'id': binding_id, 'name': rule['name'], 'source': source,
                'source_params': {'workout_type': rule.get('workout_type', '')},
                'target_kind': 'wake', 'prompt': rule.get('prompt') or '检测到新的训练记录，请按需查询详情并回应主人。',
                'enabled': True, 'send_result_to_source': True,
            })
        elif not any(row['id'] == binding_id for row in current):
            plugin.runtime.store.log('warning', plugin.id, 'freereps.rules.archived', data={'reason': '事件已有绑定，旧规则保留在归档中'})
    elif active:
        plugin.runtime.store.log('warning', plugin.id, 'freereps.rules.archived', data={'reason': '旧规则含多个动作、延迟或非唤醒模式，已归档，需在事件与脚本中配置'})
    monitor.pop('pending', None)
    monitor.pop('history', None)
    plugin.state.set('monitor', monitor)
    plugin.state.set('rules', {})
    if 'max_age_hours' in plugin.config:
        plugin.config.pop('max_age_hours')
        plugin.config.save()
    plugin.state.set('events_migrated_v2', True)
