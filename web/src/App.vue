<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import { API_BASE_URL, getErrorMessage } from '@/api/client'
import ClipboardHistory from '@/components/ClipboardHistory.vue'
import InputPanel from '@/components/InputPanel.vue'
import { useClipboard } from '@/composables/useClipboard'
import { useClipboardStore } from '@/stores/clipboardStore'
import { useUserStore } from '@/stores/userStore'

type Notice = { kind: 'ok' | 'err'; text: string } | null

const notice = ref<Notice>(null)
const searchInput = ref('')

// 单实例：剪贴板能力探测与「同步剪贴板」都由这一个 composable 提供
const { supported, needsManualInput, syncFromClipboard } = useClipboard()

const store = useClipboardStore()
const userStore = useUserStore()

const search = computed(() => store.search)
const total = computed(() => store.total)
const user = computed(() => userStore.user)

// 首屏：拉取当前用户 + 列表
onMounted(() => {
  void userStore.loadCurrentUser()
  void store.fetchItems()
})

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

async function handleSync() {
  const result = await syncFromClipboard()
  notice.value = { kind: result.ok ? 'ok' : 'err', text: result.message }
  return result
}

function handleNotice(next: { kind: 'ok' | 'err'; text: string }) {
  notice.value = next
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
    notice.value = { kind: 'ok', text: `已清空 ${removed} 条记录` }
  } catch (error) {
    notice.value = { kind: 'err', text: getErrorMessage(error) }
  }
}
</script>

<template>
  <div class="app">
    <header class="app__header">
      <h1>云剪贴板</h1>
      <p class="app__subtitle">
        后端 {{ API_BASE_URL }}
        <template v-if="user"> · 当前用户 {{ user.username }}</template>
        <template v-else> · 演示用户</template>
      </p>
    </header>

    <p v-if="!supported" class="warn">
      当前页面无法读取系统剪贴板（浏览器要求 https 或 localhost + 用户点击），
      可直接在右侧输入框粘贴内容。
    </p>
    <p v-else-if="needsManualInput" class="warn">
      读取剪贴板被拒绝，请检查浏览器权限，或在右侧输入框手动粘贴。
    </p>

    <p v-if="notice" :class="['notice', notice.kind === 'ok' ? 'notice--ok' : 'notice--err']">
      {{ notice.text }}
    </p>

    <!-- 左：历史记录（含搜索/排序/刷新/清空）  右：剪贴板输入 -->
    <div class="layout">
      <ClipboardHistory
        v-model:search-input="searchInput"
        @clear-all="handleClearAll"
      />
      <InputPanel :on-sync-clipboard="handleSync" @notice="handleNotice" />
    </div>

    <footer class="footer">
      <template v-if="search">筛选：{{ search }} · </template>
      阶段一 · 第 2 步：Web 端骨架与单端闭环（读取剪贴板 → 上传 → 列表展示 → 点击复制）
    </footer>
  </div>
</template>
