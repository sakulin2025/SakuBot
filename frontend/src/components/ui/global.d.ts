export {}
declare module 'vue' {
  export interface GlobalComponents {
    SButton: (typeof import('./SButton.vue'))['default']
    SInput: (typeof import('./SInput.vue'))['default']
    SCheckbox: (typeof import('./SCheckbox.vue'))['default']
    SSelect: (typeof import('./SSelect.vue'))['default']
    STextarea: (typeof import('./STextarea.vue'))['default']
    SSwitch: (typeof import('./SSwitch.vue'))['default']
    SCard: (typeof import('./SCard.vue'))['default']
    SForm: (typeof import('./SForm.vue'))['default']
    SFormItem: (typeof import('./SFormItem.vue'))['default']
    SPageHeader: (typeof import('./SPageHeader.vue'))['default']
    STabs: (typeof import('./STabs.vue'))['default']
    STable: (typeof import('./STable.vue'))['default']
    SSpinner: (typeof import('./SSpinner.vue'))['default']
    SDialog: (typeof import('../UiModal.vue'))['default']
    STag: (typeof import('../UiBadge.vue'))['default']
    SEmpty: (typeof import('../UiEmpty.vue'))['default']
  }
}
