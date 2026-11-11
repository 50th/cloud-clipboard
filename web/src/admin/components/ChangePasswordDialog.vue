<script setup lang="ts">
/**
 * 管理端 · 修改当前管理员密码。
 *
 * 策略与后端一致；成功后服务端撤销全部令牌，管理端会话也会被清空，
 * 需要用新密码重新登录。
 */
import { computed, ref, watch } from 'vue'

import ModalDialog from '@/admin/components/ModalDialog.vue'
import { useAdminStore } from '@/admin/stores/adminStore'
import { getErrorMessage } from '#src/api/client.ts'
import { validatePassword } from '#src/utils/passwordPolicy.ts'

const props = defineProps<{ open: boolean }>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'changed'): void
}>()

const store = useAdminStore()

const oldPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const submitting = ref(false)
const error = ref('')

const validationError = computed(() => {
  const policyError = validatePassword(newPassword.value, store.user?.username)
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
  error.value = ''
}

watch(
  () => props.open,
  (open) => {
    if (open) {
      resetForm()
    }
  },
)

/** 提交中不允许关闭，避免请求已发出但界面状态不明。 */
function close(): void {
  if (!submitting.value) {
    emit('close')
  }
}

async function submit(): Promise<void> {
  if (!canSubmit.value) {
    return
  }
  submitting.value = true
  error.value = ''
  try {
    await store.changePassword(oldPassword.value, newPassword.value)
    emit('changed')
    emit('close')
  } catch (err) {
    error.value = getErrorMessage(err)
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <ModalDialog :open="open" title="修改密码" @close="close">
    <form class="change-password" @submit.prevent="submit">
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

      <p v-if="error" class="inline-error" role="alert">{{ error }}</p>
      <p v-else-if="newPassword && validationError" class="inline-error">
        {{ validationError }}
      </p>

      <div class="change-password__actions">
        <button type="button" class="btn btn--small" :disabled="submitting" @click="close">
          取消
        </button>
        <button type="submit" class="btn btn--small btn--primary" :disabled="!canSubmit">
          {{ submitting ? '提交中…' : '确认修改' }}
        </button>
      </div>
    </form>
  </ModalDialog>
</template>

<style scoped>
.change-password {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.change-password__actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 4px;
}
</style>
