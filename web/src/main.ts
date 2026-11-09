/**
 * 应用入口：按路径分发用户端与管理端。
 *
 * 两个入口都通过动态 import 拆包，普通用户访问 `/` 不会加载管理端代码，
 * 管理端也不依赖 vue-router；Nginx 现有 SPA fallback 已支持 `/admin`。
 */

import { isAdminPath } from '@/admin/path'

const admin = isAdminPath(window.location.pathname)
void (admin ? import('@/admin/main') : import('@/bootstrap'))
