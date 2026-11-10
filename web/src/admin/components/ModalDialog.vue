<script setup lang="ts">
/** 通用模态对话框：Esc、遮罩点击、底部按钮都可以关闭；右上角按钮可选。 */
import { onBeforeUnmount, onMounted } from 'vue'

const props = withDefaults(
  defineProps<{
    open: boolean
    title: string
    /** 是否显示右上角关闭按钮；默认关闭，避免与底部「关闭 / 取消」重复 */
    showClose?: boolean
  }>(),
  { showClose: false },
)

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
          <button
            v-if="props.showClose"
            type="button"
            class="btn btn--small"
            @click="emit('close')"
          >
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
