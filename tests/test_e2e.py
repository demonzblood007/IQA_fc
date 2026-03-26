"""End-to-end integration tests for the full IQA pipeline.

Uses real PoC adapters (LocalStorageAdapter, SQLiteDBAdapter, LocalQueueAdapter)
and patches WebhookClient.notify to capture webhook calls without real HTTP.
"""
from __future__ import annotations

import io
from unittest.mock import patch

import pytest
from PIL import Image
from starlette.testclient import TestClient

from adapters.local_queue import LocalQueueAdapter
from adapters.local_storage import LocalStorageAdapter
from adapters.sqlite_db import SQLiteDBAdapter
from api.main import app, get_job_service
from core.domain import JobStatus
from core.job_service import JobService
from core.scoring_engine import IQAScoringEngine
from core.webhook_client import WebhookClient
from worker.ml_worker import MLWorker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_jpeg_bytes(width: int = 50, height: int = 50) -> bytes:
    """Create a real JPEG image in memory using Pillow."""
    buf = io.BytesIO()
    img = Image.new("RGB", (width, height), color=(120, 80, 200))
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _make_wired_services(tmp_path: str) -> tuple[JobService, LocalQueueAdapter, SQLiteDBAdapter, LocalStorageAdapter]:
    """Wire real PoC adapters and return them alongside the JobService."""
    storage = LocalStorageAdapter(base_dir=str(tmp_path) + "/images")
    database = SQLiteDBAdapter(db_path=str(tmp_path) + "/jobs.db")
    queue = LocalQueueAdapter()
    job_service = JobService(storage=storage, database=database, queue=queue)
    return job_service, queue, database, storage


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_full_e2e_pipeline(tmp_path: object) -> None:
    """Full pipeline: API submit → worker process → DB result → webhook delivery."""
    job_service, queue, database, storage = _make_wired_services(str(tmp_path))

    app.dependency_overrides[get_job_service] = lambda: job_service

    webhook_calls: list = []

    try:
        with patch(
            "core.webhook_client.WebhookClient.notify",
            side_effect=lambda *a, **kw: webhook_calls.append((a, kw)),
        ):
            # 1. Submit job via API
            with TestClient(app) as client:
                jpeg_bytes = _make_jpeg_bytes()
                response = client.post(
                    "/jobs",
                    data={"webhook_url": "https://example.com/hook"},
                    files={"image": ("photo.jpg", jpeg_bytes, "image/jpeg")},
                )
                assert response.status_code == 202
                body = response.json()
                assert "job_id" in body
                job_id: str = body["job_id"]

            # 2. Run worker to process the job directly (no background thread)
            scoring_engine = IQAScoringEngine()
            webhook_client = WebhookClient()
            worker = MLWorker(
                queue=queue,
                database=database,
                storage=storage,
                scoring_engine=scoring_engine,
                webhook_client=webhook_client,
            )
            worker.process_job(job_id)

    finally:
        app.dependency_overrides.clear()

    # 3. Verify final job state in DB
    job = database.get_job(job_id)
    assert job is not None
    assert job.status == JobStatus.COMPLETED
    assert job.score is not None
    assert 0.0 <= job.score.overall <= 1.0
    assert 0.0 <= job.score.sharpness <= 1.0
    assert 0.0 <= job.score.brightness <= 1.0
    assert 0.0 <= job.score.contrast <= 1.0

    # 4. Verify webhook was called exactly once with correct payload
    assert len(webhook_calls) == 1
    call_args = webhook_calls[0][0]  # positional args tuple
    # notify(webhook_url, job_id, score, status)
    assert call_args[1] == job_id
    assert call_args[3] == JobStatus.COMPLETED


def test_e2e_via_api_status_endpoint(tmp_path: object) -> None:
    """GET /jobs/{job_id} returns COMPLETED status with all score fields after processing."""
    job_service, queue, database, storage = _make_wired_services(str(tmp_path))

    app.dependency_overrides[get_job_service] = lambda: job_service

    try:
        with patch("core.webhook_client.WebhookClient.notify"):
            with TestClient(app) as client:
                # Submit
                jpeg_bytes = _make_jpeg_bytes()
                submit_resp = client.post(
                    "/jobs",
                    data={"webhook_url": "https://example.com/hook"},
                    files={"image": ("photo.jpg", jpeg_bytes, "image/jpeg")},
                )
                assert submit_resp.status_code == 202
                job_id = submit_resp.json()["job_id"]

                # Verify PENDING status via API before processing
                status_resp = client.get(f"/jobs/{job_id}")
                assert status_resp.status_code == 200
                assert status_resp.json()["status"] == "PENDING"

            # Process the job
            worker = MLWorker(
                queue=queue,
                database=database,
                storage=storage,
                scoring_engine=IQAScoringEngine(),
                webhook_client=WebhookClient(),
            )
            worker.process_job(job_id)

            # Query completed status via API
            with TestClient(app) as client:
                status_resp = client.get(f"/jobs/{job_id}")
                assert status_resp.status_code == 200
                data = status_resp.json()

    finally:
        app.dependency_overrides.clear()

    assert data["status"] == "COMPLETED"
    assert data["score"] is not None
    score = data["score"]
    assert 0.0 <= score["overall"] <= 1.0
    assert 0.0 <= score["sharpness"] <= 1.0
    assert 0.0 <= score["brightness"] <= 1.0
    assert 0.0 <= score["contrast"] <= 1.0
