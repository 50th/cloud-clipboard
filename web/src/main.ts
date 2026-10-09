import { createPinia } from 'pinia'
import { createApp } from 'vue'

import App from '@/App.vue'
import { setUnauthorizedHandler } from '@/api/client'
import { useUserStore } from '@/stores/userStore'
import '@/styles.css'

const pinia = createPinia()
const app = createApp(App).use(pinia)

// 令牌过期/被吊销时后端返回 401：清空登录态回到登录页。
// 在这里注册而不是写进 api/client.ts，是为了避免 store 与 axios 客户端循环依赖。
setUnauthorizedHandler(() => {
  useUserStore(pinia).logout()
})

app.mount('#app')
