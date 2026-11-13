<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'

import { getErrorMessage } from '@/api/client'
import { useAutoSave } from '@/composables/useAutoSave'
import { useClipboardStore } from '@/stores/clipboardStore'
import { byteSize, formatBytes } from '@/utils/format'

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

/**
 * 自动保存成功后待回填到标题栏的标题。
 *
 * 标题留空时由服务端自动生成，不回填的话输入框一直空着，
 * 用户看不到这条记录实际叫什么。回填要等保存结束再做（见下方 watch(saving)）。
 */
let pendingTitleBackfill: {
  title: string
  submittedText: string
  submittedTitle: string
} | null = null

const { saving, error: autoSaveError, lastSaved, pending, remainingMs, progress, markSaved, saveNow } =
  useAutoSave({
    text,
    extra: title,
    enabled: autoSave,
    delay: AUTO_SAVE_DELAY,
    onSave: async () => {
      // 记录提交时的值：请求期间用户可能继续输入
      const submittedText = text.value
      const submittedTitle = title.value
      try {
        // 自动保存复用同一条草稿记录，不会每个中间态都新建一行
        const { item } = await store.saveDraft(submittedText, submittedTitle)
        if (submittedTitle.trim() === '' && item.title) {
          pendingTitleBackfill = { title: item.title, submittedText, submittedTitle }
        }
        const at = new Date().toLocaleTimeString('zh-CN', { hour12: false })
        emit('notice', { kind: 'ok', text: `已自动保存（${at}）：${item.title}` })
      } catch (err) {
        // 抛回给 useAutoSave 记录 error，再由下面的 watch 统一提示
        throw new Error(getErrorMessage(err))
      }
    },
  })

/**
 * 保存结束后把服务端生成的标题回填到标题栏。
 *
 * ⚠️ 必须等 `saving` 落回 false 再改标题：保存过程中改标题会被
 * useAutoSave 判定为新的未保存改动，多触发一次保存。
 */
watch(saving, (isSaving) => {
  if (isSaving || !pendingTitleBackfill) {
    return
  }
  const { title: generated, submittedText, submittedTitle } = pendingTitleBackfill
  pendingTitleBackfill = null
  // 保存期间用户自己填了标题：以用户输入为准，不覆盖
  if (title.value !== submittedTitle) {
    return
  }
  title.value = generated
  // 基线按「提交时的正文 + 回填后的标题」重建，避免回填本身触发一次多余的自动保存
  markSaved(submittedText)
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

    // 列表里的那条可能已过期：载入前先取一次最新详情
    const ticket = store.editTicket
    const hasRequest = await store.refreshRequestedEdit()
    // 等待详情期间用户又点了另一条：交给那次请求处理，避免把旧请求应用到新目标上
    if (ticket !== store.editTicket) {
      return
    }
    if (!hasRequest) {
      emit('notice', { kind: 'err', text: '载入失败：该记录可能已被删除' })
      return
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
 * 清空正文，**保留标题**。
 *
 * ⚠️ **不解除草稿关联**：清空只是清正文，用户的预期是"继续编辑同一条"。
 * 想新开一条请点「新建剪贴板」。
 * `markSaved('')` 让自动保存不会把空内容存进去，而重新输入后会正常再触发保存。
 */
function clearInput() {
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

/**
 * 其他设备改动了正在编辑的这一条：给出提示，由用户决定是否载入最新。
 *
 * 本机保存是后写覆盖，没有版本号校验；提示能避免用户毫不知情地覆盖对方内容。
 */
watch(
  () => store.remoteUpdate,
  (item) => {
    if (!item) {
      return
    }
    // 本地输入与远端内容完全一致：没有覆盖风险，直接收起提示
    if (item.content.trim() === text.value.trim() && item.title.trim() === title.value.trim()) {
      store.dismissRemoteUpdate()
      return
    }
    emit('notice', {
      kind: 'err',
      text: '这条记录已在其他设备更新；继续保存会覆盖对方的内容',
    })
  },
)

/** 载入其他设备的最新版本（会丢弃当前未保存的改动） */
function handleLoadRemote() {
  const item = store.applyRemoteUpdate()
  if (!item) {
    return
  }
  title.value = item.title
  text.value = item.content
  editingTitle.value = item.title
  // 内容与库里一致，避免立刻触发一次无意义的自动保存
  markSaved(item.content)
  emit('notice', { kind: 'ok', text: '已载入其他设备的最新内容' })
}

async function handleSave() {
  if (text.value.trim() === '') {
    return
  }
  try {
    const { item, deduped } = await store.uploadText(text.value, title.value)
    // 手动保存成功后标记已保存，避免自动保存重复提交同一内容
    markSaved(text.value)
    emit('notice', {
      kind: 'ok',
      text: deduped ? `内容已存在，已刷新时间戳：${item.title}` : `已保存：${item.title}`,
    })
  } catch (err) {
    emit('notice', { kind: 'err', text: getErrorMessage(err) })
  }
}

/** Ctrl/Cmd + Enter 快速保存 */
function onKeydown(event: KeyboardEvent) {
  if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
    event.preventDefault()
    void handleSave()
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
      <span class="hint hint--keyboard">Ctrl+Enter 快速保存</span>
    </div>

    <!--
      正在编辑已有记录时给出明确提示：否则用户不知道"保存"会更新那一条
      而不是新建，容易误改历史记录。
    -->
    <div v-if="store.editingId" class="editing-banner">
      <span class="editing-banner__text">
        ✎ 正在编辑已有记录<template v-if="editingTitle">：{{ editingTitle }}</template>
        <span class="editing-banner__sub">（保存会更新这一条，不会新建）</span>
      </span>
    </div>

    <!--
      其他设备改过这一条时的提示：本机保存会直接覆盖，必须让用户知道
      （没有版本号校验，见 clipboardStore 的 remoteUpdate 说明）。
    -->
    <div v-if="store.remoteUpdate" class="editing-banner editing-banner--warn">
      <span class="editing-banner__text">
        ⚠ 这条记录已在其他设备更新
        <span class="editing-banner__sub">（继续保存会覆盖对方的修改）</span>
      </span>
      <span class="editing-banner__actions">
        <button type="button" class="btn btn--small" @click="handleLoadRemote">载入最新</button>
        <button type="button" class="btn btn--small" @click="store.dismissRemoteUpdate()">
          忽略
        </button>
      </span>
    </div>

    <label class="field field--tight">
      <span>标题（留空将自动生成，如「剪贴板 · 10-05 21:56」，按本机时区）</span>
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
        placeholder="在这里输入或粘贴内容；点历史记录可载入编辑"
        @keydown="onKeydown"
      />
    </label>

    <div class="actions actions--wrap">
      <button
        type="button"
        class="btn btn--primary"
        :disabled="text.trim() === ''"
        @click="handleSave"
      >
        保存
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

/* 其他设备更新提示：用警示色与「正在编辑」的蓝色横幅区分开 */
.editing-banner--warn {
  background: #fffbeb;
  border-color: #fde68a;
  color: #92400e;
}

.editing-banner--warn .editing-banner__sub {
  color: #b45309;
}

.editing-banner__actions {
  display: flex;
  flex-shrink: 0;
  gap: 6px;
}
</style>
