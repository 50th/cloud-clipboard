<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { adminAuditApi } from '@/admin/api/audit.ts'
import type { AdminAuditLogList } from '@/admin/api/client.ts'
import Pagination from '@/admin/components/Pagination.vue'
import { getErrorMessage } from '#src/api/client.ts'
import { formatDateTime } from '@/utils/format.ts'

const adminUsername = ref('')
const action = ref('')
const startLocal = ref('')
const endLocal = ref('')
const page = ref(1)
const size = ref(10)
const data = ref<AdminAuditLogList | null>(null)
const loading = ref(false)
const error = ref('')

const actions = [
  { value: '', label: '全部动作' },
  { value: 'admin.login', label: 'admin.login' },
  { value: 'user.update', label: 'user.update' },
  { value: 'user.enable', label: 'user.enable' },
  { value: 'user.disable', label: 'user.disable' },
  { value: 'user.promote', label: 'user.promote' },
  { value: 'user.demote', label: 'user.demote' },
  { value: 'user.reset_password', label: 'user.reset_password' },
  { value: 'user.delete', label: 'user.delete' },
  { value: 'user.clipboards.clear', label: 'user.clipboards.clear' },
  { value: 'clipboard.delete', label: 'clipboard.delete' },
]

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
    data.value = await adminAuditApi.list({
      page: page.value,
      size: size.value,
      admin_username: adminUsername.value.trim() || undefined,
      action: action.value || undefined,
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

function detailText(detail: Record<string, unknown> | null | undefined): string {
  return detail ? JSON.stringify(detail) : '—'
}

onMounted(load)
</script>

<template>
  <section class="card">
    <div class="panel__head">
      <h2>操作日志</h2>
      <span class="hint">共 {{ data?.total ?? 0 }} 条</span>
    </div>

    <form class="admin-toolbar" @submit.prevent="applyFilters">
      <input
        v-model="adminUsername"
        type="search"
        placeholder="管理员用户名"
        aria-label="管理员用户名"
      />
      <select v-model="action" aria-label="动作筛选" @change="applyFilters">
        <option v-for="item in actions" :key="item.value" :value="item.value">
          {{ item.label }}
        </option>
      </select>
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
            <th>管理员</th>
            <th>动作</th>
            <th>目标类型</th>
            <th>目标 ID</th>
            <th>详情</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="entry in data.items" :key="entry.id">
            <td>{{ formatDateTime(entry.created_at) }}</td>
            <td>{{ entry.admin_username }}</td>
            <td><code>{{ entry.action }}</code></td>
            <td>{{ entry.target_type || '—' }}</td>
            <td class="audit-target">{{ entry.target_id || '—' }}</td>
            <td class="audit-detail">{{ detailText(entry.detail) }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <p v-else-if="!loading" class="admin-empty">没有匹配的审计记录</p>

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
.audit-target {
  max-width: 280px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.audit-detail {
  max-width: 320px;
  white-space: normal;
  word-break: break-all;
}
</style>
