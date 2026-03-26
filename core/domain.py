from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class JobStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass
class IQAScore:
    overall: float
    sharpness: float
    brightness: float
    contrast: float


@dataclass
class Job:
    job_id: str
    image_path: str
    webhook_url: str
    status: JobStatus
    score: Optional[IQAScore] = None
    error: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
