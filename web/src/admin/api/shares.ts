/** 管理端：全局分享列表。 */

import { adminHttp } from './client.ts'
import type { components } from '#src/types/api.ts'

export type AdminShare = components['schemas']['AdminShareResponse']
export type AdminShareList = components['schemas']['AdminShareList']
export type AdminShareStatus = components['schemas']['ShareStatus']

export interface AdminShareQuery {
  page?: number
  size?: number
  status?: AdminShareStatus
  username?: string
}

export const adminSharesApi = {
  list: async (params: AdminShareQuery = {}): Promise<AdminShareList> => {
    const { data } = await adminHttp.get<AdminShareList>('/admin/shares', {
      params,
    })
    return data
  },
}
