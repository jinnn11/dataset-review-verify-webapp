import type {
  BulkDecisionResult,
  DecisionDraft,
  GroupRecord,
  HistoryResponse,
  ProgressSummary,
  QueueResponse,
  ReasonCode,
  UserInfo
} from './types'

function normalizeErrorMessage(raw: string, status: number): string {
  const fallback = `Request failed: ${status}`
  if (!raw) {
    return fallback
  }

  try {
    const parsed = JSON.parse(raw) as { detail?: unknown; message?: unknown }
    if (typeof parsed.detail === 'string' && parsed.detail.trim()) {
      return parsed.detail
    }
    if (Array.isArray(parsed.detail)) {
      const messages = parsed.detail
        .map((entry) => (entry && typeof entry === 'object' && 'msg' in entry ? String((entry as { msg: unknown }).msg) : ''))
        .filter((msg) => msg.trim())
      if (messages.length > 0) {
        return messages.join('; ')
      }
    }
    if (parsed.detail != null) {
      return String(parsed.detail)
    }
    if (typeof parsed.message === 'string' && parsed.message.trim()) {
      return parsed.message
    }
  } catch {
    // Response is not JSON; return plain text below.
  }

  return raw.trim() || fallback
}

async function request<T>(url: string, options: RequestInit = {}): Promise<T> {
  const { headers: optionHeaders, ...restOptions } = options

  const response = await fetch(url, {
    credentials: 'include',
    ...restOptions,
    headers: {
      'Content-Type': 'application/json',
      ...(optionHeaders ?? {})
    }
  })

  if (!response.ok) {
    const text = await response.text()
    throw new Error(normalizeErrorMessage(text, response.status))
  }

  if (response.status === 204) {
    return {} as T
  }

  return response.json() as Promise<T>
}

export async function login(username: string, password: string): Promise<UserInfo> {
  return request<UserInfo>('/api/v1/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password })
  })
}

export async function me(): Promise<UserInfo> {
  return request<UserInfo>('/api/v1/auth/me')
}

export async function logout(csrfToken: string): Promise<void> {
  await request('/api/v1/auth/logout', {
    method: 'POST',
    headers: {
      'X-CSRF-Token': csrfToken
    }
  })
}

export async function fetchQueue(cursor: string | null, search: string): Promise<QueueResponse> {
  const query = new URLSearchParams()
  query.set('limit', '50')
  if (cursor) {
    query.set('cursor', cursor)
  }
  if (search.trim()) {
    query.set('search', search.trim())
  }

  return request<QueueResponse>(`/api/v1/review/queue?${query.toString()}`)
}

export async function fetchHistory(cursor: string | null, search: string): Promise<HistoryResponse> {
  const query = new URLSearchParams()
  query.set('limit', '100')
  if (cursor) {
    query.set('cursor', cursor)
  }
  if (search.trim()) {
    query.set('search', search.trim())
  }
  return request<HistoryResponse>(`/api/v1/review/history?${query.toString()}`)
}

export async function saveDecisions(groupId: number, decisions: DecisionDraft[], csrfToken: string): Promise<BulkDecisionResult> {
  if (!decisions.length) {
    return { saved: 0, saved_image_ids: [], skipped_image_ids: [] }
  }

  const reasonByState: Record<DecisionDraft['state'], ReasonCode> = {
    keep: 'count_matches',
    delete: 'extra_same_class'
  }

  const payload = {
    decisions: decisions.map((item) => ({
      group_id: groupId,
      image_id: item.image_id,
      state: item.state,
      reason_code: reasonByState[item.state],
      notes: ''
    }))
  }

  const response = await request<BulkDecisionResult>('/api/v1/review/decision/bulk', {
    method: 'POST',
    headers: {
      'X-CSRF-Token': csrfToken
    },
    body: JSON.stringify(payload)
  })
  return response
}

export async function fetchGroupById(groupId: number): Promise<GroupRecord> {
  return request<GroupRecord>(`/api/v1/review/group/${groupId}`)
}

export async function saveDecision(
  groupId: number,
  imageId: number,
  state: DecisionDraft['state'],
  csrfToken: string
): Promise<void> {
  const reasonByState: Record<DecisionDraft['state'], ReasonCode> = {
    keep: 'count_matches',
    delete: 'extra_same_class'
  }

  await request('/api/v1/review/decision', {
    method: 'POST',
    headers: {
      'X-CSRF-Token': csrfToken
    },
    body: JSON.stringify({
      group_id: groupId,
      image_id: imageId,
      state,
      reason_code: reasonByState[state],
      notes: ''
    })
  })
}

export async function fetchProgress(): Promise<ProgressSummary> {
  return request<ProgressSummary>('/api/v1/progress/summary')
}

export async function runIngestion(csrfToken: string): Promise<void> {
  await request('/api/v1/ingest/run', {
    method: 'POST',
    headers: {
      'X-CSRF-Token': csrfToken
    }
  })
}

export async function softDeleteImage(imageId: number, csrfToken: string): Promise<void> {
  await request(`/api/v1/files/soft-delete/${imageId}`, {
    method: 'POST',
    headers: {
      'X-CSRF-Token': csrfToken
    }
  })
}

export async function undoSoftDeleteForImage(imageId: number, csrfToken: string): Promise<void> {
  await request(`/api/v1/files/undo/${imageId}`, {
    method: 'POST',
    headers: {
      'X-CSRF-Token': csrfToken
    }
  })
}

export async function undoDecisionForImage(imageId: number, csrfToken: string): Promise<void> {
  await request(`/api/v1/review/undo/${imageId}`, {
    method: 'POST',
    headers: {
      'X-CSRF-Token': csrfToken
    }
  })
}

export function maskUrl(groupId: number): string {
  return `/api/v1/media/mask/${groupId}`
}

export function imageUrl(imageId: number): string {
  return `/api/v1/media/image/${imageId}`
}
