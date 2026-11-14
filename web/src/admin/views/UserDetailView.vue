<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import { adminUsersApi } from '@/admin/api/users.ts'
import { adminShareSettingsApi } from '@/admin/api/settings.ts'
import {
  adminUserSharesApi,
  type AdminUserShareList,
} from '@/admin/api/userShares.ts'
import { adminClipboardsApi } from '@/admin/api/clipboards.ts'
import type {
  AdminClipboardItem,
  AdminClipboardItemList,
  AdminUser,
} from '@/admin/api/client.ts'
import ModalDialog from '@/admin/components/ModalDialog.vue'
import Pagination from '@/admin/components/Pagination.vue'
import { useAdminStore } from '@/admin/stores/adminStore'
import { getErrorMessage } from '#src/api/client.ts'
import { validatePassword } from '#src/utils/passwordPolicy.ts'
import { formatBytes, formatDateTime } from '@/utils/format.ts'

const store = useAdminStore()

const user = ref<AdminUser | null>(null)
/** 剪贴板 / 分享记录都在模态框中展示 */
const clipboardsOpen = ref(false)
const clipboards = ref<AdminClipboardItemList | null>(null)
const clipboardPage = ref(1)
const clipboardSize = ref(10)
const clipboardLoading = ref(false)
const expanded = ref<AdminClipboardItem | null>(null)

const sharesOpen = ref(false)
const shares = ref<AdminUserShareList | null>(null)
const sharePage = ref(1)
const shareSize = ref(10)
const shareLoading = ref(false)

const loading = ref(false)
const error = ref('')
const notice = ref('')
const busy = ref(false)

const resetOpen = ref(false)
const newPassword = ref('')

/** 分享上限：单独设置，留空表示跟随全局默认值 */
const globalShareLimit = ref<number | null>(null)
const shareLimitOpen = ref(false)
/** 数字输入框会由 Vue 自动转成 number；空字符串表示“跟随全局” */
const shareLimitInput = ref<number | ''>('')

const isSelf = computed(() => user.value?.id === store.user?.id)

const shareLimitText = computed(() => {
  if (!user.value) {
    return '—'
  }
  if (user.value.share_limit !== null && user.value.share_limit !== undefined) {
    return String(user.value.share_limit)
  }
  return globalShareLimit.value === null
    ? '跟随全局'
    : `跟随全局（${globalShareLimit.value}）`
})

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
    const [detail, settings] = await Promise.all([
      adminUsersApi.detail(id),
      adminShareSettingsApi.get().catch(() => null),
    ])
    user.value = detail
    globalShareLimit.value = settings ? settings.user_share_limit : null
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

function openShareLimit(): void {
  shareLimitInput.value =
    user.value?.share_limit !== null && user.value?.share_limit !== undefined
      ? user.value.share_limit
      : ''
  shareLimitOpen.value = true
  error.value = ''
  notice.value = ''
}

async function submitShareLimit(): Promise<void> {
  if (!user.value) {
    return
  }
  const raw = shareLimitInput.value
  if (raw !== '' && (!Number.isInteger(raw) || raw < 1 || raw > 10_000)) {
    error.value = '分享上限需为 1–10000 的整数；留空表示跟随全局'
    return
  }

  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    await adminUsersApi.update(user.value.id, {
      share_limit: raw === '' ? null : raw,
    })
    notice.value =
      raw === '' ? '已清除单独限额，改为跟随全局' : `分享上限已设为 ${raw}`
    shareLimitOpen.value = false
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
  const policyError = validatePassword(newPassword.value, user.value.username)
  if (policyError) {
    error.value = policyError
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
    clipboardPage.value = 1
    expanded.value = null
    notice.value = result.message
    await load()
    if (clipboardsOpen.value) {
      await loadClipboards()
    }
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
    if (
      clipboards.value &&
      clipboards.value.items.length === 1 &&
      clipboardPage.value > 1
    ) {
      clipboardPage.value -= 1
    }
    await load()
    await loadClipboards()
  } catch (err) {
    error.value = getErrorMessage(err)
  }
}

/* ---------- 剪贴板模态框 ---------- */

async function loadClipboards(): Promise<void> {
  if (!user.value) {
    return
  }
  clipboardLoading.value = true
  error.value = ''
  try {
    clipboards.value = await adminClipboardsApi.list({
      user_id: user.value.id,
      page: clipboardPage.value,
      size: clipboardSize.value,
      sort_by: 'updated_at',
      order: 'desc',
    })
  } catch (err) {
    error.value = getErrorMessage(err)
  } finally {
    clipboardLoading.value = false
  }
}

async function openClipboards(): Promise<void> {
  clipboardsOpen.value = true
  clipboardPage.value = 1
  clipboards.value = null
  expanded.value = null
  await loadClipboards()
}

function closeClipboards(): void {
  clipboardsOpen.value = false
  clipboards.value = null
  expanded.value = null
}

function changeClipboardPage(next: number): void {
  clipboardPage.value = next
  expanded.value = null
  void loadClipboards()
}

function changeClipboardSize(next: number): void {
  clipboardSize.value = next
  clipboardPage.value = 1
  expanded.value = null
  void loadClipboards()
}

/* ---------- 分享记录模态框 ---------- */

async function loadShares(): Promise<void> {
  if (!user.value) {
    return
  }
  shareLoading.value = true
  error.value = ''
  try {
    shares.value = await adminUserSharesApi.list(user.value.id, {
      page: sharePage.value,
      size: shareSize.value,
    })
  } catch (err) {
    error.value = getErrorMessage(err)
  } finally {
    shareLoading.value = false
  }
}

async function openShares(): Promise<void> {
  sharesOpen.value = true
  sharePage.value = 1
  shares.value = null
  await loadShares()
}

function closeShares(): void {
  sharesOpen.value = false
  shares.value = null
}

function changeSharePage(next: number): void {
  sharePage.value = next
  void loadShares()
}

function changeShareSize(next: number): void {
  shareSize.value = next
  sharePage.value = 1
  void loadShares()
}

const shareStatusLabels: Record<string, string> = {
  active: '有效',
  expired: '已过期',
  exhausted: '次数用尽',
  revoked: '已撤销',
}

function shareStatusLabel(status: string): string {
  return shareStatusLabels[status] ?? status
}

function shareStatusClass(status: string): string {
  if (status === 'active') {
    return 'badge badge--ok'
  }
  if (status === 'revoked') {
    return 'badge badge--off'
  }
  return 'badge badge--warn'
}

onMounted(load)
watch(
  () => store.selectedUserId,
  () => {
    clipboardsOpen.value = false
    sharesOpen.value = false
    clipboards.value = null
    shares.value = null
    expanded.value = null
    clipboardPage.value = 1
    sharePage.value = 1
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
          <dt>分享上限</dt>
          <dd>{{ shareLimitText }}</dd>
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
            class="btn btn--small"
            :disabled="busy"
            @click="openShareLimit"
          >
            设置分享上限
          </button>
          <button type="button" class="btn btn--small" @click="openClipboards">
            查看剪贴板
          </button>
          <button type="button" class="btn btn--small" @click="openShares">
            查看分享记录
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
            placeholder="新密码（至少 8 位，含字母和数字）"
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

        <form
          v-if="shareLimitOpen"
          class="admin-form-inline"
          @submit.prevent="submitShareLimit"
        >
          <input
            v-model="shareLimitInput"
            type="number"
            min="1"
            max="10000"
            placeholder="1–10000，留空表示跟随全局"
          />
          <button type="submit" class="btn btn--small btn--primary" :disabled="busy">
            保存分享上限
          </button>
          <button
            type="button"
            class="btn btn--small"
            :disabled="busy"
            @click="shareLimitOpen = false"
          >
            取消
          </button>
        </form>
      </div>
    </template>
    <p v-else-if="!loading" class="admin-empty">请从用户列表选择用户</p>
  </section>

  <!-- 剪贴板：模态框展示 -->
  <ModalDialog
    :open="clipboardsOpen"
    :title="`剪贴板 · ${user?.username ?? ''}`"
    @close="closeClipboards"
  >
    <p class="admin-form__hint">共 {{ clipboards?.total ?? 0 }} 条</p>

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
    <p v-else-if="!clipboardLoading" class="admin-empty">该用户还没有剪贴板</p>

    <Pagination
      :page="clipboardPage"
      :pages="clipboards?.pages ?? 0"
      :total="clipboards?.total ?? 0"
      :size="clipboardSize"
      @update:page="changeClipboardPage"
      @update:size="changeClipboardSize"
    />

    <template #footer>
      <button type="button" class="btn btn--small" @click="closeClipboards">
        关闭
      </button>
    </template>
  </ModalDialog>

  <!-- 剪贴板全文：嵌套模态框 -->
  <ModalDialog
    :open="Boolean(expanded)"
    :title="expanded?.title ?? '剪贴板全文'"
    @close="expanded = null"
  >
    <pre class="clipboard-content">{{ expanded?.content }}</pre>
    <template #footer>
      <button type="button" class="btn btn--small" @click="expanded = null">
        关闭
      </button>
    </template>
  </ModalDialog>

  <!-- 分享记录：模态框展示 -->
  <ModalDialog
    :open="sharesOpen"
    :title="`分享记录 · ${user?.username ?? ''}`"
    @close="closeShares"
  >
    <p class="admin-form__hint">共 {{ shares?.total ?? 0 }} 个分享</p>

    <div v-if="shares && shares.items.length" class="admin-table__wrap">
      <table class="admin-table">
        <thead>
          <tr>
            <th>标题</th>
            <th>模式</th>
            <th>状态</th>
            <th>查看次数</th>
            <th>到期时间</th>
            <th>创建时间</th>
            <th>密码</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="share in shares.items" :key="share.id">
            <td class="share-title-cell" :title="share.title">
              {{ share.title }}
            </td>
            <td>{{ share.mode === 'live' ? '跟随最新' : '快照' }}</td>
            <td>
              <span :class="shareStatusClass(share.status)">
                {{ shareStatusLabel(share.status) }}
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
          </tr>
        </tbody>
      </table>
    </div>
    <p v-else-if="!shareLoading" class="admin-empty">该用户还没有分享</p>

    <Pagination
      :page="sharePage"
      :pages="shares?.pages ?? 0"
      :total="shares?.total ?? 0"
      :size="shareSize"
      @update:page="changeSharePage"
      @update:size="changeShareSize"
    />

    <template #footer>
      <button type="button" class="btn btn--small" @click="closeShares">
        关闭
      </button>
    </template>
  </ModalDialog>
</template>

<style scoped>
.share-title-cell {
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
