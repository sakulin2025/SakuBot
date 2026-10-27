import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { router } from './router'
import App from './App.vue'
import './style.css'
import SakuUI from './components/ui'

createApp(App).use(createPinia()).use(router).use(SakuUI).mount('#app')
