<script setup lang="ts">
/**
 * 公开分享查看页。
 *
 * 计数规则：页面加载与刷新只调 `meta`；只有用户点击「查看内容」
 * 或提交正确密码时才调 `access` 并计数。
 */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import { getErrorMessage, publicShareApi } from '@/api/client'
import type { PublicShareContent, PublicShareMeta } from '@/api/client'
import { useCopy } from '@/composables/useCopy'
import { formatDateTime } from '@/utils/format'

const token = computed(() => {
  const path = window.location.pathname
  const raw = path.startsWith('/s/') ? path.slice(3) : ''
  return decodeURIComponent(raw).replace(/\/+$/, '')
})

const loading = ref(true)
const meta = ref<PublicShareMeta | null>(null)
const content = ref<PublicShareContent | null>(null)
const password = ref('')
const submitting = ref(false)
const errorText = ref('')
const fatal = ref(false)

/** 交互错误用 Toast 展示，默认 5 秒后自动消失 */
const TOAST_TIMEOUT_MS = 5000
const toast = ref('')
let toastTimer: ReturnType<typeof setTimeout> | undefined

function showToast(text: string): void {
  toast.value = text
  if (toastTimer !== undefined) {
    clearTimeout(toastTimer)
  }
  toastTimer = setTimeout(() => {
    toast.value = ''
    toastTimer = undefined
  }, TOAST_TIMEOUT_MS)
}

const { copied, error: copyError, copy } = useCopy()

const remaining = computed(() =>
  content.value ? content.value.remaining_views : meta.value?.remaining_views,
)

const displayTitle = computed(
  () => content.value?.title ?? meta.value?.title ?? '受密码保护的内容',
)

function statusOf(error: unknown): number | undefined {
  return (error as { response?: { status?: number } }).response?.status
}

function messageFor(status: number | undefined, fallback: string): string {
  if (status === 404) {
    return '分享不存在'
  }
  if (status === 410) {
    return '分享已失效'
  }
  if (status === 429) {
    return '尝试过于频繁，请稍后再试'
  }
  return fallback
}

async function loadMeta(): Promise<void> {
  loading.value = true
  errorText.value = ''
  if (!token.value) {
    fatal.value = true
    errorText.value = '分享不存在'
    loading.value = false
    return
  }
  try {
    meta.value = await publicShareApi.meta(token.value)
  } catch (error) {
    fatal.value = true
    errorText.value = messageFor(statusOf(error), getErrorMessage(error))
  } finally {
    loading.value = false
  }
}

async function viewContent(): Promise<void> {
  if (!meta.value || submitting.value) {
    return
  }
  if (meta.value.password_required && !password.value) {
    showToast('请输入密码')
    return
  }
  submitting.value = true
  try {
    content.value = await publicShareApi.access(
      token.value,
      meta.value.password_required ? password.value : undefined,
    )
    toast.value = ''
  } catch (error) {
    const status = statusOf(error)
    // 分享在查看过程中失效：切到页面级失效状态，而不是只弹一条很快消失的提示
    if (status === 404 || status === 410) {
      fatal.value = true
      errorText.value = messageFor(status, getErrorMessage(error))
      return
    }
    showToast(
      status === 403 ? '密码错误' : messageFor(status, getErrorMessage(error)),
    )
  } finally {
    submitting.value = false
  }
}

onMounted(loadMeta)

onBeforeUnmount(() => {
  if (toastTimer !== undefined) {
    clearTimeout(toastTimer)
  }
})
</script>

<template>
  <main class="share-page">
    <header class="share-head">
      <h1>云剪贴板 · 分享</h1>
      <p class="hint">只读链接 · 不会保存到你的剪贴板</p>
    </header>

    <p v-if="loading" class="loading">正在加载…</p>

    <section v-else-if="fatal" class="card share-card">
      <p class="inline-error" role="alert">{{ errorText }}</p>
    </section>

    <section v-else-if="meta" class="card share-card">
      <h2 class="share-title">{{ displayTitle }}</h2>

      <div v-if="content" class="share-body">
        <pre class="share-content">{{ content.content }}</pre>
        <div class="share-actions">
          <button
            type="button"
            class="btn btn--small btn--primary"
            @click="copy(content.content)"
          >
            {{ copied ? '✓ 已复制' : '复制内容' }}
          </button>
          <span v-if="copyError" class="warn">{{ copyError }}</span>
        </div>
      </div>

      <form
        v-else
        class="share-unlock"
        :class="{ 'share-unlock--single': !meta.password_required }"
        @submit.prevent="viewContent"
      >
        <label v-if="meta.password_required" class="field share-unlock__field">
          <span>访问密码</span>
          <input
            v-model="password"
            type="password"
            autocomplete="off"
            :disabled="submitting"
            placeholder="请输入分享者设置的密码"
          />
        </label>
        <button
          type="submit"
          class="btn btn--primary share-unlock__submit"
          :disabled="submitting"
        >
          {{ submitting ? '正在查看…' : '查看内容' }}
        </button>
      </form>

      <dl class="share-meta">
        <div v-if="meta.expires_at">
          <dt>到期时间</dt>
          <dd>{{ formatDateTime(meta.expires_at) }}</dd>
        </div>
        <div v-if="remaining !== null && remaining !== undefined">
          <dt>剩余查看次数</dt>
          <dd>{{ remaining }}</dd>
        </div>
      </dl>
    </section>

    <footer class="share-foot">
      <a href="/">返回云剪贴板</a>
    </footer>

    <!-- 交互错误用 Toast：固定悬浮、5 秒后自动消失（样式复用全局 .notice） -->
    <Transition name="notice-fade">
      <p
        v-if="toast"
        class="notice notice--err share-toast"
        role="alert"
        aria-live="assertive"
      >
        {{ toast }}
      </p>
    </Transition>
  </main>
</template>

<style scoped>
.share-page {
  max-width: 760px;
  margin: 0 auto;
  padding: 28px 16px 48px;
}

/*
 * 分享页的 Hero：深青 → 薄荷绿渐变 + 右上角柔光，
 * 与品牌在营销页上的氛围 Hero 呼应；正文卡片保持扁平、密集。
 */
.share-head {
  position: relative;
  overflow: hidden;
  padding: 36px 32px;
  border-radius: var(--radius-xl);
  background: linear-gradient(135deg, #1a3d4a 0%, #2d5a4f 100%);
  color: #fff;
  box-shadow: 0 24px 48px -24px rgba(26, 61, 74, 0.55);
}

.share-head::after {
  content: '';
  position: absolute;
  top: -96px;
  right: -72px;
  width: 280px;
  height: 280px;
  border-radius: 50%;
  background: radial-gradient(closest-side, rgba(0, 212, 164, 0.55), transparent 72%);
  pointer-events: none;
}

.share-head h1 {
  position: relative;
  margin: 0 0 6px;
  color: #fff;
  font-size: 28px;
  font-weight: 600;
  letter-spacing: -0.6px;
  line-height: 1.15;
}

.share-head .hint {
  position: relative;
  margin: 0;
  color: rgba(255, 255, 255, 0.72);
  font-size: 13px;
}

.share-card {
  margin-top: 16px;
  padding: 28px;
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-card);
}

.share-title {
  margin: 0 0 16px;
  font-size: 20px;
  font-weight: 600;
  letter-spacing: -0.3px;
  word-break: break-word;
}

.share-content {
  margin: 0;
  padding: 16px;
  max-height: 60vh;
  overflow: auto;
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-lg);
  background: var(--surface-soft);
  white-space: pre-wrap;
  word-break: break-word;
  font-family: var(--font-mono);
  font-size: 13px;
  line-height: 1.7;
  color: var(--charcoal);
}

.share-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 16px;
}

.share-unlock {
  display: flex;
  align-items: flex-end;
  gap: 10px;
}

/* 密码框占剩余宽度，按钮固定不换行，二者保持同一行 */
.share-unlock__field {
  flex: 1 1 auto;
  min-width: 0;
  margin-bottom: 0;
}

.share-unlock__field input {
  min-height: 42px;
}

.share-unlock__submit {
  flex: 0 0 auto;
  min-height: 42px;
  padding: 10px 20px;
  white-space: nowrap;
}

/* 无密码时只有按钮：让它占满整行，而不是靠左缩成一小块 */
.share-unlock--single .share-unlock__submit {
  flex: 1 1 auto;
  width: 100%;
  min-height: 44px;
}

.share-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 20px 0 0;
  padding-top: 16px;
  border-top: 1px solid var(--border-soft);
  color: var(--text-muted);
  font-size: 12px;
}

.share-meta div {
  display: inline-flex;
  gap: 6px;
  padding: 4px 12px;
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-full);
  background: var(--surface-soft);
}

.share-meta dt,
.share-meta dd {
  margin: 0;
}

.share-meta dt {
  color: var(--stone);
}

.share-meta dd {
  color: var(--text);
  font-weight: 500;
}

.share-foot {
  margin-top: 24px;
  text-align: center;
  font-size: 12px;
}

.share-foot a {
  color: var(--text-muted);
  text-decoration: none;
  transition: color 0.15s ease;
}

.share-foot a:hover {
  color: var(--text);
  text-decoration: underline;
}

/* 分享页 Toast 固定在上方（全局 .notice 桌面端默认在底部） */
.share-toast {
  top: calc(16px + env(safe-area-inset-top));
  bottom: auto;
}

.share-toast.notice-fade-enter-from,
.share-toast.notice-fade-leave-to {
  transform: translateX(-50%) translateY(-10px);
}

@media (max-width: 900px) {
  .share-page {
    padding: 16px 12px 32px;
    padding-top: calc(16px + env(safe-area-inset-top));
  }

  .share-head {
    padding: 24px 20px;
    border-radius: var(--radius-lg);
  }

  .share-head h1 {
    font-size: 22px;
  }

  .share-card {
    padding: 18px 16px;
    border-radius: var(--radius-lg);
  }

  .share-title {
    font-size: 18px;
  }

  .share-content {
    font-size: 14px;
    padding: 14px;
  }
}
</style>
