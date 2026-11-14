/** 管理端分享限额设置接口。 */

import { adminHttp } from './client.ts'
import type { components } from '#src/types/api.ts'

export type ShareSettings = components['schemas']['ShareSettingsResponse']

export const adminShareSettingsApi = {
  get: async (): Promise<ShareSettings> => {
    const { data } = await adminHttp.get<ShareSettings>('/admin/settings/shares')
    return data
  },

  update: async (userShareLimit: number): Promise<ShareSettings> => {
    const { data } = await adminHttp.put<ShareSettings>('/admin/settings/shares', {
      user_share_limit: userShareLimit,
    })
    return data
  },
}
