import { createRouter, createWebHashHistory } from 'vue-router'
import Dashboard from '@/components/dashboard.vue'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    {
      path: '/',
      name: 'dashboard',
      component: Dashboard
    }
  ]
})

export default router
