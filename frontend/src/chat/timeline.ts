export interface TimelineMessage {
  id: number
  uid: string
  at: number
  meta: Record<string, unknown>
}
export interface TimelineEntry {
  key: string
  kind: 'model' | 'tool' | 'compression'
  at: number
  name?: string
}
export interface TimelineRun<E extends TimelineEntry> {
  id: string
  event_id: number
  entries: E[]
}
export type TimelineItem<M, E> =
  | { kind: 'message'; key: string; message: M }
  | { kind: 'tools'; key: string; runId: string; entries: E[] }
  | { kind: 'compression'; key: string; runId: string; entry: E }

// Messages are boundaries, even when several belong to the same wake/run.
// Use persisted absorption time so reloads retain safe-point insertion order.
export function buildTimeline<M extends TimelineMessage, E extends TimelineEntry>(
  messages: M[], runs: TimelineRun<E>[],
): TimelineItem<M, E>[] {
  type Row = { at: number; order: number; item: TimelineItem<M, E> }
  const rows: Row[] = messages.map(message => ({
    at: typeof message.meta.absorbed_at === 'number' ? message.meta.absorbed_at : message.at,
    order: 0,
    item: { kind: 'message', key: 'message:' + message.uid, message },
  }))
  const anchors = new Map(messages.map(message => [message.id, message.at]))
  for (const run of runs) {
    const anchor = anchors.get(run.event_id)
    if (anchor === undefined) continue
    for (const entry of run.entries) {
      if (entry.kind === 'model' || (entry.kind === 'tool' && entry.name?.split('.').at(-1) === 'message_send')) continue
      const key = run.id + ':' + entry.key
      rows.push({ at: Math.max(anchor, entry.at), order: 1, item: entry.kind === 'tool'
        ? { kind: 'tools', key, runId: run.id, entries: [entry] }
        : { kind: 'compression', key, runId: run.id, entry } })
    }
  }
  rows.sort((a, b) => a.at - b.at || a.order - b.order)
  const result: TimelineItem<M, E>[] = []
  for (const { item } of rows) {
    const previous = result.at(-1)
    if (item.kind === 'tools' && previous?.kind === 'tools' && previous.runId === item.runId) previous.entries.push(...item.entries)
    else result.push(item)
  }
  return result
}
