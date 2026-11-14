/** 管理端分享访问记录接口（成功 + 失败）。 */

import { adminHttp } from './client.ts'
import type { components } from '#src/types/api.ts'

export type AdminShareAccessLog =
  components['schemas']['AdminShareAccessLogResponse']
export type AdminShareAccessLogList =
  components['schemas']['AdminShareAccessLogList']
export type AdminShareAccessResult = 'all' | 'success' | 'failure'

export interface AdminShareAccessLogQuery {
  page?: number
  size?: number
  result?: AdminShareAccessResult
  share_id?: string
  username?: string
  start?: string
  end?: string
}

export const adminShareAccessLogsApi = {
  list: async (
    params: AdminShareAccessLogQuery = {},
  ): Promise<AdminShareAccessLogList> => {
    const { data } = await adminHttp.get<AdminShareAccessLogList>(
      '/admin/share-access-logs',
      { params },
    )
    return data
  },
}
