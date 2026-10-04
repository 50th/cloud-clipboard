import { useCallback, useState } from 'react'

import { ClipboardItemCard } from '#src/components/ClipboardItemCard.tsx'
import { useClipboardStore } from '#src/stores/clipboardStore.ts'

interface ClipboardHistoryProps {
  /** 搜索框的即时值（防抖由 App 统一处理） */
  searchInput: string
  onSearchInputChange: (value: string) => void
  /** 清空全部（确认与提示由 App 统一处理） */
  onClearAll: () => void
}

/**
 * 左栏：历史记录及其全部操作。
 *
 * 按需求把「刷新、搜索、排序、清空全部」这些历史相关操作都收进左栏，
 * 与列表在视觉上成为一个整体。
 */
export function ClipboardHistory({
  searchInput,
  onSearchInputChange,
  onClearAll,
}: ClipboardHistoryProps) {
  const items = useClipboardStore((state) => state.items)
  const loading = useClipboardStore((state) => state.loading)
  const refreshing = useClipboardStore((state) => state.refreshing)
  const error = useClipboardStore((state) => state.error)
  const total = useClipboardStore((state) => state.total)
  const page = useClipboardStore((state) => state.page)
  const pages = useClipboardStore((state) => state.pages)
  const search = useClipboardStore((state) => state.search)
  const order = useClipboardStore((state) => state.order)
  const setOrder = useClipboardStore((state) => state.setOrder)
  const setPage = useClipboardStore((state) => state.setPage)
  const fetchItems = useClipboardStore((state) => state.fetchItems)
  const removeItem = useClipboardStore((state) => state.removeItem)

  const [deletingId, setDeletingId] = useState<string | null>(null)

  const handleDelete = useCallback(
    async (id: string) => {
      setDeletingId(id)
      try {
        await removeItem(id)
      } finally {
        setDeletingId(null)
      }
    },
    [removeItem],
  )

  return (
    <section className="card panel panel--history">
      <div className="panel__head">
        <h2>历史记录</h2>
        <span className="count">
          共 {total} 条{refreshing ? ' · 同步中…' : ''}
        </span>
      </div>

      {/* 搜索框：位于历史记录列表顶部 */}
      <label className="field field--tight">
        <span>搜索（标题或内容）</span>
        <input
          type="search"
          value={searchInput}
          placeholder="输入关键字，停止输入后自动搜索"
          onChange={(event) => onSearchInputChange(event.target.value)}
        />
      </label>

      {/* 历史相关操作：全部集中在左栏 */}
      <div className="actions actions--wrap history-actions">
        <button type="button" className="btn btn--small" onClick={() => void fetchItems()}>
          刷新
        </button>
        <select
          className="select select--small"
          value={order}
          onChange={(event) => void setOrder(event.target.value as 'asc' | 'desc')}
          aria-label="排序"
        >
          <option value="desc">最新优先</option>
          <option value="asc">最早优先</option>
        </select>
        <button
          type="button"
          className="btn btn--small btn--danger"
          onClick={onClearAll}
          disabled={total === 0}
        >
          清空全部
        </button>
      </div>

      {search && <p className="count">正在按「{search}」筛选，共 {total} 条命中</p>}
      {error && <p className="notice notice--err">{error}</p>}

      <div className="history-scroll">
        {loading ? (
          <p className="loading">加载中…</p>
        ) : items.length === 0 ? (
          <p className="empty">还没有记录。在右侧输入内容，或点「同步剪贴板」。</p>
        ) : (
          <div className="items">
            {items.map((item) => (
              <ClipboardItemCard
                key={item.id}
                item={item}
                onDelete={handleDelete}
                deleting={deletingId === item.id}
              />
            ))}
          </div>
        )}
      </div>

      {pages > 1 && (
        <nav className="pagination">
          <button
            type="button"
            className="btn btn--small"
            disabled={page <= 1}
            onClick={() => void setPage(page - 1)}
          >
            上一页
          </button>
          <span>
            第 {page} / {pages} 页
          </span>
          <button
            type="button"
            className="btn btn--small"
            disabled={page >= pages}
            onClick={() => void setPage(page + 1)}
          >
            下一页
          </button>
        </nav>
      )}
    </section>
  )
}
