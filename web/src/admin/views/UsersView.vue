<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { adminUsersApi } from '@/admin/api/users.ts'
import type { AdminUser, AdminUserList } from '@/admin/api/client.ts'
import Pagination from '@/admin/components/Pagination.vue'
import { useAdminStore } from '@/admin/stores/adminStore'
import { getErrorMessage } from '#src/api/client.ts'
import { formatDateTime } from '@/utils/format.ts'

const store = useAdminStore()

const search = ref('')
const status = ref<'all' | 'active' | 'disabled'>('all')
const role = ref<'all' | 'admin' | 'user'>('all')
const page = ref(1)
const size = ref(10)
const data = ref<AdminUserList | null>(null)
const loading = ref(false)
const error = ref('')
const notice = ref('')
const busyId = ref<string | null>(null)

async function load(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    data.value = await adminUsersApi.list({
      page: page.value,
      size: size.value,
      search: search.value.trim() || undefined,
      status: status.value,
      role: role.value,
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

async function toggleActive(user: AdminUser): Promise<void> {
  const action = user.is_active ? '禁用' : '启用'
  const message = user.is_active
    ? `确定禁用用户 ${user.username}？禁用后其登录与实时连接将立即失效。`
    : `确定启用用户 ${user.username}？`
  if (!window.confirm(message)) {
    return
  }
  busyId.value = user.id
  error.value = ''
  notice.value = ''
  try {
    await adminUsersApi.update(user.id, { is_active: !user.is_active })
    notice.value = `已${action}用户 ${user.username}`
    await load()
  } catch (err) {
    error.value = getErrorMessage(err)
  } finally {
    busyId.value = null
  }
}

async function removeUser(user: AdminUser): Promise<void> {
  const message =
    `确定删除用户 ${user.username}？\n` +
    `其 ${user.item_count} 条剪贴板将一并删除，且不可恢复。`
  if (!window.confirm(message)) {
    return
  }
  busyId.value = user.id
  error.value = ''
  notice.value = ''
  try {
    const result = await adminUsersApi.remove(user.id)
    notice.value = result.message
    if (data.value && data.value.items.length === 1 && page.value > 1) {
      page.value -= 1
    }
    await load()
  } catch (err) {
    error.value = getErrorMessage(err)
  } finally {
    busyId.value = null
  }
}

function formatDate(value: string | null | undefined): string {
  return value ? formatDateTime(value) : '—'
}

onMounted(load)
</script>

<template>
  <section class="card">
    <div class="panel__head">
      <h2>用户管理</h2>
      <span class="hint">共 {{ data?.total ?? 0 }} 个用户</span>
    </div>

    <form class="admin-toolbar" @submit.prevent="applyFilters">
      <input
        v-model="search"
        type="search"
        placeholder="搜索用户名或邮箱"
        aria-label="搜索用户"
      />
      <select v-model="status" aria-label="状态筛选" @change="applyFilters">
        <option value="all">全部状态</option>
        <option value="active">启用</option>
        <option value="disabled">禁用</option>
      </select>
      <select v-model="role" aria-label="角色筛选" @change="applyFilters">
        <option value="all">全部角色</option>
        <option value="admin">管理员</option>
        <option value="user">普通用户</option>
      </select>
      <button type="submit" class="btn btn--small btn--primary">搜索</button>
      <button type="button" class="btn btn--small" :disabled="loading" @click="load">
        刷新
      </button>
    </form>

    <p v-if="error" class="inline-error" role="alert">{{ error }}</p>
    <p v-if="notice" class="hint" role="status">{{ notice }}</p>

    <div v-if="data && data.items.length" class="admin-table__wrap">
      <table class="admin-table">
        <thead>
          <tr>
            <th>用户名</th>
            <th>邮箱</th>
            <th>状态</th>
            <th>角色</th>
            <th>剪贴板</th>
            <th>最后登录</th>
            <th>注册时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="user in data.items" :key="user.id">
            <td>{{ user.username }}</td>
            <td>{{ user.email }}</td>
            <td>
              <span :class="['badge', user.is_active ? 'badge--ok' : 'badge--off']">
                {{ user.is_active ? '启用' : '禁用' }}
              </span>
            </td>
            <td>
              <span v-if="user.is_admin" class="badge badge--admin">管理员</span>
              <span v-else class="hint">普通用户</span>
            </td>
            <td>{{ user.item_count }}</td>
            <td>{{ formatDate(user.last_login_at) }}</td>
            <td>{{ formatDate(user.created_at) }}</td>
            <td>
              <div class="admin-table__actions">
                <button
                  type="button"
                  class="btn btn--small"
                  @click="store.openUser(user.id)"
                >
                  详情
                </button>
                <button
                  type="button"
                  class="btn btn--small"
                  :disabled="busyId === user.id"
                  @click="toggleActive(user)"
                >
                  {{ user.is_active ? '禁用' : '启用' }}
                </button>
                <button
                  type="button"
                  class="btn btn--small btn--danger"
                  :disabled="busyId === user.id"
                  @click="removeUser(user)"
                >
                  删除
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <p v-else-if="!loading" class="admin-empty">没有匹配的用户</p>

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
