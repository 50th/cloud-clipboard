import { useCallback, useEffect, useRef, useState } from 'react'

import { API_BASE_URL, getErrorMessage } from '#src/api/client.ts'
import { ClipboardHistory } from '#src/components/ClipboardHistory.tsx'
import { InputPanel } from '#src/components/InputPanel.tsx'
import { useClipboard } from '#src/hooks/useClipboard.ts'
import { useClipboardStore } from '#src/stores/clipboardStore.ts'
import { useUserStore } from '#src/stores/userStore.ts'

type Notice = { kind: 'ok' | 'err'; text: string } | null

export default function App() {
  const [notice, setNotice] = useState<Notice>(null)
  const [searchInput, setSearchInput] = useState('')

  // 单实例：剪贴板能力探测与「同步剪贴板」都由这一个 hook 提供
  const { supported, needsManualInput, syncFromClipboard } = useClipboard()

  const fetchItems = useClipboardStore((state) => state.fetchItems)
  const total = useClipboardStore((state) => state.total)
  const search = useClipboardStore((state) => state.search)
  const setSearch = useClipboardStore((state) => state.setSearch)
  const clearAll = useClipboardStore((state) => state.clearAll)

  const user = useUserStore((state) => state.user)
  const loadCurrentUser = useUserStore((state) => state.loadCurrentUser)

  // 首屏：拉取当前用户 + 列表
  useEffect(() => {
    void loadCurrentUser()
    void fetchItems()
  }, [fetchItems, loadCurrentUser])

  // 搜索防抖：停止输入 300ms 后查后端
  const skipFirstSearch = useRef(true)
  useEffect(() => {
    if (skipFirstSearch.current) {
      skipFirstSearch.current = false
      return
    }
    const timer = window.setTimeout(() => {
      void setSearch(searchInput)
    }, 300)
    return () => window.clearTimeout(timer)
  }, [searchInput, setSearch])

  const handleSync = useCallback(async () => {
    const result = await syncFromClipboard()
    setNotice({ kind: result.ok ? 'ok' : 'err', text: result.message })
    return result
  }, [syncFromClipboard])

  const handleClearAll = useCallback(async () => {
    if (total === 0) {
      return
    }
    if (!window.confirm(`确定清空全部 ${total} 条记录？此操作不可撤销。`)) {
      return
    }
    try {
      const removed = await clearAll()
      setNotice({ kind: 'ok', text: `已清空 ${removed} 条记录` })
    } catch (error) {
      setNotice({ kind: 'err', text: getErrorMessage(error) })
    }
  }, [clearAll, total])

  return (
    <div className="app">
      <header className="app__header">
        <h1>云剪贴板</h1>
        <p className="app__subtitle">
          后端 {API_BASE_URL}
          {user ? ` · 当前用户 ${user.username}` : ' · 演示用户'}
        </p>
      </header>

      {!supported && (
        <p className="warn">
          当前页面无法读取系统剪贴板（浏览器要求 https 或 localhost + 用户点击），
          可直接在右侧输入框粘贴内容。
        </p>
      )}
      {supported && needsManualInput && (
        <p className="warn">读取剪贴板被拒绝，请检查浏览器权限，或在右侧输入框手动粘贴。</p>
      )}

      {notice && (
        <p className={`notice ${notice.kind === 'ok' ? 'notice--ok' : 'notice--err'}`}>
          {notice.text}
        </p>
      )}

      {/* 左：历史记录（含搜索/排序/刷新/清空）  右：剪贴板输入 */}
      <div className="layout">
        <ClipboardHistory
          searchInput={searchInput}
          onSearchInputChange={setSearchInput}
          onClearAll={() => void handleClearAll()}
        />
        <InputPanel
          onNotice={({ kind, text }) => setNotice({ kind, text })}
          onSyncClipboard={handleSync}
        />
      </div>

      <footer className="footer">
        {search ? `筛选：${search} · ` : ''}
        阶段一 · 第 2 步：Web 端骨架与单端闭环（读取剪贴板 → 上传 → 列表展示 → 点击复制）
      </footer>
    </div>
  )
}
