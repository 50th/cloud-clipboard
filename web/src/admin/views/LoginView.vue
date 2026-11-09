<script setup lang="ts">
import { computed, ref } from 'vue'

import { getErrorMessage } from '#src/api/client.ts'
import { useAdminStore } from '@/admin/stores/adminStore'

const store = useAdminStore()

const username = ref('')
const password = ref('')
const error = ref('')

const canSubmit = computed(
  () => !store.loading && username.value.trim().length > 0 && password.value.length >= 6,
)

async function submit(): Promise<void> {
  if (!canSubmit.value) {
    error.value = '请输入账号和至少 6 位密码'
    return
  }
  error.value = ''
  try {
    await store.login(username.value.trim(), password.value)
    // 登录成功后立即清空内存中的密码
    password.value = ''
  } catch (err) {
    error.value = getErrorMessage(err)
  }
}
</script>

<template>
  <section class="card admin-login">
    <h2>管理员登录</h2>
    <p class="hint">
      仅管理员账号可进入。管理端不会保存密码，关闭标签页后需重新登录。
    </p>

    <form class="admin-login__form" @submit.prevent="submit">
      <label>
        <span>账号</span>
        <input
          v-model="username"
          type="text"
          autocomplete="username"
          placeholder="用户名或邮箱"
        />
      </label>
      <label>
        <span>密码</span>
        <input
          v-model="password"
          type="password"
          autocomplete="current-password"
          placeholder="至少 6 位"
        />
      </label>

      <p v-if="error" class="inline-error" role="alert">{{ error }}</p>

      <button type="submit" class="btn btn--primary" :disabled="!canSubmit">
        {{ store.loading ? '登录中…' : '登录' }}
      </button>
    </form>
  </section>
</template>

<style scoped>
.admin-login {
  max-width: 420px;
  margin: 48px auto;
}

.admin-login__form {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 16px;
}

.admin-login__form label {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 13px;
}

.admin-login__form input {
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  font-size: 14px;
}

.admin-login__form button {
  margin-top: 4px;
}
</style>
