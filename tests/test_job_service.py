"""Unit tests for JobService using mock adapters."""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock, call

import pytest

from core.domain import Job, JobStatus
from core.job_service import JobService


def _make_service() -> tuple[JobService, MagicMock, MagicMock, MagicMock]:
    storage = MagicMock()
    database = MagicMock()
    queue = MagicMock()
    storage.save_image.return_value = "/tmp/images/test.jpg"
    service = JobService(storage=storage, database=database, queue=queue)
    return service, storage, database, queue


class TestSubmitJob:
    def test_returns_valid_uuid(self) -> None:
        service, _, _, _ = _make_service()
        job_id = service.submit_job(b"image_bytes", "https://example.com/webhook")
        # Must be parseable as a UUID without raising
        parsed = uuid.UUID(job_id)
        assert str(parsed) == job_id

    def test_correct_call_order(self) -> None:
        service, storage, database, queue = _make_service()
        manager = MagicMock()
        manager.attach_mock(storage, "storage")
        manager.attach_mock(database, "database")
        manager.attach_mock(queue, "queue")

        job_id = service.submit_job(b"image_bytes", "https://example.com/webhook")

        # Extract the Job object that was passed to create_job
        created_job = database.create_job.call_args[0][0]

        expected_calls = [
            call.storage.save_image(job_id, b"image_bytes"),
            call.database.create_job(created_job),
            call.queue.enqueue(job_id),
        ]
        assert manager.mock_calls == expected_calls

    def test_storage_failure_prevents_db_write_and_enqueue(self) -> None:
        service, storage, database, queue = _make_service()
        storage.save_image.side_effect = OSError("disk full")

        with pytest.raises(OSError, match="disk full"):
            service.submit_job(b"image_bytes", "https://example.com/webhook")

        database.create_job.assert_not_called()
        queue.enqueue.assert_not_called()


class TestGetJobStatus:
    def test_delegates_to_database_get_job(self) -> None:
        service, _, database, _ = _make_service()
        expected_job = Job(
            job_id="abc-123",
            image_path="/tmp/images/abc-123.jpg",
            webhook_url="https://example.com/webhook",
            status=JobStatus.PENDING,
        )
        database.get_job.return_value = expected_job

        result = service.get_job_status("abc-123")

        database.get_job.assert_called_once_with("abc-123")
        assert result is expected_job

    def test_returns_none_when_job_not_found(self) -> None:
        service, _, database, _ = _make_service()
        database.get_job.return_value = None

        result = service.get_job_status("nonexistent-id")

        database.get_job.assert_called_once_with("nonexistent-id")
        assert result is None
