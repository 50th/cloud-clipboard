<script setup lang="ts">
import { computed, ref } from 'vue'

import type { ClipboardItem } from '@/api/client'
import { useCopy } from '@/composables/useCopy'
import { formatBytes, formatRelative } from '@/utils/format'

const props = defineProps<{
  item: ClipboardItem
  deleting: boolean
  /** 是否是当前正在编辑的那一条（用于高亮） */
  editing?: boolean
}>()

const emit = defineEmits<{
  (e: 'delete', id: string): void
  /** 点整卡进入右侧编辑 */
  (e: 'edit', item: ClipboardItem): void
}>()

const { copied, error: copyError, copy } = useCopy()
const expanded = ref(false)

/** 超过 160 字折叠显示 */
const collapsible = computed(() => props.item.content.length > 160)
const shownContent = computed(() =>
  collapsible.value && !expanded.value ? `${props.item.content.slice(0, 160)}…` : props.item.content,
)

const size = computed(() => props.item.metadata?.size)
const updated = computed(() => props.item.updated_at !== props.item.created_at)

function requestEdit() {
  emit('edit', props.item)
}

/** 键盘可达：整卡可点击，就得能用 Enter / 空格触发 */
function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' || event.key === ' ') {
    event.preventDefault()
    requestEdit()
  }
}
</script>

<template>
  <article
    class="item"
    :class="{ 'item--editing': editing }"
    role="button"
    tabindex="0"
    :aria-pressed="editing ? 'true' : 'false'"
    :title="editing ? '正在编辑这一条' : '点击载入到右侧编辑'"
    @click="requestEdit"
    @keydown="onKeydown"
  >
    <header class="item__head">
      <h3 class="item__title" :title="item.title">{{ item.title }}</h3>
      <span class="item__time" :title="item.created_at">
        {{ formatRelative(item.created_at) }}
      </span>
    </header>

    <pre class="item__content">{{ shownContent }}</pre>

    <!--
      卡片级点击会触发编辑，所以卡片内的按钮必须 `.stop`，
      否则点「复制」会同时把内容载入输入区。
    -->
    <div class="item__actions">
      <button
        type="button"
        class="btn btn--small btn--primary"
        @click.stop="copy(item.content)"
      >
        {{ copied ? '✓ 已复制' : '复制' }}
      </button>
      <button
        v-if="collapsible"
        type="button"
        class="btn btn--small"
        @click.stop="expanded = !expanded"
      >
        {{ expanded ? '收起' : '展开' }}
      </button>
      <button
        type="button"
        class="btn btn--small btn--danger"
        :disabled="deleting"
        @click.stop="emit('delete', item.id)"
      >
        {{ deleting ? '删除中…' : '删除' }}
      </button>
      <span class="item__meta">
        <template v-if="editing">● 编辑中 · </template>
        {{ item.content_type }}
        <template v-if="typeof size === 'number'"> · {{ formatBytes(size) }}</template>
        <template v-if="updated"> · 已更新</template>
      </span>
      <span v-if="copyError" class="warn">{{ copyError }}</span>
    </div>
  </article>
</template>
