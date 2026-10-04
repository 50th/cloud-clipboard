/**
 * 剪贴板状态（Pinia setup store）。
 *
 * 规范：状态集中在本 store，避免 prop drilling（AGENT.md 第 8 节）。
 * 业务逻辑与框架无关——只有响应式 API 是 Vue 的，端到端测试可直接驱动本 store。
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'

import { clipboardApi, getErrorMessage } from '#src/api/client.ts'
import type { ClipboardItem, SortOrder } from '#src/api/client.ts'

export const PAGE_SIZE = 20

/**
 * 本次会话中出现过的记录 id（含历史列表里见过的）。
 * 用于判断一次上传是否命中了服务端内容去重。
 */
const knownIds = new Set<string>()

export const useClipboardStore = defineStore('clipboard', () => {
  const items = ref<ClipboardItem[]>([])
  const total = ref(0)
  const pages = ref(0)
  const page = ref(1)
  /** 列表阻塞式加载（首屏 / 翻页） */
  const loading = ref(false)
  /** 后台静默刷新，不清空列表 */
  const refreshing = ref(false)
  const error = ref<string | null>(null)
  const search = ref('')
  const order = ref<SortOrder>('desc')

  /** 拉取列表；`silent=true` 用于上传后静默刷新，不显示加载态 */
  async function fetchItems(options: { page?: number; silent?: boolean } = {}) {
    const target = options.page ?? page.value
    if (options.silent) {
      refreshing.value = true
      error.value = null
    } else {
      loading.value = true
      error.value = null
    }

    try {
      const data = await clipboardApi.list({
        page: target,
        size: PAGE_SIZE,
        search: search.value || undefined,
        order: order.value,
      })
      for (const item of data.items) {
        knownIds.add(item.id)
      }
      items.value = data.items
      total.value = data.total
      pages.value = data.pages
      page.value = data.page
    } catch (err) {
      error.value = getErrorMessage(err)
    } finally {
      loading.value = false
      refreshing.value = false
    }
  }

  async function setPage(next: number) {
    page.value = next
    await fetchItems({ page: next })
  }

  async function setSearch(next: string) {
    search.value = next
    page.value = 1
    await fetchItems({ page: 1 })
  }

  async function setOrder(next: SortOrder) {
    order.value = next
    await fetchItems({ page: 1 })
  }

  /**
   * 上传文本；`title` 留空时由服务端自动生成。
   * 返回 `deduped=true` 表示命中了服务端内容去重。
   */
  async function uploadText(
    text: string,
    title?: string,
  ): Promise<{ item: ClipboardItem; deduped: boolean }> {
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
    await fetchItems({ page: 1, silent: true })
    return { item, deduped }
  }

  async function removeItem(id: string) {
    await clipboardApi.remove(id)
    // 删除当前页最后一条时回退一页，避免停在空页
    const nextPage = items.value.length === 1 && page.value > 1 ? page.value - 1 : page.value
    await fetchItems({ page: nextPage, silent: true })
  }

  async function clearAll(): Promise<number> {
    const removed = total.value
    await clipboardApi.clear()
    await fetchItems({ page: 1, silent: true })
    return removed
  }

  return {
    items,
    total,
    pages,
    page,
    loading,
    refreshing,
    error,
    search,
    order,
    fetchItems,
    setPage,
    setSearch,
    setOrder,
    uploadText,
    removeItem,
    clearAll,
  }
})
