import type { ProgressSummary, UserRole } from '../types'

interface TopBarProps {
  username: string
  role: UserRole
  progress: ProgressSummary | null
  search: string
  onSearchChange: (value: string) => void
  onSearchSubmit: () => void
  onLogout: () => Promise<void>
  onIngest: () => Promise<void>
}

export function TopBar({
  username,
  role,
  progress,
  search,
  onSearchChange,
  onSearchSubmit,
  onLogout,
  onIngest
}: TopBarProps) {
  return (
    <header className="top-bar">
      <div className="top-bar-meta">
        <h1>Mask Review Queue</h1>
        <span className="reviewer-tag">Reviewer: {username}</span>
        <div className="top-bar-progress">
          <span>Total {progress?.total_images ?? 0}</span>
          <span>Active {progress?.active_images ?? 0}</span>
          <span title="Reviewed = latest decision state is Keep or Delete">Reviewed {progress?.reviewed ?? 0}</span>
          <span>Keep {progress?.keep ?? 0}</span>
          <span>Delete {progress?.delete ?? 0}</span>
        </div>
      </div>
      <div className="top-bar-actions">
        <input
          value={search}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder="Search group key"
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              onSearchSubmit()
            }
          }}
        />
        <button onClick={onSearchSubmit}>Search</button>
        {role === 'admin' ? <button onClick={() => void onIngest()}>Ingest</button> : null}
        <button className="ghost" onClick={() => void onLogout()}>
          Logout
        </button>
      </div>
    </header>
  )
}
