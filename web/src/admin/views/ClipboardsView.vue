<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { adminClipboardsApi } from '@/admin/api/clipboards.ts'
import type {
  AdminClipboardItem,
  AdminClipboardItemList,
} from '@/admin/api/client.ts'
import Pagination from '@/admin/components/Pagination.vue'
import ModalDialog from '@/admin/components/ModalDialog.vue'
import { getErrorMessage } from '#src/api/client.ts'
import { formatBytes, byteSize, formatDateTime } from '@/utils/format.ts'

const search = ref('')
const username = ref('')
const contentType = ref<'all' | 'text' | 'image' | 'file'>('all')
const page = ref(1)
const size = ref(10)
const data = ref<AdminClipboardItemList | null>(null)
const expanded = ref<AdminClipboardItem | null>(null)
const loading = ref(false)
const error = ref('')
const notice = ref('')

function formatDate(value: string | null | undefined): string {
  return value ? formatDateTime(value) : '—'
}

function itemSize(item: AdminClipboardItem): string {
  const size = (item.metadata as { size?: number } | null)?.size
  return formatBytes(typeof size === 'number' ? size : byteSize(item.content))
}

async function load(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    data.value = await adminClipboardsApi.list({
      page: page.value,
      size: size.value,
      search: search.value.trim() || undefined,
      username: username.value.trim() || undefined,
      content_type: contentType.value === 'all' ? undefined : contentType.value,
      sort_by: 'updated_at',
      order: 'desc',
    })
  } catch (err) {
    error.value = getErrorMessage(err)
  } finally {
    loading.value = false
  }
}

function applyFilters(): void {
  page.value = 1
  expanded.value = null
  void load()
}

function changePage(next: number): void {
  page.value = next
  expanded.value = null
  void load()
}

function changeSize(next: number): void {
  size.value = next
  page.value = 1
  expanded.value = null
  void load()
}

async function openItem(id: string): Promise<void> {
  error.value = ''
  try {
    expanded.value = await adminClipboardsApi.detail(id)
  } catch (err) {
    error.value = getErrorMessage(err)
  }
}

async function deleteItem(item: AdminClipboardItem): Promise<void> {
  if (!window.confirm('确定删除这条剪贴板？此操作不可恢复。')) {
    return
  }
  error.value = ''
  notice.value = ''
  try {
    await adminClipboardsApi.remove(item.id)
    if (expanded.value?.id === item.id) {
      expanded.value = null
    }
    notice.value = '已删除剪贴板'
    if (data.value && data.value.items.length === 1 && page.value > 1) {
      page.value -= 1
    }
    await load()
  } catch (err) {
    error.value = getErrorMessage(err)
  }
}

onMounted(load)
</script>

<template>
  <section class="card">
    <div class="panel__head">
      <h2>剪贴板管理</h2>
      <span class="hint">共 {{ data?.total ?? 0 }} 条</span>
    </div>

    <form class="admin-toolbar" @submit.prevent="applyFilters">
      <input
        v-model="search"
        type="search"
        placeholder="搜索标题或内容"
        aria-label="搜索剪贴板"
      />
      <input
        v-model="username"
        type="search"
        placeholder="按用户名筛选"
        aria-label="按用户名筛选"
      />
      <select v-model="contentType" aria-label="内容类型" @change="applyFilters">
        <option value="all">全部类型</option>
        <option value="text">text</option>
        <option value="image">image</option>
        <option value="file">file</option>
      </select>
      <button type="submit" class="btn btn--small btn--primary">搜索</button>
      <button type="button" class="btn btn--small" :disabled="loading" @click="load">
        刷新
      </button>
    </form>

    <p v-if="error" class="inline-error" role="alert">{{ error }}</p>
    <p v-if="notice" class="hint" role="status">{{ notice }}</p>

    <div v-if="data && data.items.length" class="admin-table__wrap">
      <table class="admin-table">
        <thead>
          <tr>
            <th>标题</th>
            <th>所属用户</th>
            <th>类型</th>
            <th>大小</th>
            <th>创建时间</th>
            <th>更新时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in data.items" :key="item.id">
            <td>{{ item.title }}</td>
            <td>{{ item.username }}</td>
            <td>{{ item.content_type }}</td>
            <td>{{ itemSize(item) }}</td>
            <td>{{ formatDate(item.created_at) }}</td>
            <td>{{ formatDate(item.updated_at) }}</td>
            <td>
              <div class="admin-table__actions">
                <button
                  type="button"
                  class="btn btn--small"
                  @click="openItem(item.id)"
                >
                  查看全文
                </button>
                <button
                  type="button"
                  class="btn btn--small btn--danger"
                  @click="deleteItem(item)"
                >
                  删除
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <p v-else-if="!loading" class="admin-empty">没有匹配的剪贴板</p>

    <ModalDialog
      :open="Boolean(expanded)"
      :title="expanded?.title ?? '剪贴板详情'"
      @close="expanded = null"
    >
      <template v-if="expanded">
        <dl class="clipboard-detail">
          <dt>标题</dt>
          <dd>{{ expanded.title }}</dd>
          <dt>所属用户</dt>
          <dd>{{ expanded.username }}（{{ expanded.user_id }}）</dd>
          <dt>类型</dt>
          <dd>{{ expanded.content_type }}</dd>
          <dt>大小</dt>
          <dd>{{ itemSize(expanded) }}</dd>
          <dt>创建时间</dt>
          <dd>{{ formatDate(expanded.created_at) }}</dd>
          <dt>更新时间</dt>
          <dd>{{ formatDate(expanded.updated_at) }}</dd>
          <dt>记录 ID</dt>
          <dd>{{ expanded.id }}</dd>
        </dl>
        <h4 class="clipboard-detail__label">内容</h4>
        <pre class="clipboard-content">{{ expanded.content }}</pre>
      </template>
      <template #footer>
        <button
          v-if="expanded"
          type="button"
          class="btn btn--small btn--danger"
          @click="deleteItem(expanded)"
        >
          删除
        </button>
        <button type="button" class="btn btn--small" @click="expanded = null">
          关闭
        </button>
      </template>
    </ModalDialog>

    <Pagination
      :page="page"
      :pages="data?.pages ?? 0"
      :total="data?.total ?? 0"
      :size="size"
      @update:page="changePage"
      @update:size="changeSize"
    />
  </section>
</template>
