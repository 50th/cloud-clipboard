<script setup lang="ts">
/**
 * 登录 / 注册页（第 4 步）。
 *
 * 后端已接入真实 JWT：未登录时所有剪贴板请求都会 401，
 * 因此这里不再有"演示用户"兜底入口。
 */
import { computed, ref } from 'vue'

import { getErrorMessage } from '#src/api/client.ts'
import { useUserStore } from '#src/stores/userStore.ts'

const emit = defineEmits<{ (e: 'notice', value: { kind: 'ok' | 'err'; text: string }): void }>()

const userStore = useUserStore()

type Mode = 'login' | 'register'
const mode = ref<Mode>('login')

const username = ref('')
const email = ref('')
const password = ref('')
const submitting = ref(false)

const isRegister = computed(() => mode.value === 'register')

const submitLabel = computed(() => {
  if (submitting.value) {
    return isRegister.value ? '注册中…' : '登录中…'
  }
  return isRegister.value ? '注册并登录' : '登录'
})

/** 前端预校验，避免明显无效的请求打到后端 */
const canSubmit = computed(() => {
  if (submitting.value) {
    return false
  }
  if (username.value.trim().length < 3 || password.value.length < 6) {
    return false
  }
  if (isRegister.value) {
    return email.value.trim().length >= 3
  }
  return true
})

function switchMode(next: Mode) {
  mode.value = next
  password.value = ''
}

async function handleSubmit() {
  if (!canSubmit.value) {
    return
  }
  submitting.value = true
  try {
    if (isRegister.value) {
      await userStore.register(username.value.trim(), email.value.trim(), password.value)
      emit('notice', { kind: 'ok', text: `注册成功，已以 ${username.value.trim()} 登录` })
    } else {
      await userStore.login(username.value.trim(), password.value)
      emit('notice', { kind: 'ok', text: `已登录：${username.value.trim()}` })
    }
    password.value = ''
  } catch (error) {
    emit('notice', { kind: 'err', text: getErrorMessage(error) })
  } finally {
    submitting.value = false
  }
}

/** 一键填入本地演示账号（仅在开发环境可见） */
function fillDemoAccount() {
  mode.value = 'login'
  username.value = 'demo'
  password.value = 'demo1234'
}
</script>

<template>
  <div class="card login">
    <div class="login__tabs">
      <button
        type="button"
        class="login__tab"
        :class="{ 'login__tab--active': mode === 'login' }"
        @click="switchMode('login')"
      >
        登录
      </button>
      <button
        type="button"
        class="login__tab"
        :class="{ 'login__tab--active': mode === 'register' }"
        @click="switchMode('register')"
      >
        注册
      </button>
    </div>

    <p class="hint">
      <template v-if="isRegister">创建一个新账号，注册成功后会直接登录。</template>
      <template v-else>登录后才能查看和同步你的剪贴板记录。</template>
    </p>

    <form @submit.prevent="handleSubmit">
      <label class="field">
        <span>{{ isRegister ? '用户名（3-32 字符）' : '用户名或邮箱' }}</span>
        <input
          v-model="username"
          type="text"
          autocomplete="username"
          placeholder="demo"
          :disabled="submitting"
        />
      </label>

      <label v-if="isRegister" class="field">
        <span>邮箱</span>
        <input
          v-model="email"
          type="email"
          autocomplete="email"
          placeholder="you@example.com"
          :disabled="submitting"
        />
      </label>

      <label class="field">
        <span>密码（至少 6 字符，且不超过 72 字节）</span>
        <input
          v-model="password"
          type="password"
          :autocomplete="isRegister ? 'new-password' : 'current-password'"
          placeholder="••••••••"
          :disabled="submitting"
        />
      </label>

      <div class="login__actions">
        <button type="submit" class="btn btn--primary" :disabled="!canSubmit">
          {{ submitLabel }}
        </button>
        <button
          v-if="!isRegister"
          type="button"
          class="btn btn--small"
          :disabled="submitting"
          @click="fillDemoAccount"
        >
          填入演示账号
        </button>
      </div>
    </form>

    <p class="login__note">
      密码经 bcrypt 哈希后存储；服务端只保存哈希，不保存明文。
    </p>
  </div>
</template>

<style scoped>
.login {
  max-width: 420px;
  margin: 0 auto;
}

.login__tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 12px;
  border-bottom: 1px solid var(--border);
}

.login__tab {
  border: none;
  background: none;
  padding: 8px 14px;
  font: inherit;
  font-size: 14px;
  color: var(--text-muted);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
}

.login__tab--active {
  color: var(--primary);
  border-bottom-color: var(--primary);
  font-weight: 500;
}

.login__actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 14px;
}

.login__note {
  margin: 14px 0 0;
  padding-top: 10px;
  border-top: 1px dashed var(--border);
  color: var(--text-muted);
  font-size: 12px;
}
</style>
