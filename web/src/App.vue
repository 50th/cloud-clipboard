<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import LoginPanel from '@/components/LoginPanel.vue'
import ChangePasswordDialog from '@/components/ChangePasswordDialog.vue'
import ClipboardHistory from '@/components/ClipboardHistory.vue'
import InputPanel from '@/components/InputPanel.vue'
import MySharesDialog from '@/components/MySharesDialog.vue'
import ShareDialog from '@/components/ShareDialog.vue'
import { getErrorMessage, shareApi } from '@/api/client'
import type { ClipboardItem } from '@/api/client'
import { useNotice } from '@/composables/useNotice'
import { useWebSocket } from '@/composables/useWebSocket'
import { useClipboardStore } from '@/stores/clipboardStore'
import { useUserStore } from '@/stores/userStore'
import { logger } from '@/utils/logger'

// 提示带自动消失：登出后停在登录页，没有后续操作能覆盖它，
// 否则"已退出登录"会一直挂着（错误提示同理）。
const { notice, showNotice, clearNotice } = useNotice()

const searchInput = ref('')
/** 「修改密码」弹窗开关（仅登录后可用） */
const passwordDialogOpen = ref(false)
/** 创建分享弹窗：记录当前要分享的条目 */
const shareDialogOpen = ref(false)
const shareItem = ref<ClipboardItem | null>(null)
/** 「我的分享」弹窗 */
const mySharesOpen = ref(false)
/** 右上角用户名菜单 */
const userMenuOpen = ref(false)
const userMenuEl = ref<HTMLElement | null>(null)

function toggleUserMenu() {
  userMenuOpen.value = !userMenuOpen.value
}

function closeUserMenu() {
  userMenuOpen.value = false
}

/** 点右上角用户名 → 修改密码 */
function openPasswordDialog() {
  closeUserMenu()
  passwordDialogOpen.value = true
}

function onDocumentClick(event: MouseEvent) {
  if (!userMenuOpen.value) {
    return
  }
  const target = event.target
  if (!(target instanceof Node) || !userMenuEl.value?.contains(target)) {
    closeUserMenu()
  }
}

function onDocumentKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    closeUserMenu()
  }
}

onMounted(() => {
  document.addEventListener('click', onDocumentClick)
  document.addEventListener('keydown', onDocumentKeydown)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onDocumentClick)
  document.removeEventListener('keydown', onDocumentKeydown)
})

function handleShare(item: ClipboardItem) {
  shareItem.value = item
  shareDialogOpen.value = true
}

/**
 * 当前可见的视图。
 *
 * 桌面端两栏同时可见，本状态不参与布局；
 * 移动端（≤900px）通过顶部页签只显示其中一栏，默认停在「历史记录」。
 * 两栏组件始终挂载（用 CSS 隐藏），所以草稿、分页、滚动位置都不会丢。
 */
type Pane = 'input' | 'history'
const activePane = ref<Pane>('history')

function switchPane(next: Pane) {
  if (activePane.value === next) {
    return
  }
  activePane.value = next
  // 切页时清掉旧焦点：既收起软键盘，也避免焦点留在被隐藏的面板上
  const active = document.activeElement
  if (active instanceof HTMLElement) {
    active.blur()
  }
}

const store = useClipboardStore()
const userStore = useUserStore()

const search = computed(() => store.search)
const total = computed(() => store.total)
const user = computed(() => userStore.user)
const isAuthenticated = computed(() => userStore.isAuthenticated)

// 首屏：先用本地 token 恢复会话，成功后再拉列表（未登录时拉列表必然 401）
onMounted(async () => {
  await userStore.restoreSession()
  if (isAuthenticated.value) {
    await store.fetchItems()
    connect()
  }
})

// 实时同步：登录后建立 WebSocket；收到事件就静默刷新列表。
// 断线期间可能漏事件，所以重连成功后也要拉一次。
const realtimeEnabled = computed(() => isAuthenticated.value)
const {
  connected: realtimeConnected,
  connect,
  disconnect,
} = useWebSocket({
  get enabled() {
    return realtimeEnabled.value
  },
  onEvent: (envelope) => void store.applyRealtimeEvent(envelope),
  onReconnect: () => void store.fetchItems({ page: store.page, silent: true }),
})

// 登录/登出后同步剪贴板列表与实时连接，避免上一个账号的数据残留
watch(isAuthenticated, async (loggedIn) => {
  if (loggedIn) {
    // 登录成功时清掉上一条提示（通常是"已退出登录"），否则会带到新会话里
    clearNotice()
    await store.fetchItems()
    connect()
  } else {
    disconnect()
    store.reset()
    searchInput.value = ''
    activePane.value = 'history'
    userMenuOpen.value = false
  }
})

// 点历史记录 → 载入输入区；移动端同时切到「剪贴板输入」页签。
// 桌面两栏都可见，切换状态不会改变布局。
watch(
  () => store.editTicket,
  (ticket, previous) => {
    if (ticket !== previous) {
      switchPane('input')
    }
  },
)

// 搜索防抖：停止输入 300ms 后查后端
let searchTimer: ReturnType<typeof setTimeout> | undefined
watch(searchInput, (value) => {
  if (searchTimer !== undefined) {
    clearTimeout(searchTimer)
  }
  searchTimer = setTimeout(() => {
    void store.setSearch(value)
  }, 300)
})

function handleLogout() {
  closeUserMenu()
  userStore.logout()
  showNotice({ kind: 'ok', text: '已退出登录' })
}

function handleNotice(next: { kind: 'ok' | 'err'; text: string }) {
  showNotice(next)
}

async function handleClearAll() {
  if (total.value === 0) {
    return
  }

  // 清空会级联删除分享；先查当前用户的有效分享总数。
  let activeShares = 0
  try {
    activeShares = (await shareApi.list({ status: 'active', size: 1 })).total
  } catch (error) {
    logger.debug('查询有效分享总数失败，按 0 处理', error)
  }

  const message =
    activeShares > 0
      ? `你有 ${activeShares} 个有效分享，清空后这些链接将立即失效。确定清空？`
      : `确定清空全部 ${total.value} 条记录？此操作不可撤销。`
  if (!window.confirm(message)) {
    return
  }
  try {
    const removed = await store.clearAll()
    showNotice({ kind: 'ok', text: `已清空 ${removed} 条记录` })
  } catch (error) {
    logger.error('清空剪贴板失败', error)
    showNotice({ kind: 'err', text: getErrorMessage(error) })
  }
}
</script>

<template>
  <div class="app">
    <header class="app__header">
      <div class="app__titlebar">
        <h1>云剪贴板</h1>
        <div v-if="isAuthenticated" class="app__actions">
          <button
            type="button"
            class="btn btn--small"
            @click="mySharesOpen = true"
          >
            我的分享
          </button>
          <div ref="userMenuEl" class="user-menu">
            <button
              type="button"
              class="user-menu__trigger"
              aria-haspopup="menu"
              :aria-expanded="userMenuOpen"
              @click="toggleUserMenu"
            >
              {{ user?.username ?? '账号' }}
              <span class="user-menu__caret" aria-hidden="true">▾</span>
            </button>
            <div v-if="userMenuOpen" class="user-menu__panel" role="menu">
              <button
                type="button"
                class="user-menu__item"
                role="menuitem"
                @click="openPasswordDialog"
              >
                修改密码
              </button>
              <button
                type="button"
                class="user-menu__item user-menu__item--danger"
                role="menuitem"
                @click="handleLogout"
              >
                退出登录
              </button>
            </div>
          </div>
        </div>
      </div>
      <p v-if="isAuthenticated" class="app__subtitle">
        <span :class="['realtime', realtimeConnected ? 'realtime--on' : 'realtime--off']">
          {{ realtimeConnected ? '实时同步中' : '实时连接断开，正在重连…' }}
        </span>
      </p>
    </header>

    <!--
      提示是**固定悬浮**的（见 styles.css 的 .notice）：不参与文档流，
      出现与消失都不会顶动下面的输入区。
    -->
    <Transition name="notice-fade">
      <p
        v-if="notice"
        :class="['notice', notice.kind === 'ok' ? 'notice--ok' : 'notice--err']"
        role="status"
        aria-live="polite"
      >
        {{ notice.text }}
      </p>
    </Transition>

    <!-- 未登录：只显示登录/注册；JWT 未接入前这里曾是"演示用户"兜底入口 -->
    <template v-if="userStore.restoring">
      <p class="loading">正在恢复登录状态…</p>
    </template>

    <LoginPanel v-else-if="!isAuthenticated" @notice="handleNotice" />

    <template v-else>
      <!--
        移动端页签：桌面端由 CSS 隐藏，两栏同时可见。
        两个面板始终挂载，切换只是显示/隐藏，不会重建输入区或列表。
      -->
      <nav class="pane-tabs" role="tablist" aria-label="视图切换">
        <button
          type="button"
          class="pane-tabs__tab"
          :class="{ 'pane-tabs__tab--active': activePane === 'history' }"
          role="tab"
          :aria-selected="activePane === 'history'"
          @click="switchPane('history')"
        >
          历史记录
          <span v-if="total > 0" class="pane-tabs__badge">{{ total }}</span>
        </button>
        <button
          type="button"
          class="pane-tabs__tab"
          :class="{ 'pane-tabs__tab--active': activePane === 'input' }"
          role="tab"
          :aria-selected="activePane === 'input'"
          @click="switchPane('input')"
        >
          剪贴板输入
        </button>
      </nav>

      <!-- 桌面：左历史 右输入；移动：由顶部页签一次显示一栏 -->
      <div class="layout">
        <div
          class="layout__pane"
          :class="{ 'layout__pane--active': activePane === 'history' }"
        >
          <ClipboardHistory
            v-model:search-input="searchInput"
            @clear-all="handleClearAll"
            @share="handleShare"
          />
        </div>
        <div
          class="layout__pane"
          :class="{ 'layout__pane--active': activePane === 'input' }"
        >
          <InputPanel @notice="handleNotice" />
        </div>
      </div>

      <footer class="footer">
        <template v-if="search">筛选：{{ search }} · </template>
        文字剪贴板 v1.0.0
      </footer>
    </template>

    <ChangePasswordDialog
      v-if="isAuthenticated"
      :open="passwordDialogOpen"
      :username="user?.username ?? ''"
      @close="passwordDialogOpen = false"
      @notice="handleNotice"
    />

    <ShareDialog
      v-if="isAuthenticated"
      :open="shareDialogOpen"
      :item="shareItem"
      @close="shareDialogOpen = false"
      @notice="handleNotice"
    />

    <MySharesDialog
      v-if="isAuthenticated"
      :open="mySharesOpen"
      @close="mySharesOpen = false"
      @notice="handleNotice"
    />
  </div>
</template>

<style scoped>
.app__titlebar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.app__actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* ---------- 右上角用户名下拉菜单 ---------- */
.user-menu {
  position: relative;
}

.user-menu__trigger {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  max-width: 180px;
  padding: 4px 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: #fff;
  color: var(--text);
  font: inherit;
  font-size: 12px;
  cursor: pointer;
}

.user-menu__trigger:hover {
  background: #f3f4f6;
}

.user-menu__caret {
  color: var(--text-muted);
  font-size: 10px;
}

.user-menu__panel {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  z-index: 60;
  min-width: 148px;
  padding: 6px;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 10px;
  box-shadow: 0 12px 30px rgba(15, 23, 42, 0.18);
}

.user-menu__item {
  display: block;
  width: 100%;
  padding: 8px 10px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--text);
  font: inherit;
  font-size: 13px;
  text-align: left;
  cursor: pointer;
}

.user-menu__item:hover {
  background: #f3f4f6;
}

.user-menu__item--danger {
  color: var(--danger);
}

@media (max-width: 900px) {
  .user-menu__trigger {
    min-height: 36px;
    font-size: 13px;
  }
}

.realtime--on {
  color: var(--success);
}

.realtime--off {
  color: #b45309;
}
</style>
