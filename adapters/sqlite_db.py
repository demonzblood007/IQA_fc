"""SQLite-backed DatabasePort implementation using SQLAlchemy Core."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Column,
    MetaData,
    String,
    Float,
    Table,
    create_engine,
    text,
)
from sqlalchemy.exc import IntegrityError

from core.domain import IQAScore, Job, JobStatus
from core.exceptions import DuplicateJobError
from core.ports import DatabasePort


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


metadata = MetaData()

jobs_table = Table(
    "jobs",
    metadata,
    Column("job_id", String, primary_key=True),
    Column("image_path", String, nullable=False),
    Column("webhook_url", String, nullable=False),
    Column("status", String, nullable=False, default="PENDING"),
    Column("score_overall", Float, nullable=True),
    Column("score_sharpness", Float, nullable=True),
    Column("score_brightness", Float, nullable=True),
    Column("score_contrast", Float, nullable=True),
    Column("error", String, nullable=True),
    Column("created_at", String, nullable=False),
    Column("updated_at", String, nullable=False),
)


class SQLiteDBAdapter(DatabasePort):
    """DatabasePort implementation backed by a SQLite file via SQLAlchemy Core.

    Creates the ``jobs`` table on first use if it does not already exist.
    Suitable for PoC and single-node deployments. For production, swap with
    ``DynamoDBAdapter`` without any changes to ``core/``.
    """

    def __init__(self, db_path: str = "./iqa_jobs.db") -> None:
        """Initialize the adapter and ensure the schema exists.

        Args:
            db_path: Path to the SQLite database file. Defaults to
                ``./iqa_jobs.db`` relative to the working directory.
                Use ``":memory:"`` for an ephemeral in-memory database.
        """
        self._engine = create_engine(f"sqlite:///{db_path}")
        metadata.create_all(self._engine)

    def create_job(self, job: Job) -> None:
        """Insert a new job record into the database with PENDING status.

        Both ``created_at`` and ``updated_at`` are set to the current UTC time.
        Score fields are left NULL until the worker completes processing.

        Args:
            job: The ``Job`` domain object to persist. ``job.job_id`` must be
                unique across all existing records.

        Raises:
            DuplicateJobError: If a job with the same ``job_id`` already exists.
        """
        now = _utc_now()
        try:
            with self._engine.begin() as conn:
                conn.execute(
                    jobs_table.insert().values(
                        job_id=job.job_id,
                        image_path=job.image_path,
                        webhook_url=job.webhook_url,
                        status=job.status.value,
                        score_overall=None,
                        score_sharpness=None,
                        score_brightness=None,
                        score_contrast=None,
                        error=job.error,
                        created_at=now,
                        updated_at=now,
                    )
                )
        except IntegrityError as exc:
            raise DuplicateJobError(
                f"Job with job_id '{job.job_id}' already exists."
            ) from exc

    def get_job(self, job_id: str) -> Optional[Job]:
        """Retrieve a job record by its unique identifier.

        Reconstructs the ``IQAScore`` sub-object only when the job status is
        ``COMPLETED`` and score data is present in the database.

        Args:
            job_id: The UUID string identifying the job to retrieve.

        Returns:
            A fully populated ``Job`` domain object if found, or ``None`` if
            no record with the given ``job_id`` exists.
        """
        with self._engine.connect() as conn:
            row = conn.execute(
                jobs_table.select().where(jobs_table.c.job_id == job_id)
            ).fetchone()

        if row is None:
            return None

        score: Optional[IQAScore] = None
        if row.status == JobStatus.COMPLETED and row.score_overall is not None:
            score = IQAScore(
                overall=row.score_overall,
                sharpness=row.score_sharpness,
                brightness=row.score_brightness,
                contrast=row.score_contrast,
            )

        return Job(
            job_id=row.job_id,
            image_path=row.image_path,
            webhook_url=row.webhook_url,
            status=JobStatus(row.status),
            score=score,
            error=row.error,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def update_job_status(self, job_id: str, status: JobStatus) -> None:
        """Update only the status field of an existing job record.

        Also refreshes ``updated_at`` to the current UTC time. Used by the
        worker to transition a job from PENDING → PROCESSING.

        Args:
            job_id: The UUID string identifying the job to update.
            status: The new ``JobStatus`` value to set.
        """
        with self._engine.begin() as conn:
            conn.execute(
                jobs_table.update()
                .where(jobs_table.c.job_id == job_id)
                .values(status=status.value, updated_at=_utc_now())
            )

    def update_job_result(
        self, job_id: str, score: IQAScore, status: JobStatus
    ) -> None:
        """Persist the IQA scoring result and final status for a completed job.

        Writes all four score dimensions (overall, sharpness, brightness,
        contrast) alongside the terminal status (COMPLETED or FAILED) and
        refreshes ``updated_at``.

        Args:
            job_id: The UUID string identifying the job to update.
            score: The ``IQAScore`` produced by ``IQAScoringEngine.score``.
            status: The terminal ``JobStatus`` — typically ``COMPLETED`` or
                ``FAILED``.
        """
        with self._engine.begin() as conn:
            conn.execute(
                jobs_table.update()
                .where(jobs_table.c.job_id == job_id)
                .values(
                    status=status.value,
                    score_overall=score.overall,
                    score_sharpness=score.sharpness,
                    score_brightness=score.brightness,
                    score_contrast=score.contrast,
                    updated_at=_utc_now(),
                )
            )
