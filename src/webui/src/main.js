import { createApp, watch } from 'vue'
import { createPinia } from 'pinia'
import Antd from 'ant-design-vue'
import App from './App.vue'
import router from './router'
import log from '@/log/log'

import 'ant-design-vue/dist/reset.css'
import localStorageAndPythonStorage from '@/stores/local-storage-and-python-storage'

const app = createApp(App)

const pinia = createPinia()

watch(
  pinia.state,
  async (state) => {
    // persist the whole state to the local storage whenever it changes
      if (state) {
          return localStorageAndPythonStorage.setItem('piniaState', JSON.stringify(state))
      }
  },
  { deep: true }
)

app.use(pinia)
app.use(router)
app.use(Antd)

localStorageAndPythonStorage.getItem('piniaState').then((state) => {
    if(state) {
        try {
            pinia.state.value = JSON.parse(state)
        } catch (e) {
            log.error(e)
        }
    }

    window.appVM = app.mount('#app')
})
