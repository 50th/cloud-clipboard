/**
 * 应用入口：按路径分发用户端与管理端。
 *
 * 两个入口都通过动态 import 拆包，普通用户访问 `/` 不会加载管理端代码，
 * 管理端也不依赖 vue-router；Nginx 现有 SPA fallback 已支持 `/admin`。
 */

import { isAdminPath } from '@/admin/path'

// 两个 import() 必须分开写：写在同一个三元表达式里时，Vite 只会为整条语句
// 绑定一份依赖表，导致管理端 CSS 不被预加载。
if (isAdminPath(window.location.pathname)) {
  void import('@/admin/main')
} else {
  void import('@/bootstrap')
}
