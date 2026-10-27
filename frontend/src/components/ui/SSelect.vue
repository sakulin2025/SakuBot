<script lang="ts">
import {
  defineComponent,
  h,
  isVNode,
  nextTick,
  onBeforeUnmount,
  onMounted,
  onUpdated,
  ref,
  useId,
  watch,
} from 'vue'
import type { CSSProperties, PropType, VNode } from 'vue'
import UiIcon from '../UiIcon.vue'

interface SelectOption {
  value: string | number
  label: string
  disabled?: boolean
  group?: string
  selected?: boolean
}
function labelText(value: unknown): string {
  if (typeof value === 'string' || typeof value === 'number') return String(value)
  if (Array.isArray(value)) return value.map(labelText).join('')
  return isVNode(value) ? labelText(value.children) : ''
}
function slotOptions(nodes: VNode[], group = '', disabled = false): SelectOption[] {
  return nodes.flatMap((node) => {
    if (node.type === 'option') {
      const label = labelText(node.children).trim()
      return [
        {
          value: node.props?.value ?? label,
          label,
          group,
          disabled: disabled || node.props?.disabled === '' || !!node.props?.disabled,
          selected: node.props?.selected === '' || !!node.props?.selected,
        },
      ]
    }
    if (Array.isArray(node.children))
      return slotOptions(
        node.children.filter(isVNode),
        node.type === 'optgroup' ? String(node.props?.label || '') : group,
        disabled || (node.type === 'optgroup' && (node.props?.disabled === '' || !!node.props?.disabled)),
      )
    return []
  })
}
export default defineComponent({
  name: 'SSelect',
  inheritAttrs: false,
  props: {
    modelValue: { type: [String, Number] as PropType<string | number | null>, default: undefined },
    options: Array as PropType<SelectOption[]>,
    disabled: Boolean,
    filterable: Boolean,
    placeholder: { type: String, default: '请选择' },
  },
  emits: { 'update:modelValue': (_value: string) => true, change: (_event: Event) => true },
  setup(props, { attrs, slots, emit, expose }) {
    const uid = useId()
    const root = ref<HTMLElement>(),
      trigger = ref<HTMLButtonElement>(),
      panel = ref<HTMLElement>(),
      native = ref<HTMLSelectElement>()
    const open = ref(false),
      invalid = ref(false),
      query = ref(''),
      highlighted = ref(-1)
    const internalValue = ref<string>()
    const position = ref<CSSProperties>({})
    let items: SelectOption[] = []
    let closing: ReturnType<typeof setTimeout> | undefined
    let observer: ResizeObserver | undefined
    let frame = 0,
      typeBuffer = '',
      typedAt = 0
    const isDisabled = () => props.disabled || !!trigger.value?.matches(':disabled')
    const value = () =>
      String(
        props.modelValue !== undefined
          ? (props.modelValue ?? '')
          : attrs.value !== undefined
            ? (attrs.value ?? '')
            : (internalValue.value ?? items.find((item) => item.selected)?.value ?? items[0]?.value ?? ''),
      )
    const visible = () =>
      items.filter(
        (item) => !query.value || item.label.toLocaleLowerCase().includes(query.value.toLocaleLowerCase()),
      )
    function align() {
      if (!open.value || !trigger.value || !panel.value) return
      const rect = trigger.value.getBoundingClientRect()
      const below = window.innerHeight - rect.bottom - 12,
        above = rect.top - 12
      const up = below < 200 && above > below
      const maxHeight = Math.max(70, Math.min(320, up ? above : below))
      const width = Math.min(Math.max(rect.width, 160), window.innerWidth - 20)
      const height = Math.min(panel.value.scrollHeight, maxHeight)
      const next: CSSProperties = {
        width: width + 'px',
        maxHeight: maxHeight + 'px',
        left: Math.max(10, Math.min(rect.left, window.innerWidth - width - 10)) + 'px',
        top: (up ? Math.max(8, rect.top - height - 6) : rect.bottom + 6) + 'px',
        transformOrigin: up ? 'bottom center' : 'top center',
      }
      if (JSON.stringify(position.value) !== JSON.stringify(next)) position.value = next
    }
    function scrollActive() {
      nextTick(() =>
        panel.value?.querySelector<HTMLElement>('[data-active="true"]')?.scrollIntoView({ block: 'nearest' }),
      )
    }
    async function show() {
      if (isDisabled() || open.value) return
      clearTimeout(closing)
      query.value = ''
      const selected = items.findIndex((item) => String(item.value) === value() && !item.disabled)
      highlighted.value = selected >= 0 ? selected : items.findIndex((item) => !item.disabled)
      open.value = true
      await nextTick()
      panel.value?.classList.remove('is-closing')
      if (panel.value && !panel.value.matches(':popover-open')) panel.value.showPopover?.()
      align()
      scrollActive()
    }
    function close() {
      if (!open.value) return
      open.value = false
      panel.value?.classList.add('is-closing')
      clearTimeout(closing)
      closing = setTimeout(() => {
        panel.value?.hidePopover?.()
        panel.value?.classList.remove('is-closing')
      }, 130)
    }
    function choose(item: SelectOption) {
      if (item.disabled || isDisabled()) return
      const before = value(),
        next = String(item.value)
      internalValue.value = next
      invalid.value = false
      if (native.value) {
        native.value.value = next
        if (next !== before) native.value.dispatchEvent(new Event('change', { bubbles: true }))
      }
      close()
      trigger.value?.focus()
    }
    function change(event: Event) {
      emit('update:modelValue', (event.target as HTMLSelectElement).value)
      emit('change', event)
    }
    function move(direction: number) {
      const choices = visible()
      for (let offset = 1; offset <= choices.length; offset++) {
        const index = (highlighted.value + direction * offset + choices.length) % choices.length
        if (!choices[index]?.disabled) {
          highlighted.value = index
          scrollActive()
          return
        }
      }
    }
    function keyboard(event: KeyboardEvent) {
      if (isDisabled()) return
      if (event.key === 'Escape' && open.value) {
        event.preventDefault()
        event.stopPropagation()
        close()
        trigger.value?.focus()
        return
      }
      if (event.key === 'Tab') {
        close()
        return
      }
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault()
        if (!open.value) void show()
        else move(event.key === 'ArrowDown' ? 1 : -1)
        return
      }
      if (event.key === 'Enter' || (event.key === ' ' && event.target === trigger.value)) {
        event.preventDefault()
        if (!open.value) void show()
        else {
          const item = visible()[highlighted.value]
          if (item) choose(item)
        }
        return
      }
      if ((event.key === 'Home' || event.key === 'End') && open.value && event.target === trigger.value) {
        event.preventDefault()
        const choices = visible()
        let last = choices.length - 1
        while (last >= 0 && choices[last]?.disabled) last--
        highlighted.value = event.key === 'Home' ? choices.findIndex((item) => !item.disabled) : last
        scrollActive()
        return
      }
      if (
        event.target === trigger.value &&
        event.key.length === 1 &&
        !event.ctrlKey &&
        !event.metaKey &&
        !event.altKey
      ) {
        event.preventDefault()
        if (Date.now() - typedAt > 700) typeBuffer = ''
        typedAt = Date.now()
        typeBuffer += event.key.toLocaleLowerCase()
        const index = visible().findIndex(
          (item) => !item.disabled && item.label.toLocaleLowerCase().startsWith(typeBuffer),
        )
        if (index >= 0) {
          if (!open.value) void show()
          highlighted.value = index
          scrollActive()
        }
      }
    }
    function outside(event: Event) {
      if (root.value && !root.value.contains(event.target as Node)) close()
    }
    function scroll(event: Event) {
      if (!panel.value?.contains(event.target as Node)) align()
    }
    function sync() {
      if (native.value && native.value.value !== value()) native.value.value = value()
      if (open.value) {
        cancelAnimationFrame(frame)
        frame = requestAnimationFrame(align)
      }
    }
    watch(
      () => props.disabled,
      (disabled) => {
        if (disabled) close()
      },
    )
    onMounted(() => {
      sync()
      observer = new ResizeObserver(align)
      if (trigger.value) observer.observe(trigger.value)
      document.addEventListener('pointerdown', outside, true)
      document.addEventListener('scroll', scroll, true)
      window.addEventListener('resize', align)
      window.addEventListener('blur', close)
    })
    onUpdated(sync)
    onBeforeUnmount(() => {
      clearTimeout(closing)
      cancelAnimationFrame(frame)
      observer?.disconnect()
      panel.value?.hidePopover?.()
      document.removeEventListener('pointerdown', outside, true)
      document.removeEventListener('scroll', scroll, true)
      window.removeEventListener('resize', align)
      window.removeEventListener('blur', close)
    })
    expose({ focus: () => trigger.value?.focus(), element: native, open: show, close })
    return () => {
      items = props.options ?? slotOptions(slots.default?.() ?? [])
      const selected = items.find((item) => String(item.value) === value())
      const choices = visible(),
        searchable = props.filterable || items.length > 8
      const triggerAttrs = { ...attrs }
      for (const key of ['class', 'style', 'value', 'name', 'required', 'form']) delete triggerAttrs[key]
      return h(
        'span',
        {
          ref: root,
          class: [
            's-select',
            attrs.class,
            { 'is-open': open.value, 'is-disabled': props.disabled, 'is-invalid': invalid.value },
          ],
          style: attrs.style as CSSProperties,
          onFocusout: (event: FocusEvent) => {
            if (!root.value?.contains(event.relatedTarget as Node)) close()
          },
        },
        [
          h(
            'button',
            {
              ...triggerAttrs,
              ref: trigger,
              type: 'button',
              class: 's-select-trigger',
              disabled: props.disabled,
              role: 'combobox',
              'aria-haspopup': 'listbox',
              'aria-expanded': open.value,
              'aria-controls': uid + '-list',
              'aria-required': attrs.required !== undefined && attrs.required !== false ? true : undefined,
              'aria-invalid': invalid.value || undefined,
              'aria-activedescendant':
                open.value && highlighted.value >= 0 ? uid + '-option-' + highlighted.value : undefined,
              onClick: () => (open.value ? close() : void show()),
              onKeydown: keyboard,
            },
            [
              h(
                'span',
                { class: ['s-select-label', { 'is-placeholder': !selected }] },
                selected?.label || props.placeholder,
              ),
              h(UiIcon, { name: 'right', size: 14, class: 's-select-chevron' }),
            ],
          ),
          h(
            'select',
            {
              ref: native,
              class: 's-select-native',
              tabindex: -1,
              'aria-hidden': 'true',
              name: attrs.name,
              form: attrs.form,
              required: attrs.required !== undefined && attrs.required !== false,
              disabled: props.disabled,
              onChange: change,
              onFocus: () => trigger.value?.focus(),
              onInvalid: (event: Event) => {
                event.preventDefault()
                invalid.value = true
                trigger.value?.focus()
              },
            },
            items.map((item) => h('option', { value: item.value, disabled: item.disabled }, item.label)),
          ),
          h(
            'div',
            {
              ref: panel,
              popover: 'manual',
              class: ['s-select-popup', { 'is-visible': open.value }],
              style: position.value,
              onKeydown: keyboard,
            },
            [
              searchable
                ? h('div', { class: 's-select-search' }, [
                    h(UiIcon, { name: 'search', size: 15 }),
                    h('input', {
                      value: query.value,
                      placeholder: '搜索',
                      'aria-label': '搜索选项',
                      onInput: (event: Event) => {
                        query.value = (event.target as HTMLInputElement).value
                        highlighted.value = visible().findIndex((item) => !item.disabled)
                      },
                    }),
                  ])
                : null,
              h(
                'div',
                {
                  id: uid + '-list',
                  role: 'listbox',
                  class: 's-select-options',
                  'aria-label': attrs['aria-label'] || '选项',
                },
                choices.length
                  ? choices.flatMap((item, index) => [
                      item.group && (index === 0 || choices[index - 1]?.group !== item.group)
                        ? h('div', { class: 's-select-group' }, item.group)
                        : null,
                      h(
                        'div',
                        {
                          id: uid + '-option-' + index,
                          key: String(item.value) + ':' + index,
                          role: 'option',
                          'aria-selected': String(item.value) === value(),
                          'aria-disabled': !!item.disabled,
                          class: [
                            's-select-option',
                            {
                              'is-selected': String(item.value) === value(),
                              'is-active': highlighted.value === index,
                              'is-disabled': item.disabled,
                            },
                          ],
                          'data-active': highlighted.value === index,
                          onPointermove: () => {
                            if (!item.disabled) highlighted.value = index
                          },
                          onMousedown: (event: MouseEvent) => event.preventDefault(),
                          onClick: () => choose(item),
                        },
                        [
                          h('span', item.label),
                          String(item.value) === value() ? h(UiIcon, { name: 'check', size: 15 }) : null,
                        ],
                      ),
                    ])
                  : [h('div', { class: 's-select-empty' }, '暂无选项')],
              ),
            ],
          ),
        ],
      )
    }
  },
})
</script>

<style>
.s-select {
  transition:
    background var(--s-motion),
    border-color var(--s-motion),
    box-shadow var(--s-motion);
}
.s-select:focus {
  outline: 0;
  border-color: var(--accent);
  box-shadow: var(--s-ring);
  background: #fff;
}
.s-select:disabled {
  background: #f5f5f9;
  color: var(--muted);
  cursor: not-allowed;
}
.s-select {
  cursor: pointer;
}
.s-select {
  position: relative;
  display: inline-flex;
  min-width: 100px;
  max-width: 100%;
  vertical-align: middle;
  outline: 0;
}
.s-select.filter-select {
  padding: 0;
  border: 0;
  min-height: 0;
  background: transparent;
  box-shadow: none;
}
.s-select-trigger {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  width: 100%;
  min-width: 0;
  min-height: 38px;
  padding: 9px 12px;
  border: 1px solid #e0ddeb;
  border-radius: 8px;
  background: #fff;
  color: var(--ink);
  font-size: 12px;
  font-weight: 400;
  text-align: left;
  line-height: 1.5;
  cursor: pointer;
  transition:
    border-color var(--s-motion),
    box-shadow var(--s-motion),
    background var(--s-motion);
}
.s-select-trigger:hover:not(:disabled) {
  border-color: #bcb3df;
}
.s-select-trigger:focus-visible,
.s-select.is-open .s-select-trigger {
  outline: 0;
  border-color: var(--accent);
  box-shadow: var(--s-ring);
}
.s-select-trigger:disabled {
  background: #f5f4f9;
  color: var(--muted);
  cursor: not-allowed;
  opacity: 0.65;
}
.s-select.is-invalid .s-select-trigger {
  border-color: var(--negative);
}
.s-select-label {
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  flex: 1;
}
.s-select-label.is-placeholder {
  color: var(--muted);
}
.s-select-chevron {
  flex-shrink: 0;
  color: #aaa3bd;
  transform: rotate(90deg);
  transition:
    transform var(--s-motion),
    color var(--s-motion);
}
.s-select.is-open .s-select-chevron {
  transform: rotate(-90deg);
  color: var(--accent);
}
.s-select-native {
  position: absolute !important;
  left: 0 !important;
  bottom: 0 !important;
  width: 1px !important;
  height: 1px !important;
  min-width: 1px !important;
  max-width: 1px !important;
  min-height: 1px !important;
  padding: 0 !important;
  margin: 0 !important;
  opacity: 0 !important;
  clip-path: inset(50%) !important;
  pointer-events: none !important;
  border: 0 !important;
}
.s-select-popup {
  position: fixed;
  inset: auto;
  margin: 0;
  padding: 5px;
  box-sizing: border-box;
  max-width: calc(100vw - 20px);
  max-height: 320px;
  overflow: hidden;
  border: 1px solid #e8e3f4;
  border-radius: 11px;
  background: #fff;
  color: var(--ink);
  box-shadow:
    0 12px 40px #30215d1a,
    0 2px 7px #30215d08;
  font: 12px/1.5 var(--font);
  z-index: 2000;
}
.s-select-popup:popover-open,
.s-select-popup.is-visible {
  display: flex;
  flex-direction: column;
  animation: s-select-in 0.15s cubic-bezier(0.2, 0.9, 0.2, 1);
}
.s-select-popup:not(.is-visible):not(:popover-open) {
  display: none;
}
.s-select-popup.is-closing {
  animation: s-select-out 0.13s ease forwards;
  pointer-events: none;
}
.s-select-options {
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
  scrollbar-width: thin;
  scrollbar-color: #d7d0e9 transparent;
}
.s-select-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  min-height: 34px;
  padding: 7px 10px;
  margin: 2px 0;
  border-radius: 6px;
  cursor: pointer;
  transition:
    background 0.1s ease,
    color 0.1s ease;
}
.s-select-option > span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.s-select-option svg {
  flex-shrink: 0;
}
.s-select-option.is-active {
  background: #f4f1fb;
}
.s-select-option.is-selected {
  background: #f0ecfc;
  color: var(--accent);
  font-weight: 550;
}
.s-select-option.is-disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.s-select-option.is-disabled.is-active {
  background: transparent;
}
.s-select-search {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 3px 4px 6px;
  padding: 6px 8px;
  border: 1px solid var(--border);
  border-radius: 7px;
  color: var(--muted);
  flex-shrink: 0;
}
.s-select-search:focus-within {
  border-color: #b9adee;
}
.s-select-search input {
  width: 100%;
  min-width: 0;
  height: 22px;
  min-height: 0;
  padding: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
  font: inherit;
  box-shadow: none;
  color: var(--ink);
  outline: 0;
}
.s-select-search input:focus-visible {
  outline: 0;
  box-shadow: none;
}
.s-select-empty {
  padding: 18px;
  text-align: center;
  color: var(--muted);
}
.s-select-group {
  padding: 8px 10px 3px;
  font-size: 10px;
  color: var(--muted);
}
.field > .s-select {
  width: 100%;
}
.compact-field > .s-select {
  min-width: 100px;
  max-width: 280px;
}
@keyframes s-select-in {
  from {
    opacity: 0;
    transform: translateY(-3px) scale(0.98);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}
@keyframes s-select-out {
  to {
    opacity: 0;
    transform: scale(0.98);
  }
}

.filter-select {
  width: 100%;
  background: #fff;
  border: 1px solid #e0e5ee;
  border-radius: 7px;
  padding: 10px 12px;
  color: #535d71;
  min-height: 39px;
  font-size: 12px;
  box-shadow: 0 1px 2px #1c295103;
  transition:
    border-color 0.15s,
    box-shadow 0.15s;
}
.filter-select {
  width: auto;
  min-height: 36px;
  height: 36px;
  font-size: 10px;
  color: #969eae;
  margin-left: auto;
}
@media (max-width: 700px) {
  .filter-select {
    font-size: 9px;
    padding-left: 8px;
    padding-right: 6px;
    max-width: 105px;
  }
}
</style>
