"""Integration tests for the FastAPI ingestion layer (api/main.py)."""
from __future__ import annotations

import io
import tempfile

import pytest
from PIL import Image
from starlette.testclient import TestClient

from adapters.local_queue import LocalQueueAdapter
from adapters.local_storage import LocalStorageAdapter
from adapters.sqlite_db import SQLiteDBAdapter
from api.main import app, get_job_service
from core.job_service import JobService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_jpeg_bytes() -> bytes:
    """Create a minimal valid JPEG image in memory using Pillow."""
    buf = io.BytesIO()
    img = Image.new("RGB", (10, 10), color=(128, 64, 32))
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _make_test_job_service(tmp_path: str) -> JobService:
    """Return a JobService wired to isolated local adapters."""
    storage = LocalStorageAdapter(base_dir=tmp_path)
    # Use a real temp file — avoids SQLAlchemy shared-MetaData issues with :memory:
    db_path = str(tmp_path) + "/test_jobs.db"
    database = SQLiteDBAdapter(db_path=db_path)
    queue = LocalQueueAdapter()
    return JobService(storage=storage, database=database, queue=queue)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def client(tmp_path):  # type: ignore[no-untyped-def]
    """TestClient with dependency-overridden JobService for test isolation."""
    job_service = _make_test_job_service(str(tmp_path))

    app.dependency_overrides[get_job_service] = lambda: job_service
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_submit_job_valid(client: TestClient) -> None:
    """POST a valid JPEG with a valid webhook_url → 202 with job_id."""
    jpeg_bytes = _make_jpeg_bytes()
    response = client.post(
        "/jobs",
        data={"webhook_url": "https://example.com/hook"},
        files={"image": ("photo.jpg", jpeg_bytes, "image/jpeg")},
    )
    assert response.status_code == 202
    body = response.json()
    assert "job_id" in body
    assert isinstance(body["job_id"], str)
    assert len(body["job_id"]) > 0


def test_get_job_unknown(client: TestClient) -> None:
    """GET /jobs/<nonexistent-id> → 404."""
    response = client.get("/jobs/nonexistent-id-12345")
    assert response.status_code == 404


def test_submit_job_bad_mime(client: TestClient) -> None:
    """POST a file with content_type text/plain → 422."""
    response = client.post(
        "/jobs",
        data={"webhook_url": "https://example.com/hook"},
        files={"image": ("file.txt", b"hello world", "text/plain")},
    )
    assert response.status_code == 422


def test_submit_job_ssrf_localhost(client: TestClient) -> None:
    """POST with webhook_url http://localhost/hook → 422 (SSRF)."""
    jpeg_bytes = _make_jpeg_bytes()
    response = client.post(
        "/jobs",
        data={"webhook_url": "http://localhost/hook"},
        files={"image": ("photo.jpg", jpeg_bytes, "image/jpeg")},
    )
    assert response.status_code == 422


def test_submit_job_ssrf_private_ip(client: TestClient) -> None:
    """POST with webhook_url http://192.168.1.1/hook → 422 (SSRF)."""
    jpeg_bytes = _make_jpeg_bytes()
    response = client.post(
        "/jobs",
        data={"webhook_url": "http://192.168.1.1/hook"},
        files={"image": ("photo.jpg", jpeg_bytes, "image/jpeg")},
    )
    assert response.status_code == 422


def test_submit_job_ssrf_bad_scheme(client: TestClient) -> None:
    """POST with webhook_url ftp://example.com/hook → 422 (bad scheme)."""
    jpeg_bytes = _make_jpeg_bytes()
    response = client.post(
        "/jobs",
        data={"webhook_url": "ftp://example.com/hook"},
        files={"image": ("photo.jpg", jpeg_bytes, "image/jpeg")},
    )
    assert response.status_code == 422
