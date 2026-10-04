import { useCallback, useEffect, useState } from 'react'

import { getErrorMessage } from '#src/api/client.ts'
import { useAutoSave } from '#src/hooks/useAutoSave.ts'
import { useClipboardStore } from '#src/stores/clipboardStore.ts'
import { byteSize, formatBytes } from '#src/utils/format.ts'

interface InputPanelProps {
  /** 上传结果回调（成功/失败提示） */
  onNotice: (notice: { kind: 'ok' | 'err'; text: string }) => void
  /** 读取系统剪贴板并上传 */
  onSyncClipboard: () => Promise<{ ok: boolean; message: string }>
}

/** 右侧面板：标题 + 正文输入，支持自动保存。 */
export function InputPanel({ onNotice, onSyncClipboard }: InputPanelProps) {
  const uploadText = useClipboardStore((state) => state.uploadText)

  const [title, setTitle] = useState('')
  const [text, setText] = useState('')
  const [autoSave, setAutoSave] = useState(true)

  const clearInput = useCallback(() => {
    setTitle('')
    setText('')
  }, [])

  const { saving, error: autoSaveError, lastSaved, markSaved } = useAutoSave({
    text,
    extra: title,
    enabled: autoSave,
    onSave: async () => {
      try {
        const { item } = await uploadText(text, title)
        onNotice({ kind: 'ok', text: `已自动保存：${item.title}` })
      } catch (err) {
        throw new Error(getErrorMessage(err))
      }
    },
  })

  // 自动保存失败时提示一次
  useEffect(() => {
    if (autoSaveError) {
      onNotice({ kind: 'err', text: `自动保存失败：${autoSaveError}` })
    }
  }, [autoSaveError, onNotice])

  const handleManualUpload = useCallback(async () => {
    if (text.trim() === '') {
      return
    }
    try {
      const { item, deduped } = await uploadText(text, title)
      // 手动上传成功后标记已保存，避免自动保存重复上传同一内容
      markSaved(text)
      onNotice({
        kind: 'ok',
        text: deduped
          ? `内容已存在，已刷新时间戳：${item.title}`
          : `已上传：${item.title}`,
      })
    } catch (err) {
      onNotice({ kind: 'err', text: getErrorMessage(err) })
    }
  }, [markSaved, onNotice, text, title, uploadText])

  const handleSyncClipboard = useCallback(async () => {
    const result = await onSyncClipboard()
    if (result.ok) {
      // 系统剪贴板内容已入库，把当前输入标记为已保存，避免自动保存再传一遍
      markSaved(text)
    }
  }, [markSaved, onSyncClipboard, text])

  const isDirty = text.trim() !== '' && lastSaved === null
  const statusText = !autoSave
    ? '已关闭'
    : saving
      ? '保存中…'
      : text.trim() === ''
        ? '等待输入'
        : isDirty
          ? '待保存'
          : `已保存 ${
              new Date(lastSaved ?? Date.now()).toLocaleTimeString('zh-CN', {
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
              })
            }`

  return (
    <section className="card panel panel--input">
      <div className="panel__head panel__head--split">
        <h2>剪贴板输入</h2>
        <span className="hint">Ctrl+Enter 快速上传</span>
      </div>

      <label className="field field--tight">
        <span>标题（留空将自动生成，如「demo · 10-03 12:55」）</span>
        <input
          value={title}
          placeholder="不填也可以，会自动生成标题"
          onChange={(event) => setTitle(event.target.value)}
          maxLength={200}
        />
      </label>

      <label className="field field--grow">
        <span>内容（{text ? formatBytes(byteSize(text)) : '0 B'}）</span>
        <textarea
          className="editor"
          value={text}
          placeholder="在这里输入或粘贴内容，也可以点下面的「同步剪贴板」直接抓取系统剪贴板"
          onChange={(event) => setText(event.target.value)}
          onKeyDown={(event) => {
            if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
              event.preventDefault()
              void handleManualUpload()
            }
          }}
        />
      </label>

      <div className="actions actions--wrap">
        <button
          type="button"
          className="btn btn--primary"
          onClick={() => void handleManualUpload()}
          disabled={text.trim() === ''}
        >
          上传
        </button>
        <button type="button" className="btn btn--primary" onClick={() => void handleSyncClipboard()}>
          同步剪贴板
        </button>
        <button
          type="button"
          className="btn"
          onClick={clearInput}
          disabled={text === '' && title === ''}
        >
          清空输入
        </button>
      </div>

      <div className="autosave">
        <label className="switch">
          <input
            type="checkbox"
            checked={autoSave}
            onChange={(event) => setAutoSave(event.target.checked)}
          />
          <span>自动保存（停止输入 1.5 秒后上传）</span>
        </label>
        <span className="autosave__status">{statusText}</span>
      </div>
    </section>
  )
}
