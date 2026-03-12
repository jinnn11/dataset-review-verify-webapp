export type UserRole = 'admin' | 'reviewer'

export type ReviewState = 'keep' | 'delete' | 'needs_review'

export type ReasonCode =
  | 'count_matches'
  | 'different_class_allowed'
  | 'extra_same_class'
  | 'policy_violation'
  | 'uncertain'

export interface UserInfo {
  username: string
  role: UserRole
  csrf_token: string
}

export interface GeneratedImageRecord {
  id: number
  image_path: string
  status: string
  current_state: ReviewState | null
  current_reason: ReasonCode | null
  current_notes: string
  current_reviewer: string | null
  current_decision_at: string | null
}

export interface GroupRecord {
  id: number
  group_key: string
  mask_path: string
  generated_images: GeneratedImageRecord[]
}

export interface QueueResponse {
  items: GroupRecord[]
  next_cursor: string | null
}

export interface HistoryItem {
  decision_id: number
  group_id: number
  group_key: string
  mask_path: string
  image_id: number
  image_path: string
  image_status: string
  state: Extract<ReviewState, 'keep' | 'delete'>
  reason_code: ReasonCode
  reviewer: string | null
  decided_at: string
}

export interface HistoryResponse {
  items: HistoryItem[]
  next_cursor: string | null
}

export interface BulkDecisionResult {
  saved: number
  saved_image_ids: number[]
  skipped_image_ids: number[]
}

export interface ProgressSummary {
  total_images: number
  active_images: number
  trashed_images: number
  reviewed: number
  keep: number
  delete: number
  needs_review: number
  remaining: number
}

export interface DecisionDraft {
  image_id: number
  state: Extract<ReviewState, 'keep' | 'delete'>
}
