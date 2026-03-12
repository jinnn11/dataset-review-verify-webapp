import { useCallback, useEffect, useMemo, useRef, useState, type UIEvent } from 'react'

import {
  fetchHistory,
  fetchProgress,
  fetchGroupById,
  fetchQueue,
  imageUrl,
  maskUrl,
  runIngestion,
  saveDecisions,
  undoDecisionForImage,
  softDeleteImage,
  undoSoftDeleteForImage
} from '../api'
import type { GroupRecord, HistoryItem, ProgressSummary, ReviewState, UserRole } from '../types'
import { ImageCard } from './ImageCard'
import { TopBar } from './TopBar'

interface ReviewDashboardProps {
  username: string
  role: UserRole
  csrfToken: string
  onLogout: () => Promise<void>
}

type DecisionChoice = Extract<ReviewState, 'keep' | 'delete'>
type DecisionMap = Record<number, DecisionChoice>

interface LastBatchAction {
  groupId: number
  imageIds: number[]
  state: DecisionChoice
  softDeletedImageIds: number[]
  createdAt: number
}

const newYorkDateFormatter = new Intl.DateTimeFormat('en-US', {
  timeZone: 'America/New_York',
  year: 'numeric',
  month: 'short',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hour12: true,
  timeZoneName: 'short'
})

function isResolvedState(state: ReviewState | null | undefined): state is DecisionChoice {
  return state === 'keep' || state === 'delete'
}

function formatNewYorkTime(value: string): string {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return value
  }
  return newYorkDateFormatter.format(parsed)
}

function buildInitialDecisionMap(group: GroupRecord | null): DecisionMap {
  if (!group) {
    return {}
  }

  const map: DecisionMap = {}
  for (const image of group.generated_images) {
    if (isResolvedState(image.current_state)) {
      map[image.id] = image.current_state
    }
  }
  return map
}

export function ReviewDashboard({ username, role, csrfToken, onLogout }: ReviewDashboardProps) {
  const [viewMode, setViewMode] = useState<'review' | 'history'>('review')
  const [queue, setQueue] = useState<GroupRecord[]>([])
  const [nextCursor, setNextCursor] = useState<string | null>(null)
  const [selectedGroupIndex, setSelectedGroupIndex] = useState(0)
  const [focusedImageIndex, setFocusedImageIndex] = useState(0)
  const [search, setSearch] = useState('')

  const [decisions, setDecisions] = useState<DecisionMap>({})
  const [pendingSaveIds, setPendingSaveIds] = useState<number[]>([])
  const [softDeletedImageIds, setSoftDeletedImageIds] = useState<number[]>([])
  const [selectedImageIds, setSelectedImageIds] = useState<number[]>([])
  const [lastBatchAction, setLastBatchAction] = useState<LastBatchAction | null>(null)

  const [progress, setProgress] = useState<ProgressSummary | null>(null)
  const [historyItems, setHistoryItems] = useState<HistoryItem[]>([])
  const [historyCursor, setHistoryCursor] = useState<string | null>(null)
  const [historyLoading, setHistoryLoading] = useState(false)
  const historyRequestInFlightRef = useRef(false)
  const [loading, setLoading] = useState(false)
  const [autoAdvancing, setAutoAdvancing] = useState(false)
  const [reviewFinished, setReviewFinished] = useState(false)
  const [isApplyingBulkAction, setIsApplyingBulkAction] = useState(false)
  const [isUndoingBatch, setIsUndoingBatch] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const currentGroup = queue[selectedGroupIndex] ?? null

  const reviewableImages = useMemo(
    () => (currentGroup ? currentGroup.generated_images.filter((image) => !softDeletedImageIds.includes(image.id)) : []),
    [currentGroup, softDeletedImageIds]
  )

  const remainingImages = useMemo(
    () =>
      reviewableImages.filter((image) => {
        const state = decisions[image.id] ?? image.current_state
        return !isResolvedState(state)
      }),
    [decisions, reviewableImages]
  )

  const visibleImages = useMemo(() => remainingImages.slice(0, 4), [remainingImages])

  const currentGroupComplete = useMemo(() => {
    if (!currentGroup) {
      return false
    }
    return remainingImages.length === 0 && pendingSaveIds.length === 0
  }, [currentGroup, pendingSaveIds.length, remainingImages.length])

  const refreshProgress = useCallback(async () => {
    const data = await fetchProgress()
    setProgress(data)
  }, [])

  const loadHistory = useCallback(
    async (reset: boolean) => {
      if (historyRequestInFlightRef.current) {
        return
      }
      historyRequestInFlightRef.current = true
      setHistoryLoading(true)
      setError('')
      setMessage('')
      try {
        const cursor = reset ? null : historyCursor
        const response = await fetchHistory(cursor, search)
        setHistoryItems((previous) => (reset ? response.items : [...previous, ...response.items]))
        setHistoryCursor(response.next_cursor)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load history')
      } finally {
        historyRequestInFlightRef.current = false
        setHistoryLoading(false)
      }
    },
    [historyCursor, search]
  )

  const loadQueue = useCallback(
    async (reset: boolean) => {
      setLoading(true)
      setError('')
      setMessage('')
      try {
        const cursor = reset ? null : nextCursor
        const response = await fetchQueue(cursor, search)
        setQueue((previous) => (reset ? response.items : [...previous, ...response.items]))
        setNextCursor(response.next_cursor)
        setReviewFinished(false)
        if (reset) {
          setSelectedGroupIndex(0)
          setFocusedImageIndex(0)
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load queue')
      } finally {
        setLoading(false)
      }
    },
    [nextCursor, search]
  )

  const advanceToNextGroup = useCallback(async (): Promise<boolean> => {
    if (selectedGroupIndex < queue.length - 1) {
      setSelectedGroupIndex((idx) => idx + 1)
      return true
    }

    if (!nextCursor) {
      return false
    }

    setLoading(true)
    try {
      const response = await fetchQueue(nextCursor, search)
      if (!response.items.length) {
        setNextCursor(response.next_cursor)
        return false
      }

      const startIndex = queue.length
      setQueue((previous) => [...previous, ...response.items])
      setNextCursor(response.next_cursor)
      setSelectedGroupIndex(startIndex)
      setFocusedImageIndex(0)
      return true
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load next mask')
      return false
    } finally {
      setLoading(false)
    }
  }, [nextCursor, queue.length, search, selectedGroupIndex])

  useEffect(() => {
    void loadQueue(true)
    void refreshProgress()
    // Intentionally run once on mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshProgress])

  useEffect(() => {
    if (viewMode !== 'history') {
      return
    }
    void loadHistory(true)
  }, [loadHistory, viewMode])

  useEffect(() => {
    setDecisions(buildInitialDecisionMap(currentGroup))
    setPendingSaveIds([])
    setSoftDeletedImageIds([])
    setSelectedImageIds([])
    setFocusedImageIndex(0)
    setAutoAdvancing(false)
    setReviewFinished(false)
  }, [currentGroup?.id])

  const refreshGroupById = useCallback(
    async (groupId: number) => {
      try {
        const updatedGroup = await fetchGroupById(groupId)
        const targetIndex = queue.findIndex((group) => group.id === groupId)
        if (targetIndex >= 0) {
          setQueue((previous) => previous.map((group) => (group.id === groupId ? updatedGroup : group)))
          setSelectedGroupIndex(targetIndex)
        } else {
          setQueue((previous) => [updatedGroup, ...previous])
          setSelectedGroupIndex(0)
        }

        setDecisions(buildInitialDecisionMap(updatedGroup))
        setPendingSaveIds([])
        setSoftDeletedImageIds([])
        setSelectedImageIds([])
        setFocusedImageIndex(0)
      } catch {
        await loadQueue(true)
      }
    },
    [loadQueue, queue]
  )

  useEffect(() => {
    if (focusedImageIndex > Math.max(visibleImages.length - 1, 0)) {
      setFocusedImageIndex(Math.max(visibleImages.length - 1, 0))
    }
  }, [focusedImageIndex, visibleImages.length])

  useEffect(() => {
    const visibleIds = new Set(visibleImages.map((image) => image.id))
    setSelectedImageIds((previous) => previous.filter((id) => visibleIds.has(id)))
  }, [visibleImages])

  useEffect(() => {
    if (viewMode !== 'review' || !currentGroup || !currentGroupComplete || autoAdvancing || reviewFinished) {
      return
    }

    let cancelled = false

    const run = async () => {
      setAutoAdvancing(true)
      const advanced = await advanceToNextGroup()
      if (cancelled) {
        return
      }
      if (!advanced) {
        setMessage('All masks are complete.')
        setReviewFinished(true)
      }
      setAutoAdvancing(false)
    }

    void run()

    return () => {
      cancelled = true
    }
  }, [advanceToNextGroup, autoAdvancing, currentGroup, currentGroupComplete, reviewFinished, viewMode])

  const toggleImageSelection = useCallback(
    (imageId: number) => {
      if (pendingSaveIds.includes(imageId) || isApplyingBulkAction || isUndoingBatch) {
        return
      }
      setSelectedImageIds((previous) =>
        previous.includes(imageId) ? previous.filter((id) => id !== imageId) : [...previous, imageId]
      )
    },
    [isApplyingBulkAction, isUndoingBatch, pendingSaveIds]
  )

  const applyBulkDecision = useCallback(
    async (state: DecisionChoice) => {
      if (!currentGroup || isApplyingBulkAction || isUndoingBatch) {
        return
      }

      const visibleIdSet = new Set(visibleImages.map((image) => image.id))
      const targetImageIds = selectedImageIds.filter((id) => visibleIdSet.has(id) && !pendingSaveIds.includes(id))
      if (targetImageIds.length === 0) {
        setError('')
        setMessage('Select at least one image to apply Keep/Delete.')
        return
      }

      setError('')
      setMessage('')
      setIsApplyingBulkAction(true)

      const previousDecisions = new Map<number, DecisionChoice | undefined>()
      for (const imageId of targetImageIds) {
        previousDecisions.set(imageId, decisions[imageId])
      }

      setDecisions((previous) => {
        const next = { ...previous }
        for (const imageId of targetImageIds) {
          next[imageId] = state
        }
        return next
      })
      setPendingSaveIds((previous) => [...new Set([...previous, ...targetImageIds])])
      setSelectedImageIds((previous) => previous.filter((id) => !targetImageIds.includes(id)))

      try {
        if (state === 'delete') {
          if (role !== 'admin') {
            setError('Soft delete requires admin access.')
            setDecisions((previous) => {
              const next = { ...previous }
              for (const imageId of targetImageIds) {
                const prior = previousDecisions.get(imageId)
                if (prior) {
                  next[imageId] = prior
                } else {
                  delete next[imageId]
                }
              }
              return next
            })
            setSelectedImageIds((previous) => [...new Set([...previous, ...targetImageIds])])
            return
          }

          const softDeletedSuccess: number[] = []
          const softDeleteFailures: number[] = []
          for (const imageId of targetImageIds) {
            try {
              await softDeleteImage(imageId, csrfToken)
              softDeletedSuccess.push(imageId)
            } catch {
              softDeleteFailures.push(imageId)
            }
          }

          if (softDeletedSuccess.length > 0) {
            setSoftDeletedImageIds((previous) => [...new Set([...previous, ...softDeletedSuccess])])
            setLastBatchAction({
              groupId: currentGroup.id,
              imageIds: [...softDeletedSuccess],
              state: 'delete',
              softDeletedImageIds: [...softDeletedSuccess],
              createdAt: Date.now()
            })
          } else {
            setLastBatchAction(null)
          }

          if (softDeleteFailures.length > 0) {
            setDecisions((previous) => {
              const next = { ...previous }
              for (const imageId of softDeleteFailures) {
                const prior = previousDecisions.get(imageId)
                if (prior) {
                  next[imageId] = prior
                } else {
                  delete next[imageId]
                }
              }
              return next
            })
            setSelectedImageIds((previous) => [...new Set([...previous, ...softDeleteFailures])])
            setError(`Soft delete failed for IDs: ${softDeleteFailures.join(', ')}.`)
          }
          setMessage(`Soft deleted ${softDeletedSuccess.length}/${targetImageIds.length} images.`)
        } else {
          const bulkResult = await saveDecisions(
            currentGroup.id,
            targetImageIds.map((imageId) => ({ image_id: imageId, state })),
            csrfToken
          )
          const savedImageIds = bulkResult.saved_image_ids
          const skippedImageIds = bulkResult.skipped_image_ids

          if (skippedImageIds.length > 0) {
            setDecisions((previous) => {
              const next = { ...previous }
              for (const imageId of skippedImageIds) {
                delete next[imageId]
              }
              return next
            })
            setSelectedImageIds((previous) => [...new Set([...previous, ...skippedImageIds])])
          }

          if (savedImageIds.length > 0) {
            setLastBatchAction({
              groupId: currentGroup.id,
              imageIds: [...savedImageIds],
              state: 'keep',
              softDeletedImageIds: [],
              createdAt: Date.now()
            })
          } else {
            setLastBatchAction(null)
          }

          const summaryParts = [`Saved ${bulkResult.saved}/${targetImageIds.length} decisions as keep.`]
          if (skippedImageIds.length > 0) {
            summaryParts.push(`Skipped IDs: ${skippedImageIds.join(', ')}.`)
          }
          setMessage(summaryParts.join(' '))
        }

        await refreshProgress()
      } catch (err) {
        setDecisions((previous) => {
          const next = { ...previous }
          for (const imageId of targetImageIds) {
            const prior = previousDecisions.get(imageId)
            if (prior) {
              next[imageId] = prior
            } else {
              delete next[imageId]
            }
          }
          return next
        })
        setSelectedImageIds((previous) => [...new Set([...previous, ...targetImageIds])])
        setError(err instanceof Error ? err.message : 'Bulk auto-save failed')
      } finally {
        setPendingSaveIds((previous) => previous.filter((id) => !targetImageIds.includes(id)))
        setIsApplyingBulkAction(false)
      }
    },
    [
      csrfToken,
      currentGroup,
      decisions,
      isApplyingBulkAction,
      isUndoingBatch,
      pendingSaveIds,
      refreshProgress,
      role,
      selectedImageIds,
      visibleImages
    ]
  )

  const undoLastBatch = useCallback(async () => {
    if (!lastBatchAction || isUndoingBatch) {
      return
    }

    setError('')
    setMessage('')
    setIsUndoingBatch(true)

    const failedSoftUndoIds: number[] = []
    const failedDecisionUndoIds: number[] = []
    let restoredCount = 0

    try {
      if (lastBatchAction.state === 'keep') {
        const keepUndoResults = await Promise.allSettled(
          lastBatchAction.imageIds.map(async (imageId) => undoDecisionForImage(imageId, csrfToken))
        )
        keepUndoResults.forEach((result, index) => {
          const imageId = lastBatchAction.imageIds[index]
          if (result.status === 'fulfilled') {
            restoredCount += 1
            return
          }
          failedDecisionUndoIds.push(imageId)
        })
      } else {
        const deleteUndoResults = await Promise.allSettled(
          lastBatchAction.softDeletedImageIds.map(async (imageId) => undoSoftDeleteForImage(imageId, csrfToken))
        )

        const restoredFromSoftDelete: number[] = []
        deleteUndoResults.forEach((result, index) => {
          const imageId = lastBatchAction.softDeletedImageIds[index]
          if (result.status === 'fulfilled') {
            restoredCount += 1
            restoredFromSoftDelete.push(imageId)
            return
          }
          failedSoftUndoIds.push(imageId)
        })

        if (restoredFromSoftDelete.length > 0) {
          setSoftDeletedImageIds((previous) => previous.filter((id) => !restoredFromSoftDelete.includes(id)))
        }
      }

      await refreshGroupById(lastBatchAction.groupId)
      await refreshProgress()

      const totalToUndo =
        lastBatchAction.state === 'delete' ? lastBatchAction.softDeletedImageIds.length : lastBatchAction.imageIds.length
      const failedIds = [...failedSoftUndoIds, ...failedDecisionUndoIds]

      if (failedIds.length === 0) {
        setLastBatchAction(null)
        setMessage(`Undo restored ${restoredCount}/${totalToUndo} images.`)
        return
      }

      if (lastBatchAction.state === 'keep') {
        setLastBatchAction({
          ...lastBatchAction,
          imageIds: [...failedDecisionUndoIds],
          createdAt: Date.now()
        })
      } else {
        setLastBatchAction({
          ...lastBatchAction,
          softDeletedImageIds: [...failedSoftUndoIds],
          imageIds: [...failedSoftUndoIds],
          createdAt: Date.now()
        })
      }

      setError(`Undo restored ${restoredCount}/${totalToUndo}. Retry for image IDs: ${failedIds.join(', ')}.`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Undo failed')
    } finally {
      setIsUndoingBatch(false)
    }
  }, [csrfToken, isUndoingBatch, lastBatchAction, refreshGroupById, refreshProgress])

  useEffect(() => {
    const listener = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null
      if (target && ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)) {
        return
      }
      if (viewMode !== 'review') {
        return
      }

      if (event.key.toLowerCase() === 'k') {
        event.preventDefault()
        void applyBulkDecision('keep')
      }
      if (event.key.toLowerCase() === 'd') {
        event.preventDefault()
        if (role === 'admin') {
          void applyBulkDecision('delete')
        }
      }
      if (event.key === 'Escape') {
        event.preventDefault()
        setSelectedImageIds([])
      }
      if (event.key === 'ArrowRight') {
        if (!currentGroup || visibleImages.length === 0) {
          return
        }
        event.preventDefault()
        setFocusedImageIndex((idx) => Math.min(idx + 1, visibleImages.length - 1))
      }
      if (event.key === 'ArrowLeft') {
        if (!currentGroup || visibleImages.length === 0) {
          return
        }
        event.preventDefault()
        setFocusedImageIndex((idx) => Math.max(idx - 1, 0))
      }
      if (event.key === 'ArrowDown') {
        if (!currentGroup || visibleImages.length === 0) {
          return
        }
        event.preventDefault()
        setFocusedImageIndex((idx) => Math.min(idx + 2, visibleImages.length - 1))
      }
      if (event.key === 'ArrowUp') {
        if (!currentGroup || visibleImages.length === 0) {
          return
        }
        event.preventDefault()
        setFocusedImageIndex((idx) => Math.max(idx - 2, 0))
      }
      if (event.key === ' ') {
        if (!currentGroup || visibleImages.length === 0) {
          return
        }
        const focused = visibleImages[focusedImageIndex]
        if (!focused) {
          return
        }
        event.preventDefault()
        toggleImageSelection(focused.id)
      }
    }

    window.addEventListener('keydown', listener)
    return () => window.removeEventListener('keydown', listener)
  }, [applyBulkDecision, currentGroup, focusedImageIndex, toggleImageSelection, viewMode, visibleImages])

  const onSearchSubmit = () => {
    if (viewMode === 'history') {
      void loadHistory(true)
      return
    }
    void loadQueue(true)
  }

  const onIngest = async () => {
    setError('')
    try {
      await runIngestion(csrfToken)
      setMessage('Ingestion complete. Queue refreshed.')
      await loadQueue(true)
      await refreshProgress()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ingestion failed')
    }
  }

  const selectedVisibleCount = selectedImageIds.length

  const onHistoryScroll = (event: UIEvent<HTMLDivElement>) => {
    if (historyRequestInFlightRef.current || !historyCursor) {
      return
    }
    const target = event.currentTarget
    const remaining = target.scrollHeight - target.scrollTop - target.clientHeight
    if (remaining < 180) {
      void loadHistory(false)
    }
  }

  return (
    <div className="review-shell">
      <TopBar
        username={username}
        role={role}
        progress={progress}
        search={search}
        onSearchChange={setSearch}
        onSearchSubmit={onSearchSubmit}
        onLogout={onLogout}
        onIngest={onIngest}
      />
      <div className="mode-switch">
        <button
          type="button"
          className={viewMode === 'review' ? 'mode-button active' : 'mode-button'}
          onClick={() => setViewMode('review')}
        >
          Review Queue
        </button>
        <button
          type="button"
          className={viewMode === 'history' ? 'mode-button active' : 'mode-button'}
          onClick={() => setViewMode('history')}
        >
          Review History
        </button>
      </div>
      {viewMode === 'review' ? (
      <main className="workspace">
        <aside className="mask-panel">
          <div className="panel-heading">
            <h2>{currentGroup ? currentGroup.group_key : 'No mask loaded'}</h2>
            <p>{currentGroup ? `Mask ID ${currentGroup.id}` : 'Run ingestion or adjust filters.'}</p>
          </div>
          {currentGroup ? (
            <img src={maskUrl(currentGroup.id)} alt={`Mask ${currentGroup.group_key}`} className="mask-image" />
          ) : (
            <div className="empty-mask">No mask to display</div>
          )}
          <div className="group-controls">
            <span className="autosave-label">Autosave is ON. Bulk Keep/Delete saves instantly.</span>
          </div>
        </aside>

        <section className="grid-panel">
          <div className="grid-header">
            <h3>Generated Images</h3>
            <p>Hotkeys: Space select, K Keep, D Soft delete (admin), Esc clear, Arrow keys move focus</p>
            {currentGroup ? (
              <p>
                Showing {visibleImages.length} cards. Remaining for this mask: {remainingImages.length}.
              </p>
            ) : null}
            <p>Selected {selectedVisibleCount} images.</p>
          </div>
          {error ? <p className="error-message">{error}</p> : null}
          {message ? <p className="success-message">{message}</p> : null}
          <div className="grid-workspace">
            <div className="corner-controls corner-controls-top">
              <button
                type="button"
                className="corner-action keep-corner"
                disabled={!currentGroup || selectedVisibleCount === 0 || isApplyingBulkAction || isUndoingBatch}
                onClick={() => void applyBulkDecision('keep')}
              >
                Keep Selected
              </button>
              <button
                type="button"
                className="corner-action delete-corner"
                disabled={!currentGroup || selectedVisibleCount === 0 || isApplyingBulkAction || isUndoingBatch || role !== 'admin'}
                onClick={() => void applyBulkDecision('delete')}
              >
                Soft Delete Selected
              </button>
            </div>

            <div className="image-grid">
              {visibleImages.map((image, index) => (
                <ImageCard
                  key={image.id}
                  image={image}
                  isFocused={index === focusedImageIndex}
                  isSelected={selectedImageIds.includes(image.id)}
                  onFocus={() => setFocusedImageIndex(index)}
                  onToggleSelect={() => toggleImageSelection(image.id)}
                />
              ))}
            </div>

            <div className="corner-controls corner-controls-bottom">
              <button
                type="button"
                className="corner-action undo-corner"
                disabled={!lastBatchAction || isApplyingBulkAction || isUndoingBatch}
                onClick={() => void undoLastBatch()}
                title={
                  lastBatchAction
                    ? `Undo ${lastBatchAction.state} batch from mask ${lastBatchAction.groupId}`
                    : 'No batch to undo'
                }
              >
                Undo Last Batch
              </button>
            </div>
          </div>
        </section>
      </main>
      ) : (
        <main className="history-workspace">
          <section className="history-panel">
            <div className="history-header">
              <h3>Review History</h3>
              <p>Scroll to browse all Keep and Soft Delete decisions with mask/image pairs.</p>
            </div>
            {error ? <p className="error-message">{error}</p> : null}
            {message ? <p className="success-message">{message}</p> : null}
            <div className="history-list" onScroll={onHistoryScroll}>
              {historyItems.map((item) => (
                <article key={item.decision_id} className="history-row">
                  <div className="history-meta">
                    <span className={`history-state ${item.state === 'delete' ? 'delete' : 'keep'}`}>
                      {item.state === 'delete' ? 'Soft Deleted' : 'Kept'}
                    </span>
                    <h4>{item.group_key}</h4>
                    <p>Image ID {item.image_id}</p>
                    <p>{formatNewYorkTime(item.decided_at)}</p>
                  </div>
                  <div className="history-images">
                    <div className="history-image-card">
                      <p>Mask</p>
                      <img src={maskUrl(item.group_id)} alt={`Mask ${item.group_key}`} loading="lazy" />
                    </div>
                    <div className="history-image-card">
                      <p>Generated</p>
                      <img src={imageUrl(item.image_id)} alt={`Generated ${item.image_id}`} loading="lazy" />
                    </div>
                  </div>
                </article>
              ))}
              {historyLoading ? <p className="history-status">Loading history...</p> : null}
              {!historyLoading && historyItems.length === 0 ? <p className="history-status">No review history yet.</p> : null}
              {!historyLoading && historyItems.length > 0 && !historyCursor ? (
                <p className="history-status">End of history.</p>
              ) : null}
            </div>
          </section>
        </main>
      )}
    </div>
  )
}
