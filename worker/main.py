"""Worker process entry point."""

import logging

logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    from adapters.local_queue import LocalQueueAdapter
    from adapters.local_storage import LocalStorageAdapter
    from adapters.sqlite_db import SQLiteDBAdapter
    from core.scoring_engine import IQAScoringEngine
    from core.webhook_client import WebhookClient
    from worker.ml_worker import MLWorker

    storage = LocalStorageAdapter(base_dir="/tmp/iqa_images")
    database = SQLiteDBAdapter(db_path="./iqa_jobs.db")
    queue = LocalQueueAdapter()
    scoring_engine = IQAScoringEngine()
    webhook_client = WebhookClient()

    worker = MLWorker(
        queue=queue,
        database=database,
        storage=storage,
        scoring_engine=scoring_engine,
        webhook_client=webhook_client,
    )
    worker.run()
