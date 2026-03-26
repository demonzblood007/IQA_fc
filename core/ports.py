"""Abstract port interfaces for the IQA microservice.

Defines the contracts that all infrastructure adapters must satisfy.
Core business logic depends only on these interfaces — never on concrete
adapter implementations.
"""

from abc import ABC, abstractmethod
from typing import Optional

from core.domain import IQAScore, Job, JobStatus


class StoragePort(ABC):
    """Abstract interface for binary image storage.

    Implementations must provide durable save/load semantics: bytes written
    via ``save_image`` must be retrievable via ``load_image`` using the
    returned path/key.
    """

    @abstractmethod
    def save_image(self, job_id: str, image_bytes: bytes) -> str:
        """Persist raw image bytes and return a retrieval handle.

        Args:
            job_id: Unique identifier for the job; used to derive the
                storage key or filename.
            image_bytes: Raw binary content of the image to persist.

        Returns:
            An opaque string (filesystem path, S3 key, etc.) that can be
            passed to ``load_image`` to retrieve the same bytes.
        """
        ...

    @abstractmethod
    def load_image(self, image_path: str) -> bytes:
        """Retrieve raw image bytes using a handle from ``save_image``.

        Args:
            image_path: The storage handle returned by a prior ``save_image``
                call for this job.

        Returns:
            Raw binary content of the stored image.

        Raises:
            FileNotFoundError: If the handle does not resolve to stored data.
        """
        ...


class DatabasePort(ABC):
    """Abstract interface for job state persistence.

    Implementations must provide consistent CRUD semantics for ``Job``
    records across the full PENDING → PROCESSING → COMPLETED/FAILED lifecycle.
    """

    @abstractmethod
    def create_job(self, job: Job) -> None:
        """Insert a new job record.

        Args:
            job: The ``Job`` domain object to persist. ``job.job_id`` must be
                unique; implementations must enforce this constraint.

        Raises:
            DuplicateJobError: If a job with the same ``job_id`` already exists.
        """
        ...

    @abstractmethod
    def get_job(self, job_id: str) -> Optional[Job]:
        """Retrieve a job record by its unique identifier.

        Args:
            job_id: UUID string identifying the job to retrieve.

        Returns:
            The ``Job`` domain object if found, or ``None`` if no record
            with the given ``job_id`` exists.
        """
        ...

    @abstractmethod
    def update_job_status(self, job_id: str, status: JobStatus) -> None:
        """Update the status field of an existing job record.

        Args:
            job_id: UUID string identifying the job to update.
            status: The new ``JobStatus`` value to set.
        """
        ...

    @abstractmethod
    def update_job_result(self, job_id: str, score: IQAScore, status: JobStatus) -> None:
        """Persist the IQA scoring result and terminal status for a job.

        Args:
            job_id: UUID string identifying the job to update.
            score: The ``IQAScore`` produced by ``IQAScoringEngine.score``.
            status: Terminal ``JobStatus`` — typically ``COMPLETED`` or
                ``FAILED``.
        """
        ...


class QueuePort(ABC):
    """Abstract interface for job ID message queuing.

    Implementations must provide at-least-once delivery semantics for
    ``enqueue``/``dequeue`` pairs. The queue carries only ``job_id`` strings;
    full job data is retrieved from ``DatabasePort``.
    """

    @abstractmethod
    def enqueue(self, job_id: str) -> None:
        """Push a job ID onto the queue for worker pickup.

        Args:
            job_id: UUID string of the job to enqueue.
        """
        ...

    @abstractmethod
    def dequeue(self) -> Optional[str]:
        """Pop the next job ID from the queue without blocking.

        Returns:
            The next ``job_id`` string if the queue is non-empty, or ``None``
            if the queue is currently empty.
        """
        ...
