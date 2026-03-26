"""WebhookClient — delivers job results to a webhook URL with exponential backoff retry."""

from __future__ import annotations

import logging
import time
from dataclasses import asdict
from typing import Optional

import httpx

from core.domain import IQAScore, JobStatus

logger = logging.getLogger(__name__)

MAX_WEBHOOK_RETRIES = 3


class WebhookClient:
    """Posts job completion payloads to a caller-supplied webhook URL."""

    def notify(
        self,
        webhook_url: str,
        job_id: str,
        score: Optional[IQAScore],
        status: JobStatus,
        error: Optional[str] = None,
    ) -> None:
        """Send a POST notification to *webhook_url*.

        Retries up to MAX_WEBHOOK_RETRIES times on HTTP errors or non-2xx
        responses using exponential backoff (1 s, 2 s, 4 s …).  After all
        retries are exhausted the failure is logged and the method returns
        normally — webhook failures never affect job state in the database.
        """
        payload: dict = {
            "job_id": job_id,
            "status": status.value,
            "score": asdict(score) if score is not None else None,
            "error": error,
        }

        with httpx.Client() as client:
            for attempt in range(MAX_WEBHOOK_RETRIES):
                try:
                    response = client.post(webhook_url, json=payload)
                    if response.is_success:
                        return
                    logger.warning(
                        "Webhook delivery returned non-2xx status %s for job %s "
                        "(attempt %d/%d)",
                        response.status_code,
                        job_id,
                        attempt + 1,
                        MAX_WEBHOOK_RETRIES,
                    )
                except httpx.RequestError as exc:
                    logger.warning(
                        "Webhook delivery raised %s for job %s (attempt %d/%d): %s",
                        type(exc).__name__,
                        job_id,
                        attempt + 1,
                        MAX_WEBHOOK_RETRIES,
                        exc,
                    )

                # Exponential backoff — skip sleep after the last attempt
                if attempt < MAX_WEBHOOK_RETRIES - 1:
                    time.sleep(2**attempt)

        logger.error(
            "Webhook delivery failed after %d attempts for job %s",
            MAX_WEBHOOK_RETRIES,
            job_id,
        )
