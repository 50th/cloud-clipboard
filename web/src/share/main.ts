/**
 * 分享公开页启动入口（由 `main.ts` 在 `/s` 路径下动态加载）。
 *
 * 公开页**不引入 Pinia、用户 store 或主应用 App.vue**：
 * 访问者可能没有登录态，页面也不应读取本地登录信息。
 */

import { createApp } from 'vue'

import ShareView from '@/share/ShareView.vue'
import '@/styles.css'

// 运行时兜底：真正的防护由 Nginx server 级响应头提供（见 docs/share.md）。
function applyPrivacyMeta(): void {
  const ensureMeta = (name: string, content: string) => {
    let element = document.querySelector<HTMLMetaElement>(`meta[name="${name}"]`)
    if (!element) {
      element = document.createElement('meta')
      element.name = name
      document.head.appendChild(element)
    }
    element.content = content
  }
  ensureMeta('robots', 'noindex, nofollow')
  ensureMeta('referrer', 'no-referrer')
}

applyPrivacyMeta()
document.title = '分享 · 云剪贴板'

createApp(ShareView).mount('#app')
