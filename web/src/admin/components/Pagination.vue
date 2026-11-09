<script setup lang="ts">
const props = defineProps<{
  page: number
  pages: number
  total: number
  size: number
}>()

const emit = defineEmits<{
  (e: 'update:page', page: number): void
  (e: 'update:size', size: number): void
}>()

/** 可选分页大小；与后端 `size` 上限 100 保持一致。 */
const sizeOptions = [10, 20, 50, 100]

function go(next: number): void {
  if (next < 1 || next > props.pages || next === props.page) {
    return
  }
  emit('update:page', next)
}

function changeSize(event: Event): void {
  const next = Number((event.target as HTMLSelectElement).value)
  if (next !== props.size) {
    emit('update:size', next)
  }
}
</script>

<template>
  <div v-if="pages > 0" class="admin-pagination">
    <label class="admin-pagination__size">
      每页
      <select :value="size" aria-label="每页条数" @change="changeSize">
        <option v-for="option in sizeOptions" :key="option" :value="option">
          {{ option }} 条
        </option>
      </select>
    </label>
    <span>共 {{ total }} 条 · 第 {{ page }} / {{ pages }} 页</span>
    <button
      type="button"
      class="btn btn--small"
      :disabled="page <= 1"
      @click="go(page - 1)"
    >
      上一页
    </button>
    <button
      type="button"
      class="btn btn--small"
      :disabled="page >= pages"
      @click="go(page + 1)"
    >
      下一页
    </button>
  </div>
</template>
