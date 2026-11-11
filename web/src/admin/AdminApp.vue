<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'

import LoginView from '@/admin/views/LoginView.vue'
import DashboardView from '@/admin/views/DashboardView.vue'
import UsersView from '@/admin/views/UsersView.vue'
import UserDetailView from '@/admin/views/UserDetailView.vue'
import ClipboardsView from '@/admin/views/ClipboardsView.vue'
import InviteCodesView from '@/admin/views/InviteCodesView.vue'
import AuditLogsView from '@/admin/views/AuditLogsView.vue'
import ChangePasswordDialog from '@/admin/components/ChangePasswordDialog.vue'
import { useAdminStore } from '@/admin/stores/adminStore'
import type { AdminView } from '@/admin/stores/adminStore'

const store = useAdminStore()

/** 修改密码成功后回到登录页时展示的提示。 */
const loginNotice = ref('')
const passwordDialogOpen = ref(false)

watch(
  () => store.isAuthenticated,
  (authenticated) => {
    if (authenticated) {
      loginNotice.value = ''
      passwordDialogOpen.value = false
    }
  },
)

const navItems: { key: AdminView; label: string }[] = [
  { key: 'dashboard', label: '概览' },
  { key: 'users', label: '用户管理' },
  { key: 'clipboards', label: '剪贴板管理' },
  { key: 'inviteCodes', label: '邀请码' },
  { key: 'audit', label: '操作日志' },
]

onMounted(() => {
  void store.restoreSession()
})

function isActive(key: AdminView): boolean {
  if (key === 'users') {
    return store.activeView === 'users' || store.activeView === 'userDetail'
  }
  return store.activeView === key
}
</script>

<template>
  <div class="admin">
    <header class="admin__header">
      <div>
        <h1>云剪贴板 · 后台管理</h1>
        <p v-if="store.user" class="admin__subtitle">
          当前管理员 {{ store.user.username }} · {{ store.user.email }}
        </p>
      </div>
      <div v-if="store.isAuthenticated" class="admin__header-actions">
        <button
          type="button"
          class="btn btn--small"
          @click="passwordDialogOpen = true"
        >
          修改密码
        </button>
        <button type="button" class="btn btn--small" @click="store.logout()">
          退出登录
        </button>
      </div>
    </header>

    <template v-if="store.restoring">
      <p class="loading">正在恢复管理会话…</p>
    </template>

    <LoginView v-else-if="!store.isAuthenticated" :notice="loginNotice" />

    <template v-else>
      <nav class="admin__nav" aria-label="管理视图切换">
        <button
          v-for="item in navItems"
          :key="item.key"
          type="button"
          class="admin__nav-item"
          :class="{ 'admin__nav-item--active': isActive(item.key) }"
          @click="store.setView(item.key)"
        >
          {{ item.label }}
        </button>
      </nav>

      <main class="admin__body">
        <DashboardView v-if="store.activeView === 'dashboard'" />
        <UsersView v-else-if="store.activeView === 'users'" />
        <UserDetailView v-else-if="store.activeView === 'userDetail'" />
        <ClipboardsView v-else-if="store.activeView === 'clipboards'" />
        <InviteCodesView v-else-if="store.activeView === 'inviteCodes'" />
        <AuditLogsView v-else />
      </main>
    </template>

    <ChangePasswordDialog
      v-if="store.isAuthenticated"
      :open="passwordDialogOpen"
      @close="passwordDialogOpen = false"
      @changed="loginNotice = '密码已修改，请使用新密码重新登录'"
    />
  </div>
</template>
