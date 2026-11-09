/** 管理端剪贴板接口。 */

import { adminHttp } from './client.ts'
import type {
  AdminClipboardItem,
  AdminClipboardItemList,
  MessageResponse,
} from './client.ts'

export interface AdminClipboardQuery {
  page?: number
  size?: number
  user_id?: string
  username?: string
  search?: string
  content_type?: 'text' | 'image' | 'file'
  sort_by?: 'created_at' | 'updated_at'
  order?: 'asc' | 'desc'
}

export const adminClipboardsApi = {
  list: async (
    params: AdminClipboardQuery = {},
  ): Promise<AdminClipboardItemList> => {
    const { data } = await adminHttp.get<AdminClipboardItemList>(
      '/admin/clipboards',
      { params },
    )
    return data
  },

  detail: async (id: string): Promise<AdminClipboardItem> => {
    const { data } = await adminHttp.get<AdminClipboardItem>(
      `/admin/clipboards/${id}`,
    )
    return data
  },

  remove: async (id: string): Promise<MessageResponse> => {
    const { data } = await adminHttp.delete<MessageResponse>(
      `/admin/clipboards/${id}`,
    )
    return data
  },
}
