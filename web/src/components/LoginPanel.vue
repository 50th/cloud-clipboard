<script setup lang="ts">
/**
 * 登录 / 注册页（第 4 步）。
 *
 * 后端已接入真实 JWT：未登录时所有剪贴板请求都会 401，
 * 因此这里只提供真实账号的登录与注册。
 */
import { computed, ref } from 'vue'

import { getErrorMessage } from '#src/api/client.ts'
import { useUserStore } from '#src/stores/userStore.ts'

const emit = defineEmits<{ (e: 'notice', value: { kind: 'ok' | 'err'; text: string }): void }>()

const userStore = useUserStore()

type Mode = 'login' | 'register'
const mode = ref<Mode>('login')

/** 「记住密码」的本地存储键（只存在本机浏览器，不上传服务端） */
const REMEMBER_KEY = 'cloud-clipboard.remembered-credentials'

interface RememberedCredentials {
  username: string
  password: string
}

const username = ref('')
const email = ref('')
const password = ref('')
const inviteCode = ref('')
const submitting = ref(false)
const remember = ref(false)

/** 读取上次保存的登录信息；解析失败时忽略并保持空表单。 */
function loadRememberedCredentials(): void {
  try {
    const raw = localStorage.getItem(REMEMBER_KEY)
    if (!raw) {
      return
    }
    const saved = JSON.parse(raw) as Partial<RememberedCredentials>
    if (saved.username) {
      username.value = saved.username
    }
    if (saved.password) {
      password.value = saved.password
    }
    remember.value = true
  } catch {
    /* 私密模式或数据损坏时忽略 */
  }
}

loadRememberedCredentials()

/** 勾选时保存账号密码，取消勾选时立即清除。 */
function handleRememberChange(): void {
  if (!remember.value) {
    clearRememberedCredentials()
  }
}

function persistRememberedCredentials(): void {
  try {
    if (remember.value) {
      localStorage.setItem(
        REMEMBER_KEY,
        JSON.stringify({ username: username.value.trim(), password: password.value }),
      )
    } else {
      localStorage.removeItem(REMEMBER_KEY)
    }
  } catch {
    /* localStorage 不可用时忽略 */
  }
}

function clearRememberedCredentials(): void {
  try {
    localStorage.removeItem(REMEMBER_KEY)
  } catch {
    /* localStorage 不可用时忽略 */
  }
}

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
      await userStore.register(
        username.value.trim(),
        email.value.trim(),
        password.value,
        inviteCode.value.trim() || undefined,
      )
      // 注册的是新账号，清掉可能属于其他账号的本地记录
      clearRememberedCredentials()
      emit('notice', { kind: 'ok', text: `注册成功，已以 ${username.value.trim()} 登录` })
    } else {
      await userStore.login(username.value.trim(), password.value)
      persistRememberedCredentials()
      emit('notice', { kind: 'ok', text: `已登录：${username.value.trim()}` })
    }
    password.value = ''
  } catch (error) {
    emit('notice', { kind: 'err', text: getErrorMessage(error) })
  } finally {
    submitting.value = false
  }
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
          placeholder="用户名或邮箱"
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

      <label v-if="isRegister" class="field">
        <span>邀请码（服务端开启注册验证时必填）</span>
        <input
          v-model="inviteCode"
          type="text"
          autocomplete="off"
          placeholder="请输入邀请码"
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

      <label v-if="!isRegister" class="switch login__remember">
        <input
          v-model="remember"
          type="checkbox"
          :disabled="submitting"
          @change="handleRememberChange"
        />
        <span>记住密码（保存在本机浏览器）</span>
      </label>

      <div class="login__actions">
        <button type="submit" class="btn btn--primary" :disabled="!canSubmit">
          {{ submitLabel }}
        </button>
      </div>
    </form>
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

.login__remember {
  margin-top: 10px;
  font-size: 13px;
  color: var(--text-muted);
}

.login__actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 14px;
}
</style>
