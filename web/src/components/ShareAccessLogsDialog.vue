<script setup lang="ts">
/** 单条分享的成功访问记录；失败记录只有管理员能看。 */
import { ref, watch } from 'vue'

import { getErrorMessage, shareApi } from '@/api/client'
import type { ClipboardShare, ShareAccessLogList } from '@/api/client'
import { formatDateTime } from '@/utils/format'

const props = defineProps<{
  open: boolean
  share: ClipboardShare | null
}>()

const emit = defineEmits<{ (e: 'close'): void }>()

const PAGE_SIZE = 10

const data = ref<ShareAccessLogList | null>(null)
const page = ref(1)
const loading = ref(false)
const errorText = ref('')

async function load(): Promise<void> {
  if (!props.share) {
    return
  }
  loading.value = true
  errorText.value = ''
  try {
    data.value = await shareApi.accessLogs(props.share.id, {
      page: page.value,
      size: PAGE_SIZE,
    })
  } catch (error) {
    errorText.value = getErrorMessage(error)
  } finally {
    loading.value = false
  }
}

function changePage(next: number): void {
  page.value = next
  void load()
}

watch(
  () => [props.open, props.share?.id] as const,
  ([open]) => {
    if (open) {
      page.value = 1
      data.value = null
      errorText.value = ''
      void load()
    }
  },
)
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="modal modal--nested" role="presentation" @click.self="emit('close')">
      <div class="modal__panel" role="dialog" aria-modal="true" aria-label="访问记录">
        <header class="modal__head">
          <h2 class="modal__title">访问记录 · {{ share?.title ?? '' }}</h2>
          <button type="button" class="btn btn--small" :disabled="loading" @click="load">
            刷新
          </button>
        </header>

        <div class="modal__body">
          <p class="hint">只展示成功查看记录的脱敏 IP 与 User-Agent；失败尝试仅管理员可见。</p>
          <p v-if="errorText" class="inline-error" role="alert">{{ errorText }}</p>
          <p v-if="loading" class="loading">加载中…</p>
          <p v-else-if="!data || data.items.length === 0" class="empty">暂无访问记录</p>

          <div v-else class="log-scroll">
            <table class="log-table">
              <thead>
                <tr>
                  <th>时间</th>
                  <th>IP</th>
                  <th>User-Agent</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="log in data.items" :key="log.id">
                  <td>{{ formatDateTime(log.accessed_at) }}</td>
                  <td>{{ log.ip_masked ?? '—' }}</td>
                  <td class="log-ua" :title="log.user_agent ?? ''">
                    {{ log.user_agent ?? '—' }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <nav v-if="data && data.pages > 1" class="pagination">
            <button
              type="button"
              class="btn btn--small"
              :disabled="page <= 1"
              @click="changePage(page - 1)"
            >
              上一页
            </button>
            <span>第 {{ page }} / {{ data.pages }} 页</span>
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
          <button type="button" class="btn" @click="emit('close')">关闭</button>
        </footer>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
/* 弹窗基础样式在全局 styles.css，这里只覆盖宽度与日志表格 */
.modal__panel {
  width: min(720px, 100%);
}

.log-scroll {
  overflow: auto;
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-md);
}

.log-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

.log-table th,
.log-table td {
  padding: 10px 12px;
  border-bottom: 1px solid var(--border-soft);
  text-align: left;
  vertical-align: top;
}

.log-table tbody tr:last-child td {
  border-bottom: none;
}

.log-table tbody tr:hover {
  background: var(--surface-soft);
}

.log-table th {
  position: sticky;
  top: 0;
  background: var(--surface);
  color: var(--text-muted);
  font-size: 11.5px;
  font-weight: 600;
}

.log-ua {
  max-width: 320px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
