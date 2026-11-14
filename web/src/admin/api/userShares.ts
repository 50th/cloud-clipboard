/** 管理端：指定用户的分享记录。 */

import { adminHttp } from './client.ts'
import type { components } from '#src/types/api.ts'

export type AdminUserShare = components['schemas']['AdminUserShareResponse']
export type AdminUserShareList = components['schemas']['AdminUserShareList']
export type AdminUserShareStatus = components['schemas']['ShareStatus']

export interface AdminUserShareQuery {
  page?: number
  size?: number
  status?: AdminUserShareStatus
}

export const adminUserSharesApi = {
  list: async (
    userId: string,
    params: AdminUserShareQuery = {},
  ): Promise<AdminUserShareList> => {
    const { data } = await adminHttp.get<AdminUserShareList>(
      `/admin/users/${userId}/shares`,
      { params },
    )
    return data
  },
}
