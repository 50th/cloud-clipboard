<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { ref } from 'vue'

import ClipboardItemCard from '@/components/ClipboardItemCard.vue'
import type { ClipboardItem } from '@/api/client'
import { shareApi } from '@/api/client'
import { useClipboardStore } from '@/stores/clipboardStore'
import { logger } from '@/utils/logger'

const store = useClipboardStore()
const { items, loading, error, total, page, pages, search, order } = storeToRefs(store)

const props = defineProps<{
  /** 搜索框的即时值（防抖由 App 统一处理） */
  searchInput: string
}>()

const emit = defineEmits<{
  (e: 'update:searchInput', value: string): void
  /** 清空全部（确认与提示由 App 统一处理） */
  (e: 'clear-all'): void
  /** 打开创建分享弹窗 */
  (e: 'share', item: ClipboardItem): void
}>()

const deletingId = ref<string | null>(null)

/** 搜索框输入：只向上抛出，防抖在 App 里统一处理 */
function onSearchInput(event: Event) {
  emit('update:searchInput', (event.target as HTMLInputElement).value)
}

async function handleDelete(id: string) {
  const target = items.value.find((item) => item.id === id)
  const label = target?.title ? `「${target.title}」` : '这条记录'

  // 删除会级联删除分享；先查有效分享数，避免用户不知道链接会失效。
  let activeShares = 0
  try {
    const result = await shareApi.list({ item_id: id, status: 'active', size: 1 })
    activeShares = result.total
  } catch (error) {
    // 查询失败不阻塞删除；按 0 处理，保持原有确认文案。
    logger.debug('查询有效分享数失败，按 0 处理', error)
  }

  const message =
    activeShares > 0
      ? `该记录有 ${activeShares} 个有效分享，删除后这些链接将立即失效。确定删除？`
      : `确定删除${label}？此操作不可撤销。`
  if (!window.confirm(message)) {
    return
  }

  deletingId.value = id
  try {
    await store.removeItem(id)
  } finally {
    deletingId.value = null
  }
}

function handleShare(item: ClipboardItem) {
  emit('share', item)
}

/**
 * 点条目载入输入区编辑。
 *
 * 只**请求**，真正的切换由输入区在落盘当前未保存内容之后执行
 * （见 clipboardStore 的 requestEdit / applyRequestedEdit）。
 */
function handleEdit(item: ClipboardItem) {
  store.requestEdit(item)
}
</script>

<template>
  <section class="card panel panel--history">
    <div class="panel__head">
      <h2>历史记录</h2>
      <span class="count">
        共 {{ total }} 条{{ store.refreshing ? ' · 同步中…' : '' }}
      </span>
    </div>

    <!-- 搜索框：位于历史记录列表顶部 -->
    <label class="field field--tight">
      <span>搜索（标题或内容）</span>
      <input
        type="search"
        :value="props.searchInput"
        placeholder="输入关键字，停止输入后自动搜索"
        @input="onSearchInput"
      />
    </label>

    <!-- 历史相关操作：全部集中在历史面板 -->
    <div class="actions actions--wrap history-actions">
      <button type="button" class="btn btn--small" @click="store.fetchItems()">刷新</button>
      <select
        class="select select--small"
        :value="order"
        aria-label="排序"
        @change="store.setOrder(($event.target as HTMLSelectElement).value as 'asc' | 'desc')"
      >
        <option value="desc">最近修改</option>
        <option value="asc">最早修改</option>
      </select>
      <button
        type="button"
        class="btn btn--small btn--danger"
        :disabled="total === 0"
        @click="emit('clear-all')"
      >
        清空全部
      </button>
    </div>

    <p v-if="search" class="count">正在按「{{ search }}」筛选，共 {{ total }} 条命中</p>
    <p v-if="error" class="inline-error">{{ error }}</p>

    <div class="history-scroll">
      <p v-if="loading" class="loading">加载中…</p>
      <p v-else-if="items.length === 0" class="empty">
        还没有记录。在输入区输入或粘贴内容后点「保存」。
      </p>
      <div v-else class="items">
        <ClipboardItemCard
          v-for="item in items"
          :key="item.id"
          :item="item"
          :deleting="deletingId === item.id"
          :editing="store.editingId === item.id"
          @delete="handleDelete"
          @edit="handleEdit"
          @share="handleShare"
        />
      </div>
    </div>

    <nav v-if="pages > 1" class="pagination">
      <button
        type="button"
        class="btn btn--small"
        :disabled="page <= 1"
        @click="store.setPage(page - 1)"
      >
        上一页
      </button>
      <span>第 {{ page }} / {{ pages }} 页</span>
      <button
        type="button"
        class="btn btn--small"
        :disabled="page >= pages"
        @click="store.setPage(page + 1)"
      >
        下一页
      </button>
    </nav>
  </section>
</template>
