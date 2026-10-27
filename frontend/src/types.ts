export interface Configuration {
  enabled: boolean
  providers: Provider[]
  models: ModelEntry[]
  main_model_id: string
  lightweight_model_id: string
  main_persona_id: string
  max_steps: number
  compression_enabled: boolean
  compression_threshold: number
  conversation: { mode: 'broadcast' | 'intelligent'; targets: string[]; tool_events: boolean }
  message_processing: { image_model_id: string; speech_recognition: string }
  context_chars: number
  plugins: string[]
  agent_concurrency: number
  agent_settings: Record<string, { persona_id: string; model_id: string }>
  main_session: { type: string }
}
export interface Provider {
  id: string
  name: string
  api_base: string
  api_key_configured: boolean
  enabled: boolean
}
export interface Capabilities {
  text: boolean
  image: boolean
  audio: boolean
  tools: boolean
}
export interface ModelMetadata {
  context_window: number
  capabilities: Partial<Capabilities>
  source: string
  fetched_at: number
}
export interface ModelEntry {
  id: string
  name: string
  provider_id: string
  model_id: string
  enabled: boolean
  capabilities: Capabilities
  extra_body: Record<string, unknown>
  context_window: number
  effective_context_window: number
  metadata: ModelMetadata
}
export interface AvailableModel {
  model_id: string
  name: string
  capabilities: Capabilities
  metadata: ModelMetadata
}
export interface ToolInfo {
  plugin_id: string
  name: string
  description: string
}
export interface Status {
  agents_revision: string
  registry_revision: string
  version: string
  enabled: boolean
  configured: boolean
  main_session: string
  error: string
  running: null | { id: string; event_id: number; started: number }
  queue: { status: string; count: number }[]
  plugins: { name: string }[]
  tools: ToolInfo[]
}
export interface Setup {
  steps: {
    key: string
    title: string
    icon: string
    path: string
    completed: boolean
    optional: boolean
    plugin_id: string
  }[]
  completed: Record<string, boolean>
  optional: string[]
  plugins: { name: string; label: string; required: boolean; selected: boolean; loaded: boolean }[]
}
export interface EventRecord {
  id: number | string
  uid: string
  run_id?: string
  at: number
  kind: string
  source: string
  actor: string
  label: string
  target: string
  text: string
  meta: string
  status: string
  priority: number
  expires: number
  error: string
}
export interface Memory {
  key: string
  text: string
  source: string
  updated: number
}
export interface Person {
  id: string
  data: { id: string; nickname: string; aliases: string[]; groups: Record<string, string> }
  updated: number
}
export interface Task {
  id: string
  status: string
  updated: number
  data: {
    run_id?: string
    goal: string
    progress?: string
    progress_at?: number
    tool_rounds?: number
    context?: string
    result?: string
    created: number
    finished?: number
  }
}
export interface Schedule {
  id: string
  next_at: number
  data: {
    name: string
    content: string
    mode: string
    at?: string
    interval_seconds?: number
    target: string
    target_id?: string
    enabled: boolean
    include_context: boolean
  }
}
export interface Run {
  id: string
  event_id: number | null
  started: number
  finished: number | null
  status: string
  error: string
  trace?: string
}
export interface Delivery {
  id: string
  target: string
  text: string
  action: string
  params: string
  status: string
  result: string
  error: string
  at: number
}

export interface PluginInfo {
  has_settings?: boolean
  configured?: boolean
  builtin: boolean
  name: string
  label: string
  required: boolean
  selected: boolean
  loaded: boolean
  state: 'enabled' | 'disabled' | 'unavailable' | 'pending_configuration'
  available: boolean
  reason: string
  icon: string
}
export interface PluginPage {
  plugin_id: string
  id: string
  title: string
  group: string
  icon: string
  order: number
  group_order: number
  route: string
  url: string
  aliases: string[]
}
export interface PluginRegistry {
  revision: string
  pages: PluginPage[]
  plugins: PluginInfo[]
}
export interface Persona {
  id: string
  name: string
  prompt: string
  visible_plugins: string[] | null
  created: number
  updated: number
}
export interface FunctionInfo extends ToolInfo {
  source_label?: string
  parameters: Record<string, unknown>
  available: boolean
}
export interface LogRecord {
  id: number
  at: number
  level: string
  source: string
  event: string
  run_id: string
  tool_call_id: number | null
  data: string
}
export interface ToolCall {
  id: number
  run_id: string
  call_id: string
  tool_name: string
  plugin_id: string
  origin: string
  arguments: string
  output: string
  status: string
  started: number
  finished: number | null
  error: string
}

export interface AgentInfo {
  id: string
  local_id: string
  plugin_id: string
  name: string
  description: string
  persona_id: string
  model_id: string
  persona_mode: 'default' | 'library' | 'managed'
  plugin_persona_id: string
  plugin_model_id: string
  effective_persona_id: string
  effective_model_id: string
  persona_source: string
  model_source: string
  persona_name: string
  model_name: string
  busy: boolean
  resetting: boolean
  ready: boolean
  enabled: boolean
}
export interface AgentCatalog {
  revision: string
  defaults: {
    persona_id: string
    model_id: string
  }
  items: AgentInfo[]
}
