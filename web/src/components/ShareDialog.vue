<script setup lang="ts">
/**
 * 创建分享弹窗。
 *
 * 风格与 `ChangePasswordDialog.vue` 保持一致：Teleport + 遮罩 + 底部按钮。
 * 创建成功后在同一弹窗展示完整链接与复制按钮。
 */
import { computed, ref, watch } from 'vue'

import { getErrorMessage, shareApi } from '@/api/client'
import type { ClipboardItem, ClipboardShare, ShareExpiresIn, ShareMode } from '@/api/client'
import { useCopy } from '@/composables/useCopy'
import { logger } from '@/utils/logger'

/** 与后端 `SHARE_PER_ITEM_LIMIT` 保持一致：同一条记录最多 5 个有效分享。 */
const ITEM_SHARE_LIMIT = 5

const props = defineProps<{
  open: boolean
  item: ClipboardItem | null
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'notice', value: { kind: 'ok' | 'err'; text: string }): void
  (e: 'created'): void
}>()

const { copied, copy } = useCopy()

const mode = ref<ShareMode>('snapshot')
const expiresIn = ref<ShareExpiresIn>('7d')
const password = ref('')
const maxViews = ref<number | ''>('')
const submitting = ref(false)
const errorText = ref('')
const created = ref<ClipboardShare | null>(null)
/** 该记录当前的有效分享数（打开弹窗时查询） */
const activeShareCount = ref(0)

const encoder = new TextEncoder()

const atItemLimit = computed(() => activeShareCount.value >= ITEM_SHARE_LIMIT)
const canSubmit = computed(
  () => !submitting.value && props.item !== null && !atItemLimit.value,
)

function reset(): void {
  mode.value = 'snapshot'
  expiresIn.value = '7d'
  password.value = ''
  maxViews.value = ''
  submitting.value = false
  errorText.value = ''
  created.value = null
  activeShareCount.value = 0
}

async function loadActiveShareCount(): Promise<void> {
  if (!props.item) {
    return
  }
  try {
    const result = await shareApi.list({
      item_id: props.item.id,
      status: 'active',
      size: 1,
    })
    activeShareCount.value = result.total
  } catch (error) {
    // 查询失败不阻塞创建；后端仍会做最终限额校验
    logger.debug('查询该记录有效分享数失败', error)
  }
}

watch(
  () => props.open,
  (open) => {
    if (open) {
      reset()
      void loadActiveShareCount()
    }
  },
)

function close(): void {
  if (!submitting.value) {
    emit('close')
  }
}

function validate(): string {
  if (password.value) {
    if (password.value.length < 4 || password.value.length > 24) {
      return '密码长度需为 4–24 个字符'
    }
    if (encoder.encode(password.value).length > 72) {
      return '密码不能超过 72 字节'
    }
  }
  if (maxViews.value !== '') {
    const value = Number(maxViews.value)
    if (!Number.isInteger(value) || value < 1 || value > 10_000) {
      return '最大查看次数需为 1–10000 的整数'
    }
  }
  return ''
}

async function handleSubmit(): Promise<void> {
  if (!props.item || submitting.value) {
    return
  }
  const validationError = validate()
  if (validationError) {
    errorText.value = validationError
    return
  }

  submitting.value = true
  errorText.value = ''
  try {
    created.value = await shareApi.create(props.item.id, {
      mode: mode.value,
      expires_in: expiresIn.value,
      password: password.value || null,
      max_views: maxViews.value === '' ? null : Number(maxViews.value),
    })
    activeShareCount.value += 1
    emit('created')
  } catch (error) {
    const text = getErrorMessage(error)
    errorText.value = text
    emit('notice', { kind: 'err', text })
    // 409（单条/全局限额）时刷新已有分享数，帮助用户理解下一步
    if ((error as { response?: { status?: number } }).response?.status === 409) {
      void loadActiveShareCount()
    }
  } finally {
    submitting.value = false
  }
}

async function copyLink(): Promise<void> {
  if (created.value) {
    await copy(created.value.url)
  }
}
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="modal" role="presentation" @click.self="close">
      <div class="modal__panel" role="dialog" aria-modal="true" aria-label="分享剪贴板">
        <header class="modal__head">
          <h2 class="modal__title">分享「{{ item?.title ?? '' }}」</h2>
        </header>

        <div class="modal__body">
          <template v-if="created">
            <p class="hint">
              链接可随时在「我的分享」中再次复制；撤销后立即失效。
            </p>
            <div class="share-link">
              <input :value="created.url" readonly aria-label="分享链接" />
              <button
                type="button"
                class="btn btn--small btn--primary share-link__copy"
                @click="copyLink"
              >
                {{ copied ? '已复制' : '复制' }}
              </button>
            </div>
            <dl class="share-summary">
              <div>
                <dt>模式</dt>
                <dd>{{ created.mode === 'live' ? '跟随最新' : '快照' }}</dd>
              </div>
              <div>
                <dt>密码</dt>
                <dd>{{ created.password_protected ? '已设置' : '无' }}</dd>
              </div>
              <div>
                <dt>最大查看次数</dt>
                <dd>{{ created.max_views ?? '不限' }}</dd>
              </div>
            </dl>
          </template>

          <form v-else class="share-form" @submit.prevent="handleSubmit">
            <p
              v-if="activeShareCount > 0"
              class="hint share-form__quota"
              :class="{ 'share-form__quota--full': atItemLimit }"
            >
              该记录已有 {{ activeShareCount }} 个有效分享（单条最多
              {{ ITEM_SHARE_LIMIT }} 个）。
              <template v-if="atItemLimit">
                请先在「我的分享」撤销旧链接后再创建。
              </template>
            </p>

            <label class="field">
              <span>内容模式</span>
              <select v-model="mode" :disabled="submitting">
                <option value="snapshot">快照（复制当前正文）</option>
                <option value="live">跟随最新（读取原记录最新内容）</option>
              </select>
            </label>

            <label class="field">
              <span>有效期</span>
              <select v-model="expiresIn" :disabled="submitting">
                <option value="1h">1 小时</option>
                <option value="1d">1 天</option>
                <option value="7d">7 天</option>
                <option value="30d">30 天</option>
              </select>
            </label>

            <label class="field">
              <span>访问密码（可空，4–24 字符）</span>
              <input
                v-model="password"
                type="password"
                autocomplete="new-password"
                :disabled="submitting"
                placeholder="留空表示无密码"
              />
            </label>

            <label class="field">
              <span>最大查看次数（可空，1–10000）</span>
              <input
                v-model.number="maxViews"
                type="number"
                min="1"
                max="10000"
                :disabled="submitting"
                placeholder="留空表示不限"
              />
            </label>

            <p v-if="errorText" class="form-error" role="alert">{{ errorText }}</p>
          </form>
        </div>

        <footer class="modal__foot">
          <template v-if="created">
            <button type="button" class="btn" @click="close">关闭</button>
          </template>
          <template v-else>
            <button type="button" class="btn" :disabled="submitting" @click="close">
              取消
            </button>
            <button
              type="button"
              class="btn btn--primary"
              :disabled="!canSubmit"
              @click="handleSubmit"
            >
              {{
                submitting
                  ? '创建中…'
                  : atItemLimit
                    ? '已达单条上限'
                    : '创建分享'
              }}
            </button>
          </template>
        </footer>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.modal {
  position: fixed;
  inset: 0;
  z-index: 90;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(15, 23, 42, 0.45);
}

.modal__panel {
  width: min(420px, 100%);
  max-height: 85vh;
  overflow: auto;
  background: var(--card);
  border-radius: 12px;
  box-shadow: 0 20px 50px rgba(15, 23, 42, 0.25);
}

.modal__head {
  padding: 14px 16px;
  border-bottom: 1px solid var(--border);
}

.modal__title {
  margin: 0;
  font-size: 15px;
  word-break: break-word;
}

.modal__body {
  padding: 16px;
}

.modal__foot {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 0 16px 16px;
}

.form-error {
  margin: 10px 0 0;
  color: var(--danger);
  font-size: 12px;
}

.share-form__quota {
  margin: 0 0 10px;
}

.share-form__quota--full {
  color: var(--danger);
}

.share-link {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}

.share-link input {
  flex: 1 1 auto;
  min-width: 0;
  /* 链接栏不必占满整行：限制输入框长度，复制按钮紧随其后 */
  max-width: 300px;
  font-size: 12px;
}

/* 复制按钮不参与压缩，避免窄屏时“复制”被挤成两行 */
.share-link__copy {
  flex: 0 0 auto;
  white-space: nowrap;
}

.share-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 24px;
  margin: 14px 0 0;
  color: var(--text-muted);
  font-size: 12px;
}

.share-summary div {
  display: flex;
  gap: 6px;
}

.share-summary dt,
.share-summary dd {
  margin: 0;
}
</style>
