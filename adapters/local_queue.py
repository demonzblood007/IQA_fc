"""In-process queue-backed QueuePort implementation."""

import queue
from typing import Optional

from core.ports import QueuePort


class LocalQueueAdapter(QueuePort):
    """QueuePort implementation backed by Python's standard ``queue.Queue``.

    Operates entirely in-process and in-memory. Thread-safe for single-process
    use. Not suitable for multi-process or distributed deployments — use
    ``SQSQueueAdapter`` for those scenarios.
    """

    def __init__(self) -> None:
        """Initialize the adapter with an empty in-memory FIFO queue."""
        self._queue: queue.Queue[str] = queue.Queue()

    def enqueue(self, job_id: str) -> None:
        """Push a job ID onto the tail of the queue.

        Args:
            job_id: Unique identifier of the job to enqueue. The worker will
                dequeue this value to locate and process the corresponding job.
        """
        self._queue.put(job_id)

    def dequeue(self) -> Optional[str]:
        """Pop the next job ID from the head of the queue without blocking.

        Returns:
            The next ``job_id`` string if the queue is non-empty, or ``None``
            if the queue is currently empty.
        """
        try:
            return self._queue.get(block=False)
        except queue.Empty:
            return None
