from __future__ import annotations

from pathlib import Path

from app.core.config import settings


def _admin_csrf(client) -> str:
    login_response = client.post("/api/v1/auth/login", json={"username": "admin", "password": "pass123"})
    assert login_response.status_code == 200
    return login_response.json()["csrf_token"]


def test_undo_delete_restores_needs_review_state(client, monkeypatch):
    monkeypatch.setattr(settings, "enable_soft_delete", True)
    csrf_token = _admin_csrf(client)

    delete_response = client.post("/api/v1/files/soft-delete/1", headers={"X-CSRF-Token": csrf_token})
    assert delete_response.status_code == 200

    undo_response = client.post("/api/v1/files/undo/1", headers={"X-CSRF-Token": csrf_token})
    assert undo_response.status_code == 200
    undo_payload = undo_response.json()
    assert undo_payload["restored_at"] is not None
    assert undo_payload["restored_by"] is not None

    queue_response = client.get("/api/v1/review/queue?limit=10")
    assert queue_response.status_code == 200
    queue_payload = queue_response.json()
    alpha_group = next(group for group in queue_payload["items"] if group["group_key"] == "alpha")
    image_row = next(image for image in alpha_group["generated_images"] if image["id"] == 1)
    assert image_row["current_state"] == "needs_review"


def test_progress_includes_active_and_trashed_counts(client, monkeypatch):
    monkeypatch.setattr(settings, "enable_soft_delete", True)
    csrf_token = _admin_csrf(client)

    delete_response = client.post("/api/v1/files/soft-delete/1", headers={"X-CSRF-Token": csrf_token})
    assert delete_response.status_code == 200

    progress_response = client.get("/api/v1/progress/summary")
    assert progress_response.status_code == 200
    payload = progress_response.json()
    assert payload["total_images"] == 3
    assert payload["active_images"] == 2
    assert payload["trashed_images"] == 1
    assert payload["reviewed"] == 1
    assert payload["delete"] == 1


def test_soft_delete_conflict_for_already_trashed_image(client, monkeypatch):
    monkeypatch.setattr(settings, "enable_soft_delete", True)
    csrf_token = _admin_csrf(client)

    first_delete = client.post("/api/v1/files/soft-delete/1", headers={"X-CSRF-Token": csrf_token})
    assert first_delete.status_code == 200

    second_delete = client.post("/api/v1/files/soft-delete/1", headers={"X-CSRF-Token": csrf_token})
    assert second_delete.status_code == 409


def test_restore_records_restored_by(client, monkeypatch):
    monkeypatch.setattr(settings, "enable_soft_delete", True)
    csrf_token = _admin_csrf(client)

    delete_response = client.post("/api/v1/files/soft-delete/1", headers={"X-CSRF-Token": csrf_token})
    assert delete_response.status_code == 200
    operation_id = delete_response.json()["operation_id"]

    restore_response = client.post(f"/api/v1/files/restore/{operation_id}", headers={"X-CSRF-Token": csrf_token})
    assert restore_response.status_code == 200
    restore_payload = restore_response.json()
    assert restore_payload["restored_at"] is not None
    assert restore_payload["restored_by"] is not None


def test_undo_returns_404_when_trash_file_missing(client, monkeypatch):
    monkeypatch.setattr(settings, "enable_soft_delete", True)
    csrf_token = _admin_csrf(client)

    delete_response = client.post("/api/v1/files/soft-delete/1", headers={"X-CSRF-Token": csrf_token})
    assert delete_response.status_code == 200
    trash_path = Path(delete_response.json()["trash_path"])
    trash_path.unlink()

    undo_response = client.post("/api/v1/files/undo/1", headers={"X-CSRF-Token": csrf_token})
    assert undo_response.status_code == 404


def test_ingest_marks_missing_generated_files_as_trashed(client, dataset_root):
    csrf_token = _admin_csrf(client)

    missing_path = dataset_root / "generated" / "alpha_gen_2.png"
    missing_path.unlink()

    ingest_response = client.post("/api/v1/ingest/run", headers={"X-CSRF-Token": csrf_token})
    assert ingest_response.status_code == 200

    progress_response = client.get("/api/v1/progress/summary")
    assert progress_response.status_code == 200
    payload = progress_response.json()
    assert payload["active_images"] == 2
    assert payload["trashed_images"] == 1

    queue_response = client.get("/api/v1/review/queue?limit=10")
    assert queue_response.status_code == 200
    queue_payload = queue_response.json()
    alpha_group = next(group for group in queue_payload["items"] if group["group_key"] == "alpha")
    image_ids = [image["id"] for image in alpha_group["generated_images"]]
    assert 2 not in image_ids
