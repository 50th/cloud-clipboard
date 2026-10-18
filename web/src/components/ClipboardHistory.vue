<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { ref } from 'vue'

import ClipboardItemCard from '@/components/ClipboardItemCard.vue'
import type { ClipboardItem } from '@/api/client'
import { useClipboardStore } from '@/stores/clipboardStore'

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
}>()

const deletingId = ref<string | null>(null)

/** 搜索框输入：只向上抛出，防抖在 App 里统一处理 */
function onSearchInput(event: Event) {
  emit('update:searchInput', (event.target as HTMLInputElement).value)
}

async function handleDelete(id: string) {
  deletingId.value = id
  try {
    await store.removeItem(id)
  } finally {
    deletingId.value = null
  }
}

/**
 * 点条目载入右侧编辑。
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

    <!-- 历史相关操作：全部集中在左栏 -->
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
        还没有记录。在右侧输入内容，或点「同步剪贴板」。
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
