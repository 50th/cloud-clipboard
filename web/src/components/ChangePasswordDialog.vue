<script setup lang="ts">
/**
 * 修改密码弹窗。
 *
 * 密码策略与后端保持一致：至少 8 个字符、同时包含字母和数字、不能包含用户名。
 * 修改成功后服务端会撤销全部令牌，本机也回到登录页，需要用新密码重新登录。
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { getErrorMessage } from '#src/api/client.ts'
import { useUserStore } from '#src/stores/userStore.ts'
import { clearRememberedCredentials } from '#src/utils/rememberedCredentials.ts'
import { validatePassword } from '#src/utils/passwordPolicy.ts'

const props = defineProps<{
  open: boolean
  username: string
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'notice', value: { kind: 'ok' | 'err'; text: string }): void
}>()

const userStore = useUserStore()

const oldPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const submitting = ref(false)

/** 前端预校验；服务端仍会做最终校验。 */
const validationError = computed(() => {
  const policyError = validatePassword(newPassword.value, props.username)
  if (policyError) {
    return policyError
  }
  if (confirmPassword.value && newPassword.value !== confirmPassword.value) {
    return '两次输入的新密码不一致'
  }
  return ''
})

const canSubmit = computed(
  () =>
    !submitting.value &&
    oldPassword.value.length > 0 &&
    newPassword.value.length > 0 &&
    confirmPassword.value.length > 0 &&
    validationError.value === '',
)

function resetForm(): void {
  oldPassword.value = ''
  newPassword.value = ''
  confirmPassword.value = ''
}

watch(
  () => props.open,
  (open) => {
    if (open) {
      resetForm()
    }
  },
)

function close(): void {
  if (!submitting.value) {
    emit('close')
  }
}

function onKeydown(event: KeyboardEvent): void {
  if (props.open && event.key === 'Escape') {
    close()
  }
}

onMounted(() => window.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))

async function handleSubmit(): Promise<void> {
  if (!canSubmit.value) {
    return
  }
  submitting.value = true
  try {
    await userStore.changePassword(oldPassword.value, newPassword.value)
    // 服务端已撤销全部令牌；本机保存的「记住密码」也一并清掉，避免继续用旧密码登录
    clearRememberedCredentials()
    emit('notice', { kind: 'ok', text: '密码已修改，请使用新密码重新登录' })
    emit('close')
  } catch (error) {
    emit('notice', { kind: 'err', text: getErrorMessage(error) })
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="modal" role="presentation" @click.self="close">
      <div class="modal__panel" role="dialog" aria-modal="true" aria-label="修改密码">
        <header class="modal__head">
          <h2 class="modal__title">修改密码</h2>
        </header>
        <form class="modal__body" @submit.prevent="handleSubmit">
          <p class="hint">
            新密码至少 8 个字符，需同时包含字母和数字，且不能包含用户名。
            修改成功后所有设备都需要重新登录。
          </p>

          <label class="field">
            <span>当前密码</span>
            <input
              v-model="oldPassword"
              type="password"
              autocomplete="current-password"
              :disabled="submitting"
            />
          </label>

          <label class="field">
            <span>新密码</span>
            <input
              v-model="newPassword"
              type="password"
              autocomplete="new-password"
              :disabled="submitting"
            />
          </label>

          <label class="field">
            <span>确认新密码</span>
            <input
              v-model="confirmPassword"
              type="password"
              autocomplete="new-password"
              :disabled="submitting"
            />
          </label>

          <p v-if="newPassword && validationError" class="form-error">
            {{ validationError }}
          </p>

          <footer class="modal__foot">
            <button type="button" class="btn" :disabled="submitting" @click="close">
              取消
            </button>
            <button type="submit" class="btn btn--primary" :disabled="!canSubmit">
              {{ submitting ? '提交中…' : '确认修改' }}
            </button>
          </footer>
        </form>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
/* 弹窗基础样式在全局 styles.css，这里只覆盖宽度与内嵌 footer */
.modal__panel {
  width: min(440px, 100%);
}

/* 这个弹窗的 footer 在 form 内部（提交按钮要触发表单提交），
   因此不收 body 的内边距，只保留一条分隔线 */
.modal__foot {
  margin-top: 16px;
  padding: 16px 0 0;
  border-top: 1px solid var(--border-soft);
}

.form-error {
  margin: 10px 0 0;
  color: var(--danger);
  font-size: 12px;
}
</style>
