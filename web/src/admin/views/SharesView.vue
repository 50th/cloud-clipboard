<script setup lang="ts">
/** 分享管理：全局分享列表（只读）。 */
import { onMounted, ref } from 'vue'

import {
  adminSharesApi,
  type AdminShareStatus,
  type AdminShareList,
} from '@/admin/api/shares.ts'
import Pagination from '@/admin/components/Pagination.vue'
import { useAdminStore } from '@/admin/stores/adminStore'
import { getErrorMessage } from '#src/api/client.ts'
import { formatDateTime } from '@/utils/format.ts'

const store = useAdminStore()

const status = ref<AdminShareStatus | 'all'>('all')
const username = ref('')
const page = ref(1)
const size = ref(10)
const data = ref<AdminShareList | null>(null)
const loading = ref(false)
const error = ref('')

const statusOptions: { value: AdminShareStatus | 'all'; label: string }[] = [
  { value: 'all', label: '全部状态' },
  { value: 'active', label: '有效' },
  { value: 'expired', label: '已过期' },
  { value: 'exhausted', label: '次数用尽' },
  { value: 'revoked', label: '已撤销' },
]

const statusLabels: Record<string, string> = {
  active: '有效',
  expired: '已过期',
  exhausted: '次数用尽',
  revoked: '已撤销',
}

function statusClass(value: string): string {
  if (value === 'active') {
    return 'badge badge--ok'
  }
  if (value === 'revoked') {
    return 'badge badge--off'
  }
  return 'badge badge--warn'
}

function formatDate(value: string | null | undefined): string {
  return value ? formatDateTime(value) : '—'
}

async function load(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    data.value = await adminSharesApi.list({
      page: page.value,
      size: size.value,
      status: status.value === 'all' ? undefined : status.value,
      username: username.value.trim() || undefined,
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
      <h2>分享管理</h2>
      <span class="hint">共 {{ data?.total ?? 0 }} 个分享</span>
    </div>

    <form class="admin-toolbar" @submit.prevent="applyFilters">
      <select v-model="status" aria-label="分享状态筛选" @change="applyFilters">
        <option v-for="item in statusOptions" :key="item.value" :value="item.value">
          {{ item.label }}
        </option>
      </select>
      <input
        v-model="username"
        type="search"
        placeholder="分享者用户名"
        aria-label="分享者用户名"
      />
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
            <th>标题</th>
            <th>分享者</th>
            <th>模式</th>
            <th>状态</th>
            <th>查看次数</th>
            <th>到期时间</th>
            <th>创建时间</th>
            <th>密码</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="share in data.items" :key="share.id">
            <td class="share-title-cell" :title="share.title">
              {{ share.title }}
            </td>
            <td>{{ share.owner_username }}</td>
            <td>{{ share.mode === 'live' ? '跟随最新' : '快照' }}</td>
            <td>
              <span :class="statusClass(share.status)">
                {{ statusLabels[share.status] ?? share.status }}
              </span>
            </td>
            <td>
              {{ share.view_count }}<template v-if="share.max_views">
                / {{ share.max_views }}</template
              >
            </td>
            <td>{{ formatDate(share.expires_at) }}</td>
            <td>{{ formatDate(share.created_at) }}</td>
            <td>{{ share.password_protected ? '有' : '无' }}</td>
            <td>
              <div class="admin-table__actions">
                <button
                  type="button"
                  class="btn btn--small"
                  @click="store.openUser(share.owner_id)"
                >
                  查看用户
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <p v-else-if="!loading" class="admin-empty">没有符合条件的分享</p>

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
.share-title-cell {
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
