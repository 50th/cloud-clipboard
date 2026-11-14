<script setup lang="ts">
/**
 * 网站设置：集中管理全站配置。
 *
 * 当前只有「分享设置」一项；后续新增配置按同样的 section 结构追加。
 */
import { onMounted, ref } from 'vue'

import { adminShareSettingsApi, type ShareSettings } from '@/admin/api/settings.ts'
import { getErrorMessage } from '#src/api/client.ts'
import { formatDateTime } from '@/utils/format.ts'

const data = ref<ShareSettings | null>(null)
const limit = ref(50)
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const notice = ref('')

function formatDate(value: string | null | undefined): string {
  return value ? formatDateTime(value) : '—'
}

async function load(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    data.value = await adminShareSettingsApi.get()
    limit.value = data.value.user_share_limit
  } catch (err) {
    error.value = getErrorMessage(err)
  } finally {
    loading.value = false
  }
}

async function save(): Promise<void> {
  if (!Number.isInteger(limit.value) || limit.value < 1 || limit.value > 10_000) {
    error.value = '分享限额需为 1–10000 的整数'
    return
  }
  saving.value = true
  error.value = ''
  notice.value = ''
  try {
    data.value = await adminShareSettingsApi.update(limit.value)
    notice.value = `已保存：每用户最多 ${data.value.user_share_limit} 个有效分享`
  } catch (err) {
    error.value = getErrorMessage(err)
  } finally {
    saving.value = false
  }
}

function selectAll(event: FocusEvent): void {
  const target = event.target
  if (target instanceof HTMLInputElement) {
    target.select()
  }
}

onMounted(load)
</script>

<template>
  <section class="card">
    <div class="panel__head">
      <h2>网站设置</h2>
      <button type="button" class="btn btn--small" :disabled="loading" @click="load">
        刷新
      </button>
    </div>

    <p class="hint">集中管理全站配置；后续新增的配置项会继续加在这里。</p>

    <p v-if="error" class="inline-error" role="alert">{{ error }}</p>
    <p v-if="notice" class="hint" role="status">{{ notice }}</p>

    <section class="site-settings__section">
      <h3>分享设置</h3>
      <p class="hint">
        全局默认的每用户有效分享上限（已撤销、已过期、次数用尽不占额度）。
        用户详情可单独覆盖；调低不会删除已有分享，只阻止继续新建。
      </p>

      <form class="admin-form-inline" @submit.prevent="save">
        <label class="site-settings__field">
          <span>每用户有效分享上限</span>
          <input
            v-model.number="limit"
            type="number"
            min="1"
            max="10000"
            :disabled="saving || loading"
            @focus="selectAll"
          />
        </label>
        <button
          type="submit"
          class="btn btn--small btn--primary"
          :disabled="saving || loading"
        >
          {{ saving ? '保存中…' : '保存' }}
        </button>
      </form>

      <dl class="site-settings__meta">
        <div>
          <dt>最近更新</dt>
          <dd>{{ formatDate(data?.updated_at) }}</dd>
        </div>
        <div>
          <dt>更新人</dt>
          <dd>{{ data?.updated_by_username ?? '—' }}</dd>
        </div>
      </dl>
    </section>
  </section>
</template>

<style scoped>
.site-settings__section {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--border);
}

.site-settings__section h3 {
  margin: 0 0 8px;
  font-size: 14px;
}

.site-settings__field {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}

.site-settings__field input {
  width: 140px;
}

.site-settings__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 24px;
  margin: 14px 0 0;
  color: var(--text-muted);
  font-size: 12px;
}

.site-settings__meta div {
  display: flex;
  gap: 6px;
}

.site-settings__meta dt,
.site-settings__meta dd {
  margin: 0;
}
</style>
