<script setup lang="ts">
import { computed } from 'vue'
import {
  LayoutDashboard,
  Radio,
  ListTodo,
  Cpu,
  Cable,
  Bot,
  Blocks,
  Brain,
  UsersRound,
  Clock3,
  Activity,
  Send,
  SlidersHorizontal,
  ChevronRight,
  ChevronLeft,
  ArrowUpRight,
  ArrowRight,
  Check,
  Plus,
  RefreshCw,
  Search,
  X,
  Power,
  Pause,
  LogOut,
  Menu,
  Inbox,
  CheckCircle2,
  Circle,
  Pencil,
  Trash2,
  Copy,
  LoaderCircle,
  Eye,
  EyeOff,
  KeyRound,
  Bell,
  ShieldCheck,
  Ellipsis,
  Folder,
  FileText,
  Upload,
  Download,
  MessagesSquare,
} from '@lucide/vue'
const props = withDefaults(defineProps<{ name: string; size?: number; strokeWidth?: number }>(), {
  size: 19,
  strokeWidth: 1.7,
})
const icons = {
  chat: MessagesSquare,
  folder: Folder,
  file: FileText,
  upload: Upload,
  download: Download,
  dashboard: LayoutDashboard,
  events: Radio,
  tasks: ListTodo,
  model: Cpu,
  connection: Cable,
  persona: Bot,
  plugins: Blocks,
  memory: Brain,
  people: UsersRound,
  clock: Clock3,
  activity: Activity,
  send: Send,
  settings: SlidersHorizontal,
  right: ChevronRight,
  left: ChevronLeft,
  external: ArrowUpRight,
  arrow: ArrowRight,
  check: Check,
  plus: Plus,
  refresh: RefreshCw,
  search: Search,
  close: X,
  power: Power,
  pause: Pause,
  logout: LogOut,
  menu: Menu,
  empty: Inbox,
  complete: CheckCircle2,
  circle: Circle,
  edit: Pencil,
  trash: Trash2,
  copy: Copy,
  loading: LoaderCircle,
  eye: Eye,
  hidden: EyeOff,
  key: KeyRound,
  bell: Bell,
  shield: ShieldCheck,
  more: Ellipsis,
}
const icon = computed(() => icons[props.name as keyof typeof icons] || Circle)
</script>
<template><component :is="icon" :size="size" :stroke-width="strokeWidth" aria-hidden="true" /></template>

<style>
.spinning {
  animation: spin 1s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
