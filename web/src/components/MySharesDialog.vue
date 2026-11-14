<script setup lang="ts">
/** 「我的分享」分页弹窗：状态筛选、标题/内容搜索、复制链接、访问记录、撤销。 */
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import { getErrorMessage, shareApi } from '@/api/client'
import type { ClipboardShare, ClipboardShareList, ShareStatus } from '@/api/client'
import ShareAccessLogsDialog from '@/components/ShareAccessLogsDialog.vue'
import { writeText } from '@/utils/clipboard'
import { formatDateTime } from '@/utils/format'

const props = defineProps<{ open: boolean }>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'notice', value: { kind: 'ok' | 'err'; text: string }): void
}>()

type StatusFilter = ShareStatus | 'all'

const sizeOptions = [10, 20, 50]

const data = ref<ClipboardShareList | null>(null)
const page = ref(1)
const size = ref(10)
/** 默认只看有效分享 */
const statusFilter = ref<StatusFilter>('active')
const searchInput = ref('')
const search = ref('')
const loading = ref(false)
const errorText = ref('')
const busyId = ref<string | null>(null)
const copiedId = ref<string | null>(null)
const logsShare = ref<ClipboardShare | null>(null)
let copiedTimer: ReturnType<typeof setTimeout> | undefined
let searchTimer: ReturnType<typeof setTimeout> | undefined

const statusOptions: { value: StatusFilter; label: string }[] = [
  { value: 'active', label: '有效' },
  { value: 'expired', label: '已过期' },
  { value: 'exhausted', label: '次数用尽' },
  { value: 'revoked', label: '已撤销' },
  { value: 'all', label: '全部状态' },
]

const emptyText = computed(() => {
  if (search.value) {
    return `没有匹配「${search.value}」的分享`
  }
  if (statusFilter.value === 'active') {
    return '还没有有效分享。在历史记录卡片上点「分享」生成链接。'
  }
  if (statusFilter.value === 'all') {
    return '还没有分享。在历史记录卡片上点「分享」生成链接。'
  }
  return '没有该状态的分享'
})

const statusLabels: Record<ShareStatus, string> = {
  active: '有效',
  expired: '已过期',
  exhausted: '次数用尽',
  revoked: '已撤销',
}

const statusClasses: Record<ShareStatus, string> = {
  active: 'badge badge--ok',
  expired: 'badge badge--warn',
  exhausted: 'badge badge--warn',
  revoked: 'badge badge--off',
}

function modeLabel(mode: ClipboardShare['mode']): string {
  return mode === 'live' ? '跟随最新' : '快照'
}

function close(): void {
  emit('close')
}

async function load(): Promise<void> {
  loading.value = true
  errorText.value = ''
  try {
    data.value = await shareApi.list({
      page: page.value,
      size: size.value,
      status: statusFilter.value === 'all' ? undefined : statusFilter.value,
      search: search.value || undefined,
    })
  } catch (error) {
    errorText.value = getErrorMessage(error)
  } finally {
    loading.value = false
  }
}

/** 状态筛选或搜索变化后回到第一页。 */
function applyFilters(): void {
  page.value = 1
  search.value = searchInput.value.trim()
  void load()
}

function changePage(next: number): void {
  page.value = next
  void load()
}

function changeSize(next: number): void {
  size.value = next
  page.value = 1
  void load()
}

// 搜索防抖：停止输入 300ms 后查询（按标题或内容）
watch(searchInput, (value) => {
  if (searchTimer !== undefined) {
    clearTimeout(searchTimer)
  }
  searchTimer = setTimeout(() => {
    page.value = 1
    search.value = value.trim()
    void load()
  }, 300)
})

onBeforeUnmount(() => {
  if (searchTimer !== undefined) {
    clearTimeout(searchTimer)
  }
  if (copiedTimer !== undefined) {
    clearTimeout(copiedTimer)
  }
})

async function copyLink(share: ClipboardShare): Promise<void> {
  try {
    await writeText(share.url)
    copiedId.value = share.id
    if (copiedTimer !== undefined) {
      clearTimeout(copiedTimer)
    }
    copiedTimer = setTimeout(() => {
      copiedId.value = null
    }, 1500)
  } catch (error) {
    emit('notice', { kind: 'err', text: getErrorMessage(error) })
  }
}

async function revoke(share: ClipboardShare): Promise<void> {
  if (!window.confirm('撤销后链接立即失效，且无法恢复。确定撤销？')) {
    return
  }
  busyId.value = share.id
  errorText.value = ''
  try {
    await shareApi.revoke(share.id)
    emit('notice', { kind: 'ok', text: '已撤销分享' })
    // 撤销后当前页可能变空：回退一页再刷新
    if (data.value && data.value.items.length === 1 && page.value > 1) {
      page.value -= 1
    }
    await load()
  } catch (error) {
    errorText.value = getErrorMessage(error)
  } finally {
    busyId.value = null
  }
}

watch(
  () => props.open,
  (open) => {
    if (open) {
      page.value = 1
      size.value = 10
      statusFilter.value = 'active'
      searchInput.value = ''
      search.value = ''
      data.value = null
      errorText.value = ''
      void load()
    } else {
      logsShare.value = null
    }
  },
)
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="modal" role="presentation" @click.self="close">
      <div class="modal__panel" role="dialog" aria-modal="true" aria-label="我的分享">
        <header class="modal__head">
          <h2 class="modal__title">我的分享</h2>
          <button type="button" class="btn btn--small" :disabled="loading" @click="load">
            刷新
          </button>
        </header>

        <div class="modal__body">
          <div class="share-toolbar">
            <select
              v-model="statusFilter"
              class="select select--small"
              aria-label="分享状态筛选"
              @change="applyFilters"
            >
              <option v-for="item in statusOptions" :key="item.value" :value="item.value">
                {{ item.label }}
              </option>
            </select>
            <input
              v-model="searchInput"
              type="search"
              placeholder="搜索标题或内容"
              aria-label="搜索分享"
            />
          </div>

          <p v-if="errorText" class="inline-error" role="alert">{{ errorText }}</p>
          <p v-if="loading" class="loading">加载中…</p>
          <p v-else-if="!data || data.items.length === 0" class="empty">
            {{ emptyText }}
          </p>

          <ul v-else class="share-list">
            <li v-for="share in data.items" :key="share.id" class="share-row">
              <div class="share-row__head">
                <strong class="share-row__title" :title="share.title">
                  {{ share.title }}
                </strong>
                <span :class="statusClasses[share.status]">
                  {{ statusLabels[share.status] }}
                </span>
              </div>
              <p class="share-row__meta">
                {{ modeLabel(share.mode) }} ·
                查看 {{ share.view_count }} 次<template v-if="share.max_views">
                  / {{ share.max_views }}</template
                >
                <template v-if="share.expires_at">
                  · 到期 {{ formatDateTime(share.expires_at) }}
                </template>
                <template v-if="share.password_protected"> · 有密码</template>
              </p>
              <div class="share-row__actions">
                <button
                  type="button"
                  class="btn btn--small"
                  :disabled="share.status === 'revoked'"
                  @click="copyLink(share)"
                >
                  {{ copiedId === share.id ? '已复制' : '复制链接' }}
                </button>
                <button
                  type="button"
                  class="btn btn--small"
                  @click="logsShare = share"
                >
                  访问记录
                </button>
                <button
                  type="button"
                  class="btn btn--small btn--danger"
                  :disabled="share.status === 'revoked' || busyId === share.id"
                  @click="revoke(share)"
                >
                  {{ share.status === 'revoked' ? '已撤销' : '撤销' }}
                </button>
              </div>
            </li>
          </ul>

          <nav v-if="data" class="pagination share-pagination">
            <label class="share-pagination__size">
              每页
              <select
                class="select select--small"
                :value="size"
                aria-label="每页条数"
                @change="changeSize(Number(($event.target as HTMLSelectElement).value))"
              >
                <option v-for="option in sizeOptions" :key="option" :value="option">
                  {{ option }}
                </option>
              </select>
            </label>
            <span>共 {{ data.total }} 个</span>
            <button
              type="button"
              class="btn btn--small"
              :disabled="page <= 1"
              @click="changePage(page - 1)"
            >
              上一页
            </button>
            <span>第 {{ page }} / {{ data.pages || 1 }} 页</span>
            <button
              type="button"
              class="btn btn--small"
              :disabled="page >= data.pages"
              @click="changePage(page + 1)"
            >
              下一页
            </button>
          </nav>
        </div>

        <footer class="modal__foot">
          <button type="button" class="btn" @click="close">关闭</button>
        </footer>
      </div>
    </div>
  </Teleport>

  <ShareAccessLogsDialog
    :open="logsShare !== null"
    :share="logsShare"
    @close="logsShare = null"
  />
</template>

<style scoped>
.modal {
  position: fixed;
  inset: 0;
  z-index: 90;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(15, 23, 42, 0.45);
}

.modal__panel {
  width: min(620px, 100%);
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--card);
  border-radius: 12px;
  box-shadow: 0 20px 50px rgba(15, 23, 42, 0.25);
}

.modal__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 14px 16px;
  border-bottom: 1px solid var(--border);
}

.modal__title {
  margin: 0;
  font-size: 15px;
}

.modal__body {
  flex: 1 1 auto;
  overflow: auto;
  padding: 16px;
}

.modal__foot {
  display: flex;
  justify-content: flex-end;
  padding: 12px 16px;
  border-top: 1px solid var(--border);
}

/* 状态筛选 + 搜索：筛选固定宽度，搜索框占剩余空间 */
.share-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

/* 下拉框与输入框使用同一高度/字号，视觉上对齐 */
.share-toolbar select,
.share-toolbar input {
  height: 38px;
  padding: 8px 10px;
  font-size: 13px;
}

.share-toolbar select {
  flex: 0 0 auto;
  min-width: 104px;
}

.share-toolbar input {
  flex: 1 1 auto;
  min-width: 0;
}

.share-pagination {
  flex-wrap: wrap;
  gap: 8px 12px;
}

.share-pagination__size {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.share-pagination__size select {
  width: auto;
  height: 32px;
  padding: 4px 8px;
  font-size: 12px;
}

@media (max-width: 900px) {
  /* 移动端字号保持 16px，避免 iOS 聚焦时整页放大；两者仍保持等高 */
  .share-toolbar select,
  .share-toolbar input {
    height: 44px;
    font-size: 16px;
  }
}

.share-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.share-row {
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: 10px;
}

.share-row__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}

.share-row__title {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
}

.share-row__meta {
  margin: 4px 0 8px;
  color: var(--text-muted);
  font-size: 12px;
}

.share-row__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.badge {
  flex-shrink: 0;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
}

.badge--ok {
  background: #ecfdf5;
  color: var(--success);
}

.badge--warn {
  background: #fffbeb;
  color: #b45309;
}

.badge--off {
  background: #f3f4f6;
  color: var(--text-muted);
}
</style>
