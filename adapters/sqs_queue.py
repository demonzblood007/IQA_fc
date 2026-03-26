"""SQSQueueAdapter — future AWS SQS implementation stub."""
from __future__ import annotations

from typing import Optional

from core.ports import QueuePort


class SQSQueueAdapter(QueuePort):
    """Stub for future AWS SQS queue adapter.

    Replace this with a real boto3-backed implementation when migrating
    from the PoC to cloud infrastructure. No changes to core/ are required.
    """

    def enqueue(self, job_id: str) -> None:
        raise NotImplementedError("SQSQueueAdapter is not yet implemented.")

    def dequeue(self) -> Optional[str]:
        raise NotImplementedError("SQSQueueAdapter is not yet implemented.")
