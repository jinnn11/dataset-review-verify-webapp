# Dataset Review Web App

Private web app for mask-vs-generated image review and verification, with audited soft delete, undo, and reviewer authentication.

## What It Does
- Shows one mask and related generated images.
- Reviewer selects visible images in bulk and applies `Keep` or `Soft Delete` (admin only).
- Autosaves immediately (no manual save button).
- Shows 4 visible cards at a time and live-replaces as decisions are made.
- Auto-advances to the next mask when current mask is fully resolved.
- Supports `Undo Last Batch` (single-level undo for the most recent bulk action).
- Includes `Review History` mode for scrollable keep/delete records with mask+image previews.

## Current Stack
- Backend: FastAPI + SQLAlchemy
- Frontend: React + TypeScript + Vite
- Data storage:
  - Docker mode: PostgreSQL
  - Gradio/non-Docker mode: SQLite (`data/review.db`) by default
- File storage: local disk (`data/`)
- Optional deployment:
  - Docker Compose + Nginx + HTTPS
  - Gradio launcher (no Docker / no sudo)

## Current UI / Behavior
- Bulk multi-select flow (no per-image keep/delete buttons).
- Corner controls in review panel:
  - Top-left: `Keep Selected`
  - Top-right: `Soft Delete Selected`
  - Bottom-right: `Undo Last Batch`
- Search by `group_key`.
- Keyboard shortcuts (review mode):
  - `Space`: toggle selection on focused card
  - `K`: keep selected
  - `D`: soft-delete selected (admin)
  - `Esc`: clear selection
  - Arrow keys: move focus
- Progress chips: `Total`, `Active`, `Reviewed`, `Keep`, `Delete`
- Counter semantics:
  - snapshot-based latest state
  - `Reviewed = Keep + Delete`
- History timestamps are rendered in `America/New_York`.

## Safety Model
- Login required for protected routes.
- CSRF required for state-changing requests.
- Role behavior:
  - `reviewer`: keep + undo decision + review/history browsing
  - `admin`: all reviewer actions + soft-delete/undo-delete/restore + ingest
- No hard-delete endpoint in app flow.
- Soft delete moves files to trash and writes audit rows.
- Undo/restore marks image reviewable again (`needs_review`).

## Dataset Layout
Expected directory structure:

```text
data/
  masks/
  generated/
  .trash/
```

`app_config.yaml` controls filename grouping:

```yaml
dataset:
  root_dir: /data
  masks_dir: masks
  generated_dir: generated
  trash_dir: .trash
  mask_regex: '^(?P<group_key>.+)_mask\.(png|jpg|jpeg|webp)$'
  generated_regex: '^(?P<group_key>.+)_gen_[0-9]+\.(png|jpg|jpeg|webp)$'
```

## Environment (`.env`)
Use `.env` in repo root. Current required values:

```env
SECRET_KEY=replace-with-long-random-secret
ADMIN_USERNAME=admin
ADMIN_PASSWORD=change-admin-password
ENABLE_SOFT_DELETE=true
AUTO_INGEST_ON_STARTUP=true
```

Notes:
- Runtime reads `.env`.
- In this repo snapshot, `.env.example` is not used by startup scripts.

## Run Option 1: Gradio (No Docker / No sudo)
Recommended when server does not allow Docker/sudo.

```bash
chmod +x gradio/run_gradio.sh
./gradio/run_gradio.sh
```

The launcher now supports:
- `GRADIO_SHARE=true|false` (default `true`)
- `GRADIO_HOST` (default `0.0.0.0`)
- `GRADIO_PORT` (default `7860`)

Examples:

```bash
GRADIO_SHARE=false ./gradio/run_gradio.sh
GRADIO_PORT=7871 ./gradio/run_gradio.sh
GRADIO_HOST=0.0.0.0 GRADIO_PORT=7871 ./gradio/run_gradio.sh
```

Behavior:
- Main app path: `/app`
- Panel path:
  - `/` when share mode is on
  - `/gradio` when share mode is off
- API path: `/api/v1/*`
- If `frontend/dist` is missing, launcher attempts build (requires npm).
- If selected port is busy, launcher exits with a clear message.

Public link notes:
- Share mode prints a temporary `*.gradio.live` URL.
- Link lifetime is temporary (typically around one week).
- If link is not printed, outbound tunnel/network may be blocked.

## Detailed Gradio Deployment Guide (Server)
Use this if you are deploying on a fresh server account.

### 1) What must exist
- Python 3.10+ available as `python3`
- Git (to clone/update repo)
- Dataset directories and files:
  - `data/masks`
  - `data/generated`
- Optional: Node.js + npm only if `frontend/dist` is missing

### 2) If Node/npm is not available
You have two valid paths:
- Build frontend on another machine and copy `frontend/dist` to server.
- Install Node in user-space (`nvm`) and allow server build.

### 3) Prepare repository
```bash
cd <your-workspace>
git clone <your-repo-url> dataset_review_app
cd dataset_review_app
```

### 4) Prepare dataset
```bash
mkdir -p data/masks data/generated data/.trash
# copy your files into data/masks and data/generated
```

### 5) Create `.env`
```env
SECRET_KEY=replace-with-a-long-random-secret
ADMIN_USERNAME=admin
ADMIN_PASSWORD=change-this-password
ENABLE_SOFT_DELETE=true
AUTO_INGEST_ON_STARTUP=true
```

Optional overrides (only if needed):
```env
DATABASE_URL=sqlite:////absolute/path/to/review.db
DATASET_ROOT_DIR=/absolute/path/to/data
APP_CONFIG_PATH=/absolute/path/to/app_config.yaml
SESSION_COOKIE_SECURE=false
```

### 6) Start app
Foreground:
```bash
chmod +x gradio/run_gradio.sh
GRADIO_HOST=0.0.0.0 GRADIO_PORT=7860 GRADIO_SHARE=true ./gradio/run_gradio.sh
```

Background:
```bash
chmod +x gradio/run_gradio.sh
nohup env GRADIO_HOST=0.0.0.0 GRADIO_PORT=7860 GRADIO_SHARE=true ./gradio/run_gradio.sh > gradio.log 2>&1 &
```

### 7) Verify
```bash
curl -I http://127.0.0.1:7860/
curl -I http://127.0.0.1:7860/app
curl -I http://127.0.0.1:7860/api/v1/auth/me
```

Expected:
- `/` returns Gradio panel (`200`)
- `/app` returns React app HTML (`200`)
- `/api/v1/auth/me` returns `401` before login (this is correct)

### 8) Logs and process operations
View logs:
```bash
tail -f gradio.log
```

Stop by port:
```bash
lsof -iTCP:7860 -sTCP:LISTEN
kill <PID>
```

Restart:
```bash
lsof -iTCP:7860 -sTCP:LISTEN
kill <PID>
nohup env GRADIO_HOST=0.0.0.0 GRADIO_PORT=7860 GRADIO_SHARE=true ./gradio/run_gradio.sh > gradio.log 2>&1 &
```

### 9) Running multiple apps on same server
Use separate ports and separate state/data paths per app.

Example app A:
```bash
nohup env GRADIO_PORT=7860 ./gradio/run_gradio.sh > appA.log 2>&1 &
```

Example app B:
```bash
nohup env GRADIO_PORT=7861 DATABASE_URL=sqlite:////path/appB.db DATASET_ROOT_DIR=/path/appB_data ./gradio/run_gradio.sh > appB.log 2>&1 &
```

## Run Option 2: Docker Compose

```bash
./infra/scripts/generate-dev-cert.sh
docker compose up -d --build
```

Open:
- `https://localhost`

Important:
- Docker setup uses secure cookie mode (`SESSION_COOKIE_SECURE=true`), so use HTTPS.

## Persistence and Restart Behavior
- App state persists across restart as long as DB and `data/` are preserved.
- Gradio default DB is `data/review.db`.
- Restart continues from latest saved state (autosave is immediate).
- If trash files are externally purged, old soft-delete undo/restore may fail for those purged files.

## API Surface (Current)
- Auth:
  - `POST /api/v1/auth/login`
  - `POST /api/v1/auth/logout`
  - `GET /api/v1/auth/me`
- Review:
  - `GET /api/v1/review/queue`
  - `GET /api/v1/review/group/{group_id}`
  - `GET /api/v1/review/history`
  - `POST /api/v1/review/decision`
  - `POST /api/v1/review/decision/bulk`
  - `POST /api/v1/review/undo/{image_id}`
- File ops:
  - `POST /api/v1/files/soft-delete/{image_id}` (admin)
  - `POST /api/v1/files/undo/{image_id}` (admin)
  - `POST /api/v1/files/restore/{operation_id}` (admin)
- Progress / ingest / media:
  - `GET /api/v1/progress/summary`
  - `POST /api/v1/ingest/run` (admin)
  - `GET /api/v1/media/mask/{group_id}`
  - `GET /api/v1/media/image/{image_id}`

## Testing
Docker mode:

```bash
docker compose exec -T backend pytest -q
```

Local mode (using `.venv-gradio`):

```bash
PYTHONPATH=backend .venv-gradio/bin/pytest backend/tests -q
```

## Repeatable Test Reset
Save baseline once:

```bash
./infra/scripts/save-test-baseline.sh
```

Restore baseline later (files + DB review state reset + re-ingest):

```bash
./infra/scripts/restore-test-baseline.sh
```

`restore-test-baseline.sh` supports both:
- Docker backend path (if container is running)
- Local Gradio/non-Docker path

## Repository Layout
- `backend/`: FastAPI app, services, schemas, tests
- `frontend/`: React app
- `gradio/`: Gradio host launcher
- `infra/`: nginx config and utility scripts
- `app_config.yaml`: dataset parsing/grouping config
- `docker-compose.yml`: Docker deployment stack

## Citation
See `CITATION.cff`.

## Author
Author: Swaminathan Sankaran  
M.S. Engineering Science (Data Science), University at Buffalo

This web application was developed to support dataset review and verification for the CUBS lab. The tool focuses on mask-vs-generated image review, bulk keep/soft-delete decisions, undo support, and auditable dataset curation.
