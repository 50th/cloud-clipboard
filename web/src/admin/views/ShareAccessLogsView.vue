<script setup lang="ts">
/** 分享访问记录：管理员可查看成功与失败尝试。 */
import { onMounted, ref } from 'vue'

import {
  adminShareAccessLogsApi,
  type AdminShareAccessLogList,
  type AdminShareAccessResult,
} from '@/admin/api/shareAccessLogs.ts'
import Pagination from '@/admin/components/Pagination.vue'
import { getErrorMessage } from '#src/api/client.ts'
import { formatDateTime } from '@/utils/format.ts'

const result = ref<AdminShareAccessResult>('all')
const shareId = ref('')
const username = ref('')
const startLocal = ref('')
const endLocal = ref('')
const page = ref(1)
const size = ref(10)
const data = ref<AdminShareAccessLogList | null>(null)
const loading = ref(false)
const error = ref('')

const resultOptions: { value: AdminShareAccessResult; label: string }[] = [
  { value: 'all', label: '全部结果' },
  { value: 'success', label: '成功' },
  { value: 'failure', label: '失败' },
]

const resultLabels: Record<string, string> = {
  success: '成功',
  password_failed: '密码错误',
  expired: '已过期',
  revoked: '已撤销',
  exhausted: '次数用尽',
  owner_disabled: '分享者被禁用',
}

function resultClass(value: string): string {
  return value === 'success' ? 'badge badge--ok' : 'badge badge--warn'
}

function toIso(value: string): string | undefined {
  if (!value) {
    return undefined
  }
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? undefined : date.toISOString()
}

async function load(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    data.value = await adminShareAccessLogsApi.list({
      page: page.value,
      size: size.value,
      result: result.value,
      share_id: shareId.value.trim() || undefined,
      username: username.value.trim() || undefined,
      start: toIso(startLocal.value),
      end: toIso(endLocal.value),
    })
  } catch (err) {
    error.value = getErrorMessage(err)
  } finally {
    loading.value = false
  }
}

function applyFilters(): void {
  page.value = 1
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

onMounted(load)
</script>

<template>
  <section class="card">
    <div class="panel__head">
      <h2>分享访问记录</h2>
      <span class="hint">共 {{ data?.total ?? 0 }} 条</span>
    </div>

    <p class="hint">失败记录只有本页面能查看；用户端「我的分享」只返回成功记录。</p>

    <form class="admin-toolbar" @submit.prevent="applyFilters">
      <select v-model="result" aria-label="结果筛选">
        <option v-for="item in resultOptions" :key="item.value" :value="item.value">
          {{ item.label }}
        </option>
      </select>
      <input
        v-model="shareId"
        type="search"
        placeholder="分享 UUID"
        aria-label="分享 UUID"
      />
      <input
        v-model="username"
        type="search"
        placeholder="分享者用户名"
        aria-label="分享者用户名"
      />
      <label class="admin-toolbar__field">
        开始
        <input v-model="startLocal" type="datetime-local" aria-label="开始时间" />
      </label>
      <label class="admin-toolbar__field">
        结束
        <input v-model="endLocal" type="datetime-local" aria-label="结束时间" />
      </label>
      <button type="submit" class="btn btn--small btn--primary">筛选</button>
      <button type="button" class="btn btn--small" :disabled="loading" @click="load">
        刷新
      </button>
    </form>

    <p v-if="error" class="inline-error" role="alert">{{ error }}</p>

    <div v-if="data && data.items.length" class="admin-table__wrap">
      <table class="admin-table">
        <thead>
          <tr>
            <th>时间</th>
            <th>结果</th>
            <th>分享标题</th>
            <th>分享者</th>
            <th>原始 IP</th>
            <th>User-Agent</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="log in data.items" :key="log.id">
            <td>{{ formatDateTime(log.accessed_at) }}</td>
            <td>
              <span :class="resultClass(log.result)">
                {{ resultLabels[log.result] ?? log.result }}
              </span>
            </td>
            <td class="share-log-title" :title="log.share_title">
              {{ log.share_title }}
            </td>
            <td>{{ log.owner_username }}</td>
            <td>{{ log.ip ?? '—' }}</td>
            <td class="share-log-ua" :title="log.user_agent ?? ''">
              {{ log.user_agent ?? '—' }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <p v-else-if="!loading" class="admin-empty">没有匹配的访问记录</p>

    <Pagination
      :page="page"
      :pages="data?.pages ?? 0"
      :total="data?.total ?? 0"
      :size="size"
      @update:page="changePage"
      @update:size="changeSize"
    />
  </section>
</template>

<style scoped>
.share-log-title,
.share-log-ua {
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
