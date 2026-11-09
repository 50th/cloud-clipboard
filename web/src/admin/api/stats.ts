/** 管理端概览统计接口。 */

import { adminHttp } from './client.ts'
import type { AdminStats } from './client.ts'

export const adminStatsApi = {
  get: async (): Promise<AdminStats> => {
    const { data } = await adminHttp.get<AdminStats>('/admin/stats')
    return data
  },
}
