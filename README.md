# Dataset Review Web App

Private web app for mask-vs-generated image review with safe delete workflow, auditability, and production deployment support.

## Tech Stack
- Backend: FastAPI + SQLAlchemy + PostgreSQL
- Frontend: React + TypeScript + Vite
- Reverse proxy: Nginx with HTTPS
- Deployment: Docker Compose
- Storage: local disk mounted at `/data`

## Current Review Workflow
1. Login (`reviewer` or `admin`).
2. Open `Review Queue` mode.
3. For each mask, select generated images using the card selector.
4. Apply bulk action with `Keep Selected` for accepted images or `Soft Delete Selected` (admin only) for rejected images.
5. Decisions are auto-saved immediately. No manual save step.
6. Queue shows 4 visible cards at a time and live-replaces with remaining images for the same mask.
7. When a mask is complete, the app auto-advances to the next mask.
8. `Undo Last Batch` restores only the most recent bulk action.
9. Open `Review History` mode to scroll all current keep/delete results with mask+image pairs.

## Current UI/Behavior Features
- Bulk multi-select review flow (no per-image Keep/Delete buttons)
- Corner-positioned bulk controls: top-left `Keep Selected`, top-right `Soft Delete Selected`, bottom-right `Undo Last Batch`
- Search by `group_key`
- Keyboard shortcuts in review mode: `Space` toggle selection, `K` keep selected, `D` soft-delete selected (admin), `Esc` clear selection, arrow keys move focus
- Progress chips: `Total`, `Active`, `Reviewed`, `Keep`, `Delete`
- Counter semantics: snapshot-based (`Reviewed = Keep + Delete` from latest decision state)
- Review history timestamps displayed in `America/New_York`

## Safety and Data Guarantees
- Login required for protected routes
- CSRF protection for state-changing requests
- Role-based behavior: `reviewer` can keep and undo decisions, `admin` can keep + soft delete + restore/undo delete + ingest
- Soft delete only in app flow (no hard delete endpoint)
- Soft delete moves files to trash folder and writes deletion operation audit
- Undo/restore resets image to reviewable state

## Dataset Configuration
Update `app_config.yaml`:

```yaml
dataset:
  root_dir: /data
  masks_dir: masks
  generated_dir: generated
  trash_dir: .trash
  mask_regex: '^(?P<group_key>.+)_mask\.(png|jpg|jpeg|webp)$'
  generated_regex: '^(?P<group_key>.+)_gen_[0-9]+\.(png|jpg|jpeg|webp)$'
```

Expected host layout:

```text
data/
  masks/
  generated/
  .trash/
```

## Environment
Create `.env` from `.env.example` and set secure values:

```env
SECRET_KEY=replace-with-long-random-secret
ADMIN_USERNAME=admin
ADMIN_PASSWORD=change-admin-password
ENABLE_SOFT_DELETE=false
AUTO_INGEST_ON_STARTUP=true
```

Notes:
- Runtime uses `.env`.
- `.env.example` is a template only.

## Run (Docker Compose)
1. Generate development certs:

```bash
./infra/scripts/generate-dev-cert.sh
```

2. Start services:

```bash
docker compose up -d --build
```

3. Open:
- `https://localhost`

Important:
- Login/session cookie is configured as `Secure`, so use HTTPS (not plain HTTP).

## Run (Gradio, No Docker / No sudo)
Use this path when you cannot run Docker on the server.

1. Start with the launcher script:

```bash
chmod +x gradio/run_gradio.sh
./gradio/run_gradio.sh
```

2. Open:
- Gradio prints a local URL and a public share URL (`*.gradio.live`) when `GRADIO_SHARE=true` (default).
- Main review UI path remains `/app` on that same host.
- Gradio panel path:
  - `/` in share mode (default)
  - `/gradio` when `GRADIO_SHARE=false`

Notes:
- This keeps the existing React UI/features (no UI rewrite).
- API stays available at `/api/v1/*`.
- Non-Docker defaults are applied automatically (SQLite in `data/review.db`, local dataset root, HTTP-safe cookie settings).
- See `gradio/README.md` for details.
- Disable share-link mode when needed:

```bash
GRADIO_SHARE=false ./gradio/run_gradio.sh
```

### Gradio Server Deployment Steps
Use these steps when deploying to a remote server without sudo/docker.

1. Copy project to server and place dataset in `data/masks` and `data/generated`.
2. Set `.env` (at minimum: `SECRET_KEY`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `ENABLE_SOFT_DELETE`).
3. Ensure `frontend/dist` exists:
- If server has Node/npm, `run_gradio.sh` can build automatically when missing.
- If server has no npm, build `frontend/dist` on another machine and copy that folder to server.
4. Start service:

```bash
cd <repo-root>
chmod +x gradio/run_gradio.sh
nohup ./gradio/run_gradio.sh > gradio.log 2>&1 &
```

5. Verify:

```bash
curl -I http://127.0.0.1:7860/
curl -I http://127.0.0.1:7860/app
curl -I http://127.0.0.1:7860/api/v1/auth/me
```

### Gradio Auto Public Link Notes
- Auto public link works only in Gradio `share=True` mode (enabled by default in `gradio/run_gradio.sh`).
- Share links are temporary (typically expire after about one week).
- If the share link does not appear, outbound internet/tunnel connectivity from server is blocked.
- For long-term stable production URLs, use a domain + reverse proxy.

## API Endpoints (Current)
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/me`
- `GET /api/v1/review/queue?cursor=&limit=&search=`
- `GET /api/v1/review/group/{group_id}`
- `GET /api/v1/review/history?cursor=&limit=&search=`
- `POST /api/v1/review/decision` (keep/needs_review)
- `POST /api/v1/review/decision/bulk` (keep-only in current UI flow)
- `POST /api/v1/review/undo/{image_id}`
- `GET /api/v1/progress/summary`
- `POST /api/v1/files/soft-delete/{image_id}` (admin)
- `POST /api/v1/files/undo/{image_id}` (admin)
- `POST /api/v1/files/restore/{operation_id}` (admin)
- `POST /api/v1/ingest/run` (admin)
- `GET /api/v1/media/mask/{group_id}`
- `GET /api/v1/media/image/{image_id}`

## Testing
Run backend tests in container:

```bash
docker compose exec -T backend pytest -q
```

## Repeatable Test Reset
If you want to rerun the same dataset scenario repeatedly:

1. Save baseline once:

```bash
./infra/scripts/save-test-baseline.sh
```

2. Restore baseline anytime (files + DB review state reset):

```bash
./infra/scripts/restore-test-baseline.sh
```

Note: this script now supports both modes automatically:
- Docker mode (uses running `backend` container if available)
- Gradio/non-Docker mode (uses local Python + SQLite/postgres from `.env`)

## Repository Layout
- `backend/` FastAPI app and tests
- `frontend/` React app
- `infra/nginx/default.conf` HTTPS reverse proxy
- `app_config.yaml` dataset/file-name pairing rules
- `docker-compose.yml` deployment stack

## Production Notes
- Replace dev certificates with valid TLS certificates.
- Set strong `SECRET_KEY` and admin credentials.
- Restrict server access to trusted users/networks.
- Keep regular backups of Postgres volume and `/data`.

## Author
Author: Swaminathan Sankaran
M.S. Engineering Science (Data Science), University at Buffalo

This web application was developed to support dataset review and verification for the
CUBS lab. The tool is focused on mask-vs-generated image review,
bulk keep/soft-delete decisions, undo support, and auditable dataset curation.
