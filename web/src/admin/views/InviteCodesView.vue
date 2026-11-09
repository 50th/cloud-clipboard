<script setup lang="ts">
import { onMounted, ref } from 'vue'

import {
  adminInviteCodesApi,
  type AdminInviteCode,
  type AdminInviteCodeList,
  type AdminInviteCodeStatus,
} from '@/admin/api/inviteCodes.ts'
import Pagination from '@/admin/components/Pagination.vue'
import ModalDialog from '@/admin/components/ModalDialog.vue'
import { getErrorMessage } from '#src/api/client.ts'
import { writeText } from '@/utils/clipboard.ts'
import { formatDateTime } from '@/utils/format.ts'

const status = ref<AdminInviteCodeStatus>('all')
const page = ref(1)
const size = ref(10)
const data = ref<AdminInviteCodeList | null>(null)
const loading = ref(false)
const error = ref('')
const notice = ref('')
const busyId = ref<string | null>(null)

const createOpen = ref(false)
const creating = ref(false)
const form = ref({ label: '', maxUses: 1, expiresDays: 7 })

const createdCode = ref<string | null>(null)
const copied = ref(false)

const statusOptions: { value: AdminInviteCodeStatus; label: string }[] = [
  { value: 'all', label: '全部状态' },
  { value: 'active', label: '可用' },
  { value: 'exhausted', label: '已用尽' },
  { value: 'expired', label: '已过期' },
  { value: 'revoked', label: '已撤销' },
]

const statusLabels: Record<string, string> = {
  active: '可用',
  exhausted: '已用尽',
  expired: '已过期',
  revoked: '已撤销',
}

function statusClass(value: string): string {
  if (value === 'active') {
    return 'badge badge--ok'
  }
  if (value === 'exhausted') {
    return 'badge badge--warn'
  }
  return 'badge badge--off'
}

function formatDate(value: string | null | undefined): string {
  return value ? formatDateTime(value) : '—'
}

function usageText(item: AdminInviteCode): string {
  const max = item.max_uses === null ? '不限' : String(item.max_uses)
  return `${item.used_count} / ${max}`
}

async function load(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    data.value = await adminInviteCodesApi.list({
      page: page.value,
      size: size.value,
      status: status.value,
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

function openCreate(): void {
  form.value = { label: '', maxUses: 1, expiresDays: 7 }
  error.value = ''
  notice.value = ''
  createOpen.value = true
}

/** 聚焦时全选，避免在预填的 1 后面继续输入变成 12。 */
function selectAll(event: FocusEvent): void {
  const target = event.target
  if (target instanceof HTMLInputElement) {
    target.select()
  }
}

async function submitCreate(): Promise<void> {
  if (!Number.isInteger(form.value.maxUses) || form.value.maxUses < 1) {
    error.value = '使用次数必须是大于 0 的整数'
    return
  }
  creating.value = true
  error.value = ''
  try {
    const result = await adminInviteCodesApi.create({
      label: form.value.label.trim() || undefined,
      max_uses: form.value.maxUses,
      expires_days: form.value.expiresDays,
    })
    createOpen.value = false
    createdCode.value = result.code
    copied.value = false
  } catch (err) {
    error.value = getErrorMessage(err)
  } finally {
    creating.value = false
  }
}

async function copyCode(): Promise<void> {
  if (!createdCode.value) {
    return
  }
  try {
    await writeText(createdCode.value)
    copied.value = true
    window.setTimeout(() => {
      copied.value = false
    }, 2000)
  } catch (err) {
    error.value = err instanceof Error ? err.message : '复制失败'
  }
}

function closeCreated(): void {
  createdCode.value = null
  copied.value = false
  void load()
}

async function revoke(item: AdminInviteCode): Promise<void> {
  if (
    !window.confirm(
      `确定撤销邀请码 ${item.code_hint}…？撤销后无法再用于注册，此操作不可恢复。`,
    )
  ) {
    return
  }
  busyId.value = item.id
  error.value = ''
  notice.value = ''
  try {
    await adminInviteCodesApi.revoke(item.id)
    notice.value = '邀请码已撤销'
    await load()
  } catch (err) {
    error.value = getErrorMessage(err)
  } finally {
    busyId.value = null
  }
}

onMounted(load)
</script>

<template>
  <section class="card">
    <div class="panel__head">
      <h2>邀请码管理</h2>
      <div class="admin-dashboard__actions">
        <span class="hint">共 {{ data?.total ?? 0 }} 个邀请码</span>
        <button type="button" class="btn btn--small btn--primary" @click="openCreate">
          生成邀请码
        </button>
        <button type="button" class="btn btn--small" :disabled="loading" @click="load">
          刷新
        </button>
      </div>
    </div>

    <form class="admin-toolbar" @submit.prevent="applyFilters">
      <select v-model="status" aria-label="状态筛选" @change="applyFilters">
        <option v-for="item in statusOptions" :key="item.value" :value="item.value">
          {{ item.label }}
        </option>
      </select>
      <button type="submit" class="btn btn--small btn--primary">筛选</button>
    </form>

    <p v-if="error" class="inline-error" role="alert">{{ error }}</p>
    <p v-if="notice" class="hint" role="status">{{ notice }}</p>

    <div v-if="data && data.items.length" class="admin-table__wrap">
      <table class="admin-table">
        <thead>
          <tr>
            <th>前缀</th>
            <th>备注</th>
            <th>使用次数</th>
            <th>状态</th>
            <th>过期时间</th>
            <th>最近使用</th>
            <th>创建时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in data.items" :key="item.id">
            <td><code>{{ item.code_hint }}…</code></td>
            <td>{{ item.label || '—' }}</td>
            <td>{{ usageText(item) }}</td>
            <td>
              <span :class="statusClass(item.status)">
                {{ statusLabels[item.status] ?? item.status }}
              </span>
            </td>
            <td>{{ formatDate(item.expires_at) }}</td>
            <td>{{ formatDate(item.last_used_at) }}</td>
            <td>{{ formatDate(item.created_at) }}</td>
            <td>
              <div class="admin-table__actions">
                <button
                  type="button"
                  class="btn btn--small btn--danger"
                  :disabled="busyId === item.id || item.status === 'revoked'"
                  @click="revoke(item)"
                >
                  {{ item.status === 'revoked' ? '已撤销' : '撤销' }}
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <p v-else-if="!loading" class="admin-empty">没有符合条件的邀请码</p>

    <Pagination
      :page="page"
      :pages="data?.pages ?? 0"
      :total="data?.total ?? 0"
      :size="size"
      @update:page="changePage"
      @update:size="changeSize"
    />
  </section>

  <ModalDialog :open="createOpen" title="生成邀请码" @close="createOpen = false">
    <form class="admin-form" @submit.prevent="submitCreate">
      <label>
        <span>备注</span>
        <input v-model="form.label" type="text" maxlength="64" placeholder="例如：给 alice" />
      </label>
      <label>
        <span>最大使用次数（必填）</span>
        <input
          v-model.number="form.maxUses"
          type="number"
          min="1"
          max="1000"
          @focus="selectAll"
        />
      </label>
      <label>
        <span>有效期（天）</span>
        <input
          v-model.number="form.expiresDays"
          type="number"
          min="0"
          max="3650"
          @focus="selectAll"
        />
      </label>
      <p class="admin-form__hint">有效期填 0 表示不过期；使用次数用尽后邀请码自动失效。</p>
    </form>
    <template #footer>
      <button
        type="button"
        class="btn btn--small btn--primary"
        :disabled="creating"
        @click="submitCreate"
      >
        {{ creating ? '生成中…' : '生成' }}
      </button>
      <button type="button" class="btn btn--small" @click="createOpen = false">
        取消
      </button>
    </template>
  </ModalDialog>

  <ModalDialog
    :open="Boolean(createdCode)"
    title="邀请码已生成"
    @close="closeCreated"
  >
    <p class="admin-form__hint">明文只显示这一次，请立即复制并妥善保存。</p>
    <div class="invite-code">{{ createdCode }}</div>
    <template #footer>
      <button type="button" class="btn btn--small btn--primary" @click="copyCode">
        {{ copied ? '已复制' : '复制' }}
      </button>
      <button type="button" class="btn btn--small" @click="closeCreated">
        关闭
      </button>
    </template>
  </ModalDialog>
</template>
