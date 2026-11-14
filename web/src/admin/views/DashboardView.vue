<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { adminStatsApi } from '@/admin/api/stats.ts'
import type { AdminStats } from '@/admin/api/client.ts'
import { useAdminStore } from '@/admin/stores/adminStore'
import type { AdminView } from '@/admin/stores/adminStore'
import { getErrorMessage } from '#src/api/client.ts'
import { formatBytes } from '@/utils/format.ts'

const store = useAdminStore()

const stats = ref<AdminStats | null>(null)
const loading = ref(false)
const error = ref('')

async function load(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    stats.value = await adminStatsApi.get()
  } catch (err) {
    error.value = getErrorMessage(err)
  } finally {
    loading.value = false
  }
}

onMounted(load)

/** 每张卡片都能跳到对应管理页面（无 view 的仅展示数值）。 */
const cards: {
  key: keyof Omit<AdminStats, 'total_bytes'>
  label: string
  view?: AdminView
}[] = [
  { key: 'user_count', label: '用户总数', view: 'users' },
  { key: 'active_user_count', label: '启用用户', view: 'users' },
  { key: 'admin_count', label: '管理员', view: 'users' },
  { key: 'item_count', label: '剪贴板条数', view: 'clipboards' },
  { key: 'new_users_7d', label: '近 7 天新增用户', view: 'users' },
  { key: 'new_items_7d', label: '近 7 天新增记录', view: 'clipboards' },
  { key: 'share_count', label: '分享总数', view: 'shares' },
  { key: 'active_share_count', label: '有效分享', view: 'shares' },
  { key: 'invite_code_count', label: '邀请码总数', view: 'inviteCodes' },
  { key: 'active_invite_count', label: '可用邀请码', view: 'inviteCodes' },
  { key: 'invite_used_count', label: '邀请码使用次数', view: 'inviteCodes' },
]

function valueOf(key: (typeof cards)[number]['key']): number {
  return stats.value ? Number(stats.value[key] ?? 0) : 0
}

function go(view: AdminView): void {
  store.setView(view)
}
</script>

<template>
  <section class="card">
    <div class="panel__head">
      <h2>概览</h2>
      <div class="admin-dashboard__actions">
        <span class="hint">可点击的卡片进入对应页面</span>
        <button type="button" class="btn btn--small" :disabled="loading" @click="load">
          {{ loading ? '刷新中…' : '刷新' }}
        </button>
      </div>
    </div>

    <p v-if="error" class="inline-error" role="alert">{{ error }}</p>

    <template v-if="stats">
      <div class="admin-grid">
        <button
          v-for="card in cards"
          :key="card.key"
          type="button"
          class="stat-card"
          :class="{ 'stat-card--link': Boolean(card.view) }"
          :disabled="!card.view"
          @click="card.view ? go(card.view) : undefined"
        >
          <span class="stat-card__label">{{ card.label }}</span>
          <strong class="stat-card__value">{{ valueOf(card.key) }}</strong>
        </button>
        <button
          type="button"
          class="stat-card stat-card--link"
          @click="go('clipboards')"
        >
          <span class="stat-card__label">内容总占用</span>
          <strong class="stat-card__value">{{ formatBytes(stats.total_bytes) }}</strong>
        </button>
      </div>
    </template>
    <p v-else-if="!loading" class="admin-empty">暂无统计数据</p>
  </section>
</template>
