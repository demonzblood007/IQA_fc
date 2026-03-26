"""DynamoDBAdapter — future AWS DynamoDB implementation stub."""
from __future__ import annotations

from typing import Optional

from core.domain import IQAScore, Job, JobStatus
from core.ports import DatabasePort


class DynamoDBAdapter(DatabasePort):
    """Stub for future AWS DynamoDB database adapter.

    Replace this with a real boto3-backed implementation when migrating
    from the PoC to cloud infrastructure. No changes to core/ are required.
    """

    def create_job(self, job: Job) -> None:
        raise NotImplementedError("DynamoDBAdapter is not yet implemented.")

    def get_job(self, job_id: str) -> Optional[Job]:
        raise NotImplementedError("DynamoDBAdapter is not yet implemented.")

    def update_job_status(self, job_id: str, status: JobStatus) -> None:
        raise NotImplementedError("DynamoDBAdapter is not yet implemented.")

    def update_job_result(self, job_id: str, score: IQAScore, status: JobStatus) -> None:
        raise NotImplementedError("DynamoDBAdapter is not yet implemented.")
