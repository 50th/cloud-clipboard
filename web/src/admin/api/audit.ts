/** 管理端操作审计接口。 */

import { adminHttp } from './client.ts'
import type { AdminAuditLogList } from './client.ts'

export interface AdminAuditQuery {
  page?: number
  size?: number
  admin_username?: string
  action?: string
  target_id?: string
  start?: string
  end?: string
}

export const adminAuditApi = {
  list: async (params: AdminAuditQuery = {}): Promise<AdminAuditLogList> => {
    const { data } = await adminHttp.get<AdminAuditLogList>(
      '/admin/audit-logs',
      { params },
    )
    return data
  },
}
