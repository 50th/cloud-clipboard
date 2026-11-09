/** 管理端用户接口。 */

import { adminHttp } from './client.ts'
import type {
  AdminUser,
  AdminUserList,
  AdminUserUpdate,
  MessageResponse,
} from './client.ts'

export interface AdminUserQuery {
  page?: number
  size?: number
  search?: string
  status?: 'all' | 'active' | 'disabled'
  role?: 'all' | 'admin' | 'user'
  sort_by?: 'created_at' | 'last_login_at' | 'item_count'
  order?: 'asc' | 'desc'
}

export const adminUsersApi = {
  list: async (params: AdminUserQuery = {}): Promise<AdminUserList> => {
    const { data } = await adminHttp.get<AdminUserList>('/admin/users', { params })
    return data
  },

  detail: async (id: string): Promise<AdminUser> => {
    const { data } = await adminHttp.get<AdminUser>(`/admin/users/${id}`)
    return data
  },

  update: async (id: string, payload: AdminUserUpdate): Promise<AdminUser> => {
    const { data } = await adminHttp.patch<AdminUser>(
      `/admin/users/${id}`,
      payload,
    )
    return data
  },

  resetPassword: async (id: string, password: string): Promise<MessageResponse> => {
    const { data } = await adminHttp.post<MessageResponse>(
      `/admin/users/${id}/reset-password`,
      { password },
    )
    return data
  },

  remove: async (id: string): Promise<MessageResponse> => {
    const { data } = await adminHttp.delete<MessageResponse>(`/admin/users/${id}`)
    return data
  },

  clearClipboards: async (id: string): Promise<MessageResponse> => {
    const { data } = await adminHttp.delete<MessageResponse>(
      `/admin/users/${id}/clipboards`,
    )
    return data
  },
}
