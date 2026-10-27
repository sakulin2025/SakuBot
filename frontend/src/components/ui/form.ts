import type { InjectionKey } from 'vue'
export interface FormRule {
  required?: boolean
  min?: number
  validate?: (value: unknown) => boolean
  message: string
}
export const formKey: InjectionKey<{ errors: Record<string, string>; disabled: () => boolean }> =
  Symbol('saku-form')
