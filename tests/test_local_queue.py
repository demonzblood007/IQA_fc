from adapters.local_queue import LocalQueueAdapter


def test_enqueue_dequeue_roundtrip() -> None:
    q = LocalQueueAdapter()
    q.enqueue("job-123")
    assert q.dequeue() == "job-123"


def test_fifo_order() -> None:
    q = LocalQueueAdapter()
    ids = ["job-1", "job-2", "job-3"]
    for job_id in ids:
        q.enqueue(job_id)
    for job_id in ids:
        assert q.dequeue() == job_id


def test_dequeue_empty_returns_none() -> None:
    q = LocalQueueAdapter()
    assert q.dequeue() is None


def test_dequeue_after_all_consumed_returns_none() -> None:
    q = LocalQueueAdapter()
    q.enqueue("job-abc")
    q.dequeue()
    assert q.dequeue() is None
