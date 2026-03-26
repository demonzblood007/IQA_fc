"""JobService — orchestrates job submission and status queries via injected ports."""
from __future__ import annotations

import uuid
from typing import Optional

from core.domain import Job, JobStatus
from core.ports import DatabasePort, QueuePort, StoragePort


class JobService:
    """Orchestrates job submission. Depends only on ports, never on adapters."""

    def __init__(
        self,
        storage: StoragePort,
        database: DatabasePort,
        queue: QueuePort,
    ) -> None:
        self._storage = storage
        self._database = database
        self._queue = queue

    def submit_job(self, image_bytes: bytes, webhook_url: str) -> str:
        """Create a new IQA job and return its job_id (UUID string).

        Steps:
        1. Generate a UUID job_id
        2. Persist image via storage (propagates any exception immediately)
        3. Create job record in DB with status=PENDING
        4. Enqueue job_id
        5. Return job_id
        """
        job_id = str(uuid.uuid4())

        # May raise — propagate immediately; no DB write, no enqueue
        image_path = self._storage.save_image(job_id, image_bytes)

        job = Job(
            job_id=job_id,
            image_path=image_path,
            webhook_url=webhook_url,
            status=JobStatus.PENDING,
        )

        self._database.create_job(job)
        self._queue.enqueue(job_id)

        return job_id

    def get_job_status(self, job_id: str) -> Optional[Job]:
        """Return current job state, or None if not found."""
        return self._database.get_job(job_id)
