"""Unit tests for MLWorker."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, call

from core.domain import IQAScore, Job, JobStatus
from core.exceptions import ImageDecodeError
from worker.ml_worker import MLWorker


def _make_worker(**overrides) -> MLWorker:
    defaults = dict(
        queue=MagicMock(),
        database=MagicMock(),
        storage=MagicMock(),
        scoring_engine=MagicMock(),
        webhook_client=MagicMock(),
    )
    defaults.update(overrides)
    return MLWorker(**defaults)


def _make_job(job_id: str = "job-1") -> Job:
    return Job(
        job_id=job_id,
        image_path="/tmp/test.jpg",
        webhook_url="https://example.com/hook",
        status=JobStatus.PENDING,
    )


class TestHappyPath:
    def test_happy_path(self) -> None:
        score = IQAScore(overall=0.8, sharpness=0.7, brightness=0.9, contrast=0.8)
        database = MagicMock()
        storage = MagicMock()
        scoring_engine = MagicMock()
        webhook_client = MagicMock()

        database.get_job.return_value = _make_job()
        storage.load_image.return_value = b"fake-image-bytes"
        scoring_engine.score.return_value = score

        worker = _make_worker(
            database=database,
            storage=storage,
            scoring_engine=scoring_engine,
            webhook_client=webhook_client,
        )

        worker.process_job("job-1")

        database.update_job_status.assert_called_once_with("job-1", JobStatus.PROCESSING)
        database.update_job_result.assert_called_once_with("job-1", score, JobStatus.COMPLETED)
        webhook_client.notify.assert_called_once_with(
            "https://example.com/hook", "job-1", score, JobStatus.COMPLETED
        )


class TestImageDecodeFailure:
    def test_image_decode_failure_sets_failed(self) -> None:
        database = MagicMock()
        storage = MagicMock()
        webhook_client = MagicMock()

        database.get_job.return_value = _make_job()
        storage.load_image.side_effect = ImageDecodeError("bad image")

        worker = _make_worker(
            database=database,
            storage=storage,
            webhook_client=webhook_client,
        )

        with pytest.raises(ImageDecodeError):
            worker.process_job("job-1")

        # PROCESSING transition must happen first
        database.update_job_status.assert_any_call("job-1", JobStatus.PROCESSING)
        # FAILED transition must happen on error
        database.update_job_status.assert_any_call("job-1", JobStatus.FAILED)
        # Webhook must be notified with FAILED status
        notify_call = webhook_client.notify.call_args
        assert notify_call is not None
        assert notify_call.kwargs.get("status") == JobStatus.FAILED or notify_call.args[3] == JobStatus.FAILED


class TestWebhookFailureDoesNotAffectDB:
    def test_webhook_failure_does_not_affect_db_state(self) -> None:
        score = IQAScore(overall=0.8, sharpness=0.7, brightness=0.9, contrast=0.8)
        database = MagicMock()
        storage = MagicMock()
        scoring_engine = MagicMock()
        webhook_client = MagicMock()

        database.get_job.return_value = _make_job()
        storage.load_image.return_value = b"fake-image-bytes"
        scoring_engine.score.return_value = score
        webhook_client.notify.side_effect = Exception("webhook down")

        worker = _make_worker(
            database=database,
            storage=storage,
            scoring_engine=scoring_engine,
            webhook_client=webhook_client,
        )

        # Should NOT raise — webhook failures are fire-and-forget
        worker.process_job("job-1")

        # DB must still reflect COMPLETED
        database.update_job_result.assert_called_once_with("job-1", score, JobStatus.COMPLETED)
