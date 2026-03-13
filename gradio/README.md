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
