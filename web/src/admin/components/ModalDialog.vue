<script setup lang="ts">
/** 通用模态对话框：Esc、遮罩点击、右上角按钮都可以关闭。 */
import { onBeforeUnmount, onMounted } from 'vue'

defineProps<{
  open: boolean
  title: string
}>()

const emit = defineEmits<{ (e: 'close'): void }>()

function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape') {
    emit('close')
  }
}

onMounted(() => window.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="modal"
      role="presentation"
      @click.self="emit('close')"
    >
      <div class="modal__panel" role="dialog" aria-modal="true" :aria-label="title">
        <header class="modal__head">
          <h3 class="modal__title">{{ title }}</h3>
          <button type="button" class="btn btn--small" @click="emit('close')">
            关闭
          </button>
        </header>
        <div class="modal__body">
          <slot />
        </div>
        <footer v-if="$slots.footer" class="modal__foot">
          <slot name="footer" />
        </footer>
      </div>
    </div>
  </Teleport>
</template>
