<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'

import { getErrorMessage } from '@/api/client'
import { useAutoSave } from '@/composables/useAutoSave'
import { useClipboardStore } from '@/stores/clipboardStore'
import { byteSize, formatBytes } from '@/utils/format'

const props = defineProps<{
  /** 读取系统剪贴板并上传（由 App 提供，内部统一处理提示） */
  onSyncClipboard: () => Promise<{ ok: boolean; message: string }>
}>()

const emit = defineEmits<{
  (e: 'notice', notice: { kind: 'ok' | 'err'; text: string }): void
}>()

const store = useClipboardStore()

/** 停止输入多久后自动保存（毫秒）。2 秒比 1.5 秒更能避开打字中的自然停顿 */
const AUTO_SAVE_DELAY = 2000

const title = ref('')
const text = ref('')
const autoSave = ref(true)

const contentSize = computed(() => (text.value ? formatBytes(byteSize(text.value)) : '0 B'))

const { saving, error: autoSaveError, lastSaved, pending, remainingMs, progress, markSaved, saveNow } =
  useAutoSave({
    text,
    extra: title,
    enabled: autoSave,
    delay: AUTO_SAVE_DELAY,
    onSave: async () => {
      try {
        // 自动保存复用同一条草稿记录，不会每个中间态都新建一行
        const { item } = await store.saveDraft(text.value, title.value)
        const at = new Date().toLocaleTimeString('zh-CN', { hour12: false })
        emit('notice', { kind: 'ok', text: `已自动保存（${at}）：${item.title}` })
      } catch (err) {
        // 抛回给 useAutoSave 记录 error，再由下面的 watch 统一提示
        throw new Error(getErrorMessage(err))
      }
    },
  })

// 自动保存失败时提示一次
watch(autoSaveError, (message) => {
  if (message) {
    emit('notice', { kind: 'err', text: `自动保存失败：${message}` })
  }
})

/** 正文编辑框的 DOM 引用：载入记录后聚焦，方便直接改 */
const editorRef = ref<HTMLTextAreaElement | null>(null)

/** 正在编辑的那条记录的标题（仅用于提示"在改哪一条"） */
const editingTitle = ref('')

/**
 * 响应「从列表点开一条记录来编辑」。
 *
 * ⚠️ 顺序很关键：**先把当前未保存的内容落盘，再切换编辑目标**。
 * 反过来会让输入框里那几个还没到自动保存时机的字，跟着旧草稿一起丢掉。
 */
watch(
  () => store.editTicket,
  async () => {
    if (pending.value) {
      await saveNow()
    }

    const item = store.applyRequestedEdit()
    if (!item) {
      return
    }

    title.value = item.title
    text.value = item.content
    editingTitle.value = item.title
    // 内容与库里一致，标记为已保存，否则会立刻触发一次无意义的自动保存
    markSaved(item.content)

    await nextTick()
    editorRef.value?.focus()
  },
)

/**
 * 清空输入框。
 *
 * ⚠️ **不解除草稿关联**：清空只是清界面，用户的预期是"继续编辑同一条"。
 * 想新开一条请点「新建剪贴板」。
 * `markSaved('')` 让自动保存不会把空内容存进去，而重新输入后会正常再触发保存。
 */
function clearInput() {
  title.value = ''
  text.value = ''
  markSaved('')
}

/**
 * 显式开启一条新剪贴板。
 *
 * **只有这个动作会解除草稿关联**——此后输入的内容会另起一行，
 * 而不是继续更新上一条记录。
 */
function handleStartNew() {
  store.startNewDraft()
  markSaved('')
  title.value = ''
  text.value = ''
  editingTitle.value = ''
  emit('notice', { kind: 'ok', text: '已开启新剪贴板，接下来输入的内容会另起一条记录' })
}

async function handleManualUpload() {
  if (text.value.trim() === '') {
    return
  }
  try {
    const { item, deduped } = await store.uploadText(text.value, title.value)
    // 手动上传成功后标记已保存，避免自动保存重复上传同一内容
    markSaved(text.value)
    emit('notice', {
      kind: 'ok',
      text: deduped ? `内容已存在，已刷新时间戳：${item.title}` : `已上传：${item.title}`,
    })
  } catch (err) {
    emit('notice', { kind: 'err', text: getErrorMessage(err) })
  }
}

async function handleSyncClipboard() {
  const result = await props.onSyncClipboard()
  if (result.ok) {
    // 系统剪贴板内容已入库，把当前输入标记为已保存，避免自动保存再传一遍
    markSaved(text.value)
  }
}

/** Ctrl/Cmd + Enter 快速上传 */
function onKeydown(event: KeyboardEvent) {
  if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
    event.preventDefault()
    void handleManualUpload()
  }
}

/**
 * 状态种类。
 *
 * ⚠️ `pending` 必须来自 composable，**不能**用 `lastSaved === null` 判断——
 * 那样首次保存成功后再编辑，状态会一直显示旧的「已自动保存」时间。
 */
type StatusKind = 'off' | 'saving' | 'idle' | 'pending' | 'saved'

const statusKind = computed<StatusKind>(() => {
  if (!autoSave.value) {
    return 'off'
  }
  if (saving.value) {
    return 'saving'
  }
  if (pending.value) {
    return 'pending'
  }
  if (text.value.trim() === '' || lastSaved.value === null) {
    return 'idle'
  }
  return 'saved'
})

/** 剩余秒数。向上取整，避免出现「0 秒后自动保存」却还没保存的尴尬 */
const remainingSeconds = computed(() => Math.ceil(remainingMs.value / 1000))

/** 倒计时进度条宽度 */
const progressWidth = computed(() => `${Math.round(progress.value * 100)}%`)

const statusText = computed(() => {
  switch (statusKind.value) {
    case 'off':
      return '已关闭'
    case 'saving':
      return '保存中…'
    case 'pending':
      return `${remainingSeconds.value} 秒后自动保存`
    case 'saved':
      return `已自动保存 ${new Date(lastSaved.value ?? 0).toLocaleTimeString('zh-CN', {
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      })}`
    default:
      return '等待输入'
  }
})
</script>

<template>
  <section class="card panel panel--input">
    <div class="panel__head panel__head--split">
      <h2>剪贴板输入</h2>
      <span class="hint">Ctrl+Enter 快速上传</span>
    </div>

    <!--
      正在编辑已有记录时给出明确提示：否则用户不知道"上传"会更新那一条
      而不是新建，容易误改历史记录。
    -->
    <div v-if="store.editingId" class="editing-banner">
      <span class="editing-banner__text">
        ✎ 正在编辑已有记录<template v-if="editingTitle">：{{ editingTitle }}</template>
        <span class="editing-banner__sub">（保存会更新这一条，不会新建）</span>
      </span>
      <button type="button" class="btn btn--small" @click="handleStartNew">改为新建</button>
    </div>

    <label class="field field--tight">
      <span>标题（留空将自动生成，如「demo · 10-05 21:56」，按本机时区）</span>
      <input
        v-model="title"
        maxlength="200"
        placeholder="不填也可以，会自动生成标题"
      />
    </label>

    <label class="field field--grow">
      <span>内容（{{ contentSize }}）</span>
      <textarea
        ref="editorRef"
        v-model="text"
        class="editor"
        placeholder="在这里输入或粘贴内容，也可以点下面的「同步剪贴板」直接抓取系统剪贴板；点左侧历史记录可载入编辑"
        @keydown="onKeydown"
      />
    </label>

    <div class="actions actions--wrap">
      <button
        type="button"
        class="btn btn--primary"
        :disabled="text.trim() === ''"
        @click="handleManualUpload"
      >
        上传
      </button>
      <button type="button" class="btn btn--primary" @click="handleSyncClipboard">
        同步剪贴板
      </button>
      <button type="button" class="btn" @click="handleStartNew">
        ＋ 新建剪贴板
      </button>
      <button
        type="button"
        class="btn"
        :disabled="text === '' && title === ''"
        @click="clearInput"
      >
        清空输入
      </button>
    </div>

    <div class="autosave">
      <label class="switch">
        <input v-model="autoSave" type="checkbox" />
        <span>自动保存（停止输入 {{ AUTO_SAVE_DELAY / 1000 }} 秒后保存到当前草稿）</span>
      </label>

      <span class="autosave__right">
        <!--
          按钮常驻（仅禁用）而不是条件渲染：有条件出现会让这一行宽度跳动。
        -->
        <button
          type="button"
          class="btn btn--small"
          :disabled="statusKind !== 'pending'"
          :title="statusKind === 'pending' ? '跳过剩余等待，立刻保存' : '没有待保存的改动'"
          @click="saveNow"
        >
          立即保存
        </button>
        <span
          class="autosave__status"
          :class="{
            'autosave__status--saved': statusKind === 'saved',
            'autosave__status--pending': statusKind === 'pending',
          }"
        >
          <template v-if="statusKind === 'saving'">⏳ </template>
          <template v-else-if="statusKind === 'saved'">✓ </template>
          {{ statusText }}
        </span>
      </span>

      <!-- 倒计时进度条：绝对定位，不占布局高度 -->
      <span v-if="statusKind === 'pending'" class="autosave__progress" aria-hidden="true">
        <span class="autosave__progress-fill" :style="{ width: progressWidth }" />
      </span>
    </div>
  </section>
</template>

<style scoped>
/* 布局与配色在全局 styles.css 里（设计系统集中管理），这里只放组件特有的部分 */
.autosave__right {
  display: flex;
  align-items: center;
  gap: 10px;
}
</style>
