"""Tests for SQLiteDBAdapter — tasks 5.1 and 5.2."""

import pytest

from core.domain import IQAScore, Job, JobStatus
from core.exceptions import DuplicateJobError
from adapters.sqlite_db import SQLiteDBAdapter


@pytest.fixture
def db(tmp_path) -> SQLiteDBAdapter:
    return SQLiteDBAdapter(db_path=str(tmp_path / "test.db"))


def _pending_job(job_id: str = "job-1") -> Job:
    return Job(
        job_id=job_id,
        image_path="/tmp/img.jpg",
        webhook_url="http://example.com/hook",
        status=JobStatus.PENDING,
    )


# --- create_job / get_job ---

def test_create_and_get_job(db: SQLiteDBAdapter) -> None:
    job = _pending_job()
    db.create_job(job)
    result = db.get_job(job.job_id)
    assert result is not None
    assert result.job_id == job.job_id
    assert result.image_path == job.image_path
    assert result.webhook_url == job.webhook_url
    assert result.status == JobStatus.PENDING
    assert result.score is None
    assert result.created_at is not None
    assert result.updated_at is not None


def test_get_job_returns_none_for_unknown(db: SQLiteDBAdapter) -> None:
    assert db.get_job("nonexistent") is None


def test_create_job_sets_timestamps(db: SQLiteDBAdapter) -> None:
    db.create_job(_pending_job())
    result = db.get_job("job-1")
    assert result is not None
    assert result.created_at is not None
    assert result.updated_at is not None
    # Both timestamps should be equal on creation
    assert result.created_at == result.updated_at


# --- 5.2: DuplicateJobError on duplicate job_id ---

def test_create_job_raises_duplicate_job_error(db: SQLiteDBAdapter) -> None:
    job = _pending_job()
    db.create_job(job)
    with pytest.raises(DuplicateJobError):
        db.create_job(job)


def test_duplicate_error_does_not_overwrite_original(db: SQLiteDBAdapter) -> None:
    job = _pending_job()
    db.create_job(job)
    duplicate = Job(
        job_id=job.job_id,
        image_path="/other/path.jpg",
        webhook_url="http://other.com/hook",
        status=JobStatus.PENDING,
    )
    with pytest.raises(DuplicateJobError):
        db.create_job(duplicate)
    # Original record is unchanged
    stored = db.get_job(job.job_id)
    assert stored is not None
    assert stored.image_path == job.image_path


# --- update_job_status ---

def test_update_job_status(db: SQLiteDBAdapter) -> None:
    db.create_job(_pending_job())
    db.update_job_status("job-1", JobStatus.PROCESSING)
    result = db.get_job("job-1")
    assert result is not None
    assert result.status == JobStatus.PROCESSING


# --- update_job_result ---

def test_update_job_result(db: SQLiteDBAdapter) -> None:
    db.create_job(_pending_job())
    score = IQAScore(overall=0.8, sharpness=0.7, brightness=0.9, contrast=0.8)
    db.update_job_result("job-1", score, JobStatus.COMPLETED)
    result = db.get_job("job-1")
    assert result is not None
    assert result.status == JobStatus.COMPLETED
    assert result.score is not None
    assert result.score.overall == pytest.approx(0.8)
    assert result.score.sharpness == pytest.approx(0.7)
    assert result.score.brightness == pytest.approx(0.9)
    assert result.score.contrast == pytest.approx(0.8)


def test_get_job_no_score_when_not_completed(db: SQLiteDBAdapter) -> None:
    db.create_job(_pending_job())
    db.update_job_status("job-1", JobStatus.PROCESSING)
    result = db.get_job("job-1")
    assert result is not None
    assert result.score is None
