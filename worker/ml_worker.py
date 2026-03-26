"""Background ML worker — polls the queue and processes IQA jobs."""

from __future__ import annotations

import logging
import time
from typing import Optional

from core.domain import JobStatus
from core.exceptions import ImageDecodeError
from core.ports import DatabasePort, QueuePort, StoragePort
from core.scoring_engine import IQAScoringEngine
from core.webhook_client import WebhookClient

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS: int = 1


class MLWorker:
    """Polls the queue and processes image quality assessment jobs end-to-end."""

    def __init__(
        self,
        queue: QueuePort,
        database: DatabasePort,
        storage: StoragePort,
        scoring_engine: IQAScoringEngine,
        webhook_client: WebhookClient,
    ) -> None:
        self._queue = queue
        self._database = database
        self._storage = storage
        self._scoring_engine = scoring_engine
        self._webhook_client = webhook_client

    def run(self) -> None:
        """Blocking poll loop. Runs until process is terminated."""
        logger.info("MLWorker started, polling queue every %ds", POLL_INTERVAL_SECONDS)
        while True:
            job_id: Optional[str] = self._queue.dequeue()
            if job_id is None:
                time.sleep(POLL_INTERVAL_SECONDS)
                continue
            try:
                self.process_job(job_id)
            except Exception as exc:
                logger.error("Unhandled error processing job %s: %s", job_id, exc)
                try:
                    self._database.update_job_status(job_id, JobStatus.FAILED)
                except Exception as db_exc:
                    logger.error("Failed to mark job %s as FAILED: %s", job_id, db_exc)

    def process_job(self, job_id: str) -> None:
        """Processes a single job end-to-end."""
        # Transition to PROCESSING
        self._database.update_job_status(job_id, JobStatus.PROCESSING)

        try:
            job = self._database.get_job(job_id)
            image_bytes = self._storage.load_image(job.image_path)
            score = self._scoring_engine.score(image_bytes)
            self._database.update_job_result(job_id, score, JobStatus.COMPLETED)
            try:
                self._webhook_client.notify(
                    job.webhook_url, job_id, score, JobStatus.COMPLETED
                )
            except Exception as webhook_exc:
                logger.warning(
                    "Webhook notification failed for job %s: %s", job_id, webhook_exc
                )
        except Exception as exc:
            logger.error("Job %s failed: %s", job_id, exc)
            self._database.update_job_status(job_id, JobStatus.FAILED)
            try:
                job = self._database.get_job(job_id)
                webhook_url = job.webhook_url if job else ""
            except Exception:
                webhook_url = ""
            try:
                self._webhook_client.notify(
                    webhook_url, job_id, None, JobStatus.FAILED, error=str(exc)
                )
            except Exception as webhook_exc:
                logger.warning(
                    "Webhook failure notification failed for job %s: %s",
                    job_id,
                    webhook_exc,
                )
            raise
