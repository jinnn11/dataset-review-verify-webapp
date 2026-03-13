#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

import gradio as gr
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


def _load_dotenv_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _configure_runtime_env(repo_root: Path) -> None:
    _load_dotenv_file(repo_root / ".env")
    os.environ.setdefault("APP_CONFIG_PATH", str(repo_root / "app_config.yaml"))
    os.environ.setdefault("DATASET_ROOT_DIR", str(repo_root / "data"))
    os.environ.setdefault("DATABASE_URL", f"sqlite:///{(repo_root / 'data' / 'review.db').resolve()}")
    os.environ.setdefault("SESSION_COOKIE_SECURE", "false")
    os.environ.setdefault("AUTO_INGEST_ON_STARTUP", "true")

    backend_dir = repo_root / "backend"
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))


def _ensure_frontend_dist(repo_root: Path, build_frontend: bool) -> Path:
    frontend_dir = repo_root / "frontend"
    dist_dir = frontend_dir / "dist"
    index_file = dist_dir / "index.html"

    if index_file.exists():
        return dist_dir

    if not build_frontend:
        raise FileNotFoundError(
            "frontend/dist/index.html not found. Run with --build-frontend "
            "or build frontend manually using `cd frontend && npm install && npm run build`."
        )

    try:
        subprocess.run(["npm", "install"], cwd=frontend_dir, check=True)
        subprocess.run(["npm", "run", "build"], cwd=frontend_dir, check=True)
    except FileNotFoundError as exc:
        raise RuntimeError(
            "npm was not found. To keep the same React UI, either:\n"
            "1) Install Node.js/npm in user space (no sudo) and rerun, or\n"
            "2) Build frontend/dist on another machine and copy it to this server.\n"
            "Expected file: frontend/dist/index.html"
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"Frontend build failed (exit {exc.returncode}).") from exc

    if not index_file.exists():
        raise FileNotFoundError("Frontend build completed but dist/index.html is still missing.")
    return dist_dir


def _mount_spa(app: FastAPI, dist_dir: Path, *, add_root_redirect: bool) -> None:
    dist_root = dist_dir.resolve()
    assets_dir = dist_root / "assets"
    if assets_dir.exists():
        app.mount("/app/assets", StaticFiles(directory=str(assets_dir)), name="review-assets")
        # Compatibility alias: some built bundles still request absolute "/assets/*".
        # Serving both paths prevents blank iframe loads caused by 404 static assets.
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="review-assets-root")

    index_path = dist_root / "index.html"
    index_html = index_path.read_text(encoding="utf-8")
    index_html = index_html.replace('src="/assets/', 'src="/app/assets/')
    index_html = index_html.replace('href="/assets/', 'href="/app/assets/')

    if add_root_redirect:
        @app.get("/", include_in_schema=False)
        def root_redirect() -> RedirectResponse:
            return RedirectResponse(url="/gradio")

    @app.get("/app", include_in_schema=False)
    def serve_app_root() -> HTMLResponse:
        return HTMLResponse(index_html)

    @app.get("/app/{asset_path:path}", include_in_schema=False)
    def serve_app_assets(asset_path: str) -> FileResponse:
        candidate = (dist_root / asset_path).resolve()
        try:
            candidate.relative_to(dist_root)
        except ValueError:
            return FileResponse(index_path)
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index_path)


def _iframe_html() -> str:
    nonce = int(time.time() * 1000)
    return (
        f'<iframe src="/app?ts={nonce}" '
        'style="width:100%;height:80vh;border:1px solid #444;border-radius:10px;background:#111;"></iframe>'
    )


def _build_gradio_panel(*, standalone_share_mode: bool) -> gr.Blocks:
    panel_route = "/" if standalone_share_mode else "/gradio"
    with gr.Blocks(title="Dataset Review Launcher") as demo:
        gr.Markdown(
            f"""
# Dataset Review and Verification
This Gradio entrypoint preserves the original React review UI and backend behavior.

- Main review app: `/app`
- Gradio panel: `{panel_route}`
- API: `/api/v1/*`
"""
        )

        with gr.Row():
            open_btn = gr.Button("Reload Embedded Review App")

        frame = gr.HTML(value=_iframe_html())
        open_btn.click(fn=_iframe_html, outputs=frame)
        gr.HTML('<a href="/app" target="_blank" rel="noopener noreferrer">Open Review App in New Tab</a>')

        gr.Markdown(
            """
Use your existing credentials from `.env` (`ADMIN_USERNAME`, `ADMIN_PASSWORD`).
For HTTP-only servers, keep `SESSION_COOKIE_SECURE=false`.
"""
        )
    return demo


def _initialize_backend_state() -> None:
    from app.core.config import get_dataset_config, settings  # pylint: disable=import-error,import-outside-toplevel
    from app.db.init_db import init_db  # pylint: disable=import-error,import-outside-toplevel
    from app.db.session import SessionLocal  # pylint: disable=import-error,import-outside-toplevel
    from app.services.ingestion import run_ingestion  # pylint: disable=import-error,import-outside-toplevel

    init_db()
    if settings.auto_ingest_on_startup:
        try:
            with SessionLocal() as db:
                run_ingestion(db, get_dataset_config())
        except Exception:  # noqa: BLE001
            # Keep app booting even if ingest fails.
            pass


def _attach_backend_endpoints(host_app: FastAPI, *, add_cors: bool) -> None:
    from app.api.router import api_router  # pylint: disable=import-error,import-outside-toplevel

    if add_cors:
        host_app.add_middleware(
            CORSMiddleware,
            allow_origins=["https://localhost", "http://localhost:5173"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @host_app.get("/healthz", include_in_schema=False)
    def health() -> dict[str, str]:
        return {"status": "ok"}

    host_app.include_router(api_router)


def create_gradio_host_app(build_frontend: bool) -> FastAPI:
    repo_root = _repo_root()
    _configure_runtime_env(repo_root)

    from app.main import create_app  # pylint: disable=import-error,import-outside-toplevel

    api_app = create_app()
    dist_dir = _ensure_frontend_dist(repo_root, build_frontend=build_frontend)
    _mount_spa(api_app, dist_dir, add_root_redirect=True)

    panel = _build_gradio_panel(standalone_share_mode=False)
    return gr.mount_gradio_app(api_app, panel, path="/gradio")


def create_gradio_share_demo(build_frontend: bool) -> tuple[gr.Blocks, Path]:
    repo_root = _repo_root()
    _configure_runtime_env(repo_root)
    dist_dir = _ensure_frontend_dist(repo_root, build_frontend=build_frontend)

    demo = _build_gradio_panel(standalone_share_mode=True)
    return demo, dist_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Run dataset review app with Gradio entrypoint")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=7860)
    parser.add_argument("--build-frontend", action="store_true", help="Build frontend if dist is missing")
    parser.add_argument("--share", action="store_true", help="Enable Gradio public share link mode")
    args = parser.parse_args()

    if args.share:
        demo, dist_dir = create_gradio_share_demo(build_frontend=args.build_frontend)
        try:
            live_app, local_url, share_url = demo.launch(
                share=True,
                server_name=args.host,
                server_port=args.port,
                show_error=True,
                inbrowser=False,
                prevent_thread_lock=True,
            )
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                "Failed to start Gradio share mode. This usually means outbound internet/tunnel access is blocked."
            ) from exc

        _mount_spa(live_app, dist_dir, add_root_redirect=False)
        _initialize_backend_state()
        _attach_backend_endpoints(live_app, add_cors=False)

        print(f"Local URL: {local_url}")
        print(f"Share URL: {share_url}")
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            demo.close()
        return

    app = create_gradio_host_app(build_frontend=args.build_frontend)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
