<script setup lang="ts">
import { computed, ref } from 'vue'

import type { ClipboardItem } from '@/api/client'
import { useCopy } from '@/composables/useCopy'
import { formatBytes, formatRelative } from '@/utils/format'

const props = defineProps<{
  item: ClipboardItem
  deleting: boolean
}>()

const emit = defineEmits<{
  (e: 'delete', id: string): void
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
</script>

<template>
  <article class="item">
    <header class="item__head">
      <h3 class="item__title" :title="item.title">{{ item.title }}</h3>
      <span class="item__time" :title="item.created_at">
        {{ formatRelative(item.created_at) }}
      </span>
    </header>

    <pre class="item__content">{{ shownContent }}</pre>

    <div class="item__actions">
      <button
        type="button"
        class="btn btn--small btn--primary"
        @click="copy(item.content)"
      >
        {{ copied ? '✓ 已复制' : '复制' }}
      </button>
      <button
        v-if="collapsible"
        type="button"
        class="btn btn--small"
        @click="expanded = !expanded"
      >
        {{ expanded ? '收起' : '展开' }}
      </button>
      <button
        type="button"
        class="btn btn--small btn--danger"
        :disabled="deleting"
        @click="emit('delete', item.id)"
      >
        {{ deleting ? '删除中…' : '删除' }}
      </button>
      <span class="item__meta">
        {{ item.content_type }}
        <template v-if="typeof size === 'number'"> · {{ formatBytes(size) }}</template>
        <template v-if="updated"> · 已更新</template>
      </span>
      <span v-if="copyError" class="warn">{{ copyError }}</span>
    </div>
  </article>
</template>
