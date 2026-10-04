/**
 * 全局状态（Zustand）。
 *
 * 规范：状态集中在 store 中，避免 prop drilling（AGENT.md 第 8 节）。
 */

import { create } from 'zustand'

import { clipboardApi, getErrorMessage } from '#src/api/client.ts'
import type { ClipboardItem, SortOrder } from '#src/api/client.ts'

export const PAGE_SIZE = 20

/**
 * 本次会话中出现过的记录 id（含历史列表里见过的）。
 * 用于判断一次上传是否命中了服务端内容去重。
 */
const knownIds = new Set<string>()

interface ClipboardState {
  items: ClipboardItem[]
  total: number
  pages: number
  page: number
  /** 列表阻塞式加载（首屏 / 翻页） */
  loading: boolean
  /** 后台静默刷新，不清空列表 */
  refreshing: boolean
  error: string | null
  search: string
  order: SortOrder

  /** 拉取列表；`silent=true` 用于上传后静默刷新，不显示加载态 */
  fetchItems: (options?: { page?: number; silent?: boolean }) => Promise<void>
  setPage: (page: number) => Promise<void>
  setSearch: (search: string) => Promise<void>
  setOrder: (order: SortOrder) => Promise<void>
  /**
   * 上传文本。
   * `title` 留空时由服务端自动生成。
   * 返回 `deduped=true` 表示命中了服务端内容去重。
   */
  uploadText: (
    text: string,
    title?: string,
  ) => Promise<{ item: ClipboardItem; deduped: boolean }>
  removeItem: (id: string) => Promise<void>
  clearAll: () => Promise<number>
}

export const useClipboardStore = create<ClipboardState>((set, get) => ({
  items: [],
  total: 0,
  pages: 0,
  page: 1,
  loading: false,
  refreshing: false,
  error: null,
  search: '',
  order: 'desc',

  fetchItems: async ({ page, silent } = {}) => {
    const target = page ?? get().page
    set(silent ? { refreshing: true, error: null } : { loading: true, error: null })

    try {
      const data = await clipboardApi.list({
        page: target,
        size: PAGE_SIZE,
        search: get().search || undefined,
        order: get().order,
      })
      for (const item of data.items) {
        knownIds.add(item.id)
      }
      set({
        items: data.items,
        total: data.total,
        pages: data.pages,
        page: data.page,
        loading: false,
        refreshing: false,
      })
    } catch (error) {
      set({ error: getErrorMessage(error), loading: false, refreshing: false })
    }
  },

  setPage: async (page) => {
    set({ page })
    await get().fetchItems({ page })
  },

  setSearch: async (search) => {
    set({ search, page: 1 })
    await get().fetchItems({ page: 1 })
  },

  setOrder: async (order) => {
    set({ order })
    await get().fetchItems({ page: 1 })
  },

  uploadText: async (text, title) => {
    // 服务端去重时返回的是已存在的记录：该 id 必然在「本次上传之前」就出现过。
    // 因此用跨请求累积的 knownIds 判断，避免「上传 → 立刻再传同样内容」时漏判。
    const trimmedTitle = title?.trim() ?? ''
    const item = await clipboardApi.create({
      content: text,
      content_type: 'text',
      ...(trimmedTitle ? { title: trimmedTitle } : {}),
    })
    const deduped = knownIds.has(item.id)
    knownIds.add(item.id)
    await get().fetchItems({ page: 1, silent: true })
    return { item, deduped }
  },

  removeItem: async (id) => {
    await clipboardApi.remove(id)
    const { page, items } = get()
    // 删除当前页最后一条时回退一页，避免停在空页
    const nextPage = items.length === 1 && page > 1 ? page - 1 : page
    await get().fetchItems({ page: nextPage, silent: true })
  },

  clearAll: async () => {
    const removed = get().total
    await clipboardApi.clear()
    await get().fetchItems({ page: 1, silent: true })
    return removed
  },
}))
