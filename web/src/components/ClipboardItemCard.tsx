import { useCallback, useState } from 'react'

import type { ClipboardItem } from '#src/api/client.ts'
import { useCopy } from '#src/hooks/useCopy.ts'
import { formatBytes, formatRelative } from '#src/utils/format.ts'

interface ClipboardItemCardProps {
  item: ClipboardItem
  onDelete: (id: string) => void
  deleting: boolean
}

/** 单条剪贴板记录：展示标题与正文、复制回剪贴板、删除。 */
export function ClipboardItemCard({ item, onDelete, deleting }: ClipboardItemCardProps) {
  const { copied, error, copy } = useCopy()
  const [expanded, setExpanded] = useState(false)

  const size = item.metadata?.size
  const long = item.content.length > 160

  const handleCopy = useCallback(() => {
    void copy(item.content)
  }, [copy, item.content])

  const handleDelete = useCallback(() => {
    onDelete(item.id)
  }, [item.id, onDelete])

  return (
    <article className="item">
      <header className="item__head">
        <h3 className="item__title" title={item.title}>
          {item.title}
        </h3>
        <span className="item__time" title={item.created_at}>
          {formatRelative(item.created_at)}
        </span>
      </header>

      <pre className="item__content">
        {long && !expanded ? `${item.content.slice(0, 160)}…` : item.content}
      </pre>

      <div className="item__actions">
        <button type="button" className="btn btn--small btn--primary" onClick={handleCopy}>
          {copied ? '✓ 已复制' : '复制'}
        </button>
        {long && (
          <button
            type="button"
            className="btn btn--small"
            onClick={() => setExpanded((value) => !value)}
          >
            {expanded ? '收起' : '展开'}
          </button>
        )}
        <button
          type="button"
          className="btn btn--small btn--danger"
          onClick={handleDelete}
          disabled={deleting}
        >
          {deleting ? '删除中…' : '删除'}
        </button>
        <span className="item__meta">
          {item.content_type}
          {typeof size === 'number' ? ` · ${formatBytes(size)}` : ''}
          {item.updated_at !== item.created_at ? ' · 已更新' : ''}
        </span>
        {error && <span className="warn">{error}</span>}
      </div>
    </article>
  )
}
