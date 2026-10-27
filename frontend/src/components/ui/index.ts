import type { App } from 'vue'
import SButton from './SButton.vue'
import SInput from './SInput.vue'
import SCheckbox from './SCheckbox.vue'
import SSelect from './SSelect.vue'
import STextarea from './STextarea.vue'
import SSwitch from './SSwitch.vue'
import SCard from './SCard.vue'
import SForm from './SForm.vue'
import SFormItem from './SFormItem.vue'
import SPageHeader from './SPageHeader.vue'
import STabs from './STabs.vue'
import STable from './STable.vue'
import SSpinner from './SSpinner.vue'
import SDialog from '../UiModal.vue'
import STag from '../UiBadge.vue'
import SEmpty from '../UiEmpty.vue'
export {
  SButton,
  SInput,
  SCheckbox,
  SSelect,
  STextarea,
  SSwitch,
  SCard,
  SForm,
  SFormItem,
  SPageHeader,
  STabs,
  STable,
  SSpinner,
  SDialog,
  STag,
  SEmpty,
}
export default {
  install(app: App) {
    for (const [name, component] of Object.entries({
      SButton,
      SInput,
      SCheckbox,
      SSelect,
      STextarea,
      SSwitch,
      SCard,
      SForm,
      SFormItem,
      SPageHeader,
      STabs,
      STable,
      SSpinner,
      SDialog,
      STag,
      SEmpty,
    }))
      app.component(name, component)
  },
}
