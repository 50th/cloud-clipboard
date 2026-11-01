<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import LoginPanel from '@/components/LoginPanel.vue'
import ClipboardHistory from '@/components/ClipboardHistory.vue'
import InputPanel from '@/components/InputPanel.vue'
import { API_BASE_URL, getErrorMessage } from '@/api/client'
import { useNotice } from '@/composables/useNotice'
import { useWebSocket } from '@/composables/useWebSocket'
import { useClipboardStore } from '@/stores/clipboardStore'
import { useUserStore } from '@/stores/userStore'

// 提示带自动消失：登出后停在登录页，没有后续操作能覆盖它，
// 否则"已退出登录"会一直挂着（错误提示同理）。
const { notice, showNotice, clearNotice } = useNotice()

const searchInput = ref('')

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
  if (!window.confirm(`确定清空全部 ${total.value} 条记录？此操作不可撤销。`)) {
    return
  }
  try {
    const removed = await store.clearAll()
    showNotice({ kind: 'ok', text: `已清空 ${removed} 条记录` })
  } catch (error) {
    showNotice({ kind: 'err', text: getErrorMessage(error) })
  }
}
</script>

<template>
  <div class="app">
    <header class="app__header">
      <div class="app__titlebar">
        <h1>云剪贴板</h1>
        <button
          v-if="isAuthenticated"
          type="button"
          class="btn btn--small"
          @click="handleLogout"
        >
          退出登录
        </button>
      </div>
      <p class="app__subtitle">
        <!-- 后端地址是开发信息，移动端隐藏，避免把状态行挤成两行 -->
        <span class="app__backend">后端 {{ API_BASE_URL }} · </span>
        <template v-if="user">当前用户 {{ user.username }}</template>
        <template v-else>未登录</template>
        <template v-if="isAuthenticated">
          ·
          <span :class="['realtime', realtimeConnected ? 'realtime--on' : 'realtime--off']">
            {{ realtimeConnected ? '实时同步中' : '实时连接断开，正在重连…' }}
          </span>
        </template>
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
  </div>
</template>

<style scoped>
.app__titlebar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.realtime--on {
  color: var(--success);
}

.realtime--off {
  color: #b45309;
}
</style>
