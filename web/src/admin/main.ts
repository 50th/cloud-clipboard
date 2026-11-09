/** 管理端启动入口（由 `main.ts` 在 `/admin` 路径下动态加载）。 */

import { createPinia } from 'pinia'
import { createApp } from 'vue'

import AdminApp from '@/admin/AdminApp.vue'
import { setAdminUnauthorizedHandler } from '@/admin/api/client'
import { useAdminStore } from '@/admin/stores/adminStore'
import '@/styles.css'
import '@/admin/admin.css'

const pinia = createPinia()
const app = createApp(AdminApp).use(pinia)

// 401 时只清理管理端登录态，不影响用户端。
setAdminUnauthorizedHandler(() => {
  useAdminStore(pinia).logout()
})

document.title = '后台管理 · 云剪贴板'
app.mount('#app')
