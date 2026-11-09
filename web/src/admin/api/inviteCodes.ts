/** 管理端邀请码接口。 */

import { adminHttp } from './client.ts'
import type { components } from '#src/types/api.ts'

export type AdminInviteCode = components['schemas']['AdminInviteCodeResponse']
export type AdminInviteCodeCreated =
  components['schemas']['AdminInviteCodeCreated']
export type AdminInviteCodeList = components['schemas']['AdminInviteCodeList']
export type AdminInviteCodeStatus = components['schemas']['AdminInviteCodeStatus']

export interface AdminInviteCodeQuery {
  page?: number
  size?: number
  status?: AdminInviteCodeStatus
}

export interface AdminInviteCodeCreatePayload {
  label?: string
  max_uses: number
  expires_days?: number
}

export const adminInviteCodesApi = {
  list: async (
    params: AdminInviteCodeQuery = {},
  ): Promise<AdminInviteCodeList> => {
    const { data } = await adminHttp.get<AdminInviteCodeList>(
      '/admin/invite-codes',
      { params },
    )
    return data
  },

  /** 创建；响应里的 `code` 是**一次性明文**。 */
  create: async (
    payload: AdminInviteCodeCreatePayload,
  ): Promise<AdminInviteCodeCreated> => {
    const { data } = await adminHttp.post<AdminInviteCodeCreated>(
      '/admin/invite-codes',
      payload,
    )
    return data
  },

  revoke: async (id: string): Promise<AdminInviteCode> => {
    const { data } = await adminHttp.post<AdminInviteCode>(
      `/admin/invite-codes/${id}/revoke`,
    )
    return data
  },
}
