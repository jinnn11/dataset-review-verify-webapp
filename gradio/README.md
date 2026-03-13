# Gradio Deployment (No Docker, No sudo)

This folder provides a script-based deployment path that keeps the existing app behavior:
- React UI is served at `/app`
- FastAPI API remains at `/api/v1/*`
- Gradio public share link is enabled by default (`share=True`)

## Why this works
- No rewrite of UI/features into Gradio components.
- Gradio is used as an entrypoint panel and launcher route.
- Existing review workflow, bulk decisions, soft delete, undo, and history remain unchanged.

## Prerequisites
- Python 3.10+
- Node.js + npm only if `frontend/dist` is not already present

## Run
From repo root:

```bash
chmod +x gradio/run_gradio.sh
./gradio/run_gradio.sh
```

Output:
- Gradio prints:
  - local URL (usually `http://<server-host>:7860`)
  - public share URL (`https://*.gradio.live`)
- Main review UI is at `/app` on the same host.
- Gradio panel route:
  - `/` in share mode (default)
  - `/gradio` when share mode is disabled

Disable share mode:

```bash
GRADIO_SHARE=false ./gradio/run_gradio.sh
```

Custom host/port:

```bash
GRADIO_HOST=0.0.0.0 GRADIO_PORT=7871 ./gradio/run_gradio.sh
```

If the selected port is already in use, launcher exits with a clear message.

## If npm is not available on server
You still have two no-sudo options:

1. Install Node.js in user space (e.g., `nvm`) and run `./gradio/run_gradio.sh`.
2. Build frontend once elsewhere and copy `frontend/dist` to server, then run `./gradio/run_gradio.sh`.

The launcher uses existing `frontend/dist` when present and skips npm build.

## Environment notes
- Script loads values from `.env` if present.
- Defaults for non-Docker mode:
  - `DATABASE_URL=sqlite:///data/review.db`
  - `DATASET_ROOT_DIR=<repo>/data`
  - `APP_CONFIG_PATH=<repo>/app_config.yaml`
  - `SESSION_COOKIE_SECURE=false`

If your server has HTTPS in front of this app, set `SESSION_COOKIE_SECURE=true`.

## Full Server Checklist (No sudo)
1. Clone repo and enter directory.
2. Prepare dataset folders:

```bash
mkdir -p data/masks data/generated data/.trash
```

3. Create `.env` in repo root:

```env
SECRET_KEY=replace-with-a-long-random-secret
ADMIN_USERNAME=admin
ADMIN_PASSWORD=change-this-password
ENABLE_SOFT_DELETE=true
AUTO_INGEST_ON_STARTUP=true
```

4. Start app:

```bash
chmod +x gradio/run_gradio.sh
nohup env GRADIO_HOST=0.0.0.0 GRADIO_PORT=7860 GRADIO_SHARE=true ./gradio/run_gradio.sh > gradio.log 2>&1 &
```

5. Verify:

```bash
curl -I http://127.0.0.1:7860/
curl -I http://127.0.0.1:7860/app
curl -I http://127.0.0.1:7860/api/v1/auth/me
```

## Operations
View logs:

```bash
tail -f gradio.log
```

Stop/restart:

```bash
lsof -iTCP:7860 -sTCP:LISTEN
kill <PID>
nohup env GRADIO_HOST=0.0.0.0 GRADIO_PORT=7860 GRADIO_SHARE=true ./gradio/run_gradio.sh > gradio.log 2>&1 &
```

## Multiple Apps On One Server
Run each app on a different port, and if needed use separate DB/data paths.

Example second app:

```bash
nohup env GRADIO_PORT=7861 DATABASE_URL=sqlite:////path/appB.db DATASET_ROOT_DIR=/path/appB_data ./gradio/run_gradio.sh > appB.log 2>&1 &
```
