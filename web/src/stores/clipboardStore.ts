/**
 * 剪贴板状态（Pinia setup store）。
 *
 * 规范：状态集中在本 store，避免 prop drilling（AGENT.md 第 8 节）。
 * 业务逻辑与框架无关——只有响应式 API 是 Vue 的，端到端测试可直接驱动本 store。
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'

import { LOCAL_TIMEZONE, clipboardApi, getErrorMessage } from '#src/api/client.ts'
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

  /**
   * 「自动保存草稿」的当前记录 id 与它已保存的内容/标题。
   *
   * 自动保存复用同一条记录：打字过程中每隔一段时间保存一次、
   * 只更新这一行，而不是每个中间态都新建一行（否则历史列表会被刷屏）。
   */
  let draftId: string | null = null
  let draftContent = ''

  /** 清空草稿关联（用户清空输入框、或手动上传后另起一行时调用） */
  function resetDraft() {
    draftId = null
    draftContent = ''
  }

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
   * 保存自动保存草稿：**复用同一条记录**，没有草稿时才新建。
   *
   * 返回 `deduped=true` 表示新建时命中了服务端内容去重。
   */
  async function saveDraft(
    text: string,
    title?: string,
  ): Promise<{ item: ClipboardItem; deduped: boolean }> {
    const trimmedTitle = title?.trim() ?? ''

    if (draftId) {
      try {
        const item = await clipboardApi.update(draftId, {
          content: text,
          ...(trimmedTitle ? { title: trimmedTitle } : {}),
          timezone: LOCAL_TIMEZONE,
        })
        draftContent = item.content
        await fetchItems({ page: 1, silent: true })
        return { item, deduped: false }
      } catch (err) {
        // 草稿可能在别处被删了 → 丢掉关联，走下面的新建分支
        if (!isNotFound(err)) {
          throw err
        }
        resetDraft()
      }
    }

    const { item, deduped } = await createNew(text, title)
    draftId = item.id
    draftContent = item.content
    return { item, deduped }
  }

  /** 新建一条记录（不做草稿复用） */
  async function createNew(
    text: string,
    title?: string,
  ): Promise<{ item: ClipboardItem; deduped: boolean }> {
    const trimmedTitle = title?.trim() ?? ''
    const item = await clipboardApi.create({
      content: text,
      content_type: 'text',
      timezone: LOCAL_TIMEZONE,
      ...(trimmedTitle ? { title: trimmedTitle } : {}),
    })
    const deduped = knownIds.has(item.id)
    knownIds.add(item.id)
    await fetchItems({ page: 1, silent: true })
    return { item, deduped }
  }

  /**
   * 手动上传。
   *
   * 若输入框内容与当前草稿保存的内容一致，则**复用草稿那一行**（只更新标题），
   * 避免「自动保存已经把内容存进去了，再点上传又冒出一行一模一样的」。
   */
  async function uploadText(
    text: string,
    title?: string,
  ): Promise<{ item: ClipboardItem; deduped: boolean }> {
    const trimmedTitle = title?.trim() ?? ''
    const content = text.trim()

    if (draftId && draftContent === content) {
      const item = await clipboardApi.update(draftId, {
        ...(trimmedTitle ? { title: trimmedTitle } : {}),
        timezone: LOCAL_TIMEZONE,
      })
      draftContent = item.content
      await fetchItems({ page: 1, silent: true })
      return { item, deduped: false }
    }

    // 手动上传视为「记录定稿」：另起一行，并解除草稿关联
    const result = await createNew(content, title)
    resetDraft()
    return result
  }

  /** 用户清空输入框时调用，避免下一条内容覆盖旧草稿 */
  function clearDraft() {
    resetDraft()
  }

  async function removeItem(id: string) {
    await clipboardApi.remove(id)
    if (draftId === id) {
      resetDraft()
    }
    // 删除当前页最后一条时回退一页，避免停在空页
    const nextPage = items.value.length === 1 && page.value > 1 ? page.value - 1 : page.value
    await fetchItems({ page: nextPage, silent: true })
  }

  async function clearAll(): Promise<number> {
    const removed = total.value
    await clipboardApi.clear()
    resetDraft()
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
    saveDraft,
    uploadText,
    clearDraft,
    removeItem,
    clearAll,
  }
})

/** 判断异常是否为 404（草稿已被删除） */
function isNotFound(error: unknown): boolean {
  return (
    typeof error === 'object' &&
    error !== null &&
    'response' in error &&
    (error as { response?: { status?: number } }).response?.status === 404
  )
}
