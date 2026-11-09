<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import { adminUsersApi } from '@/admin/api/users.ts'
import { adminClipboardsApi } from '@/admin/api/clipboards.ts'
import type {
  AdminClipboardItem,
  AdminClipboardItemList,
  AdminUser,
} from '@/admin/api/client.ts'
import Pagination from '@/admin/components/Pagination.vue'
import { useAdminStore } from '@/admin/stores/adminStore'
import { getErrorMessage } from '#src/api/client.ts'
import { formatBytes, formatDateTime } from '@/utils/format.ts'

const store = useAdminStore()

const user = ref<AdminUser | null>(null)
const clipboards = ref<AdminClipboardItemList | null>(null)
const page = ref(1)
const size = ref(10)
const expanded = ref<AdminClipboardItem | null>(null)
const loading = ref(false)
const error = ref('')
const notice = ref('')
const busy = ref(false)

const resetOpen = ref(false)
const newPassword = ref('')

const isSelf = computed(() => user.value?.id === store.user?.id)

function formatDate(value: string | null | undefined): string {
  return value ? formatDateTime(value) : '—'
}

function itemSize(item: AdminClipboardItem): string {
  const size = (item.metadata as { size?: number } | null)?.size
  return typeof size === 'number' ? formatBytes(size) : '—'
}

async function load(): Promise<void> {
  const id = store.selectedUserId
  if (!id) {
    user.value = null
    clipboards.value = null
    return
  }
  loading.value = true
  error.value = ''
  try {
    const [detail, list] = await Promise.all([
      adminUsersApi.detail(id),
      adminClipboardsApi.list({
        user_id: id,
        page: page.value,
        size: size.value,
        sort_by: 'updated_at',
        order: 'desc',
      }),
    ])
    user.value = detail
    clipboards.value = list
  } catch (err) {
    error.value = getErrorMessage(err)
  } finally {
    loading.value = false
  }
}

async function toggleActive(): Promise<void> {
  if (!user.value) {
    return
  }
  const message = user.value.is_active
    ? `确定禁用用户 ${user.value.username}？禁用后其登录与实时连接将立即失效。`
    : `确定启用用户 ${user.value.username}？`
  if (!window.confirm(message)) {
    return
  }
  const nextActive = !user.value.is_active
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    await adminUsersApi.update(user.value.id, { is_active: nextActive })
    notice.value = nextActive ? '已启用用户' : '已禁用用户'
    await load()
  } catch (err) {
    error.value = getErrorMessage(err)
  } finally {
    busy.value = false
  }
}

async function submitReset(): Promise<void> {
  if (!user.value) {
    return
  }
  if (newPassword.value.length < 6) {
    error.value = '新密码至少 6 位'
    return
  }
  if (
    !window.confirm(
      `确定重置用户 ${user.value.username} 的密码？其全部旧登录状态将立即失效。`,
    )
  ) {
    return
  }
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    const result = await adminUsersApi.resetPassword(user.value.id, newPassword.value)
    newPassword.value = ''
    resetOpen.value = false
    notice.value = result.message
  } catch (err) {
    error.value = getErrorMessage(err)
  } finally {
    busy.value = false
  }
}

async function clearClipboards(): Promise<void> {
  if (!user.value) {
    return
  }
  if (
    !window.confirm(
      `确定清空用户 ${user.value.username} 的全部剪贴板？此操作不可恢复。`,
    )
  ) {
    return
  }
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    const result = await adminUsersApi.clearClipboards(user.value.id)
    expanded.value = null
    page.value = 1
    notice.value = result.message
    await load()
  } catch (err) {
    error.value = getErrorMessage(err)
  } finally {
    busy.value = false
  }
}

async function removeUser(): Promise<void> {
  if (!user.value) {
    return
  }
  const message =
    `确定删除用户 ${user.value.username}？\n` +
    `其 ${user.value.item_count} 条剪贴板将一并删除，且不可恢复。`
  if (!window.confirm(message)) {
    return
  }
  busy.value = true
  error.value = ''
  try {
    await adminUsersApi.remove(user.value.id)
    store.setView('users')
  } catch (err) {
    error.value = getErrorMessage(err)
  } finally {
    busy.value = false
  }
}

async function openItem(id: string): Promise<void> {
  error.value = ''
  try {
    expanded.value = await adminClipboardsApi.detail(id)
  } catch (err) {
    error.value = getErrorMessage(err)
  }
}

async function deleteItem(item: AdminClipboardItem): Promise<void> {
  if (!window.confirm('确定删除这条剪贴板？此操作不可恢复。')) {
    return
  }
  error.value = ''
  notice.value = ''
  try {
    await adminClipboardsApi.remove(item.id)
    if (expanded.value?.id === item.id) {
      expanded.value = null
    }
    notice.value = '已删除剪贴板'
    if (clipboards.value && clipboards.value.items.length === 1 && page.value > 1) {
      page.value -= 1
    }
    await load()
  } catch (err) {
    error.value = getErrorMessage(err)
  }
}

function changePage(next: number): void {
  page.value = next
  expanded.value = null
  void load()
}

function changeSize(next: number): void {
  size.value = next
  page.value = 1
  expanded.value = null
  void load()
}

onMounted(load)
watch(
  () => store.selectedUserId,
  () => {
    page.value = 1
    expanded.value = null
    void load()
  },
)
</script>

<template>
  <section class="card">
    <div class="panel__head">
      <h2>用户详情</h2>
      <button type="button" class="btn btn--small" @click="store.setView('users')">
        返回用户列表
      </button>
    </div>

    <p v-if="error" class="inline-error" role="alert">{{ error }}</p>
    <p v-if="notice" class="hint" role="status">{{ notice }}</p>

    <template v-if="user">
      <div class="admin-detail">
        <dl>
          <dt>用户 ID</dt>
          <dd>{{ user.id }}</dd>
          <dt>用户名</dt>
          <dd>{{ user.username }}</dd>
          <dt>邮箱</dt>
          <dd>{{ user.email }}</dd>
          <dt>昵称</dt>
          <dd>{{ user.nickname || '—' }}</dd>
          <dt>状态</dt>
          <dd>
            <span :class="['badge', user.is_active ? 'badge--ok' : 'badge--off']">
              {{ user.is_active ? '启用' : '禁用' }}
            </span>
            <span v-if="user.is_admin" class="badge badge--admin">管理员</span>
          </dd>
          <dt>注册时间</dt>
          <dd>{{ formatDate(user.created_at) }}</dd>
          <dt>最后登录</dt>
          <dd>{{ formatDate(user.last_login_at) }}</dd>
          <dt>剪贴板条数</dt>
          <dd>{{ user.item_count }}</dd>
          <dt>最后一条记录</dt>
          <dd>{{ formatDate(user.last_item_at) }}</dd>
        </dl>

        <div class="admin-table__actions">
          <button
            v-if="!isSelf"
            type="button"
            class="btn btn--small"
            :disabled="busy"
            @click="toggleActive"
          >
            {{ user.is_active ? '禁用账号' : '启用账号' }}
          </button>
          <button
            v-if="!isSelf"
            type="button"
            class="btn btn--small"
            :disabled="busy"
            @click="resetOpen = !resetOpen"
          >
            重置密码
          </button>
          <button
            type="button"
            class="btn btn--small btn--danger"
            :disabled="busy"
            @click="clearClipboards"
          >
            清空剪贴板
          </button>
          <button
            v-if="!isSelf"
            type="button"
            class="btn btn--small btn--danger"
            :disabled="busy"
            @click="removeUser"
          >
            删除用户
          </button>
        </div>

        <form
          v-if="resetOpen"
          class="admin-form-inline"
          @submit.prevent="submitReset"
        >
          <input
            v-model="newPassword"
            type="password"
            autocomplete="new-password"
            placeholder="新密码（至少 6 位）"
          />
          <button type="submit" class="btn btn--small btn--primary" :disabled="busy">
            确认重置
          </button>
          <button
            type="button"
            class="btn btn--small"
            :disabled="busy"
            @click="resetOpen = false"
          >
            取消
          </button>
        </form>
      </div>

      <div class="panel__head" style="margin-top: 20px">
        <h2>该用户的剪贴板</h2>
        <span class="hint">共 {{ clipboards?.total ?? 0 }} 条</span>
      </div>

      <div v-if="clipboards && clipboards.items.length" class="admin-table__wrap">
        <table class="admin-table">
          <thead>
            <tr>
              <th>标题</th>
              <th>大小</th>
              <th>创建时间</th>
              <th>更新时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in clipboards.items" :key="item.id">
              <td>{{ item.title }}</td>
              <td>{{ itemSize(item) }}</td>
              <td>{{ formatDate(item.created_at) }}</td>
              <td>{{ formatDate(item.updated_at) }}</td>
              <td>
                <div class="admin-table__actions">
                  <button
                    type="button"
                    class="btn btn--small"
                    @click="openItem(item.id)"
                  >
                    查看全文
                  </button>
                  <button
                    type="button"
                    class="btn btn--small btn--danger"
                    @click="deleteItem(item)"
                  >
                    删除
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-else-if="!loading" class="admin-empty">该用户还没有剪贴板</p>

      <div v-if="expanded" style="margin-top: 12px">
        <div class="panel__head">
          <h3>{{ expanded.title }}</h3>
          <button type="button" class="btn btn--small" @click="expanded = null">
            关闭
          </button>
        </div>
        <pre class="clipboard-content">{{ expanded.content }}</pre>
      </div>

      <Pagination
        :page="page"
        :pages="clipboards?.pages ?? 0"
        :total="clipboards?.total ?? 0"
        :size="size"
        @update:page="changePage"
        @update:size="changeSize"
      />
    </template>
    <p v-else-if="!loading" class="admin-empty">请从用户列表选择用户</p>
  </section>
</template>
